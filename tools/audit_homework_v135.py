"""Read-only V13.5 SQLite link audit. Example:
python tools/audit_homework_v135.py --db /path/to/database.db --json
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from services.homework_integrity_v135 import audit_database


def run(db_path: Path):
    path = db_path.expanduser().resolve(strict=True)
    con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        con.execute('PRAGMA query_only=ON')
        return audit_database(con)
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Ödev kayıt bağlantılarını salt okunur denetler.')
    parser.add_argument('--db', required=True, type=Path, help='SQLite veritabanı yolu')
    parser.add_argument('--json', action='store_true', help='Makine okunur JSON çıktı')
    args = parser.parse_args(argv)
    try:
        report = run(args.db)
    except (OSError, sqlite3.Error) as exc:
        parser.exit(2, f'Veritabanı okunamadı: {exc}\n')
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        if not report.findings:
            print('Kontrol edilen bağlantılarda sorun bulunmadı.')
        for f in report.findings:
            print(f'[{f.severity.upper()}] {f.message}: {f.count} kayıt' +
                  ('; örnek satır ID: ' + ','.join(f.references) if f.references else ''))
        print('\nBu araç veritabanını değiştirmez ve otomatik düzeltme yapmaz.')
    return 1 if report.findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
