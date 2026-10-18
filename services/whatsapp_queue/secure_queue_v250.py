# -*- coding: utf-8 -*-
"""V25.0 optional encrypted queue. Not enabled in existing WhatsApp UI.

Install adds code but DOES NOT alter V24.9 send methods or legacy queues.
Callers must explicitly migrate legacy queues with a backup/privacy plan and
validate on Windows. This is an opt-in pilot, not a hidden auto-migration.
"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable

from .dpapi_v250 import WindowsDPAPI, ProtectionError
from .queue_v246 import (SafeWhatsAppQueue, QueueBusyError, PENDING, IN_FLIGHT,
    UNKNOWN, INVALID, FAILED, UI_UNVERIFIED, normalize_phone)

PREFIX = 'dpapi:v250:'

class LegacyQueueNeedsReview(RuntimeError):
    pass


class ProtectedWhatsAppQueue(SafeWhatsAppQueue):
    """Uses existing V24.6 tables, encrypts recipient/message/detail at rest.

    A caller that wants to use a previous plaintext queue must explicitly run
    migrate_legacy_to_encrypted on a *copy* first. No implicit migration.
    """
    def __init__(self, path: str, protector=None, *, allow_legacy_review=False):
        self.protector = protector if protector is not None else WindowsDPAPI('wa-queue-v250')
        super().__init__(path)
        if not allow_legacy_review:
            self.assert_encrypted()

    def _enc(self, text: str) -> str:
        raw = str(text).encode('utf-8')
        return PREFIX + base64.b64encode(self.protector.seal(raw)).decode('ascii')

    def _dec(self, value: str) -> str:
        if not isinstance(value, str) or not value.startswith(PREFIX):
            raise LegacyQueueNeedsReview('Eski açık metin kuyruğu var; otomatik gönderim durduruldu.')
        try:
            decoded = base64.b64decode(value[len(PREFIX):], validate=True)
            return self.protector.open(decoded).decode('utf-8')
        except LegacyQueueNeedsReview:
            raise
        except Exception as exc:
            raise ProtectionError('WhatsApp kuyruğu açılamıyor; gönderim durduruldu.') from exc

    def assert_encrypted(self):
        with self.connect() as con:
            old = con.execute('''SELECT 1 FROM jobs WHERE recipient NOT LIKE ?
                OR message NOT LIKE ? OR detail NOT LIKE ? LIMIT 1''',
                (PREFIX + '%',) * 3).fetchone()
        if old:
            raise LegacyQueueNeedsReview(
                'Kuyrukta eski açık metin kayıtları bulundu. Bu sürüm otomatik dönüşüm yapmaz.')

    def create_batch(self, db_path: str, jobs: Iterable[dict]) -> str:
        self.assert_encrypted()
        items = list(jobs)
        if not items:
            raise ValueError('Kuyrukta alıcı yok')
        batch = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        # Encrypt ALL entries in memory before opening transaction. If DPAPI
        # fails, no plaintext row or partially inserted batch is persisted.
        prepared = []
        seen = set()
        for entry in items:
            sid = entry.get('student_id')
            raw = str(entry.get('recipient', ''))
            msg = str(entry.get('message', ''))
            phone = normalize_phone(raw, str(entry.get('country_code', '90')))
            finger = (sid, phone or raw, msg)
            if finger in seen:
                continue
            seen.add(finger)
            state = PENDING if phone and msg.strip() else INVALID if not phone else FAILED
            detail = '' if state == PENDING else 'Numara biçimi geçersiz' if state == INVALID else 'Mesaj boş'
            prepared.append((uuid.uuid4().hex, batch, sid, self._enc(phone or raw),
                self._enc(msg), state, None, now, now, self._enc(detail)))
        with self.connect() as con:
            con.execute('INSERT INTO batches VALUES(?,?,?,?,?)',
                (batch, now, now, 'ACTIVE', os.path.realpath(db_path)))
            con.executemany('''INSERT INTO jobs
                (id,batch_id,student_id,recipient,message,state,attempt_token,created,updated,detail)
                VALUES (?,?,?,?,?,?,?,?,?,?)''', prepared)
        return batch

    def _plain_job(self, row):
        value = dict(row)
        for k in ('recipient','message','detail'):
            value[k] = self._dec(value[k])
        return value

    def claim_next(self, batch: str):
        self.assert_encrypted()
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            if con.execute('SELECT 1 FROM jobs WHERE batch_id=? AND state=? LIMIT 1',
                           (batch, IN_FLIGHT)).fetchone():
                raise QueueBusyError('Aynı kuyruk başka bir işlem tarafından kullanılıyor')
            row = con.execute('SELECT * FROM jobs WHERE batch_id=? AND state=? ORDER BY rowid LIMIT 1',
                              (batch, PENDING)).fetchone()
            if row is None:
                return None
            job = self._plain_job(row)  # decryption BEFORE marking in-flight
            token = uuid.uuid4().hex
            cur = con.execute('UPDATE jobs SET state=?, attempt_token=?,updated=? WHERE id=? AND state=?',
                              (IN_FLIGHT, token, datetime.now(timezone.utc).isoformat(timespec='seconds'),
                               job['id'], PENDING))
            if cur.rowcount != 1:
                raise QueueBusyError('Gönderim işi eş zamanlı değişti')
            job['attempt_token'] = token
            return job

    def rows(self, batch: str):
        self.assert_encrypted()
        with self.connect() as con:
            return [self._plain_job(r) for r in con.execute(
                'SELECT * FROM jobs WHERE batch_id=? ORDER BY rowid', (batch,))]

    def finish(self, job_id: str, token: str, result: str, detail: str = ''):
        if result not in (UI_UNVERIFIED, UNKNOWN, INVALID, FAILED):
            raise ValueError('Tanımsız gönderim sonucu')
        encrypted_detail = self._enc((detail or '')[:300])
        with self.connect() as con:
            cur = con.execute('''UPDATE jobs SET state=?,detail=?,updated=?
                WHERE id=? AND state=? AND attempt_token=?''',
                (result, encrypted_detail, datetime.now(timezone.utc).isoformat(timespec='seconds'),
                 job_id, IN_FLIGHT, token))
            if cur.rowcount != 1:
                raise QueueBusyError('Gönderim işi eş zamanlı değişti')

    def recover_interrupted(self, batch: str) -> int:
        with self.connect() as con:
            cur = con.execute('''UPDATE jobs SET state=?,detail=?,updated=?
                WHERE batch_id=? AND state=?''',
                (UNKNOWN, self._enc('Program kapandı; gönderim durumu doğrulanamıyor'),
                 datetime.now(timezone.utc).isoformat(timespec='seconds'), batch, IN_FLIGHT))
            return cur.rowcount

    def migrate_legacy_to_encrypted(self, *, explicit_consent=False) -> int:
        """Optional one-way transition; requires explicit consent and worker lock.

        Historical plaintext bytes may persist in filesystem snapshots, old
        backups and SQLite journal/slack. Do not claim full historical erasure.
        In-flight messages are never migrated automatically.
        """
        if not explicit_consent:
            raise PermissionError('Açık onay olmadan eski kuyruk dönüştürülemez.')
        fd = self.acquire_lock()
        try:
            with self.connect() as con:
                con.execute('BEGIN IMMEDIATE')
                if con.execute('SELECT 1 FROM jobs WHERE state=? LIMIT 1', (IN_FLIGHT,)).fetchone():
                    raise QueueBusyError('Gönderim sürerken dönüşüm yapılamaz.')
                original = con.execute('SELECT id,recipient,message,detail FROM jobs').fetchall()
                encrypted = []
                for r in original:
                    out = []
                    for field in ('recipient','message','detail'):
                        value = str(r[field])
                        
                        if value.startswith(PREFIX):
                            self._dec(value)  # Reject another user's encrypted records.
                            out.append(value)
                        else:
                            out.append(self._enc(value))
                    encrypted.append((out[0], out[1], out[2], r['id']))
                con.executemany('UPDATE jobs SET recipient=?,message=?,detail=? WHERE id=?', encrypted)
            self.assert_encrypted()
            return len(original)
        finally:
            self.release_lock(fd)
