"""V23.4 scoped control: legacy preservation and transaction regression tests."""
import sqlite3
import unittest
from pathlib import Path

from services.curriculum_v234 import (
    ScopedControlError, get_overview, set_scoped_control_status, status_history,
)


def sample():
    c=sqlite3.connect(':memory:')
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.executescript('''
    CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT);
    INSERT INTO ogrenci VALUES (1,'Ali'),(2,'Ayşe');
    CREATE TABLE odev(id INT PRIMARY KEY, ogrenci_id INT, durum TEXT);
    INSERT INTO odev VALUES(10,1,'devam'),(11,2,'tamam');
    CREATE TABLE odev_satir(id INT PRIMARY KEY, odev_id INT, durum TEXT);
    INSERT INTO odev_satir VALUES (9,10,'devam');
    CREATE TABLE kapsam_odev_v233(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ogrenci_id INTEGER NOT NULL REFERENCES ogrenci(id),
      ders TEXT NOT NULL, konu_ref TEXT NOT NULL, konu_adi TEXT NOT NULL,
      kapsam TEXT NOT NULL CHECK(kapsam IN ('Grup','Öğrenci')),
      kitap_ad TEXT NOT NULL, sure_dk INTEGER NOT NULL,
      bitis_tarihi TEXT NOT NULL, durum TEXT NOT NULL DEFAULT 'devam'
        CHECK(durum IN ('devam','tamam','iptal')),
      olusturma_tarihi TEXT NOT NULL, bitis_islem_tarihi TEXT
    );
    CREATE UNIQUE INDEX uq_kapsam_aktif_v233
      ON kapsam_odev_v233(ogrenci_id,ders,konu_ref,kitap_ad) WHERE durum='devam';
    INSERT INTO kapsam_odev_v233 VALUES
      (1,1,'fizik','Grup|fizik|2','Dalgalar','Grup','Kitap A',40,'2026-12-01','devam','2026-10-12',NULL),
      (2,1,'fizik','Öğrenci|fizik|3','Basınç','Öğrenci','Kitap B',30,'2026-12-04','tamam','2026-10-12','2026-10-12'),
      (3,2,'fizik','Grup|fizik|2','Dalgalar','Grup','Kitap A',50,'2026-12-05','devam','2026-10-12',NULL);
    ''')
    c.commit()
    return c


class ScopedControlTests(unittest.TestCase):
    def setUp(self):
        self.c=sample()
        self.legacy=list(self.c.execute('SELECT * FROM odev'))
        self.old_lines=list(self.c.execute('SELECT * FROM odev_satir'))
    def tearDown(self): self.c.close()

    def assert_legacy_intact(self):
        self.assertEqual(self.legacy,list(self.c.execute('SELECT * FROM odev')))
        self.assertEqual(self.old_lines,list(self.c.execute('SELECT * FROM odev_satir')))

    def test_single_student_view_and_counts(self):
        o=get_overview(self.c,student_id=1)
        self.assertEqual(2,len(o.assignments))
        self.assertEqual((1,1,0),(o.open_count,o.completed_count,o.cancelled_count))
        self.assertEqual({1,2},{r.id for r in o.assignments})
        self.assert_legacy_intact()
    def test_other_student_isolated(self):
        o=get_overview(self.c,student_id=2)
        self.assertEqual([3],[r.id for r in o.assignments]);self.assertEqual(1,o.open_count)
    def test_read_does_not_create_log(self):
        before=list(self.c.iterdump())
        get_overview(self.c,student_id=1)
        status_history(self.c,student_id=1,assignment_id=1)
        self.assertEqual(before,list(self.c.iterdump()))
    def test_legacy_empty_scoped_table_read(self):
        self.c.execute('DROP TABLE kapsam_odev_v233');self.c.commit()
        self.assertEqual(0,get_overview(self.c,student_id=1).open_count)
    def test_complete_with_audit_and_legacy_preserved(self):
        self.assertTrue(set_scoped_control_status(self.c,student_id=1,assignment_id=1,
                          expected_status='devam',new_status='tamam'))
        self.assertEqual('tamam',self.c.execute('SELECT durum FROM kapsam_odev_v233 WHERE id=1').fetchone()[0])
        self.assertEqual(1,len(status_history(self.c,student_id=1,assignment_id=1)))
        self.assert_legacy_intact()
    def test_cancel(self):
        set_scoped_control_status(self.c,student_id=1,assignment_id=1,
                                   expected_status='devam',new_status='iptal')
        self.assertEqual('iptal',self.c.execute('SELECT durum FROM kapsam_odev_v233 WHERE id=1').fetchone()[0])
    def test_undo_complete_preserves_old_end_date_in_audit(self):
        set_scoped_control_status(self.c,student_id=1,assignment_id=2,
                                   expected_status='tamam',new_status='devam')
        self.assertIsNone(self.c.execute('SELECT bitis_islem_tarihi FROM kapsam_odev_v233 WHERE id=2').fetchone()[0])
        raw=self.c.execute('SELECT onceki_bitis_islem_tarihi FROM kapsam_odev_kontrol_log_v234').fetchone()[0]
        self.assertEqual('2026-10-12',raw)
    def test_two_steps_and_history(self):
        set_scoped_control_status(self.c,student_id=1,assignment_id=1,expected_status='devam',new_status='tamam')
        set_scoped_control_status(self.c,student_id=1,assignment_id=1,expected_status='tamam',new_status='devam')
        self.assertEqual(2,len(status_history(self.c,student_id=1,assignment_id=1)))
    def test_wrong_student_no_log(self):
        with self.assertRaises(ScopedControlError):
            set_scoped_control_status(self.c,student_id=2,assignment_id=1,expected_status='devam',new_status='tamam')
        self.assertFalse(self.c.execute('SELECT 1 FROM sqlite_master WHERE name="kapsam_odev_kontrol_log_v234"').fetchone())
        self.assert_legacy_intact()
    def test_stale_expected_state_fails(self):
        with self.assertRaises(ScopedControlError):
            set_scoped_control_status(self.c,student_id=1,assignment_id=2,expected_status='devam',new_status='iptal')
    def test_invalid_transition_fails(self):
        with self.assertRaises(ScopedControlError):
            set_scoped_control_status(self.c,student_id=1,assignment_id=2,expected_status='tamam',new_status='iptal')
    def test_duplicate_on_undo_rolls_back(self):
        self.c.execute('''INSERT INTO kapsam_odev_v233
         (id,ogrenci_id,ders,konu_ref,konu_adi,kapsam,kitap_ad,sure_dk,bitis_tarihi,durum,olusturma_tarihi)
         VALUES(4,1,'fizik','Öğrenci|fizik|3','Basınç','Öğrenci','Kitap B',45,'2026-12-04','devam','2026-10-12')'''); self.c.commit()
        with self.assertRaises(ScopedControlError):
            set_scoped_control_status(self.c,student_id=1,assignment_id=2,expected_status='tamam',new_status='devam')
        self.assertEqual('tamam',self.c.execute('SELECT durum FROM kapsam_odev_v233 WHERE id=2').fetchone()[0])
        self.assertFalse(self.c.execute('SELECT 1 FROM sqlite_master WHERE name="kapsam_odev_kontrol_log_v234"').fetchone())
    def test_unrelated_open_transaction_not_committed(self):
        self.c.execute('UPDATE ogrenci SET ad=? WHERE id=2',('Değişim',))
        with self.assertRaises(ScopedControlError):
            set_scoped_control_status(self.c,student_id=1,assignment_id=1,expected_status='devam',new_status='tamam')
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()
        self.assertEqual('Ayşe',self.c.execute('SELECT ad FROM ogrenci WHERE id=2').fetchone()[0])
    def test_audit_failure_rolls_back_update(self):
        self.c.execute('''CREATE TABLE kapsam_odev_kontrol_log_v234 (
          id INTEGER PRIMARY KEY, kapsam_odev_id INTEGER,ogrenci_id INTEGER,
          onceki_durum TEXT,yeni_durum TEXT,onceki_bitis_islem_tarihi TEXT,
          yeni_bitis_islem_tarihi TEXT,islem_zamani TEXT,kaynak TEXT)''')
        self.c.execute('''CREATE TRIGGER block_audit BEFORE INSERT ON kapsam_odev_kontrol_log_v234
          BEGIN SELECT RAISE(ABORT,'Audit failed'); END''')
        self.c.commit()
        with self.assertRaises(ScopedControlError):
            set_scoped_control_status(self.c,student_id=1,assignment_id=1,expected_status='devam',new_status='tamam')
        self.assertEqual('devam',self.c.execute('SELECT durum FROM kapsam_odev_v233 WHERE id=1').fetchone()[0])
    def test_control_is_optional_and_modal(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'ui/odev_kontrol.py').read_text(encoding='utf-8')
        self.assertIn('ScopedControlDialogV234(self, student_id=self.ogr_id).exec()',source)
        self.assertIn('self.btnKaydet.clicked.connect(self._kaydet)',source)
        self.assertIn('self.tab.cellClicked.connect(self._chk_cell_click)',source)
        ui=(root/'ui/scoped_control_v234.py').read_text(encoding='utf-8')
        self.assertIn('setModal(True)',ui)
        self.assertIn('kapsam',ui.lower())

if __name__=='__main__': unittest.main()
