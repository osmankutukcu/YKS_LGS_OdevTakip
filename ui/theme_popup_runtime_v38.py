# -*- coding: utf-8 -*-
"""Opt-in-at-application-start guard for standard Qt message/notification dialogs.

A QEvent.Show filter covers QMessageBox.information/warning/question/critical
without replacing or monkeypatching their APIs. No changes to button roles,
modal state, timeouts, return codes or signal connections.
"""
from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtWidgets import QApplication, QMessageBox, QInputDialog, QProgressDialog, QErrorMessage
from ui.theme_notification_tokens_v38 import notification_qss

_STANDARD_DIALOG_TYPES = (QMessageBox, QInputDialog, QProgressDialog, QErrorMessage)
_ORIGINAL_STYLE_PROPERTY = '_v38_original_notification_style'
_LAST_APPLIED_PROPERTY = '_v39_last_notification_style'


def _style_standard_dialog(widget):
    """Idempotent styling; retain developer's original local non-color styles."""
    if not isinstance(widget, _STANDARD_DIALOG_TYPES):
        return False
    original = widget.property(_ORIGINAL_STYLE_PROPERTY)
    current = widget.styleSheet()
    last_applied = widget.property(_LAST_APPLIED_PROPERTY)
    if original is None or (last_applied is not None and current != last_applied):
        # The owning dialog may update its own local CSS while visible.
        # Preserve that newer style instead of resurrecting old local CSS.
        original = current
        widget.setProperty(_ORIGINAL_STYLE_PROPERTY, original)
    effective = (original + '\n' if original else '') + notification_qss()
    if current != effective:
        widget.setStyleSheet(effective)
    widget.setProperty(_LAST_APPLIED_PROPERTY, effective)
    return True


class _NotificationThemeGuard(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, _STANDARD_DIALOG_TYPES):
            try:
                _style_standard_dialog(watched)
            except Exception:
                pass
        return False  # Never swallow a click, dialog event or keyboard event.


def install_notification_guard(app):
    """Install once and refresh already-visible standard notification dialogs."""
    if not isinstance(app, QApplication):
        return
    guard = getattr(app, '_theme_notification_guard_v38', None)
    if guard is None:
        guard = _NotificationThemeGuard(app)
        app.installEventFilter(guard)
        app._theme_notification_guard_v38 = guard  # keep QObject alive
    refresh_open_notifications(app)


def refresh_open_notifications(app):
    """Live theme switching updates open boxes without closing/reopening them."""
    if not isinstance(app, QApplication):
        return
    for widget in app.topLevelWidgets():
        if isinstance(widget, _STANDARD_DIALOG_TYPES):
            try:
                _style_standard_dialog(widget)
            except Exception:
                continue
