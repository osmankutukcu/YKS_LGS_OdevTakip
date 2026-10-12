"""V21: Existing Student360 + homework-control summary, read only.

Never creates tables or mutates grades, assignments, marks, or coaching records.
Control counters use only the primary ``odev`` table used by OdevKontrolDialog.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import sqlite3
from services.student360_v16.reader import read_student_overview
from services.student360_v16.models import StudentOverview
from services.performance_evidence_v14 import DONE, OPEN, TRANSFERRED


@dataclass(frozen=True)
class ControlCounts:
    completed: int
    open: int
    unknown: int
    excluded: int


@dataclass(frozen=True)
class ControlPreview:
    lesson: str
    topic: str
    status: str


@dataclass(frozen=True)
class WorkspaceReport:
    student: StudentOverview
    control: ControlCounts
    notes: tuple[str, ...]
    recent_control: tuple[ControlPreview, ...] = ()


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in con.execute('PRAGMA table_info("' + table + '")')}


def read_control_counts(con: sqlite3.Connection, student_id: int) -> ControlCounts:
    """Current primary control states; not a historic deadline performance metric."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Öğrenci kimliği geçersiz.')
    columns = _columns(con, 'odev')
    if not {'ogrenci_id', 'durum'}.issubset(columns):
        raise ValueError('Ödev Kontrol kaynağının gerekli alanları bulunamadı.')
    optional = [c for c in ('silindi', 'aktarildi') if c in columns]
    sql = 'SELECT durum' + ''.join(', ' + c for c in optional) + ' FROM odev WHERE ogrenci_id=?'
    completed = opened = unknown = excluded = 0
    for row in con.execute(sql, (student_id,)):
        status = str(row[0] or '').strip().lower()
        if any(bool(value) for value in row[1:]) or status in TRANSFERRED:
            excluded += 1
        elif status in DONE:
            completed += 1
        elif status in OPEN:
            opened += 1
        else:
            unknown += 1
    return ControlCounts(completed, opened, unknown, excluded)


def read_recent_control(con: sqlite3.Connection, student_id: int, limit: int = 6) -> tuple[ControlPreview, ...]:
    """Short, non-editable list from the same primary control source."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Öğrenci kimliği geçersiz.')
    columns = _columns(con, 'odev')
    if not {'id', 'ogrenci_id', 'durum'}.issubset(columns):
        raise ValueError('Ödev Kontrol kaynağı beklenen kimlik alanlarını içermiyor.')
    fields = ['durum']
    fields += [col for col in ('ders', 'konu_ad', 'silindi', 'aktarildi') if col in columns]
    query = ('SELECT ' + ','.join(fields) + ' FROM odev WHERE ogrenci_id=? '
             'ORDER BY id DESC LIMIT 70')
    output = []
    for raw in con.execute(query, (student_id,)):
        values = dict(zip(fields, raw))
        status = str(values['durum'] or '').strip().lower()
        if values.get('silindi') or values.get('aktarildi') or status in TRANSFERRED:
            continue
        label = 'Bitti' if status in DONE else ('Açık' if status in OPEN else 'Belirsiz')
        lesson = str(values.get('ders') or 'Ders belirtilmemiş').strip()[:70]
        topic = str(values.get('konu_ad') or 'Konu belirtilmemiş').strip()[:95]
        output.append(ControlPreview(lesson, topic, label))
        if len(output) >= limit:
            break
    return tuple(output)


def read_workspace_report(con: sqlite3.Connection, student_id: int, *, as_of: date | None = None) -> WorkspaceReport:
    """Same student must own both the Student360 and control report."""
    student = read_student_overview(con, student_id, as_of=as_of)
    if student.student_id != student_id:
        raise ValueError('Öğrenci kimliği uyuşmuyor.')
    control = read_control_counts(con, student_id)
    notes = ['Kontrol durumu ana ödev kayıtlarının güncel durumudur; akademik başarı değildir.']
    if control.unknown:
        notes.append(f'{control.unknown} ödevde bilinmeyen durum kodu var; Kontrol ekranında incelenmeli.')
    if student.homework_uncertainty:
        notes.append('İki ödev kaynağı arasında eşleştirme belirsizliği var; otomatik düzeltme yapılmadı.')
    return WorkspaceReport(student, control, tuple(notes), read_recent_control(con, student_id))
