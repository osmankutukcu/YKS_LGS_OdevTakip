# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QDateEdit, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QMenu, QApplication,
    QGroupBox, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QTimer, QPoint
from PyQt6.QtGui import QAction, QCursor, QKeySequence, QIcon

from ui.progress import IlerlemePenceresi
from utils.async_workers import arka_planda_calistir
from utils.xlsx_io import ogrenci_sablon_olustur, ogrenci_excel_oku
import db
from pathlib import Path
from utils import audit_manager  # NEW


ANA_GRUPLAR = ["YKS", "LGS", "Ara Sınıf"]
ALT_GRUPLAR = {
    "YKS": ["mezun-say", "mezun-ea", "mezun-söz", "12-say", "12-ea", "12-söz"],
    "Ara Sınıf": ["11-say", "11-ea", "11-söz", "10.sınıf", "9.sınıf"],
    "LGS": ["8.sınıf", "7.sınıf", "6.sınıf"]
}
YAKINLIK_LISTE = ["Anne", "Baba", "Kardeş", "Teyze", "Hala", "Amca", "Dayı", "Vasi", "Komşu", "Diğer"]


class OgrenciFormu(QWidget):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("OgrenciFormu")
        # client-side görünürlük filtresi (DB'ye dokunmadan)
        self._client_filter_active = False
        self._client_filter_col = None
        self._client_filter_val = None

        self._build_ui()
        self._load_list()  # tüm liste

    # ---------------- UI ----------------
    def _build_ui(self):
        # --- Sol panel: Form ---
        # --- Sol panel: Modern Group Layout ---
        sol_scroll = QScrollArea()
        sol_scroll.setWidgetResizable(True)
        sol_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sol_content = QWidget()
        sol_layout = QVBoxLayout(sol_content)
        sol_layout.setSpacing(15)
        sol_layout.setContentsMargins(0, 0, 10, 0)

        # 1. Kimlik & Okul
        gb_kimlik = QGroupBox("Kimlik ve Okul Bilgileri")
        gl_kimlik = QGridLayout(gb_kimlik)
        gl_kimlik.setVerticalSpacing(10)
        
        self.txtAd = QLineEdit(); self.txtAd.setPlaceholderText("Ad")
        self.txtSoyad = QLineEdit(); self.txtSoyad.setPlaceholderText("Soyad")
        self.txtNo = QLineEdit(); self.txtNo.setPlaceholderText("Okul No")
        self.dtpDogum = QDateEdit(); self.dtpDogum.setCalendarPopup(True); self.dtpDogum.setDate(QDate(2008, 1, 1))
        
        gl_kimlik.addWidget(QLabel("Ad:"), 0, 0)
        gl_kimlik.addWidget(self.txtAd, 0, 1)
        gl_kimlik.addWidget(QLabel("Soyad:"), 0, 2)
        gl_kimlik.addWidget(self.txtSoyad, 0, 3)
        
        gl_kimlik.addWidget(QLabel("Okul No:"), 1, 0)
        gl_kimlik.addWidget(self.txtNo, 1, 1)
        gl_kimlik.addWidget(QLabel("D. Tarihi:"), 1, 2)
        gl_kimlik.addWidget(self.dtpDogum, 1, 3)

        self.cmbAna = QComboBox(); self.cmbAna.addItems(ANA_GRUPLAR)
        self.cmbAlt = QComboBox(); self._alt_grup_guncelle("YKS")
        self.cmbAna.currentTextChanged.connect(self._alt_grup_guncelle)
        
        gl_kimlik.addWidget(QLabel("Grup:"), 2, 0)
        h_grp = QHBoxLayout(); h_grp.setSpacing(5)
        h_grp.addWidget(self.cmbAna); h_grp.addWidget(self.cmbAlt)
        gl_kimlik.addLayout(h_grp, 2, 1, 1, 3) # Span across
        
        sol_layout.addWidget(gb_kimlik)
        
        # 2. İletişim (Öğrenci)
        gb_iletisim = QGroupBox("Öğrenci İletişim")
        gl_iletisim = QGridLayout(gb_iletisim)
        
        self.txtOgrTel = QLineEdit(); self.txtOgrTel.setInputMask("0(599) 999 99 99;_"); self.txtOgrTel.setPlaceholderText("0(5XX)...")
        self.txtOgrMail = QLineEdit(); self.txtOgrMail.setPlaceholderText("email@...")
        
        gl_iletisim.addWidget(QLabel("Tel:"), 0, 0); gl_iletisim.addWidget(self.txtOgrTel, 0, 1)
        gl_iletisim.addWidget(QLabel("Mail:"), 0, 2); gl_iletisim.addWidget(self.txtOgrMail, 0, 3)
        sol_layout.addWidget(gb_iletisim)

        # 3. Veli Bilgileri
        gb_veli = QGroupBox("Veli Bilgileri")
        gl_veli = QGridLayout(gb_veli)
        
        self.txtVeliAd = QLineEdit(); self.txtVeliAd.setPlaceholderText("Veli Ad Soyad")
        self.cmbYakin = QComboBox(); self.cmbYakin.addItems(YAKINLIK_LISTE)
        
        gl_veli.addWidget(QLabel("Veli Adı:"), 0, 0); gl_veli.addWidget(self.txtVeliAd, 0, 1)
        gl_veli.addWidget(QLabel("Yakınlık:"), 0, 2); gl_veli.addWidget(self.cmbYakin, 0, 3)
        
        self.txtVeliTel1 = QLineEdit(); self.txtVeliTel1.setInputMask("0(599) 999 99 99;_"); self.txtVeliTel1.setPlaceholderText("Tel 1")
        self.txtVeliTel2 = QLineEdit(); self.txtVeliTel2.setPlaceholderText("Tel 2 (Opsiyonel)")
        self.txtVeliMail = QLineEdit(); self.txtVeliMail.setPlaceholderText("Veli Mail")
        
        gl_veli.addWidget(QLabel("Tel 1:"), 1, 0); gl_veli.addWidget(self.txtVeliTel1, 1, 1)
        gl_veli.addWidget(QLabel("Tel 2:"), 1, 2); gl_veli.addWidget(self.txtVeliTel2, 1, 3)
        gl_veli.addWidget(QLabel("Mail:"), 2, 0); gl_veli.addWidget(self.txtVeliMail, 2, 1, 1, 3)
        
        sol_layout.addWidget(gb_veli)

        # 4. Notlar
        gb_not = QGroupBox("Kişisel Notlar")
        l_not = QVBoxLayout(gb_not)
        self.txtKisisel = QTextEdit(); self.txtKisisel.setMaximumHeight(80)
        l_not.addWidget(self.txtKisisel)
        sol_layout.addWidget(gb_not)
        
        sol_scroll.setWidget(sol_content)

        # Butonlar
        # Butonlar (2 Satır Layout: Daha ferah ve okunabilir)
        # 1. Satır: CRUD (Yeni, Kaydet, Güncelle, Sil)
        row_crud = QHBoxLayout()
        row_crud.setSpacing(8)
        
        self.btnYeni = QPushButton("✨ Yeni")
        self.btnYeni.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        self.btnKaydet = QPushButton("💾 Kaydet")
        self.btnKaydet.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnKaydet.setObjectName("primary") 
        
        self.btnGuncelle = QPushButton("🔄 Güncelle")
        self.btnGuncelle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        self.btnSil = QPushButton("🗑️ Sil")
        self.btnSil.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnSil.setObjectName("danger")
        
        row_crud.addWidget(self.btnYeni)
        row_crud.addWidget(self.btnKaydet)
        row_crud.addWidget(self.btnGuncelle)
        row_crud.addWidget(self.btnSil)

        # 2. Satır: Araçlar (Excel)
        row_tools = QHBoxLayout()
        row_tools.setSpacing(8)
        
        self.btnExcelSablon = QPushButton("📄 Boş Şablon Al")
        self.btnExcelSablon.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnExcelSablon.setObjectName("excelSecondary")
        
        self.btnExcelAktar = QPushButton("📥 Excel'den Yükle")
        self.btnExcelAktar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnExcelAktar.setObjectName("excelSecondary")
        
        row_tools.addStretch()
        row_tools.addWidget(self.btnExcelSablon)
        row_tools.addWidget(self.btnExcelAktar)

        sol_widget = QWidget()
        sol_v = QVBoxLayout(sol_widget)
        sol_v.addWidget(sol_scroll)
        sol_v.addLayout(row_crud)
        sol_v.addLayout(row_tools)

        # --- Sağ panel: Liste (Tüm Kolonlar) ---
        self.txtAra = QLineEdit()
        self.txtAra.setPlaceholderText("Ad, Soyad veya Veli Ara... (Ctrl+F)")
        self.txtAra.setClearButtonEnabled(True)

        # ID, Ad, Soyad, No, Ana, Alt, OgrTel, OgrMail, VeliAd, Yakinlik, VeliTel1, VeliTel2, VeliMail, Dogum
        cols = ["ID", "Ad", "Soyad", "No", "Grup", "Alt Grup", "Tel", "Mail", "Veli", "Yakınlık", "Veli T1", "Veli T2", "Veli Mail", "D.Tarihi"]
        self.liste = QTableWidget(0, len(cols))
        self.liste.setHorizontalHeaderLabels(cols)
        self.liste.setSelectionBehavior(self.liste.SelectionBehavior.SelectRows)
        self.liste.setSelectionMode(self.liste.SelectionMode.ExtendedSelection)
        self.liste.setEditTriggers(self.liste.EditTrigger.NoEditTriggers)
        self.liste.setAlternatingRowColors(True)
        self.liste.setShowGrid(False)
        self.liste.setSortingEnabled(True)
        
        # Context Menu
        self._setup_table_context_menu()
        self.lblInfo = QLabel("")
        self.lblInfo.setObjectName("listInfo")

        sag_widget = QWidget()
        sag_v = QVBoxLayout(sag_widget)
        
        # --- Dashboard Widget (Yeni) ---
        self.dash_widget = QWidget()
        dl = QHBoxLayout(self.dash_widget)
        dl.setContentsMargins(0,0,0,10)
        dl.setSpacing(15)

        def make_card(icon, label, value_id):
            f = QFrame(); f.setObjectName("statCard")
            # Gölge efekti (kodla eklemek yerine CSS ile border kullanalım)
            l = QHBoxLayout(f); l.setContentsMargins(15,15,15,15); l.setSpacing(15)
            lbl_icon = QLabel(icon); lbl_icon.setStyleSheet("font-size: 28px; background: transparent;")
            v_layout = QVBoxLayout(); v_layout.setSpacing(2)
            lbl_val = QLabel("0"); lbl_val.setObjectName(value_id); lbl_val.setStyleSheet("font-size: 20px; font-weight: 800; color: #1e293b;")
            lbl_tit = QLabel(label); lbl_tit.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;")
            v_layout.addWidget(lbl_val); v_layout.addWidget(lbl_tit)
            l.addWidget(lbl_icon); l.addLayout(v_layout)
            return f, lbl_val

        self.card_total, self.lbl_stat_total = make_card("👥", "Toplam", "statTotal")
        self.card_yks, self.lbl_stat_yks = make_card("🎓", "YKS", "statYKS")
        self.card_lgs, self.lbl_stat_lgs = make_card("🎒", "LGS", "statLGS")
        self.card_bday, self.lbl_stat_bday = make_card("🎂", "Doğum Günü", "statBday")
        
        dl.addWidget(self.card_total); dl.addWidget(self.card_yks)
        dl.addWidget(self.card_lgs); dl.addWidget(self.card_bday)
        
        sag_v.addWidget(self.dash_widget)
        
        # Arama ve Hızlı Seçim Araçları
        row_search = QHBoxLayout()
        row_search.addWidget(self.txtAra, 1)
        
        self.btnSecTumunu = QPushButton("☑️ Tümünü Seç")
        self.btnSecTumunu.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnSecTumunu.setToolTip("Listedeki tüm öğrencileri seçer")
        self.btnSecTumunu.clicked.connect(self.liste.selectAll)
        
        self.btnSecTemizle = QPushButton("Seçimi Temizle")
        self.btnSecTemizle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnSecTemizle.setToolTip("Tablodaki tüm seçimleri kaldırır")
        self.btnSecTemizle.clicked.connect(self.liste.clearSelection)
        
        row_search.addWidget(self.btnSecTumunu)
        row_search.addWidget(self.btnSecTemizle)
        sag_v.addLayout(row_search)
        
        sag_v.addWidget(self.liste)
        sag_v.addWidget(self.lblInfo)

        self._ara_timer = QTimer(self)
        self._ara_timer.setSingleShot(True)
        self._ara_timer.timeout.connect(lambda: self._load_list(self.txtAra.text().strip()))
        self.txtAra.textChanged.connect(lambda: self._ara_timer.start(300))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sol_widget)
        splitter.addWidget(sag_widget)
        sol_widget.setMinimumWidth(480) # Biraz daha geniş
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root = QVBoxLayout(self)
        root.addWidget(splitter)
        
        # Bağlantılar
        self.btnYeni.clicked.connect(self._temizle)
        self.btnKaydet.clicked.connect(self._kaydet)
        self.btnGuncelle.clicked.connect(self._guncelle)
        self.btnSil.clicked.connect(self._sil)
        self.btnExcelSablon.clicked.connect(self._sablon)
        self.btnExcelAktar.clicked.connect(self._excelden_aktar)
        self.liste.itemSelectionChanged.connect(self._liste_secildi)
        self.liste.itemSelectionChanged.connect(self._update_info_label)

        # Kısayollar
        self.btnYeni.setShortcut(QKeySequence.StandardKey.New)
        self.btnKaydet.setShortcut(QKeySequence.StandardKey.Save)
        self.btnGuncelle.setShortcut(QKeySequence("Ctrl+U"))
        self.btnSil.setShortcut(QKeySequence.StandardKey.Delete)
        self.txtAra.setShortcutEnabled(False)  # QLineEdit'te yok; global ekleyelim
        QAction(self).setShortcut   # no-op to avoid lint

        # Global Ctrl+F arama odağı
        self._sc_find = QAction(self); self._sc_find.setShortcut(QKeySequence.StandardKey.Find)
        self._sc_find.triggered.connect(lambda: self.txtAra.setFocus(Qt.FocusReason.ShortcutFocusReason))
        self.addAction(self._sc_find)

        # >>> SADECE GÖRSEL
        self.setObjectName("OgrenciFormuRoot")
        self._apply_visuals()

    # ---------------- Yardımcılar ----------------
    def _alt_grup_guncelle(self, ana):
        self.cmbAlt.clear()
        self.cmbAlt.addItems(ALT_GRUPLAR.get(ana, []))

    def _load_list(self, q: str = ""):
        """Ad/Soyad'a göre filtreli liste yükle (q boşsa hepsi)."""
        # Sıralama açıkken satır ekleme bazı temalarda boyamayı geciktirebilir
        sorting_on = self.liste.isSortingEnabled()
        if sorting_on:
            self.liste.setSortingEnabled(False)

        con = db.get_conn()
        cur = con.cursor()

        if q:
            like = f"%{q}%"
            # 14 Columns query
            sql = """SELECT id, ad, soyad, COALESCE(ogr_no,''), COALESCE(ana_grup,''), COALESCE(alt_grup,''),
                    COALESCE(ogr_tel,''), COALESCE(ogr_mail,''), COALESCE(veli_ad,''), COALESCE(veli_yakinlik,''),
                    COALESCE(veli_tel1,''), COALESCE(veli_tel2,''), COALESCE(veli_mail,''), COALESCE(dogum_tarihi,'')
                    FROM ogrenci
                    WHERE ad LIKE ? OR soyad LIKE ? OR veli_ad LIKE ?
                    ORDER BY id DESC"""
            rows = cur.execute(sql, (like, like, like)).fetchall()
        else:
            sql = """SELECT id, ad, soyad, COALESCE(ogr_no,''), COALESCE(ana_grup,''), COALESCE(alt_grup,''),
                    COALESCE(ogr_tel,''), COALESCE(ogr_mail,''), COALESCE(veli_ad,''), COALESCE(veli_yakinlik,''),
                    COALESCE(veli_tel1,''), COALESCE(veli_tel2,''), COALESCE(veli_mail,''), COALESCE(dogum_tarihi,'')
                    FROM ogrenci
                    ORDER BY id DESC"""
            rows = cur.execute(sql).fetchall()

        self.liste.clearSelection()
        self.liste.setRowCount(0)
        text_brush = self.palette().text()

        for r in rows:
            i = self.liste.rowCount()
            self.liste.insertRow(i)
            # Create items
            for c_idx, val in enumerate(r):
                # r[0] is ID, r[1]... map 1:1 to cols
                it = QTableWidgetItem(str(val) if val is not None else "")
                it.setForeground(text_brush)
                self.liste.setItem(i, c_idx, it)

        # client-side filtre aktifse (DB dokunmadan) uygula
        if self._client_filter_active and self._client_filter_col is not None:
            self._apply_client_filter(self._client_filter_col, self._client_filter_val)

        # Sıralamayı eski haline getir
        if sorting_on:
            self.liste.setSortingEnabled(True)

        self._update_info_label()
        self._update_stats()

    def _temizle(self):
        for w in [self.txtAd, self.txtSoyad, self.txtNo, self.txtVeliAd,
                  self.txtVeliTel1, self.txtVeliTel2, self.txtOgrTel,
                  self.txtOgrMail, self.txtVeliMail]:
            w.clear()
        self.cmbAna.setCurrentIndex(0)
        self._alt_grup_guncelle(self.cmbAna.currentText())
        self.txtKisisel.clear()
        self.dtpDogum.setDate(QDate(2008, 1, 1))
        self.liste.clearSelection()
        self._update_info_label()

    def _clean_tel(self, val):
        """Maskeden gelen boş karakterleri (örn: (5  ) ___) temizler."""
        if not val: return ""
        # Sadece rakamları sayalım
        digits = "".join([c for c in val if c.isdigit()])
        # Eğer sadece maskeden gelen '05' veya '5' varsa (uzunluk < 7 gibi) boş say
        if len(digits) < 7: return ""
        return val.strip()

    def _topla(self):
        return dict(
            ad=self.txtAd.text().strip().title(),
            soyad=self.txtSoyad.text().strip().title(),
            ogr_no=self.txtNo.text().strip(),
            ana_grup=self.cmbAna.currentText(),
            alt_grup=self.cmbAlt.currentText(),
            veli_ad=self.txtVeliAd.text().strip(),
            veli_yakinlik=self.cmbYakin.currentText(),
            veli_tel1=self._clean_tel(self.txtVeliTel1.text()),
            veli_tel2=self._clean_tel(self.txtVeliTel2.text()),
            ogr_tel=self._clean_tel(self.txtOgrTel.text()),
            ogr_mail=self.txtOgrMail.text().strip(),
            veli_mail=self.txtVeliMail.text().strip(),
            dogum_tarihi=self.dtpDogum.date().toString("yyyy-MM-dd"),
            kisisel_bilgiler=self.txtKisisel.toPlainText().strip()
        )

    def _secili_id(self):
        items = self.liste.selectedItems()
        if not items:
            return None
        return int(self.liste.item(items[0].row(), 0).text())

    def _secili_idler(self):
        """Tabloda seçili satırlardaki tüm ID'leri (benzersiz) döndürür."""
        if not self.liste.selectionModel():
            return []
        rows = {idx.row() for idx in self.liste.selectionModel().selectedRows()}
        if not rows:
            oid = self._secili_id()
            return [] if oid is None else [oid]
        ids = []
        for r in sorted(rows):
            it = self.liste.item(r, 0)
            if it and it.text().strip():
                try:
                    ids.append(int(it.text()))
                except ValueError:
                    pass
        return ids

    # ---------------- CRUD ----------------
    def _kaydet(self):
        d = self._topla()
        if not d["ad"] or not d["soyad"]:
            QMessageBox.warning(self, "Eksik", "Ad ve Soyad zorunludur.")
            return

        # Mükerrer Kayıt Kontrolü
        con = db.get_conn(); cur = con.cursor()
        cur.execute("SELECT count(*) FROM ogrenci WHERE ad=? AND soyad=?", (d['ad'], d['soyad']))
        dup_count = cur.fetchone()[0]
        if dup_count > 0:
            resp = QMessageBox.question(self, "Mükerrer Kayıt Uyarısı", 
                                        f"{d['ad']} {d['soyad']} isminde bir öğrenci zaten var.\nYine de kaydetmek istiyor musunuz?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.No:
                return
        cur.execute("""INSERT INTO ogrenci(ad,soyad,ogr_no,ana_grup,alt_grup,veli_ad,veli_yakinlik,
                        veli_tel1,veli_tel2,ogr_tel,ogr_mail,veli_mail,dogum_tarihi,kisisel_bilgiler)
                       VALUES(:ad,:soyad,:ogr_no,:ana_grup,:alt_grup,:veli_ad,:veli_yakinlik,
                        :veli_tel1,:veli_tel2,:ogr_tel,:ogr_mail,:veli_mail,:dogum_tarihi,:kisisel_bilgiler)""", d)
        con.commit()
        audit_manager.log("CREATE", "STUDENT", f"Yeni öğrenci eklendi: {d['ad']} {d['soyad']}")
        self._load_list()
        self._temizle()
        self._refresh_main_dashboard()
        QMessageBox.information(self, "Tamam", "Kayıt eklendi.")

    def _refresh_main_dashboard(self):
        try:
            p = self.parent()
            while p:
                if hasattr(p, "dashboard") and p.dashboard:
                    p.dashboard.refresh_stats()
                    break
                p = p.parent()
        except Exception:
            pass

    def _guncelle(self):
        oid = self._secili_id()
        if not oid:
            QMessageBox.information(self, "Bilgi", "Listeden bir öğrenci seçiniz.")
            return
        d = self._topla(); d["id"] = oid
        con = db.get_conn(); cur = con.cursor()
        cur.execute("""UPDATE ogrenci
                          SET ad=:ad, soyad=:soyad, ogr_no=:ogr_no, ana_grup=:ana_grup, alt_grup=:alt_grup,
                              veli_ad=:veli_ad, veli_yakinlik=:veli_yakinlik, veli_tel1=:veli_tel1, veli_tel2=:veli_tel2,
                              ogr_tel=:ogr_tel, ogr_mail=:ogr_mail, veli_mail=:veli_mail, dogum_tarihi=:dogum_tarihi,
                              kisisel_bilgiler=:kisisel_bilgiler
                        WHERE id=:id""", d)
        con.commit()
        audit_manager.log("UPDATE", "STUDENT", f"Öğrenci güncellendi (ID: {oid})")
        self._load_list()
        self._refresh_main_dashboard()
        QMessageBox.information(self, "Tamam", "Kayıt güncellendi.")

    def _sil(self):
        ids = self._secili_idler()
        if not ids:
            QMessageBox.information(self, "Bilgi", "Listeden en az bir öğrenci seçiniz.")
            return

        adet = len(ids)
        detay = "1 kayıt" if adet == 1 else f"{adet} kayıt"
        resp = QMessageBox.question(
            self, "Onay",
            f"Seçili {detay} ve ilişkili TÜM kayıtları (ödevler, performans vb.) silmek istediğinize emin misiniz?\n"
            "Bu işlem geri alınamaz.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        toplu = (adet >= 10)
        ilerleme = None
        if toplu:
            ilerleme = IlerlemePenceresi("Kayıtlar Siliniyor…")
            ilerleme.show()

        def islem(progress):
            con = db.get_conn()
            cur = con.cursor()
            try:
                cur.execute("PRAGMA foreign_keys = ON;")
                cur.execute("BEGIN")
                CHUNK = 400
                total = len(ids)
                for i in range(0, total, CHUNK):
                    chunk = ids[i:i+CHUNK]
                    q_marks = ",".join("?" for _ in chunk)

                    # 1. Ödev alt satırları ve ödevler
                    try:
                        cur.execute(f"DELETE FROM odev WHERE kume_id IN (SELECT id FROM odev_kume WHERE ogrenci_id IN ({q_marks}))", chunk)
                    except Exception:
                        pass
                    try:
                        cur.execute(f"DELETE FROM odev_satir WHERE kume_id IN (SELECT id FROM odev_kume WHERE ogrenci_id IN ({q_marks}))", chunk)
                    except Exception:
                        pass
                    try:
                        cur.execute(f"DELETE FROM odev_kume WHERE ogrenci_id IN ({q_marks})", chunk)
                    except Exception:
                        pass

                    # 2. İlgili tüm takip ve performans tabloları
                    related_tables = [
                        "ogrenci_kitap",
                        "ogrenci_performans",
                        "ogrenci_perf_gunluk",
                        "ogrenci_perf_hafta_ders",
                        "ogrenci_kitap_ilerleme",
                        "koc_plan",
                        "koc_program",
                        "koc_hedef",
                        "koc_kitaplar",
                        "koc_konu_takip",
                        "deneme_sonuclari",
                        "ogrenci_anket",
                        "odev_takip",
                        "ogrenci_konu_takip",
                        "risk_snapshot",
                        "odev_aktar_log",
                        "whatsapp_log"
                    ]
                    for table in related_tables:
                        try:
                            cur.execute(f"DELETE FROM {table} WHERE ogrenci_id IN ({q_marks})", chunk)
                        except Exception:
                            pass

                    # 3. Ana öğrenci tablosu
                    cur.execute(f"DELETE FROM ogrenci WHERE id IN ({q_marks})", chunk)

                    if progress:
                        done = min(i + CHUNK, total)
                        progress.emit(int(done * 100 / max(1, total)))
                con.commit()
                audit_manager.log("DELETE", "STUDENT", f"{total} öğrenci ve ilişkili kayıtları silindi.")
            except Exception as e:
                try:
                    con.rollback()
                except Exception:
                    pass
                raise e

        def bitti(_):
            if ilerleme:
                ilerleme.close()
            self._load_list()
            self._temizle()
            self._refresh_main_dashboard()
            QMessageBox.information(self, "Tamam", "Silme işlemi tamamlandı.")

        def hata(msg):
            if ilerleme:
                ilerleme.close()
            QMessageBox.critical(self, "Hata", f"Silme sırasında hata oluştu:\n{msg}")

        if toplu:
            arka_planda_calistir(islem, callback=bitti, hata_cb=hata, ilerleme_cb=ilerleme.guncelle)
        else:
            try:
                islem(None)
                bitti(None)
            except Exception as e:
                hata(str(e))

    # ---------------- Excel ----------------
    def _sablon(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Excel Şablonu Kaydet",
                                            "ogrenciler_sablon.xlsx", "Excel (*.xlsx)")
        if not fn:
            return
        dosya = ogrenci_sablon_olustur(Path(fn))
        QMessageBox.information(self, "Hazır", f"Şablon oluşturuldu:\n{dosya}")

    def _excelden_aktar(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Excel Dosyası Seç", "", "Excel (*.xlsx)")
        if not fn:
            return
        ilerleme = IlerlemePenceresi("Excel'den Aktarım"); ilerleme.show()

        def islem(progress):
            df = ogrenci_excel_oku(Path(fn))
            con = db.get_conn(); cur = con.cursor()
            toplam = len(df)
            for i, row in df.iterrows():
                d = row.to_dict()
                cur.execute("""INSERT INTO ogrenci(ad,soyad,ogr_no,ana_grup,alt_grup,veli_ad,veli_yakinlik,
                                veli_tel1,veli_tel2,ogr_tel,ogr_mail,veli_mail,dogum_tarihi,kisisel_bilgiler)
                               VALUES(:ad,:soyad,:ogr_no,:ana_grup,:alt_grup,:veli_ad,:veli_yakinlik,
                                :veli_tel1,:veli_tel2,:ogr_tel,:ogr_mail,:veli_mail,:dogum_tarihi,:kisisel_bilgiler)""", d)
                if toplam:
                    progress.emit(int((i + 1) * 100 / max(1, toplam)))
            con.commit()
            return toplam

        def bitti(_sonuc):
            ilerleme.close()
            self._load_list()
            self._refresh_main_dashboard()
            QMessageBox.information(self, "Tamam", "Aktarım bitti.")

        def hata(msg):
            ilerleme.close()
            QMessageBox.critical(self, "Hata", msg)

        arka_planda_calistir(islem, callback=bitti, hata_cb=hata, ilerleme_cb=ilerleme.guncelle)

    # ---------------- Liste seçimi ----------------
    def _liste_secildi(self):
        it = self.liste.selectedItems()
        if not it:
            return
        oid = int(self.liste.item(it[0].row(), 0).text())
        con = db.get_conn()
        row = con.execute("SELECT * FROM ogrenci WHERE id=?", (oid,)).fetchone()
        if not row:
            return

        self.txtAd.setText(row["ad"] or "")
        self.txtSoyad.setText(row["soyad"] or "")
        self.txtNo.setText(row["ogr_no"] or "")
        self.cmbAna.setCurrentText(row["ana_grup"] or "YKS")
        self._alt_grup_guncelle(self.cmbAna.currentText())
        self.cmbAlt.setCurrentText(row["alt_grup"] or "")
        self.txtVeliAd.setText(row["veli_ad"] or "")
        self.cmbYakin.setCurrentText(row["veli_yakinlik"] or "Diğer")
        self.txtVeliTel1.setText(row["veli_tel1"] or "")
        self.txtVeliTel2.setText(row["veli_tel2"] or "")
        self.txtOgrTel.setText(row["ogr_tel"] or "")
        self.txtOgrMail.setText(row["ogr_mail"] or "")
        self.txtVeliMail.setText(row["veli_mail"] or "")
        try:
            y, m, d = (row["dogum_tarihi"] or "2008-01-01").split("-")
            self.dtpDogum.setDate(QDate(int(y), int(m), int(d)))
        except Exception:
            self.dtpDogum.setDate(QDate(2008, 1, 1))
        self.txtKisisel.setPlainText(row["kisisel_bilgiler"] or "")

    # ---------------- Görsel tema (yerleşimden bağımsız) ----------------
    # ---------------- Görsel tema (yerleşimden bağımsız) ----------------
    def _apply_visuals(self):
        """
        Açık, sade ve modern tema + tablo header hover + satır hover + belirgin ComboBox oku.
        Yerleşime/metriklere dokunmaz.
        """
        from PyQt6.QtWidgets import QHeaderView
        
        # Header hizası (görsel)
        hh = self.liste.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # Standart Açık/Modern Renkler
        bg      = "#f9fafb"
        card    = "#ffffff"
        field   = "#ffffff"
        stroke  = "#e5e7eb"
        text    = "#1f2937"
        subtle  = "#6b7280"
        accent  = "#3b82f6"
        accent2 = "#10b981"
        
        rowAlt  = "#f9fafb"
        selBg   = "#eff6ff"
        selFg   = "#1e3a8a"
        hdrBg   = "#f3f4f6"
        hdrTxt  = "#374151"
        hdrBr   = "#e5e7eb"
        
        # SVG için rengi URL-friendly yap (# -> %23)
        accent_enc = accent.replace('#', '%23')

        # Font ailesi (Sistem fontları öncelikli)
        font_stack = "'.AppleSystemUIFont', 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif"

        qss = f"""
        #OgrenciFormuRoot {{
            background: {bg};
            color: {text};
            font-family: {font_stack};
            font-size: 13px;
        }}
        
        QDialog {{
            background: {bg}; 
            color: {text};
        }}

        #OgrenciFormuRoot QLabel {{
            color: {subtle};
            font-weight: 500;
        }}
        
        #statCard {{
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
        }}
        #statCard:hover {{
            border: 1px solid {accent};
            background-color: #f8fafc;
        }}

        /* Giriş alanları */
        #OgrenciFormuRoot QLineEdit,
        #OgrenciFormuRoot QComboBox,
        #OgrenciFormuRoot QDateEdit,
        #OgrenciFormuRoot QTextEdit {{
            background: {field};
            border: 1px solid {stroke};
            color: #111827;
            border-radius: 6px;
            padding: 8px;
            font-size: 13px;
        }}
        #OgrenciFormuRoot QLineEdit:hover,
        #OgrenciFormuRoot QComboBox:hover,
        #OgrenciFormuRoot QDateEdit:hover,
        #OgrenciFormuRoot QTextEdit:hover {{
            border: 1px solid {subtle};
        }}
        #OgrenciFormuRoot QLineEdit:focus,
        #OgrenciFormuRoot QComboBox:focus,
        #OgrenciFormuRoot QDateEdit:focus,
        #OgrenciFormuRoot QTextEdit:focus {{
            border: 2px solid {accent};
            padding: 7px;
        }}

        /* ComboBox Ok */
        #OgrenciFormuRoot QComboBox::drop-down {{
            width: 30px;
            border: none;
            background: transparent;
        }}
        #OgrenciFormuRoot QComboBox::down-arrow {{
            image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='{accent_enc}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>");
            width: 16px;
            height: 16px;
        }}

        /* Butonlar */
        #OgrenciFormuRoot QPushButton {{
            background: {card};
            color: {text};
            border: 1px solid {stroke};
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
        }}
        #OgrenciFormuRoot QPushButton:hover {{
            background: {rowAlt};
            border-color: #d1d5db;
        }}
        #OgrenciFormuRoot QPushButton#primary {{
            background: {accent};
            color: white;
            border: 1px solid {accent};
        }}
        #OgrenciFormuRoot QPushButton#primary:hover {{
            background: #2563eb;
            border-color: #2563eb;
        }}
        #OgrenciFormuRoot QPushButton#danger {{
            background: #fee2e2;
            color: #ef4444;
            border: 1px solid #fecaca;
        }}
        #OgrenciFormuRoot QPushButton#danger:hover {{
            background: #fecaca;
        }}
        #OgrenciFormuRoot QPushButton#excelSecondary {{
            background: #ecfdf5;
            color: {accent2};
            border: 1px solid #a7f3d0;
        }}
        #OgrenciFormuRoot QPushButton#excelSecondary:hover {{
            background: #d1fae5;
        }}

        /* Tablo */
        #OgrenciFormuRoot QTableWidget {{
            background: {card};
            border: 1px solid {stroke};
            border-radius: 8px;
            gridline-color: {stroke};
            alternate-background-color: {rowAlt};
            selection-background-color: {selBg};
            selection-color: {selFg};
            outline: none;
        }}
        
        #OgrenciFormuRoot QHeaderView::section {{
            background: {hdrBg};
            color: {hdrTxt};
            border: none;
            border-bottom: 2px solid {hdrBr};
            padding: 8px 12px;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
        }}
        
        #OgrenciFormuRoot QTableWidget::item {{
            padding: 4px;
            border-bottom: 1px solid #f3f4f6;
        }}

        /* GroupBox Modernizasyon */
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {stroke};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 24px;
            background: {card};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            top: 0px;
            padding: 0 5px;
            color: {accent};
            background: transparent;
        }}
        """

        # Nesne adlarını ata (CSS seçiciler için)
        self.btnKaydet.setObjectName("primary")
        self.btnSil.setObjectName("danger")
        self.btnExcelSablon.setObjectName("excelSecondary")
        self.btnExcelAktar.setObjectName("excelSecondary")
        self.txtAra.setObjectName("searchBox")

        self.setStyleSheet(qss)

        # Hover tracking
        self.liste.setMouseTracking(True)

    # ---------------- Sağ tık menüsü ----------------
    def _setup_table_context_menu(self):
        self.liste.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.liste.customContextMenuRequested.connect(self._show_list_ctx_menu)

        # Hazır aksiyonlar (Modern Emojili)
        self.act_delete_selected = QAction("🗑️  Seçili Kayıtları Sil", self)
        self.act_delete_selected.setShortcut(QKeySequence.StandardKey.Delete)
        self.act_delete_selected.triggered.connect(self._sil)
        self.liste.addAction(self.act_delete_selected)  # Delete kısayolu tablo odaklıyken çalışsın

        self.act_copy_cell = QAction("📋  Hücreyi Kopyala", self)
        self.act_copy_row = QAction("📑  Satırı Kopyala (TSV)", self)
        self.act_copy_csv = QAction("📊  Seçimi CSV Olarak Kopyala", self)
        self.act_export_selected_csv = QAction("💾  Seçimi CSV'ye Kaydet…", self)

        self.act_filter_value = QAction("🔍  Bu Değere Göre Filtrele", self)
        self.act_clear_filter = QAction("❎  Filtreyi Temizle", self)

        self.act_show_only_selected = QAction("👁️  Sadece Seçili Satırları Göster", self)
        self.act_clear_row_hiding = QAction("🔓  Satır Gizlemeyi Temizle", self)

        self.act_resize_cols = QAction("↔️  Kolonları Genişlet", self)
        self.act_reset_cols = QAction("📏  Genişlikleri Sıfırla", self)

        self.act_select_all = QAction("☑️  Tümünü Seç", self)
        self.act_clear_selection = QAction("⬜  Seçimi Temizle", self)

        self.act_sort_asc = QAction("🔼  Artan Sırala", self)
        self.act_sort_desc = QAction("🔽  Azalan Sırala", self)

        self.act_copy_cell.triggered.connect(self._ctx_copy_cell)
        self.act_copy_row.triggered.connect(self._ctx_copy_row)
        self.act_copy_csv.triggered.connect(self._ctx_copy_csv)
        self.act_export_selected_csv.triggered.connect(self._ctx_export_selected_csv)

        self.act_filter_value.triggered.connect(self._ctx_filter_value)
        self.act_clear_filter.triggered.connect(self._ctx_clear_filter)

        self.act_show_only_selected.triggered.connect(self._ctx_show_only_selected)
        self.act_clear_row_hiding.triggered.connect(self._ctx_clear_row_hiding)

        self.act_resize_cols.triggered.connect(self._ctx_resize_cols)
        self.act_reset_cols.triggered.connect(self._ctx_reset_cols)

        self.act_select_all.triggered.connect(self.liste.selectAll)
        self.act_clear_selection.triggered.connect(self.liste.clearSelection)

        self.act_sort_asc.triggered.connect(lambda: self._ctx_sort(True))
        self.act_sort_desc.triggered.connect(lambda: self._ctx_sort(False))

    def _show_list_ctx_menu(self, pos: QPoint):
        menu = QMenu(self)

        # ---- BOLLUK VE MODERN GÖRÜNÜM ----
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 5px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QMenu::item {
                padding: 8px 24px 8px 12px;
                border-radius: 6px;
                margin: 2px 0;
                color: #334155;
                font-size: 13px;
                font-weight: 500;
            }
            QMenu::item:selected {
                background-color: #eff6ff;
                color: #2563eb;
            }
            QMenu::separator {
                height: 1px;
                background: #f1f5f9;
                margin: 6px 0;
            }
        """)

        menu.addAction(self.act_delete_selected)
        menu.addSeparator()

        menu.addAction(self.act_copy_cell)
        menu.addAction(self.act_copy_row)
        menu.addAction(self.act_copy_csv)
        menu.addAction(self.act_export_selected_csv)
        menu.addSeparator()

        menu.addAction(self.act_filter_value)
        if self._client_filter_active:
            menu.addAction(self.act_clear_filter)
        menu.addSeparator()

        menu.addAction(self.act_show_only_selected)
        menu.addAction(self.act_clear_row_hiding)
        menu.addSeparator()

        menu.addAction(self.act_sort_asc)
        menu.addAction(self.act_sort_desc)
        menu.addSeparator()

        menu.addAction(self.act_resize_cols)
        menu.addAction(self.act_reset_cols)
        menu.addSeparator()

        menu.addAction(self.act_select_all)
        menu.addAction(self.act_clear_selection)

        menu.exec(QCursor.pos())

    # ---- Context menü eylemleri ----
    def _current_cell(self):
        it = self.liste.currentItem()
        if not it:
            return None, None, None
        row = it.row(); col = it.column(); text = it.text()
        return row, col, text

    def _ctx_copy_cell(self):
        _, _, text = self._current_cell()
        if text is None:
            return
        QApplication.clipboard().setText(text)

    def _ctx_copy_row(self):
        it = self.liste.currentItem()
        if not it:
            return
        row = it.row()
        values = []
        for c in range(self.liste.columnCount()):
            item = self.liste.item(row, c)
            values.append("" if item is None else item.text())
        QApplication.clipboard().setText("\t".join(values))  # TSV

    def _ctx_copy_csv(self):
        # Seçili hücreleri CSV olarak kopyala
        sel_ranges = self.liste.selectedRanges()
        if not sel_ranges:
            return
        r = sel_ranges[0]
        lines = []
        for rr in range(r.topRow(), r.bottomRow() + 1):
            vals = []
            for cc in range(r.leftColumn(), r.rightColumn() + 1):
                it = self.liste.item(rr, cc)
                v = "" if it is None else it.text()
                if any(x in v for x in [",", '"', "\n"]):
                    v = '"' + v.replace('"', '""') + '"'
                vals.append(v)
            lines.append(",".join(vals))
        QApplication.clipboard().setText("\n".join(lines))

    def _ctx_export_selected_csv(self):
        ids = self._secili_idler()
        if not ids:
            QMessageBox.information(self, "Bilgi", "Seçili kayıt yok.")
            return
        fn, _ = QFileDialog.getSaveFileName(self, "Seçili Kayıtları Kaydet",
                                            "ogrenciler_secili.csv", "CSV (*.csv)")
        if not fn:
            return
        # Başlık satırı + seçili satırlar
        headers = [self.liste.horizontalHeaderItem(i).text() for i in range(self.liste.columnCount())]
        lines = [",".join(headers)]
        for r in sorted({idx.row() for idx in self.liste.selectionModel().selectedRows()}):
            vals = []
            for c in range(self.liste.columnCount()):
                it = self.liste.item(r, c)
                v = "" if it is None else it.text()
                if any(x in v for x in [",", '"', "\n"]):
                    v = '"' + v.replace('"', '""') + '"'
                vals.append(v)
            lines.append(",".join(vals))
        try:
            Path(fn).write_text("\n".join(lines), encoding="utf-8")
            QMessageBox.information(self, "Tamam", f"Dosya kaydedildi:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yazma hatası: {e}")

    def _ctx_filter_value(self):
        row, col, text = self._current_cell()
        if text is None:
            return
        self._client_filter_active = True
        self._client_filter_col = col
        self._client_filter_val = text
        self._apply_client_filter(col, text)

    def _ctx_clear_filter(self):
        self._client_filter_active = False
        self._client_filter_col = None
        self._client_filter_val = None
        for r in range(self.liste.rowCount()):
            self.liste.setRowHidden(r, False)

    def _apply_client_filter(self, col: int, value: str):
        """DB'ye dokunmadan, tablo üzerinde görünürlük filtresi."""
        for r in range(self.liste.rowCount()):
            it = self.liste.item(r, col)
            visible = (it and it.text() == value)
            self.liste.setRowHidden(r, not visible)

    def _ctx_show_only_selected(self):
        selected_rows = {idx.row() for idx in self.liste.selectionModel().selectedRows()}
        if not selected_rows:
            return
        for r in range(self.liste.rowCount()):
            self.liste.setRowHidden(r, r not in selected_rows)

    def _ctx_clear_row_hiding(self):
        for r in range(self.liste.rowCount()):
            self.liste.setRowHidden(r, False)

    def _ctx_resize_cols(self):
        # İçeriğe göre otomatik genişlet
        from PyQt6.QtWidgets import QHeaderView
        hh = self.liste.horizontalHeader()
        old_modes = [hh.sectionResizeMode(i) for i in range(self.liste.columnCount())]
        for i in range(self.liste.columnCount()):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(self.liste.columnCount()):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

    def _ctx_reset_cols(self):
        from PyQt6.QtWidgets import QHeaderView
        hh = self.liste.horizontalHeader()
        for i in range(self.liste.columnCount()):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            self.liste.setColumnWidth(i, 120)

    def _ctx_sort(self, ascending=True):
        col = self.liste.currentColumn()
        if col < 0: return
        # Sorting açık olduğundan emin ol
        if not self.liste.isSortingEnabled():
             self.liste.setSortingEnabled(True)
        order = Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder
        self.liste.sortItems(col, order)

    # ---------------- küçük UX yardımcıları ----------------
    def _update_info_label(self):
        toplam = self.liste.rowCount()
        secili = len(self.liste.selectionModel().selectedRows()) if self.liste.selectionModel() else 0
        if self._client_filter_active:
            self.lblInfo.setText(f"Toplam: {toplam} • Seçili: {secili} • Filtre: sütun {self._client_filter_col+1}, değer '{self._client_filter_val}'")
        else:
            self.lblInfo.setText(f"Toplam: {toplam} • Seçili: {secili}")

    # ---------------- Dashboard Logic ----------------
    def _update_stats(self):
        try:
            con = db.get_conn(); cur = con.cursor()
            
            tot = cur.execute("SELECT count(*) FROM ogrenci").fetchone()[0]
            self.lbl_stat_total.setText(str(tot))
            
            yks = cur.execute("SELECT count(*) FROM ogrenci WHERE ana_grup='YKS'").fetchone()[0]
            self.lbl_stat_yks.setText(str(yks))
            
            lgs = cur.execute("SELECT count(*) FROM ogrenci WHERE ana_grup='LGS'").fetchone()[0]
            self.lbl_stat_lgs.setText(str(lgs))
            
            # Doğum Günü (Bugün)
            from datetime import date
            today_str = date.today().strftime("%m-%d")
            # sqlite substr(dogum_tarihi, 6, 5) -> "MM-DD"
            bd = cur.execute("SELECT count(*) FROM ogrenci WHERE substr(dogum_tarihi, 6, 5) = ?", (today_str,)).fetchone()[0]
            
            if bd > 0:
                self.lbl_stat_bday.setText(f"{bd} Kişi! 🎉")
                self.lbl_stat_bday.setStyleSheet("font-size: 20px; font-weight: 800; color: #e11d48;") # Pembe/Kırmızı
            else:
                self.lbl_stat_bday.setText("Yok")
                self.lbl_stat_bday.setStyleSheet("font-size: 20px; font-weight: 800; color: #94a3b8;")
        except: pass