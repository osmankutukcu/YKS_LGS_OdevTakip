from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from datetime import datetime

def export_plan_pdf(path, plan_text, kurum_adi='', egitim_kocu='', logo_path=None, ogrenci_bilgi=None, qr_text=None):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 2*cm

    # Logo
    if logo_path:
        try:
            img = ImageReader(logo_path)
            c.drawImage(img, 2*cm, h-3*cm, width=3*cm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Başlık ve üst bilgi
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(w/2, h-1.5*cm, 'Haftalık Çalışma Planı')

    c.setFont('Helvetica', 9)
    if kurum_adi:
        c.drawRightString(w-2*cm, h-1.2*cm, kurum_adi)

    c.setFont('Helvetica-Oblique', 9)
    c.drawRightString(w-2*cm, h-1.7*cm, datetime.now().strftime('%Y-%m-%d %H:%M'))

    if egitim_kocu:
        c.setFont('Helvetica-Oblique', 10)
        c.drawRightString(w-2*cm, h-2.2*cm, f'Eğitim Koçu: {egitim_kocu}')

    # Öğrenci bilgisi
    if ogrenci_bilgi:
        c.setFont('Helvetica', 10)
        c.drawString(2*cm, h-2.6*cm, ogrenci_bilgi)

    # QR
    if qr_text:
        try:
            code = qr.QrCodeWidget(qr_text)
            b = code.getBounds()
            w_qr = 2.6*cm
            h_qr = 2.6*cm
            scale_x = w_qr / (b[2] - b[0])
            scale_y = h_qr / (b[3] - b[1])
            d = Drawing(w_qr, h_qr)
            d.add(code)
            d.transform = (scale_x, 0, 0, scale_y, 0, 0)
            renderPDF.draw(d, c, A4[0] - (2*cm + w_qr), h - 3.2*cm)
        except Exception:
            pass

    # Metin gövdesi
    c.setFont('Helvetica', 11)
    left = 2*cm
    right = w - 2*cm
    width = right - left
    line_h = 14

    for line in plan_text.splitlines():
        # Basit sarma: yaklaşık karakter/px hesabı (gerekirse geliştirilebilir)
        while c.stringWidth(line, 'Helvetica', 11) > width:
            # genişliğe sığacak kesim
            cut = len(line)
            # ikili arama yerine küçük adımlarla kısaltalım
            while cut > 0 and c.stringWidth(line[:cut], 'Helvetica', 11) > width:
                cut -= 1
            if cut <= 0:
                break
            c.drawString(left, y, line[:cut])
            y -= line_h
            line = line[cut:]
            if y < 3*cm:
                c.showPage()
                c.setFont('Helvetica', 11)
                y = h - 2*cm
        if line:
            c.drawString(left, y, line)
            y -= line_h
            if y < 3*cm:
                c.showPage()
                c.setFont('Helvetica', 11)
                y = h - 2*cm

    # İmza alanı
    c.setFont('Helvetica', 10)
    c.drawString(2*cm, 2.5*cm, 'Veli/Öğrenci İmzası: __________________________')

    c.save()
    return path
