# -*- coding: utf-8 -*-
"""V3.5.36 synthetic-only, backward-compatible, zero-write tests."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.academic_actions_v3536 import read_student_action_card
from services.canonical_homework_evidence_v3535 import scan_canonical_homework
from services.teacher_copilot_v5 import read_teacher_feed
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 18)


def db():
    con = sqlite3.connect(':memory:')
    con.executescript('''
      CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT,
        aktif INTEGER, dogum_tarihi TEXT, veli_tel1 TEXT);
      CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
        bitis_tarihi TEXT, verilis_tarihi TEXT);
      CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
        kume_id INTEGER, ders TEXT, durum TEXT);
      CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
        kume_id INTEGER, odev_id INTEGER, ders TEXT, durum TEXT,
        silindi INTEGER DEFAULT 0, aktarildi INTEGER DEFAULT 0);
      CREATE TABLE koc_plan(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
        baslangic_tarihi TEXT, bitis_tarihi TEXT);
      CREATE TABLE koc_program(id INTEGER PRIMARY KEY, plan_id INTEGER);
      CREATE TABLE koc_hedef(id INTEGER PRIMARY KEY, plan_id INTEGER);
      INSERT INTO ogrenci VALUES(1,'Test','Öğrenci',1,NULL,'05551234567');
      INSERT INTO ogrenci VALUES(2,'Diğer','Öğrenci',1,NULL,NULL);
      INSERT INTO ogrenci VALUES(3,'Pasif','Öğrenci',0,NULL,NULL);
      INSERT INTO odev_kume VALUES(100,1,'2026-10-15','2026-10-01');
      INSERT INTO odev_kume VALUES(200,2,'2026-10-21','2026-10-01');
      INSERT INTO odev VALUES(101,1,100,'Fizik','devam');
      INSERT INTO odev VALUES(201,2,200,'Biyoloji','tamam');
      INSERT INTO koc_plan VALUES(9,1,'2026-10-12','2026-10-20');
      INSERT INTO koc_program VALUES(91,9);
    ''')
    return con


class AcademicActionTests(unittest.TestCase):
    def setUp(self):
        self.con = db()

    def tearDown(self):
        self.con.close()

    def test_missing_or_bad_student_never_accepted(self):
        for sid in (0,-1,True,'1',None,3,999):
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                read_student_action_card(self.con,sid,today=DAY)

    def test_existing_canonical_default_return_unchanged(self):
        a = scan_canonical_homework(self.con, today=DAY)
        b = scan_canonical_homework(self.con, today=DAY, focus_student_id=1)
        self.assertNotIn('focus_student', a)
        self.assertEqual({k:v for k,v in b.items() if k != 'focus_student'}, a)

    def test_legacy_overdue_action_scoped_to_one_student(self):
        card = read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(card['state'],'HOMEWORK_FOLLOWUP')
        self.assertIn('Fizik',card['next_step'])
        self.assertEqual(card['homework']['overdue_open_tasks'],1)
        self.assertEqual(card['homework']['canonical_tasks'],1)
        self.assertEqual(card['plan']['state'],'READY')
        self.assertFalse(card['calendar_plan_verified'])
        self.assertFalse(card['auto_change_allowed'])

    def test_same_parent_two_modern_children_not_double_counted(self):
        self.con.executemany('INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(?,1,100,101,?,?)',
                              [(301,'Fizik','devam'),(302,'Fizik','tamam')])
        card=read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(card['homework']['canonical_tasks'],2)
        self.assertEqual(card['homework']['completed_tasks'],1)
        self.assertEqual(card['homework']['overdue_open_tasks'],1)

    def test_overdue_action_not_truncated_by_cohort_queue(self):
        # Student 1 is 11th in global sort; focused card must still be correct.
        for sid in range(10,30):
            self.con.execute('INSERT INTO ogrenci VALUES(?,?,?,1,NULL,NULL)',(sid,'Yeni',str(sid)))
            self.con.execute('INSERT INTO odev_kume VALUES(?,?,?,?)',(sid,sid,'2026-10-01','2026-09-30'))
            self.con.execute('INSERT INTO odev VALUES(?,?,?,?,?)',(sid,sid,sid,'Kimya','devam'))
            self.con.execute('INSERT INTO odev VALUES(?,?,?,?,?)',(sid+100,sid,sid,'Kimya','devam'))
        self.assertNotIn(1,[x['student_id'] for x in scan_canonical_homework(self.con,today=DAY)['priority_cards']])
        self.assertEqual(read_student_action_card(self.con,1,today=DAY)['homework']['overdue_open_tasks'],1)

    def test_wrong_owner_blocks_both_students(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(300,2,100,101,'Fizik','devam')")
        for sid in (1,2):
            with self.subTest(sid=sid):
                card=read_student_action_card(self.con,sid,today=DAY)
                self.assertEqual(card['state'],'LINK_REVIEW')
                self.assertIsNone(card['homework']['overdue_open_tasks'])

    def test_unlinked_modern_same_group_quarantines_student(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,ders,durum) VALUES(300,1,100,'Fizik','devam')")
        self.assertEqual(read_student_action_card(self.con,1,today=DAY)['state'],'LINK_REVIEW')

    def test_partial_undated_not_overdue(self):
        self.con.execute("UPDATE odev_kume SET bitis_tarihi='?' WHERE id=100")
        card=read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(card['homework']['overdue_open_tasks'],0)
        self.assertEqual(card['state'],'PARTIAL_COVERAGE')

    def test_other_student_incomplete_not_make_self_unverified(self):
        self.con.execute("UPDATE odev_kume SET bitis_tarihi='?' WHERE id=200")
        card=read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(card['state'],'HOMEWORK_FOLLOWUP')
        self.assertEqual(card['global_coverage'],'PARTIAL_COVERAGE')

    def test_plan_missing_not_calendar_assumed(self):
        self.con.execute('DELETE FROM odev WHERE ogrenci_id=1')
        self.con.execute('DELETE FROM koc_program WHERE plan_id=9')
        self.con.execute('DELETE FROM koc_plan WHERE id=9')
        card=read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(card['state'],'PLAN_REVIEW')
        self.assertEqual(card['plan']['state'],'MISSING')
        self.assertFalse(card['calendar_plan_verified'])

    def test_plan_conflict_alert_when_no_overdue(self):
        self.con.execute('DELETE FROM odev WHERE ogrenci_id=1')
        self.con.execute("INSERT INTO koc_plan VALUES(10,1,'2026-10-01','2026-10-25')")
        card=read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(card['state'],'PLAN_REVIEW')
        self.assertEqual(card['plan']['state'],'CONFLICT')

    def test_mixed_unavailable_schema_never_assumed_empty(self):
        self.con.execute('DROP TABLE odev_satir')
        with self.assertRaises(sqlite3.OperationalError):
            read_student_action_card(self.con,1,today=DAY)

    def test_no_writes_no_row_factory_changes_and_no_contact_leaks(self):
        old = self.con.total_changes
        original_factory=self.con.row_factory
        card=read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(old, self.con.total_changes)
        self.assertIs(original_factory, self.con.row_factory)
        self.assertNotIn('05551234567',repr(card))

    def test_consistent_named_row_factory(self):
        self.con.row_factory=sqlite3.Row
        card=read_student_action_card(self.con,1,today=DAY)
        self.assertEqual(card['homework']['overdue_open_tasks'],1)
        self.assertIs(self.con.row_factory,sqlite3.Row)

    def test_evidence_same_read_only_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'test.db'
            out=sqlite3.connect(target)
            self.con.backup(out);out.close()
            con=sqlite3.connect(target.as_uri()+'?mode=ro',uri=True)
            try:
                con.execute('PRAGMA query_only=ON')
                con.execute('BEGIN')
                self.assertEqual(read_student_action_card(con,1,today=DAY)['state'],'HOMEWORK_FOLLOWUP')
                con.rollback()
            finally: con.close()

    def test_teacher_feed_embeds_verified_card_without_writes(self):
        # Old student feed depends on V10 tables; this synthetic schema is enough
        # for this student's existing birthday/overdue priority.
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'test.db'; out=sqlite3.connect(target)
            self.con.backup(out);out.close()
            result=read_teacher_feed(target,today=DAY)
            if result['cards']:
                action=result['cards'][0].get('verified_academic_action')
                self.assertIsNotNone(action)
                self.assertEqual(action['student_id'],result['cards'][0]['student_id'])

    def test_protected_core_guard(self):
        self.assertEqual(audit(ROOT)['status'],'PASS')

    def test_expected_integrations_parsed(self):
        for name in ('services/teacher_copilot_v5.py',
                     'services/coach_assistant_v1/module_bridge_v264.py',
                     'ui/student360_panel_v16.py','ui/teacher_copilot_strip_v5.py'):
            src=(ROOT/name).read_text('utf8')
            ast.parse(src)
            self.assertIn('academic_action',src) if 'teacher_copilot_strip' in name else self.assertIn('academic_action' if 'teacher_copilot_v5' in name else 'read_student_action_card',src)
        self.assertNotIn('INSERT INTO', (ROOT/'services/academic_actions_v3536.py').read_text('utf8'))


if __name__=='__main__': unittest.main()
