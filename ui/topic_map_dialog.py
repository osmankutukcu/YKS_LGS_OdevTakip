# -*- coding: utf-8 -*-
"""
Akıllı Müfredat ve Konu Hakimiyet Haritası (TopicMapDialog)
YKS & LGS sınav maratonu için makro müfredat takibi, konu hakimiyet oranları,
aktif ödev entegrasyonu ve A4 Çalışma Panosu Çıktısı (PDF / Yazdır).
"""

import os
import json
import sqlite3
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QWidget, QPushButton, QProgressBar, QMessageBox, QFrame,
    QScrollArea, QGridLayout, QGroupBox, QTabWidget, QListWidget, QListWidgetItem, QStackedWidget,
    QDateEdit, QLineEdit, QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSlider, QSpinBox, QTextEdit, QFileDialog, QSplitter, QRadioButton, QButtonGroup, QCheckBox
)
from PyQt6.QtCore import Qt, QSize, QDate, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QTextDocument, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog

import db

# ----------------------------------------------------------------------
# 1. Müfredat Bilgi Havuzu Yükleyicisi (curriculum.json)
# ----------------------------------------------------------------------
CURRICULUM_DATA = {}

def load_curriculum():
    global CURRICULUM_DATA
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(base_dir, "assets", "curriculum.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                CURRICULUM_DATA = data.get("topics", {})
    except Exception as e:
        print("Curriculum yükleme hatası:", e)

load_curriculum()

def get_topic_info(topic_name):
    """Konu için soru ağırlığı, önem derecesi ve koç ipucunu döner."""
    if not CURRICULUM_DATA:
        return {}
    if topic_name in CURRICULUM_DATA:
        return CURRICULUM_DATA[topic_name]
    # Kısmi eşleşme dene
    t_lower = topic_name.lower().strip()
    for k, v in CURRICULUM_DATA.items():
        k_lower = k.lower().strip()
        if t_lower == k_lower or t_lower in k_lower or k_lower in t_lower:
            return v
    return {}


# ----------------------------------------------------------------------
# 2. Konu Yönetimi ve Ödev Atama Modalı (AssignmentManagerDialog)
# ----------------------------------------------------------------------
class AssignmentManagerDialog(QDialog):
    """
    Seçilen konunun hem makro hakimiyet durumunu (koc_konu_takip)
    hem de mikro ödevlerini (odev_takip) yöneten modern diyalog.
    """
    def __init__(self, student_id, lesson_name, topic_name, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self.lesson_name = lesson_name
        self.topic_name = topic_name
        self.curriculum_info = get_topic_info(topic_name)
        
        self.setWindowTitle(f"🎯 Konu Yönetimi: {topic_name} ({lesson_name})")
        self.resize(800, 640)
        self.setMinimumSize(740, 580)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background: white;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                font-weight: 600;
                padding: 10px 20px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #2563eb;
                border: 1px solid #cbd5e1;
                border-bottom: 2px solid #2563eb;
            }
            QTableWidget {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                gridline-color: #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                color: #1e293b;
                font-weight: 600;
            }
            QComboBox:hover { border-color: #3b82f6; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #cbd5e1;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: #f8fafc;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #475569;
                width: 0;
                height: 0;
            }
        """)
        
        self.init_ui()
        self.load_mastery_data()
        self.load_assignments()

    def init_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setSpacing(12)
        main_lay.setContentsMargins(16, 16, 16, 16)
        
        # --- Üst Bilgi Kartı ---
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #2563eb);
                border-radius: 10px;
                padding: 12px;
            }
        """)
        h_lay = QHBoxLayout(header_card)
        h_lay.setContentsMargins(14, 10, 14, 10)
        
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_sub = QLabel(f"📚 {self.lesson_name.upper()}")
        lbl_sub.setStyleSheet("color: #93c5fd; font-size: 11px; font-weight: bold; text-transform: uppercase;")
        lbl_name = QLabel(self.topic_name)
        lbl_name.setStyleSheet("color: white; font-size: 18px; font-weight: 900;")
        v_title.addWidget(lbl_sub)
        v_title.addWidget(lbl_name)
        h_lay.addLayout(v_title)
        h_lay.addStretch()
        
        # ÖSYM Soru Ağırlığı Rozeti
        imp = self.curriculum_info.get("importance", "Standart")
        q_count = self.curriculum_info.get("questions", "Soru Dağılımı")
        badge_frame = QFrame()
        badge_frame.setStyleSheet("background: rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 6px 12px;")
        b_lay = QVBoxLayout(badge_frame)
        b_lay.setContentsMargins(0, 0, 0, 0)
        lbl_badge_title = QLabel("🎯 ÖSYM Sınav Ağırlığı")
        lbl_badge_title.setStyleSheet("color: #e0e7ff; font-size: 10px; font-weight: 600;")
        lbl_badge_val = QLabel(f"{imp} • {q_count}")
        lbl_badge_val.setStyleSheet("color: #fef08a; font-size: 12px; font-weight: bold;")
        b_lay.addWidget(lbl_badge_title)
        b_lay.addWidget(lbl_badge_val)
        h_lay.addWidget(badge_frame)
        
        main_lay.addWidget(header_card)
        
        # Koç İpucu Şeridi (varsa)
        tip = self.curriculum_info.get("tip")
        if tip:
            tip_frame = QFrame()
            tip_frame.setStyleSheet("background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 6px 12px;")
            t_lay = QHBoxLayout(tip_frame)
            t_lay.setContentsMargins(4, 4, 4, 4)
            lbl_tip = QLabel(f"💡 <b>Koç Stratejisi:</b> {tip}")
            lbl_tip.setStyleSheet("color: #1e40af; font-size: 11px;")
            lbl_tip.setWordWrap(True)
            t_lay.addWidget(lbl_tip)
            main_lay.addWidget(tip_frame)

        # --- Sekmeler (Hakimiyet & Ödevler) ---
        self.tabs = QTabWidget()
        
        # Sekme 1: Konu Hakimiyet & Koçluk Durumu
        tab_mastery = QWidget()
        self._setup_mastery_tab(tab_mastery)
        self.tabs.addTab(tab_mastery, "🎯 Konu Hakimiyeti & Koçluk Durumu")
        
        # Sekme 2: Ödev ve Kaynak Takibi
        tab_assign = QWidget()
        self._setup_assign_tab(tab_assign)
        self.tabs.addTab(tab_assign, "📘 Ödevler & Kaynaklar (odev_takip)")
        
        main_lay.addWidget(self.tabs, stretch=1)
        
        # Alt Kapat Butonu
        btn_close = QPushButton("Kapat ve Güncelle")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                padding: 10px 24px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        btn_close.clicked.connect(self.accept)
        main_lay.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _setup_mastery_tab(self, parent):
        lay = QVBoxLayout(parent)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)
        
        # Durum Seçimi
        g_status = QGroupBox("📌 Konu İlerleme Aşaması")
        g_status.setStyleSheet("font-weight: bold; color: #1e293b;")
        v_stat = QVBoxLayout(g_status)
        
        self.cmb_status = QComboBox()
        self.cmb_status.addItem("⚪ 0 - Henüz Başlanmadı", 0)
        self.cmb_status.addItem("📖 1 - Konu Anlatımı Çalışıldı / Not Çıkarıldı", 1)
        self.cmb_status.addItem("✏️ 2 - Soru Çözüldü / Temel Testler Bitti", 2)
        self.cmb_status.addItem("⚠️ 3 - Tekrar Gerekli (Eksik / Yanlış Fazla)", 3)
        self.cmb_status.addItem("✅ 4 - Tamamlandı / Tam Hakimiyet", 4)
        self.cmb_status.currentIndexChanged.connect(self._on_status_changed)
        v_stat.addWidget(self.cmb_status)
        lay.addWidget(g_status)
        
        # Hakimiyet Puanı (%0 - %100)
        g_score = QGroupBox("📊 Konu Hakimiyet & Net Yüzdesi")
        g_score.setStyleSheet("font-weight: bold; color: #1e293b;")
        v_score = QVBoxLayout(g_score)
        
        h_score = QHBoxLayout()
        self.slider_score = QSlider(Qt.Orientation.Horizontal)
        self.slider_score.setRange(0, 100)
        self.slider_score.setValue(0)
        
        self.spin_score = QSpinBox()
        self.spin_score.setRange(0, 100)
        self.spin_score.setSuffix(" %")
        self.spin_score.setFixedWidth(80)
        self.spin_score.setStyleSheet("font-weight: bold; font-size: 14px; color: #2563eb;")
        
        self.slider_score.valueChanged.connect(self.spin_score.setValue)
        self.spin_score.valueChanged.connect(self.slider_score.setValue)
        
        h_score.addWidget(self.slider_score, stretch=1)
        h_score.addWidget(self.spin_score)
        v_score.addLayout(h_score)
        lay.addWidget(g_score)
        
        # Soru Hedefi & Çözülen
        g_questions = QGroupBox("🎯 Soru Hedefi ve Çözülen Sayı")
        g_questions.setStyleSheet("font-weight: bold; color: #1e293b;")
        h_q = QHBoxLayout(g_questions)
        
        h_q.addWidget(QLabel("Çözülen Soru:"))
        self.spin_cozulen = QSpinBox()
        self.spin_cozulen.setRange(0, 10000)
        self.spin_cozulen.setSingleStep(10)
        h_q.addWidget(self.spin_cozulen)
        
        h_q.addWidget(QLabel("Hedef Soru:"))
        self.spin_hedef = QSpinBox()
        self.spin_hedef.setRange(0, 10000)
        self.spin_hedef.setSingleStep(10)
        self.spin_hedef.setValue(100)
        h_q.addWidget(self.spin_hedef)
        lay.addWidget(g_questions)
        
        # Koç Notu
        g_notes = QGroupBox("📝 Koçun Değerlendirme ve Çalışma Notu")
        g_notes.setStyleSheet("font-weight: bold; color: #1e293b;")
        v_notes = QVBoxLayout(g_notes)
        self.txt_koc_notu = QTextEdit()
        self.txt_koc_notu.setPlaceholderText("Örn: Formüllerde sıkıntı yok, ancak yeni nesil paragraf tipi matematik sorularında süreye dikkat etmeli...")
        self.txt_koc_notu.setMaximumHeight(75)
        v_notes.addWidget(self.txt_koc_notu)
        lay.addWidget(g_notes)
        
        # Kaydet Butonu
        btn_save_mastery = QPushButton("💾 Konu Hakimiyet Durumunu Kaydet")
        btn_save_mastery.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_mastery.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_save_mastery.clicked.connect(self.save_mastery_data)
        lay.addWidget(btn_save_mastery)
        lay.addStretch()

    def _setup_assign_tab(self, parent):
        lay = QVBoxLayout(parent)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)
        
        # Tablo
        lay.addWidget(QLabel("📋 <b>Bu Konuya Ait Verilen Ödevler:</b>"))
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Kaynak Kitap", "Kontrol Tarihi", "Durum", "İşlem"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 110)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 110)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 160)
        
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.table, stretch=1)
        
        # Yeni Ekleme Formu
        grp_new = QGroupBox("✨ Yeni Ödev Ata")
        grp_new.setStyleSheet("font-weight: bold; color: #1e293b;")
        frm_lay = QVBoxLayout(grp_new)
        
        h_inputs = QHBoxLayout()
        
        v_b = QVBoxLayout()
        v_b.addWidget(QLabel("Kaynak Kitap:"))
        self.cmb_book = QComboBox()
        self.cmb_book.setEditable(True)
        self.load_student_books()
        v_b.addWidget(self.cmb_book)
        h_inputs.addLayout(v_b, stretch=2)
        
        v_d1 = QVBoxLayout()
        v_d1.addWidget(QLabel("Başlangıç:"))
        self.date_start = QDateEdit(QDate.currentDate())
        self.date_start.setCalendarPopup(True)
        v_d1.addWidget(self.date_start)
        h_inputs.addLayout(v_d1, stretch=1)
        
        v_d2 = QVBoxLayout()
        v_d2.addWidget(QLabel("Kontrol Tarihi 🔔:"))
        self.date_control = QDateEdit(QDate.currentDate().addDays(4))
        self.date_control.setCalendarPopup(True)
        v_d2.addWidget(self.date_control)
        h_inputs.addLayout(v_d2, stretch=1)
        
        frm_lay.addLayout(h_inputs)
        
        btn_add = QPushButton("➕ Ödevi Kaydet ve Listeye Ekle")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_add.clicked.connect(self.add_assignment)
        frm_lay.addWidget(btn_add)
        
        lay.addWidget(grp_new)

    def _on_status_changed(self, idx):
        val = self.cmb_status.currentData()
        if val == 4: # Tamamlandı
            if self.spin_score.value() < 85:
                self.spin_score.setValue(100)
        elif val == 3: # Tekrar
            if self.spin_score.value() > 65:
                self.spin_score.setValue(45)

    def load_mastery_data(self):
        try:
            con = db.get_conn()
            r = con.execute("""
                SELECT durum, hakimiyet_puani, cozulen_soru, hedef_soru, koc_notu
                FROM koc_konu_takip
                WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=?
            """, (self.student_id, self.lesson_name, self.topic_name)).fetchone()
            
            if r:
                st = r['durum'] if r['durum'] is not None else 0
                idx = self.cmb_status.findData(st)
                if idx >= 0:
                    self.cmb_status.setCurrentIndex(idx)
                
                score = r['hakimiyet_puani'] or 0
                self.spin_score.setValue(score)
                self.spin_cozulen.setValue(r['cozulen_soru'] or 0)
                self.spin_hedef.setValue(r['hedef_soru'] or 100)
                self.txt_koc_notu.setPlainText(r['koc_notu'] or "")
            else:
                self.cmb_status.setCurrentIndex(0)
                self.spin_score.setValue(0)
                self.spin_cozulen.setValue(0)
                self.spin_hedef.setValue(100)
        except Exception as e:
            print("load_mastery_data error:", e)

    def save_mastery_data(self):
        st = self.cmb_status.currentData()
        score = self.spin_score.value()
        coz = self.spin_cozulen.value()
        hedef = self.spin_hedef.value()
        note = self.txt_koc_notu.toPlainText().strip()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        try:
            con = db.get_conn()
            exist = con.execute("""
                SELECT id FROM koc_konu_takip 
                WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=?
            """, (self.student_id, self.lesson_name, self.topic_name)).fetchone()
            
            if exist:
                con.execute("""
                    UPDATE koc_konu_takip
                    SET durum=?, hakimiyet_puani=?, cozulen_soru=?, hedef_soru=?, koc_notu=?, updated_at=?
                    WHERE id=?
                """, (st, score, coz, hedef, note, now_str, exist['id']))
            else:
                con.execute("""
                    INSERT INTO koc_konu_takip
                    (ogrenci_id, ders_adi, konu_adi, durum, hakimiyet_puani, cozulen_soru, hedef_soru, koc_notu, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.student_id, self.lesson_name, self.topic_name, st, score, coz, hedef, note, now_str))
                
            con.commit()
            QMessageBox.information(self, "Başarılı", "Konu hakimiyet bilgileri başarıyla kaydedildi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")

    def load_student_books(self):
        try:
            con = db.get_conn()
            res = con.execute("SELECT kitap_ad FROM ogrenci_kitap WHERE ogrenci_id=? AND ders=? ORDER BY kitap_ad", 
                              (self.student_id, self.lesson_name)).fetchall()
            books = [r[0] for r in res]
            self.cmb_book.clear()
            self.cmb_book.addItems(books)
            if not books:
                # Havuzdan öner
                res_all = con.execute("SELECT ad FROM kitap WHERE ders=? ORDER BY ad", (self.lesson_name,)).fetchall()
                self.cmb_book.addItems([r[0] for r in res_all])
            self.cmb_book.lineEdit().setPlaceholderText("Kitap seçin veya manuel yazın...")
        except: pass

    def load_assignments(self):
        self.table.setRowCount(0)
        try:
            con = db.get_conn()
            rows = con.execute("""
                SELECT id, kitap_adi, kontrol_tarihi, durum 
                FROM odev_takip 
                WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=?
                ORDER BY created_at DESC
            """, (self.student_id, self.lesson_name, self.topic_name)).fetchall()
            
            self.table.setRowCount(len(rows))
            today_str = QDate.currentDate().toString("yyyy-MM-dd")
            
            for i, r in enumerate(rows):
                # 1. Kaynak
                self.table.setItem(i, 0, QTableWidgetItem(r['kitap_adi']))
                
                # 2. Tarih Formatı
                raw_date = r['kontrol_tarihi']
                try:
                    d_obj = QDate.fromString(raw_date, "yyyy-MM-dd")
                    d_str = d_obj.toString("dd.MM.yyyy")
                except: d_str = raw_date
                
                it_date = QTableWidgetItem(d_str)
                it_date.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if r['durum'] == 'Aktif' and raw_date < today_str:
                    it_date.setForeground(QColor("#dc2626")) # Gecikmiş
                    it_date.setText(f"🚨 {d_str}")
                self.table.setItem(i, 1, it_date)
                
                # 3. Durum
                st_item = QTableWidgetItem(r['durum'])
                st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if r['durum'] == 'Aktif':
                    st_item.setForeground(QColor("#d97706"))
                    st_item.setText("⏳ Aktif")
                else:
                    st_item.setForeground(QColor("#16a34a"))
                    st_item.setText("✅ Bitti")
                self.table.setItem(i, 2, st_item)
                
                # 4. İşlemler
                w_btn = QWidget()
                h_b = QHBoxLayout(w_btn)
                h_b.setContentsMargins(4, 2, 4, 2)
                h_b.setSpacing(6)
                
                if r['durum'] == 'Aktif':
                    btn_done = QPushButton("✓ Bitir")
                    btn_done.setStyleSheet("background: #dcfce7; color: #166534; border: 1px solid #86efac; border-radius: 4px; font-weight: bold; padding: 3px 8px;")
                    btn_done.clicked.connect(lambda _, rid=r['id']: self.mark_done(rid))
                    h_b.addWidget(btn_done)
                else:
                    btn_undo = QPushButton("↺ Geri Al")
                    btn_undo.setStyleSheet("background: #fff7ed; color: #c2410c; border: 1px solid #fdba74; border-radius: 4px; font-weight: bold; padding: 3px 8px;")
                    btn_undo.clicked.connect(lambda _, rid=r['id']: self.mark_active(rid))
                    h_b.addWidget(btn_undo)
                
                btn_del = QPushButton("Sil")
                btn_del.setStyleSheet("background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; border-radius: 4px; font-weight: bold; padding: 3px 8px;")
                btn_del.clicked.connect(lambda _, rid=r['id']: self.delete_assignment(rid))
                h_b.addWidget(btn_del)
                
                self.table.setCellWidget(i, 3, w_btn)
        except Exception as e:
            print("Load assignments error:", e)

    def add_assignment(self):
        book = self.cmb_book.currentText().strip()
        if not book:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir kaynak kitap seçiniz veya yazınız.")
            return
        
        s_date = self.date_start.date().toString("yyyy-MM-dd")
        c_date = self.date_control.date().toString("yyyy-MM-dd")
        
        try:
            con = db.get_conn()
            con.execute("""
                INSERT INTO odev_takip (ogrenci_id, ders_adi, konu_adi, kitap_adi, baslangic_tarihi, kontrol_tarihi, durum)
                VALUES (?, ?, ?, ?, ?, ?, 'Aktif')
            """, (self.student_id, self.lesson_name, self.topic_name, book, s_date, c_date))
            con.commit()
            
            # Otomatik olarak koc_konu_takip durumunu en az 'Çalışılıyor' yap
            exist = con.execute("""
                SELECT id, durum FROM koc_konu_takip 
                WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=?
            """, (self.student_id, self.lesson_name, self.topic_name)).fetchone()
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            if not exist:
                con.execute("""
                    INSERT INTO koc_konu_takip (ogrenci_id, ders_adi, konu_adi, durum, hakimiyet_puani, updated_at)
                    VALUES (?, ?, ?, 1, 30, ?)
                """, (self.student_id, self.lesson_name, self.topic_name, now_str))
                con.commit()
            elif exist['durum'] == 0:
                con.execute("UPDATE koc_konu_takip SET durum=1 WHERE id=?", (exist['id'],))
                con.commit()
                
            self.load_assignments()
            self.load_mastery_data()
            self.cmb_book.setCurrentIndex(-1)
        except Exception as e:
            print("Add Error:", e)

    def mark_done(self, rid):
        try:
            con = db.get_conn()
            con.execute("UPDATE odev_takip SET durum='Tamamlandı' WHERE id=?", (rid,))
            con.commit()
            self.load_assignments()
        except: pass

    def mark_active(self, rid):
        try:
            con = db.get_conn()
            con.execute("UPDATE odev_takip SET durum='Aktif' WHERE id=?", (rid,))
            con.commit()
            self.load_assignments()
        except: pass

    def delete_assignment(self, rid):
        if QMessageBox.question(self, "Ödevi Sil", "Bu ödevi silmek istediğinize emin misiniz?") == QMessageBox.StandardButton.Yes:
            try:
                con = db.get_conn()
                con.execute("DELETE FROM odev_takip WHERE id=?", (rid,))
                con.commit()
                self.load_assignments()
            except: pass


# ----------------------------------------------------------------------
# 3. Modern Konu Kartı Bileşeni (TopicChip / ModernTopicCard)
# ----------------------------------------------------------------------
class TopicChip(QFrame):
    """
    Kullanıcının gördüğü konu kartı.
    Status rozeti, konu başlığı, ÖSYM soru frekansı ve aktif ödev durumunu gösterir.
    """
    clicked = pyqtSignal()
    
    def __init__(self, topic_data, status, extra_data=None, parent=None):
        super().__init__(parent)
        self.topic_data = dict(topic_data) if topic_data else {}
        self.status = status # 0: Başlanmadı, 1: Çalışıldı, 2: Soru, 3: Tekrar, 4: Bitti
        self.extra_data = extra_data or {}
        self.curriculum_info = get_topic_info(self.topic_data.get('konu', ''))
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(225, 118)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(3)
        
        # 1. Üst Rozet (Durum & İlerleme)
        self.lbl_status = QLabel()
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setFixedHeight(22)
        layout.addWidget(self.lbl_status)
        
        # 2. Konu Başlığı
        self.lbl_title = QLabel(self.topic_data.get('konu', ''))
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet("font-weight: 700; font-size: 11.5px; color: #0f172a; line-height: 1.2;")
        layout.addWidget(self.lbl_title, stretch=1)
        
        # 3. Alt Satır (ÖSYM Ağırlığı & Ödev / Soru Sayısı)
        h_sub = QHBoxLayout()
        h_sub.setContentsMargins(0, 0, 0, 0)
        h_sub.setSpacing(4)
        
        self.lbl_weight = QLabel()
        self.lbl_weight.setStyleSheet("font-size: 9.5px; font-weight: 600; color: #64748b; background: rgba(0,0,0,0.04); border-radius: 4px; padding: 1px 4px;")
        h_sub.addWidget(self.lbl_weight)
        
        h_sub.addStretch()
        
        self.lbl_extra = QLabel()
        self.lbl_extra.setStyleSheet("font-size: 9.5px; font-weight: bold;")
        h_sub.addWidget(self.lbl_extra)
        
        layout.addLayout(h_sub)
        
        self.update_style()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def update_style(self):
        active = self.extra_data.get('active_count', 0)
        finished = self.extra_data.get('finished_count', 0)
        mastery_durum = self.extra_data.get('mastery_durum', None)
        mastery_score = self.extra_data.get('mastery_score', 0)
        
        # Durum Analizi:
        # 1. Eğer açık ödev varsa -> Çalışılıyor (Mavi / Turuncu)
        # 2. Eğer koç durum=4 veya finished>0 ve active==0 -> Yeşil (Tamamlandı)
        # 3. Eğer koç durum=3 -> Kırmızı (Tekrar Gerekli)
        # 4. Eğer koç durum in (1,2) -> Sarı / Mavi (Çalışılıyor)
        # 5. Hiçbiri yoksa -> Gri (Başlanmadı)
        
        if active > 0:
            bg = "#eff6ff"
            border = "#93c5fd"
            hover_border = "#2563eb"
            badge_bg = "#dbeafe"
            badge_txt = "#1d4ed8"
            status_txt = f"⏳ {active} Aktif Ödev"
            if self.extra_data.get('next_control'):
                d = self.extra_data['next_control']
                try:
                    d_fmt = QDate.fromString(d, "yyyy-MM-dd").toString("dd.MM")
                    status_txt += f" ({d_fmt})"
                except: pass
        elif mastery_durum == 4 or (finished > 0 and active == 0 and mastery_durum != 3):
            bg = "#f0fdf4"
            border = "#86efac"
            hover_border = "#16a34a"
            badge_bg = "#dcfce7"
            badge_txt = "#15803d"
            pct_val = mastery_score if mastery_score > 0 else 100
            status_txt = f"✅ Tamamlandı (%{pct_val})"
        elif mastery_durum == 3:
            bg = "#fef2f2"
            border = "#fca5a5"
            hover_border = "#dc2626"
            badge_bg = "#fee2e2"
            badge_txt = "#b91c1c"
            status_txt = "⚠️ Tekrar Gerekli"
        elif mastery_durum in (1, 2) or (mastery_score > 0):
            bg = "#fefce8"
            border = "#fde047"
            hover_border = "#ca8a04"
            badge_bg = "#fef08a"
            badge_txt = "#854d0e"
            status_txt = f"📖 Çalışılıyor (%{mastery_score})"
        else:
            bg = "#ffffff"
            border = "#e2e8f0"
            hover_border = "#94a3b8"
            badge_bg = "#f1f5f9"
            badge_txt = "#64748b"
            status_txt = "⚪ Henüz Başlanmadı"
            
        self.setStyleSheet(f"""
            TopicChip {{
                background-color: {bg};
                border: 1.5px solid {border};
                border-radius: 10px;
            }}
            TopicChip:hover {{
                border: 2px solid {hover_border};
                background-color: #ffffff;
            }}
        """)
        
        self.lbl_status.setText(status_txt)
        self.lbl_status.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_txt};
            font-weight: bold;
            font-size: 10px;
            border-radius: 6px;
            padding: 2px 4px;
        """)
        
        # ÖSYM Sınav Ağırlığı Bilgisi
        q_info = self.curriculum_info.get("questions")
        if q_info:
            self.lbl_weight.setText(f"⭐ {q_info}")
        else:
            self.lbl_weight.setText("🎯 Müfredat")
            
        # Alt Sağ Ekstra Bilgi
        if self.extra_data.get('cozulen_soru', 0) > 0:
            self.lbl_extra.setText(f"✏️ {self.extra_data['cozulen_soru']} s.")
            self.lbl_extra.setStyleSheet("color: #2563eb;")
        elif finished > 0:
            self.lbl_extra.setText(f"📘 {finished} biten")
            self.lbl_extra.setStyleSheet("color: #16a34a;")
        else:
            self.lbl_extra.setText("")


# ----------------------------------------------------------------------
# 4. A4 Öğrenci Çalışma Panosu Çıktı Sihirbazı (StudyBoardPosterDialog)
# ----------------------------------------------------------------------
class StudyBoardPosterDialog(QDialog):
    """
    Öğrencinin odasındaki çalışma masası veya panosuna asacağı
    A4 formatında yüksek çözünürlüklü ve estetik Çalışma Çizelgesi oluşturur.
    """
    def __init__(self, student_info, lesson_name, topics, topic_stats_map, all_lessons_data=None, parent=None):
        super().__init__(parent)
        self.student_info = student_info
        self.lesson_name = lesson_name
        self.topics = topics
        self.topic_stats_map = topic_stats_map
        self.all_lessons_data = all_lessons_data or []
        
        self.setWindowTitle("🖨️ Pano İçin Çıktı Al - Konu Takip Çizelgesi")
        self.resize(520, 420)
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QGroupBox { font-weight: bold; color: #1e293b; }
            QRadioButton { font-weight: 600; color: #334155; }
        """)
        
        self.init_ui()

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 20)
        
        # Başlık Bilgisi
        lbl_h = QLabel("🖨️ Öğrenci Çalışma Panosu Çıktı Sihirbazı")
        lbl_h.setStyleSheet("font-size: 16px; font-weight: 900; color: #1e3a8a;")
        lay.addWidget(lbl_h)
        
        lbl_desc = QLabel(
            "Bu sihirbaz ile öğrencinizin çalışma masasına veya panosuna yapıştırabileceği, "
            "konuları çalıştıkça kutucukları işaretleyeceği yüksek kaliteli bir A4 çizelgesi basabilirsiniz."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #475569; font-size: 11.5px;")
        lay.addWidget(lbl_desc)
        
        # Kapsam Seçimi
        grp_scope = QGroupBox("📋 Yazdırma Kapsamı")
        v_sc = QVBoxLayout(grp_scope)
        
        self.radio_current = QRadioButton(f"Sadece Seçili Ders: {self.lesson_name} (A4 Tek Sayfa Pano)")
        self.radio_current.setChecked(True)
        v_sc.addWidget(self.radio_current)
        
        self.radio_all = QRadioButton("Tüm Müfredat Dersleri (Komple YKS/LGS Çalışma Seti)")
        v_sc.addWidget(self.radio_all)
        lay.addWidget(grp_scope)
        
        # Seçenekler
        grp_opts = QGroupBox("⚙️ Çizelge Detayları")
        v_op = QVBoxLayout(grp_opts)
        
        self.chk_weights = QCheckBox("ÖSYM Sınav Soru Dağılımı ve Ağırlıklarını Tabloda Göster")
        self.chk_weights.setChecked(True)
        v_op.addWidget(self.chk_weights)
        
        self.chk_checkboxes = QCheckBox("4 Kademeli Takip Kutucukları Ekle (Özet, 1. Test, 2. Test, Koç Onayı)")
        self.chk_checkboxes.setChecked(True)
        v_op.addWidget(self.chk_checkboxes)
        
        self.chk_rules = QCheckBox("Alt Kısma 'Pano Çalışma Kuralları' ve Koç İmza Alanı Ekle")
        self.chk_rules.setChecked(True)
        v_op.addWidget(self.chk_rules)
        lay.addWidget(grp_opts)
        
        lay.addStretch()
        
        # Butonlar
        h_btn = QHBoxLayout()
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 16px; font-weight: bold; color: #475569;")
        btn_cancel.clicked.connect(self.reject)
        h_btn.addWidget(btn_cancel)
        
        h_btn.addStretch()
        
        btn_pdf = QPushButton("📄 PDF Olarak Kaydet")
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.setStyleSheet("background: #0284c7; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold;")
        btn_pdf.clicked.connect(self.export_pdf)
        h_btn.addWidget(btn_pdf)
        
        btn_print = QPushButton("🖨️ Yazıcıya Gönder (Yazdır)")
        btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_print.setStyleSheet("background: #16a34a; color: white; border-radius: 6px; padding: 8px 18px; font-weight: bold;")
        btn_print.clicked.connect(self.print_dialog)
        h_btn.addWidget(btn_print)
        
        lay.addLayout(h_btn)

    def generate_html(self):
        is_all = self.radio_all.isChecked()
        stu_name = f"{self.student_info.get('ad', '')} {self.student_info.get('soyad', '')}".strip()
        hedef = self.student_info.get('hedef_bolum') or self.student_info.get('alt_grup') or "Hedef Üniversite / Lise"
        ana_grup = self.student_info.get('ana_grup') or "YKS"
        now_date = datetime.now().strftime("%d.%m.%Y")
        
        sections = []
        if not is_all:
            sections.append((self.lesson_name, self.topics))
        else:
            for lname, ltopics in self.all_lessons_data:
                sections.append((lname, ltopics))
                
        html_pages = []
        
        for idx, (lname, topics_list) in enumerate(sections):
            rows_html = []
            for s_idx, t in enumerate(topics_list, 1):
                tname = t.get('konu', '')
                tinfo = get_topic_info(tname)
                stat = self.topic_stats_map.get((lname, tname), {})
                
                weight_str = tinfo.get("questions", "—")
                
                # Mevcut durum
                durum_val = stat.get('mastery_durum', 0)
                is_done = durum_val == 4 or (stat.get('finished_count', 0) > 0 and stat.get('active_count', 0) == 0)
                
                c1 = "checked" if is_done or durum_val >= 1 else ""
                c2 = "checked" if is_done or durum_val >= 2 else ""
                c3 = "checked" if is_done or durum_val >= 3 else ""
                c4 = "checked" if is_done else ""
                
                ch1 = f"<span class='chk-box {c1}'>{'✓' if c1 else ''}</span>"
                ch2 = f"<span class='chk-box {c2}'>{'✓' if c2 else ''}</span>"
                ch3 = f"<span class='chk-box {c3}'>{'✓' if c3 else ''}</span>"
                ch4 = f"<span class='chk-box {c4}'>{'✓' if c4 else ''}</span>"
                
                score_str = f"%{stat.get('mastery_score', 0)}" if stat.get('mastery_score', 0) > 0 else "—"
                
                row_tr = f"""
                <tr>
                    <td style="text-align: center; color: #64748b; font-weight: bold; width: 28px;">{s_idx}</td>
                    <td class="topic-cell">{tname}</td>
                    <td style="text-align: center; width: 75px;"><span class="weight-badge">{weight_str}</span></td>
                    <td class="box-cell">{ch1} Özet</td>
                    <td class="box-cell">{ch2} 1. Test</td>
                    <td class="box-cell">{ch3} 2. Test</td>
                    <td class="box-cell">{ch4} Koç</td>
                    <td style="text-align: center; width: 45px; font-weight: bold; color: #2563eb;">{score_str}</td>
                    <td style="text-align: center; width: 65px; color: #94a3b8; font-size: 9px;">.../.../202..</td>
                </tr>
                """
                rows_html.append(row_tr)
                
            page_class = "page-break" if idx < len(sections) - 1 else ""
            
            p_html = f"""
            <div class="poster-container {page_class}">
                <!-- Üst Başlık Kartı -->
                <div class="header-card">
                    <div style="display: table; width: 100%;">
                        <div style="display: table-cell; vertical-align: middle;">
                            <div class="header-title">🎯 {ana_grup} HEDEF VE ÇALIŞMA PANOSU</div>
                            <div class="header-sub">Öğrenci Müfredat Tamamlama ve Konu Hakimiyet Çizelgesi</div>
                        </div>
                        <div style="display: table-cell; text-align: right; vertical-align: middle;">
                            <div style="font-size: 14px; font-weight: 900; color: #2563eb;">{lname.upper()}</div>
                            <div style="font-size: 10px; color: #64748b;">Toplam: {len(topics_list)} Konu</div>
                        </div>
                    </div>
                    
                    <div class="meta-grid">
                        <div class="meta-col"><span class="meta-label">ÖĞRENCİ:</span> <span class="meta-val">{stu_name}</span></div>
                        <div class="meta-col"><span class="meta-label">ALAN / GRUP:</span> <span class="meta-val">{ana_grup}</span></div>
                        <div class="meta-col"><span class="meta-label">HEDEF:</span> <span class="meta-val">{hedef}</span></div>
                        <div class="meta-col"><span class="meta-label">TARİH:</span> <span class="meta-val">{now_date}</span></div>
                    </div>
                    <div class="motto">"Her işaretlenen kutucuk, seni hedefine bir adım daha yaklaştırır!" 🚀</div>
                </div>

                <!-- Çizelge Tablosu -->
                <table class="checklist">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Konu Başlığı</th>
                            <th>ÖSYM Ağırlık</th>
                            <th>1. Konu/Özet</th>
                            <th>2. Temel Test</th>
                            <th>3. Zor Test</th>
                            <th>4. Koç Onayı</th>
                            <th>Hakimiyet</th>
                            <th>Bitiş Tarihi</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows_html)}
                    </tbody>
                </table>

                <!-- Pano Kuralları & Koç İmzası -->
                <div class="footer-box">
                    <div style="display: table; width: 100%;">
                        <div style="display: table-cell; width: 65%; vertical-align: top;">
                            <b style="color: #1e3a8a;">📌 Pano Kullanım Kuralları:</b>
                            <div class="rules">
                                1. Konuyu tam anlamadan soru bankasına geçme.<br>
                                2. Yapamadığın soruları kesip koçluk seansında koçuna mutlaka sor.<br>
                                3. Tamamlanan her aşamayı renkli kalemle işaretle, panonu daima güncel tut.
                            </div>
                        </div>
                        <div style="display: table-cell; width: 35%; text-align: right; vertical-align: bottom;">
                            <div style="font-size: 10px; color: #475569; margin-bottom: 25px;">Eğitim Koçu Onayı & Parafı</div>
                            <div style="border-top: 1px solid #94a3b8; width: 140px; margin-left: auto; text-align: center; font-size: 9px; color: #64748b;">İmza / Tarih</div>
                        </div>
                    </div>
                </div>
            </div>
            """
            html_pages.append(p_html)

        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4 portrait;
                margin: 6mm 8mm 6mm 8mm;
            }}
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #1e293b;
                margin: 0;
                padding: 0;
                font-size: 9pt;
            }}
            .header-card {{
                border: 2px solid #2563eb;
                border-radius: 8px;
                padding: 8px 12px;
                background: #f8fafc;
                margin-bottom: 6px;
            }}
            .header-title {{
                font-size: 13pt;
                font-weight: 900;
                color: #1e3a8a;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .header-sub {{
                font-size: 8pt;
                color: #64748b;
                margin-bottom: 3px;
            }}
            .meta-grid {{
                display: table;
                width: 100%;
                margin-top: 4px;
                border-top: 1px dashed #cbd5e1;
                padding-top: 4px;
            }}
            .meta-col {{
                display: table-cell;
                width: 25%;
                font-size: 8pt;
            }}
            .meta-label {{
                font-weight: bold;
                color: #64748b;
            }}
            .meta-val {{
                color: #0f172a;
                font-weight: 700;
            }}
            .motto {{
                margin-top: 4px;
                font-size: 7.5pt;
                font-style: italic;
                color: #2563eb;
                text-align: right;
            }}
            table.checklist {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 4px;
                margin-bottom: 6px;
            }}
            table.checklist th {{
                background-color: #1e293b;
                color: #ffffff;
                font-weight: bold;
                font-size: 8pt;
                padding: 4px 2px;
                text-align: center;
                border: 1px solid #334155;
            }}
            table.checklist td {{
                padding: 2.5px 4px;
                border: 1px solid #cbd5e1;
                font-size: 8pt;
            }}
            tr:nth-child(even) {{ background-color: #f8fafc; }}
            .topic-cell {{ font-weight: 600; color: #0f172a; }}
            .box-cell {{
                text-align: center;
                width: 56px;
                font-size: 7.5pt;
                color: #475569;
            }}
            .chk-box {{
                display: inline-block;
                width: 10px;
                height: 10px;
                border: 1px solid #64748b;
                border-radius: 2px;
                vertical-align: middle;
                margin-right: 2px;
                background: #ffffff;
                line-height: 10px;
                text-align: center;
                font-size: 7pt;
            }}
            .chk-box.checked {{
                background-color: #16a34a;
                border-color: #15803d;
                color: white;
                font-weight: bold;
            }}
            .weight-badge {{
                display: inline-block;
                background: #fef3c7;
                color: #b45309;
                font-size: 7.5pt;
                font-weight: bold;
                padding: 1px 3px;
                border-radius: 3px;
                border: 1px solid #fde68a;
            }}
            .footer-box {{
                margin-top: 6px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background: #f8fafc;
            }}
            .rules {{
                font-size: 7.5pt;
                color: #334155;
                margin-top: 2px;
                line-height: 1.3;
            }}
            .page-break {{
                page-break-after: always;
            }}
        </style>
        </head>
        <body>
            {''.join(html_pages)}
        </body>
        </html>
        """
        return full_html

    def export_pdf(self):
        stu_name = f"{self.student_info.get('ad', '')}_{self.student_info.get('soyad', '')}".strip()
        default_filename = f"Pano_Takip_Cizelgesi_{stu_name}_{self.lesson_name}.pdf".replace(" ", "_")
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Pano Çizelgesini PDF Olarak Kaydet",
            os.path.expanduser(f"~/Desktop/{default_filename}"),
            "PDF Dosyaları (*.pdf)"
        )
        if not path:
            return
            
        try:
            from PyQt6.QtGui import QPageLayout, QPageSize, QFont
            from PyQt6.QtCore import QMarginsF, QSizeF
            html = self.generate_html()
            
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            
            layout = QPageLayout(printer.pageLayout())
            layout.setMargins(QMarginsF(8.0, 8.0, 8.0, 8.0))
            printer.setPageLayout(layout)
            
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Segoe UI", 9))
            doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size()))
            doc.setHtml(html)
            doc.print(printer)
            
            QMessageBox.information(self, "Kaydedildi", f"Pano takip çizelgesi başarıyla PDF olarak oluşturuldu:\n\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulurken hata çıktı:\n{e}")

    def print_dialog(self):
        try:
            from PyQt6.QtGui import QPageLayout, QPageSize, QFont
            from PyQt6.QtCore import QMarginsF, QSizeF
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            
            layout = QPageLayout(printer.pageLayout())
            layout.setMargins(QMarginsF(8.0, 8.0, 8.0, 8.0))
            printer.setPageLayout(layout)
            
            dlg = QPrintDialog(printer, self)
            if dlg.exec() == QPrintDialog.DialogCode.Accepted:
                html = self.generate_html()
                doc = QTextDocument()
                doc.setDefaultFont(QFont("Segoe UI", 9))
                doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size()))
                doc.setHtml(html)
                doc.print(printer)
                QMessageBox.information(self, "Yazdırıldı", "Pano çizelgesi yazıcıya başarıyla iletildi.")
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yazdırma hatası:\n{e}")


# ----------------------------------------------------------------------
# 5. Ana Diyalog (TopicMapDialog)
# ----------------------------------------------------------------------
class TopicMapDialog(QDialog):
    """
    Akıllı Müfredat ve Konu Hakimiyet Haritası.
    YKS/LGS maratonunda makro yol haritası, KPI göstergeleri,
    canlı filtreleme, koçluk analizleri ve pano çıktısı.
    """
    def __init__(self, parent=None, student_id=None):
        super().__init__(parent)
        self.setWindowTitle("🗺️ Akıllı Müfredat ve Konu Hakimiyet Haritası")
        self.resize(1280, 840)
        self.setMinimumSize(1100, 720)
        self.student_id = student_id
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.setStyleSheet("background-color: #f8fafc;")

        self.current_chips = [] # Aktif sayfadaki kartlar
        self.active_status_filter = "ALL" # ALL, DONE, WORKING, REVIEW, TODO

        self._init_db_table()
        self.init_ui()
        self.load_students()

    def _init_db_table(self):
        try:
            con = db.get_conn()
            con.execute("""
                CREATE TABLE IF NOT EXISTS odev_takip (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ogrenci_id INTEGER,
                    ders_adi TEXT,
                    konu_adi TEXT,
                    kitap_adi TEXT,
                    baslangic_tarihi TEXT,
                    kontrol_tarihi TEXT,
                    durum TEXT, -- 'Aktif', 'Tamamlandı'
                    created_at DATE DEFAULT CURRENT_DATE
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS koc_konu_takip (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ogrenci_id INTEGER,
                    ders_adi TEXT,
                    konu_adi TEXT,
                    kitap_id INTEGER DEFAULT 0,
                    durum INTEGER DEFAULT 0,
                    hakimiyet_puani INTEGER DEFAULT 0,
                    cozulen_soru INTEGER DEFAULT 0,
                    hedef_soru INTEGER DEFAULT 0,
                    tekrar_durumu TEXT DEFAULT '',
                    son_tekrar_tarihi TEXT DEFAULT '',
                    koc_notu TEXT DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
                )
            """)
            con.commit()
        except Exception as e:
            print("init_db_table error:", e)

    def init_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(14, 14, 14, 14)
        root_lay.setSpacing(12)
        
        # ==========================================================
        # 1. ÜST YÖNETİCİ BAŞLIK VE FİLTRE ÇUBUĞU (Executive Header)
        # ==========================================================
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        h_top_lay = QHBoxLayout(header_frame)
        h_top_lay.setContentsMargins(16, 12, 16, 12)
        h_top_lay.setSpacing(16)
        
        # Başlık ve İkon
        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_title = QLabel("🗺️ Akıllı Müfredat ve Konu Hakimiyet Haritası")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 900; color: #1e3a8a;")
        lbl_sub = QLabel("Öğrencinin tüm müfredat ilerlemesini, konu hakimiyetini ve ödev durumlarını kuşbakışı yönetin.")
        lbl_sub.setStyleSheet("font-size: 11.5px; color: #64748b;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)
        h_top_lay.addLayout(v_head, stretch=1)
        
        # Öğrenci Seçici (Windows combobox mavi hata giderilmiş)
        v_stu = QVBoxLayout()
        v_stu.setSpacing(2)
        lbl_stu_tag = QLabel("ÖĞRENCİ:")
        lbl_stu_tag.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b;")
        self.cmb_student = QComboBox()
        self.cmb_student.setFixedWidth(220)
        self.cmb_student.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 12px;
                color: #1e293b;
                font-weight: 700;
                font-size: 12.5px;
            }
            QComboBox:hover { border-color: #2563eb; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid #cbd5e1;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background: #f8fafc;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #475569;
                width: 0;
                height: 0;
            }
        """)
        self.cmb_student.currentIndexChanged.connect(self.load_map)
        v_stu.addWidget(lbl_stu_tag)
        v_stu.addWidget(self.cmb_student)
        h_top_lay.addLayout(v_stu)
        
        # Arama Kutusu
        v_search = QVBoxLayout()
        v_search.setSpacing(2)
        lbl_srch_tag = QLabel("KONU ARAMA:")
        lbl_srch_tag.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Konu filtrele...")
        self.txt_search.setFixedWidth(180)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 10px;
                color: #1e293b;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #2563eb; }
        """)
        self.txt_search.textChanged.connect(self._filter_cards)
        v_search.addWidget(lbl_srch_tag)
        v_search.addWidget(self.txt_search)
        h_top_lay.addLayout(v_search)
        
        # PANO ÇIKTISI BUTONU (Yıldız Özellik!)
        self.btn_print_board = QPushButton("🖨️ Pano İçin Çıktı Al (PDF)")
        self.btn_print_board.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_print_board.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: white;
                font-weight: bold;
                font-size: 12.5px;
                border-radius: 8px;
                padding: 10px 18px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #1e3a8a);
            }
        """)
        self.btn_print_board.clicked.connect(self.open_poster_dialog)
        h_top_lay.addWidget(self.btn_print_board)
        
        # Yenile Butonu
        btn_refresh = QPushButton("🔄")
        btn_refresh.setToolTip("Yenile")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-size: 14px;
                padding: 8px 12px;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        btn_refresh.clicked.connect(self.load_map)
        h_top_lay.addWidget(btn_refresh)
        
        root_lay.addWidget(header_frame)
        
        # ==========================================================
        # 2. ÜST KPI ÖZET ŞERİDİ (Key Performance Indicators)
        # ==========================================================
        kpi_frame = QFrame()
        kpi_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        h_kpi_lay = QHBoxLayout(kpi_frame)
        h_kpi_lay.setContentsMargins(16, 8, 16, 8)
        h_kpi_lay.setSpacing(12)
        
        self.kpi_total = self._create_kpi_card("🎯 Toplam Konu", "0", "#334155", "#f1f5f9")
        self.kpi_done = self._create_kpi_card("✅ Hakim Olunan", "0 (%0)", "#15803d", "#dcfce7")
        self.kpi_active = self._create_kpi_card("⏳ Aktif Çalışılan", "0 Konu", "#1d4ed8", "#dbeafe")
        self.kpi_review = self._create_kpi_card("⚠️ Tekrar Gereken", "0 Konu", "#b91c1c", "#fee2e2")
        
        h_kpi_lay.addWidget(self.kpi_total)
        h_kpi_lay.addWidget(self.kpi_done)
        h_kpi_lay.addWidget(self.kpi_active)
        h_kpi_lay.addWidget(self.kpi_review)
        
        # Genel Müfredat İlerleme Çubuğu
        v_prog = QVBoxLayout()
        v_prog.setSpacing(4)
        lbl_pr_title = QLabel("📊 Genel Müfredat İlerlemesi")
        lbl_pr_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 9px;
                text-align: center;
                font-weight: bold;
                font-size: 10.5px;
                color: #0f172a;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
                border-radius: 8px;
            }
        """)
        v_prog.addWidget(lbl_pr_title)
        v_prog.addWidget(self.progress_bar)
        h_kpi_lay.addLayout(v_prog, stretch=1)
        
        root_lay.addWidget(kpi_frame)
        
        # ==========================================================
        # 3. ANA ÇALIŞMA ALANI (Splitter: Sol Dersler, Orta Izgara, Sağ Analiz)
        # ==========================================================
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { background: #e2e8f0; border-radius: 4px; }")
        
        # --- SOL PANEL: Ders Listesi Gezgini ---
        self.left_sidebar = QFrame()
        self.left_sidebar.setMinimumWidth(240)
        self.left_sidebar.setMaximumWidth(300)
        self.left_sidebar.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;")
        l_lay = QVBoxLayout(self.left_sidebar)
        l_lay.setContentsMargins(10, 12, 10, 12)
        l_lay.setSpacing(8)
        
        lbl_l_title = QLabel("📚 Müfredat Dersleri")
        lbl_l_title.setStyleSheet("font-size: 13px; font-weight: 900; color: #1e3a8a; padding-left: 4px;")
        l_lay.addWidget(lbl_l_title)
        
        self.list_lessons = QListWidget()
        self.list_lessons.setFrameShape(QFrame.Shape.NoFrame)
        self.list_lessons.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 8px;
                margin-bottom: 3px;
                font-weight: 600;
                font-size: 12px;
                color: #334155;
            }
            QListWidget::item:hover {
                background: #f1f5f9;
                color: #0f172a;
            }
            QListWidget::item:selected {
                background: #eff6ff;
                color: #2563eb;
                font-weight: bold;
                border-left: 3px solid #2563eb;
            }
        """)
        self.list_lessons.currentRowChanged.connect(self.on_lesson_changed)
        l_lay.addWidget(self.list_lessons)
        splitter.addWidget(self.left_sidebar)
        
        # --- ORTA PANEL: Konu Kartları Izgarası ---
        center_panel = QFrame()
        center_panel.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(14, 12, 14, 12)
        center_layout.setSpacing(10)
        
        # Orta Panel Üst Başlık & Hızlı Filtre Butonları
        c_top_lay = QHBoxLayout()
        
        self.lbl_current_lesson = QLabel("Ders Seçiniz")
        self.lbl_current_lesson.setStyleSheet("font-size: 18px; font-weight: 900; color: #0f172a;")
        c_top_lay.addWidget(self.lbl_current_lesson)
        
        self.lbl_lesson_badge = QLabel("0 Konu")
        self.lbl_lesson_badge.setStyleSheet("background: #f1f5f9; color: #475569; font-weight: bold; font-size: 11px; padding: 3px 8px; border-radius: 6px;")
        c_top_lay.addWidget(self.lbl_lesson_badge)
        
        c_top_lay.addStretch()
        
        # Filtre Butonları (Tümü, Biten, Çalışılan, Tekrar)
        self.btn_f_all = self._create_filter_btn("Tümü", "ALL", True)
        self.btn_f_done = self._create_filter_btn("✅ Bitenler", "DONE")
        self.btn_f_active = self._create_filter_btn("⏳ Aktifler", "WORKING")
        self.btn_f_review = self._create_filter_btn("⚠️ Eksikler", "REVIEW")
        
        c_top_lay.addWidget(self.btn_f_all)
        c_top_lay.addWidget(self.btn_f_done)
        c_top_lay.addWidget(self.btn_f_active)
        c_top_lay.addWidget(self.btn_f_review)
        
        center_layout.addLayout(c_top_lay)
        
        # Stacked Pages
        self.stack = QStackedWidget()
        center_layout.addWidget(self.stack, stretch=1)
        splitter.addWidget(center_panel)
        
        # --- SAĞ PANEL: Öğrenci Hakimiyet & Koçluk Strateji Merkezi ---
        right_panel = QFrame()
        right_panel.setMinimumWidth(300)
        right_panel.setMaximumWidth(360)
        right_panel.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;")
        r_lay = QVBoxLayout(right_panel)
        r_lay.setContentsMargins(14, 14, 14, 14)
        r_lay.setSpacing(12)
        
        # 1. Öğrenci Profil Kartı
        self.student_profile_card = QFrame()
        self.student_profile_card.setObjectName("studentProfileCard")
        self.student_profile_card.setStyleSheet("""
            QFrame#studentProfileCard {
                background: #f8fafc;
                border: 1.5px solid #e2e8f0;
                border-radius: 10px;
            }
            QFrame#studentProfileCard QLabel {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        sp_lay = QVBoxLayout(self.student_profile_card)
        sp_lay.setContentsMargins(12, 10, 12, 10)
        sp_lay.setSpacing(4)
        self.lbl_sp_name = QLabel("Öğrenci Seçilmedi")
        self.lbl_sp_name.setStyleSheet("font-weight: 800; font-size: 14px; color: #0f172a;")
        self.lbl_sp_target = QLabel("Hedef: —")
        self.lbl_sp_target.setStyleSheet("font-size: 11px; color: #2563eb; font-weight: 600;")
        sp_lay.addWidget(self.lbl_sp_name)
        sp_lay.addWidget(self.lbl_sp_target)
        r_lay.addWidget(self.student_profile_card)
        
        # 2. Seçili Ders İlerleme Kartı
        self.lesson_stat_card = QFrame()
        self.lesson_stat_card.setObjectName("lessonStatCard")
        self.lesson_stat_card.setStyleSheet("""
            QFrame#lessonStatCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e3a8a, stop:1 #2563eb);
                border-radius: 10px;
                border: none;
            }
            QFrame#lessonStatCard QLabel {
                background: transparent;
                border: none;
                padding: 0px;
            }
        """)
        ls_lay = QVBoxLayout(self.lesson_stat_card)
        ls_lay.setContentsMargins(14, 12, 14, 12)
        ls_lay.setSpacing(4)
        lbl_ls_title = QLabel("DERS HAKİMİYETİ")
        lbl_ls_title.setStyleSheet("color: #bfdbfe; font-size: 10px; font-weight: 900; letter-spacing: 0.5px;")
        self.lbl_lesson_pct = QLabel("%0")
        self.lbl_lesson_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_lesson_pct.setStyleSheet("color: #ffffff; font-size: 32px; font-weight: 900;")
        self.lbl_lesson_substat = QLabel("0 / 0 Konu Bitti")
        self.lbl_lesson_substat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_lesson_substat.setStyleSheet("color: #e0e7ff; font-size: 11.5px; font-weight: 600;")
        ls_lay.addWidget(lbl_ls_title)
        ls_lay.addWidget(self.lbl_lesson_pct)
        ls_lay.addWidget(self.lbl_lesson_substat)
        r_lay.addWidget(self.lesson_stat_card)
        
        # 3. ÖSYM Çıkmış Soru & Sınav Ağırlık Tavsiyeleri
        lbl_osym_h = QLabel("🎯 Sınav Stratejisi ve Kritik Konular")
        lbl_osym_h.setStyleSheet("font-size: 12px; font-weight: bold; color: #1e3a8a;")
        r_lay.addWidget(lbl_osym_h)
        
        self.scroll_strategy = QScrollArea()
        self.scroll_strategy.setWidgetResizable(True)
        self.scroll_strategy.setFixedHeight(140)
        self.scroll_strategy.setStyleSheet("""
            QScrollArea {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                width: 6px;
                background: #f1f5f9;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 3px;
            }
        """)
        self.txt_strategy = QLabel("Ders seçildiğinde sınavda en çok soru çıkan konular burada listelenir.")
        self.txt_strategy.setWordWrap(True)
        self.txt_strategy.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                padding: 8px;
                font-size: 11px;
                color: #334155;
                line-height: 1.35;
            }
        """)
        self.scroll_strategy.setWidget(self.txt_strategy)
        r_lay.addWidget(self.scroll_strategy)
        
        # 4. Akıllı Hatırlatmalar ve Uyarılar
        lbl_alert_h = QLabel("🔔 Hatırlatmalar ve Kontrol Tarihleri")
        lbl_alert_h.setStyleSheet("font-size: 12px; font-weight: bold; color: #1e3a8a;")
        r_lay.addWidget(lbl_alert_h)
        
        self.scroll_warnings = QScrollArea()
        self.scroll_warnings.setWidgetResizable(True)
        self.scroll_warnings.setStyleSheet("border: none; background: transparent;")
        self.txt_warnings = QLabel("İnceleniyor...")
        self.txt_warnings.setWordWrap(True)
        self.txt_warnings.setStyleSheet("font-size: 11px; padding: 4px;")
        self.scroll_warnings.setWidget(self.txt_warnings)
        r_lay.addWidget(self.scroll_warnings, stretch=1)
        
        # 5. Hızlı Butonlar
        btn_print_current = QPushButton("🖨️ Bu Dersi Pano Olarak Al")
        btn_print_current.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_print_current.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px;
                font-weight: 700;
                font-size: 11.5px;
            }
            QPushButton:hover { background: #e2e8f0; border-color: #94a3b8; }
        """)
        btn_print_current.clicked.connect(self.open_poster_dialog)
        r_lay.addWidget(btn_print_current)
        
        btn_cls = QPushButton("Kapat")
        btn_cls.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cls.setStyleSheet("""
            QPushButton {
                background: white;
                color: #64748b;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px;
                font-weight: 600;
            }
            QPushButton:hover { background: #f8fafc; color: #0f172a; }
        """)
        btn_cls.clicked.connect(self.close)
        r_lay.addWidget(btn_cls)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([260, 680, 340])
        
        root_lay.addWidget(splitter, stretch=1)

    def _create_kpi_card(self, title, val, txt_color, bg_color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {bg_color};
                border-radius: 10px;
                padding: 6px 12px;
            }}
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #64748b;")
        
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"font-size: 15px; font-weight: 900; color: {txt_color};")
        
        v.addWidget(lbl_t)
        v.addWidget(lbl_v)
        card.lbl_val = lbl_v
        return card

    def _create_filter_btn(self, text, code, is_default=False):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(is_default)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #475569;
            }
            QPushButton:checked {
                background: #eff6ff;
                border: 1.5px solid #2563eb;
                color: #2563eb;
                font-weight: bold;
            }
        """)
        btn.clicked.connect(lambda: self._on_filter_clicked(code))
        return btn

    def _on_filter_clicked(self, code):
        self.active_status_filter = code
        self.btn_f_all.setChecked(code == "ALL")
        self.btn_f_done.setChecked(code == "DONE")
        self.btn_f_active.setChecked(code == "WORKING")
        self.btn_f_review.setChecked(code == "REVIEW")
        self._filter_cards()

    def load_students(self):
        try:
            con = db.get_conn()
            rows = con.execute("SELECT id, ad || ' ' || soyad, ana_grup, alt_grup, hedef_bolum FROM ogrenci ORDER BY ad").fetchall()
            self.cmb_student.blockSignals(True)
            self.cmb_student.clear()
            for r in rows:
                self.cmb_student.addItem(r[1], r[0])
            self.cmb_student.blockSignals(False)
            
            if self.student_id:
                idx = self.cmb_student.findData(self.student_id)
                if idx >= 0:
                    self.cmb_student.setCurrentIndex(idx)
            elif self.cmb_student.count() > 0:
                self.cmb_student.setCurrentIndex(0)
                
            self.load_map()
        except Exception as e:
            print("load_students error:", e)

    def load_map(self):
        student_id = self.cmb_student.currentData()
        if not student_id:
            return
            
        con = db.get_conn()
        
        # 1. Öğrenci Bilgilerini Al
        stu_row = con.execute("SELECT id, ad, soyad, ana_grup, alt_grup, hedef_bolum FROM ogrenci WHERE id=?", (student_id,)).fetchone()
        if stu_row:
            self.student_info = dict(stu_row)
            name_str = f"{stu_row['ad']} {stu_row['soyad']}"
            target_str = stu_row['hedef_bolum'] or stu_row['alt_grup'] or "Hedef Belirlenmedi"
            self.lbl_sp_name.setText(name_str)
            self.lbl_sp_target.setText(f"🎯 Hedef: {target_str} ({stu_row['ana_grup'] or 'YKS'})")
        else:
            self.student_info = {}
            
        ana_grup = self.student_info.get('ana_grup', 'YKS')
        
        # 2. Dersleri Belirle
        db.init_curriculum(con)
        config = db.get_lesson_config(con)
        
        allowed = ["LGS", "Genel"] if ana_grup == "LGS" else ["YKS", "Ara Sınıf", "Genel"]
        lessons = sorted([l for l in config.values() if l['aktif'] and (l.get('grup', 'Genel') in allowed or l.get('grup') == 'Genel')], 
                         key=lambda x: x.get('siralama', 99))
                         
        # 3. Ödev ve Hakimiyet Verilerini Çek
        # a) odev_takip
        self.assignment_map = {}
        try:
            rows = con.execute("""
                SELECT ders_adi, konu_adi, durum, kontrol_tarihi 
                FROM odev_takip WHERE ogrenci_id=?
            """, (student_id,)).fetchall()
            
            for r in rows:
                k = (r['ders_adi'], r['konu_adi'])
                if k not in self.assignment_map:
                    self.assignment_map[k] = {'active_count': 0, 'finished_count': 0, 'control_dates': []}
                if r['durum'] == 'Aktif':
                    self.assignment_map[k]['active_count'] += 1
                    if r['kontrol_tarihi']:
                        self.assignment_map[k]['control_dates'].append(r['kontrol_tarihi'])
                else:
                    self.assignment_map[k]['finished_count'] += 1
        except Exception as e:
            print("odev_takip load error:", e)
            
        # b) koc_konu_takip
        self.mastery_map = {}
        try:
            m_rows = con.execute("""
                SELECT ders_adi, konu_adi, durum, hakimiyet_puani, cozulen_soru, hedef_soru, koc_notu
                FROM koc_konu_takip WHERE ogrenci_id=?
            """, (student_id,)).fetchall()
            for r in m_rows:
                k = (r['ders_adi'], r['konu_adi'])
                self.mastery_map[k] = {
                    'durum': r['durum'],
                    'hakimiyet_puani': r['hakimiyet_puani'],
                    'cozulen_soru': r['cozulen_soru'],
                    'hedef_soru': r['hedef_soru'],
                    'koc_notu': r['koc_notu']
                }
        except Exception as e:
            print("koc_konu_takip load error:", e)

        # 4. Sol Listeyi ve Orta Stack Sayfalarını İnşa Et
        self.list_lessons.blockSignals(True)
        self.list_lessons.clear()
        
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
            
        self.current_chips = []
        self.all_lessons_data = [] # [(lesson_name, topics)]
        self.global_stats = {'total': 0, 'done': 0, 'active': 0, 'review': 0}
        self.upcoming_warnings = []
        self.lesson_stats = {} # lname -> {total, done}
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        
        # İkon eşleştirici
        icon_map = {
            "matematik": "📐", "problemler": "🧩", "geometri": "🧮",
            "fizik": "⚡", "kimya": "🧪", "biyoloji": "🧬",
            "türkçe": "📖", "paragraf": "📑", "tarih": "📜",
            "coğrafya": "🌍", "felsefe": "🏛️", "edebiyat": "📚",
            "fen": "🔬", "ingilizce": "🇬🇧", "din": "🕌"
        }
        
        for less in lessons:
            lname = less['ad']
            lid = less['id']
            topics = [dict(t) for t in db.ders_konularini_cek(con, lid)]
            self.all_lessons_data.append((lname, topics))
            
            # Ders İkonu Bul
            ico = "📘"
            for k_ico, v_ico in icon_map.items():
                if k_ico in lname.lower():
                    ico = v_ico
                    break
                    
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(4, 4, 4, 4)
            
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            
            content = QWidget()
            content.setStyleSheet("background: transparent;")
            grid = QGridLayout(content)
            grid.setSpacing(12)
            grid.setContentsMargins(8, 8, 8, 8)
            
            l_done = 0
            col = 0
            row = 0
            page_chips = []
            
            for t in topics:
                tname = t['konu']
                self.global_stats['total'] += 1
                
                # Birleşik Veri
                k = (lname, tname)
                asgn = self.assignment_map.get(k, {'active_count': 0, 'finished_count': 0, 'control_dates': []})
                mstr = self.mastery_map.get(k, {'durum': 0, 'hakimiyet_puani': 0, 'cozulen_soru': 0})
                
                ctrls = sorted(asgn.get('control_dates', []))
                next_ctrl = ctrls[0] if ctrls else None
                if next_ctrl:
                    if next_ctrl < today_str:
                        self.upcoming_warnings.append(f"🚨 <b>{lname} - {tname}</b> kontrolü GECİKTİ! ({next_ctrl})")
                    elif next_ctrl <= QDate.currentDate().addDays(3).toString("yyyy-MM-dd"):
                        self.upcoming_warnings.append(f"⏰ <b>{lname} - {tname}</b> kontrolü yaklaştı ({next_ctrl})")
                
                # Durum ve KPI hesaplama
                durum = mstr.get('durum', 0)
                active_count = asgn.get('active_count', 0)
                finished_count = asgn.get('finished_count', 0)
                
                if active_count > 0:
                    self.global_stats['active'] += 1
                elif durum == 4 or (finished_count > 0 and durum != 3):
                    self.global_stats['done'] += 1
                    l_done += 1
                elif durum == 3:
                    self.global_stats['review'] += 1
                
                extra_payload = {
                    'active_count': active_count,
                    'finished_count': finished_count,
                    'next_control': next_ctrl,
                    'mastery_durum': durum,
                    'mastery_score': mstr.get('hakimiyet_puani', 0),
                    'cozulen_soru': mstr.get('cozulen_soru', 0)
                }
                
                chip = TopicChip(t, durum, extra_data=extra_payload)
                chip.lesson_name = lname
                chip.clicked.connect(lambda ch=chip, ln=lname: self.on_chip_click(ch, ln))
                grid.addWidget(chip, row, col)
                page_chips.append(chip)
                
                col += 1
                if col >= 3:
                    col = 0
                    row += 1
                    
            scroll.setWidget(content)
            pl.addWidget(scroll)
            page.chips = page_chips
            self.stack.addWidget(page)
            
            # Ders listesi öğesi rozeti
            total_t = len(topics)
            self.lesson_stats[lname] = {'total': total_t, 'done': l_done}
            pct_l = int((l_done / total_t) * 100) if total_t > 0 else 0
            
            item_txt = f"{ico} {lname}  ({l_done}/{total_t})"
            l_item = QListWidgetItem(item_txt)
            if pct_l >= 80:
                l_item.setForeground(QColor("#15803d"))
            self.list_lessons.addItem(l_item)
            
        self.list_lessons.blockSignals(False)
        if self.list_lessons.count() > 0:
            self.list_lessons.setCurrentRow(0)
            
        self.update_kpis()
        self.update_sidebar()

    def on_lesson_changed(self, row):
        if row >= 0 and row < self.stack.count():
            self.stack.setCurrentIndex(row)
            curr_item = self.list_lessons.item(row)
            if curr_item:
                # İkonu ayıkla
                txt = curr_item.text().split("  (")[0]
                self.lbl_current_lesson.setText(txt)
                
            page = self.stack.widget(row)
            self.current_chips = getattr(page, 'chips', [])
            self.lbl_lesson_badge.setText(f"{len(self.current_chips)} Konu")
            
            self._filter_cards()
            self.update_sidebar()

    def _filter_cards(self):
        query = self.txt_search.text().lower().strip()
        filt = self.active_status_filter
        
        for chip in self.current_chips:
            tname = chip.topic_data.get('konu', '').lower()
            text_matches = (not query) or (query in tname)
            
            status_matches = True
            active = chip.extra_data.get('active_count', 0)
            finished = chip.extra_data.get('finished_count', 0)
            m_durum = chip.extra_data.get('mastery_durum', 0)
            
            if filt == "DONE":
                status_matches = (m_durum == 4) or (finished > 0 and active == 0 and m_durum != 3)
            elif filt == "WORKING":
                status_matches = (active > 0) or (m_durum in (1, 2))
            elif filt == "REVIEW":
                status_matches = (m_durum == 3)
            elif filt == "TODO":
                status_matches = (active == 0 and finished == 0 and m_durum == 0)
                
            chip.setVisible(text_matches and status_matches)

    def on_chip_click(self, chip: TopicChip, lesson_name):
        student_id = self.cmb_student.currentData()
        if not student_id:
            return
            
        dlg = AssignmentManagerDialog(student_id, lesson_name, chip.topic_data['konu'], self)
        dlg.exec()
        # Yenile
        self.load_map()

    def update_kpis(self):
        total = self.global_stats['total']
        done = self.global_stats['done']
        active = self.global_stats['active']
        review = self.global_stats['review']
        
        pct = int((done / total) * 100) if total > 0 else 0
        
        self.kpi_total.lbl_val.setText(str(total))
        self.kpi_done.lbl_val.setText(f"{done} (%{pct})")
        self.kpi_active.lbl_val.setText(f"{active} Konu")
        self.kpi_review.lbl_val.setText(f"{review} Konu")
        self.progress_bar.setValue(pct)

    def update_sidebar(self):
        curr_row = self.list_lessons.currentRow()
        if curr_row < 0:
            return
            
        curr_item = self.list_lessons.item(curr_row)
        if not curr_item:
            return
            
        raw_text = curr_item.text()
        parts = raw_text.split("  (")
        lname = parts[0]
        for p_ico in ["📐 ", "🧩 ", "🧮 ", "⚡ ", "🧪 ", "🧬 ", "📖 ", "📑 ", "📜 ", "🌍 ", "🏛️ ", "📚 ", "🔬 ", "🇬🇧 ", "🕌 ", "📘 "]:
            lname = lname.replace(p_ico, "")
        lname = lname.strip()
        
        # Seçili ders istatistiği
        st = self.lesson_stats.get(lname, {'total': 0, 'done': 0})
        total = st['total']
        done = st['done']
        pct = int((done / total) * 100) if total > 0 else 0
        
        self.lbl_lesson_pct.setText(f"%{pct}")
        self.lbl_lesson_substat.setText(f"{done} / {total} Konu Tamamlandı")
        
        # ÖSYM Kritik Konular Analizi
        high_yield_topics = []
        for chip in self.current_chips:
            tname = chip.topic_data.get('konu', '')
            info = get_topic_info(tname)
            imp = info.get("importance", "")
            q_cnt = info.get("questions", "")
            if "5/5" in imp or "Yüksek" in imp or "2-" in q_cnt or "3-" in q_cnt or "4-" in q_cnt or "10-" in q_cnt:
                m_durum = chip.extra_data.get('mastery_durum', 0)
                is_done = m_durum == 4 or (chip.extra_data.get('finished_count', 0) > 0 and chip.extra_data.get('active_count', 0) == 0)
                status_icon = "✅" if is_done else ("⏳" if chip.extra_data.get('active_count', 0) > 0 else "⚪")
                high_yield_topics.append(f"{status_icon} <b>{tname}</b>: {q_cnt}")
                
        if high_yield_topics:
            strat_html = "<b style='color: #1e3a8a;'>ÖSYM'de En Çok Soru Çıkan Konular:</b><br><br>"
            strat_html += "<br>".join(high_yield_topics[:6])
            if len(high_yield_topics) > 6:
                strat_html += f"<br><i>...ve {len(high_yield_topics)-6} kritik konu daha</i>"
            self.txt_strategy.setText(strat_html)
        else:
            self.txt_strategy.setText("Bu derste tüm konular dengeli dağılıma sahiptir. Düzenli çalışma önerilir.")
            
        # Uyarılar
        if self.upcoming_warnings:
            self.txt_warnings.setStyleSheet("""
                QLabel { 
                    color: #b91c1c; 
                    background: #fef2f2; 
                    padding: 8px; 
                    border: 1px solid #fecaca;
                    border-radius: 6px; 
                }
            """)
            msg = "<br><br>".join(self.upcoming_warnings[:6])
            if len(self.upcoming_warnings) > 6:
                msg += f"<br><br>...ve {len(self.upcoming_warnings)-6} bildirim daha"
            self.txt_warnings.setText(msg)
        else:
            self.txt_warnings.setText("👍 Yaklaşan veya geciken kontrol görünmüyor. Her şey yolunda!")
            self.txt_warnings.setStyleSheet("color: #166534; background: #f0fdf4; padding: 10px; border-radius: 6px;")

    def open_poster_dialog(self):
        """Pano Çıktısı Sihirbazını Açar"""
        curr_row = self.list_lessons.currentRow()
        if curr_row < 0 or not self.all_lessons_data:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir ders seçiniz.")
            return
            
        lname, topics = self.all_lessons_data[curr_row]
        
        # Stats map
        topic_stats_map = {}
        for chip in self.current_chips:
            topic_stats_map[(chip.lesson_name, chip.topic_data.get('konu', ''))] = chip.extra_data
            
        dlg = StudyBoardPosterDialog(
            student_info=self.student_info,
            lesson_name=lname,
            topics=topics,
            topic_stats_map=topic_stats_map,
            all_lessons_data=self.all_lessons_data,
            parent=self
        )
        dlg.exec()
