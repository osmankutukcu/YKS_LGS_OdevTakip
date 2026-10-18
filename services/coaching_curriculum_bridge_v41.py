"""V41: non-mutating coach curriculum view, preserving legacy coaching keys.

This module DOES NOT guess old subject names, rename coaching rows, or create tables.
New custom subjects use their immutable lesson ID for new coaching records.
Existing coach subject strings remain unchanged for compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
from typing import Mapping, Iterable


@dataclass(frozen=True)
class CoachSubject:
    storage_key: str
    title: str
    code: str | None
    topics: tuple[str, ...]
    historical: bool = False


def _tables(con):
    return {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(con, table: str):
    if table not in _tables(con):
        return set()
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', table):
        return set()
    return {str(r[1]) for r in con.execute(f'PRAGMA table_info("{table}")')}


def _looks_lgs(main_group: str, sub_group: str) -> bool:
    main = str(main_group or '').lower().strip()
    if main == 'lgs':
        return True
    if main in ('yks', 'ara sınıf', 'ara sinif'):
        return False
    sub = str(sub_group or '').lower()
    return ('lgs' in sub or '8.' in sub or '8.sınıf' in sub or 'ortaokul' in sub)


def read_scoped_topics(con: sqlite3.Connection, code: str, *, student_id: int | None = None,
                       main_group: str = '', sub_group: str = '') -> tuple[str, ...]:
    """Read General → Group → Student topic titles, never mixing row-ID namespaces."""
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', str(code or '')):
        return ()
    tables = _tables(con)
    topics: dict[str, str] = {}
    if code in tables and 'konu' in _columns(con, code):
        order = ' ORDER BY id' if 'id' in _columns(con, code) else ''
        for row in con.execute(f'SELECT konu FROM "{code}"{order}'):
            val = str(row[0] or '').strip()
            if val:
                topics.setdefault(val.casefold(), val)
    for table, conditions, params in (
        ('grup_konu_duzen', ('ders=?', 'ana_grup=?', 'alt_grup=?'), (code, main_group, sub_group)),
        ('ogrenci_konu_duzen', ('ders=?', 'ogrenci_id=?'), (code, student_id)),
    ):
        required = {clause.split('=')[0] for clause in conditions} | {'konu'}
        if not required <= _columns(con, table):
            continue
        if table == 'grup_konu_duzen' and (not main_group or not sub_group):
            continue
        if table == 'ogrenci_konu_duzen' and not student_id:
            continue
        sql = f'SELECT konu FROM "{table}" WHERE ' + ' AND '.join(conditions)
        for row in con.execute(sql, params):
            val = str(row[0] or '').strip()
            if val:
                topics[val.casefold()] = val
    return tuple(topics.values())


def read_student_coach_subjects(
    con: sqlite3.Connection, *, student_id: int, main_group: str, sub_group: str,
    legacy_topics: Mapping[str, Iterable[str]], legacy_code_labels: Mapping[str, str],
    default_group_lessons: Mapping[str, Iterable[str]],
) -> tuple[CoachSubject, ...]:
    """Legacy labels intact; new custom choices only when assigned to the student's group.

    Inactive/unassigned historical coaching subjects remain selectable. Ambiguous
    display names are never automatically mapped to a lesson ID.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli öğrenci kimliği gerekli.')
    tables = _tables(con)
    is_lgs = _looks_lgs(main_group, sub_group)
    catalog = {}
    if {'id', 'ad', 'aktif', 'ozel'} <= _columns(con, 'ders_tanimlari'):
        order = ' ORDER BY siralama,id' if 'siralama' in _columns(con, 'ders_tanimlari') else ' ORDER BY id'
        for row in con.execute('SELECT id,ad,aktif,ozel FROM ders_tanimlari' + order):
            catalog[str(row[0])] = (str(row[1] or row[0]), bool(row[2]), bool(row[3]))
    selected = []
    if {'grup_adi', 'ders_id'} <= _columns(con, 'grup_dersleri') and sub_group:
        selected = [str(r[0]) for r in con.execute('SELECT ders_id FROM grup_dersleri WHERE grup_adi=?', (sub_group,))]
    if not selected:
        selected = list(default_group_lessons.get(main_group, default_group_lessons.get('YKS', ())))
    allowed = set(selected)

    history = set()
    recorded_topics: dict[str, list[str]] = {}
    if {'ogrenci_id', 'ders_adi', 'konu_adi'} <= _columns(con, 'koc_konu_takip'):
        order = ' ORDER BY id' if 'id' in _columns(con, 'koc_konu_takip') else ''
        for label, topic in con.execute(
            'SELECT ders_adi, konu_adi FROM koc_konu_takip WHERE ogrenci_id=?' + order,
            (student_id,)):
            label = str(label or '').strip()
            topic = str(topic or '').strip()
            if label and topic:
                recorded_topics.setdefault(label, []).append(topic)
    def with_recorded(storage_key, topics):
        # Old coaching records must remain visible even after a topic rename/removal.
        return tuple(dict.fromkeys([*topics, *recorded_topics.get(storage_key, [])]))

    for table in ('koc_konu_takip', 'koc_kitaplar'):
        if {'ogrenci_id', 'ders_adi'} <= _columns(con, table):
            history.update(str(row[0]) for row in con.execute(
                f'SELECT DISTINCT ders_adi FROM "{table}" WHERE ogrenci_id=? AND ders_adi IS NOT NULL',
                (student_id,)) if str(row[0] or '').strip())

    options: list[CoachSubject] = []
    used = set()
    # Keep exactly the same legacy coaching storage strings and exam filtering.
    for name, original_topics in legacy_topics.items():
        if ('(LGS)' in name or 'lgs' in name.lower()) != is_lgs and name not in history:
            continue
        code = next((k for k, v in legacy_code_labels.items() if v == name), None)
        if code in catalog and catalog[code][2] and name not in history:
            # New custom courses use immutable code, not the old guessed label.
            continue
        if code in catalog and not catalog[code][1] and name not in history:
            # Historical legacy labels without matching active code are left alone;
            # explicitly inactive course labels are hidden unless used historically.
            continue
        topics = tuple(str(t) for t in original_topics if str(t).strip())
        if code and code in catalog:
            current = read_scoped_topics(con, code, student_id=student_id,
                                         main_group=main_group, sub_group=sub_group)
            if current:
                topics = current
        options.append(CoachSubject(name, name, code, with_recorded(name, topics), name in history))
        used.add(name)

    # Only custom courses assigned to this group (or those already used by the
    # student) are offered. Storage uses immutable ID to withstand label edits.
    for code, (title, active, custom) in catalog.items():
        if not custom:
            continue
        if not ((active and code in allowed) or code in history):
            continue
        if code in used:
            continue
        scoped = read_scoped_topics(con, code, student_id=student_id,
                                    main_group=main_group, sub_group=sub_group)
        # Teacher-friendly label: the stable technical ID remains in the item data.
        label = f'{title} (Özel)' if active else f'{title} (Pasif • Geçmiş)'
        if any(other.title == label for other in options):
            label += f' · {code}'  # distinguish same-named courses without guessing
        options.append(CoachSubject(code, label, code, with_recorded(code, scoped), code in history))
        used.add(code)

    # Historical labels that cannot be resolved stay distinct; no guessing.
    for name in sorted(history - used):
        options.append(CoachSubject(name, f'{name} (önceki koçluk kaydı)', None,
                                    with_recorded(name, ()), True))
        used.add(name)
    return tuple(options)
