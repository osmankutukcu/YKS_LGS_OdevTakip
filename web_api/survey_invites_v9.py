# -*- coding: utf-8 -*-
"""V9 opt-in mobile questionnaire links for existing V8 surveys.

No changes to checkbox, homework, survey scoring, or current interview system.
Survey response is held for explicit teacher review before it reaches ogrenci_anket.
The admin API uses the EXISTING x-access-key middleware in web_api.main.
Public GET/POST are the only unauthenticated exceptions to that middleware.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import os
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

import db

router = APIRouter()
CATALOG_PATH = Path(__file__).resolve().parent.parent / 'services' / 'survey_catalog_v9.json'


def _enabled() -> None:
    if os.getenv('YKS_SURVEY_V9_ENABLED') != '1':
        raise HTTPException(503, 'Çevrim içi anketler etkinleştirilmedi.')


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds')


def _base_url():
    base = os.getenv('YKS_SURVEY_PUBLIC_BASE_URL', '').strip().rstrip('/')
    p = urlsplit(base)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise HTTPException(503, 'Anket için HTTPS adresi yapılandırılmalı.')
    return base


def _token_key(token):
    if not isinstance(token, str) or len(token) != 43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token):
        raise HTTPException(404, 'Bu bağlantı kullanılamıyor.')
    return sha256(token.encode('ascii')).hexdigest()


def _conn():
    con = db.get_conn()
    con.execute('PRAGMA busy_timeout=5000')
    return con


from services.survey_invite_writer_v9 import _init


def _fetch_invite(con, token, *, for_use=True):
    row = con.execute('SELECT id, student_id, survey_code, survey_snapshot, expires_at, state FROM survey_v9_invites WHERE token_sha256=?', (_token_key(token),)).fetchone()
    if not row:
        raise HTTPException(404, 'Bu bağlantı kullanılamıyor.')
    ident, student, code, snap, expires, state = row
    if for_use and (state != 'issued' or datetime.fromisoformat(expires) <= _now()):
        raise HTTPException(410, 'Bu bağlantı artık geçerli değil.')
    return ident, student, code, json.loads(snap)


def _headers():
    return {
        'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
        'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'none'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; style-src 'unsafe-inline'",
    }


def _page(survey, token):
    parts = []
    for i, q in enumerate(survey['questions'], 1):
        question = escape(q['text'])
        key = escape(q['key'], quote=True)
        controls = ''.join(
            f'<label><input type="radio" name="{key}" value="{v}" required> {v}</label>' for v in range(1, 6)
        )
        parts.append(f'<fieldset><legend>{i}. {question}</legend><div class="choices">{controls}</div></fieldset>')
    body = '\n'.join(parts)
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="referrer" content="no-referrer"><title>Öğrenci Öz-Değerlendirme</title>
    <style>body{{margin:0;background:#f6f8fb;color:#172033;font-family:system-ui,sans-serif;line-height:1.55}}
    main{{max-width:740px;margin:20px auto;padding:24px;background:white;border-radius:16px}}
    fieldset{{border:1px solid #d6dce5;border-radius:12px;margin:15px 0;padding:15px}}
    legend{{font-weight:600;padding:0 5px}}.choices{{display:flex;flex-wrap:wrap;gap:12px}}
    .choices label{{cursor:pointer;padding:8px 12px;border:1px solid #d6dce5;border-radius:8px}}
    button{{padding:14px 26px;background:#1b4c95;color:white;border:0;border-radius:10px;font-size:16px;cursor:pointer}}
    @media(max-width:600px){{main{{margin:0;border-radius:0;padding:16px}}}}</style></head>
    <body><main><h1>{escape(survey['title'])}</h1>
    <p>Bu bir öz-değerlendirme formudur; sınav başarısı veya psikolojik durum hakkında tanı koymaz.
    Yanıtlarınız öğretmen tarafından incelendikten sonra öğrenci dosyanıza aktarılabilir.</p>
    <p><strong>1:</strong> Hiç katılmıyorum · <strong>5:</strong> Tamamen katılıyorum.</p>
    <form action="/s/{token}" method="post">{body}
    <button type="submit">Yanıtları gönder</button></form></main></body></html>'''


@router.post('/api/v9/surveys/invites')
async def create_invite(request: Request):
    """Existing admin access-key middleware protects this endpoint."""
    _enabled()
    try:
        data = await request.json()
        sid, code = data['student_id'], data['survey_code']
    except (ValueError, TypeError, KeyError):
        raise HTTPException(422, 'Öğrenci ve anket seçimi gerekli.')
    from services.survey_invite_writer_v9 import create_link
    try:
        return create_link(sid, code)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None



@router.get('/s/{token}', response_class=HTMLResponse)
def public_form(token: str):
    _enabled()
    con = _conn()
    try:
        _init(con)
        _, _, _, survey = _fetch_invite(con, token)
        return HTMLResponse(_page(survey, token), headers=_headers())
    finally:
        con.close()


@router.post('/s/{token}', response_class=HTMLResponse)
async def submit_form(token: str, request: Request):
    _enabled()
    raw_len = request.headers.get('content-length', '0')
    if not raw_len.isdigit() or int(raw_len) > 16000:
        raise HTTPException(413, 'Form gönderimi çok büyük.')
    con = _conn()
    try:
        _init(con)
        con.execute('BEGIN IMMEDIATE')
        ident, _, _, snap = _fetch_invite(con, token)
        form = await request.form()
        questions = snap['questions']
        keys = {q['key'] for q in questions}
        if len(form) != len(keys) or set(form.keys()) != keys:
            raise HTTPException(422, 'Bütün soruları yanıtlayınız.')
        answers = {}
        for key in keys:
            v = form.get(key)
            if not isinstance(v, str) or v not in ('1','2','3','4','5'):
                raise HTTPException(422, 'Yanıtlar 1 ile 5 arasında olmalı.')
            answers[key] = int(v)
        con.execute('INSERT INTO survey_v9_submissions (invite_id,answers_json,received_at) VALUES (?,?,?)',
                    (ident,json.dumps(answers,sort_keys=True),_iso(_now())))
        con.execute('UPDATE survey_v9_invites SET state=?, submitted_at=? WHERE id=?',
                    ('submitted',_iso(_now()),ident))
        con.commit()
        return HTMLResponse('<!doctype html><html lang="tr"><meta charset="utf-8">'
                            '<meta name="viewport" content="width=device-width,initial-scale=1">'
                            '<body style="font-family:system-ui;padding:32px"><h1>Yanıtlarınız alındı.</h1>'
                            '<p>Öğretmeninizin incelemesine iletildi. Teşekkür ederiz.</p></body></html>',
                            headers=_headers())
    finally:
        con.close()


@router.get('/api/v9/surveys/submissions')
def list_submissions(student_id: int):
    _enabled()
    if student_id <= 0:
        raise HTTPException(422, 'Geçersiz öğrenci.')
    from services.survey_review_v9 import pending_for_student
    try:
        rows = pending_for_student(student_id,include_reviewed=True)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return [{k:v for k,v in r.items() if k!='questions'} for r in rows]



@router.post('/api/v9/surveys/submissions/{submission_id}/approve')
def approve_submission(submission_id: int):
    _enabled()
    from services.survey_review_v9 import decide
    try: return decide(submission_id,'approved')
    except ValueError as exc: raise HTTPException(409,str(exc)) from None



@router.post('/api/v9/surveys/submissions/{submission_id}/reject')
def reject_submission(submission_id: int):
    _enabled()
    from services.survey_review_v9 import decide
    try: return decide(submission_id,'rejected')
    except ValueError as exc: raise HTTPException(409,str(exc)) from None



@router.post('/api/v9/surveys/invites/{invite_id}/revoke')
def revoke_invite(invite_id:int):
    _enabled()
    con=_conn()
    try:
        _init(con)
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT state FROM survey_v9_invites WHERE id=?',(invite_id,)).fetchone()
        if not row or row[0] != 'issued':
            raise HTTPException(409,'Aktif bağlantı bulunamadı.')
        con.execute('UPDATE survey_v9_invites SET state=? WHERE id=?',('revoked',invite_id))
        con.commit()
        return {'status':'revoked'}
    finally:
        con.close()
