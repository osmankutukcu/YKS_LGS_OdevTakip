# -*- coding: utf-8 -*-
# progress.py

from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QWidget, QSizePolicy

# ——— İlerleme Penceresi (Standart Pencere) ———
class IlerlemePenceresi(QDialog):
    """
    Standart OS pencere çerçevesi kullanan, sade ve garanti çalışan ilerleme penceresi.
    Güvenli (siyah kutu olmayan) ve sade versiyon.
    """
    def __init__(self, baslik: str | None = None, ebeveyn=None):
        super().__init__(ebeveyn)

        # GÜVENLİ PENCERE (Siyah Kutu Önleyici)
        self.setWindowFlags(
            Qt.WindowType.Dialog 
            | Qt.WindowType.WindowTitleHint 
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Boyutlar (Sabit ve Kararlı)
        self.setFixedWidth(450)
        self.setFixedHeight(150)
        self.setWindowTitle(baslik if baslik else "İşlem Yapılıyor")

        # Stil (Beyaz zemin, Siyah yazı - Sade)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #000000;
                font-size: 14px;
                font-weight: 500;
            }
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                text-align: center;
                background: #f1f5f9;
                color: #000000;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
            }
        """)

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        # Metin
        self.lbl = QLabel("Veriler hazırlanıyor…", self)
        self.lbl.setWordWrap(True)
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Standart Progress Bar
        self.prg = QProgressBar(self)
        self.prg.setRange(0, 100)
        self.prg.setValue(0)
        self.prg.setFixedHeight(25)
        
        root.addWidget(self.lbl)
        root.addWidget(self.prg)

        if baslik:
            self.lbl.setText(baslik)

    def _set_text(self, text: str):
        # Yazı rengini HTML ile de garantiye alalım (eski güvenilir yöntem)
        self.lbl.setText(f"<span style='color:#000000;'>{text}</span>")

    def showEvent(self, e):
        super().showEvent(e)
        self._center()

    def _center(self):
        if self.parent() and getattr(self.parent(), "isVisible", lambda: False)():
            pr = self.parent().frameGeometry()
            my = self.frameGeometry()
            self.move(max(0, pr.center().x() - my.width() // 2),
                      max(0, pr.center().y() - my.height() // 2))
        else:
            self.move(200, 200)

    def guncelle(self, yuzde: int, yazi: str | None = None):
        v = max(0, min(100, int(yuzde)))
        if self.prg.value() != v:
            self.prg.setValue(v)
        
        if yazi:
            self._set_text(yazi)
            if len(yazi) < 30:
                self.setWindowTitle(yazi)

        # Performans için processEvents'i buraya koymuyoruz, çağıran yer (timer) halletsin.

    # Eski çağrılar hata vermesin diye boş metodlar
    def adim_goster(self, yazi): pass
    def log_ekle(self, satir): pass
    def adim_ayarla(self, m, t, e=None): pass

# Geriye dönük uyumluluk
class FlatProgressBar(QProgressBar): pass
class Spinner(QWidget): pass
class BlackPanel(QWidget): pass