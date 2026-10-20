# -*- coding: utf-8 -*-
"""KoçPilot 360 / 3.5.61: opt-in, read-only academic evidence coordination.

Combines EXISTING academic action + coaching snapshot readers.  It does not
introduce another score, infer knowledge from completed homework, modify
homework, send messages, or register any UI or DB hooks.  Read within a
caller-managed coherent SQLite read transaction; for real deployments use a
read-only connection, a background worker, and bound runtimes.
"""
from __future__ import annotations

from datetime import date, datetime
import sqlite3

from services.academic_actions_v3536 import read_student_action_card
from services.coaching_integration_guard_v3560 import read_coaching_snapshot

_LINK_REVIEW = 'LINK_REVIEW'
_REVIEW = 'Öğrenci–ödev bağlantıları tutarsız olabilir. Önce Denetim ekranında kontrol edin.'
_UNVERIFIED = 'Koçluk kanıtlarından biri güvenilir biçimde okunamadı. Kayıtları kontrol edin.'
_SOURCE_KEYS = ('academic_actions_v3536', 'shared_academic_decision_v3530')


def _student_id(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError('Valid positive student ID required')
    return value


def _read_source(reader, con, sid, day):
    try:
        item = reader(con, sid, today=day)
    except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError, RuntimeError):
        return None, 'UNVERIFIED'
    if not isinstance(item, dict) or item.get('student_id') != sid:
        return None, 'IDENTITY_MISMATCH'
    return item, str(item.get('state') or 'UNVERIFIED')


def read_coaching_evidence_hub(con: sqlite3.Connection, student_id: int, *,
                               today: date | None = None) -> dict:
    """Return one conservative action for a verified student, without writes.

    Strictly read-only but the caller MUST supply a SQLite connection to a
    coherent snapshot. If any source cannot be verified, do not advertise a
    learning outcome or automatically promote a competing suggestion.
    """
    sid = _student_id(student_id)
    day = today or date.today()
    if not isinstance(day, date) or isinstance(day, datetime):
        raise ValueError('today must be a date')

    old_row_factory = con.row_factory
    try:
        action, action_state = _read_source(read_student_action_card, con, sid, day)
        coaching, coaching_state = _read_source(read_coaching_snapshot, con, sid, day)
    finally:
        # Preserve the caller's cursor format, even on an old reader's failure.
        con.row_factory = old_row_factory

    summary = coaching.get('academic_card') if coaching else None
    if not isinstance(summary, dict) or summary.get('student_id') != sid:
        if isinstance(summary, dict) and summary.get('student_id') not in (None, sid):
            coaching_state = 'IDENTITY_MISMATCH'
        elif coaching_state not in ('IDENTITY_MISMATCH', _LINK_REVIEW):
            coaching_state = 'UNVERIFIED'
        summary = None
    elif summary.get('state') == _LINK_REVIEW:
        coaching_state = _LINK_REVIEW
    elif summary.get('state'):
        coaching_state = str(summary['state'])

    home = action.get('homework') if action else None
    if isinstance(home, dict) and home.get('student_id') != sid:
        action_state = 'IDENTITY_MISMATCH'
    if isinstance(home, dict) and home.get('state') == _LINK_REVIEW:
        action_state = _LINK_REVIEW

    source_states = dict(zip(_SOURCE_KEYS, (action_state, coaching_state)))
    base = {
        'schema': 'coaching_evidence_hub_v3561',
        'student_id': sid,
        'as_of': day.isoformat(),
        'sources': source_states,
        'read_only': True,
        'auto_change_allowed': False,
        'requires_teacher_approval': True,
        'homework_is_not_mastery': True,
        'weekly_calendar_verified': False,
        'remote_data_verified': False,
    }
    if _LINK_REVIEW in source_states.values():
        return {**base, 'state': _LINK_REVIEW, 'priority': 'DATA_REVIEW',
                'next_step': _REVIEW, 'basis': 'Öğrenci–ödev sahipliği doğrulaması',
                'evidence_level': 'BLOCKED', 'suggestions': []}
    if 'IDENTITY_MISMATCH' in source_states.values():
        return {**base, 'state': 'IDENTITY_MISMATCH', 'priority': 'DATA_REVIEW',
                'next_step': 'Kaynaklar farklı öğrenci döndürdü; öğrenci kimliğini doğrulayın.',
                'basis': 'Kaynak öğrenci kimliği uyumsuzluğu',
                'evidence_level': 'BLOCKED', 'suggestions': []}
    if not action or not summary or action_state == 'UNVERIFIED' or coaching_state == 'UNVERIFIED':
        return {**base, 'state': 'UNVERIFIED', 'priority': 'DATA_REVIEW',
                'next_step': _UNVERIFIED, 'basis': 'Eksik veya okunamayan kanıt kaynağı',
                'evidence_level': 'UNVERIFIED', 'suggestions': []}

    # Priority is decided from existing reader states, never invented scores.
    # Student-owned overdue tasks supersede generic plan reminders.
    # Merge generic duplicate planning suggestions from the two readers.
    overdue = home.get('overdue_open_tasks') if isinstance(home, dict) else None
    if action_state == 'HOMEWORK_FOLLOWUP' and type(overdue) is int and overdue > 0:
        kind, priority, step = 'HOMEWORK_FOLLOWUP', 'HOMEWORK_REVIEW', action.get('next_step', '')
        basis = action.get('basis', '')
        evidence = 'VERIFIED_LOCAL_HOMEWORK'
    elif action_state == 'PARTIAL_COVERAGE':
        kind, priority, step = 'PARTIAL_COVERAGE', 'DATA_REVIEW', action.get('next_step', '')
        basis, evidence = action.get('basis', ''), 'INCOMPLETE_LOCAL_HOMEWORK'
    elif action_state == 'PLAN_REVIEW':
        kind, priority, step = 'PLAN_REVIEW', 'PLAN_REVIEW', action.get('next_step', '')
        basis, evidence = action.get('basis', ''), 'LOCAL_COACHING_PLAN'
    elif coaching_state in ('RECOMMENDATION', 'PLAN_REVIEW', 'PLAN_SUGGESTION'):
        kind, priority, step = coaching_state, 'ACADEMIC_REVIEW' if coaching_state == 'RECOMMENDATION' else 'PLAN_REVIEW', summary.get('next_step', '')
        basis, evidence = summary.get('basis', ''), 'EXISTING_COACH_EVIDENCE'
    elif action_state == 'NO_VERIFIED_PRIORITY' and coaching_state == 'NO_PRIORITY':
        kind, priority, step = 'NO_VERIFIED_PRIORITY', 'ROUTINE', action.get('next_step', '')
        basis, evidence = action.get('basis', ''), 'LOCAL_RECORDS_ONLY'
    else:
        # Unexpected combinations are not treated as a healthy student.
        kind, priority, step = 'REVIEW', 'DATA_REVIEW', 'Modüller farklı durumlar gösteriyor; kayıtları birlikte inceleyin.'
        basis, evidence = 'Modüller arası durum denetimi', 'UNVERIFIED'
    if not isinstance(step, str) or not step.strip():
        kind, priority, step = 'REVIEW', 'DATA_REVIEW', _UNVERIFIED
        evidence = 'UNVERIFIED'
    if not isinstance(basis, str):
        basis = 'Kaynak açıklaması doğrulanamadı.'
    step = step.strip()[:260]
    return {**base, 'state': kind, 'priority': priority,
            'next_step': step, 'basis': basis.strip()[:190],
            'evidence_level': evidence,
            'suggestions': [{'kind': kind, 'text': step,
                             'requires_teacher_approval': True,
                             'automatic_assignment': False}],
            'deduplicated': True}
