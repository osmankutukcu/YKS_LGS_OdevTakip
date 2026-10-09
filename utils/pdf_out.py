# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from datetime import datetime
from textwrap import wrap
from textwrap import wrap

from textwrap import wrap

def verilen_odevler_pdf(dosya, baslik, ogrenci_adsoyad, bitis_tarihi, satirlar,
                         logo_path=None, kurum_adi=None, logo_align='left', iletisim_satiri=None, qr_link=None):
    """
    satirlar: list of dicts -> {"ders","kitap","konu","sure","aciklama"}
    """
    c = canvas.Canvas(dosya, pagesize=A4)
    w, h = A4

    # Başlık
    # Logo & başlık hizalama
    x_logo = 2*cm
    if logo_align == 'center':
        x_logo = (w-2.5*cm)/2
    elif logo_align == 'right':
        x_logo = w - 2.5*cm - 2*cm
    if logo_path:
        try:
            c.drawImage(logo_path, x_logo, h-2.8*cm, width=2.5*cm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setFont("Helvetica-Bold", 16)
    title = kurum_adi or baslik
    c.drawCentredString(w/2, h-2*cm, title)
    c.setFont("Helvetica", 11)
    c.drawString(2*cm, h-2.7*cm, f"Öğrenci: {ogrenci_adsoyad}")
    c.drawString(2*cm, h-3.2*cm, f"Bitiş Tarihi: {bitis_tarihi}")
    if iletisim_satiri:
        c.setFont("Helvetica-Oblique", 9)
        c.drawRightString(w-2*cm, h-3.2*cm, iletisim_satiri)

    # Tablo başlıkları
    y = h - 4*cm
    headers = ["Ders", "Kitap", "Konu", "Süre (dk)", "Açıklama"]
    widths = [3.0*cm, 4.0*cm, 7.0*cm, 2.5*cm, 4.0*cm]

    def _wraps(cells):
        widths = [5*cm, 5*cm, 6*cm, 3*cm, 6*cm]
        out_lines, max_lines = [], 1
        for i, txt in enumerate(cells):
            char_w = 0.16*cm
            max_chars = max(1, int(widths[i]/char_w))
            lines = wrap(str(txt), max_chars)
            out_lines.append(lines)
            max_lines = max(max_lines, len(lines))
        return out_lines, max_lines

    def _row_height(cells, header=False):
        _, max_lines = _wraps(cells)
        base = 0.9*cm
        return base if header else max(base, 0.5*cm + max_lines*0.35*cm)

    def draw_row(cells, y, header=False):
        x = 2*cm
        for i, txt in enumerate(cells):
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.5)
            c.rect(x, y-0.8*cm, widths[i], 0.8*cm, stroke=1, fill=0)
            c.setFont("Helvetica-Bold" if header else "Helvetica", 10)
            lines = wrap(str(txt), 40 if i in (1,2,4) else 20)
            max_lines = 2 if not header else 1
            for li, line in enumerate(lines[:max_lines]):
                c.drawString(x+3, y-0.55*cm - li*0.35*cm, line)
            x += widths[i]

    draw_row(headers, y, header=True)
    y -= 0.9*cm

    # sayfa altına yaklaşınca başlık/başlık satırını tekrar bas
    for s in satirlar:
        if y < 2*cm:
            c.showPage()
            y = h - 2*cm
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(w/2, h-2*cm, kurum_adi or baslik)
            c.setFont("Helvetica", 11)
            c.drawString(2*cm, h-2.7*cm, f"Öğrenci: {ogrenci_adsoyad}")
            c.drawString(2*cm, h-3.2*cm, f"Bitiş Tarihi: {bitis_tarihi}")
            if iletisim_satiri:
                c.setFont("Helvetica-Oblique", 9)
                c.drawRightString(w-2*cm, h-3.2*cm, iletisim_satiri)
            y = h - 4*cm
            draw_row(["Ders","Kitap","Konu","Süre (dk)","Açıklama"], y, header=True)
            y -= 0.9*cm
        draw_row([s["ders"], s["kitap"], s["konu"], s.get("sure",""), s.get("aciklama","")], y)
        y -= 0.9*cm

    # İmza alanı
    c.setFont("Helvetica", 10)
    c.drawString(2*cm, 2.5*cm, "Öğrenci İmzası:")
    c.line(5*cm, 2.5*cm, 11*cm, 2.5*cm)
    c.drawString(12*cm, 2.5*cm, "Öğretmen/Koç İmzası:")
    c.line(16*cm, 2.5*cm, 20*cm, 2.5*cm)

    # QR kod (isteğe bağlı ödev linki)
    if qr_link:
        try:
            from reportlab.graphics.barcode import qr
            from reportlab.graphics.shapes import Drawing
            from reportlab.graphics import renderPDF
            q = qr.QrCodeWidget(qr_link)
            b = q.getBounds()
            size = 3*cm
            w_qr = b[2]-b[0]; h_qr = b[3]-b[1]
            d = Drawing(size, size, transform=[size/w_qr,0,0,size/h_qr,0,0])
            d.add(q)
            renderPDF.draw(d, c, w-2*cm-size, 2.8*cm)
            c.setFont("Helvetica", 8)
            c.drawRightString(w-2*cm, 2.4*cm, "Ödeve Git")
        except Exception:
            pass

    c.showPage()
    c.save()
    return dosya
