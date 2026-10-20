"""Read-only command line SQLite index audit for KoçPilot student loading.

Example: python -m tools.student_load_sql_audit_v3579 --database "C:/test-copy.db"
Does not output path, records, SQL identifiers with private content, or keys.
"""
from __future__ import annotations
import argparse
import json
from services.student_load_sql_audit_v3579 import audit_database_path


def main(argv=None):
    p = argparse.ArgumentParser(description='KoçPilot 360: read-only student-load SQL audit')
    p.add_argument('--database', required=True, help='Path to a BACKUP/COPY of SQLite database')
    args = p.parse_args(argv)
    try:
        result = audit_database_path(args.database)
    except (OSError, ValueError, RuntimeError) as e:
        print(json.dumps({'status': 'audit_unavailable', 'error_type': type(e).__name__}))
        return 2
    except Exception as e:  # sqlite3.DatabaseError, sqlite3.OperationalError
        print(json.dumps({'status': 'audit_unavailable', 'error_type': type(e).__name__}))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get('status') == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
