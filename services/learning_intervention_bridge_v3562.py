# -*- coding: utf-8 -*-
"""KoçPilot 360 / v3.5.62 – optional *read-only* learning-intervention drafts.

Integrates the existing V25 recorded question checks, V28 teacher quick-notes,
and the V3561 canonical coaching evidence gate. No legacy/UI mutations, schema
migrations, background threads, messages, or mastery diagnosis. Deliberately
rejects uncertain ownership, malformed counts and future-dated observations.
Call on a coherent SQLite read snapshot, preferably off the UI thread.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import sqlite3

from services.coaching_evidence_hub_v3561 import read_coaching_evidence_hub

_OBSERVATION_COLS = frozenset({'id', 'student_id', 'lesson', 'topic', 'correct',
    'wrong', 'blank', 'mode', 'reason', 'observed_on', 'homework_id'})
_NOTE_COLS = frozenset({'id','student_id','homework_id','lesson','topic','reason_code','updated_at'})
_QUICK_LABELS = {
    'difficulty': 'Zorluk gözlemi (nedeni belirsiz)',
    'concept': 'Kavram güçlüğü gözlemi', 'time': 'Zaman güçlüğü gözlemi',
    'attention': 'Dikkat veya işlem güçlüğü gözlemi',
    'workload': 'İş yükü gözlemi', 'ask': 'Öğrenciye sorulacak konu',
    'easy': 'Kolay geldi gözlemi',
}
_BLOCKED = frozenset({'LINK_REVIEW', 'IDENTITY_MISMATCH', 'UNVERIFIED', 'REVIEW'})


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    """Names are hardcoded, not user-controlled."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return set()
    return {x[1] for x in con.execute('PRAGMA table_info("' + table + '")')}


def _date(raw):
    try:
        if isinstance(raw, datetime):
            return None
        if isinstance(raw, date):
            return raw
        if type(raw) is not str or len(raw) < 10:
            return None
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _norm(raw):
    return ' '.join(str(raw or '').strip().split()).casefold()


def _candidate(kind, lesson, topic, why, step, basis, due=None, *, priority=2):
    return {'kind': kind, 'lesson': lesson[:90], 'topic': topic[:140],
            'why': why[:280], 'teacher_next_step': step[:280], 'basis': basis[:160],
            'suggested_check_on': due.isoformat() if due else None,
            'requires_teacher_approval': True, 'auto_assignment': False,
            'priority_order': priority, 'learning_diagnosis': False}


def read_learning_intervention_draft(con: sqlite3.Connection, student_id: int, *,
                                     today: date | None = None,
                                     hub_card: dict | None = None,
                                     max_recommendations: int = 3) -> dict:
    """Conservative at-most-3 suggestion card, with explicit provenance.

    `hub_card` enables reuse of a same-transaction V3561 card, but must have
    matching schema, student ID and reference date. Trusted callers must
    obtain it from read_coaching_evidence_hub, not client-submitted JSON.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Positive verified student ID required')
    day = today if today is not None else date.today()
    if type(day) is not date:
        raise ValueError('today must be a date')
    if type(max_recommendations) is not int or not 1 <= max_recommendations <= 3:
        raise ValueError('max_recommendations must be 1 to 3')

    old_factory = con.row_factory
    try:
        con.row_factory = sqlite3.Row
        student_cols = _columns(con, 'ogrenci')
        if not {'id', 'aktif'} <= student_cols:
            raise ValueError('Student source is not verifiable')
        if con.execute('SELECT 1 FROM ogrenci WHERE id=? AND aktif=1', (student_id,)).fetchone() is None:
            raise ValueError('No active student for the supplied ID')

        if hub_card is None:
            hub_card = read_coaching_evidence_hub(con, student_id, today=day)
        elif (not isinstance(hub_card, dict) or hub_card.get('schema') != 'coaching_evidence_hub_v3561'
              or hub_card.get('student_id') != student_id or hub_card.get('as_of') != day.isoformat()
              or hub_card.get('read_only') is not True or hub_card.get('auto_change_allowed') is not False):
            raise ValueError('Untrusted or stale coaching evidence hub')

        common = {'schema': 'learning_intervention_bridge_v3562',
                  'student_id': student_id, 'as_of': day.isoformat(),
                  'read_only': True, 'auto_change_allowed': False,
                  'requires_teacher_approval': True, 'homework_is_not_mastery': True,
                  'automatic_messages': False, 'automatic_assignments': False,
                  'mastery_verified': False, 'causality_verified': False,
                  'source_hub_state': hub_card.get('state'),
                  'limitations': ['Ödev tamamlamak öğrenme kanıtı değildir.',
                     'Öğretmen gözlemi tek başına zorlanmanın kök nedenini kanıtlamaz.',
                     'Tekrar günleri planlama önerisidir; kişisel unutma yüzdesi değildir.']}

        if (hub_card.get('state') in _BLOCKED or
            hub_card.get('evidence_level') in ('BLOCKED', 'UNVERIFIED') or
            hub_card.get('state') is None):
            return {**common, 'state': 'DATA_REVIEW', 'recommendations': [],
                    'source_quality': 'BLOCKED',
                    'next_step': 'Önce öğrenci ve ödev kayıtlarının doğruluğunu kontrol edin.',
                    'evidence_counts': {'valid_checks': 0, 'quick_notes': 0, 'excluded_checks': 0}}

        observation_cols = _columns(con, 'adaptive_observation_v25')
        note_cols = _columns(con, 'adaptive_quick_note_v28')
        if observation_cols and not _OBSERVATION_COLS <= observation_cols:
            return {**common, 'state': 'SOURCE_REVIEW', 'recommendations': [],
                    'source_quality': 'UNVERIFIED', 'next_step': 'Öğrenme ölçüm tablosunun şemasını doğrulayın.',
                    'evidence_counts': {'valid_checks': 0, 'quick_notes': 0, 'excluded_checks': 0}}
        if note_cols and not _NOTE_COLS <= note_cols:
            return {**common, 'state': 'SOURCE_REVIEW', 'recommendations': [],
                    'source_quality': 'UNVERIFIED', 'next_step': 'Hızlı Teşhis tablosunun şemasını doğrulayın.',
                    'evidence_counts': {'valid_checks': 0, 'quick_notes': 0, 'excluded_checks': 0}}

        checks = defaultdict(list)
        notes = defaultdict(list)
        excluded = 0
        if observation_cols:
            obs_rows = con.execute('''SELECT id,student_id,homework_id,lesson,topic,mode,reason,
                       correct,wrong,blank,observed_on
                FROM adaptive_observation_v25 WHERE student_id=?
                ORDER BY observed_on DESC,id DESC LIMIT 250''', (student_id,)).fetchall()
            for r in obs_rows:
                lesson, topic = str(r['lesson'] or '').strip(), str(r['topic'] or '').strip()
                check_day = _date(r['observed_on'])
                numbers = (r['correct'], r['wrong'], r['blank'])
                # Never infer a percentage from malformed or empty observations.
                if (not lesson or not topic or not check_day or check_day > day
                    or any(type(v) is not int or v < 0 or v > 10000 for v in numbers)
                    or not 1 <= sum(numbers) <= 10000):
                    excluded += 1
                    continue
                if r['homework_id'] is not None:
                    # A related homework ID must really belong to student and cluster.
                    # Any conflict blocks *all* academic proposals, not just this row.
                    owner = con.execute('''SELECT 1 FROM odev o JOIN odev_kume k ON k.id=o.kume_id
                        WHERE o.id=? AND o.ogrenci_id=? AND k.ogrenci_id=?''',
                        (r['homework_id'], student_id, student_id)).fetchone()
                    if not owner:
                        return {**common, 'state': 'DATA_REVIEW', 'recommendations': [],
                                'source_quality': 'BLOCKED',
                                'next_step': 'Ölçüme bağlı ödevin öğrenci sahipliği uyuşmuyor; kayıtları doğrulayın.',
                                'evidence_counts': {'valid_checks':0,'quick_notes':0,'excluded_checks':excluded}}
                k = (_norm(lesson), _norm(topic))
                checks[k].append({'lesson': lesson, 'topic': topic, 'date': check_day,
                                  'correct': numbers[0], 'total': sum(numbers),
                                  'mode': str(r['mode'] or '').strip(),
                                  'reason': str(r['reason'] or '').strip()})

        if note_cols:
            note_rows = con.execute('''SELECT id,student_id,homework_id,lesson,topic,reason_code,updated_at
                FROM adaptive_quick_note_v28 WHERE student_id=?
                ORDER BY updated_at DESC,id DESC LIMIT 60''', (student_id,)).fetchall()
            for r in note_rows:
                nd = _date(r['updated_at'])
                lesson, topic = str(r['lesson'] or '').strip(), str(r['topic'] or '').strip()
                if (not lesson or not topic or nd is None or nd > day
                    or r['reason_code'] not in _QUICK_LABELS):
                    continue
                if r['homework_id'] is not None:
                    owner = con.execute('''SELECT 1 FROM odev o JOIN odev_kume k ON k.id=o.kume_id
                        WHERE o.id=? AND o.ogrenci_id=? AND k.ogrenci_id=?''',
                        (r['homework_id'], student_id, student_id)).fetchone()
                    if not owner:
                        return {**common, 'state': 'DATA_REVIEW', 'recommendations': [],
                                'source_quality': 'BLOCKED',
                                'next_step': 'Hızlı Teşhis kaydına bağlı ödev uyuşmuyor; kayıtları doğrulayın.',
                                'evidence_counts': {'valid_checks':0,'quick_notes':0,'excluded_checks':excluded}}
                notes[(_norm(lesson), _norm(topic))].append({
                    'lesson': lesson, 'topic': topic, 'date': nd,
                    'code': r['reason_code']})

        candidates = []
        for key in checks.keys() | notes.keys():
            seq = sorted(checks[key], key=lambda c:c['date'], reverse=True)
            qnotes = sorted(notes[key],key=lambda n:n['date'],reverse=True)
            latest = seq[0] if seq else None
            note = qnotes[0] if qnotes else None
            lesson = (latest or note)['lesson']
            topic = (latest or note)['topic']
            recent_checks = [c for c in seq if c['total'] >= 5]
            independent_days = {c['date'] for c in recent_checks}
            latest_accuracy = latest['correct'] / latest['total'] if latest else None
            if (latest and latest['total'] >= 5 and latest_accuracy < 0.65
                and len(independent_days) >= 2 and
                any(c['date'] != latest['date'] and c['correct']/c['total'] < .65 for c in recent_checks)):
                candidates.append(_candidate('TARGETED_REVIEW', lesson, topic,
                    'Farklı günlerde en az iki ölçümde düşük doğruluk gözlendi; neden henüz bilinmiyor.',
                    'Öğrenciyle hata türlerini inceleyin; kısa bir hedefli kontrol veya telafi taslağı hazırlayın.',
                    'V25 soru sonuçları, farklı ölçüm günleri', priority=0))
                continue
            if latest and latest['total'] >= 5 and latest_accuracy < .65:
                candidates.append(_candidate('CHECK_ERRORS', lesson, topic,
                    'Son kayıtlı kısa ölçümde doğruluk düşüktü; tek ölçüm kesin öğrenme hükmü vermez.',
                    'Hata türünü konuşup başka bir günde kısa bağımsız ölçüm yapın.',
                    'V25 soru sonuçları', priority=1))
                continue
            if note and note['code'] != 'easy' and (not latest or latest['date'] <= note['date']):
                candidates.append(_candidate('CLARIFY_OBSERVATION',lesson,topic,
                    'Hızlı Teşhis: '+_QUICK_LABELS[note['code']]+'; gözlem kesin neden değildir.',
                    'Öğrenciye kısa bir soru sorun veya 5 soruluk kontrol uygulayın.',
                    'V28 öğretmen gözlemi', priority=2))
                continue
            if latest and latest['total'] >= 5:
                elapsed = (day-latest['date']).days
                # A bounded reminder, not a claimed actual forgetting percentage.
                # Not called mastery even after two strong checks.
                # Use conservative fixed windows until personalization is validated.
                gap = 7 if len(independent_days) >= 2 else 2
                if elapsed >= gap:
                    candidates.append(_candidate('SPACED_CHECK',lesson,topic,
                        f'Son kısa ölçümün üzerinden {elapsed} gün geçti; hatırlama düzeyi bugün bilinmiyor.',
                        'Geri getirme veya karma kısa yoklamayla hatırlamayı yeniden kontrol edin.',
                        'V25 ölçüm tarihi; öneri aralığı 2 veya 7 gün', latest['date']+timedelta(days=gap),
                        priority=3))

        candidates.sort(key=lambda r: (r['priority_order'], r['lesson'].casefold(), r['topic'].casefold()))
        chosen = candidates[:max_recommendations]
        # Deliberately do not mutate the V3561 suggestions, state or ordering.
        return {**common, 'state': 'REVIEW_SUGGESTED' if chosen else 'NO_LEARNING_PRIORITY',
                'source_quality': 'LOCAL_RECORDED_OBSERVATIONS' if checks or notes else 'NO_OBSERVATIONS',
                'recommendations': chosen,
                'evidence_counts': {'valid_checks': sum(map(len,checks.values())),
                                   'quick_notes': sum(map(len,notes.values())),
                                   'excluded_checks': excluded},
                'next_step': (chosen[0]['teacher_next_step'] if chosen else
                    'Yeni bir öğrenme kanıtı yoksa normal takip sürsün; ödev tamamlanmasını öğrenme olarak yorumlamayın.')}
    finally:
        con.row_factory = old_factory
