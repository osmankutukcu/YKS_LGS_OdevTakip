"""V23.3 safe student/group topic assignment regression tests."""
import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path

from services.curriculum_v233 import (available_scoped_topics, available_books,
    list_assignments, create_assignment, change_status, ScopedAssignmentError)


def sample_db():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
    CREATE TABLE ders_tanimlari(id TEXT PRIMARY KEY, ad TEXT);
    INSERT INTO ders_tanimlari VALUES('fizik','Fizik');
    CREATE TABLE fizik(id INTEGER PRIMARY KEY, konu TEXT, ort_soru INT, ort_sure INT);
    INSERT INTO fizik VALUES (1,'Hareket',20,20),(2,'Elektrik',30,30);
    CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ana_grup TEXT, alt_grup TEXT);
    INSERT INTO ogrenci VALUES(1,'YKS','12-say'),(2,'YKS','12-ea');
    CREATE TABLE grup_konu_duzen(id INTEGER PRIMARY KEY, ana_grup TEXT,alt_grup TEXT,
      ders TEXT,konu TEXT,ort_soru INT,ort_sure INT);
    INSERT INTO grup_konu_duzen VALUES (1,'YKS','12-say','fizik','Elektrik',40,40),
      (2,'YKS','12-say','fizik','Yüksek Gerilim',20,20);
    CREATE TABLE ogrenci_konu_duzen(id INTEGER PRIMARY KEY,ogrenci_id INT,
      ders TEXT,konu TEXT,ort_soru INT,ort_sure INT);
    INSERT INTO ogrenci_konu_duzen VALUES(1,1,'fizik','Kişisel Tekrar',15,15);
    CREATE TABLE ogrenci_kitap(ogrenci_id INT,ders TEXT,kitap_ad TEXT);
    INSERT INTO ogrenci_kitap VALUES (1,'fizik','Fizik Kitabı'),(2,'fizik','Farklı Kitap');
    CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INT,ders TEXT,konu_id INT,konu_ad TEXT,kitap_ad TEXT,durum TEXT);
    INSERT INTO odev VALUES(10,1,'fizik',2,'Elektrik','Fizik Kitabı','tamam');
    CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INT,konu TEXT);
    INSERT INTO odev_satir VALUES(8,1,'Hareket');
    ''')
    con.commit()
    return con


class ScopedHomeworks(unittest.TestCase):
    def setUp(self):
        self.con=sample_db()
        self.start_legacy = list(self.con.execute('SELECT * FROM odev'))
        self.start_lines = list(self.con.execute('SELECT * FROM odev_satir'))
        self.today=(date.today()+timedelta(days=7)).isoformat()
        self.opts=available_scoped_topics(self.con,student_id=1,lesson='fizik')

    def tearDown(self):
        self.con.close()

    def assign(self, **kw):
        option=next(x for x in self.opts if x.title=='Yüksek Gerilim')
        args=dict(student_id=1,lesson='fizik',topic_reference=option.reference,
                  expected_title=option.title,book='Fizik Kitabı',minutes=35,due_date=self.today)
        args.update(kw)
        return create_assignment(self.con, **args)

    def test_effective_topics_only_scoped(self):
        self.assertTrue(any(x.title=='Yüksek Gerilim' and x.source=='Grup' for x in self.opts))
        self.assertTrue(any(x.title=='Kişisel Tekrar' and x.source=='Öğrenci' for x in self.opts))
        self.assertFalse(any(x.title=='Hareket' for x in self.opts))
        self.assertTrue(any(x.title=='Elektrik' and x.source=='Grup' for x in self.opts))

    def test_other_student_not_shown(self):
        self.assertEqual((),available_scoped_topics(self.con,student_id=2,lesson='fizik'))
        self.assertEqual(('Farklı Kitap',),available_books(self.con,student_id=2,lesson='fizik'))

    def test_preview_readonly_does_not_create_table(self):
        before=list(self.con.iterdump())
        list_assignments(self.con,student_id=1,lesson='fizik')
        available_scoped_topics(self.con,student_id=1,lesson='fizik')
        self.assertEqual(before,list(self.con.iterdump()))

    def test_assign_new_and_view_legacy_untouched(self):
        pk=self.assign()
        self.assertGreater(pk,0)
        records=list_assignments(self.con,student_id=1,lesson='fizik')
        self.assertEqual(1,len(records))
        self.assertEqual('devam',records[0].status)
        self.assertEqual('Grup',records[0].source)
        self.assertEqual(self.start_legacy,list(self.con.execute('SELECT * FROM odev')))
        self.assertEqual(self.start_lines,list(self.con.execute('SELECT * FROM odev_satir')))

    def test_reject_duplicate_open_task(self):
        self.assign()
        with self.assertRaises(ScopedAssignmentError): self.assign()
        self.assertEqual(1,len(list_assignments(self.con,student_id=1)))

    def test_wrong_student_group_fails(self):
        with self.assertRaises(ScopedAssignmentError): self.assign(student_id=2,book='Farklı Kitap')
        self.assertEqual((),list_assignments(self.con,student_id=1))

    def test_wrong_book_fails(self):
        with self.assertRaises(ScopedAssignmentError): self.assign(book='Farklı Kitap')
        self.assertEqual((),list_assignments(self.con,student_id=1))

    def test_forged_general_id_fails(self):
        with self.assertRaises(ScopedAssignmentError): self.assign(topic_reference='1')

    def test_topic_rename_blocks_stale_submission(self):
        self.con.execute("UPDATE grup_konu_duzen SET konu='Yeni Ad' WHERE id=2")
        self.con.commit()
        with self.assertRaises(ScopedAssignmentError): self.assign()
        self.assertFalse(self.con.execute("SELECT 1 FROM sqlite_master WHERE name='kapsam_odev_v233'").fetchone())

    def test_group_change_blocks_stale_submission(self):
        self.con.execute("UPDATE ogrenci SET alt_grup='12-ea' WHERE id=1")
        self.con.commit()
        with self.assertRaises(ScopedAssignmentError): self.assign()

    def test_ambiguous_duplicates_block_assignment(self):
        self.con.execute("INSERT INTO grup_konu_duzen VALUES (9,'YKS','12-say','fizik','Yüksek Gerilim',20,20)")
        self.con.commit()
        with self.assertRaises(ScopedAssignmentError): self.assign()

    def test_past_date_invalid(self):
        with self.assertRaises(ScopedAssignmentError): self.assign(due_date='2000-01-01')

    def test_invalid_duration(self):
        with self.assertRaises(ScopedAssignmentError): self.assign(minutes=1441)

    def test_wrong_student_cannot_finish(self):
        pk=self.assign()
        with self.assertRaises(ScopedAssignmentError): change_status(self.con,assignment_id=pk,student_id=2,new_status='tamam')
        self.assertEqual('devam',list_assignments(self.con,student_id=1)[0].status)

    def test_can_finish_and_reissue(self):
        pk=self.assign()
        self.assertTrue(change_status(self.con,assignment_id=pk,student_id=1,new_status='tamam'))
        self.assertEqual('tamam',list_assignments(self.con,student_id=1)[0].status)
        with self.assertRaises(ScopedAssignmentError): change_status(self.con,assignment_id=pk,student_id=1,new_status='iptal')
        self.assign()
        self.assertEqual(2,len(list_assignments(self.con,student_id=1)))

    def test_cancel_preserves_audit(self):
        pk=self.assign()
        change_status(self.con,assignment_id=pk,student_id=1,new_status='iptal')
        row=list_assignments(self.con,student_id=1)[0]
        self.assertEqual(pk,row.id)
        self.assertEqual('iptal',row.status)

    def test_student_filter_isolation(self):
        self.assign()
        self.assertEqual((),list_assignments(self.con,student_id=2))

    def test_invalid_student_rejected(self):
        with self.assertRaises(Exception): available_scoped_topics(self.con,student_id=999,lesson='fizik')

    def test_database_pending_other_write_is_not_committed(self):
        self.con.execute("UPDATE ogrenci SET alt_grup='12-ea' WHERE id=2")
        with self.assertRaises(ScopedAssignmentError): self.assign()
        self.assertTrue(self.con.in_transaction)
        self.con.rollback()

    def test_student360_shows_scoped_tasks_separately(self):
        src=(Path(__file__).resolve().parents[1]/'ui/student_workspace_panel_v21.py').read_text()
        self.assertIn('KAPSAMA ÖZEL ÖDEVLER (AYRI KAYIT)',src)
        self.assertIn('Bu rakamlar ana ödev kontrol toplamlarına dahil değildir.',src)

    def test_v232_preview_stays_and_old_checkbox_path_unchanged(self):
        root=Path(__file__).resolve().parents[1]
        preview=(root/'ui/curriculum_matrix_preview_v232.py').read_text()
        main=(root/'ui/homework_form.py').read_text()
        self.assertIn('Kapsama Özel Ödevler',preview)
        self.assertIn('self._tik_degisti(it, table, ders)',main)
        self.assertIn('SELECT ders, konu_id, kitap_ad, durum FROM odev WHERE ogrenci_id=?', main)


if __name__=='__main__': unittest.main()
