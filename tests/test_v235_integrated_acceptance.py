"""Integrated V23.5 acceptance: legacy + scoped rows never share a writable ID.

All mutation scenarios use temporary in-memory SQLite fixtures, never user DBs.
"""
from __future__ import annotations
from pathlib import Path
import sqlite3
import unittest

from services.stabilization_v235 import audit_connection
from services.student_workspace_v21 import read_control_counts
from services.curriculum_v234 import get_overview, set_scoped_control_status


def sample():
    con = sqlite3.connect(':memory:')
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
    CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, aktif INTEGER);
    INSERT INTO ogrenci VALUES(1,1),(2,1),(3,0);
    CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, durum TEXT,
                      silindi INTEGER DEFAULT 0, aktarildi INTEGER DEFAULT 0);
    INSERT INTO odev VALUES(11,1,'devam',0,0),(12,1,'tamam',0,0),
                            (13,1,'devam',1,0),(21,2,'devam',0,0);
    CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, odev_id INTEGER);
    INSERT INTO odev_satir VALUES(5,1,11),(6,2,21);
    CREATE TABLE kapsam_odev_v233(
       id INTEGER PRIMARY KEY,ogrenci_id INTEGER, ders TEXT, konu_ref TEXT,
       konu_adi TEXT, kapsam TEXT,kitap_ad TEXT,sure_dk INTEGER,bitis_tarihi TEXT,
       durum TEXT,olusturma_tarihi TEXT,bitis_islem_tarihi TEXT);
    CREATE UNIQUE INDEX uq_kapsam_aktif_v233
       ON kapsam_odev_v233(ogrenci_id,ders,konu_ref,kitap_ad) WHERE durum='devam';
    INSERT INTO kapsam_odev_v233 VALUES
     (31,1,'fizik','group|2','Dalgalar','Grup','A',20,'2026-12-01','devam','2026-10-12',NULL),
     (32,1,'fizik','student|9','Basınç','Öğrenci','B',40,'2026-12-01','tamam','2026-10-12','2026-10-12'),
     (41,2,'fizik','group|2','Dalgalar','Grup','A',30,'2026-12-01','devam','2026-10-12',NULL);
    ''')
    con.commit()
    return con


class IntegratedAcceptanceTests(unittest.TestCase):
    def setUp(self): self.con = sample()
    def tearDown(self): self.con.close()
    def report(self, **kw): return audit_connection(self.con, **kw)

    def test_clean_check_two_ledgers(self):
        r = self.report(include_students=True)
        self.assertTrue(r.passed)
        self.assertEqual((2,1,4,3),(r.active_students,r.inactive_students,r.legacy_rows,r.scoped_rows))
        self.assertEqual(0,r.orphaned_detail_links)
        self.assertEqual((1,1,0,1,1,1,0),tuple(vars(r.student_counters[0]).values())[1:])
        self.assertEqual(1,r.student_counters[1].legacy_open)
        self.assertEqual(1,r.student_counters[1].scoped_open)

    def test_default_report_does_not_contain_personal_identifiers(self):
        self.assertEqual((),self.report().student_counters)

    def test_no_ddl_or_record_change_on_read(self):
        dump = list(self.con.iterdump()); changes=self.con.total_changes
        self.report(); self.report(include_students=True)
        self.assertEqual(dump,list(self.con.iterdump()))
        self.assertEqual(changes,self.con.total_changes)

    def test_audit_permitted_query_only_mode(self):
        self.con.execute('PRAGMA query_only=ON')
        self.assertTrue(self.report().passed)

    def test_legacy_and_scoped_counters_agree_with_existing_readers(self):
        r=self.report(include_students=True)
        for counts in r.student_counters:
            original=read_control_counts(self.con,counts.student_id)
            scoped=get_overview(self.con,student_id=counts.student_id)
            self.assertEqual((original.open,original.completed,original.unknown,original.excluded),
                             (counts.legacy_open,counts.legacy_completed,counts.legacy_unknown,counts.legacy_excluded))
            self.assertEqual((scoped.open_count,scoped.completed_count,scoped.cancelled_count),
                             (counts.scoped_open,counts.scoped_completed,counts.scoped_cancelled))

    def test_toggling_scoped_task_does_not_change_legacy(self):
        legacy=list(self.con.execute('SELECT * FROM odev ORDER BY id'))
        set_scoped_control_status(self.con,student_id=1,assignment_id=31,expected_status='devam',new_status='tamam')
        r=self.report(include_students=True)
        self.assertTrue(r.passed)
        self.assertEqual(0,r.student_counters[0].scoped_open)
        self.assertEqual(2,r.student_counters[0].scoped_completed)
        self.assertEqual(legacy,list(self.con.execute('SELECT * FROM odev ORDER BY id')))
        set_scoped_control_status(self.con,student_id=1,assignment_id=31,expected_status='tamam',new_status='devam')
        self.assertEqual(1,self.report(include_students=True).student_counters[0].scoped_open)
        self.assertEqual(legacy,list(self.con.execute('SELECT * FROM odev ORDER BY id')))

    def test_orphan_detail_detected_without_fix(self):
        self.con.execute('INSERT INTO odev_satir VALUES(8,1,999)');self.con.commit()
        before=list(self.con.iterdump())
        r=self.report()
        self.assertFalse(r.passed)
        self.assertEqual(1,r.orphaned_detail_links)
        self.assertEqual(before,list(self.con.iterdump()))

    def test_wrong_student_link_detected(self):
        self.con.execute('INSERT INTO odev_satir VALUES(8,2,11)');self.con.commit()
        r=self.report()
        self.assertFalse(r.passed)
        self.assertEqual(1,r.wrong_student_detail_links)

    def test_missing_student_records_are_flagged(self):
        self.con.execute("INSERT INTO odev VALUES(50,999,'devam',0,0)")
        self.con.execute("INSERT INTO kapsam_odev_v233 VALUES (99,998,'F','r','t','Grup','A',20,'2026-12-01','devam','2026-10-12',NULL)")
        self.con.commit()
        r=self.report()
        self.assertEqual((1,1),(r.missing_legacy_students,r.missing_scoped_students))
        self.assertFalse(r.passed)

    def test_no_scoped_table_is_backward_compatible(self):
        self.con.execute('DROP TABLE kapsam_odev_v233');self.con.commit()
        r=self.report(include_students=True)
        self.assertTrue(r.passed)
        self.assertEqual(0,r.scoped_rows)
        self.assertTrue(any('henüz yok' in w for w in r.warnings))

    def test_invalid_schema_fails_closed(self):
        self.con.execute('DROP TABLE odev');self.con.commit()
        with self.assertRaisesRegex(ValueError,'Zorunlu'):
            self.report()

    def test_invalid_scoped_status_flags_problem(self):
        self.con.execute("UPDATE kapsam_odev_v233 SET durum='yanlış' WHERE id=31")
        self.con.commit()
        r=self.report()
        self.assertEqual(1,r.invalid_scoped_statuses)
        self.assertFalse(r.passed)

    def test_legacy_methods_and_separate_scoped_entrypoint_preserved(self):
        root=Path(__file__).resolve().parents[1]
        old=(root/'ui/odev_kontrol.py').read_text(encoding='utf-8')
        main=(root/'ui/homework_form.py').read_text(encoding='utf-8')
        self.assertIn('self.btnKaydet.clicked.connect(self._kaydet)',old)
        self.assertIn('self.tab.cellClicked.connect(self._chk_cell_click)',old)
        self.assertIn('ScopedControlDialogV234(self, student_id=self.ogr_id).exec()',old)
        self.assertIn('self._tik_degisti(it, table, ders)',main)

if __name__=='__main__':unittest.main()
