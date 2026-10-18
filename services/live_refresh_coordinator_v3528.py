# -*- coding: utf-8 -*-
"""V3.5.28 optional Qt-free refresh decisions, layered on existing coach router.

This module does NOT hook any UI form or publish write events. Existing screens
may opt in later, after a successful save and Windows UAT. An unacknowledged
refresh never consumes the event cursor, even when hidden/dirty/busy.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.coach_assistant_v1.event_router_v267 import CoachChange, CoachChangeRouter
from services.system_registry_v3528 import affected_modules


@dataclass(frozen=True)
class RefreshDecision:
    status: str
    from_cursor: int
    latest_cursor: int
    changed: bool
    overflow: bool
    reason: str

    def acknowledged_cursor(self, *, refreshed_successfully: bool) -> int:
        """Only move cursor AFTER a real successful data read in the consumer."""
        if self.status in ('NO_CHANGE', 'IRRELEVANT'):
            return self.latest_cursor
        if self.status == 'REFRESH_REQUIRED' and refreshed_successfully:
            return self.latest_cursor
        return self.from_cursor


def decide_refresh(router: CoachChangeRouter, after_cursor: int, *,
                   student_id: int, module: str,
                   lesson: str = '', topic: str = '',
                   is_visible: bool = True, has_unsaved_changes: bool = False,
                   is_busy: bool = False) -> RefreshDecision:
    """Only decide; never trigger callbacks/queries/UI refresh inside this method.

    Filter by module and student before planning a refresh. Overflow means
    unknown/missing events, so for that student prefer conservative re-read.
    """
    if not isinstance(router, CoachChangeRouter):
        raise TypeError('Expected CoachChangeRouter')
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Student context is required; never guess identity')
    if type(after_cursor) is not int or after_cursor < 0 or after_cursor > router.cursor:
        raise ValueError('Invalid or future event cursor')
    if not isinstance(module, str) or not module:
        raise ValueError('Module must be declared')
    # Validate module key even for empty queues.
    from services.system_registry_v3528 import MODULES
    if module not in {spec.key for spec in MODULES}:
        raise ValueError('Unknown module')
    decision = router.check(after_cursor, student_id=student_id,
                            lesson=lesson, topic=topic)
    # On a module-irrelevant event, router.check alone would say changed.
    # Keep a safe conservative refresh decision. Future event metadata may
    # narrow this; do not suppress a change based on unavailable metadata.
    if not decision.changed:
        return RefreshDecision('NO_CHANGE', after_cursor, decision.cursor,
                               False, decision.overflow, 'No matching event')
    if not is_visible:
        return RefreshDecision('DEFER_HIDDEN', after_cursor, decision.cursor,
                               True, decision.overflow, 'Window not visible')
    if has_unsaved_changes:
        return RefreshDecision('DEFER_DIRTY', after_cursor, decision.cursor,
                               True, decision.overflow, 'Unsaved edits take priority')
    if is_busy:
        return RefreshDecision('DEFER_BUSY', after_cursor, decision.cursor,
                               True, decision.overflow, 'Interaction is in progress')
    return RefreshDecision('REFRESH_REQUIRED', after_cursor, decision.cursor,
                           True, decision.overflow,
                           'Potentially stale information; re-read authoritative source')


def signal_after_commit(router: CoachChangeRouter, kind: str, *,
                        student_id: int | None = None,
                        lesson: str | None = None, topic: str | None = None,
                        revision: str = '') -> int:
    """Explicit producer API. Caller MUST verify commit before invoking.

    No DB write, no accidental silent retry, no private fields in payload.
    Unknown DB change MUST be unscoped; never guess a student identity.
    """
    affected_modules(kind)  # validate known event types
    return router.publish(CoachChange(kind=kind, student_id=student_id,
                                      lesson=lesson, topic=topic,
                                      revision=revision))


class ExternalCommitObserver:
    """Read-only observer of commits originating on OTHER SQLite connections.

    The first poll creates a baseline. Own-connection writes are invisible to
    data_version; those writers must explicitly signal AFTER commit.
    """
    def __init__(self, db_path, router: CoachChangeRouter):
        from services.live_change_probe_v241 import DatabaseChangeProbe
        if not isinstance(router, CoachChangeRouter):
            raise TypeError('Expected CoachChangeRouter')
        self._probe = DatabaseChangeProbe(db_path)
        self._router = router

    def poll(self) -> bool:
        if self._probe.poll():
            signal_after_commit(self._router, 'database_unknown')
            return True
        return False

    @property
    def last_error(self):
        return self._probe.last_error

    def close(self):
        self._probe.close()
