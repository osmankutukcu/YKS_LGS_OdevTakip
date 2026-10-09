# -*- coding: utf-8 -*-
"""
utils/analytics_engine.py

Amaç:
- Haftalık ve son gün aralıkları için öğrenci başına performans metriklerini
  hesaplayıp `ogrenci_performans` tablosuna yazar (mevcut Performans Paneli).
- Günlük özet, haftalık-ders kırılımı, kitap ilerleme ve cohort-kapsam tablolarını üretir
  (öğrenci detay ve rapor ekranları için).
- Python 3.9 uyumlu (Union pipe 'X | Y' KULLANILMAZ).

Bu dosyanın çıktıları şu yerlerden kullanılır:
- main_window.run_full_refresh()  -> rebuild_all(con),
                                     rebuild_performance_* çağrıları
- student_detail.py               -> ogrenci_perf_gunluk, ogrenci_perf_hafta_ders,
                                     ogrenci_kitap_ilerleme, cohort_kitap_kapsam
"""

from typing import Optional, Dict, Any, Tuple, List
import sqlite3
from datetime import date, datetime, timedelta

# ---------------------------------------------------------
#  Rapor ayarlarını okuyan küçük yardımcı
# ---------------------------------------------------------

def _get_report_settings(con: sqlite3.Connection) -> Dict[str, Any]:
    """
    services.report_settings.load_settings(con) çağırmayı dener.
    Hata alırsa boş dict döner (varsayılanlarla çalışır).
    """
    try:
        from services.report_settings import load_settings
    except Exception:
        return {}
    try:
        return load_settings(con)
    except Exception:
        return {}


# ------------------ Küçük tarih yardımcıları ------------------

def _week_bounds(d: date) -> Tuple[date, date]:
    s = d - timedelta(days=d.weekday())           # Pazartesi
    return s, s + timedelta(days=6)               # Pazar


def _lastN_bounds(d: date, days: int) -> Tuple[date, date]:
    """
    Son N gün (bugün dahil) için aralık döndürür.
    days >= 1 olmalı.
    """
    days = max(1, int(days))
    return d - timedelta(days=days - 1), d        # bugün dahil


def _iso(d: date) -> str:
    return d.isoformat()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ------------------ SQLite yardımcıları ------------------

def _register_sqlite_helpers(con: sqlite3.Connection) -> None:
    """SQLite’a küçük yardımcı fonksiyonlar ekle (idempotent)."""
    def _greatest(*args):
        vals = [a for a in args if a is not None]
        return max(vals) if vals else None

    def _least(*args):
        vals = [a for a in args if a is not None]
        return min(vals) if vals else None

    con.create_function("GREATEST", -1, _greatest)
    con.create_function("LEAST", -1, _least)


def _install_try_cast_date(con: sqlite3.Connection) -> None:
    """Metin→tarih dönüşümünde çökmeyi engeller; ordinal döndürür."""
    from datetime import datetime as _dt

    def _try_cast_date(s):
        if s is None:
            return None
        s = str(s).strip()
        if not s:
            return None
        fmts = ["%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]
        for f in fmts:
            try:
                return _dt.strptime(s, f).date().toordinal()
            except Exception:
                pass
        try:
            return _dt.fromisoformat(s).date().toordinal()
        except Exception:
            return None

    con.create_function("TRY_CAST_DATE", 1, _try_cast_date)


def _table_has_columns(con: sqlite3.Connection, table: str, cols: List[str]) -> bool:
    try:
        cur = con.execute(f"PRAGMA table_info({table})")
        present = {row["name"] for row in cur.fetchall()}
        return all(c in present for c in cols)
    except Exception:
        return False


def _first_existing_column(con: sqlite3.Connection, table: str, candidates: List[str]) -> Optional[str]:
    try:
        cur = con.execute(f"PRAGMA table_info({table})")
        present = {row["name"] for row in cur.fetchall()}
        for c in candidates:
            if c in present:
                return c
    except Exception:
        pass
    return None


# ------------------ Şema güvencesi (tüm özet tablolar) ------------------

def ensure_performance_schema(con: sqlite3.Connection) -> None:
    _register_sqlite_helpers(con)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_performans (
            ogrenci_id     INTEGER NOT NULL,
            period_start   TEXT    NOT NULL,
            period_end     TEXT    NOT NULL,
            ilerleme_yuzde REAL    NOT NULL DEFAULT 0,
            gorev_bitti    INTEGER NOT NULL DEFAULT 0,
            gorev_toplam   INTEGER NOT NULL DEFAULT 0,
            kume_sayisi    INTEGER NOT NULL DEFAULT 0,
            gecikmis_kume  INTEGER NOT NULL DEFAULT 0,
            generated_at   TEXT    NOT NULL,
            UNIQUE(ogrenci_id, period_start, period_end)
        )
    """)
    con.commit()


def ensure_analytics_schemas(con: sqlite3.Connection) -> None:
    """Öğrenci detay ve rapor ekranlarının okuduğu tabloları güvenceye al."""
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_perf_gunluk(
            ogrenci_id INTEGER NOT NULL,
            gun        TEXT    NOT NULL,
            tamam      INTEGER DEFAULT 0,
            kismi      INTEGER DEFAULT 0,
            yapilmadi  INTEGER DEFAULT 0,
            geciken    INTEGER DEFAULT 0,
            PRIMARY KEY(ogrenci_id, gun)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_perf_hafta_ders(
            ogrenci_id INTEGER NOT NULL,
            week_start TEXT    NOT NULL,
            week_end   TEXT    NOT NULL,
            ders       TEXT    NOT NULL,
            toplam     INTEGER DEFAULT 0,
            bitti      INTEGER DEFAULT 0,
            yuzde      INTEGER DEFAULT 0,
            PRIMARY KEY(ogrenci_id, week_start, week_end, ders)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_kitap_ilerleme(
            ogrenci_id   INTEGER NOT NULL,
            ders         TEXT    NOT NULL,
            kitap        TEXT    NOT NULL,
            konu_say     INTEGER DEFAULT 0,
            bitti_say    INTEGER DEFAULT 0,
            yuzde        INTEGER DEFAULT 0,
            last_done_ts TEXT,
            PRIMARY KEY(ogrenci_id, ders, kitap)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cohort_kitap_kapsam(
            ders          TEXT NOT NULL,
            kitap         TEXT NOT NULL,
            konu          TEXT NOT NULL,
            done_count    INTEGER DEFAULT 0,
            student_count INTEGER DEFAULT 0,
            pct           INTEGER DEFAULT 0,
            PRIMARY KEY(ders, kitap, konu)
        )
    """)
    con.commit()


# ------------------ Esnek alan keşfi/predikatlar ------------------

def _detect_date_filters(con: sqlite3.Connection) -> Dict[str, str]:
    """
    odev_satir tablosunda tarih için kullanılacak sütunu seç.
    Öncelik: son_teslim, teslim_tarihi, bitis_tarihi, konu_tarihi, olusturma_tarihi
    """
    base = "odev_satir"
    for name in ["son_teslim", "teslim_tarihi", "bitis_tarihi", "konu_tarihi", "olusturma_tarihi", "tarih"]:
        if _table_has_columns(con, base, [name]):
            return {"date_col": name}
    return {"date_col": ""}  # yoksa tarih filtresi uygulanmaz


def _detect_done_predicate(con: sqlite3.Connection) -> str:
    """
    odev_satir üzerinde “tamamlandı”yı anlamak için esnek şart.
    - bitti_flag=1 veya durum in (...) veya bitis_tarihi NOT NULL vb.
    Ayrıca:
    - rapor_ayar.aktarilan_sayilma_sekli="done" ise 'aktarildi' durumunu
      da tamamlandı listesine ekler.
    """
    t = "odev_satir"
    parts: List[str] = []

    # Ayarlardan 'aktarildi' durumunun nasıl sayılacağını oku
    settings = _get_report_settings(con)
    aktarilan_as_done = settings.get("aktarilan_sayilma_sekli", "done") == "done"
    extra_done_statuses: List[str] = []
    if aktarilan_as_done:
        extra_done_statuses.extend(["aktarildi", "aktarılmış", "aktarildi.", "aktarildi "])

    if _table_has_columns(con, t, ["bitti_flag"]):
        parts.append("COALESCE(bitti_flag,0)=1")

    if _table_has_columns(con, t, ["durum"]):
        base_statuses = [
            'bitti', 'tamam', 'done', 'tamamlandı', 'tamamlandi',
            'yapildi', 'yapıldı', 'ok'
        ]
        if extra_done_statuses:
            base_statuses.extend(extra_done_statuses)
        # benzersiz + alt harf
        base_statuses = sorted({s.lower() for s in base_statuses})
        in_list = ",".join(f"'{s}'" for s in base_statuses)
        parts.append(f"LOWER(COALESCE(durum,'')) IN ({in_list})")

    if _table_has_columns(con, t, ["bitis_tarihi"]):
        parts.append("(bitis_tarihi IS NOT NULL AND TRIM(COALESCE(bitis_tarihi,''))<>'')")

    return "(" + " OR ".join(parts) + ")" if parts else "(0)"


def _detect_overdue_predicate(con: sqlite3.Connection) -> Optional[str]:
    """
    “gecikmiş” kümeler için bir koşul üretir (varsa).
    Örn: durum 'gecikmis' veya (done=0 ve bitis_tarihi > son_teslim)
    """
    t = "odev_satir"
    have_done = _detect_done_predicate(con)
    has_son = _table_has_columns(con, t, ["son_teslim"])
    has_bitis = _table_has_columns(con, t, ["bitis_tarihi"])
    has_durum = _table_has_columns(con, t, ["durum"])
    preds: List[str] = []
    if has_durum:
        preds.append("LOWER(COALESCE(durum,'')) IN ('gecikmis','gecikmiş')")
    if has_son and has_bitis:
        preds.append(f"({have_done}=0 AND TRY_CAST_DATE(bitis_tarihi) > TRY_CAST_DATE(son_teslim))")
    return "(" + " OR ".join(preds) + ")" if preds else None


def _date_between_predicate(date_col: str, start_iso: str, end_iso: str) -> str:
    """Tarih sütunu varsa aralık filtresi, yoksa hep TRUE."""
    if not date_col:
        return "1=1"
    return (f"(TRY_CAST_DATE({date_col}) IS NOT NULL "
            f"AND TRY_CAST_DATE({date_col}) BETWEEN TRY_CAST_DATE('{start_iso}') AND TRY_CAST_DATE('{end_iso}'))")


# ------------------ Çekirdek metrik hesapları (Performans Paneli) ------------------

def _compute_metrics_for_student(
    con: sqlite3.Connection,
    student_id: int,
    start_d: date,
    end_d: date
) -> Dict[str, Any]:
    """
    Tek bir öğrenci için metrikleri hesaplar.
    Dönüş: dict(gorev_bitti, gorev_toplam, kume_sayisi, gecikmis_kume, ilerleme_yuzde)
    """
    _install_try_cast_date(con)
    rng = (_iso(start_d), _iso(end_d))
    date_col = _detect_date_filters(con).get("date_col", "")

    # Görev tablosu var mı?
    try:
        con.execute("SELECT 1 FROM odev_satir LIMIT 1")
    except Exception:
        return dict(gorev_bitti=0, gorev_toplam=0, kume_sayisi=0, gecikmis_kume=0, ilerleme_yuzde=0.0)

    # Öğrenci sütunu?
    ogr_col = "ogrenci_id" if _table_has_columns(con, "odev_satir", ["ogrenci_id"]) else None
    if ogr_col is None:
        return dict(gorev_bitti=0, gorev_toplam=0, kume_sayisi=0, gecikmis_kume=0, ilerleme_yuzde=0.0)

    done_pred = _detect_done_predicate(con)
    where_rng = _date_between_predicate(date_col, rng[0], rng[1])

    # Toplam & biten
    total = int(con.execute(
        f"SELECT COUNT(*) FROM odev_satir WHERE {ogr_col}=? AND {where_rng}",
        (student_id,)
    ).fetchone()[0])

    done = int(con.execute(
        f"SELECT COUNT(*) FROM odev_satir WHERE {ogr_col}=? AND {where_rng} AND {done_pred}",
        (student_id,)
    ).fetchone()[0])

    # Küme sayısı
    kume_col = _first_existing_column(con, "odev_satir", ["kume_id", "kume", "cluster_id"])
    if kume_col:
        kume_say = int(con.execute(
            f"SELECT COUNT(DISTINCT {kume_col}) FROM odev_satir WHERE {ogr_col}=? AND {where_rng}",
            (student_id,)
        ).fetchone()[0])
    else:
        kume_say = 0

    # Gecikmiş küme
    overdue_pred = _detect_overdue_predicate(con)
    if overdue_pred and kume_col:
        gecikmis = int(con.execute(f"""
            SELECT COUNT(*) FROM (
              SELECT {kume_col}
                FROM odev_satir
               WHERE {ogr_col}=? AND {where_rng} AND {overdue_pred}
               GROUP BY {kume_col}
            ) t
        """, (student_id,)).fetchone()[0])
    else:
        gecikmis = 0

    pct = float(0.0 if total <= 0 else (done * 100.0) / max(1, total))
    return dict(
        gorev_bitti=done,
        gorev_toplam=total,
        kume_sayisi=kume_say,
        gecikmis_kume=gecikmis,
        ilerleme_yuzde=round(pct, 2)
    )


def _iter_student_ids(con: sqlite3.Connection) -> List[int]:
    try:
        cur = con.execute("SELECT id FROM ogrenci")
        return [int(r[0]) for r in cur.fetchall()]
    except Exception:
        return []


def _upsert_performance_row(
    con: sqlite3.Connection,
    student_id: int,
    start_d: date,
    end_d: date,
    metrics: Dict[str, Any]
) -> None:
    ensure_performance_schema(con)
    con.execute("""
        INSERT INTO ogrenci_performans
        (ogrenci_id, period_start, period_end,
         ilerleme_yuzde, gorev_bitti, gorev_toplam, kume_sayisi, gecikmis_kume, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ogrenci_id, period_start, period_end) DO UPDATE SET
            ilerleme_yuzde=excluded.ilerleme_yuzde,
            gorev_bitti   =excluded.gorev_bitti,
            gorev_toplam  =excluded.gorev_toplam,
            kume_sayisi   =excluded.kume_sayisi,
            gecikmis_kume =excluded.gecikmis_kume,
            generated_at  =excluded.generated_at
    """, (
        student_id,
        _iso(start_d), _iso(end_d),
        float(metrics.get("ilerleme_yuzde", 0.0)),
        int(metrics.get("gorev_bitti", 0)),
        int(metrics.get("gorev_toplam", 0)),
        int(metrics.get("kume_sayisi", 0)),
        int(metrics.get("gecikmis_kume", 0)),
        _now_iso()
    ))


def rebuild_performance_for_range(
    con: sqlite3.Connection,
    start_d: date,
    end_d: date
) -> None:
    """Verilen tarih aralığı için tüm öğrenciler adına `ogrenci_performans`ı günceller."""
    con.row_factory = sqlite3.Row
    _register_sqlite_helpers(con)
    ensure_performance_schema(con)

    ids = _iter_student_ids(con)
    if not ids:
        return

    for sid in ids:
        met = _compute_metrics_for_student(con, sid, start_d, end_d)
        _upsert_performance_row(con, sid, start_d, end_d, met)

    con.commit()


# ------------------ Dışa açık “hazır” fonksiyonlar (Performans Paneli) ------------------

def rebuild_performance_current_week(con: sqlite3.Connection, today: Optional[date] = None) -> Tuple[str, str]:
    """Bu haftanın (Pzt–Paz) özetini üretir -> ogrenci_performans."""
    if today is None:
        today = date.today()
    ws, we = _week_bounds(today)
    rebuild_performance_for_range(con, ws, we)
    return _iso(ws), _iso(we)


def rebuild_performance_last_30_days(con: sqlite3.Connection, today: Optional[date] = None) -> Tuple[str, str]:
    """
    Geriye dönük son 30 gün için özet üretir.
    (Bu fonksiyon eski API ile uyum için tutuluyor;
     günlük rebuild_all içindeki ayara göre çalışıyor.)
    """
    if today is None:
        today = date.today()
    s, e = _lastN_bounds(today, 30)
    rebuild_performance_for_range(con, s, e)
    return _iso(s), _iso(e)


# ------------------ Günlük/Haftalık/Kitap/Cohort Özetleri (Detay ekranları) ------------------

def rebuild_daily(con: sqlite3.Connection, start: date, end: date) -> None:
    """
    odev + odev_satir'dan günlük özet (tamam/kısmi/yapılmadı/geciken) yazar -> ogrenci_perf_gunluk.
    """
    ensure_analytics_schemas(con)
    cur = con.cursor()
    cur.execute(
        "DELETE FROM ogrenci_perf_gunluk WHERE date(gun) BETWEEN date(?) AND date(?)",
        (start.isoformat(), end.isoformat())
    )

    # GÜNCELLENEN: geciken = bitis tarihi geçmiş ve hâlâ eksik (s_devam>0)
    norm_sql = """
    WITH satir AS (
      SELECT s.ogrenci_id AS ogrenci_id, s.kume_id AS kume_id,
             DATE(COALESCE(s.tarih, k.bitis_tarihi)) AS gun,
             LOWER(COALESCE(s.durum,'devam')) AS durum,
             k.bitis_tarihi AS bitis
        FROM odev_satir s LEFT JOIN odev_kume k ON k.id=s.kume_id
      UNION ALL
      SELECT o.ogrenci_id, o.kume_id,
             DATE(k.bitis_tarihi) AS gun,
             LOWER(COALESCE(o.durum,'devam')) AS durum,
             k.bitis_tarihi AS bitis
        FROM odev o LEFT JOIN odev_kume k ON k.id=o.kume_id
    ),
    filt AS (
      SELECT * FROM satir WHERE gun IS NOT NULL
        AND date(gun) BETWEEN date(?) AND date(?)
    ),
    kume_gun AS (
      SELECT ogrenci_id, gun, kume_id,
             SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','ok','done','bitti','tamamlandi','tamamlandı') THEN 1 ELSE 0 END) AS s_tamam,
             SUM(CASE WHEN durum IN ('devam','kaldı','todo','acik','açik','açık','eksik','yarim','yarım') THEN 1 ELSE 0 END) AS s_devam,
             MIN(bitis) AS bitis
        FROM filt
       GROUP BY ogrenci_id, gun, kume_id
    ),
    sinif AS (
      SELECT ogrenci_id, gun,
        SUM(CASE WHEN s_tamam>0 AND s_devam=0 THEN 1 ELSE 0 END) AS tamam,
        SUM(CASE WHEN s_tamam>0 AND s_devam>0 THEN 1 ELSE 0 END) AS kismi,
        SUM(CASE WHEN s_tamam=0 AND s_devam>0 THEN 1 ELSE 0 END) AS yapilmadi,
        /* GÜNCEL: bitis < now VE s_devam>0 ise geciken */
        SUM(CASE WHEN s_devam>0 AND bitis IS NOT NULL AND date(bitis)<date('now') THEN 1 ELSE 0 END) AS geciken
      FROM kume_gun
      GROUP BY ogrenci_id, gun
    )
    SELECT * FROM sinif
    """

    rows = cur.execute(norm_sql, (start.isoformat(), end.isoformat())).fetchall()

    cur.executemany(
        """
        INSERT OR IGNORE INTO ogrenci_perf_gunluk
            (ogrenci_id, gun, tamam, kismi, yapilmadi, geciken)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["ogrenci_id"],
                r["gun"],
                r["tamam"],
                r["kismi"],
                r["yapilmadi"],
                r["geciken"],
            )
            for r in rows
        ],
    )
    con.commit()


def rebuild_weekly_by_ders(con: sqlite3.Connection, week_start: date, week_end: date) -> None:
    """
    Haftalık ders kırılımı -> ogrenci_perf_hafta_ders (öğrenci, ders bazında toplam/bitti/yüzde).
    """
    ensure_analytics_schemas(con)
    cur = con.cursor()
    cur.execute("""DELETE FROM ogrenci_perf_hafta_ders
                   WHERE week_start=? AND week_end=?""",
                (week_start.isoformat(), week_end.isoformat()))
    q = """
    WITH src AS (
      SELECT o.ogrenci_id AS ogrenci_id, o.ders AS ders, o.kume_id AS kume_id,
             LOWER(COALESCE(o.durum,'devam')) AS durum
        FROM odev o JOIN odev_kume k ON k.id=o.kume_id
       WHERE date(k.bitis_tarihi) BETWEEN date(?) AND date(?)
      UNION ALL
      SELECT s.ogrenci_id, s.ders, s.kume_id,
             LOWER(COALESCE(s.durum,'devam')) AS durum
        FROM odev_satir s JOIN odev_kume k ON k.id=s.kume_id
       WHERE date(k.bitis_tarihi) BETWEEN date(?) AND date(?)
    )
    SELECT ogrenci_id, COALESCE(ders,'(belirsiz)') AS ders,
           COUNT(*) AS toplam,
           SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','ok','done','bitti') THEN 1 ELSE 0 END) AS bitti
      FROM src
     GROUP BY ogrenci_id, COALESCE(ders,'(belirsiz)')
    """
    rows = cur.execute(q, (week_start.isoformat(), week_end.isoformat(),
                           week_start.isoformat(), week_end.isoformat())).fetchall()
    for r in rows:
        toplam = int(r["toplam"] or 0)
        bitti  = int(r["bitti"]  or 0)
        yuzde  = (bitti*100//toplam) if toplam>0 else 0
        cur.execute("""INSERT INTO ogrenci_perf_hafta_ders
                       (ogrenci_id,week_start,week_end,ders,toplam,bitti,yuzde)
                       VALUES(?,?,?,?,?,?,?)""",
                    (r["ogrenci_id"], week_start.isoformat(), week_end.isoformat(),
                     r["ders"], toplam, bitti, yuzde))
    con.commit()


def rebuild_book_progress(con: sqlite3.Connection) -> None:
    """
    Öğrenci–ders–kitap ilerleme yüzdesi -> ogrenci_kitap_ilerleme.
    """
    ensure_analytics_schemas(con)
    cur = con.cursor()
    cur.execute("DELETE FROM ogrenci_kitap_ilerleme")

    q = """
    WITH satir AS (
      SELECT ogrenci_id, ders, kitap AS kitap, konu,
             LOWER(COALESCE(durum,'devam')) AS durum,
             COALESCE(durum_ts, NULL) AS durum_ts
        FROM odev_satir
      UNION ALL
      SELECT ogrenci_id, ders, kitap_ad AS kitap, konu_ad AS konu,
             LOWER(COALESCE(durum,'devam')) AS durum,
             NULL AS durum_ts
        FROM odev
    ),
    agg AS (
      SELECT ogrenci_id, COALESCE(ders,'(belirsiz)') AS ders, COALESCE(kitap,'(belirsiz)') AS kitap,
             COUNT(*) AS konu_say,
             SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','ok','done','bitti') THEN 1 ELSE 0 END) AS bitti_say,
             MAX(durum_ts) AS last_done_ts
        FROM satir
       GROUP BY ogrenci_id, COALESCE(ders,'(belirsiz)'), COALESCE(kitap,'(belirsiz)')
    )
    SELECT * FROM agg
    """
    rows = cur.execute(q).fetchall()
    cur.executemany("""INSERT INTO ogrenci_kitap_ilerleme
                       (ogrenci_id, ders, kitap, konu_say, bitti_say, yuzde, last_done_ts)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [(r["ogrenci_id"], r["ders"], r["kitap"], r["konu_say"], r["bitti_say"],
                      (int(r["bitti_say"]*100//r["konu_say"]) if int(r["konu_say"] or 0)>0 else 0),
                      r["last_done_ts"]) for r in rows])
    con.commit()


def rebuild_cohort_book_cov(con: sqlite3.Connection) -> None:
    """
    Her ders–kitap–konu için kaç öğrenci bitirmiş (cohort yüzdesi) -> cohort_kitap_kapsam.
    """
    ensure_analytics_schemas(con)
    cur = con.cursor()
    cur.execute("DELETE FROM cohort_kitap_kapsam")
    q = """
    WITH satir AS (
      SELECT ogrenci_id, ders, kitap, konu,
             LOWER(COALESCE(durum,'devam')) AS durum
        FROM odev_satir
      UNION ALL
      SELECT ogrenci_id, ders, kitap_ad AS kitap, konu_ad AS konu,
             LOWER(COALESCE(durum,'devam')) AS durum
        FROM odev
    ),
    done AS (
      SELECT DISTINCT ogrenci_id, ders, kitap, konu
        FROM satir
       WHERE durum IN ('tamam','yapildi','yapıldı','ok','done','bitti')
    ),
    counts AS (
      SELECT ders, kitap, konu,
             COUNT(*) AS done_count,
             (SELECT COUNT(DISTINCT ogrenci_id) FROM satir) AS student_count
        FROM done
       GROUP BY ders, kitap, konu
    )
    SELECT ders, kitap, konu, done_count, student_count,
           CASE WHEN student_count>0 THEN CAST(done_count*100/student_count AS INT) ELSE 0 END AS pct
      FROM counts
    """
    rows = cur.execute(q).fetchall()
    cur.executemany("""INSERT INTO cohort_kitap_kapsam(ders,kitap,konu,done_count,student_count,pct)
                       VALUES (?,?,?,?,?,?)""",
                    [(r["ders"], r["kitap"], r["konu"], r["done_count"], r["student_count"], r["pct"]) for r in rows])
    con.commit()


def rebuild_all(con: sqlite3.Connection, ref: Optional[date] = None) -> None:
    """
    Tek tuş “yenile”: günlük özet, haftalık ders kırılımı, kitap ilerleme, cohort kapsam.
    main_window.run_full_refresh() burayı çağırır.
    Ayarlara göre:
    - gunluk_son_gun : günlük özet için kaç güne bakılacağı
    """
    ensure_analytics_schemas(con)
    today = ref or date.today()

    settings = _get_report_settings(con)
    try:
        days = int(settings.get("gunluk_son_gun", "30"))
    except Exception:
        days = 30
    if days < 1:
        days = 1
    if days > 120:
        days = 120

    s_daily, e_daily = _lastN_bounds(today, days)
    rebuild_daily(con, s_daily, e_daily)

    ws, we = _week_bounds(today)
    rebuild_weekly_by_ders(con, ws, we)

    rebuild_book_progress(con)
    rebuild_cohort_book_cov(con)


# ------------------ Basit öneri motoru (kural tabanlı) ------------------

def recommend_next(con: sqlite3.Connection, ogrenci_id: int, limit: int = 6) -> List[Dict[str, Any]]:
    """
    Zayıf ders/kitap/konu + cohort'ta geride olunanlardan kısa bir öneri listesi döndürür.
    Dönüş elemanı örneği:
      {'tip':'konu'|'kitap'|'ders', 'ders':..., 'kitap':..., 'konu':..., 'gerekce':...}
    """
    ensure_analytics_schemas(con)
    cur = con.cursor()
    out: List[Dict[str, Any]] = []

    # 1) Zayıf ders: Son hafta düşük yüzde
    ws, we = _week_bounds(date.today())
    r = cur.execute("""
        SELECT ders, yuzde FROM ogrenci_perf_hafta_ders
         WHERE ogrenci_id=? AND week_start=? AND week_end=?
         ORDER BY yuzde ASC LIMIT 2
    """, (ogrenci_id, ws.isoformat(), we.isoformat())).fetchall()
    for row in r:
        out.append({"tip": "ders", "ders": row["ders"], "gerekce": f"Bu hafta {row['ders']} düşük performans."})

    # 2) Kitap ilerleme: düşük yüzde
    r = cur.execute("""
        SELECT ders, kitap, yuzde FROM ogrenci_kitap_ilerleme
         WHERE ogrenci_id=? ORDER BY yuzde ASC LIMIT 2
    """, (ogrenci_id,)).fetchall()
    for row in r:
        out.append({"tip": "kitap", "ders": row["ders"], "kitap": row["kitap"],
                    "gerekce": f"{row['kitap']} kitabında ilerleme düşük (%{row['yuzde']})."})

    # 3) Cohort'a göre geride olunan konu
    r = cur.execute("""
        SELECT c.ders, c.kitap, c.konu, c.pct
          FROM cohort_kitap_kapsam c
         WHERE c.pct >= 50
           AND NOT EXISTS (
              SELECT 1 FROM odev_satir s
               WHERE s.ogrenci_id=? AND s.ders=c.ders AND s.kitap=c.kitap AND s.konu=c.konu
                 AND LOWER(COALESCE(s.durum,'devam')) IN ('tamam','yapildi','yapıldı','ok','done','bitti')
           )
         ORDER BY c.pct DESC LIMIT 2
    """, (ogrenci_id,)).fetchall()
    for row in r:
        out.append({"tip": "konu", "ders": row["ders"], "kitap": row["kitap"], "konu": row["konu"],
                    "gerekce": f"Cohort’un %{row['pct']}’i tamamlamış; geridesin."})

    return out[:limit]
