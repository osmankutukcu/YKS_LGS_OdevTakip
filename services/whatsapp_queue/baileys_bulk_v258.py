# -*- coding: utf-8 -*-
"""Opt-in Baileys batch preflight. Independent of legacy Selenium sender."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path

from .queue_v246 import normalize_phone

MAX_RECIPIENTS = 150
MAX_MESSAGE_CHARS = 3000
TRANSPORT_MARKER = 'BAILEYS_V258'


class BatchValidationError(ValueError):
    pass


def masked_phone(number: str) -> str:
    return '***' + str(number)[-4:]


class SuppressionRegistry:
    """Local opt-out register: salted one-way phone fingerprints, no raw phones.

    IMPORTANT: reversible consent records are not manufactured; the institution
    must document actual permission separately. Failure to read => fail closed.
    """
    def __init__(self, filename: str):
        self.path = Path(filename)
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            salt, digests = data['salt'], data['digests']
            if not isinstance(salt, str) or len(salt) != 64 or not isinstance(digests, list):
                raise BatchValidationError('Ret listesi bozuk; gönderim durduruldu')
            bytes.fromhex(salt)
            if any(not isinstance(x, str) or len(x) != 64 for x in digests):
                raise BatchValidationError('Ret listesi bozuk; gönderim durduruldu')
            self.salt = salt
            self.digests = set(digests)
        else:
            self.salt = secrets.token_hex(32)
            self.digests = set()
            self._save()

    def _hash(self, number: str) -> str:
        return hashlib.sha256(bytes.fromhex(self.salt) + number.encode('ascii')).hexdigest()

    def contains(self, number: str) -> bool:
        return self._hash(number) in self.digests

    def add(self, raw_number: str) -> None:
        number = normalize_phone(raw_number)
        if not number:
            raise BatchValidationError('Ret listesine geçerli Türkiye cep numarası giriniz')
        self.digests.add(self._hash(number))
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.wa_rets_', dir=str(self.path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump({'salt': self.salt, 'digests': sorted(self.digests)}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name != 'nt':
                os.chmod(name, 0o600)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def prepare_recipients(raw_jobs: list[dict], country_code: str, suppressed: SuppressionRegistry):
    """Return distinct approved candidates; no DB write and no WhatsApp call.

    Any number linked to multiple student IDs is rejected entirely to prevent
    unintentional disclosure or double sends to shared family phones.
    """
    by_phone: dict[str, dict] = {}
    conflicts: set[str] = set()
    invalid = blank = excluded = duplicate = 0
    for item in raw_jobs:
        raw = str(item.get('recipient', '')).strip()
        phone = normalize_phone(raw, country_code)
        if not phone:
            invalid += 1
            continue
        if suppressed.contains(phone):
            excluded += 1
            continue
        content = str(item.get('message', '')).strip()
        if not content or len(content) > MAX_MESSAGE_CHARS:
            blank += 1
            continue
        if phone in conflicts:
            continue
        prev = by_phone.get(phone)
        if prev:
            if prev['student_id'] != item.get('student_id') or prev['message'] != content:
                conflicts.add(phone)
                del by_phone[phone]
            else:
                duplicate += 1
        else:
            by_phone[phone] = {
                'student_id': item.get('student_id'), 'recipient': phone,
                'message': content, 'country_code': country_code,
            }
    candidates = list(by_phone.values())
    if len(candidates) > MAX_RECIPIENTS:
        raise BatchValidationError(
            f'Bir partide en çok {MAX_RECIPIENTS} farklı telefon olabilir; seçilen {len(candidates)}. '
            'Lütfen öğrenci seçimini daraltın.')
    return candidates, {
        'invalid': invalid, 'oversize_or_empty': blank,
        'excluded': excluded, 'duplicate': duplicate, 'shared_phone': len(conflicts)
    }


def bulk_bridge_dir() -> Path:
    """User-writable Node workspace, works in both source and packaged Windows EXE."""
    base = os.environ.get('LOCALAPPDATA')
    if not base:
        base = str(Path.home() / 'AppData' / 'Local')
    return Path(base) / 'YKS_LGS_HomeworkManager' / 'BaileysNodeV258'


def stage_bulk_bridge() -> Path:
    """Copy release files ONLY after explicit install action; never install npm in EXE folder."""
    import sys
    import shutil
    from .baileys_v257 import bridge_dir
    if sys.platform != 'win32':
        raise BatchValidationError('Baileys Windows pilotu yalnızca Windows içindir')
    source = bridge_dir()
    target = bulk_bridge_dir()
    target.mkdir(parents=True, exist_ok=True)
    names = ('package.json', 'bridge.mjs', 'rules.mjs',
             'bulk_bridge_v258.mjs', 'bulk_rules_v258.mjs',
             'Windows_Hazirla_V258.cmd')
    for name in names:
        source_file = source / name
        if not source_file.is_file():
            raise BatchValidationError('Paket kurulum dosyası eksik: ' + name)
        shutil.copyfile(source_file, target / name)
    tests = target / 'tests'
    tests.mkdir(exist_ok=True)
    for name in ('rules.test.mjs','bulk_rules_v258.test.mjs'):
        file = source / 'tests' / name
        if not file.is_file():
            raise BatchValidationError('Protokol test dosyası eksik: ' + name)
        shutil.copyfile(file, tests / name)
    return target


def bulk_prerequisites():
    from .baileys_v257 import prerequisites
    ok, reason = prerequisites(folder=bulk_bridge_dir())
    if not ok:
        return ok, reason
    if not (bulk_bridge_dir() / 'bulk_bridge_v258.mjs').is_file():
        return False, 'V25.8 toplu bağlantı bileşeni bulunamadı.'
    return True, 'Baileys toplu bağlantısı için bileşenler hazır (Windows eşleştirmesi gereklidir).'


def batch_transport(queue, batch_id: str) -> str:
    with queue.connect() as c:
        row = c.execute('SELECT status FROM batches WHERE id=?', (batch_id,)).fetchone()
    return str(row[0]) if row else ''


def mark_batch(queue, batch_id: str) -> None:
    with queue.connect() as c:
        result = c.execute("UPDATE batches SET status=? WHERE id=? AND status='ACTIVE'",
                           (TRANSPORT_MARKER, batch_id))
        if result.rowcount != 1:
            raise BatchValidationError('Gönderim partisi yönteme bağlanamadı; işleme başlanmadı')


def baileys_queue_path_for(db_path: str, appdata_dir: str) -> str:
    """Isolate DPAPI-protected Baileys queue from legacy plaintext queue."""
    from .queue_v246 import queue_path_for
    path = Path(queue_path_for(db_path, appdata_dir))
    return str(path.with_name(path.name.replace('wa_kuyruk_', 'wa_baileys_v258_', 1)))


def open_baileys_queue(db_path: str, appdata_dir: str):
    from .secure_queue_v250 import ProtectedWhatsAppQueue
    # On Windows, user-scoped DPAPI encrypts recipient, message and detail.
    # Deliberately fails closed on another OS or unavailable DPAPI.
    return ProtectedWhatsAppQueue(baileys_queue_path_for(db_path, appdata_dir))
