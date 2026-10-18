# V3.5.35 independent data correctness and release guards; no Qt or real PII.
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.canonical_homework_evidence_v3535 import scan_canonical_homework
from services.teacher_copilot_v5 import read_teacher_feed
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 18)


def fixture():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT,
            dogum_tarihi TEXT, veli_tel1 TEXT, aktif INTEGER);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            verilis_tarihi TEXT, bitis_tarihi TEXT);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER,
            ders TEXT, durum TEXT);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            kume_id INTEGER, odev_id INTEGER, ders TEXT, durum TEXT,
            silindi INTEGER DEFAULT 0, aktarildi INTEGER DEFAULT 0);
        INSERT INTO ogrenci VALUES(1,'Ada','Örnek',NULL,'05550000000',1);
        INSERT INTO ogrenci VALUES(2,'Mert','Örnek',NULL,NULL,1);
        INSERT INTO ogrenci VALUES(3,'Duru','Örnek',NULL,NULL,0);
        INSERT INTO odev_kume VALUES(11,1,'2026-10-01','2026-10-12');
        INSERT INTO odev_kume VALUES(12,2,'2026-10-01','2026-10-21');
        INSERT INTO odev VALUES(101,1,11,'Fizik','devam');
        INSERT INTO odev VALUES(102,2,12,'Kimya','tamam');
        CREATE TABLE coach_brief_review_v11(review_day TEXT, student_id INTEGER,
            suggestion_type TEXT, evidence_signature TEXT);
    ''')
    return con


class CanonicalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture()

    def tearDown(self):
        self.db.close()

    def scan(self):
        return scan_canonical_homework(self.db, today=DAY)

    def test_legacy_only_counts(self):
        r = self.scan()
        self.assertEqual(r['state'], 'OBSERVED')
        self.assertEqual((r['canonical_tasks'], r['overdue_open_tasks']), (2, 1))
        self.assertEqual(r['source_counts'], {'odev':2, 'odev_satir':0})
        self.assertEqual(len(r['priority_cards']), 1)

    def test_explicit_link_suppresses_one_parent(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(50,1,11,101,'Fizik','devam')")
        r=self.scan()
        self.assertEqual(r['canonical_tasks'],2)
        self.assertEqual(r['overdue_open_tasks'],1)
        self.assertEqual(r['source_counts'],{'odev':1,'odev_satir':1})

    def test_two_distinct_children_remain_two_tasks(self):
        self.db.executemany('INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(?,1,11,101,?,?)',
                            [(50,'Fizik','devam'),(51,'Fizik','tamam')])
        r=self.scan()
        self.assertEqual(r['canonical_tasks'],3)
        self.assertEqual(r['overdue_open_tasks'],1)
        self.assertEqual(r['completed_tasks'],2)

    def test_independent_child_other_group_is_new_task(self):
        self.db.execute('INSERT INTO odev_kume VALUES(13,1,?,?)',('2026-10-01','2026-10-10'))
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,ders,durum) VALUES(50,1,13,'Matematik','devam')")
        r=self.scan()
        self.assertEqual(r['canonical_tasks'],3)
        self.assertEqual(r['overdue_open_tasks'],2)

    def test_unlinked_child_same_group_is_ambiguous_not_double_counted(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,ders,durum) VALUES(50,1,11,'Fizik','devam')")
        r=self.scan()
        self.assertEqual(r['state'],'PARTIAL_COVERAGE')
        self.assertEqual(r['ambiguous_legacy_modern_groups'],1)
        self.assertEqual(r['ownership_or_ambiguity_review_students'],1)
        self.assertEqual(r['canonical_tasks'],1)
        self.assertEqual(r['priority_cards'],[])

    def test_wrong_parent_owner_blocks_both(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(50,2,11,101,'Fizik','devam')")
        r=self.scan()
        self.assertEqual(r['evaluated_students'],0)
        self.assertEqual(r['priority_cards'],[])

    def test_dangling_parent_and_group_excluded(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(50,1,999,999,'Fizik','devam')")
        r=self.scan()
        self.assertEqual(r['evaluated_students'],1)
        self.assertEqual(r['overdue_open_tasks'],0)
        self.assertGreaterEqual(r['rejected_rows'],1)

    def test_orphan_primary_group_excluded(self):
        self.db.execute("INSERT INTO odev VALUES(103,1,999,'Fizik','devam')")
        r=self.scan()
        self.assertEqual(r['evaluated_students'],1)
        self.assertEqual(r['overdue_open_tasks'],0)

    def test_child_can_inherit_verified_parent_due_date(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,odev_id,ders,durum) VALUES(50,1,101,'Fizik','devam')")
        r=self.scan()
        self.assertEqual(r['canonical_tasks'],2)
        self.assertEqual(r['overdue_open_tasks'],1)

    def test_linked_child_different_group_blocked(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(50,1,12,101,'Fizik','devam')")
        r=self.scan()
        self.assertEqual(r['evaluated_students'],0)

    def test_deleted_child_not_counted_and_parent_suppressed(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum,silindi) VALUES(50,1,11,101,'Fizik','devam',1)")
        r=self.scan()
        self.assertEqual(r['canonical_tasks'],1)
        self.assertEqual(r['overdue_open_tasks'],0)

    def test_independent_no_group_has_no_due_date(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,ders,durum) VALUES(50,1,'Matematik','devam')")
        r=self.scan()
        self.assertEqual(r['undated_count'],1)
        self.assertEqual(r['overdue_open_tasks'],1)
        self.assertEqual(r['state'],'PARTIAL_COVERAGE')

    def test_invalid_due_date_is_not_guessed(self):
        self.db.execute("UPDATE odev_kume SET bitis_tarihi='?' WHERE id=11")
        r=self.scan()
        self.assertEqual(r['undated_count'],1)
        self.assertEqual(r['overdue_open_tasks'],0)
        self.assertEqual(r['state'],'PARTIAL_COVERAGE')

    def test_unknown_status_excluded_not_done(self):
        self.db.execute("UPDATE odev SET durum='BİLİNMEYEN' WHERE id=101")
        r=self.scan()
        self.assertEqual(r['unknown_status_count'],1)
        self.assertEqual(r['canonical_tasks'],1)
        self.assertEqual(r['state'],'PARTIAL_COVERAGE')

    def test_no_pii_and_no_db_writes(self):
        before = self.db.total_changes
        r=self.scan()
        self.assertEqual(self.db.total_changes,before)
        self.assertNotIn('05550000000',json.dumps(r,ensure_ascii=False))
        self.assertTrue(r['no_automatic_write'])
        self.assertFalse(r['remote_verified'])

    def test_students_inactive_not_in_cards(self):
        self.db.execute('INSERT INTO odev_kume VALUES(14,3,?,?)',('2026-10-01','2026-10-10'))
        self.db.execute("INSERT INTO odev VALUES(103,3,14,'Tarih','devam')")
        r=self.scan()
        self.assertEqual(r['active_students'],2)
        self.assertEqual(r['overdue_students'],1)

    def test_multiple_undated_not_overdue(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,durum) VALUES(50,1,'devam')")
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,durum) VALUES(51,1,'devam')")
        r=self.scan()
        self.assertEqual(r['undated_count'],2)
        self.assertEqual(r['canonical_tasks'],4)

    def test_queue_bounded(self):
        for sid in range(20,50):
            self.db.execute('INSERT INTO ogrenci VALUES(?,?,?,NULL,NULL,1)',(sid,'Test',str(sid)))
            self.db.execute('INSERT INTO odev_kume VALUES(?,?,?,?)',(sid,sid,'2026-10-01','2026-10-05'))
            self.db.execute('INSERT INTO odev VALUES(?,?,?,?,?)',(sid,sid,sid,'Fizik','devam'))
        r=self.scan()
        self.assertEqual(r['priority_total'],31)
        self.assertEqual(len(r['priority_cards']),5)

    def test_missing_schema_rejected(self):
        self.db.execute('DROP TABLE odev_satir')
        with self.assertRaises(sqlite3.OperationalError): self.scan()

    def test_teacher_feed_same_snapshot_integration(self):
        # Set up V10/V11 minimum integration schema; coordinator must retain old fields.
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)/'fake.db'
            d = sqlite3.connect(dest)
            self.db.backup(d)
            d.close()
            r=read_teacher_feed(dest,today=DAY)
            c=r['cohort']['canonical_homework']
            self.assertEqual(c['state'],'OBSERVED')
            self.assertEqual(c['canonical_tasks'],2)
            self.assertEqual(r['cohort']['overdue_students'],1)

    def test_teacher_feed_never_promotes_blocked_student(self):
        # Legacy V10 may have a valid task plus a second corrupt modern link.
        # The new canonical quarantine also filters that student's V10 card.
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(50,2,11,101,'Fizik','devam')")
        self.db.commit()
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)/'fake.db'
            d = sqlite3.connect(dest)
            self.db.backup(d)
            d.close()
            feed = read_teacher_feed(dest, today=DAY)
            self.assertEqual(feed['cohort']['canonical_homework']['ownership_or_ambiguity_review_students'], 2)
            self.assertNotIn(1, [c['student_id'] for c in feed['cards']])

    def test_soft_deleted_parent_reconciliation_is_partial(self):
        self.db.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum,silindi) VALUES(50,1,11,101,'Fizik','devam',1)")
        r = self.scan()
        self.assertEqual(r['state'], 'PARTIAL_COVERAGE')

    def test_release_core_is_byte_identical(self):
        self.assertEqual(audit(ROOT)['status'],'PASS')

if __name__=='__main__': unittest.main()
