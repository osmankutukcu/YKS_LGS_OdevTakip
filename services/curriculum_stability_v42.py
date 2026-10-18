# -*- coding: utf-8 -*-
"""V42: salt-okunur müfredat -> koçluk / kitap / ödev / rapor sözleşme denetimi.

Bu dosya UYGULAMAYA bağlanmaz: gerçek kayıt akışını ve Qt formlarını değiştirmez.
Bilinmeyen ders adlarını asla otomatik eşleştirmez veya yeniden yazmaz.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, asdict
from pathlib import Path
import ast
import hashlib
import json
import sqlite3

from services.coaching_curriculum_bridge_v41 import read_student_coach_subjects
from services.lesson_catalog_v39 import read_lesson_options, resolve_lesson_code


PROTECTED_RELATIVE = (
    'ui/homework_form.py', 'ui/odev_kontrol.py', 'db.py', 'main_window.py',
    'ui/curriculum_page.py', 'ui/topic_editor.py', 'ui/coaching_manager.py',
    'ui/book_dialog.py', 'ui/reports.py', 'ui/modern_settings.py',
)


@dataclass(frozen=True)
class Finding:
    severity: str  # ERROR: pilot durmalı; REVIEW: öğretmen denetlemeli; INFO: tarihî veri olabilir
    code: str
    message: str


@dataclass(frozen=True)
class StudentContract:
    group: str
    main_group: str
    assignment_mode: str
    active_lessons: tuple[str, ...]
    assigned_custom_lessons: tuple[str, ...]
    coaching_custom_lessons: tuple[str, ...]
    student_source_counts: tuple[tuple[str, int], ...]
    findings: tuple[Finding, ...]


def _columns(con, table: str, tables: set[str]) -> set[str]:
    if table not in tables:
        return set()
    # Table never comes from a user-controlled parameter: fixed constant list only.
    return {str(r[1]) for r in con.execute(f'PRAGMA table_info("{table}")')}


def _db_literals(db_source: Path) -> tuple[dict, dict]:
    """Pull configuration WITHOUT importing db.py / creating a database."""
    tree = ast.parse(db_source.read_text(encoding='utf-8'))
    names = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if n.targets[0].id in ('DEFAULT_GRUP_DERSLER', 'CURRICULUM_GROUPS'):
                names[n.targets[0].id] = ast.literal_eval(n.value)
    if 'DEFAULT_GRUP_DERSLER' not in names or 'CURRICULUM_GROUPS' not in names:
        raise ValueError('Grup varsayılanları bulunamadı; denetim yapılamıyor.')
    return names['DEFAULT_GRUP_DERSLER'], names['CURRICULUM_GROUPS']


def source_integrity(root: Path, baseline: dict[str, str]) -> tuple[Finding, ...]:
    """Expected SHA256s are frozen from V41; NO updating baselines on mismatch."""
    root = Path(root)
    findings = []
    for file in PROTECTED_RELATIVE:
        expected = baseline.get(file)
        path = root / file
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if not expected or actual != expected:
            findings.append(Finding('ERROR', 'PROTECTED_SOURCE_CHANGED',
                                    f'Korunan dosya değişmiş/eksik: {file}'))
    return tuple(findings)


def inspect_student_contract(db_path: str | Path, *, student_id: int,
                             db_source: str | Path) -> StudentContract:
    """Bounded, read-only contract inspection. Never calls db.get_conn().

    The selected student is used ONLY as a bound SQL parameter. Names, phone
    numbers, and notes are deliberately absent from the report.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Pozitif tam sayı öğrenci ID gerekli.')
    path = Path(db_path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError('SQLite dosyası bulunamadı.')
    defaults, groups = _db_literals(Path(db_source))
    findings: list[Finding] = []
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as con:
        con.execute('PRAGMA query_only=ON')
        con.execute('BEGIN')
        tables = {str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'ogrenci', 'ders_tanimlari'} <= tables:
            raise ValueError('Öğrenci/ders tablosu eksik. Test durduruldu.')
        if not {'id', 'ana_grup', 'alt_grup'} <= _columns(con, 'ogrenci', tables):
            raise ValueError('Öğrenci grubu şeması beklenen yapıda değil.')
        if not {'id', 'ad', 'aktif', 'ozel'} <= _columns(con, 'ders_tanimlari', tables):
            raise ValueError('Ders kataloğu şeması beklenen yapıda değil.')
        student = con.execute('SELECT ana_grup,alt_grup FROM ogrenci WHERE id=?',
                              (student_id,)).fetchone()
        if student is None:
            raise ValueError('Öğrenci kaydı bulunamadı.')
        main, subgroup = (str(x or '').strip() for x in student)
        if not main:
            main = next((name for name, subs in groups.items() if subgroup in subs), 'YKS')
            findings.append(Finding('REVIEW', 'MISSING_MAIN_GROUP',
                                    'Öğrencinin ana grubu eksik; uyumluluk varsayılanı kullanıldı.'))
        if not subgroup:
            findings.append(Finding('REVIEW', 'MISSING_SUBGROUP',
                                    'Alt grup boş; öğrenciye özel grup eşleştirmesi uygulanamaz.'))
        catalog = {
            str(row[0]): (str(row[1] or row[0]), bool(row[2]), bool(row[3]))
            for row in con.execute('SELECT id,ad,aktif,ozel FROM ders_tanimlari')
        }
        if not catalog:
            raise ValueError('Ders kataloğu boş; sonuç üretilemiyor.')
        selected = []
        if {'grup_adi', 'ders_id'} <= _columns(con, 'grup_dersleri', tables) and subgroup:
            selected = [str(r[0]) for r in con.execute(
                'SELECT ders_id FROM grup_dersleri WHERE grup_adi=?', (subgroup,))]
        assigned = selected if selected else list(defaults.get(main, defaults['YKS']))
        active_lessons = tuple(dict.fromkeys(
            c for c in assigned if c in catalog and catalog[c][1]
        ))
        unknown = sorted(set(assigned) - set(catalog))
        if unknown:
            findings.append(Finding('REVIEW', 'UNKNOWN_ASSIGNED_LESSON',
                                    'Ders kataloğunda olmayan grup atamaları: ' + ', '.join(unknown[:8])))
        disabled = sorted(c for c in assigned if c in catalog and not catalog[c][1])
        if disabled:
            findings.append(Finding('INFO', 'INACTIVE_ASSIGNMENT',
                                    'Gruba atanmış pasif dersler (geçmiş veri korunmalı): ' +
                                    ', '.join(disabled[:8])))
        group_owners = {str(row[0]) for row in con.execute(
            'SELECT DISTINCT ana_grup FROM ogrenci WHERE alt_grup=?', (subgroup,)
        ) if row[0]}
        if len(group_owners) > 1:
            findings.append(Finding('REVIEW', 'GROUP_NAME_COLLISION',
                                    'Aynı alt grup birden çok ana grupta kullanılıyor; '
                                    'grup eşleştirmeleri alt grup adına göre tutuluyor.'))
        # Existing v41 bridge should offer all assigned and active custom lessons.
        subject_options = read_student_coach_subjects(
            con, student_id=student_id, main_group=main, sub_group=subgroup,
            legacy_topics={}, legacy_code_labels={}, default_group_lessons=defaults,
        )
        expected_custom = {c for c in active_lessons if catalog[c][2]}
        provided_custom = {o.storage_key for o in subject_options
                           if o.code in catalog and catalog[o.code][2] and o.storage_key == o.code}
        missing_custom = sorted(expected_custom - provided_custom)
        if missing_custom:
            findings.append(Finding('ERROR', 'CUSTOM_COURSE_MISSING_IN_COACHING',
                                    'Aktif özel ders Koçlukta bulunamadı: ' + ', '.join(missing_custom[:8])))
        if 'koc_konu_takip' in tables and {'ogrenci_id', 'ders_adi'} <= _columns(con, 'koc_konu_takip', tables):
            opts = read_lesson_options(con)
            labels = [str(r[0]) for r in con.execute(
                'SELECT DISTINCT ders_adi FROM koc_konu_takip WHERE ogrenci_id=?', (student_id,))
                if str(r[0] or '').strip()]
            unresolved = sorted({t for t in labels if resolve_lesson_code(t, opts) is None})
            if unresolved:
                # Historic strings are NOT an error, and are never silently migrated.
                findings.append(Finding('REVIEW', 'UNRESOLVED_COACH_LABEL',
                                        f'{len(unresolved)} farklı eski Koçluk ders etiketi kesin eşleşmiyor; '
                                        'otomatik birleştirme yapılmadı.'))
        else:
            findings.append(Finding('REVIEW', 'COACH_SOURCE_ABSENT',
                                    'Koçluk kayıt tablosu veya beklenen sütunları bulunamadı.'))
        source_counts = []
        # Only count rows belonging to the requested student. Never sum these
        # different sources into a purported "total number of homework".
        for table in ('ogrenci_kitap', 'odev', 'odev_satir', 'odev_takip',
                      'kapsam_odev_v233', 'koc_konu_takip', 'koc_kitaplar'):
            cols = _columns(con, table, tables)
            if 'ogrenci_id' in cols:
                count = int(con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE ogrenci_id=?',
                                        (student_id,)).fetchone()[0])
                source_counts.append((table, count))
            else:
                findings.append(Finding('INFO', 'SOURCE_NOT_COMPARABLE',
                                        f'{table} tablosu yok veya öğrenci kimliği sütunu eksik.'))
    return StudentContract(
        group=subgroup, main_group=main,
        assignment_mode='Gruba özel' if selected else 'Varsayılan',
        active_lessons=active_lessons,
        assigned_custom_lessons=tuple(sorted(expected_custom)),
        coaching_custom_lessons=tuple(sorted(provided_custom)),
        student_source_counts=tuple(source_counts),
        findings=tuple(findings),
    )


def to_public_report(contract: StudentContract) -> dict:
    """Export no name, student id, group or lesson-specific sensitive data."""
    return {
        'assignment_mode': contract.assignment_mode,
        'active_lesson_count': len(contract.active_lessons),
        'custom_assigned_count': len(contract.assigned_custom_lessons),
        'custom_coaching_count': len(contract.coaching_custom_lessons),
        'source_counts': dict(contract.student_source_counts),
        'findings': [asdict(f) for f in contract.findings],
        'database_access': 'READ_ONLY',  # no assertion about live WAL/checkpoint bytes
        'desktop_ui_accepted': False,
    }
