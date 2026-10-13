"""Read-only SQL analysis of the existing V31 control form queries.

Runs with SQLite mode=ro, never creates indexes or mutates the user's DB.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from urllib.parse import quote
from time import perf_counter_ns
from typing import Any


def _read_only(db_path: str | Path) -> sqlite3.Connection:
    p = Path(db_path).expanduser().resolve(strict=True)
    if not p.is_file():
        raise ValueError('Veritabanı dosyası bulunamadı.')
    # Force read-only even if the caller opened a live DB. Query only metadata.
    con = sqlite3.connect('file:' + quote(p.as_posix(), safe='/:') + '?mode=ro', uri=True)
    con.execute('PRAGMA query_only=ON')
    return con


def inspect_query_plans(db_path: str | Path) -> dict[str, Any]:
    con = _read_only(db_path)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        needed = {'odev', 'odev_kume'}
        if not needed.issubset(tables):
            return {'schema_supported': False, 'missing_tables': sorted(needed - tables)}
        indexes = {}
        for table in sorted(needed):
            indexes[table] = [r[1] for r in con.execute(f'PRAGMA index_list("{table}")')]
        probes = {
            'cluster_open': ('SELECT id FROM odev WHERE kume_id = ? ORDER BY id', (1,)),
            'student_summary': ('SELECT count(*) FROM odev d JOIN odev_kume k ON k.id = d.kume_id WHERE k.ogrenci_id = ? AND COALESCE(d.silindi,0)=0', (1,)),
        }
        plans = {}
        for name, (sql, params) in probes.items():
            try:
                plans[name] = [str(r[3]) for r in con.execute('EXPLAIN QUERY PLAN ' + sql, params)]
            except sqlite3.OperationalError as exc:
                # Old installations may lack migrated columns; report, do not repair.
                plans[name] = [f'unavailable: {type(exc).__name__}']
        return {'schema_supported': True, 'indexes': indexes, 'plans': plans,
                'mutations': 0, 'student_records_exported': 0}
    finally:
        con.close()


def compare_header_stat_queries(db_path: str | Path, student_id: int, repeats: int = 8) -> dict[str, Any]:
    """Compare *read-only* single-pass vs original two aggregate SELECTs.

    Result deliberately omits actual aggregates/IDs to protect student privacy.
    Existing production SQL is NOT changed by running the benchmark.
    """
    repeats = int(repeats)
    if not 1 <= repeats <= 100:
        raise ValueError('repeats must be between 1 and 100')
    con = _read_only(db_path)
    try:
        old1 = '''SELECT COUNT(*), SUM(CASE WHEN TRIM(LOWER(COALESCE(d.durum,''))) IN ('yapildi','tamam') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN COALESCE(d.aktarildi,0)=1 THEN 1 ELSE 0 END)
                    FROM odev d JOIN odev_kume k ON k.id=d.kume_id WHERE k.ogrenci_id=? AND COALESCE(d.silindi,0)=0'''
        old2 = '''SELECT COUNT(*), SUM(CASE WHEN TRIM(LOWER(COALESCE(d.durum,''))) IN ('yapildi','tamam') THEN 1 ELSE 0 END)
                    FROM odev d JOIN odev_kume k ON k.id=d.kume_id WHERE k.ogrenci_id=? AND COALESCE(d.aktarildi,0)=0'''
        # Match old filtering semantics exactly (note: active omits silindi filter).
        combined = '''SELECT
          SUM(CASE WHEN COALESCE(d.silindi,0)=0 THEN 1 ELSE 0 END),
          SUM(CASE WHEN COALESCE(d.silindi,0)=0 AND TRIM(LOWER(COALESCE(d.durum,''))) IN ('yapildi','tamam') THEN 1 ELSE 0 END),
          SUM(CASE WHEN COALESCE(d.silindi,0)=0 AND COALESCE(d.aktarildi,0)=1 THEN 1 ELSE 0 END),
          SUM(CASE WHEN COALESCE(d.aktarildi,0)=0 THEN 1 ELSE 0 END),
          SUM(CASE WHEN COALESCE(d.aktarildi,0)=0 AND TRIM(LOWER(COALESCE(d.durum,''))) IN ('yapildi','tamam') THEN 1 ELSE 0 END)
          FROM odev d JOIN odev_kume k ON k.id=d.kume_id WHERE k.ogrenci_id=?'''
        params = (int(student_id),)
        # Verify mathematical equivalence first, fail closed before timing.
        old_a = con.execute(old1, params).fetchone()
        old_b = con.execute(old2, params).fetchone()
        candidate = con.execute(combined, params).fetchone()
        reference = tuple(int(v or 0) for v in (*old_a, *old_b))
        observed = tuple(int(v or 0) for v in candidate)
        equivalent = reference == observed
        if not equivalent:
            return {'equivalent': False, 'measurements_taken': 0, 'mutations': 0}
        old_t, new_t = [], []
        for _ in range(repeats):
            start = perf_counter_ns()
            con.execute(old1, params).fetchone()
            con.execute(old2, params).fetchone()
            old_t.append((perf_counter_ns() - start) / 1e6)
            start = perf_counter_ns()
            con.execute(combined, params).fetchone()
            new_t.append((perf_counter_ns() - start) / 1e6)
        return {'equivalent': True, 'measurements_taken': repeats,
                'legacy_avg_ms': round(sum(old_t)/repeats, 4),
                'candidate_avg_ms': round(sum(new_t)/repeats, 4),
                'mutations': 0, 'student_records_exported': 0,
                'note': 'Candidate for later opt-in use; not installed in the core UI'}
    except sqlite3.OperationalError:
        return {'equivalent': None, 'measurements_taken': 0,
                'note': 'Some legacy database columns not found; migration was not attempted',
                'mutations': 0}
    finally:
        con.close()
