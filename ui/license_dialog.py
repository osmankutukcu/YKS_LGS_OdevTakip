# -*- coding: utf-8 -*-
"""
YKS-LGS Ödev & Takip Yöneticisi
Modern Lisans Aktivasyon İletişim Kutusu (License Dialog)
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QFrame, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor

from utils.license_manager import manager


class LicenseDialog(QDialog):
    def __init__(self, parent=None, can_cancel=True):
        super().__init__(parent)
        self.can_cancel = can_cancel
        self.setWindowTitle("Lisans Aktivasyonu - YKS/LGS Ödev Takip")
        self.setFixedWidth(520)
        
        # Pencere Bayrakları (Her zaman en önde ve görünür)
        if not can_cancel:
            self.setWindowFlags(
                Qt.WindowType.Dialog 
                | Qt.WindowType.WindowStaysOnTopHint 
                | Qt.WindowType.WindowCloseButtonHint
            )
        else:
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)

        self._load_status()
        self._init_ui()
        self._apply_styling()
        self._center_on_screen()

    def _load_status(self):
        self.status = manager.check_status()
        self.machine_id = self.status.get("machine_id", "")
        self.status_msg = self.status.get("message", "")
        self.is_valid = (self.status.get("status") == "valid")
        self.is_licensed = self.status.get("is_license", False)

    def _center_on_screen(self):
        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            geo = primary_screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(14)
        
        # 1. Header Banner
        header_frame = QFrame()
        header_frame.setObjectName("headerCard")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(16, 12, 16, 12)
        h_layout.setSpacing(14)
        
        icon_lbl = QLabel("🛡️")
        icon_lbl.setStyleSheet("font-size: 32px; background: transparent;")
        h_layout.addWidget(icon_lbl)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        t1 = QLabel("Lisans Aktivasyonu")
        t1.setStyleSheet("color: #ffffff; font-size: 17px; font-weight: bold; background: transparent;")
        t2 = QLabel("YKS-LGS Ödev & Takip Yönetim Sistemi v2")
        t2.setStyleSheet("color: #94a3b8; font-size: 12px; background: transparent;")
        text_layout.addWidget(t1)
        text_layout.addWidget(t2)
        h_layout.addLayout(text_layout)
        h_layout.addStretch()
        
        main_layout.addWidget(header_frame)
        
        # 2. Status Alert Box
        alert_frame = QFrame()
        alert_frame.setObjectName("alertFrame")
        
        if not self.is_valid:
            alert_frame.setStyleSheet("""
                QFrame#alertFrame {
                    background-color: #fef2f2;
                    border: 1px solid #fecaca;
                    border-radius: 8px;
                }
            """)
            alert_icon = "⚠️"
            alert_color = "#991b1b"
            alert_title = f"Lisans Gerekli: {self.status_msg}"
            alert_desc = "Kullanıma devam etmek için lütfen geçerli lisans anahtarınızı giriniz."
        elif not self.is_licensed:
            alert_frame.setStyleSheet("""
                QFrame#alertFrame {
                    background-color: #eff6ff;
                    border: 1px solid #bfdbfe;
                    border-radius: 8px;
                }
            """)
            alert_icon = "⏳"
            alert_color = "#1e40af"
            days_left = self.status.get("days_left", 14)
            alert_title = f"14 Günlük Deneme Sürümü Aktif ({days_left} Gün Kaldı)"
            alert_desc = "Tam lisansa yükseltmek için aşağıdaki alana lisans anahtarınızı girebilirsiniz."
        else:
            alert_frame.setStyleSheet("""
                QFrame#alertFrame {
                    background-color: #f0fdf4;
                    border: 1px solid #bbf7d0;
                    border-radius: 8px;
                }
            """)
            alert_icon = "✅"
            alert_color = "#166534"
            alert_title = f"Lisans Aktif: {self.status_msg}"
            alert_desc = "Sistem lisansınız başarıyla doğrulanmıştır."
            
        alert_layout = QHBoxLayout(alert_frame)
        alert_layout.setContentsMargins(12, 10, 12, 10)
        alert_layout.setSpacing(10)
        
        a_icon = QLabel(alert_icon)
        a_icon.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        alert_layout.addWidget(a_icon)
        
        a_text_box = QVBoxLayout()
        a_text_box.setSpacing(2)
        a_t1 = QLabel(alert_title)
        a_t1.setStyleSheet(f"color: {alert_color}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
        a_t2 = QLabel(alert_desc)
        a_t2.setStyleSheet("color: #475569; font-size: 11px; background: transparent; border: none;")
        a_text_box.addWidget(a_t1)
        a_text_box.addWidget(a_t2)
        alert_layout.addLayout(a_text_box)
        alert_layout.addStretch()
        
        main_layout.addWidget(alert_frame)
        
        # 3. Machine ID Box
        mid_label = QLabel("Bilgisayar Makine Kimliği (Hardware ID):")
        mid_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155;")
        main_layout.addWidget(mid_label)
        
        mid_frame = QFrame()
        mid_frame.setObjectName("midFrame")
        mid_h = QHBoxLayout(mid_frame)
        mid_h.setContentsMargins(10, 4, 6, 4)
        mid_h.setSpacing(8)
        
        self.txt_mid = QLineEdit(self.machine_id)
        self.txt_mid.setReadOnly(True)
        self.txt_mid.setStyleSheet("""
            QLineEdit {
                border: none;
                font-family: Consolas, 'SF Mono', Menlo, Monaco, monospace;
                font-size: 15px;
                font-weight: bold;
                color: #0369a1;
                background: transparent;
                padding: 4px;
                letter-spacing: 1px;
            }
        """)
        mid_h.addWidget(self.txt_mid)
        
        self.btn_copy = QPushButton("📋 Kopyala")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setObjectName("btnCopy")
        self.btn_copy.clicked.connect(self._copy_mid)
        mid_h.addWidget(self.btn_copy)
        
        main_layout.addWidget(mid_frame)
        
        mid_hint = QLabel("💡 Yeni lisans anahtarı oluşturulması için yukarıdaki kodu yöneticinize iletiniz.")
        mid_hint.setStyleSheet("font-size: 11px; color: #64748b; margin-top: 0px;")
        main_layout.addWidget(mid_hint)
        
        # 4. License Key Input Box
        key_label = QLabel("Lisans Anahtarı:")
        key_label.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155; margin-top: 4px;")
        main_layout.addWidget(key_label)
        
        self.txt_key = QTextEdit()
        self.txt_key.setPlaceholderText("Size verilen lisans anahtarını buraya yapıştırınız...")
        self.txt_key.setFixedHeight(75)
        self.txt_key.setStyleSheet("""
            QTextEdit {
                font-family: Consolas, 'SF Mono', Menlo, Monaco, monospace;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        main_layout.addWidget(self.txt_key)
        
        # Paste shortcut button row
        paste_row = QHBoxLayout()
        btn_paste = QPushButton("📋 Panodan Yapıştır")
        btn_paste.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_paste.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #2563eb;
                border: none;
                font-size: 12px;
                font-weight: 600;
                text-align: left;
                padding: 2px 4px;
            }
            QPushButton:hover {
                color: #1d4ed8;
                text-decoration: underline;
            }
        """)
        btn_paste.clicked.connect(self._paste_key)
        paste_row.addWidget(btn_paste)
        paste_row.addStretch()
        main_layout.addLayout(paste_row)
        
        # 5. Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(0, 6, 0, 0)
        
        self.btn_activate = QPushButton("🚀 Lisansı Aktifleştir")
        self.btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_activate.setObjectName("btnActivate")
        self.btn_activate.clicked.connect(self._activate)
        btn_layout.addWidget(self.btn_activate, stretch=2)
        
        if self.can_cancel:
            self.btn_close = QPushButton("Kapat")
            self.btn_close.setObjectName("btnClose")
            self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_close.clicked.connect(self.reject)
            btn_layout.addWidget(self.btn_close, stretch=1)
        else:
            self.btn_quit = QPushButton("✖ Çıkış")
            self.btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_quit.setObjectName("btnQuit")
            self.btn_quit.clicked.connect(self._quit_app)
            btn_layout.addWidget(self.btn_quit, stretch=1)
            
        main_layout.addLayout(btn_layout)

    def _apply_styling(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QFrame#headerCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e293b);
                border-radius: 12px;
            }
            QFrame#midFrame {
                background-color: #ffffff;
                border: 1.5px solid #e2e8f0;
                border-radius: 8px;
            }
            QLineEdit, QTextEdit {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
                color: #0f172a;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #3b82f6;
            }
            QPushButton#btnCopy {
                background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#btnCopy:hover {
                background-color: #e2e8f0;
            }
            QPushButton#btnActivate {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 8px;
            }
            QPushButton#btnActivate:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
            }
            QPushButton#btnActivate:pressed {
                background: #1e40af;
            }
            QPushButton#btnClose {
                background-color: #e2e8f0;
                color: #334155;
                border: 1px solid #cbd5e1;
                padding: 12px 18px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton#btnClose:hover {
                background-color: #cbd5e1;
            }
            QPushButton#btnQuit {
                background-color: #fee2e2;
                color: #dc2626;
                border: 1px solid #fecaca;
                padding: 12px 18px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton#btnQuit:hover {
                background-color: #fca5a5;
                color: #991b1b;
            }
            QPushButton#btnQuit:pressed {
                background-color: #f87171;
            }
        """)

    def _copy_mid(self):
        text = self.txt_mid.text().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.btn_copy.setText("✓ Kopyalandı!")
            self.btn_copy.setStyleSheet("""
                background-color: #dcfce7;
                color: #166534;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            """)
            QTimer.singleShot(2500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.btn_copy.setText("📋 Kopyala")
        self.btn_copy.setStyleSheet("""
            background-color: #f1f5f9;
            color: #1e293b;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: bold;
        """)

    def _paste_key(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.txt_key.setPlainText(text)

    def _activate(self):
        key = self.txt_key.toPlainText().strip()
        if not key:
            QMessageBox.warning(self, "Uyarı", "Lütfen lisans anahtarını giriniz.")
            self.txt_key.setFocus()
            return
            
        success, msg = manager.activate_license(key)
        if success:
            QMessageBox.information(
                self, "Lisans Aktif Edildi",
                f"Tebrikler!\n\n{msg}\n\nProgramınızı güvenle kullanabilirsiniz."
            )
            self.accept()
        else:
            QMessageBox.critical(
                self, "Aktivasyon Başarısız",
                f"Lisans anahtarı doğrulanamadı:\n\n{msg}\n\nLütfen anahtarın bu makineye ait olduğundan emin olunuz."
            )

    def _quit_app(self):
        self.reject()
        QApplication.instance().quit()
        sys.exit(0)

    def closeEvent(self, event):
        if not self.can_cancel:
            self.reject()
            QApplication.instance().quit()
            sys.exit(0)
        else:
            super().closeEvent(event)
