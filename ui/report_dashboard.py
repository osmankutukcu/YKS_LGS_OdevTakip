# -*- coding: utf-8 -*-
"""
ui/report_dashboard.py
Toplu Değerlendirme / Veli Raporu ekranı.

Özellikler:
- Öğrenci listesi: Toplam Görev / Tamamlanan / Başarı %
    -> ogrenci_perf_hafta_ders tablosundan, ders bazlı haftalık özetlerin
       öğrenci bazında toplanmış hali.
- Sınıf filtresi: ogrenci.alt_grup alanına göre (11.sınıf, mezun-say vb.)
- Üst grafik: Öğrencilerin Başarı Yüzdeleri (İlk N)
    -> N: 10 / 20 / 30 / 40 / 50 combobox ile seçilir.
- Alt grafik: Derslere Göre Başarı Yüzdeleri
    -> Mod combobox: "Genel (Tüm Öğrenciler)" / "Seçili Öğrenci"
"""

import os
import sys
import os

# Kendi başına çalıştırıldığında kök dizini (package root) görsün
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import sqlite3
from typing import List, Optional, Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableView, QSpinBox, QFileDialog, QMessageBox, QWidget, QSplitter
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from services.parent_report import generate_parent_report
from services.report_settings import load_settings
from ui.report_settings_dialog import ReportSettingsDialog

from PyQt6.QtWidgets import QDialog


from ui.reports import RaporlarFormu  # <-- Eski "RaporlarFormu" nun yolu
import db  # Eğer bu dosyada zaten kullanıyorsan tekrar yazma





# ---------------- Matplotlib Canvas ----------------

class _MatCanvas(FigureCanvasQTAgg):
    def __init__(self, parent: QWidget = None):
        fig = Figure(figsize=(4, 3))
        self.ax = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)


# ---------------- Ana Dialog ----------------

class ReportDashboard(QDialog):
    """
    Toplu değerlendirme ve toplu veli raporu ekranı.
    """

    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con

        self.setWindowTitle("Toplu Değerlendirme / Genel Görünüm")
        self.resize(1200, 700)

        # Bu değişkenler grafiklerde tekrar kullanmak için
        self._summary_rows: List[sqlite3.Row] = []
        self.settings = load_settings(self.con)
        self._legacy_win = None  # Eski Raporlar formu için pencere referansı

        # 1) Arayüz
        self._build_ui()

        # 2) Filtre combobox'larını doldur
        self._load_filters()

        # 3) Başlangıç verisini yükle
        # 3) Başlangıç verisini yükle
        self.refresh_data()
        
        # 4) Stil
        self._apply_modern_visuals()

    # ---------- Stil ----------
    def _apply_modern_visuals(self):
        self.setStyleSheet("""
            QDialog, QWidget { 
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
                font-size: 13px; 
                background-color: #f8fafc; 
                color: #1e293b; 
            }
            
            /* -- Tablo -- */
            QTableView {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff;
                selection-color: #1e3a8a;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 600;
                color: #475569;
                text-transform: uppercase;
                font-size: 11px;
            }

            /* -- Butonlar -- */
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
                color: #475569;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #94a3b8;
                color: #334155;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }

            /* -- Özel Butonlar (Object Name ile) -- */
            /* Primary (Mavi) - Yenile */
            QPushButton#btnPrimary {
                background-color: #2563eb; color: white; border: 1px solid #2563eb;
            }
            QPushButton#btnPrimary:hover { background-color: #1d4ed8; border-color: #1d4ed8; }

            /* Success (Yeşil) - Excel */
            QPushButton#btnExcel {
                background-color: #ecfdf5; color: #059669; border: 1px solid #a7f3d0;
            }
            QPushButton#btnExcel:hover { background-color: #d1fae5; }

            /* PDF (Pastel Kırmızı) */
            QPushButton#btnPdf {
                background-color: #fff1f2; color: #be123c; border: 1px solid #fb7185;
            }
            QPushButton#btnPdf:hover { background-color: #ffe4e6; }
            
            /* Info (Mor) - Settings */
            QPushButton#btnInfo {
                background-color: #f3e8ff; color: #7c3aed; border: 1px solid #e9d5ff;
            }
            QPushButton#btnInfo:hover { background-color: #e9d5ff; }

            /* -- Inputs -- */
            QComboBox, QSpinBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: #ffffff;
            }
            QComboBox:focus, QSpinBox:focus {
                border: 2px solid #3b82f6;
            }
            
            QSplitter::handle {
                background-color: #cbd5e1;
            }
        """)

    # ---------- UI Kurulumu ----------

    def _build_ui(self) -> None:
        main = QVBoxLayout(self)

        # --- Üst filtre bar ---
        top_row = QHBoxLayout()
        self.lbl_sinif = QLabel("Sınıf:")
        top_row.addWidget(self.lbl_sinif)

        self.cmb_sinif = QComboBox()
        self.cmb_sinif.setMinimumWidth(160)
        top_row.addWidget(self.cmb_sinif)

        top_row.addSpacing(20)
        top_row.addWidget(QLabel("Min %:"))
        self.spin_min_pct = QSpinBox()
        self.spin_min_pct.setRange(0, 100)
        self.spin_min_pct.setValue(0)
        top_row.addWidget(self.spin_min_pct)

        top_row.addStretch()

        self.btn_settings = QPushButton("⚙️ Kriter Ayarları")
        self.btn_settings.setObjectName("btnInfo")
        self.btn_refresh = QPushButton("🔄 Analizleri Yenile")
        self.btn_refresh.setObjectName("btnPrimary")
        self.btn_legacy_reports = QPushButton("📄 Detaylı Raporlar")
        self.btn_legacy_reports.setObjectName("btnPrimary")

        top_row.addWidget(self.btn_settings)
        top_row.addWidget(self.btn_refresh)
        top_row.addWidget(self.btn_legacy_reports)

        main.addLayout(top_row)

        # --- Yönetici KPI Ribbon ---
        kpi_ribbon = QHBoxLayout()
        kpi_ribbon.setSpacing(10)

        def _make_kpi_card(title: str, color: str):
            w = QWidget()
            w.setStyleSheet("""
                QWidget {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                }
                QLabel {
                    background: transparent;
                    border: none;
                }
            """)
            l = QVBoxLayout(w)
            l.setContentsMargins(12, 6, 12, 6)
            l.setSpacing(2)
            lt = QLabel(title)
            lt.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
            lv = QLabel("-")
            lv.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            l.addWidget(lt)
            l.addWidget(lv)
            return w, lv

        c1, self.lbl_kpi_total_st = _make_kpi_card("👥 Toplam Öğrenci", "#2563eb")
        c2, self.lbl_kpi_avg_succ = _make_kpi_card("📈 Sınıf Başarı Ortalaması", "#10b981")
        c3, self.lbl_kpi_champs = _make_kpi_card("👑 %80+ Şampiyon Kulübü", "#d97706")
        c4, self.lbl_kpi_at_risk = _make_kpi_card("⚠️ Takip Gerekenler (< %50)", "#ef4444")
        kpi_ribbon.addWidget(c1)
        kpi_ribbon.addWidget(c2)
        kpi_ribbon.addWidget(c3)
        kpi_ribbon.addWidget(c4)
        main.addLayout(kpi_ribbon)

        # --- Orta alan: sol tablo, sağ grafikler ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol: öğrenci tablo
        self.table = QTableView()
        self.table_model = QStandardItemModel(self)
        self.table.setModel(self.table_model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        splitter.addWidget(self.table)

        # Sağ: grafikler
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        # Üst grafik başlık + top N combobox
        top_title_row = QHBoxLayout()
        self.lbl_top = QLabel("Öğrencilerin Başarı Yüzdeleri")
        self.lbl_top.setStyleSheet("font-weight: bold;")
        top_title_row.addWidget(self.lbl_top)

        top_title_row.addStretch()
        top_title_row.addWidget(QLabel("Gösterilecek Öğrenci:"))
        self.cmb_topN = QComboBox()
        for n in (10, 20, 30, 40, 50):
            self.cmb_topN.addItem(str(n), n)
        self.cmb_topN.setCurrentIndex(0)  # 10
        top_title_row.addWidget(self.cmb_topN)

        right_layout.addLayout(top_title_row)

        self.canvas_students = _MatCanvas(right_widget)
        self.ax_students = self.canvas_students.ax
        right_layout.addWidget(self.canvas_students, stretch=3)

        # Alt grafik başlık + mod combobox
        bottom_title_row = QHBoxLayout()
        self.lbl_ders = QLabel("Derslere Göre Başarı Yüzdeleri")
        self.lbl_ders.setStyleSheet("font-weight: bold;")
        bottom_title_row.addWidget(self.lbl_ders)

        bottom_title_row.addStretch()
        bottom_title_row.addWidget(QLabel("Mod:"))
        self.cmb_ders_mode = QComboBox()
        self.cmb_ders_mode.addItem("Genel (Tüm Öğrenciler)", "genel")
        self.cmb_ders_mode.addItem("Seçili Öğrenci", "ogrenci")
        bottom_title_row.addWidget(self.cmb_ders_mode)

        right_layout.addLayout(bottom_title_row)

        self.canvas_ders = _MatCanvas(right_widget)
        self.ax_ders = self.canvas_ders.ax
        right_layout.addWidget(self.canvas_ders, stretch=2)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        main.addWidget(splitter)

        # --- Alt butonlar ---
        bottom = QHBoxLayout()
        self.btn_parent = QPushButton("📄 Seçili Veli PDF")
        self.btn_parent.setObjectName("btnPdf")
        self.btn_parent_all = QPushButton("📚 Tüm Liste PDF")
        self.btn_parent_all.setObjectName("btnPdf")
        self.btn_export_excel = QPushButton("📊 Excel’e Aktar")
        self.btn_export_excel.setObjectName("btnExcel")

        bottom.addWidget(self.btn_parent)
        bottom.addWidget(self.btn_parent_all)
        bottom.addStretch()
        bottom.addWidget(self.btn_export_excel)

        main.addLayout(bottom)

        # --- Bağlantılar ---
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_parent.clicked.connect(self._make_single_parent_pdf)
        self.btn_parent_all.clicked.connect(self._make_bulk_parent_pdf)
        self.btn_export_excel.clicked.connect(self._export_excel)

        # BURASI ÖNEMLİ: yeni buton sinyali
        self.btn_legacy_reports.clicked.connect(self._open_legacy_reports)

        # satır seçimi, grafik güncelleme
        self.table.selectionModel().selectionChanged.connect(
            self._on_row_selection_changed
        )
        self.cmb_topN.currentIndexChanged.connect(
            lambda *_: self._update_student_chart(self._summary_rows)
        )
        self.cmb_ders_mode.currentIndexChanged.connect(
            lambda *_: self._update_ders_chart(self._selected_student_id())
        )


    def _open_legacy_reports(self):
        """Üstteki 'Detaylı Raporlar (Eski)' butonu."""
        # Zaten açıksa öne getir
        if self._legacy_win is not None:
            try:
                self._legacy_win.raise_()
                self._legacy_win.activateWindow()
            except Exception:
                pass
            return

        # Önce kendimizi gizleyelim
        self.hide()

        # Eski rapor penceresini oluştur
        legacy = RaporlarFormu(self)
        legacy.setWindowTitle("Detaylı Raporlar")
        legacy.setWindowFlag(Qt.WindowType.Window, True)
        legacy.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Boyut ve merkez konum (açılmadan önce)
        legacy.resize(1200, 700)
        center = self.geometry().center()
        geo = legacy.frameGeometry()
        geo.moveCenter(center)
        legacy.move(geo.topLeft())

        # Kapanınca tekrar dashboard açılsın
        def _on_closed(*_):
            self._legacy_win = None
            self.show()
            self.raise_()
            self.activateWindow()

        legacy.destroyed.connect(_on_closed)

        self._legacy_win = legacy

        # --- Platform Tespiti ve Tam Ekran Ayarı ---
        import platform
        system = platform.system()

        if system == "Windows":
            legacy.showMaximized()  # Tam ekran benzeri açılış
            # Tam gerçek fullscreen istersen bunu açabilirsin:
            # legacy.showFullScreen()
        else:
            # macOS ve Linux → maximize daha kullanıcı dostu
            legacy.showMaximized()

    # ---------- Filtreler ----------

    def _load_filters(self) -> None:
        """
        Sınıf filtresi için ogrenci.alt_grup alanını kullanır.
        (11.sınıf, 10.sınıf, mezun-say vb.)
        """
        self.cmb_sinif.clear()
        self.cmb_sinif.addItem("Hepsi", "")

        try:
            cur = self.con.execute(
                """
                SELECT DISTINCT alt_grup
                  FROM ogrenci
                 WHERE alt_grup IS NOT NULL
                   AND TRIM(alt_grup) <> ''
                 ORDER BY alt_grup
                """
            )
            for row in cur.fetchall():
                self.cmb_sinif.addItem(row["alt_grup"], row["alt_grup"])
        except Exception:
            # Hata olsa da ekran çalışsın
            pass

    # ---------- Özet satırları çekme ----------

    def _get_summary_rows(self):
        """
        Öğrenci listesi için özet satırları getirir.

        Kaynak:
            - ogrenci
            - odev_kume
            - odev

        Toplam Görev  = o öğrencinin tüm kümelerindeki odev satır sayısı
        Tamamlanan    = durum'a göre "yapıldı" kabul edilen satırlar
                        (Kriter ayarlarına göre 'aktarildi' satırları
                         tamam kabul edilebilir veya edilmeyebilir.)
        Başarı %      = 100 * Tamamlanan / Toplam Görev
        """
        # --- Filtreler ---
        sinif_val = self.cmb_sinif.currentData()
        sinif_filter = (sinif_val or "").strip()
        min_pct = int(self.spin_min_pct.value())

        where_ogr = ["o.aktif = 1"]
        params: list[Any] = []

        if sinif_filter:
            where_ogr.append("COALESCE(o.alt_grup,'') = ?")
            params.append(sinif_filter)

        where_sql = " AND ".join(where_ogr)

        # --- Kriter ayarlarını oku ---
        settings = getattr(self, "settings", {}) or {}
        aktar_mod = settings.get("aktarilan_sayilma_sekli", "done")

        # Her durumda "tamam" kabul edilen durumlar
        base_done_statuses = [
            "yapildi", "yapıldı", "tamam", "bitti", "done",
            "tamamlandı", "✓", "ok", "1", "true", "evet"
        ]

        done_statuses = list(base_done_statuses)

        # Eğer kullanıcı "YAPILDI kabul et" seçtiyse
        # → 'aktarildi' / 'aktarıldı' durumları da tamam kabul edilir
        if aktar_mod == "done":
            done_statuses += ["aktarildi", "aktarıldı", "aktarim", "aktarım"]

        # SQL IN (...) listesi için placeholder üret
        in_placeholders = ", ".join("?" for _ in done_statuses)

        sql = f"""
            SELECT
                o.id AS ogrenci_id,
                (o.ad || ' ' || o.soyad)                AS ad_soyad,
                COALESCE(o.alt_grup, '')               AS sinif_grup,
                COUNT(d.id)                            AS gorev_toplam,
                SUM(
                    CASE
                        WHEN LOWER(TRIM(COALESCE(d.durum,''))) IN ({in_placeholders})
                        THEN 1 ELSE 0
                    END
                )                                      AS gorev_bitti
            FROM ogrenci o
            LEFT JOIN odev_kume k
                   ON k.ogrenci_id = o.id
            LEFT JOIN odev d
                   ON d.kume_id = k.id
            WHERE {where_sql}
            GROUP BY o.id, o.ad, o.soyad, o.alt_grup
        """

        # Sınıf filtresi parametreleri + durum listesi parametreleri
        all_params: list[Any] = list(params) + done_statuses

        cur = self.con.execute(sql, all_params)
        rows = []

        for r in cur.fetchall():
            toplam = int(r["gorev_toplam"] or 0)
            bitti = int(r["gorev_bitti"] or 0)
            if toplam <= 0:
                basari_pct = 0.0
            else:
                basari_pct = round(100.0 * bitti / toplam, 1)

            if min_pct and basari_pct < min_pct:
                continue

            rows.append({
                "ogrenci_id": r["ogrenci_id"],
                "ad_soyad": r["ad_soyad"] or "",
                "sinif_grup": r["sinif_grup"] or "",
                "gorev_toplam": toplam,
                "gorev_bitti": bitti,
                "basari_pct": basari_pct,
            })

        # Başarıya göre büyükten küçüğe sırala
        rows.sort(key=lambda x: (-x["basari_pct"], x["ad_soyad"].lower()))
        return rows

    def _get_summary_rows(self):
        """
        Öğrenci listesi için özet satırları getirir.

        Kaynak:
            - ogrenci
            - odev_kume
            - odev

        Toplam Görev  = o öğrencinin tüm kümelerindeki odev satır sayısı
        Tamamlanan    = durum'a göre "yapıldı" kabul edilen satırlar
                        (Kriter ayarlarına göre 'aktarildi' satırları
                         tamam kabul edilebilir veya edilmeyebilir.)
        Başarı %      = 100 * Tamamlanan / Toplam Görev
        """
        # --- Filtreler ---
        # Combobox üzerindeki görünen metne göre filtreleyeceğiz
        sinif_text = (self.cmb_sinif.currentText() or "").strip()
        # "Hepsi" seçiliyse sınıf filtresi yok demektir
        if sinif_text.lower().startswith("hepsi"):
            sinif_filter = ""
        else:
            sinif_filter = sinif_text

        min_pct = int(self.spin_min_pct.value())

        # Sadece aktif öğrenciler
        where_ogr = ["o.aktif = 1"]
        where_sql = " AND ".join(where_ogr)
        params: list[Any] = []  # şu anda sadece durum listesi için kullanacağız

        # --- Kriter ayarlarını oku ---
        settings = getattr(self, "settings", {}) or {}
        aktar_mod = settings.get("aktarilan_sayilma_sekli", "done")

        # Her durumda "tamam" kabul edilen durumlar
        base_done_statuses = [
            "yapildi", "yapıldı", "tamam", "bitti", "done",
            "tamamlandı", "✓", "ok", "1", "true", "evet"
        ]

        done_statuses = list(base_done_statuses)

        # Eğer kullanıcı "YAPILDI kabul et" seçtiyse
        # → 'aktarildi' / 'aktarıldı' durumları da tamam kabul edilir
        if aktar_mod == "done":
            done_statuses += ["aktarildi", "aktarıldı", "aktarim", "aktarım"]

        # SQL IN (...) listesi için placeholder üret
        in_placeholders = ", ".join("?" for _ in done_statuses)

        sql = f"""
            SELECT
                o.id AS ogrenci_id,
                (o.ad || ' ' || o.soyad)                AS ad_soyad,
                COALESCE(o.alt_grup, '')               AS sinif_grup,
                COUNT(d.id)                            AS gorev_toplam,
                SUM(
                    CASE
                        WHEN LOWER(TRIM(COALESCE(d.durum,''))) IN ({in_placeholders})
                        THEN 1 ELSE 0
                    END
                )                                      AS gorev_bitti
            FROM ogrenci o
            LEFT JOIN odev_kume k
                   ON k.ogrenci_id = o.id
            LEFT JOIN odev d
                   ON d.kume_id = k.id
            WHERE {where_sql}
            GROUP BY o.id, o.ad, o.soyad, o.alt_grup
        """

        # Yalnızca durum listesi parametreleri
        all_params: list[Any] = list(params) + done_statuses

        cur = self.con.execute(sql, all_params)
        rows = []

        for r in cur.fetchall():
            toplam = int(r["gorev_toplam"] or 0)
            bitti = int(r["gorev_bitti"] or 0)
            if toplam <= 0:
                basari_pct = 0.0
            else:
                basari_pct = round(100.0 * bitti / toplam, 1)

            # --- Sınıf filtresini PYTHON tarafında uygula ---
            sinif_grup = (r["sinif_grup"] or "").strip()
            if sinif_filter and sinif_grup != sinif_filter:
                continue

            # Min % filtresi
            if min_pct and basari_pct < min_pct:
                continue

            rows.append({
                "ogrenci_id": r["ogrenci_id"],
                "ad_soyad": r["ad_soyad"] or "",
                "sinif_grup": sinif_grup,
                "gorev_toplam": toplam,
                "gorev_bitti": bitti,
                "basari_pct": basari_pct,
            })

        # Başarıya göre büyükten küçüğe sırala
        rows.sort(key=lambda x: (-x["basari_pct"], x["ad_soyad"].lower()))
        return rows

    def refresh_data(self) -> None:
        # Verileri çek
        rows = self._get_summary_rows()
        self._summary_rows = rows  # grafikte yeniden kullanacağız

        # Tabloyu doldur
        self.table_model.clear()
        headers = ["Öğrenci ID", "Ad Soyad", "Sınıf/Grup",
                   "Toplam Görev", "Tamamlanan", "Başarı %"]
        self.table_model.setHorizontalHeaderLabels(headers)

        for r in rows:
            items = [
                QStandardItem(str(r["ogrenci_id"])),
                QStandardItem(r["ad_soyad"]),
                QStandardItem(r["sinif_grup"]),
                QStandardItem(str(r["gorev_toplam"])),
                QStandardItem(str(r["gorev_bitti"])),
                QStandardItem(f"{r['basari_pct']:.1f}"),
            ]
            for it in items:
                it.setEditable(False)
            self.table_model.appendRow(items)

        self.table.resizeColumnsToContents()

        # Update KPI Ribbon
        if hasattr(self, 'lbl_kpi_total_st'):
            total_st = len(rows)
            avg_pct = round(sum(r["basari_pct"] for r in rows) / total_st, 1) if total_st > 0 else 0.0
            champs = sum(1 for r in rows if r["basari_pct"] >= 80.0)
            at_risk = sum(1 for r in rows if r["basari_pct"] < 50.0)
            self.lbl_kpi_total_st.setText(f"{total_st} Öğrenci")
            self.lbl_kpi_avg_succ.setText(f"% {avg_pct:.1f}")
            self.lbl_kpi_champs.setText(f"{champs} Öğrenci")
            self.lbl_kpi_at_risk.setText(f"{at_risk} Öğrenci")

        # Grafikler
        self._update_student_chart(rows)
        # alt grafiği başlangıçta GENEL modda bırakalım
        self._update_ders_chart(None)

    # ---------- Kriter Ayarları ----------

    def _open_settings(self) -> None:
        # DİKKAT: parametre sırası (parent, con)
        dlg = ReportSettingsDialog(self, self.con)

        # Kullanıcı "Kaydet"e basarsa → Accepted döner
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Ayarları yeniden oku
            self.settings = load_settings(self.con)
            # Tablo + grafikleri yeniden çiz
            self.refresh_data()

    # ---------- Üst Grafik: Öğrenci Başarıları ----------

    def _update_student_chart(self, rows=None):
        """
        Üst grafik: Öğrencilerin başarı yüzdeleri.
        En yüksek başarı en üstte görünecek.
        """
        if rows is None:
            rows = getattr(self, "_summary_rows", [])

        ax = self.canvas_students.ax
        ax.clear()

        if not rows:
            ax.text(0.5, 0.5, "Veri yok",
                    ha="center", va="center", fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas_students.draw()
            return

        # combobox’tan N değerini al
        try:
            n = int(self.cmb_topN.currentData() or self.cmb_topN.currentText())
        except Exception:
            n = 10

        top_rows = rows[:n]

        names = [r["ad_soyad"] for r in top_rows]
        pcts = [float(r["basari_pct"] or 0.0) for r in top_rows]

        y_pos = list(range(len(names)))
        ax.barh(y_pos, pcts)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=8)
        ax.set_xlim(0, 100)
        ax.set_xlabel("%")

        # Yüzdeleri çubukların yanına yaz
        for i, v in enumerate(pcts):
            ax.text(v + 1, i, f"{v:.1f}%", va="center", fontsize=8)

        # En başarılı öğrenci en üstte görünsün
        ax.invert_yaxis()

        self.canvas_students.draw()

    # ---------- Alt Grafik: Ders Başarıları ----------

    def _update_ders_chart(self, ogrenci_id: Optional[int] = None) -> None:
        """
        Alt grafiği (derslere göre başarı yüzdeleri) günceller.

        ogrenci_id = None  -> Genel (tüm öğrenciler)
        ogrenci_id = id    -> Sadece seçili öğrenci
        """
        cur = self.con.cursor()

        if ogrenci_id is None or self.cmb_ders_mode.currentData() == "genel":
            # GENEL MOD: tüm öğrenciler için ders bazında
            sql = """
                SELECT
                    ders,
                    SUM(toplam) AS toplam,
                    SUM(bitti)  AS bitti,
                    CASE
                        WHEN SUM(toplam) = 0 THEN 0
                        ELSE ROUND(100.0 * SUM(bitti) / SUM(toplam), 1)
                    END AS pct
                FROM ogrenci_perf_hafta_ders
                GROUP BY ders
                HAVING toplam > 0
                ORDER BY pct DESC
            """
            cur.execute(sql)
        else:
            # SEÇİLİ ÖĞRENCİ MODU
            sql = """
                SELECT
                    ders,
                    SUM(toplam) AS toplam,
                    SUM(bitti)  AS bitti,
                    CASE
                        WHEN SUM(toplam) = 0 THEN 0
                        ELSE ROUND(100.0 * SUM(bitti) / SUM(toplam), 1)
                    END AS pct
                FROM ogrenci_perf_hafta_ders
                WHERE ogrenci_id = ?
                GROUP BY ders
                HAVING toplam > 0
                ORDER BY pct DESC
            """
            cur.execute(sql, (ogrenci_id,))

        rows = cur.fetchall()

        ax = self.ax_ders
        ax.clear()

        if not rows:
            ax.text(0.5, 0.5, "Veri yok", ha="center", va="center")
            ax.set_xticks([])
            ax.set_yticks([])
            self.canvas_ders.draw()
            return

        dersler = [r["ders"] for r in rows]
        pct_list = [float(r["pct"] or 0) for r in rows]
        y_pos = range(len(dersler))

        ax.barh(list(y_pos), pct_list)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(dersler)
        ax.set_xlim(0, 100)
        ax.set_xlabel("%")

        for i, v in enumerate(pct_list):
            ax.text(v + 1, i, f"{v:.1f}%", va="center")

        self.canvas_ders.draw()

    # ---------- Tablo seçim / yardımcılar ----------

    def _selected_student_id(self) -> int:
        index = self.table.currentIndex()
        if not index.isValid():
            return -1
        row = index.row()
        id_index = self.table_model.index(row, 0)
        try:
            return int(self.table_model.data(id_index))
        except Exception:
            return -1

    def _on_row_selection_changed(self, *args, **kwargs) -> None:
        if self.cmb_ders_mode.currentData() == "ogrenci":
            sid = self._selected_student_id()
        else:
            sid = None
        self._update_ders_chart(sid)

    # ---------- PDF Üretimi ----------

    def _make_single_parent_pdf(self) -> None:
        sid = self._selected_student_id()
        if sid <= 0:
            QMessageBox.warning(self, "Seçim yok", "Lütfen tablodan bir öğrenci seçin.")
            return

        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Veli PDF kaydet",
            f"veli_rapor_{sid}.pdf",
            "PDF Dosyası (*.pdf)"
        )
        if not fname:
            return

        try:
            generate_parent_report(self.con, sid, fname, self.settings)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulurken hata oluştu:\n{e}")
            return

        QMessageBox.information(self, "Tamam", "Veli raporu başarıyla oluşturuldu.")

    def _make_bulk_parent_pdf(self) -> None:
        row_count = self.table_model.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "Veri yok", "Listede öğrenci bulunmuyor.")
            return

        folder = QFileDialog.getExistingDirectory(self, "PDF'lerin kaydedileceği klasör")
        if not folder:
            return

        errors = []
        for row in range(row_count):
            id_index = self.table_model.index(row, 0)
            name_index = self.table_model.index(row, 1)
            try:
                sid = int(self.table_model.data(id_index))
            except Exception:
                continue
            name = self.table_model.data(name_index) or str(sid)
            safe_name = "".join(ch for ch in name if ch not in r'\/:*?"<>|')
            path = os.path.join(folder, f"veli_rapor_{safe_name}_{sid}.pdf")
            try:
                generate_parent_report(self.con, sid, path, self.settings)
            except Exception as e:
                errors.append(f"{sid}: {e}")

        if errors:
            QMessageBox.warning(
                self,
                "Tamamlandı (bazı hatalar)",
                "Çoğu PDF oluşturuldu ama bazı öğrencilerde hata oluştu.\n\n"
                + "\n".join(errors[:10]),
            )
        else:
            QMessageBox.information(self, "Tamam", "Tüm veli raporları başarıyla oluşturuldu.")

    # ---------- Excel Aktarımı ----------

    def _export_excel(self) -> None:
        row_count = self.table_model.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "Veri yok", "Aktarılacak satır yok.")
            return

        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Tabloyu Kaydet",
            "toplu_degerlendirme.xlsx",
            "Excel Dosyası (*.xlsx);;CSV (*.csv)"
        )
        if not fname:
            return

        if fname.lower().endswith(".csv"):
            import csv
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                headers = [
                    self.table_model.headerData(c, Qt.Orientation.Horizontal)
                    for c in range(self.table_model.columnCount())
                ]
                writer.writerow(headers)
                for r in range(row_count):
                    row_vals = [
                        self.table_model.data(self.table_model.index(r, c)) or ""
                        for c in range(self.table_model.columnCount())
                    ]
                    writer.writerow(row_vals)
        else:
            try:
                import pandas as pd
            except ImportError:
                QMessageBox.critical(self, "Hata", "Excel için pandas modülü gerekiyor.")
                return
            data = []
            headers = [
                self.table_model.headerData(c, Qt.Orientation.Horizontal)
                for c in range(self.table_model.columnCount())
            ]
            for r in range(row_count):
                row_vals = [
                    self.table_model.data(self.table_model.index(r, c)) or ""
                    for c in range(self.table_model.columnCount())
                ]
                data.append(row_vals)
            df = pd.DataFrame(data, columns=headers)
            try:
                df.to_excel(fname, index=False)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Excel yazarken hata:\n{e}")
                return

        QMessageBox.information(self, "Tamam", "Tablo başarıyla dışa aktarıldı.")