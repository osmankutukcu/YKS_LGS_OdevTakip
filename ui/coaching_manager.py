# -*- coding: utf-8 -*-
import sys
import os
from datetime import datetime, date

# Kendi başına çalıştırıldığında kök dizini görsün
# Kendi başına çalıştırıldığında kök dizini görsün
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

def get_base_path():
    """ PyInstaller ve Normal Çalışma için Base Path """
    if getattr(sys, 'frozen', False):
        # PyInstaller ile paketlenmişse
        return sys._MEIPASS
    return parent_dir

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QProgressBar,
    QMessageBox, QDialog, QFormLayout, QDateEdit, QLineEdit, QTabWidget,
    QAbstractItemView, QMenu, QSpinBox, QListWidget, QListWidgetItem, QFrame,
    QTextEdit, QColorDialog, QButtonGroup, QCheckBox
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtCore import Qt, QDate, QMarginsF
from PyQt6.QtGui import QColor, QIcon, QFont, QAction, QCursor, QTextDocument, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter

import sqlite3
import db
from utils import whatsapp # Mevcut modülü kullanıyoruz
from utils import settings as appset
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from ui.survey_manager import SurveyManager # Yeni Anket Sistemi
from ui.schedule_settings import ScheduleSettingsDialog
from ui.coach_dialog import CoachDetailDialog
from ui.smart_report_dialog import SmartReportDialog

# Ekstra Gelişmiş Koçluk Sabitleri ve Yardımcıları
TRACK_SUBJECTS_CONFIG = {
    "say": {
        "name": "Sayısal (TYT + AYT)",
        "badge": "YKS Sayısal",
        "subjects": [
            ("Matematik (TYT)", 150, "📐"),
            ("Matematik (AYT)", 150, "📈"),
            ("Geometri", 100, "📏"),
            ("Fizik", 120, "⚡"),
            ("Kimya", 100, "🧪"),
            ("Biyoloji", 100, "🧬"),
            ("Türkçe / Paragraf", 150, "📖"),
        ]
    },
    "ea": {
        "name": "Eşit Ağırlık (TYT + AYT)",
        "badge": "YKS Eşit Ağırlık",
        "subjects": [
            ("Matematik (TYT)", 150, "📐"),
            ("Matematik (AYT)", 140, "📈"),
            ("Geometri", 90, "📏"),
            ("Türkçe / Paragraf", 150, "📖"),
            ("Edebiyat", 100, "📜"),
            ("Tarih", 80, "🏛️"),
            ("Coğrafya", 80, "🌍"),
        ]
    },
    "soz": {
        "name": "Sözel (TYT + AYT)",
        "badge": "YKS Sözel",
        "subjects": [
            ("Türkçe / Paragraf", 175, "📖"),
            ("Edebiyat", 120, "📜"),
            ("Tarih", 100, "🏛️"),
            ("Coğrafya", 100, "🌍"),
            ("Felsefe & Din", 75, "💭"),
            ("Matematik (TYT)", 80, "📐"),
        ]
    },
    "tyt": {
        "name": "TYT Odaklı (Temel Yeterlilik)",
        "badge": "YKS TYT",
        "subjects": [
            ("Türkçe", 150, "📖"),
            ("Paragraf", 120, "📑"),
            ("Matematik (TYT)", 150, "📐"),
            ("Geometri", 90, "📏"),
            ("Fizik (TYT)", 80, "⚡"),
            ("Kimya (TYT)", 80, "🧪"),
            ("Biyoloji (TYT)", 80, "🧬"),
            ("Sosyal Bilimler", 80, "🌍"),
        ]
    },
    "lgs": {
        "name": "LGS (8. Sınıf)",
        "badge": "8. Sınıf LGS",
        "subjects": [
            ("Matematik", 140, "📐"),
            ("Fen Bilimleri", 140, "🔬"),
            ("Türkçe", 140, "📖"),
            ("T.C. İnkılap Tarihi", 90, "🏛️"),
            ("Din Kültürü", 60, "🕌"),
            ("İngilizce", 80, "🇬🇧"),
        ]
    },
    "dil": {
        "name": "YDT / Dil (TYT + YDT)",
        "badge": "YKS YDT",
        "subjects": [
            ("İngilizce / YDT", 220, "🇬🇧"),
            ("Türkçe / Paragraf", 150, "📖"),
            ("Matematik (TYT)", 90, "📐"),
            ("Sosyal Bilgiler", 70, "🌍"),
        ]
    }
}



# Haftalık Ders Listesi (Varsayılan)
DEFAULT_SUBJECTS = [
    "Matematik (TYT)", "Matematik (AYT)", "Geometri", "Fizik", "Kimya", "Biyoloji", 
    "Türkçe", "Edebiyat", "Tarih", "Coğrafya", "Felsefe", "Din", "Dil Bilgisi"
]

DEFAULT_LGS_SUBJECTS = [
    "Türkçe", "Matematik", "Fen Bilimleri", "T.C. İnkılap Tarihi", "Din Kültürü", "İngilizce"
]

import json
import glob

# Dinamik Konu Listesi (Seed klasöründen)
TOPIC_LIST = {}
CURRICULUM_DATA = {}

def load_curriculum_data():
    global CURRICULUM_DATA
    try:
        base = get_base_path()
        path = os.path.join(base, "assets", "curriculum.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                CURRICULUM_DATA = json.load(f)
        else:
            print("Curriculum dosyasını bulamadım:", path)
    except Exception as e:
        print(f"Error loading curriculum.json: {e}")

load_curriculum_data()


from PyQt6.QtWidgets import QInputDialog

def load_topics_from_system():
    global TOPIC_LIST
    TOPIC_LIST = {} # Reset
    
    # 1. Önce Veritabanından Çekmeyi Dene (En Güncel Veri)
    try:
        con = db.get_conn()
        for table_name in db.DERS_TABLOLARI:
            # Görünen Adı Oluştur (tyt_matematik -> Matematik (TYT))
            display_name = table_name.replace("_", " ").title()
            if "Tyt" in display_name: display_name = display_name.replace("Tyt", "(TYT)")
            if "Ayt" in display_name: display_name = display_name.replace("Ayt", "(AYT)")
            if "Lgs" in display_name: display_name = display_name.replace("Lgs", "(LGS)")
            
            # Veriyi Çek
            try:
                rows = con.execute(f"SELECT konu FROM {table_name} ORDER BY id").fetchall()
                topics = [r[0] for r in rows]
                if topics:
                    TOPIC_LIST[display_name] = topics
            except Exception as e:
                # Tablo olmayabilir veya hata olabilir
                pass
        con.close()
    except Exception as e:
        print(f"DB Topic Load Error: {e}")

    # 2. Eğer DB boş geldiyse veya eksikse, Seed dosyalarından tamamla (Fallback)
    #    (Özellikle ilk kurulumda DB henüz oluşmamışsa burası devreye girer)
    if not TOPIC_LIST:
        base = get_base_path()
        seed_path = os.path.join(base, "seed")
        
        if os.path.exists(seed_path):
            files = glob.glob(os.path.join(seed_path, "*.json"))
            for f in files:
                basename = os.path.basename(f).replace(".json", "")
                display_name = basename.replace("_", " ").title()
                if "Tyt" in display_name: display_name = display_name.replace("Tyt", "(TYT)")
                if "Ayt" in display_name: display_name = display_name.replace("Ayt", "(AYT)")
                if "Lgs" in display_name: display_name = display_name.replace("Lgs", "(LGS)")
                
                # Eğer DB'den zaten geldiyse dosyadan okuma
                if display_name in TOPIC_LIST:
                    continue

                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                        if isinstance(data, list):
                            if data and isinstance(data[0], str): topics = data
                            elif data and isinstance(data[0], dict): topics = [item.get("name", "") for item in data]
                            else: topics = []
                            
                            if topics:
                                TOPIC_LIST[display_name] = topics
                except: pass

    # 3. Son Güvenlik Ağı: Default Listeler (Boş kalmasın)
    for subj in DEFAULT_SUBJECTS:
        if subj not in TOPIC_LIST:
            TOPIC_LIST[subj] = []

# İlk yükleme
load_topics_from_system()


class WeeklyPlanCreateDialog(QDialog):
    """
    Öğrencinin alanına (Sayısal, EA, Sözel, LGS) özel ders filtreli ve 
    her ders için ayrı soru hedefi belirlenebilen profesyonel planlama sihirbazı.
    """
    def __init__(self, student_name: str, group_str: str, start_date, parent=None):
        super().__init__(parent)
        self.student_name = student_name
        self.group_str = (group_str or "").lower()
        self.start_date = start_date
        self.end_date = start_date.addDays(6)
        
        self.setWindowTitle(f"Haftalık Hedef ve Soru Planı — {self.student_name}")
        self.resize(650, 680)
        self.setMinimumSize(580, 560)
        
        self._apply_styles()
        self._init_ui()
        self._detect_and_select_track()

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QFrame.HeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #2563eb);
                border-radius: 12px;
                color: white;
            }
            QFrame.ContentCard {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QPushButton.TrackBtn {
                background-color: #ffffff;
                color: #334155;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton.TrackBtn:hover {
                background-color: #eff6ff;
                border-color: #3b82f6;
                color: #1d4ed8;
            }
            QPushButton.TrackBtn:checked {
                background-color: #2563eb;
                border-color: #1d4ed8;
                color: #ffffff;
            }
            QPushButton.PresetBtn {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton.PresetBtn:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
            QTableWidget {
                border: none;
                background-color: white;
                gridline-color: #f1f5f9;
            }
            QTableWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 700;
                color: #475569;
                font-size: 11px;
            }
        """)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # 1. Başlık Kartı
        header = QFrame()
        header.setProperty("class", "HeaderCard")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(18, 14, 18, 14)
        h_lay.setSpacing(14)

        icon_lbl = QLabel("🎯")
        icon_lbl.setStyleSheet("font-size: 32px; background: transparent; color: white;")
        h_lay.addWidget(icon_lbl)

        v_tit = QVBoxLayout()
        v_tit.setSpacing(2)
        lbl_t = QLabel(f"Yeni Haftalık Soru Planı: {self.student_name}")
        lbl_t.setStyleSheet("color: white; font-size: 16px; font-weight: 800; background: transparent;")
        lbl_s = QLabel(f"📅 Hedef Hafta: {self.start_date.toString('dd.MM.yyyy')} — {self.end_date.toString('dd.MM.yyyy')}")
        lbl_s.setStyleSheet("color: #bfdbfe; font-size: 12px; font-weight: 500; background: transparent;")
        v_tit.addWidget(lbl_t)
        v_tit.addWidget(lbl_s)
        h_lay.addLayout(v_tit, 1)

        self.lbl_badge = QLabel("Sayısal")
        self.lbl_badge.setStyleSheet("background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.4); border-radius: 14px; padding: 4px 12px; font-weight: 700; font-size: 11px;")
        h_lay.addWidget(self.lbl_badge)
        root.addWidget(header)

        # 2. Alan / Track Hızlı Filtre Butonları
        filter_box = QFrame()
        filter_box.setProperty("class", "ContentCard")
        fb_lay = QVBoxLayout(filter_box)
        fb_lay.setContentsMargins(12, 10, 12, 10)
        fb_lay.setSpacing(8)

        lbl_fb = QLabel("🎯 Alan / Müfredat Seçimi (Dersleri Otomatik Ayarlar):")
        lbl_fb.setStyleSheet("font-weight: 700; font-size: 11px; color: #475569;")
        fb_lay.addWidget(lbl_fb)

        h_tracks = QHBoxLayout()
        h_tracks.setSpacing(8)
        self.btn_group_track = QButtonGroup(self)

        tracks_info = [
            ("say", "📐 Sayısal"),
            ("ea", "⚖️ Eşit Ağırlık"),
            ("soz", "📖 Sözel"),
            ("tyt", "🎯 TYT Odaklı"),
            ("lgs", "🎒 LGS (8. Sınıf)"),
            ("dil", "🇬🇧 YDT / Dil")
        ]

        self.track_btns = {}
        for t_key, t_label in tracks_info:
            b = QPushButton(t_label)
            b.setProperty("class", "TrackBtn")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, k=t_key: self._set_track(k))
            self.btn_group_track.addButton(b)
            self.track_btns[t_key] = b
            h_tracks.addWidget(b)

        fb_lay.addLayout(h_tracks)

        # Hızlı seçim aksiyonları
        h_act = QHBoxLayout()
        btn_sel_all = QPushButton("✓ Tümünü Seç")
        btn_sel_all.setStyleSheet("font-size: 10px; padding: 3px 8px;")
        btn_sel_all.clicked.connect(self._select_all)
        
        btn_clear_all = QPushButton("✕ Temizle")
        btn_clear_all.setStyleSheet("font-size: 10px; padding: 3px 8px;")
        btn_clear_all.clicked.connect(self._clear_all)

        h_act.addWidget(btn_sel_all)
        h_act.addWidget(btn_clear_all)
        h_act.addStretch(1)
        fb_lay.addLayout(h_act)

        root.addWidget(filter_box)

        # 3. Ders Listesi & Hedef Soru Tablosu
        list_card = QFrame()
        list_card.setProperty("class", "ContentCard")
        lc_lay = QVBoxLayout(list_card)
        lc_lay.setContentsMargins(10, 8, 10, 8)
        lc_lay.setSpacing(6)

        self.tbl_subjects = QTableWidget(0, 4)
        self.tbl_subjects.setHorizontalHeaderLabels(["Seç", "Ders Adı", "Hedef Soru", "Hızlı Ayar"])
        hh = self.tbl_subjects.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed); self.tbl_subjects.setColumnWidth(0, 45)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); self.tbl_subjects.setColumnWidth(2, 110)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed); self.tbl_subjects.setColumnWidth(3, 160)
        self.tbl_subjects.verticalHeader().setDefaultSectionSize(40)
        self.tbl_subjects.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lc_lay.addWidget(self.tbl_subjects)

        root.addWidget(list_card, 1)

        # 4. Alt Özet ve Canlı Metrik Kartı
        sum_card = QFrame()
        sum_card.setStyleSheet("background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 8px 14px;")
        h_sum = QHBoxLayout(sum_card)
        h_sum.setContentsMargins(8, 4, 8, 4)

        self.lbl_sum_total = QLabel("🎯 Toplam Hedef: 0 Soru")
        self.lbl_sum_total.setStyleSheet("color: #1e40af; font-size: 14px; font-weight: 800;")
        self.lbl_sum_daily = QLabel("⏱️ Günlük Ortalama: 0 Soru / Gün")
        self.lbl_sum_daily.setStyleSheet("color: #3b82f6; font-size: 12px; font-weight: 600;")

        h_sum.addWidget(self.lbl_sum_total)
        h_sum.addSpacing(20)
        h_sum.addWidget(self.lbl_sum_daily)
        h_sum.addStretch(1)
        root.addWidget(sum_card)

        # 5. Butonlar
        h_btn = QHBoxLayout()
        h_btn.setSpacing(10)
        btn_cancel = QPushButton("✕ İptal")
        btn_cancel.setStyleSheet("padding: 8px 18px; border-radius: 8px; border: 1px solid #cbd5e1; background: #ffffff; color: #475569; font-weight: 600;")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("✨ Planı Oluştur & Başlat")
        btn_ok.setStyleSheet("padding: 9px 24px; border-radius: 8px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8); color: white; font-weight: 800; font-size: 13px; border: 1px solid #1d4ed8;")
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self.accept)

        h_btn.addStretch(1)
        h_btn.addWidget(btn_cancel)
        h_btn.addWidget(btn_ok)
        root.addLayout(h_btn)

    def _detect_and_select_track(self):
        g = self.group_str
        if "lgs" in g or "8." in g or "8.sınıf" in g or "ortaokul" in g:
            track = "lgs"
        elif "dil" in g or "ydt" in g:
            track = "dil"
        elif "ea" in g or "esit" in g:
            track = "ea"
        elif "soz" in g or "sozel" in g:
            track = "soz"
        elif "tyt" in g:
            track = "tyt"
        else:
            track = "say"

        if track in self.track_btns:
            self.track_btns[track].setChecked(True)
        self._set_track(track)

    def _set_track(self, track_key: str):
        cfg = TRACK_SUBJECTS_CONFIG.get(track_key, TRACK_SUBJECTS_CONFIG["say"])
        self.lbl_badge.setText(cfg["badge"])

        self.tbl_subjects.setRowCount(0)
        subjects = cfg["subjects"]

        self.row_widgets = []

        for row_idx, (s_name, def_target, s_icon) in enumerate(subjects):
            self.tbl_subjects.insertRow(row_idx)

            # Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            chk.toggled.connect(self._recalc_totals)
            w_chk = QWidget(); l_chk = QHBoxLayout(w_chk); l_chk.setAlignment(Qt.AlignmentFlag.AlignCenter); l_chk.setContentsMargins(0,0,0,0); l_chk.addWidget(chk)
            self.tbl_subjects.setCellWidget(row_idx, 0, w_chk)

            # Ders Adı
            it_name = QTableWidgetItem(f"{s_icon}  {s_name}")
            it_name.setData(Qt.ItemDataRole.UserRole, s_name)
            it_name.setFlags(it_name.flags() ^ Qt.ItemFlag.ItemIsEditable)
            it_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.tbl_subjects.setItem(row_idx, 1, it_name)

            # SpinBox (Hedef Soru)
            sp = QSpinBox()
            sp.setRange(10, 2000)
            sp.setSingleStep(25)
            sp.setValue(def_target)
            sp.valueChanged.connect(self._recalc_totals)
            self.tbl_subjects.setCellWidget(row_idx, 2, sp)

            # Hızlı Butonlar
            w_p = QWidget(); l_p = QHBoxLayout(w_p); l_p.setContentsMargins(4, 2, 4, 2); l_p.setSpacing(4)
            for add_val in [50, 100, 150, 200]:
                btn = QPushButton(str(add_val))
                btn.setProperty("class", "PresetBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, spin=sp, v=add_val: spin.setValue(v))
                l_p.addWidget(btn)
            self.tbl_subjects.setCellWidget(row_idx, 3, w_p)

            self.row_widgets.append((chk, it_name, sp))

        self._recalc_totals()

    def _select_all(self):
        for chk, _, _ in self.row_widgets:
            chk.setChecked(True)
        self._recalc_totals()

    def _clear_all(self):
        for chk, _, _ in self.row_widgets:
            chk.setChecked(False)
        self._recalc_totals()

    def _recalc_totals(self):
        total = 0
        active_count = 0
        for chk, _, sp in self.row_widgets:
            if chk.isChecked():
                total += sp.value()
                active_count += 1

        daily_avg = int(round(total / 6.0)) if total > 0 else 0
        self.lbl_sum_total.setText(f"🎯 Toplam Hedef: {total:,} Soru ({active_count} Ders)".replace(",", "."))
        self.lbl_sum_daily.setText(f"⏱️ Günlük Ortalama: ~{daily_avg} Soru / Gün (6 gün çalışma)")

    def get_selected_goals(self):
        result = []
        for chk, it_name, sp in self.row_widgets:
            if chk.isChecked():
                clean_name = it_name.data(Qt.ItemDataRole.UserRole)
                result.append((clean_name, sp.value()))
        return result


class CoachingManager(QWidget):
    """
    Profesyonel Öğrenci Koçluğu ve Soru Hedef Takip Sistemi.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_student_id = None
        self.current_student_name = ""
        self.current_student_group = ""
        self.current_plan_id = None
        
        self._ensure_schema() # Veritabanı migrasyonu (Renk kolonu için)
        
        self._setup_ui()
        self._load_students()
        self._update_exam_countdown()
    
    def _ensure_schema(self):
        """Koçluk tablolarını ve eksik kolonları kontrol et ve oluştur (Lazy Migration)"""
        try:
            con = db.get_conn()
            cur = con.cursor()
            if hasattr(db, '_init_coaching_tables'):
                db._init_coaching_tables(cur)
            else:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS koc_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ogrenci_id INTEGER,
                    baslangic_tarihi TEXT,
                    bitis_tarihi TEXT,
                    notlar TEXT,
                    aktif INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
                )""")
                cur.execute("""
                CREATE TABLE IF NOT EXISTS koc_hedef (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER,
                    ders_adi TEXT,
                    hedef_soru INTEGER DEFAULT 0,
                    cozulen_soru INTEGER DEFAULT 0,
                    hedef_saat REAL DEFAULT 0,
                    calisilan_saat REAL DEFAULT 0,
                    durum TEXT DEFAULT 'devam', 
                    FOREIGN KEY(plan_id) REFERENCES koc_plan(id) ON DELETE CASCADE
                )""")
                cur.execute("""
                CREATE TABLE IF NOT EXISTS koc_program (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER,
                    gun TEXT,
                    saat TEXT,
                    icerik TEXT,
                    renk TEXT,
                    FOREIGN KEY(plan_id) REFERENCES koc_plan(id) ON DELETE CASCADE
                )""")
                cur.execute("""
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
                )""")
                cur.execute("""
                CREATE TABLE IF NOT EXISTS koc_kitaplar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ogrenci_id INTEGER,
                    ders_adi TEXT,
                    kitap_adi TEXT,
                    FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
                )""")
            con.commit()
            con.close()
        except Exception as e:
            print(f"Coaching schema check error: {e}")

    def _calculate_target_exam(self, student_id=None):
        today = QDate.currentDate()
        year = today.year()
        # Eğer bugünün tarihi 20 Haziran'ı geçmişse, aktif hedef bir sonraki yılın Haziran sınavıdır
        if today > QDate(year, 6, 20):
            target_year = year + 1
        else:
            target_year = year

        # LGS Tarihi: Hedef yılın Haziran ayının ilk Pazarı
        d_lgs = QDate(target_year, 6, 1)
        while d_lgs.dayOfWeek() != 7: # 7 = Pazar
            d_lgs = d_lgs.addDays(1)

        # YKS Tarihi: Hedef yılın Haziran ayının 3. Cumartesisi
        d_yks = QDate(target_year, 6, 1)
        sats = 0
        while True:
            if d_yks.dayOfWeek() == 6: # 6 = Cumartesi
                sats += 1
                if sats == 3:
                    break
            d_yks = d_yks.addDays(1)

        # Seçili öğrencinin grubu kontrol edilsin
        ana_grup = ""
        alt_grup = ""
        if student_id:
            con = db.get_conn()
            try:
                r = con.execute("SELECT ana_grup, alt_grup FROM ogrenci WHERE id=?", (student_id,)).fetchone()
                if r:
                    ana_grup = str(r["ana_grup"] or "")
                    alt_grup = str(r["alt_grup"] or "")
            except Exception:
                pass
            finally:
                con.close()

        combined_grp = f"{ana_grup} {alt_grup}".upper()

        if "LGS" in combined_grp or "8" in combined_grp:
            exam_name = f"LGS {target_year}"
            target_date = d_lgs
            icon = "🎒"
        elif "YKS" in combined_grp or any(k in combined_grp for k in ["12", "MEZUN", "TYT", "AYT", "SAY", "EA", "SÖZ"]):
            exam_name = f"YKS {target_year}"
            target_date = d_yks
            icon = "🎓"
        else:
            # Kullanıcının manuel kaydettiği geçerli bir gelecek tarih var mı?
            saved_date_str = appset.ayar_get("target_exam_date")
            if saved_date_str:
                saved_date = QDate.fromString(saved_date_str, "yyyy-MM-dd")
                if saved_date.isValid() and today.daysTo(saved_date) >= 0:
                    exam_name = f"Hedef Sınav ({saved_date.toString('dd.MM.yyyy')})"
                    target_date = saved_date
                    icon = "🎯"
                else:
                    exam_name = f"YKS {target_year}"
                    target_date = d_yks
                    icon = "🎯"
            else:
                exam_name = f"YKS {target_year}"
                target_date = d_yks
                icon = "🎯"

        days_left = today.daysTo(target_date)
        if days_left < 0:
            target_date = target_date.addYears(1)
            days_left = today.daysTo(target_date)

        return exam_name, target_date, days_left, icon

    def _update_exam_countdown(self):
        if not hasattr(self, 'lbl_count'):
            return
        exam_name, target_date, days_left, icon = self._calculate_target_exam(self.current_student_id)
        if hasattr(self, 'lbl_icon'):
            self.lbl_icon.setText(icon)

        if days_left == 0:
            self.lbl_count.setText(f"{exam_name}: Bugün Sınav Günü! 🍀")
        elif days_left == 1:
            self.lbl_count.setText(f"{exam_name}: Yarın Sınav! (1 Gün)")
        else:
            self.lbl_count.setText(f"{exam_name}: {days_left} Gün Kaldı")

        if hasattr(self, 'cnt_cont'):
            self.cnt_cont.setToolTip(
                f"Hedef Tarih: {target_date.toString('dd MMMM yyyy dddd')} ({days_left} gün kaldı)\n"
                f"Değiştirmek için '⚙️ Tarih Belirle' butonuna tıklayınız."
            )

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # --- ANA SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #cbd5e1;
                border-radius: 1px;
            }
        """)

        # 1. SOL PANEL: Öğrenci Listesi
        left_widget = QWidget()
        l_lay = QVBoxLayout(left_widget)
        l_lay.setContentsMargins(0, 0, 6, 0)
        l_lay.setSpacing(10)

        header_l = QHBoxLayout()
        lbl_list_title = QLabel("👥 Öğrenci Listesi")
        lbl_list_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        self.lbl_student_count = QLabel("(0 Aktif)")
        self.lbl_student_count.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b; background: #f1f5f9; padding: 2px 6px; border-radius: 8px;")
        header_l.addWidget(lbl_list_title)
        header_l.addSpacing(6)
        header_l.addWidget(self.lbl_student_count)
        header_l.addStretch()
        l_lay.addLayout(header_l)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Öğrenci veya grup ara...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 7px 10px;
                font-size: 12px;
                color: #1e293b;
            }
            QLineEdit:focus {
                border: 1.5px solid #3b82f6;
                background: #f8fafc;
            }
        """)
        self.search_box.textChanged.connect(self._filter_students)
        l_lay.addWidget(self.search_box)

        self.list_students = QListWidget()
        self.list_students.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                outline: none;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 6px;
                border-bottom: 1px solid #f1f5f9;
                color: #1e293b;
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
                font-weight: 700;
                border-left: 3px solid #2563eb;
            }
        """)
        self.list_students.itemClicked.connect(self._on_student_selected)
        l_lay.addWidget(self.list_students)

        splitter.addWidget(left_widget)

        # 2. SAĞ PANEL: TAB YAPISI
        self.right_widget = QWidget()
        self.right_widget.setEnabled(False)
        r_lay = QVBoxLayout(self.right_widget)
        r_lay.setContentsMargins(6, 0, 0, 0)
        r_lay.setSpacing(10)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                background: #ffffff;
                padding: 4px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: 600;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1e40af;
                font-weight: 700;
                border: 1px solid #e2e8f0;
                border-bottom: 2px solid #2563eb;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
                color: #1e293b;
            }
        """)
        r_lay.addWidget(self.tabs)

        # TAB 1: Takip (Mevcut Görünüm)
        self.tab_plan = QWidget()
        self._init_tab_plan(self.tab_plan)
        self.tabs.addTab(self.tab_plan, "📝 Takip ve Hedefler")

        # TAB 2: Analiz (Grafik)
        self.tab_analysis = QWidget()
        self._init_tab_analysis(self.tab_analysis)
        self.tabs.addTab(self.tab_analysis, "📈 Gelişim Analizi")

        # TAB 3: Program
        self.tab_schedule = QWidget()
        self._init_tab_schedule(self.tab_schedule)
        self.tabs.addTab(self.tab_schedule, "🗓️ Ders Programı")

        # TAB 4: Notlar
        self.tab_notes = QWidget()
        self._init_tab_notes(self.tab_notes)
        self.tabs.addTab(self.tab_notes, "📌 Görüşme Notları")

        # TAB 5: Konu Takibi (YENİ)
        self.tab_topics = QWidget()
        self._init_tab_topics(self.tab_topics)
        self.tabs.addTab(self.tab_topics, "📋 Konu Takibi")

        # TAB 6: Anketler (YENİ)
        self.tab_survey = SurveyManager()
        self.tabs.addTab(self.tab_survey, "🧠 Profesyonel Anketler")

        splitter.addWidget(self.right_widget)

        splitter.setStretchFactor(0, 24)
        splitter.setStretchFactor(1, 76)

        main_layout.addWidget(splitter)

    # --- TAB KURULUMLARI ---
    def _init_tab_plan(self, parent):
        lay = QVBoxLayout(parent)
        lay.setSpacing(12)
        lay.setContentsMargins(12, 12, 12, 12)

        # --- ÜST BAŞLIK ve TARİH ---
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        title = QLabel("🎓 Profesyonel Öğrenci Koçluğu")
        title.setStyleSheet("font-size: 20px; font-weight: 800; color: #1e3a8a; letter-spacing: -0.5px;") 
        subtitle = QLabel("Haftalık soru hedefleri, görüşme planı ve yapay zeka destekli performans analizi")
        subtitle.setStyleSheet("font-size: 11px; color: #64748b;")
        v_title.addWidget(title)
        v_title.addWidget(subtitle)
        header_layout.addLayout(v_title)

        header_layout.addStretch()

        # Sayaç (Countdown Pill)
        self.cnt_cont = QFrame()
        self.cnt_cont.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #eff6ff, stop:1 #e0e7ff);
                border: 1px solid #bfdbfe;
                border-radius: 18px;
            }
        """)
        cl = QHBoxLayout(self.cnt_cont)
        cl.setContentsMargins(12, 6, 12, 6)
        cl.setSpacing(6)

        self.lbl_icon = QLabel("🎯")
        self.lbl_icon.setStyleSheet("font-size: 16px; border:none; background:transparent;")
        self.lbl_count = QLabel("YKS 2027: 282 Gün Kaldı")
        self.lbl_count.setStyleSheet("color: #1e40af; font-weight: 700; font-size: 12px; border:none; background:transparent;")
        cl.addWidget(self.lbl_icon)
        cl.addWidget(self.lbl_count)
        header_layout.addWidget(self.cnt_cont)

        btn_set_date = QPushButton("⚙️ Tarih Belirle")
        btn_set_date.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_set_date.setToolTip("Hedef sınav tarihini özelleştirin veya hazır YKS/LGS takvimini seçin")
        btn_set_date.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                color: #334155;
            }
            QPushButton:hover {
                background: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
        """)
        btn_set_date.clicked.connect(self._set_exam_date)
        header_layout.addWidget(btn_set_date)

        lay.addWidget(header_widget)

        # --- ÖĞRENCİ ve HAFTA SEÇİMİ / GÖRÜŞME KARTI ---
        week_bar = QFrame()
        week_bar.setStyleSheet("""
            .QFrame {
                background: #f8fafc;
                border-radius: 10px;
                border: 1px solid #e2e8f0;
            }
        """)
        wb_lay = QVBoxLayout(week_bar)
        wb_lay.setContentsMargins(14, 10, 14, 10)
        wb_lay.setSpacing(8)

        # Üst Satır: Öğrenci Profili ve Görüşme Zamanı
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # Öğrenci Profil Bilgisi
        self.lbl_student_chip = QLabel("👤 Henüz Öğrenci Seçilmedi")
        self.lbl_student_chip.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b; border:none; background:transparent;")
        row1.addWidget(self.lbl_student_chip)

        self.lbl_student_badge = QLabel("Genel")
        self.lbl_student_badge.setStyleSheet("""
            QLabel {
                background: #dbeafe;
                color: #1e40af;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 10px;
                border: none;
            }
        """)
        self.lbl_student_badge.setVisible(False)
        row1.addWidget(self.lbl_student_badge)

        # For backwards compatibility with other methods
        self.lbl_student_name = QLabel("Seçili Öğrenci: Yok")
        self.lbl_student_name.setVisible(False)
        row1.addWidget(self.lbl_student_name)

        row1.addStretch()

        # Görüşme Zamanı Ayarı Grubu
        lbl_koc_time_title = QLabel("📅 Haftalık Görüşme:")
        lbl_koc_time_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569; border:none; background:transparent;")
        row1.addWidget(lbl_koc_time_title)

        self.cb_koc_gun = QComboBox()
        self.cb_koc_gun.addItems(["", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"])
        self.cb_koc_gun.setFixedWidth(115)
        self.cb_koc_gun.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                color: #1e293b;
            }
        """)
        row1.addWidget(self.cb_koc_gun)

        from PyQt6.QtWidgets import QTimeEdit
        self.te_koc_saat = QTimeEdit()
        self.te_koc_saat.setDisplayFormat("HH:mm")
        self.te_koc_saat.setFixedWidth(80)
        self.te_koc_saat.setStyleSheet("""
            QTimeEdit {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 12px;
                color: #1e293b;
            }
        """)
        row1.addWidget(self.te_koc_saat)

        self.btn_save_koc_time = QPushButton("💾 Kaydet")
        self.btn_save_koc_time.setToolTip("Öğrencinin haftalık koçluk görüşme gün ve saatini kaydet")
        self.btn_save_koc_time.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_koc_time.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: 600;
                font-size: 11px;
                border-radius: 6px;
                padding: 5px 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_save_koc_time.clicked.connect(self._save_student_koc_info)
        row1.addWidget(self.btn_save_koc_time)

        wb_lay.addLayout(row1)

        # Alt Satır: Hafta Seçimi ve Plan Oluşturma
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        lbl_week_nav = QLabel("🗓️ Takip Haftası:")
        lbl_week_nav.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569; border:none; background:transparent;")
        row2.addWidget(lbl_week_nav)

        btn_prev_week = QPushButton("◀ Önceki")
        btn_prev_week.setToolTip("Bir önceki haftaya git")
        btn_prev_week.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_prev_week.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
                color: #334155;
            }
            QPushButton:hover { background: #f1f5f9; }
        """)
        btn_prev_week.clicked.connect(lambda: self.dt_week.setDate(self.dt_week.date().addDays(-7)))
        row2.addWidget(btn_prev_week)

        self.dt_week = QDateEdit(QDate.currentDate())
        self.dt_week.setDisplayFormat("dd.MM.yyyy")
        self.dt_week.setCalendarPopup(True)
        self.dt_week.setFixedWidth(110)
        self.dt_week.setStyleSheet("""
            QDateEdit {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 12px;
                font-weight: 600;
                color: #1e293b;
            }
        """)
        self.dt_week.dateChanged.connect(self._load_plan)
        row2.addWidget(self.dt_week)

        btn_next_week = QPushButton("Sonraki ▶")
        btn_next_week.setToolTip("Bir sonraki haftaya git")
        btn_next_week.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next_week.setStyleSheet("""
            QPushButton {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
                color: #334155;
            }
            QPushButton:hover { background: #f1f5f9; }
        """)
        btn_next_week.clicked.connect(lambda: self.dt_week.setDate(self.dt_week.date().addDays(7)))
        row2.addWidget(btn_next_week)

        row2.addStretch()

        self.btn_create_plan = QPushButton("✨ Bu Hafta İçin Yeni Plan Oluştur")
        self.btn_create_plan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_plan.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: 700;
                font-size: 12px;
                border-radius: 6px;
                padding: 6px 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_create_plan.clicked.connect(self._create_plan)
        row2.addWidget(self.btn_create_plan)

        wb_lay.addLayout(row2)
        lay.addWidget(week_bar)

        # --- MODERN DASHBOARD METRİK KARTLARI ---
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(12)

        def create_card(icon, title, subtitle, obj_name, accent_color, bg_tint):
            frm = QFrame()
            frm.setStyleSheet(f"""
                .QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 {bg_tint});
                    border: 1px solid #e2e8f0;
                    border-top: 4px solid {accent_color};
                    border-radius: 10px;
                }}
            """)
            l = QHBoxLayout(frm)
            l.setContentsMargins(16, 12, 16, 12)
            l.setSpacing(12)

            lbl_ico = QLabel(icon)
            lbl_ico.setFixedSize(40, 40)
            lbl_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_ico.setStyleSheet(f"""
                font-size: 20px;
                background-color: {accent_color}18;
                border-radius: 20px;
                border: 1px solid {accent_color}33;
            """)

            v = QVBoxLayout()
            v.setSpacing(2)
            lbl_tit = QLabel(title)
            lbl_tit.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border:none; background:transparent;")
            lbl_val = QLabel("-")
            lbl_val.setObjectName(obj_name)
            lbl_val.setStyleSheet("color: #0f172a; font-size: 24px; font-weight: 800; border:none; background:transparent;")
            lbl_sub = QLabel(subtitle)
            lbl_sub.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 500; border:none; background:transparent;")

            v.addWidget(lbl_tit)
            v.addWidget(lbl_val)
            v.addWidget(lbl_sub)

            l.addWidget(lbl_ico)
            l.addLayout(v)
            l.addStretch()
            return frm, lbl_val, lbl_sub

        card1, self.lbl_total_target, self.lbl_target_sub = create_card("🎯", "Haftalık Soru Hedefi", "Belirlenen toplam hedef", "lblT", "#3b82f6", "#eff6ff")
        card2, self.lbl_total_solved, self.lbl_solved_sub = create_card("✅", "Çözülen Soru", "Öğrencinin çözdüğü soru", "lblS", "#10b981", "#ecfdf5")
        card3, self.lbl_completion_rate, self.lbl_completion_sub = create_card("🏆", "Başarı Oranı", "Genel tamamlama seviyesi", "lblR", "#f59e0b", "#fffbeb")

        summary_layout.addWidget(card1)
        summary_layout.addWidget(card2)
        summary_layout.addWidget(card3)
        lay.addLayout(summary_layout)

        # --- YAPAY ZEKA KOÇ YORUMU ---
        self.frm_ai = QFrame()
        self.frm_ai.setStyleSheet("""
            .QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f0fdf4, stop:1 #ecfdf5);
                border: 1px solid #a7f3d0;
                border-radius: 10px;
            }
        """)
        ai_lay = QHBoxLayout(self.frm_ai)
        ai_lay.setContentsMargins(14, 10, 14, 10)
        ai_lay.setSpacing(10)

        lbl_ai_icon = QLabel("✨")
        lbl_ai_icon.setStyleSheet("font-size: 18px; border:none; background:transparent;")
        ai_lay.addWidget(lbl_ai_icon)

        lbl_ai_tit = QLabel("<b>YAPAY ZEKA KOÇ DEĞERLENDİRMESİ:</b>")
        lbl_ai_tit.setStyleSheet("font-size: 11px; color: #065f46; letter-spacing: 0.5px; border:none; background:transparent;")
        ai_lay.addWidget(lbl_ai_tit)

        self.lbl_ai_comment = QLabel("Veri bekleniyor...")
        self.lbl_ai_comment.setStyleSheet("color: #047857; font-size: 12px; font-weight: 600; border:none; background:transparent;")
        ai_lay.addWidget(self.lbl_ai_comment)
        ai_lay.addStretch()
        lay.addWidget(self.frm_ai)

        # -- Hedef Tablosu Bildirimi (Plan Yoksa) --
        self.lbl_no_plan_notice = QLabel("📋 Bu hafta için henüz bir hedef planı oluşturulmadı. Yukarıdaki '<b>✨ Bu Hafta İçin Yeni Plan Oluştur</b>' butonuna tıklayarak haftalık ders hedeflerini belirleyebilirsiniz.")
        self.lbl_no_plan_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_no_plan_notice.setStyleSheet("""
            QLabel {
                background: #f8fafc;
                border: 1.5px dashed #cbd5e1;
                border-radius: 8px;
                padding: 24px;
                font-size: 13px;
                color: #64748b;
            }
        """)
        self.lbl_no_plan_notice.setVisible(False)
        lay.addWidget(self.lbl_no_plan_notice)

        # -- Hedef Tablosu --
        self.table_goals = QTableWidget()
        cols = ["Ders", "Hedef (Soru)", "Çözülen", "Hedef (Saat)", "Çalışılan", "İlerleme Oranı"]
        self.table_goals.setColumnCount(len(cols))
        self.table_goals.setHorizontalHeaderLabels(cols)
        self.table_goals.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_goals.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table_goals.verticalHeader().setDefaultSectionSize(42)
        self.table_goals.setAlternatingRowColors(True)
        self.table_goals.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff;
                selection-color: #1e3a8a;
            }
            QTableWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #334155;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #cbd5e1;
                padding: 8px 10px;
            }
        """)
        lay.addWidget(self.table_goals)

        # -- Alt Butonlar --
        bot_bar = QHBoxLayout()
        bot_bar.setSpacing(10)

        lbl_tip = QLabel("💡 <b>İpucu:</b> Çözülen soru sayılarını girdikten sonra 'İlerlemeyi Kaydet'e basınız.")
        lbl_tip.setStyleSheet("font-size: 11px; color: #64748b;")
        bot_bar.addWidget(lbl_tip)
        bot_bar.addStretch()

        self.btn_smart_report = QPushButton("📊 Akıllı Koçluk Raporu")
        self.btn_smart_report.setMinimumHeight(40)
        self.btn_smart_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_smart_report.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                font-weight: 700;
                font-size: 12px;
                border-radius: 8px;
                padding: 8px 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)
        self.btn_smart_report.clicked.connect(self._open_smart_report)
        bot_bar.addWidget(self.btn_smart_report)

        self.btn_whatsapp = QPushButton("📱 Veliye WhatsApp Gönder")
        self.btn_whatsapp.setMinimumHeight(40)
        self.btn_whatsapp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_whatsapp.setStyleSheet("""
            QPushButton {
                background-color: #25D366;
                color: white;
                font-weight: 700;
                font-size: 12px;
                border-radius: 8px;
                padding: 8px 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1ebd5b;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        self.btn_whatsapp.clicked.connect(self._send_whatsapp)
        self.btn_whatsapp.setEnabled(False)
        bot_bar.addWidget(self.btn_whatsapp)

        self.btn_save = QPushButton("💾 İlerlemeyi Kaydet")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: 700;
                font-size: 12px;
                border-radius: 8px;
                padding: 8px 20px;
                border: none;
            }
            QPushButton:hover {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #94a3b8;
            }
        """)
        self.btn_save.clicked.connect(self._save_progress)
        bot_bar.addWidget(self.btn_save)

        lay.addLayout(bot_bar)

    # --- TAB 4: GÖRÜŞME NOTLARI ---
    def _init_tab_notes(self, parent):
        l = QVBoxLayout(parent)
        l.setContentsMargins(10, 10, 10, 10)
        l.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # SOL PANEL: Geçmiş Görüşme Notları Arşivi
        left_box = QFrame()
        left_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;")
        lb_lay = QVBoxLayout(left_box)
        lb_lay.setContentsMargins(10, 10, 10, 10)
        lb_lay.setSpacing(8)

        lbl_hist_tit = QLabel("📋 Görüşme Notları Arşivi")
        lbl_hist_tit.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 12px;")
        lb_lay.addWidget(lbl_hist_tit)

        self.btn_new_note_session = QPushButton("➕ Bu Hafta İçin Not Yaz")
        self.btn_new_note_session.setStyleSheet("background: #2563eb; color: white; font-weight: 700; padding: 6px; border-radius: 6px; font-size: 11px;")
        self.btn_new_note_session.clicked.connect(self._reset_notes_to_current_week)
        lb_lay.addWidget(self.btn_new_note_session)

        self.list_past_notes = QListWidget()
        self.list_past_notes.setStyleSheet("""
            QListWidget { background: white; border: 1px solid #cbd5e1; border-radius: 6px; outline: none; }
            QListWidget::item { padding: 8px 10px; border-bottom: 1px solid #f1f5f9; color: #334155; font-size: 11px; }
            QListWidget::item:selected { background: #eff6ff; color: #1d4ed8; font-weight: 700; }
        """)
        self.list_past_notes.itemClicked.connect(self._on_past_note_selected)
        lb_lay.addWidget(self.list_past_notes, 1)

        splitter.addWidget(left_box)

        # SAĞ PANEL: Yapılandırılmış Görüşme Formu
        right_box = QFrame()
        right_box.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px;")
        rb_lay = QVBoxLayout(right_box)
        rb_lay.setContentsMargins(14, 12, 14, 12)
        rb_lay.setSpacing(10)

        # 1. Görüşme Üst Bilgi Barı
        info_card = QFrame()
        info_card.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px;")
        h_info = QHBoxLayout(info_card)
        h_info.setContentsMargins(8, 4, 8, 4)
        h_info.setSpacing(12)

        # Tarih
        from PyQt6.QtWidgets import QDateEdit
        from PyQt6.QtCore import QDate
        h_info.addWidget(QLabel("📅 Tarih:"))
        self.date_notes = QDateEdit(QDate.currentDate())
        self.date_notes.setCalendarPopup(True)
        self.date_notes.setDisplayFormat("dd.MM.yyyy")
        self.date_notes.setFixedWidth(105)
        h_info.addWidget(self.date_notes)

        # Tür
        h_info.addWidget(QLabel("🕒 Tür:"))
        self.cmb_notes_type = QComboBox()
        self.cmb_notes_type.addItems(["Birebir Yüz Yüze", "Online Görüşme (Zoom/Meet)", "Telefon Görüşmesi", "Veli & Öğrenci Toplantısı"])
        self.cmb_notes_type.setFixedWidth(175)
        h_info.addWidget(self.cmb_notes_type)

        # Mood / Ruh Hali
        h_info.addWidget(QLabel("⚡ Öğrenci Ruh Hali:"))
        self.cmb_notes_mood = QComboBox()
        self.cmb_notes_mood.addItems([
            "🔥 Çok Yüksek & Hırslı",
            "😊 Pozitif & İstekli",
            "⚖️ Normal / Dengeli",
            "🥱 Yorgun / İsteksiz",
            "😟 Kaygılı / Stresli"
        ])
        self.cmb_notes_mood.setFixedWidth(160)
        h_info.addWidget(self.cmb_notes_mood)
        h_info.addStretch()
        rb_lay.addWidget(info_card)

        # 2. Hızlı Koçluk Şablonları Barı
        h_tpl = QHBoxLayout()
        h_tpl.setSpacing(6)
        h_tpl.addWidget(QLabel("Hızlı Şablon:"))
        
        tpl_list = [
            ("📋 Haftalık Rutin", self._tpl_routine),
            ("📈 Deneme Analizi", self._tpl_deneme),
            ("🧘 Sınav Kaygısı", self._tpl_anxiety),
            ("⏱️ Zaman Yönetimi", self._tpl_time_mgmt)
        ]
        for t_name, t_func in tpl_list:
            btn_t = QPushButton(t_name)
            btn_t.setStyleSheet("padding: 3px 8px; font-size: 11px; background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; border-radius: 4px;")
            btn_t.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_t.clicked.connect(t_func)
            h_tpl.addWidget(btn_t)
        h_tpl.addStretch()
        rb_lay.addLayout(h_tpl)

        # 3. Not Sekmeleri
        self.tabs_notes_inner = QTabWidget()
        self.tabs_notes_inner.setStyleSheet("""
            QTabBar::tab { padding: 6px 14px; font-size: 11px; font-weight: 600; }
            QTabBar::tab:selected { color: #2563eb; border-bottom: 2px solid #2563eb; }
        """)

        # Sekme 1: Gündem ve Hafta Değerlendirmesi
        self.txt_note_agenda = QTextEdit()
        self.txt_note_agenda.setPlaceholderText("Bu haftaki ders çalışma performansı, çözülen soru sayısı, ödevlerin eksiksizliği ve görüşülen konular...")
        self.tabs_notes_inner.addTab(self.txt_note_agenda, "🎯 Gündem & Değerlendirme")

        # Sekme 2: Yeni Kararlar ve Aksiyon Maddeleri
        self.txt_note_actions = QTextEdit()
        self.txt_note_actions.setPlaceholderText("Önümüzdeki hafta için kararlaştırılan özel aksiyonlar (Örn: Her sabah 30 paragraf, Salı AYT Mat denemesi, uyku düzeni)...")
        self.tabs_notes_inner.addTab(self.txt_note_actions, "🚀 Yeni Kararlar & Aksiyonlar")

        # Sekme 3: Veli Notu & WhatsApp İletisi
        self.txt_note_parent = QTextEdit()
        self.txt_note_parent.setPlaceholderText("Veliye tek tıkla gönderilecek haftalık gelişim ve koçluk özeti...")
        self.tabs_notes_inner.addTab(self.txt_note_parent, "👨‍👩‍👦 Veli Bilgilendirme Notu")

        # Sekme 4: Ham Metin (Geriye dönük tam uyumluluk için txt_notes)
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Tüm görüşme notlarının birleşik metni...")
        self.tabs_notes_inner.addTab(self.txt_notes, "📝 Birleşik Not Metni")

        rb_lay.addWidget(self.tabs_notes_inner, 1)

        # 4. Alt Butonlar
        h_bot_notes = QHBoxLayout()
        h_bot_notes.setSpacing(8)

        btn_ai_note = QPushButton("🤖 Akıllı Koç Yorumu Üret")
        btn_ai_note.setStyleSheet("background-color: #7c3aed; color: white; padding: 7px 14px; font-weight: 700; border-radius: 6px;")
        btn_ai_note.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ai_note.clicked.connect(self._generate_auto_comment)
        h_bot_notes.addWidget(btn_ai_note)

        btn_wa_note = QPushButton("📱 Veliye WhatsApp İlet")
        btn_wa_note.setStyleSheet("background-color: #10b981; color: white; padding: 7px 14px; font-weight: 700; border-radius: 6px;")
        btn_wa_note.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_wa_note.clicked.connect(self._send_notes_whatsapp)
        h_bot_notes.addWidget(btn_wa_note)

        h_bot_notes.addStretch()

        btn_save_note = QPushButton("💾 Notları Kaydet")
        btn_save_note.setStyleSheet("background-color: #2563eb; color: white; padding: 7px 20px; font-weight: 800; border-radius: 6px;")
        btn_save_note.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_note.clicked.connect(self._save_notes)
        h_bot_notes.addWidget(btn_save_note)

        rb_lay.addLayout(h_bot_notes)
        splitter.addWidget(right_box)

        splitter.setStretchFactor(0, 28)
        splitter.setStretchFactor(1, 72)
        splitter.setSizes([220, 600])

        l.addWidget(splitter)

    # --- TAB 2: GELİŞİM ANALİZİ ---
    def _init_tab_analysis(self, parent):
        l = QVBoxLayout(parent)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(12)

        # 1. ÜST KPI ÖZET KARTLARI
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        def make_kpi(icon, title, val_def, accent_col):
            box = QFrame()
            box.setStyleSheet(f"""
                QFrame {{
                    background: white;
                    border: 1px solid #e2e8f0;
                    border-top: 3px solid {accent_col};
                    border-radius: 8px;
                    padding: 8px 12px;
                }}
            """)
            bl = QHBoxLayout(box)
            bl.setContentsMargins(6, 4, 6, 4)
            bl.setSpacing(10)

            ico = QLabel(icon)
            ico.setStyleSheet(f"font-size: 22px; background: {accent_col}15; border-radius: 16px; padding: 4px;")
            v = QVBoxLayout()
            v.setSpacing(1)
            t = QLabel(title)
            t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase;")
            val = QLabel(val_def)
            val.setStyleSheet("font-size: 17px; font-weight: 800; color: #0f172a;")
            v.addWidget(t); v.addWidget(val)
            bl.addWidget(ico); bl.addLayout(v); bl.addStretch()
            return box, val

        self.card_ana1, self.lbl_ana_rate = make_kpi("🎯", "Ortalama Başarı", "%0", "#10b981")
        self.card_ana2, self.lbl_ana_avg = make_kpi("📈", "Haftalık Soru Hacmi", "0 Soru", "#2563eb")
        self.card_ana3, self.lbl_ana_top = make_kpi("🌟", "En Aktif Ders", "—", "#f59e0b")
        self.card_ana4, self.lbl_ana_low = make_kpi("⚠️", "Takviye Gereken", "—", "#ef4444")

        kpi_row.addWidget(self.card_ana1)
        kpi_row.addWidget(self.card_ana2)
        kpi_row.addWidget(self.card_ana3)
        kpi_row.addWidget(self.card_ana4)
        l.addLayout(kpi_row)

        # 2. GRAFİK VE PERFORMANS TABLOSU (SPLITTER)
        ana_split = QSplitter(Qt.Orientation.Vertical)
        ana_split.setHandleWidth(2)

        # Grafikler (Haftalık Trend + Ders Dağılımı)
        chart_frame = QFrame()
        chart_frame.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 6px;")
        cf_lay = QVBoxLayout(chart_frame)
        cf_lay.setContentsMargins(4, 4, 4, 4)

        self.figure = plt.figure(figsize=(10, 4.2), dpi=90)
        self.canvas = FigureCanvas(self.figure)
        cf_lay.addWidget(self.canvas)
        ana_split.addWidget(chart_frame)

        # Alt Bölüm: Ders Bazlı İstatistik Tablosu ve AI Değerlendirmesi
        bot_widget = QWidget()
        bw_lay = QHBoxLayout(bot_widget)
        bw_lay.setContentsMargins(0, 4, 0, 0)
        bw_lay.setSpacing(10)

        # Tablo
        self.tbl_subject_stats = QTableWidget(0, 5)
        self.tbl_subject_stats.setHorizontalHeaderLabels(["Ders", "Toplam Hedef", "Toplam Çözülen", "Tamamlama %", "Koçluk Durumu"])
        hh_s = self.tbl_subject_stats.horizontalHeader()
        hh_s.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh_s.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_subject_stats.setStyleSheet("""
            QTableWidget { background: white; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 11px; }
            QHeaderView::section { background: #f8fafc; font-weight: 700; color: #475569; padding: 6px; border: none; border-bottom: 1px solid #e2e8f0; }
        """)
        bw_lay.addWidget(self.tbl_subject_stats, 6)

        # Koç Teşhis Kartı
        diag_card = QFrame()
        diag_card.setStyleSheet("background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px;")
        diag_lay = QVBoxLayout(diag_card)
        diag_lay.setSpacing(6)
        lbl_diag_tit = QLabel("💡 <b>Koçluk Gelişim Yorumu:</b>")
        lbl_diag_tit.setStyleSheet("color: #166534; font-size: 12px;")
        self.lbl_ana_diagnostic = QLabel("Öğrenci verileri inceleniyor...")
        self.lbl_ana_diagnostic.setWordWrap(True)
        self.lbl_ana_diagnostic.setStyleSheet("color: #15803d; font-size: 11px; line-height: 1.4;")
        diag_lay.addWidget(lbl_diag_tit)
        diag_lay.addWidget(self.lbl_ana_diagnostic, 1)
        bw_lay.addWidget(diag_card, 4)

        ana_split.addWidget(bot_widget)
        ana_split.setStretchFactor(0, 6)
        ana_split.setStretchFactor(1, 4)
        l.addWidget(ana_split, 1)

    # --- TAB 3: DERS PROGRAMI ---
    def _init_tab_schedule(self, parent):
        l = QVBoxLayout(parent)
        l.setContentsMargins(10, 10, 10, 10)
        l.setSpacing(10)

        # 1. Hızlı Ders Paleti ve Şablon Barı
        palette_card = QFrame()
        palette_card.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px;")
        pc_lay = QVBoxLayout(palette_card)
        pc_lay.setContentsMargins(8, 6, 8, 6)
        pc_lay.setSpacing(6)

        h_pal_top = QHBoxLayout()
        lbl_pal = QLabel("🎨 <b>Hızlı Ders & Aktivite Paleti:</b> (Hücreye tek tıkla boyamak için ders seçin)")
        lbl_pal.setStyleSheet("font-size: 11px; color: #475569;")
        h_pal_top.addWidget(lbl_pal)

        self.lbl_active_brush = QLabel("🖌️ Aktif Fırça: <b>Seçilmedi</b>")
        self.lbl_active_brush.setStyleSheet("color: #2563eb; font-size: 11px; font-weight: 700; background: #eff6ff; padding: 3px 8px; border-radius: 4px;")
        h_pal_top.addStretch()
        h_pal_top.addWidget(self.lbl_active_brush)
        pc_lay.addLayout(h_pal_top)

        # Çipler
        h_chips = QHBoxLayout()
        h_chips.setSpacing(6)
        self._active_brush_data = None

        chips = [
            ("📐 Matematik", "#dbeafe", "#1e40af"),
            ("⚡ Fizik", "#f3e8ff", "#6b21a8"),
            ("🧪 Kimya", "#fef3c7", "#92400e"),
            ("🧬 Biyoloji", "#dcfce7", "#166534"),
            ("📖 Türkçe", "#ffe4e6", "#9f1239"),
            ("🏛️ Sosyal", "#ffedd5", "#9a3412"),
            ("🏫 Okul", "#f1f5f9", "#334155"),
            ("📝 Deneme", "#e0e7ff", "#3730a3"),
            ("☕ Mola", "#ecfdf5", "#065f46"),
            ("🧹 Sil", "#ffffff", "#dc2626")
        ]

        for text, bg, fg in chips:
            btn_c = QPushButton(text)
            btn_c.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-weight: 700;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border-color: #2563eb;
                }}
            """)
            btn_c.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_c.clicked.connect(lambda _, t=text, b=bg, f=fg: self._set_schedule_brush(t, b, f))
            h_chips.addWidget(btn_c)

        h_chips.addStretch()

        # Hazır Şablonlar Butonu
        self.cmb_prog_templates = QComboBox()
        self.cmb_prog_templates.addItems([
            "📋 Hazır Program Şablonu...",
            "🏫 Okul + Akşam Etüt Rutini",
            "🎓 Mezun Yoğun Kamp Rutini",
            "🎒 LGS Dengeli Hazırlık",
            "🧹 Tüm Programı Temizle"
        ])
        self.cmb_prog_templates.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        self.cmb_prog_templates.currentIndexChanged.connect(self._apply_schedule_template)
        h_chips.addWidget(self.cmb_prog_templates)

        pc_lay.addLayout(h_chips)
        l.addWidget(palette_card)

        # 2. Haftalık Çizelge Tablosu
        self.table_schedule = QTableWidget()
        self.table_schedule.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_schedule.customContextMenuRequested.connect(self._show_schedule_context_menu)
        self.table_schedule.cellClicked.connect(self._on_schedule_cell_clicked)
        l.addWidget(self.table_schedule, 1)

        # 3. Alt Özet ve Aksiyon Barı
        bot_sched = QHBoxLayout()
        self.lbl_schedule_summary = QLabel("📊 Haftalık Net Çalışma Kapasitesi: Hesaplanıyor...")
        self.lbl_schedule_summary.setStyleSheet("color: #475569; font-weight: 700; font-size: 11px;")
        bot_sched.addWidget(self.lbl_schedule_summary)
        bot_sched.addStretch()

        btn_print_sched = QPushButton("🖨️ Yazdır / PDF")
        btn_print_sched.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 12px; font-weight: 600;")
        btn_print_sched.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_print_sched.clicked.connect(self._print_schedule_pdf)
        bot_sched.addWidget(btn_print_sched)

        btn_settings = QPushButton("⚙️ Zaman Ayarları")
        btn_settings.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 12px; font-weight: 600; color: #334155;")
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_settings.clicked.connect(self._show_schedule_settings)
        bot_sched.addWidget(btn_settings)

        btn_save_prog = QPushButton("💾 Programı Kaydet")
        btn_save_prog.setStyleSheet("background-color: #2563eb; color: white; padding: 7px 18px; font-weight: 800; border-radius: 6px;")
        btn_save_prog.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_prog.clicked.connect(self._save_schedule)
        bot_sched.addWidget(btn_save_prog)

        l.addLayout(bot_sched)
        self._rebuild_schedule_table()


    def _show_schedule_settings(self):
        dlg = ScheduleSettingsDialog(self)
        if dlg.exec():
            self._rebuild_schedule_table()
            # Varsa mevcut program verilerini tekrar yüklemeyi deneyebiliriz ama şu anlık tablo yapısı değiştiği için
            # kullanıcıya "Yeniden yükle" demesi daha sağlıklı olabilir veya otomatik yükleriz.
            if self.current_plan_id:
                con = db.get_conn()
                try:
                    self._load_schedule_data(con)
                finally:
                    con.close()

    def _rebuild_schedule_table(self):
        try:
            start_h = int(appset.ayar_get("schedule_start_hour", 9))
            end_h = int(appset.ayar_get("schedule_end_hour", 21))
        except ValueError:
            start_h = 9
            end_h = 21
        
        hours = [f"{h:02d}:00" for h in range(start_h, end_h + 1)] # Bitiş dahil
        
        self.table_schedule.clear()
        self.table_schedule.setRowCount(len(hours))
        self.table_schedule.setColumnCount(8) # Saat + 7 Gün
        
        days = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        self.table_schedule.setHorizontalHeaderLabels(days)
        
        # Stil Ayarları
        self.table_schedule.setAlternatingRowColors(True)
        self.table_schedule.setMouseTracking(True) # Hover için gerekli
        self.table_schedule.setStyleSheet("""
            QTableWidget { 
                gridline-color: #d1d5db; 
                selection-background-color: #bfdbfe; 
                selection-color: black; 
            }
            QTableWidget::item:hover {
                background-color: #dbeafe; /* Hover Efekti */
            }
            QHeaderView::section { 
                background-color: #f3f4f6; 
                font-weight: bold; 
                border: 1px solid #e5e7eb; 
                padding: 4px; 
            }
        """)
        
        for i, h in enumerate(hours):
            # Saat Sütunu
            item = QTableWidgetItem(h)
            item.setBackground(QColor("#eff6ff"))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_schedule.setItem(i, 0, item)
            
            # Gün Sütunları (Boş başlat)
            for j in range(1, 8):
                self.table_schedule.setItem(i, j, QTableWidgetItem(""))

        self.table_schedule.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_schedule.verticalHeader().setVisible(False)
        self.table_schedule.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_schedule.setColumnWidth(0, 70)

    def _show_schedule_context_menu(self, pos):
        # Tıklanan öğeyi bulmak için en güvenli yol: global cursor -> viewport mapping
        # `pos` bazen header kaymaları nedeniyle yanıltıcı olabilir.
        viewport_pos = self.table_schedule.viewport().mapFromGlobal(QCursor.pos())
        item = self.table_schedule.itemAt(viewport_pos)
        
        # Eğer bir öğeye tıklandıysa ve seçili değilse, seçimi ona kaydır
        # Böylece kullanıcı sağ tık yapınca o hücre seçilmiş olur ve işlemler o hücreye uygulanır.
        if item:
            if not item.isSelected():
                self.table_schedule.clearSelection()
                item.setSelected(True)
        else:
            # Boşluğa tıklandıysa menü açma
            return
            
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
                font-size: 13px;
                color: #374151;
            }
            QMenu::item:selected {
                background-color: #eff6ff; /* Hover Rengi */
                color: #2563eb;
                font-weight: bold;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e5e7eb;
                margin: 4px 0;
            }
        """)
        
        # Basit Eylemler
        act_add = QAction("➕ Ders Ekle", self)
        act_add.triggered.connect(self._ctx_add_lesson)
        
        act_color = QAction("🎨 Renk Seç", self)
        act_color.triggered.connect(self._ctx_set_color)
        
        act_clear = QAction("🗑️ Temizle", self)
        act_clear.triggered.connect(self._ctx_clear_cell)
        
        act_copy = QAction("📄 Kopyala", self)
        act_copy.triggered.connect(self._ctx_copy)
        
        act_paste = QAction("📋 Yapıştır", self)
        act_paste.triggered.connect(self._ctx_paste)

        menu.addAction(act_add)
        menu.addAction(act_color)
        menu.addSeparator()
        menu.addAction(act_copy)
        menu.addAction(act_paste)
        menu.addSeparator()
        menu.addAction(act_clear)
        
        menu.exec(self.table_schedule.viewport().mapToGlobal(pos))

    def _ctx_add_lesson(self):
        items = self.table_schedule.selectedItems()
        if not items: return
        
        # Basit bir diyalog veya preset listesi
        # Şimdilik manuel girişe (zaten edit edilebilir) ek olarak hızlı seçim sunalım.
        # Daha gelişmiş versiyonda burada SubjectSelection açılabilir.
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Ders Seç")
        dlg.setFixedSize(200, 300)
        l = QVBoxLayout(dlg)
        
        lst = QListWidget()
        lst.addItems(["Matematik", "Fizik", "Kimya", "Biyoloji", "Türkçe", "Tarih", "Coğrafya", "Felsefe", "Din K.", "İngilizce", "Geometri", "Mola", "Etüt"])
        l.addWidget(lst)
        
        def _apply():
            txt = lst.currentItem().text() if lst.currentItem() else ""
            if txt:
                for it in items:
                    if it.column() > 0: # Saat sütununa dokunma
                        it.setText(txt)
            dlg.accept()
            
        lst.itemDoubleClicked.connect(lambda x: _apply())
        btn_select = QPushButton("Seç ve Ekle")
        btn_select.clicked.connect(_apply)
        l.addWidget(btn_select)
        
        dlg.exec()

    def _ctx_set_color(self):
        items = self.table_schedule.selectedItems()
        if not items: return
        
        # Parent belirtmek önemli (macOS modal sorunu için)
        color = QColorDialog.getColor(Qt.GlobalColor.white, self, "Renk Seç")
        if color.isValid():
            for it in items:
                 if it.column() > 0:
                     it.setBackground(color)

    def _ctx_copy(self):
        items = self.table_schedule.selectedItems()
        if not items: return
        # Sadece ilk seçili öğeyi kopyalayalım
        it = items[0]
        self._copied_text = it.text()
        self._copied_bg = it.background()

    def _ctx_paste(self):
        if not hasattr(self, '_copied_text'): return
        
        items = self.table_schedule.selectedItems()
        for it in items:
            if it.column() > 0:
                it.setText(self._copied_text)
                it.setBackground(self._copied_bg)
                     
    def _ctx_clear_cell(self):
        for it in self.table_schedule.selectedItems():
            if it.column() > 0:
                it.setText("")
                it.setData(Qt.ItemDataRole.BackgroundRole, None) # Rengi sıfırla (Alternating color geri gelir)

    def _init_tab_topics(self, parent):
        l = QVBoxLayout(parent)
        l.setContentsMargins(10, 10, 10, 10)
        l.setSpacing(10)
        
        # 1. KPI Gösterge Kartları Paneli (Müfredat Hakimiyeti Özeti)
        kpi_frame = QFrame()
        kpi_frame.setStyleSheet("QFrame { background: transparent; }")
        kpi_layout = QHBoxLayout(kpi_frame)
        kpi_layout.setContentsMargins(0, 0, 0, 4)
        kpi_layout.setSpacing(12)

        # Kart 1: Müfredat İlerlemesi
        c1 = QFrame()
        c1.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-top: 3px solid #3b82f6;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        c1_lay = QVBoxLayout(c1)
        c1_lay.setContentsMargins(4, 4, 4, 4)
        c1_lay.setSpacing(4)
        c1_lay.addWidget(QLabel("<span style='font-size: 11px; font-weight: bold; color: #64748b;'>🎯 MÜFREDAT HAKİMİYETİ</span>"))
        self.lbl_topic_kpi_progress = QLabel("%0")
        self.lbl_topic_kpi_progress.setStyleSheet("font-size: 22px; font-weight: bold; color: #1e3a8a;")
        c1_lay.addWidget(self.lbl_topic_kpi_progress)
        self.pbar_topic_mastery = QProgressBar()
        self.pbar_topic_mastery.setRange(0, 100)
        self.pbar_topic_mastery.setValue(0)
        self.pbar_topic_mastery.setFixedHeight(6)
        self.pbar_topic_mastery.setTextVisible(False)
        self.pbar_topic_mastery.setStyleSheet("QProgressBar { background: #f1f5f9; border-radius: 3px; } QProgressBar::chunk { background: #3b82f6; border-radius: 3px; }")
        c1_lay.addWidget(self.pbar_topic_mastery)
        kpi_layout.addWidget(c1)

        # Kart 2: Tamamlanan / Sınava Hazır Konular
        c2 = QFrame()
        c2.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-top: 3px solid #10b981;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        c2_lay = QVBoxLayout(c2)
        c2_lay.setContentsMargins(4, 4, 4, 4)
        c2_lay.setSpacing(4)
        c2_lay.addWidget(QLabel("<span style='font-size: 11px; font-weight: bold; color: #64748b;'>🏆 TAM HAKİMİYET</span>"))
        self.lbl_topic_kpi_mastered = QLabel("0 / 0 Konu")
        self.lbl_topic_kpi_mastered.setStyleSheet("font-size: 22px; font-weight: bold; color: #065f46;")
        c2_lay.addWidget(self.lbl_topic_kpi_mastered)
        self.lbl_topic_kpi_sub_mastered = QLabel("Sınava hazır seviye")
        self.lbl_topic_kpi_sub_mastered.setStyleSheet("font-size: 11px; color: #059669;")
        c2_lay.addWidget(self.lbl_topic_kpi_sub_mastered)
        kpi_layout.addWidget(c2)

        # Kart 3: Tekrar ve Pekiştirme Bekleyenler
        c3 = QFrame()
        c3.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-top: 3px solid #f59e0b;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        c3_lay = QVBoxLayout(c3)
        c3_lay.setContentsMargins(4, 4, 4, 4)
        c3_lay.setSpacing(4)
        c3_lay.addWidget(QLabel("<span style='font-size: 11px; font-weight: bold; color: #64748b;'>🔄 TEKRAR & PEKİŞTİRME</span>"))
        self.lbl_topic_kpi_review = QLabel("0 Konu")
        self.lbl_topic_kpi_review.setStyleSheet("font-size: 22px; font-weight: bold; color: #92400e;")
        c3_lay.addWidget(self.lbl_topic_kpi_review)
        self.lbl_topic_kpi_sub_review = QLabel("Aralıklı tekrar bekleyen")
        self.lbl_topic_kpi_sub_review.setStyleSheet("font-size: 11px; color: #d97706;")
        c3_lay.addWidget(self.lbl_topic_kpi_sub_review)
        kpi_layout.addWidget(c3)

        # Kart 4: Kritik Sınav Konuları (ÖSYM/MEB)
        c4 = QFrame()
        c4.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-top: 3px solid #ef4444;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        c4_lay = QVBoxLayout(c4)
        c4_lay.setContentsMargins(4, 4, 4, 4)
        c4_lay.setSpacing(4)
        c4_lay.addWidget(QLabel("<span style='font-size: 11px; font-weight: bold; color: #64748b;'>🔥 KRİTİK SINAV KONULARI</span>"))
        self.lbl_topic_kpi_critical = QLabel("0 / 0 Hazır")
        self.lbl_topic_kpi_critical.setStyleSheet("font-size: 22px; font-weight: bold; color: #991b1b;")
        c4_lay.addWidget(self.lbl_topic_kpi_critical)
        self.lbl_topic_kpi_sub_critical = QLabel("ÖSYM'de çok soru çıkanlar")
        self.lbl_topic_kpi_sub_critical.setStyleSheet("font-size: 11px; color: #dc2626;")
        c4_lay.addWidget(self.lbl_topic_kpi_sub_critical)
        kpi_layout.addWidget(c4)

        l.addWidget(kpi_frame)

        # 2. Modern Filtre ve Kontrol Araç Çubuğu
        ctrl_card = QFrame()
        ctrl_card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        ctrl_lay = QVBoxLayout(ctrl_card)
        ctrl_lay.setContentsMargins(6, 6, 6, 6)
        ctrl_lay.setSpacing(8)

        # 1. Satır: Ders, Kaynak, Kitap Ekle, Arama, Filtre
        r1 = QHBoxLayout()
        r1.setSpacing(10)

        r1.addWidget(QLabel("<b>Ders:</b>"))
        self.cmb_topic_subject = QComboBox()
        self.cmb_topic_subject.setMinimumWidth(180)
        self.cmb_topic_subject.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 500;
                color: #1e293b;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: transparent;
            }
            QComboBox::drop-down:hover {
                background: #f1f5f9;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
            }
        """)
        self.cmb_topic_subject.addItems(list(TOPIC_LIST.keys()))
        self.cmb_topic_subject.currentTextChanged.connect(self._load_topics)
        r1.addWidget(self.cmb_topic_subject)

        r1.addWidget(QLabel("<b>Kaynak/Kitap:</b>"))
        self.cmb_topic_book = QComboBox()
        self.cmb_topic_book.setMinimumWidth(170)
        self.cmb_topic_book.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                color: #1e293b;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: transparent;
            }
            QComboBox::drop-down:hover {
                background: #f1f5f9;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
            }
        """)
        self.cmb_topic_book.currentTextChanged.connect(self._on_book_changed)
        r1.addWidget(self.cmb_topic_book)

        btn_add_book = QPushButton("➕ Kitap Ekle")
        btn_add_book.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_book.setFixedHeight(32)
        btn_add_book.setToolTip("Öğrencinin çözdüğü soru bankası veya fasikülü ekleyin (Örn: 345 TYT Matematik, Bilgi Sarmal, Apotemi vb.)")
        btn_add_book.setStyleSheet("""
            QPushButton {
                background-color: #16a34a; 
                color: white; 
                font-weight: bold; 
                font-size: 11px;
                border-radius: 6px;
                padding: 0 12px;
                border: none;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        btn_add_book.clicked.connect(self._add_new_book)
        r1.addWidget(btn_add_book)

        self.btn_del_book = QPushButton("🗑️")
        self.btn_del_book.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_del_book.setFixedHeight(32)
        self.btn_del_book.setFixedWidth(32)
        self.btn_del_book.setToolTip("Seçili kitabı ve bu kitaba ait takipleri sil")
        self.btn_del_book.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2; 
                color: #b91c1c; 
                font-weight: bold; 
                font-size: 12px;
                border-radius: 6px;
                border: 1px solid #fca5a5;
            }
            QPushButton:hover { background-color: #fecaca; }
            QPushButton:disabled { background-color: #f1f5f9; color: #94a3b8; border-color: #cbd5e1; }
        """)
        self.btn_del_book.setEnabled(False)
        self.btn_del_book.clicked.connect(self._delete_current_book)
        r1.addWidget(self.btn_del_book)

        r1.addSpacing(10)

        # Canlı Arama
        from PyQt6.QtWidgets import QLineEdit
        self.txt_topic_search = QLineEdit()
        self.txt_topic_search.setPlaceholderText("🔍 Konu ara...")
        self.txt_topic_search.setFixedWidth(160)
        self.txt_topic_search.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #3b82f6; }
        """)
        self.txt_topic_search.textChanged.connect(self._load_topics)
        r1.addWidget(self.txt_topic_search)

        # Durum Filtresi
        r1.addWidget(QLabel("<b>Filtre:</b>"))
        self.cmb_topic_filter = QComboBox()
        self.cmb_topic_filter.setFixedWidth(170)
        self.cmb_topic_filter.setStyleSheet("""
            QComboBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 12px;
                color: #1e293b;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #e2e8f0;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: transparent;
            }
            QComboBox::drop-down:hover {
                background: #f1f5f9;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
            }
        """)
        self.cmb_topic_filter.addItems([
            "Tüm Konular",
            "Sadece Eksikler",
            "Çalışılıyor / Pekiştirme",
            "Tam Hakimiyet (Bitenler)",
            "Tekrar Bekleyenler",
            "🔥 Kritik Sınav Konuları"
        ])
        self.cmb_topic_filter.currentTextChanged.connect(self._load_topics)
        r1.addWidget(self.cmb_topic_filter)

        r1.addStretch()
        ctrl_lay.addLayout(r1)

        # 2. Satır: Eylem Butonları
        r2 = QHBoxLayout()
        r2.setSpacing(10)

        btn_curriculum_rep = QPushButton("📊 Müfredat Hakimiyet Raporu")
        btn_curriculum_rep.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_curriculum_rep.setFixedHeight(30)
        btn_curriculum_rep.setStyleSheet("""
            QPushButton {
                background: #eff6ff;
                color: #1d4ed8;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 14px;
                border: 1px solid #93c5fd;
            }
            QPushButton:hover { background: #dbeafe; }
        """)
        btn_curriculum_rep.clicked.connect(self._open_curriculum_report)
        r2.addWidget(btn_curriculum_rep)

        btn_transfer_weekly = QPushButton("🎯 Eksikleri Bu Haftaki Plana Aktar")
        btn_transfer_weekly.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_transfer_weekly.setFixedHeight(30)
        btn_transfer_weekly.setStyleSheet("""
            QPushButton {
                background: #f0fdf4;
                color: #15803d;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 14px;
                border: 1px solid #86efac;
            }
            QPushButton:hover { background: #dcfce7; }
        """)
        btn_transfer_weekly.clicked.connect(self._transfer_to_weekly_plan)
        r2.addWidget(btn_transfer_weekly)

        btn_refresh_topics = QPushButton("🔄 Yenile")
        btn_refresh_topics.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh_topics.setFixedHeight(30)
        btn_refresh_topics.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                color: #475569;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 0 12px;
                border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background: #f1f5f9; }
        """)
        btn_refresh_topics.clicked.connect(self._load_topics)
        r2.addWidget(btn_refresh_topics)

        r2.addStretch()
        ctrl_lay.addLayout(r2)

        l.addWidget(ctrl_card)
        
        # 3. Analitik Konu Tablosu
        self.table_topics = QTableWidget()
        self.table_topics.setColumnCount(7)
        self.table_topics.setHorizontalHeaderLabels([
            "Konu & Sınav Ağırlığı", 
            "Koçluk Hakimiyet Düzeyi", 
            "Kavrama Oranı", 
            "Çözülen Soru", 
            "Aralıklı Tekrar", 
            "Koç Notu", 
            "Strateji Rehberi"
        ])
        
        header = self.table_topics.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)      # Konu Adı: Esnek
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)        # Hakimiyet: Sabit 210
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)        # Kavrama: Sabit 130
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)        # Soru: Sabit 120
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)        # Tekrar: Sabit 140
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)        # Koç Notu: Sabit 100
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)        # Rehber: Sabit 110
        
        self.table_topics.setColumnWidth(1, 210)
        self.table_topics.setColumnWidth(2, 130)
        self.table_topics.setColumnWidth(3, 120)
        self.table_topics.setColumnWidth(4, 140)
        self.table_topics.setColumnWidth(5, 100)
        self.table_topics.setColumnWidth(6, 110)
        
        self.table_topics.verticalHeader().setVisible(False)
        self.table_topics.verticalHeader().setDefaultSectionSize(62)
        self.table_topics.setAlternatingRowColors(True)
        self.table_topics.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid #cbd5e1;
                padding: 6px;
                height: 36px;
            }
        """)
        
        l.addWidget(self.table_topics)


    # --- LİSTELEME ---
    def _load_students(self):
        self.list_students.clear()
        con = db.get_conn()
        try:
            rows = con.execute("SELECT id, ad, soyad, ana_grup, alt_grup FROM ogrenci WHERE aktif=1 ORDER BY ad, soyad").fetchall()
            if hasattr(self, 'lbl_student_count'):
                self.lbl_student_count.setText(f"({len(rows)} Aktif)")
            for r in rows:
                full_name = f"{r['ad']} {r['soyad']}"
                ana_grup = str(r["ana_grup"] or "").strip()
                alt_grup = str(r["alt_grup"] or "").strip()
                
                parts = []
                if ana_grup: parts.append(ana_grup)
                if alt_grup: parts.append(alt_grup)
                grp_text = " • ".join(parts) if parts else "Genel"
                
                item = QListWidgetItem(f"{full_name}\n  ↳ {grp_text}")
                item.setData(Qt.ItemDataRole.UserRole, r['id'])
                item.setData(Qt.ItemDataRole.UserRole + 1, full_name)
                item.setData(Qt.ItemDataRole.UserRole + 2, ana_grup)
                item.setData(Qt.ItemDataRole.UserRole + 3, alt_grup)
                item.setData(Qt.ItemDataRole.UserRole + 4, grp_text)
                self.list_students.addItem(item)
                
            # Eğer öğrenci varsa ve hiçbiri seçili değilse ilk öğrenciyi otomatik seç
            if rows and self.current_student_id is None:
                first_item = self.list_students.item(0)
                self.list_students.setCurrentItem(first_item)
                self._on_student_selected(first_item)
        finally:
            con.close()
            
    def _filter_students(self, text):
        query = text.lower().strip()
        for i in range(self.list_students.count()):
            item = self.list_students.item(i)
            full_name = item.data(Qt.ItemDataRole.UserRole + 1) or ""
            grp = item.data(Qt.ItemDataRole.UserRole + 4) or ""
            search_str = f"{full_name} {grp}".lower()
            item.setHidden(query not in search_str)

    def _on_student_selected(self, item):
        self.current_student_id = item.data(Qt.ItemDataRole.UserRole)
        std_name = item.data(Qt.ItemDataRole.UserRole + 1) or item.text().split("\n")[0].strip()
        ana_grup = item.data(Qt.ItemDataRole.UserRole + 2) or ""
        alt_grup = item.data(Qt.ItemDataRole.UserRole + 3) or ""
        grp_text = item.data(Qt.ItemDataRole.UserRole + 4) or ""
        
        self.current_student_name = std_name
        self.current_student_group = grp_text
        
        if hasattr(self, 'lbl_student_chip'):
            self.lbl_student_chip.setText(f"👤 {std_name}")
        if hasattr(self, 'lbl_student_badge'):
            self.lbl_student_badge.setText(grp_text if grp_text else "Genel")
            self.lbl_student_badge.setVisible(True)
            
        self.lbl_student_name.setText(f"Öğrenci: {std_name}")
        self.right_widget.setEnabled(True)
        
        # Sınav sayacını öğrencinin hedefine göre (YKS vs LGS) dinamik güncelle
        self._update_exam_countdown()
        
        if hasattr(self.tab_survey, 'set_student'):
            self.tab_survey.set_student(self.current_student_id, std_name)
        else:
            self.tab_survey.reset_form()
            
        self._load_plan()
        self._load_student_koc_info() # Görüşme saatini yükle

    def _load_student_koc_info(self):
        if not self.current_student_id: return
        con = db.get_conn()
        try:
            r = con.execute("SELECT kocluk_gunu, kocluk_saati FROM ogrenci WHERE id=?", (self.current_student_id,)).fetchone()
            if r:
                gun = r["kocluk_gunu"] or ""
                saat = r["kocluk_saati"] or "00:00"
                
                # Combo set
                idx = self.cb_koc_gun.findText(gun)
                if idx >= 0: self.cb_koc_gun.setCurrentIndex(idx)
                else: self.cb_koc_gun.setCurrentIndex(0)
                
                from PyQt6.QtCore import QTime
                try:
                    t = QTime.fromString(saat, "HH:mm")
                    if t.isValid(): self.te_koc_saat.setTime(t)
                    else: self.te_koc_saat.setTime(QTime(0,0))
                except: pass
        except Exception as e:
            print(f"Koc info load error: {e}")
            
    def _save_student_koc_info(self):
        if not self.current_student_id: 
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir öğrenci seçiniz.")
            return
            
        gun = self.cb_koc_gun.currentText().strip()
        saat = self.te_koc_saat.time().toString("HH:mm")
        
        # Validation check
        if not gun:
            QMessageBox.warning(self, "Eksik Seçim", "⚠️ Lütfen bir <b>Görüşme Günü</b> seçiniz.")
            return
            
        con = db.get_conn()
        try:
            con.execute("UPDATE ogrenci SET kocluk_gunu=?, kocluk_saati=? WHERE id=?", (gun, saat, self.current_student_id))
            con.commit()
            
            # Professional feedback
            std_name = self.current_student_name or self.lbl_student_name.text().replace("Öğrenci: ", "").replace("Seçili Öğrenci: ", "").strip()
            msg = (f"✅ <b>{std_name}</b> adlı öğrencinin haftalık görüşme planı kaydedildi.<br><br>"
                   f"📅 <b>Görüşme Günü:</b> {gun}<br>"
                   f"⏰ <b>Görüşme Saati:</b> {saat}")
            
            QMessageBox.information(self, "Görüşme Planı Kaydedildi", msg)
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    # --- PLAN YÖNETİMİ ---
    def _get_week_start(self):
        # Seçili tarihin pazartesisini bul
        sel_date = self.dt_week.date()
        # dayOfWeek: 1=Ptesi, 7=Pazar
        offset = sel_date.dayOfWeek() - 1
        start = sel_date.addDays(-offset)
        return start

    def _load_plan(self):
        if not self.current_student_id: return
        
        start_date = self._get_week_start()
        start_str = start_date.toString("yyyy-MM-dd")
        
        con = db.get_conn()
        try:
            # Plan var mı?
            row = con.execute("""
                SELECT id, notlar FROM koc_plan 
                WHERE ogrenci_id=? AND baslangic_tarihi=?
            """, (self.current_student_id, start_str)).fetchone()
            
            self.table_goals.setRowCount(0)
            
            if row:
                self.current_plan_id = row["id"]
                self.btn_create_plan.setText("🔄 Haftalık Planı Yeniden Düzenle")
                self.btn_create_plan.setVisible(True)
                self.btn_save.setEnabled(True)
                self.btn_whatsapp.setEnabled(True)
                if hasattr(self, 'lbl_no_plan_notice'):
                    self.lbl_no_plan_notice.setVisible(False)
                self.table_goals.setVisible(True)
                
                # NOTLAR (Yapılandırılmış alanlara ayrıştır)
                self._populate_notes_fields(row["notlar"] or "")
                
                self._load_goals(con)
                self._load_schedule_data(con) # Program
                self._update_analysis_chart(con) # Grafik & KPI
                self._load_past_notes_list(con) # Not arşivi
                self._recalc_schedule_hours()
            else:
                self.current_plan_id = None
                self.btn_create_plan.setText("✨ Bu Hafta İçin Yeni Plan Oluştur")
                self.btn_create_plan.setVisible(True)
                self.btn_save.setEnabled(False)
                self.btn_whatsapp.setEnabled(False)
                self._populate_notes_fields("")
                self.table_goals.setRowCount(0)
                if hasattr(self, 'lbl_no_plan_notice'):
                    self.lbl_no_plan_notice.setVisible(True)
                    self.table_goals.setVisible(False)
                
                # Görsel Kartları Sıfırla
                self.lbl_total_target.setText("0")
                self.lbl_total_solved.setText("0")
                self.lbl_completion_rate.setText("%0")
                self.lbl_completion_rate.setStyleSheet("color: #64748b; font-size: 24px; font-weight: 800; border:none; background:transparent;")
                if hasattr(self, 'lbl_completion_sub'):
                    self.lbl_completion_sub.setText("Bu hafta için plan yok")
                if hasattr(self, 'lbl_ai_comment'):
                    self.lbl_ai_comment.setText("Bu hafta için henüz bir hedef planı oluşturulmamış.")
                
                # Tablodaki içerikleri temizle (Plan yoksa)
                self._clear_schedule_grid()
                self._update_analysis_chart(con)
                self._load_past_notes_list(con)
                self._recalc_schedule_hours()

            # Konu Takibi her durumda yüklenmeli (Plan'dan bağımsız)
            self._load_topics()
        finally:
            con.close()

    def _clear_schedule_grid(self):
        rows = self.table_schedule.rowCount()
        cols = self.table_schedule.columnCount()
        for r in range(rows):
            for c in range(1, cols):
                self.table_schedule.setItem(r, c, QTableWidgetItem(""))
                if self.table_schedule.item(r, c):
                    self.table_schedule.item(r, c).setBackground(QColor(0,0,0,0))
                    self.table_schedule.item(r, c).setData(Qt.ItemDataRole.BackgroundRole, None)

    def _load_goals(self, con):
        rows = con.execute("SELECT * FROM koc_hedef WHERE plan_id=?", (self.current_plan_id,)).fetchall()
        self.table_goals.setRowCount(len(rows))
        
        total_target = 0
        total_solved = 0
        
        for i, row_data in enumerate(rows):
            r = dict(row_data)
            # 0: Ders
            it_ders = QTableWidgetItem(r["ders_adi"])
            it_ders.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table_goals.setItem(i, 0, it_ders)
            
            # 1: Hedef (Soru)
            it_hs = QTableWidgetItem(str(r["hedef_soru"]))
            it_hs.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_goals.setItem(i, 1, it_hs)
            
            # 2: Çözülen (Soru)
            it_cs = QTableWidgetItem(str(r["cozulen_soru"]))
            it_cs.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_cs.setBackground(QColor("#f0fdf4"))
            it_cs.setForeground(QColor("#15803d"))
            it_cs.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table_goals.setItem(i, 2, it_cs)

            # 3: Hedef (Saat)
            h_saat = r.get("hedef_saat", 0) or 0
            it_hh = QTableWidgetItem(str(h_saat))
            it_hh.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_goals.setItem(i, 3, it_hh)

            # 4: Çalışılan (Saat)
            c_saat = r.get("calisilan_saat", 0) or 0
            it_ch = QTableWidgetItem(str(c_saat))
            it_ch.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_ch.setBackground(QColor("#eff6ff"))
            it_ch.setForeground(QColor("#1d4ed8"))
            it_ch.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table_goals.setItem(i, 4, it_ch)
            
            # Kartlar için data topla
            total_target += r["hedef_soru"]
            total_solved += r["cozulen_soru"]
            
            # 5: Progress Bar (Soru bazlı)
            pbar = QProgressBar()
            pbar.setRange(0, max(1, r["hedef_soru"]))
            pbar.setValue(min(r["cozulen_soru"], max(1, r["hedef_soru"])))
            
            pct = 0
            if r["hedef_soru"] > 0: pct = r["cozulen_soru"] / r["hedef_soru"]
            
            pct_int = int(pct * 100)
            pbar.setFormat(f"%{pct_int}")
            pbar.setTextVisible(True)
            
            if pct >= 1.0: bar_color = "#059669"
            elif pct >= 0.5: bar_color = "#d97706"
            else: bar_color = "#dc2626"
            
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    background-color: #f1f5f9;
                    text-align: center;
                    font-size: 11px;
                    font-weight: 700;
                    color: #1e293b;
                    height: 22px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 5px;
                }}
            """)
            self.table_goals.setCellWidget(i, 5, pbar)

        # Kartları Güncelle
        self.lbl_total_target.setText(f"{total_target:,}".replace(",", "."))
        self.lbl_total_solved.setText(f"{total_solved:,}".replace(",", "."))
        rate = 0
        if total_target > 0: rate = int((total_solved / total_target) * 100)
        
        self.lbl_completion_rate.setText(f"%{rate}")
        
        # Renklendirme ve Alt Durum
        if rate >= 80:
            color = "#059669"
            sub = f"🌟 Harika Performans (%{rate})"
        elif rate >= 50:
            color = "#d97706"
            sub = f"⚡ İstikrarlı İlerleme (%{rate})"
        else:
            color = "#dc2626"
            sub = f"⚠️ Tempoyu Artırmalıyız (%{rate})" if total_target > 0 else "Henüz Veri Yok"
            
        self.lbl_completion_rate.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 800; border:none; background:transparent;")
        if hasattr(self, 'lbl_completion_sub'):
            self.lbl_completion_sub.setText(sub)
        
        # AI Yorum Güncelle
        if hasattr(self, 'lbl_ai_comment'):
            if total_target == 0:
                self.lbl_ai_comment.setText("Henüz bir hedef planı oluşturulmamış.")
            elif rate < 30:
                self.lbl_ai_comment.setText(f"Henüz yolun başındayız (%{rate}). Bu hafta hedeflere odaklanıp tempoyu yükseltmeliyiz! 🚀")
            elif rate < 70:
                self.lbl_ai_comment.setText(f"İyi bir ilerleme var (%{rate}). Kalan günlerde hedefleri yakalamak için gayreti sürdürelim. 💪")
            else:
                self.lbl_ai_comment.setText(f"Mükemmel performans! Hedeflerin %{rate}'i tamamlandı. Bu disiplin başarı getirecektir! 🌟")

    def _create_plan(self):
        if not self.current_student_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce sol listeden bir öğrenci seçin.")
            return

        student_name = ""
        group_str = ""
        con = db.get_conn()
        try:
            r = con.execute("SELECT ad, soyad, ana_grup FROM ogrenci WHERE id=?", (self.current_student_id,)).fetchone()
            if r:
                student_name = f"{r['ad']} {r['soyad']}".strip()
                group_str = str(r["ana_grup"] or "")
        finally:
            con.close()

        start_date = self._get_week_start()
        dlg = WeeklyPlanCreateDialog(student_name, group_str, start_date, self)
        if dlg.exec():
            selected_goals = dlg.get_selected_goals()
            if not selected_goals:
                QMessageBox.warning(self, "Uyarı", "Lütfen en az bir ders seçin.")
                return

            end_date = start_date.addDays(6)
            con = db.get_conn()
            try:
                # Var olan bir plan var mı kontrol et
                existing = con.execute("""
                    SELECT id FROM koc_plan WHERE ogrenci_id=? AND baslangic_tarihi=?
                """, (self.current_student_id, start_date.toString("yyyy-MM-dd"))).fetchone()

                if existing:
                    plan_id = existing["id"]
                    con.execute("DELETE FROM koc_hedef WHERE plan_id=?", (plan_id,))
                else:
                    cur = con.execute("""
                        INSERT INTO koc_plan (ogrenci_id, baslangic_tarihi, bitis_tarihi)
                        VALUES (?, ?, ?)
                    """, (self.current_student_id, start_date.toString("yyyy-MM-dd"), end_date.toString("yyyy-MM-dd")))
                    plan_id = cur.lastrowid

                for ders_adi, hedef_soru in selected_goals:
                    con.execute("""
                        INSERT INTO koc_hedef (plan_id, ders_adi, hedef_soru, cozulen_soru, hedef_saat, calisilan_saat)
                        VALUES (?, ?, ?, 0, 0, 0)
                    """, (plan_id, ders_adi, hedef_soru))

                con.commit()
                self._load_plan()
                QMessageBox.information(
                    self,
                    "Plan Oluşturuldu ✨",
                    f"<b>{student_name}</b> için <b>{len(selected_goals)}</b> ders içeren haftalık hedef planı başarıyla oluşturuldu!<br><br>"
                    "Artık hedefleri takip edebilir ve çözülen soruları kaydedebilirsiniz."
                )
            finally:
                con.close()

    def _save_progress(self):
        if not self.current_plan_id: return
        
        con = db.get_conn()
        try:
            rows = self.table_goals.rowCount()
            for r in range(rows):
                subject = self.table_goals.item(r, 0).text()
                
                # Sütun indeksleri kaydı:
                # 0:Ders, 1:HedefSoru, 2:Çözülen, 3:HedefSaat, 4:Çalışılan, 5:Bar
                
                # Hedef Soru (Güncelleme imkanı tanıyalım)
                try: h_soru = int(self.table_goals.item(r, 1).text())
                except: h_soru = 0
                
                try: c_soru = int(self.table_goals.item(r, 2).text())
                except: c_soru = 0
                
                try: h_saat = float(self.table_goals.item(r, 3).text())
                except: h_saat = 0.0
                
                try: c_saat = float(self.table_goals.item(r, 4).text())
                except: c_saat = 0.0
                
                con.execute("""
                    UPDATE koc_hedef 
                    SET hedef_soru=?, cozulen_soru=?, hedef_saat=?, calisilan_saat=?
                    WHERE plan_id=? AND ders_adi=?
                """, (h_soru, c_soru, h_saat, c_saat, self.current_plan_id, subject))
            
            con.commit()
            QMessageBox.information(self, "Kaydedildi", "İlerlemeler güncellendi.")
            self._load_plan() # Progress barları güncelle
        finally:
            con.close()

    def _send_whatsapp(self):
        if not self.current_plan_id or not self.current_student_id: return
        
        # 1. Verileri Hazırla
        con = db.get_conn()
        try:
            # Öğrenci ve Veli Tel
            ogr = con.execute("SELECT ad, soyad, veli_tel1, veli_tel2 FROM ogrenci WHERE id=?", (self.current_student_id,)).fetchone()
            if not ogr: return
            
            tel = ogr["veli_tel1"] or ogr["veli_tel2"]
            if not tel:
                QMessageBox.warning(self, "Numara Yok", "Öğrenciye ait veli numarası bulunamadı.")
                return
            
            # Plan Verileri
            rows = con.execute("SELECT * FROM koc_hedef WHERE plan_id=?", (self.current_plan_id,)).fetchall()
            
            student_name = f"{ogr['ad']} {ogr['soyad']}"
            tarih = self.dt_week.date().toString("dd.MM.yyyy")

            # --- Raporu Zenginleştir ---
            import random
            motivational_quotes = [
                "🚀 Harika gidiyorsun! Aynı azimle devam.",
                "🌟 Başarı tesadüf değildir, çabanız takdire şayan.",
                "💪 Adım adım hedefe yaklaşıyoruz.",
                "✨ Potansiyelin çok yüksek, sana inanıyoruz.",
                "📚 Çalışmalarının karşılığını alacağına eminim."
            ]
            quote = random.choice(motivational_quotes)

            # --- DETAYLI ANALİZ HESAPLA ---
            total_target = 0
            total_solved = 0
            total_hours_target = 0.0
            total_hours_done = 0.0
            
            best_subj = ("-", -1) # (Name, Rate)
            weak_subj = ("-", 999) # (Name, Rate)
            
            detail_lines = ""
            for row_data in rows:
                r = dict(row_data)
                d_target = r["hedef_soru"]
                d_solved = r["cozulen_soru"]
                h_target = r.get("hedef_saat", 0) or 0
                h_done = r.get("calisilan_saat", 0) or 0
                
                total_target += d_target
                total_solved += d_solved
                total_hours_target += h_target
                total_hours_done += h_done
                
                # Başarı Oranı
                d_rate = 0
                if d_target > 0: d_rate = (d_solved / d_target) * 100
                
                # En İyi / En Zayıf Analizi
                if d_rate > best_subj[1] and d_target > 0: best_subj = (r["ders_adi"], d_rate)
                if d_rate < weak_subj[1] and d_target > 0: weak_subj = (r["ders_adi"], d_rate)
                
                # İkon
                icon = "✅" if d_rate >= 100 else ("⚠️" if d_rate > 0 else "⭕")
                detail_lines += f"{icon} *{r['ders_adi']}*: {d_solved}/{d_target} (%{int(d_rate)})\n"

            # Genel Oran
            rate = int((total_solved / total_target * 100)) if total_target > 0 else 0
            
            # --- MESAJ OLUŞTUR ---
            msg = f"🎓 *KOÇLUK PERFORMANS RAPORU*\n"
            msg += f"👤 *Öğrenci:* {student_name}\n"
            msg += f"🗓️ *Hafta:* {tarih}\n\n"
            
            msg += f"📊 *GENEL DURUM:*\n"
            msg += f"• Başarı Oranı: *%{rate}*\n"
            msg += f"• Toplam Soru: *{total_solved}* / {total_target}\n"
            if total_hours_done > 0:
                msg += f"• Çalışma Süresi: *{total_hours_done} Saat*\n"
            
            msg += f"\n🧠 *ANALİZ NOTLARI:*\n"
            if best_subj[1] > -1:
                msg += f"🔥 *Yıldız Ders:* {best_subj[0]} (%{int(best_subj[1])})\n"
            if weak_subj[1] < 999:
                 msg += f"🛡️ *Desteklenmeli:* {weak_subj[0]} (%{int(weak_subj[1])})\n"
            
            # AI Yorumunu Ekle
            if hasattr(self, 'lbl_ai_comment') and self.lbl_ai_comment.text() and "Veri bekleniyor" not in self.lbl_ai_comment.text():
                 ai_txt = self.lbl_ai_comment.text().replace("Yapay Zeka Koç Yorumu:", "").strip()
                 msg += f"\n🤖 *KOÇ YORUMU:*\n_{ai_txt}_\n"

            msg += "──────────────\n"
            msg += "*DERS DETAYLARI:*\n"
            msg += detail_lines
            msg += "\n💡 *" + quote + "*\n"
            msg += "✨ _Başarılar dileriz._"
            
            # --- YENİ MODERN PREVIEW DIALOG ---
            from ui.report_preview_dialog import ReportPreviewDialog
            
            dlg = ReportPreviewDialog(self, msg, student_name, tel)
            if dlg.exec():
                final_msg = dlg.final_text # Kullanıcı düzenlemiş olabilir
                
                # Sadece Text Gönderimi (Güvenli)
                res = whatsapp.whatsapp_gonder(
                    numaralar=[tel],
                    mesaj=final_msg,
                    ogrenci_id=self.current_student_id
                )
                
                if res.get("gonderilen", 0) > 0:
                    QMessageBox.information(self, "Başarılı", "Rapor başarıyla gönderildi! 🚀")
                else:
                    QMessageBox.warning(self, "Hata", f"Gönderilemedi.\nHatalı Numaralar: {res.get('fail')}")
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Rapor oluşturulurken hata: {str(e)}")
        finally:
            con.close()

    def _create_coaching_html(self, ogrenci, tarih, rows, t_target, t_solved, rate):
        # Renkler
        c_blue = "#1e40af"
        c_bg = "#f8fafc"
        
        # Satırları oluştur
        rows_html = ""
        for r_raw in rows:
            r = dict(r_raw)
            dt = r["hedef_soru"]
            ds = r["cozulen_soru"]
            p = int((ds/dt)*100) if dt > 0 else 0
            
            color = "#15803d" if p >= 100 else ("#b45309" if p >= 50 else "#b91c1c")
            bar_w = min(100, p)
            
            rows_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; font-weight: bold; color: #334155;">{r['ders_adi']}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{r['kitap_adi'] or '-'}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">{r['konu_adi'] or '-'}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: center; font-weight: bold;">{dt}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: center; color: {color}; font-weight: 800;">{ds}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e2e8f0; width: 20%;">
                    <div style="background-color: #e2e8f0; height: 6px; border-radius: 3px;">
                        <div style="background-color: {color}; width: {bar_w}%; height: 6px; border-radius: 3px;"></div>
                    </div>
                </td>
            </tr>
            """

        rate_color = "#15803d" if rate >= 80 else "#b45309"
        stat_color = "#15803d" if rate >= 80 else "#b91c1c"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; }}
                h1 {{ color: {c_blue}; font-size: 24px; margin-bottom: 5px; }}
                .box {{ border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; background-color: white; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
                th {{ text-align: left; background-color: {c_bg}; padding: 8px; border-bottom: 2px solid #94a3b8; color: #475569; }}
                .stat-box {{ text-align: center; padding: 10px; border: 1px solid #e2e8f0; border-radius: 6px; background-color: #f1f5f9; }}
                .val {{ font-size: 18px; font-weight: bold; color: {c_blue}; }}
                .lbl {{ font-size: 10px; color: #64748b; text-transform: uppercase; }}
            </style>
        </head>
        <body style="background-color: #f8fafc; padding: 20px;">
            
            <div style="text-align: center; margin-bottom: 30px;">
                <h1>HAFTALIK KOÇLUK RAPORU</h1>
                <div style="color: #64748b; font-size: 14px;">{tarih} Tarihli Gelişim Raporu</div>
            </div>

            <div class="box">
                <table style="width: 100%;">
                    <tr>
                        <td width="60%">
                            <div style="font-size: 10px; color: #94a3b8; font-weight: bold; text-transform: uppercase;">ÖĞRENCİ</div>
                            <div style="font-size: 18px; font-weight: bold; color: #0f172a;">{ogrenci}</div>
                        </td>
                        <td width="40%" align="right">
                             <div style="font-size: 10px; color: #94a3b8; font-weight: bold; text-transform: uppercase;">GENEL BAŞARI</div>
                             <div style="font-size: 24px; font-weight: 900; color: {rate_color};">%{rate}</div>
                        </td>
                    </tr>
                </table>
            </div>

            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <table style="width:100%"><tr>
                <td width="33%"><div class="stat-box"><span class="val">{t_target}</span><br><span class="lbl">HEDEF SORU</span></div></td>
                <td width="33%"><div class="stat-box"><span class="val" style="color:#0f172a;">{t_solved}</span><br><span class="lbl">ÇÖZÜLEN SORU</span></div></td>
                <td width="33%"><div class="stat-box"><span class="val" style="color:{stat_color};">%{rate}</span><br><span class="lbl">BAŞARI ORANI</span></div></td>
                </tr></table>
            </div>

            <div class="box">
                <div style="font-weight: bold; margin-bottom: 10px; font-size: 14px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px;">DERS BAZLI DETAYLAR</div>
                <table>
                    <thead>
                        <tr>
                            <th width="20%">DERS</th>
                            <th width="20%">KİTAP</th>
                            <th width="20%">KONU</th>
                            <th width="10%" style="text-align: center;">HEDEF</th>
                            <th width="10%" style="text-align: center;">ÇÖZÜLEN</th>
                            <th width="20%">İLERLEME</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>

            <div style="margin-top: 30px; text-align: center; color: #94a3b8; font-size: 10px;">
                Bu rapor YKS/LGS Homework Manager tarafından otomatik oluşturulmuştur.<br>
                Tarih: {QDate.currentDate().toString("dd.MM.yyyy")}
            </div>
            
        </body>
        </html>
        """
        return html

    # --- YENİ GELİŞMİŞ KOÇLUK VE PROGRAM METOTLARI ---
    
    # ------------------ 1. DERS PROGRAMI METOTLARI ------------------
    def _set_schedule_brush(self, text, bg, fg):
        if "Sil" in text:
            self._active_brush_data = ("", "#ffffff", "#000000")
            self.lbl_active_brush.setText("🖌️ Aktif Fırça: <b>🧹 Silme Modu</b>")
            self.lbl_active_brush.setStyleSheet("color: #dc2626; font-size: 11px; font-weight: 700; background: #fee2e2; padding: 3px 8px; border-radius: 4px;")
        else:
            self._active_brush_data = (text, bg, fg)
            self.lbl_active_brush.setText(f"🖌️ Aktif Fırça: <b>{text}</b>")
            self.lbl_active_brush.setStyleSheet(f"color: {fg}; font-size: 11px; font-weight: 700; background: {bg}; padding: 3px 8px; border-radius: 4px; border: 1px solid {fg}40;")

    def _on_schedule_cell_clicked(self, row, col):
        if col == 0:
            return  # Saat sütunu
        if hasattr(self, '_active_brush_data') and self._active_brush_data:
            text, bg, fg = self._active_brush_data
            item = self.table_schedule.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.table_schedule.setItem(row, col, item)
            item.setText(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if text else QFont.Weight.Normal))
            if text:
                item.setBackground(QColor(bg))
                item.setForeground(QColor(fg))
            else:
                item.setBackground(QColor("#ffffff"))
                item.setForeground(QColor("#334155"))
            self._recalc_schedule_hours()

    def _recalc_schedule_hours(self):
        if not hasattr(self, 'table_schedule'):
            return
        rows = self.table_schedule.rowCount()
        cols = self.table_schedule.columnCount()
        study_hours = 0
        school_hours = 0
        break_hours = 0

        for r in range(rows):
            for c in range(1, cols):
                item = self.table_schedule.item(r, c)
                if item:
                    txt = (item.text() or "").strip().lower()
                    if not txt:
                        continue
                    if "okul" in txt:
                        school_hours += 1
                    elif "mola" in txt or "dinlenme" in txt or "yemek" in txt:
                        break_hours += 1
                    else:
                        study_hours += 1

        total = study_hours + school_hours
        if hasattr(self, 'lbl_schedule_summary'):
            self.lbl_schedule_summary.setText(
                f"📊 Haftalık Net Kapasite: <b>{study_hours} Saat Bireysel Çalışma/Etüt</b> | {school_hours} Saat Okul | {total} Saat Toplam Program"
            )

    def _apply_schedule_template(self, index):
        if index <= 0:
            return

        choice = self.cmb_prog_templates.currentText()
        rows = self.table_schedule.rowCount()
        cols = self.table_schedule.columnCount()

        if "Temizle" in choice:
            for r in range(rows):
                for c in range(1, cols):
                    it = self.table_schedule.item(r, c)
                    if it:
                        it.setText("")
                        it.setBackground(QColor("#ffffff"))
            self._recalc_schedule_hours()
            self.cmb_prog_templates.setCurrentIndex(0)
            return

        def set_cell(r, c, txt, bg, fg):
            it = self.table_schedule.item(r, c)
            if not it:
                it = QTableWidgetItem()
                self.table_schedule.setItem(r, c, it)
            it.setText(txt)
            it.setBackground(QColor(bg))
            it.setForeground(QColor(fg))
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

        def find_hour_row(h_str):
            for r in range(rows):
                it = self.table_schedule.item(r, 0)
                if it and it.text().startswith(h_str):
                    return r
            return -1

        if "Okul + Akşam" in choice:
            for c in range(1, 6):
                for h in ["08", "09", "10", "11", "12", "13", "14", "15"]:
                    r = find_hour_row(h)
                    if r >= 0: set_cell(r, c, "🏫 Okul", "#f1f5f9", "#334155")
                r16 = find_hour_row("16"); r17 = find_hour_row("17")
                if r16 >= 0: set_cell(r16, c, "☕ Mola", "#ecfdf5", "#065f46")
                if r17 >= 0: set_cell(r17, c, "☕ Mola", "#ecfdf5", "#065f46")
                r18 = find_hour_row("18"); r19 = find_hour_row("19"); r20 = find_hour_row("20"); r21 = find_hour_row("21")
                if c in (1, 3):
                    if r18 >= 0: set_cell(r18, c, "📐 Matematik", "#dbeafe", "#1e40af")
                    if r19 >= 0: set_cell(r19, c, "📐 Matematik", "#dbeafe", "#1e40af")
                    if r20 >= 0: set_cell(r20, c, "⚡ Fizik", "#f3e8ff", "#6b21a8")
                    if r21 >= 0: set_cell(r21, c, "📖 Türkçe", "#ffe4e6", "#9f1239")
                elif c in (2, 4):
                    if r18 >= 0: set_cell(r18, c, "🧪 Kimya", "#fef3c7", "#92400e")
                    if r19 >= 0: set_cell(r19, c, "🧬 Biyoloji", "#dcfce7", "#166534")
                    if r20 >= 0: set_cell(r20, c, "📐 Matematik", "#dbeafe", "#1e40af")
                    if r21 >= 0: set_cell(r21, c, "📖 Türkçe", "#ffe4e6", "#9f1239")
                elif c == 5:
                    if r18 >= 0: set_cell(r18, c, "📝 Deneme", "#e0e7ff", "#3730a3")
                    if r19 >= 0: set_cell(r19, c, "📝 Deneme", "#e0e7ff", "#3730a3")
                    if r20 >= 0: set_cell(r20, c, "🏛️ Sosyal", "#ffedd5", "#9a3412")
                    if r21 >= 0: set_cell(r21, c, "☕ Mola", "#ecfdf5", "#065f46")
            for c in (6,):
                for h, sub, bg, fg in [
                    ("09", "📝 Deneme", "#e0e7ff", "#3730a3"),
                    ("10", "📝 Deneme", "#e0e7ff", "#3730a3"),
                    ("11", "📝 Deneme", "#e0e7ff", "#3730a3"),
                    ("12", "☕ Mola", "#ecfdf5", "#065f46"),
                    ("13", "📐 Matematik", "#dbeafe", "#1e40af"),
                    ("14", "⚡ Fizik", "#f3e8ff", "#6b21a8"),
                    ("15", "🧪 Kimya", "#fef3c7", "#92400e"),
                ]:
                    r = find_hour_row(h)
                    if r >= 0: set_cell(r, c, sub, bg, fg)

        elif "Mezun" in choice:
            for c in range(1, 7):
                schedule_map = [
                    ("09", "📐 Matematik", "#dbeafe", "#1e40af"),
                    ("10", "📐 Matematik", "#dbeafe", "#1e40af"),
                    ("11", "⚡ Fizik" if c % 2 == 1 else "🧪 Kimya", "#f3e8ff" if c % 2 == 1 else "#fef3c7", "#6b21a8" if c % 2 == 1 else "#92400e"),
                    ("12", "☕ Mola", "#ecfdf5", "#065f46"),
                    ("13", "🧬 Biyoloji" if c % 2 == 1 else "🏛️ Sosyal", "#dcfce7" if c % 2 == 1 else "#ffedd5", "#166534" if c % 2 == 1 else "#9a3412"),
                    ("14", "📖 Türkçe", "#ffe4e6", "#9f1239"),
                    ("15", "📝 Deneme" if c in (3, 6) else "📐 Matematik", "#e0e7ff" if c in (3, 6) else "#dbeafe", "#3730a3" if c in (3, 6) else "#1e40af"),
                    ("16", "☕ Mola", "#ecfdf5", "#065f46"),
                    ("17", "⚡ Fizik", "#f3e8ff", "#6b21a8"),
                    ("18", "☕ Mola", "#ecfdf5", "#065f46"),
                    ("19", "📐 Matematik", "#dbeafe", "#1e40af"),
                    ("20", "🧪 Kimya", "#fef3c7", "#92400e"),
                    ("21", "📖 Türkçe", "#ffe4e6", "#9f1239"),
                ]
                for h, sub, bg, fg in schedule_map:
                    r = find_hour_row(h)
                    if r >= 0: set_cell(r, c, sub, bg, fg)

        elif "LGS" in choice:
            for c in range(1, 6):
                for h in ["08", "09", "10", "11", "12", "13", "14"]:
                    r = find_hour_row(h)
                    if r >= 0: set_cell(r, c, "🏫 Okul", "#f1f5f9", "#334155")
                r16 = find_hour_row("16")
                if r16 >= 0: set_cell(r16, c, "☕ Mola", "#ecfdf5", "#065f46")
                r17 = find_hour_row("17")
                if r17 >= 0: set_cell(r17, c, "📖 Türkçe (Paragraf)", "#ffe4e6", "#9f1239")
                r18 = find_hour_row("18")
                if r18 >= 0: set_cell(r18, c, "📐 Matematik (Yeni Nesil)", "#dbeafe", "#1e40af")
                r19 = find_hour_row("19")
                if r19 >= 0: set_cell(r19, c, "☕ Mola", "#ecfdf5", "#065f46")
                r20 = find_hour_row("20")
                if r20 >= 0: set_cell(r20, c, "🧬 Fen Bilimleri", "#dcfce7", "#166534")

            for h, sub, bg, fg in [
                ("09", "📝 LGS Deneme Sınavı", "#e0e7ff", "#3730a3"),
                ("10", "📝 LGS Deneme Sınavı", "#e0e7ff", "#3730a3"),
                ("11", "☕ Mola", "#ecfdf5", "#065f46"),
                ("12", "📐 Matematik Soru Çözümü", "#dbeafe", "#1e40af"),
                ("13", "🧬 Fen Bilimleri Soru Çözümü", "#dcfce7", "#166534"),
            ]:
                r = find_hour_row(h)
                if r >= 0: set_cell(r, 6, sub, bg, fg)

        self._recalc_schedule_hours()
        self.cmb_prog_templates.setCurrentIndex(0)
        QMessageBox.information(self, "Şablon Uygulandı", f"'{choice}' şablonu haftalık çizelgeye yerleştirildi. Değişiklikleri kaydetmek için 'Programı Kaydet'e basabilirsiniz.")

    def _print_schedule_pdf(self):
        student_name = ""
        if self.current_student_id:
            con = db.get_conn()
            try:
                r = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (self.current_student_id,)).fetchone()
                if r: student_name = f"{r['ad']} {r['soyad']}".strip()
            finally:
                con.close()

        days = ["Saat", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        rows = self.table_schedule.rowCount()

        table_rows_html = ""
        for r in range(rows):
            saat = self.table_schedule.item(r, 0).text() if self.table_schedule.item(r, 0) else ""
            table_rows_html += f"<tr><td style='font-weight: bold; background: #f1f5f9; text-align: center; padding: 6px; border: 1px solid #cbd5e1;'>{saat}</td>"
            for c in range(1, 8):
                it = self.table_schedule.item(r, c)
                txt = it.text().strip() if it else ""
                bg = it.background().color().name() if (it and it.background().style() != Qt.BrushStyle.NoBrush) else "#ffffff"
                fg = it.foreground().color().name() if (it and it.foreground().style() != Qt.BrushStyle.NoBrush) else "#1e293b"
                table_rows_html += f"<td style='background: {bg}; color: {fg}; text-align: center; padding: 6px; font-weight: 600; border: 1px solid #cbd5e1; font-size: 11px;'>{txt}</td>"
            table_rows_html += "</tr>"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 15px; color: #1e293b; }}
                h2 {{ text-align: center; color: #1e3a8a; margin-bottom: 4px; }}
                .sub {{ text-align: center; color: #64748b; font-size: 12px; margin-bottom: 15px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background: #1e40af; color: white; padding: 8px; font-size: 12px; border: 1px solid #1e3a8a; }}
            </style>
        </head>
        <body>
            <h2>HAFTALIK ÇALIŞMA VE DERS PROGRAMI</h2>
            <div class="sub"><b>Öğrenci:</b> {student_name} | <b>Oluşturulma:</b> {QDate.currentDate().toString('dd.MM.yyyy')}</div>
            <table>
                <thead>
                    <tr>
                        {"".join(f"<th>{d}</th>" for d in days)}
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>
            <div style="margin-top: 15px; font-size: 10px; color: #94a3b8; text-align: right;">
                YKS/LGS Homework Manager Eğitim Koçluğu Modülü
            </div>
        </body>
        </html>
        """

        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

        doc = QTextDocument()
        doc.setHtml(html)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        p_dlg = QPrintDialog(printer, self)
        if p_dlg.exec() == QPrintDialog.DialogCode.Accepted:
            doc.print(printer)
            QMessageBox.information(self, "Yazdırıldı", "Ders programı başarıyla yazıcıya / PDF'e gönderildi.")

    def _save_schedule(self):
        if not self.current_plan_id:
            reply = QMessageBox.question(self, "Plan Oluştur", 
                "Bu hafta için henüz bir plan oluşturulmamış. Otomatik oluşturulsun mu?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self._auto_create_plan()
            else:
                return

        if not self.current_plan_id: return

        con = db.get_conn()
        try:
            con.execute("DELETE FROM koc_program WHERE plan_id=?", (self.current_plan_id,))
            
            rows = self.table_schedule.rowCount()
            cols = self.table_schedule.columnCount()
            days_map = {1:"Pazartesi", 2:"Salı", 3:"Çarşamba", 4:"Perşembe", 5:"Cuma", 6:"Cumartesi", 7:"Pazar"}
            
            for r in range(rows):
                saat_item = self.table_schedule.item(r, 0)
                if not saat_item:
                    continue
                saat = saat_item.text()
                for c in range(1, cols):
                    item = self.table_schedule.item(r, c)
                    if item:
                        txt = item.text().strip()
                        bg = item.background().color().name() if item.background().style() != Qt.BrushStyle.NoBrush else ""
                        is_colored = bg and bg.lower() not in ["#ffffff", "#000000", "white", "black"]
                        if txt or is_colored:
                            gun = days_map[c]
                            con.execute("INSERT INTO koc_program (plan_id, gun, saat, icerik, renk) VALUES (?,?,?,?,?)",
                                (self.current_plan_id, gun, saat, txt, bg))
            
            con.commit()
            self._recalc_schedule_hours()
            QMessageBox.information(self, "Kaydedildi", "Haftalık ders programı başarıyla kaydedildi! 💾")
        finally:
            con.close()

    def _auto_create_plan(self):
        start_date = self._get_week_start()
        end_date = start_date.addDays(6)
        
        con = db.get_conn()
        try:
            cur = con.execute("""
                INSERT INTO koc_plan (ogrenci_id, baslangic_tarihi, bitis_tarihi)
                VALUES (?, ?, ?)
            """, (self.current_student_id, start_date.toString("yyyy-MM-dd"), end_date.toString("yyyy-MM-dd")))
            self.current_plan_id = cur.lastrowid
            con.commit()
            self._load_plan()
        finally:
            con.close()

    def _load_schedule_data(self, con):
        rows_count = self.table_schedule.rowCount()
        cols_count = self.table_schedule.columnCount()
        for r in range(rows_count):
            for c in range(1, cols_count):
                self.table_schedule.setItem(r, c, QTableWidgetItem(""))

        rows = con.execute("SELECT * FROM koc_program WHERE plan_id=?", (self.current_plan_id,)).fetchall()
        days_map_rev = {"Pazartesi":1, "Salı":2, "Çarşamba":3, "Perşembe":4, "Cuma":5, "Cumartesi":6, "Pazar":7}
        
        for r in rows:
            dict_r = dict(r)
            gun = dict_r["gun"]
            saat = dict_r["saat"]
            icerik = dict_r["icerik"]
            
            row_idx = -1
            for i in range(self.table_schedule.rowCount()):
                if self.table_schedule.item(i, 0).text() == saat:
                    row_idx = i
                    break
            
            col_idx = days_map_rev.get(gun, -1)
            
            if row_idx >= 0 and col_idx > 0:
                item = QTableWidgetItem(icerik)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                renk = dict_r.get("renk")
                if renk:
                    item.setBackground(QColor(renk))
                self.table_schedule.setItem(row_idx, col_idx, item)

        self._recalc_schedule_hours()

    # ------------------ 2. GELİŞİM ANALİZİ METOTLARI ------------------
    def _update_analysis_chart(self, con):
        if not self.current_student_id:
            return

        # 1. Fetch all weekly plans for this student
        plans = con.execute("""
            SELECT p.id, p.baslangic_tarihi, p.bitis_tarihi,
                   COALESCE(SUM(h.hedef_soru), 0) as tot_target,
                   COALESCE(SUM(h.cozulen_soru), 0) as tot_solved
            FROM koc_plan p
            LEFT JOIN koc_hedef h ON h.plan_id = p.id
            WHERE p.ogrenci_id = ?
            GROUP BY p.id
            ORDER BY p.baslangic_tarihi ASC
        """, (self.current_student_id,)).fetchall()

        # 2. Fetch subject-wise aggregated totals
        subject_stats = con.execute("""
            SELECT h.ders_adi,
                   SUM(h.hedef_soru) as s_target,
                   SUM(h.cozulen_soru) as s_solved
            FROM koc_plan p
            JOIN koc_hedef h ON h.plan_id = p.id
            WHERE p.ogrenci_id = ?
            GROUP BY h.ders_adi
            ORDER BY s_solved DESC
        """, (self.current_student_id,)).fetchall()

        total_target = sum(p["tot_target"] for p in plans)
        total_solved = sum(p["tot_solved"] for p in plans)
        overall_rate = int(round(100 * total_solved / total_target)) if total_target > 0 else 0
        avg_vol = int(round(total_solved / max(1, len(plans)))) if plans else 0

        # KPI Updates
        if hasattr(self, 'lbl_ana_rate'):
            self.lbl_ana_rate.setText(f"%{overall_rate}")
        if hasattr(self, 'lbl_ana_avg'):
            self.lbl_ana_avg.setText(f"{avg_vol} Soru / Hf")

        top_subject = "—"
        low_subject = "—"
        low_pct = 100

        if subject_stats:
            top_subject = subject_stats[0]["ders_adi"]
            for s in subject_stats:
                st = s["s_target"] or 0
                ss = s["s_solved"] or 0
                pct = int(round(100 * ss / st)) if st > 0 else 0
                if st >= 50 and pct < low_pct:
                    low_pct = pct
                    low_subject = s["ders_adi"]
            if low_subject == "—" and len(subject_stats) > 1:
                low_subject = subject_stats[-1]["ders_adi"]

        if hasattr(self, 'lbl_ana_top'):
            self.lbl_ana_top.setText(top_subject[:16])
        if hasattr(self, 'lbl_ana_low'):
            self.lbl_ana_low.setText(low_subject[:16])

        # 3. Table: tbl_subject_stats
        if hasattr(self, 'tbl_subject_stats'):
            self.tbl_subject_stats.setRowCount(len(subject_stats))
            for row_idx, s in enumerate(subject_stats):
                st = s["s_target"] or 0
                ss = s["s_solved"] or 0
                pct = int(round(100 * ss / st)) if st > 0 else 0

                it_d = QTableWidgetItem(s["ders_adi"])
                it_d.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.tbl_subject_stats.setItem(row_idx, 0, it_d)

                it_t = QTableWidgetItem(f"{st:,}".replace(",", "."))
                it_t.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_subject_stats.setItem(row_idx, 1, it_t)

                it_s = QTableWidgetItem(f"{ss:,}".replace(",", "."))
                it_s.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_subject_stats.setItem(row_idx, 2, it_s)

                it_p = QTableWidgetItem(f"%{pct}")
                it_p.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                if pct >= 80:
                    it_p.setForeground(QColor("#15803d"))
                    it_p.setBackground(QColor("#f0fdf4"))
                elif pct >= 50:
                    it_p.setForeground(QColor("#b45309"))
                    it_p.setBackground(QColor("#fefce8"))
                else:
                    it_p.setForeground(QColor("#b91c1c"))
                    it_p.setBackground(QColor("#fef2f2"))
                self.tbl_subject_stats.setItem(row_idx, 3, it_p)

                status_str = "⭐ Mükemmel" if pct >= 85 else ("👍 Yeterli" if pct >= 65 else ("⚠️ Takviye Gerekli" if pct >= 35 else "⏳ Kritik"))
                it_stat = QTableWidgetItem(status_str)
                it_stat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_subject_stats.setItem(row_idx, 4, it_stat)

        # 4. Diagnostic Comment
        if hasattr(self, 'lbl_ana_diagnostic'):
            if not plans:
                diag = "Öğrenci için henüz kaydedilmiş haftalık koçluk verisi bulunmuyor. Yeni bir plan oluşturarak süreci başlatabilirsiniz."
            else:
                diag = (
                    f"Öğrencinin kayıtlı {len(plans)} haftalık koçluk süreci incelendiğinde; genel hedef tamamlama oranı %{overall_rate} seviyesindedir. "
                    f"Haftalık ortalama soru çözüm hacmi {avg_vol} soru olarak gerçekleşmiştir. "
                    f"En yüksek efor ve süreklilik <b>{top_subject}</b> dersinde sağlanmıştır. "
                )
                if low_subject != "—":
                    diag += f"Buna karşılık <b>{low_subject}</b> dersinde hedeflerin gerisinde kalınmış olup önümüzdeki haftalık planda soru hedefinin dengelenmesi önerilir."
            self.lbl_ana_diagnostic.setText(diag)

        # 5. Matplotlib Dual Charts
        if hasattr(self, 'figure') and hasattr(self, 'canvas'):
            self.figure.clear()
            ax1 = self.figure.add_subplot(121)
            ax2 = self.figure.add_subplot(122)

            # Chart 1: Haftalık Trend
            recent_plans = plans[-8:] if len(plans) > 8 else plans
            if recent_plans:
                x_labels = [p["baslangic_tarihi"][5:] for p in recent_plans]
                t_vals = [p["tot_target"] for p in recent_plans]
                s_vals = [p["tot_solved"] for p in recent_plans]
                
                import numpy as np
                x = np.arange(len(x_labels))
                width = 0.35

                ax1.bar(x - width/2, t_vals, width, label='Hedef', color='#cbd5e1', edgecolor='#94a3b8', alpha=0.9)
                bars_s = ax1.bar(x + width/2, s_vals, width, label='Çözülen', color='#2563eb', edgecolor='#1d4ed8')
                
                for bar in bars_s:
                    h = bar.get_height()
                    if h > 0:
                        ax1.annotate(f"{int(h)}", xy=(bar.get_x() + bar.get_width() / 2, h),
                                     xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')

                ax1.set_xticks(x)
                ax1.set_xticklabels(x_labels, fontsize=9)
                ax1.set_title("Haftalık Soru Hacmi (Hedef vs Çözülen)", fontsize=10, fontweight='bold', pad=8)
                ax1.legend(loc='upper left', fontsize=8)
                ax1.grid(axis='y', linestyle='--', alpha=0.3)
                ax1.spines['top'].set_visible(False)
                ax1.spines['right'].set_visible(False)
            else:
                ax1.text(0.5, 0.5, "Haftalık plan verisi yok", ha='center', va='center', color='#94a3b8')
                ax1.axis('off')

            # Chart 2: Ders Dağılımı Donut Chart
            if subject_stats:
                top_subs = subject_stats[:5]
                labels = [s["ders_adi"] for s in top_subs]
                vals = [s["s_solved"] for s in top_subs]
                
                other_val = sum(s["s_solved"] for s in subject_stats[5:])
                if other_val > 0:
                    labels.append("Diğer")
                    vals.append(other_val)

                if sum(vals) > 0:
                    colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b']
                    wedges, _, autotexts = ax2.pie(
                        vals,
                        labels=labels,
                        autopct='%1.0f%%',
                        pctdistance=0.75,
                        startangle=140,
                        colors=colors[:len(vals)],
                        wedgeprops=dict(width=0.42, edgecolor='white', linewidth=2),
                        textprops=dict(fontsize=8)
                    )
                    for at in autotexts:
                        at.set_color('white')
                        at.set_weight('bold')
                        at.set_fontsize(8)
                    ax2.set_title("Çözülen Soru Ders Dağılımı", fontsize=10, fontweight='bold', pad=8)
                else:
                    ax2.text(0.5, 0.5, "Çözülen soru sayısı henüz 0", ha='center', va='center', color='#94a3b8')
                    ax2.axis('off')
            else:
                ax2.text(0.5, 0.5, "Ders istatistiği bulunamadı", ha='center', va='center', color='#94a3b8')
                ax2.axis('off')

            self.figure.tight_layout()
            self.canvas.draw()

    # ------------------ 3. GÖRÜŞME NOTLARI METOTLARI ------------------
    def _tpl_routine(self):
        self.txt_note_agenda.setPlainText(
            "• Geçen haftanın ödevleri ve çözülen soru hedefleri kontrol edildi.\n"
            "• Yapılamayan ve boş bırakılan sorular incelendi, konu eksikleri tespit edildi.\n"
            "• Günlük rutin soru çözümü (Paragraf & Problem) sürekliliği değerlendirildi."
        )
        self.txt_note_actions.setPlainText(
            "1. Her sabah kahvaltıdan önce 25 paragraf sorusu süre tutularak çözülecek.\n"
            "2. Matematik branş denemesi haftada 2 güne çıkarılacak (Çarşamba & Cumartesi).\n"
            "3. Yanlış yapılan sorular kesilerek soru defterine yapıştırılacak."
        )
        self.txt_note_parent.setPlainText(
            "Öğrencimiz bu hafta hedeflerini büyük oranda yakalamıştır. Özellikle çalışma disiplininde istikrar gözleniyor. "
            "Önümüzdeki hafta eksik konulara yönelik branş denemelerine ağırlık vereceğiz."
        )
        self._compose_notes_text()

    def _tpl_deneme(self):
        self.txt_note_agenda.setPlainText(
            "• Son yapılan genel/kurumsal deneme sınavının net karnesi değerlendirildi.\n"
            "• Türkçe'de zaman yönetimi, Matematik'te işlem hatası yapılan sorular analiz edildi.\n"
            "• Fen / Sosyal bölümündeki bilgi eksikleri belirlendi."
        )
        self.txt_note_actions.setPlainText(
            "1. Deneme sınavı süresi için turlama tekniği zorunlu uygulanacak.\n"
            "2. Yanlış çıkan 2 kritik konu için video konu tekrarı + 100'er soru çözülecek.\n"
            "3. Optik form kodlama ve odaklanma egzersizleri yapılacak."
        )
        self.txt_note_parent.setPlainText(
            "Yapılan deneme sınavı analizi neticesinde öğrencimizin güçlü olduğu alanlar pekişmiş, "
            "zamanlama hataları için özel strateji belirlenmiştir. Genel net ortalamasında olumlu bir yükseliş trendi mevcuttur."
        )
        self._compose_notes_text()

    def _tpl_anxiety(self):
        self.txt_note_agenda.setPlainText(
            "• Öğrencinin sınav ve net kaygısı, stres seviyesi ve uyku düzeni ele alındı.\n"
            "• Deneme anında yaşanan panik ve dikkatsizlik durumları konuşuldu.\n"
            "• Özgüven ve motivasyon odaklı birebir koçluk görüşmesi gerçekleştirildi."
        )
        self.txt_note_actions.setPlainText(
            "1. Deneme sınavlarına 'sıralama' değil 'eksik tespit aracı' gözüyle bakılacak.\n"
            "2. Sınav öncesi nefes ve odaklanma egzersizleri uygulanacak.\n"
            "3. Uyku saati en geç 23:30 olarak sabitlenecek."
        )
        self.txt_note_parent.setPlainText(
            "Öğrencimizle sınav kaygısını azaltma ve zihinsel dayanıklılığı artırma üzerine verimli bir koçluk görüşmesi yaptık. "
            "Ev ortamında net odaklı baskıdan kaçınılması ve öğrencinin çabasının takdir edilmesi sürece büyük katkı sağlayacaktır."
        )
        self._compose_notes_text()

    def _tpl_time_mgmt(self):
        self.txt_note_agenda.setPlainText(
            "• Günlük telefon/ekran süresi ve masa başında geçirilen net çalışma saati hesaplandı.\n"
            "• Pomodoro ve blok çalışma tekniklerinin etkinliği değerlendirildi.\n"
            "• Gün içi ölü zamanların soru çözümüne kazandırılması tartışıldı."
        )
        self.txt_note_actions.setPlainText(
            "1. 50 dk ders + 10 dk mola şeklinde blok çalışma sistemine geçilecek.\n"
            "2. Ders esnasında telefon farklı bir odada sessiz konumda tutulacak.\n"
            "3. Günlük çalışma saati hedefi minimum 4.5 saat olarak takip edilecek."
        )
        self.txt_note_parent.setPlainText(
            "Haftalık zaman yönetimi planımız revize edilmiştir. Masa başı odaklanma süresini artırmak amacıyla yeni çalışma blokları oluşturulmuştur."
        )
        self._compose_notes_text()

    def _generate_auto_comment(self):
        student_name = ""
        if self.current_student_id:
            con = db.get_conn()
            try:
                r = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (self.current_student_id,)).fetchone()
                if r: student_name = f"{r['ad']} {r['soyad']}".strip()
            finally:
                con.close()

        raw_rate = self.lbl_completion_rate.text().replace("%", "").strip()
        try: rate = int(raw_rate)
        except: rate = 0
        solved = self.lbl_total_solved.text()
        target = self.lbl_total_target.text()

        agenda = f"• {student_name} ile haftalık periyodik koçluk görüşmesi gerçekleştirildi.\n"
        agenda += f"• Bu haftaki toplam hedef: {target} soru, çözülen: {solved} soru (%{rate} tamamlama oranı).\n"

        if rate >= 85:
            agenda += "• Öğrenci hedeflerine tam sadakat gösterdi, çalışma temposu ve motivasyonu üst düzeyde."
            actions = "1. Mevcut yüksek disiplin korunacak, zorluk derecesi yüksek yeni nesil sorulara geçilecek.\n2. Haftalık branş denemesi sıklığı artırılacak."
            parent = f"Değerli Velimiz, öğrencimiz {student_name} bu hafta belirlediğimiz hedeflerin %{rate}'ini başarıyla tamamlayarak ({solved} soru) mükemmel bir gayret göstermiştir. Bu disiplinin devamını diliyoruz."
        elif rate >= 60:
            agenda += "• Öğrenci hedeflerin önemli bir kısmını tamamladı, ancak belirli derslerde aksamalar görüldü."
            actions = "1. Eksik kalan branşlardan günlük ekstra 30 soru telafi programı uygulanacak.\n2. Hafta ortası kısa ara kontrol yapılacak."
            parent = f"Değerli Velimiz, öğrencimiz {student_name} bu hafta %{rate} başarı oranıyla {solved} soru tamamlamıştır. Önümüzdeki hafta eksikleri kapatmak üzere çalışma planını yoğunlaştırdık."
        else:
            agenda += "• Bu hafta hedeflerin gerisinde kalındı. Süreçteki motivasyon kaybı veya zamanlama problemleri masaya yatırıldı."
            actions = "1. Günlük soru hedefleri daha erişilebilir seviyeye çekilip kademeli artırılacak.\n2. Akşam çalışma takibi sıklaştırılacak."
            parent = f"Değerli Velimiz, öğrencimiz {student_name} ile yaptığımız haftalık görüşmede hedeflerin gerisinde kaldığımızı tespit ettik (%{rate}). Önümüzdeki hafta çalışma temposunu yeniden yükseltmek için özel bir takip planı devreye aldık."

        self.txt_note_agenda.setPlainText(agenda)
        self.txt_note_actions.setPlainText(actions)
        self.txt_note_parent.setPlainText(parent)
        self._compose_notes_text()
        QMessageBox.information(self, "Yorum Üretildi", "Akıllı koçluk analizi ve değerlendirme metinleri alanlara başarıyla dolduruldu! ✨")

    def _compose_notes_text(self):
        dt = self.date_notes.date().toString("dd.MM.yyyy") if hasattr(self, 'date_notes') else ""
        m_type = self.cmb_notes_type.currentText() if hasattr(self, 'cmb_notes_type') else ""
        mood = self.cmb_notes_mood.currentText() if hasattr(self, 'cmb_notes_mood') else ""
        ag = self.txt_note_agenda.toPlainText().strip() if hasattr(self, 'txt_note_agenda') else ""
        ac = self.txt_note_actions.toPlainText().strip() if hasattr(self, 'txt_note_actions') else ""
        pn = self.txt_note_parent.toPlainText().strip() if hasattr(self, 'txt_note_parent') else ""

        full = f"📅 GÖRÜŞME BİLGİLERİ: {dt} | Tür: {m_type} | Ruh Hali: {mood}\n\n"
        if ag:
            full += f"🎯 GÜNDEM VE DEĞERLENDİRME:\n{ag}\n\n"
        if ac:
            full += f"🚀 YENİ KARARLAR VE AKSİYONLAR:\n{ac}\n\n"
        if pn:
            full += f"👨‍👩‍👦 VELİ BİLGİLENDİRME NOTU:\n{pn}\n"

        if hasattr(self, 'txt_notes'):
            self.txt_notes.setPlainText(full)
        return full

    def _populate_notes_fields(self, raw_notlar: str):
        if not hasattr(self, 'txt_notes'): return
        import json
        if not raw_notlar:
            if hasattr(self, 'txt_note_agenda'): self.txt_note_agenda.clear()
            if hasattr(self, 'txt_note_actions'): self.txt_note_actions.clear()
            if hasattr(self, 'txt_note_parent'): self.txt_note_parent.clear()
            self.txt_notes.clear()
            return

        try:
            d = json.loads(raw_notlar)
            if isinstance(d, dict):
                if hasattr(self, 'date_notes') and d.get("date"):
                    qd = QDate.fromString(d["date"], "yyyy-MM-dd")
                    if qd.isValid(): self.date_notes.setDate(qd)
                if hasattr(self, 'cmb_notes_type') and d.get("type"):
                    idx = self.cmb_notes_type.findText(d["type"])
                    if idx >= 0: self.cmb_notes_type.setCurrentIndex(idx)
                if hasattr(self, 'cmb_notes_mood') and d.get("mood"):
                    idx = self.cmb_notes_mood.findText(d["mood"])
                    if idx >= 0: self.cmb_notes_mood.setCurrentIndex(idx)
                if hasattr(self, 'txt_note_agenda'):
                    self.txt_note_agenda.setPlainText(d.get("agenda", ""))
                if hasattr(self, 'txt_note_actions'):
                    self.txt_note_actions.setPlainText(d.get("actions", ""))
                if hasattr(self, 'txt_note_parent'):
                    self.txt_note_parent.setPlainText(d.get("parent", ""))
                if hasattr(self, 'txt_notes'):
                    self.txt_notes.setPlainText(d.get("composed", "") or raw_notlar)
                return
        except Exception:
            pass

        # Fallback for plain text note
        if hasattr(self, 'txt_note_agenda'): self.txt_note_agenda.setPlainText(raw_notlar)
        if hasattr(self, 'txt_notes'): self.txt_notes.setPlainText(raw_notlar)

    def _save_notes(self):
        if not self.current_plan_id:
            QMessageBox.warning(self, "Uyarı", "Not kaydetmek için önce mevcut bir hafta planı seçili olmalıdır.")
            return

        import json
        note_data = {
            "date": self.date_notes.date().toString("yyyy-MM-dd") if hasattr(self, 'date_notes') else "",
            "type": self.cmb_notes_type.currentText() if hasattr(self, 'cmb_notes_type') else "",
            "mood": self.cmb_notes_mood.currentText() if hasattr(self, 'cmb_notes_mood') else "",
            "agenda": self.txt_note_agenda.toPlainText().strip() if hasattr(self, 'txt_note_agenda') else "",
            "actions": self.txt_note_actions.toPlainText().strip() if hasattr(self, 'txt_note_actions') else "",
            "parent": self.txt_note_parent.toPlainText().strip() if hasattr(self, 'txt_note_parent') else "",
            "composed": self._compose_notes_text()
        }
        json_str = json.dumps(note_data, ensure_ascii=False)

        con = db.get_conn()
        try:
            con.execute("UPDATE koc_plan SET notlar=? WHERE id=?", (json_str, self.current_plan_id))
            con.commit()
            self._load_past_notes_list(con)
            QMessageBox.information(self, "Kaydedildi", "Haftalık koçluk görüşme notları ve aksiyon maddeleri başarıyla kaydedildi! 💾")
        finally:
            con.close()

    def _send_notes_whatsapp(self):
        parent_text = self.txt_note_parent.toPlainText().strip() if hasattr(self, 'txt_note_parent') else ""
        if not parent_text:
            parent_text = self.txt_notes.toPlainText().strip() if hasattr(self, 'txt_notes') else ""

        if not parent_text:
            QMessageBox.warning(self, "Uyarı", "Gönderilecek bir veli bilgilendirme notu bulunmuyor.")
            return

        student_name = ""
        parent_phone = ""
        if self.current_student_id:
            con = db.get_conn()
            try:
                r = con.execute("SELECT ad, soyad, veli_tel1, veli_tel2, ogr_tel FROM ogrenci WHERE id=?", (self.current_student_id,)).fetchone()
                if r:
                    student_name = f"{r['ad']} {r['soyad']}".strip()
                    parent_phone = (r["veli_tel1"] or r["veli_tel2"] or r["ogr_tel"] or "").strip()
            finally:
                con.close()

        wa_msg = f"*EĞİTİM KOÇLUĞU HAFTALIK BİLGİLENDİRME*\n"
        wa_msg += f"👤 *Öğrenci:* {student_name}\n"
        wa_msg += f"📅 *Tarih:* {QDate.currentDate().toString('dd.MM.yyyy')}\n\n"
        wa_msg += f"{parent_text}\n\n"
        wa_msg += f"_YKS/LGS Homework Manager Koçluk Sistemi_"

        QApplication.clipboard().setText(wa_msg)
        if parent_phone:
            import urllib.parse
            import webbrowser
            clean_phone = "".join(filter(str.isdigit, parent_phone))
            if clean_phone.startswith("0"): clean_phone = "90" + clean_phone[1:]
            elif not clean_phone.startswith("90") and len(clean_phone) == 10: clean_phone = "90" + clean_phone
            
            url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(wa_msg)}"
            webbrowser.open(url)
            QMessageBox.information(self, "WhatsApp Hazır", f"Mesaj panoya kopyalandı ve {student_name} velisi için WhatsApp Web açıldı!")
        else:
            QMessageBox.information(self, "Kopyalandı", "Kayıtlı veli telefonu bulunamadı, ancak mesaj panoya kopyalandı! WhatsApp'a yapıştırıp gönderebilirsiniz.")

    def _reset_notes_to_current_week(self):
        if hasattr(self, 'dt_week'):
            self.dt_week.setDate(QDate.currentDate())
        else:
            self._load_plan()
        if hasattr(self, 'txt_note_agenda'): self.txt_note_agenda.setFocus()

    def _load_past_notes_list(self, con):
        if not hasattr(self, 'list_past_notes') or not self.current_student_id:
            return
        self.list_past_notes.clear()
        rows = con.execute("""
            SELECT id, baslangic_tarihi, bitis_tarihi, notlar
            FROM koc_plan
            WHERE ogrenci_id=?
            ORDER BY baslangic_tarihi DESC
        """, (self.current_student_id,)).fetchall()

        import json
        for r in rows:
            b_tar = r["baslangic_tarihi"] or ""
            raw_not = r["notlar"] or ""
            
            preview = "Not girilmedi"
            m_type = "Görüşme"
            if raw_not:
                try:
                    d = json.loads(raw_not)
                    m_type = d.get("type", "Görüşme")
                    preview = (d.get("agenda", "") or d.get("composed", "") or "Görüşme kaydı").replace("\n", " ")[:38]
                except:
                    preview = raw_not.replace("\n", " ")[:38]

            it = QListWidgetItem(f"📅 {b_tar} ({m_type})\n   └ {preview}...")
            it.setData(Qt.ItemDataRole.UserRole, r["id"])
            if r["id"] == self.current_plan_id:
                it.setBackground(QColor("#eff6ff"))
                it.setForeground(QColor("#1d4ed8"))
            self.list_past_notes.addItem(it)

    def _on_past_note_selected(self, item):
        plan_id = item.data(Qt.ItemDataRole.UserRole)
        if not plan_id:
            return
        con = db.get_conn()
        try:
            r = con.execute("SELECT id, baslangic_tarihi, notlar FROM koc_plan WHERE id=?", (plan_id,)).fetchone()
            if r:
                b_date = QDate.fromString(r["baslangic_tarihi"], "yyyy-MM-dd")
                if b_date.isValid():
                    if hasattr(self, 'dt_week'):
                        self.dt_week.setDate(b_date)
                    else:
                        self._load_plan()
        finally:
            con.close()


    def _on_book_changed(self, text=None):
        cur_id = self.cmb_topic_book.currentData() if hasattr(self, 'cmb_topic_book') else 0
        if hasattr(self, 'btn_del_book'):
            self.btn_del_book.setEnabled(bool(cur_id and cur_id > 0))
        self._load_topics()

    def _add_new_book(self):
        if not self.current_student_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce sol listeden bir öğrenci seçin.")
            return
        subject = self.cmb_topic_subject.currentText()
        if not subject:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir ders seçin.")
            return
            
        name, ok = QInputDialog.getText(
            self, 
            "Yeni Kaynak/Kitap Ekle", 
            f"<b>{subject}</b> için öğrencinin çözdüğü kitap/kaynak adı:\n(Örn: 345 TYT Matematik, Bilgi Sarmal, Apotemi vb.)"
        )
        if ok and name and name.strip():
            b_name = name.strip()
            con = db.get_conn()
            try:
                con.execute("INSERT INTO koc_kitaplar (ogrenci_id, ders_adi, kitap_adi) VALUES (?,?,?)", 
                          (self.current_student_id, subject, b_name))
                con.commit()
                self._target_book_to_select = b_name
                self._load_topics()
                QMessageBox.information(
                    self, 
                    "Kitap Başarıyla Eklendi", 
                    f"<b>'{b_name}'</b> kitabı başarıyla eklendi ve seçildi.\n\n"
                    f"Artık bu kitaba ait konu ilerlemelerini ayrı bir kaynak olarak takip edebilirsiniz."
                )
            finally:
                con.close()

    def _delete_current_book(self):
        if not self.current_student_id: return
        cur_id = self.cmb_topic_book.currentData()
        book_name = self.cmb_topic_book.currentText()
        if not cur_id or cur_id <= 0:
            return
            
        ans = QMessageBox.question(
            self,
            "Kitabı Sil",
            f"<b>'{book_name}'</b> kitabını ve bu kitaba ait tüm ilerleme kayıtlarını silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            con = db.get_conn()
            try:
                con.execute("DELETE FROM koc_kitaplar WHERE id=? AND ogrenci_id=?", (cur_id, self.current_student_id))
                con.execute("DELETE FROM koc_konu_takip WHERE kitap_id=? AND ogrenci_id=?", (cur_id, self.current_student_id))
                con.commit()
                self._target_book_to_select = "Genel Takip (Özet)"
                self._load_topics()
            finally:
                con.close()

    def _load_topics(self):
        if not self.current_student_id: return
        
        subject = self.cmb_topic_subject.currentText()
        if not subject: return
        
        curr_book = self.cmb_topic_book.currentText()
        
        con = db.get_conn()
        try:
            # 1. Kaynak/Kitapları Yükle
            bk_rows = con.execute("SELECT id, kitap_adi FROM koc_kitaplar WHERE ogrenci_id=? AND ders_adi=?", 
                                (self.current_student_id, subject)).fetchall()
            
            self.cmb_topic_book.blockSignals(True)
            self.cmb_topic_book.clear()
            self.cmb_topic_book.addItem("Genel Takip (Özet)", 0)
            
            target_sel = getattr(self, '_target_book_to_select', None)
            if target_sel:
                curr_book = target_sel
                self._target_book_to_select = None
            
            selected_book_id = 0
            for b_id, b_name in bk_rows:
                self.cmb_topic_book.addItem(b_name, b_id)
                if b_name == curr_book:
                    self.cmb_topic_book.setCurrentText(b_name)
                    selected_book_id = b_id
            
            if curr_book == "Genel Takip (Özet)":
                self.cmb_topic_book.setCurrentIndex(0)
                selected_book_id = 0
                
            cur_idx = self.cmb_topic_book.currentIndex()
            if cur_idx > -1:
                selected_book_id = self.cmb_topic_book.itemData(cur_idx) or 0
            
            if hasattr(self, 'btn_del_book'):
                self.btn_del_book.setEnabled(bool(selected_book_id and selected_book_id > 0))
            
            self.cmb_topic_book.blockSignals(False)
            
            # 2. Tüm Konuları ve Veritabanı Kayıtlarını Çek
            all_topics = TOPIC_LIST.get(subject, [])
            
            sql = """
                SELECT id, konu_adi, durum, hakimiyet_puani, cozulen_soru, hedef_soru, 
                       tekrar_durumu, son_tekrar_tarihi, koc_notu, updated_at 
                FROM koc_konu_takip 
                WHERE ogrenci_id=? AND ders_adi=? AND kitap_id=?
            """
            rows = con.execute(sql, (self.current_student_id, subject, selected_book_id)).fetchall()
            record_map = {r["konu_adi"]: dict(r) for r in rows}
            
            # 3. KPI İstatistiklerini Hesapla (Tüm Konular Üzerinden)
            total_topics = len(all_topics)
            mastered_count = 0
            review_count = 0
            critical_total = 0
            critical_mastered = 0
            total_mastery_sum = 0
            
            score_defaults = {0: 0, 1: 30, 2: 60, 3: 80, 4: 100, 5: 20}
            
            for topic in all_topics:
                rec = record_map.get(topic, {})
                durum = rec.get("durum", 0)
                score = rec.get("hakimiyet_puani") or score_defaults.get(durum, 0)
                total_mastery_sum += score
                
                if durum == 4:
                    mastered_count += 1
                tekrar = str(rec.get("tekrar_durumu", "")).lower()
                if durum == 3 or "tekrar" in tekrar:
                    review_count += 1
                    
                c_data = CURRICULUM_DATA.get("topics", {}).get(topic, {})
                imp = str(c_data.get("importance", "")).lower()
                if "yüksek" in imp or "5/5" in imp or "4/5" in imp:
                    critical_total += 1
                    if durum == 4:
                        critical_mastered += 1
                        
            avg_mastery = int(total_mastery_sum / total_topics) if total_topics > 0 else 0
            
            # KPI Kartlarını Güncelle
            if hasattr(self, 'lbl_topic_kpi_progress'):
                self.lbl_topic_kpi_progress.setText(f"%{avg_mastery}")
                self.pbar_topic_mastery.setValue(avg_mastery)
                self.lbl_topic_kpi_mastered.setText(f"{mastered_count} / {total_topics} Konu")
                self.lbl_topic_kpi_review.setText(f"{review_count} Konu")
                self.lbl_topic_kpi_critical.setText(f"{critical_mastered} / {critical_total} Hazır")
            
            # 4. Arama ve Filtreleme
            search_q = self.txt_topic_search.text().lower().strip() if hasattr(self, 'txt_topic_search') else ""
            filter_mode = self.cmb_topic_filter.currentText() if hasattr(self, 'cmb_topic_filter') else "Tüm Konular"
            
            filtered_topics = []
            for topic in all_topics:
                if search_q and search_q not in topic.lower():
                    continue
                rec = record_map.get(topic, {})
                durum = rec.get("durum", 0)
                c_data = CURRICULUM_DATA.get("topics", {}).get(topic, {})
                imp = str(c_data.get("importance", "")).lower()
                tekrar = str(rec.get("tekrar_durumu", "")).lower()
                
                if filter_mode == "Sadece Eksikler" and durum == 4:
                    continue
                elif filter_mode == "Çalışılıyor / Pekiştirme" and durum not in (1, 2, 3):
                    continue
                elif filter_mode == "Tam Hakimiyet (Bitenler)" and durum != 4:
                    continue
                elif filter_mode == "Tekrar Bekleyenler" and durum != 3 and "tekrar" not in tekrar:
                    continue
                elif filter_mode == "🔥 Kritik Sınav Konuları" and not ("yüksek" in imp or "5/5" in imp or "4/5" in imp):
                    continue
                filtered_topics.append(topic)
                
            # 5. Tabloyu Doldur
            self.table_topics.setRowCount(len(filtered_topics))
            
            for i, topic in enumerate(filtered_topics):
                rec = record_map.get(topic, {})
                durum = rec.get("durum", 0)
                score = rec.get("hakimiyet_puani") if rec.get("hakimiyet_puani") is not None else score_defaults.get(durum, 0)
                cozulen = rec.get("cozulen_soru", 0)
                hedef = rec.get("hedef_soru", 0)
                tekrar_durumu = rec.get("tekrar_durumu", "")
                son_tekrar = rec.get("son_tekrar_tarihi", "")
                koc_notu = str(rec.get("koc_notu", "") or "").strip()
                c_data = CURRICULUM_DATA.get("topics", {}).get(topic, {})
                
                # --- KOLON 0: Konu Adı + Sınav Ağırlığı Rozeti (Geniş & Üst Üste Gelmeyen) ---
                w_topic = QWidget()
                w_topic_lay = QVBoxLayout(w_topic)
                w_topic_lay.setContentsMargins(10, 6, 10, 6)
                w_topic_lay.setSpacing(4)
                
                lbl_tname = QLabel(f"<b>{topic}</b>")
                lbl_tname.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f172a;")
                lbl_tname.setMinimumHeight(18)
                w_topic_lay.addWidget(lbl_tname)
                
                imp = str(c_data.get("importance", "")).strip()
                qs = str(c_data.get("questions", "")).strip()
                
                if "yüksek" in imp.lower() or "5/5" in imp.lower():
                    badge_txt = f"<span style='background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:bold;'>🔥 Yüksek Önem ({qs if qs else '1-3 Soru'})</span>"
                elif "orta" in imp.lower() or "3/5" in imp.lower() or "4/5" in imp.lower():
                    badge_txt = f"<span style='background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:bold;'>⭐ Orta Önem ({qs if qs else '1-2 Soru'})</span>"
                else:
                    badge_txt = f"<span style='background:#f1f5f9; color:#64748b; padding:2px 8px; border-radius:4px; font-size:10px;'>📌 Temel Konu ({qs if qs else '1 Soru'})</span>"
                    
                lbl_badge = QLabel(badge_txt)
                lbl_badge.setFixedHeight(20)
                w_topic_lay.addWidget(lbl_badge)
                self.table_topics.setCellWidget(i, 0, w_topic)
                
                # --- KOLON 1: Koçluk Hakimiyet Düzeyi (6 Seviye) ---
                cmb_status = QComboBox()
                cmb_status.setCursor(Qt.CursorShape.PointingHandCursor)
                cmb_status.addItem("⚪ Başlanmadı", 0)
                cmb_status.addItem("📖 Konu Anlatımı / Dinleme", 1)
                cmb_status.addItem("✏️ 1. Kaynak Test Çözümü", 2)
                cmb_status.addItem("🔄 Pekiştirme & Tekrar", 3)
                cmb_status.addItem("🏆 Tam Hakimiyet (Usta)", 4)
                cmb_status.addItem("⚠️ Zorlanıyor / Kritik Eksik", 5)
                
                # Seçili indexi bul
                idx_to_set = 0
                for opt_idx in range(cmb_status.count()):
                    if cmb_status.itemData(opt_idx) == durum:
                        idx_to_set = opt_idx
                        break
                cmb_status.setCurrentIndex(idx_to_set)
                
                # Duruma göre renk stili
                status_styles = {
                    0: "background: #f8fafc; color: #475569; border: 1px solid #cbd5e1;",
                    1: "background: #eff6ff; color: #1d4ed8; border: 1px solid #93c5fd; font-weight: bold;",
                    2: "background: #fefce8; color: #854d0e; border: 1px solid #fef08a; font-weight: bold;",
                    3: "background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; font-weight: bold;",
                    4: "background: #f0fdf4; color: #15803d; border: 1px solid #86efac; font-weight: bold;",
                    5: "background: #fef2f2; color: #b91c1c; border: 1px solid #fca5a5; font-weight: bold;",
                }
                curr_style = status_styles.get(durum, status_styles[0])
                cmb_status.setStyleSheet(f"""
                    QComboBox {{
                        {curr_style}
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-size: 11px;
                    }}
                    QComboBox::drop-down {{
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 20px;
                        border-left: 1px solid #e2e8f0;
                        border-top-right-radius: 6px;
                        border-bottom-right-radius: 6px;
                        background: transparent;
                    }}
                    QComboBox::drop-down:hover {{
                        background: #f1f5f9;
                    }}
                    QComboBox::down-arrow {{
                        image: none;
                        border-left: 4px solid transparent;
                        border-right: 4px solid transparent;
                        border-top: 5px solid #64748b;
                    }}
                """)
                
                cmb_status.currentIndexChanged.connect(
                    lambda c_idx, t=topic, s=subject, bid=selected_book_id, cmb=cmb_status: 
                        self._save_topic_status(s, t, cmb.itemData(c_idx), bid)
                )
                self.table_topics.setCellWidget(i, 1, cmb_status)
                
                # --- KOLON 2: Kavrama Oranı (%) ---
                w_score = QWidget()
                w_score_lay = QHBoxLayout(w_score)
                w_score_lay.setContentsMargins(6, 4, 6, 4)
                w_score_lay.setSpacing(6)
                
                spbar = QProgressBar()
                spbar.setRange(0, 100)
                spbar.setValue(score)
                spbar.setFixedHeight(8)
                spbar.setTextVisible(False)
                
                bar_color = "#22c55e" if score >= 70 else ("#f59e0b" if score >= 40 else "#ef4444")
                spbar.setStyleSheet(f"""
                    QProgressBar {{ background: #f1f5f9; border-radius: 4px; }}
                    QProgressBar::chunk {{ background: {bar_color}; border-radius: 4px; }}
                """)
                w_score_lay.addWidget(spbar)
                
                btn_score = QPushButton(f"%{score}")
                btn_score.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_score.setToolTip("Kavrama / Anlama oranını değiştirmek için tıklayın")
                btn_score.setFixedSize(48, 26)
                btn_score.setStyleSheet("""
                    QPushButton {
                        background: #ffffff;
                        color: #1e293b;
                        font-weight: bold;
                        font-size: 11px;
                        border: 1px solid #cbd5e1;
                        border-radius: 4px;
                    }
                    QPushButton:hover { background: #f1f5f9; border-color: #3b82f6; }
                """)
                btn_score.clicked.connect(lambda _, t=topic, s=subject, sc=score, bid=selected_book_id: 
                    self._edit_topic_mastery(s, t, sc, bid)
                )
                w_score_lay.addWidget(btn_score)
                self.table_topics.setCellWidget(i, 2, w_score)
                
                # --- KOLON 3: Çözülen Soru / Hedef ---
                q_text = f"{cozulen} / {hedef} Soru" if hedef > 0 else f"{cozulen} Soru"
                btn_q = QPushButton(q_text)
                btn_q.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_q.setToolTip("Çözülen ve hedef soru sayısını güncellemek için tıklayın")
                btn_q.setFixedHeight(28)
                btn_q.setStyleSheet("""
                    QPushButton {
                        background: #f8fafc;
                        color: #0f172a;
                        font-size: 11px;
                        font-weight: 600;
                        border: 1px solid #e2e8f0;
                        border-radius: 6px;
                        padding: 0 8px;
                    }
                    QPushButton:hover { background: #eff6ff; border-color: #93c5fd; color: #1d4ed8; }
                """)
                btn_q.clicked.connect(lambda _, t=topic, s=subject, cz=cozulen, hf=hedef, bid=selected_book_id:
                    self._edit_topic_questions(s, t, cz, hf, bid)
                )
                self.table_topics.setCellWidget(i, 3, btn_q)
                
                # --- KOLON 4: Aralıklı Tekrar (Spaced Repetition) ---
                if durum == 4:
                    rep_txt = "✅ Sınava Hazır"
                    rep_style = "background: #f0fdf4; color: #15803d; border: 1px solid #86efac;"
                elif son_tekrar:
                    rep_txt = f"📅 {son_tekrar[-5:]} Tekrarı"
                    rep_style = "background: #fefce8; color: #854d0e; border: 1px solid #fde047;"
                elif durum in (2, 3):
                    rep_txt = "⏳ Tekrar Planla"
                    rep_style = "background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa;"
                else:
                    rep_txt = "⚪ Başlanmadı"
                    rep_style = "background: #f8fafc; color: #94a3b8; border: 1px solid #e2e8f0;"
                    
                btn_rep = QPushButton(rep_txt)
                btn_rep.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_rep.setToolTip("Aralıklı tekrar durumunu güncellemek / Bugün tekrar edildi olarak işaretlemek için tıklayın")
                btn_rep.setFixedHeight(28)
                btn_rep.setStyleSheet(f"""
                    QPushButton {{
                        {rep_style}
                        font-size: 11px;
                        font-weight: 500;
                        border-radius: 6px;
                        padding: 0 6px;
                    }}
                    QPushButton:hover {{ opacity: 0.9; }}
                """)
                btn_rep.clicked.connect(lambda _, t=topic, s=subject, bid=selected_book_id:
                    self._mark_spaced_repetition(s, t, bid)
                )
                self.table_topics.setCellWidget(i, 4, btn_rep)
                
                # --- KOLON 5: Koç Notu ---
                if koc_notu:
                    btn_note = QPushButton("📝 Not Var")
                    btn_note.setToolTip(f"Koç Notu:\n{koc_notu}")
                    btn_note.setStyleSheet("""
                        QPushButton {
                            background: #eff6ff;
                            color: #1d4ed8;
                            font-size: 11px;
                            font-weight: bold;
                            border: 1px solid #bfdbfe;
                            border-radius: 6px;
                        }
                        QPushButton:hover { background: #dbeafe; }
                    """)
                else:
                    btn_note = QPushButton("➕ Not Ekle")
                    btn_note.setToolTip("Bu konuya özel koç değerlendirme notu ekleyin")
                    btn_note.setStyleSheet("""
                        QPushButton {
                            background: #f8fafc;
                            color: #64748b;
                            font-size: 11px;
                            border: 1px solid #e2e8f0;
                            border-radius: 6px;
                        }
                        QPushButton:hover { background: #f1f5f9; color: #0f172a; }
                    """)
                btn_note.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_note.setFixedHeight(28)
                btn_note.clicked.connect(lambda _, t=topic, s=subject, n=koc_notu, bid=selected_book_id:
                    self._edit_topic_note(s, t, n, bid)
                )
                self.table_topics.setCellWidget(i, 5, btn_note)
                
                # --- KOLON 6: Strateji Rehberi (Koç Modu) ---
                btn_guide = QPushButton("💡 Koç Modu")
                btn_guide.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_guide.setToolTip("ÖSYM analizleri, çalışma modları ve çıkmış soru taktikleri")
                btn_guide.setFixedHeight(28)
                btn_guide.setStyleSheet("""
                    QPushButton {
                        background: #3b82f6;
                        color: white;
                        font-weight: bold;
                        font-size: 11px;
                        border-radius: 6px;
                        border: none;
                    }
                    QPushButton:hover { background: #2563eb; }
                """)
                btn_guide.clicked.connect(lambda _, t=topic, d=c_data: self._open_coach_details(t, d))
                self.table_topics.setCellWidget(i, 6, btn_guide)
                
        finally:
            con.close()

    def _open_coach_details(self, name, data):
        if not data:
            data = {
                "importance": "Belirleniyor",
                "questions": "1 Soru",
                "tip": "Bu konunun temel kavramlarını tam pekiştirip soru çözümlerine geçin.",
                "coach_checklist": ["Konu özeti çıkarıldı mı?", "Yanlış sorular incelendi mi?"]
            }
        dlg = CoachDetailDialog(name, data, self)
        dlg.exec()

    def _save_topic_status(self, subject, topic, status, book_id):
        if not self.current_student_id: return
        
        # Duruma göre varsayılan kavrama puanı
        default_scores = {0: 0, 1: 30, 2: 60, 3: 80, 4: 100, 5: 25}
        new_score = default_scores.get(status, 0)
        tekrar_val = "Sınava Hazır" if status == 4 else ("Pekiştirme/Tekrar" if status == 3 else "")
        
        con = db.get_conn()
        try:
            exist = con.execute(
                "SELECT id, hakimiyet_puani FROM koc_konu_takip WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=? AND kitap_id=?", 
                (self.current_student_id, subject, topic, book_id)
            ).fetchone()
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            if exist:
                cur_score = exist["hakimiyet_puani"] or 0
                # Eğer puan daha önce manuel verilmemişse veya tam hakimiyete alındıysa güncelle
                target_score = 100 if status == 4 else (cur_score if cur_score > 0 else new_score)
                con.execute("""
                    UPDATE koc_konu_takip 
                    SET durum=?, hakimiyet_puani=?, tekrar_durumu=?, updated_at=?
                    WHERE id=?
                """, (status, target_score, tekrar_val, now_str, exist["id"]))
            else:
                con.execute("""
                    INSERT INTO koc_konu_takip 
                    (ogrenci_id, ders_adi, konu_adi, durum, hakimiyet_puani, tekrar_durumu, kitap_id, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.current_student_id, subject, topic, status, new_score, tekrar_val, book_id, now_str))
                
            con.commit()
            self._load_topics()
        finally:
            con.close()

    def _edit_topic_mastery(self, subject, topic, current_val, book_id):
        if not self.current_student_id: return
        val, ok = QInputDialog.getInt(
            self, "Kavrama & Net Oranı",
            f"'{topic}' konusundaki öğrenci hakimiyet ve net oranı (%) [0-100]:",
            current_val, 0, 100, 5
        )
        if ok:
            con = db.get_conn()
            try:
                exist = con.execute(
                    "SELECT id FROM koc_konu_takip WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=? AND kitap_id=?",
                    (self.current_student_id, subject, topic, book_id)
                ).fetchone()
                
                # Puana göre durum önerisi
                durum = 4 if val >= 85 else (3 if val >= 70 else (2 if val >= 45 else 1))
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                if exist:
                    con.execute("""
                        UPDATE koc_konu_takip 
                        SET hakimiyet_puani=?, durum=?, updated_at=?
                        WHERE id=?
                    """, (val, durum, now_str, exist["id"]))
                else:
                    con.execute("""
                        INSERT INTO koc_konu_takip 
                        (ogrenci_id, ders_adi, konu_adi, durum, hakimiyet_puani, kitap_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (self.current_student_id, subject, topic, durum, val, book_id, now_str))
                    
                con.commit()
                self._load_topics()
            finally:
                con.close()

    def _edit_topic_questions(self, subject, topic, current_cozulen, current_hedef, book_id):
        if not self.current_student_id: return
        coz, ok1 = QInputDialog.getInt(
            self, "Çözülen Soru Sayısı",
            f"'{topic}' konusundan şimdiye kadar çözülen toplam soru sayısı:",
            current_cozulen, 0, 10000, 10
        )
        if not ok1: return
        
        hdf, ok2 = QInputDialog.getInt(
            self, "Hedef Soru Sayısı",
            f"'{topic}' konusu için toplam hedef soru sayısı:",
            current_hedef if current_hedef else 150, 0, 10000, 10
        )
        if not ok2: return
        
        con = db.get_conn()
        try:
            exist = con.execute(
                "SELECT id FROM koc_konu_takip WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=? AND kitap_id=?",
                (self.current_student_id, subject, topic, book_id)
            ).fetchone()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            if exist:
                con.execute("""
                    UPDATE koc_konu_takip 
                    SET cozulen_soru=?, hedef_soru=?, updated_at=?
                    WHERE id=?
                """, (coz, hdf, now_str, exist["id"]))
            else:
                con.execute("""
                    INSERT INTO koc_konu_takip 
                    (ogrenci_id, ders_adi, konu_adi, cozulen_soru, hedef_soru, kitap_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (self.current_student_id, subject, topic, coz, hdf, book_id, now_str))
            con.commit()
            self._load_topics()
        finally:
            con.close()

    def _edit_topic_note(self, subject, topic, current_note, book_id):
        if not self.current_student_id: return
        
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Koç Notu: {topic}")
        dlg.resize(480, 260)
        l = QVBoxLayout(dlg)
        l.setSpacing(10)
        
        l.addWidget(QLabel(f"<b>{topic}</b> — Koçluk Değerlendirme Notu:"))
        txt = QTextEdit()
        txt.setPlainText(current_note)
        txt.setPlaceholderText("Örn: Bu konuda işaret hataları yapıyor. 20 soru yeni nesil soru pekiştirilmeli.")
        l.addWidget(txt)
        
        b_lay = QHBoxLayout()
        b_lay.addStretch()
        btn_save = QPushButton("💾 Notu Kaydet")
        btn_save.setStyleSheet("background: #16a34a; color: white; font-weight: bold; padding: 6px 14px; border-radius: 6px;")
        btn_save.clicked.connect(dlg.accept)
        b_lay.addWidget(btn_save)
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dlg.reject)
        b_lay.addWidget(btn_cancel)
        l.addLayout(b_lay)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            note_content = txt.toPlainText().strip()
            con = db.get_conn()
            try:
                exist = con.execute(
                    "SELECT id FROM koc_konu_takip WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=? AND kitap_id=?",
                    (self.current_student_id, subject, topic, book_id)
                ).fetchone()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                if exist:
                    con.execute("UPDATE koc_konu_takip SET koc_notu=?, updated_at=? WHERE id=?", 
                                (note_content, now_str, exist["id"]))
                else:
                    con.execute("""
                        INSERT INTO koc_konu_takip 
                        (ogrenci_id, ders_adi, konu_adi, koc_notu, kitap_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (self.current_student_id, subject, topic, note_content, book_id, now_str))
                con.commit()
                self._load_topics()
            finally:
                con.close()

    def _mark_spaced_repetition(self, subject, topic, book_id):
        if not self.current_student_id: return
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        res = QMessageBox.question(
            self, "Aralıklı Tekrar",
            f"'{topic}' konusunu bugün ({today_str}) tekrar edildi olarak işaretlemek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes: return
        
        con = db.get_conn()
        try:
            exist = con.execute(
                "SELECT id FROM koc_konu_takip WHERE ogrenci_id=? AND ders_adi=? AND konu_adi=? AND kitap_id=?",
                (self.current_student_id, subject, topic, book_id)
            ).fetchone()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            if exist:
                con.execute("""
                    UPDATE koc_konu_takip 
                    SET son_tekrar_tarihi=?, tekrar_durumu='Tekrar Yapıldı', updated_at=?
                    WHERE id=?
                """, (today_str, now_str, exist["id"]))
            else:
                con.execute("""
                    INSERT INTO koc_konu_takip 
                    (ogrenci_id, ders_adi, konu_adi, son_tekrar_tarihi, tekrar_durumu, kitap_id, updated_at)
                    VALUES (?, ?, ?, ?, 'Tekrar Yapıldı', ?, ?)
                """, (self.current_student_id, subject, topic, today_str, book_id, now_str))
            con.commit()
            self._load_topics()
            QMessageBox.information(self, "Başarılı", f"'{topic}' tekrar tarihi ({today_str}) olarak kaydedildi!")
        finally:
            con.close()

    def _open_curriculum_report(self):
        if not self.current_student_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir öğrenci seçiniz.")
            return
            
        subject = self.cmb_topic_subject.currentText()
        std_name = self.current_student_name or "Öğrenci"
        
        con = db.get_conn()
        try:
            rows = con.execute("""
                SELECT konu_adi, durum, hakimiyet_puani, cozulen_soru, hedef_soru, koc_notu, son_tekrar_tarihi 
                FROM koc_konu_takip 
                WHERE ogrenci_id=? AND ders_adi=?
            """, (self.current_student_id, subject)).fetchall()
            rec_map = {r["konu_adi"]: dict(r) for r in rows}
        finally:
            con.close()
            
        topics = TOPIC_LIST.get(subject, [])
        durum_labels = {
            0: "⚪ Başlanmadı", 1: "📖 Konu Anlatımı", 2: "✏️ 1. Kaynak Testi",
            3: "🔄 Pekiştirme/Tekrar", 4: "🏆 Tam Hakimiyet", 5: "⚠️ Zorlanıyor/Eksik"
        }
        
        tr_rows = ""
        total_puan = 0
        mastered = 0
        for idx, t in enumerate(topics):
            r = rec_map.get(t, {})
            dur = r.get("durum", 0)
            puan = r.get("hakimiyet_puani", 0)
            total_puan += puan
            if dur == 4: mastered += 1
            coz = r.get("cozulen_soru", 0)
            note = r.get("koc_notu", "") or "-"
            
            c_data = CURRICULUM_DATA.get("topics", {}).get(t, {})
            imp = c_data.get("importance", "-")
            
            tr_rows += f"""
            <tr style='border-bottom: 1px solid #e2e8f0; height: 32px;'>
                <td style='padding: 6px;'><b>{idx+1}. {t}</b><br><small style='color:#64748b;'>{imp}</small></td>
                <td style='padding: 6px;'>{durum_labels.get(dur, '-')}</td>
                <td style='padding: 6px; font-weight:bold;'>%{puan}</td>
                <td style='padding: 6px;'>{coz} Soru</td>
                <td style='padding: 6px; font-size:11px;'>{note}</td>
            </tr>
            """
            
        avg_pct = int(total_puan / len(topics)) if topics else 0
        
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Müfredat Analiz Raporu: {subject}")
        dlg.resize(720, 600)
        l = QVBoxLayout(dlg)
        
        txt = QTextEdit()
        txt.setReadOnly(True)
        html = f"""
        <div style='font-family: sans-serif; padding: 10px;'>
            <h2 style='color: #0f172a; margin-bottom: 4px;'>📊 {std_name} — {subject} Konu Hakimiyeti Raporu</h2>
            <p style='color: #64748b; margin-top: 0;'>Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 15px;'>
                <b>Genel Müfredat Hakimiyeti:</b> %{avg_pct} &nbsp;|&nbsp; 
                <b>Tam Hakimiyet:</b> {mastered} / {len(topics)} Konu
            </div>
            <table style='width: 100%; border-collapse: collapse; text-align: left;'>
                <thead>
                    <tr style='background: #f1f5f9; color: #334155;'>
                        <th style='padding: 8px;'>Konu & Önem</th>
                        <th style='padding: 8px;'>Durum</th>
                        <th style='padding: 8px;'>Kavrama</th>
                        <th style='padding: 8px;'>Çözülen</th>
                        <th style='padding: 8px;'>Koç Notu</th>
                    </tr>
                </thead>
                <tbody>
                    {tr_rows}
                </tbody>
            </table>
        </div>
        """
        txt.setHtml(html)
        l.addWidget(txt)
        
        btn_bar = QHBoxLayout()
        btn_copy_wa = QPushButton("📱 WhatsApp Metni Olarak Kopyala")
        btn_copy_wa.setStyleSheet("background: #25D366; color: white; font-weight: bold; padding: 8px 14px; border-radius: 6px;")
        
        def copy_wa():
            from PyQt6.QtWidgets import QApplication
            wa_text = f"📚 *{std_name} — {subject} Konu Hakimiyeti Özeti*\n\n"
            wa_text += f"🎯 *Genel İlerleme:* %{avg_pct}\n"
            wa_text += f"🏆 *Tamamlanan Konu:* {mastered} / {len(topics)}\n\n"
            wa_text += "*Öne Çıkan Eksikler & Tekrar Gerekenler:*\n"
            for t in topics:
                r = rec_map.get(t, {})
                dur = r.get("durum", 0)
                if dur in (1, 2, 3, 5):
                    wa_text += f"• {t} (%{r.get('hakimiyet_puani', 0)}) - {durum_labels.get(dur)}\n"
            wa_text += "\n_Eğitim Koçluğu Başarı Raporu 🚀_"
            QApplication.clipboard().setText(wa_text)
            QMessageBox.information(dlg, "Kopyalandı", "WhatsApp metni panoya kopyalandı!")
            
        btn_copy_wa.clicked.connect(copy_wa)
        btn_bar.addWidget(btn_copy_wa)
        
        btn_print = QPushButton("🖨️ Yazdır")
        btn_print.setStyleSheet("background: #f1f5f9; font-weight: bold; padding: 8px 14px; border: 1px solid #cbd5e1; border-radius: 6px;")
        
        def print_rep():
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            p_dlg = QPrintDialog(printer, dlg)
            if p_dlg.exec() == QPrintDialog.DialogCode.Accepted:
                txt.print(printer)
                
        btn_print.clicked.connect(print_rep)
        btn_bar.addWidget(btn_print)
        
        btn_bar.addStretch()
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(dlg.accept)
        btn_bar.addWidget(btn_close)
        
        l.addLayout(btn_bar)
        dlg.exec()

    def _transfer_to_weekly_plan(self):
        if not self.current_student_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir öğrenci seçiniz.")
            return
            
        subject = self.cmb_topic_subject.currentText()
        all_topics = TOPIC_LIST.get(subject, [])
        
        con = db.get_conn()
        try:
            rows = con.execute(
                "SELECT konu_adi, durum FROM koc_konu_takip WHERE ogrenci_id=? AND ders_adi=?",
                (self.current_student_id, subject)
            ).fetchall()
            status_map = {r["konu_adi"]: r["durum"] for r in rows}
        finally:
            con.close()
            
        # Tamamlanmamış (durum < 4) konuları listele
        incomplete_topics = [t for t in all_topics if status_map.get(t, 0) < 4]
        
        if not incomplete_topics:
            QMessageBox.information(self, "Bilgi", f"{subject} dersindeki tüm konular tamamlanmış görünüyor!")
            return
            
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Eksikleri Plana Aktar: {subject}")
        dlg.resize(450, 480)
        l = QVBoxLayout(dlg)
        l.setSpacing(10)
        
        l.addWidget(QLabel(f"<b>{subject}</b> dersinde eksik olan konular listelendi.\nBu haftanın planına eklemek istediklerinizi seçiniz:"))
        
        lw = QListWidget()
        for t in incomplete_topics:
            item = QListWidgetItem(t)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            lw.addItem(item)
            
        l.addWidget(lw)
        
        # Soru Hedefi
        h_lay = QHBoxLayout()
        h_lay.addWidget(QLabel("Her konu için soru hedefi:"))
        from PyQt6.QtWidgets import QSpinBox
        sb_target = QSpinBox()
        sb_target.setRange(10, 500)
        sb_target.setValue(50)
        sb_target.setSingleStep(10)
        h_lay.addWidget(sb_target)
        h_lay.addStretch()
        l.addLayout(h_lay)
        
        btn_bar = QHBoxLayout()
        btn_sel_all = QPushButton("Tümünü Seç")
        btn_sel_all.clicked.connect(lambda: [lw.item(i).setCheckState(Qt.CheckState.Checked) for i in range(lw.count())])
        btn_bar.addWidget(btn_sel_all)
        
        btn_clear = QPushButton("Temizle")
        btn_clear.clicked.connect(lambda: [lw.item(i).setCheckState(Qt.CheckState.Unchecked) for i in range(lw.count())])
        btn_bar.addWidget(btn_clear)
        
        btn_bar.addStretch()
        
        btn_add = QPushButton("✨ Plana Ekle")
        btn_add.setStyleSheet("background: #16a34a; color: white; font-weight: bold; padding: 6px 16px; border-radius: 6px;")
        btn_add.clicked.connect(dlg.accept)
        btn_bar.addWidget(btn_add)
        l.addLayout(btn_bar)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected_topics = []
            for i in range(lw.count()):
                it = lw.item(i)
                if it.checkState() == Qt.CheckState.Checked:
                    selected_topics.append(it.text())
                    
            if not selected_topics:
                QMessageBox.warning(self, "Uyarı", "Hiçbir konu seçilmedi.")
                return
                
            # Aktif haftalık plana ekle
            if not self.current_plan_id:
                self._auto_create_plan()
                
            if not self.current_plan_id:
                QMessageBox.warning(self, "Hata", "Aktif haftalık plan oluşturulamadı.")
                return
                
            con = db.get_conn()
            added_count = 0
            try:
                per_target = sb_target.value()
                for st in selected_topics:
                    target_name = f"{subject} - {st}"
                    # Mevcut hedefte var mı?
                    exist = con.execute("SELECT id FROM koc_hedef WHERE plan_id=? AND ders_adi=?", 
                                      (self.current_plan_id, target_name)).fetchone()
                    if not exist:
                        con.execute("""
                            INSERT INTO koc_hedef (plan_id, ders_adi, hedef_soru, cozulen_soru)
                            VALUES (?, ?, ?, 0)
                        """, (self.current_plan_id, target_name, per_target))
                        added_count += 1
                con.commit()
                self._load_plan() # Haftalık planı yenile
                QMessageBox.information(self, "Başarılı", f"{added_count} konu bu haftanın koçluk hedeflerine eklendi!")
            finally:
                con.close()


    def _open_smart_report(self):
        if not self.current_student_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir öğrenci seçin.")
            return

        # 1. Gather Stats (Weekly)
        # Using existing labels or small DB query if labels empty
        try:
            rate = int(self.lbl_completion_rate.text().replace("%", "").strip())
        except: rate = 0
            
        try:
            solved = int(self.lbl_total_solved.text())
        except: solved = 0

        try:
            target = int(self.lbl_total_target.text())
        except: target = 0

        stats = {
            "rate": rate,
            "total_solved": solved,
            "total_target": target
        }

        # 2. Gather Topic Status + Coach Data
        con = db.get_conn()
        topics_data = []
        try:
            # Fetch all user topic statuses
            rows = con.execute("SELECT ders_adi, konu_adi, durum FROM koc_konu_takip WHERE ogrenci_id=?", 
                             (self.current_student_id,)).fetchall()
            
            for r in rows:
                t_name = r["konu_adi"]
                # Try to get coach metadata
                c_data = CURRICULUM_DATA.get("topics", {}).get(t_name, {})
                
                topics_data.append({
                    "subject": r["ders_adi"],
                    "name": t_name,
                    "status": r["durum"], # 1: Started, 2: Completed
                    "coach_data": c_data
                })
        finally:
            con.close()

        student_data = {
            "stats": stats,
            "topics": topics_data
        }
        
        student_name = getattr(self, 'current_student_name', None) or self.lbl_student_name.text().replace("Öğrenci: ", "").replace("Seçili Öğrenci: ", "").strip()
        
        dlg = SmartReportDialog(student_name, student_data, self)
        dlg.exec()

    def _set_exam_date(self):
        today = QDate.currentDate()
        year = today.year()
        target_year = year + 1 if today > QDate(year, 6, 20) else year
        
        # LGS is 1st Sunday of June
        d_lgs = QDate(target_year, 6, 1)
        while d_lgs.dayOfWeek() != 7:
            d_lgs = d_lgs.addDays(1)
            
        # YKS is 3rd Saturday of June
        d_yks = QDate(target_year, 6, 1)
        sats = 0
        while True:
            if d_yks.dayOfWeek() == 6:
                sats += 1
                if sats == 3:
                    break
            d_yks = d_yks.addDays(1)

        dlg = QDialog(self)
        dlg.setWindowTitle("Hedef Sınav Tarihi Ayarla")
        dlg.setMinimumWidth(400)
        l = QVBoxLayout(dlg)
        l.setSpacing(14)
        l.setContentsMargins(20, 20, 20, 20)
        
        lbl_info = QLabel("<b>Hedef Sınav Tarihini Belirleyin:</b><br><span style='color: #64748b; font-size: 11px;'>Hazır YKS veya LGS takvimini seçebilir ya da özel bir tarih belirleyebilirsiniz.</span>")
        lbl_info.setWordWrap(True)
        l.addWidget(lbl_info)
        
        # Hazır Butonlar
        btn_preset_yks = QPushButton(f"🎓 Yaklaşan YKS Tarihi ({d_yks.toString('dd.MM.yyyy')})")
        btn_preset_yks.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_preset_yks.setStyleSheet("padding: 8px 12px; font-weight: 600; text-align: left; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; color: #1e40af;")
        
        btn_preset_lgs = QPushButton(f"🎒 Yaklaşan LGS Tarihi ({d_lgs.toString('dd.MM.yyyy')})")
        btn_preset_lgs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_preset_lgs.setStyleSheet("padding: 8px 12px; font-weight: 600; text-align: left; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; color: #065f46;")
        
        l.addWidget(btn_preset_yks)
        l.addWidget(btn_preset_lgs)
        
        l.addWidget(QLabel("<b>Özel Tarih Seçimi:</b>"))
        cal = QDateEdit()
        cal.setCalendarPopup(True)
        cal.setDisplayFormat("dd.MM.yyyy")
        cal.setMinimumDate(today)
        cal.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 6px;")
        
        saved_date_str = appset.ayar_get("target_exam_date")
        if saved_date_str:
            saved_d = QDate.fromString(saved_date_str, "yyyy-MM-dd")
            if saved_d.isValid() and saved_d >= today:
                cal.setDate(saved_d)
            else:
                cal.setDate(d_yks)
        else:
            cal.setDate(d_yks)
            
        l.addWidget(cal)
        
        btn_preset_yks.clicked.connect(lambda: cal.setDate(d_yks))
        btn_preset_lgs.clicked.connect(lambda: cal.setDate(d_lgs))
        
        btns = QHBoxLayout()
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dlg.reject)
        btn_cancel.setStyleSheet("padding: 7px 16px; border-radius: 6px; border: 1px solid #cbd5e1; background: #f8fafc;")
        
        btn_ok = QPushButton("💾 Tarihi Kaydet")
        btn_ok.clicked.connect(dlg.accept)
        btn_ok.setStyleSheet("padding: 7px 20px; border-radius: 6px; background: #2563eb; color: white; font-weight: bold;")
        
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        l.addLayout(btns)
        
        if dlg.exec():
            new_date = cal.date()
            appset.ayar_set("target_exam_date", new_date.toString("yyyy-MM-dd"))
            self._update_exam_countdown()
            QMessageBox.information(self, "Tarih Kaydedildi", f"Hedef sınav tarihi <b>{new_date.toString('dd.MM.yyyy')}</b> olarak güncellendi.")

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    db.init_db() # Tabloları garantile
    win = CoachingManager()
    win.resize(1000, 600)
    win.show()
    sys.exit(app.exec())
