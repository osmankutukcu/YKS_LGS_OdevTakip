"""V24.2: conservative local per-student commit classification (read only).

A commit alone cannot reveal its author, student, course or table.  This
reader compares bounded snapshots for a *known selected student* only, on a
read-only SQLite connection after a committed change was detected by V24.1.
No SQLite triggers, writes, student selection, cloud calls or PII persistence.

If a source is too large/invalid to safely fingerprint, conservatively fall
back to refresh (unknown), rather than misreporting the student's data as
unchanged.  No success event is generated on a rolled-back transaction.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import sqlite3

MAX_ROWS_PER_SOURCE = 500
MAX_FIELD_BYTES = 1_000_000
# Explicit allowlist only; selected student filter is ALWAYS parameterized.
_DIRECT = {
    'ogrenci': ('id', 'student'),
    'odev': ('ogrenci_id', 'homework'),
    'odev_kume': ('ogrenci_id', 'homework'),
    'odev_satir': ('ogrenci_id', 'homework'),
    'odev_islem_log': ('ogrenci_id', 'homework'),
    'odev_aktar_log': ('ogrenci_id', 'homework'),
    'odev_takip': ('ogrenci_id', 'topic_map'),
    'koc_konu_takip': ('ogrenci_id', 'coaching'),
    'koc_plan': ('ogrenci_id', 'coaching'),
    'koc_kitaplar': ('ogrenci_id', 'coaching'),
    'ogrenci_anket': ('ogrenci_id', 'survey'),
    'deneme': ('ogrenci_id', 'exam'),
    'deneme_sonuclari': ('ogrenci_id', 'exam'),
    'soru_konu_kanit_v19': ('ogrenci_id', 'exam'),
    'ogrenci_perf_gunluk': ('ogrenci_id', 'performance'),
    'ogrenci_perf_hafta_ders': ('ogrenci_id', 'performance'),
    'ogrenci_performans': ('ogrenci_id', 'performance'),
    'risk_snapshot': ('student_id', 'performance'),
}
_INDIRECT = {
    'koc_hedef': ('koc_plan','plan_id','coaching'),
    'koc_program': ('koc_plan','plan_id','coaching'),
    'deneme_sonuc': ('deneme','deneme_id','exam'),
}

class ScopeNotReliable(RuntimeError):
    """A source is too large or inconsistent to safely suppress a refresh."""

@dataclass(frozen=True)
class StudentDataChange:
    student_id: int
    kinds: tuple[str, ...]
    uncertain: bool = False
    tables: tuple[str, ...] = field(default=(), compare=False)  # V24.3 metadata


def _hash_rows(con, table, where, params):
    # All table names are hardcoded above; no user-controlled SQL identifiers.
    cur = con.execute(f'SELECT * FROM "{table}" WHERE {where} LIMIT ?',
                      (*params, MAX_ROWS_PER_SOURCE + 1))
    rows = cur.fetchall()
    if len(rows) > MAX_ROWS_PER_SOURCE:
        raise ScopeNotReliable(f'{table}: sample would be incomplete')
    # Content hash catches updates, including those that don't update timestamps.
    # Per-row digests are sorted because an implicit SQLite row order is not stable.
    digests=[]
    for row in rows:
        data=repr(tuple(row)).encode('utf-8', errors='replace')
        if len(data) > MAX_FIELD_BYTES:
            raise ScopeNotReliable(f'{table}: oversized row')
        digests.append(hashlib.sha256(data).digest())
    digests.sort()
    return hashlib.sha256(b''.join(digests)).hexdigest()


def student_snapshot(con: sqlite3.Connection, student_id: int):
    """Return source -> digest; never changes the database or returns row data."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Invalid student id')
    existing = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    colmap = {}
    for table in set(_DIRECT) | set(_INDIRECT) | {'koc_plan','deneme'}:
        if table in existing:
            colmap[table]={r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}
    result={}
    for table,(student_col,_) in _DIRECT.items():
        if table not in existing:continue
        if student_col not in colmap.get(table,set()):
            raise ScopeNotReliable(f'{table}: student ownership column missing')
        result[table]=_hash_rows(con,table,f'"{student_col}"=?',(student_id,))
    for table,(parent,foreign,_) in _INDIRECT.items():
        if table not in existing: continue
        if parent not in existing or foreign not in colmap.get(table,set()) or 'id' not in colmap.get(parent,set()) or 'ogrenci_id' not in colmap.get(parent,set()):
            raise ScopeNotReliable(f'{table}: cannot validate parent ownership')
        result[table]=_hash_rows(con,table,
            f'"{foreign}" IN (SELECT "id" FROM "{parent}" WHERE "ogrenci_id"=?)',
            (student_id,))
    return result


class StudentChangeRouter:
    def __init__(self):
        self._baseline = {}

    def baseline(self, con, student_id):
        self._baseline[student_id] = student_snapshot(con,student_id)

    def after_commit(self, con, student_ids):
        """Classify each selected student; unknown scope => safe refresh."""
        output={}
        for sid in set(student_ids):
            if type(sid) is not int or sid <= 0:continue
            try:
                new=student_snapshot(con,sid)
                old=self._baseline.get(sid)
                self._baseline[sid]=new
                if old is None:
                    output[sid]=StudentDataChange(sid,('unknown',),True)
                    continue
                changed={t for t in (set(old)|set(new)) if old.get(t)!=new.get(t)}
                if changed:
                    kinds={_DIRECT[t][1] if t in _DIRECT else _INDIRECT[t][2] for t in changed}
                    output[sid]=StudentDataChange(sid,tuple(sorted(kinds)),False,tuple(sorted(changed)))
            except (sqlite3.Error,ScopeNotReliable,ValueError,MemoryError):
                # Fail open for freshness, not for writing. No personal data logged.
                self._baseline.pop(sid,None)
                output[sid]=StudentDataChange(sid,('unknown',),True)
        return output
