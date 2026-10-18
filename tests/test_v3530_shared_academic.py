# -*- coding: utf-8 -*-
"""Synthetic V3.5.30 regression suite, intentionally independent of PyQt/Windows."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
import sqlite3
import unittest

from services.shared_academic_decision_v3530 import (
    read_shared_academic_card, read_verified_plan_context,
)
from tests.test_coach_evidence_v5 import make_db
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 18)


class SharedAcademicTests(unittest.TestCase):
    def setUp(self):
        self.con = make_db()

    def tearDown(self):
        self.con.close()

    def _plan_schema(self):
        self.con.executescript('''
        CREATE TABLE koc_plan(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            baslangic_tarihi TEXT, bitis_tarihi TEXT);
        CREATE TABLE koc_program(id INTEGER PRIMARY KEY, plan_id INTEGER);
        CREATE TABLE koc_hedef(id INTEGER PRIMARY KEY, plan_id INTEGER);
        ''')

    def _overdue(self):
        self.con.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,kitap,durum) "
                         "VALUES(1,1,'Fizik','İvme','Kaynak','devam')")

    def test_missing_coaching_schema_is_not_no_plan(self):
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['student_id'], 1)
        self.assertEqual(card['plan']['state'], 'UNVERIFIED')
        self.assertFalse(card['calendar_plan_verified'])
        self.assertFalse(card['auto_change_allowed'])
        self.assertIsNone(card['academic'])

    def test_no_weekly_plan_is_distinct_from_unavailable(self):
        self._plan_schema()
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['plan']['state'], 'MISSING')
        self.assertEqual(card['state'], 'PLAN_SUGGESTION')
        self.assertIn('hedef', card['next_step'])

    def test_plan_and_program_detected_for_one_student(self):
        self._plan_schema()
        self.con.execute("INSERT INTO koc_plan VALUES(10,1,'2026-10-12','2026-10-18')")
        self.con.execute('INSERT INTO koc_program VALUES(15,10)')
        self.con.execute('INSERT INTO koc_hedef VALUES(22,10)')
        self.con.execute("INSERT INTO koc_plan VALUES(11,2,'2026-10-12','2026-10-18')")
        self.con.execute('INSERT INTO koc_program VALUES(16,11)')
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['plan']['state'], 'READY')
        self.assertEqual(card['plan']['program_blocks'], 1)
        self.assertEqual(card['plan']['target_count'], 1)
        self.assertFalse(card['calendar_plan_verified'])  # not the separate calendar

    def test_missing_program_table_cannot_be_reported_as_empty(self):
        self.con.execute('''CREATE TABLE koc_plan(
            id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            baslangic_tarihi TEXT, bitis_tarihi TEXT)''')
        self.con.execute("INSERT INTO koc_plan VALUES(10,1,'2026-10-12','2026-10-18')")
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['plan']['state'], 'PARTIAL')
        self.assertIsNone(card['plan']['program_blocks'])

    def test_missing_program_blocks_is_actionable_only_as_suggestion(self):
        self._plan_schema()
        self.con.execute("INSERT INTO koc_plan VALUES(10,1,'2026-10-12','2026-10-18')")
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['plan']['state'], 'NO_BLOCKS')
        self.assertEqual(card['state'], 'PLAN_SUGGESTION')
        self.assertFalse(card['auto_change_allowed'])

    def test_overlapping_plan_warns_but_does_not_hide_overdue_homework(self):
        self._plan_schema()
        self.con.execute("INSERT INTO koc_plan VALUES(10,1,'2026-10-12','2026-10-18')")
        self.con.execute("INSERT INTO koc_plan VALUES(11,1,'2026-10-15','2026-10-22')")
        self._overdue()
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['plan']['state'], 'CONFLICT')
        self.assertEqual(card['state'], 'RECOMMENDATION')
        self.assertIn('Fizik', card['next_step'])
        self.assertIn('çakışan', card['planning_hint'])
        self.assertEqual(read_verified_plan_context(self.con, 1, today=TODAY)['state'], 'CONFLICT')

    def test_dangling_group_and_wrong_owner_block_advice(self):
        self.con.execute('ALTER TABLE odev_kume ADD COLUMN ogrenci_id INTEGER')
        self.con.execute('UPDATE odev_kume SET ogrenci_id=2 WHERE id=1')
        self._overdue()
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['state'], 'LINK_REVIEW')
        self.assertIsNone(card['academic'])
        self.assertEqual(card['plan']['state'], 'WITHHELD')
        self.assertEqual(read_verified_plan_context(self.con, 1)['state'], 'LINK_REVIEW')

    def test_invalid_and_missing_student_fail_closed(self):
        for sid in (0, -1, '1', True, None, 999):
            with self.subTest(student_id=sid), self.assertRaises(ValueError):
                read_shared_academic_card(self.con, sid, today=TODAY)

    def test_do_not_modify_connections_or_database(self):
        self._plan_schema()
        self._overdue()
        before = self.con.total_changes
        old_factory = self.con.row_factory
        for _ in range(2):
            card = read_shared_academic_card(self.con, 1, today=TODAY)
            self.assertIn('Fizik', card['next_step'])
        self.assertEqual(before, self.con.total_changes)
        self.assertIs(old_factory, self.con.row_factory)

    def test_default_sqlite_tuple_rows_receive_real_homework_evidence(self):
        self._overdue()
        self.con.row_factory = None  # Student360 uses a tuple-row connection.
        before = self.con.total_changes
        card = read_shared_academic_card(self.con, 1, today=TODAY)
        self.assertEqual(card['state'], 'RECOMMENDATION')
        self.assertIn('Fizik', card['next_step'])
        self.assertIsNone(self.con.row_factory)
        self.assertEqual(self.con.total_changes, before)

    def test_no_cross_student_plan(self):
        self._plan_schema()
        self.con.execute("INSERT INTO koc_plan VALUES(11,2,'2026-10-12','2026-10-18')")
        self.con.execute('INSERT INTO koc_program VALUES(16,11)')
        self.assertEqual(read_shared_academic_card(self.con, 1, today=TODAY)['plan']['state'], 'MISSING')


class WireContractTests(unittest.TestCase):
    def test_original_critical_forms_protected(self):
        self.assertEqual(audit(ROOT)['status'], 'PASS')

    def test_integrations_no_extra_buttons_or_form_modification(self):
        targets = (
            'services/teacher_copilot_v5.py', 'services/coach_assistant_v1/module_bridge_v264.py',
            'ui/student360_panel_v16.py', 'ui/teacher_copilot_strip_v5.py',
        )
        for relative in targets:
            source = (ROOT / relative).read_text(encoding='utf8')
            ast.parse(source)
            self.assertIn('shared_academic', source)
        self.assertIn('read_shared_academic_card', (ROOT/'ui/student360_panel_v16.py').read_text(encoding='utf8'))
        self.assertIn('read_verified_plan_context', (ROOT/'services/coach_assistant_v1/module_bridge_v264.py').read_text(encoding='utf8'))
        self.assertIn('self._watch.poll()', (ROOT/'ui/teacher_copilot_strip_v5.py').read_text(encoding='utf8'))


if __name__ == '__main__':
    unittest.main()
