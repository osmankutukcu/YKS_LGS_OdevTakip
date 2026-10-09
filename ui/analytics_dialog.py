# -*- coding: utf-8 -*-
from __future__ import annotations
import sqlite3
from datetime import date, timedelta
from typing import List, Tuple, Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QWidget, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QMessageBox, QFrame, QSplitter
)

# Matplotlib integration
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.patches as mpatches

import db
from utils import analytics_engine as ae

class AnalyticsDialog(QDialog):
    def __init__(self, parent=None, student_id: int = None, student_name: str = ""):
        super().__init__(parent)
        self.student_id = student_id
        self.student_name = student_name
        
        self.setWindowTitle(f"Detaylı Analiz & Gelişim Grafikleri - {student_name}")
        self.resize(1000, 700)
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QTabWidget::pane { border: 1px solid #e2e8f0; background: white; border-radius: 6px; }
            QTabBar::tab {
                background: #f1f5f9; color: #475569; padding: 10px 20px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: white; color: #0f172a; font-weight: bold; border-bottom: 2px solid #3b82f6; }
        """)

        self.layout = QVBoxLayout(self)
        
        # Header
        head = QLabel(f"📊 {student_name} İçin Performans Analizi")
        head.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b; margin: 10px;")
        self.layout.addWidget(head)

        # Tabs
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.tab_subject = QWidget()
        self.tab_trend = QWidget()
        self.tab_weakness = QWidget()

        self.tabs.addTab(self.tab_subject, "Ders Başarısı")
        self.tabs.addTab(self.tab_trend, "Haftalık Gelişim Trendi")
        self.tabs.addTab(self.tab_weakness, "Konu/Kitap Detayları")

        self.setup_subject_tab()
        self.setup_trend_tab()
        self.setup_detail_tab()

        # Load Data
        if self.student_id:
            self.load_data()

    def setup_subject_tab(self):
        lay = QVBoxLayout(self.tab_subject)
        
        # Grafik Alanı
        self.fig_subj = Figure(figsize=(5, 4), dpi=100)
        self.canvas_subj = FigureCanvasQTAgg(self.fig_subj)
        lay.addWidget(self.canvas_subj)
        
        info = QLabel("Bu grafik, öğrencinin bu haftaki (veya son dönemdeki) ders bazlı görev tamamlama yüzdelerini gösterir.")
        info.setStyleSheet("color: #64748b; font-style: italic;")
        lay.addWidget(info)

    def setup_trend_tab(self):
        lay = QVBoxLayout(self.tab_trend)
        
        self.fig_trend = Figure(figsize=(5, 4), dpi=100)
        self.canvas_trend = FigureCanvasQTAgg(self.fig_trend)
        lay.addWidget(self.canvas_trend)

        info = QLabel("Son 5 haftalık genel ilerleme yüzdesi değişimi.")
        info.setStyleSheet("color: #64748b; font-style: italic;")
        lay.addWidget(info)

    def setup_detail_tab(self):
        lay = QVBoxLayout(self.tab_weakness)
        
        self.table_det = QTableWidget()
        self.table_det.setColumnCount(4)
        self.table_det.setHorizontalHeaderLabels(["Ders", "Kitap", "Bitirilen / Toplam", "İlerleme %"])
        self.table_det.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table_det)

    def load_data(self):
        con = db.get_conn()
        try:
            # 1) Ders Grafiği Verisi (Bu Hafta)
            ws, we = ae._week_bounds(date.today())
            ae.rebuild_weekly_by_ders(con, ws, we) # Refresh cache for accurate data
            
            cur = con.cursor()
            rows = cur.execute("""
                SELECT ders, yuzde 
                FROM ogrenci_perf_hafta_ders 
                WHERE ogrenci_id=? AND week_start=? 
                ORDER BY yuzde DESC
            """, (self.student_id, ws.isoformat())).fetchall()

            dersler = []
            yuzdeler = []
            colors = []
            
            for r in rows:
                dersler.append(r['ders'])
                y = r['yuzde']
                yuzdeler.append(y)
                if y >= 80: colors.append('#22c55e') # Green
                elif y >= 50: colors.append('#eab308') # Yellow
                else: colors.append('#ef4444') # Red

            # Plot Subject Bar Chart
            self.fig_subj.clear()
            ax = self.fig_subj.add_subplot(111)
            bars = ax.bar(dersler, yuzdeler, color=colors)
            ax.set_ylim(0, 100)
            ax.set_ylabel('Başarı %')
            ax.set_title('Bu Haftanın Ders Basarımı')
            
            # Rotate labels if too many
            if len(dersler) > 5:
                ax.tick_params(axis='x', rotation=45)
            
            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'%{int(height)}',
                        ha='center', va='bottom')
            
            self.fig_subj.tight_layout()
            self.canvas_subj.draw()

            # 2) Trend Verisi (Son 5 Hafta)
            dates = []
            rates = []
            
            # Geriye dönük 5 hafta
            curr = ws
            for _ in range(5):
                # O haftanın genel yüzdesini bulmak için aggregate etmemiz lazım
                # Yada ogrenci_performans tablosuna bakabiliriz eğer haftalık kayıt atıyorsak.
                # Ama ogrenci_performans genelde seçili aralığı tutar.
                # Basitçe ogrenci_perf_hafta_ders tablosundan ortalama alalım veya yeniden hesaplayalım.
                # Daha kolayı: utils içindeki compute fonksiyonunu çağırıp o aralık için hesaplatmak.
                
                w_end = curr + timedelta(days=6)
                met = ae._compute_metrics_for_student(con, self.student_id, curr, w_end)
                
                label = f"{curr.strftime('%d.%m')}"
                dates.insert(0, label) # Başa ekle (kronolojik)
                rates.insert(0, met['ilerleme_yuzde'])
                
                curr = curr - timedelta(days=7)

            # Plot Trend Line
            self.fig_trend.clear()
            ax2 = self.fig_trend.add_subplot(111)
            ax2.plot(dates, rates, marker='o', linestyle='-', color='#3b82f6', linewidth=3)
            ax2.fill_between(dates, rates, color='#3b82f6', alpha=0.1)
            ax2.set_ylim(0, 105)
            ax2.set_ylabel('Genel İlerleme %')
            ax2.set_title('Haftalık Performans Trendi')
            ax2.grid(True, linestyle='--', alpha=0.6)
            
            for i, txt in enumerate(rates):
                ax2.annotate(f"{txt}%", (dates[i], rates[i]), textcoords="offset points", xytext=(0,10), ha='center')

            self.fig_trend.tight_layout()
            self.canvas_trend.draw()

            # 3) Konu/Kitap Detayları
            ae.rebuild_book_progress(con)
            books = cur.execute("""
                SELECT ders, kitap, konu_say, bitti_say, yuzde 
                FROM ogrenci_kitap_ilerleme
                WHERE ogrenci_id=?
                ORDER BY yuzde ASC
            """, (self.student_id,)).fetchall()
            
            self.table_det.setRowCount(0)
            for row in books:
                r = self.table_det.rowCount()
                self.table_det.insertRow(r)
                self.table_det.setItem(r, 0, QTableWidgetItem(str(row['ders'])))
                self.table_det.setItem(r, 1, QTableWidgetItem(str(row['kitap'])))
                self.table_det.setItem(r, 2, QTableWidgetItem(f"{row['bitti_say']} / {row['konu_say']}"))
                
                # Progress Bar in Table? Or just color text
                prob_item = QTableWidgetItem(f"%{row['yuzde']}")
                if row['yuzde'] < 50:
                    prob_item.setForeground(QColor('#ef4444'))
                elif row['yuzde'] >= 80:
                    prob_item.setForeground(QColor('#22c55e'))
                
                self.table_det.setItem(r, 3, prob_item)

        except Exception as e:
            QMessageBox.warning(self, "Veri Hatası", f"Analiz verileri alınırken hata: {str(e)}")
        finally:
            con.close()
