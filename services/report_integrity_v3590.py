# -*- coding: utf-8 -*-
"""V3.5.90: independent, read-only report evidence integrity checks.

Does NOT replace legacy totals, issue coaching risk labels, alter student records,
read private contacts, use a network connection, or infer exams from homework.
Conflicting ownership and unlinked mixed rows are warnings, never a deletion rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import sqlite3

from services.canonical_homework_evidence_v3535 import DONE, OPEN, INACTIVE, scan_canonical_homework
from services.performance_evidence_v14 import _date
from services.report_diagnostics_v3589 import inspect_report_sources

MAX_STUDENT_ROWS = 5000
MAX_COHORT_ROWS = 15000


@dataclass(frozen=True)
class StudentIntegrity:
    state: str                 # checked | review | limited | unavailable
    examined: int
    owner_conflicts: int
    ambiguous_groups: int
    linked_parents: int
    undated: int
    unknown_status: int
    reasons: tuple[str, ...]


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f'PRAGMA table_info({table})')}


def audit_student_integrity(con: sqlite3.Connection, student_id: int, *,
                            max_rows: int = MAX_STUDENT_ROWS) -> StudentIntegrity:
    """Check only records that may belong to this EXACT student.

    A child linked to a parent/group owned by this student is included even if
    its own owner points to another student, so contamination is not invisible.
    No names, exam records or student IDs are returned in reasons.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçersiz öğrenci kimliği.')
    if type(max_rows) is not int or max_rows < 1:
        raise ValueError('Kayıt sınırı geçersiz.')
    mandatory = {
        'ogrenci': {'id', 'aktif'},
        'odev_kume': {'id', 'ogrenci_id', 'bitis_tarihi'},
        'odev': {'id', 'ogrenci_id', 'kume_id', 'durum'},
        'odev_satir': {'id', 'ogrenci_id', 'kume_id', 'durum'},
    }
    for table, required in mandatory.items():
        if not required <= _cols(con, table):
            return StudentIntegrity('unavailable', 0, 0, 0, 0, 0, 0,
                                    ('Ödev kayıtlarının sahiplik kontrolü için gerekli alanlar bulunamadı.',))
    row = con.execute('SELECT aktif FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if row is None or row[0] != 1:
        raise ValueError('Öğrenci bulunamadı veya aktif değil.')

    child_has_parent = 'odev_id' in _cols(con, 'odev_satir')
    # Bounded records per student, including other-owner rows attributed to
    # this student's group or explicit parent. Never fetch whole cohorts here.
    def fetch(table):
        child = table == 'odev_satir'
        parent_join = (' LEFT JOIN odev p ON p.id=r.odev_id '
                       'LEFT JOIN odev_kume pg ON pg.id=p.kume_id ') if child and child_has_parent else ''
        parent_id = 'r.odev_id' if child and child_has_parent else 'NULL'
        parent_owner = 'p.ogrenci_id' if child and child_has_parent else 'NULL'
        parent_group = 'p.kume_id' if child and child_has_parent else 'NULL'
        parent_group_owner = 'pg.ogrenci_id' if child and child_has_parent else 'NULL'
        parent_due = 'pg.bitis_tarihi' if child and child_has_parent else 'NULL'
        cond = '(r.ogrenci_id=? OR g.ogrenci_id=?'
        if child and child_has_parent:
            cond += ' OR p.ogrenci_id=?'
        cond += ')'
        optional = _cols(con, table)
        deleted = 'r.silindi' if 'silindi' in optional else 'NULL'
        moved = 'r.aktarildi' if 'aktarildi' in optional else 'NULL'
        sql = (f'SELECT r.id,r.ogrenci_id,r.kume_id,g.ogrenci_id,g.bitis_tarihi,'
               f'{parent_id},{parent_owner},{parent_group},{parent_group_owner},'
               f'{parent_due},r.durum,{deleted},{moved} '
               f'FROM {table} r LEFT JOIN odev_kume g ON g.id=r.kume_id '
               f'{parent_join} WHERE {cond} LIMIT ?')
        args = (student_id, student_id) + ((student_id,) if child and child_has_parent else ()) + (max_rows + 1,)
        return con.execute(sql, args).fetchall()

    parents = fetch('odev')
    children = fetch('odev_satir')
    if len(parents) + len(children) > max_rows:
        return StudentIntegrity('limited', 0, 0, 0, 0, 0, 0,
                                ('Öğrencinin kayıtları hızlı denetim sınırını aştı; tam sahiplik kontrolü yapılmadı.',))

    conflicts = unknown = undated = 0
    parent_groups = set()
    unlinked_groups = set()
    linked_ids = set()
    for table, rows in (('odev', parents), ('odev_satir', children)):
        for rid, sid, gid, gowner, due_raw, parent_id, powner, pgroup, pgowner, pdue, status, deleted, moved in rows:
            if sid != student_id or (gid is not None and gowner != sid):
                conflicts += 1
                continue
            if table == 'odev_satir' and parent_id is not None:
                if (powner != sid or (gid is not None and pgroup != gid)
                        or (pgroup is not None and pgowner != sid)):
                    conflicts += 1
                    continue
                linked_ids.add(parent_id)
            if table == 'odev':
                if gid is not None:
                    parent_groups.add(gid)
            elif parent_id is None and gid is not None:
                unlinked_groups.add(gid)
            status_text = str(status or 'devam').strip().lower()
            if deleted in (1, '1', True) or moved in (1, '1', True) or status_text in INACTIVE:
                continue
            if status_text not in DONE and status_text not in OPEN:
                unknown += 1
            elif _date(due_raw if gid is not None else pdue) is None:
                # Verified explicit parent link may supply a verified group date;
                # independent rows never inherit another student's deadline.
                undated += 1
    ambiguous = len(parent_groups & unlinked_groups)
    reasons = []
    if conflicts:
        reasons.append(f'{conflicts} kaydın öğrenci/küme/üst görev bağlantısı doğrulanamadı; bu kayıtları öğretmen incelemeli.')
    if ambiguous:
        reasons.append(f'{ambiguous} kümede bağımsız satırlarla ana görev birlikte bulunuyor; aynı görev oldukları varsayılamaz.')
    if unknown:
        reasons.append(f'{unknown} kayıtta durum alanı tanınmıyor; tamamlanmış sayılmamalı.')
    if undated:
        reasons.append(f'{undated} kayıtta geçerli teslim tarihi doğrulanamadı; gecikme yorumu sınırlı.')
    if linked_ids:
        reasons.append(f'{len(linked_ids)} ana görevle açık bağlantılı alt satırlar bulundu; yalnızca bu bağlantılar kesin eşleştirme kanıtıdır.')
    status = ('review' if conflicts or ambiguous else
              'limited' if unknown or undated else 'checked')
    if not reasons:
        reasons.append('İncelenen yerel kayıtlarda sahiplik veya kaynak çakışması saptanmadı; sınav başarısı ölçülmedi.')
    return StudentIntegrity(status, len(parents)+len(children), conflicts, ambiguous,
                            len(linked_ids), undated, unknown, tuple(reasons))


def audit_cohort_report_sources(con: sqlite3.Connection, *,
                                reference_day: date | None = None,
                                max_rows: int = MAX_COHORT_ROWS) -> dict:
    """Anonymous cohort diagnostic: existing counters + canonical evidence if safe.

    Doesn't publish student names, IDs, phone numbers or priority cards.
    Does not assert equality between different date windows / granularity.
    """
    # First check bounded COUNTs. In large installations the old INTERSECT
    # candidate query can be expensive; skip it rather than blocking the UI.
    if type(max_rows) is not int or max_rows < 1:
        raise ValueError('Hızlı denetim sınırı geçersiz.')
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = tuple(t for t in ('odev', 'odev_satir') if t not in tables)
    main = con.execute('SELECT COUNT(*) FROM odev').fetchone()[0] if 'odev' in tables else 0
    child = con.execute('SELECT COUNT(*) FROM odev_satir').fetchone()[0] if 'odev_satir' in tables else 0
    response = {
        'mode': 'preliminary', 'main': main, 'rows': child,
        'candidate_keys': None, 'missing': missing,
        'monthly': 'ogrenci_perf_gunluk' in tables,
        'weekly': 'ogrenci_perf_hafta_ders' in tables,
        'state': 'unavailable', 'details': None,
    }
    if missing:
        return response
    if main + child > max_rows:
        response['state'] = 'limited'
        return response
    pre = inspect_report_sources(con)
    response['candidate_keys'] = pre['candidate_keys']
    try:
        canonical = scan_canonical_homework(con, today=reference_day or date.today())
    except (sqlite3.Error, ValueError, TypeError):
        return response
    details = {key: canonical[key] for key in (
        'active_students', 'evaluated_students',
        'ownership_or_ambiguity_review_students',
        'ambiguous_legacy_modern_groups', 'rejected_rows', 'excluded_or_shadow_rows',
        'unknown_status_count', 'undated_count', 'canonical_tasks',
        'completed_tasks', 'overdue_open_tasks', 'source_counts',
    )}
    response['mode'] = 'canonical'
    response['state'] = canonical['state']
    response['details'] = details
    return response


def explain_cohort_audit(info: dict) -> str:
    """Human-friendly, non-identifying summary (suitable for local UI)."""
    lines = [
        'YEREL ÖDEV KAYNAKLARI',
        f'Ana görev kayıtları: {info["main"]} | Alt satırlar: {info["rows"]}',
        'Aynı öğrenci/küme/ders aday anahtarı: ' + (
            str(info['candidate_keys']) if info['candidate_keys'] is not None
            else 'büyük veri nedeniyle taranmadı'),
        'Bu benzerlik çift sayım kanıtı değildir.',
    ]
    detail = info.get('details')
    if detail:
        lines += ['', 'DOĞRULANABİLEN KAYIT KAPSAMI',
                  f'Aktif öğrenci: {detail["active_students"]} | Değerlendirilen: {detail["evaluated_students"]}',
                  f'Bağlantısı inceleme gerektiren öğrenci: {detail["ownership_or_ambiguity_review_students"]}',
                  f'Belirsiz ana/alt grup: {detail["ambiguous_legacy_modern_groups"]}',
                  f'Dışarıda kalan/gölge satır: {detail["excluded_or_shadow_rows"]}',
                  f'Tanınmayan durum: {detail["unknown_status_count"]} | Tarihi belirsiz: {detail["undated_count"]}',
                  f'Geçerli kanıt görevleri: {detail["canonical_tasks"]} | Tamamlanan: {detail["completed_tasks"]}',
                  f'Tarihi geçmiş açık görev: {detail["overdue_open_tasks"]}',
                  ('Durum: KAYNAK İNCELEMESİ GEREKLİ' if info['state'] != 'OBSERVED'
                   else 'Durum: Yerel kanıt ön denetimi tamamlandı')]
    elif info.get('state') == 'limited':
        lines += ['', 'Kayıt sayısı hızlı tarama sınırını aşıyor; yalnızca ön denetim yapılabildi.']
    else:
        lines += ['', 'Tam kanıt denetimi için gerekli kaynak şeması doğrulanamadı.']
    if info.get('missing'):
        lines += ['Eksik tablolar: ' + ', '.join(info['missing'])]
    lines += ['', 'UYARI: Farklı ekranlarda tarih kapsamı ve kayıt birimi farklı olabilir.',
              'Ödev yüzdesi sınav başarısı değildir. Kayıtlar değiştirilmedi veya internete gönderilmedi.']
    return '\n'.join(lines)
