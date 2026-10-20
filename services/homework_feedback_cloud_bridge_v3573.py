# -*- coding: utf-8 -*-
"""Windows -> minimal cloud survey relay (feature-flagged, never exposes SQLite).

Only invitation and four respondent answers leave the separate feedback relay.
The identity mapping stays in the teacher's existing LOCAL sqlite database.
Never writes homework status, quick diagnosis, grades or weekly schedule.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import os
import secrets
import sqlite3
import uuid

from services import homework_feedback_v3571 as legacy

FLAG='YKS_FEEDBACK_RELAY_V14_ENABLED'


def configured():
    return os.getenv(FLAG)=='1'


def _settings():
    if not configured(): raise ValueError('Çevrim içi röle pilotu etkin değil.')
    base=os.getenv('YKS_FEEDBACK_RELAY_URL','').strip().rstrip('/')
    parsed=urlsplit(base)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
        or parsed.path not in ('','/') or parsed.query or parsed.fragment):
        raise ValueError('Geçerli HTTPS röle adresi gerekir.')
    tenant=os.getenv('YKS_FEEDBACK_RELAY_TENANT','').strip()
    key=os.getenv('YKS_FEEDBACK_RELAY_KEY','')
    import re
    if not re.fullmatch('[a-zA-Z0-9_-]{3,48}',tenant) or len(key)<32:
        raise ValueError('Kurum anahtarı veya kimliği yapılandırılmamış.')
    return base,tenant,key


def _remote(method,path,payload=None):
    base,tenant,key=_settings()
    data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode('utf-8')
    req=Request(base+path, data=data,method=method, headers={
        'x-kocpilot-tenant':tenant,'x-kocpilot-key':key,
        'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urlopen(req,timeout=8) as response:
            if response.status not in (200,201):raise ValueError('Röle yanıtı geçersiz.')
            raw=response.read(100000)
            return json.loads(raw)
    except (URLError, HTTPError,TimeoutError,ValueError,json.JSONDecodeError) as exc:
        raise ValueError('Güvenli anket servisine erişilemedi veya sunucu yanıtı kabul edilmedi.') from exc


def _schema(con):
    legacy._init(con)
    con.execute('''CREATE TABLE IF NOT EXISTS homework_feedback_cloud_invites_v3573 (
         local_invite_id INTEGER NOT NULL UNIQUE,
         remote_ref TEXT NOT NULL UNIQUE,
         tenant TEXT NOT NULL,
         FOREIGN KEY(local_invite_id) REFERENCES homework_feedback_v3571_invites(id))''')
    con.execute('''CREATE TABLE IF NOT EXISTS homework_feedback_cloud_cursor_v3573 (
         tenant TEXT PRIMARY KEY, last_id INTEGER NOT NULL DEFAULT 0)''')
    con.execute('''CREATE TABLE IF NOT EXISTS homework_feedback_cloud_skips_v3573 (
         tenant TEXT NOT NULL, response_id INTEGER NOT NULL,
         reason TEXT NOT NULL, recorded_at TEXT NOT NULL,
         PRIMARY KEY(tenant,response_id))''')


def create_link(student_id, homework_id, respondent):
    """Uses only existing ownership verified in legacy._owned()."""
    legacy._enabled()
    legacy._int_id(student_id);legacy._int_id(homework_id)
    if respondent not in legacy.RESPONDENTS:
        raise ValueError('Öğrenci veya veli türünü seçin.')
    _,tenant,_=_settings()
    con=legacy.db.get_conn()
    try:
        lesson,topic=legacy._owned(con,student_id,homework_id)
    finally:con.close()
    token=secrets.token_urlsafe(32)
    remote_ref=str(uuid.uuid4())
    response=_remote('POST','/v14/invites',{
        'invite_ref':remote_ref,'token':token,'respondent':respondent,
        'lesson':lesson or 'Ders bilgisi yok','topic':topic or 'Konu bilgisi yok'})
    base,_,_=_settings()
    expected_url=base+'/r/'+token
    if (response.get('invite_ref')!=remote_ref or response.get('url')!=expected_url):
        raise ValueError('Sunucunun davet doğrulaması başarısız.')
    expires_at=response.get('expires_at')
    try:
        expires=datetime.fromisoformat(expires_at)
        if expires.tzinfo is None or expires<=datetime.now(timezone.utc):raise ValueError()
    except (TypeError,ValueError):raise ValueError('Davet süresi doğrulanamadı.') from None
    con=legacy.db.get_conn()
    try:
        con.execute('BEGIN IMMEDIATE')
        legacy._owned(con,student_id,homework_id)  # revalidate ownership after network
        _schema(con)
        cur=con.execute('''INSERT INTO homework_feedback_v3571_invites
           (token_hash,student_id,homework_id,respondent,lesson,topic,issued_at,expires_at)
           VALUES(?,?,?,?,?,?,?,?)''', (legacy._token_hash(token),student_id,homework_id,
                                       respondent,lesson,topic,legacy._iso(legacy._now()),expires_at))
        con.execute('''INSERT INTO homework_feedback_cloud_invites_v3573
            (local_invite_id,remote_ref,tenant) VALUES(?,?,?)''',(cur.lastrowid,remote_ref,tenant))
        con.commit()
    except Exception:
        con.rollback()
        # Prevent orphan usable invitation when local persistence failed.
        try:_remote('POST','/v14/invites/'+remote_ref+'/revoke',{})
        except ValueError:pass
        raise
    finally:con.close()
    return {'url':expected_url,'expires_at':expires_at,'student_id':student_id,
            'homework_id':homework_id,'respondent':respondent,'title':legacy.FORMS[respondent]['title']}


def sync_replies(*,max_batches=2):
    """Idempotent offline-safe pull; cursor/replies persist in SAME transaction.

    A deleted or transferred homework is SKIPPED, never reassigned.
    Does not alter legacy homework/teacher quick note tables.
    """
    legacy._enabled()
    _,tenant,_=_settings()
    con=legacy.db.get_conn()
    try:
        _schema(con);con.commit()
        row=con.execute('SELECT last_id FROM homework_feedback_cloud_cursor_v3573 WHERE tenant=?',(tenant,)).fetchone()
        cursor=row[0] if row else 0
        imported=skipped=0
        for _ in range(max(1,min(int(max_batches),10))):
            batch=_remote('GET','/v14/replies?'+urlencode({'cursor':cursor,'limit':50}))
            records=batch.get('items',[])
            if type(records) is not list or len(records)>50:
                raise ValueError('Anket servisi yanıtı geçersiz.')
            if not records:break
            for item in records:
                if type(item) is not dict:
                    raise ValueError('Anket kaydı geçersiz.')
                response_id=item.get('id');remote_ref=item.get('invite_ref')
                if type(response_id) is not int or response_id<=cursor or not isinstance(remote_ref,str):
                    raise ValueError('Röle sırası veya kimliği geçersiz.')
                # Cursor advances on rejected records, but rejection is auditable.
                # We validate all remote data before accepting the transaction.
                answers=legacy._validate_answers(item.get('answers'))
                received=item.get('received_at')
                try:
                    value=datetime.fromisoformat(received)
                    if not value.tzinfo:raise ValueError()
                except (ValueError,TypeError):raise ValueError('Zaman bilgisi geçersiz.') from None
                con.execute('BEGIN IMMEDIATE')
                try:
                    mapping=con.execute('''SELECT i.id,i.student_id,i.homework_id,i.state
                         FROM homework_feedback_cloud_invites_v3573 m
                         JOIN homework_feedback_v3571_invites i ON i.id=m.local_invite_id
                         WHERE m.tenant=? AND m.remote_ref=?''',(tenant,remote_ref)).fetchone()
                    reason=None
                    if mapping is None:reason='unmapped_invite'
                    elif mapping[3]!='issued':reason='not_issued'
                    else:
                        try:legacy._owned(con,mapping[1],mapping[2])
                        except ValueError:reason='homework_owner_mismatch'
                    if reason:
                        con.execute('''INSERT OR IGNORE INTO homework_feedback_cloud_skips_v3573
                          (tenant,response_id,reason,recorded_at) VALUES(?,?,?,?)''',
                          (tenant,response_id,reason,legacy._iso(legacy._now())))
                        skipped+=1
                    else:
                        con.execute('''INSERT INTO homework_feedback_v3571_replies
                          (invite_id,answers_json,received_at) VALUES(?,?,?)''',
                          (mapping[0],json.dumps(answers,ensure_ascii=False,sort_keys=True),received))
                        con.execute("UPDATE homework_feedback_v3571_invites SET state='submitted' WHERE id=?",(mapping[0],))
                        imported+=1
                    con.execute('''INSERT INTO homework_feedback_cloud_cursor_v3573(tenant,last_id)
                        VALUES(?,?) ON CONFLICT(tenant) DO UPDATE SET last_id=excluded.last_id''',
                        (tenant,response_id))
                    con.commit()
                    cursor=response_id
                except Exception:
                    con.rollback();raise
            if len(records)<50:break
        return {'imported':imported,'skipped':skipped,'cursor':cursor}
    finally:con.close()
