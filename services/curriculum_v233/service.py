"""V23.3 — scoped homework ledger with verified topic/student/book identity.

This is intentionally NOT a writer for `odev`, `odev_satir`, or matrix checkbox
rows. Their general-topic numeric IDs cannot represent group/personal topics.
Only explicit teacher actions mutate a *new* table; SELECT calls are read-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional
import sqlite3

from services.curriculum_v231 import TopicIdentity, effective_topics, topic_key


class ScopedAssignmentError(ValueError):
    pass


@dataclass(frozen=True)
class ScopedTopicChoice:
    reference: str
    title: str
    source: str


@dataclass(frozen=True)
class ScopedAssignment:
    id: int
    student_id: int
    lesson: str
    topic_reference: str
    topic_title: str
    source: str
    book: str
    minutes: int
    due_date: str
    status: str


_CREATE = '''
CREATE TABLE IF NOT EXISTS kapsam_odev_v233 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ogrenci_id INTEGER NOT NULL REFERENCES ogrenci(id),
  ders TEXT NOT NULL,
  konu_ref TEXT NOT NULL,
  konu_adi TEXT NOT NULL,
  kapsam TEXT NOT NULL CHECK (kapsam IN ('Grup','Öğrenci')),
  kitap_ad TEXT NOT NULL,
  sure_dk INTEGER NOT NULL CHECK(sure_dk BETWEEN 0 AND 1440),
  bitis_tarihi TEXT NOT NULL,
  durum TEXT NOT NULL DEFAULT 'devam' CHECK(durum IN ('devam','tamam','iptal')),
  olusturma_tarihi TEXT NOT NULL,
  bitis_islem_tarihi TEXT
)'''
_INDEX = '''CREATE UNIQUE INDEX IF NOT EXISTS uq_kapsam_aktif_v233
ON kapsam_odev_v233(ogrenci_id, ders, konu_ref, kitap_ad)
WHERE durum='devam' '''


def _table_exists(con):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kapsam_odev_v233'").fetchone())


def _student_exists(con, student_id):
    if not con.execute('SELECT 1 FROM ogrenci WHERE id=?', (student_id,)).fetchone():
        raise ScopedAssignmentError('Öğrenci bulunamadı. Kayıt yapılmadı.')


def available_scoped_topics(con: sqlite3.Connection, *, student_id: int, lesson: str) -> tuple[ScopedTopicChoice, ...]:
    """Only unambiguous, effective group/personal topics; no old IDs are returned."""
    student_id = int(student_id)
    if student_id <= 0:
        raise ScopedAssignmentError('Öğrenci ID gerekli.')
    snapshot = effective_topics(con, ders=lesson, ogrenci_id=student_id)
    return tuple(ScopedTopicChoice(v.record.identity.key, v.record.name, v.record.identity.scope)
                 for v in snapshot.topics if v.record.identity.scope in ('Grup', 'Öğrenci'))


def available_books(con: sqlite3.Connection, *, student_id: int, lesson: str) -> tuple[str, ...]:
    _student_exists(con, int(student_id))
    return tuple(str(r[0]) for r in con.execute(
        'SELECT kitap_ad FROM ogrenci_kitap WHERE ogrenci_id=? AND ders=? ORDER BY kitap_ad',
        (int(student_id), lesson)))


def list_assignments(con: sqlite3.Connection, *, student_id: int, lesson: Optional[str] = None) -> tuple[ScopedAssignment, ...]:
    """No migration/table creation when merely viewing."""
    student_id = int(student_id)
    _student_exists(con, student_id)
    if not _table_exists(con):
        return ()
    query = ('SELECT id,ogrenci_id,ders,konu_ref,konu_adi,kapsam,kitap_ad,sure_dk,bitis_tarihi,durum '
             'FROM kapsam_odev_v233 WHERE ogrenci_id=?')
    params = [student_id]
    if lesson is not None:
        query += ' AND ders=?'
        params.append(lesson)
    query += ' ORDER BY id DESC'
    return tuple(ScopedAssignment(*r) for r in con.execute(query, params))


def _write_transaction(con, callback):
    """Do not inadvertently commit any pending unrelated GUI transaction."""
    if con.in_transaction:
        raise ScopedAssignmentError('Başka bir kayıt işlemi sürüyor; önce onu tamamlayınız.')
    try:
        con.execute('BEGIN IMMEDIATE')
        value = callback()
        con.commit()
        return value
    except Exception:
        con.rollback()
        raise


def create_assignment(con: sqlite3.Connection, *, student_id: int, lesson: str,
                      topic_reference: str, expected_title: str, book: str,
                      minutes: int, due_date: str) -> int:
    """Teacher-approved scoped assignment; atomic, no historical homework touched."""
    try:
        student_id = int(student_id)
        minutes = int(minutes)
        deadline = date.fromisoformat(str(due_date))
    except (TypeError, ValueError) as exc:
        raise ScopedAssignmentError('Öğrenci, süre veya teslim tarihi geçersiz.') from exc
    if student_id <= 0 or minutes < 0 or minutes > 1440:
        raise ScopedAssignmentError('Öğrenci veya çalışma süresi geçersiz.')
    if deadline < date.today():
        raise ScopedAssignmentError('Teslim tarihi geçmiş olamaz.')
    if not book or not book.strip() or book != book.strip():
        raise ScopedAssignmentError('Öğrenciye atanmış bir kitap seçiniz.')
    if not expected_title or not expected_title.strip():
        raise ScopedAssignmentError('Konu adı boş.')

    def apply():
        _student_exists(con, student_id)
        # Re-read under the SAME write lock: edited curriculum, changed student group
        # and duplicate topics must all fail closed, not reuse a stale preview.
        options = available_scoped_topics(con, student_id=student_id, lesson=lesson)
        matches = [x for x in options if x.reference == topic_reference and x.title == expected_title]
        if len(matches) != 1:
            raise ScopedAssignmentError('Konu veya kapsam değişmiş; listeyi yenileyiniz.')
        if book not in available_books(con, student_id=student_id, lesson=lesson):
            raise ScopedAssignmentError('Kitap bu öğrenciye kayıtlı değil; işlem yapılmadı.')
        con.execute(_CREATE)
        con.execute(_INDEX)
        try:
            cursor = con.execute('''INSERT INTO kapsam_odev_v233
              (ogrenci_id,ders,konu_ref,konu_adi,kapsam,kitap_ad,sure_dk,bitis_tarihi,olusturma_tarihi)
              VALUES (?,?,?,?,?,?,?,?,?)''',
              (student_id, lesson, topic_reference, expected_title, matches[0].source,
               book, minutes, deadline.isoformat(), date.today().isoformat()))
        except sqlite3.IntegrityError as exc:
            raise ScopedAssignmentError('Bu kapsam konusu için aynı kitapta zaten açık bir ödev var.') from exc
        return int(cursor.lastrowid)
    return _write_transaction(con, apply)


def change_status(con: sqlite3.Connection, *, assignment_id: int, student_id: int,
                  new_status: str, expected_status: str = 'devam') -> bool:
    """Explicit completion/cancellation; no deletion or undo of legacy homework."""
    if new_status not in ('tamam', 'iptal') or expected_status != 'devam':
        raise ScopedAssignmentError('Yalnızca açık kapsam ödevi tamamlanabilir veya iptal edilebilir.')
    def apply():
        if not _table_exists(con):
            raise ScopedAssignmentError('Kapsam ödevi bulunamadı.')
        row = con.execute('SELECT ogrenci_id,durum FROM kapsam_odev_v233 WHERE id=?',
                          (int(assignment_id),)).fetchone()
        if not row or int(row[0]) != int(student_id) or row[1] != expected_status:
            raise ScopedAssignmentError('Ödev sahibi veya durumu değişmiş; işlem yapılmadı.')
        changed = con.execute('''UPDATE kapsam_odev_v233 SET durum=?,bitis_islem_tarihi=?
                                 WHERE id=? AND ogrenci_id=? AND durum=?''',
                              (new_status, date.today().isoformat(), int(assignment_id), int(student_id), expected_status))
        if changed.rowcount != 1:
            raise ScopedAssignmentError('Eşzamanlı değişiklik tespit edildi; işlemi yenileyiniz.')
        return True
    return _write_transaction(con, apply)
