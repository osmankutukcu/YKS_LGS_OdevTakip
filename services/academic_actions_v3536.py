# -*- coding: utf-8 -*-
"""V3.5.36 read-only, same-student academic action explanation.

One canonical homework interpretation for Student 360, Coach Assistant and
teacher brief. Coaching PLAN information is not a verified weekly calendar.
No diagnosis, automatic assignment, messaging or DB writes. Incomplete
student ownership blocks academic advice rather than generating a guess.
"""
from __future__ import annotations

from datetime import date
import sqlite3

from services.canonical_homework_evidence_v3535 import scan_canonical_homework
from services.shared_academic_decision_v3530 import read_verified_plan_context


def read_student_action_card(con: sqlite3.Connection, student_id: int, *,
                             today: date | None = None) -> dict:
    """Use the caller's existing read snapshot; do not start a transaction.

    Raises for an invalid/inactive student or unavailable source. The caller
    must translate these into UNVERIFIED, not a clean academic assessment.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('A verified student ID is required')
    day = today or date.today()
    if not isinstance(day, date):
        raise ValueError('Invalid reference date')
    canonical = scan_canonical_homework(con, today=day, focus_student_id=student_id)
    focus = canonical['focus_student']
    if focus['student_id'] != student_id:
        raise ValueError('Student ownership evidence does not match request')
    common = {'student_id': student_id, 'as_of': day.isoformat(),
              'homework': focus, 'global_coverage': canonical['state'],
              'requires_teacher_approval': True, 'auto_change_allowed': False,
              'calendar_plan_verified': False, 'remote_verified': False,
              'basis': 'Doğrulanmış yerel odev/odev_satir ve koçluk planı kayıtları',
              'not_mastery_diagnosis': True}
    if focus['state'] == 'LINK_REVIEW':
        return {**common, 'state': 'LINK_REVIEW', 'plan': None,
                'next_step': 'Önce öğrenci–ödev/küme bağlantılarını Denetim ekranında inceleyin.',
                'note': 'Bu öğrenci için akademik sayılar güvenilir kabul edilmedi.'}
    try:
        plan = read_verified_plan_context(con, student_id, today=day)
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        plan = {'state': 'UNVERIFIED', 'summary': 'Koçluk planı okunamadı.',
                'program_blocks': None, 'target_count': None}
    if plan['state'] == 'LINK_REVIEW':
        return {**common, 'state': 'LINK_REVIEW', 'plan': None,
                'next_step': 'Önce öğrenci–ödev bağlantılarını Denetim ekranında inceleyin.',
                'note': 'Akademik öneri durduruldu.'}
    overdue = focus['overdue_open_tasks']
    if overdue:
        lesson = focus['top_overdue_lesson'] or 'ders belirtilmemiş'
        state = 'HOMEWORK_FOLLOWUP'
        step = (f'{lesson} kapsamında teslim tarihi geçmiş {overdue} açık ödevi '
                'öğrenciyle doğrulayın; gerekiyorsa telafi çalışmasını değerlendirin.')
    elif plan['state'] == 'CONFLICT':
        state = 'PLAN_REVIEW'
        step = 'Aynı döneme ait çakışan koçluk planlarını inceleyin.'
    elif plan['state'] == 'MISSING':
        state = 'PLAN_REVIEW'
        step = 'Öğrencinin haftalık çalışma hedeflerini ve uygun saatlerini gözden geçirin.'
    elif plan['state'] == 'NO_BLOCKS':
        state = 'PLAN_REVIEW'
        step = 'Koçluk planında çalışma blokları bulunmuyor; zaman planını değerlendirin.'
    elif plan['state'] in ('UNVERIFIED', 'PARTIAL'):
        state = 'UNVERIFIED'
        step = 'Haftalık koçluk planı kaynağını doğrulayın.'
    elif focus['state'] == 'PARTIAL_COVERAGE':
        state = 'PARTIAL_COVERAGE'
        step = 'Bazı ödevlerin tarihi veya bağlantısı doğrulanamadı; kapsamı inceleyin.'
    else:
        state = 'NO_VERIFIED_PRIORITY'
        step = 'Doğrulanabilen mevcut kayıtlar acil bir ödev müdahalesi göstermiyor; normal takibe devam edin.'
    return {**common, 'state': state, 'plan': plan,
            'next_step': step[:260],
            'note': ('Ödev tamamlama öğrenme kanıtı değildir. Koçluk planı ayrı bir haftalık '
                     'takvimin üretildiğini göstermez. Bulut kayıtları doğrulanmadı.'),
            'plan_attention': plan['summary'] if plan['state'] in ('MISSING', 'CONFLICT', 'NO_BLOCKS', 'PARTIAL', 'UNVERIFIED') else None}
