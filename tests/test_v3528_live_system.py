# -*- coding: utf-8 -*-
"""V3.5.28 safety tests; synthetic fixtures only, no real student database."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.coach_assistant_v1.event_router_v267 import CoachChangeRouter
from services.system_registry_v3528 import MODULES, affected_modules, validate_registry
from services.live_refresh_coordinator_v3528 import (
    ExternalCommitObserver, decide_refresh, signal_after_commit,
)
from services.system_health_v3528 import database_schema_health, system_snapshot

ROOT = Path(__file__).resolve().parents[1]


class ModuleCatalogTests(unittest.TestCase):
    def test_catalog_has_no_duplicate_keys(self):
        self.assertEqual(len(MODULES), len({m.key for m in MODULES}))

    def test_all_modules_are_discoverable_in_source_without_importing_qt(self):
        result = validate_registry(ROOT)
        self.assertEqual(result['status'], 'PASS', result['issues'])
        self.assertEqual(result['source_present'], len(MODULES))
        self.assertTrue(all(m['runtime_tested'] is False for m in result['modules']))

    def test_homework_and_control_are_explicitly_protected(self):
        entries = {m.key: m for m in MODULES}
        self.assertTrue(entries['homework'].protected)
        self.assertTrue(entries['control'].protected)

    def test_declared_relations_have_known_endpoints(self):
        entries = {m.key for m in MODULES}
        self.assertTrue(all(dep in entries for m in MODULES for dep in m.depends_on))

    def test_event_impact_is_explicit(self):
        self.assertIn('reports', affected_modules('homework'))
        self.assertIn('student360', affected_modules('control'))
        self.assertIn('planner', affected_modules('coaching_plan'))
        self.assertEqual(len(affected_modules('database_unknown')), len(MODULES))
        with self.assertRaises(ValueError):
            affected_modules('does_not_exist')


class LiveRefreshTests(unittest.TestCase):
    def setUp(self):
        self.bus = CoachChangeRouter(capacity=4)
        self.cursor = self.bus.cursor

    def _decision(self, **kwargs):
        return decide_refresh(self.bus, self.cursor, student_id=11,
                              module='student360', **kwargs)

    def test_no_event_no_refresh(self):
        d = self._decision()
        self.assertEqual(d.status, 'NO_CHANGE')
        self.assertEqual(d.acknowledged_cursor(refreshed_successfully=False), self.cursor)

    def test_correct_student_refreshes_but_other_student_does_not(self):
        signal_after_commit(self.bus, 'homework', student_id=22)
        self.assertEqual(self._decision().status, 'NO_CHANGE')
        signal_after_commit(self.bus, 'homework', student_id=11)
        self.assertEqual(self._decision().status, 'REFRESH_REQUIRED')

    def test_dirty_edit_is_not_discarded_and_event_cursor_is_not_consumed(self):
        signal_after_commit(self.bus, 'control', student_id=11)
        dirty = self._decision(has_unsaved_changes=True)
        self.assertEqual(dirty.status, 'DEFER_DIRTY')
        self.assertEqual(dirty.acknowledged_cursor(refreshed_successfully=True), self.cursor)
        ready = self._decision(has_unsaved_changes=False)
        self.assertEqual(ready.status, 'REFRESH_REQUIRED')
        self.assertEqual(ready.acknowledged_cursor(refreshed_successfully=False), self.cursor)
        self.assertEqual(ready.acknowledged_cursor(refreshed_successfully=True), self.bus.cursor)

    def test_hidden_or_busy_defer_without_losing_the_event(self):
        signal_after_commit(self.bus, 'coaching_plan', student_id=11)
        for props, expected in (({'is_visible': False}, 'DEFER_HIDDEN'),
                                ({'is_busy': True}, 'DEFER_BUSY')):
            with self.subTest(status=expected):
                d = self._decision(**props)
                self.assertEqual(d.status, expected)
                self.assertEqual(d.acknowledged_cursor(refreshed_successfully=True), self.cursor)

    def test_unknown_database_change_refreshes_any_selected_student(self):
        signal_after_commit(self.bus, 'database_unknown')
        d = self._decision()
        self.assertTrue(d.changed)
        self.assertEqual(d.status, 'REFRESH_REQUIRED')

    def test_unknown_change_cannot_be_given_a_fake_student_scope(self):
        with self.assertRaises(ValueError):
            signal_after_commit(self.bus, 'database_unknown', student_id=11)
        self.assertEqual(self.bus.cursor, 0)

    def test_invalid_module_is_rejected(self):
        with self.assertRaises(ValueError):
            decide_refresh(self.bus, 0, student_id=11, module='unregistered')

    def test_missing_student_or_impossible_cursor_is_rejected(self):
        with self.assertRaises(ValueError):
            decide_refresh(self.bus, 0, student_id=0, module='student360')
        with self.assertRaises(ValueError):
            decide_refresh(self.bus, 99, student_id=11, module='student360')

    def test_overflow_cannot_silently_hide_past_changes(self):
        for index in range(7):
            signal_after_commit(self.bus, 'exam', student_id=index + 1)
        d = self._decision()
        self.assertTrue(d.overflow)
        self.assertEqual(d.status, 'REFRESH_REQUIRED')

    def test_topic_and_lesson_scopes_are_not_crossed(self):
        signal_after_commit(self.bus, 'homework', student_id=11, lesson='Fizik', topic='Optik')
        unrelated = self._decision(lesson='Kimya')
        self.assertEqual(unrelated.status, 'NO_CHANGE')
        related = self._decision(lesson='Fizik')
        self.assertEqual(related.status, 'REFRESH_REQUIRED')

    def test_external_connection_commit_fires_one_generic_event(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'synthetic.sqlite'
            with closing(sqlite3.connect(db)) as con:
                con.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)')
                con.commit()
            observer = ExternalCommitObserver(db, self.bus)
            try:
                self.assertFalse(observer.poll())  # establish baseline
                with closing(sqlite3.connect(db)) as con:
                    con.execute("INSERT INTO sample(value) VALUES ('hello')")
                    con.commit()
                self.assertTrue(observer.poll())
                self.assertEqual(self.bus.cursor, 1)
                self.assertFalse(observer.poll())
                self.assertEqual(self.bus.cursor, 1)
            finally:
                observer.close()

    def test_uncommitted_other_connection_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'synthetic.sqlite'
            with closing(sqlite3.connect(db)) as con:
                con.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY)')
                con.commit()
            observer = ExternalCommitObserver(db, self.bus)
            other = sqlite3.connect(db)
            try:
                self.assertFalse(observer.poll())
                other.execute('BEGIN')
                other.execute('INSERT INTO sample(id) VALUES (1)')
                self.assertFalse(observer.poll())
                other.rollback()
                self.assertFalse(observer.poll())
                self.assertEqual(self.bus.cursor, 0)
            finally:
                other.close()
                observer.close()


class SystemHealthTests(unittest.TestCase):
    def test_snapshot_never_reads_a_db_unless_explicit(self):
        status = system_snapshot(ROOT)
        self.assertEqual(status['source_state'], 'SOURCE_READY')
        self.assertEqual(status['database']['state'], 'NOT_REQUESTED')
        self.assertFalse(status['release']['production_approved'])
        self.assertEqual(status['live_updates']['new_decision_engine'], 'OPT_IN_PILOT_NOT_UI_CONNECTED')

    def test_missing_db_path_does_not_create_a_file(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'nonexistent.sqlite'
            result = database_schema_health(db)
            self.assertEqual(result['state'], 'DB_NOT_FOUND')
            self.assertFalse(db.exists())

    def test_schema_only_reads_no_student_rows_and_keeps_db_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'synthetic.sqlite'
            with closing(sqlite3.connect(db)) as con:
                con.execute('CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, secret TEXT)')
                con.execute('CREATE TABLE odev (id INTEGER PRIMARY KEY)')
                con.execute('CREATE TABLE odev_kume (id INTEGER PRIMARY KEY)')
                con.execute("INSERT INTO ogrenci(secret) VALUES ('PRIVATE_SENTINEL_SHOULD_NOT_LEAK')")
                con.commit()
            initial = hashlib.sha256(db.read_bytes()).hexdigest()
            snap = system_snapshot(ROOT, db_path=db)
            after = hashlib.sha256(db.read_bytes()).hexdigest()
            self.assertEqual(snap['database']['state'], 'SCHEMA_PRESENT')
            self.assertEqual(initial, after)
            self.assertNotIn('PRIVATE_SENTINEL_SHOULD_NOT_LEAK', json.dumps(snap))
            self.assertFalse(snap['database']['row_data_read'])

    def test_incomplete_schema_is_reported_but_never_fixed(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'synthetic.sqlite'
            with closing(sqlite3.connect(db)) as con:
                con.execute('CREATE TABLE ogrenci (id INTEGER PRIMARY KEY)')
                con.commit()
            result = database_schema_health(db)
            self.assertEqual(result['state'], 'SCHEMA_REVIEW')
            self.assertIn('odev', result['missing_tables'])
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual([r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")], ['ogrenci'])


if __name__ == '__main__':
    unittest.main()
