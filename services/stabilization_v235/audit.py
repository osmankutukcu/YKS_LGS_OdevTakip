"""V23.5: read-only checks across primary homework, scoped homework and student identity.

This module deliberately does not import db.py or a Qt module.  Opening the
production database, running migrations, changing checkboxes, or repairing
records are NOT an audit operation. Its results are operational diagnostics,
not a student's academic performance score.
"""
from __future__ import annotations
from dataclasses import dataclass
import sqlite3
from typing import Optional

from services.performance_evidence_v14 import DONE, OPEN, TRANSFERRED

_SCOPED = frozenset(('devam', 'tamam', 'iptal'))

@dataclass(frozen=True)
class StudentCounters:
    student_id: int
    legacy_open: int
    legacy_completed: int
    legacy_unknown: int
    legacy_excluded: int
    scoped_open: int
    scoped_completed: int
    scoped_cancelled: int

    @property
    def legacy_total(self) -> int:
        return self.legacy_open + self.legacy_completed + self.legacy_unknown + self.legacy_excluded

    @property
    def scoped_total(self) -> int:
        return self.scoped_open + self.scoped_completed + self.scoped_cancelled

@dataclass(frozen=True)
class AcceptanceReport:
    database_check: str
    active_students: int
    inactive_students: int
    legacy_rows: int
    scoped_rows: int
    orphaned_detail_links: int
    wrong_student_detail_links: int
    missing_legacy_students: int
    missing_scoped_students: int
    invalid_scoped_statuses: int
    student_counters: tuple[StudentCounters, ...]
    warnings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.database_check == 'ok' and not any((
            self.orphaned_detail_links, self.wrong_student_detail_links,
            self.missing_legacy_students, self.missing_scoped_students,
            self.invalid_scoped_statuses,
        ))


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in con.execute(f'PRAGMA table_info("{table}")')}


def _has(con: sqlite3.Connection, table: str) -> bool:
    return bool(con.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',
                            ('table', table)).fetchone())


def _count(con: sqlite3.Connection, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def audit_connection(con: sqlite3.Connection, *, include_students: bool = False) -> AcceptanceReport:
    """Inspect without schema changes or writes; never fix a problem automatically.

    ``include_students=False`` avoids including student IDs in reports and
    commands by default. Statuses from the two ledgers are counted separately.
    Callers should open a SQLite mode=ro connection with PRAGMA query_only=ON.
    """
    required = {'ogrenci': {'id'}, 'odev': {'id','ogrenci_id','durum'}}
    for table, cols in required.items():
        if not _has(con, table) or not cols.issubset(_columns(con, table)):
            raise ValueError(f'Zorunlu tablo/kolon eksik: {table}. Kayıtlar değiştirilmedi.')
    if _has(con, 'kapsam_odev_v233') and not {'id','ogrenci_id','durum'}.issubset(_columns(con, 'kapsam_odev_v233')):
        raise ValueError('Kapsam ödevleri şeması uyumsuz. İnceleme durduruldu.')

    db_ok = str(con.execute('PRAGMA quick_check').fetchone()[0])
    students = {int(r[0]): bool(r[1]) for r in con.execute(
        'SELECT id,' + ('COALESCE(aktif,1)' if 'aktif' in _columns(con,'ogrenci') else '1') + ' FROM ogrenci')}
    counters = {sid: [0]*7 for sid,active in students.items() if active}
    missing_main = missing_scoped = invalid_scoped = 0
    excluded_cols = [col for col in ('silindi','aktarildi') if col in _columns(con,'odev')]
    fields = 'ogrenci_id,durum' + ''.join(','+col for col in excluded_cols)
    total_main = 0
    for row in con.execute('SELECT '+fields+' FROM odev'):
        total_main += 1
        sid = int(row[0]) if row[0] is not None else -1
        if sid not in students:
            missing_main += 1
        if sid not in counters:
            continue
        status = str(row[1] or '').strip().lower()
        if any(bool(value) for value in row[2:]) or status in TRANSFERRED:
            counters[sid][3] += 1
        elif status in DONE:
            counters[sid][1] += 1
        elif status in OPEN:
            counters[sid][0] += 1
        else:
            counters[sid][2] += 1
    total_scoped = 0
    if _has(con,'kapsam_odev_v233'):
        for sid_raw, status in con.execute('SELECT ogrenci_id,durum FROM kapsam_odev_v233'):
            total_scoped += 1
            sid = int(sid_raw) if sid_raw is not None else -1
            if sid not in students:
                missing_scoped += 1
            if status not in _SCOPED:
                invalid_scoped += 1
                continue
            if sid in counters:
                counters[sid][{'devam':4,'tamam':5,'iptal':6}[status]] += 1

    orphans = mismatches = 0
    if _has(con,'odev_satir') and {'odev_id','ogrenci_id'}.issubset(_columns(con,'odev_satir')):
        orphans = _count(con, '''SELECT COUNT(*) FROM odev_satir s
            LEFT JOIN odev o ON o.id=s.odev_id
            WHERE s.odev_id IS NOT NULL AND o.id IS NULL''')
        mismatches = _count(con, '''SELECT COUNT(*) FROM odev_satir s
            JOIN odev o ON o.id=s.odev_id
            WHERE s.ogrenci_id IS NOT NULL AND o.ogrenci_id != s.ogrenci_id''')

    warnings = []
    for number, msg in ((orphans,'Kopuk ödev_satir → odev bağlantısı'),
                        (mismatches,'Öğrencisi farklı ödev_satir bağlantısı'),
                        (missing_main,'Öğrencisi bulunamayan ana ödev'),
                        (missing_scoped,'Öğrencisi bulunamayan kapsam ödevi'),
                        (invalid_scoped,'Geçersiz kapsam ödevi durumu')):
        if number:
            warnings.append(f'{msg}: {number}; otomatik düzeltme yapılmadı.')
    if db_ok != 'ok':
        warnings.append('SQLite quick_check başarısız; veritabanını kullanmadan önce yedek incelemesi gerekli.')
    if not _has(con,'kapsam_odev_v233'):
        warnings.append('Kapsam ödevi tablosu henüz yok; bu, eski kurulumlarda normaldir.')
    if any(values[2] for values in counters.values()):
        warnings.append('Bilinmeyen ana ödev durumları mevcut; toplamlar akademik başarı göstergesi değildir.')
    items = tuple(StudentCounters(sid, *counters[sid]) for sid in sorted(counters)) if include_students else ()
    return AcceptanceReport(db_ok,sum(students.values()),len(students)-sum(students.values()),
                            total_main,total_scoped,orphans,mismatches,missing_main,
                            missing_scoped,invalid_scoped,items,tuple(warnings))
