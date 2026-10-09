# -*- coding: utf-8 -*-
"""
D — Baştan tasarlanmış, optimize edilmiş raporlama ekranı
Python 3.9 uyumlu / YKS_LGS_HomeworkManager veritabanı şeması ile çalışır.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QDateEdit, QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QDate, QSizeF
from PyQt6.QtGui import QPixmap
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import sqlite3
from typing import List, Tuple, Dict, Any, Optional

import db  # mevcut db yardımcıların (get_conn, listele_ogrenciler, DERS_TABLOLARI vs.)


# --- Küçük yardımcılar ------------------------------------------------------

def _make_in_qs(col_name: str, values: List[Any]) -> Tuple[str, List[Any]]:
    """IN (...) sorgusu üretir."""
    if not values:
        return "", []
    placeholders = ",".join(["?"] * len(values))
    return f" AND {col_name} IN ({placeholders})", list(values)

def _add_value_labels(ax):
    """Çubukların üstüne değer etiketleri yerleştirir."""
    for p in ax.patches:
        try:
            v = float(p.get_height())
        except Exception:
            continue
        if v <= 0:
            continue
        ax.annotate(
            f"{int(v)}" if abs(v - int(v)) < 0.01 else f"{v:.1f}",
            (p.get_x() + p.get_width() / 2.0, p.get_height()),
            ha="center", va="bottom", fontsize=9, xytext=(0, 3),
            textcoords="offset points"
        )


def _make_in_clause(col_name: str, values: List[Any]) -> Tuple[str, List[Any]]:
    """
    IN (...) cümlesi üretir.
    values boşsa: ("", [])
    """
    if not values:
        return "", []
    placeholders = ",".join(["?"] * len(values))
    return " AND {col} IN ({ph})".format(col=col_name, ph=placeholders), list(values)


# --- Ana Form ---------------------------------------------------------------


class RaporlarFormu(QWidget):
    """
    Sol: Filtreler + Grafik + Dışa Aktarım
    Sağ: Öğrenci & Ders checklist

    Grafik Türleri:
      - Durum Dağılımı
      - Haftalık Saat Trendi (dk)
      - Ders Dağılımı
      - Geciken Ödevler
      - Öğrenci Başına Tamamlanan (Top 10)
      - Tamamlama Oranı %
      - Gecikme Isı Haritası
      - Konu Verimi (dk/konu)
      - Hafta içi / Hafta sonu
      - Kitap Payı
      - Seri (Streak)
      - Öğrenci KPI
    """
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Raporlar (Yeni)")
        self._last_table_rows: List[Tuple[str, float]] = []
        # Tek bağlantı kullan (senin db.get_conn zaten singleton gibi)
        self._con = db.get_conn()

        root = QHBoxLayout(self)

        # ---------------- SOL SÜTUN ----------------
        left = QVBoxLayout()

        # Filtre barı
        flt = QHBoxLayout()
        flt.addWidget(QLabel("Grafik Türü"))
        self.cmbTur = QComboBox()
        self._grafik_ops = [
            ("Durum Dağılımı", "durum"),
            ("Haftalık Saat Trendi (dk)", "trend"),
            ("Ders Dağılımı", "ders"),
            ("Geciken Ödevler", "geciken"),
            ("Öğrenci Başına Tamamlanan (Top 10)", "top10"),
            ("Tamamlama Oranı %", "tamamlama"),
            ("Gecikme Isı Haritası", "isi"),
            ("Konu Verimi (dk/konu)", "verim"),
            ("Hafta içi / Hafta sonu", "ww"),
            ("Kitap Payı", "kitap"),
            ("Seri (Streak)", "streak"),
            ("Öğrenci KPI", "kpi"),
        ]
        for label, key in self._grafik_ops:
            self.cmbTur.addItem(label, key)
        self.cmbTur.setCurrentIndex(0)

        flt.addWidget(self.cmbTur)

        flt.addWidget(QLabel("Başlangıç"))
        self.dtpBas = QDateEdit()
        self.dtpBas.setCalendarPopup(True)
        self.dtpBas.setDate(QDate.currentDate().addMonths(-2))
        flt.addWidget(self.dtpBas)

        flt.addWidget(QLabel("Bitiş"))
        self.dtpBit = QDateEdit()
        self.dtpBit.setCalendarPopup(True)
        self.dtpBit.setDate(QDate.currentDate())
        flt.addWidget(self.dtpBit)

        self.btnGoster = QPushButton("▶️ Göster")
        self.btnGoster.setObjectName("btnPrimary")
        flt.addWidget(self.btnGoster)
        flt.addStretch(1)
        left.addLayout(flt)

        # Küçük özet label (toplam / tamam / devam)
        self.lblOzet = QLabel("Özet: -")
        self.lblOzet.setStyleSheet("color: #555; font-size: 11px;")
        left.addWidget(self.lblOzet)

        # Grafik alanı
        self.fig = Figure(figsize=(6, 4))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        left.addWidget(self.canvas, 1)

        # Akıllı Analiz Kutusu
        self.lblInsightHeader = QLabel("💡 Yapay Zeka - Akıllı Analiz")
        self.lblInsightHeader.setStyleSheet("color: #2563eb; font-weight: bold; margin-top: 8px;")
        
        from PyQt6.QtWidgets import QTextEdit
        self.txtInsight = QTextEdit()
        self.txtInsight.setReadOnly(True)
        self.txtInsight.setMaximumHeight(80)
        self.txtInsight.setStyleSheet("""
            QTextEdit {
                background-color: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 6px;
                color: #334155;
                font-size: 13px;
                padding: 4px;
            }
        """)
        left.addWidget(self.lblInsightHeader)
        left.addWidget(self.txtInsight)

        # Çıktı butonları
        out = QHBoxLayout()
        
        self.btnMobileProgram = QPushButton("📱 Cep Programı")
        self.btnMobileProgram.setToolTip("Telefona göndermek için Haftalık Program PDF'i oluştur")
        self.btnMobileProgram.setStyleSheet("background-color: #7c3aed; color: white; border: 1px solid #6d28d9;")
        self.btnMobileProgram.clicked.connect(self._mobile_program)
        out.addWidget(self.btnMobileProgram)
        
        self.btnYazdir = QPushButton("🖨️ Yazdır")
        self.btnYazdir.setObjectName("btnInfo")
        self.btnExcel = QPushButton("📊 Excel'e Aktar")
        self.btnExcel.setObjectName("btnExcel")
        self.btnPdf = QPushButton("📄 PDF Kaydet")
        self.btnPdf.setObjectName("btnPdf")
        
        self.btnBulk = QPushButton("🚀 Toplu Rapor")
        self.btnBulk.setToolTip("Tüm öğrenciler için otomatik rapor oluştur ve klasöre kaydet")
        self.btnBulk.setStyleSheet("background-color: #2563eb; color: white; border: 1px solid #1d4ed8; font-weight: bold;")
        self.btnBulk.clicked.connect(self._toplu_rapor_olustur)

        out.addStretch(1)
        out.addWidget(self.btnBulk)
        out.addWidget(self.btnYazdir)
        out.addWidget(self.btnExcel)
        out.addWidget(self.btnPdf)
        left.addLayout(out)

        # ---------------- SAĞ SÜTUN ----------------
        right = QVBoxLayout()

        right.addWidget(QLabel("Öğrenciler"))
        self.lstOgr = QListWidget()
        self.lstOgr.setSelectionMode(self.lstOgr.SelectionMode.NoSelection)
        right.addWidget(self.lstOgr, 1)

        ogBtns = QHBoxLayout()
        self.btnOgrAll = QPushButton("✅ Tümünü Seç")
        self.btnOgrAll.setObjectName("btnSuccess")
        self.btnOgrNone = QPushButton("🔳 Hiçbiri")
        ogBtns.addWidget(self.btnOgrAll)
        ogBtns.addWidget(self.btnOgrNone)
        right.addLayout(ogBtns)

        right.addWidget(QLabel("Dersler"))
        self.lstDers = QListWidget()
        self.lstDers.setSelectionMode(self.lstDers.SelectionMode.NoSelection)
        right.addWidget(self.lstDers, 1)

        drBtns = QHBoxLayout()
        self.btnDersAll = QPushButton("✅ Tümünü Seç")
        self.btnDersAll.setObjectName("btnSuccess")
        self.btnDersNone = QPushButton("🔳 Hiçbiri")
        drBtns.addWidget(self.btnDersAll)
        drBtns.addWidget(self.btnDersNone)
        right.addLayout(drBtns)

        root.addLayout(left, 3)
        root.addLayout(right, 1)

        # Sinyaller
        self.btnGoster.clicked.connect(self._goster)
        self.btnYazdir.clicked.connect(self._yazdir)
        self.btnExcel.clicked.connect(self._excel)
        self.btnPdf.clicked.connect(self._pdf)
        self.btnOgrAll.clicked.connect(lambda: self._check_all(self.lstOgr, True))
        self.btnOgrNone.clicked.connect(lambda: self._check_all(self.lstOgr, False))
        self.btnDersAll.clicked.connect(lambda: self._check_all(self.lstDers, True))
        self.btnDersNone.clicked.connect(lambda: self._check_all(self.lstDers, False))
        self.lstOgr.itemDoubleClicked.connect(self._toggle_item)
        self.lstDers.itemDoubleClicked.connect(self._toggle_item)

        # İlk yükleme
        self._yukle_ogrenciler()
        self._yukle_dersler()

        # İlk çizim
        self._goster()
        
        # Stil
        self._apply_modern_visuals()

    def _apply_modern_visuals(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; background-color: #f8fafc; color: #1e293b; }
            
            QLabel { font-weight: 600; color: #334155; }
            QComboBox, QDateEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px; background: white; min-height: 24px; }
            QComboBox:focus, QDateEdit:focus { border: 2px solid #2563eb; }
            
            QListWidget { border: 1px solid #e2e8f0; border-radius: 8px; background: white; }
            QListWidget::item { padding: 4px; }
            QListWidget::item:selected { background: #eff6ff; color: #1e3a8a; }
            
            /* Buttons */
            QPushButton { border-radius: 6px; padding: 6px 12px; font-weight: 600; background: white; border: 1px solid #cbd5e1; color: #475569; }
            QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
            
            QPushButton#btnPrimary { background-color: #2563eb; color: white; border: 1px solid #2563eb; }
            QPushButton#btnPrimary:hover { background-color: #1d4ed8; }
            
            QPushButton#btnSuccess { background-color: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
            QPushButton#btnSuccess:hover { background-color: #d1fae5; }
            
            QPushButton#btnExcel { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
            QPushButton#btnExcel:hover { background-color: #bbf7d0; }

            QPushButton#btnPdf { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
            QPushButton#btnPdf:hover { background-color: #fecaca; }

            QPushButton#btnInfo { background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
            QPushButton#btnInfo:hover { background-color: #dbeafe; }
        """)

    # ---------- Checklist yardımcıları ----------

    def _yukle_ogrenciler(self):
        self.lstOgr.clear()
        con = self._con
        for r in db.listele_ogrenciler(con, aktif_yalniz=True):
            it = QListWidgetItem(f"{r['ad']} {r['soyad']}")
            it.setData(0x0100, int(r['id']))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.lstOgr.addItem(it)

    def _yukle_dersler(self):
        self.lstDers.clear()
        dersler: List[str] = []
        try:
            dersler = list(db.DERS_TABLOLARI)  # senin sabitin
        except Exception:
            pass

        if not dersler:
            # Fallback: odev_satir'dan distinct ders
            con = self._con
            rows = con.execute(
                "SELECT DISTINCT ders FROM odev_satir "
                "WHERE ders IS NOT NULL AND ders<>'' ORDER BY ders"
            ).fetchall()
            dersler = [r[0] for r in rows]

        for d in dersler:
            it = QListWidgetItem(d)
            it.setData(0x0100, d)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.lstDers.addItem(it)

    def _check_all(self, qlist: QListWidget, val: bool):
        st = Qt.CheckState.Checked if val else Qt.CheckState.Unchecked
        for i in range(qlist.count()):
            qlist.item(i).setCheckState(st)

    def _toggle_item(self, it: QListWidgetItem):
        it.setCheckState(
            Qt.CheckState.Unchecked if it.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )

    def _secili_ogr_idler(self) -> List[int]:
        out: List[int] = []
        for i in range(self.lstOgr.count()):
            it = self.lstOgr.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(int(it.data(0x0100)))
        return out

    def _secili_dersler(self) -> List[str]:
        out: List[str] = []
        for i in range(self.lstDers.count()):
            it = self.lstDers.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(str(it.data(0x0100)))
        return out

    # ---------- Veri çekme yardımcıları ----------

    def _adsoyad(self, oid: int) -> str:
        try:
            con = self._con
            r = con.execute(
                "SELECT ad, soyad FROM ogrenci WHERE id=?", (oid,)
            ).fetchone()
            if not r:
                return "Öğrenci#%d" % oid
            ad = r["ad"] or ""
            soy = r["soyad"] or ""
            full = (ad + " " + soy).strip()
            return full or ("Öğrenci#%d" % oid)
        except Exception:
            return "Öğrenci#%d" % oid

    def _durum_dagilimi(self, bas: str, bit: str,
                         ogr_ids: List[int], dersler: List[str]) -> Dict[str, int]:
        """
        odev + odev_satir birleşik durum sayımı.
        Çıktı: {'devam': x, 'yapildi': y, 'iptal': z, 'diger': t}
        """
        con = self._con
        # ---- A) odev + odev_kume
        params: List[Any] = [bas, bit]
        id_sql = ders_sql = ""

        if ogr_ids:
            id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
            params += add
        if dersler:
            ders_sql, add = _make_in_clause("o.ders", dersler)
            params += add

        sql_odev = """
            SELECT CASE
                     WHEN LOWER(COALESCE(o.durum,'')) IN ('tamam','yapildi','yapıldı') THEN 'yapildi'
                     WHEN LOWER(COALESCE(o.durum,'')) IN ('iptal','cancel') THEN 'iptal'
                     ELSE 'devam'
                   END AS d
            FROM odev o
            JOIN odev_kume k ON k.id = o.kume_id
            WHERE date(COALESCE(k.verilis_tarihi, k.bitis_tarihi,'')) BETWEEN date(?) AND date(?)
              {id_sql} {ders_sql}
        """.format(id_sql=id_sql, ders_sql=ders_sql)

        rows_odev = con.execute(sql_odev, params).fetchall()

        # ---- B) odev_satir
        params2: List[Any] = [bas, bit]
        id_sql2 = ders_sql2 = ""
        if ogr_ids:
            id_sql2, add2 = _make_in_clause("s.ogrenci_id", ogr_ids)
            params2 += add2
        if dersler:
            ders_sql2, add2 = _make_in_clause("s.ders", dersler)
            params2 += add2

        sql_sat = """
            SELECT CASE
                     WHEN LOWER(COALESCE(s.durum,'')) IN ('tamam','yapildi','yapıldı') THEN 'yapildi'
                     WHEN LOWER(COALESCE(s.durum,'')) IN ('iptal','cancel') THEN 'iptal'
                     ELSE 'devam'
                   END AS d
            FROM odev_satir s
            WHERE date(COALESCE(s.tarih,'')) BETWEEN date(?) AND date(?)
              {id_sql} {ders_sql}
        """.format(id_sql=id_sql2, ders_sql=ders_sql2)

        rows_sat = con.execute(sql_sat, params2).fetchall()

        say = {'devam': 0, 'yapildi': 0, 'iptal': 0, 'diger': 0}
        for r in list(rows_odev) + list(rows_sat):
            d = (r["d"] or "").lower()
            if d not in say:
                d = 'diger'
            say[d] += 1
        return say

    def _haftalik_saat_trendi(self, bas: str, bit: str,
                              ogr_ids: List[int], ders_list: List[str]
                              ) -> List[Tuple[str, float]]:
        """
        Haftalara göre toplam çalışma dakikası.
        Kaynak: öncelik odev_satir.sure_dk; yoksa odev.saat_dk; o da yoksa adet*25 dk.
        Çıktı: [('2025-45', 120), ...]
        """
        con = self._con

        # Önce odev_satir varsa onu kullan
        cols_os = {r[1] for r in con.execute("PRAGMA table_info(odev_satir)")}
        params: List[Any] = [bas, bit]
        id_sql = ders_sql = ""
        if ogr_ids:
            id_sql, add = _make_in_clause("s.ogrenci_id", ogr_ids)
            params += add
        if ders_list:
            ders_sql, add = _make_in_clause("s.ders", ders_list)
            params += add

        rows: List[sqlite3.Row] = []
        if cols_os:
            dk_expr = "COALESCE(s.sure_dk, 0)"
            sql_new = f"""
                SELECT strftime('%Y-%W', date(COALESCE(s.tarih,''))) AS yw,
                       SUM({dk_expr}) AS dk,
                       COUNT(*) AS adet
                FROM odev_satir s
                WHERE date(COALESCE(s.tarih,'')) BETWEEN date(?) AND date(?)
                  AND LOWER(COALESCE(s.durum,'')) NOT IN ('iptal','cancel')
                  {id_sql} {ders_sql}
                GROUP BY yw
                ORDER BY yw
            """
            rows = con.execute(sql_new, params).fetchall()

        # Eğer dk hep 0 ise adet*25
        out: Dict[str, float] = {}
        for r in rows:
            yw = r["yw"] or ""
            dk = float(r["dk"] or 0.0)
            adet = int(r["adet"] or 0)
            if dk <= 0 and adet > 0:
                dk = adet * 25.0
            out[yw] = out.get(yw, 0.0) + dk

        # Fallback: hiç veri yoksa odev+odev_kume
        if not out:
            params = [bas, bit]
            id_sql = ders_sql = ""
            if ogr_ids:
                id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
                params += add
            if ders_list:
                ders_sql, add = _make_in_clause("o.ders", ders_list)
                params += add

            sql_old = f"""
                SELECT strftime('%Y-%W', date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,''))) AS yw,
                       SUM(COALESCE(o.saat_dk,0)) AS dk,
                       COUNT(*) AS adet
                FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) BETWEEN date(?) AND date(?)
                  AND LOWER(COALESCE(o.durum,'')) NOT IN ('iptal','cancel')
                  {id_sql} {ders_sql}
                GROUP BY yw
                ORDER BY yw
            """
            rows2 = con.execute(sql_old, params).fetchall()
            for r in rows2:
                yw = r["yw"] or ""
                dk = float(r["dk"] or 0.0)
                adet = int(r["adet"] or 0)
                if dk <= 0 and adet > 0:
                    dk = adet * 25.0
                out[yw] = out.get(yw, 0.0) + dk

        return sorted([(k, v) for k, v in out.items()], key=lambda x: x[0])

    def _ders_dagilimi(self, bas: str, bit: str,
                        ogr_ids: List[int], ders: List[str]
                        ) -> List[Tuple[str, float]]:
        con = self._con
        sql = "SELECT COALESCE(ders,'(boş)') AS d, COUNT(*) AS c FROM odev_satir WHERE 1=1"
        params: List[Any] = []
        if bas:
            sql += " AND date(COALESCE(tarih,'')) >= date(?)"
            params.append(bas)
        if bit:
            sql += " AND date(COALESCE(tarih,'')) <= date(?)"
            params.append(bit)
        if ogr_ids:
            sql_in, add = _make_in_clause("ogrenci_id", ogr_ids)
            sql += sql_in
            params += add
        if ders:
            sql_in, add = _make_in_clause("ders", ders)
            sql += sql_in
            params += add
        sql += " GROUP BY d ORDER BY c DESC"
        rows = con.execute(sql, params).fetchall()
        return [(r["d"], float(r["c"] or 0)) for r in rows]

    def _geciken_odevler(self, bas: str, bit: str,
                         ogr_ids: List[int], ders: List[str]
                         ) -> List[Tuple[str, float]]:
        """
        Öğrenci bazında geciken küme sayısı.
        bitis_tarihi < bugün ve hala tamamlanmamış ödev satırı var.
        """
        con = self._con
        try:
            con.execute("SELECT 1 FROM odev_kume LIMIT 1")
            con.execute("SELECT 1 FROM odev LIMIT 1")
        except Exception:
            return []

        sql = (
            "SELECT o.ogrenci_id AS oid, COUNT(DISTINCT k.id) AS adet "
            "FROM odev_kume k "
            "JOIN odev o ON o.kume_id = k.id "
            "WHERE date(COALESCE(k.bitis_tarihi,'')) < date('now')"
        )
        params: List[Any] = []

        if bas:
            sql += " AND date(COALESCE(k.verilis_tarihi,'')) >= date(?)"
            params.append(bas)
        if bit:
            sql += " AND date(COALESCE(k.verilis_tarihi,'')) <= date(?)"
            params.append(bit)
        if ogr_ids:
            sql_in, add = _make_in_clause("o.ogrenci_id", ogr_ids)
            sql += sql_in
            params += add
        if ders:
            sql_in, add = _make_in_clause("o.ders", ders)
            sql += sql_in
            params += add
        sql += " GROUP BY o.ogrenci_id ORDER BY adet DESC"

        rows = con.execute(sql, params).fetchall()
        out: List[Tuple[str, float]] = []
        for r in rows:
            name = self._adsoyad(int(r["oid"]))
            out.append((name, float(r["adet"] or 0)))
        return out

    def _tamamlanan_top(self, bas: str, bit: str,
                        ogr_ids: List[int], ders: List[str],
                        limit: int = 10
                        ) -> List[Tuple[str, float]]:
        con = self._con
        sql = (
            "SELECT ogrenci_id AS oid, COUNT(*) AS c FROM odev_satir "
            "WHERE LOWER(COALESCE(durum,'')) IN ('yapildi','yapıldı','tamam')"
        )
        params: List[Any] = []
        if bas:
            sql += " AND date(COALESCE(tarih,'')) >= date(?)"
            params.append(bas)
        if bit:
            sql += " AND date(COALESCE(tarih,'')) <= date(?)"
            params.append(bit)
        if ogr_ids:
            sql_in, add = _make_in_clause("ogrenci_id", ogr_ids)
            sql += sql_in
            params += add
        if ders:
            sql_in, add = _make_in_clause("ders", ders)
            sql += sql_in
            params += add
        sql += " GROUP BY oid ORDER BY c DESC LIMIT ?"
        params.append(limit)
        rows = con.execute(sql, params).fetchall()
        out: List[Tuple[str, float]] = []
        for r in rows:
            out.append((self._adsoyad(int(r["oid"])), float(r["c"] or 0)))
        return out

    def _tamamlama_orani(self, bas: str, bit: str,
                         ogr_ids: List[int], ders_list: List[str]
                         ) -> List[Tuple[str, float]]:
        """
        Her öğrenci için tamamlanan / toplam oranı (yüzde).
        Kaynak: odev (durum alanı)
        Çıktı: [(ad, yüzde), ...]
        """
        con = self._con
        p: List[Any] = [bas, bit]
        id_sql = ders_sql = ""
        if ogr_ids:
            id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
            p += add
        if ders_list:
            ders_sql, add = _make_in_clause("o.ders", ders_list)
            p += add

        sql = f"""
          SELECT o.ogrenci_id AS oid,
                 SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) IN ('tamam','yapildi','yapıldı')
                          THEN 1 ELSE 0 END) AS done,
                 COUNT(*) AS total
          FROM odev o
          JOIN odev_kume k ON k.id=o.kume_id
          WHERE date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) BETWEEN date(?) AND date(?)
            {id_sql} {ders_sql}
          GROUP BY o.ogrenci_id
        """
        rows = con.execute(sql, p).fetchall()
        out: List[Tuple[str, float]] = []
        for r in rows:
            done = int(r["done"] or 0)
            total = int(r["total"] or 0)
            if total <= 0:
                oran = 0.0
            else:
                oran = 100.0 * done / float(total)
            out.append((self._adsoyad(int(r["oid"])), oran))
        # En yüksekten düşüğe
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    def _gecikme_isiharitasi_data(self, bas: str, bit: str,
                                  ogr_ids: List[int], ders_list: List[str]
                                  ) -> Tuple[List[str], List[str], List[List[float]]]:
        """
        Gecikme Isı Haritası için ham veri:
        Dönen:
          (ogrenci_etiket_listesi, ders_etiket_listesi, matris)
          matris[i][j] = geciken adet
        """
        con = self._con
        p: List[Any] = [bit, bas, bit]
        id_sql = ders_sql = ""
        if ogr_ids:
            id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
            p += add
        if ders_list:
            ders_sql, add = _make_in_clause("o.ders", ders_list)
            p += add

        sql = f"""
          SELECT o.ogrenci_id AS oid,
                 o.ders,
                 SUM(
                     CASE
                       WHEN LOWER(COALESCE(o.durum,'')) NOT IN ('tamam','yapildi','yapıldı')
                            AND date(COALESCE(k.bitis_tarihi,'')) < date(?)
                       THEN 1 ELSE 0
                     END
                 ) AS overdue
          FROM odev o
          JOIN odev_kume k ON k.id=o.kume_id
          WHERE date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) BETWEEN date(?) AND date(?)
            {id_sql} {ders_sql}
          GROUP BY o.ogrenci_id, o.ders
        """
        rows = con.execute(sql, p).fetchall()
        if not rows:
            return [], [], []

        # Ogr ve ders setleri
        ogr_ids_all = sorted({int(r["oid"]) for r in rows})
        ders_all = sorted({str(r["ders"]) for r in rows if r["ders"]})

        # index map
        idx_ogr = {oid: i for i, oid in enumerate(ogr_ids_all)}
        idx_ders = {d: j for j, d in enumerate(ders_all)}

        # boş matris
        matr: List[List[float]] = [
            [0.0 for _ in ders_all] for _ in ogr_ids_all
        ]
        for r in rows:
            oid = int(r["oid"])
            d = str(r["ders"] or "")
            if d not in idx_ders:
                continue
            i = idx_ogr[oid]
            j = idx_ders[d]
            matr[i][j] = float(r["overdue"] or 0.0)

        ogr_labels = [self._adsoyad(oid) for oid in ogr_ids_all]
        return ogr_labels, ders_all, matr

    def _konu_verimi(self, bas: str, bit: str,
                     ogr_ids: List[int], ders_list: List[str]
                     ) -> List[Tuple[str, float]]:
        """
        Konu bazında dk/konu metriği.
        Kaynak: odev (saat_dk + durum 'tamam')
        Çıktı: [("Mat - Üslü Sayılar", 35.2), ...] (en çok dk harcanandan aşağı)
        """
        con = self._con
        p: List[Any] = [bas, bit]
        id_sql = ders_sql = ""
        if ogr_ids:
            id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
            p += add
        if ders_list:
            ders_sql, add = _make_in_clause("o.ders", ders_list)
            p += add

        sql = f"""
          SELECT o.ders,
                 o.konu_ad,
                 SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) IN ('tamam','yapildi','yapıldı')
                          THEN COALESCE(o.saat_dk,0) ELSE 0 END) AS dk,
                 SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) IN ('tamam','yapildi','yapıldı')
                          THEN 1 ELSE 0 END) AS done
          FROM odev o
          JOIN odev_kume k ON k.id=o.kume_id
          WHERE date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) BETWEEN date(?) AND date(?)
            {id_sql} {ders_sql}
          GROUP BY o.ders, o.konu_ad
        """
        rows = con.execute(sql, p).fetchall()
        out: List[Tuple[str, float]] = []
        for r in rows:
            ders = r["ders"] or ""
            konu = r["konu_ad"] or ""
            if not konu:
                continue
            dk = float(r["dk"] or 0.0)
            done = int(r["done"] or 0)
            if done <= 0:
                continue
            oran = dk / float(done)  # bir tamamlanan konu başına ortalama dk
            label = f"{ders} - {konu}" if ders else konu
            out.append((label, oran))
        # En verimli (en az süre) ya da en büyük süre? Burada "en çok emek harcanan"
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:25]  # grafiği çok kalabalık yapmamak için ilk 25

    def _weekday_weekend(self, bas: str, bit: str,
                         ogr_ids: List[int], ders_list: List[str]
                         ) -> Dict[str, int]:
        """
        Hafta içi / hafta sonu toplam dk.
        Önce odev_satir (sure_dk), yoksa odev+odev_kume (saat_dk) + adet*25 fallback.
        Dönüş: {"haftaici": x, "haftasonu": y}
        """
        con = self._con

        haftaici = 0.0
        haftasonu = 0.0

        cols_os = {r[1] for r in con.execute("PRAGMA table_info(odev_satir)")}
        used_new = False

        if cols_os:
            used_new = True
            p: List[Any] = [bas, bit]
            id_sql, add = _make_in_clause("s.ogrenci_id", ogr_ids)
            p += add
            ders_sql, add = _make_in_clause("s.ders", ders_list)
            p += add
            dk_expr = "COALESCE(s.sure_dk,0)"

            sql_new = f"""
                SELECT strftime('%w', date(COALESCE(s.tarih,''))) AS dow,
                       SUM({dk_expr}) AS dk,
                       COUNT(*) AS adet
                FROM odev_satir s
                WHERE date(COALESCE(s.tarih,'')) BETWEEN date(?) AND date(?)
                  AND LOWER(COALESCE(s.durum,'')) NOT IN ('iptal','cancel')
                  {id_sql} {ders_sql}
                GROUP BY dow
            """
            rows = con.execute(sql_new, p).fetchall()
            for r in rows:
                dow = str(r["dow"] or "")
                dk = float(r["dk"] or 0.0)
                adet = int(r["adet"] or 0)
                if dk <= 0 and adet > 0:
                    dk = adet * 25.0
                if dow in ("1", "2", "3", "4", "5"):
                    haftaici += dk
                elif dow in ("0", "6"):
                    haftasonu += dk

        # Eski şemaya fallback
        if (not used_new) or (haftaici + haftasonu <= 0.0):
            try:
                con.execute("SELECT 1 FROM odev LIMIT 1")
                con.execute("SELECT 1 FROM odev_kume LIMIT 1")
                have_old = True
            except Exception:
                have_old = False

            if have_old:
                p = [bas, bit]
                id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
                p += add
                ders_sql, add = _make_in_clause("o.ders", ders_list)
                p += add

                sql_old = f"""
                    SELECT strftime('%w', date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,''))) AS dow,
                           SUM(COALESCE(o.saat_dk,0)) AS dk,
                           COUNT(*) AS adet
                    FROM odev o
                    JOIN odev_kume k ON k.id=o.kume_id
                    WHERE date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) BETWEEN date(?) AND date(?)
                      AND LOWER(COALESCE(o.durum,'')) NOT IN ('iptal','cancel')
                      {id_sql} {ders_sql}
                    GROUP BY dow
                """
                rows2 = con.execute(sql_old, p).fetchall()
                for r in rows2:
                    dow = str(r["dow"] or "")
                    dk = float(r["dk"] or 0.0)
                    adet = int(r["adet"] or 0)
                    if dk <= 0 and adet > 0:
                        dk = adet * 25.0
                    if dow in ("1", "2", "3", "4", "5"):
                        haftaici += dk
                    elif dow in ("0", "6"):
                        haftasonu += dk

        return {"haftaici": int(round(haftaici)), "haftasonu": int(round(haftasonu))}

    def _kitap_pay(self, bas: str, bit: str,
                   ogr_ids: List[int], ders: List[str]
                   ) -> List[Tuple[str, float]]:
        """Önce odev_satir.kitap, olmazsa odev.kitap_ad."""
        con = self._con
        params: List[Any] = []
        sql = "SELECT COALESCE(kitap,'(boş)') AS label, COUNT(*) AS cnt FROM odev_satir WHERE 1=1"
        if bas:
            sql += " AND date(COALESCE(tarih,'')) >= date(?)"
            params.append(bas)
        if bit:
            sql += " AND date(COALESCE(tarih,'')) <= date(?)"
            params.append(bit)
        if ogr_ids:
            sql_in, add = _make_in_clause("ogrenci_id", ogr_ids)
            sql += sql_in
            params += add
        if ders:
            sql_in, add = _make_in_clause("ders", ders)
            sql += sql_in
            params += add
        sql += " GROUP BY label ORDER BY cnt DESC"
        rows = con.execute(sql, params).fetchall()
        toplam = sum(int(r["cnt"] or 0) for r in rows) if rows else 0
        if toplam > 0:
            return [(r["label"], float(r["cnt"] or 0)) for r in rows]

        # Fallback: odev + odev_kume
        params2: List[Any] = []
        sql2 = (
            "SELECT COALESCE(o.kitap_ad,'(boş)') AS label, COUNT(*) AS cnt "
            "FROM odev o JOIN odev_kume k ON k.id=o.kume_id WHERE 1=1"
        )
        if bas:
            sql2 += " AND date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) >= date(?)"
            params2.append(bas)
        if bit:
            sql2 += " AND date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) <= date(?)"
            params2.append(bit)
        if ogr_ids:
            sql_in, add = _make_in_clause("o.ogrenci_id", ogr_ids)
            sql2 += sql_in
            params2 += add
        if ders:
            sql_in, add = _make_in_clause("o.ders", ders)
            sql2 += sql_in
            params2 += add
        sql2 += " GROUP BY label ORDER BY cnt DESC"
        rows2 = con.execute(sql2, params2).fetchall()
        return [(r["label"], float(r["cnt"] or 0)) for r in rows2]

    def _streak(self, bas: str, bit: str,
                ogr_ids: List[int], ders_list: List[str]
                ) -> List[Dict[str, Any]]:
        """
        Her öğrenci için:
          - max_streak: en uzun ardışık gün
          - cur_streak: aralığın sonuna kadar devam eden seri uzunluğu
          - active_days: toplam çalışılan gün
        """
        import datetime as _dt
        con = self._con

        # ---- A) odev_satir
        p: List[Any] = [bas, bit]
        id_sql = ders_sql = ""
        if ogr_ids:
            id_sql, add = _make_in_clause("s.ogrenci_id", ogr_ids)
            p += add
        if ders_list:
            ders_sql, add = _make_in_clause("s.ders", ders_list)
            p += add

        sql_new = f"""
            SELECT s.ogrenci_id AS oid, date(COALESCE(s.tarih,'')) AS d
            FROM odev_satir s
            WHERE date(COALESCE(s.tarih,'')) BETWEEN date(?) AND date(?)
              AND LOWER(COALESCE(s.durum,'')) NOT IN ('iptal','cancel')
              {id_sql} {ders_sql}
            GROUP BY s.ogrenci_id, date(COALESCE(s.tarih,''))
            ORDER BY s.ogrenci_id, d
        """
        rows = con.execute(sql_new, p).fetchall()

        # ---- B) Fallback: odev+odev_kume
        if not rows:
            p = [bas, bit]
            id_sql = ders_sql = ""
            if ogr_ids:
                id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
                p += add
            if ders_list:
                ders_sql, add = _make_in_clause("o.ders", ders_list)
                p += add
            sql_old = f"""
                SELECT o.ogrenci_id AS oid, date(COALESCE(k.verilis_tarihi,'')) AS d
                FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE date(COALESCE(k.verilis_tarihi,'')) BETWEEN date(?) AND date(?)
                  AND LOWER(COALESCE(o.durum,'')) NOT IN ('iptal','cancel')
                  {id_sql} {ders_sql}
                GROUP BY o.ogrenci_id, date(COALESCE(k.verilis_tarihi,''))
                ORDER BY o.ogrenci_id, d
            """
            rows = con.execute(sql_old, p).fetchall()

        try:
            end_dt = _dt.date.fromisoformat(bit)
        except Exception:
            end_dt = _dt.date.today()

        days: Dict[int, List[_dt.date]] = {}
        for r in rows:
            oid = int(r["oid"])
            d = r["d"]
            if not d:
                continue
            try:
                dt = _dt.date.fromisoformat(d)
            except Exception:
                continue
            days.setdefault(oid, []).append(dt)

        out: List[Dict[str, Any]] = []
        for oid, dlist in days.items():
            dlist = sorted(set(dlist))
            if not dlist:
                continue
            max_st = 1
            run = 1
            for i in range(1, len(dlist)):
                if (dlist[i] - dlist[i - 1]).days == 1:
                    run += 1
                else:
                    if run > max_st:
                        max_st = run
                    run = 1
            if run > max_st:
                max_st = run

            cur_st = 1
            i = len(dlist) - 1
            while i > 0 and (dlist[i] - dlist[i - 1]).days == 1:
                cur_st += 1
                i -= 1

            out.append({
                "oid": oid,
                "ad": self._adsoyad(oid),
                "max_streak": int(max_st),
                "cur_streak": int(cur_st),
                "active_days": int(len(dlist)),
            })

        # Seçilen ama veri çıkmayan öğrenciler için 0 ekle
        for oid in (ogr_ids or []):
            if not any(x["oid"] == oid for x in out):
                out.append({
                    "oid": oid,
                    "ad": self._adsoyad(oid),
                    "max_streak": 0,
                    "cur_streak": 0,
                    "active_days": 0,
                })

        out.sort(key=lambda x: x["ad"].lower())
        return out

    def _ogrenci_kpi(self, bas: str, bit: str,
                     ogr_ids: List[int], ders_list: List[str]
                     ) -> List[Dict[str, Any]]:
        """
        Öğrenci bazında KPI: tamam / (tamam + devam) * 100
        Kaynak: tercihen odev_satir, yoksa odev.
        """
        con = self._con

        # 1) odev_satir
        p: List[Any] = [bas, bit]
        id_sql = ders_sql = ""
        if ogr_ids:
            id_sql, add = _make_in_clause("s.ogrenci_id", ogr_ids)
            p += add
        if ders_list:
            ders_sql, add = _make_in_clause("s.ders", ders_list)
            p += add

        sql = f"""
            SELECT s.ogrenci_id AS oid,
                   SUM(CASE WHEN LOWER(COALESCE(s.durum,'')) IN ('yapildi','yapıldı','tamam') THEN 1 ELSE 0 END) AS tamam,
                   SUM(CASE WHEN LOWER(COALESCE(s.durum,'')) IN ('iptal','cancel') THEN 1 ELSE 0 END) AS iptal,
                   SUM(CASE WHEN LOWER(COALESCE(s.durum,'')) NOT IN ('yapildi','yapıldı','tamam','iptal','cancel') THEN 1 ELSE 0 END) AS devam
            FROM odev_satir s
            WHERE date(COALESCE(s.tarih,'')) BETWEEN date(?) AND date(?)
              {id_sql} {ders_sql}
            GROUP BY s.ogrenci_id
        """
        rows = con.execute(sql, p).fetchall()

        # 2) fallback: odev
        if not rows:
            p = [bas, bit]
            id_sql = ders_sql = ""
            if ogr_ids:
                id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
                p += add
            if ders_list:
                ders_sql, add = _make_in_clause("o.ders", ders_list)
                p += add
            sql2 = f"""
                SELECT o.ogrenci_id AS oid,
                       SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) IN ('yapildi','yapıldı','tamam') THEN 1 ELSE 0 END) AS tamam,
                       SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) IN ('iptal','cancel') THEN 1 ELSE 0 END) AS iptal,
                       SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) NOT IN ('yapildi','yapıldı','tamam','iptal','cancel') THEN 1 ELSE 0 END) AS devam
                FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE date(COALESCE(k.verilis_tarihi,'')) BETWEEN date(?) AND date(?)
                  {id_sql} {ders_sql}
                GROUP BY o.ogrenci_id
            """
            rows = con.execute(sql2, p).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            tamam = int(r["tamam"] or 0)
            devam = int(r["devam"] or 0)
            # iptal puanlamaya katılmıyor
            total = tamam + devam
            skor = 100.0 * tamam / float(total) if total > 0 else 0.0
            oid = int(r["oid"])
            out.append({
                "oid": oid,
                "ad": self._adsoyad(oid),
                "tamam": tamam,
                "devam": devam,
                "skor": skor,
            })

        out.sort(key=lambda x: x["skor"], reverse=True)
        return out

    # ---------- Genel yardımcılar ----------

    def _labels_vals(self, rows: List[Tuple[Any, Any]]) -> Tuple[List[str], List[float]]:
        """
        rows beklenen format: [(label, value), ...]
        Güvenli string/float dönüştürme yapar, value <= 0 olanları atar.
        """
        labels: List[str] = []
        vals: List[float] = []
        for r in rows or []:
            lab: Optional[str] = None
            val: Optional[float] = None
            if isinstance(r, (tuple, list)) and len(r) >= 2:
                lab = str(r[0])
                try:
                    val = float(r[1])
                except Exception:
                    val = None
            if lab is not None and val is not None and val > 0:
                labels.append(lab)
                vals.append(val)
        return labels, vals

    def _guncel_ozet(self, bas: str, bit: str,
                     ogr_ids: List[int], ders: List[str]) -> None:
        """
        Üstteki küçük özet label'ı günceller:
        toplam / tamam / devam / iptal sayıları.
        Kaynak: odev_satir (varsa), yoksa odev.
        """
        con = self._con

        # 1) odev_satir
        p: List[Any] = [bas, bit]
        id_sql = ders_sql = ""
        if ogr_ids:
            id_sql, add = _make_in_clause("ogrenci_id", ogr_ids)
            p += add
        if ders:
            ders_sql, add = _make_in_clause("ders", ders)
            p += add

        sql = f"""
            SELECT
               SUM(CASE WHEN LOWER(COALESCE(durum,'')) IN ('yapildi','yapıldı','tamam') THEN 1 ELSE 0 END) AS tamam,
               SUM(CASE WHEN LOWER(COALESCE(durum,'')) IN ('iptal','cancel') THEN 1 ELSE 0 END) AS iptal,
               SUM(CASE WHEN LOWER(COALESCE(durum,'')) NOT IN ('yapildi','yapıldı','tamam','iptal','cancel') THEN 1 ELSE 0 END) AS devam
            FROM odev_satir
            WHERE date(COALESCE(tarih,'')) BETWEEN date(?) AND date(?)
              {id_sql} {ders_sql}
        """
        row = con.execute(sql, p).fetchone()
        if not row:
            # 2) fallback: odev
            p = [bas, bit]
            id_sql = ders_sql = ""
            if ogr_ids:
                id_sql, add = _make_in_clause("o.ogrenci_id", ogr_ids)
                p += add
            if ders:
                ders_sql, add = _make_in_clause("o.ders", ders)
                p += add
            sql2 = f"""
                SELECT
                   SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) IN ('yapildi','yapıldı','tamam') THEN 1 ELSE 0 END) AS tamam,
                   SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) IN ('iptal','cancel') THEN 1 ELSE 0 END) AS iptal,
                   SUM(CASE WHEN LOWER(COALESCE(o.durum,'')) NOT IN ('yapildi','yapıldı','tamam','iptal','cancel') THEN 1 ELSE 0 END) AS devam
                FROM odev o
                JOIN odev_kume k ON k.id=o.kume_id
                WHERE date(COALESCE(k.verilis_tarihi,k.bitis_tarihi,'')) BETWEEN date(?) AND date(?)
                  {id_sql} {ders_sql}
            """
            row = con.execute(sql2, p).fetchone()

        if not row:
            self.lblOzet.setText("Özet: veri yok.")
            return

        tamam = int(row["tamam"] or 0)
        iptal = int(row["iptal"] or 0)
        devam = int(row["devam"] or 0)
        toplam = tamam + iptal + devam

        parca: List[str] = [
            f"Toplam: {toplam}",
            f"Tamam: {tamam}",
            f"Devam: {devam}",
            f"İptal: {iptal}",
        ]
        if ogr_ids:
            parca.append(f"{len(ogr_ids)} öğrenci")
        if ders:
            parca.append(f"{len(ders)} ders")
        self.lblOzet.setText("Özet: " + " | ".join(parca))

    # ---------- Çizim / Göster ----------

    def _goster(self):
        bas = self.dtpBas.date().toString("yyyy-MM-dd")
        bit = self.dtpBit.date().toString("yyyy-MM-dd")
        ogr = self._secili_ogr_idler()
        ders = self._secili_dersler()
        tur_label = self.cmbTur.currentText()
        tur_key = self.cmbTur.currentData()  # isn't used but dursun

        self.ax.clear()
        self._last_table_rows = []

        subtitle_parts: List[str] = []
        if ogr:
            subtitle_parts.append(f"{len(ogr)} öğrenci")
        if ders:
            subtitle_parts.append(f"{len(ders)} ders")
        subtitle = " | ".join(subtitle_parts) if subtitle_parts else "Tüm Kayıtlar"

        # Özet güncelle
        self._guncel_ozet(bas, bit, ogr, ders)

        # ---- 1) Durum Dağılımı
        if tur_label == "Durum Dağılımı":
            data = self._durum_dagilimi(bas, bit, ogr, ders)
            labels = ["devam", "yapildi", "iptal", "diger"]
            vals = [float(data.get(k, 0)) for k in labels]
            self._last_table_rows = list(zip(labels, vals))
            if not any(v > 0 for v in vals):
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.bar(labels, vals)
                self.ax.set_title(f"Ödev Durumları\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("Adet")
                _add_value_labels(self.ax)

        # ---- 2) Haftalık Saat Trendi (dk)
        elif tur_label == "Haftalık Saat Trendi (dk)":
            rows = self._haftalik_saat_trendi(bas, bit, ogr, ders)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))
            if not labels:
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.plot(labels, vals, marker="o")
                self.ax.set_title(f"Haftalık Toplam Çalışma Süresi (dk)\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("Dakika")
                self.ax.set_xlabel("Yıl-Hafta")
                self.ax.grid(True, linestyle="--", alpha=0.4)

        # ---- 3) Ders Dağılımı
        elif tur_label == "Ders Dağılımı":
            rows = self._ders_dagilimi(bas, bit, ogr, ders)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))
            if not any(v > 0 for v in vals):
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.bar(labels, vals)
                self.ax.tick_params(axis='x', rotation=35)
                self.ax.set_title(f"Ders Bazında Ödev Sayısı\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("Adet")
                _add_value_labels(self.ax)

        # ---- 4) Geciken Ödevler
        elif tur_label == "Geciken Ödevler":
            rows = self._geciken_odevler(bas, bit, ogr, ders)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))
            if not any(v > 0 for v in vals):
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.bar(labels, vals)
                self.ax.tick_params(axis='x', rotation=35)
                self.ax.set_title(f"Geciken Ödevler (Öğrenci Bazında)\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("Adet")
                _add_value_labels(self.ax)

        # ---- 5) Öğrenci Başına Tamamlanan (Top 10)
        elif tur_label == "Öğrenci Başına Tamamlanan (Top 10)":
            rows = self._tamamlanan_top(bas, bit, ogr, ders, limit=10)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))
            if not any(v > 0 for v in vals):
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.bar(labels, vals)
                self.ax.tick_params(axis='x', rotation=35)
                self.ax.set_title(f"Tamamlanan Ödev Sayısı — Top 10 Öğrenci\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("Adet")
                _add_value_labels(self.ax)

        # ---- 6) Tamamlama Oranı %
        elif tur_label == "Tamamlama Oranı %":
            rows = self._tamamlama_orani(bas, bit, ogr, ders)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))
            if not labels:
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.bar(labels, vals)
                self.ax.tick_params(axis='x', rotation=35)
                self.ax.set_title(f"Tamamlama Oranı (%)\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("%")
                _add_value_labels(self.ax)

        # ---- 7) Gecikme Isı Haritası
        elif tur_label == "Gecikme Isı Haritası":
            ogr_labels, ders_labels, mat = self._gecikme_isiharitasi_data(bas, bit, ogr, ders)
            if not ogr_labels or not ders_labels:
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                import numpy as np
                arr = np.array(mat, dtype=float)
                im = self.ax.imshow(arr, aspect="auto")
                self.fig.colorbar(im, ax=self.ax, fraction=0.046, pad=0.04)
                self.ax.set_xticks(range(len(ders_labels)))
                self.ax.set_xticklabels(ders_labels, rotation=35, ha="right")
                self.ax.set_yticks(range(len(ogr_labels)))
                self.ax.set_yticklabels(ogr_labels)
                self.ax.set_title(f"Gecikme Isı Haritası\n{bas} → {bit}  •  {subtitle}")
                # Hücrelerin içine sayı yazmak istersen:
                for i in range(len(ogr_labels)):
                    for j in range(len(ders_labels)):
                        v = arr[i, j]
                        if v > 0:
                            self.ax.text(j, i, int(v), ha="center", va="center", fontsize=8)

        # ---- 8) Konu Verimi (dk/konu)
        elif tur_label == "Konu Verimi (dk/konu)":
            rows = self._konu_verimi(bas, bit, ogr, ders)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))
            if not labels:
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.bar(labels, vals)
                self.ax.tick_params(axis='x', rotation=35)
                self.ax.set_title(f"Konu Verimi (dk/konu)\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("dk/konu")
                _add_value_labels(self.ax)

        # ---- 9) Hafta içi / Hafta sonu
        elif tur_label == "Hafta içi / Hafta sonu":
            res = self._weekday_weekend(bas, bit, ogr, ders)
            labels = ["Hafta içi", "Hafta sonu"]
            vals = [float(res.get("haftaici", 0)), float(res.get("haftasonu", 0))]
            self._last_table_rows = list(zip(labels, vals))
            if not any(v > 0 for v in vals):
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                # Fix: Explicit X coordinates + no rotation
                x_pos = range(len(labels))
                self.ax.bar(x_pos, vals, tick_label=labels, width=0.5, color=['#3b82f6', '#f59e0b'])
                self.ax.set_title(f"Hafta içi / Hafta sonu Çalışma Dakikası\n{bas} → {bit}  •  {subtitle}")
                self.ax.set_ylabel("Dakika")
                self.ax.tick_params(axis='x', rotation=0) # Düzeltme: Etiketleri düz tut
                _add_value_labels(self.ax)
            # Y-eksenini 0'dan başlat
            self.ax.set_ylim(bottom=0)

        # ---- 10) Kitap Payı

        # ---- 10) Kitap Payı
        elif tur_label == "Kitap Payı":
            rows = self._kitap_pay(bas, bit, ogr, ders)
            labels, vals = self._labels_vals(rows)
            self._last_table_rows = list(zip(labels, vals))
            vals_f = [float(v) for v in vals]
            if not vals_f or sum(vals_f) <= 0:
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nFiltreleri genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
            else:
                self.ax.pie(vals_f, labels=labels, autopct="%1.0f%%", startangle=90)
                self.ax.axis("equal")
                self.ax.set_title(f"Kitap Payları\n{bas} → {bit}  •  {subtitle}")

        # ---- 11) Seri (Streak)
        elif tur_label == "Seri (Streak)":
            stats = self._streak(bas, bit, ogr, ders)
            if not stats:
                self.ax.set_title(f"Aralıksız Gün Sayısı (Streak)\n{bas} → {bit}")
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nTarih/Ders/Öğrenci seçimini genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
                self._last_table_rows = []
            else:
                labels = [s["ad"] for s in stats]
                vals = [float(s["max_streak"]) for s in stats]
                cur = [float(s["cur_streak"]) for s in stats]
                self.ax.bar(labels, vals)
                self.ax.set_ylabel("Gün")
                self.ax.set_title(f"Aralıksız Gün Sayısı (Streak)\n{bas} → {bit} • {len(labels)} öğrenci")
                self.ax.tick_params(axis='x', rotation=35)
                for i, v in enumerate(vals):
                    self.ax.text(i, v + 0.05, f"{int(v)} (cur {int(cur[i])})",
                                 ha="center", va="bottom", fontsize=9)
                self._last_table_rows = list(zip(labels, vals))

        # ---- 12) Öğrenci KPI
        elif tur_label == "Öğrenci KPI":
            stats = self._ogrenci_kpi(bas, bit, ogr, ders)
            if not stats:
                self.ax.text(0.5, 0.5, "Veri bulunamadı.\nTarih/ders/öğrenci filtresini genişletin.",
                             ha="center", va="center", transform=self.ax.transAxes, alpha=0.7)
                self._last_table_rows = []
            else:
                labels = [s["ad"] for s in stats]
                vals = [float(s["skor"]) for s in stats]
                self.ax.bar(labels, vals)
                self.ax.set_ylim(0, 100)
                self.ax.set_ylabel("Tamamlama Skoru (%)")
                self.ax.set_title(f"Öğrenci KPI (tamamlama oranı)\n{bas} → {bit} • {len(labels)} öğrenci")
                self.ax.tick_params(axis='x', rotation=35)
                _add_value_labels(self.ax)
                self._last_table_rows = list(zip(labels, vals))

        else:
            self.ax.text(0.5, 0.5, "Bu grafik türü henüz bağlanmadı.",
                         ha="center", va="center", transform=self.ax.transAxes)



        # Y-eksenini 0'dan başlat (pie hariç, heatmap hariç, ww hariç - yukarıda set ettik)
        if tur_label not in ("Kitap Payı", "Gecikme Isı Haritası", "Hafta içi / Hafta sonu"):
            try:
                self.ax.set_ylim(bottom=0)
            except Exception:
                pass

        self.fig.tight_layout()
        self.canvas.draw_idle()
        
        # Akıllı Analizi Çalıştır
        self._generate_smart_insights(tur_label, self._last_table_rows)

    def _generate_smart_insights(self, chart_type: str, data: List[Tuple[str, float]]):
        """
        Grafik türüne ve veriye göre otomatik yorum üretir.
        """
        if not data:
            self.txtInsight.setHtml("<i>Veri yok, analiz yapılamıyor.</i>")
            return

        cols = [d[0] for d in data]
        vals = [d[1] for d in data]
        total = sum(vals) if vals else 0
        
        comment = ""
        
        if chart_type == "Durum Dağılımı":
            dct = dict(data)
            yapildi = dct.get("yapildi", 0)
            iptal = dct.get("iptal", 0)
            rate = (yapildi / total * 100) if total else 0
            comment = f"Toplam <b>{int(total)}</b> ödevin <b>{int(yapildi)}</b> tanesi tamamlanmış (%{rate:.1f}).<br>"
            if rate > 80: comment += "🚀 <b>Harika!</b> Tamamlama oranı çok yüksek."
            elif rate < 50: comment += "⚠️ <b>Dikkat:</b> Ödevlerin yarısından fazlası beklemede."
            else: comment += "✅ Süreç normal, ancak takibi bırakmayın."

        elif chart_type == "Haftalık Saat Trendi (dk)":
            if len(vals) >= 2:
                diff = vals[-1] - vals[-2]
                trend = "artış" if diff > 0 else "azalış"
                comment = f"Son hafta çalışma süresi: <b>{int(vals[-1])} dk</b>. Önceki haftaya göre <b>{trend}</b> var.<br>"
                if diff > 0: comment += "💪 Tempoyu koruyun!"
                else: comment += "📉 Düşüş var, motivasyon gerekebilir."
            else:
                comment = "Trend analizi için en az 2 haftalık veri gerekiyor."

        elif chart_type == "Geciken Ödevler":
            top1 = data[0]
            comment = f"En çok gecikme yaşayan: <b>{top1[0]}</b> ({int(top1[1])} küme).<br>"
            comment += "Bu öğrenci ile planlama toplantısı yapılması önerilir."

        elif chart_type == "Öğrenci Başına Tamamlanan (Top 10)":
            top1 = data[0]
            comment = f"Lider: <b>{top1[0]}</b> ({int(top1[1])} ödev).<br>Tebrik edebilirsiniz! 🎉"

        elif chart_type == "Tamamlama Oranı %":
            # Ortalamayı bul
            avg = sum(vals)/len(vals) if vals else 0
            comment = f"Sınıfın ortalama tamamlama oranı: <b>%{avg:.1f}</b>.<br>"
            if avg < 60: comment += "Genel başarı düşük, ödev yükünü kontrol edin."
        
        elif chart_type == "Hafta içi / Hafta sonu":
            wd = dict(data).get("Hafta içi", 0)
            we = dict(data).get("Hafta sonu", 0)
            if wd > we:
                comment = "Çalışmaların çoğu <b>hafta içi</b> yoğunlaşıyor."
            else:
                comment = "Öğrenciler <b>hafta sonu</b> daha yoğun çalışıyor."

        elif chart_type == "Konu Verimi (dk/konu)":
            hardest = data[0][0]
            comment = f"En çok zaman harcanan (zorlanılan) konu: <b>{hardest}</b>.<br>Bu konu için ek etüt planlanabilir."

        else:
            comment = f"Görüntülenen grafik için {len(data)} veri noktası analiz edildi."

        self.txtInsight.setHtml(comment)


    # ---------- Dışa Aktarma / Yazdırma ----------

    def _excel(self):
        if not self._last_table_rows:
            QMessageBox.information(self, "Bilgi", "Önce grafiği üretin (Göster).")
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, "Kaydet", "rapor.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not fn:
            return
        labels, vals = zip(*self._last_table_rows) if self._last_table_rows else ([], [])
        try:
            import pandas as pd
            import numpy as np
            df = pd.DataFrame({"Etiket": labels, "Değer": np.array(vals, dtype=float)})
            if fn.lower().endswith(".csv"):
                df.to_csv(fn, index=False)
            else:
                df.to_excel(fn, index=False)
            QMessageBox.information(self, "Dışa Aktar", "Kayıt tamam.")
        except Exception:
            # pandas yoksa csv
            if not fn.lower().endswith(".csv"):
                fn = fn.rsplit(".", 1)[0] + ".csv"
            try:
                with open(fn, "w", encoding="utf-8") as f:
                    f.write("Etiket,Değer\n")
                    for a, b in self._last_table_rows:
                        f.write(f"{a},{b}\n")
                QMessageBox.information(self, "Dışa Aktar", "CSV olarak kaydedildi.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kaydedilemedi: {e}")

    def _pdf(self):
        fn, _ = QFileDialog.getSaveFileName(
            self, "Profesyonel PDF Raporu Kaydet", "rapor.pdf", "PDF Dosyaları (*.pdf)"
        )
        if not fn:
            return
        self._save_pdf_internal(fn)
        QMessageBox.information(self, "Başarılı", f"PDF Raporu kaydedildi:\n{fn}")

    def _save_pdf_internal(self, fn: str):
        """PDF oluşturma mantığı (dosya yolu verilir, kaydeder)."""
        try:
            from PyQt6.QtPrintSupport import QPrinter
            from PyQt6.QtGui import QPainter, QPageLayout, QPageSize, QFont, QColor
            from PyQt6.QtCore import QRectF, QMarginsF
            import datetime

            # Yazıcı ayarla (A4)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(fn)
            printer.setPageLayout(QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(10, 10, 10, 10) # mm
            ))

            painter = QPainter(printer)
            if not painter.isActive():
                print("Yazıcı başlatılamadı.")
                return

            # --- Yardımcı değerler ---
            def mm(x): return x * (printer.resolution() / 25.4)
            
            w_page = printer.pageLayout().paintRectPixels(printer.resolution()).width()
            h_page = printer.pageLayout().paintRectPixels(printer.resolution()).height()
            
            x_cursor = 0
            y_cursor = 0
            
            # --- 1. Başlık & Logo Alanı ---
            painter.setPen(Qt.GlobalColor.black)
            f_title = QFont("Arial", 24, QFont.Weight.Bold)
            painter.setFont(f_title)
            title_rect = QRectF(0, y_cursor, w_page, mm(15))
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "YKS/LGS Performans Raporu")
            
            f_date = QFont("Arial", 10)
            painter.setFont(f_date)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, 
                             datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))
            
            y_cursor += mm(15)
            
            # Alt çizgi
            painter.setPen(QColor("#3b82f6")) # Profesyonel mavi
            painter.drawLine(int(title_rect.left()), int(y_cursor), int(title_rect.right()), int(y_cursor))
            y_cursor += mm(5)

            # --- 2. Filtre Bilgisi ---
            f_sub = QFont("Arial", 11)
            f_sub.setItalic(True)
            painter.setFont(f_sub)
            painter.setPen(QColor("#555555"))
            
            bas = self.dtpBas.date().toString("yyyy-MM-dd")
            bit = self.dtpBit.date().toString("yyyy-MM-dd")
            
            # Seçili dersleri özetle
            secili_dersler = []
            for i in range(self.lstDers.count()):
                it = self.lstDers.item(i)
                if it.checkState() == Qt.CheckState.Checked:
                    secili_dersler.append(it.text())
            
            ders_text = "Tümü"
            if len(secili_dersler) < self.lstDers.count():
                if len(secili_dersler) <= 3:
                    ders_text = ", ".join(secili_dersler)
                else:
                    ders_text = f"{len(secili_dersler)} ders seçili"
            
            # Seçili öğrenci adı (eğer tek ise)
            ogr_text = "Çoklu / Filtre"
            sel_ogr = [self.lstOgr.item(i).text() for i in range(self.lstOgr.count()) if self.lstOgr.item(i).checkState() == Qt.CheckState.Checked]
            if len(sel_ogr) == 1:
                ogr_text = sel_ogr[0]
            elif len(sel_ogr) == self.lstOgr.count():
                ogr_text = "Tüm Sınıf"
            
            subtitle = f"Öğrenci: {ogr_text}\nDönem: {bas} - {bit}  •  Dersler: {ders_text}"
            
            sub_rect = QRectF(0, y_cursor, w_page, mm(12))
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft, subtitle)
            y_cursor += mm(14)

            # --- 3. Grafik (Resim Olarak) ---
            img = self.canvas.grab().toImage()
            max_h_graph = h_page * 0.45
            
            if not img.isNull():
                aspect = img.height() / img.width()
                graph_w = w_page
                graph_h = graph_w * aspect
                if graph_h > max_h_graph:
                    graph_h = max_h_graph
                    graph_w = graph_h / aspect
                
                # Ortala
                graph_x = (w_page - graph_w) / 2
                painter.drawImage(QRectF(graph_x, y_cursor, graph_w, graph_h), img)
                y_cursor += graph_h + mm(10)

            # --- 4. Veri Tablosu ---
            if self._last_table_rows:
                painter.setPen(Qt.GlobalColor.black)
                f_h3 = QFont("Arial", 14, QFont.Weight.Bold)
                painter.setFont(f_h3)
                painter.drawText(QRectF(0, y_cursor, w_page, mm(10)), Qt.AlignmentFlag.AlignLeft, "Veri Özeti")
                y_cursor += mm(10)
                
                row_h = mm(8)
                col_w = w_page / 2.5 
                
                # Header
                painter.fillRect(QRectF(0, y_cursor, w_page, row_h), QColor("#f1f5f9"))
                painter.setPen(Qt.GlobalColor.black)
                f_th = QFont("Arial", 10, QFont.Weight.Bold)
                painter.setFont(f_th)
                painter.drawText(QRectF(mm(2), y_cursor, col_w, row_h), Qt.AlignmentFlag.AlignVCenter, "Etiket")
                painter.drawText(QRectF(col_w + mm(2), y_cursor, col_w, row_h), Qt.AlignmentFlag.AlignVCenter, "Değer")
                y_cursor += row_h
                
                # Rows
                f_td = QFont("Arial", 10)
                painter.setFont(f_td)
                
                for i, (etiket, deger) in enumerate(self._last_table_rows):
                    if y_cursor + row_h > h_page - mm(15):
                        printer.newPage()
                        y_cursor = mm(10)
                    
                    if i % 2 == 1:
                        painter.fillRect(QRectF(0, y_cursor, w_page, row_h), QColor("#f8fafc"))
                        
                    painter.drawText(QRectF(mm(2), y_cursor, col_w, row_h), Qt.AlignmentFlag.AlignVCenter, str(etiket))
                    painter.drawText(QRectF(col_w + mm(2), y_cursor, col_w, row_h), Qt.AlignmentFlag.AlignVCenter, str(deger))
                    
                    painter.setPen(QColor("#e2e8f0"))
                    painter.drawLine(0, int(y_cursor+row_h), int(w_page), int(y_cursor+row_h))
                    painter.setPen(Qt.GlobalColor.black)
                    
                    y_cursor += row_h

            # --- 5. Alt Bilgi ---
            painter.setPen(QColor("#94a3b8"))
            f_foot = QFont("Arial", 8)
            painter.setFont(f_foot)
            foot_rect = QRectF(0, h_page - mm(10), w_page, mm(10))
            painter.drawText(foot_rect, Qt.AlignmentFlag.AlignRight, "YKS/LGS Takip Sistemi tarafından oluşturulmuştur.")

            painter.end()

        except Exception as e:
            print(f"PDF Save Error: {e}")
            raise e


    def _toplu_rapor_olustur(self):
        """Tüm öğrencileri sırayla seçer, grafiği günceller ve PDF kaydeder."""
        try:
            import os
            import datetime
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget, QHBoxLayout, QPushButton, QApplication
            from PyQt6.QtCore import Qt, QUrl
            from PyQt6.QtGui import QDesktopServices

            # 1. Klasör Hazırla
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            folder_name = f"Raporlar_{datetime.datetime.now().strftime('%Y-%m-%d_%H%M')}"
            save_dir = os.path.join(desktop, folder_name)
            os.makedirs(save_dir, exist_ok=True)

            generated_files = [] # list of (student_name, file_path, phone)

            # 2. Mevcut seçimi sakla
            old_selection = [i for i in range(self.lstOgr.count()) if self.lstOgr.item(i).checkState() == Qt.CheckState.Checked]
            
            # 3. Öğrenci Listesini Al (Telefonları da çekmek lazım)
            # lstOgr data'sında sadece ID var. Telefonu DB'den çekmemiz gerek.
            con = self._con
            # student_id -> phone map
            phones = {}
            rows = con.execute("SELECT id, ogr_tel, veli_tel1 FROM ogrenci").fetchall()
            
            def clean_tel(t):
                if not t: return ""
                c = "".join(filter(str.isdigit, str(t)))
                if len(c) < 10: return ""
                if c.startswith("0"): c = "9" + c
                elif len(c) == 10: c = "90" + c
                return c

            for r in rows:
                # Önce öğrenci teli, yoksa veli teli
                p = clean_tel(r["ogr_tel"])
                if not p:
                    p = clean_tel(r["veli_tel1"])
                phones[str(r["id"])] = p

            # DEBUG START
            try:
                debug_path = os.path.join(desktop, "debug_phones.txt")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(f"Fetched {len(rows)} rows from DB.\n")
                    for r in rows[:5]:
                        f.write(f"ID: {r['id']} - OT: {r['ogr_tel']} - VT: {r['veli_tel1']}\n")
                    f.write(f"Phones dict size: {len(phones)}\n")
                    sample_keys = list(phones.keys())[:5]
                    f.write(f"Sample keys: {sample_keys}\n")
            except Exception as e:
                print(f"Debug log error: {e}")
            # DEBUG END

            # 4. Döngü
            count = self.lstOgr.count()
            # Progress Dialog
            pd = QDialog(self)
            pd.setWindowTitle("Raporlar Oluşturuluyor...")
            pd.setFixedSize(300, 100)
            pd_lbl = QLabel("Lütfen bekleyin...", pd)
            pd_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pd_layout = QVBoxLayout()
            pd_layout.addWidget(pd_lbl)
            pd.setLayout(pd_layout)
            pd.show()

            for i in range(count):
                item = self.lstOgr.item(i)
                st_id = item.data(Qt.ItemDataRole.UserRole)
                st_name = item.text()
                
                pd_lbl.setText(f"İşleniyor: {st_name} ({i+1}/{count})")
                QApplication.processEvents()

                # Tekli seçim yap
                self._check_all(self.lstOgr, False) # Hepsini kapat
                item.setCheckState(Qt.CheckState.Checked) # Bunu aç
                
                # Grafiği çizdir (UI thread'de render edilmesini bekle)
                self._goster() 
                QApplication.processEvents() 
                
                # PDF Kaydet
                safe_name = st_name.replace(" ", "_").replace("/", "-").replace("\\", "-")
                filename = f"{safe_name}_Rapor.pdf"
                full_path = os.path.join(save_dir, filename)
                
                self._save_pdf_internal(full_path)
                
                generated_files.append({
                    "name": st_name,
                    "path": full_path,
                    "phone": phones.get(str(st_id), "")
                })

            pd.close()
            
            # Seçimi eski haline getir
            self._check_all(self.lstOgr, False)
            for i in old_selection:
                self.lstOgr.item(i).setCheckState(Qt.CheckState.Checked)
            self._goster()

            # 5. Sonuç Dialogu (WhatsApp Helper)
            dlg = QDialog(self)
            dlg.setWindowTitle("Toplu Rapor Gönderim Yardımcısı")
            dlg.resize(500, 600)
            
            layout = QVBoxLayout()
            
            info = QLabel(f"<h3 style='color:#16a34a'>✅ {len(generated_files)} Rapor Oluşturuldu!</h3>"
                          f"Dosyalar şu klasörde: <b>{save_dir}</b><br><br>"
                          "Aşağıdaki listeden öğrencinin <b>WhatsApp</b> butonuna tıkla, açılan sohbet penceresine klasörden dosyayı sürükle.")
            info.setWordWrap(True)
            layout.addWidget(info)
            
            btnOpenDir = QPushButton("📂 Klasörü Aç")
            btnOpenDir.setStyleSheet("background-color:#f59e0b; font-weight:bold; padding:8px;")
            btnOpenDir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(save_dir)))
            layout.addWidget(btnOpenDir)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            clayout = QVBoxLayout()
            
            for f in generated_files:
                row = QHBoxLayout()
                row.addWidget(QLabel(f.get("name")))
                
                ph = f.get("phone")
                if ph and len(ph) > 5:
                    btnW = QPushButton("WhatsApp Aç")
                    btnW.setStyleSheet("color:green;")
                    url = f"https://wa.me/{ph}"
                    btnW.clicked.connect(lambda checked, u=url: QDesktopServices.openUrl(QUrl(u)))
                    row.addWidget(btnW)
                else:
                    row.addWidget(QLabel("(No Yok)"))
                
                clayout.addLayout(row)
                
            clayout.addStretch()
            content.setLayout(clayout)
            scroll.setWidget(content)
            layout.addWidget(scroll)
            
            closeBtn = QPushButton("Tamam")
            closeBtn.clicked.connect(dlg.close)
            layout.addWidget(closeBtn)
            
            dlg.setLayout(layout)
            dlg.exec()

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Toplu işlem sırasında hata: {e}")

    def _yazdir(self):
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt6.QtGui import QPainter
        except Exception:
            QMessageBox.information(self, "Bilgi", "PyQt6 yazdırma bileşenleri gerekli.")
            return
        img = self.canvas.grab().toImage()
        if img.isNull():
            QMessageBox.information(self, "Bilgi", "Yazdıracak görüntü yok.")
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() != QPrintDialog.DialogCode.Accepted:
            return
        painter = QPainter(printer)
        rect = painter.viewport()
        pix = QPixmap.fromImage(img)
        scaled = pix.scaled(
            rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(
            int((rect.width() - scaled.width()) / 2),
            int((rect.height() - scaled.height()) / 2),
            scaled
        )
        painter.end()


        painter.end()


    def _mobile_program(self):
        """Haftalık Ders Programı (Mobil PDF)"""
        fn, _ = QFileDialog.getSaveFileName(self, "Haftalık Program Kaydet", "haftalik_program.pdf", "PDF (*.pdf)")
        if not fn: return

        # 1. Veriyi Çek
        con = self._con
        try:
            db.migrate_ogrenci(con)
        except Exception:
            pass
        try:
            # Gün sıralaması için CASE
            sql = """
            SELECT ad, soyad, ogr_tel, kocluk_gunu, kocluk_saati 
            FROM ogrenci 
            WHERE kocluk_gunu IS NOT NULL AND kocluk_gunu != '' AND aktif=1
            ORDER BY 
              CASE kocluk_gunu
                WHEN 'Pazartesi' THEN 1
                WHEN 'Salı' THEN 2
                WHEN 'Çarşamba' THEN 3
                WHEN 'Perşembe' THEN 4
                WHEN 'Cuma' THEN 5
                WHEN 'Cumartesi' THEN 6
                WHEN 'Pazar' THEN 7
                ELSE 8
              END,
              kocluk_saati
            """
            rows = con.execute(sql).fetchall()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veri çekilemedi: {e}")
            return

        if not rows:
            QMessageBox.warning(self, "Uyarı", "Görüşme günü tanımlanmış aktif öğrenci bulunamadı.\nLütfen 'Takip ve Hedefler' ekranından öğrencilere gün atayın.")
            return

        # 2. HTML Oluştur
        import datetime
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; color: #333; }}
                h1 {{ text-align: center; color: #4338ca; margin-bottom: 5px; font-size: 24px; }}
                .sub {{ text-align: center; color: #666; font-size: 12px; margin-bottom: 20px; }}
                
                .day-block {{ margin-bottom: 15px; page-break-inside: avoid; }}
                .day-header {{ 
                    background-color: #e0e7ff; color: #3730a3; 
                    padding: 8px; font-weight: bold; font-size: 16px; 
                    border-radius: 6px; margin-bottom: 8px;
                }}
                .card {{
                    background-color: #f8fafc; border-left: 5px solid #3b82f6;
                    padding: 10px; margin-bottom: 8px; border-radius: 4px; border: 1px solid #e2e8f0;
                }}
                .time {{ font-weight: 800; color: #1e3a8a; font-size: 14px; min-width: 50px; display: inline-block; }}
                .name {{ font-weight: 600; font-size: 15px; }}
                .actions {{ margin-top: 5px; font-size: 12px; }}
                a {{ text-decoration: none; color: #2563eb; font-weight: bold; }}
                .cb {{ display: inline-block; width: 12px; height: 12px; border: 1px solid #999; margin-right: 5px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>Haftalık Koçluk Programı</h1>
            <div class="sub">Oluşturulma: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
        """

        current_day = None
        for r in rows:
            gun = r["kocluk_gunu"]
            saat = r["kocluk_saati"] or "??:??"
            ad = f"{r['ad']} {r['soyad']}"
            tel = r["ogr_tel"] or ""
            
            # Telefon temizle
            tel_clean = "".join(filter(str.isdigit, tel))
            if tel_clean.startswith("0"): tel_clean = "9" + tel_clean
            elif not tel_clean.startswith("90") and len(tel_clean)==10: tel_clean = "90" + tel_clean
            
            if gun != current_day:
                if current_day is not None: html += "</div>" # Close previous day block
                html += f'<div class="day-block"><div class="day-header">{gun}</div>'
                current_day = gun
            
            html += f"""
            <div class="card">
                <div><span class="time">{saat}</span> <span class="name">{ad}</span></div>
                <div style="margin-top:4px; color:#555; font-size:11px;">
                   <span class="cb"></span>Ödev Kontrol &nbsp; <span class="cb"></span>Yeni Plan
                </div>
            """
            
            if tel:
                html += f"""
                <div class="actions">
                    📞 <a href="tel:{tel}">Ara</a> &nbsp;|&nbsp; 
                    💬 <a href="https://wa.me/{tel_clean}">WhatsApp</a>
                </div>
                """
            html += "</div>"
            
        if current_day is not None: html += "</div>"
        html += "</body></html>"

        # 3. PDF Kaydet
        from PyQt6.QtGui import QTextDocument, QPageSize
        doc = QTextDocument()
        doc.setHtml(html)
        
        # Mobil oranlı sayfa (örn 10cm x 18cm gibi veya A5, ama PDF okuyucular genelde fit width yapar)
        # Direkt A4 yapıp kenarlıkları geniş tutabiliriz veya özel boyut.
        # A4 standarttır, her yerde açılır.
        from PyQt6.QtPrintSupport import QPrinter
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(fn)
        # Dikey telefon için dar sayfa daha şık durur ama A4 güvenlidir. 
        # Biz A4 kullanalım, yazıcıdan çıktı almak isteyen de olur.
        doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.Point).size())) # type: ignore
        doc.print(printer)
        
        QMessageBox.information(self, "Başarılı", f"Cep programı oluşturuldu:\n{fn}\n\nBu dosyayı telefonunuza gönderip kullanabilirsiniz.")


# Lokal test
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = RaporlarFormu()
    w.resize(1200, 720)
    w.show()
    sys.exit(app.exec())

