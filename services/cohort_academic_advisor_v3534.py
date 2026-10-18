# -*- coding: utf-8 -*-
"""V3.5.34 — institution-local, evidence-bounded academic follow-up queue.

No writes, network, messages, diagnosis, score or unverified student attribution.
Reuses the existing V10 facts/suggestions in the SAME read-only snapshot;
it never scans all students through the expensive per-student coaching engine.
"""
from __future__ import annotations

from datetime import date
import sqlite3

from services.daily_brief_v11 import review_identity


REQUIRED = frozenset({'ogrenci', 'odev', 'odev_kume'})


def _columns(con, table: str) -> set[str]:
    return {str(row[1]) for row in con.execute('PRAGMA table_info(' + table + ')')}


def _unsafe_student_ids(con) -> set[int]:
    """Find all identities implicated by broken ownership, including both sides.

    Only known, hardcoded table names are inserted into SQL. If schema is not
    suitable, fail closed instead of attributing ambiguous rows to a child.
    """
    tables = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not REQUIRED <= tables:
        raise sqlite3.OperationalError('required identity tables unavailable')
    columns = {t: _columns(con, t) for t in ('odev', 'odev_kume')}
    if not {'id', 'ogrenci_id'} <= columns['odev_kume'] or not {'ogrenci_id', 'kume_id'} <= columns['odev']:
        raise sqlite3.OperationalError('ownership columns unavailable')
    unsafe = set()
    for table in ('odev', 'odev_satir'):
        if table not in tables:
            continue
        col = _columns(con, table)
        if {'ogrenci_id', 'kume_id'} <= col:
            rows = con.execute(f'''
                SELECT t.ogrenci_id, k.ogrenci_id
                FROM {table} t LEFT JOIN odev_kume k ON k.id=t.kume_id
                WHERE t.kume_id IS NOT NULL AND
                    (k.id IS NULL OR k.ogrenci_id IS NULL OR t.ogrenci_id IS NULL
                     OR k.ogrenci_id<>t.ogrenci_id)
            ''').fetchall()
            for sid, owner in rows:
                for value in (sid, owner):
                    if type(value) is int and value > 0:
                        unsafe.add(value)
        if table == 'odev_satir' and {'odev_id', 'ogrenci_id'} <= col and 'id' in columns['odev']:
            rows = con.execute('''
                SELECT s.ogrenci_id, o.ogrenci_id
                FROM odev_satir s LEFT JOIN odev o ON o.id=s.odev_id
                WHERE s.odev_id IS NOT NULL AND
                    (o.id IS NULL OR o.ogrenci_id IS NULL OR s.ogrenci_id IS NULL
                     OR o.ogrenci_id<>s.ogrenci_id)
            ''').fetchall()
            for sid, owner in rows:
                for value in (sid, owner):
                    if type(value) is int and value > 0:
                        unsafe.add(value)
    return unsafe


def _weekly_plan_coverage(con, student_ids: set[int], day: date) -> dict:
    """Only counts current *coaching* plans, never claims calendar accuracy."""
    tables = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'koc_plan' not in tables:
        return {'state': 'UNVERIFIED', 'with_plan': None, 'without_plan': None,
                'conflict_students': None}
    cols = _columns(con, 'koc_plan')
    if not {'ogrenci_id', 'baslangic_tarihi', 'bitis_tarihi'} <= cols:
        return {'state': 'UNVERIFIED', 'with_plan': None, 'without_plan': None,
                'conflict_students': None}
    active = 'AND aktif=1' if 'aktif' in cols else ''
    # Imported legacy plans may use another date representation. In that case
    # absence of an ISO-matching row does NOT establish absence of a plan.
    bad_date = con.execute(f'''
        SELECT 1 FROM koc_plan WHERE
        (baslangic_tarihi IS NULL OR bitis_tarihi IS NULL OR
         baslangic_tarihi NOT GLOB '[0-9][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]' OR
         bitis_tarihi NOT GLOB '[0-9][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]')
         {active} LIMIT 1
    ''').fetchone()
    if bad_date:
        return {'state': 'UNVERIFIED', 'with_plan': None, 'without_plan': None,
                'conflict_students': None}
    current = day.isoformat()
    rows = con.execute(f'''SELECT ogrenci_id, COUNT(*) FROM koc_plan
        WHERE baslangic_tarihi<=? AND bitis_tarihi>=? {active}
        GROUP BY ogrenci_id''', (current, current)).fetchall()
    counts = {int(sid): int(n) for sid, n in rows if type(sid) is int and sid in student_ids}
    with_plan = sum(sid in counts for sid in student_ids)
    return {'state': 'OBSERVED_COACHING_PLANS', 'with_plan': with_plan,
            'without_plan': len(student_ids) - with_plan,
            'conflict_students': sum(counts.get(sid, 0) > 1 for sid in student_ids),
            'note': 'Koçluk planının varlığı doğrulanır; takvim, içerik veya öğrenme başarısı doğrulanmaz.'}


def summarize_cohort(con: sqlite3.Connection, facts: list[dict],
                     suggestions: list[dict], reviewed: set, *,
                     today: date | None = None, max_cards: int = 5) -> dict:
    """Build a bounded review queue without running per-student inference.

    `facts` and `suggestions` must come from collect_student_facts and
    make_suggestions in the caller's current consistent read transaction.
    An observation is not a diagnosis. A reviewed V11 signal is not repeated.
    """
    day = today or date.today()
    if not isinstance(day, date):
        raise ValueError('Invalid day')
    max_cards = max(1, min(10, int(max_cards)))
    ids = {int(f['id']) for f in facts if type(f.get('id')) is int and f['id'] > 0}
    if len(ids) != len(facts):
        raise ValueError('Invalid or duplicate active student identity')
    unsafe = _unsafe_student_ids(con) & ids
    safe = ids - unsafe
    scope = [f for f in facts if f['id'] in safe]
    overdue_students = [f for f in scope if int(f.get('overdue_recent') or 0) > 0 or
                        int(f.get('overdue_old') or 0) > 0]
    recent = [f for f in overdue_students if int(f.get('overdue_recent') or 0) > 0]
    old = [f for f in overdue_students if not int(f.get('overdue_recent') or 0)]
    no_history = sum(not bool(f.get('has_assignment_history')) for f in scope)
    # V11's reviewed state is checked against the SAME evidence signature, date
    # and student ID. No durable learner 'risk' label is created.
    by_sid = {}
    for s in suggestions:
        ident = review_identity(s)
        if ident is None or ident[0] not in safe or ident in reviewed or s.get('type') != 'overdue':
            continue
        f = s.get('data') or {}
        sid = ident[0]
        if sid in by_sid:
            continue
        by_sid[sid] = {
            'student_id': sid,
            'kind': 'OVERDUE_REVIEW',
            'name': (' '.join(str(f.get(k) or '').strip() for k in ('ad', 'soyad'))).strip()[:100],
            'lesson': str(f.get('problem_lesson') or '').strip()[:80],
            'recent_open_due': max(0, int(f.get('overdue_recent') or 0)),
            'old_open_due': max(0, int(f.get('overdue_old') or 0)),
            'action': 'Ödevin gerçek durumunu öğrenciyle doğrulayın; gerekiyorsa telafi değerlendirin.',
            'basis': 'Tarihi geçmiş, açık ve sahipliği doğrulanmış ödev kayıtları',
            'requires_teacher_approval': True,
        }
    queue = sorted(by_sid.values(), key=lambda c: (
        -int(c['recent_open_due'] > 0), -c['recent_open_due'],
        -c['old_open_due'], c['student_id']))
    plan = _weekly_plan_coverage(con, safe, day)
    # V10 only observes legacy `odev`. Modern `odev_satir` may hold additional
    # independent or more up-to-date work; never call this complete coverage.
    modern_cols = _columns(con, 'odev_satir')
    modern_count = (int(con.execute('SELECT COUNT(*) FROM odev_satir').fetchone()[0])
                    if {'id', 'ogrenci_id'} <= modern_cols else 0)
    partial = modern_count > 0
    return {
        'state': 'REVIEW_REQUIRED' if unsafe else ('PARTIAL_COVERAGE' if partial else 'OBSERVED'),
        'as_of': day.isoformat(),
        'scope': 'active_students_in_this_local_sqlite_only',
        'homework_coverage': 'LEGACY_V10_ONLY_MODERN_NOT_EVALUATED' if partial else 'LEGACY_V10_ONLY',
        'modern_rows_not_evaluated': modern_count,
        'active_students': len(ids),
        'evaluated_students': len(safe),
        'ownership_review_students': len(unsafe),
        'overdue_students': len(overdue_students),
        'recent_overdue_students': len(recent),
        'old_only_overdue_students': len(old),
        'no_assignment_history_students': no_history,
        'pending_overdue_reviews': len(queue),
        'priority_cards': queue[:max_cards],
        'weekly_coaching_plan': plan,
        'evidence_scope': 'verified_owned_legacy_homework_and_weekly_coaching_plan_only',
        'not_mastery_or_risk_diagnosis': True,
        'no_automatic_write': True,
        'remote_verified': False,
    }
