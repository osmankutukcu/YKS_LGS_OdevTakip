# -*- coding: utf-8 -*-
"""V38: Qt-free, accessible presentation tokens for standard notifications.

No business, dialog-answer, database, licensing, or network dependencies.
"""
from ui.theme import readable_text, _mix, _contrast_safe_background
from ui.theme_tokens_v37 import semantic_palette


def notification_palette():
    base = semantic_palette()
    bg = base['surface']
    fg = readable_text(bg, base['surface_fg'])
    soft = _mix(bg, base['fg'], 0.08 if base['dark'] else 0.035)
    selected = base['selected']
    btn = base['neutral']
    btn_fg = readable_text(btn, base['neutral_fg'])
    hover = _mix(btn, base['primary'], 0.15)
    focus = base['btn_bg']
    focus_fg = readable_text(focus, base['btn_fg'])
    focus_hover = _contrast_safe_background(base['btn_hover'], focus_fg)
    progress = base['success_bg']
    return {
        'bg': bg, 'fg': fg,
        'soft': soft, 'soft_fg': readable_text(soft, fg),
        'field': base['field'], 'field_fg': base['field_fg'],
        'border': base['border'], 'selection': selected,
        'selection_fg': readable_text(selected, base['selected_fg']),
        'btn': btn, 'btn_fg': btn_fg,
        'hover': hover, 'hover_fg': readable_text(hover, btn_fg),
        'focus': focus, 'focus_fg': focus_fg,
        'focus_hover': focus_hover,
        'disabled': base['alt'], 'disabled_fg': readable_text(base['alt'], base['alt_fg']),
        'progress': progress, 'progress_fg': readable_text(progress, base['success_fg']),
    }


def notification_qss():
    """Local styles for *standard* Qt dialogs; preserve button roles and behavior."""
    c = notification_palette()
    return f"""
    QMessageBox, QInputDialog, QProgressDialog, QErrorMessage {{
        background:{c['bg']}; color:{c['fg']};
    }}
    QMessageBox QLabel, QInputDialog QLabel, QProgressDialog QLabel,
    QErrorMessage QLabel, QMessageBox QCheckBox, QErrorMessage QCheckBox {{
        background:transparent; color:{c['fg']};
    }}
    QMessageBox QTextEdit, QMessageBox QTextBrowser, QMessageBox QPlainTextEdit,
    QErrorMessage QTextEdit, QErrorMessage QTextBrowser, QProgressDialog QTextEdit,
    QInputDialog QLineEdit, QInputDialog QTextEdit, QInputDialog QPlainTextEdit,
    QInputDialog QSpinBox, QInputDialog QDoubleSpinBox, QInputDialog QComboBox {{
        background:{c['field']}; color:{c['field_fg']};
        border:1px solid {c['border']}; border-radius:5px; padding:5px 7px;
        selection-background-color:{c['selection']};
        selection-color:{c['selection_fg']};
    }}
    QInputDialog QComboBox QAbstractItemView {{
        background:{c['field']}; color:{c['field_fg']};
        selection-background-color:{c['selection']};
        selection-color:{c['selection_fg']};
    }}
    QMessageBox QPushButton, QInputDialog QPushButton,
    QProgressDialog QPushButton, QErrorMessage QPushButton {{
        background:{c['btn']}; color:{c['btn_fg']};
        border:1px solid {c['border']}; border-radius:6px;
        min-width:82px; padding:6px 13px;
    }}
    QMessageBox QPushButton:hover, QInputDialog QPushButton:hover,
    QProgressDialog QPushButton:hover, QErrorMessage QPushButton:hover {{
        background:{c['hover']}; color:{c['hover_fg']};
    }}
    QMessageBox QPushButton:default, QInputDialog QPushButton:default,
    QProgressDialog QPushButton:default, QErrorMessage QPushButton:default {{
        background:{c['focus']}; color:{c['focus_fg']};
        border-color:{c['focus']};
    }}
    QMessageBox QPushButton:default:hover, QInputDialog QPushButton:default:hover,
    QProgressDialog QPushButton:default:hover, QErrorMessage QPushButton:default:hover {{
        background:{c['focus_hover']}; color:{c['focus_fg']};
    }}
    QMessageBox QPushButton:disabled, QInputDialog QPushButton:disabled,
    QProgressDialog QPushButton:disabled, QErrorMessage QPushButton:disabled {{
        background:{c['disabled']}; color:{c['disabled_fg']};
        border-color:{c['border']};
    }}
    QProgressDialog QProgressBar {{
        background:{c['soft']}; color:{c['soft_fg']};
        border:1px solid {c['border']}; text-align:center;
        border-radius:5px;
    }}
    QProgressDialog QProgressBar::chunk {{
        background:{c['progress']};
    }}
    """


def toast_colors(kind, custom_background=None):
    """Status colors are stable between themes; text remains readable."""
    backgrounds = {
        'info': '#2563EB', 'success': '#15803D',
        'warn': '#EAB308', 'error': '#B91C1C',
    }
    bg = custom_background or backgrounds.get(kind, backgrounds['info'])
    return bg, readable_text(bg, '#FFFFFF')
