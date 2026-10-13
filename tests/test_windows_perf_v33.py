from __future__ import annotations
from tools.v35_reviewed_source_contract import verify_legacy_handlers
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.windows_perf_v33 import RefreshGate, install_experimental_style_coalescing
from tools.v33_windows_ab_pilot import main as v33_main

ROOT = Path(__file__).resolve().parents[1]


class TestRefreshGate(unittest.TestCase):
    def test_100_requests_one_refresh(self):
        queue, events = [], []
        gate = RefreshGate(queue.append, lambda: events.append('refresh'))
        for _ in range(100):
            gate.request()
        self.assertEqual(len(queue), 1)
        self.assertEqual(gate.requests, 100)
        self.assertEqual(gate.coalesced, 99)
        queue.pop()()
        self.assertEqual(events, ['refresh'])
        self.assertFalse(gate.pending)

    def test_sequential_events_refresh_twice(self):
        queue, done = [], []
        gate = RefreshGate(queue.append, lambda: done.append(1))
        gate.request(); queue.pop()()
        gate.request(); queue.pop()()
        self.assertEqual(len(done), 2)

    def test_reentrant_request_does_not_schedule_forever(self):
        q = []
        gate = None
        def refresh():
            gate.request()
        gate = RefreshGate(q.append, refresh)
        gate.request()
        q.pop()()
        self.assertEqual(len(q), 0)
        self.assertEqual(gate.coalesced, 1)

    def test_exception_restores_state(self):
        q = []
        def broken(): raise RuntimeError('test')
        gate = RefreshGate(q.append, broken)
        gate.request()
        with self.assertRaises(RuntimeError): q.pop()()
        self.assertFalse(gate.running)
        self.assertFalse(gate.pending)
        gate.request()
        self.assertEqual(len(q), 1)

    def test_scheduler_exception_does_not_lock_state(self):
        def broken(fn): raise RuntimeError('queue unavailable')
        gate = RefreshGate(broken, lambda: None)
        with self.assertRaises(RuntimeError): gate.request()
        self.assertFalse(gate.pending)

    def test_no_request_is_no_refresh(self):
        queue, calls = [], []
        gate = RefreshGate(queue.append, lambda: calls.append(1))
        gate.flush()
        self.assertEqual(calls, [])


class FakeViewport:
    def __init__(self): self.repaint_requests = 0
    def update(self): self.repaint_requests += 1


class FakeTable:
    def __init__(self): self.vp = FakeViewport(); self._model = object()
    def model(self): return self._model
    def viewport(self): return self.vp


class FakeBlocker:
    starts, ends = 0, 0
    def __init__(self, model):
        FakeBlocker.starts += 1
    def __del__(self):
        FakeBlocker.ends += 1


class TestExperimentalPatch(unittest.TestCase):
    def setUp(self):
        FakeBlocker.starts = FakeBlocker.ends = 0
        self.tasks = []

    def make_cls(self):
        class Sample:
            def __init__(self): self.tab = FakeTable(); self.calls = 0
            def _refresh_right_table_styles(self): self.calls += 1
        return Sample

    def test_disabled_by_default_and_once_per_event_loop(self):
        cls = self.make_cls()
        inst = cls()
        inst._refresh_right_table_styles()
        self.assertEqual(inst.calls, 1)
        self.assertTrue(install_experimental_style_coalescing(cls, submit=self.tasks.append,
            blocker_factory=FakeBlocker))
        self.assertFalse(install_experimental_style_coalescing(cls, submit=self.tasks.append,
            blocker_factory=FakeBlocker))
        for _ in range(50): inst._refresh_right_table_styles()
        self.assertEqual(inst.calls, 1)
        self.assertEqual(len(self.tasks),1)
        self.tasks.pop()()
        self.assertEqual(inst.calls,2)
        self.assertEqual(inst.tab.vp.repaint_requests,1)
        self.assertEqual((FakeBlocker.starts,FakeBlocker.ends),(1,1))

    def test_actual_style_timing_is_separate_from_deferred_queue_time(self):
        cls = self.make_cls()
        durations = []
        install_experimental_style_coalescing(
            cls, submit=self.tasks.append, blocker_factory=FakeBlocker,
            record_actual_ns=durations.append)
        inst=cls()
        for _ in range(6): inst._refresh_right_table_styles()
        self.assertEqual(durations, [])  # No real style refresh yet.
        self.tasks.pop()()
        self.assertEqual(len(durations),1)
        self.assertGreaterEqual(durations[0], 0)

    def test_each_dialog_uses_own_gate(self):
        cls = self.make_cls()
        install_experimental_style_coalescing(cls, submit=self.tasks.append,
            blocker_factory=FakeBlocker)
        a, b = cls(), cls()
        a._refresh_right_table_styles(); b._refresh_right_table_styles()
        self.assertEqual(len(self.tasks),2)
        for task in self.tasks: task()
        self.assertEqual((a.calls,b.calls),(1,1))

    def test_failed_legacy_refresh_unblocks_model(self):
        class Bad:
            def __init__(self): self.tab = FakeTable()
            def _refresh_right_table_styles(self): raise ValueError('test')
        install_experimental_style_coalescing(Bad, submit=self.tasks.append,
            blocker_factory=FakeBlocker)
        x = Bad()
        x._refresh_right_table_styles()
        with self.assertRaises(ValueError): self.tasks.pop()()
        self.assertEqual(FakeBlocker.starts,FakeBlocker.ends)

    def test_bypasses_missing_table(self):
        cls = self.make_cls()
        install_experimental_style_coalescing(cls, submit=self.tasks.append,
            blocker_factory=FakeBlocker)
        a=cls(); a.tab=None
        a._refresh_right_table_styles(); self.tasks.pop()()
        self.assertEqual(a.calls,0)


class TestReleaseSafety(unittest.TestCase):
    def test_production_core_unchanged(self):
        hashes={
          'ui/homework_form.py':'f015d489390ad0d529aabd2f447eaeaed14ccd54f48aaa81dd4a5ed47aef6cad',
          'ui/odev_kontrol.py':'7ca39f447e4a7cd71cb4eb14fde9bba53fae6c183092d0758a77c8d009cd4d0c',
        }
        for rel, expected in hashes.items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),expected)

        verify_legacy_handlers(ROOT)

    def test_inspect_only_does_not_mutate_db_or_require_qt(self):
        with tempfile.TemporaryDirectory() as d:
            dbpath = Path(d)/'test.db'
            with sqlite3.connect(dbpath) as con:
                con.executescript('CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER); CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, silindi INTEGER, ogrenci_id INTEGER);')
            h1=hashlib.sha256(dbpath.read_bytes()).hexdigest()
            from io import StringIO
            from contextlib import redirect_stdout
            out=StringIO()
            with redirect_stdout(out):
                result=v33_main(['--database',str(dbpath),'--mode','coalesced','--inspect-only'])
            self.assertEqual(result,0)
            self.assertEqual(hashlib.sha256(dbpath.read_bytes()).hexdigest(),h1)
            self.assertEqual(json.loads(out.getvalue())['mutations'],0)

    def test_live_mode_requires_explicit_gate(self):
        with tempfile.TemporaryDirectory() as d:
            dbpath = Path(d)/'test.db'; dbpath.write_bytes(b'test')
            with patch.dict('os.environ',{'ODEV_V33_TEST_DB_CONFIRMED':''}):
                with self.assertRaises(SystemExit):
                    v33_main(['--database',str(dbpath),'--mode','coalesced'])

    def test_normal_application_not_importing_experimental_patch(self):
        for p in ['app.py','main_window.py','ui/homework_form.py','ui/odev_kontrol.py']:
            self.assertNotIn('windows_perf_v33', (ROOT/p).read_text(encoding='utf-8'))


if __name__ == '__main__': unittest.main()
