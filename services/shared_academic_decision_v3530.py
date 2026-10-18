# -*- coding: utf-8 -*-
"""V3.5.30: Same-student, read-only academic evidence and coaching-plan context.

One optional contract for Student 360, the teacher's automatic brief and the
Coach Assistant. Never mutates homework or creates/schedules work. The weekly
*coaching* plan is not a proof that the separate calendar has been generated.
"""
from __future__ import annotations

from datetime import date
import sqlite3

from services.proactive_academic_v3529 import (
    _student_has_ownership_conflict, read_academic_next_step,
)


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    # Constant, developer-defined identifiers only.
    return {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}


def _student_exists(con: sqlite3.Connection, student_id: int) -> bool:
    cols = _cols(con, 'ogrenci')
    if 'id' not in cols:
        return False
    active = ', aktif' if 'aktif' in cols else ''
    row = con.execute(f'SELECT id{active} FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    return row is not None and (not active or row[1] != 0)


def _plan_context(con: sqlite3.Connection, student_id: int, day: date) -> dict:
    """Coaching plan only; unknown schema is NOT equivalent to no plan."""
    cols = _cols(con, 'koc_plan')
    required = {'id', 'ogrenci_id', 'baslangic_tarihi', 'bitis_tarihi'}
    if not required <= cols:
        return {'state': 'UNVERIFIED', 'summary': 'Koçluk planı kaynağı doğrulanamadı.',
                'program_blocks': None, 'target_count': None}
    rows = con.execute('''SELECT id FROM koc_plan WHERE ogrenci_id=?
        AND baslangic_tarihi<=? AND bitis_tarihi>=? ORDER BY id LIMIT 3''',
        (student_id, day.isoformat(), day.isoformat())).fetchall()
    if not rows:
        return {'state': 'MISSING', 'summary': 'Seçili gün için kayıtlı koçluk planı bulunamadı.',
                'program_blocks': None, 'target_count': None}
    if len(rows) != 1:
        return {'state': 'CONFLICT', 'summary': 'Bu öğrenci ve tarih için çakışan koçluk planları var.',
                'program_blocks': None, 'target_count': None}
    pid = rows[0][0]
    program_cols = _cols(con, 'koc_program')
    target_cols = _cols(con, 'koc_hedef')
    blocks = (int(con.execute('SELECT COUNT(*) FROM koc_program WHERE plan_id=?', (pid,)).fetchone()[0])
              if 'plan_id' in program_cols else None)
    targets = (int(con.execute('SELECT COUNT(*) FROM koc_hedef WHERE plan_id=?', (pid,)).fetchone()[0])
               if 'plan_id' in target_cols else None)
    if blocks is None:
        state, summary = 'PARTIAL', 'Koçluk planı mevcut; program blokları doğrulanamadı.'
    elif not blocks:
        state, summary = 'NO_BLOCKS', 'Koçluk planı var; kayıtlı ders programı bloğu bulunmadı.'
    else:
        state, summary = 'READY', f'Koçluk planı mevcut; {blocks} ders programı bloğu kayıtlı.'
    return {'state': state, 'summary': summary, 'program_blocks': blocks,
            'target_count': targets}


def read_verified_plan_context(con: sqlite3.Connection, student_id: int, *,
                               today: date | None = None) -> dict:
    """Lightweight read-only plan context, without re-reading coaching evidence.

    Intended for already-running Coach Assistant flows that have gathered
    evidence once and must not repeat those potentially costly queries.
    """
    if type(student_id) is not int or student_id <= 0 or not _student_exists(con, student_id):
        raise ValueError('Verified student ID is required')
    if _student_has_ownership_conflict(con, student_id):
        return {'state': 'LINK_REVIEW', 'summary': 'Önce öğrenci–ödev bağlantıları doğrulanmalı.',
                'program_blocks': None, 'target_count': None}
    return _plan_context(con, student_id, today or date.today())


def read_shared_academic_card(con: sqlite3.Connection, student_id: int, *,
                              today: date | None = None) -> dict:
    """Read one verified student's existing facts, without synthesizing diagnosis.

    This function expects an existing sqlite connection. The caller controls
    the read-only transaction, time budget and worker execution. No PII is
    logged, cached, networked or returned beyond the teacher-facing advice.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('A verified student ID is required')
    day = today or date.today()
    if not isinstance(day, date):
        raise ValueError('Invalid reference date')
    if not _student_exists(con, student_id):
        raise ValueError('Student not found, inactive or identity unverified')
    if _student_has_ownership_conflict(con, student_id):
        return {
            'student_id': student_id, 'as_of': day.isoformat(),
            'state': 'LINK_REVIEW', 'academic': None,
            'plan': {'state': 'WITHHELD', 'summary': 'Önce öğrenci–ödev bağlantıları doğrulanmalı.',
                     'program_blocks': None, 'target_count': None},
            'next_step': 'Öğrenci–ödev bağlantılarını Denetim ekranında kontrol edin.',
            'basis': 'Öğrenci kimliği ve ödev/küme ilişki denetimi',
            'planning_hint': None, 'requires_teacher_approval': True,
            'auto_change_allowed': False, 'calendar_plan_verified': False,
            'sources': ('proactive_academic_v3529',),
        }
    try:
        plan = _plan_context(con, student_id, day)
    except (sqlite3.Error, ValueError, TypeError):
        plan = {'state': 'UNVERIFIED', 'summary': 'Koçluk planı geçici olarak okunamadı.',
                'program_blocks': None, 'target_count': None}
    # The V5 evidence reader expects named SQLite rows. Existing Student360
    # opens ordinary tuple-row connections; isolate and restore this adapter.
    old_factory = con.row_factory
    try:
        con.row_factory = sqlite3.Row
        academic = read_academic_next_step(con, student_id, today=day)
    except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError):
        academic = None  # Unverified sources do not imply academic progress.
        academic_unavailable = True
    else:
        academic_unavailable = False
    finally:
        con.row_factory = old_factory
    if academic and academic.get('student_id') != student_id:
        academic = None
        academic_unavailable = True

    if academic:
        step, basis, state = academic['next_step'], academic['basis'], 'RECOMMENDATION'
    elif plan['state'] == 'CONFLICT':
        step = 'Çakışan koçluk planlarını öğretmen olarak inceleyin.'
        basis = 'Koçluk planı: aynı tarih aralığında birden fazla kayıt'
        state = 'PLAN_REVIEW'
    elif academic_unavailable:
        step, basis, state = 'Akademik kanıt kaynağı doğrulanamadı; mevcut kayıtları kontrol edin.', 'Kaynak okuma durumu', 'UNVERIFIED'
    elif plan['state'] == 'MISSING':
        step, basis, state = 'Bu haftanın çalışma hedeflerini ve uygun saatlerini öğrenciyle değerlendirin.', 'Koçluk planı: seçili gün kayıt yok', 'PLAN_SUGGESTION'
    elif plan['state'] == 'NO_BLOCKS':
        step, basis, state = 'Koçluk planındaki çalışma zamanlarını gözden geçirin.', 'Koçluk planı: kayıtlı blok yok', 'PLAN_SUGGESTION'
    elif plan['state'] in ('UNVERIFIED', 'PARTIAL'):
        step, basis, state = 'Koçluk planı verisinin erişilebilirliğini doğrulayın.', 'Plan kaynağı doğrulanamadı', 'UNVERIFIED'
    else:
        step, basis, state = 'Ek müdahale kanıtı yok; normal akademik takibe devam edin.', 'Mevcut doğrulanabilen kayıt kapsamı', 'NO_PRIORITY'

    return {
        'student_id': student_id, 'as_of': day.isoformat(), 'state': state,
        'academic': academic, 'plan': plan, 'next_step': step[:260], 'basis': basis[:190],
        'planning_hint': (plan['summary'] if plan['state'] in ('MISSING', 'CONFLICT', 'NO_BLOCKS', 'PARTIAL') else None),
        'requires_teacher_approval': True, 'auto_change_allowed': False,
        'calendar_plan_verified': False,  # Coaching plan != calendar schedule.
        'sources': ('proactive_academic_v3529', 'koc_plan', 'koc_program', 'koc_hedef'),
    }
