# -*- coding: utf-8 -*-
"""V3.5.29 regressions: synthetic data, no Qt/Windows or real student records."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.proactive_integrity_v3529 import read_integrity_overview
from services.proactive_academic_v3529 import read_academic_next_step
from services.teacher_copilot_v5 import read_teacher_feed
from tools.v3527_core_guard import audit
from tests.test_coach_evidence_v5 import make_db

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 18)


def integrity_database(path):
    with sqlite3.connect(path) as con:
        con.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,odev_id INTEGER);
        INSERT INTO ogrenci VALUES(1),(2);
        INSERT INTO odev_kume VALUES (10,1);
        INSERT INTO odev VALUES (20,1,10);
        INSERT INTO odev_satir VALUES (30,1,10,20);
        ''')


class AcademicSignalTests(unittest.TestCase):
    def setUp(self):
        self.con = make_db()
    def tearDown(self):
        self.con.close()
    def test_student_identity_is_strict(self):
        for sid in (None, 0, -1, '1', True):
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                read_academic_next_step(self.con, sid, today=TODAY)
    def test_missing_work_is_not_misdiagnosed(self):
        self.assertIsNone(read_academic_next_step(self.con, 1, today=TODAY))
    def test_read_only_overdue_with_explicit_teacher_approval(self):
        self.con.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,kitap,durum) VALUES(1,1,'Fizik','İvme','A','devam')")
        before = self.con.total_changes
        x = read_academic_next_step(self.con, 1, today=TODAY)
        self.assertEqual(x['student_id'], 1)
        self.assertEqual(x['kind'], 'overdue')
        self.assertIn('Fizik', x['next_step'])
        self.assertTrue(x['requires_approval'])
        self.assertTrue(x['not_mastery_diagnosis'])
        self.assertEqual(self.con.total_changes, before)
        self.assertIsNone(read_academic_next_step(self.con, 2, today=TODAY))
    def test_wrong_group_owner_suppresses_academic_recommendation(self):
        self.con.execute('ALTER TABLE odev_kume ADD COLUMN ogrenci_id INTEGER')
        self.con.execute('UPDATE odev_kume SET ogrenci_id=2 WHERE id=1')
        self.con.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,kitap,durum) VALUES(1,1,'Fizik','İvme','A','devam')")
        self.assertIsNone(read_academic_next_step(self.con, 1, today=TODAY))

    def test_linked_homework_wrong_student_suppresses_recommendation(self):
        self.con.execute("INSERT INTO odev VALUES(22,2,1,'Fizik','İvme','A','devam',NULL,NULL)")
        self.con.execute("INSERT INTO odev_satir(ogrenci_id,odev_id,kume_id,ders,konu,kitap,durum) VALUES(1,22,1,'Fizik','İvme','A','devam')")
        self.assertIsNone(read_academic_next_step(self.con, 1, today=TODAY))

    def test_missing_group_link_suppresses_recommendation(self):
        self.con.execute('ALTER TABLE odev_kume ADD COLUMN ogrenci_id INTEGER')
        self.con.execute('UPDATE odev_kume SET ogrenci_id=1 WHERE id=1')
        self.con.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,kitap,durum) VALUES(1,999,'Fizik','İvme','A','devam')")
        self.assertIsNone(read_academic_next_step(self.con, 1, today=TODAY))

    def test_missing_linked_homework_suppresses_recommendation(self):
        self.con.execute("INSERT INTO odev_satir(ogrenci_id,odev_id,kume_id,ders,konu,kitap,durum) VALUES(1,999,1,'Fizik','İvme','A','devam')")
        self.assertIsNone(read_academic_next_step(self.con, 1, today=TODAY))

    def test_comparable_exam_gets_review_not_mastery_diagnosis(self):
        self.con.executescript('''
          INSERT INTO denemeler VALUES(1,'2026-09-02'),(2,'2026-10-10');
          INSERT INTO deneme_sonuclari VALUES (1,1,1,'Matematik',13,2,12.5);
          INSERT INTO deneme_sonuclari VALUES (2,2,1,'Matematik',9,4,8.0);
        ''')
        x = read_academic_next_step(self.con, 1, today=TODAY)
        self.assertEqual(x['kind'], 'exam_follow_up')
        self.assertIn('kontrol', x['next_step'])
        self.assertTrue(x['requires_approval'])
        self.assertIsNone(read_academic_next_step(self.con, 2, today=TODAY))


class IntegrityWatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'synthetic.sqlite'
        integrity_database(self.db)
    def tearDown(self):
        self.tmp.cleanup()
    def test_ro_clean_scope_is_not_general_health_claim(self):
        before = self.db.read_bytes()
        data = read_integrity_overview(self.db)
        self.assertEqual(data['state'], 'NO_FINDINGS_IN_SCOPE')
        self.assertTrue(data['not_full_system_health'])
        self.assertTrue(data['read_only'])
        self.assertEqual(before, self.db.read_bytes())
    def test_cross_student_mismatch_is_not_dismissed_as_old_archive(self):
        with sqlite3.connect(self.db) as con:
            con.execute('UPDATE odev_satir SET ogrenci_id=2 WHERE id=30')
        before = self.db.read_bytes()
        data = read_integrity_overview(self.db)
        self.assertEqual(data['state'], 'REVIEW')
        self.assertGreater(data['urgent_count'], 0)
        self.assertIn('LINKED_HOMEWORK_STUDENT_MISMATCH', data['codes'])
        self.assertNotIn('30', str(data))  # No record IDs leave background audit.
        self.assertEqual(self.db.read_bytes(), before)
    def test_missing_database_does_not_create_it(self):
        path = self.db.with_name('missing.sqlite')
        self.assertEqual(read_integrity_overview(path)['state'], 'UNAVAILABLE')
        self.assertFalse(path.exists())
    def test_incomplete_schema_does_not_appear_healthy(self):
        with sqlite3.connect(self.db) as con:
            con.execute('DROP TABLE odev_satir')
        r = read_integrity_overview(self.db)
        self.assertEqual(r['state'], 'REVIEW')
        self.assertIn('MISSING_TABLE', r['codes'])
    def test_locked_database_timeout_not_green(self):
        with sqlite3.connect(self.db) as con:
            con.execute('BEGIN EXCLUSIVE')
            result = read_integrity_overview(self.db, time_budget_seconds=0.1)
            self.assertIn(result['state'], ('UNVERIFIED', 'REVIEW'))
            self.assertNotEqual(result['state'], 'NO_FINDINGS_IN_SCOPE')
            con.rollback()


class IntegrationContractTests(unittest.TestCase):
    def test_core_guard_unchanged(self):
        self.assertEqual(audit(ROOT)['status'], 'PASS')
    def test_gui_auto_updates_from_worker_no_extra_button_to_click(self):
        source = (ROOT/'ui/teacher_copilot_strip_v5.py').read_text('utf8')
        ast.parse(source)
        self.assertIn('time.monotonic() >= self._next_integrity_due', source)
        self.assertIn('args=(self._path, self._result_queue, due)', source)
        self.assertIn('self._present_integrity', source)
        self.assertIn("first.get('academic')", source)
        self.assertNotIn('btnRunSystemAudit', source)
    def test_integrity_dialog_no_false_guarantee(self):
        source = (ROOT/'ui/homework_integrity_dialog_v135.py').read_text('utf8')
        ast.parse(source)
        self.assertNotIn('Aktif öğrencilerinizin verilerini bozmaz.', source)
        self.assertNotIn('Tamamen Sağlam', source)
        self.assertIn('Etki alanı yalnızca bu raporla kesinleştirilemez.', source)
    def test_old_feed_keeps_contract_on_sparse_schema(self):
        from tests.test_teacher_copilot_v5 import CopilotV5Tests
        sample = CopilotV5Tests('test_missing_db_does_not_create_a_new_database')
        sample.setUp()
        try:
            card = read_teacher_feed(sample.db, today=date(2026, 10, 15), feedback_path=sample.feedback)
            self.assertEqual(len(card['cards']), 2)
            self.assertEqual(card['cards'][0]['student_id'], 1)
            self.assertIsNone(card['cards'][0]['academic'])
        finally:
            sample.tearDown()


if __name__ == '__main__':
    unittest.main()
