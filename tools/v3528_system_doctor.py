# -*- coding: utf-8 -*-
"""V3.5.28: safe CLI summary for module catalog + source health (opt-in DB)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.system_health_v3528 import system_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description='Salt-okunur sistem sağlığı ve modül haritası')
    parser.add_argument('--db', type=Path, help='Optional, explicitly selected SQLite path (schema only)')
    parser.add_argument('--output', type=Path, help='Write no-PII JSON only to an explicit destination')
    args = parser.parse_args(argv)
    snapshot = system_snapshot(ROOT, db_path=args.db)
    message = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(message + '\n', encoding='utf8')
    print(message)
    return 0 if snapshot['source_state'] == 'SOURCE_READY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
