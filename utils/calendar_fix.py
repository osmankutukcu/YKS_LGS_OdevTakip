# utils/calendar_fix.py
# -*- coding: utf-8 -*-
"""
PyQt6 Takvim Fix (stabil & kompakt)
- Tüm QDateEdit / QDateTimeEdit takvimlerini tek yerden düzenler.
- Türkçe yerel ayar, Pazartesi haftabaşı, kısa gün adları, ızgara çizgisi.
- Aynı editöre tekrar tekrar kurulum yapmaz (flag ile korunur).
Kullanım:
    from utils.calendar_fix import install_calendar_fix, attach_calendar_to
    install_calendar_fix(QApplication.instance(), main_window,
                         show_week_numbers=False, weekend_color="#e11d48")
"""

from typing import Optional, Dict, Any, Union

from PyQt6.QtCore import QObject, QEvent, Qt, QLocale, QDate, QSize, QTimer
from PyQt6.QtWidgets import (
    QApplication, QCalendarWidget, QDateEdit, QDateTimeEdit
)

# ------------------------- Basit stil -------------------------
_CAL_QSS = """
QCalendarWidget {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: #f5f7fa;
    border-bottom: 1px solid #e5e7eb;
    padding: 4px;
}
QCalendarWidget QToolButton {
    border: none;
    padding: 4px 10px;
    font-weight: 600;
    min-height: 24px;
}
QCalendarWidget QToolButton:hover { background: #e9eef5; border-radius: 6px; }
#qt_calendar_monthbutton, #qt_calendar_yearbutton { min-width: 110px; }
QCalendarWidget QTableView {
    selection-background-color: #e3f2fd;
    gridline-color: #e5e7eb;
    outline: none;
    font-size: 14px;
}
QCalendarWidget QTableView QHeaderView::section {
    background: #ffffff;
    border: none;
    padding: 6px 2px;
    font-weight: 600;
}
"""

_TR_LOCALE = QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey)

# ------------------------------ Yardımcılar ------------------------------
def _apply_weekend_colors(cal: QCalendarWidget, color_hex: str = "#e11d48") -> None:
    from PyQt6.QtGui import QColor
    fmt = cal.weekdayTextFormat(Qt.DayOfWeek.Saturday)
    fmt.setForeground(QColor(color_hex))
    cal.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, fmt)
    cal.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, fmt)

def _size_sanity(cal: QCalendarWidget) -> None:
    w = max(cal.sizeHint().width(), 320)
    h = max(cal.sizeHint().height(), 260)
    cal.setMinimumSize(QSize(w, h))

def _tune_calendar(
    cal: QCalendarWidget,
    locale: Optional[QLocale] = None,
    options: Optional[Dict[str, Any]] = None
) -> None:
    options = options or {}
    cal.setLocale(locale or _TR_LOCALE)
    cal.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
    cal.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
    cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    cal.setGridVisible(True)
    if options.get("show_week_numbers", False):
        cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)
    cal.setStyleSheet(_CAL_QSS)
    _size_sanity(cal)
    _apply_weekend_colors(cal, options.get("weekend_color", "#e11d48"))

    # Opsiyonel min/max tarih
    min_date = options.get("min_date")
    max_date = options.get("max_date")
    if isinstance(min_date, QDate):
        cal.setMinimumDate(min_date)
    if isinstance(max_date, QDate):
        cal.setMaximumDate(max_date)

class NiceCalendar(QCalendarWidget):
    def __init__(self, parent=None, locale: Optional[QLocale] = None, options: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        _tune_calendar(self, locale=locale, options=options)

    def showEvent(self, ev):
        super().showEvent(ev)
        _size_sanity(self)

def _ensure_calendar_on(
    editor: Union[QDateEdit, QDateTimeEdit],
    locale: Optional[QLocale],
    options: Optional[Dict[str, Any]]
) -> None:
    """Editöre takvim uygula; daha önce yapıldıysa tekrar yapma."""
    if getattr(editor, "_nice_cal_ok", False):
        return

    editor.setCalendarPopup(True)
    cal = editor.calendarWidget()
    if cal is None or not isinstance(cal, QCalendarWidget):
        cal = NiceCalendar(editor, locale=locale or _TR_LOCALE, options=options)
        editor.setCalendarWidget(cal)
    else:
        _tune_calendar(cal, locale=locale or _TR_LOCALE, options=options)

    # Görüntü biçimi boşsa Türkçe format ata
    if isinstance(editor, QDateEdit) and not editor.displayFormat():
        editor.setDisplayFormat("d.M.yyyy")
    elif isinstance(editor, QDateTimeEdit) and not editor.displayFormat():
        editor.setDisplayFormat("d.M.yyyy HH:mm")

    # Tek sefer kuruldu işareti
    setattr(editor, "_nice_cal_ok", True)

# --------------------------- Kurulum sınıfı ---------------------------
class _CalendarInstaller(QObject):
    """Uygulama genelinde otomatik kurulum (tek sefer)."""
    def __init__(self, app: QApplication, root_widget, locale: Optional[QLocale], options: Dict[str, Any]):
        super().__init__(root_widget)
        self._app = app
        self._locale = locale or _TR_LOCALE
        self._options = options or {}
        self._in_event = False  # reentrancy kilidi
        app.installEventFilter(self)
        self.apply_to_existing(root_widget)

    def apply_to_existing(self, root_widget):
        if not root_widget:
            return
        for w in root_widget.findChildren(QDateEdit):
            _ensure_calendar_on(w, self._locale, self._options)
        for w in root_widget.findChildren(QDateTimeEdit):
            _ensure_calendar_on(w, self._locale, self._options)

    def eventFilter(self, obj, ev):
        try:
            # Sadece gerçek odak girişlerinde, doğrudan olayı alan nesne üzerinden çalış.
            if ev.type() == QEvent.Type.FocusIn:
                # Reentrancy kilidi: aynı odak dalgasında tekrar girmeyelim
                if self._in_event:
                    return False
                self._in_event = True
                try:
                    # Olayı alan nesne (obj) editör mü?
                    if isinstance(obj, (QDateEdit, QDateTimeEdit)):
                        # Zaten kuruluysa hiçbir şey yapma
                        if getattr(obj, "_nice_cal_ok", False):
                            return False
                        # Aynı odak dalgasında birden fazla kez kuyruğa girme
                        if getattr(obj, "_nice_cal_scheduled", False):
                            return False
                        setattr(obj, "_nice_cal_scheduled", True)

                        def _apply_once(target=obj):
                            try:
                                # Target hâlâ yaşıyor ve editör tipinde mi?
                                if isinstance(target, (QDateEdit, QDateTimeEdit)):
                                    _ensure_calendar_on(target, self._locale, self._options)
                            finally:
                                try:
                                    setattr(target, "_nice_cal_scheduled", False)
                                except Exception:
                                    pass

                        # GUI boşaldığında bir kere çalıştır
                        QTimer.singleShot(0, _apply_once)
                finally:
                    self._in_event = False
        except (KeyboardInterrupt, Exception):
            pass

        return False  # olayı yaymaya devam et

# ------------------------------- Dış API -------------------------------
def install_calendar_fix(app: QApplication, root_widget, locale: Optional[QLocale] = None, **options) -> None:
    """App geneli kurulum (idempotent)."""
    if not isinstance(app, QApplication):
        return
    if getattr(app, "_calendar_fix_installed", False):
        inst: Optional[_CalendarInstaller] = getattr(app, "_calendar_fix_instance", None)
        if inst:
            inst.apply_to_existing(root_widget)
        return
    app._calendar_fix_installed = True
    app._calendar_fix_instance = _CalendarInstaller(app, root_widget, locale or _TR_LOCALE, options or {})

def attach_calendar_to(editor: Union[QDateEdit, QDateTimeEdit], locale: Optional[QLocale] = None, **options) -> None:
    """Yalnızca tek bir alan için kurulum."""
    _ensure_calendar_on(editor, locale or _TR_LOCALE, options or {})
