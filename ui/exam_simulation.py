# -*- coding: utf-8 -*-
"""
Gerçek Sınav Simülatörü & İnteraktif Optik Sınav Salonu (ExamSimulationDialog)
- ÖSYM ve MEB standartlarında gerçek sınav süresi ve salon saati
- İnteraktif Optik Kodlama Formu (A, B, C, D, E işaretleme)
- Turlama tekniği ve şüpheli soru takibi (Flagged questions)
- Ders bazlı harcanan süre ölçümü (Time spent per subject)
- Cevap anahtarı ile anında otomatik optik okuma ve puanlama
- Doğrudan denemeler & deneme_sonuclari DB entegrasyonu
"""

import sys
import os
import sqlite3
import json
import datetime as dt
from typing import Dict, List, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QLCDNumber, QProgressBar, QFrame, QMessageBox, QTimeEdit, QWidget, 
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QScrollArea, QTabWidget, QRadioButton, QButtonGroup, QCheckBox,
    QGridLayout, QSpinBox, QDoubleSpinBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QTime, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon, QTextDocument, QPageLayout

import db
from services.exam_score_calculator import (
    calculate_exam_score, TURKEY_BENCHMARKS
)

# ----------------------------------------------------------------------
# Standart Sınav Ders ve Soru Dağılımları
# ----------------------------------------------------------------------
EXAM_STRUCTURES = {
    "YKS - TYT (165 dk - 120 Soru)": {
        "type_code": "TYT",
        "minutes": 165,
        "options_count": 5, # A B C D E
        "exit_ban_minutes": 120, # İlk 120 dk çıkış yasak
        "last_ban_minutes": 15,  # Son 15 dk çıkış yasak
        "subjects": [
            {"name": "Türkçe", "questions": 40},
            {"name": "Sosyal", "questions": 20},
            {"name": "Matematik", "questions": 40},
            {"name": "Fen", "questions": 20}
        ]
    },
    "YKS - AYT Sayısal (180 dk - 80 Soru)": {
        "type_code": "AYT",
        "alan": "SAY",
        "minutes": 180,
        "options_count": 5,
        "exit_ban_minutes": 135,
        "last_ban_minutes": 15,
        "subjects": [
            {"name": "Matematik", "questions": 40},
            {"name": "Fizik", "questions": 14},
            {"name": "Kimya", "questions": 13},
            {"name": "Biyoloji", "questions": 13}
        ]
    },
    "YKS - AYT Eşit Ağırlık (180 dk - 80 Soru)": {
        "type_code": "AYT",
        "alan": "EA",
        "minutes": 180,
        "options_count": 5,
        "exit_ban_minutes": 135,
        "last_ban_minutes": 15,
        "subjects": [
            {"name": "Matematik", "questions": 40},
            {"name": "Edebiyat", "questions": 24},
            {"name": "Tarih", "questions": 10},
            {"name": "Coğrafya", "questions": 6}
        ]
    },
    "LGS 1. Oturum - Sözel (75 dk - 50 Soru)": {
        "type_code": "LGS",
        "minutes": 75,
        "options_count": 4, # A B C D
        "exit_ban_minutes": 50,
        "last_ban_minutes": 15,
        "subjects": [
            {"name": "Türkçe", "questions": 20},
            {"name": "İnkılap", "questions": 10},
            {"name": "Din", "questions": 10},
            {"name": "İngilizce", "questions": 10}
        ]
    },
    "LGS 2. Oturum - Sayısal (80 dk - 40 Soru)": {
        "type_code": "LGS",
        "minutes": 80,
        "options_count": 4,
        "exit_ban_minutes": 55,
        "last_ban_minutes": 15,
        "subjects": [
            {"name": "Matematik", "questions": 20},
            {"name": "Fen", "questions": 20}
        ]
    },
    "Branş Denemesi (Özel Süre & Ders)": {
        "type_code": "BRANŞ",
        "minutes": 45,
        "options_count": 5,
        "exit_ban_minutes": 30,
        "last_ban_minutes": 10,
        "subjects": [
            {"name": "Matematik", "questions": 40}
        ]
    }
}

# ----------------------------------------------------------------------
# Tek Bir Optik Soru Satırı Bileşeni (OpticQuestionRow)
# ----------------------------------------------------------------------
class OpticQuestionRow(QFrame):
    """ÖSYM standardında gerçekçi optik form satırı."""
    selection_changed = pyqtSignal(int, str, bool) # q_num, selected_option, is_flagged
    
    def __init__(self, q_num: int, options_count: int = 5, parent=None):
        super().__init__(parent)
        self.q_num = q_num
        self.options_count = options_count
        self.selected_opt = ""
        self.is_flagged = False
        
        self.setFixedHeight(34)
        
        h_lay = QHBoxLayout(self)
        h_lay.setContentsMargins(4, 2, 4, 2)
        h_lay.setSpacing(5)
        
        # Soru Numarası (01, 02 ... 40 - Net, belirgin ve ortalı)
        self.lbl_num = QLabel(f"{q_num:02d}")
        self.lbl_num.setFixedSize(28, 24)
        self.lbl_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_lay.addWidget(self.lbl_num)
        
        # Baloncuk Butonları (A, B, C, D, E)
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.option_buttons = {}
        
        letters = ["A", "B", "C", "D", "E"][:options_count]
        for letter in letters:
            btn = QPushButton(letter)
            btn.setCheckable(True)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    border: 1.5px solid #94a3b8;
                    border-radius: 12px;
                    background-color: #ffffff;
                    color: #1e293b;
                    font-weight: 800;
                    font-size: 10.5px;
                    padding: 0px;
                    margin: 0px;
                }
                QPushButton:hover {
                    border-color: #2563eb;
                    background-color: #eff6ff;
                    color: #1d4ed8;
                }
                QPushButton:checked {
                    background-color: #0f172a; /* Kurşun kalem grafit siyahı */
                    color: #ffffff;
                    border: 1.5px solid #0f172a;
                    font-weight: 900;
                }
            """)
            btn.clicked.connect(lambda _, l=letter: self._on_option_clicked(l))
            self.btn_group.addButton(btn)
            self.option_buttons[letter] = btn
            h_lay.addWidget(btn)
            
        h_lay.addSpacing(2)
        
        # Turlama / Şüpheli Bayrak Butonu
        self.btn_flag = QPushButton("?")
        self.btn_flag.setCheckable(True)
        self.btn_flag.setToolTip("Şüpheli Soru (Turlama Tekniği)")
        self.btn_flag.setFixedSize(22, 22)
        self.btn_flag.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_flag.setStyleSheet("""
            QPushButton {
                border: 1.5px solid #cbd5e1;
                border-radius: 4px;
                background-color: #f8fafc;
                color: #64748b;
                font-weight: 900;
                font-size: 10px;
            }
            QPushButton:hover { border-color: #f59e0b; color: #d97706; }
            QPushButton:checked {
                background-color: #fef08a;
                border-color: #eab308;
                color: #854d0e;
                font-weight: 900;
            }
        """)
        self.btn_flag.clicked.connect(self._on_flag_clicked)
        h_lay.addWidget(self.btn_flag)
        
        # Temizle Butonu
        btn_clr = QPushButton("✕")
        btn_clr.setToolTip("Cevabı temizle")
        btn_clr.setFixedSize(18, 18)
        btn_clr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clr.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #94a3b8;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { color: #dc2626; }
        """)
        btn_clr.clicked.connect(self._clear_selection)
        h_lay.addWidget(btn_clr)

        self._update_style()

    def _update_style(self):
        if self.is_flagged:
            border_css = "border-left: 4px solid #f59e0b; background-color: #fefce8;"
            num_style = "background-color: #fef08a; color: #854d0e; font-weight: 900; font-size: 11px; border-radius: 4px; border: 1px solid #facc15;"
        elif self.selected_opt:
            border_css = "border-left: 4px solid #2563eb; background-color: #eff6ff;"
            num_style = "background-color: #dbeafe; color: #1e40af; font-weight: 900; font-size: 11px; border-radius: 4px; border: 1px solid #93c5fd;"
        else:
            border_css = "border-left: 2px solid transparent; background-color: #ffffff;"
            num_style = "background-color: #f1f5f9; color: #334155; font-weight: 800; font-size: 11px; border-radius: 4px; border: 1px solid #e2e8f0;"

        self.setStyleSheet(f"""
            QFrame {{
                {border_css}
                border-bottom: 1px solid #f1f5f9;
                border-radius: 4px;
            }}
            QFrame:hover {{
                background-color: #f8fafc;
            }}
        """)
        self.lbl_num.setStyleSheet(num_style)

    def _on_option_clicked(self, letter: str):
        self.selected_opt = letter
        self._update_style()
        self.selection_changed.emit(self.q_num, self.selected_opt, self.is_flagged)
        
    def _on_flag_clicked(self):
        self.is_flagged = self.btn_flag.isChecked()
        self._update_style()
        self.selection_changed.emit(self.q_num, self.selected_opt, self.is_flagged)

    def _clear_selection(self):
        checked = self.btn_group.checkedButton()
        if checked:
            self.btn_group.setExclusive(False)
            checked.setChecked(False)
            self.btn_group.setExclusive(True)
        self.selected_opt = ""
        self._update_style()
        self.selection_changed.emit(self.q_num, "", self.is_flagged)


# ----------------------------------------------------------------------
# Ana Simülatör Diyaloğu
# ----------------------------------------------------------------------
class ExamSimulationDialog(QDialog):
    """
    Gerçek Sınav Simülatörü ve Optik Sınav Salonu.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⏳ Gerçek Sınav Simülatörü & Optik Sınav Salonu")
        self.resize(1180, 760)
        self.setMinimumSize(1020, 700)
        self.setStyleSheet("""
            QDialog, QWidget {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QDialog {
                background-color: #f8fafc;
            }
        """)

        self.remaining_seconds = 0
        self.total_seconds = 0
        self.current_exam_config = {}
        self.student_answers = {} # subj -> {q_num: opt}
        self.flagged_questions = set() # (subj, q_num)
        self.subject_time_spent = {} # subj -> seconds
        self.active_subject = ""
        self.last_tick_time = dt.datetime.now()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._timer_tick)
        
        self.stack = QStackedWidget()
        self._init_setup_ui()
        self._init_exam_ui()
        self._init_results_ui()
        
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.addWidget(self.stack)
        
        self._load_students()

    # ==========================================================
    # EKRAN 1: Sınav Başlatma & Konfigürasyon
    # ==========================================================
    def _init_setup_ui(self):
        self.page_setup = QWidget()
        lay = QVBoxLayout(self.page_setup)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(16)
        
        # Başlık Kartı
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #2563eb);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        hl = QVBoxLayout(header_card)
        lbl_t = QLabel("⏳ Gerçek Sınav Simülatörü & Optik Sınav Salonu")
        lbl_t.setStyleSheet("font-size: 22px; font-weight: 900; color: white;")
        lbl_sub = QLabel("ÖSYM ve MEB sınav standartlarında gerçek süre, salon saati, interaktif optik kodlama ve anında analiz")
        lbl_sub.setStyleSheet("font-size: 12px; color: #bfdbfe;")
        hl.addWidget(lbl_t)
        hl.addWidget(lbl_sub)
        lay.addWidget(header_card)
        
        # Ayarlar Gövdesi
        body_frame = QFrame()
        body_frame.setObjectName("setupBodyFrame")
        body_frame.setStyleSheet("""
            QFrame#setupBodyFrame {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 18px;
            }
            QFrame#setupBodyFrame QLabel {
                background: transparent;
                border: none;
                color: #1e293b;
            }
            QFrame#setupBodyFrame QCheckBox {
                background: transparent;
                border: none;
                color: #1e293b;
                font-size: 13px;
                font-weight: 600;
                spacing: 10px;
                padding: 6px 2px;
            }
            QFrame#setupBodyFrame QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #94a3b8;
                border-radius: 5px;
                background-color: #ffffff;
            }
            QFrame#setupBodyFrame QCheckBox::indicator:hover {
                border-color: #2563eb;
                background-color: #eff6ff;
            }
            QFrame#setupBodyFrame QCheckBox::indicator:checked {
                background-color: #2563eb;
                border-color: #1d4ed8;
            }
        """)
        grid = QGridLayout(body_frame)
        grid.setSpacing(14)
        
        # 1. Sınav Türü
        grid.addWidget(QLabel("<b>📝 Sınav Türü:</b>"), 0, 0)
        self.cmb_exam_type = QComboBox()
        self.cmb_exam_type.addItems(list(EXAM_STRUCTURES.keys()))
        self.cmb_exam_type.setStyleSheet("padding: 8px; border: 1.5px solid #cbd5e1; border-radius: 6px; font-weight: bold; background: white;")
        self.cmb_exam_type.currentIndexChanged.connect(self._on_exam_type_changed)
        grid.addWidget(self.cmb_exam_type, 0, 1)
        
        # 2. Öğrenci
        grid.addWidget(QLabel("<b>👤 Öğrenci:</b>"), 1, 0)
        self.cmb_student = QComboBox()
        self.cmb_student.setEditable(True)
        self.cmb_student.setStyleSheet("padding: 8px; border: 1.5px solid #cbd5e1; border-radius: 6px; background: white;")
        grid.addWidget(self.cmb_student, 1, 1)
        
        # 3. Deneme Adı
        grid.addWidget(QLabel("<b>🏷️ Deneme Adı:</b>"), 2, 0)
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Örn: 3D Türkiye Geneli Deneme-1")
        self.inp_name.setStyleSheet("padding: 8px; border: 1.5px solid #cbd5e1; border-radius: 6px; background: white;")
        grid.addWidget(self.inp_name, 2, 1)
        
        # 4. Cevap Anahtarı (İsteğe bağlı)
        grid.addWidget(QLabel("<b>🔑 Cevap Anahtarı (İsteğe Bağlı):</b>"), 3, 0)
        self.inp_answer_key = QLineEdit()
        self.inp_answer_key.setPlaceholderText("Örn: 1A 2C 3D 4B veya ABCDE... (Sınav bitince anında puanlar)")
        self.inp_answer_key.setStyleSheet("padding: 8px; border: 1.5px solid #cbd5e1; border-radius: 6px; background: white;")
        grid.addWidget(self.inp_answer_key, 3, 1)
        
        # 5. Gerçekçi Mod Seçenekleri
        grid.addWidget(QLabel("<b>⚙️ Salon Kuralları:</b>"), 4, 0)
        v_opts = QVBoxLayout()
        self.chk_salon_clock = QCheckBox("Resmi ÖSYM Salon Saati Modu (10:15 - 13:00 Senkronizasyonu)")
        self.chk_salon_clock.setChecked(True)
        self.chk_exit_ban = QCheckBox("Salondan Çıkış Yasağı Kuralı (İlk 120 dk ve son 15 dk uyarısı)")
        self.chk_exit_ban.setChecked(True)
        self.chk_turlama = QCheckBox("Turlama Tekniği & Şüpheli Soru Takibi Aktif")
        self.chk_turlama.setChecked(True)
        v_opts.addWidget(self.chk_salon_clock)
        v_opts.addWidget(self.chk_exit_ban)
        v_opts.addWidget(self.chk_turlama)
        grid.addLayout(v_opts, 4, 1)
        
        lay.addWidget(body_frame)
        lay.addStretch()
        
        # Başlat Butonu
        self.btn_start = QPushButton("🚀 Gerçek Sınav Modunu Başlat")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: white;
                font-weight: 900;
                font-size: 16px;
                padding: 14px;
                border-radius: 10px;
                border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        self.btn_start.clicked.connect(self._start_exam)
        lay.addWidget(self.btn_start)
        
        self.stack.addWidget(self.page_setup)

    def _load_students(self):
        try:
            con = db.get_conn()
            rows = con.execute("SELECT id, ad || ' ' || soyad as full_name FROM ogrenci WHERE aktif=1 ORDER BY ad").fetchall()
            self.cmb_student.clear()
            for r in rows:
                self.cmb_student.addItem(r["full_name"], r["id"])
            con.close()
        except: pass

    def _on_exam_type_changed(self):
        pass

    # ==========================================================
    # EKRAN 2: Sınav Salonu & İnteraktif Optik Kodlama
    # ==========================================================
    def _init_exam_ui(self):
        self.page_exam = QWidget()
        lay = QVBoxLayout(self.page_exam)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)
        
        # --- Üst Durum Çubuğu ---
        top_bar = QFrame()
        top_bar.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 8px 14px;")
        h_top = QHBoxLayout(top_bar)
        h_top.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_exam_banner = QLabel("TYT Denemesi")
        self.lbl_exam_banner.setStyleSheet("font-size: 15px; font-weight: 900; color: #1e3a8a;")
        h_top.addWidget(self.lbl_exam_banner)
        
        h_top.addStretch()
        
        self.lbl_exit_ban_badge = QLabel("⚠️ Çıkış Yasağı Süresindesiniz")
        self.lbl_exit_ban_badge.setStyleSheet("background: #fef3c7; color: #b45309; font-weight: bold; font-size: 11px; padding: 4px 10px; border-radius: 6px;")
        h_top.addWidget(self.lbl_exit_ban_badge)
        
        btn_finish = QPushButton("🏁 Sınavı Bitir")
        btn_finish.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_finish.setStyleSheet("background: #dc2626; color: white; font-weight: bold; border-radius: 6px; padding: 6px 14px;")
        btn_finish.clicked.connect(self._confirm_finish_exam)
        h_top.addWidget(btn_finish)
        
        lay.addWidget(top_bar)
        
        # --- Ana İki Kolonlu Gövde ---
        h_body = QHBoxLayout()
        h_body.setSpacing(12)
        
        # SOL KOLON: Sayaç & Turlama Paneli (320px)
        left_box = QFrame()
        left_box.setFixedWidth(290)
        left_box.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;")
        v_left = QVBoxLayout(left_box)
        v_left.setSpacing(10)
        
        # 1. Salon Saati & Sayaç
        lbl_clk_title = QLabel("⏳ SALON SAATİ & KALAN SÜRE")
        lbl_clk_title.setStyleSheet("font-size: 11px; font-weight: 900; color: #64748b;")
        v_left.addWidget(lbl_clk_title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.lcd = QLCDNumber()
        self.lcd.setDigitCount(8)
        self.lcd.setFixedHeight(85)
        self.lcd.setStyleSheet("border: 2px solid #2563eb; border-radius: 8px; background: #0f172a; color: #38bdf8;")
        v_left.addWidget(self.lcd)
        
        self.prog_time = QProgressBar()
        self.prog_time.setFixedHeight(10)
        self.prog_time.setTextVisible(False)
        self.prog_time.setStyleSheet("QProgressBar { border-radius: 5px; background: #e2e8f0; } QProgressBar::chunk { background: #10b981; border-radius: 5px; }")
        v_left.addWidget(self.prog_time)
        
        # 2. Canlı İlerleme İstatistikleri
        stat_frame = QFrame()
        stat_frame.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px;")
        g_st = QGridLayout(stat_frame)
        g_st.setSpacing(6)
        
        def mini_st(title, val_attr):
            l1 = QLabel(title); l1.setStyleSheet("font-size: 10px; color: #64748b; font-weight: bold;")
            l2 = QLabel("0"); l2.setStyleSheet("font-size: 15px; font-weight: 900; color: #1e3a8a;")
            setattr(self, val_attr, l2)
            v = QVBoxLayout(); v.setSpacing(0); v.addWidget(l1); v.addWidget(l2)
            return v
            
        g_st.addLayout(mini_st("İŞARETLENEN", "lbl_stat_answered"), 0, 0)
        g_st.addLayout(mini_st("BOŞ KALAN", "lbl_stat_empty"), 0, 1)
        g_st.addLayout(mini_st("ŞÜPHELİ (TURLAMA)", "lbl_stat_flagged"), 1, 0)
        g_st.addLayout(mini_st("TOPLAM SORU", "lbl_stat_total"), 1, 1)
        v_left.addWidget(stat_frame)
        
        # 3. Turlama Listesi (Şüpheli Sorular)
        lbl_tur_h = QLabel("📌 Geri Dönülecek Şüpheli Sorular:")
        lbl_tur_h.setStyleSheet("font-weight: 800; font-size: 11px; color: #b45309;")
        v_left.addWidget(lbl_tur_h)
        
        self.scroll_flags = QScrollArea()
        self.scroll_flags.setWidgetResizable(True)
        self.scroll_flags.setStyleSheet("border: 1px solid #fed7aa; background: #fffbeb; border-radius: 6px;")
        self.lbl_flagged_list = QLabel("Henüz şüpheli işaretlenen soru yok.")
        self.lbl_flagged_list.setWordWrap(True)
        self.lbl_flagged_list.setStyleSheet("font-size: 10.5px; color: #78350f; padding: 8px;")
        self.scroll_flags.setWidget(self.lbl_flagged_list)
        v_left.addWidget(self.scroll_flags, stretch=1)
        
        # 4. Ders Süre Dağılımı Özeti
        self.lbl_time_summary = QLabel("⏱️ Ders süreleri canlı kaydediliyor...")
        self.lbl_time_summary.setStyleSheet("font-size: 10.5px; color: #64748b; font-style: italic;")
        v_left.addWidget(self.lbl_time_summary)
        
        h_body.addWidget(left_box, stretch=3)
        
        # SAĞ KOLON: İnteraktif Optik Kodlama Formu
        right_box = QFrame()
        right_box.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px;")
        v_right = QVBoxLayout(right_box)
        v_right.setSpacing(6)
        
        lbl_opt_h = QLabel("📝 ÖSYM İNTERAKTİF OPTİK KODLAMA FORMU")
        lbl_opt_h.setStyleSheet("font-size: 13px; font-weight: 900; color: #1e3a8a; padding-left: 6px;")
        v_right.addWidget(lbl_opt_h)
        
        self.tab_subjects = QTabWidget()
        self.tab_subjects.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
            QTabBar::tab { font-weight: 700; padding: 8px 14px; background: #f1f5f9; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: white; color: #2563eb; border-bottom: 2px solid #2563eb; }
        """)
        self.tab_subjects.currentChanged.connect(self._on_subject_tab_changed)
        v_right.addWidget(self.tab_subjects, stretch=1)
        
        h_body.addWidget(right_box, stretch=7)
        lay.addLayout(h_body, stretch=1)
        
        self.stack.addWidget(self.page_exam)

    def _start_exam(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir deneme sınavı adı giriniz.")
            return
            
        type_str = self.cmb_exam_type.currentText()
        self.current_exam_config = EXAM_STRUCTURES.get(type_str, EXAM_STRUCTURES["YKS - TYT (165 dk - 120 Soru)"])
        
        self.total_seconds = self.current_exam_config["minutes"] * 60
        self.remaining_seconds = self.total_seconds
        
        stu_name = self.cmb_student.currentText()
        self.lbl_exam_banner.setText(f"{type_str} • {name} ({stu_name})")
        
        # Optik Formu İnşa Et
        self._build_optical_form()
        
        # Başlat
        self.stack.setCurrentIndex(1)
        self.last_tick_time = dt.datetime.now()
        self.timer.start(1000)
        self._update_lcd()

    def _build_optical_form(self):
        self.tab_subjects.clear()
        self.student_answers = {}
        self.flagged_questions = set()
        self.subject_time_spent = {}
        self.nav_buttons = {}
        self.optic_rows = {}
        
        subjects = self.current_exam_config.get("subjects", [])
        opts_cnt = self.current_exam_config.get("options_count", 5)
        
        total_q = sum(s["questions"] for s in subjects)
        self.lbl_stat_total.setText(str(total_q))
        self.lbl_stat_empty.setText(str(total_q))
        self.lbl_stat_answered.setText("0")
        self.lbl_stat_flagged.setText("0")
        
        for subj in subjects:
            s_name = subj["name"]
            q_cnt = subj["questions"]
            self.student_answers[s_name] = {}
            self.subject_time_spent[s_name] = 0
            
            # Sayfa Ana Taşıyıcısı
            tab_page = QWidget()
            t_lay = QVBoxLayout(tab_page)
            t_lay.setContentsMargins(6, 6, 6, 6)
            t_lay.setSpacing(6)

            # Optik Soru Listesi Taşıyıcısı (Gerçekçi ÖSYM Kağıdı Düzeni)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none; background: transparent;")
            
            content = QWidget()
            cols_count = 2 if q_cnt <= 20 else 3
            grid = QGridLayout(content)
            grid.setSpacing(3)
            grid.setContentsMargins(6, 6, 6, 6)
            per_col = (q_cnt + cols_count - 1) // cols_count

            # Sütun Başlıkları Ekle (NO  A  B  C  D  E   ?)
            letters = ["A", "B", "C", "D", "E"][:opts_cnt]
            for col_i in range(cols_count):
                hdr = QFrame()
                hdr.setFixedHeight(28)
                hdr.setStyleSheet("background-color: #f1f5f9; border-radius: 5px; border: 1px solid #cbd5e1;")
                hl = QHBoxLayout(hdr)
                hl.setContentsMargins(4, 2, 4, 2)
                hl.setSpacing(5)
                
                l_no = QLabel("NO")
                l_no.setFixedSize(28, 22)
                l_no.setAlignment(Qt.AlignmentFlag.AlignCenter)
                l_no.setStyleSheet("font-weight: 900; font-size: 10px; color: #334155; background: transparent; border: none;")
                hl.addWidget(l_no)
                
                for lt in letters:
                    l_opt = QLabel(lt)
                    l_opt.setFixedSize(24, 22)
                    l_opt.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    l_opt.setStyleSheet("font-weight: 900; font-size: 10px; color: #334155; background: transparent; border: none;")
                    hl.addWidget(l_opt)
                    
                hl.addSpacing(2)
                l_flg = QLabel("?")
                l_flg.setFixedSize(22, 22)
                l_flg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                l_flg.setStyleSheet("font-weight: 900; font-size: 11px; color: #d97706; background: transparent; border: none;")
                hl.addWidget(l_flg)
                
                l_space = QLabel("")
                l_space.setFixedSize(18, 22)
                hl.addWidget(l_space)
                
                grid.addWidget(hdr, 0, col_i)
            
            for q_i in range(1, q_cnt + 1):
                c_idx = (q_i - 1) // per_col
                r_idx = ((q_i - 1) % per_col) + 1  # 0. satır başlık olduğu için +1
                
                row_w = OpticQuestionRow(q_i, options_count=opts_cnt)
                self.optic_rows[(s_name, q_i)] = row_w
                row_w.selection_changed.connect(lambda num, opt, flag, sn=s_name: self._on_optic_selection(sn, num, opt, flag))
                grid.addWidget(row_w, r_idx, c_idx)

            scroll.setWidget(content)
            t_lay.addWidget(scroll, 1)

            self.tab_subjects.addTab(tab_page, f"{s_name} ({q_cnt})")
            
        if subjects:
            self.active_subject = subjects[0]["name"]

    def _on_subject_tab_changed(self, idx):
        if idx >= 0:
            txt = self.tab_subjects.tabText(idx)
            self.active_subject = txt.split(" (")[0]

    def _on_optic_selection(self, subject: str, q_num: int, opt: str, is_flagged: bool):
        if opt:
            self.student_answers[subject][q_num] = opt
        else:
            self.student_answers[subject].pop(q_num, None)
            
        k = (subject, q_num)
        if is_flagged:
            self.flagged_questions.add(k)
        else:
            self.flagged_questions.discard(k)

        # Mini Navigasyon Butonunu Güncelle
        nav_btn = self.nav_buttons.get((subject, q_num))
        if nav_btn:
            if is_flagged:
                nav_btn.setStyleSheet("background-color: #f59e0b; color: white; border: 1px solid #d97706; font-weight: 800; border-radius: 4px; font-size: 10px;")
                nav_btn.setText(f"{q_num}?")
            elif opt:
                nav_btn.setStyleSheet("background-color: #1e293b; color: white; border: 1px solid #0f172a; font-weight: 800; border-radius: 4px; font-size: 10px;")
                nav_btn.setText(str(q_num))
            else:
                nav_btn.setStyleSheet("background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; font-weight: bold; border-radius: 4px; font-size: 10px;")
                nav_btn.setText(str(q_num))
            
        # Sayaçları Güncelle
        answered = sum(len(ans) for ans in self.student_answers.values())
        total = int(self.lbl_stat_total.text())
        empty = max(0, total - answered)
        
        self.lbl_stat_answered.setText(str(answered))
        self.lbl_stat_empty.setText(str(empty))
        self.lbl_stat_flagged.setText(str(len(self.flagged_questions)))
        
        # Turlama Listesi Güncelle
        if self.flagged_questions:
            sorted_flags = sorted(list(self.flagged_questions))
            items_txt = [f"• <b>{s}</b> Soru {q}" for s, q in sorted_flags]
            self.lbl_flagged_list.setText("<br>".join(items_txt))
        else:
            self.lbl_flagged_list.setText("Henüz şüpheli işaretlenen soru yok.")

    def _timer_tick(self):
        self.remaining_seconds -= 1
        now = dt.datetime.now()
        
        # Aktif derse süre ekle
        if self.active_subject in self.subject_time_spent:
            self.subject_time_spent[self.active_subject] += 1
            
        self._update_lcd()
        
        if self.remaining_seconds <= 0:
            self.timer.stop()
            self._finish_exam(auto=True)

    def _update_lcd(self):
        s = self.remaining_seconds
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        self.lcd.display(f"{h:02}:{m:02}:{sec:02}")
        
        if self.total_seconds > 0:
            pct = int((s / self.total_seconds) * 100)
            self.prog_time.setValue(pct)
            
            # Son 15 dakika uyarısı
            if s <= 15 * 60:
                self.prog_time.setStyleSheet("QProgressBar { border-radius: 5px; background: #e2e8f0; } QProgressBar::chunk { background: #dc2626; border-radius: 5px; }")
                self.lbl_exit_ban_badge.setText("🔴 SON 15 DAKİKA - Çıkış Yasaktır!")
                self.lbl_exit_ban_badge.setStyleSheet("background: #fee2e2; color: #dc2626; font-weight: bold; font-size: 11px; padding: 4px 10px; border-radius: 6px;")
            elif s >= (self.total_seconds - self.current_exam_config.get("exit_ban_minutes", 120) * 60):
                self.lbl_exit_ban_badge.setText("⚠️ İlk Süre Çıkış Yasağı")
            else:
                self.lbl_exit_ban_badge.setText("🟢 Çıkışa İzin Verilen Zaman")
                self.lbl_exit_ban_badge.setStyleSheet("background: #dcfce7; color: #15803d; font-weight: bold; font-size: 11px; padding: 4px 10px; border-radius: 6px;")

    def _confirm_finish_exam(self):
        if QMessageBox.question(self, "Sınavı Bitir", "Sınavı sonlandırmak istediğinize emin misiniz?\\nOptik formdaki işaretlemeleriniz değerlendirilecek.") == QMessageBox.StandardButton.Yes:
            self._finish_exam()

    def _finish_exam(self, auto=False):
        self.timer.stop()
        if auto:
            QMessageBox.information(self, "Süre Doldu", "Sınav süresi sona erdi! Kalemleri bırakınız.")
            
        self._calculate_and_show_results()

    # ==========================================================
    # EKRAN 3: Sınav Bitimi & Otomatik Optik Değerlendirme
    # ==========================================================
    def _init_results_ui(self):
        self.page_result = QWidget()
        lay = QVBoxLayout(self.page_result)
        lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(14)
        
        # Sonuç Başlığı
        res_header = QFrame()
        res_header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                border-radius: 12px;
                padding: 14px;
            }
        """)
        rhl = QVBoxLayout(res_header)
        lbl_rt = QLabel("🎉 Sınav Tamamlandı ve Optik Form Değerlendirildi")
        lbl_rt.setStyleSheet("color: white; font-size: 18px; font-weight: 900;")
        self.lbl_res_sub = QLabel("Netleriniz, ÖSYM/MEB puanınız ve tahmini Türkiye sıralamanız hesaplandı.")
        self.lbl_res_sub.setStyleSheet("color: #d1fae5; font-size: 11.5px;")
        rhl.addWidget(lbl_rt)
        rhl.addWidget(self.lbl_res_sub)
        lay.addWidget(res_header)
        
        # Puan & Sıra Gösterge Kartları
        p_frame = QFrame()
        p_frame.setStyleSheet("background: white; border: 1.5px solid #10b981; border-radius: 10px; padding: 12px;")
        h_pf = QHBoxLayout(p_frame)
        
        def r_box(title, val_attr, color="#1e3a8a"):
            v = QVBoxLayout(); v.setSpacing(1)
            l1 = QLabel(title); l1.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b;")
            l2 = QLabel("0.00"); l2.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {color};")
            setattr(self, val_attr, l2)
            v.addWidget(l1); v.addWidget(l2)
            return v
            
        h_pf.addLayout(r_box("TOPLAM NET", "lbl_res_net", "#2563eb"))
        h_pf.addLayout(r_box("ÖSYM/MEB PUANI", "lbl_res_score", "#059669"))
        h_pf.addLayout(r_box("TAHMİNİ TÜRKİYE SIRASI", "lbl_res_rank", "#d97706"))
        h_pf.addLayout(r_box("TÜRKİYE DİLİMİ", "lbl_res_dilim", "#7c3aed"))
        lay.addWidget(p_frame)
        
        # Ders Bazlı Sonuç ve Süre Tablosu
        self.table_res = QTableWidget()
        self.table_res.setColumnCount(6)
        self.table_res.setHorizontalHeaderLabels(["Ders", "Doğru", "Yanlış", "Boş", "Net", "Harcanan Süre"])
        self.table_res.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_res.setColumnWidth(1, 70)
        self.table_res.setColumnWidth(2, 70)
        self.table_res.setColumnWidth(3, 70)
        self.table_res.setColumnWidth(4, 90)
        self.table_res.setColumnWidth(5, 120)
        lay.addWidget(self.table_res, stretch=1)
        
        # Aksiyon Butonları
        h_btns = QHBoxLayout()
        btn_save_db = QPushButton("💾 Sonucu Deneme Takip Modülüne Kaydet")
        btn_save_db.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_db.setStyleSheet("background: #2563eb; color: white; font-weight: bold; padding: 10px 18px; border-radius: 8px;")
        btn_save_db.clicked.connect(self._save_to_database)
        h_btns.addWidget(btn_save_db)
        
        btn_close = QPushButton("Kapat ve Bitir")
        btn_close.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px 18px; font-weight: bold;")
        btn_close.clicked.connect(self.accept)
        h_btns.addWidget(btn_close)
        
        lay.addLayout(h_btns)
        self.stack.addWidget(self.page_result)

    def _calculate_and_show_results(self):
        # 1. Cevap anahtarı varsa otomatik eşle
        raw_key = self.inp_answer_key.text().strip().upper()
        # Parse key
        key_map = {}
        if raw_key:
            import re
            # Try format "1A 2B 3C" or "1:A, 2:B"
            matches = re.findall(r"(\d+)\s*[:\-\.]?\s*([A-E])", raw_key)
            if matches:
                for qn, opt in matches:
                    key_map[int(qn)] = opt
            elif len(raw_key) >= 10 and not any(c.isdigit() for c in raw_key):
                # String like "ABCDEDCBA..."
                for idx, c in enumerate(raw_key, 1):
                    key_map[idx] = c
                    
        self.table_res.setRowCount(0)
        net_dict = {}
        row_i = 0
        
        total_d = 0
        total_y = 0
        total_b = 0
        
        subjects = self.current_exam_config.get("subjects", [])
        self.final_subject_results = []
        
        for subj in subjects:
            s_name = subj["name"]
            q_cnt = subj["questions"]
            ans = self.student_answers.get(s_name, {})
            
            d = 0
            y = 0
            
            if key_map:
                for q_i in range(1, q_cnt + 1):
                    st_opt = ans.get(q_i)
                    corr = key_map.get(q_i)
                    if st_opt and corr:
                        if st_opt == corr: d += 1
                        else: y += 1
                    elif st_opt:
                        d += 1 # Default assumption
            else:
                d = len(ans)
                y = 0
                
            b = max(0, q_cnt - d - y)
            net = max(0.0, d - (y / 4.0))
            net_dict[s_name] = net
            
            total_d += d
            total_y += y
            total_b += b
            
            # Süre
            sec_spent = self.subject_time_spent.get(s_name, 0)
            m_spent = sec_spent // 60
            
            self.table_res.insertRow(row_i)
            self.table_res.setItem(row_i, 0, QTableWidgetItem(s_name))
            self.table_res.setItem(row_i, 1, QTableWidgetItem(str(d)))
            self.table_res.setItem(row_i, 2, QTableWidgetItem(str(y)))
            self.table_res.setItem(row_i, 3, QTableWidgetItem(str(b)))
            
            it_net = QTableWidgetItem(f"{net:.2f}")
            it_net.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            it_net.setForeground(QColor("#2563eb"))
            self.table_res.setItem(row_i, 4, it_net)
            
            self.table_res.setItem(row_i, 5, QTableWidgetItem(f"{m_spent} dk ({sec_spent % 60} sn)"))
            
            self.final_subject_results.append({
                "ders": s_name, "d": d, "y": y, "bos": b, "net": net
            })
            row_i += 1
            
        # Puan ve Sıralama
        type_code = self.current_exam_config.get("type_code", "TYT")
        alan = self.current_exam_config.get("alan", "SAY")
        self.final_calc = calculate_exam_score(type_code, net_dict, alan=alan)
        
        self.lbl_res_net.setText(f"{self.final_calc['toplam_net']:.2f}")
        self.lbl_res_score.setText(f"{self.final_calc['ham_puan']:.2f}")
        self.lbl_res_rank.setText(f"~{self.final_calc['tahmini_sira']:,}")
        self.lbl_res_dilim.setText(f"%{self.final_calc['yuzdelik_dilim']}")
        
        self.stack.setCurrentIndex(2)

    def _save_to_database(self):
        try:
            con = db.get_conn()
            today_str = QDate.currentDate().toString("yyyy-MM-dd")
            name = self.inp_name.text().strip()
            tur = self.current_exam_config.get("type_code", "TYT")
            
            # 1. Denemeyi ekle
            cur = con.execute("""
                INSERT INTO denemeler (tarih, deneme_adi, yayin_adi, tur, aciklama)
                VALUES (?, ?, 'Simülatör', ?, 'Gerçek Sınav Simülatörü Otomatik Sonucu')
            """, (today_str, name, tur))
            exam_id = cur.lastrowid
            
            # 2. Öğrenci ID
            stu_id = self.cmb_student.currentData()
            if not stu_id:
                # First active student fallback
                r = con.execute("SELECT id FROM ogrenci LIMIT 1").fetchone()
                stu_id = r["id"] if r else 1
                
            # 3. Sonuçları ekle
            for res in self.final_subject_results:
                con.execute("""
                    INSERT INTO deneme_sonuclari (deneme_id, ogrenci_id, ders_adi, dogru, yanlis, bos, net)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (exam_id, stu_id, res["ders"], res["d"], res["y"], res["bos"], res["net"]))
                
            con.commit()
            con.close()
            QMessageBox.information(self, "Kaydedildi", "Sınav sonuçlarınız 'Deneme Sınavları' modülüne başarıyla aktarıldı!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"DB Kayıt Hatası: {e}")
