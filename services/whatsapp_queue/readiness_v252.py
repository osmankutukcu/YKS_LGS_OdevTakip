# -*- coding: utf-8 -*-
"""V25.2 offline Windows security checks (no WhatsApp network, no real contacts).

These tests never enable headless/WhatsApp sending, migrate user records or
probe an actual WhatsApp session. Diagnostics contain no secrets or paths.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import platform
import sqlite3
import sys

from .dpapi_v250 import WindowsDPAPI, ProtectionError
from .queue_v246 import SafeWhatsAppQueue, UNKNOWN
from .secure_queue_v250 import ProtectedWhatsAppQueue
from .safe_copy_v251 import assess_legacy, create_encrypted_copy
from .secure_vault_v250 import SecureLocalVault

SENTINEL = b'V252_SYNTHETIC_ONLY_NOT_A_REAL_WHATSAPP_SECRET'
MESSAGE = 'V252_TEST_MESSAGE_NO_REAL_STUDENT_DATA'

class ReadinessFailure(RuntimeError):
    pass


def _require(condition: bool, description: str):
    if not condition:
        raise ReadinessFailure(description)


def _offline_smoke(protector_factory):
    """Test using fake provider only when explicitly injected by unit tests.

    Normal caller must use WindowsDPAPI, not a fallback fake cipher.
    """
    checks = []
    with TemporaryDirectory(prefix='v252_offline_synthetic_') as temp:
        folder = Path(temp)
        protector = protector_factory('wa-queue-v250')
        vault_protector = protector_factory('wa-auth-v250')
        _require(protector.open(protector.seal(SENTINEL)) == SENTINEL,
                 'DPAPI round-trip başarısız')
        checks.append('dpapi_roundtrip')

        # A different purpose cannot decrypt a credential. This does not
        # prove isolation between Windows user profiles (requires 2 accounts).
        mismatched = protector_factory('v252-other-purpose')
        try:
            mismatched.open(protector.seal(SENTINEL))
        except Exception:
            checks.append('purpose_isolation')
        else:
            raise ReadinessFailure('Amaç sınırı hatası: farklı amaçla çözme mümkün')

        vdir = folder/'vault'
        vault = SecureLocalVault(str(vdir), protector=vault_protector)
        vault.put('v252_synthetic', SENTINEL)
        restarted = SecureLocalVault(str(vdir), protector=protector_factory('wa-auth-v250'))
        _require(restarted.get('v252_synthetic') == SENTINEL,
                 'Kasa tekrar açıldığında okunamadı')
        _require(SENTINEL not in (vdir/'v252_synthetic.dpapi').read_bytes(),
                 'Oturum kasası açık metin içeriyor')
        checks.append('vault_restart_and_no_plaintext')

        src = folder/'legacy.sqlite3'
        dst = folder/'protected.sqlite3'
        old = SafeWhatsAppQueue(str(src))
        batch = old.create_batch(str(folder/'synthetic.db'), [
            {'student_id':101, 'recipient':'05321234567', 'message':MESSAGE},
            {'student_id':102, 'recipient':'invalid-number', 'message':MESSAGE+'-invalid'},
        ])
        before = src.read_bytes()
        result = create_encrypted_copy(src, dst, explicit_consent=True, protector=protector)
        _require(result['jobs'] == 2 and not result['sending_enabled'],
                 'Kopyanın sayısı veya güvenli durumu hatalı')
        _require(src.read_bytes() == before, 'Kaynak kuyruk değiştirildi')
        checks.append('legacy_copy_source_unchanged')

        secure = ProtectedWhatsAppQueue(str(dst), protector=protector_factory('wa-queue-v250'))
        _require(secure.rows(batch) == old.rows(batch), 'Şifreli kopya aynı kayıtları vermiyor')
        raw = dst.read_bytes()
        _require(MESSAGE.encode('utf-8') not in raw and b'905321234567' not in raw,
                 'Şifreli dosyada mesaj veya telefon açık metin')
        checks.append('encrypted_queue_restart_and_no_plaintext')

        # A claimed message can never be automatically tried again after
        # crash recovery. Its outcome must stay unknown.
        job = secure.claim_next(batch)
        _require(job is not None and job['student_id'] == 101,
                 'Kuyruk geçerli alıcıyı seçemedi')
        _require(secure.recover_interrupted(batch) == 1,
                 'Yarım kalan deneme bulunamadı')
        _require(secure.claim_next(batch) is None, 'Bilinmeyen mesaj yeniden işleme alındı')
        _require(any(row['state'] == UNKNOWN for row in secure.rows(batch)),
                 'Gönderim belirsiz durumu kayboldu')
        checks.append('crash_recovery_no_duplicate_send')

        _require(vault.delete('v252_synthetic'), 'Sentetik kasa kaydı temizlenemedi')
    return checks


def windows_offline_readiness(*, protector_factory=None, platform_name=None) -> dict:
    """Returns privacy-safe report; nothing is sent, no personal data read.

    `protector_factory` is for test injection only. When absent, real Windows
    DPAPI is mandatory. No encryption downgrade is possible in production.
    """
    is_windows = (os.name == 'nt') if platform_name is None else (platform_name == 'nt')
    report = {
        'version': 'V25.2', 'test_data': 'synthetic_only',
        'whatsapp_connection': 'NOT_ATTEMPTED', 'message_delivery': 'NOT_ATTEMPTED',
        'personal_data_access': 'NONE', 'headless_baileys': 'DISABLED',
        'result': 'BLOCKED', 'passed_checks': [], 'requires_real_windows': True,
    }
    if not is_windows and protector_factory is None:
        report['result'] = 'NOT_RUN_WINDOWS_REQUIRED'
        return report
    test_double_supplied = protector_factory is not None
    if protector_factory is None:
        protector_factory = lambda purpose: WindowsDPAPI(purpose)
    try:
        report['passed_checks'] = _offline_smoke(protector_factory)
        report['result'] = ('PASS_TEST_DOUBLE_ONLY' if test_double_supplied else 'PASS_WINDOWS_SYNTHETIC_TEST')
    except Exception:
        # Do not expose paths, secrets, Windows API internals or raw exceptions.
        report['result'] = 'FAIL_CLOSED'
        report['passed_checks'] = []
    return report


def inspect_legacy_counts(path: str) -> dict:
    """Only explicitly provided source; returns counts, never numbers/text/paths."""
    try:
        summary = assess_legacy(path)
        return {'result':'SAFE_TO_COPY_FOR_REVIEW', 'batches':summary['batches'],
                'jobs':summary['jobs'], 'states':summary['states'],
                'will_migrate':False, 'will_send':False}
    except Exception:
        return {'result':'REQUIRES_MANUAL_REVIEW', 'will_migrate':False, 'will_send':False}
