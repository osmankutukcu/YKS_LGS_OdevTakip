# -*- coding: utf-8 -*-
"""V27 read-only sidebar: evidence, privacy, flags and legacy preservation."""
import os
import sqlite3
import unittest
from unittest.mock import patch
from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v27.presenter import sidebar_data
from services.adaptive_coaching_v27.flags import enabled


class AdaptiveSidebarV27Test(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.con.execute('PRAGMA foreign_keys=ON')
        self.con.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
                                 verilis_tarihi TEXT, bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER,
                            ders TEXT, konu_ad TEXT, kitap_ad TEXT,
                            saat_dk INTEGER, durum TEXT, aciklama TEXT);
          INSERT INTO ogrenci VALUES (1,'Öğrenci','Bir'),(2,'Öğrenci','İki');
          INSERT INTO odev_kume VALUES(15,1,'2026-10-05','2026-10-15'),
                                      (16,2,'2026-10-05','2026-10-15');
          INSERT INTO odev VALUES(21,15,1,'Fizik','Enerji','345',40,'tamam','Asıl veri'),
                                 (22,15,1,'Fizik','Basınç','345',35,'devam','Asıl veri'),
                                 (23,16,2,'Fizik','Enerji','345',45,'devam','Başka öğrenci');
        ''')

    def tearDown(self):
        self.con.close()

    def original(self):
        return [tuple(r) for r in self.con.execute('SELECT * FROM odev ORDER BY id')]

    def test_no_table_means_no_measured_learning_no_mutations(self):
        before = self.original()
        model = sidebar_data(self.con, 1, today='2026-10-13')
        self.assertFalse(model['has_evidence_storage'])
        self.assertEqual(model['evidence_count'], 0)
        self.assertEqual(model['suggested_review_percent'], 30)
        self.assertEqual(model['groups']['Aralıklı tekrar'], [])
        self.assertIn('başlatılmadı', model['status'])
        self.assertFalse(self.con.execute("SELECT name FROM sqlite_master WHERE name LIKE 'adaptive_%'").fetchone())
        self.assertEqual(before, self.original())

    def test_readonly_sqlite_connection_and_no_ticked_mastery(self):
        self.con.execute('PRAGMA query_only=ON')
        model = sidebar_data(self.con, 1)
        self.assertEqual(model['evidence_count'], 0)
        self.assertEqual(model['metrics'], {})
        with self.assertRaises(sqlite3.OperationalError):
            self.con.execute("UPDATE odev SET durum='devam' WHERE id=21")

    def test_observations_change_decision_but_not_legacy(self):
        engine.ensure_schema(self.con)
        before = self.original()
        engine.save_observation(self.con, 1,'Fizik','Enerji',homework_id=21,
                                correct=2,wrong=6,blank=1,
                                observed_on='2026-10-01',subskill='Enerji dönüşümleri')
        model = sidebar_data(self.con,1,today='2026-10-13')
        self.assertEqual(model['evidence_count'], 1)
        self.assertEqual(model['metrics']['support'], 1)
        self.assertTrue(model['groups']['Aralıklı tekrar'])
        self.assertTrue(model['groups']['Hedefli destek'])
        self.assertEqual(model['groups']['Hedefli destek'][0]['source'], 'V25 tanılayıcı gözlemleri')
        self.assertEqual(before, self.original())
        second = sidebar_data(self.con,2,today='2026-10-13')
        self.assertEqual(second['evidence_count'], 0)
        self.assertFalse(second['groups']['Hedefli destek'])

    def test_profile_replaces_70_30_not_reported_as_history(self):
        engine.ensure_schema(self.con)
        engine.save_preferences(self.con,1,dict(review_percent=40,weekly_minutes=380,max_session_minutes=55))
        model = sidebar_data(self.con,1)
        self.assertEqual(model['suggested_current_percent'],60)
        self.assertEqual(model['suggested_review_percent'],40)
        self.assertEqual(model['weekly_minutes'],380)
        self.assertEqual(model['suggested_session_minutes'],55)

    def test_blocker_window_and_student_isolation(self):
        engine.ensure_schema(self.con)
        engine.save_blocker(self.con,1,'Zaman yönetimi','Haftalık görev çok uzun',resolution='Ödevleri küçült')
        model = sidebar_data(self.con,1,today='2026-10-13')
        other = sidebar_data(self.con,2,today='2026-10-13')
        self.assertTrue(any(b['reason']=='Zaman yönetimi' for b in model['blockers']))
        self.assertEqual(other['blockers'],[])

    def test_invalid_student(self):
        with self.assertRaises(ValueError):
            sidebar_data(self.con, 500)

    def test_feature_flag_is_fully_optional(self):
        with patch.dict(os.environ, {'EDUTRACK_ADAPTIVE_V27':'0'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ, {'EDUTRACK_ADAPTIVE_V27':'1',
                                     'EDUTRACK_ADAPTIVE_V26':'1',
                                     'EDUTRACK_ADAPTIVE_V25':'1'}):
            self.assertTrue(enabled())

    def test_no_legacy_dml_in_presenter(self):
        import inspect
        from services.adaptive_coaching_v27 import presenter
        body = inspect.getsource(presenter)
        self.assertNotIn('UPDATE odev ',body)
        self.assertNotIn('DELETE FROM odev',body)
        self.assertNotIn('CREATE TABLE',body)


if __name__ == '__main__':
    unittest.main()
