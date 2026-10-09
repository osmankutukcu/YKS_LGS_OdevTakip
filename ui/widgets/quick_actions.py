# ui/widgets/quick_actions.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt

class QuickActions(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(8)
        self.btnOdev   = QPushButton("Ödev Takip")
        self.btnRandevu= QPushButton("Hızlı Görüşme")
        self.btnYedek  = QPushButton("Yedek Al")
        self.btnDB     = QPushButton("DB Araçları")
        self.btnTema   = QPushButton("Tema")
        for b in (self.btnOdev, self.btnRandevu, self.btnYedek, self.btnDB, self.btnTema):
            b.setMinimumHeight(36)
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)

        # ana pencerenin metodlarına köprü kur
        main = self._find_main()
        if main:
            self.btnOdev.clicked.connect(main._odev_ac)
            self.btnRandevu.clicked.connect(main._hizli_gorusme)
            self.btnDB.clicked.connect(main._onar_menu)
            self.btnTema.clicked.connect(main._tema_degistir)
            # “Yedek Al” kısa yol
            self.btnYedek.clicked.connect(getattr(main, "_db_quick_backup", lambda: None))

    def _find_main(self):
        w = self.parent()
        while w and w.parent():
            w = w.parent()
        return w