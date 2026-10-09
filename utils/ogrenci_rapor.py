# -*- coding: utf-8 -*-
# utils/ogrenci_rapor.py

import os, io, datetime as dt
from collections import defaultdict, Counter

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, Flowable
)
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from typing import Optional

# ===================== Matplotlib (opsiyonel) =====================
try:
    import matplotlib
    matplotlib.use("Agg")  # GUI gerektirmez
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False
    plt = None

# ===================== Türkçe font kaydı =====================

def _register_turkish_font():
    """
    Kullanılabilir bir TTF bulup ReportLab'a kaydeder.
    (reg_name, bold_name, mpl_family_display) döndürür.
    """
    candidates = []
    try:
        import matplotlib as _mpl
        mp = _mpl.get_data_path()
        candidates.append((
            os.path.join(mp, "fonts", "ttf", "DejaVuSans.ttf"),
            os.path.join(mp, "fonts", "ttf", "DejaVuSans-Bold.ttf"),
            "DejaVuSans", "DejaVuSans-Bold", "DejaVu Sans"
        ))
    except Exception:
        pass

    candidates += [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "DejaVuSans", "DejaVuSans-Bold", "DejaVu Sans"),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "ArialUnicode", "ArialBold", "Arial Unicode MS"),
        ("/Library/Fonts/Arial Unicode.ttf",
         "/Library/Fonts/Arial Bold.ttf",
         "ArialUnicode", "ArialBold", "Arial Unicode MS"),
    ]

    for reg_path, bold_path, reg_name, bold_name, mpl_family in candidates:
        try:
            if os.path.exists(reg_path):
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                else:
                    bold_name = reg_name
                return reg_name, bold_name, mpl_family
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold", None

FONT_REG, FONT_BOLD, MPL_FAMILY = _register_turkish_font()

if _HAS_MPL and MPL_FAMILY:
    import matplotlib as _mpl
    _mpl.rcParams["font.family"] = [MPL_FAMILY]
    _mpl.rcParams["axes.unicode_minus"] = False

# ===================== DB =====================
import db

# ===================== Ortak stiller ve yardımcılar =====================
_styles = getSampleStyleSheet()
PAGE_W, PAGE_H = A4

def _cm(x):
    return x * cm

def _date(s):
    try:
        return dt.date.fromisoformat(s) if s else None
    except Exception:
        return None

def _rget(row, key, default=0):
    try:
        v = row[key]
        return default if v is None else v
    except Exception:
        return default

def _daterange(start, end):
    if not start or not end:
        return []
    cur = start
    out = []
    while cur <= end:
        out.append(cur)
        cur += dt.timedelta(days=1)
    return out

# wrap’li paragraflar
WRAP8 = ParagraphStyle("WRAP8", parent=_styles["BodyText"], fontName=FONT_REG,
                       fontSize=8, leading=9, wordWrap='CJK')
WRAP9B = ParagraphStyle("WRAP9B", parent=_styles["BodyText"], fontName=FONT_BOLD,
                        fontSize=9, leading=10, wordWrap='CJK')
TITLE = _styles["Title"]; TITLE.fontName = FONT_REG
H2 = _styles["Heading2"]; H2.fontName = FONT_REG
H3 = _styles["Heading3"]; H3.fontName = FONT_REG
BODY = _styles["BodyText"]; BODY.fontName = FONT_REG

DEFAULT_GENEL_METIN = (
    "<b>Genel Değerlendirme ve Tavsiyeler</b><br/><br/>"
    "• <b>Tamamlama oranı</b> düşükse: 1–2 haftalık kısa döngülerle net günlük hedefler belirleyin "
    "(örn. “1 konu + 20 dk tekrar”).<br/>"
    "• <b>Gecikmeler</b>: görevleri mikro parçalara bölün (Pomodoro 25/5 veya 40/10); yeni ödevlerde "
    "<i>48 saat içinde ilk temas</i> kuralını uygulayın.<br/>"
    "• <b>Trend & streak</b>: dalgalanmayı azaltmak için “günlük asgari plan” (en az 30 dk temel + 10 dk tekrar).<br/>"
    "• <b>Süre dağılımı</b>: zayıf derslere haftalık iki sabit slot ayırın; güçlü derslerde süre artışı yerine "
    "kalite (yanlış analizi, özet kart).<br/>"
    "• <b>Konu kapsamı</b>: “devam” statüsü uzuyorsa neden analiz edin: kavram eksiği → 10–15 soru + kısa not; "
    "uygulama eksiği → tek oturumda 20–30 soru; hız → zamana karşı mini deneme.<br/>"
    "• <b>Tamamlanabilirlik önceliği</b>: bitmeye en yakın konu/kitapları önce kapatıp motivasyonu yükseltin.<br/>"
    "• <b>Haftalık plan</b>: 4–5 gün, her gün 2 blok (40–50 dk + 10 dk ara), toplam 5–7 saat; ertesi gün "
    "10 dk “sıcak başlama” tekrarı.<br/>"
    "• <b>Veli paylaşımı</b>: haftalık iki gösterge—tamamlanan konu sayısı ve gecikme sayısı "
    "(hedef: her hafta +4 konu, –2 gecikme).<br/>"
    "• <b>Alternatif (sınava yakın)</b>: 2–3 günde bir mini deneme → hata analizi → konu etiketli onarım listesi."
)

def _P(txt, style=WRAP8):
    return Paragraph(("-" if txt in (None, "") else str(txt)), style)

def _fit_colwidths(colwidths_cm, left=1.6, right=1.6):
    """Toplam genişlik frame'i aşıyorsa orantılı küçültür (cm)."""
    frame_w_cm = (PAGE_W / cm) - left - right
    total = sum(colwidths_cm)
    if total <= frame_w_cm:
        return [w * cm for w in colwidths_cm]
    scale = frame_w_cm / total
    return [w * scale * cm for w in colwidths_cm]

def _table(data, colwidths_cm, header_bg=colors.whitesmoke,
           header_bold=True, align=None):
    """Sık kullanılan tablo kurulumunu tek yerde yapar."""
    t = Table(data, repeatRows=1, splitByRow=1,
              colWidths=_fit_colwidths(colwidths_cm))
    st = [
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('FONT', (0, 0), (-1, 0), FONT_BOLD if header_bold else FONT_REG, 9),
        ('FONT', (0, 1), (-1, -1), FONT_REG, 8),
    ]
    if align:
        st.append(('ALIGN', align[0], align[1], align[2]))
    t.setStyle(TableStyle(st))
    return t

# ===================== Grafik yardımcıları =====================

def _fig_to_img(fig, width_cm=16):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=160)
    if _HAS_MPL:
        plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    img.drawWidth = width_cm * cm
    w, h = fig.get_size_inches()
    img.drawHeight = (width_cm * cm) * (h / w)
    return img

def _normalize_series(series):
    out = []
    if not series:
        return out
    if isinstance(series, dict):
        for k in sorted(series.keys()):
            try:
                out.append((str(k), int(series[k] or 0)))
            except Exception:
                out.append((str(k), 0))
        return out
    for it in series:
        try:
            if hasattr(it, "keys"):
                if "gun" in it.keys():
                    d = it["gun"]
                    m = it["dk"] if "dk" in it.keys() else 0
                    out.append((str(d), int(m or 0)))
                    continue
            if isinstance(it, (list, tuple)) and len(it) >= 2:
                out.append((str(it[0]), int(it[1] or 0)))
                continue
            if isinstance(it, (dt.date, dt.datetime, str)):
                out.append((str(it), 0))
        except Exception:
            pass
    return out

def chart_daily_minutes(series):
    """Günlük toplam çalışma dakikası trend grafiği."""
    if not _HAS_MPL:
        return Paragraph("Grafik oluşturulamadı (matplotlib bulunamadı).", BODY)
    norm = _normalize_series(series) or [(dt.date.today().isoformat(), 0)]
    dates, mins = [], []
    for d, m in norm:
        try:
            dates.append(dt.date.fromisoformat(str(d)))
        except Exception:
            dates.append(dt.date.today())
        try:
            mins.append(int(m))
        except Exception:
            mins.append(0)
    fig = plt.figure(figsize=(8, 2.8))
    ax = fig.add_subplot(111)
    ax.plot(dates, mins, marker='o')
    ax.set_title("Günlük Çalışma Süresi (dk) – Trend")
    ax.set_xlabel("Tarih")
    ax.set_ylabel("Dakika")
    ax.grid(True, linestyle=":", linewidth=0.6)
    fig.autofmt_xdate()
    fig.tight_layout()
    return _fig_to_img(fig)

def chart_by_ders(mins_by_ders):
    """Ders bazında toplam çalışma süresi çubuk grafiği."""
    if not _HAS_MPL:
        return Paragraph("Grafik oluşturulamadı (matplotlib bulunamadı).", BODY)

    if not mins_by_ders:
        ders = ["(kayıt yok)"]
        vals = [0]
    else:
        ders = []
        vals = []
        for k, v in mins_by_ders.items():
            name = (k or "").strip() or "(adı yok)"
            ders.append(name)
            try:
                vals.append(int(v) if v is not None else 0)
            except Exception:
                vals.append(0)

    fig = plt.figure(figsize=(7.5, 3))
    ax = fig.add_subplot(111)
    x = list(range(len(ders)))
    ax.bar(x, vals)
    ax.set_title("Ders Bazında Süre Dağılımı (dk)")
    ax.set_ylabel("Dakika")
    ax.set_xticks(x)
    ax.set_xticklabels(ders, rotation=25, ha="right")
    ax.grid(axis="y", linestyle=":", linewidth=0.6)
    if all(v == 0 for v in vals):
        ax.set_ylim(0, 1)
    fig.tight_layout()
    return _fig_to_img(fig)

def chart_status_pie(done, cont, overdue):
    """
    Durum dağılımı pasta grafiği:
    Tamam / Devam / Gecikme oranlarını gösterir.
    """
    if not _HAS_MPL:
        return Paragraph("Grafik oluşturulamadı (matplotlib bulunamadı).", BODY)
    labels_tr = ["Tamam", "Devam", "Gecikme"]
    values = [int(done or 0), int(cont or 0), int(overdue or 0)]
    total = sum(values)
    if total == 0:
        values = [1, 0, 0]
        total = 1

    def _autopct(vals):
        def inner(pct):
            v = int(round(pct * sum(vals) / 100.0))
            return "" if v == 0 else f"%{pct:.0f}"
        return inner

    positive = sum(1 for v in values if v > 0)
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    if positive == 1:
        wedges, texts, autotexts = ax.pie(
            values,
            startangle=120,
            counterclock=False,
            wedgeprops=dict(width=0.45),
            labels=None,
            autopct=_autopct(values),
            pctdistance=0.75,
            textprops=dict(fontsize=10),
        )
        idx = max(range(len(values)), key=lambda i: values[i])
        ax.text(
            0, 0,
            f"{labels_tr[idx]}\n%100",
            ha="center", va="center",
            fontsize=12, fontweight="bold"
        )
    else:
        explode = [0.03 if v > 0 else 0 for v in values]
        wedges, texts, autotexts = ax.pie(
            values,
            labels=None,
            explode=explode,
            autopct=_autopct(values),
            pctdistance=0.7,
            labeldistance=1.12,
            startangle=120,
            counterclock=False,
            textprops=dict(fontsize=10),
        )
    ax.set_title("Durum Dağılımı")
    ax.axis("equal")
    if total > 0:
        legend_labels = []
        for lab, val in zip(labels_tr, values):
            prc = (100.0 * val / total) if total else 0.0
            legend_labels.append(f"{lab} – {val} adet (%{prc:.0f})")
        ax.legend(
            wedges, legend_labels, title="Özet",
            loc="center left", bbox_to_anchor=(1.02, 0.5),
            borderaxespad=0.0, fontsize=9, title_fontsize=10
        )
    fig.tight_layout()
    return _fig_to_img(fig, width_cm=12)

def chart_heatmap_weekly(day_series):
    """Kısa ısı-harita: haftanın günleri x haftalar (günlük dk)."""
    if not _HAS_MPL:
        return Paragraph("Grafik oluşturulamadı (matplotlib bulunamadı).", BODY)
    norm = _normalize_series(day_series)
    if not norm:
        return Paragraph("Isı-harita için veri yok.", BODY)
    vals = {}
    min_date, max_date = None, None
    for s, v in norm:
        try:
            d = dt.date.fromisoformat(s)
        except Exception:
            continue
        min_date = d if not min_date or d < min_date else min_date
        max_date = d if not max_date or d > max_date else max_date
        vals[d] = int(v)
    start = min_date - dt.timedelta(days=min_date.weekday())  # pazartesiden başlat
    end = max_date
    weeks = []
    cur = start
    while cur <= end:
        weeks.append(cur)
        cur += dt.timedelta(days=7)
    import numpy as np
    H = np.zeros((7, len(weeks)), dtype=int)
    for i, w0 in enumerate(weeks):
        for r in range(7):
            d = w0 + dt.timedelta(days=r)
            H[r, i] = vals.get(d, 0)
    fig = plt.figure(figsize=(8, 2.6))
    ax = fig.add_subplot(111)
    im = ax.imshow(H, aspect='auto', origin='lower')
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"])
    ax.set_xticks(range(len(weeks)))
    ax.set_xticklabels([(w.strftime("%d.%m")) for w in weeks],
                       rotation=45, ha="right")
    ax.set_title("Günlük Performans Isı Haritası (dk)")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    fig.tight_layout()
    return _fig_to_img(fig)

def chart_topN_bars(counter_map, title, xlabel="Değer", N=5):
    """En çok zaman harcanan N kitap/konu grafiği."""
    if not _HAS_MPL:
        return Paragraph("Grafik oluşturulamadı (matplotlib bulunamadı).", BODY)
    items = sorted(counter_map.items(), key=lambda x: x[1], reverse=True)[:N]
    if not items:
        return Paragraph(f"{title}: veri yok.", BODY)
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    fig = plt.figure(figsize=(7.5, 2.8))
    ax = fig.add_subplot(111)
    ax.barh(range(len(items)), vals)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", linestyle=":", linewidth=0.6)
    fig.tight_layout()
    return _fig_to_img(fig)

def chart_weekday_minutes(dk_by_dow):
    """
    Haftanın günlerine göre toplam çalışma dakikası grafiği.
    dk_by_dow: {'0': dk, '1': dk, ...} (0=Paz, 1=Pzt, ...)
    """
    if not _HAS_MPL:
        return Paragraph("Grafik oluşturulamadı (matplotlib bulunamadı).", BODY)

    labels_tr = ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"]
    vals = []
    for i in range(7):
        key = str(i)
        vals.append(int(dk_by_dow.get(key, 0) or 0))

    fig = plt.figure(figsize=(7.5, 2.8))
    ax = fig.add_subplot(111)
    ax.bar(range(7), vals)
    ax.set_xticks(range(7))
    ax.set_xticklabels(labels_tr)
    ax.set_ylabel("Dakika")
    ax.set_title("Haftanın Günlerine Göre Çalışma Dağılımı")
    ax.grid(axis="y", linestyle=":", linewidth=0.6)
    if all(v == 0 for v in vals):
        ax.set_ylim(0, 1)
    fig.tight_layout()
    return _fig_to_img(fig)

# ===================== Veri sorguları (DB ile uyumlu) =====================

def _kpis(con, ogr_id, d1, d2):
    # durum: tamam / yapildi / yapıldı / devam vb. için case-insensitive kontrol
    row = con.execute("""
        SELECT
          SUM(
            CASE
              WHEN LOWER(COALESCE(o.durum,'')) IN ('tamam','yapildi','yapıldı')
              THEN 1 ELSE 0
            END
          ) AS done,
          SUM(
            CASE
              WHEN LOWER(COALESCE(o.durum,'')) IN ('devam')
              THEN 1 ELSE 0
            END
          ) AS cont
        FROM odev o
        JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND date(k.verilis_tarihi) BETWEEN ? AND ?;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchone()
    done = int(_rget(row, "done", 0))
    cont = int(_rget(row, "cont", 0))

    row = con.execute("""
        SELECT COUNT(*) AS late
        FROM odev o
        JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=?
          AND LOWER(COALESCE(o.durum,'')) IN ('devam')
          AND date(k.bitis_tarihi) < date('now');
    """, (ogr_id,)).fetchone()
    late = int(_rget(row, "late", 0))

    row = con.execute("""
        SELECT COALESCE(SUM(o.saat_dk),0) AS mins
        FROM odev o
        JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=?
          AND date(k.verilis_tarihi) BETWEEN ? AND ?
          AND LOWER(COALESCE(o.durum,'')) IN ('tamam','yapildi','yapıldı','devam');
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchone()
    mins = int(_rget(row, "mins", 0))

    # streak (son 60 gün içinde aralıksız tamamlanan gün sayısı)
    days = [r["verilis_tarihi"] for r in con.execute("""
        SELECT DISTINCT k.verilis_tarihi
        FROM odev o JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=?
          AND LOWER(COALESCE(o.durum,'')) IN ('tamam','yapildi','yapıldı')
          AND date(k.verilis_tarihi) >= date('now','-60 day');
    """, (ogr_id,)).fetchall()]
    ds = {_date(x) for x in days if _date(x)}
    streak = 0
    cur = dt.date.today()
    while cur in ds:
        streak += 1
        cur -= dt.timedelta(days=1)
    return dict(done=done, cont=cont, late=late, mins=mins, streak=streak)

def _mins_by_ders(con, ogr_id, d1, d2):
    rows = con.execute("""
        SELECT o.ders, COALESCE(SUM(o.saat_dk),0) AS dk
        FROM odev o JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND date(k.verilis_tarihi) BETWEEN ? AND ?
        GROUP BY o.ders
        ORDER BY dk DESC;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall()
    out = {}
    for r in rows:
        name = (r["ders"] or "").strip() or "(adı yok)"
        try:
            out[name] = int(r["dk"] or 0)
        except Exception:
            out[name] = 0
    return out

def _overdues(con, ogr_id):
    rows = con.execute("""
        SELECT o.ders, o.kitap_ad, o.konu_ad, k.bitis_tarihi,
               CAST(julianday('now') - julianday(k.bitis_tarihi) AS INT) AS gecgun
        FROM odev o
        JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=?
          AND LOWER(COALESCE(o.durum,'')) IN ('devam')
          AND date(k.bitis_tarihi) < date('now')
        ORDER BY gecgun DESC;
    """, (ogr_id,)).fetchall()
    return rows

def _aktarmalar(con, ogr_id):
    rows = con.execute("""
        SELECT o.ders, o.kitap_ad, o.konu_ad,
               MIN(o.kume_id)           AS ilk,
               MAX(o.kume_id)           AS son,
               MIN(k.verilis_tarihi)    AS ilk_ver,
               MAX(k.verilis_tarihi)    AS son_ver
        FROM odev AS o
        JOIN odev_kume AS k ON k.id = o.kume_id
        WHERE o.ogrenci_id=?
        GROUP BY o.ders, o.kitap_ad, o.konu_ad
        HAVING COUNT(DISTINCT o.kume_id) > 1
        ORDER BY son DESC;
    """, (ogr_id,)).fetchall()
    return rows

def _konu_kapsam(con, ogr_id, ders_key):
    topics = []
    try:
        topics = [r["konu"] for r in con.execute("SELECT konu FROM %s" % ders_key)]
    except Exception:
        return []
    rows = con.execute("""
        SELECT konu_ad,
               MAX(
                 CASE WHEN LOWER(COALESCE(durum,'')) IN ('tamam','yapildi','yapıldı')
                      THEN 1 ELSE 0 END
               ) AS tamam,
               MAX(
                 CASE WHEN LOWER(COALESCE(durum,'')) IN ('devam')
                      THEN 1 ELSE 0 END
               ) AS devam
        FROM odev
        WHERE ogrenci_id=? AND ders=?
        GROUP BY konu_ad;
    """, (ogr_id, ders_key)).fetchall()
    mp = {
        r["konu_ad"]: (
            "tamam" if r["tamam"] else "devam" if r["devam"] else "yok"
        )
        for r in rows
    }
    out = []
    for k in topics:
        out.append((k, mp.get(k, "yok")))
    return out

def _kitap_listesi(con, ogr_id):
    rows = con.execute("""
        SELECT ders, kitap_ad, MIN(eklenme_tarih) AS eklenme
        FROM ogrenci_kitap
        WHERE ogrenci_id=?
        GROUP BY ders, kitap_ad
        ORDER BY ders, kitap_ad;
    """, (ogr_id,)).fetchall()
    return rows

def _kitap_ozet(con, ogr_id, ders, kitap):
    row = con.execute("""
        SELECT
          COUNT(*) AS toplam,
          SUM(LOWER(COALESCE(durum,'')) IN ('tamam','yapildi','yapıldı')) AS tamam,
          SUM(LOWER(COALESCE(durum,'')) IN ('devam')) AS devam,
          SUM(CASE WHEN silindi=1 THEN 1 ELSE 0 END) AS silinen,
          COALESCE(SUM(saat_dk),0) AS dk,
          MIN(k.verilis_tarihi) AS ilk_ver,
          MAX(k.verilis_tarihi) AS son_ver
        FROM odev o
        JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND o.ders=? AND o.kitap_ad=?;
    """, (ogr_id, ders, kitap)).fetchone()

    iler = con.execute("""
        SELECT yuzde, last_done_ts, bitti_say, konu_say
        FROM ogrenci_kitap_ilerleme
        WHERE ogrenci_id=? AND ders=? AND kitap=?;
    """, (ogr_id, ders, kitap)).fetchone()

    return dict(
        toplam=int(_rget(row, "toplam", 0)),
        tamam=int(_rget(row, "tamam", 0)),
        devam=int(_rget(row, "devam", 0)),
        silinen=int(_rget(row, "silinen", 0)),
        dk=int(_rget(row, "dk", 0)),
        ilk_ver=_rget(row, "ilk_ver", None),
        son_ver=_rget(row, "son_ver", None),
        yuzde=int(_rget(iler or {}, "yuzde", 0)),
        last_done_ts=_rget(iler or {}, "last_done_ts", None),
        bitti_say=int(_rget(iler or {}, "bitti_say", 0)),
        konu_say=int(_rget(iler or {}, "konu_say", 0)),
    )

def _kitap_konu_dokumu(con, ogr_id, ders, kitap):
    rows = con.execute("""
        SELECT
          konu_ad AS konu,
          SUM(1) AS atama_adet,
          SUM(LOWER(COALESCE(durum,'')) IN ('tamam','yapildi','yapıldı')) AS tamam,
          SUM(LOWER(COALESCE(durum,'')) IN ('devam')) AS devam,
          COALESCE(SUM(saat_dk),0) AS dk,
          MIN(k.verilis_tarihi) AS ilk_ver,
          MAX(k.verilis_tarihi) AS son_ver,
          MAX(o.tamamlanma_tarihi) AS son_tamam
        FROM odev o
        JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND o.ders=? AND o.kitap_ad=?
        GROUP BY konu
        ORDER BY tamam DESC, atama_adet DESC, konu;
    """, (ogr_id, ders, kitap)).fetchall()
    return rows

def _silinen_odevler(con, ogr_id, d1=None, d2=None):
    where = "o.ogrenci_id=? AND o.silindi=1"
    params = [ogr_id]
    if d1 and d2:
        where += " AND date(o.silinme_tarihi) BETWEEN ? AND ?"
        params += [d1.isoformat(), d2.isoformat()]
    rows = con.execute("""
        SELECT o.ders, o.kitap_ad, o.konu_ad, o.durum,
               o.silinme_tarihi, o.silinme_nedeni
        FROM odev o
        WHERE %s
        ORDER BY o.silinme_tarihi DESC, o.ders, o.kitap_ad, o.konu_ad;
    """ % where, params).fetchall()
    return rows

def _gunluk_tarihce(con, ogr_id, d1, d2):
    out = defaultdict(lambda: dict(atama=0, tamam=0, aktar=0, silme=0, durum=0))

    for r in con.execute("""
        SELECT k.verilis_tarihi AS gun, COUNT(*) AS n
        FROM odev o JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND date(k.verilis_tarihi) BETWEEN ? AND ?
        GROUP BY k.verilis_tarihi;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall():
        out[_rget(r, "gun", "")]["atama"] += int(_rget(r, "n", 0))

    for r in con.execute("""
        SELECT o.tamamlanma_tarihi AS gun, COUNT(*) AS n
        FROM odev o
        WHERE o.ogrenci_id=?
          AND o.tamamlanma_tarihi IS NOT NULL
          AND date(o.tamamlanma_tarihi) BETWEEN ? AND ?
        GROUP BY o.tamamlanma_tarihi;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall():
        out[_rget(r, "gun", "")]["tamam"] += int(_rget(r, "n", 0))

    for r in con.execute("""
        SELECT date(ts) AS gun, COUNT(*) AS n
        FROM odev_aktar_log
        WHERE ogrenci_id=? AND date(ts) BETWEEN ? AND ?
        GROUP BY date(ts);
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall():
        out[_rget(r, "gun", "")]["aktar"] += int(_rget(r, "n", 0))

    for r in con.execute("""
        SELECT date(silinme_tarihi) AS gun, COUNT(*) AS n
        FROM odev
        WHERE ogrenci_id=? AND silindi=1
          AND date(silinme_tarihi) BETWEEN ? AND ?
        GROUP BY date(silinme_tarihi);
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall():
        out[_rget(r, "gun", "")]["silme"] += int(_rget(r, "n", 0))

    for r in con.execute("""
        SELECT date(durum_degisti_tarihi) AS gun, COUNT(*) AS n
        FROM odev
        WHERE ogrenci_id=? AND durum_degisti_tarihi IS NOT NULL
          AND date(durum_degisti_tarihi) BETWEEN ? AND ?
        GROUP BY date(durum_degisti_tarihi);
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall():
        out[_rget(r, "gun", "")]["durum"] += int(_rget(r, "n", 0))

    timeline = []
    for day in _daterange(d1, d2):
        key = day.isoformat()
        d = out.get(key, dict(atama=0, tamam=0, aktar=0, silme=0, durum=0))
        timeline.append((key, d["atama"], d["tamam"], d["aktar"], d["silme"], d["durum"]))
    return timeline

def _kume_odevleri(con, ogr_id, d1, d2):
    rows = con.execute("""
        SELECT k.id AS kume_id, k.verilis_tarihi, k.bitis_tarihi, k.aciklama,
               o.ders, o.kitap_ad, o.konu_ad, o.durum, o.saat_dk
        FROM odev o
        JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND date(k.verilis_tarihi) BETWEEN ? AND ?
        ORDER BY k.verilis_tarihi, k.id, o.ders, o.kitap_ad, o.konu_ad;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall()
    return rows

def _mins_daily(con, ogr_id, d1, d2):
    """
    [d1, d2] aralığında her gün için toplanan dakika.
    Kayıt olmayan günler 0 dk olarak döner.
    """
    rows = con.execute("""
        SELECT k.verilis_tarihi AS gun, COALESCE(SUM(o.saat_dk),0) AS dk
        FROM odev o
        JOIN odev_kume k ON k.id = o.kume_id
        WHERE o.ogrenci_id = ?
          AND date(k.verilis_tarihi) BETWEEN ? AND ?
        GROUP BY k.verilis_tarihi
        ORDER BY k.verilis_tarihi;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall()

    mp = {str(r["gun"]): int(r["dk"] or 0) for r in rows}
    return [(day.isoformat(), mp.get(day.isoformat(), 0)) for day in _daterange(d1, d2)]

def _mins_by_weekday(con, ogr_id, d1, d2):
    """
    Haftanın günlerine göre toplam dk.
    0=Pazar, 1=Pazartesi, ... 6=Cumartesi
    """
    rows = con.execute("""
        SELECT strftime('%w', date(k.verilis_tarihi)) AS dow,
               COALESCE(SUM(o.saat_dk),0) AS dk
        FROM odev o
        JOIN odev_kume k ON k.id = o.kume_id
        WHERE o.ogrenci_id = ?
          AND date(k.verilis_tarihi) BETWEEN ? AND ?
        GROUP BY dow
        ORDER BY dow;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall()
    mp = {}
    for r in rows:
        dow = str(_rget(r, "dow", "0"))
        mp[dow] = int(_rget(r, "dk", 0))
    return mp

# ===================== PDF üretimi =====================

def ogrenci_rapor_pdf(ogr_id: int, fn: str, d1, d2,
                      kurum_adi: Optional[str] = None,
                      logo_path: Optional[str] = None,
                      genel_degerlendirme: Optional[str] = None):
    """
    Tek öğrencilik detaylı PDF raporu üretir.
    """
    con = db.get_conn()
    ogr = con.execute("SELECT * FROM ogrenci WHERE id=?", (ogr_id,)).fetchone()
    if not ogr:
        raise RuntimeError("Öğrenci bulunamadı")

    adsoy = f"{ogr['ad']} {ogr['soyad']}"

    doc = SimpleDocTemplate(
        fn, pagesize=A4,
        leftMargin=_cm(1.6), rightMargin=_cm(1.6),
        topMargin=_cm(1.4), bottomMargin=_cm(1.4)
    )
    story = []

    # ---- Kapak ve üst bilgi
    cap = kurum_adi or "Ödev Takip Raporu"
    if logo_path and os.path.exists(logo_path):
        try:
            im = Image(logo_path, width=_cm(2.0), height=_cm(2.0))
            im.hAlign = 'RIGHT'
            story.append(im)
        except Exception:
            pass

    story.append(Paragraph(cap, TITLE))
    story.append(Spacer(1, _cm(0.2)))
    story.append(Paragraph(f"Öğrenci: <b>{adsoy}</b>", H2))
    story.append(Paragraph(f"Dönem: {d1} – {d2}", BODY))
    story.append(Spacer(1, _cm(0.35)))

    # KPI
    k = _kpis(con, ogr_id, d1, d2)
    gun_say = max((d2 - d1).days + 1, 1)
    ort_gun = k['mins'] // gun_say if gun_say > 0 else 0
    toplam_odev = k['done'] + k['cont']
    tamamlama_orani = (100.0 * k['done'] / toplam_odev) if toplam_odev > 0 else 0.0

    kpi_tbl = _table([
        [
            _P("Tamamlama", WRAP9B), _P(k['done']),
            _P("Devam", WRAP9B), _P(k['cont']),
            _P("Gecikme (aktif)", WRAP9B), _P(k['late']),
            _P("Günlük Ort.", WRAP9B), _P(f"{ort_gun} dk"),
            _P("Streak", WRAP9B), _P(f"{k['streak']} gün")
        ]
    ], [2.2, 1.6, 1.8, 1.6, 3.0, 1.8, 2.4, 2.0, 1.8, 2.0])
    story.append(kpi_tbl)
    story.append(Spacer(1, _cm(0.2)))

    # KPI açıklaması (veli için)
    story.append(Paragraph(
        "Bu satırda öğrencinin seçilen dönemdeki genel performansı özetlenmiştir. "
        "<b>Tamamlama</b> biten ödev sayısını, <b>Devam</b> hâlâ üzerinde çalışılan ödevleri, "
        "<b>Gecikme</b> süreyi geçen ödevleri, <b>Günlük Ort.</b> ise bu dönem boyunca günlük "
        "ortalama çalışma süresini gösterir. <b>Streak</b>, öğrencinin hiç ara vermeden üst üste "
        "çalıştığı gün sayısıdır.", WRAP8)
    )
    story.append(Spacer(1, _cm(0.3)))

    # --- Velilere kısa özet (Top gecikenler + mini ısı-harita)
    story.append(Paragraph("Velilere Kısa Özet", H2))
    story.append(Paragraph(
        "Bu bölümde, özellikle gecikmiş ödevler ve son haftalardaki çalışma yoğunluğu "
        "kısaca gösterilmektedir. Veliler için, takibin nereden başlayacağına dair hızlı bir "
        "bakış sunar.", WRAP8)
    )

    ov = _overdues(con, ogr_id)
    data = [[
        _P("Ders", WRAP9B), _P("Kitap", WRAP9B), _P("Konu", WRAP9B),
        _P("Bitiş", WRAP9B), _P("Gecikme (gün)", WRAP9B)
    ]]
    if not ov:
        data.append([_P("-"), _P("-"), _P("Gecikmiş ödev yok."), _P("-"), _P("-")])
    else:
        for r in ov[:5]:
            data.append([
                _P(r["ders"]), _P(r["kitap_ad"]), _P(r["konu_ad"]),
                _P(r["bitis_tarihi"]), _P(int(r["gecgun"]))
            ])
    story.append(_table(
        data,
        [2.0, 3.0, 8.6, 2.2, 2.2],
        header_bg=colors.Color(0.93, 0.40, 0.40)
    ))

    day_series = _mins_daily(con, ogr_id, d1, d2)
    story.append(Spacer(1, _cm(0.25)))
    story.append(chart_heatmap_weekly(day_series))
    story.append(Paragraph(
        "Isı-haritadaki renk yoğunluğu, o gün daha fazla dakika çalışıldığını gösterir. "
        "Daha koyu alanlar, öğrencinin daha verimli geçtiği günleri; açık alanlar ise "
        "daha zayıf günleri göstermektedir.", WRAP8)
    )

    # Top N’ler: en çok zaman harcanan kitap & konular
    rows = con.execute("""
        SELECT o.kitap_ad AS k, COALESCE(SUM(o.saat_dk),0) AS dk
        FROM odev o JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND date(k.verilis_tarihi) BETWEEN ? AND ?
        GROUP BY o.kitap_ad ORDER BY dk DESC;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall()
    top_kitap = {_rget(r, 'k', '-'): int(_rget(r, 'dk', 0)) for r in rows}

    rows = con.execute("""
        SELECT o.konu_ad AS k, COALESCE(SUM(o.saat_dk),0) AS dk
        FROM odev o JOIN odev_kume k ON k.id=o.kume_id
        WHERE o.ogrenci_id=? AND date(k.verilis_tarihi) BETWEEN ? AND ?
        GROUP BY o.konu_ad ORDER BY dk DESC;
    """, (ogr_id, d1.isoformat(), d2.isoformat())).fetchall()
    top_konu = {_rget(r, 'k', '-'): int(_rget(r, 'dk', 0)) for r in rows}

    story.append(Spacer(1, _cm(0.25)))
    story.append(chart_topN_bars(top_kitap, "En Çok Zaman Harcanan 5 Kitap", "Dakika", N=5))
    story.append(Paragraph(
        "Bu grafik, öğrencinin en çok zaman ayırdığı kitapları göstermektedir. "
        "Özellikle sınav senesinde bazı kitaplarda aşırı yoğunlaşma veya tam tersi "
        "hiç dokunulmayan kaynaklar bu grafikten fark edilebilir.", WRAP8)
    )
    story.append(Spacer(1, _cm(0.15)))
    story.append(chart_topN_bars(top_konu, "En Çok Zaman Harcanan 5 Konu", "Dakika", N=5))
    story.append(Paragraph(
        "Burada ise konular bazında harcanan süre görülmektedir. Öğrenci, zorlandığı "
        "konularda daha çok tekrar yapıyor olabilir; veli, hangi konuların önceliklendirildiğini "
        "bu grafikten takip edebilir.", WRAP8)
    )

    # Ana grafikler
    story.append(Spacer(1, _cm(0.25)))
    story.append(chart_daily_minutes(day_series))
    story.append(Paragraph(
        "Günlük çalışma süresi grafiği, seçilen tarihler arasında öğrencinin "
        "hangi günler daha düzenli çalıştığını gösterir. Çok dalgalı bir grafik, "
        "düzenli çalışma alışkanlığının henüz oturmadığına işaret edebilir.", WRAP8)
    )

    story.append(Spacer(1, _cm(0.2)))
    story.append(chart_by_ders(_mins_by_ders(con, ogr_id, d1, d2)))
    story.append(Paragraph(
        "Ders bazında süre dağılımı, hangi derse ne kadar zaman ayrıldığını "
        "özetler. Eksik kaldığı düşünülen derslerde süreyi bir miktar artırmak, "
        "güçlü derslerde ise daha çok pekiştirme ve soru çözümüne yönelmek önerilir.", WRAP8)
    )

    story.append(Spacer(1, _cm(0.2)))
    story.append(chart_status_pie(k['done'], k['cont'], k['late']))
    story.append(Paragraph(
        "Durum dağılımı grafiğinde; <b>Tamam</b> bitmiş ödevleri, "
        "<b>Devam</b> hâlâ sürdürülenleri, <b>Gecikme</b> ise süresi geçmiş "
        "olmasına rağmen tamamlanmamış ödevleri göstermektedir. Hedef, gecikme dilimini "
        "mümkün olduğunca küçük tutmaktır.", WRAP8)
    )

    # Yeni: Haftanın günlerine göre çalışma grafiği
    story.append(Spacer(1, _cm(0.2)))
    dk_by_dow = _mins_by_weekday(con, ogr_id, d1, d2)
    story.append(chart_weekday_minutes(dk_by_dow))
    story.append(Paragraph(
        "Bu grafikte, haftanın hangi günlerinde daha çok çalışıldığı görülür. "
        "Örneğin hafta sonu çok yoğun, hafta içi çok zayıf ise, hafta içi için "
        "küçük ama düzenli çalışma blokları eklemek faydalı olacaktır.", WRAP8)
    )

    story.append(PageBreak())

    # Kitap Bazlı Özet
    story.append(Paragraph("Kitap Bazlı Özet", H2))
    story.append(Paragraph(
        "Bu bölüm, öğrencinin her bir kitap için kaç konu atandığını, "
        "ne kadarını tamamladığını ve toplamda ne kadar süre harcadığını göstermektedir. "
        "Veliler için, kullanılan kaynakların ne derece verimli gittiğini takip etme imkânı sunar.", WRAP8)
    )

    kitaplar = _kitap_listesi(con, ogr_id)
    if not kitaplar:
        story.append(Paragraph("Öğrenciye kayıtlı kitap bulunamadı.", BODY))
    else:
        data = [[
            _P("Ders", WRAP9B), _P("Kitap", WRAP9B), _P("Konu Say", WRAP9B),
            _P("Biten", WRAP9B), _P("Devam", WRAP9B), _P("Silinen", WRAP9B),
            _P("Toplam dk", WRAP9B), _P("% İlerleme", WRAP9B),
            _P("İlk Ver.", WRAP9B), _P("Son Ver.", WRAP9B), _P("Son Tamam", WRAP9B)
        ]]
        for r in kitaplar:
            ders, kitap = r["ders"], r["kitap_ad"]
            oz = _kitap_ozet(con, ogr_id, ders, kitap)
            data.append([
                _P(ders), _P(kitap), _P(oz['konu_say'] or "-"),
                _P(oz['tamam']), _P(oz['devam']), _P(oz['silinen']),
                _P(oz['dk']), _P(f"{oz['yuzde']}%"),
                _P(oz['ilk_ver'] or "-"), _P(oz['son_ver'] or "-"),
                _P(oz['last_done_ts'] or "-")
            ])
        story.append(_table(
            data,
            [2.1, 3.4, 1.7, 1.5, 1.6, 1.8, 2.0, 2.0, 2.2, 2.2, 2.4]
        ))
    story.append(PageBreak())

    # Kitaplara Göre Konu Dökümü (kitap bazında)
    story.append(Paragraph("Kitaplara Göre Konu Dökümü", H2))
    story.append(Paragraph(
        "Her kitap için konu bazında atama ve tamamlama durumları bu bölümde listelenmiştir. "
        "Bu tablo, hangi konuların tekrar tekrar verildiğini ve hangilerinin hızlıca tamamlandığını "
        "göstermesi açısından önemlidir.", WRAP8)
    )

    if not kitaplar:
        story.append(Paragraph("Liste yok.", BODY))
    else:
        for r in kitaplar:
            ders, kitap = r["ders"], r["kitap_ad"]
            story.append(Paragraph(f"{ders} / <b>{kitap}</b>", H3))
            rows = _kitap_konu_dokumu(con, ogr_id, ders, kitap)
            if not rows:
                story.append(Paragraph("Kayıt bulunamadı.", BODY))
                story.append(Spacer(1, _cm(0.2)))
                continue
            data = [[
                _P("Konu", WRAP9B), _P("Atama", WRAP9B), _P("Tamam", WRAP9B),
                _P("Devam", WRAP9B), _P("Toplam dk", WRAP9B),
                _P("İlk Ver.", WRAP9B), _P("Son Ver.", WRAP9B),
                _P("Son Tamam", WRAP9B)
            ]]
            for x in rows:
                data.append([
                    _P(x["konu"]),
                    _P(int(_rget(x, "atama_adet", 0))),
                    _P(int(_rget(x, "tamam", 0))),
                    _P(int(_rget(x, "devam", 0))),
                    _P(int(_rget(x, "dk", 0))),
                    _P(_rget(x, "ilk_ver", "-") or "-"),
                    _P(_rget(x, "son_ver", "-") or "-"),
                    _P(_rget(x, "son_tamam", "-") or "-")
                ])
            story.append(_table(
                data,
                [7.6, 1.6, 1.6, 1.8, 2.2, 2.2, 2.2, 2.4],
                header_bg=colors.Color(0.78, 0.90, 0.96)
            ))
            story.append(Spacer(1, _cm(0.25)))
    story.append(PageBreak())

    # Silinen Ödevler
    story.append(Paragraph("Silinen Ödevler (Log)", H2))
    story.append(Paragraph(
        "Bu bölüm, sistemden silinen ödevleri ve silinme nedenlerini gösterir. "
        "Genellikle yanlış girilmiş kayıtlar veya tekrarlayan ödevler burada listelenir.", WRAP8)
    )

    sil = _silinen_odevler(con, ogr_id, d1, d2)
    if not sil:
        story.append(Paragraph("Bu dönemde silinen ödev kaydı yok.", BODY))
    else:
        data = [[
            _P("Ders", WRAP9B), _P("Kitap", WRAP9B), _P("Konu", WRAP9B),
            _P("Durum", WRAP9B), _P("Silinme Tarihi", WRAP9B),
            _P("Neden", WRAP9B)
        ]]
        for s in sil:
            data.append([
                _P(_rget(s, "ders", "-")),
                _P(_rget(s, "kitap_ad", "-")),
                _P(_rget(s, "konu_ad", "-")),
                _P(_rget(s, "durum", "-")),
                _P(_rget(s, "silinme_tarihi", "-")),
                _P(_rget(s, "silinme_nedeni", "-"))
            ])
        story.append(_table(
            data,
            [2.2, 3.0, 7.6, 2.0, 2.8, 3.0],
            header_bg=colors.Color(0.95, 0.80, 0.80)
        ))
    story.append(PageBreak())

    # Tarihçe – Gün Gün Olaylar
    story.append(Paragraph("Tarihçe – Gün Gün Olaylar", H2))
    story.append(Paragraph(
        "Bu tablo, seçilen dönemde her gün kaç ödev atandığını, kaçının tamamlandığını, "
        "kaçı başka kümelere aktarıldığını ve kaç silme / durum değişikliği yapıldığını "
        "gün gün göstermektedir.", WRAP8)
    )

    tl = _gunluk_tarihce(con, ogr_id, d1, d2)
    if tl:
        data = [[
            _P("Tarih", WRAP9B), _P("Atama", WRAP9B), _P("Tamam", WRAP9B),
            _P("Aktarım", WRAP9B), _P("Silme", WRAP9B),
            _P("Durum Değişimi", WRAP9B)
        ]]
        for gun, a, tmm, akt, silm, dur in tl:
            if any([a, tmm, akt, silm, dur]):
                data.append([
                    _P(gun), _P(a), _P(tmm),
                    _P(akt), _P(silm), _P(dur)
                ])
        if len(data) == 1:
            story.append(Paragraph("Bu dönemde kayıtlı olay yok.", BODY))
        else:
            story.append(_table(
                data,
                [2.6, 1.8, 1.8, 2.0, 1.8, 3.4]
            ))
    else:
        story.append(Paragraph("Bu dönemde kayıtlı olay yok.", BODY))
    story.append(PageBreak())

    # Kümelere Göre Atanan Ödevler
    story.append(Paragraph("Kümelere Göre Atanan Ödevler (Tarih Tarih)", H2))
    story.append(Paragraph(
        "Her ödev kümesi için hangi dersten, hangi kitaptan ve hangi konulardan "
        "ödev verildiği bu bölümde listelenir. Bu sayede, büyük ödev paketlerinin "
        "içeriği tek bakışta görülebilir.", WRAP8)
    )

    ko = _kume_odevleri(con, ogr_id, d1, d2)
    if not ko:
        story.append(Paragraph("Bu dönemde kümelere atanan ödev bulunmuyor.", BODY))
    else:
        by_kume = defaultdict(list)
        for r in ko:
            by_kume[(r["kume_id"], r["verilis_tarihi"],
                     r["bitis_tarihi"], r["aciklama"])].append(r)
        for (kid, ver, bit, acik), lst in by_kume.items():
            story.append(Paragraph(
                f"Küme #{kid} – Veriliş: {ver} – Bitiş: {bit or '-'}", H3)
            )
            if acik:
                story.append(Paragraph(f"<i>Açıklama:</i> {acik}", BODY))
            data = [[
                _P("Ders", WRAP9B), _P("Kitap", WRAP9B), _P("Konu", WRAP9B),
                _P("Durum", WRAP9B), _P("Dakika", WRAP9B)
            ]]
            for r in lst:
                data.append([
                    _P(r["ders"]), _P(r["kitap_ad"]), _P(r["konu_ad"]),
                    _P(r["durum"]), _P(int(_rget(r, "saat_dk", 0)))
                ])
            story.append(_table(
                data,
                [2.2, 3.0, 9.0, 2.0, 1.6],
                header_bg=colors.Color(0.90, 0.95, 0.98)
            ))
            story.append(Spacer(1, _cm(0.22)))

    # Konu Kapsamı – tüm dersler
    story.append(PageBreak())
    story.append(Paragraph("Konu Kapsamı (Tüm Dersler)", H2))
    story.append(Paragraph(
        "Bu bölümde, öğrencinin derslere ait konu listeleri üzerinde ne kadar ilerlediği "
        "özetlenir. “Tamam” işaretli konular bitmiş, “Devam” olanlar üzerinde çalışılan, "
        "çizgi (—) olanlar ise henüz hiç başlanmamış konuları ifade eder.", WRAP8)
    )

    dersler = [
        r["ders"] for r in con.execute(
            "SELECT DISTINCT ders FROM odev WHERE ogrenci_id=?",
            (ogr_id,)
        ).fetchall()
    ]

    def _table_exists(con_, name):
        try:
            con_.execute("SELECT 1 FROM %s LIMIT 1" % name)
            return True
        except Exception:
            return False

    for ders_key in dersler:
        if not _table_exists(con, ders_key):
            continue
        rows = _konu_kapsam(con, ogr_id, ders_key)
        if not rows:
            continue
        story.append(Paragraph(ders_key.replace("_", " ").upper(), H3))
        data = [[_P("Konu", WRAP9B), _P("Durum", WRAP9B)]]
        for ktopic, st in rows:
            data.append([
                _P(ktopic),
                _P({"tamam": "Tamam", "devam": "Devam", "yok": "—"}.get(st, "—"))
            ])
        story.append(_table(
            data,
            [12.6, 4.4],
            header_bg=colors.grey
        ))
        story.append(Spacer(1, _cm(0.25)))

    # Son sayfa – notlar
    story.append(PageBreak())
    story.append(Paragraph("Genel Değerlendirme ve Notlar", H2))

    metin = (genel_degerlendirme
             if (genel_degerlendirme and genel_degerlendirme.strip())
             else DEFAULT_GENEL_METIN)
    story.append(Paragraph(metin, BODY))

    story.append(Spacer(1, _cm(0.6)))
    story.append(Paragraph(
        "<i>Not:</i> Bu rapor, öğrencinin sistemde kayıtlı çalışma verileri "
        "dikkate alınarak otomatik olarak oluşturulmuştur. Veliler, bu raporu "
        "öğrenciyle birlikte inceleyerek haftalık hedefler belirleyebilir.",
        BODY
    ))

    doc.build(story)
