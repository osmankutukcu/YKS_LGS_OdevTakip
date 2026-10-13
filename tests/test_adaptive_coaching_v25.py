# -*- coding: utf-8 -*-
"""V25 core contract tests. Run: python -m unittest tests/test_adaptive_coaching_v25.py"""
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from services.adaptive_coaching_v25 import engine


class AdaptiveCoachingV25Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER NOT NULL,
                                 verilis_tarihi TEXT, bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER,
                            ders TEXT, konu_ad TEXT, kitap_ad TEXT,
                            saat_dk INTEGER, durum TEXT, aciklama TEXT);
          INSERT INTO ogrenci(id,ad,soyad) VALUES (1,'Deneme','Bir'),(2,'Deneme','İki');
          INSERT INTO odev_kume(id,ogrenci_id,verilis_tarihi) VALUES
              (11,1,'2026-09-22'),(12,2,'2026-09-28');
          INSERT INTO odev(id,kume_id,ogrenci_id,ders,konu_ad,kitap_ad,saat_dk,durum,aciklama)
          VALUES (21,11,1,'Fizik','Madde ve Özellikleri','Bilgi Sarmal',25,'devam','Korunmalı'),
                 (22,11,1,'Matematik','Fonksiyonlar','345',25,'yapildi','Korunmalı'),
                 (23,12,2,'Fizik','Madde ve Özellikleri','345',20,'devam','Başka öğrenci');
        ''')
        engine.ensure_schema(self.db)

    def tearDown(self):
        self.db.close()

    def _legacy(self):
        return [tuple(row) for row in self.db.execute('SELECT * FROM odev ORDER BY id')]

    def test_schema_idempotent_separate_and_no_legacy_mutation(self):
        before = self._legacy()
        engine.ensure_schema(self.db)
        engine.save_observation(self.db,1,'Fizik','Madde ve Özellikleri',homework_id=21,
                 subskill='Özkütle grafiği',mode='Hedefli soru',correct=4,wrong=3,blank=1,
                 reason='Kavram eksikliği')
        self.assertEqual(self._legacy(),before)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM adaptive_observation_v25').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM odev').fetchone()[0],3)

    def test_cannot_associate_other_students_homework(self):
        before = self._legacy()
        with self.assertRaises(ValueError):
            engine.save_observation(self.db,1,'Fizik','Madde ve Özellikleri',
                homework_id=23,correct=1)
        with self.assertRaises(ValueError):
            engine.save_blocker(self.db,1,'İş yükü',homework_id=23)
        with self.assertRaises(ValueError):
            engine.save_observation(self.db,1,'Matematik','Fonksiyonlar',
                homework_id=21,correct=3)
        self.assertEqual(self._legacy(),before)
        self.assertEqual(engine.observations(self.db,1),[])

    def test_unmeasured_homework_is_not_mastery(self):
        topics=engine.student_topics(self.db,1)
        self.assertTrue(topics)
        self.assertEqual({t['level'] for t in topics},{'Ölçüm gerekli'})
        self.assertTrue(all(t['accuracy'] is None for t in topics))
        self.assertEqual(sum(x['done_count'] for x in topics),1)

    def test_draft_does_not_change_assignments(self):
        before=self._legacy()
        prefs=engine.save_preferences(self.db,1,{'weekly_minutes':150,'review_percent':30,
                                               'learning_style':'Mikro adım'})
        self.assertEqual(engine.load_preferences(self.db,1)['review_percent'],30)
        p=engine.make_plan(self.db,1,prefs,today=date(2026,10,13))
        self.assertEqual(p['student_id'],1)
        self.assertLessEqual(p['planned_minutes'],150)
        self.assertTrue(all(item['needs_teacher_approval'] for item in p['items']))
        planid=engine.save_plan(self.db,1,p)
        self.assertGreater(planid,0)
        self.assertEqual(self.db.execute('SELECT approved FROM adaptive_plan_v25 WHERE id=?',(planid,)).fetchone()[0],0)
        self.assertEqual(before,self._legacy())

    def test_recent_observation_low_accuracy_is_support(self):
        engine.save_observation(self.db,1,'Fizik','Madde ve Özellikleri',
                 homework_id=21, correct=1,wrong=5,blank=2,reason='Kavram eksikliği',
                 observed_on='2026-10-12')
        t=next(r for r in engine.student_topics(self.db,1) if r['lesson']=='Fizik')
        self.assertEqual(t['level'],'Hedefli destek')
        self.assertEqual(t['accuracy'],12)
        self.assertEqual(t['subskills'],[])
        self.assertEqual(len(engine.observations(self.db,2)),0)

    def test_spaced_days_needed_for_strong_evidence(self):
        # Two 5-question checks on the same date must NOT become mastery.
        for _ in range(2):
            engine.save_observation(self.db,1,'Fizik','Madde ve Özellikleri',
                homework_id=21,correct=5,observed_on='2026-10-01')
        t=next(x for x in engine.student_topics(self.db,1) if x['lesson']=='Fizik')
        self.assertEqual(t['strong_checks'],1)
        self.assertNotEqual(t['level'],'Olumlu kanıt (tekrar doğrula)')
        engine.save_observation(self.db,1,'Fizik','Madde ve Özellikleri',
            homework_id=21,correct=5,observed_on='2026-10-08')
        t=next(x for x in engine.student_topics(self.db,1) if x['lesson']=='Fizik')
        self.assertGreaterEqual(t['strong_checks'],2)

    def test_old_unmeasured_homework_not_spaced_recall(self):
        stats=engine.student_overview(self.db,1,today='2026-10-13')
        self.assertEqual(stats['due_topics'],0)
        p=engine.make_plan(self.db,1,today='2026-10-13')
        self.assertTrue(p['items'])
        self.assertTrue(all(x['category']=='Güncel odak' for x in p['items']))

    def test_blockers_are_additive_not_rollover(self):
        before=self._legacy()
        pk=engine.save_blocker(self.db,1,'İş yükü','20 soru yetişmedi',homework_id=21,
                resolution='10 kritik soruya indirip sonraki hafta gözden geçir')
        self.assertGreater(pk,0)
        self.assertEqual(len(engine.get_blockers(self.db,1)),1)
        self.assertEqual(self._legacy(),before)

    def test_deletion_preserves_evidence_history(self):
        engine.save_observation(self.db,1,'Fizik','Madde ve Özellikleri',homework_id=21,
                                correct=1,wrong=2)
        self.db.execute('DELETE FROM odev WHERE id=21')
        self.db.commit()
        row=self.db.execute('SELECT homework_id FROM adaptive_observation_v25').fetchone()
        self.assertIsNone(row['homework_id'])
        self.assertEqual(len(engine.observations(self.db,1)),1)

    def test_unknown_student_rejected(self):
        with self.assertRaises(ValueError):
            engine.make_plan(self.db,999)
        with self.assertRaises(ValueError):
            engine.save_preferences(self.db,999,{})

    def test_plan_no_fictional_tasks(self):
        self.db.execute('INSERT INTO ogrenci(id,ad) VALUES(3,\'Deneme\')')
        p=engine.make_plan(self.db,3,today=date(2026,10,13))
        self.assertEqual(p['items'],[])
        self.assertTrue(p['warnings'])

    def test_recent_workload_blocker_reduces_new_plan_not_existing_homework(self):
        before=self._legacy()
        engine.save_blocker(self.db,1,'İş yükü','Haftalık yük yüksek',homework_id=21)
        p=engine.make_plan(self.db,1,{'weekly_minutes':300,'review_percent':30},
                           today=date.today())
        self.assertEqual(p['effective_weekly_minutes'],240)
        self.assertLessEqual(p['planned_minutes'],240)
        self.assertTrue(any('azaltıldı' in w for w in p['warnings']))
        self.assertEqual(before,self._legacy())

    def test_feature_gate(self):
        from unittest.mock import patch
        from services.adaptive_coaching_v25.flags import enabled
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V25':'0'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V25':'1'}):
            self.assertTrue(enabled())

if __name__=='__main__':
    unittest.main()
