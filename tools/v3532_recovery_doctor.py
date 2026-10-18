# -*- coding: utf-8 -*-
"""Offline/opt-in V3.5.32 recovery proof. No live DB restore command exists."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.verified_recovery_v3532 import preview_restore, create_verified_backup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Veri silmeden güvenli SQLite kurtarma provası")
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("preview", help="Yedeği izole ortamda dene; etkin veritabanına dokunma")
    check.add_argument("backup")
    create = sub.add_parser("create", help="Açık istekle online SQLite görüntüsü oluştur")
    create.add_argument("source")
    create.add_argument("destination")
    create.add_argument("--raw", action="store_true", help="GZIP yerine doğrudan SQLite veritabanı")
    args = parser.parse_args(argv)
    if args.action == "preview":
        result = preview_restore(args.backup)
    else:
        result = create_verified_backup(args.source, args.destination, compress=not args.raw)
    # Avoid printing paths or personal data even for successful backups.
    public = {k: v for k, v in result.items() if k not in ("archive_path", "manifest_path")}
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0 if result["status"] in ("REHEARSAL_PASSED", "BACKUP_CREATED_AND_REHEARSED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
