# -*- coding: utf-8 -*-
"""V3.5.48 — scoped, persistent and *opt-in* live-PDF link lifecycle.

No listening socket, login form, public URL, or student data mutation here.
Production MUST provide real authenticated session+tenant/student ACL and HTTPS.
Token registry is a SEPARATE SQLite file; never pass the academic database path.
Use a single shared encrypted/backed-up registry storage when scaling to multiple
instances; SQLite is intended for a single server pilot only.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
import datetime as dt
import hmac
import os
import re
import secrets
import sqlite3
import time

from services.mobile_pdf_live_gateway_v3547 import (
    PREFIX, REF_PATTERN, MAX_TTL, validate_https_origin,
    _read_verified_card, _html_page,
)

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_:\-]{0,79}$')
_DEFAULT_RESPONSE_HEADERS = [
    ('Content-Type','text/html; charset=utf-8'),
    ('Cache-Control','no-store, private'),
    ('Pragma','no-cache'),
    ('Referrer-Policy','no-referrer'),
    ('X-Content-Type-Options','nosniff'),
    ('X-Frame-Options','DENY'),
    ('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"),
]


def _scope(value, label):
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f'{label} için geçerli bir kimlik gerekli.')
    return value


def _student(value):
    if type(value) is int and value > 0:
        return value
    if type(value) is str and value.isascii() and value.isdecimal() and value == str(int(value)) and int(value)>0:
        return int(value)
    raise ValueError('Doğrulanmış pozitif öğrenci kimliği gerekli.')


@dataclass(frozen=True)
class TeacherPrincipal:
    """Identity returned ONLY by externally verified session provider.

    Constructing this struct is NOT authentication. Do not trust HTTP headers,
    query parameters or client-submitted cookies as its source.
    """
    tenant_id: str
    teacher_id: str
    expires_at: float
    role: str = 'teacher'

    def __post_init__(self):
        _scope(self.tenant_id,'Kurum')
        _scope(self.teacher_id,'Öğretmen')
        if self.role not in ('teacher','institution_admin'):
            raise ValueError('Yetkisiz rol.')
        if type(self.expires_at) not in (int,float):
            raise ValueError('Geçersiz oturum süresi.')


@dataclass(frozen=True)
class ScopedLink:
    student_id: int
    tenant_id: str
    teacher_id: str
    expires_at: float


class PersistentStudentLinkStore:
    """SQLite hashed-token store, revocation, expiry, and per-teacher rate gate.

    Only link-metadata is written into the separate registry database. No
    student names, phone numbers or passwords are persisted. A PDF ref alone
    grants *zero* student access and must always be checked against session.
    """
    def __init__(self, registry_path, *, clock=None, max_active=20000):
        self.path = Path(registry_path).resolve()
        self.clock = clock or time.time
        if type(max_active) is not int or max_active < 1:
            raise ValueError('Geçersiz bağlantı limiti.')
        self.max_active = max_active
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            # The registry contains link metadata: restrict file access on POSIX.
            fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        with closing(self._connect()) as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS live_pdf_links (
                token_digest TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                teacher_id TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL
              );
              CREATE INDEX IF NOT EXISTS idx_live_pdf_expiry ON live_pdf_links(expires_at);
              CREATE TABLE IF NOT EXISTS rate_windows (
                key_digest TEXT PRIMARY KEY,
                window_start INTEGER NOT NULL,
                hits INTEGER NOT NULL
              );
            ''')

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('PRAGMA secure_delete=ON')
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _digest(ref):
        return sha256(ref.encode('ascii')).hexdigest()

    def issue(self, *, student_id, tenant_id, teacher_id, verified=False, ttl_seconds=3600):
        sid = _student(student_id)
        tenant_id = _scope(tenant_id,'Kurum')
        teacher_id = _scope(teacher_id,'Öğretmen')
        if verified is not True:
            raise ValueError('Öğrenci kimliği doğrulanmalı.')
        if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= MAX_TTL:
            raise ValueError('Bağlantı süresi 60 saniye ile 7 gün arasında olmalı.')
        now = float(self.clock())
        ref = secrets.token_urlsafe(32)
        with closing(self._connect()) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM live_pdf_links WHERE expires_at <= ?', (now,))
                count = db.execute('SELECT COUNT(*) FROM live_pdf_links').fetchone()[0]
                if count >= self.max_active:
                    raise RuntimeError('Bağlantı kapasitesi doldu.')
                db.execute('''INSERT INTO live_pdf_links
                            (token_digest, tenant_id, teacher_id, student_id, expires_at, created_at)
                            VALUES (?,?,?,?,?,?)''',
                           (self._digest(ref), tenant_id, teacher_id, sid, now+ttl_seconds, now))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        return ref

    def resolve(self, ref):
        if not isinstance(ref,str) or REF_PATTERN.fullmatch(ref) is None:
            return None
        with closing(self._connect()) as db:
            row = db.execute('''SELECT student_id,tenant_id,teacher_id,expires_at FROM live_pdf_links
                                WHERE token_digest=? AND expires_at>?''',
                             (self._digest(ref), float(self.clock()))).fetchone()
        if not row:
            return None
        return ScopedLink(int(row['student_id']),row['tenant_id'],row['teacher_id'],row['expires_at'])

    def revoke(self, ref):
        if not isinstance(ref,str) or REF_PATTERN.fullmatch(ref) is None:
            return False
        with closing(self._connect()) as db:
            result = db.execute('DELETE FROM live_pdf_links WHERE token_digest=?',(self._digest(ref),))
            return result.rowcount > 0

    def revoke_teacher(self, tenant_id, teacher_id):
        """Revoke all links when teacher loses access or an account is disabled."""
        tenant_id = _scope(tenant_id,'Kurum')
        teacher_id = _scope(teacher_id,'Öğretmen')
        with closing(self._connect()) as db:
            result = db.execute('DELETE FROM live_pdf_links WHERE tenant_id=? AND teacher_id=?',
                                (tenant_id,teacher_id))
            return result.rowcount

    def check_rate(self, tenant_id, teacher_id, *, maximum=60, interval_seconds=60):
        """Bound total authenticated lookups without trusting client IP headers.

        This is basic per-user throttling, NOT a replacement for reverse proxy
        IP rate-limits, HTTPS access logging or a central distributed gateway.
        """
        tenant_id = _scope(tenant_id,'Kurum')
        teacher_id = _scope(teacher_id,'Öğretmen')
        if type(maximum) is not int or maximum < 1 or type(interval_seconds) is not int or interval_seconds < 1:
            raise ValueError('Geçersiz hız sınırı.')
        ident = sha256((tenant_id+'\x00'+teacher_id).encode('utf-8')).hexdigest()
        now = int(self.clock())
        with closing(self._connect()) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM rate_windows WHERE window_start < ?', (now-interval_seconds,))
                row = db.execute('SELECT window_start,hits FROM rate_windows WHERE key_digest=?',(ident,)).fetchone()
                if row is None or now-row['window_start'] >= interval_seconds:
                    db.execute('INSERT INTO rate_windows VALUES (?,?,1) ON CONFLICT(key_digest) '
                               'DO UPDATE SET window_start=excluded.window_start,hits=1',(ident,now))
                    permitted = True
                elif row['hits'] >= maximum:
                    permitted = False
                else:
                    db.execute('UPDATE rate_windows SET hits=hits+1 WHERE key_digest=?',(ident,))
                    permitted = True
                db.execute('COMMIT')
                return permitted
            except BaseException:
                db.execute('ROLLBACK')
                raise


def prepare_scoped_pdf_links(context, registry, *, principal, authorize_student,
                             origin=None, explicit_opt_in=False, deployment_ready=False,
                             ttl_seconds=3600, clock=None):
    """Create PDF URL map ONLY after real login, ACL, HTTPS and opt-in.

    Caller must obtain principal from trusted identity provider; there is NO
    desktop-side user/password or fake authentication in this module.
    """
    if not (explicit_opt_in and deployment_ready and origin and callable(authorize_student)):
        return {}
    now = float((clock or time.time)())
    if not isinstance(principal,TeacherPrincipal) or principal.expires_at <= now:
        return {}
    base = validate_https_origin(origin)
    result = {}
    for sid_text, card in (context.get('student_cards') or {}).items():
        try:
            sid = _student(sid_text)
        except (TypeError,ValueError):
            continue
        if not isinstance(card,dict) or card.get('verified') is not True or card.get('state') == 'LINK_REVIEW':
            continue
        try:
            if authorize_student(principal,sid) is not True:
                continue
        except Exception:
            continue
        ref=registry.issue(student_id=sid, tenant_id=principal.tenant_id,
                           teacher_id=principal.teacher_id, verified=True,
                           ttl_seconds=ttl_seconds)
        result[str(sid)] = base + PREFIX + ref
    return result


def create_scoped_mobile_wsgi_app(registry, academic_db_path, *, origin,
                                  authenticate_session, authorize_student, card_reader=None,
                                  clock=None, max_per_minute=60):
    """Production-facing WSGI adapter, no built-in login or server startup.

    authenticate_session MUST use a real, server-validated login session.
    Neither X-Forwarded headers, public URL nor PDF ref constitutes login.
    Caller must also connect authorize_student to database ACL each request.
    Server must set trusted `wsgi.url_scheme=https` after TLS termination.
    """
    if not callable(authenticate_session) or not callable(authorize_student):
        raise ValueError('Gerçek oturum ve yetki sağlayıcıları zorunludur.')
    public_origin = validate_https_origin(origin)
    expected_host = urlsplit(public_origin).netloc
    clock = clock or time.time
    reader = card_reader or (lambda sid: _read_verified_card(academic_db_path,sid))

    def app(environ, start_response):
        method = environ.get('REQUEST_METHOD')
        def response(status, body=b''):
            start_response(status, list(_DEFAULT_RESPONSE_HEADERS))
            return [] if method == 'HEAD' else [body]
        if method not in ('GET','HEAD'):
            return response('405 Method Not Allowed')
        # Never trust user-controlled X-Forwarded-Proto/Host; front end must
        # supply correct trusted WSGI scheme and host after TLS termination.
        if environ.get('wsgi.url_scheme') != 'https' or environ.get('HTTP_HOST') != expected_host:
            return response('404 Not Found')
        try:
            principal = authenticate_session(environ)
        except Exception:
            principal = None
        if not isinstance(principal,TeacherPrincipal) or principal.expires_at <= float(clock()):
            return response('401 Unauthorized',b'Oturum dogrulanamadi.')
        try:
            if not registry.check_rate(principal.tenant_id,principal.teacher_id,maximum=max_per_minute):
                return response('429 Too Many Requests',b'Istek siniri asildi.')
        except Exception:
            return response('503 Service Unavailable')
        path = environ.get('PATH_INFO','')
        if not isinstance(path,str) or not path.startswith(PREFIX):
            return response('404 Not Found')
        ref = path[len(PREFIX):]
        scope = registry.resolve(ref)
        if scope is None:
            return response('404 Not Found')
        # Exact owner *and* tenant are required even for another admin account.
        if not (hmac.compare_digest(scope.tenant_id,principal.tenant_id) and
                hmac.compare_digest(scope.teacher_id,principal.teacher_id)):
            return response('404 Not Found')
        try:
            if authorize_student(principal,scope.student_id) is not True:
                return response('403 Forbidden')
        except Exception:
            return response('403 Forbidden')
        try:
            record = reader(scope.student_id)
        except Exception:
            record = None
        if not record or not isinstance(record[1],dict) or record[1].get('verified') is not True:
            return response('404 Not Found')
        return response('200 OK',_html_page(record[0],record[1]))
    return app
