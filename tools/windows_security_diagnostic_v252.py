#!/usr/bin/env python3
"""Local-only Windows self-check. No WhatsApp accounts, API, internet, or user DB.

Examples:
  py tools\\windows_security_diagnostic_v252.py
  py tools\\windows_security_diagnostic_v252.py --inspect-legacy "X:\\queue.sqlite3"
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.whatsapp_queue.readiness_v252 import (
    windows_offline_readiness, inspect_legacy_counts,
)

def main(argv=None):
    cli=argparse.ArgumentParser(description='V25.2 çevrimdışı Windows güvenlik ön testi')
    cli.add_argument('--inspect-legacy', default=None,
                     help='Yalnızca belirtilen eski kuyruğun durum sayılarını oku; telefon/metin alma')
    args=cli.parse_args(argv)
    report=windows_offline_readiness()
    if args.inspect_legacy is not None:
        report['legacy_queue'] = inspect_legacy_counts(args.inspect_legacy)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report['result'] == 'PASS_WINDOWS_SYNTHETIC_TEST' else 2

if __name__=='__main__':raise SystemExit(main())
