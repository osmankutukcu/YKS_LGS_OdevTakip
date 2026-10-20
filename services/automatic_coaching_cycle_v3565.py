# -*- coding: utf-8 -*-
"""KoçPilot 360 v3.5.65 - read-only, on-demand coaching cycle coordination.

Uses existing V3561 canonical evidence, V3562 independent checks/quick notes,
and V3538 APPROVED follow-up records. Never writes homework, changes a checkbox,
assumes homework completion is mastery, sends messages, or creates interventions.
Must run on one caller-managed, query-only SQLite read transaction off the UI thread.
"""
from __future__ import annotations

from datetime import date
import sqlite3

from services.coaching_evidence_hub_v3561 import read_coaching_evidence_hub
from services.learning_intervention_bridge_v3562 import read_learning_intervention_draft

_BLOCKED = frozenset({'LINK_REVIEW', 'IDENTITY_MISMATCH', 'UNVERIFIED', 'REVIEW'})
_KIND = {
    'TARGETED_REVIEW': 'TARGETED_REVIEW',
    'CHECK_ERRORS': 'INDEPENDENT_RECHECK',
    'CLARIFY_OBSERVATION': 'CLARIFY_OBSERVATION',
    'SPACED_CHECK': 'SPACED_RETRIEVAL',
}


def _casefold(text):
    return ' '.join(str(text or '').split()).casefold()


def _step(kind, *, lesson='', topic='', reason='', next_step='', due=None, source='', priority=3):
    return {
        'kind': kind, 'lesson': str(lesson)[:90], 'topic': str(topic)[:140],
        'reason': str(reason)[:300], 'next_step': str(next_step)[:300],
        'suggested_on': due, 'source': source, 'priority': priority,
        'read_only': True, 'teacher_approval_required': True,
        'auto_assignment': False, 'auto_message': False,
        'causality_verified': False, 'mastery_verified': False,
    }


def _base(sid, day):
    return {'schema': 'automatic_coaching_cycle_v3565', 'student_id': sid,
            'as_of': day.isoformat(), 'state': 'NO_PRIORITY',
            'read_only': True, 'teacher_approval_required': True,
            'auto_change_allowed': False, 'automatic_assignments': False,
            'automatic_messages': False, 'homework_is_not_mastery': True,
            'causality_verified': False, 'mastery_verified': False,
            'next_actions': [], 'pending_count': 0,
            'source_states': {}, 'reason': '',
            'limitations': 'Ödev tiki öğrenme kanıtı değildir; öneriler öğretmen incelemesi içindir.'}


def combine_cycle_sources(hub: dict, learning: dict, followups: dict | None, *,
                          student_id: int, today: date, max_actions: int = 2) -> dict:
    """Pure fail-closed, deterministic and bounded priority reducer.

    Caller must produce all arguments inside the same database read transaction.
    Passing an arbitrary object is not an authorization for any action; no writes.
    """
    if type(student_id) is not int or student_id <= 0 or type(today) is not date:
        raise ValueError('Verified student and date required')
    if type(max_actions) is not int or not 1 <= max_actions <= 3:
        raise ValueError('Action limit must be 1-3')
    base = _base(student_id, today)
    expected = today.isoformat()
    if (not isinstance(hub, dict) or hub.get('schema') != 'coaching_evidence_hub_v3561'
        or hub.get('student_id') != student_id or hub.get('as_of') != expected
        or hub.get('read_only') is not True or hub.get('auto_change_allowed') is not False
        or not isinstance(learning, dict)
        or learning.get('schema') != 'learning_intervention_bridge_v3562'
        or learning.get('student_id') != student_id or learning.get('as_of') != expected
        or learning.get('read_only') is not True or learning.get('auto_change_allowed') is not False
        or learning.get('automatic_assignments') is not False):
        return {**base, 'state': 'DATA_REVIEW', 'reason': 'Ortak veri kaynaklarının öğrenci/tarih/güvenlik eşleşmesi doğrulanamadı.'}
    hub_state, learning_state = hub.get('state'), learning.get('state')
    base['source_states'] = {'homework': hub_state, 'learning': learning_state,
                             'followup': 'NO_LEDGER' if followups is None else (followups.get('state') if isinstance(followups, dict) else 'INVALID')}
    if (hub_state in _BLOCKED or hub.get('evidence_level') in ('UNVERIFIED', 'BLOCKED')
        or hub.get('priority') == 'DATA_REVIEW'
        or learning_state in ('DATA_REVIEW', 'SOURCE_REVIEW', 'UNVERIFIED')
        or learning.get('source_quality') in ('UNVERIFIED', 'BLOCKED')
        or learning_state not in ('REVIEW_SUGGESTED', 'NO_LEARNING_PRIORITY')):
        return {**base, 'state': 'DATA_REVIEW',
                'reason': 'Önce öğrenci, ödev ve öğrenme kayıtlarının bütünlüğünü inceleyin.'}

    if followups is not None:
        if (not isinstance(followups, dict) or followups.get('student_id') != student_id
            or followups.get('as_of') != expected
            or followups.get('state') not in ('OBSERVED', 'NO_APPROVED_INTERVENTION')
            or followups.get('student_data_written') is not False
            or not isinstance(followups.get('records'), list)):
            return {**base, 'state': 'DATA_REVIEW', 'reason': 'Müdahale izlem kaynağı doğrulanamadı.'}
        for entry in followups['records']:
            if not isinstance(entry, dict) or entry.get('student_id') != student_id:
                return {**base, 'state': 'DATA_REVIEW', 'reason': 'Müdahale kaydında öğrenci eşleşmiyor.'}

    ranked = []
    if followups:
        due = {'MEASUREMENT_REVIEW_DUE': 0, 'MEASUREMENT_OVERDUE': 0,
               'DAY14_RECHECK_DUE': 0, 'DAY7_RECHECK_DUE': 0}
        for entry in followups['records']:
            state = entry.get('status')
            if state not in due:
                continue
            ranked.append(_step('INTERVENTION_FOLLOWUP',
                lesson=entry.get('lesson'), topic=entry.get('topic'),
                reason=entry.get('reason') or 'Onaylı müdahale sonrası izlem gerekiyor.',
                next_step='Mevcut müdahale izleminde bağımsız ölçümü ve öğretmen yorumunu inceleyin.',
                source='v3538_onayli_mudahale', priority=due[state]))

    observations = learning.get('recommendations') or []
    if not isinstance(observations, list):
        return {**base, 'state': 'DATA_REVIEW', 'reason': 'Öğrenme öneri biçimi doğrulanamadı.'}
    for item in observations[:3]:
        if (not isinstance(item, dict) or item.get('requires_teacher_approval') is not True
            or item.get('auto_assignment') is not False
            or item.get('kind') not in _KIND
            or not isinstance(item.get('lesson'), str) or not item['lesson'].strip()
            or not isinstance(item.get('topic'), str) or not item['topic'].strip()):
            return {**base, 'state': 'DATA_REVIEW', 'reason': 'Öğrenme öneri güvenlik alanları doğrulanamadı.'}
        due = item.get('suggested_check_on')
        if due is not None:
            try:
                due_day = date.fromisoformat(due)
                if due_day > today:
                    continue  # future check, don't interrupt teacher today
            except (TypeError, ValueError):
                return {**base, 'state': 'DATA_REVIEW', 'reason': 'Önerilen kontrol tarihi geçersiz.'}
        ranked.append(_step(_KIND[item['kind']], lesson=item.get('lesson'),
                            topic=item.get('topic'), reason=item.get('why'),
                            next_step=item.get('teacher_next_step'), due=due,
                            source=item.get('basis') or 'v3562_olcum',
                            priority=1 if item['kind'] == 'TARGETED_REVIEW' else 2))

    # A completed assignment is only a reason to ask for a *possible*
    # independent check, not a learning judgement or an urgent diagnosis.
    counts = learning.get('evidence_counts')
    if not isinstance(counts, dict):
        return {**base, 'state': 'DATA_REVIEW', 'reason': 'Ölçüm sayıları doğrulanamadı.'}
    n_checks = counts.get('valid_checks')
    if type(n_checks) is not int or n_checks < 0:
        return {**base, 'state': 'DATA_REVIEW', 'reason': 'Ölçüm sayıları güvenilir değil.'}
    # Homework aggregate can be incomplete, so never infer *which* topic or
    # when an assignment was completed from the count alone.
    if (n_checks == 0 and learning_state == 'NO_LEARNING_PRIORITY'
        and hub.get('evidence_level') in ('VERIFIED_LOCAL_HOMEWORK', 'LOCAL_RECORDS_ONLY', 'EXISTING_COACH_EVIDENCE', 'LOCAL_COACHING_PLAN')
        and isinstance(hub.get('sources'), dict)):
        # Only the canonical reader may supply student-specific completion.
        # We intentionally do not use a generic "has homework" guess here.
        canonical = hub.get('canonical_focus')
        if isinstance(canonical, dict) and canonical.get('student_id') == student_id \
           and canonical.get('state') == 'OBSERVED' and \
           type(canonical.get('completed_tasks')) is int and canonical['completed_tasks'] > 0:
            ranked.append(_step('OPTIONAL_INDEPENDENT_CHECK',
                reason='Tamamlanan ödev var, ancak bağımsız kısa ölçüm kaydı bulunamadı.',
                next_step='Uygun gördüğünüz bir kazanım için 5 soruluk kısa kontrol uygulayın.',
                source='v3535_tamamlanma_v3562_olcum_yok', priority=4))

    ranked.sort(key=lambda s: (s['priority'], _casefold(s['lesson']), _casefold(s['topic']), s['kind']))
    chosen, seen = [], set()
    for item in ranked:
        key = (_casefold(item['lesson']), _casefold(item['topic']))
        if key in seen:  # the most important step for one topic wins
            continue
        seen.add(key)
        chosen.append(item)
        if len(chosen) >= max_actions:
            break
    if chosen:
        return {**base, 'state': 'ACTION_SUGGESTED', 'next_actions': chosen,
                'pending_count': len(chosen), 'reason': chosen[0]['reason']}
    return {**base, 'state': 'NO_PRIORITY', 'reason': 'Bugün yeni bir koçluk eylemi saptanmadı; bu öğrenmenin kanıtlandığı anlamına gelmez.'}


def read_automatic_coaching_cycle(con: sqlite3.Connection, student_id: int, *,
                                  today: date | None = None, max_actions: int = 2) -> dict:
    """On-demand, no timer/polling. Existing sources are consulted on one snapshot."""
    day = date.today() if today is None else today
    if type(day) is not date or type(student_id) is not int or student_id <= 0:
        raise ValueError('Student ID or date invalid')
    # Existing v3561 source performs canonical ownership validation.
    hub = read_coaching_evidence_hub(con, student_id, today=day)
    learning = read_learning_intervention_draft(con, student_id, today=day, hub_card=hub)
    followups = None
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='adaptive_intervention_v11'").fetchone():
        from services.intervention_followup_v3538 import read_student_followups
        try:
            followups = read_student_followups(con, student_id, as_of=day, limit=2)
        except (sqlite3.Error, KeyError, TypeError, ValueError, OverflowError):
            base = _base(student_id, day)
            return {**base, 'state': 'DATA_REVIEW', 'reason': 'Müdahale izlem kaydı okunamadı; öneri gizlendi.'}
    # Only read canonical completion counts when independent measurements are absent.
    # This optional read does not map completion to any specific topic or mastery.
    if (learning.get('source_quality') == 'NO_OBSERVATIONS'
        and hub.get('evidence_level') in ('VERIFIED_LOCAL_HOMEWORK', 'LOCAL_RECORDS_ONLY', 'EXISTING_COACH_EVIDENCE', 'LOCAL_COACHING_PLAN')
        and hub.get('priority') != 'DATA_REVIEW'):
        from services.canonical_homework_evidence_v3535 import scan_canonical_homework
        focus = scan_canonical_homework(con, today=day, focus_student_id=student_id).get('focus_student')
        hub = {**hub, 'canonical_focus': focus}
    return combine_cycle_sources(hub, learning, followups,
                                 student_id=student_id, today=day, max_actions=max_actions)
