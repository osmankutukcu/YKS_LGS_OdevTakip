"""Run V3580 SQLite index comparison on synthetic data or an explicit TEST COPY.

Never runs during normal application startup. No SQL modifications to input DB.
Does not expose record contents, identifiers or file paths.
"""
from __future__ import annotations

import argparse
import json
from services.student_load_index_benchmark_v3580 import benchmark_backup_path, synthetic_benchmark


def main(argv=None):
    parser = argparse.ArgumentParser(description='KoçPilot: disposable in-memory index benchmark')
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--synthetic', action='store_true', help='Generate disposable synthetic data')
    target.add_argument('--database', help='Path to an offline BACKUP/TEST SQLite file (never changed)')
    parser.add_argument('--repeats', type=int, default=12)
    args = parser.parse_args(argv)
    try:
        result = (synthetic_benchmark(repeats=args.repeats) if args.synthetic
                  else benchmark_backup_path(args.database, repeats=args.repeats))
    except Exception as exc:
        # Do not leak paths or student rows through exception text.
        result = {'status': 'benchmark_unavailable', 'error_type': type(exc).__name__,
                  'source_changed': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('status') == 'ok' else 2


if __name__ == '__main__':
    raise SystemExit(main())
