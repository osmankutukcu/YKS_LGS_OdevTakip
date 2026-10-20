import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from services.student_load_index_benchmark_v3580 import (
    benchmark_backup_path, compare_in_memory, synthetic_benchmark)


class StudentLoadIndexBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'copy_with_private_content.db'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE odev (ogrenci_id INTEGER, ders TEXT, konu_id INTEGER, kitap_ad TEXT, durum TEXT)')
            db.executemany('INSERT INTO odev VALUES (?,?,?,?,?)', [
                (i % 3 + 1, 'TEST_SECRET_TOPIC', i, 'PRIVATE_BOOK_X', 'tamam')
                for i in range(75)
            ])
        self.raw = self.path.read_bytes()

    def test_backup_source_unchanged(self):
        result = benchmark_backup_path(self.path, repeats=2)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['rows_equivalent'])
        self.assertFalse(result['source_changed'])
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_results_contain_no_private_data(self):
        result = benchmark_backup_path(self.path, repeats=1)
        serial = json.dumps(result)
        for secret in ('TEST_SECRET_TOPIC', 'PRIVATE_BOOK_X', str(self.path)):
            self.assertNotIn(secret, serial)
        self.assertEqual(result['student_samples_checked'], 3)

    def test_memory_limit_blocks_clone_and_untouched(self):
        result = benchmark_backup_path(self.path, max_copy_bytes=1)
        self.assertEqual(result['status'], 'memory_limit_exceeded')
        self.assertTrue(result['no_copy_created'])
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_readonly_missing_file_no_creation(self):
        missing = Path(self.tmp.name) / 'nope.db'
        with self.assertRaises(FileNotFoundError):
            benchmark_backup_path(missing)
        self.assertFalse(missing.exists())

    def test_tiny_data_no_migration_recommendation(self):
        result = benchmark_backup_path(self.path, repeats=1)
        self.assertEqual(result['recommendation'], 'small_dataset_no_action_without_windows_evidence')

    def test_existing_index_remains_unchanged(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE INDEX existing_odev_index ON odev(ogrenci_id)')
        snapshot = self.path.read_bytes()
        result = benchmark_backup_path(self.path, repeats=1)
        self.assertTrue(result['existing_student_index'])
        self.assertEqual(result['recommendation'], 'existing_student_index_present_no_migration_needed')
        self.assertEqual(self.path.read_bytes(), snapshot)

    def test_empty_table_no_fake_result(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE odev (ogrenci_id INTEGER, ders TEXT, konu_id INTEGER, kitap_ad TEXT, durum TEXT)')
            result = compare_in_memory(db, repeats=1)
            self.assertEqual(result['status'], 'no_student_sample')

    def test_missing_schema_no_index_creation(self):
        with sqlite3.connect(':memory:') as db:
            result = compare_in_memory(db)
            self.assertEqual(result['status'], 'missing_homework_table')

    def test_refuses_direct_disk_connection(self):
        with sqlite3.connect(self.path) as disk:
            with self.assertRaises(ValueError):
                compare_in_memory(disk, repeats=1)
        self.assertEqual(self.path.read_bytes(), self.raw)

    def test_invalid_repeats(self):
        with self.assertRaises(ValueError):
            synthetic_benchmark(repeats=0)

    def test_synthetic(self):
        result = synthetic_benchmark(row_count=500, students=10, repeats=1)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['synthetic_data'])
        self.assertTrue(result['rows_equivalent'])

    def test_cli(self):
        root = Path(__file__).resolve().parents[1]
        process = subprocess.run([sys.executable, '-m', 'tools.student_load_index_benchmark_v3580',
                                  '--database', str(self.path), '--repeats', '1'],
                                 cwd=root, text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['status'], 'ok')
        self.assertNotIn(str(self.path), process.stdout)

    def test_cli_error_sanitized(self):
        root = Path(__file__).resolve().parents[1]
        process = subprocess.run([sys.executable, '-m', 'tools.student_load_index_benchmark_v3580',
                                  '--database', str(self.path) + '_missing'],
                                 cwd=root, text=True, capture_output=True)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(json.loads(process.stdout)['error_type'], 'FileNotFoundError')
        self.assertNotIn(str(self.path), process.stdout)


if __name__ == '__main__':
    unittest.main()
