"""Read-only V23.5 integration inspection. No db.py imports, migrations or repairs.

Run from project root: python tools/audit_integration_v235.py --db /path/to/copy.db
Never run against the live database while another process writes to it.
"""
from __future__ import annotations
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.stabilization_v235 import audit_connection


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='V23.5 salt-okunur modül entegrasyon denetimi')
    parser.add_argument('--db', type=Path, required=True, help='Kapalı programdan alınmış SQLite yedeği')
    args = parser.parse_args(argv)
    path = args.db.expanduser().resolve()
    if not path.is_file():
        parser.error('Veritabanı dosyası bulunamadı; yeni veritabanı oluşturulmaz.')
    # SQLite URI file paths escape safely, existing-file-only and read-only.
    uri = path.as_uri() + '?mode=ro'
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as con:
            con.execute('PRAGMA query_only=ON')
            con.execute('BEGIN')  # one consistent read snapshot
            report = audit_connection(con)
            con.rollback()
    except (ValueError,sqlite3.Error,OSError) as exc:
        print('DENETİM YAPILAMADI:', str(exc))
        return 2
    print('SQLite:', report.database_check)
    print('Aktif/pasif öğrenci:', report.active_students,'/',report.inactive_students)
    print('Ana ödev:',report.legacy_rows,'| Ayrı kapsam ödevi:',report.scoped_rows)
    print('Kopuk bağlantı:',report.orphaned_detail_links,
          '| Öğrenci uyuşmazlığı:', report.wrong_student_detail_links)
    if report.warnings:
        for warning in report.warnings:
            print('UYARI:',warning)
    else:
        print('Denetlenen bütünlük kontrollerinde sorun bulunmadı.')
    print('UYARI: Kod kontrolü gerçek Windows/PyQt6 GUI testi yerine geçmez.')
    return 0 if report.passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
