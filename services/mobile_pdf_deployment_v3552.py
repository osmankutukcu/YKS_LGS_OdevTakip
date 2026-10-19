# -*- coding: utf-8 -*-
"""V3.5.52: fail-closed composition of mobile PDF live-card and feedback apps.

IMPORTANT: This module does NOT implement school login, deploy TLS, synchronize
Windows' SQLite data, or expose a socket. All three must be independently
provided and verified by the deployment owner before enabling the gateway.

The only academic data access in the gateway is through the existing read-only
card-reader. Feedback is stored in an isolated inbox, never in homework tables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from contextlib import closing
import math
import sqlite3
import time

from services.mobile_pdf_live_gateway_v3547 import PREFIX, validate_https_origin
from services.mobile_pdf_feedback_v3550 import (
    FEEDBACK_PREFIX, FeedbackInbox, create_feedback_wsgi_app,
)
from services.mobile_pdf_secure_portal_v3548 import (
    PersistentStudentLinkStore, create_scoped_mobile_wsgi_app,
)
from services.mobile_pdf_feedback_center_v3551 import FeedbackCenter

_RESPONSE_HEADERS = [
    ('Content-Type', 'text/plain; charset=utf-8'),
    ('Cache-Control', 'no-store, private'),
    ('Referrer-Policy', 'no-referrer'),
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('Content-Security-Policy', "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
]


@dataclass(frozen=True)
class MobileDeploymentConfig:
    """Trusted server-owned configuration, never supplied by a PDF or a user.

    academic_snapshot is a *server-side, separately replicated read-only copy*,
    NOT the Windows live working database. The synchronizer is external.
    last_confirmed_sync must report a *trusted successful synchronization* time.
    """
    origin: str
    academic_snapshot: Path
    link_registry: Path
    feedback_registry: Path
    csrf_secret: bytes = field(repr=False)
    max_snapshot_age_seconds: int = 900

    def __post_init__(self):
        validate_https_origin(self.origin)
        if not isinstance(self.csrf_secret, bytes) or len(self.csrf_secret) < 32:
            raise ValueError('HTTPS servisi için güçlü ayrı bir CSRF anahtarı gereklidir.')
        if type(self.max_snapshot_age_seconds) is not int or not 60 <= self.max_snapshot_age_seconds <= 86400:
            raise ValueError('Veri güncellik sınırı 60 saniye ile 24 saat arasında olmalıdır.')
        files = [Path(self.academic_snapshot).resolve(), Path(self.link_registry).resolve(),
                 Path(self.feedback_registry).resolve()]
        if len(set(files)) != 3:
            raise ValueError('Akademik veri ile bağlantı/yanıt depoları farklı dosyalarda tutulmalıdır.')


def _verified_sqlite_snapshot(path):
    """Very small read-only health probe; never fixes or mutates a database."""
    db_path = Path(path)
    if not db_path.is_file():
        return False
    try:
        with db_path.open('rb') as f:
            if f.read(16) != b'SQLite format 3\x00':
                return False
        from urllib.parse import quote
        uri = 'file:' + quote(str(db_path.resolve()), safe='/:') + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
            db.execute('PRAGMA query_only=ON')
            return db.execute('PRAGMA quick_check(1)').fetchone()[0] == 'ok'
    except (OSError, sqlite3.Error):
        return False


def deployment_status(config, *, last_confirmed_sync=None, now=None):
    """Non-sensitive status for deployment operator; never reports success by assumption."""
    current = float(time.time() if now is None else now)
    result = {
        'https_origin_valid': False,
        'isolated_registry_paths': False,
        'academic_snapshot_readable': False,
        'snapshot_fresh': False,
        'ready_for_traffic': False,
    }
    if not isinstance(config, MobileDeploymentConfig):
        return result
    try:
        validate_https_origin(config.origin)
        result['https_origin_valid'] = True
        distinct = len({Path(p).resolve() for p in (
            config.academic_snapshot, config.link_registry, config.feedback_registry)}) == 3
        result['isolated_registry_paths'] = distinct
        result['academic_snapshot_readable'] = _verified_sqlite_snapshot(config.academic_snapshot)
        if callable(last_confirmed_sync):
            ts = last_confirmed_sync()  # supplied ONLY by trusted synchronizer
            if type(ts) in (int,float) and math.isfinite(ts):
                age = current - float(ts)
                result['snapshot_fresh'] = -60 <= age <= config.max_snapshot_age_seconds
    except Exception:
        pass
    result['ready_for_traffic'] = all(result[k] for k in (
        'https_origin_valid', 'isolated_registry_paths',
        'academic_snapshot_readable', 'snapshot_fresh'))
    return result


@dataclass(frozen=True)
class MobileGatewayRuntime:
    """Callables wired only after explicit deployment operator approval."""
    app: object
    teacher_feedback_provider: object | None
    enabled: bool


def _unavailable(environ, start_response):
    start_response('503 Service Unavailable', list(_RESPONSE_HEADERS))
    return [b'Mobil servis guvenli yapilandirma tamamlanmadan kapali.']


def create_mobile_gateway(config, *,
        teacher_session=None, recipient_session=None,
        authorize_teacher_student=None, authorize_recipient=None,
        desktop_teacher_session=None, teacher_student_label=None,
        last_confirmed_sync=None, card_reader=None,
        explicit_opt_in=False, trusted_https_ready=False,
        identity_provider_verified=False, school_acl_verified=False,
        server_snapshot_sync_verified=False, clock=None):
    """Compose both existing WSGI apps; never invent a school login.

    SECURITY CONTRACT: all callbacks must be server-side providers that verify
    school identity/roles/tenant independently. Boolean attestations are
    deployment prerequisites, not replacements for that verification.

    A disabled gateway neither creates SQLite registry files nor attaches a
    feedback provider to the desktop. Tests may inject simulated callbacks;
    production MUST use genuine school SSO + synchronized, authenticated data.
    """
    if not all(x is True for x in (
        explicit_opt_in, trusted_https_ready, identity_provider_verified,
        school_acl_verified, server_snapshot_sync_verified)):
        return MobileGatewayRuntime(_unavailable, None, False)
    if not isinstance(config, MobileDeploymentConfig):
        raise ValueError('Sunucuya ait geçerli güvenli yapılandırma gerekli.')
    callbacks = (teacher_session, recipient_session, authorize_teacher_student,
                 authorize_recipient, desktop_teacher_session, last_confirmed_sync)
    if any(not callable(f) for f in callbacks):
        raise ValueError('Doğrulanmış kurum oturumu, yetkilendirme ve veri eşitleme servisleri zorunludur.')
    if teacher_student_label is not None and not callable(teacher_student_label):
        raise ValueError('Öğrenci etiketi sağlayıcısı geçersiz.')
    clock = clock or time.time
    if not deployment_status(config, last_confirmed_sync=last_confirmed_sync, now=clock())['ready_for_traffic']:
        raise RuntimeError('Güvenilir sunucu akademik kopyası hazır veya güncel değil.')
    links = PersistentStudentLinkStore(config.link_registry, clock=clock)
    inbox = FeedbackInbox(config.feedback_registry, clock=clock)
    live_app = create_scoped_mobile_wsgi_app(
        links, config.academic_snapshot, origin=config.origin,
        authenticate_session=teacher_session,
        authorize_student=authorize_teacher_student,
        card_reader=card_reader, clock=clock,
    )
    reply_app = create_feedback_wsgi_app(
        inbox, origin=config.origin,
        authenticate_session=recipient_session,
        authorize_recipient=authorize_recipient,
        csrf_secret=config.csrf_secret,
        deployment_ready=True, clock=clock,
    )
    host = urlsplit(config.origin).netloc

    def gateway(environ, start_response):
        # Reject unauthenticated transport *before* consulting or reading any record.
        if (environ.get('wsgi.url_scheme') != 'https' or
                environ.get('HTTP_HOST') != host):
            start_response('403 Forbidden', list(_RESPONSE_HEADERS))
            return [b'HTTPS gereklidir.']
        if not deployment_status(config, last_confirmed_sync=last_confirmed_sync,
                                 now=clock())['ready_for_traffic']:
            return _unavailable(environ, start_response)
        path = environ.get('PATH_INFO', '')
        if isinstance(path, str) and path.startswith(PREFIX):
            return live_app(environ, start_response)
        if isinstance(path, str) and path.startswith(FEEDBACK_PREFIX):
            return reply_app(environ, start_response)
        start_response('404 Not Found', list(_RESPONSE_HEADERS))
        return [b'Bulunamadi.']

    def desktop_feedback_provider():
        # FeedbackCenter checks the session and student ACL *on every action*.
        return FeedbackCenter(
            inbox, principal_provider=desktop_teacher_session,
            authorize_student=authorize_teacher_student,
            student_label=teacher_student_label, clock=clock,
        )

    return MobileGatewayRuntime(gateway, desktop_feedback_provider, True)
