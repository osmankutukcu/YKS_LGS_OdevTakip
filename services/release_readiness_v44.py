# -*- coding: utf-8 -*-
"""V44: yayın öncesi salt-okunur, fail-closed kaynak/ödev denetimi.

NOT a replacement for historical V35 gate, and NOT a release approval.
No DB migrations/edits. All SQLite reads require isolated backup acknowledgement.
"""
from __future__ import annotations
import ast
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from services.curriculum_stability_v42 import source_integrity
from services.homework_integrity_v43 import audit_backup, digest
from tools.v35_release_gate import PROTECTED as V35_PROTECTED
from tools.v35_reviewed_source_contract import LEGACY_HANDLERS, ALT_LEGACY_METHODS


def v35_legacy_review(root: Path) -> dict:
    """Evaluate historical V35 checks without changing or reapproving fingerprints."""
    root = Path(root)
    source_diffs = []
    for name, expected in V35_PROTECTED.items():
        f = root / name
        actual = sha256(f.read_bytes().replace(b'\r\n', b'\n')).hexdigest() if f.is_file() else None
        if actual != expected:
            source_diffs.append(name)
    methods = []
    for name, spec in LEGACY_HANDLERS.items():
        f = root / name
        try:
            tree = ast.parse(f.read_text(encoding='utf-8'))
            klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == spec['class'])
        except (OSError, SyntaxError, StopIteration):
            for method in spec['methods']:
                methods.append({'file': name, 'method': method, 'state': 'MISSING_CLASS_OR_BAD_SOURCE'})
            continue
        for method, approved in spec['methods'].items():
            actual = [sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                      for n in klass.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and n.name == method]
            alt = ALT_LEGACY_METHODS.get(name, {}).get(method)
            state = ('MATCH' if actual == approved else 'APPROVED_ALTERNATIVE' if actual == alt
                     else 'DRIFT_OR_MISSING')
            methods.append({'file': name, 'method': method, 'state': state})
    return {
        'source_hash_differences': sorted(source_diffs),
        'method_count': len(methods),
        'method_matches': sum(m['state'] in ('MATCH', 'APPROVED_ALTERNATIVE') for m in methods),
        'method_differences': [m for m in methods if m['state'] not in ('MATCH', 'APPROVED_ALTERNATIVE')],
        'status': ('BLOCK' if source_diffs or any(m['state'] not in ('MATCH', 'APPROVED_ALTERNATIVE') for m in methods)
                   else 'PASS'),
        'historical_gate_modified': False,
    }


def _read_only_connection(db: Path):
    con = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    con.execute('PRAGMA query_only=ON')
    return con


def summarize_orphan_candidates(db: Path) -> dict:
    """Only aggregate counts. A candidate is NOT proof of correct linkage."""
    db = Path(db)
    pre_hash = digest(db)
    with closing(_read_only_connection(db)) as con:
        # Called only after V43 verifies schema and isolated backup.
        rows = con.execute('''
            SELECT (SELECT COUNT(*) FROM odev h
                    WHERE h.ogrenci_id=l.ogrenci_id AND h.kume_id IS l.kume_id)
            FROM odev_satir l
            WHERE l.odev_id IS NOT NULL
              AND NOT EXISTS(SELECT 1 FROM odev h0 WHERE h0.id=l.odev_id)
        ''').fetchall()
    counts = [int(r[0]) for r in rows]
    post_hash = digest(db)
    return {
        'unresolved_orphan_rows': len(rows),
        'no_same_student_cluster_candidate': sum(n == 0 for n in counts),
        'one_same_student_cluster_candidate': sum(n == 1 for n in counts),
        'multiple_same_student_cluster_candidates': sum(n > 1 for n in counts),
        'source_unchanged': pre_hash == post_hash,
        'repair_performed': False,
        'candidate_is_proof': False,
    }


def v44_preflight(root: Path, db: Path | None = None, *, backup_ack: bool = False) -> dict:
    root = Path(root)
    manifest = json.loads((root / 'tests/v42_protected_hashes.json').read_text(encoding='utf-8'))
    protection_diffs = source_integrity(root, manifest)
    legacy = v35_legacy_review(root)
    result = {
        'stage': 'V44_PRE_RELEASE_REVIEW',
        'base_protection': {'status': 'BLOCK' if protection_diffs else 'PASS',
                            'checked_count': len(manifest),
                            'changed': [d.message for d in protection_diffs]},
        'historical_v35_gate': legacy,
        'manual_windows_pilot': 'NOT_VERIFIED',
        'manual_macos_pilot': 'NOT_VERIFIED',
        'checkbox_latency': 'NOT_MEASURED',
        'signed_human_source_review': 'PENDING',
        'automatic_data_repair': False,
        'release_ready': False,
    }
    if db is not None:
        audit = audit_backup(Path(db), acknowledged_backup=backup_ack)
        result['database_audit'] = audit
        if audit['database_test'] in ('PASS', 'REVIEW') and audit['source_unchanged']:
            result['orphan_candidate_review'] = summarize_orphan_candidates(Path(db))
            if not result['orphan_candidate_review']['source_unchanged']:
                result['database_audit']['database_test'] = 'BLOCK'
    result['next_action'] = ('STOP_SOURCE_REVIEW' if protection_diffs or legacy['status'] == 'BLOCK'
                             else 'REVIEW_DATABASE' if result.get('database_audit', {}).get('database_test') in ('BLOCK', 'REVIEW')
                             else 'WINDOWS_MACOS_PILOT_REQUIRED')
    return result
