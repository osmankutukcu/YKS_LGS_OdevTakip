# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy,
    QLineEdit, QPushButton, QComboBox, QFileDialog, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QIcon, QPainter, QPageLayout
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

# Matplotlib – PyQt6 backend
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except ImportError:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib as mpl

from datetime import date, timedelta
import db

# ---------------- Global Matplotlib stili ----------------
PRIMARY = "#2563eb"   # mavi
ACCENT  = "#0f766e"   # yeşil
WARNING = "#f97316"   # turuncu
DANGER  = "#b91c1c"   # kırmızı
MUTED   = "#64748b"   # gri

mpl.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 10,
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.linewidth": 0.4,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "#f8fafc",
    "axes.facecolor": "#ffffff",
})

# ---------------- Tarih yardımcıları ----------------
def _week_bounds(d: date):
    s = d - timedelta(days=d.weekday())  # Pazartesi
    return s, s + timedelta(days=6)


# ---------------- Normalize SQL ----------------
def _normalized_satir_sql():
    # (senin eski koddakiyle birebir)
    return r"""
    WITH raw AS (
        SELECT s.ogrenci_id, s.kume_id,
               DATE(COALESCE(s.tarih, k.bitis_tarihi)) AS gun,
               COALESCE(s.durum, 'devam') AS durum,
               k.bitis_tarihi AS bitis
        FROM odev_satir s
        LEFT JOIN odev_kume k ON k.id = s.kume_id
        UNION ALL
        SELECT o.ogrenci_id, o.kume_id,
               DATE(k.bitis_tarihi) AS gun,
               COALESCE(o.durum, 'devam') AS durum,
               k.bitis_tarihi AS bitis
        FROM odev o
        LEFT JOIN odev_kume k ON k.id = o.kume_id
    ),
    clean AS (
        SELECT
          ogrenci_id, kume_id, gun, bitis,
          LOWER(
            TRIM(
              REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                REPLACE(durum,'İ','i'),'I','i'),'Ş','s'),'Ğ','g'),'Ü','u'),'Ö','o'),'Ç','c')
            )
          ) AS d
        FROM raw
        WHERE gun IS NOT NULL
    ),
    canon AS (
        SELECT
          ogrenci_id, kume_id, gun, bitis,
          CASE
            WHEN d IN ('tamam','yapildi','yapıldı','ok','done','bitti','bitirildi','tamamlandi','tamamlandı','✓','✔','okey') THEN 'tamam'
            WHEN d LIKE '%bitti%' OR d LIKE '%tamam%' OR d LIKE 'ok' THEN 'tamam'
            WHEN d IN ('devam','todo','acik','açik','açık','kaldi','kaldı','bekliyor','yapilacak','yapılacak','eksik','acik-gorev') THEN 'devam'
            WHEN d LIKE '%todo%' OR d LIKE '%acik%' OR d LIKE '%açik%' OR d LIKE '%açık%' OR d LIKE '%kald%' OR d LIKE '%eksik%' THEN 'devam'
            ELSE 'devam'
          END AS durum
        FROM clean
    ),
    kume_ozet AS (
        SELECT
          ogrenci_id, gun, kume_id,
          SUM(CASE WHEN durum='tamam' THEN 1 ELSE 0 END) AS s_tamam,
          SUM(CASE WHEN durum='devam' THEN 1 ELSE 0 END) AS s_devam,
          MIN(bitis) AS bitis
        FROM canon
        GROUP BY ogrenci_id, gun, kume_id
    ),
    kume_sinif AS (
        SELECT
          ogrenci_id, gun, kume_id, bitis,
          CASE WHEN s_tamam>0 AND s_devam=0 THEN 1 ELSE 0 END AS is_tamam,
          CASE WHEN s_tamam>0 AND s_devam>0 THEN 1 ELSE 0 END AS is_kismi,
          CASE WHEN s_tamam=0 AND s_devam>0 THEN 1 ELSE 0 END AS is_yapilmadi
        FROM kume_ozet
    )
    SELECT * FROM kume_sinif
    """


# =====================================================
#                    D I A L O G
# =====================================================
class OgrenciDetayDialog(QDialog):
    """
    Üst bar:
      • Öğrenci seçimi
      • Hızlı arama
      • Analizleri Yenile • PDF • Yazdır

    Sağ tık menüsü:
      • Günlük ilerleme aralığı: 7 / 14 / 30 gün
      • Haftalık trend: Adet / Yüzde
    """
    def __init__(self, ogrenci_id=None, adsoyad="", parent=None):
        super().__init__(parent)
        self.ogrenci_id = int(ogrenci_id) if ogrenci_id else None
        self.adsoyad = adsoyad or ""

        # Sağ tık ayarları
        self._range_days = 30        # 7 / 14 / 30
        self._weekly_mode = "count"  # "count" | "percent"

        self.setWindowTitle("Öğrenci Detayı")
        self.resize(1024, 720)
        self._apply_modern_visuals()

    def _apply_modern_visuals(self):
        self.setStyleSheet("""
            QDialog, QWidget { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; background-color: #f8fafc; color: #1e293b; }
            QLabel { font-weight: 500; color: #334155; }
            
            QLineEdit, QComboBox { border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px; background: white; min-height: 24px; }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #2563eb; }
            
            /* Buttons */
            QPushButton { border-radius: 6px; padding: 6px 12px; font-weight: 600; background: white; border: 1px solid #cbd5e1; color: #475569; }
            QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
            
            QPushButton#btnPrimary { background-color: #2563eb; color: white; border: 1px solid #2563eb; }
            QPushButton#btnPrimary:hover { background-color: #1d4ed8; }
            
            QPushButton#btnPdf { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
            QPushButton#btnPdf:hover { background-color: #fecaca; }

            QPushButton#btnInfo { background-color: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
            QPushButton#btnInfo:hover { background-color: #dbeafe; }
        """)

        root = QVBoxLayout(self)

        # Başlık
        self._lblTitle = QLabel("🧠 " + (self.adsoyad or "Öğrenci seçiniz"))
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        self._lblTitle.setFont(f)
        self._lblTitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._lblTitle)

        # Üst kontrol barı
        bar = QHBoxLayout()
        self.cmbStudents = QComboBox()
        self.cmbStudents.setEditable(True)
        self.cmbStudents.lineEdit().setPlaceholderText("Öğrenci seç / yaz…")
        self.cmbStudents.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.txtAra = QLineEdit()
        self.txtAra.setPlaceholderText("Ad Soyad ara (en az 2 harf)…")

        self.btnYenile = QPushButton("🔄 Analizleri Yenile")
        self.btnYenile.setObjectName("btnPrimary")
        # self.btnYenile.setIcon(QIcon.fromTheme("view-refresh")) # Removed icon to use Emoji

        self.btnPdf = QPushButton("📄 PDF'ye Aktar")
        self.btnPdf.setObjectName("btnPdf")
        self.btnPrint = QPushButton("🖨️ Yazdır")
        self.btnPrint.setObjectName("btnInfo")

        bar.addWidget(QLabel("Öğrenci:"))
        bar.addWidget(self.cmbStudents, 2)
        bar.addSpacing(12)
        bar.addWidget(QLabel("Ara:"))
        bar.addWidget(self.txtAra, 2)
        bar.addStretch(1)
        bar.addWidget(self.btnYenile)
        bar.addWidget(self.btnPdf)
        bar.addWidget(self.btnPrint)
        root.addLayout(bar)

        # ===== Öğrenci Yönetici Snapshot Bandı =====
        self.profile_card = QWidget()
        self.profile_card.setObjectName("ProfileCard")
        self.profile_card.setStyleSheet("""
            QWidget#ProfileCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #334155);
                border-radius: 8px;
            }
            QWidget#ProfileCard QLabel {
                background: transparent;
                border: none;
                color: #f8fafc;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        p_lay = QHBoxLayout(self.profile_card)
        p_lay.setContentsMargins(14, 8, 14, 8)
        self.lbl_prof_group = QLabel("🏷️ Grup: -")
        self.lbl_prof_target = QLabel("🎯 Hedef: -")
        self.lbl_prof_coach = QLabel("📅 Koçluk: -")
        self.lbl_prof_status = QLabel("🟢 Aktif")
        p_lay.addWidget(self.lbl_prof_group)
        p_lay.addSpacing(15)
        p_lay.addWidget(self.lbl_prof_target)
        p_lay.addSpacing(15)
        p_lay.addWidget(self.lbl_prof_coach)
        p_lay.addStretch()
        p_lay.addWidget(self.lbl_prof_status)
        root.addWidget(self.profile_card)

        # ===== KPI Özet Kartları =====
        kpi_bar = QHBoxLayout()
        root.addLayout(kpi_bar)

        def _make_kpi_label(title: str, val_color="#2563eb"):
            w = QWidget(self)
            lay = QVBoxLayout(w)
            lay.setContentsMargins(8, 8, 8, 8)

            lbl_title = QLabel(title)
            f_small = QFont()
            f_small.setPointSize(9)
            lbl_title.setFont(f_small)
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_title.setStyleSheet("color: #64748b; font-weight: 600;")

            lbl_value = QLabel("-")
            f_big = QFont()
            f_big.setPointSize(16)
            f_big.setBold(True)
            lbl_value.setFont(f_big)
            lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lay.addWidget(lbl_title)
            lay.addWidget(lbl_value)

            w.setStyleSheet(f"""
                QWidget {{
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                }}
                QLabel {{
                    background: transparent;
                    border: none;
                }}
            """)
            lbl_value.setStyleSheet(f"color: {val_color};")
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            return w, lbl_title, lbl_value

        card1, self.lblKpiAvgTitle, self.lblKpiAvg = _make_kpi_label("Son X Günde Ortalama İlerleme", "#2563eb")
        card2, self.lblKpiWeekTitle, self.lblKpiWeek = _make_kpi_label("Bu Hafta Tamamlanan Küme", "#10b981")
        card3, self.lblKpiMissingTitle, self.lblKpiMissing = _make_kpi_label("Tamamlanmamış Ödev Sayısı", "#ef4444")
        card4, self.lblKpiLevelTitle, self.lblKpiLevel = _make_kpi_label("Koçluk Değerlendirmesi", "#8b5cf6")

        kpi_bar.addWidget(card1)
        kpi_bar.addWidget(card2)
        kpi_bar.addWidget(card3)
        kpi_bar.addWidget(card4)

        # 2x2 grafik alanı
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        root.addLayout(row1)
        root.addLayout(row2)

        self.fig1 = Figure(figsize=(5, 3), dpi=100)
        self.cv1 = FigureCanvas(self.fig1)
        self.fig2 = Figure(figsize=(5, 3), dpi=100)
        self.cv2 = FigureCanvas(self.fig2)
        self.fig3 = Figure(figsize=(5, 3), dpi=100)
        self.cv3 = FigureCanvas(self.fig3)
        self.fig4 = Figure(figsize=(5, 3.8), dpi=100)
        self.cv4 = FigureCanvas(self.fig4)

        # Grafikler için sağ tık menüsü (her canvas'ta)
        for cv in (self.cv1, self.cv2, self.cv3, self.cv4):
            cv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            cv.customContextMenuRequested.connect(self._show_context_menu)

        # İstersen dialog'un boş alanında da çalışsın
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._plot_wrappers = []

        def _wrap(canvas):
            w = QWidget(self)
            lay = QVBoxLayout(w)
            lay.setContentsMargins(4, 4, 4, 4)
            lay.addWidget(canvas)
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._plot_wrappers.append(w)
            return w

        row1.addWidget(_wrap(self.cv1))
        row1.addWidget(_wrap(self.cv2))
        row2.addWidget(_wrap(self.cv3))
        row2.addWidget(_wrap(self.cv4))

        # Alt özet
        self._lblSummary = QLabel("")
        self._lblSummary.setWordWrap(True)
        self._lblSummary.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._lblSummary)

        # Sinyaller
        self.btnYenile.clicked.connect(self._yenile_analiz)
        self.btnPdf.clicked.connect(self._export_pdf)
        self.btnPrint.clicked.connect(self._print_report)

        self.txtAra.returnPressed.connect(self._ara_ve_sec)
        self.txtAra.textChanged.connect(self._ara_otomatik)
        self.cmbStudents.activated.connect(self._combo_secildi)

        # Öğrencileri doldur ve ilk çizimi yap
        self._fill_students(initial_id=self.ogrenci_id)
        self._load_and_draw()

    # ---------------- Sağ tık menüsü (ortak) ----------------
    def _show_context_menu(self, pos: QPoint):
        """Hem dialog hem de canvas'lar için sağ tık menüsü."""
        sender = self.sender()
        if hasattr(sender, "mapToGlobal"):
            global_pos = sender.mapToGlobal(pos)
        else:
            global_pos = self.mapToGlobal(pos)

        menu = QMenu(self)

        # Günlük aralık menüsü
        sub_range = menu.addMenu("📈 Günlük İlerleme Aralığı")
        act7 = sub_range.addAction("Son 7 Gün")
        act14 = sub_range.addAction("Son 14 Gün")
        act30 = sub_range.addAction("Son 30 Gün")

        for act, val in ((act7, 7), (act14, 14), (act30, 30)):
            act.setCheckable(True)
            if self._range_days == val:
                act.setChecked(True)

        # Haftalık görünüm menüsü
        sub_week = menu.addMenu("🔁 Haftalık Trend Görünümü")
        actCount = sub_week.addAction("Adet")
        actPercent = sub_week.addAction("Yüzde")

        for act, mode in ((actCount, "count"), (actPercent, "percent")):
            act.setCheckable(True)
            if self._weekly_mode == mode:
                act.setChecked(True)

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen in (act7, act14, act30):
            self._range_days = {act7: 7, act14: 14, act30: 30}[chosen]
            self._load_and_draw()
        elif chosen in (actCount, actPercent):
            self._weekly_mode = "count" if chosen is actCount else "percent"
            self._load_and_draw()

    # ---------------- Öğrenci listesi ----------------
    def _fill_students(self, initial_id=None):
        self.cmbStudents.blockSignals(True)
        self.cmbStudents.clear()

        con = db.get_conn()
        rows = []
        try:
            rows = con.execute(
                "SELECT id, ad, soyad FROM ogrenci ORDER BY ad, soyad"
            ).fetchall()
        finally:
            con.close()

        selected_idx = -1
        for i, r in enumerate(rows):
            name = f"{r['ad']} {r['soyad']}".strip()
            self.cmbStudents.addItem(name, int(r["id"]))
            if initial_id and int(r["id"]) == int(initial_id):
                selected_idx = i

        if selected_idx >= 0:
            self.cmbStudents.setCurrentIndex(selected_idx)
            self._set_student(
                int(rows[selected_idx]["id"]),
                f"{rows[selected_idx]['ad']} {rows[selected_idx]['soyad']}",
                redraw=False,
            )
        elif rows:
            self.ogrenci_id = None
            self._lblTitle.setText("🧠 Öğrenci seçiniz")

        self.cmbStudents.blockSignals(False)

    def _combo_secildi(self, index):
        oid = self.cmbStudents.itemData(index)
        adsoyad = self.cmbStudents.itemText(index)
        if oid:
            self._set_student(int(oid), adsoyad)

    # ---------------- Arama ----------------
    def _ara_ve_sec(self):
        q = (self.txtAra.text() or "").strip().lower()
        if len(q) < 2:
            return
        con = db.get_conn()
        try:
            row = con.execute(
                """
                SELECT id, ad, soyad
                FROM ogrenci
                WHERE lower(ad || ' ' || soyad) LIKE ?
                ORDER BY ad, soyad
                LIMIT 1
            """,
                (f"%{q}%",),
            ).fetchone()
            if row:
                self._set_student(
                    int(row["id"]), f"{row['ad']} {row['soyad']}"
                )
        finally:
            con.close()

    def _ara_otomatik(self, _):
        q = (self.txtAra.text() or "").strip().lower()
        if len(q) < 3:
            return
        con = db.get_conn()
        try:
            rows = con.execute(
                """
                SELECT id, ad, soyad
                FROM ogrenci
                WHERE lower(ad || ' ' || soyad) LIKE ?
                ORDER BY ad, soyad
                LIMIT 2
            """,
                (f"%{q}%",),
            ).fetchall()
            if len(rows) == 1:
                r = rows[0]
                self._set_student(
                    int(r["id"]), f"{r['ad']} {r['soyad']}"
                )
        finally:
            con.close()

    def _sync_combo_to_current(self):
        if not self.ogrenci_id:
            return
        for i in range(self.cmbStudents.count()):
            if int(self.cmbStudents.itemData(i) or 0) == int(self.ogrenci_id):
                self.cmbStudents.blockSignals(True)
                self.cmbStudents.setCurrentIndex(i)
                self.cmbStudents.blockSignals(False)
                break

    # ---------------- Durum değiştirme ----------------
    def _set_student(self, oid, adsoyad, redraw=True):
        self.ogrenci_id = int(oid)
        self.adsoyad = adsoyad
        self._lblTitle.setText("🧠 " + adsoyad)
        self._sync_combo_to_current()
        if redraw:
            self._load_and_draw()

    # ---------------- Analizleri Yenile ----------------
    def _yenile_analiz(self):
        try:
            from utils import analytics_engine as ae
        except Exception as e:
            QMessageBox.critical(
                self, "Modül Hatası", f"analytics_engine yüklenemedi:\n{e}"
            )
            return

        con = db.get_conn()
        try:
            ae.rebuild_all(con)
        finally:
            con.close()

        self._load_and_draw()

    # ---------------- Ortak render (PDF & yazdır) ----------------
    def _render_full_page(self, printer: QPrinter):
        painter = QPainter(printer)

        # PyQt6: pageRect birim parametresi ister
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)

        w = self.width()
        h = self.height()

        if w == 0 or h == 0:
            self.render(painter)
            painter.end()
            return

        scale = min(page_rect.width() / w, page_rect.height() / h)

        # Ortala
        x = page_rect.x() + (page_rect.width() - w * scale) / 2
        y = page_rect.y() + (page_rect.height() - h * scale) / 2

        painter.translate(x, y)
        painter.scale(scale, scale)

        self.render(painter)
        painter.end()

    # ---------------- PDF & Yazdır ----------------
    def _export_pdf(self):
        if not self.ogrenci_id:
            QMessageBox.warning(
                self, "Öğrenci Seçilmedi", "Önce bir öğrenci seçmelisiniz."
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "PDF olarak kaydet", "", "PDF Dosyası (*.pdf)"
        )
        if not filename:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(filename)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)

        self._render_full_page(printer)

        QMessageBox.information(
            self, "PDF Kaydedildi", "Rapor PDF olarak kaydedildi."
        )

    def _print_report(self):
        if not self.ogrenci_id:
            QMessageBox.warning(
                self, "Öğrenci Seçilmedi", "Önce bir öğrenci seçmelisiniz."
            )
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._render_full_page(printer)

    # ---------------- Data & Charts ----------------
    def _load_and_draw(self):
        # Seçim yoksa placeholder
        if not self.ogrenci_id:
            for fig, cv in (
                (self.fig1, self.cv1),
                (self.fig2, self.cv2),
                (self.fig3, self.cv3),
                (self.fig4, self.cv4),
            ):
                fig.clear()
                ax = fig.add_subplot(111)
                ax.text(
                    0.5, 0.5, "Öğrenci seçiniz",
                    ha="center", va="center"
                )
                ax.set_axis_off()
                fig.tight_layout()
                cv.draw()
            self._lblSummary.setText("")
            self.lblKpiAvg.setText("-")
            self.lblKpiWeek.setText("-")
            self.lblKpiMissing.setText("-")
            if hasattr(self, 'lblKpiLevel'):
                self.lblKpiLevel.setText("-")
            if hasattr(self, 'lbl_prof_group'):
                self.lbl_prof_group.setText("🏷️ Grup: -")
                self.lbl_prof_target.setText("🎯 Hedef: -")
                self.lbl_prof_coach.setText("📅 Koçluk: -")
            return

        con = db.get_conn()
        try:
            # Öğrenci Profil Bilgisi
            row_st = con.execute("""
                SELECT ana_grup, alt_grup, hedef_bolum, hedef_tyt, hedef_ayt, hedef_lgs,
                       kocluk_gunu, kocluk_saati, aktif
                FROM ogrenci WHERE id=?
            """, (self.ogrenci_id,)).fetchone()
            if row_st and hasattr(self, 'lbl_prof_group'):
                grp_txt = f"🏷️ Grup: {row_st['ana_grup'] or 'Genel'}"
                if row_st['alt_grup']:
                    grp_txt += f" ({row_st['alt_grup']})"
                self.lbl_prof_group.setText(grp_txt)

                target_parts = []
                if row_st['hedef_bolum']: target_parts.append(str(row_st['hedef_bolum']))
                if row_st['hedef_tyt']: target_parts.append(f"TYT: {row_st['hedef_tyt']}")
                if row_st['hedef_ayt']: target_parts.append(f"AYT: {row_st['hedef_ayt']}")
                if row_st['hedef_lgs']: target_parts.append(f"LGS: {row_st['hedef_lgs']}")
                target_str = " • ".join(target_parts) if target_parts else "Belirtilmedi"
                self.lbl_prof_target.setText(f"🎯 Hedef: {target_str}")

                coach_parts = []
                if row_st['kocluk_gunu']: coach_parts.append(str(row_st['kocluk_gunu']))
                if row_st['kocluk_saati']: coach_parts.append(str(row_st['kocluk_saati']))
                self.lbl_prof_coach.setText(f"📅 Koçluk: {' '.join(coach_parts) if coach_parts else 'Belirtilmedi'}")
                self.lbl_prof_status.setText("🟢 Aktif" if row_st['aktif'] != 0 else "⚪ Pasif")

            today = date.today()
            w_s, w_e = _week_bounds(today)
            m_s = today - timedelta(days=self._range_days - 1)
            m_e = today

            # 1) Günlük ilerleme
            daily = con.execute(
                """
                SELECT gun,
                       100.0 * CAST(COALESCE(tamam,0) AS REAL) /
                       NULLIF(COALESCE(tamam,0)+COALESCE(kismi,0)+COALESCE(yapilmadi,0),0) AS ilerleme_pct
                FROM ogrenci_perf_gunluk
                WHERE ogrenci_id=? AND date(gun) BETWEEN date(?) AND date(?)
                ORDER BY date(gun)
            """,
                (self.ogrenci_id, m_s.isoformat(), m_e.isoformat()),
            ).fetchall()

            if not daily:
                daily = con.execute(
                    f"""
                    WITH ks AS ({_normalized_satir_sql()}),
                    g AS (
                      SELECT gun,
                             SUM(is_tamam) AS tamam,
                             SUM(is_kismi) AS kismi,
                             SUM(is_yapilmadi) AS yapilmadi
                      FROM ks
                      WHERE ogrenci_id=? AND date(gun) BETWEEN date(?) AND date(?)
                      GROUP BY gun
                    )
                    SELECT gun,
                           100.0 * CAST(COALESCE(tamam,0) AS REAL) /
                           NULLIF(COALESCE(tamam,0)+COALESCE(kismi,0)+COALESCE(yapilmadi,0),0) AS ilerleme_pct
                    FROM g
                    ORDER BY gun
                """,
                    (self.ogrenci_id, m_s.isoformat(), m_e.isoformat()),
                ).fetchall()

            # 2) Haftalık toplamlar
            weekly = con.execute(
                """
                SELECT
                  SUM(tamam)   AS tamam,
                  SUM(kismi)   AS kismi,
                  SUM(yapilmadi) AS yapilmadi
                FROM ogrenci_perf_gunluk
                WHERE ogrenci_id=? AND date(gun) BETWEEN date(?) AND date(?)
            """,
                (self.ogrenci_id, w_s.isoformat(), w_e.isoformat()),
            ).fetchone()

            if (not weekly) or (
                weekly["tamam"] is None
                and weekly["kismi"] is None
                and weekly["yapilmadi"] is None
            ):
                weekly = con.execute(
                    f"""
                    WITH ks AS ({_normalized_satir_sql()})
                    SELECT
                      SUM(is_tamam)    AS tamam,
                      SUM(is_kismi)    AS kismi,
                      SUM(is_yapilmadi) AS yapilmadi
                    FROM ks
                    WHERE ogrenci_id=? AND date(gun) BETWEEN date(?) AND date(?)
                """,
                    (self.ogrenci_id, w_s.isoformat(), w_e.isoformat()),
                ).fetchone()

            # 3) Geciken günler
            geciken = con.execute(
                """
                SELECT STRFTIME('%w', gun) AS weekday,
                       SUM(geciken) AS c
                  FROM ogrenci_perf_gunluk
                 WHERE ogrenci_id=? AND date(gun) BETWEEN date(?) AND date(?)
                 GROUP BY STRFTIME('%w', gun)
                 HAVING SUM(geciken) > 0
                 ORDER BY c DESC
            """,
                (self.ogrenci_id, m_s.isoformat(), m_e.isoformat()),
            ).fetchall()

            if not geciken:
                geciken = con.execute(
                    f"""
                    WITH ks AS ({_normalized_satir_sql()})
                    SELECT STRFTIME('%w', gun) AS weekday, COUNT(*) AS c
                    FROM ks
                    WHERE ogrenci_id=? 
                      AND (is_yapilmadi=1 OR is_kismi=1)
                      AND bitis IS NOT NULL AND date(bitis) < date('now')
                      AND date(gun) BETWEEN date(?) AND date(?)
                    GROUP BY STRFTIME('%w', gun)
                    ORDER BY c DESC
                """,
                    (self.ogrenci_id, m_s.isoformat(), m_e.isoformat()),
                ).fetchall()

            # 4) Ders kırılımı
            ders_rows = []
            try:
                ders_rows = con.execute(
                    """
                    WITH src AS (
                        SELECT ogrenci_id, ders,
                               LOWER(COALESCE(durum,'devam')) AS durum
                          FROM odev
                         WHERE ogrenci_id=?
                        UNION ALL
                        SELECT ogrenci_id, ders,
                               LOWER(COALESCE(durum,'devam')) AS durum
                          FROM odev_satir
                         WHERE ogrenci_id=?
                    )
                    SELECT COALESCE(ders,'Bilinmiyor') AS ders,
                           COUNT(*) AS kac
                      FROM src
                     WHERE durum NOT IN ('tamam','yapildi','yapıldı','ok','done','bitti',
                                         'bitirildi','tamamlandi','tamamlandı')
                     GROUP BY ders
                     ORDER BY kac DESC
                     LIMIT 8
                """,
                    (self.ogrenci_id, self.ogrenci_id),
                ).fetchall()
            except Exception:
                ders_rows = []
        finally:
            con.close()

        # ---- Çizim 1: Günlük İlerleme
        self.fig1.clear()
        ax = self.fig1.add_subplot(111)
        xs = [r["gun"] for r in daily]
        ys = [float(r["ilerleme_pct"] or 0) for r in daily]
        if xs:
            ax.plot(
                range(len(xs)),
                ys,
                marker="o",
                linewidth=1.8,
                color=PRIMARY,
            )
            step = max(1, len(xs) // 6)
            ax.set_xticks(list(range(0, len(xs), step)))
            ax.set_xticklabels(
                [xs[i] for i in range(0, len(xs), step)],
                rotation=30,
                ha="right",
            )
            ax.set_ylim(0, 100)
            ax.set_ylabel("Tamamlanma (%)")

            # Hedef çizgisi (ör: %80)
            hedef = 80
            ax.axhline(hedef, linestyle=":", linewidth=0.8, color=MUTED)
            ax.text(
                0.99,
                hedef / 100.0,
                " Hedef %80",
                ha="right",
                va="bottom",
                transform=ax.get_yaxis_transform(),
                color=MUTED,
                fontsize=8,
            )

            ax.set_title(f"📈 Günlük İlerleme (%) – Son {self._range_days} Gün")
        else:
            ax.text(0.5, 0.5, "Veri yok", ha="center", va="center")
            ax.set_axis_off()
        self.fig1.tight_layout(pad=1.2)
        self.cv1.draw()

        # ---- Çizim 2: Haftalık Trend
        self.fig2.clear()
        ax2 = self.fig2.add_subplot(111)
        t = int(weekly["tamam"] or 0) if weekly else 0
        k = int(weekly["kismi"] or 0) if weekly else 0
        yv = int(weekly["yapilmadi"] or 0) if weekly else 0

        if self._weekly_mode == "percent":
            total = t + k + yv
            if total == 0:
                ax2.text(
                    0.5,
                    0.5,
                    "Bu hafta için veri yok",
                    ha="center",
                    va="center",
                )
                ax2.set_axis_off()
            else:
                perc = [
                    100 * t / total,
                    100 * k / total,
                    100 * yv / total,
                ]
                colors = [ACCENT, WARNING, DANGER]
                bars = ax2.bar(
                    ["Tamam", "Kısmi", "Yapılmadı"],
                    perc,
                    color=colors,
                )
                ax2.set_ylim(0, 100)
                ax2.set_ylabel("Yüzde (%)")
                ax2.set_title("🔁 Haftalık Trend (Pzt–Paz) – Yüzde")
                for label, b, cnt, p in zip(
                    ["Tamam", "Kısmi", "Yapılmadı"], bars, [t, k, yv], perc
                ):
                    ax2.text(
                        b.get_x() + b.get_width() / 2.0,
                        p + 2,
                        f"{cnt} (%{p:.0f})",
                        ha="center",
                        va="bottom",
                    )
        else:
            if t + k + yv == 0:
                ax2.text(
                    0.5,
                    0.5,
                    "Bu hafta için veri yok",
                    ha="center",
                    va="center",
                )
                ax2.set_axis_off()
            else:
                vals = [t, k, yv]
                colors = [ACCENT, WARNING, DANGER]
                bars = ax2.bar(
                    ["Tamam", "Kısmi", "Yapılmadı"],
                    vals,
                    color=colors,
                )
                maxv = max(vals)
                ax2.set_ylim(0, maxv * 1.25)
                ax2.set_ylabel("Küme Sayısı")
                ax2.set_title("🔁 Haftalık Trend (Pzt–Paz)")
                for b, v in zip(bars, vals):
                    ax2.text(
                        b.get_x() + b.get_width() / 2.0,
                        v + maxv * 0.03,
                        str(v),
                        ha="center",
                        va="bottom",
                    )

        self.fig2.tight_layout(pad=1.2)
        self.cv2.draw()

        # ---- Çizim 3: En çok geciken gün
        self.fig3.clear()
        ax3 = self.fig3.add_subplot(111)
        wd_map = {
            "0": "Paz",
            "1": "Pzt",
            "2": "Sal",
            "3": "Çar",
            "4": "Per",
            "5": "Cum",
            "6": "Cmt",
        }
        labels = [wd_map.get(str(r["weekday"]), str(r["weekday"])) for r in geciken]
        vals = [int(r["c"]) for r in geciken]
        if labels:
            bars3 = ax3.bar(labels, vals, color=WARNING)
            maxv3 = max(vals)
            ax3.set_ylim(0, maxv3 * 1.25 if maxv3 > 0 else 1)
            ax3.set_ylabel("Geciken Küme")
            ax3.set_title(f"⏰ En Çok Geciken Gün (Son {self._range_days} Gün)")
            for b, v in zip(bars3, vals):
                ax3.text(
                    b.get_x() + b.get_width() / 2.0,
                    v + (maxv3 * 0.03 if maxv3 > 0 else 0.1),
                    str(v),
                    ha="center",
                    va="bottom",
                )
        else:
            ax3.text(
                0.5,
                0.5,
                "Gecikme verisi yok",
                ha="center",
                va="center",
            )
            ax3.set_axis_off()
        self.fig3.tight_layout(pad=1.2)
        self.cv3.draw()

        # ---- Çizim 4: Ders kırılımı
        self.fig4.clear()
        ax4 = self.fig4.add_subplot(111)
        if ders_rows:
            dlabels = [r["ders"] for r in ders_rows]
            dvals = [int(r["kac"]) for r in ders_rows]
            ax4.barh(dlabels, dvals, color=DANGER)
            maxv4 = max(dvals)
            ax4.set_xlim(0, maxv4 * 1.25 if maxv4 > 0 else 1)
            ax4.set_xlabel("Tamamlanmamış Ödev")
            ax4.set_title("Tamamlanmamış Ödevlerin Ders Kırılımı")
            for i, v in enumerate(dvals):
                ax4.text(
                    v + (maxv4 * 0.03 if maxv4 > 0 else 0.1),
                    i,
                    str(v),
                    va="center",
                )
        else:
            dvals = []
            ax4.text(
                0.5,
                0.5,
                "Ders kırılımı verisi yok / şemada 'ders' alanı yok.",
                ha="center",
                va="center",
            )
            ax4.set_axis_off()
        self.fig4.tight_layout(pad=1.2)
        self.cv4.draw()

        # ---- KPI kartları
        avg_pct = round(sum(ys) / len(ys), 1) if ys else 0.0
        total_delay_days = sum(vals) if vals else 0
        t_count = t
        k_count = k
        y_count = yv
        incomplete_total = sum(dvals) if ders_rows else 0

        self.lblKpiAvg.setText(f"% {avg_pct:.1f}")
        self.lblKpiWeek.setText(str(t_count))
        self.lblKpiMissing.setText(str(incomplete_total))
        self.lblKpiAvgTitle.setText(f"Son {self._range_days} Günde Ortalama İlerleme")
        if hasattr(self, 'lblKpiLevel'):
            if avg_pct >= 85:
                self.lblKpiLevel.setText("🌟 Mükemmel")
            elif avg_pct >= 70:
                self.lblKpiLevel.setText("✅ Başarılı")
            elif avg_pct >= 50:
                self.lblKpiLevel.setText("⚠️ Sınırda")
            else:
                self.lblKpiLevel.setText("🚨 Riskli")

        # ---- AKILLI ANALİZ KARTI (Eski basit özet yerine)
        # Önce eski özeti temizleyelim veya gizleyelim (kodu basitleştirmek için update ediyoruz)
        self._lblSummary.setVisible(False)
        
        # Eğer daha önce eklemediysek ekleyelim
        if not hasattr(self, "_smart_panel"):
            self._smart_panel = SmartInsightPanel()
            layout_parent = self._lblSummary.parentWidget().layout()
            layout_parent.addWidget(self._smart_panel)
            
        # Verileri analiz et ve panele gönder
        insights = []
        
        # 1. Başarı Durumu
        if avg_pct >= 85:
            insights.append(("🌟", "Mükemmel İlerleme", "Öğrencimiz son dönemde çok istikrarlı ve başarılı."))
        elif avg_pct >= 70:
            insights.append(("✅", "İyi Durumda", "Genel ilerleme tatmin edici düzeyde."))
        elif avg_pct >= 50:
            insights.append(("⚠️", "Dikkat", "Başarı ortalaması sınırdır, takviye gerekebilir."))
        else:
            insights.append(("🚨", "Riskli", "Ödev yapma alışkanlığında ciddi düşüş var, görüşme önerilir."))
            
        # 2. Ders Bazlı Analiz (En çok eksik olan ders)
        if ders_rows:
            worst_lesson = ders_rows[0]["ders"]
            worst_count = ders_rows[0]["kac"]
            insights.append(("books", f"{worst_lesson} Dersi", f"En çok eksik ödev ({worst_count} adet) bu derste birikmiş."))
            
        # 3. Haftalık Trend
        trend_msg = ""
        total_week = t_count + k_count + y_count
        if total_week > 0:
            completion_rate = (t_count / total_week) * 100
            if completion_rate > 80:
                trend_msg = "Bu hafta harika bir performans sergiliyor."
            elif completion_rate < 40:
                trend_msg = "Bu hafta performans düşüklüğü gözlemleniyor."
        
        if trend_msg:
             insights.append(("trend", "Haftalık Trend", trend_msg))
             
        self._smart_panel.update_insights(insights)

class SmartInsightPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget#MainFrame {
                background: #fdfeff;
                border: 1px solid #dbeafe;
                border-radius: 12px;
                border-left: 6px solid #6366f1;
            }
            QLabel { color: #334155; }
        """)
        
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        
        self.frame = QWidget()
        self.frame.setObjectName("MainFrame")
        self.flay = QVBoxLayout(self.frame)
        self.flay.setContentsMargins(16, 16, 16, 16)
        
        header = QLabel("💡 Yapay Zeka Destekli Analiz")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #4338ca; margin-bottom: 8px;")
        self.flay.addWidget(header)
        
        self.content_lay = QVBoxLayout()
        self.flay.addLayout(self.content_lay)
        
        self.lay.addWidget(self.frame)
        
    def update_insights(self, items):
        # Clear old items
        while self.content_lay.count():
            child = self.content_lay.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        if not items:
            self.content_lay.addWidget(QLabel("Henüz yeterli veri yok."))
            return

        for icon, title, desc in items:
            row = QWidget()
            rlay = QHBoxLayout(row)
            rlay.setContentsMargins(0, 4, 0, 4)
            rlay.setSpacing(10)
            
            # Icon Wrapper
            lbl_icon = QLabel(icon if len(icon) < 5 else "📌") # Emoji or simple char
            if icon == "books": lbl_icon.setText("📚")
            if icon == "trend": lbl_icon.setText("📈")
            
            lbl_icon.setStyleSheet("font-size: 18px; background: #e0e7ff; border-radius: 8px; padding: 6px;")
            lbl_icon.setFixedSize(36, 36)
            lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Text
            vtext = QVBoxLayout()
            vtext.setSpacing(2)
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e293b;")
            lbl_d = QLabel(desc)
            lbl_d.setStyleSheet("font-size: 12px; color: #64748b;")
            lbl_d.setWordWrap(True)
            
            vtext.addWidget(lbl_t)
            vtext.addWidget(lbl_d)
            
            rlay.addWidget(lbl_icon)
            rlay.addLayout(vtext)
            
            self.content_lay.addWidget(row)
