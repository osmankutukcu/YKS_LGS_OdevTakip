from __future__ import annotations
from tools.v35_reviewed_source_contract import verify_legacy_handlers
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
from services.windows_perf_v32 import MethodStats, install_method_timing, inspect_query_plans, compare_header_stat_queries
from tools.v32_windows_profile import main as pilot_main


class WindowsPerfV32Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'sahte_ogrenciler_test.db'
        con = sqlite3.connect(self.path)
        con.executescript('''
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER NOT NULL);
            CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER NOT NULL,
                ogrenci_id INTEGER NOT NULL, ders TEXT, konu_ad TEXT, kitap_ad TEXT,
                durum TEXT, saat_dk INTEGER, silindi INTEGER DEFAULT 0, aktarildi INTEGER DEFAULT 0);
            CREATE INDEX idx_test_odev_kume ON odev(kume_id);
            INSERT INTO odev_kume(id,ogrenci_id) VALUES (10,1),(11,1),(20,2);
            INSERT INTO odev(id,kume_id,ogrenci_id,ders,konu_ad,kitap_ad,durum,saat_dk,silindi,aktarildi) VALUES
              (1,10,1,'fizik','Enerji','Kitap','yapildi',45,0,0),
              (2,10,1,'fizik','Basınç','Kitap','devam',60,0,0),
              (3,11,1,'fizik','Işık','Kitap','yapildi',40,1,1),
              (4,11,1,'kimya','Molekül','Kitap','tamam',35,0,1),
              (5,20,2,'fizik','Kuvvet','Kitap','yapildi',90,0,0);
        ''')
        con.commit()
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _hash(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_read_only_plan_and_no_pii(self):
        before = self._hash()
        result = inspect_query_plans(self.path)
        self.assertEqual(before, self._hash())
        self.assertTrue(result['schema_supported'])
        self.assertTrue(any('idx_test_odev_kume' in plan for plan in result['plans']['cluster_open']))
        self.assertNotIn('Enerji', str(result))
        self.assertEqual(result['mutations'], 0)

    def test_combined_sql_same_as_legacy_and_no_mutations(self):
        before = self._hash()
        for student in (1, 2, 999):
            result = compare_header_stat_queries(self.path, student, repeats=4)
            self.assertTrue(result['equivalent'], result)
            self.assertEqual(result['measurements_taken'], 4)
        self.assertEqual(before, self._hash())

    def test_old_schema_safe_fallback(self):
        p = Path(self.tmp.name)/'old.db'
        with sqlite3.connect(p) as con:
            con.executescript('CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER); CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER);')
        r = compare_header_stat_queries(p, 1)
        self.assertIsNone(r['equivalent'])
        self.assertEqual(r['mutations'],0)

    def test_instrumentation_keeps_method_semantics_and_never_logs_arguments(self):
        c = MethodStats()
        class Fake:
            def good(self, student_secret):
                return student_secret + 1
            def bad(self, student_secret):
                raise ValueError('expected')
        self.assertTrue(install_method_timing(Fake,'good',c))
        self.assertFalse(install_method_timing(Fake,'good',c))
        self.assertTrue(install_method_timing(Fake,'bad',c))
        self.assertEqual(Fake().good(987654321),987654322)
        with self.assertRaisesRegex(ValueError,'expected'):
            Fake().bad('a private name')
        report = c.report()
        self.assertEqual(report['methods']['Fake.bad']['exceptions'],1)
        self.assertNotIn('987654321',json.dumps(report))
        self.assertNotIn('private name',json.dumps(report))

    def test_inspection_cli_without_qt(self):
        from contextlib import redirect_stdout
        from io import StringIO
        buf = StringIO()
        with redirect_stdout(buf):
            self.assertEqual(pilot_main(['--database',str(self.path),'--inspect-only','--student-id','1']),0)
        obj = json.loads(buf.getvalue())
        self.assertEqual(obj['student_records_exported'],0)
        self.assertTrue(obj['optional_query_comparison']['equivalent'])

    def test_legacy_core_hash_still_unchanged(self):
        checks={
            'ui/homework_form.py':'827098c0628bccbac89fbcb37cdf9967467b8971e65457d1d484768c824ffb5b',
            'ui/odev_kontrol.py':'7ca39f447e4a7cd71cb4eb14fde9bba53fae6c183092d0758a77c8d009cd4d0c',
        }
        # Older maintenance tests provide authoritative source checksums.
        for rel, want in list(checks.items())[:2]:
            self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),want)

        verify_legacy_handlers(ROOT)

if __name__=='__main__':
    unittest.main()
