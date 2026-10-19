# -*- coding: utf-8 -*-
"""V3.5.46: bounded, read-only integration of the fourth mobile PDF.

Existing canonical homework, comparable exam, coaching-plan and approved
intervention-followup engines are the sources of truth. No database migrations,
remote requests, student updates, automatic messages, or automatic assignments.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from contextlib import closing
import sqlite3
from urllib.parse import quote

from services.smart_mobile_pdf_v3545 import build_pocket_snapshot
from services.mobile_agenda_pdf_v3541 import normalize_mobile_number
from services.intervention_advisor_v3537 import build_intervention_draft
from services.academic_actions_v3536 import read_student_action_card
from services.intervention_followup_v3538 import read_student_followups

_MAX_STUDENTS = 40
_DUE = frozenset({'MEASUREMENT_REVIEW_DUE','MEASUREMENT_OVERDUE',
                  'DAY14_RECHECK_DUE','DAY7_RECHECK_DUE'})


def _key(student_id):
    if type(student_id) is int and student_id > 0:
        return student_id
    if type(student_id) is str and student_id.isascii() and student_id.isdecimal():
        n = int(student_id)
        if n > 0 and str(n) == student_id:
            return n
    return None


def _fallback_student(message, *, state='UNVERIFIED'):
    return {'state': state, 'summary': message, 'homework': None,
            'exam': None, 'coaching_plan': None, 'followup': None,
            'recommendations': [], 'contact_allowed': False,
            'verified': False, 'requires_teacher_approval': True}


def _contact_verification(con, sid, snapshot_entry):
    """Cross-check recipient identity AND stored numbers in the SAME DB snapshot.

    This is a stricter rule for the *new fourth PDF*, never the legacy agenda.
    """
    cols = {r[1] for r in con.execute('PRAGMA table_info(ogrenci)')}
    if not {'ad', 'soyad', 'ogr_tel', 'veli_tel1'} <= cols:
        return False
    row = con.execute('SELECT ad,soyad,ogr_tel,veli_tel1 FROM ogrenci '
                      'WHERE id=? AND aktif=1', (sid,)).fetchone()
    if row is None:
        return False
    stored_name = ' '.join(str(x or '').strip() for x in row[:2]).strip()
    pdf_name = str(snapshot_entry.get('name') or '').strip()
    if ' '.join(pdf_name.casefold().split()) != ' '.join(stored_name.casefold().split()):
        return False
    for field, stored in (('phone', row[2]), ('parent_phone', row[3])):
        preview = normalize_mobile_number(snapshot_entry.get(field))
        actual = normalize_mobile_number(stored)
        if preview != actual:
            return False
    return not snapshot_entry.get('contact_conflict', False)


def _verified_student(con, sid, day, snapshot_entry):
    # One canonical ownership/academic observation, reused for intervention.
    card = read_student_action_card(con, sid, today=day)
    if card.get('student_id') != sid or card.get('state') == 'LINK_REVIEW':
        return _fallback_student('Öğrenci–ödev sahiplik bağı denetlenmeli; iletişim kapatıldı.',
                                 state='LINK_REVIEW')
    draft = build_intervention_draft(con, sid, today=day, action_card=card)
    if draft.get('student_id') != sid or draft.get('state') == 'DATA_REVIEW':
        return _fallback_student('Öğrenci bağlantısı doğrulanamadı; iletişim kapatıldı.',
                                 state='LINK_REVIEW')
    homework = card.get('homework') or {}
    plan = card.get('plan') or {}
    exam = draft.get('exam') or {}
    recommendations = []
    for entry in (draft.get('recommendations') or [])[:3]:
        if isinstance(entry, dict):
            recommendations.append(str(entry.get('title') or '')[:120])
    followup = {'state':'SOURCE_UNVERIFIED', 'attention_count':None}
    try:
        follow = read_student_followups(con, sid, as_of=day, limit=2)
        if follow.get('student_id') == sid:
            followup = {'state': follow.get('state'),
                        'attention_count': follow.get('attention_count'),
                        'statuses': [r.get('status') for r in follow.get('records',[])][:2]}
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        pass  # Never treat inaccessible followup records as known empty.
    partial = (card.get('state') in ('UNVERIFIED', 'PARTIAL_COVERAGE')
               or card.get('global_coverage') != 'OBSERVED'
               or plan.get('state') in ('UNVERIFIED', 'PARTIAL')
               or exam.get('state') == 'SOURCE_UNVERIFIED'
               or followup.get('state') == 'SOURCE_UNVERIFIED')
    summary = (recommendations[0] if recommendations else
               str(card.get('next_step') or 'Akademik kaynaklar için ek doğrulama gerekli.'))
    return {
        'state': draft.get('state') or 'UNVERIFIED', 'summary': summary[:240],
        'homework': {
            'state': homework.get('state'), 'total': homework.get('canonical_tasks'),
            'completed': homework.get('completed_tasks'),
            'overdue': homework.get('overdue_open_tasks'),
            'undated': homework.get('undated_tasks')},
        'exam': {'state':exam.get('state', 'SOURCE_UNVERIFIED'),
                 'signals': [{'course': str(s.get('course') or '')[:70],
                              'net_delta': s.get('net_delta'),
                              'exam_type': s.get('exam_type')}
                             for s in (exam.get('signals') or [])[:2] if isinstance(s, dict)]},
        'coaching_plan': {'state': plan.get('state', 'UNVERIFIED'),
                          'summary': str(plan.get('summary') or 'Plan kanıtı doğrulanamadı.')[:180]},
        'followup': followup, 'recommendations': recommendations,
        'verified': True, 'partial': partial,
        'contact_allowed': _contact_verification(con, sid, snapshot_entry),
        'requires_teacher_approval': True}


def collect_mobile_pdf_context(database_path, schedule, days, *, today=None,
                               max_students=_MAX_STUDENTS):
    """Read only verified schedule student IDs from current local database.

    When there are too many students only a bounded subset is analyzed and
    coverage is prominently marked PARTIAL; never claim that others are clear.
    Failure to access DB yields a labelled UNVERIFIED document, not silent OK.
    """
    if type(max_students) is not int or not 1 <= max_students <= 100:
        raise ValueError('max_students must be in range 1..100')
    day = today or date.today()
    if type(day) is not date:
        raise ValueError('today must be date')
    snap = build_pocket_snapshot(schedule, days)
    subjects = snap['students']
    identity_map = {}
    unverified_ids = 0
    for entry in subjects:
        sid = _key(entry['id'])
        if sid is not None and sid not in identity_map:
            identity_map[sid] = entry
        elif sid is None:
            unverified_ids += 1
    # Review attention students before routine checks; sorting is deterministic.
    ordered = sorted(identity_map, key=lambda sid:(not identity_map[sid]['attention'], sid))
    selected = ordered[:max_students]
    result = {'as_of':datetime.now().strftime('%Y-%m-%d %H:%M'),
              'scope':'yerel SQLite / oluşturulma anı', 'live':False,
              'remote_verified':False, 'student_count':len(subjects),
              'verified_count':0, 'evaluated_count':0,
              'not_evaluated_count':len(ordered)-len(selected)+unverified_ids,
              'student_cards':{}, 'source_state':'UNVERIFIED',
              'warnings':[], 'requires_teacher_approval':True,
              'contact_blocked_count':0, 'messages_sent':False,
              'student_data_written':False}
    for sid in ordered[len(selected):]:
        result['student_cards'][str(sid)] = _fallback_student(
            'Bu öğrenci kapsam sınırı nedeniyle henüz analiz edilmedi.',state='NOT_EVALUATED')
    if unverified_ids:
        result['warnings'].append(f'{unverified_ids} öğrenci kaydının kimliği doğrulanmadı.')
    source = Path(database_path)
    if not source.is_file():
        result['warnings'].append('Yerel veritabanı bulunamadı; akademik entegrasyon doğrulanamadı.')
        result['not_evaluated_count'] = len(subjects)
        for sid in selected:
            result['student_cards'][str(sid)] = _fallback_student('Veritabanı bulunamadı; iletişim doğrulanmadı.')
        return result
    # Connection created inside calling thread, SQLite snapshot is read-only.
    uri = 'file:' + quote(str(source.resolve()), safe='/:') + '?mode=ro'
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=3.0)) as con:
            con.execute('PRAGMA query_only=ON')
            con.execute('PRAGMA busy_timeout=3000')
            con.execute('BEGIN')
            try:
                for sid in selected:
                    try:
                        row = _verified_student(con, sid, day, identity_map[sid])
                    except (sqlite3.Error, ValueError, KeyError, TypeError):
                        row = _fallback_student('Bu öğrencinin akademik kaynakları doğrulanamadı.')
                    result['student_cards'][str(sid)] = row
                    result['evaluated_count'] += 1
                    if row['verified']:
                        result['verified_count'] += 1
                    if not row['contact_allowed']:
                        result['contact_blocked_count'] += 1
            finally:
                con.execute('ROLLBACK')
    except (sqlite3.Error, OSError) as e:
        result['warnings'].append('Yerel veritabanı bağlantısı kurulamadı; akademik veriler doğrulanamadı.')
        # Do not expose filesystem paths/SQLite errors in PDF.
        result['not_evaluated_count'] = len(subjects)
        for sid in selected:
            result['student_cards'][str(sid)] = _fallback_student('Kaynak okunamadı; iletişim doğrulanmadı.')
        return result
    if result['not_evaluated_count']:
        result['warnings'].append('Öğrenci sayısı nedeniyle akademik tarama kısmi; incelenmeyenler temiz kabul edilmedi.')
    if result['contact_blocked_count']:
        result['warnings'].append('Öğrenci kimliği, kayıt sahipliği veya iletişim numarası uyuşmayan öğrencilerin bağlantıları kapatıldı.')
    if (result['verified_count'] < len(identity_map) or unverified_ids or
        any(card.get('partial') for card in result['student_cards'].values())):
        result['source_state'] = 'PARTIAL'
    else:
        result['source_state'] = 'LOCAL_VERIFIED'
    return result
