# -*- coding: utf-8 -*-
"""Additive, namespaced sync transaction helpers; never alters desktop tables.

IMPORTANT: receipt and business write MUST share one SQLite transaction.
See tests/test_safe_sync.py before integrating into a production database.
"""
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta

from fastapi import HTTPException

def ensure_desktop_schema(conn):
    """Fail before any sync table is created on a wrong/empty DB file."""
    required = {
        'ogrenci': {'id', 'aktif'},
        'odev_kume': {'id', 'ogrenci_id', 'verilis_tarihi', 'bitis_tarihi'},
        'odev': {'id', 'kume_id', 'ogrenci_id', 'ders', 'konu_ad', 'kitap_ad', 'durum'},
        'odev_satir': {'id', 'odev_id', 'ogrenci_id', 'kume_id', 'durum'},
        'kitap': {'ders', 'ad'},
    }
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required.keys() <= existing:
        raise ValueError('Masaüstü veritabanı tabloları eksik; yanlış veritabanı')
    for table, names in required.items():
        columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        if not names <= columns:
            raise ValueError('Masaüstü veritabanı şeması uyumsuz')


IDENTITY_TABLE_SQL = """CREATE TABLE IF NOT EXISTS mobile_sync_identity (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)"""


def database_identity(conn):
    """Stable UUID stored alongside desktop records, not tied to URL/IP/port."""
    conn.execute(IDENTITY_TABLE_SQL)
    row = conn.execute("SELECT value FROM mobile_sync_identity WHERE key='database_id'").fetchone()
    if row:
        return row[0]
    token = str(uuid.uuid4())
    conn.execute("INSERT OR IGNORE INTO mobile_sync_identity(key,value) VALUES('database_id',?)", (token,))
    return conn.execute("SELECT value FROM mobile_sync_identity WHERE key='database_id'").fetchone()[0]


RECEIPT_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS mobile_sync_receipts (
  mutation_id TEXT PRIMARY KEY,
  payload_digest TEXT NOT NULL,
  applied_at TEXT NOT NULL
)'''


def digest_item(item):
    body = {'type': item.type, 'payload': item.payload, 'created_at': item.created_at}
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _as_int(value):
    try:
        val = int(value)
    except (ValueError, TypeError):
        raise ValueError('Geçersiz sayısal kimlik') from None
    if val <= 0:
        raise ValueError('Kimlik sıfırdan büyük olmalı')
    return val


def _date(value, given_date=None):
    if not value:
        # Seven offline days must not silently move the promised deadline.
        anchor = date.fromisoformat(given_date) if given_date else date.today()
        return (anchor + timedelta(days=7)).isoformat()
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('Teslim tarihi YYYY-MM-DD olmalı')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError('Geçersiz teslim tarihi') from None


def _created_date(item):
    """Store date from when teacher assigned work offline, not from sync date.

    Strict bounds reduce clock errors (but not malicious changes to device clock).
    """
    local_value = item.payload.get('assigned_local_date')
    if local_value is not None:
        try:
            value = date.fromisoformat(local_value)
            if value.isoformat() == local_value and date.today() - timedelta(days=90) <= value <= date.today() + timedelta(days=2):
                return value.isoformat()
        except (ValueError, TypeError):
            pass
        raise ValueError('Yerel ödev tarihi geçersiz')
    if not item.created_at:
        return date.today().isoformat()
    try:
        stamp = datetime.fromisoformat(item.created_at.replace('Z', '+00:00'))
        value = stamp.date()
        if date.today() - timedelta(days=90) <= value <= date.today() + timedelta(days=2):
            return value.isoformat()
    except (ValueError, TypeError, AttributeError):
        pass
    raise ValueError('Cihaz tarihi geçersiz; tarih düzeltilmeli')


def _create_homework(con, item):
    """Transaction-scoped equivalent of web_api.main.create_homework.

    Pilot integration MUST compare resulting kume/odev/odev_satir rows against
    the exact desktop version and the existing /api/homework endpoint.
    """
    from web_api.main import GRUP_DERSLER
    p = item.payload
    student_id = _as_int(p.get('student_id'))
    lesson = p.get('lesson')
    book = p.get('book')
    topics = p.get('topics')
    if not isinstance(lesson, str) or lesson not in {l for group in GRUP_DERSLER.values() for l in group}:
        raise ValueError('Geçersiz ders')
    if not isinstance(book, str) or not book.strip() or len(book) > 250:
        raise ValueError('Geçersiz kitap')
    if not isinstance(topics, list) or not 1 <= len(topics) <= 100:
        raise ValueError('1-100 konu gerekli')
    topic_list = []
    seen = set()
    for topic in topics:
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 300:
            raise ValueError('Geçersiz konu')
        t = topic.strip()
        if t not in seen:
            topic_list.append(t)
            seen.add(t)
    verilis = _created_date(item)
    bitis = _date(p.get('due_date'), verilis)
    cur = con.cursor()
    if not cur.execute('SELECT 1 FROM ogrenci WHERE id=?', (student_id,)).fetchone():
        raise ValueError('Öğrenci bulunamadı')
    cur.execute('INSERT INTO odev_kume(ogrenci_id,verilis_tarihi,bitis_tarihi) VALUES(?,?,?)',
                (student_id, verilis, bitis))
    kume_id = cur.lastrowid
    try:
        cur.execute('INSERT OR IGNORE INTO kitap(ders,ad) VALUES(?,?)', (lesson, book.strip()))
    except Exception:
        # Existing web API intentionally treats optional global book registry as best-effort.
        pass
    for i, topic in enumerate(topic_list):
        topic_id = -(i + 1)
        try:
            row = cur.execute(f'SELECT id FROM "{lesson}" WHERE konu=?', (topic,)).fetchone()
            if row:
                topic_id = row[0]
        except Exception:
            pass
        cur.execute('''INSERT INTO odev
            (kume_id,ogrenci_id,ders,konu_id,konu_ad,kitap_ad,saat_dk,aciklama,durum,verilis_tarihi)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (kume_id, student_id, lesson, topic_id, topic, book, 0, '', 'devam', verilis))
        header_id = cur.lastrowid
        cur.execute('''INSERT INTO odev_satir
            (odev_id,kume_id,ogrenci_id,ders,konu,kitap,durum,tarih)
            VALUES(?,?,?,?,?,?,?,?)''',
            (header_id, kume_id, student_id, lesson, topic, book, 'devam', verilis))
    return {'kume_id': kume_id, 'topics': len(topic_list)}


def status_fingerprint(header_id, raw_status, completed_at):
    """Cheap optimistic concurrency token; cannot detect same-value ABA updates."""
    from utils.homework_status import is_completed
    canonical = ['tamam' if is_completed(raw_status) else 'devam', completed_at or '']
    raw = json.dumps([int(header_id), *canonical], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _update_header_status(con, payload):
    from web_api.homework_store import set_headers_done
    ids = payload.get('homework_ids')
    status = payload.get('status')
    expected = payload.get('expected_status')
    expected_by_id = payload.get('expected_statuses')
    fingerprints = payload.get('expected_fingerprints')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 500 or status not in ('tamam', 'devam'):
        raise ValueError('Geçersiz ödev durumu isteği')
    if expected is not None and expected not in ('tamam', 'yapildi', 'devam'):
        raise ValueError('Geçersiz önceki durum')
    ids = list(dict.fromkeys(_as_int(n) for n in ids))
    markers = ','.join('?' for _ in ids)
    existing = con.execute(f'SELECT id,durum,tamamlanma_tarihi FROM odev WHERE id IN ({markers})', ids).fetchall()
    if len(existing) != len(ids):
        raise ValueError('Ödev kayıtlarından biri silinmiş veya bulunamadı')
    from utils.homework_status import is_completed as completed
    if expected_by_id is not None:
        if not isinstance(expected_by_id, dict) or any(str(x) not in expected_by_id for x in ids):
            raise ValueError('Önceki durum bilgileri eksik')
        for header_id, server_status, _ in existing:
            previous = expected_by_id.get(str(header_id))
            if previous not in ('tamam', 'devam'):
                raise ValueError('Önceki ödev durumu geçersiz')
            if completed(server_status) != completed(previous):
                raise SyncConflict('Ödev durumu başka bir cihazda değişmiş; kullanıcı incelemesi gerekli')
    if fingerprints is not None:
        if not isinstance(fingerprints, dict):
            raise ValueError('Durum doğrulama bilgisi geçersiz')
        for header_id, server_status, completed_at in existing:
            token = fingerprints.get(str(header_id))
            if token is not None and token != status_fingerprint(header_id, server_status, completed_at):
                raise SyncConflict('Ödev eşitlemeden sonra değiştirilmiş; kullanıcı incelemesi gerekli')
    if expected is not None:
        expected_done = completed(expected)
        desired_done = completed(status)
        for _, server_status in existing:
            if completed(server_status) not in (expected_done, desired_done):
                raise SyncConflict('Sunucudaki ödev durumu başka bir işlemle değişmiş')
            # With binary status, expected != desired always; while same as desired
            # can be acknowledged safely, same as expected can be changed.
    changed = set_headers_done(con, ids, status == 'tamam')
    if changed != len(ids):
        raise ValueError('Ödev durumlarının tamamı değiştirilemedi')
    return {'updated': changed}


class SyncConflict(Exception):
    pass


def apply_command(con, item):
    if item.type == 'ASSIGN_HOMEWORK':
        return _create_homework(con, item)
    if item.type == 'SET_HOMEWORK_STATUS':
        return _update_header_status(con, item.payload)
    if item.type == 'COMPLETE_HOMEWORK':
        from web_api.homework_store import set_single_line_done
        line_id = _as_int(item.payload.get('line_id'))
        changed = set_single_line_done(con, line_id, True)
        if changed != 1:
            raise ValueError('Ödev alt satırı bulunamadı')
        return {'updated': changed}
    raise ValueError('Bilinmeyen çevrimdışı işlem türü')


def apply_once(conn, item, expected_database_id=None):
    """Exactly-once DB *effect* by SQLite transaction + persistent receipt.

    Caller must own this connection; on error this function rolls back.
    Concurrent clients are serialized by SQLite BEGIN IMMEDIATE.
    """
    if len(item.id) < 8 or len(item.id) > 128:
        raise ValueError('İşlem kimliği geçersiz')
    digest = digest_item(item)
    try:
        conn.execute('BEGIN IMMEDIATE')
        ensure_desktop_schema(conn)
        dbid = database_identity(conn)
        if expected_database_id is not None and expected_database_id != dbid:
            raise SyncConflict('Yanlış masaüstü/veritabanı: işlem aktarımı durduruldu')
        conn.execute(RECEIPT_TABLE_SQL)
        row = conn.execute('SELECT payload_digest FROM mobile_sync_receipts WHERE mutation_id=?',
                           (item.id,)).fetchone()
        if row:
            if row[0] != digest:
                raise SyncConflict('Aynı işlem kimliği farklı içerikle yeniden gönderildi')
            conn.commit()
            return {'id': item.id, 'status': 'already_applied'}
        detail = apply_command(conn, item)
        conn.execute('INSERT INTO mobile_sync_receipts(mutation_id,payload_digest,applied_at) VALUES(?,?,?)',
                     (item.id, digest, datetime.now().isoformat()))
        conn.commit()
        return {'id': item.id, 'status': 'applied', 'detail': detail}
    except Exception:
        conn.rollback()
        raise
