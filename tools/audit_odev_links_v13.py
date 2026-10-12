# -*- coding: utf-8 -*-
"""V13 salt okunur ödev bağlantı denetimi; hiçbir kayıt değiştirilmez."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sqlite3


def audit_connection(con: sqlite3.Connection) -> dict:
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    needed = {'odev', 'odev_satir', 'odev_kume', 'ogrenci'}
    if not needed <= tables:
        raise ValueError('Eksik tablolar: ' + ', '.join(sorted(needed - tables)))
    columns = {r[1] for r in con.execute('PRAGMA table_info(odev_satir)')}
    if not {'id', 'odev_id', 'ogrenci_id', 'kume_id'} <= columns:
        raise ValueError('odev_satir sütunları beklenenden farklı.')
    q = lambda sql: [int(r[0]) for r in con.execute(sql)]
    result = {
      'read_only': True,
      'integrity': con.execute('PRAGMA quick_check').fetchone()[0],
      'counts': {name: con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
                 for name in sorted(needed)},
      'unlinked_rows': con.execute('SELECT COUNT(*) FROM odev_satir WHERE odev_id IS NULL').fetchone()[0],
      'orphan_links': q('''SELECT s.id FROM odev_satir s LEFT JOIN odev o ON o.id=s.odev_id
                           WHERE s.odev_id IS NOT NULL AND o.id IS NULL ORDER BY s.id'''),
      'cross_student_links': q('''SELECT s.id FROM odev_satir s JOIN odev o ON o.id=s.odev_id
                                 WHERE s.ogrenci_id IS NOT NULL AND s.ogrenci_id<>o.ogrenci_id ORDER BY s.id'''),
      'cross_group_links': q('''SELECT s.id FROM odev_satir s JOIN odev o ON o.id=s.odev_id
                               WHERE s.kume_id IS NOT NULL AND s.kume_id<>o.kume_id ORDER BY s.id'''),
      'missing_legacy_group': q('''SELECT o.id FROM odev o LEFT JOIN odev_kume k ON k.id=o.kume_id
                                   WHERE k.id IS NULL ORDER BY o.id'''),
    }
    result['needs_review'] = any(result[x] for x in
        ('orphan_links', 'cross_student_links', 'cross_group_links', 'missing_legacy_group'))
    result['note'] = ('Tabloların toplamları doğrudan eşit olmak zorunda değildir. '
                      'Hiçbir kayıt değiştirilmedi. Kimlikler manuel olarak incelenmelidir.')
    return result


def audit_path(path: str | Path) -> dict:
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('SQLite dosyası bulunamadı.')
    con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    try:
        con.execute('PRAGMA query_only=ON')
        return audit_connection(con)
    finally:
        con.close()


def main() -> None:
    p = argparse.ArgumentParser(description='Salt okunur V13 ödev denetimi')
    p.add_argument('database', help='SQLite veritabanı dosya yolu')
    print(json.dumps(audit_path(p.parse_args().database), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
