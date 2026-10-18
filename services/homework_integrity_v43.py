# -*- coding: utf-8 -*-
"""V43: Salt okunur, kişisel veri çıkarmayan ödev bütünlüğü kontrolü.

Canlı veritabanı üzerinde işlem yapmaz. Yalnızca KAPALI uygulamadan alınmış
ayrı bir yedek üzerinde çalıştırılmalıdır. Orijinal dosyaya dokunmaz.
"""
from __future__ import annotations
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3

REQUIRED = {
    'ogrenci': {'id'},
    'odev_kume': {'id', 'ogrenci_id'},
    'odev': {'id', 'ogrenci_id', 'kume_id'},
    'odev_satir': {'id', 'ogrenci_id', 'kume_id', 'odev_id'},
}
OPTIONAL_COUNTS = ('odev_takip', 'kapsam_odev_v233', 'ogrenci_kitap', 'koc_konu_takip')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _connection(path: Path):
    # sqlite uri mode=ro + query_only, no table creation / migration / write.
    c = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    c.execute('PRAGMA query_only=ON')
    return c


def _count(con, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def audit_backup(path: Path, *, acknowledged_backup: bool = False) -> dict:
    """Report COUNTS only; never output names, phones, notes or row identifiers.

    Fail closed if a WAL/SHM sidecar exists, because a live file may not contain
    all committed data. Requires explicit backup acknowledgement.
    """
    path = Path(path)
    if not acknowledged_backup:
        raise ValueError('Yalnızca ayrı veritabanı yedeği: --backup-ack gerekli.')
    if not path.is_file() or path.is_symlink() or path.stat().st_size < 100:
        raise ValueError('Geçerli normal SQLite yedek dosyası yok.')
    if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('WAL/SHM/journal var: uygulamayı kapatıp tutarlı yedek oluşturun.')
    with path.open('rb') as f:
        if f.read(16) != b'SQLite format 3\x00':
            raise ValueError('Dosya SQLite biçiminde değil.')
    before = digest(path)
    result = {
        'database_test': 'NOT_VERIFIED',
        'counts': {}, 'link_checks': {}, 'findings': [],
        'contains_personal_student_details': False,
        'automatic_repairs': False,
        'source_unchanged': False,
    }
    with closing(_connection(path)) as con:
        integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
        result['sqlite_integrity'] = 'PASS' if integrity == 'ok' else 'FAIL'
        if integrity != 'ok':
            result['findings'].append({'severity': 'BLOCK', 'code': 'SQLITE_INTEGRITY'})
            result['database_test'] = 'BLOCK'
            result['source_unchanged'] = before == digest(path)
            return result
        tables = {str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = []
        for name, fields in REQUIRED.items():
            if name not in tables:
                missing.append(name)
                continue
            columns = {str(row[1]) for row in con.execute(f'PRAGMA table_info("{name}")')}
            if not fields.issubset(columns):
                missing.append(name + ':columns')
        if missing:
            result['findings'].append({'severity': 'BLOCK', 'code': 'UNSUPPORTED_SCHEMA', 'items': sorted(missing)})
            result['database_test'] = 'BLOCK'
        else:
            for name in (*REQUIRED, *OPTIONAL_COUNTS):
                if name in tables:
                    result['counts'][name] = _count(con, f'SELECT COUNT(*) FROM "{name}"')
            checks = {
                'cluster_missing_student': 'SELECT COUNT(*) FROM odev_kume k LEFT JOIN ogrenci s ON s.id=k.ogrenci_id WHERE s.id IS NULL',
                'homework_missing_student': 'SELECT COUNT(*) FROM odev h LEFT JOIN ogrenci s ON s.id=h.ogrenci_id WHERE s.id IS NULL',
                'line_missing_student': 'SELECT COUNT(*) FROM odev_satir l LEFT JOIN ogrenci s ON s.id=l.ogrenci_id WHERE s.id IS NULL',
                'homework_missing_cluster': 'SELECT COUNT(*) FROM odev h LEFT JOIN odev_kume k ON k.id=h.kume_id WHERE h.kume_id IS NOT NULL AND k.id IS NULL',
                'homework_wrong_cluster_student': 'SELECT COUNT(*) FROM odev h JOIN odev_kume k ON k.id=h.kume_id WHERE h.ogrenci_id != k.ogrenci_id',
                'line_missing_cluster': 'SELECT COUNT(*) FROM odev_satir l LEFT JOIN odev_kume k ON k.id=l.kume_id WHERE l.kume_id IS NOT NULL AND k.id IS NULL',
                'line_wrong_cluster_student': 'SELECT COUNT(*) FROM odev_satir l JOIN odev_kume k ON k.id=l.kume_id WHERE l.ogrenci_id != k.ogrenci_id',
                'line_wrong_homework_student': 'SELECT COUNT(*) FROM odev_satir l JOIN odev h ON h.id=l.odev_id WHERE l.ogrenci_id != h.ogrenci_id',
                'line_wrong_homework_cluster': 'SELECT COUNT(*) FROM odev_satir l JOIN odev h ON h.id=l.odev_id WHERE l.kume_id IS NOT h.kume_id',
                'line_broken_homework_link': 'SELECT COUNT(*) FROM odev_satir l LEFT JOIN odev h ON h.id=l.odev_id WHERE l.odev_id IS NOT NULL AND h.id IS NULL',
                'legacy_unlinked_lines': 'SELECT COUNT(*) FROM odev_satir l WHERE l.odev_id IS NULL',
            }
            for opt in OPTIONAL_COUNTS:
                if opt in tables:
                    cols = {str(r[1]) for r in con.execute(f'PRAGMA table_info("{opt}")')}
                    if 'ogrenci_id' in cols:
                        checks['optional_' + opt + '_missing_student'] = (
                            f'SELECT COUNT(*) FROM "{opt}" a LEFT JOIN ogrenci s '
                            'ON s.id=a.ogrenci_id WHERE a.ogrenci_id IS NOT NULL AND s.id IS NULL'
                        )
            result['link_checks'] = {key: _count(con, query) for key, query in checks.items()}
            # Strict cross-student and missing record links stop deployment; older
            # standalone rows need manual review rather than automatic repair.
            blockers = set(checks) - {'line_broken_homework_link', 'legacy_unlinked_lines'}
            for key, count in result['link_checks'].items():
                if not count:
                    continue
                severity = 'BLOCK' if key in blockers else 'REVIEW'
                result['findings'].append({'severity': severity, 'code': key.upper(), 'count': count})
            result['database_test'] = ('BLOCK' if any(x['severity'] == 'BLOCK' for x in result['findings'])
                                       else 'REVIEW' if result['findings'] else 'PASS')
        # Foreign key violations, if relationships are actually declared.
        fk = con.execute('PRAGMA foreign_key_check').fetchall()
        result['foreign_key_violations'] = len(fk)
        if fk:
            result['findings'].append({'severity': 'BLOCK', 'code': 'FOREIGN_KEY_VIOLATIONS', 'count': len(fk)})
            result['database_test'] = 'BLOCK'
    after = digest(path)
    result['source_unchanged'] = before == after
    if not result['source_unchanged']:
        result['findings'].append({'severity': 'BLOCK', 'code': 'SOURCE_CHANGED_DURING_AUDIT'})
        result['database_test'] = 'BLOCK'
    return result
