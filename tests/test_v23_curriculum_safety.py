"""V23 müfredat çekirdeği regresyonu (PyQt6 gerekmez, gerçek DB gerekmez)."""
import sqlite3
import unittest

from services.curriculum_v23 import (
    CurriculumSafetyError, topic_impact, save_topics, rename_topic_safe,
    delete_unused_topics,
)
from utils.konu_rename import rename_topic


def make_db():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
        CREATE TABLE ders_tanimlari(id TEXT PRIMARY KEY, ad TEXT);
        INSERT INTO ders_tanimlari VALUES('fizik','Fizik');
        CREATE TABLE fizik(id INTEGER PRIMARY KEY, konu TEXT NOT NULL,
                           ort_soru INTEGER, ort_sure INTEGER);
        INSERT INTO fizik VALUES(1,'Elektrostatik',20,35);
        INSERT INTO fizik VALUES(2,'Basınç',15,25);
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, alt_grup TEXT);
        INSERT INTO ogrenci VALUES(1,'A','12-say'),(2,'B','12-ea');
        CREATE TABLE grup_konu_duzen(id INTEGER PRIMARY KEY, ana_grup TEXT,
            alt_grup TEXT, ders TEXT, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
        INSERT INTO grup_konu_duzen VALUES(1,'YKS','12-say','fizik','Elektrik',25,30);
        CREATE TABLE ogrenci_konu_duzen(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            ders TEXT, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
        INSERT INTO ogrenci_konu_duzen VALUES(1,1,'fizik','Devreler',25,40);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            ders TEXT, konu_id INTEGER, konu_ad TEXT, durum TEXT);
        INSERT INTO odev VALUES(1,1,'fizik',1,'Elektrostatik','devam');
        INSERT INTO odev VALUES(2,2,'fizik',1,'Elektrostatik','tamam');
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
            ders TEXT, konu TEXT);
        INSERT INTO odev_satir VALUES(1,1,'fizik','Elektrostatik');
        CREATE TABLE konu_istatistik(ders TEXT, konu TEXT, tamam INTEGER,
            yapilmadi INTEGER, PRIMARY KEY(ders,konu));
        INSERT INTO konu_istatistik VALUES('fizik','Elektrostatik',5,2);
        CREATE TABLE cohort_kitap_kapsam(ders TEXT, kitap TEXT, konu TEXT,
            done_count INTEGER, student_count INTEGER);
    ''')
    return con


class CurriculumSafetyV23(unittest.TestCase):
    def setUp(self):
        self.con = make_db()

    def tearDown(self):
        self.con.close()

    def values(self, q, params=()):
        return [tuple(row) for row in self.con.execute(q, params)]

    def test_impact_is_read_only(self):
        before = self.values('SELECT * FROM odev')
        result = topic_impact(self.con, scope='Genel', ders='fizik', topic_id=1, name='Elektrostatik')
        self.assertTrue(result['has_history'])
        self.assertEqual(2, result['references']['odev'])
        self.assertEqual(before, self.values('SELECT * FROM odev'))

    def test_rename_keeps_topic_id_all_assignments_and_statistics(self):
        result = rename_topic_safe(self.con, scope='Genel', ders='fizik', old_name='Elektrostatik',
                                   new_name='Elektriklenme', topic_id=1)
        self.assertTrue(result['history_preserved'])
        self.assertEqual([(1,'Elektriklenme')], self.values('SELECT id,konu FROM fizik WHERE id=1'))
        self.assertEqual([(1,1,'Elektrostatik'), (2,2,'Elektrostatik')],
                         self.values('SELECT id, ogrenci_id,konu_ad FROM odev ORDER BY id'))
        self.assertEqual([(5,2)], self.values('SELECT tamam,yapilmadi FROM konu_istatistik'))

    def test_old_api_rename_rejects_historical_writes_without_losing_stats(self):
        with self.assertRaises(CurriculumSafetyError):
            rename_topic(self.con, ders='fizik', old_name='Elektrostatik',
                         new_name='Elektriklenme', update_history=True)
        self.assertEqual([(5,2)], self.values('SELECT tamam,yapilmadi FROM konu_istatistik'))
        self.assertEqual('Elektrostatik', self.values('SELECT konu FROM fizik WHERE id=1')[0][0])

    def test_group_rename_does_not_touch_all_students(self):
        rename_topic_safe(self.con, scope='Grup', ders='fizik', old_name='Elektrik',
                          new_name='Elektriklenme', topic_id=1, ana_grup='YKS', alt_grup='12-say')
        self.assertEqual('Elektriklenme', self.values('SELECT konu FROM grup_konu_duzen WHERE id=1')[0][0])
        self.assertEqual(2, self.con.execute('SELECT COUNT(*) FROM odev WHERE konu_ad="Elektrostatik"').fetchone()[0])

    def test_rename_existing_target_blocked_atomically(self):
        with self.assertRaises(CurriculumSafetyError):
            rename_topic_safe(self.con, scope='Genel', ders='fizik',
                              old_name='Elektrostatik', new_name='Basınç', topic_id=1)
        self.assertEqual('Elektrostatik', self.values('SELECT konu FROM fizik WHERE id=1')[0][0])

    def test_delete_protects_used_topic_and_batch(self):
        with self.assertRaises(CurriculumSafetyError):
            delete_unused_topics(self.con, scope='Genel', ders='fizik', ids=[1,2])
        self.assertEqual(2, self.con.execute('SELECT COUNT(*) FROM fizik').fetchone()[0])

    def test_unused_topic_can_be_removed(self):
        self.assertEqual(1, delete_unused_topics(self.con, scope='Genel', ders='fizik', ids=[2]))
        self.assertEqual([('Elektrostatik',)], self.values('SELECT konu FROM fizik'))

    def test_save_updates_targets_but_not_name_or_id(self):
        save_topics(self.con, scope='Genel', ders='fizik', rows=[
            {'id':1,'konu':'Elektrostatik','ort_soru':30,'ort_sure':45},
            {'id':2,'konu':'Basınç','ort_soru':15,'ort_sure':25}],
            expected_names={1:'Elektrostatik',2:'Basınç'})
        self.assertEqual((1,30,45), self.values('SELECT id,ort_soru,ort_sure FROM fizik WHERE id=1')[0])

    def test_inline_rename_rejected_without_side_effect(self):
        with self.assertRaises(CurriculumSafetyError):
            save_topics(self.con, scope='Genel', ders='fizik', rows=[
                {'id':1,'konu':'DEĞİŞTİRİLDİ','ort_soru':999,'ort_sure':999},
                {'id':2,'konu':'Basınç','ort_soru':0,'ort_sure':1}],
                expected_names={1:'Elektrostatik',2:'Basınç'})
        self.assertEqual((20,35), self.values('SELECT ort_soru,ort_sure FROM fizik WHERE id=1')[0])

    def test_duplicate_rows_abort_no_partial_insert(self):
        with self.assertRaises(CurriculumSafetyError):
            save_topics(self.con, scope='Genel', ders='fizik', rows=[
                {'konu':'Yeni','ort_soru':1}, {'konu':'yeni','ort_soru':3}])
        self.assertEqual(2, self.con.execute('SELECT COUNT(*) FROM fizik').fetchone()[0])

    def test_group_save_updates_existing_by_id_without_duplication(self):
        save_topics(self.con, scope='Grup', ders='fizik',ana_grup='YKS',alt_grup='12-say',
                    rows=[{'id':1,'konu':'Elektrik','ort_soru':40,'ort_sure':60}],
                    expected_names={1:'Elektrik'})
        self.assertEqual([(1,'Elektrik',40)],
                         self.values('SELECT id,konu,ort_soru FROM grup_konu_duzen'))

    def test_student_scope_cannot_edit_other_student_row(self):
        with self.assertRaises(CurriculumSafetyError):
            save_topics(self.con, scope='Öğrenci', ders='fizik', ogrenci_id=2,
                        rows=[{'id':1,'konu':'Devreler','ort_soru':50}],
                        expected_names={1:'Devreler'})
        self.assertEqual(25, self.values('SELECT ort_soru FROM ogrenci_konu_duzen')[0][0])

    def test_invalid_ders_table_rejected(self):
        with self.assertRaises(CurriculumSafetyError):
            save_topics(self.con, scope='Genel',ders='odev',rows=[{'konu':'hack'}])

    def test_stale_loaded_name_prevents_overwriting(self):
        with self.assertRaises(CurriculumSafetyError):
            save_topics(self.con, scope='Genel',ders='fizik',
                        rows=[{'id':1,'konu':'Elektrostatik','ort_soru':30}],
                        expected_names={1:'Old'})

    def test_same_topic_case_change_preserves_id(self):
        rename_topic_safe(self.con, scope='Genel', ders='fizik',
                          old_name='Basınç', new_name='BASINÇ', topic_id=2)
        self.assertEqual([(2, 'BASINÇ')], self.values('SELECT id,konu FROM fizik WHERE id=2'))

    def test_saved_topic_cannot_duplicate_renamed_name_across_open_windows(self):
        with self.assertRaises(CurriculumSafetyError):
            save_topics(self.con, scope='Genel',ders='fizik',
                        rows=[{'konu':'BASINÇ','ort_soru':13}])
        self.assertEqual(2, self.values('SELECT COUNT(*) FROM fizik')[0][0])

    def test_multiscope_identical_name_not_inferred_same_id(self):
        save_topics(self.con, scope='Öğrenci',ders='fizik',ogrenci_id=1,
                    rows=[{'konu':'Elektrostatik','ort_soru':10}])
        self.assertEqual(1, self.values("SELECT COUNT(*) FROM ogrenci_konu_duzen WHERE konu='Elektrostatik'")[0][0])
        self.assertEqual(2, self.values('SELECT COUNT(*) FROM odev')[0][0])


if __name__ == '__main__':
    unittest.main()
