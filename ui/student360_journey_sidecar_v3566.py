# -*- coding: utf-8 -*-
"""Optional non-blocking Student 360 cycle view; unchanged Student 360 layout.

Loads asynchronously from SQLite query-only snapshot, never from UI thread.
Student identity and generation are checked again before displaying a result.
"""
from __future__ import annotations
from contextlib import closing
from datetime import date
import sqlite3
import time
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, QSettings


class _Signals(QObject):
    ready = pyqtSignal(int, int, object)


class _Job(QRunnable):
    def __init__(self, serial, sid):
        super().__init__()
        self.serial, self.sid = serial, sid
        self.signals = _Signals()

    def run(self):
        summary = None
        try:
            from db import DB_PATH
            from services.automatic_coaching_cycle_v3565 import read_automatic_coaching_cycle
            from services.coaching_journey_summary_v3566 import format_journey_summary
            uri = DB_PATH.resolve().as_uri() + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=1.5)) as con:
                con.execute('PRAGMA query_only=ON')
                con.execute('BEGIN')
                deadline = time.monotonic() + 2.5
                con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 2000)
                try:
                    cycle = read_automatic_coaching_cycle(con, self.sid)
                    summary = format_journey_summary(cycle, self.sid)
                    # V3.5.67: the SAME top academic action used by the
                    # Coach Assistant and the teacher strip; no extra SQL.
                    try:
                        from services.coaching_action_center_v3567 import (
                            build_action_center_card, compact_teacher_line)
                        today = date.today()  # Do not present a stale priority
                        priority = build_action_center_card(cycle, self.sid, today=today)
                        enabled = str(QSettings('EduTrack', 'HomeworkManagerV2').value(
                            'coaching_action_center_v3567_enabled', '1')).lower() not in ('0','false','off','no')
                        if enabled and priority['state'] == 'ACTION_SUGGESTED':
                            summary = (summary + '\n\nORTAK KOÇLUK ÖNCELİĞİ\n'
                                       + compact_teacher_line(priority, self.sid, today=today))
                    except (TypeError, ValueError, KeyError, ImportError):
                        pass  # Old V3566 summary survives optional V3567 faults.
                    # V3.5.72: optional teacher-approved self-report note.
                    # Reuse the same query-only snapshot and background worker.
                    try:
                        import os
                        if os.getenv('YKS_HOMEWORK_FEEDBACK_V12_ENABLED') == '1':
                            from services.homework_feedback_coaching_v3572 import (
                                read_coaching_feedback, format_student360_feedback)
                            note = format_student360_feedback(
                                read_coaching_feedback(con, self.sid), self.sid)
                            if note:
                                summary = (summary + '\n\n' + note) if summary else note
                    except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError):
                        pass
                finally:
                    con.set_progress_handler(None, 0)
                    con.rollback()
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError, ImportError):
            summary = None
        self.signals.ready.emit(self.serial, self.sid, summary)


class Student360JourneySidecarV3566(QObject):
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.serial = 0
        self.active = {}
        self.settings = QSettings('EduTrack', 'HomeworkManagerV2')

    def request(self, student_id):
        self.serial += 1
        serial = self.serial
        if type(student_id) is not int or student_id <= 0:
            return
        if str(self.settings.value('coaching_journey_v3566_enabled', '1')).lower() in ('0', 'false', 'off', 'no'):
            return
        if len(self.active) >= 2:
            return  # later manual/committed refresh can retry
        job = _Job(serial, student_id)
        self.active[serial] = job
        job.signals.ready.connect(self._result)
        QThreadPool.globalInstance().start(job)

    def _result(self, serial, sid, result):
        self.active.pop(serial, None)
        if (serial != self.serial or sid != getattr(self.panel, 'student_id', None)
            or not isinstance(result, str)
            or str(self.settings.value('coaching_journey_v3566_enabled', '1')).lower() in ('0', 'false', 'off', 'no')):
            return
        output = getattr(self.panel, 'output', None)
        if output is not None:
            output.append('\n' + result)
