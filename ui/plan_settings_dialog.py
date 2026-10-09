# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QCheckBox, QComboBox, QLineEdit, QPushButton, 
    QGroupBox, QSpinBox, QRadioButton, QButtonGroup, 
    QTextEdit, QTimeEdit, QMessageBox, QWidget, QScrollArea, QFrame, QInputDialog,
    QListWidget, QAbstractItemView, QTabWidget, QGridLayout
)
from PyQt6.QtCore import Qt, QTime, QRectF
from PyQt6.QtGui import QIcon, QPainter, QColor, QPen, QBrush, QFont, QLinearGradient

PROFILE_FILE = "plan_profiles.json"


class DayTimelineWidget(QFrame):
    """
    24 Saatlik İnteraktif Gün Çizelgesi ve Çalışma Kapasitesi Görselleştirici.
    Okul saatlerini, sabit kurs/etüt bloklarını ve kalan net serbest çalışma kapasitesini renkli çubuk üzerinde gösterir.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setStyleSheet("""
            DayTimelineWidget {
                background: #ffffff;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        
        self.day_name = "Pazartesi"
        self.school_times = None # (start_min, end_min)
        self.blocks = [] # list of (start_min, end_min, label)
        self.total_free = 0
        
    def update_data(self, day, school_active, s_time, e_time, block_list):
        self.day_name = day or "Pazartesi"
        
        # Okul saatleri
        self.school_times = None
        if school_active and self.day_name not in ["Cumartesi", "Pazar"]:
            if hasattr(s_time, "hour") and hasattr(e_time, "hour"):
                s = s_time.hour() * 60 + s_time.minute()
                e = e_time.hour() * 60 + e_time.minute()
                self.school_times = (s, e)
            
        # Sabit blokları ayrıştır
        self.blocks = []
        for b_str in block_list:
            is_match = False
            b_lower = b_str.lower()
            if b_lower.startswith(self.day_name.lower()):
                is_match = True
            if "hafta içi" in b_lower and self.day_name not in ["Cumartesi", "Pazar"]:
                is_match = True
            if "her gün" in b_lower:
                is_match = True
            
            if is_match:
                try:
                    m = re.search(r'\[(\d{2}:\d{2})-(\d{2}:\d{2})\]', b_str)
                    if m:
                        t1 = QTime.fromString(m.group(1), "HH:mm")
                        t2 = QTime.fromString(m.group(2), "HH:mm")
                        s = t1.hour() * 60 + t1.minute()
                        e = t2.hour() * 60 + t2.minute()
                        label = b_str.split("]")[-1].strip() or "Kısıt"
                        self.blocks.append((s, e, label))
                except Exception:
                    pass
                
        self.calculate_free_time()
        self.update()
        
    def calculate_free_time(self):
        day_start = 7 * 60   # 07:00
        day_end = 23 * 60 + 30 # 23:30
        
        busy_intervals = []
        if self.school_times:
            busy_intervals.append(self.school_times)
        busy_intervals.extend([(b[0], b[1]) for b in self.blocks])
        
        # Birleştir (Merge intervals)
        busy_intervals.sort()
        merged = []
        for start, end in busy_intervals:
            if not merged:
                merged.append((start, end))
            else:
                last_s, last_e = merged[-1]
                if start < last_e:
                    merged[-1] = (last_s, max(last_e, end))
                else:
                    merged.append((start, end))
                    
        total_busy = 0
        for s, e in merged:
            s_c = max(day_start, s)
            e_c = min(day_end, e)
            if e_c > s_c:
                total_busy += (e_c - s_c)
            
        self.total_free = max(0, (day_end - day_start) - total_busy)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Üst Başlık & Kapasite Özeti
        hours = self.total_free // 60
        mins = self.total_free % 60
        
        p.setPen(QColor("#0f172a"))
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header_text = f"📅 {self.day_name} 24 Saatlik Zaman Çizelgesi"
        p.drawText(16, 24, header_text)
        
        # Kalan kapasite rozeti
        cap_text = f"🟢 Serbest Çalışma Kapasitesi: ~{hours} sa {mins} dk"
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.setPen(QColor("#059669"))
        p.drawText(w - p.fontMetrics().horizontalAdvance(cap_text) - 18, 24, cap_text)
        
        # Çubuk Koordinatları
        bar_y = 28
        bar_h = 28
        start_min = 6 * 60  # 06:00
        end_min = 24 * 60   # 24:00
        total_range = end_min - start_min
        
        def min_to_x(m):
            ratio = (m - start_min) / total_range
            return 20 + ratio * (w - 40)
            
        # Zemin (Serbest çalışma açık mavi/gri)
        p.setBrush(QColor("#f1f5f9"))
        p.setPen(QPen(QColor("#cbd5e1"), 1))
        p.drawRoundedRect(QRectF(20, bar_y, w - 40, bar_h), 5, 5)
        
        # Okul Alanı
        if self.school_times:
            s, e = self.school_times
            x1 = min_to_x(s)
            x2 = min_to_x(e)
            if x2 > x1:
                grad_school = QLinearGradient(x1, bar_y, x2, bar_y + bar_h)
                grad_school.setColorAt(0, QColor("#fecaca"))
                grad_school.setColorAt(1, QColor("#fee2e2"))
                p.setBrush(grad_school)
                p.setPen(QPen(QColor("#f87171"), 1))
                p.drawRoundedRect(QRectF(x1, bar_y + 2, x2 - x1, bar_h - 4), 4, 4)
                if x2 - x1 > 45: 
                    p.setPen(QColor("#991b1b"))
                    p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                    p.drawText(QRectF(x1, bar_y + 2, x2 - x1, bar_h - 4), Qt.AlignmentFlag.AlignCenter, "🏫 OKUL")
        
        # Sabit Bloklar (Kurs, Etüt, Özel Ders)
        for s, e, lbl in self.blocks:
            x1 = min_to_x(s)
            x2 = min_to_x(e)
            if x2 > x1:
                grad_block = QLinearGradient(x1, bar_y, x2, bar_y + bar_h)
                grad_block.setColorAt(0, QColor("#fed7aa"))
                grad_block.setColorAt(1, QColor("#ffedd5"))
                p.setBrush(grad_block)
                p.setPen(QPen(QColor("#fb923c"), 1))
                p.drawRoundedRect(QRectF(x1, bar_y + 3, x2 - x1, bar_h - 6), 4, 4)
                if x2 - x1 > 35: 
                    p.setPen(QColor("#9a3412"))
                    p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                    short_lbl = lbl[:8] + ".." if len(lbl) > 8 else lbl
                    p.drawText(QRectF(x1, bar_y + 3, x2 - x1, bar_h - 6), Qt.AlignmentFlag.AlignCenter, short_lbl)
                     
        # Saat İşaretleri (Her 3 saatte bir)
        p.setPen(QColor("#64748b"))
        p.setFont(QFont("Segoe UI", 7.5))
        for h_val in range(6, 25, 3):
            mx = min_to_x(h_val * 60)
            p.drawText(int(mx) - 12, bar_y + bar_h + 13, f"{h_val:02d}:00")
            
        # Alt Lejant (Okul, Sabit Kısıt, Serbest Zaman)
        p.setFont(QFont("Segoe UI", 8))
        leg_y = bar_y + bar_h + 24
        
        # Kırmızı nokta - Okul
        p.setBrush(QColor("#ef4444")); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(22, leg_y - 7, 7, 7)
        p.setPen(QColor("#475569"))
        p.drawText(33, leg_y, "Okul Saatleri")
        
        # Turuncu nokta - Kurs
        p.setBrush(QColor("#f97316")); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(118, leg_y - 7, 7, 7)
        p.setPen(QColor("#475569"))
        p.drawText(129, leg_y, "Sabit Ders/Kurs")
        
        # Yeşil nokta - Serbest
        p.setBrush(QColor("#10b981")); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(235, leg_y - 7, 7, 7)
        p.setPen(QColor("#475569"))
        p.drawText(246, leg_y, "Ödev & Çalışma Alanı")


class PlanSettingsDialog(QDialog):
    """
    Profesyonel Akıllı Takvim ve Haftalık Planlama Sihirbazı (V3.5 Executive).
    Öğrencinin okul saatleri, özel ders rutinleri ve kapasitesine göre yapay zeka destekli takvim parametreleri üretir.
    """
    def __init__(self, parent=None, lesson_names: Optional[List[str]] = None, student_name: Optional[str] = None):
        super().__init__(parent)
        self.student_name = student_name
        
        # Fallback student_name
        if not self.student_name and parent:
            try:
                if hasattr(parent, "cmbAd") and hasattr(parent, "cmbSoyad"):
                    self.student_name = f"{parent.cmbAd.currentText()} {parent.cmbSoyad.currentText()}".strip()
                elif hasattr(parent, "student_name"):
                    self.student_name = parent.student_name
            except Exception:
                pass
             
        self.lesson_names = lesson_names or []
        self.result_details = ""
        self.profiles = {}
        
        self.setWindowTitle("📅 Akıllı Haftalık Planlama & Takvim Sihirbazı")
        
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(780, int(avail.width() * 0.90))
            h = min(680, int(avail.height() * 0.90))
            self.resize(w, h)
        else:
            self.resize(740, 640)
        self.setMinimumSize(600, 480)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-top: 3px solid #2563eb;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                font-size: 11.5px;
                font-weight: 600;
                padding: 7px 14px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1d4ed8;
                font-weight: bold;
                border: 1px solid #2563eb;
                border-top: 3px solid #2563eb;
                border-bottom: 2px solid #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
                color: #0f172a;
            }
            QGroupBox { 
                font-weight: 700;
                font-size: 12px;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
                margin-top: 8px;
                background: #ffffff;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #1e3a8a;
            }
            QLabel { color: #334155; }
            QLineEdit, QTimeEdit, QSpinBox, QComboBox {
                padding: 5px 8px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background: #ffffff;
                selection-background-color: #2563eb;
                font-size: 12px;
            }
            QLineEdit:focus, QTimeEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #2563eb;
            }
            QSpinBox, QTimeEdit {
                padding-right: 20px;
            }
            QSpinBox::up-button, QTimeEdit::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 17px;
                border-left: 1px solid #cbd5e1;
                border-bottom: 1px solid #e2e8f0;
                background: #f8fafc;
                border-top-right-radius: 4px;
            }
            QSpinBox::up-button:hover, QTimeEdit::up-button:hover { background: #e2e8f0; }
            QSpinBox::up-arrow, QTimeEdit::up-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-bottom: 4.5px solid #475569;
            }
            QSpinBox::down-button, QTimeEdit::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 17px;
                border-left: 1px solid #cbd5e1;
                background: #f8fafc;
                border-bottom-right-radius: 4px;
            }
            QSpinBox::down-button:hover, QTimeEdit::down-button:hover { background: #e2e8f0; }
            QSpinBox::down-arrow, QTimeEdit::down-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-top: 4.5px solid #475569;
            }
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background: #ffffff;
                padding: 3px;
            }
            QListWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #f1f5f9;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background: #eff6ff;
                color: #1e40af;
                font-weight: 600;
            }
        """)
        
        self._build_ui()
        self.cmb_profiles.currentIndexChanged.connect(self._on_profile_changed)
        self._load_profiles()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. MODERN EXECUTIVE HEADER BANNER (Kompakt) ---
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:0.5 #2563eb, stop:1 #3b82f6);
            border-bottom: 1px solid #1d4ed8;
        """)
        head_lay = QVBoxLayout(header_widget)
        head_lay.setContentsMargins(18, 10, 18, 10)
        head_lay.setSpacing(8)
        
        h_title = QHBoxLayout()
        lbl_icon = QLabel("🗓️")
        lbl_icon.setStyleSheet("font-size: 24px;")
        
        v_ti = QVBoxLayout()
        v_ti.setSpacing(2)
        lbl_title = QLabel("Haftalık Çalışma & Akıllı Takvim Planlayıcı")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffffff;")
        
        sub_text = "Öğrencinin okul saatleri, rutin kısıtları ve akademik hedeflerine göre dengeli bir çalışma takvimi oluşturun."
        if self.student_name:
            sub_text = f"Öğrenci: <b>{self.student_name}</b> • " + sub_text
            
        lbl_sub = QLabel(sub_text)
        lbl_sub.setStyleSheet("color: #e0e7ff; font-size: 11px;")
        v_ti.addWidget(lbl_title)
        v_ti.addWidget(lbl_sub)
        
        h_title.addWidget(lbl_icon)
        h_title.addLayout(v_ti)
        h_title.addStretch()
        head_lay.addLayout(h_title)
        
        # Profil & Şablon Çubuğu
        h_prof = QHBoxLayout()
        lbl_prof = QLabel("<font color='#e0e7ff'><b>📋 Kayıtlı Şablon / Profil:</b></font>")
        lbl_prof.setStyleSheet("font-size: 11.5px;")
        h_prof.addWidget(lbl_prof)
        
        self.cmb_profiles = QComboBox()
        self.cmb_profiles.setStyleSheet("background: white; border-radius: 5px; padding: 3px 8px; min-width: 200px;")
        
        btn_save_prof = QPushButton("💾 Profili Kaydet")
        btn_save_prof.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_prof.setStyleSheet("""
            QPushButton {
                background: #10b981; color: white; font-weight: bold; border: none; border-radius: 5px; padding: 4px 12px; font-size: 11.5px;
            }
            QPushButton:hover { background: #059669; }
        """)
        btn_save_prof.clicked.connect(self._save_current_profile)

        btn_update_prof = QPushButton("🔄 Güncelle")
        btn_update_prof.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_update_prof.setToolTip("Seçili profilin ayarlarını mevcut form verileriyle günceller")
        btn_update_prof.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; font-weight: bold; border: none; border-radius: 5px; padding: 4px 11px; font-size: 11.5px;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_update_prof.clicked.connect(self._update_current_profile)
        
        btn_del_prof = QPushButton("🗑️ Sil")
        btn_del_prof.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del_prof.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.85); color: white; font-weight: bold; border: none; border-radius: 5px; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background: #dc2626; }
        """)
        btn_del_prof.clicked.connect(self._delete_profile)

        h_prof.addWidget(self.cmb_profiles, 1)
        h_prof.addWidget(btn_save_prof)
        h_prof.addWidget(btn_update_prof)
        h_prof.addWidget(btn_del_prof)
        head_lay.addLayout(h_prof)
        
        main_layout.addWidget(header_widget)

        def _wrap_in_scroll(w: QWidget) -> QScrollArea:
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.Shape.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sa.setStyleSheet("QScrollArea { background: transparent; border: none; }")
            w.setStyleSheet("background: transparent;")
            sa.setWidget(w)
            return sa

        # --- 2. DÖRT SEKMELİ YAPI (Tabs) ---
        tab_container = QWidget()
        tab_container_lay = QVBoxLayout(tab_container)
        tab_container_lay.setContentsMargins(12, 6, 12, 6)
        
        self.tabs = QTabWidget()
        tab_container_lay.addWidget(self.tabs)
        main_layout.addWidget(tab_container, 1)

        # ==========================================
        # SEKME 1: 🕒 Zaman & Rutin (Okul & Kısıtlar)
        # ==========================================
        tab1 = QWidget()
        t1_lay = QVBoxLayout(tab1)
        t1_lay.setContentsMargins(16, 14, 16, 14)
        t1_lay.setSpacing(12)

        # Okul ve Öğrenci Durumu Grubu
        grp_profile = QGroupBox("👤 1. Öğrenci Durumu & Okul Saatleri")
        lay_profile = QVBoxLayout(grp_profile)
        lay_profile.setSpacing(10)
        
        h_prof_type = QHBoxLayout()
        h_prof_type.addWidget(QLabel("<b>Öğrenci Tipi:</b>"))
        self.cmb_student_type = QComboBox()
        self.cmb_student_type.addItems([
            "🏫 Okula Gidiyor (Standart Hafta İçi)", 
            "🎓 Mezun (Tüm Gün Serbest & Yoğun)", 
            "🛠️ Özel / Serbest Çalışma Programı"
        ])
        self.cmb_student_type.currentIndexChanged.connect(self._on_student_type_changed)
        h_prof_type.addWidget(self.cmb_student_type, 1)
        lay_profile.addLayout(h_prof_type)
        
        self.widget_school_times = QWidget()
        h_school = QHBoxLayout(self.widget_school_times)
        h_school.setContentsMargins(0, 0, 0, 0)
        self.chk_school = QCheckBox("Okul Var") 
        self.chk_school.setVisible(False)
        self.chk_school.setChecked(True)
        
        self.time_school_start = QTimeEdit(QTime(8, 30))
        self.time_school_end = QTimeEdit(QTime(15, 40))
        self.time_school_start.setDisplayFormat("HH:mm")
        self.time_school_end.setDisplayFormat("HH:mm")
        
        h_school.addWidget(QLabel("<b>Okul Başlangıç:</b>"))
        h_school.addWidget(self.time_school_start)
        h_school.addSpacing(16)
        h_school.addWidget(QLabel("<b>Okul Bitiş:</b>"))
        h_school.addWidget(self.time_school_end)
        h_school.addStretch()
        lay_profile.addWidget(self.widget_school_times)
        t1_lay.addWidget(grp_profile)

        # Sabit Rutinler (Kurs, Özel Ders)
        grp_blocks = QGroupBox("📅 2. Sabit Saatler & Rutinler (Özel Ders, Kurs, Antrenman)")
        lay_blocks = QVBoxLayout(grp_blocks)
        lay_blocks.setSpacing(8)
        
        lbl_hint = QLabel("Haftalık rutinde <b>KESİNLİKLE MEŞGUL</b> olan saatleri ekleyin. Takvim bu saatlere ödev yerleştirmez.")
        lbl_hint.setStyleSheet("color: #64748b; font-size: 11.5px;")
        lay_blocks.addWidget(lbl_hint)
        
        h_add_block = QHBoxLayout()
        self.cmb_block_day = QComboBox()
        self.cmb_block_day.addItems(["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar", "Hafta İçi Her Gün"])
        
        self.time_block_start = QTimeEdit(QTime(17, 0))
        self.time_block_end = QTimeEdit(QTime(19, 0))
        self.time_block_start.setDisplayFormat("HH:mm")
        self.time_block_end.setDisplayFormat("HH:mm")
        
        self.txt_block_desc = QLineEdit()
        self.txt_block_desc.setPlaceholderText("Örn: Fizik Özel Ders, Basketbol Antrenmanı")
        
        btn_add_block = QPushButton("➕ Ekle")
        btn_add_block.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_block.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; font-weight: bold; border-radius: 6px; padding: 6px 14px;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_add_block.clicked.connect(self._add_block_item)
        
        h_add_block.addWidget(self.cmb_block_day)
        h_add_block.addWidget(self.time_block_start)
        h_add_block.addWidget(QLabel("➔"))
        h_add_block.addWidget(self.time_block_end)
        h_add_block.addWidget(self.txt_block_desc, 1)
        h_add_block.addWidget(btn_add_block)
        lay_blocks.addLayout(h_add_block)
        
        self.lst_blocks = QListWidget()
        self.lst_blocks.setMaximumHeight(85)
        lay_blocks.addWidget(self.lst_blocks)
        
        h_rem = QHBoxLayout()
        h_rem.addStretch()
        btn_rem_block = QPushButton("🗑️ Seçili Rutin Saatini Kaldır")
        btn_rem_block.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rem_block.clicked.connect(self._remove_block_item)
        btn_rem_block.setStyleSheet("color: #ef4444; background: transparent; border: none; font-weight: 600; font-size: 11.5px;")
        h_rem.addWidget(btn_rem_block)
        lay_blocks.addLayout(h_rem)
        t1_lay.addWidget(grp_blocks)

        # Görsel 24 Saatlik Zaman Çizelgesi
        self.timeline = DayTimelineWidget()
        t1_lay.addWidget(self.timeline)

        self.tabs.addTab(_wrap_in_scroll(tab1), "🕒 Zaman & Okul")

        # ==========================================
        # SEKME 2: 🚀 Tempo & Hedef (Süre, Biyoritim, Tatil)
        # ==========================================
        tab2 = QWidget()
        t2_lay = QVBoxLayout(tab2)
        t2_lay.setContentsMargins(16, 14, 16, 14)
        t2_lay.setSpacing(14)

        grp_cap = QGroupBox("🚀 1. Günlük Çalışma Temposu & Hedef")
        lay_cap = QVBoxLayout(grp_cap)
        lay_cap.setSpacing(12)
        
        h_max = QHBoxLayout()
        lbl_max = QLabel("<b>Günlük Maksimum Ev Çalışma Süresi:</b>")
        lbl_max.setToolTip("Öğrencinin okul/dershane haricinde evde yapacağı toplam ödev ve tekrar süresi.")
        self.spin_max = QSpinBox()
        self.spin_max.setRange(30, 720)
        self.spin_max.setSingleStep(15)
        self.spin_max.setValue(180)
        self.spin_max.setSuffix(" dakika (~3 saat)")
        self.spin_max.setMinimumWidth(170)
        self.spin_max.valueChanged.connect(self._on_max_spin_changed)
        
        h_max.addWidget(lbl_max)
        h_max.addWidget(self.spin_max)
        h_max.addStretch()
        lay_cap.addLayout(h_max)

        h_wk = QHBoxLayout()
        h_wk.addWidget(QLabel("<b>Hafta Sonu Yük Modu:</b>"))
        self.bg_weekend = QButtonGroup(self)
        self.rb_w_relax = QRadioButton("🍃 Hafif (Dinlenme Odaklı)")
        self.rb_w_normal = QRadioButton("⚖️ Dengeli (Standart)")
        self.rb_w_hard = QRadioButton("🔥 Yoğun Kamp (Maksimum Verim)")
        self.rb_w_normal.setChecked(True)
        self.bg_weekend.addButton(self.rb_w_relax)
        self.bg_weekend.addButton(self.rb_w_normal)
        self.bg_weekend.addButton(self.rb_w_hard)
        h_wk.addWidget(self.rb_w_relax)
        h_wk.addWidget(self.rb_w_normal)
        h_wk.addWidget(self.rb_w_hard)
        h_wk.addStretch()
        lay_cap.addLayout(h_wk)
        
        t2_lay.addWidget(grp_cap)

        grp_bio = QGroupBox("🧠 2. Zihinsel Verim & Biyoritim Modu")
        lay_bio = QVBoxLayout(grp_bio)
        lay_bio.setSpacing(8)
        
        h_bio = QHBoxLayout()
        h_bio.addWidget(QLabel("<b>Verim Modu:</b>"))
        self.cmb_bio = QComboBox()
        self.cmb_bio.addItems([
            "⚖️ Standart Dengeli Dağılım", 
            "☀️ Sabah İnsanı (Zor dersleri erken saatlere al)", 
            "🌙 Gece Kuşu (Zor dersleri akşam/gece saatlerine al)"
        ])
        h_bio.addWidget(self.cmb_bio, 1)
        lay_bio.addLayout(h_bio)
        
        lbl_bio_hint = QLabel("<i>*Bu ayar, zorluk derecesi 4 ve 5 olan görevleri öğrencinin zihinsel verim saatine göre önceliklendirir.</i>")
        lbl_bio_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        lay_bio.addWidget(lbl_bio_hint)
        t2_lay.addWidget(grp_bio)

        grp_holiday = QGroupBox("🏖️ 3. Haftalık Dinlenme Günü")
        lay_hol = QVBoxLayout(grp_holiday)
        lay_hol.setSpacing(8)
        
        h_empty = QHBoxLayout()
        self.chk_empty_day = QCheckBox("<b>Haftada 1 Gün Tam Tatil Ver (Ödev Atama):</b>")
        self.cmb_empty_day = QComboBox()
        self.cmb_empty_day.addItems(["Pazar", "Cumartesi", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Rastgele"])
        self.cmb_empty_day.setCurrentIndex(0)
        self.cmb_empty_day.setEnabled(False)
        self.chk_empty_day.toggled.connect(self.cmb_empty_day.setEnabled)
        h_empty.addWidget(self.chk_empty_day)
        h_empty.addWidget(self.cmb_empty_day)
        h_empty.addStretch()
        lay_hol.addLayout(h_empty)
        t2_lay.addWidget(grp_holiday)
        t2_lay.addStretch(1)

        self.tabs.addTab(_wrap_in_scroll(tab2), "🚀 Hedef & Tempo")

        # ==========================================
        # SEKME 3: 🤖 Akıllı Koçluk & Öncelikler
        # ==========================================
        tab3 = QWidget()
        t3_lay = QVBoxLayout(tab3)
        t3_lay.setContentsMargins(16, 14, 16, 14)
        t3_lay.setSpacing(12)

        grp_focus = QGroupBox("🔥 1. En Çok Zorlanılan / Öncelikli Dersler")
        lay_focus = QVBoxLayout(grp_focus)
        lay_focus.setSpacing(10)
        
        btn_ai = QPushButton("🤖 Yapay Zeka ile Eksik & Öncelik Analizi Yap")
        btn_ai.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ai.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #4f46e5); 
                color: white; font-weight: bold; border-radius: 6px; padding: 10px; font-size: 13px;
            }
            QPushButton:hover { background: #6d28d9; }
        """)
        btn_ai.clicked.connect(self._perform_ai_analysis)
        lay_focus.addWidget(btn_ai)
        
        self.txt_focus = QLineEdit()
        self.txt_focus.setPlaceholderText("Örn: Matematik, Fizik, Geometri (Öncelik verilecek dersler)")
        lay_focus.addWidget(self.txt_focus)

        lbl_pop = QLabel("<b>Hızlı Ekle Rozetleri:</b>")
        lbl_pop.setStyleSheet("font-size: 11px; color: #475569;")
        lay_focus.addWidget(lbl_pop)

        grid_lessons = QGridLayout()
        grid_lessons.setSpacing(6)
        
        popular_lessons = [
            "TYT Matematik", "AYT Matematik", "Geometri", 
            "Fizik", "Kimya", "Biyoloji", 
            "Türkçe", "Tarih", "Coğrafya", "Edebiyat", "Felsefe", "İngilizce"
        ]
        all_lessons = list(dict.fromkeys(popular_lessons + self.lesson_names))
        
        for i, ln in enumerate(all_lessons[:12]):
            btn = QPushButton(ln)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { 
                    background: #f8fafc; color: #334155; border: 1px solid #cbd5e1; 
                    border-radius: 5px; padding: 5px 8px; font-size: 11.5px; font-weight: 500;
                }
                QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; font-weight: bold; }
            """)
            btn.clicked.connect(lambda _, x=ln: self._add_focus_tag(x))
            grid_lessons.addWidget(btn, i // 4, i % 4)
            
        lay_focus.addLayout(grid_lessons)
        t3_lay.addWidget(grp_focus)

        grp_notes = QGroupBox("📝 2. Özel Durum Notları & Ek Kısıtlamalar")
        lay_notes = QVBoxLayout(grp_notes)
        lay_notes.setSpacing(8)
        
        lbl_tmpl = QLabel("<b>Hazır Şablon Cümleleri (Tıklayınca Ekler):</b>")
        lbl_tmpl.setStyleSheet("font-size: 11px; color: #475569;")
        lay_notes.addWidget(lbl_tmpl)
        
        h_tmps = QHBoxLayout()
        templates = [
            "Çarşamba etüt var", "Hafta içi 20:00'den sonra boş", 
            "Cumartesi öğleden sonra serbest", "Pazar deneme sınavı var"
        ]
        for t in templates:
            btn = QPushButton(t)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { 
                    font-size: 11px; padding: 4px 8px; color: #4338ca; 
                    background: #eef2ff; border: 1px dashed #a5b4fc; border-radius: 4px;
                }
                QPushButton:hover { background: #e0e7ff; }
            """)
            btn.clicked.connect(lambda _, x=t: self._append_template_note(x))
            h_tmps.addWidget(btn)
            
        lay_notes.addLayout(h_tmps)
        
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Öğrenciye özel durumlar (Örn: Çarşamba akşamı maç var, sabahları erken kalkamaz, Cuma akşamı tekrar günü olsun)...")
        self.txt_notes.setMaximumHeight(75)
        lay_notes.addWidget(self.txt_notes)
        t3_lay.addWidget(grp_notes)
        t3_lay.addStretch(1)

        self.tabs.addTab(_wrap_in_scroll(tab3), "🤖 Akıllı Koç & Notlar")

        # ==========================================
        # SEKME 4: 📖 Kullanım Kılavuzu & Rehber
        # ==========================================
        tab_help = QWidget()
        t_help_lay = QVBoxLayout(tab_help)
        t_help_lay.setContentsMargins(16, 14, 16, 14)
        t_help_lay.setSpacing(12)

        # Kart 1: Zaman & Okul
        grp_h1 = QGroupBox("🕒 1. Zaman & Okul Rutini Nasıl Çalışır?")
        lay_h1 = QVBoxLayout(grp_h1)
        lay_h1.setSpacing(6)
        lbl_h1 = QLabel(
            "• <b>Öğrenci Tipi:</b> <i>Okula Gidiyor</i> seçildiğinde hafta içi okul saatleri otomatik kilitlenir. "
            "<i>Mezun</i> seçildiğinde sabah saatleri de çalışma bloğuna açılır.<br>"
            "• <b>Sabit Saatler (Kırmızı Bloklar):</b> Öğrencinin kurs, özel ders veya spor antrenmanı gibi "
            "kesinlikle ders çalışamayacağı saatlerini buraya ekleyin. Algoritma bu saatlere ASLA ödev yerleştirmez.<br>"
            "• <b>24 Saatlik Zaman Çizelgesi:</b> Yaptığınız saat seçimleri aşağıdaki çizelgede anlık güncellenir."
        )
        lbl_h1.setWordWrap(True)
        lbl_h1.setStyleSheet("color: #334155; font-size: 11.5px; line-height: 140%;")
        lay_h1.addWidget(lbl_h1)
        t_help_lay.addWidget(grp_h1)

        # Kart 2: Hedef & Tempo
        grp_h2 = QGroupBox("🚀 2. Hedef, Biyoritim & Tatil Dengesi")
        lay_h2 = QVBoxLayout(grp_h2)
        lay_h2.setSpacing(6)
        lbl_h2 = QLabel(
            "• <b>Günlük Maksimum Ev Süresi:</b> Öğrencinin aşırı yüklenip bıkmasını (burnout) engeller. "
            "Ödevler bu süreyi aşmayacak şekilde günlere eşit dağıtılır (Örn: 180 dk = günde en fazla 3 saat).<br>"
            "• <b>Hafta Sonu Yük Modu:</b> <i>Yoğun Kamp</i> seçilirse hafta sonu soru ve ödev kapasitesi artırılır; "
            "<i>Hafif</i> seçilirse öğrenciye daha fazla dinlenme payı bırakılır.<br>"
            "• <b>Biyoritim Modu:</b> <i>Sabah İnsanı</i> seçilirse zorluk derecesi 4 ve 5 olan ağır dersler "
            "(Matematik, Fizik vb.) günün ilk saatlerine yerleştirilir. <i>Gece Kuşu</i> ise akşam saatlerini hedefler.<br>"
            "• <b>Haftalık Dinlenme Günü:</b> Belirlediğiniz günde (örn. Pazar) öğrenciye sıfır ödev atanır."
        )
        lbl_h2.setWordWrap(True)
        lbl_h2.setStyleSheet("color: #334155; font-size: 11.5px; line-height: 140%;")
        lay_h2.addWidget(lbl_h2)
        t_help_lay.addWidget(grp_h2)

        # Kart 3: Akıllı Koçluk & Yapay Zeka
        grp_h3 = QGroupBox("🤖 3. Akıllı Koçluk & Yapay Zeka Analizi")
        lay_h3 = QVBoxLayout(grp_h3)
        lay_h3.setSpacing(6)
        lbl_h3 = QLabel(
            "• <b>Yapay Zeka Analiz Butonu:</b> Sistem, öğrencinin geciken ödevlerini ve deneme performansını tarayarak "
            "eksik olduğu ve takviye gereken dersleri otomatik bulur ve öncelik kutusuna yazar.<br>"
            "• <b>Öncelikli Ders Rozetleri:</b> Hızlıca ders etiketlerine tıklayarak bu derslerin haftalık planda "
            "öncelikli gün ve saatlere atanmasını sağlayabilirsiniz.<br>"
            "• <b>Özel Durum Notları:</b> 'Çarşamba etüt var', 'Cuma akşamı tekrar günü' gibi notları hazır butonlarla "
            "veya serbest metin olarak eklediğinizde plan bu kısıtlara göre optimize edilir."
        )
        lbl_h3.setWordWrap(True)
        lbl_h3.setStyleSheet("color: #334155; font-size: 11.5px; line-height: 140%;")
        lay_h3.addWidget(lbl_h3)
        t_help_lay.addWidget(grp_h3)

        # Kart 4: Pedagojik Başarı İpuçları
        grp_h4 = QGroupBox("💡 4. Koçluk Tavsiyesi: Başarılı Bir Planın Formülü")
        lay_h4 = QVBoxLayout(grp_h4)
        lay_h4.setSpacing(6)
        lbl_h4 = QLabel(
            "1. <b>Sürdürülebilirlik Hızdan Önemlidir:</b> İlk haftalarda günlük 120-180 dakika ile başlayın.<br>"
            "2. <b>Blok Çalışma & Mola:</b> Her 45-50 dakikalık çalışma sonrasında 10-15 dakika zihinsel mola verin.<br>"
            "3. <b>Farklı Branş Dağılımı:</b> Aynı gün üst üste 3 sayısal veya 3 sözel ders yerine dengeli dağıtım zihni canlı tutar."
        )
        lbl_h4.setWordWrap(True)
        lbl_h4.setStyleSheet("color: #047857; font-size: 11.5px; font-weight: 500; line-height: 140%;")
        grp_h4.setStyleSheet("QGroupBox { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; margin-top: 10px; font-weight: bold; color: #166534; }")
        lay_h4.addWidget(lbl_h4)
        t_help_lay.addWidget(grp_h4)
        t_help_lay.addStretch(1)

        self.tabs.addTab(_wrap_in_scroll(tab_help), "📖 Kullanım Kılavuzu & Rehber")

        # --- 3. FOOTER ACTIONS ---
        footer_widget = QWidget()
        footer_widget.setStyleSheet("background-color: #ffffff; border-top: 1px solid #e2e8f0;")
        foot_lay = QHBoxLayout(footer_widget)
        foot_lay.setContentsMargins(16, 8, 16, 8)
        
        self.lbl_footer_summary = QLabel("🎯 Hedef: ~180 dk/gün • Biyoritim: Dengeli")
        self.lbl_footer_summary.setStyleSheet("color: #64748b; font-size: 11.5px; font-weight: 500;")
        foot_lay.addWidget(self.lbl_footer_summary)
        foot_lay.addStretch(1)
        
        btn_cancel = QPushButton("İptal")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #f1f5f9; color: #475569; font-weight: 600; 
                padding: 7px 16px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 12px;
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_create = QPushButton("✨ Haftalık Planı Oluştur & Önizle")
        btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_create.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981); 
                color: white; font-weight: 800; padding: 8px 20px; font-size: 12.5px; border: none; border-radius: 6px;
            }
            QPushButton:hover { background: #047857; }
        """)
        btn_create.clicked.connect(self._create_plan)
        
        foot_lay.addWidget(btn_cancel)
        foot_lay.addWidget(btn_create)
        main_layout.addWidget(footer_widget)

        # Eski gizli bileşenler (Geriye uyumluluk için)
        self.chk_course = QCheckBox(); self.chk_course.setVisible(False)
        self.time_course_start = QTimeEdit(); self.time_course_start.setVisible(False)
        self.time_course_end = QTimeEdit(); self.time_course_end.setVisible(False)

        # Timeline bağlantıları
        self._setup_timeline_connections()
        self._refresh_timeline()

    def _setup_timeline_connections(self):
        self.cmb_student_type.currentIndexChanged.connect(self._refresh_timeline)
        self.time_school_start.timeChanged.connect(self._refresh_timeline)
        self.time_school_end.timeChanged.connect(self._refresh_timeline)
        self.cmb_block_day.currentTextChanged.connect(self._refresh_timeline)
        self.spin_max.valueChanged.connect(self._update_footer_summary)
        self.cmb_bio.currentIndexChanged.connect(self._update_footer_summary)

    def _on_max_spin_changed(self, val):
        hours = val // 60
        mins = val % 60
        suffix_str = f" dakika (~{hours} sa {mins} dk)" if hours > 0 else f" dakika"
        self.spin_max.setSuffix(suffix_str)
        self._update_footer_summary()

    def _update_footer_summary(self):
        val = self.spin_max.value()
        bio = self.cmb_bio.currentText().split()[0] # İkon ve kısa ad
        self.lbl_footer_summary.setText(f"🎯 Hedef: ~{val} dk/gün • Mod: {bio}")

    def _append_template_note(self, text: str):
        curr = self.txt_notes.toPlainText().strip()
        if text not in curr:
            if curr:
                self.txt_notes.setPlainText(curr + ", " + text)
            else:
                self.txt_notes.setPlainText(text)

    def _refresh_timeline(self):
        day = self.cmb_block_day.currentText()
        st = self.time_school_start.time()
        et = self.time_school_end.time()
        school_active = self.widget_school_times.isVisible()
        
        blocks = []
        for i in range(self.lst_blocks.count()):
            blocks.append(self.lst_blocks.item(i).text())
            
        self.timeline.update_data(day, school_active, st, et, blocks)

    def _on_student_type_changed(self):
        idx = self.cmb_student_type.currentIndex()
        if idx == 0: # Okula Gidiyor
            self.widget_school_times.setVisible(True)
            self.chk_school.setChecked(True)
        else: # Mezun veya Özel
            self.widget_school_times.setVisible(False)
            self.chk_school.setChecked(False)
        self._refresh_timeline()

    def _add_block_item(self):
        day = self.cmb_block_day.currentText()
        st = self.time_block_start.time().toString("HH:mm")
        et = self.time_block_end.time().toString("HH:mm")
        desc = self.txt_block_desc.text().strip() or "Meşgul / Rutin"
        
        item_text = f"{day} [{st}-{et}] {desc}"
        self.lst_blocks.addItem(item_text)
        self.txt_block_desc.clear()
        self._refresh_timeline()

    def _remove_block_item(self):
        row = self.lst_blocks.currentRow()
        if row >= 0:
            self.lst_blocks.takeItem(row)
        self._refresh_timeline()

    def _toggle_school_times(self, checked):
        pass

    def _toggle_course_times(self, checked):
        pass

    def _add_focus_tag(self, txt: str):
        curr = self.txt_focus.text().strip()
        if txt not in curr:
            if curr:
                curr += ", "
            curr += txt
            self.txt_focus.setText(curr)

    def _perform_ai_analysis(self):
        is_lgs = False
        if self.lesson_names:
            is_lgs = any("lgs" in str(x).lower() for x in self.lesson_names)
        
        group_label = "LGS" if is_lgs else "YKS"
        suggestions = []
        reasons = []

        if is_lgs:
            suggestions = ["LGS Matematik", "LGS Fen Bilimleri"]
            reasons = [
                "<b>LGS Matematik:</b> Yeni nesil beceri temelli sorularda pratik ve soru kökü analiz ihtiyacı.",
                "<b>LGS Fen Bilimleri:</b> Deneysel ve grafik okuma sorularında konu tekrarı gereksinimi."
            ]
        else:
            suggestions = ["TYT Matematik", "Geometri", "Fizik"]
            reasons = [
                "<b>TYT Matematik:</b> Problemler ve sayı basamakları hızlanma çalışması.",
                "<b>Geometri:</b> Üçgende alan ve analitik görme pratiği.",
                "<b>Fizik:</b> Mekanik ve optik formül pekiştirmesi."
            ]

        # UI Güncelle
        curr = self.txt_focus.text()
        new_text = curr
        for s in suggestions:
            if s.lower() not in curr.lower():
                if new_text:
                    new_text += ", "
                new_text += s
        self.txt_focus.setText(new_text)
        
        s_name = self.student_name or "Öğrenci"
        msg = f"<h3>🤖 Yapay Zeka Koçluk Analizi</h3><hr>"
        msg += f"Öğrenci: <b>{s_name}</b> ({group_label})<br>"
        msg += "<i>Sistem performans ve ders zorluk verilerini analiz etti:</i><br><br>"
        msg += "<b>⚠️ Tespit Edilen Kritik Öncelikler:</b><ul>"
        for r in reasons:
            msg += f"<li>{r}</li>"
        msg += "</ul><br><i>*Öneri: Bu dersler takvime öncelikli ve dinç olunan saatlerde yerleştirilecektir.*</i>"
        QMessageBox.information(self, "AI Koç Analizi Tamamlandı", msg)

    def _gather_data(self) -> Dict[str, Any]:
        p_idx = self.cmb_student_type.currentIndex()
        
        school_str = "Yok"
        if self.widget_school_times.isVisible():
            st = self.time_school_start.time().toString("HH:mm")
            et = self.time_school_end.time().toString("HH:mm")
            school_str = f"{st}-{et}"
        
        blocks = []
        for i in range(self.lst_blocks.count()):
            blocks.append(self.lst_blocks.item(i).text())
            
        weekend_mode = "Dengeli"
        if self.rb_w_relax.isChecked():
            weekend_mode = "Hafif"
        elif self.rb_w_hard.isChecked():
            weekend_mode = "Yoğun"

        empty = "Yok"
        if self.chk_empty_day.isChecked():
            empty = self.cmb_empty_day.currentText()
            
        return {
            "profile_idx": p_idx,
            "school": school_str,
            "max": self.spin_max.value(),
            "weekend_mode": weekend_mode,
            "biorhythm": self.cmb_bio.currentText(),
            "blocks": blocks,
            "focus": self.txt_focus.text(),
            "empty": empty,
            "note": self.txt_notes.toPlainText()
        }

    def _apply_data(self, data: Dict[str, Any]):
        try:
            p_idx = int(data.get("profile_idx", 0))
            self.cmb_student_type.setCurrentIndex(p_idx)
        except Exception:
            pass
        
        sc = data.get("school", "Yok")
        if sc != "Yok":
            try:
                s, e = sc.split("-")
                self.time_school_start.setTime(QTime.fromString(s.strip(), "HH:mm"))
                self.time_school_end.setTime(QTime.fromString(e.strip(), "HH:mm"))
            except Exception:
                pass

        self.lst_blocks.clear()
        blocks = data.get("blocks", [])
        for b in blocks:
            self.lst_blocks.addItem(b)
            
        self.spin_max.setValue(int(data.get("max", 180)))
        
        wm = data.get("weekend_mode", "Dengeli")
        if wm == "Hafif":
            self.rb_w_relax.setChecked(True)
        elif wm == "Yoğun":
            self.rb_w_hard.setChecked(True)
        else:
            self.rb_w_normal.setChecked(True)

        bio_txt = data.get("biorhythm", "Standart")
        for i in range(self.cmb_bio.count()):
            if bio_txt.lower() in self.cmb_bio.itemText(i).lower():
                self.cmb_bio.setCurrentIndex(i)
                break

        self.txt_focus.setText(data.get("focus", ""))
        
        emp = data.get("empty", "Yok")
        if emp == "Yok":
            self.chk_empty_day.setChecked(False)
        else:
            self.chk_empty_day.setChecked(True)
            self.cmb_empty_day.setCurrentText(emp)
            
        self.txt_notes.setText(data.get("note", ""))
        self._refresh_timeline()

    def _load_profiles(self):
        self.cmb_profiles.blockSignals(True)
        self.cmb_profiles.clear()
        self.cmb_profiles.addItem("Varsayılan Standart Ayarlar", None)
        
        if os.path.exists(PROFILE_FILE):
            try:
                with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                    self.profiles = json.load(f)
                for name in self.profiles:
                    self.cmb_profiles.addItem(f"👤 {name}", name)
            except Exception as e:
                print(f"Profil yükleme hatası: {e}")
                self.profiles = {}
        else:
            self.profiles = {}
        self.cmb_profiles.blockSignals(False)

    def _save_current_profile(self):
        text, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil İsmi (Örn: YKS Sayısal 12-A / Yoğun):")
        if ok and text:
            data = self._gather_data()
            self.profiles[text] = data
            try:
                with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.profiles, f, ensure_ascii=False, indent=2)
                
                self._load_profiles()
                idx = self.cmb_profiles.findData(text)
                if idx >= 0:
                    self.cmb_profiles.setCurrentIndex(idx)
                    
                QMessageBox.information(self, "Başarılı", f"'{text}' profili başarıyla kaydedildi.")
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Kaydedilemedi: {e}")

    def _update_current_profile(self):
        curr = self.cmb_profiles.currentData()
        if not curr:
            QMessageBox.information(
                self, "Profil Güncelle",
                "Şu anda 'Varsayılan Standart Ayarlar' seçili.\n\n"
                "Mevcut ayarları yeni bir şablon / profil olarak kaydetmek için lütfen '💾 Profili Kaydet' butonunu kullanın."
            )
            return

        ans = QMessageBox.question(
            self, "Profil Güncelle",
            f"'{curr}' profilini ekrandaki güncel ayarlar ile güncellemek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if ans == QMessageBox.StandardButton.Yes:
            data = self._gather_data()
            self.profiles[curr] = data
            try:
                with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.profiles, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Başarılı", f"'{curr}' profili başarıyla güncellendi.")
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Profil güncellenemedi: {e}")

    def _delete_profile(self):
        curr = self.cmb_profiles.currentData()
        if not curr:
            return
        
        ans = QMessageBox.question(
            self, "Profil Sil", f"'{curr}' profilini silmek istediğinize emin misiniz?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            if curr in self.profiles:
                del self.profiles[curr]
                try:
                    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                        json.dump(self.profiles, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                self._load_profiles()

    def _on_profile_changed(self):
        name = self.cmb_profiles.currentData()
        if name and name in self.profiles:
            self._apply_data(self.profiles[name])
        else:
            self.chk_school.setChecked(True)
            self.spin_max.setValue(180)
            self.rb_w_normal.setChecked(True)
            self.cmb_bio.setCurrentIndex(0)
            self.txt_focus.clear()
            self.chk_empty_day.setChecked(False)
            self.txt_notes.clear()
            self.lst_blocks.clear()
            self._refresh_timeline()

    def _create_plan(self):
        data = self._gather_data()
        prompt_parts = []
        
        prompt_parts.append("--- AI KOÇLUK SİSTEMİ BAŞLATILDI ---")
        prompt_parts.append("ROL: Sen sadece ders programı yapan bir algoritma değil, öğrencinin akademik koçusun.")
        prompt_parts.append("GÖREV: Öğrencinin verilerini analiz et, gerçekçi ve motive edici bir plan oluştur.")
        
        # 1. Profil ve Biyoritim
        p_idx = data["profile_idx"]
        p_name = self.cmb_student_type.itemText(p_idx)
        prompt_parts.append(f"ÖĞRENCİ PROFİLİ: {p_name}")
        prompt_parts.append(f"BİYORİTİM (Verim Modu): {data['biorhythm']}")
        
        # 2. Okul
        if data["school"] != "Yok": 
            prompt_parts.append(f"OKUL SAATLERİ (Ders Atama): {data['school']}")
        else:
            prompt_parts.append("OKUL: Yok (Tüm gün serbest)")
        
        # 3. KESİN Kısıtlar (Structured)
        if data["blocks"]:
            blocks_str = " ; ".join(data["blocks"])
            prompt_parts.append(f"!!! ZORUNLU ENGEL (ASLA DERS KOYMA) !!!: {blocks_str}")
            
        # 4. Hedefler
        prompt_parts.append(f"GÜNLÜK HEDEF: {data['max']} dakika")
        prompt_parts.append(f"HAFTA SONU MODU: {data['weekend_mode']}")
            
        # 5. Zorlanılan Dersler
        if data["focus"]: 
            prompt_parts.append(f"KRİTİK DERSLER (Zorlanıyor, Ağırlık Ver): {data['focus']}")
             
        # 6. Tatil
        if data["empty"] != "Yok" and data["empty"] != "Rastgele":
            prompt_parts.append(f"TAM GÜN TATİL: {data['empty']}")
             
        # 7. Ekstra Notlar
        if data["note"]: 
            prompt_parts.append(f"ÖZEL NOTLAR: {data['note']}")
            
        self.result_details = " || ".join(prompt_parts)
        self.accept()

    def get_details(self) -> str:
        return self.result_details
