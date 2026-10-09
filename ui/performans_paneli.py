# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, QPoint, QSize, QRect, QMarginsF
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QFont,
    QImage,
    QPageLayout,
    QPageSize,
    QPdfWriter,
    QPen,
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QSizePolicy,
    QHeaderView,
    QStyledItemDelegate,
    QFileDialog,
    QTableView,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QFrame,
    QSplitter,
    QToolButton,
    QApplication,
    QProgressDialog,
    QMessageBox,
)
from utils.web_portal import WebPortalGenerator
from ui.analytics_dialog import AnalyticsDialog
from PyQt6.QtGui import QIcon, QAction

try: 
    from ui.theme import Theme
except: pass

import math

import math
import os
import re
import tempfile

import xlsxwriter

import db


# ------------------ Tarih yardımcıları ------------------


def _week_bounds(d: date):
    """Verilen tarihin haftasının (Pazartesi–Pazar) başlangıç ve bitişi."""
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def _last30_bounds(d: date):
    """Son 30 günün [start, end] sınırları (bugün dahil)."""
    start = d - timedelta(days=29)
    end = d
    return start, end


# ------------------ Ana Dialog ------------------


class PerformansPaneli(QDialog):
    """
    3 sekme:
      1) Haftanın ilk 5’i        → son hafta en yüksek ilerleme yüzdesi
      2) Gecikme trendi artanlar → son 30 güne göre geciken ödev sayısı artanlar
      3) %80+ Kulübü             → haftalık ve/veya 30 günlük oranı >=80 olanlar

    Hesaplamalar doğrudan günlüklere bakan `ogrenci_perf_gunluk`
    tablosundan yapılıyor.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Performans Paneli")
        self.resize(900, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Stil ---
        self.setStyleSheet("""
            QDialog { background-color: #f1f5f9; }
            QLabel { font-family: 'Segoe UI'; }
            QPushButton { font-family: 'Segoe UI'; border-radius: 6px; }
        """)

        # --- Üst Toolbar (Modern) ---
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: white; border-bottom: 1px solid #e2e8f0;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(20, 15, 20, 15)
        tb_layout.setSpacing(15)

        # 1. Başlık ve İkon
        lbl_head = QLabel("📊 Performans Analizi")
        lbl_head.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        tb_layout.addWidget(lbl_head)
        
        # 2. Tarih Seçimi (Dönem)
        self.comboPeriod = QComboBox()
        self.comboPeriod.addItems(["Bu Hafta", "Geçen Hafta"])
        self.comboPeriod.setFixedWidth(130)
        self.comboPeriod.setStyleSheet("""
            QComboBox {
                padding: 6px; border: 1px solid #cbd5e1; border-radius: 6px;
                background-color: #f8fafc; color: #334155;
            }
        """)
        self.comboPeriod.currentIndexChanged.connect(self._period_changed)
        tb_layout.addWidget(self.comboPeriod)

        # 3. Bilgi Etiketi
        self.lblInfo = QLabel("")
        self.lblInfo.setStyleSheet("font-size: 12px; color: #64748b; margin-left: 10px;")
        tb_layout.addWidget(self.lblInfo, 1)

        # 4. Arama Çubuğu
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("🔍 Öğrenci Ara...")
        self.txtSearch.setFixedWidth(200)
        self.txtSearch.setStyleSheet("""
            QLineEdit {
                padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 20px;
                background-color: #f8fafc; color: #334155;
            }
            QLineEdit:focus { border: 1px solid #3b82f6; background-color: white; }
        """)
        self.txtSearch.textChanged.connect(self._filter_rows)
        tb_layout.addWidget(self.txtSearch)

        # 5. Yenile Butonu
        self.btnYenile = QPushButton("Yenile")
        self.btnYenile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnYenile.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; color: white; border: none; font-weight: bold; padding: 6px 15px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btnYenile.clicked.connect(self._yenile)
        tb_layout.addWidget(self.btnYenile)

        root.addWidget(toolbar)

        # İçerik Alanı (Paddingli)
        content_area = QWidget()
        content_box = QVBoxLayout(content_area)
        content_box.setContentsMargins(20, 20, 20, 20)
        
        # --- Boş veri etiketi ---
        self.lblEmpty = QLabel(
            "Henüz görüntülenecek performans özeti oluşmadı. "
            "Ödev girişleri/sonuçları eklendikçe burada görünecek."
        )
        self.lblEmpty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblEmpty.setStyleSheet("color:#9aa0a6; padding:18px; font-size:13px;")
        self.lblEmpty.hide()
        content_box.addWidget(self.lblEmpty)
        
        root.addWidget(content_area)
        
        # Referans tarih (Bugün)
        self.current_ref_date = date.today()

        # --- Sekmeler + tablolar ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 8px; background: white; }
            QTabWidget::tab-bar { left: 10px; }
            QTabBar::tab {
                background: #e2e8f0; color: #64748b; padding: 8px 16px; margin-right: 4px; border-top-left-radius: 6px; border-top-right-radius: 6px;
                font-weight: 600;
            }
            QTabBar::tab:selected { background: white; color: #3b82f6; border-bottom: 2px solid white; }
            QTabBar::tab:hover { background: #f1f5f9; }
        """)
        content_box.addWidget(self.tabs)

        self.tabTop5 = QTableWidget()
        self.tabTrend = QTableWidget()
        self.tabClub = QTableWidget()

        for t in (self.tabTop5, self.tabTrend, self.tabClub):
            self._tune_table_widget(t)

        # Tab 1: Podyum + Tablo
        top5_container = QWidget()
        top5_lay = QVBoxLayout(top5_container)
        top5_lay.setContentsMargins(8, 8, 8, 8)
        top5_lay.setSpacing(10)

        self.podium_box = self._build_podium_ui()
        top5_lay.addWidget(self.podium_box)
        top5_lay.addWidget(self.tabTop5, 1)

        self.tabs.addTab(top5_container, "🏆 Haftanın İlk 5'i (Liderlik)")
        self.tabs.addTab(self._wrap(self.tabTrend), "📈 Gecikme Trendi")
        self.tabs.addTab(self._wrap(self.tabClub), "🌟 %80+ Kulübü")

        self._cached_top5_rows = []
        self._cached_club_rows = []

        # Görsel delegate’ler
        self._enable_visuals()
        self._enable_trend_visuals()

        # Export butonları
        self._add_visual_exports()

        # Şema garantisi (varsa)
        try:
            con = db.get_conn()
            if hasattr(db, "ensure_performance_schema"):
                db.ensure_performance_schema(con)
            con.close()
        except Exception:
            pass

        # Açılışta verileri yükle
        self._yenile()

    # --------- Genel görünüm ayarları ---------

    def _tune_table_widget(self, t: QTableWidget):
        t.setColumnCount(0)
        t.setRowCount(0)
        t.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        t.setWordWrap(False)
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        t.verticalHeader().setVisible(False)

        header = t.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(110)

        t.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #f1f5f9;
                font-size: 13px;
                background-color: white;
                border: none;
                selection-background-color: #eff6ff;
                selection-color: #1e3a8a;
            }
            QHeaderView::section {
                font-weight: 600;
                padding: 10px;
                background: #f8fafc;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                color: #475569;
                text-transform: uppercase;
                font-size: 11px;
            }
            QTableWidget::item { padding: 8px; border-bottom: 1px solid #f1f5f9; }
        """
        )

    def _period_changed(self, idx):
        if idx == 0: # Bu Hafta
            self.current_ref_date = date.today()
        elif idx == 1: # Geçen Hafta
            self.current_ref_date = date.today() - timedelta(days=7)
        self._yenile()

    def _filter_rows(self, text):
        text = text.lower().strip()
        for tab in (self.tabTop5, self.tabTrend, self.tabClub):
            for r in range(tab.rowCount()):
                item = tab.item(r, 0) # 0. indeks her zaman öğrenci adı
                if not item: continue
                match = text in item.text().lower()
                tab.setRowHidden(r, not match)

    def _wrap(self, w: QWidget) -> QWidget:
        box = QVBoxLayout()
        box.setContentsMargins(8, 8, 8, 8)
        cont = QWidget()
        cont.setLayout(box)
        box.addWidget(w)
        return cont

    def _set_empty_message(self, msg: str | None):
        has_msg = bool((msg or "").strip())
        self.lblEmpty.setText(msg or "")
        self.lblEmpty.setVisible(has_msg)
        self.tabs.setVisible(not has_msg)

    # --------- Veri yenile ---------

    # --------- Veri yenile ---------

    def _yenile(self):
        # Ref tarihe göre hafta hesapla
        today = self.current_ref_date
        ws, we = _week_bounds(today)
        l30s, l30e = _last30_bounds(date.today()) # Son 30 gün sabit kalsın veya o da kaysın mı? 
        # Kullanıcı "Tarih Aralığı" dediğinde genelde hepsi kaysın ister ama "Son 30 gün" adı üstünde son 30 gündür.
        # Biz yine de tutarlılık için referans tarihten geriye 30 gün alalım:
        l30s, l30e = _last30_bounds(today)

        self.lblInfo.setText(
            f"Hafta: {ws.isoformat()} – {we.isoformat()}   |   "
            f"Son 30 gün: {l30s.isoformat()} – {l30e.isoformat()}"
        )

        con = db.get_conn()
        try:
            # Eski versiyon yardımcı fonksiyonlar varsa dene ama hata paneli bozmasın
            try:
                if hasattr(db, "rebuild_performance_current_week"):
                    db.rebuild_performance_current_week(con)
                if hasattr(db, "rebuild_performance_last_30_days"):
                    db.rebuild_performance_last_30_days(con)
            except Exception:
                pass

            top5_cnt = self._fill_top5(con, ws, we)
            trend_cnt = self._fill_trend(con, l30s, l30e)
            club_cnt = self._fill_club(con, ws, we, l30s, l30e)
        finally:
            con.close()

        if (top5_cnt + trend_cnt + club_cnt) == 0:
            self._set_empty_message(
                "Henüz görüntülenecek performans özeti oluşmadı. "
                "Ödev girişleri/sonuçları eklendikçe burada görünecek."
            )
        else:
            self._set_empty_message(None)

    # --------- Sekme 1: Haftanın İlk 5’i ---------

    def _fill_top5(self, con, ws: date, we: date) -> int:
        ws_s, we_s = ws.isoformat(), we.isoformat()

        rows = con.execute(
            """
            WITH haftalik AS (
                SELECT
                    op.ogrenci_id,
                    SUM(op.tamam)                        AS gorev_bitti,
                    SUM(op.tamam + op.kismi + op.yapilmadi) AS gorev_toplam
                FROM ogrenci_perf_gunluk op
                WHERE date(op.gun) BETWEEN date(?) AND date(?)
                GROUP BY op.ogrenci_id
            ),
            ks AS (
                SELECT
                    s.ogrenci_id,
                    DATE(COALESCE(s.tarih, k.bitis_tarihi)) AS gun,
                    s.kume_id
                FROM odev_satir s
                LEFT JOIN odev_kume k ON k.id = s.kume_id
                UNION ALL
                SELECT
                    o.ogrenci_id,
                    DATE(k.bitis_tarihi)                    AS gun,
                    o.kume_id
                FROM odev o
                LEFT JOIN odev_kume k ON k.id = o.kume_id
            ),
            kume_hafta AS (
                SELECT
                    ogrenci_id,
                    COUNT(DISTINCT kume_id) AS kume_sayisi
                FROM ks
                WHERE gun IS NOT NULL AND date(gun) BETWEEN date(?) AND date(?)
                GROUP BY ogrenci_id
            )
            SELECT
                o.id AS ogrenci_id,
                o.ad, o.soyad,
                h.gorev_bitti,
                h.gorev_toplam,
                COALESCE(k.kume_sayisi, 0) AS kume_sayisi,
                CASE
                    WHEN COALESCE(h.gorev_toplam,0) = 0 THEN 0
                    ELSE ROUND(100.0 * COALESCE(h.gorev_bitti,0) / h.gorev_toplam)
                END AS ilerleme_yuzde
            FROM ogrenci o
            LEFT JOIN haftalik   h ON h.ogrenci_id = o.id
            LEFT JOIN kume_hafta k ON k.ogrenci_id = o.id
            WHERE COALESCE(h.gorev_toplam,0) > 0
            ORDER BY ilerleme_yuzde DESC, h.gorev_bitti DESC
            LIMIT 5
            """,
            (ws_s, we_s, ws_s, we_s),
        ).fetchall()

        headers = ["Öğrenci", "İlerleme %", "Biten Görev", "Toplam Görev", "Küme Sayısı"]
        self.tabTop5.setColumnCount(len(headers))
        self.tabTop5.setHorizontalHeaderLabels(headers)
        self.tabTop5.setRowCount(len(rows))

        for i, r in enumerate(rows):
            adsoyad = f"{(r['ad'] or '').strip()} {(r['soyad'] or '').strip()}".strip()
            vals = [
                adsoyad,
                str(int(r["ilerleme_yuzde"] or 0)),
                str(int(r["gorev_bitti"] or 0)),
                str(int(r["gorev_toplam"] or 0)),
                str(int(r["kume_sayisi"] or 0)),
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                     it.setData(Qt.ItemDataRole.UserRole, r["ogrenci_id"])
                self.tabTop5.setItem(i, j, it)

        self._cached_top5_rows = rows
        self._update_podium(rows)
        self.tabTop5.resizeColumnsToContents()
        return len(rows)

    # --------- Sekme 2: Gecikme Trendi ---------

    def _fill_trend(self, con, l30s: date, l30e: date) -> int:
        a_s, a_e = l30s.isoformat(), l30e.isoformat()
        prev_end = l30s - timedelta(days=1)
        prev_start = prev_end - timedelta(days=29)
        b_s, b_e = prev_start.isoformat(), prev_end.isoformat()

        rows = con.execute(
            """
            WITH a AS (
                SELECT ogrenci_id, SUM(geciken) AS gecikme_a
                FROM ogrenci_perf_gunluk
                WHERE date(gun) BETWEEN date(?) AND date(?)
                GROUP BY ogrenci_id
            ),
            b AS (
                SELECT ogrenci_id, SUM(geciken) AS gecikme_b
                FROM ogrenci_perf_gunluk
                WHERE date(gun) BETWEEN date(?) AND date(?)
                GROUP BY ogrenci_id
            )
            SELECT
                o.id AS ogrenci_id, o.ad, o.soyad,
                COALESCE(a.gecikme_a,0) AS son30,
                COALESCE(b.gecikme_b,0) AS onceki30,
                (COALESCE(a.gecikme_a,0) - COALESCE(b.gecikme_b,0)) AS fark
            FROM ogrenci o
            LEFT JOIN a ON a.ogrenci_id = o.id
            LEFT JOIN b ON b.ogrenci_id = o.id
            WHERE COALESCE(a.gecikme_a,0) > COALESCE(b.gecikme_b,0)
            ORDER BY fark DESC, son30 DESC
            LIMIT 20
            """,
            (a_s, a_e, b_s, b_e),
        ).fetchall()

        headers = ["Öğrenci", "Son 30 Gün Gecikme", "Önceki 30 Gün Gecikme", "Artış"]
        self.tabTrend.setColumnCount(len(headers))
        self.tabTrend.setHorizontalHeaderLabels(headers)
        self.tabTrend.setRowCount(len(rows))

        for i, r in enumerate(rows):
            adsoyad = f"{(r['ad'] or '').strip()} {(r['soyad'] or '').strip()}".strip()
            vals = [
                adsoyad,
                str(int(r["son30"] or 0)),
                str(int(r["onceki30"] or 0)),
                str(int(r["fark"] or 0)),
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r["ogrenci_id"])
                self.tabTrend.setItem(i, j, it)

        self.tabTrend.resizeColumnsToContents()
        return len(rows)

    # --------- Sekme 3: %80+ Kulübü ---------

    def _fill_club(self, con, ws: date, we: date, l30s: date, l30e: date) -> int:
        """
        %80+ Kulübü (Hafta + Son 30 Gün)
        - Haftalık ve son 30 gün tamamlama yüzdeleri
        - Değişim (hafta - 30 gün)
        - Hafta / 30 gün bitti/toplam adetleri
        - Rozet: 80–89, 90–94, 95+ için seviye
        """
        ws_s, we_s = ws.isoformat(), we.isoformat()
        l30s_s, l30e_s = l30s.isoformat(), l30e.isoformat()

        rows = con.execute(
            """
            WITH w AS (
                SELECT
                    op.ogrenci_id,
                    SUM(op.tamam)                                   AS bitti_w,
                    SUM(op.tamam + op.kismi + op.yapilmadi)         AS toplam_w
                FROM ogrenci_perf_gunluk op
                WHERE date(op.gun) BETWEEN date(?) AND date(?)
                GROUP BY op.ogrenci_id
            ),
            w_pct AS (
                SELECT
                    ogrenci_id,
                    bitti_w,
                    toplam_w,
                    CASE
                        WHEN toplam_w > 0
                            THEN ROUND(100.0 * bitti_w / toplam_w, 1)
                        ELSE 0
                    END AS w_pct
                FROM w
            ),
            m AS (
                SELECT
                    op.ogrenci_id,
                    SUM(op.tamam)                                   AS bitti_m,
                    SUM(op.tamam + op.kismi + op.yapilmadi)         AS toplam_m
                FROM ogrenci_perf_gunluk op
                WHERE date(op.gun) BETWEEN date(?) AND date(?)
                GROUP BY op.ogrenci_id
            ),
            m_pct AS (
                SELECT
                    ogrenci_id,
                    bitti_m,
                    toplam_m,
                    CASE
                        WHEN toplam_m > 0
                            THEN ROUND(100.0 * bitti_m / toplam_m, 1)
                        ELSE 0
                    END AS m_pct
                FROM m
            )
            SELECT
                o.id AS ogrenci_id,
                o.ad,
                o.soyad,
                COALESCE(wp.w_pct, 0)                     AS hafta_pct,
                COALESCE(mp.m_pct, 0)                     AS ay_pct,
                COALESCE(wp.bitti_w, 0)                   AS hafta_bitti,
                COALESCE(wp.toplam_w, 0)                  AS hafta_toplam,
                COALESCE(mp.bitti_m, 0)                   AS ay_bitti,
                COALESCE(mp.toplam_m, 0)                  AS ay_toplam
            FROM ogrenci o
            LEFT JOIN w_pct  wp ON wp.ogrenci_id = o.id
            LEFT JOIN m_pct  mp ON mp.ogrenci_id = o.id
            WHERE COALESCE(wp.w_pct, 0) >= 80
               OR COALESCE(mp.m_pct, 0) >= 80
            ORDER BY
                CASE
                    WHEN COALESCE(wp.w_pct,0) >= COALESCE(mp.m_pct,0)
                        THEN COALESCE(wp.w_pct,0)
                    ELSE COALESCE(mp.m_pct,0)
                END DESC
            LIMIT 50
            """,
            (ws_s, we_s, l30s_s, l30e_s),
        ).fetchall()

        # ------------ Tablo iskeleti ------------
        from PyQt6.QtWidgets import QTableWidgetItem, QStyledItemDelegate
        from PyQt6.QtGui import QColor, QBrush, QFont
        from PyQt6.QtCore import Qt, QRect

        self.tabClub.clear()
        self.tabClub.setRowCount(0)

        headers = [
            "Öğrenci",
            "Haftalık %",
            "30 Gün %",
            "Değişim",
            "Hafta (B/T)",
            "30 Gün (B/T)",
            "Rozet",
        ]
        self.tabClub.setColumnCount(len(headers))
        self.tabClub.setHorizontalHeaderLabels(headers)

        def _make_item(text, center=False, bold=False, user_data=None):
            it = QTableWidgetItem(str(text))
            if user_data is not None:
                it.setData(Qt.ItemDataRole.UserRole, user_data)
            if center:
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if bold:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            return it

        def _rozet_for(hafta_pct: float, ay_pct: float) -> str:
            en_yuksek = max(hafta_pct, ay_pct)
            if en_yuksek >= 95:
                return "🥇 Şampiyon"
            if en_yuksek >= 90:
                return "🥈 Altın Kulüp"
            if en_yuksek >= 85:
                return "🥉 Gümüş Kulüp"
            return "⭐ %80 Kulübü"

        # ------------ Satırları doldur ------------
        for r, row in enumerate(rows):
            self.tabClub.insertRow(r)

            adsoyad = f"{(row['ad'] or '').strip()} {(row['soyad'] or '').strip()}".strip()
            hafta_pct = float(row["hafta_pct"] or 0.0)
            ay_pct = float(row["ay_pct"] or 0.0)
            diff = hafta_pct - ay_pct

            hafta_bitti = int(row["hafta_bitti"] or 0)
            hafta_top = int(row["hafta_toplam"] or 0)
            ay_bitti = int(row["ay_bitti"] or 0)
            ay_top = int(row["ay_toplam"] or 0)

            self.tabClub.setItem(r, 0, _make_item(adsoyad, bold=True, user_data=row["ogrenci_id"]))
            self.tabClub.setItem(r, 1, _make_item(f"{hafta_pct:.1f}%", center=True))
            self.tabClub.setItem(r, 2, _make_item(f"{ay_pct:.1f}%", center=True))

            sign = "+" if diff >= 0 else ""
            self.tabClub.setItem(r, 3, _make_item(f"{sign}{diff:.1f} p", center=True))

            self.tabClub.setItem(r, 4, _make_item(f"{hafta_bitti}/{hafta_top}", center=True))
            self.tabClub.setItem(r, 5, _make_item(f"{ay_bitti}/{ay_top}", center=True))
            self.tabClub.setItem(
                r, 6,
                _make_item(_rozet_for(hafta_pct, ay_pct), center=True, bold=True),
            )

        # Satır yüksekliği ve başlık ayarları
        for r in range(self.tabClub.rowCount()):
            self.tabClub.setRowHeight(r, 26)

        h = self.tabClub.horizontalHeader()
        h.setStretchLastSection(True)
        h.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        # ------------ Yüzdeler için renkli bar delegate ------------
        class _PctDelegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                col = index.column()
                if col not in (1, 2, 3):
                    return super().paint(painter, option, index)

                txt = index.data() or ""
                try:
                    if col in (1, 2):
                        # "%": 0–100 → 0–1
                        val = float(txt.replace("%", "").replace(",", "."))
                        ratio = max(0.0, min(val / 100.0, 1.0))
                    else:
                        # Değişim: -20 .. +20 → 0..1
                        num = float(
                            txt.replace("p", "")
                               .replace("+", "")
                               .replace(",", ".")
                        )
                        ratio = max(0.0, min((num + 20.0) / 40.0, 1.0))
                except Exception:
                    return super().paint(painter, option, index)

                painter.save()
                rect = option.rect.adjusted(4, 6, -4, -6)

                # Renk seçimi
                if col == 3:
                    # Değişim
                    num = float(
                        txt.replace("p", "")
                           .replace("+", "")
                           .replace(",", ".") or 0
                    )
                    if num >= 5:
                        color = QColor("#16a34a")   # güçlü artış
                    elif num >= 0:
                        color = QColor("#4ade80")   # hafif artış
                    elif num <= -5:
                        color = QColor("#ef4444")   # güçlü düşüş
                    else:
                        color = QColor("#f97316")   # hafif düşüş
                else:
                    # % sütunları
                    val = float(txt.replace("%", "").replace(",", ".") or 0)
                    if val >= 95:
                        color = QColor("#16a34a")
                    elif val >= 90:
                        color = QColor("#22c55e")
                    elif val >= 85:
                        color = QColor("#84cc16")
                    else:
                        color = QColor("#fbbf24")

                painter.setRenderHint(painter.RenderHint.Antialiasing, True)
                painter.setPen(Qt.PenStyle.NoPen)
                fill = QRect(rect.x(), rect.y(), int(rect.width() * ratio), rect.height())
                painter.setBrush(QBrush(color))
                painter.drawRoundedRect(fill, 6, 6)

                painter.setPen(Qt.GlobalColor.white)
                f = QFont(option.font)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)
                painter.restore()

        # Yüzde + değişim sütunları için renkli bar delegate
        class _PctDelegate(QStyledItemDelegate):
            def _text_color_for_bg(self, color: QColor) -> QColor:
                """
                Arka plan rengine göre otomatik yazı rengi:
                - Koyu yeşil / kırmızı tonlarda beyaz
                - Açık sarı / açık yeşil tonlarda koyu gri
                """
                r, g, b = color.red(), color.green(), color.blue()
                # basit parlaklık hesabı (0–255)
                brightness = (r * 299 + g * 587 + b * 114) / 1000.0
                if brightness < 140:
                    # koyu arka plan → açık yazı
                    return QColor("#F9FAFB")  # neredeyse beyaz
                else:
                    # açık arka plan → koyu yazı
                    return QColor("#111827")  # koyu gri (siyah yerine daha yumuşak)

            def paint(self, painter, option, index):
                col = index.column()
                if col not in (1, 2, 3):
                    return super().paint(painter, option, index)

                txt = index.data() or ""
                try:
                    if col in (1, 2):  # "%"
                        val = float(str(txt).replace("%", "").replace(",", "."))
                        ratio = max(0.0, min(val / 100.0, 1.0))
                    else:
                        # "Değişim": -20 .. +20 aralığını 0..1'e sıkıştır
                        num = float(
                            str(txt)
                            .replace("p", "")
                            .replace("+", "")
                            .replace(",", ".")
                        )
                        ratio = max(0.0, min((num + 20.0) / 40.0, 1.0))
                except Exception:
                    return super().paint(painter, option, index)

                painter.save()
                rect = option.rect.adjusted(4, 6, -4, -6)

                # --- Renk seçimi ---
                if col == 3:  # Değişim sütunu
                    num = float(
                        str(txt)
                        .replace("p", "")
                        .replace("+", "")
                        .replace(",", ".") or 0
                    )
                    if num >= 5:
                        color = QColor("#16a34a")  # güçlü artış
                    elif num >= 0:
                        color = QColor("#4ade80")  # hafif artış
                    elif num <= -5:
                        color = QColor("#ef4444")  # güçlü düşüş
                    else:
                        color = QColor("#f97316")  # hafif düşüş
                else:
                    # % sütunları: 80+ yeşil tonları
                    val = float(str(txt).replace("%", "").replace(",", ".") or 0)
                    if val >= 95:
                        color = QColor("#16a34a")
                    elif val >= 90:
                        color = QColor("#22c55e")
                    elif val >= 85:
                        color = QColor("#84cc16")
                    else:
                        color = QColor("#fbbf24")

                # --- Bar çizimi ---
                painter.setRenderHint(painter.RenderHint.Antialiasing, True)
                painter.setPen(Qt.PenStyle.NoPen)
                fill = QRect(rect.x(), rect.y(), int(rect.width() * ratio), rect.height())
                painter.setBrush(QBrush(color))
                painter.drawRoundedRect(fill, 6, 6)

                # --- Metin (kontrastlı) ---
                text_color = self._text_color_for_bg(color)
                painter.setPen(text_color)
                f = QFont(option.font)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)

                painter.restore()

        delegate = _PctDelegate(self.tabClub)
        self.tabClub.setItemDelegateForColumn(1, delegate)
        self.tabClub.setItemDelegateForColumn(2, delegate)
        self.tabClub.setItemDelegateForColumn(3, delegate)

        self._cached_club_rows = rows
        return len(rows)




    # --------- Görsel delegate’ler ---------

    def _enable_visuals(self):
        class _PercentBarDelegate(QStyledItemDelegate):
            def __init__(self, pct_cols):
                super().__init__()
                self._pct_cols = set(pct_cols)

            def paint(self, painter, option, index):
                if index.column() not in self._pct_cols:
                    return super().paint(painter, option, index)

                try:
                    raw = str(index.data() or "").replace("%", "").strip()
                    pct = max(0, min(100, int(float(raw))))
                except Exception:
                    pct = 0

                painter.save()
                painter.fillRect(option.rect, QColor(248, 250, 252))

                r = option.rect.adjusted(6, 6, -6, -6)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(230, 236, 242))
                painter.drawRoundedRect(r, 6, 6)

                def _mix(c1, c2, t_):
                    return QColor(
                        int(c1.red() + (c2.red() - c1.red()) * t_),
                        int(c1.green() + (c2.green() - c1.green()) * t_),
                        int(c1.blue() + (c2.blue() - c1.blue()) * t_),
                    )

                t_ = pct / 100.0
                fill = _mix(QColor("#ef4444"), QColor("#22c55e"), t_)
                bar = QRect(r.x(), r.y(), int(r.width() * t_), r.height())
                painter.setBrush(fill)
                painter.drawRoundedRect(bar, 6, 6)

                if pct >= 90:
                    msg = "🔥 Süper!"
                elif pct >= 75:
                    msg = "💪 Harika"
                elif pct >= 50:
                    msg = "🙂 İyi"
                elif pct >= 30:
                    msg = "⚡ Başlayalım"
                else:
                    msg = "🚀 İlk adım"

                txt = f"{pct}%  •  {msg}"
                f = QFont(option.font)
                f.setBold(True)
                painter.setFont(f)
                painter.setPen(QColor(30, 41, 59))
                painter.drawText(r, Qt.AlignmentFlag.AlignCenter, txt)
                painter.restore()

            def sizeHint(self, option, index):
                s = super().sizeHint(option, index)
                if index.column() in self._pct_cols:
                    s.setHeight(max(s.height(), 28))
                return s

        for table in (self.tabTop5, self.tabTrend, self.tabClub):
            h = table.horizontalHeader()
            h.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            h.setStretchLastSection(True)
            h.setMinimumSectionSize(140)

        self.tabTop5.setItemDelegate(_PercentBarDelegate({1}))
        self.tabClub.setItemDelegate(_PercentBarDelegate({1, 2}))

    def _enable_trend_visuals(self):
        class _TrendDelegate(QStyledItemDelegate):
            def paint(self, painter, option, index):
                if index.column() != 3:
                    return super().paint(painter, option, index)

                try:
                    diff = int(index.data() or 0)
                except Exception:
                    diff = 0

                painter.save()
                r = option.rect.adjusted(6, 6, -6, -6)

                if diff >= 3:
                    color = QColor("#ef4444")
                    msg = "⚠️ Dikkat! Gecikme artıyor"
                elif diff == 2:
                    color = QColor("#f59e0b")
                    msg = "⏳ Küçük artış"
                elif diff == 1:
                    msg = "💪 Daha iyi gidiyorsun"
                    color = QColor("#84cc16")
                else:
                    msg = "✅ Süper istikrar"
                    color = QColor("#22c55e")

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                fill = QRect(r.x(), r.y(), int(r.width() * min(abs(diff) / 5, 1.0)), r.height())
                painter.drawRoundedRect(fill, 5, 5)

                painter.setPen(QColor(255, 255, 255))
                f = QFont(option.font)
                f.setBold(True)
                painter.setFont(f)
                painter.drawText(r, Qt.AlignmentFlag.AlignCenter, f"{diff} → {msg}")
                painter.restore()

            def sizeHint(self, option, index):
                s = super().sizeHint(option, index)
                if index.column() == 3:
                    s.setHeight(max(s.height(), 26))
                return s

        self.tabTrend.setItemDelegate(_TrendDelegate())

    # --------- PDF / Excel / Yazdır (görsel) ---------

    # ---------- PDF / Excel / Yazdır (Görsel) Helper Methods ----------

    def _header_height(self, tv):
        h = tv.horizontalHeader()
        try:
            return h.height()
        except Exception:
            return 28

    def _content_size_for_table(self, table):
        w = 0
        for c in range(table.model().columnCount()):
            w += table.columnWidth(c)
        w += 2
        h = self._header_height(table)
        for r in range(table.model().rowCount()):
            h += table.rowHeight(r)
        h += 2
        return QSize(max(1, w), max(1, h))

    def _clone_view_for_print(self, src):
        view = QTableView()
        view.setModel(src.model())
        view.setAlternatingRowColors(src.alternatingRowColors())
        view.setWordWrap(src.wordWrap())
        view.setSelectionBehavior(src.selectionBehavior())
        view.setSelectionMode(src.selectionMode())
        view.verticalHeader().setVisible(False)
        view.horizontalHeader().setVisible(True)
        view.horizontalHeader().setStretchLastSection(src.horizontalHeader().stretchLastSection())
        try:
            mode = src.horizontalHeader().sectionResizeMode(0)
            for c in range(src.model().columnCount()):
                view.horizontalHeader().setSectionResizeMode(c, mode)
        except Exception:
            pass
        for c in range(src.model().columnCount()):
            view.setColumnWidth(c, src.columnWidth(c))
        for r in range(src.model().rowCount()):
            view.setRowHeight(r, src.rowHeight(r))
        for c in range(src.model().columnCount()):
            d = src.itemDelegateForColumn(c)
            if d is not None:
                view.setItemDelegateForColumn(c, d)
        size = self._content_size_for_table(src)
        view.resize(size)
        view.setMinimumSize(size)
        view.setMaximumSize(size)
        view.setFixedSize(size)
        return view

    def render_table_full_to_image(self, table, scale=2.0):
        printable = self._clone_view_for_print(table)
        size = printable.size()
        W = max(1, int(size.width() * scale))
        H = max(1, int(size.height() * scale))
        img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(scale)
        img.fill(0)
        p = QPainter(img)
        printable.render(p)
        p.end()
        return img

    def _render_table_full_png(self, table, path, scale=2.0):
        view = table
        app = QApplication.instance()
        h_head = view.horizontalHeader().height()
        v_len = view.verticalHeader().length()
        fw = view.frameWidth() * 2
        total_h = h_head + v_len + fw + 6
        total_w = view.horizontalHeader().length() + view.verticalHeader().width() + fw
        old_size = view.size()
        view.resize(total_w, total_h)
        view.doItemsLayout()
        if app: app.processEvents()
        w = max(1, int(total_w * scale))
        h = max(1, int(total_h * scale))
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(scale)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        view.horizontalHeader().render(p, QPoint(0, 0))
        view.viewport().render(p, QPoint(0, h_head))
        p.end()
        img.save(path, "PNG")
        view.resize(old_size)
        view.doItemsLayout()
        if app: app.processEvents()

    def grab_all_tabs_images(self, scale=2.0):
        mapping = [
            ("Haftanın İlk 5'i", self.tabTop5),
            ("Gecikme Trendi", self.tabTrend),
            ("%80+ Kulübü", self.tabClub),
        ]
        out = []
        for name, tab in mapping:
            img = self.render_table_full_to_image(tab, scale=scale)
            out.append((name, img))
        return out

    def _draw_page_header(self, painter, rect, title, sub_info):
        f_title = QFont("Segoe UI", 16, QFont.Weight.Bold)
        painter.setFont(f_title)
        painter.setPen(QColor("#1e293b"))
        header_top = rect.y() + 20
        header_h_box = 60
        header_rect = QRect(rect.x(), header_top, rect.width(), header_h_box)
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, title.upper())
        f_sub = QFont("Segoe UI", 11)
        painter.setFont(f_sub)
        painter.setPen(QColor("#64748b"))
        sub_top = header_top + header_h_box + 10 
        sub_rect = QRect(rect.x(), sub_top, rect.width(), 30)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, sub_info)
        painter.setPen(QPen(QColor("#cbd5e1"), 2))
        line_y = sub_top + 40
        painter.drawLine(rect.x(), line_y, rect.right(), line_y)
        return (line_y - rect.y()) + 20

    def _draw_page_footer(self, painter, rect, page_num, total_pages):
        f_foot = QFont("Segoe UI", 9)
        painter.setFont(f_foot)
        painter.setPen(QColor("#94a3b8"))
        footer_h = 50
        foot_rect = QRect(rect.x(), rect.bottom() - footer_h, rect.width(), 40)
        pg_str = f"{page_num}"
        if total_pages: pg_str += f" / {total_pages}"
        txt = f"Öğrenci Performans Sistemi  •  {date.today().strftime('%d.%m.%Y')}  •  Sayfa {pg_str}"
        painter.drawText(foot_rect, Qt.AlignmentFlag.AlignCenter, txt)
        return footer_h

    def _paint_image_on_pages(self, painter, writer_or_printer, img_list, report_title):
        page_layout = writer_or_printer.pageLayout()
        page_rect = page_layout.paintRectPixels(writer_or_printer.resolution())
        try:
            ws, we = _week_bounds(self.current_ref_date)
            dt_info = f"Dönem: {ws.strftime('%d.%m.%Y')} - {we.strftime('%d.%m.%Y')}"
        except:
            dt_info = f"Tarih: {date.today().strftime('%d.%m.%Y')}"
        total_sections = len(img_list)
        for idx, (sect_name, img) in enumerate(img_list):
            if img.isNull(): continue
            y_src = 0
            page_idx = 1
            while y_src < img.height():
                header_h = self._draw_page_header(painter, page_rect, f"{report_title} – {sect_name}", dt_info)
                footer_h = self._draw_page_footer(painter, page_rect, page_idx, "")
                content_top = page_rect.y() + header_h
                avail_h = page_rect.height() - header_h - footer_h - 10
                avail_w = page_rect.width()
                scale_w = avail_w / img.width()
                slice_h_src = int(avail_h / scale_w)
                if slice_h_src <= 0: slice_h_src = 100
                src_h = min(slice_h_src, img.height() - y_src)
                dst_rect = QRect(page_rect.x(), content_top, avail_w, int(src_h * scale_w))
                src_rect = QRect(0, y_src, img.width(), src_h)
                painter.drawImage(dst_rect, img, src_rect)
                y_src += src_h
                page_idx += 1
                if y_src < img.height():
                    writer_or_printer.newPage()
            if idx < total_sections - 1:
                writer_or_printer.newPage()

    def export_pdf_visual(self):
        file, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", "", "PDF (*.pdf)")
        if not file: return
        progress = QProgressDialog("Rapor hazırlanıyor, lütfen bekleyin...", "İptal", 0, 100, self)
        progress.setWindowTitle("PDF Oluşturuluyor")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(10)
        QApplication.processEvents()
        try:
            tmpdir = tempfile.mkdtemp(prefix="perfpanel_full_")
            tab_map = [("Haftanın İlk 5'i", self.tabTop5), ("Gecikme Trendi", self.tabTrend), ("%80+ Kulübü", self.tabClub)]
            SCALE = 3.0
            images = []
            step_val = 10
            step_inc = 40 / len(tab_map)
            for name, table in tab_map:
                if progress.wasCanceled(): return
                progress.setLabelText(f"Tablo işleniyor: {name}...")
                png_path = os.path.join(tmpdir, f"{name.replace(' ', '_')}.png")
                self._render_table_full_png(table, png_path, scale=SCALE)
                img = QImage(png_path)
                images.append((name, img))
                step_val += step_inc
                progress.setValue(int(step_val))
                QApplication.processEvents()
            progress.setLabelText("PDF dosyası oluşturuluyor...")
            writer = QPdfWriter(file)
            writer.setCreator("Performans Takip Sistemi")
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setResolution(300)
            layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(10, 10, 10, 10))
            writer.setPageLayout(layout)
            painter = QPainter(writer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            progress.setValue(60)
            self._paint_image_on_pages(painter, writer, images, "PERFORMANS RAPORU")
            painter.end()
            progress.setValue(100)
            QMessageBox.information(self, "İşlem Tamamlandı", f"Rapor başarıyla kaydedildi:\n\n📂 {file}\n\nProfesyonel formatta PDF oluşturuldu.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PDF oluşturulurken bir hata oluştu:\n{str(e)}")
        finally:
            progress.close()

    def print_visual(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        dlg = QPrintDialog(printer, self)
        if not dlg.exec(): return
        progress = QProgressDialog("Yazdırılıyor...", "İptal", 0, 100, self)
        progress.setWindowTitle("Yazdırma İşlemi")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        try:
            progress.setValue(20)
            current = self.tabs.currentWidget().findChild(type(self.tabTop5))
            if not current: current = self.tabs.currentWidget()
            progress.setLabelText("Görüntü oluşturuluyor...")
            SCALE = 3.0
            img = self.render_table_full_to_image(current, scale=SCALE)
            title = self.tabs.tabText(self.tabs.currentIndex())
            progress.setValue(50)
            progress.setLabelText("Yazıcıya gönderiliyor...")
            painter = QPainter(printer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            self._paint_image_on_pages(painter, printer, [(title, img)], "PERFORMANS RAPORU")
            painter.end()
            progress.setValue(100)
            QMessageBox.information(self, "Yazdırıldı", "Belge başarıyla yazıcı kuyruğuna gönderildi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yazdırma sırasında hata:\n{str(e)}")
        finally:
            progress.close()

    def export_excel_visual(self):
        file, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "", "Excel (*.xlsx)")
        if not file: return
        progress = QProgressDialog("Excel'e aktarılıyor...", "İptal", 0, 100, self)
        progress.setWindowTitle("Excel Export")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        try:
            progress.setValue(10)
            images = self.grab_all_tabs_images(scale=2.0)
            progress.setValue(40)
            wb = xlsxwriter.Workbook(file)
            ws_vis = wb.add_worksheet("Panolar")
            row = 0
            total_imgs = len(images)
            for i, (name, img) in enumerate(images):
                if progress.wasCanceled(): 
                    wb.close()
                    return
                progress.setLabelText(f"Sayfaya ekleniyor: {name}")
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                img.save(tmp.name, "PNG")
                ws_vis.write(row, 0, name)
                ws_vis.insert_image(row+1, 0, tmp.name, {'x_scale': 0.8, 'y_scale': 0.8})
                row += 50 
                step = 40 + int((i+1)/total_imgs * 50)
                progress.setValue(step)
                QApplication.processEvents()
            wb.close()
            progress.setValue(100)
            QMessageBox.information(self, "Başarılı", f"Excel dosyası oluşturuldu:\n\n📂 {file}\n\nTüm panolar görsel olarak eklendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel hatası:\n{str(e)}")
        finally:
            progress.close()

    def export_web_portal(self):
        # Aktif öğrenciyi bul
        current_idx = self.tabs.currentIndex()
        table = None
        if current_idx == 0: table = self.tabTop5
        elif current_idx == 1: table = self.tabTrend
        elif current_idx == 2: table = self.tabClub
        
        sid, name = None, None
        if table:
            row = table.currentRow()
            if row >= 0:
                item = table.item(row, 0)
                if item:
                    sid = item.data(Qt.ItemDataRole.UserRole)
                    name = item.text()
        
        if not sid:
            QMessageBox.warning(self, "Öğrenci Seçilmedi", "Lütfen tablodan bir öğrenci seçin.")
            return

        default_name = f"{name.replace(' ', '_')}_Portal.html"
        file, _ = QFileDialog.getSaveFileName(self, "Web Portalı Kaydet", default_name, "HTML (*.html)")
        if not file: return

        try:
            gen = WebPortalGenerator(int(sid), name)
            gen.generate(file)
            QMessageBox.information(self, "Başarılı", f"Web portalı oluşturuldu:\n\n📂 {file}\n\nTarayıcıda açarak inceleyebilirsiniz.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Portal oluşturulurken hata:\n{str(e)}")

    def _add_visual_exports(self):
        """Alt kısma PDF ve Yazdır butonlarını ekler (Modern Görünüm)."""
        def open_analytics():
            current_idx = self.tabs.currentIndex()
            table = None
            if current_idx == 0: table = self.tabTop5
            elif current_idx == 1: table = self.tabTrend
            elif current_idx == 2: table = self.tabClub
            if not table: return
            row = table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Öğrenci Seçilmedi", "Lütfen analiz için tablodan bir öğrenci seçin.")
                return
            item = table.item(row, 0)
            if not item: return
            sid = item.data(Qt.ItemDataRole.UserRole)
            name = item.text()
            if not sid:
                QMessageBox.warning(self, "Hata", "Öğrenci ID'si bulunamadı (UserRole eksik).")
                return
            dlg = AnalyticsDialog(self, student_id=int(sid), student_name=name)
            dlg.exec()

        btn_frame = QFrame()
        btn_frame.setStyleSheet("""
            QFrame { background-color: #ffffff; border-top: 1px solid #e2e8f0; }
            QPushButton { background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; color: #334155; font-family: 'Segoe UI'; font-weight: 600; font-size: 13px; padding: 8px 16px; }
            QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; color: #0f172a; }
            QPushButton:pressed { background-color: #e2e8f0; }
        """)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(10, 8, 10, 8)
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_board_poster = QPushButton("📌 Panoya Asmak İçin A4 Pano Posteri (PDF)")
        btn_board_poster.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_board_poster.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #2563eb);
                color: white; font-weight: 800; border-radius: 6px; padding: 8px 16px; border: none; font-size: 12px;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_board_poster.clicked.connect(self.export_board_poster_pdf)
        btn_layout.addWidget(btn_board_poster)

        btn_analytics = QPushButton("📊 Detaylı Analiz")
        btn_analytics.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_analytics.clicked.connect(open_analytics)
        btn_layout.addWidget(btn_analytics)

        # Web Portal
        btn_web = QPushButton("🌐 Web Portalı")
        btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_web.clicked.connect(self.export_web_portal)
        btn_layout.addWidget(btn_web)

        btn_pdf = QPushButton("PDF Olarak Kaydet")
        btn_pdf.setIcon(QIcon.fromTheme("application-pdf"))
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.clicked.connect(self.export_pdf_visual)
        
        btn_excel = QPushButton("Excel'e Aktar")
        btn_excel.setIcon(QIcon.fromTheme("x-office-spreadsheet"))
        btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_excel.clicked.connect(self.export_excel_visual)

        btn_print = QPushButton("Yazdır")
        btn_print.setIcon(QIcon.fromTheme("document-print"))
        btn_print.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_print.setStyleSheet("background-color: #3b82f6; color: white; border: none;")
        btn_print.clicked.connect(self.print_visual)

        btn_layout.addWidget(btn_pdf)
        btn_layout.addWidget(btn_excel)
        btn_layout.addWidget(btn_print)

        self.layout().addWidget(btn_frame)

    def _build_podium_ui(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("PodiumFrame")
        frame.setStyleSheet("""
            QFrame#PodiumFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8fafc, stop:1 #f1f5f9);
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 10px;
            }
        """)
        h_lay = QHBoxLayout(frame)
        h_lay.setSpacing(14)
        h_lay.setContentsMargins(12, 10, 12, 10)

        def make_podium_card(rank_ico, rank_title, border_col, bg_col):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_col};
                    border: 2px solid {border_col};
                    border-radius: 10px;
                }}
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(10, 8, 10, 8)
            c_lay.setSpacing(3)
            c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_ico = QLabel(rank_ico)
            lbl_ico.setStyleSheet("font-size: 24px;")
            lbl_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_title = QLabel(rank_title)
            lbl_title.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {border_col};")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_name = QLabel("—")
            lbl_name.setStyleSheet("font-size: 13px; font-weight: 800; color: #0f172a;")
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_score = QLabel("Tamamlama: %0")
            lbl_score.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            lbl_score.setAlignment(Qt.AlignmentFlag.AlignCenter)

            c_lay.addWidget(lbl_ico)
            c_lay.addWidget(lbl_title)
            c_lay.addWidget(lbl_name)
            c_lay.addWidget(lbl_score)
            return card, lbl_name, lbl_score

        # 2nd Place (Silver)
        self.podium_card2, self.lbl_podium_name2, self.lbl_podium_score2 = make_podium_card(
            "🥈", "2. SIRA (GÜMÜŞ)", "#94a3b8", "#ffffff"
        )
        # 1st Place (Gold - Elevated)
        self.podium_card1, self.lbl_podium_name1, self.lbl_podium_score1 = make_podium_card(
            "👑 🥇", "1. SIRA (ALTIN ŞAMPİYON)", "#f59e0b", "#fffbeb"
        )
        # 3rd Place (Bronze)
        self.podium_card3, self.lbl_podium_name3, self.lbl_podium_score3 = make_podium_card(
            "🥉", "3. SIRA (BRONZ)", "#d97706", "#ffffff"
        )

        h_lay.addWidget(self.podium_card2, 1)
        h_lay.addWidget(self.podium_card1, 1)
        h_lay.addWidget(self.podium_card3, 1)
        return frame

    def _update_podium(self, rows):
        if len(rows) > 0:
            r1 = rows[0]
            name1 = f"{(r1['ad'] or '').strip()} {(r1['soyad'] or '').strip()}".strip()
            self.lbl_podium_name1.setText(name1)
            self.lbl_podium_score1.setText(f"Tamamlama: %{int(r1['ilerleme_yuzde'] or 0)} ({r1['gorev_bitti']}/{r1['gorev_toplam']} Ödev)")
        else:
            self.lbl_podium_name1.setText("—")
            self.lbl_podium_score1.setText("Tamamlama: %0")

        if len(rows) > 1:
            r2 = rows[1]
            name2 = f"{(r2['ad'] or '').strip()} {(r2['soyad'] or '').strip()}".strip()
            self.lbl_podium_name2.setText(name2)
            self.lbl_podium_score2.setText(f"Tamamlama: %{int(r2['ilerleme_yuzde'] or 0)}")
        else:
            self.lbl_podium_name2.setText("—")
            self.lbl_podium_score2.setText("Tamamlama: %0")

        if len(rows) > 2:
            r3 = rows[2]
            name3 = f"{(r3['ad'] or '').strip()} {(r3['soyad'] or '').strip()}".strip()
            self.lbl_podium_name3.setText(name3)
            self.lbl_podium_score3.setText(f"Tamamlama: %{int(r3['ilerleme_yuzde'] or 0)}")
        else:
            self.lbl_podium_name3.setText("—")
            self.lbl_podium_score3.setText("Tamamlama: %0")

    def export_board_poster_pdf(self):
        """Kullanıcının panoya asabileceği, yüksek kaliteli ve motivasyonel A4 Başarı Posteri oluşturur."""
        from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize
        from PyQt6.QtCore import QSizeF, QMarginsF
        from PyQt6.QtPrintSupport import QPrinter
        import subprocess, sys

        file, _ = QFileDialog.getSaveFileName(
            self, "Panoya Asmak İçin A4 Pano Posteri Kaydet", "Haftalik_Basari_Panosu.pdf", "PDF (*.pdf)"
        )
        if not file:
            return

        today = self.current_ref_date
        ws, we = _week_bounds(today)
        period_str = f"{ws.strftime('%d.%m.%Y')} – {we.strftime('%d.%m.%Y')}"

        # Top 5 HTML Rows
        top5_html = ""
        medals = ["🥇 1.", "🥈 2.", "🥉 3.", "⭐ 4.", "⭐ 5."]
        for i, r in enumerate(self._cached_top5_rows[:5]):
            adsoyad = f"{(r['ad'] or '').strip()} {(r['soyad'] or '').strip()}".strip()
            pct = int(r["ilerleme_yuzde"] or 0)
            bitti = int(r["gorev_bitti"] or 0)
            toplam = int(r["gorev_toplam"] or 0)
            medal = medals[i] if i < len(medals) else f"{i+1}."
            bg_tr = "#f0fdf4" if i == 0 else ("#f8fafc" if i % 2 == 0 else "#ffffff")

            top5_html += f"""
            <tr style="background-color: {bg_tr};">
                <td style="padding: 7pt; font-weight: bold; border-bottom: 1px solid #e2e8f0; text-align: center; color: #1e3a8a;">{medal}</td>
                <td style="padding: 7pt; font-weight: bold; border-bottom: 1px solid #e2e8f0; color: #0f172a;">{adsoyad}</td>
                <td style="padding: 7pt; font-weight: bold; border-bottom: 1px solid #e2e8f0; text-align: center; color: #15803d;">%{pct}</td>
                <td style="padding: 7pt; border-bottom: 1px solid #e2e8f0; text-align: center; color: #475569;">{bitti} / {toplam} Görev</td>
                <td style="padding: 7pt; border-bottom: 1px solid #e2e8f0; text-align: center; color: #2563eb; font-weight: bold;">{'⭐ Şampiyon' if i==0 else '🌟 Başarılı'}</td>
            </tr>
            """

        if not top5_html:
            top5_html = "<tr><td colspan='5' style='padding: 10pt; text-align: center; color: #64748b;'>Bu hafta henüz tamamlanan görev bulunmamaktadır.</td></tr>"

        # %80+ Club Badges HTML (3 Sütunlu Izgara Tablosu)
        club_badges_html = "<table style='width: 100%; border: none; margin-top: 4pt;'>"
        cols_count = 3
        cells = []
        for r in self._cached_club_rows:
            adsoyad = f"{(r['ad'] or '').strip()} {(r['soyad'] or '').strip()}".strip()
            pct = float(r["w_pct"] or 0)
            badge_title = "Altın Yıldız" if pct >= 95 else ("Gümüş Yıldız" if pct >= 90 else "Bronz Yıldız")
            badge_bg = "#fef3c7" if pct >= 95 else ("#f1f5f9" if pct >= 90 else "#ffedd5")
            badge_border = "#f59e0b" if pct >= 95 else ("#94a3b8" if pct >= 90 else "#ea580c")
            badge_col = "#b45309" if pct >= 95 else ("#334155" if pct >= 90 else "#c2410c")

            cell = f"""
            <td style="width: 33%; padding: 4pt; border: none;">
                <div style="background-color: {badge_bg}; border: 1.5px solid {badge_border}; border-radius: 6pt; padding: 6pt; text-align: center;">
                    <div style="font-size: 10pt; font-weight: bold; color: {badge_col};">🎖️ {adsoyad}</div>
                    <div style="font-size: 8.5pt; color: #475569; margin-top: 2pt; font-weight: 600;">%{pct:.1f} • {badge_title}</div>
                </div>
            </td>
            """
            cells.append(cell)

        if not cells:
            club_badges_html = "<div style='color: #64748b; font-size: 9.5pt; text-align: center; padding: 6pt;'>Henüz %80 barajını aşan öğrenci bulunmuyor.</div>"
        else:
            rows_html = ""
            for i in range(0, len(cells), cols_count):
                row_cells = cells[i:i+cols_count]
                while len(row_cells) < cols_count:
                    row_cells.append("<td style='width: 33%; border: none;'></td>")
                rows_html += f"<tr>{''.join(row_cells)}</tr>"
            club_badges_html += rows_html + "</table>"

        # Podium HTML for Poster
        podium_poster_html = ""
        if len(self._cached_top5_rows) > 0:
            r1 = self._cached_top5_rows[0]
            n1 = f"{(r1['ad'] or '').strip()} {(r1['soyad'] or '').strip()}".strip()
            p1 = int(r1["ilerleme_yuzde"] or 0)
            podium_poster_html += f"""
            <div style="background: #fffbeb; border: 2px solid #f59e0b; border-radius: 8pt; padding: 8pt 12pt; margin-bottom: 10pt; text-align: center;">
                <div style="font-size: 18pt;">👑 🥇</div>
                <div style="font-size: 13pt; font-weight: bold; color: #b45309; margin: 2pt 0;">HAFTANIN ŞAMPİYONU: {n1}</div>
                <div style="font-size: 10pt; color: #78350f; font-weight: 600;">Tamamlama Oranı: %{p1} ({r1['gorev_bitti']}/{r1['gorev_toplam']} Ödev)</div>
            </div>
            """

        poster_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; color: #1e293b; }}
                .header {{ background: #1e3a8a; color: white; padding: 12pt 16pt; border-radius: 8pt; text-align: center; margin-bottom: 10pt; }}
                .h-title {{ font-size: 17pt; font-weight: 900; margin: 0; letter-spacing: 1px; }}
                .h-sub {{ font-size: 9.5pt; margin-top: 3pt; color: #bfdbfe; }}
                .section-title {{ font-size: 11pt; font-weight: bold; color: #1e3a8a; margin: 10pt 0 4pt 0; border-bottom: 1.5px solid #3b82f6; padding-bottom: 2pt; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 4pt; font-size: 9pt; }}
                th {{ background-color: #f1f5f9; color: #334155; font-weight: bold; padding: 6pt; border-bottom: 2px solid #cbd5e1; text-align: center; }}
                .quote-box {{ background: #f8fafc; border-left: 4px solid #3b82f6; padding: 8pt; margin: 10pt 0 8pt 0; font-style: italic; font-size: 9pt; color: #475569; }}
                .footer-box {{ margin-top: 14pt; border-top: 1px solid #cbd5e1; padding-top: 6pt; font-size: 8.5pt; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="h-title">🏆 HAFTALIK PERFORMANS VE BAŞARI PANOSU</div>
                <div class="h-sub">Kurumsal Öğrenci Takip Sistemi • Hafta: {period_str}</div>
            </div>

            {podium_poster_html}

            <div class="section-title">🥇 HAFTANIN EN YÜKSEK PERFORMANS GÖSTERENLERİ (TOP 5)</div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 15%;">Derece</th>
                        <th style="width: 40%; text-align: left; padding-left: 8pt;">Öğrenci Adı Soyadı</th>
                        <th style="width: 15%;">Başarı %</th>
                        <th style="width: 15%;">Ödevler</th>
                        <th style="width: 15%;">Durum</th>
                    </tr>
                </thead>
                <tbody>
                    {top5_html}
                </tbody>
            </table>

            <div class="section-title">🌟 %80+ BAŞARI KULÜBÜ GURUR LİSTESİ</div>
            <div style="margin-top: 4pt;">
                {club_badges_html}
            </div>

            <div class="quote-box">
                <b>💡 Koçun Haftalık Motivasyon Mesajı:</b><br>
                "Büyük başarılar, pes etmeden atılan istikrarlı küçük adımlarla gelir. Bu hafta azimle çalışan tüm öğrencilerimizi yürekten tebrik eder, yeni haftada hedeflerimize aynı kararlılıkla odaklanmayı dilerim."
            </div>

            <div class="footer-box">
                <table style="width: 100%; border: none;">
                    <tr>
                        <td style="border: none; text-align: left; font-weight: bold; color: #475569;">
                            Kurum: YKS/LGS Koçluk & Rehberlik Koordinatörlüğü
                        </td>
                        <td style="border: none; text-align: right; font-weight: bold; color: #475569;">
                            İmza & Onay: _______________________
                        </td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(8, 8, 8, 8),
                QPageLayout.Unit.Millimeter
            )
            printer.setPageLayout(layout)

            doc = QTextDocument()
            doc.setDefaultFont(QFont("Segoe UI", 9))
            page_rect = printer.pageRect(QPrinter.Unit.Point)
            doc.setPageSize(QSizeF(page_rect.width(), page_rect.height()))
            doc.setHtml(poster_html)
            doc.print(printer)

            res = QMessageBox.information(
                self, "A4 Pano Posteri Hazır!",
                f"""Renkli A4 Başarı Posteri başarıyla oluşturuldu:

📂 {file}

Dosyayı şimdi açmak ister misiniz?""",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if res == QMessageBox.StandardButton.Yes:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(file))
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Poster oluşturulurken hata: {e}")
