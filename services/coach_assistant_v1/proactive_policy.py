# -*- coding: utf-8 -*-
"""Small, testable, in-memory attention budget for teacher-facing coach hints.

No student details, answers or activity are persisted.  This module never writes
homework, suggests a clinical diagnosis or calls an external service.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
import hashlib
import time

VALID_MODES = ("quiet", "balanced", "active")


def signal_key(badge: str, hook: str) -> str:
    """Stable opaque signal identity; no raw student name is stored in history."""
    text = (str(badge or "") + "\x1f" + str(hook or "")).strip().casefold()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def severity(badge: str) -> int:
    b = str(badge or "").casefold()
    if any(s in b for s in ("darboğaz", "kritik", "risk", "düşük doğruluk", "fark ettiniz")):
        return 3
    if any(s in b for s in ("yük", "birikim", "geçmiş", "doğruluk", "eksik")):
        return 2
    return 1


@dataclass(frozen=True)
class Verdict:
    show: bool
    reason: str


class ProactiveGate:
    """Deduplicate suggestions, pace auto-notifications, never suppress saved inbox.

    Uses monotonic time.  A new student receives a fresh in-memory session scope;
    global pacing still applies to prevent rapid browsing from spamming the UI.
    """
    def __init__(self, clock=None):
        self.clock = clock or time.monotonic
        self._shown: dict[tuple[int, str], float] = {}
        self._global_last: float | None = None
        self._recent: deque[float] = deque()

    def decide(self, *, student_id: int, key: str, priority: int, mode: str,
               interruptible: bool = True) -> Verdict:
        now = float(self.clock())
        if mode not in VALID_MODES:
            return Verdict(False, "invalid_mode")
        if mode == "quiet":
            return Verdict(False, "quiet")
        if priority < 2 and mode != "active":
            return Verdict(False, "low_priority")
        if not interruptible:
            return Verdict(False, "teacher_busy")
        if type(student_id) is not int or student_id <= 0 or not key:
            return Verdict(False, "invalid_context")
        previous = self._shown.get((student_id, key))
        if previous is not None and now - previous < 3600:
            return Verdict(False, "duplicate")
        self._recent = deque(t for t in self._recent if now - t < 3600)
        if len(self._recent) >= (4 if mode == "balanced" else 6):
            return Verdict(False, "hourly_limit")
        if self._global_last is not None:
            gap = 90 if priority >= 3 else 300 if priority == 2 else 600
            if mode == "active":
                gap = max(50, gap // 2)
            if now - self._global_last < gap:
                return Verdict(False, "global_cooldown")
        self._shown[(student_id, key)] = now
        self._global_last = now
        self._recent.append(now)
        # Trim old student keys without keeping student records beyond the session.
        if len(self._shown) > 300:
            self._shown = {k: t for k, t in self._shown.items() if now - t < 3600}
        return Verdict(True, "accepted")


def database_stamp(db_path):
    """Cheap change hint, not evidence of successful cloud synchronization."""
    from pathlib import Path
    path = Path(db_path)
    values = []
    for part in (path, Path(str(path) + "-wal")):
        try:
            stat = part.stat()
            values.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            values.append(None)
    return tuple(values)
