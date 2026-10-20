# -*- coding: utf-8 -*-
"""Safe, read-only targets for the EXISTING context menu (v3.5.68 pilot).

Never dispatch here. Source records are checked against one student and date;
the UI adapter additionally rechecks live student and loaded matrix on click.
"""
from __future__ import annotations
from datetime import date


def recommended_existing_targets(student_id: int, today: date, *, cycle=None, alignment=None):
    """Return immutable navigation descriptors, never an assignment request."""
    if type(student_id) is not int or student_id <= 0 or type(today) is not date:
        return ()
    targets = []
    try:
        from services.coaching_action_center_v3567 import build_action_center_card
        priority = build_action_center_card(cycle, student_id, today=today)
    except (ImportError, TypeError, KeyError, ValueError):
        priority = None
    if (isinstance(priority, dict) and priority.get('state') == 'ACTION_SUGGESTED'
        and priority.get('student_id') == student_id
        and priority.get('as_of') == today.isoformat()
        and priority.get('action_key') == 'btnOgrenme'
        and priority.get('read_only') is True
        and priority.get('teacher_approval_required') is True
        and priority.get('auto_assignment') is False
        and priority.get('auto_message') is False):
        area = priority.get('area') or 'Öğrenme'
        targets.append({'key': 'learning', 'label': '🧠 Öğrenme kontrolünü incele',
                        'detail': str(area)[:150], 'student_id': student_id,
                        'as_of': today.isoformat(), 'read_only': True})
    if (isinstance(alignment, dict)
        and alignment.get('schema') == 'science_wizard_alignment_v3564'
        and type(alignment.get('student_id')) is int
        and alignment['student_id'] == student_id
        and alignment.get('as_of') == today.isoformat()
        and alignment.get('state') == 'MATCHED'
        and alignment.get('read_only') is True
        and alignment.get('teacher_approval_required') is True
        and alignment.get('auto_assignment') is False
        and alignment.get('auto_selection') is False
        and alignment.get('requires_live_matrix_recheck') is True
        and alignment.get('existing_wizard_unchanged') is True):
        matched = alignment.get('matched')
        if isinstance(matched, list) and 1 <= len(matched) <= 2 and all(
            isinstance(x, dict) and
            all(isinstance(x.get(k), str) and 0 < len(x[k].strip()) <= 140
                for k in ('lesson', 'topic', 'existing_book'))
            and x.get('teacher_must_review_in_existing_wizard') is True
            and x.get('automatic_transfer') is False
            and type(x.get('minutes')) is int and 1 <= x['minutes'] <= 120
            for x in matched
        ):
            item = matched[0]
            targets.append({'key': 'wizard', 'label': '✨ Mevcut Sihirbaz taslağını incele',
                            'detail': f"{item['lesson']} / {item['topic']} / {item['existing_book']}"[:200],
                            'student_id': student_id, 'as_of': today.isoformat(),
                            'read_only': True})
    return tuple(targets)
