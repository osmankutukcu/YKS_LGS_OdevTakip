# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, 
    QPushButton, QGroupBox, QMessageBox, QPlainTextEdit, QComboBox
)
from PyQt6.QtCore import Qt
from utils import settings as appset

class ScheduleSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ders Programı Saat ve Zaman Ayarları")
        self.resize(440, 480)
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; font-family: sans-serif; }
            QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 10px; background: white; padding: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #1e3a8a; }
        """)
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # Şablon Seçici
        h_tpl = QHBoxLayout()
        h_tpl.addWidget(QLabel("<b>Hızlı Saat Şablonu:</b>"))
        self.cmb_tpl = QComboBox()
        self.cmb_tpl.addItems([
            "-- Hazır Şablon Seç --",
            "Standart Saatlik (09:00 - 22:00)",
            "Erken Başlangıç (08:00 - 23:00)",
            "Okul / 40 Dk Ders & Teneffüs",
            "Etüt / 45 Dk Bloklar",
            "Akşam Etüdü (16:00 - 23:00)"
        ])
        self.cmb_tpl.currentIndexChanged.connect(self._apply_preset_template)
        h_tpl.addWidget(self.cmb_tpl)
        layout.addLayout(h_tpl)

        # Özel Saat Listesi Grubu
        grp_slots = QGroupBox("Program Saat Dilimleri (Her Satıra Bir Saat)")
        v_slots = QVBoxLayout(grp_slots)
        v_slots.setSpacing(6)
        
        lbl_hint = QLabel("Aşağıdaki saatleri dilediğiniz gibi düzenleyebilir, yeni satır ekleyip silebilirsiniz:")
        lbl_hint.setStyleSheet("font-size: 11px; color: #64748b; font-weight: normal;")
        v_slots.addWidget(lbl_hint)

        self.txt_slots = QPlainTextEdit()
        self.txt_slots.setPlaceholderText("Örnek:\n08:30 - 09:15\n09:25 - 10:10\n...")
        self.txt_slots.setStyleSheet("""
            QPlainTextEdit {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
                font-family: monospace;
            
                color: #15191E;}
            QPlainTextEdit:focus { border-color: #3b82f6; background: white; }
        """)
        v_slots.addWidget(self.txt_slots)

        layout.addWidget(grp_slots, 1)

        # Butonlar
        btn_bar = QHBoxLayout()
        btn_reset = QPushButton("↺ Varsayılana Dön")
        btn_reset.setStyleSheet("""
            QPushButton {
                background: #f1f5f9; color: #475569; font-weight: 600;
                padding: 8px 12px; border-radius: 6px; border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background: #e2e8f0; 
                color: #15191E;}
        """)
        btn_reset.clicked.connect(self._reset_defaults)
        btn_bar.addWidget(btn_reset)

        btn_bar.addStretch()

        btn_save = QPushButton("💾 Kaydet ve Tabloya Uygula")
        btn_save.setStyleSheet("""
            QPushButton { 
                background-color: #2563eb; color: white; font-weight: bold; 
                padding: 8px 18px; border-radius: 6px; border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; 
                color: #FFFFFF;}
        """)
        btn_save.clicked.connect(self._save)
        btn_bar.addWidget(btn_save)

        layout.addLayout(btn_bar)

    def _load_settings(self):
        custom = appset.ayar_get("schedule_custom_slots", "")
        if custom and custom.strip():
            self.txt_slots.setPlainText(custom.strip())
        else:
            try:
                start = int(appset.ayar_get("schedule_start_hour", 9))
                end = int(appset.ayar_get("schedule_end_hour", 21))
            except (ValueError, TypeError):
                start = 9
                end = 21
            default_slots = [f"{h:02d}:00" for h in range(start, end + 1)]
            self.txt_slots.setPlainText("\n".join(default_slots))

    def _apply_preset_template(self, idx):
        if idx == 1: # Standart
            slots = [f"{h:02d}:00" for h in range(9, 23)]
        elif idx == 2: # Erken
            slots = [f"{h:02d}:00" for h in range(8, 24)]
        elif idx == 3: # Okul 40 dk
            slots = [
                "08:30 - 09:10 (1. Ders)",
                "09:20 - 10:00 (2. Ders)",
                "10:10 - 10:50 (3. Ders)",
                "11:00 - 11:40 (4. Ders)",
                "11:50 - 12:30 (5. Ders)",
                "12:30 - 13:20 (Öğle Molası)",
                "13:20 - 14:00 (6. Ders)",
                "14:10 - 14:50 (7. Ders)",
                "15:00 - 15:40 (8. Ders)",
                "16:30 - 17:30 (Etüt 1)",
                "18:00 - 19:00 (Etüt 2)",
                "19:30 - 20:30 (Etüt 3)",
                "21:00 - 22:00 (Serbest Okuma)"
            ]
        elif idx == 4: # Etüt 45 dk
            slots = [
                "09:00 - 09:45 (Blok 1)",
                "10:00 - 10:45 (Blok 2)",
                "11:00 - 11:45 (Blok 3)",
                "12:00 - 13:00 (Öğle Molası)",
                "13:00 - 13:45 (Blok 4)",
                "14:00 - 14:45 (Blok 5)",
                "15:00 - 15:45 (Blok 6)",
                "16:30 - 17:15 (Blok 7)",
                "17:30 - 18:15 (Blok 8)",
                "19:00 - 20:00 (Akşam Tekrarı)",
                "20:30 - 21:30 (Soru Çözümü)",
                "22:00 - 22:45 (Gün Sonu Değerlendirme)"
            ]
        elif idx == 5: # Akşam Etüdü
            slots = [f"{h:02d}:00" for h in range(16, 24)]
        else:
            return
        self.txt_slots.setPlainText("\n".join(slots))

    def _reset_defaults(self):
        default_slots = [f"{h:02d}:00" for h in range(9, 23)]
        self.txt_slots.setPlainText("\n".join(default_slots))

    def _save(self):
        raw = self.txt_slots.toPlainText().strip()
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            QMessageBox.warning(self, "Hata", "Lütfen en az bir saat satırı giriniz.")
            return

        appset.ayar_set("schedule_custom_slots", "\n".join(lines))
        self.accept()
