from __future__ import annotations
# ui/weekly_plan.py
from PyQt6.QtCore import Qt, QDate, QStandardPaths
from PyQt6.QtGui import (
    QPainter, QPageSize, QFont, QAction, QKeyEvent, QFontMetrics, QColor, QBrush
)
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PyQt6.QtGui import QPageLayout
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QSpinBox,
    QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QFrame,
    QRadioButton, QHeaderView, QLineEdit, QMenu, QMessageBox, QComboBox,
    QToolButton, QSlider, QGroupBox
)
import os, json

# ----------------------- yardımcılar -----------------------

TR_GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def gun_adlari(baslangic: QDate):
    """Başlangıç gününden itibaren 7 günün Türkçe isimleri."""
    start_idx = baslangic.dayOfWeek() - 1  # QDate: 1=Mon
    return [TR_GUNLER[(start_idx + i) % 7] for i in range(7)]


# ===================== Senaryo Düzenleyici Dialog =====================

class ScenarioEditorDialog(QDialog):
    """
    Senaryo profilleri düzenleme diyaloğu.
    Kolonlar: Ad, Dakika, Maks Ödev/Gün, Ardışık İzin, Hafta Sonu Tercihi
    """
    COLS = ["Ad", "Dakika", "Maks Ödev/Gün", "Ardışık İzin", "Hafta Sonu Tercihi"]

    def __init__(self, scenarios: dict, defaults: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Senaryoları Düzenle")
        self.resize(720, 480)
        self._defaults = defaults
        # iç kopya
        self._data: dict = {k: dict(v) for k, v in scenarios.items()}

        v = QVBoxLayout(self)
        # tablo
        self.tbl = QTableWidget(0, len(self.COLS), self)
        self.tbl.setHorizontalHeaderLabels(self.COLS)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        v.addWidget(self.tbl, 1)

        # buton bar
        bar = QHBoxLayout()
        self.btnAdd = QPushButton("Ekle")
        self.btnDel = QPushButton("Sil")
        self.btnReset = QPushButton("Varsayılanları Yükle")
        bar.addWidget(self.btnAdd)
        bar.addWidget(self.btnDel)
        bar.addWidget(self.btnReset)
        bar.addWidget(self.btnReset)
        bar.addStretch(1)
        self.btnCancel = QPushButton("İptal")
        self.btnOk = QPushButton("Kaydet")
        
        self.btnAdd.setObjectName("btnPrimary")
        self.btnDel.setObjectName("btnDanger")
        self.btnReset.setObjectName("btnStandard")
        self.btnCancel.setObjectName("btnStandard")
        self.btnOk.setObjectName("btnAction")

        bar.addWidget(self.btnCancel)
        bar.addWidget(self.btnOk)
        v.addLayout(bar)

        # doldur
        self._load_table()

        # sinyaller
        self.btnAdd.clicked.connect(self._add_row)
        self.btnDel.clicked.connect(self._del_row)
        self.btnReset.clicked.connect(self._load_defaults)
        self.btnCancel.clicked.connect(self.reject)
        self.btnOk.clicked.connect(self._save_and_accept)

    # -------- helpers --------

    def _load_table(self):
        self.tbl.setRowCount(0)
        for name, prof in self._data.items():
            self._append_row(
                name,
                int(prof.get("minutes", 90)),
                int(prof.get("max_tasks", 3)),
                bool(prof.get("allow_back_to_back", False)),
                bool(prof.get("weekend_prefer", False)),
            )

    def _append_row(self, name: str, minutes: int, max_tasks: int,
                    allow_b2b: bool, weekend: bool):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)

        it_name = QTableWidgetItem(name)
        it_name.setFlags(it_name.flags() | Qt.ItemFlag.ItemIsEditable)
        self.tbl.setItem(r, 0, it_name)

        it_min = QTableWidgetItem(str(minutes))
        it_min.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        it_min.setFlags(it_min.flags() | Qt.ItemFlag.ItemIsEditable)
        self.tbl.setItem(r, 1, it_min)

        it_max = QTableWidgetItem(str(max_tasks))
        it_max.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        it_max.setFlags(it_max.flags() | Qt.ItemFlag.ItemIsEditable)
        self.tbl.setItem(r, 2, it_max)

        it_b2b = QTableWidgetItem("Evet" if allow_b2b else "Hayır")
        it_b2b.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        it_b2b.setFlags(it_b2b.flags() | Qt.ItemFlag.ItemIsEditable)
        self.tbl.setItem(r, 3, it_b2b)

        it_wk = QTableWidgetItem("Evet" if weekend else "Hayır")
        it_wk.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        it_wk.setFlags(it_wk.flags() | Qt.ItemFlag.ItemIsEditable)
        self.tbl.setItem(r, 4, it_wk)

    def _add_row(self):
        self._append_row("Yeni Senaryo", 90, 3, False, False)

    def _del_row(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.tbl.removeRow(r)

    def _load_defaults(self):
        self._data = {k: dict(v) for k, v in self._defaults.items()}
        self._load_table()

    def _save_and_accept(self):
        # tabloyu sözlüğe geri topla
        out = {}
        for r in range(self.tbl.rowCount()):
            name = (self.tbl.item(r, 0).text() if self.tbl.item(r, 0) else "").strip()
            if not name:
                continue
            try:
                minutes = int((self.tbl.item(r, 1).text() or "0").strip())
            except Exception:
                minutes = 90
            try:
                max_tasks = int((self.tbl.item(r, 2).text() or "3").strip())
            except Exception:
                max_tasks = 3
            b2b = ((self.tbl.item(r, 3).text() or "").strip().lower()
                   in ("evet", "true", "1"))
            wk = ((self.tbl.item(r, 4).text() or "").strip().lower()
                  in ("evet", "true", "1"))
            out[name] = {
                "minutes": minutes,
                "max_tasks": max_tasks,
                "allow_back_to_back": b2b,
                "weekend_prefer": wk,
            }
        self._data = out
        self.accept()

    def scenarios(self) -> dict:
        return self._data


# ===================== Haftalık Plan Dialog =====================

class HaftalikPlanDialog(QDialog):
    """
    Haftalık Plan Oluştur
    - items: [{'ders','kitap','konu','dk'}...]
    - Otomatik/Manuel işaretleme
    - Gerçek gün adları
    - PDF/Önizleme/Yazdır (+ isteğe bağlı plan özeti tablosu)
    - Senaryo profilleri (dakika + davranış)
    - Öğrenciye göre SON ödev kümesi önbelleği
    """

    # ---------- Senaryo depolama ----------
    def _scenario_store_path(self) -> str:
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        ) or "."
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "weekly_plan_scenarios.json")

    def _scenario_defaults(self):
        # Dakika=her gün baz hedef; diğer alanlar opsiyonel
        return {
            # Basit (eski) profiller
            "Standart": {
                "minutes": 90,
                "max_tasks": 3,
                "allow_back_to_back": False,
            },
            "Yoğun": {
                "minutes": 120,
                "max_tasks": 4,
                "allow_back_to_back": False,
            },
            "Sınav Haftası": {
                "minutes": 60,
                "max_tasks": 5,
                "allow_back_to_back": True,
            },
            "Hafif": {
                "minutes": 45,
                "max_tasks": 2,
                "allow_back_to_back": False,
            },
            "Esnek": {
                "minutes": 75,
                "max_tasks": 3,
                "allow_back_to_back": False,
            },
            # Yeni akıllı profiller
            "Full-time Kütüphane": {
                "minutes": 480,
                "max_tasks": 6,
                "allow_back_to_back": False,
                "weekend_prefer": False,
            },
            "Okul Sonrası": {
                "minutes": 330,
                "max_tasks": 4,
                "allow_back_to_back": True,
                "weekend_prefer": True,  # Cumartesi/Pazar tercih
            },
            "Derece Sprint": {
                "minutes": 420,
                "max_tasks": 5,
                "allow_back_to_back": False,
                "weekend_prefer": False,
            },
        }

    def _scenario_load(self):
        """Dosyayı oku, normalize et ve varsayılanlarla birleştir (eksikler eklensin)."""
        defaults = self._scenario_defaults()
        path = self._scenario_store_path()
        data = {}

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f) or {}
            except Exception:
                raw = {}
            # normalize (eski int format desteği)
            for name, val in raw.items():
                if isinstance(val, int):
                    prof = {"minutes": int(val)}
                else:
                    prof = dict(val or {})
                prof["minutes"] = int(prof.get("minutes", prof.get("mins", 90)))
                prof["max_tasks"] = int(prof.get("max_tasks", 3))
                prof["allow_back_to_back"] = bool(
                    prof.get("allow_back_to_back", False)
                )
                prof["weekend_prefer"] = bool(prof.get("weekend_prefer", False))
                data[name] = prof

        # eksik varsayılanları ekle
        changed = False
        for name, prof in defaults.items():
            if name not in data:
                data[name] = dict(prof)
                changed = True
        if changed:
            self._scenario_save(data)

        return data

    def _scenario_save(self, dct: dict):
        with open(self._scenario_store_path(), "w", encoding="utf-8") as f:
            json.dump(dct, f, ensure_ascii=False, indent=2)

    # ---------- SON ÖDEV SETİ (öğrenciye göre) ----------
    def _last_items_store_path(self) -> str:
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        ) or "."
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "weekly_plan_last_items.json")

    def _student_key(self) -> str:
        # Ad + Soyad basit anahtar (istersen ID ile değiştir)
        return (
            f"{(self.ogr_ad or '').strip()} {(self.ogr_soyad or '').strip()}".strip()
            or "_GENEL_"
        )

    def _cache_load_last_items(self) -> list[dict]:
        p = self._last_items_store_path()
        if not os.path.exists(p):
            return []
        try:
            with open(p, "r", encoding="utf-8") as f:
                all_data = json.load(f) or {}
            return list(all_data.get(self._student_key(), []))
        except Exception:
            return []

    def _cache_save_last_items(self, items: list[dict]):
        p = self._last_items_store_path()
        try:
            all_data = {}
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    all_data = json.load(f) or {}
        except Exception:
            all_data = {}
        all_data[self._student_key()] = items or []
        with open(p, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

    # ---------- Yardımcı ----------
    def _strip_minutes_suffix(self, name: str) -> str:
        """
        "Standart (180 dk)" -> "Standart"
        Sonunda ' (NN dk)' varsa ayıklarız; yoksa aynen döner.
        """
        i = name.rfind(" (")
        if i != -1 and name.endswith(" dk)"):
            return name[:i]
        return name

    def _insert_blank_rows(self, count: int = 1, per_dk: int | None = None, at_row: int | None = None):
        """items ve tabloya boş satırlar ekler (etiket göstermeden)."""
        if per_dk is None:
            per_dk = 30
        if at_row is None or at_row < 0 or at_row > self.tbl.rowCount() - 1:
            at_row = self.tbl.rowCount() - 1  # footer’ın üstüne ekle

        ins_index = min(len(self.items), at_row)

        # Veri listesine ekle
        for i in range(count):
            self.items.insert(
                ins_index + i,
                {"ders": "", "kitap": "", "konu": "", "dk": int(per_dk)}
            )

        # Tablo satırları
        for i in range(count):
            r = at_row + i
            self.tbl.insertRow(r)

            # Ödev hücresi boş gelsin
            titem = QTableWidgetItem("")
            titem.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.tbl.setItem(r, 0, titem)

            for c in range(1, 8):
                it = QTableWidgetItem("")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl.setItem(r, c, it)

            fm = self.fontMetrics()
            lines = 3  # boş satır için de 3 satırlık yükseklik
            base_h = fm.lineSpacing() * (lines + 1.2)
            self.tbl.setRowHeight(r, max(54, int(base_h)))

    def _delete_row(self, row: int):
        """Seçili veri satırını sil (footer hariç)."""
        last_data_row = self.tbl.rowCount() - 2
        if row < 0 or row > last_data_row:
            return
        if row < len(self.items):
            del self.items[row]
        self.tbl.removeRow(row)
        self._update_day_header_totals()

    # ---------- Init ----------
    class HaftalikPlanDialog(QDialog):
        ...

    def __init__(self, items, parent=None, ogrenci_adi="", ogrenci_soyadi="",
                 verilme_tarihi: QDate | None = None, bitis_tarihi: QDate | None = None,
                 gunluk_hedef: int = 90, varsayilan_sure: int = 45):
        super().__init__(parent)
        self.setWindowTitle("Haftalık Plan Oluştur")
        self.resize(1140, 660)
        self.setMinimumSize(850, 520)

        self._varsayilan_sure = max(5, int(varsayilan_sure or 45))
        self._initial_gunluk_hedef = max(0, int(gunluk_hedef or 90))

        # Temel veriler
        self.items = items or []  # dışarıdan gelen liste (boş olabilir)
        for itm in self.items:
            try:
                dval = int(itm.get("dk", 0) or 0)
            except Exception:
                dval = 0
            if dval <= 0:
                itm["dk"] = self._varsayilan_sure

        self.ogr_ad = ogrenci_adi
        self.ogr_soyad = ogrenci_soyadi
        self.verilis = verilme_tarihi or QDate.currentDate()
        self.bitis = bitis_tarihi or self.verilis.addDays(7)

        # Son seçilen otomatik dağıtma stratejisi
        self._auto_strategy = "balanced"  # balanced | intense | light | weekend

        # Senaryo profilleri
        self._scenarios: dict[str, dict] = self._scenario_load()

        # Arayüz
        self._build_ui()
        self._apply_modern_visuals()
        self._populate_table()  # self.items boşsa sadece footer satırı eklenir
        self._rebuild_day_headers()
        self._scenario_refresh_combo()

        # Başlangıçta ödev varsa otomatik olarak haftaya dengeli dağıt
        if self.items:
            self._auto_distribute("balanced")

    def _apply_modern_visuals(self):
        # Inject modern styles similar to main app
        self.setStyleSheet(self.styleSheet() + """
            QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QPushButton { 
                border-radius: 6px; padding: 6px 12px; font-weight: 500;
                background-color: #f3f4f6; border: 1px solid #d1d5db; color: #1f2937;
            }
            QPushButton:hover { background-color: #e5e7eb; }

            QPushButton#btnAction { background-color: #059669; color: white; border: none; }
            QPushButton#btnAction:hover { background-color: #047857; }

            QPushButton#btnPrimary { background-color: #2563eb; color: white; border: none; }
            QPushButton#btnPrimary:hover { background-color: #1d4ed8; }

            QPushButton#btnDanger { background-color: #fee2e2; color: #dc2626; border: 1px solid #fecaca; }
            QPushButton#btnDanger:hover { background-color: #fecaca; }
            
            QPushButton#btnSuccess { background-color: #22c55e; color: white; border: none; }
            QPushButton#btnSuccess:hover { background-color: #16a34a; }

            QPushButton#btnStandard { background-color: #fff; color: #374151; border: 1px solid #d1d5db; }
            QPushButton#btnStandard:hover { background-color: #f9fafb; }
            
            QPushButton#btnAutoDistribute { background-color: #2563eb; color: white; font-weight: bold; border: none; }
            QPushButton#btnAutoDistribute:hover { background-color: #1d4ed8; }

            QLineEdit, QComboBox, QDateEdit, QTableWidget {
                border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; background: white;
            }
            QSpinBox {
                border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; background: white;
                padding-right: 20px;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 17px;
                border-left: 1px solid #d1d5db;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
                border-top-right-radius: 4px;
            }
            QSpinBox::up-button:hover { background: #e5e7eb; }
            QSpinBox::up-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-bottom: 4.5px solid #4b5563;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 17px;
                border-left: 1px solid #d1d5db;
                background: #f9fafb;
                border-bottom-right-radius: 4px;
            }
            QSpinBox::down-button:hover { background: #e5e7eb; }
            QSpinBox::down-arrow {
                image: none;
                width: 0; height: 0;
                border-left: 3.5px solid transparent;
                border-right: 3.5px solid transparent;
                border-top: 4.5px solid #4b5563;
            }
            QLineEdit:focus, QTableWidget:focus {
                border-color: #2563eb;
            }
            QHeaderView::section { background-color: #f9fafb; padding: 4px; border: none; border-bottom: 2px solid #e5e7eb; font-weight: bold; }
        """)

    # ---------------- UI kurulum ----------------

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)

        # -------- ÜST SATIR (Row 1: Temel Parametreler) --------
        bar1 = QHBoxLayout()
        bar1.setSpacing(8)

        bar1.addWidget(QLabel("Başlangıç:"))
        self.dtBasla = QDateEdit(QDate.currentDate())
        self.dtBasla.setCalendarPopup(True)
        self.dtBasla.setMinimumWidth(110)
        bar1.addWidget(self.dtBasla)

        bar1.addSpacing(6)
        bar1.addWidget(QLabel("Günlük Hedef:"))
        self.spGunluk = QSpinBox()
        self.spGunluk.setRange(0, 1000)
        self.spGunluk.setValue(getattr(self, "_initial_gunluk_hedef", 90))
        self.spGunluk.setSuffix(" dk")
        self.spGunluk.setMaximumWidth(85)
        bar1.addWidget(self.spGunluk)

        bar1.addSpacing(6)
        bar1.addWidget(QLabel("Maks. Ödev/Gün:"))
        self.spMaxOdev = QSpinBox()
        self.spMaxOdev.setRange(1, 12)
        self.spMaxOdev.setValue(3)
        self.spMaxOdev.setMaximumWidth(70)
        bar1.addWidget(self.spMaxOdev)

        bar1.addSpacing(6)
        bar1.addWidget(QLabel("Tolerans (± dk):"))
        self.spTol = QSpinBox()
        self.spTol.setRange(0, 120)
        self.spTol.setValue(10)
        self.spTol.setMaximumWidth(70)
        bar1.addWidget(self.spTol)

        bar1.addSpacing(6)
        self.chkArdArda = QCheckBox("Aynı dersi yığma")
        bar1.addWidget(self.chkArdArda)

        bar1.addStretch(1)

        self.optAuto = QRadioButton("Otomatik")
        self.optMan = QRadioButton("Manuel")
        self.optAuto.setChecked(True)
        bar1.addWidget(self.optAuto)
        bar1.addWidget(self.optMan)

        v.addLayout(bar1)

        # -------- ALT SATIR (Row 2: Senaryolar & Ödev Süreleri) --------
        bar2 = QHBoxLayout()
        bar2.setSpacing(6)

        bar2.addWidget(QLabel("Senaryo:"))
        self.cboScenario = QComboBox()
        self.cboScenario.setMinimumContentsLength(16)
        self.cboScenario.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.cboScenario.setMinimumWidth(170)
        bar2.addWidget(self.cboScenario)

        self.spScenarioMin = QSpinBox()
        self.spScenarioMin.setRange(0, 1000)
        self.spScenarioMin.setVisible(False)

        self.btnScnSave = QPushButton("Kaydet")
        self.btnScnDel = QPushButton("Sil")
        self.btnScnEdit = QPushButton("Senaryoları Düzenle")
        
        self.btnScnSave.setObjectName("btnAction")
        self.btnScnDel.setObjectName("btnDanger")
        self.btnScnEdit.setObjectName("btnStandard")
        
        bar2.addWidget(self.btnScnSave)
        bar2.addWidget(self.btnScnDel)
        bar2.addWidget(self.btnScnEdit)

        bar2.addSpacing(12)
        lbl_dur = QLabel("⏱️ Ödev Süresi:")
        lbl_dur.setStyleSheet("font-weight: 500; color: #1e293b;")
        bar2.addWidget(lbl_dur)

        self.spOdevSure = QSpinBox()
        self.spOdevSure.setRange(5, 300)
        self.spOdevSure.setSingleStep(5)
        self.spOdevSure.setValue(getattr(self, "_varsayilan_sure", 45))
        self.spOdevSure.setSuffix(" dk")
        self.spOdevSure.setFixedWidth(72)
        self.spOdevSure.setToolTip("Plandaki ödevlerin varsayılan süresi")
        bar2.addWidget(self.spOdevSure)

        self.btnApplyDurAll = QPushButton("⚡ Tümüne Uygula")
        self.btnApplyDurAll.setObjectName("btnStandard")
        self.btnApplyDurAll.setToolTip("Plandaki TÜM ödevlerin süresini bu değere ayarla ve hücreleri güncelle")
        self.btnApplyDurAll.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnApplyDurAll.clicked.connect(self._apply_duration_to_all_tasks)
        bar2.addWidget(self.btnApplyDurAll)

        bar2.addStretch(1)

        v.addLayout(bar2)

        # -------- TABLO --------
        self.tbl = QTableWidget(0, 8, self)
        self.tbl.setFrameShape(QFrame.Shape.StyledPanel)
        self.tbl.verticalHeader().setVisible(True)
        self.tbl.horizontalHeader().setVisible(True)
        self.tbl.setWordWrap(True)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 8):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch)
        self.tbl.setHorizontalHeaderItem(0, QTableWidgetItem("Ödev"))

        self.tbl.setStyleSheet("""
            QTableWidget { gridline-color: #a0a0a0; }
            QTableWidget::item { border: 1px solid #b0b0b0; padding: 6px; }
        """)
        v.addWidget(self.tbl, 1)

        # -------- ALT AYARLAR & SEÇENEKLER (Satır 1) --------
        self.chkIncludeSummary = QCheckBox("PDF çıktısında Plan Özeti tablosu olsun")
        self.chkIncludeSummary.setChecked(False)

        self.chkFooterAuto = QCheckBox("Günlük hedef satırını otomatik doldur")
        self.chkFooterAuto.setChecked(True)
        self.chkFooterAuto.toggled.connect(lambda _on: self._footer_fill_all_days())

        row_settings = QHBoxLayout()
        row_settings.setSpacing(12)

        # Dağıtım Ayarları Kutusu
        grp_settings = QGroupBox("Dağıtım Ayarları")
        grp_settings.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; 
                border: 1px solid #d1d5db; 
                border-radius: 6px; 
                margin-top: 14px; 
                padding: 4px 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                color: #374151;
            }
            QLabel { font-weight: normal; }
        """)
        lay_settings = QHBoxLayout(grp_settings)
        lay_settings.setContentsMargins(8, 2, 8, 4)

        # Slider
        lblDensityIcon = QLabel("⚡")
        self.lblDensity = QLabel("Yoğunluk: %100")
        self.lblDensity.setMinimumWidth(85)
        self.sliderDensity = QSlider(Qt.Orientation.Horizontal)
        self.sliderDensity.setRange(50, 150)
        self.sliderDensity.setValue(100)
        self.sliderDensity.setFixedWidth(130)
        self.sliderDensity.setToolTip("Otomatik dağıtımda hedef süreyi ve kapasiteyi çarpar.")
        self.sliderDensity.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dcfce7, stop:1 #fee2e2);
                height: 10px;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #3b82f6;
                border-radius: 4px;
            }
            QSlider::add-page:horizontal {
                background: #e5e7eb;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #1d4ed8;
                border: 1px solid #1e40af;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)

        # Karıştır Checkbox
        self.chkShuffle = QCheckBox("Karıştır")
        self.chkShuffle.setToolTip("Dersleri rastgele sırada dağıtır (her seferinde farklı sonuçlar için).")

        lay_settings.addWidget(lblDensityIcon)
        lay_settings.addWidget(self.sliderDensity)
        lay_settings.addWidget(self.lblDensity)
        lay_settings.addSpacing(8)
        lay_settings.addWidget(self.chkShuffle)
        
        row_settings.addWidget(grp_settings)
        row_settings.addStretch(1)

        # Sağ: PDF Özeti ve Son Strateji
        v_opt = QVBoxLayout()
        v_opt.setSpacing(2)
        v_opt.addWidget(self.chkIncludeSummary)
        self.lblLastStrategy = QLabel("Son strateji: Dengeli dağıt (önerilen)")
        self.lblLastStrategy.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
        v_opt.addWidget(self.lblLastStrategy)
        row_settings.addLayout(v_opt)

        v.addLayout(row_settings)

        # -------- ALT EYLEMLER & DAĞITIM ÇUBUĞU (Satır 2 - Responsive) --------
        row_actions = QHBoxLayout()
        row_actions.setSpacing(8)

        self.btnYazdir = QPushButton("📄 PDF / Yazdır")
        self.btnYazdir.setObjectName("btnStandard")
        self.btnYazdir.setFixedHeight(32)
        self.btnYazdir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnYazdir.setStyleSheet("padding: 4px 14px; font-weight: 600; font-size: 12px;")

        lbl_strat = QLabel("Strateji:")
        lbl_strat.setStyleSheet("font-weight: bold; color: #374151; font-size: 12px;")

        self.cboAutoStrategy = QComboBox()
        self.cboAutoStrategy.setFixedHeight(32)
        self.cboAutoStrategy.setMinimumWidth(160)
        self.cboAutoStrategy.addItem("⚖️ Dengeli Dağıt (Önerilen)", "balanced")
        self.cboAutoStrategy.addItem("🔥 Yoğun / Derece Modu", "intense")
        self.cboAutoStrategy.addItem("🌱 Hafif / Rahat Mod", "light")
        self.cboAutoStrategy.addItem("📅 Hafta Sonu Ağırlıklı", "weekend")
        self.cboAutoStrategy.addItem("🧱 Ders Blokları Modu", "block_course")
        self.cboAutoStrategy.addItem("📦 Yoğun Blok Günler", "block_dense")
        self.cboAutoStrategy.addItem("🧹 Dağıtımı Temizle", "clear")

        self.btnAuto = QPushButton("⚡ Otomatik Dağıt")
        self.btnAuto.setObjectName("btnAutoDistribute")
        self.btnAuto.setFixedHeight(32)
        self.btnAuto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnAuto.setToolTip("Ödevleri seçili stratejiye göre anında günlere dağıtır.")
        self.btnAuto.setStyleSheet("padding: 4px 14px; font-weight: bold; font-size: 12px;")

        self.btnUygula = QPushButton("Planı Uygula")
        self.btnUygula.setObjectName("btnSuccess")
        self.btnUygula.setFixedHeight(32)
        self.btnUygula.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnUygula.setStyleSheet("padding: 4px 18px; font-weight: bold; font-size: 12.5px;")

        row_actions.addWidget(self.btnYazdir)
        row_actions.addStretch(1)
        row_actions.addWidget(lbl_strat)
        row_actions.addWidget(self.cboAutoStrategy)
        row_actions.addWidget(self.btnAuto)
        row_actions.addWidget(self.btnUygula)

        v.addLayout(row_actions)

        # Footer satırı girdisi (kullanıcıya gösterilmiyor, footer hücrelerini doldurmak için)
        self.footer_line = QLineEdit()
        self.footer_line.setPlaceholderText("ör. 90 dk (önerilen)")
        self.footer_line.setText(str(self.spGunluk.value()) + " dk")

        # -------- SİNYALLER --------
        self.dtBasla.dateChanged.connect(self._rebuild_day_headers)

        self.btnYazdir.clicked.connect(self._print_preview)
        self.btnUygula.clicked.connect(self._accept_with_result)
        self.btnAuto.clicked.connect(self._on_btn_auto_clicked)
        self.cboAutoStrategy.currentIndexChanged.connect(self._on_strategy_combo_changed)

        # Slider sinyali
        self.sliderDensity.valueChanged.connect(self._density_changed)

        self.optMan.toggled.connect(self._mode_changed)
        self.tbl.cellDoubleClicked.connect(self._toggle_cell)
        self.tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._table_menu)

        # Senaryo sinyalleri
        self.cboScenario.currentTextChanged.connect(self._scenario_changed)
        self.btnScnSave.clicked.connect(self._scenario_save_clicked)
        self.btnScnDel.clicked.connect(self._scenario_delete_clicked)
        self.btnScnEdit.clicked.connect(self._open_scenario_editor)
        self.spScenarioMin.valueChanged.connect(self._scenario_min_changed)

        # Günlük hedef değişince footer’ı güncelle
        self.spGunluk.valueChanged.connect(self._on_gunluk_changed)

    def _on_btn_auto_clicked(self):
        strategy = self.cboAutoStrategy.currentData() or "balanced"
        self._auto_distribute(strategy)

    def _on_strategy_combo_changed(self, idx: int):
        strategy = self.cboAutoStrategy.currentData() or "balanced"
        self._auto_distribute(strategy)

    def _build_auto_menu(self):
        pass
    # -------- Otomatik Dağıt menüsü / stratejiler --------

    def _init_auto_menu(self):
        """Otomatik dağıt açılır menüsünü kur."""
        self.mnuAuto = QMenu(self)

        def add_action(key, text, desc):
            act = self.mnuAuto.addAction(text)
            act.setData(key)
            act.setToolTip(desc)

        add_action("balanced", "Dengeli dağıt (önerilen)",
                   "Günlük hedef etrafında, güne eşit dağılmış plan.")
        add_action("intense", "Yoğun / Derece modu",
                   "Günlük dakikayı biraz yükseltir, daha çok ödev dağıtır.")
        add_action("light", "Hafif / Yeni başlayan",
                   "Günlük dakikayı ve ödev sayısını azaltır.")
        add_action("weekend", "Hafta sonu ağırlıklı",
                   "Yoğunluğu Cumartesi-Pazar günlerine taşır.")

        self.mnuAuto.triggered.connect(self._on_auto_strategy_triggered)

        # Hover efekti
        self.mnuAuto.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #c0c0c0;
            }
            QMenu::item {
                padding: 6px 14px;
            }
            QMenu::item:selected {
                background: #0078d7;
                color: white;
            }
        """)

        self._update_auto_hint(self._auto_strategy)

    def _show_auto_menu(self):
        """Otomatik Dağıt butonuna tıklanınca menüyü göster."""
        pos = self.btnAutoDistrib.mapToGlobal(self.btnAutoDistrib.rect().bottomLeft())
        self.mnuAuto.exec(pos)

    def _on_auto_strategy_triggered(self, act: QAction):
        mode = act.data() or "balanced"
        self._auto_strategy = mode
        self._update_auto_hint(mode)
        self._auto_distribute(mode)

    def _update_auto_hint(self, mode: str | None = None):
        if mode is None:
            mode = self._auto_strategy
        mapping = {
            "balanced": "Son strateji: Dengeli (önerilen)",
            "intense":  "Son strateji: Yoğun / Derece",
            "light":    "Son strateji: Hafif",
            "weekend":  "Son strateji: Hafta sonu ağırlıklı",
        }
        if hasattr(self, "lblDistribHint"):
            self.lblDistribHint.setText(mapping.get(mode, "Son strateji: Dengeli (önerilen)"))

    # ------- Senaryo UI yardımcıları -------

    def _scenario_refresh_combo(self):
        cur = self.cboScenario.currentText()
        self.cboScenario.blockSignals(True)
        self.cboScenario.clear()
        for name, prof in self._scenarios.items():
            base = self._strip_minutes_suffix(name)
            mins = int(prof.get("minutes", 90))
            self.cboScenario.addItem(f"{base} ({mins} dk)")
        self.cboScenario.blockSignals(False)

        matched_idx = -1
        if hasattr(self, "_initial_gunluk_hedef") and self._initial_gunluk_hedef > 0:
            for i in range(self.cboScenario.count()):
                if f"({self._initial_gunluk_hedef} dk)" in self.cboScenario.itemText(i):
                    matched_idx = i
                    break

        if matched_idx >= 0:
            self.cboScenario.setCurrentIndex(matched_idx)
        elif cur:
            idx = self.cboScenario.findText(cur)
            if idx >= 0:
                self.cboScenario.setCurrentIndex(idx)
        if self.cboScenario.count() > 0 and self.cboScenario.currentIndex() < 0:
            self.cboScenario.setCurrentIndex(0)

        self._scenario_changed(self.cboScenario.currentText())

        if hasattr(self, "_initial_gunluk_hedef") and self._initial_gunluk_hedef > 0 and matched_idx < 0:
            self.spGunluk.setValue(self._initial_gunluk_hedef)

    def _active_profile(self) -> dict:
        label = self.cboScenario.currentText()
        key = self._strip_minutes_suffix(label)
        prof = None
        if key in self._scenarios:
            prof = self._scenarios.get(key, {})
        else:
            for k, v in self._scenarios.items():
                if self._strip_minutes_suffix(k) == key:
                    prof = v
                    break
        if prof is None:
            prof = {}

        return {
            "minutes": int(prof.get("minutes", self.spGunluk.value())),
            "max_tasks": int(prof.get("max_tasks", self.spMaxOdev.value())),
            "allow_back_to_back": bool(
                prof.get("allow_back_to_back", not self.chkArdArda.isChecked())
            ),
            "weekend_prefer": bool(prof.get("weekend_prefer", False)),
        }

    def _scenario_changed(self, _name_label: str):
        prof = self._active_profile()
        self.spScenarioMin.blockSignals(True)
        self.spScenarioMin.setValue(prof["minutes"])
        self.spScenarioMin.blockSignals(False)

        self.spGunluk.blockSignals(True)
        self.spGunluk.setValue(prof["minutes"])
        self.spGunluk.blockSignals(False)

        self.spMaxOdev.setValue(prof["max_tasks"])
        self.chkArdArda.setChecked(not prof["allow_back_to_back"])
        self._on_gunluk_changed(prof["minutes"])
        self._update_load_visuals()

    def _scenario_min_changed(self, val: int):
        self.spGunluk.blockSignals(True)
        self.spGunluk.setValue(val)
        self.spGunluk.blockSignals(False)
        self._on_gunluk_changed(val)
        self._update_load_visuals()

    def _density_changed(self, val: int):
        self.lblDensity.setText(f"Yoğunluk: %{val}")
        # Canlı önizleme: Eğer otomatik moddaysa ve manuel işaretli DEĞİLSE dağıtımı güncelle
        if hasattr(self, "optAuto") and self.optAuto.isChecked():
            # Performans için belki timer konabilir ama şimdilik doğrudan çağırıyoruz (küçük veri)
            self._auto_distribute()
        else:
             self._update_load_visuals()

    def _mark_cell(self, row: int, col: int, dk: int = 0):
        it = self.tbl.item(row, col)
        if it is None:
            it = QTableWidgetItem()
            self.tbl.setItem(row, col, it)
        badge_text = f"✔ {dk} dk" if dk > 0 else "✔"
        it.setText(badge_text)
        it.setBackground(QBrush(QColor("#dcfce7")))
        it.setForeground(QBrush(QColor("#166534")))
        font = it.font()
        font.setBold(True)
        it.setFont(font)
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _unmark_cell(self, row: int, col: int):
        it = self.tbl.item(row, col)
        if it is None:
            return
        it.setText("")
        it.setBackground(QBrush(QColor(255, 255, 255)))
        it.setForeground(QBrush(QColor(0, 0, 0)))

    def _update_load_visuals(self):
        """
        Headers heatmap colorization based on load:
        Green: 85-115% of target (ideal)
        Blue: 40-85% of target (light)
        Yellow: 115-135% of target (moderately heavy)
        Red: >135% (overload)
        """
        from PyQt6.QtGui import QColor
        day_names, totals, counts = self._compute_day_totals()
        target = self.spGunluk.value() or 90

        for c in range(7):
            name = day_names[c]
            load = totals[c]
            cnt = counts[c]
            ratio = load / target if target > 0 else 0

            bg = "#f9fafb"
            fg = "#374151"

            if load > 0:
                if 0.85 <= ratio <= 1.15:
                    bg = "#dcfce7"  # green-100 (ideal)
                    fg = "#14532d"
                elif 0.35 <= ratio < 0.85:
                    bg = "#e0f2fe"  # blue-100 (light)
                    fg = "#0369a1"
                elif 1.15 < ratio <= 1.35:
                    bg = "#fef9c3"  # yellow-100 (moderate)
                    fg = "#713f12"
                else:  # > 1.35
                    bg = "#fee2e2"  # red-100 (overload)
                    fg = "#7f1d1d"

            it = self.tbl.horizontalHeaderItem(c + 1)
            if it is None:
                it = QTableWidgetItem()
                self.tbl.setHorizontalHeaderItem(c + 1, it)

            it.setBackground(QColor(bg))
            it.setForeground(QColor(fg))
            if load > 0:
                it.setText(f"{name}\n{load} dk ({cnt} Ödev)")
            else:
                it.setText(f"{name}\n(0 dk)")

    def _scenario_save_clicked(self):
        from PyQt6.QtWidgets import QInputDialog

        mins = int(self.spScenarioMin.value())

        name, ok = QInputDialog.getText(
            self, "Senaryo İsmi", "Bu senaryoya bir isim verin:"
        )
        if not ok or not name.strip():
            return
        key = name.strip()

        prof = {
            "minutes": mins,
            "max_tasks": int(self.spMaxOdev.value()),
            "allow_back_to_back": not self.chkArdArda.isChecked(),
            "weekend_prefer": bool(self._active_profile().get("weekend_prefer", False)),
        }

        self._scenarios[key] = prof
        self._scenario_save(self._scenarios)
        self._scenario_refresh_combo()
        QMessageBox.information(self, "Senaryo", "Kaydedildi.")

    def _scenario_delete_clicked(self):
        label = self.cboScenario.currentText().strip()
        key = self._strip_minutes_suffix(label)
        target = None
        if key in self._scenarios:
            target = key
        else:
            for k in list(self._scenarios.keys()):
                if self._strip_minutes_suffix(k) == key:
                    target = k
                    break
        if not target:
            return
        if (
            QMessageBox.question(
                self, "Senaryo Sil", f"“{key}” silinsin mi?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        del self._scenarios[target]
        self._scenario_save(self._scenarios)
        self._scenario_refresh_combo()

    def _open_scenario_editor(self):
        dlg = ScenarioEditorDialog(self._scenarios, self._scenario_defaults(), self)
        if dlg.exec():
            self._scenarios = dlg.scenarios()
            self._scenario_save(self._scenarios)
            self._scenario_refresh_combo()

    # ---------------- tablo doldurma ----------------

    def _populate_table(self):
        self.tbl.setRowCount(0)
        for it in (self.items or []):
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)

            ders = it.get("ders", "")
            kitap = it.get("kitap", "")
            konu = it.get("konu", "")
            dk = int(it.get("dk", 0) or 0)

            text = f"{ders}\n{kitap}\n{konu}".strip("\n")
            titem = QTableWidgetItem(text)
            titem.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self.tbl.setItem(r, 0, titem)

            for c in range(1, 8):
                icell = QTableWidgetItem("")
                icell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl.setItem(r, c, icell)

            # 3 satırlık metin (ders / kitap / konu) rahatça sığsın
            fm = self.fontMetrics()

            # İlgili satırdaki Ödev hücresinin metnine bak
            item = self.tbl.item(r, 0)
            txt = item.text() if item is not None else ""

            # Metindeki satır sayısına göre yükseklik; en az 3 satır kabul et
            lines = max(3, txt.count("\n") + 1)
            base_h = fm.lineSpacing() * (lines + 1.2)  # satırlar + ufak boşluk

            self.tbl.setRowHeight(r, max(54, int(base_h)))

        self._add_footer_row()
        self._update_day_header_totals()

    def _add_footer_row(self):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        it = QTableWidgetItem("Günlük hedef\nçalışma süresi:")
        it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.tbl.setItem(r, 0, it)
        self.tbl.item(r, 0).setBackground(Qt.GlobalColor.lightGray)

        val = self.footer_line.text()
        for c in range(1, 8):
            lab = QTableWidgetItem(val)
            lab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tbl.setItem(r, c, lab)

        if r > 0:
            self.tbl.setRowHeight(r, max(self.tbl.rowHeight(r - 1), 36))

    def _footer_fill_all_days(self):
        r = self.tbl.rowCount() - 1
        if r < 0:
            return
        val = self.footer_line.text()
        for c in range(1, 8):
            it = self.tbl.item(r, c)
            if it is None:
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl.setItem(r, c, it)
            it.setText(val)

    def _on_gunluk_changed(self, mins: int):
        self.footer_line.setText(f"{mins} dk")
        self._footer_fill_all_days()
        self._update_day_header_totals()

    # ---------------- günlük toplam dk hesaplama ----------------

    def _compute_day_totals(self):
        """
        Her gün için (Pzt–Pazar) toplam dk ve ödev sayısını hesaplar.
        """
        day_names = gun_adlari(self.dtBasla.date())
        totals = [0] * 7
        counts = [0] * 7

        last_row = self.tbl.rowCount() - 1
        if last_row < 0:
            return day_names, totals, counts

        for r in range(last_row):
            it_src = self.items[r] if r < len(self.items) else {}
            try:
                dk = int(it_src.get("dk", 0) or 0)
            except Exception:
                dk = 0
            if dk <= 0:
                dk = getattr(self, "_varsayilan_sure", 45)

            for c in range(7):
                cell = self.tbl.item(r, c + 1)
                if cell and (cell.text() or "").strip():
                    totals[c] += dk
                    counts[c] += 1

        return day_names, totals, counts

    def _update_day_header_totals(self):
        self._update_load_visuals()

    # ---------------- başlık/gün adları ----------------

    def _rebuild_day_headers(self):
        adlar = gun_adlari(self.dtBasla.date())
        for i, ad in enumerate(adlar, start=1):
            self.tbl.setHorizontalHeaderItem(i, QTableWidgetItem(ad))

    def _on_date_changed(self, _d: QDate):
        self._rebuild_day_headers()
        self._update_day_header_totals()

    # ---------------- manuel işaretleme & süre yönetimi ----------------

    def _apply_duration_to_all_tasks(self):
        new_dk = self.spOdevSure.value() if hasattr(self, "spOdevSure") else 45
        self._varsayilan_sure = new_dk
        for itm in self.items:
            itm["dk"] = new_dk
        for r in range(self.tbl.rowCount() - 1):
            for c in range(1, 8):
                cell = self.tbl.item(r, c)
                if cell and (cell.text() or "").strip():
                    cell.setText(f"✔ {new_dk} dk")
        self._update_load_visuals()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Bilgi", f"Tüm ödevlerin süresi {new_dk} dk olarak güncellendi.")

    def _prompt_change_row_duration(self, row: int):
        if row < 0 or row >= (self.tbl.rowCount() - 1):
            return
        from PyQt6.QtWidgets import QInputDialog
        curr_dk = getattr(self, "_varsayilan_sure", 45)
        task_label = "Seçili Ödev"
        if row < len(self.items):
            itm = self.items[row]
            curr_dk = int(itm.get("dk", 0) or getattr(self, "_varsayilan_sure", 45))
            d = itm.get("ders", "")
            k = itm.get("konu", "")
            if d or k:
                task_label = f"{d} - {k}".strip(" -")
        new_val, ok = QInputDialog.getInt(self, "Ödev Süresi Düzenle",
                                          f"'{task_label}' için süre (dakika):",
                                          curr_dk, 5, 360, 5)
        if ok and new_val > 0:
            if row < len(self.items):
                self.items[row]["dk"] = new_val
            for c in range(1, 8):
                cell = self.tbl.item(row, c)
                if cell and (cell.text() or "").strip():
                    cell.setText(f"✔ {new_val} dk")
            self._update_load_visuals()

    def _toggle_cell(self, row: int, col: int):
        if row >= (self.tbl.rowCount() - 1):
            return
        if col == 0:
            self._prompt_change_row_duration(row)
            return
        if col < 1:
            return
        it = self.tbl.item(row, col)
        if it and (it.text() or "").strip():
            self._unmark_cell(row, col)
        else:
            dk = getattr(self, "_varsayilan_sure", 45)
            if row < len(self.items):
                dk = int(self.items[row].get("dk", 0) or getattr(self, "_varsayilan_sure", 45))
            self._mark_cell(row, col, dk)
        self._update_load_visuals()

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Space:
            idx = self.tbl.currentIndex()
            if idx.isValid():
                self._toggle_cell(idx.row(), idx.column())
                return
        super().keyPressEvent(e)

    # --------- sağ tık menü + özetler ---------

    def _table_menu(self, pos):
        idx = self.tbl.indexAt(pos)
        row = idx.row()

        menu = QMenu(self)
        # Modern stil
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
                color: #1e293b;
            }
            QMenu::item:selected {
                background: #eff6ff;
                color: #2563eb;
            }
            QMenu::separator {
                height: 1px;
                background: #e2e8f0;
                margin: 4px 8px;
            }
        """)

        a_add_above = QAction("⬆️ Üstüne boş satır ekle", self)
        a_add_below = QAction("⬇️ Altına boş satır ekle", self)
        a_del = QAction("🗑️ Seçili satırı sil", self)

        if idx.isValid() and row < (self.tbl.rowCount() - 1):
            curr_dk = getattr(self, "_varsayilan_sure", 45)
            if row < len(self.items):
                curr_dk = int(self.items[row].get("dk", 0) or getattr(self, "_varsayilan_sure", 45))
            a_set_dur = QAction(f"⏱️ Bu Ödevin Süresini Değiştir ({curr_dk} dk)...", self)
            a_set_dur.triggered.connect(lambda: self._prompt_change_row_duration(row))
            menu.addAction(a_set_dur)
            menu.addSeparator()

        menu.addAction(a_add_above)
        menu.addAction(a_add_below)
        menu.addAction(a_del)
        menu.addSeparator()

        a_row = QAction("🧹 Bu satırdaki işaretleri temizle", self)
        a_week = QAction("📅 Bu satırı haftaya dağıt (1’er gün)", self)
        a_all = QAction("❌ Tüm işaretleri temizle", self)
        
        menu.addAction(a_row)
        menu.addAction(a_week)
        menu.addSeparator()
        menu.addAction(a_all)

        # Bağlantılar
        a_add_above.triggered.connect(lambda: self._insert_blank_rows(1, at_row=row))
        a_add_below.triggered.connect(lambda: self._insert_blank_rows(1, at_row=row + 1))
        a_del.triggered.connect(lambda: self._delete_row(row))
        a_row.triggered.connect(lambda: self._clear_row(row))
        a_all.triggered.connect(self._clear_all_marks)
        a_week.triggered.connect(lambda: self._spread_row(row))

        # Footer’da bazılarını pasifleştir
        if (not idx.isValid()) or row >= (self.tbl.rowCount() - 1):
            a_row.setEnabled(False)
            a_week.setEnabled(False)
            a_del.setEnabled(False)

        menu.exec(self.tbl.viewport().mapToGlobal(pos))

    def _clear_row(self, row: int):
        if row < 0 or row >= (self.tbl.rowCount() - 1):
            return
        for c in range(1, 8):
            self._unmark_cell(row, c)
        self._update_load_visuals()

    def _clear_all_marks(self):
        for r in range(self.tbl.rowCount() - 1):
            for c in range(1, 8):
                self._unmark_cell(r, c)
        self._update_load_visuals()

    def _spread_row(self, row: int):
        if row < 0 or row >= (self.tbl.rowCount() - 1):
            return
        dk = 45
        if row < len(self.items):
            dk = int(self.items[row].get("dk", 0) or 45)
        for c in range(1, 8):
            self._mark_cell(row, c, dk)
        self._update_load_visuals()

    def _show_week_summary(self):
        day_names, totals, counts = self._compute_day_totals()
        total_all = sum(totals)
        total_tasks = sum(counts)

        lines = []
        for d, t, c in zip(day_names, totals, counts):
            if t:
                lines.append(f"{d}: {t} dk, {c} ödev")

        if not lines:
            msg = "Henüz herhangi bir gün için işaretlenmiş ödev bulunmuyor."
        else:
            msg = "Haftalık çalışma özeti:\n\n" + "\n".join(lines)
            msg += f"\n\nGenel toplam: {total_all} dk, {total_tasks} ödev"
            hedef = self.spGunluk.value()
            if hedef > 0:
                ort = total_all / len(day_names)
                msg += f"\nGünlük ortalama: {ort:.1f} dk (hedef: {hedef} dk)"

        QMessageBox.information(self, "Haftalık Özet", msg)

    def _show_day_summary(self, col: int):
        if col < 1:
            return
        day_names, totals, counts = self._compute_day_totals()
        idx = col - 1
        name = day_names[idx]
        t = totals[idx]
        c = counts[idx]

        if t == 0:
            msg = f"{name} günü için henüz işaretlenmiş ödev yok."
        else:
            msg = (
                f"{name} günü toplam {t} dk çalışma ve {c} ödev planlanmış görünüyor."
            )
            hedef = self.spGunluk.value()
            tol = self.spTol.value()
            if hedef > 0:
                diff = t - hedef
                if abs(diff) <= tol:
                    durum = "hedefe çok yakın 👍"
                elif diff > 0:
                    durum = f"hedefin {diff} dk üzerinde"
                else:
                    durum = f"hedefin {-diff} dk altında"
                msg += f"\nGünlük hedef: {hedef} dk (Durum: {durum})"

        QMessageBox.information(self, name, msg)

    # ---------------- mod ----------------

    def _mode_changed(self, manual_on: bool):
        # Manuel mod açıldığında otomatik dağıt butonunu devre dışı bırak
        self.btnAuto.setEnabled(not manual_on)

    # ---------------- otomatik dağıtım MENÜSÜ ----------------

    def _auto_distribute_menu(self):
        """
        Otomatik dağıt (Simüle) butonu için açılır menü.
        Kullanıcı mod seçiyor, sonra ilgili dağıtım yapılıyor.
        """
        if not self.items:
            QMessageBox.information(self, "Otomatik Dağıt", "Önce en az bir ödev ekleyin.")
            return

        menu = QMenu(self)
        # HOVER efekti
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #c0c0c0;
            }
            QMenu::item {
                padding: 6px 18px;
            }
            QMenu::item:selected {
                background: #0078d4;
                color: #ffffff;
            }
        """)

        label_to_mode = {
            "Dengeli dağıt (önerilen)": "balanced",
            "Hafta içi yoğun, hafta sonu hafif": "weekday_heavy",
            "Hafta sonu yoğun (deneme odaklı)": "weekend_heavy",
            "En az bir gün boş kalsın (genelde Pazar)": "keep_free_day",
        }

        for text in label_to_mode:
            menu.addAction(text)

        act = menu.exec(
            self.btnSim.mapToGlobal(self.btnSim.rect().bottomLeft())
        )
        if act is None:
            return

        mode = label_to_mode.get(act.text(), "balanced")

        # Hata olursa kullanıcıya göster
        try:
            self._auto_distribute(mode)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Otomatik Dağıtım Hatası",
                f"Otomatik dağıtılırken bir hata oluştu:\n\n{e}",
            )

    # ---------------- otomatik dağıtım CORE ----------------
    # ---------------- BLOK DAĞITMA YARDIMCILARI ----------------

    # ---------------- BLOK DAĞITMA YARDIMCILARI ----------------

    def _distribute_block_dense(self, hedef: int, tol: int, cap: int):
        """
        Blok dağıt (yoğun günler):
        - 1. günden başlar, o günü hedef+tol*1.2 civarına kadar doldurur.
        - Sonra 2. güne geçer; hepsi dolarsa en az dolu günü seçer.
        - Amaç: Bazı günler çok yoğun, bazı günler hafif; “full kütüphane günü”
          isteyen derece öğrencileri için.
        """
        self._clear_all_marks()

        last_data_row = self.tbl.rowCount() - 1  # footer hariç
        if last_data_row <= 0:
            return

        # satır sürelerini oku (yoksa 0)
        row_dk = []
        for r in range(last_data_row):
            it_src = self.items[r] if r < len(self.items) else {}
            row_dk.append(int(it_src.get("dk", 0) or 0))

        # daha profesyonel görünmesi için en uzunlardan başlayalım
        rows = sorted(range(last_data_row), key=lambda r: row_dk[r], reverse=True)

        gun_dk = [0] * 7
        gun_adet = [0] * 7

        gun_adi = [
            self.tbl.horizontalHeaderItem(i).text().split("\n")[0]
            if self.tbl.horizontalHeaderItem(i) else TR_GUNLER[i - 1]
            for i in range(1, 8)
        ]

        g = 0  # aktif gün (0..6)

        for r in rows:
            dk = row_dk[r]
            # mevcut günde yer açılana kadar sonraki güne geç
            while g < 6 and (
                    gun_dk[g] + dk > hedef + int(tol * 1.2) or gun_adet[g] >= cap
            ):
                g += 1

            if g > 6:
                # tüm günler dolu; en az dk olan güne kaydır
                g = min(range(7), key=lambda i: gun_dk[i])

            if dk <= 0:
                dk = 45
            self._mark_cell(r, g + 1, dk)
            gun_dk[g] += dk
            gun_adet[g] += 1

        self._update_load_visuals()

    def _distribute_block_by_course(self, hedef: int, tol: int, cap: int):
        """
        Blok dağıt (ders blokları) – GELİŞMİŞ

        Hedef:
        - Aynı dersi mümkün olduğunca bloklar halinde tut.
        - Ama sadece 2–3 günü doldurup diğer günleri boş bırakma;
          toplam yükü tüm haftaya yaymaya çalış.
        """
        self._clear_all_marks()

        last_data_row = self.tbl.rowCount() - 1  # footer hariç
        if last_data_row <= 0:
            return

        gun_dk = [0] * 7
        gun_adet = [0] * 7

        gun_adi = [
            self.tbl.horizontalHeaderItem(i).text().split("\n")[0]
            if self.tbl.horizontalHeaderItem(i) else TR_GUNLER[i - 1]
            for i in range(1, 8)
        ]

        # ders -> satır listesi
        course_rows: dict[str, list[int]] = {}
        row_dk: dict[int, int] = {}

        for r in range(last_data_row):
            it_src = self.items[r] if r < len(self.items) else {}
            ders = (it_src.get("ders", "") or "").strip() or "(Diğer)"
            dk = int(it_src.get("dk", 0) or 0)
            course_rows.setdefault(ders, []).append(r)
            row_dk[r] = dk

        # dersleri toplam sürelerine göre sırala (uzun dersler önce)
        def toplam_sure(row_list: list[int]) -> int:
            return sum(row_dk.get(rr, 0) for rr in row_list)

        ordered_courses = sorted(
            course_rows.items(),
            key=lambda kv: toplam_sure(kv[1]),
            reverse=True
        )

        # Her dersin hangi günlerde kullanıldığını tutalım (blok etkisi için)
        course_days: dict[str, set[int]] = {}

        for ders, rows in ordered_courses:
            used_days = course_days.setdefault(ders, set())

            # Bu dersin satırlarını da uzunluktan küçüğe sırala
            rows_sorted = sorted(rows, key=lambda rr: row_dk.get(rr, 0), reverse=True)

            for r in rows_sorted:
                dk = row_dk.get(r, 0)

                # 1) Günleri, toplam dk + ödev sayısına göre azdan çoğa sırala
                day_order = sorted(
                    range(7),
                    key=lambda g: (gun_dk[g], gun_adet[g])
                )

                # 2) Önce bu derste daha önce kullanılan günleri dene (blok etkisi)
                preferred = [g for g in day_order if g in used_days]
                others = [g for g in day_order if g not in used_days]
                candidates = preferred + others

                placed = False
                limit = hedef + int(tol * 1.2)

                for g in candidates:
                    # kapasite kontrolü
                    if gun_adet[g] >= cap:
                        continue
                    if gun_dk[g] + dk > limit:
                        continue

                    # bu güne yerleştirebiliyoruz
                    if dk <= 0:
                        dk = 45
                    self._mark_cell(r, g + 1, dk)
                    gun_dk[g] += dk
                    gun_adet[g] += 1
                    used_days.add(g)
                    placed = True
                    break

                if not placed:
                    # her yere sığmadıysa, kısıtları biraz esnetip
                    # en az yükü olan güne zorunlu yerleştir
                    g = min(range(7), key=lambda i: (gun_dk[i], gun_adet[i]))
                    if dk <= 0:
                        dk = 45
                    self._mark_cell(r, g + 1, dk)
                    gun_dk[g] += dk
                    gun_adet[g] += 1
                    used_days.add(g)

        # Görsel yük dağılımını ve ısı haritasını güncelle
        self._update_load_visuals()

    def _auto_distribute(self, strategy: str | None = None):
        """
        Senaryo-kurallı dağıtım:

        strategy:
            balanced     : Dengeli (genel kullanım)
            intense      : Yoğun / derece modu (daha agresif)
            light        : Hafif / yeni başlayan
            weekend      : Hafta sonu ağırlıklı
            exam         : Deneme günü odaklı
            block_dense  : Yoğun blok günler
            block_course : Ders blokları
        """
        if self.optMan.isChecked():
            QMessageBox.information(
                self, "Otomatik Dağıt",
                "Manuel mod açıkken otomatik dağıtma kullanılamaz."
            )
            return

        if strategy is None:
            strategy = getattr(self, "_auto_strategy", "balanced")
        self._auto_strategy = strategy

        prof = self._active_profile()
        base_hedef = self.spGunluk.value()
        base_tol = self.spTol.value()
        base_cap = prof["max_tasks"]
        allow_back_to_back = prof["allow_back_to_back"]
        weekend_prefer = prof["weekend_prefer"]

        # --------  BLOK MODLARI ÖNCE --------
        if strategy == "block_dense":
            self._distribute_block_dense(base_hedef, base_tol, base_cap)
            label = "Blok dağıt (yoğun günler)"
            if hasattr(self, "lblLastStrategy"):
                self.lblLastStrategy.setText(f"Son strateji: {label}")
            return

        if strategy == "block_course":
            self._distribute_block_by_course(base_hedef, base_tol, base_cap)
            label = "Blok dağıt (ders blokları)"
            if hasattr(self, "lblLastStrategy"):
                self.lblLastStrategy.setText(f"Son strateji: {label}")
            return

        # --------  YOĞUN / HAFİF / HAFTA SONU / DENEME AYARLARI --------
        
        hedef = base_hedef
        tol = base_tol
        cap = base_cap
        weekend_bias = 0.0

        # Strateji bazlı ayarlamalar (önce bunu yapıyoruz)
        if strategy == "balanced":
            weekend_bias = 0.3 if weekend_prefer else 0.0

        elif strategy == "intense":
            # Çok çalışan, kütüphane öğrencisi:
            hedef = int(base_hedef * 1.1)  # hedefi %10 yukarı çek
            tol = int(base_tol * 1.7)  # daha geniş tolerans
            cap = min(base_cap + 2, 12)  # gün başına daha çok ödev
            weekend_bias = 0.2  # hafta sonuna hafif kaydırma

        elif strategy == "light":
            # Yeni başlayan, çabuk yorulan:
            hedef = int(base_hedef * 0.7)  # hedefi düşür
            tol = max(5, int(base_tol * 0.5))  # daha dar tolerans
            cap = max(1, base_cap - 1)  # daha az ödev
            weekend_bias = 0.0

        elif strategy == "weekend":
            weekend_bias = 0.9  # hafta sonu çok avantajlı

        elif strategy == "clear":
             # Temizle modu
             self._clear_all_marks()
             self._update_load_visuals()
             if hasattr(self, "lblLastStrategy"):
                 self.lblLastStrategy.setText("Son işlem: Temizle")
             return

        elif strategy == "exam":
            tol = int(base_tol * 1.2)  # deneme günleri için biraz esnek
            weekend_bias = 0.0  # nötr

        # Şimdi yoğunluk çarpanını uygula (HER STRATEJİ İÇİN GEÇERLİ OLSUN)
        # Density density logic applied AFTER strategy adjustments
        density = self.sliderDensity.value() / 100.0
        hedef = int(hedef * density)
        # Cap'i de ölçekle ama minimum 1
        cap = max(1, int(cap * density))

        # --------  ORTAK DAĞITIM ALGORİTMASI --------
        self._clear_all_marks()

        last_data_row = self.tbl.rowCount() - 1
        if last_data_row <= 0:
            return

        gun_dk = [0] * 7
        gun_adet = [0] * 7
        gun_adi = [
            self.tbl.horizontalHeaderItem(i).text().split("\n")[0]
            if self.tbl.horizontalHeaderItem(i) else TR_GUNLER[i - 1]
            for i in range(1, 8)
        ]
        last_ders_for_gun = [None] * 7

        weekend_idx = {
            i for i, name in enumerate(gun_adi)
            if name in ("Cumartesi", "Pazar")
        }

        # exam modu için deneme satırlarını ayıralım
        exam_rows = set()
        if strategy == "exam":
            for r in range(last_data_row):
                t = self.tbl.item(r, 0).text().lower() if self.tbl.item(r, 0) else ""
                if "deneme" in t or "trial" in t:
                    exam_rows.add(r)

        # satırları, süre büyük olandan küçüğe sırala (büyük işler önce)
        row_order = list(range(last_data_row))

        def row_dk(r):
            it_src = self.items[r] if r < len(self.items) else {}
            return int(it_src.get("dk", 0) or 0)

        row_order.sort(key=row_dk, reverse=True)

        # Karıştır modu aktifse rastgelelik ekle (ama uzun dersler yine de öncelikli kalabilir, ya da tamamen rastgele)
        # Mevcut yapı: Uzun dersler önce dağıtılıyor.
        # Eğer karıştır işaretliyse, aynı uzunluktaki derslerin sırasını değiştirmek için shuffle
        # veya tamamen shuffle yapıp "best fit" algoritmasına güvenebiliriz.
        if self.chkShuffle.isChecked():
            import random
            random.shuffle(row_order)
            # Shuffle sonrası tekrar süreye göre sıralamak shuffle etkisini bozar.
            # Ancak "büyük taşları önce koymak" algoritma başarısı için önemlidir.
            # O yüzden: Biraz "gürültü" ekleyip sıralayalım.
            # Row'lara rastgele +/- %20 sahte süre ekleyip ona göre sıralayalım?
            # Ya da: Direkt shuffle yapalım, algoritma yine de en uygun günü bulmaya çalışır.
            # Kullanıcı "Karıştır" dediyse farklı kombinasyon istiyordur.
            pass 

        for r in row_order:
            it_src = self.items[r] if r < len(self.items) else {}
            ders = it_src.get("ders", "")
            dk = int(it_src.get("dk", 0) or 0)

            best_c, best_score = None, 10 ** 9

            for c in range(7):
                # max ödev sınırı
                if gun_adet[c] >= cap:
                    continue

                # ardışık aynı ders kuralı
                if (not allow_back_to_back) and last_ders_for_gun[c] == ders:
                    continue

                new_total = gun_dk[c] + dk

                # temel farklar
                base_diff = abs(new_total - hedef)
                overflow = max(0, new_total - (hedef + tol))
                underflow = max(0, hedef - new_total)

                # stratejiye göre ceza/ödül
                if strategy == "intense":
                    penalty = overflow * 1.5 + underflow * 0.2
                    day_bias = gun_dk[c] * 0.02
                elif strategy == "light":
                    penalty = overflow * 4.0 + underflow * 1.0
                    day_bias = gun_dk[c] * 0.10
                else:  # balanced / weekend / exam
                    penalty = overflow * 3.0 + underflow * 0.5
                    day_bias = gun_dk[c] * 0.05

                score = base_diff + penalty + day_bias

                # hafta sonu avantaj / dezavantaj
                if weekend_bias > 0:
                    if c in weekend_idx:
                        score *= (1.0 - weekend_bias * 0.5)  # avantaj
                    else:
                        score *= (1.0 + weekend_bias * 0.3)  # dezavantaj

                # deneme modu özel
                if strategy == "exam":
                    if r in exam_rows:
                        # denemeyi Salı–Cuma aralığına çek
                        if 1 <= c <= 4:
                            score *= 0.6
                        else:
                            score *= 1.4
                    else:
                        # deneme olmayanları, deneme ile aynı güne fazla yığma
                        # (şimdilik basit: ağır günleri dezavantajlı yapıyoruz)
                        if gun_dk[c] > hedef + tol:
                            score *= 1.2

                if score < best_score:
                    best_score, best_c = score, c

            if best_c is None:
                # hiçbiri kurallara uymuyorsa en az ödevli günü seç
                best_c = min(range(7), key=lambda i: gun_adet[i])

            if dk <= 0:
                dk = 45
            self._mark_cell(r, best_c + 1, dk)
            gun_dk[best_c] += dk
            gun_adet[best_c] += 1
            last_ders_for_gun[best_c] = ders

        # Visual update (Heatmap)
        self._update_load_visuals()

        label_map = {
            "balanced": "Dengeli dağıt (önerilen)",
            "intense": "Yoğun / Derece modu",
            "light": "Hafif / Yeni başlayan",
            "weekend": "Hafta sonu ağırlıklı",
            "exam": "Deneme günü odaklı",
        }
        label = label_map.get(strategy, strategy)
        if hasattr(self, "lblLastStrategy"):
            self.lblLastStrategy.setText(f"Son strateji: {label}")

    # ---------------- sonuç toplama ----------------

    def _collect_plan(self):
        day_names = gun_adlari(self.dtBasla.date())
        out = []
        last_row = self.tbl.rowCount() - 1
        for r in range(last_row):
            t = self.tbl.item(r, 0).text() if self.tbl.item(r, 0) else ""
            ders, kitap, konu = (t.split("\n") + ["", "", ""])[:3]
            days = [
                c - 1
                for c in range(1, 8)
                if (self.tbl.item(r, c).text() or "").strip()
            ]
            if days:
                aciklama = " - ".join(day_names[i] for i in days)
                out.append(
                    {
                        "ders": ders,
                        "kitap": kitap,
                        "konu": konu,
                        "days": days,
                        "aciklama": aciklama,
                    }
                )
        return out

    def _accept_with_result(self):
        self.verilen = self._collect_plan()
        if not self.verilen:
            QMessageBox.information(self, "Plan", "Herhangi bir gün işaretlenmedi.")
            return
        try:
            self._cache_save_last_items(self.items)
        except Exception:
            pass
        self.accept()

    # ---------------- Yazdırma / PDF ----------------

    def _print_preview(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        printer.setFullPage(False)

        dlg = QPrintPreviewDialog(printer, self)
        dlg.setWindowTitle("Önizleme / Yazdır")
        dlg.paintRequested.connect(self._do_print)
        dlg.exec()

    def _do_print(self, printer: QPrinter):
        p = QPainter()
        if not p.begin(printer):
            return

        try:
            page_rect = printer.pageLayout().paintRectPixels(printer.resolution())
            is_portrait = printer.pageLayout().orientation() == QPageLayout.Orientation.Portrait

            ML, MT, MR, MB = 54, 46, 54, 60
            MAX_W = page_rect.width() - (ML + MR)
            MAX_H = page_rect.height() - (MT + MB)

            def draw_page_header():
                from PyQt6.QtGui import QPixmap
                from utils import settings as appset

                x_l = page_rect.left() + ML
                y_t = page_rect.top() + MT
                W = MAX_W
                RIGHT_INSET = 20

                try:
                    kurum = (appset.ayar_get('kurum_adi', '') or '').strip()
                    kocu = (appset.ayar_get('egitim_kocu', '') or '').strip()
                    iletisim = (appset.ayar_get('iletisim_satiri', '') or '').strip()
                    web = (appset.ayar_get('kurum_web', '') or '').strip()
                    logo_path = (appset.ayar_get('logo_path', '') or '').strip()
                    logo_align = (appset.ayar_get('logo_align', 'left') or 'left').lower()
                except Exception:
                    kurum = kocu = iletisim = web = logo_path = ''
                    logo_align = 'left'

                ogrenci = f"{(self.ogr_ad or '').strip()} {(self.ogr_soyad or '').strip()}".strip()
                verilis = self.verilis.toString('dd.MM.yyyy')
                bitis = self.bitis.toString('dd.MM.yyyy')

                f_title = QFont(p.font())
                f_title.setPointSize(16)
                f_title.setBold(True)
                f_sub = QFont(p.font())
                f_sub.setPointSize(10)
                f_meta = QFont(p.font())
                f_meta.setPointSize(10)

                logo_w = logo_h = 0
                if logo_path:
                    try:
                        pm = QPixmap(logo_path)
                        if not pm.isNull():
                            title_probe = QFont(p.font())
                            title_probe.setPointSize(16)
                            title_probe.setBold(True)
                            th_probe = QFontMetrics(title_probe).height()
                            desired_h = max(th_probe * 1.8, 38 if is_portrait else 52)
                            pm = pm.scaledToHeight(int(desired_h), Qt.TransformationMode.SmoothTransformation)

                            if logo_align == 'center':
                                px = x_l + (W - pm.width()) // 2
                            elif logo_align == 'right':
                                px = x_l + W - pm.width()
                            else:
                                px = x_l
                            p.drawPixmap(px, y_t, pm)
                            logo_w, logo_h = pm.width(), pm.height()
                    except Exception:
                        pass

                left_x = x_l + (logo_w + 8 if logo_w and logo_align == 'left' else 0)
                left_w = int(W * 0.62)
                right_x = left_x + left_w

                right_edge_limit = x_l + W - RIGHT_INSET
                if logo_w and logo_align == 'right':
                    right_edge_limit = min(right_edge_limit, x_l + W - logo_w - 10)

                right_w = max(140, right_edge_limit - right_x)
                if right_w < 140:
                    shrink = 140 - right_w
                    left_w = max(200, left_w - shrink)
                    right_x = left_x + left_w
                    right_w = max(140, right_edge_limit - right_x)

                cur_y = y_t
                p.setFont(f_title)
                th = p.fontMetrics().height()
                p.drawText(left_x, cur_y, left_w, th,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           "Haftalık Çalışma Planı")
                cur_y += th + 4

                if kurum:
                    p.setFont(f_sub)
                    kh = p.fontMetrics().height()
                    p.drawText(left_x, cur_y, left_w, kh,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, kurum)
                    cur_y += kh + 2

                p.setFont(f_sub)
                sh = p.fontMetrics().height()
                p.drawText(left_x, cur_y, left_w, sh,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           f"Öğrenci: {ogrenci if ogrenci else '-'}")
                cur_y += sh + 2

                kocu_text = kocu if kocu else "-"
                p.drawText(left_x, cur_y, left_w, sh,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           f"Eğitim Koçu: {kocu_text}")
                cur_y += sh + 2

                if iletisim or web:
                    p.drawText(left_x, cur_y, left_w, sh,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               " / ".join(t for t in (iletisim, web) if t))
                    cur_y += sh + 2

                left_bottom = max(cur_y, y_t + (logo_h if logo_align == 'left' else 0))

                p.setFont(f_meta)
                mh = p.fontMetrics().height()
                p.drawText(right_x, y_t, right_w, mh,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           f"Veriliş: {verilis}    Bitiş: {bitis}")

                return max(left_bottom, y_t + mh) + 16

            def draw_table_header(y, cell_w):
                headers = ["Ödev"] + [
                    (self.tbl.horizontalHeaderItem(c).text()
                     if self.tbl.horizontalHeaderItem(c) else "")
                    for c in range(1, 8)
                ]
                base_pt = 10 if not is_portrait else 9
                f_head = QFont(p.font())
                f_head.setPointSize(base_pt)
                f_head.setBold(True)
                p.setFont(f_head)
                fm_head = QFontMetrics(f_head)
                #head_h = max(fm_head.height() + 12, 32)
                head_h = max(int(fm_head.height() * 1.9), 34)

                x0 = page_rect.left() + ML
                p.drawRect(x0, y, cell_w * 8, head_h)
                for c, txt in enumerate(headers):
                    p.drawRect(x0 + c * cell_w, y, cell_w, head_h)
                    p.drawText(x0 + c * cell_w + 4, y, cell_w - 8, head_h,
                               Qt.AlignmentFlag.AlignCenter, txt)
                return y + head_h

            base_pt = 10 if not is_portrait else 9
            f_cell = QFont(p.font())
            f_cell.setPointSize(base_pt)
            f_bold = QFont(f_cell)
            f_bold.setBold(True)
            f_mark = QFont(f_cell)
            f_mark.setPointSize(base_pt + 1)
            f_mark.setBold(True)
            fm_bold = QFontMetrics(f_bold)
            fm_cell = QFontMetrics(f_cell)
            PAD = 6 if is_portrait else 8
            GAP = 4 if is_portrait else 6
            WRAP_ALIGN = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap

            def fit_height(text: str, font: QFont, w: int, max_px: int) -> tuple[int, QFont]:
                if not text:
                    return 0, font
                f = QFont(font)
                for _ in range(6):
                    fm = QFontMetrics(f)
                    h = fm.boundingRect(0, 0, w, 100000, WRAP_ALIGN, text).height()
                    if h <= max_px or f.pointSize() <= 7:
                        return h, f
                    f.setPointSize(f.pointSize() - 1)
                return h, f

            y = draw_page_header()
            COLS = 8
            cell_w = int(MAX_W / COLS)
            y = draw_table_header(y, cell_w)

            rows_data = len(self.items)
            rows_total = rows_data + 1
            cap_each = 58 if is_portrait else 76
            min_row = max(34, fm_cell.height() * 2 + 10)
            w_in = cell_w - 16

            row_heights = []
            line_fonts = []
            for r in range(rows_total):
                if r < rows_data:
                    it = self.items[r]
                    ders = it.get("ders", "")
                    kitap = it.get("kitap", "")
                    konu = it.get("konu", "")
                    h1 = fm_bold.height()
                    h2, f2 = fit_height(kitap, f_cell, w_in, cap_each)
                    h3, f3 = fit_height(konu, f_cell, w_in, cap_each)
                    total = PAD + h1 + (GAP + h2 if h2 else 0) + (GAP + h3 if h3 else 0) + PAD
                    row_heights.append(max(min_row, total))
                    line_fonts.append((f_bold, f2, f3))
                else:
                    f_footer_lbl = QFont(f_cell)
                    f_footer_lbl.setPointSize(base_pt - 1)
                    row_heights.append(min_row)
                    line_fonts.append((f_footer_lbl, f_cell, f_cell))

            x0 = page_rect.left() + ML
            bottom_limit = page_rect.top() + MT + MAX_H

            for r in range(rows_total):
                ch = row_heights[r]
                if (y + ch) > bottom_limit:
                    printer.newPage()
                    y = draw_page_header()
                    y = draw_table_header(y, cell_w)

                p.drawRect(x0, y, cell_w * COLS, ch)

                p.drawRect(x0, y, cell_w, ch)
                p.save()
                p.setClipRect(x0 + 1, y + 1, cell_w - 2, ch - 2)

                if r < rows_data:
                    it = self.items[r]
                    ders = it.get("ders", "")
                    kitap = it.get("kitap", "")
                    konu = it.get("konu", "")
                    f_ders, f_kitap, f_konu = line_fonts[r]
                    p.setFont(f_ders)
                    fm = QFontMetrics(f_ders)
                    h1 = fm.height()
                    p.drawText(x0 + 8, y + PAD, w_in, h1,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, ders)
                    cur_y = y + PAD + h1
                    if kitap:
                        p.setFont(f_kitap)
                        fm = QFontMetrics(f_kitap)
                        h2 = fm.boundingRect(0, 0, w_in, 100000, WRAP_ALIGN, kitap).height()
                        p.drawText(x0 + 8, cur_y + GAP, w_in, h2, WRAP_ALIGN, kitap)
                        cur_y += GAP + h2
                    if konu:
                        p.setFont(f_konu)
                        fm = QFontMetrics(f_konu)
                        h3 = fm.boundingRect(0, 0, w_in, 100000, WRAP_ALIGN, konu).height()
                        p.drawText(x0 + 8, cur_y + GAP, w_in, h3, WRAP_ALIGN, konu)
                else:
                    f_footer_lbl, _, _ = line_fonts[r]
                    p.setFont(f_footer_lbl)
                    fm = QFontMetrics(f_footer_lbl)
                    lh = fm.height()
                    p.drawText(x0 + 8, y + (ch - 2 * lh) // 2, w_in, lh,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               "Günlük hedef")
                    p.drawText(x0 + 8, y + (ch - 2 * lh) // 2 + lh, w_in, lh,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               "çalışma süresi:")

                p.restore()

                for c in range(1, COLS):
                    p.drawRect(x0 + c * cell_w, y, cell_w, ch)
                    txt = ""
                    if r < rows_data:
                        cell = self.tbl.item(r, c)
                        txt = (cell.text() if cell else "")
                    elif r == rows_data and 1 <= c <= 7:
                        txt = self.footer_line.text()
                    if txt:
                        p.save()
                        p.setFont(f_mark)
                        p.drawText(x0 + c * cell_w, y, cell_w, ch,
                                   Qt.AlignmentFlag.AlignCenter, txt)
                        p.restore()

                y += ch

            # -------- Plan Özeti (isteğe bağlı) --------
            if getattr(self, "chkIncludeSummary", None) and self.chkIncludeSummary.isChecked():
                day_names = gun_adlari(self.dtBasla.date())
                hedef = self.spGunluk.value()
                tol = self.spTol.value()

                totals = [0] * 7
                counts = [0] * 7
                last_data_row = min(len(self.items), self.tbl.rowCount() - 1)

                for r in range(last_data_row):
                    dk = int(self.items[r].get("dk", 0) or 0)
                    if dk <= 0:
                        continue
                    for c in range(7):
                        cell = self.tbl.item(r, c + 1)
                        if cell and (cell.text() or "").strip():
                            totals[c] += dk
                            counts[c] += 1

                weekly_total = sum(totals)
                avg = weekly_total / 7.0 if 7 else 0.0

                # Yeterli yer yoksa yeni sayfa aç
                f_sum = QFont(p.font())
                f_sum.setPointSize(10)
                fm_sum = QFontMetrics(f_sum)
                header_h = fm_sum.height() + 10
                row_h = fm_sum.height() + 8
                footer_h = fm_sum.height() + 10
                needed = header_h + len(day_names) * row_h + footer_h + 20

                if y + needed > bottom_limit:
                    printer.newPage()
                    y = draw_page_header()

                x0 = page_rect.left() + ML
                table_w = MAX_W

                # Başlık
                p.setFont(f_sum)
                p.drawText(x0, y, table_w, header_h,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           "Plan Özeti (Günlük Toplamlar)")
                y += header_h

                # Kolon genişlikleri
                col_titles = ["Gün", "Toplam dk", "Ödev sayısı", "Durum"]
                col_w = [
                    int(table_w * 0.18),
                    int(table_w * 0.16),
                    int(table_w * 0.16),
                    table_w - int(table_w * 0.18) - int(table_w * 0.16) - int(table_w * 0.16),
                ]

                # Header satırı
                p.drawRect(x0, y, table_w, row_h)
                cx = x0
                for t, cw in zip(col_titles, col_w):
                    p.drawRect(cx, y, cw, row_h)
                    p.drawText(cx + 4, y, cw - 8, row_h,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t)
                    cx += cw
                y += row_h

                # Satırlar
                f_row = QFont(p.font())
                f_row.setPointSize(9)
                p.setFont(f_row)
                fm_row = QFontMetrics(f_row)
                row_h = fm_row.height() + 6

                for i, name in enumerate(day_names):
                    toplam = totals[i]
                    adet = counts[i]
                    if toplam == 0 and adet == 0:
                        durum = "-"
                    else:
                        if toplam < hedef - tol:
                            durum = f"{hedef - toplam} dk eksik"
                        elif toplam > hedef + tol:
                            durum = f"{toplam - hedef} dk fazla"
                        else:
                            durum = "Hedefe yakın"

                    p.drawRect(x0, y, table_w, row_h)
                    cx = x0
                    vals = [name, f"{toplam} dk", str(adet), durum]
                    for v, cw in zip(vals, col_w):
                        p.drawRect(cx, y, cw, row_h)
                        p.drawText(cx + 4, y, cw - 8, row_h,
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, v)
                        cx += cw
                    y += row_h

                # Alt satır – genel özet
                txt = (f"Günlük hedef: {hedef} dk, tolerans: ±{tol} dk, "
                       f"haftalık toplam: {weekly_total} dk, günlük ortalama: {avg:.1f} dk")
                y += 4
                p.drawText(x0, y, table_w, row_h,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)

        finally:
            p.end()


# -------------- OdevTakipFormu için yardımcı --------------

def items_from_verilen_table(tbl) -> list[dict]:
    """
    OdevTakipFormu'ndaki 'verilen' QTableWidget'ından items listesi üretir.
    Beklenen kolon dizilimi: 0=Ders, 1=Kitap, 2=Konu, 3=Süre(dk)
    """
    items = []
    if tbl is None:
        return items
    for r in range(tbl.rowCount()):
        ders = (tbl.item(r, 0).text() if tbl.item(r, 0) else "").strip()
        kitap = (tbl.item(r, 1).text() if tbl.item(r, 1) else "").strip()
        konu = (tbl.item(r, 2).text() if tbl.item(r, 2) else "").strip()
        try:
            dk = int((tbl.item(r, 3).text() if tbl.item(r, 3) else "0").strip() or "0")
        except Exception:
            dk = 0
        if dk <= 0:
            dk = 45
        if ders or kitap or konu:
            items.append({"ders": ders, "kitap": kitap, "konu": konu, "dk": dk})
    return items