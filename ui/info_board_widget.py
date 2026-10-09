from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QFrame, QPushButton,
    QGraphicsDropShadowEffect, QSizePolicy, QDialog,
    QListWidget, QListWidgetItem, QLineEdit, QApplication, QWidget,
    QSlider, QComboBox, QScrollArea, QGridLayout, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
from services.web_service import WebContentProvider
import datetime


class _FilterBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(148,163,184,0.16);
                border-radius: 12px;
            }
            QPushButton {
                background: transparent;
                border: 1px solid rgba(148,163,184,0.18);
                border-radius: 10px;
                padding: 4px 10px;
                color: rgba(226,232,240,0.95);
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.06); border: 1px solid rgba(148,163,184,0.30); }
            QPushButton:checked {
                background: rgba(255,255,255,0.12);
                border: 1px solid rgba(148,163,184,0.40);
            }
            QLineEdit {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(148,163,184,0.18);
                border-radius: 10px;
                padding: 5px 10px;
                color: #E2E8F0;
                font-weight: 800;
                font-size: 11px;
            }
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(8)

        self.btn_all = QPushButton("Tümü")
        self.btn_rehberlik = QPushButton("🧠 Koçluk & Taktik")
        self.btn_yks = QPushButton("YKS")
        self.btn_lgs = QPushButton("LGS")
        self.btn_msu = QPushButton("MSÜ")
        self.btn_resmi = QPushButton("Resmî")

        for b in [self.btn_all, self.btn_rehberlik, self.btn_yks, self.btn_lgs, self.btn_msu, self.btn_resmi]:
            b.setCheckable(True)

        self.btn_all.setChecked(True)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara: kılavuz, sonuç, taktik, pomodoro...")

        lay.addWidget(self.btn_all)
        lay.addWidget(self.btn_rehberlik)
        lay.addWidget(self.btn_yks)
        lay.addWidget(self.btn_lgs)
        lay.addWidget(self.btn_msu)
        lay.addWidget(self.btn_resmi)
        lay.addStretch()
        lay.addWidget(self.search, 1)

    def current_filter(self) -> str:
        if self.btn_rehberlik.isChecked():
            return "REHBERLIK"
        if self.btn_resmi.isChecked():
            return "RESMI"
        if self.btn_yks.isChecked():
            return "YKS"
        if self.btn_lgs.isChecked():
            return "LGS"
        if self.btn_msu.isChecked():
            return "MSU"
        return "ALL"

    def set_exclusive(self, btn: QPushButton):
        for b in [self.btn_all, self.btn_rehberlik, self.btn_yks, self.btn_lgs, self.btn_msu, self.btn_resmi]:
            b.setChecked(False)
        btn.setChecked(True)


class _NewsDetailDialog(QDialog):
    def __init__(self, items: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detay — Güncel İçerikler")
        self.setMinimumSize(780, 470)
        self.setStyleSheet("""
            QDialog { background: #0b1220; }
            QLabel { color: #E2E8F0; }
            QListWidget {
                background: rgba(255,255,255,0.05);
                color: #E2E8F0;
                border: 1px solid rgba(148,163,184,0.20);
                border-radius: 12px;
                font-size: 12px;
            }
            QListWidget::item { padding: 8px; }
            QListWidget::item:selected { background: rgba(255,255,255,0.1); border-radius: 6px; }
        """)

        self._all_items: list[dict] = items[:] if items else []

        lay = QVBoxLayout(self)

        header_row = QHBoxLayout()
        header = QLabel("Tek tıkla açılır. Filtrele / ara, sonra seç.")
        header.setStyleSheet("font-size: 13px; font-weight: 900; color: #F8FAFC;")
        header_row.addWidget(header)

        header_row.addStretch()

        # ✅ Kopyala butonu
        self.btn_copy = QPushButton("Kopyala (Seçili)")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setStyleSheet("""
            QPushButton{
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(148,163,184,0.22);
                border-radius: 12px;
                padding: 6px 12px;
                color: #F8FAFC;
                font-weight: 900;
            }
            QPushButton:hover{ background: rgba(255,255,255,0.16); border: 1px solid rgba(148,163,184,0.35); }
        """)
        self.btn_copy.clicked.connect(self._copy_selected)
        header_row.addWidget(self.btn_copy)

        lay.addLayout(header_row)

        self.filters = _FilterBar()
        lay.addWidget(self.filters)

        self.listw = QListWidget()
        lay.addWidget(self.listw, 1)

        bottom = QHBoxLayout()
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("font-size: 11px; color: rgba(148,163,184,0.95); font-weight: 800;")
        bottom.addWidget(self.lbl_count)
        bottom.addStretch()

        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet("""
            QPushButton{
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(148,163,184,0.20);
                border-radius: 12px;
                padding: 8px 14px;
                color: #F8FAFC;
                font-weight: 900;
            }
            QPushButton:hover{ background: rgba(255,255,255,0.16); border: 1px solid rgba(148,163,184,0.35); }
        """)
        bottom.addWidget(btn_close)
        lay.addLayout(bottom)

        self.listw.itemClicked.connect(self._open)

        self.filters.btn_all.clicked.connect(lambda: self._on_filter(self.filters.btn_all))
        self.filters.btn_rehberlik.clicked.connect(lambda: self._on_filter(self.filters.btn_rehberlik))
        self.filters.btn_yks.clicked.connect(lambda: self._on_filter(self.filters.btn_yks))
        self.filters.btn_lgs.clicked.connect(lambda: self._on_filter(self.filters.btn_lgs))
        self.filters.btn_msu.clicked.connect(lambda: self._on_filter(self.filters.btn_msu))
        self.filters.btn_resmi.clicked.connect(lambda: self._on_filter(self.filters.btn_resmi))
        self.filters.search.textChanged.connect(lambda _: self._render())

        self._render()

    def _copy_selected(self):
        item = self.listw.currentItem()
        if not item:
            return
        url = item.data(Qt.ItemDataRole.UserRole) or ""
        text = item.text().strip()
        payload = f"{text}\n{url}".strip()
        QApplication.clipboard().setText(payload)

        # küçük feedback
        self.btn_copy.setText("Kopyalandı ✓")
        QTimer.singleShot(900, lambda: self.btn_copy.setText("Kopyala (Seçili)"))

    def _on_filter(self, btn: QPushButton):
        self.filters.set_exclusive(btn)
        self._render()

    def _matches_filter(self, it: dict) -> bool:
        f = self.filters.current_filter()
        title = (it.get("title") or "").lower()
        tags = (it.get("tags") or "").upper()
        src = (it.get("source") or "").upper()

        if f == "ALL":
            return True
        if f == "REHBERLIK":
            return (src in ["REHBERLİK", "PDR", "KOÇ", "ANALİZ", "TEKRAR", "ODAK", "SAĞLIK", "METOT", "MOTİVASYON"]) or any(x in tags for x in ["REHBERLİK", "ODAK", "TEKRAR", "ANALİZ", "STRATEJİ", "MOTİVASYON"])
        if f == "RESMI":
            return (src in ["ÖSYM", "MEB"]) or ("RESMÎ" in tags) or ("RESM" in tags)
        if f == "YKS":
            return ("YKS" in tags) or ("tyt" in title) or ("ayt" in title) or ("yks" in title)
        if f == "LGS":
            return ("LGS" in tags) or ("lgs" in title)
        if f == "MSU":
            return ("MSÜ" in tags) or ("msü" in title)
        return True

    def _matches_search(self, it: dict) -> bool:
        q = (self.filters.search.text() or "").strip().lower()
        if not q:
            return True
        hay = f"{it.get('source','')} {it.get('title','')} {it.get('tags','')}".lower()
        return q in hay

    def _render(self):
        self.listw.clear()
        filtered = [it for it in self._all_items if self._matches_filter(it) and self._matches_search(it)]

        try:
            filtered.sort(key=lambda x: int(x.get("score", 0)), reverse=True)
        except Exception:
            pass

        for it in filtered[:50]:
            src = it.get("source", "")
            t = it.get("title", "")
            url = it.get("url", "")
            pub = it.get("published", "")
            tags = it.get("tags", "")

            # Format list item nicely
            line = f"[{src}] {t}"
            if tags:
                line += f"  <{tags}>"
            if pub:
                line += f"  ({pub})"

            item = QListWidgetItem(line)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.listw.addItem(item)

        self.lbl_count.setText(f"Gösterilen: {min(len(filtered),50)} / Toplam: {len(self._all_items)}")

        # ilk elemanı seç (kopyala kolay olsun)
        if self.listw.count() > 0 and self.listw.currentRow() < 0:
            self.listw.setCurrentRow(0)

    def _open(self, item: QListWidgetItem):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            QDesktopServices.openUrl(QUrl(url))


_TR_MONTHS = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

_SIMULATION_CONFIGS = {
    "LGS": {
        "title": "LGS",
        "full_name": "LGS (Liselere Geçiş Sistemi)",
        "badge": "8. Sınıf MEB Müfredatı",
        "icon": "🎒",
        "accent": "#FBBF24",
        "tracks": {
            "8. Sınıf MEB Tüm Dersler": {
                "total": 56,
                "default_remaining": 28,
                "desc": "Matematik (12), Fen (11), Türkçe (11), İnkılap (8), Din (4), İngilizce (10)",
                "rec_daily": "100 - 150 soru",
            }
        },
        "default_speed": 3,
        "default_buffer": 7,
        "default_revision": 21,
    },
    "MSÜ": {
        "title": "MSÜ",
        "full_name": "MSÜ (Milli Savunma Üniversitesi)",
        "badge": "ÖSYM TYT Ortak Müfredatı",
        "icon": "🎖️",
        "accent": "#34D399",
        "tracks": {
            "TYT / MSÜ Ortak Müfredat": {
                "total": 115,
                "default_remaining": 45,
                "desc": "TYT Mat (31), Geo (14), Türkçe (15), Fizik (14), Kimya (12), Biyo (12), Tarih (12), Coğrafya (12), Felsefe (5)",
                "rec_daily": "120 - 180 soru",
            }
        },
        "default_speed": 4,
        "default_buffer": 7,
        "default_revision": 25,
    },
    "YKS": {
        "title": "YKS",
        "full_name": "YKS (Yükseköğretim Kurumları Sınavı)",
        "badge": "ÖSYM TYT & AYT Müfredatı",
        "icon": "🎓",
        "accent": "#60A5FA",
        "tracks": {
            "Sayısal (TYT + AYT Sayısal)": {
                "total": 180,
                "default_remaining": 65,
                "desc": "TYT-AYT Mat & Geo (73), TYT-AYT Fen (83: Fizik 47, Kimya 21, Biyo 28), TYT Türkçe (24)",
                "rec_daily": "150 - 220 soru",
            },
            "Eşit Ağırlık (TYT + AYT EA)": {
                "total": 160,
                "default_remaining": 55,
                "desc": "TYT-AYT Mat & Geo (73), TYT Türkçe & AYT Edebiyat (40), TYT-AYT Tarih/Coğrafya (47)",
                "rec_daily": "140 - 200 soru",
            },
            "Sözel (TYT + AYT Sözel)": {
                "total": 145,
                "default_remaining": 50,
                "desc": "TYT Türkçe & Edebiyat (40), Tarih 1-2, Coğrafya 1-2, Felsefe Grubu & Din (80), TYT Mat (25)",
                "rec_daily": "130 - 190 soru",
            },
            "TYT Odaklı (Yalnızca TYT)": {
                "total": 115,
                "default_remaining": 40,
                "desc": "Temel Yeterlilik Testi: Türkçe (15), Paragraf (40), Temel Mat (31), Fen (38), Sosyal (30)",
                "rec_daily": "120 - 170 soru",
            },
            "YDT / Dil (TYT + Yabancı Dil)": {
                "total": 85,
                "default_remaining": 30,
                "desc": "TYT Çekirdek Müfredat + YDT Reading, Vocabulary, Gramer & Çeviri",
                "rec_daily": "120 - 180 soru",
            }
        },
        "default_speed": 4,
        "default_buffer": 7,
        "default_revision": 30,
    }
}


class _SimulationDialog(QDialog):
    """
    Profesyonel, Gerçekçi Sınav ve Konu Yetiştirme Simülasyonu
    - MEB & ÖSYM Gerçek Müfredat Konu/Ünite Tavanları
    - Alan / Track Seçimi (Sayısal, EA, Sözel, TYT, LGS, MSÜ)
    - Takvim Bitiş Tarihi Tahmini (gün/ay/yıl)
    - Aksama Payı (Buffer) & Son Deneme/Tekrar Kampı Marjı
    - Koçluk Metrikleri & Günlük Soru Tavsiyesi
    - Dinamik Durum İndikatörü ve Modern Executive Dark Tema
    """
    def __init__(self, exam_name: str, remaining_days: int, parent=None):
        super().__init__(parent)
        self.exam_name = (exam_name or "YKS").upper().strip()
        self.remaining_days = max(1, int(remaining_days))

        # Config eşleme
        if "LGS" in self.exam_name:
            self.cfg = _SIMULATION_CONFIGS["LGS"]
            self.exam_key = "LGS"
        elif "MSÜ" in self.exam_name or "MSU" in self.exam_name:
            self.cfg = _SIMULATION_CONFIGS["MSÜ"]
            self.exam_key = "MSÜ"
        else:
            self.cfg = _SIMULATION_CONFIGS["YKS"]
            self.exam_key = "YKS"

        # İlk aktif alan / track
        self.track_names = list(self.cfg["tracks"].keys())
        self.current_track_name = self.track_names[0]
        self.current_track = self.cfg["tracks"][self.current_track_name]

        self.setWindowTitle(f"Stratejik Sınav Simülasyonu — {self.cfg['full_name']}")
        
        # Ekran boyutuna göre güvenli pencere boyutu
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(660, max(560, int(avail.width() * 0.50)))
            h = min(730, max(580, int(avail.height() * 0.88)))
            self.resize(w, h)
        else:
            self.resize(640, 700)
        self.setMinimumSize(540, 560)

        self._apply_theme()
        self._init_ui()
        self._recalc()

    def _apply_theme(self):
        accent = self.cfg["accent"]
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #0b1120;
            }}
            QLabel {{
                color: #e2e8f0;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }}
            QFrame#HeaderCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #131d33, stop:1 #0f172a);
                border: 1px solid rgba(148, 163, 184, 0.18);
                border-radius: 14px;
            }}
            QFrame#ControlCard {{
                background: #111827;
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 12px;
            }}
            QFrame#ResultCard {{
                background: #131c2e;
                border: 1px solid rgba(148, 163, 184, 0.20);
                border-radius: 14px;
            }}
            QComboBox {{
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 12px;
                color: #f8fafc;
                font-weight: 700;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {accent};
            }}
            QComboBox QAbstractItemView {{
                background: #1e293b;
                border: 1px solid #475569;
                selection-background-color: #2563eb;
                color: #f8fafc;
                padding: 4px;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid #334155;
                height: 7px;
                background: #1e293b;
                margin: 2px 0;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {accent};
                border: 2px solid #ffffff;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                transform: scale(1.1);
                background: #ffffff;
                border: 2px solid {accent};
            }}
            QSlider::sub-page:horizontal {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 {accent});
                border-radius: 4px;
            }}
            QPushButton.PresetBtn {{
                background: #1e293b;
                border: 1px solid #334155;
                color: #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton.PresetBtn:hover {{
                background: #334155;
                color: #ffffff;
                border-color: {accent};
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: #0b1120;
                width: 7px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #334155;
                min-height: 24px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #475569;
            }}
        """)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Scroll Area for smaller screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(14)

        # 1. HEADER CARD
        header = QFrame()
        header.setObjectName("HeaderCard")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 14, 16, 14)
        h_lay.setSpacing(14)

        icon_lbl = QLabel(self.cfg["icon"])
        icon_lbl.setStyleSheet("font-size: 34px;")

        v_head = QVBoxLayout()
        v_head.setSpacing(3)
        lbl_title = QLabel(f"{self.cfg['full_name']} Stratejik Analizi")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #ffffff;")
        
        lbl_sub = QLabel(f"ÖSYM/MEB Resmi Müfredatına Dayalı Akıllı Yetiştirme Modeli")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_sub)

        # Kalan Gün Badge
        lbl_badge = QLabel(f"⏱️ {self.remaining_days} Gün Kaldı")
        lbl_badge.setStyleSheet(f"""
            background: rgba(30, 41, 59, 0.9);
            color: {self.cfg['accent']};
            border: 1px solid {self.cfg['accent']};
            font-size: 13px;
            font-weight: 800;
            padding: 6px 14px;
            border-radius: 20px;
        """)

        h_lay.addWidget(icon_lbl)
        h_lay.addLayout(v_head, 1)
        h_lay.addWidget(lbl_badge)
        lay.addWidget(header)

        # 2. ALAN / TRACK SEÇİMİ (YKS ise Combo, değilse Bilgi Kartı)
        track_card = QFrame()
        track_card.setObjectName("ControlCard")
        t_lay = QVBoxLayout(track_card)
        t_lay.setContentsMargins(14, 12, 14, 12)
        t_lay.setSpacing(8)

        if len(self.track_names) > 1:
            t_row = QHBoxLayout()
            t_lbl = QLabel("🎯 Alan / Müfredat Seçimi:")
            t_lbl.setStyleSheet("font-weight: 700; font-size: 12px; color: #cbd5e1;")
            self.cmb_track = QComboBox()
            for t_name in self.track_names:
                tot = self.cfg["tracks"][t_name]["total"]
                self.cmb_track.addItem(f"{t_name} — (Toplam {tot} Konu)", t_name)
            self.cmb_track.currentIndexChanged.connect(self._on_track_changed)
            t_row.addWidget(t_lbl)
            t_row.addWidget(self.cmb_track, 1)
            t_lay.addLayout(t_row)
        else:
            self.cmb_track = None
            t_row = QHBoxLayout()
            t_lbl = QLabel(f"🎯 Kapsam: {self.current_track_name} (Toplam {self.current_track['total']} Konu)")
            t_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {self.cfg['accent']};")
            t_row.addWidget(t_lbl)
            t_row.addStretch(1)
            t_lay.addLayout(t_row)

        self.lbl_track_desc = QLabel(self.current_track["desc"])
        self.lbl_track_desc.setWordWrap(True)
        self.lbl_track_desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.3;")
        t_lay.addWidget(self.lbl_track_desc)
        lay.addWidget(track_card)

        # 3. PARAMETRE VE SLIDER KARTI
        ctrl_card = QFrame()
        ctrl_card.setObjectName("ControlCard")
        c_lay = QVBoxLayout(ctrl_card)
        c_lay.setContentsMargins(14, 14, 14, 14)
        c_lay.setSpacing(14)

        # 1) Kalan Konu Slider
        box1 = QVBoxLayout(); box1.setSpacing(4)
        row1 = QHBoxLayout()
        lbl_c1 = QLabel("1️⃣ Çalışılacak Kalan Konu / Ünite Sayısı")
        lbl_c1.setStyleSheet("color: #f1f5f9; font-weight: 700; font-size: 12px;")
        self.lbl_topic_val = QLabel("")
        self.lbl_topic_val.setStyleSheet(f"color: {self.cfg['accent']}; font-weight: 800; font-size: 12px;")
        row1.addWidget(lbl_c1); row1.addStretch(1); row1.addWidget(self.lbl_topic_val)
        
        self.slider_topics = QSlider(Qt.Orientation.Horizontal)
        self.slider_topics.setRange(1, self.current_track["total"])
        self.slider_topics.setValue(min(self.current_track["default_remaining"], self.current_track["total"]))
        self.slider_topics.valueChanged.connect(self._recalc)
        box1.addLayout(row1); box1.addWidget(self.slider_topics)
        c_lay.addLayout(box1)

        # 2) Haftalık Hız Slider & Preset Butonları
        box2 = QVBoxLayout(); box2.setSpacing(4)
        row2 = QHBoxLayout()
        lbl_c2 = QLabel("2️⃣ Haftalık Bitirme Hızı (Tempo)")
        lbl_c2.setStyleSheet("color: #f1f5f9; font-weight: 700; font-size: 12px;")
        self.lbl_speed_val = QLabel("")
        self.lbl_speed_val.setStyleSheet("color: #38bdf8; font-weight: 800; font-size: 12px;")
        row2.addWidget(lbl_c2); row2.addStretch(1); row2.addWidget(self.lbl_speed_val)

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(1, 8)
        self.slider_speed.setValue(self.cfg["default_speed"])
        self.slider_speed.valueChanged.connect(self._recalc)
        box2.addLayout(row2); box2.addWidget(self.slider_speed)

        # Hızlı Tempo Butonları
        p_row = QHBoxLayout(); p_row.setSpacing(6)
        p_lbl = QLabel("Hızlı Ayar:"); p_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600;")
        p_row.addWidget(p_lbl)
        
        btn_p2 = QPushButton("🧘 Sakin (2 konu/hf)")
        btn_p2.setProperty("class", "PresetBtn")
        btn_p2.clicked.connect(lambda: self.slider_speed.setValue(2))
        
        btn_p3 = QPushButton("🎯 Standart (3 konu/hf)")
        btn_p3.setProperty("class", "PresetBtn")
        btn_p3.clicked.connect(lambda: self.slider_speed.setValue(3))
        
        btn_p5 = QPushButton("⚡ Yoğun (5 konu/hf)")
        btn_p5.setProperty("class", "PresetBtn")
        btn_p5.clicked.connect(lambda: self.slider_speed.setValue(5))

        for b in (btn_p2, btn_p3, btn_p5):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            p_row.addWidget(b)
        p_row.addStretch(1)
        box2.addLayout(p_row)
        c_lay.addLayout(box2)

        # 3) Buffer (Aksama Payı) Slider
        box3 = QVBoxLayout(); box3.setSpacing(4)
        row3 = QHBoxLayout()
        lbl_c3 = QLabel("3️⃣ Güvenlik & Aksama Payı (Yazılılar / Hastalık / Mola)")
        lbl_c3.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 12px;")
        self.lbl_buffer_val = QLabel("")
        self.lbl_buffer_val.setStyleSheet("color: #fbbf24; font-weight: 800; font-size: 12px;")
        row3.addWidget(lbl_c3); row3.addStretch(1); row3.addWidget(self.lbl_buffer_val)

        self.slider_buffer = QSlider(Qt.Orientation.Horizontal)
        self.slider_buffer.setRange(0, 30)
        self.slider_buffer.setValue(self.cfg["default_buffer"])
        self.slider_buffer.valueChanged.connect(self._recalc)
        box3.addLayout(row3); box3.addWidget(self.slider_buffer)
        c_lay.addLayout(box3)

        # 4) Son Tekrar & Seri Deneme Dönemi
        box4 = QVBoxLayout(); box4.setSpacing(4)
        row4 = QHBoxLayout()
        lbl_c4 = QLabel("4️⃣ Sınav Öncesi Seri Deneme & Analiz Kampı")
        lbl_c4.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 12px;")
        self.lbl_revision_val = QLabel("")
        self.lbl_revision_val.setStyleSheet("color: #a78bfa; font-weight: 800; font-size: 12px;")
        row4.addWidget(lbl_c4); row4.addStretch(1); row4.addWidget(self.lbl_revision_val)

        self.slider_revision = QSlider(Qt.Orientation.Horizontal)
        self.slider_revision.setRange(7, 60)
        self.slider_revision.setValue(self.cfg["default_revision"])
        self.slider_revision.valueChanged.connect(self._recalc)
        box4.addLayout(row4); box4.addWidget(self.slider_revision)
        c_lay.addLayout(box4)

        lay.addWidget(ctrl_card)

        # 4. YÜRÜTME & KOÇLUK ANALİZ KARTI (RESULTS)
        self.res_card = QFrame()
        self.res_card.setObjectName("ResultCard")
        r_lay = QVBoxLayout(self.res_card)
        r_lay.setContentsMargins(16, 16, 16, 16)
        r_lay.setSpacing(10)

        # Durum Başlığı & Badge
        self.lbl_status_banner = QLabel("Hesaplanıyor…")
        self.lbl_status_banner.setStyleSheet("font-size: 15px; font-weight: 900; color: #22c55e;")
        r_lay.addWidget(self.lbl_status_banner)

        # Progress Bar (Hedef Tamamlama Oranı)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #1e293b;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981);
                border-radius: 4px;
            }
        """)
        r_lay.addWidget(self.progress_bar)

        # 3'lü KPI Metrik Kutuları
        kpi_row = QHBoxLayout(); kpi_row.setSpacing(10)
        
        def create_kpi_box(title: str):
            box = QFrame()
            box.setStyleSheet("background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 8px; padding: 6px;")
            b_lay = QVBoxLayout(box); b_lay.setContentsMargins(8, 6, 8, 6); b_lay.setSpacing(2)
            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 700; text-transform: uppercase;")
            lbl_v = QLabel("—")
            lbl_v.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 800;")
            b_lay.addWidget(lbl_t); b_lay.addWidget(lbl_v)
            return box, lbl_v

        self.box_kpi1, self.lbl_kpi_date = create_kpi_box("📅 Hedef Bitiş Tarihi")
        self.box_kpi2, self.lbl_kpi_margin = create_kpi_box("⏱️ Sınav Öncesi Marj")
        self.box_kpi3, self.lbl_kpi_questions = create_kpi_box("🎯 Önerilen Günlük Soru")
        
        kpi_row.addWidget(self.box_kpi1)
        kpi_row.addWidget(self.box_kpi2)
        kpi_row.addWidget(self.box_kpi3)
        r_lay.addLayout(kpi_row)

        # Koçluk Tavsiye Metni
        self.lbl_coach_advice = QLabel("…")
        self.lbl_coach_advice.setWordWrap(True)
        self.lbl_coach_advice.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.45; background: rgba(0,0,0,0.15); padding: 8px 12px; border-radius: 6px;")
        r_lay.addWidget(self.lbl_coach_advice)

        lay.addWidget(self.res_card)

        # 5. ALT KAPAT BUTONU
        btn_close = QPushButton("✓ Planı Onayla & Kapat")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #334155);
                color: #ffffff;
                border: 1px solid #475569;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 800;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                border-color: #3b82f6;
            }
        """)
        root.addWidget(btn_close)

    def _on_track_changed(self, idx: int):
        if self.cmb_track:
            track_name = self.cmb_track.currentData()
            if track_name in self.cfg["tracks"]:
                self.current_track_name = track_name
                self.current_track = self.cfg["tracks"][track_name]
                self.lbl_track_desc.setText(self.current_track["desc"])
                
                # Slider sınırını ve varsayılanını güncelle
                total = self.current_track["total"]
                self.slider_topics.blockSignals(True)
                self.slider_topics.setRange(1, total)
                if self.slider_topics.value() > total:
                    self.slider_topics.setValue(total)
                self.slider_topics.blockSignals(False)
                self._recalc()

    def _recalc(self):
        topics = int(self.slider_topics.value())
        total_topics = self.current_track["total"]
        speed_per_week = int(self.slider_speed.value())
        buffer_days = int(self.slider_buffer.value())
        revision_days = int(self.slider_revision.value())

        pct = int((topics / float(total_topics)) * 100) if total_topics > 0 else 0
        self.lbl_topic_val.setText(f"{topics} / {total_topics} Konu (%{pct})")
        self.lbl_speed_val.setText(f"Haftada {speed_per_week} Konu")
        self.lbl_buffer_val.setText(f"+{buffer_days} Gün Pay")
        self.lbl_revision_val.setText(f"{revision_days} Gün Deneme Kampı")

        # Gerçek Takvim Tarihleri
        today = datetime.date.today()
        exam_date = today + datetime.timedelta(days=self.remaining_days)

        # Çalışılabilir gün marjı
        workable_days = max(0, self.remaining_days - revision_days - buffer_days)
        daily_rate = speed_per_week / 6.0
        if daily_rate <= 0:
            daily_rate = 0.01

        days_needed = int(round(topics / daily_rate))
        target_finish_date = today + datetime.timedelta(days=days_needed + buffer_days)
        margin_days = (exam_date - target_finish_date).days

        # Format Tarihler
        target_str = f"{target_finish_date.day} {_TR_MONTHS[target_finish_date.month]} {target_finish_date.year}"
        exam_str = f"{exam_date.day} {_TR_MONTHS[exam_date.month]} {exam_date.year}"

        self.lbl_kpi_date.setText(target_str)
        self.lbl_kpi_questions.setText(self.current_track.get("rec_daily", "120-180 soru"))

        # Durum Değerlendirmesi
        if workable_days <= 0:
            color = "#ef4444"
            status_title = "🚨 Plan Kilitlendi! Gün Sayısı Yetersiz"
            self.lbl_kpi_margin.setText("0 Gün")
            self.lbl_kpi_margin.setStyleSheet("color: #ef4444; font-size: 13px; font-weight: 800;")
            advice = (
                f"Sınava kalan toplam {self.remaining_days} günün {revision_days} günü deneme kampı ve {buffer_days} günü "
                f"aksama payına ayrıldığı için konu çalışacak gün kalmıyor. Lütfen deneme kampını veya aksama payını azaltın."
            )
            pct_prog = 100
        elif days_needed <= workable_days:
            color = "#10b981"
            status_title = f"🟢 Harika! Konular {margin_days} Gün Erken Yetişiyor"
            self.lbl_kpi_margin.setText(f"+{margin_days} Gün Erken")
            self.lbl_kpi_margin.setStyleSheet("color: #10b981; font-size: 13px; font-weight: 800;")
            
            total_deneme_days = revision_days + max(0, margin_days)
            advice = (
                f"🎯 **Koçluk Raporu:** Mevcut temponuzla ({speed_per_week} konu/hf) tüm kalan konular **{target_str}** "
                f"tarihinde tamamen bitiyor. Sınav gününe kadar ({exam_str}) toplam **{total_deneme_days} gün** tamamen "
                f"genel deneme, çıkmış sınav soruları ve nokta atışı analizlere kalıyor. Tavsiye edilen tempoyu koruyun!"
            )
            pct_prog = int((days_needed / float(workable_days)) * 100)
        elif days_needed <= workable_days + 7:
            color = "#f59e0b"
            status_title = f"🟡 Sınırda! Hata Payı Çok Düşük ({abs(margin_days)} gün marj)"
            self.lbl_kpi_margin.setText(f"{margin_days} Gün Marj")
            self.lbl_kpi_margin.setStyleSheet("color: #f59e0b; font-size: 13px; font-weight: 800;")
            advice = (
                f"⚠️ **Koçluk Uyarısı:** Konu bitişi **{target_str}** olarak öngörülüyor. Plan sınırda ilerliyor. "
                f"Olası okul sınavı veya hastalık durumunda konular deneme kampına sarkabilir. Haftalık hızınızı +1 konu "
                f"artırmanız veya elenen konuları şimdiden belirlemeniz önerilir."
            )
            pct_prog = 100
        else:
            color = "#f43f5e"
            late_days = abs(margin_days)
            status_title = f"🔴 Yetişmeme Riski Var! (~{late_days} Gün Sarkma)"
            self.lbl_kpi_margin.setText(f"-{late_days} Gün Gecikme")
            self.lbl_kpi_margin.setStyleSheet("color: #f43f5e; font-size: 13px; font-weight: 800;")
            
            # Gerekli hız hesabı
            safe_speed = max(1, int(round(topics / (workable_days / 6.0)))) if workable_days > 0 else 5
            advice = (
                f"🚨 **Acil Eylem Planı:** Bu tempoyla konular sınavdan sonraya ({target_str}) sarkıyor. "
                f"Planı kurtarmak için: 1) Haftalık hızınızı en az **{safe_speed} konu/hafta** seviyesine çıkarın, "
                f"2) Son deneme kampı süresini optimize edin veya 3) Soru getirme katsayısı düşük konuları eleyin."
            )
            pct_prog = 100

        self.lbl_status_banner.setText(status_title)
        self.lbl_status_banner.setStyleSheet(f"font-size: 14px; font-weight: 900; color: {color};")
        self.lbl_coach_advice.setText(advice)

        self.progress_bar.setValue(min(100, pct_prog))
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #1e293b;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 4px;
            }}
        """)


class InfoBoardWidget(QFrame):
    """
    Eğitim Odaklı Bilgi Panosu (PRO)
    + Otomatik yenileme (default: 30 dk)
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(118)
        self.setObjectName("InfoBoard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # ✅ Otomatik yenileme ayarı (dakika)
        self.AUTO_REFRESH_MINUTES = 5

        self.setStyleSheet("""
            QFrame#InfoBoard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0b1220, stop:0.55 #0f172a, stop:1 #111c2d);
                border-radius: 14px;
                border: 1px solid rgba(148,163,184,0.18);
            }
            QFrame#InfoBoard:hover { border: 1px solid rgba(148,163,184,0.35); }
            QLabel { background: transparent; color: white; border: none; }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        self._items: list[dict] = []
        self._exam_sources = {}

        # Sayaç kutuları (senin mevcut yapın korunuyor)
        self.counter_layout = QHBoxLayout()
        self.counter_layout.setSpacing(10)

        self._counter_value_labels = {}
        self._counter_bar_widgets = {}
        self._counter_total_defaults = {"YKS": 365, "MSÜ": 300, "LGS": 365}
        self._last_total_days = {}

        def create_counter_box(title: str, accent: str):
            box = QFrame()
            box.setFixedSize(104, 78)
            box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            box.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.06);
                    border-radius: 10px;
                    border: 1px solid rgba(148,163,184,0.16);
                }
                QFrame:hover {
                    background: rgba(255,255,255,0.08);
                    border: 1px solid rgba(148,163,184,0.28);
                }
            """)
            
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.setToolTip("Yetiştirme Simülasyonu için tıkla 🐢")

            v = QVBoxLayout(box)
            v.setContentsMargins(8, 8, 8, 8)
            v.setSpacing(2)
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_t = QLabel(title)
            lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_t.setStyleSheet(f"font-size: 11px; font-weight: 900; color: {accent}; letter-spacing: 0.6px;")

            lbl_v = QLabel("--")
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_v.setStyleSheet("font-size: 22px; font-weight: 900; color: #F8FAFC;")

            lbl_d = QLabel("GÜN")
            lbl_d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_d.setStyleSheet("font-size: 9px; color: rgba(148,163,184,0.9); font-weight: 800;")

            bar_wrap = QFrame()
            bar_wrap.setFixedHeight(6)
            bar_wrap.setStyleSheet("background: rgba(148,163,184,0.18); border-radius: 3px;")

            bar_fill = QFrame(bar_wrap)
            bar_fill.setStyleSheet(f"background: {accent}; border-radius: 3px;")
            bar_fill.setGeometry(0, 0, 0, 6)

            v.addWidget(lbl_t)
            v.addWidget(lbl_v)
            v.addWidget(lbl_d)
            v.addSpacing(2)
            v.addWidget(bar_wrap)

            # Tıklama olayı (closure)
            def on_box_click(event):
                try:
                    current_days_text = lbl_v.text()
                    # Sayıya çevir
                    if current_days_text.isdigit():
                        d = int(current_days_text)
                    else:
                        d = 30 # fallback
                    self._open_simulation(title, d)
                except:
                    pass

            box.mousePressEvent = on_box_click

            return box, lbl_v, bar_wrap, bar_fill

        self.box_yks, self.lbl_yks, self._barwrap_yks, self._barfill_yks = create_counter_box("YKS", "#60A5FA")
        self.box_msu, self.lbl_msu, self._barwrap_msu, self._barfill_msu = create_counter_box("MSÜ", "#34D399")
        self.box_lgs, self.lbl_lgs, self._barwrap_lgs, self._barfill_lgs = create_counter_box("LGS", "#FBBF24")

        self._counter_value_labels["YKS"] = self.lbl_yks
        self._counter_value_labels["MSÜ"] = self.lbl_msu
        self._counter_value_labels["LGS"] = self.lbl_lgs

        self._counter_bar_widgets["YKS"] = (self._barwrap_yks, self._barfill_yks)
        self._counter_bar_widgets["MSÜ"] = (self._barwrap_msu, self._barfill_msu)
        self._counter_bar_widgets["LGS"] = (self._barwrap_lgs, self._barfill_lgs)

        self.counter_layout.addWidget(self.box_yks)
        self.counter_layout.addWidget(self.box_msu)
        self.counter_layout.addWidget(self.box_lgs)
        layout.addLayout(self.counter_layout)

        line = QFrame()
        line.setFixedWidth(1)
        line.setStyleSheet("background: rgba(148,163,184,0.20);")
        layout.addWidget(line)

        v_news = QVBoxLayout()
        v_news.setSpacing(4)
        v_news.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_news_title = QLabel("📢 GÜNCEL EĞİTİM NOTU")
        # Font boyutunu 10px -> 9px, letter-spacing 1px -> 0px çektik sığması için
        lbl_news_title.setStyleSheet("font-size: 9px; font-weight: 900; color: rgba(148,163,184,0.95); letter-spacing: 0px;")

        self.lbl_tag = QLabel("")
        self.lbl_tag.setVisible(False)
        self.lbl_tag.setStyleSheet("""
            QLabel {
                color: rgba(226,232,240,0.95);
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(148,163,184,0.22);
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 800;
            }
        """)

        self.lbl_net = QLabel("")
        self.lbl_net.setVisible(False)
        self.lbl_net.setStyleSheet("""
            QLabel {
                color: rgba(226,232,240,0.95);
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(148,163,184,0.20);
                border-radius: 10px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 800;
            }
        """)

        self.btn_detail = QPushButton("Detay")
        self.btn_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_detail.setVisible(False)
        self.btn_detail.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(148,163,184,0.22);
                border-radius: 10px;
                padding: 2px 10px;
                color: #F8FAFC;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.14); border: 1px solid rgba(148,163,184,0.35); }
        """)
        self.btn_detail.clicked.connect(self._open_detail)

        top_row.addWidget(lbl_news_title)
        top_row.addWidget(self.lbl_tag)
        top_row.addWidget(self.lbl_net)
        top_row.addWidget(self.btn_detail)
        top_row.addStretch()

        self.lbl_analysis = QLabel("Veriler yükleniyor…")
        self.lbl_analysis.setWordWrap(True)
        self.lbl_analysis.setStyleSheet("font-size: 13px; font-weight: 650; color: #E2E8F0;")
        self.lbl_analysis.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._analysis_full_text = ""
        self._analysis_collapsed = True

        self.btn_more = QPushButton("Devamını göster")
        self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_more.setVisible(False)
        self.btn_more.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(226,232,240,0.95);
                border: 1px solid rgba(148,163,184,0.25);
                border-radius: 10px;
                padding: 3px 10px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.06); border: 1px solid rgba(148,163,184,0.40); }
        """)
        self.btn_more.clicked.connect(self._toggle_analysis)

        self.lbl_updated = QLabel("")
        self.lbl_updated.setStyleSheet("font-size: 10px; color: rgba(148,163,184,0.9);")
        self.lbl_updated.setVisible(False)

        v_news.addLayout(top_row)
        v_news.addWidget(self.lbl_analysis)
        v_news.addWidget(self.btn_more, alignment=Qt.AlignmentFlag.AlignLeft)
        v_news.addWidget(self.lbl_updated)
        layout.addLayout(v_news, 1)

        v_btn = QVBoxLayout()
        v_btn.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setFixedSize(28, 28)
        self.btn_refresh.setToolTip("Bilgileri Yenile")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.10);
                border-radius: 14px;
                color: #F8FAFC;
                border: 1px solid rgba(148,163,184,0.20);
                font-weight: 900;
            }
            QPushButton:hover { background: rgba(255,255,255,0.16); border: 1px solid rgba(148,163,184,0.35); }
            QPushButton:disabled { color: rgba(226,232,240,0.6); background: rgba(255,255,255,0.08); }
        """)
        self.btn_refresh.clicked.connect(self.start_fetch)
        v_btn.addWidget(self.btn_refresh)
        layout.addLayout(v_btn)

        self._spin_states = ["⟳", "⟲", "⟳", "⟲"]
        self._spin_i = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._spin_tick)

        # Provider
        self.provider = WebContentProvider()
        self.provider.on_data_ready.connect(self.update_ui)

        # ✅ Otomatik yenileme timer
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(int(self.AUTO_REFRESH_MINUTES * 60 * 1000))
        self._auto_timer.timeout.connect(self._auto_refresh_tick)
        self._auto_timer.timeout.connect(self._auto_refresh_tick)
        self._auto_timer.start()

        # ✅ Haber Ticker Timer
        self._ticker_timer = QTimer(self)
        self._ticker_timer.timeout.connect(self._update_ticker)
        self._ticker_index = 0

        QTimer.singleShot(500, self.start_fetch)

    def _auto_refresh_tick(self):
        # Kullanıcı o anda manuel bastıysa/çalışıyorsa çakışma olmasın
        if self.provider.isRunning():
            return
        self.start_fetch()

    def _open_detail(self):
        if not self._items:
            return
        dlg = _NewsDetailDialog(self._items, self)
        dlg.exec()

    def _spin_tick(self):
        self._spin_i = (self._spin_i + 1) % len(self._spin_states)
        self.btn_refresh.setText(self._spin_states[self._spin_i])

    def _set_loading(self, loading: bool):
        self.btn_refresh.setDisabled(loading)
        if loading:
            self._spin_i = 0
            self.btn_refresh.setText(self._spin_states[0])
            self._spin_timer.start(120)
        else:
            self._spin_timer.stop()
            self.btn_refresh.setText("⟳")

    def _safe_int(self, v, default="-"):
        try:
            if v is None:
                return default
            iv = int(v)
            return "0" if iv < 0 else str(iv)
        except Exception:
            return default

    def _set_analysis_text(self, text: str):
        text = (text or "").strip()
        if not text:
            self._analysis_full_text = "Bilgi yok."
            self.lbl_analysis.setText("Bilgi yok.")
            self.btn_more.setVisible(False)
            return

        self._analysis_full_text = text
        limit = 160
        if len(text) > limit:
            self._analysis_collapsed = True
            self.lbl_analysis.setText(text[:limit].rstrip() + "…")
            self.btn_more.setText("Devamını göster")
            self.btn_more.setVisible(True)
        else:
            self._analysis_collapsed = False
            self.lbl_analysis.setText(text)
            self.btn_more.setVisible(False)

    def _toggle_analysis(self):
        if not self._analysis_full_text:
            return
        if self._analysis_collapsed:
            # Genişletiyoruz -> Ticker dursun, tam metni göster
            self._ticker_timer.stop()
            self.lbl_analysis.setText(self._analysis_full_text)
            self.btn_more.setText("Kısalt")
            self._analysis_collapsed = False
        else:
            # Daraltıyoruz -> Ticker çalışsın (veya ilk summary)
            self._analysis_collapsed = True
            
            if self._items:
                self._update_ticker()
                self._ticker_timer.start(8000)
            else:
                self._set_analysis_text(self._analysis_full_text)

    def _set_tag(self, tag: str | None):
        tag = (tag or "").strip()
        if not tag:
            self.lbl_tag.setVisible(False)
            return
        self.lbl_tag.setText(tag.upper())
        self.lbl_tag.setVisible(True)

    def _set_net_chip(self, online: bool):
        self.lbl_net.setVisible(True)
        if online:
            self.lbl_net.setText("ONLINE")
            self.lbl_net.setStyleSheet("color: #4ade80; background: rgba(34,197,94,0.15); border: 1px solid rgba(74,222,128,0.3); border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 800;")
            self.lbl_net.setToolTip("İçerik çevrimiçi kaynaklardan güncellendi.")
        else:
            self.lbl_net.setText("YEREL BİLGİ BANKASI")
            self.lbl_net.setStyleSheet("color: #38bdf8; background: rgba(56,189,248,0.15); border: 1px solid rgba(56,189,248,0.3); border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 800;")
            self.lbl_net.setToolTip("Çevrimdışı mod: 60+ uzman koçluk, PDR ve sınav taktiği kartı aktif.")
    
    def _set_progress(self, exam_key: str, remaining_days):
        wrap, fill = self._counter_bar_widgets.get(exam_key, (None, None))
        if wrap is None or fill is None:
            return

        w = wrap.width()
        h = wrap.height()

        try:
            r = int(remaining_days)
            if r < 0:
                r = 0
        except Exception:
            r = None

        total = self._last_total_days.get(exam_key, None)
        if total is None:
            total = self._counter_total_defaults.get(exam_key, 365)

        try:
            total = int(total)
            if total <= 0:
                total = self._counter_total_defaults.get(exam_key, 365)
        except Exception:
            total = self._counter_total_defaults.get(exam_key, 365)

        pct = 0 if r is None else min(1.0, max(0.0, r / float(total)))
        fill_w = int(w * pct)
        fill_w = max(0, min(w, fill_w))
        fill.setGeometry(0, 0, fill_w, h)

    def start_fetch(self):
        self._set_loading(True)
        self.lbl_analysis.setText("Güncelleniyor…")
        self.btn_more.setVisible(False)
        self.lbl_updated.setVisible(False)
        self.lbl_net.setVisible(False)
        self.lbl_tag.setVisible(False)
        self.btn_detail.setVisible(False)

        try:
            if hasattr(self.provider, "force_refresh"):
                self.provider.force_refresh()
            self.provider.start()
        except Exception:
            self._set_loading(False)
            self.lbl_analysis.setText("Şu an veri alınamadı. Yenilemeyi tekrar deneyin.")

    def update_ui(self, data):
        self._set_loading(False)
        data = data or {}

        counts = data.get("countdown", {}) or {}
        # (opsiyonel) servis total günleri sağlayabilir - ekledim
        self._last_total_days = data.get("countdown_total", {}) or {}

        # Sayaçlar
        self.lbl_yks.setText(self._safe_int(counts.get("YKS", "-"), default="-"))
        self.lbl_msu.setText(self._safe_int(counts.get("MSÜ", "-"), default="-"))
        self.lbl_lgs.setText(self._safe_int(counts.get("LGS", "-"), default="-"))

        # Progress Barlar
        self._set_progress("YKS", counts.get("YKS", None))
        self._set_progress("MSÜ", counts.get("MSÜ", None))
        self._set_progress("LGS", counts.get("LGS", None))

        # Analiz (Full Text) sakla
        self._analysis_full_text = data.get("analysis", "Bilgi yok.")
        self._set_tag(data.get("analysis_tag", None))
        self._set_net_chip(bool(data.get("online", False)))

        # Items
        self._items = data.get("items", []) or []
        
        # 🟢 Fallback / Çeşitlilik İçin Ekstra Notlar
        extra_notes = [
            {"source": "KOÇ", "title": "Pomodoro tekniği ile 25 dk odaklan, 5 dk molayı ihmal etme.", "tags": "TEKNİK,ODAK"},
            {"source": "REHBERLİK", "title": "Sınav anında turlama tekniğini kullanmak netlerini artırır.", "tags": "TAKTİK,SINAV"},
            {"source": "MOTİVASYON", "title": "Başarı, her gün tekrarlanan küçük gayretlerin toplamıdır.", "tags": "MOTİVASYON"},
            {"source": "SAĞLIK", "title": "Düzenli uyku ve su tüketimi, hafıkanı %30 daha verimli kılar.", "tags": "SAĞLIK,BEYİN"},
            {"source": "PLAN", "title": "Haftalık planını Pazar akşamından yap, haftaya hazır başla.", "tags": "PLANLAMA"},
            {"source": "ANALİZ", "title": "Yapamadığın sorular en iyi öğretmenindir. Yanlışlarını analiz et.", "tags": "GELİŞİM"},
            {"source": "YKS", "title": "TYT nankördür, düzenli paragraf ve problem çözmeyi bırakma.", "tags": "STRATEJİ"},
        ]
        # Mevcut listenin sonuna ekleyip karıştırabiliriz veya sırayla gösteririz
        # Her güncellemede bunları da listeye dahil edelim ki döngü olsun.
        for note in extra_notes:
            # Sadece listede yoksa ekle (basit kontrol)
            if not any(x.get("title") == note["title"] for x in self._items):
                self._items.append(note)

        self.btn_detail.setVisible(bool(self._items))

        # Ticker Başlat
        self._ticker_index = 0
        if self._items:
            # Default collapsed başla
            self._analysis_collapsed = True
            self._update_ticker()
            # Kullanıcı raporlaması: 5 dakika çok uzun, 8 saniyeye düşürdük
            self._ticker_timer.start(8000) 
        else:
            self._ticker_timer.stop()
            self._set_analysis_text(self._analysis_full_text)

        now = datetime.datetime.now().strftime("%H:%M")
        self.lbl_updated.setText(f"Son: {now}")
        self.lbl_updated.setVisible(True)

    def _update_ticker(self):
        # Sadece collapsed ise güncelle
        if not self._analysis_collapsed or not self._items:
            return

        it = self._items[self._ticker_index]
        self._ticker_index = (self._ticker_index + 1) % len(self._items)

        # Basit formatlama
        src = it.get("source", "INFO")
        title = it.get("title", "")
        tags = (it.get("tags") or "").upper()

        prefix = "📌"
        if "ÖSYM" in src: prefix = "📢 ÖSYM:"
        elif "MEB" in src: prefix = "📢 MEB:"
        elif "NEWS" in src: prefix = "🔥 Gündem:"
        elif src in ["REHBERLİK", "PDR"]: prefix = "🧠 PDR & Rehberlik:"
        elif src == "KOÇ": prefix = "🎯 Koçluk Taktik:"
        elif src == "ODAK": prefix = "⏳ Derin Odak:"
        elif src in ["TEKRAR", "METOT"]: prefix = "🔄 Akıllı Tekrar:"
        elif src == "ANALİZ": prefix = "📊 Deneme Otopsisi:"
        elif src == "SAĞLIK": prefix = "🥗 Zihin & Sağlık:"
        elif src == "MOTİVASYON": prefix = "⭐ Motivasyon:"
        elif src == "MÜFREDAT": prefix = "📘 Maarif Modeli:"
        elif "YKS" in src: prefix = "🎯 YKS Taktik:"
        elif "LGS" in src: prefix = "📘 LGS Taktik:"

        if "TAKVİM" in tags: prefix = "🗓️ Takvim:"
        elif "SÜREÇ" in tags: prefix = "⚡ Süreç:"
        elif "UZMAN" in tags: prefix = "🧠 Uzman:"

        txt = f"{prefix} {title}"
        # Çok uzunsa ...
        if len(txt) > 130:
            txt = txt[:128] + "…"
        
        self.lbl_analysis.setText(txt)
        
        # Etiketi de ona uygun güncelle
        if tags:
            first_tag = tags.split(",")[0]
            self.lbl_tag.setText(first_tag)
            self.lbl_tag.setVisible(True)
        
        # Devamını göster butonu hep aktif kalsın (full text varsa)
        if self._analysis_full_text and len(self._analysis_full_text) > 10:
             self.btn_more.setVisible(True)
             self.btn_more.setText("Devamını göster")

    def _open_simulation(self, exam_name: str, days: int):
        dlg = _SimulationDialog(exam_name, days, self)
        dlg.exec()

