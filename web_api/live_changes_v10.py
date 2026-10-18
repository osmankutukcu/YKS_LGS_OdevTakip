"""V10: opt-in, authenticated, read-only revision heartbeat for *one* desktop DB.

This does not provide Internet cloud synchronization or tenant RBAC. It only
informs already-authenticated clients when the local desktop SQLite changed.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import closing
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from services.live_student_summary_v3 import SQLiteChangeMonitor

router = APIRouter(prefix='/api/sync', tags=['Live Change Hint V10'])

class _Observer:
    def __init__(self):
        self.lock = threading.RLock()
        self.path: Path | None = None
        self.monitor: SQLiteChangeMonitor | None = None
        self.epoch = secrets.token_hex(12)
        self.revision = 0

    def read(self, db_path: Path):
        with self.lock:
            path = db_path.resolve()
            if self.path != path or self.monitor is None:
                if self.monitor:
                    self.monitor.close()
                self.path = path
                self.monitor = SQLiteChangeMonitor(path)
                self.epoch = secrets.token_hex(12)
                self.revision = 0
            try:
                if not path.is_file():
                    raise OSError('Database unavailable')
                changed = self.monitor.poll()
                if changed:
                    self.revision += 1
                # Read-only check of existing database identity, never create it.
                uri = path.as_uri() + '?mode=ro'
                with closing(sqlite3.connect(uri, uri=True, timeout=2)) as con:
                    con.execute('PRAGMA query_only=ON')
                    row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mobile_sync_identity'").fetchone()
                    if not row:
                        raise ValueError('Masaüstü eşitleme kimliği oluşturulmamış')
                    ident = con.execute("SELECT value FROM mobile_sync_identity WHERE key='database_id'").fetchone()
                    if not ident or not isinstance(ident[0], str) or not ident[0]:
                        raise ValueError('Veritabanı kimliği bulunamadı')
                    return {'version': 10, 'database_id': ident[0], 'epoch': self.epoch,
                            'revision': self.revision, 'scope': 'one_desktop_sqlite',
                            'cloud_verified': False}
            except (sqlite3.Error, OSError, ValueError) as exc:
                # A stale watcher must not lead the client to treat old data as current.
                if self.monitor:
                    self.monitor.close()
                self.monitor = None
                raise HTTPException(503, 'Yerel senkronizasyon kaynağı hazır değil') from exc

_observer = _Observer()

@router.get('/live10')
def current_change_hint():
    if os.environ.get('YKS_LIVE_V10_ENABLED') != '1':
        raise HTTPException(503, 'Canlı değişiklik bildirimleri pilotta kapalı')
    import db
    return _observer.read(Path(db.DB_PATH))
