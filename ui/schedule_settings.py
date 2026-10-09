# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, 
    QPushButton, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from utils import settings as appset

class ScheduleSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ders Programı Ayarları")
        self.setFixedSize(350, 250)
        self.setStyleSheet("""
            QDialog { background-color: #f9fafb; }
            QGroupBox { font-weight: bold; border: 1px solid #d1d5db; border-radius: 6px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Saat Aralığı Grubu
        grp_hours = QGroupBox("Zaman Aralığı")
        h_lay = QVBoxLayout(grp_hours)
        h_lay.setSpacing(15)

        # Başlangıç Saati
        row_start = QHBoxLayout()
        row_start.addWidget(QLabel("Başlangıç Saati:"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(5, 12) # 05:00 - 12:00 arası başlayabilir
        self.spin_start.setSuffix(":00")
        row_start.addWidget(self.spin_start)
        h_lay.addLayout(row_start)

        # Bitiş Saati
        row_end = QHBoxLayout()
        row_end.addWidget(QLabel("Bitiş Saati:"))
        self.spin_end = QSpinBox()
        self.spin_end.setRange(18, 24) # 18:00 - 24:00 arası bitebilir
        self.spin_end.setSuffix(":00")
        row_end.addWidget(self.spin_end)
        h_lay.addLayout(row_end)

        layout.addWidget(grp_hours)

        layout.addStretch()

        # Kaydet Butonu
        btn_save = QPushButton("💾 Kaydet ve Uygula")
        btn_save.setStyleSheet("""
            QPushButton { 
                background-color: #2563eb; color: white; font-weight: bold; 
                padding: 10px; border-radius: 6px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

    def _load_settings(self):
        # Varsayılanlar
        try:
            start = int(appset.ayar_get("schedule_start_hour", 9))
            end = int(appset.ayar_get("schedule_end_hour", 21))
        except (ValueError, TypeError):
            start = 9
            end = 21
        
        self.spin_start.setValue(start)
        self.spin_end.setValue(end)

    def _save(self):
        start = self.spin_start.value()
        end = self.spin_end.value()

        if start >= end:
            QMessageBox.warning(self, "Hata", "Başlangıç saati bitiş saatinden küçük olmalıdır.")
            return

        appset.ayar_set("schedule_start_hour", start)
        appset.ayar_set("schedule_end_hour", end)
        
        self.accept()
