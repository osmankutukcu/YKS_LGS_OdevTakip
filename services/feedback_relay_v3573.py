# -*- coding: utf-8 -*-
"""v3.5.73 opt-in, minimal-data, tenant-scoped HTTPS feedback relay.

Run as a SEPARATE FastAPI app: uvicorn services.feedback_relay_v3573:app.
The cloud database contains NO student identifiers, phone numbers, homework IDs,
local quick-diagnosis records or student names. Not a replacement for desktop DB.

IMPORTANT: pilot infrastructure, requires HTTPS reverse proxy, ingress rate limits,
separate backups/retention policy and real-device authorization testing.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from hmac import compare_digest
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import re
import secrets
import sqlite3
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title='KoçPilot Ödev Geri Bildirim Rölesi - Pilot', docs_url=None,
              redoc_url=None, openapi_url=None)
RESPONDENTS = ('student', 'parent')
OBSTACLES = {
    'none': 'Belirgin güçlük gözlenmedi',
    'concept': 'Konuyu veya yönergeyi anlamakta zorlandı',
    'time': 'Zaman yetmedi',
    'attention': 'Dikkat veya işlem sırasında zorlandı',
    'workload': 'Çalışma yükü fazla geldi',
    'unknown': 'Bilmiyorum / emin değilim',
}
QUESTIONS = {
    'student': ('Ödevde ne kadar ilerleyebildin?', 'Konuyu ne kadar anladığını düşünüyorsun?',
                'Ödev için ayrılan süre yeterli miydi?', 'En çok nerede zorlandın?'),
    'parent': ('Gözlemlediğiniz kadarıyla ödev ne kadar ilerledi?',
               'Çocuğunuz konuyu ne kadar rahat açıklayabildi?',
               'Çalışma için süre yeterli miydi?', 'Hangi güçlük gözlendi?'),
}
_HEADERS = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
            'X-Frame-Options': 'DENY', 'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"}


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat(timespec='seconds')


def _token_hash(token):
    if not isinstance(token, str) or not re.fullmatch('[a-zA-Z0-9_-]{43}', token):
        raise ValueError('Bağlantı geçersiz.')
    return sha256(token.encode('ascii')).hexdigest()


def _valid_public_base():
    base = os.getenv('YKS_FEEDBACK_RELAY_PUBLIC_URL', '').strip().rstrip('/')
    url = urlsplit(base)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('HTTPS üzerinden erişilen anket adresi yapılandırılmalıdır.')
    return base


def _conn():
    location = os.getenv('YKS_FEEDBACK_RELAY_DB', '').strip()
    if not location or location == ':memory:':
        raise RuntimeError('Ayrı röle veritabanı konumu gerekli.')
    db_path = Path(location).expanduser()
    if not db_path.is_absolute():
        raise RuntimeError('Röle veritabanı için mutlak dosya yolu kullanın.')
    con = sqlite3.connect(str(db_path), timeout=10)
    con.execute('PRAGMA busy_timeout=10000')
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''CREATE TABLE IF NOT EXISTS invites (
       id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, invite_ref TEXT NOT NULL,
       token_hash TEXT NOT NULL UNIQUE, respondent TEXT NOT NULL, lesson TEXT NOT NULL,
       topic TEXT NOT NULL, expires_at TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'issued',
       UNIQUE(tenant,invite_ref));
       CREATE TABLE IF NOT EXISTS replies (
       id INTEGER PRIMARY KEY, invite_id INTEGER NOT NULL UNIQUE REFERENCES invites(id),
       tenant TEXT NOT NULL, invite_ref TEXT NOT NULL, answers_json TEXT NOT NULL,
       received_at TEXT NOT NULL);
       CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON replies(tenant,id);
    ''')
    return con


def _authorize(request):
    tenant = request.headers.get('x-kocpilot-tenant', '')
    key = request.headers.get('x-kocpilot-key', '')
    if not re.fullmatch('[a-zA-Z0-9_-]{3,48}', tenant) or len(key)<32 or len(key)>256:
        raise HTTPException(401, 'Yetkisiz.')
    try: credentials=json.loads(os.getenv('YKS_FEEDBACK_RELAY_TENANT_HASHES', '{}'))
    except ValueError: credentials={}
    expected=credentials.get(tenant) if type(credentials) is dict else None
    digest=sha256(key.encode()).hexdigest()
    if not isinstance(expected,str) or len(expected)!=64 or not compare_digest(digest,expected):
        raise HTTPException(401, 'Yetkisiz.')
    return tenant


def _answers(data):
    if type(data) is not dict or set(data)!= {'completion','understanding','time_fit','obstacle'}:
        raise ValueError('Yanıtların tamamı gerekli.')
    for key in ('completion','understanding','time_fit'):
        if type(data[key]) is not int or not 1<=data[key]<=5:
            raise ValueError('Geçersiz değerlendirme.')
    if data['obstacle'] not in OBSTACLES or type(data['obstacle']) is not str:
        raise ValueError('Geçersiz güçlük değeri.')
    return data


async def _json(request):
    length=request.headers.get('content-length','')
    if not length.isdecimal() or int(length)>4096:
        raise HTTPException(413,'İstek çok büyük veya boyutu bilinmiyor.')
    try: return await request.json()
    except Exception: raise HTTPException(422,'Geçersiz JSON.') from None


@app.post('/v14/invites')
async def create_invite(request:Request):
    tenant=_authorize(request)
    data=await _json(request)
    if type(data) is not dict or set(data)!= {'invite_ref','token','respondent','lesson','topic'}:
        raise HTTPException(422,'Davet alanları geçersiz.')
    try:
        invite_ref=str(uuid.UUID(data['invite_ref']))
        if invite_ref!=data['invite_ref']: raise ValueError()
        token_hash=_token_hash(data['token'])
        respondent=data['respondent']
        if respondent not in RESPONDENTS: raise ValueError()
        lesson,topic=data['lesson'],data['topic']
        if not isinstance(lesson,str) or not isinstance(topic,str) or not 1<=len(lesson)<=90 or not 1<=len(topic)<=140:
            raise ValueError()
        base=_valid_public_base()
    except (TypeError,ValueError,KeyError): raise HTTPException(422,'Davet doğrulanamadı.') from None
    con=_conn()
    try:
        con.execute('BEGIN IMMEDIATE')
        old=con.execute('SELECT token_hash,respondent,lesson,topic,expires_at,state FROM invites WHERE tenant=? AND invite_ref=?',
                        (tenant,invite_ref)).fetchone()
        if old:
            if old[:4]!=(token_hash,respondent,lesson,topic) or old[5]!='issued':
                raise HTTPException(409,'Davet kimliği çakışıyor.')
            expiry=old[4]
        else:
            expiry=_iso(_now()+timedelta(hours=48))
            try:
                con.execute('INSERT INTO invites(tenant,invite_ref,token_hash,respondent,lesson,topic,expires_at) VALUES(?,?,?,?,?,?,?)',
                            (tenant,invite_ref,token_hash,respondent,lesson,topic,expiry))
            except sqlite3.IntegrityError:
                raise HTTPException(409,'Bağlantı kimliği tekrar kullanılamaz.') from None
        con.commit()
        return {'invite_ref':invite_ref,'url':base+'/r/'+data['token'],'expires_at':expiry}
    finally: con.close()


def _invite(con,token):
    row=con.execute('SELECT id,respondent,lesson,topic,expires_at,state FROM invites WHERE token_hash=?',
                    (_token_hash(token),)).fetchone()
    if not row or row[5]!='issued' or datetime.fromisoformat(row[4])<=_now():
        raise HTTPException(410,'Bağlantı geçersiz, süresi dolmuş veya kullanılmış.')
    return row


def _html(token,row):
    respondent,lesson,topic=row[1:4]
    questions=QUESTIONS[respondent]
    title='Öğrenci Öz Değerlendirmesi' if respondent=='student' else 'Veli Gözlem Formu'
    blocks=[]
    for index,key in enumerate(('completion','understanding','time_fit')):
        labels=''.join(f'<label><input type="radio" name="{key}" value="{v}" required>{v}</label>' for v in range(1,6))
        blocks.append(f'<fieldset><legend>{index+1}. {escape(questions[index])}</legend><div class="scale">{labels}</div></fieldset>')
    options=''.join(f'<label><input type="radio" name="obstacle" value="{escape(k)}" required>{escape(v)}</label>' for k,v in OBSTACLES.items())
    blocks.append(f'<fieldset><legend>4. {escape(questions[3])}</legend>{options}</fieldset>')
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{font:16px/1.6 system-ui;background:#f3f6fb;color:#17263a;margin:0}}main{{max-width:630px;margin:20px auto;padding:22px;border-radius:14px;background:white}}fieldset{{border:1px solid #d6e0ea;border-radius:9px;margin:14px 0;padding:14px}}legend{{font-weight:650}}label{{display:block;margin:7px 0}}.scale{{display:flex;gap:15px}}button{{background:#1456a0;color:white;border:0;border-radius:9px;padding:14px;font-weight:bold}}@media(max-width:650px){{main{{margin:0;border-radius:0}}}}</style></head><body><main><h2>{title}</h2><p><b>Ders/Konu:</b> {escape(lesson)} / {escape(topic)}</p><p>Gönüllü kısa geri bildirimdir, öğrenme testi veya öğretmen teşhisi değildir. Puanlar: 1 = az, 5 = çok.</p><form action="/r/{escape(token)}" method="post">{''.join(blocks)}<label><input type="checkbox" name="consent" value="yes" required>Yanıtımın öğretmene iletilmek üzere saklanacağını anladım.</label><button type="submit">Yanıtları gönder</button></form></main></body></html>'''


@app.get('/r/{token}',response_class=HTMLResponse)
def public_form(token:str):
    try:
        con=_conn()
        try: row=_invite(con,token)
        finally:con.close()
        return HTMLResponse(_html(token,row),headers=_HEADERS)
    except ValueError: raise HTTPException(404,'Bağlantı bulunamadı.') from None


@app.post('/r/{token}',response_class=HTMLResponse)
async def public_submit(token:str,request:Request):
    length=request.headers.get('content-length','')
    if not length.isdecimal() or int(length)>8192:
        raise HTTPException(413,'Form verisi çok büyük.')
    form=await request.form()
    if len(form)!=5 or set(form.keys())!={'completion','understanding','time_fit','obstacle','consent'} or form.get('consent')!='yes':
        raise HTTPException(422,'Bütün yanıtlar gerekli.')
    try: answers=_answers({k:int(form[k]) if form[k] in ('1','2','3','4','5') else None for k in ('completion','understanding','time_fit')} | {'obstacle':str(form['obstacle'])})
    except (TypeError,ValueError): raise HTTPException(422,'Yanıtlar geçersiz.') from None
    con=_conn()
    try:
        con.execute('BEGIN IMMEDIATE')
        row=_invite(con,token)
        tenant,ref=con.execute('SELECT tenant,invite_ref FROM invites WHERE id=?',(row[0],)).fetchone()
        now=_iso(_now())
        con.execute('INSERT INTO replies(invite_id,tenant,invite_ref,answers_json,received_at) VALUES(?,?,?,?,?)',
                    (row[0],tenant,ref,json.dumps(answers,sort_keys=True,ensure_ascii=False),now))
        con.execute("UPDATE invites SET state='submitted' WHERE id=?",(row[0],))
        con.commit()
    except ValueError: raise HTTPException(404,'Bağlantı bulunamadı.') from None
    finally:con.close()
    return HTMLResponse('<!doctype html><html lang="tr"><meta charset="utf-8"><body style="font-family:system-ui;padding:25px"><h2>Yanıtınız alındı.</h2><p>Öğretmenin incelemesine iletilecek. Teşekkürler.</p></body></html>',headers=_HEADERS)


@app.get('/v14/replies')
def replies(request:Request,cursor:int=0,limit:int=50):
    tenant=_authorize(request)
    if cursor<0 or not 1<=limit<=100: raise HTTPException(422,'Sorgu geçersiz.')
    con=_conn()
    try:
        rows=con.execute('SELECT id,invite_ref,answers_json,received_at FROM replies WHERE tenant=? AND id>? ORDER BY id LIMIT ?',
                         (tenant,cursor,limit)).fetchall()
        return {'items':[{'id':r[0],'invite_ref':r[1],'answers':json.loads(r[2]),'received_at':r[3]} for r in rows]}
    finally:con.close()


@app.post('/v14/invites/{invite_ref}/revoke')
def revoke(invite_ref:str, request:Request):
    tenant=_authorize(request)
    try:ref=str(uuid.UUID(invite_ref))
    except ValueError:raise HTTPException(422,'Davet numarası geçersiz.') from None
    con=_conn()
    try:
        with con:
            n=con.execute("UPDATE invites SET state='revoked' WHERE tenant=? AND invite_ref=? AND state='issued'",
                          (tenant,ref)).rowcount
        if n!=1:raise HTTPException(409,'Etkin davet yok.')
        return {'state':'revoked'}
    finally:con.close()
