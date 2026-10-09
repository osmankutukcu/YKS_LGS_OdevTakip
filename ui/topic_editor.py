# -*- coding: utf-8 -*-
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox, QSplitter, QSizePolicy,
    QLineEdit, QMenu, QFileDialog, QInputDialog
)
from PyQt6.QtGui import QAction, QGuiApplication, QShortcut, QKeySequence, QIcon, QColor, QFont
from PyQt6.QtCore import Qt, QSettings, QByteArray
import csv, io
import db

# Yeni yardımcılar
from utils.konu_helper import get_active_list
from utils.konu_rename import rename_topic

# ---- Sabit grup listeleri ----
ANA_GRUPLAR = ["YKS", "LGS", "Ara Sınıf"]
ALT_GRUPLAR = {
    "YKS": ["mezun-say", "mezun-ea", "mezun-söz", "12-say", "12-ea", "12-söz"],
    "Ara Sınıf": ["11-say", "11-ea", "11-söz", "10.sınıf", "9.sınıf"],
    "LGS": ["8.sınıf", "7.sınıf", "6.sınıf"],
}


class DersKonuEditor(QWidget):
    """Ders/Konu düzenleme ekranı (Genel / Grup / Öğrenci kapsamlı)"""
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Ders/Konu Düzenle")

        self.settings: QSettings = QSettings("EduApps", "YKS_LGS_HomeworkManager")
        self._loading = False
        self._ensure_aux_tables()

        self._build_ui()
        self._restore_ui_state()
        self._populate_groups()
        self._populate_students()
        self._populate_lessons() # Initial load
        self._yukle()

        # 👉 Sağ tık menüsü için hover stili
        self.setStyleSheet(self.styleSheet() + """
                    QMenu {
                        background: #f9fafb;
                        border: 1px solid #e5e7eb;
                    }
                    QMenu::item {
                        padding: 4px 16px;
                    }
                    QMenu::item:selected {
                        background: #2563eb;
                        color: white;
                    }
                """)

    # ---------------------------------------------------------------------
    # DB yardımcı tablolar
    def _ensure_aux_tables(self):
        con = db.get_conn(); cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_konu_duzen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL,
            ders TEXT NOT NULL,
            konu TEXT NOT NULL,
            ort_soru INTEGER,
            ort_sure INTEGER,
            UNIQUE(ogrenci_id, ders, konu)
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS grup_konu_duzen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ana_grup TEXT,
            alt_grup TEXT,
            ders TEXT NOT NULL,
            konu TEXT NOT NULL,
            ort_soru INTEGER,
            ort_sure INTEGER,
            UNIQUE(ana_grup, alt_grup, ders, konu)
        )
        """)
        con.commit()

    # ---------------------------------------------------------------------
    # UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(15)

        # --- ÜST FİLTRE PANELİ (Modern Grid) ---
        from PyQt6.QtWidgets import QGroupBox, QGridLayout
        
        grp_filter = QGroupBox("🔍 Filtrele ve Seç")
        grp_filter.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; border: 1px solid #d1d5db; border-radius: 8px; 
                margin-top: 10px; padding-top: 15px; background-color: #f9fafb;
                font-family: 'Segoe UI', sans-serif;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #374151; }
            QLabel { font-weight: 500; color: #374151; }
            QComboBox, QLineEdit {
                padding: 6px; border: 1px solid #d1d5db; border-radius: 4px; background-color: white;
                min-width: 120px;
            }
            QComboBox:focus, QLineEdit:focus { border: 1px solid #3b82f6; }
            QPushButton {
                 border-radius: 4px; padding: 6px 12px; font-weight: 600;
            }
        """)
        
        grid = QGridLayout(grp_filter)
        grid.setContentsMargins(15, 15, 15, 15)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(12)

        # 1. Satır: Kapsam | Öğrenci | Ders
        grid.addWidget(QLabel("Kapsam:"), 0, 0)
        self.cmbKapsam = QComboBox(); self.cmbKapsam.addItems(["Genel", "Grup", "Öğrenci"])
        grid.addWidget(self.cmbKapsam, 0, 1)
        
        grid.addWidget(QLabel("Öğrenci:"), 0, 2)
        self.cmbOgrenci = QComboBox()
        grid.addWidget(self.cmbOgrenci, 0, 3)

        grid.addWidget(QLabel("Ders:"), 0, 4)
        self.cmbDers = QComboBox() # Dynamic loaded via _populate_lessons
        grid.addWidget(self.cmbDers, 0, 5)

        # 2. Satır: Ana Grup | Alt Grup | Arama (Geniş)
        grid.addWidget(QLabel("Ana Grup:"), 1, 0)
        self.cmbAnaGrup = QComboBox()
        grid.addWidget(self.cmbAnaGrup, 1, 1)

        grid.addWidget(QLabel("Alt Grup:"), 1, 2)
        self.cmbAltGrup = QComboBox()
        grid.addWidget(self.cmbAltGrup, 1, 3)
        
        grid.addWidget(QLabel("Ara:"), 1, 4)
        self.txtAra = QLineEdit(); self.txtAra.setPlaceholderText("Konu adı ara...")
        grid.addWidget(self.txtAra, 1, 5)

        # 3. Satır: İstatistikler ve Butonlar
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        self.lbl_topic_stats = QLabel("📊 Toplam: 0 Konu")
        self.lbl_topic_stats.setStyleSheet("font-weight: 600; color: #2563eb; font-size: 13px;")
        action_layout.addWidget(self.lbl_topic_stats)
        
        action_layout.addStretch()
        
        self.btnOsymHighlight = QPushButton("⭐ ÖSYM Trend Konuları Vurgula")
        self.btnOsymHighlight.setStyleSheet("background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; font-weight: 600; border-radius: 4px; padding: 6px 12px;")
        self.btnOsymHighlight.setToolTip("ÖSYM ve LGS sınavlarında en çok soru gelen konuları tespit et ve renklendir")
        self.btnOsymHighlight.clicked.connect(self._highlight_osym_topics)
        action_layout.addWidget(self.btnOsymHighlight)
        
        self.btnYukle = QPushButton("🔄 Listele / Yenile")
        self.btnYukle.setStyleSheet("background-color: white; border: 1px solid #d1d5db; color: #374151;")
        
        self.btnKaydet = QPushButton("💾 Değişiklikleri Kaydet")
        self.btnKaydet.setStyleSheet("background-color: #10b981; color: white; border: none;") # Emerald Green
        self.btnKaydet.setMinimumHeight(32)
        
        action_layout.addWidget(self.btnYukle)
        action_layout.addWidget(self.btnKaydet)
        
        # Grid'in altına butonları ekle (Span 6 columns)
        grid.addLayout(action_layout, 2, 0, 1, 6)
        
        root.addWidget(grp_filter)

        # --- SPLITTER (Tablo vs Excel) ---
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.setHandleWidth(8)
        self.split.setStyleSheet("""
            QSplitter::handle {
                background: #e5e7eb;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                margin: 0 4px;
            }
            QSplitter::handle:hover { background: #3b82f6; }
        """)
        root.addWidget(self.split, 1)

        # SOL: Tablo + Toolbar
        leftWrap = QWidget(); left = QVBoxLayout(leftWrap)
        left.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        hb_tools = QHBoxLayout()
        self.btnEkle = QPushButton("Satır Ekle"); self.btnEkle.setObjectName("btnStandard")
        self.btnEkle.setIcon(QIcon(":/icons/add")) if hasattr(self, "QIcon") else None
        
        self.btnSil = QPushButton("Satır Sil"); self.btnSil.setObjectName("btnDanger") # Kırmızı
        self.btnSil.setIcon(QIcon(":/icons/delete")) if hasattr(self, "QIcon") else None
        
        self.btnIceri = QPushButton("📂 Excel/CSV Al"); self.btnIceri.setObjectName("btnStandard")
        self.btnIceri.setToolTip("CSV veya Excel'den (CSV formatında) veri yükle")
        
        self.btnDisari = QPushButton("💾 Excel/CSV Ver"); self.btnDisari.setObjectName("btnStandard")
        self.btnDisari.setToolTip("Listeyi CSV (Excel uyumlu) formatında kaydet")
        
        hb_tools.addWidget(self.btnEkle)
        hb_tools.addWidget(self.btnSil)
        hb_tools.addStretch(1)
        hb_tools.addWidget(self.btnIceri)
        hb_tools.addWidget(self.btnDisari)
        left.addLayout(hb_tools)

        # Tablo
        self.tab = QTableWidget(0, 4)
        self.tab.setHorizontalHeaderLabels(["ID", "Konu", "Ort. Soru", "Ort. Süre(dk)"])
        self.tab.horizontalHeader().setStretchLastSection(True)
        self.tab.setAlternatingRowColors(True)
        self.tab.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Tablo stili (Main Window'daki gibi)
        self.tab.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #e5e7eb;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                color: #374151;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #e5e7eb;
                padding: 6px;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #3b82f6;
                color: white;
            }
        """)
        
        self.tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self._open_ctx_menu)
        left.addWidget(self.tab, 1)
        self.split.addWidget(leftWrap)

        # SAĞ: Toplu Ekleme
        rightWrap = QWidget(); right = QVBoxLayout(rightWrap)
        right.setContentsMargins(4, 0, 0, 0)
        
        lbl_info = QLabel("Hızlı Ekleme Paneli (Excel/Metin)")
        lbl_info.setStyleSheet("font-weight: bold; color: #4b5563;")
        right.addWidget(lbl_info)
        
        self.txtYapistir = QTextEdit()
        self.txtYapistir.setPlaceholderText("Excel'den 'Konu' sütununu kopyalayıp buraya yapıştırın...\n(Her satır yeni bir konu olur)")
        self.txtYapistir.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: #f9fafb;
                padding: 8px;
            }
            QTextEdit:focus {
                border: 1px solid #3b82f6;
                background: white;
            }
        """)
        right.addWidget(self.txtYapistir, 1)
        
        # Sağ alt butonlar
        rtools = QHBoxLayout()
        self.btnTemizle = QPushButton("Temizle")
        self.btnTemizle.setObjectName("btnStandard")
        self.btnTemizle.setToolTip("Yapıştırma alanını temizle")
        
        self.btnTopluEkle = QPushButton("Listeye Ekle")
        self.btnTopluEkle.setObjectName("btnAction") # Mavi
        self.btnTopluEkle.setToolTip("Buradaki metinleri sol taraftaki listeye ekler")
        
        rtools.addWidget(self.btnTemizle)
        
        self.btnOnizle = QPushButton("Önizle")
        self.btnOnizle.setToolTip("Eklenecek satır sayısını göster")
        rtools.addWidget(self.btnOnizle)
        
        rtools.addStretch(1)
        rtools.addWidget(self.btnTopluEkle)
        right.addLayout(rtools)
        
        self.split.addWidget(rightWrap)

        # Başlangıç oranları
        self.split.setSizes([720, 360])

        # SİNYALLER
        self.cmbKapsam.currentIndexChanged.connect(self._toggle_scope)
        self.cmbAnaGrup.currentIndexChanged.connect(self._on_group_change) # Group change handler
        self.cmbAltGrup.currentIndexChanged.connect(self._on_group_change)
        self.cmbOgrenci.currentIndexChanged.connect(self._on_student_change) # Student change handler
        self.cmbDers.currentIndexChanged.connect(self._yukle)
        self.btnYukle.clicked.connect(self._full_refresh) # Changed from _yukle to _full_refresh
        self.btnKaydet.clicked.connect(self._kaydet)
        self.btnEkle.clicked.connect(self._ekle_satir)
        self.btnSil.clicked.connect(self._sil_satir)
        self.btnIceri.clicked.connect(self._import_csv)
        self.btnDisari.clicked.connect(self._export_csv)
        self.btnTopluEkle.clicked.connect(self._toplu_ekle)
        self.btnTemizle.clicked.connect(self.txtYapistir.clear)

        # MOVED SIGNALS
        self.btnOnizle.clicked.connect(self._preview_bulk)
        self.txtAra.textChanged.connect(self._apply_filter)
        self.split.splitterMoved.connect(lambda *_: self._save_ui_state())

        # MOVED SHORTCUTS
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._kaydet)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._ekle_satir)
        QShortcut(QKeySequence("Del"),    self, activated=self._sil_satir)
        QShortcut(QKeySequence("Ctrl+C"), self, activated=self._copy_tsv)
        QShortcut(QKeySequence("Ctrl+V"), self, activated=lambda: self._paste_from_clipboard(mode="smart"))
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.txtAra.setFocus())

    def _full_refresh(self):
        """Tüm verileri (öğrenci, ders listesi vb.) yeniden yükle."""
        current_st = self.cmbOgrenci.currentData()
        current_grp_ana = self.cmbAnaGrup.currentText()
        current_grp_alt = self.cmbAltGrup.currentText()
        
        self._populate_groups()
        self._populate_students()
        
        # Seçimleri korumaya çalış
        if current_grp_ana: self.cmbAnaGrup.setCurrentText(current_grp_ana)
        if current_grp_alt: self.cmbAltGrup.setCurrentText(current_grp_alt) 
        if current_st:
            idx = self.cmbOgrenci.findData(current_st)
            if idx >= 0: self.cmbOgrenci.setCurrentIndex(idx)
            
        self._populate_lessons() # Bu da _yukle() çağırır

    # ---------------------------------------------------------------------
    # Akıllı Ders Listeleme (Müfredat Bağlantılı)
    def _populate_lessons(self):
        """Kapsama göre (Öğrenci/Grup/Genel) ders listesini filtrele ve Görünen Adları kullan."""
        # Mevcut seçimi korumaya çalış
        current_id = self.cmbDers.currentData()
        
        self.cmbDers.blockSignals(True)
        self.cmbDers.clear()
        
        scope = self.cmbKapsam.currentText()
        allowed_ids = None # None = Hepsi
        
        # 1. Filtreleme Mantığı
        if scope == "Öğrenci":
            data = self.cmbOgrenci.currentData()
            if data: # Öğrenci seçiliyse
                try:
                    import db
                    if hasattr(db, 'get_student_curriculum'):
                        allowed_ids = db.get_student_curriculum(int(data))
                except: pass
                
        elif scope == "Grup":
            alt = self.cmbAltGrup.currentText()
            ana = self.cmbAnaGrup.currentText()
            if alt:
                try:
                    # Özel grup ayarı var mı?
                    import db
                    config_ids = db.get_lessons_for_group(alt)
                    if config_ids:
                        allowed_ids = config_ids
                    else:
                        # Yoksa varsayılanlar
                        if hasattr(db, 'DEFAULT_GRUP_DERSLER'):
                            allowed_ids = db.DEFAULT_GRUP_DERSLER.get(ana, [])
                except: pass
        
        # 2. Tüm Dersleri Config'den Config'den al (İsimler için)
        active_lessons = []
        try:
            import db
            # DB init edilmemiş olabilir, garantiye al
            if hasattr(db, 'init_curriculum'):
                 db.init_curriculum(db.get_conn())
            
            config = db.get_lesson_config(db.get_conn())
            if not config and hasattr(db, 'DERS_TABLOLARI'):
                # Fallback to simple list if config empty
                for t in db.DERS_TABLOLARI:
                    active_lessons.append({"id": t, "ad": t, "grup": "Genel"})
            else:
                for k, v in config.items():
                    # Eğer filtre varsa sadece izin verilenleri ekle
                    if allowed_ids is not None:
                        if k in allowed_ids:
                            active_lessons.append(v)
                    else:
                        # Genel modda sadece AKTİF olanlar mı? Yoksa hepsi mi?
                        # Editör olduğu için pasifleri de görmek isteyebilir ama genelde aktiftir.
                        if v.get('aktif', 1):
                            active_lessons.append(v)
                            
        except Exception as e:
           print("Lesson load err:", e)
           # Fallback
           import db
           if hasattr(db, 'DERS_TABLOLARI'):
                for t in db.DERS_TABLOLARI:
                    active_lessons.append({"id": t, "ad": t, "grup": "Genel"})

        # 3. Sırala ve Ekle
        # Gruba ve Sıraya göre
        active_lessons.sort(key=lambda x: (x.get('grup', 'Z'), x.get('siralama', 999), x.get('ad', '')))
        
        for less in active_lessons:
            self.cmbDers.addItem(less.get('ad', less['id']), less['id'])
            
        # Seçimi geri yükle
        idx = self.cmbDers.findData(current_id)
        if idx >= 0:
            self.cmbDers.setCurrentIndex(idx)
        else:
            if self.cmbDers.count() > 0: self.cmbDers.setCurrentIndex(0)
            
        self.cmbDers.blockSignals(False)
        self._yukle() # Tabloyu yenile

    def _on_student_change(self):
        if self.cmbKapsam.currentText() == "Öğrenci":
            self._populate_lessons()
        else:
            self._yukle()

    def _on_group_change(self):
        self._update_alt_gruplar()
        if self.cmbKapsam.currentText() == "Grup":
             self._populate_lessons()
        else:
             self._yukle()

    # ---------------------------------------------------------------------
    # Gruplar / öğrenciler
    def _populate_groups(self):
        self.cmbAnaGrup.clear()
        self.cmbAnaGrup.addItems(ANA_GRUPLAR)
        self._update_alt_gruplar()

    def _update_alt_gruplar(self):
        ag = self.cmbAnaGrup.currentText()
        self.cmbAltGrup.blockSignals(True)
        self.cmbAltGrup.clear()
        self.cmbAltGrup.addItem("")
        if ag in ALT_GRUPLAR:
            self.cmbAltGrup.addItems(ALT_GRUPLAR[ag])
        self.cmbAltGrup.blockSignals(False)

    def _populate_students(self):
        con = db.get_conn(); cur = con.cursor()
        rows = cur.execute(
            "SELECT id, ad || ' ' || soyad AS adsoy FROM ogrenci ORDER BY ad, soyad"
        ).fetchall()
        self.cmbOgrenci.clear()
        self.cmbOgrenci.addItem("")  # boş = seçilmedi
        for r in rows:
            self.cmbOgrenci.addItem(r["adsoy"], r["id"])

    # ---------------------------------------------------------------------
    # Kapsam görünürlüğü
    def _toggle_scope(self):
        scope = self.cmbKapsam.currentText()
        self.cmbAnaGrup.setEnabled(scope == "Grup")
        self.cmbAltGrup.setEnabled(scope == "Grup")
        self.cmbOgrenci.setEnabled(scope == "Öğrenci")
        self._yukle()

    # ---------------------------------------------------------------------
    # UI state
    def _save_ui_state(self):
        self.settings.setValue("derskonu/split_sizes", self.split.sizes())
        self.settings.setValue("derskonu/header_state", self.tab.horizontalHeader().saveState())

    def _restore_ui_state(self):
        sizes = self.settings.value("derskonu/split_sizes", None)
        if isinstance(sizes, list) and len(sizes) == 2 and all(isinstance(x, int) for x in sizes):
            self.split.setSizes(sizes)
        header_state = self.settings.value("derskonu/header_state", None)
        if isinstance(header_state, QByteArray):
            self.tab.horizontalHeader().restoreState(header_state)

    def closeEvent(self, e):
        self._save_ui_state()
        return super().closeEvent(e)

    # ---------------------------------------------------------------------
    # ---------------------------------------------------------------------
    # Kapsam parametreleri
    def _current_scope(self):
        s = self.cmbKapsam.currentText()
        # Display Name yerine ID (Tablo Adı) kullan
        ders = self.cmbDers.currentData()
        if not ders:
             # Fallback: veri yoksa texti al (ama eski sistem için) veya boş dön
             ders = "" 
             
        if s == "Genel":
            return "Genel", {"ders": ders}
        elif s == "Grup":
            return "Grup", {
                "ders": ders,
                "ana_grup": self.cmbAnaGrup.currentText(),
                "alt_grup": self.cmbAltGrup.currentText(),
            }
        else:
            data = self.cmbOgrenci.currentData()
            ogr_id = int(data) if data and str(data).isdigit() else None
            return "Öğrenci", {"ders": ders, "ogrenci_id": ogr_id}

    # ---------------------------------------------------------------------
    # Veri yükleme
    def _yukle(self):
        scope, p = self._current_scope()
        
        # Eğer ders seçili değilse işlem yapma (Hata Önleme)
        if not p.get("ders"):
            self.tab.setRowCount(0)
            return

        con = db.get_conn(); cur = con.cursor()
        if scope == "Genel":
            rows = db.ders_konularini_cek(con, p["ders"])
        elif scope == "Grup":
            rows = cur.execute("""
                SELECT id, konu, ort_soru, ort_sure FROM grup_konu_duzen
                WHERE ders=? AND ana_grup=? AND alt_grup=?
                ORDER BY id
            """, (p["ders"], p["ana_grup"], p["alt_grup"])).fetchall()
        else:
            if not p.get("ogrenci_id"):
                rows = []
            else:
                rows = cur.execute("""
                    SELECT id, konu, ort_soru, ort_sure FROM ogrenci_konu_duzen
                    WHERE ogrenci_id=? AND ders=?
                    ORDER BY id
                """, (p["ogrenci_id"], p["ders"])).fetchall()

        self._loading = True
        self.tab.setRowCount(0)
        for r in rows:
            i = self.tab.rowCount(); self.tab.insertRow(i)
            self.tab.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.tab.setItem(i, 1, QTableWidgetItem(r["konu"]))
            self.tab.setItem(i, 2, QTableWidgetItem(str(r["ort_soru"] or "")))
            self.tab.setItem(i, 3, QTableWidgetItem(str(r["ort_sure"] or "")))
        self._loading = False
        self.tab.resizeColumnsToContents()
        self._apply_filter(self.txtAra.text())
        self._validate_rows()

        # İstatistikleri güncelle
        if hasattr(self, 'lbl_topic_stats'):
            total_topics = len(rows)
            valid_q = [int(r["ort_soru"]) for r in rows if r["ort_soru"] and str(r["ort_soru"]).isdigit()]
            avg_q = round(sum(valid_q) / len(valid_q)) if valid_q else 0
            valid_t = [int(r["ort_sure"]) for r in rows if r["ort_sure"] and str(r["ort_sure"]).isdigit()]
            avg_t = round(sum(valid_t) / len(valid_t)) if valid_t else 0
            scope_name = self.cmbKapsam.currentText()
            self.lbl_topic_stats.setText(f"📊 {scope_name}: {total_topics} Konu  •  Ort. Hedef: {avg_q} Soru ({avg_t} dk)")


    def _highlight_osym_topics(self):
        """ÖSYM ve LGS sınavlarında en sık sorulan kritik konuları tespit edip altın sarısı renkle vurgular."""
        keywords = [
            "paragraf", "problem", "üslü", "köklü", "fonksiyon", "türev", "integral",
            "trigonometri", "polinom", "limit", "asit", "baz", "periyodik", "mol",
            "kuvvet", "hareket", "optik", "dalga", "hücre", "kalıtım", "fotosentez",
            "ekoloji", "cümlede anlam", "yazım kuralları", "noktalama", "üçgen", "çember",
            "analitik", "oran", "orantı", "çarpan", "katlar", "kareköklü", "olasılık"
        ]
        count = 0
        for r in range(self.tab.rowCount()):
            it = self.tab.item(r, 1)
            if not it:
                continue
            txt = it.text().lower()
            if any(k in txt for k in keywords):
                it.setBackground(QColor("#fef9c3"))
                it.setForeground(QColor("#854d0e"))
                it.setToolTip("⭐ ÖSYM / Sınav Trend Yüksek Frekanslı Konu")
                count += 1
        if count > 0:
            QMessageBox.information(self, "⭐ ÖSYM Trend Konuları", f"Bu derste sınavlarda en çok çıkan {count} kritik konu tespit edildi ve altın sarısı renkle vurgulandı.")
        else:
            QMessageBox.information(self, "ÖSYM Trend Konuları", "Bu ders listesinde standart anahtar kelimelerle eşleşen konu bulunamadı.")

    def _validate_rows(self):
        """Konu adı boş olanları kırmızı işaretle."""
        for r in range(self.tab.rowCount()):
            it = self.tab.item(r, 1)
            if not it:
                continue
            text = it.text().strip()
            if not text:
                it.setBackground(QColor("#fee2e2")) # Kırmızımsı
                it.setToolTip("Konu adı boş olamaz!")
            else:
                it.setBackground(QColor("white"))
                it.setToolTip("")

    # ---------------------------------------------------------------------
    # Kaydet
    # ---------------------------------------------------------------------
    # Kaydet
    def _kaydet(self):
        scope, p = self._current_scope()
        con = db.get_conn(); cur = con.cursor()

        for i in range(self.tab.rowCount()):
            idt = self._cell(i, 0)
            konu = self._cell(i, 1)
            ort_soru = (self._cell(i, 2).strip() or None)
            ort_sure = (self._cell(i, 3).strip() or None)
            if not konu.strip():
                continue

            if scope == "Genel":
                if idt.strip():
                    cur.execute(
                        f"UPDATE {p['ders']} SET konu=?, ort_soru=?, ort_sure=? WHERE id=?",
                        (konu, ort_soru, ort_sure, int(idt))
                    )
                else:
                    cur.execute(
                        f"INSERT INTO {p['ders']}(konu, ort_soru, ort_sure) VALUES(?,?,?)",
                        (konu, ort_soru, ort_sure)
                    )
            elif scope == "Grup":
                cur.execute("""
                    INSERT INTO grup_konu_duzen(ana_grup, alt_grup, ders, konu, ort_soru, ort_sure)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(ana_grup, alt_grup, ders, konu)
                    DO UPDATE SET ort_soru=excluded.ort_soru, ort_sure=excluded.ort_sure
                """, (p["ana_grup"], p["alt_grup"], p["ders"], konu, ort_soru, ort_sure))
            else:
                if not p.get("ogrenci_id"):
                    QMessageBox.warning(self, "Eksik Bilgi", "Öğrenci seçilmedi.")
                    return
                cur.execute("""
                    INSERT INTO ogrenci_konu_duzen(ogrenci_id, ders, konu, ort_soru, ort_sure)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(ogrenci_id, ders, konu)
                    DO UPDATE SET ort_soru=excluded.ort_soru, ort_sure=excluded.ort_sure
                """, (p["ogrenci_id"], p["ders"], konu, ort_soru, ort_sure))

        con.commit()
        self._yukle()
        QMessageBox.information(self, "Kaydedildi", "Değişiklikler kaydedildi.")

    # ---------------------------------------------------------------------
    # Satır ekle/sil
    def _ekle_satir(self, *, after: Optional[int] = None, clone_from: Optional[int] = None):
        r = self.tab.rowCount() if after is None else after + 1
        self.tab.insertRow(r)
        if clone_from is not None and 0 <= clone_from < self.tab.rowCount():
            for c in range(4):
                src = self.tab.item(clone_from, c)
                self.tab.setItem(r, c, QTableWidgetItem(src.text() if src else ""))
            self.tab.setItem(r, 0, QTableWidgetItem(""))  # ID kopyalanmasın
        else:
            for c in range(4):
                self.tab.setItem(r, c, QTableWidgetItem(""))
        self.tab.setCurrentCell(r, 1)

    def _sil_satir(self):
        rows = sorted({it.row() for it in self.tab.selectedItems()}, reverse=True)
        if not rows:
            return
        scope, p = self._current_scope()
        con = db.get_conn(); cur = con.cursor()
        for r in rows:
            idit = self.tab.item(r, 0)
            if idit and idit.text().strip():
                idv = int(idit.text())
                if scope == "Genel":
                    cur.execute(f"DELETE FROM {p['ders']} WHERE id=?", (idv,))
                elif scope == "Grup":
                    cur.execute("DELETE FROM grup_konu_duzen WHERE id=?", (idv,))
                else:
                    cur.execute("DELETE FROM ogrenci_konu_duzen WHERE id=?", (idv,))
            self.tab.removeRow(r)
        con.commit()

    # ---------------------------------------------------------------------
    # Toplu ekle (sağ panel)
    # Toplu ekle (sağ panel)
    def _toplu_ekle(self):
        raw = self.txtYapistir.toPlainText().strip()
        if not raw:
            return
        
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        if not lines:
            return

        # Tabloya ekle (DB'ye hemen yazma)
        added_count = 0
        for konu in lines:
            r = self.tab.rowCount()
            self.tab.insertRow(r)
            # 0: ID (Boş=Yeni), 1: Konu, 2: Soru, 3: Süre
            self.tab.setItem(r, 0, QTableWidgetItem("")) 
            self.tab.setItem(r, 1, QTableWidgetItem(konu))
            self.tab.setItem(r, 2, QTableWidgetItem(""))
            self.tab.setItem(r, 3, QTableWidgetItem(""))
            added_count += 1
            
        self.txtYapistir.clear()
        self.tab.scrollToBottom()
        QMessageBox.information(self, "Eklendi", f"{added_count} adet konu listeye eklendi.\n\nKalıcı olması için 'Değişiklikleri Kaydet' butonuna basmayı unutmayın!")

    def _preview_bulk(self):
        text = self.txtYapistir.toPlainText().strip()
        lines = [l for l in text.splitlines() if l.strip()]
        if not lines:
            QMessageBox.information(self, "Önizleme", "Yapıştırılacak metin yok.")
            return
        QMessageBox.information(self, "Önizleme", f"Toplam {len(lines)} satır tespit edildi.\n\nİçeri Aktar'a basarak ekleyebilirsiniz.")

    # ---------------------------------------------------------------------
    # CSV içe/dışa aktar
    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV Dışa Aktar", "", "CSV (*.csv)")
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "konu", "ort_soru", "ort_sure"])
            for i in range(self.tab.rowCount()):
                w.writerow([self._cell(i, c) for c in range(4)])
        QMessageBox.information(self, "Tamam", "CSV olarak dışa aktarıldı.")

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV İçe Al", "", "CSV (*.csv)")
        if not path: return
        with open(path, "r", encoding="utf-8") as f:
            rdr = csv.reader(f)
            header = next(rdr, None)
            for row in rdr:
                i = self.tab.rowCount(); self.tab.insertRow(i)
                vals = (row + ["", "", "", ""])[:4]
                # ID’yi dışarıdan gelmişse bile boşlayalım (yeni kayıt gibi)
                self.tab.setItem(i, 0, QTableWidgetItem(""))
                self.tab.setItem(i, 1, QTableWidgetItem(vals[1]))
                self.tab.setItem(i, 2, QTableWidgetItem(vals[2]))
                self.tab.setItem(i, 3, QTableWidgetItem(vals[3]))
        self.tab.resizeColumnsToContents()

    # ---------------------------------------------------------------------
    # Filtre
    def _apply_filter(self, text: str):
        text = (text or "").lower().strip()
        for r in range(self.tab.rowCount()):
            konu = (self._cell(r, 1) or "").lower()
            self.tab.setRowHidden(r, (text not in konu))

    # ---------------------------------------------------------------------
    # Hücre yardımcıları
    def _cell(self, r, c):
        it = self.tab.item(r, c)
        return it.text() if it else ""

    # ---------------------------------------------------------------------
    # Sağ tık menüsü
    def _open_ctx_menu(self, pos):
        menu = QMenu(self)

        # Satır işlemleri
        act_new_above = QAction("Üstüne Satır Ekle", self)
        act_new_below = QAction("Altına Satır Ekle", self)
        act_duplicate = QAction("Satırı Çoğalt", self)
        act_del_rows = QAction("Seçili Satır(lar)ı Sil", self)
        menu.addAction(act_new_above); menu.addAction(act_new_below); menu.addAction(act_duplicate)
        menu.addSeparator(); menu.addAction(act_del_rows); menu.addSeparator()

        # Kopyala/Yapıştır
        act_copy_tsv    = QAction("Seçimi Kopyala (TSV)", self)
        act_paste_smart = QAction("Yapıştır (Akıllı: Konu/Ort.Soru/Ort.Süre)", self)
        act_paste_konu  = QAction("Yapıştır → Sadece 'Konu'", self)
        act_paste_soru  = QAction("Yapıştır → Sadece 'Ort. Soru'", self)
        act_paste_sure  = QAction("Yapıştır → Sadece 'Ort. Süre(dk)'", self)
        act_clear_sel   = QAction("Seçimi Temizle", self)
        menu.addAction(act_copy_tsv); menu.addAction(act_paste_smart)
        menu.addSeparator()
        menu.addAction(act_paste_konu); menu.addAction(act_paste_soru); menu.addAction(act_paste_sure)
        menu.addSeparator(); menu.addAction(act_clear_sel); menu.addSeparator()

        # Görünüm / aktar
        act_resize = QAction("Kolonları İçeriğe Sığdır", self)
        act_export = QAction("CSV Dışa Aktar…", self)
        act_import = QAction("CSV İçe Al…", self)
        menu.addAction(act_resize); menu.addSeparator()
        menu.addAction(act_import); menu.addAction(act_export); menu.addSeparator()

        # Genelden doldurma
        act_from_gen_all     = QAction("Genel Şablondan Kopyala → Hepsini Ekle", self)
        act_from_gen_missing = QAction("Genel Şablondan Kopyala → Sadece Eksikleri Ekle", self)
        act_from_gen_replace = QAction("Genel Şablondan Kopyala → Temizle ve Yerine Yaz", self)
        menu.addAction(act_from_gen_all); menu.addAction(act_from_gen_missing); menu.addAction(act_from_gen_replace)

        # Etkin liste + ad değiştirme
        menu.addSeparator()
        act_preview_active = QAction("Etkin Listeyi Göster (Önceliklenmiş)", self)
        act_rename_topic   = QAction("Ad Değiştirme Sihirbazı…", self)
        menu.addAction(act_preview_active)
        menu.addAction(act_rename_topic)

        # Tıklanan satır
        index = self.tab.indexAt(pos)
        row = index.row() if index.isValid() else (self.tab.currentRow() if self.tab.currentRow() >= 0 else None)

        # Bağlantılar
        act_new_above.triggered.connect(lambda: self._ekle_satir(after=(row-1 if row is not None else None)))
        act_new_below.triggered.connect(lambda: self._ekle_satir(after=(row if row is not None else None)))
        act_duplicate.triggered.connect(lambda: self._ekle_satir(after=(row if row is not None else None),
                                                                 clone_from=(row if row is not None else None)))
        act_del_rows.triggered.connect(self._sil_satir)

        act_copy_tsv.triggered.connect(self._copy_tsv)
        act_paste_smart.triggered.connect(lambda: self._paste_from_clipboard(mode="smart"))
        act_paste_konu.triggered.connect(lambda: self._paste_from_clipboard(mode="konu"))
        act_paste_soru.triggered.connect(lambda: self._paste_from_clipboard(mode="soru"))
        act_paste_sure.triggered.connect(lambda: self._paste_from_clipboard(mode="sure"))
        act_clear_sel.triggered.connect(self._clear_selection)

        act_resize.triggered.connect(self.tab.resizeColumnsToContents)
        act_export.triggered.connect(self._export_csv)
        act_import.triggered.connect(self._import_csv)

        act_from_gen_all.triggered.connect(lambda: self._copy_from_general(mode="append_all"))
        act_from_gen_missing.triggered.connect(lambda: self._copy_from_general(mode="append_missing"))
        act_from_gen_replace.triggered.connect(lambda: self._copy_from_general(mode="replace"))

        act_preview_active.triggered.connect(self._preview_active_list)
        act_rename_topic.triggered.connect(self._rename_topic_wizard)

        menu.exec(self.tab.mapToGlobal(pos))

    # ---------------------------------------------------------------------
    # Kopyala / Yapıştır yardımcıları
    def _copy_tsv(self):
        sel = self.tab.selectedRanges()
        if not sel:
            return
        r = sel[0]
        buf = io.StringIO()
        w = csv.writer(buf, delimiter="\t")
        for i in range(r.topRow(), r.bottomRow()+1):
            row = []
            for j in range(r.leftColumn(), r.rightColumn()+1):
                it = self.tab.item(i, j)
                row.append((it.text() if it else "") if j != 0 else "")  # ID'yi kopyalama
            w.writerow(row)
        QGuiApplication.clipboard().setText(buf.getvalue())

    def _clipboard_text(self) -> str:
        return (QGuiApplication.clipboard().text() or "").strip()

    def _parse_table_text(self, text: str) -> List[List[str]]:
        if not text:
            return []
        lines = [ln for ln in text.splitlines() if ln.strip() != ""]
        rows: List[List[str]] = []
        for ln in lines:
            if "\t" in ln: parts = ln.split("\t")
            elif ";" in ln: parts = ln.split(";")
            elif "," in ln: parts = ln.split(",")
            else: parts = [ln]
            rows.append([p.strip() for p in parts])
        return rows

    def _paste_from_clipboard(self, mode: str = "smart"):
        txt = self._clipboard_text()
        if not txt:
            return
        data = self._parse_table_text(txt)
        if not data:
            return

        # başlık algıla
        headers = [h.lower() for h in data[0]]
        header_map = {"konu": None, "soru": None, "sure": None}
        for j, h in enumerate(headers):
            if "konu" in h: header_map["konu"] = j
            if "soru" in h: header_map["soru"] = j
            if "süre" in h or "sure" in h: header_map["sure"] = j
        start_i = 1 if any(v is not None for v in header_map.values()) else 0

        r0 = self.tab.currentRow()
        if r0 < 0:
            r0 = self.tab.rowCount()

        self._loading = True
        r = r0
        for i in range(start_i, len(data)):
            row = data[i]
            if r >= self.tab.rowCount():
                self.tab.insertRow(r)
                for c in range(4):
                    self.tab.setItem(r, c, QTableWidgetItem(""))

            if mode in ("konu", "soru", "sure"):
                col = {"konu": 1, "soru": 2, "sure": 3}[mode]
                val = row[0] if row else ""
                self.tab.setItem(r, col, QTableWidgetItem(val))
            else:
                # SMART
                if header_map["konu"] is not None or header_map["soru"] is not None or header_map["sure"] is not None:
                    if header_map["konu"] is not None and header_map["konu"] < len(row):
                        self.tab.setItem(r, 1, QTableWidgetItem(row[header_map["konu"]]))
                    if header_map["soru"] is not None and header_map["soru"] < len(row):
                        self.tab.setItem(r, 2, QTableWidgetItem(row[header_map["soru"]]))
                    if header_map["sure"] is not None and header_map["sure"] < len(row):
                        self.tab.setItem(r, 3, QTableWidgetItem(row[header_map["sure"]]))
                else:
                    konu = row[0] if len(row) >= 1 else ""
                    soru = row[1] if len(row) >= 2 else ""
                    sure = row[2] if len(row) >= 3 else ""
                    self.tab.setItem(r, 1, QTableWidgetItem(konu))
                    if soru != "": self.tab.setItem(r, 2, QTableWidgetItem(soru))
                    if sure != "": self.tab.setItem(r, 3, QTableWidgetItem(sure))
            r += 1
        self._loading = False
        self.tab.resizeColumnsToContents()

    def _clear_selection(self):
        for it in self.tab.selectedItems():
            if it.column() == 0:   # ID'yi temizleme
                continue
            it.setText("")

    # ---------------------------------------------------------------------
    # Genelden kopyalama (grup/öğrenci görünümüne)
    def _copy_from_general(self, mode: str = "append_all"):
        """
        mode:
          - append_all     : Genel listedeki tüm konuları ekrana ekler
          - append_missing : Sadece eksik olanları ekler
          - replace        : Tabloyu temizler, genel ile birebir doldurur
        Not: ekrana yazar; DB'ye yazmak için Kaydet'e bas.
        """
        ders = self.cmbDers.currentText()
        con = db.get_conn()
        genel_rows = db.ders_konularini_cek(con, ders)  # [{id, konu, ort_soru, ort_sure}, ...]

        current = set()
        for i in range(self.tab.rowCount()):
            k = (self._cell(i, 1) or "").strip().lower()
            if k:
                current.add(k)

        self._loading = True
        if mode == "replace":
            self.tab.setRowCount(0)

        for gr in genel_rows:
            konu = (gr["konu"] or "").strip()
            if not konu:
                continue
            if mode == "append_missing" and konu.lower() in current:
                continue

            i = self.tab.rowCount()
            self.tab.insertRow(i)
            self.tab.setItem(i, 0, QTableWidgetItem(""))  # ID boş
            self.tab.setItem(i, 1, QTableWidgetItem(konu))
            self.tab.setItem(i, 2, QTableWidgetItem(str(gr["ort_soru"] or "")))
            self.tab.setItem(i, 3, QTableWidgetItem(str(gr["ort_sure"] or "")))

        self._loading = False
        self.tab.resizeColumnsToContents()

    # ---------------------------------------------------------------------
    # Etkin Liste önizleme
    def _preview_active_list(self):
        """Mevcut kapsam (Genel / Grup / Öğrenci) için etkin listeyi göster."""
        scope, p = self._current_scope()
        con = db.get_conn()

        aktif = get_active_list(
            con,
            ders=p["ders"],
            ogrenci_id=p.get("ogrenci_id"),
            ana_grup=p.get("ana_grup"),
            alt_grup=p.get("alt_grup"),
        )

        if not aktif:
            QMessageBox.information(self, "Etkin Liste", "Bu kapsam için konu bulunamadı.")
            return

        lines = []
        for i, r in enumerate(aktif, start=1):
            s = f"{i:02d}. {r['konu']}"
            ek = []
            if r.get("ort_soru") not in (None, ""):
                ek.append(f"Soru: {r['ort_soru']}")
            if r.get("ort_sure") not in (None, ""):
                ek.append(f"Süre: {r['ort_sure']} dk")
            if ek:
                s += "  (" + ", ".join(ek) + ")"
            lines.append(s)

        QMessageBox.information(
            self,
            "Etkin Liste",
            "Öncelik sırası: Öğrenci > Grup > Genel\n\n" + "\n".join(lines)
        )

    # ---------------------------------------------------------------------
    # Ad değiştirme sihirbazı
    def _rename_topic_wizard(self):
        """Seçili konunun adını değiştir ve istersen geçmiş kayıtları güncelle."""
        row = self.tab.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Önce listeden bir satır seçin.")
            return

        old_name = self._cell(row, 1).strip()
        if not old_name:
            QMessageBox.warning(self, "Uyarı", "Seçili satırda 'Konu' boş.")
            return

        # Yeni ad sor
        new_name, ok = QInputDialog.getText(
            self,
            "Ad Değiştirme",
            f"Eski ad: {old_name}\n\nYeni konu adını girin:",
            text=old_name,
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()

        # Geçmişi güncelle?
        reply = QMessageBox.question(
            self,
            "Geçmişi Güncelle?",
            "Geçmiş ödev kayıtlarındaki konu adlarını da güncellemek ister misiniz?\n"
            "(Önerilen: Evet)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        update_history = (reply == QMessageBox.StandardButton.Yes)

        scope, p = self._current_scope()
        con = db.get_conn()

        rename_topic(
            con,
            ders=p["ders"],
            old_name=old_name,
            new_name=new_name,
            scope=scope,
            ana_grup=p.get("ana_grup"),
            alt_grup=p.get("alt_grup"),
            ogrenci_id=p.get("ogrenci_id"),
            merge_if_exists=True,
            update_history=update_history,
        )

        self._yukle()
        QMessageBox.information(self, "Tamam", f"'{old_name}' → '{new_name}' olarak güncellendi.")