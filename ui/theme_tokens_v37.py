# -*- coding: utf-8 -*-
"""V37: semantic UI colors for individual forms; Qt-free to allow headless tests.

These tokens affect presentation only; no database, scheduling, or student records.
"""
from ui import app_settings as appset
from ui.theme_scrollbar_v41 import scrollbar_qss
from ui.theme import (
    _safe_color, _mix, readable_text, tema_presets, _color_setting,
    _contrast_safe_background, _shade,
)


def semantic_palette():
    selected = tema_presets().get(appset.ayar_get('tema_seti', '') or '')
    mode = str(appset.ayar_get('tema_mod', None) or appset.ayar_get('tema', 'açık') or 'açık').lower()
    dark = mode in ('koyu', 'dark')
    matching = selected and selected['mode'] == ('dark' if dark else 'light')
    fallback_bg = selected['bg'] if matching else ('#1b1c1d' if dark else '#FFFFFF')
    # In the absence of a matching preset, an out-of-mode saved background is ignored.
    saved_bg = appset.ayar_get('tema_bg', None)
    if not matching and saved_bg and selected and saved_bg.lower() == selected['bg'].lower():
        saved_bg = None
    bg = _safe_color(saved_bg, fallback_bg)
    surface = _color_setting('tema_card', '#2A2C31' if dark else '#FFFFFF')
    alt = _color_setting('tema_alt', '#33363C' if dark else '#F4F7FB')
    field = '#292C32' if dark else '#FFFFFF'
    fg = readable_text(bg, '#EDEDED' if dark else '#172033')
    surface_fg = readable_text(surface, fg)
    field_fg = readable_text(field, fg)
    primary = _color_setting('tema_primary', selected['primary'] if selected else '#2563eb')
    accent = _color_setting('tema_accent', selected['accent'] if selected else '#10b981')
    border = _mix('#6B7280', bg, 0.42 if dark else 0.65)
    neutral = _mix(surface, fg, 0.06 if dark else 0.025)
    tab_hover = _mix(primary, surface, .13)
    selected_bg = _mix(surface, primary, .20 if dark else .12)
    btn_bg = _mix(primary, '#000000', .15 if dark else .08)
    btn_fg = readable_text(btn_bg, '#FFFFFF')
    btn_hover = _contrast_safe_background(_shade(btn_bg, .92 if dark else 1.07), btn_fg)
    semantic = {
        'dark': dark, 'bg':bg, 'fg':fg, 'surface':surface, 'surface_fg':surface_fg,
        'alt':alt, 'alt_fg':readable_text(alt, surface_fg), 'field':field,
        'field_fg':field_fg, 'primary':primary, 'accent':accent, 'border':border,
        'neutral':neutral,'neutral_fg':readable_text(neutral, fg),
        'tab_hover':tab_hover,'tab_hover_fg':readable_text(tab_hover, surface_fg),
        'selected':selected_bg, 'selected_fg':readable_text(selected_bg, surface_fg, (surface,)),
        'btn_bg':btn_bg, 'btn_fg':btn_fg, 'btn_hover':btn_hover,
        'danger_bg':'#7F1D1D' if dark else '#FEE2E2',
        'success_bg':'#065F46' if dark else '#DCFCE7',
        'info_bg':'#3730A3' if dark else '#EEF2FF',
    }
    for key in ('danger', 'success', 'info'):
        semantic[key+'_fg'] = readable_text(semantic[key+'_bg'], '#FFFFFF' if dark else '#172033')
        semantic[key+'_hover'] = _mix(semantic[key+'_bg'], fg, .12 if dark else .055)
        semantic[key+'_hover_fg'] = readable_text(semantic[key+'_hover'],semantic[key+'_fg'])
    return semantic


def homework_root_qss():
    """Override only presentation of the root tracking form, preserving its signals/actions."""
    c = semantic_palette()
    return f"""
    QWidget#HomeworkRootV37 {{ background:{c['bg']}; color:{c['fg']}; }}
    QLabel {{ color:{c['fg']}; background:transparent; }}
    QGroupBox {{ color:{c['fg']}; border-color:{c['border']}; }}
    QTabWidget::pane {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:6px; }}
    QTabBar::tab {{ background:{c['alt']}; color:{c['alt_fg']}; border:1px solid {c['border']};
        border-radius:6px; padding:6px 12px; margin-right:2px; font-weight:600; }}
    QTabBar::tab:selected {{ background:{c['surface']}; color:{c['surface_fg']};
        border-bottom:2px solid {c['primary']}; }}
    QTabBar::tab:hover:!selected {{ background:{c['tab_hover']}; color:{c['tab_hover_fg']}; }}
    QPushButton, QToolButton {{ background:{c['neutral']};color:{c['neutral_fg']};
        border:1px solid {c['border']};padding:6px 12px;border-radius:6px;font-weight:600; }}
    QPushButton:hover, QToolButton:hover {{ background:{c['tab_hover']}; color:{c['tab_hover_fg']}; }}
    QPushButton:disabled, QToolButton:disabled {{ background:{c['alt']};
        color:{c['alt_fg']}; border-color:{c['border']}; }}
    QPushButton#btnPrimary {{ background:{c['btn_bg']};color:{c['btn_fg']};border-color:{c['btn_bg']}; }}
    QPushButton#btnPrimary:hover {{ background:{c['btn_hover']}; color:{c['btn_fg']}; }}
    QPushButton#btnAction, QPushButton#btnSuccess {{ background:{c['success_bg']};color:{c['success_fg']};
        border-color:{c['success_bg']}; }}
    QPushButton#btnAction:hover, QPushButton#btnSuccess:hover {{ background:{c['success_hover']}; color:{c['success_hover_fg']}; }}
    QPushButton#btnDanger {{ background:{c['danger_bg']};color:{c['danger_fg']};border-color:{c['danger_bg']}; }}
    QPushButton#btnDanger:hover {{ background:{c['danger_hover']};color:{c['danger_hover_fg']}; }}
    QPushButton#btnInfo {{ background:{c['info_bg']};color:{c['info_fg']};border-color:{c['info_bg']}; }}
    QPushButton#btnInfo:hover {{ background:{c['info_hover']};color:{c['info_hover_fg']}; }}
    QLineEdit, QTextEdit, QPlainTextEdit, QDateEdit, QTimeEdit, QDateTimeEdit,
    QComboBox, QSpinBox, QDoubleSpinBox {{ background:{c['field']};color:{c['field_fg']};
        border:1px solid {c['border']};border-radius:6px;padding:5px 8px;
        selection-background-color:{c['selected']}; selection-color:{c['selected_fg']}; }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
    QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border:2px solid {c['primary']}; }}
    QComboBox QAbstractItemView {{ background:{c['field']};color:{c['field_fg']};
        selection-background-color:{c['selected']};selection-color:{c['selected_fg']}; }}
    QTableWidget, QTableView, QListWidget, QTreeWidget, QListView, QTreeView {{
        background:{c['surface']};color:{c['surface_fg']};alternate-background-color:{c['alt']};
        gridline-color:{c['border']};selection-background-color:{c['selected']};
        selection-color:{c['selected_fg']};border:1px solid {c['border']}; }}
    QTableWidget::item:hover, QTableView::item:hover, QListWidget::item:hover,
    QTreeWidget::item:hover {{background:{c['tab_hover']};color:{c['tab_hover_fg']};}}
    QHeaderView::section {{ background:{c['alt']};color:{c['alt_fg']};font-weight:600;
        border-bottom:1px solid {c['border']};padding:5px; }}
    QMenu {{background:{c['surface']};color:{c['surface_fg']};border:1px solid {c['border']};}}
    QMenu::item:selected {{background:{c['selected']};color:{c['selected_fg']};}}
    QToolTip {{background:{c['surface']};color:{c['surface_fg']};border:1px solid {c['border']};}}
    {scrollbar_qss(_mix(c['surface'], c['bg'], .60), c['surface_fg'], c['primary'], appset.ayar_get('tema_scrollbar', 12))}
    """
