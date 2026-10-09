# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QLineEdit, QProgressBar, QFrame, QScrollArea, QWidget, QCompleter, 
    QCheckBox, QTabWidget, QMessageBox, QApplication, QGridLayout
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from services.exam_data import (
    get_exam_data, get_available_years, get_available_cities, 
    get_available_categories, ALL_EXAM_DATA
)
from ui.advanced_analytics import AdvancedNetAndTrendPanel
import db


class TargetAnalysisDialog(QDialog):
    """
    Akıllı Hedef ve Sıralama Sihirbazı (V3 - Çok Yıllı 2024, 2025 & 2026)
    - Tab 1: Akıllı Hedef Analizi (Gap Analysis / Hedef vs Gerçekleşen)
    - Tab 2: Performans & Trend Takibi (Resmi ÖSYM & MEB Karşılaştırması)
    """

    def __init__(self, parent=None, student_id=None):
        super().__init__(parent)
        self.student_id = student_id
        
        # Eğer student_id verilmediyse DB'den ilk öğrenciyi al
        if not self.student_id:
            try:
                con = db.get_conn()
                row = con.execute("SELECT id FROM ogrenci WHERE aktif=1 ORDER BY ad, soyad LIMIT 1").fetchone()
                if not row:
                    row = con.execute("SELECT id FROM ogrenci ORDER BY ad, soyad LIMIT 1").fetchone()
                if row: 
                    self.student_id = row[0]
            except Exception: 
                pass

        self.setWindowTitle("🎯 Akıllı Hedef Analizi ve Performans Merkezi (2024 - 2025 - 2026)")
        
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(1150, int(screen.width() * 0.88))
        h = min(880, int(screen.height() * 0.88))
        self.resize(w, h)
        self.setMinimumSize(750, 560)
        
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif; }
            QLabel { color: #334155; }
            QLineEdit, QComboBox {
                padding: 10px 12px;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background: white;
                font-size: 13px;
                color: #0f172a;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 2px solid #2563eb;
            }
            QPushButton#ActionBtn {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
            }
            QPushButton#ActionBtn:hover { background-color: #1d4ed8; }
            
            QPushButton#SearchBtn {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: 600;
                border-radius: 8px;
                padding: 8px 14px;
                border: 1px solid #cbd5e1;
            }
            QPushButton#SearchBtn:hover { background-color: #e2e8f0; color: #0f172a; }

            QFrame#Card {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QTabWidget::pane { border: 0; }
            QTabBar::tab {
                background: #e2e8f0;
                color: #64748b;
                padding: 12px 22px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #2563eb;
                border-bottom: 3px solid #2563eb;
            }
            QTabBar::tab:hover {
                background: #cbd5e1;
                color: #1e293b;
            }
        """)

        lay_main = QVBoxLayout(self)
        lay_main.setContentsMargins(14, 12, 14, 12)
        lay_main.setSpacing(10)
        
        # --- ÜST ÖĞRENCİ SEÇİM ÇUBUĞU ---
        top_bar = QFrame()
        top_bar.setObjectName("Card")
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(14, 8, 14, 8)
        top_lay.setSpacing(12)
        
        top_lay.addWidget(QLabel("<b>👤 Aktif Öğrenci:</b>"))
        self.cmb_student = QComboBox()
        self.cmb_student.setMinimumWidth(260)
        self._load_students_list()
        self.cmb_student.currentIndexChanged.connect(self._on_student_combo_changed)
        top_lay.addWidget(self.cmb_student)
        
        self.btn_fetch_deneme = QPushButton("📥 Son Deneme Netlerini Doldur")
        self.btn_fetch_deneme.setObjectName("SearchBtn")
        self.btn_fetch_deneme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fetch_deneme.setToolTip("Öğrencinin sistemdeki en son deneme sınavı netlerini otomatik forma doldurur.")
        self.btn_fetch_deneme.clicked.connect(self._fetch_latest_student_deneme)
        top_lay.addWidget(self.btn_fetch_deneme)
        
        top_lay.addStretch(1)
        lay_main.addWidget(top_bar)
        
        # Tabs
        self.tabs = QTabWidget()
        lay_main.addWidget(self.tabs, 1)
        
        # --- TAB 1: Hedef Analizi (Gap Analysis) ---
        self.tab_target = QWidget()
        self._init_target_tab(self.tab_target)
        self.tabs.addTab(self.tab_target, "🎯 Hedef Analizi (Gap Analysis)")
        
        # --- TAB 2: Performans & Trend Takibi ---
        self.tab_advanced = AdvancedNetAndTrendPanel(student_id=self.student_id)
        self.tabs.addTab(self.tab_advanced, "📈 Performans & Trend Takibi")

        self._load_student_target()

    def _load_students_list(self):
        """Öğrenci açılır kutusunu doldurur."""
        try:
            con = db.get_conn()
            rows = con.execute("SELECT id, ad, soyad FROM ogrenci WHERE aktif=1 ORDER BY ad, soyad").fetchall()
            if not rows:
                rows = con.execute("SELECT id, ad, soyad FROM ogrenci ORDER BY ad, soyad").fetchall()
                
            self.cmb_student.blockSignals(True)
            self.cmb_student.clear()
            sel_idx = 0
            for i, r in enumerate(rows):
                s_id = r[0]
                ad_soyad = f"{r[1]} {r[2]}".strip()
                self.cmb_student.addItem(f"{s_id} • {ad_soyad}", s_id)
                if self.student_id and s_id == self.student_id:
                    sel_idx = i
                    
            self.cmb_student.setCurrentIndex(sel_idx)
            self.cmb_student.blockSignals(False)
        except Exception as e:
            print("Öğrenci listesi hatası:", e)

    def _on_student_combo_changed(self):
        new_id = self.cmb_student.currentData()
        if new_id:
            self.student_id = int(new_id)
            if hasattr(self, "tab_advanced") and self.tab_advanced:
                self.tab_advanced.set_student_id(self.student_id)
            self._load_student_target()

    def _fetch_latest_student_deneme(self):
        """Öğrencinin kayıtlı son deneme netlerini çeker ve giriş alanlarına doldurur."""
        if not self.student_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir öğrenci seçin.")
            return
            
        try:
            con = db.get_conn()
            # En son deneme
            d_row = con.execute("""
                SELECT d.id, d.tarih, d.deneme_adi, d.tur
                FROM deneme_sonuclari ds
                JOIN denemeler d ON d.id = ds.deneme_id
                WHERE ds.ogrenci_id = ?
                ORDER BY d.tarih DESC, d.id DESC LIMIT 1
            """, (self.student_id,)).fetchone()
            
            if not d_row:
                QMessageBox.information(self, "Bilgi", "Seçili öğrenciye ait kayıtlı deneme sınavı bulunamadı.")
                return
                
            d_id, d_tarih, d_adi, d_tur = d_row
            
            # Sınav türüne göre netleri çek
            results = con.execute("""
                SELECT ders_adi, net FROM deneme_sonuclari 
                WHERE deneme_id=? AND ogrenci_id=?
            """, (d_id, self.student_id)).fetchall()
            
            exam = self.cb_exam.currentText()
            
            if "YKS" in exam:
                tyt_total = sum(float(r[1] or 0) for r in results if "TYT" in (r[0] or "").upper())
                ayt_total = sum(float(r[1] or 0) for r in results if "AYT" in (r[0] or "").upper() or "YDT" in (r[0] or "").upper())
                
                # Eğer ders isimlerinde TYT/AYT ayrımı yoksa akıllı dağıt
                if tyt_total == 0 and ayt_total == 0:
                    tot = sum(float(r[1] or 0) for r in results)
                    tyt_total = round(tot * 0.6, 1)
                    ayt_total = round(tot * 0.4, 1)
                    
                self.inp_net1.setText(str(round(tyt_total, 1)))
                self.inp_net2.setText(str(round(ayt_total, 1)))
                QMessageBox.information(
                    self, "Netler Aktarıldı", 
                    f"Son Deneme ({d_adi} - {d_tarih}) netleri aktarıldı:\n• TYT: {tyt_total:.1f}\n• AYT: {ayt_total:.1f}"
                )
            else: # LGS
                lgs_total = sum(float(r[1] or 0) for r in results)
                self.inp_net1.setText(str(round(lgs_total, 1)))
                QMessageBox.information(
                    self, "Netler Aktarıldı", 
                    f"Son LGS Denemesi ({d_adi} - {d_tarih}) neti aktarıldı:\n• Toplam Net: {lgs_total:.1f} / 90"
                )
                
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Deneme netleri çekilirken hata oluştu: {e}")

    def _init_target_tab(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        slayout = QVBoxLayout(scroll_content)
        slayout.setSpacing(18)
        slayout.setContentsMargins(24, 20, 24, 24)

        # Başlık Alanı
        h_lay = QHBoxLayout()
        icon = QLabel("🚀")
        icon.setStyleSheet("font-size: 40px;")
        
        v_head = QVBoxLayout()
        lbl_title = QLabel("Hedef vs. Gerçekleşen (Gap Analysis)")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #0f172a;")
        lbl_desc = QLabel("2024, 2025 ve 2026 Projeksiyon verilerini kullanarak hedeflediğin bölüm veya liseye ne kadar yakın olduğunu gör.")
        lbl_desc.setStyleSheet("font-size: 13px; color: #64748b;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_desc)
        
        h_lay.addWidget(icon)
        h_lay.addLayout(v_head)
        h_lay.addStretch()
        slayout.addLayout(h_lay)

        # Form Kartı
        self.form_frame = QFrame()
        self.form_frame.setObjectName("Card")
        form_lay = QVBoxLayout(self.form_frame)
        form_lay.setContentsMargins(22, 20, 22, 20)
        form_lay.setSpacing(16)

        # Grid: 1. Sınav Türü, 2. Yıl Seçimi, 3. Şehir Filtresi
        grid_selectors = QGridLayout()
        grid_selectors.setHorizontalSpacing(14)
        grid_selectors.setVerticalSpacing(6)

        grid_selectors.addWidget(QLabel("<b>1. Sınav Türünü Seç:</b>"), 0, 0)
        self.cb_exam = QComboBox()
        self.cb_exam.addItems(["YKS-SAY", "YKS-EA", "YKS-SÖZ", "YKS-DİL", "LGS"])
        self.cb_exam.currentIndexChanged.connect(self._on_exam_change)
        grid_selectors.addWidget(self.cb_exam, 1, 0)

        grid_selectors.addWidget(QLabel("<b>2. Analiz / Projeksiyon Yılı:</b>"), 0, 1)
        self.cb_year = QComboBox()
        self.cb_year.addItems([
            "2025 (Son Yerleştirme Verisi - Güncel)", 
            "2026 (Akıllı Projeksiyon & Güvenli Hedef)", 
            "2024 (ÖSYM Taban Referans)"
        ])
        self.cb_year.currentIndexChanged.connect(self._on_year_change)
        grid_selectors.addWidget(self.cb_year, 1, 1)

        grid_selectors.addWidget(QLabel("<b>3. Şehir Filtresi:</b>"), 0, 2)
        self.cb_city = QComboBox()
        self.cb_city.currentIndexChanged.connect(self._on_filter_changed)
        grid_selectors.addWidget(self.cb_city, 1, 2)

        form_lay.addLayout(grid_selectors)

        # 4. Hedef Okul/Bölüm Seçimi
        row_target_label = QHBoxLayout()
        row_target_label.addWidget(QLabel("<b>4. Hedef Okul / Bölüm Seç:</b>"))
        row_target_label.addStretch()
        
        self.btn_search = QPushButton("🌍 Bu Bölümü İnternette Ara (YÖK Atlas / Google)")
        self.btn_search.setObjectName("SearchBtn")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.clicked.connect(self._search_online)
        self.btn_search.setVisible(True)
        row_target_label.addWidget(self.btn_search)
        form_lay.addLayout(row_target_label)

        self.cb_target = QComboBox()
        self.cb_target.setEditable(True) 
        self.cb_target.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.cb_target.currentIndexChanged.connect(self._on_target_change)
        self.cb_target.setMinimumHeight(44)
        form_lay.addWidget(self.cb_target)

        # Manuel Giriş Alanı
        self.manual_frame = QFrame()
        self.manual_frame.setObjectName("Card")
        self.manual_frame.setStyleSheet("background: #f8fafc; border: 1px dashed #94a3b8; border-radius: 8px;")
        self.manual_frame.setVisible(False)
        manual_lay = QVBoxLayout(self.manual_frame)
        manual_lay.setContentsMargins(14, 12, 14, 12)
        manual_lay.setSpacing(10)
        
        lbl_info = QLabel("<b>✏️ Manuel Veri Girişi:</b> Listede bulamadığınız okul/bölümün net hedeflerini buraya manuel yazın.")
        lbl_info.setStyleSheet("color: #334155; font-size: 12px;")
        manual_lay.addWidget(lbl_info)
        
        self.goal_input_lay = QHBoxLayout()
        self.inp_goal_1 = QLineEdit(); self.inp_goal_1.setPlaceholderText("Hedef TYT Neti")
        self.inp_goal_2 = QLineEdit(); self.inp_goal_2.setPlaceholderText("Hedef AYT/YDT Neti")
        self.goal_input_lay.addWidget(self.inp_goal_1)
        self.goal_input_lay.addWidget(self.inp_goal_2)
        manual_lay.addLayout(self.goal_input_lay)
        form_lay.addWidget(self.manual_frame)

        # Güvenli Hedef Checkbox
        self.chk_trend = QCheckBox("🛡️ 2026 Güvenli Hedef Katsayısı Uygula (%2.5 Yığılma & Rekabet Güvencesi)")
        self.chk_trend.setStyleSheet("font-size: 13px; color: #0f172a; font-weight: 600;")
        self.chk_trend.setToolTip("Sınavdaki yığılma ve rekabet artışını kompanse etmek için gereken net hedeflerini %2.5 artırarak güvenli bir çalışma çıtası belirler.")
        form_lay.addWidget(self.chk_trend)

        # 5. Güncel Netlerin
        self.lbl_input = QLabel("<b>5. Güncel Netlerin (Deneme Sınavı Sonuçların):</b>") 
        self.lbl_input.setStyleSheet("margin-top: 6px;")
        form_lay.addWidget(self.lbl_input)
        
        input_row = QHBoxLayout()
        self.inp_net1 = QLineEdit()
        self.inp_net1.setPlaceholderText("Senin TYT Netin")
        self.inp_net2 = QLineEdit() 
        self.inp_net2.setPlaceholderText("Senin AYT / YDT Netin")
        
        input_row.addWidget(self.inp_net1)
        input_row.addWidget(self.inp_net2)
        form_lay.addLayout(input_row)

        slayout.addWidget(self.form_frame)

        # Aksiyon Butonu
        self.btn_analyze = QPushButton("🚀 Analiz Et & Hedefi Öğrenciye Kaydet")
        self.btn_analyze.setObjectName("ActionBtn")
        self.btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_analyze.clicked.connect(self._analyze)
        slayout.addWidget(self.btn_analyze)

        # Sonuç Kartı
        self.res_frame = QFrame()
        self.res_frame.setVisible(False)
        self.res_frame.setStyleSheet("""
            QFrame {
                background: #ffffff; 
                border: 1px solid #cbd5e1; 
                border-radius: 12px;
            }
        """)
        res_lay = QVBoxLayout(self.res_frame)
        res_lay.setContentsMargins(20, 18, 20, 18)
        res_lay.setSpacing(12)
        
        self.lbl_res_title = QLabel("Analiz Sonucu")
        self.lbl_res_title.setStyleSheet("font-weight: 800; font-size: 16px; color: #0f172a;")
        
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                text-align: center;
                background-color: #f1f5f9;
                height: 24px;
                font-weight: bold;
                font-size: 12px;
                color: #1e293b;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 5px;
            }
        """)
        self.progress.setFixedHeight(24)

        self.lbl_res_desc = QLabel()
        self.lbl_res_desc.setWordWrap(True)
        self.lbl_res_desc.setStyleSheet("font-size: 13px; line-height: 1.5; color: #1e293b;")

        res_lay.addWidget(self.lbl_res_title)
        res_lay.addWidget(self.progress)
        res_lay.addWidget(self.lbl_res_desc)
        
        slayout.addWidget(self.res_frame)
        slayout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self._on_exam_change()

    def _get_selected_year(self) -> int:
        txt = self.cb_year.currentText()
        if "2024" in txt: return 2024
        if "2026" in txt: return 2026
        return 2025

    def _on_year_change(self):
        self._populate_target_schools()

    def _on_filter_changed(self):
        self._populate_target_schools()

    def _on_exam_change(self):
        exam = self.cb_exam.currentText()
        
        # Şehirleri güncelle
        cities = get_available_cities(exam)
        self.cb_city.blockSignals(True)
        self.cb_city.clear()
        self.cb_city.addItems(cities)
        self.cb_city.blockSignals(False)

        # Arayüz etiketleri
        if "YKS" in exam:
            if "DİL" in exam:
                self.lbl_input.setText("<b>5. Güncel Netlerin (Örn: TYT 65, YDT 70):</b>")
                self.inp_net1.setPlaceholderText("TYT Netin (120 Soru)")
                self.inp_net2.setPlaceholderText("YDT Netin (80 Soru)")
                self.inp_goal_2.setPlaceholderText("Hedef YDT Neti (80 Soru)")
            else:
                self.lbl_input.setText("<b>5. Güncel Netlerin (Örn: TYT 75, AYT 50):</b>")
                self.inp_net1.setPlaceholderText("TYT Netin (120 Soru)")
                self.inp_net2.setPlaceholderText("AYT Netin (80 Soru)")
                self.inp_goal_2.setPlaceholderText("Hedef AYT Neti (80 Soru)")
                
            self.inp_net1.setVisible(True)
            self.inp_net2.setVisible(True)
            self.inp_goal_1.setPlaceholderText("Hedef TYT Neti")
            self.inp_goal_2.setVisible(True)
            self.chk_trend.setText("🛡️ 2026 Güvenli Hedef Katsayısı Uygula (+%2.5 Katsayı Güvencesi)")
        else: # LGS
            self.lbl_input.setText("<b>5. Güncel Toplam Net (LGS - 90 Soru Üzerinden):</b>")
            self.inp_net1.setPlaceholderText("Toplam LGS Netin (Max 90)")
            self.inp_net2.setVisible(False)
            self.inp_goal_1.setPlaceholderText("Hedef Toplam Net (Max 90)")
            self.inp_goal_2.setVisible(False)
            self.chk_trend.setText("🛡️ 2026 Güvenli Hedef Katsayısı Uygula (+%1.5 LGS Puan Marjı)")

        self._populate_target_schools()
        self.res_frame.setVisible(False)

    def _populate_target_schools(self):
        exam = self.cb_exam.currentText()
        year = self._get_selected_year()
        city = self.cb_city.currentText()
        
        targets = get_exam_data(exam, year=year, city=city)
        
        self.cb_target.blockSignals(True)
        self.cb_target.clear()
        
        self.target_data_map = {}
        
        # Manuel Seçeneği
        manual_title = "--- ✏️ Manuel Veri Girişi (Listede Yoksa) ---"
        self.cb_target.addItem(manual_title, {"manual": True, "name": manual_title})
        
        items_text = [manual_title]
        
        for t in targets:
            name = t["name"]
            puan = t.get("puan", 0)
            
            if "YKS" in exam:
                rank = t.get("rank", 0)
                rank_str = f"Sıralama: ~{rank:,}" if rank else ""
                disp = f"{name}  [{rank_str} • Taban: {puan:.1f}]" if rank else f"{name}  [Taban: {puan:.1f}]"
            else: # LGS
                perc = t.get("perc", 0)
                perc_str = f"%{perc:.2f} Dilim" if perc else ""
                disp = f"{name}  [{perc_str} • Taban: {puan:.1f}]" if perc else f"{name}  [Taban: {puan:.1f}]"
                
            self.cb_target.addItem(disp, t)
            items_text.append(disp)
            self.target_data_map[disp] = t
            
        completer = QCompleter(items_text)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.cb_target.setCompleter(completer)
        
        self.cb_target.blockSignals(False)
        self._on_target_change()

    def _on_target_change(self):
        txt = self.cb_target.currentText()
        if "Manuel" in txt:
            self.manual_frame.setVisible(True)
            self.btn_search.setText("🌍 Bölüm Ara (Google)")
        else:
            self.manual_frame.setVisible(False)
            clean = txt.split("[")[0].strip()
            self.btn_search.setText(f"🌍 {clean[:24]}... Ara")

    def _search_online(self):
        target = self.cb_target.currentText().split("[")[0].strip()
        year = self._get_selected_year()
        if "Manuel" in target:
            query = f"YKS {year} taban puanları ve başarı sıralamaları YÖK Atlas"
        else:
            query = f"{target} {year} taban puanları başarı sırası netleri YÖK Atlas"
        
        url_str = f"https://www.google.com/search?q={query}"
        QDesktopServices.openUrl(QUrl(url_str))

    def _load_student_target(self):
        """Öğrencinin kaydedilmiş hedefini yükler."""
        if not self.student_id: return

        try:
            con = db.get_conn()
            row = con.execute("SELECT hedef_bolum, hedef_tyt, hedef_ayt, hedef_lgs FROM ogrenci WHERE id=?", (self.student_id,)).fetchone()
            if not row: return

            h_bolum = (row["hedef_bolum"] or "").strip()
            h_tyt = row["hedef_tyt"] or 0
            h_ayt = row["hedef_ayt"] or 0
            h_lgs = row["hedef_lgs"] or 0

            if not h_bolum: return

            if h_lgs > 0:
                self.cb_exam.setCurrentText("LGS")
                self.inp_goal_1.setText(str(h_lgs))
            else:
                self.inp_goal_1.setText(str(h_tyt))
                self.inp_goal_2.setText(str(h_ayt))
                if "LGS" in self.cb_exam.currentText():
                    self.cb_exam.setCurrentText("YKS-SAY")

            # Okul eşleşmesi bul
            found = False
            for i in range(self.cb_target.count()):
                t_txt = self.cb_target.itemText(i)
                if h_bolum.lower() in t_txt.lower():
                    self.cb_target.setCurrentIndex(i)
                    found = True
                    break
                    
            if not found:
                self.cb_target.setEditText(h_bolum)
                self.manual_frame.setVisible(True)
                
            # Tab 2'ye de hedefi ilet
            target_data = {"name": h_bolum}
            if h_lgs > 0: target_data["req_net"] = h_lgs
            else: 
                target_data["req_tyt"] = h_tyt
                target_data["req_ayt"] = h_ayt
            
            if hasattr(self.tab_advanced, "set_target"):
                self.tab_advanced.set_target(target_data)
                
        except Exception as e:
            print("Hedef yükleme hatası:", e)

    def _analyze(self):
        exam = self.cb_exam.currentText()
        selected_data = self.cb_target.currentData()
        target_text = self.cb_target.currentText()
        year = self._get_selected_year()
        
        is_manual = False
        if not selected_data or selected_data.get("manual") or "Manuel" in target_text:
            is_manual = True
            
        req_tyt = 0.0
        req_ayt = 0.0
        req_net = 0.0
        puan_taban = 0.0
        rank_taban = 0
        
        if is_manual:
            try:
                if "YKS" in exam:
                    req_tyt = float(self.inp_goal_1.text().replace(",", ".") or "0")
                    req_ayt = float(self.inp_goal_2.text().replace(",", ".") or "0")
                else:
                    req_net = float(self.inp_goal_1.text().replace(",", ".") or "0")
            except ValueError:
                QMessageBox.warning(self, "Hata", "Lütfen hedef netlerinizi geçerli sayısal değerler olarak girin.")
                return
        else:
            req_tyt = float(selected_data.get("tyt", 0))
            req_ayt = float(selected_data.get("ayt", 0))
            req_net = float(selected_data.get("net", 0))
            puan_taban = float(selected_data.get("puan", 0))
            rank_taban = int(selected_data.get("rank", 0) or selected_data.get("perc", 0))

        # Güvenli Hedef Katsayısı
        trend_applied = False
        if self.chk_trend.isChecked():
            trend_applied = True
            if "YKS" in exam:
                req_tyt = round(req_tyt * 1.025, 1)
                req_ayt = round(req_ayt * 1.025, 1)
            else:
                req_net = round(min(90.0, req_net * 1.015), 1)

        # Kullanıcı Netleri
        try:
            curr_n1 = float(self.inp_net1.text().replace(",", ".") or "0")
            curr_n2 = float(self.inp_net2.text().replace(",", ".") or "0") if "YKS" in exam else 0.0
        except ValueError:
            QMessageBox.warning(self, "Hata", "Lütfen mevcut netlerinizi geçerli sayısal değerler olarak girin.")
            return

        # Öğrenci Profiline Kaydet
        disp_name = target_text.split("[")[0].strip()
        if is_manual: disp_name = "Özel Hedef"
        
        if self.student_id:
            try:
                con = db.get_conn()
                con.execute("""
                    UPDATE ogrenci 
                    SET hedef_bolum=?, hedef_tyt=?, hedef_ayt=?, hedef_lgs=?
                    WHERE id=?
                """, (disp_name, req_tyt, req_ayt, req_net, self.student_id))
                con.commit()
            except Exception as e:
                print("DB Kayıt Hatası:", e)

        # Tab 2 Senkronizasyonu
        if hasattr(self.tab_advanced, "set_target"):
            self.tab_advanced.set_target({
                "name": disp_name,
                "req_tyt": req_tyt,
                "req_ayt": req_ayt,
                "req_net": req_net
            })

        # Gap Hesaplamaları
        if "YKS" in exam:
            diff_tyt = curr_n1 - req_tyt
            diff_ayt = curr_n2 - req_ayt
            
            # Katsayılar (TYT %40, AYT %60)
            w_tyt, w_ayt = 0.40, 0.60
            tot_req = (req_tyt * w_tyt) + (req_ayt * w_ayt)
            tot_curr = (curr_n1 * w_tyt) + (curr_n2 * w_ayt)
            
            pct = int((tot_curr / max(0.1, tot_req)) * 100) if tot_req > 0 else 0
            pct = min(120, max(0, pct))
            self.progress.setValue(min(100, pct))
            
            # Renkler
            c_tyt = "#16a34a" if diff_tyt >= 0 else "#dc2626"
            c_ayt = "#16a34a" if diff_ayt >= 0 else "#dc2626"
            sign_tyt = "+" if diff_tyt >= 0 else ""
            sign_ayt = "+" if diff_ayt >= 0 else ""
            
            # Sıralama tahmini
            est_rank = ""
            if rank_taban > 0:
                if pct >= 100:
                    est_rank = f"<span style='color:#16a34a; font-weight:bold;'>~{int(rank_taban * 0.9):,} veya daha iyi</span>"
                elif pct >= 85:
                    est_rank = f"<span style='color:#2563eb; font-weight:bold;'>~{int(rank_taban * 1.3):,} bandında</span>"
                else:
                    est_rank = f"<span style='color:#d97706; font-weight:bold;'>~{int(rank_taban * 2.2):,} bandında</span>"

            # Koçluk Tavsiyesi
            if diff_ayt < -5 and diff_tyt < -5:
                advice = "💡 <b>Stratejik Koçluk Notu:</b> Hem TYT hem de AYT'de açık bulunuyor. AYT'nin puan etkisi %60 olduğundan çalışma sürenizin en az %60'ını AYT eksik konularına ve branş denemelerine ayırmalısınız."
            elif diff_ayt < -3:
                advice = "💡 <b>Stratejik Koçluk Notu:</b> TYT temelin sağlam görünüyor; hedefine ulaşmak için tüm odağını AYT derslerine vermelisin. AYT'deki her 1 net, TYT'deki 2.5 nete eşdeğerdir."
            elif diff_tyt < -5:
                advice = "💡 <b>Stratejik Koçluk Notu:</b> AYT seviyen oldukça iyi, ancak TYT süresini ve paragraf/problem hızını artırarak TYT netlerini yukarı çekmelisin."
            else:
                advice = "🌟 <b>Stratejik Koçluk Notu:</b> Harika bir seviyedesin! Hedeflenen puan çıtasını yakaladın. Kalan sürede deneme sınavı sıklığını artırıp dereceye oynayabilirsin."

            trend_badge = " <span style='background:#fef3c7; color:#92400e; padding:2px 6px; border-radius:4px; font-size:11px;'>+Güvenli Hedef Uygulandı</span>" if trend_applied else ""

            html = f"""
            <div style='line-height:1.6;'>
                <div style='font-size:14px; margin-bottom:8px;'>
                    Hedeflenen Program: <b>{disp_name}</b> ({year} Referansı){trend_badge}
                </div>
                
                <table border='0' cellspacing='6' cellpadding='4' style='width:100%;'>
                    <tr>
                        <td style='background:#f1f5f9; border-radius:6px; padding:8px;'>
                            <b>🎯 Hedef Netler:</b><br>
                            TYT: <b>{req_tyt:.1f}</b> &nbsp;•&nbsp; AYT: <b>{req_ayt:.1f}</b>
                        </td>
                        <td style='background:#f8fafc; border-radius:6px; padding:8px;'>
                            <b>👤 Senin Netlerin:</b><br>
                            TYT: <b>{curr_n1:.1f}</b> &nbsp;•&nbsp; AYT: <b>{curr_n2:.1f}</b>
                        </td>
                        <td style='background:#eff6ff; border-radius:6px; padding:8px;'>
                            <b>⚖️ Kalan Açık (Gap):</b><br>
                            TYT: <b style='color:{c_tyt};'>{sign_tyt}{diff_tyt:.1f}</b> &nbsp;•&nbsp; 
                            AYT: <b style='color:{c_ayt};'>{sign_ayt}{diff_ayt:.1f}</b>
                        </td>
                    </tr>
                </table>
            """
            
            if rank_taban > 0:
                html += f"""
                <div style='margin-top:8px; padding:8px; background:#f8fafc; border-radius:6px; border:1px solid #e2e8f0;'>
                    🎯 <b>Hedef Taban Sıralaması:</b> ~{rank_taban:,} &nbsp;|&nbsp; 
                    📍 <b>Mevcut Seviye Sıralama Tahmini:</b> {est_rank}
                </div>
                """
                
            html += f"""
                <div style='margin-top:10px; padding:10px; background:#ecfdf5; border-radius:6px; border:1px solid #a7f3d0; color:#065f46;'>
                    {advice}
                </div>
            </div>
            """
            self.lbl_res_desc.setText(html)
            self._style_result_box(pct)
            
        else: # LGS
            diff = curr_n1 - req_net
            pct = int((curr_n1 / max(0.1, req_net)) * 100) if req_net > 0 else 0
            pct = min(120, max(0, pct))
            self.progress.setValue(min(100, pct))
            
            c_diff = "#16a34a" if diff >= 0 else "#dc2626"
            sign = "+" if diff >= 0 else ""
            
            if diff >= 0:
                advice = "🌟 <b>Koçluk Notu:</b> Tebrikler! Hedeflediğin lisenin net çıtasını yakaladın. Sınava kadar kondisyonunu korumalı ve süre stresini minimuma indirmelisin."
            elif diff >= -5:
                advice = "💡 <b>Koçluk Notu:</b> Hedefe çok yakınsın! Matematik ve Fen'deki birkaç netlik boş veya dikkatsizlik kaynaklı yanlışı kapatarak hedefine rahatlıkla yerleşebilirsin."
            else:
                advice = "⚠️ <b>Koçluk Notu:</b> Kapatılması gereken bir net açığı bulunuyor. Özellikle katsayısı 4 olan Matematik, Türkçe ve Fen Bilimleri testlerine odaklanmalısın."

            trend_badge = " <span style='background:#fef3c7; color:#92400e; padding:2px 6px; border-radius:4px; font-size:11px;'>+Güvenli Hedef Uygulandı</span>" if trend_applied else ""

            html = f"""
            <div style='line-height:1.6;'>
                <div style='font-size:14px; margin-bottom:8px;'>
                    Hedeflenen Okul: <b>{disp_name}</b> ({year} Referansı){trend_badge}
                </div>
                
                <table border='0' cellspacing='6' cellpadding='4' style='width:100%;'>
                    <tr>
                        <td style='background:#f1f5f9; border-radius:6px; padding:8px;'>
                            <b>🎯 Hedef Net:</b><br>
                            <b>{req_net:.1f}</b> / 90
                        </td>
                        <td style='background:#f8fafc; border-radius:6px; padding:8px;'>
                            <b>👤 Senin Netin:</b><br>
                            <b>{curr_n1:.1f}</b> / 90
                        </td>
                        <td style='background:#eff6ff; border-radius:6px; padding:8px;'>
                            <b>⚖️ Kalan Açık (Gap):</b><br>
                            <b style='color:{c_diff}; font-size:14px;'>{sign}{diff:.1f} Net</b>
                        </td>
                    </tr>
                </table>
                
                <div style='margin-top:10px; padding:10px; background:#ecfdf5; border-radius:6px; border:1px solid #a7f3d0; color:#065f46;'>
                    {advice}
                </div>
            </div>
            """
            self.lbl_res_desc.setText(html)
            self._style_result_box(pct)

    def _style_result_box(self, pct: int):
        if pct >= 100:
            title = f"🎉 Hedefe Ulaşma Seviyesi: %{pct} (Hedef Tamamlandı & Derece Bandı)"
            color = "#10b981"
            bg = "#f0fdf4"
        elif pct >= 85:
            title = f"🚀 Hedefe Ulaşma Seviyesi: %{pct} (Çok İyi Durumdasın)"
            color = "#2563eb"
            bg = "#eff6ff"
        elif pct >= 70:
            title = f"📈 Hedefe Ulaşma Seviyesi: %{pct} (İyi Yoldasın - Hızlanabilirsin)"
            color = "#d97706"
            bg = "#fffbeb"
        else:
            title = f"⚠️ Hedefe Ulaşma Seviyesi: %{pct} (Açık Kapatma Programı Gerekiyor)"
            color = "#dc2626"
            bg = "#fef2f2"
            
        self.lbl_res_title.setText(title)
        self.lbl_res_title.setStyleSheet(f"font-weight: 800; font-size: 15px; color: {color};")
        self.res_frame.setStyleSheet(f"background: {bg}; border: 1px solid {color}40; border-radius: 12px;") 
        self.res_frame.setVisible(True)
