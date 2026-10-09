# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QTabWidget, QWidget, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt

class CoachDetailDialog(QDialog):
    def __init__(self, topic_name, topic_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Koç Modu: {topic_name}")
        self.setFixedSize(600, 600)
        self.topic_data = topic_data
        self._setup_ui(topic_name)

    def _setup_ui(self, topic_name):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Header
        lbl_title = QLabel(topic_name)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e3a8a;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)
        
        # Stats Row
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #f1f5f9; border-radius: 6px; padding: 10px;")
        sl = QHBoxLayout(stats_frame)
        
        imp = self.topic_data.get("importance", "Belirsiz")
        qs = self.topic_data.get("questions", "-")
        # Ensure we handle simple string vs richer format if necessary, though populate_knowledge ensures strings
        sl.addWidget(QLabel(f"<b>📌 Önem Düzeyi:</b> {imp}"))
        sl.addStretch()
        sl.addWidget(QLabel(f"<b>❓ Tahmini Soru:</b> {qs}"))
        layout.addWidget(stats_frame)
        
        # Main Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 4px; }
            QTabBar::tab { background: #f8fafc; padding: 8px 12px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #ffffff; border: 1px solid #e2e8f0; border-bottom: none; font-weight: bold; color: #2563eb; }
        """)
        
        layout.addWidget(tabs)
        
        # 1. Genel Bakış (Overview)
        tab_overview = QWidget()
        self._init_overview(tab_overview)
        tabs.addTab(tab_overview, "Genel Bakış")
        
        # 2. Çalışma Modları (Study Variants)
        tab_variants = QWidget()
        self._init_variants(tab_variants)
        tabs.addTab(tab_variants, "Çalışma Modları")
        
        # 3. Koç Listesi (Checklist)
        tab_checklist = QWidget()
        self._init_checklist(tab_checklist)
        tabs.addTab(tab_checklist, "Kontrol Listesi")
        
        # 4. Tekrar (Spaced Repetition)
        tab_repetition = QWidget()
        self._init_repetition(tab_repetition)
        tabs.addTab(tab_repetition, "Tekrar Takvimi")

        # Close
        btn_close = QPushButton("Kapat")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; border-radius: 6px; font-weight: bold; padding: 8px; }
            QPushButton:hover { background-color: #dc2626; }
        """)
        layout.addWidget(btn_close)

    def _init_overview(self, parent):
        l = QVBoxLayout(parent)
        l.setSpacing(15)
        
        # Tip
        tip = self.topic_data.get("tip", "")
        if tip:
            lbl = QLabel(f"💡 <b>Koç İpucu:</b> {tip}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("background: #fef9c3; color: #854d0e; padding: 12px; border-radius: 6px; border: 1px solid #fde047;")
            l.addWidget(lbl)
            
        # Mistakes
        mistakes = self.topic_data.get("common_mistakes", [])
        if mistakes:
            l.addWidget(QLabel("<b>⚠️ Sık Yapılan Hatalar:</b>"))
            lst = QListWidget()
            lst.addItems(mistakes)
            lst.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc;")
            lst.setFixedHeight(100)
            l.addWidget(lst)

        # Formulas
        formulas = self.topic_data.get("mini_formulas", [])
        if formulas:
            l.addWidget(QLabel("<b>📐 Kritik Formüller:</b>"))
            list_w = QListWidget()
            list_w.addItems(formulas)
            list_w.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc;")
            list_w.setFixedHeight(100)
            l.addWidget(list_w)
            
        l.addStretch()
            
    def _init_variants(self, parent):
        l = QVBoxLayout(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(15)
        
        variants = self.topic_data.get("study_variants", [])
        if not variants:
            cl.addWidget(QLabel("Özel çalışma modu bulunamadı."))
        
        for v in variants:
            frame = QFrame()
            frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px;")
            fl = QVBoxLayout(frame)
            
            # Header
            name = v.get("name", "Varyant")
            mins = v.get("minutes", 0)
            goal = v.get("goal", "")
            
            head_lbl = QLabel(f"<span style='font-size:14px; color:#1e40af;'><b>{name}</b></span> <span style='color:#64748b;'>({mins} dk)</span>")
            fl.addWidget(head_lbl)
            
            if goal:
                fl.addWidget(QLabel(f"<i>Hedef: {goal}</i>"))
            
            # Steps
            steps = v.get("steps", [])
            if steps:
                step_txt = "<ul style='margin-top:5px; padding-left:20px;'>" + "".join([f"<li>{s}</li>" for s in steps]) + "</ul>"
                fl.addWidget(QLabel(step_txt))
                
            cl.addWidget(frame)
            
        cl.addStretch()
        scroll.setWidget(content)
        l.addWidget(scroll)

    def _init_checklist(self, parent):
        l = QVBoxLayout(parent)
        checklist = self.topic_data.get("coach_checklist", [])
        
        if not checklist:
            l.addWidget(QLabel("Özel bir kontrol listesi yok."))
            l.addStretch()
            return
        
        l.addWidget(QLabel("<i>Konuyu tam anlamak için bunları tamamla:</i>"))
        
        lst = QListWidget()
        for item in checklist:
            lst.addItem(f"✅ {item}")
        lst.setStyleSheet("font-size: 13px; spacing: 4px;")
        l.addWidget(lst)

    def _init_repetition(self, parent):
        l = QVBoxLayout(parent)
        rep = self.topic_data.get("spaced_repetition", [])
        
        if not rep:
            l.addWidget(QLabel("Tekrar programı yok."))
            l.addStretch()
            return

        l.addWidget(QLabel("<i>Unutmayı önlemek için tekrar takvimi:</i>"))
        
        # Table-like structure using Grid or Vertical
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        content = QWidget()
        cl = QVBoxLayout(content)
        
        for r in rep:
            day = r.get("day_offset", 0)
            task = r.get("task", "")
            
            row = QFrame()
            row.setStyleSheet("background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; margin-bottom: 5px;")
            rl = QHBoxLayout(row)
            rl.addWidget(QLabel(f"<b>+{day}. Gün</b>"))
            rl.addWidget(QLabel(task))
            cl.addWidget(row)
            
        cl.addStretch()
        scroll.setWidget(content)
        l.addWidget(scroll)
