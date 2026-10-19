# -*- coding: utf-8 -*-
"""V3.5.50 - opt-in two-way feedback gateway for the separate mobile PDF.

A PDF/WhatsApp link is a student-scoped *locator*, never login/permission.
Live service requires production HTTPS, separately verified recipient sessions,
CSRF, guardian/student ACL and a trusted teacher issuing invitation links.
Writes ONLY to a separate SQLite feedback inbox, NEVER to homework/academics.
No listening socket, account provider or public deployment is supplied here.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing
from hashlib import sha256
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import hmac
import os
import secrets
import sqlite3
import time

from services.mobile_pdf_live_gateway_v3547 import validate_https_origin, REF_PATTERN
from services.mobile_pdf_secure_portal_v3548 import _student, _scope, TeacherPrincipal

FEEDBACK_PREFIX = '/mobile/feedback/'
ROLES = ('student', 'parent')
STATUS = {
    'started': 'Çalışmaya başladım',
    'completed_claim': 'Çalışmayı bitirdim (beyan)',
    'need_help': 'Yardıma ihtiyacım var',
    'meeting_request': 'Görüşme talep ediyorum',
}
REASONS = {
    'none': 'Ek açıklama yok',
    'time': 'Zaman planlaması',
    'difficult': 'Sorular zorlayıcı',
    'technical': 'Teknik sorun',
    'other': 'Diğer',
}
BASE_HEADERS = (
    ('Content-Type', 'text/html; charset=utf-8'),
    ('Cache-Control', 'no-store, private'),
    ('Pragma', 'no-cache'),
    ('Referrer-Policy', 'no-referrer'),
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"),
)


@dataclass(frozen=True)
class RecipientPrincipal:
    """Only constructed from a VERIFIED external school login session."""
    tenant_id: str
    subject_id: str
    student_id: int
    role: str
    session_id: str
    expires_at: float

    def __post_init__(self):
        _scope(self.tenant_id, 'Kurum')
        _scope(self.subject_id, 'Hesap')
        _scope(self.session_id, 'Oturum')
        _student(self.student_id)
        if self.role not in ROLES or type(self.expires_at) not in (int, float):
            raise ValueError('Geçersiz alıcı oturumu.')


@dataclass(frozen=True)
class Invite:
    tenant_id: str
    teacher_id: str
    student_id: int
    role: str
    expires_at: float
    used: bool


class FeedbackInbox:
    """Separate single-node SQLite pilot; real deployment needs managed storage."""
    def __init__(self, registry_path, *, clock=None, max_active=20000):
        self.path = Path(registry_path).resolve()
        self.clock = clock or time.time
        if type(max_active) is not int or max_active < 1:
            raise ValueError('Geçersiz bağlantı sınırı.')
        self.max_active = max_active
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        with closing(self._db()) as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS feedback_invites (
                digest TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                teacher_id TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                recipient_role TEXT NOT NULL,
                issued_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                used_at REAL
            );
            CREATE INDEX IF NOT EXISTS feedback_expiry ON feedback_invites(expires_at);
            CREATE TABLE IF NOT EXISTS feedback_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invite_digest TEXT NOT NULL UNIQUE REFERENCES feedback_invites(digest),
                tenant_id TEXT NOT NULL,
                teacher_id TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                recipient_role TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                received_at REAL NOT NULL,
                reviewed_at REAL
            );
            CREATE INDEX IF NOT EXISTS feedback_teacher_inbox
                ON feedback_submissions(tenant_id,teacher_id,reviewed_at,received_at);
            ''')

    def _db(self):
        db = sqlite3.connect(str(self.path), isolation_level=None, timeout=5)
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('PRAGMA secure_delete=ON')
        db.execute('PRAGMA foreign_keys=ON')
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _digest(ref):
        return sha256(ref.encode('ascii')).hexdigest()

    def issue(self, *, student_id, tenant_id, teacher_id, role, verified=False, ttl_seconds=86400):
        student_id = _student(student_id)
        tenant_id = _scope(tenant_id, 'Kurum')
        teacher_id = _scope(teacher_id, 'Öğretmen')
        if role not in ROLES or verified is not True:
            raise ValueError('Doğrulanmış öğrenci ve alıcı gereklidir.')
        if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 7*86400:
            raise ValueError('Bağlantı süresi 60 saniye ile 7 gün arasında olmalıdır.')
        now = float(self.clock())
        ref = secrets.token_urlsafe(32)
        with closing(self._db()) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM feedback_invites WHERE expires_at <= ? AND used_at IS NULL', (now,))
                active = db.execute('SELECT COUNT(*) FROM feedback_invites WHERE used_at IS NULL').fetchone()[0]
                if active >= self.max_active:
                    raise RuntimeError('Bağlantı sınırına ulaşıldı.')
                db.execute('''INSERT INTO feedback_invites
                    (digest,tenant_id,teacher_id,student_id,recipient_role,issued_at,expires_at)
                    VALUES(?,?,?,?,?,?,?)''',
                    (self._digest(ref), tenant_id, teacher_id, student_id, role, now, now+ttl_seconds))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        return ref

    def get(self, ref):
        if not isinstance(ref, str) or REF_PATTERN.fullmatch(ref) is None:
            return None
        with closing(self._db()) as db:
            row = db.execute('''SELECT tenant_id,teacher_id,student_id,recipient_role,expires_at,used_at
                FROM feedback_invites WHERE digest=? AND expires_at>?''',
                (self._digest(ref), float(self.clock()))).fetchone()
        if row is None:
            return None
        return Invite(row['tenant_id'],row['teacher_id'],int(row['student_id']),
                      row['recipient_role'],float(row['expires_at']),row['used_at'] is not None)

    def submit(self, ref, *, principal, status, reason='none'):
        if not isinstance(principal, RecipientPrincipal) or float(principal.expires_at) <= float(self.clock()):
            return False
        if status not in STATUS or reason not in REASONS:
            raise ValueError('Desteklenmeyen geri bildirim.')
        if not isinstance(ref, str) or REF_PATTERN.fullmatch(ref) is None:
            return False
        now = float(self.clock())
        with closing(self._db()) as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('''SELECT tenant_id,teacher_id,student_id,recipient_role
                    FROM feedback_invites WHERE digest=? AND used_at IS NULL AND expires_at>?''',
                    (self._digest(ref), now)).fetchone()
                if (row is None or row['tenant_id'] != principal.tenant_id or
                    int(row['student_id']) != principal.student_id or
                    row['recipient_role'] != principal.role):
                    db.execute('ROLLBACK')
                    return False
                result = db.execute('''UPDATE feedback_invites SET used_at=?
                    WHERE digest=? AND used_at IS NULL''',(now,self._digest(ref)))
                if result.rowcount != 1:
                    db.execute('ROLLBACK')
                    return False
                db.execute('''INSERT INTO feedback_submissions
                    (invite_digest,tenant_id,teacher_id,student_id,recipient_role,status,reason,received_at)
                    VALUES(?,?,?,?,?,?,?,?)''',
                    (self._digest(ref),row['tenant_id'],row['teacher_id'],row['student_id'],
                     row['recipient_role'],status,reason,now))
                db.execute('COMMIT')
                return True
            except BaseException:
                db.execute('ROLLBACK')
                raise

    def revoke(self, ref):
        if not isinstance(ref, str) or REF_PATTERN.fullmatch(ref) is None:
            return False
        with closing(self._db()) as db:
            result = db.execute('DELETE FROM feedback_invites WHERE digest=? AND used_at IS NULL',
                                (self._digest(ref),))
            return result.rowcount > 0

    def revoke_teacher(self, tenant_id, teacher_id):
        tenant_id,teacher_id=_scope(tenant_id,'Kurum'),_scope(teacher_id,'Öğretmen')
        with closing(self._db()) as db:
            result=db.execute('DELETE FROM feedback_invites WHERE tenant_id=? AND teacher_id=? AND used_at IS NULL',
                              (tenant_id,teacher_id))
            return result.rowcount

    def teacher_inbox(self, *, principal, limit=100):
        if not isinstance(principal, TeacherPrincipal) or principal.expires_at <= self.clock():
            raise PermissionError('Doğrulanmış öğretmen oturumu gerekir.')
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Geçersiz liste sınırı.')
        with closing(self._db()) as db:
            rows=db.execute('''SELECT id,student_id,recipient_role,status,reason,received_at,reviewed_at
                FROM feedback_submissions WHERE tenant_id=? AND teacher_id=?
                ORDER BY received_at DESC,id DESC LIMIT ?''',
                (principal.tenant_id,principal.teacher_id,limit)).fetchall()
        return [dict(r) for r in rows]

    def mark_reviewed(self, response_id, *, principal):
        if not isinstance(principal, TeacherPrincipal) or principal.expires_at <= self.clock():
            raise PermissionError('Doğrulanmış öğretmen oturumu gerekir.')
        if type(response_id) is not int or response_id < 1:
            raise ValueError('Geçersiz yanıt numarası.')
        with closing(self._db()) as db:
            result = db.execute('''UPDATE feedback_submissions SET reviewed_at=?
                WHERE id=? AND tenant_id=? AND teacher_id=? AND reviewed_at IS NULL''',
                (float(self.clock()),response_id,principal.tenant_id,principal.teacher_id))
        return result.rowcount == 1


def validate_feedback_pdf_link(url, origin):
    try:
        expected = validate_https_origin(origin)
        parsed = urlsplit(url)
        ref = parsed.path[len(FEEDBACK_PREFIX):] if parsed.path.startswith(FEEDBACK_PREFIX) else ''
        return (parsed.scheme == 'https' and parsed.netloc == urlsplit(expected).netloc
                and parsed.path == FEEDBACK_PREFIX+ref and REF_PATTERN.fullmatch(ref) is not None
                and parsed.query == '' and parsed.fragment == '' and parsed.username is None
                and parsed.password is None)
    except (TypeError, ValueError, AttributeError):
        return False


def prepare_feedback_links(context, inbox, *, principal, authorize_student, recipient_eligible,
                           origin=None, explicit_opt_in=False, deployment_ready=False,
                           ttl_seconds=86400, clock=None):
    """Issue ONLY after externally authenticated teacher and recipient relationship checks."""
    if not (explicit_opt_in is True and deployment_ready is True and origin):
        return {}
    origin=validate_https_origin(origin)
    now=float((clock or inbox.clock)())
    if not isinstance(principal, TeacherPrincipal) or principal.expires_at <= now:
        return {}
    if not callable(authorize_student) or not callable(recipient_eligible):
        raise ValueError('Öğretmen ve alıcı yetki denetleyicileri gereklidir.')
    result={}
    for sid_text, card in (context.get('student_cards') or {}).items():
        try: sid=_student(sid_text)
        except (ValueError,TypeError): continue
        if not isinstance(card,dict) or not card.get('verified') or not card.get('contact_allowed'):
            continue
        try: allowed=authorize_student(principal,sid) is True
        except Exception: allowed=False
        if not allowed: continue
        role_links={}
        for role in ROLES:
            try: eligible=recipient_eligible(principal,sid,role) is True
            except Exception: eligible=False
            if eligible:
                ref=inbox.issue(student_id=sid,tenant_id=principal.tenant_id,
                    teacher_id=principal.teacher_id,role=role,verified=True,ttl_seconds=ttl_seconds)
                role_links[role]=origin+FEEDBACK_PREFIX+ref
        if role_links: result[str(sid)]=role_links
    return result


def _html_form(csrf):
    # No student name, phone or internal academic data in the form itself.
    options=''.join(f'<option value="{escape(code)}">{escape(label)}</option>' for code,label in STATUS.items())
    reasons=''.join(f'<option value="{escape(code)}">{escape(label)}</option>' for code,label in REASONS.items())
    return ('<!doctype html><html lang="tr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Öğrenci Durum Bildirimi</title><style>'
            'body{font:17px system-ui;background:#edf3fc;color:#142a4e;padding:14px}'
            'main{max-width:520px;margin:auto;background:white;padding:23px;border-radius:18px}'
            'select,button{font:inherit;width:100%;padding:13px;margin:9px 0;border-radius:8px}'
            'button{background:#174ba9;color:white;border:0}</style></head><body><main>'
            '<h1>Akademik Durum Bildirimi</h1><p>Bu bildirim öğretmenin kontrol kuyruğuna alınır; '
            'ödev doğrudan tamamlanmış olarak işaretlenmez.</p>'
            '<form method="post"><label>Durum<select name="status" required>'+options+'</select></label>'
            '<label>Gerekirse gerekçe<select name="reason">'+reasons+'</select></label>'
            '<input type="hidden" name="csrf" value="'+escape(csrf,quote=True)+'">'
            '<button type="submit">Bildirimi Gönder</button></form>'
            '<small>Yalnızca oturum ve öğrenci/veli yetkisi doğrulanınca kullanılabilir.</small>'
            '</main></body></html>').encode('utf-8')


def create_feedback_wsgi_app(inbox, *, origin, authenticate_session, authorize_recipient,
                             csrf_secret, deployment_ready=False, clock=None):
    """WSGI factory: secure deployment providers REQUIRED; no socket is opened.

    authenticate_session(environ) must independently verify an httpOnly secure
    cookie and return RecipientPrincipal. authorize_recipient checks school ACL.
    Reverse proxy must terminate real TLS and strip client-supplied forwarding
    headers; we deliberately do not trust HTTP_X_FORWARDED_PROTO here.
    """
    if deployment_ready is not True:
        raise ValueError('HTTPS ve gerçek kullanıcı oturumları kurulmadan servis açılamaz.')
    origin=validate_https_origin(origin)
    if not callable(authenticate_session) or not callable(authorize_recipient):
        raise ValueError('Gerçek oturum ve öğrenci yetkisi doğrulaması gereklidir.')
    if not isinstance(csrf_secret,bytes) or len(csrf_secret)<32:
        raise ValueError('Sunucu tarafında güçlü CSRF anahtarı gerekli.')
    nowfunc=clock or inbox.clock
    netloc=urlsplit(origin).netloc

    def csrf(ref,session):
        return hmac.new(csrf_secret,(ref+'\x00'+session).encode('utf-8'),'sha256').hexdigest()

    def app(environ,start_response):
        def respond(status,body):
            start_response(status,list(BASE_HEADERS))
            return [body if environ.get('REQUEST_METHOD') != 'HEAD' else b'']
        method=environ.get('REQUEST_METHOD')
        if method not in ('GET','HEAD','POST'):
            return respond('405 Method Not Allowed',b'Izin verilmeyen islem.')
        if environ.get('wsgi.url_scheme')!='https' or environ.get('HTTP_HOST')!=netloc:
            return respond('403 Forbidden',b'HTTPS baglantisi gerekli.')
        path=environ.get('PATH_INFO','')
        ref=path[len(FEEDBACK_PREFIX):] if path.startswith(FEEDBACK_PREFIX) else ''
        if not ref or REF_PATTERN.fullmatch(ref) is None or path != FEEDBACK_PREFIX+ref:
            return respond('404 Not Found',b'Gecerli baglanti bulunamadi.')
        # Never trust role, tenant or student identifiers submitted by clients.
        try: p=authenticate_session(environ)
        except Exception: p=None
        if not isinstance(p,RecipientPrincipal) or p.expires_at <= nowfunc():
            return respond('401 Unauthorized',b'Oturum acmaniz gerekir.')
        invite=inbox.get(ref)
        if invite is None:
            return respond('404 Not Found',b'Baglanti bulunamadi veya suresi doldu.')
        if (invite.tenant_id!=p.tenant_id or invite.student_id!=p.student_id or
            invite.role!=p.role):
            return respond('403 Forbidden',b'Bu bildirim icin yetkiniz yok.')
        try: allowed=authorize_recipient(p,invite.student_id,invite.role) is True
        except Exception: allowed=False
        if not allowed:
            return respond('403 Forbidden',b'Bu bildirim icin yetkiniz yok.')
        if invite.used:
            return respond('409 Conflict',b'Bu davet icin bildirim daha once alinmis.')
        if method in ('GET','HEAD'):
            return respond('200 OK',_html_form(csrf(ref,p.session_id)))
        if environ.get('HTTP_ORIGIN') != origin:
            return respond('403 Forbidden',b'Gonderim kaynagi dogrulanamadi.')
        if environ.get('CONTENT_TYPE','').split(';',1)[0].strip().lower() != 'application/x-www-form-urlencoded':
            return respond('415 Unsupported Media Type',b'Form bicimi gecersiz.')
        try: size=int(environ.get('CONTENT_LENGTH','-1'))
        except (ValueError,TypeError): size=-1
        if size<1 or size>2048:
            return respond('413 Content Too Large',b'Form boyutu gecersiz.')
        stream=environ.get('wsgi.input')
        if stream is None:
            return respond('400 Bad Request',b'Form verisi eksik.')
        raw=stream.read(size)
        if len(raw)!=size:
            return respond('400 Bad Request',b'Eksik form verisi.')
        try:
            fields=parse_qs(raw.decode('utf-8'),strict_parsing=True,keep_blank_values=True,
                            max_num_fields=5)
            if set(fields) != {'status','reason','csrf'} or any(len(v)!=1 for v in fields.values()):
                raise ValueError('Eksik veya çoklu alan')
            status,reason,token=(fields[k][0] for k in ('status','reason','csrf'))
        except (UnicodeError,ValueError):
            return respond('400 Bad Request',b'Form alanlari gecersiz.')
        if not hmac.compare_digest(token,csrf(ref,p.session_id)):
            return respond('403 Forbidden',b'Oturum dogrulamasi basarisiz.')
        if status not in STATUS or reason not in REASONS:
            return respond('400 Bad Request',b'Bildirim secimi gecersiz.')
        if not inbox.submit(ref,principal=p,status=status,reason=reason):
            return respond('409 Conflict',b'Bildirim artik kullanilamiyor.')
        return respond('200 OK',b'<html lang="tr"><meta charset="utf-8"><p>Bildirim ogretmene inceleme icin ulasti. Odev durumu otomatik degismedi.</p></html>')
    return app
