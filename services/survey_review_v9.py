# -*- coding: utf-8 -*-
"""Shared explicit teacher review of remote survey submissions (no diagnosis)."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import db
from services.survey_invite_writer_v9 import _init


def pending_for_student(student_id:int, *, include_reviewed=False)->list[dict]:
    if type(student_id) is not int or student_id<=0:raise ValueError('Geçersiz öğrenci kimliği.')
    con=db.get_conn()
    try:
        _init(con)
        extra='' if include_reviewed else "AND s.decision='pending'"
        rows=con.execute('''SELECT s.id,i.student_id,i.survey_code,i.survey_snapshot,s.answers_json,
             s.received_at,s.decision FROM survey_v9_submissions s
             JOIN survey_v9_invites i ON i.id=s.invite_id
             WHERE i.student_id=? '''+extra+' ORDER BY s.id DESC LIMIT 100',(student_id,)).fetchall()
        return [{'submission_id':r[0], 'student_id':r[1], 'survey_code':r[2],
                 'survey_title':json.loads(r[3])['title'],
                 'questions':json.loads(r[3])['questions'], 'answers':json.loads(r[4]),
                 'received_at':r[5], 'decision':r[6]} for r in rows]
    finally:con.close()


def decide(submission_id:int, decision:str)->dict:
    if type(submission_id) is not int or submission_id<=0 or decision not in ('approved','rejected'):
        raise ValueError('Geçersiz işlem.')
    con=db.get_conn()
    try:
        _init(con)
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('''SELECT i.student_id,i.survey_code,s.answers_json,s.decision,
                        i.survey_snapshot,s.invite_id FROM survey_v9_submissions s
                        JOIN survey_v9_invites i ON i.id=s.invite_id WHERE s.id=?''',(submission_id,)).fetchone()
        if not row or row[3]!='pending':raise ValueError('Bekleyen anket bulunamadı veya daha önce işlendi.')
        sid,code,answers_text,_,snap_text,invite_id=row
        if not con.execute('SELECT id FROM ogrenci WHERE id=? AND aktif=1',(sid,)).fetchone():
            raise ValueError('Öğrenci artık aktif değil.')
        snap=json.loads(snap_text)
        answers=json.loads(answers_text)
        if set(answers) != {q['key'] for q in snap['questions']} or any(type(v) is not int or v not in (1,2,3,4,5) for v in answers.values()):
            raise ValueError('Yanıt bütünlüğü geçersiz.')
        rec=None
        if decision=='approved':
            rec=con.execute('INSERT INTO ogrenci_anket (ogrenci_id,anket_kodu,cevaplar) VALUES (?,?,?)',
                            (sid,code,answers_text)).lastrowid
        now=datetime.now(timezone.utc).isoformat(timespec='seconds')
        con.execute('UPDATE survey_v9_submissions SET decision=?,reviewed_at=?,imported_anket_id=? WHERE id=?',
                    (decision,now,rec,submission_id))
        con.execute('UPDATE survey_v9_invites SET state=? WHERE id=?',(decision,invite_id))
        con.commit()
        return {'status':decision,'student_id':sid,'survey_code':code,'record_id':rec}
    finally:con.close()
