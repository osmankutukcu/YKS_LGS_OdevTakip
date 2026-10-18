# -*- coding: utf-8 -*-
"""V3.5.26 pilot gate: deterministic, non-invasive source checks.

Optional SQLite audit accepts ONLY an explicitly acknowledged closed BACKUP,
never silently touches a live database. This gate is not Windows UAT.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CORE_FUNCTIONS = {'ui/homework_form.py': {'_kaydet_kume', '_odev_kontrol'},
                  'ui/odev_kontrol.py': {'_kaydet', '_hesapla_yuzde'}}


def _shadowed_methods(tree: ast.AST) -> list[dict]:
    findings = []
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        methods = {}
        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.setdefault(node.name, []).append(node.lineno)
        for name, lines in methods.items():
            if len(lines) > 1:
                findings.append({'class': cls.name, 'method': name,
                                 'definitions': len(lines), 'active_line': lines[-1]})
    return findings


def source_gate(root: Path = ROOT) -> dict:
    root = Path(root)
    baseline = json.loads((root/'tests/v42_protected_hashes.json').read_text('utf8'))
    modified = [name for name, sha in sorted(baseline.items())
                if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest() != sha]
    missing_methods = []
    shadowed = {}
    for source, needed in CORE_FUNCTIONS.items():
        tree = ast.parse((root/source).read_text('utf8'))
        # Only class definitions; module-level helpers do not satisfy the form contract.
        available = {fn.name for klass in ast.walk(tree) if isinstance(klass, ast.ClassDef)
                     for fn in klass.body if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))}
        missing_methods += [f'{source}:{name}' for name in sorted(needed-available)]
        shadowed[source] = _shadowed_methods(tree)
    changed_module = (root/'services/portal_homework_v3526.py').read_text('utf8')
    portal = (root/'utils/web_portal.py').read_text('utf8')
    portal_connected = (all(s in portal for s in ('subject_progress(self.con, self.sid)',
                                                 'pending_homework(self.con, self.sid, limit=10)'))
                        and 'def subject_progress(' in changed_module
                        and 'def pending_homework(' in changed_module)
    status = 'PASS' if not modified and not missing_methods and portal_connected else 'BLOCK'
    return {'pilot_source_status': status,
            'protected_files_checked': len(baseline),
            'protected_files_changed': modified,
            'core_handlers_missing': missing_methods,
            'report_linked': portal_connected,
            'duplicate_handlers_observed_not_deleted': shadowed,
            'data_writes': False,
            'windows_user_acceptance': 'NOT_VERIFIED',
            'public_release_ready': False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='V3.5.26 korunan çekirdek kaynak kontrolü')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--backup', type=Path, help='Yalnızca kapalı uygulamadan alınmış veritabanı yedeği')
    parser.add_argument('--backup-ack', action='store_true')
    parser.add_argument('--output', type=Path, help='JSON sonucu dosyaya yaz (kişi bilgisi yok)')
    args = parser.parse_args(argv)
    report = source_gate(args.root)
    if args.backup:
        if not args.backup_ack:
            parser.error('--backup için --backup-ack zorunludur.')
        from services.homework_integrity_v43 import audit_backup
        # Contains only counts and codes; no student names or phones.
        report['backup_audit'] = audit_backup(args.backup, acknowledged_backup=True)
        if report['backup_audit']['database_test'] == 'BLOCK':
            report['pilot_source_status'] = 'BLOCK'
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['pilot_source_status']=='PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
