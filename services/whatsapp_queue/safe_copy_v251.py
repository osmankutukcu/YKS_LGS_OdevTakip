# -*- coding: utf-8 -*-
"""V25.1: explicit, non-destructive copy from legacy queue to a NEW protected queue.

NO dispatch, no Web/WhatsApp connection, no automatic activation. The original
queue is preserved, and the protected copy is never chosen by the current UI.
The DB may contain sensitive metadata (student_id, source_db, status, timestamps):
only recipient, message and detail are encrypted, exactly as in V25.0.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import uuid

from .dpapi_v250 import WindowsDPAPI, ProtectionError
from .secure_queue_v250 import ProtectedWhatsAppQueue, PREFIX
from .queue_v246 import IN_FLIGHT, QueueBusyError

class MigrationBlocked(RuntimeError):
    pass


@contextmanager
def _exclusive_sidecar_lock(path: Path):
    lock = Path(str(path) + '.v251-migration.lock')
    fd = None
    try:
        fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, str(os.getpid()).encode('ascii'))
        yield
    except FileExistsError as exc:
        raise MigrationBlocked('Başka bir geçiş işlemi var veya eski kilit inceleme gerektiriyor.') from exc
    finally:
        if fd is not None:
            os.close(fd)
            try:
                lock.unlink()
            except FileNotFoundError:
                pass


def _paths(source, destination):
    src, dest = Path(source).expanduser().absolute(), Path(destination).expanduser().absolute()
    if src == dest:
        raise MigrationBlocked('Kaynak ile hedef aynı olamaz.')
    if not src.is_file() or src.is_symlink():
        raise MigrationBlocked('Kaynak bulunamadı veya sembolik bağlantı; işlem yapılmadı.')
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir() or dest.parent.is_symlink():
        raise MigrationBlocked('Hedef mevcut, geçersiz veya hedef klasörü güvenli değil.')
    if src.parent != dest.parent:
        raise MigrationBlocked('Şifreli kopya kaynakla aynı güvenli klasörde oluşturulmalı.')
    return src, dest


def _legacy_snapshot(con):
    """Read under BEGIN IMMEDIATE; no writes to the source.

    Fail-closed if active attempts, partial encryption or inconsistent rows.
    """
    ok = con.execute('PRAGMA quick_check').fetchone()
    if not ok or ok[0] != 'ok':
        raise MigrationBlocked('Kaynak kuyruğun SQLite bütünlük testi başarısız.')
    batch_cols = {r[1] for r in con.execute('PRAGMA table_info(batches)')}
    job_cols = {r[1] for r in con.execute('PRAGMA table_info(jobs)')}
    if not {'id','created','updated','status','source_db'} <= batch_cols or not {
        'id','batch_id','student_id','recipient','message','state',
        'attempt_token','created','updated','detail'} <= job_cols:
        raise MigrationBlocked('Kuyruk şeması beklenenden farklı.')
    batches = con.execute('SELECT id,created,updated,status,source_db FROM batches ORDER BY rowid').fetchall()
    jobs = con.execute('''SELECT id,batch_id,student_id,recipient,message,state,
            attempt_token,created,updated,detail FROM jobs ORDER BY rowid''').fetchall()
    ids = {b['id'] for b in batches}
    if len(ids) != len(batches):
        raise MigrationBlocked('Tekrarlanan parti kaydı bulundu.')
    for j in jobs:
        if j['batch_id'] not in ids:
            raise MigrationBlocked('Partisi bulunmayan mesaj var.')
        if j['state'] == IN_FLIGHT:
            raise MigrationBlocked('Gönderim denemesi sürüyor veya yarım kaldı; inceleme gerekli.')
        if any(not isinstance(j[f], str) or j[f].startswith(PREFIX) for f in ('recipient','message','detail')):
            raise MigrationBlocked('Eski kuyruk kısmen şifreli veya veri biçimi belirsiz.')
    return batches, jobs


def assess_legacy(source):
    """Read-only status; returns counts, never message content or phone numbers."""
    src = Path(source).expanduser().absolute()
    if not src.is_file() or src.is_symlink():
        raise MigrationBlocked('Kuyruk dosyası bulunamadı.')
    try:
        uri = src.as_uri() + '?mode=ro'
        with sqlite3.connect(uri, uri=True, timeout=5) as con:
            con.row_factory = sqlite3.Row
            batches, jobs = _legacy_snapshot(con)
        return {'batches':len(batches),'jobs':len(jobs), 'states': dict(Counter(j['state'] for j in jobs)),
                'safe_to_copy':True}
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as exc:
        raise MigrationBlocked('Kuyruk okunamadı veya yapısı doğrulanamadı.') from exc


def create_encrypted_copy(source, destination, *, explicit_consent=False, protector=None):
    """Clone to NEW encrypted queue, preserving original untouched.

    Existing application will keep using its legacy queue. This function never
    auto-activates the new queue, requeues messages, nor sends messages.
    WindowsDPAPI is required unless an explicit test protector is provided.
    """
    if not explicit_consent:
        raise PermissionError('Öğretmenin açık onayı olmadan kopyalama yapılmaz.')
    src, dest = _paths(source, destination)
    protector = protector if protector is not None else WindowsDPAPI('wa-queue-v250')
    temporary = dest.with_name('.' + dest.name + '.pending-' + uuid.uuid4().hex + '.sqlite3')
    try:
        with _exclusive_sidecar_lock(src), _exclusive_sidecar_lock(dest):
            if dest.exists() or dest.is_symlink():
                raise MigrationBlocked('Hedef artık mevcut; üzerine yazılmadı.')
            # Lock the source against concurrent SQLite writers during snapshot.
            # This lock does not alter any row. A legacy worker process that
            # tries to write will wait until the snapshot completes.
            with sqlite3.connect(str(src), timeout=15, isolation_level=None) as origin:
                origin.row_factory = sqlite3.Row
                origin.execute('BEGIN IMMEDIATE')
                try:
                    batches, jobs = _legacy_snapshot(origin)
                    protected = ProtectedWhatsAppQueue(str(temporary), protector=protector)
                    # Encrypt in memory before the SQLite insertion. The new
                    # file never receives plaintext recipient/message/detail.
                    encrypted_jobs = []
                    for j in jobs:
                        encrypted_jobs.append((j['id'],j['batch_id'],j['student_id'],
                            protected._enc(j['recipient']),protected._enc(j['message']),
                            j['state'],j['attempt_token'],j['created'],j['updated'],
                            protected._enc(j['detail'])))
                    with protected.connect() as out:
                        out.execute('BEGIN IMMEDIATE')
                        out.executemany('''INSERT INTO batches
                            (id,created,updated,status,source_db) VALUES (?,?,?,?,?)''',
                            [tuple(b) for b in batches])
                        out.executemany('''INSERT INTO jobs
                            (id,batch_id,student_id,recipient,message,state,attempt_token,created,updated,detail)
                            VALUES (?,?,?,?,?,?,?,?,?,?)''', encrypted_jobs)
                    protected.assert_encrypted()
                    # Validate every ciphertext against the current user's protector.
                    with protected.connect() as verify:
                        copied = verify.execute('''SELECT id,batch_id,student_id,recipient,message,state,
                            attempt_token,created,updated,detail FROM jobs ORDER BY rowid''').fetchall()
                        copied_batches = verify.execute('SELECT COUNT(*) FROM batches').fetchone()[0]
                        integrity = verify.execute('PRAGMA quick_check').fetchone()[0]
                    if len(copied) != len(jobs) or copied_batches != len(batches) or integrity != 'ok':
                        raise MigrationBlocked('Kopya doğrulama başarısız.')
                    for original, clone in zip(jobs, copied):
                        for field in ('recipient','message','detail'):
                            if protected._dec(clone[field]) != original[field]:
                                raise MigrationBlocked('Şifreli kopya kaynakla uyuşmuyor.')
                        for field in ('id','batch_id','student_id','state','attempt_token','created','updated'):
                            if clone[field] != original[field]:
                                raise MigrationBlocked('Kopyada kayıt bilgileri uyuşmuyor.')
                    os.chmod(temporary, 0o600)
                    # hard link is no-overwrite atomic publish: no accidental
                    # replacement if another process created destination.
                    os.link(temporary, dest)
                    temporary.unlink()
                finally:
                    origin.rollback()
        return {'batches':len(batches),'jobs':len(jobs),
                'protected_copy_created':True, 'legacy_unchanged':True, 'sending_enabled':False}
    except (sqlite3.DatabaseError, sqlite3.OperationalError) as exc:
        raise MigrationBlocked('Geçiş sırasında SQLite işlemi güvenli biçimde durduruldu.') from exc
    finally:
        # An interrupted process might leave a pending file; production must
        # never treat pending files as dispatchable queues.
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
