# -*- coding: utf-8 -*-
"""Teacher-approved *lesson + topic* priorities for the existing weekly calendar.

Read-only with respect to persistent data.  Does not create homework, change
minutes/deadlines, or infer subskills that are missing from the assigned tasks.
Opt-in: absence of a topic list is a strict no-op for the historical planner.
"""
from __future__ import annotations
import unicodedata
from typing import Any

MAX_FOCUS = 20


def _key(value: Any) -> str:
    return unicodedata.normalize('NFC', str(value or '').strip()).translate(str.maketrans({'İ': 'i', 'I': 'ı'})).lower()


def accepted_topic_pairs(homework: list[dict], proposals: list[dict]) -> list[dict]:
    """Only currently assigned lesson/topic combinations can be approved."""
    assignments = {(_key(row.get('ders')), _key(row.get('konu')))
                   for row in (homework or [])[:500] if isinstance(row, dict)}
    choices: list[dict] = []
    seen = set()
    for proposal in (proposals or [])[:MAX_FOCUS]:
        if not isinstance(proposal, dict):
            continue
        lesson = str(proposal.get('lesson') or '').strip()
        topic = str(proposal.get('topic') or '').strip()
        pair = (_key(lesson), _key(topic))
        if not all(pair) or pair not in assignments or pair in seen:
            continue
        seen.add(pair)
        choices.append({'lesson': lesson, 'topic': topic})
    return choices


def topic_focused(task: Any, focus: list[dict]) -> bool:
    """Match original (possibly unsplit) task topic, never a similar name."""
    raw = getattr(task, 'raw', {}) or {}
    if not isinstance(raw, dict):
        return False
    pair = (_key(raw.get('ders')), _key(raw.get('konu')))
    return pair in {(_key(e.get('lesson')), _key(e.get('topic')))
                    for e in (focus or []) if isinstance(e, dict)}


def promote_topics(tasks: list[Any], approved: list[dict], deadline_score) -> int:
    """In-memory priority only; preserve deadlines, durations, assignments.

    Existing date priority always sorts first.  When equal, the explicitly
    approved exact topic wins over other topics (including from a manually
    preferred lesson).  No new tasks or timetable constraints are introduced.
    """
    if not approved:
        return 0
    original = [getattr(t, 'raw', {}) or {} for t in tasks]
    allowed = accepted_topic_pairs(original, approved)
    if not allowed:
        return 0
    keys = {(_key(e['lesson']), _key(e['topic'])) for e in allowed}
    def is_target(task):
        raw = getattr(task, 'raw', {}) or {}
        return isinstance(raw, dict) and (_key(raw.get('ders')), _key(raw.get('konu'))) in keys

    matched = 0
    for task in tasks:
        if is_target(task):
            task.priority = max(task.priority, 5)
            task.kind = 'konu_odak'
            matched += 1
    if matched:
        tasks.sort(key=lambda t: (
            deadline_score(t.deadline),
            -t.priority,
            0 if is_target(t) else 1,
            -t.zorluk,
            -t.sure,
        ))
    return matched
