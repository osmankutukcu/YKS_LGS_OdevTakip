# -*- coding: utf-8 -*-
"""No Qt, no live students, no network and no database writes."""
from __future__ import annotations
from datetime import date
import json
import sqlite3
import unittest

from services.report_integrity_v3590 import (
    audit_student_integrity, audit_cohort_report_sources, explain_cohort_audit,
)
from tests.test_v3535_canonical_evidence import fixture

DAY = date(2026, 10, 21)


class V3590EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.con = fixture()
        self.addCleanup(self.con.close)

    def _check(self, student=1):
        return audit_student_integrity(self.con, student)

    def test_clean_ownership_is_not_a_statement_of_exam_success(self):
        result = self._check()
        self.assertEqual(result.state, 'checked')
        self.assertEqual(result.examined, 1)
        self.assertIn('sınav başarısı ölçülmedi', ' '.join(result.reasons))

    def test_explicit_parent_link_is_evidence_without_double_count(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(51,1,11,101,'Fizik','devam')")
        self.assertEqual(self._check().state, 'checked')
        self.assertEqual(self._check().linked_parents, 1)
        group = audit_cohort_report_sources(self.con, reference_day=DAY)
        self.assertEqual(group['details']['canonical_tasks'], 2)

    def test_verified_parent_can_supply_missing_child_group_date(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(51,1,NULL,101,'Fizik','devam')")
        r = self._check()
        self.assertEqual(r.state, 'checked')
        self.assertEqual(r.undated, 0)

    def test_parent_group_owner_mismatch_is_not_accepted(self):
        self.con.execute("UPDATE odev_kume SET ogrenci_id=2 WHERE id=11")
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(51,1,NULL,101,'Fizik','devam')")
        self.assertEqual(self._check().state, 'review')

    def test_unlinked_child_same_group_requires_manual_review(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,ders,durum) VALUES(51,1,11,'Fizik','devam')")
        result = self._check()
        self.assertEqual(result.state, 'review')
        self.assertEqual(result.ambiguous_groups, 1)

    def test_child_wrong_student_but_parent_belongs_to_student_is_detected(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(51,2,11,101,'Fizik','devam')")
        self.assertEqual(self._check().owner_conflicts, 1)
        self.assertEqual(self._check().state, 'review')

    def test_unrelated_students_not_in_student_notes(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(51,2,12,102,'Kimya','devam')")
        self.assertEqual(self._check(1).state, 'checked')

    def test_orphan_group_and_parent_blocked(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(51,1,999,999,'Fizik','devam')")
        self.assertEqual(self._check().state, 'review')

    def test_undated_and_unknown_state_are_limited_not_failure(self):
        self.con.execute("UPDATE odev_kume SET bitis_tarihi=NULL WHERE id=11")
        self.con.execute("UPDATE odev SET durum='devam' WHERE id=101")
        self.assertEqual(self._check().undated, 1)
        self.con.execute("UPDATE odev SET durum='?' WHERE id=101")
        r = self._check()
        self.assertEqual(r.unknown_status, 1)
        self.assertEqual(r.state, 'limited')

    def test_inactive_is_not_misclassified_or_exposed(self):
        with self.assertRaises(ValueError):
            self._check(3)

    def test_invalid_identity_rejected(self):
        for value in (0, -1, True, '1', 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self._check(value)

    def test_limit_does_not_claim_complete_check(self):
        with self.assertRaises(ValueError):
            audit_student_integrity(self.con, 1, max_rows=0)
        res = audit_student_integrity(self.con, 1, max_rows=1)
        self.assertEqual(res.state, 'checked')
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,ders,durum) VALUES(51,1,11,'Fizik','devam')")
        r = audit_student_integrity(self.con, 1, max_rows=1)
        self.assertEqual(r.state, 'limited')
        self.assertEqual(r.examined, 0)

    def test_legacy_without_explicit_parent_column_is_supported(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,aktif INTEGER);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,durum TEXT);
          CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,durum TEXT);
          INSERT INTO ogrenci VALUES(1,1);
          INSERT INTO odev_kume VALUES(5,1,'2026-10-20');
          INSERT INTO odev VALUES(10,1,5,'devam');
        ''')
        self.assertEqual(audit_student_integrity(db, 1).state, 'checked')

    def test_missing_schema_visible_not_guessed(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        result = audit_student_integrity(db, 1)
        self.assertEqual(result.state, 'unavailable')
        result2 = audit_cohort_report_sources(db, reference_day=DAY)
        self.assertEqual(result2['state'], 'unavailable')

    def test_large_cohort_is_limited_without_running_full_scan(self):
        a = audit_cohort_report_sources(self.con, reference_day=DAY, max_rows=1)
        self.assertEqual(a['state'], 'limited')
        self.assertIsNone(a['details'])

    def test_source_audit_no_personally_identifying_data_and_no_mutations(self):
        self.con.execute('PRAGMA query_only=ON')
        before=self.con.total_changes
        result = audit_cohort_report_sources(self.con, reference_day=DAY)
        display = explain_cohort_audit(result)
        self.assertEqual(result['mode'], 'canonical')
        self.assertIn('Geçerli kanıt görevleri', display)
        self.assertNotIn('Ada', display)
        self.assertNotIn('Mert', display)
        self.assertNotIn('05550000000', json.dumps(result,ensure_ascii=False))
        self.assertEqual(self.con.total_changes, before)

    def test_snapshot_different_time_ranges_are_explicit(self):
        text = explain_cohort_audit(audit_cohort_report_sources(self.con, reference_day=DAY))
        self.assertIn('tarih kapsamı', text)
        self.assertIn('Kayıtlar değiştirilmedi', text)


if __name__ == '__main__':
    unittest.main()
