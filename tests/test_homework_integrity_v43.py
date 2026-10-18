# -*- coding: utf-8 -*-
from __future__ import annotations
"""V43: isolated synthetic SQLite behavior; no Qt or production student data."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.homework_integrity_v43 import audit_backup, digest
from tools.v43_pilot_preflight import preflight

ROOT = Path(__file__).resolve().parents[1]


class HomeworkPilotIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.db = Path(self.td.name) / 'independent_pilot_snapshot.db'
        with sqlite3.connect(self.db) as c:
            c.executescript('''
                CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,alt_grup TEXT);
                CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER);
                CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,durum TEXT);
                CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,odev_id INTEGER,durum TEXT);
                INSERT INTO ogrenci VALUES(1,'NOT_FOR_REPORT','A'), (2,'NOT_FOR_REPORT_2','B');
                INSERT INTO odev_kume VALUES(11,1), (22,2);
                INSERT INTO odev VALUES(101,1,11,'devam'), (202,2,22,'yapildi');
                INSERT INTO odev_satir VALUES(1001,1,11,101,'devam'), (2002,2,22,202,'tamam');
            ''')

    def runaudit(self):
        return audit_backup(self.db, acknowledged_backup=True)

    def test_synthetic_two_students_all_links_pass(self):
        before = digest(self.db)
        result = self.runaudit()
        self.assertEqual(result['database_test'], 'PASS')
        self.assertTrue(result['source_unchanged'])
        self.assertEqual(result['sqlite_integrity'], 'PASS')
        self.assertEqual(result['foreign_key_violations'], 0)
        self.assertTrue(all(v == 0 for v in result['link_checks'].values()))
        self.assertEqual(before, digest(self.db))

    def test_only_counts_no_private_info(self):
        result = self.runaudit()
        public = json.dumps(result, ensure_ascii=False)
        self.assertNotIn('NOT_FOR_REPORT', public)
        self.assertNotIn(str(self.db), public)
        self.assertEqual(result['counts']['odev'], 2)
        self.assertEqual(result['contains_personal_student_details'], False)

    def test_student_cross_link_is_blocker_without_repair(self):
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE odev_satir SET ogrenci_id=2 WHERE id=1001')
        before = digest(self.db)
        result = self.runaudit()
        self.assertEqual(result['database_test'], 'BLOCK')
        self.assertEqual(result['link_checks']['line_wrong_homework_student'], 1)
        self.assertEqual(result['link_checks']['line_wrong_cluster_student'], 1)
        self.assertEqual(before, digest(self.db))

    def test_wrong_header_cluster_link_is_blocker(self):
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE odev SET kume_id=22 WHERE id=101')
        result = self.runaudit()
        self.assertEqual(result['database_test'], 'BLOCK')
        self.assertEqual(result['link_checks']['homework_wrong_cluster_student'], 1)
        self.assertEqual(result['link_checks']['line_wrong_homework_cluster'], 1)

    def test_legacy_unlinked_rows_are_review_not_deleted(self):
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE odev_satir SET odev_id=NULL WHERE id=1001')
        result = self.runaudit()
        self.assertEqual(result['database_test'], 'REVIEW')
        self.assertEqual(result['link_checks']['legacy_unlinked_lines'], 1)
        with sqlite3.connect(self.db) as c:
            self.assertIsNone(c.execute('SELECT odev_id FROM odev_satir WHERE id=1001').fetchone()[0])

    def test_broken_reference_requires_review_not_auto_link(self):
        with sqlite3.connect(self.db) as c:
            c.execute('UPDATE odev_satir SET odev_id=999 WHERE id=1001')
        self.assertEqual(self.runaudit()['link_checks']['line_broken_homework_link'], 1)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT odev_id FROM odev_satir WHERE id=1001').fetchone()[0], 999)

    def test_schema_missing_required_link_column_blocks(self):
        with sqlite3.connect(self.db) as c:
            c.execute('ALTER TABLE odev_satir DROP COLUMN odev_id')
        result = self.runaudit()
        self.assertEqual(result['database_test'], 'BLOCK')
        self.assertEqual(result['findings'][0]['code'], 'UNSUPPORTED_SCHEMA')

    def test_database_not_read_without_explicit_backup_ack(self):
        with self.assertRaisesRegex(ValueError, 'backup-ack'):
            audit_backup(self.db)

    def test_database_rejected_if_sidecar_present(self):
        sidecar = Path(str(self.db) + '-wal')
        sidecar.write_bytes(b'pending transaction')
        try:
            with self.assertRaisesRegex(ValueError, 'WAL/SHM'):
                self.runaudit()
        finally:
            sidecar.unlink()

    def test_missing_file_not_created(self):
        db = Path(self.td.name) / 'never_created.db'
        with self.assertRaises(ValueError):
            audit_backup(db, acknowledged_backup=True)
        self.assertFalse(db.exists())

    def test_sqlite_invalid_file_rejected(self):
        self.db.write_bytes(b'X'*200)
        with self.assertRaisesRegex(ValueError, 'SQLite'):
            self.runaudit()

    def test_backup_and_source_guard_no_ui_approval(self):
        report = preflight(ROOT, db=self.db, backup_ack=True)
        self.assertEqual(report['protected_sources']['status'], 'PASS')
        self.assertFalse(report['release_ready'])
        self.assertEqual(report['gui_windows'], 'NOT_TESTED')
        self.assertEqual(report['gui_mac'], 'NOT_TESTED')
        self.assertEqual(report['manual_acceptance'], 'PENDING')

    def test_source_hash_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            from shutil import copytree
            root = Path(tmp)/'src'
            # Only files used by source_integrity check are required.
            baseline = json.loads((ROOT/'tests/v42_protected_hashes.json').read_text())
            (root/'tests').mkdir(parents=True)
            (root/'tests/v42_protected_hashes.json').write_text(json.dumps(baseline))
            for name in baseline:
                file = root/name
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_bytes((ROOT/name).read_bytes())
            target = root/'ui/homework_form.py'
            target.write_bytes(target.read_bytes()+b'\n# modified core must block\n')
            result = preflight(root)
            self.assertEqual(result['protected_sources']['status'], 'BLOCK')
            self.assertFalse(result['release_ready'])


if __name__ == '__main__':
    unittest.main()
