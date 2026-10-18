# -*- coding: utf-8 -*-
"""V26.8 in-process hints from successful, already-committed coaching saves.

These hints are advisory and never part of a DB transaction.  Consumers must
re-read authoritative data, not interpret a hint as proof of a valid write.
No student names, raw scores or personal notes enter the shared event queue.
"""
from __future__ import annotations

import logging

from services.coach_assistant_v1.event_router_v267 import CoachChange, get_coach_router

_ALLOWED = frozenset({'independent_measurement', 'coaching_plan', 'student_profile', 'exam'})


def publish_saved_coaching_change(kind: str, student_id: int, *, lesson: str = '', topic: str = '') -> bool:
    """Best-effort notification ONLY after caller has confirmed a commit.

    False means no notification, not that the underlying write failed.
    """
    if not isinstance(kind, str) or kind not in _ALLOWED or type(student_id) is not int or student_id <= 0:
        return False
    try:
        subject = lesson.strip() if isinstance(lesson, str) else ''
        topic_name = topic.strip() if isinstance(topic, str) and subject else ''
        # A course-free plan/preference change is intentionally student-wide.
        change = CoachChange(kind=kind, student_id=student_id,
                             lesson=subject or None, topic=topic_name or None)
        get_coach_router().publish(change)
        return True
    except Exception as exc:
        # Optional event forwarding MUST NOT make an already-committed save
        # look unsuccessful, including unexpected I/O or implementation errors.
        # Never log raw student data, note contents, or event payloads.
        logging.getLogger(__name__).warning('Coach change hint skipped: %s', type(exc).__name__)
        return False
