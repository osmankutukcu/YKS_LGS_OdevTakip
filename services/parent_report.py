# -*- coding: utf-8 -*-
"""
services/parent_report.py

Öğrenci veli PDF raporu üretimi.

Kullanılan veriler:
- ogrenci               : öğrenci adı / id
- odev + odev_satir     : Son N günde ders bazlı özet + günlük özet
- (odev + ders tabloları)   : kitap / konu ilerleme yüzdeleri

Not:
ogrenci_rapor.py içindeki _register_turkish_font fonksiyonu ile
AYNI fontlar kullanılır. Böylece Türkçe karakterler her iki PDF’te
de aynı şekilde (düzgün) çıkar.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta, datetime

from typing import Dict, Any, List, Tuple, Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ============================================================
#  FONT AYARLARI  (ogrenci_rapor.py ile UYUMLU)
# ============================================================

_MAIN_FONT_NAME: Optional[str] = None
_BOLD_FONT_NAME: Optional[str] = None


def _register_turkish_fonts() -> Tuple[str, str]:
    """
    Fontları ayarlar ve (normal_font_adı, bold_font_adı) döndürür.

    Önce ogrenci_rapor._register_turkish_font() fonksiyonunu kullanır.
    Eğer herhangi bir nedenle import edemezse, basit bir DejaVuSans /
    Helvetica fallback’ine düşer.
    """
    global _MAIN_FONT_NAME, _BOLD_FONT_NAME
    if _MAIN_FONT_NAME and _BOLD_FONT_NAME:
        return _MAIN_FONT_NAME, _BOLD_FONT_NAME

    # 1) ogrenci_rapor’dan aynen almayı dene
    try:
        import ogrenci_rapor as orap

        # ogrenci_rapor içindeki yardımcı fonksiyon:
        # def _register_turkish_font():
        #     return (FONT_REG, FONT_BOLD, mpl_font_family)
        reg_name, bold_name, _ = orap._register_turkish_font()

        _MAIN_FONT_NAME = reg_name
        _BOLD_FONT_NAME = bold_name
        return _MAIN_FONT_NAME, _BOLD_FONT_NAME
    except Exception:
        # Devam edip kendi fallback’imize düşeceğiz
        pass

    # 2) Proje /fonts klasöründe DejaVuSans varsa onu kullan
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fonts_dir = os.path.join(base_dir, "fonts")
    regular_path = os.path.join(fonts_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(fonts_dir, "DejaVuSans-Bold.ttf")

    if os.path.exists(regular_path) and os.path.exists(bold_path):
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", regular_path))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))
            _MAIN_FONT_NAME = "DejaVuSans"
            _BOLD_FONT_NAME = "DejaVuSans-Bold"
            return _MAIN_FONT_NAME, _BOLD_FONT_NAME
        except Exception:
            pass

    # 3) En son çare: Helvetica
    _MAIN_FONT_NAME = "Helvetica"
    _BOLD_FONT_NAME = "Helvetica-Bold"
    return _MAIN_FONT_NAME, _BOLD_FONT_NAME


def _safe_text(txt: str) -> str:
    """
    Metni doğrudan döndürür.
    DejaVuSans fontu varsa zaten tüm Türkçe karakterler sorunsuz çıkar.
    Yoksa bile en azından '?' yerine gerçek Unicode karakterleri yazdırır.
    """
    if txt is None:
        return ""
    try:
        return str(txt)
    except Exception:
        return ""


# ============================================================
#  KİTAP / KONU İLERLEME HESABI
# ============================================================

def calc_kitap_progress_rows(
    con: sqlite3.Connection,
    ogrenci_id: int
) -> List[Tuple[str, str, int, int, int]]:
    """
    (ders, kitap) bazında ilerlemeyi hesaplar.

    Dönüş: liste[(ders, kitap, perc, done, total)]
        - perc  = round(100 * done / total)
        - done  = bu (ders, kitap) için 'yapıldı' işaretlenmiş BENZERSİZ konu_ad sayısı
        - total = ilgili *ders* tablosundaki toplam konu sayısı (satır sayısı)
    """
    cur = con.cursor()

    # (ders, kitap) çiftlerini hem odev’den hem ogrenci_kitap’tan topla
    pairs = set()
    for r in cur.execute("""
        SELECT DISTINCT ders, COALESCE(kitap_ad,'') AS kitap
        FROM odev
        WHERE ogrenci_id=? AND COALESCE(kitap_ad,'')<>''
    """, (ogrenci_id,)):
        pairs.add((r["ders"], r["kitap"]))

    for r in cur.execute("""
        SELECT DISTINCT ders, COALESCE(kitap_ad,'') AS kitap
        FROM ogrenci_kitap
        WHERE ogrenci_id=? AND COALESCE(kitap_ad,'')<>''
    """, (ogrenci_id,)):
        pairs.add((r["ders"], r["kitap"]))

    if not pairs:
        return []

    def _is_done(val: Optional[str]) -> bool:
        s = (val or "").strip().lower()
        return s in {
            "yapildi", "tamam", "bitti", "done", "tamamlandı",
            "✓", "1", "true", "evet", "ok"
        }

    rows: List[Tuple[str, str, int, int, int]] = []

    for ders, kitap in sorted(pairs):
        # 1) TOPLAM konu sayısı: ilgili ders tablosundaki satır sayısı
        try:
            total = (
                con.execute(f"SELECT COUNT(*) AS c FROM {ders}")
                .fetchone()["c"] or 0
            )
        except sqlite3.Error:
            total = 0  # tablo adı uyuşmuyorsa güvenli çık

        # 2) DONE: bu (ders, kitap) için 'yapıldı' işaretlenmiş BENZERSİZ konu_ad sayısı
        done_set = set()
        for r in con.execute("""
            SELECT DISTINCT konu_ad, durum
            FROM odev
            WHERE ogrenci_id=? AND ders=? AND kitap_ad=?
        """, (ogrenci_id, ders, kitap)):
            if _is_done(r["durum"]):
                k = (r["konu_ad"] or "").strip()
                if k:
                    done_set.add(k)
        done = len(done_set)

        # 3) % hesapla
        perc = int(round((done / total) * 100)) if total else 0
        rows.append((ders, kitap, perc, done, total))

    return rows


# ============================================================
#  DB YARDIMCILARI
# ============================================================

def _get_student(con: sqlite3.Connection, ogrenci_id: int) -> Optional[Dict[str, Any]]:
    cur = con.execute(
        "SELECT id, ad, soyad FROM ogrenci WHERE id = ?",
        (ogrenci_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    adsoy = (row["ad"] or "").strip() + " " + (row["soyad"] or "").strip()
    return {
        "id": row["id"],
        "ad": row["ad"] or "",
        "soyad": row["soyad"] or "",
        "adsoyad": adsoy.strip() or f"Öğrenci #{row['id']}"
    }


# ============================================================
#  SON N GÜNDE DERS BAZLI ÖZET
# ============================================================

def _get_period_summary(
    con: sqlite3.Connection,
    ogrenci_id: int,
    days_window: int
) -> List[Dict[str, Any]]:
    """
    Son N günde (bitis_tarihi penceresi) ders bazlı özet.

    - Kaynak: odev + odev_satir + odev_kume
    - Her satır bir “görev” kabul edilir.
    - toplam: o dersteki görev sayısı
    - bitti : o derste tamamlanmış görev sayısı
    - yuzde: 100 * bitti / toplam
    """
    if days_window <= 0:
        days_window = 7

    today = date.today()
    start = today - timedelta(days=days_window - 1)

    start_s = start.isoformat()
    end_s = today.isoformat()

    def is_done(durum: Optional[str], tamam_tarih: Optional[str]) -> bool:
        if tamam_tarih:
            return True
        s = (durum or "").strip().lower()
        if not s:
            return False
        keywords = {
            "tamam", "bitti", "yapildi", "yapıldı",
            "done", "ok", "✓", "✔", "1", "true", "evet"
        }
        return any(k in s for k in keywords)

    sql = """
        SELECT o.ders AS ders,
               o.durum AS durum,
               o.tamamlanma_tarihi AS tamam_tarih,
               DATE(k.bitis_tarihi) AS gun
          FROM odev o
          JOIN odev_kume k ON k.id = o.kume_id
         WHERE o.ogrenci_id = ?
           AND k.bitis_tarihi IS NOT NULL
           AND DATE(k.bitis_tarihi) BETWEEN ? AND ?
           AND (o.silindi IS NULL OR o.silindi = 0)

        UNION ALL

        SELECT s.ders AS ders,
               s.durum AS durum,
               s.tamamlanma_tarihi AS tamam_tarih,
               DATE(k.bitis_tarihi) AS gun
          FROM odev_satir s
          JOIN odev_kume k ON k.id = s.kume_id
         WHERE s.ogrenci_id = ?
           AND k.bitis_tarihi IS NOT NULL
           AND DATE(k.bitis_tarihi) BETWEEN ? AND ?
           AND (s.silindi IS NULL OR s.silindi = 0)
    """

    cur = con.execute(sql, (ogrenci_id, start_s, end_s,
                            ogrenci_id, start_s, end_s))

    ders_map: Dict[str, Dict[str, int]] = {}

    for ders, durum, tamam_tarih, gun_str in cur.fetchall():
        if not ders or not gun_str:
            continue

        d = ders_map.setdefault(ders, {"toplam": 0, "bitti": 0})
        d["toplam"] += 1
        if is_done(durum, tamam_tarih):
            d["bitti"] += 1

    out: List[Dict[str, Any]] = []
    for ders, data in sorted(ders_map.items()):
        toplam = data["toplam"]
        bitti = data["bitti"]
        yuzde = (100.0 * bitti / toplam) if toplam else 0.0
        out.append({
            "ders": ders,
            "toplam": toplam,
            "bitti": bitti,
            "yuzde": yuzde,
        })

    return out


# ============================================================
#  GÜNLÜK ÖZET (SON N GÜN)
# ============================================================

def _get_recent_daily(con: sqlite3.Connection,
                      ogrenci_id: int,
                      max_days: int = 6) -> List[Dict[str, Any]]:
    """
    Son Günlerde Görev Durumu (ÖDEV BAZLI)

    - odev + odev_satir tablosundaki TÜM satırları sayar.
    - Her satır bir “görev” kabul edilir.
    - Gruplama: satırın bağlı olduğu kümenin bitiş tarihi (odev_kume.bitis_tarihi)
    - Durum sınıfları:
        * tamam  -> durum 'tamam' / 'bitti' / 'yapildi' vb. VEYA tamamlanma_tarihi doluysa
        * kısmi  -> durum metninde 'kism' / 'kısmi' geçiyorsa
        * yapılmadı -> bitiş tarihi bugün veya SONRASI ve tamamlanmamışsa
        * geciken   -> bitiş tarihi bugün ÖNCESİ ve tamamlanmamışsa
    - En SON max_days farklı gün rapora yazılır.
    """
    today = date.today()

    def is_done(durum: str | None, tamam_tarih: str | None) -> bool:
        # tamamlanma tarihi doluysa direkt "tamam"
        if tamam_tarih:
            return True
        s = (durum or "").strip().lower()
        if not s:
            return False
        # Sende kullandığımız done seti ile uyumlu
        keywords = {
            "tamam", "bitti", "yapildi", "yapıldı",
            "done", "ok", "✓", "✔", "1", "true", "evet"
        }
        return any(k in s for k in keywords)

    def is_partial(durum: str | None) -> bool:
        s = (durum or "").lower()
        return ("kism" in s) or ("kısmi" in s)

    # Hem odev hem odev_satir satırlarını getir
    sql = """
        SELECT DATE(k.bitis_tarihi) AS gun,
               o.durum              AS durum,
               o.tamamlanma_tarihi  AS tamam_tarih
          FROM odev o
          JOIN odev_kume k ON k.id = o.kume_id
         WHERE o.ogrenci_id = ?
           AND k.bitis_tarihi IS NOT NULL
           AND (o.silindi IS NULL OR o.silindi = 0)

        UNION ALL

        SELECT DATE(k.bitis_tarihi) AS gun,
               s.durum              AS durum,
               s.tamamlanma_tarihi  AS tamam_tarih
          FROM odev_satir s
          JOIN odev_kume k ON k.id = s.kume_id
         WHERE s.ogrenci_id = ?
           AND k.bitis_tarihi IS NOT NULL
           AND (s.silindi IS NULL OR s.silindi = 0)
    """

    cur = con.execute(sql, (ogrenci_id, ogrenci_id))

    gunluk: dict[str, Dict[str, int]] = {}

    for gun_str, durum, tamam_tarih in cur.fetchall():
        if not gun_str:
            continue

        gun_dt = date.fromisoformat(gun_str)

        if gun_str not in gunluk:
            gunluk[gun_str] = {"tamam": 0, "kismi": 0, "yapilmadi": 0, "geciken": 0}

        rec = gunluk[gun_str]

        # 1) TAMAM
        if is_done(durum, tamam_tarih):
            rec["tamam"] += 1
            continue

        # 2) KISMİ
        if is_partial(durum):
            rec["kismi"] += 1
            continue

        # 3) Tamamlanmamış satırlar
        if gun_dt < today:
            rec["geciken"] += 1
        else:
            rec["yapilmadi"] += 1

    if not gunluk:
        return []

    # Tüm günleri sırala, EN SON max_days günü al
    all_days = sorted(gunluk.keys())      # örn: 2025-11-05, 2025-11-11, ...
    selected = all_days[-max_days:]       # son max_days gün

    result: List[Dict[str, Any]] = []
    for gun_str in selected:
        rec = gunluk[gun_str]
        result.append({
            "gun": gun_str,
            "tamam": rec["tamam"],
            "kismi": rec["kismi"],
            "yapilmadi": rec["yapilmadi"],
            "geciken": rec["geciken"],
        })

    return result


def _get_book_progress(con: sqlite3.Connection, ogrenci_id: int) -> List[Dict[str, Any]]:
    """
    Kitap ilerlemelerini, ders tablosundaki TOPLAM konu sayısına göre hesaplar.

    Dönüş: liste[{
        ders: str,
        kitap: str,
        konu_say: int,   # total
        bitti_say: int,  # done
        yuzde: int
    }]
    """
    rows_calc = calc_kitap_progress_rows(con, ogrenci_id)
    out: List[Dict[str, Any]] = []
    for ders, kitap, perc, done, total in rows_calc:
        out.append({
            "ders": ders or "(belirsiz)",
            "kitap": kitap or "(belirsiz)",
            "konu_say": int(total or 0),
            "bitti_say": int(done or 0),
            "yuzde": int(perc or 0),
        })
    return out


# ============================================================
#  PDF ÇİZİM YARDIMCILARI
# ============================================================

def _draw_title(c: canvas.Canvas, student: Dict[str, Any]) -> float:
    """
    Başlık ve öğrenci bilgilerini çizer, yeni y pozisyonunu döndürür.
    """
    main_font, bold_font = _register_turkish_fonts()
    width, height = A4
    margin = 40

    c.setFont(bold_font, 16)
    c.drawString(margin, height - margin, _safe_text("ÖĞRENCİ ÖZET RAPORU"))

    c.setFont(main_font, 10)
    today_str = date.today().strftime("%d.%m.%Y")
    c.drawRightString(width - margin, height - margin + 2, today_str)

    y = height - margin - 30

    c.setFont(bold_font, 11)
    c.drawString(margin, y, _safe_text(student["adsoyad"]))
    y -= 14

    c.setFont(main_font, 10)
    c.drawString(margin, y, _safe_text(f"Öğrenci ID: {student['id']}"))
    y -= 20

    return y


def _draw_period_summary(
    c: canvas.Canvas,
    y: float,
    summary: List[Dict[str, Any]],
    n_days: int
) -> float:
    """
    Son N günde ders bazlı özet kısmını çizer.
    Solda metin, sağda yatay yüzde barı.
    """
    main_font, bold_font = _register_turkish_fonts()
    page_w, _ = A4
    margin = 40

    c.setFont(bold_font, 11)
    c.drawString(margin, y, _safe_text(f"Son {n_days} Günde Ders Bazlı Özet"))
    y -= 14
    c.setFont(main_font, 9)

    if not summary:
        c.drawString(margin, y, _safe_text("Bu aralık için kayıtlı görev bulunamadı."))
        y -= 16
        return y

    text_x = margin
    bar_w = 140
    bar_x = page_w - margin - bar_w
    bar_h = 6
    max_text_width = bar_x - text_x - 10

    for idx, row in enumerate(summary):
        if y < 130:
            break

        ders = row["ders"]
        toplam = row["toplam"]
        bitti = row["bitti"]
        yuzde = row["yuzde"]

        # Zebra arka plan (okunabilirlik için)
        if idx % 2 == 1:
            c.setFillColor(colors.whitesmoke)
            c.rect(margin - 5, y - 2, page_w - 2 * margin + 10, 11, fill=1, stroke=0)
            c.setFillColor(colors.black)

        # Etiket
        label = ders
        while pdfmetrics.stringWidth(label, main_font, 9) > max_text_width and len(label) > 4:
            label = label[:-4] + "..."

        line = f"- {label}: {bitti}/{toplam} görev (%{yuzde:.1f})"
        c.drawString(text_x, y, _safe_text(line))

        # Bar
        pct_clamped = max(0.0, min(100.0, float(yuzde)))
        fill_w = bar_w * pct_clamped / 100.0

        c.setStrokeColor(colors.lightgrey)
        c.rect(bar_x, y - bar_h + 2, bar_w, bar_h, stroke=1, fill=0)

        c.setFillColor(colors.HexColor("#3366cc"))
        c.rect(bar_x, y - bar_h + 2, fill_w, bar_h, stroke=0, fill=1)
        c.setFillColor(colors.black)

        y -= 12

    y -= 6
    return y


def _draw_daily_table(
    c: canvas.Canvas,
    y: float,
    daily: List[Dict[str, Any]],
    n_days: int
) -> float:
    """
    Günlük tablo + sağda çok renkli bar grafikleri.
    """
    main_font, bold_font = _register_turkish_fonts()
    page_w, _ = A4
    margin = 40

    c.setFont(bold_font, 11)
    c.drawString(margin, y, _safe_text(f"Son {n_days} Günde Görev Durumu"))
    y -= 14
    c.setFont(main_font, 9)

    if not daily:
        c.drawString(margin, y, _safe_text("Bu öğrenci için günlük özet bulunamadı."))
        y -= 16
        return y

    # --- Legend (renk açıklaması) ---
    legend_x = margin
    legend_y = y

    def _legend_box(x, label, color_obj):
        nonlocal legend_y
        c.setFillColor(color_obj)
        c.rect(x, legend_y - 6, 8, 6, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawString(x + 12, legend_y - 6, _safe_text(label))

    _legend_box(legend_x, "Tamam", colors.HexColor("#2e7d32"))      # yeşil
    _legend_box(legend_x + 80, "Kısmi", colors.HexColor("#ff9800"))  # turuncu
    _legend_box(legend_x + 150, "Yapılmadı", colors.HexColor("#90a4ae"))  # gri
    _legend_box(legend_x + 240, "Geciken", colors.HexColor("#d32f2f"))    # kırmızı

    y = legend_y - 14

    # Tablo başlığı
    c.setFont(bold_font, 9)
    c.drawString(margin, y, _safe_text("Tarih"))
    c.drawString(margin + 80, y, _safe_text("Tamam"))
    c.drawString(margin + 130, y, _safe_text("Kısmi"))
    c.drawString(margin + 180, y, _safe_text("Yapılmadı"))
    c.drawString(margin + 250, y, _safe_text("Geciken"))
    y -= 10
    c.setFont(main_font, 9)

    bar_w = 180
    bar_x = page_w - margin - bar_w
    bar_h = 6

    for idx, row in enumerate(daily):
        if y < 120:
            break

        # Zebra arka plan
        if idx % 2 == 1:
            c.setFillColor(colors.whitesmoke)
            c.rect(margin - 5, y - 2, page_w - 2 * margin + 10, 11, fill=1, stroke=0)
            c.setFillColor(colors.black)

        done = int(row["tamam"])
        partial = int(row["kismi"])
        pending = int(row["yapilmadi"])
        late = int(row["geciken"])
        total = max(1, done + partial + pending + late)

        # Metinsel kısım
        c.drawString(margin, y, _safe_text(row["gun"]))
        c.drawString(margin + 80, y, _safe_text(str(done)))
        c.drawString(margin + 130, y, _safe_text(str(partial)))
        c.drawString(margin + 180, y, _safe_text(str(pending)))
        c.drawString(margin + 250, y, _safe_text(str(late)))

        # Barın çerçevesi
        c.setStrokeColor(colors.lightgrey)
        c.rect(bar_x, y - bar_h + 2, bar_w, bar_h, stroke=1, fill=0)

        # Segmentler
        x_pos = bar_x

        def _seg(width, color_obj):
            nonlocal x_pos
            if width <= 0:
                return
            c.setFillColor(color_obj)
            c.rect(x_pos, y - bar_h + 2, width, bar_h, stroke=0, fill=1)
            x_pos += width

        _seg(bar_w * done / total, colors.HexColor("#2e7d32"))      # tamam
        _seg(bar_w * partial / total, colors.HexColor("#ff9800"))   # kısmi
        _seg(bar_w * pending / total, colors.HexColor("#90a4ae"))   # yapılmadı
        _seg(bar_w * late / total, colors.HexColor("#d32f2f"))      # geciken

        c.setFillColor(colors.black)
        y -= 12

    y -= 6
    return y


def _draw_book_progress(c: canvas.Canvas, y: float,
                        books: List[Dict[str, Any]]) -> float:
    """
    Solda metin, sağda yatay bar ile kitap ilerlemeleri.
    Uzun kitap isimleri barların üstüne binmesin diye:
    - metin alanını geniş tuttuk
    - çok uzun "ders/kitap" etiketlerini gerektiğinde '...' ile kısaltıyoruz.
    """
    main_font, bold_font = _register_turkish_fonts()
    page_w, _ = A4
    margin = 40

    c.setFont(bold_font, 11)
    c.drawString(margin, y, _safe_text("Kitap İlerleme Durumu"))
    y -= 16

    if not books:
        c.setFont(main_font, 9)
        c.drawString(margin, y, _safe_text("Henüz kitap ilerleme kaydı yok."))
        y -= 16
        return y

    c.setFont(main_font, 9)

    # Metin ve bar için alanlar
    text_x = margin
    bar_w = 170
    bar_x = page_w - margin - bar_w        # barı sağ tarafa sabitle
    max_text_width = bar_x - text_x - 10   # metin bu genişliği aşmasın
    bar_h = 6

    for idx, row in enumerate(books):
        if y < 80:  # sayfanın altına çok yaklaşırsa kırpmamak için
            break

        # Zebra arka plan
        if idx % 2 == 1:
            c.setFillColor(colors.whitesmoke)
            c.rect(margin - 5, y - 2, page_w - 2 * margin + 10, 11, fill=1, stroke=0)
            c.setFillColor(colors.black)

        ders = row["ders"]
        kitap = row["kitap"]
        konu_say = row["konu_say"]
        bitti_say = row["bitti_say"]
        yuzde = row["yuzde"]

        # 1) Etiketi oluşturalım: "ders / kitap"
        label = f"{ders} / {kitap}"

        # 2) Gerekirse kısalt: max_text_width'i aşarsa '...' ile kırp
        while pdfmetrics.stringWidth(label, main_font, 9) > max_text_width and len(label) > 4:
            label = label[:-4] + "..."

        # 3) Metin satırı: " - ders / kitap: 5/40 konu (%12)"
        line = f"- {label}: {bitti_say}/{konu_say} konu (%{yuzde})"
        c.drawString(text_x, y, _safe_text(line))

        # 4) Bar'ı çiz
        pct_clamped = max(0, min(100, yuzde))
        fill_w = bar_w * pct_clamped / 100.0

        c.setStrokeColor(colors.lightgrey)
        c.rect(bar_x, y - bar_h + 2, bar_w, bar_h, stroke=1, fill=0)

        c.setFillColor(colors.HexColor("#3366cc"))
        c.rect(bar_x, y - bar_h + 2, fill_w, bar_h, stroke=0, fill=1)
        c.setFillColor(colors.black)

        y -= 12

    y -= 6
    return y


def _draw_teacher_note(c: canvas.Canvas, y: float) -> None:
    main_font, bold_font = _register_turkish_fonts()
    margin = 40

    c.setFont(bold_font, 11)
    c.drawString(margin, y, _safe_text("Öğretmen Notu"))
    y -= 12
    c.setFont(main_font, 8)
    c.drawString(
        margin,
        y,
        _safe_text("(Bu alan çıktıyı aldıktan sonra öğretmen tarafından el yazısıyla doldurulabilir.)"),
    )
    y -= 10

    # 5 satır çizgisi
    for _ in range(5):
        c.line(margin, y, A4[0] - margin, y)
        y -= 12
#s
def _build_output_path(base_output_path: str, student: Dict[str, Any], ts: str) -> str:
    """
    base_output_path:
        - Klasör olabilir (örn: 'raporlar')
        - Tam dosya yolu olabilir (örn: 'raporlar/veli_rapor.pdf')
    Her iki durumda da:
        ID - Ad_Soyad - YYYYMMDD_HHMM.pdf
    adında bir dosya üretir.
    """
    # 1) Klasör kısmını bul
    folder = base_output_path
    if not os.path.isdir(folder):
        folder, _ = os.path.split(base_output_path)

    if not folder:
        folder = os.getcwd()

    # 2) Öğrenci ad-soyadı (boşluklar alt çizgi)
    safe_name = (student["adsoyad"] or "").replace(" ", "_")

    # 3) Nihai dosya adı
    filename = f"{student['id']} - {safe_name} - {ts}.pdf"
    return os.path.join(folder, filename)
#f



# ============================================================
#  ANA FONKSİYON
# ============================================================

def generate_parent_report(
    con: sqlite3.Connection,
    ogrenci_id: int,
    output_path: str,
    settings: Dict[str, Any]
) -> None:
    """
    Tek bir öğrenci için veli PDF raporu üretir.
    Hata olursa exception fırlatır (çağıran yer try/except ile yakalıyor).
    """
    student = _get_student(con, ogrenci_id)
    if not student:
        raise ValueError(f"Öğrenci bulunamadı (id={ogrenci_id})")

    # Ayarlardaki günlük özet aralığı (örn. 30 gün)
    try:
        window_days = int(settings.get("daily_days") or 30)
    except (TypeError, ValueError):
        window_days = 30
    if window_days <= 0:
        window_days = 30

    # Önce verileri çek
    period_summary = _get_period_summary(con, ogrenci_id, window_days)
    daily = _get_recent_daily(con, ogrenci_id, max_days=window_days)
    books = _get_book_progress(con, ogrenci_id)

    # Zaman damgası (YYYYMMDD_HHMM)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    # Çağıran ne verirse versin, burada son dosya adını standartlaştırıyoruz
    final_output_path = _build_output_path(output_path, student, ts)

    # PDF oluştur
    _register_turkish_fonts()  # emin olalım
    c = canvas.Canvas(final_output_path, pagesize=A4)
    c.setTitle(_safe_text(f"{student['id']} - {student['adsoyad']} - {ts}"))

    y = _draw_title(c, student)

    y = _draw_period_summary(c, y, period_summary, window_days)
    y = _draw_daily_table(c, y, daily, window_days)
    y = _draw_book_progress(c, y, books)
    _draw_teacher_note(c, y - 10)

    c.showPage()
    c.save()
