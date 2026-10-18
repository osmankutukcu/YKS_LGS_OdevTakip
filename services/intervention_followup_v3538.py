# -*- coding: utf-8 -*-
"""V3.5.38: read-only follow-up scheduling on *existing* approved V11 interventions.

No tables, background writes, automatic treatment decisions or causal claims.
Teacher approval, qualitative feedback and measurement recording remain in the
existing Adaptive Follow-up UI/V11 services. Only local SQLite is consulted.
"""
from __future__ import annotations

from datetime import date, timedelta
import sqlite3

from services.adaptive_outcomes_v11 import evaluate_intervention, list_interventions


def _as_day(value):
    if value is None:
        return date.today()
    if type(value) is date:
        return value
    if type(value) is str:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() == value:
            return parsed
    raise ValueError('İzlem tarihi geçerli bir YYYY-AA-GG tarihi olmalı.')


def _student_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Doğrulanmış öğrenci kimliği gerekli.')
    return value


def _table_exists(con, table):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _summarize_record(con, sid, entry, day):
    """One previously teacher-approved ledger row; no external record update."""
    if int(entry['student_id']) != sid:
        raise ValueError('İzlem öğrenci kapsamı uyuşmuyor.')
    applied = _as_day(entry['applied_on'])
    if applied > day:
        return None  # no fictional future follow-up
    days = (day - applied).days
    report = evaluate_intervention(con, sid, int(entry['id']), as_of=day)
    review = report['teacher_review']
    ready = report['ready']
    if review in ('helpful', 'not_helpful', 'unclear'):
        state = 'TEACHER_REVIEWED'
        reason = 'Öğretmen değerlendirmesi kayıtlıdır; sonuç nedensellik kanıtı değildir.'
    elif ready:
        state = 'MEASUREMENT_REVIEW_DUE'
        reason = 'Önce/sonra bağımsız ölçüm mevcut; fark öğretmen tarafından yorumlanmalı.'
    elif days > 45:
        state = 'MEASUREMENT_OVERDUE'
        reason = '45 günlük izlem penceresi geçmiş; bağımsız ölçüm yeterli değil.'
    elif days >= 14:
        state = 'DAY14_RECHECK_DUE'
        reason = '14. gün kontrolü geldi; yeterli karşılaştırılabilir ölçüm yok.'
    elif days >= 7:
        state = 'DAY7_RECHECK_DUE'
        reason = '7. gün kontrolü geldi; bağımsız ölçüm durumu değerlendirilmeli.'
    else:
        state = 'WAITING_FOR_DAY7'
        reason = f'İlk gözden geçirme { (applied + timedelta(days=7)).isoformat() } tarihinde.'
    return {
        'id': int(entry['id']), 'student_id': sid, 'lesson': str(entry['lesson']),
        'topic': str(entry['topic']), 'action_code': str(entry['action_code']),
        'applied_on': applied.isoformat(), 'days_since': days,
        'day7': (applied + timedelta(days=7)).isoformat(),
        'day14': (applied + timedelta(days=14)).isoformat(),
        'status': state, 'reason': reason, 'teacher_review': review,
        'measurement_ready': bool(ready),
        'delta_percentage_points': report['delta_percentage_points'] if ready else None,
        'baseline_days': report['baseline']['days'],
        'followup_days': report['followup']['days'],
        'next_step': report['next_step'],
        'causality_not_established': True,
    }


def read_student_followups(con: sqlite3.Connection, student_id: int, *, as_of=None, limit: int = 3) -> dict:
    """Optional extra Student360/coach card: read-only; same student, same snapshot."""
    sid, day = _student_id(student_id), _as_day(as_of)
    if type(limit) is not int or limit < 1 or limit > 15:
        raise ValueError('İzlem sayısı 1-15 olmalı.')
    entries = list_interventions(con, sid, limit=max(limit, 15))
    items = []
    for entry in entries:
        item = _summarize_record(con, sid, entry, day)
        if item is not None:
            items.append(item)
        if len(items) == limit:
            break
    attention_states = {'MEASUREMENT_REVIEW_DUE', 'MEASUREMENT_OVERDUE',
                        'DAY14_RECHECK_DUE', 'DAY7_RECHECK_DUE'}
    return {
        'student_id': sid, 'as_of': day.isoformat(),
        'state': 'OBSERVED' if items else 'NO_APPROVED_INTERVENTION',
        'records': items,
        'attention_count': sum(item['status'] in attention_states for item in items),
        'automated_records': False, 'student_data_written': False,
        'remote_verified': False,
        'warning': 'Ödev tiki ve önce/sonra değişim nedensellik veya müdahale etkisi kanıtı değildir.',
    }


def scan_cohort_followups(con: sqlite3.Connection, *, as_of=None,
                          max_scan: int = 5000, max_cards: int = 3) -> dict:
    """Bounded institution snapshot, built on V11 teacher-approved ledger only.

    Cohort counts mean *dates reached on the local ledger*, not verified academic
    need or measured effectiveness. If the cap is hit, report partial coverage.
    """
    day = _as_day(as_of)
    if type(max_scan) is not int or not 1 <= max_scan <= 10000:
        raise ValueError('Tarama üst sınırı 1-10000 olmalı.')
    if type(max_cards) is not int or not 1 <= max_cards <= 10:
        raise ValueError('Kart üst sınırı 1-10 olmalı.')
    common = {'as_of': day.isoformat(), 'remote_verified': False,
              'source': 'local_teacher_approved_v11_only',
              'student_data_written': False, 'messages_sent': False}
    if not _table_exists(con, 'adaptive_intervention_v11'):
        return {**common, 'state': 'NO_APPROVED_INTERVENTIONS', 'date_due_candidates': 0,
                'evaluated_records': 0, 'priority_cards': []}
    if not _table_exists(con, 'ogrenci'):
        return {**common, 'state': 'UNVERIFIED', 'date_due_candidates': None,
                'evaluated_records': 0, 'priority_cards': []}
    fields = {r[1] for r in con.execute('PRAGMA table_info(ogrenci)').fetchall()}
    active = ' AND o.aktif=1 ' if 'aktif' in fields else ''
    # The most recent intervention for each learner, not the last intervention
    # globally (which would hide low-frequency learners). Older interventions
    # remain readable in Student360 via read_student_followups.
    query = f'''WITH ranked AS (
      SELECT i.id, i.student_id, i.applied_on, i.teacher_review,
             ROW_NUMBER() OVER (PARTITION BY i.student_id
                                ORDER BY i.applied_on DESC, i.id DESC) AS rn
        FROM adaptive_intervention_v11 i JOIN ogrenci o ON o.id=i.student_id
       WHERE (i.applied_on<=? OR date(i.applied_on) IS NULL) {active}
    ) SELECT id,student_id,applied_on FROM ranked
       WHERE rn=1 AND COALESCE(teacher_review,'')=''
       ORDER BY applied_on ASC,id ASC LIMIT ?'''
    rows = con.execute(query, (day.isoformat(), max_scan + 1)).fetchall()
    limited = len(rows) > max_scan
    rows = rows[:max_scan]
    dates_reached = []
    invalid = 0
    for iid, sid, applied in rows:
        try:
            started = _as_day(applied)
        except (ValueError, TypeError):
            invalid += 1
            continue
        if started <= day - timedelta(days=7):
            dates_reached.append((int(iid), int(sid), started))
    cards = []
    # Only evaluate a small number of ranked student records; expensive
    # observation reads must not block the UI worker on a large institution.
    for _, sid, _ in dates_reached[:max_cards]:
        report = read_student_followups(con, sid, as_of=day, limit=1)
        if report['records'] and report['records'][0]['status'] != 'TEACHER_REVIEWED':
            item = report['records'][0]
            cards.append({'student_id': sid, 'status': item['status'],
                          'lesson': item['lesson'], 'topic': item['topic'],
                          'next_step': item['reason']})
    return {**common,
            'state': 'PARTIAL_COVERAGE' if limited or invalid else 'OBSERVED',
            'evaluated_records': len(rows), 'date_due_candidates': len(dates_reached),
            'invalid_date_rows': invalid, 'priority_cards': cards,
            'meaning': 'Tarihi gelen kayıtlar, öğretmen müdahale izlem defterinin yerel kayıtlarıdır; akademik tanı değildir.'}
