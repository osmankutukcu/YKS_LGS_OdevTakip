# -*- coding: utf-8 -*-
"""V25.3: synthetic cross-Windows-account DPAPI isolation acceptance test.

NO WhatsApp account, sending, network calls, student DB or live credential access.
The real CLI must use WindowsDPAPI and a Windows SID from the OS. Simulated
providers are accepted solely for unit tests and cannot enable sending.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
from typing import Callable

from .dpapi_v250 import WindowsDPAPI, ProtectionError

CHALLENGE = 'v253_synthetic_challenge.json'
WITNESS = 'v253_second_user_result.json'
FINAL = 'v253_final_result.json'
PURPOSE = 'v253-synthetic-cross-user-isolation'
TTL_SECONDS = 24 * 3600
MAX_FILE_BYTES = 8192
VERSION = 'V25.3'

class IsolationTestError(RuntimeError):
    """No sensitive error messages are raised from here."""


def current_windows_sid() -> str:
    """Discover current Windows account SID without exporting name or SID."""
    if os.name != 'nt':
        raise IsolationTestError('Bu doğrulama için gerçek Windows gerekiyor.')
    try:
        result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                                text=True, capture_output=True, check=True,
                                timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        cells = next(csv.reader(io.StringIO(result.stdout)))
        sid = next((part.strip() for part in cells if re.fullmatch(r'S-1-(?:\d+-)+\d+', part.strip())), None)
        if not sid:
            raise ValueError('no SID')
        return sid
    except Exception as exc:
        raise IsolationTestError('Windows kullanıcı kimliği okunamadı.') from exc


def _file(folder: str | Path, name: str) -> Path:
    root = Path(folder).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise IsolationTestError('Test klasörü mevcut ve normal dizin olmalı.')
    target = root / name
    if target.is_symlink():
        raise IsolationTestError('Sembolik bağlantı dosyası reddedildi.')
    return target


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _digest(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _marker(nonce: str, sid: str) -> str:
    return hashlib.sha256((nonce + '|' + sid).encode('utf-8')).hexdigest()


def _write_once(target: Path, payload: dict) -> None:
    # Exclusive creation; no destructive overwrites of another user's test.
    try:
        with target.open('x', encoding='utf-8') as fh:
            fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + '\n')
            fh.flush()
            os.fsync(fh.fileno())
    except FileExistsError as exc:
        raise IsolationTestError('Test kaydı zaten var. Önce eski testi temizleyin.') from exc
    except OSError as exc:
        raise IsolationTestError('Paylaşılan test klasörüne kayıt yazılamadı.') from exc


def _load(target: Path) -> dict:
    if not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
        raise IsolationTestError('Test kaydı yok veya beklenen boyutta değil.')
    try:
        obj = json.loads(target.read_text(encoding='utf-8'))
        if not isinstance(obj, dict):
            raise ValueError('not an object')
        return obj
    except (OSError, ValueError, UnicodeError) as exc:
        raise IsolationTestError('Test kaydı okunamadı.') from exc


def _challenge(folder: Path, now: int):
    obj = _load(_file(folder, CHALLENGE))
    required = {'version', 'nonce', 'creator_marker', 'cipher_b64',
                'plaintext_sha256', 'cipher_sha256', 'created_at', 'expires_at'}
    if set(obj) != required or obj['version'] != VERSION:
        raise IsolationTestError('Test kaydı biçimi geçersiz.')
    if not isinstance(obj['nonce'], str) or not re.fullmatch(r'[0-9a-f]{32}', obj['nonce']):
        raise IsolationTestError('Test kimliği geçersiz.')
    if not all(isinstance(obj[k], str) and re.fullmatch(r'[a-f0-9]{64}', obj[k])
               for k in ('creator_marker', 'plaintext_sha256', 'cipher_sha256')):
        raise IsolationTestError('Test özeti biçimi geçersiz.')
    if not isinstance(obj['created_at'], int) or not isinstance(obj['expires_at'], int):
        raise IsolationTestError('Test zamanı geçersiz.')
    if obj['expires_at'] - obj['created_at'] != TTL_SECONDS or not obj['created_at'] - 60 <= now <= obj['expires_at']:
        raise IsolationTestError('Testin süresi dolmuş veya saat geçersiz.')
    try:
        blob = base64.b64decode(obj['cipher_b64'], validate=True)
    except Exception as exc:
        raise IsolationTestError('Şifreli test içeriği bozuk.') from exc
    if len(blob) > 4096 or _digest_bytes(blob) != obj['cipher_sha256']:
        raise IsolationTestError('Şifreli test içeriği değiştirilmiş.')
    return obj, blob


def _digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def prepare(folder: str | Path, sid: str, protector=None, now: int | None = None) -> dict:
    """User A creates randomized *synthetic* DPAPI sample. Does not touch app."""
    t = int(time.time() if now is None else now)
    root = Path(folder)
    for filename in (CHALLENGE, WITNESS, FINAL):
        if _file(root, filename).exists():
            raise IsolationTestError('Bu klasörde önceki test var. Yeni test için boş klasör kullanın.')
    p = protector if protector is not None else WindowsDPAPI(PURPOSE)
    token = secrets.token_bytes(32)
    ciphertext = p.seal(token)
    if p.open(ciphertext) != token:
        raise IsolationTestError('Birinci kullanıcının şifreleme testi başarısız.')
    nonce = secrets.token_hex(16)
    body = dict(version=VERSION, nonce=nonce, creator_marker=_marker(nonce, sid),
                cipher_b64=base64.b64encode(ciphertext).decode('ascii'),
                plaintext_sha256=_digest_bytes(token), cipher_sha256=_digest_bytes(ciphertext),
                created_at=t, expires_at=t+TTL_SECONDS)
    _write_once(_file(root, CHALLENGE), body)
    return {'version': VERSION, 'phase': 'PREPARED_BY_USER_A',
            'second_user_required': True, 'whatsapp_connection': 'DISABLED',
            'sending_enabled': False}


def verify_other(folder: str | Path, sid: str, protector=None, now: int | None = None) -> dict:
    """User B must be a genuinely different SID; decryption MUST be rejected."""
    t = int(time.time() if now is None else now)
    root = Path(folder)
    obj, ciphertext = _challenge(root, t)
    verifier = _marker(obj['nonce'], sid)
    if verifier == obj['creator_marker']:
        raise IsolationTestError('Bu aynı Windows hesabı. Farklı kullanıcıyla sınayın.')
    if _file(root, WITNESS).exists() or _file(root, FINAL).exists():
        raise IsolationTestError('Bu test daha önce doğrulanmış; yeni boş klasör kullanın.')
    p = protector if protector is not None else WindowsDPAPI(PURPOSE)
    try:
        decoded = p.open(ciphertext)
    except ProtectionError:
        # This is expected if Windows user-scoped DPAPI enforces isolation.
        pass
    except Exception as exc:
        raise IsolationTestError('Şifre çözme testi belirsiz hatayla durdu.') from exc
    else:
        # Under no circumstances call this success, even if plaintext differs.
        _ = decoded
        raise IsolationTestError('GÜVENLİK BAŞARISIZ: ikinci kullanıcı şifreyi açabildi.')
    witness = {'version': VERSION, 'nonce': obj['nonce'], 'user_b_marker': verifier,
               'challenge_sha256': _digest(obj), 'checked_at': t,
               'result': 'SECOND_USER_DPAPI_DENIED'}
    _write_once(_file(root, WITNESS), witness)
    return {'version': VERSION, 'phase': 'SECOND_USER_REJECTED',
            'final_creator_recheck_required': True, 'sending_enabled': False}


def finalize(folder: str | Path, sid: str, protector=None, now: int | None = None) -> dict:
    """User A verifies original ciphertext still decrypts after User B's trial."""
    t = int(time.time() if now is None else now)
    root = Path(folder)
    obj, ciphertext = _challenge(root, t)
    if _marker(obj['nonce'], sid) != obj['creator_marker']:
        raise IsolationTestError('Son onay ilk Windows kullanıcısında yapılmalı.')
    witness = _load(_file(root, WITNESS))
    if set(witness) != {'version','nonce','user_b_marker','challenge_sha256','checked_at','result'} or (
        witness['version'] != VERSION or witness['nonce'] != obj['nonce'] or
        witness['result'] != 'SECOND_USER_DPAPI_DENIED' or
        witness['challenge_sha256'] != _digest(obj) or
        witness['user_b_marker'] == obj['creator_marker'] or
        not isinstance(witness['checked_at'], int) or
        not obj['created_at'] <= witness['checked_at'] <= t
    ):
        raise IsolationTestError('İkinci kullanıcı test kaydı uyuşmuyor.')
    p = protector if protector is not None else WindowsDPAPI(PURPOSE)
    try:
        actual = p.open(ciphertext)
    except Exception as exc:
        raise IsolationTestError('İlk kullanıcı şifreyi yeniden açamadı.') from exc
    if _digest_bytes(actual) != obj['plaintext_sha256']:
        raise IsolationTestError('Test verisi doğrulanamadı.')
    report = {'version': VERSION, 'result': 'PASS_TWO_USERS_SYNTHETIC_DPAPI',
              'steps': ['creator_roundtrip', 'second_sid_distinct',
                        'second_user_denied', 'creator_roundtrip_after_check'],
              'whatsapp_connection': 'NOT_ATTEMPTED',
              'message_delivery': 'NOT_ATTEMPTED',
              'personal_data_access': 'NONE', 'sending_enabled': False,
              'baileys_status': 'DISABLED', 'completed_at': t}
    _write_once(_file(root, FINAL), report)
    return report


def cleanup(folder: str | Path) -> dict:
    root = Path(folder)
    for name in (CHALLENGE, WITNESS, FINAL):
        candidate = _file(root, name)
        if candidate.exists():
            record = _load(candidate)
            if record.get('version') != VERSION:
                raise IsolationTestError('Klasörde beklenmeyen dosya var; otomatik temizlik durdu.')
    for name in (CHALLENGE, WITNESS, FINAL):
        _file(root, name).unlink(missing_ok=True)
    return {'version':VERSION, 'phase':'SYNTHETIC_FILES_REMOVED', 'sending_enabled':False}
