#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V43 bağımsız salt okunur ödev bütünlüğü ve sürüm ön kabul kontrolü.

Bu aracı çalıştırmak Windows/macOS GUI ve manuel yayım onayı anlamına GELMEZ.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.curriculum_stability_v42 import source_integrity
from services.homework_integrity_v43 import audit_backup


def preflight(root: Path, *, db=None, backup_ack=False):
    baseline = json.loads((root/'tests/v42_protected_hashes.json').read_text(encoding='utf-8'))
    changes = source_integrity(root, baseline)
    data = {
        'stage': 'V43_PREPILOT',
        'checked_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'protected_sources': {'status': 'PASS' if not changes else 'BLOCK',
                              'count': len(baseline), 'changed': [x.message for x in changes]},
        'gui_mac': 'NOT_TESTED',
        'gui_windows': 'NOT_TESTED',
        'checkbox_performance': 'NOT_MEASURED_ON_DEVICE',
        'manual_acceptance': 'PENDING',
        'legacy_v35_release_gate': 'REQUIRES_SEPARATE_REVIEW',
        'release_ready': False,
    }
    if db is not None:
        data['backup_integrity'] = audit_backup(Path(db), acknowledged_backup=backup_ack)
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description='V43 - ödev kayıt koruma, kaynak ve pilot ön kontrol')
    parser.add_argument('--db', help='SADECE kapalı uygulamadan alınmış BAĞIMSIZ SQLite yedeği')
    parser.add_argument('--backup-ack', action='store_true', help='Bu dosyanın ayrı ve tutarlı bir YEDEK olduğunu onaylıyorum')
    parser.add_argument('--report', help='Kişisel veri içermeyen JSON rapor dosyası')
    args = parser.parse_args(argv)
    try:
        report = preflight(ROOT, db=args.db, backup_ack=args.backup_ack)
        if args.report:
            outfile = Path(args.report)
            outfile.parent.mkdir(parents=True, exist_ok=True)
            outfile.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        # manual acceptance pending -> diagnostic pass != release pass
        return 1 if report['protected_sources']['status'] != 'PASS' or (
            report.get('backup_integrity', {}).get('database_test') == 'BLOCK') else 0
    except (OSError, ValueError, json.JSONDecodeError, __import__('sqlite3').DatabaseError) as err:
        print('V43 ÖN DENETİM DURDURULDU:', str(err), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
