# -*- coding: utf-8 -*-
"""V3.5.72: read-only, teacher-reviewed micro feedback for existing coaching.

A student/parent's subjective report is *not* teacher diagnosis, independent
learning evidence, homework completion, or a causal finding. This module reads
only the V3571 tables, never changes homework, weekly plan or quick-note data.
"""
from __future__ import annotations

import json
import sqlite3

from services.homework_feedback_v3571 import OBSTACLES

SCHEMA = 'homework_feedback_coaching_v3572'
_TABLES = {'homework_feedback_v3571_invites', 'homework_feedback_v3571_replies'}
_ROLES = {'student': 'Öğrenci öz değerlendirmesi', 'parent': 'Veli gözlemi'}


def _valid_id(student_id):
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli öğrenci kimliği gerekir.')


def _schema_ready(con):
    existing = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?,?)",
        tuple(sorted(_TABLES))).fetchall()}
    return existing == _TABLES


def read_coaching_feedback(con: sqlite3.Connection, student_id: int, *, limit: int = 3):
    """Use the caller's coherent, query-only snapshot (never create tables)."""
    _valid_id(student_id)
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError('Görünür kayıt sınırı 1 ile 5 arasında olmalı.')
    base = {'schema': SCHEMA, 'student_id': student_id, 'read_only': True,
            'teacher_review_required': True, 'is_learning_evidence': False,
            'is_teacher_diagnosis': False, 'changes_homework': False,
            'changes_weekly_plan': False, 'items': []}
    try:
        active = con.execute('SELECT 1 FROM ogrenci WHERE id=? AND aktif=1',
                             (student_id,)).fetchone()
        if active is None:
            return {**base, 'state': 'STUDENT_UNVERIFIED'}
        if not _schema_ready(con):
            return {**base, 'state': 'NO_PILOT_DATA'}
        rows = con.execute('''
            SELECT r.id, i.homework_id, i.respondent, i.lesson, i.topic,
                   o.ders, o.konu_ad, r.answers_json, r.received_at
              FROM homework_feedback_v3571_replies r
              JOIN homework_feedback_v3571_invites i ON i.id=r.invite_id
              JOIN odev o ON o.id=i.homework_id AND o.ogrenci_id=i.student_id
              JOIN odev_kume k ON k.id=o.kume_id AND k.ogrenci_id=i.student_id
             WHERE i.student_id=? AND r.review_state='approved'
                   AND i.state='approved'
             ORDER BY r.id DESC LIMIT ?''', (student_id, min(limit * 5, 25))).fetchall()
        items=[]
        for reply_id, homework_id, role, lesson, topic, current_lesson, current_topic, raw, received in rows:
            if role not in _ROLES:
                continue
            # A modified homework must not inherit someone else's historical report.
            if (str(lesson or '').strip() != str(current_lesson or '').strip()
                    or str(topic or '').strip() != str(current_topic or '').strip()):
                continue
            try:
                answer=json.loads(raw)
            except (ValueError, TypeError):
                continue
            if type(answer) is not dict or set(answer) != {'completion','understanding','time_fit','obstacle'}:
                continue
            if any(type(answer[k]) is not int or not 1 <= answer[k] <= 5
                   for k in ('completion','understanding','time_fit')):
                continue
            if answer['obstacle'] not in OBSTACLES:
                continue
            items.append({'reply_id':reply_id, 'homework_id':homework_id,
                          'source':_ROLES[role], 'respondent':role,
                          'lesson':str(lesson)[:90], 'topic':str(topic)[:140],
                          'obstacle':answer['obstacle'],
                          'obstacle_label':OBSTACLES[answer['obstacle']],
                          'reported_understanding':answer['understanding'],
                          'reported_time_fit':answer['time_fit'],
                          'received_at':str(received or '')[:32],
                          'teacher_approved':True, 'independent_measurement':False})
            if len(items) == limit:
                break
        return {**base,'state':'APPROVED_OBSERVATIONS' if items else 'NO_APPROVED_FEEDBACK',
                'items':items}
    except (sqlite3.DatabaseError, KeyError, TypeError, ValueError):
        # Fail closed; never interpret unreadable data as 'no difficulty'.
        return {**base, 'state': 'SOURCE_UNVERIFIED'}


def format_student360_feedback(card, student_id):
    """Plain text for the already-existing Student360 output; no new UI."""
    if (type(student_id) is not int or student_id <= 0
            or type(card) is not dict or card.get('schema') != SCHEMA
            or card.get('student_id') != student_id
            or card.get('read_only') is not True
            or card.get('is_learning_evidence') is not False
            or card.get('is_teacher_diagnosis') is not False
            or card.get('changes_homework') is not False):
        return ''
    if card.get('state') != 'APPROVED_OBSERVATIONS':
        return ''
    items=card.get('items')
    if not isinstance(items,list) or len(items) > 5:
        return ''
    text=['ÖĞRENCİ–VELİ ÖDEV GERİ BİLDİRİMİ · ÖĞRETMEN ONAYLI']
    for item in items:
        if (type(item) is not dict or item.get('teacher_approved') is not True
                or item.get('independent_measurement') is not False
                or item.get('respondent') not in _ROLES):
            return ''
        text.append('• '+_ROLES[item['respondent']]+' · '+str(item.get('lesson') or '')[:90]
                    +' / '+str(item.get('topic') or '')[:140]
                    +' · bildirilen güçlük: '+str(item.get('obstacle_label') or '')[:110])
    text.append('Bu gönüllü beyanlar öğretmen teşhisi veya öğrenme başarısı değildir.')
    text.append('Öneri: Gerekirse öğrenciyle görüşün ve bağımsız kısa öğrenme kontrolü yapın.')
    return '\n'.join(text)


def assistant_feedback_hint(card, student_id):
    """One optional, reviewed, student-scoped inbox hint; never auto-act."""
    if (type(student_id) is not int or student_id <= 0
            or not isinstance(card,dict) or card.get('schema') != SCHEMA
            or card.get('student_id') != student_id
            or card.get('read_only') is not True
            or card.get('is_learning_evidence') is not False
            or card.get('changes_homework') is not False
            or card.get('state') != 'APPROVED_OBSERVATIONS'):
        return None
    items=card.get('items')
    if not isinstance(items,list) or not items:
        return None
    item=items[0]
    if (not isinstance(item,dict) or item.get('teacher_approved') is not True
            or item.get('independent_measurement') is not False
            or item.get('respondent') not in _ROLES
            or type(item.get('reply_id')) is not int):
        return None
    return {'student_id':student_id,'reply_id':item['reply_id'],
            'source':_ROLES[item['respondent']],
            'lesson':str(item.get('lesson') or '')[:90],
            'topic':str(item.get('topic') or '')[:140],
            'obstacle_label':str(item.get('obstacle_label') or '')[:110],
            'next_step':'Öğrenci beyanını öğretmen gözlemiyle karşılaştırın; gerekirse bağımsız kısa yoklama yapın.',
            'teacher_approval_required':True,'auto_assignment':False}
