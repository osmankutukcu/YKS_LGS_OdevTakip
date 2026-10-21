# -*- coding: utf-8 -*-
"""V3.5.94 – bounded, student-scoped *navigation*, not assignment.

No writes, no remote services and no inferred interventions. Opening the
existing forms is the teacher's explicit next action.
"""
from __future__ import annotations
from dataclasses import dataclass
import time

ALLOWED_DESTINATIONS = frozenset(('coaching', 'weekly'))
MAX_AGE_SECONDS = 120


@dataclass(frozen=True)
class NavigationIntent:
    destination: str
    student_id: int
    issued_at: float


def valid_active_student(con, student_id: int) -> bool:
    if type(student_id) is not int or student_id <= 0:
        return False
    try:
        cols = {str(row[1]) for row in con.execute('PRAGMA table_info(ogrenci)')}
        if not {'id', 'ad', 'soyad'} <= cols:
            return False
        condition = 'AND COALESCE(aktif,1)=1' if 'aktif' in cols else ''
        row = con.execute('SELECT id FROM ogrenci WHERE id=? ' + condition,
                          (student_id,)).fetchone()
        return row is not None and type(row[0]) is int and row[0] == student_id
    except Exception:
        return False


def issue_navigation(con, destination: str, student_id: int, *,
                     selected_student_id: int) -> NavigationIntent:
    """Issue only for the currently selected, still-active student."""
    if (type(destination) is not str or destination not in ALLOWED_DESTINATIONS or
            type(selected_student_id) is not int or
            type(student_id) is not int or
            student_id != selected_student_id or
            not valid_active_student(con, student_id)):
        raise ValueError('Geçiş için öğrenci kaydı veya hedef doğrulanamadı.')
    return NavigationIntent(destination, student_id, time.monotonic())


def verify_navigation(con, intent: NavigationIntent, *, now: float | None = None) -> bool:
    """Verify again right before opening the legacy form (fail closed)."""
    if type(intent) is not NavigationIntent:
        return False
    instant = time.monotonic() if now is None else now
    if (type(intent.destination) is not str or
            intent.destination not in ALLOWED_DESTINATIONS or
            type(intent.issued_at) not in (float, int) or
            type(instant) not in (float, int) or
            not (0 <= instant - intent.issued_at <= MAX_AGE_SECONDS)):
        return False
    return valid_active_student(con, intent.student_id)
