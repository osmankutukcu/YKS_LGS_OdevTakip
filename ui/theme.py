# -*- coding: utf-8 -*-
from ui import app_settings as appset

# ==========================
#  Küçük renk yardımcıları
# ==========================
def _clamp(v):
    return max(0, min(255, int(v)))

def _hex_to_rgb(h):
    h = h.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(_clamp(c) for c in rgb)

def _mix(c1, c2, t=0.5):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))

def _shade(c, f):  # f>1 aç, f<1 koyu
    r, g, b = _hex_to_rgb(c)
    if f >= 1:
        return _rgb_to_hex((r + (255 - r) * (f - 1), g + (255 - g) * (f - 1), b + (255 - b) * (f - 1)))
    else:
        return _rgb_to_hex((r * f, g * f, b * f))

# ==========================
#  Tema Preset'leri
# ==========================
def tema_presets():
    # mode: 'dark' ya da 'light'
    return {
        # ——— KOYU (yumuşak) ———
        "Soft Dark":        {"mode": "dark",  "primary": "#69A7FF", "accent": "#35C176", "bg": "#222428"},
        "Nord":             {"mode": "dark",  "primary": "#88C0D0", "accent": "#A3BE8C", "bg": "#2E3440"},
        "Dracula":          {"mode": "dark",  "primary": "#BD93F9", "accent": "#50FA7B", "bg": "#282A36"}, # Fixed BG
        "Atom One Dark":    {"mode": "dark",  "primary": "#61AFEF", "accent": "#98C379", "bg": "#1F2329"},
        "Everforest":       {"mode": "dark",  "primary": "#A7C080", "accent": "#E69875", "bg": "#2D353B"},
        "Catppuccin Mocha": {"mode": "dark",  "primary": "#89b4fa", "accent": "#a6e3a1", "bg": "#1e1e2e"},
        "Klasik Koyu":      {"mode": "dark",  "primary": "#3b82f6", "accent": "#10b981", "bg": "#18181b"}, # Modernized (Zinc-900 / Blue-500)

        # ——— AÇIK (modern) ———
        "Cloud Light":      {"mode": "light", "primary": "#2563eb", "accent": "#10b981", "bg": "#ffffff"}, # Inter blue
        "Duo Light":        {"mode": "light", "primary": "#0B61A4", "accent": "#2EA043", "bg": "#FAFAFC"},
        "Material Blue":    {"mode": "light", "primary": "#2962FF", "accent": "#00C853", "bg": "#FFFFFF"},
        "Silk":             {"mode": "light", "primary": "#1F7AE0", "accent": "#50B37B", "bg": "#F7F8FA"},
        "Mint Light":       {"mode": "light", "primary": "#2D7CF7", "accent": "#19B885", "bg": "#F9FAFB"},
        "Solarized Light":  {"mode": "light", "primary": "#268BD2", "accent": "#2AA198", "bg": "#FDF6E3"},
        "One Light":        {"mode": "light", "primary": "#0B61A4", "accent": "#2EA043", "bg": "#FAFAFA"},
        "Catppuccin Latte": {"mode": "light", "primary": "#1e66f5", "accent": "#40a02b", "bg": "#eff1f5"},

        # ——— SPOR ———
        "Fenerbahçe":       {"mode": "light", "primary": "#0A2A66", "accent": "#FFD100", "bg": "#FFFFFF"},
        "Galatasaray":      {"mode": "light", "primary": "#A40000", "accent": "#FFB81C", "bg": "#FFF9F1"},
        "Beşiktaş":         {"mode": "light", "primary": "#000000", "accent": "#E30613", "bg": "#FFFFFF"},
        "Trabzonspor":      {"mode": "light", "primary": "#7C162E", "accent": "#3A88A0", "bg": "#FDFDFE"},
        "Samsunspor":       {"mode": "light", "primary": "#D40000", "accent": "#222222", "bg": "#FFFFFF"},
        "Anadolu Efes":     {"mode": "light", "primary": "#0D47A1", "accent": "#E53935", "bg": "#FFFFFF"},

        # ——— GENÇ & eğlenceli ———
        "Neon":             {"mode": "dark",  "primary": "#00F5D4", "accent": "#F15BB5", "bg": "#111218"},
        "Cyberpunk":        {"mode": "dark",  "primary": "#08F7FE", "accent": "#FE53BB", "bg": "#1A002B"},
        "Vaporwave":        {"mode": "dark",  "primary": "#7DF9FF", "accent": "#FF77AA", "bg": "#201A3A"},
        "Pastel Pop":       {"mode": "light", "primary": "#6C8CFF", "accent": "#FF9EC4", "bg": "#FFFDFE"},
        "Sakura":           {"mode": "light", "primary": "#D14D72", "accent": "#FFB3C1", "bg": "#FFF4F7"},
        "Ocean Breeze":     {"mode": "light", "primary": "#0BA3C7", "accent": "#00C2A8", "bg": "#F4FBFD"},
        "Sunset Pop":       {"mode": "light", "primary": "#F76B1C", "accent": "#FAD961", "bg": "#FFF7EE"},
        "Midnight Purple":  {"mode": "dark",  "primary": "#9A7BFF", "accent": "#6BE6B4", "bg": "#181325"},
        "Matrix":           {"mode": "dark",  "primary": "#00FF88", "accent": "#81F495", "bg": "#0F1511"},
        "Retro GameBoy":    {"mode": "light", "primary": "#0F380F", "accent": "#8BAC0F", "bg": "#E0F8D0"},
        "Rainbow Candy":    {"mode": "light", "primary": "#7D5FFF", "accent": "#FF6B6B", "bg": "#FFFFFF"},
        "Forest Mint":      {"mode": "light", "primary": "#2E7D32", "accent": "#00C896", "bg": "#F2FBF7"},
    }

def tema_apply_preset(ad):
    """Seçilen preset'i ayarlara yazar (UI tarafında çağırabilirsin)."""
    p = tema_presets().get(ad)
    if not p:
        return
    appset.ayar_set("tema_seti", ad)
    appset.ayar_set("tema_mod", "koyu" if p["mode"] == "dark" else "açık")
    appset.ayar_set("tema_primary", p["primary"])
    appset.ayar_set("tema_accent",  p["accent"])
    appset.ayar_set("tema_bg",      p["bg"])

# ==========================
#  QSS Üretimi
# ==========================
def build_qss():
    # Varsayılan (Fallback) temayı 'açık' (Light) olarak değiştiriyoruz.
    tema = (appset.ayar_get('tema', None) or appset.ayar_get('tema_mod', 'açık') or 'açık').lower()
    if tema not in ('açık', 'acik', 'light', 'koyu', 'dark'):
        tema = 'açık'
    is_dark = tema in ('koyu', 'dark')

    preset_ad = appset.ayar_get('tema_seti', None)
    preset = tema_presets().get(preset_ad, None)

    font_px  = int(appset.ayar_get('tema_font', '12') or 12)
    density  = (appset.ayar_get('tema_density', 'cozy') or 'cozy').lower()
    radius   = int(appset.ayar_get('tema_radius', '6') or 6)
    borders  = (appset.ayar_get('tema_borders', 'normal') or 'normal').lower()
    sb_size  = int(appset.ayar_get('tema_scrollbar', '12') or 12)

    if density == 'compact':
        pad_y, pad_x, row_pad = 4, 8, 4
    elif density == 'comfortable':
        pad_y, pad_x, row_pad = 9, 14, 9
    else:
        pad_y, pad_x, row_pad = 7, 12, 7

    primary = (appset.ayar_get('tema_primary', None) or (preset['primary'] if preset else '#2d89ef'))
    accent  = (appset.ayar_get('tema_accent',  None) or (preset['accent']  if preset else '#21ba45'))

    # Mode uyumluluğu kontrolü: Preset, istenen modla (Koyu/Açık) uyuşuyorsa BG'sini kullan
    use_preset_bg = False
    if preset:
        preset_mode = preset.get("mode", "dark")
        if is_dark and preset_mode == "dark":
            use_preset_bg = True
        elif not is_dark and preset_mode == "light":
            use_preset_bg = True

    # Eğer manuel arka plan ayarı varsa onu kullan, yoksa preset uyumluysa onu, yoksa varsayılan
    default_bg_for_mode = '#1b1c1d' if is_dark else '#ffffff'
    preset_bg = preset['bg'] if (preset and use_preset_bg) else default_bg_for_mode
    
    bg = appset.ayar_get('tema_bg', None) or preset_bg

    fg      = '#EDEDED' if is_dark else '#1b1b1b'

    # Kart ve alt arka plan, kullanıcıya açıldı
    default_card = '#2A2C31' if is_dark else '#F6F7F9'
    default_alt  = '#33363C' if is_dark else '#EEF0F3'
    card = appset.ayar_get('tema_card', default_card) or default_card
    alt  = appset.ayar_get('tema_alt',  default_alt)  or default_alt

    bd_mix  = 0.65 if borders == 'subtle' else (0.45 if borders == 'bold' else 0.55)
    bd      = _mix(card, bg, bd_mix)
    dim     = _mix(fg, bg, 0.65 if is_dark else 0.45)

    # Listeler – moda göre varsayılan
    default_list_bg = '#1b1c1d' if is_dark else '#FFFFFF'
    default_list_fg = '#EDEDED' if is_dark else '#111315'
    default_list_alt = '#252628' if is_dark else '#F4F7FB'
    default_grid_c = '#383b40' if is_dark else '#D9DEE5'
    
    default_head_bg = '#2A2C31' if is_dark else '#FFFFFF'
    default_head_fg = '#EAF2FF' if is_dark else '#2B2F33'

    list_bg   = appset.ayar_get('tema_list_bg',   default_list_bg) or default_list_bg
    list_fg   = appset.ayar_get('tema_list_fg',   default_list_fg) or default_list_fg
    list_alt  = appset.ayar_get('tema_list_alt',  default_list_alt) or default_list_alt
    grid_c    = appset.ayar_get('tema_list_grid', default_grid_c) or default_grid_c
    
    head_bg   = appset.ayar_get('tema_head_bg',   default_head_bg) or default_head_bg
    head_fg   = appset.ayar_get('tema_head_fg',   default_head_fg) or default_head_fg
    head_glow = appset.ayar_get('tema_head_glow', _mix(primary, '#FFFFFF', 0.92))

    # Liste hover renkleri
    default_list_hover_bg = _mix(primary, list_bg, 0.06)
    list_hover_bg = appset.ayar_get('tema_list_hover_bg', default_list_hover_bg) or default_list_hover_bg
    list_hover_fg = appset.ayar_get('tema_list_hover_fg', list_fg) or list_fg

    danger = appset.ayar_get('tema_danger', '#D32F2F') or '#D32F2F'
    warn   = appset.ayar_get('tema_warn',   '#F6A721') or '#F6A721'
    ok     = appset.ayar_get('tema_ok',     accent)    or accent

    # Buton renkleri
    button_bg     = appset.ayar_get('tema_button_bg',     primary) or primary
    button_fg     = appset.ayar_get('tema_button_fg',     '#ffffff') or '#ffffff'
    button_border = appset.ayar_get('tema_button_border', primary) or primary

    primary_hover   = _shade(button_bg, 0.9  if is_dark else 1.08)
    primary_pressed = _shade(button_bg, 0.80 if is_dark else 0.95)
    sel_bg_dark     = _mix(primary, '#000000', 0.22)
    sel_bg_light    = _mix(primary, '#FFFFFF', 0.88)
    sel_bg          = sel_bg_dark if is_dark else sel_bg_light
    sel_fg          = '#FFFFFF' if is_dark else '#0F1113'

    popup_bg, popup_fg, popup_sel = '#FFFFFF', '#111315', _mix(primary, '#FFFFFF', 0.85)

    # Başlık 3B hissi + spor aksan çizgisi
    if is_dark:
        # Koyu mod: degrade aşağı doğru biraz daha açılır
        head_grad = f"qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {head_bg}, stop:1 {_mix(head_bg,'#FFFFFF',0.06)})"
    else:
        # Açık mod: degrade aşağı doğru hafif grileşir
        head_grad = f"qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {_mix(head_bg,'#FFFFFF',0.0)}, stop:1 {_mix(head_bg,'#E9EEF6',0.15)})"
    sport_line = _mix(primary, '#FFFFFF', 0.65)  # alt çizgi için

    # Sekme (Tab) renkleri
    default_tab_bg       = _mix(card, bg, 0.80)
    default_tab_sel_bg   = card
    default_tab_fg       = fg
    default_tab_sel_fg   = fg
    default_tab_hover_bg = _mix(default_tab_bg, primary, 0.08)

    tab_bg       = appset.ayar_get('tema_tab_bg',       default_tab_bg)       or default_tab_bg
    tab_fg       = appset.ayar_get('tema_tab_fg',       default_tab_fg)       or default_tab_fg
    tab_sel_bg   = appset.ayar_get('tema_tab_sel_bg',   default_tab_sel_bg)   or default_tab_sel_bg
    tab_sel_fg   = appset.ayar_get('tema_tab_sel_fg',   default_tab_sel_fg)   or default_tab_sel_fg
    tab_hover_bg = appset.ayar_get('tema_tab_hover_bg', default_tab_hover_bg) or default_tab_hover_bg

    # Araç çubuğu butonları için icon-only modu
    icon_only_raw = str(appset.ayar_get('tema_button_icon_only', '0')).lower()
    icon_only = icon_only_raw in ('1', 'true', 'yes', 'on')

    if icon_only:
        toolbutton_block = f"""
    QToolButton {{
        background:transparent;
        border:1px solid {bd};
        border-radius:{radius}px;
        padding:4px;
        min-width:26px;
        max-width:26px;
        font-size:0px;  /* sadece simge */
    }}
    QToolButton:hover {{
        background:{_mix(primary,bg,0.10)};
        border-color:{primary};
    }}
    """
    else:
        toolbutton_block = f"""
    QToolButton {{
        background:{_mix(card,bg,0.85)};
        border:1px solid {bd};
        border-radius:{radius}px;
        padding:{max(2, pad_y-2)}px {max(6, pad_x-4)}px;
    }}
    QToolButton:hover {{
        background:{_mix(primary,bg,0.08)};
        border-color:{primary};
    }}
    """

    return f"""
    /* ====== Temel ====== */
    * {{
        font-size:{font_px}px;
        color:{fg};
    }}
    QWidget {{ background:{bg}; }}

    QLabel {{ background:transparent; color:{('#F2F4F8' if is_dark else '#1b1b1b')}; }}
    QLabel#inverse {{ background:#000; color:#EAF2FF; padding:2px 4px; border-radius:4px; }}

    /* ====== Butonlar ====== */
    QPushButton {{
        background:{button_bg};
        color:{button_fg};
        border:1px solid {button_border};
        padding:{pad_y}px {pad_x}px;
        border-radius:{radius}px;
        font-weight:600;
    }}
    QPushButton:hover   {{ background:{primary_hover}; }}
    QPushButton:pressed {{ background:{primary_pressed}; }}
    QPushButton:disabled {{
        background:{_mix(button_bg,bg,0.2)};
        color:{_mix(button_fg,bg,0.5)};
        border-color:{_mix(button_border,bg,0.2)};
    }}
    QPushButton#btnSecondary {{
        background:transparent;
        color:{primary};
        border:1px solid {bd};
    }}
    QPushButton#btnSecondary:hover {{
        background:{_mix(primary,bg,0.08)};
        border-color:{primary};
    }}
    QPushButton#btnDanger {{ background:{danger}; border-color:{danger}; }}
    QPushButton#btnDanger:hover {{ background:{_shade(danger,0.9)}; }}

    {toolbutton_block}

    /* ====== Metin & Girdi ====== */
    QLineEdit {{
        background:#FFFFFF;
        color:#111315;
        border:1px solid {bd};
        border-radius:{radius}px;
        padding:6px 8px;
        selection-background-color:{sel_bg};
        selection-color:{sel_fg};
    }}
    QLineEdit:focus {{ border:1px solid {primary}; }}

    QPlainTextEdit, QTextEdit {{
        background:{card};
        color:{('#111315' if not is_dark else '#EDEDED')};
        border:1px solid {bd};
        border-radius:{radius}px;
        padding:6px 8px;
        selection-background-color:{sel_bg};
        selection-color:{sel_fg};
    }}
    QPlainTextEdit:focus, QTextEdit:focus {{ border:1px solid {primary}; }}

    /* Tarih/Saat edit ve takvimler okunur */
    QDateEdit, QTimeEdit, QDateTimeEdit {{
        background:#FFFFFF;
        color:#111315;
        border:1px solid {bd};
        border-radius:{radius}px;
        padding:6px 8px;
        selection-background-color:{sel_bg};
        selection-color:{sel_fg};
    }}
    QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{ border:1px solid {primary}; }}
    QCalendarWidget {{
        background:#FFFFFF;
        color:#111315;
        border:1px solid {grid_c};
        border-radius:{radius}px;
    }}
    QCalendarWidget QToolButton {{
        background:transparent;
        color:#111315;
        border:none;
        font-weight:600;
        padding:4px 6px;
    }}
    QCalendarWidget QToolButton:hover {{ background:{popup_sel}; }}
    QCalendarWidget QMenu {{ background:#FFFFFF; color:#111315; }}
    QCalendarWidget QSpinBox {{ background:#FFFFFF; color:#111315; border:1px solid {grid_c}; }}

    /* ComboBox (içerik her zaman görünür) */
    QComboBox {{
        color:#111315;
        background:#FFFFFF;
        border:1px solid {bd};
        border-radius:{radius}px;
        padding:6px 8px;
        selection-background-color:{sel_bg};
        selection-color:{sel_fg};
    }}
    QComboBox:focus {{ border:1px solid {primary}; }}
    QComboBox:editable QLineEdit {{ color:#111315; background:#FFFFFF; border:none; }}
    QComboBox QAbstractItemView {{
        background:{popup_bg};
        color:{popup_fg};
        border:1px solid {grid_c};
        selection-background-color:{popup_sel};
        selection-color:#0F1113;
        outline:none;
    }}
    QComboBox QAbstractItemView::item {{ padding:6px 10px; }}
    QComboBox::drop-down {{
        subcontrol-origin:padding;
        subcontrol-position:top right;
        width:28px;
        border-left:1px solid {bd};
        background:{_mix(primary, '#FFFFFF', 0.15)};
        border-top-right-radius:{radius}px;
        border-bottom-right-radius:{radius}px;
        margin:0;
    }}
    QComboBox::down-arrow {{ width:12px; height:12px; margin-right:7px; }}

    /* Spin buttons */
    QSpinBox, QDoubleSpinBox {{
        padding-right: 20px;
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin:border;
        subcontrol-position:top right;
        width:18px;
        border-left:1px solid {bd};
        background:{_mix(card,bg,0.9)};
        border-top-right-radius:{radius}px;
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
        background:{_mix(card,primary,0.85)};
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: none;
        width: 0; height: 0;
        border-left: 3.5px solid transparent;
        border-right: 3.5px solid transparent;
        border-bottom: 4.5px solid {fg};
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin:border;
        subcontrol-position:bottom right;
        width:18px;
        border-left:1px solid {bd};
        background:{_mix(card,bg,0.9)};
        border-bottom-right-radius:{radius}px;
    }}
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background:{_mix(card,primary,0.85)};
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: none;
        width: 0; height: 0;
        border-left: 3.5px solid transparent;
        border-right: 3.5px solid transparent;
        border-top: 4.5px solid {fg};
    }}

    /* Check/Radio & Item View Indicators */
    QCheckBox, QRadioButton {{ spacing:6px; color:{fg}; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width:16px; height:16px; }}
    QCheckBox::indicator,
    QTableWidget::indicator, QTableView::indicator,
    QListWidget::indicator, QListView::indicator,
    QTreeWidget::indicator, QTreeView::indicator {{
        width:16px;
        height:16px;
        border-radius:3.5px;
        margin:0;
        padding:0;
        border:1.5px solid #9AA4AE;
        background:#FFFFFF;
    }}
    QCheckBox::indicator:hover,
    QTableWidget::indicator:hover, QTableView::indicator:hover,
    QListWidget::indicator:hover, QListView::indicator:hover,
    QTreeWidget::indicator:hover, QTreeView::indicator:hover {{
        border-color:{accent};
    }}
    QCheckBox::indicator:checked,
    QTableWidget::indicator:checked, QTableView::indicator:checked,
    QListWidget::indicator:checked, QListView::indicator:checked,
    QTreeWidget::indicator:checked, QTreeView::indicator:checked {{
        background:{accent};
        border:1.5px solid {_shade(accent,0.85)};
        image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'><path fill='none' stroke='white' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round' d='M3.2 8.2l3.4 3.4L13 4.2'/></svg>");
    }}
    QCheckBox::indicator:disabled,
    QTableWidget::indicator:disabled, QTableView::indicator:disabled,
    QListWidget::indicator:disabled, QListView::indicator:disabled,
    QTreeWidget::indicator:disabled, QTreeView::indicator:disabled {{
        border-color:#CBD5E1;
        background:#F1F5F9;
    }}
    QRadioButton::indicator:unchecked {{
        background:#FFFFFF;
        border:1.5px solid #9AA4AE;
        border-radius:8px;
        width:16px;
        height:16px;
    }}
    QRadioButton::indicator:checked {{
        background:{accent};
        border:4px solid {_shade(accent,0.85)};
        border-radius:8px;
        width:16px;
        height:16px;
    }}

    /* Sekmeler (TabControl) */
    QTabWidget::pane {{
        border:1px solid {bd};
        border-radius:{radius}px;
        padding:4px;
        background:{card};
    }}
    QTabBar::tab {{
        background:{tab_bg};
        color:{tab_fg};
        border:1px solid {bd};
        padding:8px 14px;
        margin:2px;
        border-top-left-radius:{radius}px;
        border-top-right-radius:{radius}px;
    }}
    QTabBar::tab:selected {{
        background:{tab_sel_bg};
        border-bottom-color:{tab_sel_bg};
        color:{tab_sel_fg};
        font-weight:600;
    }}
    QTabBar::tab:hover {{
        background:{tab_hover_bg};
    }}

    /* Başlıklar — yumuşak 3B + spor ince alt çizgi */
    QHeaderView::section {{
        background:{head_grad};
        color:{head_fg};
        padding:{row_pad + 1}px;
        border:0px;
        border-bottom:2px solid {sport_line};
        font-weight:600;
    }}

    /* Listeler — daima açık ve okunur */
    QTableView, QTableWidget, QListView, QTreeView {{
        background:{list_bg};
        color:{list_fg};
        gridline-color:{grid_c};
        selection-background-color:{sel_bg};
        selection-color:{sel_fg};
        alternate-background-color:{list_alt};
        outline:none;
    }}
    QTableView::item, QTableWidget::item, QListView::item, QTreeView::item {{
        padding:{row_pad}px 8px;
    }}
    /* Hücre hover */
    QTableView::item:hover,
    QTableWidget::item:hover,
    QListView::item:hover,
    QTreeView::item:hover {{
        background:{list_hover_bg};
        color:{list_hover_fg};
    }}

    /* Menü & Toolbar */
    QMenu {{
        background:{card};
        border:1px solid {bd};
    }}
    QMenu::item {{ padding:6px 12px; }}
    QToolBar {{
        background:{_mix(card,bg,0.9)};
        border-bottom:1px solid {bd};
    }}

    /* Slider */
    QSlider::groove:horizontal {{
        height:6px;
        background:{_mix(card,bg,0.7)};
        border-radius:3px;
    }}
    QSlider::handle:horizontal {{
        width:16px;
        height:16px;
        background:{primary};
        border-radius:8px;
        margin:-5px 0;
    }}

    /* StatusBar */
    QStatusBar {{
        background:{_mix(card,bg,0.9)};
        color:{dim};
    }}

    /* Scrollbars */
    /* Scrollbars - Ultra Modern (Subtle & Thin) */
    QScrollBar:vertical {{
        background: transparent;
        width: {sb_size}px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {_mix(fg, bg, 0.80)};
        min-height: 40px;
        border-radius: {sb_size//2}px;
        border: 4px solid transparent;
        background-clip: content-box;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {_mix(fg, bg, 0.60)};
    }}
    QScrollBar::handle:vertical:pressed {{
        background: {primary};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
        background: transparent;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: {sb_size}px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {_mix(fg, bg, 0.80)};
        min-width: 40px;
        border-radius: {sb_size//2}px;
        border: 4px solid transparent;
        background-clip: content-box;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {_mix(fg, bg, 0.60)};
    }}
    QScrollBar::handle:horizontal:pressed {{
        background: {primary};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
        background: transparent;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}
    QScrollBar::corner {{
        background: transparent;
    }}

    /* Link & muted label */
    QLabel#link, QLabel[textInteractionFlags~="LinksAccessibleByMouse"] {{ color:{primary}; }}
    QLabel#muted {{ color:{dim}; }}

    /* Progress */
    QProgressBar {{
        background:{_mix(card,bg,0.7)};
        border:1px solid {bd};
        border-radius:{radius}px;
        text-align:center;
        color:{fg};
        padding:2px;
    }}
    QProgressBar::chunk {{
        background-color:{ok};
        border-radius:{radius}px;
    }}

    /* MessageBox */
    QMessageBox {{ background:{card}; }}
    QMessageBox QLabel {{ color:{fg}; }}
    QMessageBox QPushButton {{ min-width:88px; }}
    """

# ==========================
#  Uygulama'ya uygula
# ==========================
def apply(app):
    try:
        app.setStyleSheet(build_qss())
    except Exception:
        pass
