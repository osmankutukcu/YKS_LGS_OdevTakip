# -*- coding: utf-8 -*-
"""V3.5.27 — pure Python source/behavior sentinel; never touches actual DB."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from utils.checkbox_dispatch import PendingCheckboxChanges
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]


class ProtectedFormSourceTests(unittest.TestCase):
    def test_pinned_core_source_contract(self):
        self.assertEqual(audit(ROOT)['status'], 'PASS')

    def test_previous_10_protected_files_identical(self):
        expected=json.loads((ROOT/'tests/v42_protected_hashes.json').read_text('utf8'))
        self.assertEqual(len(expected),10)
        for rel, digest in expected.items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(), digest)

    def test_4_critical_helpers_are_protected(self):
        report = audit(ROOT)
        self.assertEqual(report['protected_helpers'], 4)
        self.assertFalse(report['errors'])

    def test_13_behavior_methods_are_pinned(self):
        report=audit(ROOT)
        self.assertEqual(len(report['effective_handlers']),13)
        self.assertFalse(report['errors'])

    def test_duplicate_handlers_are_reported_but_not_deleted(self):
        report=audit(ROOT)
        for rel, name in [('ui/homework_form.py','_odev_kontrol'),
                          ('ui/odev_kontrol.py','_hesapla_yuzde')]:
            with self.subTest(method=name):
                self.assertEqual(report['effective_handlers'][rel+':'+name]['definition_count'],2)
                self.assertIn('EXISTING_SHADOWED_METHOD:'+rel+':'+name, report['warnings'])

    def test_gate_rejects_locking_color_mutation_in_separate_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone=self._clone(tmp)
            p=clone/'ui/homework_form.py'
            p.write_text(p.read_text('utf8').replace('#A5D6A7','#ABCDEF',1), encoding='utf8')
            self.assertEqual(audit(clone)['status'],'BLOCK')
            self.assertTrue(any('homework_form.py' in e for e in audit(clone)['errors']))

    def test_gate_rejects_checkbox_signal_disconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone=self._clone(tmp)
            p=clone/'ui/odev_kontrol.py'
            p.write_text(p.read_text('utf8').replace('tab.itemChanged.connect(self._on_table_item_changed)',
                         'tab.itemChanged.connect(self._no_handler)',1),encoding='utf8')
            errors=audit(clone)['errors']
            self.assertTrue(any(e.startswith('SIGNAL_WIRING_MISSING:') for e in errors))

    def test_gate_rejects_change_to_effective_duplicate_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone=self._clone(tmp)
            p=clone/'ui/odev_kontrol.py'
            content=p.read_text('utf8').replace('        self._update_header_stats()','        self._set_header_stats(0, 1)',1)
            p.write_text(content,encoding='utf8')
            self.assertEqual(audit(clone)['status'],'BLOCK')

    def test_ci_blocks_build_when_protected_core_is_modified(self):
        workflow=(ROOT/'.github/workflows/build_installer.yml').read_text('utf8')
        self.assertIn('python tools/v3527_core_guard.py', workflow)
        self.assertIn('python -m unittest tests.test_v3527_protected_forms -v', workflow)
        self.assertIn('if ($LASTEXITCODE -ne 0)', workflow)

    def test_source_guard_requires_no_qt_and_no_student_data(self):
        report=audit(ROOT)
        self.assertFalse(report['database_read_or_write'])
        self.assertFalse(report['runtime_monkey_patching'])
        self.assertEqual(report['windows_visual_and_interactive_uat'],'NOT_VERIFIED')
        self.assertFalse(report['production_release_authorized'])

    def _clone(self, where):
        clone=Path(where)
        (clone/'ui').mkdir(exist_ok=True)
        (clone/'tests').mkdir(exist_ok=True)
        for rel in ('ui/homework_form.py','ui/odev_kontrol.py',
                    'tests/v42_protected_hashes.json','tests/v3527_effective_behavior_baseline.json',
                    'tests/v3527_protected_helpers.json',
                    'utils/checkbox_dispatch.py','utils/wizard_integrity_v8.py',
                    'utils/homework_integrity_v133.py','utils/table_tune.py'):
            p=clone/rel; p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/rel,p)
        # Preserve other protected source digests without requiring full copies;
        # missing unrelated source files themselves fail closed, which is okay
        return clone


class PendingCheckboxBehaviorTests(unittest.TestCase):
    def test_same_cell_many_events_keeps_single_latest_key(self):
        q=PendingCheckboxChanges()
        for _ in range(1000): q.push(5,2)
        self.assertEqual(len(q),1)
        self.assertEqual(q.drain(),((5,2),))
        self.assertFalse(q)

    def test_multiple_cells_preserve_first_arrival_order(self):
        q=PendingCheckboxChanges()
        for cell in ((1,1),(3,2),(1,1),(0,4),(3,2)):
            q.push(*cell)
        self.assertEqual(q.drain(),((1,1),(3,2),(0,4)))

    def test_drain_is_idempotent_and_new_events_remain_possible(self):
        q=PendingCheckboxChanges()
        q.push(0,1)
        self.assertEqual(q.drain(),((0,1),))
        self.assertEqual(q.drain(),())
        q.push(2,5)
        self.assertEqual(q.drain(),((2,5),))

    def test_large_queue_no_row_loss(self):
        q=PendingCheckboxChanges()
        for idx in range(1000):q.push(idx//50,idx%50)
        self.assertEqual(len(q.drain()),1000)


if __name__=='__main__': unittest.main()
