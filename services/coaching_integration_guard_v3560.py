# -*- coding: utf-8 -*-
"""V3.5.60: opt-in, read-only integration guard for academic coaching.

Never writes to the database, alters homework states, or performs network I/O.
The caller owns the SQLite connection and controls when to invoke this module.
"""
from __future__ import annotations

from datetime import date
import sqlite3


def read_coaching_snapshot(con: sqlite3.Connection, student_id: int, *, today: date | None = None) -> dict:
    """Return a bounded, same-student coaching snapshot with explicit uncertainty."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('A positive integer student ID is required')
    if today is not None and not isinstance(today, date):
        raise ValueError('today must be a date')
    from services.shared_academic_decision_v3530 import read_shared_academic_card
    card = read_shared_academic_card(con, student_id, today=today)
    return {
        'student_id': student_id,
        'source': 'shared_academic_decision_v3530',
        'read_only': True,
        'state': str(card.get('state') or 'UNVERIFIED'),
        'academic_card': card,
        'disclaimer': 'Ödevin tamamlanması tek başına öğrenme kanıtı değildir.',
    }
