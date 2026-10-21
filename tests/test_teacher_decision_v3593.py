# -*- coding: utf-8 -*-
"""V3593 decision view: student isolation, incomplete evidence, Qt route guards."""
from __future__ import annotations
import ast
from datetime import date
from pathlib import Path
import sqlite3
import unittest

from tests.test_report_intervention_plan_v3592 import source
from services.report_decision_view_v3593 import make_decision_view

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026,10,21)


class TeacherDecisionReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.con = source()
        self.addCleanup(self.con.close)

    def view(self, sid=1, days=90):
        return make_decision_view(self.con, sid, days=days, as_of=DAY)

    def test_scoped_student_and_period(self):
        self.con.execute('PRAGMA query_only=ON')
        before=self.con.total_changes
        view=self.view()
        self.assertEqual((view.student_id,view.days,view.as_of),(1,90,DAY))
        self.assertEqual(view.status,'ölçüm var')
        self.assertTrue(view.courses)
        self.assertIn('8,5 net',view.courses[0].exam_line)
        self.assertIn('1/2',view.courses[0].topic_line)
        self.assertTrue(view.steps)
        self.assertEqual(self.con.total_changes,before)

    def test_students_cannot_see_each_others_courses(self):
        first=self.view(1)
        second=self.view(2)
        self.assertIn('TYT Matematik',repr(first.courses))
        self.assertNotIn('TYT Matematik',repr(second.courses))
        self.assertNotIn('8,5 net',repr(second))

    def test_repeated_net_never_presented_as_valid(self):
        self.con.execute('''INSERT INTO deneme_sonuclari
            (id,deneme_id,ogrenci_id,ders_adi,dogru,yanlis,bos,net)
            VALUES (302,12,1,'Matematik',15,2,3,14.5)''')
        v=self.view()
        self.assertIn('mükerrer',v.courses[0].exam_line)
        self.assertEqual(v.status,'önce doğrula')
        self.assertNotIn('14,5 net',repr(v))

    def test_absent_measurement_no_failure_diagnosis(self):
        self.con.execute('DELETE FROM deneme_sonuclari WHERE ogrenci_id=1')
        v=self.view()
        self.assertFalse(v.courses)
        self.assertEqual(v.status,'veri yetersiz')
        self.assertIn('ölçüm',v.steps[0][1])

    def test_reject_invalid_id_days_and_date(self):
        for val in (False,0,-1,1.0,'1',999):
            with self.subTest(id=val),self.assertRaises(ValueError):
                self.view(val)
        for days in (0,1,7,31,365,'90',True):
            with self.subTest(days=days),self.assertRaises(ValueError):
                self.view(days=days)
        with self.assertRaises(ValueError):
            make_decision_view(self.con,1,as_of='2026-10-21')

    def test_only_bounded_current_course_evidence(self):
        self.assertLessEqual(len(self.view().courses),4)
        self.assertLessEqual(len(self.view().steps),3)
        self.assertLessEqual(len(self.view().warnings),12)


class TeacherDecisionSourceTests(unittest.TestCase):
    def test_six_original_routes_and_new_opt_in_remain(self):
        src=(ROOT/'ui/report_center_v3581.py').read_text('utf-8')
        tree=ast.parse(src)
        routes=next(ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name)
                    and t.id=='REPORT_ROUTES' for t in n.targets))
        self.assertEqual(len(routes),6)
        self.assertIn('"🧭 Öğretmen Karar Paneli"',src)
        self.assertIn('advisor.clicked.connect(self._open_teacher_decision)',src)
        self.assertIn('from ui.teacher_decision_dialog_v3593 import TeacherDecisionDialog',src)
        self.assertIn('owns_connection',src)

    def test_no_network_or_record_mutation_in_new_sources(self):
        for rel in ('services/report_decision_view_v3593.py',
                    'ui/teacher_decision_dialog_v3593.py'):
            code=(ROOT/rel).read_text('utf-8')
            ast.parse(code)
            for forbidden in ('requests.', 'httpx.', 'QDesktopServices',
                              '.commit(', '.rollback(', 'INSERT INTO ', 'UPDATE ogrenci ',
                              'DELETE FROM ', 'QFileDialog'):
                with self.subTest(file=rel,forbidden=forbidden):
                    self.assertNotIn(forbidden,code)
        ui=(ROOT/'ui/teacher_decision_dialog_v3593.py').read_text('utf-8')
        self.assertIn('TextFormat.PlainText',ui)
        self.assertIn('_clear_display',ui)
        self.assertIn('view.student_id, view.days',ui)

    def test_legacy_core_hashes_protected(self):
        import json,hashlib
        expected=json.loads((ROOT/'tests/v42_protected_hashes.json').read_text('utf-8'))
        for rel,digest in expected.items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),digest)


try:
    from PyQt6.QtWidgets import QApplication
    from ui.teacher_decision_dialog_v3593 import TeacherDecisionDialog
    HAVE_QT=True
except ImportError:
    HAVE_QT=False


@unittest.skipUnless(HAVE_QT,'PyQt6 unavailable; run on Qt-equipped Windows/macOS test host')
class TeacherDecisionGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.db=source()
        self.addCleanup(self.db.close)
        self.dialog=TeacherDecisionDialog(self.db)
        self.addCleanup(self.dialog.close)

    def test_search_reset_and_switch_student(self):
        i=self.dialog.students.findData(1)
        self.assertGreater(i,0)
        self.dialog.students.setCurrentIndex(i)
        self.assertEqual(self.dialog._last_key[:2],(1,90))
        self.dialog.search.setText('not-an-existing-student')
        self.assertIsNone(self.dialog._last_key)
        self.assertIsNone(self.dialog.students.currentData())
        self.dialog.search.clear()
        i=self.dialog.students.findData(2)
        self.dialog.students.setCurrentIndex(i)
        self.assertEqual(self.dialog._last_key[:2],(2,90))
        self.assertNotIn('TYT Matematik',self.dialog.info.text())

    def test_period_reset(self):
        self.dialog.students.setCurrentIndex(self.dialog.students.findData(1))
        self.dialog.period.setCurrentIndex(self.dialog.period.findData(30))
        self.assertEqual(self.dialog._last_key[:2],(1,30))


if __name__=='__main__':
    unittest.main()
