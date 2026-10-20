# -*- coding: utf-8 -*-
"""KoçPilot 360 v3.5.69: conservative, read-only study-plan preview.

Combines the existing V3565 ranked coaching cycle with V3564 *real*
lesson/topic/book suggestions. No due date, free time, book, score or mastery
is invented. A confirmed unallocated weekly budget is OPTIONAL: without it
no recommendation is represented as schedulable. All writes/assignments
remain under the existing teacher-approved wizard and original forms.
"""
from __future__ import annotations

from datetime import date

from services.coaching_action_center_v3567 import build_action_center_card
from utils.wizard_integrity_v8 import exact_task_key


_ALLOWED_ALIGNMENT_STATES = frozenset({
    'MATCHED', 'NO_VERIFIED_BOOK_MATCH', 'NO_LEARNING_PROPOSAL',
    'DRAFT_NOT_INITIALIZED', 'DRAFT_REVIEW', 'DATA_REVIEW',
})


def _base(sid: int, today: date, state: str, reason: str) -> dict:
    return {
        'schema': 'smart_study_plan_v3569', 'student_id': sid,
        'as_of': today.isoformat(), 'state': state, 'reason': reason[:260],
        'read_only': True, 'teacher_approval_required': True,
        'auto_assignment': False, 'auto_selection': False,
        'auto_message': False, 'auto_calendar_write': False,
        'calendar_verified': False, 'homework_is_not_mastery': True,
        'mastery_verified': False, 'causality_verified': False,
        'planning_steps': [], 'candidate_minutes': 0,
        'unallocated_minutes_verified': False,
        'limitations': 'Taslak takvime yazılmaz; öğretmen mevcut ekranlarda ayrıca onaylar.',
    }


def _text(value, limit: int) -> str:
    return ' '.join(value.split())[:limit] if isinstance(value, str) else ''


def _validate_alignment(alignment: dict, sid: int, day: str) -> bool:
    if (not isinstance(alignment, dict)
        or alignment.get('schema') != 'science_wizard_alignment_v3564'
        or type(alignment.get('student_id')) is not int
        or alignment['student_id'] != sid or alignment.get('as_of') != day
        or alignment.get('state') not in _ALLOWED_ALIGNMENT_STATES
        or alignment.get('read_only') is not True
        or alignment.get('teacher_approval_required') is not True
        or alignment.get('auto_assignment') is not False
        or alignment.get('auto_selection') is not False
        or alignment.get('requires_live_matrix_recheck') is not True
        or alignment.get('existing_wizard_unchanged') is not True
        or not isinstance(alignment.get('matched'), list)):
        return False
    matches = alignment['matched']
    if len(matches) > 2 or (alignment['state'] != 'MATCHED' and matches):
        return False
    seen = set()
    total = 0
    for item in matches:
        if (not isinstance(item, dict)
            or item.get('teacher_must_review_in_existing_wizard') is not True
            or item.get('automatic_transfer') is not False
            or type(item.get('minutes')) is not int
            or not 1 <= item['minutes'] <= 120
            or any(not _text(item.get(k), 160) for k in ('lesson', 'topic', 'existing_book'))):
            return False
        key = exact_task_key(item['lesson'], '', item['topic'])
        if key in seen:
            return False
        seen.add(key)
        total += item['minutes']
    if alignment['state'] == 'MATCHED':
        if not matches or type(alignment.get('suggested_minutes')) is not int:
            return False
        if alignment['suggested_minutes'] != total:
            return False
        if type(alignment.get('overload_limited')) is not bool:
            return False
    return True


def build_smart_study_plan(cycle: dict, alignment: dict | None, student_id: int, *,
                           today: date, verified_unallocated_minutes: int | None = None,
                           max_steps: int = 2) -> dict:
    """Build an advisory preview, never a confirmed timetable.

    verified_unallocated_minutes must be the **already net** available minutes
    provided by a caller that independently checked current assignments and
    calendar constraints. None means unknown, NOT unlimited. This release
    deliberately passes None from the UI because no shared validated budget
    snapshot is currently guaranteed.
    """
    if (type(student_id) is not int or student_id <= 0 or type(today) is not date
        or type(max_steps) is not int or not 1 <= max_steps <= 3):
        raise ValueError('Geçerli öğrenci, tarih ve öneri sınırı gerekir.')
    if (verified_unallocated_minutes is not None
        and (type(verified_unallocated_minutes) is not int
             or not 0 <= verified_unallocated_minutes <= 10080)):
        raise ValueError('Doğrulanmış kullanılabilir süre geçersiz.')
    base = _base(student_id, today, 'NO_PRIORITY', 'Bugün doğrulanmış yeni çalışma önceliği bulunmuyor.')
    card = build_action_center_card(cycle, student_id, today=today)
    if card.get('state') == 'DATA_REVIEW':
        return {**base, 'state': 'DATA_REVIEW', 'reason': 'Ortak akademik kararın öğrenci veya kaynak doğrulaması başarısız.'}
    if alignment is not None and not _validate_alignment(alignment, student_id, today.isoformat()):
        return {**base, 'state': 'DATA_REVIEW', 'reason': 'Ödev taslağında güvenli öğrenci, tarih veya içerik eşleşmesi yok.'}
    if alignment is not None and alignment['state'] in ('DATA_REVIEW', 'DRAFT_REVIEW'):
        # Do not promote a possibly mismatched book after wizard data review.
        alignment = None
    if card.get('state') != 'ACTION_SUGGESTED':
        return base

    # Reuse EXACT ranking from the V3565 cycle. Never let a lower-ranked
    # wizard match displace an overdue approved-intervention recheck.
    available = verified_unallocated_minutes
    matched = {}
    if alignment and alignment.get('state') == 'MATCHED':
        for item in alignment['matched']:
            matched[exact_task_key(item['lesson'], '', item['topic'])] = item

    steps, selected = [], set()
    for item in cycle['next_actions']:
        key = exact_task_key(_text(item.get('lesson'), 90), '', _text(item.get('topic'), 140))
        if key in selected:
            continue
        selected.add(key)
        row = matched.get(key)
        kind = item['kind']
        step = {
            'kind': 'LEARNING_REVIEW', 'source_kind': kind,
            'lesson': _text(item.get('lesson'), 90),
            'topic': _text(item.get('topic'), 140),
            'reason': _text(item.get('reason'), 260),
            'next_step': _text(item.get('next_step'), 260),
            'existing_book': '', 'candidate_minutes': 0,
            'capacity_status': 'NOT_APPLICABLE',
            'teacher_approval_required': True, 'read_only': True,
            'automatic_transfer': False, 'scheduled': False,
        }
        # An approved intervention follow-up must remain a measurement,
        # not silently become more homework from a coincidentally matched book.
        if row is not None and kind != 'INTERVENTION_FOLLOWUP':
            minutes = row['minutes']
            overloaded = alignment.get('overload_limited') is True
            if overloaded:
                step['capacity_status'] = 'OVERLOAD_REVIEW'
            elif available is None:
                step['capacity_status'] = 'UNKNOWN'
            elif minutes > available:
                step['capacity_status'] = 'INSUFFICIENT'
            else:
                step.update(kind='WIZARD_PREVIEW', existing_book=_text(row['existing_book'], 140),
                            candidate_minutes=minutes, capacity_status='VERIFIED_BUDGET_FITS')
                available -= minutes
            # Unknown budget is allowed to show a *candidate* but not a slot.
            if step['capacity_status'] == 'UNKNOWN':
                step.update(kind='WIZARD_PREVIEW', existing_book=_text(row['existing_book'], 140),
                            candidate_minutes=minutes)
            if step['kind'] == 'WIZARD_PREVIEW':
                step['next_step'] = 'Mevcut Sihirbazda kitap–konu eşleşmesini yeniden kontrol edip öğretmen onayıyla değerlendirin.'
        steps.append(step)
        if len(steps) >= max_steps:
            break
    if not steps:
        return base
    result = {**base, 'state': 'REVIEW_SUGGESTED', 'reason': steps[0]['reason'],
              'planning_steps': steps, 'candidate_minutes': sum(s['candidate_minutes'] for s in steps),
              'unallocated_minutes_verified': verified_unallocated_minutes is not None}
    return result


def compact_study_plan_hint(plan: dict, student_id: int, *, today: date,
                            expected_lesson: str = '', expected_topic: str = '') -> str:
    """Bounded plain-text addition to an already visible priority; not a new popup."""
    if (not isinstance(plan, dict) or plan.get('schema') != 'smart_study_plan_v3569'
        or plan.get('student_id') != student_id or plan.get('as_of') != today.isoformat()
        or plan.get('read_only') is not True or plan.get('teacher_approval_required') is not True
        or plan.get('auto_assignment') is not False or plan.get('auto_message') is not False
        or plan.get('auto_calendar_write') is not False or plan.get('calendar_verified') is not False
        or plan.get('state') != 'REVIEW_SUGGESTED'):
        return ''
    steps = plan.get('planning_steps')
    if not isinstance(steps, list) or not steps or not isinstance(steps[0], dict):
        return ''
    top = steps[0]
    # Never attach a different topic's suggested study to a priority card.
    if (_text(top.get('lesson'),90).casefold() != _text(expected_lesson,90).casefold()
        or _text(top.get('topic'),140).casefold() != _text(expected_topic,140).casefold()):
        return ''
    if top.get('teacher_approval_required') is not True or top.get('automatic_transfer') is not False:
        return ''
    if top.get('kind') != 'WIZARD_PREVIEW':
        return 'Çalışma planı: Önce bağımsız öğrenme kontrolünü inceleyin; yeni ödev otomatik oluşturulmadı.'
    if (type(top.get('candidate_minutes')) is not int or not 1 <= top['candidate_minutes'] <= 120
        or not _text(top.get('existing_book'), 140)):
        return ''
    label = ('Takvime uygunluk doğrulanmadı' if top.get('capacity_status') == 'UNKNOWN'
             else 'Doğrulanmış süre bütçesine sığıyor' if top.get('capacity_status') == 'VERIFIED_BUDGET_FITS'
             else 'Öğretmen kapasite kontrolü gerekir')
    return (f"Sihirbaz taslak adayı: {_text(top['existing_book'],90)} — "
            f"{top['candidate_minutes']} dk. {label}; ödev atanmadı.")[:270]
