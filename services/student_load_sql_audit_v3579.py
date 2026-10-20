# -*- coding: utf-8 -*-
"""V3579: Strictly read-only SQLite diagnostics for student loading.

No import of Qt, no database schema modifications, no application hooks.
The same query used in `ui/homework_form.py` is analyzed with SQLite's
EXPLAIN QUERY PLAN.  Reports contain aggregate counts, never student ids,
student names, books, topics, row contents, or local database paths.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

_MATRIX_SQL = 'SELECT ders, konu_id, kitap_ad, durum FROM odev WHERE ogrenci_id=?'
_CREATE_INDEX_SUGGESTION = (
    'CREATE INDEX IF NOT EXISTS idx_kocpilot_odev_ogrenci_id ON odev(ogrenci_id)'
)


def audit_connection(connection: sqlite3.Connection) -> dict[str, Any]:
    """Inspect index shape and read-query plan, without reading student records."""
    connection.execute('PRAGMA query_only=ON')
    table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='odev'"
    ).fetchone()
    if not table:
        return {'status': 'missing_homework_table', 'read_only': True}
    columns = {str(row[1]).lower() for row in connection.execute('PRAGMA table_info("odev")')}
    required = {'ogrenci_id', 'ders', 'konu_id', 'kitap_ad', 'durum'}
    if not required.issubset(columns):
        return {'status': 'incompatible_homework_table', 'read_only': True}

    rows = int(connection.execute('SELECT COUNT(*) FROM odev').fetchone()[0])
    # Column names and index types are schema facts; no row contents are emitted.
    index_has_student_prefix = False
    inspected_indexes = 0
    for item in connection.execute('PRAGMA index_list("odev")'):
        idx_name = str(item[1])
        # PRAGMA argument cannot be bound; escape the double quote in identifiers.
        safe_name = idx_name.replace('"', '""')
        cols = [str(c[2]).lower() for c in connection.execute(
            f'PRAGMA index_info("{safe_name}")'
        ) if c[2] is not None]
        inspected_indexes += 1
        if cols and cols[0] == 'ogrenci_id':
            index_has_student_prefix = True

    query_plan = [str(row[3]) for row in connection.execute(
        'EXPLAIN QUERY PLAN ' + _MATRIX_SQL, (0,)
    ).fetchall()]
    plan_uses_search = any('SEARCH' in line.upper() and 'ODEV' in line.upper() for line in query_plan)
    plan_uses_scan = any('SCAN' in line.upper() and 'ODEV' in line.upper() for line in query_plan)
    # This is a possible optimization, NOT a migration decision or proof of slowness.
    recommendation = (
        'inspect_optional_student_index' if rows >= 1000 and not index_has_student_prefix
        else 'measure_windows_before_index_change'
    )
    return {
        'status': 'ok',
        'read_only': True,
        'homework_row_count': rows,
        'indexes_checked': inspected_indexes,
        'has_student_prefix_index': index_has_student_prefix,
        'query_plan_search': plan_uses_search,
        'query_plan_scan': plan_uses_scan,
        'recommendation': recommendation,
    }


def audit_database_path(path: str | Path) -> dict[str, Any]:
    """Use SQLite read-only URI. The real DB cannot be written or created."""
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise ValueError('The database path is not a regular file')
    uri = p.as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as con:
        return audit_connection(con)
