# -*- coding: utf-8 -*-
# ui/widgets/tabbar_wrap.py
from PyQt6.QtWidgets import QTabBar, QLabel
from PyQt6.QtCore import Qt

class CokSatirliTabBar(QTabBar):
    """
    Güvenli çok satır başlık: QPainter kullanılmaz.
    Her sekmeye wordWrap açık QLabel yerleştirir.
    """
    def __init__(self, parent=None, max_width_px=220):
        super().__init__(parent)
        self._max_width = max_width_px
        self.setElideMode(Qt.TextElideMode.ElideNone)  # metni kesme
        self.setExpanding(False)                       # doğal genişlik
        self.setDrawBase(True)

    def _ensure_label(self, index: int):
        # Sağ taraf butonu yerine bir QLabel koyup metni sığdırıyoruz
        w = self.tabButton(index, QTabBar.ButtonPosition.RightSide)
        if not isinstance(w, QLabel):
            lab = QLabel(self)
            lab.setWordWrap(True)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            lab.setFixedWidth(self._max_width)
            # RightSide'a yerleştir (LeftSide da olur, biri yeterli)
            self.setTabButton(index, QTabBar.ButtonPosition.RightSide, lab)
            return lab
        return w

    def setTabText(self, index: int, text: str):
        super().setTabText(index, text)
        lab = self._ensure_label(index)
        # Alt satıra inmesi için boşluk/alt tirelere göre kendisi sarar
        lab.setText(text.replace("_", " "))

    def tabInserted(self, index: int):
        super().tabInserted(index)
        self._ensure_label(index)

    def tabRemoved(self, index: int):
        super().tabRemoved(index)

    # Stil ile biraz boşluk
    def minimumTabSizeHint(self, index: int):
        s = super().minimumTabSizeHint(index)
        # bir miktar yükseklik (2 satır için)
        s.setHeight(max(s.height(), 44))
        return s