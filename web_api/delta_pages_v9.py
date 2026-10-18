# -*- coding: utf-8 -*-
"""V9 opt-in changed-student transfer (read-only against legacy SQLite).

Every request computes the ordinary V8 snapshot then compares per-student hashes;
this saves BANDWIDTH, not server CPU. The immutable response is page-pinned.
No triggers, migrations, changes to legacy endpoints, or student data writes.
"""
from __future__ import annotations

import hashlib
import json
import math
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

router = APIRouter(prefix='/delta9', tags=['Offline Sync V9'])
PAGE_CHARS = 384 * 1024
SESSION_TTL_SEC = 12 * 60
MAX_PATCH_CHARS = 24 * 1024 * 1024
MAX_LIVE_CHARS = 80 * 1024 * 1024
MAX_SESSIONS = 3
MAX_STUDENTS = 10000

class DeltaStart(BaseModel):
    database_id: str = Field(min_length=1, max_length=128)
    # SHA-256 hashes of locally persisted student+curriculum records.
    manifest: dict[str, str] = Field(default_factory=dict)

@dataclass(frozen=True)
class DeltaSession:
    text: str
    digest: str
    created_at: float

_sessions: dict[str, DeltaSession] = {}
_lock = threading.RLock()


def canonical(value: Any) -> str:
    """Deterministic cross-language JSON: UTF-8, sorted object keys, compact.

    JS numbers cannot distinguish 1 from 1.0. Normalize integral floats;
    remaining float formatting differences conservatively cause a redownload.
    """
    if value is None: return 'null'
    if value is True: return 'true'
    if value is False: return 'false'
    if isinstance(value, str): return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int): return str(value)
    if isinstance(value, float):
        if not math.isfinite(value): raise ValueError('Non-finite snapshot number')
        if value.is_integer() and abs(value) < 1e21: return str(int(value))
        return json.dumps(value, allow_nan=False)
    if isinstance(value, list): return '[' + ','.join(canonical(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{' + ','.join(canonical(str(k))+':'+canonical(value[k]) for k in sorted(value, key=lambda k: str(k))) + '}'
    raise TypeError(f'Unsupported snapshot JSON type: {type(value).__name__}')


def record_hash(student: dict, curriculum: dict) -> str:
    text = canonical({'student': student, 'curriculum': curriculum})
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def build_patch(snapshot: dict, request: DeltaStart) -> dict:
    # The desktop generator sometimes returns integer curriculum keys. JSON
    # transport converts them to strings: normalize BEFORE indexing/digests.
    snap = json.loads(json.dumps(jsonable_encoder(snapshot), ensure_ascii=False,
                                 allow_nan=False, separators=(',', ':')))
    if snap.get('version') != 1 or not isinstance(snap.get('students'), list) or not isinstance(snap.get('curriculum'), dict):
        raise HTTPException(503, 'Masaüstü tam veri görüntüsü geçersiz')
    if request.database_id != snap.get('database_id'):
        raise HTTPException(409, 'Yanlış masaüstü veritabanı: yerel veriler korunuyor')
    if len(request.manifest) > MAX_STUDENTS or len(snap['students']) > MAX_STUDENTS:
        raise HTTPException(413, 'Öğrenci sayısı pilot sınırını aşıyor')
    if any(not key.isdecimal() or len(key) > 20 or not isinstance(digest, str) or
           len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest)
           for key, digest in request.manifest.items()):
        raise HTTPException(422, 'İstemci değişiklik listesi geçersiz')
    order, index, changed, encountered = [], {}, {}, set()
    for s in snap['students']:
        key = str(s.get('id'))
        if not key.isdecimal() or key in encountered or key not in snap['curriculum']:
            raise HTTPException(503, 'Sunucu öğrenci/konu paketi tutarsız')
        encountered.add(key)
        data = snap['curriculum'][key]
        sha = record_hash(s, data)
        order.append(key)
        index[key] = sha
        if request.manifest.get(key) != sha:
            changed[key] = {'student': s, 'curriculum': data}
    if len(snap['curriculum']) != len(order):
        raise HTTPException(503, 'Sunucu öğrenci/konu sayısı farklı')
    removed = sorted(set(request.manifest) - encountered, key=lambda x: int(x))
    return {
        'version': 9, 'snapshot_version': 1, 'database_id': snap['database_id'],
        'generated_at': snap['generated_at'], 'order': order,
        'index': index, 'changed': changed, 'removed': removed,
    }


def _prune(now):
    for token in list(_sessions):
        if now - _sessions[token].created_at > SESSION_TTL_SEC:
            del _sessions[token]


def make_session(snapshot: dict, request: DeltaStart) -> dict:
    patch = build_patch(snapshot, request)
    raw = json.dumps(patch, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
    if len(raw) > MAX_PATCH_CHARS:
        raise HTTPException(413, 'Değişiklik paketi pilot sınırını aşıyor; tam indirmeyi kullanın')
    digest = hashlib.sha256(raw.encode('ascii')).hexdigest()
    token = secrets.token_urlsafe(32)
    with _lock:
        now = time.monotonic()
        _prune(now)
        if len(_sessions) >= MAX_SESSIONS or sum(len(v.text) for v in _sessions.values()) + len(raw) > MAX_LIVE_CHARS:
            raise HTTPException(503, 'İndirme oturumları dolu; tekrar deneyin')
        _sessions[token] = DeltaSession(raw, digest, now)
    return {'version': 9, 'token': token, 'database_id': patch['database_id'],
            'sha256': digest, 'pages': max(1, (len(raw)+PAGE_CHARS-1)//PAGE_CHARS),
            'size': len(raw), 'page_chars': PAGE_CHARS, 'changed_count': len(patch['changed']),
            'removed_count': len(patch['removed']), 'total_students': len(patch['order'])}


@router.post('/start')
def delta_start(body: DeltaStart):
    from web_api.sync_engine import get_sync_snapshot
    # The original generator checks for concurrent writes during its scan.
    return make_session(get_sync_snapshot(student_id=None), body)


@router.get('/{token}/{page}')
def delta_page(token: str, page: int):
    with _lock:
        _prune(time.monotonic())
        session = _sessions.get(token)
        if not session: raise HTTPException(410, 'İndirme oturumu sona erdi; yeniden başlayın')
        count = max(1, (len(session.text)+PAGE_CHARS-1)//PAGE_CHARS)
        if not 0 <= page < count: raise HTTPException(404, 'Geçersiz sayfa')
        chunk = session.text[page*PAGE_CHARS:(page+1)*PAGE_CHARS]
        return {'version': 9, 'page': page, 'pages': count, 'sha256': session.digest, 'chunk': chunk}


@router.post('/{token}/close')
def delta_close(token: str):
    with _lock: _sessions.pop(token, None)
    return {'ok': True}
