"""Read-only consolidation of existing modules, keyed exclusively by ogrenci.id.

No inserts/updates/migrations. Reuses V14 and V15 evidence definitions so the
Coaching Plan does not show a competing set of performance calculations.
"""
from __future__ import annotations
from datetime import date
import sqlite3
from .models import StudentOverview
from services.performance_evidence_v14 import compute_evidence
from services.performance_coaching_v15 import _load_exam_rows, _exam_summary


def _has(con: sqlite3.Connection, name: str, columns: set[str]) -> bool:
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone():
        return False
    return columns.issubset({r[1] for r in con.execute(f'PRAGMA table_info("{name}")')})


def read_student_overview(con: sqlite3.Connection, student_id: int, *, as_of: date | None = None) -> StudentOverview:
    """Read one student. Never substitute the first list row for a missing ID."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli bir öğrenci kimliği gerekli.')
    today = as_of or date.today()
    row = con.execute('SELECT id, ad, soyad, aktif FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if row is None or row[3] == 0:
        raise ValueError('Öğrenci bulunamadı veya aktif değil.')
    name = (str(row[1] or '') + ' ' + str(row[2] or '')).strip()
    notes: list[str] = []

    # V14 single source of truth: do not count odev plus odev_satir twice.
    evidence = compute_evidence(con, reference_day=today)
    student = next((s for s in evidence.students if s.student_id == student_id), None)
    if student is None:
        raise ValueError('Öğrencinin performans kaydı okunamadı.')
    hw = (f'{student.last30.completed}/{student.last30.total} teslim dönemi ödevi'
          if student.last30.total else 'Son 30 günde tarihli ödev verisi yok')
    if student.uncertain_count:
        notes.append('İki ödev kaynağı aynı kümede; ikincil kayıt ayrıca sayılmadı, eşdeğerlik doğrulanmadı.')
    if student.undated_count:
        notes.append('Teslim tarihi belirsiz ödevler başarı oranından çıkarıldı.')
    if student.last30.total and student.last30.total < 5:
        notes.append('Ödev örneklemi az; yüzdeler dikkatle yorumlanmalı.')

    # V15: no across-exam-type or unknown-denominator comparisons.
    observations, source_flags, _ = _load_exam_rows(con, today, {student_id})
    exam, strength, _, explanation = _exam_summary(
        observations.get(student_id, []), source_flags.get(student_id, set()))

    plan_label = 'Bu hafta koçluk planı kayıtlı değil'
    plan_id = None
    goals = program_entries = 0
    if _has(con, 'koc_plan', {'id','ogrenci_id','baslangic_tarihi','bitis_tarihi'}):
        plan = con.execute('''SELECT id FROM koc_plan WHERE ogrenci_id=?
            AND baslangic_tarihi<=? AND bitis_tarihi>=?
            ORDER BY baslangic_tarihi DESC,id DESC LIMIT 1''',
            (student_id, today.isoformat(), today.isoformat())).fetchone()
        if plan:
            plan_id = int(plan[0]); plan_label = 'Bu haftanın koçluk planı mevcut'
    if plan_id is not None:
        if _has(con,'koc_hedef',{'plan_id'}):
            goals = int(con.execute('SELECT COUNT(*) FROM koc_hedef WHERE plan_id=?', (plan_id,)).fetchone()[0])
        if _has(con,'koc_program',{'plan_id'}):
            program_entries = int(con.execute('SELECT COUNT(*) FROM koc_program WHERE plan_id=?', (plan_id,)).fetchone()[0])

    # Coach-topic records are planning/teacher markings, not measured mastery.
    total = marked = 0
    if _has(con, 'koc_konu_takip', {'ogrenci_id','durum'}):
        total, marked = con.execute('''SELECT COUNT(*),COALESCE(SUM(CASE WHEN durum IN (2,4) THEN 1 ELSE 0 END),0)
                FROM koc_konu_takip WHERE ogrenci_id=?''', (student_id,)).fetchone()
    return StudentOverview(student_id,name,hw,student.last30.total,student.overdue_all,
                           student.uncertain_count,exam,strength,explanation,plan_label,
                           goals,program_entries,int(total),int(marked),tuple(notes))
