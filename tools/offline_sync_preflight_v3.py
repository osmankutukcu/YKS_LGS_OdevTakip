# -*- coding: utf-8 -*-
"""Read-only SQLite preflight for mobile sync. Only --backup creates a separate new file.

Examples:
  python tools/offline_sync_preflight_v3.py --db "C:/.../YKS_LGS_HomeworkManager.db"
  python tools/offline_sync_preflight_v3.py --db "C:/.../YKS_LGS_HomeworkManager.db" --backup "D:/Yedekler"

Never issues UPDATE/DELETE/ALTER on the desktop database.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def inspect(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f'Veritabanı bulunamadı: {path}')
    uri = path.resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True, timeout=30) as db:
        db.execute('PRAGMA query_only=ON')
        integrity = db.execute('PRAGMA quick_check').fetchone()[0]
        existing = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {'ogrenci', 'odev', 'odev_satir', 'odev_kume', 'kitap'}
        foreign_issues = db.execute('PRAGMA foreign_key_check').fetchall()
        report = {'path': str(path.resolve()), 'integrity': integrity,
                  'required_tables_present': sorted(required & existing),
                  'missing_tables': sorted(required - existing),
                  'foreign_key_issues': len(foreign_issues),
                  'safe_for_sync_pilot': integrity == 'ok' and not(required - existing) and len(foreign_issues)==0}
        # Existing data may have legacy FK anomalies; do not automatically fix them.
        if 'odev' in existing and 'odev_satir' in existing:
            from services.homework_integrity_v135 import audit_database
            audit = audit_database(db)
            report['homework_integrity_findings'] = [
                {'code': x.code, 'severity': x.severity, 'count': x.count}
                for x in audit.findings
            ]
            report['safe_for_sync_pilot'] &= not any(x.severity == 'critical' for x in audit.findings)
    return report


def backup(path: Path, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f'YKS_LGS_pre_v3_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sqlite'
    if destination.exists():
        raise FileExistsError(f'Yedek zaten mevcut: {destination}')
    src_uri = path.resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(src_uri, uri=True, timeout=30) as src:
        with sqlite3.connect(str(destination), timeout=30) as dst:
            src.backup(dst)
    with sqlite3.connect(destination) as check:
        if check.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            destination.unlink(missing_ok=True)
            raise RuntimeError('Yedek doğrulanamadı; kurulum yapmayın')
    return destination


def main():
    parser = argparse.ArgumentParser(description='V3 çevrimdışı eşitleme, salt okunur masaüstü DB kontrolü')
    parser.add_argument('--db', required=True, help='Aktif SQLite dosyasının TAM yolu')
    parser.add_argument('--backup', default=None, help='Opsiyonel: yeni yedek oluşturulacak klasör')
    args = parser.parse_args()
    path = Path(args.db).expanduser()
    report = inspect(path)
    if args.backup and report['safe_for_sync_pilot']:
        report['backup_path'] = str(backup(path, Path(args.backup).expanduser()))
    elif args.backup:
        report['backup_path'] = None
        report['warning'] = 'Kritik kontrol başarısız; yedekleme ve pilot kurulumu durduruldu'
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report['safe_for_sync_pilot']:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
