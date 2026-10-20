# -*- coding: utf-8 -*-
"""V3580: opt-in student-load index experiments, exclusively in SQLite memory.

NEVER modifies the source database. Does not import the UI or open an app DB.
The source must be explicitly provided by an operator, ideally a disconnected
backup. No identifiers, paths or row contents occur in the result JSON.
"""
from __future__ import annotations

import math
import sqlite3
import statistics
import time
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from services.student_load_sql_audit_v3579 import audit_connection

_QUERY = 'SELECT ders, konu_id, kitap_ad, durum FROM odev WHERE ogrenci_id=?'
_INDEX_SQL = 'CREATE INDEX IF NOT EXISTS idx_v3580_memory_only ON odev(ogrenci_id)'
_DEFAULT_LIMIT = 96 * 1024 * 1024


def _pct(numbers: list[float], percentage: float) -> float:
    ordered = sorted(numbers)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, math.ceil(percentage * len(ordered)) - 1))]


def _measure(connection: sqlite3.Connection, samples: list[Any], repeats: int) -> dict[str, float]:
    for student_id in samples:
        connection.execute(_QUERY, (student_id,)).fetchall()
    values = []
    for _ in range(repeats):
        for student_id in samples:
            start = time.perf_counter_ns()
            connection.execute(_QUERY, (student_id,)).fetchall()
            values.append((time.perf_counter_ns() - start) / 1_000_000)
    return {
        'median_ms': round(float(statistics.median(values)), 5),
        'p95_ms': round(_pct(values, 0.95), 5),
        'queries_measured': len(values),
    }


def _samples(connection: sqlite3.Connection) -> list[Any]:
    # Only in-memory values, never included in returned JSON or logs.
    return [row[0] for row in connection.execute(
        'SELECT ogrenci_id FROM odev WHERE ogrenci_id IS NOT NULL '
        'GROUP BY ogrenci_id ORDER BY COUNT(*) DESC LIMIT 4'
    )]


def compare_in_memory(connection: sqlite3.Connection, *, repeats: int = 12) -> dict[str, Any]:
    """Compare on a *disposable in-memory DB*, including row-result equivalence."""
    if not 1 <= repeats <= 100:
        raise ValueError('invalid repeat count')
    databases = connection.execute('PRAGMA database_list').fetchall()
    if any(str(row[2]) for row in databases if str(row[1]) == 'main'):
        raise ValueError('benchmark requires disposable SQLite memory database')
    pre = audit_connection(connection)
    if pre.get('status') != 'ok':
        return {'status': pre.get('status', 'audit_unavailable'), 'source_changed': False}
    sample_ids = _samples(connection)
    if not sample_ids:
        return {'status': 'no_student_sample', 'source_changed': False, 'homework_row_count': 0}
    before_data = {i: Counter(connection.execute(_QUERY, (i,)).fetchall()) for i in sample_ids}
    before = _measure(connection, sample_ids, repeats)
    before_plan = [r[3] for r in connection.execute('EXPLAIN QUERY PLAN ' + _QUERY, (sample_ids[0],))]
    # The imported V3579 auditor sets query_only=ON on this connection.
    # Re-enable writes ONLY after verifying it is a disposable :memory: database.
    connection.execute('PRAGMA query_only=OFF')
    connection.execute(_INDEX_SQL)
    after_data = {i: Counter(connection.execute(_QUERY, (i,)).fetchall()) for i in sample_ids}
    after = _measure(connection, sample_ids, repeats)
    after_plan = [r[3] for r in connection.execute('EXPLAIN QUERY PLAN ' + _QUERY, (sample_ids[0],))]
    equal = before_data == after_data
    median_before = before['median_ms']
    median_after = after['median_ms']
    ratio = (median_before / median_after) if median_after > 0 else None
    if not equal:
        recommendation = 'do_not_apply_results_differ'
    elif pre['has_student_prefix_index']:
        recommendation = 'existing_student_index_present_no_migration_needed'
    elif pre['homework_row_count'] < 1000:
        recommendation = 'small_dataset_no_action_without_windows_evidence'
    elif ratio is not None and ratio >= 1.2 and (median_before-median_after) >= 0.1:
        recommendation = 'candidate_only_requires_real_windows_and_write_impact_tests'
    else:
        recommendation = 'insufficient_evidence_for_index_change'
    return {
        'status': 'ok' if equal else 'result_mismatch',
        'comparison_location': 'disposable_memory_only',
        'source_changed': False,
        'source_read_only': True,
        'student_ids_disclosed': False,
        'homework_row_count': pre['homework_row_count'],
        'student_samples_checked': len(sample_ids),
        'rows_equivalent': equal,
        'existing_student_index': pre['has_student_prefix_index'],
        'before': before,
        'after_memory_index': after,
        'median_speed_ratio': round(ratio, 2) if ratio is not None else None,
        'before_plan_uses_scan': any('SCAN' in str(x).upper() and 'ODEV' in str(x).upper() for x in before_plan),
        'after_plan_uses_search': any('SEARCH' in str(x).upper() and 'ODEV' in str(x).upper() for x in after_plan),
        'recommendation': recommendation,
        'qualification': 'microbenchmark_not_full_gui_load_and_write_cost_not_measured',
    }


def benchmark_backup_path(path: str | Path, *, max_copy_bytes: int = _DEFAULT_LIMIT,
                          repeats: int = 12) -> dict[str, Any]:
    """Open supplied backup read-only and clone it to private SQLite :memory:."""
    if max_copy_bytes <= 0:
        raise ValueError('invalid memory limit')
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise ValueError('database is not a regular file')
    with closing(sqlite3.connect(p.as_uri() + '?mode=ro', uri=True, timeout=5)) as src:
        src.execute('PRAGMA query_only=ON')
        size = int(src.execute('PRAGMA page_count').fetchone()[0]) * int(src.execute('PRAGMA page_size').fetchone()[0])
        if size > max_copy_bytes:
            return {'status': 'memory_limit_exceeded', 'source_changed': False,
                    'source_read_only': True, 'no_copy_created': True}
        with closing(sqlite3.connect(':memory:')) as temp:
            src.backup(temp)
            return compare_in_memory(temp, repeats=repeats)


def synthetic_benchmark(*, row_count: int = 12000, students: int = 150,
                        repeats: int = 12) -> dict[str, Any]:
    """Optional synthetic demo. Never claims to measure user's actual computer."""
    if not 100 <= row_count <= 100000 or not 1 <= students <= 5000:
        raise ValueError('invalid synthetic size')
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('CREATE TABLE odev (ogrenci_id INTEGER, ders TEXT, konu_id INTEGER, kitap_ad TEXT, durum TEXT)')
        db.executemany('INSERT INTO odev VALUES (?,?,?,?,?)', (
            (i % students + 1, f'ders_{i%12}', i%90, 'ornek_kitap', 'devam')
            for i in range(row_count)
        ))
        result = compare_in_memory(db, repeats=repeats)
        result['synthetic_data'] = True
        return result
