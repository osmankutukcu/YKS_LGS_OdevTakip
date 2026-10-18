"""V3.5.31 system health CLI. Aggregates ONLY health codes; never writes files.

Example: python -m tools.v3531_health_doctor --db /path/to/your.sqlite
This is for technical reviewers, not a required teacher workflow.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from services.system_health_v3531 import observe_local_health


def main(argv=None):
    p = argparse.ArgumentParser(description='Read-only scoped technical health observation')
    p.add_argument('--db', required=True, help='Local SQLite file to inspect')
    p.add_argument('--backup-dir', default=None, help='Optional explicit backup folder')
    p.add_argument('--source-root', default=None, help='Optional source tree catalog check')
    args = p.parse_args(argv)
    summary = observe_local_health(Path(args.db), backup_dir=args.backup_dir,
                                   project_root=args.source_root)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 2 if summary['state'] == 'REVIEW' else 0


if __name__ == '__main__':
    raise SystemExit(main())
