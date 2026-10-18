# -*- coding: utf-8 -*-
"""Read-only, no-PII, no-network health snapshot for an opt-in system panel.

Do not infer Windows UI acceptance or cloud synchronization from code presence.
A caller must explicitly supply a DB path; we never import db.py or discover it.
"""
from __future__ import annotations

from pathlib import Path
from contextlib import closing
import sqlite3

from services.system_registry_v3528 import validate_registry

# Schema-only names, not student identities, numbers, counts or content.
_CRITICAL_TABLES = ('ogrenci', 'odev', 'odev_kume')


def database_schema_health(db_path: Path) -> dict:
    db_path = Path(db_path)
    if not db_path.is_file():
        return {'state': 'DB_NOT_FOUND', 'checked': False,
                'missing_tables': [], 'row_data_read': False, 'db_modified': False}
    try:
        # mode=ro doesn't create a missing database or permit table writes.
        with closing(sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro',
                                     uri=True, timeout=0.4)) as con:
            con.execute('PRAGMA query_only=ON')
            tables = {str(r[0]) for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
        absent = [name for name in _CRITICAL_TABLES if name not in tables]
        return {'state': 'SCHEMA_PRESENT' if not absent else 'SCHEMA_REVIEW',
                'checked': True, 'missing_tables': absent,
                'row_data_read': False, 'db_modified': False}
    except (sqlite3.Error, OSError, ValueError):
        return {'state': 'DB_UNAVAILABLE', 'checked': False,
                'missing_tables': [], 'row_data_read': False, 'db_modified': False}


def system_snapshot(root: Path, *, db_path: Path | None = None) -> dict:
    from tools.v3527_core_guard import audit
    root = Path(root)
    protected = audit(root)
    registry = validate_registry(root)
    state = 'SOURCE_READY' if protected['status'] == 'PASS' and registry['status'] == 'PASS' else 'BLOCK_OR_REVIEW'
    return {
        'pilot': 'V3.5.28',
        'source_state': state,
        'protected_core': {
            'status': protected['status'],
            'protected_files_changed': len(protected.get('errors', [])),
        },
        'module_catalog': registry,
        'database': ({'state': 'NOT_REQUESTED', 'checked': False,
                      'row_data_read': False, 'db_modified': False}
                     if db_path is None else database_schema_health(Path(db_path))),
        'live_updates': {
            'existing_sqlite_probe': 'SOURCE_PRESENT',
            'existing_scoped_router': 'SOURCE_PRESENT',
            'new_decision_engine': 'OPT_IN_PILOT_NOT_UI_CONNECTED',
            'cross_device_sync_verified': False,
            'automatic_data_repair': False,
        },
        'release': {
            'windows_interactive_uat': 'NOT_VERIFIED',
            'production_approved': False,
        },
        'notes': 'Static code checks and optional schema check; not end-to-end operation proof.',
    }
