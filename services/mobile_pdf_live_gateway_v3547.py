# -*- coding: utf-8 -*-
"""V3.5.47 — opt-in read-only academic mobile gateway contract.

SECURITY BOUNDARY: this is NOT started by the desktop application. A trusted
HTTPS deployment must supply BOTH a real authenticated principal provider and
an independent per-student authorization checker. PDF refs carry no user ID,
password, or credentials. A ref never grants authorization by itself.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
from html import escape
import re
import secrets
import sqlite3
import threading
from pathlib import Path
from contextlib import closing
from urllib.parse import urlsplit, urlunsplit, quote

REF_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{32,90}$')
PREFIX = '/mobile/academic/r/'
MAX_TTL = 7 * 24 * 3600


def _positive_id(value):
    if type(value) is int and value > 0:
        return value
    if type(value) is str and value.isascii() and value.isdecimal() and str(int(value)) == value and int(value) > 0:
        return int(value)
    return None


def validate_https_origin(origin):
    """Allow only canonical public HTTPS origins, no URL userinfo or path."""
    if not isinstance(origin, str):
        raise ValueError('Canlı bağlantı için HTTPS kökeni belirtilmeli.')
    parsed = urlsplit(origin)
    hostname = parsed.hostname or ''
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError('IP adresi üzerinden canlı bağlantı etkinleştirilemez.')
    if (parsed.scheme != 'https' or not hostname or '.' not in hostname or
        parsed.username is not None or parsed.password is not None or
        parsed.path not in ('', '/') or parsed.query or parsed.fragment or
        hostname.lower() in ('localhost', 'example.com', 'example.org') or
        hostname.endswith(('.localhost', '.local', '.internal')) or
        any(c.isspace() for c in origin) or any(c in hostname for c in '\\%')):
        raise ValueError('Yalnızca gerçek HTTPS uygulama alan adı kullanılabilir.')
    try:
        port = parsed.port
    except ValueError as e:
        raise ValueError('Geçersiz HTTPS bağlantı noktası.') from e
    # Reject nonstandard ports: mobile reverse proxy must be ordinary HTTPS.
    if port not in (None, 443):
        raise ValueError('Canlı bağlantı HTTPS/443 üzerinde olmalıdır.')
    return 'https://' + hostname.lower() + ('' if port is None else ':443')


def validate_pdf_live_link(url, origin):
    """Reject URLs not targeting the configured, authenticated route."""
    try:
        base = validate_https_origin(origin)
        part = urlsplit(url)
        token = part.path[len(PREFIX):] if part.path.startswith(PREFIX) else ''
        return (isinstance(url, str) and
                part.scheme == 'https' and part.netloc == urlsplit(base).netloc and
                part.path == PREFIX + token and bool(REF_PATTERN.fullmatch(token)) and
                not part.query and not part.fragment and
                part.username is None and part.password is None)
    except (TypeError, ValueError):
        return False


class StudentLinkRegistry:
    """Ephemeral, student-bound opaque references, not authentication tokens."""
    def __init__(self, *, clock=None, limit=10000):
        self._clock = clock or (lambda: dt.datetime.now(dt.timezone.utc).timestamp())
        self._entries = {}
        self._lock = threading.RLock()
        self.limit = limit

    def issue(self, student_id, *, verified=False, ttl_seconds=24*3600):
        sid = _positive_id(student_id)
        if not verified or sid is None or type(ttl_seconds) is not int or not 60 <= ttl_seconds <= MAX_TTL:
            raise ValueError('Yalnızca doğrulanmış öğrenciye süreli bağlantı hazırlanabilir.')
        with self._lock:
            now = self._clock()
            self._entries = {ref:entry for ref,entry in self._entries.items() if entry[1] > now}
            if len(self._entries) >= self.limit:
                raise RuntimeError('Bağlantı kapasitesi doldu.')
            ref = secrets.token_urlsafe(32)
            self._entries[ref] = (sid, now + ttl_seconds)
            return ref

    def resolve(self, ref):
        if not isinstance(ref,str) or not REF_PATTERN.fullmatch(ref):
            return None
        with self._lock:
            entry = self._entries.get(ref)
            if not entry:
                return None
            if self._clock() >= entry[1]:
                del self._entries[ref]
                return None
            return entry[0]

    def revoke(self, ref):
        with self._lock:
            self._entries.pop(ref, None)


def prepare_pdf_links(context, registry, *, https_origin=None, enabled=False,
                      authenticated_gateway_ready=False, ttl_seconds=24*3600):
    """Explicit opt-in only: no live links until external login gateway exists.

    A trusted caller must attest real HTTPS + authentication before enabling.
    Copies of PDF do not carry credentials, only opaque selectors; login remains
    mandatory on every live request. Unverified student = no link.
    """
    if not enabled or not authenticated_gateway_ready or not https_origin:
        return {}
    origin = validate_https_origin(https_origin)
    result = {}
    for sid_text, card in (context.get('student_cards') or {}).items():
        sid = _positive_id(sid_text)
        if sid is None or not isinstance(card, dict) or not card.get('verified') or card.get('state') == 'LINK_REVIEW':
            continue
        ref = registry.issue(sid, verified=True, ttl_seconds=ttl_seconds)
        result[str(sid)] = origin + PREFIX + ref
    return result


def _read_verified_card(db_path, sid):
    """Read current data from the SAME domain model as the PDF, never write."""
    from services.mobile_pdf_system_bridge_v3546 import _verified_student
    from urllib.parse import quote as urlquote
    path = Path(db_path)
    if not path.is_file():
        return None
    uri = 'file:' + urlquote(str(path.resolve()), safe='/:') + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=3)) as con:
        con.execute('PRAGMA query_only=ON')
        con.execute('BEGIN')
        try:
            row = con.execute('SELECT ad,soyad,ogr_tel,veli_tel1 FROM ogrenci WHERE id=? AND aktif=1', (sid,)).fetchone()
            if not row:
                return None
            name = ' '.join(str(x or '').strip() for x in row[:2]).strip()
            snapshot = {'name':name, 'phone':row[2], 'parent_phone':row[3], 'contact_conflict':False}
            card = _verified_student(con, sid, dt.date.today(), snapshot)
            if not card.get('verified'):
                return None
            # No phone/email field is returned to mobile web page.
            return name, card
        finally:
            con.execute('ROLLBACK')


def _html_page(name, card):
    """Static escaped HTML, no external scripts, trackers or writable forms."""
    def txt(value): return escape(str(value if value is not None else 'Doğrulanmadı'), quote=True)
    homework = card.get('homework') or {}
    plan = card.get('coaching_plan') or {}
    exam = card.get('exam') or {}
    follow = card.get('followup') or {}
    warning = ('Kısmi kaynak: bazı akademik kayıtlar doğrulanmadı.' if card.get('partial')
               else 'Bu veriler son doğrulanan yerel kayıtlara dayanır.')
    return ("<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Güncel Akademik Kart</title><style>"
        "body{font:16px system-ui;background:#eef3fa;color:#132848;margin:0;padding:16px}"
        "main{max-width:560px;margin:auto}.card{background:white;border-radius:14px;padding:17px;margin:12px 0}"
        "h1{font-size:23px}h2{font-size:17px}small{color:#52637b}"
        "</style></head><body><main><h1>Güncel Akademik Kart</h1>"
        "<div class='card'><h2>"+txt(name)+"</h2>"
        "<small>Bu ekran oturum ve öğrenci yetkisi doğrulanmadan açılmaz.</small></div>"
        "<div class='card'><h2>Ödev kanıtı</h2>"
        "<p>Toplam: "+txt(homework.get('total'))+" · Tamamlanan: "+txt(homework.get('completed'))+
        " · Süresi geçmiş açık: "+txt(homework.get('overdue'))+"</p></div>"
        "<div class='card'><h2>Koçluk ve izlem</h2><p>"+txt(plan.get('summary'))+"</p>"
        "<p>İzlem durumu: "+txt(follow.get('state'))+"</p></div>"
        "<div class='card'><h2>Akademik kontrol</h2><p>"+txt(card.get('summary'))+"</p>"
        "<small>Sınav ölçümü: "+txt(exam.get('state'))+". "+txt(warning)+"</small></div>"
        "<small>Bu sayfadan ödev ataması, tamamlama veya mesaj gönderme yapılmaz.</small>"
        "</main></body></html>").encode('utf-8')


def create_readonly_wsgi_app(registry, database_path, *, authenticate=None, authorize=None,
                             card_reader=None):
    """WSGI app. Both authentication and per-student authorization REQUIRED.

    The application does NOT open a listening socket. Only integrate behind a
    real HTTPS reverse proxy with protected sessions, CSRF/rate limits, audit,
    organization scope and privacy review, or use tests with fake authenticator.
    """
    if not callable(authenticate) or not callable(authorize):
        raise ValueError('Kimlik doğrulama ve öğrenci yetki denetimi olmadan servis kurulamaz.')
    reader = card_reader or (lambda sid: _read_verified_card(database_path,sid))
    headers = [('Content-Type','text/html; charset=utf-8'),
               ('Cache-Control','no-store, private'),
               ('Pragma','no-cache'), ('Referrer-Policy','no-referrer'),
               ('X-Content-Type-Options','nosniff'),
               ('X-Frame-Options','DENY'),
               ('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")]

    def app(environ, start_response):
        def reply(code, content):
            start_response(code, headers)
            return [content if environ.get('REQUEST_METHOD') != 'HEAD' else b'']
        if environ.get('REQUEST_METHOD') not in ('GET','HEAD'):
            return reply('405 Method Not Allowed',b'Bu servis salt okunur.')
        try:
            principal = authenticate(environ)
        except Exception:
            principal = None
        if principal is None or principal is False:
            return reply('401 Unauthorized',b'Oturum acmaniz gerekir.')
        path = environ.get('PATH_INFO','')
        if not path.startswith(PREFIX):
            return reply('404 Not Found',b'Bulunamadi.')
        sid = registry.resolve(path[len(PREFIX):])
        if sid is None:
            return reply('404 Not Found',b'Baglanti bulunamadi veya suresi doldu.')
        try:
            permitted = authorize(principal,sid)
        except Exception:
            permitted = False
        if permitted is not True:
            return reply('403 Forbidden',b'Bu ogrenciye erisim yetkiniz yok.')
        try:
            record = reader(sid)
        except Exception:
            record = None
        if not record:
            return reply('404 Not Found',b'Guncel kayit dogrulanamadi.')
        name, card = record
        if not isinstance(card,dict) or not card.get('verified'):
            return reply('404 Not Found',b'Guncel kayit dogrulanamadi.')
        return reply('200 OK',_html_page(name,card))
    return app
