# -*- coding: utf-8 -*-
"""
app_settings.py — Compact & Responsive Ayarlar
- Tema, PDF, WhatsApp aynı
- Motivasyon ayarları ayrı dialogdan açılır (buton)
- PyQt6 / Python 3.9 uyumlu
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QMessageBox, QGroupBox, QGridLayout, QRadioButton,
    QSpinBox, QApplication, QDialog, QDialogButtonBox, QColorDialog, QCheckBox,
    QScrollArea, QInputDialog, QTabWidget, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ui.responsive import apply_responsive
from utils import settings as appset
import importlib
import json

# ---- motivation_toast ile DOĞRUDAN ENTEGRASYON ----
try:
    from ui.motivation_toast import (
        load_settings as mot_load,
        save_settings as mot_save,
        preview_settings as mot_preview,
    )
except Exception:
    mot_load = mot_save = mot_preview = None


# ---------------- Lazy theme API ----------------
def _theme_api():
    try:
        theme = importlib.import_module('ui.theme')
        return theme.tema_presets, theme.tema_apply_preset, theme.apply
    except Exception:
        return (lambda: {"Klasik Koyu": {"mode": "dark"}}), (lambda _name: None), (lambda _app: None)


# ---------------- Fallback mini toast ----------------
def _fallback_toast(parent, text, color="#22c55e", ms=1800, font=18):
    from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect
    from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve

    w = QFrame(parent)
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    w.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
    w.setStyleSheet(
        "QFrame{background:%s;border-radius:14px;padding:8px 14px;}"
        "QLabel{color:white;font-weight:600;}" % color
    )
    lay = QHBoxLayout(w)
    lay.setContentsMargins(12, 8, 12, 8)
    lbl = QLabel(text)
    f = lbl.font()
    f.setPointSize(font)
    lbl.setFont(f)
    lay.addWidget(lbl)
    w.adjustSize()

    geo = parent.window().geometry()
    w.move(geo.center().x() - w.width() // 2, geo.center().y() - w.height() // 2)
    w.show()

    # GC koruması
    w._eff = QGraphicsOpacityEffect(w)
    w.setGraphicsEffect(w._eff)

    w._a1 = QPropertyAnimation(w._eff, b"opacity", w)
    w._a1.setDuration(220)
    w._a1.setStartValue(0)
    w._a1.setEndValue(1)
    w._a1.setEasingCurve(QEasingCurve.Type.OutCubic)
    w._a1.start()

    from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect
    from PyQt6.QtCore import QPropertyAnimation, QEasingCurve

    def _fade(self, w: QWidget, start: float, end: float, dur: int = 300):
        # --- Güvenlik: widget silinmişse / görünür değilse sessiz çık ---
        if w is None or not isinstance(w, QWidget):
            return
        try:
            _ = w.isVisible()
        except RuntimeError:
            return

        eff = getattr(w, "_eff", None)
        if eff is None:
            try:
                eff = QGraphicsOpacityEffect(w)
                w.setGraphicsEffect(eff)
                w._eff = eff
            except RuntimeError:
                return

        try:
            anim = QPropertyAnimation(eff, b"opacity", w)
            anim.setDuration(int(dur))
            anim.setStartValue(float(start))
            anim.setEndValue(float(end))
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        except RuntimeError:
            return

    QTimer.singleShot(ms, _fade)


# ---------------- Görünüm Ayarları Dialog ----------------
class GorunumAyarDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Görünüm Ayarları")
        self.resize(520, 320)
        self._tema_presets, self._tema_apply_preset, self._apply_theme = _theme_api()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        gbox = QGroupBox("Tema Seti ve Görünüm")
        g = QGridLayout(gbox)
        g.setContentsMargins(12, 10, 12, 10)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)

        self.cmbTemaSeti = QComboBox()
        try:
            self.cmbTemaSeti.addItems(list(self._tema_presets().keys()))
        except Exception:
            self.cmbTemaSeti.addItems(["Klasik Koyu"])
        self.cmbTemaSeti.setCurrentText(str(appset.ayar_get('tema_seti', 'Klasik Koyu')))

        self.spinFont = QSpinBox()
        self.spinFont.setRange(9, 22)
        self.spinFont.setValue(int(appset.ayar_get('tema_font', '12') or 12))

        self.cmbDensity = QComboBox()
        self.cmbDensity.addItems(["compact", "cozy", "comfortable"])
        self.cmbDensity.setCurrentText(str(appset.ayar_get('tema_density', 'compact')))

        self.spinRadius = QSpinBox()
        self.spinRadius.setRange(0, 20)
        self.spinRadius.setValue(int(appset.ayar_get('tema_radius', '6') or 6))

        r = 0
        g.addWidget(QLabel("Hazır Tema"), r, 0)
        g.addWidget(self.cmbTemaSeti, r, 1)
        r += 1
        g.addWidget(QLabel("Yazı Boyutu"), r, 0)
        g.addWidget(self.spinFont, r, 1)
        r += 1
        g.addWidget(QLabel("Yoğunluk"), r, 0)
        g.addWidget(self.cmbDensity, r, 1)
        r += 1
        g.addWidget(QLabel("Köşe Yuvarlaklığı"), r, 0)
        g.addWidget(self.spinRadius, r, 1)
        r += 1
        lay.addWidget(gbox)

        btns = QDialogButtonBox()
        self.btnApply = btns.addButton("Uygula", QDialogButtonBox.ButtonRole.ApplyRole)
        self.btnSave = btns.addButton("Kaydet", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btnClose = btns.addButton("Kapat", QDialogButtonBox.ButtonRole.RejectRole)
        lay.addWidget(btns)

        def _apply_live():
            try:
                self._tema_apply_preset(self.cmbTemaSeti.currentText())
                appset.ayar_set('tema_font', str(self.spinFont.value()))
                appset.ayar_set('tema_density', self.cmbDensity.currentText())
                appset.ayar_set('tema_radius', str(self.spinRadius.value()))
                self._apply_theme(QApplication.instance())
            except Exception:
                pass

        self.cmbTemaSeti.currentIndexChanged.connect(_apply_live)
        self.spinFont.valueChanged.connect(lambda *_: _apply_live())
        self.cmbDensity.currentIndexChanged.connect(_apply_live)
        self.spinRadius.valueChanged.connect(_apply_live)
        self.btnApply.clicked.connect(_apply_live)
        self.btnSave.clicked.connect(
            lambda: (appset.ayar_set('tema_seti', self.cmbTemaSeti.currentText()), self.accept())
        )
        self.btnClose.clicked.connect(self.reject)


# ---------------- TEMA YÖNETİCİSİ (PRO) ----------------
class ThemeManagerDialog(QDialog):
    """
    Profesyonel tema yöneticisi:
    - Hazır preset'ten başla
    - Tüm önemli renk + görünüm ayarlarını düzenle
    - Özel tema olarak kaydet / güncelle / sil
    - Anında uygulama
    """
    COLOR_KEYS = [
        ("tema_primary",        "Ana Renk (primary)",          "#2d89ef"),
        ("tema_accent",         "Vurgu Rengi (accent)",        "#21ba45"),
        ("tema_bg",             "Arka Plan (Uygulama)",        "#1b1c1d"),

        ("tema_card",           "Kart Arka Planı",             "#2A2C31"),
        ("tema_alt",            "Alt Panel Arka Planı",        "#33363C"),

        ("tema_list_bg",        "Liste Arka Planı",            "#FFFFFF"),
        ("tema_list_alt",       "Liste Alternatif Satır",      "#F4F7FB"),
        ("tema_list_fg",        "Liste Yazı Rengi",            "#111315"),
        ("tema_list_grid",      "Liste Izgara Çizgisi",        "#D9DEE5"),
        ("tema_list_hover_bg",  "Liste Hover Arka Plan",       "#E6F0FF"),
        ("tema_list_hover_fg",  "Liste Hover Yazı Rengi",      "#0F1113"),

        ("tema_head_bg",        "Liste Başlığı Arka Plan",     "#FFFFFF"),
        ("tema_head_fg",        "Liste Başlığı Yazı Rengi",    "#2B2F33"),

        ("tema_tab_bg",         "Sekme Arka Planı",            "#E5E7EB"),
        ("tema_tab_fg",         "Sekme Yazı Rengi",            "#111827"),
        ("tema_tab_sel_bg",     "Aktif Sekme Arka Planı",      "#FFFFFF"),
        ("tema_tab_sel_fg",     "Aktif Sekme Yazı Rengi",      "#111827"),
        ("tema_tab_hover_bg",   "Sekme Hover Arka Planı",      "#E0ECFF"),

        ("tema_button_bg",      "Ana Buton Arka Planı",        "#2d89ef"),
        ("tema_button_fg",      "Ana Buton Yazı Rengi",        "#ffffff"),
        ("tema_button_border",  "Ana Buton Çerçeve Rengi",     "#2d89ef"),

        ("tema_danger",         "Danger (Kırmızı)",            "#D32F2F"),
        ("tema_warn",           "Uyarı (Turuncu)",             "#F6A721"),
        ("tema_ok",             "Başarılı (Yeşil)",            "#16A34A"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tema Yöneticisi")
        # Biraz daha düşük yükseklik, ama asıl çözüm scroll
        self.resize(820, 520)

        self._tema_presets, self._tema_apply_preset, self._apply_theme = _theme_api()
        self._color_fields = {}
        self._custom_themes = self._load_customs()

        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        # Mevcut moda göre koyu/açık karar ver
        tema_mod = (appset.ayar_get("tema_mod", appset.ayar_get("tema", "koyu")) or "koyu").lower()
        is_dark = tema_mod not in ("açık", "acik", "light")

        dynamic_defaults = {
            "tema_card": "#2A2C31" if is_dark else "#F6F7F9",
            "tema_alt":  "#33363C" if is_dark else "#EEF0F3",
            "tema_list_hover_bg": "#E6F0FF",
            "tema_list_hover_fg": "#0F1113",
            "tema_tab_bg": "#E5E7EB",
            "tema_tab_fg": "#111827",
            "tema_tab_sel_bg": "#FFFFFF",
            "tema_tab_sel_fg": "#111827",
            "tema_tab_hover_bg": "#E0ECFF",
        }

        # ----- Üst satır: preset seçimi -----
        top = QHBoxLayout()
        top.addWidget(QLabel("Hazır Tema Preseti:"))
        self.cmbPreset = QComboBox()
        try:
            self.cmbPreset.addItems(list(self._tema_presets().keys()))
        except Exception:
            self.cmbPreset.addItems(["Klasik Koyu"])
        self.cmbPreset.setCurrentText(str(appset.ayar_get("tema_seti", "Klasik Koyu")))
        btnPresetYukle = QPushButton("Preseti Yükle")
        btnPresetYukle.clicked.connect(self._preset_yukle)
        top.addWidget(self.cmbPreset)
        top.addWidget(btnPresetYukle)
        top.addStretch(1)
        main.addLayout(top)

        # ----- Orta kısım: 3 kolon (Renkler / Parametreler / Özel temalar) -----
        body = QHBoxLayout()
        body.setSpacing(10)
        main.addLayout(body, 1)

        # ===== SOL: Renkler (SCROLL'LU) =====
        gb_colors = QGroupBox("Renkler")
        grid_c = QGridLayout(gb_colors)
        grid_c.setContentsMargins(10, 8, 10, 8)
        grid_c.setHorizontalSpacing(8)
        grid_c.setVerticalSpacing(6)

        def add_color_row(row, key, label_text, default_from_list):
            default = dynamic_defaults.get(key, default_from_list)
            lbl = QLabel(label_text)
            line = QLineEdit(str(appset.ayar_get(key, default) or default))
            btn = QPushButton("…")
            btn.setFixedWidth(28)

            def pick():
                c = QColorDialog.getColor(QColor(line.text() or default), self, label_text)
                if c.isValid():
                    line.setText(c.name())

            btn.clicked.connect(pick)
            grid_c.addWidget(lbl, row, 0)
            grid_c.addWidget(line, row, 1)
            grid_c.addWidget(btn, row, 2)
            self._color_fields[key] = line

        r = 0
        for key, text, default in self.COLOR_KEYS:
            add_color_row(r, key, text, default)
            r += 1

        # Renk groupbox'ını scroll içine al
        scroll_colors = QScrollArea()
        scroll_colors.setWidgetResizable(True)
        scroll_colors.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_colors.setWidget(gb_colors)

        body.addWidget(scroll_colors, 2)

        # ===== ORTA: Görünüm Parametreleri =====
        gb_look = QGroupBox("Görünüm Parametreleri")
        grid_l = QGridLayout(gb_look)
        grid_l.setContentsMargins(10, 8, 10, 8)
        grid_l.setHorizontalSpacing(8)
        grid_l.setVerticalSpacing(6)

        # Mod (açık / koyu)
        self.radLight = QRadioButton("Açık (light)")
        self.radDark = QRadioButton("Koyu (dark)")
        if is_dark:
            self.radDark.setChecked(True)
        else:
            self.radLight.setChecked(True)

        grid_l.addWidget(QLabel("Tema Modu"), 0, 0)
        hb_mod = QHBoxLayout()
        hb_mod.addWidget(self.radLight)
        hb_mod.addWidget(self.radDark)
        hb_mod.addStretch(1)
        w_mod = QWidget()
        w_mod.setLayout(hb_mod)
        grid_l.addWidget(w_mod, 0, 1, 1, 2)

        # Font
        self.spinFont = QSpinBox()
        self.spinFont.setRange(9, 26)
        self.spinFont.setValue(int(appset.ayar_get("tema_font", "12") or 12))
        grid_l.addWidget(QLabel("Yazı Boyutu"), 1, 0)
        grid_l.addWidget(self.spinFont, 1, 1, 1, 2)

        # Yoğunluk
        self.cmbDensity = QComboBox()
        self.cmbDensity.addItems(["compact", "cozy", "comfortable"])
        self.cmbDensity.setCurrentText(str(appset.ayar_get("tema_density", "cozy") or "cozy"))
        grid_l.addWidget(QLabel("Satır Yoğunluğu"), 2, 0)
        grid_l.addWidget(self.cmbDensity, 2, 1, 1, 2)

        # Köşe yuvarlaklığı
        self.spinRadius = QSpinBox()
        self.spinRadius.setRange(0, 20)
        self.spinRadius.setValue(int(appset.ayar_get("tema_radius", "6") or 6))
        grid_l.addWidget(QLabel("Köşe Yuvarlaklığı"), 3, 0)
        grid_l.addWidget(self.spinRadius, 3, 1, 1, 2)

        # Border stili
        self.cmbBorders = QComboBox()
        self.cmbBorders.addItems(["subtle", "normal", "bold"])
        self.cmbBorders.setCurrentText(str(appset.ayar_get("tema_borders", "normal") or "normal"))
        grid_l.addWidget(QLabel("Çerçeve Stili"), 4, 0)
        grid_l.addWidget(self.cmbBorders, 4, 1, 1, 2)

        # Scrollbar
        self.spinScroll = QSpinBox()
        self.spinScroll.setRange(6, 24)
        self.spinScroll.setValue(int(appset.ayar_get("tema_scrollbar", "12") or 12))
        grid_l.addWidget(QLabel("ScrollBar Genişliği"), 5, 0)
        grid_l.addWidget(self.spinScroll, 5, 1, 1, 2)

        # Araç çubuğu butonları: icon-only
        self.chkIconOnly = QCheckBox("Araç çubuğu butonlarını sadece simge göster (icon-only)")
        icon_only_raw = str(appset.ayar_get("tema_button_icon_only", "0")).lower()
        self.chkIconOnly.setChecked(icon_only_raw in ("1", "true", "yes", "on"))
        grid_l.addWidget(self.chkIconOnly, 6, 0, 1, 3)

        body.addWidget(gb_look, 1)

        # ===== SAĞ: Özel Temalar =====
        gb_custom = QGroupBox("Özel Temalar")
        grid_t = QGridLayout(gb_custom)
        grid_t.setContentsMargins(10, 8, 10, 8)
        grid_t.setHorizontalSpacing(8)
        grid_t.setVerticalSpacing(6)

        self.cmbCustom = QComboBox()
        self._reload_custom_combo()

        btnLoad = QPushButton("Seçili Temayı Yükle")
        btnNew = QPushButton("Yeni Tema Kaydet…")
        btnUpdate = QPushButton("Seçili Temayı Güncelle")
        btnDelete = QPushButton("Seçili Temayı Sil")

        btnLoad.clicked.connect(self._custom_load)
        btnNew.clicked.connect(self._custom_new)
        btnUpdate.clicked.connect(self._custom_update)
        btnDelete.clicked.connect(self._custom_delete)

        grid_t.addWidget(QLabel("Kayıtlı Özel Temalar"), 0, 0, 1, 2)
        grid_t.addWidget(self.cmbCustom, 1, 0, 1, 2)
        grid_t.addWidget(btnLoad,   2, 0, 1, 2)
        grid_t.addWidget(btnNew,    3, 0, 1, 2)
        grid_t.addWidget(btnUpdate, 4, 0, 1, 2)
        grid_t.addWidget(btnDelete, 5, 0, 1, 2)

        body.addWidget(gb_custom, 1)

        # ===== ALT: Butonlar (her zaman görünür) =====
        btns = QDialogButtonBox()
        self.btnApply = btns.addButton("Anında Uygula", QDialogButtonBox.ButtonRole.ApplyRole)
        self.btnSaveClose = btns.addButton("Kaydet ve Kapat", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btnClose = btns.addButton("İptal", QDialogButtonBox.ButtonRole.RejectRole)
        main.addWidget(btns)

        self.btnApply.clicked.connect(self._apply_live)
        self.btnSaveClose.clicked.connect(self._save_and_close)
        self.btnClose.clicked.connect(self.reject)

        # Küçük stil dokunuşu
        self.setStyleSheet("""
            QGroupBox {
                font-weight:600;
                border:1px solid #e2e8f0;
                border-radius:8px;
                margin-top:10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left:8px;
                padding:0 4px;
            }
            QLabel { color:#0f172a; }
            QLineEdit, QComboBox, QSpinBox { min-height: 24px; padding: 2px 6px; }
            QPushButton { min-height: 26px; padding: 4px 10px; }
        """)

    # ==== Custom tema load/save (aynı mantık) ====
    def _load_customs(self):
        raw = appset.ayar_get("tema_customs", "{}") or "{}"
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_customs(self):
        try:
            appset.ayar_set("tema_customs", json.dumps(self._custom_themes, ensure_ascii=False))
        except Exception:
            pass

    def _reload_custom_combo(self):
        self.cmbCustom.clear
        names = sorted(self._custom_themes.keys())
        if names:
            self.cmbCustom.addItems(names)

    def _preset_yukle(self):
        name = self.cmbPreset.currentText()
        presets = self._tema_presets()
        p = presets.get(name, {})
        if not p:
            return

        self._color_fields["tema_primary"].setText(p.get("primary", self._color_fields["tema_primary"].text()))
        self._color_fields["tema_accent"].setText(p.get("accent", self._color_fields["tema_accent"].text()))
        self._color_fields["tema_bg"].setText(p.get("bg", self._color_fields["tema_bg"].text()))

        mode = (p.get("mode") or "dark").lower()
        if mode in ("light", "açık", "acik"):
            self.radLight.setChecked(True)
        else:
            self.radDark.setChecked(True)

        is_dark_preset = (mode in ("dark", "koyu"))

        if is_dark_preset:
            self._color_fields["tema_list_bg"].setText("#1b1c1d")
            self._color_fields["tema_list_alt"].setText("#252628")
            self._color_fields["tema_list_fg"].setText("#EDEDED")
            self._color_fields["tema_list_grid"].setText("#383b40")
            self._color_fields["tema_head_bg"].setText("#2A2C31")
            self._color_fields["tema_head_fg"].setText("#EAF2FF")
        else:
            self._color_fields["tema_list_bg"].setText("#FFFFFF")
            self._color_fields["tema_list_alt"].setText("#F4F7FB")
            self._color_fields["tema_list_fg"].setText("#111315")
            self._color_fields["tema_list_grid"].setText("#D9DEE5")
            self._color_fields["tema_head_bg"].setText("#FFFFFF")
            self._color_fields["tema_head_fg"].setText("#2B2F33")

    def _collect_theme_dict(self):
        mode = "light" if self.radLight.isChecked() else "dark"

        data = {
            "mode": mode,
            "tema_font": int(self.spinFont.value()),
            "tema_density": self.cmbDensity.currentText(),
            "tema_radius": int(self.spinRadius.value()),
            "tema_borders": self.cmbBorders.currentText(),
            "tema_scrollbar": int(self.spinScroll.value()),
            "tema_button_icon_only": bool(self.chkIconOnly.isChecked()),
        }
        for key, _, default in self.COLOR_KEYS:
            val = self._color_fields.get(key).text().strip() or default
            data[key] = val
        return data

    def _apply_settings_to_appset(self):
        theme_dict = self._collect_theme_dict()
        mode = theme_dict.get("mode", "dark")

        appset.ayar_set("tema", "koyu" if mode == "dark" else "açık")
        appset.ayar_set("tema_mod", "koyu" if mode == "dark" else "açık")

        appset.ayar_set("tema_font", str(theme_dict["tema_font"]))
        appset.ayar_set("tema_density", theme_dict["tema_density"])
        appset.ayar_set("tema_radius", str(theme_dict["tema_radius"]))
        appset.ayar_set("tema_borders", theme_dict["tema_borders"])
        appset.ayar_set("tema_scrollbar", str(theme_dict["tema_scrollbar"]))
        appset.ayar_set(
            "tema_button_icon_only",
            "1" if theme_dict.get("tema_button_icon_only") else "0"
        )

        for key, _, _ in self.COLOR_KEYS:
            appset.ayar_set(key, theme_dict[key])

        try:
            self._apply_theme(QApplication.instance())
        except Exception:
            pass

    def _apply_live(self):
        self._apply_settings_to_appset()

    def _save_and_close(self):
        self._apply_settings_to_appset()
        self.accept()

    def _current_custom_name(self):
        return self.cmbCustom.currentText().strip() or None

    def _custom_load(self):
        name = self._current_custom_name()
        if not name or name not in self._custom_themes:
            return
        d = self._custom_themes[name]

        mode = (d.get("mode") or "dark").lower()
        if mode in ("light", "açık", "acik"):
            self.radLight.setChecked(True)
        else:
            self.radDark.setChecked(True)

        self.spinFont.setValue(int(d.get("tema_font", self.spinFont.value())))
        self.cmbDensity.setCurrentText(d.get("tema_density", self.cmbDensity.currentText()))
        self.spinRadius.setValue(int(d.get("tema_radius", self.spinRadius.value())))
        self.cmbBorders.setCurrentText(d.get("tema_borders", self.cmbBorders.currentText()))
        self.spinScroll.setValue(int(d.get("tema_scrollbar", self.spinScroll.value())))
        self.chkIconOnly.setChecked(bool(d.get("tema_button_icon_only", False)))

        for key, _, default in self.COLOR_KEYS:
            val = d.get(key, self._color_fields[key].text() or default)
            self._color_fields[key].setText(val)

        appset.ayar_set("tema_seti", name)
        self._apply_settings_to_appset()

    def _custom_new(self):
        name, ok = QInputDialog.getText(self, "Yeni Tema Kaydet", "Tema adı:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return

        if name in self._custom_themes:
            cevap = QMessageBox.question(
                self,
                "Üzerine Yazılsın mı?",
                f"'{name}' isimli tema zaten var.\nÜzerine yazmak ister misin?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if cevap != QMessageBox.StandardButton.Yes:
                return

        self._custom_themes[name] = self._collect_theme_dict()
        self._save_customs()
        self._reload_custom_combo()
        self.cmbCustom.setCurrentText(name)
        appset.ayar_set("tema_seti", name)
        self._apply_settings_to_appset()
        QMessageBox.information(self, "Tema", f"'{name}' teması kaydedildi.")

    def _custom_update(self):
        name = self._current_custom_name()
        if not name or name not in self._custom_themes:
            QMessageBox.warning(self, "Tema", "Güncellenecek özel tema seçili değil.")
            return
        self._custom_themes[name] = self._collect_theme_dict()
        self._save_customs()
        appset.ayar_set("tema_seti", name)
        self._apply_settings_to_appset()
        QMessageBox.information(self, "Tema", f"'{name}' teması güncellendi.")

    def _custom_delete(self):
        name = self._current_custom_name()
        if not name or name not in self._custom_themes:
            return
        cevap = QMessageBox.question(
            self,
            "Temayı Sil",
            f"'{name}' isimli temayı silmek istediğine emin misin?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return
        del self._custom_themes[name]
        self._save_customs()
        self._reload_custom_combo()
        QMessageBox.information(self, "Tema", f"'{name}' teması silindi.")




# ---------------- Motivasyon Ayarları Dialog (GÜNCEL) ----------------
class MotivationDialog(QDialog):
    """
    Bu dialog; ui/motivation_toast.load_settings/save_settings ile
    motive_* anahtarlarını doğrudan yönetir.
    Ayrıca motive_50_* ve motive_75_* anahtarları ile
    %50 / %75 seviyeleri için ayrı motivasyon ayarları sağlar.
    Eski mot_* auto anahtarına da yazılır (geri uyum).
    """

    STYLE_LIST = [
        # sade tostlar
        "zoom_fade",
        "toast",
        "toast_top",
        "toast_bottom",
        "toast_top_right",
        "toast_bottom_right",
        "toast_top_left",
        "toast_bottom_left",
        # efektler
        "confetti",
        "confetti_soft",
        "confetti_crazy",
        "stars",
        # kombinler
        "both",
        "both_soft",
        "exam_focus",   # YKS modunda üst bar + hafif konfeti
        "last_sprint",  # %75 civarı son düzlüğe girerken
        "epic",
        "minimal",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Motivasyon Ayarları")
        self.resize(620, 420)

        # --- mevcut 100% ayarlarını oku ---
        s = {}
        try:
            s = mot_load() if callable(mot_load) else {}
        except Exception:
            s = {}

        # Defaultlar (ui/motivation_toast.DEFAULTS ile uyumlu)
        s.setdefault("message", "Harika! Tüm ödevleri tamamladın! 🎉")
        s.setdefault("color", "#16a34a")
        s.setdefault("duration", 2600)
        s.setdefault("font", 24)
        s.setdefault("sound_path", "")
        s.setdefault("sound_volume", 0.25)
        s.setdefault("confetti", 120)
        s.setdefault("style", "both")

        # auto flag'i hem motive_* hem eski mot_* anahtarlarından gelebilir
        auto = (
            bool(appset.ayar_get("motive_auto_when_full", True))
            or bool(appset.ayar_get("motive_auto_on_full", True))
            or bool(appset.ayar_get("motive_auto_100", True))
            or bool(appset.ayar_get("mot_auto_show", True))
        )

        # %50 / %75 ayarları (yoksa 100% ayarlarına düşer)
        try:
            from ui.motivation_toast import load_level_settings as mot_load_level
        except Exception:
            mot_load_level = None

        if mot_load_level:
            s75 = mot_load_level(75)
            s50 = mot_load_level(50)
        else:
            # fall-back: 75/50 için makul varsayılanlar
            s75 = dict(
                auto=True,
                message="İyi gidiyorsun! Çoğunu bitirdin, devam! 🚀",
                color="#0ea5e9",
                duration=2200,
                font=22,
                style="last_sprint",
                confetti=140,
                sound_path="",
                sound_volume=0.25,
            )
            s50 = dict(
                auto=True,
                message="Güzel başlangıç, yolun yarısındasın! 💪",
                color="#f59e0b",
                duration=2000,
                font=20,
                style="exam_focus",
                confetti=80,
                sound_path="",
                sound_volume=0.25,
            )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ----------------- Sekmeler -----------------
        tabs = QTabWidget()
        root.addWidget(tabs)

        # === 100% SEKME ===
        tab100 = QWidget()
        tabs.addTab(tab100, "%100 Tamamlandığında")

        lay100 = QVBoxLayout(tab100)
        gbox100 = QGroupBox("Tamamı %100 olduğunda")
        g100 = QGridLayout(gbox100)
        g100.setContentsMargins(12, 10, 12, 10)
        g100.setHorizontalSpacing(10)
        g100.setVerticalSpacing(8)

        self.chkAuto100 = QCheckBox("Tamamı %100 olduğunda otomatik göster")
        self.chkAuto100.setChecked(bool(auto))
        g100.addWidget(self.chkAuto100, 0, 0, 1, 3)

        # stil
        self.cmbStyle100 = QComboBox()
        self.cmbStyle100.addItems(self.STYLE_LIST)
        cur_style = str(s.get("style", "both"))
        if cur_style not in self.STYLE_LIST:
            self.cmbStyle100.addItem(cur_style)
        self.cmbStyle100.setCurrentText(cur_style)

        # mesaj
        self.txtMsg100 = QLineEdit(str(s.get("message", "")))

        # süre
        self.spinMs100 = QSpinBox()
        self.spinMs100.setRange(500, 15000)
        self.spinMs100.setValue(int(s.get("duration", 2600)))

        # font
        self.spinFont100 = QSpinBox()
        self.spinFont100.setRange(10, 120)
        self.spinFont100.setValue(int(s.get("font", 24)))

        # konfeti yoğunluğu
        self.spinConf100 = QSpinBox()
        self.spinConf100.setRange(10, 250)
        self.spinConf100.setValue(int(s.get("confetti", 120)))

        # renk
        self.txtColor100 = QLineEdit(str(s.get("color", "#16a34a")))
        btnColor100 = QPushButton("Renk Seç...")

        # ses yolu
        self.txtSound100 = QLineEdit(str(s.get("sound_path", "") or ""))
        btnSound100 = QPushButton("Ses Seç...")

        # ses seviyesi
        self.spinVol100 = QDoubleSpinBox()
        self.spinVol100.setRange(0.0, 1.0)
        self.spinVol100.setSingleStep(0.05)
        self.spinVol100.setValue(float(s.get("sound_volume", 0.25)))

        btnColor100.clicked.connect(
            lambda: self._pick_color(self.txtColor100)
        )
        btnSound100.clicked.connect(
            lambda: self._pick_sound(self.txtSound100)
        )

        r = 1
        g100.addWidget(QLabel("Stil"), r, 0)
        g100.addWidget(self.cmbStyle100, r, 1, 1, 2)
        r += 1
        g100.addWidget(QLabel("Mesaj"), r, 0)
        g100.addWidget(self.txtMsg100, r, 1, 1, 2)
        r += 1
        g100.addWidget(QLabel("Süre (ms)"), r, 0)
        g100.addWidget(self.spinMs100, r, 1, 1, 2)
        r += 1
        g100.addWidget(QLabel("Font Boyutu"), r, 0)
        g100.addWidget(self.spinFont100, r, 1, 1, 2)
        r += 1
        g100.addWidget(QLabel("Konfeti Yoğunluğu"), r, 0)
        g100.addWidget(self.spinConf100, r, 1, 1, 2)
        r += 1
        g100.addWidget(QLabel("Renk"), r, 0)
        g100.addWidget(self.txtColor100, r, 1)
        g100.addWidget(btnColor100, r, 2)
        r += 1
        g100.addWidget(QLabel("Ses"), r, 0)
        g100.addWidget(self.txtSound100, r, 1)
        g100.addWidget(btnSound100, r, 2)
        r += 1
        g100.addWidget(QLabel("Ses Seviyesi (0–1)"), r, 0)
        g100.addWidget(self.spinVol100, r, 1, 1, 2)
        r += 1

        lay100.addWidget(gbox100)

        # === %75 SEKME ===
        tab75 = QWidget()
        tabs.addTab(tab75, "%75 Tamamlandığında")

        lay75 = QVBoxLayout(tab75)
        gbox75 = QGroupBox("%75 seviyesinde motivasyon")
        g75 = QGridLayout(gbox75)
        g75.setContentsMargins(12, 10, 12, 10)
        g75.setHorizontalSpacing(10)
        g75.setVerticalSpacing(8)

        self.chkAuto75 = QCheckBox("%75 olduğunda otomatik göster")
        self.chkAuto75.setChecked(bool(s75.get("auto", True)))
        g75.addWidget(self.chkAuto75, 0, 0, 1, 3)

        self.cmbStyle75 = QComboBox()
        self.cmbStyle75.addItems(self.STYLE_LIST)
        cur_style75 = str(s75.get("style", "last_sprint"))
        if cur_style75 not in self.STYLE_LIST:
            self.cmbStyle75.addItem(cur_style75)
        self.cmbStyle75.setCurrentText(cur_style75)

        self.txtMsg75 = QLineEdit(str(s75.get("message", "")))
        self.spinMs75 = QSpinBox()
        self.spinMs75.setRange(500, 15000)
        self.spinMs75.setValue(int(s75.get("duration", 2200)))
        self.spinFont75 = QSpinBox()
        self.spinFont75.setRange(10, 120)
        self.spinFont75.setValue(int(s75.get("font", 22)))
        self.spinConf75 = QSpinBox()
        self.spinConf75.setRange(10, 250)
        self.spinConf75.setValue(int(s75.get("confetti", 140)))
        self.txtColor75 = QLineEdit(str(s75.get("color", "#0ea5e9")))
        btnColor75 = QPushButton("Renk Seç...")
        self.txtSound75 = QLineEdit(str(s75.get("sound_path", "") or ""))
        btnSound75 = QPushButton("Ses Seç...")
        self.spinVol75 = QDoubleSpinBox()
        self.spinVol75.setRange(0.0, 1.0)
        self.spinVol75.setSingleStep(0.05)
        self.spinVol75.setValue(float(s75.get("sound_volume", 0.25)))

        btnColor75.clicked.connect(
            lambda: self._pick_color(self.txtColor75)
        )
        btnSound75.clicked.connect(
            lambda: self._pick_sound(self.txtSound75)
        )

        r = 1
        g75.addWidget(QLabel("Stil"), r, 0)
        g75.addWidget(self.cmbStyle75, r, 1, 1, 2)
        r += 1
        g75.addWidget(QLabel("Mesaj"), r, 0)
        g75.addWidget(self.txtMsg75, r, 1, 1, 2)
        r += 1
        g75.addWidget(QLabel("Süre (ms)"), r, 0)
        g75.addWidget(self.spinMs75, r, 1, 1, 2)
        r += 1
        g75.addWidget(QLabel("Font Boyutu"), r, 0)
        g75.addWidget(self.spinFont75, r, 1, 1, 2)
        r += 1
        g75.addWidget(QLabel("Konfeti Yoğunluğu"), r, 0)
        g75.addWidget(self.spinConf75, r, 1, 1, 2)
        r += 1
        g75.addWidget(QLabel("Renk"), r, 0)
        g75.addWidget(self.txtColor75, r, 1)
        g75.addWidget(btnColor75, r, 2)
        r += 1
        g75.addWidget(QLabel("Ses"), r, 0)
        g75.addWidget(self.txtSound75, r, 1)
        g75.addWidget(btnSound75, r, 2)
        r += 1
        g75.addWidget(QLabel("Ses Seviyesi (0–1)"), r, 0)
        g75.addWidget(self.spinVol75, r, 1, 1, 2)
        r += 1

        lay75.addWidget(gbox75)

        # === %50 SEKME ===
        tab50 = QWidget()
        tabs.addTab(tab50, "%50 Tamamlandığında")

        lay50 = QVBoxLayout(tab50)
        gbox50 = QGroupBox("%50 seviyesinde motivasyon")
        g50 = QGridLayout(gbox50)
        g50.setContentsMargins(12, 10, 12, 10)
        g50.setHorizontalSpacing(10)
        g50.setVerticalSpacing(8)

        self.chkAuto50 = QCheckBox("%50 olduğunda otomatik göster")
        self.chkAuto50.setChecked(bool(s50.get("auto", True)))
        g50.addWidget(self.chkAuto50, 0, 0, 1, 3)

        self.cmbStyle50 = QComboBox()
        self.cmbStyle50.addItems(self.STYLE_LIST)
        cur_style50 = str(s50.get("style", "exam_focus"))
        if cur_style50 not in self.STYLE_LIST:
            self.cmbStyle50.addItem(cur_style50)
        self.cmbStyle50.setCurrentText(cur_style50)

        self.txtMsg50 = QLineEdit(str(s50.get("message", "")))
        self.spinMs50 = QSpinBox()
        self.spinMs50.setRange(500, 15000)
        self.spinMs50.setValue(int(s50.get("duration", 2000)))
        self.spinFont50 = QSpinBox()
        self.spinFont50.setRange(10, 120)
        self.spinFont50.setValue(int(s50.get("font", 20)))
        self.spinConf50 = QSpinBox()
        self.spinConf50.setRange(10, 250)
        self.spinConf50.setValue(int(s50.get("confetti", 80)))
        self.txtColor50 = QLineEdit(str(s50.get("color", "#f59e0b")))
        btnColor50 = QPushButton("Renk Seç...")
        self.txtSound50 = QLineEdit(str(s50.get("sound_path", "") or ""))
        btnSound50 = QPushButton("Ses Seç...")
        self.spinVol50 = QDoubleSpinBox()
        self.spinVol50.setRange(0.0, 1.0)
        self.spinVol50.setSingleStep(0.05)
        self.spinVol50.setValue(float(s50.get("sound_volume", 0.25)))

        btnColor50.clicked.connect(
            lambda: self._pick_color(self.txtColor50)
        )
        btnSound50.clicked.connect(
            lambda: self._pick_sound(self.txtSound50)
        )

        r = 1
        g50.addWidget(QLabel("Stil"), r, 0)
        g50.addWidget(self.cmbStyle50, r, 1, 1, 2)
        r += 1
        g50.addWidget(QLabel("Mesaj"), r, 0)
        g50.addWidget(self.txtMsg50, r, 1, 1, 2)
        r += 1
        g50.addWidget(QLabel("Süre (ms)"), r, 0)
        g50.addWidget(self.spinMs50, r, 1, 1, 2)
        r += 1
        g50.addWidget(QLabel("Font Boyutu"), r, 0)
        g50.addWidget(self.spinFont50, r, 1, 1, 2)
        r += 1
        g50.addWidget(QLabel("Konfeti Yoğunluğu"), r, 0)
        g50.addWidget(self.spinConf50, r, 1, 1, 2)
        r += 1
        g50.addWidget(QLabel("Renk"), r, 0)
        g50.addWidget(self.txtColor50, r, 1)
        g50.addWidget(btnColor50, r, 2)
        r += 1
        g50.addWidget(QLabel("Ses"), r, 0)
        g50.addWidget(self.txtSound50, r, 1)
        g50.addWidget(btnSound50, r, 2)
        r += 1
        g50.addWidget(QLabel("Ses Seviyesi (0–1)"), r, 0)
        g50.addWidget(self.spinVol50, r, 1, 1, 2)
        r += 1

        lay50.addWidget(gbox50)

        # --- alt butonlar ---
        btns = QDialogButtonBox()
        self.btnPreview = btns.addButton(
            "Önizleme", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.btnSave = btns.addButton(
            "Kaydet", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.btnClose = btns.addButton(
            "Kapat", QDialogButtonBox.ButtonRole.RejectRole
        )
        root.addWidget(btns)

        self.btnPreview.clicked.connect(self._preview)
        self.btnSave.clicked.connect(self._save_and_close)
        self.btnClose.clicked.connect(self.reject)

        self._apply_compact_styles()

        # Geri uyum için eski isimler (dışarıda kullandıysan bozulmasın)
        self.chkAuto = self.chkAuto100
        self.cmbStyle = self.cmbStyle100
        self.txtMsg = self.txtMsg100
        self.spinMs = self.spinMs100
        self.spinFont = self.spinFont100
        self.txtColor = self.txtColor100
        self.txtSound = self.txtSound100

    # ----------------------------------------------------

    def _apply_compact_styles(self):
        self.setStyleSheet(
            """
            QGroupBox {
                font-weight:600;
                border:1px solid #e2e8f0;
                border-radius:8px;
                margin-top:10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left:8px;
                padding:0 4px;
            }
            QLabel { color:#0f172a; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                min-height: 26px;
                padding: 2px 6px;
            }
            QPushButton {
                min-height: 28px;
                padding: 6px 10px;
            }
        """
        )

    # --- yardımcılar ---

    def _pick_color(self, line_edit: QLineEdit):
        c = QColorDialog.getColor(
            QColor(line_edit.text() or "#22c55e"), self, "Renk Seç"
        )
        if c.isValid():
            line_edit.setText(c.name())

    def _pick_sound(self, line_edit: QLineEdit):
        fn, _ = QFileDialog.getOpenFileName(
            self, "Ses Seç", "", "Ses Dosyası (*.wav *.mp3 *.m4a)"
        )
        if fn:
            line_edit.setText(fn)

    # --- buton işlemleri ---

    def _preview(self):
        """
        'Önizleme' butonu:
        Artık utils/settings'ten okunan eski değerleri değil,
        DİREKT olarak şu an dialogda gördüğün değerleri kullanıyor.
        """
        # motivation_toast içindeki stil motorunu kullanmaya çalış
        try:
            from ui.motivation_toast import _run_style as mot_run_style
        except Exception:
            mot_run_style = None

        # 100% sekmesindeki güncel değerleri al
        msg = self.txtMsg100.text().strip() or "Süpersin! 🎉"
        color = self.txtColor100.text().strip() or "#22c55e"
        duration = int(self.spinMs100.value())
        font_size = int(self.spinFont100.value())
        conf = int(self.spinConf100.value())
        style = self.cmbStyle100.currentText() or "both"
        sound_path = self.txtSound100.text().strip() or None
        sound_volume = float(self.spinVol100.value())

        if mot_run_style:
            # Tüm efektleri (stil + konfeti + ses) anlık değerlere göre çalıştır
            mot_run_style(
                parent=self,
                style=style,
                message=msg,
                color=color,
                duration_ms=duration,
                font_size=font_size,
                confetti_density=conf,
                sound_path=sound_path,
                sound_volume=sound_volume,
                position="center",
            )
        else:
            # Olmadıysa en basit fallback: sadece toast
            _fallback_toast(
                self,
                msg,
                color=color,
                ms=duration,
                font=font_size,
            )

    def _preview(self):
        """
        'Önizleme' butonu:
        Artık utils/settings'ten okunan eski değerleri değil,
        DİREKT olarak şu an dialogda gördüğün değerleri kullanıyor.
        """
        # motivation_toast içindeki stil motorunu kullanmaya çalış
        try:
            from ui.motivation_toast import _run_style as mot_run_style
        except Exception:
            mot_run_style = None

        # 100% sekmesindeki güncel değerleri al
        msg = self.txtMsg100.text().strip() or "Süpersin! 🎉"
        color = self.txtColor100.text().strip() or "#22c55e"
        duration = int(self.spinMs100.value())
        font_size = int(self.spinFont100.value())
        conf = int(self.spinConf100.value())
        style = self.cmbStyle100.currentText() or "both"
        sound_path = self.txtSound100.text().strip() or None
        sound_volume = float(self.spinVol100.value())

        if mot_run_style:
            # Tüm efektleri (stil + konfeti + ses) anlık değerlere göre çalıştır
            mot_run_style(
                parent=self,
                style=style,
                message=msg,
                color=color,
                duration_ms=duration,
                font_size=font_size,
                confetti_density=conf,
                sound_path=sound_path,
                sound_volume=sound_volume,
                position="center",
            )
        else:
            # Olmadıysa en basit fallback: sadece toast
            _fallback_toast(
                self,
                msg,
                color=color,
                ms=duration,
                font=font_size,
            )


    def _save_and_close(self):
        # ---------- 1) 100% ayarlarını kaydet ----------
        prefs = dict(
            message=self.txtMsg100.text().strip() or "Süpersin! 🎉",
            color=self.txtColor100.text().strip() or "#16a34a",
            duration=int(self.spinMs100.value()),
            font=int(self.spinFont100.value()),
            sound_path=self.txtSound100.text().strip() or None,
            sound_volume=float(self.spinVol100.value()),
            confetti=int(self.spinConf100.value()),
            style=self.cmbStyle100.currentText() or "both",
            auto_when_100=bool(self.chkAuto100.isChecked()),
        )
        try:
            if callable(mot_save):
                mot_save(prefs)
            else:
                # Kanonik keylere direkt yaz
                appset.ayar_set("motive_message", prefs["message"])
                appset.ayar_set("motive_color", prefs["color"])
                appset.ayar_set("motive_duration", prefs["duration"])
                appset.ayar_set("motive_font_size", prefs["font"])
                appset.ayar_set("motive_style", prefs["style"])
                appset.ayar_set(
                    "motive_confetti", prefs.get("confetti", 120)
                )
                if prefs.get("sound_path"):
                    appset.ayar_set("motive_sound_path", prefs["sound_path"])
                appset.ayar_set(
                    "motive_sound_volume", prefs.get("sound_volume", 0.25)
                )
                appset.ayar_set(
                    "motive_auto_when_full",
                    "1" if prefs["auto_when_100"] else "0",
                )
        except Exception:
            # Sessiz düş – yine de temel alanları yaz
            appset.ayar_set("motive_message", prefs["message"])
            appset.ayar_set("motive_color", prefs["color"])
            appset.ayar_set("motive_duration", prefs["duration"])
            appset.ayar_set("motive_font_size", prefs["font"])
            appset.ayar_set("motive_style", prefs["style"])
            appset.ayar_set("motive_confetti", prefs.get("confetti", 120))
            if prefs.get("sound_path"):
                appset.ayar_set("motive_sound_path", prefs["sound_path"])
            appset.ayar_set(
                "motive_sound_volume", prefs.get("sound_volume", 0.25)
            )
            appset.ayar_set(
                "motive_auto_when_full",
                "1" if prefs["auto_when_100"] else "0",
            )

        # Geri uyum için eski mot_* auto anahtarına da yaz
        appset.ayar_set(
            "mot_auto_show", "1" if self.chkAuto100.isChecked() else "0"
        )

        # ---------- 2) %75 ve %50 ayarlarını kaydet ----------
        def save_level(level: int,
                       auto_cb: QCheckBox,
                       txt_msg: QLineEdit,
                       txt_color: QLineEdit,
                       spin_ms: QSpinBox,
                       spin_font: QSpinBox,
                       spin_conf: QSpinBox,
                       cmb_style: QComboBox,
                       txt_sound: QLineEdit,
                       spin_vol: QDoubleSpinBox):
            if appset is None:
                return
            pref = dict(
                auto=bool(auto_cb.isChecked()),
                message=txt_msg.text().strip(),
                color=txt_color.text().strip() or "#16a34a",
                duration=int(spin_ms.value()),
                font=int(spin_font.value()),
                confetti=int(spin_conf.value()),
                style=cmb_style.currentText() or "both",
                sound_path=txt_sound.text().strip() or "",
                sound_volume=float(spin_vol.value()),
            )
            appset.ayar_set(f"motive_{level}_auto", "1" if pref["auto"] else "0")
            appset.ayar_set(f"motive_{level}_message", pref["message"])
            appset.ayar_set(f"motive_{level}_color", pref["color"])
            appset.ayar_set(f"motive_{level}_duration", pref["duration"])
            appset.ayar_set(f"motive_{level}_font", pref["font"])
            appset.ayar_set(f"motive_{level}_confetti", pref["confetti"])
            appset.ayar_set(f"motive_{level}_style", pref["style"])
            if pref["sound_path"]:
                appset.ayar_set(
                    f"motive_{level}_sound_path", pref["sound_path"]
                )
            appset.ayar_set(
                f"motive_{level}_sound_volume", pref["sound_volume"]
            )

        save_level(
            75,
            self.chkAuto75,
            self.txtMsg75,
            self.txtColor75,
            self.spinMs75,
            self.spinFont75,
            self.spinConf75,
            self.cmbStyle75,
            self.txtSound75,
            self.spinVol75,
        )
        save_level(
            50,
            self.chkAuto50,
            self.txtMsg50,
            self.txtColor50,
            self.spinMs50,
            self.spinFont50,
            self.spinConf50,
            self.cmbStyle50,
            self.txtSound50,
            self.spinVol50,
        )

        self.accept()



# ---------------- Ana Ayarlar (ScrollArea + Compact) ----------------
class UygulamaAyarlar(QWidget):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("Uygulama Ayarları")
        self.resize(780, 560)

        # scrollable içerik
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        page = QWidget()
        scroll.setWidget(page)
        root = QVBoxLayout(page)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        outer.addWidget(scroll)

        self._tema_presets, self._tema_apply_preset, self._apply_theme = _theme_api()

        # Tema seçimi
        gb_theme = QGroupBox("Tema")
        g0 = QGridLayout(gb_theme)
        g0.setContentsMargins(12, 10, 12, 10)
        g0.setHorizontalSpacing(10)
        self.radAcik = QRadioButton("Açık")
        self.radKoyu = QRadioButton("Koyu")
        tema_kayit = (appset.ayar_get('tema', 'açık') or 'açık').lower().strip()
        (self.radKoyu if tema_kayit in ('koyu', 'dark') else self.radAcik).setChecked(True)
        g0.addWidget(self.radAcik, 0, 0)
        g0.addWidget(self.radKoyu, 0, 1)
        root.addWidget(gb_theme)

        # Görünüm Ayarları + Tema Yöneticisi + Motivasyon
        hbTop = QHBoxLayout()
        hbTop.addStretch(1)

        btnGorunum = QPushButton("Görünüm Ayarları…")
        btnGorunum.clicked.connect(self._ac_gorunum_ayar)
        hbTop.addWidget(btnGorunum)

        btnTema = QPushButton("Tema Yöneticisi…")
        btnTema.clicked.connect(self._ac_tema_yonetici)
        hbTop.addWidget(btnTema)

        self.lblMot = QLabel(self._mot_summary_text())
        btnMot = QPushButton("Motivasyon Ayarları…")
        btnMot.clicked.connect(self._ac_motivation)
        hbTop.addWidget(self.lblMot)
        hbTop.addWidget(btnMot)

        btnBackup = QPushButton("☁️ Veri Yedekleme")
        btnBackup.setStyleSheet("background-color: #ebf8ff; color: #2b6cb0; border: 1px solid #bee3f8;")
        btnBackup.clicked.connect(self._ac_backup)
        hbTop.addWidget(btnBackup)
        
        btnAudit = QPushButton("📜 İşlem Kayıtları")
        btnAudit.setStyleSheet("background-color: #f3e8ff; color: #6b21a8; border: 1px solid #d8b4fe;")
        btnAudit.clicked.connect(self._ac_audit)
        hbTop.addWidget(btnAudit)
        
        root.addLayout(hbTop)

        # PDF Ayarları
        gb_pdf = QGroupBox("PDF Ayarları")
        g = QGridLayout(gb_pdf)
        g.setContentsMargins(12, 10, 12, 10)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(8)
        self.txtKurum = QLineEdit(str(appset.ayar_get('kurum_adi', '')))
        self.txtLogo = QLineEdit(str(appset.ayar_get('logo_path', '')))
        self.cmbLogoHiza = QComboBox()
        self.cmbLogoHiza.addItems(["left", "center", "right"])
        self.cmbLogoHiza.setCurrentText(appset.ayar_get('logo_align', 'left') or 'left')
        self.txtIletisim = QLineEdit(str(appset.ayar_get('iletisim_satiri', '')))
        self.txtQr = QLineEdit(str(appset.ayar_get('odev_qr_link', '')))
        self.txtKocu = QLineEdit(str(appset.ayar_get('egitim_kocu', '')))
        self.txtHatirlaWp = QLineEdit(str(appset.ayar_get(
            'hatirlatma_wp_sablon',
            'Merhaba, yarın ödev kontrolünüz var. Lütfen şu çalışmaları tamamlayın: {ozet}'
        )))
        self.txtHatirlaWp2 = QLineEdit(str(appset.ayar_get(
            'hatirlatma_wp_sablon_geciken',
            'Merhaba, gecikmiş ödevleriniz bulunuyor: {ozet}'
        )))
        self.txtWeb = QLineEdit(str(appset.ayar_get('kurum_web', '')))
        btnLogo = QPushButton("Seç...")
        btnLogo.clicked.connect(self._logo_sec)

        i = 0
        g.addWidget(QLabel("Kurum Adı"), i, 0)
        g.addWidget(self.txtKurum, i, 1, 1, 2)
        i += 1
        g.addWidget(QLabel("Logo"), i, 0)
        g.addWidget(self.txtLogo, i, 1)
        g.addWidget(btnLogo, i, 2)
        i += 1
        g.addWidget(QLabel("Logo Hizası"), i, 0)
        g.addWidget(self.cmbLogoHiza, i, 1, 1, 2)
        i += 1
        g.addWidget(QLabel("İletişim Satırı (adres/telefon)"), i, 0)
        g.addWidget(self.txtIletisim, i, 1, 1, 2)
        i += 1
        g.addWidget(QLabel("Ödev QR Linki (opsiyonel)"), i, 0)
        g.addWidget(self.txtQr, i, 1, 1, 2)
        i += 1
        g.addWidget(QLabel("Eğitim Koçu Bilgisi"), i, 0)
        g.addWidget(self.txtKocu, i, 1, 1, 2)
        i += 1
        g.addWidget(QLabel("WhatsApp Hatırlatma Şablonu"), i, 0)
        g.addWidget(self.txtHatirlaWp, i, 1, 1, 2)
        i += 1
        g.addWidget(QLabel("Geciken Şablonu"), i, 0)
        g.addWidget(self.txtHatirlaWp2, i, 1, 1, 2)
        i += 1
        g.addWidget(QLabel("Kurum Web Adresi"), i, 0)
        g.addWidget(self.txtWeb, i, 1, 1, 2)
        i += 1
        root.addWidget(gb_pdf)

        # WhatsApp görselleri
        gb_wp = QGroupBox("WhatsApp Görsel Şablonları")
        g2 = QGridLayout(gb_wp)
        g2.setContentsMargins(12, 10, 12, 10)
        g2.setHorizontalSpacing(10)
        g2.setVerticalSpacing(8)
        self.txtWpSearch = QLineEdit(str(appset.ayar_get('wp_search_img', '')))
        self.txtWpError = QLineEdit(str(appset.ayar_get('wp_error_img', '')))
        b1 = QPushButton("Arama Görseli Seç...", clicked=lambda: self._gorsel_sec(self.txtWpSearch))
        b2 = QPushButton("Hata Görseli Seç...", clicked=lambda: self._gorsel_sec(self.txtWpError))
        g2.addWidget(QLabel("Arama Kutusu Görseli"), 0, 0)
        g2.addWidget(self.txtWpSearch, 0, 1)
        g2.addWidget(b1, 0, 2)
        g2.addWidget(QLabel("Hata Görseli"), 1, 0)
        g2.addWidget(self.txtWpError, 1, 1)
        g2.addWidget(b2, 1, 2)
        root.addWidget(gb_wp)

        # alt bar
        bar = QHBoxLayout()
        bar.addStretch(1)
        bar.addWidget(QPushButton("Kapat", clicked=self.close))
        btnKaydet = QPushButton("Kaydet", clicked=self._kaydet)
        bar.addWidget(btnKaydet)
        root.addLayout(bar)

        # Compact görünüm
        self.setStyleSheet("""
            QGroupBox { font-weight:600; border:1px solid #e2e8f0; border-radius:8px; margin-top:10px; }
            QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }
            QLabel { color:#0f172a; }
            QLineEdit, QComboBox, QSpinBox { min-height: 26px; padding: 2px 6px; }
            QPushButton { min-height: 28px; padding: 6px 12px; }
        """)
        try:
            apply_responsive(self)
        except Exception:
            pass

    # --- helpers ---
    def _mot_summary_text(self):
        # Gerçek kayıtları motivation_toast'tan oku
        try:
            s = mot_load() if callable(mot_load) else {}
        except Exception:
            s = {}
        style_txt = (s.get("style") or appset.ayar_get('motive_style', 'zoom_fade') or 'zoom_fade')
        auto = (
            bool(appset.ayar_get('motive_auto_when_full', True)) or
            bool(appset.ayar_get('motive_auto_on_full', True)) or
            bool(appset.ayar_get('motive_auto_100', True)) or
            bool(appset.ayar_get('mot_auto_show', True))
        )
        return f"Motivasyon: {style_txt}  ({'otomatik' if auto else 'manuel'})"

    def _ac_gorunum_ayar(self):
        GorunumAyarDialog(self).exec()

    def _ac_tema_yonetici(self):
        dlg = ThemeManagerDialog(self)
        if dlg.exec():
            # Kaydet ve kapat ile çıktıysa, temayı yeniden uygula
            try:
                _, _, apply_theme = _theme_api()
                apply_theme(QApplication.instance())
            except Exception:
                pass

    def _ac_motivation(self):
        dlg = MotivationDialog(self)
        if dlg.exec():
            self.lblMot.setText(self._mot_summary_text())

    def _ac_backup(self):
        from ui.backup_dialog import BackupDialog
        BackupDialog(self).exec()

    def _ac_audit(self):
        try:
            from ui.audit_viewer import AuditLogDialog
            AuditLogDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Log görüntüleyici açılamadı:\n{e}")

    def _logo_sec(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Logo Seç", "", "Resim (*.png *.jpg *.jpeg)")
        if fn:
            self.txtLogo.setText(fn)

    def _gorsel_sec(self, line: QLineEdit):
        fn, _ = QFileDialog.getOpenFileName(self, "Görsel Seç", "", "Resim (*.png *.jpg *.jpeg)")
        if fn:
            line.setText(fn)

    def _kaydet(self):
        appset.ayar_set('tema', 'koyu' if self.radKoyu.isChecked() else 'açık')
        appset.ayar_set('kurum_adi', self.txtKurum.text().strip())
        appset.ayar_set('logo_path', self.txtLogo.text().strip())
        appset.ayar_set('logo_align', self.cmbLogoHiza.currentText())
        appset.ayar_set('iletisim_satiri', self.txtIletisim.text().strip())
        appset.ayar_set('odev_qr_link', self.txtQr.text().strip())
        appset.ayar_set('egitim_kocu', self.txtKocu.text().strip())
        appset.ayar_set('hatirlatma_wp_sablon', self.txtHatirlaWp.text().strip())
        appset.ayar_set('hatirlatma_wp_sablon_geciken', self.txtHatirlaWp2.text().strip())
        appset.ayar_set('kurum_web', self.txtWeb.text().strip())
        appset.ayar_set('wp_search_img', self.txtWpSearch.text().strip())
        appset.ayar_set('wp_error_img', self.txtWpError.text().strip())
        # temayı uygula (varsa)
        try:
            _, _, apply_theme = _theme_api()
            apply_theme(QApplication.instance())
        except Exception:
            pass
        QMessageBox.information(self, "Ayar", "Ayarlar kaydedildi.")
        try:
            apply_responsive(self)
        except Exception:
            pass


# ----- geri uyumlu kısa adlar -----
def ayar_get(anahtar, varsayilan=None):
    return appset.ayar_get(anahtar, varsayilan)


def ayar_set(anahtar, deger):
    return appset.ayar_set(anahtar, deger)
