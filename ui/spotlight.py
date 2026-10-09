# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, 
                             QLabel, QWidget, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon
import db

class SpotlightDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 400)
        
        # Ana kapsayıcı (Yuvarlak köşe ve gölge için)
        self.main_frame = QFrame(self)
        self.main_frame.setGeometry(0, 0, 600, 400)
        self.main_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e; /* Koyu */
                border-radius: 12px;
                border: 1px solid #313244;
            }
        """)
        
        # Gölge
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0,0,0, 100))
        shadow.setOffset(0, 10)
        self.main_frame.setGraphicsEffect(shadow)
        
        lay = QVBoxLayout(self.main_frame)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(5)
        
        # Arama kutusu
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("Ne yapmak istiyorsunuz? (Örn: Ahmet, Ayarlar, Rapor...)")
        self.txtSearch.setStyleSheet("""
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 16px;
                selection-background-color: #585b70;
            }
            QLineEdit:focus {
                background-color: #45475a;
            }
        """)
        lay.addWidget(self.txtSearch)
        
        # Sonuç listesi
        self.lstResults = QListWidget()
        self.lstResults.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                color: #a6adc8;
                padding: 10px;
                border-radius: 6px;
                font-size: 14px;
            }
            QListWidget::item:selected {
                background-color: #45475a;
                color: #ffffff;
            }
        """)
        lay.addWidget(self.lstResults)
        
        # İpuçları
        lbl_hint = QLabel("Seçmek için ⬆⬇, açmak için Enter, kapatmak için Esc")
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_hint.setStyleSheet("color: #6c7086; font-size: 11px;")
        lay.addWidget(lbl_hint)
        
        self.txtSearch.textChanged.connect(self._on_search)
        self.lstResults.itemActivated.connect(self._execute)
        
        # Veri önbelleği
        self.actions = [
            {"name": "Öğrenci Kaydı", "type": "menu", "func": parent._ogrenci_ac},
            {"name": "Ödev Takip", "type": "menu", "func": parent._odev_ac},
            {"name": "Raporlar", "type": "menu", "func": parent._rapor_ac},
            {"name": "Ders/Konu Düzenle", "type": "menu", "func": parent._ders_konu},
            {"name": "WhatsApp Toplu Gönder", "type": "menu", "func": parent._wp_hizli},
            {"name": "Ayarlar", "type": "menu", "func": parent._ayarlar},
            {"name": "Hızlı Görüşme", "type": "menu", "func": parent._hizli_gorusme},
            {"name": "Veritabanını Onar", "type": "menu", "func": parent._onar_menu},
            {"name": "Tema Değiştir", "type": "menu", "func": parent._tema_degistir},
            {"name": "Hakkında", "type": "menu", "func": parent._hakkinda},
        ]
        
        self.students = []
        try:
            con = db.get_conn()
            for r in con.execute("SELECT id, ad, soyad FROM ogrenci"):
                self.students.append({
                    "name": f"{r['ad']} {r['soyad']}", 
                    "type": "student", 
                    "id": r['id'],
                    "func": lambda sid=r['id']: self._open_student_detail(sid)
                })
        except:
            pass
            
        self._on_search("")

    def _open_student_detail(self, sid):
        # Bu fonksiyon parent'ın _ogrenci_detay fonksiyonuna benzer, 
        # ama direkt ID ile açmalı.
        # Main window'da _ogrenci_detay parametresiz, bu yüzden burada manuel import
        try:
            from ui.student_detail import OgrenciDetayDialog
            dlg = OgrenciDetayDialog(ogrenci_id=sid, adsoyad="", parent=self.parent())
            dlg.setModal(True)
            dlg.showMaximized()
            dlg.exec()
        except:
            pass

    def _on_search(self, txt):
        txt = txt.lower().strip()
        self.lstResults.clear()
        
        # 1. Menü eşleşmeleri
        for act in self.actions:
            if not txt or txt in act["name"].lower():
                it = QListWidgetItem(f"MENU: {act['name']}")
                it.setData(Qt.ItemDataRole.UserRole, act)
                self.lstResults.addItem(it)
        
        # 2. Öğrenci eşleşmeleri
        count = 0
        for s in self.students:
            if count > 10: break # Çok fazla sonuç gösterme
            if not txt or txt in s["name"].lower():
                it = QListWidgetItem(f"ÖĞRENCİ: {s['name']}")
                it.setData(Qt.ItemDataRole.UserRole, s)
                self.lstResults.addItem(it)
                count += 1
                
        if self.lstResults.count() > 0:
            self.lstResults.setCurrentRow(0)

    def _execute(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data.get("func"):
            self.accept()
            QTimer.singleShot(100, data["func"])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Down:
            idx = self.lstResults.currentRow() + 1
            if idx < self.lstResults.count():
                self.lstResults.setCurrentRow(idx)
        elif event.key() == Qt.Key.Key_Up:
            idx = self.lstResults.currentRow() - 1
            if idx >= 0:
                self.lstResults.setCurrentRow(idx)
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.lstResults.currentItem():
                self._execute(self.lstResults.currentItem())
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            # Diğer tuşları arama kutusuna ver
            if self.txtSearch.hasFocus():
                super().keyPressEvent(event)
            else:
                self.txtSearch.setFocus()
                self.txtSearch.event(event)

