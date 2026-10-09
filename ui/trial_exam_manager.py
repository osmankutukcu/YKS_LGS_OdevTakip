# -*- coding: utf-8 -*-
"""
Profesyonel Deneme Sınavları & Başarı Analiz Merkezi (TrialExamManager)
- ÖSYM ve MEB resmi katsayıları ile gerçekçi puan ve başarı sırası hesaplama
- Online Türkiye geneli net ortalamaları ve benchmark kıyaslama
- A4 Bireysel Öğrenci Deneme Karnesi (PDF Sonuç Belgesi)
- Canlı net hesaplama, Excel desteği ve derin teşhis analizleri
"""

import sys
import os
import sqlite3
import json
import numpy as np
from typing import List, Optional, Dict, Any

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QFrame,
    QMessageBox, QDialog, QFormLayout, QDateEdit, QLineEdit, QTabWidget,
    QAbstractItemView, QMenu, QSpinBox, QDoubleSpinBox, QFileDialog, QApplication,
    QProgressBar, QScrollArea, QGroupBox
)
from PyQt6.QtCore import Qt, QDate, QSize, QEvent
from PyQt6.QtGui import QColor, QIcon, QFont, QAction, QKeySequence, QTextDocument, QPageLayout

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

import db
from utils import settings as appset
from ui.trial_exam_settings import TrialExamSettingsDialog, DEFAULT_CONFIG
from services.exam_score_calculator import (
    TURKEY_BENCHMARKS, calculate_exam_score, calculate_tyt_score, 
    calculate_ayt_score, calculate_lgs_score
)

# ----------------------------------------------------------------------
# Matplotlib Tuvali
# ----------------------------------------------------------------------
class _MatCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        fig = Figure(figsize=(5, 3.5), dpi=100)
        self.ax = fig.add_subplot(111)
        fig.tight_layout()
        super().__init__(fig)
        self.setParent(parent)

# ----------------------------------------------------------------------
# Online Türkiye Geneli Karşılaştırma Modalı
# ----------------------------------------------------------------------
class TurkeyBenchmarkDialog(QDialog):
    """
    Sınıf net ortalamalarını Türkiye geneli ÖSYM / MEB resmi verileriyle 
    yan yana kıyaslayan profesyonel benchmark penceresi.
    """
    def __init__(self, exam_type: str, class_averages: Dict[str, float], parent=None):
        super().__init__(parent)
        self.exam_type = exam_type.upper()
        self.class_averages = class_averages
        
        self.setWindowTitle("🌐 Online Türkiye Geneli Sınav Karşılaştırması")
        self.resize(750, 520)
        self.setStyleSheet("background-color: #f8fafc;")
        
        self.init_ui()

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(14)
        
        # Header
        h_card = QFrame()
        h_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #2563eb);
                border-radius: 10px;
                padding: 12px;
            }
        """)
        hl = QVBoxLayout(h_card)
        lbl_t = QLabel(f"🌐 {self.exam_type} Türkiye Geneli Başarı Kıyaslaması")
        lbl_t.setStyleSheet("color: white; font-size: 16px; font-weight: 900;")
        lbl_sub = QLabel("Kurum / Sınıf netlerinizin ÖSYM ve MEB resmi Türkiye ortalamalarına göre performansı")
        lbl_sub.setStyleSheet("color: #bfdbfe; font-size: 11px;")
        hl.addWidget(lbl_t)
        hl.addWidget(lbl_sub)
        lay.addWidget(h_card)
        
        # Karşılaştırma Tablosu
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Ders", "Bizim Sınıf Neti", "Türkiye Ortalaması", "Fark", "Başarı Durumu"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(1, 120)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(2, 130)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 90)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(4, 130)
        
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QHeaderView::section {
                background: #f1f5f9;
                color: #475569;
                font-weight: bold;
                padding: 6px;
            }
        """)
        
        # Benchmark Data
        benchmark_key = "TYT" if "TYT" in self.exam_type else ("LGS" if "LGS" in self.exam_type else "AYT")
        b_data = TURKEY_BENCHMARKS.get(benchmark_key, TURKEY_BENCHMARKS["TYT"])["subjects"]
        
        row_idx = 0
        table.setRowCount(len(self.class_averages))
        
        for subj, my_net in self.class_averages.items():
            tr_info = b_data.get(subj, {})
            tr_avg = tr_info.get("average_net", 0.0)
            diff = my_net - tr_avg
            
            # 1. Ders
            table.setItem(row_idx, 0, QTableWidgetItem(subj))
            
            # 2. Bizim Sınıf Neti
            it_my = QTableWidgetItem(f"{my_net:.2f} Net")
            it_my.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_my.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            table.setItem(row_idx, 1, it_my)
            
            # 3. Türkiye
            it_tr = QTableWidgetItem(f"{tr_avg:.2f} Net" if tr_avg > 0 else "—")
            it_tr.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_idx, 2, it_tr)
            
            # 4. Fark
            diff_sign = "+" if diff > 0 else ""
            it_diff = QTableWidgetItem(f"{diff_sign}{diff:.2f}" if tr_avg > 0 else "—")
            it_diff.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if diff > 0:
                it_diff.setForeground(QColor("#15803d"))
                it_diff.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            elif diff < 0:
                it_diff.setForeground(QColor("#dc2626"))
            table.setItem(row_idx, 3, it_diff)
            
            # 5. Başarı Durumu
            if tr_avg > 0:
                pct = int((my_net / tr_avg) * 100)
                if diff >= 5:
                    st_txt = f"🌟 Çok İleri (%{pct})"
                    st_col = "#15803d"
                elif diff >= 0:
                    st_txt = f"✅ Türkiye Üstü (%{pct})"
                    st_col = "#2563eb"
                else:
                    st_txt = f"⚠️ Geliştirilmeli (%{pct})"
                    st_col = "#d97706"
            else:
                st_txt = "Standard"
                st_col = "#64748b"
                
            it_st = QTableWidgetItem(st_txt)
            it_st.setForeground(QColor(st_col))
            it_st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_idx, 4, it_st)
            
            row_idx += 1
            
        lay.addWidget(table, stretch=1)
        
        # Kapat Butonu
        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet("background: #2563eb; color: white; padding: 8px 20px; font-weight: bold; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)


# ----------------------------------------------------------------------
# Bireysel Öğrenci Deneme Karnesi (A4 PDF Sonuç Belgesi)
# ----------------------------------------------------------------------
class StudentReportCardDialog(QDialog):
    """
    Öğrenciye özel, veliye ve koça sunulabilecek A4 Deneme Sonuç Karnesi basar.
    """
    def __init__(self, student_name: str, exam_name: str, exam_type: str, 
                 exam_date: str, rank: int, total_students: int, 
                 subject_results: List[Dict[str, Any]], score_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.student_name = student_name
        self.exam_name = exam_name
        self.exam_type = exam_type
        self.exam_date = exam_date
        self.rank = rank
        self.total_students = total_students
        self.subject_results = subject_results
        self.score_data = score_data
        
        self.setWindowTitle(f"📄 Deneme Sınavı Sonuç Karnesi: {student_name}")
        self.resize(560, 480)
        self.setStyleSheet("background-color: #f8fafc;")
        
        self.init_ui()

    def init_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 20)
        
        lbl_h = QLabel("📄 Öğrenci Deneme Karnesi (A4 Sonuç Belgesi)")
        lbl_h.setStyleSheet("font-size: 16px; font-weight: 900; color: #1e3a8a;")
        lay.addWidget(lbl_h)
        
        lbl_sub = QLabel(f"Öğrenci: <b>{self.student_name}</b> | Sınav: <b>{self.exam_name}</b> ({self.exam_type})")
        lbl_sub.setStyleSheet("font-size: 12px; color: #334155;")
        lay.addWidget(lbl_sub)
        
        # Özet Kart
        frm_score = QFrame()
        frm_score.setStyleSheet("background: white; border: 1.5px solid #2563eb; border-radius: 8px; padding: 12px;")
        f_lay = QHBoxLayout(frm_score)
        
        def score_col(title, val, color="#1e3a8a"):
            v = QVBoxLayout()
            l1 = QLabel(title); l1.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b;")
            l2 = QLabel(val); l2.setStyleSheet(f"font-size: 16px; font-weight: 900; color: {color};")
            v.addWidget(l1); v.addWidget(l2)
            return v
            
        f_lay.addLayout(score_col("TOPLAM NET", f"{self.score_data.get('toplam_net', 0):.2f}", "#2563eb"))
        f_lay.addLayout(score_col("ÖSYM/MEB PUANI", f"{self.score_data.get('ham_puan', 0):.2f}", "#059669"))
        f_lay.addLayout(score_col("SINIF DERECESİ", f"{self.rank} / {self.total_students}", "#d97706"))
        f_lay.addLayout(score_col("TAHMİNİ TÜRKİYE DİLİMİ", f"%{self.score_data.get('yuzdelik_dilim', 0)}", "#7c3aed"))
        lay.addWidget(frm_score)
        
        lay.addStretch()
        
        # Butonlar
        h_btn = QHBoxLayout()
        btn_cancel = QPushButton("Kapat")
        btn_cancel.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 16px; font-weight: bold;")
        btn_cancel.clicked.connect(self.reject)
        h_btn.addWidget(btn_cancel)
        
        h_btn.addStretch()
        
        btn_pdf = QPushButton("📄 PDF Olarak Kaydet")
        btn_pdf.setStyleSheet("background: #0284c7; color: white; font-weight: bold; border-radius: 6px; padding: 8px 18px;")
        btn_pdf.clicked.connect(self.export_pdf)
        h_btn.addWidget(btn_pdf)
        
        btn_print = QPushButton("🖨️ Yazıcıya Gönder")
        btn_print.setStyleSheet("background: #16a34a; color: white; font-weight: bold; border-radius: 6px; padding: 8px 18px;")
        btn_print.clicked.connect(self.print_card)
        h_btn.addWidget(btn_print)
        
        lay.addLayout(h_btn)

    def generate_html(self):
        rows_tr = []
        for r in self.subject_results:
            d = r.get("d", 0)
            y = r.get("y", 0)
            net = r.get("net", 0.0)
            subj = r.get("ders", "")
            q_cnt = d + y + r.get("bos", 0)
            if q_cnt == 0: q_cnt = 40 if "Mat" in subj or "Türk" in subj else 20
            
            pct = int((net / q_cnt) * 100) if q_cnt > 0 else 0
            if pct < 0: pct = 0
            
            tr = f"""
            <tr>
                <td style="padding: 6px 8px; font-weight: bold; border: 1px solid #cbd5e1;">{subj}</td>
                <td style="text-align: center; border: 1px solid #cbd5e1;">{d}</td>
                <td style="text-align: center; border: 1px solid #cbd5e1; color: #dc2626;">{y}</td>
                <td style="text-align: center; border: 1px solid #cbd5e1; color: #64748b;">{max(0, q_cnt - d - y)}</td>
                <td style="text-align: center; font-weight: bold; color: #2563eb; border: 1px solid #cbd5e1;">{net:.2f}</td>
                <td style="text-align: center; font-weight: bold; border: 1px solid #cbd5e1;">%{pct}</td>
            </tr>
            """
            rows_tr.append(tr)
            
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4 portrait; margin: 12mm 15mm; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; color: #1e293b; font-size: 11px; }}
            .header-card {{ border: 2px solid #2563eb; border-radius: 8px; padding: 12px; background: #f8fafc; margin-bottom: 12px; }}
            .title {{ font-size: 18px; font-weight: 900; color: #1e3a8a; text-transform: uppercase; }}
            .sub {{ font-size: 11px; color: #475569; margin-top: 2px; }}
            .score-grid {{ display: table; width: 100%; border: 1.5px solid #2563eb; border-radius: 6px; margin-bottom: 14px; }}
            .score-col {{ display: table-cell; width: 25%; text-align: center; padding: 10px 4px; border-right: 1px dashed #cbd5e1; }}
            .score-col:last-child {{ border-right: none; }}
            .score-val {{ font-size: 18px; font-weight: 900; color: #2563eb; }}
            .score-lbl {{ font-size: 10px; color: #64748b; font-weight: bold; text-transform: uppercase; }}
            table.results {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; }}
            table.results th {{ background: #1e293b; color: white; padding: 6px 8px; font-size: 10px; border: 1px solid #334155; }}
            .advice-box {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; background: #ffffff; margin-bottom: 15px; font-size: 10.5px; }}
            .sign-grid {{ display: table; width: 100%; margin-top: 30px; }}
            .sign-col {{ display: table-cell; width: 50%; text-align: center; color: #64748b; font-size: 10px; }}
        </style>
        </head>
        <body>
            <div class="header-card">
                <div style="display: table; width: 100%;">
                    <div style="display: table-cell;">
                        <div class="title">🎓 DENEME SINAVI SONUÇ BELGESİ</div>
                        <div class="sub">Kurumsal Değerlendirme ve Performans Takip Raporu</div>
                    </div>
                    <div style="display: table-cell; text-align: right; vertical-align: middle;">
                        <span style="background: #2563eb; color: white; font-weight: bold; padding: 4px 10px; border-radius: 6px; font-size: 12px;">{self.exam_type}</span>
                    </div>
                </div>
                <div style="margin-top: 8px; border-top: 1px dashed #cbd5e1; padding-top: 6px; display: table; width: 100%;">
                    <div style="display: table-cell; width: 33%;"><b>Öğrenci:</b> {self.student_name}</div>
                    <div style="display: table-cell; width: 33%;"><b>Sınav Adı:</b> {self.exam_name}</div>
                    <div style="display: table-cell; width: 33%; text-align: right;"><b>Tarih:</b> {self.exam_date}</div>
                </div>
            </div>

            <div class="score-grid">
                <div class="score-col">
                    <div class="score-val">{self.score_data.get('toplam_net', 0):.2f}</div>
                    <div class="score-lbl">Toplam Net</div>
                </div>
                <div class="score-col">
                    <div class="score-val" style="color: #059669;">{self.score_data.get('ham_puan', 0):.2f}</div>
                    <div class="score-lbl">ÖSYM/MEB Puanı</div>
                </div>
                <div class="score-col">
                    <div class="score-val" style="color: #d97706;">{self.rank} / {self.total_students}</div>
                    <div class="score-lbl">Kurum Sıralaması</div>
                </div>
                <div class="score-col">
                    <div class="score-val" style="color: #7c3aed;">%{self.score_data.get('yuzdelik_dilim', 0)}</div>
                    <div class="score-lbl">Tahmini Türkiye Dilimi</div>
                </div>
            </div>

            <table class="results">
                <thead>
                    <tr>
                        <th>DERS ADI</th>
                        <th>DOĞRU</th>
                        <th>YANLIŞ</th>
                        <th>BOŞ</th>
                        <th>NET</th>
                        <th>BAŞARI %</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_tr)}
                </tbody>
            </table>

            <div class="advice-box">
                <b style="color: #1e3a8a;">🎯 Koçun Stratejik Değerlendirmesi:</b><br>
                Öğrencimiz bu sınavda <b>{self.score_data.get('ham_puan', 0):.2f}</b> puan alarak kurum genelinde <b>{self.rank}.</b> sırada yer almıştır. 
                Sınavda en çok net kazandıran dersler pekiştirilmeli, hata yapılan sorular haftalık koçluk görüşmesinde soru otopsisi yapılarak analiz edilmelidir.
            </div>

            <div class="sign-grid">
                <div class="sign-col">
                    <div>Öğrenci / Veli İmzası</div>
                    <div style="margin-top: 35px; border-top: 1px solid #94a3b8; width: 140px; margin-left: auto; margin-right: auto;"></div>
                </div>
                <div class="sign-col">
                    <div>Eğitim Koçu / Kurum Onayı</div>
                    <div style="margin-top: 35px; border-top: 1px solid #94a3b8; width: 140px; margin-left: auto; margin-right: auto;"></div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def export_pdf(self):
        stu_slug = self.student_name.replace(" ", "_")
        filename = f"Deneme_Karnesi_{stu_slug}_{self.exam_type}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Deneme Karnesini PDF Kaydet", os.path.expanduser(f"~/Desktop/{filename}"), "PDF Files (*.pdf)")
        if not path: return
        
        try:
            from PyQt6.QtPrintSupport import QPrinter
            doc = QTextDocument()
            doc.setHtml(self.generate_html())
            prn = QPrinter(QPrinter.PrinterMode.HighResolution)
            prn.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            prn.setOutputFileName(path)
            prn.setPageOrientation(QPageLayout.Orientation.Portrait)
            doc.print(prn)
            QMessageBox.information(self, "Başarılı", f"Karne başarıyla kaydedildi:\n\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def print_card(self):
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            prn = QPrinter(QPrinter.PrinterMode.HighResolution)
            prn.setPageOrientation(QPageLayout.Orientation.Portrait)
            dlg = QPrintDialog(prn, self)
            if dlg.exec() == QPrintDialog.DialogCode.Accepted:
                doc = QTextDocument()
                doc.setHtml(self.generate_html())
                doc.print(prn)
                QMessageBox.information(self, "Yazdırıldı", "Karne yazıcıya iletildi.")
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


# ----------------------------------------------------------------------
# Ana Sınıf: TrialExamManager
# ----------------------------------------------------------------------
class TrialExamManager(QWidget):
    """
    Profesyonel Deneme Sınavı Takip ve Analiz Modülü.
    ÖSYM/MEB puanlama, tahmini sıralama motoru, online benchmark ve PDF karneleme.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_exam_id: Optional[int] = None
        self.current_exam_type: str = "TYT"
        self._updating_score = False
        
        self._load_config()
        self._ensure_schema()
        
        self._setup_ui()
        self._load_exam_list()

    def _ensure_schema(self):
        try:
            con = db.get_conn()
            cur = con.cursor()
            if hasattr(db, '_init_deneme_tables'):
                db._init_deneme_tables(cur)
            con.commit()
            con.close()
        except Exception as e:
            print(f"Trial exam schema check error: {e}")

    def _load_config(self):
        saved = appset.ayar_get("trial_exam_config")
        if saved:
            try:
                self.config = json.loads(saved)
            except:
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
        self.exam_types = list(self.config.keys())

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # ==========================================================
        # 1. ÜST YÖNETİCİ BAŞLIK VE AKSİYON ÇUBUĞU
        # ==========================================================
        top_frame = QFrame()
        top_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        top_bar = QHBoxLayout(top_frame)
        top_bar.setContentsMargins(16, 12, 16, 12)
        top_bar.setSpacing(14)
        
        # Başlık
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        self.lbl_title = QLabel("📊 Profesyonel Deneme Sınavları & Başarı Analiz Merkezi")
        self.lbl_title.setStyleSheet("font-size: 17px; font-weight: 900; color: #1e3a8a;")
        lbl_sub = QLabel("ÖSYM ve MEB resmi katsayıları, tahmini Türkiye sıralaması, online karşılaştırma ve A4 deneme karnesi")
        lbl_sub.setStyleSheet("font-size: 11px; color: #64748b;")
        v_title.addWidget(self.lbl_title)
        v_title.addWidget(lbl_sub)
        top_bar.addLayout(v_title, stretch=1)
        
        # Filtre Türü
        v_f = QVBoxLayout()
        v_f.setSpacing(2)
        lbl_ft = QLabel("SINAV TÜRÜ:")
        lbl_ft.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b;")
        self.cmb_filter_type = QComboBox()
        self.cmb_filter_type.setFixedWidth(130)
        self.cmb_filter_type.addItem("Tümü")
        self.cmb_filter_type.addItems(self.exam_types)
        self.cmb_filter_type.setStyleSheet("""
            QComboBox {
                background-color: #ffffff; border: 1.5px solid #cbd5e1; border-radius: 6px; padding: 5px 8px; font-weight: bold; color: #1e293b;
            }
        """)
        self.cmb_filter_type.currentTextChanged.connect(self._load_exam_list)
        v_f.addWidget(lbl_ft)
        v_f.addWidget(self.cmb_filter_type)
        top_bar.addLayout(v_f)
        
        # Online Benchmark Butonu
        self.btn_online_bench = QPushButton("🌐 Türkiye Geneli Kıyasla")
        self.btn_online_bench.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_online_bench.setStyleSheet("""
            QPushButton {
                background: #0284c7; color: white; font-weight: bold; border-radius: 8px; padding: 9px 14px; font-size: 12px;
            }
            QPushButton:hover { background: #0369a1; }
        """)
        self.btn_online_bench.clicked.connect(self._open_turkey_benchmark)
        top_bar.addWidget(self.btn_online_bench)

        # Ayarlar Butonu
        self.btn_settings = QPushButton("⚙️ Ayarlar")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("background-color: #4b5563; color: white; padding: 9px 14px; border-radius: 8px; font-weight: bold;")
        self.btn_settings.clicked.connect(self._open_settings)
        top_bar.addWidget(self.btn_settings)

        # Yeni Deneme Butonu
        self.btn_new = QPushButton("➕ Yeni Deneme Tanımla")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; 
                padding: 9px 16px; border-radius: 8px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_new.clicked.connect(self._open_new_exam_dialog)
        top_bar.addWidget(self.btn_new)
        
        main_layout.addWidget(top_frame)

        # ==========================================================
        # 2. ÜST KPI ÖZET ŞERİDİ
        # ==========================================================
        kpi_frame = QFrame()
        kpi_frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
        """)
        h_kpi = QHBoxLayout(kpi_frame)
        h_kpi.setContentsMargins(14, 8, 14, 8)
        h_kpi.setSpacing(12)
        
        self.kpi_total_exams = self._create_kpi_card("📋 Toplam Deneme", "0", "#334155", "#f1f5f9")
        self.kpi_part = self._create_kpi_card("👥 Sınava Katılım", "0 Öğrenci", "#1e40af", "#eff6ff")
        self.kpi_class_net = self._create_kpi_card("📊 Sınıf Net Ort.", "0.00 Net", "#059669", "#dcfce7")
        self.kpi_top_score = self._create_kpi_card("🏆 Zirve Puan & Net", "0.00", "#d97706", "#fef3c7")
        self.kpi_turkey_diff = self._create_kpi_card("🌐 Türkiye Karşılaştırması", "İnceleniyor", "#7c3aed", "#f3e8ff")
        
        h_kpi.addWidget(self.kpi_total_exams)
        h_kpi.addWidget(self.kpi_part)
        h_kpi.addWidget(self.kpi_class_net)
        h_kpi.addWidget(self.kpi_top_score)
        h_kpi.addWidget(self.kpi_turkey_diff)
        main_layout.addWidget(kpi_frame)

        # ==========================================================
        # 3. ORTA SPLITTER (Sol Liste, Sağ Detay & Tablar)
        # ==========================================================
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(8)
        self.splitter.setStyleSheet("QSplitter::handle { background: #e2e8f0; margin: 4px; border-radius: 4px; }")

        # 1) SOL: Deneme Listesi
        self.left_panel = QFrame()
        self.left_panel.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px;")
        lay_left = QVBoxLayout(self.left_panel)
        lay_left.setContentsMargins(8, 10, 8, 10)
        lay_left.setSpacing(6)
        
        lbl_list_h = QLabel("📑 Uygulanan Denemeler")
        lbl_list_h.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 12px; padding-left: 4px;")
        lay_left.addWidget(lbl_list_h)
        
        self.table_exams = QTableWidget()
        self.table_exams.setColumnCount(4)
        self.table_exams.setHorizontalHeaderLabels(["ID", "Tarih", "Deneme Adı", "Tür"])
        self.table_exams.verticalHeader().setVisible(False)
        self.table_exams.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_exams.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_exams.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_exams.setAlternatingRowColors(True)
        self.table_exams.setColumnWidth(0, 36)
        self.table_exams.setColumnWidth(1, 85)
        self.table_exams.setColumnWidth(3, 60)
        
        header = self.table_exams.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        
        self.table_exams.itemSelectionChanged.connect(self._on_exam_selected)
        self.table_exams.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_exams.customContextMenuRequested.connect(self._show_context_menu)
        
        lay_left.addWidget(self.table_exams)
        self.splitter.addWidget(self.left_panel)

        # 2) SAĞ: Detaylar (Tablar)
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 10px;")
        lay_right = QVBoxLayout(self.right_panel)
        lay_right.setContentsMargins(10, 10, 10, 10)
        
        self.tabs = QTabWidget()
        
        # Tab 1: Sonuç Girişi & Puanlama
        self.tab_entry = QWidget()
        self._setup_entry_tab()
        self.tabs.addTab(self.tab_entry, "📝 Sonuç Girişi & ÖSYM/MEB Puanlama")
        
        # Tab 2: Sıralama & Derece Listesi
        self.tab_ranking = QWidget()
        self._setup_ranking_tab()
        self.tabs.addTab(self.tab_ranking, "🏆 Sıralama & Karne Listesi")
        
        # Tab 3: Detaylı Analiz & Teşhis
        self.tab_analysis = QWidget()
        self._setup_analysis_tab()
        self.tabs.addTab(self.tab_analysis, "📊 Detaylı Teşhis Analizi")
        
        # Tab 4: Online Benchmark & Şablonlar
        self.tab_online = QWidget()
        self._setup_online_tab()
        self.tabs.addTab(self.tab_online, "🌐 Online Türkiye Benchmark & Şablonlar")
        
        self.tabs.currentChanged.connect(self._on_tab_changed)
        lay_right.addWidget(self.tabs)
        self.splitter.addWidget(self.right_panel)
        
        self.splitter.setSizes([320, 880])
        main_layout.addWidget(self.splitter, stretch=1)
        
        self.right_panel.setEnabled(False)

    def _create_kpi_card(self, title, val, txt_color, bg_color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {bg_color};
                border-radius: 8px;
                padding: 4px 10px;
            }}
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b;")
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"font-size: 14px; font-weight: 900; color: {txt_color};")
        v.addWidget(lbl_t)
        v.addWidget(lbl_v)
        card.lbl_val = lbl_v
        return card

    def _setup_entry_tab(self):
        lay = QVBoxLayout(self.tab_entry)
        lay.setSpacing(10)
        lay.setContentsMargins(6, 6, 6, 6)
        
        # Dashboard Şeridi
        self.dash_exam = QFrame()
        self.dash_exam.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px;")
        dl = QHBoxLayout(self.dash_exam)
        dl.setContentsMargins(6, 4, 6, 4)
        
        self.lbl_d_info = QLabel("Seçili Deneme: -")
        self.lbl_d_info.setStyleSheet("font-weight: 800; font-size: 13px; color: #1e3a8a;")
        dl.addWidget(self.lbl_d_info)
        dl.addStretch()
        
        self.btn_recalc = QPushButton("⚡ Otomatik Hesapla")
        self.btn_recalc.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        self.btn_recalc.clicked.connect(self._recalc_all)
        dl.addWidget(self.btn_recalc)
        
        self.btn_export = QPushButton("📤 Excel'e Aktar")
        self.btn_export.setStyleSheet("background-color: #0284c7; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.btn_export.clicked.connect(self._export_excel)
        dl.addWidget(self.btn_export)
        
        self.btn_card_selected = QPushButton("📄 Karne Çıkar (PDF)")
        self.btn_card_selected.setStyleSheet("background-color: #7c3aed; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.btn_card_selected.clicked.connect(self._open_selected_student_report_card)
        dl.addWidget(self.btn_card_selected)

        self.btn_save_scores = QPushButton("💾 Sonuçları Kaydet")
        self.btn_save_scores.setStyleSheet("background-color: #059669; color: white; padding: 6px 14px; border-radius: 6px; font-weight: bold;")
        self.btn_save_scores.clicked.connect(self._save_scores)
        dl.addWidget(self.btn_save_scores)
        
        lay.addWidget(self.dash_exam)
        
        # Sonuç Matris Tablosu
        self.table_scores = QTableWidget()
        self.table_scores.installEventFilter(self)
        self.table_scores.itemChanged.connect(self._on_score_changed)
        self.table_scores.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_scores.customContextMenuRequested.connect(self._show_table_context_menu)
        lay.addWidget(self.table_scores, stretch=1)
        
        lbl_hint = QLabel("💡 İpucu: Doğru/Yanlış girdiğinizde Net, ÖSYM/MEB Puanı ve Türkiye Dilimi anında canlı hesaplanır. Excel'den kopyalayıp CTRL+V ile yapıştırabilirsiniz.")
        lbl_hint.setStyleSheet("font-style: italic; color: #475569; font-size: 11px;")
        lay.addWidget(lbl_hint)

    def _setup_ranking_tab(self):
        lay = QVBoxLayout(self.tab_ranking)
        lay.setSpacing(8)
        lay.setContentsMargins(6, 6, 6, 6)
        
        top_h = QHBoxLayout()
        lbl_r = QLabel("🏆 Sınav Başarı ve Derece Sıralaması")
        lbl_r.setStyleSheet("font-weight: 800; font-size: 13px; color: #1e3a8a;")
        top_h.addWidget(lbl_r)
        top_h.addStretch()
        
        btn_print_ranking = QPushButton("🖨️ Sıralama Listesini Yazdır (PDF)")
        btn_print_ranking.setStyleSheet("background: #0284c7; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        btn_print_ranking.clicked.connect(self._export_ranking_pdf)
        top_h.addWidget(btn_print_ranking)
        
        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        btn_refresh.clicked.connect(self._load_ranking)
        top_h.addWidget(btn_refresh)
        lay.addLayout(top_h)
        
        self.table_ranking = QTableWidget()
        self.table_ranking.setColumnCount(6)
        self.table_ranking.setHorizontalHeaderLabels(["Sıra", "Öğrenci Adı Soyadı", "Toplam Net", "ÖSYM/MEB Puanı", "Tahmini Türkiye Dilimi", "İşlem"])
        self.table_ranking.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_ranking.setColumnWidth(0, 50)
        self.table_ranking.setColumnWidth(2, 90)
        self.table_ranking.setColumnWidth(3, 110)
        self.table_ranking.setColumnWidth(4, 140)
        self.table_ranking.setColumnWidth(5, 110)
        self.table_ranking.verticalHeader().setDefaultSectionSize(40)
        
        lay.addWidget(self.table_ranking, stretch=1)

    def _setup_analysis_tab(self):
        lay = QVBoxLayout(self.tab_analysis)
        lay.setSpacing(10)
        lay.setContentsMargins(6, 6, 6, 6)
        
        # Üst Özet
        self.lbl_class_avg = QLabel("Sınıf Ortalaması: -")
        self.lbl_class_avg.setStyleSheet("font-size: 13px; font-weight: bold; color: #2563eb; background: #eff6ff; padding: 8px 12px; border-radius: 6px;")
        lay.addWidget(self.lbl_class_avg)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Grafik 1: Ders Ortalamaları
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.setContentsMargins(0,0,0,0)
        l1.addWidget(QLabel("<b>📊 Ders Bazlı Sınıf Net Ortalamaları:</b>"))
        self.canvas_subjects = _MatCanvas(w1)
        l1.addWidget(self.canvas_subjects)
        splitter.addWidget(w1)
        
        # Grafik 2: Net Dağılımı ve Normal Dağılım
        w2 = QWidget(); l2 = QVBoxLayout(w2); l2.setContentsMargins(0,0,0,0)
        l2.addWidget(QLabel("<b>📈 Net Dağılım Histogramı ve Başarı Çan Eğrisi:</b>"))
        self.canvas_dist = _MatCanvas(w2)
        l2.addWidget(self.canvas_dist)
        splitter.addWidget(w2)
        
        lay.addWidget(splitter, stretch=1)

    def _setup_online_tab(self):
        lay = QVBoxLayout(self.tab_online)
        lay.setSpacing(12)
        lay.setContentsMargins(12, 12, 12, 12)
        
        lbl_ot = QLabel("🌐 Resmi ÖSYM ve MEB Türkiye Net Ortalamaları")
        lbl_ot.setStyleSheet("font-weight: 800; font-size: 14px; color: #1e3a8a;")
        lay.addWidget(lbl_ot)
        
        desc = QLabel("Aşağıdaki veriler ÖSYM ve MEB resmi sınav raporlarından derlenmiştir. Öğrencilerinizin netlerini bu standartlarla kıyaslayabilirsiniz.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 11.5px;")
        lay.addWidget(desc)
        
        self.table_benchmarks = QTableWidget()
        self.table_benchmarks.setColumnCount(4)
        self.table_benchmarks.setHorizontalHeaderLabels(["Sınav & Ders", "Soru Sayısı", "Türkiye Net Ortalaması", "Standart Sapma"])
        self.table_benchmarks.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_benchmarks.setColumnWidth(1, 100)
        self.table_benchmarks.setColumnWidth(2, 150)
        self.table_benchmarks.setColumnWidth(3, 120)
        
        # Fill Table
        row_i = 0
        for e_key, b_info in TURKEY_BENCHMARKS.items():
            for s_name, s_vals in b_info["subjects"].items():
                self.table_benchmarks.insertRow(row_i)
                self.table_benchmarks.setItem(row_i, 0, QTableWidgetItem(f"[{e_key}] {s_name}"))
                self.table_benchmarks.setItem(row_i, 1, QTableWidgetItem(str(s_vals["questions"])))
                
                it_avg = QTableWidgetItem(f"{s_vals['average_net']:.2f} Net")
                it_avg.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                it_avg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_benchmarks.setItem(row_i, 2, it_avg)
                
                it_sd = QTableWidgetItem(str(s_vals.get("std_dev", "-")))
                it_sd.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_benchmarks.setItem(row_i, 3, it_sd)
                row_i += 1
                
        lay.addWidget(self.table_benchmarks, stretch=1)
        
        # Hazır Şablonlar Kutusu
        grp_tpl = QGroupBox("📦 Popüler Türkiye Geneli Deneme Şablonları")
        grp_tpl.setStyleSheet("font-weight: bold; color: #1e3a8a;")
        v_tpl = QVBoxLayout(grp_tpl)
        v_tpl.addWidget(QLabel("Tek tıkla Türkiye geneli deneme sınavı tanımlayabilirsiniz:"))
        
        h_tpl_btn = QHBoxLayout()
        for tpl_name, tpl_type in [("3D TYT Türkiye Geneli", "TYT"), ("Özdebir AYT TG", "AYT"), ("Bilgi Sarmal TYT", "TYT"), ("MEB LGS Denemesi", "LGS")]:
            btn = QPushButton(f"➕ {tpl_name}")
            btn.setStyleSheet("background: #eff6ff; border: 1.5px solid #93c5fd; color: #1d4ed8; font-weight: bold; padding: 6px 10px; border-radius: 6px;")
            btn.clicked.connect(lambda _, n=tpl_name, t=tpl_type: self._create_template_exam(n, t))
            h_tpl_btn.addWidget(btn)
        v_tpl.addLayout(h_tpl_btn)
        lay.addWidget(grp_tpl)

    def _create_template_exam(self, name: str, exam_type: str):
        today_str = QDate.currentDate().toString("yyyy-MM-dd")
        try:
            con = db.get_conn()
            con.execute("""
                INSERT INTO denemeler (tarih, deneme_adi, yayin_adi, tur, aciklama)
                VALUES (?, ?, ?, ?, 'Türkiye Geneli Hazır Şablon')
            """, (today_str, name, name.split()[0], exam_type))
            con.commit()
            con.close()
            self._load_exam_list()
            QMessageBox.information(self, "Oluşturuldu", f"'{name}' deneme sınavı başarıyla eklendi!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _on_tab_changed(self, idx):
        if idx == 2:
            self._update_analysis()

    # --- VERİ İŞLEMLERİ ---
    def _load_exam_list(self):
        self.table_exams.setRowCount(0)
        con = db.get_conn()
        
        filter_type = self.cmb_filter_type.currentText()
        sql = "SELECT id, tarih, deneme_adi, tur FROM denemeler WHERE 1=1"
        args = []
        if filter_type != "Tümü":
            sql += " AND tur=?"
            args.append(filter_type)
        sql += " ORDER BY tarih DESC, id DESC"
        
        try:
            cur = con.execute(sql, args).fetchall()
            self.kpi_total_exams.lbl_val.setText(str(len(cur)))
            
            for row in cur:
                r = self.table_exams.rowCount()
                self.table_exams.insertRow(r)
                self.table_exams.setItem(r, 0, QTableWidgetItem(str(row["id"])))
                self.table_exams.setItem(r, 1, QTableWidgetItem(row["tarih"]))
                self.table_exams.setItem(r, 2, QTableWidgetItem(row["deneme_adi"]))
                
                # Renkli Tür Rozeti
                tur_str = row["tur"]
                it_tur = QTableWidgetItem(tur_str)
                it_tur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if "TYT" in tur_str:
                    it_tur.setForeground(QColor("#2563eb"))
                elif "AYT" in tur_str:
                    it_tur.setForeground(QColor("#059669"))
                elif "LGS" in tur_str:
                    it_tur.setForeground(QColor("#d97706"))
                self.table_exams.setItem(r, 3, it_tur)
        except Exception as e:
            print(f"Load exams error: {e}")
        finally:
            con.close()

    def _open_settings(self):
        dlg = TrialExamSettingsDialog(self)
        if dlg.exec():
            self._load_config()
            curr_filter = self.cmb_filter_type.currentText()
            self.cmb_filter_type.clear()
            self.cmb_filter_type.addItem("Tümü")
            self.cmb_filter_type.addItems(self.exam_types)
            idx = self.cmb_filter_type.findText(curr_filter)
            if idx >= 0: self.cmb_filter_type.setCurrentIndex(idx)
            if self.current_exam_id:
                self._init_score_table(self.current_exam_type)
                self._load_scores()
                self._load_ranking()

    def _open_new_exam_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Deneme Sınavı")
        dlg.setFixedSize(420, 320)
        dlg.setStyleSheet("background-color: #f8fafc;")
        form = QFormLayout(dlg)
        form.setSpacing(12)
        
        inp_date = QDateEdit(QDate.currentDate()); inp_date.setCalendarPopup(True)
        inp_name = QLineEdit()
        inp_name.setPlaceholderText("Örn: 3D Türkiye Geneli 1")
        inp_pub = QLineEdit()
        inp_pub.setPlaceholderText("Örn: 3D Yayınları")
        inp_type = QComboBox(); inp_type.addItems(self.exam_types)
        inp_desc = QLineEdit()
        inp_desc.setPlaceholderText("İsteğe bağlı not...")
        
        form.addRow("Tarih:", inp_date)
        form.addRow("Deneme Adı:", inp_name)
        form.addRow("Yayın Evi:", inp_pub)
        form.addRow("Sınav Türü:", inp_type)
        form.addRow("Açıklama:", inp_desc)
        
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("Kaydet ve Oluştur")
        btn_ok.setStyleSheet("background: #2563eb; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet("background: white; border: 1px solid #cbd5e1; padding: 8px 16px; border-radius: 6px;")
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_ok); btn_box.addWidget(btn_cancel)
        form.addRow(btn_box)
        
        if dlg.exec():
            if not inp_name.text().strip():
                QMessageBox.warning(self, "Eksik Bilgi", "Lütfen deneme adını giriniz.")
                return
            con = db.get_conn()
            try:
                con.execute("""
                    INSERT INTO denemeler (tarih, deneme_adi, yayin_adi, tur, aciklama)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    inp_date.date().toString("yyyy-MM-dd"),
                    inp_name.text().strip(),
                    inp_pub.text().strip(),
                    inp_type.currentText(),
                    inp_desc.text().strip()
                ))
                con.commit()
                self._load_exam_list()
                QMessageBox.information(self, "Başarılı", "Deneme sınavı başarıyla tanımlandı.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))
            finally:
                con.close()

    def _on_exam_selected(self):
        selected = self.table_exams.selectedItems()
        if not selected:
            self.current_exam_id = None
            self.right_panel.setEnabled(False)
            return
            
        row = selected[0].row()
        exam_id = int(self.table_exams.item(row, 0).text())
        exam_name = self.table_exams.item(row, 2).text()
        exam_type = self.table_exams.item(row, 3).text()
        
        self.current_exam_id = exam_id
        self.current_exam_name = exam_name
        self.current_exam_type = exam_type
        self.right_panel.setEnabled(True)
        
        self.lbl_d_info.setText(f"📝 {exam_name} ({exam_type})")
        
        self._init_score_table(exam_type)
        self._load_scores()
        self._load_ranking()

    def _init_score_table(self, exam_type):
        subjects = self.config.get(exam_type, [])
        if not subjects: subjects = ["Türkçe", "Matematik"]
        self.current_subjects = subjects
        
        headers = ["Öğrenci Adı Soyadı"]
        for subj in subjects:
            short = subj[:4]
            headers.extend([f"{short}\\nD", f"{short}\\nY", "Net"])
            
        headers.append("TOPLAM\\nNET")
        headers.append("ÖSYM/MEB\\nPUAN")
        headers.append("TÜRKİYE\\nDİLİM")

        self.table_scores.setColumnCount(len(headers))
        self.table_scores.setHorizontalHeaderLabels(headers)
        
        self.table_scores.setColumnWidth(0, 160)
        col = 1
        for _ in subjects:
            self.table_scores.setColumnWidth(col, 40)
            self.table_scores.setColumnWidth(col+1, 40)
            self.table_scores.setColumnWidth(col+2, 45)
            col += 3
            
        self.table_scores.setColumnWidth(col, 65) # Toplam net
        self.total_net_col_idx = col
        
        self.table_scores.setColumnWidth(col+1, 75) # Puan
        self.score_col_idx = col + 1
        
        self.table_scores.setColumnWidth(col+2, 70) # Dilim
        self.rank_col_idx = col + 2

    def _load_scores(self):
        if not self.current_exam_id: return
        self.table_scores.setRowCount(0)
        
        con = db.get_conn()
        try:
            students = con.execute("SELECT id, ad, soyad FROM ogrenci WHERE aktif=1 ORDER BY ad, soyad").fetchall()
            rows = con.execute("SELECT * FROM deneme_sonuclari WHERE deneme_id=?", (self.current_exam_id,)).fetchall()
            scores_map = {}
            for r in rows:
                scores_map[(r["ogrenci_id"], r["ders_adi"])] = dict(r)
                
            self.table_scores.setRowCount(len(students))
            
            for row_idx, stu in enumerate(students):
                stu_id = stu["id"]
                it_name = QTableWidgetItem(f"{stu['ad']} {stu['soyad']}")
                it_name.setData(Qt.ItemDataRole.UserRole, stu_id)
                it_name.setFlags(it_name.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table_scores.setItem(row_idx, 0, it_name)
                
                col_idx = 1
                net_dict = {}
                
                for subj in self.current_subjects:
                    data = scores_map.get((stu_id, subj), {})
                    d = data.get("dogru", "")
                    y = data.get("yanlis", "")
                    n = data.get("net", 0.0)
                    
                    net_dict[subj] = float(n) if n else 0.0
                    
                    self.table_scores.setItem(row_idx, col_idx, QTableWidgetItem(str(d) if d != "" else "")); col_idx += 1
                    self.table_scores.setItem(row_idx, col_idx, QTableWidgetItem(str(y) if y != "" else "")); col_idx += 1
                    
                    it_net = QTableWidgetItem(f"{n:.2f}" if n else "")
                    it_net.setFlags(it_net.flags() ^ Qt.ItemFlag.ItemIsEditable)
                    it_net.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_scores.setItem(row_idx, col_idx, it_net); col_idx += 1
                    
                # Hesaplama
                res = calculate_exam_score(self.current_exam_type, net_dict)
                
                # Toplam Net
                it_tot = QTableWidgetItem(f"{res['toplam_net']:.2f}")
                it_tot.setFlags(it_tot.flags() ^ Qt.ItemFlag.ItemIsEditable)
                it_tot.setBackground(QColor("#eff6ff"))
                it_tot.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                it_tot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_scores.setItem(row_idx, self.total_net_col_idx, it_tot)
                
                # Puan
                it_p = QTableWidgetItem(f"{res['ham_puan']:.2f}")
                it_p.setFlags(it_p.flags() ^ Qt.ItemFlag.ItemIsEditable)
                it_p.setBackground(QColor("#f0fdf4"))
                it_p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                it_p.setForeground(QColor("#15803d"))
                it_p.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_scores.setItem(row_idx, self.score_col_idx, it_p)
                
                # Dilim
                it_d = QTableWidgetItem(f"%{res['yuzdelik_dilim']}")
                it_d.setFlags(it_d.flags() ^ Qt.ItemFlag.ItemIsEditable)
                it_d.setBackground(QColor("#fefce8"))
                it_d.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_scores.setItem(row_idx, self.rank_col_idx, it_d)
                
        finally:
            con.close()
            self._update_dash_stats()

    def _save_scores(self):
        if not self.current_exam_id: return
        con = db.get_conn()
        try:
            con.execute("DELETE FROM deneme_sonuclari WHERE deneme_id=?", (self.current_exam_id,))
            row_count = self.table_scores.rowCount()
            
            for r in range(row_count):
                it_name = self.table_scores.item(r, 0)
                if not it_name: continue
                stu_id = it_name.data(Qt.ItemDataRole.UserRole)
                col_idx = 1
                
                for subj in self.current_subjects:
                    d_item = self.table_scores.item(r, col_idx)
                    y_item = self.table_scores.item(r, col_idx+1)
                    
                    d_val = int(d_item.text()) if d_item and d_item.text().isdigit() else 0
                    y_val = int(y_item.text()) if y_item and y_item.text().isdigit() else 0
                    
                    net_val = d_val - (y_val / 4.0)
                    if net_val < 0: net_val = 0.0
                    
                    self.table_scores.item(r, col_idx+2).setText(f"{net_val:.2f}")
                    
                    if d_val > 0 or y_val > 0:
                        con.execute("""
                            INSERT INTO deneme_sonuclari (deneme_id, ogrenci_id, ders_adi, dogru, yanlis, net)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (self.current_exam_id, stu_id, subj, d_val, y_val, net_val))
                    col_idx += 3
                    
            con.commit()
            QMessageBox.information(self, "Kaydedildi", "Deneme sonuçları ve puanları başarıyla kaydedildi.")
            self._load_ranking()
            self._update_dash_stats()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")
        finally:
            con.close()

    def _recalc_row_total(self, row):
        net_dict = {}
        for idx, subj in enumerate(self.current_subjects):
            c = 1 + (idx * 3) + 2
            n_item = self.table_scores.item(row, c)
            val = float(n_item.text()) if n_item and n_item.text() else 0.0
            net_dict[subj] = val
            
        res = calculate_exam_score(self.current_exam_type, net_dict)
        self.table_scores.item(row, self.total_net_col_idx).setText(f"{res['toplam_net']:.2f}")
        self.table_scores.item(row, self.score_col_idx).setText(f"{res['ham_puan']:.2f}")
        self.table_scores.item(row, self.rank_col_idx).setText(f"%{res['yuzdelik_dilim']}")

    def _on_score_changed(self, item):
        if getattr(self, "_updating_score", False): return
        row = item.row(); col = item.column()
        if col == 0 or col >= self.total_net_col_idx: return
        
        rem = (col - 1) % 3
        if rem == 2: return
        
        base = col - rem
        self._updating_score = True
        try:
            d_item = self.table_scores.item(row, base)
            y_item = self.table_scores.item(row, base+1)
            n_item = self.table_scores.item(row, base+2)
            
            d_val = float(d_item.text()) if d_item and d_item.text().strip() else 0.0
            y_val = float(y_item.text()) if y_item and y_item.text().strip() else 0.0
            net = d_val - (y_val / 4.0)
            if net < 0: net = 0.0
            
            n_item.setText(f"{net:.2f}")
            self._recalc_row_total(row)
        except: pass
        finally:
            self._updating_score = False

    def _recalc_all(self):
        for r in range(self.table_scores.rowCount()):
            for idx in range(len(self.current_subjects)):
                c = 1 + (idx * 3)
                self._updating_score = True
                try:
                    d_item = self.table_scores.item(r, c)
                    y_item = self.table_scores.item(r, c+1)
                    n_item = self.table_scores.item(r, c+2)
                    d_val = float(d_item.text()) if d_item and d_item.text().strip() else 0.0
                    y_val = float(y_item.text()) if y_item and y_item.text().strip() else 0.0
                    net = max(0.0, d_val - (y_val / 4.0))
                    n_item.setText(f"{net:.2f}")
                except: pass
                finally: self._updating_score = False
            self._recalc_row_total(r)
        self._update_dash_stats()

    def _update_dash_stats(self):
        total_parts = 0
        total_net_sum = 0.0
        max_net = 0.0
        max_score = 0.0
        
        for r in range(self.table_scores.rowCount()):
            t_item = self.table_scores.item(r, self.total_net_col_idx)
            s_item = self.table_scores.item(r, self.score_col_idx)
            if t_item:
                try:
                    val = float(t_item.text())
                    sc = float(s_item.text()) if s_item else 0.0
                    if val > 0:
                        total_parts += 1
                        total_net_sum += val
                        if val > max_net: max_net = val
                        if sc > max_score: max_score = sc
                except: pass
                
        avg = total_net_sum / total_parts if total_parts > 0 else 0.0
        self.kpi_part.lbl_val.setText(f"{total_parts} Öğrenci")
        self.kpi_class_net.lbl_val.setText(f"{avg:.2f} Net")
        self.kpi_top_score.lbl_val.setText(f"{max_score:.1f} P ({max_net:.1f} N)")
        
        # Türkiye Benchmark Kıyas
        b_key = "TYT" if "TYT" in self.current_exam_type else ("LGS" if "LGS" in self.current_exam_type else "AYT")
        tr_tot = TURKEY_BENCHMARKS.get(b_key, {}).get("total_average_net", 40.0)
        diff_pct = int(((avg - tr_tot) / tr_tot) * 100) if tr_tot > 0 else 0
        if diff_pct >= 0:
            self.kpi_turkey_diff.lbl_val.setText(f"+%{diff_pct} TR Üstü")
            self.kpi_turkey_diff.lbl_val.setStyleSheet("font-size: 14px; font-weight: 900; color: #15803d;")
        else:
            self.kpi_turkey_diff.lbl_val.setText(f"%{diff_pct} TR Altı")
            self.kpi_turkey_diff.lbl_val.setStyleSheet("font-size: 14px; font-weight: 900; color: #dc2626;")

    def _load_ranking(self):
        if not self.current_exam_id: return
        self.table_ranking.setRowCount(0)
        con = db.get_conn()
        try:
            rows = con.execute("""
                SELECT s.ogrenci_id, o.ad, o.soyad, SUM(s.net) as toplam_net
                FROM deneme_sonuclari s
                JOIN ogrenci o ON s.ogrenci_id = o.id
                WHERE s.deneme_id = ?
                GROUP BY s.ogrenci_id
                ORDER BY toplam_net DESC
            """, (self.current_exam_id,)).fetchall()
            
            for i, row in enumerate(rows):
                r = self.table_ranking.rowCount()
                self.table_ranking.insertRow(r)
                
                # Sıra ve Madalya
                medal = "🥇 " if i == 0 else ("🥈 " if i == 1 else ("🥉 " if i == 2 else ""))
                it_rank = QTableWidgetItem(f"{medal}{i+1}")
                it_rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_ranking.setItem(r, 0, it_rank)
                
                # İsim
                it_name = QTableWidgetItem(f"{row['ad']} {row['soyad']}")
                it_name.setData(Qt.ItemDataRole.UserRole, row['ogrenci_id'])
                self.table_ranking.setItem(r, 1, it_name)
                
                # Net
                it_net = QTableWidgetItem(f"{row['toplam_net']:.2f}")
                it_net.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_net.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.table_ranking.setItem(r, 2, it_net)
                
                # Puan ve Sıralama
                # Detaylı netlerini çek
                sub_rows = con.execute("SELECT ders_adi, net FROM deneme_sonuclari WHERE deneme_id=? AND ogrenci_id=?", 
                                       (self.current_exam_id, row['ogrenci_id'])).fetchall()
                net_map = {sr['ders_adi']: sr['net'] for sr in sub_rows}
                calc_res = calculate_exam_score(self.current_exam_type, net_map)
                
                it_sc = QTableWidgetItem(f"{calc_res['ham_puan']:.2f}")
                it_sc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_sc.setForeground(QColor("#15803d"))
                it_sc.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                self.table_ranking.setItem(r, 3, it_sc)
                
                it_dilim = QTableWidgetItem(f"%{calc_res['yuzdelik_dilim']} (İlk {calc_res['tahmini_sira']:,})")
                it_dilim.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table_ranking.setItem(r, 4, it_dilim)
                
                # İşlem Butonu: Karne
                btn_karne = QPushButton("📄 Karne")
                btn_karne.setStyleSheet("background: #eff6ff; color: #2563eb; border: 1px solid #93c5fd; border-radius: 4px; font-weight: bold; padding: 2px 6px;")
                btn_karne.clicked.connect(lambda _, oid=row['ogrenci_id'], rnk=i+1, tot=len(rows): self._open_student_report_card(oid, rnk, tot))
                self.table_ranking.setCellWidget(r, 5, btn_karne)
                
        finally:
            con.close()

    def _open_selected_student_report_card(self):
        curr_row = self.table_scores.currentRow()
        if curr_row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen tablodan bir öğrenci satırı seçiniz.")
            return
        it = self.table_scores.item(curr_row, 0)
        if not it: return
        stu_id = it.data(Qt.ItemDataRole.UserRole)
        self._open_student_report_card(stu_id, curr_row+1, self.table_scores.rowCount())

    def _open_student_report_card(self, student_id: int, rank: int, total_students: int):
        con = db.get_conn()
        try:
            stu_row = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (student_id,)).fetchone()
            if not stu_row: return
            stu_name = f"{stu_row['ad']} {stu_row['soyad']}"
            
            exam_row = con.execute("SELECT deneme_adi, tarih, tur FROM denemeler WHERE id=?", (self.current_exam_id,)).fetchone()
            if not exam_row: return
            
            sub_rows = con.execute("SELECT ders_adi, dogru, yanlis, net FROM deneme_sonuclari WHERE deneme_id=? AND ogrenci_id=?", 
                                   (self.current_exam_id, student_id)).fetchall()
            
            subject_results = []
            net_map = {}
            for sr in sub_rows:
                subject_results.append({
                    "ders": sr["ders_adi"], "d": sr["dogru"], "y": sr["yanlis"], "net": sr["net"], "bos": 0
                })
                net_map[sr["ders_adi"]] = sr["net"]
                
            score_data = calculate_exam_score(exam_row["tur"], net_map)
            
            dlg = StudentReportCardDialog(
                student_name=stu_name,
                exam_name=exam_row["deneme_adi"],
                exam_type=exam_row["tur"],
                exam_date=exam_row["tarih"],
                rank=rank,
                total_students=total_students,
                subject_results=subject_results,
                score_data=score_data,
                parent=self
            )
            dlg.exec()
        finally:
            con.close()

    def _open_turkey_benchmark(self):
        if not self.current_exam_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir deneme sınavı seçiniz.")
            return
        # Calculate subject averages
        class_averages = {}
        con = db.get_conn()
        try:
            rows = con.execute("SELECT ders_adi, AVG(net) as avg_net FROM deneme_sonuclari WHERE deneme_id=? GROUP BY ders_adi", 
                               (self.current_exam_id,)).fetchall()
            for r in rows:
                class_averages[r["ders_adi"]] = round(r["avg_net"] or 0.0, 2)
        finally:
            con.close()
            
        dlg = TurkeyBenchmarkDialog(self.current_exam_type, class_averages, parent=self)
        dlg.exec()

    def _export_ranking_pdf(self):
        if self.table_ranking.rowCount() == 0:
            QMessageBox.warning(self, "Uyarı", "Yazdırılacak sıralama verisi yok.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Sıralama Listesini PDF Olarak Kaydet", 
                                              os.path.expanduser(f"~/Desktop/Siralama_Listesi_{self.current_exam_type}.pdf"), 
                                              "PDF Files (*.pdf)")
        if not path: return
        
        try:
            rows_html = []
            for r in range(self.table_ranking.rowCount()):
                rank_str = self.table_ranking.item(r, 0).text()
                name_str = self.table_ranking.item(r, 1).text()
                net_str = self.table_ranking.item(r, 2).text()
                puan_str = self.table_ranking.item(r, 3).text()
                dilim_str = self.table_ranking.item(r, 4).text()
                
                rows_html.append(f"""
                <tr>
                    <td style="padding:6px;text-align:center;border:1px solid #cbd5e1;font-weight:bold;">{rank_str}</td>
                    <td style="padding:6px;border:1px solid #cbd5e1;font-weight:bold;">{name_str}</td>
                    <td style="padding:6px;text-align:center;border:1px solid #cbd5e1;color:#2563eb;font-weight:bold;">{net_str}</td>
                    <td style="padding:6px;text-align:center;border:1px solid #cbd5e1;color:#15803d;font-weight:bold;">{puan_str}</td>
                    <td style="padding:6px;text-align:center;border:1px solid #cbd5e1;">{dilim_str}</td>
                </tr>
                """)
                
            html = f"""
            <!DOCTYPE html><html><head><meta charset='utf-8'>
            <style>
                @page {{ size: A4 portrait; margin: 15mm; }}
                body {{ font-family: Arial, sans-serif; font-size: 11px; color: #1e293b; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
                th {{ background: #1e293b; color: white; padding: 8px; border: 1px solid #334155; }}
            </style></head><body>
            <h2 style='color:#1e3a8a;margin-bottom:4px;'>🏆 {self.current_exam_name} ({self.current_exam_type})</h2>
            <div style='color:#64748b;'>Resmi Sınav Başarı ve Sıralama Listesi</div>
            <table>
                <thead><tr><th>Sıra</th><th>Öğrenci</th><th>Toplam Net</th><th>Puan</th><th>Türkiye Dilimi</th></tr></thead>
                <tbody>{''.join(rows_html)}</tbody>
            </table>
            </body></html>
            """
            from PyQt6.QtPrintSupport import QPrinter
            doc = QTextDocument()
            doc.setHtml(html)
            prn = QPrinter(QPrinter.PrinterMode.HighResolution)
            prn.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            prn.setOutputFileName(path)
            doc.print(prn)
            QMessageBox.information(self, "Kaydedildi", f"Sıralama listesi PDF olarak kaydedildi:\n\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _export_excel(self):
        if self.table_scores.rowCount() == 0:
            QMessageBox.warning(self, "Uyarı", "Tabloda veri yok.")
            return

        out_path, _ = QFileDialog.getSaveFileName(self, "Excel Olarak Kaydet", f"Deneme_Sonuclari_{self.current_exam_id}.xlsx", "Excel Files (*.xlsx)")
        if not out_path: return

        try:
            import pandas as pd
            headers = [self.table_scores.horizontalHeaderItem(c).text().replace("\n", " ") for c in range(self.table_scores.columnCount())]
            data = []
            for r in range(self.table_scores.rowCount()):
                row_data = []
                for c in range(self.table_scores.columnCount()):
                    it = self.table_scores.item(r, c)
                    val = it.text() if it else ""
                    try: val = float(val)
                    except: pass
                    row_data.append(val)
                data.append(row_data)

            df = pd.DataFrame(data, columns=headers)
            df.to_excel(out_path, index=False)
            QMessageBox.information(self, "Başarılı", f"Dosya kaydedildi:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel hatası:\n{e}")

    def _show_context_menu(self, pos):
        menu = QMenu()
        act_del = QAction("❌ Bu Denemeyi Sil", self)
        act_del.triggered.connect(self._delete_exam)
        menu.addAction(act_del)
        menu.exec(self.table_exams.viewport().mapToGlobal(pos))

    def _delete_exam(self):
        if not self.current_exam_id: return
        if QMessageBox.question(self, "Sil", "Bu denemeyi ve tüm sonuçlarını silmek istiyor musunuz?") != QMessageBox.StandardButton.Yes:
            return
        con = db.get_conn()
        try:
            con.execute("DELETE FROM denemeler WHERE id=?", (self.current_exam_id,))
            con.commit()
            self._load_exam_list()
            self.table_scores.setRowCount(0)
            self.right_panel.setEnabled(False)
        finally:
            con.close()

    def eventFilter(self, source, event):
        if source == self.table_scores and event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Paste):
                self._handle_paste()
                return True
        return super().eventFilter(source, event)

    def _show_table_context_menu(self, pos):
        menu = QMenu()
        act_paste = QAction("📋 Yapıştır (Excel'den)", self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self._handle_paste)
        menu.addAction(act_paste)
        
        act_karne = QAction("📄 Seçili Öğrenciye Karne Çıkar (PDF)", self)
        act_karne.triggered.connect(self._open_selected_student_report_card)
        menu.addAction(act_karne)
        
        menu.exec(self.table_scores.viewport().mapToGlobal(pos))

    def _handle_paste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        rows = text.strip().split('\n')
        if not rows: return
        
        selected = self.table_scores.selectedRanges()
        start_row = selected[0].topRow() if selected else 0
        start_col = selected[0].leftColumn() if selected else 0
        
        for i, row_text in enumerate(rows):
            r = start_row + i
            if r >= self.table_scores.rowCount(): break
            cells = row_text.split('	')
            for j, cell_text in enumerate(cells):
                c = start_col + j
                if c >= self.table_scores.columnCount(): break
                item = self.table_scores.item(r, c)
                if item and (item.flags() & Qt.ItemFlag.ItemIsEditable):
                    item.setText(cell_text.strip())
                    
        self._recalc_all()

    def _update_analysis(self):
        if not self.current_exam_id: return
        con = db.get_conn()
        try:
            rows = con.execute("SELECT ders_adi, net FROM deneme_sonuclari WHERE deneme_id=?", (self.current_exam_id,)).fetchall()
            subject_nets = {}
            for r in rows:
                if r['ders_adi'] not in subject_nets: subject_nets[r['ders_adi']] = []
                subject_nets[r['ders_adi']].append(r['net'])
                
            rows_all = con.execute("SELECT ogrenci_id, SUM(net) as top_net FROM deneme_sonuclari WHERE deneme_id=? GROUP BY ogrenci_id", 
                                   (self.current_exam_id,)).fetchall()
            net_values = [r['top_net'] for r in rows_all if r['top_net'] is not None]
            
            # Grafik 1: Ders Ortalamaları
            self.canvas_subjects.ax.clear()
            subjects = self.current_subjects
            avgs = []
            labels = []
            for subj in subjects:
                nets = subject_nets.get(subj, [])
                avg = sum(nets) / len(nets) if nets else 0.0
                avgs.append(avg)
                labels.append(subj[:4])
                
            bars = self.canvas_subjects.ax.bar(labels, avgs, color='#2563eb', width=0.55)
            self.canvas_subjects.ax.set_ylim(bottom=0)
            self.canvas_subjects.ax.grid(axis='y', linestyle='--', alpha=0.5)
            for rect in bars:
                h = rect.get_height()
                self.canvas_subjects.ax.text(rect.get_x() + rect.get_width()/2., h + 0.1, f'{h:.1f}', ha='center', va='bottom', fontsize=8, fontweight='bold')
            self.canvas_subjects.draw()
            
            # Grafik 2: Net Dağılımı
            self.canvas_dist.ax.clear()
            if net_values:
                n, bins, patches = self.canvas_dist.ax.hist(net_values, bins=max(5, min(15, len(net_values))), color='#10b981', alpha=0.75, edgecolor='white')
                mu = np.mean(net_values)
                sigma = np.std(net_values)
                if sigma > 0:
                    y = ((1 / (np.sqrt(2 * np.pi) * sigma)) * np.exp(-0.5 * (1 / sigma * (bins - mu))**2))
                    y = y * len(net_values) * (bins[1] - bins[0])
                    self.canvas_dist.ax.plot(bins, y, '--', color='#dc2626', linewidth=2, label='Çan Eğrisi')
                    self.canvas_dist.ax.legend()
                self.lbl_class_avg.setText(f"📊 Sınıf Ortalaması: {mu:.2f} Net | En Yüksek: {max(net_values):.2f} Net | Katılım: {len(net_values)} Öğrenci")
            else:
                self.lbl_class_avg.setText("Veri Yok")
            self.canvas_dist.ax.set_xlabel("Net Aralığı")
            self.canvas_dist.ax.set_ylabel("Öğrenci Sayısı")
            self.canvas_dist.draw()
        except Exception as e:
            print("Analiz hatası:", e)
        finally:
            con.close()
