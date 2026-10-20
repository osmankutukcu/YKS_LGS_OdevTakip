# -*- coding: utf-8 -*-
"""Opt-in V3.5.71 mobile micro feedback over the existing secured FastAPI service.

GET/POST /h/{opaque-token} are publicly reachable ONLY through possession of
an expiring one-use random link; all /api endpoints require the existing web
access-key middleware. No automatic WhatsApp, SMTP or legacy DB mutations.
"""
from __future__ import annotations

from html import escape
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from services import homework_feedback_v3571 as feedback

router=APIRouter()
_HEADERS={
    'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer',
    'X-Content-Type-Options':'nosniff', 'X-Frame-Options':'DENY',
    'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}


def _response_error(exc):
    msg=str(exc)
    status=503 if 'etkin değil' in msg else (410 if 'süresi doldu' in msg else 404)
    raise HTTPException(status,msg) from None


def _form_html(token, data):
    qs=[]
    for idx,(key,title) in enumerate(data['questions'],1):
        radios=''.join(f'<label><input type="radio" name="{escape(key)}" value="{i}" required> {i}</label>' for i in range(1,6))
        qs.append(f'<fieldset><legend>{idx}. {escape(title)}</legend><div class="choices">{radios}</div></fieldset>')
    opts=''.join('<label><input type="radio" name="obstacle" value="'+escape(key)+'" required> '
                 +escape(val)+'</label>' for key,val in data['obstacles'].items())
    qs.append(f'<fieldset><legend>4. {escape(data["obstacle_question"])}</legend><div class="obstacles">{opts}</div></fieldset>')
    block=''.join(qs)
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="referrer" content="no-referrer"><title>Ödev Hızlı Geri Bildirim</title>
    <style>body{{font:16px/1.6 system-ui,sans-serif;background:#f4f7fb;color:#142339;margin:0}}
    main{{max-width:670px;margin:22px auto;padding:22px;background:white;border-radius:14px}}
    fieldset{{border:1px solid #d6deea;border-radius:12px;margin:15px 0;padding:14px}}
    legend{{font-weight:650}}label{{cursor:pointer}}.choices{{display:flex;gap:10px;flex-wrap:wrap}}
    .choices label{{border:1px solid #bccce4;border-radius:8px;padding:8px 12px}}
    .obstacles label{{display:block;margin:7px 0}}button{{background:#1557ac;color:white;
    border:0;border-radius:9px;padding:13px 18px;font-weight:bold;font-size:16px}}
    .muted{{color:#56657b}}@media(max-width:600px){{main{{margin:0;border-radius:0;padding:17px}}}}</style></head>
    <body><main><h1>{escape(data['title'])}</h1>
    <p><strong>Ders/Konu:</strong> {escape(data['lesson'])} / {escape(data['topic'])}</p>
    <p class="muted">Gönüllü kısa geri bildirimdir. Tamamlandı işareti ve notlar değişmez.
    Yanıtları öğretmen inceleyecektir. Bu form bir öğrenme testi veya tanı değildir.</p>
    <p><strong>Ölçek:</strong> {escape(data['scale'])}</p>
    <form action="/h/{token}" method="post">{block}
    <p><label><input type="checkbox" name="consent" value="yes" required>
    Bu gönüllü gözlemin seçilen öğrenci için öğretmen tarafından incelenip
    ayrı bir akademik geri bildirim kaydı olarak saklanacağını anladım.</label></p>
    <button type="submit">Yanıtlarımı gönder</button></form></main></body></html>'''


@router.get('/h/{token}',response_class=HTMLResponse)
def open_feedback(token: str):
    try:data=feedback.read_invite(token)
    except ValueError as exc:_response_error(exc)
    return HTMLResponse(_form_html(token,data),headers=_HEADERS)


@router.post('/h/{token}',response_class=HTMLResponse)
async def post_feedback(token: str, request: Request):
    raw_len=request.headers.get('content-length','')
    if not raw_len.isdigit() or int(raw_len)>8192:
        raise HTTPException(413,'Form gönderimi çok büyük.')
    form=await request.form()
    if len(form)!=5 or set(form.keys())!={'completion','understanding','time_fit','obstacle','consent'} or form.get('consent')!='yes':
        raise HTTPException(422,'Bütün soruları yanıtlayınız.')
    try:
        answers={key:int(form[key]) if form[key] in ('1','2','3','4','5') else None
                 for key in ('completion','understanding','time_fit')}
        answers['obstacle']=form['obstacle']
        feedback.submit(token,answers)
    except (ValueError,TypeError) as exc:
        msg=str(exc)
        raise HTTPException(410 if ('süresi doldu' in msg or 'daha önce' in msg) else 422,msg) from None
    return HTMLResponse('<!doctype html><html lang="tr"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<body style="font-family:system-ui;padding:24px"><h1>Yanıtınız alındı.</h1>'
        '<p>Öğretmenin incelemesine iletildi. Teşekkür ederiz.</p></body></html>',headers=_HEADERS)


@router.post('/api/v12/homework-feedback/invites')
async def create_invite(request: Request):
    try:
        data=await request.json()
        return feedback.create_link(data.get('student_id'),data.get('homework_id'),data.get('respondent'))
    except (ValueError,TypeError,AttributeError) as exc:
        raise HTTPException(422,str(exc)) from None


@router.get('/api/v12/homework-feedback/submissions')
def get_submissions(student_id:int):
    try:return feedback.list_feedback(student_id,pending_only=False)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None


@router.post('/api/v12/homework-feedback/submissions/{reply_id}/{decision}')
def decide_submission(reply_id:int,decision:str,student_id:int):
    try:return feedback.decide(student_id,reply_id,decision)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None


@router.post('/api/v12/homework-feedback/invites/{invite_id}/revoke')
def revoke_invite(invite_id:int,student_id:int):
    try:feedback.revoke(student_id,invite_id)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    return {'state':'revoked'}
