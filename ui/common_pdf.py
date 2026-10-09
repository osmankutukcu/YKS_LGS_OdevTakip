# ui/common_pdf.py (ya da randevu_takvimi.py'nin üst kısmına da koyabilirsin)
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtCore import Qt, QMarginsF
import html

def _html_escape(s):
    return html.escape(str(s if s is not None else ""))

def build_html_table(title: str, subtitle: str, headers: list[str], rows: list[list[str]]) -> str:
    # Basit, okunaklı bir şablon (A4 dikey – kenar boşluğu CSS ile)
    head = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        @page {{ margin: 18mm; }}
        body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; color:#111; }}
        h1 {{ margin:0 0 6px 0; font-size:18pt; }}
        .sub {{ margin:0 0 14px 0; color:#444; font-size:10pt; }}
        table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
        th, td {{ border: 1px solid #cfd8e3; padding: 6px 8px; font-size:10pt; word-wrap: break-word; }}
        th {{ background:#f1f5f9; text-align:left; }}
        tfoot td {{ border:none; padding-top:10px; color:#666; font-size:9pt; }}
      </style>
    </head>
    <body>
      <h1>{_html_escape(title)}</h1>
      <div class="sub">{_html_escape(subtitle)}</div>
      <table>
        <thead><tr>
          {''.join(f'<th>{_html_escape(h)}</th>' for h in headers)}
        </tr></thead>
        <tbody>
          {''.join('<tr>' + ''.join(f'<td>{_html_escape(c)}</td>' for c in row) + '</tr>' for row in rows)}
        </tbody>
      </table>
    """
    tail = """
      <footer>
        <table style="width:100%; margin-top:6mm;">
          <tr>
            <td style="border:none; font-size:9pt; color:#667085;">
              Bu çıktı uygulamadan otomatik oluşturulmuştur.
            </td>
          </tr>
        </table>
      </footer>
    </body></html>"""
    return head + tail

# ui/common_pdf.py

from PyQt6.QtGui import QFont, QTextDocument
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtGui import QTextOption
from PyQt6.QtCore import QSizeF
from PyQt6.QtGui import QPageLayout, QPageSize

def save_html_as_pdf(html: str,
                     path: str,
                     landscape: bool = False,
                     base_font_family: str = "Arial",
                     base_font_point: int = 10) -> None:
    """
    Verilen HTML'yi A4'e ölçekleyip PDF'e yazdırır.
    - Varsayılan font None OLAMAZ; QFont verilmelidir.
    """
    doc = QTextDocument()
    # ❗ HATA ÇÖZÜMÜ: None yerine QFont kullan
    doc.setDefaultFont(QFont(base_font_family, base_font_point))
    doc.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    if landscape:
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)

    # Okunabilirlik için makul kenar boşlukları (mm)
    layout = QPageLayout(printer.pageLayout())
    layout.setMargins(QMarginsF(10.0, 12.0, 10.0, 12.0))
    printer.setPageLayout(layout)

    # Metni sayfa genişliğine göre hizala/katla
    opt = doc.defaultTextOption()
    opt.setWrapMode(QTextOption.WrapMode.WordWrap)
    doc.setDefaultTextOption(opt)

    # Yazdır
    doc.print(printer)