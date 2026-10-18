# -*- coding: utf-8 -*-
"""V8 optional immutable, paged snapshot sessions.

The desktop SQLite tables and existing /api/sync/snapshot endpoint are untouched.
Sessions exist in process memory only, expire automatically, and keep a single
consistent snapshot across pages. This is NOT a differential sync feed.
Requires a single API worker or shared session storage for multi-worker deployments.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix='/paged', tags=['Offline Sync V8'])
PAGE_CHARS = 384 * 1024
SESSION_TTL_SEC = 12 * 60
MAX_SNAPSHOT_CHARS = 24 * 1024 * 1024
MAX_LIVE_BYTES = 80 * 1024 * 1024
MAX_SESSIONS = 3

@dataclass(frozen=True)
class SnapshotSession:
    text: str
    database_id: str
    digest: str
    created_monotonic: float

_sessions: dict[str, SnapshotSession] = {}
_mutex = threading.RLock()


def _prune(now: float) -> None:
    for token in list(_sessions):
        if now - _sessions[token].created_monotonic > SESSION_TTL_SEC:
            del _sessions[token]


def _require_session(token: str) -> SnapshotSession:
    with _mutex:
        _prune(time.monotonic())
        session = _sessions.get(token)
        if not session:
            raise HTTPException(status_code=410, detail='Parçalı veri oturumu sona erdi; yeniden başlayın.')
        return session


def _serialize(snapshot: dict) -> str:
    # ASCII JSON means exact cross-platform page joins without splitting UTF-8.
    raw = json.dumps(jsonable_encoder(snapshot), ensure_ascii=True, separators=(',', ':'), allow_nan=False)
    if len(raw) > MAX_SNAPSHOT_CHARS:
        raise HTTPException(413, detail='Çevrimdışı paket bellek sınırını aştı; küçültülmeli.')
    return raw


def make_session(snapshot: dict) -> dict:
    if snapshot.get('version') != 1 or not snapshot.get('database_id') or not isinstance(snapshot.get('students'), list):
        raise HTTPException(503, detail='Geçersiz masaüstü verisi; indirme reddedildi.')
    raw = _serialize(snapshot)
    token = secrets.token_urlsafe(32)
    sha = hashlib.sha256(raw.encode('ascii')).hexdigest()
    with _mutex:
        now = time.monotonic()
        _prune(now)
        active_bytes = sum(len(x.text) for x in _sessions.values())
        if len(_sessions) >= MAX_SESSIONS or active_bytes + len(raw) > MAX_LIVE_BYTES:
            raise HTTPException(503, detail='Diğer indirmeler sürüyor; biraz sonra yeniden deneyin.')
        _sessions[token] = SnapshotSession(raw, snapshot['database_id'], sha, now)
    return {'version': 8, 'token': token, 'database_id': snapshot['database_id'],
            'sha256': sha, 'pages': max(1, (len(raw) + PAGE_CHARS - 1) // PAGE_CHARS),
            'size': len(raw), 'page_chars': PAGE_CHARS,
            'expires_in_seconds': SESSION_TTL_SEC}


@router.post('/start')
def paged_start():
    # Lazily import: the existing generator remains the source of truth.
    from web_api.sync_engine import get_sync_snapshot
    snapshot = get_sync_snapshot(student_id=None)
    return make_session(snapshot)


@router.get('/{token}/{page}')
def paged_get(token: str, page: int):
    session = _require_session(token)
    pages = max(1, (len(session.text) + PAGE_CHARS - 1) // PAGE_CHARS)
    if page < 0 or page >= pages:
        raise HTTPException(404, 'Geçersiz sayfa numarası')
    start = page * PAGE_CHARS
    return {'version': 8, 'page': page, 'pages': pages,
            'sha256': session.digest,
            'chunk': session.text[start:start + PAGE_CHARS]}


@router.post('/{token}/close')
def paged_close(token: str):
    with _mutex:
        _sessions.pop(token, None)
    return {'ok': True}
