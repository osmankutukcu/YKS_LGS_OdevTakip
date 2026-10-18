# -*- coding: utf-8 -*-
"""V26.6 read-only revision hints for cooperating coach windows.

Only OS file metadata is read. This is a best-effort LOCAL change hint,
not a transactional notification bus, cloud sync proof, or student-specific
mutation log. No SQLite writes, no timers, no background threads here.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from services.coach_assistant_v1.proactive_policy import database_stamp


def get_revision(db_path):
    """Cheap bounded check covering the SQLite database and active WAL file."""
    try:
        return database_stamp(db_path)
    except (OSError, ValueError, TypeError):
        return None


def known_revision(revision) -> bool:
    return (isinstance(revision, tuple) and len(revision) == 2 and
            revision[0] is not None)


def changed_during_read(before, after) -> bool:
    """Fail closed when both file states are known and clearly different.

    Missing/inaccessible files cannot prove freshness, so caller should not
    claim a successful synchronization from a ``False`` result alone.
    """
    return known_revision(before) and known_revision(after) and before != after


@dataclass
class RevisionWatch:
    """Deduplicate/batch disk-change hints without polling or touching UI.

    `observe` is invoked by an existing UI timer on the UI thread. A new hint
    is emitted once the file state has been stable for ``quiet_seconds`` and
    the per-window cooldown has elapsed. Distinct student selection resets it.
    """

    quiet_seconds: float = 2.0
    cooldown_seconds: float = 45.0
    clock: object = time.monotonic

    def __post_init__(self):
        self.baseline = None
        self.candidate = None
        self.candidate_since = None
        self.last_notice = None

    def reset(self, revision=None):
        self.baseline = revision if known_revision(revision) else None
        self.candidate = None
        self.candidate_since = None
        self.last_notice = None

    def observe(self, revision) -> bool:
        if not known_revision(revision):
            return False
        now = float(self.clock())
        if self.baseline is None:
            self.baseline = revision
            return False
        if revision == self.baseline:
            self.candidate = None
            self.candidate_since = None
            return False
        if revision != self.candidate:
            self.candidate = revision
            self.candidate_since = now
            return False
        if self.candidate_since is None or now - self.candidate_since < self.quiet_seconds:
            return False
        if self.last_notice is not None and now - self.last_notice < self.cooldown_seconds:
            return False
        self.baseline = revision
        self.candidate = None
        self.candidate_since = None
        self.last_notice = now
        return True
