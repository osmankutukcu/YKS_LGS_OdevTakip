from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QListWidget, 
    QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, 
    QMessageBox, QWidget, QProgressDialog, QScrollArea, QFrame,
    QTabWidget, QTextBrowser, QLineEdit, QSplitter, QSpinBox,
    QProgressBar, QHeaderView, QCheckBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor
import db
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class SmartWizardDialog(QDialog):
    """
    Akıllı Ödev ve Başarı Sihirbazı v3.0 Pro.
    Bilimsel Pedagojik Teknikler:
    - Hermann Ebbinghaus Unutma Eğrisi & Aralıklı Tekrar (1, 7, 14, 30 gün)
    - Bilişsel Yük Teorisi (%30 Tekrar, %50 Ana Hedef, %20 Telafi)
    - ÖSYM / LGS Sınav Soru Frekansı Matrisi
    - Çok Boyutlu Öğrenci Analitiği & Yerel PDR Koçluk Raporlama
    """
    def __init__(self, ogrenci_id=None, parent=None, available_books=None):
        super().__init__(parent)
        self.setWindowTitle("🧙‍♂️ Akıllı Ödev ve Başarı Sihirbazı v3.0 Pro")
        self.resize(1200, 800)
        self.ogrenci_id = ogrenci_id
        self.available_books = available_books or {}
        self.suggested_tasks = []
        self.filtered_tasks = []
        self.selected_homeworks = []
        self.current_filter_category = "all"
        self.analytics_data = None
        self.weekly_plan_data = None

        self._build_ui()
        self._load_students()

        if self.ogrenci_id:
            QTimer.singleShot(400, self._run_analysis)

        self.showMaximized()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 12, 15, 12)
        root.setSpacing(10)

        # --- HEADER ---
        header = QHBoxLayout()
        header.setSpacing(12)

        lbl_icon = QLabel("🧙‍♂️")
        lbl_icon.setStyleSheet("font-size: 38px;")

        vbox = QVBoxLayout()
        lbl_title = QLabel("Yapay Zeka & Pedagojik Başarı Sihirbazı")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4338ca;")
        lbl_desc = QLabel("Ebbinghaus Unutma Eğrisi • Bilişsel Yük Dengesi • ÖSYM/LGS Sınav Öncelikleri")
        lbl_desc.setStyleSheet("color: #64748b; font-size: 12px;")
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_desc)

        header.addWidget(lbl_icon)
        header.addLayout(vbox)
        header.addStretch(1)

        # Öğrenci Seçici (Eğer dışarıdan verilmediyse)
        self.cmbStudent = QComboBox()
        self.cmbStudent.setMinimumWidth(220)
        self.cmbStudent.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 12px; font-weight: bold; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 24px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 8px; }
        """)
        self.cmbStudent.setEnabled(self.ogrenci_id is None)
        self.cmbStudent.currentIndexChanged.connect(self._on_student_combo_changed)

        header.addWidget(QLabel("<b>Öğrenci:</b>"))
        header.addWidget(self.cmbStudent)
        root.addLayout(header)

        # --- 4 LIVE EXECUTIVE KPI CARDS ---
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.card_success = self._create_kpi_card("📊 Genel Başarı", "%0", "0/0 Ödev Tamamlandı", "#059669", "#ecfdf5")
        self.card_overdue = self._create_kpi_card("⏳ Geciken / Telafi", "0 Ödev", "Acil Telafi Bekliyor", "#dc2626", "#fef2f2")
        self.card_ebbinghaus = self._create_kpi_card("🧠 Ebbinghaus Tekrarı", "0 Konu", "Hafıza Tazeleyici", "#7c3aed", "#f5f3ff")
        self.card_exam = self._create_kpi_card("🎯 Sınavda Çok Çıkar", "0 Konu", "ÖSYM/LGS Yüksek Ağırlık", "#d97706", "#fffbeb")

        kpi_row.addWidget(self.card_success)
        kpi_row.addWidget(self.card_overdue)
        kpi_row.addWidget(self.card_ebbinghaus)
        kpi_row.addWidget(self.card_exam)
        root.addLayout(kpi_row)

        # --- TABS ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 8px; background: white; top: -1px; } 
            QTabBar::tab { background: #f8fafc; border: 1px solid #cbd5e1; padding: 9px 20px; font-weight: 600; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 4px; color: #475569; }
            QTabBar::tab:selected { background: white; border-bottom-color: white; font-weight: bold; color: #4338ca; }
        """)

        # Tab 1: Akıllı Ödev Önerileri
        self.tabSuggestions = QWidget()
        self._build_suggestions_tab(self.tabSuggestions)
        self.tabs.addTab(self.tabSuggestions, "🎯 Akıllı Ödev Önerileri")

        # Tab 2: Haftalık Strateji (Pro)
        self.tabStrategy = QWidget()
        self._build_strategy_tab(self.tabStrategy)
        self.tabs.addTab(self.tabStrategy, "📅 Haftalık Strateji & Dağılım (Pro)")

        # Tab 3: AI Koçluk & PDR Raporu
        self.tabCoach = QWidget()
        self._build_coach_tab(self.tabCoach)
        self.tabs.addTab(self.tabCoach, "🤖 AI Koçluk & PDR Raporu")

        root.addWidget(self.tabs, 1)

    def _create_kpi_card(self, title: str, main_val: str, subtitle: str, color: str, bg_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {color}40;
                border-radius: 10px;
                padding: 6px 12px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        
        lbl_m = QLabel(main_val)
        lbl_m.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {color};")
        lbl_m.setObjectName("kpi_main")

        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet("font-size: 11px; color: #64748b;")
        lbl_s.setObjectName("kpi_sub")

        lay.addWidget(lbl_t)
        lay.addWidget(lbl_m)
        lay.addWidget(lbl_s)
        return card

    def _build_suggestions_tab(self, parent_widget):
        main_lay = QVBoxLayout(parent_widget)
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(10)

        content = QHBoxLayout()
        content.setSpacing(12)

        # --- SOL PANEL: Bilişsel Yük & Pedagojik Durum ---
        left_panel = QFrame()
        left_panel.setFixedWidth(330)
        left_panel.setStyleSheet("QFrame { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; }")
        lay_left = QVBoxLayout(left_panel)
        lay_left.setContentsMargins(12, 12, 12, 12)
        lay_left.setSpacing(10)

        lbl_left_title = QLabel("🧠 Bilişsel Profil & Analiz")
        lbl_left_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1e293b;")
        lay_left.addWidget(lbl_left_title)

        # Profil Rozeti
        self.lblProfileBadge = QLabel("🎯 Profil: Analiz bekleniyor...")
        self.lblProfileBadge.setWordWrap(True)
        self.lblProfileBadge.setStyleSheet("background: #e0e7ff; color: #3730a3; padding: 8px 10px; border-radius: 6px; font-weight: bold; font-size: 12px;")
        lay_left.addWidget(self.lblProfileBadge)

        # Ders Bazlı İlerleme Çubukları Scroll Alanı
        lay_left.addWidget(QLabel("<b>Ders Bazlı Tamamlama Durumu:</b>"))
        scroll_lessons = QScrollArea()
        scroll_lessons.setWidgetResizable(True)
        scroll_lessons.setFrameShape(QFrame.Shape.NoFrame)
        scroll_lessons.setStyleSheet("background: transparent;")
        
        self.lessons_container = QWidget()
        self.lessons_container.setStyleSheet("background: transparent;")
        self.lay_lessons_bars = QVBoxLayout(self.lessons_container)
        self.lay_lessons_bars.setContentsMargins(0, 0, 0, 0)
        self.lay_lessons_bars.setSpacing(6)
        self.lay_lessons_bars.addStretch(1)
        scroll_lessons.setWidget(self.lessons_container)
        lay_left.addWidget(scroll_lessons, 1)

        # Strateji Modu
        lay_left.addWidget(QLabel("<b>Planlama Strateji Modu:</b>"))
        self.cmbStrategyMode = QComboBox()
        self.cmbStrategyMode.addItems([
            "🌟 Dengeli Karma (Tavsiye Edilen)",
            "🚨 Acil Telafi & Gecikenler",
            "🧠 Ebbinghaus Aralıklı Tekrar",
            "🔥 ÖSYM Sınav & Net Artırma",
            "📘 Müfredat İlerleme"
        ])
        self.cmbStrategyMode.setStyleSheet("""
            QComboBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; font-size: 12px; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
            QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #64748b; margin-right: 6px; }
        """)
        self.cmbStrategyMode.currentIndexChanged.connect(self._on_strategy_mode_changed)
        lay_left.addWidget(self.cmbStrategyMode)

        # Hedef Süre
        h_dur = QHBoxLayout()
        h_dur.addWidget(QLabel("<b>Hedef Süre:</b>"))
        self.spTargetMinutes = QSpinBox()
        self.spTargetMinutes.setRange(30, 480)
        self.spTargetMinutes.setSingleStep(30)
        self.spTargetMinutes.setValue(180)
        self.spTargetMinutes.setSuffix(" dk")
        self.spTargetMinutes.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px;")
        self.spTargetMinutes.valueChanged.connect(self._on_target_minutes_changed)
        h_dur.addWidget(self.spTargetMinutes)
        lay_left.addLayout(h_dur)

        # Yeniden Analiz Butonu
        self.btnReanalyze = QPushButton("🔄 Yeniden Analiz Et")
        self.btnReanalyze.setStyleSheet("""
            QPushButton { background: #4f46e5; color: white; font-weight: bold; border-radius: 6px; padding: 8px; font-size: 12px; }
            QPushButton:hover { background: #4338ca; }
        """)
        self.btnReanalyze.clicked.connect(self._run_analysis)
        lay_left.addWidget(self.btnReanalyze)

        content.addWidget(left_panel)

        # --- SAĞ PANEL: Öneri Listesi & Tablo ---
        right_panel = QWidget()
        lay_right = QVBoxLayout(right_panel)
        lay_right.setContentsMargins(0, 0, 0, 0)
        lay_right.setSpacing(8)

        # Filtre ve Arama Araç Çubuğu
        tools_lay = QHBoxLayout()
        tools_lay.setSpacing(6)

        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("🔍 Konu, ders veya kitap ara...")
        self.txtSearch.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;")
        self.txtSearch.textChanged.connect(self._filter_table_items)
        tools_lay.addWidget(self.txtSearch, 2)

        # Kategori Butonları
        self.btnFilterAll = QPushButton("Tümü")
        self.btnFilterRemedial = QPushButton("🚨 Telafi")
        self.btnFilterEbbinghaus = QPushButton("🧠 Tekrar")
        self.btnFilterExam = QPushButton("🔥 Sınav")
        self.btnFilterCurriculum = QPushButton("📘 Müfredat")

        for b in [self.btnFilterAll, self.btnFilterRemedial, self.btnFilterEbbinghaus, self.btnFilterExam, self.btnFilterCurriculum]:
            b.setCheckable(True)
            b.setStyleSheet("""
                QPushButton { background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: 600; color: #334155; }
                QPushButton:checked { background: #4338ca; color: white; border-color: #4338ca; }
            """)
        self.btnFilterAll.setChecked(True)

        self.btnFilterAll.clicked.connect(lambda: self._set_category_filter("all"))
        self.btnFilterRemedial.clicked.connect(lambda: self._set_category_filter("remedial"))
        self.btnFilterEbbinghaus.clicked.connect(lambda: self._set_category_filter("ebbinghaus"))
        self.btnFilterExam.clicked.connect(lambda: self._set_category_filter("exam"))
        self.btnFilterCurriculum.clicked.connect(lambda: self._set_category_filter("curriculum"))

        tools_lay.addWidget(self.btnFilterAll)
        tools_lay.addWidget(self.btnFilterRemedial)
        tools_lay.addWidget(self.btnFilterEbbinghaus)
        tools_lay.addWidget(self.btnFilterExam)
        tools_lay.addWidget(self.btnFilterCurriculum)

        self.btnToggleSelectAll = QPushButton("Tümünü Seç/Kaldır")
        self.btnToggleSelectAll.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 10px; font-size: 11px; font-weight: bold;")
        self.btnToggleSelectAll.clicked.connect(self._toggle_selection)
        tools_lay.addWidget(self.btnToggleSelectAll)

        lay_right.addLayout(tools_lay)

        # Tablo
        self.tableSuggestions = QTableWidget(0, 7)
        self.tableSuggestions.setHorizontalHeaderLabels([
            "Öncelik & Tür", "Ders", "Kitap / Kaynak", "Konu", "Hedef Yük", "Bilimsel Gerekçe & Detay", "Seç"
        ])
        self.tableSuggestions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableSuggestions.setStyleSheet("""
            QTableWidget { background: white; gridline-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; }
            QHeaderView::section { background-color: #f8fafc; padding: 6px 8px; border: 1px solid #e2e8f0; font-weight: bold; color: #334155; }
            QTableWidget::item { padding: 4px 6px; }
        """)
        self.tableSuggestions.verticalHeader().setVisible(False)
        lay_right.addWidget(self.tableSuggestions)

        content.addWidget(right_panel, 1)
        main_lay.addLayout(content)

        # --- ALT BAR (Footer) ---
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.lblLiveSummary = QLabel("Seçilen: 0 Ödev (~0 dk, ~0 Soru) | Bilişsel Yük: 🟢 Dengeli")
        self.lblLiveSummary.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b;")
        footer.addWidget(self.lblLiveSummary)
        footer.addStretch(1)

        self.btnPrint = QPushButton("🖨️ PDF Raporu")
        self.btnPrint.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 14px; font-weight: 600; color: #334155;")
        self.btnPrint.clicked.connect(self._print_preview)
        footer.addWidget(self.btnPrint)

        self.btnCopyWhatsapp = QPushButton("📋 Panoya Kopyala")
        self.btnCopyWhatsapp.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 14px; font-weight: 600; color: #334155;")
        self.btnCopyWhatsapp.clicked.connect(self._copy_suggestions_text)
        footer.addWidget(self.btnCopyWhatsapp)

        self.btnAddSelected = QPushButton("✅ Seçilenleri Ödev Takip Formuna Aktar")
        self.btnAddSelected.setStyleSheet("""
            QPushButton { background-color: #059669; color: white; padding: 10px 22px; font-weight: bold; border-radius: 8px; font-size: 13px; }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btnAddSelected.clicked.connect(self._accept_selection)
        footer.addWidget(self.btnAddSelected)

        main_lay.addLayout(footer)

    def _build_strategy_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel("📅 <b>Bilişsel Yük & Pomodoro Dengeli Haftalık Çalışma Matrisi:</b> Ödevleri ve aralıklı tekrarları günlere dengeli şekilde yayar.")
        info.setStyleSheet("color: #475569; font-size: 13px;")
        layout.addWidget(info)

        self.txtStrategy = QTextBrowser()
        self.txtStrategy.setStyleSheet("background: #fafafa; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; font-family: 'Segoe UI', sans-serif;")
        layout.addWidget(self.txtStrategy, 1)

        btn_bar = QHBoxLayout()
        self.btnCopyPlan = QPushButton("📋 Haftalık Planı Kopyala")
        self.btnCopyPlan.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 14px; font-weight: bold;")
        self.btnCopyPlan.clicked.connect(self._copy_plan_text)

        self.btnRefreshPlan = QPushButton("🔄 Planı Yenile")
        self.btnRefreshPlan.setStyleSheet("background: #4f46e5; color: white; border-radius: 6px; padding: 6px 14px; font-weight: bold;")
        self.btnRefreshPlan.clicked.connect(lambda: self._generate_weekly_plan(silent=False))

        btn_bar.addStretch()
        btn_bar.addWidget(self.btnCopyPlan)
        btn_bar.addWidget(self.btnRefreshPlan)
        layout.addLayout(btn_bar)

    def _build_coach_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_info = QLabel("🤖 <b>Pedagojik PDR Koçluk ve Motivasyon Analizi:</b> Öğrencinin geçmiş ödev performansı ve öğrenme eğrisine göre bilimsel koçluk değerlendirmesi üretir.")
        top_info.setStyleSheet("color: #475569; font-size: 13px;")
        layout.addWidget(top_info)

        split = QSplitter(Qt.Orientation.Horizontal)

        # Sol PDR Değerlendirme
        pdr_box = QFrame()
        pdr_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        lay_pdr = QVBoxLayout(pdr_box)
        lay_pdr.addWidget(QLabel("<b>📋 Pedagojik Durum Değerlendirmesi:</b>"))
        self.txtPdrSummary = QTextBrowser()
        self.txtPdrSummary.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 13px;")
        lay_pdr.addWidget(self.txtPdrSummary)
        split.addWidget(pdr_box)

        # Sağ WhatsApp Mesajları
        wa_box = QFrame()
        wa_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        lay_wa = QVBoxLayout(wa_box)
        
        lay_wa.addWidget(QLabel("<b>📱 Öğrenciye Özel WhatsApp Mesajı:</b>"))
        self.txtWaStudent = QTextBrowser()
        self.txtWaStudent.setStyleSheet("background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 8px; font-size: 12px;")
        lay_wa.addWidget(self.txtWaStudent)
        
        btn_cp_st = QPushButton("📋 Öğrenci Mesajını Kopyala")
        btn_cp_st.setStyleSheet("background: #059669; color: white; font-weight: bold; border-radius: 6px; padding: 6px;")
        btn_cp_st.clicked.connect(lambda: self._copy_to_clipboard(self.txtWaStudent.toPlainText(), "Öğrenci mesajı kopyalandı ✅"))
        lay_wa.addWidget(btn_cp_st)

        lay_wa.addWidget(QLabel("<b>👨‍👩‍👦 Veliye Özel Bilgilendirme Mesajı:</b>"))
        self.txtWaParent = QTextBrowser()
        self.txtWaParent.setStyleSheet("background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px; font-size: 12px;")
        lay_wa.addWidget(self.txtWaParent)

        btn_cp_pr = QPushButton("📋 Veli Mesajını Kopyala")
        btn_cp_pr.setStyleSheet("background: #2563eb; color: white; font-weight: bold; border-radius: 6px; padding: 6px;")
        btn_cp_pr.clicked.connect(lambda: self._copy_to_clipboard(self.txtWaParent.toPlainText(), "Veli mesajı kopyalandı ✅"))
        lay_wa.addWidget(btn_cp_pr)

        split.addWidget(wa_box)
        layout.addWidget(split, 1)

    # ---------------- LOGIC & DATA LOADING ----------------

    def _load_students(self):
        con = db.get_conn()
        try:
            rows = con.execute("SELECT id, ad, soyad FROM ogrenci WHERE aktif=1 ORDER BY ad").fetchall()
            for r in rows:
                name = f"{r['ad']} {r['soyad']}".strip()
                self.cmbStudent.addItem(name, r['id'])
                if self.ogrenci_id and r['id'] == self.ogrenci_id:
                    self.cmbStudent.setCurrentText(name)
        finally:
            con.close()

    def _get_current_oid(self):
        if self.ogrenci_id:
            return self.ogrenci_id
        idx = self.cmbStudent.currentIndex()
        if idx >= 0:
            return self.cmbStudent.itemData(idx)
        return None

    def _on_student_combo_changed(self, idx):
        if idx >= 0:
            self.ogrenci_id = self.cmbStudent.itemData(idx)
            self._run_analysis()

    def _run_analysis(self):
        oid = self._get_current_oid()
        if not oid:
            return

        progress = QProgressDialog("Öğrenci geçmişi, Ebbinghaus eğrisi ve sınav hedefleri analiz ediliyor...", "İptal", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        progress.setValue(20)

        con = db.get_conn()
        try:
            from utils import ai_recommend

            # 1. Kapsamlı Öğrenci Analitiği Çek
            analytics = ai_recommend.get_comprehensive_student_analytics(con, oid)
            self.analytics_data = analytics
            progress.setValue(50)

            # 2. KPI Kartlarını Güncelle
            ratio = analytics["overall"]["completion_ratio"]
            done = analytics["overall"]["completed_count"]
            total = analytics["overall"]["total_assigned"]
            overdue = analytics["overall"]["overdue_count"]
            ebbinghaus_cnt = len(analytics["ebbinghaus_reviews"])
            gaps_cnt = len(analytics["curriculum_gaps"])

            self.card_success.findChild(QLabel, "kpi_main").setText(f"%{ratio}")
            self.card_success.findChild(QLabel, "kpi_sub").setText(f"{done}/{total} Ödev Tamamlandı")

            self.card_overdue.findChild(QLabel, "kpi_main").setText(f"{overdue} Ödev")
            self.card_overdue.findChild(QLabel, "kpi_sub").setText("Acil Telafi Bekliyor" if overdue > 0 else "Gecikmiş Ödev Yok")

            self.card_ebbinghaus.findChild(QLabel, "kpi_main").setText(f"{ebbinghaus_cnt} Konu")
            self.card_ebbinghaus.findChild(QLabel, "kpi_sub").setText("Hafıza Tazeleyici" if ebbinghaus_cnt > 0 else "Tekrar Eşiği Temiz")

            self.card_exam.findChild(QLabel, "kpi_main").setText(f"{gaps_cnt} Konu")
            self.card_exam.findChild(QLabel, "kpi_sub").setText("ÖSYM/LGS Yüksek Ağırlık")

            # 3. Sol Panel Profil ve İlerleme Çubukları
            self.lblProfileBadge.setText(f"🎯 Profil: {analytics['cognitive_profile']}")
            self._update_lesson_progress_bars(analytics["lesson_stats"])
            progress.setValue(70)

            # 4. Akıllı Ödev Önerilerini Üret
            mode_map = {
                0: "balanced",
                1: "remedial",
                2: "ebbinghaus",
                3: "exam_focus",
                4: "curriculum",
            }
            curr_mode = mode_map.get(self.cmbStrategyMode.currentIndex(), "balanced")
            tgt_min = self.spTargetMinutes.value()

            suggestions = ai_recommend.generate_smart_homework_suggestions(
                con, oid,
                available_books=self.available_books,
                mode=curr_mode,
                target_minutes=tgt_min,
                limit=14
            )
            self.suggested_tasks = suggestions
            self.filtered_tasks = list(suggestions)
            self._fill_table()
            progress.setValue(85)

            # 5. Haftalık Plan ve PDR Raporunu Üret
            self._generate_weekly_plan(silent=True)
            self._generate_pdr_report()
            progress.setValue(100)

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Analiz Hatası", f"Analiz sırasında bir hata oluştu:\n{e}")
        finally:
            con.close()
            progress.setValue(100)

    def _update_lesson_progress_bars(self, lesson_stats: Dict[str, Any]):
        # Mevcut barları temizle
        while self.lay_lessons_bars.count() > 1:
            child = self.lay_lessons_bars.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for d_key, data in lesson_stats.items():
            box = QWidget()
            b_lay = QVBoxLayout(box)
            b_lay.setContentsMargins(0, 2, 0, 2)
            b_lay.setSpacing(2)

            h_lbl = QHBoxLayout()
            lbl_name = QLabel(data["name"])
            lbl_name.setStyleSheet("font-size: 11px; font-weight: 600; color: #334155;")
            lbl_pct = QLabel(f"%{data['ratio']} ({data['done']}/{data['total']})")
            lbl_pct.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {data['color']};")
            h_lbl.addWidget(lbl_name)
            h_lbl.addStretch(1)
            h_lbl.addWidget(lbl_pct)
            b_lay.addLayout(h_lbl)

            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(data["ratio"])
            pbar.setTextVisible(False)
            pbar.setFixedHeight(6)
            pbar.setStyleSheet(f"""
                QProgressBar {{ background-color: #e2e8f0; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {data['color']}; border-radius: 3px; }}
            """)
            b_lay.addWidget(pbar)

            self.lay_lessons_bars.insertWidget(self.lay_lessons_bars.count() - 1, box)

    def _fill_table(self):
        self.tableSuggestions.setRowCount(0)
        for i, task in enumerate(self.filtered_tasks):
            self.tableSuggestions.insertRow(i)

            # 0: Badge (Öncelik & Tür)
            badge_text = task.get("badge") or "📌 Öneri"
            badge_col = task.get("badge_color") or "#4338ca"
            lbl_badge = QLabel(f" {badge_text} ")
            lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_badge.setStyleSheet(f"""
                background-color: {badge_col}15;
                color: {badge_col};
                border: 1px solid {badge_col}40;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 6px;
            """)
            self.tableSuggestions.setCellWidget(i, 0, lbl_badge)

            # 1: Ders
            d_name = task.get("ders", "-").replace("_", " ").title()
            it_ders = QTableWidgetItem(d_name)
            it_ders.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tableSuggestions.setItem(i, 1, it_ders)

            # 2: Kitap
            it_kitap = QTableWidgetItem(task.get("kitap", "-"))
            self.tableSuggestions.setItem(i, 2, it_kitap)

            # 3: Konu
            it_konu = QTableWidgetItem(task.get("konu", "-"))
            it_konu.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tableSuggestions.setItem(i, 3, it_konu)

            # 4: Hedef Yük
            dk = task.get("dk", 30)
            soru = task.get("soru", 20)
            it_load = QTableWidgetItem(f"🎯 ~{soru} Soru • ⏱️ {dk} dk")
            it_load.setForeground(QColor("#059669"))
            self.tableSuggestions.setItem(i, 4, it_load)

            # 5: Bilimsel Gerekçe & Detay
            reason = task.get("reason") or task.get("explain") or task.get("aciklama", "")
            it_reason = QTableWidgetItem(str(reason))
            it_reason.setToolTip(str(reason))
            self.tableSuggestions.setItem(i, 5, it_reason)

            # 6: Checkbox
            chk = QCheckBox()
            chk.setChecked(True)
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.addWidget(chk)
            self.tableSuggestions.setCellWidget(i, 6, w)
            w.chk = chk
            chk.stateChanged.connect(self._update_summary)

        self.tableSuggestions.resizeColumnsToContents()
        h = self.tableSuggestions.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.tableSuggestions.setColumnWidth(6, 45)

        self._update_summary()

    def _update_summary(self):
        count = 0
        total_min = 0
        total_q = 0
        for i in range(self.tableSuggestions.rowCount()):
            w = self.tableSuggestions.cellWidget(i, 6)
            if w and hasattr(w, 'chk') and w.chk.isChecked():
                count += 1
                if i < len(self.filtered_tasks):
                    task = self.filtered_tasks[i]
                    total_min += int(task.get('dk', 30) or 30)
                    total_q += int(task.get('soru', 20) or 20)

        saat = total_min // 60
        dk_mod = total_min % 60
        time_str = f"{total_min} dk"
        if saat > 0:
            time_str = f"{saat} sa {dk_mod} dk ({total_min} dk)"

        # Bilişsel Yük Seviyesi
        if total_min <= 180:
            load_txt = "🟢 Bilişsel Yük: İdeal & Dengeli"
            c_code = "#059669"
        elif total_min <= 300:
            load_txt = "🟡 Bilişsel Yük: Yoğun (Mola Tavsiye Edilir)"
            c_code = "#d97706"
        else:
            load_txt = "🔴 Bilişsel Yük: Aşırı (Öğrenciyi Yormayacak Şekilde Yayın)"
            c_code = "#dc2626"

        self.lblLiveSummary.setText(f"Seçilen: {count} Ödev (~{time_str}, ~{total_q} Soru) | {load_txt}")
        self.lblLiveSummary.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {c_code};")

    def _set_category_filter(self, cat: str):
        self.current_filter_category = cat
        # Buton stillerini güncelle
        self.btnFilterAll.setChecked(cat == "all")
        self.btnFilterRemedial.setChecked(cat == "remedial")
        self.btnFilterEbbinghaus.setChecked(cat == "ebbinghaus")
        self.btnFilterExam.setChecked(cat == "exam")
        self.btnFilterCurriculum.setChecked(cat == "curriculum")
        self._filter_table_items()

    def _filter_table_items(self):
        search_txt = self.txtSearch.text().strip().lower()
        cat = self.current_filter_category

        filtered = []
        for t in self.suggested_tasks:
            # Kategori kontrolü
            t_type = t.get("type", "")
            if cat == "remedial" and t_type != "remedial":
                continue
            if cat == "ebbinghaus" and t_type != "ebbinghaus":
                continue
            if cat == "exam" and "🔥" not in (t.get("badge") or ""):
                continue
            if cat == "curriculum" and t_type != "curriculum":
                continue

            # Arama kontrolü
            if search_txt:
                d = t.get("ders", "").lower()
                k = t.get("konu", "").lower()
                b = t.get("kitap", "").lower()
                r = str(t.get("reason", "")).lower()
                if search_txt not in d and search_txt not in k and search_txt not in b and search_txt not in r:
                    continue

            filtered.append(t)

        self.filtered_tasks = filtered
        self._fill_table()

    def _toggle_selection(self):
        if self.tableSuggestions.rowCount() == 0:
            return
        w = self.tableSuggestions.cellWidget(0, 6)
        tgt = not w.chk.isChecked() if w else True
        for i in range(self.tableSuggestions.rowCount()):
            w = self.tableSuggestions.cellWidget(i, 6)
            if w:
                w.chk.setChecked(tgt)

    def _on_strategy_mode_changed(self, idx):
        self._run_analysis()

    def _on_target_minutes_changed(self, val):
        self._run_analysis()

    def _accept_selection(self):
        final_list = []
        for i in range(self.tableSuggestions.rowCount()):
            w = self.tableSuggestions.cellWidget(i, 6)
            if w and w.chk.isChecked() and i < len(self.filtered_tasks):
                final_list.append(self.filtered_tasks[i])

        if not final_list:
            QMessageBox.information(self, "Seçim Yapılmadı", "Lütfen listeye eklemek için en az bir ödev seçiniz.")
            return

        self.selected_homeworks = final_list
        self.accept()

    def _generate_weekly_plan(self, silent=False):
        oid = self._get_current_oid()
        if not oid:
            return

        con = db.get_conn()
        try:
            from utils import ai_recommend
            plan = ai_recommend.weekly_strategy_plan(con, oid, available_books=self.available_books)
            self.weekly_plan_data = plan

            days_tr = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
            html = """
            <style>
                body { font-family: 'Segoe UI', Tahoma, sans-serif; color: #1e293b; margin: 10px; }
                .day-card { border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 12px; background: white; overflow: hidden; }
                .day-header { background: #f1f5f9; padding: 8px 14px; font-weight: bold; border-bottom: 1px solid #e2e8f0; display: flex; }
                .day-title { font-size: 14px; color: #334155; }
                .day-badge { float: right; background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 10px; font-size: 11px; }
                .task-row { padding: 8px 14px; border-bottom: 1px solid #f8fafc; font-size: 12px; }
                .task-row:last-child { border-bottom: none; }
                .badge-task { background: #dcfce7; color: #15803d; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 10px; margin-right: 6px; }
            </style>
            """

            schedule = plan.get("schedule", [])
            for day in schedule:
                d_str = day.get("date", "")
                try:
                    dt = datetime.strptime(d_str, "%Y-%m-%d")
                    d_name = days_tr[dt.weekday()]
                except Exception:
                    d_name = d_str

                items = day.get("items", [])
                tot_dk = sum(it.get("dk", 30) for it in items)

                html += f"""
                <div class="day-card">
                    <div class="day-header">
                        <span class="day-title">📅 {d_name} <small style="color:#64748b;">({d_str})</small></span>
                        <span class="day-badge">{tot_dk} dk Hedef</span>
                    </div>
                """
                if not items:
                    html += "<div style='padding: 10px 14px; color: #94a3b8; font-style: italic;'>Bu gün için planlanan özel çalışma yok (Dinlenme & Genel Tekrar).</div>"
                else:
                    for it in items:
                        ders = it.get("ders", "").replace("_", " ").title()
                        konu = it.get("konu", "")
                        dk = it.get("dk", 30)
                        neden = it.get("neden", "")
                        html += f"""
                        <div class="task-row">
                            <span class="badge-task">⏱️ {dk} dk</span>
                            <b>{ders}:</b> {konu} — <span style="color: #64748b; font-style: italic;">{neden}</span>
                        </div>
                        """
                html += "</div>"

            self.txtStrategy.setHtml(html)
        except Exception as e:
            if not silent:
                self.txtStrategy.setText(f"Plan üretilirken hata oluştu: {e}")
        finally:
            con.close()

    def _generate_pdr_report(self):
        oid = self._get_current_oid()
        if not oid:
            return

        con = db.get_conn()
        try:
            from utils import ai_recommend
            pdr = ai_recommend.generate_pedagogical_pdr_report(con, oid)
            
            # HTML formatında PDR Raporu
            html_pdr = f"""
            <div style="line-height: 1.6; color: #334155;">
                <h3 style="color: #4338ca; margin-top: 0;">🎓 PDR & Koçluk Analiz Özeti</h3>
                <p>{pdr['summary']}</p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 12px 0;">
                <h4 style="color: #059669; margin-bottom: 4px;">🚀 Güçlü Olduğu Alanlar:</h4>
                <p>{", ".join(pdr['strong_lessons']) if pdr['strong_lessons'] else "Tüm branşlarda dengeli ilerleme sergileniyor."}</p>
                <h4 style="color: #dc2626; margin-bottom: 4px;">⚠️ Dikkat ve Telafi Gerektiren Alanlar:</h4>
                <p>{", ".join(pdr['weak_lessons']) if pdr['weak_lessons'] else "Kritik bir eksiklik saptanmadı, form korumaya devam edilmeli."}</p>
                <h4 style="color: #7c3aed; margin-bottom: 4px;">🧠 Çalışma Disiplini ve Ebbinghaus Tavsiyesi:</h4>
                <p>Öğrencinin çalıştığı konuları kalıcı hafızaya aktarması için 7. ve 30. gün hatırlatma testleri kritik önem taşımaktadır. Günlük çalışma blokları 40 dakika odaklanma + 10 dakika mola periyotlarıyla yürütülmelidir.</p>
            </div>
            """
            self.txtPdrSummary.setHtml(html_pdr)
            self.txtWaStudent.setPlainText(pdr["whatsapp_student"])
            self.txtWaParent.setPlainText(pdr["whatsapp_parent"])
        except Exception as e:
            self.txtPdrSummary.setText(f"PDR raporu üretilemedi: {e}")
        finally:
            con.close()

    def _copy_to_clipboard(self, text: str, msg: str = "Panoya kopyalandı ✅"):
        cb = QApplication.clipboard()
        cb.setText(text)
        QMessageBox.information(self, "Kopyalandı", msg)

    def _copy_suggestions_text(self):
        lines = ["📌 *Akıllı Ödev Sihirbazı - Seçilen Ödevler*\n"]
        for t in self.filtered_tasks:
            d = t.get("ders", "").replace("_", " ").title()
            k = t.get("konu", "")
            b = t.get("kitap", "")
            dk = t.get("dk", 30)
            soru = t.get("soru", 20)
            r = t.get("reason", "")
            lines.append(f"• *{d}* ({b}): {k} | ~{soru} Soru ({dk} dk)\n  ↳ _{r}_")
        self._copy_to_clipboard("\n".join(lines), "Ödev listesi panoya kopyalandı ✅")

    def _copy_plan_text(self):
        if self.weekly_plan_data:
            txt = self.txtStrategy.toPlainText()
            self._copy_to_clipboard(txt, "Haftalık plan metni kopyalandı ✅")

    def _print_preview(self):
        from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        from PyQt6.QtGui import QTextDocument, QPageSize

        student_name = self.cmbStudent.currentText()
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 30px; color: #1e293b; }}
                h1 {{ color: #4338ca; border-bottom: 2px solid #4338ca; padding-bottom: 8px; font-size: 20pt; }}
                .kpi-box {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 10pt; }}
                th {{ background-color: #4338ca; color: white; padding: 8px; text-align: left; border: 1px solid #3730a3; }}
                td {{ padding: 8px; border: 1px solid #cbd5e1; vertical-align: top; }}
                tr:nth-child(even) {{ background-color: #f8fafc; }}
                .footer {{ margin-top: 30px; font-size: 9pt; color: #64748b; text-align: right; border-top: 1px solid #e2e8f0; padding-top: 8px; }}
            </style>
        </head>
        <body>
            <h1>Ödev & Başarı Raporu: {student_name}</h1>
            <div class="kpi-box">
                <b>Pedagojik Profil:</b> {self.lblProfileBadge.text()}<br>
                <b>Durum Özeti:</b> {self.lblLiveSummary.text()}
            </div>
            <h3>📌 Önerilen Çalışma & Telafi Listesi</h3>
            <table>
                <thead>
                    <tr>
                        <th width="15%">Tür</th>
                        <th width="18%">Ders</th>
                        <th width="20%">Kitap</th>
                        <th width="22%">Konu</th>
                        <th width="10%">Hedef</th>
                        <th width="15%">Açıklama</th>
                    </tr>
                </thead>
                <tbody>
        """
        for t in self.filtered_tasks:
            badge = t.get("badge", "")
            ders = t.get("ders", "").replace("_", " ").title()
            kitap = t.get("kitap", "")
            konu = t.get("konu", "")
            dk = t.get("dk", 30)
            soru = t.get("soru", 20)
            reason = t.get("reason", "")
            html += f"""
                <tr>
                    <td><b>{badge}</b></td>
                    <td>{ders}</td>
                    <td>{kitap}</td>
                    <td>{konu}</td>
                    <td>{soru} Soru ({dk} dk)</td>
                    <td>{reason}</td>
                </tr>
            """
        html += f"""
                </tbody>
            </table>
            <div class="footer">Rapor Tarihi: {now_str} | Akıllı Ödev ve Başarı Sihirbazı v3.0 Pro</div>
        </body>
        </html>
        """

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        try:
            from PyQt6.QtCore import QMarginsF
            from PyQt6.QtGui import QPageLayout
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            layout = QPageLayout(printer.pageLayout())
            layout.setMargins(QMarginsF(12.0, 12.0, 12.0, 12.0))
            printer.setPageLayout(layout)
        except Exception:
            pass

        preview = QPrintPreviewDialog(printer, self)
        preview.setMinimumSize(1100, 850)

        def handle_print(p):
            doc = QTextDocument()
            doc.setHtml(html)
            try:
                doc.setPageSize(p.pageRect(QPrinter.Unit.Point).size())
            except Exception:
                pass
            doc.print(p)

        preview.paintRequested.connect(handle_print)
        preview.exec()
