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
from services.proactive_academic_v3529 import read_academic_next_step
from services.shared_academic_decision_v3530 import read_shared_academic_card
from services.cohort_academic_advisor_v3534 import summarize_cohort
from services.canonical_homework_evidence_v3535 import scan_canonical_homework


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
        # V3.5.34 cohort review reuses this very same V10 read snapshot.
        # A missing schema or timeout is UNVERIFIED, never a healthy verdict.
        cohort = {'state': 'UNVERIFIED', 'active_students': None,
                  'remote_verified': False, 'priority_cards': []}
        if time.monotonic() < deadline - 1.5:
            try:
                cohort = summarize_cohort(con, facts, suggestions, reviewed,
                                          today=day, max_cards=5)
            except (sqlite3.Error, ValueError, TypeError, KeyError):
                pass
        # V3.5.35: separate canonical homework evidence from V10 reviewed flags.
        # Preserve older cohort fields for backward compatibility; never claim
        # V10 reviewed state also reviews independent modern rows.
        if cohort.get('state') != 'UNVERIFIED' and time.monotonic() < deadline - 0.65:
            try:
                cohort['canonical_homework'] = scan_canonical_homework(con, today=day, max_cards=5)
            except (sqlite3.Error, ValueError, TypeError, KeyError):
                cohort['canonical_homework'] = {'state': 'UNVERIFIED', 'priority_cards': []}
        # Do not let legacy V10 suggestions bypass verified V3.5.35
        # quarantine when ownership/group identity is ambiguous.
        canonical = cohort.get('canonical_homework') or {}
        if canonical.get('state') in ('OBSERVED', 'PARTIAL_COVERAGE'):
            banned = set(canonical.get('excluded_student_ids') or ())
            if banned:
                ordered = [s for s in ordered
                           if (s.get('data') or {}).get('id') not in banned]
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
                'coach': None, 'academic': None, 'shared_academic': None,
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
        # V3.5.29: Only the top candidate, on the SAME read-only transaction.
        # A missing/incomplete legacy schema must never break the existing feed.
        if cards and time.monotonic() < deadline - 0.5:
            try:
                sid = int(cards[0]['student_id'])
                # Shared Student360/coach/planning context, always selected SID.
                shared = read_shared_academic_card(con, sid, today=day)
                if shared['student_id'] == sid:
                    cards[0]['shared_academic'] = shared
                    academic = shared.get('academic')
                    if academic and academic['student_id'] == sid:
                        cards[0]['academic'] = academic
            except Exception:
                # Optional advice must never disrupt the original teacher feed.
                pass
        # V3.5.36: same-student action, only while the existing time budget
        # permits. Do not delay or alter the original V10/V11 teacher feed.
        if cards and time.monotonic() < deadline - 1.0:
            try:
                from services.academic_actions_v3536 import read_student_action_card
                student_id = cards[0]['student_id']
                verified_action = read_student_action_card(con, student_id, today=day)
                if verified_action['student_id'] == student_id:
                    cards[0]['verified_academic_action'] = verified_action
                    # Optional V3.5.37 guidance reuses canonical card; only
                    # run when the teacher feed still has spare time.
                    if time.monotonic() < deadline - 0.55:
                        try:
                            from services.intervention_advisor_v3537 import build_intervention_draft
                            draft = build_intervention_draft(con, student_id, today=day,
                                                             action_card=verified_action)
                            if draft['student_id'] == student_id:
                                cards[0]['intervention_draft'] = draft
                        except (sqlite3.Error, ValueError, TypeError, KeyError):
                            pass
            except (sqlite3.Error, ValueError, TypeError, KeyError):
                pass
        # V3.5.38: a bounded, read-only check of previously TEACHER-approved
        # intervention follow-ups. No additional student assignment is made.
        followups = {'state': 'UNVERIFIED', 'date_due_candidates': None,
                     'priority_cards': []}
        if time.monotonic() < deadline - 0.5:
            try:
                from services.intervention_followup_v3538 import scan_cohort_followups
                followups = scan_cohort_followups(con, as_of=day, max_scan=5000, max_cards=2)
            except (sqlite3.Error, ValueError, TypeError, KeyError):
                pass
        # V3.5.39: optional descriptive aggregate; never reorders V10/V11
        # priorities, modifies existing intervention choices, or blocks feed.
        historical_patterns = {'state': 'NOT_RUN', 'patterns': []}
        if cards and time.monotonic() < deadline - 1.25:
            try:
                from services.intervention_patterns_v3539 import read_historical_patterns
                recent = cards[0].get('intervention_draft') or {}
                suggestions = recent.get('recommendations') or []
                lesson = suggestions[0].get('subject') if suggestions else None
                historical_patterns = read_historical_patterns(
                    con, lesson=lesson, max_scan=60, max_groups=1)
            except (sqlite3.Error, ValueError, TypeError, KeyError):
                historical_patterns = {'state': 'SOURCE_UNVERIFIED', 'patterns': []}
        # V3.5.67: ONE optional academic priority for the already chosen
        # first student. Existing V10/V11 ordering and overdue list untouched.
        # Same read snapshot, bounded by the pre-existing timeout.
        if cards and time.monotonic() < deadline - 1.5:
            try:
                from services.automatic_coaching_cycle_v3565 import read_automatic_coaching_cycle
                from services.coaching_action_center_v3567 import build_action_center_card
                sid = cards[0]['student_id']
                cycle = read_automatic_coaching_cycle(con, sid, today=day, max_actions=2)
                card = build_action_center_card(cycle, sid, today=day)
                if card['state'] == 'ACTION_SUGGESTED':
                    cards[0]['shared_coaching_priority_v3567'] = card
            except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError):
                pass  # Optional new view never replaces the original feed.
        con.rollback()
        return {
            'day': day.isoformat(),
            'checked_at': datetime.now().strftime('%H:%M:%S'),
            'cards': cards, 'total_queued': len(candidate), 'cohort': cohort,
            'intervention_followups': followups,
            'historical_patterns': historical_patterns,
            'source': 'local_read_only', 'remote_verified': False,
            'feedback_scope': 'per_device_noncritical_presentation_only',
        }
    finally:
        con.close()
