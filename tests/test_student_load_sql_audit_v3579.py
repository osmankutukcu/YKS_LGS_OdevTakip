import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from services.student_load_sql_audit_v3579 import audit_connection, audit_database_path


class StudentLoadSQLAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'test_student_data.db'
        with sqlite3.connect(self.db) as con:
            con.execute('CREATE TABLE odev (ogrenci_id INTEGER, ders TEXT, konu_id INTEGER, kitap_ad TEXT, durum TEXT)')
            con.executemany('INSERT INTO odev VALUES (?,?,?,?,?)', [
                (1, 'fizik', 1, 'KITAP_XYZ', 'devam'),
                (2, 'matematik', 4, 'DERS_123', 'tamam'),
            ])
        self.raw_data = self.db.read_bytes()

    def test_read_only_aggregate_and_no_private_fields(self):
        result = audit_database_path(self.db)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['read_only'])
        self.assertEqual(result['homework_row_count'], 2)
        serialized = json.dumps(result)
        self.assertNotIn('KITAP_XYZ', serialized)
        self.assertNotIn('DERS_123', serialized)
        self.assertNotIn(str(self.db), serialized)
        self.assertEqual(self.db.read_bytes(), self.raw_data)

    def test_missing_index_detected(self):
        result = audit_database_path(self.db)
        self.assertFalse(result['has_student_prefix_index'])

    def test_index_is_detected_without_mutation(self):
        with sqlite3.connect(self.db) as con:
            con.execute('CREATE INDEX idx_test_odev_student ON odev(ogrenci_id, ders)')
        original_bytes = self.db.read_bytes()
        result = audit_database_path(self.db)
        self.assertTrue(result['has_student_prefix_index'])
        self.assertTrue(result['query_plan_search'])
        self.assertEqual(self.db.read_bytes(), original_bytes)

    def test_other_column_index_not_mistaken_for_student_index(self):
        with sqlite3.connect(self.db) as con:
            con.execute('CREATE INDEX idx_test_lesson ON odev(ders, ogrenci_id)')
        result = audit_database_path(self.db)
        self.assertFalse(result['has_student_prefix_index'])

    def test_empty_missing_table_is_handled(self):
        conn = sqlite3.connect(':memory:')
        try:
            result = audit_connection(conn)
            self.assertEqual(result['status'], 'missing_homework_table')
            self.assertTrue(result['read_only'])
        finally:
            conn.close()

    def test_readonly_pragma_rejects_writes(self):
        con = sqlite3.connect(self.db)
        try:
            audit_connection(con)
            with self.assertRaises(sqlite3.OperationalError):
                con.execute('DELETE FROM odev')
        finally:
            con.close()
        self.assertEqual(self.db.read_bytes(), self.raw_data)

    def test_cli_returns_json_without_sensitive_details(self):
        r = subprocess.run([sys.executable, '-m', 'tools.student_load_sql_audit_v3579', '--database', str(self.db)],
                           cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['status'], 'ok')
        self.assertNotIn(str(self.db), r.stdout)

    def test_cli_missing_file_does_not_create_db(self):
        missing = Path(self.tmp.name) / 'missing.db'
        r = subprocess.run([sys.executable, '-m', 'tools.student_load_sql_audit_v3579', '--database', str(missing)],
                           cwd=str(Path(__file__).resolve().parents[1]), capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(missing.exists())


if __name__ == '__main__': unittest.main()
