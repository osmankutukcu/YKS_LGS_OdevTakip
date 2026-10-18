"""V4 read-only presentation bridge for the EXISTING daily V10/V11 work queue.

It deliberately does not invent a learning/risk score or use the network. The
original suggestion and acknowledgement rules remain the single source of truth.
No user/student data are written to SQLite by this module.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sqlite3

from services.daily_coach_v10 import collect_student_facts, make_suggestions
from services.daily_brief_v11 import load_reviewed, daily_brief


def _read_reviewed(con: sqlite3.Connection, on_day: date) -> set:
    # Review history table is optional until original dialog has initialized it.
    # Never call ensure_review_table from this read-only strip.
    try:
        return load_reviewed(con, on_day)
    except sqlite3.OperationalError as exc:
        if 'no such table' in str(exc).lower() and 'coach_brief_review_v11' in str(exc):
            return set()
        raise


def read_today_priority(db_path: str | Path, *, today: date | None = None) -> dict:
    day = today or date.today()
    path = Path(db_path).expanduser().resolve()
    # Path.as_uri handles Windows drive letters, spaces and non-ASCII paths.
    uri = path.as_uri() + '?mode=ro'
    con = sqlite3.connect(uri, uri=True, timeout=2.0)
    try:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only=ON')
        # Bound large-dataset UI work: abort a query exceeding its allotted
        # read-time budget; never block the GUI thread.
        import time
        deadline = time.monotonic() + 8.0
        con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10_000)
        facts = collect_student_facts(con, today=day)
        suggestions = make_suggestions(facts, today=day)
        reviewed = _read_reviewed(con, day)
        top = daily_brief(suggestions, reviewed=reviewed, limit=5)
        first = top[0] if top else None
        item = None
        if first:
            data = first.get('data') or {}
            # Keep only material necessary for a teacher-facing, short summary.
            item = {
                'student_id': int(data['id']),
                'kind': str(first.get('type') or '')[:40],
                'title': str(first.get('title') or '')[:180],
                'reason': str(first.get('desc') or '')[:280],
                'basis': str((first.get('reasons') or [''])[0])[:220],
            }
        return {
            'day': day.isoformat(), 'priority_count': len(top),
            'first': item, 'checked_at': datetime.now().strftime('%H:%M:%S'),
            'source': 'local_sqlite_v10_v11',
        }
    finally:
        con.close()
