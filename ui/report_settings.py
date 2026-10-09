# -*- coding: utf-8 -*-
"""
ui/report_settings.py
Rapor kriterlerini görsel olarak düzenlemeyi sağlayan dialog.
27 kasım
"""

from __future__ import annotations
from typing import Dict, Any
import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QRadioButton, QLabel, QSpinBox, QPushButton,
    QCheckBox, QWidget
)

from services.report_settings import load_settings, save_settings


class ReportSettingsDialog(QDialog):
    """
    Kullanıcıya rapor ayarlarını düzenlettiğimiz pencere.
    """

    def __init__(self, con: sqlite3.Connection, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Rapor Kriterleri")
        self.setModal(True)
        self.con = con
        self.settings: Dict[str, Any] = load_settings(self.con)

        self._build_ui()
        self._load_to_widgets()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)

        # --- Aktarılan ödevler grubu ---
        grp_transfer = QGroupBox("Aktarılan Ödevler Nasıl Sayılsın?")
        v1 = QVBoxLayout(grp_transfer)
        self.rb_transfer_done = QRadioButton("YAPILDI kabul et (tamamlandı say)")
        self.rb_transfer_not_done = QRadioButton("YAPILMADI kabul et (eksik say)")
        v1.addWidget(self.rb_transfer_done)
        v1.addWidget(self.rb_transfer_not_done)
        main.addWidget(grp_transfer)

        # --- Günlük özet aralığı ---
        grp_daily = QGroupBox("Günlük Özet Aralığı")
        h2 = QHBoxLayout(grp_daily)
        lbl_days = QLabel("Son kaç günü analiz etsin:")
        self.spin_days = QSpinBox()
        self.spin_days.setRange(1, 120)
        self.spin_days.setSingleStep(1)
        h2.addWidget(lbl_days)
        h2.addWidget(self.spin_days)
        h2.addStretch()
        main.addWidget(grp_daily)

        # --- Diğer (ileri) ayarlar için placeholder ---
        grp_other = QGroupBox("Diğer Seçenekler (isteğe bağlı)")
        v3 = QVBoxLayout(grp_other)
        self.chk_show_overdue = QCheckBox("Gecikmiş kümeleri raporlarda ayrıca vurgula")
        self.chk_show_overdue.setChecked(True)
        self.chk_show_overdue.setEnabled(False)  # Şimdilik sadece bilgisel
        v3.addWidget(self.chk_show_overdue)
        main.addWidget(grp_other)

        # --- Butonlar ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_ok = QPushButton("Kaydet")
        self.btn_cancel = QPushButton("Vazgeç")
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        main.addLayout(btn_row)

        self.btn_ok.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _load_to_widgets(self) -> None:
        # aktarilan_sayilma_sekli
        mode = self.settings.get("aktarilan_sayilma_sekli", "done")
        if mode == "not_done":
            self.rb_transfer_not_done.setChecked(True)
        else:
            self.rb_transfer_done.setChecked(True)

        # gunluk_son_gun
        try:
            val = int(self.settings.get("gunluk_son_gun", "30"))
        except Exception:
            val = 30
        val = max(1, min(120, val))
        self.spin_days.setValue(val)

    # ---------------- Events ----------------

    def _on_accept(self) -> None:
        data = dict(self.settings)  # mevcutları al

        data["aktarilan_sayilma_sekli"] = (
            "done" if self.rb_transfer_done.isChecked() else "not_done"
        )
        data["gunluk_son_gun"] = str(self.spin_days.value())

        save_settings(self.con, data)
        self.accept()
