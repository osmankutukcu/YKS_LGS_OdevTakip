# -*- coding: utf-8 -*-
"""
WhatsApp Toplu ve Hızlı Mesajlaşma Merkezi (WhatsappHizliDialog)
Ultra-Modern, Kişiselleştirilmiş Değişken Destekli, Profesyonel Toplu İletişim Stüdyosu:
- Hazır Koçluk Şablonları (Ödev Hatırlatma, Gecikme Uyarısı, Deneme Sınavı, Randevu, Motivasyon)
- Dinamik Kişiselleştirme Değişkenleri: {ad}, {soyad}, {ad_soyad}, {grup}, {hedef}, {tarih}
- Akıllı Öğrenci Filtreleme (Grup/Sınıf bazında, Sadece Gecikenler, Aktif Ödevliler)
- Canlı Alıcı Hesaplayıcı (Veli-1, Veli-2, Öğrenci) ve Karakter/Kelime Sayacı
- İlk Öğrenci İçin Canlı Mesaj Önizleme Kutusu
- Adım Adım İlerleme Çubuğu ve Doğrudan whatsapp_log Veritabanı Entegrasyonu
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QCheckBox, QLineEdit,
    QWidget, QComboBox, QFrame, QSplitter, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QFont, QColor, QCursor, QTextCursor
import datetime
import db

def _norm_num(s: str | None) -> str:
    """Telefonu 10 haneli veya +90 ile standart formata dönüştürür."""
    if not s:
        return ""
    t = "".join(ch for ch in str(s) if ch.isdigit() or ch == "+")
    if t and not t.startswith("+") and len(t) >= 10:
        if t.startswith("0"):
            t = t[1:]
        if len(t) == 10:
            t = "+90" + t
    return t

# Hazır Şablon Kütüphanesi
PRESET_TEMPLATES = [
    {
        "title": "📌 Genel Ödev Hatırlatma",
        "text": (
            "Merhaba {ad},\n"
            "🗓️ {tarih} tarihli haftalık ödev ve soru çözüm hedeflerin sisteme girilmiştir.\n"
            "Hedefin olan *{hedef}* yolunda disiplinle çalışmanı bekliyoruz.\n"
            "✨ Başarılar dileriz!"
        )
    },
    {
        "title": "⚠️ Geciken Ödev Bildirimi",
        "text": (
            "Sayın Velimiz ve Sevgili {ad},\n"
            "Sistemimizde teslim tarihi geçmiş tamamlanmamış ödevleriniz bulunmaktadır.\n"
            "Lütfen en kısa sürede ödevlerinizi tamamlayıp kontrol ettiriniz.\n"
            "İyi çalışmalar dileriz. 📚"
        )
    },
    {
        "title": "📝 Deneme Sınavı Çağrısı",
        "text": (
            "Sevgili {ad},\n"
            "Haftalık genel deneme sınavımız planlanan gün ve saatte uygulanacaktır.\n"
            "Optik form ve sınav salonunda zamanında hazır bulunman önemle rica olunur. 🎯"
        )
    },
    {
        "title": "🗓️ Koçluk Randevu Hatırlatması",
        "text": (
            "Merhaba {ad},\n"
            "Haftalık bireysel koçluk görüşmemiz belirlenen saatte gerçekleşecektir.\n"
            "Çözülen soru defterin ve kitaplarınla birlikte hazır olmanı rica ederiz. ⏳"
        )
    },
    {
        "title": "✨ Motivasyon ve Takdir Mesajı",
        "text": (
            "Tebrikler {ad}! 👏\n"
            "Bu hafta gösterdiğin gayret ve ödev tamamlama performansın takdire şayan.\n"
            "Aynı azim ve inançla hedefine doğru adım adım ilerlemeye devam! 🌟"
        )
    },
    {
        "title": "💬 Özel / Boş Şablon",
        "text": ""
    }
]

ROLE_STUDENT_DATA = Qt.ItemDataRole.UserRole + 1


class WhatsappHizliDialog(QDialog):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("💬 WhatsApp Toplu ve Hızlı Mesajlaşma Merkezi")
        self.resize(1120, 720)
        self.setMinimumSize(980, 640)

        self._all_students: list[dict] = []
        self._is_sending = False
        self._stop_requested = False

        self._apply_styling()
        self._init_ui()
        self._load_students()
        self._on_template_selected(0)
        self._update_preview()

    def _apply_styling(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
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
            QFrame#StatCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 8px 14px;
            }
            QFrame#BoxCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 12px;
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
            QLineEdit, QTextEdit, QComboBox {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
                color: #1e293b;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
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
            QPushButton#btnSend {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                font-size: 14px;
                font-weight: 700;
                padding: 10px 22px;
            }
            QPushButton#btnSend:hover {
                background-color: #1d4ed8;
            }
            QPushButton#btnStop {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                padding: 10px 18px;
            }
            QPushButton#btnStop:hover {
                background-color: #dc2626;
            }
            QPushButton#btnTag {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                color: #1e40af;
                padding: 3px 7px;
                font-size: 11px;
                font-weight: 700;
                border-radius: 4px;
            }
            QPushButton#btnTag:hover {
                background-color: #dbeafe;
            }
            QPushButton#btnEmoji {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                padding: 3px 6px;
                font-size: 12px;
                border-radius: 4px;
            }
            QPushButton#btnEmoji:hover {
                background-color: #e2e8f0;
            }
            QPushButton#btnQuickAction {
                padding: 5px 8px;
                font-size: 11.5px;
                font-weight: 600;
            }
            QCheckBox {
                font-size: 12.5px;
                font-weight: 600;
                color: #334155;
            }
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                text-align: center;
                background-color: #f1f5f9;
                height: 18px;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 5px;
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
        lbl_t = QLabel("💬 WhatsApp Toplu ve Hızlı Mesajlaşma Merkezi")
        lbl_t.setStyleSheet("color: white; font-size: 18px; font-weight: 800;")
        lbl_sub = QLabel("Öğrenci ve velilere kişiselleştirilmiş değişkenlerle toplu duyuru, ödev hatırlatma ve randevu bildirim stüdyosu")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 12px;")
        left_h.addWidget(lbl_t)
        left_h.addWidget(lbl_sub)
        h_lay.addLayout(left_h)

        h_lay.addStretch()

        root_lay.addWidget(header_card)

        # 2. ÜST İSTATİSTİK ŞERİDİ
        stat_row = QHBoxLayout()
        stat_row.setSpacing(10)

        self.card_total = self._create_stat_chip("👥 Toplam Öğrenci", "0", "#2563eb")
        self.card_selected = self._create_stat_chip("🎯 Seçilen Öğrenci", "0", "#16a34a")
        self.card_recipients = self._create_stat_chip("📱 Hedef Alıcı Numarası", "0", "#8b5cf6")

        stat_row.addWidget(self.card_total)
        stat_row.addWidget(self.card_selected)
        stat_row.addWidget(self.card_recipients)
        root_lay.addLayout(stat_row)

        # 3. ANA SPLITTER: SOL (ÖĞRENCİ SEÇİMİ) + SAĞ (ŞABLON VE MESAJ STÜDYOSU)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---------- SOL PANEL: ÖĞRENCİ SEÇİMİ ----------
        left_card = QFrame()
        left_card.setObjectName("BoxCard")
        l_lay = QVBoxLayout(left_card)
        l_lay.setContentsMargins(10, 10, 10, 10)
        l_lay.setSpacing(8)

        lbl_l_title = QLabel("👥 Öğrenci Seçim ve Filtreleme")
        lbl_l_title.setStyleSheet("font-weight: 800; font-size: 13.5px; color: #1e293b;")
        l_lay.addWidget(lbl_l_title)

        # Arama & Grup Filtresi
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self.txtSearch = QLineEdit()
        self.txtSearch.setPlaceholderText("🔍 Ad, soyad veya numara ara...")
        self.txtSearch.textChanged.connect(self._apply_student_filters)
        filter_row.addWidget(self.txtSearch, stretch=2)

        self.cmbGroup = QComboBox()
        self.cmbGroup.addItem("Tüm Gruplar")
        self.cmbGroup.currentIndexChanged.connect(self._apply_student_filters)
        filter_row.addWidget(self.cmbGroup, stretch=1)
        l_lay.addLayout(filter_row)

        # Hızlı Seçim Butonları
        quick_btns = QHBoxLayout()
        quick_btns.setSpacing(5)
        self.btnSelectAll = QPushButton("🌟 Tümünü Seç")
        self.btnSelectAll.setObjectName("btnQuickAction")
        self.btnSelectAll.clicked.connect(lambda: self._check_all_students(True))
        self.btnSelectOverdue = QPushButton("⚠️ Gecikenler")
        self.btnSelectOverdue.setObjectName("btnQuickAction")
        self.btnSelectOverdue.clicked.connect(self._select_overdue_students)
        self.btnClearSelection = QPushButton("🧹 Temizle")
        self.btnClearSelection.setObjectName("btnQuickAction")
        self.btnClearSelection.clicked.connect(lambda: self._check_all_students(False))

        quick_btns.addWidget(self.btnSelectAll)
        quick_btns.addWidget(self.btnSelectOverdue)
        quick_btns.addWidget(self.btnClearSelection)
        l_lay.addLayout(quick_btns)

        # Öğrenci Listesi
        self.lstStudents = QListWidget()
        self.lstStudents.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lstStudents.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.lstStudents.itemChanged.connect(self._on_student_item_changed)
        self.lstStudents.itemClicked.connect(self._on_student_clicked)
        l_lay.addWidget(self.lstStudents, stretch=1)

        left_card.setMinimumWidth(380)
        splitter.addWidget(left_card)

        # ---------- SAĞ PANEL: MESAJ VE ŞABLON STÜDYOSU ----------
        right_card = QFrame()
        right_card.setObjectName("BoxCard")
        r_lay = QVBoxLayout(right_card)
        r_lay.setContentsMargins(12, 10, 12, 10)
        r_lay.setSpacing(8)

        # 1. Şablon Seçici
        tmpl_row = QHBoxLayout()
        lbl_tmpl = QLabel("📋 Hazır Koçluk Şablonu:")
        lbl_tmpl.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        tmpl_row.addWidget(lbl_tmpl)

        self.cmbTemplate = QComboBox()
        for t in PRESET_TEMPLATES:
            self.cmbTemplate.addItem(t["title"])
        self.cmbTemplate.currentIndexChanged.connect(self._on_template_selected)
        tmpl_row.addWidget(self.cmbTemplate, stretch=1)
        r_lay.addLayout(tmpl_row)

        # 2. Değişken Butonları & Format Barı (2 Satır)
        tags_wrap = QVBoxLayout()
        tags_wrap.setSpacing(5)
        lbl_var = QLabel("✨ Dinamik Değişkenler & Hızlı Araçlar (Tıklayarak Mesaja Ekleyin):")
        lbl_var.setStyleSheet("font-weight: 700; font-size: 11.5px; color: #64748b;")
        tags_wrap.addWidget(lbl_var)

        # Satır 1: Kişiselleştirme Değişkenleri
        tag_row1 = QHBoxLayout()
        tag_row1.setSpacing(4)
        for tag_name in ["{ad}", "{soyad}", "{ad_soyad}", "{grup}", "{hedef}", "{tarih}"]:
            btn_tag = QPushButton(tag_name)
            btn_tag.setObjectName("btnTag")
            btn_tag.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_tag.clicked.connect(lambda _, t=tag_name: self._insert_variable(t))
            tag_row1.addWidget(btn_tag)
        tag_row1.addStretch()
        tags_wrap.addLayout(tag_row1)

        # Satır 2: WhatsApp Formatlama & Emojiler
        tag_row2 = QHBoxLayout()
        tag_row2.setSpacing(4)
        for fmt_lbl, fmt_char in [("*Kalın*", "*"), ("_İtalik_", "_"), ("~Üstüçizili~", "~")]:
            btn_fmt = QPushButton(fmt_lbl)
            btn_fmt.setObjectName("btnTag")
            btn_fmt.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_fmt.clicked.connect(lambda _, f=fmt_char: self._wrap_format(f))
            tag_row2.addWidget(btn_fmt)
        tag_row2.addSpacing(6)
        for em in ["🎯", "📚", "⏳", "✅", "⚠️", "✨", "👏", "📅", "💡"]:
            btn_em = QPushButton(em)
            btn_em.setObjectName("btnEmoji")
            btn_em.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_em.clicked.connect(lambda _, e=em: self._insert_variable(e))
            tag_row2.addWidget(btn_em)
        tag_row2.addStretch()
        tags_wrap.addLayout(tag_row2)

        r_lay.addLayout(tags_wrap)

        # 3. Mesaj Düzenleme Alanı
        self.txtMessage = QTextEdit()
        self.txtMessage.setPlaceholderText("Mesajınızı buraya yazın veya yukarıdaki hazır şablonlardan birini seçin...")
        self.txtMessage.textChanged.connect(self._on_message_text_changed)
        r_lay.addWidget(self.txtMessage, stretch=2)

        # Sayaç Satırı
        count_row = QHBoxLayout()
        self.lblCounts = QLabel("0 Karakter | 0 Kelime")
        self.lblCounts.setStyleSheet("color: #64748b; font-size: 11.5px;")
        count_row.addWidget(self.lblCounts)
        count_row.addStretch()
        r_lay.addLayout(count_row)

        # 4. Alıcı Türü Seçenekleri
        recip_frame = QFrame()
        recip_frame.setStyleSheet("background-color: #f1f5f9; border-radius: 8px; padding: 6px 10px;")
        rf_lay = QHBoxLayout(recip_frame)
        rf_lay.setContentsMargins(10, 6, 10, 6)
        rf_lay.setSpacing(12)
        lbl_rec = QLabel("🎯 <b>Alıcılar:</b>")
        lbl_rec.setStyleSheet("color: #1e293b; font-size: 12px;")
        rf_lay.addWidget(lbl_rec)

        self.chkVeli1 = QCheckBox("Veli-1 (Anne/Baba)")
        self.chkVeli1.setChecked(True)
        self.chkVeli1.toggled.connect(self._recalculate_recipients)
        rf_lay.addWidget(self.chkVeli1)

        self.chkVeli2 = QCheckBox("Veli-2 (Diğer)")
        self.chkVeli2.setChecked(False)
        self.chkVeli2.toggled.connect(self._recalculate_recipients)
        rf_lay.addWidget(self.chkVeli2)

        self.chkOgrenci = QCheckBox("Öğrenci Kendi Telefonu")
        self.chkOgrenci.setChecked(True)
        self.chkOgrenci.toggled.connect(self._recalculate_recipients)
        rf_lay.addWidget(self.chkOgrenci)

        rf_lay.addStretch()
        r_lay.addWidget(recip_frame)

        # 5. Canlı Önizleme Kartı
        preview_box = QFrame()
        preview_box.setStyleSheet("background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 8px 10px;")
        pb_lay = QVBoxLayout(preview_box)
        pb_lay.setContentsMargins(6, 6, 6, 6)
        pb_lay.setSpacing(4)

        self.lbl_preview_title = QLabel("👁️ İlk Seçili Öğrenci İçin Canlı Önizleme:")
        self.lbl_preview_title.setStyleSheet("font-weight: 700; font-size: 11.5px; color: #1e40af;")
        pb_lay.addWidget(self.lbl_preview_title)

        self.txtPreview = QTextEdit()
        self.txtPreview.setReadOnly(True)
        self.txtPreview.setMaximumHeight(95)
        self.txtPreview.setStyleSheet("background-color: #ffffff; border: 1px solid #93c5fd; border-radius: 6px; font-size: 12px; color: #1e3a8a;")
        pb_lay.addWidget(self.txtPreview)

        r_lay.addWidget(preview_box, stretch=1)

        splitter.addWidget(right_card)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        root_lay.addWidget(splitter, stretch=1)

        # 4. ALT GÖNDERİM & İLERLEME ÇUBUĞU
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.progressBar = QProgressBar()
        self.progressBar.setVisible(False)
        bottom_bar.addWidget(self.progressBar, stretch=2)

        self.lblStatus = QLabel("Hazır")
        self.lblStatus.setStyleSheet("font-weight: 600; color: #475569; font-size: 12.5px;")
        bottom_bar.addWidget(self.lblStatus, stretch=2)

        self.btnStop = QPushButton("⏹️ Durdur")
        self.btnStop.setObjectName("btnStop")
        self.btnStop.setVisible(False)
        self.btnStop.clicked.connect(self._request_stop)
        bottom_bar.addWidget(self.btnStop)

        self.btnClose = QPushButton("Kapat")
        self.btnClose.clicked.connect(self.reject)
        bottom_bar.addWidget(self.btnClose)

        self.btnSend = QPushButton("🚀 Seçilenlere Toplu Gönder")
        self.btnSend.setObjectName("btnSend")
        self.btnSend.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnSend.clicked.connect(self._start_bulk_send)
        bottom_bar.addWidget(self.btnSend)

        root_lay.addLayout(bottom_bar)

    def _create_stat_chip(self, title: str, val: str, color: str) -> QFrame:
        chip = QFrame()
        chip.setObjectName("StatCard")
        c_lay = QHBoxLayout(chip)
        c_lay.setContentsMargins(12, 6, 12, 6)
        c_lay.setSpacing(8)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("font-weight: 700; color: #64748b; font-size: 12px;")
        c_lay.addWidget(lbl_t)

        lbl_v = QLabel(val)
        lbl_v.setObjectName("ChipVal")
        lbl_v.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {color};")
        c_lay.addWidget(lbl_v)

        return chip

    def _update_chip(self, chip: QFrame, val: str):
        lbl_v = chip.findChild(QLabel, "ChipVal")
        if lbl_v:
            lbl_v.setText(val)

    # ==========================================
    # VERİ YÜKLEME & FİLTRELEME
    # ==========================================

    def _load_students(self):
        self._all_students.clear()
        con = db.get_conn()
        try:
            q = """
                SELECT id, ad, soyad, ana_grup, alt_grup, 
                       veli_tel1, veli_tel2, ogr_tel, hedef_bolum, hedef_tyt, hedef_ayt
                FROM ogrenci
                WHERE aktif = 1
                ORDER BY ad, soyad
            """
            rows = con.execute(q).fetchall()
            groups = set()

            for r in rows:
                oid = int(r["id"])
                ad = str(r["ad"] or "").strip()
                soyad = str(r["soyad"] or "").strip()
                adsoyad = f"{ad} {soyad}".strip() or f"Öğrenci #{oid}"
                grup = str(r["ana_grup"] or r["alt_grup"] or "Genel").strip()
                if grup:
                    groups.add(grup)

                hedef = str(r["hedef_bolum"] or r["hedef_tyt"] or r["hedef_ayt"] or "YKS/LGS Hedefi").strip()

                numdict = {
                    "veli1": _norm_num(r["veli_tel1"]),
                    "veli2": _norm_num(r["veli_tel2"]),
                    "ogr":   _norm_num(r["ogr_tel"]),
                }

                # Geciken ödev kontrolü (odev_kume ile JOIN)
                q_overdue = """
                    SELECT count(*) 
                    FROM odev o 
                    JOIN odev_kume k ON o.kume_id = k.id 
                    WHERE o.ogrenci_id = ? AND o.durum != 'TAMAMLANDI' AND date(k.bitis_tarihi) < date('now', 'localtime')
                """
                try:
                    has_overdue = (con.execute(q_overdue, (oid,)).fetchone()[0] > 0)
                except Exception:
                    has_overdue = False

                self._all_students.append({
                    "id": oid,
                    "ad": ad,
                    "soyad": soyad,
                    "adsoyad": adsoyad,
                    "grup": grup,
                    "hedef": hedef,
                    "numdict": numdict,
                    "has_overdue": has_overdue
                })

            # Grup filtresi doldur
            self.cmbGroup.blockSignals(True)
            self.cmbGroup.clear()
            self.cmbGroup.addItem("Tüm Gruplar")
            for g in sorted(groups):
                self.cmbGroup.addItem(g)
            self.cmbGroup.blockSignals(False)

        except Exception as e:
            print("Öğrenci yükleme hatası:", e)

        self._update_chip(self.card_total, str(len(self._all_students)))
        self._populate_student_list()

    def _populate_student_list(self):
        self.lstStudents.blockSignals(True)
        self.lstStudents.clear()

        search_q = self.txtSearch.text().strip().lower()
        selected_grp = self.cmbGroup.currentText()

        for s in self._all_students:
            # Grup filtresi
            if selected_grp != "Tüm Gruplar" and s["grup"] != selected_grp:
                continue

            # Arama filtresi
            if search_q:
                haystack = f"{s['adsoyad']} {s['grup']} {s['numdict']['veli1']} {s['numdict']['ogr']}".lower()
                if search_q not in haystack:
                    continue

            # Numaraları kontrol et
            overdue_tag = "  [⚠️ Gecikme]" if s["has_overdue"] else ""
            disp_text = f"{s['adsoyad']}  ({s['grup']}){overdue_tag}"
            it = QListWidgetItem(disp_text)
            it.setToolTip(f"Kayıtlı Telefonlar:\n• Veli-1: {s['numdict']['veli1'] or 'Yok'}\n• Veli-2: {s['numdict']['veli2'] or 'Yok'}\n• Öğrenci: {s['numdict']['ogr'] or 'Yok'}")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            it.setCheckState(Qt.CheckState.Unchecked)
            it.setData(ROLE_STUDENT_DATA, s)

            if s["has_overdue"]:
                it.setForeground(QColor("#b91c1c"))

            self.lstStudents.addItem(it)

        self.lstStudents.blockSignals(False)
        self._recalculate_recipients()

    def _apply_student_filters(self):
        self._populate_student_list()

    def _check_all_students(self, val: bool):
        self.lstStudents.blockSignals(True)
        state = Qt.CheckState.Checked if val else Qt.CheckState.Unchecked
        for i in range(self.lstStudents.count()):
            self.lstStudents.item(i).setCheckState(state)
        self.lstStudents.blockSignals(False)
        self._recalculate_recipients()
        self._update_preview()

    def _select_overdue_students(self):
        self.lstStudents.blockSignals(True)
        for i in range(self.lstStudents.count()):
            it = self.lstStudents.item(i)
            s: dict = it.data(ROLE_STUDENT_DATA)
            if s and s.get("has_overdue"):
                it.setCheckState(Qt.CheckState.Checked)
            else:
                it.setCheckState(Qt.CheckState.Unchecked)
        self.lstStudents.blockSignals(False)
        self._recalculate_recipients()
        self._update_preview()

    def _on_student_item_changed(self, it: QListWidgetItem):
        self._recalculate_recipients()
        self._update_preview()

    def _on_student_clicked(self, it: QListWidgetItem):
        self._update_preview(specific_student=it.data(ROLE_STUDENT_DATA))

    def _get_selected_students(self) -> list[dict]:
        res = []
        for i in range(self.lstStudents.count()):
            it = self.lstStudents.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                s = it.data(ROLE_STUDENT_DATA)
                if s:
                    res.append(s)
        return res

    def _recalculate_recipients(self):
        selected = self._get_selected_students()
        self._update_chip(self.card_selected, str(len(selected)))

        total_numbers = 0
        use_v1 = self.chkVeli1.isChecked()
        use_v2 = self.chkVeli2.isChecked()
        use_ogr = self.chkOgrenci.isChecked()

        for s in selected:
            nd = s.get("numdict", {})
            if use_v1 and nd.get("veli1"):
                total_numbers += 1
            if use_v2 and nd.get("veli2"):
                total_numbers += 1
            if use_ogr and nd.get("ogr"):
                total_numbers += 1

        self._update_chip(self.card_recipients, str(total_numbers))

    # ==========================================
    # ŞABLON & METİN İŞLEMLERİ
    # ==========================================

    def _on_template_selected(self, idx: int):
        if 0 <= idx < len(PRESET_TEMPLATES):
            t = PRESET_TEMPLATES[idx]
            if t["text"]:
                self.txtMessage.setPlainText(t["text"])
            elif idx == len(PRESET_TEMPLATES) - 1:
                self.txtMessage.clear()
        self._update_preview()

    def _insert_variable(self, tag: str):
        cursor = self.txtMessage.textCursor()
        cursor.insertText(tag)
        self.txtMessage.setTextCursor(cursor)
        self.txtMessage.setFocus()

    def _wrap_format(self, char: str):
        cursor = self.txtMessage.textCursor()
        if cursor.hasSelection():
            sel = cursor.selectedText()
            cursor.insertText(f"{char}{sel}{char}")
        else:
            cursor.insertText(f"{char}metin{char}")
        self.txtMessage.setTextCursor(cursor)
        self.txtMessage.setFocus()

    def _on_message_text_changed(self):
        txt = self.txtMessage.toPlainText()
        chars = len(txt)
        words = len(txt.split()) if txt.strip() else 0
        self.lblCounts.setText(f"{chars} Karakter | {words} Kelime")
        self._update_preview()

    def _format_personalized_message(self, tmpl: str, s: dict) -> str:
        today_str = datetime.date.today().strftime("%d.%m.%Y")
        msg = tmpl.replace("{ad}", s.get("ad", ""))
        msg = msg.replace("{soyad}", s.get("soyad", ""))
        msg = msg.replace("{ad_soyad}", s.get("adsoyad", ""))
        msg = msg.replace("{grup}", s.get("grup", ""))
        msg = msg.replace("{hedef}", s.get("hedef", ""))
        msg = msg.replace("{tarih}", today_str)
        return msg

    def _update_preview(self, specific_student: dict | None = None):
        target_s = specific_student
        if not target_s:
            selected = self._get_selected_students()
            target_s = selected[0] if selected else (self._all_students[0] if self._all_students else None)

        raw_msg = self.txtMessage.toPlainText().strip()
        if not target_s:
            self.lbl_preview_title.setText("👁️ Canlı Önizleme: (Öğrenci bulunamadı)")
            self.txtPreview.setPlainText(raw_msg)
            return

        self.lbl_preview_title.setText(f"👁️ Önizleme: {target_s['adsoyad']} ({target_s['grup']})")
        personalized = self._format_personalized_message(raw_msg, target_s)
        self.txtPreview.setPlainText(personalized)

    # ==========================================
    # GÖNDERİM & İLERLEME
    # ==========================================

    def _request_stop(self):
        self._stop_requested = True
        self.lblStatus.setText("Gönderim durduruluyor...")

    def _start_bulk_send(self):
        selected_students = self._get_selected_students()
        if not selected_students:
            QMessageBox.warning(self, "Öğrenci Seçilmedi", "Lütfen mesaj gönderilecek en az bir öğrenci işaretleyin.")
            return

        raw_template = self.txtMessage.toPlainText().strip()
        if not raw_template:
            QMessageBox.warning(self, "Mesaj Boş", "Lütfen gönderilecek mesaj metnini giriniz.")
            return

        use_v1 = self.chkVeli1.isChecked()
        use_v2 = self.chkVeli2.isChecked()
        use_ogr = self.chkOgrenci.isChecked()

        if not (use_v1 or use_v2 or use_ogr):
            QMessageBox.warning(self, "Alıcı Türü Yok", "Lütfen en az bir alıcı türü (Veli-1, Veli-2 veya Öğrenci) seçin.")
            return

        # Toplam gönderim listesi hazırla
        send_queue: list[tuple[dict, str, str]] = [] # (student_dict, phone_number, personalized_message)
        for s in selected_students:
            personalized_msg = self._format_personalized_message(raw_template, s)
            nd = s.get("numdict", {})
            if use_v1 and nd.get("veli1"):
                send_queue.append((s, nd["veli1"], personalized_msg))
            if use_v2 and nd.get("veli2"):
                send_queue.append((s, nd["veli2"], personalized_msg))
            if use_ogr and nd.get("ogr"):
                send_queue.append((s, nd["ogr"], personalized_msg))

        if not send_queue:
            QMessageBox.warning(self, "Numara Bulunamadı", "Seçili öğrencilerin belirtilen kategorilerde geçerli telefon numarası bulunmuyor.")
            return

        ans = QMessageBox.question(
            self, "Toplu Gönderim Onayı",
            f"Toplam <b>{len(selected_students)} öğrenci</b> için <b>{len(send_queue)} alıcı numarasına</b> WhatsApp mesajı gönderilecek.\n\n"
            "İşlemi başlatmak istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        # Gönderim UI Hazırla
        self._is_sending = True
        self._stop_requested = False
        self.btnSend.setEnabled(False)
        self.btnStop.setVisible(True)
        self.progressBar.setVisible(True)
        self.progressBar.setMaximum(len(send_queue))
        self.progressBar.setValue(0)

        import utils.whatsapp as wa

        success_count = 0
        fail_count = 0

        for idx, (s, phone, msg) in enumerate(send_queue):
            if self._stop_requested:
                break

            self.progressBar.setValue(idx + 1)
            self.lblStatus.setText(f"Gönderiliyor: {idx + 1}/{len(send_queue)} — {s['adsoyad']} ({phone})")
            QApplication.processEvents()

            try:
                res = wa.whatsapp_gonder(
                    numaralar=[phone],
                    mesaj=msg,
                    ogrenci_id=s["id"]
                )
                if res.get("gonderilen", 0) > 0:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                print("Gönderim hatası:", e)

            QApplication.processEvents()

        self._is_sending = False
        self.btnSend.setEnabled(True)
        self.btnStop.setVisible(False)
        self.progressBar.setVisible(False)

        if self._stop_requested:
            self.lblStatus.setText(f"Durduruldu. Başarılı: {success_count} | Kalan: {len(send_queue) - (success_count + fail_count)}")
            QMessageBox.information(self, "Durduruldu", f"Toplu gönderim kullanıcı tarafından durduruldu.\n\nBaşarıyla iletilen: {success_count}\nHatalı: {fail_count}")
        else:
            self.lblStatus.setText(f"Tamamlandı! Başarılı: {success_count} | Hatalı: {fail_count}")
            QMessageBox.information(self, "Tamamlandı", f"Toplu WhatsApp gönderimi tamamlandı!\n\n✅ Başarılı: {success_count}\n❌ Hatalı: {fail_count}\n\nTüm detaylar WhatsApp Günlüğü'ne kaydedildi.")