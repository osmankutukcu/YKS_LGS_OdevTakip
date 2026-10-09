# -*- coding: utf-8 -*-
"""
WhatsApp Gönderim ve İletişim Günlüğü (WhatsappLogRaporu)
Ultra-Modern, KPI Destekli, Profesyonel WhatsApp Log Takip ve Denetim Merkezi:
- Üst KPI Özet Şeridi (Toplam Gönderim, Başarılı, Başarısız, Ulaşılan Kişi)
- Akıllı Tarih Filtreleri (Tüm Zamanlar, Bu Yıl, Son 30 Gün, Son 7 Gün)
- Görsel Durum Rozetleri (✅ Başarılı / ❌ Başarısız)
- Canlı Arama ve Öğrenci Bazlı Mesaj Sayacı
- Detaylı Mesaj Önizleme ve Tek Tıkla Yeniden Gönderim (WhatsApp)
- CSV Dışa Aktarma ve Toplu Hata Telafisi
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QTableWidget, QTableWidgetItem, QDateEdit, QFileDialog, QCheckBox,
    QMessageBox, QListWidgetItem, QLineEdit, QMenu, QFrame, QTextEdit,
    QSplitter, QHeaderView, QApplication
)
from PyQt6.QtCore import QDate, Qt, QPoint, QUrl
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QCursor
import csv
import re
import urllib.parse
import db

def _norm_phone(num: str) -> str:
    """Telefonu 10 haneli standart Türk mobil formatına normalize eder."""
    if not num:
        return ""
    digits = "".join(ch for ch in str(num) if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return digits

def _format_display_phone(num: str) -> str:
    """Okunabilir telefon formatı üretir: +90 (5XX) XXX XX XX"""
    if not num:
        return "—"
    digits = "".join(ch for ch in str(num) if ch.isdigit())
    if len(digits) == 10:
        return f"+90 ({digits[:3]}) {digits[3:6]} {digits[6:8]} {digits[8:]}"
    elif len(digits) == 11 and digits.startswith("0"):
        d = digits[1:]
        return f"+90 ({d[:3]}) {d[3:6]} {d[6:8]} {d[8:]}"
    elif len(digits) == 12 and digits.startswith("90"):
        d = digits[2:]
        return f"+90 ({d[:3]}) {d[3:6]} {d[6:8]} {d[8:]}"
    return str(num)


class WhatsappLogRaporu(QWidget):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("📋 WhatsApp Gönderim ve İletişim Günlüğü")
        self.resize(1180, 740)

        # Dahili veri önbellekleri
        self._ogr_kaynak: list[dict] = []
        self._checked_ids: set[int] = set()
        self._phone_index: dict[str, tuple[int, str]] = {}
        self._id_to_name: dict[int, str] = {}
        self._cached_rows: list[dict] = []

        self._apply_styling()
        self._init_ui()
        self._load_metadata()
        self._init_date_range()
        self._getir()

    def _apply_styling(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                color: #334155;
            }
            QFrame#HeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #0f172a);
                border-radius: 12px;
                padding: 14px;
            }
            QFrame#HeaderCard QLabel {
                background: transparent;
                border: none;
            }
            QFrame#KpiCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px 14px;
            }
            QFrame#KpiCard:hover {
                border-color: #cbd5e1;
            }
            QFrame#FilterCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px 14px;
            }
            QFrame#DetailCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 12px;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff;
                selection-color: #1e3a8a;
            }
            QTableWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #f8fafc;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                font-weight: 700;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 8px 10px;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 7px 10px;
                border-bottom: 1px solid #f1f5f9;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #f8fafc;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
            }
            QLineEdit, QDateEdit {
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus, QDateEdit:focus {
                border-color: #3b82f6;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
                font-size: 12.5px;
                color: #475569;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #94a3b8;
                color: #1e293b;
            }
            QPushButton#btnPrimary {
                background-color: #2563eb;
                color: white;
                border: none;
            }
            QPushButton#btnPrimary:hover {
                background-color: #1d4ed8;
            }
            QPushButton#btnSuccess {
                background-color: #10b981;
                color: white;
                border: none;
            }
            QPushButton#btnSuccess:hover {
                background-color: #059669;
            }
            QPushButton#btnPreset {
                padding: 5px 10px;
                font-size: 11.5px;
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
            }
            QPushButton#btnPreset:hover {
                background-color: #e2e8f0;
                border-color: #cbd5e1;
            }
            QCheckBox {
                font-size: 12.5px;
                font-weight: 600;
                color: #475569;
            }
        """)

    def _init_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(16, 16, 16, 16)
        root_lay.setSpacing(12)

        # 1. BAŞLIK KARTI
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        h_lay = QHBoxLayout(header_card)
        h_lay.setContentsMargins(14, 10, 14, 10)

        left_h = QVBoxLayout()
        left_h.setSpacing(3)
        lbl_t = QLabel("📋 WhatsApp Gönderim ve İletişim Günlüğü")
        lbl_t.setStyleSheet("color: white; font-size: 18px; font-weight: 800;")
        lbl_sub = QLabel("Öğrenci ve velilere iletilen bildirim, ödev hatırlatma ve randevu mesajlarının merkezi denetim kaydı")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 12px;")
        left_h.addWidget(lbl_t)
        left_h.addWidget(lbl_sub)
        h_lay.addLayout(left_h)

        h_lay.addStretch()

        self.btnCsv = QPushButton("📥 CSV Dışa Aktar")
        self.btnCsv.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnCsv.clicked.connect(self._export_csv)
        h_lay.addWidget(self.btnCsv)

        self.btnRefreshAll = QPushButton("🔄 Günlüğü Yenile")
        self.btnRefreshAll.setObjectName("btnPrimary")
        self.btnRefreshAll.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnRefreshAll.clicked.connect(self._getir)
        h_lay.addWidget(self.btnRefreshAll)

        root_lay.addWidget(header_card)

        # 2. KPI KARTLARI ŞERİDİ
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.card_total = self._create_kpi_card("📨 Toplam Gönderim", "0", "#2563eb", "Kayıtlı bildirim")
        self.card_success = self._create_kpi_card("✅ Başarılı İletim", "0", "#16a34a", "%0 başarı oranı")
        self.card_fail = self._create_kpi_card("❌ Hatalı / Başarısız", "0", "#dc2626", "Tekrar denenmeli")
        self.card_unique = self._create_kpi_card("👥 Ulaşılan Numara", "0", "#8b5cf6", "Farklı alıcı")

        kpi_row.addWidget(self.card_total)
        kpi_row.addWidget(self.card_success)
        kpi_row.addWidget(self.card_fail)
        kpi_row.addWidget(self.card_unique)
        root_lay.addLayout(kpi_row)

        # 3. FİLTRE VE ARAMA BARI
        filter_card = QFrame()
        filter_card.setObjectName("FilterCard")
        f_lay = QHBoxLayout(filter_card)
        f_lay.setContentsMargins(10, 8, 10, 8)
        f_lay.setSpacing(8)

        # Tarih filtre butonları
        btn_all_time = QPushButton("🌟 Tüm Zamanlar")
        btn_all_time.setObjectName("btnPreset")
        btn_all_time.clicked.connect(lambda: self._set_date_preset("all"))
        f_lay.addWidget(btn_all_time)

        btn_this_year = QPushButton("📅 Bu Yıl")
        btn_this_year.setObjectName("btnPreset")
        btn_this_year.clicked.connect(lambda: self._set_date_preset("year"))
        f_lay.addWidget(btn_this_year)

        btn_last_30 = QPushButton("🗓️ Son 30 Gün")
        btn_last_30.setObjectName("btnPreset")
        btn_last_30.clicked.connect(lambda: self._set_date_preset("30d"))
        f_lay.addWidget(btn_last_30)

        btn_last_7 = QPushButton("⚡ Son 7 Gün")
        btn_last_7.setObjectName("btnPreset")
        btn_last_7.clicked.connect(lambda: self._set_date_preset("7d"))
        f_lay.addWidget(btn_last_7)

        f_lay.addSpacing(6)
        f_lay.addWidget(QLabel("Tarih:"))
        self.dtpBas = QDateEdit()
        self.dtpBas.setCalendarPopup(True)
        self.dtpBas.setDisplayFormat("dd.MM.yyyy")
        self.dtpBas.dateChanged.connect(self._getir)
        f_lay.addWidget(self.dtpBas)

        f_lay.addWidget(QLabel("—"))
        self.dtpBit = QDateEdit()
        self.dtpBit.setCalendarPopup(True)
        self.dtpBit.setDisplayFormat("dd.MM.yyyy")
        self.dtpBit.dateChanged.connect(self._getir)
        f_lay.addWidget(self.dtpBit)

        f_lay.addSpacing(8)
        self.chkFail = QCheckBox("Sadece Hatalılar")
        self.chkFail.toggled.connect(self._getir)
        f_lay.addWidget(self.chkFail)

        f_lay.addStretch()

        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("🔍 Öğrenci, numara veya mesaj ara...")
        self.txtSearch.setFixedWidth(240)
        self.txtSearch.textChanged.connect(self._apply_table_search)
        f_lay.addWidget(self.txtSearch)

        root_lay.addWidget(filter_card)

        # 4. ORTA BÖLÜM: SOL (ÖĞRENCİ LİSTESİ) + SAĞ (TABLO VE MESAJ DETAYI)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol Panel: Öğrenciler
        left_widget = QWidget()
        l_lay = QVBoxLayout(left_widget)
        l_lay.setContentsMargins(0, 0, 0, 0)
        l_lay.setSpacing(6)

        l_top = QHBoxLayout()
        l_lbl = QLabel("👥 Öğrenci Filtresi")
        l_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #1e293b;")
        l_top.addWidget(l_lbl)
        l_top.addStretch()
        l_lay.addLayout(l_top)

        self.txtOgrAra = QLineEdit()
        self.txtOgrAra.setPlaceholderText("Öğrenci adı yazın...")
        self.txtOgrAra.textChanged.connect(self._filtre_ogrenciler)
        l_lay.addWidget(self.txtOgrAra)

        self.lstOgr = QListWidget()
        self.lstOgr.setSelectionMode(self.lstOgr.SelectionMode.ExtendedSelection)
        self.lstOgr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lstOgr.customContextMenuRequested.connect(self._show_left_menu)
        self.lstOgr.itemChanged.connect(self._on_ogr_check_changed)
        l_lay.addWidget(self.lstOgr, stretch=1)

        l_btns = QHBoxLayout()
        self.btnSelAll = QPushButton("Tümünü Seç")
        self.btnSelAll.clicked.connect(lambda: self._check_all_students(True))
        self.btnSelNone = QPushButton("Temizle")
        self.btnSelNone.clicked.connect(lambda: self._check_all_students(False))
        l_btns.addWidget(self.btnSelAll)
        l_btns.addWidget(self.btnSelNone)
        l_lay.addLayout(l_btns)

        left_widget.setMinimumWidth(220)
        splitter.addWidget(left_widget)

        # Sağ Panel: Tablo + Alt Mesaj Detay Paneli
        right_widget = QWidget()
        r_lay = QVBoxLayout(right_widget)
        r_lay.setContentsMargins(0, 0, 0, 0)
        r_lay.setSpacing(8)

        # Tablo
        self.tab = QTableWidget(0, 6)
        self.tab.setHorizontalHeaderLabels([
            "Tarih & Saat", "Durum", "Öğrenci",
            "Telefon / Alıcı", "Mesaj Önizleme", "Log ID"
        ])
        self.tab.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tab.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tab.setAlternatingRowColors(True)
        self.tab.setSortingEnabled(True)
        self.tab.verticalHeader().setVisible(False)
        self.tab.horizontalHeader().setStretchLastSection(False)
        self.tab.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tab.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self._show_table_menu)
        r_lay.addWidget(self.tab, stretch=3)

        # Alt Mesaj Detay Kutusu
        detail_card = QFrame()
        detail_card.setObjectName("DetailCard")
        d_lay = QVBoxLayout(detail_card)
        d_lay.setContentsMargins(10, 8, 10, 8)
        d_lay.setSpacing(6)

        d_head = QHBoxLayout()
        self.lbl_detail_title = QLabel("💬 Seçili Mesaj Detayı")
        self.lbl_detail_title.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        d_head.addWidget(self.lbl_detail_title)

        d_head.addStretch()

        self.btnCopyMsg = QPushButton("📋 Mesajı Kopyala")
        self.btnCopyMsg.setEnabled(False)
        self.btnCopyMsg.clicked.connect(self._copy_message)
        d_head.addWidget(self.btnCopyMsg)

        self.btnResendMsg = QPushButton("📲 WhatsApp'la Aç / Gönder")
        self.btnResendMsg.setObjectName("btnSuccess")
        self.btnResendMsg.setEnabled(False)
        self.btnResendMsg.clicked.connect(self._resend_single)
        d_head.addWidget(self.btnResendMsg)

        d_lay.addLayout(d_head)

        self.txtDetail = QTextEdit()
        self.txtDetail.setReadOnly(True)
        self.txtDetail.setMaximumHeight(100)
        self.txtDetail.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 12.5px; padding: 6px;")
        self.txtDetail.setPlaceholderText("Mesajın tam metnini görüntülemek için yukarıdaki tablodan bir satıra tıklayın...")
        d_lay.addWidget(self.txtDetail)

        r_lay.addWidget(detail_card, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        root_lay.addWidget(splitter, stretch=1)

    def _create_kpi_card(self, title: str, val: str, color: str, sub: str) -> QFrame:
        card = QFrame()
        card.setObjectName("KpiCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(12, 8, 12, 8)
        c_lay.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #64748b;")
        c_lay.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setObjectName("ValLabel")
        lbl_v.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {color};")
        c_lay.addWidget(lbl_v)

        lbl_s = QLabel(sub)
        lbl_s.setObjectName("SubLabel")
        lbl_s.setStyleSheet("font-size: 10.5px; color: #94a3b8;")
        c_lay.addWidget(lbl_s)

        return card

    def _update_kpi(self, card: QFrame, val: str, sub: str = ""):
        lbl_v = card.findChild(QLabel, "ValLabel")
        if lbl_v:
            lbl_v.setText(val)
        if sub:
            lbl_s = card.findChild(QLabel, "SubLabel")
            if lbl_s:
                lbl_s.setText(sub)

    # ==========================================
    # VERİ YÜKLEME & EŞLEŞTİRME
    # ==========================================

    def _load_metadata(self):
        """Öğrenci verilerini ve telefon eşleştirme indeksini hazırlar."""
        con = db.get_conn()
        self._ogr_kaynak.clear()
        self._phone_index.clear()
        self._id_to_name.clear()

        q = "SELECT id, ad, soyad, veli_tel1, veli_tel2, ogr_tel FROM ogrenci WHERE aktif = 1 ORDER BY ad, soyad"
        try:
            for r in con.execute(q).fetchall():
                oid = int(r["id"])
                ad = str(r["ad"] or "").strip()
                soy = str(r["soyad"] or "").strip()
                adsoyad = f"{ad} {soy}".strip() or f"Öğrenci #{oid}"

                self._ogr_kaynak.append({"id": oid, "text": adsoyad})
                self._id_to_name[oid] = adsoyad

                for col in ("veli_tel1", "veli_tel2", "ogr_tel"):
                    raw = str(r[col] or "").replace(";", ",")
                    for p in raw.split(","):
                        norm = _norm_phone(p)
                        if norm and norm not in self._phone_index:
                            self._phone_index[norm] = (oid, adsoyad)
        except Exception as e:
            print("Öğrenci metadata yükleme hatası:", e)

        self._populate_student_list()

    def _populate_student_list(self, filter_txt: str = ""):
        self.lstOgr.blockSignals(True)
        self.lstOgr.clear()
        fl = (filter_txt or "").strip().lower()
        for k in self._ogr_kaynak:
            if fl and fl not in k["text"].lower():
                continue
            it = QListWidgetItem(k["text"])
            it.setData(Qt.ItemDataRole.UserRole, k["id"])
            it.setFlags(
                it.flags() | Qt.ItemFlag.ItemIsUserCheckable |
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            it.setCheckState(
                Qt.CheckState.Checked if k["id"] in self._checked_ids else Qt.CheckState.Unchecked
            )
            self.lstOgr.addItem(it)
        self.lstOgr.blockSignals(False)

    def _filtre_ogrenciler(self, txt: str):
        self._collect_checked_students()
        self._populate_student_list(txt)

    def _collect_checked_students(self):
        for i in range(self.lstOgr.count()):
            it = self.lstOgr.item(i)
            oid = it.data(Qt.ItemDataRole.UserRole)
            if oid:
                if it.checkState() == Qt.CheckState.Checked:
                    self._checked_ids.add(int(oid))
                else:
                    self._checked_ids.discard(int(oid))

    def _on_ogr_check_changed(self, it: QListWidgetItem):
        self._collect_checked_students()
        self._getir()

    def _check_all_students(self, val: bool):
        self.lstOgr.blockSignals(True)
        state = Qt.CheckState.Checked if val else Qt.CheckState.Unchecked
        for i in range(self.lstOgr.count()):
            self.lstOgr.item(i).setCheckState(state)
        self.lstOgr.blockSignals(False)
        self._collect_checked_students()
        self._getir()

    def _show_left_menu(self, pos: QPoint):
        item = self.lstOgr.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_only = menu.addAction("Sadece bu öğrenciyi seç")
        act_all = menu.addAction("Tümünü seç")
        act_none = menu.addAction("Seçimleri temizle")
        act = menu.exec(self.lstOgr.mapToGlobal(pos))
        if act == act_only:
            self._checked_ids.clear()
            oid = item.data(Qt.ItemDataRole.UserRole)
            if oid:
                self._checked_ids.add(int(oid))
            self._populate_student_list(self.txtOgrAra.text())
            self._getir()
        elif act == act_all:
            self._check_all_students(True)
        elif act == act_none:
            self._check_all_students(False)

    # ==========================================
    # TARİH VE GETİRME MANTIĞI
    # ==========================================

    def _init_date_range(self):
        """Veritabanındaki en eski ve en yeni kayda göre başlangıç tarihini akıllıca belirler."""
        con = db.get_conn()
        try:
            r = con.execute("SELECT MIN(date(COALESCE(zaman, ts))), MAX(date(COALESCE(zaman, ts))) FROM whatsapp_log").fetchone()
            min_date, max_date = r[0], r[1]
            if min_date:
                parts = [int(p) for p in min_date.split("-")]
                self.dtpBas.setDate(QDate(parts[0], parts[1], parts[2]))
            else:
                self.dtpBas.setDate(QDate(2025, 1, 1))
            
            self.dtpBit.setDate(QDate.currentDate().addDays(1))
        except Exception:
            self.dtpBas.setDate(QDate(2025, 1, 1))
            self.dtpBit.setDate(QDate.currentDate().addDays(1))

    def _set_date_preset(self, preset: str):
        self.dtpBas.blockSignals(True)
        self.dtpBit.blockSignals(True)
        today = QDate.currentDate()

        if preset == "all":
            self.dtpBas.setDate(QDate(2020, 1, 1))
            self.dtpBit.setDate(today.addDays(1))
        elif preset == "year":
            self.dtpBas.setDate(QDate(today.year(), 1, 1))
            self.dtpBit.setDate(today.addDays(1))
        elif preset == "30d":
            self.dtpBas.setDate(today.addDays(-30))
            self.dtpBit.setDate(today.addDays(1))
        elif preset == "7d":
            self.dtpBas.setDate(today.addDays(-7))
            self.dtpBit.setDate(today.addDays(1))

        self.dtpBas.blockSignals(False)
        self.dtpBit.blockSignals(False)
        self._getir()

    def _resolve_student(self, row: dict) -> tuple[int | None, str]:
        """Log satırından öğrenci kimliğini ve adını çözer."""
        # 1. Doğrudan ogrenci_id
        oid = row.get("ogrenci_id")
        if oid and int(oid) in self._id_to_name:
            return int(oid), self._id_to_name[int(oid)]

        # 2. ogrenci_adsoyad kolonu
        adsoyad = (row.get("ogrenci_adsoyad") or "").strip()
        if adsoyad:
            return None, adsoyad

        # 3. Telefon numarasından eşleme
        raw_num = row.get("numara") or row.get("numaralar") or ""
        for p in str(raw_num).replace(";", ",").split(","):
            norm = _norm_phone(p)
            if norm in self._phone_index:
                return self._phone_index[norm]

        # 4. Mesaj içeriğinden isim çıkarma (Koçluk Raporu vb.)
        msg = row.get("mesaj") or row.get("mesaj_onizleme") or ""
        m = re.search(r"Öğrenci:\s*([^\n\r*]+)", msg, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip()
            if extracted:
                return None, extracted

        return None, "—"

    def _getir(self):
        """Veritabanından log kayıtlarını okur ve tabloyu doldurur."""
        con = db.get_conn()
        bas = self.dtpBas.date().toString("yyyy-MM-dd")
        bit = self.dtpBit.date().toString("yyyy-MM-dd")

        sql = """
            SELECT id, 
                   COALESCE(zaman, ts, datetime('now')) AS tarihs,
                   ogrenci_id, numara, numaralar,
                   mesaj_onizleme, mesaj,
                   durum, hata,
                   COALESCE(gonderilen, 0) AS gonderilen,
                   COALESCE(basarisiz, 0) AS basarisiz,
                   ogrenci_adsoyad
            FROM whatsapp_log
            WHERE date(COALESCE(zaman, ts)) BETWEEN date(?) AND date(?)
            ORDER BY id DESC
        """
        try:
            raw_rows = con.execute(sql, (bas, bit)).fetchall()
        except Exception as e:
            print("Log çekme hatası:", e)
            raw_rows = []

        self._cached_rows.clear()
        total_count = 0
        success_count = 0
        fail_count = 0
        unique_phones = set()

        for r in raw_rows:
            d = dict(r)
            oid, adsoyad = self._resolve_student(d)
            d["resolved_oid"] = oid
            d["resolved_name"] = adsoyad

            durum_str = str(d.get("durum") or "").upper()
            gonderilen = int(d.get("gonderilen") or 0)
            basarisiz = int(d.get("basarisiz") or 0)

            # Başarı/Hata durumu hesapla
            if durum_str in ("OK", "GÖNDERİLDİ", "SUCCESS") or (gonderilen > 0 and basarisiz == 0):
                is_success = True
            elif basarisiz > 0 or durum_str in ("HATA", "FAIL", "ERROR"):
                is_success = False
            else:
                # Varsayılan olarak durum OK kabul edilir (eski loglar)
                is_success = True

            d["is_success"] = is_success

            # Öğrenci filtresi (Sol listeden seçilmişse)
            if self._checked_ids:
                if oid is not None and oid not in self._checked_ids:
                    continue
                elif oid is None:
                    # İsim üzerinden kontrol
                    matched = any(
                        self._id_to_name.get(sid, "").lower() == adsoyad.lower()
                        for sid in self._checked_ids
                    )
                    if not matched:
                        continue

            if self.chkFail.isChecked() and is_success:
                continue

            total_count += 1
            if is_success:
                success_count += 1
            else:
                fail_count += 1

            num_str = d.get("numara") or d.get("numaralar") or ""
            norm_p = _norm_phone(num_str)
            if norm_p:
                unique_phones.add(norm_p)

            self._cached_rows.append(d)

        # KPI Kartlarını Güncelle
        rate = int((success_count / total_count * 100)) if total_count > 0 else 0
        self._update_kpi(self.card_total, str(total_count), f"{len(raw_rows)} toplam aralıkta")
        self._update_kpi(self.card_success, str(success_count), f"%{rate} başarı oranı")
        self._update_kpi(self.card_fail, str(fail_count), "İletilemeyen bildirim")
        self._update_kpi(self.card_unique, str(len(unique_phones)), "Farklı telefon numarası")

        self._render_table()

    def _render_table(self):
        """Önbellekteki kayıtları tabloya işler."""
        self.tab.setSortingEnabled(False)
        self.tab.setRowCount(0)

        search_txt = self.txtSearch.text().strip().lower()

        for d in self._cached_rows:
            # Arama filtresi
            tarih_txt = str(d.get("tarihs") or "")
            name_txt = str(d.get("resolved_name") or "")
            num_txt = str(d.get("numara") or d.get("numaralar") or "")
            msg_txt = str(d.get("mesaj") or d.get("mesaj_onizleme") or "")

            if search_txt:
                haystack = f"{tarih_txt} {name_txt} {num_txt} {msg_txt}".lower()
                if search_txt not in haystack:
                    continue

            i = self.tab.rowCount()
            self.tab.insertRow(i)

            # 1. Tarih
            it_date = QTableWidgetItem(tarih_txt)
            it_date.setData(Qt.ItemDataRole.UserRole, d)
            self.tab.setItem(i, 0, it_date)

            # 2. Durum Rozeti
            is_success = d["is_success"]
            if is_success:
                it_stat = QTableWidgetItem("✅ Başarılı")
                it_stat.setForeground(QColor("#16a34a"))
            else:
                it_stat = QTableWidgetItem("❌ Hata")
                it_stat.setForeground(QColor("#dc2626"))
            it_stat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tab.setItem(i, 1, it_stat)

            # 3. Öğrenci Adı
            it_name = QTableWidgetItem(name_txt)
            it_name.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.tab.setItem(i, 2, it_name)

            # 4. Telefon Numarası
            disp_num = _format_display_phone(num_txt)
            it_phone = QTableWidgetItem(disp_num)
            it_phone.setForeground(QColor("#475569"))
            self.tab.setItem(i, 3, it_phone)

            # 5. Mesaj Önizleme
            clean_msg = " ".join(msg_txt.split())
            it_msg = QTableWidgetItem(clean_msg[:120] + ("..." if len(clean_msg) > 120 else ""))
            it_msg.setToolTip(msg_txt)
            self.tab.setItem(i, 4, it_msg)

            # 6. Log ID
            it_id = QTableWidgetItem(str(d.get("id") or ""))
            it_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_id.setForeground(QColor("#94a3b8"))
            self.tab.setItem(i, 5, it_id)

        self.tab.setSortingEnabled(True)
        self.tab.resizeColumnToContents(0)
        self.tab.resizeColumnToContents(1)
        self.tab.resizeColumnToContents(2)
        self.tab.resizeColumnToContents(3)
        self.tab.resizeColumnToContents(5)

        # Temizle detay kutusu
        self.txtDetail.clear()
        self.btnCopyMsg.setEnabled(False)
        self.btnResendMsg.setEnabled(False)

    def _apply_table_search(self):
        self._render_table()

    # ==========================================
    # SEÇİM & MESAJ DETAYLARI
    # ==========================================

    def _on_table_selection_changed(self):
        rows = self.tab.selectedItems()
        if not rows:
            self.txtDetail.clear()
            self.lbl_detail_title.setText("💬 Seçili Mesaj Detayı")
            self.btnCopyMsg.setEnabled(False)
            self.btnResendMsg.setEnabled(False)
            return

        row_idx = self.tab.currentRow()
        it_date = self.tab.item(row_idx, 0)
        if not it_date:
            return

        d: dict = it_date.data(Qt.ItemDataRole.UserRole)
        if not d:
            return

        name = d.get("resolved_name", "—")
        num = _format_display_phone(d.get("numara") or d.get("numaralar") or "")
        tarih = d.get("tarihs", "")
        msg = d.get("mesaj") or d.get("mesaj_onizleme") or "—"
        hata = d.get("hata")

        self.lbl_detail_title.setText(f"💬 Mesaj Detayı: {name} ({num}) — {tarih}")
        
        detail_text = msg
        if hata:
            detail_text += f"\n\n[!] Sistem Hatası: {hata}"

        self.txtDetail.setPlainText(detail_text)
        self.btnCopyMsg.setEnabled(True)
        self.btnResendMsg.setEnabled(True)

    def _copy_message(self):
        text = self.txtDetail.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.btnCopyMsg.setText("✅ Kopyalandı!")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.btnCopyMsg.setText("📋 Mesajı Kopyala"))

    def _resend_single(self):
        row_idx = self.tab.currentRow()
        if row_idx < 0:
            return
        it_date = self.tab.item(row_idx, 0)
        if not it_date:
            return
        d: dict = it_date.data(Qt.ItemDataRole.UserRole)
        if not d:
            return

        num = str(d.get("numara") or d.get("numaralar") or "").strip()
        msg = d.get("mesaj") or d.get("mesaj_onizleme") or ""
        
        if not num:
            QMessageBox.warning(self, "Numara Eksik", "Bu kayıt için telefon numarası bulunamadı.")
            return

        # WhatsApp Web / Desktop Deeplink ile aç
        encoded_msg = urllib.parse.quote(msg)
        clean_num = "".join(ch for ch in num if ch.isdigit())
        url = f"https://api.whatsapp.com/send?phone={clean_num}&text={encoded_msg}"
        QDesktopServices.openUrl(QUrl(url))

    def _show_table_menu(self, pos: QPoint):
        item = self.tab.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_copy = menu.addAction("📋 Mesajı Kopyala")
        act_resend = menu.addAction("📲 WhatsApp ile Aç / Gönder")
        menu.addSeparator()
        act_del = menu.addAction("🗑️ Bu Log Kaydını Sil")

        action = menu.exec(self.tab.mapToGlobal(pos))
        if action == act_copy:
            self._copy_message()
        elif action == act_resend:
            self._resend_single()
        elif action == act_del:
            self._delete_current_log()

    def _delete_current_log(self):
        row_idx = self.tab.currentRow()
        if row_idx < 0:
            return
        it_date = self.tab.item(row_idx, 0)
        if not it_date:
            return
        d: dict = it_date.data(Qt.ItemDataRole.UserRole)
        if not d:
            return

        log_id = d.get("id")
        ans = QMessageBox.question(
            self, "Kaydı Sil", 
            f"#{log_id} numaralı log kaydı silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            try:
                con = db.get_conn()
                con.execute("DELETE FROM whatsapp_log WHERE id = ?", (log_id,))
                con.commit()
                self._getir()
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kayıt silinemedi: {e}")

    def _export_csv(self):
        fn, _ = QFileDialog.getSaveFileName(self, "CSV Olarak Kaydet", "whatsapp_log_raporu.csv", "CSV Dosyası (*.csv)")
        if not fn:
            return

        try:
            with open(fn, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Log ID", "Tarih & Saat", "Durum", "Öğrenci Adı", "Numara", "Mesaj Metni", "Hata Bilgisi"])
                for d in self._cached_rows:
                    writer.writerow([
                        d.get("id", ""),
                        d.get("tarihs", ""),
                        "Başarılı" if d.get("is_success") else "Hata",
                        d.get("resolved_name", ""),
                        d.get("numara") or d.get("numaralar") or "",
                        d.get("mesaj") or d.get("mesaj_onizleme") or "",
                        d.get("hata") or ""
                    ])
            QMessageBox.information(self, "Başarılı", f"Rapor başarıyla kaydedildi:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"CSV dışa aktarılırken hata oluştu: {e}")