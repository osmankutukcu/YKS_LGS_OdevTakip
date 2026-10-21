# -*- coding: utf-8 -*-
"""V3594: fail-closed routing; no writes or student mixing."""
from __future__ import annotations
import ast
from pathlib import Path
import sqlite3
import unittest

from services.report_navigation_v3594 import (
    NavigationIntent, issue_navigation, verify_navigation, valid_active_student,
    MAX_AGE_SECONDS,
)
from ui.report_navigation_bridge_v3594 import _select_coaching_student

ROOT = Path(__file__).resolve().parents[1]


def con_for_tests():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER)')
    db.executemany('INSERT INTO ogrenci VALUES (?,?,?,?)',
                   [(1,'Ali','Veli',1),(2,'Berna','Fırat',1),(3,'Kapalı','Öğrenci',0)])
    return db


class NavigationIntentTests(unittest.TestCase):
    def setUp(self):
        self.db = con_for_tests()
        self.addCleanup(self.db.close)

    def test_valid_two_routes_are_immutable_and_student_scoped(self):
        for route in ('weekly', 'coaching'):
            with self.subTest(route=route):
                intent = issue_navigation(self.db, route, 2, selected_student_id=2)
                self.assertTrue(verify_navigation(self.db, intent))
                self.assertEqual((intent.student_id, intent.destination), (2, route))
                with self.assertRaises(Exception):
                    intent.student_id = 1

    def test_different_selected_student_rejected(self):
        with self.assertRaises(ValueError):
            issue_navigation(self.db, 'weekly', 1, selected_student_id=2)

    def test_missing_inactive_invalid_ids_are_rejected(self):
        for sid in (-1, 0, 3, 888, False, 1.0, '1', None):
            with self.subTest(sid=sid):
                self.assertFalse(valid_active_student(self.db, sid))
                with self.assertRaises(ValueError):
                    issue_navigation(self.db, 'coaching', sid, selected_student_id=sid)

    def test_unknown_destinations_cannot_be_dispatched(self):
        for dest in ('write_homework', 'delete', 'whatsapp', '', None):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                issue_navigation(self.db, dest, 1, selected_student_id=1)

    def test_expiry_and_future_timestamp_fail(self):
        intent = issue_navigation(self.db, 'weekly', 1, selected_student_id=1)
        self.assertTrue(verify_navigation(self.db, intent, now=intent.issued_at))
        self.assertTrue(verify_navigation(self.db, intent, now=intent.issued_at+MAX_AGE_SECONDS-0.1))
        self.assertFalse(verify_navigation(self.db, intent, now=intent.issued_at+MAX_AGE_SECONDS+0.1))
        self.assertFalse(verify_navigation(self.db, intent, now=intent.issued_at-1))

    def test_revalidate_if_student_deactivated_after_approval(self):
        intent = issue_navigation(self.db, 'weekly', 2, selected_student_id=2)
        self.db.execute('UPDATE ogrenci SET aktif=0 WHERE id=2')
        self.assertFalse(verify_navigation(self.db, intent))

    def test_data_missing_fail_closed(self):
        self.db.execute('DROP TABLE ogrenci')
        self.assertFalse(valid_active_student(self.db, 1))
        self.assertFalse(verify_navigation(self.db, NavigationIntent('weekly',1,0),now=1))

    def test_legacy_schema_without_active_column(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT)')
        db.execute('INSERT INTO ogrenci VALUES(4,"Ece","Deniz")')
        self.assertTrue(valid_active_student(db, 4))

    def test_invalid_objects_are_rejected(self):
        for inp in (None, 1, {'student_id':1}, 'coaching'):
            self.assertFalse(verify_navigation(self.db, inp))

    def test_no_database_mutations_by_service(self):
        count = self.db.total_changes
        self.db.execute('PRAGMA query_only=ON')
        intent = issue_navigation(self.db, 'weekly', 1, selected_student_id=1)
        self.assertTrue(verify_navigation(self.db, intent))
        self.assertEqual(self.db.total_changes, count)


class MockItem:
    def __init__(self, sid): self.sid=sid
    def data(self, role): return self.sid if role == 44 else None

class MockList:
    def __init__(self, values): self.items=[MockItem(n) for n in values];self.current=None
    def count(self): return len(self.items)
    def item(self,i): return self.items[i]
    def setCurrentItem(self,item): self.current=item

class MockCoaching:
    def __init__(self, items): self.list_students=MockList(items);self.current_student_id=None
    def _on_student_selected(self, item): self.current_student_id=item.sid


class BridgeTests(unittest.TestCase):
    def test_select_exact_coach_id_not_default(self):
        obj=MockCoaching([1,2,3]);obj.current_student_id=1
        _select_coaching_student(obj, 2, role=44)
        self.assertEqual(obj.current_student_id,2)
        self.assertEqual(obj.list_students.current.sid,2)

    def test_missing_coach_id_does_not_pick_other_student(self):
        obj=MockCoaching([1,2])
        with self.assertRaises(RuntimeError):
            _select_coaching_student(obj,99,role=44)
        self.assertIsNone(obj.list_students.current)

    def test_inconsistent_widget_blocks_wrong_student(self):
        obj=MockCoaching([1,2]);obj._on_student_selected=lambda i: None
        with self.assertRaises(RuntimeError):
            _select_coaching_student(obj,2,role=44)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.db = con_for_tests()
        self.addCleanup(self.db.close)
        self.intent = issue_navigation(self.db, 'weekly', 2, selected_student_id=2)

    def test_existing_homework_form_selected_at_construction(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from ui.report_navigation_bridge_v3594 import open_confirmed_navigation
        seen = []
        class FakeHomework:
            def __init__(self, parent=None, ogrenci_id=None):
                self.actual = ogrenci_id
            def select_student_by_id(self, student_id, autoload=False):
                self.actual = student_id
            def _secili_ogrenci_id(self): return self.actual
        class FakeMain:
            def _show_dialog(self, cls):
                obj=cls(None)
                seen.append(obj._secili_ogrenci_id())
        modules = {'db': SimpleNamespace(get_conn=lambda: self.db),
                   'ui.homework_form': SimpleNamespace(OdevTakipFormu=FakeHomework)}
        class NonClosing:
            def __init__(self, conn): self.conn=conn
            def execute(self, *a): return self.conn.execute(*a)
            def close(self): pass
        modules['db'].get_conn=lambda: NonClosing(self.db)
        with patch.dict(sys.modules, modules):
            open_confirmed_navigation(FakeMain(), self.intent)
        self.assertEqual(seen,[2])

    def test_weekly_form_fails_if_student_selection_invalid(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from ui.report_navigation_bridge_v3594 import open_confirmed_navigation
        class WrongHomework:
            def __init__(self,parent=None,ogrenci_id=None): self.actual=1
            def select_student_by_id(self, sid, autoload=False): pass
            def _secili_ogrenci_id(self): return self.actual
        class FakeMain:
            def _show_dialog(self, cls): cls(None)
        class NonClosing:
            def execute(self, *args): return self_db.execute(*args)
            def close(self): pass
        self_db=self.db
        modules={'db': SimpleNamespace(get_conn=lambda: NonClosing()),
                 'ui.homework_form': SimpleNamespace(OdevTakipFormu=WrongHomework)}
        with patch.dict(sys.modules, modules):
            with self.assertRaises(RuntimeError):
                open_confirmed_navigation(FakeMain(), self.intent)

    def test_newly_inactive_student_does_not_open_form(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        from ui.report_navigation_bridge_v3594 import open_confirmed_navigation
        self.db.execute('UPDATE ogrenci SET aktif=0 WHERE id=2')
        seen=[]
        class Main:
            def _show_dialog(self, cls): seen.append(cls)
        db_conn=self.db
        class NonClosing:
            def execute(self, *a): return db_conn.execute(*a)
            def close(self): pass
        with patch.dict(sys.modules, {'db': SimpleNamespace(get_conn=lambda:NonClosing())}):
            with self.assertRaises(ValueError):
                open_confirmed_navigation(Main(),self.intent)
        self.assertEqual(seen, [])


class SourceGuardTests(unittest.TestCase):
    def test_new_code_uses_existing_safe_routes_only(self):
        code=(ROOT/'ui/report_navigation_bridge_v3594.py').read_text('utf8')
        self.assertIn('ui.homework_form import OdevTakipFormu',code)
        self.assertIn('ogrenci_id=requested_id',code)
        self.assertIn('selected != requested_id',code)
        self.assertIn('ui.coaching_manager import CoachingManager',code)
        self.assertNotIn('INSERT INTO',code)
        self.assertNotIn('.commit(',code)
        self.assertNotIn('requests.',code)
        self.assertNotIn('QDesktopServices',code)

    def test_double_confirmation_and_modal_close(self):
        teacher=(ROOT/'ui/teacher_decision_dialog_v3593.py').read_text('utf8')
        center=(ROOT/'ui/report_center_v3581.py').read_text('utf8')
        app=(ROOT/'app.py').read_text('utf8')
        self.assertIn('QMessageBox.question',teacher)
        self.assertIn('self._last_key[:2]',teacher)
        self.assertIn('self.approved_navigation = intent',center)
        self.assertIn('self.accept()  # Return to app.py',center)
        self.assertIn('QTimer.singleShot(0, _go_to_selected_student)',app)
        self.assertIn('open_confirmed_navigation(w, request)',app)
        for path in ('ui/teacher_decision_dialog_v3593.py','ui/report_center_v3581.py','app.py'):
            ast.parse((ROOT/path).read_text('utf8'))

    def test_original_six_reporting_routes_remain(self):
        tree=ast.parse((ROOT/'ui/report_center_v3581.py').read_text('utf8'))
        routes=next(ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name)
                    and t.id=='REPORT_ROUTES' for t in n.targets))
        self.assertEqual(len(routes),6)

    def test_unchanged_protected_sources(self):
        import hashlib,json
        expected=json.loads((ROOT/'tests/v42_protected_hashes.json').read_text('utf8'))
        self.assertGreaterEqual(len(expected),10)
        for rel,digest in expected.items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),digest)


if __name__ == '__main__': unittest.main()
