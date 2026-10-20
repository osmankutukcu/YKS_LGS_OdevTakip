# -*- coding: utf-8 -*-
"""V3.5.71 opt-in, homework-bound student/parent micro feedback.

Keeps self-reports strictly separate from teacher quick diagnoses, homework
checkboxes, legacy student surveys, academic results, and weekly schedules.
No automatic outbound messages, homework writes, diagnosis or mastery inference.
Public links work only on a deliberately configured HTTPS FastAPI server.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlsplit
import json
import os
import secrets
import sqlite3

import db

FEATURE_FLAG = 'YKS_HOMEWORK_FEEDBACK_V12_ENABLED'
RESPONDENTS = ('student', 'parent')
OBSTACLES = {
    'none': 'Belirgin güçlük gözlenmedi',
    'concept': 'Konuyu veya yönergeyi anlamakta zorlandı',
    'time': 'Zaman yetmedi',
    'attention': 'Dikkat veya işlem sırasında zorlandı',
    'workload': 'Çalışma yükü fazla geldi',
    'unknown': 'Bilmiyorum / emin değilim',
}
FORMS = {
    'student': {
        'title': 'Ödev Sonrası Kısa Öğrenci Öz Değerlendirmesi',
        'questions': [
            ('completion', 'Bu ödevde ne kadar ilerleyebildin?'),
            ('understanding', 'Çalıştığın konuyu ne kadar anladığını düşünüyorsun?'),
            ('time_fit', 'Ödev için ayrılan süre sana ne kadar yeterli geldi?'),
        ],
        'scale': '1 = Çok az / hiç, 5 = Tamamen / çok',
        'obstacle': 'En çok hangi noktada zorlandın?',
    },
    'parent': {
        'title': 'Ödev Çalışması Veli Gözlemi',
        'questions': [
            ('completion', 'Gözlemleyebildiğiniz kadarıyla ödev çalışması ne kadar ilerledi?'),
            ('understanding', 'Çocuğunuz çalışırken konuyu ne kadar rahat açıklayabildi?'),
            ('time_fit', 'Çalışma için ayrılan zamanın ne kadar yeterli olduğunu gözlemlediniz?'),
        ],
        'scale': '1 = Çok az / hiç, 5 = Tamamen / çok (gözlemlemediyseniz göndermeyin)',
        'obstacle': 'Gözlemlediğiniz başlıca güçlük hangisiydi?',
    },
}


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds')


def _enabled():
    if os.getenv(FEATURE_FLAG) != '1':
        raise ValueError('Ödev geri bildirim pilotu etkin değil.')


def _base():
    base = os.getenv('YKS_SURVEY_PUBLIC_BASE_URL', '').strip().rstrip('/')
    url = urlsplit(base)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
        or url.query or url.fragment or url.path not in ('', '/')):
        raise ValueError('Geçerli bir HTTPS anket sunucusu adresi gereklidir.')
    return base


def _int_id(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Geçerli öğrenci, ödev ve kayıt kimliği gerekir.')
    return value


def _token_hash(token):
    if (not isinstance(token, str) or len(token) != 43 or
        any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token)):
        raise ValueError('Bağlantı geçersiz.')
    return sha256(token.encode('ascii')).hexdigest()


def _init(con):
    # Only NEW, prefixed auxiliary tables. Never mutate old tables.
    con.execute('''CREATE TABLE IF NOT EXISTS homework_feedback_v3571_invites (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       token_hash TEXT NOT NULL UNIQUE,
       student_id INTEGER NOT NULL,
       homework_id INTEGER NOT NULL,
       respondent TEXT NOT NULL CHECK(respondent IN ('student','parent')),
       lesson TEXT NOT NULL,
       topic TEXT NOT NULL,
       issued_at TEXT NOT NULL,
       expires_at TEXT NOT NULL,
       state TEXT NOT NULL DEFAULT 'issued'
         CHECK(state IN ('issued','submitted','approved','rejected','revoked'))
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS homework_feedback_v3571_replies (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       invite_id INTEGER NOT NULL UNIQUE REFERENCES homework_feedback_v3571_invites(id),
       answers_json TEXT NOT NULL,
       received_at TEXT NOT NULL,
       review_state TEXT NOT NULL DEFAULT 'pending'
         CHECK(review_state IN ('pending','approved','rejected')),
       reviewed_at TEXT
    )''')
    con.execute('''CREATE INDEX IF NOT EXISTS idx_homework_feedback_student
        ON homework_feedback_v3571_invites(student_id,id)''')


def _owned(con, student_id, homework_id):
    row = con.execute('''SELECT o.ders, o.konu_ad FROM odev o
       JOIN odev_kume k ON k.id=o.kume_id
       JOIN ogrenci s ON s.id=o.ogrenci_id
       WHERE o.id=? AND o.ogrenci_id=? AND k.ogrenci_id=? AND s.aktif=1''',
       (homework_id,student_id,student_id)).fetchone()
    if not row:
        raise ValueError('Ödev seçili aktif öğrenciye ait değil.')
    return str(row[0] or '').strip()[:90], str(row[1] or '').strip()[:140]


def list_homeworks(student_id, *, limit=60):
    """Existing homework rows, read-only. No extra timetable or data-entry UI."""
    _int_id(student_id)
    con = db.get_conn()
    try:
        rows = con.execute('''SELECT o.id, o.ders, o.konu_ad FROM odev o
            JOIN odev_kume k ON k.id=o.kume_id
            JOIN ogrenci s ON s.id=o.ogrenci_id
            WHERE o.ogrenci_id=? AND k.ogrenci_id=? AND s.aktif=1
            ORDER BY o.id DESC LIMIT ?''', (student_id,student_id,max(1,min(int(limit),100)))).fetchall()
        return [{'homework_id':r[0], 'lesson':str(r[1] or '')[:90],
                 'topic':str(r[2] or '')[:140]} for r in rows]
    finally:
        con.close()


def create_link(student_id, homework_id, respondent):
    _enabled()
    base = _base()
    _int_id(student_id); _int_id(homework_id)
    if respondent not in RESPONDENTS:
        raise ValueError('Yanıtlayan öğrenci veya veli olmalı.')
    con = db.get_conn()
    try:
        lesson, topic = _owned(con, student_id, homework_id)
        _init(con)
        token = secrets.token_urlsafe(32)
        now = _now()
        expiry = _iso(now + timedelta(hours=48))
        with con:
            con.execute('''INSERT INTO homework_feedback_v3571_invites
               (token_hash,student_id,homework_id,respondent,lesson,topic,issued_at,expires_at)
               VALUES (?,?,?,?,?,?,?,?)''',
               (_token_hash(token),student_id,homework_id,respondent,lesson,topic,_iso(now),expiry))
        return {'url':base+'/h/'+token,'student_id':student_id,
                'homework_id':homework_id,'respondent':respondent,
                'expires_at':expiry,'title':FORMS[respondent]['title']}
    finally:
        con.close()


def _lookup(con, token, *, issued_only=True):
    row = con.execute('''SELECT id,student_id,homework_id,respondent,lesson,topic,expires_at,state
       FROM homework_feedback_v3571_invites WHERE token_hash=?''', (_token_hash(token),)).fetchone()
    if not row:
        raise ValueError('Bağlantı bulunamadı.')
    row = dict(zip(('invite_id','student_id','homework_id','respondent','lesson',
                    'topic','expires_at','state'),row))
    if issued_only and (row['state']!='issued' or datetime.fromisoformat(row['expires_at'])<=_now()):
        raise ValueError('Bağlantının süresi doldu veya daha önce kullanıldı.')
    return row


def read_invite(token):
    _enabled()
    con = db.get_conn()
    try:
        _init(con)
        row = _lookup(con, token)
        return {'title':FORMS[row['respondent']]['title'],
                'questions':FORMS[row['respondent']]['questions'],
                'scale':FORMS[row['respondent']]['scale'],
                'obstacle_question':FORMS[row['respondent']]['obstacle'],
                'obstacles':OBSTACLES,'respondent':row['respondent'],
                # Only course/topic; no student name, phone or id in public HTML.
                'lesson':row['lesson'],'topic':row['topic']}
    finally:
        con.close()


def _validate_answers(answers):
    keys = {'completion','understanding','time_fit','obstacle'}
    if type(answers) is not dict or set(answers) != keys:
        raise ValueError('Bütün soruların yanıtlanması gerekir.')
    normalized={}
    for key in ('completion','understanding','time_fit'):
        val=answers[key]
        if type(val) is not int or not 1 <= val <= 5:
            raise ValueError('Değerlendirme yanıtları 1–5 arasında olmalı.')
        normalized[key]=val
    if type(answers['obstacle']) is not str or answers['obstacle'] not in OBSTACLES:
        raise ValueError('Tanımlı olmayan güçlük yanıtı.')
    normalized['obstacle']=answers['obstacle']
    return normalized


def submit(token, answers):
    """One-time receipt. Student/parent report NEVER becomes teacher diagnosis."""
    _enabled()
    parsed = _validate_answers(answers)
    con = db.get_conn()
    try:
        _init(con)
        con.execute('BEGIN IMMEDIATE')
        row = _lookup(con, token)
        # Bind again on submission; a deleted/moved homework must be rejected.
        _owned(con, row['student_id'], row['homework_id'])
        now=_iso(_now())
        con.execute('''INSERT INTO homework_feedback_v3571_replies
           (invite_id,answers_json,received_at) VALUES (?,?,?)''',
           (row['invite_id'],json.dumps(parsed,ensure_ascii=False,sort_keys=True),now))
        con.execute("UPDATE homework_feedback_v3571_invites SET state='submitted' WHERE id=?",(row['invite_id'],))
        con.commit()
        return {'state':'pending_teacher_review'}
    finally:
        con.close()


def list_feedback(student_id, *, pending_only=True, limit=100):
    _int_id(student_id)
    con=db.get_conn()
    try:
        # Historical dbs: reading should not create a table without opt-in.
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='homework_feedback_v3571_invites'").fetchone():
            return []
        state_clause = "AND r.review_state='pending'" if pending_only else ''
        rows=con.execute('''SELECT r.id,i.student_id,i.homework_id,i.respondent,
            i.lesson,i.topic,r.answers_json,r.received_at,r.review_state
            FROM homework_feedback_v3571_replies r
            JOIN homework_feedback_v3571_invites i ON i.id=r.invite_id
            WHERE i.student_id=? '''+state_clause+''' ORDER BY r.id DESC LIMIT ?''',
            (student_id,max(1,min(int(limit),200)))).fetchall()
        return [{'reply_id':r[0],'student_id':r[1],'homework_id':r[2],
            'respondent':r[3],'lesson':r[4],'topic':r[5],
            'answers':json.loads(r[6]),'received_at':r[7],
            'review_state':r[8]} for r in rows]
    finally:con.close()


def decide(student_id, reply_id, decision):
    """Explicit teacher review, never promote a self-report to teacher quick note."""
    _int_id(student_id);_int_id(reply_id)
    if decision not in ('approved','rejected'):
        raise ValueError('Geçersiz öğretmen kararı.')
    con=db.get_conn()
    try:
        _init(con)
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('''SELECT i.id,i.homework_id FROM homework_feedback_v3571_replies r
            JOIN homework_feedback_v3571_invites i ON i.id=r.invite_id
            WHERE r.id=? AND i.student_id=? AND r.review_state='pending' ''',
            (reply_id,student_id)).fetchone()
        if not row:
            raise ValueError('Öğrenciye ait bekleyen yanıt bulunamadı.')
        _owned(con,student_id,row[1])
        con.execute('''UPDATE homework_feedback_v3571_replies
            SET review_state=?,reviewed_at=? WHERE id=?''',
            (decision,_iso(_now()),reply_id))
        con.execute('''UPDATE homework_feedback_v3571_invites
            SET state=? WHERE id=?''',(decision,row[0]))
        con.commit()
        return {'student_id':student_id,'reply_id':reply_id,'state':decision}
    finally:con.close()


def revoke(student_id, invite_id):
    _int_id(student_id);_int_id(invite_id)
    con=db.get_conn()
    try:
        _init(con)
        with con:
            changed=con.execute("""UPDATE homework_feedback_v3571_invites
                SET state='revoked' WHERE student_id=? AND id=? AND state='issued'""",
                (student_id,invite_id))
        if changed.rowcount!=1:
            raise ValueError('Bu öğrenciye ait etkin bağlantı bulunamadı.')
    finally:con.close()


def approved_summary(student_id, *, limit=8):
    """Read-only and explicitly labelled; never grade learning or infer cause."""
    rows = list_feedback(student_id,pending_only=False,limit=max(1,min(limit*4,100)))
    # Re-check current owner before showing a historical approved response.
    con=db.get_conn()
    try:
        verified=[]
        for r in rows:
            if r['review_state'] != 'approved':
                continue
            try: _owned(con,student_id,r['homework_id'])
            except ValueError: continue
            verified.append(r)
        approved=verified[:limit]
    finally: con.close()
    lines=[]
    for r in approved:
        a=r['answers']
        who='Öğrenci beyanı' if r['respondent']=='student' else 'Veli gözlemi'
        lines.append({'student_id':student_id,'homework_id':r['homework_id'],
            'lesson':r['lesson'],'topic':r['topic'],'source':who,
            'reported_obstacle':a['obstacle'],
            'obstacle_label':OBSTACLES.get(a['obstacle'],'Belirsiz'),
            'completion_self_rating':a['completion'],
            'understanding_self_rating':a['understanding'],
            'not_mastery_evidence':True,'not_teacher_diagnosis':True,
            'suggestion':'İlgili ödevi öğretmenle doğrulayın; gerekiyorsa kısa bağımsız kontrol yapın.'})
    return lines
