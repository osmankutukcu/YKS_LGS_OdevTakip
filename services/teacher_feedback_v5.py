"""Private, per-device, optional V5 teacher feedback for NONCRITICAL card ordering.

Contains no student identifier, student records, or message contents. The core
V10/V11 prioritizer and assignment/coach algorithms are never trained/changed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

KINDS = frozenset({'overdue', 'silent', 'star', 'birthday'})
VOTES = frozenset({'useful', 'not_useful'})


def default_path() -> Path:
    base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config'))
    return base / 'YKS_LGS_Manager' / 'teacher_feedback_v5.json'


def read_feedback(path: Path | str | None = None) -> dict:
    p = Path(path) if path is not None else default_path()
    try:
        if not p.is_file() or p.is_symlink() or p.stat().st_size > 8192:
            return {}
        obj = json.loads(p.read_text(encoding='utf-8'))
        if obj.get('version') != 1 or not isinstance(obj.get('counts'), dict):
            return {}
        result = {}
        for kind in KINDS:
            record = obj['counts'].get(kind)
            if isinstance(record, dict):
                result[kind] = {vote: max(0, min(1000, int(record.get(vote, 0))))
                                for vote in VOTES}
        return result
    except (OSError, TypeError, ValueError, AttributeError, json.JSONDecodeError):
        return {}


def preference(counts: dict, kind: str) -> int:
    v = counts.get(kind) or {}
    positive = min(30, max(0, int(v.get('useful', 0))))
    negative = min(30, max(0, int(v.get('not_useful', 0))))
    # Conservative and capped: cannot hide overdue or change coach decisions.
    return max(-2, min(2, positive - negative))


def vote(kind: str, rating: str, path: Path | str | None = None) -> dict:
    if kind not in KINDS or rating not in VOTES:
        raise ValueError('Desteklenmeyen geri bildirim.')
    p = Path(path) if path is not None else default_path()
    if p.is_symlink():
        raise ValueError('Geri bildirim konumu güvenli değil.')
    counts = read_feedback(p)
    row = counts.setdefault(kind, {'useful': 0, 'not_useful': 0})
    row[rating] = min(1000, row[rating] + 1)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.teacher_v5_', suffix='.tmp', dir=str(p.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump({'version': 1, 'counts': counts}, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, p)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return counts
