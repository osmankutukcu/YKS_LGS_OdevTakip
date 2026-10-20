# -*- coding: utf-8 -*-
"""Modern, compact, and intuitive Homework Save Mode Dialog.

Replaces the legacy raw radio-box modal with a sleek, card-based responsive design:
- 100% preserves return format: {'mode': 'yeni'|'ekle', 'kume_id': int|None, 'bitis_guncelle': bool, 'bitis_tarihi': str|None}
- Explains clearly what 'Yeni Küme' vs 'Var Olana Ekle' does in teacher-friendly terms.
- Compact macOS Ventura/Sonoma card layout, zero wasted vertical space.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import db


class ModernSaveModeDialog(QDialog):
    """Compact and modern modal for choosing homework saving cluster mode."""

    def __init__(self, parent: Optional[QWidget], ogr_id: int, initial_date: Optional[QDate] = None):
        super().__init__(parent)
        self.ogr_id = int(ogr_id)
        self.initial_date = initial_date or QDate.currentDate()
        self.selected_mode = "yeni"  # 'yeni' or 'ekle'

        self.setWindowTitle("Ödev Kayıt Seçenekleri")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setFixedWidth(430)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
        """)

        self._build_ui()
        self._load_clusters()
        self._update_cards_state()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)

        # 1. Header (Modern Badged Icon + Clear Title)
        header = QHBoxLayout()
        header.setSpacing(12)

        badge_lbl = QLabel("📋")
        badge_lbl.setFixedSize(44, 44)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #3730a3);
                color: #ffffff;
                font-size: 22px;
                border-radius: 10px;
            }
        """)
        header.addWidget(badge_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("Ödev Kayıt Seçenekleri")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #0f172a;")
        desc_lbl = QLabel("Verilen ödevler sisteme nasıl kaydedilsin?")
        desc_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(desc_lbl)
        header.addLayout(title_col, 1)

        root.addLayout(header)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("border: none; background-color: #f1f5f9; height: 1px;")
        root.addWidget(div)

        # 2. Interactive Selection Cards
        self.cardYeni = QFrame()
        self.cardYeni.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cardYeni.mousePressEvent = lambda e: self._set_mode("yeni")
        card1_layout = QHBoxLayout(self.cardYeni)
        card1_layout.setContentsMargins(14, 12, 14, 12)
        card1_layout.setSpacing(12)

        icon1 = QLabel("✨")
        icon1.setFixedSize(32, 32)
        icon1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon1.setStyleSheet("background: #eef2ff; border-radius: 8px; font-size: 16px;")
        card1_layout.addWidget(icon1)

        c1_text = QVBoxLayout()
        c1_text.setSpacing(1)
        self.lblTitleYeni = QLabel("Yeni Ödev Paketi Oluştur (Önerilen)")
        self.lblTitleYeni.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e1b4b;")
        lblDescYeni = QLabel("Ödevleri bağımsız yeni bir haftalık liste olarak kaydeder.")
        lblDescYeni.setStyleSheet("font-size: 11px; color: #64748b;")
        c1_text.addWidget(self.lblTitleYeni)
        c1_text.addWidget(lblDescYeni)
        card1_layout.addLayout(c1_text, 1)

        self.radioYeni = QLabel("●")
        self.radioYeni.setStyleSheet("font-size: 18px; color: #4f46e5;")
        card1_layout.addWidget(self.radioYeni)

        root.addWidget(self.cardYeni)

        # Card 2: Mevcut Kümeye Ekle
        self.cardEkle = QFrame()
        self.cardEkle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cardEkle.mousePressEvent = lambda e: self._set_mode("ekle")
        card2_col = QVBoxLayout(self.cardEkle)
        card2_col.setContentsMargins(14, 12, 14, 12)
        card2_col.setSpacing(8)

        c2_head = QHBoxLayout()
        c2_head.setSpacing(12)
        icon2 = QLabel("📂")
        icon2.setFixedSize(32, 32)
        icon2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon2.setStyleSheet("background: #f1f5f9; border-radius: 8px; font-size: 16px;")
        c2_head.addWidget(icon2)

        c2_text = QVBoxLayout()
        c2_text.setSpacing(1)
        self.lblTitleEkle = QLabel("Mevcut Pakete / Kümeye Ekle")
        self.lblTitleEkle.setStyleSheet("font-size: 13px; font-weight: 600; color: #334155;")
        lblDescEkle = QLabel("Öğrencinin açık olan son ödev listesine ilave eder.")
        lblDescEkle.setStyleSheet("font-size: 11px; color: #64748b;")
        c2_text.addWidget(self.lblTitleEkle)
        c2_text.addWidget(lblDescEkle)
        c2_head.addLayout(c2_text, 1)

        self.radioEkle = QLabel("○")
        self.radioEkle.setStyleSheet("font-size: 18px; color: #94a3b8;")
        c2_head.addWidget(self.radioEkle)
        card2_col.addLayout(c2_head)

        # Cluster dropdown (inside card 2)
        self.cmbKume = QComboBox()
        self.cmbKume.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                color: #1e293b;
            }
            QComboBox:disabled {
                background: #f8fafc;
                color: #94a3b8;
                border-color: #e2e8f0;
            }
        """)
        card2_col.addWidget(self.cmbKume)

        root.addWidget(self.cardEkle)

        # 3. Compact Date Section
        date_bar = QFrame()
        date_bar.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        date_layout = QHBoxLayout(date_bar)
        date_layout.setContentsMargins(12, 8, 12, 8)
        date_layout.setSpacing(10)

        self.chkBitis = QCheckBox("📅 Bitiş Tarihini Güncelle")
        self.chkBitis.setStyleSheet("font-size: 12px; font-weight: 500; color: #334155;")
        self.chkBitis.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        date_layout.addWidget(self.chkBitis)

        date_layout.addStretch(1)

        self.dtBitis = QDateEdit()
        self.dtBitis.setCalendarPopup(True)
        self.dtBitis.setDate(self.initial_date)
        self.dtBitis.setEnabled(False)
        self.dtBitis.setStyleSheet("""
            QDateEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 600;
                color: #1e293b;
            }
            QDateEdit:disabled {
                background: #f1f5f9;
                color: #94a3b8;
                border-color: #e2e8f0;
            }
        """)
        self.chkBitis.toggled.connect(self.dtBitis.setEnabled)
        date_layout.addWidget(self.dtBitis)

        root.addWidget(date_bar)

        # 4. Actions Footer
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 4, 0, 0)
        btn_bar.setSpacing(10)

        btn_bar.addStretch(1)

        self.btnCancel = QPushButton("Vazgeç")
        self.btnCancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnCancel.setStyleSheet("""
            QPushButton {
                padding: 8px 18px;
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                color: #475569;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
        """)
        self.btnCancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btnCancel)

        self.btnOk = QPushButton("Kaydet")
        self.btnOk.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnOk.setStyleSheet("""
            QPushButton {
                padding: 8px 24px;
                background-color: #4f46e5;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
        """)
        self.btnOk.clicked.connect(self.accept)
        btn_bar.addWidget(self.btnOk)

        root.addLayout(btn_bar)

    def _set_mode(self, mode: str):
        self.selected_mode = mode
        self._update_cards_state()

    def _update_cards_state(self):
        is_yeni = (self.selected_mode == "yeni")
        if is_yeni:
            self.cardYeni.setStyleSheet("""
                QFrame {
                    background-color: #f5f7ff;
                    border: 2px solid #4f46e5;
                    border-radius: 10px;
                }
            """)
            self.cardEkle.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                }
                QFrame:hover {
                    border-color: #cbd5e1;
                    background-color: #f8fafc;
                }
            """)
            self.radioYeni.setText("●")
            self.radioYeni.setStyleSheet("font-size: 18px; color: #4f46e5;")
            self.radioEkle.setText("○")
            self.radioEkle.setStyleSheet("font-size: 18px; color: #94a3b8;")
            self.cmbKume.setEnabled(False)
            self.lblTitleYeni.setStyleSheet("font-size: 13px; font-weight: 700; color: #3730a3;")
            self.lblTitleEkle.setStyleSheet("font-size: 13px; font-weight: 600; color: #64748b;")
        else:
            self.cardEkle.setStyleSheet("""
                QFrame {
                    background-color: #f5f7ff;
                    border: 2px solid #4f46e5;
                    border-radius: 10px;
                }
            """)
            self.cardYeni.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                }
                QFrame:hover {
                    border-color: #cbd5e1;
                    background-color: #f8fafc;
                }
            """)
            self.radioEkle.setText("●")
            self.radioEkle.setStyleSheet("font-size: 18px; color: #4f46e5;")
            self.radioYeni.setText("○")
            self.radioYeni.setStyleSheet("font-size: 18px; color: #94a3b8;")
            self.cmbKume.setEnabled(True)
            self.lblTitleEkle.setStyleSheet("font-size: 13px; font-weight: 700; color: #3730a3;")
            self.lblTitleYeni.setStyleSheet("font-size: 13px; font-weight: 600; color: #64748b;")

    def _load_clusters(self):
        try:
            con = db.get_conn()
            rows = con.execute(
                "SELECT id, verilis_tarihi, bitis_tarihi FROM odev_kume "
                "WHERE ogrenci_id=? ORDER BY id DESC LIMIT 30",
                (self.ogr_id,),
            ).fetchall()
            for r in rows:
                txt = f"📦 Küme #{r['id']}  (Veriliş: {r['verilis_tarihi'] or '-'} → Bitiş: {r['bitis_tarihi'] or '-'})"
                self.cmbKume.addItem(txt, int(r["id"]))
        except Exception:
            pass

        if self.cmbKume.count() == 0:
            self.cmbKume.addItem("Bu öğrencinin kayıtlı kümesi yok", None)
            self.cardEkle.setEnabled(False)

    def get_result(self) -> Optional[Dict[str, Any]]:
        """Returns dialog decision dictionary or None if rejected."""
        if self.result() != QDialog.DialogCode.Accepted:
            return None
        is_ekle = (self.selected_mode == "ekle")
        return {
            "mode": "ekle" if is_ekle else "yeni",
            "kume_id": self.cmbKume.currentData() if is_ekle else None,
            "bitis_guncelle": self.chkBitis.isChecked(),
            "bitis_tarihi": self.dtBitis.date().toString("yyyy-MM-dd") if self.chkBitis.isChecked() else None,
        }


def show_modern_save_mode_dialog(parent: QWidget, ogr_id: int) -> Optional[Dict[str, Any]]:
    """Safe drop-in replacement helper for OdevTakipFormu._kume_kaydet_modu_secimi."""
    initial_date = None
    try:
        if hasattr(parent, "dtpBitis"):
            initial_date = parent.dtpBitis.date()
    except Exception:
        pass

    dlg = ModernSaveModeDialog(parent, ogr_id, initial_date=initial_date)
    dlg.exec()
    return dlg.get_result()
