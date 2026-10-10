from __future__ import annotations
# part 1/7
# -*- coding: utf-8 -*-

# --- Standart kütüphane ---
import sys
import os
# Ana dizini sys.path'e ekle (doğrudan çalıştırılma durumunda)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
import re
import sqlite3
import traceback
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta

# --- PyQt6 çekirdek ---
from PyQt6.QtCore import (
    QDate, QEasingCurve, QPropertyAnimation, QTimer, QEvent, QRect, QObject, QSettings, QByteArray, Qt
)
from PyQt6.QtGui import (
    QFont, QBrush, QTextCursor, QPainter, QPalette, QColor, QKeySequence, QShortcut, QPen, QCursor
)
from PyQt6.QtWidgets import (
    QWidget, QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox, QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyleOption,
    QFrame, QSplitter, QLineEdit, QSizePolicy, QComboBox, QSpinBox, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QHBoxLayout, QVBoxLayout, QMenu, QInputDialog, QProgressDialog, QTableView,
    QDialog, QGridLayout, QGroupBox, QProgressBar, QCheckBox, QDateEdit, QToolButton, QScrollArea,
    QRadioButton, QTextEdit, QFileDialog, QHeaderView, QTabBar, QProxyStyle
)

#eksik konu tavsiye için
from utils import ai_recommend


from utils.table_tune import apply_simple_tuning_to_left_tables

# --- Proje içi (opsiyonel güvenli importlar) ---
try:
    from ui.print_helper import ListPrintDialog, _ModelAdapter, PrintProfile
except Exception:
    ListPrintDialog = _ModelAdapter = PrintProfile = None

try:
    from ui.book_dialog import KitapDialog
except Exception:
    KitapDialog = None

try:
    from ui.odev_kontrol import OdevKontrolDialog
except Exception:
    OdevKontrolDialog = None
from ui.odev_kontrol import OdevKontrolDialog


try:
    from utils import whatsapp
except Exception:
    whatsapp = None

try:
    import db
except Exception:
    db = None  # db yoksa, ilgili fonksiyonlar try/except ile korunuyor

# Tema/hover (opsiyonel)
try:
    from themes.header_hover_highlighter import HeaderHoverHighlighter
except Exception:
    HeaderHoverHighlighter = None

try:
    from ui import app_settings as appset  # tema/ayar
except Exception:
    appset = None

# ----------------------------------------------------------------------
# Modern Rapor Dialogu (Görsel İyileştirme)
# ----------------------------------------------------------------------
class ModernReportDialog(QDialog):
    def __init__(self, title, subtitle, metrics, comparisons, comment, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        # Ekran boyutuna göre güvenli yükseklik belirle
        from PyQt6.QtWidgets import QApplication, QScrollArea
        screen = QApplication.primaryScreen()
        avail_geo = screen.availableGeometry()
        safe_height = int(avail_geo.height() * 0.85)

        self.setFixedWidth(530) # Scrollbar payı için biraz genişletildi
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-family: 'Segoe UI', sans-serif; }
            .MetricCard { 
                background-color: #f8f9fa; 
                border-radius: 8px; 
                border: 1px solid #e9ecef;
            }
            .MetricValue { font-size: 22px; font-weight: bold; color: #2c3e50; }
            .MetricLabel { font-size: 11px; color: #7f8c8d; font-weight: bold; letter-spacing: 0.5px; }
        """)

        # Ana Layout (ScrollArea + Buton Alanı)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # İçerik Widget'ı
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # --- ORİJİNAL İÇERİK OLUŞTURMA (layout değişkeni content_widget'a bağlı) ---
        
        # Header
        head = QFrame()
        hl = QVBoxLayout(head)
        hl.setSpacing(4)
        hl.setContentsMargins(0,0,0,10)
        t = QLabel(title)
        t.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s = QLabel(subtitle)
        s.setStyleSheet("font-size: 14px; color: #95a5a6;")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(t)
        hl.addWidget(s)
        layout.addWidget(head)
        
        # Metrics Grid
        if metrics:
            grid = QGridLayout()
            grid.setSpacing(15)
            row, col = 0, 0
            for label_txt, val_txt, color_hex in metrics:
                card = QFrame()
                card.setProperty("class", "MetricCard")
                cl = QVBoxLayout(card)
                cl.setContentsMargins(15, 15, 15, 15)
                cl.setSpacing(5)
                
                vl = QLabel(str(val_txt))
                vl.setProperty("class", "MetricValue")
                if color_hex:
                    vl.setStyleSheet(f"color: {color_hex}; font-size: 24px; font-weight: bold;")
                vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                ll = QLabel(label_txt.upper())
                ll.setProperty("class", "MetricLabel")
                ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                cl.addWidget(vl)
                cl.addWidget(ll)
                grid.addWidget(card, row, col)
                col += 1
                if col > 1: # 2 columns
                    col = 0
                    row += 1
            layout.addLayout(grid)
            
        # Comparisons
        if comparisons:
            grp = QGroupBox("📊 Kıyaslama")
            grp.setStyleSheet("""
                QGroupBox { 
                    font-weight: bold; color: #34495e; 
                    border: 1px solid #dfe6e9; border-radius: 8px; 
                    margin-top: 20px; padding-top: 15px; padding-bottom: 10px;
                } 
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px;}
            """)
            gl = QVBoxLayout(grp)
            gl.setSpacing(12)
            gl.setContentsMargins(15, 20, 15, 15)
            for label, pct, color in comparisons:
                row = QHBoxLayout()
                lbl = QLabel(label)
                lbl.setFixedWidth(180) 
                lbl.setWordWrap(True)
                lbl.setStyleSheet("font-size: 11px; font-weight: 500; color: #2c3e50;")
                
                p = QProgressBar()
                p.setRange(0, 100)
                p.setValue(min(100, int(pct)))
                p.setTextVisible(True)
                p.setFormat(f"%p%")
                p.setStyleSheet(f"""
                    QProgressBar {{
                        height: 18px;
                        border-radius: 9px;
                        background-color: #f1f2f6;
                        text-align: center;
                        color: #636e72;
                        font-weight: bold;
                        font-size: 11px;
                    }}
                    QProgressBar::chunk {{
                        background-color: {color};
                        border-radius: 9px;
                    }}
                """)
                row.addWidget(lbl)
                row.addWidget(p)
                gl.addLayout(row)
            layout.addWidget(grp)
            
        # Comment
        if comment:
            cframe = QLabel(comment["text"])
            cframe.setWordWrap(True)
            bg = comment.get("bg", "#f0f7ff")
            bd = comment.get("border", "#3498db")
            text_col = comment.get("color", "#2c3e50")
            cframe.setStyleSheet(f"""
                background-color: {bg}; 
                border-left: 5px solid {bd}; 
                color: {text_col};
                padding: 15px; 
                border-radius: 6px; 
                font-size: 13px; 
                line-height: 1.4;
            """)
            layout.addWidget(cframe)

        # Scroll Area Setup
        layout.addStretch(1) # İçerik azsa yukarı it
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Close Button Area (Fixed Bottom)
        btn_area = QWidget()
        btn_area.setStyleSheet("background-color: #ffffff; border-top: 1px solid #dfe6e9;")
        bl = QVBoxLayout(btn_area)
        bl.setContentsMargins(20, 15, 20, 15)
        
        btn = QPushButton("Kapat")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self.accept)
        btn.setFixedHeight(40)
        btn.setStyleSheet("""
            QPushButton { 
                background-color: #2c3e50; 
                color: white; 
                border-radius: 6px; 
                font-weight: bold; 
                font-size: 14px;
            } 
            QPushButton:hover { background-color: #34495e; }
        """)
        bl.addWidget(btn)
        main_layout.addWidget(btn_area)

        # Max yükseklik ayarı
        self.setMaximumHeight(safe_height)
        # Başlangıçta içeriğe göre boyutlan ama ekranı aşma
        self.resize(530, min(900, safe_height))

# ---- GLOBAL yardımcılar ----
def _qfetchall(con, sql, params=()):
    try:
        return con.execute(sql, params).fetchall()
    except Exception:
        return []

def _qone(con, sql, params=()):
    try:
        return con.execute(sql, params).fetchone()
    except Exception:
        return None

# Özel roller
OVERDUE_FLAG_ROLE = Qt.ItemDataRole.UserRole + 31  # hücre gecikmeli mi?
OVERDUE_DAYS_ROLE = Qt.ItemDataRole.UserRole + 32  # kaç gün gecikmeli?
_ORG_BG_ROLE       = Qt.ItemDataRole.UserRole + 99  # özgün arka plan saklama

# Grup -> Gösterilecek dersler eşlemesi

# Ders İkonları, Temiz Başlıkları ve Kategorileri
LESSON_META = {
    "tyt_matematik": {"icon": "📐", "title": "TYT Matematik", "cat": "Sayısal"},
    "problemler": {"icon": "🧩", "title": "Problemler", "cat": "Sayısal"},
    "ayt_matematik": {"icon": "📈", "title": "AYT Matematik", "cat": "Sayısal"},
    "geometri": {"icon": "📏", "title": "Geometri", "cat": "Sayısal"},
    "fizik": {"icon": "⚡", "title": "Fizik", "cat": "Sayısal"},
    "kimya": {"icon": "🧪", "title": "Kimya", "cat": "Sayısal"},
    "biyoloji": {"icon": "🧬", "title": "Biyoloji", "cat": "Sayısal"},
    "turkce": {"icon": "📖", "title": "Türkçe", "cat": "Sözel & EA"},
    "paragraf": {"icon": "📑", "title": "Paragraf", "cat": "Sözel & EA"},
    "tarih": {"icon": "🏛️", "title": "Tarih", "cat": "Sözel & EA"},
    "cografya": {"icon": "🌍", "title": "Coğrafya", "cat": "Sözel & EA"},
    "felsefe": {"icon": "💭", "title": "Felsefe", "cat": "Sözel & EA"},
    "edebiyat": {"icon": "📜", "title": "Edebiyat", "cat": "Sözel & EA"},
    "din": {"icon": "🕌", "title": "Din Kültürü", "cat": "Sözel & EA"},
    "ingilizce": {"icon": "🇬🇧", "title": "İngilizce", "cat": "Dil"},
    "lgs_matematik": {"icon": "📐", "title": "LGS Matematik", "cat": "Sayısal"},
    "lgs_fen": {"icon": "🔬", "title": "LGS Fen Bilimleri", "cat": "Sayısal"},
    "lgs_turkce": {"icon": "📖", "title": "LGS Türkçe", "cat": "Sözel"},
    "lgs_inkilap": {"icon": "🏛️", "title": "LGS İnkılap", "cat": "Sözel"},
    "lgs_dinkulturu": {"icon": "🕌", "title": "LGS Din Kültürü", "cat": "Sözel"},
    "lgs_ingilizce": {"icon": "🇬🇧", "title": "LGS Yabancı Dil", "cat": "Dil"}
}

GRUP_DERSLER = {
    "YKS": ["tyt_matematik", "problemler", "ayt_matematik", "geometri", "fizik", "kimya",
            "biyoloji", "turkce", "paragraf", "tarih", "cografya", "felsefe", "edebiyat"],
    "Ara Sınıf": ["geometri", "fizik", "kimya", "biyoloji", "turkce", "tarih", "cografya",
                  "felsefe", "edebiyat", "tyt_matematik", "problemler"],
    "LGS": ["lgs_matematik", "lgs_fen", "lgs_turkce", "lgs_inkilap", "lgs_dinkulturu", "lgs_ingilizce"]
}

# İlerleme penceresi (opsiyonel)
try:
    from ui.progress import IlerlemePenceresi
except Exception:
    try:
        from progress import IlerlemePenceresi  # alternatif konum
    except Exception:
        IlerlemePenceresi = None


# ----------------------------------------------------------------------
# ÖNERİ PANELİ (Gelişmiş) — drop-in replacement
# ----------------------------------------------------------------------
class OneriPaneli(QWidget):
    """
    - Birincil kaynak: host._oneri_yenile(zorluk_max=..)
    - Yedek kaynak : host._takviye_adaylari(days_ahead=3)
    - Pasif/silinmiş kitaplar filtrelenir (aktif set boşsa filtre yok)
    - dk tahmini: host._tahmini_sure / estimate_duration / dk_for -> yoksa 20 dk
    - Arama, sıralama, tekrar eleme, durum renklendirme
    - Kısayollar + sağ tık menüsü
    """

    def __init__(self, parent: Optional[QWidget] = None, host: Optional[QWidget] = None):
        super().__init__(parent)
        self._host: Optional[QWidget] = host or parent
        self._active_books_cache = None
        self._raw_items: List[dict] = []
        self._last_selection_keys: set[str] = set()
        self._sort_key = "natural"  # natural | dk↑ | dk↓ | ders | kitap | konu
        self._show_already_assigned: bool = False

        # boyut politikası
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # ---- UI ----
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Başlık satırı
        top = QHBoxLayout()
        top.setSpacing(8)
        lbl = QLabel("Öneriler (son 30 gün)")
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        top.addWidget(lbl)

        # Arama kutusu
        self.txtAra = QLineEdit()
        self.txtAra.setPlaceholderText("Ara: ders / kitap / konu …  (Ctrl/⌘+F)")
        self.txtAra.setClearButtonEnabled(True)
        top.addStretch(1)
        top.addWidget(self.txtAra, 2)

        # Yenile
        self.btnYenile = QPushButton("Yenile")
        self.btnYenile.setMinimumHeight(26)
        top.addWidget(self.btnYenile)
        root.addLayout(top)

        # Liste
        self.liste = QListWidget()
        self.liste.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.liste.setMinimumHeight(240)
        self.liste.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        root.addWidget(self.liste)
        root.addStretch(1)  # ✅ liste ile buton grubu arasına esnetici

        # --- Filtre/ayar satırı ---
        fl = QHBoxLayout()
        fl.setSpacing(8)

        # Zorluk ≤
        fl.addWidget(QLabel("Zorluk ≤"))
        self.cmbZorluk = QComboBox()
        self.cmbZorluk.addItems([str(i) for i in range(1, 6)])
        self.cmbZorluk.setCurrentText("5")
        fl.addWidget(self.cmbZorluk)

        # Sırala
        fl.addWidget(QLabel("Sırala"))
        self.cmbSirala = QComboBox()
        self.cmbSirala.addItems(["Varsayılan", "Süre ↑", "Süre ↓", "Ders", "Kitap", "Konu"])
        fl.addWidget(self.cmbSirala)

        # Hedef Paket ±
        fl.addSpacing(12)
        fl.addWidget(QLabel("Hedef Paket (dk)"))
        self.spPaket = QSpinBox()
        self.spPaket.setRange(0, 9999)
        self.spPaket.setValue(60)
        fl.addWidget(self.spPaket)

        fl.addWidget(QLabel("±"))
        self.spTol = QSpinBox()
        self.spTol.setRange(0, 9999)
        self.spTol.setValue(10)
        fl.addWidget(self.spTol)

        # Aynı kitabı çeşitlendir
        self.chkCesitlendir = QCheckBox("Aynı kitabı çeşitlendir")
        self.chkCesitlendir.setChecked(True)
        fl.addWidget(self.chkCesitlendir)

        fl.addStretch(1)

        self.btnPaket = QPushButton("Hedefe göre paketle")
        self.btnPaket.setMinimumHeight(26)
        fl.addWidget(self.btnPaket)

        root.addLayout(fl)

        # 'Zaten verilmişleri göster' tek satır
        row_show = QHBoxLayout()
        row_show.addStretch(1)
        self.chkShowAlready = QCheckBox("Zaten verilmişleri göster")
        self.chkShowAlready.setChecked(False)
        self.chkShowAlready.setToolTip("Verilmiş ödevleri listede göster/gizle")
        row_show.addWidget(self.chkShowAlready)
        root.addLayout(row_show)

        # Aksiyon butonları
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btnEksik = QPushButton("Eksik Konuları Getir")
        self.btnTakviye = QPushButton("Yaklaşan Bitişe Takviye")
        self.btnEkle = QPushButton("Seçilenleri Ekle")
        self.btnEkle.setMinimumHeight(26)
        btns.addWidget(self.btnEksik)
        btns.addWidget(self.btnTakviye)
        btns.addSpacing(16)
        btns.addWidget(self.btnEkle)
        root.addLayout(btns)
        root.addStretch(1)



        # ---- Kısayollar
        QShortcut(QKeySequence("Ctrl+A"), self.liste, activated=self._select_all)
        QShortcut(QKeySequence("Meta+A"), self.liste, activated=self._select_all)
        QShortcut(QKeySequence("Space"), self.liste, activated=self._toggle_checked)
        QShortcut(QKeySequence("Return"), self, activated=self._ekle_click)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.txtAra.setFocus())
        QShortcut(QKeySequence("Meta+F"), self, activated=lambda: self.txtAra.setFocus())

        # ---- Sinyaller
        self.btnYenile.clicked.connect(self._yenile_click)
        self.btnPaket.clicked.connect(self._paket_click)
        self.btnEkle.clicked.connect(self._ekle_click)
        self.btnEksik.clicked.connect(self._eksik_click)
        self.btnTakviye.clicked.connect(self._takviye_click)
        self.cmbZorluk.activated.connect(self._zorluk_degisti)
        self.cmbSirala.activated.connect(self._sirala_degisti)
        self.txtAra.textChanged.connect(self._apply_view)
        self.chkShowAlready.toggled.connect(self._on_show_already_toggled)
        self.liste.customContextMenuRequested.connect(self._ctx_menu)

    # ---------- QWidget overrides ----------
    def showEvent(self, ev):
        super().showEvent(ev)
        if self.liste.count() == 0:
            self.auto_refresh()

    # --------------------------- Host / yardımcı -------------------------
    def attach_host(self, host: QWidget):
        self._host = host

    def _get_host(self) -> Optional[QWidget]:
        if self._host:
            return self._host
        w = self.parent()
        while w:
            if all(hasattr(w, m) for m in ("_oneri_yenile", "_oneri_sec_ekle", "_oneri_paketle")):
                self._host = w
                break
            w = w.parent() if hasattr(w, "parent") else None
        return self._host

    def _host_active_books_set(self) -> set[str]:
        host = self._get_host()
        if not host:
            return set()
        try:
            fn = getattr(host, "_aktif_kitaplar", None)
            if callable(fn):
                return set((x or "").strip().lower() for x in fn())
        except Exception:
            pass
        return set()

    def _is_book_active(self, kitap: str) -> bool:
        if self._active_books_cache is None:
            self._active_books_cache = self._host_active_books_set()
        return True if not self._active_books_cache else (kitap or "").strip().lower() in self._active_books_cache

    def _estimate_minutes(self, ders: str, kitap: str, konu: str) -> int:
        host = self._get_host()
        for cand in ("_tahmini_sure", "estimate_duration", "dk_for"):
            fn = getattr(host, cand, None)
            if callable(fn):
                try:
                    v = fn(ders, kitap, konu)
                    if isinstance(v, (int, float)) and v > 0:
                        return int(v)
                except Exception:
                    pass
        return 20

    def _key_of(self, d: dict) -> str:
        return f"{(d.get('ders') or '').strip().lower()}|{(d.get('kitap') or '').strip().lower()}|{(d.get('konu') or '').strip().lower()}"

    # ---------------------------- Public API -----------------------------
    def auto_refresh(self):
        self._yenile_click()

    def clear(self):
        self.liste.clear()

    def set_items(self, items: List[dict]):
        """Ham veriyi al; normalize et; tekrarları ele; görünümü uygula."""
        norm_items: List[dict] = []
        for obj in (items or []):
            if not isinstance(obj, dict):
                continue
            ders = (obj.get("ders") or "").strip()
            kitap = (obj.get("kitap") or "").strip()
            konu = (obj.get("konu") or "").strip()
            try:
                dk = int(obj.get("dk") or 0)
            except Exception:
                dk = 0
            if dk <= 0:
                dk = self._estimate_minutes(ders, kitap, konu)

            #if kitap and not self._is_book_active(kitap):
                #continue

            entry = {
                "ders": ders, "kitap": kitap, "konu": konu, "dk": dk,
                "status": (obj.get("status") or "").strip().lower(),
                "due": obj.get("due")
            }
            norm_items.append(entry)

        # tekrarları kaldır (son gelen kazanır)
        uniq: Dict[str, dict] = {}
        for d in norm_items:
            uniq[self._key_of(d)] = d
        self._raw_items = list(uniq.values())

        self._apply_view()

    def selected_items(self) -> List[dict]:
        out: List[dict] = []
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            if it.checkState() == Qt.CheckState.Checked or it.isSelected():
                d = it.data(Qt.ItemDataRole.UserRole)
                if isinstance(d, dict):
                    out.append(d)
        return out

    # -------------------------- Görünüm / filtre -------------------------
    def _apply_view(self):
        if not hasattr(self, "_show_already_assigned"):
            self._show_already_assigned = False

        # eski seçimleri / check'leri hatırla
        self._last_selection_keys = set(
            self._key_of(self.liste.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.liste.count())
            if self.liste.item(i).isSelected() and isinstance(self.liste.item(i).data(Qt.ItemDataRole.UserRole), dict)
        )
        checked_keys = set()
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                d = it.data(Qt.ItemDataRole.UserRole)
                if isinstance(d, dict):
                    checked_keys.add(self._key_of(d))

        # temizle
        self.clear()

        q = (self.txtAra.text() or "").strip().lower()
        items = list(self._raw_items)
        n_before_filter = len(items)

        # serbest arama
        if q:
            def hit(d):
                s = f"{d['ders']} {d['kitap']} {d['konu']}".lower()
                return all(part in s for part in q.split())
            items = [d for d in items if hit(d)]

        # 'zaten verilmiş' gizleme
        if not self._show_already_assigned:
            try:
                items = [
                    d for d in items
                    if not self._is_already_assigned(d.get('ders', ''), d.get('kitap', ''), d.get('konu', ''))
                ]
            except Exception:
                pass

            if n_before_filter > 0 and len(items) == 0:
                # Hepsi gizlendiyse otomatik göstere al ve bilgi ver
                self._show_already_assigned = True
                try:
                    self.chkShowAlready.blockSignals(True)
                    self.chkShowAlready.setChecked(True)
                    self.chkShowAlready.blockSignals(False)
                except Exception:
                    pass
                host = self._get_host()
                try:
                    if host and hasattr(host, "_toast"):
                        host._toast("Tüm öneriler daha önce verildiği için gizlenmişti. Görünür yaptım.",
                                    parent=host, msec=1800, under_widget=getattr(self, 'btnYenile', None))
                except Exception:
                    pass
                # items'ı yeniden kur
                items = list(self._raw_items)
                if q:
                    def hit2(d):
                        s = f"{d['ders']} {d['kitap']} {d['konu']}".lower()
                        return all(part in s for part in q.split())
                    items = [d for d in items if hit2(d)]

        # sıralama
        key = self._sort_key
        if key == "dk↑":
            items.sort(key=lambda d: (d["dk"], d["ders"], d["kitap"], d["konu"]))
        elif key == "dk↓":
            items.sort(key=lambda d: (-d["dk"], d["ders"], d["kitap"], d["konu"]))
        elif key == "ders":
            items.sort(key=lambda d: (d["ders"], d["kitap"], d["konu"]))
        elif key == "kitap":
            items.sort(key=lambda d: (d["kitap"], d["ders"], d["konu"]))
        elif key == "konu":
            items.sort(key=lambda d: (d["konu"], d["ders"], d["kitap"]))
        # natural: orijinal sıra

        # çiz
        for d in items:
            if d.get("kitap"):
                txt = f"{d['ders']} / {d['kitap']} / {d['konu']}  ({d['dk']} dk)"
            else:
                txt = f"{d['ders']} / {d['konu']}  ({d['dk']} dk)"
            it = QListWidgetItem(txt)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable |
                        Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, d)

            # durum renklendirme + tooltip
            st = d.get("status", "")
            if st == "gecikmis":
                it.setBackground(QColor("#FDE2E4"))
            elif st == "yakinda":
                it.setBackground(QColor("#FFF3CD"))

            # görünürken 'zaten verilmiş' ipucu
            try:
                if self._show_already_assigned and self._is_already_assigned(d.get('ders', ''), d.get('kitap', ''),
                                                                             d.get('konu', '')):
                    it.setForeground(QColor("#999999"))
                    base_tip = it.toolTip() or ""
                    tip = (" • " if base_tip else "") + "Zaten verilmiş"
                    it.setToolTip(base_tip + tip)
            except Exception:
                pass

            if d.get("due"):
                tip = f"Son tarih: {d['due']} • Durum: {st or '-'}"
                if it.toolTip():
                    tip = it.toolTip() + " • " + tip
                it.setToolTip(tip)

            self.liste.addItem(it)

        # eski check/seçimleri geri yükle
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            d = it.data(Qt.ItemDataRole.UserRole)
            if not isinstance(d, dict):
                continue
            k = self._key_of(d)
            if k in checked_keys:
                it.setCheckState(Qt.CheckState.Checked)
            if k in self._last_selection_keys:
                it.setSelected(True)

    def _sirala_degisti(self):
        m = self.cmbSirala.currentText()
        self._sort_key = {
            "Varsayılan": "natural", "Süre ↑": "dk↑", "Süre ↓": "dk↓",
            "Ders": "ders", "Kitap": "kitap", "Konu": "konu"
        }.get(m, "natural")
        self._apply_view()

    # ----------------------- Panel olayları / aksiyon --------------------
    def _zorluk_degisti(self, *_):
        self._active_books_cache = None
        self._yenile_click()

    def _yenile_click(self):
        """Önerileri host’tan çek; tekilleştir; global-done ve 'zaten verilmiş' filtrele; uygula."""
        host = self._get_host()
        items: List[dict] = []

        # 1) Ana kaynaktan öneriler
        try:
            if host and hasattr(host, "_oneri_yenile"):
                zmax = int(self.cmbZorluk.currentText())
                items = host._oneri_yenile(zorluk_max=zmax) or []
        except Exception:
            items = []

        # 2) Boşsa takviye adayları
        if not items and host and hasattr(host, "_takviye_adaylari"):
            try:
                cand = host._takviye_adaylari(days_ahead=3) or []
                items = [{
                    "ders": (c.get("ders", "") or "").strip(),
                    "kitap": (c.get("kitap", "") or "").strip(),
                    "konu": (c.get("konu", "") or "").strip(),
                    "dk": int(c.get("dk", 0) or 0),
                    "status": c.get("status"),
                    "due": c.get("due"),
                } for c in cand]
            except Exception:
                items = []

        # 3) Tekilleştir (ders/kitap/konu)
        dedup: Dict[tuple, dict] = {}
        for it in (items or []):
            key = ((it.get("ders", "") or ""), (it.get("kitap", "") or ""), (it.get("konu", "") or ""))
            prev = dedup.get(key)
            if not prev:
                dedup[key] = it
            else:
                if str(it.get("due", "")) > str(prev.get("due", "")):
                    dedup[key] = it
        items = list(dedup.values())

        # 4) Global-done çıkar
        try:
            ogr_id = getattr(host, "_secili_ogrenci_id", lambda: None)()
        except Exception:
            ogr_id = None
        if ogr_id and db:
            items = [
                it for it in items
                if not self._is_globally_done(ogr_id, it.get("ders", ""), it.get("kitap", ""), it.get("konu", ""))
            ]

        # 5) 'Zaten verilmiş' gizle (checkbox kapalıysa)
        if not self._show_already_assigned:
            items = [it for it in items
                     if not self._is_already_assigned(it.get("ders", ""), it.get("kitap", ""), it.get("konu", ""))]

        self._raw_items = items
        self.set_items(items)

    def _ekle_click(self):
        """Seçilen/işaretli önerileri Verilen tablosuna ekler; sol grid hücresini de işaretler."""
        host = self._get_host()
        if not host:
            return

        # 1) Liste öğelerini topla (önce checked, yoksa selected)
        picked = []
        try:
            for i in range(self.liste.count()):
                it = self.liste.item(i)
                if it and it.checkState() == Qt.CheckState.Checked:
                    picked.append(it)
        except Exception:
            picked = []

        if not picked:
            try:
                picked = list(self.liste.selectedItems())
            except Exception:
                picked = []

        if not picked:
            try:
                if hasattr(host, "_toast"):
                    host._toast("Seçili öğe yok.", parent=host, msec=1300,
                                under_widget=getattr(self, 'btnEkle', None))
            except Exception:
                pass
            return

        # 2) QListWidgetItem -> dict
        def item_to_dict(obj):
            if isinstance(obj, dict):
                obj["dk"] = int(obj.get("dk", 0) or 0)
                return obj
            try:
                data = obj.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict):
                    data["dk"] = int(data.get("dk", 0) or 0)
                    return data
            except Exception:
                pass
            try:
                txt = (obj.text() or "").strip()
                m = re.search(r"\((\d+)\s*dk\)", txt)
                dk_val = int(m.group(1)) if m else 0
                if m:
                    txt = re.sub(r"\s*\(\d+\s*dk\)\s*$", "", txt).strip()
                parts = [p.strip() for p in txt.split("/") if p.strip()]
                ders = parts[0] if len(parts) > 0 else ""
                kitap = parts[1] if len(parts) > 1 else ""
                konu = parts[2] if len(parts) > 2 else ""
                return {"ders": ders, "kitap": kitap, "konu": konu, "dk": dk_val}
            except Exception:
                return {"ders": "", "kitap": "", "konu": "", "dk": 0}

        selected = [item_to_dict(it) for it in picked]

        # 3) Süze & ekle
        eklendi = 0
        atlanan = []

        for it in (selected or []):
            ders = (it.get("ders") or "").strip()
            kitap = (it.get("kitap") or "").strip()
            konu = (it.get("konu") or "").strip()
            dk = str(int(it.get("dk", 0) or 0))
            if not ders or not kitap or not konu:
                continue

            # engel kontrolü
            blocked, reason = self._neden_eklenemez(ders, kitap, konu)
            if blocked:
                atlanan.append(f"{ders}/{kitap}/{konu} — {reason}")
                continue

            # ekle
            try:
                host._verilen_satir_ekle(ders, kitap, konu, dk, "")
                eklendi += 1
                # sol grid hücresini işaretle
                try:
                    if hasattr(host, "_hucre_bul"):
                        t, r, c = host._hucre_bul(ders, kitap, konu)
                        if t is not None:
                            item = t.item(r, c)
                            if item is None:
                                item = QTableWidgetItem()
                                t.setItem(r, c, item)
                            item.setCheckState(Qt.CheckState.Checked)
                except Exception:
                    pass
            except Exception:
                atlanan.append(f"{ders}/{kitap}/{konu} — eklenemedi")

        # 4) Geri bildirim
        try:
            if hasattr(host, "_toast"):
                if eklendi:
                    host._toast(f"{eklendi} ödev eklendi ✅", parent=host, msec=1400,
                                under_widget=getattr(self, 'btnEkle', None))
                else:
                    msg = "Seçili öğe yok." if not selected else "Eklenecek yeni ödev yok."
                    host._toast(msg, parent=host, msec=1400,
                                under_widget=getattr(self, 'btnEkle', None))
        except Exception:
            pass

        if atlanan:
            try:
                QMessageBox.information(self, "Atlananlar", "• " + "\n• ".join(atlanan))
            except Exception:
                pass

    def _paket_click(self):
        host = self._get_host()
        if not host:
            return
        hedef = int(self.spPaket.value())
        tol   = int(self.spTol.value())
        ces   = bool(self.chkCesitlendir.isChecked())

        # host algoritması varsa onu kullan
        if hasattr(host, "_oneri_paketle") and callable(host._oneri_paketle):
            try:
                host._oneri_paketle(hedef, tol, ces)
                return
            except Exception:
                pass

        # yerel greedy
        items = self.selected_items() or list(self._raw_items)
        items = [x for x in items if isinstance(x, dict)]
        items.sort(key=lambda x: int(x.get("dk", 0) or 0), reverse=True)

        hedef_min, hedef_max = max(0, hedef - tol), hedef + tol
        toplam, paket, seen = 0, [], set()

        for it in items:
            if ces and it.get("kitap"):
                k = it["kitap"].strip().lower()
                if k in seen:
                    continue
            dk = int(it.get("dk", 0) or 0)
            if dk <= 0:
                continue
            if toplam < hedef_min or (toplam + dk) <= hedef_max:
                paket.append(it); toplam += dk
                if ces and it.get("kitap"):
                    seen.add(it["kitap"].strip().lower())
                if hedef_min <= toplam <= hedef_max:
                    break

        if not paket and items:
            paket = [items[0]]

        try:
            if paket and hasattr(host, "_oneri_sec_ekle"):
                host._oneri_sec_ekle(paket)
        except Exception:
            pass

    # ------------------------ Kısa yol butonları ------------------------
    def _eksik_click(self):
        """Eksik konular kısa yolu; host API’lerini dener, yoksa yeniler."""
        host = self._get_host()
        items = None

        # 1) Liste dönen API
        if host:
            fn_list = getattr(host, "_akilli_eksik_konular_liste", None)
            if callable(fn_list):
                try:
                    data = fn_list() or []
                    if data:
                        items = [{
                            "ders": (x.get("ders") or "").strip(),
                            "kitap": (x.get("kitap") or "").strip(),
                            "konu": (x.get("konu") or "").strip(),
                            "dk": int(x.get("dk", 0) or 0),
                            "status": (x.get("status") or "").strip().lower(),
                            "due": x.get("due"),
                        } for x in data]
                except Exception:
                    items = None

        # 2) UI açan API’yi sessizce kullanıp panelden hasat et
        if items is None and host and hasattr(host, "_akilli_eksik_konular"):
            orig_info = None
            try:
                orig_info = QMessageBox.information
                QMessageBox.information = lambda *a, **k: 0  # sessize al
            except Exception:
                orig_info = None

            try:
                host._akilli_eksik_konular()
                oneri = getattr(host, "oneri", None)
                if oneri and hasattr(oneri, "liste") and oneri.liste.count() > 0:
                    gathered = []
                    for i in range(oneri.liste.count()):
                        d = oneri.liste.item(i).data(Qt.ItemDataRole.UserRole)
                        if isinstance(d, dict):
                            gathered.append(d)
                    if gathered:
                        items = gathered
            except Exception:
                items = None
            finally:
                try:
                    if orig_info:
                        QMessageBox.information = orig_info
                except Exception:
                    pass

        if items:
            self.set_items(items)
            try:
                if hasattr(host, "_toast"):
                    host._toast(
                        f"🎯 {len(items)} eksik konu bulundu ve öneri listesine eklendi.",
                        parent=host, msec=2500, under_widget=getattr(self, 'btnEksik', None)
                    )
            except Exception:
                pass
        else:
            try:
                if hasattr(host, "_toast"):
                    host._toast("🔍 Eksik konu bulunamadı.", parent=host, msec=1800,
                                under_widget=getattr(self, 'btnEksik', None))
            except Exception:
                pass
            self._yenile_click()

    def _takviye_click(self):
        """Yaklaşan bitişe takviye kısa yolu."""
        host = self._get_host()
        items = None

        fn = getattr(host, "_takviye_adaylari", None) if host else None
        if callable(fn):
            try:
                cand = fn(days_ahead=3) or []
                if cand:
                    items = [{
                        "ders":  (c.get("ders", "") or "").strip(),
                        "kitap": (c.get("kitap", "") or "").strip(),
                        "konu":  (c.get("konu", "") or "").strip(),
                        "dk":    int(c.get("dk", 0) or 0),
                        "status": c.get("status"),
                        "due":    c.get("due"),
                    } for c in cand]
            except Exception:
                items = None

        if items is None and host and hasattr(host, "_akilli_takviye"):
            try:
                host._akilli_takviye()
                oneri = getattr(host, "oneri", None)
                if oneri and hasattr(oneri, "liste"):
                    gathered = []
                    for i in range(oneri.liste.count()):
                        d = oneri.liste.item(i).data(Qt.ItemDataRole.UserRole)
                        if isinstance(d, dict):
                            gathered.append(d)
                    if gathered:
                        items = gathered
            except Exception:
                items = None

        if items:
            self.set_items(items)
        else:
            self._yenile_click()

    # ------------------------ Global / Already checks -------------------
    def _is_globally_done(self, ogr_id: int, ders: str, kitap: str, konu: str) -> bool:
        """Aynı (ders/kitap/konu) için en son durum 'yapıldı/tamam' mı?"""
        if not db:
            return False
        try:
            ders = (ders or "").strip().lower()
            kitap = (kitap or "").strip().lower()
            konu = (konu or "").strip().lower()
            if not ogr_id or not ders or not kitap or not konu:
                return False

            con = db.get_conn()
            row = con.execute("""
                SELECT LOWER(COALESCE(d.durum,'')) AS durum
                  FROM odev d
                  JOIN odev_kume k ON k.id = d.kume_id
                 WHERE k.ogrenci_id = ?
                   AND LOWER(COALESCE(d.ders,''))      = ?
                   AND LOWER(COALESCE(d.kitap_ad,''))  = ?
                   AND LOWER(COALESCE(d.konu_ad,''))   = ?
                 ORDER BY k.id DESC, d.id DESC
                 LIMIT 1
            """, (ogr_id, ders, kitap, konu)).fetchone()

            return bool(row) and row["durum"] in ("yapildi", "tamam")
        except Exception:
            return False

    def _global_done_check(self, ders: str, kitap: str, konu: str) -> bool:
        """Öğrenci bağımsız 'bu ödev geçmişte tamamlandı mı?' kontrolü (farklı şemalara uyumlu)."""
        if not db:
            return False
        try:
            con = db.get_conn()
            d = (ders or "").strip()
            k = (kitap or "").strip()
            n = (konu or "").strip()

            row = con.execute("""
                SELECT 1
                  FROM odev
                 WHERE LOWER(COALESCE(ders,''))      = LOWER(?)
                   AND COALESCE(kitap_ad,'')          = ?
                   AND COALESCE(konu_ad,'')           = ?
                   AND LOWER(COALESCE(durum,'')) IN ('yapildi','tamam')
                 LIMIT 1
            """, (d, k, n)).fetchone()
            if row:
                return True

            try:
                row2 = con.execute("""
                    SELECT 1
                      FROM odev_kume_item i
                      JOIN odev_kume k ON k.id = i.kume_id
                     WHERE i.ders = ? AND i.kitap = ? AND i.konu = ? AND i.yapildi = 1
                     ORDER BY k.bitis_tarihi DESC
                     LIMIT 1
                """, (d, k, n)).fetchone()
                if row2:
                    return True
            except Exception:
                pass

            try:
                row3 = con.execute("""
                    SELECT 1
                      FROM odev
                     WHERE ders = ? AND kitap = ? AND konu = ? AND yapildi = 1
                     LIMIT 1
                """, (d, k, n)).fetchone()
                return bool(row3)
            except Exception:
                return False
        except Exception:
            return False

    def _neden_eklenemez(self, ders: str, kitap: str, konu: str) -> tuple[bool, str]:
        """Eklemeyi engelleyen nedeni (varsa) döndürür."""
        d = (ders or "").strip()
        k = (kitap or "").strip()
        n = (konu or "").strip()

        host = self._get_host()
        if not host:
            return (True, "Ana form yok")

        try:
            if hasattr(host, "_verilen_var_mi") and host._verilen_var_mi(d, k, n):
                return (True, "Zaten Verilenler tablosunda var")
        except Exception:
            pass

        try:
            if hasattr(host, "_hucre_bul"):
                t, r, c = host._hucre_bul(d, k, n)
                if t is not None:
                    it = t.item(r, c)
                    if it and it.checkState() == Qt.CheckState.Checked:
                        return (True, "Sol gridde zaten işaretli")
        except Exception:
            pass

        try:
            if db:
                try:
                    ogr_id = host._secili_ogrenci_id()
                except Exception:
                    ogr_id = None
                if ogr_id:
                    con = db.get_conn()
                    row = con.execute(
                        """
                        SELECT 1
                          FROM odev d
                          JOIN odev_kume k ON k.id = d.kume_id
                         WHERE k.ogrenci_id = ?
                           AND LOWER(COALESCE(d.ders,''))     = LOWER(?)
                           AND COALESCE(d.kitap_ad,'')         = ?
                           AND COALESCE(d.konu_ad,'')          = ?
                           AND LOWER(COALESCE(d.durum,'')) IN ('devam','yapildi')
                         LIMIT 1
                        """,
                        (ogr_id, d, k, n)
                    ).fetchone()
                    if row:
                        return (True, "Aynı ödev zaten bir kümede (devam/yapıldı)")
        except Exception:
            pass

        try:
            ogr_id = None
            try:
                ogr_id = host._secili_ogrenci_id()
            except Exception:
                ogr_id = None
            if ogr_id and self._is_globally_done(ogr_id, d, k, n):
                return (True, "Öğrenci bu ödevi geçmişte tamamladı")
        except Exception:
            pass

        try:
            if hasattr(host, "_global_done_check") and host._global_done_check(d, k, n):
                return (True, "Global olarak tamamlandı işaretli")
        except Exception:
            pass

        return (False, "")

    def _on_show_already_toggled(self, on: bool):
        self._show_already_assigned = bool(on)
        self._apply_view()

    def _is_already_assigned(self, ders: str, kitap: str, konu: str) -> bool:
        """Bu ödev zaten verilmiş mi veya sol gridden işaretli mi?"""
        host = self._get_host()
        if not host:
            return False
        try:
            if hasattr(host, "_verilen_var_mi") and host._verilen_var_mi(ders, kitap, konu):
                return True
            if hasattr(host, "_hucre_bul"):
                t, r, c = host._hucre_bul(ders, kitap, konu)
                if t is not None:
                    it = t.item(r, c)
                    if it and it.checkState() == Qt.CheckState.Checked:
                        return True
        except Exception:
            pass
        return False

    def is_globally_done(self, ogr_id: int, ders: str, kitap: str, konu: str) -> bool:
        """Alias: bazı çağrılar is_globally_done bekliyor (host._global_done_check’e delege)."""
        host = getattr(self, "_host", None) or self.parent()
        try:
            if host and hasattr(host, "_global_done_check"):
                return bool(host._global_done_check(ders, kitap, konu))
        except Exception:
            pass
        return False

    # ------------------------------ Kısayol/menü -------------------------
    def _ctx_menu(self, pos):
        m = QMenu(self)
        a1 = m.addAction("Tümünü işaretle")
        a2 = m.addAction("İşaretleri kaldır")
        a3 = m.addAction("İşaretleri tersine çevir")
        m.addSeparator()
        a4 = m.addAction("Yalnız gecikmişleri göster")
        a5 = m.addAction("Tümünü göster")
        m.addSeparator()
        a6 = m.addAction("Seçileni en üste getir")
        a7 = m.addAction("Seçileni panoya kopyala")
        act = m.exec(self.liste.mapToGlobal(pos))

        if act == a1:
            for i in range(self.liste.count()):
                self.liste.item(i).setCheckState(Qt.CheckState.Checked)
        elif act == a2:
            for i in range(self.liste.count()):
                self.liste.item(i).setCheckState(Qt.CheckState.Unchecked)
        elif act == a3:
            for i in range(self.liste.count()):
                it = self.liste.item(i)
                it.setCheckState(Qt.CheckState.Unchecked if it.checkState() == Qt.CheckState.Checked
                                 else Qt.CheckState.Checked)
        elif act == a4:
            self.txtAra.setText("")
            self._raw_items = [d for d in self._raw_items if (d.get("status") == "gecikmis")]
            self._apply_view()
        elif act == a5:
            self._yenile_click()
        elif act == a6:
            sel = self.selected_items()
            if sel:
                keys = set(self._key_of(d) for d in sel)
                rest = [d for d in self._raw_items if self._key_of(d) not in keys]
                self._raw_items = sel + rest
                self._apply_view()
        elif act == a7:
            sel = self.selected_items()
            if sel:
                txt = "\n".join(f"{d['ders']} / {d['kitap']} / {d['konu']} ({d['dk']} dk)" for d in sel)
                QApplication.clipboard().setText(txt)

    def _select_all(self):
        self.liste.selectAll()

    def _toggle_checked(self):
        for it in self.liste.selectedItems():
            it.setCheckState(
                Qt.CheckState.Unchecked
                if it.checkState() == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
# part 1/7
# -*- coding: utf-8 -*-

# --- Standart kütüphane ---
import sys
import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict

# --- PyQt6 çekirdek ---
from PyQt6.QtCore import (
    QDate, QEasingCurve, QPropertyAnimation, QTimer, QEvent, QRect, QObject, QSettings, QByteArray, Qt
)
from PyQt6.QtGui import (
    QFont, QBrush, QTextCursor, QPainter, QPalette, QColor, QKeySequence, QShortcut
)
from PyQt6.QtWidgets import (
    QWidget, QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox, QGraphicsOpacityEffect,
    QStyle, QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyleOption, QFrame, QSplitter,
    QLineEdit, QSizePolicy, QComboBox, QSpinBox, QListWidget, QListWidgetItem, QPushButton, QLabel,
    QHBoxLayout, QVBoxLayout, QMenu
)
from PyQt6.QtCore import QTimer


# --- Proje içi (opsiyonel güvenli importlar) ---
try:
    from ui.print_helper import ListPrintDialog, _ModelAdapter, PrintProfile
except Exception:
    ListPrintDialog = _ModelAdapter = PrintProfile = None

try:
    from ui.book_dialog import KitapDialog
except Exception:
    KitapDialog = None

try:
    from ui.odev_kontrol import OdevKontrolDialog
except Exception:
    OdevKontrolDialog = None

try:
    from utils import whatsapp
except Exception:
    whatsapp = None

try:
    import db
except Exception:
    db = None  # db yoksa, ilgili fonksiyonlar try/except ile korunuyor

# Tema/hover (opsiyonel)
try:
    from themes.header_hover_highlighter import HeaderHoverHighlighter
except Exception:
    HeaderHoverHighlighter = None

try:
    from ui import app_settings as appset  # tema/ayar
except Exception:
    appset = None

# ---- GLOBAL yardımcılar ----
def _qfetchall(con, sql, params=()):
    try:
        return con.execute(sql, params).fetchall()
    except Exception:
        return []

def _qone(con, sql, params=()):
    try:
        return con.execute(sql, params).fetchone()
    except Exception:
        return None

# Özel roller
OVERDUE_FLAG_ROLE = Qt.ItemDataRole.UserRole + 31  # hücre gecikmeli mi?
OVERDUE_DAYS_ROLE = Qt.ItemDataRole.UserRole + 32  # kaç gün gecikmeli?
_ORG_BG_ROLE       = Qt.ItemDataRole.UserRole + 99  # özgün arka plan saklama

# Grup -> Gösterilecek dersler eşlemesi
GRUP_DERSLER = {
    "YKS": ["tyt_matematik", "problemler", "ayt_matematik", "geometri", "fizik", "kimya",
            "biyoloji", "turkce", "paragraf", "tarih", "cografya", "felsefe", "edebiyat"],
    "Ara Sınıf": ["geometri", "fizik", "kimya", "biyoloji", "turkce", "tarih", "cografya",
                  "felsefe", "edebiyat", "tyt_matematik", "problemler"],
    "LGS": ["lgs_matematik", "lgs_fen", "lgs_turkce", "lgs_inkilap", "lgs_dinkulturu", "lgs_ingilizce"]
}

# İlerleme penceresi (opsiyonel)
try:
    from ui.progress import IlerlemePenceresi
except Exception:
    try:
        from progress import IlerlemePenceresi  # alternatif konum
    except Exception:
        IlerlemePenceresi = None


# ----------------------------------------------------------------------
# ÖNERİ PANELİ (Gelişmiş) — drop-in replacement
# ----------------------------------------------------------------------
class OneriPaneli(QWidget):
    """
    - Birincil kaynak: host._oneri_yenile(zorluk_max=..)
    - Yedek kaynak : host._takviye_adaylari(days_ahead=3)
    - Pasif/silinmiş kitaplar filtrelenir (aktif set boşsa filtre yok)
    - dk tahmini: host._tahmini_sure / estimate_duration / dk_for -> yoksa 20 dk
    - Arama, sıralama, tekrar eleme, durum renklendirme
    - Kısayollar + sağ tık menüsü
    """

    def __init__(self, parent: Optional[QWidget] = None, host: Optional[QWidget] = None):
        super().__init__(parent)
        self._host: Optional[QWidget] = host or parent
        self._active_books_cache = None
        self._raw_items: List[dict] = []
        self._last_selection_keys: set[str] = set()
        self._sort_key = "natural"  # natural | dk↑ | dk↓ | ders | kitap | konu
        self._show_already_assigned: bool = False

        # boyut politikası
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        # ---- UI ----
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Başlık satırı
        top = QHBoxLayout()
        top.setSpacing(8)
        lbl = QLabel("Öneriler (son 30 gün)")
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        top.addWidget(lbl)

        # Arama kutusu
        self.txtAra = QLineEdit()
        self.txtAra.setPlaceholderText("Ara: ders / kitap / konu …  (Ctrl/⌘+F)")
        self.txtAra.setClearButtonEnabled(True)
        top.addStretch(1)
        top.addWidget(self.txtAra, 2)

        # Yenile
        self.btnYenile = QPushButton("Yenile")
        self.btnYenile.setMinimumHeight(26)
        top.addWidget(self.btnYenile)
        root.addLayout(top)

        # Liste
        self.liste = QListWidget()
        self.liste.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.liste.setMinimumHeight(240)
        self.liste.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        root.addWidget(self.liste)

        # --- Filtre/ayar satırı ---
        fl = QHBoxLayout()
        fl.setSpacing(8)

        # Zorluk ≤
        fl.addWidget(QLabel("Zorluk ≤"))
        self.cmbZorluk = QComboBox()
        self.cmbZorluk.addItems([str(i) for i in range(1, 6)])
        self.cmbZorluk.setCurrentText("5")
        fl.addWidget(self.cmbZorluk)

        # Sırala
        fl.addWidget(QLabel("Sırala"))
        self.cmbSirala = QComboBox()
        self.cmbSirala.addItems(["Varsayılan", "Süre ↑", "Süre ↓", "Ders", "Kitap", "Konu"])
        fl.addWidget(self.cmbSirala)

        # Hedef Paket ±
        fl.addSpacing(12)
        fl.addWidget(QLabel("Hedef Paket (dk)"))
        self.spPaket = QSpinBox()
        self.spPaket.setRange(0, 9999)
        self.spPaket.setValue(60)
        fl.addWidget(self.spPaket)

        fl.addWidget(QLabel("±"))
        self.spTol = QSpinBox()
        self.spTol.setRange(0, 9999)
        self.spTol.setValue(10)
        fl.addWidget(self.spTol)

        # Aynı kitabı çeşitlendir
        self.chkCesitlendir = QCheckBox("Aynı kitabı çeşitlendir")
        self.chkCesitlendir.setChecked(True)
        fl.addWidget(self.chkCesitlendir)

        fl.addStretch(1)

        self.btnPaket = QPushButton("Hedefe göre paketle")
        self.btnPaket.setMinimumHeight(26)
        fl.addWidget(self.btnPaket)

        root.addLayout(fl)

        # 'Zaten verilmişleri göster' tek satır
        row_show = QHBoxLayout()
        row_show.addStretch(1)
        self.chkShowAlready = QCheckBox("Zaten verilmişleri göster")
        self.chkShowAlready.setChecked(False)
        self.chkShowAlready.setToolTip("Verilmiş ödevleri listede göster/gizle")
        row_show.addWidget(self.chkShowAlready)
        root.addLayout(row_show)

        # Aksiyon butonları
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btnEksik = QPushButton("Eksik Konuları Getir")
        self.btnSmartAI = QPushButton("🧠 AI Akıllı Sıralama")
        self.btnNlpAdvisor = QPushButton("🔍 NLP Eksik Analizi")
        self.btnTakviye = QPushButton("Yaklaşan Bitişe Takviye")
        self.btnEkle = QPushButton("Seçilenleri Ekle")
        self.btnEkle.setMinimumHeight(26)
        
        btns.addWidget(self.btnEksik)
        btns.addWidget(self.btnSmartAI)
        btns.addWidget(self.btnNlpAdvisor)
        btns.addWidget(self.btnTakviye)
        btns.addSpacing(16)
        btns.addWidget(self.btnEkle)
        root.addLayout(btns)


        # ---- Kısayollar
        QShortcut(QKeySequence("Ctrl+A"), self.liste, activated=self._select_all)
        QShortcut(QKeySequence("Meta+A"), self.liste, activated=self._select_all)
        QShortcut(QKeySequence("Space"), self.liste, activated=self._toggle_checked)
        QShortcut(QKeySequence("Return"), self, activated=self._ekle_click)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.txtAra.setFocus())
        QShortcut(QKeySequence("Meta+F"), self, activated=lambda: self.txtAra.setFocus())

        # ---- Sinyaller
        self.btnYenile.clicked.connect(self._yenile_click)
        self.btnPaket.clicked.connect(self._paket_click)
        self.btnEkle.clicked.connect(self._ekle_click)
        self.btnEksik.clicked.connect(self._eksik_click)
        self.btnSmartAI.clicked.connect(self._smart_ai_click)
        self.btnTakviye.clicked.connect(self._takviye_click)
        self.cmbZorluk.activated.connect(self._zorluk_degisti)
        self.cmbSirala.activated.connect(self._sirala_degisti)
        self.txtAra.textChanged.connect(self._apply_view)
        self.chkShowAlready.toggled.connect(self._on_show_already_toggled)
        self.liste.customContextMenuRequested.connect(self._ctx_menu)

    # ---------- QWidget overrides ----------
    def showEvent(self, ev):
        super().showEvent(ev)
        if self.liste.count() == 0:
            self.auto_refresh()

    # --------------------------- Host / yardımcı -------------------------
    def attach_host(self, host: QWidget):
        self._host = host

    def _get_host(self) -> Optional[QWidget]:
        if self._host:
            return self._host
        w = self.parent()
        while w:
            if all(hasattr(w, m) for m in ("_oneri_yenile", "_oneri_sec_ekle", "_oneri_paketle")):
                self._host = w
                break
            w = w.parent() if hasattr(w, "parent") else None
        return self._host

    def _host_active_books_set(self) -> set[str]:
        host = self._get_host()
        if not host:
            return set()
        try:
            fn = getattr(host, "_aktif_kitaplar", None)
            if callable(fn):
                return set((x or "").strip().lower() for x in fn())
        except Exception:
            pass
        return set()

    def _is_book_active(self, kitap: str) -> bool:
        if self._active_books_cache is None:
            self._active_books_cache = self._host_active_books_set()
        return True if not self._active_books_cache else (kitap or "").strip().lower() in self._active_books_cache

    def _estimate_minutes(self, ders: str, kitap: str, konu: str) -> int:
        host = self._get_host()
        for cand in ("_tahmini_sure", "estimate_duration", "dk_for"):
            fn = getattr(host, cand, None)
            if callable(fn):
                try:
                    v = fn(ders, kitap, konu)
                    if isinstance(v, (int, float)) and v > 0:
                        return int(v)
                except Exception:
                    pass
        return 20

    def _key_of(self, d: dict) -> str:
        return f"{(d.get('ders') or '').strip().lower()}|{(d.get('kitap') or '').strip().lower()}|{(d.get('konu') or '').strip().lower()}"

    # ---------------------------- Public API -----------------------------
    def auto_refresh(self):
        self._yenile_click()

    def clear(self):
        self.liste.clear()

    def set_items(self, items: List[dict]):
        """Ham veriyi al; normalize et; tekrarları ele; görünümü uygula."""
        norm_items: List[dict] = []
        for obj in (items or []):
            if not isinstance(obj, dict):
                continue
            ders = (obj.get("ders") or "").strip()
            kitap = (obj.get("kitap") or "").strip()
            konu = (obj.get("konu") or "").strip()
            try:
                dk = int(obj.get("dk") or 0)
            except Exception:
                dk = 0
            if dk <= 0:
                dk = self._estimate_minutes(ders, kitap, konu)

            if kitap and not self._is_book_active(kitap):
                continue

            entry = {
                "ders": ders, "kitap": kitap, "konu": konu, "dk": dk,
                "status": (obj.get("status") or "").strip().lower(),
                "due": obj.get("due")
            }
            norm_items.append(entry)

        # tekrarları kaldır (son gelen kazanır)
        uniq: Dict[str, dict] = {}
        for d in norm_items:
            uniq[self._key_of(d)] = d
        self._raw_items = list(uniq.values())

        self._apply_view()

    def selected_items(self) -> List[dict]:
        out: List[dict] = []
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            if it.checkState() == Qt.CheckState.Checked or it.isSelected():
                d = it.data(Qt.ItemDataRole.UserRole)
                if isinstance(d, dict):
                    out.append(d)
        return out

    # -------------------------- Görünüm / filtre -------------------------
    def _apply_view(self):
        if not hasattr(self, "_show_already_assigned"):
            self._show_already_assigned = False

        # eski seçimleri / check'leri hatırla
        self._last_selection_keys = set(
            self._key_of(self.liste.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.liste.count())
            if self.liste.item(i).isSelected() and isinstance(self.liste.item(i).data(Qt.ItemDataRole.UserRole), dict)
        )
        checked_keys = set()
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                d = it.data(Qt.ItemDataRole.UserRole)
                if isinstance(d, dict):
                    checked_keys.add(self._key_of(d))

        # temizle
        self.clear()

        q = (self.txtAra.text() or "").strip().lower()
        items = list(self._raw_items)
        n_before_filter = len(items)

        # serbest arama
        if q:
            def hit(d):
                s = f"{d['ders']} {d['kitap']} {d['konu']}".lower()
                return all(part in s for part in q.split())
            items = [d for d in items if hit(d)]

        # 'zaten verilmiş' gizleme
        if not self._show_already_assigned:
            try:
                items = [
                    d for d in items
                    if not self._is_already_assigned(d.get('ders', ''), d.get('kitap', ''), d.get('konu', ''))
                ]
            except Exception:
                pass

            if n_before_filter > 0 and len(items) == 0:
                # Hepsi gizlendiyse otomatik göstere al ve bilgi ver
                self._show_already_assigned = True
                try:
                    self.chkShowAlready.blockSignals(True)
                    self.chkShowAlready.setChecked(True)
                    self.chkShowAlready.blockSignals(False)
                except Exception:
                    pass
                host = self._get_host()
                try:
                    if host and hasattr(host, "_toast"):
                        host._toast("Tüm öneriler daha önce verildiği için gizlenmişti. Görünür yaptım.",
                                    parent=host, msec=1800, under_widget=getattr(self, 'btnYenile', None))
                except Exception:
                    pass
                # items'ı yeniden kur
                items = list(self._raw_items)
                if q:
                    def hit2(d):
                        s = f"{d['ders']} {d['kitap']} {d['konu']}".lower()
                        return all(part in s for part in q.split())
                    items = [d for d in items if hit2(d)]

        # sıralama
        key = self._sort_key
        if key == "dk↑":
            items.sort(key=lambda d: (d["dk"], d["ders"], d["kitap"], d["konu"]))
        elif key == "dk↓":
            items.sort(key=lambda d: (-d["dk"], d["ders"], d["kitap"], d["konu"]))
        elif key == "ders":
            items.sort(key=lambda d: (d["ders"], d["kitap"], d["konu"]))
        elif key == "kitap":
            items.sort(key=lambda d: (d["kitap"], d["ders"], d["konu"]))
        elif key == "konu":
            items.sort(key=lambda d: (d["konu"], d["ders"], d["kitap"]))
        # natural: orijinal sıra

        # çiz
        for d in items:
            if d.get("kitap"):
                txt = f"{d['ders']} / {d['kitap']} / {d['konu']}  ({d['dk']} dk)"
            else:
                txt = f"{d['ders']} / {d['konu']}  ({d['dk']} dk)"
            it = QListWidgetItem(txt)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable |
                        Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, d)

            # durum renklendirme + tooltip
            st = d.get("status", "")
            if st == "gecikmis":
                it.setBackground(QColor("#FDE2E4"))
            elif st == "yakinda":
                it.setBackground(QColor("#FFF3CD"))

            # görünürken 'zaten verilmiş' ipucu
            try:
                if self._show_already_assigned and self._is_already_assigned(d.get('ders', ''), d.get('kitap', ''),
                                                                             d.get('konu', '')):
                    it.setForeground(QColor("#999999"))
                    base_tip = it.toolTip() or ""
                    tip = (" • " if base_tip else "") + "Zaten verilmiş"
                    it.setToolTip(base_tip + tip)
            except Exception:
                pass

            if d.get("due"):
                tip = f"Son tarih: {d['due']} • Durum: {st or '-'}"
                if it.toolTip():
                    tip = it.toolTip() + " • " + tip
                it.setToolTip(tip)

            self.liste.addItem(it)

        # eski check/seçimleri geri yükle
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            d = it.data(Qt.ItemDataRole.UserRole)
            if not isinstance(d, dict):
                continue
            k = self._key_of(d)
            if k in checked_keys:
                it.setCheckState(Qt.CheckState.Checked)
            if k in self._last_selection_keys:
                it.setSelected(True)

    def _sirala_degisti(self):
        m = self.cmbSirala.currentText()
        self._sort_key = {
            "Varsayılan": "natural", "Süre ↑": "dk↑", "Süre ↓": "dk↓",
            "Ders": "ders", "Kitap": "kitap", "Konu": "konu"
        }.get(m, "natural")
        self._apply_view()

    # ----------------------- Panel olayları / aksiyon --------------------
    def _zorluk_degisti(self, *_):
        self._active_books_cache = None
        self._yenile_click()

    def _yenile_click(self):
        """Önerileri host’tan çek; tekilleştir; global-done ve 'zaten verilmiş' filtrele; uygula."""
        host = self._get_host()
        items: List[dict] = []

        # 1) Ana kaynaktan öneriler
        try:
            if host and hasattr(host, "_oneri_yenile"):
                zmax = int(self.cmbZorluk.currentText())
                items = host._oneri_yenile(zorluk_max=zmax) or []
        except Exception:
            items = []

        # 2) Boşsa takviye adayları
        if not items and host and hasattr(host, "_takviye_adaylari"):
            try:
                cand = host._takviye_adaylari(days_ahead=3) or []
                items = [{
                    "ders": (c.get("ders", "") or "").strip(),
                    "kitap": (c.get("kitap", "") or "").strip(),
                    "konu": (c.get("konu", "") or "").strip(),
                    "dk": int(c.get("dk", 0) or 0),
                    "status": c.get("status"),
                    "due": c.get("due"),
                } for c in cand]
            except Exception:
                items = []

        # 3) Tekilleştir (ders/kitap/konu)
        dedup: Dict[tuple, dict] = {}
        for it in (items or []):
            key = ((it.get("ders", "") or ""), (it.get("kitap", "") or ""), (it.get("konu", "") or ""))
            prev = dedup.get(key)
            if not prev:
                dedup[key] = it
            else:
                if str(it.get("due", "")) > str(prev.get("due", "")):
                    dedup[key] = it
        items = list(dedup.values())

        # 4) Global-done çıkar
        try:
            ogr_id = getattr(host, "_secili_ogrenci_id", lambda: None)()
        except Exception:
            ogr_id = None
        if ogr_id and db:
            items = [
                it for it in items
                if not self._is_globally_done(ogr_id, it.get("ders", ""), it.get("kitap", ""), it.get("konu", ""))
            ]

        # 5) 'Zaten verilmiş' gizle (checkbox kapalıysa)
        if not self._show_already_assigned:
            items = [it for it in items
                     if not self._is_already_assigned(it.get("ders", ""), it.get("kitap", ""), it.get("konu", ""))]

        self._raw_items = items
        self.set_items(items)

    def _ekle_click(self):
        """Seçilen/işaretli önerileri Verilen tablosuna ekler; sol grid hücresini de işaretler."""
        host = self._get_host()
        if not host:
            return

        # 1) Liste öğelerini topla (önce checked, yoksa selected)
        picked = []
        try:
            for i in range(self.liste.count()):
                it = self.liste.item(i)
                if it and it.checkState() == Qt.CheckState.Checked:
                    picked.append(it)
        except Exception:
            picked = []

        if not picked:
            try:
                picked = list(self.liste.selectedItems())
            except Exception:
                picked = []

        if not picked:
            try:
                if hasattr(host, "_toast"):
                    host._toast("Seçili öğe yok.", parent=host, msec=1300,
                                under_widget=getattr(self, 'btnEkle', None))
            except Exception:
                pass
            return

        # 2) QListWidgetItem -> dict
        def item_to_dict(obj):
            if isinstance(obj, dict):
                obj["dk"] = int(obj.get("dk", 0) or 0)
                return obj
            try:
                data = obj.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict):
                    data["dk"] = int(data.get("dk", 0) or 0)
                    return data
            except Exception:
                pass
            try:
                txt = (obj.text() or "").strip()
                m = re.search(r"\((\d+)\s*dk\)", txt)
                dk_val = int(m.group(1)) if m else 0
                if m:
                    txt = re.sub(r"\s*\(\d+\s*dk\)\s*$", "", txt).strip()
                parts = [p.strip() for p in txt.split("/") if p.strip()]
                ders = parts[0] if len(parts) > 0 else ""
                kitap = parts[1] if len(parts) > 1 else ""
                konu = parts[2] if len(parts) > 2 else ""
                return {"ders": ders, "kitap": kitap, "konu": konu, "dk": dk_val}
            except Exception:
                return {"ders": "", "kitap": "", "konu": "", "dk": 0}

        selected = [item_to_dict(it) for it in picked]

        # 3) Süze & ekle
        eklendi = 0
        atlanan = []

        for it in (selected or []):
            ders = (it.get("ders") or "").strip()
            kitap = (it.get("kitap") or "").strip()
            konu = (it.get("konu") or "").strip()
            dk = str(int(it.get("dk", 0) or 0))
            if not ders or not kitap or not konu:
                continue

            # engel kontrolü
            blocked, reason = self._neden_eklenemez(ders, kitap, konu)
            if blocked:
                atlanan.append(f"{ders}/{kitap}/{konu} — {reason}")
                continue

            # ekle
            try:
                host._verilen_satir_ekle(ders, kitap, konu, dk, "")
                eklendi += 1
                # sol grid hücresini işaretle
                try:
                    if hasattr(host, "_hucre_bul"):
                        t, r, c = host._hucre_bul(ders, kitap, konu)
                        if t is not None:
                            item = t.item(r, c)
                            if item is None:
                                item = QTableWidgetItem()
                                t.setItem(r, c, item)
                            item.setCheckState(Qt.CheckState.Checked)
                except Exception:
                    pass
            except Exception:
                atlanan.append(f"{ders}/{kitap}/{konu} — eklenemedi")

        # 4) Geri bildirim
        try:
            if hasattr(host, "_toast"):
                if eklendi:
                    host._toast(f"{eklendi} ödev eklendi ✅", parent=host, msec=1400,
                                under_widget=getattr(self, 'btnEkle', None))
                else:
                    msg = "Seçili öğe yok." if not selected else "Eklenecek yeni ödev yok."
                    host._toast(msg, parent=host, msec=1400,
                                under_widget=getattr(self, 'btnEkle', None))
        except Exception:
            pass

        if atlanan:
            try:
                QMessageBox.information(self, "Atlananlar", "• " + "\n• ".join(atlanan))
            except Exception:
                pass

    def _paket_click(self):
        host = self._get_host()
        if not host:
            return
        hedef = int(self.spPaket.value())
        tol   = int(self.spTol.value())
        ces   = bool(self.chkCesitlendir.isChecked())

        # host algoritması varsa onu kullan
        if hasattr(host, "_oneri_paketle") and callable(host._oneri_paketle):
            try:
                host._oneri_paketle(hedef, tol, ces)
                return
            except Exception:
                pass

        # yerel greedy
        items = self.selected_items() or list(self._raw_items)
        items = [x for x in items if isinstance(x, dict)]
        items.sort(key=lambda x: int(x.get("dk", 0) or 0), reverse=True)

        hedef_min, hedef_max = max(0, hedef - tol), hedef + tol
        toplam, paket, seen = 0, [], set()

        for it in items:
            if ces and it.get("kitap"):
                k = it["kitap"].strip().lower()
                if k in seen:
                    continue
            dk = int(it.get("dk", 0) or 0)
            if dk <= 0:
                continue
            if toplam < hedef_min or (toplam + dk) <= hedef_max:
                paket.append(it); toplam += dk
                if ces and it.get("kitap"):
                    seen.add(it["kitap"].strip().lower())
                if hedef_min <= toplam <= hedef_max:
                    break

        if not paket and items:
            paket = [items[0]]

        try:
            if paket and hasattr(host, "_oneri_sec_ekle"):
                host._oneri_sec_ekle(paket)
        except Exception:
            pass

    # ------------------------ Kısa yol butonları ------------------------
    def _eksik_click(self):
        """Eksik konular kısa yolu; host API’lerini dener, yoksa yeniler."""
        host = self._get_host()
        items = None

        # 1) Liste dönen API
        if host:
            fn_list = getattr(host, "_akilli_eksik_konular_liste", None)
            if callable(fn_list):
                try:
                    data = fn_list() or []
                    if data:
                        items = [{
                            "ders": (x.get("ders") or "").strip(),
                            "kitap": (x.get("kitap") or "").strip(),
                            "konu": (x.get("konu") or "").strip(),
                            "dk": int(x.get("dk", 0) or 0),
                            "status": (x.get("status") or "").strip().lower(),
                            "due": x.get("due"),
                        } for x in data]
                except Exception:
                    items = None

        # 2) UI açan API’yi sessizce kullanıp panelden hasat et
        if items is None and host and hasattr(host, "_akilli_eksik_konular"):
            orig_info = None
            try:
                orig_info = QMessageBox.information
                QMessageBox.information = lambda *a, **k: 0  # sessize al
            except Exception:
                orig_info = None

            try:
                host._akilli_eksik_konular()
                oneri = getattr(host, "oneri", None)
                if oneri and hasattr(oneri, "liste") and oneri.liste.count() > 0:
                    gathered = []
                    for i in range(oneri.liste.count()):
                        d = oneri.liste.item(i).data(Qt.ItemDataRole.UserRole)
                        if isinstance(d, dict):
                            gathered.append(d)
                    if gathered:
                        items = gathered
            except Exception:
                items = None
            finally:
                try:
                    if orig_info:
                        QMessageBox.information = orig_info
                except Exception:
                    pass

        if items:
            self.set_items(items)
            try:
                if hasattr(host, "_toast"):
                    host._toast(
                        f"🎯 {len(items)} eksik konu bulundu ve öneri listesine eklendi.",
                        parent=host, msec=2500, under_widget=getattr(self, 'btnEksik', None)
                    )
            except Exception:
                pass
        else:
            try:
                if hasattr(host, "_toast"):
                    host._toast("🔍 Eksik konu bulunamadı.", parent=host, msec=1800,
                                under_widget=getattr(self, 'btnEksik', None))
            except Exception:
                pass
            self._yenile_click()

    def _takviye_click(self):
        """Yaklaşan bitişe takviye kısa yolu."""
        host = self._get_host()
        items = None

        fn = getattr(host, "_takviye_adaylari", None) if host else None
        if callable(fn):
            try:
                cand = fn(days_ahead=3) or []
                if cand:
                    items = [{
                        "ders":  (c.get("ders", "") or "").strip(),
                        "kitap": (c.get("kitap", "") or "").strip(),
                        "konu":  (c.get("konu", "") or "").strip(),
                        "dk":    int(c.get("dk", 0) or 0),
                        "status": c.get("status"),
                        "due":    c.get("due"),
                    } for c in cand]
            except Exception:
                items = None

        if items is None and host and hasattr(host, "_akilli_takviye"):
            try:
                host._akilli_takviye()
                oneri = getattr(host, "oneri", None)
                if oneri and hasattr(oneri, "liste"):
                    gathered = []
                    for i in range(oneri.liste.count()):
                        d = oneri.liste.item(i).data(Qt.ItemDataRole.UserRole)
                        if isinstance(d, dict):
                            gathered.append(d)
                    if gathered:
                        items = gathered
            except Exception:
                items = None

        if items:
            self.set_items(items)
        else:
            self._yenile_click()

    # ------------------------ Global / Already checks -------------------
    def _is_globally_done(self, ogr_id: int, ders: str, kitap: str, konu: str) -> bool:
        """Aynı (ders/kitap/konu) için en son durum 'yapıldı/tamam' mı?"""
        if not db:
            return False
        try:
            ders = (ders or "").strip().lower()
            kitap = (kitap or "").strip().lower()
            konu = (konu or "").strip().lower()
            if not ogr_id or not ders or not kitap or not konu:
                return False

            con = db.get_conn()
            row = con.execute("""
                SELECT LOWER(COALESCE(d.durum,'')) AS durum
                  FROM odev d
                  JOIN odev_kume k ON k.id = d.kume_id
                 WHERE k.ogrenci_id = ?
                   AND LOWER(COALESCE(d.ders,''))      = ?
                   AND LOWER(COALESCE(d.kitap_ad,''))  = ?
                   AND LOWER(COALESCE(d.konu_ad,''))   = ?
                 ORDER BY k.id DESC, d.id DESC
                 LIMIT 1
            """, (ogr_id, ders, kitap, konu)).fetchone()

            return bool(row) and row["durum"] in ("yapildi", "tamam")
        except Exception:
            return False

    def _global_done_check(self, ders: str, kitap: str, konu: str) -> bool:
        """Öğrenci bağımsız 'bu ödev geçmişte tamamlandı mı?' kontrolü (farklı şemalara uyumlu)."""
        if not db:
            return False
        try:
            con = db.get_conn()
            d = (ders or "").strip()
            k = (kitap or "").strip()
            n = (konu or "").strip()

            row = con.execute("""
                SELECT 1
                  FROM odev
                 WHERE LOWER(COALESCE(ders,''))      = LOWER(?)
                   AND COALESCE(kitap_ad,'')          = ?
                   AND COALESCE(konu_ad,'')           = ?
                   AND LOWER(COALESCE(durum,'')) IN ('yapildi','tamam')
                 LIMIT 1
            """, (d, k, n)).fetchone()
            if row:
                return True

            try:
                row2 = con.execute("""
                    SELECT 1
                      FROM odev_kume_item i
                      JOIN odev_kume k ON k.id = i.kume_id
                     WHERE i.ders = ? AND i.kitap = ? AND i.konu = ? AND i.yapildi = 1
                     ORDER BY k.bitis_tarihi DESC
                     LIMIT 1
                """, (d, k, n)).fetchone()
                if row2:
                    return True
            except Exception:
                pass

            try:
                row3 = con.execute("""
                    SELECT 1
                      FROM odev
                     WHERE ders = ? AND kitap = ? AND konu = ? AND yapildi = 1
                     LIMIT 1
                """, (d, k, n)).fetchone()
                return bool(row3)
            except Exception:
                return False
        except Exception:
            return False

    def _neden_eklenemez(self, ders: str, kitap: str, konu: str) -> tuple[bool, str]:
        """Eklemeyi engelleyen nedeni (varsa) döndürür."""
        d = (ders or "").strip()
        k = (kitap or "").strip()
        n = (konu or "").strip()

        host = self._get_host()
        if not host:
            return (True, "Ana form yok")

        try:
            if hasattr(host, "_verilen_var_mi") and host._verilen_var_mi(d, k, n):
                return (True, "Zaten Verilenler tablosunda var")
        except Exception:
            pass

        try:
            if hasattr(host, "_hucre_bul"):
                t, r, c = host._hucre_bul(d, k, n)
                if t is not None:
                    it = t.item(r, c)
                    if it and it.checkState() == Qt.CheckState.Checked:
                        return (True, "Sol gridde zaten işaretli")
        except Exception:
            pass

        try:
            if db:
                try:
                    ogr_id = host._secili_ogrenci_id()
                except Exception:
                    ogr_id = None
                if ogr_id:
                    con = db.get_conn()
                    row = con.execute(
                        """
                        SELECT 1
                          FROM odev d
                          JOIN odev_kume k ON k.id = d.kume_id
                         WHERE k.ogrenci_id = ?
                           AND LOWER(COALESCE(d.ders,''))     = LOWER(?)
                           AND COALESCE(d.kitap_ad,'')         = ?
                           AND COALESCE(d.konu_ad,'')          = ?
                           AND LOWER(COALESCE(d.durum,'')) IN ('devam','yapildi')
                         LIMIT 1
                        """,
                        (ogr_id, d, k, n)
                    ).fetchone()
                    if row:
                        return (True, "Aynı ödev zaten bir kümede (devam/yapıldı)")
        except Exception:
            pass

        try:
            ogr_id = None
            try:
                ogr_id = host._secili_ogrenci_id()
            except Exception:
                ogr_id = None
            if ogr_id and self._is_globally_done(ogr_id, d, k, n):
                return (True, "Öğrenci bu ödevi geçmişte tamamladı")
        except Exception:
            pass

        try:
            if hasattr(host, "_global_done_check") and host._global_done_check(d, k, n):
                return (True, "Global olarak tamamlandı işaretli")
        except Exception:
            pass

        return (False, "")

    def _on_show_already_toggled(self, on: bool):
        self._show_already_assigned = bool(on)
        self._apply_view()

    def _is_already_assigned(self, ders: str, kitap: str, konu: str) -> bool:
        """Bu ödev zaten verilmiş mi veya sol gridden işaretli mi?"""
        host = self._get_host()
        if not host:
            return False
        try:
            if hasattr(host, "_verilen_var_mi") and host._verilen_var_mi(ders, kitap, konu):
                return True
            if hasattr(host, "_hucre_bul"):
                t, r, c = host._hucre_bul(ders, kitap, konu)
                if t is not None:
                    it = t.item(r, c)
                    if it and it.checkState() == Qt.CheckState.Checked:
                        return True
        except Exception:
            pass
        return False

    def is_globally_done(self, ogr_id: int, ders: str, kitap: str, konu: str) -> bool:
        """Alias: bazı çağrılar is_globally_done bekliyor (host._global_done_check’e delege)."""
        host = getattr(self, "_host", None) or self.parent()
        try:
            if host and hasattr(host, "_global_done_check"):
                return bool(host._global_done_check(ders, kitap, konu))
        except Exception:
            pass
        return False

    # ---------------- AI SMART SORT ----------------
    def _smart_ai_click(self):
        """
        AI Algoritması kullanarak mevcut listeyi (veya yenileyip)
        öğrencinin zayıf olduğu ve uzun süredir çalışmadığı derslere göre sıralar.
        """
        host = self._get_host()
        if not host: return
        
        # 1. Host'tan öğrenci ID al
        # OdevTakipFormu içinde: self.cmbOgrenci.currentData()
        try:
            ogr_id = host.cmbOgrenci.currentData()
            # None veya 0 gelirse
            if not ogr_id:
                # Belki _secili_ogrenci_id() metodu vardır
                if hasattr(host, "_secili_ogrenci_id"):
                     ogr_id = host._secili_ogrenci_id()
                     
            if not ogr_id:
                QMessageBox.warning(self, "Uyarı", "Lütfen önce bir öğrenci seçin.")
                return
        except:
            return

        # 2. Listeyi Yenile (Ham veri gelsin)
        self._yenile_click()
        
        # 3. AI Ağırlıklarını Hesapla
        try:
            from services.smart_scheduler import weighted_subject_recommendation
            con = db.get_conn()
            weights_list = weighted_subject_recommendation(con, int(ogr_id), limit=20)
            
            # List -> Dict { 'Matematik': 80.5, ... }
            w_map = {item['subject'].lower(): item['priority_score'] for item in weights_list}
            
            # Helper for default low priority
            def get_priority(ders_adi):
                d = str(ders_adi).lower()
                # Tam eşleşme ara
                if d in w_map: return w_map[d]
                # Kısmi eşleşme
                for k, v in w_map.items():
                    if k in d or d in k:
                        return v
                return 0.0

            # 4. Mevcut self._raw_items listesini bu ağırlıklara göre sırala
            # Yüksek puan -> Listenin başına
            if hasattr(host, "_toast"):
                host._toast("Yapay Zeka ağırlıkları uygulanıyor...", duration=1500)
                QApplication.processEvents()

            self._raw_items.sort(key=lambda x: (
                -get_priority(x.get('ders', '')), # Puan (büyükten küçüğe)
                x.get('ders', ''),
                x.get('konu', '')
            ))
            
            # 5. Görünümü güncelle
            self._apply_view()
            
            # Bilgi ver
            msg = "Sıralama Güncellendi! Öncelikli Dersler:\n"
            for w in weights_list[:3]:
                msg += f"• {w['subject']} (Skor: {w['priority_score']})\n"
            
            if hasattr(host, "_toast"):
                host._toast(f"Liste AI ile akıllı sıralandı! 🧠\nTop: {weights_list[0]['subject'] if weights_list else '?'}", duration=3000)
            else:
                print(msg)

        except Exception as e:
            QMessageBox.critical(self, "AI Hatası", f"Algoritma çalışırken hata oluştu:\n{e}")

    def _on_nlp_advisor_click(self):
        """
        Öğrencinin geçmiş ödev verilerini analiz edip eksik olduğu noktaları
        bir pop-up rapor halinde sunar ve ilgili konuları filtreler.
        """
        host = self._get_host()
        if not host: return
        
        try:
             ogr_id = host.cmbOgrenci.currentData()
             if not ogr_id and hasattr(host, "_secili_ogrenci_id"):
                 ogr_id = host._secili_ogrenci_id()
                 
             if not ogr_id:
                 QMessageBox.warning(self, "Uyarı", "Lütfen bir öğrenci seçin.")
                 return
        except:
             return

        try:
            from services.nlp_advisor import analyze_weakness_nlp
            con = db.get_conn()
            result = analyze_weakness_nlp(con, int(ogr_id))
            
            if not result:
                QMessageBox.information(self, "Bilgi", "Yeterli başarısız ödev verisi bulunamadı. Yapay Zeka analizi için daha fazla veri gerekli.")
                return
            
            # Raporu göster
            report_msg = result["report_text"]
            dlg = QMessageBox(self)
            dlg.setWindowTitle("NLP Eksik Analizi 🧠")
            dlg.setText(report_msg)
            
            # Butonlar
            btn_filter = dlg.addButton("Bulguları Filtrele & Uygula", QMessageBox.ButtonRole.AcceptRole)
            btn_close = dlg.addButton("Kapat", QMessageBox.ButtonRole.RejectRole)
            
            dlg.exec()
            
            if dlg.clickedButton() == btn_filter:
                # 1. Yenile
                self._yenile_click()
                
                # 2. Filtreyi uygula
                # Anahtar kelimelerden birini arama kutusuna yazalım veya filtreleyelim
                keywords = result["keywords"]
                target_subj = result["target_subject"]
                
                if keywords:
                    # İlk anahtar kelimeyi ve dersi kullanarak filtrele
                    search_query = f"{target_subj} {keywords[0]}"
                    self.txtAra.setText(search_query)
                    
                    if hasattr(host, "_toast"):
                         host._toast(f"Filtre uygulandı: {search_query}", duration=2000)
                elif target_subj:
                    self.txtAra.setText(target_subj)
                    
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Analiz sırasında hata: {e}")

    # ------------------------------ Kısayol/menü -------------------------
    def _ctx_menu(self, pos):
        m = QMenu(self)
        a1 = m.addAction("Tümünü işaretle")
        a2 = m.addAction("İşaretleri kaldır")
        a3 = m.addAction("İşaretleri tersine çevir")
        m.addSeparator()
        a4 = m.addAction("Yalnız gecikmişleri göster")
        a5 = m.addAction("Tümünü göster")
        m.addSeparator()
        a6 = m.addAction("Seçileni en üste getir")
        a7 = m.addAction("Seçileni panoya kopyala")
        act = m.exec(self.liste.mapToGlobal(pos))

        if act == a1:
            for i in range(self.liste.count()):
                self.liste.item(i).setCheckState(Qt.CheckState.Checked)
        elif act == a2:
            for i in range(self.liste.count()):
                self.liste.item(i).setCheckState(Qt.CheckState.Unchecked)
        elif act == a3:
            for i in range(self.liste.count()):
                it = self.liste.item(i)
                it.setCheckState(Qt.CheckState.Unchecked if it.checkState() == Qt.CheckState.Checked
                                 else Qt.CheckState.Checked)
        elif act == a4:
            self.txtAra.setText("")
            self._raw_items = [d for d in self._raw_items if (d.get("status") == "gecikmis")]
            self._apply_view()
        elif act == a5:
            self._yenile_click()
        elif act == a6:
            sel = self.selected_items()
            if sel:
                keys = set(self._key_of(d) for d in sel)
                rest = [d for d in self._raw_items if self._key_of(d) not in keys]
                self._raw_items = sel + rest
                self._apply_view()
        elif act == a7:
            sel = self.selected_items()
            if sel:
                txt = "\n".join(f"{d['ders']} / {d['kitap']} / {d['konu']} ({d['dk']} dk)" for d in sel)
                QApplication.clipboard().setText(txt)

    def _select_all(self):
        self.liste.selectAll()

    def _toggle_checked(self):
        for it in self.liste.selectedItems():
            it.setCheckState(Qt.CheckState.Unchecked if it.checkState() == Qt.CheckState.Checked
                             else Qt.CheckState.Checked)


class DersSiralamaDialog(QDialog):
    """Kullanıcının ders sekmelerinin sırasını özelleştirmesini ve
    Öğrenci, Alt Grup (örn. mezun-say, 12-say), Ana Grup (YKS, LGS) veya Genel
    kapsamında kalıcı kaydetmesini sağlayan modern diyalog."""
    def __init__(self, parent=None, current_lessons=None, student_info=None):
        super().__init__(parent)
        self.setWindowTitle("⇅ Ders Sekmelerinin Sırasını Düzenle")
        self.resize(380, 500)
        self.setMinimumSize(340, 440)
        self.lessons = list(current_lessons or [])
        self.student_info = student_info or {}
        self._init_ui()

    def _init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        lbl = QLabel("Ders sekmelerinin ekranda hangi sırayla dizileceğini belirleyin. İstediğiniz dersi seçip <b>Yukarı</b> veya <b>Aşağı</b> butonlarıyla taşıyabilirsiniz.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #475569; font-size: 11.5px;")
        lay.addWidget(lbl)

        # Kapsam seçici (Öğrenci, Alt Grup, Ana Grup, Genel)
        grp_scope = QGroupBox("💾 Sıralamanın Kaydedileceği Kapsam")
        grp_scope.setStyleSheet("""
            QGroupBox {
                font-weight: bold; font-size: 11px; color: #1e293b;
                border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 8px;
            }
        """)
        lay_scope = QVBoxLayout(grp_scope)
        lay_scope.setContentsMargins(8, 4, 8, 8)
        lay_scope.setSpacing(4)

        self.cmbScope = QComboBox()
        self.cmbScope.setStyleSheet("""
            QComboBox {
                background: white; border: 1px solid #cbd5e1; border-radius: 5px;
                padding: 4px 8px; font-size: 11.5px; font-weight: 600; color: #1e293b;
            }
        """)

        alt_grup = str(self.student_info.get("alt_grup") or "").strip()
        ana_grup = str(self.student_info.get("ana_grup") or "").strip()
        ad = str(self.student_info.get("ad") or "").strip()
        soyad = str(self.student_info.get("soyad") or "").strip()
        std_name = f"{ad} {soyad}".strip() or "Aktif Öğrenci"
        ogr_id = self.student_info.get("id")

        if alt_grup:
            self.cmbScope.addItem(f"👥 Alt Grup: {alt_grup} (Bu gruptaki tüm öğrenciler)", f"subgroup:{alt_grup}")
        if ana_grup:
            self.cmbScope.addItem(f"🎓 Ana Grup: {ana_grup} (Tüm {ana_grup} öğrencileri)", f"maingroup:{ana_grup}")
        if ogr_id:
            self.cmbScope.addItem(f"👤 Sadece Bu Öğrenci ({std_name})", f"student:{ogr_id}")
        self.cmbScope.addItem("🌐 Genel (Tüm Sistem / Varsayılan)", "global")

        lay_scope.addWidget(self.cmbScope)
        lay.addWidget(grp_scope)

        h_body = QHBoxLayout()
        h_body.setSpacing(8)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: white; border: 1px solid #cbd5e1; border-radius: 8px;
                padding: 4px; font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 10px; border-radius: 5px; margin: 1px 0px;
            }
            QListWidget::item:hover { background: #f1f5f9; }
            QListWidget::item:selected { background: #eff6ff; color: #1d4ed8; font-weight: bold; }
        """)

        for d in self.lessons:
            self.list_widget.addItem(d)

        h_body.addWidget(self.list_widget, 1)

        v_btns = QVBoxLayout()
        v_btns.setSpacing(6)
        v_btns.addStretch(1)

        btn_up = QPushButton("▲ Yukarı")
        btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_up.setStyleSheet("padding: 6px 12px; font-size: 11px; font-weight: 600; border-radius: 5px; border: 1px solid #cbd5e1; background: #f8fafc;")
        btn_up.clicked.connect(self._move_up)

        btn_down = QPushButton("▼ Aşağı")
        btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_down.setStyleSheet("padding: 6px 12px; font-size: 11px; font-weight: 600; border-radius: 5px; border: 1px solid #cbd5e1; background: #f8fafc;")
        btn_down.clicked.connect(self._move_down)

        v_btns.addWidget(btn_up)
        v_btns.addWidget(btn_down)
        v_btns.addStretch(1)
        h_body.addLayout(v_btns)

        lay.addLayout(h_body)

        h_foot = QHBoxLayout()
        btn_reset = QPushButton("↺ Sıfırla")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet("color: #64748b; background: transparent; border: none; font-size: 11px; font-weight: 500;")
        btn_reset.clicked.connect(self._reset_default)
        h_foot.addWidget(btn_reset)
        h_foot.addStretch(1)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet("padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11.5px;")
        btn_cancel.clicked.connect(self.reject)
        h_foot.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Kaydet")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; font-weight: bold;
                border-radius: 6px; padding: 6px 16px; font-size: 12px;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_save.clicked.connect(self._save)
        h_foot.addWidget(btn_save)

        lay.addLayout(h_foot)

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.list_widget.currentRow()
        if row >= 0 and row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)

    def _reset_default(self):
        scope_data = self.cmbScope.currentData() if hasattr(self, "cmbScope") else "global"
        try:
            from utils.settings import ayar_set
            if str(scope_data).startswith("subgroup:"):
                sub_grp = scope_data.split(":", 1)[1].strip().lower()
                key = f"custom_tab_order_subgroup_{sub_grp}"
            elif str(scope_data).startswith("maingroup:"):
                main_grp = scope_data.split(":", 1)[1].strip().lower()
                key = f"custom_tab_order_maingroup_{main_grp}"
            elif str(scope_data).startswith("student:"):
                std_id = scope_data.split(":", 1)[1].strip()
                key = f"custom_tab_order_student_{std_id}"
            else:
                key = "custom_lesson_tab_order"
            ayar_set(key, "")
        except Exception:
            pass
        self.accept()

    def _save(self):
        new_order = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        scope_data = str(self.cmbScope.currentData() if hasattr(self, "cmbScope") else "global")
        scope_label = self.cmbScope.currentText() if hasattr(self, "cmbScope") else "Genel"
        try:
            import json
            from utils.settings import ayar_set
            if scope_data.startswith("subgroup:"):
                sub_grp = scope_data.split(":", 1)[1].strip().lower()
                key = f"custom_tab_order_subgroup_{sub_grp}"
            elif scope_data.startswith("maingroup:"):
                main_grp = scope_data.split(":", 1)[1].strip().lower()
                key = f"custom_tab_order_maingroup_{main_grp}"
            elif scope_data.startswith("student:"):
                std_id = scope_data.split(":", 1)[1].strip()
                key = f"custom_tab_order_student_{std_id}"
            else:
                key = "custom_lesson_tab_order"
            ayar_set(key, json.dumps(new_order))
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Başarılı", f"Ders sekme sıralaması başarıyla kaydedildi:\n\n{scope_label}")
        except Exception as e:
            print("save tab order error:", e)
        self.accept()


# === PART 2/7 — updated ===



class OdevTakipFormu(QWidget):
    def __init__(self, ebeveyn=None, ogrenci_id: int | None = None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Ödev Takip")

        # Randevu’dan gelebilecek “hedef öğrenci”
        self._pending_student_id = ogrenci_id  # None ise normal (manuel) akış

        # ---- mevcut alanlarınız (dokunmayın) ----
        self._verilen_rows = []
        self._in_verilen_update = False
        self._ders_tablolari = {}
        self.oneri = None
        self._oneri_dlg = None

        # UI + öğrenci listesini yükle
        self._build_ui()
        self._ogrencileri_yukle()  # combolar burada dolar

        # Açılış tamamlanınca hedefi uygula:
        if self._pending_student_id is not None:
            QTimer.singleShot(
                0,
                lambda oid=int(self._pending_student_id): self.select_student_by_id(oid, autoload=True)
            )
        else:
            QTimer.singleShot(0, self._auto_load_on_open)
        
        # Apply modern visuals
        self._apply_visuals()

    def _apply_visuals(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; background-color: #f9fafb; color: #1f2937; }
            
            /* Tabs - Ultra Compact */
            QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 6px; }
            QTabBar { qproperty-drawBase: 0; qproperty-elideMode: 3; qproperty-expanding: 0; }
            QTabBar::tab {
                background: #f3f4f6; color: #475569; 
                padding: 6px 16px; 
                font-size: 12px; 
                font-weight: 600;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background: #fff; color: #2563eb; font-weight: bold; border-bottom: 2px solid #2563eb; 
            }
            QTabBar::tab:hover { background: #e5e7eb; }

            /* Buttons - Base */
            QPushButton { 
                border-radius: 6px; padding: 6px 12px; font-weight: 600; font-size: 12px;
                background-color: #ffffff; border: 1px solid #cbd5e1; color: #334155;
            }
            QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; }
            QPushButton:pressed { background-color: #e2e8f0; }

            /* Primary (Blue) - Actions */
            QPushButton#btnPrimary, QPushButton#btnAction {
                background-color: #2563eb; color: white; border: 1px solid #2563eb;
            }
            QPushButton#btnPrimary:hover, QPushButton#btnAction:hover { 
                background-color: #1d4ed8; border-color: #1d4ed8; 
            }

            /* Danger (Pastel Red) - Delete/Clear */
            QPushButton#btnDanger {
                background-color: #fee2e2; color: #dc2626; border: 1px solid #fecaca;
            }
            QPushButton#btnDanger:hover { 
                background-color: #fecaca; 
            }

            /* Excel (Pastel Green) */
            QPushButton#btnExcel {
                background-color: #ecfdf5; color: #059669; border: 1px solid #a7f3d0;
            }
            QPushButton#btnExcel:hover { 
                background-color: #d1fae5; 
            }
            
            /* Info/Wizard (Pastel Purple) */
            QPushButton#btnInfo {
                background-color: #f3e8ff; color: #7c3aed; border: 1px solid #e9d5ff;
            }
            QPushButton#btnInfo:hover { 
                background-color: #e9d5ff; 
            }

            /* WhatsApp (Green) */
            QPushButton#btnSuccess {
                 background-color: #dcfce7; color: #15803d; border: 1px solid #bbf7d0;
            }
            QPushButton#btnSuccess:hover {
                 background-color: #bbf7d0;
            }

            /* Inputs */
            QLineEdit, QDateEdit, QComboBox {
                border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 8px; background: white;
            }
            QSpinBox {
                border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 18px 4px 6px; background: white;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #cbd5e1;
                border-bottom: 1px solid #e2e8f0;
                background: #f8fafc;
                border-top-right-radius: 5px;
            }
            QSpinBox::up-button:hover { background: #e2e8f0; }
            QSpinBox::up-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-bottom: 4px solid #475569;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #cbd5e1;
                background: #f8fafc;
                border-bottom-right-radius: 5px;
            }
            QSpinBox::down-button:hover { background: #e2e8f0; }
            QSpinBox::down-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid #475569;
            }
            QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 2px solid #2563eb; padding: 5px 7px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
                margin-right: 8px;
            }
            
            /* Table - Fix scrollbar overlap by ensuring spacing/margins */
            QTableWidget { 
                border: 1px solid #e2e8f0; gridline-color: #f1f5f9; 
                padding-bottom: 2px; /* Slight padding at bottom */
            }
            QHeaderView::section { background-color: #f9fafb; padding: 4px; border: none; border-bottom: 2px solid #e5e7eb; font-weight: bold; }
            
            /* Modern Scrollbars */
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }

            QScrollBar:horizontal {
                border: none;
                background: #f1f5f9;
                height: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)
        combo_style = """
            QComboBox {
                border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px; background: white;
            }
            QComboBox:focus { border: 2px solid #2563eb; }
            QComboBox::drop-down {
                subcontrol-origin: padding; subcontrol-position: top right;
                width: 24px; border: none; background: transparent;
            }
            QComboBox::down-arrow {
                image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 5px solid #64748b; margin-right: 8px;
            }
        """
        for cb in (getattr(self, "cmbAd", None), getattr(self, "cmbSoyad", None), getattr(self, "cmbAraKolon", None)):
            if cb:
                cb.setStyleSheet(combo_style)
            
    def _apply_modern_visuals(self):
        """
        Ultra-compact design + scrollbar fix + THEME AWARE colors.
        """
        # Tema modunu algıla
        if appset:
            tema = (appset.ayar_get("tema", "açık") or "açık").lower()
            is_dark = tema in ("koyu", "dark")
        else:
            is_dark = False

        if is_dark:
            # DARK MODE RENKLERİ
            bg_main    = "#1f2937"  # Ana arka plan
            bg_card    = "#111827"  # Kartlar / Tablolar
            bg_input   = "#374151"  # Girdiler
            fg_text    = "#f3f4f6"  # Metin
            fg_subtle  = "#9ca3af"  # Silik metin
            
            border_col = "#4b5563"  # Kenarlıklar
            grid_col   = "#374151"  # Tablo çizgileri
            
            btn_bg     = "#374151"
            btn_fg     = "#f3f4f6"
            btn_hover  = "#4b5563"
            
            tab_bg      = "#1f2937"
            tab_fg      = "#9ca3af"
            tab_sel_bg  = "#111827"
            tab_sel_fg  = "#60a5fa"
            
            scroll_bg   = "#1f2937"
            scroll_hnd  = "#4b5563"
            
            hdr_bg      = "#374151"
            hdr_border  = "#4b5563"
            
        else:
            # LIGHT MODE RENKLERİ (Mevcut)
            bg_main    = "#ffffff"  # veya transparent
            bg_card    = "#ffffff"
            bg_input   = "#ffffff"
            fg_text    = "#1f2937"
            fg_subtle  = "#374151"
            
            border_col = "#e5e7eb"
            grid_col   = "#f3f4f6"
            
            btn_bg     = "#f9fafb"
            btn_fg     = "#1f2937"
            btn_hover  = "#f3f4f6"
            
            tab_bg      = "#f3f4f6"
            tab_fg      = "#374151"
            tab_sel_bg  = "#ffffff"
            tab_sel_fg  = "#2563eb"
            
            scroll_bg   = "#f1f1f1"
            scroll_hnd  = "#c1c1c1"

            hdr_bg      = "#f9fafb"
            hdr_border  = "#e5e7eb"

        self.setStyleSheet(f"""
            QWidget {{ font-family: 'Segoe UI', sans-serif; font-size: 11px; }}
            
            /* Tabs - Ultra Compact */
            QTabWidget::pane {{ border: 1px solid {border_col}; border-radius: 6px; background: {bg_card}; }}
            QTabBar::tab {{
                background: {tab_bg}; color: {tab_fg}; 
                padding: 4px 6px; /* Very tight padding */
                font-size: 10px; /* Small font */
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 1px;
            }}
            QTabBar::tab:selected {{ 
                background: {tab_sel_bg}; color: {tab_sel_fg}; font-weight: bold; border-bottom: 2px solid {tab_sel_fg}; 
            }}
            QTabBar::tab:hover {{ background: {btn_hover}; }}

            /* Buttons */
            QPushButton {{ 
                border-radius: 6px; padding: 6px 12px; font-weight: 500; font-size: 11px;
                background-color: {btn_bg}; border: 1px solid {border_col}; color: {btn_fg};
            }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
            
            /* Color Classes (Override defaults) */
            QPushButton#btnPrimary {{ background-color: #2563eb; color: white; border: 1px solid #2563eb; }}
            QPushButton#btnPrimary:hover {{ background-color: #1d4ed8; border-color: #1d4ed8; }}
            
            QPushButton#btnAction {{ background-color: #059669; color: white; border: 1px solid #059669; }}
            QPushButton#btnAction:hover {{ background-color: #047857; border-color: #047857; }}
            
            QPushButton#btnSuccess {{ background-color: #25D366; color: white; border: 1px solid #25D366; font-weight: bold; }}
            QPushButton#btnSuccess:hover {{ background-color: #128C7E; border-color: #128C7E; }}

            QPushButton#btnInfo {{ background-color: #8b5cf6; color: white; border: 1px solid #8b5cf6; }}
            QPushButton#btnInfo:hover {{ background-color: #7c3aed; border-color: #7c3aed; }}

            QPushButton#btnDanger {{ background-color: #fee2e2; color: #dc2626; border: 1px solid #fecaca; }}
            QPushButton#btnDanger:hover {{ background-color: #fecaca; }}
            /* Koyu modda danger butonu çok parlak kalmasın */
            /* İstenirse buraya 'if is_dark: ...' ile özel renk verilebilir ancak standart renkler kalsa da olur */

            /* Inputs */
            QLineEdit, QDateEdit, QComboBox {{
                border: 1px solid {border_col}; border-radius: 6px; padding: 4px 8px; 
                background: {bg_input}; color: {fg_text};
            }}
            QSpinBox {{
                border: 1px solid {border_col}; border-radius: 6px; padding: 4px 18px 4px 6px; 
                background: {bg_input}; color: {fg_text};
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid {border_col};
                border-bottom: 1px solid {border_col};
                background: {bg_input};
                border-top-right-radius: 5px;
            }}
            QSpinBox::up-button:hover {{ background: {bg_hover}; }}
            QSpinBox::up-arrow {{
                image: none;
                width: 0; height: 0;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-bottom: 4px solid {fg_text};
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid {border_col};
                background: {bg_input};
                border-bottom-right-radius: 5px;
            }}
            QSpinBox::down-button:hover {{ background: {bg_hover}; }}
            QSpinBox::down-arrow {{
                image: none;
                width: 0; height: 0;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid {fg_text};
            }}
            QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border-color: #2563eb;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
                margin-right: 8px;
            }}
            
            /* Table */
            QTableWidget {{ 
                background-color: {bg_card}; color: {fg_text};
                border: 1px solid {border_col}; gridline-color: {grid_col}; 
                padding-bottom: 2px;
            }}
            QHeaderView::section {{ 
                background-color: {hdr_bg}; padding: 4px; border: none; 
                border-bottom: 2px solid {hdr_border}; font-weight: bold; color: {fg_text};
            }}
            
            /* Scrollbars */
            QScrollBar:horizontal {{
                height: 12px;
                background: {scroll_bg};
            }}
            QScrollBar::handle:horizontal {{
                background: {scroll_hnd};
                border-radius: 6px;
            }}
            QScrollBar:vertical {{
                width: 12px;
                background: {scroll_bg};
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_hnd};
                border-radius: 6px;
            }}
            
            /* GroupBox / Label */
            QGroupBox {{ color: {fg_text}; }}
            QLabel {{ color: {fg_text}; }}
        """)



    def select_student_by_id(self, ogr_id: int, autoload: bool = True):
        """
        Combobox’larda ogr_id taşıyan item’ı bulur, hem Ad hem Soyad combolarını o index’e getirir.
        autoload=True ise, hemen _bilgileri_getir() çağırır.
        """
        try:
            target_idx = -1
            for i in range(self.cmbAd.count()):
                try:
                    if int(self.cmbAd.itemData(i)) == int(ogr_id):
                        target_idx = i
                        break
                except Exception:
                    pass

            if target_idx >= 0:
                # Sinyalleri kısa süre bloklayıp ikisini aynı index’e getir
                b1 = self.cmbAd.blockSignals(True)
                b2 = self.cmbSoyad.blockSignals(True)
                try:
                    self.cmbAd.setCurrentIndex(target_idx)
                    self.cmbSoyad.setCurrentIndex(target_idx)
                finally:
                    self.cmbAd.blockSignals(b1)
                    self.cmbSoyad.blockSignals(b2)

                if autoload:
                    try:
                        self._bilgileri_getir()
                    except Exception:
                        pass
        except Exception:
            pass

    def _auto_load_on_open(self):
        """
        Form ilk açıldığında:
          - pending id varsa onu seç,
          - yoksa combodaki mevcut seçimi koru,
          - ardından bilgileri getir.
        Tek sefer çalışır.
        """
        if getattr(self, "_auto_loaded", False):
            return
        self._auto_loaded = True

        try:
            pending = getattr(self, "_pending_student_id", None)
        except Exception:
            pending = None

        try:
            current = self._secili_ogrenci_id()
        except Exception:
            current = None

        oid = pending or current

        if oid:
            try:
                self.select_student_by_id(oid, autoload=False)  # [RANA: optimize] iki kez yüklemeyi önle
            except Exception:
                pass
        else:
            try:
                if self.cmbAd.count() > 0:
                    b1 = self.cmbAd.blockSignals(True)  # [RANA: optimize]
                    b2 = self.cmbSoyad.blockSignals(True)  # [RANA: optimize]
                    try:
                        self.cmbAd.setCurrentIndex(0)
                        self.cmbSoyad.setCurrentIndex(0)
                    finally:
                        self.cmbAd.blockSignals(b1)
                        self.cmbSoyad.blockSignals(b2)
            except Exception:
                pass

        try:
            self._bilgileri_getir()
        except Exception:
            pass

    # -----------------------------------
    # Haftalık Plan: Son Kümeden Aktar
    # -----------------------------------
    def _wire_haftalik_plan(self):
        from PyQt6.QtWidgets import QPushButton
        hedef_metinler = {"haftalık plan oluştur", "haftalik plan olustur", "haftalık plan", "haftalik plan"}
        for b in self.findChildren(QPushButton):
            t = (b.text() or "").strip().lower()
            if t in hedef_metinler:
                try:
                    b.clicked.disconnect()  # tüm eski bağlantıları temizle
                except Exception:
                    pass
                # ESKİ: b.clicked.connect(self._haftalik_plan_son_kumeden)
                b.clicked.connect(self._open_weekly_plan_dialog)  # YENİ
                self._btnHaftalikPlan = b
                break

    def _son_kume_id(self, con, ogrenci_id: int):
        """Bu öğrencinin son 'odev_kume' kaydının id'sini döndür (yoksa None)."""
        try:
            row = con.execute(
                "SELECT id FROM odev_kume WHERE ogrenci_id=? ORDER BY id DESC LIMIT 1",
                (ogrenci_id,)
            ).fetchone()
            return int(row["id"]) if row else None
        except Exception:
            return None

    def _kume_satirlari(self, con, kume_id: int):
        """Kümedeki satırları döndürür (liste[sqlite3.Row])."""
        try:
            return con.execute(
                "SELECT ders, kitap, konu FROM odev_satir WHERE kume_id=? ORDER BY id",
                (kume_id,)
            ).fetchall()
        except Exception:
            return []

    def _open_smart_wizard(self):
        """
        Akıllı Ödev Sihirbazı'nı açar ve seçilenleri grid üzerinde işaretler.
        """
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Öğrenci Seçiniz", "Lütfen önce bir öğrenci seçip 'Bilgileri Getir' diyerek dersleri yükleyin.")
            return

        # Önce öğrencinin mevcut kitaplarını (griddeki sütunlar) topla
        av_books = {}
        if hasattr(self, '_ders_tablolari'):
            for d_adi, tbl in self._ders_tablolari.items():
                books = []
                # 0. sütun Konu ise, 1'den başla
                try:
                    cols = tbl.columnCount()
                    for c in range(1, cols):
                        h_item = tbl.horizontalHeaderItem(c)
                        if h_item:
                            books.append(h_item.text())
                except:
                    pass
                if books:
                    av_books[d_adi] = books

        from ui.smart_wizard_dialog import SmartWizardDialog
        dlg = SmartWizardDialog(ogrenci_id=ogr_id, parent=self, available_books=av_books)
        if dlg.exec():
            tasks = dlg.selected_homeworks
            if not tasks:
                return
            
            count = 0
            grid_checked = 0
            
            for t in tasks:
                ders = t.get("ders")
                kitap = t.get("kitap")
                konu = t.get("konu")
                dk = str(t.get("dk", 30))
                aciklama = t.get("aciklama") or t.get("reason") or ""
                
                # 1) Verilen tablosuna süre ve açıklamayla ekle
                try:
                    self._verilen_satir_ekle(ders, kitap, konu, dk, aciklama)
                    count += 1
                except Exception:
                    pass

                # 2) Sol grid hücresini bul ve işaretle
                try:
                    table_widget, r, c = self._hucre_bul(ders, kitap, konu)
                    if table_widget:
                        item = table_widget.item(r, c)
                        if not item:
                            item = QTableWidgetItem()
                            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                            item.setCheckState(Qt.CheckState.Unchecked)
                            table_widget.setItem(r, c, item)
                        
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                        if item.checkState() != Qt.CheckState.Checked:
                            item.setCheckState(Qt.CheckState.Checked)
                            grid_checked += 1
                except Exception:
                    pass

            try:
                self._toplam_sure_guncelle()
            except Exception:
                pass

            msg = f"{count} adet ödev 'Verilen Ödevler' listesine eklendi ({grid_checked} adet konu tablosunda işaretlendi)."
            QMessageBox.information(self, "İşlem Tamam", msg)

    def _haftalik_plan_son_kumeden(self):
        """Son ödev kümesini haftalık plana bas."""
        from PyQt6.QtWidgets import QMessageBox
        import db

        ogr_id = None
        try:
            ogr_id = self._secili_ogrenci_id()
        except Exception:
            pass
        if not ogr_id:
            QMessageBox.information(self, "Bilgi", "Önce bir öğrenci seçin.")
            return

        con = db.get_conn()
        kume_id = self._son_kume_id(con, ogr_id)
        if not kume_id:
            QMessageBox.information(self, "Bilgi", "Bu öğrenci için veritabanında son ödev kümesi bulunamadı.")
            return

        satirlar = self._kume_satirlari(con, kume_id)
        if not satirlar:
            QMessageBox.information(self, "Bilgi", "Son küme boş görünüyor.")
            return

        # Önce varsa toplu API’yi dene
        try:
            self._haftalik_plana_bas(satirlar)
        except Exception:
            # Parça parça ekle (fallback)
            for r in satirlar:
                ders = r["ders"];
                kitap = r["kitap"];
                konu = r["konu"]
                try:
                    self._verilen_satir_ekle(ders, kitap, konu, 0, "")
                except Exception:
                    pass
            try:
                self._toplam_sure_guncelle()
            except Exception:
                pass

        QMessageBox.information(self, "Tamam", "Son küme haftalık plana aktarıldı.")



    # ---- Yardımcılar ----
    def _secili_ogrenci_id(self) -> int | None:
        """
        Ad/Soyad combolarından seçili ogrenci_id (itemData) döner.
        İkisi de aynı id’yi taşıdığından biri yeterli.
        """
        try:
            val = self.cmbAd.currentData()
            return int(val) if val is not None else None
        except Exception:
            try:
                val = self.cmbSoyad.currentData()
                return int(val) if val is not None else None
            except Exception:
                return None

    def _secili_ogrenci_info(self) -> dict:
        """Seçili öğrencinin id, ad, soyad, ana_grup, alt_grup bilgilerini döner."""
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            return {}
        try:
            import db
            con = db.get_conn()
            row = con.execute("SELECT id, ad, soyad, ana_grup, alt_grup FROM ogrenci WHERE id=?", (ogr_id,)).fetchone()
            if row:
                return {
                    "id": row["id"],
                    "ad": row["ad"] or "",
                    "soyad": row["soyad"] or "",
                    "ana_grup": (row["ana_grup"] or "").strip(),
                    "alt_grup": (row["alt_grup"] or "").strip(),
                }
        except Exception:
            pass
        return {"id": ogr_id}

    def _ogrenci_listesi(self):
        con = db.get_conn()
        return db.listele_ogrenciler(con, aktif_yalniz=True)

    # ---- UI ----
    def _build_ui(self):
        # ---- IMPORTS ----
        from PyQt6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QTabWidget,
            QTableWidget, QDateEdit, QLineEdit, QCheckBox, QSpinBox,
            QFrame, QSizePolicy, QSplitter, QGridLayout, QHeaderView,
            QToolButton, QWidget
        )
        from PyQt6.QtCore import Qt, QDate, QTimer  # QTimer eklendi

        # ---------------- ROOT ----------------
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 12)
        root.setSpacing(10)

        # === STYLE INJECTION ===
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                color: #334155;
            }
            /* --- TABS --- */
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background: white;
                top: -1px; 
            }
            QTabBar::tab {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                margin-right: 2px;
                color: #64748b;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid white; /* Blend with pane */
                color: #2563eb;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: #e2e8f0;
                color: #1e293b;
            }

            /* --- INPUTS --- */
            QLineEdit, QComboBox, QDateEdit, QSpinBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                background: white;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #3b82f6; 
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 0px;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            
            /* --- TABLES --- */
            QTableWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff;
                selection-color: #1e3a8a;
                alternate-background-color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                border-right: 1px solid #e2e8f0;
                font-weight: bold;
                color: #475569;
            }
            
            /* --- SCROLLBARS --- */
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }

            QScrollBar:horizontal {
                border: none;
                background: #f1f5f9;
                height: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                min-width: 20px;
                border-radius: 5px;
            }

            /* --- BUTTONS --- */
            QPushButton {
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                border: 1px solid #d1d5db;
                background-color: white;
                color: #374151;
            }
            QPushButton:hover { background-color: #f9fafb; }
            
            QPushButton#btnPrimary {
                background-color: #3b82f6; 
                color: white; 
                border: 1px solid #2563eb;
            }
            QPushButton#btnPrimary:hover { background-color: #2563eb; }
            
            QPushButton#btnAction {
                background-color: #10b981; 
                color: white; 
                border: 1px solid #059669;
            }
            QPushButton#btnAction:hover { background-color: #059669; }
            
             QPushButton#btnDanger {
                background-color: #ef4444; 
                color: white; 
                border: 1px solid #dc2626;
            }
            QPushButton#btnDanger:hover { background-color: #dc2626; }
        """)

        # ---------------- ÜST BAR (KOMPAKT & MİNİMALİST) ----------------
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 2)
        top.setSpacing(6)

        # Ad/Soyad (Etiketler kaldırıldı, arama kutuları kompaktlaştırıldı)
        self.cmbAd, self.cmbSoyad = QComboBox(), QComboBox()
        ad_blk, soy_blk = QVBoxLayout(), QVBoxLayout()
        for blk in (ad_blk, soy_blk):
            blk.setContentsMargins(0, 0, 0, 0)
            blk.setSpacing(2)

        self.txtAraAd = QLineEdit()
        self.txtAraAd.setPlaceholderText("Ad ara…")
        self.txtAraAd.setFixedHeight(23)
        self.txtAraAd.setFixedWidth(85)
        self.txtAraAd.setStyleSheet("font-size: 11px;")

        self.txtAraSoyad = QLineEdit()
        self.txtAraSoyad.setPlaceholderText("Soyad ara…")
        self.txtAraSoyad.setFixedHeight(23)
        self.txtAraSoyad.setFixedWidth(85)
        self.txtAraSoyad.setStyleSheet("font-size: 11px;")

        self.cmbAd.setFixedHeight(23)
        self.cmbAd.setFixedWidth(85)
        self.cmbAd.setStyleSheet("font-size: 11px; font-weight: bold;")

        self.cmbSoyad.setFixedHeight(23)
        self.cmbSoyad.setFixedWidth(85)
        self.cmbSoyad.setStyleSheet("font-size: 11px; font-weight: bold;")

        ad_blk.addWidget(self.txtAraAd)
        ad_blk.addWidget(self.cmbAd)

        soy_blk.addWidget(self.txtAraSoyad)
        soy_blk.addWidget(self.cmbSoyad)

        top.addLayout(ad_blk)
        top.addLayout(soy_blk)

        # Öğrenci Akıllı Durum & İlerleme Kartı (Kompakt Rozet Barı)
        self.card_student_snapshot = QFrame()
        self.card_student_snapshot.setObjectName("StudentSnapshotCard")
        self.card_student_snapshot.setFixedHeight(27)
        self.card_student_snapshot.setStyleSheet("""
            QFrame#StudentSnapshotCard {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        h_snap = QHBoxLayout(self.card_student_snapshot)
        h_snap.setContentsMargins(8, 2, 8, 2)
        h_snap.setSpacing(8)

        self.lbl_snap_target = QLabel("🎯 Hedef: —")
        self.lbl_snap_target.setStyleSheet("font-weight: 700; font-size: 10.5px; color: #1e3a8a; background: #eff6ff; padding: 1px 6px; border-radius: 4px; border: 1px solid #bfdbfe;")
        
        self.lbl_snap_total = QLabel("📋 Toplam: 0")
        self.lbl_snap_total.setStyleSheet("font-size: 10.5px; font-weight: 600; color: #334155;")

        self.lbl_snap_pending = QLabel("⏳ Bekleyen: 0")
        self.lbl_snap_pending.setStyleSheet("font-size: 10.5px; font-weight: 600; color: #d97706;")

        self.lbl_snap_done = QLabel("✅ Biten: 0 (%0)")
        self.lbl_snap_done.setStyleSheet("font-size: 10.5px; font-weight: 600; color: #16a34a;")

        self.lbl_snap_countdown = QLabel("⏰ 7 Gün")
        self.lbl_snap_countdown.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #2563eb; background: #e0e7ff; padding: 1px 6px; border-radius: 4px;")

        h_snap.addWidget(self.lbl_snap_target)
        h_snap.addWidget(self.lbl_snap_total)
        h_snap.addWidget(self.lbl_snap_pending)
        h_snap.addWidget(self.lbl_snap_done)
        h_snap.addWidget(self.lbl_snap_countdown)
        
        top.addWidget(self.card_student_snapshot)

        l_bitis = QHBoxLayout()
        l_bitis.setSpacing(3)
        lbl_b = QLabel("Bitiş:")
        lbl_b.setStyleSheet("font-size: 11px; color: #475569;")
        l_bitis.addWidget(lbl_b)

        self.dtpBitis = QDateEdit()
        self.dtpBitis.setCalendarPopup(True)
        self.dtpBitis.setDate(QDate.currentDate().addDays(7))
        self.dtpBitis.setFixedWidth(98)
        self.dtpBitis.setFixedHeight(27)
        self.dtpBitis.setStyleSheet("font-size: 11px;")
        self.dtpBitis.dateChanged.connect(lambda *_: self._update_student_snapshot())
        l_bitis.addWidget(self.dtpBitis)
        top.addLayout(l_bitis)

        top.addStretch(1)

        # Aksiyonlar (Kompakt & Modern Butonlar)
        self.btnGetir = QPushButton("🔎 Getir")
        self.btnGetir.setToolTip("Öğrenci Bilgilerini ve Derslerini Yükle")
        self.btnGetir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnGetir.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; color: white; font-weight: bold; border-radius: 6px; border: 1px solid #2563eb; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)

        self.btnKitap = QPushButton("📚 Kitaplar")
        self.btnKitap.setToolTip("Kitap Ekle / Sil & Havuz Yönetimi")
        self.btnKitap.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnKitap.setStyleSheet("""
            QPushButton {
                background-color: #0891b2; color: white; font-weight: bold; border-radius: 6px; border: 1px solid #0e7490; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background-color: #0e7490; }
        """)

        self.btnKaydet = QPushButton("💾 Kaydet")
        self.btnKaydet.setToolTip("Verilen Ödevleri Sisteme Kaydet")
        self.btnKaydet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnKaydet.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white; font-weight: bold; border-radius: 6px; border: 1px solid #047857; padding: 4px 12px; font-size: 11.5px;
            }
            QPushButton:hover { background-color: #047857; }
        """)

        self.btnPlan = QPushButton("📅 Plan")
        self.btnPlan.setToolTip("Haftalık Akıllı Çalışma Planı Oluştur")
        self.btnPlan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnPlan.setStyleSheet("""
            QPushButton {
                background-color: #6366f1; color: white; font-weight: bold; border-radius: 6px; border: 1px solid #4f46e5; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background-color: #4f46e5; }
        """)
        
        self.btnKontrol = QPushButton("✅ Kontrol")
        self.btnKontrol.setToolTip("Ödev Kontrol & Değerlendirme Formunu Aç")
        self.btnKontrol.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnKontrol.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; font-weight: bold; border-radius: 6px; border: 1px solid #1d4ed8; padding: 4px 10px; font-size: 11.5px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        
        self.btnWhatsapp = QPushButton("WhatsApp'tan Gönder")

        for b in (self.btnGetir, self.btnKitap, self.btnKaydet, self.btnPlan, self.btnKontrol):
            b.setFixedHeight(27)
            top.addWidget(b)
        
        root.addLayout(top)

        # ---------------- ORTA BÖLGE (H SPLITTER) ----------------
        mid_split = QSplitter(Qt.Orientation.Horizontal)
        mid_split.setChildrenCollapsible(False)
        mid_split.setHandleWidth(6)

        # ---- Sol: Sekmeler & Hızlı Gezinti Çubuğu (GENİŞ) ----
        self.left_card = QWidget()
        left_lay = QVBoxLayout(self.left_card)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        tab_nav_bar = QFrame()
        tab_nav_bar.setObjectName("TabNavBar")
        tab_nav_bar.setStyleSheet("""
            QFrame#TabNavBar {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
        """)
        tab_nav_lay = QHBoxLayout(tab_nav_bar)
        tab_nav_lay.setContentsMargins(8, 4, 8, 4)
        tab_nav_lay.setSpacing(8)

        lbl_nav = QLabel("<b>📚 Dersler:</b>")
        lbl_nav.setStyleSheet("color: #1e293b; font-size: 12px;")
        tab_nav_lay.addWidget(lbl_nav)

        self.btn_cat_all = QPushButton("🎯 Tümü")
        self.btn_cat_say = QPushButton("📐 Sayısal")
        self.btn_cat_soz = QPushButton("📖 Sözel & EA")
        for b in (self.btn_cat_all, self.btn_cat_say, self.btn_cat_soz):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(26)
            b.setStyleSheet("""
                QPushButton {
                    background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 13px;
                    padding: 2px 12px; font-size: 11px; font-weight: 600; color: #475569;
                }
                QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
            """)
            tab_nav_lay.addWidget(b)

        tab_nav_lay.addStretch(1)

        self.btn_sort_tabs = QPushButton("⇅ Sırala")
        self.btn_sort_tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sort_tabs.setFixedHeight(26)
        self.btn_sort_tabs.setToolTip("Ders sekmelerinin sırasını özelleştir ve kalıcı olarak kaydet")
        self.btn_sort_tabs.setStyleSheet("""
            QPushButton {
                background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 13px;
                padding: 2px 10px; font-size: 11px; font-weight: 600; color: #475569;
            }
            QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
        """)
        self.btn_sort_tabs.clicked.connect(self._open_tab_reorder_dialog)
        tab_nav_lay.addWidget(self.btn_sort_tabs)

        tab_nav_lay.addWidget(QLabel("<font color='#64748b' size='2'>🔍 Hızlı Geç:</font>"))
        self.cmb_quick_lesson = QComboBox()
        self.cmb_quick_lesson.setMinimumWidth(180)
        self.cmb_quick_lesson.setFixedHeight(26)
        self.cmb_quick_lesson.setStyleSheet("""
            QComboBox {
                background: white; border: 1px solid #cbd5e1; border-radius: 6px;
                padding: 2px 8px; font-size: 11.5px; font-weight: 600; color: #1e293b;
            }
        """)
        tab_nav_lay.addWidget(self.cmb_quick_lesson)

        left_lay.addWidget(tab_nav_bar)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setMovable(True)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tabs.setMinimumWidth(750)
        left_lay.addWidget(self.tabs, 1)

        # Sinyal bağlantıları
        self.btn_cat_all.clicked.connect(lambda: self._jump_to_category("all"))
        self.btn_cat_say.clicked.connect(lambda: self._jump_to_category("say"))
        self.btn_cat_soz.clicked.connect(lambda: self._jump_to_category("soz"))
        self.cmb_quick_lesson.currentIndexChanged.connect(self._on_quick_lesson_selected)
        self.tabs.currentChanged.connect(self._on_tab_changed_sync_combo)
        self.tabs.tabBar().tabMoved.connect(self._on_tab_drag_moved)

        # ---- Sağ: Dikey splitter -> [Liste] / [Alt Grid] (KOMPAKT) ----
        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setChildrenCollapsible(False)
        right_split.setHandleWidth(6)
        right_split.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        right_split.setMinimumWidth(360)
        right_split.setMaximumWidth(560)

        # Üst (sağ): liste
        lst_wrap = QFrame()
        lst_wrap.setFrameShape(QFrame.Shape.NoFrame)
        lst_lay = QVBoxLayout(lst_wrap)
        lst_lay.setContentsMargins(0, 0, 0, 0)
        lst_lay.setSpacing(4)

        # Verilen ödevler mini başlık ve varsayılan süre kontrolü
        v_top_row = QHBoxLayout()
        v_top_row.setContentsMargins(2, 0, 2, 0)
        v_top_row.setSpacing(6)

        lbl_v_title = QLabel("<b>📋 Verilen Ödevler</b>")
        lbl_v_title.setStyleSheet("font-size: 11.5px; color: #1e293b;")
        v_top_row.addWidget(lbl_v_title)

        v_top_row.addStretch(1)

        lbl_def_dur = QLabel("⏱️ Varsayılan:")
        lbl_def_dur.setStyleSheet("font-size: 11px; color: #475569; font-weight: 500;")
        lbl_def_dur.setToolTip("Yeni eklenecek ödevler için varsayılan çalışma süresi")
        v_top_row.addWidget(lbl_def_dur)

        self.spVarsayilanSure = QSpinBox()
        self.spVarsayilanSure.setRange(5, 300)
        self.spVarsayilanSure.setSingleStep(5)
        self.spVarsayilanSure.setValue(45)
        self.spVarsayilanSure.setSuffix(" dk")
        self.spVarsayilanSure.setFixedWidth(82)
        self.spVarsayilanSure.setFixedHeight(26)
        self.spVarsayilanSure.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spVarsayilanSure.setStyleSheet("""
            QSpinBox {
                font-size: 11px;
                font-weight: bold;
                color: #1d4ed8;
                border: 1px solid #93c5fd;
                border-radius: 5px;
                background: white;
                padding-right: 17px;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #bfdbfe;
                border-bottom: 1px solid #bfdbfe;
                background: #eff6ff;
                border-top-right-radius: 4px;
            }
            QSpinBox::up-button:hover { background: #dbeafe; }
            QSpinBox::up-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-bottom: 4.5px solid #1d4ed8;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #bfdbfe;
                background: #eff6ff;
                border-bottom-right-radius: 4px;
            }
            QSpinBox::down-button:hover { background: #dbeafe; }
            QSpinBox::down-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-top: 4.5px solid #1d4ed8;
            }
        """)
        self.spVarsayilanSure.setToolTip("Yeni işaretlenen ödevlere otomatik atanacak süre (dk)")
        try:
            from utils.settings import ayar_get
            stored_def_dur = ayar_get("default_homework_duration_dk", "")
            if stored_def_dur and str(stored_def_dur).strip().isdigit():
                self.spVarsayilanSure.setValue(int(stored_def_dur))
        except Exception:
            pass
        self.spVarsayilanSure.valueChanged.connect(self._on_varsayilan_sure_changed)
        v_top_row.addWidget(self.spVarsayilanSure)

        btn_apply_all_dur = QToolButton()
        btn_apply_all_dur.setText("⚡ Tümüne")
        btn_apply_all_dur.setToolTip("Yukarıdaki süreyi listedeki TÜM ödevlerin süresi olarak uygula")
        btn_apply_all_dur.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply_all_dur.setFixedHeight(24)
        btn_apply_all_dur.setStyleSheet("""
            QToolButton {
                font-size: 10.5px; font-weight: 600; color: #2563eb;
                background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; padding: 2px 6px;
            }
            QToolButton:hover { background: #dbeafe; }
        """)
        btn_apply_all_dur.clicked.connect(self._apply_default_duration_to_all)
        v_top_row.addWidget(btn_apply_all_dur)

        lst_lay.addLayout(v_top_row)

        self.verilen = QTableWidget(0, 5)
        self.verilen.setHorizontalHeaderLabels(["Ders", "Kitap", "Konu", "Süre(dk)", "Açıklama"])
        self.verilen.setSortingEnabled(True)
        self.verilen.verticalHeader().setDefaultSectionSize(28)
        self.verilen.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.verilen.setMinimumWidth(360)
        #s
        from PyQt6.QtCore import Qt, QPoint
        from PyQt6.QtWidgets import QMenu, QInputDialog

        # ...verilen ödevler tablosu sağ tık menü için
        self.verilen.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.verilen.customContextMenuRequested.connect(self._popup_verilen_menu)

        #f

        hh = self.verilen.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        fm = self.verilen.fontMetrics()
        self.verilen.setColumnWidth(3, fm.horizontalAdvance("Süre(dk)") + 24)
        self.verilen.setColumnWidth(4, fm.horizontalAdvance("Açıklama") + 24)

        # Konu sütununu tam görünür yap (kesilmeden)
        from PyQt6.QtWidgets import QHeaderView as _QHV
        hh = self.verilen.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, _QHV.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, _QHV.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, _QHV.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, _QHV.ResizeMode.Interactive)
        hh.setSectionResizeMode(4, _QHV.ResizeMode.Interactive)
        self.verilen.setColumnWidth(3, 80)
        self.verilen.setColumnWidth(4, 120)
        self.verilen.setWordWrap(False)
        self.verilen.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.verilen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # [optimize] Büyük listede gereksiz relayout’u azalt
        self.verilen.setUpdatesEnabled(True)
        fn = getattr(self.verilen, "setUniformRowHeights", None)
        if callable(fn):
            fn(True)

        lst_lay.addWidget(self.verilen)
        right_split.addWidget(lst_wrap)

        # Alt (sağ): Organize edilmiş minimalist aksiyonlar
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.NoFrame)
        bar_lay = QVBoxLayout(bar)
        bar_lay.setContentsMargins(4, 4, 4, 4)
        bar_lay.setSpacing(5)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 1) Metrikler & Filtre/Temizle Barı
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        
        lbl_h = QLabel("<b>Hedef:</b>")
        lbl_h.setStyleSheet("font-size: 11px; color: #475569;")
        row1.addWidget(lbl_h)

        self.spHedefSure = QSpinBox()
        self.spHedefSure.setRange(0, 9999)
        self.spHedefSure.setValue(90)
        self.spHedefSure.setSuffix(" dk")
        self.spHedefSure.setFixedWidth(74)
        self.spHedefSure.setFixedHeight(26)
        self.spHedefSure.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spHedefSure.setStyleSheet("""
            QSpinBox {
                font-size: 11px;
                font-weight: bold;
                color: #1e3a8a;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background: white;
                padding-right: 17px;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #cbd5e1;
                border-bottom: 1px solid #e2e8f0;
                background: #f8fafc;
                border-top-right-radius: 4px;
            }
            QSpinBox::up-button:hover { background: #e2e8f0; }
            QSpinBox::up-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-bottom: 4.5px solid #475569;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid #cbd5e1;
                background: #f8fafc;
                border-bottom-right-radius: 4px;
            }
            QSpinBox::down-button:hover { background: #e2e8f0; }
            QSpinBox::down-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-top: 4.5px solid #475569;
            }
        """)
        row1.addWidget(self.spHedefSure)

        from PyQt6.QtWidgets import QProgressBar
        self.progWorkload = QProgressBar()
        self.progWorkload.setRange(0, 100)
        self.progWorkload.setTextVisible(False)
        self.progWorkload.setFixedWidth(65)
        self.progWorkload.setFixedHeight(12)
        self.progWorkload.setToolTip("Haftalık Yük Durumu")
        self.progWorkload.setStyleSheet("""
            QProgressBar { border: 1px solid #cbd5e1; border-radius: 6px; background: #f1f5f9; }
            QProgressBar::chunk { background-color: #22c55e; border-radius: 6px; }
        """)
        row1.addWidget(self.progWorkload)

        self.lblTopSure = QLabel("Toplam: 0 dk")
        self.lblTopSure.setStyleSheet("font-weight: bold; font-size: 11px; color: #1e293b;")
        row1.addWidget(self.lblTopSure)

        # Yük Analizi Label (Gizli)
        self.lblLoadAnalysis = QLabel("")
        self.lblLoadAnalysis.setVisible(False)
        row1.addWidget(self.lblLoadAnalysis)

        row1.addStretch(1)

        self.btnFiltre = QToolButton()
        self.btnFiltre.setText("🔍 Filtre")
        self.btnFiltre.setToolTip("Tablo Filtrelerini Aç / Kapat")
        self.btnFiltre.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnFiltre.setFixedHeight(24)
        self.btnFiltre.setStyleSheet("""
            QToolButton {
                color: #2563eb; font-weight: 600; font-size: 11px;
                border: 1px solid #bfdbfe; border-radius: 5px; background: #eff6ff; padding: 2px 8px;
            }
            QToolButton:hover { background: #dbeafe; }
        """)
        row1.addWidget(self.btnFiltre)

        self.btnTemizle = QPushButton("🧹 Temizle")
        self.btnTemizle.setObjectName("btnDanger")
        self.btnTemizle.setToolTip("Verilen Ödev Tablosunu Temizle")
        self.btnTemizle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnTemizle.setFixedHeight(24)
        self.btnTemizle.setStyleSheet("""
            QPushButton {
                background: #fef2f2; color: #dc2626; border: 1px solid #fecaca;
                border-radius: 5px; font-size: 11px; font-weight: 600; padding: 2px 8px;
            }
            QPushButton:hover { background: #fee2e2; }
        """)
        row1.addWidget(self.btnTemizle)
        bar_lay.addLayout(row1)

        # 2) Eylemler (Kompakt Tek Sıra: Öneri, Takvim, Yazdır, WhatsApp)
        row2 = QHBoxLayout()
        row2.setSpacing(5)

        self.btnOneriler = QPushButton("💡 Öneri")
        self.btnOneriler.setToolTip("Öğrenciye Özel Akıllı Ödev ve Konu Önerileri")
        self.btnOneriler.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnOneriler.setFixedHeight(26)
        self.btnOneriler.setStyleSheet("""
            QPushButton {
                background: #f8fafc; color: #475569; border: 1px solid #cbd5e1;
                border-radius: 6px; font-size: 11px; font-weight: 600; padding: 2px 6px;
            }
            QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
        """)
        row2.addWidget(self.btnOneriler)

        self.btnTakvim = QPushButton("🗓️ Takvim")
        self.btnTakvim.setToolTip("Haftalık Çalışma & Akıllı Takvim Planı Oluştur")
        self.btnTakvim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnTakvim.setFixedHeight(26)
        self.btnTakvim.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
                color: white; font-weight: bold; border-radius: 6px; border: none; font-size: 11px; padding: 2px 8px;
            }
            QPushButton:hover { background: #b45309; }
        """)
        self.btnTakvim.clicked.connect(self._open_smart_calendar_pdf)
        row2.addWidget(self.btnTakvim)

        self.btnYazdir = QPushButton("🖨️ Yazdır")
        self.btnYazdir.setToolTip("Ödev Listesini Yazdır / PDF Al")
        self.btnYazdir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnYazdir.setFixedHeight(26)
        self.btnYazdir.setStyleSheet("""
            QPushButton {
                background: #f8fafc; color: #475569; border: 1px solid #cbd5e1;
                border-radius: 6px; font-size: 11px; font-weight: 600; padding: 2px 8px;
            }
            QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
        """)
        row2.addWidget(self.btnYazdir)

        self.btnWhatsapp = QPushButton("💬 WhatsApp")
        self.btnWhatsapp.setToolTip("Öğrenci ve Veliye WhatsApp Ödev Raporu Gönder")
        self.btnWhatsapp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnWhatsapp.setFixedHeight(26)
        self.btnWhatsapp.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: white; font-weight: bold; border-radius: 6px; border: none; font-size: 11px; padding: 2px 8px;
            }
            QPushButton:hover { background: #047857; }
        """)
        row2.addWidget(self.btnWhatsapp)

        bar_lay.addLayout(row2)
        right_split.addWidget(bar)

        # Sağ içi oranlar (Tabloya maksimum dikey alan)
        right_split.setStretchFactor(0, 10)
        right_split.setStretchFactor(1, 1)
        right_split.setSizes([750, 68])

        # ---- Orta splitter: sol+sağ ----
        mid_split.addWidget(self.left_card)
        mid_split.addWidget(right_split)

        # Minimumlar ve başlangıç oranı
        self.tabs.setMinimumWidth(600)
        right_split.setMinimumWidth(360)
        mid_split.setSizes([900, 480])  # ilk dağılım (sol geniş)
        mid_split.setStretchFactor(0, 7)  # sol
        mid_split.setStretchFactor(1, 3)  # sağ

        root.addWidget(mid_split, 1)

        # ---------------- ALT BAR (genel - MİNİMALİST) ----------------
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 2, 0, 0)
        bottom.setSpacing(6)
        self.btnExcel = QPushButton("📊 Excel")
        self.btnExcel.setToolTip("Ödev ve ilerleme durumunu Excel formatında dışa aktar")
        self.btnPdfAyar = QPushButton("⚙️ PDF")
        self.btnPdfAyar.setToolTip("PDF çıktı ve rapor sayfa ayarlarını düzenle")
        self.btnDetayRapor = QPushButton("📄 Rapor")
        self.btnDetayRapor.setToolTip("Öğrenci genel ödev ve performans detay raporu")
        self.btnOneriEksik = QPushButton("⚠️ Eksikler")
        self.btnOneriEksik.setToolTip("Eksik veya gecikmiş konuları listele ve analiz et")
        self.btnOneriTakviye = QPushButton("⏰ Takviye")
        self.btnOneriTakviye.setToolTip("Yaklaşan ve geciken ödevler için takviye planı oluştur")
        self.btnSihirbaz = QPushButton("✨ Sihirbaz")
        self.btnSihirbaz.setToolTip("Akıllı ödevlendirme ve konu öneri sihirbazı")

        for b in (self.btnExcel, self.btnPdfAyar, self.btnDetayRapor, self.btnOneriEksik, self.btnOneriTakviye, self.btnSihirbaz):
            b.setFixedHeight(25)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 5px;
                    padding: 2px 8px; font-size: 11px; font-weight: 600; color: #475569;
                }
                QPushButton:hover {
                    background: #eff6ff; border-color: #3b82f6; color: #1d4ed8;
                }
            """)
            bottom.addWidget(b)
        bottom.addStretch(1)
        root.addLayout(bottom)

        # ---------------- SİNYALLER ----------------
        self.btnGetir.clicked.connect(self._bilgileri_getir)
        self.cmbAd.currentIndexChanged.connect(self._ad_degisti)
        self.cmbSoyad.currentIndexChanged.connect(self._soyad_degisti)
        self.btnKitap.clicked.connect(self._kitap_dialog)
        self.btnKaydet.clicked.connect(self._kaydet_kume)
        self.btnYazdir.clicked.connect(self._pdf_yazdir)
        self.btnPdfAyar.clicked.connect(self._pdf_ayar)

        # Filtre altyapısı
        self.lblAraVerilen = QLabel("Hızlı Arama:")
        self.txtAraVerilen = QLineEdit()
        self.txtAraVerilen.setPlaceholderText("Ara...")
        self.chkRegex = QCheckBox("Regex")
        self.cmbAraKolon = QComboBox()
        self.cmbAraKolon.addItems(["Tümü", "Ders", "Kitap", "Konu", "Süre", "Açıklama"])
        self.chkGeciken = QCheckBox('Sadece gecikenler')
        self.chkBuHafta = QCheckBox('Bu hafta bitecek')

        self.btnFiltre.clicked.connect(self._show_filter_dialog)
        self.txtAraVerilen.textChanged.connect(self._filtre_verilen)
        self.chkGeciken.toggled.connect(self._filtre_verilen)
        self.chkBuHafta.toggled.connect(self._filtre_verilen)
        self.chkRegex.toggled.connect(self._filtre_verilen)
        self.cmbAraKolon.currentIndexChanged.connect(self._filtre_verilen)

        self.btnTemizle.clicked.connect(self._temizle_verilen)
        self.btnWhatsapp.clicked.connect(self._whatsapp_gonder)
        self.btnKontrol.clicked.connect(self._odev_kontrol)
        self.verilen.itemChanged.connect(self._toplam_sure_guncelle)
        self.spHedefSure.valueChanged.connect(lambda *_: self._toplam_sure_guncelle())
        self.btnDetayRapor.clicked.connect(self._detayli_rapor)
        self.btnOneriEksik.clicked.connect(self._akilli_eksik_konular)
        self.btnOneriTakviye.clicked.connect(self._akilli_takviye)

        # --- Haftalık Plan: tek ve temiz connect ---
        try:
            self.btnPlan.clicked.disconnect()  # tüm eski bağlantıları kes
        except Exception:
            pass
        self.btnPlan.clicked.connect(self._open_weekly_plan_dialog)

        # “Verilen” tablosuna diyalog açıkken sızma olursa kullanacağımız bayrak
        self._suppress_verilen = False

        self.btnOneriler.clicked.connect(self._open_oneri_dialog)
        self.btnExcel.clicked.connect(self._export_all_lists_to_excel)
        self.btnSihirbaz.clicked.connect(self._open_smart_wizard)

        self._yukle_verilen_kolon_genislik()
        self.verilen.horizontalHeader().sectionResized.connect(self._kaydet_verilen_kolon_genislik)

        self.txtAraAd.textChanged.connect(self._apply_ogrenci_filter)
        self.txtAraSoyad.textChanged.connect(self._apply_ogrenci_filter)

        # Başlangıç sonrası görünüm/tablolar
        QTimer.singleShot(0, self._polish_left_tables)
        QTimer.singleShot(0, self._apply_tables_visuals)

        self._apply_odev_takip_theme()
        QTimer.singleShot(0, self._boost_table_headers)

        # [optimize] Eski meta-bağlayıcı kapalı kalsın
        # QTimer.singleShot(0, self._wire_haftalik_plan)

        # Sol listedeki TÜM tabloları ayarla
        from utils.table_tune import apply_simple_tuning_to_left_tables
        QTimer.singleShot(0, lambda: apply_simple_tuning_to_left_tables(self))

    #s verilen ödevler tablosu sağ tık menü
    def _popup_verilen_menu(self, pos):
        index = self.verilen.indexAt(pos)
        if not index.isValid() and not self.verilen.selectedIndexes():
            return

        global_pos = self.verilen.viewport().mapToGlobal(pos)

        menu = QMenu(self)

        # ---- HOVER / GÖRÜNÜM STİLİ (Modern & Pratik) ----
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

        # ===========================
        #  1) SEÇİLİ SATIR İŞLEMLERİ
        # ===========================
        act_edit = menu.addAction("✏️  Bu satırı düzenle…")
        act_same = menu.addAction("📝  Seçili satırlara aynı süreyi ver…")
        act_auto = menu.addAction("🤖  Seçili satırlara tahmini süre ata")
        act_clear = menu.addAction("🗑️  Seçili satırları sıfırla (0 dk)")

        menu.addSeparator()

        # ===========================
        #  2) TÜM SÜTUN İŞLEMLERİ
        # ===========================
        act_all_same = menu.addAction("🔄  Tüm satırlara aynı süreyi ver…")
        act_fill_empty = menu.addAction("✨  Boş olanları doldur…")
        act_clear_all = menu.addAction("🧹  Tüm listeyi temizle (0 dk)")

        menu.addSeparator()

        # ===========================
        #  3) HEDEF İLE İLGİLİ AKILLI İŞLEMLER
        # ===========================
        act_distribute = menu.addAction("⚖️  Hedef (dk) değerini paylaştır")
        act_target_from_total = menu.addAction("🎯  Hedefi toplama eşitle")

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        # Seçili satırlar
        rows = sorted({i.row() for i in self.verilen.selectedIndexes()})
        if not rows and index.isValid():
            rows = [index.row()]

        # Küçük yardımcılar
        def _visible_rows():
            res = []
            for r in range(self.verilen.rowCount()):
                if self.verilen.isRowHidden(r):
                    continue
                res.append(r)
            return res

        def _get_int(text, default=0):
            try:
                return int(text)
            except Exception:
                return default

        # =====================
        #  1) SEÇİLİ SATIRLAR
        # =====================

        # 1.a) Tek satır düzenle
        if chosen is act_edit and index.isValid():
            r = index.row()
            current = _get_int(self._vtext(r, 3), 0)
            dk, ok = QInputDialog.getInt(
                self,
                "Süre (dk)",
                "Bu ödev için süre:",
                current,
                0,
                9999,
                5,
            )
            if not ok:
                return
            self._ensure_vcell(r, 3, str(dk))

        # 1.b) Seçili satırlara aynı süre
        elif chosen is act_same and rows:
            dk, ok = QInputDialog.getInt(
                self,
                "Süre (dk)",
                "Seçili tüm satırlar için süre:",
                20,
                0,
                9999,
                5,
            )
            if not ok:
                return
            for r in rows:
                self._ensure_vcell(r, 3, str(dk))

        # 1.c) Seçili satırlara tahmini süre
        elif chosen is act_auto and rows:
            for r in rows:
                ders = self._vtext(r, 0)
                kitap = self._vtext(r, 1)
                konu = self._vtext(r, 2)
                dk_val = 0
                try:
                    if hasattr(self, "_tahmini_sure"):
                        dk_val = int(self._tahmini_sure(ders, kitap, konu) or 0)
                except Exception:
                    dk_val = 0
                if dk_val <= 0:
                    dk_val = 20  # fallback
                self._ensure_vcell(r, 3, str(dk_val))

        # 1.d) Seçili satırların süresini sıfırla
        elif chosen is act_clear and rows:
            for r in rows:
                self._ensure_vcell(r, 3, "0")

        # =====================
        #  2) TÜM SÜTUN İŞLEMLERİ
        # =====================

        # 2.a) Tüm satırlara aynı süre
        elif chosen is act_all_same:
            all_rows = _visible_rows()
            if not all_rows:
                return
            dk, ok = QInputDialog.getInt(
                self,
                "Süre (dk)",
                "Tüm satırlar için süre:",
                20,
                0,
                9999,
                5,
            )
            if not ok:
                return
            for r in all_rows:
                self._ensure_vcell(r, 3, str(dk))

        # 2.b) Sadece süresi 0/boş olanlara süre
        elif chosen is act_fill_empty:
            all_rows = _visible_rows()
            if not all_rows:
                return
            dk, ok = QInputDialog.getInt(
                self,
                "Süre (dk)",
                "Süresi 0/boş olan satırlar için süre:",
                20,
                0,
                9999,
                5,
            )
            if not ok:
                return
            for r in all_rows:
                mevcut = _get_int(self._vtext(r, 3), 0)
                if mevcut <= 0:
                    self._ensure_vcell(r, 3, str(dk))

        # 2.c) Tüm satırların süresini sıfırla
        elif chosen is act_clear_all:
            all_rows = _visible_rows()
            for r in all_rows:
                self._ensure_vcell(r, 3, "0")

        # =====================
        #  3) HEDEF İLE İLGİLİ
        # =====================

        # 3.a) Hedef (dk)’yi seçili satırlara paylaştır
        elif chosen is act_distribute and rows and hasattr(self, "spHedefSure"):
            hedef = int(self.spHedefSure.value() or 0)
            if hedef <= 0:
                QMessageBox.information(self, "Hedef yok", "Önce Hedef (dk) alanına bir değer gir.")
                return

            n = len(rows)
            if n == 0:
                return

            # Eşit paylaştırma (örneğin 90 dk, 3 satır → 30 dk + kalan 0)
            base = hedef // n
            extra = hedef % n  # kalan dk'ları ilk satırlara 1'er dk ekleyelim

            for idx, r in enumerate(rows):
                value = base + (1 if idx < extra else 0)
                self._ensure_vcell(r, 3, str(max(0, value)))

        # 3.b) Hedef (dk)’yi listedeki toplam süreden ayarla
        elif chosen is act_target_from_total and hasattr(self, "spHedefSure"):
            top = 0
            for r in _visible_rows():
                top += _get_int(self._vtext(r, 3), 0)
            self.spHedefSure.setValue(top)

        # Menü sonrası toplamı güncelle
        try:
            self._toplam_sure_guncelle()
        except Exception:
            pass
    #f


    # s görsellik
    def _apply_odev_takip_theme(self):
        """
        Ödev Takip formu için sadece GÖRSEL dokunuşlar.
        İşlevsel hiçbir şeyi değiştirmez.
        """
        from PyQt6.QtGui import QFont, QColor
        from PyQt6.QtWidgets import QAbstractItemView, QHeaderView

        base_font = QFont();
        base_font.setPointSizeF(11.0)
        self.setFont(base_font)

        pill_css = """
        QPushButton {
            background:#1d4ed8; color:#ffffff; border:none;
            border-radius:12px; padding:6px 12px; font-weight:600;
        }
        QPushButton:hover { background:#2563eb; }
        QPushButton:pressed { background:#1e3a8a; }
        QPushButton:disabled { background:#93a5ff; color:#eef2ff; }
        """
        for b in (self.btnGetir, self.btnKitap, self.btnKaydet, self.btnPlan,
                  self.btnKontrol, self.btnWhatsapp,
                  self.btnTemizle, self.btnYazdir, self.btnOneriler,
                  self.btnExcel, self.btnPdfAyar, self.btnDetayRapor,
                  self.btnOneriEksik, self.btnOneriTakviye):
            if b:
                b.setStyleSheet(pill_css)

        self.btnFiltre.setStyleSheet("""
            QToolButton{ color:#2563eb; font-weight:600; padding:2px 4px; }
            QToolButton:hover{ text-decoration: underline; }
        """)

        self.dtpBitis.setStyleSheet("""
            QDateEdit {
                background:#ffffff; border:1px solid #d0d7e2; border-radius:8px;
                padding:4px 8px;
            }
            QDateEdit:focus { border-color:#9ec1ff; }
        """)

        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border:1px solid #e5e7eb; border-radius:10px; padding:6px; background:#ffffff;
            }
            QTabBar::tab {
                background:#f3f4f6; border:1px solid #e5e7eb; border-bottom:none;
                padding:8px 14px; margin-right:6px; border-top-left-radius:8px; border-top-right-radius:8px;
                font-weight:600; color:#334155;
            }
            QTabBar::tab:selected { background:#eaf1ff; border-color:#cfe0ff; color:#0b3b80; }
            QTabBar::tab:hover { background:#eef2ff; }
        """)

        t = self.verilen
        t.horizontalHeader().setHighlightSections(False)
        t.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        t.horizontalHeader().setFixedHeight(34)
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        t.verticalHeader().setVisible(False)
        t.setShowGrid(False)
        t.setStyleSheet("""
            QTableView {
                background:#ffffff; alternate-background-color:#fafbff;
                gridline-color:#eef2f7; selection-background-color:#eaf1ff;
                selection-color:#0b3b80; border:1px solid #e5e7eb; border-radius:10px;
            }
            QHeaderView::section {
                background:#f8fafc; color:#334155; padding:6px 10px;
                border:1px solid #e5e7eb; border-top-left-radius:8px; border-top-right-radius:8px;
            }
            QTableView::item { padding-left:8px; padding-right:8px; }
            QTableView::item:selected { background:#eaf1ff; color:#0b3b80; }
        """)
        hh: QHeaderView = t.horizontalHeader()
        hh.setSectionsClickable(True);
        hh.setStretchLastSection(False)
        t.verticalHeader().setDefaultSectionSize(30)

        # Splitter görselliği
        for sp in self.findChildren(QSplitter):
            sp.setStyleSheet("""
                QSplitter::handle { background:#eef2f7; margin:0px; }
                QSplitter::handle:hover { background:#dbe5ff; }
            """)

        self.lblTopSure.setStyleSheet("QLabel{ color:#0f172a; font-weight:600; }")

        for le in (self.txtAraAd, self.txtAraSoyad, self.txtAraVerilen):
            if le:
                le.setStyleSheet("""
                    QLineEdit {
                        background:#ffffff; border:1px solid #d0d7e2; border-radius:8px;
                        padding:4px 8px;
                    }
                    QLineEdit:focus { border-color:#9ec1ff; }
                """)

        for cb in (self.cmbAd, self.cmbSoyad, self.cmbAraKolon):
            if cb:
                cb.setStyleSheet("""
                    QComboBox {
                        background:#ffffff; border:1px solid #d0d7e2; border-radius:8px;
                        padding:4px 8px;
                    }
                    QComboBox:focus { border-color:#9ec1ff; }
                    QComboBox::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 24px;
                        border: none;
                        background: transparent;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 4px solid transparent;
                        border-right: 4px solid transparent;
                        border-top: 5px solid #64748b;
                        margin-right: 8px;
                    }
                """)

        # Sağ alt bar çerçevesi (varsa)
        try:
            frame = self.findChild(QFrame)
            if frame:
                frame.setStyleSheet("QFrame { background:#ffffff; border:1px solid #e5e7eb; border-radius:10px; }")
        except Exception:
            pass

    def _boost_table_headers(self):
        """
        - Tüm tabloların başlıklarını (header) daha belirgin ve okunur yapar.
        - self.verilen satırlarını 'Ders' sütununa göre PASTEL renklendirir (kalıcı).
        - Satırlar arası boşluğu arttırır, hücre içi yatay padding ekler.
        - Tablonun tamamına hafif gölge verir.
        """
        from PyQt6.QtCore import Qt, QTimer, QRect, QSize
        from PyQt6.QtGui import QFont, QColor, QPainter
        from PyQt6.QtWidgets import (
            QTableView, QHeaderView, QTableWidget,
            QStyledItemDelegate, QStyleOptionViewItem, QStyle,
            QGraphicsDropShadowEffect
        )

        header_css = """
            QHeaderView::section {
                background: qlineargradient(x1:0,y1:0, x2:0,y2:1,
                             stop:0 #f0f7ff, stop:1 #e6efff);
                color:#0f172a; font-weight:600; padding:10px 14px;
                border:1px solid #d9e1f2; border-top-left-radius:9px; border-top-right-radius:9px;
            }
            QHeaderView::section:horizontal:hover { background:#e7efff; }
            QHeaderView::up-arrow, QHeaderView::down-arrow { subcontrol-position:right; margin-right:6px; }
            QTableView {
                gridline-color: transparent; selection-background-color:#dbeafe;
                selection-color:#1e3a8a; background:#ffffff; border:none; border-radius:10px;
            }
            QTableCornerButton::section { background:#f0f7ff; border:1px solid #d9e1f2; border-top-left-radius:9px; }
        """

        for tv in self.findChildren(QTableView):
            hh: QHeaderView = tv.horizontalHeader()
            if hh:
                hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                hh.setHighlightSections(False)
                hh.setSectionsClickable(True)
                hh.setSortIndicatorShown(True)
                hh.setFixedHeight(38)
                hh.setMinimumSectionSize(52)

                f = QFont(tv.font());
                f.setPointSizeF(max(11.0, f.pointSizeF()) + 0.8)
                f.setWeight(QFont.Weight.DemiBold)
                hh.setFont(f)

            if tv.verticalHeader():
                tv.verticalHeader().setVisible(False)
                tv.verticalHeader().setDefaultSectionSize(46)

            tv.setMouseTracking(True)
            tv.setShowGrid(False)
            tv.setAlternatingRowColors(False)
            tv.setTextElideMode(Qt.TextElideMode.ElideRight)
            tv.setStyleSheet(header_css)

        # ---- SAĞ LİSTE: RENKLENDİR + BOŞLUK/PADDING DELEGATE ----
        t = getattr(self, "verilen", None)
        if not isinstance(t, QTableWidget) or t.columnCount() == 0:
            return

        KNOWN = {
            "fizik": "#E8F2FF", "kimya": "#FFF7C2", "biyoloji": "#E9FCEB",
            "geometri": "#EFE9FF", "matematik": "#F4E9FF",
            "tyt_matematik": "#F4E9FF", "ayt_matematik": "#F4E9FF",
            "türkçe": "#FFE7EA", "turkce": "#FFE7EA", "paragraf": "#FFE7EA", "edebiyat": "#FFE7EA",
            "tarih": "#FFF3E3", "coğrafya": "#FEFBE8", "cografya": "#FEFBE8",
            "felsefe": "#FAF5FF", "din": "#FAFAF9", "ingilizce": "#E6F4FF", "almanca": "#FEF2F2",
        }

        def _pastel_from_text(s: str) -> QColor:
            import hashlib
            key = (s or "").lower().strip()
            h = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16)
            return QColor.fromHsl(h % 360, 60, 240, 255)

        def _color_for_row(r: int) -> QColor:
            it = t.item(r, 0)
            name = (it.text() if it else "").lower()
            for k, hx in KNOWN.items():
                if name.startswith(k) or k in name:
                    return QColor(hx)
            return _pastel_from_text(name)

        def _colorize_rows():
            # [RANA: optimize] Toplu güncellemede flicker’ı azalt
            t.setUpdatesEnabled(False)
            try:
                for r in range(t.rowCount()):
                    col = _color_for_row(r)
                    for c in range(t.columnCount()):
                        it = t.item(r, c)
                        if it:
                            it.setBackground(col)
            finally:
                t.setUpdatesEnabled(True)
                t.viewport().update()

        SPACING_V = 6
        PAD_H = 14

        class _PadOnlyDelegate(QStyledItemDelegate):
            def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
                opt = QStyleOptionViewItem(option)
                self.initStyleOption(opt, index)
                r = QRect(opt.rect)
                r.adjust(PAD_H, 0, -PAD_H, -SPACING_V)
                opt.rect = r
                style = opt.widget.style() if opt.widget else t.style()
                style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

            def sizeHint(self, option, index) -> QSize:
                sz = super().sizeHint(option, index)
                return QSize(sz.width(), max(42, sz.height() + SPACING_V))

        if not hasattr(self, "_verilen_pad_delegate"):
            self._verilen_pad_delegate = _PadOnlyDelegate(t)
            t.setItemDelegate(self._verilen_pad_delegate)

        try:
            eff = QGraphicsDropShadowEffect(t)
            eff.setBlurRadius(24);
            eff.setOffset(0, 6);
            eff.setColor(QColor(0, 0, 0, 55))
            t.setGraphicsEffect(eff)
        except Exception:
            pass

        def _wire_once():
            if getattr(self, "_verilen_wired", False):
                return
            if t.model():
                t.model().rowsInserted.connect(lambda *a: _colorize_rows())
                t.model().rowsRemoved.connect(lambda *a: _colorize_rows())
                t.model().dataChanged.connect(lambda *a: _colorize_rows())
                t.model().layoutChanged.connect(lambda *a: _colorize_rows())
            t.itemChanged.connect(lambda *a: _colorize_rows())
            self._verilen_wired = True

        _wire_once()
        QTimer.singleShot(0, _colorize_rows)



    # --- SEKMEYİ KÜÇÜLT & MODERN GÖRÜNÜM UYGULA ---
    def _tabs_compact_apply(self):
        """Modern, ferah ve profesyonel sekme stili."""
        tb = self.tabs.tabBar()

        try:
            tb.setStyleSheet("")
            self.tabs.setStyleSheet("")
        except Exception:
            pass

        tb.setExpanding(False)
        tb.setElideMode(Qt.TextElideMode.ElideNone)

        f: QFont = tb.font()
        f.setPointSize(11)
        f.setBold(False)
        tb.setFont(f)

        self.tabs.setStyleSheet("""
            QTabBar {
                qproperty-drawBase: 0;
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 7px 14px;
                min-height: 26px;
                margin-right: 3px;
                margin-top: 3px;
                color: #475569;
                font-weight: 600;
                font-size: 11.5px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border: 1px solid #2563eb;
                border-top: 3px solid #2563eb;
                border-bottom: 2px solid #ffffff;
                color: #1d4ed8;
                font-weight: bold;
                margin-top: 0px;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
                color: #0f172a;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-top: 2px solid #2563eb;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
        """)

    def _on_quick_lesson_selected(self, idx: int):
        if idx >= 0 and idx < self.tabs.count():
            self.tabs.setCurrentIndex(idx)

    def _on_tab_changed_sync_combo(self, idx: int):
        if hasattr(self, "cmb_quick_lesson") and idx >= 0:
            self.cmb_quick_lesson.blockSignals(True)
            self.cmb_quick_lesson.setCurrentIndex(idx)
            self.cmb_quick_lesson.blockSignals(False)

    def _jump_to_category(self, cat: str):
        if not hasattr(self, "tabs") or self.tabs.count() == 0:
            return

        # Kategori butonlarının aktif/pasif stilleri
        active_style = """
            QPushButton {
                background: #2563eb; border: 1px solid #1d4ed8; border-radius: 13px;
                padding: 2px 12px; font-size: 11px; font-weight: bold; color: white;
            }
        """
        inactive_style = """
            QPushButton {
                background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 13px;
                padding: 2px 12px; font-size: 11px; font-weight: 600; color: #475569;
            }
            QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }
        """
        if hasattr(self, "btn_cat_all"):
            self.btn_cat_all.setStyleSheet(active_style if cat == "all" else inactive_style)
        if hasattr(self, "btn_cat_say"):
            self.btn_cat_say.setStyleSheet(active_style if cat == "say" else inactive_style)
        if hasattr(self, "btn_cat_soz"):
            self.btn_cat_soz.setStyleSheet(active_style if cat == "soz" else inactive_style)

        say_keywords = ["matematik", "geometri", "fizik", "kimya", "biyoloji", "fen"]
        soz_keywords = ["turkce", "türkçe", "paragraf", "tarih", "cografya", "coğrafya", "felsefe", "edebiyat", "din", "ingilizce", "inkilap"]

        first_visible = -1
        current_visible = False

        for i in range(self.tabs.count()):
            data = self.tabs.tabBar().tabData(i)
            key = (data.get("key") if isinstance(data, dict) else "").lower()
            text = (self.tabs.tabText(i) or "").lower()
            cat_type = LESSON_META.get(key, {}).get("cat", "")

            if cat == "all":
                visible = True
            elif cat == "say":
                visible = (cat_type == "Sayısal") or any(k in key or k in text for k in say_keywords)
            elif cat == "soz":
                visible = (cat_type in ("Sözel & EA", "Sözel", "Dil")) or any(k in key or k in text for k in soz_keywords)
            else:
                visible = True

            self.tabs.setTabVisible(i, visible)
            if visible:
                if first_visible == -1:
                    first_visible = i
                if i == self.tabs.currentIndex():
                    current_visible = True

        if not current_visible and first_visible >= 0:
            self.tabs.setCurrentIndex(first_visible)

        # Hızlı geçiş combosu ile senkronizasyon (sadece görünen sekmeler)
        if hasattr(self, "cmb_quick_lesson"):
            self.cmb_quick_lesson.blockSignals(True)
            self.cmb_quick_lesson.clear()
            for i in range(self.tabs.count()):
                if self.tabs.isTabVisible(i):
                    self.cmb_quick_lesson.addItem(self.tabs.tabText(i), i)
            curr_idx = self.tabs.currentIndex()
            c_pos = self.cmb_quick_lesson.findData(curr_idx)
            if c_pos >= 0:
                self.cmb_quick_lesson.setCurrentIndex(c_pos)
            self.cmb_quick_lesson.blockSignals(False)

    def _open_tab_reorder_dialog(self):
        if not hasattr(self, "tabs") or self.tabs.count() == 0:
            QMessageBox.information(self, "Bilgi", "Önce bir öğrenci seçip 'Getir' butonuna basarak dersleri yükleyin.")
            return

        lessons = []
        for i in range(self.tabs.count()):
            data = self.tabs.tabBar().tabData(i)
            if isinstance(data, dict) and "key" in data:
                lessons.append(data["key"])
            else:
                lessons.append(self.tabs.tabText(i))

        info = self._secili_ogrenci_info()
        dlg = DersSiralamaDialog(self, current_lessons=lessons, student_info=info)
        if dlg.exec():
            # Sıralamayı mevcut sekmelere uygula (öğrencinin derslerini yeniden getirir)
            self._bilgileri_getir()

    def _on_tab_drag_moved(self, from_idx: int, to_idx: int):
        try:
            current_order = []
            for i in range(self.tabs.count()):
                data = self.tabs.tabBar().tabData(i)
                if isinstance(data, dict) and "key" in data:
                    current_order.append(data["key"])
                else:
                    current_order.append(self.tabs.tabText(i))
            import json
            from utils.settings import ayar_set
            ayar_set("custom_lesson_tab_order", json.dumps(current_order))

            if hasattr(self, "cmb_quick_lesson"):
                self.cmb_quick_lesson.blockSignals(True)
                self.cmb_quick_lesson.clear()
                for ti in range(self.tabs.count()):
                    self.cmb_quick_lesson.addItem(self.tabs.tabText(ti), ti)
                self.cmb_quick_lesson.setCurrentIndex(self.tabs.currentIndex())
                self.cmb_quick_lesson.blockSignals(False)
        except Exception as e:
            print("tab drag move error:", e)

    def _apply_custom_tab_order(self, dersler: list[str], student_row=None) -> list[str]:
        try:
            import json
            from utils.settings import ayar_get

            info = {}
            if isinstance(student_row, dict) or hasattr(student_row, "__getitem__"):
                try:
                    info = dict(student_row)
                except Exception:
                    pass
            if not info:
                info = self._secili_ogrenci_info()

            ogr_id = info.get("id") or info.get("ogrenci_id")
            alt_grup = str(info.get("alt_grup") or "").strip().lower()
            ana_grup = str(info.get("ana_grup") or "").strip().lower()

            candidate_keys = []
            if ogr_id:
                candidate_keys.append(f"custom_tab_order_student_{ogr_id}")
            if alt_grup:
                candidate_keys.append(f"custom_tab_order_subgroup_{alt_grup}")
            if ana_grup:
                candidate_keys.append(f"custom_tab_order_maingroup_{ana_grup}")
            candidate_keys.append("custom_lesson_tab_order")

            raw = ""
            for k in candidate_keys:
                val = ayar_get(k, "")
                if val:
                    raw = val
                    break

            if raw:
                order = json.loads(raw)
                if isinstance(order, list) and order:
                    d_map = {d.strip().lower(): d for d in dersler}
                    ordered = []
                    for k in order:
                        clean_k = k.strip().lower()
                        if clean_k in d_map:
                            ordered.append(d_map.pop(clean_k))
                        else:
                            for key in list(d_map.keys()):
                                if key in clean_k or clean_k in key:
                                    ordered.append(d_map.pop(key))
                                    break
                    # Kalan dersler orijinal sırayla sona eklenir
                    for d in dersler:
                        if d.strip().lower() in d_map:
                            ordered.append(d)
                            d_map.pop(d.strip().lower())
                    return ordered
        except Exception as e:
            print("apply_custom_tab_order error:", e)
        return dersler


    def _oneri_refresh_safe(self):
        """Açıksa öneri panelini güvenli biçimde yeniler."""
        panel = getattr(self, "oneri", None)
        if panel and hasattr(panel, "_yenile_click"):
            try:
                QTimer.singleShot(0, panel._yenile_click)
            except Exception:
                pass

    def _open_oneri_dialog(self):
        from PyQt6.QtWidgets import (
            QDialog, QSplitter, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
            QLabel, QPushButton, QGroupBox, QSpinBox, QCheckBox, QComboBox,
            QSizePolicy
        )
        from PyQt6.QtCore import Qt

        try:
            if getattr(self, "_oneri_dlg", None):
                self._oneri_dlg.close()
        except Exception:
            pass

        dlg = QDialog(self)
        dlg.setWindowTitle("Öneriler")
        dlg.resize(720, 560)
        dlg.setSizeGripEnabled(True)
        dlg.setWindowOpacity(0.95)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        root = QHBoxLayout(dlg);
        root.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, dlg)
        splitter.setChildrenCollapsible(False);
        splitter.setHandleWidth(8)
        root.addWidget(splitter)

        # === SOL ===
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lv = QVBoxLayout(left);
        lv.setContentsMargins(16, 12, 12, 12);
        lv.setSpacing(8)
        lv.addWidget(QLabel("<b>Öneriler (son 30 gün)</b>"))

        panel = OneriPaneli(left)
        panel._host = self  # güvence

        # <<< ÖNEMLİ: panel referansını her iki adla da tut >>>
        self.oneri = panel
        self._oneri_panel = panel
        dlg.destroyed.connect(lambda *_: (setattr(self, "oneri", None),
                                          setattr(self, "_oneri_panel", None)))

        # Sadece listeyi full boy göster
        keep = getattr(panel, "liste", None)
        if keep is not None:
            for w in panel.findChildren(QWidget):
                if w is not keep and w.parent() is panel:
                    w.setVisible(False)
            keep.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            try:
                keep.setMinimumHeight(240)
                keep.setMaximumHeight(16777215)
            except Exception:
                pass
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lv.addWidget(panel, stretch=1)
        splitter.addWidget(left)

        # === SAĞ ===
        right = QWidget();
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 12, 12, 12);
        rv.setSpacing(12)

        box = QGroupBox("Ayarlar");
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(10);
        grid.setVerticalSpacing(8)

        lblZ = QLabel("Zorluk ≤");
        cmbZorluk = QComboBox()
        cmbZorluk.addItems([str(i) for i in range(1, 6)]);
        cmbZorluk.setFixedWidth(110)
        lblHP = QLabel("Hedef Paket (dk):");
        spHedef = QSpinBox()
        spHedef.setRange(0, 9999);
        spHedef.setValue(60);
        spHedef.setFixedWidth(110)
        lblTol = QLabel("±");
        spTol = QSpinBox()
        spTol.setRange(0, 240);
        spTol.setValue(10);
        spTol.setFixedWidth(110)
        chkCesit = QCheckBox("Aynı kitabı çeşitlendir")

        r = 0
        grid.addWidget(lblZ, r, 0);
        grid.addWidget(cmbZorluk, r, 1);
        r += 1
        grid.addWidget(lblHP, r, 0);
        grid.addWidget(spHedef, r, 1);
        r += 1
        grid.addWidget(lblTol, r, 0);
        grid.addWidget(spTol, r, 1);
        r += 1
        grid.addWidget(chkCesit, r, 0, 1, 2)
        rv.addWidget(box)

        def _btn(b: QPushButton):
            b.setFixedHeight(40)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.setMaximumWidth(260);
            b.setMinimumWidth(200)

        btnPaketle = QPushButton("Hedefe göre paketle");
        _btn(btnPaketle)
        btnYenile = QPushButton("Yenile");
        _btn(btnYenile)
        btnEksik = QPushButton("Eksik Konuları Getir");
        _btn(btnEksik)
        btnTakviye = QPushButton("Yaklaşan Bitişe Takviye");
        _btn(btnTakviye)
        btnEkle = QPushButton("Seçilenleri Ekle");
        _btn(btnEkle)
        btnKapat = QPushButton("Kapat");
        _btn(btnKapat)

        for b in (btnPaketle, btnYenile, btnEksik, btnTakviye):
            rv.addWidget(b, alignment=Qt.AlignmentFlag.AlignRight)
        rv.addStretch(1)
        rv.addWidget(btnEkle, alignment=Qt.AlignmentFlag.AlignRight)
        rv.addWidget(btnKapat, alignment=Qt.AlignmentFlag.AlignRight)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4);
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([680, 320])

        # Senkronizasyon
        if hasattr(panel, "cmbZorluk"):      cmbZorluk.setCurrentIndex(panel.cmbZorluk.currentIndex())
        if hasattr(panel, "spPaket"):        spHedef.setValue(panel.spPaket.value())
        if hasattr(panel, "spTol"):          spTol.setValue(panel.spTol.value())
        if hasattr(panel, "chkCesitlendir"): chkCesit.setChecked(panel.chkCesitlendir.isChecked())

        if hasattr(panel, "cmbZorluk"):      cmbZorluk.currentIndexChanged.connect(panel.cmbZorluk.setCurrentIndex)
        if hasattr(panel, "spPaket"):        spHedef.valueChanged.connect(panel.spPaket.setValue)
        if hasattr(panel, "spTol"):          spTol.valueChanged.connect(panel.spTol.setValue)
        if hasattr(panel, "chkCesitlendir"): chkCesit.toggled.connect(panel.chkCesitlendir.setChecked)

        if hasattr(panel, "btnPaket"):       btnPaketle.clicked.connect(panel.btnPaket.click)
        if hasattr(panel, "btnYenile"):      btnYenile.clicked.connect(panel.btnYenile.click)
        if hasattr(panel, "btnEkle"):        btnEkle.clicked.connect(panel.btnEkle.click)

        btnEksik.clicked.connect(self._akilli_eksik_konular)
        btnTakviye.clicked.connect(self._akilli_takviye)
        btnKapat.clicked.connect(dlg.close)

        self._oneri_dlg = dlg
        dlg.destroyed.connect(lambda *_: setattr(self, "_oneri_dlg", None))
        dlg.show()

        # açılışta bir kez yenile
        try:
            panel._yenile_click()
        except Exception:
            pass

    # ========== ÖNERİ PANEL YARDIMCILARI ==========

    def _active_oneri_panel(self):
        """Açık bir OneriPaneli varsa döndür, yoksa None."""
        p = getattr(self, "_oneri_panel", None) or getattr(self, "oneri", None)
        try:
            return p if (p and p.isVisible()) else None
        except Exception:
            return None

    def _oneri_set_items(self, items, title: str = "Öneriler", info_text: str | None = None):
        """
        ÖneriPaneli'ne güvenli liste bas:
        - Diyalog yoksa açar, varsa öne getirir.
        - self.oneri.set_items(...) çağrısını yapar.
        - info_text varsa Öneriler penceresinde kısa 'toast' gösterir (bloklamaz).
        """
        # 1) pencereyi hazırla/öne getir
        self._show_oneri_dialog()

        # 2) listeyi bas
        panel = getattr(self, "oneri", None) or getattr(self, "_oneri_panel", None)
        if panel is not None and hasattr(panel, "set_items"):
            try:
                panel.set_items(items or [])
            except Exception:
                pass

        # 3) başlık ve bilgi
        dlg = getattr(self, "_oneri_dlg", None)
        if dlg is not None:
            try:
                dlg.setWindowTitle(title)
            except Exception:
                pass
            if info_text:
                self._toast(info_text, parent=dlg, msec=1800)

    # --- Öneriler diyalogunu aç/öne getir (yeniden yaratma yok) ---
    def _show_oneri_dialog(self):
        """Öneriler diyalogunu güvenle açar ya da öne getirir."""
        try:
            if getattr(self, "_oneri_dlg", None) is None:
                self._open_oneri_dialog()  # ilk kez oluştur
            else:
                self._oneri_dlg.show()
                self._oneri_dlg.raise_()
                self._oneri_dlg.activateWindow()
        except Exception:
            try:
                self._open_oneri_dialog()
            except Exception:
                pass

    # --- Hafif "toast" (pencere içinde 1,6 sn görünen etiket) ---
    def _toast(self, mesaj, parent=None, msec=1600, under_widget=None):
        """
        Bloklamayan kısa bildirim (fade-in/fade-out).
        under_widget verilirse mesaj o widget'ın altına hizalanır.
        """
        from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
        from PyQt6.QtCore import QTimer, Qt, QPropertyAnimation, QRect

        if parent is None:
            parent = self

        lbl = QLabel(str(mesaj or ""), parent)
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 210);
                color: white;
                padding: 8px 14px;
                border-radius: 10px;
                font-size: 13px;
                letter-spacing: .2px;
            }
        """)

        max_w = int(parent.width() * 0.8)
        lbl.setMaximumWidth(max_w)
        lbl.adjustSize()
        w = lbl.width()
        h = lbl.height()

        if under_widget:
            g = under_widget.geometry()
            x = g.left() + (g.width() - w) // 2
            y = g.bottom() + 12
        else:
            pr: QRect = parent.rect()
            x = pr.center().x() - w // 2
            y = pr.center().y()

        x = max(8, min(x, parent.width() - w - 8))
        y = max(8, min(y, parent.height() - h - 8))

        lbl.move(int(x), int(y))
        lbl.raise_()

        eff = QGraphicsOpacityEffect(lbl)
        eff.setOpacity(0.0)
        lbl.setGraphicsEffect(eff)
        lbl.show()

        anim_in = QPropertyAnimation(eff, b"opacity", self)
        anim_in.setDuration(250)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)

        if not hasattr(self, "_live_anims"):
            self._live_anims = []
        self._live_anims.append(anim_in)
        anim_in.start()

        QTimer.singleShot(msec, lambda: self._fade_out(lbl, msec=600, remove=True))

    def _fade_out(self, lbl, msec=700, remove=True):
        """PyQt6 için güvenli fade-out animasyonu."""
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

        try:
            if not lbl or not hasattr(lbl, "setGraphicsEffect"):
                return
            if getattr(lbl, "_fading_now", False):
                return
            lbl._fading_now = True

            eff = lbl.graphicsEffect()
            if eff is None or not isinstance(eff, QGraphicsOpacityEffect):
                eff = QGraphicsOpacityEffect(lbl)
                lbl.setGraphicsEffect(eff)
            eff.setOpacity(1.0)

            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(max(1, int(msec)))
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

            def _finish():
                try:
                    if remove and hasattr(lbl, "hide"):
                        lbl.hide()
                        lbl.deleteLater()
                    else:
                        eff.setOpacity(1.0)
                except Exception:
                    pass
                finally:
                    if hasattr(lbl, "_fading_now"):
                        delattr(lbl, "_fading_now")
                    if hasattr(self, "_live_anims") and anim in self._live_anims:
                        self._live_anims.remove(anim)
            anim.finished.connect(_finish)
            if not hasattr(self, "_live_anims"):
                self._live_anims = []
            self._live_anims.append(anim)
            anim.start()
        except (RuntimeError, AttributeError) as e:
            # Widget silinmiş olabilir
            pass

    # --- Öneri dialog yönetimi (panel + dlg döndürür) --------------------------
    def _ensure_oneri_dialog(self, raise_only: bool = True):
        """
        Öneri diyalogunu ve panelini garanti altına alır.
        Yoksa açar; varsa öne getirir. (panel, dlg) döndürür.
        """
        dlg = getattr(self, "_oneri_dlg", None)
        panel = getattr(self, "oneri", None)

        need_create = (
                dlg is None or panel is None or
                not hasattr(panel, "set_items") or
                (hasattr(dlg, "isVisible") and not dlg.isVisible())
        )
        if need_create:
            self._open_oneri_dialog()
            dlg = getattr(self, "_oneri_dlg", None)
            panel = getattr(self, "oneri", None)

        if raise_only and dlg is not None:
            try:
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                pass

        return panel, dlg

    def _notify(self, title: str, text: str) -> None:
        """Bilgi mesajını non-modal göster; öneri diyalogunu asla kapatmaz."""
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import Qt
        mb = QMessageBox(self)  # ebeveyn: ANA FORM
        mb.setIcon(QMessageBox.Icon.Information)
        mb.setWindowTitle(title or "Bilgi")
        mb.setText(text or "")
        mb.setStandardButtons(QMessageBox.StandardButton.Ok)
        mb.setWindowModality(Qt.WindowModality.NonModal)
        mb.show()

    def _gridde_zaten_isaretli(self, ders: str, kitap: str, konu: str) -> bool:
        """Sol gridde bu (ders/kitap/konu) şu an işaretli mi?"""
        try:
            t, r, c = self._hucre_bul(ders, kitap, konu)
            it = t.item(r, c) if t is not None else None
            from PyQt6.QtCore import Qt
            return bool(it and it.checkState() == Qt.CheckState.Checked)
        except Exception:
            return False

    # ---------------------------------------------------------------------------

    def _current_oneri_panel(self):
        """
        Açık bir Öneriler diyalogu varsa onu döndür (self._oneri_panel),
        yoksa ana form üzerindeki self.oneri varsa onu döndür, yoksa None.
        """
        pnl = getattr(self, "_oneri_panel", None)
        if pnl is not None:
            try:
                if pnl.isVisible():
                    return pnl
            except Exception:
                pass
        return getattr(self, "oneri", None)

    def _push_oneri(self, items, info_text: str | None = None):
        """
        Üretilen öneri listesini aktif panele basar.
        Panel yoksa sessizce geçer (akışı bozmaz).
        """
        panel = self._current_oneri_panel()
        try:
            if panel and hasattr(panel, "set_items"):
                panel.set_items(items or [])
                if info_text:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.information(self, "Öneriler", info_text.format(n=len(items or [])))
        except Exception:
            pass

    def _with_oneri_target(self, panel, fn):
        """
        fn() çağrısı boyunca self.oneri'yi geçici olarak panel'e yönlendir.
        İş biter bitmez eski hedef geri yüklenir.
        """
        old = getattr(self, "oneri", None)
        try:
            self.oneri = panel
            return fn()
        finally:
            self.oneri = old

    def _ensure_oneri_dialog_open(self):
        """
        Öneri diyalogunu açık değilse aç, panel'i döndür.
        self._oneri_dlg ve self._oneri_panel referanslarını güncel tutar.
        """
        try:
            if getattr(self, "_oneri_dlg", None) and self._oneri_dlg.isVisible():
                return getattr(self, "_oneri_panel", None)
        except Exception:
            pass

        self._open_oneri_dialog()
        try:
            if getattr(self, "_oneri_dlg", None):
                self._oneri_dlg.show()
                self._oneri_dlg.raise_()
                self._oneri_dlg.activateWindow()
        except Exception:
            pass

        return getattr(self, "_oneri_panel", None)

    def _tabs_split_long_titles(self, max_len: int = 15):
        """
        Uzun başlıkları böler. Rozet varsa bozulmaması için dikkat eder.
        """
        import re
        for i in range(self.tabs.count()):
            t = self.tabs.tabText(i) or ""
            
            # Eğer zaten new line varsa dokunma
            if "\n" in t:
                continue
                
            # Rozet kontrolü
            if "🔴" in t or "🟡" in t:
                # Rozetli başlıkları bölmeyelim, tek satır kalsın (güvenli mod)
                # Veya çok uzunsa sadece metin kısmını bölebiliriz ama şimdilik risk almayalım.
                continue

            # Normal Başlık (Rozetsiz)
            if len(t) > max_len and " " in t:
                parts = t.split(" ")
                if len(parts) >= 3 and len(parts[0]) <= 2: # emoji önde
                    left = f"{parts[0]} {parts[1]}"
                    right = " ".join(parts[2:])
                    self.tabs.setTabText(i, f"{left}\n{right}")

    # ---------------- Öğrenci & Sekmeler ----------------

    def _ogrencileri_yukle(self):
        rows = self._ogrenci_listesi()
        self._ogr_all = [dict(r) if not isinstance(r, dict) else r for r in (rows or [])]
        self._apply_ogrenci_filter()
        if getattr(self, "_pending_student_id", None) is not None:
            from PyQt6.QtCore import QTimer
            oid = int(self._pending_student_id)
            QTimer.singleShot(0, lambda: self.select_student_by_id(oid, autoload=False))

    def _apply_ogrenci_filter(self):
        from PyQt6.QtWidgets import QComboBox
        adq = (self.txtAraAd.text() or "").strip().lower()
        soyq = (self.txtAraSoyad.text() or "").strip().lower()

        sel_id = self._secili_ogrenci_id()

        flist = []
        for r in (self._ogr_all or []):
            ad = (self._row_get(r, "ad", "") or "").lower()
            soyad = (self._row_get(r, "soyad", "") or "").lower()
            if adq and adq not in ad:
                continue
            if soyq and soyq not in soyad:
                continue
            flist.append(r)

        w1 = self.cmbAd.blockSignals(True)
        w2 = self.cmbSoyad.blockSignals(True)
        try:
            self.cmbAd.clear()
            self.cmbSoyad.clear()
            for r in flist:
                rid = int(self._row_get(r, "id", 0) or 0)
                ad = self._row_get(r, "ad", "")
                soyad = self._row_get(r, "soyad", "")
                self.cmbAd.addItem(ad, rid)
                self.cmbSoyad.addItem(soyad, rid)

            idx = -1
            if sel_id is not None:
                for i in range(self.cmbAd.count()):
                    if self.cmbAd.itemData(i) == sel_id:
                        idx = i
                        break
            if idx < 0 and self.cmbAd.count() > 0:
                idx = 0
            if idx >= 0:
                self.cmbAd.setCurrentIndex(idx)
                self.cmbSoyad.setCurrentIndex(idx)
        finally:
            self.cmbAd.blockSignals(w1)
            self.cmbSoyad.blockSignals(w2)

        self._auto_width_combo(self.cmbAd)
        self._auto_width_combo(self.cmbSoyad)

    def _auto_width_combo(self, cmb, max_w: int = 520):
        """
        Combobox ve popup'ını, en uzun metne göre genişletir.
        max_w: pencereyi taşırmamak için üst sınır.
        """
        try:
            fm = cmb.fontMetrics()
            max_text_w = 0
            for i in range(cmb.count()):
                txt = cmb.itemText(i) or ""
                w = fm.horizontalAdvance(txt)
                max_text_w = max(max_text_w, w)

            box_w = min(max_text_w + 40, max_w)
            cmb.setSizeAdjustPolicy(cmb.SizeAdjustPolicy.AdjustToContents)
            cmb.setMinimumContentsLength(0)
            cmb.setMinimumWidth(box_w)

            try:
                view = cmb.view()  # QListView
                view.setMinimumWidth(max_text_w + 60)
            except Exception:
                pass
        except Exception:
            pass

    def _row_get(self, row, key, default=""):
        """sqlite3.Row / dict fark etmeksizin güvenli okuma."""
        try:
            v = row[key]
            return v if v is not None else default
        except Exception:
            try:
                return row.get(key, default)
            except Exception:
                return default

    def _ad_degisti(self, idx):
        from PyQt6.QtCore import QTimer
        if 0 <= idx < self.cmbSoyad.count():
            was = self.cmbSoyad.blockSignals(True)
            self.cmbSoyad.setCurrentIndex(idx)
            self.cmbSoyad.blockSignals(was)
        QTimer.singleShot(0, lambda: getattr(self.oneri, "_yenile_click", lambda: None)())

    def _soyad_degisti(self, idx):
        from PyQt6.QtCore import QTimer
        if 0 <= idx < self.cmbAd.count():
            was = self.cmbAd.blockSignals(True)
            self.cmbAd.setCurrentIndex(idx)
            self.cmbAd.blockSignals(was)
        QTimer.singleShot(0, lambda: getattr(self.oneri, "_yenile_click", lambda: None)())

    #s--
    '''
    Kullanıcı combobox’tan öğrenciyi seçtiği anda
    Bilgileri Getir butonuna basmasına gerek kalmadan
    _bilgileri_getir() otomatik çalışsın.

    '''
    def _update_student_snapshot(self):
        try:
            oid = self._secili_ogrenci_id()
            if not oid:
                self.lbl_snap_target.setText("🎯 Hedef: —")
                self.lbl_snap_total.setText("📋 Toplam: 0")
                self.lbl_snap_pending.setText("⏳ Bekleyen: 0")
                self.lbl_snap_done.setText("✅ Biten: 0 (%0)")
                self.lbl_snap_countdown.setText("⏰ —")
                return

            import db
            con = db.get_conn()
            try:
                stu = con.execute("SELECT ana_grup, alt_grup, hedef_bolum FROM ogrenci WHERE id=?", (oid,)).fetchone()
                rows = con.execute("SELECT durum FROM odev WHERE ogrenci_id=? AND silindi=0", (oid,)).fetchall()
            finally:
                con.close()

            # Hedef / Alan
            grp = ""
            if stu:
                grp = stu["hedef_bolum"] or f"{stu['ana_grup'] or ''} {stu['alt_grup'] or ''}".strip()
            self.lbl_snap_target.setText(f"🎯 {grp or 'Hedef Belirtilmedi'}")

            # İstatistikler
            total = len(rows)
            done_words = {"yapıldı", "yapildi", "tamam", "bitti", "done", "ok", "1"}
            done_cnt = sum(1 for r in rows if (r["durum"] or "").strip().lower() in done_words)
            pending_cnt = total - done_cnt
            pct = int((done_cnt / total * 100)) if total > 0 else 0

            self.lbl_snap_total.setText(f"📋 Toplam: {total}")
            self.lbl_snap_pending.setText(f"⏳ Bekleyen: {pending_cnt}")
            self.lbl_snap_done.setText(f"✅ Biten: {done_cnt} (%{pct})")

            # Kalan gün
            bitis_qdate = self.dtpBitis.date()
            today = QDate.currentDate()
            diff = today.daysTo(bitis_qdate)
            if diff < 0:
                self.lbl_snap_countdown.setText(f"⚠️ {abs(diff)} Gün Gecikmiş!")
                self.lbl_snap_countdown.setStyleSheet("font-size: 11px; font-weight: 800; color: #dc2626; background: #fee2e2; padding: 2px 8px; border-radius: 5px;")
            elif diff == 0:
                self.lbl_snap_countdown.setText("🚨 Bugün Teslim!")
                self.lbl_snap_countdown.setStyleSheet("font-size: 11px; font-weight: 800; color: #b45309; background: #fef3c7; padding: 2px 8px; border-radius: 5px;")
            else:
                self.lbl_snap_countdown.setText(f"⏰ {diff} Gün Kaldı")
                self.lbl_snap_countdown.setStyleSheet("font-size: 11px; font-weight: 800; color: #2563eb; background: #e0e7ff; padding: 2px 8px; border-radius: 5px;")
        except Exception:
            pass

    def _ogrenci_degisti_combo_ile(self):
        """
        Combobox'tan öğrenci seçildiğinde:
        - Öneri panelini yenile
        - Seçili öğrencinin tüm bilgilerini otomatik yükle
        - Üst bar durum özet kartını güncelle
        """
        # Öneri paneli
        try:
            getattr(self.oneri, "_yenile_click", lambda: None)()
        except Exception:
            pass

        # Öğrenci bilgilerini yükle
        try:
            self._bilgileri_getir()
        except Exception:
            pass

        # Akıllı özet kartını güncelle
        try:
            self._update_student_snapshot()
        except Exception:
            pass

    def _ad_degisti(self, idx):
        from PyQt6.QtCore import QTimer
        if 0 <= idx < self.cmbSoyad.count():
            was = self.cmbSoyad.blockSignals(True)
            self.cmbSoyad.setCurrentIndex(idx)
            self.cmbSoyad.blockSignals(was)
        # Öğrenci seçimi değişti → otomatik yükle
        QTimer.singleShot(0, self._ogrenci_degisti_combo_ile)

    def _soyad_degisti(self, idx):
        from PyQt6.QtCore import QTimer
        if 0 <= idx < self.cmbAd.count():
            was = self.cmbAd.blockSignals(True)
            self.cmbAd.setCurrentIndex(idx)
            self.cmbAd.blockSignals(was)
        # Öğrenci seçimi değişti → otomatik yükle
        QTimer.singleShot(0, self._ogrenci_degisti_combo_ile)


    #f--


    def _bilgileri_getir(self):
        """
        Seçili öğrenci için sekmeleri/tabloları yeniler.
        Progress penceresi: siyah arka plan, beyaz yazı, 500x220, word-wrap.
        UI pompalama: ~220ms'de bir (daha az redraw = daha hızlı hissiyat).
        """
        from PyQt6.QtWidgets import QMessageBox, QApplication
        from PyQt6.QtCore import QTimer, QElapsedTimer

        # --- Progress sınıfını getir ---
        try:
            from ui.progress import IlerlemePenceresi
        except ImportError:
            # Fallback (eğer ui paketi olarak değilse)
            from progress import IlerlemePenceresi

        # --- UI pompalamayı sınırlı yap (hız korunur) ---
        timer = QElapsedTimer();
        timer.start()
        PUMP_MS = 220  # <— 0.22 sn’de bir processEvents (daha hızlı hissedilir)

        def _pump(force=False):
            if force or timer.elapsed() >= PUMP_MS:
                try:
                    QApplication.processEvents()
                finally:
                    timer.restart()

        # --- Progress oluştur ---
        # Artık stil ve pencere yapısı ui/progress.py içinden geliyor.
        # Burada manuel müdahale yapmıyoruz.
        dlg = IlerlemePenceresi("Öğrenci Bilgileri Yükleniyor", self)
        dlg.show()
        _pump(force=True)
        _pump(True)

        # --- Normal akış ---
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            dlg.close()
            QMessageBox.warning(self, "Eksik", "Öğrenci seçiniz.")
            return

        # 1) DB'den çek
        try:
            import db
            con = db.get_conn()
            dlg.guncelle(6, "Seçili öğrenci için temel veriler veritabanından okunuyor, lütfen bekleyiniz…");
            _pump()
            row = con.execute("SELECT * FROM ogrenci WHERE id=?", (ogr_id,)).fetchone()
        except Exception as e:
            dlg.close()
            QMessageBox.critical(self, "Hata", f"Veritabanı hatası: {e}")
            return

        if not row:
            dlg.close()
            QMessageBox.warning(self, "Bulunamadı", "Öğrenci kaydı yok.")
            return

        # 2) Grup/Dersleri hazırla
        try:
            if hasattr(db, 'get_student_curriculum'):
                # Yeni dinamik sistem (Alt gruplara göre)
                dersler = db.get_student_curriculum(ogr_id)
            else:
                ana = (row.get("ana_grup") if hasattr(row, "get") else row["ana_grup"]) or "YKS"
                dersler = GRUP_DERSLER.get(ana, [])
        except Exception:
            # Fallback
            ana = (row.get("ana_grup") if hasattr(row, "get") else row["ana_grup"]) or "YKS"
            dersler = GRUP_DERSLER.get(ana, [])

        # Kullanıcının kaydettiği özel sekme sırasını uygula
        dersler = self._apply_custom_tab_order(dersler, row)

        dlg.guncelle(12, "Mevcut sekmeler temizleniyor ve yeni ders sekmeleri için alan hazırlanıyor…");
        _pump()
        try:
            self._ders_tablolari.clear()
        except Exception:
            self._ders_tablolari = {}
        while self.tabs.count():
            self.tabs.removeTab(0);
            _pump()

        # 3) Sekmeleri oluştur
        base_after_clear = 16
        loop_budget = 60
        step = loop_budget // max(1, len(dersler)) if dersler else loop_budget
        current = base_after_clear

        for i, ders in enumerate(dersler, start=1):
            dlg.guncelle(current,
                         f"{i}/{len(dersler)} – “{ders}” sekmesi oluşturuluyor, tablo bileşenleri hazırlanıyor ve görsel ayarlar uygulanıyor…"
                         );
            _pump()
            try:
                w, tablo = self._ders_tab_olustur(ogr_id, ders)
                meta = LESSON_META.get(ders.strip().lower(), {})
                icon = meta.get("icon", "📘")
                clean_title = meta.get("title", ders.replace('_', ' ').title())
                baslik = f"{icon} {clean_title}"
                idx = self.tabs.addTab(w, baslik)
                self.tabs.setTabToolTip(idx, f"{clean_title} Dersi Konu ve Kitap Matrisi")
                self._ders_tablolari[ders] = tablo
                try:
                    bar = self.tabs.tabBar()
                    bar.setTabData(idx, {"base": baslik, "key": ders.strip().lower()})
                except Exception:
                    pass
            except Exception as e:
                print("Sekme oluşturma hatası:", ders, e)

            current = min(base_after_clear + i * step, base_after_clear + loop_budget - 2)
            dlg.guncelle(current, f"{i}/{len(dersler)} – “{ders}” sekmesi hazır.");
            _pump()

        # Hızlı ders seçici kutusunu doldur
        if hasattr(self, "cmb_quick_lesson"):
            self.cmb_quick_lesson.blockSignals(True)
            self.cmb_quick_lesson.clear()
            for ti in range(self.tabs.count()):
                self.cmb_quick_lesson.addItem(self.tabs.tabText(ti), ti)
            self.cmb_quick_lesson.blockSignals(False)

        # 4) Başlık düzenlemeleri
        dlg.guncelle(80, "Sekme başlıkları sıkılaştırılıyor ve uzun başlıklar akıllı biçimde bölünüyor…");
        _pump()
        try:
            self._tabs_compact_apply()
            self._tabs_split_long_titles()
        except Exception:
            pass

        # 5) Özet, süre, görsel cilalar
        dlg.guncelle(84, "Özet tabloları sıfırlanıyor ve toplam süre hesapları yenileniyor…");
        _pump()
        try:
            self._verilen_rows.clear()
        except Exception:
            pass
        self.verilen.setRowCount(0)
        try:
            self._toplam_sure_guncelle()
        except Exception:
            pass

        dlg.guncelle(88, "Öneriler ve görünüm iyileştirmeleri uygulanıyor, gecikmiş ödevler kontrol ediliyor…");
        _pump()
        try:
            self.oneri._yenile_click()
        except Exception:
            pass
        try:
            self._mark_overdue_cells(ogr_id)
        except Exception as e:
            print("Gecikmiş ödev kontrolü başarısız:", e)
        try:
            self._apply_global_done_for_current()
        except Exception:
            pass
        try:
            QTimer.singleShot(0, getattr(self, "_polish_left_tables", lambda: None))
            QTimer.singleShot(0, getattr(self, "_apply_tables_visuals", lambda: None))
        except Exception:
            try:
                self._polish_left_tables()
            except Exception:
                pass
            try:
                self._apply_tables_visuals()
            except Exception:
                pass

        # 6) Rozetler ve ince ayar
        dlg.guncelle(93, "Rozet/rozetler ve gecikme işaretleri güncelleniyor…");
        _pump()
        try:
            self._update_overdue_badges(ogr_id)
        except Exception:
            pass

        dlg.guncelle(96, "Son görsel ince ayarlar uygulanıyor…");
        _pump()
        try:
            # apply_simple_tuning_to_left_tables(self)
            pass
        except Exception as e:
            print("Table tuning error:", e)

        # Bitti
        dlg.guncelle(100, "Öğrenci bilgileri yüklendi. İyi çalışmalar! ✅");
        _pump(True)
        try:
            self._update_student_snapshot()
        except Exception:
            pass

        dlg.close()




    def _debug_check_kolon(self, tablo, kol=1):
        """İlk 5 satırda checkable mı ve CheckState ne – debug amaçlı."""
        from PyQt6.QtCore import Qt
        m = tablo.model()
        for r in range(min(5, m.rowCount())):
            idx = m.index(r, kol)
            print(r, bool(idx.flags() & Qt.ItemFlag.ItemIsUserCheckable),
                  m.data(idx, Qt.ItemDataRole.CheckStateRole))


    # tablo_tiklama yani hızlı tıklama ve hover için.iyi çalışıyor

    def _ders_tab_olustur(self, ogr_id: int, ders: str):
        """Zebra korunur + ince grid + hızlı toggle + hover çerçeveleri."""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
            QAbstractItemView, QStyledItemDelegate, QHeaderView
        )
        from PyQt6.QtGui import QColor, QPen, QPainterPath, QPainter, QBrush
        from PyQt6.QtCore import Qt, QEvent, QRect, QRectF, QPointF, QObject
        from PyQt6 import QtCore

        # ---- görsel parametreler ----
        GAP_X, GAP_Y = 6, 6  # hücre içi mini boşluk (gap)
        LOCKED_COLORS = {"#A5D6A7", "#FFF59D"}  # yeşil/sarı kilitli hücreler

        # ---- veri ----
        con = db.get_conn()
        konular = db.ders_konularini_cek(con, ders)
        kitaplar = [r["kitap_ad"] for r in db.ogrenci_kitaplarini_cek(con, ogr_id, ders)]

        # ---- tablo ----
        table = QTableWidget(len(konular), 1 + len(kitaplar))
        table.setHorizontalHeaderLabels(["Konu"] + kitaplar)
        table.setAlternatingRowColors(True)  # zebra
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.viewport().setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, True)
        table.setMouseTracking(True)
        table.viewport().setMouseTracking(True)
        table.setShowGrid(True)  # ince grid çizgileri

        # tema–duyarlı ince grid ve başlık çizgileri (uygulamanın kendi temasını esas alır)
        is_dark = False
        try:
            if appset:
                tema = (appset.ayar_get("tema", None) or appset.ayar_get("tema_mod", "açık") or "açık").lower()
                is_dark = tema in ("koyu", "dark")
        except Exception:
            is_dark = False

        grid_clr = "#334155" if is_dark else "#e2e8f0"  # koyu/açık
        hdr_bg = "#1e293b" if is_dark else "#f1f5f9"
        hdr_fg = "#f8fafc" if is_dark else "#0f172a"
        hdr_bd = "#334155" if is_dark else "#cbd5e1"
        hov_bg = "rgba(148, 163, 184, 0.15)" if is_dark else "rgba(2, 132, 199, 0.08)"

        table.setStyleSheet(f"""
            QTableWidget, QTableView {{
                gridline-color: {grid_clr};
                border: none;
            }}
            QTableWidget::item:hover, QTableView::item:hover {{
                background: {hov_bg};                /* zebra üstüne hafif hover */
            }}
            QHeaderView::section {{
                background: {hdr_bg};
                color: {hdr_fg};
                font-weight: 600;
                padding: 6px;
                border: 1px solid {hdr_bd};
            }}
        """)

        # ---- satırları doldur ----
        # ---- satırları doldur ----
        try:
            table.setUpdatesEnabled(False)
            table.setSortingEnabled(False)
            
            for i, k in enumerate(konular):
                it = QTableWidgetItem(k["konu"])
                it.setData(Qt.ItemDataRole.UserRole, int(k["id"]))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setItem(i, 0, it)
    
                for c in range(1, table.columnCount()):
                    chk = QTableWidgetItem()
                    flags = chk.flags()
                    flags |= (Qt.ItemFlag.ItemIsUserCheckable |
                              Qt.ItemFlag.ItemIsEnabled |
                              Qt.ItemFlag.ItemIsSelectable)
                    flags &= ~Qt.ItemFlag.ItemIsEditable
                    chk.setFlags(flags)
                    chk.setCheckState(Qt.CheckState.Unchecked)
                    table.setItem(i, c, chk)
    
            # ---- mevcut durum: kilitle/renk ----
            rows = con.execute(
                "SELECT ders, konu_id, kitap_ad, durum FROM odev WHERE ogrenci_id=?",
                (ogr_id,)
            ).fetchall()
            durum_map = {(r["ders"], int(r["konu_id"]), r["kitap_ad"]): r["durum"] for r in rows}
    
            for i in range(table.rowCount()):
                konu_id = int(table.item(i, 0).data(Qt.ItemDataRole.UserRole))
                for c in range(1, table.columnCount()):
                    kitap_ad = table.horizontalHeaderItem(c).text()
                    key = (ders, konu_id, kitap_ad)
                    if key in durum_map:
                        d = durum_map[key]
                        it = table.item(i, c)
                        if d == "devam":
                            it.setCheckState(Qt.CheckState.Checked)
                            self._kilitle_ve_boya(table, i, c, QColor("#FFF59D"), True)  # sarı
                        elif d in ("yapildi", "tamam"):
                            it.setCheckState(Qt.CheckState.Checked)
                            self._kilitle_ve_boya(table, i, c, QColor("#A5D6A7"), True)  # yeşil
        finally:
            table.setUpdatesEnabled(True)
            # Matrix tablolarında sorting genelde istenmez ama gerekirse açılabilir

        # ---- itemChanged mikro-kuyruk (akıcı) ----
        if not hasattr(self, "_ic_queue"):
            self._ic_queue = []
        if not hasattr(self, "_ic_timer"):
            self._ic_timer = QtCore.QTimer(self)
            self._ic_timer.setSingleShot(True)
            self._ic_timer.setInterval(10)

            def _ic_flush():
                batch = self._ic_queue[:]
                self._ic_queue.clear()
                try:
                    sort_on = table.isSortingEnabled()
                    table.setSortingEnabled(False)
                    table.setUpdatesEnabled(False)
                    for it, t, d in batch:
                        try:
                            self._tik_degisti(it, t, d)
                        except Exception:
                            pass
                finally:
                    try:
                        table.setUpdatesEnabled(True)
                    except Exception:
                        pass
                    try:
                        table.setSortingEnabled(sort_on)
                    except Exception:
                        pass
            
            self._ic_timer.timeout.connect(_ic_flush)

        try:
            table.itemChanged.disconnect()
        except Exception:
            pass

        def _ic_proxy(it):
            self._ic_queue.append((it, table, ders))
            self._ic_timer.start()

        table.itemChanged.connect(_ic_proxy)

        # ---- delegate’ler: gap + toggle + flash ----

        # ---- delegate’ler: gap + toggle + flash ----
        def _is_locked_index(index) -> bool:
            # 1) Flag kontrolü (En kesin yöntem)
            # Eğer ItemIsUserCheckable flag'i yoksa, kilitlidir.
            if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                return True

            # 2) Renk kontrolü (Yedek)
            try:
                b = index.data(Qt.ItemDataRole.BackgroundRole)
                if b and hasattr(b, "color"):
                    return b.color().name().lower() in {c.lower() for c in LOCKED_COLORS}
            except Exception:
                pass
            return False
            return False

        class _BaseGap(QStyledItemDelegate):
            def paint(self, painter, option, index):
                inner = option.rect.adjusted(GAP_X // 2, GAP_Y // 2, -GAP_X // 2, -GAP_Y // 2)
                opt = option.__class__(option);
                opt.rect = inner
                super().paint(painter, opt, index)



        class _Toggle(_BaseGap):
            def __init__(self, on_toggled=None, parent=None):
                super().__init__(parent);
                self._on_toggled = on_toggled

            def paint(self, painter, option, index):
                check_state = index.data(Qt.ItemDataRole.CheckStateRole)
                txt = index.data(Qt.ItemDataRole.DisplayRole)
                txt_str = str(txt).strip() if (txt is not None) else ""

                # Eğer onay kutusu rolü yoksa ve sadece metin varsa standart boyamaya devret
                if check_state is None and txt_str:
                    super().paint(painter, option, index)
                    return

                # Gap için rect küçültmesi (BaseGap mantığı)
                inner = option.rect.adjusted(GAP_X // 2, GAP_Y // 2, -GAP_X // 2, -GAP_Y // 2)

                opt = QStyleOptionViewItem(option)
                opt.rect = inner
                super().initStyleOption(opt, index)
                opt.state &= ~QStyle.StateFlag.State_HasFocus

                widget = option.widget
                style = widget.style() if widget else QApplication.style()

                # 1. Arka planı çiz
                style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, widget)

                bg_brush = index.data(Qt.ItemDataRole.BackgroundRole)
                bg_color_str = bg_brush.color().name().lower() if (bg_brush and hasattr(bg_brush, "color")) else ""
                if bg_brush and hasattr(bg_brush, "color") and bg_brush.color().alpha() > 0:
                    painter.save()
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(bg_brush)
                    painter.drawRoundedRect(QRectF(inner), 4.0, 4.0)
                    painter.restore()

                # Gecikme kontrolü
                is_overdue = bool(index.data(OVERDUE_FLAG_ROLE)) or (bg_color_str in ("#f8d7da", "#fee2e2", "#fde2e4"))

                # 2. Checkbox ve Metin Çizimi
                if check_state is not None:
                    if txt_str:
                        cw, ch = 16, 16
                        cx = inner.left() + 5 + cw // 2
                        cy = inner.center().y()
                        box_rect = QRect(cx - cw // 2, cy - ch // 2, cw, ch)
                        text_rect = QRect(inner.left() + 5 + cw + 4, inner.top(), inner.width() - (5 + cw + 6), inner.height())
                    else:
                        cw, ch = 18, 18
                        cx = inner.center().x()
                        cy = inner.center().y()
                        box_rect = QRect(cx - cw // 2, cy - ch // 2, cw, ch)
                        text_rect = None

                    is_checked = (check_state in (Qt.CheckState.Checked, 2))
                    is_partial = (check_state in (Qt.CheckState.PartiallyChecked, 1))

                    painter.save()
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    rf = QRectF(box_rect).adjusted(0.5, 0.5, -0.5, -0.5)

                    if is_checked:
                        if is_overdue:  # Gecikmiş ödev (kırmızı kilitli/vurgulu)
                            painter.setBrush(QColor("#ef4444"))
                            painter.setPen(QPen(QColor("#b91c1c"), 1.2))
                        elif bg_color_str in ("#fff59d", "#fff9c4", "#ffecb3"):  # Devam (sarı/turuncu)
                            painter.setBrush(QColor("#f59e0b"))
                            painter.setPen(QPen(QColor("#d97706"), 1.2))
                        elif bg_color_str in ("#a5d6a7", "#c8e6c9"):  # Yapıldı (yeşil)
                            painter.setBrush(QColor("#16a34a"))
                            painter.setPen(QPen(QColor("#15803d"), 1.2))
                        else:  # Normal seçili ödev
                            painter.setBrush(QColor("#2563eb"))
                            painter.setPen(QPen(QColor("#1d4ed8"), 1.2))

                        painter.drawRoundedRect(rf, 3.5, 3.5)

                        # Beyaz tik işareti (✓)
                        pen = QPen(QColor("#ffffff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                        painter.setPen(pen)
                        painter.setBrush(Qt.BrushStyle.NoBrush)

                        path = QPainterPath()
                        path.moveTo(QPointF(rf.x() + cw * 0.22, rf.y() + ch * 0.52))
                        path.lineTo(QPointF(rf.x() + cw * 0.42, rf.y() + ch * 0.74))
                        path.lineTo(QPointF(rf.x() + cw * 0.78, rf.y() + ch * 0.28))
                        painter.drawPath(path)

                    elif is_partial:
                        painter.setBrush(QColor("#fef3c7"))
                        painter.setPen(QPen(QColor("#d97706"), 1.4))
                        painter.drawRoundedRect(rf, 3.5, 3.5)
                        pen = QPen(QColor("#d97706"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                        painter.setPen(pen)
                        painter.drawLine(QPointF(rf.x() + cw * 0.25, rf.center().y()), QPointF(rf.x() + cw * 0.75, rf.center().y()))

                    else:
                        # Boş / İşaretsiz Onay Kutusu
                        is_hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
                        painter.setBrush(QColor("#ffffff"))
                        painter.setPen(QPen(QColor("#ef4444" if (is_overdue and is_hover) else ("#64748b" if is_hover else "#94a3b8")), 1.5))
                        painter.drawRoundedRect(rf, 3.5, 3.5)

                    # Metin varsa çiz (örn: "28g")
                    if text_rect and txt_str:
                        fg_brush = index.data(Qt.ItemDataRole.ForegroundRole)
                        fg_color = fg_brush.color() if (fg_brush and hasattr(fg_brush, "color")) else (QColor("#991b1b") if is_overdue else QColor("#1e293b"))
                        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if is_overdue else QFont.Weight.Normal))
                        painter.setPen(fg_color)
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, txt_str)

                    painter.restore()
                
                # 3. Flash efekti
                tbl = self.parent()
                if getattr(tbl, "_flash_cells", None) and (index.row(), index.column()) in tbl._flash_cells:
                     painter.save()
                     rect = option.rect.adjusted(GAP_X // 2 + 1, GAP_Y // 2 + 1, -(GAP_X // 2 + 1), -(GAP_Y // 2 + 1))
                     painter.setPen(Qt.PenStyle.NoPen);
                     painter.setBrush(QColor("#93C5FD"))
                     painter.drawRect(rect)
                     pen = QPen(QColor("#2563EB"));
                     pen.setWidth(2)
                     painter.setPen(pen);
                     painter.setBrush(Qt.BrushStyle.NoBrush)
                     painter.drawRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5))
                     painter.restore()

            def _toggle(self, model, index):
                st = index.data(Qt.ItemDataRole.CheckStateRole)
                new_st = Qt.CheckState.Unchecked if st == Qt.CheckState.Checked else Qt.CheckState.Checked
                model.setData(index, new_st, Qt.ItemDataRole.CheckStateRole)
                if callable(self._on_toggled):
                    try:
                        self._on_toggled(index.row(), index.column())
                    except Exception:
                        pass

            def editorEvent(self, event, model, option, index):
                if _is_locked_index(index): return True
                et = event.type();
                btn = getattr(event, "button", lambda: None)()
                # Tıklama ile toggle (tüm yücre)
                if et == QEvent.Type.MouseButtonRelease and btn == Qt.MouseButton.LeftButton:
                     self._toggle(model, index);
                     return True
                # Diğer olaylar
                return False # super çağırırsak standart davranış gelir, gerek yok çünkü biz yönettik

        class _FirstColHover(_BaseGap):
            def paint(self, painter, option, index):
                super().paint(painter, option, index)
                tbl = self.parent()
                if index.column() == 0 and getattr(tbl, "_hover_row", -1) == index.row():
                    inner = option.rect.adjusted(GAP_X // 2, GAP_Y // 2, -GAP_X // 2, -GAP_Y // 2)
                    pen = QPen(QColor("#2563EB"));
                    pen.setWidth(3)
                    painter.save();
                    painter.setPen(pen);
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(inner.adjusted(1, 1, -1, -1));
                    painter.restore()

        if not hasattr(self, "_flash_cell"):
            def _flash_cell(tbl, r, c, ms=140):
                if not hasattr(tbl, "_flash_cells"): tbl._flash_cells = set()
                tbl._flash_cells.add((r, c))
                tbl.viewport().update(tbl.visualRect(tbl.model().index(r, c)))
                QtCore.QTimer.singleShot(ms, lambda: (tbl._flash_cells.discard((r, c)),
                                                      tbl.viewport().update(
                                                          tbl.visualRect(tbl.model().index(r, c)))))

            self._flash_cell = _flash_cell

        def _on_toggled_flash(r, c, _t=table):
            self._flash_cell(_t, r, c, ms=140)

        table.setItemDelegateForColumn(0, _FirstColHover(table))
        tog = _Toggle(on_toggled=_on_toggled_flash, parent=table)
        for col in range(1, table.columnCount()): table.setItemDelegateForColumn(col, tog)
        table._gap_base_delegate = tog  # GC koruması

        # ---- başlık hover çerçevesi ----
        class HoverHeader(QHeaderView):
            def __init__(self, orientation, parent=None):
                super().__init__(orientation, parent);
                self._hover_sec = -1
                self.setMouseTracking(True);
                self.setSectionsClickable(True)

            def _section_rect(self, sec: int) -> QRect:
                if sec < 0: return QRect()
                if self.orientation() == Qt.Orientation.Horizontal:
                    x = self.sectionViewportPosition(sec);
                    w = self.sectionSize(sec)
                    return QRect(x, 0, w, self.height())
                y = self.sectionViewportPosition(sec);
                h = self.sectionSize(sec)
                return QRect(0, y, self.width(), h)

            def setHovered(self, sec: int):
                if sec == self._hover_sec: return
                old = self._hover_sec;
                self._hover_sec = sec
                if old >= 0: self.viewport().update(self._section_rect(old))
                if sec >= 0: self.viewport().update(self._section_rect(sec))

            def paintSection(self, p, rect, i):
                super().paintSection(p, rect, i)
                if i == self._hover_sec and rect.isValid():
                    p.save();
                    pen = QPen(QColor("#2563EB"));
                    pen.setWidth(2)
                    p.setPen(pen);
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRect(rect.adjusted(1, 1, -1, -1));
                    p.restore()

        hh = HoverHeader(Qt.Orientation.Horizontal, table);
        table.setHorizontalHeader(hh)

        # ---- hover takibi (1. sütun çerçevesi + header hover) ----
        class _HoverTracker(QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == QEvent.Type.MouseMove:
                    idx = table.indexAt(ev.pos())
                    if idx.isValid():
                        hh.setHovered(idx.column())
                        old = getattr(table, "_hover_row", -1);
                        new = idx.row()
                        if new != old:
                            table._hover_row = new
                            if old >= 0: table.viewport().update(table.visualRect(table.model().index(old, 0)))
                            table.viewport().update(table.visualRect(table.model().index(new, 0)))
                    else:
                        hh.setHovered(-1)
                        old = getattr(table, "_hover_row", -1);
                        table._hover_row = -1
                        if old >= 0: table.viewport().update(table.visualRect(table.model().index(old, 0)))
                elif ev.type() in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                    hh.setHovered(-1)
                    old = getattr(table, "_hover_row", -1);
                    table._hover_row = -1
                    if old >= 0: table.viewport().update(table.visualRect(table.model().index(old, 0)))
                return False

        tracker = _HoverTracker(table)
        table.viewport().installEventFilter(tracker)
        table._hover_tracker = tracker

        # ---- konteyner ----
        container = QWidget()
        lay = QVBoxLayout(container);
        lay.setContentsMargins(0, 0, 0, 0);
        lay.addWidget(table)

        # mevcut yardımcıların kalsın
        try:
            self._freeze_konu_sutunu(table)
        except Exception:
            pass
        try:
            self._install_hover_highlight(table)
        except Exception:
            pass

        # sağ tık menü (senin fonksiyonun)
        self._install_context_menu(table)

        # Konu metinleri uzun olabilir → çok satır + içeriğe göre boyut
        table.setWordWrap(True)
        table.resizeColumnToContents(0)  # 0. sütun genişliği içeriğe uysun
        for r in range(table.rowCount()):
            table.resizeRowToContents(r)  # satırlar yüksekliğini alsın
        #
        # self._freeze_konu_sutunu(table)  # Disabled to remove ghost row numbers and simple layout
        
        # Final safety to remove row numbers
        table.verticalHeader().setFixedWidth(0)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().hide()

        return container, table



    def _flash_cell(self, table, row: int, col: int, ms: int = 140):
        """
        Tıklanan hücre için belirgin 'blink': doygun mavi arka plan + 2px kenarlık.
        Kilitli (yeşil/sarı) hücrelerde çalışmaz. Sadece ilgili hücre repaint edilir.
        """
        from PyQt6.QtCore import QTimer

        it = table.item(row, col)
        if not it:
            return

        # kilitli renkler → efekt uygulama
        try:
            bg = it.background().color().name().lower()
            if bg in {"#a5d6a7", "#fff59d"}:
                return
        except Exception:
            pass

        # Flash izlemesi için set
        if not hasattr(table, "_flash_cells"):
            table._flash_cells = set()
        table._flash_cells.add((row, col))

        # Sadece bu hücreyi güncelle
        try:
            idx = table.model().index(row, col)
            table.viewport().update(table.visualRect(idx))
        except Exception:
            pass

        def _clear():
            try:
                table._flash_cells.discard((row, col))
                idx2 = table.model().index(row, col)
                table.viewport().update(table.visualRect(idx2))
            except Exception:
                pass

        QTimer.singleShot(int(ms), _clear)

    #DAHA İYİ
    def _freeze_konu_sutunu(self, table):
        """
        Solda 'Konu' donuk görünüm (sadece 0. sütun).
        >>> Hiza düzeltmesi: Ana tabloda YATAY SCROLLBAR görünür olduğunda,
        >>> sol görünümde de yatay scrollbar POLİTİKASI 'AlwaysOn' yapılır; görünmezse 'AlwaysOff'.
        >>> Böylece iki tarafta ayrılan yükseklik eşit olur ve son satır kaymaz.
        Diğer davranışlar korunur.
        """
        from PyQt6.QtWidgets import QWidget, QHBoxLayout, QTableView, QAbstractItemView, QStyledItemDelegate
        from PyQt6.QtCore import Qt, QEvent, QTimer, QModelIndex, QObject
        from PyQt6.QtGui import QColor, QPainter, QPen
        import weakref

        if getattr(table, "_frozen_ready", False):
            try:
                if hasattr(table, "_frozen_fit_sync_cb"):
                    table._frozen_fit_sync_cb()
            except Exception:
                pass
            return

        # ---- Sol görünüm
        leftView = QTableView(table.parent())
        leftView.setModel(table.model())
        leftView.verticalHeader().setVisible(False)
        leftView.verticalHeader().hide() # Double safety
        leftView.horizontalHeader().setVisible(True)
        leftView.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        leftView.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        leftView.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        leftView.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # başlangıç
        leftView.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        leftView.setFrameShape(table.frameShape())
        leftView.setFrameShadow(table.frameShadow())
        leftView.setWordWrap(True)
        leftView.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        leftView.setAlternatingRowColors(table.alternatingRowColors())
        leftView.setStyleSheet(table.styleSheet())

        # Sadece 0. sütun açık
        for c in range(table.model().columnCount()):
            leftView.setColumnHidden(c, c != 0)

        # ---- Yerleşim
        parent = table.parent()
        holder = QWidget(parent)
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(leftView)
        lay.addWidget(table)

        pl = parent.layout()
        if pl is not None:
            try:
                pl.removeWidget(table)
            except Exception:
                pass
            table.setParent(holder)
            pl.addWidget(holder)

        table.setColumnHidden(0, True)

        # ---- refs
        t_ref = weakref.ref(table)
        lv_ref = weakref.ref(leftView)

        def _alive():
            return t_ref() is not None and lv_ref() is not None

        # ---- genişlik & satır yükseklik senkronu
        def _fit_left_width():
            if not _alive(): return
            try:
                hh = table.horizontalHeader().height()
                leftView.horizontalHeader().setFixedHeight(hh)
                w_hint = max(table.columnWidth(0), leftView.sizeHintForColumn(0))
                leftView.setFixedWidth(max(0, w_hint + 2))
            except RuntimeError:
                pass

        def _sync_row_heights():
            if not _alive(): return
            try:
                rc = table.rowCount()
                for r in range(rc):
                    h = table.rowHeight(r)
                    h2 = leftView.sizeHintForRow(r)
                    hh = max(h, h2)
                    if hh != h:
                        table.setRowHeight(r, hh)
                    leftView.setRowHeight(r, hh)
            except RuntimeError:
                pass

        # ---- *** KRİTİK: yatay scrollbar politikasını aynala ***
        def _mirror_hbar_policy():
            if not _alive(): return
            try:
                hs = table.horizontalScrollBar()
            except RuntimeError:
                return
            # Görünürlük testi: maksimum > minimum ise içerik taşması vardır (en güvenlisi)
            need = False
            try:
                need = hs.maximum() > hs.minimum()
            except RuntimeError:
                need = False
            # Politika değişimi
            try:
                leftView.setHorizontalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOn if need else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
                # Aynı yükseklik için sol barın yüksekliğini de ana barınkine sabitle
                if need:
                    try:
                        leftView.horizontalScrollBar().setFixedHeight(hs.sizeHint().height())
                    except Exception:
                        pass
                else:
                    try:
                        leftView.horizontalScrollBar().setFixedHeight(
                            leftView.style().pixelMetric(leftView.style().PM_ScrollBarExtent))
                    except Exception:
                        pass
            except RuntimeError:
                pass

        # ---- dikey scroll senkronu
        def _sync_v(v):
            if not _alive(): return
            try:
                leftView.verticalScrollBar().setValue(v)
            except RuntimeError:
                pass

        try:
            table.verticalScrollBar().valueChanged.connect(_sync_v)
            table.verticalHeader().sectionResized.connect(lambda *_: _sync_row_heights())
            table.horizontalHeader().sectionResized.connect(lambda sec, *_: (_fit_left_width() if sec == 0 else None))
        except RuntimeError:
            return

        # yatay bar olaylarına bağla
        try:
            hs = table.horizontalScrollBar()
            hs.rangeChanged.connect(lambda *_: (_mirror_hbar_policy(), _sync_row_heights()))
            hs.valueChanged.connect(lambda *_: _mirror_hbar_policy())
        except RuntimeError:
            pass

        # resize/show/hide → hizayı tazele
        class _Watcher(QObject):
            def eventFilter(self, obj, ev):
                if not _alive(): return False
                et = ev.type()
                if et in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Hide):
                    QTimer.singleShot(0, lambda: (_mirror_hbar_policy(), _fit_left_width(), _sync_row_heights()))
                return False

        watcher = _Watcher(leftView)
        table.installEventFilter(watcher)
        leftView.installEventFilter(watcher)
        leftView._freeze_watcher = watcher

        # ---- hover senkron (korundu)
        try:
            table.setMouseTracking(True)
            table.viewport().setMouseTracking(True)
        except RuntimeError:
            return

        leftView._hover_row = -1
        vp = table.viewport()
        try:
            if hasattr(leftView, "_hover_tracker") and leftView._hover_tracker:
                vp.removeEventFilter(leftView._hover_tracker)
        except Exception:
            pass

        class _SafeHoverTracker(QObject):
            def eventFilter(self, obj, ev):
                if not _alive() or obj is not vp: return False
                et = ev.type()
                if et == QEvent.Type.MouseMove:
                    try:
                        idx = table.indexAt(ev.pos())
                    except RuntimeError:
                        return False
                    row = idx.row() if idx.isValid() else -1
                    if row != leftView._hover_row:
                        old = leftView._hover_row
                        leftView._hover_row = row
                        try:
                            if old >= 0:
                                leftView.viewport().update(leftView.visualRect(leftView.model().index(old, 0)))
                            if row >= 0:
                                leftView.viewport().update(leftView.visualRect(leftView.model().index(row, 0)))
                        except RuntimeError:
                            return False
                elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                    if leftView._hover_row != -1:
                        old = leftView._hover_row
                        leftView._hover_row = -1
                        try:
                            leftView.viewport().update(leftView.visualRect(leftView.model().index(old, 0)))
                        except RuntimeError:
                            return False
                return False

        tracker = _SafeHoverTracker(leftView)
        vp.installEventFilter(tracker)
        leftView._hover_tracker = tracker

        # ---- sol delege
        class HoverZebraDelegate(QStyledItemDelegate):
            def paint(self, painter: QPainter, option, index: QModelIndex):
                try:
                    base = table.palette().base().color()
                    alt = table.palette().alternateBase().color()
                except RuntimeError:
                    return
                bg = alt if (index.row() % 2) else base
                painter.save()
                painter.fillRect(option.rect, bg)
                if index.row() == getattr(leftView, "_hover_row", -1):
                    hl = QColor(37, 99, 235, 28)
                    pen = QPen(QColor(37, 99, 235));
                    pen.setWidth(2)
                    painter.fillRect(option.rect.adjusted(1, 1, -1, -1), hl)
                    painter.setPen(pen);
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
                super().paint(painter, option, index)
                painter.restore()

        leftView.setItemDelegateForColumn(0, HoverZebraDelegate(leftView))

        # ---- ilk yerleşim + tek seferlik sync
        try:
            leftView.resizeColumnToContents(0)
        except RuntimeError:
            pass

        def _safe_fit_sync():
            _mirror_hbar_policy()
            _fit_left_width()
            _sync_row_heights()

        model = table.model()
        try:
            model.modelReset.connect(lambda: QTimer.singleShot(0, _safe_fit_sync))
            model.layoutChanged.connect(lambda: QTimer.singleShot(0, _safe_fit_sync))
            model.rowsInserted.connect(lambda *_: QTimer.singleShot(0, _safe_fit_sync))
            model.rowsRemoved.connect(lambda *_: QTimer.singleShot(0, _safe_fit_sync))
        except RuntimeError:
            pass

        _safe_fit_sync()

        # ---- temizlik
        def _cleanup(*_):
            try:
                if vp:
                    vp.removeEventFilter(tracker)
            except Exception:
                pass
            try:
                table.removeEventFilter(watcher)
                leftView.removeEventFilter(watcher)
            except Exception:
                pass
            try:
                table._frozen_ready = False
            except Exception:
                pass

        try:
            table.destroyed.connect(_cleanup)
            leftView.destroyed.connect(_cleanup)
        except Exception:
            pass

        table._frozen_left_view = leftView
        table._frozen_holder = holder
        table._frozen_fit_sync_cb = _safe_fit_sync
        table._frozen_ready = True

    #s
    # ------------------ SAĞ TIK MENÜSÜ EKLEYEN FONKSİYON ------------------
    def _install_context_menu(self, table):
        """
        Sağ tık menüsü (renk-temelli kilit kontrolü, hover efektli).
        - ✅ Tek hücre: Ödev Verildi / Geri Al (toggle)
        - ➕ Aynı Satırdaki Diğer Kitaplara da Ver
        - ➖ Aynı Satırdaki Tikleri Geri Al (kilitsiz)
        - 📘 Bu Kitaptaki Tüm Konuları Ver
        - 🚫 Bu Kitaptaki Tüm Ödevleri Geri Al (kilitsiz)
        - 🧹 Bu Kitaptaki Tüm Tikleri Temizle (kilitsiz)  [= geri al ile aynı]
        Kilitli (yeşil/sarı/kırmızı tonlar) hücrelerin tikleri asla oynanmaz.
        """
        # ---- imports ----
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction, QColor
        from PyQt6.QtCore import Qt, QPoint

        # Renk-temelli kilit sezgisi (lower-case hex)
        LOCKED_COLORS = {
            "#a5d6a7",  # yeşil (tamamlandı)
            "#fff59d",  # sarı (devam)
            "#fca5a5", "#fecaca", "#ffcdd2", "#f8d7da"  # kırmızı/pembe tonları (kilitli kabul)
        }

        def _is_locked_index(index) -> bool:
            """Arka plan rengine bakarak kilitli mi? (renkten git)"""
            # 1) Flag kontrolü
            if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                return True

            try:
                brush = index.data(Qt.ItemDataRole.BackgroundRole)
                if not brush:
                    return False
                name = brush.color().name().lower()
                if name in LOCKED_COLORS:
                    return True
                # ekstra küçük heuristik: kırmızımsı tonlar
                col = brush.color().toRgb()
                h, s, l = col.hslHue(), col.hslSaturation(), col.lightness()
                return (h != -1 and (h <= 15 or h >= 345) and s >= 60 and l >= 100)
            except Exception:
                return False

        def _flash_safe(r, c):
            try:
                self._flash_cell(table, r, c, ms=120)
            except Exception:
                pass

        def _set_tick(index, checked: bool):
            """Yalnızca CheckState değiştir (kilitli ise dokunma)."""
            if not index.isValid() or _is_locked_index(index):
                return
            want = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            if index.data(Qt.ItemDataRole.CheckStateRole) != want:
                index.model().setData(index, want, Qt.ItemDataRole.CheckStateRole)
                _flash_safe(index.row(), index.column())

        def _toggle(index):
            if not index.isValid() or _is_locked_index(index):
                return
            cur = index.data(Qt.ItemDataRole.CheckStateRole)
            newv = Qt.CheckState.Unchecked if cur == Qt.CheckState.Checked else Qt.CheckState.Checked
            index.model().setData(index, newv, Qt.ItemDataRole.CheckStateRole)
            _flash_safe(index.row(), index.column())

        # Önceki bağlantı varsa kopar
        try:
            table.customContextMenuRequested.disconnect()
        except Exception:
            pass
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def _popup_menu(pos: QPoint):
            idx = table.indexAt(pos)
            menu = QMenu(table)

            # ---- HOVER / GÖRÜNÜM STİLİ (Modern & Pratik) ----
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

            # ---- Aksiyonlar (emoji ikonlu) ----
            act_toggle = QAction("✅  Ödev Verildi / Geri Al (tek hücre)", menu)
            act_row_give = QAction("➕  Aynı Satırdaki Diğer Kitaplara da Ver", menu)
            act_row_clear = QAction("➖  Aynı Satırdaki Tikleri Geri Al (kilitsiz)", menu)
            act_col_give = QAction("📘  Bu Kitaptaki Tüm Konuları Ver", menu)
            act_col_clear = QAction("🚫  Bu Kitaptaki Tüm Ödevleri Geri Al (kilitsiz)", menu)
            act_col_clean = QAction("🧹  Bu Kitaptaki Tüm Tikleri Temizle (kilitsiz)", menu)

            menu.addAction(act_toggle)
            menu.addSeparator()
            menu.addAction(act_row_give)
            menu.addAction(act_row_clear)
            menu.addAction(act_col_give)
            menu.addAction(act_col_clear)
            menu.addAction(act_col_clean)
            


            # ---- Bağlantılar ----
            def do_toggle():
                if idx.isValid() and idx.column() != 0:
                    _toggle(idx)

            def do_row_give():
                if not idx.isValid(): return
                r = idx.row()
                for c in range(1, table.columnCount()):
                    i = table.model().index(r, c)
                    _set_tick(i, True)

            def do_row_clear():
                if not idx.isValid(): return
                r = idx.row()
                for c in range(1, table.columnCount()):
                    i = table.model().index(r, c)
                    _set_tick(i, False)

            def do_col_give():
                if not idx.isValid() or idx.column() == 0: return
                c = idx.column()
                for r in range(table.rowCount()):
                    i = table.model().index(r, c)
                    _set_tick(i, True)

            def do_col_clear():
                if not idx.isValid() or idx.column() == 0: return
                c = idx.column()
                for r in range(table.rowCount()):
                    i = table.model().index(r, c)
                    _set_tick(i, False)

            def do_col_clean():
                do_col_clear()

            act_toggle.triggered.connect(do_toggle)
            act_row_give.triggered.connect(do_row_give)
            act_row_clear.triggered.connect(do_row_clear)
            act_col_give.triggered.connect(do_col_give)
            act_col_clear.triggered.connect(do_col_clear)
            act_col_clean.triggered.connect(do_col_clean)

            # --- PRO Smart Features v9 (Gap Analysis) ---
            act_book_status = QAction("📚 Kıyaslamalı Kitap Karnesi & Tahmin", menu)
            act_lesson_analyze = QAction("📈 Genel Ders/Branş Karnesi", menu)
            act_gap_analyze = QAction("📉 Eksik/Zayıf Konu Tespiti (Gap Analizi)", menu)
            act_smart_analyze = QAction("🚀 Akıllı Konu Analizi (Hız & Trend)", menu)
            
            menu.addSeparator()
            menu.addAction(act_book_status)
            menu.addAction(act_lesson_analyze)
            menu.addAction(act_gap_analyze)
            menu.addAction(act_smart_analyze)

            def do_gap_analyze():
                try:
                    oid = self._secili_ogrenci_id()
                    # Tüm konuları ve kitapları çek (Mevcut Görünüm)
                    books = []
                    for c in range(1, table.columnCount()):
                        it = table.horizontalHeaderItem(c)
                        if it: books.append(it.text())
                    
                    if not books: return
                    
                    import db
                    con = db.get_conn()
                    cur = con.cursor()
                    
                    # Tek sorguda tüm veriyi çek (Pivot benzeri)
                    # konu_ad, ogrenci_id, count
                    placeholders = ','.join(['?']*len(books))
                    cur.execute(f"""
                        SELECT konu_ad, ogrenci_id, count(id)
                        FROM odev
                        WHERE kitap_ad IN ({placeholders}) AND durum IN ('tamam','yapildi')
                        GROUP BY konu_ad, ogrenci_id
                    """, books)
                    rows = cur.fetchall()
                    con.close()
                    
                    # Veriyi işle
                    # topic_stats = { 'KonuA': {oid: 5, 'total': 100, 'users': 20}, ... }
                    topic_data = {}
                    for t, u, c in rows:
                        if t not in topic_data: topic_data[t] = {'scores': {}}
                        topic_data[t]['scores'][u] = c
                        
                    gaps = []
                    
                    for t, data in topic_data.items():
                        scores = data['scores']
                        my_s = scores.get(oid, 0)
                        u_count = len(scores)
                        if u_count == 0: continue
                        
                        avg_s = sum(scores.values()) / u_count
                        # Farkı hesapla (Ortalama - Benim)
                        gap = avg_s - my_s
                        
                        # Sadece geride olduklarımızı al
                        if gap > 0.5: # En az 0.5 fark varsa
                            gaps.append((gap, t, my_s, avg_s))
                    
                    # Sırala (En büyük fark en üstte)
                    gaps.sort(key=lambda x: x[0], reverse=True)
                    top_gaps = gaps[:5] # İlk 5
                    
                    metrics = [
                        ("Taranan Konu", f"{len(topic_data)}", "#34495e"),
                        ("Riskli Konu", f"{len(gaps)}", "#e74c3c"),
                        ("Durum", "İyi" if not gaps else "Eksik Var", "#27ae60" if not gaps else "#e67e22")
                    ]
                    
                    if not top_gaps:
                         comm = {"text": "🎉 <b>Harika!</b><br>Sınıf ortalamasının altında kaldığınız hiçbir konu yok.", "bg": "#d5f5e3", "border": "#27ae60", "color": "#1e824c"}
                         comps = []
                    else:
                        comm = {"text": "⚠️ <b>Dikkat Gerektirir.</b><br>Aşağıdaki konularda sınıf arkadaşlarınıza göre daha az soru çözmüşsünüz.", "bg": "#fadbd8", "border": "#c0392b", "color": "#c0392b"}
                        comps = []
                        # Progress bar yerine Gap listesi gösterelim
                        msg_rows = []
                        for g, t, m, a in top_gaps:
                            lbl = f"{t}\n(Siz: {m} | Sınıf: {a:.1f})"
                            comps.append((lbl, (m/a)*100 if a>0 else 0, "#e74c3c"))
                            
                    dlg = ModernReportDialog("Zayıf Nokta Analizi", f"Genel Tarama ({len(books)} Kitap)", metrics, comps, comm, table)
                    dlg.exec()

                except Exception as e:
                    QMessageBox.critical(table, "Hata", str(e))

            def do_lesson_analyze():
                try:
                    oid = self._secili_ogrenci_id()
                    books = []
                    for c in range(1, table.columnCount()):
                        it = table.horizontalHeaderItem(c)
                        if it: books.append(it.text())
                    
                    if not books: return
                    
                    placeholders = ','.join(['?'] * len(books))
                    
                    import db
                    con = db.get_conn()
                    cur = con.cursor()
                    
                    sql = f"""
                        SELECT ogrenci_id, count(id)
                        FROM odev
                        WHERE kitap_ad IN ({placeholders}) AND durum IN ('tamam','yapildi')
                        GROUP BY ogrenci_id
                    """
                    cur.execute(sql, books)
                    all_scores = cur.fetchall()
                    con.close()
                    
                    scores_map = {r[0]: r[1] for r in all_scores}
                    my_score = scores_map.get(oid, 0)
                    total_users = len(scores_map)
                    
                    if total_users == 0:
                        avg_score = 0; rank = 1
                    else:
                        avg_score = sum(scores_map.values()) / total_users
                        sorted_scores = sorted(scores_map.values(), reverse=True)
                        if my_score in sorted_scores:
                            rank = sorted_scores.index(my_score) + 1
                        else:
                            rank = total_users + 1
                            
                    max_score = max(scores_map.values()) if scores_map else 1
                    my_ratio = int((my_score/max_score)*100) if max_score>0 else 0
                    cls_ratio = int((avg_score/max_score)*100) if max_score>0 else 0
                    
                    metrics = [
                        ("Toplam Soru", f"{my_score}", "#2c3e50"),
                        ("Sınıf Ort.", f"{avg_score:.1f}", "#7f8c8d"),
                        ("Branş Sıralaması", f"{rank}. / {total_users+(1 if my_score==0 else 0)}", "#8e44ad")
                    ]
                    comps = [
                        ("Siz (Zirveye Göre)", my_ratio, "#8e44ad"),
                        ("Sınıf Ort.", cls_ratio, "#95a5a6")
                    ]
                    
                    if my_score == 0:
                         comm = {"text": "⚠️ <b>Veri Yok.</b><br>Bu branşta henüz hiç aktivite görünmüyor.", "bg": "#ecf0f1", "border": "#bdc3c7"}
                    elif rank == 1 and total_users > 1:
                        comm = {"text": "🏆 <b>BRANŞ LİDERİ!</b><br>Bu derste sınıfın en çok soru çözen öğrencisi sizsiniz.", "bg": "#d5f5e3", "border": "#27ae60", "color": "#1e824c"}
                    elif rank <= 3:
                         comm = {"text": "🔥 <b>Zirveyi Zorluyorsun!</b><br>İlk 3 içerisindesin. Liderlik çok yakın.", "bg": "#d5f5e3", "border": "#2ecc71"}
                    else:
                        comm = {"text": "📊 <b>Genel Durum.</b><br>Daha fazla kitap bitirerek sıralamanı yükseltebilirsin.", "bg": "#fcf3cf", "border": "#f1c40f"}
                        
                    dlg = ModernReportDialog("Genel Ders Karnesi", f"Kapsam: {len(books)} Kitap", metrics, comps, comm, table)
                    dlg.exec()
                    
                except Exception as e:
                    QMessageBox.critical(table, "Hata", str(e))

            def do_book_status():
                if not idx.isValid(): return
                c = idx.column()
                
                if c == 0:
                     QMessageBox.warning(table, "Hatalı Seçim", "Lütfen bir KİTAP sütununa sağ tıklayın.")
                     return

                try:
                    kitap_adi = table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else "Genel"
                    oid = self._secili_ogrenci_id()
                    total_topics = table.rowCount()
                    
                    import db
                    con = db.get_conn()
                    cur = con.cursor()
                    
                    # 1. Herkesin Durumu (Sıralama)
                    cur.execute("""
                        SELECT ogrenci_id, count(DISTINCT konu_ad)
                        FROM odev
                        WHERE kitap_ad=? AND durum IN ('tamam','yapildi')
                        GROUP BY ogrenci_id
                    """, (kitap_adi,))
                    all_scores = cur.fetchall()
                    
                    # 2. Tarihsel Veri (Yapay Zeka Tahmini İçin)
                    cur.execute("""
                        SELECT k.verilis_tarihi
                        FROM odev d
                        JOIN odev_kume k ON d.kume_id = k.id
                        WHERE d.ogrenci_id=? AND d.kitap_ad=? AND d.durum IN ('tamam','yapildi')
                    """, (oid, kitap_adi))
                    dates_raw = [r[0] for r in cur.fetchall()]
                    
                    con.close()
                    
                    # İstatistikler
                    scores_map = {r[0]: r[1] for r in all_scores}
                    my_score = scores_map.get(oid, 0)
                    active_students_count = len(scores_map)
                    
                    if active_students_count == 0:
                        avg_score = 0; rank = 1
                    else:
                        avg_score = sum(scores_map.values()) / active_students_count
                        sorted_scores = sorted(scores_map.values(), reverse=True)
                        if my_score in sorted_scores:
                            rank = sorted_scores.index(my_score) + 1
                        else:
                            rank = active_students_count + 1
                    
                    my_ratio = int((my_score / total_topics) * 100) if total_topics > 0 else 0
                    cls_ratio = int((avg_score / total_topics) * 100) if total_topics > 0 else 0
                    
                    # --- AI TAHMİNİ ---
                    est_str = "Veri Yetersiz"
                    est_color = None
                    if my_ratio == 100:
                        est_str = "TAMAMLANDI 🎉"
                        est_color = "#27ae60"
                    elif len(dates_raw) >= 2 and my_score > 0:
                        try:
                            d_objs = []
                            for d in dates_raw:
                                for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                                    try: d_objs.append(datetime.strptime(d, fmt)); break
                                    except: pass
                            if d_objs:
                                start = min(d_objs); end = max(d_objs)
                                span_days = (end - start).days
                                if span_days > 0:
                                    rate = my_score / span_days # konu/gün
                                    rem = total_topics - my_score
                                    days_left = int(rem / rate)
                                    finish_date = datetime.now() + timedelta(days=days_left)
                                    est_str = finish_date.strftime("%d.%m.%Y")
                                    # Renklendirme
                                    if days_left > 120: est_color = "#c0392b" # Çok geç
                                    elif days_left < 30: est_color = "#27ae60" # Yakın
                        except: pass

                    metrics = [
                        ("Sizin Skor", f"{my_score}/{total_topics}", "#2980b9"),
                        ("Sıralama", f"{rank}/{active_students_count+(1 if my_score==0 else 0)}", "#e67e22"),
                        ("Tahmini Bitiş", est_str, est_color)
                    ]
                    comps = [
                        ("Siz", my_ratio, "#3498db"),
                        ("Sınıf Ort.", cls_ratio, "#95a5a6")
                    ]
                    
                    # Yorum
                    if my_score == 0:
                         comm = {"text": "🏁 <b>Başlangıç Çizgisi.</b><br>Hemen ilk görevi vererek serüveni başlatın!", "bg": "#ecf0f1", "border": "#bdc3c7"}
                    elif rank == 1 and active_students_count > 1:
                        comm = {"text": "🚀 <b>ROL MODEL!</b><br>Sınıfın zirvesindesiniz. Bu tempoyu koruyun.", "bg": "#d5f5e3", "border": "#27ae60", "color": "#1e824c"}
                    else:
                        comm = {"text": "💡 <b>Analiz Notu:</b><br>Düzenli ödev vererek bitiş tarihini öne çekebilirsiniz.", "bg": "#fcf3cf", "border": "#f1c40f", "color": "#f39c12"}

                    dlg = ModernReportDialog(f"{kitap_adi}", "Gelişmiş Kitap Analizi", metrics, comps, comm, table)
                    dlg.exec()

                except Exception as e:
                    QMessageBox.critical(table, "Hata", f"Beklenmedik bir sorun:\n{str(e)}")

            def do_smart_analyze():
                if not idx.isValid(): return
                try:
                    r = idx.row()
                    konu_item = table.item(r, 0)
                    konu_adi = konu_item.text() if konu_item else "?"
                    oid = self._secili_ogrenci_id()
                    
                    import db
                    con = db.get_conn()
                    cur = con.cursor()
                    
                    cur.execute("""
                        SELECT count(id), sum(case when durum IN ('tamam','yapildi') then 1 else 0 end)
                        FROM odev WHERE ogrenci_id=? AND konu_ad=?
                    """, (oid, konu_adi))
                    res_std = cur.fetchone()
                    std_total = res_std[0] or 0
                    std_done = res_std[1] or 0
                    std_ratio = int((std_done/std_total)*100) if std_total > 0 else 0

                    # Son Aktivite (Risk Analizi)
                    cur.execute("""
                        SELECT MAX(k.verilis_tarihi)
                        FROM odev d JOIN odev_kume k ON d.kume_id=k.id
                        WHERE d.ogrenci_id=? AND d.konu_ad=? AND d.durum IN ('tamam','yapildi')
                    """, (oid, konu_adi))
                    last_date_str = cur.fetchone()[0]
                    
                    days_inactive = 0
                    risk_label = "Taze"
                    risk_color = "#27ae60"
                    
                    if last_date_str:
                         try:
                             last_date = None
                             for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                                 try: last_date = datetime.strptime(last_date_str, fmt); break
                                 except: pass
                             if last_date:
                                 days_inactive = (datetime.now() - last_date).days
                                 if days_inactive > 30: 
                                     risk_label = f"{days_inactive} Gün (⚠️ RİSKLİ)"
                                     risk_color = "#c0392b"
                                 elif days_inactive > 14:
                                     risk_label = f"{days_inactive} Gün (Soğuyor)"
                                     risk_color = "#f39c12"
                                 else:
                                     risk_label = f"{days_inactive} Gün Önce"
                         except: pass
                    else:
                        risk_label = "Veri Yok"
                        risk_color = "#7f8c8d"

                    cur.execute("""
                        SELECT ogrenci_id, sum(case when durum IN ('tamam','yapildi') then 1 else 0 end)
                        FROM odev WHERE konu_ad=? GROUP BY ogrenci_id
                    """, (konu_adi,))
                    all_rows = cur.fetchall()

                    # --- YENİ ANALİZ SORGULARI (Hız & Trend) ---
                    # 1. Ortalama Hız (Süre / Tamamlanan Ödev Sayısı)
                    avg_speed = 0
                    try:
                        spd_row = cur.execute("""
                            SELECT SUM(saat_dk), COUNT(*) 
                            FROM odev 
                            WHERE ogrenci_id=? AND konu_ad=? AND durum IN ('tamam','yapildi','bitti')
                        """, (oid, konu_adi)).fetchone()
                        total_min = spd_row[0] or 0
                        total_cnt = spd_row[1] or 0
                        if total_cnt > 0:
                            avg_speed = int(total_min / total_cnt)
                    except: pass
                    
                    # 2. Haftalık Yük (Son 7 günde tamamlanan veya verilen)
                    weekly_count = 0
                    try:
                        wk_row = cur.execute("""
                            SELECT COUNT(*) 
                            FROM odev 
                            WHERE ogrenci_id=? AND konu_ad=? 
                            AND verilis_tarihi >= date('now', '-7 days')
                        """, (oid, konu_adi)).fetchone()
                        weekly_count = wk_row[0] or 0
                    except: pass

                    con.close()
                    
                    scores_map = {r[0]: r[1] for r in all_rows}
                    total_users = len(scores_map)
                    rank = 1
                    avg_done = 0
                    if total_users > 0:
                        avg_done = sum(scores_map.values()) / total_users
                        sorted_vals = sorted(scores_map.values(), reverse=True)
                        my_d = scores_map.get(oid, 0)
                        if my_d in sorted_vals: rank = sorted_vals.index(my_d) + 1
                        else: rank = total_users + 1
                    
                    max_d = max(scores_map.values()) if scores_map else 1
                    avg_ratio = int((avg_done/max_d)*100) if max_d>0 else 0
                    
                    # --- AKADEMIK VERİ ENTEGRASYONU (JSON) ---
                    academic_inf = None
                    try:
                        import json, os
                        # ui/homework_form.py -> .. -> assets
                        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        json_path = os.path.join(base_dir, "assets", "curriculum.json")
                        
                        if os.path.exists(json_path):
                            with open(json_path, 'r', encoding='utf-8') as f:
                                db_json = json.load(f)
                                topic_db = db_json.get("topics", {})
                                # Basit eşleşme (Küçük harf duyarsız olabilir ama şimdilik direkt)
                                academic_inf = topic_db.get(konu_adi)
                                if not academic_inf:
                                    # Fallback: Strip
                                    academic_inf = topic_db.get(konu_adi.strip())
                    except: pass
                    
                    metrics = [
                        ("Tamamlanan", f"{std_done}/{std_total}", "#34495e"),
                        #("Sınıf Ort. %", f"%{avg_ratio}", "#7f8c8d"), # Aşağıya (Kıyaslamaya) taşındı
                        ("Sıralama", f"{rank}/{total_users+(1 if std_done==0 else 0)}", "#9b59b6"),
                        ("Son Aktivite", risk_label, risk_color)
                    ]

                    # --- EKLE: HIZ ve HAFTALIK METRİKLERİ ---
                    # Her zaman göster (Veri Yoksa bile '-' koy) ki kullanıcı görsün.
                    s_label = f"{avg_speed} dk" if avg_speed > 0 else "-"
                    s_color = "#d35400" if avg_speed > 60 else ("#27ae60" if avg_speed > 0 else "#95a5a6")
                    metrics.append(("Ort. Süre", s_label, s_color))
                    
                    w_label = f"{weekly_count} Adet" if weekly_count > 0 else "Yok"
                    w_color = "#2980b9" if weekly_count > 0 else "#95a5a6"
                    metrics.append(("Haftalık", w_label, w_color))
                    
                    # Eğer akademik bilgi varsa ekle
                    aca_note = ""
                    prereq_alert = False
                    
                    # Hız/Trend Yorumunu Hazırla
                    trend_msg = ""
                    if weekly_count >= 3:
                        trend_msg = "<br><br>🔥 <b>Bu hafta alev aldınız!</b><br>Son 7 günde yoğun çalışmanız var, istikrarı bozmayın."
                    elif avg_speed > 0 and avg_speed < 15:
                        trend_msg = "<br><br>⚡ <b>Çok Hızlısınız.</b><br>Ortalama süreniz çok düşük. İşlem hatası yapmadığınızdan emin olun."
                    elif avg_speed > 60:
                        trend_msg = "<br><br>⏳ <b>Zaman Yönetimi Uyarısı:</b><br>Ödev başına 60 dk üzeri zaman harcıyorsunuz. Konuyu parçalara bölerek çalışmayı deneyin."

                    if academic_inf:
                        imp = academic_inf.get("importance", "?")
                        q_cnt = academic_inf.get("questions", "")
                        tip = academic_inf.get("tip", "")
                        
                        metrics.insert(1, ("Sınav Önemi", imp, "#d35400"))
                        
                        # Koç Ünvanını Belirle (İçeriğe Göre)
                        coach_title = "YKS Koçu"
                        try:
                             # Başlıklarda LGS var mı?
                             for col in range(table.columnCount()):
                                 h_item = table.horizontalHeaderItem(col)
                                 if h_item and "LGS" in h_item.text().upper():
                                     coach_title = "LGS Koçu"
                                     break
                        except: pass
                        
                        aca_note = f"{trend_msg}<br><br>🎓 <b>{coach_title} Diyor ki:</b><br>{tip} (Ort. {q_cnt})"
                        
                        # Kritik: Ön Koşul Kontrolü
                        prereqs = academic_inf.get("prerequisites", [])
                        if prereqs:
                            try:
                                import db
                                c2 = db.get_conn()
                                cu2 = c2.cursor()
                                missing_pqs = []
                                for pq in prereqs:
                                    # En az 5 soru çözülmüş olmalı
                                    cu2.execute("SELECT count(*) FROM odev WHERE ogrenci_id=? AND konu_ad=? AND durum IN ('tamam','yapildi')", (oid, pq))
                                    p_done = cu2.fetchone()[0] or 0
                                    if p_done < 5:
                                        missing_pqs.append(pq)
                                c2.close()
                                
                                if missing_pqs:
                                    prereq_alert = True
                                    aca_note += f"<br><br>⛔ <b>KRİTİK UYARI (Ön Koşul):</b><br>Bu konuyu tam anlamak için önce <b>{', '.join(missing_pqs)}</b> konularındaki eksiklerinizi kapatmalısınız."
                            except: pass
                    else:
                        # Akademik info yoksa bile trend mesajını ekle
                        if trend_msg:
                            aca_note += trend_msg
                    
                    comps = [
                        ("Siz", (std_done/max_d)*100 if max_d>0 else 0, "#3498db"),
                        ("Sınıf Ort.", avg_ratio, "#95a5a6")

                    ]
                    
                    comm = {"text": "Veri incelendi.", "bg": "#fcf3cf", "border": "#f1c40f"}
                    
                    if prereq_alert:
                         comm = {"text": "⛔ <b>Temel Eksikliği Tespit Edildi!</b><br>Analizlerimize göre bu konunun ön koşullarını henüz tamamlamamışsınız. Lütfen uyarı bölümünü dikkate alın." + aca_note, "bg": "#fadbd8", "border": "#c0392b", "color": "#c0392b"}
                    elif "RİSKLİ" in risk_label:
                         comm = {"text": "⚠️ <b>Unutulma Riski!</b><br>Bu konuyu uzun süredir tekrar etmediniz. Hemen bir hatırlatma testi verin." + aca_note, "bg": "#fadbd8", "border": "#c0392b", "color": "#c0392b"}
                    elif rank == 1 and total_users>1:
                         comm = {"text": "🥇 <b>Zirvedesiniz.</b><br>Konu hakimiyeti mükemmel." + aca_note, "bg": "#d5f5e3", "border": "#27ae60", "color": "#1e824c"}
                    else:
                         comm["text"] = "📊 <b>Durum Analizi:</b> Mevcut tempo iyi görünüyor." + aca_note

                    dlg = ModernReportDialog(f"{konu_adi}", "Akıllı Risk & Performans Analizi", metrics, comps, comm, table)
                    dlg.exec()

                except Exception as e:
                    QMessageBox.critical(table, "Hata", str(e))

            act_book_status.triggered.connect(do_book_status)
            act_lesson_analyze.triggered.connect(do_lesson_analyze)
            act_gap_analyze.triggered.connect(do_gap_analyze)
            act_smart_analyze.triggered.connect(do_smart_analyze)

            # --- EKLENEN AKILLI ASİSTAN BÖLÜMÜ ---
            menu.addSeparator()
            menu.addSection("🧠 Akıllı Koç Asistanı")

            # Context Variables extraction
            sa_ders = ""
            sa_konu = ""
            if idx.isValid():
                _r = idx.row()
                _c = idx.column()
                # Konu (Satır başlığı - 0. sütun)
                _item0 = table.item(_r, 0)
                if _item0: sa_konu = _item0.text()
                
                # Ders/Kitap (Sütun başlığı)
                if _c > 0:
                    _hItem = table.horizontalHeaderItem(_c)
                    if _hItem: sa_ders = _hItem.text()
            
            # 1. YouTube Arama
            act_yt = QAction("📺 YouTube: Konu Videosu Bul", menu)
            def open_yt():
                import webbrowser
                from urllib.parse import quote
                # Değişkenleri güvenli kullan
                if not sa_konu: return
                term = f"{sa_ders} {sa_konu} konu anlatımı"
                webbrowser.open(f"https://www.youtube.com/results?search_query={quote(term)}")
            
            act_yt.triggered.connect(open_yt)
            menu.addAction(act_yt)

            # 2. Google Arama
            act_gg = QAction("🔍 Google: Test/PDF Materyal Ara", menu)
            def open_gg():
                import webbrowser
                from urllib.parse import quote
                if not sa_konu: return
                term = f"{sa_ders} {sa_konu} test pdf indir yeni nesil"
                webbrowser.open(f"https://www.google.com/search?q={quote(term)}")
            
            act_gg.triggered.connect(open_gg)
            menu.addAction(act_gg)

            # --- EKLENEN OTOMASYON BÖLÜMÜ ---
            menu.addSeparator()
            menu.addSection("🚀 Otomasyon & Planlama")

            # --- OTOMASYON YARDIMCILARI ---
            def get_student_contact_info(oid):
                """Veritabanından öğrenci adı ve telefonlarını çeker."""
                import db
                con = db.get_conn()
                cur = con.cursor()
                cur.execute("SELECT ad, soyad, veli_tel1, veli_tel2, ogr_tel FROM ogrenci WHERE id=?", (oid,))
                row = cur.fetchone()
                con.close()
                
                targets = []
                name = "Öğrenci"
                if row:
                    name = f"{row[0]} {row[1]}"
                    if row[2]: targets.append((f"{name} Veli 1", row[2]))
                    if row[3]: targets.append((f"{name} Veli 2", row[3]))
                    if row[4]: targets.append((f"{name} Öğrenci", row[4]))
                
                if not targets:
                    targets.append((f"{name} (No Num)", ""))
                
                return name, targets

            def simple_send_whatsapp(targets, message):
                """Basit metin mesajı gönderim otomasyonu."""
                from urllib.parse import quote
                import subprocess, sys, time
                
                is_mac = (sys.platform == "darwin")
                
                for i, (label, num) in enumerate(targets):
                    clean_num = ''.join(filter(str.isdigit, num))
                    if not clean_num: continue
                    
                    if len(clean_num) == 10 and clean_num.startswith("5"): clean_num = "90" + clean_num
                    elif len(clean_num) == 11 and clean_num.startswith("0"): clean_num = "9" + clean_num
                    
                    encoded_msg = quote(message)
                    
                    if is_mac:
                        # 1. WhatsApp URL aç
                        subprocess.run(["open", f"whatsapp://send?phone={clean_num}&text={encoded_msg}"])
                        
                        # 2. AppleScript ile Enter'a bas (Odaklanma korumalı)
                        script = """
                        delay 0.5
                        tell application "System Events"
                            set activeApp to name of first application process whose frontmost is true
                        end tell
                        delay 1.5
                        tell application "System Events"
                            if (name of first application process whose frontmost is true) is not activeApp then
                                tell application activeApp to activate
                                delay 0.5
                            end if
                            key code 36
                            delay 0.5
                            key code 36
                        end tell
                        """
                        subprocess.run(["osascript", "-e", script])
                        
                        if i < len(targets) - 1:
                            time.sleep(3.5)
                    else:
                        import webbrowser
                        webbrowser.open(f"https://web.whatsapp.com/send?phone={clean_num}&text={encoded_msg}")

            # A. HAFIZA TAZELEME SİHİRBAZI
            act_review = QAction("🧠 Hafıza Tazeleme Sihirbazı (Unutulma Riski)", menu)
            def do_smart_review():
                try:
                    oid = self._secili_ogrenci_id()
                    ogr_ad, targets = get_student_contact_info(oid)
                    
                    import db
                    con = db.get_conn()
                    cur = con.cursor()
                    
                    # 21 Günden eski
                    cur.execute("""
                        SELECT konu_ad, max(verilis_tarihi) as son_tarih
                        FROM odev 
                        WHERE ogrenci_id=? AND durum IN ('tamam','yapildi','bitti')
                        GROUP BY konu_ad
                        HAVING son_tarih < date('now', '-21 days')
                        ORDER BY son_tarih ASC LIMIT 10
                    """, (oid,))
                    rows = cur.fetchall()
                    con.close()
                    
                    if not rows:
                        QMessageBox.information(table, "Harika!", f"{ogr_ad} için riskli (unutulmaya yüz tutmuş) konu bulunamadı.")
                        return
                    
                    msg = "🧠 *HAFIZA TAZELEME ALARMI* 🧠\n\n"
                    msg += f"Sayın Velimiz, {ogr_ad} öğrencimizin aşağıdaki konuları bitirmesinin üzerinden 3 haftadan fazla zaman geçti. Bilgilerin taze kalması için bu hafta hatırlatma testleri çözülmelidir:\n\n"
                    

                    

                    


                    for r in rows:
                        t_date = r[1]
                        try: 
                            from datetime import datetime
                            t_str = datetime.strptime(t_date, "%Y-%m-%d").strftime("%d.%m.%Y")
                        except: t_str = t_date
                        msg += f"🔸 {r[0]} (Son: {t_str})\n"

                    msg += "\n💡 *Unutmayın:* Tekrar edilmeyen bilgi uçar."
                    
                    dlg = WhatsAppGonderDialog(targets, msg, table)
                    if dlg.exec():
                        simple_send_whatsapp(dlg.secili_alicilar(), dlg.mesaj())
                    
                except Exception as e:
                    QMessageBox.critical(table, "Hata", str(e))

            act_review.triggered.connect(do_smart_review)
            menu.addAction(act_review)

            # B. OTOMATİK KAMP PLANLAYICI
            act_plan = QAction("📅 Seçili Konuları Günlere Böl (Kamp Planla)", menu)
            def do_smart_plan():
                indexes = list(table.selectedIndexes())

                # Checkbox ile işaretlileri de ekle (Kullanıcı kolaylığı)
                mdl = table.model()
                for r in range(table.rowCount()):
                    for c in range(1, table.columnCount()):
                        it = table.item(r, c)
                        if it and it.checkState() == Qt.CheckState.Checked:
                            indexes.append(mdl.index(r, c))

                if not indexes:
                    QMessageBox.warning(table, "Seçim Yok", "Lütfen planlamak istediğiniz konu kutucuklarını seçin (veya onay kutusunu işaretleyin).")
                    return
                
                oid = self._secili_ogrenci_id()
                ogr_ad, targets = get_student_contact_info(oid)
                
                # Eşsiz Konuları Bul
                tasks = []
                unique_keys = set()
                indexes = sorted(indexes, key=lambda i: (i.row(), i.column()))
                
                for i in indexes:
                    if i.column() == 0: continue 
                    r = i.row(); c = i.column()
                    
                    topic = table.item(r, 0)
                    book = table.horizontalHeaderItem(c)
                    if topic and book:
                        key = (r, c)
                        if key not in unique_keys:
                            unique_keys.add(key)
                            tasks.append({"konu": topic.text(), "kitap": book.text(), "index": i})
                
                if not tasks: return

                from PyQt6.QtWidgets import QInputDialog
                daily_cnt, ok = QInputDialog.getInt(table, "Kamp Planlayıcı", f"{len(tasks)} konu seçildi.\nGünde kaç konu çalışılsın?", 3, 1, 20, 1)
                if not ok: return
                
                import datetime
                days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
                today = datetime.datetime.now()
                
                plan_msg = f"📅 *{ogr_ad.upper()} - KİŞİYE ÖZEL KAMP PROGRAMI*\n"
                plan_msg += f"🎯 Hedef: {len(tasks)} Konuyu Bitirmek\n"
                plan_msg += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                
                idx_task = 0
                day_offset = 0
                
                while idx_task < len(tasks):
                    d_date = today + datetime.timedelta(days=day_offset)
                    d_name = days[d_date.weekday()]
                    d_str = d_date.strftime("%d.%m")
                    
                    plan_msg += f"\n🗓 *{d_str} {d_name}*\n"
                    
                    for _ in range(daily_cnt):
                        if idx_task >= len(tasks): break
                        t = tasks[idx_task]
                        plan_msg += f"☐ {t['konu']} ({t['kitap']})\n"
                        
                        # Otomatik İşaretle (Opsiyonel)
                        try:
                            ix = t["index"]
                            if ix.data(Qt.ItemDataRole.CheckStateRole) != Qt.CheckState.Checked:
                                ix.model().setData(ix, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
                        except: pass
                        
                        idx_task += 1
                    day_offset += 1
                
                plan_msg += "\n🚀 *Başarılar dileriz!*"
                
                dlg = WhatsAppGonderDialog(targets, plan_msg, table)
                if dlg.exec():
                    simple_send_whatsapp(dlg.secili_alicilar(), dlg.mesaj())

            act_plan.triggered.connect(do_smart_plan)
            menu.addAction(act_plan)
            
            # --- Veli Raporu Ekle ---
            menu.addSeparator()
            act_parent_report = QAction("💬 Veli Bilgilendirme Mesajı Oluştur", menu)
            menu.addSeparator()
            menu.addAction(act_parent_report)
            
            def do_parent_report():
                """Seçili öğrenci için çok detaylı ve görsel (Emoji/Grafik) WhatsApp raporu oluşturur."""
                from PyQt6.QtWidgets import QMessageBox
                import sqlite3
                import traceback
                import os

                row = table.currentRow()
                if row < 0:
                    QMessageBox.warning(table, "Uyarı", "Lütfen listeden bir öğrenci seçin.")
                    return

                try:
                    from urllib.parse import quote
                    import subprocess, sys, time
                    try:
                        from ui.common_pdf import save_html_as_pdf
                    except ImportError:
                        save_html_as_pdf = None

                    oid = self._secili_ogrenci_id()
                    
                    import db
                    conn = db.get_conn()
                    cur = conn.cursor()

                    # 0. ALICILARI BUL (Phone Numbers)
                    # Dialog açılmadan önce hedef listesini hazırlamalıyız.
                    cur.execute("SELECT ad, soyad, veli_tel1, veli_tel2, ogr_tel FROM ogrenci WHERE id=?", (oid,))
                    s_row = cur.fetchone()
                    
                    ogr_ad = "Öğrenci"
                    targets = [] # [(Ad, Tel), ...]
                    
                    if s_row:
                        ogr_ad = f"{s_row[0]} {s_row[1]}"
                        # Numaralar
                        vt1 = s_row[2]
                        vt2 = s_row[3]
                        ot = s_row[4]
                        
                        if vt1: targets.append((f"{s_row[0]} Veli 1", vt1))
                        if vt2: targets.append((f"{s_row[0]} Veli 2", vt2))
                        if ot:  targets.append((f"{s_row[0]} Öğrenci", ot))
                    
                    # Eğer hiç numara yoksa, boş bir kayıt ekle ki dialog açılabilsin (manuel giriş için)
                    if not targets:
                        targets.append((f"{ogr_ad} (No Num)", ""))

                    
                    # 1. Haftalık İstatistikler
                    cur.execute("""
                        SELECT count(*), 
                               SUM(CASE WHEN durum IN ('tamam','yapildi','bitti') THEN 1 ELSE 0 END)
                        FROM odev 
                        WHERE ogrenci_id=? AND verilis_tarihi >= date('now','-7 days')
                    """, (oid,))
                    w_stats = cur.fetchone()
                    w_given = w_stats[0] or 0
                    w_done = w_stats[1] or 0
                    w_success = int((w_done / w_given) * 100) if w_given > 0 else 0
                    
                    # Geçen Hafta (Trend Analizi için)
                    cur.execute("""
                        SELECT count(*), 
                               SUM(CASE WHEN durum IN ('tamam','yapildi','bitti') THEN 1 ELSE 0 END)
                        FROM odev 
                        WHERE ogrenci_id=? AND verilis_tarihi >= date('now','-14 days') AND verilis_tarihi < date('now','-7 days')
                    """, (oid,))
                    p_stats = cur.fetchone()
                    prev_given = p_stats[0] or 0
                    prev_done = p_stats[1] or 0
                    prev_success = int((prev_done / prev_given) * 100) if prev_given > 0 else 0
                    
                    # Odak Noktası (En çok ödev verilen dersler)
                    cur.execute("""
                        SELECT ders, count(*) as cnt 
                        FROM odev
                        WHERE ogrenci_id=? AND verilis_tarihi >= date('now','-7 days')
                        GROUP BY ders ORDER BY cnt DESC LIMIT 2
                    """, (oid,))
                    focus_subjects = cur.fetchall()

                    # Ders Bazlı Başarı (En iyi ve En kötü)
                    cur.execute("""
                        SELECT ders, 
                               count(*) as total,
                               SUM(CASE WHEN durum IN ('tamam','yapildi','bitti') THEN 1 ELSE 0 END) as done
                        FROM odev 
                        WHERE ogrenci_id=?
                        GROUP BY ders HAVING total > 2
                    """, (oid,))
                    lesson_stats = []
                    for ld, lt, ldn in cur.fetchall():
                        suc = int((ldn/lt)*100)
                        lesson_stats.append((ld, suc))
                    
                    lesson_stats.sort(key=lambda x: x[1], reverse=True)
                    best_lesson = lesson_stats[0] if lesson_stats else None
                    worst_lesson = lesson_stats[-1] if lesson_stats else None
                    
                    # Kaynak Durumu (Detaylı)
                    cur.execute("""
                        SELECT ders, kitap_ad, 
                               count(*) as total,
                               SUM(CASE WHEN durum IN ('tamam','yapildi','bitti') THEN 1 ELSE 0 END) as done
                        FROM odev 
                        WHERE ogrenci_id=?
                        GROUP BY ders, kitap_ad
                        HAVING total >= 1
                        ORDER BY ders, done DESC
                    """, (oid,))
                    
                    subject_books = {}
                    for b_ders, b_name, b_tot, b_done in cur.fetchall():
                        if not b_ders: b_ders = "Diğer"
                        if b_ders not in subject_books:
                            subject_books[b_ders] = []
                        b_succ = int((b_done / b_tot) * 100)
                        subject_books[b_ders].append((b_name, b_succ))
                    
                    cur.execute("SELECT count(*) FROM ogrenci_kitap WHERE ogrenci_id=?", (oid,))
                    active_books_cnt = cur.fetchone()[0] or 0

                    conn.close()

                    # Kullanıcıya Format Sor
                    msg_box = QMessageBox(table)
                    msg_box.setWindowTitle("Rapor Formatı")
                    msg_box.setText(f"{ogr_ad} için rapor oluşturuluyor. Hangi formatı istersiniz?")
                    msg_box.setIcon(QMessageBox.Icon.Question)
                    
                    bt_text = msg_box.addButton("💬 WhatsApp", QMessageBox.ButtonRole.ActionRole)
                    bt_pdf = msg_box.addButton("📄 PDF Rapor", QMessageBox.ButtonRole.ActionRole)
                    bt_cancel = msg_box.addButton("İptal", QMessageBox.ButtonRole.RejectRole)
                    
                    msg_box.exec()
                    clicked = msg_box.clickedButton()
                    
                    if clicked == bt_cancel:
                        return

                    # ---------------------------------------------------------
                    # HELPER: Sending Function
                    # ---------------------------------------------------------
                    def send_via_whatsapp(targets_list, message_content, pdf_file=None):
                        """WhatsApp üzerinden mesaj gönderir. PDF varsa sadece dosyayı gösterir."""
                        is_mac = (sys.platform == "darwin")
                        
                        for i, num in enumerate(targets_list):
                            clean_num = ''.join(filter(str.isdigit, num))
                            if len(clean_num) == 10 and clean_num.startswith("5"): clean_num = "90" + clean_num
                            elif len(clean_num) == 11 and clean_num.startswith("0"): clean_num = "9" + clean_num
                            
                            encoded_msg = quote(message_content)
                            
                            if is_mac:
                                # 1. URL ile mesajı yükle
                                subprocess.run(["open", f"whatsapp://send?phone={clean_num}&text={encoded_msg}"])
                                
                                if pdf_file:
                                    # PDF Modu: Dosyayı göster
                                    try:
                                        subprocess.run(["open", "-R", pdf_file])
                                    except: pass
                                else:
                                    # Metin Modu: Otomatik Gönder (Akıllı Odaklanma)
                                    # 1. 'open' komutu sonrası aktifleşen uygulamayı (WhatsApp) tespit et.
                                    # 2. Bekleme süresinden sonra o uygulama hala aktif mi kontrol et.
                                    # 3. Değilse (kullanıcı başka yere tıkladıysa), tekrar o uygulamayı öne getir.
                                    # 4. Güvenli bir şekilde Enter tuşunu gönder.
                                    script = """
                                    delay 0.5
                                    tell application "System Events"
                                        set activeApp to name of first application process whose frontmost is true
                                    end tell
                                    delay 1.5
                                    tell application "System Events"
                                        if (name of first application process whose frontmost is true) is not activeApp then
                                            tell application activeApp to activate
                                            delay 0.5
                                        end if
                                        key code 36
                                        delay 0.5
                                        key code 36
                                    end tell
                                    """
                                    subprocess.run(["osascript", "-e", script])
                                
                            else:
                                if pdf_file and os.path.exists(pdf_file):
                                    try:
                                        if sys.platform == "win32":
                                            subprocess.run(f'explorer /select,"{os.path.abspath(pdf_file)}"', shell=True)
                                        else:
                                            subprocess.run(["xdg-open", os.path.dirname(os.path.abspath(pdf_file))])
                                    except Exception:
                                        pass
                                import webbrowser
                                webbrowser.open(f"https://web.whatsapp.com/send?phone={clean_num}&text={encoded_msg}")
                                time.sleep(1.0)

                    # ---------------------------------------------------------
                    # BRANCH 1: PDF REPORT
                    # ---------------------------------------------------------
                    if clicked == bt_pdf:
                        # Trend Metni
                        trend_text = "⚖️ İstikrarımızı koruyoruz."
                        diff = w_success - prev_success
                        if w_given > 0 and prev_given > 0:
                            if diff > 5: trend_text = f"📈 Yükselişteyiz! (+%{diff})"
                            elif diff < -5: trend_text = f"📉 Biraz düşüş var. (-%{abs(diff)})"

                        # HTML Content Generation
                        html_content = f"""
                        <html>
                        <head>
                            <meta charset="utf-8">
                            <style>
                                body {{ font-family: Helvetica, Arial, sans-serif; color: #333; }}
                                h1 {{ color: #2c3e50; font-size: 22pt; margin: 0; }}
                                h2 {{ color: #7f8c8d; font-size: 14pt; margin-top: 5px; font-weight: normal; }}
                                .card {{ background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
                                .stat-val {{ font-size: 28pt; font-weight: bold; color: #2c3e50; }}
                                .stat-lbl {{ font-size: 10pt; color: #7f8c8d; text-transform: uppercase; letter-spacing: 1px; }}
                                table {{ width: 100%; border-collapse: collapse; }}
                                th {{ text-align: left; padding: 8px; background-color: #e9ecef; color: #495057; font-size: 9pt; }}
                                td {{ padding: 8px; border-bottom: 1px solid #eee; font-size: 10pt; }}
                            </style>
                        </head>
                        <body>
                            <div style="text-align:center; padding-bottom: 20px; border-bottom: 2px solid #3498db;">
                                <h1>🎓 Gelişim Raporu</h1>
                                <h2>{ogr_ad}</h2>
                                <div style="font-size: 9pt; color: #95a5a6; margin-top: 5px;">{time.strftime('%d.%m.%Y')}</div>
                            </div>
                            <br>
                            <div class="card">
                                <table width="100%">
                                    <tr>
                                        <td width="50%" align="center" style="border:none;">
                                            <div class="stat-val" style="color:{'#27ae60' if w_success>=80 else '#e67e22' if w_success<50 else '#2980b9'}">%{w_success}</div>
                                            <div class="stat-lbl">Haftalık Başarı</div>
                                        </td>
                                        <td width="50%" align="center" style="border:none; border-left: 1px solid #ddd;">
                                            <div class="stat-val">{w_done}/{w_given}</div>
                                            <div class="stat-lbl">Tamamlanan Görev</div>
                                        </td>
                                    </tr>
                                </table>
                                <div style="text-align:center; margin-top:10px; font-style:italic; color:#555;">{trend_text}</div>
                            </div>
                            <h3>🎯 Haftanın Odağı</h3>
                            <ul>
                        """
                        if focus_subjects:
                            for sub, cnt in focus_subjects:
                                share = int((cnt/w_given)*100) if w_given > 0 else 0
                                html_content += f"<li><b>{sub}</b> (%{share} yoğunluk)</li>"
                        else:
                            html_content += "<li>Genel Tekrar</li>"
                        
                        html_content += "</ul><h3>📂 Ders Detayları</h3><table><tr><th>Ders</th><th>Durum</th><th>%</th></tr>"
                        
                        if subject_books:
                            for sub in sorted(subject_books.keys()):
                                html_content += f"<tr><td colspan='3' style='background-color:#f1f5f9; font-weight:bold;'>📌 {sub}</td></tr>"
                                for b_name, b_succ in subject_books[sub]:
                                    color = "#2ecc71" if b_succ >= 80 else "#f1c40f" if b_succ >= 50 else "#e74c3c"
                                    html_content += f"<tr><td>{b_name}</td><td><div style='width:{b_succ}px;height:5px;background:{color};'></div></td><td>%{b_succ}</td></tr>"
                        
                        html_content += "</table></body></html>"
                        
                        # Gerekli Importlar
                        from ui.common_pdf import save_html_as_pdf

                        if not save_html_as_pdf:
                            QMessageBox.warning(table, "Hata", "PDF desteği yok.")
                            return
                        
                        desktop = os.path.expanduser("~/Desktop")
                        folder = os.path.join(desktop, "YKS_Raporlar")
                        os.makedirs(folder, exist_ok=True)
                        pdf_filename = f"Rapor_{ogr_ad.replace(' ','_')}.pdf"
                        pdf_path = os.path.join(folder, pdf_filename)
                        
                        save_html_as_pdf(html_content, pdf_path)
                        
                        if not os.path.exists(pdf_path):
                            QMessageBox.critical(table, "Hata", "PDF oluşturulamadı.")
                            return
                            
                        # PDF Mesajı
                        pdf_msg = "Sayın Veli, detaylı gelişim raporu ektedir. 📎"
                        
                        dlg = WhatsAppGonderDialog(targets, pdf_msg, table)
                        if dlg.exec():
                            # Kullanıcıya bilgi ver
                            if sys.platform == "darwin":
                                info = QMessageBox(table)
                                info.setWindowTitle("PDF Hazır")
                                info.setText(f"Rapor oluşturuldu:\n📂 {pdf_filename}\n\n1. WhatsApp açılacak.\n2. Rapor klasörü açılacak.\n3. Lütfen DOSYAYI WhatsApp'a SÜRÜKLEYİP gönderin.")
                                info.exec()
                            
                            send_via_whatsapp(dlg.secili_alicilar(), dlg.mesaj(), pdf_path)
                        return

                    # ---------------------------------------------------------
                    # BRANCH 2: TEXT REPORT
                    # ---------------------------------------------------------
                    elif clicked == bt_text:
                        # Grafik Fonksiyonu (Eski Yeşil Kareler)
                        def gen_green_bar(p):
                            f = int(10 * (p / 100))
                            return "🟩" * f + "⬜" * (10 - f)
                            
                        lines = []
                        lines.append(f"Merhaba Sayın Velimiz, ben {ogr_ad} öğrencinizin Eğitim Koçu. 👋")
                        lines.append(f"\n📊 *HAFTALIK GELİŞİM RAPORU*")
                        lines.append("▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬")
                        
                        icon = "🏆" if w_success >= 90 else ("⚠️" if w_success < 50 else "✅")
                        lines.append(f"{icon} *Başarı Oranı:* %{w_success}")
                        lines.append(f"{gen_green_bar(w_success)} ({w_done}/{w_given} Görev)")
                        
                        if focus_subjects:
                            lines.append(f"\n🎯 *Odaklanılan Dersler:*")
                            for s, c in focus_subjects:
                                share = int((c / w_given) * 100) if w_given > 0 else 0
                                lines.append(f" • {s} (%{share})")
                                
                        if subject_books:
                            lines.append(f"\n📚 *Detaylar:*")
                            for sub in sorted(subject_books.keys()):
                                lines.append(f"📌 *{sub}*")
                                for bn, bs in subject_books[sub]:
                                    bs_icon = "🔹" if bs < 100 else "✅"
                                    lines.append(f"   {bs_icon} {bn}: %{bs}")
                                    
                        lines.append("▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬")
                        
                        text_msg = "\n".join(lines)
                        
                        dlg_txt = WhatsAppGonderDialog(targets, text_msg, table)
                        if dlg_txt.exec():
                             # Helper function call (PDF None)
                             send_via_whatsapp(dlg_txt.secili_alicilar(), dlg_txt.mesaj(), None)

                except Exception as e:
                    traceback.print_exc()
                    QMessageBox.critical(table, "Hata", f"Rapor hatası: {str(e)}")




            act_parent_report.triggered.connect(do_parent_report)
            
            menu.exec(table.viewport().mapToGlobal(pos))

        table.customContextMenuRequested.connect(_popup_menu)

    # --------------------------------------------------------------------------



    #f

    # ---------------- Verilen Ödevler etkileşimi ----------------

    def _tik_degisti(self, it, tablo, ders: str):
        """Konulardaki checkbox değişince sağdaki 'verilen' tablosunu senkronize eder."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTableWidgetItem

        if it is None or it.column() == 0:
            return
        if not (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        if getattr(self, "_in_verilen_update", False) or (it is None) or it.column() == 0:
            return

        konu_item = tablo.item(it.row(), 0)
        if not konu_item:
            return
        konu_ad = (konu_item.text() or "").strip()

        hdr = tablo.horizontalHeaderItem(it.column())
        if not hdr:
            return
        kitap_ad = (hdr.text() or "").strip()

        def _vtext(r, c):
            cell = self.verilen.item(r, c)
            return (cell.text() if cell and cell.text() is not None else "").strip()

        row_to_remove = None
        for r in range(self.verilen.rowCount()):
            if (_vtext(r, 0) == ders and _vtext(r, 1) == kitap_ad and _vtext(r, 2) == konu_ad):
                row_to_remove = r
                break

        is_checked = (it.checkState() == Qt.CheckState.Checked)

        self._in_verilen_update = True
        sort_on = self.verilen.isSortingEnabled()
        self.verilen.setSortingEnabled(False)
        self.verilen.blockSignals(True)
        try:
            if is_checked:
                if row_to_remove is None:
                    r = self.verilen.rowCount()
                    self.verilen.insertRow(r)
                    self.verilen.setItem(r, 0, QTableWidgetItem(ders))
                    self.verilen.setItem(r, 1, QTableWidgetItem(kitap_ad))
                    self.verilen.setItem(r, 2, QTableWidgetItem(konu_ad))
                    dk_val = self._tahmini_sure(ders, kitap_ad, konu_ad)
                    def_dk = self._get_default_sure()
                    self.verilen.setItem(r, 3, QTableWidgetItem(str(dk_val if dk_val and int(dk_val) > 0 else def_dk)))
                    self.verilen.setItem(r, 4, QTableWidgetItem(""))
            else:
                if row_to_remove is not None:
                    self.verilen.removeRow(row_to_remove)
        finally:
            self.verilen.blockSignals(False)
            self.verilen.setSortingEnabled(sort_on)
            self._in_verilen_update = False

        try:
            self._toplam_sure_guncelle()
        except Exception:
            pass

    def _get_default_sure(self) -> int:
        if hasattr(self, "spVarsayilanSure"):
            try:
                v = int(self.spVarsayilanSure.value())
                if v > 0:
                    return v
            except Exception:
                pass
        return 45

    def _on_varsayilan_sure_changed(self, val: int):
        try:
            from utils.settings import ayar_set
            ayar_set("default_homework_duration_dk", str(val))
        except Exception:
            pass

    def _apply_default_duration_to_all(self):
        val = self._get_default_sure()
        count = self.verilen.rowCount()
        if count == 0:
            return
        from PyQt6.QtWidgets import QTableWidgetItem
        self.verilen.blockSignals(True)
        try:
            for r in range(count):
                it = self.verilen.item(r, 3)
                if it is None:
                    it = QTableWidgetItem(str(val))
                    self.verilen.setItem(r, 3, it)
                else:
                    it.setText(str(val))
        finally:
            self.verilen.blockSignals(False)
        self._toplam_sure_guncelle()

    def _vtext(self, r, c):
        it = self.verilen.item(r, c)
        return it.text() if it else ""

    def _ensure_vcell(self, r, c, text=""):
        from PyQt6.QtWidgets import QTableWidgetItem
        it = self.verilen.item(r, c)
        if it is None:
            it = QTableWidgetItem(str(text) if text is not None else "")
            self.verilen.setItem(r, c, it)
        else:
            it.setText(str(text) if text is not None else "")
        return it

    def _verilen_satir_ekle(self, ders, kitap, konu, sure='', aciklama=''):
        k = self._row_key(ders, kitap, konu)
        for row in getattr(self, "_verilen_rows", []):
            if self._row_key(row.get('ders'), row.get('kitap'), row.get('konu')) == k:
                return
        sure_val = str(sure or '').strip()
        if not sure_val or sure_val == '0':
            dk_val = self._tahmini_sure(ders, kitap, konu)
            sure_val = str(dk_val if dk_val and int(dk_val) > 0 else self._get_default_sure())
        self._verilen_rows.append({
            'ders': ders or '',
            'kitap': kitap or '',
            'konu': konu or '',
            'sure': sure_val,
            'aciklama': aciklama or ''
        })
        self._refresh_verilen_table()

    def _kilitle_ve_boya(self, tablo, row, col, renk, kilitli=True):
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt
        it = tablo.item(row, col)
        if it is None:
            it = QTableWidgetItem(" ")
            tablo.setItem(row, col, it)
        it.setBackground(renk)
        if kilitli:
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsUserCheckable)
        else:
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)

    # ---------------- Kitap / Kayıt / Kontrol ----------------

    def _kitap_dialog(self):
        from PyQt6.QtWidgets import QMessageBox
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Eksik", "Öğrenci seçiniz.")
            return
        idx = self.tabs.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Eksik", "Ders sekmesi yok.")
            return
        baslik = self.tabs.tabText(idx)
        # Rozetleri, emojileri ve yüzdeleri temizle
        clean_baslik = re.sub(r'[🔴🟡]\s*\d+', '', baslik)
        clean_baslik = re.sub(r'\(?\s*%\s*\d+\s*\)?', '', clean_baslik)
        clean_baslik = re.sub(r'[^\w\s]', '', clean_baslik, flags=re.UNICODE).strip()
        ders = clean_baslik.lower().replace(" ", "_")

        def ogrenci_provider():
            con = db.get_conn()
            return ogr_id, db.listele_ogrenciler(con, aktif_yalniz=True)

        dlg = KitapDialog(ogrenci_provider, ders, self)
        res = dlg.exec()
        
        # Kitap ekleme veya silme yapıldıysa sadece o ders sekmesini anında yenile (0.05 sn)
        # Tüm sekmeleri silip yeniden oluşturan yavaş 'Yükleniyor' penceresini çalıştırmaz
        if getattr(dlg, "_degisiklik_oldu", False) or res == QDialog.DialogCode.Accepted:
            son_ders = getattr(dlg, "son_ders", None) or ders
            self._refresh_single_lesson_tab(ogr_id, son_ders)

    def _refresh_single_lesson_tab(self, ogr_id: int, ders: str):
        """
        Kitap ekleme/silme sonrası sadece ilgili ders sekmesini anında (~30 ms) yeniler.
        Tüm sekmeleri silip yeniden oluşturan yavaş ve kullanıcıyı bekleten
        'Öğrenci Bilgileri Yükleniyor' penceresini açmaz.
        """
        if not ogr_id or not ders:
            return
        try:
            norm_target = ders.strip().lower().replace(" ", "_")
            target_idx = -1
            for i in range(self.tabs.count()):
                t_txt = self.tabs.tabText(i)
                tc = re.sub(r'[🔴🟡]\s*\d+', '', t_txt)
                tc = re.sub(r'\(?\s*%\s*\d+\s*\)?', '', tc)
                tc = re.sub(r'[^\w\s]', '', tc, flags=re.UNICODE).strip().lower().replace(" ", "_")
                if tc == norm_target:
                    target_idx = i
                    break

            if target_idx >= 0:
                # Yeni tabloyu ve sekme widget'ını anında oluştur
                w, tablo = self._ders_tab_olustur(ogr_id, ders)
                self._ders_tablolari[ders] = tablo

                meta = LESSON_META.get(ders.strip().lower(), {})
                icon = meta.get("icon", "📘")
                clean_title = meta.get("title", ders.replace('_', ' ').title())
                baslik = f"{icon} {clean_title}"

                # Eski sekmenin yerine yerleştir
                self.tabs.removeTab(target_idx)
                self.tabs.insertTab(target_idx, w, baslik)
                self.tabs.setTabToolTip(target_idx, f"{clean_title} Dersi Konu ve Kitap Matrisi")
                try:
                    bar = self.tabs.tabBar()
                    bar.setTabData(target_idx, {"base": baslik, "key": ders.strip().lower()})
                except Exception:
                    pass
                self.tabs.setCurrentIndex(target_idx)

                # Gecikmiş ödevleri ve rozetleri tazele
                try:
                    self._mark_overdue_cells(ogr_id)
                except Exception:
                    pass
                try:
                    self._update_overdue_badges(ogr_id)
                except Exception:
                    pass
            else:
                # Sekme bulunamadıysa (yeni bir ders eklenmişse) güvenli tam yenileme
                self._bilgileri_getir()
        except Exception as e:
            print(f"Hızlı sekme yenileme hatası: {e}, tam yenilemeye geçiliyor.")
            self._bilgileri_getir()

    def _kaydet_kume(self):
        """Sağdaki 'verilen' tablosunu yeni bir ödev kümesi olarak KAYDET
           veya VAR OLAN bir kümeye EKLE."""
        from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import QDate

        def _v(r, c) -> str:
            it = self.verilen.item(r, c)
            return (it.text() if it and it.text() is not None else "").strip()

        def _as_int(s, dflt=0):
            try:
                return int(str(s).strip())
            except Exception:
                return dflt

        try:
            valid_ders_adlari = set()
            for lst in GRUP_DERSLER.values():
                valid_ders_adlari.update(lst)
        except Exception:
            valid_ders_adlari = None

        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Eksik", "Öğrenci seçiniz.")
            return
        if self.verilen.rowCount() == 0:
            QMessageBox.information(self, "Bilgi", "Verilecek ödev bulunmuyor.")
            return

        secim = self._kume_kaydet_modu_secimi(ogr_id)
        if secim is None:
            return  # kullanıcı vazgeçti

        con = db.get_conn()
        cur = con.cursor()
        try:
            # hedef kume_id
            if secim["mode"] == "yeni":
                verilis = QDate.currentDate().toString("yyyy-MM-dd")
                bitis = (secim.get("bitis_tarihi")
                         if secim.get("bitis_guncelle")
                         else self.dtpBitis.date().toString("yyyy-MM-dd"))
                cur.execute(
                    "INSERT INTO odev_kume(ogrenci_id, verilis_tarihi, bitis_tarihi) VALUES(?,?,?)",
                    (ogr_id, verilis, bitis)
                )
                kume_id = cur.lastrowid
            else:
                kume_id = int(secim.get("kume_id") or 0)
                if kume_id <= 0:
                    QMessageBox.warning(self, "Eksik", "Var olan küme seçilmedi.")
                    return
                if secim.get("bitis_guncelle"):
                    cur.execute("UPDATE odev_kume SET bitis_tarihi=? WHERE id=?",
                                (secim.get("bitis_tarihi"), kume_id))

            eklendi = 0
            for r in range(self.verilen.rowCount()):
                ders = _v(r, 0)
                kitap = _v(r, 1)
                konu = _v(r, 2)
                sure = _as_int(_v(r, 3), 0)
                acik = _v(r, 4)

                if not ders or not kitap or not konu:
                    continue
                if valid_ders_adlari is not None and ders not in valid_ders_adlari:
                    continue

                row = con.execute(f"SELECT id FROM {ders} WHERE konu=?", (konu,)).fetchone()
                konu_id = int(row["id"]) if row and row["id"] is not None else 0

                cur.execute(
                    """INSERT OR IGNORE INTO odev
                       (kume_id, ogrenci_id, ders, konu_id, konu_ad, kitap_ad, saat_dk, aciklama, durum)
                       VALUES(?,?,?,?,?,?,?,?,'devam')""",
                    (kume_id, ogr_id, ders, konu_id, konu, kitap, sure, acik)
                )
                eklendi += (cur.rowcount or 0) if hasattr(cur, "rowcount") else 0

            con.commit()

            if secim["mode"] == "yeni":
                QMessageBox.information(self, "Kaydedildi", f"Yeni ödev kümesi #{kume_id} oluşturuldu.")
            else:
                QMessageBox.information(self, "Güncellendi", f"Ödev kümesi #{kume_id} içine eklemeler yapıldı.")

            try:
                sarı = QColor("#FFF59D")
                if hasattr(self, "_ders_tablolari"):
                    for r in range(self.verilen.rowCount()):
                        ders = _v(r, 0)
                        kitap = _v(r, 1)
                        konu = _v(r, 2)
                        if not ders or not kitap or not konu:
                            continue
                        tablo = self._ders_tablolari.get(ders)
                        if not tablo:
                            continue
                        hedef_satir = -1
                        for rr in range(tablo.rowCount()):
                            it = tablo.item(rr, 0)
                            if it and (it.text() or "").strip().lower() == konu.lower():
                                hedef_satir = rr
                                break
                        if hedef_satir < 0:
                            continue
                        hedef_sutun = -1
                        for cc in range(1, tablo.columnCount()):
                            h = tablo.horizontalHeaderItem(cc)
                            if h and (h.text() or "").strip().lower() == kitap.lower():
                                hedef_sutun = cc
                                break
                        if hedef_sutun < 0:
                            continue

                        cell = tablo.item(hedef_satir, hedef_sutun)
                        if cell is None:
                            from PyQt6.QtWidgets import QTableWidgetItem
                            cell = QTableWidgetItem(" ")
                            tablo.setItem(hedef_satir, hedef_sutun, cell)
                        cell.setCheckState(Qt.CheckState.Checked)
                        cell.setBackground(sarı)
                        cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsUserCheckable)
            except Exception:
                pass

        except Exception as e:
            try:
                con.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Hata", f"Ödev kümesine kaydedilemedi:\n{e}")

    def _odev_kontrol(self):
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QTimer
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Eksik", "Öğrenci seçiniz.")
            return

        dlg = OdevKontrolDialog(ogr_id, self)

        # Diyalog açıkken periyodik senkron
        try:
            if getattr(self, "_kontrol_sync_timer", None) is None:
                self._kontrol_sync_timer = QTimer(self)
                self._kontrol_sync_timer.setInterval(600)  # 0.6 sn
                self._kontrol_sync_timer.setSingleShot(False)
                if hasattr(self, "_senkronize_odev_durumlari"):
                    self._kontrol_sync_timer.timeout.connect(self._senkronize_odev_durumlari)
            if hasattr(self, "_kontrol_sync_timer"):
                self._kontrol_sync_timer.start()
        except Exception:
            pass

        kod = dlg.exec()  # kapandıktan sonra devam

        try:
            if getattr(self, "_kontrol_sync_timer", None):
                self._kontrol_sync_timer.stop()
        except Exception:
            pass
        try:
            if hasattr(self, "_senkronize_odev_durumlari"):
                self._senkronize_odev_durumlari()
        except Exception:
            pass

        # Yapılmayanlar geri aktarıldıysa Verilen'e ekle (kod==2)
        if kod == 2:
            aktar = dlg.property("aktar_list") or []

            def _verilen_var_mi(ders, kitap, konu) -> bool:
                """
                Verilen tablosunda aynı (ders, kitap, konu) var mı?
                Varsa ama süre/açıklama boşsa tekrar eklemeye izin verir.
                """
                try:
                    mevcut_idx = -1
                    for r in range(self.verilen.rowCount()):
                        d_it = self.verilen.item(r, 0)
                        k_it = self.verilen.item(r, 1)
                        n_it = self.verilen.item(r, 2)
                        if not (d_it and k_it and n_it):
                            continue
                        if (d_it.text() == ders and k_it.text() == kitap and n_it.text() == konu):
                            mevcut_idx = r
                            break

                    if mevcut_idx >= 0:
                        sure_it = self.verilen.item(mevcut_idx, 3)
                        acik_it = self.verilen.item(mevcut_idx, 4)
                        sure_bos = (not sure_it or not sure_it.text().strip())
                        acik_bos = (not acik_it or not acik_it.text().strip())
                        if sure_bos or acik_bos:
                            return False
                        return True
                except Exception:
                    pass
                return False

            eklendi = 0
            atlanan = []

            for item in aktar:
                ders = (item.get('ders') or "").strip()
                kitap = (item.get('kitap') or "").strip()
                konu = (item.get('konu') or "").strip()
                if not ders or not kitap or not konu:
                    continue

                tablo = self._ders_tablolari.get(ders) if hasattr(self, "_ders_tablolari") else None
                if tablo:
                    try:
                        t, r, c = self._hucre_bul(ders, kitap, konu)
                    except Exception:
                        t = r = c = None

                    if t is not None and r is not None and c is not None:
                        it = t.item(r, c)
                        if it:
                            was_blocked = False
                            try:
                                was_blocked = t.signalsBlocked()
                                t.blockSignals(True)
                            except Exception:
                                pass
                            try:
                                it.setBackground(self.palette().base())
                                it.setFlags(
                                    it.flags()
                                    | Qt.ItemFlag.ItemIsUserCheckable
                                    | Qt.ItemFlag.ItemIsEditable
                                    | Qt.ItemFlag.ItemIsEnabled
                                )
                                it.setCheckState(Qt.CheckState.Checked)
                            finally:
                                try:
                                    t.blockSignals(was_blocked)
                                except Exception:
                                    pass

                if not self._verilen_var_mi(ders, kitap, konu):
                    dk_val = 0
                    try:
                        if hasattr(self, "_tahmini_sure"):
                            dk_val = int(self._tahmini_sure(ders, kitap, konu) or 0)
                    except Exception:
                        pass
                    if dk_val <= 0:
                        dk_val = 20

                    try:
                        self._verilen_satir_ekle(ders, kitap, konu, str(dk_val), "")
                        eklendi += 1
                    except Exception:
                        try:
                            self._verilen_satir_ekle(ders, kitap, konu, '', '')
                            eklendi += 1
                        except Exception:
                            atlanan.append(f"{ders}/{kitap}/{konu} — eklenemedi")

            try:
                if hasattr(self, "_toast"):
                    msg = f"{eklendi} ödev eklendi ✅" if eklendi else "Eklenecek yeni ödev yok."
                    self._toast(msg, parent=self, msec=1600, under_widget=getattr(self, 'btnKontrol', None))
            except Exception:
                pass

        try:
            sel_id = self._secili_ogrenci_id()
            if sel_id and hasattr(self, "_update_overdue_badges"):
                self._update_overdue_badges(sel_id)
                if sel_id and hasattr(self, "_apply_global_done_for_current"):
                    self._apply_global_done_for_current()
        except Exception:
            pass

    #WİNDOWS DA CHECKBOX TIKLAMA SORUNU İÇİN
    def _verilen_var_mi(self, ders: str, kitap: str, konu: str) -> bool:
        """
        'Verilen' tablosunda aynı (ders, kitap, konu) var mı?
        Varsa ama süre/açıklama boşsa tekrar eklemeye izin verir.
        """
        try:
            mevcut_idx = -1
            for r in range(self.verilen.rowCount()):
                d_it = self.verilen.item(r, 0)
                k_it = self.verilen.item(r, 1)
                n_it = self.verilen.item(r, 2)
                if not (d_it and k_it and n_it):
                    continue
                if (d_it.text() == ders and k_it.text() == kitap and n_it.text() == konu):
                    mevcut_idx = r
                    break

            if mevcut_idx >= 0:
                sure_it = self.verilen.item(mevcut_idx, 3)
                acik_it = self.verilen.item(mevcut_idx, 4)
                sure_bos = (not sure_it or not sure_it.text().strip())
                acik_bos = (not acik_it or not acik_it.text().strip())
                if sure_bos or acik_bos:
                    return False
                return True
        except Exception:
            pass
        return False
    def _odev_kontrol(self):
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QTimer, Qt
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Eksik", "Öğrenci seçiniz.")
            return

        dlg = OdevKontrolDialog(ogr_id, self)

        # Diyalog açıkken periyodik senkron
        try:
            if getattr(self, "_kontrol_sync_timer", None) is None:
                self._kontrol_sync_timer = QTimer(self)
                self._kontrol_sync_timer.setInterval(600)  # 0.6 sn
                self._kontrol_sync_timer.setSingleShot(False)
                if hasattr(self, "_senkronize_odev_durumlari"):
                    self._kontrol_sync_timer.timeout.connect(self._senkronize_odev_durumlari)
            if hasattr(self, "_kontrol_sync_timer"):
                self._kontrol_sync_timer.start()
        except Exception:
            pass

        kod = dlg.exec()  # kapandıktan sonra devam

        # Timer kapat + son bir senkron
        try:
            if getattr(self, "_kontrol_sync_timer", None):
                self._kontrol_sync_timer.stop()
        except Exception:
            pass
        try:
            if hasattr(self, "_senkronize_odev_durumlari"):
                self._senkronize_odev_durumlari()
        except Exception:
            pass

        # Yapılmayanlar geri aktarıldıysa (kod==2) işle
        if kod == 2:
            aktar = dlg.property("aktar_list") or []
            mode = (dlg.property("aktar_mode") or "").strip().lower()  # "silmeden" / "silerek"

            # — yardımcılar: tablo konum bul —
            def _find_row_by_konu_id(table, konu_id: int) -> int:
                for r in range(table.rowCount()):
                    it0 = table.item(r, 0)
                    try:
                        if it0 and int(it0.data(Qt.ItemDataRole.UserRole)) == int(konu_id):
                            return r
                    except Exception:
                        pass
                return -1

            def _find_col_by_kitap(table, kitap_ad: str) -> int:
                for c in range(1, table.columnCount()):
                    try:
                        if table.horizontalHeaderItem(c).text() == kitap_ad:
                            return c
                    except Exception:
                        pass
                return -1

            # -------- SOLDAKİ HÜCRELER: her iki modda da tik düşür --------
            for item in aktar:
                ders = (item.get('ders') or "").strip()
                kitap = (item.get('kitap') or "").strip()
                konu_id = item.get('konu_id')
                konu_ad = (item.get('konu') or "").strip()

                table = self._ders_tablolari.get(ders) if hasattr(self, "_ders_tablolari") else None
                if not table:
                    continue

                # satır/sütun bul
                r = -1
                if konu_id is not None:
                    r = _find_row_by_konu_id(table, int(konu_id))
                if r < 0 and konu_ad:
                    for rr in range(table.rowCount()):
                        it0 = table.item(rr, 0)
                        if it0 and it0.text().strip() == konu_ad:
                            r = rr
                            break
                c = _find_col_by_kitap(table, kitap)
                if r < 0 or c < 0:
                    continue

                it = table.item(r, c)
                if it is None:
                    from PyQt6.QtWidgets import QTableWidgetItem
                    it = QTableWidgetItem("")
                    table.setItem(r, c, it)

                # flags: checkable + enabled + selectable (EDITABLE YOK)
                fl = it.flags()
                fl |= (Qt.ItemFlag.ItemIsUserCheckable |
                       Qt.ItemFlag.ItemIsEnabled |
                       Qt.ItemFlag.ItemIsSelectable)
                fl &= ~Qt.ItemFlag.ItemIsEditable
                it.setFlags(fl)

                # mod farkı: "silmeden" ise kilit rengi kalksın
                if mode == "silmeden":
                    it.setBackground(Qt.GlobalColor.transparent)

                # checked yap
                if it.data(Qt.ItemDataRole.CheckStateRole) != Qt.CheckState.Checked:
                    it.setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Checked)

                # yalnız ilgili hücreyi tazele (performans)
                try:
                    table.viewport().update(table.visualRect(table.model().index(r, c)))
                except Exception:
                    pass

            # -------- VERİLEN TABLOSU: yeni satır ekleme akışın --------
            eklendi = 0
            atlanan = []
            for item in aktar:
                ders = (item.get('ders') or "").strip()
                kitap = (item.get('kitap') or "").strip()
                konu = (item.get('konu') or "").strip()
                if not ders or not kitap or not konu:
                    continue

                if not self._verilen_var_mi(ders, kitap, konu):
                    dk_val = 0
                    try:
                        if hasattr(self, "_tahmini_sure"):
                            dk_val = int(self._tahmini_sure(ders, kitap, konu) or 0)
                    except Exception:
                        pass
                    if dk_val <= 0:
                        dk_val = 20

                    try:
                        self._verilen_satir_ekle(ders, kitap, konu, str(dk_val), "")
                        eklendi += 1
                    except Exception:
                        try:
                            self._verilen_satir_ekle(ders, kitap, konu, '', '')
                            eklendi += 1
                        except Exception:
                            atlanan.append(f"{ders}/{kitap}/{konu} — eklenemedi")

            # küçük bildirim (varsa)
            try:
                if hasattr(self, "_toast"):
                    msg = f"{eklendi} ödev eklendi ✅" if eklendi else "Eklenecek yeni ödev yok."
                    self._toast(msg, parent=self, msec=1600, under_widget=getattr(self, 'btnKontrol', None))
            except Exception:
                pass

        # rozet/overdue güncelle
        try:
            sel_id = self._secili_ogrenci_id()
            if sel_id and hasattr(self, "_update_overdue_badges"):
                self._update_overdue_badges(sel_id)
                if sel_id and hasattr(self, "_apply_global_done_for_current"):
                    self._apply_global_done_for_current()
        except Exception:
            pass





    # ---------------- AKILLI TAKVİM (YENİ) ----------------
    def _open_smart_calendar_pdf(self):
        """
        Mevcut 'Verilen' listesindeki ödevleri alıp 
        Haftalık Program (PDF) formatına dönüştüren diyalogu açar.
        """
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        from PyQt6.QtGui import QTextDocument, QPageSize
        
        # 1. Verileri Topla
        if self.verilen.rowCount() == 0:
            QMessageBox.information(self, "Bilgi", "Listede ödev yok. Lütfen önce ödev ekleyin.")
            return

        hw_list = []
        for i in range(self.verilen.rowCount()):
            if self.verilen.isRowHidden(i): continue
            
            ders = self.verilen.item(i, 0).text()
            kitap = self.verilen.item(i, 1).text()
            konu = self.verilen.item(i, 2).text()
            sure = self.verilen.item(i, 3).text()
            
            hw_list.append({
                'ders': ders,
                'kitap': kitap,
                'konu': konu,
                'sure': sure
            })
            
        # 2. Servisi Çağır
        try:
            from services.smart_calendar import SmartCalendarService
            
            s_name = self.cmbAd.currentText() + " " + self.cmbSoyad.currentText()
            
            # Kullanıcıdan Plan Notu İste (Yeni Gelişmiş Dialog)
            try:
                from ui.plan_settings_dialog import PlanSettingsDialog
                # Ders isimlerini topla (Autocomplete için)
                lessons = [x.get('ders') for x in hw_list if x.get('ders')]
                
                dlg = PlanSettingsDialog(self, lesson_names=lessons, student_name=s_name)
                if dlg.exec():
                    details = dlg.get_details()
                else:
                    return # İptal edildi
            except ImportError:
                # Fallback (Eğer dosya bir şekilde yoksa)
                from PyQt6.QtWidgets import QInputDialog
                note, ok = QInputDialog.getText(
                    self, "Plan Ayarları", 
                    "Özel durumlar (Örn: Hafta içi okul var):"
                )
                if not ok: return
                details = note

            html_content = SmartCalendarService.create_weekly_plan_pdf(s_name, hw_list, details)
            
            if not html_content:
                return

            # 3. Önizleme
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            try:
                printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
                # Yatay (Landscape) daha iyi olabilir takvim için
                printer.setPageOrientation(QPageLayout.Orientation.Landscape)
            except:
                pass

            preview = QPrintPreviewDialog(printer, self)
            preview.setMinimumSize(1100, 800)
            preview.setWindowTitle("📅 Haftalık Çalışma Programı Oluştur")
            
            def handle_print(p):
                doc = QTextDocument()
                doc.setHtml(html_content)
                try:
                    # Sayfa kenar boşlukları ayarlaması
                    # doc.setPageSize(p.pageRect(QPrinter.Unit.Point).size()) 
                    pass
                except: pass
                doc.print(p)
                
            preview.paintRequested.connect(handle_print)
            preview.exec()
            
        except ImportError:
            QMessageBox.warning(self, "Hata", "Takvim modülü yüklenemedi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Takvim oluşturulurken hata: {e}")

    # =========================
    # Part 4/7 — PDF & WhatsApp, Verilen Tablosu Filtre/Toplam, Hücre Bulucu, Yardımcılar
    # =========================

    # Bu roller Part 1/2’de tanımlı değilse güvenli varsayılan ata
    try:
        OVERDUE_FLAG_ROLE
    except NameError:
        OVERDUE_FLAG_ROLE = 0x3F10
    try:
        OVERDUE_DAYS_ROLE
    except NameError:
        OVERDUE_DAYS_ROLE = 0x3F11
    try:
        _ORG_BG_ROLE
    except NameError:
        _ORG_BG_ROLE = 0x3F12

    # ---------------- PDF & WhatsApp ----------------

    def _pdf_ayar(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox, QFileDialog

        changed = False

        # 1) Kurum adı
        mevcut = str(appset.ayar_get('kurum_adi', '') or '')
        kurum, ok = QInputDialog.getText(
            self, "Kurum Adı",
            "PDF başlığında görünecek kurum adı:",
            text=mevcut
        )
        if not ok:
            return

        if kurum != mevcut:
            appset.ayar_set('kurum_adi', kurum)
            changed = True

        # 2) Logo ister mi?
        yanit = QMessageBox.question(
            self, "Logo",
            "PDF için logo seçmek/güncellemek ister misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if yanit == QMessageBox.StandardButton.Yes:
            fn, _ = QFileDialog.getOpenFileName(
                self, "Logo Seç (PNG/JPG)", "", "Resim (*.png *.jpg *.jpeg)"
            )
            if fn:
                appset.ayar_set('logo_path', fn)
                changed = True

        # 3) Bilgilendirme
        if changed:
            QMessageBox.information(self, "Ayar", "PDF ayarları kaydedildi.")

    def _pdf_yazdir(self):
        from PyQt6.QtWidgets import QMessageBox
        # 1) Öğrenci + DB
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Eksik", "Öğrenci seçiniz.")
            return

        con = db.get_conn()
        ogr = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (ogr_id,)).fetchone()
        if not ogr:
            QMessageBox.warning(self, "Eksik", "Öğrenci bulunamadı.")
            return

        satirlar: list[dict] = []
        son_kume_id = None
        bitis_db = None

        def _ekrandan_oku():
            from PyQt6.QtWidgets import QTableWidgetItem
            rows = []
            for r in range(self.verilen.rowCount()):
                rows.append(dict(
                    Ders=self.verilen.item(r, 0).text() if self.verilen.item(r, 0) else "",
                    Kitap=self.verilen.item(r, 1).text() if self.verilen.item(r, 1) else "",
                    Konu=self.verilen.item(r, 2).text() if self.verilen.item(r, 2) else "",
                    **{"Süre (dk)": (self.verilen.item(r, 3).text() if self.verilen.item(r, 3) else "0")},
                    Açıklama=self.verilen.item(r, 4).text() if self.verilen.item(r, 4) else "",
                ))
            return rows

        # 2) Kaynak belirleme
        if self.verilen.rowCount() == 0:
            use_last = QMessageBox.question(
                self, "Kaynak",
                "Verilen ödevler listesi boş. Ödevleri son kaydedilen kümeden otomatik çekilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes

            if use_last:
                rowk = con.execute(
                    "SELECT id, bitis_tarihi FROM odev_kume WHERE ogrenci_id=? ORDER BY id DESC LIMIT 1",
                    (ogr_id,)
                ).fetchone()
                if rowk:
                    son_kume_id = rowk["id"]
                    for rr in con.execute(
                            "SELECT ders, kitap_ad, konu_ad, saat_dk FROM odev WHERE kume_id=? ORDER BY id",
                            (son_kume_id,)
                    ):
                        satirlar.append(dict(
                            Ders=rr["ders"],
                            Kitap=rr["kitap_ad"],
                            Konu=rr["konu_ad"],
                            **{"Süre (dk)": str(rr["saat_dk"] or 0)},
                            Açıklama=""
                        ))
                    bitis_db = (rowk["bitis_tarihi"] or None)
                else:
                    QMessageBox.information(self, "Bilgi", "Önceden kaydedilmiş küme bulunamadı.")
            else:
                QMessageBox.information(self, "Yazdır",
                                        "Verilen ödevler listesi boş olduğu için yazdırma iptal edildi.")
                return
        else:
            satirlar = _ekrandan_oku()

        if not satirlar:
            QMessageBox.information(self, "Yazdır", "Yazdırılacak satır bulunamadı.")
            return

        # 3) Yazdırma diyalogu
        headers = ["Ders", "Kitap", "Konu", "Süre (dk)", "Açıklama"]
        adapter = _ModelAdapter(satirlar)
        adapter._headers = headers

        dlg = ListPrintDialog(
            parent=self,
            model_adapter=adapter,
            profile=PrintProfile(org=appset.ayar_get('kurum_adi', 'Kocum'),
                                 app="YKS_LGS_HomeworkManager",
                                 key="VerilenOdevler"),
            extra_info_callback=None,
            title="Liste Yazdır"
        )

        # Öğrenci özetini ÜSTE ekle
        if son_kume_id is not None:
            dlg.apply_student_summary(con=con, ogrenci_id=ogr_id, kume_id=son_kume_id, position="top")
        else:
            try:
                bas_iso = self.dtpBaslangic.date().toString("yyyy-MM-dd")
            except Exception:
                bas_iso = ""
            try:
                bit_iso = (bitis_db or self.dtpBitis.date().toString("yyyy-MM-dd"))
            except Exception:
                bit_iso = (bitis_db or "")
            tarih_aralik = (bas_iso, bit_iso) if (bas_iso or bit_iso) else None
            dlg.apply_student_summary(con=con, ogrenci_id=ogr_id, tarih_araligi=tarih_aralik, position="top")

        try:
            dlg.chk_student_extras.setChecked(False)
        except Exception:
            pass

        dlg.resize(720, 540)
        dlg.exec()

    def _whatsapp_gonder(self):
        from PyQt6.QtWidgets import QMessageBox, QDialog
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Eksik", "Öğrenci seçiniz.")
            return

        con = db.get_conn()
        ogr = con.execute("SELECT * FROM ogrenci WHERE id=?", (ogr_id,)).fetchone()

        def _row_get(row, key, default=""):
            try:
                v = row[key]
                return v if v is not None else default
            except Exception:
                return default

        # Alıcı havuzu
        alicilar = []
        v1 = (_row_get(ogr, "veli_tel1", "") or "").strip()
        v2 = (_row_get(ogr, "veli_tel2", "") or "").strip()
        vo = (_row_get(ogr, "ogr_tel", "") or "").strip()
        if v1: alicilar.append(("Veli 1", v1))
        if v2: alicilar.append(("Veli 2", v2))
        if vo: alicilar.append(("Öğrenci", vo))
        if not alicilar:
            QMessageBox.warning(self, "Eksik", "Kayıtlı telefon bulunamadı (veli_tel1, veli_tel2, ogr_tel).")
            return

        # Sağ liste dolu mu?
        if self.verilen.rowCount() > 0:
            use_last = False
        else:
            # Boşsa sor
            use_last = QMessageBox.question(
                self, "Kaynak", "Ödevleri son kaydedilen kümeden otomatik çekilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes

        satirlar = []
        bitis_db = None
        if use_last:
            rowk = con.execute(
                "SELECT id, bitis_tarihi FROM odev_kume WHERE ogrenci_id=? ORDER BY id DESC LIMIT 1", (ogr_id,)
            ).fetchone()
            if rowk:
                for rr in con.execute(
                        "SELECT ders, kitap_ad, konu_ad, saat_dk FROM odev WHERE kume_id=? ORDER BY id", (rowk['id'],)
                ):
                    satirlar.append(
                        f"- {rr['ders']} / {rr['kitap_ad']} / {rr['konu_ad']} (Süre: {rr['saat_dk'] or 0} dk)"
                    )
                if rowk['bitis_tarihi']:
                    bitis_db = rowk['bitis_tarihi']
            else:
                QMessageBox.information(self, "Bilgi",
                                        "Önceden kaydedilmiş küme bulunamadı, ekrandaki listeden mesaj hazırlanacak.")

        if not satirlar:
            for r in range(self.verilen.rowCount()):
                ders = self.verilen.item(r, 0).text() if self.verilen.item(r, 0) else ''
                kitap = self.verilen.item(r, 1).text() if self.verilen.item(r, 1) else ''
                konu = self.verilen.item(r, 2).text() if self.verilen.item(r, 2) else ''
                sure = self.verilen.item(r, 3).text() if self.verilen.item(r, 3) else '0'
                if ders or kitap or konu:
                    satirlar.append(f"- {ders} / {kitap} / {konu} (Süre: {sure} dk)")

        if not satirlar:
            QMessageBox.information(self, "Bilgi", "Verilen Ödevler listesi boş.")
            return

        bitis = (bitis_db or self.dtpBitis.date().toString('yyyy-MM-dd'))

        # Mesajı oluştur (ayarları dikkate alır)
        mesaj = self._build_wp_message(ogr, satirlar, bitis)

        # Alıcı seçimi + düzenleme
        dlg = WhatsAppGonderDialog(alicilar, mesaj, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        secili_numaralar = dlg.secili_alicilar()
        mesaj_final = dlg.mesaj()

        if not secili_numaralar:
            QMessageBox.information(self, "WhatsApp", "Seçili alıcı yok, gönderilmedi.")
            return

        try:
            sonuc = whatsapp.whatsapp_gonder(secili_numaralar, mesaj_final)
            det = (f"Gönderildi: {len(sonuc.get('ok', []))}  |  Başarısız: {len(sonuc.get('fail', []))}\n"
                   f"Başarısız Numaralar: {', '.join(sonuc.get('fail', [])) or '-'}")
            QMessageBox.information(self, "WhatsApp", det)
        except Exception as e:
            QMessageBox.critical(self, "WhatsApp Hatası", str(e))

    # ---------------- Filtre / Kolon genişlik / Toplam süre ----------------

    def _filtre_verilen(self, *args):
        import re
        metin = (self.txtAraVerilen.text() or '')
        use_regex = self.chkRegex.isChecked()
        kol = self.cmbAraKolon.currentIndex()  # 0=Tümü
        pat = None
        if use_regex and metin:
            try:
                pat = re.compile(metin, flags=re.IGNORECASE)
            except Exception:
                pat = None

        for i in range(self.verilen.rowCount()):
            if kol == 0:
                text = " ".join([(self.verilen.item(i, c).text() if self.verilen.item(i, c) else "") for c in
                                 range(self.verilen.columnCount())])
            else:
                c = kol - 1
                text = (self.verilen.item(i, c).text() if self.verilen.item(i, c) else "")
            if use_regex and metin and pat:
                hide = (pat.search(text or "") is None)
            else:
                hide = (metin.lower() not in (text or '').lower()) if metin else False
            self.verilen.setRowHidden(i, hide)
        self._toplam_sure_guncelle()

    def _verilen_kolon_anahtar(self):
        return "verilen_kolon_genislik"

    def _yukle_verilen_kolon_genislik(self):
        try:
            arr = appset.ayar_get(self._verilen_kolon_anahtar(), [])
            if isinstance(arr, list) and arr:
                for i, w in enumerate(arr):
                    try:
                        self.verilen.setColumnWidth(i, int(w))
                    except Exception:
                        pass
        except Exception:
            pass

    def _kaydet_verilen_kolon_genislik(self, *args):
        try:
            arr = [self.verilen.columnWidth(i) for i in range(self.verilen.columnCount())]
            appset.ayar_set(self._verilen_kolon_anahtar(), arr)
        except Exception:
            pass

    def _toplam_sure_guncelle(self):
        top = 0
        count = 0
        for i in range(self.verilen.rowCount()):
            if self.verilen.isRowHidden(i):
                continue
            try:
                txt = (self.verilen.item(i, 3).text() or "").strip()
                top += int(txt) if txt else 0
                count += 1
            except Exception:
                pass

        # Saat ve dakika formatı
        if top >= 60:
            saat = top // 60
            kalan_dk = top % 60
            saat_str = f"{saat} sa {kalan_dk} dk" if kalan_dk > 0 else f"{saat} sa"
            sure_str = f"Toplam: {top} dk ({saat_str}) • {count} Görev"
        elif top > 0:
            sure_str = f"Toplam: {top} dk • {count} Görev"
        else:
            sure_str = f"Toplam: 0 dk • {count} Görev" if count > 0 else "Toplam: 0 dk (0 Görev)"

        self.lblTopSure.setText(sure_str)
        hedef = self.spHedefSure.value()
        if hedef and top > hedef:
            self.lblTopSure.setStyleSheet("color:#dc2626;font-weight:bold;")
        else:
            self.lblTopSure.setStyleSheet("color:#1e293b;font-weight:bold;")
            
        # --- YENİ: Yük Göstergesi Güncelle ---
        if hasattr(self, "progWorkload"):
             limit_weekly = (self.spHedefSure.value() or 90) * 7
             perc = int((top / limit_weekly) * 100) if limit_weekly > 0 else 0
             self.progWorkload.setValue(min(100, perc))
             
             # Renk Skalası
             if perc > 110:
                 self.progWorkload.setStyleSheet("QProgressBar { border:1px solid #c0392b; border-radius:7px; background:#fadbd8; } QProgressBar::chunk { background-color: #e74c3c; border-radius:7px; }")
             elif perc > 85:
                 self.progWorkload.setStyleSheet("QProgressBar { border:1px solid #d35400; border-radius:7px; background:#fdebd0; } QProgressBar::chunk { background-color: #f39c12; border-radius:7px; }")
             else:
                 self.progWorkload.setStyleSheet("QProgressBar { border:1px solid #27ae60; border-radius:7px; background:#ecf0f1; } QProgressBar::chunk { background-color: #2ecc71; border-radius:7px; }")
            
        # Akıllı Yük Analizi Tetikle
        self._update_load_analysis(top, count)

    def _update_load_analysis(self, total_min: int, task_count: int = 0):
        """Ödev yükünü ve ders dağılımını analiz edip lblLoadAnalysis'e yazar."""
        if not hasattr(self, 'lblLoadAnalysis'):
            return

        visible_rows = [i for i in range(self.verilen.rowCount()) if not self.verilen.isRowHidden(i)]
        actual_count = task_count or len(visible_rows)

        # 0 Görev / Sıfır Ödev durumu
        if actual_count == 0 or total_min == 0:
            self.lblLoadAnalysis.setText(" |  📋 Henüz Ödev Eklenmedi  |  —")
            self.lblLoadAnalysis.setStyleSheet("color: #94a3b8; font-weight: 500; font-size: 11px;")
            self.lblLoadAnalysis.setToolTip("Henüz ödev listesine bir görev eklenmedi.")
            return

        # 1. Yük Durumu
        hedef = getattr(self, "spHedefSure", None)
        hedef_val = hedef.value() if hedef else 90

        if total_min > 300:
            load_status = f"⚠️ Aşırı Yoğun ({round(total_min/60, 1)} sa)"
        elif total_min > 180:
            load_status = f"⚡ Yoğun ({round(total_min/60, 1)} sa)"
        elif total_min >= 60:
            load_status = "⚖️ İdeal Denge"
        else:
            load_status = "🟢 Hafif Yük"

        # 2. Alan Dağılımı ve Denge (Süre ve Adet Bazlı Analiz)
        sayisal_keys = ["matematik", "geometri", "fizik", "kimya", "biyoloji", "fen", "mat"]
        sozel_keys = ["türkçe", "turkce", "edebiyat", "tarih", "coğrafya", "cografya", "felsefe", "inkılap", "inkilap", "din", "ingilizce", "dil", "sosyal", "paragraf"]

        dk_say, dk_soz, dk_diger = 0, 0, 0
        cnt_say, cnt_soz, cnt_diger = 0, 0, 0

        for i in visible_rows:
            ders = (self.verilen.item(i, 0).text() or "").lower()
            try:
                dk = int((self.verilen.item(i, 3).text() or "0").strip())
            except Exception:
                dk = 0
            if dk <= 0:
                dk = 45

            if any(x in ders for x in sayisal_keys):
                dk_say += dk
                cnt_say += 1
            elif any(x in ders for x in sozel_keys):
                dk_soz += dk
                cnt_soz += 1
            else:
                dk_diger += dk
                cnt_diger += 1

        total_analyzed = dk_say + dk_soz + dk_diger
        if total_analyzed > 0:
            pct_say = int(round((dk_say / total_analyzed) * 100))
            pct_soz = int(round((dk_soz / total_analyzed) * 100))
            pct_diger = max(0, 100 - pct_say - pct_soz)

            if pct_say >= 70:
                balance = f"🧮 %{pct_say} Sayısal Ağırlıklı"
                badge_color = "#2563eb"
            elif pct_soz >= 70:
                balance = f"📚 %{pct_soz} Sözel Ağırlıklı"
                badge_color = "#d97706"
            elif pct_say >= 55:
                balance = f"⚖️ Dengeli (🧮%{pct_say} Say • 📚%{pct_soz} Söz)"
                badge_color = "#059669"
            elif pct_soz >= 55:
                balance = f"⚖️ Dengeli (📚%{pct_soz} Söz • 🧮%{pct_say} Say)"
                badge_color = "#059669"
            else:
                balance = f"⚖️ Dengeli Dağılım (%{pct_say} S / %{pct_soz} S)"
                badge_color = "#059669"
        else:
            balance = "—"
            badge_color = "#64748b"

        self.lblLoadAnalysis.setText(f" |  {load_status}  |  {balance}")
        self.lblLoadAnalysis.setStyleSheet(f"color: {badge_color}; font-weight: 600; font-size: 11px;")

        tooltip_lines = [
            f"📊 Ödev Dağılım Analizi:",
            f"• Toplam Görev: {actual_count} adet",
            f"• Toplam Süre: {total_min} dk ({round(total_min/60, 1)} saat)",
            f"• Günlük Hedef: {hedef_val} dk",
            f"• Sayısal: {cnt_say} ödev ({dk_say} dk, %{pct_say if total_analyzed else 0})",
            f"• Sözel: {cnt_soz} ödev ({dk_soz} dk, %{pct_soz if total_analyzed else 0})"
        ]
        if dk_diger > 0:
            tooltip_lines.append(f"• Diğer / Genel: {cnt_diger} ödev ({dk_diger} dk, %{pct_diger})")
        self.lblLoadAnalysis.setToolTip("\n".join(tooltip_lines))

    # ---------------- Hücre bulucu (ödev kontrol aktarımı için) ----------------

    def _hucre_bul(self, ders_key: str, kitap: str, konu: str):
        tablo = getattr(self, "_ders_tablolari", {}).get(ders_key)
        if not tablo:
            return None, None, None
        r = next((i for i in range(tablo.rowCount())
                  if (tablo.item(i, 0) and (konu or '').lower() in (tablo.item(i, 0).text() or '').lower())), -1)
        if r < 0:
            return None, None, None
        c = next((j for j in range(1, tablo.columnCount())
                  if (tablo.horizontalHeaderItem(j) and (tablo.horizontalHeaderItem(j).text() or '').lower() ==
                      (kitap or '').lower())), -1)
        if c < 0:
            return None, None, None
        return tablo, r, c

    # ---------------- Yardımcılar ----------------

    def _input_text(self, title, label, text):
        from PyQt6.QtWidgets import QInputDialog
        return QInputDialog.getText(self, title, label, text=text)

    def _temizle_verilen(self):
        """Sağdaki 'Verilen Ödevler' tablosunu temizler."""
        from PyQt6.QtWidgets import QMessageBox
        if self.verilen.rowCount() == 0:
            return
        if QMessageBox.question(
                self, "Temizle", "Verilen ödevler listesini temizle?"
        ) == QMessageBox.StandardButton.Yes:
            self.verilen.setRowCount(0)
            try:
                self._toplam_sure_guncelle()
            except Exception:
                pass

    def _cell_text(self, row: int, col: int, default: str = '') -> str:
        """Verilen tablosundan güvenli metin okur."""
        it = self.verilen.item(row, col)
        return (it.text().strip() if (it and it.text() is not None) else default)

    def _cell_int(self, row: int, col: int, default: int = 0) -> int:
        """Verilen tablosundan güvenli int okur."""
        try:
            s = self._cell_text(row, col, '')
            return int(s) if s != '' else default
        except Exception:
            return default

    def _row_key(self, ders, kitap, konu):
        return (ders or '').strip(), (kitap or '').strip(), (konu or '').strip()

    def _refresh_verilen_table(self):
        """self._verilen_rows -> self.verilen’e basar (çift tetiklenmeyi önler)."""
        from PyQt6.QtWidgets import QTableWidgetItem
        if getattr(self, "_in_verilen_update", False):
            return
        self._in_verilen_update = True
        sorting = self.verilen.isSortingEnabled()
        try:
            if sorting:
                self.verilen.setSortingEnabled(False)
            self.verilen.setRowCount(0)
            for row in getattr(self, "_verilen_rows", []):
                r = self.verilen.rowCount()
                self.verilen.insertRow(r)
                self.verilen.setItem(r, 0, QTableWidgetItem(row.get('ders', '')))
                self.verilen.setItem(r, 1, QTableWidgetItem(row.get('kitap', '')))
                self.verilen.setItem(r, 2, QTableWidgetItem(row.get('konu', '')))
                s_val = str(row.get('sure', '0')).strip()
                if not s_val or s_val == '0':
                    t_val = self._tahmini_sure(row.get('ders', ''), row.get('kitap', ''), row.get('konu', ''))
                    s_val = str(t_val if t_val and int(t_val) > 0 else 45)
                self.verilen.setItem(r, 3, QTableWidgetItem(s_val))
                self.verilen.setItem(r, 4, QTableWidgetItem(row.get('aciklama', '')))
        finally:
            if sorting:
                self.verilen.setSortingEnabled(True)
            self._in_verilen_update = False
        try:
            self._toplam_sure_guncelle()
        except Exception:
            pass

    def _uygula_aktar_listesi(self, kalan_listesi):
        """
        Kalan (aktar) ödevleri 'yeni verilecek' gibi işaretle:
        - ilgili ders tablosundaki hücrelerde kilidi kaldır,
        - arka planı sıfırla,
        - checkbox=Checked yap.
        """
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTableWidgetItem

        if not kalan_listesi:
            return

        was_locked = getattr(self, "_in_verilen_update", False)
        self._in_verilen_update = True
        try:
            for row in kalan_listesi:
                ders = (row.get("ders") or "").strip()
                kitap = (row.get("kitap") or "").strip()
                konu = (row.get("konu") or "").strip()
                tablo = getattr(self, "_ders_tablolari", {}).get(ders)
                if not tablo:
                    continue

                # konu satırı
                hedef_satir = -1
                for rr in range(tablo.rowCount()):
                    it = tablo.item(rr, 0)
                    if it and (it.text() or "").strip().lower() == konu.lower():
                        hedef_satir = rr
                        break
                if hedef_satir < 0:
                    continue

                # kitap sütunu
                hedef_sutun = -1
                for cc in range(1, tablo.columnCount()):
                    h = tablo.horizontalHeaderItem(cc)
                    if h and (h.text() or "").strip().lower() == kitap.lower():
                        hedef_sutun = cc
                        break
                if hedef_sutun < 0:
                    continue

                cell = tablo.item(hedef_satir, hedef_sutun)
                if cell is None:
                    cell = QTableWidgetItem(" ")
                    tablo.setItem(hedef_satir, hedef_sutun, cell)

                cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                cell.setBackground(Qt.GlobalColor.transparent)
                cell.setCheckState(Qt.CheckState.Checked)
        finally:
            self._in_verilen_update = was_locked

        try:
            self._toplam_sure_guncelle()
        except Exception:
            pass

    def _odev_kayit_sonucu_tamamlanan(self, tamamlanan_listesi):
        """
        Ödev Kontrol sayfasında 'Kaydet' sonrası gelen tamamlanan satırları,
        konu tablolarında YEŞİL + KİLİT yap ve gecikme işaretlerini temizle.
        """
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import Qt
        yesil = QColor("#C8E6C9")

        for row in (tamamlanan_listesi or []):
            ders = (row.get("ders") or "").strip()
            kitap = (row.get("kitap") or "").strip()
            konu = (row.get("konu") or "").strip()
            tablo = getattr(self, "_ders_tablolari", {}).get(ders)
            if not tablo:
                continue

            hedef_satir = -1
            for rr in range(tablo.rowCount()):
                it = tablo.item(rr, 0)
                if it and (it.text() or "").strip().lower() == konu.lower():
                    hedef_satir = rr
                    break
            if hedef_satir < 0:
                continue

            hedef_sutun = -1
            for cc in range(1, tablo.columnCount()):
                h = tablo.horizontalHeaderItem(cc)
                if h and (h.text() or "").strip().lower() == kitap.lower():
                    hedef_sutun = cc
                    break
            if hedef_sutun < 0:
                continue

            cell = tablo.item(hedef_satir, hedef_sutun)
            if cell:
                cell.setCheckState(Qt.CheckState.Checked)
                cell.setBackground(yesil)
                # gecikme metadata'sını temizle
                cell.setText("")
                cell.setToolTip("")
                cell.setData(OVERDUE_FLAG_ROLE, None)
                cell.setData(OVERDUE_DAYS_ROLE, None)
                # kullanıcı değiştirmesin
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsEditable)

    # =========================
    # Part 5/7 — Senkronizasyon, Overdue İşaretleme, Kaydet Modu,
    # Detaylı Rapor, Akıllı Öneriler, Filtre Diyaloğu, Haftalık Plan
    # =========================

    # Güvenli ROLE sabitleri (yoksa ata)
    try:
        OVERDUE_FLAG_ROLE
    except NameError:
        OVERDUE_FLAG_ROLE = 0x3F10
    try:
        OVERDUE_DAYS_ROLE
    except NameError:
        OVERDUE_DAYS_ROLE = 0x3F11
    try:
        _ORG_BG_ROLE
    except NameError:
        _ORG_BG_ROLE = 0x3F12

    # ------------------ Sinyal Sessize Alma Yardımcısı ------------------
    def _mute_table(self, table):
        """
        with self._mute_table(table):
            ...  # table.blockSignals(True/False) otomatik
        """
        from contextlib import contextmanager

        @contextmanager
        def _guard():
            if table is not None and hasattr(table, "blockSignals"):
                table.blockSignals(True)
                try:
                    yield
                finally:
                    table.blockSignals(False)
            else:
                # table None ise yine de çalışsın
                yield

        return _guard()
    # ------------------ Kaydet Sonrası Durum Senkronizasyonu ------------------
    def _senkronize_odev_durumlari(self):
        """
        OdevKontrol'de kaydettikten sonra soldaki konu/kitap tablolarını
        DB'deki güncel 'durum' bilgisine göre renklendirir (devam=sarı, tamam=yeşil).
        Gecikme izleri (Ng/tooltip/roller) tamam durumunda temizlenir.
        """
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QTableWidgetItem

        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            return

        sarı = QColor("#FFF59D")  # devam
        yesil = QColor("#A5D6A7")  # tamam

        con = db.get_conn()
        rows = con.execute(
            "SELECT ders, konu_id, kitap_ad, LOWER(COALESCE(durum,'')) AS d "
            "FROM odev WHERE ogrenci_id=?",
            (ogr_id,)
        ).fetchall()

        durum_map = {(r["ders"], int(r["konu_id"]), r["kitap_ad"]): r["d"] for r in rows}

        for ders_key, tablo in (getattr(self, "_ders_tablolari", {}) or {}).items():
            if not tablo:
                continue

            with self._mute_table(tablo):
                for i in range(tablo.rowCount()):
                    # konu_id, 0. sütun UserRole'de tutuluyor
                    konu_id = 0
                    it0 = tablo.item(i, 0)
                    if it0 is not None:
                        try:
                            konu_id = int(it0.data(Qt.ItemDataRole.UserRole) or 0)
                        except Exception:
                            konu_id = 0

                    for c in range(1, tablo.columnCount()):
                        hi = tablo.horizontalHeaderItem(c)
                        kitap_ad = (hi.text() if hi else "").strip()
                        it = tablo.item(i, c)
                        if it is None:
                            it = QTableWidgetItem(" ")
                            tablo.setItem(i, c, it)

                        key = (ders_key, konu_id, kitap_ad)
                        d = (durum_map.get(key) or "").lower()

                        if d in ("tamam", "yapildi"):
                            it.setCheckState(Qt.CheckState.Checked)
                            it.setBackground(yesil)
                            # gecikme izleri temizle
                            it.setText("")
                            it.setToolTip("")
                            it.setData(OVERDUE_FLAG_ROLE, None)
                            it.setData(OVERDUE_DAYS_ROLE, None)
                            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsUserCheckable)

                        elif d == "devam":
                            # gecikme olarak işaretlenmişse (OVERDUE_FLAG_ROLE), kırmızıyı koru
                            if it.data(OVERDUE_FLAG_ROLE):
                                continue
                            it.setCheckState(Qt.CheckState.Checked)
                            it.setBackground(sarı)
                            it.setText("")
                            it.setToolTip("")
                            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsUserCheckable)

                        else:
                            # kayıt yok/kapalı: kullanıcıya açık, boş
                            it.setCheckState(Qt.CheckState.Unchecked)
                            it.setBackground(Qt.GlobalColor.transparent)
                            it.setText("")
                            it.setToolTip("")
                            it.setData(OVERDUE_FLAG_ROLE, None)
                            it.setData(OVERDUE_DAYS_ROLE, None)
                            it.setFlags((it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                                        & ~Qt.ItemFlag.ItemIsEditable)
    # ------------------ Gecikmiş Hücreleri Kırmızıya Boyama ------------------
    def _mark_overdue_cells(self, ogr_id: int):
        """
        ogr_id için 'devam' durumundaki ödevleri bitiş tarihine göre kontrol eder.
        Gecikmişse hücreyi kırmızı (#F8D7DA) yapar, metne 'Xg' (gecikme gün sayısı) yazar.
        Gecikme yoksa (ve tamam değilse) sarıya çeker, izleri temizler.
        """
        if not ogr_id:
            return

        from PyQt6.QtCore import QDate, Qt
        from PyQt6.QtGui import QColor
        import re

        try:
            con = db.get_conn()
            rows = con.execute("""
                SELECT o.ders, o.konu_id, o.kitap_ad, o.durum, k.bitis_tarihi
                FROM odev AS o
                JOIN odev_kume AS k ON k.id = o.kume_id
                WHERE o.ogrenci_id=? AND LOWER(COALESCE(o.durum,''))='devam'
            """, (ogr_id,)).fetchall()
        except Exception:
            return

        today = QDate.currentDate()
        kirmizi = QColor("#F8D7DA")
        sari = QColor("#FFF59D")
        siyah = QColor("#000000")

        tab_map = getattr(self, "_ders_tablolari", {}) or {}

        def normalize(s):
             return re.sub(r'[^a-z0-9]', '', str(s or "")).lower()

        for r in rows:
            ders = (r["ders"] or "").strip()
            konu_id = int(r["konu_id"] or 0)
            kitap = (r["kitap_ad"] or "").strip()
            bitis = (r["bitis_tarihi"] or "").strip()

            t = tab_map.get(ders)
            if not t:
                # Robust lookup
                nd = normalize(ders)
                for k, tbl in tab_map.items():
                    if normalize(k) == nd:
                       t = tbl
                       break
            if not t:
                continue

            # satırı id ile bul
            row_ix = -1
            for i in range(t.rowCount()):
                it0 = t.item(i, 0)
                if it0 and int(it0.data(Qt.ItemDataRole.UserRole) or 0) == konu_id:
                    row_ix = i
                    break
            if row_ix < 0:
                continue

            # sütunu kitap adıyla bul
            col_ix = -1
            for c in range(1, t.columnCount()):
                hh = t.horizontalHeaderItem(c)
                if hh and (hh.text() or "").strip().lower() == kitap.lower():
                    col_ix = c
                    break
            if col_ix < 0:
                continue

            it = t.item(row_ix, col_ix)
            if not it:
                continue

            try:
                d_bitis = QDate.fromString(bitis, "yyyy-MM-dd")
            except Exception:
                d_bitis = QDate()

            gun = d_bitis.daysTo(today) if d_bitis.isValid() else -9999
            
            # --- Renkler ---
            # Geciken: Kırmızı
            # Yaklaşan (0..2 gün arası): Turuncumsu / Koyu Sarı (#FFECB3)
            # Normal: Sarı (#FFF59D)
            c_red = QColor("#F8D7DA")
            c_orange = QColor("#FFECB3") # veya #FFE082
            c_yellow = QColor("#FFF59D")
            c_black = QColor("#000000")

            if gun > 0:
                # GECİKEN
                it.setBackground(c_red)
                it.setForeground(c_black)
                it.setText(f"{gun}g")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setToolTip(f"Bitiş: {bitis}\nGecikme: {gun} gün")
                it.setData(OVERDUE_FLAG_ROLE, True)
                it.setData(OVERDUE_DAYS_ROLE, gun)
            elif -2 <= gun <= 0:
                # YAKLAŞAN (Bugün=0, Yarın=-1, 2gün=-2)
                if gun == 0:
                    txt = "Bugün"
                elif gun == -1:
                    txt = "Yarın"
                else: # -2
                    txt = "2 gün"
                
                # Turuncu uyarı yap
                it.setBackground(c_orange)
                it.setForeground(c_black)
                it.setText(txt)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setToolTip(f"Bitiş: {bitis}\nKalan: {abs(gun)} gün")
                it.setData(OVERDUE_FLAG_ROLE, None) 
                it.setData(OVERDUE_DAYS_ROLE, gun)
            else:
                # NORMAL (Gecikme yok, Yaklaşan değil)
                it.setData(OVERDUE_FLAG_ROLE, None)
                it.setData(OVERDUE_DAYS_ROLE, None)
                # Yeşil değilse sarı yap
                if (it.background().color().name().lower() != "#a5d6a7"):
                    it.setBackground(c_yellow)
                    it.setText("")
                    it.setToolTip("")



    def _update_overdue_badges(self, ogr_id: int):
        """
        Her ders sekmesinin başlığına:
         - Gecikmiş ödev sayısı (🔴 N)
         - Yaklaşan (0..2 gün) ödev sayısı (🟡 M)
         - İlerleme Yüzdesi (%XX)
        ekler.
        
        Format: "🔴 N 🟡 M  DERS ADI  (%XX)"
        """
        import datetime
        import re
        import db
        from PyQt6.QtWidgets import QTabBar

        if not ogr_id:
            return

        today = datetime.date.today()
        s_today = today.strftime("%Y-%m-%d")
        # Yaklaşan için üst sınır: Bugün + 2 gün
        today_plus_2 = today + datetime.timedelta(days=2)
        s_target = today_plus_2.strftime("%Y-%m-%d")

        try:
            con = db.get_conn()
            # 1) Gecikme ve Yaklaşan Sayıları
            sql = """
               SELECT 
                 LOWER(TRIM(COALESCE(d.ders,''))) AS ders_key,
                 SUM(CASE WHEN LOWER(COALESCE(d.durum,'')) NOT IN ('yapildi','tamam') 
                          AND k.bitis_tarihi < ? THEN 1 ELSE 0 END) AS cnt_overdue,
                 
                 SUM(CASE WHEN LOWER(COALESCE(d.durum,'')) NOT IN ('yapildi','tamam') 
                          AND k.bitis_tarihi >= ? AND k.bitis_tarihi <= ? THEN 1 ELSE 0 END) AS cnt_approaching
                 
               FROM odev d
               JOIN odev_kume k ON k.id = d.kume_id
               WHERE k.ogrenci_id = ?
                 AND LOWER(COALESCE(d.ders, '')) <> ''
               GROUP BY LOWER(TRIM(COALESCE(d.ders,'')))
            """
            rows = con.execute(sql, (s_today, s_today, s_target, ogr_id)).fetchall()
        except Exception as e:
            print("Badge SQL error:", e)
            rows = []

        # Normalize helper
        def normalize(s):
             tmp = str(s or "").lower()
             return re.sub(r'[^\w]', '', tmp, flags=re.UNICODE)

        # map: key -> (overdue, approaching)
        stats_map = {}
        for r in rows:
             key = normalize(r["ders_key"])
             
             c_od = int(r["cnt_overdue"] or 0)
             c_ap = int(r["cnt_approaching"] or 0)
             
             if key in stats_map:
                 o_od, o_ap = stats_map[key]
                 stats_map[key] = (o_od + c_od, o_ap + c_ap)
             else:
                 stats_map[key] = (c_od, c_ap)

             # Alternatif keyler
             for prefix in ['tyt', 'ayt', 'lgs', 'yks']:
                 if key.startswith(prefix) and len(key) > len(prefix):
                     short_key = key[len(prefix):]
                     if short_key not in stats_map:
                         stats_map[short_key] = (c_od, c_ap)

        # 2) Sekme başlıklarını güncelle
        try:
            bar: QTabBar = self.tabs.tabBar()
            for i in range(self.tabs.count()):
                curr_text = self.tabs.tabText(i)
                
                # Temizlik: Rozetleri ve önceki (%XX) ifadelerini sil
                base_title = curr_text.replace('\n', ' ')
                
                # Regex 1: Rozetler [🔴🟡] rakam
                base_title = re.sub(r'[🔴🟡]\s*\d+', '', base_title)
                
                # Regex 2: Yüzde ifadesi (%\d+) veya (% \d+) veya (%XX)
                # Yeni format: %45 (parensiz)
                # Eski format: (%45)
                # Hepsini kapsayan regex:
                # \(? \s* % \s* \d+ \s* \)?
                base_title = re.sub(r'\(?\s*%\s*\d+\s*\)?', '', base_title)
                
                base_title = re.sub(r'\s+', ' ', base_title).strip()
                
                # Key bul
                clean_for_key = base_title.lower().replace(" ", "_")
                k = normalize(clean_for_key)
                
                # Stats bul
                vals = stats_map.get(k)
                if not vals:
                    # Fuzzy match
                    for mk, mv in stats_map.items():
                        if (k in mk) or (mk in k):
                            vals = mv
                            break
                
                if vals:
                    # vals artık (od, ap) ikilisi
                    od, ap = vals
                else:
                    od, ap = 0, 0
                    
                # Yeni Başlığı İnşa Et
                # Prefixler: 🔴 ... 🟡 ...
                prefixes = []
                if od > 0:
                    prefixes.append(f"🔴 {od}")
                if ap > 0:
                    prefixes.append(f"🟡 {ap}")
                
                prefix_str = " ".join(prefixes)
                
                # Format: "PREFIX  BASE_TITLE"
                if prefix_str:
                    new_title = f"{prefix_str}  {base_title}"
                else:
                    new_title = base_title

                if curr_text != new_title:
                    self.tabs.setTabText(i, new_title)

                # Zengin Bilgilendirici Sekme Tooltip'i (Rozet Anlamı)
                tooltip_lines = [f"📌 {base_title}"]
                if od > 0:
                    tooltip_lines.append(f"• 🔴 {od} Gecikmiş Ödev (Teslim tarihi geçmiş)")
                if ap > 0:
                    tooltip_lines.append(f"• 🟡 {ap} Yaklaşan Ödev (Teslimine 2 gün veya daha az kaldı)")
                if od == 0 and ap == 0:
                    tooltip_lines.append("• ✨ Bekleyen acil veya gecikmiş ödev yok")
                self.tabs.setTabToolTip(i, "\n".join(tooltip_lines))
                    
        except Exception as e:
            print("Badge update error:", e)
    # ------------------ Kayıt Modu Seçimi (Yeni Küme / Var Olana Ekle) ------------------
    def _kume_kaydet_modu_secimi(self, ogr_id: int):
        """
        Kaydetme modunu seçtirir: yeni küme mi, var olana ekle mi?
        Dönüş: None (iptal) veya
          {'mode': 'yeni'|'ekle', 'kume_id': int|None, 'bitis_guncelle': bool, 'bitis_tarihi': 'yyyy-MM-dd'}
        """
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                                     QRadioButton, QPushButton, QCheckBox, QDateEdit, QGroupBox, QFrame, QWidget)
        from PyQt6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle("Kaydetme Modu")
        dlg.setMinimumWidth(420)
        
        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- Başlık Alanı ---
        header_layout = QHBoxLayout()
        icon_label = QLabel("💾") # Save Icon
        icon_label.setStyleSheet("font-size: 36px;")
        
        text_layout = QVBoxLayout()
        title_lbl = QLabel("Ödev Kayıt Seçenekleri")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        desc_lbl = QLabel("Bu ödevleri nasıl kaydetmek istersiniz?")
        desc_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(desc_lbl)
        
        header_layout.addWidget(icon_label)
        header_layout.addSpacing(10)
        header_layout.addLayout(text_layout)
        header_layout.addStretch()
        
        main_layout.addLayout(header_layout)
        
        # --- Seçenekler Kutusu ---
        opts_group = QGroupBox()
        opts_group.setStyleSheet("""
            QGroupBox {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
            }
        """)
        opts_layout = QVBoxLayout(opts_group)
        opts_layout.setSpacing(12)
        opts_layout.setContentsMargins(15, 20, 15, 20)

        radYeni = QRadioButton("✨ Yeni bir ödev kümesi oluştur")
        radYeni.setChecked(True)
        radYeni.setStyleSheet("font-size: 13px; color: #0f172a; font-weight: 500;")
        
        radEkle = QRadioButton("➕ Var olan bir kümeye EKLE")
        radEkle.setStyleSheet("font-size: 13px; color: #0f172a; font-weight: 500;")
        
        opts_layout.addWidget(radYeni)
        opts_layout.addWidget(radEkle)

        # Küme Seçimi (Indent'li)
        kume_cont = QWidget()
        kume_layout = QHBoxLayout(kume_cont)
        kume_layout.setContentsMargins(25, 0, 0, 0)
        
        lblKume = QLabel("Küme:")
        lblKume.setStyleSheet("color: #475569;")
        cmbKume = QComboBox()
        cmbKume.setEnabled(False)
        
        kume_layout.addWidget(lblKume)
        kume_layout.addWidget(cmbKume, 1)
        
        opts_layout.addWidget(kume_cont)
        main_layout.addWidget(opts_group)

        # Veri Doldurma (Aynı Mantık)
        try:
            con = db.get_conn()
            rows = con.execute(
                "SELECT id, verilis_tarihi, bitis_tarihi FROM odev_kume "
                "WHERE ogrenci_id=? ORDER BY id DESC LIMIT 30", (ogr_id,)
            ).fetchall()
            for r in rows:
                txt = f"#{r['id']}  |  Ver.: {r['verilis_tarihi'] or '-'}  →  Bitiş: {r['bitis_tarihi'] or '-'}"
                cmbKume.addItem(txt, int(r['id']))
        except Exception:
            pass

        radEkle.toggled.connect(lambda s: cmbKume.setEnabled(s))

        # --- Bitiş Tarihi Güncelleme ---
        date_cont = QGroupBox()
        date_cont.setStyleSheet("border: none; margin-top: 5px;")
        date_layout = QHBoxLayout(date_cont)
        date_layout.setContentsMargins(0,0,0,0)
        
        chkBitis = QCheckBox("📅 Bitiş tarihini güncelle")
        chkBitis.setStyleSheet("color: #334155;")
        dtBitis = QDateEdit()
        dtBitis.setCalendarPopup(True)
        try:
            dtBitis.setDate(self.dtpBitis.date())
        except Exception: pass
        dtBitis.setEnabled(False)
        chkBitis.toggled.connect(lambda s: dtBitis.setEnabled(s))
        
        date_layout.addWidget(chkBitis)
        date_layout.addWidget(dtBitis, 1)
        
        main_layout.addWidget(date_cont)
        main_layout.addSpacing(10)

        # --- Butonlar ---
        hb = QHBoxLayout()
        btnCancel = QPushButton("Vazgeç")
        btnCancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btnCancel.setStyleSheet("""
            QPushButton { 
                padding: 8px 16px; 
                border-radius: 6px; 
                border: 1px solid #cbd5e1; 
                background-color: white; 
                color: #475569;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """)
        
        btnOk = QPushButton("Kaydet")
        btnOk.setCursor(Qt.CursorShape.PointingHandCursor)
        btnOk.setStyleSheet("""
            QPushButton { 
                padding: 8px 24px; 
                border-radius: 6px; 
                background-color: #4f46e5; 
                color: white; 
                font-weight: bold; 
                border: none;
            }
            QPushButton:hover { background-color: #4338ca; }
        """)
        
        hb.addStretch(1)
        hb.addWidget(btnCancel)
        hb.addWidget(btnOk)
        main_layout.addLayout(hb)
        
        btnCancel.clicked.connect(dlg.reject)
        btnOk.clicked.connect(dlg.accept)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        return {
            "mode": "ekle" if radEkle.isChecked() else "yeni",
            "kume_id": cmbKume.currentData() if radEkle.isChecked() else None,
            "bitis_guncelle": chkBitis.isChecked(),
            "bitis_tarihi": dtBitis.date().toString("yyyy-MM-dd")
        }
    # ------------------ Detaylı Çok-Sayfalı Rapor PDF ------------------
    def _detayli_rapor(self):
        """Seçili/çoklu öğrenci için çok sayfalı grafikli PDF rapor üretir (ikonlar garantili)."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDateEdit,
            QFileDialog, QListWidget, QListWidgetItem, QMessageBox, QLineEdit,
            QTabWidget, QTextEdit, QComboBox, QInputDialog, QStyle, QGroupBox, QFrame
        )
        from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen
        from PyQt6.QtCore import QDate, Qt, QSize
        from utils.ogrenci_rapor import ogrenci_rapor_pdf
        from utils import settings as appset
        import datetime as dt
        import os, traceback, json, shutil

        dlg = QDialog(self)
        dlg.setWindowTitle("Detaylı Rapor – Seçim")
        dlg.setMinimumWidth(550)
        dlg.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QGroupBox { 
                font-weight: bold; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 12px; font-size: 13px; color: #334155;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit, QDateEdit, QComboBox {
                border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px; background: white; min-height: 20px;
            }
            QListWidget { border: 1px solid #cbd5e1; border-radius: 6px; background: white; padding: 4px; }
            QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 6px; background: white; }
            QTabBar::tab {
                background: #f1f5f9; border: 1px solid #e2e8f0; padding: 6px 12px; margin-right: 2px;
                border-top-left-radius: 6px; border-top-right-radius: 6px; color: #64748b;
            }
            QTabBar::tab:selected { background: white; border-bottom: none; color: #2563eb; font-weight: bold; }
            QPushButton {
                border-radius: 6px; padding: 6px 12px; font-weight: 600;
                background-color: white; border: 1px solid #cbd5e1; color: #475569;
            }
            QPushButton:hover { background-color: #f1f5f9; }
            QPushButton#btnAction { background-color: #2563eb; color: white; border: none; }
            QPushButton#btnAction:hover { background-color: #1d4ed8; }
            QPushButton#btnTool { padding: 4px; border: 1px solid transparent; background: transparent; }
            QPushButton#btnTool:hover { background: #e2e8f0; border-color: #cbd5e1; }
        """)
        
        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # ---------- Helpers ----------
        def _std_icon(sp):
            try: return dlg.style().standardIcon(sp)
            except: return QIcon()

        def _themed(name, sp_fallback=None):
            ico = QIcon.fromTheme(name)
            if not ico or ico.isNull():
                ico = _std_icon(sp_fallback) if sp_fallback is not None else QIcon()
            return ico

        # ---------- TARİH ARALIĞI ----------
        grp_date = QGroupBox("Tarih Aralığı")
        row_date = QHBoxLayout(grp_date)
        row_date.setContentsMargins(15, 20, 15, 15)
        
        row_date.addWidget(QLabel("Başlangıç:"))
        dt1 = QDateEdit()
        dt1.setCalendarPopup(True)
        dt1.setDate(QDate.currentDate().addDays(-30))
        row_date.addWidget(dt1)

        row_date.addWidget(QLabel("Bitiş:"))
        dt2 = QDateEdit()
        dt2.setCalendarPopup(True)
        dt2.setDate(QDate.currentDate())
        row_date.addWidget(dt2)

        # --- Hızlı tarih butonları ---
        def _calendar_icon():
             # Basit ikon oluşturma (önceki koddan)
            pm = QPixmap(18, 18); pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(Qt.GlobalColor.black); pen.setWidth(2); p.setPen(pen)
            p.drawRoundedRect(2, 3, 14, 13, 2, 2); p.fillRect(3, 4, 12, 3, Qt.GlobalColor.black)
            p.end()
            return QIcon(pm)

        cal_ic = _calendar_icon()

        def _prep_quick_btn(btn, tip: str):
            btn.setText("")
            btn.setIcon(cal_ic)
            btn.setIconSize(QSize(16, 16))
            btn.setFixedSize(28, 28)
            btn.setToolTip(tip)
            btn.setObjectName("btnTool") # Stil için ID

        btn7 = QPushButton()
        btn30 = QPushButton()
        _prep_quick_btn(btn7, "Son 7 gün")
        _prep_quick_btn(btn30, "Son 30 gün")
        
        def _set_last(days: int):
            dt1.setDate(QDate.currentDate().addDays(-days))
            dt2.setDate(QDate.currentDate())

        btn7.clicked.connect(lambda: _set_last(7))
        btn30.clicked.connect(lambda: _set_last(30))
        
        row_date.addSpacing(10)
        row_date.addWidget(btn7)
        row_date.addWidget(btn30)
        main_layout.addWidget(grp_date)

        # ---------- ÖĞRENCİ LİSTESİ ----------
        grp_students = QGroupBox("Öğrenci Seçimi")
        v_std = QVBoxLayout(grp_students)
        v_std.setContentsMargins(15, 20, 15, 15)

        srch = QLineEdit()
        srch.setPlaceholderText("🔍 Öğrenci ara...")
        v_std.addWidget(srch)

        lst = QListWidget()
        lst.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        lst.setAlternatingRowColors(True)
        lst.setMinimumHeight(120)
        
        # Öğrenci listesini doldur
        for r in self._ogrenci_listesi():
            it = QListWidgetItem(f"{r['ad']} {r['soyad']}")
            it.setData(Qt.ItemDataRole.UserRole, int(r['id']))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Unchecked)
            lst.addItem(it)
        v_std.addWidget(lst)

        # Seçim Araçları
        tools = QHBoxLayout()
        sel_info = QLabel("Seçili: 0")
        sel_info.setStyleSheet("color: #64748b; font-size: 11px;")
        
        btnAll = QPushButton("Tümünü Seç"); btnAll.setObjectName("btnTool"); btnAll.setCursor(Qt.CursorShape.PointingHandCursor)
        btnNone = QPushButton("Temizle"); btnNone.setObjectName("btnTool"); btnNone.setCursor(Qt.CursorShape.PointingHandCursor)
        btnInvert = QPushButton("Ters Çevir"); btnInvert.setObjectName("btnTool"); btnInvert.setCursor(Qt.CursorShape.PointingHandCursor)
        
        tools.addWidget(btnAll)
        tools.addWidget(btnNone)
        tools.addWidget(btnInvert)
        tools.addStretch(1)
        tools.addWidget(sel_info)
        v_std.addLayout(tools)
        main_layout.addWidget(grp_students)

        # Logic functions for selection (same as before)
        def _update_sel_info():
            cnt = sum(1 for i in range(lst.count()) if lst.item(i).checkState() == Qt.CheckState.Checked)
            sel_info.setText(f"Seçili: {cnt}")

        def _set_all(state: Qt.CheckState):
            for i in range(lst.count()):
                it = lst.item(i)
                if not it.isHidden(): it.setCheckState(state)
            _update_sel_info()

        btnAll.clicked.connect(lambda: _set_all(Qt.CheckState.Checked))
        btnNone.clicked.connect(lambda: _set_all(Qt.CheckState.Unchecked))
        
        def _invert():
            for i in range(lst.count()):
                it = lst.item(i)
                if not it.isHidden():
                    it.setCheckState(Qt.CheckState.Unchecked if it.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)
            _update_sel_info()
        btnInvert.clicked.connect(_invert)
        
        lst.itemChanged.connect(lambda _: _update_sel_info())
        
        srch.textChanged.connect(lambda t: [
            lst.item(i).setHidden(t.lower() not in lst.item(i).text().lower()) for i in range(lst.count())
        ])

        # ---------- ŞABLON YÖNETİMİ ----------
        grp_tmpl = QGroupBox("Değerlendirme Şablonları")
        v_tmpl = QVBoxLayout(grp_tmpl)
        v_tmpl.setContentsMargins(15, 20, 15, 15)
        
        tabWidget = QTabWidget()
        v_tmpl.addWidget(tabWidget)

        kayitli = appset.ayar_get("rapor_sablonlari") or "[]"
        try: sablonlar = json.loads(kayitli)
        except: sablonlar = []

        if not sablonlar:
            sablonlar = [
                {"ad": "Genel Şablon", "icerik": "• Tamamlama oranı düşükse kısa vadeli hedefler belirlenmeli."},
                {"ad": "Başarılı Öğrenci", "icerik": "• İstikrarlı tempo korunsun; deneme analizi artırılsın."},
                {"ad": "Zayıf Performans", "icerik": "• Günlük en az 30 dk tekrar + pomodoro ile küçük parçalama."}
            ]

        edits = {}
        for sab in sablonlar:
            te = QTextEdit(); te.setPlainText(sab["icerik"])
            tabWidget.addTab(te, sab["ad"])
            edits[sab["ad"]] = te

        # Toolbar
        toolbar = QHBoxLayout()
        btnAdd = QPushButton("➕ Ekle"); btnAdd.setObjectName("btnTool")
        btnRename = QPushButton("✏️ Ad Değiştir"); btnRename.setObjectName("btnTool")
        btnDelete = QPushButton("🗑️ Sil"); btnDelete.setObjectName("btnTool")
        btnSave = QPushButton("💾 Kaydet"); btnSave.setObjectName("btnTool")
        
        toolbar.addWidget(btnAdd); toolbar.addWidget(btnRename)
        toolbar.addWidget(btnDelete); toolbar.addWidget(btnSave)
        toolbar.addStretch(1)
        v_tmpl.addLayout(toolbar)
        
        # Aktif Şablon
        row_active = QHBoxLayout()
        row_active.addWidget(QLabel("Aktif Şablon:"))
        cmbActive = QComboBox()
        cmbActive.addItems([tabWidget.tabText(i) for i in range(tabWidget.count())])
        aktif = appset.ayar_get("rapor_aktif_sablon")
        if aktif: cmbActive.setCurrentText(aktif)
        row_active.addWidget(cmbActive, 1)
        v_tmpl.addLayout(row_active)
        
        main_layout.addWidget(grp_tmpl)
        
        # ---------- Butonlar (Alt Kısım) ----------
        main_layout.addStretch(1)
        hbox_btns = QHBoxLayout()
        
        btnCancel = QPushButton("Vazgeç")
        btnCancel.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btnRun = QPushButton("Rapor Oluştur")
        btnRun.setObjectName("btnAction")
        btnRun.setCursor(Qt.CursorShape.PointingHandCursor)
        btnRun.setMinimumWidth(120)
        
        hbox_btns.addStretch(1)
        hbox_btns.addWidget(btnCancel)
        hbox_btns.addWidget(btnRun)
        main_layout.addLayout(hbox_btns)

        def _refresh_active_combo():
            names = [tabWidget.tabText(i) for i in range(tabWidget.count())]
            cur = cmbActive.currentText()
            cmbActive.clear(); cmbActive.addItems(names)
            if cur in names: cmbActive.setCurrentText(cur)
            cmbActive.blockSignals(True)
            cmbActive.clear()
            cmbActive.addItems(names)
            if cur in names:
                cmbActive.setCurrentText(cur)
            elif names:
                cmbActive.setCurrentIndex(0)
            cmbActive.blockSignals(False)

        # --- ŞABLON İŞLEMLERİ ---
        def _yeni_sablon():
            ad, ok = QInputDialog.getText(dlg, "Yeni Şablon", "Şablon adı:")
            if ok and ad.strip():
                if ad in edits:
                    QMessageBox.warning(dlg, "Var", "Bu isimde bir şablon zaten var.")
                    return
                te = QTextEdit()
                te.setPlainText("• Yeni değerlendirme metni buraya yazılacak.")
                tabWidget.addTab(te, ad)
                edits[ad] = te
                _refresh_active_combo()

        btnAdd.clicked.connect(_yeni_sablon)

        def _rename_sablon():
            idx = tabWidget.currentIndex()
            if idx < 0:
                return
            eski = tabWidget.tabText(idx)
            yeni, ok = QInputDialog.getText(dlg, "Şablon Adı Değiştir", "Yeni ad:", text=eski)
            if ok and yeni.strip():
                if yeni in edits and yeni != eski:
                    QMessageBox.warning(dlg, "Var", "Bu isim zaten kullanılıyor.")
                    return
                edits[yeni] = edits.pop(eski)
                tabWidget.setTabText(idx, yeni)
                _refresh_active_combo()

        btnRename.clicked.connect(_rename_sablon)

        def _sil_sablon():
            idx = tabWidget.currentIndex()
            if idx < 0:
                return
            ad = tabWidget.tabText(idx)
            if QMessageBox.question(dlg, "Sil",
                                    f"‘{ad}’ şablonunu silmek istiyor musunuz?") == QMessageBox.StandardButton.Yes:
                tabWidget.removeTab(idx)
                edits.pop(ad, None)
                _refresh_active_combo()

        btnDelete.clicked.connect(_sil_sablon)

        def _kaydet():
            data = []
            for i in range(tabWidget.count()):
                ad = tabWidget.tabText(i)
                icerik = edits[ad].toPlainText()
                data.append({"ad": ad, "icerik": icerik})
            appset.ayar_set("rapor_sablonlari", json.dumps(data))
            appset.ayar_set("rapor_aktif_sablon", cmbActive.currentText())

        btnSave.clicked.connect(
            lambda: (_kaydet(), QMessageBox.information(dlg, "Kaydedildi", "Şablonlar kaydedildi.")))

        # ---------- ALT BUTONLAR (Modern) ----------
        # Bu kısım zaten yukarıda modern layout içinde tanımlandı (btnRun, btnCancel).
        # Ancak eski kod bloğu aşağıda kalmış, onu temizliyoruz.
        
        # Fonksiyonel bağlamalar (Logic)
        btnCancel.clicked.connect(dlg.reject)
        
        # Raporlama işlemini başlatan fonksiyon
        def _on_run():
            # Aktif şablonu kaydet
            _kaydet()
            dlg.accept()
            
        btnRun.clicked.connect(_on_run)
        
        # Eski btnOk referansı varsa temizle, btnRun kullanacağız
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Seçili tarihleri (date objesi olarak) al
        date_start = dt1.date().toPyDate()
        date_end = dt2.date().toPyDate()
        
        # Seçili öğrenciler
        sel_ids = []
        for i in range(lst.count()):
             it = lst.item(i)
             if it.checkState() == Qt.CheckState.Checked:
                 sel_ids.append(it.data(Qt.ItemDataRole.UserRole))
        
        if not sel_ids:
             curr = lst.currentItem()
             if curr:
                 sel_ids.append(curr.data(Qt.ItemDataRole.UserRole))

        # Şablon içeriği
        aktif_sablon_adi = cmbActive.currentText()
        ek_metin = ""
        if aktif_sablon_adi in edits:
            ek_metin = edits[aktif_sablon_adi].toPlainText()

        # PDF oluştur
        if not sel_ids:
             QMessageBox.warning(self, "Uyarı", "Lütfen en az bir öğrenci seçiniz.")
             return

        try:
             # Varsayılan dosya adı belirleme
             d_s = date_start.strftime("%d.%m.%Y")
             d_e = date_end.strftime("%d.%m.%Y")
             
             default_name = "Rapor.pdf"
             
             if len(sel_ids) == 1:
                 # Tek öğrenci: ID - Ad Soyad-Tarih
                 oid = sel_ids[0]
                 name_str = "Ogrenci"
                 # Listeden ismini bul
                 for i in range(lst.count()):
                     it = lst.item(i)
                     if it.data(Qt.ItemDataRole.UserRole) == oid:
                         name_str = it.text() # Ad Soyad (boşluklu kalabilir)
                         break
                 
                 # Dosya adı için güvenli karakterler (boşluk dahil)
                 safe_name = "".join([c for c in name_str if c.isalnum() or c in (' ', '_', '-')]).strip()
                 
                 # Format: ID - Ad Soyad-TarihAralığı
                 default_name = f"{oid} - {safe_name}-{d_s}-{d_e}.pdf"
             else:
                 # Çoklu: Toplu Rapor - Tarih
                 default_name = f"Toplu Rapor - {len(sel_ids)} Ogrenci - {d_s}-{d_e}.pdf"
             path, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", default_name, "PDF Dosyaları (*.pdf)")
             if not path:
                 return
             
             is_multi = len(sel_ids) > 1
             target_path = path 
             
             from PyQt6.QtWidgets import QProgressDialog
             prog = QProgressDialog("Raporlar hazırlanıyor...", "İptal", 0, len(sel_ids), self)
             prog.setWindowModality(Qt.WindowModality.WindowModal)
             prog.show()
             
             # Geçici klasör
             temp_dir = os.path.join(os.getcwd(), "temp_reports")
             os.makedirs(temp_dir, exist_ok=True)
             
             generated_files = []
             
             # Kurum/Logo Ayarları
             k_adi = appset.ayar_get("kurum_adi", "Ödev Takip Raporu")
             l_path = appset.ayar_get("logo_path", None)

             for idx, oid in enumerate(sel_ids):
                  if prog.wasCanceled(): break
                  prog.setValue(idx)
                  
                  # Öğrenci adını bul
                  o_name_str = f"Ogrenci_{oid}"
                  for i_row in range(lst.count()):
                      it_row = lst.item(i_row)
                      if it_row.data(Qt.ItemDataRole.UserRole) == oid:
                          o_name_str = it_row.text()
                          break
                  
                  safe_o_name = "".join([c for c in o_name_str if c.isalnum() or c in (' ', '_', '-')]).strip()
                  
                  # Geçici dosya adı: {ID} - {AD SOYAD} - {TARIH}.pdf
                  # Bu isim fallback durumunda doğrudan kullanılacak.
                  fname_final = f"{oid} - {safe_o_name} - {d_s}-{d_e}.pdf"
                  tmp_Name = os.path.join(temp_dir, fname_final)
                  
                  try:
                      # PDF MOTORU ÇAĞRISI
                      ogrenci_rapor_pdf(
                          oid, 
                          tmp_Name, 
                          date_start, 
                          date_end, 
                          kurum_adi=k_adi, 
                          logo_path=l_path, 
                          genel_degerlendirme=ek_metin
                      )
                      if os.path.exists(tmp_Name):
                          generated_files.append(tmp_Name)
                  except Exception as ee:
                      print(f"Hata {oid}: {ee}")
                      traceback.print_exc()
        
        except Exception as e:
             QMessageBox.critical(self, "Hata", f"Rapor başlatılamadı: {e}")
             return

        if 'prog' in locals():
            prog.setValue(len(sel_ids))
        
        # Merge veya taşıma
        if not generated_files:
             QMessageBox.warning(self, "Hata", "Hiçbir rapor üretilemedi.")
             return
             
        if is_multi:
             # PDF Merge
             try:
                 from pypdf import PdfWriter
                 merger = PdfWriter()
                 for pdf in generated_files:
                     merger.append(pdf)
                 merger.write(target_path)
                 merger.close()
                 QMessageBox.information(self, "Tamam", f"{len(sel_ids)} öğrencinin raporu birleştirildi:\n{target_path}")
             except ImportError:
                  # Merge yapılamıyor, dosyaları (zaten doğru isimlendirilmiş) hedef klasöre kopyala
                  base_dir = os.path.dirname(target_path)
                  saved_count = 0
                  for f in generated_files:
                      fname = os.path.basename(f) # Zaten {ID} - {AD SOYAD} - {TARIH}.pdf
                      dest = os.path.join(base_dir, fname)
                      shutil.copy(f, dest)
                      saved_count += 1
                  QMessageBox.information(self, "Tamam", f"Toplu PDF birleştirilemedi (pypdf yok).\nRaporlar ayrı ayrı şu klasöre kaydedildi:\n{base_dir}\n({saved_count} adet)")
        else:
             # Tek dosya
             shutil.move(generated_files[0], target_path)
             QMessageBox.information(self, "Tamam", f"Rapor kaydedildi:\n{target_path}")
             
        # Temizlik
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Çıkmadan şablonları/aktif seçimi kaydet
        _kaydet()




    # ------------------ Akıllı Eksik Konular (Gelişmiş Panel) ------------------
    def _akilli_eksik_konular(self):
        """
        Gelişmiş Müfredat ve Eksik Konu Analiz Panelini açar.
        """
        from PyQt6.QtWidgets import QMessageBox
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Öğrenci Seçiniz", "Lütfen önce bir öğrenci seçip 'Bilgileri Getir' diyerek dersleri yükleyin.")
            return

        idx = self.tabs.currentIndex()
        active_ders = self.tabs.tabText(idx).lower().replace(" ", "_") if idx >= 0 else None

        av_books = {}
        if hasattr(self, '_ders_tablolari'):
            for d_adi, tbl in self._ders_tablolari.items():
                books = []
                try:
                    for c in range(1, tbl.columnCount()):
                        h_item = tbl.horizontalHeaderItem(c)
                        if h_item:
                            books.append(h_item.text())
                except Exception:
                    pass
                if books:
                    av_books[d_adi] = books

        from ui.missing_topics_dialog import MissingTopicsDialog
        dlg = MissingTopicsDialog(ogrenci_id=ogr_id, parent=self, available_books=av_books, active_lesson=active_ders)
        if dlg.exec():
            tasks = dlg.selected_topics
            if not tasks:
                return
            count = 0
            grid_checked = 0
            for t in tasks:
                ders = t.get("ders")
                kitap = t.get("kitap")
                konu = t.get("konu")
                dk = str(t.get("dk", 35))
                aciklama = t.get("aciklama", "")
                try:
                    self._verilen_satir_ekle(ders, kitap, konu, dk, aciklama)
                    count += 1
                except Exception:
                    pass
                try:
                    table_widget, r, c = self._hucre_bul(ders, kitap, konu)
                    if table_widget:
                        item = table_widget.item(r, c)
                        if not item:
                            item = QTableWidgetItem()
                            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                            item.setCheckState(Qt.CheckState.Unchecked)
                            table_widget.setItem(r, c, item)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                        if item.checkState() != Qt.CheckState.Checked:
                            item.setCheckState(Qt.CheckState.Checked)
                            grid_checked += 1
                except Exception:
                    pass
            try:
                self._toplam_sure_guncelle()
            except Exception:
                pass
            msg = f"{count} adet eksik konu 'Verilen Ödevler' listesine eklendi ({grid_checked} adet konu tablosunda işaretlendi)."
            QMessageBox.information(self, "İşlem Tamam", msg)


    # ------------------ Aktif Kitap Seti / Tahmini Süre ------------------

    def _aktif_kitaplar(self, ogr_id: int | None = None) -> set[str]:
        """
        Öğrenciye atanmış AKTİF kitap adlarını (lowercase) döndürür.
        Boş set dönerse takviye adaylarında filtre uygulanmaz.
        """
        names = set()
        try:
            if ogr_id is None and hasattr(self, "_secili_ogrenci_id"):
                ogr_id = self._secili_ogrenci_id()
            if ogr_id:
                con = db.get_conn()
                rows = con.execute("""
                    SELECT DISTINCT kitap_ad
                    FROM ogrenci_kitap
                    WHERE ogrenci_id=? AND (aktif IS NULL OR aktif=1)
                """, (ogr_id,)).fetchall()
                for r in rows:
                    ad = (r["kitap_ad"] or "").strip().lower()
                    if ad:
                        names.add(ad)
        except Exception:
            pass

        # Eski fallback’lar
        if not names:
            try:
                if hasattr(self, "kitap_listesi"):
                    names = {(k.ad or "").strip().lower()
                             for k in self.kitap_listesi
                             if getattr(k, "aktif", True) and (k.ad or "").strip()}
                elif hasattr(self, "kitaplar"):
                    names = {(str(k) or "").strip().lower() for k in self.kitaplar}
            except Exception:
                pass

        return names

    def _tahmini_sure(self, ders, kitap, konu):
        """
        Konu için dakika tahmini.
        1) DB'den (konu_helper / ders tablosu) ort_sure bilgisini sorgular.
        2) Varsa estimate_duration/dk_for çağırır.
        3) Varsayılan olarak standart 45 dk döner.
        """
        ders_s = str(ders or "").strip()
        konu_s = str(konu or "").strip().lower()

        # 1) Veritabanından ort_sure sorgula
        if ders_s and konu_s:
            try:
                import db
                from utils import konu_helper
                con = getattr(self, "con", None)
                if not con:
                    con = db.get_conn()
                if con:
                    ogr_id = None
                    try:
                        ogr_id = self._secili_ogrenci_id()
                    except Exception:
                        pass
                    active_list = konu_helper.get_active_list(con, ders_s, ogrenci_id=ogr_id)
                    for item in active_list:
                        if (item.get("konu") or "").strip().lower() == konu_s:
                            ort_s = item.get("ort_sure")
                            if ort_s is not None and int(ort_s) > 0:
                                return int(ort_s)
                            break
            except Exception:
                pass

        # 2) Özel metodlar
        for cand in ("estimate_duration", "dk_for"):
            fn = getattr(self, cand, None)
            if callable(fn):
                try:
                    v = fn(ders, kitap, konu)
                    if isinstance(v, (int, float)) and v > 0:
                        return int(v)
                except Exception:
                    pass

        # 3) Varsayılan süre (Kullanıcı ayarı veya 45 dk)
        return self._get_default_sure()

    # ------------------ Takviye Adayları (Bitişe Göre) ------------------

    def _takviye_adaylari(self, days_ahead: int = 3):
        """
        Yaklaşan bitiş/gecikmiş 'devam' ödevlerini DB’den derler.
        Dönüş öğesi: {'ders','kitap','konu','dk','due','status'}
          status ∈ {'gecikmis','yakinda','hafta'}
        DB boşsa _oneri_yenile() fallback’iyle üretir.
        Aktif kitap seti boşsa KİTAP FİLTRESİ uygulanmaz.
        """
        from PyQt6.QtCore import QDate

        today = QDate.currentDate()
        ogr_id = None
        try:
            ogr_id = self._secili_ogrenci_id()
        except Exception:
            pass

        aktif = self._aktif_kitaplar(ogr_id)
        allow_all = (len(aktif) == 0)

        items = []

        # 1) DB’den 'devam' kayıtları
        if ogr_id:
            try:
                con = db.get_conn()
                rows = con.execute("""
                    SELECT o.ders, o.kitap_ad, o.konu_ad, COALESCE(o.saat_dk,0) AS dk, k.bitis_tarihi
                    FROM odev AS o
                    JOIN odev_kume AS k ON k.id = o.kume_id
                    WHERE o.ogrenci_id=? AND LOWER(COALESCE(o.durum,''))='devam'
                      AND ( date(k.bitis_tarihi) < date('now')
                            OR date(k.bitis_tarihi) <= date('now', '+' || ? || ' day') )
                    ORDER BY k.bitis_tarihi ASC, o.id ASC
                """, (ogr_id, days_ahead)).fetchall()

                for r in rows:
                    ders = (r["ders"] or "").strip()
                    kitap = (r["kitap_ad"] or "").strip()
                    konu = (r["konu_ad"] or "").strip()
                    dk = int(r["dk"] or 0) or self._tahmini_sure(ders, kitap, konu)

                    if kitap and not allow_all and (kitap.strip().lower() not in aktif):
                        continue

                    due = QDate.fromString(r["bitis_tarihi"] or "", "yyyy-MM-dd")
                    if not due.isValid():
                        due = today
                    ddiff = today.daysTo(due)

                    if ddiff < 0:
                        status = "gecikmis"
                    elif ddiff <= days_ahead:
                        status = "yakinda"
                    else:
                        status = "hafta"

                    items.append({"ders": ders, "kitap": kitap, "konu": konu, "dk": dk, "due": due, "status": status})
            except Exception:
                items = []

        # 2) Fallback: _oneri_yenile tabanlı
        if not items:
            try:
                zmax = 5
                if hasattr(self, "oneri") and hasattr(self.oneri, "cmbZorluk"):
                    zmax = int(self.oneri.cmbZorluk.currentText())
                base = self._oneri_yenile(zorluk_max=zmax) or []
            except Exception:
                base = []

            week_end = self.dtpBitis.date() if hasattr(self, "dtpBitis") else today.addDays(7)

            for it in base:
                ders = (it.get("ders") or "")
                kitap = (it.get("kitap") or "")
                konu = (it.get("konu") or "")
                dk = int(it.get("dk") or 0) or self._tahmini_sure(ders, kitap, konu)

                if kitap and not allow_all and (kitap.strip().lower() not in aktif):
                    continue

                due = week_end
                ddiff = today.daysTo(due)
                if ddiff < 0:
                    status = "gecikmis"
                elif ddiff <= days_ahead:
                    status = "yakinda"
                else:
                    status = "hafta"

                items.append({"ders": ders, "kitap": kitap, "konu": konu, "dk": dk, "due": due, "status": status})

        # 3) Öncelik (gecikmiş>yakında>hafta, kısa işler öne)
        def _prio(o):
            s = o.get("status", "")
            p = 100 if s == "gecikmis" else 70 if s == "yakinda" else 40
            dk = int(o.get("dk", 0) or 0)
            return (p, -dk)

        items.sort(key=_prio, reverse=True)
        return items

    # ------------------ Buton: Akıllı Takviye & Telafi ------------------

    def _akilli_takviye(self):
        """
        Gelişmiş Akıllı Takviye ve Telafi Oluşturucu penceresini açar.
        """
        from PyQt6.QtWidgets import QMessageBox
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            QMessageBox.warning(self, "Öğrenci Seçiniz", "Lütfen önce bir öğrenci seçip 'Bilgileri Getir' diyerek dersleri yükleyin.")
            return

        idx = self.tabs.currentIndex()
        active_ders = self.tabs.tabText(idx).lower().replace(" ", "_") if idx >= 0 else None

        av_books = {}
        if hasattr(self, '_ders_tablolari'):
            for d_adi, tbl in self._ders_tablolari.items():
                books = []
                try:
                    for c in range(1, tbl.columnCount()):
                        h_item = tbl.horizontalHeaderItem(c)
                        if h_item:
                            books.append(h_item.text())
                except Exception:
                    pass
                if books:
                    av_books[d_adi] = books

        from ui.remedial_dialog import SmartRemedialDialog
        dlg = SmartRemedialDialog(ogrenci_id=ogr_id, parent=self, available_books=av_books, active_lesson=active_ders)
        if dlg.exec():
            tasks = dlg.selected_remedials
            if not tasks:
                return
            count = 0
            grid_checked = 0
            for t in tasks:
                ders = t.get("ders")
                kitap = t.get("kitap")
                konu = t.get("konu")
                dk = str(t.get("dk", 30))
                aciklama = t.get("aciklama", "")
                try:
                    self._verilen_satir_ekle(ders, kitap, konu, dk, aciklama)
                    count += 1
                except Exception:
                    pass
                try:
                    table_widget, r, c = self._hucre_bul(ders, kitap, konu)
                    if table_widget:
                        item = table_widget.item(r, c)
                        if not item:
                            item = QTableWidgetItem()
                            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                            item.setCheckState(Qt.CheckState.Unchecked)
                            table_widget.setItem(r, c, item)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                        if item.checkState() != Qt.CheckState.Checked:
                            item.setCheckState(Qt.CheckState.Checked)
                            grid_checked += 1
                except Exception:
                    pass
            try:
                self._toplam_sure_guncelle()
            except Exception:
                pass
            msg = f"{count} adet takviye ödevi 'Verilen Ödevler' listesine eklendi ({grid_checked} adet konu tablosunda işaretlendi)."
            QMessageBox.information(self, "İşlem Tamam", msg)
    #s----*******-----------

    def _tik_degisti(self, it, tablo, ders: str):
        """Konulardaki checkbox değişince sağdaki 'verilen' tablosunu senkronize eder."""

        if it is None or it.column() == 0:
            return
        if not (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        if getattr(self, "_in_verilen_update", False) or (it is None) or it.column() == 0:
            return

        konu_item = tablo.item(it.row(), 0)
        if not konu_item:
            return
        konu_ad = (konu_item.text() or "").strip()

        hdr = tablo.horizontalHeaderItem(it.column())
        if not hdr:
            return
        kitap_ad = (hdr.text() or "").strip()

        def _vtext(r, c):
            cell = self.verilen.item(r, c)
            return (cell.text() if cell and cell.text() is not None else "").strip()

        row_to_remove = None
        for r in range(self.verilen.rowCount()):
            if (_vtext(r, 0) == ders and _vtext(r, 1) == kitap_ad and _vtext(r, 2) == konu_ad):
                row_to_remove = r
                break

        is_checked = (it.checkState() == Qt.CheckState.Checked)

        self._in_verilen_update = True
        sort_on = self.verilen.isSortingEnabled()
        self.verilen.setSortingEnabled(False)
        self.verilen.blockSignals(True)
        try:
            if is_checked:
                if row_to_remove is None:
                    r = self.verilen.rowCount()
                    self.verilen.insertRow(r)
                    self.verilen.setItem(r, 0, QTableWidgetItem(ders))
                    self.verilen.setItem(r, 1, QTableWidgetItem(kitap_ad))
                    self.verilen.setItem(r, 2, QTableWidgetItem(konu_ad))
                    dk_val = self._tahmini_sure(ders, kitap_ad, konu_ad)
                    def_dk = self._get_default_sure()
                    self.verilen.setItem(r, 3, QTableWidgetItem(str(dk_val if dk_val and int(dk_val) > 0 else def_dk)))
                    self.verilen.setItem(r, 4, QTableWidgetItem(""))
            else:
                if row_to_remove is not None:
                    self.verilen.removeRow(row_to_remove)
        finally:
            self.verilen.blockSignals(False)
            self.verilen.setSortingEnabled(sort_on)
            self._in_verilen_update = False

        try:
            self._toplam_sure_guncelle()
        except Exception:
            pass

    def _ekle_click(self):
        """Seçilen/işaretli önerileri Verilen tablosuna ekler; sol grid hücresini de işaretler."""
        host = self._get_host()
        if not host:
            return

        # 1) Liste öğelerini topla (önce checked, yoksa selected)
        picked = []
        try:
            for i in range(self.liste.count()):
                it = self.liste.item(i)
                if it and it.checkState() == Qt.CheckState.Checked:
                    picked.append(it)
        except Exception:
            picked = []

        if not picked:
            try:
                picked = list(self.liste.selectedItems())
            except Exception:
                picked = []

        if not picked:
            try:
                if hasattr(host, "_toast"):
                    host._toast("Seçili öğe yok.", parent=host, msec=1300,
                                under_widget=getattr(self, 'btnEkle', None))
            except Exception:
                pass
            return

        # 2) QListWidgetItem -> dict
        def item_to_dict(obj):
            if isinstance(obj, dict):
                obj["dk"] = int(obj.get("dk", 0) or 0)
                return obj
            try:
                data = obj.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict):
                    data["dk"] = int(data.get("dk", 0) or 0)
                    return data
            except Exception:
                pass
            try:
                txt = (obj.text() or "").strip()
                m = re.search(r"\((\d+)\s*dk\)", txt)
                dk_val = int(m.group(1)) if m else 0
                if m:
                    txt = re.sub(r"\s*\(\d+\s*dk\)\s*$", "", txt).strip()
                parts = [p.strip() for p in txt.split("/") if p.strip()]
                ders = parts[0] if len(parts) > 0 else ""
                kitap = parts[1] if len(parts) > 1 else ""
                konu = parts[2] if len(parts) > 2 else ""
                return {"ders": ders, "kitap": kitap, "konu": konu, "dk": dk_val}
            except Exception:
                return {"ders": "", "kitap": "", "konu": "", "dk": 0}

        selected = [item_to_dict(it) for it in picked]

        # 3) Süze & ekle
        eklendi = 0
        atlanan = []

        for it in (selected or []):
            ders = (it.get("ders") or "").strip()
            kitap = (it.get("kitap") or "").strip()
            konu = (it.get("konu") or "").strip()
            dk = str(int(it.get("dk", 0) or 0))
            if not ders or not kitap or not konu:
                continue

            # engel kontrolü
            blocked, reason = self._neden_eklenemez(ders, kitap, konu)
            if blocked:
                atlanan.append(f"{ders}/{kitap}/{konu} — {reason}")
                continue

            # Verilen listesine ekle (kaynak=oneri)
            try:
                host._verilen_satir_ekle(ders, kitap, konu, dk, "", source="oneri")
                eklendi += 1

                #  Sol grid hücresini işaretle + soft oneri flag’i koy
                try:
                    if hasattr(host, "_hucre_bul"):
                        t, r, c = host._hucre_bul(ders, kitap, konu)
                        if t is not None:
                            item = t.item(r, c)
                            if item is None:
                                item = QTableWidgetItem()
                                t.setItem(r, c, item)

                            flags = item.flags()
                            if not (flags & Qt.ItemFlag.ItemIsUserCheckable):
                                flags |= Qt.ItemFlag.ItemIsUserCheckable
                            flags |= Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                            item.setFlags(flags)

                            # soft oneri imzası
                            item.setData(Qt.ItemDataRole.UserRole, "oneri_soft")
                            # Kullanıcıya görünür tik
                            item.setCheckState(Qt.CheckState.Checked)
                except Exception:
                    pass

            except Exception:
                atlanan.append(f"{ders}/{kitap}/{konu} — eklenemedi")

        # 4) Geri bildirim
        try:
            if hasattr(host, "_toast"):
                if eklendi:
                    host._toast(f"{eklendi} ödev eklendi ✅", parent=host, msec=1400,
                                under_widget=getattr(self, 'btnEkle', None))
                else:
                    msg = "Seçili öğe yok." if not selected else "Eklenecek yeni ödev yok."
                    host._toast(msg, parent=host, msec=1400,
                                under_widget=getattr(self, 'btnEkle', None))
        except Exception:
            pass

        if atlanan:
            try:
                QMessageBox.information(self, "Atlananlar", "• " + "\n• ".join(atlanan))
            except Exception:
                pass

    #f-----*******----------

    # ------------------ WhatsApp Mesaj Metni Oluşturucu ------------------

    def _build_wp_message(self, ogr_row, satirlar: list[str], bitis_tarihi: str) -> str:
        """
        Ayarlardan kurum/koç/iletişim/web/QR bilgilerini çekerek WhatsApp mesaj metnini oluşturur.
        """
        # sqlite3.Row -> dict (güvenli)
        try:
            ogr = dict(ogr_row) if ogr_row is not None else {}
        except Exception:
            ogr = ogr_row or {}

        kurum = (appset.ayar_get('kurum_adi') or '').strip()
        eg_kocu = (appset.ayar_get('egitim_kocu') or '').strip()
        ilet = (appset.ayar_get('iletisim_satiri') or '').strip()
        web = (appset.ayar_get('kurum_web') or '').strip()
        qr = (appset.ayar_get('odev_qr_link') or '').strip()

        ad = (ogr.get('ad') if isinstance(ogr, dict) else ogr['ad']) if ogr else ''
        soyad = (ogr.get('soyad') if isinstance(ogr, dict) else ogr['soyad']) if ogr else ''

        # Başlık & Üst Bilgi
        header = []
        if kurum:
            header.append(f"🏫 *{kurum}*")  # Okul ikonu + Kalın
        
        # Öğrenci Bilgisi
        header.append(f"👤 *Öğrenci:* {ad} {soyad}")
        
        # Tarih (Varsa)
        if bitis_tarihi:
            header.append(f"📅 *Son Teslim:* {bitis_tarihi}")

        # Ödevler Gövdesi
        # Satırları biraz süsleyelim (başında tire varsa ikonla değiştir)
        decorated_lines = []
        if satirlar:
            decorated_lines.append("📚 *Ödev Listesi:*")
            for line in satirlar:
                # Standart "- Ders / Konu" formatını "🔹 Ders..." yap
                if line.strip().startswith("-"):
                    line = "🔹 " + line.strip()[1:].strip()
                decorated_lines.append(line)
            body = "\n".join(decorated_lines)
        else:
            body = "✅ *Atanmış yeni ödev yok.*"

        # Kapanış
        closing = "✨ _Başarılar dileriz._"

        # Alt Bilgi (Footer)
        footer = []
        if eg_kocu:
            footer.append(f"👨‍🏫 *Koç:* {eg_kocu}")
        if ilet:
            footer.append(f"📞 {ilet}")
        if web:
            footer.append(f"🌐 {web}")
        # QR linki genelde uzundur, temiz dursun
        if qr:
            footer.append(f"🔗 *QR:* {qr}")

        # Parçaları birleştir
        parts = [
            "\n".join(header),
            "",  # Boşluk
            body,
            "",  # Boşluk
            closing
        ]
        
        if footer:
            parts.extend([
                "", 
                "──────────────", # Ayırıcı çizgi
                "\n".join(footer)
            ])

        return "\n".join([p for p in parts if isinstance(p, str) and p.strip() != ""])

    # ------------------ Gelişmiş Filtre Diyaloğu ------------------

    def _show_filter_dialog(self):
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
            QComboBox, QCheckBox, QPushButton
        )
        from PyQt6.QtCore import QTimer

        dlg = QDialog(self)
        dlg.setWindowTitle("Verilen – Gelişmiş Filtreler")
        v = QVBoxLayout(dlg)

        # -- Hızlı Arama --
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Hızlı Arama:"))
        txt = QLineEdit(self.txtAraVerilen.text())
        row1.addWidget(txt, 1)
        v.addLayout(row1)

        # -- Sütun + Regex --
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Sütun:"))
        cmb = QComboBox()
        cmb.addItems(["Tümü", "Ders", "Kitap", "Konu", "Süre", "Açıklama"])
        current_idx = self.cmbAraKolon.currentIndex()
        cmb.setCurrentIndex(3 if current_idx == 0 else current_idx)  # "Konu" öntanımlı
        row2.addWidget(cmb)

        chkR = QCheckBox("Regex")
        chkR.setChecked(self.chkRegex.isChecked())
        row2.addWidget(chkR)
        row2.addStretch(1)
        v.addLayout(row2)

        # -- Durum filtreleri (UI'da varsa) --
        row3 = QHBoxLayout()
        chkG = QCheckBox("Sadece gecikenler")
        chkW = QCheckBox("Bu hafta bitecek")
        try:
            chkG.setChecked(self.chkGeciken.isChecked())
            chkW.setChecked(self.chkBuHafta.isChecked())
        except Exception:
            pass
        row3.addWidget(chkG)
        row3.addWidget(chkW)
        row3.addStretch(1)
        v.addLayout(row3)

        # -- Opsiyon: eşleşenleri seç --
        chkSel = QCheckBox("Eşleşenleri seç")
        chkSel.setChecked(True)
        v.addWidget(chkSel)

        # -- Butonlar --
        btns = QHBoxLayout()
        btns.addStretch(1)
        btnCancel = QPushButton("Kapat")
        btnOk = QPushButton("Uygula")
        btns.addWidget(btnCancel)
        btns.addWidget(btnOk)
        v.addLayout(btns)

        # === Canlı uygulama (debounce) ===
        timer = QTimer(dlg)
        timer.setSingleShot(True)
        timer.setInterval(120)

        def _apply_now():
            # Ana formdaki değerleri güncelle
            bs = self.txtAraVerilen.blockSignals(True)
            self.txtAraVerilen.setText(txt.text())
            self.txtAraVerilen.blockSignals(bs)

            bs = self.cmbAraKolon.blockSignals(True)
            self.cmbAraKolon.setCurrentIndex(cmb.currentIndex())
            self.cmbAraKolon.blockSignals(bs)

            self.chkRegex.setChecked(chkR.isChecked())
            try:
                self.chkGeciken.setChecked(chkG.isChecked())
                self.chkBuHafta.setChecked(chkW.isChecked())
            except Exception:
                pass

            # Filtre uygula
            self._filtre_verilen()

            # Eşleşenleri seç
            if chkSel.isChecked():
                try:
                    self._select_verilen_matches(txt.text(), chkR.isChecked(), cmb.currentIndex())
                except Exception:
                    pass

        def _schedule_apply(*_):
            timer.start()

        timer.timeout.connect(_apply_now)

        txt.textChanged.connect(_schedule_apply)
        cmb.currentIndexChanged.connect(_schedule_apply)
        chkR.toggled.connect(_schedule_apply)
        chkG.toggled.connect(_schedule_apply)
        chkW.toggled.connect(_schedule_apply)
        chkSel.toggled.connect(_schedule_apply)

        btnCancel.clicked.connect(dlg.reject)
        btnOk.clicked.connect(lambda: (_apply_now(), dlg.accept()))

        _apply_now()
        dlg.exec()

    def _select_verilen_matches(self, text: str, use_regex: bool, col_index: int):
        """Hızlı arama mantığını kullanarak eşleşen satırları SEÇER."""
        import re
        pat = None
        if use_regex and text:
            try:
                pat = re.compile(text, flags=re.IGNORECASE)
            except Exception:
                pat = None

        self.verilen.clearSelection()

        for i in range(self.verilen.rowCount()):
            if col_index == 0:  # Tümü
                s = " ".join([
                    (self.verilen.item(i, c).text() if self.verilen.item(i, c) else "")
                    for c in range(self.verilen.columnCount())
                ])
            else:
                c = col_index - 1  # 0=Tümü, 1=Ders, 2=Kitap, 3=Konu, 4=Süre, 5=Açıklama
                s = (self.verilen.item(i, c).text() if self.verilen.item(i, c) else "")

            match = (pat.search(s or "") is not None) if pat else (
                (text.strip().lower() in (s or "").lower()) if text else False)
            if match:
                self.verilen.selectRow(i)

    # ------------------ Öğrenci Bilgisi / Son Küme Çekme ------------------

    def _current_student_info(self):
        """
        Seçili öğrencinin (id, ad, soyad) bilgisini döndürür.
        Önce formdaki id fonksiyonlarını dener; yoksa ad/soyad'dan çözer.
        """
        ad = (getattr(self, "cmbAd", None).currentText() if getattr(self, "cmbAd", None) else "") or ""
        soyad = (getattr(self, "cmbSoyad", None).currentText() if getattr(self, "cmbSoyad", None) else "") or ""
        ad, soyad = ad.strip(), soyad.strip()

        ogr_id = None
        for attr in ("_secili_ogrenci_id", "secili_ogrenci_id"):
            try:
                f = getattr(self, attr)
                ogr_id = int(f()) if callable(f) else int(f or 0)
                if ogr_id:
                    break
            except Exception:
                pass

        if not ogr_id and (ad or soyad):
            try:
                con = db.get_conn()
                row = con.execute(
                    "SELECT id FROM ogrenci WHERE LOWER(ad)=? AND LOWER(soyad)=? AND aktif=1 "
                    "ORDER BY id DESC LIMIT 1",
                    (ad.lower(), soyad.lower())
                ).fetchone()
                if row:
                    ogr_id = int(row["id"])
            except Exception:
                ogr_id = None

        return ogr_id, ad, soyad

    def _fetch_last_set_for_current_student_from_db(self, ad: str, soyad: str) -> list[dict]:
        """
        Bu öğrencinin veritabanındaki *son* ödev kümesini items listesine çevirir.
        Önce odev_satir (yeni şema), yoksa odev (legacy) tablosuna düşer.
        Dönüş: [{'ders','kitap','konu','dk'}...]
        """
        import sqlite3

        con = db.get_conn()
        ad_s = (ad or "").strip().lower()
        soy_s = (soyad or "").strip().lower()

        row = con.execute("""
            SELECT id FROM ogrenci
            WHERE TRIM(LOWER(ad))=? AND TRIM(LOWER(soyad))=?
            ORDER BY id DESC LIMIT 1
        """, (ad_s, soy_s)).fetchone()
        if not row:
            return []
        ogr_id = int(row["id"] if isinstance(row, sqlite3.Row) else row[0])

        # 1) odev_satir
        r_sat = con.execute("""
            SELECT kume_id
            FROM odev_satir
            WHERE ogrenci_id=? AND kume_id IS NOT NULL
            ORDER BY COALESCE(tarih,'') DESC, id DESC
            LIMIT 1
        """, (ogr_id,)).fetchone()

        if r_sat:
            kume_id = int(r_sat["kume_id"] if isinstance(r_sat, sqlite3.Row) else r_sat[0])
            rows = con.execute("""
                SELECT COALESCE(ders,'') AS ders,
                       COALESCE(kitap,'') AS kitap,
                       COALESCE(konu,'')  AS konu
                FROM odev_satir
                WHERE ogrenci_id=? AND kume_id=?
                ORDER BY id
            """, (ogr_id, kume_id)).fetchall()
            items = [{"ders": r["ders"], "kitap": r["kitap"], "konu": r["konu"], "dk": 0} for r in rows]
            if items:
                return items

        # 2) legacy odev
        r_k = con.execute("""
            SELECT id
            FROM odev_kume
            WHERE ogrenci_id=?
            ORDER BY COALESCE(verilis_tarihi,'') DESC, id DESC
            LIMIT 1
        """, (ogr_id,)).fetchone()
        if not r_k:
            return []

        kume_id = int(r_k["id"] if isinstance(r_k, sqlite3.Row) else r_k[0])
        rows = con.execute("""
            SELECT COALESCE(ders,'')    AS ders,
                   COALESCE(kitap_ad,'') AS kitap,
                   COALESCE(konu_ad,'')  AS konu,
                   COALESCE(saat_dk,0)   AS dk
            FROM odev
            WHERE ogrenci_id=? AND kume_id=?
            ORDER BY id
        """, (ogr_id, kume_id)).fetchall()
        return [{"ders": r["ders"], "kitap": r["kitap"], "konu": r["konu"], "dk": int(r["dk"])} for r in rows]

    # ------------------ Haftalık Plan Oluşturma ------------------

    def _on_weekly_plan(self):
        """'Haftalık Plan Oluştur' butonu."""
        from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem
        from PyQt6.QtCore import QDate
        from ui.weekly_plan import HaftalikPlanDialog, items_from_verilen_table, gun_adlari
        import inspect

        # (İsteğe bağlı) DB teşhis
        try:
            info = db.current_db_info()
            diag = (
                f"DB Yolu: {info.get('db_path')}\n"
                f"Var mı?: {info.get('exists')}   Boyut: {info.get('size')} bayt\n"
                f"Sayım -> ogrenci: {info['counts'].get('ogrenci', '?')}, "
                f"odev_kume: {info['counts'].get('odev_kume', '?')}, "
                f"odev_satir: {info['counts'].get('odev_satir', '?')}"
            )
            # Dilersen kapat: QMessageBox.information(self, "DB Teşhis", diag)
        except Exception:
            pass

        # 1) Verilen tablosundan topla
        tbl = getattr(self, "verilen", None)
        if tbl is None:
            QMessageBox.information(self, "Haftalık Plan", "Verilenler tablosu yok.")
            return
        items = items_from_verilen_table(tbl)

        # 2) Öğrenci adı/soyadı ve tarihler
        ad = (self.cmbAd.currentText() or "").strip() if hasattr(self, "cmbAd") else ""
        soyad = (self.cmbSoyad.currentText() or "").strip() if hasattr(self, "cmbSoyad") else ""
        verilis = QDate.currentDate()
        bitis = self.dtpBitis.date() if hasattr(self, "dtpBitis") else verilis.addDays(7)

        # 3) Eğer 'verilen' boşsa kullanıcıya sor → DB'den son küme
        if not items:
            mb = QMessageBox(self)
            mb.setIcon(QMessageBox.Icon.Question)
            mb.setWindowTitle("Verilen listesi boş")
            mb.setText("Bu öğrencinin 'Verilen' listesi boş görünüyor.\n"
                       "Veritabanındaki SON ödev kümesini kullanmak ister misiniz?")
            btn_use = mb.addButton("Evet, son kümeyi aktar", QMessageBox.ButtonRole.AcceptRole)
            btn_empty = mb.addButton("Boş plan aç", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = mb.addButton("İptal", QMessageBox.ButtonRole.RejectRole)
            for b in mb.buttons():
                b.setMinimumWidth(170)
            mb.exec()

            if mb.clickedButton() is btn_use:
                if not ad or not soyad:
                    QMessageBox.information(self, "Eksik Bilgi", "Lütfen öğrenci ad/soyad seçin.")
                    return
                items = self._fetch_last_set_for_current_student_from_db(ad, soyad)
                if not items:
                    QMessageBox.information(self, "Kayıt yok",
                                            "Bu öğrenci için veritabanında son ödev kümesi bulunamadı.")
                    return
            elif mb.clickedButton() is btn_empty:
                items = []
            else:
                return

        # 4) Diyaloğu aç
        dlg = HaftalikPlanDialog(items, self,
                                 ogrenci_adi=ad,
                                 ogrenci_soyadi=soyad,
                                 verilme_tarihi=verilis,
                                 bitis_tarihi=bitis)
        if not dlg.exec():
            return

        # 5) Kullanıcının işaretlediği günleri açıklamaya yaz
        plan_list = getattr(dlg, "verilen", [])  # [{'ders','kitap','konu','days':[...],'aciklama': '...'}]
        if not plan_list:
            return

        start = dlg.dtBasla.date()
        gun_isimleri = gun_adlari(start)

        for r in range(tbl.rowCount()):
            d = (tbl.item(r, 0).text() if tbl.item(r, 0) else "").strip()
            k = (tbl.item(r, 1).text() if tbl.item(r, 1) else "").strip()
            c = (tbl.item(r, 2).text() if tbl.item(r, 2) else "").strip()

            rec = next((t for t in plan_list
                        if t.get("ders", "") == d and t.get("kitap", "") == k and t.get("konu", "") == c), None)
            if not rec:
                continue

            idx_list = list(rec.get("days", []))
            if not idx_list:
                continue

            aciklama = rec.get("aciklama") or "-".join(gun_isimleri[i] for i in idx_list)

            if not tbl.item(r, 4):
                tbl.setItem(r, 4, QTableWidgetItem(aciklama))
            else:
                tbl.item(r, 4).setText(aciklama)

    # ===========================
    # >>> PART 6/7 — UPDATED <<<
    # ===========================


    import sys
    import sqlite3
    from pathlib import Path
    from typing import Optional, List, Dict, Tuple

    from PyQt6.QtCore import Qt, QObject, QEvent, QDate
    from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
    from PyQt6.QtWidgets import (
        QAbstractItemView, QStyledItemDelegate, QTableWidgetItem, QHeaderView, QMessageBox,
        QInputDialog, QProgressDialog, QStyle, QProxyStyle, QTableWidget
    )

    # --- Checkbox'ı hücrede güvenli şekilde ortalayan stil (PyQt6-safe) ---
    class _CenterCheckStyle(QProxyStyle):
        """
        QTableWidget/QTableView içindeki Item check’lerini hücre ortasına alır.
        Flags’e DOKUNMADAN, sadece çizimi yeniden konumlar.
        """

        def drawPrimitive(self, element, option, painter, widget=None):
            if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck:
                # EĞER METİN VARSA ORTALAMA YAPMA (PyQt varsayılanı solda çizer)
                if hasattr(option, 'text') and option.text:
                     super().drawPrimitive(element, option, painter, widget)
                     return

                r = option.rect
                # kare gibi davran: en küçük kenarı al
                side = min(r.width(), r.height())
                # merkezle
                x = r.x() + (r.width() - side) // 2
                y = r.y() + (r.height() - side) // 2
                new_opt = type(option)(option)
                new_opt.rect = r.__class__(x, y, side, side)
                super().drawPrimitive(element, new_opt, painter, widget)
                return
            super().drawPrimitive(element, option, painter, widget)

    # ---------------------------------------------------------------
    # OdevTakipFormu class'ı içine eklenecek METODLAR (part 6/7)
    # ---------------------------------------------------------------

    def _open_weekly_plan_dialog(self):
        from PyQt6.QtWidgets import QMessageBox, QInputDialog, QTableWidgetItem
        from PyQt6.QtCore import QDate, Qt
        from ui.weekly_plan import HaftalikPlanDialog, items_from_verilen_table, gun_adlari
        import db

        # ------------- mevcut kodun (items okuma / seçenek sorma) aynen kalsın -------------
        tbl = getattr(self, "verilen", None)
        items = items_from_verilen_table(tbl) if tbl is not None else []

        # ... (öğrenci/tarih ve "verilen boşsa" seçenek ekranın aynı) ...
        # ... items doldurulduktan sonra buraya geliyoruz ...

        # ===>>> YENİ: Verilen'e otomatik ekleyen eski yardımcıları geçici kapat
        _orig_add = getattr(self, "_verilen_satir_ekle", None)
        _orig_push = getattr(self, "_haftalik_plana_bas", None)

        def _noop(*a, **k):  # hiçbir şey yapmayan geçici fonksiyon
            return

        try:
            if callable(_orig_add):
                self._verilen_satir_ekle = _noop
            if callable(_orig_push):
                self._haftalik_plana_bas = _noop

            # 3) Diyaloğu oluştur
            dlg = HaftalikPlanDialog(items, self,
                                     ogrenci_adi=(getattr(self, "cmbAd", None).currentText() or "") if getattr(self,
                                                                                                               "cmbAd",
                                                                                                               None) else "",
                                     ogrenci_soyadi=(getattr(self, "cmbSoyad", None).currentText() or "") if getattr(
                                         self, "cmbSoyad", None) else "",
                                     verilme_tarihi=QDate.currentDate(),
                                     bitis_tarihi=(getattr(self, "dtpBitis", None).date() if getattr(self, "dtpBitis",
                                                                                                     None) else QDate.currentDate().addDays(
                                         7)))

            # ===>>> 2) Ödev sütununu 3 satır göster (Ders\nKitap\nKonu)
            try:
                for r, it in enumerate(items):
                    cell = dlg.tbl.item(r, 0)
                    if cell is None:
                        cell = QTableWidgetItem()
                        dlg.tbl.setItem(r, 0, cell)
                    d = (it.get("ders", "") or "").strip()
                    k = (it.get("kitap", "") or "").strip()
                    c = (it.get("konu", "") or "").strip()
                    cell.setText(f"{d}\n{k}\n{c}")
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    # satır yüksekliği 3 satırı rahat göstersin
                    dlg.tbl.setRowHeight(r, max(dlg.tbl.rowHeight(r), 54))
            except Exception:
                pass

            if not dlg.exec():
                return

            # 4) İşaretlenen günleri 'Açıklama'ya yaz (VERİLEN'E SADECE AÇIKLAMA YAZIYORUZ)
            start = dlg.dtBasla.date()
            gunler = gun_adlari(start)

            if tbl:
                # “Verilen” satır sayısı yetmiyorsa artır (sadece açıklama yazmak için)
                if tbl.rowCount() < len(items):
                    tbl.setRowCount(len(items))
                    for r in range(tbl.rowCount()):
                        for c in range(5):
                            if not tbl.item(r, c):
                                tbl.setItem(r, c, QTableWidgetItem(""))

                for r in range(len(items)):
                    idxs = []
                    for c in range(1, 8):  # 1..7 gün sütunları
                        it = dlg.tbl.item(r, c)
                        if it and (it.text() or "").strip():
                            idxs.append(c - 1)
                    if not idxs:
                        continue
                    acik = "-".join(gunler[i] for i in idxs)
                    if not tbl.item(r, 4):
                        tbl.setItem(r, 4, QTableWidgetItem(acik))
                    else:
                        tbl.item(r, 4).setText(acik)

        finally:
            # ===>>> Geçici kilidi kaldır: eski fonksiyonları geri yükle
            if _orig_add is not None:
                self._verilen_satir_ekle = _orig_add
            if _orig_push is not None:
                self._haftalik_plana_bas = _orig_push

    def _export_verilen_as_items(self):
        """
        'verilen' QTableWidget'ından satırları güvenli okur.
        Çıktı: [{'ders','kitap','konu','dk'} ...]  (başlığa göre eşler)
        """
        from PyQt6.QtWidgets import QTableWidgetItem
        t = getattr(self, "verilen", None)
        if t is None:
            return []

        # başlık -> kolon
        hdr_ix = {}
        for c in range(t.columnCount()):
            it = t.horizontalHeaderItem(c)
            key = (it.text() if it else "").strip().lower()
            hdr_ix[key] = c

        def col(*names):
            for n in names:
                n = n.lower()
                if n in hdr_ix:
                    return hdr_ix[n]
            return None

        ci_ders = col("ders")
        ci_kitap = col("kitap")
        ci_konu = col("konu")
        ci_dk = col("süre(dk)", "süre", "dk")

        out = []
        for r in range(t.rowCount()):
            def val(ci):
                if ci is None or ci < 0:
                    return ""
                it = t.item(r, ci)
                return (it.text() if isinstance(it, QTableWidgetItem) and it else "").strip()

            ders = val(ci_ders)
            kitap = val(ci_kitap)
            konu = val(ci_konu)
            dk_s = val(ci_dk)
            try:
                dk = int(dk_s) if dk_s else 0
            except Exception:
                dk = 0

            if ders or kitap or konu or dk:
                out.append({"ders": ders, "kitap": kitap, "konu": konu, "dk": dk})
        return out

    def _bind_items_to_verilen(self, items):
        """
        Sağdaki 'verilen' tablosunu verilen items listesine (ders/kitap/konu/dk) göre yeniler.
        """
        from PyQt6.QtWidgets import QTableWidgetItem
        t = self.verilen
        t.blockSignals(True)
        t.setUpdatesEnabled(False)
        try:
            t.clearContents()
            t.setRowCount(len(items))
            for r, it in enumerate(items):
                t.setItem(r, 0, QTableWidgetItem(it.get("ders", "")))
                t.setItem(r, 1, QTableWidgetItem(it.get("kitap", "")))
                t.setItem(r, 2, QTableWidgetItem(it.get("konu", "")))
                dk = it.get("dk", 0)
                t.setItem(r, 3, QTableWidgetItem(str(int(dk) if dk else 0)))
                # Açıklama (4) boş kalsın; diyalogdan sonra yazacağız
        finally:
            t.setUpdatesEnabled(True)
            t.blockSignals(False)
        try:
            self._toplam_sure_guncelle()
        except Exception:
            pass

    def _db_path(self) -> str:
        """
        Veritabanı dosyasının yolunu güvenli biçimde bulur.
        Öncelik sırası:
          1) self.db_path (varsa dışarıdan atanmış)
          2) Çalışan uygulamanın (frozen/exe) klasörü
          3) Proje kökü (bu dosyanın iki üstünde) / veritabani.db
          4) Bu dosyanın bir üstünde / veritabani.db
          5) Kullanıcı dizini ~/.yks_lgs_manager/veritabani.db
        İlk mevcut olanı döndürür; hiçbiri yoksa 5)’i döndürür.
        """
        # 1) Dışarıdan atanmış özel yol
        custom = getattr(self, "db_path", None)
        if custom:
            p = Path(custom)
            if p.exists():
                return str(p)

        candidates: List[Path] = []

        # 2) Frozen (PyInstaller/py2app) çalıştırma klasörü
        if getattr(sys, "frozen", False):
            app_dir = Path(sys.executable).resolve().parent
            candidates.append(app_dir / "veritabani.db")

        # 3) Proje kökü ( …/ui/weekly_plan.py -> iki üst = proje kökü varsayımı )
        here = Path(__file__).resolve()
        proj_root = here.parent.parent
        candidates.append(proj_root / "veritabani.db")

        # 4) Bir üst klasörde de deneyelim
        candidates.append(here.parent / "veritabani.db")

        # 5) Kullanıcı dizininde gizli klasör
        home_default = Path.home() / ".yks_lgs_manager" / "veritabani.db"
        candidates.append(home_default)

        for c in candidates:
            if c.exists():
                return str(c)

        # Hiçbiri yoksa varsayılanı döndür
        return str(home_default)

    def _fetch_last_set_for_current_student_from_db(self, *, ogrenci_id=None, ad=None, soyad=None):
        """
        Veritabanından öğrencinin EN SON ödev kümesini döndürür.
        Önce yeni şema (odev_satir), yoksa legacy (odev).
        Dönüş: [{'ders','kitap','konu','dk'}]
        """
        import sqlite3, db
        con = db.get_conn()
        try:
            sid = ogrenci_id
            if not sid:
                if ad is None:
                    ad = (getattr(self, "cmbAd", None).currentText() or "").strip() if getattr(self, "cmbAd",
                                                                                               None) else ""
                if soyad is None:
                    soyad = (getattr(self, "cmbSoyad", None).currentText() or "").strip() if getattr(self, "cmbSoyad",
                                                                                                     None) else ""
                row = con.execute(
                    "SELECT id FROM ogrenci WHERE TRIM(LOWER(ad))=? AND TRIM(LOWER(soyad))=? "
                    "ORDER BY id DESC LIMIT 1",
                    ((ad or "").lower(), (soyad or "").lower())
                ).fetchone()
                if not row:
                    return []
                sid = int(row["id"] if isinstance(row, sqlite3.Row) else row[0])

            # 1) odev_satir
            r = con.execute(
                "SELECT kume_id FROM odev_satir WHERE ogrenci_id=? AND kume_id IS NOT NULL "
                "ORDER BY COALESCE(tarih,'') DESC, id DESC LIMIT 1", (sid,)
            ).fetchone()
            if r:
                kume_id = int(r["kume_id"] if isinstance(r, sqlite3.Row) else r[0])
                rows = con.execute(
                    "SELECT COALESCE(ders,'') AS ders, COALESCE(kitap,'') AS kitap, COALESCE(konu,'') AS konu "
                    "FROM odev_satir WHERE ogrenci_id=? AND kume_id=? ORDER BY id",
                    (sid, kume_id)
                ).fetchall()
                items = [{"ders": rr["ders"], "kitap": rr["kitap"], "konu": rr["konu"], "dk": 0} for rr in rows]
                if items:
                    return items

            # 2) legacy odev/odev_kume
            rk = con.execute(
                "SELECT id FROM odev_kume WHERE ogrenci_id=? "
                "ORDER BY COALESCE(verilis_tarihi,'') DESC, id DESC LIMIT 1", (sid,)
            ).fetchone()
            if not rk:
                return []
            kume_id = int(rk["id"] if isinstance(rk, sqlite3.Row) else rk[0])
            rows = con.execute(
                "SELECT COALESCE(ders,'') AS ders, COALESCE(kitap_ad,'') AS kitap, "
                "COALESCE(konu_ad,'') AS konu, COALESCE(saat_dk,0) AS dk "
                "FROM odev WHERE ogrenci_id=? AND kume_id=? ORDER BY id",
                (sid, kume_id)
            ).fetchall()
            return [{"ders": rr["ders"], "kitap": rr["kitap"], "konu": rr["konu"], "dk": int(rr["dk"])} for rr in rows]
        finally:
            try:
                con.close()
            except Exception:
                pass

    def _open_weekly_plan_dialog(self):
        """
        'Haftalık Plan Oluştur' butonu:
          - Verilen tablosu doluysa onu kullanır.
          - Boşsa: Son kümeyi DB'den getirmeyi ya da 'Boş plan' oluşturmayı teklif eder.
          - Diyalog açıkken Verilenler tablosu YAN ETKİYE KAPALIDIR (hiçbir satır eklenmez).
          - Kullanıcı 'Planı Uygula' (OK) demezse Verilenler'deki olası kirlenmeler geri alınır.
          - OK denirse SADECE 'Açıklama' sütunu güncellenir (satır ekleme yok).
        """
        from PyQt6.QtCore import QDate
        from PyQt6.QtWidgets import QMessageBox, QInputDialog, QTableWidgetItem
        from ui.weekly_plan import HaftalikPlanDialog, items_from_verilen_table, gun_adlari
        import copy
        import db

        # ---------- Yardımcı: Verilen yan etkilerini kilitle ----------
        class _VerilenNoSideEffects:
            """
            Diyalog açıkken Verilen tablosuna satır eklemeyi/oynamayı engeller.
            - itemChanged sinyalini geçici kapatır,
            - _verilen_satir_ekle ve _haftalik_plana_bas (varsa) no-op yapılır,
            - çıkışta her şeyi geri yükler,
            - İptal durumunda eklenmiş fazladan satırlar saptanır ve silinir.
            """

            def __init__(self, owner, will_apply_callable):
                self.o = owner
                self._will_apply = will_apply_callable
                self._orig_add_row = None
                self._orig_bulk = None
                self._signals_blocked = False
                self._row_snapshot = None

            def __enter__(self):
                t = getattr(self.o, "verilen", None)
                if t is not None:
                    # mevcut satırları (yalnızca sayım) not et
                    self._row_snapshot = t.rowCount()
                    # sinyalleri blokla
                    try:
                        t.blockSignals(True)
                        self._signals_blocked = True
                    except Exception:
                        pass
                # satır ekleyen fonksiyonları no-op yap
                if hasattr(self.o, "_verilen_satir_ekle") and callable(self.o._verilen_satir_ekle):
                    self._orig_add_row = self.o._verilen_satir_ekle
                    self.o._verilen_satir_ekle = lambda *a, **k: None
                if hasattr(self.o, "_haftalik_plana_bas") and callable(self.o._haftalik_plana_bas):
                    self._orig_bulk = self.o._haftalik_plana_bas
                    self.o._haftalik_plana_bas = lambda *a, **k: None
                return self

            def __exit__(self, exc_type, exc, tb):
                # fonksiyonları geri yükle
                if self._orig_add_row is not None:
                    self.o._verilen_satir_ekle = self._orig_add_row
                if self._orig_bulk is not None:
                    self.o._haftalik_plana_bas = self._orig_bulk
                # sinyalleri aç + kirlenme olduysa ve UYGULAMA yapılmadıysa geri al
                t = getattr(self.o, "verilen", None)
                if t is not None and self._row_snapshot is not None:
                    try:
                        if not self._will_apply():
                            # İptal/kapama: fazla eklenmiş satırları temizle
                            while t.rowCount() > self._row_snapshot:
                                t.removeRow(t.rowCount() - 1)
                    except Exception:
                        pass
                    if self._signals_blocked:
                        try:
                            t.blockSignals(False)
                        except Exception:
                            pass

        # ---------- 1) Verilen tablosunu oku ----------
        tbl = getattr(self, "verilen", None)
        items = items_from_verilen_table(tbl) if tbl is not None else []

        # ---------- 2) Öğrenci ve tarihler ----------
        ogr_id = None
        try:
            if hasattr(self, "_secili_ogrenci_id"):
                ogr_id = int(self._secili_ogrenci_id() or 0)
        except Exception:
            ogr_id = None

        ad = (getattr(self, "cmbAd", None).currentText() or "").strip() if getattr(self, "cmbAd", None) else ""
        soyad = (getattr(self, "cmbSoyad", None).currentText() or "").strip() if getattr(self, "cmbSoyad", None) else ""
        verilis = QDate.currentDate()
        bitis = getattr(self, "dtpBitis", None).date() if getattr(self, "dtpBitis", None) else verilis.addDays(7)

        # ---------- 3) Verilen boşsa seçenek sun ----------
        if not items:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setWindowTitle("Verilen listesi boş")
            msg.setText("Bu öğrencinin 'Verilen' listesi boş görünüyor.")
            msg.setInformativeText(
                "Son kaydedilen ödev kümesini veritabanından alayım mı, yoksa boş bir plan mı açalım?")
            btn_use = msg.addButton("Evet, son kümeyi aktar", QMessageBox.ButtonRole.AcceptRole)
            btn_empty = msg.addButton("Boş plan aç", QMessageBox.ButtonRole.DestructiveRole)
            msg.addButton("İptal", QMessageBox.ButtonRole.RejectRole)
            for b in msg.buttons():
                b.setMinimumWidth(170)
            msg.exec()
            clicked = msg.clickedButton()

            if clicked is btn_use:
                if not ogr_id:
                    QMessageBox.information(self, "Bilgi", "Öğrenci seçimini/ad-soyadı kontrol edin.")
                    return
                con = db.get_conn()
                try:
                    row = con.execute(
                        "SELECT id FROM odev_kume WHERE ogrenci_id=? "
                        "ORDER BY COALESCE(verilis_tarihi,'') DESC, id DESC LIMIT 1",
                        (ogr_id,)
                    ).fetchone()
                    if not row:
                        QMessageBox.information(self, "Bilgi",
                                                "Bu öğrenci için veritabanında son ödev kümesi bulunamadı.")
                        return
                    kume_id = int(row["id"] if hasattr(row, "__getitem__") else row[0])

                    # yeni şema yardımcı varsa
                    try:
                        items_db = db.kume_satirlari(con, kume_id)
                    except Exception:
                        items_db = []

                    if not items_db:
                        rows = con.execute("""
                            SELECT COALESCE(ders,'')    AS ders,
                                   COALESCE(kitap_ad,'') AS kitap,
                                   COALESCE(konu_ad,'')  AS konu,
                                   COALESCE(saat_dk,0)   AS dk
                            FROM odev
                            WHERE ogrenci_id=? AND kume_id=?
                            ORDER BY id
                        """, (ogr_id, kume_id)).fetchall()
                        items_db = [{"ders": r["ders"], "kitap": r["kitap"], "konu": r["konu"], "dk": int(r["dk"])}
                                    for r in rows]

                    if not items_db:
                        QMessageBox.information(self, "Bilgi", "Son ödev kümesinde satır bulunamadı.")
                        return

                    items = items_db

                finally:
                    try:
                        con.close()
                    except Exception:
                        pass

            elif clicked is btn_empty:
                n, ok = QInputDialog.getInt(self, "Boş Plan", "Kaç satır oluşturulsun?", 10, 1, 200, 1)
                if not ok:
                    return
                dk, ok = QInputDialog.getInt(self, "Varsayılan Süre", "Her satır için varsayılan süre (dk):", 30, 0,
                                             600, 5)
                if not ok:
                    return
                items = [{"ders": "", "kitap": "", "konu": "", "dk": int(dk)} for _ in range(int(n))]
            else:
                return  # iptal

        # >>> Diyalog açıkken yan etkileri kilitle
        _apply_flag = {"ok": False}  # kapanışta OK mi oldu?

        def _will_apply():
            return _apply_flag["ok"]

        # (ÖNEMLİ) HaftalikPlanDialog'a KOPYA gönder (referans sızıntısını önle)
        safe_items = copy.deepcopy(items)

        with _VerilenNoSideEffects(self, _will_apply):
            dlg = HaftalikPlanDialog(safe_items, self,
                                     ogrenci_adi=ad, ogrenci_soyadi=soyad,
                                     verilme_tarihi=verilis, bitis_tarihi=bitis,
                                     gunluk_hedef=self.spHedefSure.value() if hasattr(self, "spHedefSure") else 90,
                                     varsayilan_sure=self._get_default_sure())
            if not dlg.exec():
                _apply_flag["ok"] = False
                return
            _apply_flag["ok"] = True  # Kullanıcı 'Planı Uygula' dedi

            # Günlük hedefi senkronize et
            if hasattr(self, "spHedefSure") and hasattr(dlg, "spGunluk"):
                self.spHedefSure.setValue(dlg.spGunluk.value())

            # ---------- 4) 'Açıklama' ve 'Süre(dk)' sütununu yaz ----------
            start = dlg.dtBasla.date()
            gunler = gun_adlari(start)

            # Eğer Verilen listesi boş açıldıysa, burada da SATIR EKLEME YAPMIYORUZ.
            # Yalnızca eşleşen mevcut satırların Süre ve Açıklama hücreleri güncellenir.
            tbl = getattr(self, "verilen", None)
            if tbl:
                # Dialog'un içindeki seçili günleri oku
                # (dialog tarafında 'verilen' listesi yoksa tablodan hücreleri kontrol ediyoruz)
                for r in range(min(tbl.rowCount(), dlg.tbl.rowCount())):
                    # Süre güncelle (Haftalık plan dialogunda değiştirilmiş olabilir)
                    if r < len(dlg.items):
                        item_dk = dlg.items[r].get("dk")
                        if item_dk and int(item_dk) > 0:
                            if not tbl.item(r, 3):
                                tbl.setItem(r, 3, QTableWidgetItem(str(item_dk)))
                            else:
                                tbl.item(r, 3).setText(str(item_dk))

                    idxs = []
                    for c in range(1, 8):  # 1..7 gün sütunları
                        it = dlg.tbl.item(r, c)
                        if it and (it.text() or "").strip():
                            idxs.append(c - 1)
                    if not idxs:
                        continue
                    acik = "-".join(gunler[i] for i in idxs)
                    if not tbl.item(r, 4):
                        tbl.setItem(r, 4, QTableWidgetItem(acik))
                    else:
                        tbl.item(r, 4).setText(acik)
                try:
                    self._toplam_sure_guncelle()
                except Exception:
                    pass

    # ---- Excel aktarım yardımcıları ----
    def _normalize_sheet_name(self, name: str, used: set[str]) -> str:
        bad = set(r':\/?*[]')
        clean = ''.join(ch for ch in (name or "Sayfa") if ch not in bad).strip() or "Sayfa"
        clean = clean[:31]
        base = clean
        i = 2
        while clean in used:
            suf = f"_{i}"
            clean = base[:31 - len(suf)] + suf
            i += 1
        used.add(clean)
        return clean

    def _qw_table_to_matrix(self, tbl: QTableWidget) -> Tuple[List[str], List[List[str]], List[List[str]]]:
        """
        QTableWidget -> (headers, rows, colors)
        - 1. sütun 'Konu', sonrakiler kitap adları
        - Hücre değeri: tikliyse '✔', değilse ''
        - colors: her hücre için 'RRGGBB' (başında # YOK) ya da '' (boyama yok)
        """
        # ---- Başlıklar ----
        headers = []
        for c in range(tbl.columnCount()):
            hi = tbl.horizontalHeaderItem(c)
            headers.append((hi.text() if hi else "").strip())

        rows, colors = [], []

        for r in range(tbl.rowCount()):
            row_vals, row_cols = [], []
            for c in range(tbl.columnCount()):
                it = tbl.item(r, c)

                # --- Metin / tik ---
                if it and c >= 1 and it.checkState() == Qt.CheckState.Checked:
                    txt = "✔"
                else:
                    txt = (it.text() if it else "") or ""
                row_vals.append(txt.strip())

                # --- Arka plan rengi ---
                if not it:
                    row_cols.append("")  # hiç boyama yok
                    continue

                bg = it.background()
                # ŞEFFAF ise hiç boyama yapma
                try:
                    if bg.style() == Qt.BrushStyle.NoBrush:
                        row_cols.append("")
                        continue
                except Exception:
                    pass

                col = bg.color()
                if not col.isValid():
                    row_cols.append("")
                    continue

                hexrgb = col.name().lstrip("#").upper()  # RRGGBB
                if hexrgb == "FFFFFF":
                    row_cols.append("")
                else:
                    row_cols.append(hexrgb)

            rows.append(row_vals)
            colors.append(row_cols)

        return headers, rows, colors

    def _export_all_lists_to_excel(self):
        """
        Sekmelerdeki TÜM ders tablolarını tek .xlsx'e aktarır.
        - Her ders bir sheet
        - Tikli hücrelere '✔' yazılır ve ortalanır
        - Hücre arka plan renkleri (sarı/yeşil/kırmızı) aynen basılır
        - 'Verilen' tablosu DAHİL DEĞİL
        """
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from PyQt6.QtCore import QDate
        from openpyxl.styles import PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        if not getattr(self, "_ders_tablolari", None):
            QMessageBox.information(self, "Excel Aktar", "Aktarılacak ders listesi bulunamadı.")
            return

        default = f"odev_listeleri_{QDate.currentDate().toString('yyyyMMdd')}.xlsx"
        out_path, _ = QFileDialog.getSaveFileName(self, "Excel dosyası kaydet", default, "Excel (*.xlsx)")
        if not out_path:
            return

        # Sekme sırası -> Excel sheet sırası
        used_names, seen, ordered = set(), set(), []
        for i in range(self.tabs.count()):
            title = self.tabs.tabText(i) or ""
            key = title.lower().replace(" ", "_")
            tbl = (self._ders_tablolari or {}).get(key)
            if tbl and tbl not in seen:
                ordered.append((self._normalize_sheet_name(title, used_names), tbl))
                seen.add(tbl)
        for key, tbl in (self._ders_tablolari or {}).items():
            if tbl and tbl not in seen:
                ordered.append((self._normalize_sheet_name(key.upper().replace("_", " "), used_names), tbl))
                seen.add(tbl)

        if not ordered:
            QMessageBox.information(self, "Excel Aktar", "Aktarılacak tablo bulunamadı.")
            return

        # Pandas varsa hızlı yaz, sonra openpyxl ile stilleri uygula
        try:
            try:
                import pandas as pd  # opsiyonel
            except Exception:
                pd = None

            if pd is not None:
                with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
                    # önce veri
                    for sheet, tbl in ordered:
                        headers, rows, _ = self._qw_table_to_matrix(tbl)
                        pd.DataFrame(rows, columns=headers).to_excel(xw, index=False, sheet_name=sheet)

                    # sonra biçim
                    wb = xw.book
                    for sheet, tbl in ordered:
                        ws = wb[sheet]
                        headers, rows, colors = self._qw_table_to_matrix(tbl)

                        for r_idx, (vals, cols) in enumerate(zip(rows, colors), start=2):  # 1. satır başlık
                            for c_idx, hexrgb in enumerate(cols, start=1):
                                if hexrgb:
                                    argb = "FF" + hexrgb  # ARGB zorunlu
                                    ws.cell(row=r_idx, column=c_idx).fill = PatternFill(
                                        fill_type="solid", start_color=argb, end_color=argb
                                    )
                                if c_idx >= 2 and vals[c_idx - 1] == "✔":
                                    ws.cell(row=r_idx, column=c_idx).alignment = Alignment(horizontal="center",
                                                                                           vertical="center")

                        # basit otomatik genişlik
                        from openpyxl.utils import get_column_letter
                        for c_idx in range(1, len(headers) + 1):
                            letter = get_column_letter(c_idx)
                            mx = len(str(ws.cell(row=1, column=c_idx).value or ""))
                            for r in range(2, ws.max_row + 1):
                                v = ws.cell(row=r, column=c_idx).value
                                mx = max(mx, len(str(v or "")))
                            ws.column_dimensions[letter].width = min(mx + 2, 40)
            else:
                # pandas yoksa doğrudan openpyxl
                from openpyxl import Workbook
                wb = Workbook()
                try:
                    wb.remove(wb.active)
                except Exception:
                    pass

                for sheet, tbl in ordered:
                    ws = wb.create_sheet(title=sheet)
                    headers, rows, colors = self._qw_table_to_matrix(tbl)

                    ws.append(headers)
                    for r_vals in rows:
                        ws.append(r_vals)

                    from openpyxl.styles import PatternFill, Alignment
                    for r_idx, (vals, cols) in enumerate(zip(rows, colors), start=2):
                        for c_idx, hexrgb in enumerate(cols, start=1):
                            if hexrgb:
                                argb = "FF" + hexrgb
                                ws.cell(row=r_idx, column=c_idx).fill = PatternFill(
                                    fill_type="solid", start_color=argb, end_color=argb
                                )
                            if c_idx >= 2 and vals[c_idx - 1] == "✔":
                                ws.cell(row=r_idx, column=c_idx).alignment = Alignment(horizontal="center",
                                                                                       vertical="center")

                    from openpyxl.utils import get_column_letter
                    for c_idx in range(1, len(headers) + 1):
                        letter = get_column_letter(c_idx)
                        mx = len(str(ws.cell(row=1, column=c_idx).value or ""))
                        for r in range(2, ws.max_row + 1):
                            v = ws.cell(row=r, column=c_idx).value
                            mx = max(mx, len(str(v or "")))
                        ws.column_dimensions[letter].width = min(mx + 2, 40)

                wb.save(out_path)

            QMessageBox.information(self, "Excel Aktar", f"Listeler kaydedildi:\n{out_path}")

        except Exception as e:
            QMessageBox.critical(self, "Excel Aktar", f"Hata oluştu:\n{e}")



    def _is_done_any(self, ogr_id: int, ders: str, kitap: str, konu: str) -> bool:
        """Aynı ders/kitap/konu üçlüsünden herhangi bir kümede 'yapıldı' var mı?"""
        import db
        row = db.get_conn().execute("""
               SELECT 1
               FROM odev_parca p
               JOIN odev_kume k ON k.id = p.kume_id
               WHERE k.ogrenci_id=? AND p.ders=? AND p.kitap=? AND p.konu=? AND p.yapildi=1
               LIMIT 1
           """, (ogr_id, ders, kitap, konu)).fetchone()
        return bool(row)

    def _apply_global_done_for_current(self):
        """
        Seçili öğrencide 'herhangi bir kopyası yapılmış' olan bütün kalemleri
        Ödev Takip gridinde yeşil/kilitli hale getirir.
        """
        import db
        ogr_id = self._secili_ogrenci_id()
        if not ogr_id:
            return

        rows = db.get_conn().execute("""
               SELECT p.ders, p.kitap, p.konu
               FROM odev_parca p
               JOIN odev_kume k ON k.id = p.kume_id
               WHERE k.ogrenci_id=? AND p.yapildi=1
               GROUP BY p.ders, p.kitap, p.konu
           """, (ogr_id,)).fetchall()
        done_set = {(r["ders"], r["kitap"], r["konu"]) for r in rows}

        for (ders, kitap, konu) in done_set:
            self._lock_cell_done(ders, kitap, konu)

    def _lock_cell_done(self, ders: str, kitap: str, konu: str):
        """
        İlgili hücreyi bul, yeşil yap ve kullanıcı girişini kapat (mevcut stile uydur).
        """
        try:
            t, r, c = self._hucre_bul(ders, kitap, konu)  # sende var
            if t is None:
                return
            it = t.item(r, c)
            if not it:
                return
            it.setCheckState(Qt.CheckState.Checked)
            # Düzenleme ve tıklamayı kapat
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsEnabled)
            # Tema uyumlu yeşil (alternating base) – istersen sabit yeşil kullan
            it.setBackground(self.palette().alternateBase())
        except Exception:
            pass

    # ------- Progress (gerekirse fallback) --------------------------------
    def _prg_show(self, baslik="İşlem sürüyor…", aciklama=""):
        from PyQt6.QtCore import Qt, QCoreApplication
        self._prg = None
        self._prg_is_qpd = False
        try:
            try:
                from .progress import IlerlemePenceresi  # homework_form.py UI paketindeyse
            except Exception:
                from progress import IlerlemePenceresi  # proje kökünde progress.py varsa

            dlg = IlerlemePenceresi(baslik, self)
            dlg.setWindowModality(Qt.WindowModality.NonModal)
            if aciklama:
                dlg.lbl.setText(aciklama)
            dlg.guncelle(1)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            dlg.repaint()
            QCoreApplication.processEvents()
            self._prg = dlg
            self._prg_is_qpd = False
        except Exception:
            dlg = QProgressDialog(aciklama or "Lütfen bekleyiniz…", None, 0, 100, self)
            dlg.setWindowTitle(baslik)
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            dlg.setCancelButton(None)
            dlg.setAutoClose(False)
            dlg.setAutoReset(False)
            dlg.setMinimumDuration(0)
            dlg.setValue(1)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            dlg.repaint()
            from PyQt6.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            self._prg = dlg
            self._prg_is_qpd = True

    def _prg_update(self, yuzde: int, yazi: str = None):
        from PyQt6.QtCore import QCoreApplication
        if not getattr(self, "_prg", None):
            return
        try:
            y = max(0, min(100, int(yuzde)))
            if self._prg_is_qpd:
                if yazi:
                    self._prg.setLabelText(yazi)
                self._prg.setValue(y)
            else:
                if yazi:
                    self._prg.lbl.setText(yazi)
                self._prg.guncelle(y)
            self._prg.repaint()
            QCoreApplication.processEvents()
        except Exception:
            pass

    def _prg_close(self):
        if getattr(self, "_prg", None):
            try:
                self._prg.close()
            except Exception:
                pass
        self._prg = None
        self._prg_is_qpd = False

    # ------- Tek noktadan görsellik --------------------------------------
    def _apply_tables_visuals(self):
        """
        Tek noktadan görsellik (stabil sürüm):
        - Hover vurgusu: açık mavi (hücre) + başlıklarda açık sarı/koyu mavi yazı.
        - Satır yüksekliği kompakt.
        - Sütun ve satır arası çok hafif gri ayraçlar.
        - QStyleOptionButton KULLANMADAN (PyQt6-safe).
        """
        import weakref

        # ---- Renk Ayarları ----
        HOVER_CELL_BG = QColor("#DDEFFF")  # Açık mavi hover
        HOVER_HDR_BG = QColor("#FFF9E6")  # Açık sarı başlık hover
        HOVER_HDR_FG = QColor("#0056B3")  # Koyu mavi yazı
        COL_SEP_COLOR = QColor("#E3E6EB")  # Dikey ayraç
        ROW_SEP_COLOR = QColor("#E9EBEF")  # Satır ayraç

        # ---- Hücre ve çizgi delege ----
        class _GridDelegate(QStyledItemDelegate):
            def paint(self, painter: QPainter, option, index):
                super().paint(painter, option, index)
                painter.save()
                try:
                    pen = QPen(COL_SEP_COLOR)
                    painter.setPen(pen)
                    # Dikey çizgi
                    x = option.rect.right()
                    painter.drawLine(x, option.rect.top(), x, option.rect.bottom())
                    # Yatay çizgi (satırlar arası)
                    painter.setPen(QPen(ROW_SEP_COLOR))
                    y = option.rect.bottom()
                    painter.drawLine(option.rect.left(), y, option.rect.right(), y)
                finally:
                    painter.restore()

        # ---- Hover filtresi ----
        class _HoverFilter(QObject):
            def __init__(self, table, highlighter, resetter):
                super().__init__(table)
                self._tref = weakref.ref(table)
                self._hl = highlighter
                self._rs = resetter

            def eventFilter(self, obj, ev):
                table = self._tref()
                if not table:
                    return False
                try:
                    if obj is table.viewport():
                        et = ev.type()
                        if et == QEvent.Type.MouseMove:
                            idx = table.indexAt(ev.pos())
                            if idx.isValid():
                                self._hl(table, idx.row(), idx.column())
                            else:
                                self._rs(table)
                        elif et in (QEvent.Type.Leave, QEvent.Type.Hide):
                            self._rs(table)
                except RuntimeError:
                    return False
                return False

        # ---- Hover state yardımcıları ----
        def _hover_reset(table):
            # Hücre rengi geri al
            st = getattr(table, "_hover_prev", None)
            if st:
                r, c, prev_brush = st
                item = table.item(r, c)
                if item:
                    item.setBackground(prev_brush if prev_brush else QBrush())
            table._hover_prev = None

            # Başlık renklerini temizle (tam reset)
            vh = table.verticalHeader()
            for i in range(vh.count()):
                vhi = table.verticalHeaderItem(i)
                if vhi:
                    vhi.setBackground(QBrush())
                    vhi.setForeground(QBrush())
            hh = table.horizontalHeader()
            for j in range(hh.count()):
                hhi = table.horizontalHeaderItem(j)
                if hhi:
                    hhi.setBackground(QBrush())
                    hhi.setForeground(QBrush())

        def _hover_cell(table, row, col):
            _hover_reset(table)
            item = table.item(row, col)
            if not item:
                item = QTableWidgetItem("")
                table.setItem(row, col, item)
            prev_brush = item.background()
            item.setBackground(HOVER_CELL_BG)

            # Başlıklar
            vhi = table.verticalHeaderItem(row)
            if vhi:
                vhi.setBackground(HOVER_HDR_BG)
                vhi.setForeground(HOVER_HDR_FG)
            hi = table.horizontalHeaderItem(col)
            if hi:
                hi.setBackground(HOVER_HDR_BG)
                hi.setForeground(HOVER_HDR_FG)
            table._hover_prev = (row, col, prev_brush)

        # ---- Ortak tablo kurulumu ----
        def _setup_table(table, *, show_vheader: bool):
            table.setShowGrid(False)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setWordWrap(False)
            table.setMouseTracking(True)
            table.viewport().setMouseTracking(True)
            table.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            table.verticalHeader().setVisible(show_vheader)
            table.verticalHeader().setDefaultSectionSize(32)  # daha kompakt

            # İnce çizgiler delegesi (tek sefer)
            if not isinstance(table.itemDelegate(), QStyledItemDelegate) or \
                    not isinstance(table.itemDelegate(), type(_GridDelegate(table))):
                table.setItemDelegate(_GridDelegate(table))

            # Hover filtresi (tek sefer)
            if not hasattr(table, "_hover_filter"):
                table._hover_filter = _HoverFilter(table, _hover_cell, _hover_reset)
                table.viewport().installEventFilter(table._hover_filter)

        # ---- Sağ tablo (verilen) ----
        try:
            if hasattr(self, "verilen") and self.verilen:
                _setup_table(self.verilen, show_vheader=False)
        except Exception:
            pass

        # ---- Sol tablolar ----
        try:
            for tbl in list(getattr(self, "_ders_tablolari", {}).values()):
                if tbl:
                    _setup_table(tbl, show_vheader=True)
        except Exception:
            pass

    # ------ Sol grid(ler) için checkbox ortalama + başlık genişliği ----------
    def _polish_left_tables(self):
        """
        Sol grid(ler):
          - Checkbox'ı stil yoluyla ortala (flags'e DOKUNMA).
          - Kitap sütunlarını başlığa göre sabitle.
        """
        from PyQt6.QtWidgets import QHeaderView

        tablolar = getattr(self, "_ders_tablolari", {}) or {}

        # Stil tek örnek; GC'den koru
        if not hasattr(self, "_center_check_style"):
            self._center_check_style = _CenterCheckStyle()

        for _, t in tablolar.items():
            if not t:
                continue

            # 1) Checkbox'ların ortalanması: tablo viewport’una stili uygula
            try:
                t.viewport().setStyle(self._center_check_style)
            except Exception:
                try:
                    t.setStyle(self._center_check_style)
                except Exception:
                    pass

            # 2) Kitap sütunlarını başlık metnine göre sabitle
            hdr = t.horizontalHeader()
            fm = t.fontMetrics()

            try:
                hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
            except Exception:
                pass

            # 0: Konu; 1..N: kitap sütunları
            for c in range(1, t.columnCount()):
                try:
                    title = (t.horizontalHeaderItem(c).text() or "")
                except Exception:
                    title = ""
                base_px = fm.horizontalAdvance(title)
                width = max(46, min(base_px + 28, 260))  # 28px küçük yastık payı

                try:
                    hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
                    hdr.resizeSection(c, width)
                except Exception:
                    pass

            # Son sütunu asla stretch etme (genişlemesin)
            try:
                hdr.setStretchLastSection(False)
            except Exception:
                pass


# ===========================
# >>> PART 7/7 — UPDATED <<<
# ===========================


# --- Ortalamayı sağlayan stil:
# Eğer part 6/7 içinde zaten tanımlandıysa tekrar tanımlamayalım.
from PyQt6.QtWidgets import QProxyStyle, QStyle

try:
    _CenterCheckStyle  # noqa: F821 (var mı kontrol)
except NameError:
    class _CenterCheckStyle(QProxyStyle):
        """
        Item check indicator'ı (PE_IndicatorItemViewItemCheck) hücre ortasına çizer.
        Flags'e dokunmaz, sadece çizim konumunu değiştirir (PyQt6-safe).
        """

        def drawPrimitive(self, element, option, painter, widget=None):
            if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck and option:
                # EĞER METİN VARSA ORTALAMA YAPMA (PyQt varsayılanı solda çizer)
                if hasattr(option, 'text') and option.text:
                     super().drawPrimitive(element, option, painter, widget)
                     return

                r = option.rect
                # kare gibi davran: en küçük kenarı kullan
                side = min(r.width(), r.height())
                x = r.x() + (r.width() - side) // 2
                y = r.y() + (r.height() - side) // 2
                new_opt = type(option)(option)
                # PyQt6: rect aynı türden olmalı
                from PyQt6.QtCore import QRect
                new_opt.rect = QRect(x, y, side, side)
                super().drawPrimitive(element, new_opt, painter, widget)
                return
            super().drawPrimitive(element, option, painter, widget)

# --------------------------------------------------------------------
# WhatsApp Gönderim Dialogu (Modern arayüz ui/whatsapp_dialog.py üzerinden)
from ui.whatsapp_dialog import WhatsAppGonderDialog


