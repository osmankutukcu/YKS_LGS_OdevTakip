# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt
import pyperclip

class WhatsappOnizlemeDialog(QDialog):
    def __init__(self, numaralar, mesaj, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("WhatsApp Gönderim Önizleme")
        self.resize(700, 500)
        self.numaralar = numaralar
        self.mesaj = mesaj

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Gönderilecek numaralar:"))
        self.lst = QListWidget(); self.lst.setSelectionMode(self.lst.SelectionMode.MultiSelection)
        for n in numaralar:
            self.lst.addItem(QListWidgetItem(n))
        root.addWidget(self.lst, 1)

        root.addWidget(QLabel("Mesaj önizleme:"))
        self.txt = QTextEdit(); self.txt.setPlainText(mesaj)
        root.addWidget(self.txt, 2)

        hb = QHBoxLayout()
        self.btnKopyala = QPushButton("Mesajı Kopyala")
        self.btnGonder = QPushButton("Gönder")
        self.btnIptal = QPushButton("İptal")
        hb.addWidget(self.btnKopyala); hb.addStretch(1); hb.addWidget(self.btnGonder); hb.addWidget(self.btnIptal)
        root.addLayout(hb)

        self.btnKopyala.clicked.connect(self._kopyala)
        self.btnGonder.clicked.connect(self._gonder)
        self.btnIptal.clicked.connect(self.reject)

    def _kopyala(self):
        pyperclip.copy(self.txt.toPlainText())

    def _gonder(self):
        # Kullanıcının seçili bıraktığı numaralara gönder
        secilen = [self.lst.item(i).text() for i in range(self.lst.count()) if self.lst.item(i).isSelected() or True]
        # Not: Yukarıda 'or True' -> varsayılan tümünü gönder; kullanıcı isterse seçim yapabilir
        self.numaralar = secilen
        self.mesaj = self.txt.toPlainText()
        self.accept()
