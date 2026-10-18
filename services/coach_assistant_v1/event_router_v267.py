# -*- coding: utf-8 -*-
"""V26.7: tiny in-memory, scope-aware, read-only coaching change hints.

This is NOT a database trigger, inter-process bus or proof of cloud sync.
Only a producer that knows the affected student/lesson may publish a scoped
hint. An unknown SQLite/WAL file change is global and must never be given an
invented student scope. No storage, schema changes, network or Qt dependency.
Consumers poll this queue on their EXISTING UI timer; no callbacks on worker
threads and no interference with the protected checkbox/write path.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock

from services.coach_assistant_v1.shared_rules_v260 import lesson_key

KINDS = frozenset((
    'database_unknown', 'homework', 'control', 'independent_measurement',
    'exam', 'coaching_plan', 'student_profile',
))


@dataclass(frozen=True)
class CoachChange:
    kind: str
    student_id: int | None = None
    lesson: str | None = None
    topic: str | None = None
    revision: str = ''

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError('Unrecognized coach change kind')
        if self.student_id is not None and (type(self.student_id) is not int or self.student_id <= 0):
            raise ValueError('Student scope must be a positive integer')
        if self.kind == 'database_unknown' and (self.student_id is not None or self.lesson or self.topic):
            raise ValueError('Unknown database change must stay unscoped')
        if self.kind != 'database_unknown' and self.student_id is None:
            raise ValueError('Scoped change must include student ID')
        if self.lesson is not None and (not isinstance(self.lesson, str) or not self.lesson.strip()):
            raise ValueError('Invalid lesson scope')
        if self.topic is not None and (not isinstance(self.topic, str) or not self.topic.strip() or not self.lesson):
            raise ValueError('A topic requires a lesson')
        if not isinstance(self.revision, str) or len(self.revision) > 160:
            raise ValueError('Invalid revision token')


def affects(change: CoachChange, *, student_id: int, lesson: str = '', topic: str = '') -> bool:
    """A more general viewer receives relevant specific changes.

    A viewer on 'all lessons' receives every change for its student. A viewer
    on a particular lesson does NOT receive unrelated subject changes.
    Unknown change scope must fail open (refresh) rather than hide stale data.
    """
    if type(student_id) is not int or student_id <= 0:
        return False
    if change.student_id is not None and change.student_id != student_id:
        return False
    if change.lesson and lesson and lesson_key(change.lesson) != lesson_key(lesson):
        return False
    if change.topic and topic and change.topic.casefold().strip() != topic.casefold().strip():
        return False
    return True


@dataclass(frozen=True)
class ChangeCheck:
    cursor: int
    changed: bool
    overflow: bool = False


class CoachChangeRouter:
    """Bounded nonpersistent queue; producers cannot execute UI callbacks."""

    def __init__(self, capacity: int = 256):
        if type(capacity) is not int or capacity < 2:
            raise ValueError('capacity must be >= 2')
        self._lock = RLock()
        self._items = deque(maxlen=capacity)
        self._cursor = 0

    @property
    def cursor(self) -> int:
        with self._lock:
            return self._cursor

    def publish(self, change: CoachChange) -> int:
        if not isinstance(change, CoachChange):
            raise TypeError('Expected validated CoachChange')
        with self._lock:
            # Deduplicate only when publisher supplied an actual revision token.
            # Without a token, two identical events can be two real edits.
            if change.revision and self._items and self._items[-1][1] == change:
                return self._cursor
            self._cursor += 1
            self._items.append((self._cursor, change))
            return self._cursor

    def check(self, after_cursor: int, *, student_id: int,
              lesson: str = '', topic: str = '') -> ChangeCheck:
        if type(after_cursor) is not int or after_cursor < 0:
            raise ValueError('Invalid cursor')
        with self._lock:
            latest = self._cursor
            oldest = self._items[0][0] if self._items else latest + 1
            overflow = after_cursor < oldest - 1
            if type(student_id) is not int or student_id <= 0:
                return ChangeCheck(latest, False, overflow)
            # Missing events are potentially relevant. Prefer a harmless refresh.
            relevant = overflow or any(
                seq > after_cursor and affects(event, student_id=student_id,
                                               lesson=lesson, topic=topic)
                for seq, event in self._items
            )
            return ChangeCheck(latest, relevant, overflow)


# Per-process only. Does not persist student identities, does not perform I/O.
_SHARED_ROUTER = CoachChangeRouter()


def get_coach_router() -> CoachChangeRouter:
    return _SHARED_ROUTER
