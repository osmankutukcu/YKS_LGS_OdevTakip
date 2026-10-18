# -*- coding: utf-8 -*-
"""V3.5.34 isolated data tests: no Windows/PyQt required."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from services.daily_coach_v10 import collect_student_facts, make_suggestions
from services.daily_brief_v11 import review_identity
from services.cohort_academic_advisor_v3534 import summarize_cohort
from services.teacher_copilot_v5 import read_teacher_feed
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 18)


def make_db():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT,
            dogum_tarihi TEXT, veli_tel1 TEXT, aktif INTEGER);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            verilis_tarihi TEXT, bitis_tarihi TEXT);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER,
            ders TEXT, durum TEXT);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            kume_id INTEGER, odev_id INTEGER, ders TEXT);
        INSERT INTO ogrenci VALUES(1,'Ayşe','Örnek',NULL,'05550001122',1);
        INSERT INTO ogrenci VALUES(2,'Can','Deneme',NULL,NULL,1);
        INSERT INTO ogrenci VALUES(3,'Ece','Model',NULL,NULL,1);
        INSERT INTO ogrenci VALUES(4,'Eski','Öğrenci',NULL,NULL,0);
        INSERT INTO odev_kume VALUES(11,1,'2026-10-01','2026-10-12');
        INSERT INTO odev_kume VALUES(12,3,'2026-10-12','2026-10-30');
        INSERT INTO odev VALUES(101,1,11,'Fizik','devam');
        INSERT INTO odev VALUES(102,3,12,'Kimya','tamam');
        CREATE TABLE koc_plan(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            baslangic_tarihi TEXT, bitis_tarihi TEXT, aktif INTEGER);
        INSERT INTO koc_plan VALUES(1,1,'2026-10-12','2026-10-18',1);
        INSERT INTO koc_plan VALUES(2,3,'2026-10-12','2026-10-18',1);
        CREATE TABLE coach_brief_review_v11(review_day TEXT, student_id INTEGER,
            suggestion_type TEXT, evidence_signature TEXT);
    ''')
    return con


def compute(con, *, reviewed=()):
    con.row_factory = sqlite3.Row
    facts = collect_student_facts(con, DAY)
    suggestions = make_suggestions(facts, DAY)
    return summarize_cohort(con, facts, suggestions, set(reviewed), today=DAY), suggestions


class CohortTests(unittest.TestCase):
    def setUp(self):
        self.con = make_db()

    def tearDown(self):
        self.con.close()

    def test_local_scope_overdue_and_plans(self):
        summary, _ = compute(self.con)
        self.assertEqual(summary['state'], 'OBSERVED')
        self.assertEqual((summary['active_students'], summary['evaluated_students']), (3, 3))
        self.assertEqual(summary['overdue_students'], 1)
        self.assertEqual(summary['recent_overdue_students'], 1)
        self.assertEqual(summary['no_assignment_history_students'], 1)
        self.assertEqual(summary['weekly_coaching_plan']['without_plan'], 1)
        self.assertEqual(summary['weekly_coaching_plan']['with_plan'], 2)
        self.assertEqual(summary['priority_cards'][0]['student_id'], 1)
        self.assertFalse(summary['remote_verified'])
        self.assertTrue(summary['no_automatic_write'])

    def test_no_personal_contact_exposed_to_summary(self):
        summary, _ = compute(self.con)
        self.assertNotIn('05550001122', json.dumps(summary, ensure_ascii=False))
        self.assertNotIn('tamamlandı ve öğrendi', json.dumps(summary, ensure_ascii=False))

    def test_reviewed_same_day_evidence_is_not_repeated(self):
        baseline, suggestions = compute(self.con)
        ident = next(review_identity(x) for x in suggestions if x['type'] == 'overdue')
        self.assertEqual(baseline['pending_overdue_reviews'], 1)
        reviewed, _ = compute(self.con, reviewed={ident})
        self.assertEqual(reviewed['overdue_students'], 1)
        self.assertEqual(reviewed['pending_overdue_reviews'], 0)

    def test_wrong_group_owner_blocks_both_student_identifiers(self):
        self.con.execute("INSERT INTO odev VALUES(103,2,11,'Matematik','devam')")
        summary, _ = compute(self.con)
        self.assertEqual(summary['ownership_review_students'], 2)
        self.assertEqual(summary['evaluated_students'], 1)
        self.assertEqual(summary['pending_overdue_reviews'], 0)
        self.assertEqual(summary['state'], 'REVIEW_REQUIRED')

    def test_dangling_group_blocks_academic_suggestion(self):
        self.con.execute("INSERT INTO odev VALUES(104,1,999,'Fizik','devam')")
        summary, _ = compute(self.con)
        self.assertEqual(summary['ownership_review_students'], 1)
        self.assertEqual(summary['pending_overdue_reviews'], 0)

    def test_unverified_group_owner_blocks_student(self):
        self.con.execute('UPDATE odev_kume SET ogrenci_id=NULL WHERE id=11')
        summary, _ = compute(self.con)
        self.assertEqual(summary['ownership_review_students'], 1)
        self.assertEqual(summary['pending_overdue_reviews'], 0)

    def test_null_child_owner_does_not_infer_student_from_group(self):
        self.con.execute("INSERT INTO odev_satir VALUES(500,NULL,11,NULL,'Matematik')")
        summary, _ = compute(self.con)
        self.assertEqual(summary['ownership_review_students'], 1)
        self.assertEqual(summary['pending_overdue_reviews'], 0)

    def test_wrong_linked_odev_owner_blocks_both(self):
        self.con.execute('INSERT INTO odev_satir VALUES(500,2,NULL,101,\'Matematik\')')
        summary, _ = compute(self.con)
        self.assertEqual(summary['ownership_review_students'], 2)
        self.assertEqual(summary['pending_overdue_reviews'], 0)

    def test_legacy_line_with_no_association_is_not_auto_assigned(self):
        self.con.execute("INSERT INTO odev_satir VALUES(500,2,NULL,NULL,'Matematik')")
        summary, _ = compute(self.con)
        self.assertEqual(summary['pending_overdue_reviews'], 1)
        self.assertEqual(summary['evaluated_students'], 3)
        self.assertEqual(summary['state'], 'PARTIAL_COVERAGE')
        self.assertEqual(summary['modern_rows_not_evaluated'], 1)

    def test_missing_plan_schema_is_unverified_not_missing(self):
        self.con.execute('DROP TABLE koc_plan')
        summary, _ = compute(self.con)
        self.assertEqual(summary['weekly_coaching_plan']['state'], 'UNVERIFIED')
        self.assertIsNone(summary['weekly_coaching_plan']['without_plan'])

    def test_non_iso_plan_dates_are_unverified_not_missing(self):
        self.con.execute("INSERT INTO koc_plan VALUES(7,2,'12.10.2026','18.10.2026',1)")
        summary, _ = compute(self.con)
        self.assertEqual(summary['weekly_coaching_plan']['state'], 'UNVERIFIED')
        self.assertIsNone(summary['weekly_coaching_plan']['without_plan'])

    def test_overlapping_current_week_plans_reported_separately(self):
        self.con.execute("INSERT INTO koc_plan VALUES(3,1,'2026-10-15','2026-10-22',1)")
        self.con.execute("INSERT INTO koc_plan VALUES(4,2,'2026-10-15','2026-10-22',0)")
        summary, _ = compute(self.con)
        self.assertEqual(summary['weekly_coaching_plan']['conflict_students'], 1)
        self.assertEqual(summary['weekly_coaching_plan']['with_plan'], 2)

    def test_no_duplicate_queue_with_same_student_multiple_overdues(self):
        self.con.execute("INSERT INTO odev VALUES(105,1,11,'Fizik','devam')")
        summary, _ = compute(self.con)
        self.assertEqual(summary['overdue_students'], 1)
        self.assertEqual(summary['priority_cards'][0]['recent_open_due'], 2)
        self.assertEqual(summary['pending_overdue_reviews'], 1)

    def test_queue_is_bounded(self):
        for sid in range(20, 50):
            self.con.execute('INSERT INTO ogrenci VALUES(?,?,?,NULL,NULL,1)', (sid, 'Test', str(sid)))
            self.con.execute('INSERT INTO odev_kume VALUES(?,?,?,?)', (sid, sid, '2026-10-01', '2026-10-05'))
            self.con.execute('INSERT INTO odev VALUES(?,?,?,?,?)', (sid, sid, sid, 'Fizik', 'devam'))
        summary, _ = compute(self.con)
        self.assertEqual(summary['pending_overdue_reviews'], 31)
        self.assertEqual(len(summary['priority_cards']), 5)

    def test_failed_identity_schema_fails_closed(self):
        self.con.execute('DROP TABLE odev_kume')
        with self.assertRaises(sqlite3.OperationalError):
            compute(self.con)

    def test_no_writes_to_student_database(self):
        before = self.con.total_changes
        for _ in range(3):
            compute(self.con)
        self.assertEqual(self.con.total_changes, before)

    def test_teacher_feed_uses_canonical_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'sample.db'
            target = sqlite3.connect(p)
            self.con.backup(target)
            target.close()
            result = read_teacher_feed(p, today=DAY)
            self.assertEqual(result['cohort']['active_students'], 3)
            self.assertEqual(result['cohort']['overdue_students'], 1)
            self.assertEqual(result['cohort']['priority_cards'][0]['student_id'], 1)
            self.assertNotIn('05550001122', json.dumps(result['cohort'], ensure_ascii=False))

    def test_protected_homework_and_control_unchanged(self):
        self.assertEqual(audit(ROOT)['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
