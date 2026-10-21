# -*- coding: utf-8 -*-
"""Salt-okunur ve açıklanabilir rapor yorumu.

Ödev kayıtları/deneme netleri/öğrenci kişisel verileri internete gönderilmez.
İstatistiksel çıkarımlar yalnızca sağlanan grafiğin kanıtlayabildiği sınırdadır.
"""
from __future__ import annotations
from html import escape
from math import isfinite


def interpret_chart(chart_type: str, rows) -> str:
    """Seçili grafiğin kayıtlarına göre güvenli HTML açıklaması üretir.

    Satır sayıları, durumu veya ölçümün kaynağını değiştirmez. Uç değer ve
    öğrenci adlarında HTML karakterleri de zararsız metne dönüşür.
    """
    clean = []
    for label, value in (rows or ()):  # Kayıtlar güvenilmeyen içerik olabilir.
        try:
            value = float(value)
        except (ValueError, TypeError, OverflowError):
            continue
        if not isfinite(value) or value < 0:
            continue
        clean.append((str(label), value))
    if not clean or not any(v > 0 for _, v in clean):
        return ("<b>Ölçüm bulunamadı.</b> Bu tarih aralığında seçilen koşullara "
                "uygun pozitif kayıt yok. Filtreleri veya veri kaynağını kontrol edin; "
                "veri yokluğu başarısızlık değildir.")

    data = dict(clean)
    total = sum(v for _, v in clean)
    name = lambda v: escape(str(v), quote=True)
    num = lambda v: f"{v:,.0f}".replace(",", ".")
    caveat = ("<br><small>Bu değerler kayıtlı ödev/çalışma ölçüleridir; "
              "sınav başarısı, yetenek veya psikolojik değerlendirme değildir.</small>")

    if chart_type == "Durum Dağılımı":
        done = data.get("yapildi", 0)
        pending = data.get("devam", 0)
        cancelled = data.get("iptal", 0)
        # İptal edilmiş görevleri başarı paydasına otomatik eklemiyoruz.
        eligible = done + pending
        if eligible == 0:
            return (f"<b>{num(total)} durum kaydı</b> görüntülendi; "
                    "aktif görev paydası yok. Oran yorumlanmıyor." + caveat)
        pct = done / eligible * 100
        return (f"<b>{num(done)}/{num(eligible)} etkin durum kaydı tamam.</b> "
                f"Tamamlanma: %{pct:.1f}; bekleyen: {num(pending)}; "
                f"iptal: {num(cancelled)}. "
                "Öneri: Bekleyen görevlerin teslim tarihlerini ve kayıtların "
                "tekrarsız olduğunu kontrol edin." + caveat)

    if chart_type == "Haftalık Saat Trendi (dk)":
        if len(clean) < 2:
            return "Trend için yalnızca bir hafta ölçümü var; değişim yorumu yapılmaz." + caveat
        (prev_label, prev), (last_label, last) = clean[-2:]
        diff = last - prev
        direction = "arttı" if diff > 0 else "azaldı" if diff < 0 else "değişmedi"
        return (f"<b>{name(prev_label)}:</b> {num(prev)} dk; "
                f"<b>{name(last_label)}:</b> {num(last)} dk. "
                f"Kayıtlı süre {num(abs(diff))} dk {direction}. "
                "Öneri: Kayıt eksikliği, ders programı ve ödev yükünü kontrol edin; "
                "motivasyon veya başarı değişimi çıkarılmamalı." + caveat)

    if chart_type == "Geciken Ödevler":
        target, count = max(clean, key=lambda r: r[1])
        return (f"Görüntülenen grupta en fazla <b>gecikmiş küme kaydı</b> "
                f"<b>{name(target)}</b> için görünüyor ({num(count)}). "
                "Öneri: Öğrenciyle birlikte teslim tarihlerini ve gerçek "
                "görev yükünü kontrol edin; bu bir kişilik/çalışkanlık yargısı değildir." + caveat)

    if chart_type == "Öğrenci Başına Tamamlanan (Top 10)":
        target, count = max(clean, key=lambda r: r[1])
        return (f"En fazla tamamlanmış <b>görev kaydı</b> "
                f"<b>{name(target)}</b> için ({num(count)}). "
                "Öğrencilerin verilen görev sayısı farklı olabilir; "
                "tamamlanan adet tek başına adil sıralama değildir." + caveat)

    if chart_type == "Tamamlama Oranı %":
        # Grafikte toplam/payda verilmez: öğrenci/branş kapsamını dışarıdan varsayma.
        pct = sum(x for _, x in clean) / len(clean)
        return (f"Gösterilen <b>{len(clean)} oran</b> için ağırlıksız "
                f"aritmetik ortalama %{pct:.1f}. "
                "Her oranın paydası ve görev sayısı burada bulunmuyor. "
                "Öğrenci/kurum geneli veya sınav başarısı olarak yorumlamayın." + caveat)

    if chart_type == "Konu Verimi (dk/konu)":
        target, minutes = max(clean, key=lambda r: r[1])
        return (f"En yüksek kaydedilmiş süre <b>{name(target)}</b> "
                f"konusunda ({num(minutes)} dk). "
                "Uzun süre zorlanma kanıtı değildir; içerik uzunluğu veya "
                "çalışma yoğunluğu farklı olabilir. Net/yanlış analizleriyle kontrol edin." + caveat)

    if chart_type == "Hafta içi / Hafta sonu":
        wd, we = data.get("Hafta içi", 0), data.get("Hafta sonu", 0)
        return (f"Kayıtlı toplam süre: hafta içi {num(wd)} dk; "
                f"hafta sonu {num(we)} dk. "
                "Bu dönemlerin gün sayısı farklıdır; "
                "gün başına süre karşılaştırması yapılmadan 'daha yoğun' sonucuna varmayın." + caveat)

    if chart_type == "Öğrenci KPI":
        return (f"<b>{len(clean)} öğrencinin</b> gösterilen tamamlama göstergesi var. "
                "Kriter, tarih aralığı ve görev sayıları kontrol edilmeden "
                "öğrencilerin akademik başarısı sıralanamaz." + caveat)

    if chart_type == "Seri (Streak)":
        return ("Aralıksız gün sayısı, sistemde kayıt bulunan günleri gösterir. "
                "Kayıtsız gün gerçekten çalışılmadığını kanıtlamaz." + caveat)

    return (f"<b>{len(clean)} veri noktası</b> görüntüleniyor. "
            "Grafiği ilgili tarih aralığı ve veri kaynağıyla birlikte değerlendirin. "
            "Tek başına öğrencinin akademik yeterliği hakkında hüküm vermeyin." + caveat)
