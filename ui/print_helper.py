# -*- coding: utf-8 -*-
from __future__ import annotations
"""
print_helper.py
Liste/Tablo yazdırma yöneticisi (PyQt6)
- Sütun seçimleri (checkbox), hepsi başlangıçta seçili
- Dikey/Yatay yönlendirme
- Yazıcı seçimi
- Önizleme
- Kenar boşlukları
- Üst/alt not alanları, isteğe bağlı logo
- Ayarların QSettings ile otomatik kaydı / geri yüklenmesi
- Hata denetimleri ve güvenli varsayılanlar
- QTableWidget / QTableView (QAbstractItemModel) / pandas.DataFrame destekler
"""

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Union, Any

from PyQt6.QtCore import Qt, QRectF, QMarginsF, QSettings, QPointF
from PyQt6.QtGui import QFont, QFontMetricsF, QImage, QPainter, QPageLayout, QPageSize, QColor, QTextOption
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGridLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QTableView,
    QTableWidget, QVBoxLayout, QMessageBox, QWidget, QSizePolicy
)

from PyQt6.QtGui import (
    QFont, QFontMetricsF, QImage, QPainter, QPageLayout, QPageSize,
    QColor, QTextOption, QTextDocument, QPen   # ← eklendi ve QPen
)

try:
    import pandas as pd  # opsiyonel
except Exception:
    pd = None


# ---------- Yardımcı veri türleri ----------
RowDict = dict[str, Any]
ExtraInfoFunc = Callable[[RowDict], List[str]]  # her satır için ek satırlar üretir


@dataclass
class PrintProfile:
    """Kalıcı ayarlar profili."""
    org: str = "Kocum"
    app: str = "YKS_LGS_HomeworkManager"
    key: str = "GenelListeYazdir"  # aynı projede farklı listeler için farklı key ver


# ---------- Model Soyutlaması ----------
class _ModelAdapter:
    """
    QTableWidget / QAbstractItemModel / pandas.DataFrame / dict listesi için tek arayüz.
    Checkbox kolonu: yalnızca başlığı 'yap' içerenler (örn. 'Yapıldı').
    """
    def __init__(self, source: Union[QTableWidget, QTableView, Any]):
        self._headers: List[str] = []
        self._rows: List[RowDict] = []

        # Checkbox meta – sadece İSİM bazlı
        self._checkable_names: set[str] = set()
        self._check_states: List[dict[str, bool]] = []  # {header_name: bool}

        # ---------- QTableWidget ----------
        if isinstance(source, QTableWidget):
            self._headers = [
                source.horizontalHeaderItem(c).text() if source.horizontalHeaderItem(c) else f"Col {c+1}"
                for c in range(source.columnCount())
            ]
            # İsimden sez
            self._checkable_names = {h for h in self._headers if "yap" in h.lower()}

            for r in range(source.rowCount()):
                row: RowDict = {}
                row_state: dict[str, bool] = {}
                for c, h in enumerate(self._headers):
                    it = source.item(r, c)
                    row[h] = (it.text() if it else "") or ""
                    if h in self._checkable_names and it is not None:
                        row_state[h] = (it.checkState() == Qt.CheckState.Checked)
                self._rows.append(row)
                self._check_states.append(row_state)
            return

        # ---------- QTableView (model tabanlı) ----------
        if isinstance(source, QTableView):
            model = source.model()
            if model is None:
                raise ValueError("Tablonun modeli bulunamadı.")
            self._headers = [
                str(model.headerData(c, Qt.Orientation.Horizontal) or f"Col {c+1}")
                for c in range(model.columnCount())
            ]
            self._checkable_names = {h for h in self._headers if "yap" in h.lower()}

            for r in range(model.rowCount()):
                row: RowDict = {}
                row_state: dict[str, bool] = {}
                for c, h in enumerate(self._headers):
                    idx = model.index(r, c)
                    row[h] = str(model.data(idx) or "")
                    if h in self._checkable_names:
                        cs = model.data(idx, Qt.ItemDataRole.CheckStateRole)
                        row_state[h] = (cs == Qt.CheckState.Checked)
                self._rows.append(row)
                self._check_states.append(row_state)
            return

        # ---------- pandas.DataFrame ----------
        if pd is not None and isinstance(source, pd.DataFrame):
            self._headers = [str(x) for x in source.columns.tolist()]
            self._checkable_names = {h for h in self._headers if "yap" in h.lower()}

            for _, s in source.iterrows():
                row = {str(k): ("" if (v is None) else str(v)) for k, v in s.items()}
                self._rows.append(row)
                st: dict[str, bool] = {}
                for h in self._checkable_names:
                    v = s.get(h)
                    sval = str(v).strip().lower()
                    st[h] = (v is True) or (sval in {"1", "true", "evet", "✓", "✔", "x"})
                self._check_states.append(st)
            return

        # ---------- dict listesi vb. ----------
        if isinstance(source, Iterable):
            it = list(source)
            if not it:
                self._headers, self._rows = [], []
                self._checkable_names = set()
            else:
                if not isinstance(it[0], dict):
                    raise TypeError("Desteklenmeyen kaynak türü. Dict listesi bekleniyordu.")
                # başlıkları koru
                keys = set()
                for r in it:
                    keys |= set(map(str, r.keys()))
                self._headers = list(keys)
                self._checkable_names = {h for h in self._headers if "yap" in h.lower()}
                for r in it:
                    row = {str(k): ("" if (r.get(k) is None) else str(r.get(k))) for k in self._headers}
                    self._rows.append(row)
                    st: dict[str, bool] = {}
                    for h in self._checkable_names:
                        sval = str(r.get(h, "")).strip().lower()
                        st[h] = sval in {"1", "true", "evet", "✓", "✔", "x"}
                    self._check_states.append(st)
            return

        raise TypeError("Desteklenmeyen kaynak türü: QTableWidget / QTableView / pandas.DataFrame / dict listesi.")


# ---------- Yazdırma Diyaloğu ----------
class ListPrintDialog(QDialog):
    """
    Sütun seçimi, sayfa ayarları, üst/alt not, logo, önizleme ve yazdırma.
    """
    def __init__(
        self,
        parent: Optional[QWidget],
        model_adapter: _ModelAdapter,
        profile: PrintProfile,
        extra_info_callback: Optional[ExtraInfoFunc] = None,
        title: str = "Liste Yazdır"
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        self.profile = profile
        self.adapter = model_adapter
        self.extra_info_callback = extra_info_callback

        # state
        self._selected_columns: List[str] = self.adapter._headers.copy()
        self._logo_path: str = ""
        self._margins_mm = QMarginsF(10, 10, 10, 10)
        self._orientation = QPageLayout.Orientation.Portrait
        self._header_text = ""
        self._footer_text = ""
        self._print_student_extras = False

        # UI
        self._build_ui()
        self._apply_modern_visuals()
        self._load_settings_safely()

    def _apply_modern_visuals(self):
        # Inject modern styles
        self.setStyleSheet(self.styleSheet() + """
            QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QTabWidget::pane { border: 1px solid #d1d5db; border-radius: 6px; top: -1px; }
            QTabBar::tab {
                background: #f3f4f6; color: #374151; padding: 6px 12px;
                border: 1px solid #d1d5db; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: #fff; color: #2563eb; font-weight: bold; border-bottom: 1px solid #fff; }
            QTabBar::tab:hover { background: #e5e7eb; }
            
            QPushButton { 
                border-radius: 6px; padding: 6px 12px; font-weight: 500;
                background-color: #f3f4f6; border: 1px solid #d1d5db; color: #1f2937;
            }
            QPushButton:hover { background-color: #e5e7eb; }
            QPushButton#btnPrimary { background-color: #2563eb; color: white; border: none; }
            QPushButton#btnPrimary:hover { background-color: #1d4ed8; }
            
            QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
                border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; background: white;
            }
            QListWidget { border: 1px solid #d1d5db; border-radius: 6px; }
        """)

    # ---------- UI Kurulumu ----------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # Assuming 'main_widget' should be 'self' and 'lay' should be 'root' for syntactic correctness
        # as 'main_widget' and 'lay' are not defined in the current scope.
        main_widget = self
        lay = root

        tabs = QTabWidget(main_widget)
        # Tab genişlik sorunu için stil (truncated text fix)
        tabs.setStyleSheet("QTabBar::tab { min-width: 120px; padding: 4px; }")
        
        lay.addWidget(tabs)

        # Sütunlar
        w_cols = QWidget(self)
        vcols = QVBoxLayout(w_cols)
        self.chk_all = QCheckBox("Tüm sütunları seç", w_cols)
        self.chk_all.setChecked(True)
        self.chk_all.toggled.connect(self._toggle_all_columns)
        vcols.addWidget(self.chk_all)

        self.lst_cols = QListWidget(w_cols)
        self.lst_cols.setSelectionMode(self.lst_cols.SelectionMode.NoSelection)
        for h in self.adapter._headers:
            it = QListWidgetItem(h)
            it.setCheckState(Qt.CheckState.Checked)
            self.lst_cols.addItem(it)
        vcols.addWidget(self.lst_cols)
        tabs.addTab(w_cols, "Sütunlar")

        # Sayfa & Yazıcı
        w_page = QWidget(self)
        lay_page = QFormLayout(w_page)
        
        self.cmb_orientation = QComboBox(w_page)
        self.cmb_orientation.addItems(["Dikey (Portrait)", "Yatay (Landscape)"])
        self.cmb_orientation.setCurrentIndex(0)
        
        self.chk_fit_width = QCheckBox("Tabloyu sayfa genişliğine sığdır", w_page)
        self.chk_fit_width.setChecked(True)
        
        f = lay_page # Alias
        f.addRow("Yönlendirme:", self.cmb_orientation)
        f.addRow("Sığdırma:", self.chk_fit_width)

        mgrp = QGridLayout()
        self.spn_top = QSpinBox(w_page); self.spn_top.setRange(0, 50); self.spn_top.setValue(10)
        self.spn_left = QSpinBox(w_page); self.spn_left.setRange(0, 50); self.spn_left.setValue(10)
        self.spn_right = QSpinBox(w_page); self.spn_right.setRange(0, 50); self.spn_right.setValue(10)
        self.spn_bottom = QSpinBox(w_page); self.spn_bottom.setRange(0, 50); self.spn_bottom.setValue(10)
        mgrp.addWidget(QLabel("Üst (mm):"), 0, 0); mgrp.addWidget(self.spn_top, 0, 1)
        mgrp.addWidget(QLabel("Sol (mm):"), 0, 2); mgrp.addWidget(self.spn_left, 0, 3)
        mgrp.addWidget(QLabel("Sağ (mm):"), 1, 2); mgrp.addWidget(self.spn_right, 1, 3)
        mgrp.addWidget(QLabel("Alt (mm):"), 1, 0); mgrp.addWidget(self.spn_bottom, 1, 1)
        f.addRow(QLabel("Kenar boşlukları:"), QWidget())
        f.addRow(mgrp)

        # Yazıcı seçimi butonu
        self.btn_pick_printer = QPushButton("Yazıcı Seç / Yapılandır", w_page)
        self.btn_pick_printer.clicked.connect(self._pick_printer)
        f.addRow(self.btn_pick_printer)

        tabs.addTab(w_page, "Sayfa & Yazıcı")

        # Başlık / Alt bilgi
        w_hf = QWidget(self)
        fh = QFormLayout(w_hf)

        self.edt_header = QPlainTextEdit(w_hf); self.edt_header.setPlaceholderText("Üst kısma yazılacak metin (opsiyonel)")
        self.edt_footer = QPlainTextEdit(w_hf); self.edt_footer.setPlaceholderText("Alt kısma yazılacak metin / tavsiyeler")
        self.chk_student_extras = QCheckBox("Öğrenci ek bilgilerini de yazdır (satır altında gösterilir)", w_hf)

        fh.addRow("Başlık:", self.edt_header)
        fh.addRow("Alt bilgi:", self.edt_footer)
        fh.addWidget(self.chk_student_extras)
        # --- Başlık ayarları ---
        hdr_row = QHBoxLayout()
        self.cmb_hdr_align = QComboBox(w_hf); self.cmb_hdr_align.addItems(["Sol", "Orta", "Sağ"])
        self.spn_hdr_size = QSpinBox(w_hf); self.spn_hdr_size.setRange(8, 48); self.spn_hdr_size.setValue(14)
        self.chk_hdr_bold = QCheckBox("Kalın", w_hf); self.chk_hdr_bold.setChecked(True)
        self.spn_hdr_gap = QSpinBox(w_hf); self.spn_hdr_gap.setRange(0, 30); self.spn_hdr_gap.setValue(4)
        hdr_row.addWidget(QLabel("Başlık hizası:")); hdr_row.addWidget(self.cmb_hdr_align)
        hdr_row.addWidget(QLabel("Punto:")); hdr_row.addWidget(self.spn_hdr_size)
        hdr_row.addWidget(self.chk_hdr_bold)
        hdr_row.addWidget(QLabel("Tablo boşluğu (mm):")); hdr_row.addWidget(self.spn_hdr_gap)
        fh.addRow(hdr_row)

        # --- Alt bilgi ayarları ---
        ftr_row = QHBoxLayout()
        self.cmb_ftr_align = QComboBox(w_hf); self.cmb_ftr_align.addItems(["Sol", "Orta", "Sağ"])
        self.spn_ftr_size = QSpinBox(w_hf); self.spn_ftr_size.setRange(8, 36); self.spn_ftr_size.setValue(11)
        self.chk_ftr_bold = QCheckBox("Kalın", w_hf); self.chk_ftr_bold.setChecked(False)
        self.spn_ftr_offset = QSpinBox(w_hf); self.spn_ftr_offset.setRange(0, 30); self.spn_ftr_offset.setValue(0)
        ftr_row.addWidget(QLabel("Alt bilgi hizası:")); ftr_row.addWidget(self.cmb_ftr_align)
        ftr_row.addWidget(QLabel("Punto:")); ftr_row.addWidget(self.spn_ftr_size)
        ftr_row.addWidget(self.chk_ftr_bold)
        ftr_row.addWidget(QLabel("Alt kenardan uzaklık (mm):")); ftr_row.addWidget(self.spn_ftr_offset)
        fh.addRow(ftr_row)
        tabs.addTab(w_hf, "Başlık / Notlar")

        # --- TAB 3: Gelişmiş Özellikler (YENİ) ---
        tab_adv = QWidget()
        form_adv = QFormLayout(tab_adv)
        
        self.chk_info_cards = QCheckBox("Bilgi Kartları (Özet yerine grafik)")
        self.chk_info_cards.setChecked(True)
        form_adv.addRow("İstatistik:", self.chk_info_cards)
        
        self.chk_signature = QCheckBox("İmza ve Onay Kutusu")
        self.chk_signature.setChecked(True)
        form_adv.addRow("Alt Alan:", self.chk_signature)
        
        self.chk_color_strip = QCheckBox("Ders Renk Şeritleri")
        self.chk_color_strip.setChecked(True)
        form_adv.addRow("Görsellik:", self.chk_color_strip)
        
        self.chk_motivation = QCheckBox("Motivasyon Kutusu")
        self.chk_motivation.setChecked(False)
        form_adv.addRow("Ekstra:", self.chk_motivation)
        
        tabs.addTab(tab_adv, "Gelişmiş")

        # Logo
        w_logo = QWidget(self)
        vl = QVBoxLayout(w_logo)
        self.lbl_logo = QLabel("Seçili logo yok", w_logo)
        self.btn_logo = QPushButton("Logo Seç...", w_logo)
        self.btn_logo_clear = QPushButton("Logoyu Kaldır", w_logo)
        self.btn_logo.clicked.connect(self._choose_logo)
        self.btn_logo_clear.clicked.connect(self._clear_logo)

        # --- Logo seçenekleri ---
        row1 = QHBoxLayout()
        self.cmb_logo_align = QComboBox(w_logo)
        self.cmb_logo_align.addItems(["Sol", "Orta", "Sağ"])
        row1.addWidget(QLabel("Hizalama:")); row1.addWidget(self.cmb_logo_align)
        vl.addLayout(row1)

        row2 = QHBoxLayout()
        self.spn_logo_h = QSpinBox(w_logo); self.spn_logo_h.setRange(8, 50); self.spn_logo_h.setValue(16)
        row2.addWidget(QLabel("Logo yüksekliği (mm):")); row2.addWidget(self.spn_logo_h)
        vl.addLayout(row2)

        row3 = QHBoxLayout()
        self.spn_logo_gap = QSpinBox(w_logo); self.spn_logo_gap.setRange(0, 30); self.spn_logo_gap.setValue(4)
        row3.addWidget(QLabel("Logo alt boşluğu (mm):")); row3.addWidget(self.spn_logo_gap)
        vl.addLayout(row3)

        row4 = QHBoxLayout()
        self.chk_logo_round = QCheckBox("Köşeleri yuvarla", w_logo); self.chk_logo_round.setChecked(True)
        self.chk_logo_shadow = QCheckBox("Gölgelendirme", w_logo); self.chk_logo_shadow.setChecked(True)
        self.chk_logo_border = QCheckBox("İnce çerçeve", w_logo); self.chk_logo_border.setChecked(True)
        row4.addWidget(self.chk_logo_round); row4.addWidget(self.chk_logo_shadow); row4.addWidget(self.chk_logo_border)
        vl.addLayout(row4)

        vl.addWidget(self.lbl_logo)
        hl = QHBoxLayout(); hl.addWidget(self.btn_logo); hl.addWidget(self.btn_logo_clear)
        vl.addLayout(hl)
        vl.addStretch(1)
        tabs.addTab(w_logo, "Logo")

        # Alt butonlar
        btns = QDialogButtonBox(self)
        self.btn_preview = btns.addButton("Önizleme", QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_print = btns.addButton("Yazdır", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_save = btns.addButton("Varsayılanı Kaydet", QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_close = btns.addButton("Kapat", QDialogButtonBox.ButtonRole.RejectRole)
        
        # Style buttons
        self.btn_print.setObjectName("btnPrimary")
        for b in (self.btn_preview, self.btn_save, self.btn_close, self.btn_pick_printer, self.btn_logo, self.btn_logo_clear):
            if isinstance(b, QPushButton):
                b.setObjectName("btnStandard")

        self.btn_preview.clicked.connect(self._preview)
        self.btn_print.clicked.connect(self._do_print)
        self.btn_save.clicked.connect(self._save_settings_safely)
        self.btn_close.clicked.connect(self.reject)

        root.addWidget(btns)

    # ---------- Ayarlar (QSettings) ----------
    def _settings(self) -> QSettings:
        return QSettings(self.profile.org, self.profile.app)

    def _load_settings_safely(self):
        s = self._settings()
        k = self.profile.key

        # --- Yönlendirme (enum->int güvenli) ---
        try:
            ori = int(s.value(f"{k}/orientation", int(QPageLayout.Orientation.Portrait.value)))
            self._orientation = QPageLayout.Orientation(ori)
            self.cmb_orientation.setCurrentIndex(0 if self._orientation == QPageLayout.Orientation.Portrait else 1)
        except Exception:
            self._orientation = QPageLayout.Orientation.Portrait
            self.cmb_orientation.setCurrentIndex(0)

        # --- Kenar boşlukları ---
        try:
            top = int(s.value(f"{k}/margins/top", 10))
            left = int(s.value(f"{k}/margins/left", 10))
            right = int(s.value(f"{k}/margins/right", 10))
            bottom = int(s.value(f"{k}/margins/bottom", 10))
            self.spn_top.setValue(top); self.spn_left.setValue(left)
            self.spn_right.setValue(right); self.spn_bottom.setValue(bottom)
            self._margins_mm = QMarginsF(left, top, right, bottom)
        except Exception:
            pass

        # --- Genişliğe sığdır ---
        self._fit_width = str(s.value(f"{k}/fit_width", "true") or "true").lower() == "true"
        self.chk_fit_width.setChecked(self._fit_width)

        # --- Logo yolu ---
        self._logo_path = str(s.value(f"{k}/logo_path", "") or "")
        self.lbl_logo.setText(self._logo_path if self._logo_path else "Seçili logo yok")

        # --- Başlık/Alt bilgi ---
        self._header_text = str(s.value(f"{k}/header", "") or "")
        self._footer_text = str(s.value(f"{k}/footer", "") or "")
        self.edt_header.setPlainText(self._header_text)
        self.edt_footer.setPlainText(self._footer_text)

        # --- Öğrenci ek satırları ---
        st_extras = str(s.value(f"{k}/student_extras", "false") or "false").lower()
        self._print_student_extras = (st_extras == "true")
        self.chk_student_extras.setChecked(self._print_student_extras)

        # --- Gelişmiş ayarlar ---
        self._adv_info_cards = str(s.value(f"{k}/adv_info_cards", "true") or "true").lower() == "true"
        self.chk_info_cards.setChecked(self._adv_info_cards)
        self._adv_signature = str(s.value(f"{k}/adv_signature", "true") or "true").lower() == "true"
        self.chk_signature.setChecked(self._adv_signature)
        self._adv_color_strip = str(s.value(f"{k}/adv_color_strip", "true") or "true").lower() == "true"
        self.chk_color_strip.setChecked(self._adv_color_strip)
        self._adv_motivation = str(s.value(f"{k}/adv_motivation", "false") or "false").lower() == "true"
        self.chk_motivation.setChecked(self._adv_motivation)

        # --- Sütun seçimleri ---
        saved_cols = s.value(f"{k}/selected_columns", None)
        if saved_cols:
            try:
                saved_cols = list(saved_cols) if isinstance(saved_cols, (list, tuple)) else str(saved_cols).split("||")
                header_set = set(self.adapter._headers)
                for i in range(self.lst_cols.count()):
                    it = self.lst_cols.item(i)
                    it.setCheckState(
                        Qt.CheckState.Checked if (it.text() in saved_cols and it.text() in header_set)
                        else Qt.CheckState.Unchecked
                    )
                self._sync_select_all_checkbox()
            except Exception:
                pass

        # --- Logo görünüm ayarları ---
        try:
            if hasattr(self, "cmb_logo_align"):
                self.cmb_logo_align.setCurrentIndex(int(s.value(f"{k}/logo_align", 0)))
            if hasattr(self, "spn_logo_h"):
                self.spn_logo_h.setValue(int(s.value(f"{k}/logo_h_mm", 16)))
            if hasattr(self, "spn_logo_gap"):
                self.spn_logo_gap.setValue(int(s.value(f"{k}/logo_gap_mm", 4)))
            if hasattr(self, "chk_logo_round"):
                self.chk_logo_round.setChecked(str(s.value(f"{k}/logo_round", "true")).lower() == "true")
            if hasattr(self, "chk_logo_shadow"):
                self.chk_logo_shadow.setChecked(str(s.value(f"{k}/logo_shadow", "true")).lower() == "true")
            if hasattr(self, "chk_logo_border"):
                self.chk_logo_border.setChecked(str(s.value(f"{k}/logo_border", "true")).lower() == "true")
        except Exception:
            pass

        # --- Başlık / Alt Bilgi ayarları ---
        try:
            if hasattr(self, "cmb_hdr_align"):
                self.cmb_hdr_align.setCurrentIndex(int(s.value(f"{k}/hdr_align", 1)))
            if hasattr(self, "spn_hdr_size"):
                self.spn_hdr_size.setValue(int(s.value(f"{k}/hdr_size", 14)))
            if hasattr(self, "chk_hdr_bold"):
                self.chk_hdr_bold.setChecked(str(s.value(f"{k}/hdr_bold", "true")).lower() == "true")
            if hasattr(self, "spn_hdr_gap"):
                self.spn_hdr_gap.setValue(int(s.value(f"{k}/hdr_gap_mm", 4)))

            if hasattr(self, "cmb_ftr_align"):
                self.cmb_ftr_align.setCurrentIndex(int(s.value(f"{k}/ftr_align", 0)))
            if hasattr(self, "spn_ftr_size"):
                self.spn_ftr_size.setValue(int(s.value(f"{k}/ftr_size", 11)))
            if hasattr(self, "chk_ftr_bold"):
                self.chk_ftr_bold.setChecked(str(s.value(f"{k}/ftr_bold", "false")).lower() == "true")
            if hasattr(self, "spn_ftr_offset"):
                self.spn_ftr_offset.setValue(int(s.value(f"{k}/ftr_offset_mm", 0)))
        except Exception:
            pass

    def _save_settings_safely(self):
        # UI'dan güncel değerleri çek
        self._collect_state_from_ui()

        s = self._settings()
        k = self.profile.key
        try:
            # Orientation
            try:
                ori_val = int(self._orientation.value)
            except Exception:
                ori_val = int(QPageLayout.Orientation.Portrait.value)
            s.setValue(f"{k}/orientation", ori_val)

            # Kenar boşlukları
            try:
                s.setValue(f"{k}/margins/top", int(self._margins_mm.top()))
                s.setValue(f"{k}/margins/left", int(self._margins_mm.left()))
                s.setValue(f"{k}/margins/right", int(self._margins_mm.right()))
                s.setValue(f"{k}/margins/bottom", int(self._margins_mm.bottom()))
            except Exception:
                pass

            # Genişliğe sığdır
            s.setValue(f"{k}/fit_width", str(self.chk_fit_width.isChecked()))

            # Logo / başlık / alt bilgi / öğrenci ekleri
            s.setValue(f"{k}/logo_path", self._logo_path or "")
            s.setValue(f"{k}/header", self.edt_header.toPlainText())
            s.setValue(f"{k}/footer", self.edt_footer.toPlainText())
            s.setValue(f"{k}/student_extras", str(self.chk_student_extras.isChecked()))

            # Gelişmiş
            s.setValue(f"{k}/adv_info_cards", str(self.chk_info_cards.isChecked()))
            s.setValue(f"{k}/adv_signature", str(self.chk_signature.isChecked()))
            s.setValue(f"{k}/adv_color_strip", str(self.chk_color_strip.isChecked()))
            s.setValue(f"{k}/adv_motivation", str(self.chk_motivation.isChecked()))
            
            # Sütun seçimleri
            cols = self._selected_columns if getattr(self, "_selected_columns", None) else []
            s.setValue(f"{k}/selected_columns", "||".join(map(str, cols)))

            # Başlık/Alt bilgi ayarları
            if hasattr(self, "cmb_hdr_align"):
                s.setValue(f"{k}/hdr_align", int(self.cmb_hdr_align.currentIndex()))
            if hasattr(self, "spn_hdr_size"):
                s.setValue(f"{k}/hdr_size", int(self.spn_hdr_size.value()))
            if hasattr(self, "chk_hdr_bold"):
                s.setValue(f"{k}/hdr_bold", "true" if self.chk_hdr_bold.isChecked() else "false")
            if hasattr(self, "spn_hdr_gap"):
                s.setValue(f"{k}/hdr_gap_mm", int(self.spn_hdr_gap.value()))

            if hasattr(self, "cmb_ftr_align"):
                s.setValue(f"{k}/ftr_align", int(self.cmb_ftr_align.currentIndex()))
            if hasattr(self, "spn_ftr_size"):
                s.setValue(f"{k}/ftr_size", int(self.spn_ftr_size.value()))
            if hasattr(self, "chk_ftr_bold"):
                s.setValue(f"{k}/ftr_bold", "true" if self.chk_ftr_bold.isChecked() else "false")
            if hasattr(self, "spn_ftr_offset"):
                s.setValue(f"{k}/ftr_offset_mm", int(self.spn_ftr_offset.value()))

            # Sütun seçimleri
            cols = self._selected_columns if getattr(self, "_selected_columns", None) else []
            s.setValue(f"{k}/selected_columns", "||".join(map(str, cols)))

            # Logo görünüm ayarları
            if hasattr(self, "cmb_logo_align"):
                s.setValue(f"{k}/logo_align", int(self.cmb_logo_align.currentIndex()))
            if hasattr(self, "spn_logo_h"):
                s.setValue(f"{k}/logo_h_mm", int(self.spn_logo_h.value()))
            if hasattr(self, "spn_logo_gap"):
                s.setValue(f"{k}/logo_gap_mm", int(self.spn_logo_gap.value()))
            if hasattr(self, "chk_logo_round"):
                s.setValue(f"{k}/logo_round", "true" if self.chk_logo_round.isChecked() else "false")
            if hasattr(self, "chk_logo_shadow"):
                s.setValue(f"{k}/logo_shadow", "true" if self.chk_logo_shadow.isChecked() else "false")
            if hasattr(self, "chk_logo_border"):
                s.setValue(f"{k}/logo_border", "true" if self.chk_logo_border.isChecked() else "false")

            s.sync()
            QMessageBox.information(self, "Kaydedildi", "Varsayılan ayarlar başarıyla kaydedildi.")
        except Exception as e:
            QMessageBox.warning(self, "Uyarı", f"Ayarlar kaydedilemedi:\n{e}")

    # ---------- UI olayları ----------
    def _toggle_all_columns(self, checked: bool):
        for i in range(self.lst_cols.count()):
            it = self.lst_cols.item(i)
            it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _sync_select_all_checkbox(self):
        total = self.lst_cols.count()
        checked = sum(1 for i in range(total) if self.lst_cols.item(i).checkState() == Qt.CheckState.Checked)
        self.chk_all.blockSignals(True)
        self.chk_all.setChecked(checked == total and total > 0)
        self.chk_all.blockSignals(False)

    def _choose_logo(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Logo Seç", "", "Görüntüler (*.png *.jpg *.jpeg *.bmp)")
        if fn:
            self._logo_path = fn
            self.lbl_logo.setText(fn)

    def _clear_logo(self):
        self._logo_path = ""
        self.lbl_logo.setText("Seçili logo yok")

    def _pick_printer(self):
        try:
            pr = QPrinter(QPrinter.PrinterMode.HighResolution)
            dlg = QPrintDialog(pr, self)
            dlg.setWindowTitle("Yazıcı Seç / Yapılandır")
            if dlg.exec() == QDialog.DialogCode.Accepted:
                QMessageBox.information(self, "Yazıcı seçildi", f"Seçilen yazıcı: {pr.printerName() or 'Sistem Varsayılanı'}")
        except Exception as e:
            QMessageBox.warning(self, "Uyarı", f"Yazıcı seçimi başarısız:\n{e}")

    def _collect_state_from_ui(self):
        self._orientation = QPageLayout.Orientation.Portrait if self.cmb_orientation.currentIndex() == 0 else QPageLayout.Orientation.Landscape
        self._margins_mm = QMarginsF(self.spn_left.value(), self.spn_top.value(), self.spn_right.value(), self.spn_bottom.value())
        self._header_text = self.edt_header.toPlainText().strip()
        self._footer_text = self.edt_footer.toPlainText().strip()
        self._print_student_extras = self.chk_student_extras.isChecked()
        self._fit_width = self.chk_fit_width.isChecked()

        # Gelişmiş özellikler
        self._show_info_cards = self.chk_info_cards.isChecked()
        self._show_signature = self.chk_signature.isChecked()
        self._show_color_strip = self.chk_color_strip.isChecked()
        self._show_motivation = self.chk_motivation.isChecked()

        sel = []
        for i in range(self.lst_cols.count()):
            it = self.lst_cols.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                sel.append(it.text())
        self._selected_columns = sel
        self._sync_select_all_checkbox()

    # ---------- Önizleme / Yazdırma ----------
    def _make_printer(self) -> QPrinter:
        pr = QPrinter(QPrinter.PrinterMode.HighResolution)
        layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4), self._orientation, QMarginsF(0, 0, 0, 0))
        pr.setPageLayout(layout)
        return pr

    def _preview(self):
        self._collect_state_from_ui()
        if not self._selected_columns:
            QMessageBox.warning(self, "Uyarı", "En az bir sütun seçmelisiniz.")
            return
        pr = self._make_printer()
        try:
            preview = QPrintPreviewDialog(pr, self)
            preview.setWindowTitle("Yazdırma Önizleme")
            preview.paintRequested.connect(lambda p: self._render_document(p))
            preview.exec()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Önizleme açılamadı:\n{e}")

    def _do_print(self):
        self._collect_state_from_ui()
        if not self._selected_columns:
            QMessageBox.warning(self, "Uyarı", "En az bir sütun seçmelisiniz.")
            return
        pr = self._make_printer()
        try:
            pdlg = QPrintDialog(pr, self)
            pdlg.setWindowTitle("Yazdır")
            if pdlg.exec() != QDialog.DialogCode.Accepted:
                return
            self._render_document(pr)
            QMessageBox.information(self, "Yazdırma", "İşlem gönderildi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yazdırma başarısız:\n{e}")

    # ---------- Çizim (TEK sürüm) ----------
    # --- TEK SEFERLİK ÖZETİ AYARLAMAK İÇİN YARDIMCI ---
    def set_page_summary(self, lines: List[str] | None, position: str = "top"):
        """
        Tabloya TEK SEFERLİK özet bloğu (öğrenci adı, tarih, %tamamlama vb.) eklemek için.
        lines: ["Öğrenci: ...", "Başlangıç: ...", "Bitiş: ...", "%Tamamlama: ...", ...]
        position: "top" (başlık ile tablo arasında) veya "bottom" (sayfanın altına)
        """
        self._page_summary_lines = None if not lines else [str(x) for x in lines if str(x).strip()]
        self._page_summary_position = "bottom" if str(position).lower() == "bottom" else "top"


    # --- ASIL MOTOR (GENEL) ---
    def _render_document_impl(
            self,
            printer: QPrinter,
            page_summary_lines: list[str] | None = None,
            page_summary_position: str = "top"
    ):
        """
        Gelişmiş liste yazdırma:
          - Kelime sarma (wrap) + AlignTop
          - Satır yüksekliği otomatik
          - Dikey/yatay için akıllı kolon oranları
          - Zebra satır, tekrar eden başlık, sayfa numarası
          - Checkbox çizimi
        """
        # --- Gerekli Qt sınıfları (lokal import: isim çakışması olmasın) ---
        from PyQt6.QtCore import Qt, QRectF, QMarginsF, QPointF
        from PyQt6.QtGui import QPainter, QFont, QFontMetricsF, QImage, QColor, QPageLayout

        painter = QPainter(printer)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # ===================== Yardımcılar =====================
        def px_per_mm() -> float:
            return printer.resolution() / 25.4

        def mm(x: float) -> float:
            return float(x) * px_per_mm()

        # sabit iç boşluklar (hücre pedleri)
        P_H, P_V = mm(1.8), mm(1.2)

        def draw_text_box(text: str, x: float, y: float, w: float, 
                          align_ix: int, font: QFont, dry_run: bool = False) -> float:
            """
            painter.drawText ve boundingRect kullanarak metni güvenli çizer/ölçer.
            DPI ölçeklemesi painter üzerinden yapıldığı için font boyutu doğru kalır.
            """
            if not text:
                return y

            painter.save()
            painter.setFont(font)
            
            # Hizalama
            flags = Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
            if align_ix == 1: 
                flags |= Qt.AlignmentFlag.AlignHCenter
            elif align_ix == 2: 
                flags |= Qt.AlignmentFlag.AlignRight
            else:
                flags |= Qt.AlignmentFlag.AlignLeft
            
            # Sınırsız yükseklik varsayımıyla bounding rect al
            # w genişliğinde
            constraint_rect = QRectF(x, y, w, 100000) # yeterince uzun
            
            bound_rect = painter.boundingRect(constraint_rect, flags, text)
            
            if not dry_run:
                painter.drawText(bound_rect, flags, text)
            
            painter.restore()
            
            return y + bound_rect.height() + mm(1.0) # biraz tampon

        def draw_info_cards(items: list[str],
                            x_left: float, x_right: float, y_top: float,
                            font: QFont) -> float:
            """
            Gelişmiş istatistik kartları.
            Yan yana kutucuklar halinde gösterir.
            """
            # Örnek items: ["Öğrenci: Ali", "Dönem: ...", "Tamamlama: %50", ...]
            # Basit parser: ":" ile ayırıp key/value yap
            
            painter.save()
            w_total = x_right - x_left
            
            # Kart sayısı ve genişliği
            # Sadece anlamlı (key:val) olanları al
            cards = []
            for it in items:
                if ":" in it:
                    k, v = it.split(":", 1)
                    cards.append((k.strip(), v.strip()))
            
            if not cards:
                painter.restore()
                # Fallback: düz metin
                return draw_inline_summary(items, x_left, x_right, y_top, font)

            # Kart çizim ayarları
            card_gap = mm(3)
            # Max 3 kart yan yana sığdır
            cols = 3
            card_w = (w_total - (cols - 1) * card_gap) / cols
            card_h = mm(16)
            
            row_y = y_top
            
            for i, (k, v) in enumerate(cards):
                # Satır/Sütun hesabı
                col_i = i % cols
                row_i = i // cols
                
                cx = x_left + col_i * (card_w + card_gap)
                cy = y_top + row_i * (card_h + card_gap)
                
                # Kart kutusu (Beyaz, hafif gölge efekti yerine gri kenarlık)
                rect = QRectF(cx, cy, card_w, card_h)
                painter.setPen(QColor("#d1d5db")) # Gri kenarlık
                painter.setBrush(QColor("#ffffff"))
                painter.drawRoundedRect(rect, mm(2), mm(2))
                
                # Sol kenar şeridi (Rastgele renk veya mavi)
                strip_w = mm(1.5)
                strip_rect = QRectF(cx, cy, strip_w, card_h)
                # Basit renk rotasyonu
                colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"]
                c_idx = i % len(colors)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(colors[c_idx]))
                painter.drawRoundedRect(strip_rect, mm(2), mm(2)) 
                # Sol tarafı düzeltmek için (rounded bozulmasın diye üstüne bir daha çizmek gerekebilir, 
                # ama basit olsun diye şimdilik böyle kalsın veya rect clip kullan)
                
                # Key (Başlık) - Küçük ve Gri
                font_k = QFont(font.family(), 8, QFont.Weight.Bold)
                painter.setFont(font_k)
                painter.setPen(QColor("#6b7280"))
                kt_rect = QRectF(cx + strip_w + mm(2), cy + mm(2), card_w - strip_w - mm(3), mm(5))
                painter.drawText(kt_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, k.upper())
                
                # Value (Değer) - Büyük
                font_v = QFont(font.family(), 11, QFont.Weight.Bold)
                painter.setFont(font_v)
                painter.setPen(QColor("#111827"))
                vt_rect = QRectF(cx + strip_w + mm(2), cy + mm(6), card_w - strip_w - mm(3), mm(8))
                painter.drawText(vt_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, v)
                
                # Yeni Y
                row_y = cy + card_h

            painter.restore()
            return row_y + mm(4)

        def draw_inline_summary(items: list[str],
                                x_left: float, x_right: float, y_top: float,
                                font: QFont, line_gap_mm: float = 2.2) -> float:
            """Sayfa özeti (öğrenci, dönem vb.)."""
            # Gelişmiş kart modundaysa
            if getattr(self, "_show_info_cards", False):
                return draw_info_cards(items, x_left, x_right, y_top, font)

            painter.save()
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.black)
            fm = QFontMetricsF(font)
            baseline = y_top + fm.ascent()
            step = fm.lineSpacing() + px_per_mm() * float(line_gap_mm)
            for raw in items or []:
                raw = (raw or "").strip()
                if not raw:
                    continue
                painter.drawText(QPointF(x_left, baseline), raw)
                baseline += step
            painter.restore()
            return baseline

        def draw_hbar(percent: int, x_left: float, x_right: float, y_top: float,
                      height_mm: float = 6.0, label: str | None = None) -> float:
            """Modern ilerleme çubuğu."""
            from PyQt6.QtGui import QPen, QLinearGradient
            p = max(0.0, min(100.0, float(percent)))
            w = max(0.0, x_right - x_left)
            h = mm(height_mm)
            radius = mm(1.5) # Daha keskin, modern radius
            
            painter.save()
            
            # Arkaplan (yumuşak gri)
            bg_rect = QRectF(x_left, y_top, w, h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#e5e7eb"))
            painter.drawRoundedRect(bg_rect, radius, radius)
            
            # Dolu kısım (Gradient)
            if p > 0:
                fw = w * (p / 100.0)
                fg_rect = QRectF(x_left, y_top, fw, h)
                
                grad = QLinearGradient(fg_rect.topLeft(), fg_rect.bottomLeft())
                # Yeşil tonları
                if p < 50:
                    grad.setColorAt(0, QColor("#ef4444")) # Kırmızı
                    grad.setColorAt(1, QColor("#b91c1c"))
                elif p < 80:
                    grad.setColorAt(0, QColor("#f59e0b")) # Turuncu
                    grad.setColorAt(1, QColor("#d97706"))
                else:
                    grad.setColorAt(0, QColor("#22c55e")) # Yeşil
                    grad.setColorAt(1, QColor("#15803d"))
                    
                painter.setBrush(grad)
                painter.drawRoundedRect(fg_rect, radius, radius)
            
            # Etiket (Çubuğun içinde, sağa dayalı veya ortalı)
            if label:
                lab_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
                painter.setFont(lab_font)
                fm = QFontMetricsF(lab_font)
                
                # Metni çubuğun ortasına
                tx = x_left + (w - fm.horizontalAdvance(label)) / 2.0
                ty = y_top + (h + fm.ascent() - fm.descent()) / 2.0
                
                painter.setPen(QColor("#1f2937"))
                painter.drawText(QPointF(tx, ty), label)
                
            painter.restore()
            return y_top + h

        def draw_signature_box(x: float, y: float, w: float) -> float:
            """İmza ve Onay kutusu çizer (Veli, Öğretmen)."""
            h = mm(25)
            painter.save()
            
            # Dış çerçeve (kesikli çizgi)
            rect = QRectF(x, y, w, h)
            pen = QPen(Qt.GlobalColor.black)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, mm(2), mm(2))
            
            # İçerik: İkiye böl (Veli İmza | Öğretmen Onay)
            painter.setPen(Qt.GlobalColor.black) # Düz yazı için
            font_sig = QFont("Segoe UI", 10, QFont.Weight.Bold)
            painter.setFont(font_sig)
            
            mid_x = x + w / 2.0
            
            # Sol: Veli
            r1 = QRectF(x, y + mm(2), w/2 - mm(2), mm(6))
            painter.drawText(r1, Qt.AlignmentFlag.AlignCenter, "VELİ İMZA")
            
            # Sağ: Öğretmen
            r2 = QRectF(mid_x, y + mm(2), w/2 - mm(2), mm(6))
            painter.drawText(r2, Qt.AlignmentFlag.AlignCenter, "ÖĞRETMEN ONAY")
            
            # Ortadan dikey çizgi (opsiyonel, şık durur)
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setColor(QColor("#d1d5db")) 
            painter.setPen(pen)
            painter.drawLine(QPointF(mid_x, y + mm(2)), QPointF(mid_x, y + h - mm(2)))
            
            painter.restore()
            return y + h + mm(4)

        def draw_motivation_box(x: float, y: float, w: float) -> float:
            """Haftanın Sözü / Motivasyon kutusu."""
            h = mm(20)
            painter.save()
            
            # Arkaplan (hafif sarı not kağıdı gibi veya modern gri)
            rect = QRectF(x, y, w, h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#fffbeb")) # Amber-50 (hafif sarı)
            painter.drawRoundedRect(rect, mm(2), mm(2))
            
            # Sol şerit (sarı)
            painter.setBrush(QColor("#f59e0b"))
            painter.drawRoundedRect(QRectF(x, y, mm(1.5), h), mm(2), mm(2))
            
            # Başlık
            painter.setPen(QColor("#92400e"))
            font_title = QFont("Segoe UI", 9, QFont.Weight.Bold)
            painter.setFont(font_title)
            painter.drawText(QRectF(x + mm(4), y + mm(2), w, mm(5)), "💡 HAFTANIN MOTİVASYONU / NOTU:")
            
            # Çizgili alan (yazı yazılabilsin diye)
            pen_line = QPen(QColor("#e5e7eb"))
            painter.setPen(pen_line)
            line_y = y + mm(10)
            while line_y < y + h - mm(2):
                painter.drawLine(QPointF(x + mm(4), line_y), QPointF(x + w - mm(4), line_y))
                line_y += mm(6)
            
            painter.restore()
            return y + h + mm(4)

        # --- metin yüksekliği (kelime sarma + AlignTop) ---
        ALIGN_FLAGS = int(Qt.AlignmentFlag.AlignLeft |
                          Qt.AlignmentFlag.AlignTop |
                          Qt.TextFlag.TextWordWrap)

        # --- metin sardırma (Wrap) ayarları ---
        # PyQt6: WrapAtWordBoundaryOrAnywhere -> boşluk yoksa bile kırar (URL gibi)
        def _make_qtext_option():
            opt = QTextOption()
            opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            opt.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            return opt

        def cell_text_height(text: str, rect_w: float, font: QFont, min_row_h: float) -> float:
            """
            QTextDocument ile birebir çizim yüksekliğini ölç.
            (QFontMetrics boundingRect yerine; çok satırlı ve uzun sözcüklerde daha doğru.)
            """
            inner_w = max(1.0, rect_w - 2.0 * P_H)
            doc = QTextDocument()
            doc.setDefaultFont(font)
            doc.setDefaultTextOption(_make_qtext_option())
            doc.setTextWidth(inner_w)
            doc.setPlainText(str(text or ""))
            h = float(doc.size().height())
            return max(min_row_h, h + 2.0 * P_V)

        def draw_cell_text(text: str, cell: QRectF, font: QFont):
            """Metni hücrenin iç dikdörtgenine, kelime sardırmalı çiz."""
            painter.save()
            painter.setFont(font)
            inner = QRectF(cell.left() + P_H, cell.top() + P_V,
                           max(1.0, cell.width() - 2.0 * P_H),
                           max(1.0, cell.height() - 2.0 * P_V))
            opt = _make_qtext_option()
            # drawText overload: (QRectF, str, QTextOption)
            painter.drawText(inner, str(text or ""), opt)
            painter.restore()

        # --- checkbox çizici ---
        def draw_checkbox(cell: QRectF, checked: bool):
            from PyQt6.QtGui import QPen
            box = min(cell.height() - mm(4), mm(5.5))
            cx = cell.left() + (cell.width() - box) / 2.0
            cy = cell.top() + (cell.height() - box) / 2.0
            r = QRectF(cx, cy, box, box)
            painter.save()
            painter.setBrush(Qt.GlobalColor.white)
            painter.drawRect(r)
            if checked:
                pen = QPen(Qt.GlobalColor.black)
                pen.setWidthF(1.2)
                painter.setPen(pen)
                p1 = QPointF(r.left() + box * 0.18, r.center().y())
                p2 = QPointF(r.left() + box * 0.42, r.bottom() - box * 0.18)
                p3 = QPointF(r.right() - box * 0.18, r.top() + box * 0.22)
                painter.drawLine(p1, p2)
                painter.drawLine(p2, p3)
            painter.restore()

        try:
            # --------- Sayfa iç alanı ---------
            pl = printer.pageLayout()
            rmm = pl.paintRect(QPageLayout.Unit.Millimeter)
            content = QRectF(
                (rmm.left() + self._margins_mm.left()) * px_per_mm(),
                (rmm.top() + self._margins_mm.top()) * px_per_mm(),
                (rmm.width() - self._margins_mm.left() - self._margins_mm.right()) * px_per_mm(),
                (rmm.height() - self._margins_mm.top() - self._margins_mm.bottom()) * px_per_mm(),
            )

            # --------- Fontlar / metrikler ----------
            font_title = QFont("Arial", 12, QFont.Weight.Bold)
            font_header = QFont("Arial", 10, QFont.Weight.Bold)
            font_table = QFont("Arial", 10)
            fm_header, fm_table = QFontMetricsF(font_header), QFontMetricsF(font_table)

            MIN_ROW_H = max(mm(6.0), fm_table.height() * 2.0)
            MIN_HEADER_H = max(mm(7.0), fm_header.height() * 2.2)

            y = content.top()

            # --------- Logo (varsa) ----------
            if getattr(self, "_logo_path", ""):
                try:
                    img = QImage(self._logo_path)
                    if not img.isNull():
                        logo_h_mm = getattr(self, "spn_logo_h").value() if hasattr(self, "spn_logo_h") else 16
                        logo_gap = getattr(self, "spn_logo_gap").value() if hasattr(self, "spn_logo_gap") else 4
                        logo_align = getattr(self, "cmb_logo_align").currentIndex() if hasattr(self,
                                                                                               "cmb_logo_align") else 0
                        target_h = mm(logo_h_mm)
                        ratio = target_h / float(img.height())
                        logo_w = img.width() * ratio
                        if logo_align == 1:
                            x0 = content.left() + (content.width() - logo_w) / 2.0
                        elif logo_align == 2:
                            x0 = content.right() - logo_w
                        else:
                            x0 = content.left()
                        panel = QRectF(x0, y, logo_w, target_h)
                        painter.drawImage(panel, img)
                        y = panel.bottom() + mm(logo_gap + 2.0)
                except Exception:
                    pass

            # --------- Sayfa Özeti (üst) ----------
            if page_summary_lines and page_summary_position != "bottom":
                # satır aralığını biraz arttır (daha rahat)
                y = draw_inline_summary(page_summary_lines, content.left(), content.right(), y, QFont("Arial", 11), 3.2)
                y += mm(3)

                # barlar: daha kısa ve dar
                bar_left = content.left()
                bar_right = content.left() + content.width() * 0.52  # daha dar panel
                if getattr(self, "_period_completion", None) and getattr(self, "_show_period_bar", False):
                    pp, done, tot = self._period_completion
                    y = draw_hbar(pp, bar_left, bar_right, y, 4.5, f"%{pp}  ({done}/{tot})")
                    y += mm(1.6)
                if getattr(self, "_general_completion", None) and getattr(self, "_show_completion_bar", True):
                    gp, gd, gt = self._general_completion
                    y = draw_hbar(gp, bar_left, bar_right, y, 4.5, f"%{gp}  ({gd}/{gt})")
                    y += mm(3)

            # --------- Serbest başlık metni ----------
            if getattr(self, "_header_text", ""):
                hdr_align = getattr(self, "cmb_hdr_align").currentIndex() if hasattr(self, "cmb_hdr_align") else 1
                hdr_size = int(getattr(self, "spn_hdr_size").value()) if hasattr(self, "spn_hdr_size") else 14
                hdr_bold = bool(getattr(self, "chk_hdr_bold").isChecked()) if hasattr(self, "chk_hdr_bold") else True
                hdr_gap = float(getattr(self, "spn_hdr_gap").value()) if hasattr(self, "spn_hdr_gap") else 4.0
                font_hdr = QFont("Segoe UI", hdr_size, QFont.Weight.Bold if hdr_bold else QFont.Weight.Normal)
                
                # Yeni multiline çizim -> draw_text_box
                y = draw_text_box(self._header_text, content.left(), y, content.width(), hdr_align, font_hdr)
                y += mm(hdr_gap)

            # ===================== TABLO =====================
            headers = self._selected_columns
            if not headers:
                return

            # kolon rollerini sez
            chk_names = set(getattr(self.adapter, "_checkable_names", set()))
            is_portrait = (printer.pageLayout().orientation() == QPageLayout.Orientation.Portrait)

            def role(h: str) -> str:
                hl = h.lower()
                if h in chk_names or "yap" in hl:              return "chk"
                if "açıklama" in hl or "aciklama" in hl:       return "desc"
                if "süre" in hl or "sure" in hl:               return "dur"
                if "ders" in hl:                               return "course"
                if "kitap" in hl:                              return "book"
                if "konu" in hl:                               return "topic"
                return "other"

            # --- içerik analizleri (desc boş mu? metin uzunlukları?) ---
            rows = self.adapter._rows

            def col_nonempty_ratio(h: str) -> float:
                if not h or not rows:
                    return 0.0
                nonempty = sum(1 for r in rows if str(r.get(h, "")).strip())
                return nonempty / max(1, len(rows))

            def col_maxlen(h: str) -> int:
                return max((len(str(r.get(h, "")).strip()) for r in rows), default=0)

            desc_header = next((hh for hh in headers if role(hh) == "desc"), None)
            has_desc_any = (any(bool(str(r.get(desc_header, "")).strip()) for r in rows)
                            if desc_header else False)
            desc_fill_ratio = col_nonempty_ratio(desc_header) if desc_header else 0.0

            # --- taban yüzdeleri (portre / manzara) ---
            base_pct_portrait = {"chk": 0.06, "dur": 0.07, "course": 0.16, "book": 0.16, "topic": 0.32, "desc": 0.23}
            base_pct_landscape = {"chk": 0.05, "dur": 0.06, "course": 0.15, "book": 0.15, "topic": 0.30, "desc": 0.29}
            base_pct = dict(base_pct_portrait if is_portrait else base_pct_landscape)

            # desc payını doluluğa göre ayarla
            if "desc" in base_pct:
                if not has_desc_any or desc_fill_ratio < 0.05:
                    base_pct["desc"] = 0.06  # min görünürlük
                else:
                    base_pct["desc"] = max(0.08, min(base_pct["desc"], 0.18 if is_portrait else 0.20))

            # course/book/topic alanlarını, metin uzunluklarına göre ağırlıkla
            roles_interest = ["course", "book", "topic"]
            lens = {r: 0 for r in roles_interest}
            for h in headers:
                r = role(h)
                if r in roles_interest:
                    lens[r] = max(lens[r], col_maxlen(h))

            # normalize ağırlıklar (tamamı 0 ise eşit paylaştır)
            total_len = sum(lens.values())
            if total_len == 0:
                weights = {r: 1.0 / len(roles_interest) for r in roles_interest}
            else:
                weights = {r: (lens[r] / total_len) for r in roles_interest}

            # bu rollere ayrılacak toplam pay
            alloc_total = sum(base_pct.get(r, 0) for r in roles_interest)
            for r in roles_interest:
                base_pct[r] = alloc_total * weights[r] if alloc_total > 0 else base_pct.get(r, 0)

            # minimum mm sınırları
            min_wmm = {
                "chk": 8, "dur": 14,
                "course": 24 if is_portrait else 22,
                "book": 24 if is_portrait else 22,
                "topic": 34 if is_portrait else 28,
                "desc": 18,
                "other": 20,
            }

            def pct_for(h: str) -> float:
                return base_pct.get(role(h), 0.0)

            # header -> piksel genişliği
            col_ws = []
            for h in headers:
                r = role(h)
                min_mm = min_wmm.get(r, min_wmm["other"])
                w_px = max(mm(min_mm), content.width() * pct_for(h))
                col_ws.append(w_px)

            # toplamı sayfa genişliğine eşitle (küçük sapmaları düzelt)
            total_w = sum(col_ws)
            if total_w > 0:
                s = content.width() / total_w
                col_ws = [w * s for w in col_ws]

            # kolon sol x’leri
            col_x = [content.left()]
            for w in col_ws[:-1]:
                col_x.append(col_x[-1] + w)

            # --- başlık yüksekliği ve çizimi (wrap + üst hizalı) ---
            painter.setFont(font_header)
            h_h = max(MIN_HEADER_H,
                      max(cell_text_height(h, col_ws[i], font_header, MIN_HEADER_H) for i, h in enumerate(headers)))

            def draw_header(at_y: float):
                # Başlık arka planı (Mavi modern)
                painter.fillRect(QRectF(content.left(), at_y, content.width(), h_h), QColor("#2563eb"))
                
                painter.save()
                for i, h in enumerate(headers):
                    cell = QRectF(col_x[i], at_y, col_ws[i], h_h)
                    # Çerçeve
                    # painter.setPen(QColor("#1e40af"))
                    # painter.drawRect(cell)
                    
                    # Metin (Beyaz)
                    painter.setPen(Qt.GlobalColor.white)
                    draw_cell_text(h, cell, font_header)
                painter.restore()

            draw_header(y)
            y += h_h
            painter.setFont(font_table)

            # --- sayfa numarası ---
            page_no = 1

            def draw_page_no():
                painter.save()
                lab = QFont("Arial", 9)
                painter.setFont(lab)
                txt = f"Sayfa {page_no}"
                fm = QFontMetricsF(lab)
                tx = content.right() - fm.horizontalAdvance(txt)
                ty = content.bottom() + mm(6)
                painter.drawText(QPointF(tx, ty), txt)
                painter.restore()

            # --------- Alt bilgi için yer hesabı ----------
            footer_h = 0.0
            if getattr(self, "_footer_text", ""):
                ftr_size = int(getattr(self, "spn_ftr_size").value()) if hasattr(self, "spn_ftr_size") else 11
                ftr_bold = bool(getattr(self, "chk_ftr_bold").isChecked()) if hasattr(self, "chk_ftr_bold") else False
                ftr_offset_mm = float(getattr(self, "spn_ftr_offset").value()) if hasattr(self, "spn_ftr_offset") else 0.0
                font_ftr = QFont("Arial", ftr_size, QFont.Weight.Bold if ftr_bold else QFont.Weight.Normal)
                
                # Ölçüm (dry_run=True) - width content.width() olmalı!
                fake_y = draw_text_box(self._footer_text, 0, 0, content.width(), 0, font_ftr, dry_run=True)
                footer_text_h = fake_y # 0'da başladığı için dönen değer yüksekliktir
                
                # Ekstra bileşenler için pay
                signature_h = mm(25) if getattr(self, "_show_signature", False) else 0.0
                motivation_h = mm(20) if getattr(self, "_show_motivation", False) else 0.0
                
                footer_h = footer_text_h + mm(ftr_offset_mm) + signature_h + motivation_h + mm(4.0)


            bottom_limit = content.bottom() - footer_h

            # --- satırlar ---
            rows = self.adapter._rows
            check_states = list(getattr(self.adapter, "_check_states", []))  # opsiyonel

            for r_idx, row in enumerate(rows):
                # satır yüksekliği (kolon bazında)
                row_h_list = []
                for i, h in enumerate(headers):
                    if role(h) == "chk":
                        row_h_list.append(max(MIN_ROW_H, mm(7)))
                    else:
                        row_h_list.append(cell_text_height(str(row.get(h, "")), col_ws[i], font_table, MIN_ROW_H))
                row_h = max(row_h_list) if row_h_list else MIN_ROW_H

                # sayfa taşması -> numara + yeni sayfa + başlık tekrar
                if y + row_h > bottom_limit:
                    # Alt bilgi çiz (bu sayfaya)
                    # Alt bilgi + Diğerleri çiz (bu sayfaya)
                    cur_btm_y = content.bottom() - footer_text_h - mm(4)

                    # 1. Motivasyon (en altta değil, imzanın üstünde olsun veya tam tersi) -> En üste yakın
                    # Sıralama (Aşağıdan yukarı): Footer Text -> Signature -> Motivation
                    
                    # Footer Text
                    if getattr(self, "_footer_text", ""):
                        draw_text_box(self._footer_text, content.left(), 
                                           cur_btm_y, 
                                           content.width(), ftr_align_ix, font_ftr)
                    
                    # Signature
                    if getattr(self, "_show_signature", False):
                        cur_btm_y -= (mm(25) + mm(4)) # h + gap
                        draw_signature_box(content.left(), cur_btm_y, content.width())

                    # Motivation
                    if getattr(self, "_show_motivation", False):
                        cur_btm_y -= (mm(20) + mm(4))
                        draw_motivation_box(content.left(), cur_btm_y, content.width())
                    
                    draw_page_no()
                    page_no += 1
                    printer.newPage()
                    y = content.top()
                    draw_header(y)
                    y += h_h

                # zebra
                if r_idx % 2 == 1:
                    painter.fillRect(QRectF(content.left(), y, content.width(), row_h), QColor(0, 0, 0, 10))

                # hücreler
                for i, h in enumerate(headers):
                    cell = QRectF(col_x[i], y, col_ws[i], row_h)
                    painter.drawRect(cell)
                    
                    # Renk şeridi (Ders'e göre)
                    if getattr(self, "_show_color_strip", False) and role(h) == "course":
                        course_name = str(row.get(h, "")).lower()
                        # Basit renk haritası
                        c_color = "#9ca3af" # Default gri
                        if "mat" in course_name: c_color = "#ef4444" # Kırmızı
                        elif "fen" in course_name or "fiz" in course_name: c_color = "#10b981" # Yeşil
                        elif "türk" in course_name or "edeb" in course_name: c_color = "#f59e0b" # Turuncu
                        elif "sos" in course_name or "tar" in course_name: c_color = "#8b5cf6" # Mor
                        elif "kim" in course_name: c_color = "#06b6d4" # Cyan
                        elif "biyo" in course_name: c_color = "#14b8a6" # Teal
                        elif "din" in course_name: c_color = "#6366f1" # Indigo
                        elif "ing" in course_name: c_color = "#ec4899" # Pink
                        
                        strip_w = mm(1.5)
                        strip_r = QRectF(cell.left(), cell.top(), strip_w, cell.height())
                        painter.fillRect(strip_r, QColor(c_color))

                    if role(h) == "chk":
                        st = check_states[r_idx] if (0 <= r_idx < len(check_states)) else {}
                        checked = bool(st.get(h, False))
                        if not checked:
                            sval = str(row.get(h, "")).strip().lower()
                            checked = sval in {"1", "true", "evet", "✓", "✔", "x"}
                        draw_checkbox(cell, checked)
                    else:
                        draw_cell_text(str(row.get(h, "")), cell, font_table)

                y += row_h

            # son sayfa numarası
            draw_page_no()

            # --------- Sayfa özeti (altta istenirse) ----------
            if page_summary_lines and page_summary_position == "bottom":
                y += mm(4)
                # Sayfa taşarsa yeni sayfaya
                est_h = len(page_summary_lines) * mm(6)
                if y + est_h > bottom_limit:
                     # Alt bilgi bas
                     # Alt bilgi + Diğerleri çiz
                     cur_btm_y = content.bottom() - footer_text_h - mm(4)
                     
                     if getattr(self, "_footer_text", ""):
                        draw_text_box(self._footer_text, content.left(), 
                                           cur_btm_y, 
                                           content.width(), ftr_align_ix, font_ftr)
                     
                     if getattr(self, "_show_signature", False):
                        cur_btm_y -= (mm(25) + mm(4))
                        draw_signature_box(content.left(), cur_btm_y, content.width())

                     if getattr(self, "_show_motivation", False):
                        cur_btm_y -= (mm(20) + mm(4))
                        draw_motivation_box(content.left(), cur_btm_y, content.width())
                     printer.newPage()
                     y = content.top()
                
                _ = draw_inline_summary(page_summary_lines, content.left(), content.right(), y, QFont("Arial", 11), 2.0)

            # --------- Alt bilgi metni (SON SAYFA) ----------
            if getattr(self, "_footer_text", ""):
                # zaten yukarıda hesapladık değişkenleri (ftr_align_ix vs scope dışı olabilir, tekrar al)
                ftr_align_ix = getattr(self, "cmb_ftr_align").currentIndex() if hasattr(self, "cmb_ftr_align") else 0
                # ... diğerlerini yukarıda almıştık ama scope riski var, tekrar tanımlamak güvenli:
                # (Performans kritik değil)
                ftr_size = int(getattr(self, "spn_ftr_size").value()) if hasattr(self, "spn_ftr_size") else 11
                ftr_bold = bool(getattr(self, "chk_ftr_bold").isChecked()) if hasattr(self, "chk_ftr_bold") else False
                font_ftr = QFont("Segoe UI", ftr_size, QFont.Weight.Bold if ftr_bold else QFont.Weight.Normal)
                
                # Son sayfa yazdırma
                cur_btm_y = content.bottom() - footer_text_h - mm(4)
                
                if getattr(self, "_footer_text", ""):
                    draw_text_box(self._footer_text, content.left(), 
                                       cur_btm_y, 
                                       content.width(), ftr_align_ix, font_ftr)

                if getattr(self, "_show_signature", False):
                    cur_btm_y -= (mm(25) + mm(4))
                    draw_signature_box(content.left(), cur_btm_y, content.width())

                if getattr(self, "_show_motivation", False):
                    cur_btm_y -= (mm(20) + mm(4))
                    draw_motivation_box(content.left(), cur_btm_y, content.width())

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Çizim Hatası", f"Belge oluşturulurken hata oluştu:\n{e}")
        finally:
            painter.end()

    # --- ESKİ API'YI KORUYAN SARMALAYICI ---
    def _render_document(self, printer: QPrinter):
        """
        Eski çağrılar bozulmasın diye bırakıldı.
        Varsa self._page_summary_lines / self._page_summary_position kullanır.
        Yoksa sadece tablo + başlık/altbilgi/Logo basar.
        """
        lines = getattr(self, "_page_summary_lines", None)
        pos = getattr(self, "_page_summary_position", "top")
        self._render_document_impl(printer, lines, pos)

    # --------- Özetli kolay yardımcılar (opsiyonel) ---------
    def preview_with_summary(self, summary_lines: List[str], position: str = "top"):
        self._collect_state_from_ui()
        pr = self._make_printer()
        preview = QPrintPreviewDialog(pr, self)
        preview.setWindowTitle("Yazdırma Önizleme")
        # ESKİ: preview.paintRequested.connect(lambda p: self._render_document(p, summary_lines, position))
        preview.paintRequested.connect(lambda p: self._render_document_impl(p, summary_lines, position))
        preview.exec()

    def print_with_summary(self, summary_lines: List[str], position: str = "top"):
        self._collect_state_from_ui()
        pr = self._make_printer()
        dlg = QPrintDialog(pr, self)
        dlg.setWindowTitle("Yazdır")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # ESKİ: self._render_document(pr, summary_lines, position)
            self._render_document_impl(pr, summary_lines, position)

    # ---------- Öğrenci ek bilgileri üretimi ----------
    def _build_student_extras(self, row: RowDict) -> List[str]:
        # Kullanıcı fonksiyonu öncelikli
        if self.extra_info_callback:
            try:
                lines = self.extra_info_callback(row) or []
                return [str(x) for x in lines if str(x).strip()]
            except Exception:
                pass

        # Heuristik: ilgili kolon adlarını yakala
        keys = {k.lower(): k for k in row.keys()}
        out = []

        def take(*alts):
            for a in alts:
                key = next((keys[k] for k in keys if a in k), None)
                if key:
                    val = str(row.get(key, "")).strip()
                    if val:
                        return val
            return ""

        ad = take("ad")
        soyad = take("soyad")
        sinif = take("sınıf", "sinif", "sube", "şube")
        okul = take("okul")
        veli = take("veli")
        tel = take("telefon", "tel", "gsm", "cep")
        notu = take("not", "açıklama", "aciklama")

        if any([ad, soyad, sinif]):
            out.append("Öğrenci: " + " ".join(x for x in [ad, soyad, f"({sinif})" if sinif else ""] if x))
        if okul:
            out.append(f"Okul: {okul}")
        if veli or tel:
            out.append("İletişim: " + ", ".join(x for x in [veli, tel] if x))
        if notu:
            out.append(f"Not: {notu}")

        return out

    def _make_page_summary_lines(self) -> list[str]:
        """
        'Öğrenci ek bilgilerini de yazdır' seçeneği için TEK seferlik sayfa özeti üretir.
        Tablo başlıklarına göre akıllıca alanları bulur (Öğrenci, Başlangıç, Bitiş, %Tamamlama, Kurum).
        """
        headers = [h.lower() for h in self.adapter._headers]
        rows = self.adapter._rows or [{}]

        def _find_col(*needles):
            for i, h in enumerate(headers):
                for n in needles:
                    if n in h:
                        return i
            return None

        def _first_nonempty(col_idx):
            if col_idx is None:
                return ""
            for r in rows:
                vals = list(r.values())
                if 0 <= col_idx < len(vals):
                    v = str(vals[col_idx]).strip()
                    if v:
                        return v
            return ""

        ix_student = _find_col("öğrenci", "ogrenci", "ad", "isim", "soyad")
        ix_start = _find_col("başlangıç", "baslangic", "start", "veriliş", "verilis")
        ix_end = _find_col("bitiş", "bitis", "deadline", "due", "teslim")
        ix_org = _find_col("kurum", "kaynak")
        ix_percent = _find_col("yüzde", "yuzde", "tamam", "%", "oran")

        student = _first_nonempty(ix_student)
        date_s = _first_nonempty(ix_start)
        date_e = _first_nonempty(ix_end)
        org = _first_nonempty(ix_org)
        perc = _first_nonempty(ix_percent)

        lines = []
        if student: lines.append(f"Öğrenci: {student}")
        if date_s:  lines.append(f"Başlangıç: {date_s}")
        if date_e:  lines.append(f"Bitiş: {date_e}")
        if perc:    lines.append(f"Tamamlama: %{perc.strip('%')}")
        if org:     lines.append(f"Kurum: {org}")
        return lines or ["Öğrenci Özeti"]

    # --- TEK SEFERLİK ÖZETİ AYARLAMAK İÇİN YARDIMCI ---
    def set_page_summary(self, lines: List[str] | None, position: str = "top"):
        """
        Tabloya TEK SEFERLİK özet bloğu (öğrenci adı, tarih, %tamamlama vb.) eklemek için.
        lines: ["Öğrenci: ...", "Başlangıç: ...", "Bitiş: ...", "%Tamamlama: ...", ...]
        position: "top" (başlık ile tablo arasında) veya "bottom" (sayfanın altına)
        """
        self._page_summary_lines = None if not lines else [str(x) for x in lines if str(x).strip()]
        self._page_summary_position = "bottom" if str(position).lower() == "bottom" else "top"

    def apply_student_summary(
            self,
            con,  # sqlite3.Connection
            ogrenci_id: int,
            kume_id: Optional[int] = None,  # varsa tek küme
            tarih_araligi: Optional[tuple[str, str]] = None,  # ("YYYY-MM-DD","YYYY-MM-DD")
            position: str = "top"
    ) -> None:
        import sqlite3

        def _log(*a):
            try:
                print("[print_helper.apply_student_summary]", *a)
            except Exception:
                pass

        # --- küçük yardımcılar ---
        def _column_exists(table: str, column: str) -> bool:
            try:
                rows = con.execute(f"PRAGMA table_info({table})").fetchall()
                cols = {(r["name"] if isinstance(r, dict) else r[1]).lower() for r in rows}
                return column.lower() in cols
            except Exception:
                return False

        def _build_done_expr(table: str, alias: str | None = None) -> str:
            """
            Tamamlanmış kabul edeceğimiz koşulu, tablo şemasına bakarak dinamik kur.
            alias: 'd' gibi (JOIN'lerde kullanacağız).
            """
            pref = (alias + ".") if alias else ""
            parts = []
            # her zaman çalışacak metin eşleşmeleri:
            parts += [
                f"instr(lower(coalesce({pref}durum,'')),'yap')>0",
                f"instr(lower(coalesce({pref}durum,'')),'yapıl')>0",
                f"instr(lower(coalesce({pref}durum,'')),'yapildi')>0",
                f"instr(lower(coalesce({pref}durum,'')),'tamam')>0",
                f"instr(lower(coalesce({pref}durum,'')),'bitti')>0",
            ]
            # durum_kodu varsa:
            if _column_exists(table, "durum_kodu"):
                parts.append(f"lower(coalesce({pref}durum_kodu,'')) IN ('done','tamam','bitti','ok')")
            # boolean bayraklar varsa (varsa ekle, yoksa hiç ekleme):
            for flag in ("tamam", "done", "bitirildi"):
                if _column_exists(table, flag):
                    parts.append(f"coalesce({pref}{flag},0)=1")
            return " OR ".join(parts)

        # ---------- ÜST BİLGİLER ----------
        row = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
        ogr_ad = (row["ad"] + " " + row["soyad"]).strip() if row else f"#{ogrenci_id}"

        baslangic = bitis = ""
        if kume_id is not None:
            r = con.execute("SELECT verilis_tarihi, bitis_tarihi FROM odev_kume WHERE id=?", (kume_id,)).fetchone()
            if r:
                baslangic = (r["verilis_tarihi"] or "").strip()
                bitis = (r["bitis_tarihi"] or "").strip()
        elif tarih_araligi:
            baslangic, bitis = tarih_araligi

        # ---------- SAYIM YARDIMCILARI ----------
        def _count_period_on_odev(kid: int):
            """Seçilen küme için (odev) toplam/tamamlanan ve ders/kitap sayıları."""
            try:
                total = con.execute("SELECT COUNT(*) FROM odev WHERE kume_id=?", (kid,)).fetchone()[0] or 0
                done_expr = _build_done_expr("odev")
                done = con.execute(f"SELECT COUNT(*) FROM odev WHERE kume_id=? AND ({done_expr})", (kid,)).fetchone()[
                           0] or 0
                ders_say = con.execute("SELECT COUNT(DISTINCT ders) FROM odev WHERE kume_id=?", (kid,)).fetchone()[
                               0] or 0
                kitap_say = con.execute("SELECT COUNT(DISTINCT kitap_ad) FROM odev WHERE kume_id=?", (kid,)).fetchone()[
                                0] or 0
                return int(total), int(done), int(ders_say), int(kitap_say)
            except sqlite3.Error:
                return 0, 0, 0, 0

        def _count_all_odev_join(ogr_id: int):
            """Öğrencinin tüm odev kayıtlarını odev_kume ile join ederek say."""
            try:
                total = con.execute("""
                    SELECT COUNT(*) FROM odev d
                    JOIN odev_kume k ON k.id = d.kume_id
                    WHERE k.ogrenci_id=?""", (ogr_id,)).fetchone()[0] or 0
                done_expr = _build_done_expr("odev", alias="d")
                done = con.execute(f"""
                    SELECT COUNT(*) FROM odev d
                    JOIN odev_kume k ON k.id = d.kume_id
                    WHERE k.ogrenci_id=? AND ({done_expr})
                """, (ogr_id,)).fetchone()[0] or 0
                return int(total), int(done)
            except sqlite3.Error:
                return 0, 0

        def _count_all_on_satir(ogr_id: int):
            """odev_satir (ogrenci_id var) için tüm zaman sayımı."""
            try:
                total = con.execute("SELECT COUNT(*) FROM odev_satir WHERE ogrenci_id=?", (ogr_id,)).fetchone()[0] or 0
                done_expr = _build_done_expr("odev_satir")
                done = con.execute(f"""
                    SELECT COUNT(*) FROM odev_satir
                    WHERE ogrenci_id=? AND ({done_expr})
                """, (ogr_id,)).fetchone()[0] or 0
                return int(total), int(done)
            except sqlite3.Error:
                return 0, 0

        # ---------- DÖNEM/KÜME (üstteki “Tamamlama”) ----------
        ders_say = kitap_say = 0
        if kume_id is not None:
            total, done, ders_say, kitap_say = _count_period_on_odev(kume_id)
            # total 0 geldiyse güvenli FALLBACK (JOIN + ogrenci_id) – boolean sütun kontrolü burada da dinamik
            if total == 0:
                _log(f"üst (kume_id={kume_id}) total=0, fallback çalışıyor…")
                try:
                    done_expr = _build_done_expr("odev", alias="d")
                    total = con.execute("""
                        SELECT COUNT(*) FROM odev d
                        JOIN odev_kume k ON k.id=d.kume_id
                        WHERE d.kume_id=? AND k.ogrenci_id=?""", (kume_id, ogrenci_id)).fetchone()[0] or 0
                    done = con.execute(f"""
                        SELECT COUNT(*) FROM odev d
                        JOIN odev_kume k ON k.id=d.kume_id
                        WHERE d.kume_id=? AND k.ogrenci_id=? AND ({done_expr})
                    """, (kume_id, ogrenci_id)).fetchone()[0] or 0
                    ders_say = con.execute("""
                        SELECT COUNT(DISTINCT d.ders) FROM odev d
                        JOIN odev_kume k ON k.id=d.kume_id
                        WHERE d.kume_id=? AND k.ogrenci_id=?""", (kume_id, ogrenci_id)).fetchone()[0] or 0
                    kitap_say = con.execute("""
                        SELECT COUNT(DISTINCT d.kitap_ad) FROM odev d
                        JOIN odev_kume k ON k.id=d.kume_id
                        WHERE d.kume_id=? AND k.ogrenci_id=?""", (kume_id, ogrenci_id)).fetchone()[0] or 0
                except Exception as e:
                    _log("fallback hata:", e)
        elif tarih_araligi:
            done_expr = _build_done_expr("odev_satir")
            total = con.execute(
                "SELECT COUNT(*) FROM odev_satir WHERE ogrenci_id=? AND tarih BETWEEN ? AND ?",
                (ogrenci_id, baslangic, bitis)
            ).fetchone()[0] or 0
            done = con.execute(f"""
                SELECT COUNT(*) FROM odev_satir
                WHERE ogrenci_id=? AND tarih BETWEEN ? AND ? AND ({done_expr})
            """, (ogrenci_id, baslangic, bitis)).fetchone()[0] or 0
            ders_say = con.execute(
                "SELECT COUNT(DISTINCT ders) FROM odev_satir WHERE ogrenci_id=? AND tarih BETWEEN ? AND ?",
                (ogrenci_id, baslangic, bitis)
            ).fetchone()[0] or 0
            kitap_say = con.execute(
                "SELECT COUNT(DISTINCT kitap) FROM odev_satir WHERE ogrenci_id=? AND tarih BETWEEN ? AND ?",
                (ogrenci_id, baslangic, bitis)
            ).fetchone()[0] or 0
        else:
            total, done = _count_all_odev_join(ogrenci_id)
            ders_say = con.execute("""
                SELECT COUNT(DISTINCT d.ders)
                  FROM odev d JOIN odev_kume k ON k.id=d.kume_id
                 WHERE k.ogrenci_id=?""", (ogrenci_id,)).fetchone()[0] or 0
            kitap_say = con.execute("""
                SELECT COUNT(DISTINCT d.kitap_ad)
                  FROM odev d JOIN odev_kume k ON k.id=d.kume_id
                 WHERE k.ogrenci_id=?""", (ogrenci_id,)).fetchone()[0] or 0

        yuzde = round(100 * done / total) if total else 0
        _log(
            f"kume_id={kume_id} ogrenci_id={ogrenci_id}  ->  period: done/total={done}/{total}  ders={ders_say} kitap={kitap_say}")

        # --- DÖNEM İÇİN İLERLEME ÇUBUĞU (bar #1) ---
        self._period_completion = (yuzde, int(done or 0), int(total or 0))
        self._show_period_bar = True

        # --- "TAMAMLANMAMIŞ ÖDEVLER" MINI TABLOSU (yalnızca dönem için) ---
        incompletes: list[dict] = []

        def _predicate_not_done(alias: str) -> str:
            a = (alias + ".") if alias else ""
            return f"""
                NOT (
                       instr(lower(coalesce({a}durum,'')),'yap')   > 0
                    OR instr(lower(coalesce({a}durum,'')),'tamam') > 0
                    OR instr(lower(coalesce({a}durum,'')),'bitti')  > 0
                    OR coalesce({a}tamam,0)=1
                    OR coalesce({a}done,0)=1
                    OR lower(coalesce({a}durum_kodu,'')) IN ('done','tamam','bitti')
                )
            """

        try:
            if kume_id is not None:
                rows_inc = con.execute(f"""
                    SELECT ders, kitap_ad AS kitap, konu_ad AS konu
                      FROM odev
                     WHERE kume_id=?
                       AND {_predicate_not_done('')}
                     ORDER BY id
                """, (kume_id,)).fetchall()
                incompletes = [{"ders": r["ders"] or "",
                                "kitap": r["kitap"] or "",
                                "konu": r["konu"] or ""} for r in rows_inc]
            elif tarih_araligi:
                rows_inc = con.execute(f"""
                    SELECT ders, kitap, konu
                      FROM odev_satir
                     WHERE ogrenci_id=? AND tarih BETWEEN ? AND ?
                       AND {_predicate_not_done('')}
                     ORDER BY id
                """, (ogrenci_id, baslangic, bitis)).fetchall()
                incompletes = [{"ders": r["ders"] or "",
                                "kitap": r["kitap"] or "",
                                "konu": r["konu"] or ""} for r in rows_inc]
            else:
                incompletes = []
        except Exception:
            incompletes = []

        self._incomplete_rows = incompletes[:8]
        self._incomplete_more_count = max(0, len(incompletes) - len(self._incomplete_rows))
        # ---------- GENEL TAMAMLAMA ----------
        g_total_o, g_done_o = _count_all_odev_join(ogrenci_id)
        g_total_s, g_done_s = _count_all_on_satir(ogrenci_id)
        g_total = g_total_o + g_total_s
        g_done = g_done_o + g_done_s
        g_percent = round(100 * g_done / g_total) if g_total else 0
        _log(f"genel: odev={g_done_o}/{g_total_o} + satir={g_done_s}/{g_total_s} => {g_done}/{g_total} (%{g_percent})")

        # grafikte GENEL gözüksün
        self._general_completion = (g_percent, g_done, g_total)
        self._show_completion_bar = True

        # ---------- Kurum (opsiyonel) ----------
        kurum = ""
        try:
            row = con.execute("SELECT deger FROM ayar WHERE anahtar='kurum_adi'").fetchone()
            kurum = (row["deger"] if row else "") or ""
        except Exception:
            pass

        # ---------- ÖZET SATIRLARI ----------
        lines = [f"Öğrenci: {ogr_ad}"]
        if baslangic or bitis:
            lines.append(f"Dönem: {baslangic or '-'} — {bitis or '-'}")
        lines.append(f"Tamamlama: %{yuzde} ( {done}/{total} )")
        lines.append(f"Genel tamamlama: %{g_percent} ( {g_done}/{g_total} )")
        if ders_say or kitap_say:
            lines.append(f"Ders sayısı: {ders_say}   •   Kitap sayısı: {kitap_say}")
        if kurum:
            lines.append(f"Kurum: {kurum}")

        self.set_page_summary(lines, position)
        self._print_student_extras = False


# ---------- Dış API: Projelerinde kolay kullanım ----------
class ListPrintManager:
    """
    Tek satırla kullan:
        ListPrintManager.run_for_table(self, tableWidget, profile_key="VerilenOdevler")
        ListPrintManager.run_for_view(self, tableView, profile_key="VerilenOdevler")
        ListPrintManager.run_for_dataframe(self, df, profile_key="VerilenOdevler")
        ListPrintManager.run_for_rows(self, rows_as_dicts, headers, profile_key="...")

    extra_info_callback(row_dict) -> List[str] vererek satır altına ek bilgiler bastırabilirsin.
    """

    def __init__(self, parent: Optional[QWidget] = None,
                 profile: Optional[PrintProfile] = None,
                 extra_info_callback: Optional[ExtraInfoFunc] = None):
        self.parent = parent
        self.profile = profile or PrintProfile()
        self.extra_info_callback = extra_info_callback

    # ---- Çeşitli kaynaklar için kolay başlatıcılar ----
    def run_for_table(self, table: QTableWidget, profile_key: str = "GenelListeYazdir"):
        adapter = _ModelAdapter(table)
        self._run_common(adapter, profile_key)

    def run_for_view(self, view: QTableView, profile_key: str = "GenelListeYazdir"):
        adapter = _ModelAdapter(view)
        self._run_common(adapter, profile_key)

    def run_for_dataframe(self, df: "pd.DataFrame", profile_key: str = "GenelListeYazdir"):
        if pd is None:
            raise RuntimeError("pandas bulunamadı. pip ile 'pandas' kurun veya dict listesi kullanın.")
        adapter = _ModelAdapter(df)
        self._run_common(adapter, profile_key)

    def run_for_rows(self, rows: Sequence[dict], headers: Optional[Sequence[str]] = None, profile_key: str = "GenelListeYazdir"):
        # headers verilmişse rows'u o sıraya göre normalize edelim
        norm = []
        if headers:
            for r in rows:
                norm.append({str(h): str(r.get(h, "")) for h in headers})
            adapter = _ModelAdapter(norm)
            adapter._headers = [str(h) for h in headers]
        else:
            adapter = _ModelAdapter(rows)
        self._run_common(adapter, profile_key)

    # ---- Ortak çalışma ----
    def _run_common(self, adapter: _ModelAdapter, profile_key: str):
        if not adapter._headers:
            QMessageBox.warning(self.parent, "Uyarı", "Yazdırılacak sütun bulunamadı.")
            return
        dlg = ListPrintDialog(
            parent=self.parent,
            model_adapter=adapter,
            profile=PrintProfile(self.profile.org, self.profile.app, profile_key),
            extra_info_callback=self.extra_info_callback,
            title="Liste Yazdır"
        )
        dlg.resize(720, 540)
        dlg.exec()


# ---------- Basit kullanım örneği ----------
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    from PyQt6.QtWidgets import QTableWidgetItem, QTableWidget

    tw = QTableWidget()
    tw.setRowCount(3)
    tw.setColumnCount(5)
    tw.setHorizontalHeaderLabels(["Öğrenci", "Sınıf", "Veli", "Telefon", "Not"])
    data = [
        ["Rana Betül", "5/A", "Gülden Hanım", "05xx xxx xx xx", "Ödevleri düzenli."],
        ["Berna Fırat", "7/B", "Beyza Hanım", "05xx xxx xx xx", "Konulara takviye gerekli."],
        ["Ahmet", "8/C", "Mehmet Bey", "05xx xxx xx xx", "Sınav tarihi: 28.10"]
    ]
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            tw.setItem(r, c, QTableWidgetItem(val))
    tw.resize(800, 300)
    tw.show()

    def ekstra(row: RowDict) -> List[str]:
        ad = row.get("Öğrenci", "")
        notu = row.get("Not", "")
        return [f"{ad} için ders çalışma önerisi: Her gün 20 dk tekrar.", f"Ek not: {notu}"]

    mgr = ListPrintManager(parent=tw, profile=PrintProfile(app="OdevTakip"), extra_info_callback=ekstra)
    mgr.run_for_table(tw, profile_key="VerilenOdevler")

    sys.exit(app.exec())
