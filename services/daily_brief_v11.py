"""Teacher-first, read-only daily worklist for Günün Akıllı Özeti V11.

Never uses assignments as proof of learning or inactivity. Teacher review marks
are separate from homework status and have no effect on student records.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Iterable


CREATE_REVIEW_TABLE = """
CREATE TABLE IF NOT EXISTS coach_brief_review_v11 (
    review_day TEXT NOT NULL,
    student_id INTEGER NOT NULL,
    suggestion_type TEXT NOT NULL,
    evidence_signature TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (review_day, student_id, suggestion_type, evidence_signature)
)
"""


def _student_id(suggestion: dict) -> int | None:
    f = suggestion.get("data") or {}
    try:
        value = f.get("id") or f.get("ogrenci_id")
        sid = int(value)
        return sid if sid > 0 else None
    except (ValueError, TypeError, AttributeError):
        return None


def review_identity(suggestion: dict) -> tuple[int, str, str] | None:
    """Stable same-day identity; changes when the supporting evidence changes.

    Does not include phone/name or transient UI/scores. No evidence of a student
    condition is inferred from the signature.
    """
    sid = _student_id(suggestion)
    kind = str(suggestion.get("type") or "").strip()
    if sid is None or kind not in {"overdue", "silent", "star", "birthday"}:
        return None
    f = suggestion.get("data") or {}
    evidence = {
        "overdue_recent": int(f.get("overdue_recent") or 0),
        "overdue_old": int(f.get("overdue_old") or 0),
        "completed_in_recent_set": int(f.get("completed_in_recent_set") or 0),
        "last_assignment_date": str(f.get("last_assignment_date") or ""),
        "has_assignment_history": bool(f.get("has_assignment_history")),
        "problem_lesson": str(f.get("problem_lesson") or ""),
        "problem_count": int(f.get("problem_count") or 0),
        "overdue_refs": sorted(str(x) for x in (f.get("overdue_refs") or [])),
    }
    payload = json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:24]
    return sid, kind, digest


def ensure_review_table(con) -> None:
    con.execute(CREATE_REVIEW_TABLE)


def load_reviewed(con, today: date | None = None) -> set[tuple[int, str, str]]:
    day = (today or date.today()).isoformat()
    rows = con.execute(
        """SELECT student_id, suggestion_type, evidence_signature
           FROM coach_brief_review_v11 WHERE review_day=?""", (day,)
    ).fetchall()
    return {(int(row[0]), str(row[1]), str(row[2])) for row in rows}


def set_reviewed(con, suggestion: dict, reviewed: bool, today: date | None = None) -> bool:
    identity = review_identity(suggestion)
    if identity is None:
        return False
    day = (today or date.today()).isoformat()
    if reviewed:
        con.execute("""INSERT OR IGNORE INTO coach_brief_review_v11
             (review_day, student_id, suggestion_type, evidence_signature)
             VALUES (?, ?, ?, ?)""", (day, *identity))
    else:
        con.execute("""DELETE FROM coach_brief_review_v11
             WHERE review_day=? AND student_id=? AND suggestion_type=? AND evidence_signature=?""",
            (day, *identity))
    return True


def _rank(suggestion: dict) -> tuple:
    f = suggestion.get("data") or {}
    kind = suggestion.get("type")
    recent = max(0, int(f.get("overdue_recent") or 0))
    old = max(0, int(f.get("overdue_old") or 0))
    # Recent overdue is more relevant to today's work than unverified old debt.
    if kind == "overdue":
        tier = 0 if recent else 3
        urgency = -recent if recent else -old
    elif kind == "birthday":
        tier, urgency = 1, 0
    elif kind == "star":
        tier, urgency = 2, -int(f.get("completed_in_recent_set") or 0)
    elif kind == "silent" and f.get("has_assignment_history"):
        tier, urgency = 4, -int(f.get("days_since_assigned") or 0)
    else:
        tier, urgency = 5, 0
    return (tier, urgency, _student_id(suggestion) or 0, str(suggestion.get("title") or ""))


def daily_brief(suggestions: Iterable[dict], reviewed: set | None = None, limit: int = 5) -> list[dict]:
    """Pick diverse, actionable, evidence-grounded cards for teacher review.

    Missing history, empty evidence and errors are always in 'Tümü' but do not
    inflate 'Bugünün 5 Önceliği'. The full list is never modified.
    """
    reviewed = reviewed or set()
    if limit <= 0:
        return []
    candidates = []
    for s in suggestions:
        kind = s.get("type")
        f = s.get("data") or {}
        if kind == "error" or (kind == "silent" and not f.get("has_assignment_history")):
            continue
        identity = review_identity(s)
        if identity is None or identity in reviewed:
            continue
        if kind == "overdue" and not ((f.get("overdue_recent") or 0) or (f.get("overdue_old") or 0)):
            continue
        candidates.append(s)

    out = []
    seen_students = set()
    for s in sorted(candidates, key=_rank):
        sid = _student_id(s)
        if sid in seen_students:
            continue
        out.append(s)
        seen_students.add(sid)
        if len(out) == limit:
            break
    return out


def brief_stats(suggestions: Iterable[dict], reviewed: set | None = None, limit: int = 5) -> dict:
    suggestions = list(suggestions)
    reviewed = reviewed or set()
    brief = daily_brief(suggestions, reviewed, limit)
    return {
        "priority_count": len(brief),
        "overdue_students": len({int(s["data"]["id"]) for s in suggestions
                                 if s.get("type") == "overdue" and s.get("data", {}).get("id")}),
        "no_history_count": sum(1 for s in suggestions if s.get("type") == "silent" and
                                 not (s.get("data") or {}).get("has_assignment_history")),
        "reviewed_count": sum(1 for s in suggestions if review_identity(s) in reviewed),
    }
