# -*- coding: utf-8 -*-

"""
ui/report_settings_dialog.py
4 aralık
Toplu Değerlendirme ekranı için "Rapor Kriterleri" diyalog kutusu.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QRadioButton, QButtonGroup, QSpinBox, QCheckBox,
    QPushButton, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt

from services import report_settings


class ReportSettingsDialog(QDialog):
    def __init__(self, parent, con):
        super().__init__(parent)
        self.con = con
        self.setWindowTitle("Rapor Kriterleri")
        self.setModal(True)
        self._apply_modern_visuals()
        self._build_ui()
        self._load_from_db()

    def _apply_modern_visuals(self):
        self.setStyleSheet("""
            QDialog { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; background-color: #f9fafb; color: #1f2937; }
            
            QGroupBox {
                border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 24px; background-color: white; padding-top: 20px; font-weight: 600;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; left: 12px; top: 0px; padding: 0 4px; color: #3b82f6; 
            }

            QRadioButton, QCheckBox { spacing: 8px; color: #374151; font-weight: 500; }
            QRadioButton::indicator, QCheckBox::indicator { width: 16px; height: 16px; }
            
            QSpinBox { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 8px; background: white; min-height: 24px; }
            QSpinBox:focus { border: 2px solid #3b82f6; }
            
            /* Buttons */
            QPushButton { border-radius: 6px; padding: 6px 16px; font-weight: 600; background: white; border: 1px solid #d1d5db; color: #374151; }
            QPushButton:hover { background: #f3f4f6; border-color: #9ca3af; }
            
            QPushButton#btnPrimary { background-color: #2563eb; color: white; border: 1px solid #2563eb; }
            QPushButton#btnPrimary:hover { background-color: #1d4ed8; border-color: #1d4ed8; }
            
            QPushButton#btnCancel { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
            QPushButton#btnCancel:hover { background-color: #fecaca; }
        """)

    # ----------------- UI -----------------
    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(16)

        # 1) Aktarılan ödevler nasıl sayılsın?
        grp_transfer = QGroupBox("Aktarılan Ödevler Nasıl Sayılsın?")
        v1 = QVBoxLayout(grp_transfer)
        v1.setSpacing(8)
        v1.setContentsMargins(12, 12, 12, 12)

        self.rad_done = QRadioButton("YAPILDI kabul et (tamamlandı say)")
        self.rad_not_done = QRadioButton("YAPILMADI kabul et (eksik say)")

        bg = QButtonGroup(self)
        bg.setExclusive(True)
        bg.addButton(self.rad_done)
        bg.addButton(self.rad_not_done)

        v1.addWidget(self.rad_done)
        v1.addWidget(self.rad_not_done)

        # 2) Günlük özet aralığı
        grp_days = QGroupBox("Günlük Özet Aralığı")
        h2 = QHBoxLayout(grp_days)
        h2.setSpacing(12)
        h2.setContentsMargins(12, 12, 12, 12)

        lab = QLabel("Son kaç günü analiz etsin:")
        self.spn_days = QSpinBox()
        self.spn_days.setRange(1, 365)
        self.spn_days.setValue(30)
        self.spn_days.setSuffix(" gün")
        self.spn_days.setFixedWidth(100)

        h2.addWidget(lab)
        h2.addWidget(self.spn_days)
        h2.addStretch()

        # 3) Diğer seçenekler
        grp_other = QGroupBox("Diğer Seçenekler (isteğe bağlı)")
        v3 = QVBoxLayout(grp_other)
        v3.setContentsMargins(12, 12, 12, 12)
        
        self.chk_gecikmis = QCheckBox("Gecikmiş kümeleri raporlarda ayrıca vurgula")
        self.chk_gecikmis.setTristate(False)

        v3.addWidget(self.chk_gecikmis)

        main.addWidget(grp_transfer)
        main.addWidget(grp_days)
        main.addWidget(grp_other)

        main.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Alt butonlar
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("❌ Vazgeç")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.btn_ok = QPushButton("💾 Kaydet")
        self.btn_ok.setObjectName("btnPrimary")
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_ok.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)
        
        main.addLayout(btn_row)

        self.resize(450, 480)

    # ----------------- DB <-> UI -----------------
    def _load_from_db(self):
        s = report_settings.load_settings(self.con)

        aktarilan = s.get("aktarilan_sayilma_sekli", "done")
        if aktarilan == "not_done":
            self.rad_not_done.setChecked(True)
        else:
            self.rad_done.setChecked(True)

        try:
            days = int(s.get("gunluk_son_gun", "30"))
        except (TypeError, ValueError):
            days = 30
        self.spn_days.setValue(days)

        gecikmis = s.get("gecikmis_kume_vurgula", "1")
        self.chk_gecikmis.setChecked(str(gecikmis) == "1")

    def _on_accept(self):
        aktarilan = "done" if self.rad_done.isChecked() else "not_done"
        days = self.spn_days.value()
        gecikmis = "1" if self.chk_gecikmis.isChecked() else "0"

        report_settings.save_settings(
            self.con,
            {
                "aktarilan_sayilma_sekli": aktarilan,
                "gunluk_son_gun": str(days),
                "gecikmis_kume_vurgula": gecikmis,
            },
        )
        self.accept()
