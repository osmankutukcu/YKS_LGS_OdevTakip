"""Read-only teacher 'nobetci': existing V10/V11 priorities + optional V27 glance.

Cannot send messages, create assignments, mark homework or alter SQLite. Optional
teacher feedback affects only NONURGENT visual presentation order, never
student evaluation, existing priority generation, or overdue ordering.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sqlite3
import time

from services.daily_coach_v10 import collect_student_facts, make_suggestions
from services.daily_brief_v11 import daily_brief, load_reviewed, review_identity
from services.live_student_summary_v3 import read_coach_glance
from services.teacher_feedback_v5 import read_feedback, preference


def _reviewed(con, day):
    try:
        return load_reviewed(con, day)
    except sqlite3.OperationalError as exc:
        if 'no such table' in str(exc).lower() and 'coach_brief_review_v11' in str(exc):
            return set()
        raise


def sort_for_teacher(top, prefs):
    """Respect original overdue tier, adapt only nonurgent slots."""
    urgent = [s for s in top if s.get('type') == 'overdue']
    other = [s for s in top if s.get('type') != 'overdue']
    indexed = list(enumerate(other))
    indexed.sort(key=lambda v: (-preference(prefs, str(v[1].get('type') or '')), v[0]))
    return urgent + [s for _, s in indexed]


def read_teacher_feed(db_path: str | Path, *, today: date | None = None,
                      feedback_path=None, advisor=None, max_cards: int = 3) -> dict:
    day = today or date.today()
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError('Öğrenci veritabanı bulunamadı.')
    con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1.5)
    try:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA query_only=ON')
        deadline = time.monotonic() + 7.0
        con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 10_000)
        con.execute('BEGIN')  # coherent snapshot throughout daily + adaptive read
        facts = collect_student_facts(con, today=day)
        suggestions = make_suggestions(facts, today=day)
        reviewed = _reviewed(con, day)
        candidate = daily_brief(suggestions, reviewed=reviewed, limit=15)
        prefs = read_feedback(feedback_path)
        ordered = sort_for_teacher(candidate, prefs)
        cards = []
        for s in ordered[:max(1, min(5, int(max_cards)))]:
            f = s.get('data') or {}
            identity = review_identity(s)
            sid = int(f['id'])
            if not identity or sid <= 0:
                continue
            kind = str(s.get('type') or '')
            if kind not in {'overdue', 'silent', 'star', 'birthday'}:
                continue
            cards.append({
                'student_id': sid,
                'kind': kind,
                'title': str(s.get('title') or '')[:140],
                'reason': str(s.get('desc') or '')[:240],
                'basis': str(' '.join(s.get('reasons') or []))[:320],
                'action': str(s.get('action') or 'İncele')[:40],
                'source': 'Günün Akıllı Özeti V10/V11',
                'coach': None,
            })
        # Only first relevant student; expensive V27 data never scanned for all.
        if cards and time.monotonic() < deadline - 1:
            try:
                sid = cards[0]['student_id']
                glance = read_coach_glance(con, sid, provider=advisor)
                if glance.student_id == sid:
                    cards[0]['coach'] = {
                        'priority': glance.priority[:140],
                        'next_step': glance.next_step[:200],
                        'basis': glance.basis[:120],
                        'evidence_count': glance.evidence_count,
                        'as_of': glance.as_of,
                        'source': 'Mevcut Adaptif Koç V27',
                    }
            except Exception:
                # Isolated optional advisor; do not invent advice when unavailable.
                pass
        con.rollback()
        return {
            'day': day.isoformat(),
            'checked_at': datetime.now().strftime('%H:%M:%S'),
            'cards': cards, 'total_queued': len(candidate),
            'source': 'local_read_only', 'remote_verified': False,
            'feedback_scope': 'per_device_noncritical_presentation_only',
        }
    finally:
        con.close()
