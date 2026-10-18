# -*- coding: utf-8 -*-
"""Pure-Python V9 invite creation shared by desktop and FastAPI.

This module never imports PyQt or FastAPI. No homework/checkbox mutations.
Enabled only with explicit HTTPS public base URL and feature flag.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
import json, os, secrets

import db

CATALOG_PATH = Path(__file__).with_name('survey_catalog_v9.json')


def create_link(student_id:int, survey_code:str) -> dict:
    if os.getenv('YKS_SURVEY_V9_ENABLED') != '1':
        raise ValueError('Çevrim içi anket modülü henüz etkin değil.')
    base = os.getenv('YKS_SURVEY_PUBLIC_BASE_URL','').strip().rstrip('/')
    p = urlsplit(base)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
        raise ValueError('Önce geçerli HTTPS anket sunucusu adresi yapılandırılmalı.')
    catalog=json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    if type(student_id) is not int or student_id <= 0 or survey_code not in catalog:
        raise ValueError('Öğrenci veya çevrim içi gönderime uygun anket seçilmedi.')
    con=db.get_conn()
    try:
        _init(con)
        if not con.execute('SELECT id FROM ogrenci WHERE id=? AND aktif=1',(student_id,)).fetchone():
            raise ValueError('Aktif öğrenci bulunamadı.')
        token=secrets.token_urlsafe(32)
        now=datetime.now(timezone.utc)
        until=(now+timedelta(days=3)).isoformat(timespec='seconds')
        con.execute('''INSERT INTO survey_v9_invites
           (token_sha256,student_id,survey_code,survey_snapshot,issued_at,expires_at)
           VALUES (?,?,?,?,?,?)''',
           (sha256(token.encode('ascii')).hexdigest(), student_id,survey_code,
            json.dumps(catalog[survey_code],ensure_ascii=False),now.isoformat(timespec='seconds'),until))
        con.commit()
        return {'url':base+'/s/'+token,'expires_at':until,
                'student_id':student_id,'survey_title':catalog[survey_code]['title']}
    finally:
        con.close()


def _init(con):
    con.execute('''CREATE TABLE IF NOT EXISTS survey_v9_invites (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      token_sha256 TEXT NOT NULL UNIQUE,
      student_id INTEGER NOT NULL,
      survey_code TEXT NOT NULL,
      survey_snapshot TEXT NOT NULL,
      issued_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'issued'
           CHECK(state IN ('issued','submitted','approved','rejected','revoked')),
      submitted_at TEXT
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS survey_v9_submissions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      invite_id INTEGER NOT NULL UNIQUE REFERENCES survey_v9_invites(id),
      answers_json TEXT NOT NULL,
      received_at TEXT NOT NULL,
      decision TEXT NOT NULL DEFAULT 'pending' CHECK(decision IN ('pending','approved','rejected')),
      reviewed_at TEXT,
      imported_anket_id INTEGER UNIQUE
    )''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_survey_v9_student ON survey_v9_invites(student_id, id)')



def active_links(student_id:int)->list[dict]:
    """List only non-expired, unsubmitted links for the selected student."""
    if type(student_id) is not int or student_id<=0:raise ValueError('Geçersiz öğrenci.')
    con=db.get_conn()
    try:
        _init(con)
        now=datetime.now(timezone.utc).isoformat(timespec='seconds')
        rows=con.execute('''SELECT id,survey_code,issued_at,expires_at FROM survey_v9_invites
            WHERE student_id=? AND state='issued' AND expires_at>? ORDER BY id DESC LIMIT 100''',
            (student_id,now)).fetchall()
        return [{'id':r[0],'survey_code':r[1],'issued_at':r[2],'expires_at':r[3]} for r in rows]
    finally:con.close()


def revoke_link(student_id:int, invite_id:int)->bool:
    """Student-bound revocation; no ability to revoke a different student's link."""
    if type(student_id) is not int or student_id<=0 or type(invite_id) is not int or invite_id<=0:
        raise ValueError('Geçersiz seçim.')
    con=db.get_conn()
    try:
        _init(con)
        con.execute('BEGIN IMMEDIATE')
        result=con.execute('''UPDATE survey_v9_invites SET state='revoked' WHERE id=? AND student_id=? AND state='issued' ''',
            (invite_id,student_id))
        if result.rowcount!=1:raise ValueError('Aktif bağlantı bulunamadı veya farklı öğrenciye ait.')
        con.commit()
        return True
    finally:con.close()
