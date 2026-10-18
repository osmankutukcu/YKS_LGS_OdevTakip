# -*- coding: utf-8 -*-
"""V3.5.29 evidence-constrained next-step decisions for the teacher.

Reuses existing coach evidence, no second scoring system, no new assignments,
no messages and no automatic mastery judgments. Never guesses a student ID.
"""
from __future__ import annotations

from datetime import date
import sqlite3


def _student_has_ownership_conflict(con: sqlite3.Connection, sid: int) -> bool:
    """Do not advise from a learner's records when link ownership conflicts."""
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'ogrenci' not in names:
        return True
    if 'odev_kume' in names:
        owner = {r[1] for r in con.execute('PRAGMA table_info(odev_kume)')}
        if 'ogrenci_id' in owner:
            for table in ('odev', 'odev_satir'):
                if table not in names:
                    continue
                cols = {r[1] for r in con.execute(f'PRAGMA table_info({table})')}
                if {'kume_id', 'ogrenci_id'} <= cols:
                    # A dangling group link cannot be validated as belonging to sid.
                    missing = con.execute(f'''SELECT 1 FROM {table} t
                        LEFT JOIN odev_kume k ON k.id=t.kume_id
                        WHERE t.ogrenci_id=? AND t.kume_id IS NOT NULL
                          AND k.id IS NULL LIMIT 1''', (sid,)).fetchone()
                    if missing:
                        return True
                    x = con.execute(f'''SELECT 1 FROM {table} t
                        JOIN odev_kume k ON k.id=t.kume_id
                        WHERE t.ogrenci_id=? AND k.ogrenci_id IS NOT NULL
                          AND k.ogrenci_id<>t.ogrenci_id LIMIT 1''', (sid,)).fetchone()
                    if x:
                        return True
    if {'odev_satir', 'odev'} <= names:
        a = {r[1] for r in con.execute('PRAGMA table_info(odev_satir)')}
        b = {r[1] for r in con.execute('PRAGMA table_info(odev)')}
        if {'odev_id', 'ogrenci_id'} <= a and 'ogrenci_id' in b:
            missing = con.execute('''SELECT 1 FROM odev_satir s
                LEFT JOIN odev o ON o.id=s.odev_id
                WHERE s.ogrenci_id=? AND s.odev_id IS NOT NULL
                  AND o.id IS NULL LIMIT 1''', (sid,)).fetchone()
            if missing:
                return True
            x = con.execute('''SELECT 1 FROM odev_satir s JOIN odev o ON o.id=s.odev_id
                WHERE s.ogrenci_id=? AND o.ogrenci_id IS NOT NULL
                  AND s.ogrenci_id<>o.ogrenci_id LIMIT 1''', (sid,)).fetchone()
            if x:
                return True
    return False


def read_academic_next_step(con: sqlite3.Connection, student_id: int, *,
                            today: date | None = None) -> dict | None:
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('A verified student ID is required')
    from services.coach_evidence_v5 import build_coach_brief
    if _student_has_ownership_conflict(con, student_id):
        return None
    report = build_coach_brief(con, student_id, as_of=today, max_actions=5)
    options = [action for action in report.get('actions', ()) if action.get('kind') in
               ('overdue', 'homework_review', 'exam_follow_up') and action.get('requires_approval') is True]
    if not options:
        return None
    rank = {'overdue': 0, 'exam_follow_up': 1, 'homework_review': 2}
    chosen = min(enumerate(options), key=lambda pair: (rank[pair[1]['kind']], pair[0]))[1]
    return {
        'student_id': student_id,
        'kind': str(chosen['kind']),
        'next_step': str(chosen['text'])[:260],
        'basis': str(chosen['source'])[:180],
        'evidence': str(chosen['confidence'])[:110],
        'requires_approval': True,
        'scope': 'registered_homework_and_comparable_exams_only',
        'not_mastery_diagnosis': True,
        'no_automatic_change': True,
    }
