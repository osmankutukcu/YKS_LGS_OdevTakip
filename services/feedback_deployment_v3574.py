# -*- coding: utf-8 -*-
"""Provider-neutral, read-only readiness checks for the optional survey relay.

This module DOES NOT deploy a server or enable remote surveys. It has no
network, SQLite, Qt, or credential-write side effects. Its public diagnostics
never include API keys, invite tokens, student IDs, or raw environment values.

The FastAPI v14 endpoint contract deliberately remains unchanged. A future
provider adapter must implement the same HTTPS endpoints and semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
from typing import Mapping

CONTRACT_VERSION = 'v14'
PUBLIC_ROUTES = ('GET /r/{token}', 'POST /r/{token}')
PRIVATE_ROUTES = (
    'POST /v14/invites', 'GET /v14/replies',
    'POST /v14/invites/{invite_ref}/revoke',
)
SUPPORTED_IMPLEMENTATION = 'fastapi_sqlite'  # code available; not a hosting brand
ALLOWED_DEPLOYMENT = ('standalone_https', 'reverse_proxy_https')


@dataclass(frozen=True)
class Check:
    code: str
    level: str  # ok / pending / blocked
    text: str

    def as_dict(self) -> dict:
        return {'code': self.code, 'level': self.level, 'text': self.text}


@dataclass(frozen=True)
class Report:
    role: str
    state: str  # disabled / incomplete / configuration_ready
    checks: tuple[Check, ...]

    def as_dict(self) -> dict:
        return {
            'role': self.role,
            'state': self.state,
            'live_verified': False,  # offline diagnostic never claims live readiness
            'checks': [check.as_dict() for check in self.checks],
        }


def _url_valid(raw: str) -> bool:
    """Require a simple absolute HTTPS origin; no credentials or URL fragments."""
    if not isinstance(raw, str) or raw.strip() != raw or not raw:
        return False
    try:
        parsed = urlsplit(raw)
        _ = parsed.port  # malformed numeric port should fail closed
    except ValueError:
        return False
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        return False
    if parsed.hostname in ('localhost',) or parsed.hostname.endswith('.localhost'):
        return False
    return True


def _status(role: str, checks: list[Check], disabled: bool = False) -> Report:
    if disabled:
        state = 'disabled'
    elif any(ch.level != 'ok' for ch in checks):
        state = 'incomplete'
    else:
        state = 'configuration_ready'
    return Report(role, state, tuple(checks))


def audit_desktop(environ: Mapping[str, str]) -> Report:
    """Offline Windows-side configuration check. No test traffic generated."""
    checks: list[Check] = []
    enabled = environ.get('YKS_FEEDBACK_RELAY_V14_ENABLED', '').strip() == '1'
    if not enabled:
        checks.append(Check('relay_flag', 'ok', 'Bulut anket bağlantısı kapalı; eski işleyiş korunuyor.'))
        return _status('desktop', checks, disabled=True)
    checks.append(Check('relay_flag', 'ok', 'Opsiyonel anket bağlantısı etkin.'))
    if environ.get('YKS_HOMEWORK_FEEDBACK_V12_ENABLED') == '1':
        checks.append(Check('form_flag', 'ok', 'Mevcut mini anket özelliği açık.'))
    else:
        checks.append(Check('form_flag', 'blocked', 'Mini anket özelliği etkinleştirilmemiş.'))
    if _url_valid(environ.get('YKS_FEEDBACK_RELAY_URL', '')):
        checks.append(Check('https_origin', 'ok', 'Geçerli HTTPS servis adresi yapılandırılmış.'))
    else:
        checks.append(Check('https_origin', 'blocked', 'Geçerli HTTPS servis adresi eksik veya hatalı.'))
    tenant = environ.get('YKS_FEEDBACK_RELAY_TENANT', '')
    if re.fullmatch(r'[A-Za-z0-9_-]{3,48}', tenant):
        checks.append(Check('tenant', 'ok', 'Kurum tanımlayıcısı biçimi geçerli.'))
    else:
        checks.append(Check('tenant', 'blocked', 'Kurum tanımlayıcısı eksik veya biçimi hatalı.'))
    secret = environ.get('YKS_FEEDBACK_RELAY_KEY', '')
    if isinstance(secret, str) and 32 <= len(secret) <= 256:
        checks.append(Check('secret', 'ok', 'Gizli anahtar uzunluğu uygun.'))
    else:
        checks.append(Check('secret', 'blocked', 'Kurum anahtarı eksik veya uzunluğu uygun değil.'))
    checks.append(Check('online_validation', 'pending', 'HTTPS sunucusu ve canlı cihazlar henüz bu araçla sınanmadı.'))
    # "configuration_ready" is reserved for checks that require no follow-up; this
    # intentionally remains incomplete until a separate human live acceptance step.
    return _status('desktop', checks)


def audit_server(environ: Mapping[str, str]) -> Report:
    """Offline backend configuration check; accepts ANY compliant HTTPS host."""
    checks: list[Check] = []
    if _url_valid(environ.get('YKS_FEEDBACK_RELAY_PUBLIC_URL', '')):
        checks.append(Check('public_https', 'ok', 'Herkese açık HTTPS kök adresinin biçimi geçerli.'))
    else:
        checks.append(Check('public_https', 'blocked', 'Herkese açık HTTPS kök adresi gerekli.'))
    path_text = environ.get('YKS_FEEDBACK_RELAY_DB', '')
    location = Path(path_text).expanduser() if path_text else None
    if location is None or not location.is_absolute() or path_text == ':memory:':
        checks.append(Check('persistent_db', 'blocked', 'Mutlak yollu kalıcı sunucu veritabanı tanımlanmalı.'))
    elif not location.parent.is_dir():
        checks.append(Check('persistent_db', 'blocked', 'Veritabanının kalıcı disk dizini henüz bulunmuyor.'))
    else:
        checks.append(Check('persistent_db', 'ok', 'Kalıcı veritabanı için dizin mevcut; disk kalıcılığı ayrıca sınanmalı.'))
    try:
        tenants = json.loads(environ.get('YKS_FEEDBACK_RELAY_TENANT_HASHES', ''))
    except (ValueError, TypeError):
        tenants = None
    good = isinstance(tenants, dict) and bool(tenants) and all(
        re.fullmatch(r'[A-Za-z0-9_-]{3,48}', tenant)
        and isinstance(digest, str)
        and bool(re.fullmatch(r'[a-fA-F0-9]{64}', digest))
        for tenant, digest in tenants.items()
    )
    if good:
        checks.append(Check('tenant_hashes', 'ok', 'Kurumların anahtar özetleri yapılandırılmış.'))
    else:
        checks.append(Check('tenant_hashes', 'blocked', 'Kurum anahtar özetleri eksik veya biçimi hatalı.'))
    checks.append(Check('reverse_proxy', 'pending', 'Gerçek TLS, hız sınırı ve güvenli erişim logları canlıda denetlenmeli.'))
    checks.append(Check('backup_policy', 'pending', 'Yedekleme, veri silme ve saklama süresi henüz doğrulanmadı.'))
    return _status('server', checks)


def public_contract() -> dict:
    """Stable host-independent interface; does not advertise unused providers."""
    return {
        'version': CONTRACT_VERSION,
        'current_implementation': SUPPORTED_IMPLEMENTATION,
        'hosting_provider_selected': False,
        'public_routes': list(PUBLIC_ROUTES),
        'authenticated_routes': list(PRIVATE_ROUTES),
        'authentication': 'tenant-scoped secret (server stores SHA-256 digest)',
        'data_policy': 'local student/homework mapping; remote only invite and answers',
        'state': 'pilot; no live deployment verified',
    }
