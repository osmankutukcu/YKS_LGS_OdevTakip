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

from services.plan_profile_store import (load_profiles, save_profiles, profile_path,
                                         load_assignments, save_assignments)
from services.planning_constraints import availability_for_week, free_minutes, serialize_details, parse_block, DAYS
from services.session_advisor import (record_feedback, recent_feedback, homework_summary,
                                      suggest_session_minutes, personal_profile_update)
from pathlib import Path
import sqlite3

PROFILE_FILE = "plan_profiles.json"  # legacy name; writes go to per-user application data


def get_profiles_file_path() -> Path:
    """
    plan_profiles.json dosyasının okunacağı ve yazılacağı güvenli platform AppData yolunu döner.
    Windows Program Files altında çalışırken Permission Denied (Errno 13) hatasını kesin olarak önler.
    """
    try:
        from db import _platform_appdata_dir, _exe_dir, _is_in_program_files, _is_dir_writable
        exe_dir = _exe_dir()
        if not _is_in_program_files(exe_dir) and _is_dir_writable(exe_dir):
            return exe_dir / "plan_profiles.json"
        
        app_dir = _platform_appdata_dir()
        app_dir.mkdir(parents=True, exist_ok=True)
        target = app_dir / "plan_profiles.json"
        
        old_file = exe_dir / "plan_profiles.json"
        if old_file.exists() and not target.exists():
            try:
                import shutil
                shutil.copy2(old_file, target)
            except Exception:
                pass
        return target
    except Exception:
        pass

    try:
        home_dir = Path.home() / ".yks_lgs_manager"
        home_dir.mkdir(parents=True, exist_ok=True)
        return home_dir / "plan_profiles.json"
    except Exception:
        return Path("plan_profiles.json")



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
        self.study_windows = []
        self.wake_min = 420
        self.sleep_min = 1410
        
    def update_data(self, day, school_active, s_time, e_time, block_list):
        self.day_name = day or "Pazartesi"
        
        # Okul saatleri
        self.school_times = None
        if school_active:
            if hasattr(s_time, "hour") and hasattr(e_time, "hour"):
                s = s_time.hour() * 60 + s_time.minute()
                e = e_time.hour() * 60 + e_time.minute()
                self.school_times = (s, e)
            
        # Use the same day/routine parser as the scheduling engine.
        self.blocks = []
        for rule in block_list:
            try:
                days, start, end, label = parse_block(rule)
                if list(DAYS).index(self.day_name) in days:
                    self.blocks.append((start, end, label or 'Rutin'))
            except ValueError:
                continue

        self.calculate_free_time()
        self.update()
        
    def calculate_free_time(self):
        day_start = self.wake_min
        day_end = self.sleep_min
        
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
                if start <= last_e:
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
        try:
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
            cap_text = f"🟢 Kısıt sonrası boş aralık: {hours} sa {mins} dk"
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
            
            # Yeşil çalışma pencereleri: günün gerçekten kullanılabilir alanları.
            p.setBrush(QColor('#dcfce7'))
            p.setPen(QPen(QColor('#4ade80'), 1))
            for start, end in self.study_windows:
                x1 = max(20, min_to_x(start))
                x2 = min(w - 20, min_to_x(end))
                if x2 > x1:
                    p.drawRoundedRect(QRectF(x1, bar_y + 2, x2 - x1, bar_h - 4), 3, 3)

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
            p.setFont(QFont("Segoe UI", 8))
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
        except Exception:
            pass
        finally:
            p.end()


class PlanSettingsDialog(QDialog):
    """
    Profesyonel Akıllı Takvim ve Haftalık Planlama Sihirbazı (V3.5 Executive).
    Öğrencinin okul saatleri, özel ders rutinleri ve kapasitesine göre yapay zeka destekli takvim parametreleri üretir.
    """
    def __init__(self, parent=None, lesson_names: Optional[List[str]] = None,
                 student_name: Optional[str] = None, student_id: Optional[str] = None,
                 homework_list: Optional[List[Dict[str, Any]]] = None):
        super().__init__(parent)
        self.student_name = student_name
        self.student_id = str(student_id).strip() if student_id is not None and str(student_id).strip() else None

        # Fallback student_name & student_id
        if parent:
            try:
                if not self.student_name:
                    if hasattr(parent, "cmbAd") and hasattr(parent, "cmbSoyad"):
                        self.student_name = f"{parent.cmbAd.currentText()} {parent.cmbSoyad.currentText()}".strip()
                    elif hasattr(parent, "student_name"):
                        self.student_name = parent.student_name
                if not self.student_id:
                    if hasattr(parent, "_secili_ogrenci_id"):
                        s_id = parent._secili_ogrenci_id()
                        self.student_id = str(s_id).strip() if s_id is not None and str(s_id).strip() else None
                    elif hasattr(parent, "cmbAd"):
                        s_id = parent.cmbAd.currentData()
                        self.student_id = str(s_id).strip() if s_id is not None and str(s_id).strip() else None
            except Exception:
                pass
             
        # Varsayılan entegrasyon: mevcut Verilen Ödevler tablosundan yalnızca
        # okuma yap. Ödev Takip ana kaynak dosyasında tek satır değişiklik gerekmez.
        if homework_list is None and parent is not None and hasattr(parent, 'verilen'):
            try:
                from services.calendar_plan_inputs import snapshot_homework_table
                homework_list = snapshot_homework_table(parent.verilen)
            except (ValueError, AttributeError, TypeError):
                homework_list = []
        self.homework_list = list(homework_list or [])
        self.lesson_names = lesson_names or []
        self.result_details = ""
        # Approved per-plan priorities are transient, never shared profile data.
        self._approved_topic_focus = []
        self.profiles = {}
        
        self.setWindowTitle("📅 Akıllı Haftalık Planlama & Takvim Sihirbazı")
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowMaximizeButtonHint | 
            Qt.WindowType.WindowCloseButtonHint
        )
        
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(1040, int(avail.width() * 0.94))
            h = min(780, int(avail.height() * 0.92))
            self.resize(w, h)
        else:
            self.resize(960, 720)
        self.setMinimumSize(480, 360)
        
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
        self._restore_student_profile()
        self._refresh_session_advice()
        self.weekly_overview.refresh()

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
        
        sub_text = "Verilen Ödevler listesini öğrencinin okul, kurs, uyku ve rutinlerine göre haftaya dağıtın."
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
        h_prof.setSpacing(6)
        lbl_prof = QLabel("<font color='#e0e7ff'><b>📋 Şablon:</b></font>")
        lbl_prof.setStyleSheet("font-size: 11.5px;")
        h_prof.addWidget(lbl_prof)
        
        self.cmb_profiles = QComboBox()
        self.cmb_profiles.setStyleSheet("background: white; border-radius: 5px; padding: 3px 6px; min-width: 140px; font-size: 11.5px;")
        
        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_prof.setToolTip("Mevcut ayarları yeni bir şablon/profil olarak kaydeder")
        btn_save_prof.setStyleSheet("""
            QPushButton {
                background: #10b981; color: white; font-weight: bold; border: none; border-radius: 5px; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background: #059669; }
        """)
        btn_save_prof.clicked.connect(self._save_current_profile)

        btn_update_prof = QPushButton("🔄 Güncelle")
        btn_update_prof.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_update_prof.setToolTip("Seçili profilin ayarlarını mevcut form verileriyle günceller")
        btn_update_prof.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; font-weight: bold; border: none; border-radius: 5px; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_update_prof.clicked.connect(self._update_current_profile)
        
        btn_assign = QPushButton('🎯 Öğrenciye Ata')
        btn_assign.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_assign.setEnabled(bool(self.student_id))
        btn_assign.setToolTip('Seçili şablonu bu öğrenci için sonraki açılışlarda otomatik seçer')
        btn_assign.setStyleSheet("""
            QPushButton {
                background: #7c3aed; color: white; font-weight: bold; border: none; border-radius: 5px; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background: #6d28d9; }
            QPushButton:disabled { background: #94a3b8; color: #e2e8f0; }
        """)
        btn_assign.clicked.connect(self._assign_to_student)

        btn_del_prof = QPushButton("🗑️ Sil")
        btn_del_prof.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del_prof.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.85); color: white; font-weight: bold; border: none; border-radius: 5px; padding: 4px 9px; font-size: 11.5px;
            }
            QPushButton:hover { background: #dc2626; }
        """)
        btn_del_prof.clicked.connect(self._delete_profile)

        h_prof.addWidget(self.cmb_profiles, 1)
        h_prof.addWidget(btn_save_prof)
        h_prof.addWidget(btn_update_prof)
        h_prof.addWidget(btn_assign)
        btn_pdf_preview = QPushButton('📄 PDF Önizle')
        btn_pdf_preview.setToolTip('Aynı kısıt denetimlerini kullanarak haftalık programın PDF önizlemesini açar')
        btn_pdf_preview.setStyleSheet('QPushButton{background:#e0f2fe;color:#075985;'
                                      'font-weight:700;padding:5px 9px;border-radius:5px;}')
        btn_pdf_preview.clicked.connect(self._create_plan)
        h_prof.addWidget(btn_pdf_preview)
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
        self.widget_school_times.setVisible(True)
        h_school = QHBoxLayout(self.widget_school_times)
        h_school.setContentsMargins(0, 0, 0, 0)
        self.chk_school = QCheckBox("Okul Var") 
        self.chk_school.setVisible(False)
        self.chk_school.setChecked(True)
        
        self.time_school_start = QTimeEdit(QTime(8, 30), self.widget_school_times)
        self.time_school_end = QTimeEdit(QTime(15, 40), self.widget_school_times)
        self.time_school_start.setDisplayFormat("HH:mm")
        self.time_school_end.setDisplayFormat("HH:mm")
        self.time_school_start.timeChanged.connect(self._on_standard_school_time_changed)
        self.time_school_end.timeChanged.connect(self._on_standard_school_time_changed)
        
        h_school.addWidget(QLabel("<b>Okul Başlangıç:</b>", self.widget_school_times))
        h_school.addWidget(self.time_school_start)
        h_school.addSpacing(16)
        h_school.addWidget(QLabel("<b>Okul Bitiş:</b>", self.widget_school_times))
        h_school.addWidget(self.time_school_end)
        h_school.addStretch()
        lay_profile.addWidget(self.widget_school_times)
        self.school_day_checks = []
        self.school_day_start = []
        self.school_day_end = []
        school_grid = QGridLayout()
        school_grid.setHorizontalSpacing(8)
        school_grid.addWidget(QLabel("<b>Okul günleri ve gün bazında ders saatleri:</b>"), 0, 0, 1, 3)
        for day_idx, day_name in enumerate(DAYS):
            cb = QCheckBox(day_name)
            cb.setChecked(day_idx < 5)
            start = QTimeEdit(QTime(8, 30))
            end = QTimeEdit(QTime(15, 40))
            for edit in (start, end):
                edit.setDisplayFormat("HH:mm")
                edit.timeChanged.connect(self._refresh_timeline)
            cb.toggled.connect(start.setEnabled)
            cb.toggled.connect(end.setEnabled)
            cb.toggled.connect(self._refresh_timeline)
            start.setEnabled(cb.isChecked())
            end.setEnabled(cb.isChecked())
            school_grid.addWidget(cb, day_idx + 1, 0)
            school_grid.addWidget(start, day_idx + 1, 1)
            school_grid.addWidget(end, day_idx + 1, 2)
            self.school_day_checks.append(cb)
            self.school_day_start.append(start)
            self.school_day_end.append(end)
        self.school_grid_widget = QWidget()
        self.school_grid_widget.setLayout(school_grid)
        h_after_school = QHBoxLayout()
        h_after_school.addWidget(QLabel('Okul sonrası ulaşım/dinlenme:'))
        self.spin_after_school = QSpinBox()
        self.spin_after_school.setRange(0, 180)
        self.spin_after_school.setValue(30)
        self.spin_after_school.setSuffix(' dk')
        self.spin_after_school.valueChanged.connect(self._refresh_timeline)
        h_after_school.addWidget(self.spin_after_school)
        h_after_school.addStretch()
        lay_profile.addLayout(h_after_school)
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
        self.cmb_block_day.addItems(["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar", "Hafta İçi Her Gün", "Hafta Sonu", "Her Gün"])
        
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

        # Optional per-student buffer after a course/private lesson.
        # Defaults to zero for backward compatibility with existing plans.
        h_after_routine = QHBoxLayout()
        h_after_routine.addWidget(QLabel('Sabit rutin sonrası ulaşım/dinlenme:'))
        self.spin_after_routine = QSpinBox()
        self.spin_after_routine.setRange(0, 180)
        self.spin_after_routine.setValue(0)
        self.spin_after_routine.setSuffix(' dk')
        self.spin_after_routine.setToolTip('Örn. kurs 16:00’da biter ve 20 dk seçilirse, ödev en erken 16:20’de başlar.')
        self.spin_after_routine.valueChanged.connect(self._refresh_timeline)
        h_after_routine.addWidget(self.spin_after_routine)
        h_after_routine.addStretch()
        lay_blocks.addLayout(h_after_routine)
        
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
        
        grp_rest = QGroupBox("🌙 Günlük Uyanma / Uyku ve Çalışılabilir Saat Aralığı")
        rest_row = QHBoxLayout(grp_rest)
        rest_row.addWidget(QLabel("Uyanma:"))
        self.time_wake = QTimeEdit(QTime(7, 0))
        self.time_wake.setDisplayFormat("HH:mm")
        rest_row.addWidget(self.time_wake)
        rest_row.addWidget(QLabel("Uyku:"))
        self.time_sleep = QTimeEdit(QTime(23, 30))
        self.time_sleep.setDisplayFormat("HH:mm")
        rest_row.addWidget(self.time_sleep)
        rest_row.addStretch()
        self.time_wake.timeChanged.connect(self._refresh_timeline)
        self.time_sleep.timeChanged.connect(self._refresh_timeline)
        t2_lay.addWidget(grp_cap)
        t2_lay.addWidget(grp_rest)

        grp_day_specific = QGroupBox('📅 Günlük Uyanma, Yatış, Çalışma ve Üst Sınır (İsteğe Bağlı)')
        day_layout = QGridLayout(grp_day_specific)
        for col, heading in enumerate(('Gün', 'Özel', 'Uyanma', 'Yatış', 'Çalışma Başla', 'Çalışma Bitir', 'Maks. dk')):
            day_layout.addWidget(QLabel(f'<b>{heading}</b>'), 0, col)
        self.day_override_checks = []
        self.day_override_start = []
        self.day_override_end = []
        self.day_override_max = []
        self.day_wake = []
        self.day_bed = []
        for day_idx, name in enumerate(DAYS):
            cb = QCheckBox()
            wake = QTimeEdit(QTime(7, 0))
            bed = QTimeEdit(QTime(23, 30))
            start = QTimeEdit(QTime(7, 0))
            end = QTimeEdit(QTime(23, 30))
            max_minutes = QSpinBox()
            max_minutes.setRange(0, 720)
            max_minutes.setValue(180)
            for edit in (wake, bed, start, end):
                edit.setDisplayFormat('HH:mm')
                edit.setEnabled(False)
                edit.timeChanged.connect(self._refresh_timeline)
            max_minutes.setEnabled(False)
            cb.toggled.connect(wake.setEnabled)
            cb.toggled.connect(bed.setEnabled)
            cb.toggled.connect(start.setEnabled)
            cb.toggled.connect(end.setEnabled)
            cb.toggled.connect(max_minutes.setEnabled)
            cb.toggled.connect(self._refresh_timeline)
            max_minutes.valueChanged.connect(self._refresh_timeline)
            day_layout.addWidget(QLabel(name), day_idx+1, 0)
            day_layout.addWidget(cb, day_idx+1, 1)
            day_layout.addWidget(wake, day_idx+1, 2)
            day_layout.addWidget(bed, day_idx+1, 3)
            day_layout.addWidget(start, day_idx+1, 4)
            day_layout.addWidget(end, day_idx+1, 5)
            day_layout.addWidget(max_minutes, day_idx+1, 6)
            self.day_override_checks.append(cb)
            self.day_override_start.append(start)
            self.day_override_end.append(end)
            self.day_override_max.append(max_minutes)
            self.day_wake.append(wake)
            self.day_bed.append(bed)
        desc = QLabel('İşaretlenmeyen günler genel uyanma/uyku ve maksimum süre ayarını kullanır. '
                      'Buradaki günlük maksimum, genel üst sınırı aşamaz.')
        desc.setWordWrap(True)
        day_layout.addWidget(desc, 8, 0, 1, 7)
        # Grubu sade Hedef & Tempo yerine isteğe bağlı İnce Ayarlar sekmesine taşı.

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

        # Ayrıntılı haftalık rutinler yalnızca isteyen öğretmenlerce etkinleştirilir.
        tab_advanced = QWidget()
        adv_layout = QVBoxLayout(tab_advanced)
        adv_layout.setContentsMargins(16, 14, 16, 14)
        adv_layout.setSpacing(12)
        self.chk_advanced = QCheckBox("⚙️ Günlere özel ince ayarları etkinleştir")
        self.chk_advanced.setToolTip("Kapalıyken genel çalışma saatleri uygulanır. Kaydedilen özel günler silinmez.")
        self.chk_advanced.setStyleSheet('font-size: 13px; font-weight: 700; color: #1d4ed8;')
        adv_layout.addWidget(self.chk_advanced)
        advanced_info = QLabel(
            'Örnek: Pazartesi 07:00’de uyanır, 22:00’de yatar; yalnızca 18:00–20:00 çalışır, '
            'en çok 90 dakika ödev yapar. Cumartesi tamamen farklı saatler seçilebilir. '
            'Okul, kurs, özel ders ve dinlenme blokları ayrıca çıkarılır. '
            'Bu ayarlar seçilen profil ile birlikte saklanır.')
        advanced_info.setWordWrap(True)
        advanced_info.setStyleSheet('color:#475569;')
        adv_layout.addWidget(advanced_info)
        # Öğrenciye özel süre ayarı; günlük üst sınırdan bağımsızdır.
        grp_sessions = QGroupBox('⏱️ Etüt Oturumu & Mola Düzeni (İsteğe Bağlı)')
        sessions_layout = QVBoxLayout(grp_sessions)
        self.chk_sessions = QCheckBox('Her kesintisiz etüt için üst süre belirle')
        self.chk_sessions.setToolTip('Kapalıyken önceki ödev parçalama ve 10 dakikalık geçiş arası kullanılır.')
        sessions_layout.addWidget(self.chk_sessions)
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel('Azami tek oturum:'))
        self.spin_session_minutes = QSpinBox()
        self.spin_session_minutes.setRange(15, 180)
        self.spin_session_minutes.setSingleStep(5)
        self.spin_session_minutes.setSuffix(' dk')
        self.spin_session_minutes.setValue(45)
        session_row.addWidget(self.spin_session_minutes)
        session_row.addWidget(QLabel('Oturumlar arası mola:'))
        self.spin_session_break = QSpinBox()
        self.spin_session_break.setRange(0, 60)
        self.spin_session_break.setSingleStep(5)
        self.spin_session_break.setSuffix(' dk')
        self.spin_session_break.setValue(10)
        session_row.addWidget(self.spin_session_break)
        session_row.addStretch()
        sessions_layout.addLayout(session_row)
        self.chk_session_split = QCheckBox('Uzun ödevleri oturumlara otomatik böl (toplam süre korunur)')
        self.chk_session_split.setChecked(True)
        sessions_layout.addWidget(self.chk_session_split)
        session_help = QLabel('Örnek: Günlük 180 dk, oturum 45 dk, mola 10 dk. '
                              'Mola çalışma süresine eklenmez ancak takvimde yer kaplar. '
                              'Bölünemeyen uzun görev uygun oturum bulamazsa yerleşmeyenlerde gösterilir.')
        session_help.setWordWrap(True)
        sessions_layout.addWidget(session_help)
        self.chk_sessions.toggled.connect(self.spin_session_minutes.setEnabled)
        self.chk_sessions.toggled.connect(self.spin_session_break.setEnabled)
        self.chk_sessions.toggled.connect(self.chk_session_split.setEnabled)
        self.spin_session_minutes.setEnabled(False)
        self.spin_session_break.setEnabled(False)
        self.chk_session_split.setEnabled(False)
        # Minimal one-touch coaching: no form, no extra columns in homework table.
        self.lbl_session_advice = QLabel('Öğrenci verileri kontrol edilmeyi bekliyor.')
        self.lbl_session_advice.setWordWrap(True)
        self.lbl_session_advice.setStyleSheet('color: #334155; padding: 6px; background: #eff6ff; border-radius: 5px;')
        sessions_layout.addWidget(self.lbl_session_advice)
        feedback_bar = QHBoxLayout()
        feedback_bar.addWidget(QLabel('Tek dokunuşla gözlem:'))
        self.btn_feedback_hard = QPushButton('😓 Zorlandı')
        self.btn_feedback_ok = QPushButton('✅ Uygundu')
        self.btn_feedback_easy = QPushButton('🙂 Rahat')
        for button, rating in ((self.btn_feedback_hard, 'hard'),
                               (self.btn_feedback_ok, 'ok'),
                               (self.btn_feedback_easy, 'easy')):
            button.setToolTip('Bu öğrenci için bugünkü gözlemi kaydet; aynı gün tekrar basılırsa günceller.')
            button.clicked.connect(lambda checked=False, r=rating: self._record_session_feedback(r))
            button.setEnabled(bool(self.student_id))
            feedback_bar.addWidget(button)
        feedback_bar.addStretch()
        sessions_layout.addLayout(feedback_bar)
        self.btn_accept_session_advice = QPushButton('✨ Önerilen Etüt Süresini Tek Tıkla Uygula')
        self.btn_accept_session_advice.setToolTip(
            'Yalnızca bu öğrenciye özel profil oluşturur/günceller. Diğer öğrenciler ve ödevler değişmez.')
        self.btn_accept_session_advice.setEnabled(False)
        self.btn_accept_session_advice.clicked.connect(self._apply_session_advice)
        adv_layout.addWidget(grp_sessions)
        
        grp_school_grid = QGroupBox("🏫 Gün Bazında Okul Saatleri Özelleştirmesi (İsteğe Bağlı)")
        lay_school_grid = QVBoxLayout(grp_school_grid)
        lay_school_grid.addWidget(self.school_grid_widget)
        adv_layout.addWidget(grp_school_grid)
        grp_school_grid.setEnabled(False)
        self.chk_advanced.toggled.connect(grp_school_grid.setEnabled)

        adv_layout.addWidget(grp_day_specific)
        self.grp_day_specific = grp_day_specific
        grp_day_specific.setEnabled(False)
        self.chk_advanced.toggled.connect(grp_day_specific.setEnabled)
        self.chk_advanced.toggled.connect(self._refresh_timeline)

        grp_second = QGroupBox('🕒 Günlere Göre İkinci Çalışma Dilimi (İsteğe Bağlı)')
        secondary_grid = QGridLayout(grp_second)
        secondary_grid.addWidget(QLabel('<b>Gün</b>'), 0, 0)
        secondary_grid.addWidget(QLabel('<b>İkinci dilim</b>'), 0, 1)
        secondary_grid.addWidget(QLabel('<b>Başlangıç</b>'), 0, 2)
        secondary_grid.addWidget(QLabel('<b>Bitiş</b>'), 0, 3)
        self.second_checks = []
        self.second_start = []
        self.second_end = []
        for day_idx, name in enumerate(DAYS):
            cb = QCheckBox('Açık')
            a = QTimeEdit(QTime(20, 0))
            b = QTimeEdit(QTime(22, 0))
            for control in (a, b):
                control.setDisplayFormat('HH:mm')
                control.setEnabled(False)
                control.timeChanged.connect(self._refresh_timeline)
            cb.setEnabled(False)
            self.day_override_checks[day_idx].toggled.connect(cb.setEnabled)
            self.day_override_checks[day_idx].toggled.connect(
                lambda active, check=cb: check.setChecked(False) if not active else None)
            cb.toggled.connect(a.setEnabled)
            cb.toggled.connect(b.setEnabled)
            cb.toggled.connect(self._refresh_timeline)
            secondary_grid.addWidget(QLabel(name), day_idx+1, 0)
            secondary_grid.addWidget(cb, day_idx+1, 1)
            secondary_grid.addWidget(a, day_idx+1, 2)
            secondary_grid.addWidget(b, day_idx+1, 3)
            self.second_checks.append(cb)
            self.second_start.append(a)
            self.second_end.append(b)
        grp_second.setEnabled(False)
        self.chk_advanced.toggled.connect(grp_second.setEnabled)
        adv_layout.addWidget(grp_second)

        grp_copy = QGroupBox('📋 Ayarları Hızlı Kopyala')
        copy_layout = QHBoxLayout(grp_copy)
        copy_layout.addWidget(QLabel('Kaynak gün:'))
        self.cmb_copy_source = QComboBox()
        self.cmb_copy_source.addItems(DAYS)
        copy_layout.addWidget(self.cmb_copy_source)
        copy_layout.addWidget(QLabel('Hedef:'))
        self.cmb_copy_dest = QComboBox()
        self.cmb_copy_dest.addItems(['Hafta içi (Pzt–Cum)', 'Hafta sonu (Cmt–Paz)', 'Bütün hafta'])
        copy_layout.addWidget(self.cmb_copy_dest)
        btn_copy = QPushButton('📋 Gün Ayarlarını Kopyala')
        btn_copy.clicked.connect(self._copy_advanced_day)
        copy_layout.addWidget(btn_copy)
        grp_copy.setEnabled(False)
        self.chk_advanced.toggled.connect(grp_copy.setEnabled)
        adv_layout.addWidget(grp_copy)
        lbl_second = QLabel('İki çalışma dilimi birbirini kesmemelidir. '
                            'Örneğin 16:30–18:00 ve 20:00–21:30. Aradaki zaman otomatik olarak boş bırakılır. '
                            'Gece yarısından sonraki saatler bir sonraki güne taşınmaz; yatış aynı gün içinde tanımlanır.')
        lbl_second.setWordWrap(True)
        adv_layout.addWidget(lbl_second)
        self.lbl_advanced_capacity = QLabel('📊 Bu haftanın tahmini çalışma kapasitesi: --')
        self.lbl_advanced_capacity.setWordWrap(True)
        self.lbl_advanced_capacity.setStyleSheet('color:#166534; font-weight:600;')
        adv_layout.addWidget(self.lbl_advanced_capacity)
        adv_layout.addStretch()
        self.tabs.addTab(_wrap_in_scroll(tab_advanced), '⚙️ İnce Ayarlar')

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
        
        btn_ai = QPushButton("📊 Verilen Ödevlere Göre Ders Önceliği Öner")
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

        grp_notes = QGroupBox("📝 2. Öğrenciye Özel Açıklama Notları")
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
        self.txt_notes.setPlaceholderText("Açıklama notları burada saklanır. Gerçek zaman engellerini Zaman & Okul > Sabit Saatler bölümüne ekleyin.")
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
            "• <b>Özel Durum Notları:</b> Açıklama amacıyla saklanır; tek başına saat engeli oluşturmaz. "
            "Kurs, etüt ve antrenman saatlerini 'Zaman & Okul' sekmesinde sabit rutin olarak kaydedin."
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

        # V35: Görsel tasarıma uygun salt-okunur özet. Mevcut sekmeler/ayarlar aynen kalır.
        from ui.weekly_planner_overview_v35 import WeeklyPlannerOverview
        self.weekly_overview = WeeklyPlannerOverview(self, self.homework_list)
        self.tabs.insertTab(0, _wrap_in_scroll(self.weekly_overview), '📊 Genel Bakış')
        self.tabs.currentChanged.connect(self._on_overview_tab_selected)
        self.tabs.setCurrentIndex(0)

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

    def _copy_advanced_day(self):
        source = self.cmb_copy_source.currentIndex()
        if not self.day_override_checks[source].isChecked():
            QMessageBox.information(self, 'Gün Kopyalama',
                                    'Önce kaynak günün Özel kutusunu işaretleyin.')
            return
        targets = (range(5) if self.cmb_copy_dest.currentIndex() == 0
                   else range(5, 7) if self.cmb_copy_dest.currentIndex() == 1
                   else range(7))
        attrs = (('day_wake', 'day_wake'), ('day_bed', 'day_bed'),
                 ('day_override_start', 'day_override_start'),
                 ('day_override_end', 'day_override_end'),
                 ('second_start', 'second_start'), ('second_end', 'second_end'))
        for target in targets:
            if target == source:
                continue
            self.day_override_checks[target].setChecked(True)
            for source_attr, dest_attr in attrs:
                getattr(self, dest_attr)[target].setTime(getattr(self, source_attr)[source].time())
            self.day_override_max[target].setValue(self.day_override_max[source].value())
            self.second_checks[target].setChecked(self.second_checks[source].isChecked())
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
        self.lbl_footer_summary.setText(f"🎯 Üst sınır: {val} dk/gün • Mod: {bio}")

    def _append_template_note(self, text: str):
        curr = self.txt_notes.toPlainText().strip()
        if text not in curr:
            if curr:
                self.txt_notes.setPlainText(curr + ", " + text)
            else:
                self.txt_notes.setPlainText(text)

    def _refresh_timeline(self, *_):
        day = self.cmb_block_day.currentText() if hasattr(self, 'cmb_block_day') else 'Pazartesi'
        preview_day = day if day in DAYS else 'Pazartesi'
        day_idx = list(DAYS).index(preview_day)
        school_active = self.cmb_student_type.currentIndex() == 0 and self.school_day_checks[day_idx].isChecked()
        st = self.school_day_start[day_idx].time()
        et = self.school_day_end[day_idx].time()
        blocks = [self.lst_blocks.item(i).text() for i in range(self.lst_blocks.count())]
        # Show the newly configurable post-routine buffer on the same timeline
        # used by the constraint engine, not just in the free-minute summary.
        if self.spin_after_routine.value() > 0:
            from services.planning_constraints import parse_block, hhmm
            for rule in list(blocks):
                try:
                    rule_days, _, rule_end, _ = parse_block(rule)
                except ValueError:
                    continue
                if day_idx in rule_days:
                    end_buffer = min(1439, rule_end + self.spin_after_routine.value())
                    if end_buffer > rule_end:
                        blocks.append(f'{preview_day} [{hhmm(rule_end)}-{hhmm(end_buffer)}] Ulaşım/dinlenme')
        if school_active and self.spin_after_school.value() > 0:
            end_min = et.hour() * 60 + et.minute()
            last = min(23 * 60 + 59, end_min + self.spin_after_school.value())
            if last > end_min:
                blocks.append(f'{preview_day} [{end_min//60:02d}:{end_min%60:02d}-'
                              f'{last//60:02d}:{last%60:02d}] Okul sonrası dinlenme')
        detailed = (self.chk_advanced.isChecked() and self.day_override_checks[day_idx].isChecked())
        day_wake = self.day_wake[day_idx].time() if detailed else self.time_wake.time()
        day_sleep = self.day_bed[day_idx].time() if detailed else self.time_sleep.time()
        self.timeline.wake_min = day_wake.hour() * 60 + day_wake.minute()
        self.timeline.sleep_min = day_sleep.hour() * 60 + day_sleep.minute()
        self.timeline.update_data(preview_day, school_active, st, et, blocks)
        try:
            data = self._gather_data()
            windows = availability_for_week(data)
            self.timeline.total_free = free_minutes(windows[day_idx])
            self.timeline.study_windows = windows[day_idx]
            if hasattr(self, 'lbl_advanced_capacity'):
                limit = int(data.get('max', 180))
                detail = data.get('advanced_days', {}) if data.get('advanced_enabled') else {}
                day_caps = [min(limit, int(detail.get(str(idx), {}).get('max', limit)),
                                free_minutes(windows[idx])) for idx in range(7)]
                total = sum(day_caps)
                self.lbl_advanced_capacity.setText(
                    f'📊 Haftalık üst kapasite: {total//60} sa {total%60} dk '
                    f'(günlük üst sınırlar ve gerçek boş aralıklar birlikte hesaplandı)')
            self.timeline.update()
        except (ValueError, Exception) as err:
            self.timeline.total_free = 0
            self.timeline.study_windows = []
            if hasattr(self, 'lbl_advanced_capacity'):
                self.lbl_advanced_capacity.setText('⚠️ Saatleri kontrol edin: ' + str(err))
            self.timeline.update()

    def _on_student_type_changed(self, *_):
        school = self.cmb_student_type.currentIndex() == 0
        self.widget_school_times.setVisible(school)
        for child in self.widget_school_times.findChildren(QWidget):
            child.setVisible(school)
        self.chk_school.setChecked(school)
        self._refresh_timeline()

    def _on_standard_school_time_changed(self):
        s_time = self.time_school_start.time()
        e_time = self.time_school_end.time()
        for idx in range(5):
            if hasattr(self, 'school_day_start') and idx < len(self.school_day_start):
                self.school_day_start[idx].setTime(s_time)
            if hasattr(self, 'school_day_end') and idx < len(self.school_day_end):
                self.school_day_end[idx].setTime(e_time)
        self._refresh_timeline()

    def _add_block_item(self):
        day = self.cmb_block_day.currentText()
        st = self.time_block_start.time().toString("HH:mm")
        et = self.time_block_end.time().toString("HH:mm")
        desc = self.txt_block_desc.text().strip() or "Meşgul / Rutin"
        
        item_text = f"{day} [{st}-{et}] {desc}"
        try:
            parse_block(item_text)
        except ValueError as err:
            QMessageBox.warning(self, "Geçersiz Rutin", str(err))
            return
        if item_text in [self.lst_blocks.item(i).text() for i in range(self.lst_blocks.count())]:
            QMessageBox.information(self, "Bilgi", "Bu rutin zaten eklenmiş.")
            return
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
        # Only the homework lesson names are available in this dialog. Do NOT
        # falsely claim to have measured actual exam performance or weaknesses.
        from collections import Counter
        from html import escape
        names = [str(x).strip() for x in self.lesson_names if str(x).strip()]
        if not names:
            QMessageBox.information(self, 'Ödev Dersleri',
                'Mevcut ödev listesinde ders bilgisi yok. Öncelikli dersleri elle seçebilirsiniz.')
            return
        distribution = Counter(names)
        most_common = distribution.most_common(3)
        msg = ('<h3>📊 Mevcut Ödevlerden Ders Dağılımı</h3>'
               '<p>Bu öneri sadece Verilen Ödevler listesindeki ders sıklığına dayanır. '
               '<b>Sınav sonuçları ve öğrenme eksikleri analiz edilmemiştir.</b></p><ul>')
        for name, n in most_common:
            msg += f'<li>{escape(name)}: {n} görev</li>'
        msg += '</ul><p>Bu derslerin takvimde öncelikli olmasını isterseniz listeye ekleyebilirsiniz.</p>'
        if QMessageBox.question(self, 'Ders Önceliği Önerisi', msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            current = [x.strip() for x in self.txt_focus.text().split(',') if x.strip()]
            known = {x.casefold() for x in current}
            for lesson, _ in most_common:
                if lesson.casefold() not in known:
                    current.append(lesson)
                    known.add(lesson.casefold())
            self.txt_focus.setText(', '.join(current))

    def _gather_data(self) -> Dict[str, Any]:
        p_idx = self.cmb_student_type.currentIndex()
        school_by_day = {}
        if p_idx == 0:
            for idx in range(7):
                if self.school_day_checks[idx].isChecked():
                    school_by_day[str(idx)] = [
                        self.school_day_start[idx].time().toString('HH:mm'),
                        self.school_day_end[idx].time().toString('HH:mm')]
        school_str = 'Yok'
        if school_by_day:
            school_str = school_by_day.get('0') or next(iter(school_by_day.values()))
            if isinstance(school_str, list):
                school_str = '-'.join(school_str)
        weekend_mode = 'Hafif' if self.rb_w_relax.isChecked() else 'Yoğun' if self.rb_w_hard.isChecked() else 'Dengeli'
        empty = self.cmb_empty_day.currentText() if self.chk_empty_day.isChecked() else 'Yok'
        return {
            'planner_version': 2, 'profile_idx': p_idx, 'school': school_str,
            'school_by_day': school_by_day,
            'wake': self.time_wake.time().toString('HH:mm'),
            'sleep': self.time_sleep.time().toString('HH:mm'),
            'max': self.spin_max.value(),
            'weekend_mode': weekend_mode,
            'biorhythm': self.cmb_bio.currentText(),
            'blocks': [self.lst_blocks.item(i).text() for i in range(self.lst_blocks.count())],
            'focus': self.txt_focus.text(), 'empty': empty,
            'note': self.txt_notes.toPlainText(),
            'after_school_buffer': self.spin_after_school.value() if p_idx == 0 else 0,
            'after_routine_buffer': self.spin_after_routine.value(),
            'session_enabled': self.chk_sessions.isChecked(),
            'session_minutes': self.spin_session_minutes.value(),
            'session_break': self.spin_session_break.value(),
            'session_split': self.chk_session_split.isChecked(),
            'advanced_enabled': self.chk_advanced.isChecked(),
            'advanced_days': {
                str(i): {
                    'wake': self.day_wake[i].time().toString('HH:mm'),
                    'bed': self.day_bed[i].time().toString('HH:mm'),
                    'study_start': self.day_override_start[i].time().toString('HH:mm'),
                    'study_end': self.day_override_end[i].time().toString('HH:mm'),
                    'max': self.day_override_max[i].value(),
                    **({'second_window': [self.second_start[i].time().toString('HH:mm'),
                                           self.second_end[i].time().toString('HH:mm')]}
                       if self.second_checks[i].isChecked() else {}),
                }
                for i in range(7) if self.day_override_checks[i].isChecked()
            },
            # Eski takvim motorlarına ve eski kayıtlara geriye uyumluluk.
            'day_overrides': {
                str(i): {
                    'wake': self.day_override_start[i].time().toString('HH:mm'),
                    'sleep': self.day_override_end[i].time().toString('HH:mm'),
                    'max': self.day_override_max[i].value(),
                }
                for i in range(7) if self.day_override_checks[i].isChecked()
            },
        }

    def _apply_data(self, data: Dict[str, Any]):
        try:
            p_idx = int(data.get("profile_idx", 0))
            self.cmb_student_type.setCurrentIndex(p_idx)
            self.widget_school_times.setVisible(p_idx == 0)
            for child in self.widget_school_times.findChildren(QWidget):
                child.setVisible(p_idx == 0)
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

        by_day = data.get('school_by_day')
        if by_day is None:  # read legacy profiles without losing weekdays
            by_day = {str(i): sc.split('-') for i in range(5)} if sc != 'Yok' else {}
        for i in range(7):
            pair = by_day.get(str(i))
            self.school_day_checks[i].setChecked(bool(pair))
            if pair and len(pair) == 2:
                self.school_day_start[i].setTime(QTime.fromString(pair[0], 'HH:mm'))
                self.school_day_end[i].setTime(QTime.fromString(pair[1], 'HH:mm'))
        self.time_wake.setTime(QTime.fromString(data.get('wake', '07:00'), 'HH:mm'))
        self.time_sleep.setTime(QTime.fromString(data.get('sleep', '23:30'), 'HH:mm'))
        self.spin_after_school.setValue(int(data.get('after_school_buffer', 0)))
        self.spin_after_routine.setValue(int(data.get('after_routine_buffer', 0)))
        self.spin_session_minutes.setValue(int(data.get('session_minutes', 45)))
        self.spin_session_break.setValue(int(data.get('session_break', 10)))
        self.chk_session_split.setChecked(bool(data.get('session_split', True)))
        self.chk_sessions.setChecked(bool(data.get('session_enabled', False)))
        day_overrides = data.get('day_overrides', {}) or {}
        advanced_days = data.get('advanced_days', {}) or {}
        # Önceki sürümdeki özelleştirilmiş günleri otomatik içe al.
        self.chk_advanced.setChecked(bool(data.get('advanced_enabled', bool(day_overrides or advanced_days))))
        for i in range(7):
            legacy = day_overrides.get(str(i), {}) or {}
            override = advanced_days.get(str(i), {}) or {}
            has_custom = bool(legacy or override)
            self.day_override_checks[i].setChecked(has_custom)
            first_start = override.get('study_start', legacy.get('wake', data.get('wake', '07:00')))
            first_end = override.get('study_end', legacy.get('sleep', data.get('sleep', '23:30')))
            wake_time = override.get('wake', data.get('wake', '07:00'))
            bed_time = override.get('bed', data.get('sleep', '23:30'))
            if not override and legacy:
                # Eski V2 profillerinde 'wake/sleep' çalışma saatleridir;
                # gerçek yatış-uyanış bilgisi yoktur. Mevcut çalışma alanını daraltma.
                from services.planning_constraints import to_minutes, hhmm
                wake_time = hhmm(min(to_minutes(wake_time), to_minutes(first_start)))
                bed_time = hhmm(max(to_minutes(bed_time), to_minutes(first_end)))
            self.day_wake[i].setTime(QTime.fromString(wake_time, 'HH:mm'))
            self.day_bed[i].setTime(QTime.fromString(bed_time, 'HH:mm'))
            self.day_override_start[i].setTime(QTime.fromString(first_start, 'HH:mm'))
            self.day_override_end[i].setTime(QTime.fromString(first_end, 'HH:mm'))
            self.day_override_max[i].setValue(int(override.get('max', legacy.get('max', data.get('max', 180)))))
            second = override.get('second_window')
            self.second_checks[i].setChecked(bool(second))
            if isinstance(second, (tuple, list)) and len(second) == 2:
                self.second_start[i].setTime(QTime.fromString(second[0], 'HH:mm'))
                self.second_end[i].setTime(QTime.fromString(second[1], 'HH:mm'))
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
        self.cmb_profiles.addItem('Varsayılan Standart Ayarlar', None)
        try:
            self.profiles = load_profiles()
        except Exception as err:
            self.profiles = {}
            QMessageBox.warning(self, 'Profil Okunamadı',
                                f'Kayıtlı profiller okunamadı, dosyaya dokunulmadı: {err}')
        for name in sorted(self.profiles):
            self.cmb_profiles.addItem(f'👤 {name}', name)
        self.cmb_profiles.blockSignals(False)

    def _persist_profiles(self, updated: Dict[str, Any]) -> bool:
        try:
            save_profiles(updated)
        except Exception as err:
            QMessageBox.warning(self, 'Profil Kayıt Hatası', f'Profil kaydedilemedi: {err}')
            return False
        self.profiles = updated
        self._load_profiles()
        return True

    def _restore_student_profile(self):
        if not self.student_id:
            return
        try:
            name = load_assignments().get(self.student_id)
        except (OSError, ValueError, json.JSONDecodeError):
            return
        idx = self.cmb_profiles.findData(name) if name else -1
        if idx >= 0:
            self.cmb_profiles.setCurrentIndex(idx)

    def _assign_to_student(self, silent: bool = False):
        name = self.cmb_profiles.currentData()
        if not self.student_id or not name:
            QMessageBox.information(self, 'Öğrenci Profili', 'Önce kaydedilmiş bir profil seçin.')
            return
        try:
            entries = load_assignments()
            entries[self.student_id] = name
            save_assignments(entries)
        except Exception as err:
            QMessageBox.warning(self, 'Öğrenciye Atanamadı', str(err))
            return
        if not silent:
            QMessageBox.information(self, 'Başarılı', f'{self.student_name or "Öğrenci"} için profil ilişkilendirildi.')

    def _save_current_profile(self):
        name, ok = QInputDialog.getText(self, 'Profil Kaydet', 'Profil ismi (örn. Öğrenci – 7A):')
        name = name.strip()
        if not ok or not name:
            return
        if name in self.profiles:
            QMessageBox.warning(self, 'Aynı İsim', 'Bu isimde profil mevcut. Güncelle düğmesini kullanın.')
            return
        try:
            data = self._gather_data()
            availability_for_week(data)
        except ValueError as err:
            QMessageBox.warning(self, 'Geçersiz Plan Kuralları', str(err))
            return
        updated = dict(self.profiles)
        updated[name] = data
        if self._persist_profiles(updated):
            idx = self.cmb_profiles.findData(name)
            if idx >= 0:
                self.cmb_profiles.setCurrentIndex(idx)
            if self.student_id:
                self._assign_to_student(silent=True)
            QMessageBox.information(self, 'Başarılı', f'Profil kaydedildi.\n{profile_path()}')

    def _update_current_profile(self):
        curr = self.cmb_profiles.currentData()
        if not curr:
            QMessageBox.information(self, 'Profil Güncelle', 'Önce kayıtlı bir profil seçin.')
            return
        if QMessageBox.question(self, 'Profil Güncelle', f'{curr} güncellensin mi?',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            data = self._gather_data()
            availability_for_week(data)
        except ValueError as err:
            QMessageBox.warning(self, 'Geçersiz Plan Kuralları', str(err))
            return
        updated = dict(self.profiles)
        # Preserve personal ownership and last applied observation when the
        # teacher manually saves other routine settings.
        for key in ('_session_advisor_owner', '_session_advisor_last_applied',
                    '_session_advisor_source'):
            if key in updated[curr]:
                data[key] = updated[curr][key]
        updated[curr] = data
        if self._persist_profiles(updated):
            self.cmb_profiles.setCurrentIndex(self.cmb_profiles.findData(curr))
            QMessageBox.information(self, 'Başarılı', f'{curr} güncellendi.')

    def _delete_profile(self):
        curr = self.cmb_profiles.currentData()
        if not curr:
            return
        if QMessageBox.question(self, 'Profil Sil', f'{curr} silinsin mi?',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        updated = dict(self.profiles)
        updated.pop(curr, None)
        self._persist_profiles(updated)

    def _session_homework_context(self) -> dict:
        # Opening the planner may not create/migrate DB tables. Read only.
        if not self.student_id:
            return {'available': False, 'due': 0, 'done': 0}
        try:
            import db
            dbfile = db.DB_PATH
            if not dbfile.is_file():
                return {'available': False, 'due': 0, 'done': 0}
            uri = dbfile.resolve().as_uri() + '?mode=ro'
            with sqlite3.connect(uri, uri=True, timeout=2) as con:
                return homework_summary(con, self.student_id)
        except (ImportError, OSError, sqlite3.Error, AttributeError):
            return {'available': False, 'due': 0, 'done': 0}

    def _refresh_session_advice(self):
        current_name = self.cmb_profiles.currentData()
        profile = self.profiles.get(current_name, {}) if current_name else {}
        self._session_advice = None
        self.btn_accept_session_advice.setEnabled(False)
        if not self.student_id:
            self.lbl_session_advice.setText('Kişiselleştirilmiş öneri için kayıtlı öğrenci seçilmelidir.')
            return
        if not profile:
            self.lbl_session_advice.setText('Önce profili kaydedin veya kayıtlı bir profil seçin.')
            return
        try:
            feedback = recent_feedback(self.student_id)
            homework = self._session_homework_context()
            suggestion = suggest_session_minutes(
                profile.get('session_minutes', 45), feedback, homework,
                profile.get('_session_advisor_last_applied'))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.lbl_session_advice.setText(f'Etüt önerisi okunamadı: {exc}. Profil değiştirilmedi.')
            return
        self._session_advice = suggestion
        context = (f"Son 60 günde vadesi geçmiş {homework['due']} ödevden "
                   f"{homework['done']} tamamlanmış (etüt süresini ölçmez)."
                   if homework.get('available') and homework.get('due') else
                   'Tamamlanmış ödev kaydı yok veya erişilemiyor; çalışma süresi tahmin edilmiyor.')
        target = suggestion['suggested']
        title = (f'Öneri: {target} dk. ' if suggestion['ready'] else 'Mevcut oturum korunuyor. ')
        self.lbl_session_advice.setText(title + suggestion['reason'] + '\n' + context)
        self.btn_accept_session_advice.setEnabled(bool(suggestion['ready']))

    def _record_session_feedback(self, rating: str):
        if not self.student_id:
            return
        try:
            record_feedback(self.student_id, rating)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, 'Gözlem Kaydedilemedi', str(exc))
            return
        self._refresh_session_advice()

    def _apply_session_advice(self):
        """One click changes ONLY a personal, saved profile; never a shared template."""
        name = self.cmb_profiles.currentData()
        if not name or not self.student_id:
            return
        # Re-evaluate on click; a stale button must never apply an old estimate.
        self._refresh_session_advice()
        suggestion = self._session_advice
        if not suggestion or not suggestion['ready']:
            return
        try:
            updated = dict(load_profiles())  # don't overwrite concurrent saved profiles
            source = updated.get(name)
            if not isinstance(source, dict):
                raise ValueError('Profil başka bir işlemde değişmiş. Yeniden seçin.')
            observed = recent_feedback(self.student_id)
            new_suggestion = suggest_session_minutes(
                source.get('session_minutes', 45), observed,
                self._session_homework_context(), source.get('_session_advisor_last_applied'))
            if not new_suggestion['ready'] or new_suggestion['signature'] != suggestion['signature']:
                self._refresh_session_advice()
                return
            updated, target_name = personal_profile_update(
                updated, name, self.student_id,
                new_suggestion['suggested'], new_suggestion['signature'])
            personal = updated[target_name]
            availability_for_week(personal)  # reject invalid settings before write
            save_profiles(updated)
            entries = load_assignments()
            entries[self.student_id] = target_name
            save_assignments(entries)
        except Exception as exc:
            QMessageBox.warning(self, 'Etüt Önerisi Kaydedilemedi',
                                f'Profil değişikliği tamamlanamadı: {exc}')
            return
        self.profiles = updated
        self._load_profiles()
        self.cmb_profiles.setCurrentIndex(self.cmb_profiles.findData(target_name))
        self._on_profile_changed()
        QMessageBox.information(self, 'Etüt Ayarı Kaydedildi',
            f'Bu öğrenciye özel profil: {target_name}\n'
            f'Etüt süresi: {new_suggestion["suggested"]} dk.\n'
            'Diğer öğrencilerin profilleri ve ödevleri değiştirilmedi.')

    def _on_profile_changed(self):
        name = self.cmb_profiles.currentData()
        if name and name in self.profiles:
            self._apply_data(self.profiles[name])
        else:
            self.cmb_student_type.setCurrentIndex(0)
            self.widget_school_times.setVisible(True)
            for child in self.widget_school_times.findChildren(QWidget):
                child.setVisible(True)
            self.chk_school.setChecked(True)
            self.time_school_start.setTime(QTime(8, 30))
            self.time_school_end.setTime(QTime(15, 40))
            self.spin_max.setValue(180)
            self.rb_w_normal.setChecked(True)
            self.cmb_bio.setCurrentIndex(0)
            self.txt_focus.clear()
            self.chk_empty_day.setChecked(False)
            self.txt_notes.clear()
            self.lst_blocks.clear()
            self.time_wake.setTime(QTime(7, 0))
            self.time_sleep.setTime(QTime(23, 30))
            self.spin_after_school.setValue(30)
            self.spin_after_routine.setValue(0)
            self.spin_session_minutes.setValue(45)
            self.spin_session_break.setValue(10)
            self.chk_session_split.setChecked(True)
            self.chk_sessions.setChecked(False)
            for idx in range(7):
                self.day_override_checks[idx].setChecked(False)
                self.day_override_start[idx].setTime(QTime(7, 0))
                self.day_override_end[idx].setTime(QTime(23, 30))
                self.day_override_max[idx].setValue(180)
                self.day_wake[idx].setTime(QTime(7, 0))
                self.day_bed[idx].setTime(QTime(23, 30))
                self.second_checks[idx].setChecked(False)
                self.second_start[idx].setTime(QTime(20, 0))
                self.second_end[idx].setTime(QTime(22, 0))
            self.chk_advanced.setChecked(False)
            for idx in range(7):
                self.school_day_checks[idx].setChecked(idx < 5)
                self.school_day_start[idx].setTime(QTime(8, 30))
                self.school_day_end[idx].setTime(QTime(15, 40))
            self._refresh_timeline()
        self._refresh_session_advice()

    def _on_overview_tab_selected(self, index: int) -> None:
        # Hesaplamaları yalnızca özet sekmesi açıldığında yap; Windows'ta
        # checkbox tıklamaları veya profil kaydı sırasında ek yük oluşturma.
        if index == 0 and hasattr(self, 'weekly_overview'):
            self.weekly_overview.refresh()

    def _create_plan(self):
        data = self._gather_data()
        approved = getattr(self, '_approved_topic_focus', [])
        if approved:
            parent = self.parent()
            if (parent is not None and hasattr(parent, '_secili_ogrenci_id')
                    and str(parent._secili_ogrenci_id() or '') != str(self.student_id or '')):
                QMessageBox.warning(self, 'Öğrenci Değişti',
                                    'Öğrenci seçimi değişti. Adaptif öncelikler uygulanmadı.')
                return
            from services.weekly_topic_priority_v35 import accepted_topic_pairs
            # Only currently assigned exact pairs; the shared profile is unchanged.
            data['adaptive_topic_focus_v35'] = accepted_topic_pairs(self.homework_list, approved)
        try:
            availability = availability_for_week(data)
        except ValueError as err:
            QMessageBox.warning(self, 'Takvim Kuralları Geçersiz', str(err))
            return
        if not any(availability.values()):
            QMessageBox.warning(self, 'Çalışma Saati Bulunamadı',
                                'Seçilen rutinlerle haftanın hiçbir gününde çalışma saati kalmıyor.')
            return
        self.result_details = serialize_details(data)
        self.accept()

    def get_details(self) -> str:
        return self.result_details
