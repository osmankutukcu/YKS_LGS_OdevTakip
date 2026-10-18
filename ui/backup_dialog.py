# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QHBoxLayout, QCheckBox, QMessageBox, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QIcon
from utils.backup_manager import BackupManager

class BackupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Drive / Bulut Yedekleme")
        self.resize(530, 480)
        self.manager = BackupManager()
        
        self.setStyleSheet("""
            QDialog { background-color: #f0f4f8; }
            QLabel { color: #333; }
        """)
        
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(30,30,30,30)
        
        # Başlık ve İkon
        head = QHBoxLayout()
        icon_lbl = QLabel("☁️")
        icon_lbl.setStyleSheet("font-size: 48px;")
        
        title_lay = QVBoxLayout()
        lbl_t = QLabel("Bulut Yedekleme")
        lbl_t.setStyleSheet("font-size: 20px; font-weight: bold; color: #2d3748;")
        lbl_d = QLabel("Yedekleri seçtiğiniz klasöre kaydedin.\nBulut eşitlemesi ayrıca doğrulanmalıdır.")
        lbl_d.setStyleSheet("color: #718096; font-size: 13px;")
        title_lay.addWidget(lbl_t)
        title_lay.addWidget(lbl_d)
        
        head.addWidget(icon_lbl)
        head.addSpacing(15)
        head.addLayout(title_lay)
        lay.addLayout(head)
        
        # Seçim Alanı
        card = QFrame()
        card.setStyleSheet("background: white; border-radius: 12px; border: 1px solid #e2e8f0;")
        cl = QVBoxLayout(card)
        
        self.lbl_path = QLabel(self.manager.get_backup_path() or "Henüz klasör seçilmedi")
        self.lbl_path.setStyleSheet("color: #4a5568; font-family: monospace; background: #edf2f7; padding: 8px; border-radius: 6px;")
        self.lbl_path.setWordWrap(True)
        
        btn_select = QPushButton("Klasör Seç (Google Drive)")
        btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select.setStyleSheet("""
            QPushButton {
                background-color: #4299e1; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3182ce; 
                color: #000000;}
        """)
        btn_select.clicked.connect(self._select_folder)
        
        cl.addWidget(QLabel("Yedeklenecek Hedef Klasör:"))
        cl.addWidget(self.lbl_path)
        cl.addWidget(btn_select, alignment=Qt.AlignmentFlag.AlignRight)
        
        lay.addWidget(card)
        
        # Ayarlar
        self.chk_auto = QCheckBox("Program kapanırken otomatik yedekle")
        self.chk_auto.setStyleSheet("font-size: 14px; color: #2d3748;")
        self.chk_auto.setChecked(self.manager.is_auto_backup())
        self.chk_auto.toggled.connect(self.manager.set_auto_backup)
        lay.addWidget(self.chk_auto)

        # V3.5.33: independent, explicit opt-in. Existing close-on-exit
        # setting, ZIP backup and manual backup behaviour remain unchanged.
        from utils import settings as appset
        self.chk_verified_daily = QCheckBox('Program açıkken günlük doğrulamalı SQLite yedeği al')
        self.chk_verified_daily.setAccessibleName('Günlük doğrulamalı yedekleme')
        self.chk_verified_daily.setStyleSheet('font-size: 13px; color: #2d3748;')
        self.chk_verified_daily.setChecked(
            str(appset.ayar_get('yedek_gunluk_dogrulamali_v3533', 'false')).lower() == 'true')
        self.chk_verified_daily.toggled.connect(
            lambda active: appset.ayar_set('yedek_gunluk_dogrulamali_v3533',
                                          'true' if active else 'false'))
        lay.addWidget(self.chk_verified_daily)
        note = QLabel('Günlük yedek yalnız SQLite veritabanını kapsar; planlayıcı profil dosyaları '
                      'için mevcut ZIP yedeğini de kullanın. Yedekler şifrelenmemiştir.')
        note.setWordWrap(True)
        note.setStyleSheet('font-size: 11px; color: #64748b;')
        lay.addWidget(note)
        
        # Alt Butonlar
        bot = QHBoxLayout()
        self.btn_now = QPushButton("Şimdi Yedekle")
        self.btn_now.setStyleSheet("""
            QPushButton {
                background-color: #48bb78; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #38a169; 
                color: #15191E;}
        """)
        self.btn_now.clicked.connect(self._backup_now)
        
        bot.addStretch(1)
        bot.addWidget(self.btn_now)
        lay.addLayout(bot)

    def _select_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Google Drive Klasörünü Seçin")
        if d:
            self.manager.set_backup_path(d)
            self.lbl_path.setText(d)

    def _backup_now(self):
        path = self.manager.get_backup_path()
        if not path:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir yedekleme klasörü (Google Drive) seçin.")
            return
            
        success, msg = self.manager.create_backup()
        if success:
            QMessageBox.information(self, "Başarılı", msg)
        else:
            QMessageBox.critical(self, "Hata", f"Yedeklenemedi:\n{msg}")
