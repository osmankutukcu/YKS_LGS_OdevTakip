"""V3.5.31 health center synthetic regression. No real student data, Qt or network."""
from __future__ import annotations

import ast
from contextlib import closing
from pathlib import Path
import gzip
import sqlite3
import tempfile
import time
import unittest

from services.system_health_v3531 import check_database, check_backup, observe_local_health
from tools.v3527_core_guard import audit

ROOT=Path(__file__).resolve().parents[1]

class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        self.db=self.dir/'test.db'
        with closing(sqlite3.connect(self.db)) as con:
            con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, isim TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY, student INTEGER);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY);
            INSERT INTO ogrenci VALUES(1, 'student X');
            ''')
        self.backup_dir=self.dir/'backups'
        self.backup_dir.mkdir()

    def test_read_only_probe_never_exposes_identity(self):
        before=self.db.read_bytes()
        result=observe_local_health(self.db)
        self.assertEqual(result['database']['state'],'LOCAL_DB_CHECKS_OK')
        self.assertEqual(before,self.db.read_bytes())
        self.assertNotIn('student X',str(result))
        self.assertNotIn(str(self.db),str(result))
        self.assertFalse(result['network_sync_verified'])
        self.assertFalse(result['backup_restore_tested'])
        self.assertFalse(result['automatic_repair'])
        self.assertNotEqual(result['state'], 'FULLY_HEALTHY')

    def test_missing_file_not_created(self):
        missing=self.dir/'missing.db'
        self.assertEqual(check_database(missing)['state'],'DB_NOT_FOUND')
        self.assertFalse(missing.exists())

    def test_broken_schema_warns(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('DROP TABLE odev_kume')
            con.commit()
        x=observe_local_health(self.db)
        self.assertEqual(x['database']['state'],'SCHEMA_INCOMPLETE')
        self.assertEqual(x['state'],'REVIEW')
        self.assertEqual(x['issues'][0]['area'],'database')

    def test_locked_db_never_claims_all_clear(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('BEGIN EXCLUSIVE')
            result=check_database(self.db,seconds=0.1)
            self.assertNotEqual(result['state'],'LOCAL_DB_CHECKS_OK')
            con.rollback()

    def test_sql_dump_disguised_as_sqlite_gzip_warning(self):
        p=self.backup_dir/'test_2026.db.gz'
        with gzip.open(p,'wb') as f:
            f.write(b'BEGIN TRANSACTION;\nCREATE TABLE x(a);\nCOMMIT;')
        before=p.read_bytes()
        x=check_backup(self.db)
        self.assertEqual(x['state'],'BACKUP_SQL_DUMP_MISLABELED')
        self.assertFalse(x['recovery_tested'])
        self.assertEqual(before,p.read_bytes())

    def test_sql_dump_plain_db_warning(self):
        p=self.backup_dir/'test.db'
        p.write_bytes(b'BEGIN TRANSACTION;\nCREATE TABLE x(a);\nCOMMIT;')
        self.assertEqual(check_backup(self.db)['state'],'BACKUP_SQL_DUMP_MISLABELED')

    def test_valid_sqlite_header_is_not_recovery_guarantee(self):
        p=self.backup_dir/'test_2026.db'
        p.write_bytes(self.db.read_bytes())
        x=check_backup(self.db)
        self.assertEqual(x['state'],'BACKUP_HEADER_PRESENT_ONLY')
        self.assertFalse(x['recovery_tested'])
        self.assertEqual(observe_local_health(self.db)['state'],'SCOPED_OBSERVATION')

    def test_gz_sqlite_header_cannot_restore_via_existing_ui(self):
        p=self.backup_dir/'test_2026.db.gz'
        with gzip.open(p,'wb') as f:f.write(self.db.read_bytes())
        x=check_backup(self.db)
        self.assertEqual(x['state'],'GZIP_BACKUP_RESTORE_NOT_SUPPORTED_BY_UI')

    def test_stale_snapshot(self):
        p=self.backup_dir/'test_2026.db'
        p.write_bytes(self.db.read_bytes())
        now=time.time()
        import os
        os.utime(p,(now-9*86400,now-9*86400))
        self.assertEqual(check_backup(self.db,now_timestamp=now)['state'],'OBSERVED_BACKUP_STALE')

    def test_missing_directory_is_unknown_not_backup_absent_everywhere(self):
        x=check_backup(self.db, backup_dir=self.dir/'another')
        self.assertEqual(x['state'],'NO_BACKUPS_IN_OBSERVED_DIR')
        self.assertNotEqual(x['level'],'ok')
        self.assertFalse((self.dir/'another').exists())

    def test_corrupt_compressed_archive(self):
        p=self.backup_dir/'corrupt.db.gz'
        p.write_bytes(b'bad gzip bytes')
        self.assertEqual(check_backup(self.db)['state'],'BACKUP_FORMAT_UNVERIFIED')

    def test_read_access_of_backup_only_header(self):
        p=self.backup_dir/'backup.db'
        p.write_bytes(b'SQLite format 3\0'+b'garbage')
        self.assertEqual(check_backup(self.db)['state'],'BACKUP_HEADER_PRESENT_ONLY')
        self.assertFalse(check_backup(self.db)['recovery_tested'])

    def test_optional_source_catalog_is_not_runtime_proof(self):
        report=observe_local_health(self.db, project_root=ROOT)
        self.assertEqual(report['module_sources']['catalog_count'],15)
        self.assertFalse(report['module_sources']['runtime_tested'])
        self.assertNotIn(str(ROOT),str(report))

    def test_unknown_database_health_is_never_green(self):
        with closing(sqlite3.connect(self.db)) as con:
            con.execute('BEGIN EXCLUSIVE')
            observation=observe_local_health(self.db)
            self.assertEqual(observation['state'],'UNVERIFIED')
            con.rollback()

    def test_existing_forms_byte_guard(self):
        x=audit(ROOT)
        self.assertEqual(x['status'],'PASS',x.get('errors'))

    def test_ui_uses_existing_timed_worker_no_new_click(self):
        text=(ROOT/'ui/teacher_copilot_strip_v5.py').read_text('utf8')
        ast.parse(text)
        self.assertIn("args=(self._path, self._result_queue, due)",text)
        self.assertIn("result['health'] = observe_local_health(path)",text)
        self.assertIn("self._present_health(result['health'])",text)
        self.assertIn('self.health_notice.setVisible(False)',text)
        self.assertNotIn('btnRunSystemHealth',text)

if __name__=='__main__':unittest.main()
