#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V44 bağımsız denetim; geçiş kodu 0 olmak YAYIN ONAYI değildir."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from services.release_readiness_v44 import v44_preflight


def main(argv=None):
    p = argparse.ArgumentParser(description='V44 kaynak ve izole SQLite yedeği denetimi')
    p.add_argument('--db', help='Yalnızca uygulamadan BAĞIMSIZ tutarlı SQLite yedeği')
    p.add_argument('--backup-ack', action='store_true', help='Yedeğin bağımsız/tutarlı olduğunu onayla')
    p.add_argument('--report', help='Kişisel bilgi içermeyen JSON çıktı')
    args = p.parse_args(argv)
    try:
        report = v44_preflight(ROOT, Path(args.db) if args.db else None, backup_ack=args.backup_ack)
        if args.report:
            dest = Path(args.report)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        # Fail closed for source drift and DB BLOCK. REVIEW is not a release success either.
        return 1 if report['historical_v35_gate']['status'] == 'BLOCK' or report['base_protection']['status'] == 'BLOCK' or (
            report.get('database_audit', {}).get('database_test') in ('BLOCK', 'REVIEW')) else 0
    except (OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        print('V44 ÖN DENETİM ENGELİ:', str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
