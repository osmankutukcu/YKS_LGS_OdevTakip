"""Optional V23.8 curriculum problem observer, using existing Koç Asistanı.

Only identity warnings. No silent corrections, no new database schema, no
student data in network traffic. A healthy course is completely silent.
"""
from __future__ import annotations
from contextlib import closing
from PyQt6.QtCore import QObject, QTimer, Qt
from services.coach_assistant_v1 import AssistantInsight
from services.curriculum_v238 import coverage_notice
from services.coach_assistant_v1.proactive_policy import database_stamp


def current_coverage(form):
    """Capture exactly the visible lesson and loaded student, no guessing."""
    sid = form._secili_ogrenci_id()
    loaded = getattr(form, '_loaded_student_id', None)
    if type(sid) is not int or sid <= 0 or str(sid) != str(loaded):
        return None
    index = form.tabs.currentIndex()
    if index < 0:
        return None
    td = form.tabs.tabBar().tabData(index)
    lesson = td.get('key') if isinstance(td, dict) else None
    if not isinstance(lesson, str) or not lesson:
        return None
    tables = getattr(form, '_ders_tablolari', {}) or {}
    table = tables.get(lesson)
    if table is None:
        table = next((v for k, v in tables.items() if str(k).casefold() == lesson.casefold()), None)
    if table is None:
        return None
    rows=[]
    for index in range(table.rowCount()):
        it = table.item(index, 0)
        if it is None:
            return None
        rows.append({'id': it.data(Qt.ItemDataRole.UserRole), 'konu': it.text()})
    return sid, lesson, rows


class CoverageWatch(QObject):
    def __init__(self, form, button):
        super().__init__(form)
        self.form = form
        self.button = button
        self._last_stamp = None
        self._last_context = None
        self._pending = False
        self.timer = QTimer(self)
        self.timer.setInterval(120000)
        self.timer.timeout.connect(self.check_if_changed)
        self.timer.start()
        # All original clicked/data-loading handlers complete before the delayed read.
        for widget, name in ((getattr(form,'btnGetir',None),'clicked'),
                             (getattr(form,'tabs',None),'currentChanged')):
            if widget is not None:
                getattr(widget,name).connect(self.schedule)
        self.schedule()

    def schedule(self, *_):
        if self._pending:
            return
        self._pending=True
        QTimer.singleShot(850, self._scheduled)

    def _scheduled(self):
        self._pending=False
        self.check_if_changed(force=True)

    def check_if_changed(self, *, force=False):
        assistant = getattr(getattr(self.form, '_workspace_v21', None), 'secretary', None)
        if assistant is None or not assistant.is_enabled():
            return
        if not self.form.isVisible():
            return
        context = current_coverage(self.form)
        if not context:
            return
        sid, lesson, rows = context
        try:
            from db import DB_PATH
            stamp = database_stamp(DB_PATH)
        except Exception:
            return
        key = (sid, lesson)
        if not force and stamp == self._last_stamp and key == self._last_context:
            return
        try:
            import db
            from services.curriculum_v236 import read_coverage_overview
            with closing(db.get_conn()) as con:
                overview = read_coverage_overview(con, lesson=lesson,
                    student_id=sid, general_rows=rows)
        except Exception:
            # A temporary read error must not become a false alarm.
            return
        self._last_stamp, self._last_context = stamp, key
        note_data = coverage_notice(overview, lesson)
        if note_data is None:
            return
        # Re-check student and lesson before showing; never leak an old result.
        current = current_coverage(self.form)
        if current is None or (current[0], current[1]) != key:
            return
        if getattr(assistant,'_current_sid',None) != sid:
            return
        badge='⚠️ Konu Kimliği Riski'
        note=AssistantInsight(
            title='Konu Kapsamı · Kontrol gerekiyor',
            badge=badge,
            curiosity_hook=note_data.heading,
            body_html='Yerel konu kimliği uyuşmazlığı saptandı. Konu Kapsamı ekranında sorunlu satırları inceleyebilirsiniz. Bu, resmî MEB müfredatı kontrolü değildir.',
            action_text='📚 Sorunlu konuları incele',
            target_key='curriculum_coverage',
            duration_ms=6500,
        )
        assistant._present_insight(note, source='coverage')


def attach_coverage_watch(form, button):
    if getattr(form, '_curriculum_coverage_watch_v238', None) is None:
        form._curriculum_coverage_watch_v238 = CoverageWatch(form, button)
