# -*- coding: utf-8 -*-
"""V39: idempotent, display-only styling of Qt context/dropdown menus.

Qt menus often inherit a parent stylesheet like ``background:#fff`` while
retaining white font colors from the active dark theme.  Applying both colors
on the menu itself fixes the contrast without touching its QAction objects,
triggered signals, enabled states, keyboard shortcuts or menu position.

Set widget property ``_v39_preserve_menu_style`` to True to explicitly opt
out for a menu intentionally painted by a specialized component.
"""
from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtWidgets import QApplication, QMenu
from ui.theme import readable_text, _mix
from ui.theme_tokens_v37 import semantic_palette

_ORIGINAL = '_v39_original_popup_qss'
_SUFFIX = '_v39_applied_popup_qss'
_OPTOUT = '_v39_preserve_menu_style'


def menu_palette():
    p = semantic_palette()
    bg = p['surface']
    fg = readable_text(bg, p['surface_fg'])
    selected = p['selected']
    selected_fg = readable_text(selected, p['selected_fg'])
    border = p['border']
    disabled_bg = _mix(bg, p['fg'], 0.045 if not p['dark'] else 0.10)
    # Muted, but still readable (disabled controls should remain identifiable).
    disabled_fg = readable_text(disabled_bg, _mix(fg, disabled_bg, 0.28))
    return {
        'bg': bg, 'fg': fg, 'selected': selected, 'selected_fg': selected_fg,
        'border': border, 'disabled_bg': disabled_bg,
        'disabled_fg': disabled_fg,
    }


def menu_qss():
    c = menu_palette()
    return f"""
    QMenu {{ background:{c['bg']}; color:{c['fg']}; border:1px solid {c['border']}; }}
    QMenu::item {{ color:{c['fg']}; }}
    QMenu::item:selected {{ background:{c['selected']}; color:{c['selected_fg']}; }}
    QMenu::item:disabled {{ background:{c['bg']}; color:{c['disabled_fg']}; }}
    QMenu::item:selected:disabled {{ background:{c['disabled_bg']}; color:{c['disabled_fg']}; }}
    QMenu::separator {{ background:{c['border']}; }}
    """


def style_popup_menu(widget):
    if not isinstance(widget, QMenu) or widget.property(_OPTOUT) is True:
        return False
    original = widget.property(_ORIGINAL)
    # Keep authored spacing, fonts, margins and non-color rules.  Appending only
    # foreground/background declarations avoids changing QAction semantics.
    if original is None:
        original = widget.styleSheet()
        widget.setProperty(_ORIGINAL, original)
    last_applied = widget.property(_SUFFIX)
    current = widget.styleSheet()
    # A component may deliberately set a NEW QSS after we themed it: do not
    # discard it on next theme switch.  Always rebuild from the actual new CSS.
    if last_applied is not None and current != last_applied:
        original = current
        widget.setProperty(_ORIGINAL, original)
    qss = (original + '\n' if original else '') + menu_qss()
    if current != qss:
        widget.setStyleSheet(qss)
    widget.setProperty(_SUFFIX, qss)
    return True


class _ThemeMenuGuard(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QMenu):
            try:
                style_popup_menu(watched)
            except Exception:
                pass  # No popup theme issue may block a menu from opening.
        return False


def install_popup_menu_guard(app):
    if not isinstance(app, QApplication):
        return
    guard = getattr(app, '_theme_menu_guard_v39', None)
    if guard is None:
        guard = _ThemeMenuGuard(app)
        app.installEventFilter(guard)
        app._theme_menu_guard_v39 = guard
    refresh_open_popup_menus(app)


def refresh_open_popup_menus(app):
    if not isinstance(app, QApplication):
        return
    for w in app.topLevelWidgets():
        if isinstance(w, QMenu):
            try:
                style_popup_menu(w)
            except Exception:
                continue
