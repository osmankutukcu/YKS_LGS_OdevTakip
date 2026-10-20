"""Synthetic-data isolation tests for V3.5.85 weekly profile reporting."""
from __future__ import annotations
from datetime import date
from pathlib import Path
from unittest.mock import patch
import hashlib
import os
import sqlite3
import tempfile
import unittest

from services.report_planner_bridge_v3585 import read_planner_evidence
from services.integrated_report_v3584 import read_integrated_report, preview_text, export_integrated_pdf
from tests.test_integrated_report_v3584 import prepared, DAY

MODULE = 'services.report_planner_bridge_v3585'
ROOT = Path(__file__).resolve().parents[1]


def profile(**extras):
    base = dict(planner_version=2, wake='07:00', sleep='23:00', max=180,
                school_by_day={'0':['08:00','15:00']},
                blocks=['Salı [17:00-19:00] Kurs'], empty='Yok',
                session_enabled=True, session_minutes=45)
    base.update(extras)
    return base


def approved():
    return dict(schema=1, created_on='2026-10-19', work_units=8,
                placed_minutes=330, pending_minutes=45, placed=[], pending={})


class PlannerBridgeV3585Tests(unittest.TestCase):
    def _read(self, sid=1, *, mappings=None, profiles=None, snapshot=None):
        with patch(f'{MODULE}.load_assignments', return_value={} if mappings is None else mappings), \
             patch(f'{MODULE}.load_profiles', return_value={} if profiles is None else profiles), \
             patch(f'{MODULE}.load_approved', return_value=snapshot) as load:
            r=read_planner_evidence(sid,reference_day=DAY)
        self.assertEqual(load.call_args.args, (sid,))
        return r

    def test_valid_explicit_assignment_and_approved_plan(self):
        result=self._read(mappings={'1':'A','2':'B'}, profiles={'A': profile()}, snapshot=approved())
        self.assertEqual(result.routine.status,'kayıt')
        self.assertIn('45 dk',result.routine.value)
        self.assertIn('Aday çalışma', result.routine.value)
        self.assertNotIn('2',result.routine.value.split('Aday çalışma')[0])
        self.assertEqual(result.approved_plan.status,'kayıt')
        self.assertIn('330 dk', result.approved_plan.value)
        self.assertIn('ödevlerin bugün de aynı olduğu',result.approved_plan.scope)

    def test_missing_assignment_does_not_guess_template(self):
        result=self._read(sid=2,mappings={'1':'A'},profiles={'A':profile()},snapshot=None)
        self.assertEqual(result.routine.status,'eksik')
        self.assertIn('atanmış',result.routine.value)
        self.assertEqual(result.approved_plan.status,'eksik')

    def test_owned_by_other_student_never_leaks(self):
        result=self._read(sid=1,mappings={'1':'Private Profile'},
                          profiles={'Private Profile':profile(_session_advisor_owner='2')})
        self.assertEqual(result.routine.status,'doğrulanamadı')
        self.assertIn('başka öğrenciye ait',result.routine.value)
        self.assertNotIn('45 dk',result.routine.value)
        self.assertTrue(result.routine.warning)

    def test_shared_template_marked_shared_no_profile_name_leak(self):
        result=self._read(mappings={'1':'Private Another Student','2':'Private Another Student'},
                          profiles={'Private Another Student':profile()})
        self.assertIn('Paylaşılan',result.routine.value)
        self.assertNotIn('Another Student',result.routine.value)

    def test_invalid_hours_and_legacy_versions_are_not_reported(self):
        bad=self._read(mappings={'1':'A'},profiles={'A':profile(wake='29:12')})
        self.assertEqual(bad.routine.status,'doğrulanamadı')
        old=self._read(mappings={'1':'A'},profiles={'A': {'wake':'07:00'}})
        self.assertEqual(old.routine.status,'doğrulanamadı')

    def test_assignment_reader_failure_never_falls_back_to_a_different_student(self):
        with patch(f'{MODULE}.load_assignments',side_effect=OSError('private')), \
             patch(f'{MODULE}.load_approved',return_value=None):
            result=read_planner_evidence(1,reference_day=DAY)
        self.assertEqual(result.routine.status,'doğrulanamadı')
        self.assertTrue(result.routine.warning)

    def test_approved_future_corruption_and_stale_warn(self):
        future=dict(approved(),created_on='2026-10-24')
        self.assertEqual(self._read(snapshot=future).approved_plan.status,'doğrulanamadı')
        corrupted=dict(approved(),placed_minutes=-1)
        self.assertEqual(self._read(snapshot=corrupted).approved_plan.status,'doğrulanamadı')
        stale=dict(approved(),created_on='2026-09-01')
        self.assertIn('7 günden eski',self._read(snapshot=stale).approved_plan.value)

    def test_no_cross_student_read_with_mismatched_id(self):
        for value in (0, -5, '1', True):
            with self.assertRaises(ValueError):
                read_planner_evidence(value,reference_day=DAY)

    def test_integrated_report_and_pdf_include_verified_routines_only(self):
        import fitz
        con=prepared()
        self.addCleanup(con.close)
        before=con.total_changes
        con.execute('PRAGMA query_only=ON')
        with patch(f'{MODULE}.load_assignments',return_value={'1':'A','2':'B'}), \
             patch(f'{MODULE}.load_profiles',return_value={'A':profile(),
                                                          'B':profile(_session_advisor_owner='2')}), \
             patch(f'{MODULE}.load_approved',return_value=approved()):
            result=read_integrated_report(con,1,reference_day=DAY)
        self.assertEqual(con.total_changes,before)
        self.assertEqual(result.section('Haftalık çalışma planı').status,'kayıt')
        self.assertEqual(result.section('Onaylı haftalık plan özeti').status,'kayıt')
        self.assertIn('330 dk',preview_text(result))
        with tempfile.TemporaryDirectory() as td:
            pdf=Path(td)/'integrated.pdf'
            export_integrated_pdf(result,str(pdf))
            with fitz.open(pdf) as f:
                contents=' '.join(p.get_text() for p in f)
                self.assertIn('Haftalık çalışma planı',contents)
                self.assertIn('Onaylı haftalık plan özeti',contents)
                self.assertIn('330 dk',contents)
                self.assertNotIn('Private Another Student',contents)

    def test_core_is_byte_identical_to_guard_baseline(self):
        import json
        expected=json.loads((ROOT/'tests/v42_protected_hashes.json').read_text())
        for file, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),digest,file)


if __name__=='__main__':
    unittest.main()
