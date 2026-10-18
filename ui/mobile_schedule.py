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
    QFileDialog, QMessageBox, QScrollArea
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
        
        # Düşük çözünürlüklü Windows ekranları (1366x768 vb.) için dinamik boyutlandırma
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(1000, max(760, int(avail.width() * 0.92)))
            target_h = min(740, max(480, int(avail.height() * 0.88)))
            self.resize(target_w, target_h)
            self.move(avail.x() + (avail.width() - target_w) // 2,
                      avail.y() + (avail.height() - target_h) // 2)
        else:
            self.resize(940, 640)

        self._current_html = ""
        self._setup_ui()
        self._refresh_preview()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        # Header Banner
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #1e40af);
                border-radius: 8px;
                padding: 10px 14px;
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

        self.chk_all_students = QCheckBox("Tüm Aktif Öğrenciler (Haftalık Karneli)")
        self.chk_all_students.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #475569; margin-left: 6px;")
        self.chk_all_students.stateChanged.connect(self._refresh_preview)
        toolbar.addWidget(self.chk_all_students)

        self.chk_deep_analytics = QCheckBox("📊 360° Akademik Analiz & 6 Akıllı Buton")
        self.chk_deep_analytics.setChecked(True)
        self.chk_deep_analytics.setToolTip("Her öğrenci kartına ders bazlı başarı analizi, darboğaz tespiti ve 6 farklı tek tıkla WhatsApp/Arama butonu ekler")
        self.chk_deep_analytics.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #1d4ed8; margin-left: 6px;")
        self.chk_deep_analytics.stateChanged.connect(self._refresh_preview)
        toolbar.addWidget(self.chk_deep_analytics)

        toolbar.addStretch()

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;
                padding: 6px 14px; font-weight: bold; color: #334155;
            }
            QPushButton:hover { background-color: #e2e8f0; 
                color: #15191E;}
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
            
                color: #15191E;}
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
            QPushButton:hover { background-color: #0e7490; 
                color: #FFFFFF;}
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
            QPushButton:hover { background-color: #e2e8f0; 
                color: #15191E;}
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
            QPushButton:hover { background-color: #1d4ed8; 
                color: #FFFFFF;}
        """)
        self.btn_pdf.clicked.connect(self._save_pdf)
        btn_layout.addWidget(self.btn_pdf)

        self.btn_wa_self = QPushButton("📲 PDF Kaydet & WhatsApp'ı Aç")
        self.btn_wa_self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_wa_self.setToolTip("PDF'i kaydeder, dosya konumunu gösterir ve telefona atabilmeniz için WhatsApp Web'i açar")
        self.btn_wa_self.setStyleSheet("""
            QPushButton {
                background-color: #16a34a; color: white; font-weight: bold; font-size: 13px;
                padding: 10px 18px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #15803d;
                color: #FFFFFF;}
        """)
        self.btn_wa_self.clicked.connect(self._save_pdf_and_open_whatsapp)
        btn_layout.addWidget(self.btn_wa_self)

        btn_close = QPushButton("Kapat")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0; color: #475569; font-weight: bold; font-size: 13px;
                padding: 10px 16px; border-radius: 8px; border: none;
            }
            QPushButton:hover { background-color: #cbd5e1; 
                color: #15191E;}
        """)
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_close)

        main_layout.addLayout(btn_layout)

    def _refresh_preview(self):
        grp = self.cbx_group.currentText()
        all_st = self.chk_all_students.isChecked()
        inc_an = self.chk_deep_analytics.isChecked()
        schedule, next_7_days = self.generator._fetch_data(group_filter=grp, include_all_active=all_st)
        self._current_html = self.generator._build_html(schedule, next_7_days, for_pdf=False, include_analytics=inc_an)
        self.viewer.setHtml(self._current_html)

    def _export_pdf_to_path(self, fn: str):
        grp = self.cbx_group.currentText()
        all_st = self.chk_all_students.isChecked()
        inc_an = self.chk_deep_analytics.isChecked()
        schedule, next_7_days = self.generator._fetch_data(group_filter=grp, include_all_active=all_st)
        pdf_html = self.generator._build_html(schedule, next_7_days, for_pdf=True, include_analytics=inc_an)

        # 1. Öncelik: QtWebEngine (Chromium) PDF Motoru
        # Önizleme ekranındaki tüm renkli emojileri, yuvarlatılmış köşeleri, sol durum şeritlerini,
        # sayfa bölünme korumalarını (break-inside: avoid) ve tıklanabilir WhatsApp/Arama linklerini
        # birebir aynı görsel kalitede PDF'e aktarır.
        webengine_ok = False
        try:
            from PyQt6.QtCore import QEventLoop, QMarginsF
            from PyQt6.QtGui import QPageLayout, QPageSize
            from PyQt6.QtWebEngineCore import QWebEnginePage

            if os.path.exists(fn):
                try:
                    os.remove(fn)
                except Exception:
                    pass

            page = QWebEnginePage(self)
            loop = QEventLoop(self)
            state = {"done": False, "ok": False}

            def _on_load(ok: bool):
                if not ok:
                    state["done"] = True
                    loop.quit()
                    return
                layout = QPageLayout(
                    QPageSize(QPageSize.PageSizeId.A4),
                    QPageLayout.Orientation.Portrait,
                    QMarginsF(8, 8, 8, 8),
                )
                page.printToPdf(fn, layout)

            def _on_pdf_done(_path: str, ok: bool):
                state["ok"] = bool(ok)
                state["done"] = True
                loop.quit()

            page.loadFinished.connect(_on_load)
            page.pdfPrintingFinished.connect(_on_pdf_done)
            QTimer.singleShot(15000, loop.quit)
            page.setHtml(pdf_html)
            loop.exec()
            page.deleteLater()

            if state["ok"] and os.path.exists(fn) and os.path.getsize(fn) > 1024:
                webengine_ok = True
        except Exception as e:
            print(f"[MobileSchedule] WebEngine PDF fallback notice: {e}")

        if webengine_ok:
            return

        # 2. Yedek Motor: QPrinter (ScreenResolution + Point)
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(fn)

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Arial", 10))
        page_rect = printer.pageRect(QPrinter.Unit.Point)
        if page_rect.width() > 0 and page_rect.height() > 0:
            doc.setPageSize(QSizeF(page_rect.size()))
        doc.setHtml(pdf_html)
        doc.print(printer)

    def _reveal_in_file_manager(self, fn: str):
        """Kaydedilen PDF dosyasını Finder / Windows Explorer'da seçili olarak gösterir."""
        try:
            norm_fn = os.path.abspath(fn)
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", norm_fn])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", f"/select,{norm_fn}"])
        except Exception:
            pass

    def _save_pdf(self):
        default_name = f"cep_ajandasi_{datetime.date.today().strftime('%Y_%m_%d')}.pdf"
        fn, _ = QFileDialog.getSaveFileName(self, "PDF Ajanda Kaydet", default_name, "PDF Dosyası (*.pdf)")
        if not fn:
            return
        try:
            self._export_pdf_to_path(fn)
            self.generator._open_file(fn)
            self._reveal_in_file_manager(fn)
            QMessageBox.information(
                self,
                "Başarılı",
                f"Akıllı Mobil PDF Ajanda başarıyla oluşturuldu ve açıldı:\n{fn}\n\n"
                "💡 Dosya klasörde seçili hale getirildi. Bu PDF'i WhatsApp'tan kendinize göndererek\n"
                "telefonunuzdan her öğrencinin altındaki 6 akıllı butonu tek dokunuşla kullanabilirsiniz."
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı:\n{e}")

    def _save_pdf_and_open_whatsapp(self):
        default_name = f"cep_ajandasi_{datetime.date.today().strftime('%Y_%m_%d')}.pdf"
        fn, _ = QFileDialog.getSaveFileName(self, "PDF Ajandayı Kaydet ve WhatsApp'ı Aç", default_name, "PDF Dosyası (*.pdf)")
        if not fn:
            return
        try:
            self._export_pdf_to_path(fn)
            self._reveal_in_file_manager(fn)
            # Masaüstü WhatsApp uygulaması varsa onu öne getir, yoksa WhatsApp Web aç
            opened_native = False
            if sys.platform == "darwin" and (os.path.exists("/Applications/WhatsApp.app") or os.path.exists("/Applications/WhatsApp 2.app")):
                try:
                    subprocess.Popen(["open", "-a", "WhatsApp"])
                    opened_native = True
                except Exception:
                    pass
            if not opened_native:
                webbrowser.open("https://web.whatsapp.com/")
            QMessageBox.information(
                self,
                "PDF Hazır & Klasörde Seçildi",
                f"Yeni 6 Butonlu 360° PDF kaydedildi:\n{fn}\n\n"
                "📂 Dosya Finder/Klasör penceresinde seçili olarak açıldı.\n"
                "📲 Seçili olan bu yeni PDF dosyasını doğrudan WhatsApp sohbetinize sürükleyip gönderin!"
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"İşlem tamamlanamadı:\n{e}")

    def _print_schedule(self):
        try:
            printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
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
        
        # Düşük çözünürlüklü ekranlar için dinamik boyut
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(1050, max(760, int(avail.width() * 0.92)))
            target_h = min(720, max(480, int(avail.height() * 0.88)))
            self.resize(target_w, target_h)
            self.move(avail.x() + (avail.width() - target_w) // 2,
                      avail.y() + (avail.height() - target_h) // 2)
        else:
            self.resize(960, 600)

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
            
                color: #15191E;}
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
            
                color: #15191E;}
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
            QPushButton:hover { background-color: #15803d; 
                color: #FFFFFF;}
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
            QPushButton:hover { background-color: #e2e8f0; 
                color: #15191E;}
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
            QPushButton:hover { background-color: #1d4ed8; 
                color: #FFFFFF;}
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
            
                color: #15191E;}
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
            QPushButton:hover { background-color: #15803d; 
                color: #FFFFFF;}
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
            QPushButton:hover { background-color: #0e7490; 
                color: #FFFFFF;}
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
        self.setFixedWidth(520)

        # Düşük çözünürlüklü Windows ekranları için dikey sınır ve ortalama
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            max_h = min(620, max(440, int(avail.height() * 0.88)))
            self.setMaximumHeight(max_h)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Area
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e3a8a);
                border-radius: 10px;
                padding: 12px 16px;
            }
        """)
        h_layout = QVBoxLayout(header)
        h_layout.setSpacing(3)
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

        scroll.setWidget(content_widget)
        root_layout.addWidget(scroll)


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
            pct = int(round((done / total) * 100)) if total > 0 else 0
            return f"✅ {done} / 📋 {total} (%{pct})" if total > 0 else "✅ 0 / 📋 0"
        except Exception:
            return "Veri yok"

    def _get_overdue_count(self, sid: int) -> int:
        if not sid:
            return 0
        try:
            r = self.con.execute("""
                SELECT COUNT(*) FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE o.ogrenci_id=? AND o.durum='devam' AND date(k.bitis_tarihi) < date('now')
            """, (sid,)).fetchone()
            return int(r[0] or 0) if r else 0
        except Exception:
            return 0

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

        scheduled_student_ids = set()

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
                scheduled_student_ids.add(r["id"])
                status, badge_icon, smart_note = self._analyze_student(r["id"])
                schedule[gun].append({
                    "oid": r["id"],
                    "ad": f"{r['ad']} {r['soyad']}",
                    "grup": f"{r['ana_grup'] or ''} {r['alt_grup'] or ''}".strip(),
                    "tel_ogr": r["ogr_tel"],
                    "tel_veli": r["veli_tel1"],
                    "saat": r["kocluk_saati"] or "??:??",
                    "tip": "Görüşme",
                    "detay": "Haftalık Birebir Koçluk & Değerlendirme Görüşmesi",
                    "renk": self.COLOR_MEETING,
                    "meta": {
                        "lines": [],
                        "notes": [],
                        "badge": badge_icon,
                        "smart_note": smart_note,
                        "status": status,
                        "stats": self._get_mini_stats(r["id"]),
                        "overdue": self._get_overdue_count(r["id"]),
                    }
                })

        # 2. Ödev Teslimleri
        end_date = next_7_days[-1][0]
        rows_odev = self.con.execute("""
            SELECT k.bitis_tarihi, o.id as oid, o.ad, o.soyad, o.ogr_tel, o.veli_tel1, o.ana_grup, o.alt_grup, k.aciklama,
                   GROUP_CONCAT(COALESCE(os.ders,'') || '|' || COALESCE(os.kitap_ad,'') || '|' || COALESCE(os.konu_ad,'Genel'), '$$$') as icerik_raw
            FROM odev_kume k
            JOIN ogrenci o ON o.id = k.ogrenci_id
            LEFT JOIN odev os ON os.kume_id = k.id
            WHERE o.aktif=1 AND date(k.bitis_tarihi) BETWEEN date(?) AND date(?)
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

                scheduled_student_ids.add(r["oid"])
                lines = self._parse_icerik_raw(r["icerik_raw"] or "")
                notes = [r["aciklama"]] if r["aciklama"] else []
                status, badge_icon, smart_note = self._analyze_student(r["oid"])
                stats_text = self._get_mini_stats(r["oid"])

                card_color = self._status_color(status)

                schedule[day_name].append({
                    "oid": r["oid"],
                    "ad": f"{r['ad']} {r['soyad']}",
                    "grup": f"{r['ana_grup'] or ''} {r['alt_grup'] or ''}".strip(),
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
                        "stats": stats_text,
                        "overdue": self._get_overdue_count(r["oid"]),
                    }
                })
            except Exception:
                continue

        # 3. Merging Deadlines per day
        self._merge_deadlines(schedule)

        # 4. Tüm Aktif Öğrencileri Göster (Haftalık Karneli) seçeneği işaretliyse:
        # Bu hafta takvimde teslimi olmayan aktif öğrencileri de son ödev/telafi karneleriyle ekle
        if include_all_active:
            karne_key = "📊 Haftalık Genel Karne & Telafi Takibi"
            schedule[karne_key] = []
            next_7_days.append((today.strftime("%Y-%m-%d"), karne_key))

            all_rows = self.con.execute("""
                SELECT id, ad, soyad, ogr_tel, veli_tel1, ana_grup, alt_grup
                FROM ogrenci
                WHERE aktif=1
                ORDER BY ad, soyad
            """).fetchall()

            for st in all_rows:
                if group_filter != "Tümü" and st["ana_grup"] != group_filter:
                    continue
                if st["id"] in scheduled_student_ids:
                    continue

                # Öğrencinin bekleyen/geciken veya son verilen ödevlerini çek
                pend_rows = self.con.execute("""
                    SELECT COALESCE(os.ders,'') || '|' || COALESCE(os.kitap_ad,'') || '|' || COALESCE(os.konu_ad,'Genel') as raw_item
                    FROM odev os
                    JOIN odev_kume k ON k.id = os.kume_id
                    WHERE os.ogrenci_id=? AND os.durum='devam'
                    ORDER BY date(k.bitis_tarihi) DESC
                    LIMIT 8
                """, (st["id"],)).fetchall()
                raw_joined = "$$$".join([pr["raw_item"] for pr in pend_rows if pr["raw_item"]])
                lines = self._parse_icerik_raw(raw_joined)
                if not lines:
                    lines = ["Aktif bekleyen ödev kaydı bulunmuyor (Genel haftalık takip)."]

                status, badge_icon, smart_note = self._analyze_student(st["id"])
                schedule[karne_key].append({
                    "oid": st["id"],
                    "ad": f"{st['ad']} {st['soyad']}",
                    "grup": f"{st['ana_grup'] or ''} {st['alt_grup'] or ''}".strip(),
                    "tel_ogr": st["ogr_tel"],
                    "tel_veli": st["veli_tel1"],
                    "saat": "Genel",
                    "tip": "Teslim",
                    "renk": self._status_color(status),
                    "meta": {
                        "lines": lines,
                        "notes": [],
                        "nice_date": today.strftime("%d.%m.%Y"),
                        "status": status,
                        "badge": badge_icon or "📊",
                        "smart_note": smart_note or "Haftalık Genel Durum Karnesi",
                        "stats": self._get_mini_stats(st["id"]),
                        "overdue": self._get_overdue_count(st["id"]),
                    }
                })

        # 5. Sorting
        for day in schedule:
            schedule[day].sort(key=lambda x: (x["saat"], x["ad"]))

        return schedule, next_7_days

    @staticmethod
    def _tr_title(text: str) -> str:
        if not text:
            return ""
        cleaned = str(text).replace("_", " ").strip()
        return cleaned.replace("İ", "i").replace("I", "ı").title().replace("\u0307", "")

    def _parse_icerik_raw(self, raw_str: str) -> List[str]:
        lines = []
        if not raw_str:
            return lines
        for item in raw_str.split("$$$"):
            parts = item.split("|")
            if len(parts) >= 3:
                d, k, kn = parts[0], parts[1], parts[2]
                d_clean = self._tr_title(d) if d else ""
                k_clean = self._tr_title(k) if k else ""
                kn_clean = kn.replace('_', ' ').strip().replace("\u0307", "")
                if kn_clean == "Genel":
                    kn_clean = ""
                if kn_clean:
                    kn_clean = kn_clean[0].upper() + kn_clean[1:]

                line = d_clean
                if k_clean:
                    line += f" - {k_clean}"
                if kn_clean:
                    line += f" - {kn_clean}"
                if line and line not in lines:
                    lines.append(line)
        return lines

    def _status_color(self, status: str) -> str:
        if status == "star":
            return "#f59e0b"
        if status == "risk":
            return "#ef4444"
        if status == "marathon":
            return "#3b82f6"
        if status == "steady":
            return "#10b981"
        if status == "silent":
            return "#64748b"
        return self.COLOR_DEADLINE

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
                    for l in ev["meta"]["lines"]:
                        if l not in base["meta"]["lines"]:
                            base["meta"]["lines"].append(l)
                    for n in ev["meta"]["notes"]:
                        if n not in base["meta"]["notes"]:
                            base["meta"]["notes"].append(n)
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
        stats_txt = ev["meta"].get("stats", "")
        overdue_cnt = ev["meta"].get("overdue", 0)
        perf_line = f"\n📊 *Son 14 Gün Performansın:* {stats_txt}" if stats_txt and stats_txt != "Veri yok" else ""
        if overdue_cnt > 0:
            perf_line += f"\n⚠️ *Bekleyen Telafi Ödevin:* {overdue_cnt} adet"

        if ev["tip"] == "Görüşme":
            return (
                f"Merhaba {ev['ad']}, 👋\n\n"
                f"📅 *{day_name} ({d_nice}) Saat {ev['saat']}* için haftalık birebir koçluk görüşmemiz planlanmıştır."
                f"{perf_line}\n\n"
                f"Hazırlıklarınla birlikte görüşmek üzere, başarılar dilerim! 🚀"
            )
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
                notes_str = "\n\n📌 *Koç Notu:* " + ", ".join(ev["meta"]["notes"])

            return (
                f"{intro}\n\n"
                f"📅 *{day_name} ({t_date}) Teslim Programın:*\n\n"
                f"{tasks}{notes_str}{perf_line}\n\n"
                f"İyi çalışmalar ve başarılar dilerim! 📚"
            )

    def _build_parent_msg(self, ev, day_name, d_nice):
        t_date = ev["meta"].get("nice_date", d_nice)
        stats_txt = ev["meta"].get("stats", "")
        overdue_cnt = ev["meta"].get("overdue", 0)
        perf_line = f"\n📊 *Son 14 Gün Ödev Tamamlama:* {stats_txt}" if stats_txt and stats_txt != "Veri yok" else ""
        if overdue_cnt > 0:
            perf_line += f"\n⚠️ *Teslim Tarihi Geçmiş Telafi Ödevi:* {overdue_cnt} adet"

        if ev["tip"] == "Görüşme":
            return (
                f"Sayın Velimiz,\n\n"
                f"Öğrencimiz *{ev['ad']}* ile *{day_name} ({d_nice}) Saat {ev['saat']}* haftalık koçluk randevumuz bulunmaktadır."
                f"{perf_line}\n\n"
                f"Bilginize sunar, iyi günler dileriz."
            )
        else:
            tasks = "\n".join([f"  • {l}" for l in ev["meta"]["lines"]])
            return (
                f"Sayın Velimiz,\n\n"
                f"Öğrencimiz *{ev['ad']}*'in *{day_name} ({t_date})* günü teslim etmesi gereken ödev programı aşağıdadır:\n\n"
                f"{tasks}{perf_line}\n\n"
                f"Öğrencimizin çalışmalarını evde desteklemenizi rica eder, iyi günler dileriz."
            )

    def _get_student_360_analytics(self, sid: int) -> Dict[str, Any]:
        """Öğrencinin ders bazlı başarı dağılımını, darboğaz dersini, geciken konularını,
        deneme/hedef durumunu ve V3.5.40 ortak karar motoru önerisini hesaplar."""
        result: Dict[str, Any] = {
            "total_all": 0,
            "done_all": 0,
            "pct_all": 0,
            "late_all": 0,
            "subjects": [],
            "strongest_subject": "",
            "bottleneck_subject": "",
            "late_topics": [],
            "latest_exam": "",
            "target_info": "",
            "coach_advice": "",
        }
        if not sid:
            return result
        try:
            # 1. Genel ve ders bazlı ödev dağılımı
            subj_rows = self.con.execute("""
                SELECT COALESCE(o.ders, 'Genel') as ders,
                       SUM(CASE WHEN o.durum IN ('tamam','yapildi') THEN 1 ELSE 0 END) as done_cnt,
                       SUM(CASE WHEN o.durum='devam' AND date(k.bitis_tarihi) < date('now') THEN 1 ELSE 0 END) as late_cnt,
                       COUNT(*) as total_cnt
                FROM odev o
                JOIN odev_kume k ON k.id = o.kume_id
                WHERE o.ogrenci_id=? AND COALESCE(o.silindi, 0)=0
                GROUP BY COALESCE(o.ders, 'Genel')
                ORDER BY total_cnt DESC
            """, (sid,)).fetchall()

            total_all = sum(int(r["total_cnt"] or 0) for r in subj_rows)
            done_all = sum(int(r["done_cnt"] or 0) for r in subj_rows)
            late_all = sum(int(r["late_cnt"] or 0) for r in subj_rows)
            pct_all = int(round((done_all / total_all) * 100)) if total_all > 0 else 0

            result["total_all"] = total_all
            result["done_all"] = done_all
            result["late_all"] = late_all
            result["pct_all"] = pct_all

            subjects_list = []
            for r in subj_rows:
                d_raw = self._tr_title(str(r["ders"] or "Genel"))
                d_cnt = int(r["done_cnt"] or 0)
                l_cnt = int(r["late_cnt"] or 0)
                t_cnt = int(r["total_cnt"] or 0)
                s_pct = int(round((d_cnt / t_cnt) * 100)) if t_cnt > 0 else 0
                subjects_list.append({
                    "ders": d_raw,
                    "done": d_cnt,
                    "late": l_cnt,
                    "total": t_cnt,
                    "pct": s_pct,
                })
            result["subjects"] = subjects_list[:5]

            if subjects_list:
                # En güçlü ders
                with_done = [s for s in subjects_list if s["done"] > 0]
                if with_done:
                    best = max(with_done, key=lambda x: (x["pct"], x["done"]))
                    result["strongest_subject"] = f"{best['ders']} (%{best['pct']} • {best['done']}/{best['total']})"
                # Darboğaz / En çok aksayan ders
                with_late = [s for s in subjects_list if s["late"] > 0]
                if with_late:
                    worst = max(with_late, key=lambda x: (x["late"], -x["pct"]))
                    result["bottleneck_subject"] = f"{worst['ders']} ({worst['late']} Gecikmiş • %{worst['pct']})"
                else:
                    lowest = min(subjects_list, key=lambda x: (x["pct"], -x["total"]))
                    if lowest["pct"] < 80:
                        result["bottleneck_subject"] = f"{lowest['ders']} (%{lowest['pct']} Tamamlama)"

            # 2. Geciken spesifik konular (Telafi listesi)
            late_rows = self.con.execute("""
                SELECT COALESCE(o.ders,'') as ders, COALESCE(o.kitap_ad,'') as kitap, COALESCE(o.konu_ad,'') as konu
                FROM odev o
                JOIN odev_kume k ON k.id = o.kume_id
                WHERE o.ogrenci_id=? AND o.durum='devam' AND date(k.bitis_tarihi) < date('now') AND COALESCE(o.silindi, 0)=0
                ORDER BY date(k.bitis_tarihi) DESC
                LIMIT 12
            """, (sid,)).fetchall()
            seen_topics = []
            for lr in late_rows:
                d_c = self._tr_title(str(lr["ders"] or ""))
                k_c = self._tr_title(str(lr["kitap"] or ""))
                kn_c = str(lr["konu"] or "").replace("_", " ").strip().replace("\u0307", "")
                t_item = " - ".join([p for p in (d_c, k_c, kn_c) if p and p != "Genel"])
                if t_item and t_item not in seen_topics:
                    seen_topics.append(t_item)
                if len(seen_topics) >= 5:
                    break
            result["late_topics"] = seen_topics

            # 3. Öğrenci hedef ve son deneme bilgisi
            st_row = self.con.execute("""
                SELECT hedef_bolum, hedef_tyt, hedef_ayt, hedef_lgs
                FROM ogrenci WHERE id=?
            """, (sid,)).fetchone()
            if st_row:
                h_parts = []
                if st_row["hedef_bolum"]:
                    h_parts.append(str(st_row["hedef_bolum"]))
                if st_row["hedef_tyt"]:
                    h_parts.append(f"TYT Hedef: {st_row['hedef_tyt']} Net")
                if st_row["hedef_ayt"]:
                    h_parts.append(f"AYT Hedef: {st_row['hedef_ayt']} Net")
                if st_row["hedef_lgs"]:
                    h_parts.append(f"LGS Hedef: {st_row['hedef_lgs']} Puan/Net")
                result["target_info"] = " • ".join(h_parts)

            ex_row = self.con.execute("""
                SELECT dm.deneme_adi, dm.tur, dm.tarih, SUM(ds.net) as top_net
                FROM deneme_sonuclari ds
                JOIN denemeler dm ON dm.id = ds.deneme_id
                WHERE ds.ogrenci_id=?
                GROUP BY ds.deneme_id
                ORDER BY date(dm.tarih) DESC
                LIMIT 1
            """, (sid,)).fetchone()
            if ex_row and ex_row["top_net"] is not None:
                result["latest_exam"] = f"{ex_row['deneme_adi']} ({ex_row['tur']}): {float(ex_row['top_net']):.2f} Net"

            # 4. V3.5.40 Ortak Akademik Karar & Eylem Önerisi
            try:
                from services.academic_actions_v3536 import read_student_action_card
                act_card = read_student_action_card(self.con, sid)
                if isinstance(act_card, dict) and act_card.get("next_step"):
                    result["coach_advice"] = str(act_card["next_step"])
            except Exception:
                pass

            if not result["coach_advice"]:
                if late_all > 0 and result["bottleneck_subject"]:
                    result["coach_advice"] = f"{result['bottleneck_subject']} alanında biriken görevler için öncelikli telafi etüdü uygulanmalı."
                elif pct_all >= 75:
                    result["coach_advice"] = "Genel ödev disiplini yüksek; deneme net artışı ve süre odaklı soru çözümüne ağırlık verilebilir."
                else:
                    result["coach_advice"] = "Günlük soru çözüm rutini ve teslim saatlerine uyum yakından takip edilmeli."

        except Exception as e:
            print(f"[MobileSchedule] 360 analytics error for {sid}: {e}")
        return result

    def _build_academic_analysis_msg(self, ev: Dict[str, Any], an: Dict[str, Any], day_name: str, d_nice: str) -> str:
        """Buton 4: Öğrenci veya Veliye gönderilebilecek Profesyonel 360° Akademik Analiz Raporu"""
        stats_14 = ev["meta"].get("stats", "Veri yok")
        subj_lines = []
        for s in an.get("subjects", []):
            late_tag = f" (⚠️ {s['late']} Gecikmiş)" if s["late"] > 0 else " (✅ Tamam)" if s["pct"] >= 80 else ""
            subj_lines.append(f"  ▪ *{s['ders']}:* %{s['pct']} Başarı ({s['done']}/{s['total']} Görev){late_tag}")
        subj_block = "\n".join(subj_lines) if subj_lines else "  ▪ Henüz ders bazlı ödev verisi oluşmadı."

        extra_lines = []
        if an.get("strongest_subject"):
            extra_lines.append(f"🌟 *En Güçlü Ders:* {an['strongest_subject']}")
        if an.get("bottleneck_subject"):
            extra_lines.append(f"🔎 *Odaklanılacak Darboğaz Ders:* {an['bottleneck_subject']}")
        if an.get("latest_exam"):
            extra_lines.append(f"📝 *Son Deneme Performansı:* {an['latest_exam']}")
        if an.get("target_info"):
            extra_lines.append(f"🎯 *Hedef:* {an['target_info']}")
        extra_block = "\n".join(extra_lines)

        advice = an.get("coach_advice") or "Düzenli tekrar ve zamanında ödev teslimine devam edelim."
        grup_str = f" ({ev.get('grup')})" if ev.get("grup") else ""

        return (
            f"🧭 *KOÇPİLOT 360 — AKADEMİK ANALİZ & PERFORMANS KARNESİ*\n"
            f"👤 *Öğrenci:* {ev['ad']}{grup_str}\n"
            f"📅 *Rapor Tarihi:* {day_name} ({d_nice})\n"
            f"──────────────────────────\n"
            f"📈 *Genel Ödev Disiplini:* %{an['pct_all']} ({an['done_all']} Tamamlanan / {an['total_all']} Toplam)\n"
            f"⚡ *Son 14 Gün Temposu:* {stats_14}\n"
            f"{extra_block}\n\n"
            f"📚 *DERS BAZLI BAŞARI DAĞILIMI:*\n"
            f"{subj_block}\n\n"
            f"🧠 *Koç Değerlendirmesi & Stratejik Hedef:*\n"
            f"{advice}\n\n"
            f"İyi çalışmalar ve başarılar dilerim! 🚀"
        )

    def _build_recovery_plan_msg(self, ev: Dict[str, Any], an: Dict[str, Any], day_name: str, d_nice: str) -> str:
        """Buton 5: Geciken / Eksik Konular İçin Kişisel Telafi Reçetesi (veya Gecikme Yoksa Tebrik)"""
        late_cnt = an.get("late_all", 0)
        late_topics = an.get("late_topics", [])
        if late_cnt > 0:
            topics_str = "\n".join([f"  🔸 {t}" for t in late_topics]) if late_topics else "  🔸 Sistemdeki teslim tarihi geçmiş açık ödevler"
            bottleneck = an.get("bottleneck_subject") or "aksayan dersler"
            return (
                f"⚠️ *KOÇPİLOT 360 — KİŞİSEL TELAFİ & EYLEM PLANI*\n"
                f"Merhaba *{ev['ad']}*,\n\n"
                f"Sistem analizimizde teslim tarihi geçmiş toplam *{late_cnt} adet* açık görev ve özellikle *{bottleneck}* alanında birikme tespit edildi.\n\n"
                f"📌 *Öncelikli Telafi Edilecek Konular:*\n"
                f"{topics_str}\n\n"
                f"🛠️ *3 Adımlı Telafi Reçeten:*\n"
                f"1️⃣ Bugün güncel ödevinin yanına yukarıdaki listeden en az 1 eksik konuyu ekle.\n"
                f"2️⃣ Çözemediğin soruları işaretle ve koçluk görüşmemize getir.\n"
                f"3️⃣ Tamamladığın her telafi görevini bana WhatsApp'tan bildir.\n\n"
                f"Seninle bu eksikleri hızla kapatacağız, sana güveniyorum! 💪📚"
            )
        else:
            return (
                f"🌟 *KOÇPİLOT 360 — ÜSTÜN DİSİPLİN & MOTİVASYON MESAJI*\n"
                f"Tebrikler *{ev['ad']}*! 👏\n\n"
                f"Sistemde teslim tarihi geçmiş *hiçbir eksik ödevin bulunmuyor* (Genel Başarı: *%{an['pct_all']}* • {an['done_all']}/{an['total_all']} görev).\n\n"
                f"🚀 *Bu Haftaki İleri Seviye Hedefin:*\n"
                f"• Branş denemelerinde süre tutarak hız kazanmak,\n"
                f"• Yanlış ve boş soruların video/konu analizlerini aynı gün tamamlamak.\n\n"
                f"Harika disiplinin için seni kutluyorum, zirveye doğru aynen devam! 🏆🔥"
            )

    def _build_parent_executive_report_msg(self, ev: Dict[str, Any], an: Dict[str, Any], day_name: str, d_nice: str) -> str:
        """Buton 6: Veliye Özel Detaylı 360° Gelişim & Takip Karnesi"""
        stats_14 = ev["meta"].get("stats", "Veri yok")
        subj_lines = []
        for s in an.get("subjects", [])[:4]:
            subj_lines.append(f"  • {s['ders']}: %{s['pct']} tamamlanma ({s['done']}/{s['total']} ödev)")
        subj_block = "\n".join(subj_lines) if subj_lines else "  • Ders bazlı ödev takibi devam etmektedir."

        late_cnt = an.get("late_all", 0)
        if late_cnt > 0:
            late_info = f"⚠️ *Telafi Bekleyen Görev:* {late_cnt} adet (Öncelikli ders: {an.get('bottleneck_subject', 'Belirlendi')})"
            home_tip = "Öğrencimizin biriken telafi ödevlerini bu hafta içinde eritebilmesi için evdeki çalışma saatlerini desteklemenizi rica ederiz."
        else:
            late_info = "✅ *Geciken Ödev Durumu:* Süresi geçmiş eksik ödevi bulunmamaktadır. Tebrik ederiz!"
            home_tip = "Öğrencimiz ödevlerini zamanında ve düzenli olarak tamamlamaktadır. Gösterdiğiniz ilgi ve destek için teşekkür ederiz."

        exam_line = f"\n📝 *Son Deneme Sonucu:* {an['latest_exam']}" if an.get("latest_exam") else ""

        return (
            f"📋 *SAYIN VELİMİZ — HAFTALIK 360° ÖĞRENCİ GELİŞİM KARNESİ*\n\n"
            f"Öğrencimiz *{ev['ad']}* için güncel akademik takip ve çalışma analizi aşağıda bilgilerinize sunulmuştur:\n"
            f"──────────────────────────\n"
            f"📊 *Genel Ödev Tamamlama:* %{an['pct_all']} ({an['done_all']} / {an['total_all']} Görev)\n"
            f"🗓️ *Son 14 Gün Performansı:* {stats_14}\n"
            f"{late_info}{exam_line}\n\n"
            f"📚 *Ders Bazlı Çalışma Özeti:*\n"
            f"{subj_block}\n\n"
            f"💡 *Koçluk Değerlendirmesi:*\n"
            f"{home_tip}\n\n"
            f"İyi günler dileriz. 🙏"
        )

    # --- HTML Builder for PDF / Browser ---
    def _build_html(self, schedule, next_7_days, for_pdf=False, include_analytics=True):
        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        op_stats = self._get_operational_summary()

        # Toplam hafta içi kart sayısı
        total_cards = sum(len(schedule.get(dn, [])) for _, dn in next_7_days)
        analytics_cache: Dict[int, Dict[str, Any]] = {}

        html_out = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4 portrait;
                    margin: 8mm;
                }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, Helvetica, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji';
                    color: #0f172a; margin: 0; padding: 10px;
                    background-color: #f8fafc;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
                a {{ text-decoration: none; }}
                .day-header {{
                    page-break-after: avoid;
                    break-after: avoid;
                    margin-top: 16px;
                    margin-bottom: 10px;
                }}
                .student-card {{
                    page-break-inside: avoid;
                    break-inside: avoid;
                    margin-bottom: 14px;
                }}
                .btn-bar {{
                    page-break-inside: avoid;
                    break-inside: avoid;
                }}
            </style>
        </head>
        <body>
            <!-- ÜST KURUMSAL BAŞLIK (KOÇPİLOT 360) -->
            <table width="100%" cellspacing="0" cellpadding="0" bgcolor="#0f172a" style="border-radius: 10px; margin-bottom: 12px;">
                <tr>
                    <td style="padding: 18px 20px;">
                        <table width="100%" cellspacing="0" cellpadding="0">
                            <tr>
                                <td align="left" valign="middle">
                                    <div style="font-size: 22px; font-weight: 900; color: #ffffff;">
                                        🧭 KoçPilot 360 — Haftalık Akıllı Mobil Cep Ajandası &amp; Analiz Paketi
                                    </div>
                                    <div style="font-size: 12px; color: #93c5fd; margin-top: 4px;">
                                        Oluşturulma: {now_str} • Bütünleşik Koçluk, Ödev &amp; 360° Akademik Analiz Platformu (v3.5.41)
                                    </div>
                                </td>
                                <td align="right" valign="middle">
                                    <span style="background-color: #1e3a8a; color: #38bdf8; font-size: 11px; font-weight: bold; padding: 5px 10px; border-radius: 6px;">
                                        📲 6 AKILLI BUTONLU MOBİL PDF
                                    </span>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>

            <!-- OPERASYONEL ÖZET ŞERİDİ -->
            <table width="100%" cellspacing="4" cellpadding="0" style="margin-bottom: 12px;">
                <tr>
                    <td width="25%" bgcolor="#eff6ff" align="center" style="padding: 10px; border: 1px solid #bfdbfe; border-radius: 8px;">
                        <div style="font-size: 16px; font-weight: 900; color: #1d4ed8;">📅 {op_stats['today_deadlines']}</div>
                        <div style="font-size: 10px; font-weight: bold; color: #475569; margin-top: 2px;">BUGÜN TESLİM</div>
                    </td>
                    <td width="25%" bgcolor="#f0fdfa" align="center" style="padding: 10px; border: 1px solid #99f6e4; border-radius: 8px;">
                        <div style="font-size: 16px; font-weight: 900; color: #0f766e;">🕒 {op_stats['weekly_meetings']}</div>
                        <div style="font-size: 10px; font-weight: bold; color: #475569; margin-top: 2px;">HAFTALIK RANDEVU</div>
                    </td>
                    <td width="25%" bgcolor="#fef2f2" align="center" style="padding: 10px; border: 1px solid #fecaca; border-radius: 8px;">
                        <div style="font-size: 16px; font-weight: 900; color: #dc2626;">⚠️ {op_stats['overdue_tasks']}</div>
                        <div style="font-size: 10px; font-weight: bold; color: #475569; margin-top: 2px;">GECİKEN ÖDEV</div>
                    </td>
                    <td width="25%" bgcolor="#f8fafc" align="center" style="padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px;">
                        <div style="font-size: 16px; font-weight: 900; color: #0f172a;">👥 {op_stats['active_students']} ({total_cards} Kart)</div>
                        <div style="font-size: 10px; font-weight: bold; color: #475569; margin-top: 2px;">AKTİF ÖĞRENCİ</div>
                    </td>
                </tr>
            </table>

            <!-- MOBİL KULLANIM KILAVUZU ŞERİDİ -->
            <table width="100%" cellspacing="0" cellpadding="0" bgcolor="#f0fdf4" style="border: 1px solid #bbf7d0; border-radius: 8px; margin-bottom: 16px;">
                <tr>
                    <td style="padding: 9px 14px; font-size: 11px; color: #166534; line-height: 1.45;">
                        <b>📲 Telefondan 6 Farklı Profesyonel WhatsApp Raporu Gönderimi:</b> Bu PDF'i WhatsApp'tan kendinize gönderin. Telefonda PDF'i açıp her öğrencinin altındaki:<br/>
                        <b>1) 💬 Ödev Programı</b> &nbsp;•&nbsp;
                        <b>2) 👪 Veli Ödev</b> &nbsp;•&nbsp;
                        <b>3) 📞 Hızlı Ara</b> &nbsp;•&nbsp;
                        <b>4) 📊 360° Akademik Analiz</b> &nbsp;•&nbsp;
                        <b>5) ⚠️ Telafi &amp; Eksik Planı</b> &nbsp;•&nbsp;
                        <b>6) 🎯 Veli Gelişim Karnesi</b> butonlarına dokunarak hazır raporları tek tıkla gönderin!
                    </td>
                </tr>
            </table>
        """

        for d_str, day_name in next_7_days:
            events = schedule.get(day_name, [])
            parts_d = d_str.split("-")
            nice_date = f"{parts_d[2]}.{parts_d[1]}.{parts_d[0]}" if len(parts_d) == 3 else d_str
            short_date = f"{parts_d[2]}.{parts_d[1]}" if len(parts_d) == 3 else d_str

            html_out += f"""
            <div class="day-header">
                <table width="100%" cellspacing="0" cellpadding="0" bgcolor="#e2e8f0" style="border-left: 6px solid #2563eb; border-radius: 6px;">
                    <tr>
                        <td align="left" style="padding: 9px 14px; font-size: 15px; font-weight: 900; color: #0f172a;">
                            📅 {html.escape(day_name)}
                        </td>
                        <td align="right" style="padding: 9px 14px; font-size: 12px; font-weight: bold; color: #475569;">
                            {nice_date} • {len(events)} Kayıt
                        </td>
                    </tr>
                </table>
            </div>
            """

            if not events:
                html_out += """
                <table width="100%" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 10px;">
                    <tr>
                        <td align="center" style="padding: 12px; color: #94a3b8; font-style: italic; font-size: 12px;">
                            Bu gün için planlanmış bir ödev teslimi veya randevu bulunmamaktadır.
                        </td>
                    </tr>
                </table>
                """
                continue

            for ev in events:
                sid = ev.get("oid")
                if sid not in analytics_cache:
                    analytics_cache[sid] = self._get_student_360_analytics(sid)
                an = analytics_cache[sid]

                ogr_clean = self._clean(ev.get("tel_ogr"))
                veli_clean = self._clean(ev.get("tel_veli"))
                ogr_disp = self._format_phone(ev.get("tel_ogr"))
                veli_disp = self._format_phone(ev.get("tel_veli"))

                targets = []
                if ogr_disp:
                    targets.append(f"📱 Öğr: <b>{html.escape(ogr_disp)}</b>")
                if veli_disp:
                    targets.append(f"👪 Veli: <b>{html.escape(veli_disp)}</b>")
                contact_str = " &nbsp;•&nbsp; ".join(targets) if targets else "<span style='color:#d97706;'>📵 Telefon numarası kayıtlı değil (WhatsApp'ta kişi seçerek gönderilir)</span>"

                # Grup etiketi
                grup_txt = ev.get("grup", "").strip()
                grup_badge = f"<span style='background-color:#f1f5f9; color:#334155; font-size:11px; font-weight:bold; padding:2px 7px; border-radius:6px;'>{html.escape(grup_txt)}</span>" if grup_txt else ""

                # Teslim / Randevu rozeti
                is_deadline = (ev["tip"] == "Teslim")
                if is_deadline:
                    t_date = ev["meta"].get("nice_date", nice_date)
                    saat_lbl = ev.get("saat", "18:00")
                    if saat_lbl == "Genel":
                        header_badge = f"<span style='background-color:#eff6ff; color:#1d4ed8; font-size:11px; font-weight:bold; padding:4px 9px; border-radius:8px;'>📊 Haftalık Karne ({t_date})</span>"
                    else:
                        header_badge = f"<span style='background-color:#fef2f2; color:#b91c1c; font-size:11px; font-weight:bold; padding:4px 9px; border-radius:8px;'>⏰ {t_date} • {saat_lbl} Teslim</span>"

                    task_rows_html = ""
                    for idx_line, line in enumerate(ev["meta"]["lines"], 1):
                        bg_row = "#f8fafc" if idx_line % 2 == 1 else "#ffffff"
                        task_rows_html += f"""
                        <tr>
                            <td bgcolor="{bg_row}" style="padding: 5px 10px; font-size: 13px; color: #1e293b; border-bottom: 1px solid #f1f5f9;">
                                <b>{idx_line}.</b> {html.escape(line)}
                            </td>
                        </tr>
                        """
                    if ev["meta"].get("notes"):
                        notes_joined = " | ".join(ev["meta"]["notes"])
                        task_rows_html += f"""
                        <tr>
                            <td bgcolor="#fffbeb" style="padding: 6px 10px; font-size: 12px; color: #92400e; border-top: 1px solid #fde68a;">
                                📌 <b>Koç Notu:</b> {html.escape(notes_joined)}
                            </td>
                        </tr>
                        """
                    body_content = f"""
                    <table width="100%" cellspacing="0" cellpadding="0" style="margin-top: 8px; border: 1px solid #e2e8f0; border-radius: 6px;">
                        {task_rows_html}
                    </table>
                    """
                else:
                    header_badge = f"<span style='background-color:#eff6ff; color:#1d4ed8; font-size:11px; font-weight:bold; padding:4px 9px; border-radius:8px;'>🕒 Saat: {html.escape(ev['saat'])} Randevu</span>"
                    body_content = f"""
                    <table width="100%" cellspacing="0" cellpadding="0" bgcolor="#eff6ff" style="margin-top: 8px; border: 1px solid #bfdbfe; border-radius: 6px;">
                        <tr>
                            <td style="padding: 8px 12px; font-size: 13px; color: #1e3a8a; font-weight: bold;">
                                🤝 {html.escape(ev.get('detay', 'Haftalık Koçluk Görüşmesi'))}
                            </td>
                        </tr>
                    </table>
                    """

                badge_html = ""
                if ev["meta"].get("badge"):
                    badge_html = f"<span style='background-color:#fef3c7; color:#92400e; font-size:11px; font-weight:bold; padding:3px 8px; border-radius:8px;'>{ev['meta']['badge']} {html.escape(ev['meta'].get('smart_note', ''))}</span>"

                stats_html = ""
                if ev["meta"].get("stats"):
                    stats_html = f"<span style='font-size:11px; color:#0f172a; font-weight:bold;'>📊 Son 14 Gün: {html.escape(ev['meta']['stats'])}</span>"

                overdue_cnt = ev["meta"].get("overdue", 0)
                overdue_html = ""
                if overdue_cnt > 0:
                    overdue_html = f"<span style='background-color:#fee2e2; color:#991b1b; font-size:11px; font-weight:bold; padding:2px 7px; border-radius:6px; margin-left:6px;'>🚨 {overdue_cnt} Geciken Ödev</span>"

                # --- 360° AKADEMİK ANALİZ & DERS DAĞILIM KUTUSU (KART İÇİNDE GÖRSEL ÖZET) ---
                analytics_box_html = ""
                if include_analytics and an.get("total_all", 0) > 0:
                    subj_pills = []
                    for s in an.get("subjects", [])[:5]:
                        s_color = "#166534" if s["pct"] >= 70 else "#991b1b" if s["late"] > 0 else "#1e3a8a"
                        subj_pills.append(
                            f"<b><font color='{s_color}'>{html.escape(s['ders'])}:</font></b> %{s['pct']} ({s['done']}/{s['total']})"
                        )
                    subj_summary_line = " &nbsp;|&nbsp; ".join(subj_pills)

                    hi_parts = [f"📈 <b>Genel Başarı:</b> %{an['pct_all']} ({an['done_all']}/{an['total_all']} Görev)"]
                    if an.get("strongest_subject"):
                        hi_parts.append(f"🌟 <b>Güçlü:</b> {html.escape(an['strongest_subject'])}")
                    if an.get("bottleneck_subject"):
                        hi_parts.append(f"⚠️ <b>Darboğaz:</b> {html.escape(an['bottleneck_subject'])}")
                    if an.get("latest_exam"):
                        hi_parts.append(f"📝 <b>Son Deneme:</b> {html.escape(an['latest_exam'])}")
                    hi_line = " &nbsp;•&nbsp; ".join(hi_parts)

                    late_topics_line = ""
                    if an.get("late_topics"):
                        lt_str = ", ".join(an["late_topics"][:3])
                        late_topics_line = f"<div style='margin-top: 4px; font-size: 11px; color: #991b1b;'>🔎 <b>Öncelikli Telafi Konuları:</b> {html.escape(lt_str)}</div>"

                    advice_line = ""
                    if an.get("coach_advice"):
                        advice_line = f"<div style='margin-top: 4px; font-size: 11px; color: #312e81;'>🧠 <b>KoçPilot 360 Önerisi:</b> {html.escape(an['coach_advice'])}</div>"

                    analytics_box_html = f"""
                    <table width="100%" cellspacing="0" cellpadding="0" bgcolor="#eef2ff" style="margin-top: 8px; border: 1px solid #c7d2fe; border-radius: 6px;">
                        <tr>
                            <td style="padding: 8px 12px;">
                                <div style="font-size: 11px; color: #1e1b4b;">{hi_line}</div>
                                <div style="margin-top: 4px; font-size: 11px; color: #334155;">📚 <b>Ders Dağılımı:</b> {subj_summary_line}</div>
                                {late_topics_line}
                                {advice_line}
                            </td>
                        </tr>
                    </table>
                    """

                # --- HER DURUMDA ÇIKMASI GARANTİ EDİLEN 6'LI MOBİL KOMUTA BUTONLARI ---
                target_ogr_num = ogr_clean or veli_clean
                target_veli_num = veli_clean or ogr_clean

                def _make_wa_url(phone_num: Optional[str], message_text: str) -> str:
                    enc = urllib.parse.quote(message_text)
                    if phone_num:
                        return f"https://wa.me/{phone_num}?text={enc}"
                    return f"https://api.whatsapp.com/send?text={enc}"

                # 1. Öğrenci Günlük/Haftalık Ödev Programı
                msg_ogr = self._build_msg_single(ev, day_name, short_date)
                wa_ogr_url = _make_wa_url(target_ogr_num, msg_ogr)
                wa_ogr_label = "💬 1. Ödev Programı (Öğr)" if target_ogr_num else "💬 1. Ödev Programı (Seç)"

                # 2. Veli Günlük/Haftalık Ödev Bilgilendirme
                msg_veli = self._build_parent_msg(ev, day_name, short_date)
                wa_veli_url = _make_wa_url(target_veli_num, msg_veli)
                wa_veli_label = "👪 2. Veli Ödev Bilgisi" if target_veli_num else "👪 2. Veli Ödev (Seç)"

                # 3. Telefonla Arama Butonu
                call_num = ogr_clean or veli_clean
                call_disp = ogr_disp or veli_disp
                if call_num:
                    call_url = f"tel:{call_num}"
                    call_cell_html = f"""
                    <td width="34%" bgcolor="#0f172a" align="center" valign="middle" style="padding: 7px 6px; border-radius: 6px;">
                        <a href="{call_url}" style="color: #ffffff; text-decoration: none; font-size: 11px; font-weight: bold; display: block;">
                            <font color="#ffffff">📞 3. Ara ({html.escape(call_disp)})</font>
                        </a>
                    </td>
                    """
                else:
                    call_cell_html = f"""
                    <td width="34%" bgcolor="#475569" align="center" valign="middle" style="padding: 7px 6px; border-radius: 6px;">
                        <span style="color: #ffffff; font-size: 10px; font-weight: bold;">
                            📵 3. Tel Kayıtsız (WP Seç)
                        </span>
                    </td>
                    """

                # 4. 360° Akademik Analiz Raporu (Öğrenci/Veli)
                msg_analysis = self._build_academic_analysis_msg(ev, an, day_name, short_date)
                wa_analysis_url = _make_wa_url(target_ogr_num, msg_analysis)

                # 5. Eksik / Telafi & Darboğaz Eylem Planı
                msg_recovery = self._build_recovery_plan_msg(ev, an, day_name, short_date)
                wa_recovery_url = _make_wa_url(target_ogr_num, msg_recovery)
                recovery_label = f"⚠️ 5. Telafi Planı ({an['late_all']} Eksik)" if an.get("late_all", 0) > 0 else "🌟 5. Başarı & Tebrik Mesajı"
                recovery_bg = "#d97706" if an.get("late_all", 0) > 0 else "#059669"

                # 6. Veliye Özel Detaylı 360° Gelişim Karnesi
                msg_parent_exec = self._build_parent_executive_report_msg(ev, an, day_name, short_date)
                wa_parent_exec_url = _make_wa_url(target_veli_num, msg_parent_exec)

                border_color = ev.get("renk", "#3b82f6")

                html_out += f"""
                <div class="student-card">
                <table width="100%" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="border: 1px solid #cbd5e1; border-left: 6px solid {border_color}; border-radius: 8px;">
                    <tr>
                        <td style="padding: 12px 16px;">
                            <!-- ÜST SATIR: ÖĞRENCİ ADI VE TESLİM SAATİ -->
                            <table width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="left" valign="middle">
                                        <span style="font-size: 16px; font-weight: 900; color: #0f172a;">{html.escape(ev['ad'])}</span>
                                        &nbsp;{grup_badge}
                                    </td>
                                    <td align="right" valign="middle">
                                        {header_badge}
                                    </td>
                                </tr>
                            </table>

                            <!-- İKİNCİ SATIR: TELEFON VE PERFORMANS ÖZETİ -->
                            <table width="100%" cellspacing="0" cellpadding="0" style="margin-top: 6px;">
                                <tr>
                                    <td align="left" valign="middle" style="font-size: 11px; color: #475569;">
                                        {contact_str}
                                    </td>
                                    <td align="right" valign="middle">
                                        {stats_html} {overdue_html}
                                    </td>
                                </tr>
                            </table>

                            <!-- ÜÇÜNCÜ SATIR: DURUM ROZETİ -->
                            {f'<div style="margin-top: 6px;">{badge_html}</div>' if badge_html else ''}

                            <!-- DÖRDÜNCÜ SATIR: ÖDEV LİSTESİ / GÖRÜŞME DETAYI -->
                            {body_content}

                            <!-- BEŞİNCİ SATIR: 360° AKADEMİK ANALİZ ÖZET KUTUSU -->
                            {analytics_box_html}

                            <!-- ALTINCI SATIR: 6'LI MOBİL KOMUTA MERKEZİ BUTONLARI (2 SATIR x 3 BUTON) -->
                            <div class="btn-bar">
                            <table width="100%" cellspacing="4" cellpadding="0" style="margin-top: 8px;">
                                <tr>
                                    <td width="33%" bgcolor="#16a34a" align="center" valign="middle" style="padding: 7px 6px; border-radius: 6px;">
                                        <a href="{wa_ogr_url}" style="color: #ffffff; text-decoration: none; font-size: 11px; font-weight: bold; display: block;">
                                            <font color="#ffffff">{wa_ogr_label}</font>
                                        </a>
                                    </td>
                                    <td width="33%" bgcolor="#2563eb" align="center" valign="middle" style="padding: 7px 6px; border-radius: 6px;">
                                        <a href="{wa_veli_url}" style="color: #ffffff; text-decoration: none; font-size: 11px; font-weight: bold; display: block;">
                                            <font color="#ffffff">{wa_veli_label}</font>
                                        </a>
                                    </td>
                                    {call_cell_html}
                                </tr>
                                <tr>
                                    <td width="33%" bgcolor="#7c3aed" align="center" valign="middle" style="padding: 7px 6px; border-radius: 6px;">
                                        <a href="{wa_analysis_url}" style="color: #ffffff; text-decoration: none; font-size: 11px; font-weight: bold; display: block;">
                                            <font color="#ffffff">📊 4. 360° Akademik Analiz</font>
                                        </a>
                                    </td>
                                    <td width="33%" bgcolor="{recovery_bg}" align="center" valign="middle" style="padding: 7px 6px; border-radius: 6px;">
                                        <a href="{wa_recovery_url}" style="color: #ffffff; text-decoration: none; font-size: 11px; font-weight: bold; display: block;">
                                            <font color="#ffffff">{recovery_label}</font>
                                        </a>
                                    </td>
                                    <td width="34%" bgcolor="#0891b2" align="center" valign="middle" style="padding: 7px 6px; border-radius: 6px;">
                                        <a href="{wa_parent_exec_url}" style="color: #ffffff; text-decoration: none; font-size: 11px; font-weight: bold; display: block;">
                                            <font color="#ffffff">🎯 6. Veli Gelişim Karnesi</font>
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            </div>
                        </td>
                    </tr>
                </table>
                </div>
                """

        html_out += "</body></html>"
        return html_out

    def _clean(self, t) -> Optional[str]:
        """Telefon numarasını uluslararası WhatsApp formatına (905xxxxxxxxx) temizler.
        Boş maskeleri ('(5)' vb.) ve 10 haneden kısa geçersiz girdileri eler."""
        if not t:
            return None
        c = "".join(filter(str.isdigit, str(t)))
        if len(c) < 10:
            return None
        if len(c) == 10 and c.startswith("5"):
            return "90" + c
        if len(c) == 11 and c.startswith("05"):
            return "9" + c
        if len(c) == 12 and c.startswith("905"):
            return c
        if c.startswith("0"):
            return "9" + c
        return c

    def _format_phone(self, t) -> str:
        """Geçerli telefon numarasını okunaklı '05xx xxx xx xx' biçiminde döndürür."""
        clean = self._clean(t)
        if not clean:
            return ""
        local = clean[2:] if clean.startswith("90") and len(clean) == 12 else clean
        if len(local) == 10:
            return f"0{local[0:3]} {local[3:6]} {local[6:8]} {local[8:10]}"
        return str(t).strip()

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
