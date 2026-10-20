# -*- coding: utf-8 -*-
"""V3.5.70: read-only alignment of proven coaching decisions with the EXISTING weekly planner.

No new calendar, PDF, assignment or profile. The only possible change is a
teacher-approved *transient* topic ordering in the established v35 mechanism.
Clinical/learning checks are ALWAYS informational, never new homework.
"""
from __future__ import annotations

from datetime import date
from services.weekly_topic_priority_v35 import accepted_topic_pairs

_ALLOWED_KINDS = frozenset({
    'TARGETED_REVIEW', 'INDEPENDENT_RECHECK', 'CLARIFY_OBSERVATION',
    'SPACED_RETRIEVAL', 'INTERVENTION_FOLLOWUP', 'OPTIONAL_INDEPENDENT_CHECK',
})


def align_coaching_to_existing_week(cycle: dict, student_id: int,
                                    homework_list: list[dict], *, today: date) -> dict:
    """Return bounded, uncommitted lesson/topic priorities and measurement notes.

    TARGETED_REVIEW is the only step that can create a proposed priority for an
    ALREADY ASSIGNED lesson/topic, subject to separate teacher confirmation.
    All other kinds remain *measurement-only* notes. The schedule never gains
    additional tasks or time from this bridge.
    """
    if type(student_id) is not int or student_id <= 0 or type(today) is not date:
        raise ValueError('Geçerli öğrenci ve tarih gerekir.')
    result = {'schema': 'weekly_coaching_alignment_v3570', 'student_id': student_id,
              'as_of': today.isoformat(), 'state': 'NO_ACTION',
              'focus_candidates': [], 'measurement_notes': [],
              'read_only': True, 'teacher_approval_required': True,
              'auto_assignment': False, 'auto_calendar_write': False,
              'auto_pdf_change': False, 'homework_is_not_mastery': True}
    if (not isinstance(cycle, dict) or cycle.get('schema') != 'automatic_coaching_cycle_v3565'
        or type(cycle.get('student_id')) is not int or cycle['student_id'] != student_id
        or cycle.get('as_of') != today.isoformat()
        or cycle.get('read_only') is not True
        or cycle.get('teacher_approval_required') is not True
        or cycle.get('auto_change_allowed') is not False
        or cycle.get('automatic_assignments') is not False
        or cycle.get('automatic_messages') is not False
        or cycle.get('homework_is_not_mastery') is not True
        or cycle.get('mastery_verified') is not False
        or cycle.get('state') not in ('ACTION_SUGGESTED', 'NO_PRIORITY')
        or not isinstance(cycle.get('next_actions'), list)):
        return {**result, 'state': 'DATA_REVIEW'}
    actions = cycle['next_actions']
    if len(actions) > 3 or (cycle['state'] == 'NO_PRIORITY' and actions):
        return {**result, 'state': 'DATA_REVIEW'}
    proposals, notes = [], []
    for action in actions:
        if (not isinstance(action, dict) or action.get('kind') not in _ALLOWED_KINDS
            or action.get('read_only') is not True
            or action.get('teacher_approval_required') is not True
            or action.get('auto_assignment') is not False
            or action.get('auto_message') is not False
            or action.get('causality_verified') is not False
            or action.get('mastery_verified') is not False):
            return {**result, 'state': 'DATA_REVIEW'}
        kind = action['kind']
        lesson, topic = action.get('lesson'), action.get('topic')
        if (not isinstance(lesson, str) or not isinstance(topic, str)
            or len(lesson) > 90 or len(topic) > 140):
            return {**result, 'state': 'DATA_REVIEW'}
        lesson, topic = lesson.strip(), topic.strip()
        if not lesson or not topic:
            # An aggregate missing measurement cannot target a real topic.
            if kind == 'OPTIONAL_INDEPENDENT_CHECK' and not lesson and not topic:
                continue
            return {**result, 'state': 'DATA_REVIEW'}
        if kind == 'TARGETED_REVIEW':
            proposals.append({'lesson': lesson, 'topic': topic})
        else:
            label = ('Müdahale sonrası bağımsız kontrol' if kind == 'INTERVENTION_FOLLOWUP'
                     else 'Aralıklı hatırlama kontrolü' if kind == 'SPACED_RETRIEVAL'
                     else 'Kısa öğrenme/yanlış kontrolü')
            notes.append({'lesson': lesson, 'topic': topic, 'label': label})
    if not isinstance(homework_list, list):
        return {**result, 'state': 'DATA_REVIEW'}
    approved = accepted_topic_pairs(homework_list, proposals)
    # Never infer an unassigned lesson or invent a book or subskill.
    # Weekly dialog concerns the *already given* homework only. Even a valid
    # measurement of another topic must not be presented as a weekly-plan task.
    note_pairs = accepted_topic_pairs(homework_list, notes)
    def _pair(value):
        import unicodedata
        return unicodedata.normalize('NFC', value.strip()).translate(
            str.maketrans({'İ':'i', 'I':'ı'})).lower()
    approved_note_pairs = {(_pair(p['lesson']), _pair(p['topic'])) for p in note_pairs}
    unique_notes = []
    for note in notes:
        if (_pair(note['lesson']), _pair(note['topic'])) not in approved_note_pairs:
            continue
        if len(unique_notes) >= 3:
            break
        k = (note['lesson'], note['topic'], note['label'])
        if not any((n['lesson'], n['topic'], n['label']) == k for n in unique_notes):
            unique_notes.append(note)
    return {**result,
            'state': 'REVIEW_AVAILABLE' if approved or unique_notes else 'NO_ACTION',
            'focus_candidates': approved[:3], 'measurement_notes': unique_notes}
