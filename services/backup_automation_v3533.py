# -*- coding: utf-8 -*-
"""V3.5.33 - opt-in daily verified local SQLite backup coordinator.

No Qt imports, no application data mutations, no delete/prune, no restore.
The existing ZIP backup (including planner files) is a separate facility.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib
import os
import re
import time

from services.verified_recovery_v3532 import create_verified_backup, preview_restore, due_for_backup

BACKUP_NAME = re.compile(r'^YKS_Kurtarilabilir_\d{8}T\d{6}_\d{6}Z\.db\.gz$')
MAX_CANDIDATES = 10
LOCK_NAME = '.yks_v3533_daily.lock'


def inspect_last_verified(directory: str | Path, *, now_utc: datetime | None = None,
                          scope_token: str | None = None) -> dict:
    """Only backups from this service family are candidates. No files are modified."""
    folder = Path(directory).expanduser()
    now = now_utc or datetime.now(timezone.utc)
    if not folder.is_dir() or folder.is_symlink():
        return {'status': 'DESTINATION_NOT_READY'}
    try:
        items = sorted((p for p in folder.iterdir() if p.is_file() and not p.is_symlink()
                        and BACKUP_NAME.fullmatch(p.name)), key=lambda p: p.name, reverse=True)
        invalid = 0
        for path in items[:MAX_CANDIDATES]:
            manifest_path = Path(str(path) + '.manifest.json')
            if not manifest_path.is_file() or manifest_path.is_symlink():
                invalid += 1
                continue
            try:
                meta = json.loads(manifest_path.read_text(encoding='utf-8'))
                if scope_token is not None and meta.get('backup_scope') != scope_token:
                    continue
                timestamp = datetime.fromisoformat(meta['created_at_utc'])
                if timestamp.tzinfo is None or timestamp > now:
                    invalid += 1
                    continue
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                invalid += 1
                continue
            if preview_restore(path, require_manifest=True).get('status') == 'REHEARSAL_PASSED':
                return {'status':'VERIFIED_BACKUP_FOUND', 'created_at_utc':timestamp,
                        'invalid_recent_candidates':invalid, 'verified_backup':path}
            invalid += 1
        return {'status':'NO_VERIFIED_BACKUP', 'invalid_recent_candidates':invalid}
    except OSError:
        return {'status': 'DESTINATION_UNREADABLE'}


def run_due_backup(source: str | Path, destination: str | Path, *, enabled: bool = False,
                   now_utc: datetime | None = None, interval_hours: int = 24) -> dict:
    """Create a genuine, verified SQLite image at most once per requested interval.

    Conservative concurrency: if another run owns the lock, defer. Stale locks
    are NEVER deleted automatically. No application settings changed.
    """
    if not enabled:
        return {'status':'DISABLED', 'data_modified':False}
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return {'status':'INVALID_CLOCK', 'data_modified':False}
    src = Path(source).expanduser()
    dst = Path(destination).expanduser()
    if (src.is_symlink() or dst.is_symlink() or not src.is_file() or not dst.is_dir()
            or not os.access(dst, os.W_OK)):
        return {'status':'LOCATION_NOT_READY', 'data_modified':False}
    # Fail closed: prevent background backups to a DB filename treated as a directory.
    lock = dst / LOCK_NAME
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        return {'status':'BUSY_OR_STALE_LOCK', 'data_modified':False}
    except OSError:
        return {'status':'LOCK_UNAVAILABLE', 'data_modified':False}
    try:
        # Paths are hashed only for same-destination identity separation.
        # No real paths, student IDs, or student content appear in manifests.
        scope = hashlib.sha256(os.path.normcase(str(src.resolve())).encode('utf-8')).hexdigest()[:32]
        previous = inspect_last_verified(dst, now_utc=now, scope_token=scope)
        if previous['status'] == 'DESTINATION_UNREADABLE':
            return {'status':'INSPECTION_FAILED', 'data_modified':False}
        if previous['status'] == 'VERIFIED_BACKUP_FOUND' and not due_for_backup(
                previous['created_at_utc'], now_utc=now, minimum_hours=max(1,interval_hours)):
            return {'status':'ALREADY_CURRENT', 'data_modified':False,
                    'invalid_recent_candidates':previous.get('invalid_recent_candidates',0)}
        result = create_verified_backup(src, dst, compress=True, scope_token=scope)
        if result.get('status') != 'BACKUP_CREATED_AND_REHEARSED':
            return {'status':'BACKUP_FAILED', 'data_modified':False,
                    'reason':result.get('reason','UNVERIFIED_FAILURE')}
        return {'status':'BACKUP_CREATED_AND_VERIFIED', 'data_modified':False,
                'invalid_recent_candidates':previous.get('invalid_recent_candidates',0)}
    except Exception:
        return {'status':'BACKUP_FAILED', 'data_modified':False, 'reason':'UNEXPECTED_BACKUP_EXCEPTION'}
    finally:
        try:
            lock.rmdir()  # Only remove our empty lock; never arbitrary directory contents.
        except OSError:
            pass
