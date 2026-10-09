# -*- coding: utf-8 -*-
from __future__ import annotations
import datetime
import sqlite3
import urllib.parse
import webbrowser
import subprocess
import sys
import os
import html
from typing import Any, Dict, List, Tuple, Optional

from PyQt6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QTextBrowser, QProgressBar, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QFrame, QLineEdit, QComboBox, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox
)
from PyQt6.QtGui import QTextDocument, QFont, QColor, QCursor
from PyQt6.QtCore import QSizeF, QTimer, Qt
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

import db


def _ensure_schema(con: sqlite3.Connection):
    """
    ogrenci tablosunda kocluk_gunu, kocluk_saati ve hedef kolonlarının
    varlığını her durumda garanti eder (Self-healing).
    """
    try:
        cur = con.cursor()
        cur.execute("PRAGMA table_info(ogrenci)")
        cols = {info[1] for info in cur.fetchall()}
        needed = [
            ("kocluk_gunu", "TEXT"),
            ("kocluk_saati", "TEXT"),
            ("hedef_bolum", "TEXT"),
            ("hedef_tyt", "REAL"),
            ("hedef_ayt", "REAL"),
            ("hedef_lgs", "REAL"),
        ]
        added = False
        for col_name, col_type in needed:
            if col_name not in cols:
                try:
                    cur.execute(f"ALTER TABLE ogrenci ADD COLUMN {col_name} {col_type}")
                    added = True
                except Exception:
                    pass
        if added:
            con.commit()
    except Exception as e:
        print(f"[MobileSchedule] Schema verification notice: {e}")


# =========================================================================
# 1. AKILLI PDF AJANDA ÖNİZLEME VE BASKI DİYALOĞU (OPTION 1)
# =========================================================================
class SmartMobileSchedulePreviewDialog(QDialog):
    """
    Haftalık mobil ajandayı zengin HTML formatında önizler,
    filtreler (Tümü, YKS, LGS), PDF olarak dışa aktarır veya yazdırır.
    """
    def __init__(self, parent, schedule_generator: 'MobileScheduleGenerator'):
        super().__init__(parent)
        self.generator = schedule_generator
        self.setWindowTitle("📱 Akıllı Mobil Cep Ajandası - Önizleme & Baskı")
        self.resize(1000, 780)
        self._current_html = ""
        self._setup_ui()
        self._refresh_preview()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header Banner
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #1e40af);
                border-radius: 10px;
                padding: 12px 18px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 8, 10, 8)

        lbl_title = QLabel("📱 Haftalık Akıllı Mobil Ajanda")
        lbl_title.setStyleSheet("color: white; font-size: 20px; font-weight: 800; background: transparent;")
        lbl_sub = QLabel("Ödev teslim saatleri, koçluk görüşmeleri ve durum analizleri")
        lbl_sub.setStyleSheet("color: #bfdbfe; font-size: 13px; background: transparent;")
        
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        h_layout.addLayout(v_title)
        h_layout.addStretch()

        main_layout.addWidget(header)

        # Toolbar Filters
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        lbl_filter = QLabel("🎯 Hedef Grup:")
        lbl_filter.setStyleSheet("font-weight: bold; color: #334155; font-size: 13px;")
        toolbar.addWidget(lbl_filter)

        self.cbx_group = QComboBox()
        self.cbx_group.addItems(["Tümü", "YKS", "LGS", "Ara Sınıf"])
        self.cbx_group.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 12px;
                background: white; font-weight: bold; color: #1e293b; min-width: 110px;
            }
            QComboBox::drop-down { background: transparent; border: none; }
        """)
        self.cbx_group.currentTextChanged.connect(self._refresh_preview)
        toolbar.addWidget(self.cbx_group)

        self.chk_all_students = QCheckBox("Tüm Aktif Öğrencileri Göster (Haftalık Karneli)")
        self.chk_all_students.setStyleSheet("font-size: 13px; font-weight: 600; color: #475569; margin-left: 10px;")
        self.chk_all_students.stateChanged.connect(self._refresh_preview)
        toolbar.addWidget(self.chk_all_students)

        toolbar.addStretch()

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;
                padding: 6px 14px; font-weight: bold; color: #334155;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_refresh.clicked.connect(self._refresh_preview)
        toolbar.addWidget(btn_refresh)

        main_layout.addLayout(toolbar)

        # HTML Viewer
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        self.viewer.setStyleSheet("""
            QTextBrowser {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        main_layout.addWidget(self.viewer, 1)

        # Bottom Actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_browser = QPushButton("🌐 Tarayıcıda Aç (Tam Mobil Deneyim)")
        self.btn_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browser.setStyleSheet("""
            QPushButton {
                background-color: #0891b2; color: white; font-weight: bold; font-size: 13px;
                padding: 10px 18px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #0e7490; }
        """)
        self.btn_browser.clicked.connect(self._open_in_browser)
        btn_layout.addWidget(self.btn_browser)

        self.btn_print = QPushButton("🖨️ Yazdır")
        self.btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_print.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc; color: #334155; font-weight: bold; font-size: 13px;
                padding: 10px 18px; border-radius: 8px; border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_print.clicked.connect(self._print_schedule)
        btn_layout.addWidget(self.btn_print)

        btn_layout.addStretch()

        self.btn_pdf = QPushButton("💾 PDF Olarak Kaydet & Aç")
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; font-weight: bold; font-size: 14px;
                padding: 10px 22px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_pdf.clicked.connect(self._save_pdf)
        btn_layout.addWidget(self.btn_pdf)

        btn_close = QPushButton("Kapat")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0; color: #475569; font-weight: bold; font-size: 13px;
                padding: 10px 16px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #cbd5e1; }
        """)
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        main_layout.addLayout(btn_layout)

    def _refresh_preview(self):
        grp = self.cbx_group.currentText()
        all_st = self.chk_all_students.isChecked()
        schedule, next_7_days = self.generator._fetch_data(group_filter=grp, include_all_active=all_st)
        self._current_html = self.generator._build_html(schedule, next_7_days, for_pdf=False)
        self.viewer.setHtml(self._current_html)

    def _save_pdf(self):
        default_name = f"cep_ajandasi_{datetime.date.today().strftime('%Y_%m_%d')}.pdf"
        fn, _ = QFileDialog.getSaveFileName(self, "PDF Ajanda Kaydet", default_name, "PDF Dosyası (*.pdf)")
        if not fn:
            return
        try:
            grp = self.cbx_group.currentText()
            all_st = self.chk_all_students.isChecked()
            schedule, next_7_days = self.generator._fetch_data(group_filter=grp, include_all_active=all_st)
            pdf_html = self.generator._build_html(schedule, next_7_days, for_pdf=True)
            
            doc = QTextDocument()
            doc.setHtml(pdf_html)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(fn)
            doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size()))
            doc.print(printer)

            QMessageBox.information(self, "Başarılı", f"PDF başarıyla oluşturuldu:\n{fn}")
            self.generator._open_file(fn)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı:\n{e}")

    def _print_schedule(self):
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                doc = QTextDocument()
                doc.setHtml(self._current_html)
                doc.print(printer)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yazdırma hatası:\n{e}")

    def _open_in_browser(self):
        try:
            import tempfile
            tmp_path = os.path.join(tempfile.gettempdir(), f"cep_ajanda_{os.getpid()}.html")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(self._current_html)
            self.generator._open_file(tmp_path)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Tarayıcıda açılamadı:\n{e}")

# =========================================================================
# 2. AKILLI WHATSAPP İLETİŞİM MERKEZİ & ROBOTU (OPTION 2)
# =========================================================================
class SmartBulkMessageDialog(QDialog):
    """
    Tüm öğrenci ve velilere yönelik durum bazlı yapay zeka mesajlarını listeler,
    seçili mesajları canlı düzenlemeye izin verir, tek tek veya otomatik sırayla
    WhatsApp Web/Masaüstü üzerinden gönderir.
    """
    def __init__(self, parent, schedule_generator: 'MobileScheduleGenerator'):
        super().__init__(parent)
        self.generator = schedule_generator
        self.setWindowTitle("🚀 Akıllı WhatsApp İletişim Merkezi & Gönderim Robotu")
        self.resize(1050, 720)
        self.queue: List[Dict[str, Any]] = []
        self.selected_queue: List[Dict[str, Any]] = []
        self.current_sending_idx = 0
        self.is_paused = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._process_next_auto_message)

        self._setup_ui()
        self._load_queue()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # Header Banner
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #047857);
                border-radius: 10px;
                padding: 12px 18px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 8, 10, 8)

        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_title = QLabel("🚀 Akıllı WhatsApp İletişim Merkezi & Robotu")
        lbl_title.setStyleSheet("color: white; font-size: 20px; font-weight: 800; background: transparent;")
        self.lbl_sub = QLabel("Analiz sonuçlarına göre otomatik kişiselleştirilmiş motivasyon ve teslim mesajları")
        self.lbl_sub.setStyleSheet("color: #a7f3d0; font-size: 13px; background: transparent;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(self.lbl_sub)
        h_layout.addLayout(v_title)
        h_layout.addStretch()

        self.lbl_stats_chip = QLabel("Yükleniyor...")
        self.lbl_stats_chip.setStyleSheet("""
            background: rgba(255, 255, 255, 0.15); color: white; font-size: 12px; font-weight: bold;
            padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.25);
        """)
        h_layout.addWidget(self.lbl_stats_chip)

        main_layout.addWidget(header)

        # Filters Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        lbl_scope = QLabel("📋 Kapsam:")
        lbl_scope.setStyleSheet("font-weight: bold; color: #334155;")
        filter_bar.addWidget(lbl_scope)

        self.cbx_scope = QComboBox()
        self.cbx_scope.addItems([
            "📅 Bu Haftaki Teslim ve Randevular (Gelecek 7 Gün)",
            "⚠️ Geciken Ödevi Olanlar (Telafi Hatırlatması)",
            "🌟 Haftanın Yıldızları (Tebrik & Motivasyon)",
            "👥 Tüm Aktif Öğrenciler (Genel Durum Karnesi)"
        ])
        self.cbx_scope.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;
                background: white; font-weight: bold; color: #1e293b; min-width: 260px;
            }
            QComboBox::drop-down { background: transparent; border: none; }
        """)
        self.cbx_scope.currentIndexChanged.connect(self._load_queue)
        filter_bar.addWidget(self.cbx_scope)

        lbl_role = QLabel("👥 Alıcı:")
        lbl_role.setStyleSheet("font-weight: bold; color: #334155; margin-left: 10px;")
        filter_bar.addWidget(lbl_role)

        self.cbx_role = QComboBox()
        self.cbx_role.addItems(["Tümü (Öğrenci + Veli)", "Yalnızca Öğrenciler", "Yalnızca Veliler"])
        self.cbx_role.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;
                background: white; font-weight: bold; color: #1e293b; min-width: 160px;
            }
            QComboBox::drop-down { background: transparent; border: none; }
        """)
        self.cbx_role.currentIndexChanged.connect(self._apply_role_and_search_filter)
        filter_bar.addWidget(self.cbx_role)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 İsim ile filtrele...")
        self.txt_search.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background: white;")
        self.txt_search.textChanged.connect(self._apply_role_and_search_filter)
        filter_bar.addWidget(self.txt_search)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        btn_refresh.clicked.connect(self._load_queue)
        filter_bar.addWidget(btn_refresh)

        main_layout.addLayout(filter_bar)

        # Main Splitter (Left: Table, Right: Message Editor)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left Container
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Batch Selection Buttons
        sel_bar = QHBoxLayout()
        sel_bar.setSpacing(8)
        btn_select_all = QPushButton("Tümünü Seç")
        btn_select_all.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        btn_select_all.clicked.connect(lambda: self._set_all_checked(True))
        sel_bar.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Seçimi Kaldır")
        btn_deselect_all.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        btn_deselect_all.clicked.connect(lambda: self._set_all_checked(False))
        sel_bar.addWidget(btn_deselect_all)

        self.lbl_selected_count = QLabel("Seçili: 0")
        self.lbl_selected_count.setStyleSheet("font-weight: bold; color: #2563eb; font-size: 12px; margin-left: 6px;")
        sel_bar.addWidget(self.lbl_selected_count)
        sel_bar.addStretch()

        left_layout.addLayout(sel_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Seç", "Alıcı", "Rol", "Telefon", "Durum Rozeti", "Durum"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1; border-radius: 6px; background: white;
                gridline-color: #f1f5f9; alternate-background-color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #f1f5f9; font-weight: bold; color: #334155;
                padding: 6px; border: none; border-bottom: 1px solid #cbd5e1;
            }
        """)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        left_layout.addWidget(self.table)

        splitter.addWidget(left_container)

        # Right Container (Editor & Actions)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.lbl_edit_header = QLabel("Seçili Alıcı Mesajı (Düzenlenebilir):")
        self.lbl_edit_header.setStyleSheet("font-weight: bold; color: #1e293b; font-size: 13px;")
        right_layout.addWidget(self.lbl_edit_header)

        self.txt_message = QTextEdit()
        self.txt_message.setStyleSheet("""
            QTextEdit {
                border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;
                background: white; font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 13px; line-height: 1.4;
            }
            QTextEdit:focus { border: 1px solid #10b981; }
        """)
        self.txt_message.textChanged.connect(self._on_message_text_edited)
        right_layout.addWidget(self.txt_message)

        # Single Recipient Action Buttons
        single_act = QHBoxLayout()
        single_act.setSpacing(8)

        self.btn_send_single = QPushButton("🟢 Bu Kişiye WhatsApp'ta Aç")
        self.btn_send_single.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send_single.setStyleSheet("""
            QPushButton {
                background-color: #16a34a; color: white; font-weight: bold; padding: 8px 14px;
                border-radius: 6px; border: none;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        self.btn_send_single.clicked.connect(self._send_single_whatsapp)
        single_act.addWidget(self.btn_send_single)

        self.btn_copy_single = QPushButton("📋 Metni Kopyala")
        self.btn_copy_single.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_single.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9; color: #334155; font-weight: bold; padding: 8px 14px;
                border-radius: 6px; border: 1px solid #cbd5e1;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_copy_single.clicked.connect(self._copy_single_message)
        single_act.addWidget(self.btn_copy_single)

        self.btn_reset_msg = QPushButton("🔄 Varsayılana Dön")
        self.btn_reset_msg.setStyleSheet("font-size: 11px; padding: 6px 10px;")
        self.btn_reset_msg.clicked.connect(self._reset_current_message)
        single_act.addWidget(self.btn_reset_msg)

        right_layout.addLayout(single_act)

        # Automation Log
        self.lbl_log_title = QLabel("Gönderim Günlüğü:")
        self.lbl_log_title.setStyleSheet("font-weight: bold; color: #64748b; font-size: 11px; margin-top: 6px;")
        right_layout.addWidget(self.lbl_log_title)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(120)
        self.txt_log.setStyleSheet("""
            QTextEdit {
                background: #f8fafc; border: 1px solid #e2e8f0; font-family: monospace; font-size: 11px; color: #334155;
            }
        """)
        right_layout.addWidget(self.txt_log)

        splitter.addWidget(right_container)
        splitter.setSizes([580, 420])
        main_layout.addWidget(splitter, 1)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #cbd5e1; border-radius: 6px; height: 16px; text-align: center; }
            QProgressBar::chunk { background-color: #10b981; border-radius: 5px; }
        """)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Bottom Automation Controls
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        lbl_delay = QLabel("⏱️ Aralık:")
        lbl_delay.setStyleSheet("font-weight: bold; color: #475569;")
        bottom_bar.addWidget(lbl_delay)

        self.cbx_delay = QComboBox()
        self.cbx_delay.addItems(["3 Saniye", "5 Saniye", "7 Saniye", "10 Saniye"])
        self.cbx_delay.setCurrentIndex(1)
        self.cbx_delay.setStyleSheet("padding: 6px; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px;")
        bottom_bar.addWidget(self.cbx_delay)

        self.btn_start_auto = QPushButton("🚀 Seçilenleri Otomatik Sırayla Aç")
        self.btn_start_auto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_auto.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; font-weight: bold; font-size: 13px;
                padding: 10px 18px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_start_auto.clicked.connect(self._start_auto_sending)
        bottom_bar.addWidget(self.btn_start_auto)

        self.btn_pause_auto = QPushButton("⏸️ Duraklat")
        self.btn_pause_auto.setEnabled(False)
        self.btn_pause_auto.setStyleSheet("background: #f59e0b; color: white; font-weight: bold; padding: 10px 14px; border-radius: 8px; border: none;")
        self.btn_pause_auto.clicked.connect(self._pause_auto_sending)
        bottom_bar.addWidget(self.btn_pause_auto)

        self.btn_stop_auto = QPushButton("⏹️ Durdur")
        self.btn_stop_auto.setEnabled(False)
        self.btn_stop_auto.setStyleSheet("background: #ef4444; color: white; font-weight: bold; padding: 10px 14px; border-radius: 8px; border: none;")
        self.btn_stop_auto.clicked.connect(self._stop_auto_sending)
        bottom_bar.addWidget(self.btn_stop_auto)

        bottom_bar.addStretch()

        self.btn_copy_all = QPushButton("📋 Tüm Mesajları Toplu Kopyala")
        self.btn_copy_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_all.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; font-weight: bold; padding: 10px 14px; border-radius: 8px;")
        self.btn_copy_all.clicked.connect(self._copy_all_messages)
        bottom_bar.addWidget(self.btn_copy_all)

        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet("background: #e2e8f0; color: #475569; font-weight: bold; padding: 10px 16px; border-radius: 8px; border: none;")
        btn_close.clicked.connect(self._stop_and_close)
        bottom_bar.addWidget(btn_close)

        main_layout.addLayout(bottom_bar)

    def _log(self, text: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt_log.append(f"[{ts}] {text}")
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def _load_queue(self):
        scope_idx = self.cbx_scope.currentIndex()
        con = self.generator.con
        _ensure_schema(con)

        self.queue.clear()
        today = datetime.date.today()
        days_tr = {0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"}

        if scope_idx == 0:
            # Bu haftaki teslim ve randevular
            schedule, next_7_days = self.generator._fetch_data(group_filter="Tümü", include_all_active=False)
            seen_set = set()
            for d_str, day_name in next_7_days:
                events = schedule.get(day_name, [])
                nice_d = f"{d_str.split('-')[2]}.{d_str.split('-')[1]}"
                for ev in events:
                    msg = self.generator._build_msg_single(ev, day_name, nice_d)
                    oid = ev["oid"]
                    # Öğrenci
                    if ev["tel_ogr"] and (oid, "ogr") not in seen_set:
                        seen_set.add((oid, "ogr"))
                        self.queue.append({
                            "oid": oid,
                            "name": ev["ad"],
                            "role": "Öğrenci",
                            "tel": ev["tel_ogr"],
                            "status": ev["meta"].get("status", "normal"),
                            "badge": ev["meta"].get("badge", "📘"),
                            "smart_note": ev["meta"].get("smart_note", ""),
                            "default_msg": msg,
                            "msg": msg,
                            "state": "Bekliyor",
                            "selected": True,
                        })
                    # Veli
                    if ev["tel_veli"] and (oid, "veli") not in seen_set:
                        seen_set.add((oid, "veli"))
                        veli_msg = self.generator._build_parent_msg(ev, day_name, nice_d)
                        self.queue.append({
                            "oid": oid,
                            "name": f"{ev['ad']} (Veli)",
                            "role": "Veli",
                            "tel": ev["tel_veli"],
                            "status": ev["meta"].get("status", "normal"),
                            "badge": ev["meta"].get("badge", "📘"),
                            "smart_note": ev["meta"].get("smart_note", ""),
                            "default_msg": veli_msg,
                            "msg": veli_msg,
                            "state": "Bekliyor",
                            "selected": True,
                        })
        elif scope_idx == 1:
            # Geciken ödevi olanlar
            rows = con.execute("""
                SELECT o.id, o.ad, o.soyad, o.ogr_tel, o.veli_tel1, COUNT(od.id) as late_cnt
                FROM ogrenci o
                JOIN odev od ON od.ogrenci_id = o.id
                JOIN odev_kume k ON k.id = od.kume_id
                WHERE o.aktif=1 AND od.durum='devam' AND date(k.bitis_tarihi) < date('now')
                GROUP BY o.id
                HAVING late_cnt > 0
                ORDER BY late_cnt DESC
            """).fetchall()

            for r in rows:
                full_name = f"{r['ad']} {r['soyad']}"
                late_cnt = r["late_cnt"]
                msg_ogr = f"Merhaba {full_name}, sistemde teslim tarihi geçmiş {late_cnt} adet tamamlanmamış ödevin görünüyor. Lütfen telafilerini en kısa sürede tamamlayıp sisteme işle. Başarılar dilerim! 📚"
                msg_veli = f"Sayın Velimiz, öğrencimiz {full_name}'in teslim tarihi geçmiş {late_cnt} adet tamamlanmamış ödevi bulunmaktadır. Telafi çalışmaları için takibinizi rica ederiz. İyi günler dileriz."
                if r["ogr_tel"]:
                    self.queue.append({
                        "oid": r["id"], "name": full_name, "role": "Öğrenci", "tel": r["ogr_tel"],
                        "status": "risk", "badge": "⚠️", "smart_note": f"{late_cnt} Geciken Ödev",
                        "default_msg": msg_ogr, "msg": msg_ogr, "state": "Bekliyor", "selected": True
                    })
                if r["veli_tel1"]:
                    self.queue.append({
                        "oid": r["id"], "name": f"{full_name} (Veli)", "role": "Veli", "tel": r["veli_tel1"],
                        "status": "risk", "badge": "⚠️", "smart_note": f"{late_cnt} Geciken Ödev",
                        "default_msg": msg_veli, "msg": msg_veli, "state": "Bekliyor", "selected": True
                    })
        elif scope_idx == 2:
            # Haftanın Yıldızları
            rows = con.execute("""
                SELECT o.id, o.ad, o.soyad, o.ogr_tel, o.veli_tel1, COUNT(od.id) as done_cnt
                FROM ogrenci o
                JOIN odev od ON od.ogrenci_id = o.id
                JOIN odev_kume k ON k.id = od.kume_id
                WHERE o.aktif=1 AND od.durum IN ('tamam','yapildi') AND date(k.verilis_tarihi) > date('now', '-7 days')
                GROUP BY o.id
                HAVING done_cnt >= 4
                ORDER BY done_cnt DESC
            """).fetchall()

            for r in rows:
                full_name = f"{r['ad']} {r['soyad']}"
                done_cnt = r["done_cnt"]
                msg_ogr = f"Tebrikler {full_name}! 🌟 Son 7 günde başarıyla tamamladığın {done_cnt} ödev ile bu haftanın yıldız öğrencileri arasına girdin. Harika disiplin, aynen devam! 🚀"
                msg_veli = f"Sayın Velimiz, öğrencimiz {full_name} son 7 günde tamamladığı {done_cnt} ödev ve yüksek gayreti ile haftanın en başarılı öğrencileri arasında yer almıştır. Tebrik ederiz! 🌟"
                if r["ogr_tel"]:
                    self.queue.append({
                        "oid": r["id"], "name": full_name, "role": "Öğrenci", "tel": r["ogr_tel"],
                        "status": "star", "badge": "🌟", "smart_note": f"{done_cnt} Görev Tamamlandı",
                        "default_msg": msg_ogr, "msg": msg_ogr, "state": "Bekliyor", "selected": True
                    })
                if r["veli_tel1"]:
                    self.queue.append({
                        "oid": r["id"], "name": f"{full_name} (Veli)", "role": "Veli", "tel": r["veli_tel1"],
                        "status": "star", "badge": "🌟", "smart_note": f"{done_cnt} Görev Tamamlandı",
                        "default_msg": msg_veli, "msg": msg_veli, "state": "Bekliyor", "selected": True
                    })
        else:
            # Tüm aktif öğrenciler
            rows = con.execute("""
                SELECT id, ad, soyad, ogr_tel, veli_tel1, kocluk_gunu, kocluk_saati
                FROM ogrenci
                WHERE aktif=1
                ORDER BY ad, soyad
            """).fetchall()

            for r in rows:
                full_name = f"{r['ad']} {r['soyad']}"
                status, badge, note = self.generator._analyze_student(r["id"])
                kgun = r["kocluk_gunu"] or "Belirlenmedi"
                ksaat = r["kocluk_saati"] or ""
                randevu_txt = f"Haftalık görüşme günümüz: {kgun} {ksaat}" if r["kocluk_gunu"] else ""
                
                msg_ogr = f"Merhaba {full_name}, YKS/LGS Koçluk takibimiz devam ediyor. {randevu_txt} Eksik ödevlerini tamamlamayı ve çalışma hedeflerine sadık kalmayı unutma. İyi çalışmalar! 📚"
                msg_veli = f"Sayın Velimiz, öğrencimiz {full_name}'in haftalık koçluk takibi aktiftir. {randevu_txt} Düzenli çalışma takibini sürdürmekteyiz. İyi günler dileriz."
                if r["ogr_tel"]:
                    self.queue.append({
                        "oid": r["id"], "name": full_name, "role": "Öğrenci", "tel": r["ogr_tel"],
                        "status": status, "badge": badge or "📘", "smart_note": note or "Genel Takip",
                        "default_msg": msg_ogr, "msg": msg_ogr, "state": "Bekliyor", "selected": True
                    })
                if r["veli_tel1"]:
                    self.queue.append({
                        "oid": r["id"], "name": f"{full_name} (Veli)", "role": "Veli", "tel": r["veli_tel1"],
                        "status": status, "badge": badge or "📘", "smart_note": note or "Genel Takip",
                        "default_msg": msg_veli, "msg": msg_veli, "state": "Bekliyor", "selected": True
                    })

        self._apply_role_and_search_filter()

    def _apply_role_and_search_filter(self):
        role_filter = self.cbx_role.currentText()
        query = self.txt_search.text().strip().lower()

        filtered_items = []
        for item in self.queue:
            if role_filter == "Yalnızca Öğrenciler" and item["role"] != "Öğrenci":
                continue
            if role_filter == "Yalnızca Veliler" and item["role"] != "Veli":
                continue
            if query and query not in item["name"].lower():
                continue
            filtered_items.append(item)

        self._populate_table(filtered_items)

        # Update stats chip
        st_cnt = sum(1 for x in self.queue if x["role"] == "Öğrenci")
        vl_cnt = sum(1 for x in self.queue if x["role"] == "Veli")
        self.lbl_stats_chip.setText(f"Toplam: {len(self.queue)} Alıcı (🎓 {st_cnt} Öğrenci, 👨‍👩‍👦 {vl_cnt} Veli)")

    def _populate_table(self, items: List[Dict[str, Any]]):
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))

        for row_idx, item in enumerate(items):
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(item["selected"])
            chk.stateChanged.connect(lambda state, it=item: self._on_item_check_changed(it, state))
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row_idx, 0, chk_widget)

            # Name
            it_name = QTableWidgetItem(item["name"])
            it_name.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row_idx, 1, it_name)

            # Role
            role_icon = "🎓" if item["role"] == "Öğrenci" else "👨‍👩‍👦"
            it_role = QTableWidgetItem(f"{role_icon} {item['role']}")
            it_role.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 2, it_role)

            # Phone
            it_tel = QTableWidgetItem(item["tel"] or "-")
            it_tel.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 3, it_tel)

            # Badge
            badge_text = f"{item['badge']} {item['smart_note']}".strip()
            it_badge = QTableWidgetItem(badge_text)
            it_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
            self.table.setItem(row_idx, 4, it_badge)

            # Status
            it_state = QTableWidgetItem(item["state"])
            it_state.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if item["state"] == "Açıldı":
                it_state.setForeground(QColor("#16a34a"))
                it_state.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row_idx, 5, it_state)

            # Row tag
            it_name.setData(Qt.ItemDataRole.UserRole, item)

        self.table.blockSignals(False)
        self._update_selected_count_label()

        if items:
            self.table.selectRow(0)
        else:
            self.txt_message.clear()
            self.lbl_edit_header.setText("Seçili Alıcı: (Kayıt bulunamadı)")

    def _on_item_check_changed(self, item: Dict[str, Any], state: int):
        item["selected"] = (state == 2)
        self._update_selected_count_label()

    def _set_all_checked(self, checked: bool):
        for item in self.queue:
            item["selected"] = checked
        self._apply_role_and_search_filter()

    def _update_selected_count_label(self):
        sel = sum(1 for x in self.queue if x["selected"])
        self.lbl_selected_count.setText(f"Seçili: {sel} / {len(self.queue)}")

    def _on_table_selection_changed(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item_cell = self.table.item(row, 1)
        if not item_cell:
            return
        item_data = item_cell.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        self.lbl_edit_header.setText(f"💬 {item_data['name']} ({item_data['role']} - {item_data['tel']}) Mesajı:")
        self.txt_message.blockSignals(True)
        self.txt_message.setPlainText(item_data["msg"])
        self.txt_message.blockSignals(False)

    def _on_message_text_edited(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item_cell = self.table.item(row, 1)
        if not item_cell:
            return
        item_data = item_cell.data(Qt.ItemDataRole.UserRole)
        if item_data:
            item_data["msg"] = self.txt_message.toPlainText()

    def _reset_current_message(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item_cell = self.table.item(row, 1)
        if not item_cell:
            return
        item_data = item_cell.data(Qt.ItemDataRole.UserRole)
        if item_data:
            item_data["msg"] = item_data["default_msg"]
            self.txt_message.setPlainText(item_data["msg"])
            self._log(f"Mesaj varsayılana sıfırlandı: {item_data['name']}")

    def _send_single_whatsapp(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden bir alıcı seçin.")
            return
        item_cell = self.table.item(row, 1)
        if not item_cell:
            return
        item_data = item_cell.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        tel_clean = self.generator._clean(item_data["tel"])
        if not tel_clean:
            QMessageBox.warning(self, "Geçersiz Numara", f"{item_data['name']} için geçerli bir telefon numarası bulunamadı.")
            return

        msg_enc = urllib.parse.quote(item_data["msg"])
        url = f"https://web.whatsapp.com/send?phone={tel_clean}&text={msg_enc}"
        webbrowser.open(url)

        item_data["state"] = "Açıldı"
        self.table.item(row, 5).setText("Açıldı")
        self.table.item(row, 5).setForeground(QColor("#16a34a"))
        self._log(f"WhatsApp sekmesi açıldı: {item_data['name']} ({tel_clean})")

    def _copy_single_message(self):
        txt = self.txt_message.toPlainText()
        if not txt:
            return
        QApplication.clipboard().setText(txt)
        self._log("Seçili mesaj panoya kopyalandı.")
        QMessageBox.information(self, "Kopyalandı", "Mesaj panoya kopyalandı! İstediğiniz yere yapıştırabilirsiniz. 📋")

    def _copy_all_messages(self):
        selected_items = [x for x in self.queue if x["selected"]]
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen en az bir alıcı seçin.")
            return

        all_text = []
        for it in selected_items:
            all_text.append(f"═══════════════════════════════\n👤 {it['name']} ({it['role']} - {it['tel']})\n═══════════════════════════════\n{it['msg']}\n")

        joined = "\n".join(all_text)
        QApplication.clipboard().setText(joined)
        self._log(f"{len(selected_items)} adet mesaj toplu olarak panoya kopyalandı.")
        QMessageBox.information(self, "Kopyalandı", f"{len(selected_items)} alıcının mesajı panoya kopyalandı! 📋")

    # --- Otomasyon Robotu ---
    def _start_auto_sending(self):
        self.selected_queue = [x for x in self.queue if x["selected"] and x["state"] != "Açıldı"]
        if not self.selected_queue:
            QMessageBox.information(self, "Bilgi", "Gönderilecek (bekleyen) seçili alıcı kalmadı.")
            return

        delay_str = self.cbx_delay.currentText().split()[0]
        delay_ms = int(delay_str) * 1000

        self.current_sending_idx = 0
        self.is_paused = False
        self.progress_bar.setRange(0, len(self.selected_queue))
        self.progress_bar.setValue(0)

        self.btn_start_auto.setEnabled(False)
        self.btn_pause_auto.setEnabled(True)
        self.btn_stop_auto.setEnabled(True)

        self._log(f"🚀 Otomatik gönderim robotu başlatıldı ({len(self.selected_queue)} alıcı, {delay_str} sn aralık).")
        self._process_next_auto_message()
        self.timer.start(delay_ms)

    def _pause_auto_sending(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.timer.stop()
            self.btn_pause_auto.setText("▶️ Devam Et")
            self._log("⏸️ Gönderim duraklatıldı.")
        else:
            delay_str = self.cbx_delay.currentText().split()[0]
            self.timer.start(int(delay_str) * 1000)
            self.btn_pause_auto.setText("⏸️ Duraklat")
            self._log("▶️ Gönderim devam ediyor...")

    def _stop_auto_sending(self):
        self.timer.stop()
        self.btn_start_auto.setEnabled(True)
        self.btn_pause_auto.setEnabled(False)
        self.btn_pause_auto.setText("⏸️ Duraklat")
        self.btn_stop_auto.setEnabled(False)
        self._log("⏹️ Gönderim durduruldu.")

    def _stop_and_close(self):
        self._stop_auto_sending()
        self.close()

    def _process_next_auto_message(self):
        if self.is_paused:
            return

        if self.current_sending_idx >= len(self.selected_queue):
            self._stop_auto_sending()
            self._log("✅ TÜM İŞLEMLER TAMAMLANDI.")
            QMessageBox.information(self, "Tamamlandı", "Seçili tüm profiller WhatsApp'ta açıldı.")
            return

        item = self.selected_queue[self.current_sending_idx]
        self.current_sending_idx += 1
        self.progress_bar.setValue(self.current_sending_idx)

        tel_clean = self.generator._clean(item["tel"])
        if tel_clean:
            msg_enc = urllib.parse.quote(item["msg"])
            url = f"https://web.whatsapp.com/send?phone={tel_clean}&text={msg_enc}"
            webbrowser.open(url)
            item["state"] = "Açıldı"
            self._log(f"[{self.current_sending_idx}/{len(self.selected_queue)}] Açıldı: {item['name']} ({tel_clean})")
            for r in range(self.table.rowCount()):
                row_item = self.table.item(r, 1)
                if row_item and row_item.data(Qt.ItemDataRole.UserRole) == item:
                    self.table.item(r, 5).setText("Açıldı")
                    self.table.item(r, 5).setForeground(QColor("#16a34a"))
                    break
        else:
            self._log(f"⚠️ Atlandı (Numara yok): {item['name']}")

# =========================================================================
# 3. SINIF & VELİ GRUBU BÜLTENİ KOPYALAYICI (OPTION 3)
# =========================================================================
class GroupBulletinDialog(QDialog):
    """
    Sınıf veya veli WhatsApp gruplarına atılmak üzere günlük, yarınki
    veya haftalık ödev teslim listesini emojili ve şık formatta hazırlar.
    """
    def __init__(self, parent, schedule_generator: 'MobileScheduleGenerator'):
        super().__init__(parent)
        self.generator = schedule_generator
        self.setWindowTitle("📋 Sınıf & Veli Grubu Bülteni Hazırlayıcı")
        self.resize(780, 680)
        self._setup_ui()
        self._generate_bulletin()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header Banner
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #d97706);
                border-radius: 10px;
                padding: 12px 18px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 8, 10, 8)

        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_title = QLabel("📋 Sınıf & Veli Grubu Bülteni")
        lbl_title.setStyleSheet("color: white; font-size: 20px; font-weight: 800; background: transparent;")
        lbl_sub = QLabel("WhatsApp gruplarına tek tıkla atılabilecek emojili, profesyonel teslim ve randevu bülteni")
        lbl_sub.setStyleSheet("color: #fef3c7; font-size: 13px; background: transparent;")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        h_layout.addLayout(v_title)
        h_layout.addStretch()

        main_layout.addWidget(header)

        # Scope Selection Radio Buttons
        scope_box = QFrame()
        scope_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px;")
        scope_layout = QHBoxLayout(scope_box)
        scope_layout.setSpacing(15)

        lbl_sec = QLabel("📅 Bülten Dönemi:")
        lbl_sec.setStyleSheet("font-weight: bold; color: #334155; font-size: 13px;")
        scope_layout.addWidget(lbl_sec)

        self.btn_grp = QButtonGroup(self)
        self.rb_today = QRadioButton("Bugünün Teslimleri")
        self.rb_today.setChecked(True)
        self.btn_grp.addButton(self.rb_today, 0)
        scope_layout.addWidget(self.rb_today)

        self.rb_tomorrow = QRadioButton("Yarının Teslimleri")
        self.btn_grp.addButton(self.rb_tomorrow, 1)
        scope_layout.addWidget(self.rb_tomorrow)

        self.rb_week = QRadioButton("Haftalık Genel Takvim (7 Gün)")
        self.btn_grp.addButton(self.rb_week, 2)
        scope_layout.addWidget(self.rb_week)

        self.rb_meetings = QRadioButton("Günün Görüşmeleri")
        self.btn_grp.addButton(self.rb_meetings, 3)
        scope_layout.addWidget(self.rb_meetings)

        self.rb_late = QRadioButton("Geciken Telafi Listesi")
        self.btn_grp.addButton(self.rb_late, 4)
        scope_layout.addWidget(self.rb_late)

        scope_layout.addStretch()
        self.btn_grp.idToggled.connect(self._generate_bulletin)
        main_layout.addWidget(scope_box)

        # Formatting options
        opt_layout = QHBoxLayout()
        opt_layout.setSpacing(15)

        self.chk_emojis = QCheckBox("Emoji ve Vurguları Kullan")
        self.chk_emojis.setChecked(True)
        self.chk_emojis.setStyleSheet("font-weight: 600; color: #475569;")
        self.chk_emojis.stateChanged.connect(self._generate_bulletin)
        opt_layout.addWidget(self.chk_emojis)

        self.chk_badges = QCheckBox("Öğrenci Rozetlerini Ekle (🌟/⚠️)")
        self.chk_badges.setChecked(True)
        self.chk_badges.setStyleSheet("font-weight: 600; color: #475569;")
        self.chk_badges.stateChanged.connect(self._generate_bulletin)
        opt_layout.addWidget(self.chk_badges)

        self.chk_coach_note = QCheckBox("Koç Tavsiye & Motivasyon Notu Ekle")
        self.chk_coach_note.setChecked(True)
        self.chk_coach_note.setStyleSheet("font-weight: 600; color: #475569;")
        self.chk_coach_note.stateChanged.connect(self._generate_bulletin)
        opt_layout.addWidget(self.chk_coach_note)

        opt_layout.addStretch()
        main_layout.addLayout(opt_layout)

        # Text Editor
        self.txt_bulletin = QTextEdit()
        self.txt_bulletin.setStyleSheet("""
            QTextEdit {
                background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px;
                padding: 12px; font-family: 'Consolas', 'Cascadia Code', monospace; font-size: 13px; line-height: 1.5;
            }
        """)
        main_layout.addWidget(self.txt_bulletin, 1)

        # Status feedback banner
        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet("color: #16a34a; font-weight: bold; font-size: 13px;")
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_feedback)

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        self.btn_copy = QPushButton("📋 Panoya Kopyala (WhatsApp Formatı)")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #16a34a; color: white; font-weight: bold; font-size: 14px;
                padding: 12px 24px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #15803d; }
        """)
        self.btn_copy.clicked.connect(self._copy_bulletin)
        bottom_layout.addWidget(self.btn_copy)

        self.btn_wa_web = QPushButton("🚀 WhatsApp Web'de Paylaş")
        self.btn_wa_web.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wa_web.setStyleSheet("""
            QPushButton {
                background-color: #0891b2; color: white; font-weight: bold; font-size: 13px;
                padding: 12px 18px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #0e7490; }
        """)
        self.btn_wa_web.clicked.connect(self._share_whatsapp)
        bottom_layout.addWidget(self.btn_wa_web)

        self.btn_save_txt = QPushButton("💾 Metin Dosyası (.txt) Olarak Kaydet")
        self.btn_save_txt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_txt.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; font-weight: bold; padding: 12px 16px; border-radius: 8px;")
        self.btn_save_txt.clicked.connect(self._save_txt)
        bottom_layout.addWidget(self.btn_save_txt)

        bottom_layout.addStretch()

        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet("background: #e2e8f0; color: #475569; font-weight: bold; padding: 12px 18px; border-radius: 8px; border: none;")
        btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(btn_close)

        main_layout.addLayout(bottom_layout)

    def _generate_bulletin(self):
        period_id = self.btn_grp.checkedId()
        emojis = self.chk_emojis.isChecked()
        badges = self.chk_badges.isChecked()
        coach_note = self.chk_coach_note.isChecked()

        schedule, next_7_days = self.generator._fetch_data(group_filter="Tümü", include_all_active=False)
        today = datetime.date.today()
        today_name = next_7_days[0][1]

        lines = []

        if period_id == 0:
            # Bugün
            t_str = today.strftime("%d.%m.%Y")
            header = f"📅 *{t_str} {today_name} Günlük Ödev Teslim Listesi* 📅" if emojis else f"[{t_str} {today_name} Gunluk Odev Teslim Listesi]"
            lines.append(header)
            lines.append("────────────────────────────────")

            events = [e for e in schedule.get(today_name, []) if e["tip"] == "Teslim"]
            if not events:
                lines.append("Bugün için planlanmış bir ödev teslimi bulunmamaktadır. Harika bir dinlenme/pekiştirme günü! 🎉" if emojis else "Bugun icin teslim plani yoktur.")
            else:
                for i, ev in enumerate(events, 1):
                    badge_str = f" {ev['meta'].get('badge', '')}" if (badges and ev['meta'].get('badge')) else ""
                    lines.append(f"*{i}. {ev['ad']}*{badge_str}:")
                    for t in ev["meta"]["lines"]:
                        lines.append(f"  • {t}")
                    if ev["meta"]["notes"]:
                        for n in ev["meta"]["notes"]:
                            lines.append(f"    _Not: {n}_")
                    lines.append("")

        elif period_id == 1:
            # Yarın
            tomorrow = today + datetime.timedelta(days=1)
            tm_name = next_7_days[1][1]
            t_str = tomorrow.strftime("%d.%m.%Y")
            header = f"🌅 *{t_str} {tm_name} Yarınki Ödev Teslim Listesi* 🌅" if emojis else f"[{t_str} {tm_name} Yarinki Odev Teslim Listesi]"
            lines.append(header)
            lines.append("────────────────────────────────")

            events = [e for e in schedule.get(tm_name, []) if e["tip"] == "Teslim"]
            if not events:
                lines.append("Yarın için planlanmış bir ödev teslimi bulunmamaktadır." if emojis else "Yarin icin teslim plani yoktur.")
            else:
                for i, ev in enumerate(events, 1):
                    badge_str = f" {ev['meta'].get('badge', '')}" if (badges and ev['meta'].get('badge')) else ""
                    lines.append(f"*{i}. {ev['ad']}*{badge_str}:")
                    for t in ev["meta"]["lines"]:
                        lines.append(f"  • {t}")
                    lines.append("")

        elif period_id == 2:
            # Haftalık Genel
            header = f"📆 *Haftalık Genel Takip & Teslim Programı (7 Gün)* 📆" if emojis else "[Haftalik Genel Takip ve Teslim Programi]"
            lines.append(header)
            lines.append(f"Dönem: {next_7_days[0][0]} — {next_7_days[-1][0]}")
            lines.append("════════════════════════════════")

            for d_str, day_name in next_7_days:
                evs = schedule.get(day_name, [])
                nice_d = f"{d_str.split('-')[2]}.{d_str.split('-')[1]}"
                lines.append(f"📌 *{day_name} ({nice_d})*:")
                if not evs:
                    lines.append("  _Etkinlik planı yok._")
                else:
                    for ev in evs:
                        icon = "🕒" if ev["tip"] == "Görüşme" else "📚"
                        badge_str = f" {ev['meta'].get('badge', '')}" if (badges and ev['meta'].get('badge')) else ""
                        if ev["tip"] == "Görüşme":
                            lines.append(f"  {icon} Saat {ev['saat']}: *{ev['ad']}* (Koçluk Görüşmesi)")
                        else:
                            tasks_summary = ", ".join(ev["meta"]["lines"][:2])
                            if len(ev["meta"]["lines"]) > 2:
                                tasks_summary += f" (+{len(ev['meta']['lines'])-2} ödev)"
                            lines.append(f"  {icon} *{ev['ad']}*{badge_str}: {tasks_summary}")
                lines.append("")

        elif period_id == 3:
            # Görüşmeler
            lines.append(f"🕒 *Günün Koçluk Randevuları ({today.strftime('%d.%m.%Y')} {today_name})* 🕒" if emojis else "[Gunun Kocluk Randevulari]")
            lines.append("────────────────────────────────")
            meetings = [e for e in schedule.get(today_name, []) if e["tip"] == "Görüşme"]
            if not meetings:
                lines.append("Bugün için tanımlanmış sabit bir koçluk görüşmesi görünmüyor.")
            else:
                for i, m in enumerate(meetings, 1):
                    tel = m["tel_ogr"] or m["tel_veli"] or ""
                    lines.append(f"*{i}. {m['ad']}* — Saat: *{m['saat']}* {f'(İletişim: {tel})' if tel else ''}")
            lines.append("")

        else:
            # Gecikenler
            lines.append("🚨 *Kritik Ödev Gecikme & Telafi Listesi* 🚨" if emojis else "[Kritik Odev Gecikme ve Telafi Listesi]")
            lines.append("────────────────────────────────")
            con = self.generator.con
            rows = con.execute("""
                SELECT o.ad, o.soyad, COUNT(od.id) as cnt
                FROM ogrenci o
                JOIN odev od ON od.ogrenci_id = o.id
                JOIN odev_kume k ON k.id = od.kume_id
                WHERE o.aktif=1 AND od.durum='devam' AND date(k.bitis_tarihi) < date('now')
                GROUP BY o.id
                HAVING cnt > 0
                ORDER BY cnt DESC
            """).fetchall()
            if not rows:
                lines.append("Tebrikler! Şu an hiçbir öğrencinin süresi geçmiş ödevi bulunmamaktadır. 👏")
            else:
                for i, r in enumerate(rows, 1):
                    lines.append(f"*{i}. {r['ad']} {r['soyad']}*: {r['cnt']} adet ödev telafide bekliyor ⚠️")
            lines.append("")

        if coach_note:
            lines.append("────────────────────────────────")
            lines.append("💡 *Koç Notu:* Lütfen ödevlerinizi kontrol saatinden önce tamamlayarak sisteme işleyiniz. Aksayan noktalar için koçunuzla iletişime geçiniz. İyi çalışmalar ve başarılar! 🚀" if emojis else "Not: Lutfen odevlerinizi kontrol saatinden once tamamlayiniz. Basarilar dileriz.")

        bulletin_text = "\n".join(lines)
        self.txt_bulletin.setPlainText(bulletin_text)
        self.lbl_feedback.setText("")

    def _copy_bulletin(self):
        txt = self.txt_bulletin.toPlainText()
        if not txt:
            return
        QApplication.clipboard().setText(txt)
        self.lbl_feedback.setText("✅ Bülten panoya kopyalandı! WhatsApp grubuna doğrudan yapıştırabilirsiniz.")
        QMessageBox.information(self, "Kopyalandı", "Bülten panoya kopyalandı! WhatsApp grubuna yapıştırabilirsiniz. 📋")

    def _share_whatsapp(self):
        txt = self.txt_bulletin.toPlainText()
        if not txt:
            return
        url = f"https://api.whatsapp.com/send?text={urllib.parse.quote(txt)}"
        webbrowser.open(url)

    def _save_txt(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Bülteni Kaydet", f"bulten_{datetime.date.today().strftime('%Y_%m_%d')}.txt", "Metin Dosyası (*.txt)")
        if not fn:
            return
        try:
            with open(fn, "w", encoding="utf-8") as f:
                f.write(self.txt_bulletin.toPlainText())
            QMessageBox.information(self, "Kaydedildi", f"Bülten kaydedildi:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{e}")

# =========================================================================
# 4. YENİLENEN ANA MENÜ DİYALOĞU (ScheduleActionDialog)
# =========================================================================
class ScheduleActionDialog(QDialog):
    """
    Modern kart tasarımlı, canlı KPI sayaçlı Cep Ajandası ana seçim menüsü.
    """
    def __init__(self, parent, generator: 'MobileScheduleGenerator', on_pdf, on_bulk, on_copy):
        super().__init__(parent)
        self.generator = generator
        self.setWindowTitle("📱 Akıllı Cep Ajandası & İletişim Merkezi")
        self.setFixedWidth(540)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(22, 22, 22, 22)

        # Header Area
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e3a8a);
                border-radius: 12px;
                padding: 16px 20px;
            }
        """)
        h_layout = QVBoxLayout(header)
        h_layout.setSpacing(4)
        h_layout.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("📱 Akıllı Cep Ajandası & İletişim Asistanı")
        lbl_title.setStyleSheet("font-size: 19px; font-weight: 900; color: white; background: transparent;")
        h_layout.addWidget(lbl_title)

        lbl_sub = QLabel("Haftalık ajanda, akıllı WhatsApp robotu ve sınıf grubu bülteni")
        lbl_sub.setStyleSheet("font-size: 13px; color: #93c5fd; background: transparent;")
        h_layout.addWidget(lbl_sub)

        layout.addWidget(header)

        # Live KPI Ribbon
        kpi_frame = QFrame()
        kpi_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px;
            }
        """)
        kpi_layout = QHBoxLayout(kpi_frame)
        kpi_layout.setSpacing(10)

        stats = self.generator._get_operational_summary()

        def make_kpi(icon, val, label, color):
            box = QVBoxLayout()
            box.setSpacing(2)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_v = QLabel(f"{icon} {val}")
            lbl_v.setStyleSheet(f"font-size: 16px; font-weight: 900; color: {color};")
            lbl_l = QLabel(label)
            lbl_l.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
            box.addWidget(lbl_v)
            box.addWidget(lbl_l)
            return box

        kpi_layout.addLayout(make_kpi("📅", stats["today_deadlines"], "Bugün Teslim", "#2563eb"))
        kpi_layout.addLayout(make_kpi("🕒", stats["weekly_meetings"], "Haftalık Randevu", "#0891b2"))
        kpi_layout.addLayout(make_kpi("⚠️", stats["overdue_tasks"], "Geciken Ödev", "#ef4444" if stats["overdue_tasks"] > 0 else "#10b981"))
        kpi_layout.addLayout(make_kpi("👥", stats["active_students"], "Aktif Öğrenci", "#334155"))

        layout.addWidget(kpi_frame)

        # Section subtitle
        lbl_hint = QLabel("Gerçekleştirmek istediğiniz işlemi seçiniz:")
        lbl_hint.setStyleSheet("font-size: 13px; font-weight: bold; color: #334155; margin-top: 4px;")
        layout.addWidget(lbl_hint)

        # 3 Cards Helper
        def create_action_card(title: str, badge: str, desc: str, bg_color: str, hover_color: str, border_color: str, on_click):
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    padding: 14px 18px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                    border: 1px solid #3b82f6;
                }}
            """)
            card_layout = QVBoxLayout(btn)
            card_layout.setSpacing(4)
            card_layout.setContentsMargins(0, 0, 0, 0)

            top_row = QHBoxLayout()
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a; background: transparent;")
            top_row.addWidget(lbl_t)
            top_row.addStretch()

            lbl_b = QLabel(badge)
            lbl_b.setStyleSheet("""
                background: #eff6ff; color: #1d4ed8; font-size: 10px; font-weight: 800;
                padding: 3px 8px; border-radius: 12px; border: 1px solid #bfdbfe;
            """)
            top_row.addWidget(lbl_b)
            card_layout.addLayout(top_row)

            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("font-size: 12px; color: #64748b; background: transparent;")
            lbl_d.setWordWrap(True)
            card_layout.addWidget(lbl_d)

            btn.clicked.connect(lambda: [self.close(), on_click()])
            return btn

        # Card 1: PDF
        card1 = create_action_card(
            "📄  Akıllı PDF Ajanda (Önizle & Yazdır)",
            "GÖRSEL HAFTALIK PLAN",
            "Gün gün renklendirilmiş teslim saatleri, rozetler (🌟/⚠️), tıklanabilir WhatsApp linkleri, dahili önizleme ve PDF çıktısı.",
            "#ffffff", "#f0fdf4", "#cbd5e1",
            on_pdf
        )
        layout.addWidget(card1)

        # Card 2: WhatsApp
        card2 = create_action_card(
            "🚀  Akıllı İletişim Robotu (WhatsApp Merkezi)",
            "AI MESAJ KUYRUĞU",
            "Yapay zeka ile kişiselleştirilmiş motivasyon mesajları üretir. Alıcı seçimi, mesaj düzenleme ve otomatik masaüstü/web gönderimi.",
            "#ffffff", "#eff6ff", "#cbd5e1",
            on_bulk
        )
        layout.addWidget(card2)

        # Card 3: Bulletin
        card3 = create_action_card(
            "📋  Sınıf & Veli Grubu Bülteni (Kopyala)",
            "TOPLU BÜLTEN",
            "Bugünün teslimleri, yarının programı veya haftalık genel özet. Emojili, WhatsApp formatında tek tıkla panoya kopyalama.",
            "#ffffff", "#fffbeb", "#cbd5e1",
            on_copy
        )
        layout.addWidget(card3)

        btn_cancel = QPushButton("Kapat")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: transparent; color: #64748b; font-weight: bold; padding: 6px; border: none;
            }
            QPushButton:hover { color: #0f172a; }
        """)
        btn_cancel.clicked.connect(self.close)
        layout.addWidget(btn_cancel)


# =========================================================================
# 5. GENERATOR CLASS (HESAPLAMA, VERİ ÇEKME VE YÖNETİM)
# =========================================================================
class MobileScheduleGenerator:
    COLOR_MEETING = "#3b82f6"
    COLOR_DEADLINE = "#ef4444"

    def __init__(self, parent: QWidget):
        self.parent = parent
        self.con = db.get_conn()
        _ensure_schema(self.con)

    def _get_operational_summary(self) -> Dict[str, int]:
        """Menü için anlık operasyonel özet verileri hesaplar"""
        _ensure_schema(self.con)
        try:
            # 1. Bugün teslim
            r_today = self.con.execute("""
                SELECT COUNT(*) FROM odev o
                JOIN odev_kume k ON k.id = o.kume_id
                WHERE date(k.bitis_tarihi) = date('now')
            """).fetchone()
            today_cnt = r_today[0] if r_today else 0

            # 2. Haftalık randevu
            r_meet = self.con.execute("""
                SELECT COUNT(*) FROM ogrenci
                WHERE kocluk_gunu IS NOT NULL AND kocluk_gunu != '' AND aktif=1
            """).fetchone()
            meet_cnt = r_meet[0] if r_meet else 0

            # 3. Geciken ödevler
            r_overdue = self.con.execute("""
                SELECT COUNT(*) FROM odev o
                JOIN odev_kume k ON k.id = o.kume_id
                WHERE o.durum='devam' AND date(k.bitis_tarihi) < date('now')
            """).fetchone()
            overdue_cnt = r_overdue[0] if r_overdue else 0

            # 4. Aktif öğrenci
            r_act = self.con.execute("SELECT COUNT(*) FROM ogrenci WHERE aktif=1").fetchone()
            act_cnt = r_act[0] if r_act else 0

            return {
                "today_deadlines": today_cnt,
                "weekly_meetings": meet_cnt,
                "overdue_tasks": overdue_cnt,
                "active_students": act_cnt,
            }
        except Exception as e:
            print(f"[MobileSchedule] summary error: {e}")
            return {"today_deadlines": 0, "weekly_meetings": 0, "overdue_tasks": 0, "active_students": 0}

    def _analyze_student(self, sid):
        """Öğrenci performans rozeti ve koçluk etiketi hesaplar"""
        if not sid:
            return "normal", "", ""
        try:
            # 1. Gecikme (Risk)
            r_late = self.con.execute("""
                SELECT COUNT(*) FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE o.ogrenci_id=? AND o.durum='devam' AND date(k.bitis_tarihi) < date('now')
            """, (sid,)).fetchone()
            late_count = r_late[0] if r_late else 0

            if late_count > 2:
                return "risk", "⚠️", f"{late_count} Ödev Gecikmiş!"

            # 2. Yıldız (Son 7 gün)
            r_done = self.con.execute("""
                SELECT COUNT(*) FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE o.ogrenci_id=? AND o.durum IN ('tamam','yapildi') 
                AND date(k.verilis_tarihi) > date('now', '-7 days')
            """, (sid,)).fetchone()
            done_count = r_done[0] if r_done else 0

            if done_count >= 5:
                return "star", "🌟", f"Haftanın Yıldızı ({done_count} Tamamlandı)"

            # 3. Maratoncu
            r_vol = self.con.execute("""
                SELECT COUNT(*) FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE o.ogrenci_id=? AND o.durum IN ('tamam','yapildi') 
                AND date(k.verilis_tarihi) > date('now', '-3 days')
            """, (sid,)).fetchone()
            vol_count = r_vol[0] if r_vol else 0

            if vol_count >= 8:
                return "marathon", "🏃", f"Maratoncu ({vol_count} Görev Bitti)"

            # 4. İstikrarlı
            if late_count == 0 and done_count > 0:
                return "steady", "🛡️", "İstikrarlı İlerliyor"

            # 5. Sessiz
            r_last = self.con.execute("""
                SELECT MAX(d) FROM (
                    SELECT date(verilis_tarihi) as d FROM odev_kume WHERE ogrenci_id=?
                    UNION
                    SELECT date(zaman) as d FROM whatsapp_log WHERE ogrenci_id=?
                )
            """, (sid, sid)).fetchone()
            last_date = r_last[0] if r_last else None
            if not last_date:
                return "silent", "💤", "Yeni Kayıt / Veri Yok"

            days_diff = (datetime.date.today() - datetime.datetime.strptime(last_date, "%Y-%m-%d").date()).days
            if days_diff > 10:
                return "silent", "💤", f"{days_diff} Gündür Sessiz"

            return "normal", "", ""
        except Exception:
            return "normal", "", ""

    def _get_mini_stats(self, sid):
        if not sid:
            return "Veri yok"
        try:
            r = self.con.execute("""
                SELECT 
                    SUM(CASE WHEN o.durum IN ('tamam','yapildi') THEN 1 ELSE 0 END) as done,
                    COUNT(*) as total
                FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE o.ogrenci_id=? AND date(k.verilis_tarihi) > date('now', '-14 days')
            """, (sid,)).fetchone()
            done = r[0] if r and r[0] else 0
            total = r[1] if r and r[1] else 0
            return f"✅ {done} / 📋 {total}"
        except Exception:
            return "Veri yok"

    def generate(self):
        """Cep Ajandası Ana Menüsünü Açar"""
        _ensure_schema(self.con)
        dlg = ScheduleActionDialog(
            self.parent,
            generator=self,
            on_pdf=self.open_pdf_preview_flow,
            on_bulk=self.open_bulk_communicator_flow,
            on_copy=self.open_group_bulletin_flow
        )
        dlg.exec()

    # --- Actions Entry Points ---
    def open_pdf_preview_flow(self):
        """Seçenek 1: Akıllı PDF Ajanda Önizleme ve Baskı Penceresini açar"""
        dlg = SmartMobileSchedulePreviewDialog(self.parent, self)
        dlg.exec()

    def open_bulk_communicator_flow(self):
        """Seçenek 2: Akıllı WhatsApp İletişim Merkezi & Robotunu açar"""
        dlg = SmartBulkMessageDialog(self.parent, self)
        dlg.exec()

    def open_group_bulletin_flow(self):
        """Seçenek 3: Sınıf & Veli Grubu Bülteni Penceresini açar"""
        dlg = GroupBulletinDialog(self.parent, self)
        dlg.exec()

    # --- Data Fetching ---
    def _fetch_data(self, group_filter="Tümü", include_all_active=False):
        _ensure_schema(self.con)
        today = datetime.date.today()
        days_tr = {0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"}

        schedule = {}
        next_7_days = []
        for i in range(7):
            d = today + datetime.timedelta(days=i)
            day_name = days_tr[d.weekday()]
            d_str = d.strftime("%Y-%m-%d")
            next_7_days.append((d_str, day_name))
            schedule[day_name] = []

        # 1. Sabit Görüşmeler
        rows_fixed = self.con.execute("""
            SELECT id, ad, soyad, ogr_tel, veli_tel1, kocluk_gunu, kocluk_saati, ana_grup, alt_grup 
            FROM ogrenci 
            WHERE kocluk_gunu IS NOT NULL AND kocluk_gunu != '' AND aktif=1
        """).fetchall()

        for r in rows_fixed:
            if group_filter != "Tümü" and r["ana_grup"] != group_filter:
                continue
            gun = r["kocluk_gunu"]
            if gun in schedule:
                schedule[gun].append({
                    "oid": r["id"],
                    "ad": f"{r['ad']} {r['soyad']}",
                    "tel_ogr": r["ogr_tel"],
                    "tel_veli": r["veli_tel1"],
                    "saat": r["kocluk_saati"] or "??:??",
                    "tip": "Görüşme",
                    "detay": "Haftalık Koçluk Görüşmesi",
                    "renk": self.COLOR_MEETING,
                    "meta": {"lines": [], "notes": [], "badge": "", "smart_note": "", "stats": self._get_mini_stats(r["id"])}
                })

        # 2. Ödev Teslimleri
        end_date = next_7_days[-1][0]
        rows_odev = self.con.execute("""
            SELECT k.bitis_tarihi, o.id as oid, o.ad, o.soyad, o.ogr_tel, o.veli_tel1, o.ana_grup, o.alt_grup, k.aciklama,
                   GROUP_CONCAT(COALESCE(os.ders,'') || '|' || COALESCE(os.kitap_ad,'') || '|' || COALESCE(os.konu_ad,'Genel'), '$$$') as icerik_raw
            FROM odev_kume k
            JOIN ogrenci o ON o.id = k.ogrenci_id
            LEFT JOIN odev os ON os.kume_id = k.id
            WHERE date(k.bitis_tarihi) BETWEEN date(?) AND date(?)
            GROUP BY k.id
        """, (next_7_days[0][0], end_date)).fetchall()

        for r in rows_odev:
            try:
                if group_filter != "Tümü" and r["ana_grup"] != group_filter:
                    continue
                d_obj = datetime.datetime.strptime(r["bitis_tarihi"], "%Y-%m-%d").date()
                day_name = days_tr[d_obj.weekday()]
                if day_name not in schedule:
                    continue

                lines = []
                raw_str = r["icerik_raw"] or ""
                for item in raw_str.split("$$$"):
                    parts = item.split("|")
                    if len(parts) >= 3:
                        d, k, kn = parts[0], parts[1], parts[2]
                        d_clean = d.replace('_', ' ').strip().title() if d else ""
                        k_clean = k.replace('_', ' ').strip().title() if k else ""
                        kn_clean = kn.replace('_', ' ').strip()
                        if kn_clean == "Genel":
                            kn_clean = ""
                        if kn_clean:
                            kn_clean = kn_clean[0].upper() + kn_clean[1:]

                        line = d_clean
                        if k_clean:
                            line += f" - {k_clean}"
                        if kn_clean:
                            line += f" - {kn_clean}"
                        if line:
                            lines.append(line)

                notes = [r["aciklama"]] if r["aciklama"] else []
                status, badge_icon, smart_note = self._analyze_student(r["oid"])
                stats_text = self._get_mini_stats(r["oid"])

                card_color = self.COLOR_DEADLINE
                if status == "star":
                    card_color = "#f59e0b"
                elif status == "risk":
                    card_color = "#ef4444"
                elif status == "marathon":
                    card_color = "#3b82f6"
                elif status == "steady":
                    card_color = "#10b981"
                elif status == "silent":
                    card_color = "#64748b"

                schedule[day_name].append({
                    "oid": r["oid"],
                    "ad": f"{r['ad']} {r['soyad']}",
                    "tel_ogr": r["ogr_tel"],
                    "tel_veli": r["veli_tel1"],
                    "saat": "18:00",
                    "tip": "Teslim",
                    "renk": card_color,
                    "meta": {
                        "lines": lines,
                        "notes": notes,
                        "nice_date": d_obj.strftime("%d.%m.%Y"),
                        "status": status,
                        "badge": badge_icon,
                        "smart_note": smart_note,
                        "stats": stats_text
                    }
                })
            except Exception:
                continue

        # 3. Merging Deadlines per day
        self._merge_deadlines(schedule)

        # 4. Sorting
        for day in schedule:
            schedule[day].sort(key=lambda x: (x["saat"], x["ad"]))

        return schedule, next_7_days

    def _merge_deadlines(self, schedule):
        for day, events in schedule.items():
            merged = {}
            final_list = []
            for ev in events:
                if ev["tip"] != "Teslim":
                    final_list.append(ev)
                    continue

                key = ev["ad"]
                if key not in merged:
                    merged[key] = ev
                else:
                    base = merged[key]
                    base["meta"]["lines"].extend(ev["meta"]["lines"])
                    base["meta"]["notes"].extend(ev["meta"]["notes"])
                    if not base["tel_ogr"]:
                        base["tel_ogr"] = ev["tel_ogr"]
                    if not base["tel_veli"]:
                        base["tel_veli"] = ev["tel_veli"]
                    if ev["meta"].get("status") == "risk":
                        base["meta"]["status"] = "risk"
                        base["renk"] = self.COLOR_DEADLINE
                        base["meta"]["badge"] = "⚠️"
                        base["meta"]["smart_note"] = "Dikkat: Ödev teslimlerinde aksama var."
                    elif ev["meta"].get("status") == "star" and base["meta"].get("status") != "risk":
                        base["meta"]["status"] = "star"

            final_list.extend(merged.values())
            schedule[day] = final_list

    # --- Message Builders ---
    def _build_msg_single(self, ev, day_name, d_nice):
        if ev["tip"] == "Görüşme":
            return f"Merhaba {ev['ad']}, {day_name} ({d_nice}) saat {ev['saat']} haftalık koçluk görüşmemiz planlanmıştır. Hazırlıklarınla birlikte görüşmek üzere! 👋"
        else:
            t_date = ev["meta"].get("nice_date", d_nice)
            tasks = "\n".join([f"  • {l}" for l in ev["meta"]["lines"]])
            intro = f"Merhaba {ev['ad']},"
            status = ev["meta"].get("status")
            if status == "star":
                intro += " 🌟 Harika gidiyorsun! Bu haftaki performansın ve disiplinin süper."
            elif status == "risk":
                intro += " ⚠️ Biraz hızlanmamız ve aksayan ödevleri telafi etmemiz lazım, lütfen ödevlerini aksatma."
            elif status == "marathon":
                intro += " 🏃 Hızına yetişemiyoruz, maşallah! Maraton temposu aynen devam etsin."
            elif status == "steady":
                intro += " 🛡️ Gayet istikrarlı ve düzenli gidiyorsun, aynen devam."
            elif status == "silent":
                intro += " 👀 Seni bir süredir sahalarda göremiyoruz, güçlü bir dönüş bekliyorum."

            notes_str = ""
            if ev["meta"].get("notes"):
                notes_str = "\n📌 Notlar: " + ", ".join(ev["meta"]["notes"])

            return f"{intro}\n\n{day_name} ({t_date}) günü için teslim programın:\n\n{tasks}{notes_str}\n\nİyi çalışmalar ve başarılar dilerim! 📚"

    def _build_parent_msg(self, ev, day_name, d_nice):
        t_date = ev["meta"].get("nice_date", d_nice)
        if ev["tip"] == "Görüşme":
            return f"Sayın Velimiz, öğrencimiz {ev['ad']}'in {day_name} ({d_nice}) saat {ev['saat']} haftalık koçluk randevusu bulunmaktadır. Bilginize sunar, iyi günler dileriz."
        else:
            tasks = "\n".join([f"  • {l}" for l in ev["meta"]["lines"]])
            return f"Sayın Velimiz, öğrencimiz {ev['ad']}'in {day_name} ({t_date}) günü teslim etmesi gereken ödev programı:\n\n{tasks}\n\nÖğrencimizin çalışmalarını evde desteklemenizi rica eder, iyi günler dileriz."

    # --- HTML Builder for PDF / Browser ---
    def _build_html(self, schedule, next_7_days, for_pdf=False):
        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        today_date = datetime.date.today()
        today_name = next_7_days[0][1]
        today_evs = [e for e in schedule.get(today_name, []) if e["tip"] == "Teslim"]

        html_out = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    color: #1e293b; margin: 0; padding: 20px;
                    background-color: #f8fafc;
                }}
                .header-area {{
                    background-color: #1e3a8a; color: white; border-radius: 10px;
                    padding: 20px; text-align: center; margin-bottom: 25px;
                }}
                h1 {{ margin: 0; font-size: 26px; font-weight: 800; }}
                .sub {{ margin-top: 6px; font-size: 13px; color: #bfdbfe; }}

                .day-table {{
                    width: 100%; border-collapse: collapse; margin-top: 25px; margin-bottom: 10px;
                }}
                .day-header {{
                    background-color: #e2e8f0; color: #0f172a; padding: 10px 14px;
                    font-size: 16px; font-weight: 800; border-radius: 6px;
                    border-left: 6px solid #2563eb;
                }}
                .day-date {{
                    float: right; color: #64748b; font-size: 13px; font-weight: 600;
                }}

                .card-table {{
                    width: 100%; border-collapse: collapse; margin-bottom: 16px;
                    background: white; border: 1px solid #e2e8f0; border-radius: 8px;
                }}
                .card-td {{
                    padding: 14px 18px; vertical-align: top;
                }}
                .student-name {{
                    font-size: 17px; font-weight: 800; color: #0f172a;
                }}
                .student-sub {{
                    font-size: 12px; color: #64748b; margin-top: 4px;
                }}
                .badge-span {{
                    background: #fef3c7; color: #92400e; font-size: 11px; font-weight: bold;
                    padding: 3px 8px; border-radius: 12px; border: 1px solid #fde68a; display: inline-block;
                }}
                .time-span {{
                    background: #eff6ff; color: #1d4ed8; font-size: 12px; font-weight: bold;
                    padding: 4px 10px; border-radius: 12px; border: 1px solid #bfdbfe;
                }}
                .deadline-span {{
                    background: #fef2f2; color: #b91c1c; font-size: 12px; font-weight: bold;
                    padding: 4px 10px; border-radius: 12px; border: 1px solid #fecaca;
                }}
                .task-list {{
                    margin: 8px 0 0 0; padding-left: 20px; font-size: 14px; color: #334155; line-height: 1.6;
                }}
                .btn-link {{
                    display: inline-block; padding: 6px 12px; background: #16a34a; color: white !important;
                    text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; margin-right: 6px;
                }}
                .btn-call {{
                    display: inline-block; padding: 6px 12px; background: #ffffff; color: #334155 !important;
                    text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: bold; border: 1px solid #cbd5e1;
                }}
                .empty-day {{
                    text-align: center; color: #94a3b8; font-style: italic; padding: 14px; font-size: 13px;
                }}
            </style>
        </head>
        <body>
            <div class="header-area">
                <h1>📱 Haftalık Mobil Cep Ajandası</h1>
                <div class="sub">Oluşturulma: {now_str} • YKS / LGS Asistanı v2</div>
            </div>
        """

        for d_str, day_name in next_7_days:
            events = schedule.get(day_name, [])
            nice_date = f"{d_str.split('-')[2]}.{d_str.split('-')[1]}.{d_str.split('-')[0]}"

            html_out += f"""
            <table class="day-table">
                <tr>
                    <td class="day-header">
                        <span>📅 {day_name}</span>
                        <span class="day-date">{nice_date}</span>
                    </td>
                </tr>
            </table>
            """

            if not events:
                html_out += "<div class='empty-day'>Bugün için planlanmış bir ödev teslimi veya randevu bulunmamaktadır.</div>"
                continue

            for ev in events:
                targets = []
                if ev['tel_ogr']:
                    targets.append(f"Öğr: {ev['tel_ogr']}")
                if ev['tel_veli']:
                    targets.append(f"Veli: {ev['tel_veli']}")
                contact_str = " • ".join(targets) if targets else "İletişim numarası kayıtlı değil"

                # Badges
                is_deadline = (ev["tip"] == "Teslim")
                if is_deadline:
                    t_date = ev["meta"].get("nice_date", nice_date)
                    header_badge = f"<span class='deadline-span'>⏰ {t_date} • 18:00 Teslim</span>"
                    lines_html = "".join([f"<li>{line}</li>" for line in ev["meta"]["lines"]])
                    body_content = f"<ul class='task-list'>{lines_html}</ul>"
                else:
                    header_badge = f"<span class='time-span'>🕒 Saat: {ev['saat']} Randevu</span>"
                    body_content = f"<div style='margin-top:6px; font-size:14px; color:#475569;'>{ev['detay']}</div>"

                badge_html = ""
                if ev["meta"].get("badge"):
                    badge_html = f"<span class='badge-span'>{ev['meta']['badge']} {ev['meta']['smart_note']}</span>"

                stats_html = ""
                if ev["meta"].get("stats"):
                    stats_html = f"<span style='font-size:11px; color:#64748b; margin-left:8px;'>({ev['meta']['stats']})</span>"

                target_num = self._clean(ev["tel_ogr"]) or self._clean(ev["tel_veli"])
                links_html = ""
                if target_num and not for_pdf:
                    msg = self._build_msg_single(ev, day_name, f"{d_str.split('-')[2]}.{d_str.split('-')[1]}")
                    wa_url = f"https://wa.me/{target_num}?text={urllib.parse.quote(msg)}"
                    links_html = f"""
                    <div style="margin-top: 10px;">
                        <a href="{wa_url}" class="btn-link">💬 WhatsApp Raporu</a>
                        <a href="tel:{target_num}" class="btn-call">📞 Ara</a>
                    </div>
                    """

                border_color = ev.get("renk", "#3b82f6")

                html_out += f"""
                <table class="card-table" style="border-left: 6px solid {border_color};">
                    <tr>
                        <td class="card-td">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span class="student-name">{ev['ad']}</span>
                                <span style="float: right;">{header_badge}</span>
                            </div>
                            <div class="student-sub">{contact_str} {stats_html}</div>
                            <div style="margin-top: 6px;">{badge_html}</div>
                            {body_content}
                            {links_html}
                        </td>
                    </tr>
                </table>
                """

        html_out += "</body></html>"
        return html_out

    def _clean(self, t):
        if not t:
            return None
        c = "".join(filter(str.isdigit, str(t)))
        if c.startswith("0"):
            c = "9" + c
        elif len(c) == 10:
            c = "90" + c
        return c

    def _open_file(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception:
            pass
