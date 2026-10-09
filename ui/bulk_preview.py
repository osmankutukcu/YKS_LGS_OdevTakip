# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

class TopluOnizlemeDialog(QDialog):
    def __init__(self, kayitlar, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Toplu Gönderim Önizleme")
        self.resize(900, 600)
        self.kayitlar = kayitlar

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Gönderilecek kayıtlar (Mesaj sütununu düzenleyebilirsiniz):"))

        self.tab = QTableWidget(len(kayitlar), 3)
        self.tab.setHorizontalHeaderLabels(["Öğrenci ID","Numaralar","Mesaj"])
        for i, k in enumerate(kayitlar):
            self.tab.setItem(i,0, QTableWidgetItem(str(k.get("ogrenci_id",""))))
            self.tab.setItem(i,1, QTableWidgetItem(", ".join(k.get("numaralar",[]))))
            it = QTableWidgetItem(k.get("mesaj",""))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
            self.tab.setItem(i,2, it)
        self.tab.resizeColumnsToContents()
        self.tab.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tab, 1)

        hb = QHBoxLayout()
        self.btnIptal = QPushButton("İptal")
        self.btnGonder = QPushButton("Tümünü Gönder")
        hb.addStretch(1); hb.addWidget(self.btnIptal); hb.addWidget(self.btnGonder)
        lay.addLayout(hb)

        self.btnIptal.clicked.connect(self.reject)
        self.btnGonder.clicked.connect(self.accept)

    def guncel_kayitlar(self):
        out = []
        for i in range(self.tab.rowCount()):
            out.append({
                "ogrenci_id": int(self.tab.item(i,0).text() or 0),
                "numaralar": [n.strip() for n in (self.tab.item(i,1).text() or "").split(",") if n.strip()],
                "mesaj": self.tab.item(i,2).text()
            })
        return out
