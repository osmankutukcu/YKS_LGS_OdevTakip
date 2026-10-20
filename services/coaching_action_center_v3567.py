# -*- coding: utf-8 -*-
"""V3.5.67 optional common, read-only presentation contract.

Turns ONE verified V3565 coaching decision into the same priority for Coach
Assistant, Student 360 and the lightweight daily teacher strip. No SQL, no
assignments, no changing existing V10/V11 priority or checkbox semantics.
"""
from __future__ import annotations
from datetime import date

_LABELS = {
    'INTERVENTION_FOLLOWUP': 'Müdahale sonrası ölçüm',
    'TARGETED_REVIEW': 'Hedefli öğrenme kontrolü',
    'INDEPENDENT_RECHECK': 'Bağımsız yeniden yoklama',
    'CLARIFY_OBSERVATION': 'Gözlemi doğrulama',
    'SPACED_RETRIEVAL': 'Aralıklı hatırlama kontrolü',
    'OPTIONAL_INDEPENDENT_CHECK': 'İsteğe bağlı öğrenme kontrolü',
}


def _text(value, size):
    return ' '.join(value.split())[:size] if isinstance(value, str) else ''


def _empty(sid, day, state, message):
    return {
        'schema': 'coaching_action_center_v3567', 'student_id': sid,
        'as_of': day, 'state': state, 'title': '', 'area': '',
        'reason': message, 'next_step': '', 'kind': '', 'action_key': '',
        'read_only': True, 'teacher_approval_required': True,
        'auto_change_allowed': False, 'auto_assignment': False,
        'auto_message': False, 'mastery_verified': False,
        'causality_verified': False, 'source': 'automatic_coaching_cycle_v3565',
    }


def build_action_center_card(cycle: dict, student_id: int, *, today: date) -> dict:
    """Reject mixed-student, stale and unsafe payloads; never guess priorities."""
    if type(student_id) is not int or student_id <= 0 or type(today) is not date:
        raise ValueError('Doğrulanmış öğrenci ve tarih gereklidir')
    day = today.isoformat()
    fallback = _empty(student_id, day, 'DATA_REVIEW', 'Koçluk kanıtları doğrulanamadı.')
    if (not isinstance(cycle, dict)
        or cycle.get('schema') != 'automatic_coaching_cycle_v3565'
        or type(cycle.get('student_id')) is not int or cycle['student_id'] != student_id
        or cycle.get('as_of') != day
        or cycle.get('read_only') is not True
        or cycle.get('teacher_approval_required') is not True
        or cycle.get('auto_change_allowed') is not False
        or cycle.get('automatic_assignments') is not False
        or cycle.get('automatic_messages') is not False
        or cycle.get('homework_is_not_mastery') is not True
        or cycle.get('mastery_verified') is not False
        or cycle.get('causality_verified') is not False):
        return fallback
    state = cycle.get('state')
    if state == 'DATA_REVIEW':
        return _empty(student_id, day, 'DATA_REVIEW', 'Önce akademik kayıtların öğrenci ve kaynak eşleşmesini inceleyin.')
    if state == 'NO_PRIORITY':
        if cycle.get('next_actions') != []:
            return fallback
        return _empty(student_id, day, 'NO_PRIORITY',
                      'Bugün doğrulanmış yeni öncelik bulunmadı; öğrenme kanıtlanmış sayılmaz.')
    if state != 'ACTION_SUGGESTED':
        return fallback
    steps = cycle.get('next_actions')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 3:
        return fallback
    # Validate EVERY action before presenting the first, to prevent partially
    # trusted results from being interpreted as a verified decision.
    for step in steps:
        if (not isinstance(step, dict)
            or step.get('kind') not in _LABELS
            or step.get('read_only') is not True
            or step.get('teacher_approval_required') is not True
            or step.get('auto_assignment') is not False
            or step.get('auto_message') is not False
            or step.get('mastery_verified') is not False
            or step.get('causality_verified') is not False
            or type(step.get('priority')) is not int
            or not 0 <= step['priority'] <= 5):
            return fallback
    # Source V3565 already ranks and deduplicates actions. Do not re-rank:
    # same first action is displayed on every surface for the same snapshot.
    first = steps[0]
    lesson, topic = _text(first.get('lesson'), 90), _text(first.get('topic'), 140)
    return {
        **_empty(student_id, day, 'ACTION_SUGGESTED', _text(first.get('reason'), 300)),
        'title': _LABELS[first['kind']], 'kind': first['kind'],
        'area': ' / '.join(x for x in (lesson, topic) if x),
        'lesson': lesson, 'topic': topic,
        'next_step': _text(first.get('next_step'), 300),
        'action_key': 'btnOgrenme',  # Existing navigable learning screen only.
    }


def compact_teacher_line(card: dict, student_id: int, *, today: date) -> str:
    """Plain text, bounded, no new buttons or alerts."""
    if (not isinstance(card, dict)
        or card.get('schema') != 'coaching_action_center_v3567'
        or type(card.get('student_id')) is not int or card.get('student_id') != student_id
        or card.get('as_of') != today.isoformat()
        or card.get('read_only') is not True
        or card.get('teacher_approval_required') is not True
        or card.get('auto_change_allowed') is not False
        or card.get('auto_assignment') is not False
        or card.get('auto_message') is not False
        or card.get('mastery_verified') is not False):
        return ''
    if card.get('state') != 'ACTION_SUGGESTED' or card.get('kind') not in _LABELS:
        return ''
    return ('🧠 Koçluk önceliği: ' + _text(card.get('title'), 55)
            + (' — ' + _text(card.get('area'), 140) if card.get('area') else '')
            + '. ' + _text(card.get('next_step'), 180)
            + ' (Öğretmen onayı gerekir.)')[:430]
