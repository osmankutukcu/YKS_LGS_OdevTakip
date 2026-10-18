#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V42 CLI. No application Qt import and no database write operations."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.curriculum_stability_v42 import (
    source_integrity, inspect_student_contract, to_public_report,
)


def run(root: Path, baseline_file: Path, db_path=None, student_id=None):
    baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
    findings = source_integrity(root, baseline)
    result = {
        'protected_source_check': 'PASS' if not findings else 'FAIL',
        'protected_file_count': len(baseline),
        'source_errors': [f.message for f in findings],
        'real_mac_windows_ui': 'NOT_TESTED',
        'manual_homework_and_control_pilot': 'NOT_TESTED',
        'release_ready': False,
    }
    if db_path is not None:
        if student_id is None:
            raise ValueError('Veritabanı testi için --student-id gerekli.')
        db_path = Path(db_path)
        # Hash only when no WAL is present. A live WAL may contain committed data
        # without changing the main SQLite file, so a single-file hash is NOT proof.
        result['database_audit'] = to_public_report(inspect_student_contract(
            db_path, student_id=student_id, db_source=root/'db.py'
        ))
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description='V42 salt-okunur müfredat stabilizasyon denetimi')
    p.add_argument('--db', help='YALNIZCA YEDEK SQLite dosyası kullanın')
    p.add_argument('--student-id', type=int, help='Yedek veritabanında test öğrencisi ID')
    p.add_argument('--report', help='JSON rapor yolu (gerçek öğrenci adı içermez)')
    ns = p.parse_args(argv)
    result = run(ROOT, ROOT/'tests'/'v42_protected_hashes.json', ns.db, ns.student_id)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if ns.report:
        pth = Path(ns.report)
        pth.parent.mkdir(parents=True, exist_ok=True)
        pth.write_text(payload, encoding='utf-8')
    print(payload, end='')
    return 1 if result['protected_source_check'] == 'FAIL' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print('V42 DENETİM DURDURULDU:', str(exc), file=sys.stderr)
        sys.exit(2)
