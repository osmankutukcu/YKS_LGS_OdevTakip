# -*- coding: utf-8 -*-
"""Actual PDF-page preview; optional fitz dependency, no QPdf dependency."""
from __future__ import annotations
from pathlib import Path


def rasterize_page(pdf_path: str, page_number: int, zoom=1.0) -> tuple[bytes,int]:
    """Return real page PNG + page count. Renderer intentionally never edits PDFs."""
    import fitz
    if not 0.65 <= zoom <= 1.5:
        raise ValueError('Desteklenmeyen yakınlaştırma.')
    with fitz.open(str(pdf_path)) as doc:
        count = doc.page_count
        if not 0 <= page_number < count:
            raise IndexError('Sayfa bulunamadı.')
        rect=doc[page_number].rect
        scale = min(float(zoom) * 1.25, (12_000_000 / max(1, rect.width * rect.height)) ** .5)
        pix = doc[page_number].get_pixmap(matrix=fitz.Matrix(scale,scale), alpha=False)
        return pix.tobytes('png'), count


class PDFPagePreviewDialog:  # Qt imported lazily to avoid requiring Qt for service tests
    def __new__(cls, file_path, parent=None):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                     QPushButton, QScrollArea, QWidget, QMessageBox)
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        if not Path(file_path).is_file():
            raise FileNotFoundError('Önizleme PDF dosyası bulunamadı.')
        dialog = QDialog(parent)
        dialog.setWindowTitle('KoçPilot 360 · Gerçek PDF Sayfa Önizlemesi')
        dialog.resize(880, 810)
        layout = QVBoxLayout(dialog)
        notice = QLabel('Bu görüntü, oluşturulan PDF’nin gerçek sayfasıdır. Yazdırmadan veya paylaşmadan önce kontrol edin.')
        notice.setWordWrap(True)
        layout.addWidget(notice)
        tools = QHBoxLayout()
        back = QPushButton('← Önceki')
        forward = QPushButton('Sonraki →')
        page_lbl = QLabel('')
        tools.addWidget(back); tools.addWidget(page_lbl); tools.addWidget(forward); tools.addStretch()
        zoomout=QPushButton('−'); zoomin=QPushButton('+')
        tools.addWidget(zoomout); tools.addWidget(zoomin)
        layout.addLayout(tools)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        widget=QWidget(); contents=QVBoxLayout(widget)
        pix_label=QLabel(); pix_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        contents.addWidget(pix_label)
        scroll.setWidget(widget)
        layout.addWidget(scroll,1)
        page = [0]; factor=[1.0]; total=[1]
        def paint():
            raw, count=rasterize_page(file_path, page[0], factor[0]); total[0]=count
            pix=QPixmap(); pix.loadFromData(raw, 'PNG'); pix_label.setPixmap(pix)
            page_lbl.setText(f'Sayfa {page[0]+1} / {count}  ·  %{int(factor[0]*100)}')
            back.setEnabled(page[0]>0); forward.setEnabled(page[0]+1<count)
            zoomout.setEnabled(factor[0]>.65); zoomin.setEnabled(factor[0]<1.5)
        def advance(n): page[0]=max(0,min(total[0]-1,page[0]+n)); paint()
        def zoom(n): factor[0]=max(.65,min(1.5, round(factor[0]+n,2))); paint()
        back.clicked.connect(lambda: advance(-1)); forward.clicked.connect(lambda: advance(1))
        zoomout.clicked.connect(lambda: zoom(-.15)); zoomin.clicked.connect(lambda: zoom(.15))
        paint()
        return dialog
