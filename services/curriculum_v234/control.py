"""Safely display and control V23.3 scoped assignments *without* touching legacy homework.

The legacy ``odev`` / ``odev_satir`` model stores global topic IDs. Scoped
assignments live in ``kapsam_odev_v233`` and must remain a separate accounting
category. All read functions are SELECT-only; no schema migration on viewing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import sqlite3

from services.curriculum_v233 import list_assignments, ScopedAssignment


class ScopedControlError(ValueError):
    """Failed closed: no mutation was committed."""


@dataclass(frozen=True)
class ScopedControlOverview:
    student_id: int
    assignments: tuple[ScopedAssignment, ...]
    open_count: int
    completed_count: int
    cancelled_count: int


def get_overview(con: sqlite3.Connection, *, student_id: int) -> ScopedControlOverview:
    """Read a single student's scoped tasks; never includes legacy tasks."""
    student_id = int(student_id)
    if student_id <= 0:
        raise ScopedControlError('Geçerli bir öğrenci seçiniz.')
    assignments = list_assignments(con, student_id=student_id)
    return ScopedControlOverview(
        student_id, assignments,
        sum(r.status == 'devam' for r in assignments),
        sum(r.status == 'tamam' for r in assignments),
        sum(r.status == 'iptal' for r in assignments),
    )


_HISTORY_SCHEMA = '''
CREATE TABLE IF NOT EXISTS kapsam_odev_kontrol_log_v234 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kapsam_odev_id INTEGER NOT NULL,
    ogrenci_id INTEGER NOT NULL,
    onceki_durum TEXT NOT NULL,
    yeni_durum TEXT NOT NULL,
    onceki_bitis_islem_tarihi TEXT,
    yeni_bitis_islem_tarihi TEXT,
    islem_zamani TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    kaynak TEXT NOT NULL DEFAULT 'OdevKontrolV234'
)'''


def status_history(con: sqlite3.Connection, *, student_id: int, assignment_id: int) -> tuple[tuple, ...]:
    """Read audit history without creating tables or exposing another student."""
    student_id, assignment_id = int(student_id), int(assignment_id)
    if student_id <= 0 or assignment_id <= 0:
        raise ScopedControlError('Öğrenci veya ödev kimliği geçersiz.')
    if not con.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',
                       ('table', 'kapsam_odev_kontrol_log_v234')).fetchone():
        return ()
    return tuple(con.execute('''SELECT onceki_durum, yeni_durum, islem_zamani, kaynak
      FROM kapsam_odev_kontrol_log_v234
      WHERE ogrenci_id=? AND kapsam_odev_id=? ORDER BY id''',
      (student_id, assignment_id)).fetchall())


def set_scoped_control_status(con: sqlite3.Connection, *, student_id: int,
                              assignment_id: int, expected_status: str,
                              new_status: str) -> bool:
    """Explicit transition with student binding, optimistic lock, audit, rollback.

    Allowed: devam->tamam/iptal, tamam/iptal->devam. Undo is not allowed if
    another active task already owns the same student/course/topic/book key.
    Both the update and audit insert are one SQLite transaction.
    """
    student_id, assignment_id = int(student_id), int(assignment_id)
    if student_id <= 0 or assignment_id <= 0:
        raise ScopedControlError('Öğrenci veya ödev kimliği geçersiz.')
    transitions = {'devam': {'tamam', 'iptal'}, 'tamam': {'devam'}, 'iptal': {'devam'}}
    if new_status not in transitions.get(expected_status, set()):
        raise ScopedControlError('Geçersiz durum geçişi; işlemi yenileyiniz.')
    if con.in_transaction:
        raise ScopedControlError('Başka kayıt işlemi sürerken kapsam ödevi değiştirilmez.')

    try:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('''SELECT ogrenci_id,durum,bitis_islem_tarihi
            FROM kapsam_odev_v233 WHERE id=?''', (assignment_id,)).fetchone()
        if not row or int(row[0]) != student_id or row[1] != expected_status:
            raise ScopedControlError('Ödev başka öğrenciye ait ya da durumu değişmiş; yenileyiniz.')

        # SQLite checks the original scoped-task UNIQUE partial index here;
        # a different open task for the same topic/book must block undo.
        end_date = None if new_status == 'devam' else date.today().isoformat()
        con.execute(_HISTORY_SCHEMA)
        result = con.execute('''UPDATE kapsam_odev_v233
          SET durum=?, bitis_islem_tarihi=?
          WHERE id=? AND ogrenci_id=? AND durum=?''',
          (new_status, end_date, assignment_id, student_id, expected_status))
        if result.rowcount != 1:
            raise ScopedControlError('Ödev eşzamanlı değişti; işlem iptal edildi.')
        con.execute('''INSERT INTO kapsam_odev_kontrol_log_v234
          (kapsam_odev_id,ogrenci_id,onceki_durum,yeni_durum,
           onceki_bitis_islem_tarihi,yeni_bitis_islem_tarihi)
          VALUES (?,?,?,?,?,?)''',
          (assignment_id, student_id, expected_status, new_status, row[2], end_date))
        con.commit()
        return True
    except sqlite3.IntegrityError as exc:
        con.rollback()
        raise ScopedControlError('Aynı konu/kitap için başka açık ödev var veya bütünlük kuralı ihlal edildi.') from exc
    except Exception:
        con.rollback()
        raise
