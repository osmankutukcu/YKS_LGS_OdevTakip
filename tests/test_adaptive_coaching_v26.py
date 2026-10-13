# -*- coding: utf-8 -*-
"""V26 decision queue regression. No dependency on PyQt6 or live user data."""
import os
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v26 import decision
from services.adaptive_coaching_v26.flags import enabled


class AdaptiveCenterV26Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
                                   verilis_tarihi TEXT, bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER,
                            ders TEXT, konu_ad TEXT, kitap_ad TEXT,
                            saat_dk INTEGER, durum TEXT, aciklama TEXT);
          INSERT INTO ogrenci VALUES (1,'Seda','Bir'),(2,'Ali','İki'),(3,'Ece','Üç');
          INSERT INTO odev_kume VALUES (11,1,'2026-09-22','2026-09-29'),
            (12,2,'2026-09-25','2026-10-02'),(13,3,'2026-09-25','2026-10-02');
          INSERT INTO odev VALUES
            (21,11,1,'Fizik','Özkütle','Bilgi Sarmal',35,'tamam', 'Korunmalı'),
            (22,11,1,'Matematik','Fonksiyonlar','345',35,'devam', 'Korunmalı'),
            (23,12,2,'Fizik','Özkütle','345',45,'devam','Korunmalı'),
            (24,13,3,'Türkçe','Paragraf','Soru',30,'tamamlandı','Korunmalı');
        ''')

    def tearDown(self):
        self.db.close()

    def legacy(self):
        return [tuple(r) for r in self.db.execute('SELECT * FROM odev ORDER BY id')]

    def test_no_schema_read_only_state(self):
        before = self.legacy()
        data = decision.student_decisions(self.db,1)
        self.assertIn('başlatılmadı',data['status'])
        queue=decision.institution_queue(self.db)
        self.assertEqual(queue['total_students'],3)
        self.assertFalse(queue['has_observations'])
        self.assertEqual(self.legacy(),before)
        self.assertFalse(decision.has_v25_data(self.db))
        self.assertIn('Ödev',decision.concise_summary(data))

    def test_unmeasured_homework_queues_for_measurement_not_mastery(self):
        engine.ensure_schema(self.db)
        result=decision.student_decisions(self.db,1,today='2026-10-13')
        self.assertEqual(result['evidence_count'],0)
        self.assertGreaterEqual(result['metrics']['without_evidence'],1)
        self.assertTrue(any(x['category']=='Ölçüm gerekli' for x in result['actions']))
        queue=decision.institution_queue(self.db,today='2026-10-13')
        first=next(r for r in queue['students'] if r['student_id']==1)
        self.assertEqual(first['done_rows'],1)
        self.assertEqual(first['open_rows'],1)
        self.assertEqual(first['attention'],'Ölçüm gerekli')

    def test_low_accuracy_recommends_specific_action_no_mutation(self):
        engine.ensure_schema(self.db)
        before=self.legacy()
        engine.save_observation(self.db,1,'Fizik','Özkütle',homework_id=21,
                                correct=2,wrong=5,blank=1,
                                subskill='Yoğunluk grafiği',observed_on='2026-10-10',
                                reason='Kavram eksikliği')
        result=decision.student_decisions(self.db,1,today='2026-10-13')
        self.assertEqual(result['metrics']['support'],1)
        self.assertEqual(result['actions'][0]['category'],'Hedefli destek')
        self.assertIn('Yoğunluk grafiği',result['actions'][0]['reason'])
        self.assertIn('V25',result['actions'][0]['source'])
        queue=decision.institution_queue(self.db,today='2026-10-13')
        self.assertEqual(queue['students'][0]['student_id'],1)
        self.assertEqual(queue['students'][0]['support'],1)
        self.assertEqual(before,self.legacy())

    def test_other_student_evidence_not_leaked(self):
        engine.ensure_schema(self.db)
        engine.save_observation(self.db,2,'Fizik','Özkütle',homework_id=23,
                                correct=1,wrong=6,observed_on='2026-10-10')
        first=decision.student_decisions(self.db,1)
        self.assertEqual(first['evidence_count'],0)
        second=decision.student_decisions(self.db,2)
        self.assertEqual(second['evidence_count'],1)
        with self.assertRaises(ValueError):
            decision.student_decisions(self.db,404)

    def test_due_recall_from_real_measurement_not_old_assignment(self):
        engine.ensure_schema(self.db)
        before=decision.student_decisions(self.db,1,today='2026-10-13')
        self.assertFalse(any(a['category']=='Aralıklı tekrar' for a in before['actions']))
        engine.save_observation(self.db,1,'Fizik','Özkütle',homework_id=21,
                                correct=5,wrong=1,observed_on='2026-10-01')
        after=decision.student_decisions(self.db,1,today='2026-10-13')
        self.assertTrue(any(a['category']=='Aralıklı tekrar' for a in after['actions']))

    def test_blocker_does_not_create_debt_or_update_hw(self):
        engine.ensure_schema(self.db)
        before=self.legacy()
        engine.save_blocker(self.db,1,'İş yükü','Çok fazla sayfa',homework_id=22)
        data=decision.student_decisions(self.db,1,today=date.today())
        self.assertTrue(any(a['category']=='Yük dengeleme' for a in data['actions']))
        self.assertEqual(before,self.legacy())

    def test_bounded_batch_queue_and_limited_detail(self):
        engine.ensure_schema(self.db)
        self.db.executemany('INSERT INTO ogrenci(id,ad,soyad) VALUES (?,?,?)',
            [(i,f'Öğrenci{i}','Sınama') for i in range(10, 630)])
        data=decision.institution_queue(self.db,limit=250)
        self.assertEqual(data['total_students'],623)
        self.assertEqual(len(data['students']),250)
        self.assertTrue(data['truncated'])
        self.assertEqual(len({x['student_id'] for x in data['students']}),250)
        brief=decision.student_decisions(self.db,3,maximum=2)
        self.assertLessEqual(len(brief['actions']),2)

    def test_target_and_coach_plan_are_context_not_mastery(self):
        engine.ensure_schema(self.db)
        for col in ('hedef_bolum TEXT','hedef_tyt REAL','hedef_ayt REAL','hedef_lgs REAL'):
            self.db.execute('ALTER TABLE ogrenci ADD COLUMN '+col)
        self.db.execute('UPDATE ogrenci SET hedef_bolum=?,hedef_tyt=?,hedef_ayt=? WHERE id=1',
                        ('Hacettepe Fizik',92,68))
        self.db.execute('CREATE TABLE koc_plan (id INTEGER PRIMARY KEY,ogrenci_id INTEGER, baslangic_tarihi TEXT, bitis_tarihi TEXT)')
        self.db.execute("INSERT INTO koc_plan VALUES (8,1,'2026-10-12','2026-10-19')")
        before=self.legacy()
        summary=decision.student_decisions(self.db,1,today='2026-10-13')
        self.assertIn('Hacettepe Fizik',summary['context']['target'])
        self.assertIn('1 koçluk planı',summary['context']['coaching_plan'])
        self.assertEqual(summary['evidence_count'],0)
        another=decision.student_decisions(self.db,2,today='2026-10-13')
        self.assertNotIn('Hacettepe',another['context']['target'])
        self.assertEqual(before,self.legacy())

    def test_module_flags_independent_off_and_inherited(self):
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V25':'1','EDUTRACK_ADAPTIVE_V26':'0'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V25':'0','EDUTRACK_ADAPTIVE_V26':'1'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V25':'1','EDUTRACK_ADAPTIVE_V26':'1'}):
            self.assertTrue(enabled())

    def test_student360_read_only_query(self):
        engine.ensure_schema(self.db)
        script='''
            PRAGMA query_only=ON;
        '''
        self.db.executescript(script)
        summary=decision.concise_summary(decision.student_decisions(self.db,1))
        self.assertIn('ödev',summary.lower())
        self.assertIn('ÖĞRETMEN',summary)
        self.assertEqual(self.legacy()[0][0],21)


if __name__ == '__main__':
    unittest.main()
