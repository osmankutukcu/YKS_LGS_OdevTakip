# -*- coding: utf-8 -*-
from __future__ import annotations
"""No Qt, no real student records, no modification of core code."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from services.release_readiness_v44 import summarize_orphan_candidates, v35_legacy_review, v44_preflight
from services.homework_integrity_v43 import digest

ROOT = Path(__file__).resolve().parents[1]


class V44ReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'synthetic.db'
        with sqlite3.connect(self.db) as con:
            con.executescript('''
                CREATE TABLE ogrenci(id INTEGER PRIMARY KEY);
                CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER);
                CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER);
                CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
                                        kume_id INTEGER, odev_id INTEGER);
                INSERT INTO ogrenci VALUES(1),(2);
                INSERT INTO odev_kume VALUES(10,1),(20,2);
                INSERT INTO odev VALUES(101,1,10),(102,1,10),(201,2,20);
                INSERT INTO odev_satir VALUES(1,1,10,999),(2,1,10,101),(3,2,20,NULL);
            ''')

    def test_v35_drift_not_auto_approved(self):
        report = v35_legacy_review(ROOT)
        self.assertIn(report['status'], ('PASS', 'BLOCK'))
        self.assertFalse(report['historical_gate_modified'])

    def test_valid_current_baseline_does_not_claim_release(self):
        report = v44_preflight(ROOT)
        self.assertEqual(report['base_protection']['status'], 'PASS')
        self.assertFalse(report['release_ready'])
        self.assertEqual(report['manual_windows_pilot'], 'NOT_VERIFIED')
        self.assertEqual(report['manual_macos_pilot'], 'NOT_VERIFIED')

    def test_orphan_multiple_candidates_review_not_autolink(self):
        old = digest(self.db)
        report = v44_preflight(ROOT, self.db, backup_ack=True)
        self.assertEqual(report['database_audit']['database_test'], 'REVIEW')
        self.assertEqual(report['orphan_candidate_review']['unresolved_orphan_rows'], 1)
        self.assertEqual(report['orphan_candidate_review']['multiple_same_student_cluster_candidates'], 1)
        self.assertFalse(report['orphan_candidate_review']['repair_performed'])
        self.assertFalse(report['release_ready'])
        self.assertEqual(digest(self.db), old)

    def test_orphan_no_candidate(self):
        with sqlite3.connect(self.db) as con:
            con.execute('DELETE FROM odev WHERE id IN (101,102)')
            con.execute('DELETE FROM odev_satir WHERE id=2')
        summary = summarize_orphan_candidates(self.db)
        self.assertEqual(summary['no_same_student_cluster_candidate'], 1)
        self.assertEqual(summary['one_same_student_cluster_candidate'], 0)
        self.assertEqual(summary['multiple_same_student_cluster_candidates'], 0)

    def test_orphan_one_candidate_still_not_proven(self):
        with sqlite3.connect(self.db) as con:
            con.execute('DELETE FROM odev WHERE id=102')
        summary = summarize_orphan_candidates(self.db)
        self.assertEqual(summary['one_same_student_cluster_candidate'], 1)
        self.assertFalse(summary['candidate_is_proof'])

    def test_dont_emit_personal_info(self):
        with sqlite3.connect(self.db) as con:
            con.execute('ALTER TABLE ogrenci ADD COLUMN ad TEXT')
            con.execute("UPDATE ogrenci SET ad='PERSONAL_DO_NOT_REPORT'")
        payload = json.dumps(v44_preflight(ROOT, self.db, backup_ack=True))
        self.assertNotIn('PERSONAL_DO_NOT_REPORT', payload)
        self.assertNotIn(str(self.db), payload)

    def test_db_ack_required(self):
        with self.assertRaisesRegex(ValueError, 'backup-ack'):
            v44_preflight(ROOT, self.db)

    def test_sidecar_disallowed(self):
        sidecar = Path(str(self.db)+'-wal')
        sidecar.write_bytes(b'unsafe')
        with self.assertRaisesRegex(ValueError, 'WAL/SHM'):
            v44_preflight(ROOT, self.db, backup_ack=True)

    def test_unexpected_db_corruption_fails_closed(self):
        self.db.write_bytes(b'X'*300)
        with self.assertRaisesRegex(ValueError, 'SQLite'):
            v44_preflight(ROOT, self.db, backup_ack=True)

    def test_mutation_safety_v35_gate_fingerprints_unmodified(self):
        source = (ROOT/'tools/v35_release_gate.py').read_bytes()
        before = hashlib.sha256(source).hexdigest()
        v35_legacy_review(ROOT)
        self.assertEqual(hashlib.sha256((ROOT/'tools/v35_release_gate.py').read_bytes()).hexdigest(), before)


if __name__ == '__main__': unittest.main()
