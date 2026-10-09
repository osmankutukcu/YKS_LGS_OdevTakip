# -*- coding: utf-8 -*-
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QDateEdit, QAbstractItemView,
    QStyledItemDelegate, QMenu, QListView, QProgressBar, QSplitter, QFrame,
    QLineEdit, QStackedWidget, QHeaderView, QWidget
)
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QDate, QSize
from datetime import date, timedelta, datetime
import db
from ui import app_settings as appset
from ui.common_pdf import build_html_table, save_html_as_pdf  # ← 1. adımda eklediğin dosya

# ---- Excel (pandas) ve PDF yardımcıları ----
import datetime

try:
    import pandas as pd
except Exception:
    pd = None  # Pandas yoksa None olur (CSV fallback çalışır)

# HTML → PDF dönüştürücü yardımcıları
try:
    from ui.common_pdf import build_html_table, save_html_as_pdf
except Exception:
    try:
        from .common_pdf import build_html_table, save_html_as_pdf
    except Exception:
        from common_pdf import build_html_table, save_html_as_pdf



#s--whatsapp yaedımcısı
import datetime as _dt
import sqlite3

def _randevu_kontrol_kolon(con: sqlite3.Connection) -> str:
    """
    randevu tablosunda kontrol tarihinin hangi kolonda tutulduğunu bulur.
    Eğer 'kontrol_tarihi' yoksa, 'tarih' veya 'randevu_tarihi' gibi
    bir alanı kontrol tarihi olarak kullan.
    """
    try:
        cols = [r["name"] for r in con.execute("PRAGMA table_info(randevu)")]
        if "kontrol_tarihi" in cols:
            return "kontrol_tarihi"
        if "randevu_tarihi" in cols:
            return "randevu_tarihi"
        if "tarih" in cols:
            return "tarih"
    except Exception:
        pass
    # En kötü ihtimal yedek değer:
    return "kontrol_tarihi"
#f--


# ------------------------------------------------------------
# RANDEVU TAKVİMİ – ZEBRA + SAĞ TIK + KONTROL DURUMLARI + WA/EXPORT
# ------------------------------------------------------------self.tab.setItem
class RandevuTakvimi(QDialog):
    COL_AD, COL_BITIS, COL_KALAN, COL_DURUM, COL_PROGRESS, COL_KUME = range(6)
    COL_OGR = COL_AD  # Alias for safety

    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self._hw_form = None
        self.setWindowTitle('Randevu ve Ödev Takip Takvimi')

        # 🎨 RENK SABİTLERİ
        self.CLR_DONE = (232, 245, 233)     # yeşilimsi: %100 tamamlanmış
        self.CLR_OVERDUE = (255, 235, 238)  # kırmızımsı: gecikmiş
        self.CLR_TODAY = (255, 204, 204)    # pembe: bitiş bugün
        self.CLR_SOON = (255, 249, 196)     # sarı: <=2 gün kalan
        self.CLR_NODATE = (243, 244, 246)   # gri: tarihsiz

        self.resize(1180, 740)
        self.setMinimumSize(960, 600)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # =========================================================================
        # 1. ÜST BAŞLIK KARTI (EXECUTIVE BANNER - KOMPAKT & MODERN)
        # =========================================================================
        header = QFrame()
        header.setObjectName("HeaderCard")
        header.setStyleSheet("""
            QFrame#HeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #2563eb);
                border-radius: 8px;
            }
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(12, 6, 12, 6)
        h_lay.setSpacing(10)

        icon_lbl = QLabel("📅")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; color: white; border: none;")
        h_lay.addWidget(icon_lbl)

        v_head = QVBoxLayout()
        v_head.setSpacing(1)
        lbl_h_title = QLabel("Randevu ve Ödev Takip Takvimi")
        lbl_h_title.setStyleSheet("color: white; font-size: 13.5px; font-weight: 800; background: transparent; border: none;")
        lbl_h_sub = QLabel("Öğrenci teslim tarihleri, kalan süreler, yaklaşan randevular ve WhatsApp bildirimleri")
        lbl_h_sub.setStyleSheet("color: #bfdbfe; font-size: 10.5px; font-weight: 500; background: transparent; border: none;")
        v_head.addWidget(lbl_h_title)
        v_head.addWidget(lbl_h_sub)
        h_lay.addLayout(v_head, 1)

        btn_exp_pdf = QPushButton("🖨️ PDF / Yazdır")
        btn_exp_pdf.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.18); color: white;
                border: 1px solid rgba(255,255,255,0.35); border-radius: 6px;
                padding: 4px 10px; font-weight: 700; font-size: 10.5px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.28); }
        """)
        btn_exp_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exp_pdf.clicked.connect(self._export_pdf)
        h_lay.addWidget(btn_exp_pdf)

        btn_exp_excel = QPushButton("📊 Excel İndir")
        btn_exp_excel.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.18); color: white;
                border: 1px solid rgba(255,255,255,0.35); border-radius: 6px;
                padding: 4px 10px; font-weight: 700; font-size: 10.5px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.28); }
        """)
        btn_exp_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exp_excel.clicked.connect(self._export_excel)
        h_lay.addWidget(btn_exp_excel)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background: #ffffff; color: #1e3a8a;
                border: none; border-radius: 6px;
                padding: 4px 12px; font-weight: 800; font-size: 10.5px;
            }
            QPushButton:hover { background: #f1f5f9; }
        """)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self._load_from_db)
        h_lay.addWidget(btn_refresh)

        root.addWidget(header)

        # =========================================================================
        # 2. 4 EXECUTIVE KPI ÖZET KARTI (KOMPAKT & YER TASARRUFLU)
        # =========================================================================
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)

        def make_kpi(icon, title, val_def, sub_def, accent_col, filter_val):
            box = QFrame()
            box.setFixedHeight(44)
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.setToolTip(f"{title}: {sub_def} (Filtrelemek için tıklayın)")
            box.setStyleSheet(f"""
                QFrame {{
                    background: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-left: 3.5px solid {accent_col};
                    border-radius: 7px;
                }}
                QFrame:hover {{
                    border-color: {accent_col};
                    background: #f8fafc;
                }}
            """)
            bl = QHBoxLayout(box)
            bl.setContentsMargins(10, 4, 10, 4)
            bl.setSpacing(8)

            ico = QLabel(icon)
            ico.setStyleSheet("font-size: 15px; background: transparent; border: none;")

            v = QVBoxLayout()
            v.setSpacing(0)
            v.setContentsMargins(0, 0, 0, 0)
            t = QLabel(title)
            t.setStyleSheet("font-size: 9.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px; background: transparent; border: none;")
            val = QLabel(val_def)
            val.setStyleSheet("font-size: 13.5px; font-weight: 800; color: #0f172a; background: transparent; border: none;")
            v.addWidget(t)
            v.addWidget(val)

            bl.addWidget(ico)
            bl.addLayout(v, 1)

            box.mousePressEvent = lambda e, f=filter_val: self._set_quick_filter(f)
            return box, val

        self.kpi_box1, self.lbl_kpi_total = make_kpi("📋", "Toplam Takip", "0 Küme", "Kayıtlı Ödev Kümeleri", "#2563eb", "Tümü")
        self.kpi_box2, self.lbl_kpi_overdue = make_kpi("⚠️", "Geciken Ödevler", "0 Gecikme", "Bitiş Tarihi Geçmiş", "#ef4444", "Yalnız geciken")
        self.kpi_box3, self.lbl_kpi_soon = make_kpi("⏱️", "Yaklaşan Teslimler", "0 Küme", "Son 7 Gün İçi", "#f59e0b", "Önümüzdeki 7 gün")
        self.kpi_box4, self.lbl_kpi_done = make_kpi("✅", "Tamamlananlar", "0 Küme", "%100 Tamamlanan", "#10b981", "Tümü")

        kpi_row.addWidget(self.kpi_box1)
        kpi_row.addWidget(self.kpi_box2)
        kpi_row.addWidget(self.kpi_box3)
        kpi_row.addWidget(self.kpi_box4)
        root.addLayout(kpi_row)

        # =========================================================================
        # 3. MODERN FİLTRE ARAÇ ÇUBUĞU KARTI
        # =========================================================================
        filter_card = QFrame()
        filter_card.setObjectName("FilterCard")
        filter_card.setStyleSheet("""
            QFrame#FilterCard {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        fc_lay = QVBoxLayout(filter_card)
        fc_lay.setContentsMargins(10, 6, 10, 6)
        fc_lay.setSpacing(5)

        # Satır 1: Girişler (Combo, Date, LineEdit)
        h_inputs = QHBoxLayout()
        h_inputs.setSpacing(8)

        # Tarih
        h_inputs.addWidget(QLabel("📅 Tarih:"))
        self.cmbTarih = QComboBox()
        self.cmbTarih.addItems([
            "Tümü", "Yalnız geciken", "Bugün", "Yarın",
            "Bu Hafta", "Önümüzdeki 7 gün", "Seçili Tarih", "Tarihi boş olanlar"
        ])
        self.cmbTarih.setMinimumWidth(130)
        h_inputs.addWidget(self.cmbTarih)

        # Gün
        h_inputs.addWidget(QLabel("📆 Gün:"))
        self.dtSec = QDateEdit(QDate.currentDate())
        self.dtSec.setCalendarPopup(True)
        self.dtSec.setDisplayFormat("yyyy-MM-dd")
        self.dtSec.setFixedWidth(105)
        h_inputs.addWidget(self.dtSec)

        # Öğrenci
        h_inputs.addWidget(QLabel("👤 Öğrenci:"))
        self.cmbOgr = QComboBox()
        self.cmbOgr.addItem("Tümü", userData=None)
        self.cmbOgr.setMinimumWidth(150)
        h_inputs.addWidget(self.cmbOgr)

        # Arama
        self.txtAra = QLineEdit()
        self.txtAra.setPlaceholderText("🔍 Öğrenci veya ödev ara...")
        self.txtAra.setClearButtonEnabled(True)
        self.txtAra.setMinimumWidth(150)
        h_inputs.addWidget(self.txtAra)

        # Sırala
        h_inputs.addWidget(QLabel("↕️ Sırala:"))
        self.cmbSirala = QComboBox()
        self.cmbSirala.addItems([
            "Bitiş (artan)", "Bitiş (azalan)",
            "Ad Soyad (artan)", "Ad Soyad (azalan)",
            "Küme ID (artan)", "Küme ID (azalan)"
        ])
        self.cmbSirala.setMinimumWidth(120)
        h_inputs.addWidget(self.cmbSirala)

        h_inputs.addStretch(1)
        fc_lay.addLayout(h_inputs)

        # Satır 2: Hızlı Filtre Çipleri
        h_chips = QHBoxLayout()
        h_chips.setSpacing(5)
        lbl_chip_tit = QLabel("Hızlı Filtre:")
        lbl_chip_tit.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #64748b;")
        h_chips.addWidget(lbl_chip_tit)

        filter_buttons = [
            ("✓ Tümü", "Tümü", "#f1f5f9", "#334155"),
            ("🔴 Yalnız Gecikenler", "Yalnız geciken", "#fee2e2", "#991b1b"),
            ("🟡 Bugün Bitenler", "Bugün", "#fef3c7", "#92400e"),
            ("⏱️ Bu Hafta & 7 Gün", "Önümüzdeki 7 gün", "#eff6ff", "#1e40af"),
            ("⏳ Tarihsizler", "Tarihi boş olanlar", "#f1f5f9", "#475569"),
        ]
        for btn_txt, f_val, bg, fg in filter_buttons:
            btn_f = QPushButton(btn_txt)
            btn_f.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; color: {fg}; font-weight: 700; font-size: 10.5px;
                    padding: 2px 8px; border-radius: 5px; border: 1px solid {fg}30; min-height: 22px;
                }}
                QPushButton:hover {{
                    border-color: {fg};
                }}
            """)
            btn_f.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_f.clicked.connect(lambda _, val=f_val: self.cmbTarih.setCurrentText(val))
            h_chips.addWidget(btn_f)
        h_chips.addStretch(1)
        fc_lay.addLayout(h_chips)

        root.addWidget(filter_card)

        # =========================================================================
        # 4. ORTA BÖLÜM: MASTER-DETAIL SPLITTER (TABLO + SAĞ İNCELEME KARTI)
        # =========================================================================
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # SOL: TABLO KARTI
        tab_card = QFrame()
        tab_card.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px;")
        tc_lay = QVBoxLayout(tab_card)
        tc_lay.setContentsMargins(4, 4, 4, 4)

        self.tab = QTableWidget(0, 6)
        self.tab.setHorizontalHeaderLabels(['Öğrenci Adı Soyadı', 'Bitiş Tarihi', 'Kalan Gün', 'Durum', 'İlerleme', 'Küme ID'])
        self.tab.horizontalHeader().setStretchLastSection(False)
        self.tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tab.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed); self.tab.setColumnWidth(1, 110)
        self.tab.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed); self.tab.setColumnWidth(2, 95)
        self.tab.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed); self.tab.setColumnWidth(3, 135)
        self.tab.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed); self.tab.setColumnWidth(4, 125)
        self.tab.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed); self.tab.setColumnWidth(5, 75)
        tc_lay.addWidget(self.tab)
        splitter.addWidget(tab_card)

        # SAĞ: SEÇİLİ RANDVEU VE ÖDEV İNCELEME KARTI
        self.panel_detail = QFrame()
        self.panel_detail.setObjectName("DetailPanel")
        self.panel_detail.setStyleSheet("""
            QFrame#DetailPanel {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        det_layout = QVBoxLayout(self.panel_detail)
        det_layout.setContentsMargins(12, 12, 12, 12)
        det_layout.setSpacing(10)

        lbl_det_title = QLabel("📋 Seçili Randevu & Ödev İnceleme")
        lbl_det_title.setStyleSheet("font-weight: 800; font-size: 12px; color: #1e293b; border-bottom: 1px solid #f1f5f9; padding-bottom: 4px;")
        det_layout.addWidget(lbl_det_title)

        # Stack (0: Boş Durum, 1: İçerik)
        self.det_stack = QStackedWidget()

        # 0: Boş
        w_empty = QWidget()
        l_emp = QVBoxLayout(w_empty)
        l_emp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_emp_ico = QLabel("👈")
        lbl_emp_ico.setStyleSheet("font-size: 34px;")
        lbl_emp_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_emp_txt = QLabel("İncelemek ve hızlı işlem yapmak için sol tablodan bir satır seçin.")
        lbl_emp_txt.setWordWrap(True)
        lbl_emp_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_emp_txt.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 500;")
        l_emp.addWidget(lbl_emp_ico)
        l_emp.addWidget(lbl_emp_txt)
        self.det_stack.addWidget(w_empty)

        # 1: Dolu
        w_det = QWidget()
        l_det = QVBoxLayout(w_det)
        l_det.setContentsMargins(0, 0, 0, 0)
        l_det.setSpacing(6)

        # Profil Kutusu & Küme Rozetleri (Kompakt ve Şık)
        stu_card = QFrame()
        stu_card.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        sc_lay = QVBoxLayout(stu_card)
        sc_lay.setContentsMargins(8, 6, 8, 6)
        sc_lay.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        self.lbl_det_name = QLabel("Öğrenci Adı")
        self.lbl_det_name.setStyleSheet("font-size: 13px; font-weight: 800; color: #0f172a;")
        self.lbl_det_kume_badge = QLabel("📦 Küme #—")
        self.lbl_det_kume_badge.setStyleSheet("background: #eff6ff; color: #1d4ed8; font-weight: 700; font-size: 10.5px; padding: 2px 6px; border-radius: 5px; border: 1px solid #bfdbfe;")
        self.lbl_det_status_badge = QLabel("Durum")
        self.lbl_det_status_badge.setStyleSheet("background: #f1f5f9; color: #334155; font-weight: 700; font-size: 10.5px; padding: 2px 6px; border-radius: 5px; border: 1px solid #cbd5e1;")

        top_row.addWidget(self.lbl_det_name)
        top_row.addStretch(1)
        top_row.addWidget(self.lbl_det_kume_badge)
        top_row.addWidget(self.lbl_det_status_badge)
        sc_lay.addLayout(top_row)

        self.lbl_det_meta = QLabel("Grup • Telefon")
        self.lbl_det_meta.setStyleSheet("font-size: 11px; color: #475569;")
        sc_lay.addWidget(self.lbl_det_meta)
        l_det.addWidget(stu_card)

        # Ödev Listesi
        self.lbl_hw_sub = QLabel("📚 <b>Kümedeki Ödevler & Kitaplar:</b>")
        self.lbl_hw_sub.setStyleSheet("font-size: 11px; color: #334155; margin-top: 2px;")
        l_det.addWidget(self.lbl_hw_sub)

        self.tbl_det_homeworks = QTableWidget(0, 3)
        self.tbl_det_homeworks.setHorizontalHeaderLabels(["Ders / Kitap", "Konu", "Durum"])
        self.tbl_det_homeworks.horizontalHeader().setStretchLastSection(False)
        self.tbl_det_homeworks.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_det_homeworks.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_det_homeworks.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_det_homeworks.verticalHeader().setVisible(False)
        self.tbl_det_homeworks.verticalHeader().setDefaultSectionSize(24)
        self.tbl_det_homeworks.setMinimumHeight(100)
        self.tbl_det_homeworks.setStyleSheet("""
            QTableWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 11px; }
            QHeaderView::section { background: #f8fafc; font-weight: 700; color: #475569; padding: 3px; font-size: 10px; border: none; border-bottom: 1px solid #e2e8f0; }
        """)
        l_det.addWidget(self.tbl_det_homeworks, 1)

        # Hızlı Aksiyonlar - Minimalist & Kompakt Tek Satır Buton Çubuğu
        h_act_bar = QHBoxLayout()
        h_act_bar.setSpacing(5)
        h_act_bar.setContentsMargins(0, 4, 0, 0)

        self.btn_det_wa = QPushButton("💬 WhatsApp")
        self.btn_det_wa.setToolTip("Bu öğrenciye ve velisine WhatsApp ödev bildirimi gönder")
        self.btn_det_wa.setStyleSheet("""
            QPushButton {
                background: #10b981; color: white; font-weight: 700;
                padding: 4px 8px; border-radius: 6px; font-size: 11px; border: none; min-height: 26px;
            }
            QPushButton:hover { background: #059669; }
        """)
        self.btn_det_wa.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_det_wa.clicked.connect(self._send_whatsapp_for_selected)

        self.btn_det_open = QPushButton("📖 Ödev")
        self.btn_det_open.setToolTip("Öğrencinin detaylı ödev takip formunu aç")
        self.btn_det_open.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; font-weight: 700;
                padding: 4px 8px; border-radius: 6px; font-size: 11px; border: none; min-height: 26px;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        self.btn_det_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_det_open.clicked.connect(self._open_tracking_for_selected)

        self.btn_det_analysis = QPushButton("📊 Analiz")
        self.btn_det_analysis.setToolTip("Kitap ve konu ilerleme analizini aç")
        self.btn_det_analysis.setStyleSheet("""
            QPushButton {
                background: #f1f5f9; color: #334155; font-weight: 700;
                padding: 4px 8px; border-radius: 6px; font-size: 11px; border: 1px solid #cbd5e1; min-height: 26px;
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
        """)
        self.btn_det_analysis.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_det_analysis.clicked.connect(self._open_analysis_for_selected)

        self.btn_det_done = QPushButton("✓ Tamamla")
        self.btn_det_done.setToolTip("Bu ödev kümesini tamamlandı olarak işaretle")
        self.btn_det_done.setStyleSheet("""
            QPushButton {
                background: #ecfdf5; color: #065f46; font-weight: 700;
                padding: 4px 8px; border-radius: 6px; font-size: 11px; border: 1px solid #a7f3d0; min-height: 26px;
            }
            QPushButton:hover { background: #d1fae5; }
        """)
        self.btn_det_done.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_det_done.clicked.connect(self._mark_selected_kume_completed)

        h_act_bar.addWidget(self.btn_det_wa, 1)
        h_act_bar.addWidget(self.btn_det_open, 1)
        h_act_bar.addWidget(self.btn_det_analysis, 1)
        h_act_bar.addWidget(self.btn_det_done, 1)
        l_det.addLayout(h_act_bar)

        self.det_stack.addWidget(w_det)
        det_layout.addWidget(self.det_stack, 1)

        splitter.addWidget(self.panel_detail)
        splitter.setStretchFactor(0, 62)
        splitter.setStretchFactor(1, 38)
        splitter.setSizes([660, 420])

        root.addWidget(splitter, 1)

        # =========================================================================
        # 5. MODERN ALT AKSİYON BARI (WHATSAPP & BİLDİRİMLER - KOMPAKT)
        # =========================================================================
        bar = QFrame()
        bar.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(8, 4, 8, 4)
        bar_lay.setSpacing(8)

        bar_lay.addWidget(QLabel("Şablon:"))
        self.cmbSablon = QComboBox()
        self.cmbSablon.addItems(['Genel', 'Geciken'])
        self.cmbSablon.setFixedWidth(100)
        bar_lay.addWidget(self.cmbSablon)

        self.chkYalnizGeciken = QCheckBox('Yalnız gecikenler')
        self.chkYalnizGeciken.setStyleSheet("font-weight: 600; color: #475569; font-size: 10.5px;")
        bar_lay.addWidget(self.chkYalnizGeciken)

        self.lbl_table_summary = QLabel("📊 Yükleniyor...")
        self.lbl_table_summary.setStyleSheet("color: #64748b; font-size: 10.5px; font-weight: 600; margin-left: 4px;")
        bar_lay.addWidget(self.lbl_table_summary)

        bar_lay.addStretch(1)

        self.btn24Secili = QPushButton('📱 24s (Seçili)')
        self.btn24Secili.setToolTip("Seçili öğrenciye 24 saat kala teslim hatırlatması gönder")
        self.btn24Tum = QPushButton('📱 24s (Tümü)')
        self.btn24Tum.setToolTip("Teslimine 24 saat kalan tüm öğrencilere WhatsApp hatırlatması gönder")
        self.btnTodaySel = QPushButton('🔔 Bugün (Seçili)')
        self.btnTodaySel.setToolTip("Seçili öğrenciye bugün biten ödev hatırlatması gönder")
        self.btnTodayAll = QPushButton('🔔 Bugün (Tümü)')
        self.btnTodayAll.setToolTip("Bugün teslimi olan tüm öğrencilere WhatsApp hatırlatması gönder")

        for b, col, bg in [
            (self.btn24Secili, "#1e40af", "#eff6ff"),
            (self.btn24Tum, "#1e40af", "#dbeafe"),
            (self.btnTodaySel, "#92400e", "#fef3c7"),
            (self.btnTodayAll, "#92400e", "#fde68a"),
        ]:
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {col};
                    border: 1px solid {col}40;
                    padding: 3px 8px;
                    border-radius: 5px;
                    font-weight: 700;
                    font-size: 10.5px;
                    min-height: 24px;
                }}
                QPushButton:hover {{
                    border-color: {col};
                    background-color: #ffffff;
                }}
            """)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            bar_lay.addWidget(b)

        root.addWidget(bar)

        # Sinyal bağlantıları
        self.cmbTarih.currentTextChanged.connect(self._on_tarih_tip_degisti)
        self.dtSec.dateChanged.connect(self._on_dt_changed)
        self.cmbOgr.currentIndexChanged.connect(lambda: self._load_from_db())
        self.cmbSirala.currentIndexChanged.connect(lambda: self._load_from_db())
        self.txtAra.textChanged.connect(lambda: self._load_from_db())
        self.chkYalnizGeciken.toggled.connect(self._yalniz_geciken_checkbox_senkron)

        # WhatsApp Butonları
        self.btn24Tum.clicked.connect(self._btn_24_saat_tumu)
        self.btn24Secili.clicked.connect(self._btn_24_saat_secili)
        self.btnTodayAll.clicked.connect(self._btn_bugun_tumu)
        self.btnTodaySel.clicked.connect(self._btn_bugun_secili)

        # Tablo seçim ve çift tıklama
        self.tab.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.tab.cellDoubleClicked.connect(self._ac)

        self._apply_table_style()
        self._install_context_menu()
        
        # İlk yükleme
        self._yenile_ogrenci_listesi()
        self._load_from_db()

        # Kısayol
        from PyQt6.QtGui import QShortcut, QKeySequence
        from PyQt6.QtWidgets import QMessageBox
        try:
            QShortcut(QKeySequence("F9"), self, activated=self._whatsapp_smoke_test)
        except AttributeError:
            pass

        # Global Modern Stil (Windows Mavi Kutu Artefaktlarını Tamamen Kaldırır)
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
            
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 26px 5px 10px;
                color: #1e293b;
                font-size: 12px;
                min-height: 22px;
            }
            QComboBox:hover {
                border-color: #3b82f6;
                background-color: #f8fafc;
            }
            QComboBox:focus {
                border-color: #2563eb;
                background-color: #ffffff;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
                margin-right: 6px;
            }
            QDateEdit, QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                color: #1e293b;
                font-size: 12px;
                min-height: 22px;
            }
            QDateEdit:hover, QLineEdit:hover {
                border-color: #3b82f6;
            }
            QDateEdit:focus, QLineEdit:focus {
                border-color: #2563eb;
            }
        """)


    # ---------- Stil / Zebra ----------
    class _ZebraDelegate(QStyledItemDelegate):
        zebra_light = QColor(249, 250, 251)  # gri-50
        zebra_dark = QColor(243, 244, 246)   # gri-100 (koyu tema yoksa hafif)
        def sizeHint(self, option, index):
            s = super().sizeHint(option, index)
            return QSize(s.width(), max(36, s.height() + 6))
        def paint(self, painter, option, index):
            # Eğer model hücreye özel bir arka plan vermişse onu KORU
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            if not bg:
                # Alternating: tek/çift satır – selection boyası üstte kalır
                if index.row() % 2 == 1:
                    painter.save()
                    painter.fillRect(option.rect, self.zebra_light)
                    painter.restore()
            super().paint(painter, option, index)

    def _open_analysis_dialog(self, rows: list[int]):
        if not rows: return
        oid = self._ogr_id_from_row(rows[0])
        if not oid:
            QMessageBox.warning(self, "Analiz", "Öğrenci kimliği alınamadı.")
            return
        ad = self._ogrenci_adsoyad(int(oid))

        # Öğrencinin TÜM kümelerinden birleşik kitap istatistiği
        con = db.get_conn()
        q = """
            SELECT ders, kitap_ad,
                   COUNT(*) AS toplam,
                   SUM(CASE WHEN LOWER(COALESCE(durum,'')) IN ('yapildi','tamam') THEN 1 ELSE 0 END) AS bitti
            FROM odev
            WHERE kume_id IN (SELECT id FROM odev_kume WHERE ogrenci_id=?)
            GROUP BY ders, kitap_ad
            ORDER BY ders, kitap_ad
        """
        rows_db = con.execute(q, (int(oid),)).fetchall()

        dlg = QDialog(self);
        dlg.setWindowTitle(f"Kitap İlerlemesi — {ad}")
        lay = QVBoxLayout(dlg)
        tbl = QTableWidget(0, 5, dlg)
        tbl.setHorizontalHeaderLabels(["Ders", "Kitap", "İlerleme %", "Tamam", "Toplam"])
        tbl.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(tbl)

        for r in rows_db:
            toplam = int(r["toplam"] or 0);
            bitti = int(r["bitti"] or 0)
            perc = int(round((bitti / toplam) * 100)) if toplam > 0 else 0
            i = tbl.rowCount();
            tbl.insertRow(i)
            tbl.setItem(i, 0, QTableWidgetItem(r["ders"] or ""))
            tbl.setItem(i, 1, QTableWidgetItem(r["kitap_ad"] or ""))
            pb = QProgressBar();
            pb.setRange(0, 100);
            pb.setValue(perc)
            tbl.setCellWidget(i, 2, pb)
            tbl.setItem(i, 3, QTableWidgetItem(str(bitti)))
            tbl.setItem(i, 4, QTableWidgetItem(str(toplam)))
        dlg.resize(720, 420);
        dlg.exec()

    def _apply_table_style(self):
        self.tab.setAlternatingRowColors(False)  # kendi zebramız var
        self.tab.setShowGrid(False)
        self.tab.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setHighlightSections(False)
        self.tab.verticalHeader().setDefaultSectionSize(42) # Daha rahat satır yüksekliği
        self.tab.setItemDelegate(self._ZebraDelegate(self.tab))
        
        # PRO TABLO STİLİ - Modern, Ferah ve Temiz
        self.tab.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px; /* Tablo köşeleri yuvarlatıldı */
                gridline-color: transparent;
                selection-background-color: #e0f2fe; /* Seçim rengi (açık mavi) */
                selection-color: #0c4a6e;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                outline: none; /* Focus çerçevesini kaldır */
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #64748b;
                padding: 12px 16px; /* Daha fazla boşluk */
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 700;
                font-size: 11px;
                text-transform: uppercase; /* Başlıklar büyük harf */
                letter-spacing: 0.5px;
            }
            QTableWidget::item {
                padding-left: 12px;
                padding-right: 12px;
                border-bottom: 1px solid #f1f5f9; /* İnce satır çizgisi */
            }
            QTableWidget::item:focus {
                background-color: #e0f2fe;
                border: none;
            }
            QTableCornerButton::section {
                background-color: #f8fafc;
                border: none;
                border-bottom: 2px solid #e2e8f0;
            }
            /* Tablo içindeki Progress Bar (varsa) */
            QProgressBar {
                border: none;
                background-color: #f1f5f9;
                border-radius: 6px;
                min-height: 12px;
                max-height: 12px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3b82f6; 
                border-radius: 6px;
            }
        """)

    # sınıfın içine ekle:
    def _export_rows(self, rows, fmt="pdf"):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        data = []
        for r in rows:
            rec = {
                "ogrenci": self.tab.item(r, self.COL_AD).text() if self.tab.item(r, self.COL_AD) else "",
                "bitis": self.tab.item(r, self.COL_BITIS).text() if self.tab.item(r, self.COL_BITIS) else "",
                "kalan": self.tab.item(r, self.COL_KALAN).text() if self.tab.item(r, self.COL_KALAN) else "",
                "durum": self.tab.item(r, self.COL_DURUM).text() if self.tab.item(r, self.COL_DURUM) else "",
                "kume_id": self.tab.item(r, self.COL_KUME).text() if self.tab.item(r, self.COL_KUME) else "",
                "ilerleme": (self.tab.cellWidget(r, self.COL_PROGRESS).format()
                             if self.tab.cellWidget(r, self.COL_PROGRESS) else "")
            }
            data.append(rec)

        if fmt == "pdf":
            path, _ = QFileDialog.getSaveFileName(self, "PDF olarak kaydet", "randevu_analiz.pdf", "PDF (*.pdf)")
            if not path:
                return
            ok = self._export_as_pdf_table(path, data)
            if ok:
                self._toast(f"PDF kaydedildi: {path}")
            else:
                QMessageBox.warning(self, "PDF", "PDF oluşturulamadı.")
        else:  # xlsx (mümkünse), yoksa CSV
            path, _ = QFileDialog.getSaveFileName(self, "Excel/CSV kaydet", "randevu_analiz.xlsx",
                                                  "Excel (*.xlsx);;CSV (*.csv)")
            if not path:
                return
            if path.lower().endswith(".csv"):
                ok = self._export_as_csv(path, data)
            else:
                ok = self._export_as_xlsx(path, data)
                if ok is False:
                    # fallback
                    csv_fallback = path.rsplit(".", 1)[0] + ".csv"
                    self._export_as_csv(csv_fallback, data)
                    self._toast(f"openpyxl/pandas yok; CSV olarak kaydedildi: {csv_fallback}")
                    return
            if ok:
                self._toast(f"Kaydedildi: {path}")
            else:
                QMessageBox.warning(self, "Dışa aktar", "Dosya kaydedilemedi.")

    def _export_rows(self, rows, fmt="xlsx"):
        from PyQt6.QtWidgets import QFileDialog
        if not rows:
            self._toast("Seçim yok.");
            return

        headers = ['Öğrenci', 'Bitiş Tarihi', 'Kalan', 'Durum', 'İlerleme', 'Küme ID']
        data = []
        for r in rows:
            row = []
            for c in range(self.tab.columnCount()):
                if c == self.COL_PROGRESS:
                    w = self.tab.cellWidget(r, c)
                    row.append(w.text() if w else "")
                else:
                    it = self.tab.item(r, c)
                    row.append(it.text() if it else "")
            data.append(row)

        if fmt == "xlsx":
            path, _ = QFileDialog.getSaveFileName(self, "Excel’e Kaydet", "randevu_raporu.xlsx", "Excel (*.xlsx)")
            if not path: return
            try:
                import openpyxl
                wb = openpyxl.Workbook();
                ws = wb.active;
                ws.title = "Rapor"
                ws.append(headers)
                for row in data: ws.append(row)
                # basit kolon genişliği
                for col in ws.columns:
                    ln = max(len(str(c.value or "")) for c in col)
                    ws.column_dimensions[col[0].column_letter].width = min(ln + 2, 40)
                wb.save(path)
                self._toast(f"Kaydedildi: {path}")
            except Exception:
                import csv, os
                csv_path = os.path.splitext(path)[0] + ".csv"
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f);
                    w.writerow(headers);
                    w.writerows(data)
                self._toast(f"openpyxl yok. CSV kaydedildi: {csv_path}")
            return

        if fmt == "pdf":
            path, _ = QFileDialog.getSaveFileName(self, "PDF’e Yazdır", "randevu_raporu.pdf", "PDF (*.pdf)")
            if not path: return
            self._export_pdf_table(headers, data, path)
            self._toast(f"Kaydedildi: {path}")

    def _export_pdf_table(self, headers, data, out_path):
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrinter
        def esc(s):
            return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    .replace('"', "&quot;").replace("'", "&#39;"))

        body = []
        for row in data:
            tds = "".join(f"<td style='padding:6px 8px;border:1px solid #e5e7eb'>{esc(str(x))}</td>" for x in row)
            body.append(f"<tr>{tds}</tr>")
        thead = "".join(
            f"<th style='padding:8px 10px;border:1px solid #e5e7eb;background:#f8fafc;text-align:left'>{esc(h)}</th>"
            for h in headers)
        html = f"""
        <html><head><meta charset='utf-8'></head><body>
        <h3>Randevu Raporu</h3>
        <table cellspacing='0' cellpadding='0' style='border-collapse:collapse;font-family:-apple-system,Arial;font-size:12px'>
          <thead><tr>{thead}</tr></thead>
          <tbody>{''.join(body)}</tbody>
        </table>
        </body></html>"""
        doc = QTextDocument();
        doc.setHtml(html)
        prn = QPrinter(QPrinter.PrinterMode.HighResolution)
        prn.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        prn.setOutputFileName(out_path)
        doc.print(prn)

    def _export_as_pdf_table(self, path, data):
        """
        Qt ile HTML tablosu render ederek PDF: kütüphane bağımsız, sağlam yöntem.
        """
        try:
            from PyQt6.QtGui import QTextDocument
            from PyQt6.QtPrintSupport import QPrinter
            html = ["<html><head><meta charset='utf-8'><style>"
                    "table{border-collapse:collapse;width:100%;font-family:Arial;font-size:11pt}"
                    "th,td{border:1px solid #ccc;padding:6px 8px;text-align:left}"
                    "th{background:#f1f5f9}"
                    "</style></head><body>"]
            html.append("<h3>Randevu Analiz</h3><table>")
            html.append(
                "<tr><th>Öğrenci</th><th>Bitiş</th><th>Kalan</th><th>Durum</th><th>İlerleme</th><th>Küme ID</th></tr>")
            for rec in data:
                html.append(
                    f"<tr><td>{rec['ogrenci']}</td><td>{rec['bitis']}</td><td>{rec['kalan']}</td>"
                    f"<td>{rec['durum']}</td><td>{rec['ilerleme']}</td><td>{rec['kume_id']}</td></tr>"
                )
            html.append("</table></body></html>")
            doc = QTextDocument()
            doc.setHtml("".join(html))
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            doc.print(printer)
            return True
        except Exception:
            return False

    def _export_as_xlsx(self, path, data):
        try:
            import pandas as pd
            df = pd.DataFrame(data)
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Analiz")
            return True
        except Exception:
            return False

    def _export_as_csv(self, path, data):
        try:
            import csv
            if not data:
                open(path, "w", encoding="utf-8").close()
                return True
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                w.writeheader()
                w.writerows(data)
            return True
        except Exception:
            return False

    def _toast(self, msg: str):
        """Varsa utils.toast; yoksa MessageBox ile zarif uyarı."""
        try:
            from utils import toast
            toast.info(msg)
        except Exception:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Bilgi", msg)

    # RandevuTakvimi sınıfının içinde, _apply_table_style'i AŞAĞIDAKİ ile değiştir
    def _apply_table_style(self):
        """Modern görünüm + mevcut (kırmızı/sarı/yeşil) zeminleri KORU, zebra uygula (PyQt6 uyumlu)."""
        from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
        from PyQt6.QtGui import QColor, QBrush
        from PyQt6.QtCore import QSize, Qt

        class _ColorFriendlyDelegate(QStyledItemDelegate):
            def sizeHint(self, option, index):
                s = super().sizeHint(option, index)
                return QSize(s.width(), max(36, s.height() + 6))

            def paint(self, painter, option, index):
                try:
                    # 1) Modelden gelen arka planı uygula (statü rengi varsa)
                    bg_data = index.data(Qt.ItemDataRole.BackgroundRole)
                    if isinstance(bg_data, QBrush):
                        painter.save();
                        painter.fillRect(option.rect, bg_data);
                        painter.restore()
                    elif isinstance(bg_data, QColor):
                        painter.save();
                        painter.fillRect(option.rect, bg_data);
                        painter.restore()
                    else:
                        # 2) Zebra (koyu tonlar)
                        alt = QColor(247, 249, 252) if (index.row() % 2 == 0) else QColor(232, 238, 247)
                        painter.save();
                        painter.fillRect(option.rect, alt);
                        painter.restore()

                    # 3) Seçim vurgusu (PyQt6: QStyle.StateFlag.State_Selected)
                    if option.state & QStyle.StateFlag.State_Selected:
                        sel = QColor(59, 130, 246, 80)  # yarı saydam mavi
                        painter.save();
                        painter.fillRect(option.rect, sel);
                        painter.restore()

                    # default metin/ikon
                    super().paint(painter, option, index)
                except Exception:
                    # herhangi bir çizim hatasında en azından default render'a düş
                    super().paint(painter, option, index)

        self.tab.setAlternatingRowColors(False)
        self.tab.setShowGrid(False)
        self.tab.setSelectionBehavior(self.tab.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(self.tab.SelectionMode.ExtendedSelection)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setHighlightSections(False)
        self.tab.verticalHeader().setDefaultSectionSize(36)
        self.tab.setItemDelegate(_ColorFriendlyDelegate(self.tab))

        self.tab.setStyleSheet("""
            QTableWidget { background: #ffffff; gridline-color: #e5e7eb; font-size: 13px; }
            QHeaderView::section {
                background: #f8fafc; color: #111827; padding: 8px 10px;
                border: 1px solid #e5e7eb; font-weight: 600;
            }
            QTableCornerButton::section { background: #f8fafc; border: 1px solid #e5e7eb; }
            QProgressBar {
                border: 1px solid #d1d5db; border-radius: 6px; background: #f9fafb;
                min-height: 18px; text-align: center;
            }
            QProgressBar::chunk { border-radius: 6px; }
        """)

    # ---------- Sağ tık menüsü ----------
    def _install_context_menu(self):
        self.tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self._show_row_menu)

    # --- Tablo -> satır listesi
    def _table_rows(self):
        headers = [self.tab.horizontalHeaderItem(c).text()
                   for c in range(self.tab.columnCount())]
        rows = []
        for r in range(self.tab.rowCount()):
            row = []
            for c in range(self.tab.columnCount()):
                if c == self.COL_PROGRESS:
                    w = self.tab.cellWidget(r, c)
                    row.append(f"{w.value()}%" if w else "")
                else:
                    it = self.tab.item(r, c)
                    row.append(it.text() if it else "")
            rows.append(row)
        return headers, rows

    # --- Basit CSV kaydı (garantili)
    def _save_csv(self, path):
        import csv
        headers, rows = self._table_rows()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(headers)
            w.writerows(rows)
        return path

    # --- Eğer openpyxl varsa XLSX; yoksa CSV'ye düş
    def _save_xlsx_or_csv(self, path_xlsx="randevu_takvimi.xlsx"):
        try:
            import openpyxl
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            headers, rows = self._table_rows()
            ws.append(headers)
            for row in rows:
                ws.append(row)
            wb.save(path_xlsx)
            return path_xlsx, "xlsx"
        except Exception:
            # openpyxl yoksa CSV’ye düş
            import os
            p = os.path.splitext(path_xlsx)[0] + ".csv"
            self._save_csv(p)
            return p, "csv"

    # --- Basit PDF (HTML tablo + QTextDocument)
    def _save_pdf(self, path_pdf="randevu_takvimi.pdf"):
        from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize, QFont
        from PyQt6.QtCore import QMarginsF, QSizeF
        from PyQt6.QtPrintSupport import QPrinter
        from datetime import datetime
        headers, rows = self._table_rows()
        th = "".join(f"<th style='padding:8px 6px;border:1px solid #cbd5e1;background:#1e293b;color:#ffffff;font-size:9pt;'>{h}</th>" for h in headers)
        trs = []
        for i, row in enumerate(rows):
            tds = "".join(f"<td style='padding:6px 6px;border:1px solid #e2e8f0;font-size:8.5pt;'>{col}</td>" for col in row)
            bg = "#f8fafc" if i % 2 else "#ffffff"
            trs.append(f"<tr style='background:{bg}'>{tds}</tr>")
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        html = f"""
        <html><head><meta charset='utf-8'>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; color: #1e293b; }}
            h2 {{ color: #1e3a8a; margin-bottom: 4px; font-size: 14pt; }}
            .sub {{ color: #64748b; font-size: 8.5pt; margin-bottom: 12px; }}
            table {{ border-collapse: collapse; width: 100%; }}
        </style>
        </head><body>
        <h2>📅 Randevu ve Ödev Takip Çizelgesi</h2>
        <div class="sub">Oluşturulma Tarihi: {now_str} • Toplam Kayıt: {len(rows)}</div>
        <table cellspacing="0" cellpadding="0">
          <thead><tr>{th}</tr></thead>
          <tbody>{''.join(trs)}</tbody>
        </table>
        </body></html>
        """
        doc = QTextDocument()
        doc.setDefaultFont(QFont("Segoe UI", 9))
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path_pdf)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        layout = QPageLayout(printer.pageLayout())
        layout.setMargins(QMarginsF(10.0, 10.0, 10.0, 10.0))
        printer.setPageLayout(layout)
        doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size()))
        doc.setHtml(html)
        doc.print(printer)
        return path_pdf



    #s sağ tık menü whatsapp


    def _show_row_menu(self, pos):
        # Sağ tıklanan satırı görsel olarak seç
        idx = self.tab.indexAt(pos)
        if idx.isValid():
            self.tab.selectRow(idx.row())
        
        # Seçili satırları al
        rows = sorted({i.row() for i in self.tab.selectedIndexes()})
        if not rows:
            return

        # Modern Dashboard Dialogu Çağır
        self._open_context_dashboard(rows)

    def _open_context_dashboard(self, rows):
        """Sağ tık menüsü yerine geçen modern dashboard."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QGridLayout, QMessageBox, QWidget
        from PyQt6.QtCore import Qt, QSize
        from PyQt6.QtGui import QFont, QColor, QCursor

        # Seçili öğrenci bilgisi (İlk satırı baz al)
        oid = self._ogr_id_from_row(rows[0])
        student_name = "Seçili Öğrenci"
        if oid:
            con = db.get_conn()
            r = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (oid,)).fetchone()
            if r:
                student_name = f"{r['ad']} {r['soyad']}".strip()
        
        if len(rows) > 1:
            student_name = f"{len(rows)} Öğrenci Seçildi"

        # --- Dialog ---
        dlg = QDialog(self)
        dlg.setWindowTitle(f"İşlem Paneli — {student_name}")
        dlg.setFixedSize(650, 600) # YENİ YÜKSEKLİK (Butonlar eklendiği için)
        dlg.setStyleSheet("background-color: #f8fafc;")

        # --- Layout ---
        main = QVBoxLayout(dlg)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # 1. Header (Mavi degrade veya düz renk)
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background-color: #3b82f6;
                border-bottom: 1px solid #2563eb;
            }
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_h = QLabel(student_name)
        lbl_h.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        lbl_sub = QLabel("Yapmak istediğiniz işlemi seçin")
        lbl_sub.setStyleSheet("color: #dbeafe; font-size: 13px;")
        
        h_lay.addWidget(lbl_h)
        h_lay.addWidget(lbl_sub)
        main.addWidget(header)

        # 2. Content Area
        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(25, 25, 25, 25)
        c_lay.setSpacing(20)

        # -- Yardımcı Buton Oluşturucu --
        def _btn(text, subtext, icon, color_base, callback):
            b = QPushButton()
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setFixedHeight(80)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    text-align: left;
                    padding-left: 15px;
                }}
                QPushButton:hover {{
                    background-color: {color_base};
                    border: 1px solid {color_base};
                }}
                QPushButton:hover QLabel {{ color: white; }}
            """)
            
            # İçerik layout
            l = QHBoxLayout(b)
            l.setContentsMargins(15, 10, 15, 10)
            
            # İkon
            icn = QLabel(icon)
            icn.setStyleSheet("font-size: 28px; background: transparent;")
            # Text grubu
            v = QVBoxLayout()
            v.setSpacing(2)
            t1 = QLabel(text)
            t1.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b; background: transparent;")
            t1.setObjectName("title")
            t2 = QLabel(subtext)
            t2.setStyleSheet("font-size: 12px; color: #64748b; background: transparent;")
            t2.setObjectName("sub")
            v.addWidget(t1)
            v.addWidget(t2)
            
            l.addWidget(icn)
            l.addSpacing(10)
            l.addLayout(v)
            l.addStretch(1)
            
            if callback:
                b.clicked.connect(lambda: [dlg.accept(), callback()])
            
            return b

        # -- Grid Layout --
        grid = QGridLayout()
        grid.setSpacing(15)

        # 1. Ana Aksiyon (Ödev Formu)
        btn_open = _btn("Ödev Formunu Aç", "Görüntüle ve düzenle", "🚀", "#3b82f6", 
                        lambda: self._trigger_action(rows, "open"))
        # Tam genişlik
        c_lay.addWidget(btn_open)
        
        # WhatsApp Başlığı
        lbl_wa = QLabel("İletişim & Hatırlatma (WhatsApp)")
        lbl_wa.setStyleSheet("font-weight: bold; color: #475569; margin-top: 10px;")
        c_lay.addWidget(lbl_wa)

        # WhatsApp Grid
        wa_grid = QGridLayout()
        wa_grid.setSpacing(10)
        
        # Küçük buton stili
        def _sbtn(txt, icon, cb):
            b = QPushButton(f"{icon}  {txt}")
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setFixedHeight(40)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px;
                    color: #334155; font-size: 13px; font-weight: 600; text-align: left; padding-left: 12px;
                }
                QPushButton:hover { background-color: #dcfce7; border-color: #22c55e; color: #15803d; }
            """)
            b.clicked.connect(lambda: [dlg.accept(), cb()])
            return b

        wa_grid.addWidget(_sbtn("Bugün Hatırlat", "📅", lambda: self._open_whatsapp_batch_dialog("today")), 0, 0)
        wa_grid.addWidget(_sbtn("Yarın Hatırlat", "🌤️", lambda: self._open_whatsapp_batch_dialog("tomorrow")), 0, 1)
        wa_grid.addWidget(_sbtn("Gecikmiş Hatırlat", "⏰", lambda: self._open_whatsapp_batch_dialog("overdue")), 1, 0)
        wa_grid.addWidget(_sbtn("2 Gün Sonra", "⏭️", lambda: self._open_whatsapp_batch_dialog("in2days")), 1, 1)
        # Ekstralar
        wa_grid.addWidget(_sbtn("Hiç Gelmeyenler", "❌", lambda: self._open_whatsapp_batch_dialog("never")), 2, 0)
        wa_grid.addWidget(_sbtn("Kısmi Yapanlar", "🌗", lambda: self._open_whatsapp_batch_dialog("partial")), 2, 1)
        
        # YENİ: Tebrik Mesajı (Tüm genişlik)
        btn_congrats = _sbtn("Tebrik Et (Tam Puan) 🌟", "🎉", lambda: self._open_whatsapp_batch_dialog("congratulate"))
        btn_congrats.setStyleSheet("""
            QPushButton {
                background-color: #fefce8; border: 1px solid #fef08a; border-radius: 8px;
                color: #854d0e; font-size: 13px; font-weight: 600; text-align: left; padding-left: 12px;
            }
            QPushButton:hover { background-color: #fef9c3; border-color: #fde047; color: #a16207; }
        """)
        wa_grid.addWidget(btn_congrats, 3, 0, 1, 2)

        c_lay.addLayout(wa_grid)

        # Alt Bölüm: Analiz ve Export (Yan Yana)
        hbox = QHBoxLayout()
        hbox.setSpacing(20)

        # Analiz Kolonu
        v_an = QVBoxLayout()
        lbl_an = QLabel("Analiz & İşlem")
        lbl_an.setStyleSheet("font-weight: bold; color: #475569;")
        v_an.addWidget(lbl_an)
        
        # YENİ: Hızlı Not
        b_note = _sbtn("Hızlı Not Ekle", "📝", lambda: self._hizli_not_ekle_dialog(rows))
        b_note.setStyleSheet(b_note.styleSheet().replace("#dcfce7", "#e0f2fe").replace("#22c55e", "#38bdf8").replace("#15803d", "#0369a1")) # Mavi
        v_an.addWidget(b_note)
        
        b_an1 = _sbtn("Kitap İlerlemesi", "📊", lambda: self._trigger_action(rows, "kitap_analiz"))
        b_an1.setStyleSheet(b_an1.styleSheet().replace("#dcfce7", "#e0e7ff").replace("#22c55e", "#6366f1").replace("#15803d", "#4338ca")) # Mor hover
        v_an.addWidget(b_an1)
        
        b_an2 = _sbtn("Öğrenci Özeti", "🆔", lambda: self._trigger_action(rows, "ozet"))
        b_an2.setStyleSheet(b_an2.styleSheet().replace("#dcfce7", "#e0e7ff").replace("#22c55e", "#6366f1").replace("#15803d", "#4338ca"))
        v_an.addWidget(b_an2)

        # YENİ: Akıllı Analiz Butonları
        b_an3 = _sbtn("Koç Yorumu 🤖", "🤖", lambda: self._trigger_action(rows, "akilli_yorum"))
        b_an3.setStyleSheet(b_an3.styleSheet().replace("#dcfce7", "#cffafe").replace("#22c55e", "#22d3ee").replace("#15803d", "#0891b2")) # Cyan
        v_an.addWidget(b_an3)

        b_an4 = _sbtn("Haftalık Karne", "📈", lambda: self._trigger_action(rows, "haftalik_karne"))
        b_an4.setStyleSheet(b_an4.styleSheet().replace("#dcfce7", "#ecfccb").replace("#22c55e", "#84cc16").replace("#15803d", "#4d7c0f")) # Lime/Yeşil
        v_an.addWidget(b_an4)
        
        v_an.addStretch()
        
        # Export Kolonu
        v_ex = QVBoxLayout()
        lbl_ex = QLabel("Dışa Aktar")
        lbl_ex.setStyleSheet("font-weight: bold; color: #475569;")
        v_ex.addWidget(lbl_ex)
        
        b_ex1 = _sbtn("Excel'e Kaydet", "📗", lambda: self._export_rows(rows, "xlsx"))
        b_ex1.setStyleSheet(b_ex1.styleSheet().replace("#dcfce7", "#ffedd5").replace("#22c55e", "#f97316").replace("#15803d", "#c2410c")) # Turuncu hover
        v_ex.addWidget(b_ex1)

        b_ex2 = _sbtn("PDF Oluştur", "📕", lambda: self._export_rows(rows, "pdf"))
        b_ex2.setStyleSheet(b_ex2.styleSheet().replace("#dcfce7", "#fee2e2").replace("#22c55e", "#ef4444").replace("#15803d", "#b91c1c")) # Kırmızı hover
        v_ex.addWidget(b_ex2)
        v_ex.addStretch()

        hbox.addLayout(v_an)
        hbox.addLayout(v_ex)
        
        c_lay.addLayout(hbox)
        main.addWidget(content)

        dlg.exec()

    def _hizli_not_ekle_dialog(self, rows):
        """Seçili öğrencinin son ödevine hızlı not ekler."""
        if not rows: return
        
        # Öğrenciyi bul
        oid = self._ogr_id_from_row(rows[0])
        if not oid: return
        
        # Son ödev kümesini bul
        con = db.get_conn()
        last_set = con.execute("SELECT id, aciklama FROM odev_kume WHERE ogrenci_id=? ORDER BY bitis_tarihi DESC LIMIT 1", (oid,)).fetchone()
        
        if not last_set:
            QMessageBox.warning(self, "Hata", "Bu öğrenciye ait aktif veya geçmiş bir ödev kaydı bulunamadı.\nNot eklemek için önce 'Ödev Formunu Aç' butonunu kullanın.")
            return

        set_id = last_set['id']
        old_note = last_set['aciklama'] or ""

        # Not Dialogu
        d = QDialog(self)
        d.setWindowTitle("Hızlı Not Ekle 📝")
        d.setFixedSize(400, 300)
        d.setStyleSheet("background: white;")
        
        ly = QVBoxLayout(d)
        ly.addWidget(QLabel("Eklenecek Not:"))
        
        txt = QTextEdit(d)
        txt.setPlaceholderText("Örn: Haftaya deneme var, konu ekle...")
        txt.setStyleSheet("border: 1px solid #ccc; border-radius: 6px; padding: 8px;")
        ly.addWidget(txt)
        
        # Eski notu göster (salt okunur)
        if old_note:
            ly.addWidget(QLabel("Mevcut Not:"))
            old_view = QTextEdit(d)
            old_view.setReadOnly(True)
            old_view.setPlainText(old_note)
            old_view.setFixedHeight(60)
            old_view.setStyleSheet("background: #f1f5f9; color: #64748b; border: none;")
            ly.addWidget(old_view)
        
        btn_save = QPushButton("Kaydet ve Kapat")
        btn_save.setStyleSheet("background: #3b82f6; color: white; font-weight: bold; padding: 10px; border-radius: 6px;")
        btn_save.clicked.connect(d.accept)
        ly.addWidget(btn_save)
        
        if d.exec():
            new_note = txt.toPlainText().strip()
            if new_note:
                # Tarihli not ekle
                from datetime import datetime
                stamp = datetime.now().strftime("%d-%m %H:%M")
                final_note = f"{old_note}\n\n[{stamp}] {new_note}" if old_note else f"[{stamp}] {new_note}"
                
                with db.get_conn() as con:
                    con.execute("UPDATE odev_kume SET aciklama=? WHERE id=?", (final_note, set_id))
                    con.commit()
                # Anlık önbelleğe ekle (DB gecikmesini bypass et)
                if not hasattr(self, "_today_badges"):
                    self._today_badges = set()
                try:
                    if set_data and "ogrenci_id" in set_data:
                        self._today_badges.add(int(set_data["ogrenci_id"]))
                except Exception:
                    pass

                QMessageBox.information(self, "Başarılı", "Not başarıyla kaydedildi.")
                self._load_from_db() # Tabloyu yenile (belki notu gösteriyordur)

    def _trigger_action(self, rows, action):
        """Dashboard callback router."""
        if not rows: return
        oid = self._ogr_id_from_row(rows[0])
        
        if action == "open":
            if oid: self._open_tracking_for_student(int(oid))
        elif action == "kitap_analiz":
            if oid: self._show_kitap_ilerleme_table(int(oid)) # Yeni tablo metodu
        elif action == "ozet":
            if oid: self._show_ogrenci_ozet(int(oid))
        elif action == "akilli_yorum":
            if oid: self._show_akilli_yorum(int(oid))
        elif action == "haftalik_karne":
            if oid: self._show_haftalik_karne(int(oid))
            return

    def _show_akilli_yorum(self, oid):
        """Öğrencinin durumunu analiz edip sözel 'Koç Yorumu' üretir."""
        con = db.get_conn()
        
        # 1) İstatistikleri Çek
        # Not: 'ok' -> odev_kume alias
        stats = con.execute("""
            SELECT 
                COUNT(*),
                SUM(CASE WHEN lower(COALESCE(durum,'')) IN ('yapildi','tamam','1','true','ok','bitti') THEN 1 ELSE 0 END),
                SUM(CASE WHEN lower(COALESCE(durum,'')) NOT IN ('yapildi','tamam','1','true','ok','bitti') AND date(ok.bitis_tarihi) < date('now') THEN 1 ELSE 0 END)
            FROM odev o
            JOIN odev_kume ok ON o.kume_id = ok.id
            WHERE ok.ogrenci_id=?
        """, (oid,)).fetchone()
        
        total = stats[0] or 0
        done = stats[1] or 0
        overdue = stats[2] or 0
        ratio = (done / total * 100) if total > 0 else 0
        
        ad = self._ogrenci_adsoyad(oid)
        
        # 2) Senaryo Analizi
        if total == 0:
            mood = "neutral"
            title = "BAŞLANGIÇ AŞAMASI"
            text = (
                f"{ad} için sistemde henüz kayıtlı ödev bulunmuyor.\n\n"
                "💡 Tavsiye: İlk ödev atamasını yaparak süreci başlatabilir, "
                "öğrencinin disiplinli bir başlangıç yapmasını sağlayabilirsiniz."
            )
            color = "#64748b" # gri
        elif ratio >= 90:
            mood = "happy"
            title = "MÜKEMMEL PERFORMANS"
            text = (
                f"Harika! {ad}, ödevlerinin %{int(ratio)}'ini tamamlamış durumda.\n\n"
                "🌟 Bu yüksek disiplin ve sorumluluk bilinci, başarının en büyük anahtarı. "
                "Öğrenciyi takdir ederek motivasyonunu daha da artırabilirsiniz."
            )
            color = "#15803d" # yeşil
        elif ratio >= 70:
            mood = "good"
            title = "İYİ GİDİŞAT"
            text = (
                f"{ad} genel olarak iyi bir seyir izliyor (%{int(ratio)} başarı).\n\n"
                f"✅ Çoğu görev tamamlanmış. " + 
                (f"Ancak {overdue} adet gecikmiş ödev görünüyor; bunlar eritilirse mükemmel olacak." if overdue > 0 else "İstikrarı koruması önemli.")
            )
            color = "#0ea5e9" # mavi
        elif ratio >= 50:
            mood = "mediocre"
            title = "POTANSİYEL VAR"
            text = (
                f"{ad} orta seviyede ilerliyor (%{int(ratio)} başarı).\n\n"
                f"⚠️ Tamamlanmayan ödev sayısı ({total-done}) biraz dikkat çekici. "
                "Öğrencinin çalışma düzenini gözden geçirmesi ve daha planlı ilerlemesi gerekebilir."
            )
            color = "#ca8a04" # sarı/turuncu
        else:
            mood = "bad"
            title = "DİKKAT GEREKTİRİYOR"
            text = (
                f"{ad} için işler biraz sıkıntılı görünüyor (%{int(ratio)} başarı).\n\n"
                f"🚨 {overdue} adet gecikmiş ödev ve toplamda {total-done} eksik var. "
                "Acil bir motivasyon görüşmesi yapılması ve çalışma programının hafifletilerek yeniden düzenlenmesi yararlı olabilir."
            )
            color = "#b91c1c" # kırmızı

        # 3) Dialog Gösterimi
        from PyQt6.QtWidgets import QTextEdit
        d = QDialog(self)
        d.setWindowTitle("Koç Yorumu 🤖")
        d.resize(400, 360)
        d.setStyleSheet("background: #ffffff;")
        
        layout = QVBoxLayout(d)
        layout.setSpacing(15)
        
        # İkon
        icon_map = {"happy": "🌟", "good": "👍", "mediocre": "🤔", "bad": "🚨", "neutral": "ℹ️"}
        lbl_icon = QLabel(icon_map[mood])
        lbl_icon.setStyleSheet("font-size: 54px;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_icon)
        
        # Başlık
        lbl_h = QLabel(title)
        lbl_h.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {color}; letter-spacing: 1px;")
        lbl_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_h)
        
        # Metin Kutusu
        txt_box = QTextEdit()
        txt_box.setPlainText(text)
        txt_box.setReadOnly(True)
        txt_box.setStyleSheet(f"""
            QTextEdit {{
                background-color: #f8fafc;
                border: 2px solid {color}40; /* %25 opacity hex approx */
                border-radius: 12px;
                padding: 16px;
                font-size: 14px;
                color: #334155;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(txt_box)
        
        # Kapat Butonu
        btn = QPushButton("Tamam")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: white; font-weight: bold; 
                padding: 10px; border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        btn.clicked.connect(d.accept)
        layout.addWidget(btn)
        
        d.exec()

    def _show_haftalik_karne(self, oid):
        """Son 7 gündeki performansı gösterir."""
        from datetime import datetime, timedelta
        from PyQt6.QtWidgets import QGridLayout
        
        # 1) İstatistik Hesapla
        # Son 7 gün içinde BİTİŞ TARİHİ olan kümeleri al
        con = db.get_conn()
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        # Kümeleri bul
        kume_ids = [r[0] for r in con.execute("""
            SELECT id FROM odev_kume 
            WHERE ogrenci_id=? AND bitis_tarihi >= ?
        """, (oid, seven_days_ago)).fetchall()]
        
        if not kume_ids:
            QMessageBox.information(self, "Bilgi", "Son 7 günde bitiş tarihi olan ödev bulunamadı.")
            return

        # İstatistik
        toplam = 0
        yapilan = 0
        
        placeholders = ",".join("?" * len(kume_ids))
        all_odevs = con.execute(f"SELECT durum FROM odev WHERE kume_id IN ({placeholders})", kume_ids).fetchall()
        
        toplam = len(all_odevs)
        for ro in all_odevs:
            st = (ro[0] or "").lower()
            if st in ('yapildi', 'tamam', '1', 'true', 'ok', 'bitti'):
                yapilan += 1
                
        basari = int((yapilan / toplam * 100)) if toplam > 0 else 0
        
        # 2) Görselleştir (Dialog)
        d = QDialog(self)
        d.setWindowTitle("Haftalık Karne 📊")
        d.resize(320, 400)
        d.setStyleSheet("background: #ffffff;")
        
        l = QVBoxLayout(d)
        l.setSpacing(15)
        
        # Başlık ve Tarih
        l.addWidget(QLabel(f"📅 Son 7 Gün Özeti", alignment=Qt.AlignmentFlag.AlignCenter))
        
        # Büyük Puan
        color = "#16a34a" if basari >= 80 else ("#ca8a04" if basari >= 50 else "#dc2626")
        
        lbl_score = QLabel(f"%{basari}")
        lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_score.setStyleSheet(f"font-size: 64px; font-weight: 900; color: {color};")
        l.addWidget(lbl_score)
        
        lbl_status = QLabel("MÜKEMMEL" if basari >= 90 else ("İYİ" if basari >= 70 else "GELİŞTİRİLMELİ"))
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color}; letter-spacing: 2px;")
        l.addWidget(lbl_status)
        
        # Detaylar
        grid = QGridLayout()
        def _stat_box(vals):
            w = QWidget()
            w.setStyleSheet("background: #f8fafc; border-radius: 8px; padding: 10px;")
            vl = QVBoxLayout(w)
            vl.setContentsMargins(0,0,0,0)
            vl.addWidget(QLabel(vals[0], styleSheet="color:#64748b; font-size:11px;"))
            vl.addWidget(QLabel(str(vals[1]), styleSheet="color:#0f172a; font-size:18px; font-weight:bold;"))
            return w
            
        grid.addWidget(_stat_box(("TOPLAM ÖDEV", toplam)), 0, 0)
        grid.addWidget(_stat_box(("TAMAMLANAN", yapilan)), 0, 1)
        grid.addWidget(_stat_box(("EKSİK", toplam - yapilan)), 1, 0)
        grid.addWidget(_stat_box(("KÜME SAYISI", len(kume_ids))), 1, 1)
        l.addLayout(grid)
        
        btn = QPushButton("Kapat")
        btn.setStyleSheet(f"background: {color}; color: white; border-radius: 8px; padding: 10px; font-weight: bold;")
        btn.clicked.connect(d.accept)
        l.addWidget(btn)
        
        d.exec()

    #f

    # ---------- Yardımcı görsel bileşen
    def _popup_friendly(self, cmb: QComboBox, min_w=240, max_items=14):
        cmb.setMaxVisibleItems(max_items)
        try:
            cmb.view().setMinimumWidth(min_w)
            cmb.view().setUniformItemSizes(True)
        except Exception:
            v = QListView(cmb)
            v.setMinimumWidth(min_w)
            v.setUniformItemSizes(True)
            cmb.setView(v)

    # ---------- DB yükleme & filtre & sıralama
    def _yenile_ogrenci_listesi(self):
        try:
            con = db.get_conn()
            rows = con.execute("SELECT id, ad, soyad FROM ogrenci ORDER BY ad, soyad").fetchall()
            self.cmbOgr.blockSignals(True)
            while self.cmbOgr.count() > 1:
                self.cmbOgr.removeItem(1)
            for r in rows:
                self.cmbOgr.addItem(f"{r['ad']} {r['soyad']}".strip(), userData=int(r['id']))
        finally:
            self.cmbOgr.blockSignals(False)

    def _on_tarih_tip_degisti(self):
        # checkbox ile senkron
        if self.cmbTarih.currentText() == "Yalnız geciken":
            if not self.chkYalnizGeciken.isChecked():
                self.chkYalnizGeciken.setChecked(True)
        else:
            if self.chkYalnizGeciken.isChecked():
                self.chkYalnizGeciken.setChecked(False)
        self._load_from_db()

    def _yalniz_geciken_checkbox_senkron(self, checked: bool):
        if checked:
            self.cmbTarih.setCurrentText("Yalnız geciken")
        elif self.cmbTarih.currentText() == "Yalnız geciken":
            self.cmbTarih.setCurrentText("Tümü")

    def _on_dt_changed(self, _):
        if self.cmbTarih.currentText() != "Seçili Tarih":
            self.cmbTarih.blockSignals(True)
            self.cmbTarih.setCurrentText("Seçili Tarih")
            self.cmbTarih.blockSignals(False)
        self._load_from_db()

    #s ****
    def _ensure_tarih_options(self):
        """
        cmbTarih içinde eksik olan filtreleri, mevcut sıralamayı bozmadan ekler.
        İstemezsen eklemez; ama ekli değilse otomatik eklenir.
        """
        required = [
            "Tümü",
            "Yalnız geciken",
            "Bugün",
            "Yarın",
            "Bu Hafta",
            "Önümüzdeki 7 gün",
            "Seçili Tarih",
            "Tarihi boş olanlar",
            # Ek pratik filtreler:
            "Tamamlananlar",
            "Kısmi Tamamlananlar",
            "Geciken + Bugün",
            "Bu Ay",
            "Son 7 gün",
            "Son 30 gün",
            "Önümüzdeki 14 gün",
        ]
        existing = {self.cmbTarih.itemText(i) for i in range(self.cmbTarih.count())}
        missing = [x for x in required if x not in existing]
        if not missing:
            return
        cur_txt = self.cmbTarih.currentText()
        self.cmbTarih.blockSignals(True)
        for x in missing:
            self.cmbTarih.addItem(x)
        # mevcut seçim korunur
        self.cmbTarih.setCurrentText(cur_txt)
        self.cmbTarih.blockSignals(False)

    def _yenile_ogrenci_listesi(self):
        import db
        try:
            con = db.get_conn()
            rows = con.execute(
                "SELECT id, ad, soyad FROM ogrenci ORDER BY ad, soyad"
            ).fetchall()
            self.cmbOgr.blockSignals(True)
            # İlk eleman “Tümü” kalsın
            while self.cmbOgr.count() > 1:
                self.cmbOgr.removeItem(1)
            for r in rows:
                self.cmbOgr.addItem(f"{r['ad']} {r['soyad']}".strip(), userData=int(r['id']))
        finally:
            self.cmbOgr.blockSignals(False)

    def _on_tarih_tip_degisti(self):
        # Seçenekler eksikse görünür yap
        self._ensure_tarih_options()

        # checkbox ile senkron
        if self.cmbTarih.currentText() == "Yalnız geciken":
            if not self.chkYalnizGeciken.isChecked():
                self.chkYalnizGeciken.setChecked(True)
        else:
            if self.chkYalnizGeciken.isChecked():
                self.chkYalnizGeciken.setChecked(False)

        # (opsiyonel) sadece Seçili Tarih’te tarih alanını aktif et
        # self.dtSec.setEnabled(self.cmbTarih.currentText() == "Seçili Tarih")

        self._load_from_db()

    def _yalniz_geciken_checkbox_senkron(self, checked: bool):
        """Checkbox değişince combobox'u eşitle."""
        if checked:
            self.cmbTarih.setCurrentText("Yalnız geciken")
        elif self.cmbTarih.currentText() == "Yalnız geciken":
            self.cmbTarih.setCurrentText("Tümü")

    def _on_dt_changed(self, _):
        """Takvimden gün seçilince otomatik 'Seçili Tarih'e geç ve yenile."""
        if self.cmbTarih.currentText() != "Seçili Tarih":
            self.cmbTarih.blockSignals(True)
            self.cmbTarih.setCurrentText("Seçili Tarih")
            self.cmbTarih.blockSignals(False)
        self._load_from_db()

    def _satir_filtresi(self, r) -> bool:
        """Tüm tarih/ilerleme filtreleri burada çözülür."""
        from datetime import date, datetime, timedelta

        # Seçenekleri garanti altına al
        self._ensure_tarih_options()

        bitis_str = (r["bitis"] or "").strip()
        tsec = (self.cmbTarih.currentText() or "").strip()
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # --- Arama Filtresi (YENİ) ---
        search_txt = self.txtAra.text().strip().lower()
        if search_txt:
            ad_soyad = f"{r['ad']} {r['soyad']}".strip().lower()
            if search_txt not in ad_soyad:
                return False

        # --- yardımcılar ---
        def _parse(s: str):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

        def _istat(kume_id: int):
            """
            _kume_istatistik çıktıları:
              eski sürüm: days_left, perc, toplam, bitti, toplam_dk
              yeni sürüm: days_left, label, perc, toplam, bitti, toplam_dk
            her iki durum için de güvenli ayrıştırma yapıyoruz.
            """
            stat = self._kume_istatistik(kume_id, bitis_str)
            if isinstance(stat, (list, tuple)):
                if len(stat) == 6:
                    _dl, _lbl, perc, toplam, bitti, _dk = stat
                else:
                    _dl, perc, toplam, bitti, _dk = stat
            else:
                perc, toplam, bitti = 0, 0, 0
            return perc, toplam, bitti

        d = _parse(bitis_str)

        # ---- Öğrenci filtresi (aynen) ----
        ogr_filter_id = self.cmbOgr.currentData()
        if ogr_filter_id is not None and int(ogr_filter_id) != int(r["ogr_id"]):
            return False

        # ---- Tarih/ilerleme filtreleri ----
        if tsec in ("", "Tümü"):
            return True

        if tsec == "Yalnız geciken":
            # Tanım: bitiş tarihi bugün öncesi VE kümede hiç yapılmış ödev yok (bitti == 0)
            if d is None or not (d < today):
                return False
            kume_id = int(r["kume_id"])
            _perc, _toplam, bitti = _istat(kume_id)
            return bitti == 0

        if tsec == "Bugün":
            return (d == today)

        if tsec == "Yarın":
            return (d == tomorrow)

        if tsec == "Bu Hafta":
            start = today - timedelta(days=today.weekday())  # pazartesi
            end = start + timedelta(days=6)
            return (d is not None) and (start <= d <= end)

        if tsec == "Önümüzdeki 7 gün":
            rng_start, rng_end = today, today + timedelta(days=7)
            return (d is not None) and (rng_start <= d <= rng_end)

        if tsec == "Seçili Tarih":
            return bitis_str == self.dtSec.date().toString("yyyy-MM-dd")

        if tsec == "Tarihi boş olanlar":
            return not bitis_str

        # ---- Ek pratik filtreler ----
        if tsec == "Tamamlananlar":
            kume_id = int(r["kume_id"])
            perc, toplam, _bitti = _istat(kume_id)
            return (toplam > 0 and perc >= 100)

        if tsec == "Kısmi Tamamlananlar":
            kume_id = int(r["kume_id"])
            _perc, toplam, bitti = _istat(kume_id)
            return (toplam > 0 and 0 < bitti < toplam)

        if tsec == "Geciken + Bugün":
            return (d is not None) and (d <= today)

        if tsec == "Bu Ay":
            return (d is not None) and (d.year == today.year and d.month == today.month)

        if tsec == "Son 7 gün":
            start = today - timedelta(days=7)
            return (d is not None) and (start <= d <= today)

        if tsec == "Son 30 gün":
            start = today - timedelta(days=30)
            return (d is not None) and (start <= d <= today)

        if tsec == "Önümüzdeki 14 gün":
            end = today + timedelta(days=14)
            return (d is not None) and (today <= d <= end)

        # bilinmeyen bir seçenek geldiyse eleme yapma
        return True
    #f ****

    def _sirala(self, rows: list) -> list:
        secim = (self.cmbSirala.currentText() or "").lower()
        azalan = "azalan" in secim

        def _safe_int(x, d=0):
            try: return int(x)
            except Exception: return d
        def _norm(s): return (s or "").strip().casefold()

        if "ad soyad" in secim:
            return sorted(rows, key=lambda r: (_norm(r["ad"]), _norm(r["soyad"])), reverse=azalan)
        if "küme id" in secim or "k\u00fcme id" in secim:
            return sorted(rows, key=lambda r: _safe_int(r["kume_id"], 0), reverse=azalan)
        # Bitiş
        keyfunc = (lambda r: ((r["bitis"] or "9999-12-31"), _safe_int(r["kume_id"], 0))) if not azalan \
                  else (lambda r: ((r["bitis"] or "0000-00-00"), _safe_int(r["kume_id"], 0)))
        return sorted(rows, key=keyfunc, reverse=azalan)



    #s-----
    # CLR_RUNNING = None  # 3+ gün varsa satır renksiz kalsın

    # =========================
    #  Yardımcılar (yeni)
    # =========================
    def _compute_row_state(self, *, days_left, perc, toplam):
        """
        Görsel durum önceliği:
          DONE > OVERDUE > TODAY > SOON(<=2) > RUNNING(>2) > NODATE
        Döner: (state_str, rgb_tuple_or_None)
        """
        # %100 tamam ise
        if toplam > 0 and perc >= 100:
            return "DONE", self.CLR_DONE

        # tarih yoksa
        if days_left is None:
            return "NODATE", self.CLR_NODATE

        # gün farkını güvenli tamsayıya çevir
        try:
            d = int(days_left)
        except Exception:
            return "NODATE", self.CLR_NODATE

        # durumlar
        if d < 0:
            return "OVERDUE", self.CLR_OVERDUE
        if d == 0:
            return "TODAY", self.CLR_TODAY
        if d <= 2:
            return "SOON", self.CLR_SOON

        # 3+ gün: satır renksiz
        return "RUNNING", None

    def _paint_row_background(self, row_index: int, rgb_tuple):
        """Tüm hücrelerin arka planını aynı açık renge boyar (None ise hiçbir şey yapmaz)."""
        if not rgb_tuple:
            return
        from PyQt6.QtGui import QColor
        qcol = QColor(*rgb_tuple)
        for c in range(self.tab.columnCount()):
            it = self.tab.item(row_index, c)
            if it:
                it.setBackground(qcol)

    # =========================
    #  _load_from_db (GÜNCEL)
    # =========================

    def _load_from_db(self):
        from PyQt6.QtWidgets import QProgressBar, QTableWidgetItem
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import QDate, Qt
        from datetime import date, timedelta, datetime
        import db

        # --- Lokal renkler (dış sabitlere ihtiyaç yok) ---
        CLR_DONE = (232, 245, 233)  # yeşilimsi (tamamlandı)
        CLR_OVERDUE = (255, 235, 238)  # açık kırmızı (gecikmiş)
        CLR_TODAY = (255, 243, 224)  # açık turuncu (bugün)
        CLR_SOON = (255, 249, 196)  # açık sarı (<=2 gün)
        CLR_NODATE = (243, 244, 246)  # hafif gri (tarih yok)

        def _state(days_left, perc, toplam, bitti):
            """
            Tek noktadan görsel durum:
              DONE(perc=100) > PARTIAL(0<bitti<toplam) > OVERDUE(d<0) >
              TODAY(d==0) > SOON(d<=2) > RUNNING(>2) > NODATE
            """
            if toplam > 0 and perc >= 100:
                return "DONE", CLR_DONE
            if toplam > 0 and 0 < bitti < toplam:
                return "PARTIAL", CLR_SOON
            if days_left is None:
                return "NODATE", CLR_NODATE
            try:
                d = int(days_left)
            except Exception:
                return "NODATE", CLR_NODATE
            if d < 0:  return "OVERDUE", CLR_OVERDUE
            if d == 0: return "TODAY", CLR_TODAY
            if d <= 2: return "SOON", CLR_SOON
            return "RUNNING", None

        def _badge(state: str) -> str:
            return {
                "DONE": "✅", "PARTIAL": "🟡", "OVERDUE": "🔴",
                "TODAY": "📌", "SOON": "🟡", "RUNNING": "🟦", "NODATE": "🔍"
            }.get(state, "")

        def _durum_yazi(days_left, toplam, bitti, perc):
            if toplam > 0 and bitti >= toplam:
                return "Tamamlandı"
            if toplam > 0 and 0 < bitti < toplam:
                return "Kısmi Tamamlandı"
            d = None
            try:
                d = int(days_left) if days_left is not None else None
            except Exception:
                pass
            if d is None: return "Tarih yok"
            if d < 0:     return "Gecikmiş"
            if d == 0:    return "Bugün"
            if d == 1:    return "Yarın"
            return f"{d} gün kaldı"

        con = db.get_conn()
        rows = con.execute("""
            SELECT k.id AS kume_id, COALESCE(k.bitis_tarihi,'') AS bitis,
                   o.id AS ogr_id, o.ad, o.soyad
            FROM odev_kume k JOIN ogrenci o ON o.id = k.ogrenci_id
            ORDER BY k.id ASC
        """).fetchall()

        # Mevcut filtre ve sıralamanı kullan
        filt = [r for r in rows if self._satir_filtresi(r)]
        filt = self._sirala(filt)

        self.tab.setRowCount(0)
        bugun = QDate.currentDate().toString("yyyy-MM-dd")

        for r in filt:
            i = self.tab.rowCount()
            self.tab.insertRow(i)

            adsoyad = f"{r['ad']} {r['soyad']}".strip()
            bitis = r["bitis"] or ""
            kume_id = int(r["kume_id"])

            # --- İstatistik: her iki imza ile de uyumlu ---
            stat = self._kume_istatistik(kume_id, bitis)
            # olası dönüşler:
            # (days_left, "", perc, toplam, bitti, toplam_dk)  -> eski
            # (days_left,      perc, toplam, bitti, toplam_dk) -> yeni
            if isinstance(stat, (list, tuple)):
                if len(stat) == 6:
                    days_left, _old_label, perc, toplam, bitti, toplam_dk = stat
                elif len(stat) == 5:
                    days_left, perc, toplam, bitti, toplam_dk = stat
                else:
                    # beklenmedik: güvenli varsayılanlar
                    days_left, perc, toplam, bitti, toplam_dk = None, 0, 0, 0, 0
            else:
                days_left, perc, toplam, bitti, toplam_dk = None, 0, 0, 0, 0

            state, rgb = _state(days_left, perc, toplam, bitti)
            badge = _badge(state)

            # 0) Öğrenci
            self.tab.setItem(i, self.COL_AD, QTableWidgetItem(adsoyad))

            # 1) Bitiş
            self.tab.setItem(i, self.COL_BITIS, QTableWidgetItem(bitis))

            # 2) Kalan
            it_kalan = QTableWidgetItem()
            if toplam > 0 and perc >= 100:
                it_kalan.setText(f"{badge} ✓ tamam")
                it_kalan.setBackground(QColor(*CLR_DONE))
            else:
                if days_left is None:
                    it_kalan.setText(f"{badge} -")
                    if not bitis:
                        it_kalan.setBackground(QColor(*CLR_NODATE))
                elif days_left == 0:
                    it_kalan.setText(f"{badge} 0 (bugün)")
                    it_kalan.setBackground(QColor(*CLR_TODAY))
                else:
                    it_kalan.setText(f"{badge} {days_left:+d} g")
                    if days_left < 0:
                        it_kalan.setBackground(QColor(*CLR_OVERDUE))
                    elif days_left <= 2:
                        it_kalan.setBackground(QColor(*CLR_SOON))
            self.tab.setItem(i, self.COL_KALAN, it_kalan)

            # 3) Durum
            durum_txt = _durum_yazi(days_left, toplam, bitti, perc)
            it_durum = QTableWidgetItem(durum_txt)
            color_map = {
                "DONE": CLR_DONE, "PARTIAL": CLR_SOON, "OVERDUE": CLR_OVERDUE,
                "TODAY": CLR_TODAY, "SOON": CLR_SOON, "NODATE": CLR_NODATE
            }
            if state in color_map and color_map[state]:
                it_durum.setBackground(QColor(*color_map[state]))
            self.tab.setItem(i, self.COL_DURUM, it_durum)

            # 4) Progress
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(perc)
            bar.setFormat(f"%p%  ({bitti}/{toplam})")
            bar.setTextVisible(True)
            self.tab.setCellWidget(i, self.COL_PROGRESS, bar)

            # 5) Küme ID (+ ogrenci_id UserRole)
            it_kume = QTableWidgetItem(str(kume_id))
            it_kume.setData(Qt.ItemDataRole.UserRole, int(r["ogr_id"]))
            self.tab.setItem(i, self.COL_KUME, it_kume)

            # İsteğe bağlı: bitiş bugüne eşitse satırı hafif vurgula (tamamlanmışlar hariç)
            if (bitis or "") == bugun and not (toplam > 0 and perc >= 100):
                for c in range(self.tab.columnCount()):
                    it = self.tab.item(i, c)
                    if it:
                        it.setBackground(QColor(*CLR_TODAY))

        # KPI Metrikleri Hesaplama ve Güncelleme
        total_kumes = len(rows)
        overdue_kumes = 0
        soon_kumes = 0
        done_kumes = 0
        total_perc = 0

        for r in rows:
            k_id = int(r["kume_id"])
            b_str = r["bitis"] or ""
            st = self._kume_istatistik(k_id, b_str)
            if isinstance(st, (list, tuple)):
                if len(st) == 6: dl, _, p, top, bit, _ = st
                elif len(st) == 5: dl, p, top, bit, _ = st
                else: dl, p, top, bit = None, 0, 0, 0
            else: dl, p, top, bit = None, 0, 0, 0

            total_perc += p
            if top > 0 and bit >= top:
                done_kumes += 1
            elif dl is not None:
                try:
                    d_int = int(dl)
                    if d_int < 0: overdue_kumes += 1
                    elif d_int <= 3: soon_kumes += 1
                except Exception:
                    pass

        avg_p = int(round(total_perc / total_kumes)) if total_kumes > 0 else 0

        if hasattr(self, 'lbl_kpi_total'): self.lbl_kpi_total.setText(f"{total_kumes} Küme")
        if hasattr(self, 'lbl_kpi_overdue'): self.lbl_kpi_overdue.setText(f"{overdue_kumes} Gecikme")
        if hasattr(self, 'lbl_kpi_soon'): self.lbl_kpi_soon.setText(f"{soon_kumes} Küme")
        if hasattr(self, 'lbl_kpi_done'): self.lbl_kpi_done.setText(f"{done_kumes} Küme (%{avg_p})")

        if hasattr(self, 'lbl_table_summary'):
            self.lbl_table_summary.setText(f"📊 Tabloda <b>{len(filt)}</b> küme listeleniyor (Toplam: {total_kumes})")

        # Sağ detay panelini güncelle
        self._on_table_selection_changed()
    #f-----

    # =========================================================================
    # SAĞ DETAY PANELİ VE HIZLI EYLEM METOTLARI
    # =========================================================================
    def _set_quick_filter(self, filter_val: str):
        if hasattr(self, 'cmbTarih'):
            self.cmbTarih.setCurrentText(filter_val)

    def _clear_detail_pane(self):
        if hasattr(self, 'det_stack'):
            self.det_stack.setCurrentIndex(0)

    def _on_table_selection_changed(self):
        if not hasattr(self, 'tab') or not hasattr(self, 'det_stack'):
            return
        r = self.tab.currentRow()
        if r < 0:
            # İlk satır varsa otomatik seç
            if self.tab.rowCount() > 0:
                self.tab.selectRow(0)
                r = 0
            else:
                self._clear_detail_pane()
                return

        it_ad = self.tab.item(r, self.COL_AD)
        it_bitis = self.tab.item(r, self.COL_BITIS)
        it_kalan = self.tab.item(r, self.COL_KALAN)
        it_durum = self.tab.item(r, self.COL_DURUM)
        it_kume = self.tab.item(r, self.COL_KUME)

        if not it_ad or not it_kume:
            self._clear_detail_pane()
            return

        adsoyad = it_ad.text()
        bitis = it_bitis.text() if it_bitis else "Tarih belirtilmedi"
        kalan = it_kalan.text() if it_kalan else ""
        durum = it_durum.text() if it_durum else ""
        kume_text = it_kume.text() if it_kume else ""

        oid = self._ogr_id_from_row(r)
        kume_id = None
        try:
            kume_id = int(''.join(c for c in kume_text if c.isdigit()))
        except Exception:
            pass

        self._update_detail_pane(oid, kume_id, adsoyad, bitis, kalan, durum)

    def _update_detail_pane(self, oid, kume_id, adsoyad, bitis, kalan, durum):
        if not hasattr(self, 'det_stack') or not oid or not kume_id:
            self._clear_detail_pane()
            return

        con = db.get_conn()
        try:
            r_ogr = con.execute("""
                SELECT ad, soyad, ana_grup, alt_grup, veli_ad, veli_tel1, veli_tel2, ogr_tel
                FROM ogrenci WHERE id=?
            """, (oid,)).fetchone()

            r_hw = con.execute("""
                SELECT id, ders, kitap_ad, konu_ad, durum
                FROM odev
                WHERE kume_id=? AND silindi=0
                ORDER BY id ASC
            """, (kume_id,)).fetchall()
        finally:
            con.close()

        grup = ""
        tel = ""
        if r_ogr:
            grup = f"{r_ogr['ana_grup'] or ''} {r_ogr['alt_grup'] or ''}".strip()
            tel = (r_ogr["veli_tel1"] or r_ogr["veli_tel2"] or r_ogr["ogr_tel"] or "").strip()

        self.lbl_det_name.setText(adsoyad)
        meta_str = f"🏷️ {grup or 'Grup belirtilmedi'}"
        if tel:
            meta_str += f" • 📞 {tel}"
        self.lbl_det_meta.setText(meta_str)

        self.lbl_det_kume_badge.setText(f"📦 Küme #{kume_id} • Bitiş: {bitis}")
        clean_kalan = kalan.replace("✓", "").replace("✅", "").strip()
        self.lbl_det_status_badge.setText(f"{durum} ({clean_kalan})")

        self.tbl_det_homeworks.setRowCount(len(r_hw))
        from PyQt6.QtGui import QFont, QColor
        from PyQt6.QtCore import Qt
        for idx, hw in enumerate(r_hw):
            ders = hw["ders"] or ""
            kitap = hw["kitap_ad"] or ""
            konu = hw["konu_ad"] or "-"
            h_durum = (hw["durum"] or "Bekliyor").strip()

            it_d = QTableWidgetItem(f"{ders} • {kitap}" if kitap else ders)
            it_d.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tbl_det_homeworks.setItem(idx, 0, it_d)

            it_k = QTableWidgetItem(konu)
            self.tbl_det_homeworks.setItem(idx, 1, it_k)

            it_s = QTableWidgetItem(h_durum)
            it_s.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_s.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            if h_durum.lower() in ("yapildi", "tamam"):
                it_s.setBackground(QColor("#f0fdf4"))
                it_s.setForeground(QColor("#15803d"))
            else:
                it_s.setBackground(QColor("#fef3c7"))
                it_s.setForeground(QColor("#92400e"))
            self.tbl_det_homeworks.setItem(idx, 2, it_s)

        self.lbl_hw_sub.setText(f"📚 <b>Kümedeki Ödevler & Kitaplar ({len(r_hw)} Görev):</b>")
        self.det_stack.setCurrentIndex(1)

    def _open_tracking_for_selected(self):
        r = self.tab.currentRow()
        if r < 0: return
        oid = self._ogr_id_from_row(r)
        if oid:
            self._open_tracking_for_student(int(oid))

    def _open_analysis_for_selected(self):
        r = self.tab.currentRow()
        if r < 0: return
        self._open_analysis_dialog([r])

    def _send_whatsapp_for_selected(self):
        r = self.tab.currentRow()
        if r < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce tablodan bir randevu seçin.")
            return
        oid = self._ogr_id_from_row(r)
        if not oid: return

        # Seçili satırdan öğrenci ve randevu bilgilerini topla
        it_ogr = self.tab.item(r, self.COL_AD)
        adsoyad = it_ogr.text().strip() if it_ogr else f"Öğrenci #{oid}"
        it_kume = self.tab.item(r, self.COL_KUME)
        try:
            kume_id = int(''.join(c for c in it_kume.text() if c.isdigit())) if it_kume else 0
        except Exception:
            kume_id = 0

        it_bitis = self.tab.item(r, self.COL_BITIS)
        bitis = it_bitis.text().strip() if it_bitis else ""
        it_kalan = self.tab.item(r, self.COL_KALAN)
        kalan = it_kalan.text().strip() if it_kalan else ""
        it_durum = self.tab.item(r, self.COL_DURUM)
        durum = it_durum.text().strip() if it_durum else ""

        con = db.get_conn()
        try:
            r_ogr = con.execute("SELECT ad, soyad, ogr_tel, veli_ad, veli_tel1, veli_tel2 FROM ogrenci WHERE id=?", (oid,)).fetchone()
            r_hw = con.execute("SELECT ders, kitap_ad, konu_ad, durum FROM odev WHERE kume_id=? AND silindi=0 ORDER BY id ASC", (kume_id,)).fetchall()
        finally:
            con.close()

        def _clean_phone(s):
            s = ''.join(ch for ch in (s or '') if ch.isdigit() or ch == '+')
            if not s: return ''
            if s.startswith('+'): return s
            if len(s) == 11 and s.startswith('0'): return '+90' + s[1:]
            if len(s) == 10: return '+90' + s
            return '+' + s

        phones = []
        if r_ogr:
            if r_ogr["ogr_tel"]:
                phones.append((f"📱 Öğrenci ({r_ogr['ad']})", _clean_phone(r_ogr["ogr_tel"])))
            if r_ogr["veli_tel1"]:
                v_lbl = f"👨‍👩‍👦 Veli-1 ({r_ogr['veli_ad'] or 'Veli'})"
                phones.append((v_lbl, _clean_phone(r_ogr["veli_tel1"])))
            if r_ogr["veli_tel2"]:
                phones.append(("📞 Veli-2", _clean_phone(r_ogr["veli_tel2"])))

        dlg = SingleStudentWhatsAppDialog(self, oid, adsoyad, kume_id, bitis, kalan, durum, r_hw, phones)
        dlg.exec()

    def _mark_selected_kume_completed(self):
        r = self.tab.currentRow()
        if r < 0: return
        it_kume = self.tab.item(r, self.COL_KUME)
        if not it_kume: return
        try:
            kume_id = int(''.join(c for c in it_kume.text() if c.isdigit()))
        except Exception:
            return

        reply = QMessageBox.question(
            self, "Tamamlandı İşaretle",
            f"Küme #{kume_id} kapsamındaki tüm ödevler 'Yapıldı' olarak işaretlensin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            con = db.get_conn()
            try:
                con.execute("UPDATE odev SET durum='Yapildi' WHERE kume_id=?", (kume_id,))
                con.commit()
                self._load_from_db()
                QMessageBox.information(self, "Güncellendi", "Ödevler başarıyla tamamlandı olarak işaretlendi! ✅")
            finally:
                con.close()


    # ---------- Durum mantığı
    def _kontrol_durumu(self, days_left, toplam, bitti, perc, bitis_str):
        """Kullanıcı kuralı:
           - Bitiş geçmiş ve bitti==0 ise: 'Kontrol Yapılmadı'
           - Bitiş geçmiş ve 0<bitti<toplam ise: 'Kısmi Kontrol'
           - %100 ise: 'Tamamlandı'
           - Aksi, önceki etikete göre ('Bugün', 'Yarın', 'Gecikmiş'/'... gün kaldı') sadeleştirilir.
        """
        if toplam > 0 and bitti >= toplam:
            return "Tamamlandı"
        try:
            d_left = int(days_left) if days_left is not None else None
        except Exception:
            d_left = None

        if d_left is not None and d_left < 0:
            if toplam > 0 and bitti == 0:
                return "Kontrol Yapılmadı"
            if toplam > 0 and 0 < bitti < toplam:
                return "Kısmi Kontrol"
            return "Gecikmiş"

        if d_left is None:
            return "Tarih yok"
        if d_left == 0:
            return "Bugün"
        if d_left == 1:
            return "Yarın"
        return f"{d_left} gün kaldı"

    # ---------- Kümeye ilişkin istatistik

    def _kume_istatistik(self, kume_id: int, bitis_str: str):
        from datetime import date, datetime
        con = db.get_conn()

        # 1) Gün farkı
        days_left = None
        try:
            if bitis_str:
                d = datetime.strptime(bitis_str, "%Y-%m-%d").date()
                days_left = (d - date.today()).days
        except Exception:
            pass

        # 2) Toplam / Bitti / Süre(dk)
        # Türkçe varyasyonları normalize etmek için 'ı/İ' → 'i' çevirip prefix eşleşmesi kullanıyoruz.
        # 'yap*' ve 'tamam*' hepsi bitmiş kabul edilsin (yapildi, yapıldı, yap., tamam, tamamlandı, vs.)
        try:
            row = con.execute("""
                SELECT
                  COUNT(*) AS toplam,
                  SUM(
                    CASE
                      WHEN durum IS NULL THEN 0
                      WHEN
                        LOWER(
                          REPLACE(REPLACE(TRIM(COALESCE(durum,'')),'İ','i'),'ı','i')
                        ) LIKE 'yap%' OR
                        LOWER(
                          REPLACE(REPLACE(TRIM(COALESCE(durum,'')),'İ','i'),'ı','i')
                        ) LIKE 'tamam%'
                      THEN 1
                      ELSE 0
                    END
                  ) AS bitti,
                  SUM(COALESCE(saat_dk,0)) AS toplam_dk
                FROM odev
                WHERE kume_id=?
            """, (int(kume_id),)).fetchone()

            toplam = int(row["toplam"] or 0)
            bitti = int(row["bitti"] or 0)
            toplam_dk = int(row["toplam_dk"] or 0)
        except Exception:
            toplam = bitti = toplam_dk = 0

        perc = int(round((bitti / toplam) * 100)) if toplam > 0 else 0

        # 3) Durum metni (tamamlandı her zaman öncelikli)
        if toplam > 0 and bitti >= toplam:
            durum = "Tamamlandı"
        else:
            if days_left is None:
                durum = "Tarih yok"
            elif days_left < 0:
                durum = "Gecikmiş"
            elif days_left == 0:
                durum = "Bugün"
            elif days_left == 1:
                durum = "Yarın"
            else:
                durum = f"{days_left} gün kaldı"

        return days_left, durum, perc, toplam, bitti, toplam_dk

    # ---------- Seçim / ID yardımcıları
    def _ogr_id_from_row(self, r: int):
        it = self.tab.item(r, self.COL_KUME)
        if not it: return None
        val = it.data(Qt.ItemDataRole.UserRole)
        if val is not None:
            try: return int(val)
            except Exception: return None
        # fallback: metinden kume_id -> ogrenci_id
        try:
            kume_id = int(''.join(ch for ch in (it.text() or "") if ch.isdigit()))
            con = db.get_conn()
            row = con.execute("SELECT ogrenci_id FROM odev_kume WHERE id=?", (kume_id,)).fetchone()
            return int(row["ogrenci_id"]) if row and row["ogrenci_id"] is not None else None
        except Exception:
            return None

    def _secili_ogr_idler(self):
        ids = set()
        for i in self.tab.selectedIndexes():
            oid = self._ogr_id_from_row(i.row())
            if oid: ids.add(oid)
        return sorted(ids)

    def _tum_ogrenci_idleri(self):
        ids = set()
        for r in range(self.tab.rowCount()):
            oid = self._ogr_id_from_row(r)
            if oid: ids.add(oid)
        return sorted(ids)

    #s
    # ---------- Alt butonlar (24 saat / Bugün) ----------

    def _btn_24_saat_tumu(self):
        """Tablodaki TÜM öğrenciler için 'yarın kontrol' WhatsApp penceresini aç."""
        btn = self.sender()
        if btn: btn.clearFocus()
        self.tab.setFocus()
        QTimer.singleShot(100, lambda: self._open_whatsapp_batch_dialog(mode="tomorrow"))

    def _btn_24_saat_secili(self):
        """Sadece SEÇİLİ satırlar için 'yarın kontrol' WhatsApp penceresini aç."""
        btn = self.sender()
        if btn: btn.clearFocus()
        self.tab.setFocus()
        
        def _action():
            oids = self._secili_ogr_idler()
            if not oids:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Seçim", "Lütfen listeden en az bir satır seçin.")
                return
            self._open_whatsapp_batch_dialog(mode="tomorrow", oids=oids)
            
        QTimer.singleShot(100, _action)

    def _btn_bugun_tumu(self):
        """TÜM öğrenciler için 'bugün kontrol' WhatsApp penceresini aç."""
        btn = self.sender()
        if btn: btn.clearFocus()
        self.tab.setFocus()
        QTimer.singleShot(100, lambda: self._open_whatsapp_batch_dialog(mode="today"))

    def _btn_bugun_secili(self):
        """Sadece SEÇİLİ satırlar için 'bugün kontrol' WhatsApp penceresini aç."""
        btn = self.sender()
        if btn: btn.clearFocus()
        self.tab.setFocus()
        
        def _action():
            oids = self._secili_ogr_idler()
            if not oids:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Seçim", "Lütfen listeden en az bir satır seçin.")
                return
            self._open_whatsapp_batch_dialog(mode="today", oids=oids)

        QTimer.singleShot(100, _action)

    #f

    # ---------- Çift tık ile aç
    def _ac(self, r: int, _c: int):
        oid = self._ogr_id_from_row(r)
        if not oid:
            QMessageBox.warning(self, "Öğrenci", "Öğrenci kimliği alınamadı.")
            return
        self._open_tracking_for_student(int(oid))

    def _open_tracking_for_student(self, ogr_id: int):
        try:
            from ui.homework_form import OdevTakipFormu
        except Exception as e:
            QMessageBox.critical(self, "Ödev Takip", f"Form içe aktarılamadı:\n{e}")
            return
        try:
            if self._hw_form is None or not self._hw_form.isVisible():
                self._hw_form = OdevTakipFormu(None, ogrenci_id=ogr_id)
            else:
                if hasattr(self._hw_form, "select_student_by_id"):
                    self._hw_form.select_student_by_id(ogr_id, autoload=True)
                else:
                    setattr(self._hw_form, "_pending_student_id", ogr_id)
            self._hw_form.show(); self._hw_form.raise_(); self._hw_form.activateWindow()
            self._hw_form.setWindowState(self._hw_form.windowState() | Qt.WindowState.WindowMaximized)
        except Exception:
            pass
        try: self.close()
        except Exception: pass

    # ---------- WhatsApp akışları (mevcut fonksiyonlarınızı kullanır)
    # (Aşağıdaki dört metod aynen sizdeki çağrıları yapar)
    def _aktif_sablon(self):
        return (appset.ayar_get('hatirlatma_wp_sablon_geciken')
                if self.cmbSablon.currentText() == 'Geciken'
                else appset.ayar_get('hatirlatma_wp_sablon')) or 'Merhaba: {ozet}'


    # --- Gönderim tetikçileri (sizdekiyle uyumlu) ---
    def _send_24saat_all(self):
        sablon = self._aktif_sablon()
        ids = self._tum_ogrenci_idleri()
        if not ids:
            QMessageBox.information(self, '24 Saat Kala', 'Gönderilecek öğrenci bulunamadı.')
            return
        mod = 'overdue' if self.chkYalnizGeciken.isChecked() or self.cmbSablon.currentText() == 'Geciken' else 'tomorrow'
        plan, plan_log, bos_msg, numarasiz = self._planla(ids, mod, sablon)
        toplam_ok = toplam_fail = 0
        for oid in ids:
            info = plan.get(oid, {})
            if not info.get("msg_ok"):
                continue
            msg = self._mesaj_olustur_ogr(oid, mod, sablon)
            if not msg: continue
            sonuc = self._whatsapp_gonder_ogr(oid, msg)
            toplam_ok += self._normalize_sent(sonuc)
            if isinstance(sonuc, dict):
                f = sonuc.get("fail", [])
                toplam_fail += (len(f) if isinstance(f, (list, tuple, set)) else int(bool(f)))
        try:
            detay = self._format_sonuc("24 Saat Kala", toplam_ok, toplam_fail, plan, bos_msg, numarasiz, mod)
        except Exception:
            detay = f"Gönderildi: {toplam_ok} | Başarısız: {toplam_fail}"
        QMessageBox.information(self, '24 Saat Kala', detay)
        if toplam_ok == 0 and all(not v.get("msg_ok") for v in plan.values()):
            self._whatsapp_quick_check("WhatsApp Hızlı Kontrol")

    def _send_24saat_selected(self):
        sablon = self._aktif_sablon()
        ids = self._secili_ogr_idler()
        if not ids:
            QMessageBox.warning(self, '24 Saat', 'Seçili öğrenci yok.')
            return
        mod = 'overdue' if self.chkYalnizGeciken.isChecked() or self.cmbSablon.currentText() == 'Geciken' else 'tomorrow'
        plan, plan_log, bos_msg, numarasiz = self._planla(ids, mod, sablon)
        toplam_ok = toplam_fail = 0
        for oid in ids:
            info = plan.get(oid, {})
            if not info.get("msg_ok"): continue
            msg = self._mesaj_olustur_ogr(oid, mod, sablon)
            if not msg: continue
            sonuc = self._whatsapp_gonder_ogr(oid, msg)
            toplam_ok += self._normalize_sent(sonuc)
            if isinstance(sonuc, dict):
                f = sonuc.get('fail', [])
                toplam_fail += (len(f) if isinstance(f, (list, tuple, set)) else int(bool(f)))
        try:
            detay = self._format_sonuc("24 Saat (Seçili)", toplam_ok, toplam_fail, plan, bos_msg, numarasiz, mod)
        except Exception:
            detay = f"Gönderildi: {toplam_ok} | Başarısız: {toplam_fail}"
        QMessageBox.information(self, '24 Saat (Seçili)', detay)
        if toplam_ok == 0 and all(not v.get("msg_ok") for v in plan.values()):
            self._whatsapp_quick_check("WhatsApp Hızlı Kontrol")

    def _send_today_all(self):
        sablon = appset.ayar_get('hatirlatma_wp_sablon_bugun') or self._aktif_sablon()
        ids = [oid for oid in self._tum_ogrenci_idleri() if self._kume_idleri_due(oid, 'today')]
        if not ids:
            QMessageBox.information(self, 'Bugün Hatırlat', 'Bugün bitişi olan öğrenci bulunamadı.')
            return
        mod = 'today'
        plan, plan_log, bos_msg, numarasiz = self._planla(ids, mod, sablon)
        toplam_ok = toplam_fail = 0
        for oid in ids:
            info = plan.get(oid, {})
            if not info.get("msg_ok"): continue
            msg = self._mesaj_olustur_ogr(oid, mod, sablon)
            if not msg: continue
            sonuc = self._whatsapp_gonder_ogr(oid, msg)
            toplam_ok += self._normalize_sent(sonuc)
            if isinstance(sonuc, dict):
                toplam_fail += len(sonuc.get('fail', [])) if isinstance(sonuc.get('fail', []), list) else 0
        try:
            detay = self._format_sonuc("Bugün Hatırlat (Tümü)", toplam_ok, toplam_fail, plan, bos_msg, numarasiz, mod)
        except Exception:
            detay = f"Gönderildi: {toplam_ok} | Başarısız: {toplam_fail}"
        QMessageBox.information(self, 'Bugün Hatırlat (Tümü)', detay)
        if toplam_ok == 0 and all(not v.get("msg_ok") for v in plan.values()):
            self._whatsapp_quick_check("WhatsApp Hızlı Kontrol")

    def _send_today_selected(self):
        sablon = appset.ayar_get('hatirlatma_wp_sablon_bugun') or self._aktif_sablon()
        ids = self._secili_ogr_idler()
        if not ids:
            QMessageBox.warning(self, 'Bugün Hatırlat (Seçili)', 'Seçili öğrenci yok.')
            return
        mod = 'today'
        plan, plan_log, bos_msg, numarasiz = self._planla(ids, mod, sablon)
        toplam_ok = toplam_fail = 0
        for oid in ids:
            info = plan.get(oid, {})
            if not info.get("msg_ok"): continue
            msg = self._mesaj_olustur_ogr(oid, mod, sablon)
            if not msg: continue
            sonuc = self._whatsapp_gonder_ogr(oid, msg)
            toplam_ok += self._normalize_sent(sonuc)
            if isinstance(sonuc, dict):
                toplam_fail += len(sonuc.get('fail', [])) if isinstance(sonuc.get('fail', []), list) else 0
        try:
            detay = self._format_sonuc("Bugün Hatırlat (Seçili)", toplam_ok, toplam_fail, plan, bos_msg, numarasiz, mod)
        except Exception:
            detay = f"Gönderildi: {toplam_ok} | Başarısız: {toplam_fail}"
        QMessageBox.information(self, 'Bugün Hatırlat (Seçili)', detay)
        if toplam_ok == 0 and all(not v.get("msg_ok") for v in plan.values()):
            self._whatsapp_quick_check("WhatsApp Hızlı Kontrol")

    # ---------- Analiz popup’ları ----------
    def _show_ogrenci_ozet(self, oid: int):
        """Öğrenci odaklı modern istatistik dashboard."""
        
        # --- Verileri Çek ---
        con = db.get_conn()
        r = con.execute("SELECT ad, soyad, ogr_no FROM ogrenci WHERE id=?", (oid,)).fetchone()
        ad = f"{r['ad']} {r['soyad']}".strip() if r else f"Öğrenci#{oid}"
        ogr_no = r['ogr_no'] if r and r['ogr_no'] else "---"

        # İstatistikler (Toplam Küme ve Tamamlanan Küme)
        row = con.execute("""
            SELECT COUNT(*) AS ks,
                   SUM(CASE WHEN x.bitti = x.toplam AND x.toplam>0 THEN 1 ELSE 0 END) AS full_done
            FROM (
               SELECT k.id,
                      (SELECT COUNT(*) FROM odev WHERE kume_id=k.id) AS toplam,
                      (SELECT COUNT(*) FROM odev WHERE kume_id=k.id AND LOWER(COALESCE(durum,'')) IN ('yapildi','tamam','evet','1')) AS bitti
               FROM odev_kume k WHERE k.ogrenci_id=?
            ) x
        """, (oid,)).fetchone()
        
        ks = int(row["ks"] or 0)        # Toplam Küme
        fd = int(row["full_done"] or 0) # Tamamlanan
        ratio = int((fd / ks * 100)) if ks > 0 else 0

        # --- UI Oluştur ---
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont, QColor

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Öğrenci Özeti — {ad}")
        dlg.setFixedSize(500, 320)
        dlg.setStyleSheet("background-color: #f8fafc;")

        # Ana Layout
        main_lay = QVBoxLayout(dlg)
        main_lay.setContentsMargins(25, 25, 25, 25)
        main_lay.setSpacing(20)

        # 1. Başlık ve İkon
        title_lay = QHBoxLayout()
        icon_lbl = QLabel("👤")
        icon_lbl.setStyleSheet("font-size: 32px;")
        
        txt_lay = QVBoxLayout()
        txt_lay.setSpacing(2)
        lbl_ad = QLabel(ad)
        lbl_ad.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        lbl_no = QLabel(f"Öğrenci No: {ogr_no}")
        lbl_no.setStyleSheet("font-size: 13px; color: #64748b;")
        txt_lay.addWidget(lbl_ad)
        txt_lay.addWidget(lbl_no)
        
        title_lay.addWidget(icon_lbl)
        title_lay.addLayout(txt_lay)
        title_lay.addStretch(1)
        main_lay.addLayout(title_lay)

        # 2. İstatistik Kartları (Grid-like)
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        stats_lay = QHBoxLayout(stats_frame)
        stats_lay.setContentsMargins(20, 20, 20, 20)
        stats_lay.setSpacing(10)

        def _mk_stat(title, val, color="#0f172a"):
            v = QVBoxLayout()
            l1 = QLabel(title)
            l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l1.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 600; text-transform: uppercase;")
            
            l2 = QLabel(str(val))
            l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l2.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 800;")
            
            v.addWidget(l1)
            v.addWidget(l2)
            return v
        
        # Ayırıcı Çizgi
        def _sep():
            f = QFrame()
            f.setFrameShape(QFrame.Shape.VLine)
            f.setStyleSheet("color: #e2e8f0;")
            f.setFixedWidth(1)
            return f

        stats_lay.addLayout(_mk_stat("Toplam Ödev K.", ks))
        stats_lay.addWidget(_sep())
        stats_lay.addLayout(_mk_stat("Tamamlanan", fd, "#10b981")) # Yeşil
        stats_lay.addWidget(_sep())
        stats_lay.addLayout(_mk_stat("Başarı Oranı", f"%{ratio}", "#3b82f6")) # Mavi

        main_lay.addWidget(stats_frame)
        
        # 3. Kapat Butonu
        btn_close = QPushButton("Kapat")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        btn_close.clicked.connect(dlg.accept)
        
        main_lay.addStretch(1)
        main_lay.addWidget(btn_close)

        dlg.exec()

    def _show_kitap_ilerleme(self, oid: int):
        """
        % ilerleme = (öğrencinin 'yapıldı' işaretlediği BENZERSİZ konu_ad adedi)
                     / (o DERSE ait TOPLAM konu sayısı)  — kitap bazında.
        Not: toplam konu sayısı ders tablosundaki satır sayısıdır (tyt_matematik, geometri, ...).
        """
        import sqlite3
        con = db.get_conn()
        cur = con.cursor()

        # (ders, kitap) çiftlerini hem odev’den hem ogrenci_kitap’tan topla
        pairs = set()
        for r in cur.execute("""
            SELECT DISTINCT ders, COALESCE(kitap_ad,'') AS kitap
            FROM odev
            WHERE ogrenci_id=? AND COALESCE(kitap_ad,'')<>''
        """, (oid,)):
            pairs.add((r["ders"], r["kitap"]))

        for r in cur.execute("""
            SELECT DISTINCT ders, COALESCE(kitap_ad,'') AS kitap
            FROM ogrenci_kitap
            WHERE ogrenci_id=? AND COALESCE(kitap_ad,'')<>''
        """, (oid,)):
            pairs.add((r["ders"], r["kitap"]))

        if not pairs:
            QMessageBox.information(self, "Kitap İlerlemesi", "Kayıt bulunamadı.")
            return

        def _is_done(val: str | None) -> bool:
            s = (val or "").strip().lower()
            # sistemde kullandığın başlıca “tamam” varyantları
            return s in {"yapildi", "tamam", "bitti", "done", "tamamlandı", "✓", "1", "true", "evet", "ok"}

        lines: list[str] = []

        for ders, kitap in sorted(pairs):
            # 1) TOPLAM konu sayısı: ilgili ders tablosundaki satır sayısı
            try:
                total = cur.execute(f"SELECT COUNT(*) AS c FROM {ders}").fetchone()["c"] or 0
            except sqlite3.Error:
                total = 0  # ders adı tabloyla birebir değilse güvenli çık

            # 2) DONE: bu (ders, kitap) için 'yapıldı' işaretlenmiş BENZERSİZ konu_ad sayısı
            done_set = set()
            for r in cur.execute("""
                SELECT DISTINCT konu_ad, durum
                FROM odev
                WHERE ogrenci_id=? AND ders=? AND kitap_ad=?
            """, (oid, ders, kitap)):
                if _is_done(r["durum"]):
                    k = (r["konu_ad"] or "").strip()
                    if k:
                        done_set.add(k)
            done = len(done_set)

            # 3) % hesapla
            perc = int(round((done / total) * 100)) if total else 0
            lines.append(f"• {ders} / {kitap}: %{perc}  ({done}/{total})")

        QMessageBox.information(self, "Kitap İlerlemesi", "\n".join(lines))


    def _show_kitap_ilerleme_table(self, oid: int):
        """
        Ders ve kitap bazlı ilerlemeyi modern ve profesyonel bir arayüzde gösterir.
        Analiz kısmı için tablo ve barlar içerir.
        """
        from PyQt6.QtCore import Qt, QSize
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
            QHeaderView, QProgressBar, QMessageBox, QPushButton, QLabel, QFrame, QWidget
        )
        from PyQt6.QtGui import QFont, QColor

        # Verileri çek
        rows = self._calc_kitap_progress_rows(oid)
        if not rows:
            QMessageBox.information(self, "Kitap İlerlemesi", "Bu öğrenci için kayıt bulunamadı.")
            return

        # Öğrenci Bilgisi
        con = db.get_conn()
        r = con.execute("SELECT ad, soyad, COALESCE(ogr_no,'') AS ogr_no FROM ogrenci WHERE id=?", (oid,)).fetchone()
        ad = f"{r['ad']} {r['soyad']}".strip() if r else f"Öğrenci#{oid}"
        ogr_no = (r["ogr_no"] or "").strip()

        # İstatistikler
        total_tasks = sum(x[4] for x in rows)  # Toplam
        total_done = sum(x[3] for x in rows)   # Tamam
        total_books = len(rows)
        global_perc = int((total_done / total_tasks * 100)) if total_tasks > 0 else 0

        # --- Dialog Kurulumu ---
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Kitap Analizi — {ad}")
        dlg.resize(1000, 600)
        dlg.setStyleSheet("background-color: #f8fafc;")

        main_lay = QVBoxLayout(dlg)
        main_lay.setContentsMargins(20, 20, 20, 20)
        main_lay.setSpacing(20)

        # --- 1. Üst Bilgi Kartı (Dashboard) ---
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        info_lay = QHBoxLayout(info_frame)
        info_lay.setContentsMargins(20, 15, 20, 15)
        info_lay.setSpacing(30)

        # Kart Yardımcısı
        def _stat_item(lbl_text, val_text, color="#1e293b"):
            vbox = QVBoxLayout()
            vbox.setSpacing(2)
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet("color: #64748b; font-size: 13px; font-weight: 500;")
            val = QLabel(val_text)
            val.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 700;")
            vbox.addWidget(lbl)
            vbox.addWidget(val)
            return vbox

        info_lay.addLayout(_stat_item("Öğrenci", ad))
        info_lay.addLayout(_stat_item("Toplam Kitap", str(total_books)))
        info_lay.addLayout(_stat_item("Tamamlanan Konu", f"{total_done} / {total_tasks}", "#059669"))
        
        # Genel Yüzde Yuvarlak/Büyük
        perc_lay = QVBoxLayout()
        perl_lbl = QLabel("Genel Durum")
        perl_lbl.setStyleSheet("color: #64748b; font-size: 13px;")
        perc_val = QLabel(f"%{global_perc}")
        perc_val.setStyleSheet("color: #2563eb; font-size: 24px; font-weight: 800;")
        perc_lay.addWidget(perl_lbl, 0, Qt.AlignmentFlag.AlignRight)
        perc_lay.addWidget(perc_val, 0, Qt.AlignmentFlag.AlignRight)
        
        info_lay.addStretch(1)
        info_lay.addLayout(perc_lay)

        main_lay.addWidget(info_frame)

        # --- 2. Tablo ---
        tbl = QTableWidget(len(rows), 5)
        tbl.setHorizontalHeaderLabels(["Ders", "Kitap", "İlerleme Durumu", "Tamam", "Toplam"])
        tbl.setShowGrid(False)
        tbl.setAlternatingRowColors(True)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        # Tablo stil
        tbl.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                gridline-color: #f1f5f9;
                font-size: 14px;
            }
            QTableWidget::item {
                padding-left: 10px;
                color: #334155;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #475569;
                padding: 10px;
                border: none;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #e0f2fe;
                color: #0369a1;
            }
        """)

        # Kolon ayarları
        header = tbl.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Ders
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Kitap
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)            # Progress
        tbl.setColumnWidth(2, 200) # Progress bar genişliği
        
        # Veri Doldurma
        for i, (ders, kitap, perc, done, total) in enumerate(rows):
            # Ders
            it0 = QTableWidgetItem(ders)
            it0.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            tbl.setItem(i, 0, it0)
            
            # Kitap
            tbl.setItem(i, 1, QTableWidgetItem(kitap))

            # Progress Bar (Custom Widget)
            p_container = QWidget()
            p_layout = QVBoxLayout(p_container)
            p_layout.setContentsMargins(5, 5, 5, 5)
            p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            pb = QProgressBar()
            pb.setRange(0, 100)
            pb.setValue(int(perc))
            pb.setFixedHeight(14)
            pb.setTextVisible(False)
            
            # Renkli Progress
            if perc >= 100:
                chunk_color = "#10b981" # Yeşil
            elif perc > 50:
                chunk_color = "#3b82f6" # Mavi
            else:
                chunk_color = "#f59e0b" # Turuncu
                
            pb.setStyleSheet(f"""
                QProgressBar {{
                    border: none;
                    background-color: #e2e8f0;
                    border-radius: 7px;
                }}
                QProgressBar::chunk {{
                    background-color: {chunk_color};
                    border-radius: 7px;
                }}
            """)
            
            # Yüzde yazısı
            lbl_perc = QLabel(f"%{int(perc)}")
            lbl_perc.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold;")
            
            sub_lay = QHBoxLayout()
            sub_lay.setSpacing(8)
            sub_lay.setContentsMargins(0,0,0,0)
            sub_lay.addWidget(pb)
            sub_lay.addWidget(lbl_perc)
            
            p_layout.addLayout(sub_lay)
            tbl.setCellWidget(i, 2, p_container)

            # Tamam / Toplam
            it3 = QTableWidgetItem(str(done))
            it3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tbl.setItem(i, 3, it3)

            it4 = QTableWidgetItem(str(total))
            it4.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tbl.setItem(i, 4, it4)

        main_lay.addWidget(tbl)

        # --- 3. Alt Butonlar ---
        btn_lay = QHBoxLayout()
        btn_lay.addStretch(1)

        def _mk_btn(txt, icon_emoji, bg):
            b = QPushButton(f"{icon_emoji}  {txt}")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 13px;
                }}
                QPushButton:hover {{ opacity: 0.9; }}
            """)
            return b

        btn_excel = _mk_btn("Excel'e Aktar", "📊", "#10b981") # Yeşil
        btn_pdf = _mk_btn("PDF Olarak Yazdır", "📄", "#ef4444")   # Kırmızı

        btn_excel.clicked.connect(lambda: self._export_kitap_ilerleme_excel(oid, rows)) # rows (5li tuple)
        btn_pdf.clicked.connect(lambda: self._export_kitap_ilerleme_pdf(oid, rows))

        btn_lay.addWidget(btn_excel)
        btn_lay.addWidget(btn_pdf)

        main_lay.addLayout(btn_lay)

        dlg.exec()

    def _calc_kitap_progress_rows(self, oid: int):
        """
        Her (ders, kitap) için:
          total = ilgili 'ders' tablosundaki toplam konu adedi
          done  = öğrencinin o kitapta 'yapıldı' işaretlediği BENZERSİZ konu_ad sayısı
          perc  = round(done / total * 100)
        Dönüş: [ (ders, kitap, perc, done, total) ... ]  sıralı
        """
        import sqlite3
        con = db.get_conn()
        cur = con.cursor()

        # Bu öğrencinin (ders, kitap) çiftleri
        pairs = cur.execute("""
            SELECT DISTINCT o.ders, o.kitap_ad
            FROM odev o
            JOIN odev_kume k ON k.id = o.kume_id
            WHERE k.ogrenci_id=? AND COALESCE(o.kitap_ad,'')<>''
        """, (oid,)).fetchall()
        if not pairs:
            return []

        # Payda için her ders tablosundaki toplam konu sayısını toplu al
        dersler = [r["ders"] for r in pairs]
        total_by_ders: dict[str, int] = {}
        for ders in sorted(set(dersler)):
            try:
                # Konu alanı boş olanları sayma
                total = cur.execute(
                    f"SELECT COUNT(*) AS c FROM {ders} WHERE TRIM(COALESCE(konu,''))<>''"
                ).fetchone()["c"] or 0
            except sqlite3.Error:
                total = 0
            # Güvenlik: tabloda bulunamazsa en azından ödevde görünen farklı konular kadar olsun
            if total == 0:
                total = cur.execute("""
                    SELECT COUNT(DISTINCT konu_ad) AS c
                    FROM odev o JOIN odev_kume k ON k.id=o.kume_id
                    WHERE k.ogrenci_id=? AND o.ders=?
                """, (oid, ders)).fetchone()["c"] or 0
            total_by_ders[ders] = int(total)

        # ‘Tamam’ varyantları
        def _is_done(s: str | None) -> bool:
            s = (s or "").strip().lower()
            return s in {"yapildi", "tamam", "tamamlandı", "bitti", "done", "✓", "1", "true", "evet", "ok"}

        rows = []
        for r in pairs:
            ders, kitap = r["ders"], r["kitap_ad"]
            total = total_by_ders.get(ders, 0)

            # Bu kitapta bitirilen BENZERSİZ konular
            done = cur.execute("""
                SELECT COUNT(*) AS c FROM (
                  SELECT DISTINCT o.konu_ad
                  FROM odev o JOIN odev_kume k ON k.id=o.kume_id
                  WHERE k.ogrenci_id=? AND o.ders=? AND o.kitap_ad=? 
                        AND TRIM(COALESCE(o.konu_ad,''))<>'' 
                        AND LOWER(COALESCE(o.durum,'')) IN ('yapildi','tamam','tamamlandı','bitti','done','✓','1','true','evet','ok')
                )
            """, (oid, ders, kitap)).fetchone()["c"] or 0

            perc = int(round((done / total) * 100)) if total else 0
            rows.append((ders, kitap, perc, int(done), int(total)))

        # Görseldeki sıralamaya benzer olsun
        rows.sort(key=lambda x: (x[0], x[1]))
        return rows

    def _sanitize_filename(self, s: str) -> str:
        import re
        s = (s or "").strip()
        s = re.sub(r"[^\w\-\. ]+", "_", s, flags=re.UNICODE)
        s = re.sub(r"\s+", "_", s)
        return s[:80] if len(s) > 80 else s


    def _export_kitap_ilerleme_excel(self, oid: int, ad: str, ogr_no: str,
                                     rows: list[tuple], overall_done: int, overall_total: int):
        """
        rows: [(ders, kitap, perc, done, total), ...]
        Excel'e dışa aktarır. Özet sayfası ekler.
        """
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import datetime

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        base = f"kitap_ilerleme_{oid}_{self._sanitize_filename(ad)}_{ts}"
        suggested = base + ".xlsx"

        path, _ = QFileDialog.getSaveFileName(self, "Excel’e Kaydet", suggested,
                                              "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return

        # Özet bilgiler
        overall_total = int(overall_total or 0)
        overall_done = int(overall_done or 0)
        overall_perc = round((overall_done / overall_total) * 100) if overall_total else 0

        try:
            # Önce .xlsx dene (pandas + openpyxl/xlsxwriter), olmazsa CSV'ye düş
            import pandas as pd  # type: ignore

            df = pd.DataFrame(
                [(d, k, int(p), int(done), int(t)) for (d, k, p, done, t) in rows],
                columns=["Ders", "Kitap", "İlerleme %", "Tamam", "Toplam"]
            )

            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                # Ana tablo
                df.to_excel(writer, index=False, sheet_name="Kitap İlerlemesi")

                # Özet sayfası
                import pandas as pd
                meta = {
                    "OgrenciID": [oid],
                    "OgrenciAdSoyad": [ad],
                    "OgrenciNo": [ogr_no],
                    "ToplamTamam": [overall_done],
                    "ToplamKonu": [overall_total],
                    "GenelYuzde": [overall_perc],
                    "OlusturmaZamani": [ts],
                }
                pd.DataFrame(meta).to_excel(writer, index=False, sheet_name="Özet")

            QMessageBox.information(self, "Excel", f"Kaydedildi:\n{path}")
        except Exception:
            # CSV’ye düş
            import csv
            if not path.lower().endswith(".csv"):
                path = path.rsplit(".", 1)[0] + ".csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["# Öğrenci ID", oid])
                w.writerow(["# Ad Soyad", ad])
                w.writerow(["# Öğrenci No", ogr_no])
                w.writerow(["# Toplam Tamam", overall_done])
                w.writerow(["# Toplam Konu", overall_total])
                w.writerow(["# Genel Yüzde", overall_perc])
                w.writerow([])
                w.writerow(["Ders", "Kitap", "İlerleme %", "Tamam", "Toplam"])
                for d, k, p, done, t in rows:
                    w.writerow([d, k, int(p), int(done), int(t)])
            QMessageBox.information(self, "CSV", f"Excel kütüphanesi bulunamadı, CSV olarak kaydedildi:\n{path}")

    def _export_kitap_ilerleme_pdf(self, oid: int, ad: str, ogr_no: str,
                                   table_widget, rows: list[tuple],
                                   overall_done: int, overall_total: int):
        """
        PDF’e yazdırır. Varsayılan olarak tablo görünümünü olduğu gibi PDF’e basar.
        Üst bilgi olarak ID/Ad/Sayımlar eklenir.
        """
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from PyQt6.QtGui import QPainter, QPageLayout, QPageSize
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtCore import QRectF, QSizeF, Qt
        import datetime

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        base = f"kitap_ilerleme_{oid}_{self._sanitize_filename(ad)}_{ts}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "PDF’e Yazdır", base, "PDF (*.pdf)")
        if not path:
            return

        overall_total = int(overall_total or 0)
        overall_done = int(overall_done or 0)
        overall_perc = round((overall_done / overall_total) * 100) if overall_total else 0

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        painter = QPainter(printer)

        # Üst başlık kutusu
        margin = 20  # px
        rect = printer.pageRect(QPrinter.Unit.Point)
        header_rect = QRectF(rect.left() + margin, rect.top() + margin,
                             rect.width() - 2 * margin, 80)

        painter.setFont(painter.font())
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                         f"Kitap İlerlemesi Raporu\n"
                         f"Öğrenci ID: {oid}   Ad Soyad: {ad}   Öğrenci No: {ogr_no}\n"
                         f"Toplam: {overall_done}/{overall_total}  (Genel: %{overall_perc})")

        # Tabloyu başlığın altına sığacak şekilde ölçekle
        painter.save()
        available = QRectF(header_rect.left(),
                           header_rect.bottom() + 10,
                           header_rect.width(),
                           rect.height() - header_rect.height() - 2 * margin)

        # Table widget'ı bir resim gibi çiz
        # (yüksek tablo tek sayfaya sığmazsa Qt otomatik küçültür)
        table_widget.render(painter, targetOffset=available.topLeft().toPoint())
        painter.restore()

        painter.end()
        QMessageBox.information(self, "PDF", f"Kaydedildi:\n{path}")

    # randevu_takvimi.py
    import os, datetime
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    from PyQt6.QtCore import Qt
    try:
        import pandas as pd
    except Exception:
        pd = None

    def _export_kitap_ilerleme_pdf(self, oid: int, rows: list[tuple]):
        # rows: (ders, kitap, perc, done, total)
        con = db.get_conn()
        r = con.execute("SELECT id, ad, soyad FROM ogrenci WHERE id=?", (oid,)).fetchone()
        oid_txt = str(oid)
        adsoyad = (f"{r['ad']} {r['soyad']}".strip() if r else f"Öğrenci#{oid_txt}")

        headers = ["Ders", "Kitap", "İlerleme %", "Tamam", "Toplam"]
        body = []
        for ders, kitap, perc, done, total in rows:
            body.append([ders, kitap, f"%{perc}", str(done), str(total)])

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        title = f"Kitap İlerlemesi — {adsoyad}"
        subtitle = f"Öğrenci ID: {oid_txt} · Tarih: {now}"

        html_str = build_html_table(title, subtitle, headers, body)
        default_name = f"{oid_txt} - {adsoyad} - Kitap İlerlemesi.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "PDF'e yazdır", default_name, "PDF (*.pdf)")
        if not path:
            return
        save_html_as_pdf(html_str, path, landscape=False)
        QMessageBox.information(self, "PDF", f"Kaydedildi:\n{path}")

    def _export_kitap_ilerleme_excel(self, oid: int, rows: list[tuple]):
        import os, datetime as dt
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        try:
            import pandas as pd
        except Exception:
            QMessageBox.warning(self, "Excel", "pandas kurulu değil. `pip install pandas openpyxl`")
            return

        con = db.get_conn()
        who = con.execute("SELECT id, ad, soyad FROM ogrenci WHERE id=?", (oid,)).fetchone()
        sid = who["id"]
        sname = f"{(who['ad'] or '').strip()} {(who['soyad'] or '').strip()}".strip() or f"Ogrenci#{sid}"

        # rows: (ders, kitap, perc, done, total)
        df = pd.DataFrame(rows, columns=["Ders", "Kitap", "İlerleme %", "Tamam", "Toplam"])
        total_toplam = int(df["Toplam"].sum()) if not df.empty else 0
        total_done = int(df["Tamam"].sum()) if not df.empty else 0
        genel_yuzde = int(round((total_done / total_toplam) * 100)) if total_toplam else 0

        df_summary = pd.DataFrame([{
            "Öğrenci ID": sid,
            "Öğrenci": sname,
            "Toplam Kitap": len(df),
            "Genel Tamam": total_done,
            "Genel Toplam": total_toplam,
            "Genel %": genel_yuzde,
            "Tarih": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }])

        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        default_name = f"{sid:04d}_{sname.replace(' ', '_')}_KitapIlerlemesi_{stamp}.xlsx"

        # 🔹 Kullanıcıya kayıt yeri soralım
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Excel Olarak Kaydet",
            os.path.expanduser(f"~/Desktop/{default_name}"),
            "Excel Dosyası (*.xlsx)"
        )
        if not save_path:
            return  # Kullanıcı iptal ettiyse çık

        # Yaz
        try:
            with pd.ExcelWriter(save_path, engine="openpyxl") as ex:
                df_summary.to_excel(ex, sheet_name="Özet", index=False)
                df.to_excel(ex, sheet_name="Detay", index=False)
        except Exception:
            with pd.ExcelWriter(save_path, engine="xlsxwriter") as ex:
                df_summary.to_excel(ex, sheet_name="Özet", index=False)
                df.to_excel(ex, sheet_name="Detay", index=False)

        QMessageBox.information(self, "Excel", f"Kaydedildi:\n{save_path}")

    # ---------- Dışa aktarım (örnek)
    def _export_excel(self):
        try:
            path, kind = self._save_xlsx_or_csv("randevu_takvimi.xlsx")
            QMessageBox.information(self, "Dışa Aktarım",
                                    f"Kaydedildi ({kind.upper()}):\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Dışa Aktarım", f"Hata: {e}")

    def _export_pdf(self):
        try:
            path = self._save_pdf("randevu_takvimi.pdf")
            QMessageBox.information(self, "PDF", f"Kaydedildi:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "PDF", f"PDF oluşturulamadı:\n{e}")

    def _whatsapp_smoke_test(self):
        """F9: Hızlı WhatsApp gönderim testi (mevcutsa utils.whatsapp’ı dener)."""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox

        try:
            num, ok = QInputDialog.getText(self, "WhatsApp Test", "Telefon (+90xxxxxxxxxx):")
            if not ok or not num:
                return
            msg, ok2 = QInputDialog.getMultiLineText(self, "WhatsApp Test", "Mesaj:", "Test mesajı")
            if not ok2:
                return

            try:
                from utils import whatsapp
            except Exception:
                QMessageBox.warning(self, "WhatsApp Test", "utils.whatsapp bulunamadı.")
                return

            try:
                r = whatsapp.whatsapp_gonder([num], msg, ogrenci_id=None)
            except Exception as e:
                QMessageBox.critical(self, "WhatsApp Test", f"Gönderim hatası:\n{e}")
                return

            # basit özet
            ok_say = 1 if (r is True or r == 1) else 0
            if isinstance(r, dict):
                ok_say = len(r.get("ok", [])) if isinstance(r.get("ok"), (list, tuple)) else int(r.get("gonderilen", 0))

            QMessageBox.information(self, "WhatsApp Test", f"Gönderildi: {ok_say}\nHam dönüş: {repr(r)}")

        except Exception as e:
            QMessageBox.critical(self, "WhatsApp Test", str(e))
    #S
    # --- Basit toast (yoksa) ---
    def _toast(self, msg: str):
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, self.windowTitle() or "Bilgi", msg)
        except Exception:
            print("[INFO]", msg)

    # --- Seçili satırlardan 'hiç görüşmeye gelmeyen' ve 'kısmi yapan' ayrımı ---
    def _split_never_vs_partial(self, rows):
        """
        rows: tablo satır indeksleri listesi
        Döner: (never_ids, partial_ids) -> ogrenci_id listeleri
        never: toplam>0 ve bitti==0
        partial: 0<bitti<toplam
        """
        con = db.get_conn()
        never, partial = set(), set()
        for r in rows:
            it_kume = self.tab.item(r, self.COL_KUME)
            if not it_kume:
                continue
            try:
                kume_id = int("".join(ch for ch in (it_kume.text() or "") if ch.isdigit()))
            except Exception:
                continue

            row = con.execute("""
                SELECT
                  COUNT(*) AS toplam,
                  SUM(CASE WHEN LOWER(COALESCE(durum,'')) IN ('yapildi','tamam')
                           THEN 1 ELSE 0 END) AS bitti
                FROM odev WHERE kume_id=?
            """, (kume_id,)).fetchone()
            toplam = int(row["toplam"] or 0)
            bitti = int(row["bitti"] or 0)

            oid = self._ogr_id_from_row(r)
            if not oid:
                continue
            if toplam > 0 and bitti == 0:
                never.add(int(oid))
            elif 0 < bitti < toplam:
                partial.add(int(oid))

        return sorted(never), sorted(partial)

    # --- Plan oluşturucu (WhatsApp ön-kontrol) ---
    def _planla(self, ids, mod, sablon):
        """
        ids: ogrenci_id listesi
        mod: 'today' | 'tomorrow' | 'overdue'
        sablon: mesaj şablonu
        """
        plan = {}
        bos_mesaj = 0
        numarasiz = 0
        lines = []

        for oid in ids:
            ad = self._ogrenci_adsoyad(oid)
            try:
                msg = self._mesaj_olustur_ogr(oid, mod, sablon)
            except Exception:
                msg = None

            try:
                nums = self._telefonlar(oid) or []
            except Exception:
                nums = []

            try:
                kume_ids = self._kume_idleri_due(oid, mod)
                kume_say = len(kume_ids)
            except Exception:
                kume_say = 0

            if not msg:
                bos_mesaj += 1
            if not nums:
                numarasiz += 1

            plan[oid] = {
                "ad": ad,
                "msg_ok": bool(msg),
                "msg_len": len(msg or ""),
                "nums": list(nums),
                "kume_say": kume_say,
            }
            lines.append(f"{ad}: msg={'var' if msg else 'yok'} num={'var' if nums else 'yok'} kume={kume_say}")

        return plan, " | ".join(lines[-6:]) if lines else "", bos_mesaj, numarasiz

    # --- Seçili ID listesine today modunda gönderim (menü kısayolu kullanır) ---
    def _send_custom_today(self, ogr_ids):
        sablon = (appset.ayar_get('hatirlatma_wp_sablon_bugun') or self._aktif_sablon()) or "Merhaba {ad}, {ozet}"
        mod = 'today'
        plan, _log, bos_msg, numarasiz = self._planla(ogr_ids, mod, sablon)

        ok = fail = 0
        for oid in ogr_ids:
            if not plan.get(oid, {}).get("msg_ok"):
                continue
            m = self._mesaj_olustur_ogr(oid, mod, sablon)
            if not m:
                continue
            r = self._whatsapp_gonder_ogr(oid, m)
            ok += self._normalize_sent(r)
            if isinstance(r, dict):
                f = r.get('fail', [])
                fail += (len(f) if isinstance(f, (list, tuple, set)) else int(bool(f)))

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "WhatsApp",
                                f"Gönderilen: {ok}\nBaşarısız: {fail}\nMesaj oluşmayan: {bos_msg}\nNumarası olmayan: {numarasiz}")

    #F


    #s . whatsapp için
    def _split_never_vs_partial(self, rows):
        """Seçili satırlardan ogrenci_id toplayıp 'bitti==0' olanları NEVER, 0<bitti<toplam olanları PARTIAL döndür."""
        con = db.get_conn()
        never, partial = set(), set()
        for r in rows:
            kume_id = int(self.tab.item(r, self.COL_KUME).text())
            row = con.execute("""
                SELECT COUNT(*) AS toplam,
                       SUM(CASE WHEN LOWER(COALESCE(durum,'')) IN ('yapildi','tamam') THEN 1 ELSE 0 END) AS bitti
                FROM odev WHERE kume_id=?""", (kume_id,)).fetchone()
            toplam = int(row["toplam"] or 0);
            bitti = int(row["bitti"] or 0)
            oid = self._ogr_id_from_row(r)
            if not oid: continue
            if toplam > 0 and bitti == 0:
                never.add(int(oid))
            elif 0 < bitti < toplam:
                partial.add(int(oid))
        return sorted(never), sorted(partial)

    def _send_custom_today(self, ogr_ids):
        """Bugün modunda yalnızca verilen id'lere gönderim (seçimden bağımsız)."""
        sablon = (appset.ayar_get('hatirlatma_wp_sablon_bugun') or self._aktif_sablon()) or "Merhaba {ad}, {ozet}"
        mod = 'today'
        plan, _planlog, bos_msg, numarasiz = self._planla(ogr_ids, mod, sablon)
        ok = fail = 0
        for oid in ogr_ids:
            if not plan.get(oid, {}).get("msg_ok"): continue
            msg = self._mesaj_olustur_ogr(oid, mod, sablon)
            if not msg: continue
            res = self._whatsapp_gonder_ogr(oid, msg)
            ok += self._normalize_sent(res)
            if isinstance(res, dict):
                f = res.get('fail', [])
                fail += (len(f) if isinstance(f, (list, tuple, set)) else int(bool(f)))
        QMessageBox.information(self, "WhatsApp",
                                f"Gönderilen: {ok}\nBaşarısız: {fail}\nMesaj oluşmayan: {bos_msg}\nNumarası olmayan: {numarasiz}")
    #f

    #s
    def _ogrenci_adsoyad(self, oid: int) -> str:
        con = db.get_conn()
        r = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (oid,)).fetchone()
        return f"{(r['ad'] or '').strip()} {(r['soyad'] or '').strip()}".strip() if r else f"Öğrenci#{oid}"

    def _ogr_id_from_row(self, r: int):
        # ZATEN varsa dokunma; yoksa bu güvenli sürümü kullan
        it = self.tab.item(r, self.COL_KUME)
        if not it:
            return None
        val = it.data(Qt.ItemDataRole.UserRole)
        if val is not None:
            try:
                return int(val)
            except Exception:
                return None
        txt = (it.text() or "").strip()
        digits = txt if txt.isdigit() else "".join(ch for ch in txt if ch.isdigit())
        if not digits:
            return None
        con = db.get_conn()
        row = con.execute("SELECT ogrenci_id FROM odev_kume WHERE id=?", (int(digits),)).fetchone()
        return int(row["ogrenci_id"]) if row and row["ogrenci_id"] is not None else None

    def _kume_bitti_toplam(self, kume_id: int):
        con = db.get_conn()
        r = con.execute("""
            SELECT
              COUNT(*) AS toplam,
              SUM(CASE WHEN LOWER(COALESCE(durum,'')) IN ('yapildi','tamam') THEN 1 ELSE 0 END) AS bitti
            FROM odev WHERE kume_id=?
        """, (kume_id,)).fetchone()
        toplam = int(r["toplam"] or 0)
        bitti = int(r["bitti"] or 0)
        return bitti, toplam

    def _split_never_vs_partial(self, rows: list[int] | None = None, oids: list[int] | None = None):
        """
        'Hiç gelmeyen' = kümesinde toplam>0 ve bitti==0
        'Kısmi' = 0 < bitti < toplam
        rows verilirse listeden alır; oids verilirse o id’ler için tabloda tarar.
        """
        never_ids, partial_ids = set(), set()
        if rows is None:
            rows = []
        # hangi satırlara bakılacağını bul
        if not rows and oids:
            target = []
            for r in range(self.tab.rowCount()):
                oid = self._ogr_id_from_row(r)
                if oid in set(oids):
                    target.append(r)
            rows = target

        for r in rows:
            oid = self._ogr_id_from_row(r)
            if not oid:
                continue
            kume_id_txt = (self.tab.item(r, self.COL_KUME).text() or "").strip()
            try:
                kume_id = int(kume_id_txt)
            except Exception:
                continue
            bitti, toplam = self._kume_bitti_toplam(kume_id)
            if toplam > 0 and bitti == 0:
                never_ids.add(oid)
            elif 0 < bitti < toplam:
                partial_ids.add(oid)
        return sorted(never_ids), sorted(partial_ids)

    # ---- WhatsApp yardımcıları ----
    def _normalize_sent(self, result):
        try:
            if isinstance(result, bool): return 1 if result else 0
            if isinstance(result, int):  return max(0, result)
            if isinstance(result, dict):
                for k in ("gonderilen", "sent", "count", "n", "ok"):
                    if k in result:
                        v = result[k]
                        return len(v) if isinstance(v, (list, tuple, set)) else int(v or 0)
            if isinstance(result, str):
                return 1 if result.strip().lower() in {"ok", "true", "1", "sent", "success"} else 0
        except Exception:
            pass
        return 0

    def _whatsapp_quick_check(self, baslik="WhatsApp Hızlı Kontrol"):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, baslik,
                                "Kontrol listesi:\n"
                                " • WhatsApp Desktop açık ve QR oturum açık mı?\n"
                                " • Telefon numaraları +90 formatında mı?\n"
                                " • (macOS) Erişilebilirlik izni verildi mi?\n"
                                " • utils/whatsapp.whatsapp_gonder doğru çalışıyor mu?"
                                )

    def _kume_idleri_due(self, ogrenci_id: int, mod: str):
        """
        Belirli bir öğrenci için, bitiş/veriliş tarihine göre randevuya düşen küme id'lerini döner.

        mod:
          - "today"    : bugün bitiş/veriliş tarihi olanlar
          - "tomorrow" : yarın bitiş/veriliş tarihi olanlar
          - "in2days"  : 2 gün sonra bitiş/veriliş tarihi olanlar
          - "overdue"  : bugünden önce bitiş/veriliş tarihi olup, hiç 'yapıldı' işareti olmayan kümeler
        """
        con = db.get_conn()

        # Baz alınan tarih: gerçek bugünün tarihi
        # (istersen burayı self.dtSec.date() ile seçili güne bağlarız)
        base = date.today()

        # --- BUGÜN / YARIN / 2 GÜN SONRA ---
        if mod in ("today", "tomorrow", "in2days"):
            if mod == "today":
                target = base
            elif mod == "tomorrow":
                target = base + timedelta(days=1)
            else:  # "in2days"
                target = base + timedelta(days=2)

            target_str = target.isoformat()
            q = """
                SELECT id
                FROM odev_kume
                WHERE ogrenci_id = ?
                  AND date(COALESCE(bitis_tarihi, verilis_tarihi)) = date(?)
            """
            return [int(r["id"]) for r in con.execute(q, (ogrenci_id, target_str))]

        # --- GECİKMİŞ KÜMELER (hiç yapılmamış) ---
        elif mod == "overdue":
            today_str = base.isoformat()
            q = """
                SELECT id,
                       COALESCE(bitis_tarihi, verilis_tarihi) AS bt
                FROM odev_kume
                WHERE ogrenci_id = ?
                  AND date(COALESCE(bitis_tarihi, verilis_tarihi)) < date(?)
            """
            rows = con.execute(q, (ogrenci_id, today_str)).fetchall()
            sonuc = []

            for r in rows:
                kume_id = int(r["id"])
                bt = r["bt"]

                # (kalan_gun, durum, yuzde, toplam_satir, yapilan_satir, toplam_dk)
                stat = self._kume_istatistik(kume_id, bt)
                if len(stat) == 6:
                    _, _, _, toplam, bitti, _ = stat
                elif len(stat) == 5:
                    _, _, toplam, bitti, _ = stat
                else:
                    continue

                # Tanım: en az bir satır olacak ve HİÇBİR satır yapılmamış olacak
                if toplam > 0 and bitti == 0:
                    sonuc.append(kume_id)

            return sonuc

        # Diğer modlar için (never / partial) burada kullanılmıyor
        return []

    def _kume_ozet_satirlari(self, kume_id: int):
        con = db.get_conn()

        h = con.execute(
            "SELECT verilis_tarihi, bitis_tarihi FROM odev_kume WHERE id=?",
            (kume_id,)
        ).fetchone()

        ver = h["verilis_tarihi"] if h else "-"
        bit = h["bitis_tarihi"] if h else "-"

        lines = [f"— Küme #{kume_id} • {ver} → {bit}"]
        toplam_dk = 0

        # 1) Yeni odev tablosu
        for r in con.execute("""
                SELECT ders,
                       kitap_ad                    AS kitap,
                       konu_ad                     AS konu,
                       COALESCE(saat_dk, 0)        AS dk
                FROM odev
                WHERE kume_id=?
                  AND silindi = 0
                ORDER BY id
            """, (kume_id,)):
            sat = f"• {r['ders']} / {r['kitap']} / {r['konu']}"
            if r["dk"]:
                sat += f" ({int(r['dk'])} dk)"
                toplam_dk += int(r["dk"])
            lines.append(sat)

        # 2) Eski odev_satir tablosu (varsa) – aynı kümeye bağlı satırlar da gelsin
        try:
            for r in con.execute("""
                    SELECT ders,
                           COALESCE(kitap_ad, kitap, '') AS kitap,
                           COALESCE(konu_ad,  konu,  '') AS konu,
                           COALESCE(dk, sure_dk, 0)      AS dk
                    FROM odev_satir
                    WHERE kume_id=?
                      AND silindi = 0
                    ORDER BY id
                """, (kume_id,)):
                sat = f"• {r['ders']} / {r['kitap']} / {r['konu']}"
                if r["dk"]:
                    sat += f" ({int(r['dk'])} dk)"
                    toplam_dk += int(r["dk"])
                lines.append(sat)
        except Exception:
            # Eski tablo yoksa sessizce geç
            pass

        return lines, toplam_dk

    def _mesaj_olustur_ogr(self, ogr_id: int, mod: str, sablon: str):
        con = db.get_conn()

        ogr = con.execute(
            "SELECT ad, soyad FROM ogrenci WHERE id=?",
            (ogr_id,)
        ).fetchone()
        if not ogr:
            return ""

        ad = f"{ogr['ad']} {ogr['soyad']}".strip()

        # İlgili moda göre kümeleri al (bugün / yarın / gecikmiş)
        kume_ids = self._kume_idleri_due(ogr_id, mod)
        if not kume_ids:
            return ""

        tum_lines = []
        toplam_dk = 0

        for kid in kume_ids:
            lines, dk = self._kume_ozet_satirlari(kid)
            tum_lines.extend(lines)
            toplam_dk += dk

        ozet = "\n".join(tum_lines)
        if not ozet.strip():
            return ""

        # Şablonu doldururken mod bilgisini de ver
        body = self._fill_template(sablon, ad, ozet, toplam_dk, mod)

        # Mesajın üst kısmına moda göre kısa giriş cümlesi
        if mod == "today":
            giris = "Bugün ödev kontrolün var. Aşağıdaki çalışmaları tamamlayıp gelmen önemli."
        elif mod == "tomorrow":
            giris = "Yarın ödev kontrolün var. Lütfen aşağıdaki çalışmaları elinden geldiğince tamamla."
        elif mod == "overdue":
            giris = "Kontrol tarihi geçmiş ve henüz tamamlanmamış ödevlerin aşağıda listelenmiştir."
        else:
            giris = ""

        baslik = f"{ad} - Ödev Özeti"

        if giris:
            return baslik + "\n\n" + giris + "\n\n" + body
        else:
            return baslik + "\n\n" + body
    def _whatsapp_gonder_ogr(self, oid: int, mesaj: str):
        # Telefonları çek
        con = db.get_conn()
        r = con.execute("SELECT veli_tel1, veli_tel2, ogr_tel FROM ogrenci WHERE id=?", (oid,)).fetchone()

        def _clean(s):
            s = ''.join(ch for ch in (s or '') if ch.isdigit() or ch == '+')
            if not s: return ''
            if s.startswith('+'): return s
            if len(s) == 11 and s.startswith('0'): return '+90' + s[1:]
            if len(s) == 10: return '+90' + s
            return '+' + s

        nums = []
        if r:
            for k in ("veli_tel1", "veli_tel2", "ogr_tel"):
                n = _clean(r[k]);
                nums.append(n) if n else None
        nums = list(dict.fromkeys(nums))
        if not nums:
            return {"ok": [], "fail": [], "gonderilen": 0}

        try:
            from utils import whatsapp
            res = whatsapp.whatsapp_gonder(nums, mesaj, ogrenci_id=oid)  # senin imzana uygunsa böyle
            sent = self._normalize_sent(res)
            return {"ok": nums[:sent], "fail": nums[sent:], "gonderilen": sent}
        except Exception as e:
            # sessiz düş: log yerine bilgi döndür
            return {"ok": [], "fail": nums, "gonderilen": 0, "error": str(e)}
    #f


    #s---2 kasım
    def _ogrenci_adsoyad(self, oid: int) -> str:
        con = db.get_conn()
        r = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (oid,)).fetchone()
        return f"{(r['ad'] or '')} {(r['soyad'] or '')}".strip() if r else f"Öğrenci#{oid}"

    def _tum_ogrenci_idleri(self):
        con = db.get_conn()
        return [int(r["id"]) for r in con.execute("SELECT id FROM ogrenci ORDER BY id").fetchall()]

    def _kume_istat(self, oid: int) -> tuple[int, int, int]:
        """
        Seçilen ogrenci_id için tabloda görünen ilk kume_id'yi bulur,
        o kümeye ait (bitti, toplam, yüzde) döndürür.
        Öğrenciye ait küme görünmüyorsa (0,0,0).
        """
        kume_id = self._first_kume_for_student_in_view(int(oid))
        if not kume_id:
            return 0, 0, 0
        return self._odev_done_counter(int(kume_id))

    def _has_any_whatsapp_log(self, oid: int) -> bool:
        con = db.get_conn()
        r = con.execute("SELECT 1 FROM whatsapp_log WHERE ogrenci_id=? LIMIT 1", (oid,)).fetchone()
        return bool(r)

    def _split_never_vs_partial(self, oids: list[int]) -> tuple[list[int], list[int]]:
        """
        'Hiç görüşmeye gelmeyen' ve 'kısmi yapan' ayrımı.
        - never: toplam>0 ve bitti==0 olanlar
        - partial: toplam>0 ve 0<bitti<toplam olanlar
        Not: toplam==0 ise hiçbirine sokmuyoruz (kayıt yok).
        """
        never, partial = [], []
        for oid in oids:
            try:
                done, total, perc = self._kume_istat(int(oid))
            except Exception:
                done, total, perc = 0, 0, 0
            if total <= 0:
                continue  # veri yok; atla
            if done == 0:
                never.append(int(oid))
            elif 0 < done < total:
                partial.append(int(oid))
        return never, partial



    #s--
    def _default_wa_template_for_mode(self, mode: str) -> str:
        """
        WhatsApp toplu gönderim için, seçilen moda göre temel mesaj şablonu.
        Kullanıcı isterse dialog içinde bunu değiştirebilir.

        Kullanılabilir placeholder'lar:
            {ad}   -> öğrencinin adı / adı soyadı
            {ozet} -> oluşturulan ödev listesi
        """
        templates = {
            "today": (
                "👋 Merhaba değerli öğrencim {ad},\n\n"
                "📌 Bugün ödev kontrolünüz var.\n\n"
                "📚 Lütfen şu çalışmaları tamamlayın:\n{ozet}\n\n"
                "⏳ Programına uyman başarı için çok önemli.\nHer zaman yanındayım! 💙"
            ),
            "tomorrow": (
                "👋 Merhaba değerli öğrencim {ad},\n\n"
                "📌 Yarın ödev kontrolünüz var.\n\n"
                "📚 Lütfen çalışmaları hazırla:\n{ozet}\n\n"
                "⏳ Yarın görüşmek üzere! 💙"
            ),
            "in2days": (
                "👋 Merhaba değerli öğrencim {ad},\n\n"
                "📌 2 gün sonra ödev kontrolünüz var.\n\n"
                "📚 Hazırlıklarını yapmayı unutma:\n{ozet}\n\n"
                "💪 Başarılar dilerim! 💙"
            ),
            "overdue": (
                "👋 Merhaba değerli öğrencim {ad},\n\n"
                "⚠️ Ödev kontrolünüz gecikmiş görünüyor.\n\n"
                "🚀 Lütfen en kısa sürede şunları tamamlayalım:\n{ozet}\n\n"
                "Birlikte halledebiliriz, güveniyorum! 💙"
            ),
            "never": (
                "👋 Merhaba değerli öğrencim {ad},\n\n"
                "⚠️ Bugün planlanan görüşmeye katılmadınız.\n\n"
                "📚 Lütfen şu çalışmaları tamamlayıp dönüş yapın:\n{ozet}\n\n"
                "Telafi edelim! 💙"
            ),
            "partial": (
                "👋 Merhaba değerli öğrencim {ad},\n\n"
                "👍 Ödevlerinizin bir kısmı tamamlanmış, tebrikler.\n\n"
                "📌 Eksik kalanları da tamamlayalım:\n{ozet}\n\n"
                "Gayretin harika! 💙"
            ),
            "congratulate": (
                "🌟 Harikasın {ad}! Bu haftaki tüm ödevlerini eksiksiz tamamladığın için tebrik ediyorum. "
                "Disiplinli çalışman ve gayretin takdire şayan. Başarılarının devamını dilerim! 👏"
            ),
        }

        # Eğer bu mod için özel bir şablon varsa onu kullan
        if mode in templates:
            return templates[mode]

        # Yedek: genel ayardan gelen şablon
        try:
            return self._aktif_sablon()
        except Exception:
            return "Merhaba değerli öğrencim {ad}, ödev çalışmalarınızla ilgili bilgilendirme: {ozet}"

    def _fill_template(self, tpl: str, ogr: dict, mode: str) -> str:
        ad = (ogr.get("ad") or "").strip().upper()
        soyad = (ogr.get("soyad") or "").strip().upper()
        ad_full = f"{ad} {soyad}".strip()

        # 1) Durum cümlesi
        durum_map = {
            "today": "bugün ödev kontrolünüz var.",
            "tomorrow": "yarın ödev kontrolünüz var.",
            "in2days": "2 gün sonra ödev kontrolünüz var.",
            "overdue": "ödev kontrolünüz gecikmiş görünüyor.",
            "never": "bugünkü görüşmeye henüz gelmediniz.",
            "partial": "bugünkü ödevlerinizin bir kısmını tamamladınız.",
        }
        durum = durum_map.get(mode, "ödev çalışmalarınızla ilgili bilgilendirme.")

        # 2) Hitap — sadece burada olacak
        hitap = f"👋 Merhaba değerli öğrencim {ad_full},\n\n"

        # 3) Placeholder değişimi
        tpl = tpl.replace("{ad}", ad)
        tpl = tpl.replace("{soyad}", soyad)
        tpl = tpl.replace("{ogrenci}", ad_full)
        tpl = tpl.replace("{ogrenci_adsoyad}", ad_full)
        tpl = tpl.replace("{durum}", durum)

        if mode == "congratulate":
            # Tebrik mesajı için özel prefix kontrolü (prepend yapma)
            pass
        elif not tpl.startswith("👋 Merhaba"):
             tpl = hitap + tpl

        return tpl

    def _open_whatsapp_batch_dialog(self, mode: str, oids=None):
        """
        mode : today / tomorrow / in2days / overdue / never / partial / congratulate
        oids : [optional] list of student IDs to limit the batch
        """
        from PyQt6.QtWidgets import QMessageBox

        # ------------------- 1) Aday öğrenci listesi -------------------
        if oids is None:
            # Eski otomatik davranış
            if mode in ("today", "tomorrow", "in2days", "overdue"):
                # Bugün / yarın / 2 gün sonra / gecikmiş -> tüm öğrenciler taranır
                oids = self._tum_ogrenci_idleri()
            else:
                # never / partial / congratulate -> seçili varsa seçili, yoksa tümü
                oids = self._secili_ogr_idler() or self._tum_ogrenci_idleri()
        else:
            # Butonlardan gelen özel seçim
            oids = [int(o) for o in (oids or [])]
            if not oids:
                QMessageBox.warning(self, "Seçim", "Lütfen listeden en az bir satır seçin.")
                return

        rows = []
        for oid in oids:
            oid = int(oid)
            ad = self._ogrenci_adsoyad(oid)
            
            # Mod'a göre öğrenciyi filtrele (örn: never ise gelmemiş mi?)
            # 'congratulate' modu: HERKES (seçili olanlar) kabul edilir, ekstra filtre yok.
            if mode == "never":
                 if not self._is_bugun_gelmemis(oid): continue
            elif mode == "partial":
                 # ... (mevcut kod) ...
                 pass



            durum_map = {
                "today": "bugün",
                "tomorrow": "yarın",
                "in2days": "2 gün sonra",
                "overdue": "geciken",
                "never": "bugünkü görüşmeye gelmeyen",
                "partial": "kısmi yapan",
            }
            durum = durum_map.get(mode, "")
            nums = self._numbers_dict(oid)

            # ------------------- 2) FİLTRELER (ESKİ MANTIK) -------------------
            if mode == "never":
                # yalnızca BUGÜN due olup done==0 olanlar
                if not self._is_bugun_gelmemis(oid):
                    continue

            elif mode == "partial":
                # bugüne özel kısmi (0<done<total) varsa al; yoksa atla
                klist = self._kume_idleri_due(oid, "today")
                ok = False
                for k in (klist or []):
                    d, t, _ = self._odev_done_counter(int(k))
                    if t > 0 and 0 < d < t:
                        ok = True
                        break
                if not ok:
                    continue

            elif mode in ("today", "tomorrow", "in2days", "overdue"):
                # ilgili moda göre (bugün/yarın/2 gün sonra/gecikmiş) en az bir kümesi olmalı
                if not self._kume_idleri_due(oid, mode):
                    continue

            rows.append((oid, ad, durum, nums))


        if not rows:
            QMessageBox.information(self, "WhatsApp", "Gönderilecek uygun öğrenci bulunamadı.")
            return

        # Başlıktaki yazı (sadece görsel)
        title_map = {
            "today": "BUGÜN",
            "tomorrow": "YARIN",
            "in2days": "2 GÜN SONRA",
            "overdue": "GECİKMİŞ",
            "never": "HİÇ GELMEYENLER",
            "partial": "KISMİ YAPANLAR",
        }
        dlg_title = f"WhatsApp – {title_map.get(mode, mode)}"

        dlg = _WhatsAppBatchDialog(self, dlg_title, rows)
        dlg._wa_mode = mode


        # ------------------- 3) Mesaj şablonu -------------------
        try:
            base_tpl = self._aktif_sablon() or ""
        except Exception:
            base_tpl = ""

        durum_cumle_map = {
            "today": "bugün ödev kontrolünüz var.",
            "tomorrow": "yarın ödev kontrolünüz var.",
            "in2days": "2 gün sonra ödev kontrolünüz var.",
            "overdue": "ödev kontrolünüz gecikmiş görünüyor.",
            "never": "bugünkü görüşmeye henüz gelmediniz.",
            "partial": "bugünkü ödevlerinizin bir kısmını tamamladınız.",
        }
        durum_cumle = durum_cumle_map.get(mode, "ödev çalışmalarınızla ilgili bilgilendirme.")

        if "{durum}" in base_tpl:
            sablon = base_tpl.replace("{durum}", durum_cumle)
        else:
            #sablon = f"Merhaba, {durum_cumle} Lütfen şu çalışmaları tamamlayın: {{ozet}}"
            sablon = (
                "👋 Merhaba değerli öğrencim {ad},\n\n"
                f"📌 {durum_cumle}\n\n"
                "📚 Aşağıdaki çalışmaları tamamlamayı unutma:\n"
                "{ozet}\n\n"
                "⏳ Programına uyman başarı için çok önemli.\n"
                "Her zaman yanındayım! 💙"
            )

        # 🔥 HER MESAJIN BAŞINA ÖĞRENCİ ADI EKLE
        #sablon = f"Merhaba değerli öğrencim {{ad}},\n{sablon}"

        dlg._msg_template = sablon
        dlg.edtTemplate.setText(sablon)

        # görünüm
        self._tune_wa_batch_table(dlg.tbl)

        # Excel’e kaydet / Gönder
        dlg.btnExport.clicked.connect(lambda: self._export_wa_batch_to_excel(dlg))
        dlg.btnSend.clicked.connect(lambda: self._send_from_whatsapp_batch(dlg))
        dlg.exec()

    def _open_whatsapp_batch_dialog(self, mode: str, oids: list[int] | None = None):
        """
        mode : today / tomorrow / in2days / overdue / never / partial

        Eski mantık KORUNDU:
            - today / tomorrow / in2days / overdue  -> (oids None ise) tüm öğrenciler taranır
            - never / partial                       -> (oids None ise) seçili varsa seçili, yoksa tümü

        Yeni ek:
            - oids listesi dolu gelirse, SADECE o ID'ler üzerinden çalışır
              (alt taraftaki 'Seçili' butonları bunu kullanacak)
        """
        from PyQt6.QtWidgets import QMessageBox

        # ------------------- 1) Aday öğrenci listesi -------------------
        if oids is None:
            # Eski otomatik davranış
            if mode in ("today", "tomorrow", "in2days", "overdue"):
                # Bugün / yarın / 2 gün sonra / gecikmiş -> tüm öğrenciler taranır
                oids = self._tum_ogrenci_idleri()
            else:
                # never / partial -> seçili varsa seçili, yoksa tümü
                oids = self._secili_ogr_idler() or self._tum_ogrenci_idleri()
        else:
            # Butonlardan gelen özel seçim
            oids = [int(o) for o in (oids or [])]
            if not oids:
                QMessageBox.warning(self, "Seçim", "Lütfen listeden en az bir satır seçin.")
                return

        rows = []
        for oid in oids:
            oid = int(oid)
            ad = self._ogrenci_adsoyad(oid)
            
            # Mod'a göre öğrenciyi filtrele (örn: never ise gelmemiş mi?)
            if mode == "never":
                 if not self._is_bugun_gelmemis(oid): continue
            elif mode == "partial":
                 # bugüne özel kısmi (0<done<total) varsa al; yoksa atla
                 klist = self._kume_idleri_due(oid, "today")
                 ok = False
                 for k in (klist or []):
                     d, t, _ = self._odev_done_counter(int(k))
                     if t > 0 and 0 < d < t:
                         ok = True
                         break
                 if not ok:
                     continue
            elif mode in ("today", "tomorrow", "in2days", "overdue"):
                 # ilgili moda göre en az bir kümesi olmalı
                 if not self._kume_idleri_due(oid, mode):
                     continue

            durum_map = {
                "today": "bugün",
                "tomorrow": "yarın",
                "in2days": "2 gün sonra",
                "overdue": "geciken",
                "never": "bugünkü görüşmeye gelmeyen",
                "partial": "kısmi yapan",
                "congratulate": "harika giden",
            }
            durum = durum_map.get(mode, "")
            nums = self._numbers_dict(oid)
            
            rows.append((oid, ad, durum, nums))

        if not rows:
            QMessageBox.information(self, "WhatsApp", "Gönderilecek uygun öğrenci bulunamadı.")
            return

        # Başlıktaki yazı (sadece görsel)
        title_map = {
            "today": "BUGÜN",
            "tomorrow": "YARIN",
            "in2days": "2 GÜN SONRA",
            "overdue": "GECİKMİŞ",
            "never": "HİÇ GELMEYENLER",
            "partial": "KISMİ YAPANLAR",
            "congratulate": "TEBRİK",
        }
        dlg_title = f"WhatsApp – {title_map.get(mode, mode)}"

        dlg = _WhatsAppBatchDialog(self, dlg_title, rows)
        dlg._wa_mode = mode

        # 2) Şablonu belirle
        tpl = self._default_wa_template_for_mode(mode)
        dlg._msg_template = tpl
        dlg.edtTemplate.setPlainText(tpl)

        # Görünüm ve Sinyaller
        dlg._update_preview()
        self._tune_wa_batch_table(dlg.tbl)

        dlg.btnExport.clicked.connect(lambda: self._export_wa_batch_to_excel(dlg))
        dlg.btnSend.clicked.connect(lambda: self._send_from_whatsapp_batch(dlg))

        if dlg.exec():
            # Gönderim başarılı ise
            self._send_from_whatsapp_batch(dlg)

    #f--

    def _tune_wa_batch_table(self, tbl):
        from PyQt6.QtWidgets import QHeaderView
        from PyQt6.QtCore import Qt

        if tbl is None:
            return

        tbl.verticalHeader().setDefaultSectionSize(44)
        for r in range(tbl.rowCount()):
            tbl.setRowHeight(r, 44)

        tbl.setWordWrap(False)
        tbl.setTextElideMode(Qt.TextElideMode.ElideRight)

        hdr = tbl.horizontalHeader()
        hdr.setStretchLastSection(True)

        COL_GONDER, COL_AD, COL_DURUM, COL_VELI1, COL_VELI2, COL_OGRTEL, COL_ONIZLEME = range(7)

        hdr.setSectionResizeMode(COL_GONDER, QHeaderView.ResizeMode.Fixed)
        tbl.setColumnWidth(COL_GONDER, 70)

        # ÖĞRENCİ kolonunu görünür tutmak için min genişlik veriyoruz
        hdr.setSectionResizeMode(COL_AD, QHeaderView.ResizeMode.Interactive)
        tbl.setColumnWidth(COL_AD, 220)

        hdr.setSectionResizeMode(COL_DURUM, QHeaderView.ResizeMode.ResizeToContents)

        for c in (COL_VELI1, COL_VELI2, COL_OGRTEL):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
            tbl.setColumnWidth(c, max(180, tbl.columnWidth(c)))

        hdr.setSectionResizeMode(COL_ONIZLEME, QHeaderView.ResizeMode.Stretch)

        tbl.setStyleSheet("""
            QTableWidget::item { padding: 6px; }
            QLineEdit { padding: 6px 8px; }
            QCheckBox { padding-left: 6px; }
        """)

    def _numbers_dict(self, oid: int) -> dict:
        """DB’den numaraları topla ve +90… formatla."""
        con = db.get_conn()
        r = con.execute("SELECT veli_tel1, veli_tel2, ogr_tel FROM ogrenci WHERE id=?", (oid,)).fetchone()
        def clean(s):  # kendi temizleyicin
            return self._clean_phone(s or "")
        return {
            "veli1": clean(r["veli_tel1"]) if r else "",
            "veli2": clean(r["veli_tel2"]) if r else "",
            "ogr":   clean(r["ogr_tel"])   if r else "",
        }

    def _whatsapp_gonder_nums(self, nums: list[str], mesaj: str, ogrenci_id: int | None = None):
        """Seçilen numaralara, masaüstü WhatsApp ile gönder. Hatalıyı otomatik atlar."""
        from utils import whatsapp
        # Temizle + benzersiz
        cleaned = []
        for n in nums:
            n2 = self._clean_phone(n)
            if n2:
                cleaned.append(n2)
        cleaned = list(dict.fromkeys(cleaned))
        if not cleaned or not mesaj:
            return {"ok": [], "fail": cleaned, "gonderilen": 0}

        try:
            # Toplu dene
            res = whatsapp.whatsapp_gonder(list(cleaned), mesaj, ogrenci_id=ogrenci_id)
            sent = self._normalize_sent(res)
            if sent > 0:
                return {"ok": cleaned[:sent], "fail": cleaned[sent:], "gonderilen": sent}
        except Exception:
            pass

        # Tek tek fallback
        ok, fail = [], []
        for n in cleaned:
            try:
                r = whatsapp.whatsapp_gonder([n], mesaj, ogrenci_id=ogrenci_id)
                s = self._normalize_sent(r)
                if s > 0 or r is True or r == 1:
                    ok.append(n)
                else:
                    fail.append(n)
            except Exception:
                fail.append(n)
        return {"ok": ok, "fail": fail, "gonderilen": len(ok)}

    def _clean_phone(self, s: str) -> str:
        """Numarayı WhatsApp için normalize eder (+90xxxxxxxxxx)."""
        s = ''.join(ch for ch in (s or '') if ch.isdigit() or ch == '+')
        if not s:
            return ''
        if s.startswith('+'):
            return s
        if len(s) == 11 and s.startswith('0'):  # 0XXXXXXXXXX → +90XXXXXXXXXX
            return '+90' + s[1:]
        if len(s) == 10:  # XXXXXXXXXX  → +90XXXXXXXXXX
            return '+90' + s
        return '+' + s

    def _kume_id_from_row(self, row: int) -> int | None:
        it = self.tab.item(row, self.COL_KUME) if hasattr(self, "COL_KUME") else None
        if not it:
            return None
        txt = (it.text() or "").strip()
        digits = txt if txt.isdigit() else ''.join(ch for ch in txt if ch.isdigit())
        return int(digits) if digits else None

    def _first_kume_for_student_in_view(self, oid: int) -> int | None:
        """Tabloda görünen satırlar içinde bu öğrenciye ait ilk kume_id."""
        from PyQt6.QtCore import Qt
        for r in range(self.tab.rowCount()):
            it = self.tab.item(r, self.COL_KUME) if hasattr(self, "COL_KUME") else None
            if not it:
                continue
            try:
                if int(it.data(Qt.ItemDataRole.UserRole)) == int(oid):
                    return self._kume_id_from_row(r)
            except Exception:
                continue
        return None

    def _odev_done_counter(self, kume_id: int) -> tuple[int, int, int]:
        """
        Bu kume_id için (bitti, toplam, yüzde) döndürür.
        'bitti' adında kolon olmasa bile PRAGMA ile uygun 'done' kolonu aranır.
        """
        import sqlite3
        con = db.get_conn()

        # 1) Şemadan olası bitiş kolonlarını seç
        try:
            cols = [c["name"] for c in con.execute("PRAGMA table_info(odev)").fetchall()]
        except Exception:
            cols = []
        candidate_bool = [c for c in ["bitti", "tamam", "yapildi", "is_done", "done"] if c in cols]
        has_durum = ("durum" in cols)

        # 2) Veriyi çek
        rows = con.execute("SELECT * FROM odev WHERE kume_id=?", (kume_id,)).fetchall()
        toplam = len(rows)
        if toplam == 0:
            return 0, 0, 0

        # 3) Python tarafında say
        def _truthy(v):
            if v is None: return False
            if isinstance(v, (int, bool)): return int(v) != 0
            s = str(v).strip().lower()
            return s in {"1", "true", "evet", "yes", "y", "t", "✓", "ok"}

        def _durum_done(s):
            s = (s or "").strip().lower()
            # en çok görülen anahtarlar
            return any(k in s for k in ["tamam", "bitti", "yapıl", "yapildi", "done", "complete"])

        bitti = 0
        for r in rows:
            done_ok = False
            # bool tarzı bir kolon varsa onu kullan
            for col in candidate_bool:
                try:
                    if _truthy(r[col]):
                        done_ok = True
                        break
                except Exception:
                    pass
            # yoksa 'durum' metninden anla
            if not done_ok and has_durum:
                try:
                    if _durum_done(r["durum"]):
                        done_ok = True
                except Exception:
                    pass
            bitti += int(done_ok)

        perc = int(round((bitti / toplam) * 100)) if toplam else 0
        return bitti, toplam, perc

    def _export_wa_batch_to_excel(self, dlg):
        from PyQt6.QtWidgets import QFileDialog
        import pandas as pd

        path, _ = QFileDialog.getSaveFileName(self, "Excel'e Kaydet", "wa_listesi.xlsx", "Excel (*.xlsx)")
        if not path:
            return

        rows = []
        T = dlg.tbl
        for r in range(T.rowCount()):
            # gönder seçili mi?
            send_w = T.cellWidget(r, 0)
            send_ok = getattr(send_w, "chk", None).isChecked() if send_w else False

            oid = T.item(r, 1).data(Qt.ItemDataRole.UserRole) if T.item(r, 1) else None
            ad = T.item(r, 1).text() if T.item(r, 1) else ""
            durum = T.item(r, 2).text() if T.item(r, 2) else ""

            def _num(col):
                w = T.cellWidget(r, col)
                return w.edit.text().strip() if (w and hasattr(w, "edit")) else ""

            def _sel(col):
                w = T.cellWidget(r, col)
                return bool(w.cb.isChecked()) if (w and hasattr(w, "cb")) else False

            rows.append({
                "Gönder": send_ok,
                "OID": oid,
                "Öğrenci": ad,
                "Durum": durum,
                "Veli-1 (seçili)": _sel(3), "Veli-1": _num(3),
                "Veli-2 (seçili)": _sel(4), "Veli-2": _num(4),
                "Öğrenci (seçili)": _sel(5), "Öğrenci": _num(5),
            })

        pd.DataFrame(rows).to_excel(path, index=False)
        QMessageBox.information(self, "Excel", "Liste kaydedildi.")

    def _is_bugun_gelmemis(self, oid: int) -> bool:
        """
        'Bugünkü görüşmeye gelmeyen' tanımı:
        - Öğrencinin 'today' due kume'lerinden en az birinde toplam>0 ve done==0 ise True.
        - Hiç 'today' due yoksa False.
        """
        klist = self._kume_idleri_due(int(oid), 'today') or []
        if not klist:
            return False
        for k in klist:
            try:
                done, total, _ = self._odev_done_counter(int(k))
                if total > 0 and done == 0:
                    return True
            except Exception:
                pass
        return False

    # --- ÖZET ÜRETİCİSİ ---------------------------------------------------------

    def _kisa_odev_aciklamasi(self, row) -> str:
        """
        Esnek: odev tablosunda hangi sütunlar varsa onlardan kısa başlık derler.
        Sıra: ders / ders_adi → konu / konu_adi → alt_konu → baslik/ad → id
        """

        def g(k):
            try:
                return (row[k] or "").strip()
            except Exception:
                return ""

        parcalar = []
        ders = g("ders") or g("ders_adi") or g("course")
        if ders: parcalar.append(ders)
        konu = g("konu") or g("konu_adi") or g("topic")
        if konu: parcalar.append(konu)
        alt = g("alt_konu") or g("subtopic")
        if alt: parcalar.append(alt)
        bas = g("baslik") or g("ad") or g("title")
        if bas and not parcalar:  # ders/konu yoksa en azından başlık dursun
            parcalar.append(bas)
        if not parcalar:
            try:
                parcalar.append(f"ödev#{row['id']}")
            except Exception:
                parcalar.append("ödev")
        return " / ".join(parcalar)

    def _mesaj_olustur_ogr(self, oid: int, mode: str, template: str) -> str:
        """
        {ozet} yerini, moda göre ilgili KÜME(ler)DEN kısa ödev listesiyle doldurur.
        - today: bugün due olan kümeler
        - overdue: gecikenler
        - never: bugün due olup done==0 olan kümeler
        - partial: bugün due olup 0<done<total olan kümeler
        """
        import sqlite3
        con = db.get_conn()

        # 1) aday kume_id listesi
        if mode in ("today", "overdue"):
            klist = self._kume_idleri_due(int(oid), 'today' if mode == "today" else 'overdue') or []
        elif mode == "never":
            klist = []
            for k in self._kume_idleri_due(int(oid), 'today') or []:
                d, t, _ = self._odev_done_counter(int(k))
                if t > 0 and d == 0:
                    klist.append(int(k))
        elif mode == "partial":
            klist = []
            for k in self._kume_idleri_due(int(oid), 'today') or []:
                d, t, _ = self._odev_done_counter(int(k))
                if t > 0 and 0 < d < t:
                    klist.append(int(k))
        else:
            klist = self._kume_idleri_due(int(oid), 'today') or []

        # 2) küme tarihlerini (varsa) çek
        def _kume_tarih(kid):
            try:
                r = con.execute("SELECT baslangic, bitis FROM odev_kume WHERE id=?", (kid,)).fetchone()
                if r:
                    bs = (r["baslangic"] or "").split(" ")[0]
                    bt = (r["bitis"] or "").split(" ")[0]
                    if bs or bt:
                        return f"{bs} → {bt}".strip()
            except Exception:
                pass
            return ""

        # 3) özet metni
        lines = []
        for idx, kid in enumerate(klist, 1):
            # bu kümeye ait ödevleri sırala
            try:
                rows = con.execute("SELECT * FROM odev WHERE kume_id=? ORDER BY id", (int(kid),)).fetchall()
            except Exception:
                rows = []
            if not rows:
                continue

            tarih = _kume_tarih(int(kid))
            if tarih:
                lines.append(f"— Küme #{idx} • {tarih}")
            else:
                lines.append(f"— Küme #{idx}")

            for r in rows:
                lines.append(f"• {self._kisa_odev_aciklamasi(r)}")

            # kümeler arasında boş satır
            if idx < len(klist):
                lines.append("")

        ozet = "\n".join(lines).strip()

        # 4) Şablonu doldur
        msg = (template or "").replace("{ozet}", ozet if ozet else "")
        # hiç özet üretilmediyse en azından yer tutucuyu sil
        return msg.strip()

    # ============= 1) Bugün gelmeyenleri bul + mesajı ayrıntılandır =============
    def _odev_satir_done_(self, r) -> bool:
        """
        Bir ödev satırının yapılmış/yapılmamış oluşunu güvenle tespit eder.
        Bool kolonlar (bitti/tamam/yapildi/is_done/done) önceliklidir.
        Aksi halde 'durum' metninden anlar.
        """

        def V(key):
            try:
                if hasattr(r, "keys") and key in r.keys():
                    return r[key]
                return r.get(key)
            except Exception:
                return None

        # 1) doğrudan bool tarzı kolonlar
        for key in ("bitti", "tamam", "yapildi", "is_done", "done"):
            v = V(key)
            if v is None:
                continue
            if isinstance(v, (int, bool)):
                return int(v) != 0
            s = str(v).strip().lower()
            if s in {"1", "true", "evet", "yes", "y", "t", "✓", "ok", "done", "tamam", "bitti"}:
                return True

        # 2) durum metni
        d = V("durum")
        s = str(d or "").strip().lower()
        if not s:
            return False
        # “tamam/bitti/yapıldı/complete/done” gibi anahtarlar
        keys = ("tamam", "bitti", "yapıl", "yapildi", "done", "complete", "bitirildi", "işaretlendi")
        return any(k in s for k in keys)

    def _odevleri_kumeden_getir_(self, kume_id: int):
        """
        odev tablosundan bu kümenin satırlarını getirir.
        Mümkün olan kolonları (ders/kitap/konu/durum/bitti/yapildi) tek seferde taşır.
        """
        con = db.get_conn()
        try:
            cols = [c["name"] for c in con.execute("PRAGMA table_info(odev)").fetchall()]
        except Exception:
            cols = []

        # Görünmesini istediğimiz aday kolonlar
        want = ["id", "kume_id", "ders", "kitap", "konu", "durum", "bitti", "tamam", "yapildi", "is_done", "done"]
        sel = [c for c in want if c in cols]
        if not sel:
            # en kötü ihtimal tüm satırları al
            sel = ["*"]

        q = f"SELECT {', '.join(sel)} FROM odev WHERE kume_id=? ORDER BY id"
        rows = con.execute(q, (int(kume_id),)).fetchall()
        return rows or []

    def _never_mode_ogrenciler_bugun_(self) -> list[int]:
        """
        'Hiç görüşmeye gelmeyen' = kontrol tarihi BUGÜN olan kümeleri bulunan
        ve o kümedeki hiçbir ödev 'yapıldı' görünmeyen öğrenciler.
        """
        adaylar = []
        for oid in self._tum_ogrenci_idleri():
            # bugün due olan küme listesi
            klist = self._kume_idleri_due(int(oid), 'today')  # senin mevcut fonksiyonun
            if not klist:
                continue
            # küme bazında kontrol: en az bir kümede hiç yapılmış iş yoksa 'never'
            has_never = False
            for kid in klist:
                rows = self._odevleri_kumeden_getir_(int(kid))
                if not rows:
                    continue
                # kümedeki yapılan sayısı
                done_count = sum(1 for r in rows if self._odev_satir_done_(r))
                if done_count == 0:  # bugün randevusu var ama hiçbir satır yapılmamış → gelmemiş say
                    has_never = True
                    break
            if has_never:
                adaylar.append(int(oid))
        return adaylar

    def _format_odev_listesi_(self, rows) -> list[str]:
        """
        Tercih sırası: Kitap/Konu -> Konu -> Kitap -> Ders
        """

        def V(obj, k):
            try:
                if hasattr(obj, "keys") and k in obj.keys():
                    return obj[k] or ""
                return (obj.get(k) or "")
            except Exception:
                return ""

        out = []
        for r in rows:
            ders = (V(r, "ders")).strip()
            kitap = (V(r, "kitap")).strip()
            konu = (V(r, "konu")).strip()

            if kitap and konu:
                out.append(f"• {kitap} / {konu}")
            elif konu:
                out.append(f"• {konu}")
            elif kitap:
                out.append(f"• {kitap}")
            else:
                out.append(f"• {ders or 'çalışma'}")
        return out

    def _mesaj_olustur_ogr(self, oid: int, mode: str, template: str) -> str:
        """
        {ozet} -> öğrencinin İLGİLİ kümelerindeki YAPILMAMIŞ maddelerin listesi.
        - today/overdue: self._kume_idleri_due(...) ile gelen kümeler
        - never: BUGÜN randevusu olan ve done==0 (hiç işaretlenmemiş) kümeler
        Özet boşsa '—' koyar.
        """
        import re

        # 1) ilgili kümeler
        if mode in ("today", "overdue"):
            klist = self._kume_idleri_due(int(oid), 'today' if mode == "today" else 'overdue') or []
        elif mode == "never":
            today_k = self._kume_idleri_due(int(oid), 'today') or []
            klist = [kid for kid in today_k if self._odev_done_counter(int(kid))[0] == 0]  # hiç işaret yok
        else:
            klist = self._kume_idleri_due(int(oid), 'today') or []

        # 2) her kümeden yapılmamışları topla
        lines_all = []
        for idx, kid in enumerate(klist, start=1):
            try:
                rows = self._odevleri_kumeden_getir_(int(kid))
            except Exception:
                rows = []

            not_done = []
            for r in rows:
                try:
                    if not self._odev_satir_done_(r):
                        not_done.append(r)
                except Exception:
                    # done bilgisi yoksa varsayılan: yapılmamış say
                    not_done.append(r)

            if not not_done:
                continue

            # birden fazla küme varsa başlık ekle
            if len(klist) > 1:
                lines_all.append(f"— Küme #{idx}")
            lines_all.extend(self._format_odev_listesi_(not_done))

        ozet = ("\n".join(lines_all)).strip() if lines_all else "—"

        # 3) şablona yerleştir + {ozet}, {ad}, {soyad}, {adsoyad} varyantlarını da yakala
        con = db.get_conn()
        try:
            r = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (int(oid),)).fetchone()
        finally:
            con.close()
        ad = (r["ad"] or "").strip() if r else ""
        soyad = (r["soyad"] or "").strip() if r else ""
        adsoyad = f"{ad} {soyad}".strip() or f"Öğrenci #{oid}"

        msg = str(template or "").strip()
        if not msg or msg in ("Merhaba", "Merhaba:", "Merhaba :", "Merhaba {ozet}", "Merhaba: {ozet}"):
            msg = (
                "👋 Merhaba {ad},\n\n"
                "📌 Ödev Takip & Randevu Bilgilendirmesi:\n"
                "📚 Çalışma Listen:\n{ozet}\n\n"
                "⏳ Programına uyup çalışmalarını tamamlamanı bekliyorum. Başarılar dilerim! 💙"
            )
        msg = msg.replace("{adsoyad}", adsoyad)
        msg = msg.replace("{ad}", ad or adsoyad)
        msg = msg.replace("{soyad}", soyad)
        msg = msg.replace("{ozet}", ozet)
        msg = re.sub(r"\{\s*[OoÖö]zet\s*\}", ozet, msg)
        return msg

    def _wa_today_noshow_kumeler(self, ogrenci_id: int) -> list[int]:
        """
        Bugün bitiş tarihi olan ve içinde HİÇ 'tamam/bitti/yapıldı/done' bulunmayan
        odev_kume.id listesini döndürür.
        """
        con = db.get_conn()
        # bugün bitişli kümeler
        klist = [r["id"] for r in con.execute(
            "SELECT id FROM odev_kume WHERE ogrenci_id=? AND date(bitis_tarihi)=date('now')",
            (int(ogrenci_id),)
        ).fetchall()]

        done_words = {"tamam", "bitti", "yapıldı", "yapildi", "done", "complete", "ok"}
        out = []
        for kid in klist:
            rows = con.execute("SELECT durum FROM odev WHERE kume_id=?", (kid,)).fetchall()
            if not rows:  # satır yoksa 'gelmedi' kabul etmeyelim
                continue
            any_done = False
            for rr in rows:
                s = (rr["durum"] or "").strip().lower()
                if any(w in s for w in done_words) or s == "1":
                    any_done = True
                    break
            if not any_done:
                out.append(kid)
        return out

    def _wa_kume_ozet(self, kume_id: int, sadece_yapilmayan: bool = False) -> list[str]:
        """
        • ders / kitap_ad / konu_ad formatında maddeler döndürür.
        Boş olan alanlar atlanır (ör: sadece 'ders / konu' da olabilir).
        """
        con = db.get_conn()
        rows = con.execute(
            "SELECT ders, kitap_ad, konu_ad, durum FROM odev WHERE kume_id=? ORDER BY id",
            (int(kume_id),)
        ).fetchall()

        done_words = {"tamam", "bitti", "yapıldı", "yapildi", "done", "complete", "ok"}
        bullets = []
        for r in rows:
            if sadece_yapilmayan:
                s = (r["durum"] or "").strip().lower()
                if any(w in s for w in done_words) or s == "1":
                    continue

            ders = (r["ders"] or "").strip()
            kitap = (r["kitap_ad"] or "").strip()
            konu = (r["konu_ad"] or "").strip()

            # Boş olmayan parçaları sırayla birleştir → "ders / kitap / konu"
            parts = [p for p in (ders, kitap, konu) if p]
            if parts:
                bullets.append("• " + " / ".join(parts))

        return bullets

    def _mesaj_olustur_ogr_wa(self, ogrenci_id: int, mode: str, template: str) -> str:
        """
        mode: today | overdue | never | partial
        {ozet} yerini doldurur. Dolduramazsa {ozet} yazısını tamamen çıkarır.
        """
        con = db.get_conn()
        ozet_satirlari = []

        def _kumeler_for_mode():
            if mode == "never":  # bugün randevusu olup hiç gelmeyen
                return self._wa_today_noshow_kumeler(ogrenci_id)
            elif mode == "today":
                return self._kume_idleri_due(ogrenci_id, "today") or []
            elif mode == "overdue":
                return self._kume_idleri_due(ogrenci_id, "overdue") or []
            else:  # partial → görünen ilk küme
                k = self._first_kume_for_student_in_view(ogrenci_id)
                return [k] if k else []

        kumeler = _kumeler_for_mode()
        idx = 1
        for kid in kumeler:
            bullets = self._wa_kume_ozet(kid, sadece_yapilmayan=(mode in {"never", "overdue"}))
            if not bullets:
                continue
            # Küme başlığı (tarih aralığı varsa ekleyelim)
            try:
                r = con.execute("SELECT verilis_tarihi, bitis_tarihi FROM odev_kume WHERE id=?",
                                (kid,)).fetchone()
                tarih_kisim = ""
                if r and (r["verilis_tarihi"] or r["bitis_tarihi"]):
                    v = (r["verilis_tarihi"] or "").split(" ")[0]
                    b = (r["bitis_tarihi"] or "").split(" ")[0]
                    if v or b:
                        tarih_kisim = f" — Küme #{idx} • {v} → {b}"
                if tarih_kisim:
                    ozet_satirlari.append(tarih_kisim)
            except Exception:
                pass
            ozet_satirlari.extend(bullets)
            idx += 1

        # Şablonu doldur
        ozet = "\n".join(ozet_satirlari).strip()
        msg = template
        if "{ozet}" in msg:
            msg = msg.replace("{ozet}", ozet) if ozet else msg.replace("{ozet}", "").rstrip()
        # Başta/sonda gereksiz çizgi-kolon kalırsa temizle
        msg = msg.replace(":\n\n", ":\n").replace(":\n—", ":\n—").strip()
        return msg


    from utils import whatsapp  # ← senin çalışan dosyan
    def _send_from_whatsapp_batch(self, dlg):
        from utils import whatsapp as wa
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QMessageBox

        T = dlg.tbl
        # QTextEdit olduğu için toPlainText() kullanıyoruz
        try:
            template = dlg.edtTemplate.toPlainText().strip()
        except AttributeError:
            # Fallback: eğer bir şekilde QLineEdit kalırsa
            template = dlg.edtTemplate.text().strip()

        if not template:
            template = dlg._msg_template

        ok = fail = 0
        for r in range(T.rowCount()):
            send_w = T.cellWidget(r, 0)
            if not (send_w and hasattr(send_w, "chk") and send_w.chk.isChecked()):
                continue

            oid_item = T.item(r, 1)
            oid = oid_item.data(Qt.ItemDataRole.UserRole) if oid_item else None
            if not oid:
                continue
            oid = int(oid)

            # 1) mesajı oluştur (eski mantık)
            try:
                msg = self._mesaj_olustur_ogr_wa(oid, dlg._wa_mode, template)
            except Exception:
                msg = ""

            # 1.b) BOŞSA güvenli fallback (özellikle 'never' modu için)
            if not msg or not msg.strip():
                if dlg._wa_mode == "never":
                    msg = ("Merhaba, bugün randevunuz vardı; henüz gelmediniz. "
                           "Lütfen aşağıdaki çalışmaları tamamlayınız: {ozet}")
                elif dlg._wa_mode == "congratulate":
                     msg = ("Harikasın! 🌟 Bu haftaki ödevlerini eksiksiz tamamladığın için tebrik ederim. "
                            "Başarılarının devamını dilerim! 👏\n\n- {ozet}")
                else:
                    msg = "Merhaba, lütfen çalışmalarınızı tamamlayınız: {ozet}"

            # 1.c) 🔥 BURADA ÖĞRENCİ BİLGİLERİNİ YERLEŞTİRİYORUZ
            try:
                adsoyad = (self._ogrenci_adsoyad(oid) or "").strip()
            except Exception:
                adsoyad = ""

            parts = adsoyad.split()
            if parts:
                ad = parts[0]
                soyad = " ".join(parts[1:]) if len(parts) > 1 else ""
            else:
                ad = ""
                soyad = ""

            # {ad} artık AD + SOYAD olsun:
            if ad and soyad:
                ad_full = f"{ad} {soyad}".upper()  # ← TAMAMI BÜYÜK HARF
            else:
                ad_full = (ad or adsoyad).upper()

            rep = {
                "{ad}": ad_full,  # ← BURASI ÖNEMLİ
                "{soyad}": soyad,
                "{ogrenci_ad}": ad,
                "{ogrenci_soyad}": soyad,
                "{ogrenci}": adsoyad,
                "{ogrenci_adsoyad}": adsoyad,
            }
            for k, v in rep.items():
                msg = msg.replace(k, v)

            # 2) SEÇİLİ her numaraya ayrı ayrı gönder
            for col in (3, 4, 5):
                cell = T.cellWidget(r, col)
                if cell and getattr(cell, "cb", None) and cell.cb.isChecked():
                    n = (cell.edit.text() or "").strip()
                    if not n:
                        continue
                    res = wa.whatsapp_gonder([n], msg, ogrenci_id=oid)
                    if res.get("gonderilen", 0) >= 1:
                        ok += 1
                    else:
                        fail += 1

        QMessageBox.information(self, "WhatsApp", f"Gönderilen: {ok}\nBaşarısız: {fail}")


    # f--


    def _load_randevular_with_filters(self):
        """
        İçerik seçeneklerindeki checkbox'lara göre randevu listesini filtreler
        ve tabloya (ör: self.tblRandevu) doldurur.
        """
        con = self.con  # Zaten randevu_takvimi'nde kullandığın bağlantı
        kontrol_col = _randevu_kontrol_kolon(con)

        conds = []

        # --- BURASI mail_send_whatsapp.py'deki ile AYNI MANTIK ---
        # self.chkKontrolBugun, self.chkKontrolYarin, self.chkKontrol2Gun,
        # self.chkKontrolGecmis gibi checkbox isimlerini mail_send_whatsapp.py'dekiyle
        # birebir aynı kullanırsan, direkt çalışır.

        if self.chkKontrolBugun.isChecked():
            conds.append(f"date({kontrol_col}, 'localtime') = date('now','localtime')")

        if self.chkKontrolYarin.isChecked():
            conds.append(f"date({kontrol_col}, 'localtime') = date('now','localtime','+1 day')")

        if self.chkKontrol2Gun.isChecked():
            conds.append(f"date({kontrol_col}, 'localtime') = date('now','localtime','+2 day')")

        if self.chkKontrolGecmis.isChecked():
            conds.append(f"date({kontrol_col}, 'localtime') < date('now','localtime')")

        # Hiç filtre seçili değilse: tüm randevuları getir
        where_extra = ""
        if conds:
            where_extra = " AND (" + " OR ".join(conds) + ")"

        # Default order clause if not specified elsewhere
        order_clause = f"date(r.{kontrol_col}) ASC, r.id ASC"

        sql = f"""
            SELECT
                r.id,
                r.ogrenci_id,
                (o.ad || ' ' || o.soyad) as ogrenci_adsoyad,
                r.{kontrol_col} as kontrol_tarihi,
                r.aciklama,
                r.ders,
                r.konu,
                o.id as ogr_id,
                o.ad,
                o.soyad,
                ok.bitis_tarihi as bitis,
                o.soyad,
                ok.bitis_tarihi as bitis,
                ok.id as kume_id
            FROM randevu r
            LEFT JOIN ogrenci o ON r.ogrenci_id = o.id
            LEFT JOIN odev_kume ok ON ok.ogrenci_id = o.id 
                 AND ok.bitis_tarihi = (SELECT MAX(bitis_tarihi) FROM odev_kume WHERE ogrenci_id=o.id)
            WHERE 1=1
            {where_extra}
            ORDER BY {order_clause}
        """

        rows = con.execute(sql).fetchall()
        
        # --- Pill Delegate Initialization (Modern Kalan Column) ---
        if not hasattr(self, "_pill_delegate"):
            from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
            from PyQt6.QtGui import QColor, QPainterPath, QBrush
            from PyQt6.QtCore import QRectF

            class PillDelegate(QStyledItemDelegate):
                def paint(self, painter, option, index):
                    painter.save()
                    # Arka planı temizle (seçim varsa koru)
                    if option.state & QStyle.StateFlag.State_Selected:
                        painter.fillRect(option.rect, option.palette.highlight())
                    else:
                        painter.fillRect(option.rect, QColor("white")) # Temiz zemin

                    text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
                    
                    # Renk belirle
                    bg = QColor("#f1f5f9") # Gri (default)
                    fg = QColor("#475569")
                    
                    lower = text.lower()
                    if "tamam" in lower or "bitti" in lower:
                        bg = QColor("#dcfce7") # Yeşil
                        fg = QColor("#15803d")
                    elif "bugün" in lower:
                        bg = QColor("#ffedd5") # Turuncu
                        fg = QColor("#c2410c")
                    elif "gecik" in lower or ("-" not in text and "g" in lower and "tamam" not in lower): 
                        # Pozitif gün sayısı ve tamam değilse -> gecikmiş (muhtemelen)
                        # Not: Mevcut mantıkta "-45 g" = 45 gün kaldı (gelecek). "45 g" = gecikti?
                        # Kontrol edelim: "Kalan" sütunu genelde (target - now).days. 
                        # Gelecek ise > 0 olmalı?
                        # Kullanıcı ekranında "-49 g" sarı görünüyor. Demek ki negatif = gecikmiş?
                        # Hayır, "2025-11-05" bitiş. Bugün "2024-12-24". Yaklaşık 11 ay var.
                        # Neden -49g ? 
                        # Belki (now - target) = negatif (today < target).
                        # Neyse, renklere göre davranalım.
                        pass
                        
                    # İkon/Durum analizi ile renk:
                    # Hücrenin orijinal background'una bakabiliriz (daha güvenli)
                    orig_bg = index.data(Qt.ItemDataRole.BackgroundRole)
                    if isinstance(orig_bg, QColor):
                        if orig_bg.name() == "#e8f5e9": # Yeşil
                             bg, fg = QColor("#dcfce7"), QColor("#15803d")
                        elif orig_bg.name() == "#ffcdd2" or orig_bg.name() == "#ffebee": # Kırmızı
                             bg, fg = QColor("#fee2e2"), QColor("#b91c1c")
                        elif orig_bg.name() == "#fff9c4": # Sarı
                             bg, fg = QColor("#fef3c7"), QColor("#b45309")

                    # Kapsül Çiz
                    rect = QRectF(option.rect).adjusted(6, 6, -6, -6)
                    path = QPainterPath()
                    path.addRoundedRect(rect, 6, 6)
                    painter.fillPath(path, bg)
                    
                    # Metin Çiz
                    painter.setPen(fg)
                    painter.setFont(option.font)
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
                    painter.restore()

            self._pill_delegate = PillDelegate(self.tblRandevu)
            # Kolon 3 ("Kalan") varsayımıyla:
            self.tblRandevu.setItemDelegateForColumn(3, self._pill_delegate)

        # --- Badge Logic Hazırlık ---
        from datetime import datetime
        today_tag = datetime.now().strftime("[%d-%m") # Örn: "[24-12"
        try:
            c2 = con.execute("SELECT ogrenci_id FROM odev_kume WHERE aciklama LIKE ?", (f"%{today_tag}%",))
            note_oids = {row[0] for row in c2.fetchall()}
        except Exception:
            note_oids = set()
            
        # Memory Cache Merge
        if hasattr(self, "_today_badges"):
            note_oids.update(self._today_badges)

        # --- Tabloyu doldur ---
        self.tblRandevu.setRowCount(0)
        for r in rows:
            i = self.tblRandevu.rowCount()
            self.tblRandevu.insertRow(i)

            # 0: id
            it_id = QTableWidgetItem(str(r["id"]))
            self.tblRandevu.setItem(i, 0, it_id)

            # 1: öğrenci ad soyad
            ad_soyad = r["ogrenci_adsoyad"] or f"Öğrenci ID: {r['ogrenci_id']}"
            it_ogr = QTableWidgetItem(ad_soyad)
            it_ogr.setData(Qt.ItemDataRole.UserRole, r["ogrenci_id"]) 
            
            # Badge Logic (Kesin Çözüm - int cast)
            if int(r["ogrenci_id"] or 0) in note_oids:
                it_ogr.setText(f"{ad_soyad} 📝")
                it_ogr.setToolTip(f"Bugün ({today_tag}...) tarihli not bulundu.")
            
            self.tblRandevu.setItem(i, 1, it_ogr)

            # 2: kontrol tarihi
            it_kontrol = QTableWidgetItem(str(r["kontrol_tarihi"] or ""))
            self.tblRandevu.setItem(i, 2, it_kontrol)

            # 3: ders
            it_ders = QTableWidgetItem(r["ders"] or "")
            self.tblRandevu.setItem(i, 3, it_ders)

            # 4: konu / açıklama
            it_konu = QTableWidgetItem(r["konu"] or r["aciklama"] or "")
            self.tblRandevu.setItem(i, 4, it_konu)

            self.tblRandevu.setRowHeight(i, 24)

        self.tblRandevu.clearSelection()

    import datetime as _dt
    import sqlite3
    from typing import List, Optional





#s------ diyalog sınıfını ekle (dosyanın sonuna koyabilirsin). Numara seçimleri, şablon, ve gönderim akışı tek yerde
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QLineEdit, QTextEdit, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QPushButton, QWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt

class SingleStudentWhatsAppDialog(QDialog):
    """
    Seçili öğrenci için zenginleştirilmiş, kişiselleştirilmiş ve düzenlenebilir WhatsApp bildirim paneli.
    """
    def __init__(self, parent, student_id: int, student_name: str, kume_id: int, bitis: str, kalan: str, durum: str, hw_items: list, phones: list):
        super().__init__(parent)
        self.student_id = student_id
        self.student_name = student_name
        self.kume_id = kume_id
        self.bitis = bitis
        self.kalan = kalan
        self.durum = durum
        self.hw_items = hw_items
        self.phones = phones

        self.setWindowTitle(f"📱 WhatsApp Bildirimi — {student_name}")
        self.resize(560, 620)
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QLabel { color: #1e293b; }
        """)
        self._init_ui()

    def _init_ui(self):
        from PyQt6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox, 
            QPlainTextEdit, QPushButton, QMessageBox, QLineEdit, QApplication
        )
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QDesktopServices
        import urllib.parse

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        # 1. Başlık Kartı
        card = QFrame()
        card.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px;")
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(4)

        lbl_n = QLabel(f"👤 {self.student_name}")
        lbl_n.setStyleSheet("font-size: 16px; font-weight: 800; color: #1e3a8a;")
        
        info_txt = f"📦 Küme #{self.kume_id} • 🗓️ Teslim: {self.bitis} ({self.kalan}) • Durum: {self.durum}"
        lbl_i = QLabel(info_txt)
        lbl_i.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600;")
        
        c_lay.addWidget(lbl_n)
        c_lay.addWidget(lbl_i)
        lay.addWidget(card)

        # 2. Telefon Seçimi
        lbl_tel_h = QLabel("<b>📞 Gönderilecek Telefon Numarası:</b>")
        lbl_tel_h.setStyleSheet("font-size: 12px;")
        lay.addWidget(lbl_tel_h)

        h_tel = QHBoxLayout()
        self.cmb_phones = QComboBox()
        self.cmb_phones.setStyleSheet("padding: 7px; border: 1.5px solid #cbd5e1; border-radius: 6px; font-weight: 600; background: white;")
        
        for lbl, num in self.phones:
            self.cmb_phones.addItem(f"{lbl}: {num}", num)
            
        self.cmb_phones.addItem("✏️ Farklı / Manuel Numara Gir...", "custom")
        h_tel.addWidget(self.cmb_phones, 1)

        self.inp_custom_phone = QLineEdit()
        self.inp_custom_phone.setPlaceholderText("05xxxxxxxxx")
        self.inp_custom_phone.setStyleSheet("padding: 7px; border: 1.5px solid #cbd5e1; border-radius: 6px; background: white;")
        self.inp_custom_phone.setVisible(False)
        h_tel.addWidget(self.inp_custom_phone, 1)

        def on_phone_combo_changed(idx):
            is_custom = self.cmb_phones.currentData() == "custom"
            self.inp_custom_phone.setVisible(is_custom)
            
        self.cmb_phones.currentIndexChanged.connect(on_phone_combo_changed)
        lay.addLayout(h_tel)

        # 3. Mesaj Düzenleme Alanı
        lbl_msg_h = QLabel("<b>💬 İletilecek WhatsApp Mesajı (İstediğiniz gibi düzenleyebilirsiniz):</b>")
        lbl_msg_h.setStyleSheet("font-size: 12px;")
        lay.addWidget(lbl_msg_h)

        # Ödev maddelerini oluştur
        hw_bullets = []
        for hw in self.hw_items:
            ders = hw["ders"] or ""
            kitap = hw["kitap_ad"] or ""
            konu = hw["konu_ad"] or ""
            durum = hw["durum"] or "Bekliyor"
            
            part = f"• {ders}"
            if konu: part += f" / {konu}"
            if kitap: part += f" ({kitap})"
            part += f" [Durum: {durum}]"
            hw_bullets.append(part)
            
        hw_text = "\n".join(hw_bullets) if hw_bullets else "• Aktif bekleyen ödev kaydı bulunmuyor."

        default_msg = (
            f"👋 Merhaba değerli öğrencim {self.student_name},\n\n"
            f"🗓️ *Ödev & Randevu Takip Bildirimi*\n"
            f"📌 Teslim / Kontrol Tarihi: {self.bitis} ({self.kalan})\n"
            f"📦 Küme Durumu: {self.durum}\n\n"
            f"📚 *Sana Atanan Çalışma ve Ödevler:*\n"
            f"{hw_text}\n\n"
            f"🎯 *Eğitim Koçu Notu:*\n"
            f"Planına sadık kalarak çalışmalarını zamanında tamamlamanı bekliyorum. "
            f"Yapamadığın veya takıldığın soruları mutlaka işaretle, seansta birlikte analiz edeceğiz. Başarılar dilerim! 🚀💪✨"
        )

        self.txt_message = QPlainTextEdit()
        self.txt_message.setPlainText(default_msg)
        self.txt_message.setStyleSheet("""
            QPlainTextEdit {
                background: white;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                color: #1e293b;
                line-height: 1.4;
            }
        """)
        lay.addWidget(self.txt_message, 1)

        # 4. Alt Butonlar
        h_btn = QHBoxLayout()
        h_btn.setSpacing(10)

        btn_copy = QPushButton("📋 Mesajı Kopyala")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 14px; font-weight: bold; color: #475569;")
        def do_copy():
            QApplication.clipboard().setText(self.txt_message.toPlainText())
            QMessageBox.information(self, "Kopyalandı", "WhatsApp mesaj metni panoya kopyalandı! ✅")
        btn_copy.clicked.connect(do_copy)
        h_btn.addWidget(btn_copy)

        h_btn.addStretch(1)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 14px; font-weight: bold; color: #64748b;")
        btn_cancel.clicked.connect(self.reject)
        h_btn.addWidget(btn_cancel)

        btn_send = QPushButton("🚀 WhatsApp ile Gönder")
        btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send.setStyleSheet("""
            QPushButton {
                background-color: #16a34a;
                color: white;
                font-weight: 800;
                font-size: 12.5px;
                border-radius: 6px;
                padding: 8px 18px;
                border: none;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        def do_send():
            raw_phone = self.inp_custom_phone.text().strip() if self.cmb_phones.currentData() == "custom" else self.cmb_phones.currentData()
            clean_digits = "".join(filter(str.isdigit, str(raw_phone or "")))
            if not clean_digits or len(clean_digits) < 10:
                QMessageBox.warning(self, "Geçersiz Telefon", "Lütfen geçerli bir telefon numarası seçin veya girin.")
                return
            if len(clean_digits) == 10 and clean_digits.startswith("5"):
                target_num = "90" + clean_digits
            elif len(clean_digits) == 11 and clean_digits.startswith("05"):
                target_num = "90" + clean_digits[1:]
            else:
                target_num = clean_digits

            msg_text = self.txt_message.toPlainText().strip()
            if not msg_text:
                QMessageBox.warning(self, "Boş Mesaj", "Lütfen gönderilecek bir mesaj yazınız.")
                return

            sent_ok = False
            try:
                from utils import whatsapp
                r = whatsapp.whatsapp_gonder([f"+{target_num}"], msg_text, ogrenci_id=self.student_id)
                sent_ok = True
            except Exception as e:
                # Fallback: web/app URL aç
                url_encoded = urllib.parse.quote(msg_text)
                wa_url = f"https://web.whatsapp.com/send?phone={target_num}&text={url_encoded}"
                QDesktopServices.openUrl(QUrl(wa_url))
                sent_ok = True

            QMessageBox.information(self, "Gönderildi", f"WhatsApp bildirimi başarıyla iletildi:\n\nAlıcı: +{target_num}\nÖğrenci: {self.student_name}")
            self.accept()

        btn_send.clicked.connect(do_send)
        h_btn.addWidget(btn_send)

        lay.addLayout(h_btn)


class _WhatsAppBatchDialog(QDialog):
    """
    Modernize edilmiş WhatsApp toplu gönderim diyaloğu.
    Kontrolcü (RandevuTakvimi) buradaki 'tbl', 'btnSend', 'edtTemplate' gibi
    alanlara eriştiği için isimleri KORUNMUŞTUR.
    """
    def __init__(self, parent, title, rows):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1100, 750)
        self.setStyleSheet("background-color: #f8fafc;")

        self._parent = parent
        self._rows = rows              # [(oid, ad, durum, nums), ...]
        self._wa_mode = "today"        # dışarıdan set
        self._msg_template = ""        # dışarıdan set

        # --- Ana Layout ---
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # 1. HEADER (Mavi Şerit)
        header = QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e2e8f0;")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(25, 0, 25, 0)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1e293b;")
        
        lbl_info = QLabel("Gönderim öncesi listeyi ve mesajı kontrol ediniz.")
        lbl_info.setStyleSheet("color: #64748b; font-size: 13px;")

        h_lay.addWidget(lbl_title)
        h_lay.addStretch(1)
        h_lay.addWidget(lbl_info)
        
        main.addWidget(header)

        # 2. CONTENT (Tablo + Sağ Panel)
        content_box = QWidget()
        c_lay = QHBoxLayout(content_box)
        c_lay.setContentsMargins(25, 25, 25, 25)
        c_lay.setSpacing(25)

        # A) SOL PANEL: TABLO
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        
        # Tablo üstü araç çubuğu
        tools = QHBoxLayout()
        self.btnAll = QPushButton("Tümünü Seç")
        self.btnNone = QPushButton("Seçimi Kaldır")
        
        for b in (self.btnAll, self.btnNone):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton { background: #e2e8f0; border: none; padding: 5px 12px; border-radius: 6px; color: #475569; font-weight: 600; font-size: 12px; }
                QPushButton:hover { background: #cbd5e1; }
            """)
        
        tools.addWidget(self.btnAll)
        tools.addWidget(self.btnNone)
        tools.addStretch(1)
        left_panel.addLayout(tools)

        # Tablo
        self.tbl = QTableWidget(0, 7, self)
        self.tbl.setHorizontalHeaderLabels([
            "Seç", "Öğrenci", "Durum", "Veli-1", "Veli-2", "Ogr. Tel", "İzle"
        ])
        
        # Kolon Ayarları (Hata düzeltmesi: Her kolon eşit olmasın)
        header = self.tbl.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed) # Seç
        self.tbl.setColumnWidth(0, 50)
        
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Öğrenci (Esnek)
        
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Durum
        
        # Telefonlar
        for c in (3, 4, 5):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.tbl.setColumnWidth(c, 130)

        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed) # Önizleme
        self.tbl.setColumnWidth(6, 50)

        self.tbl.setObjectName("tblWa")
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setShowGrid(False)  # Grid yerine zebra
        self.tblWa = self.tbl 
        
        # Tablo Stili
        self.tbl.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: transparent;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #475569;
                padding: 12px;
                border: none;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:selected {
                background-color: #eff6ff;
                color: #1e3a8a;
            }
            QLineEdit {
                background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px;
            }
            QLineEdit:focus { border: 1px solid #3b82f6; background: #fff; }
        """)
        
        left_panel.addWidget(self.tbl)
        c_lay.addLayout(left_panel, stretch=2)

        # B) SAĞ PANEL: MESAJ & PREVIEW
        right_panel = QVBoxLayout()
        right_panel.setSpacing(20)

        # B1. Mesaj Editörü Kutu
        msg_frame = QWidget()
        msg_frame.setStyleSheet("#msgFrame { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }")
        msg_frame.setObjectName("msgFrame")
        mf_lay = QVBoxLayout(msg_frame)
        mf_lay.setContentsMargins(15, 15, 15, 15)

        mf_lay.addWidget(QLabel("📝 Mesaj Şablonu"))
        
        # MODERNIZASYON: QLineEdit -> QTextEdit
        from PyQt6.QtWidgets import QTextEdit
        self.edtTemplate = QTextEdit(self)
        self.edtTemplate.setPlaceholderText("Mesaj şablonunuzu buraya yazın...")
        self.edtTemplate.setFixedHeight(120) # Rahat yükseklik
        self.edtTemplate.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e2e8f0; border-radius: 8px; padding: 10px; font-size: 14px; background: #f8fafc;
            }
            QTextEdit:focus { border-color: #3b82f6; background: #ffffff; }
        """)
        mf_lay.addWidget(self.edtTemplate)
        
        lbl_hint = QLabel("İpuçları: {ad}, {soyad}, {ozet} değişkenlerini kullanabilirsiniz.")
        lbl_hint.setStyleSheet("color: #94a3b8; font-size: 11px; margin-top: 5px;")
        mf_lay.addWidget(lbl_hint)
        
        right_panel.addWidget(msg_frame)

        # B2. Önizleme Kartı (WhatsApp Bubble gibi)
        preview_frame = QWidget()
        preview_frame.setStyleSheet("""
            QWidget { background-color: #dcf8c6; border-radius: 12px; border: 1px solid #cfebd0; }
        """)
        pf_lay = QVBoxLayout(preview_frame)
        pf_lay.setContentsMargins(15, 15, 15, 15)
        
        pf_lay.addWidget(QLabel("👁️ Önizleme"))
        self.txtPreview = QLabel("Mesajınız burada görünecek...")
        self.txtPreview.setWordWrap(True)
        self.txtPreview.setStyleSheet("font-size: 13px; color: #111b21; line-height: 1.4;")
        pf_lay.addWidget(self.txtPreview)
        pf_lay.addStretch()
        
        right_panel.addWidget(preview_frame)
        right_panel.addStretch()

        c_lay.addLayout(right_panel, stretch=1)
        main.addWidget(content_box)

        # 3. FOOTER (Action Bar)
        footer = QWidget()
        footer.setFixedHeight(80)
        footer.setStyleSheet("background-color: #ffffff; border-top: 1px solid #e2e8f0;")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(25, 0, 25, 0)
        
        # Excel Butonu
        self.btnExport = QPushButton("Excel'e Kaydet")
        self.btnExport.setFlat(True)
        self.btnExport.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnExport.setStyleSheet("color: #059669; font-weight: 600; font-size: 14px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 8px 16px; background: #ecfdf5;")

        # Kapat Butonu
        self.btnClose = QPushButton("Vazgeç")
        self.btnClose.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnClose.setStyleSheet("""
            QPushButton { background: transparent; color: #64748b; font-weight: 600; font-size: 14px; padding: 8px 16px; }
            QPushButton:hover { color: #334155; }
        """)

        # Gönder Butonu (Primary)
        self.btnSend = QPushButton("WhatsApp ile Gönder 🚀")
        self.btnSend.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnSend.setFixedHeight(44)
        self.btnSend.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
                color: white; font-weight: bold; font-size: 15px; border-radius: 8px; padding: 0 24px; border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:pressed { background: #1e40af; }
        """)

        f_lay.addWidget(self.btnExport)
        f_lay.addStretch(1)
        f_lay.addWidget(self.btnClose)
        f_lay.addSpacing(10)
        f_lay.addWidget(self.btnSend)

        main.addWidget(footer)

        # --- Sinyaller ---
        self.btnAll.clicked.connect(self._check_all)
        self.btnNone.clicked.connect(self._uncheck_all)
        self.btnClose.clicked.connect(self.reject)
        
        # Canlı önizleme için (basit bir bağlantı, textChanged'e bağlayalım)
        self.edtTemplate.textChanged.connect(self._update_preview)

        self._fill_table()

    def _fill_table(self):
        from PyQt6.QtGui import QFont  # <-- EKLENDİ
        self.tbl.setRowCount(0)
        for (oid, ad, durum, nums) in self._rows:
            i = self.tbl.rowCount()
            self.tbl.insertRow(i)

            # 0) GÖNDER (Checkbox ortalanmış)
            send_w = QWidget()
            sw_lay = QHBoxLayout(send_w)
            sw_lay.setContentsMargins(0, 0, 0, 0)
            sw_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            send_w.chk = QCheckBox()
            send_w.chk.setChecked(True)
            sw_lay.addWidget(send_w.chk)
            self.tbl.setCellWidget(i, 0, send_w)

            # 1) Öğrenci
            it0 = QTableWidgetItem(ad)
            it0.setData(Qt.ItemDataRole.UserRole, int(oid))
            it0.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tbl.setItem(i, 1, it0)

            # 2) Durum
            self.tbl.setItem(i, 2, QTableWidgetItem(durum or ""))

            # 3-4-5) Numara hücreleri (cb + edit)
            for col, key in [(3, "veli1"), (4, "veli2"), (5, "ogr")]:
                sub = QWidget()
                h = QHBoxLayout(sub)
                h.setContentsMargins(4, 2, 4, 2)
                h.setSpacing(6)
                
                cb = QCheckBox()
                cb.setChecked(bool(nums.get(key)))
                
                edit = QLineEdit(nums.get(key, ""))
                edit.setPlaceholderText("—")
                # Edit stil (yukarıda genel verildi ama buraya özel ufak ayar yapılabilir)
                
                sub.cb = cb
                sub.edit = edit
                h.addWidget(cb)
                h.addWidget(edit)
                self.tbl.setCellWidget(i, col, sub)

            # 6) Önizleme (ikon)
            self.tbl.setItem(i, 6, QTableWidgetItem("👁️"))

    def _check_all(self):
        for r in range(self.tbl.rowCount()):
            w = self.tbl.cellWidget(r, 0)
            if hasattr(w, "chk"):
                w.chk.setChecked(True)

    def _uncheck_all(self):
        for r in range(self.tbl.rowCount()):
            w = self.tbl.cellWidget(r, 0)
            if hasattr(w, "chk"):
                w.chk.setChecked(False)

    def _update_preview(self):
        # Basit bir önizleme güncellemesi
        try:
            txt = self.edtTemplate.toPlainText()
        except AttributeError:
            txt = self.edtTemplate.text()
            
        if not txt:
            self.txtPreview.setText("Mesaj şablonu boş.")
            return
        # Örnek bir isimle doldur
        sample = txt.replace("{ad}", "Ahmet").replace("{soyad}", "Yılmaz").replace("{ozet}", "• Matematik\n• Fizik")
        self.txtPreview.setText(sample)


#f ----



# ---- küçük yardımcı widget (chip görünümü) ----
from PyQt6.QtWidgets import QWidget, QHBoxLayout
class QHBoxLayoutWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Chip")
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(10, 6, 10, 6)
        self.lay.setSpacing(8)
        from PyQt6.QtWidgets import QLabel
        self.lbl = QLabel("Etiket")
        self.lbl.setObjectName("ChipLabel")
        self.lay.addWidget(self.lbl)

