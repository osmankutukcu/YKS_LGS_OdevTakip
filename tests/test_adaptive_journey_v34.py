# -*- coding: utf-8 -*-
"""V34 student journey and read-only cross-feature regression tests."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import os
import sqlite3
import unittest

from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v26.decision import student_decisions
from services.adaptive_coaching_v27.presenter import sidebar_data
from services.adaptive_coaching_v28.quick_notes import set_note
from services.adaptive_coaching_v29.next_steps import student_next_steps
from services.adaptive_coaching_v30.drafts import build_draft
from services.adaptive_coaching_v34.flags import enabled
from services.adaptive_coaching_v34.journey import compose_journey, journey_text

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CRITICAL_SHA256 = {
    'ui/homework_form.py': 'f015d489390ad0d529aabd2f447eaeaed14ccd54f48aaa81dd4a5ed47aef6cad',
    'ui/odev_kontrol.py': '7ca39f447e4a7cd71cb4eb14fde9bba53fae6c183092d0758a77c8d009cd4d0c',
    'db.py': '0273aa9842fea40e1961728de39c2a04bc796eb66d9dadad2bb2d25e22b75b94',
    'main_window.py': '953aef2a7cb3c4296015b565d145d794c6e86f491c3b215ee4ed03150fa3e668',
}


class JourneyV34Tests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.con.execute('PRAGMA foreign_keys=ON')
        self.con.executescript('''
          CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
          CREATE TABLE odev_kume (id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
              verilis_tarihi TEXT, bitis_tarihi TEXT);
          CREATE TABLE odev (id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER,
              ders TEXT, konu_ad TEXT, kitap_ad TEXT,saat_dk INTEGER,durum TEXT,aciklama TEXT);
          INSERT INTO ogrenci VALUES (1,'Deneme','Bir'), (2,'Deneme','İki');
          INSERT INTO odev_kume VALUES (10,1,'2026-10-01','2026-10-20'),
                                      (20,2,'2026-10-01','2026-10-20');
          INSERT INTO odev VALUES
              (11,10,1,'Fizik','Enerji','345',45,'devam','Mevcut'),
              (12,10,1,'Fizik','Basınç','BS',45,'tamam','Mevcut 2'),
              (21,20,2,'Fizik','Enerji','345',50,'devam','Diğer öğrenci');
        ''')
        self.today = date(2026, 10, 13)

    def tearDown(self):
        self.con.close()

    def legacy(self):
        return [tuple(r) for r in self.con.execute('SELECT * FROM odev ORDER BY id')]

    def test_empty_evidence_remains_unmeasured_and_read_only(self):
        before = self.legacy()
        brief = student_decisions(self.con, 1, today=self.today)
        result = compose_journey(1, brief)
        self.assertTrue(result['measurement_needed'])
        self.assertIn('ölçümü yok', result['evidence_label'])
        self.assertTrue(result['teacher_approval_required'])
        self.assertNotIn('başarılı', journey_text(result).lower())
        self.assertEqual(before, self.legacy())
        self.assertFalse(self.con.execute("SELECT 1 FROM sqlite_master WHERE name='adaptive_observation_v25'").fetchone())

    def test_teacher_note_is_hypothesis_not_learning_measure(self):
        engine.ensure_schema(self.con)
        set_note(self.con, 1, 11, 'time')
        before = self.legacy()
        summary = sidebar_data(self.con,1,today=self.today)
        view = summary['learning_journey_v34']
        self.assertEqual(view['student_id'], 1)
        self.assertEqual(view['explicit_teacher_notes'], 1)
        self.assertEqual(view['verified_next_steps'], 1)
        self.assertIn('Bağımsız öğrenme ölçümü yok', view['evidence_label'])
        self.assertIn('Zaman', view['priorities'][0]['title'])
        self.assertIn('V28', view['priorities'][0]['source'])
        self.assertEqual(self.legacy(), before)

    def test_real_learning_evidence_is_separate_from_task_status(self):
        engine.ensure_schema(self.con)
        engine.save_observation(self.con,1,'Fizik','Enerji',homework_id=11,
                                correct=2,wrong=6,subskill='İş-enerji grafiği',observed_on='2026-10-12')
        view = sidebar_data(self.con,1,today=self.today)['learning_journey_v34']
        self.assertFalse(view['measurement_needed'])
        self.assertIn('1 gözlem',view['evidence_label'])
        self.assertTrue(any(x['kind']=='Hedefli destek' for x in view['priorities']))
        self.assertTrue(view['teacher_approval_required'])

    def test_no_data_leak_between_students(self):
        engine.ensure_schema(self.con)
        set_note(self.con,2,21,'concept')
        result = sidebar_data(self.con,1,today=self.today)
        self.assertEqual(result['learning_journey_v34']['explicit_teacher_notes'],0)
        self.assertEqual(result['learning_journey_v34']['verified_next_steps'],0)
        student_two = sidebar_data(self.con,2,today=self.today)
        self.assertEqual(student_two['learning_journey_v34']['explicit_teacher_notes'],1)
        with self.assertRaisesRegex(ValueError,'farklı bir öğrenciye'):
            compose_journey(1,student_decisions(self.con,1),[{'student_id':2}],[])
        with self.assertRaisesRegex(ValueError,'kimliği uyuşmuyor'):
            compose_journey(1,student_decisions(self.con,2))

    def test_recommendations_bounded_non_mutating_inputs(self):
        brief={'student_id':1,'evidence_count':0,'metrics':{},'actions':[
            {'lesson':'Fizik','topic':str(i),'title':f'Konu {i}',
             'category':'İzleme','next_step':'Tekrar','source':'V26'} for i in range(30)]}
        note={'student_id':1,'lesson':'Fizik','topic':'0','title':'Görüşme', 'next_step':'Kısa görüşme'}
        original=deepcopy((brief,note))
        outcome=compose_journey(1,brief,(),[note],max_actions=100)
        self.assertLessEqual(len(outcome['priorities']),5)
        self.assertEqual(len([x for x in outcome['priorities'] if x['topic']=='0']),1)
        self.assertEqual((brief,note),original)

    def test_v34_flag_disables_addon_without_disabling_existing_panel(self):
        with patch.dict(os.environ, {'EDUTRACK_ADAPTIVE_V34':'0','EDUTRACK_ADAPTIVE_V27':'1'}):
            self.assertFalse(enabled())
            result=sidebar_data(self.con,1,today=self.today)
            self.assertIsNone(result['learning_journey_v34'])
            self.assertEqual(result['student_id'],1)
        with patch.dict(os.environ, {'EDUTRACK_ADAPTIVE_V34':'1','EDUTRACK_ADAPTIVE_V27':'0'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ, {'EDUTRACK_ADAPTIVE_V34':'1','EDUTRACK_ADAPTIVE_V27':'1'}):
            self.assertTrue(enabled())

    def test_full_coach_chain_does_not_mutate_assigned_homework(self):
        engine.ensure_schema(self.con)
        set_note(self.con,1,11,'time')
        engine.save_observation(self.con,1,'Fizik','Enerji',homework_id=11,
                                correct=3,wrong=3,observed_on='2026-10-11')
        before=self.legacy()
        con=self.con
        con.execute('PRAGMA query_only=ON')
        try:
            brief=student_decisions(con,1,today=self.today)
            steps=student_next_steps(con,1,today=self.today)
            self.assertEqual(len(steps),1)
            view=sidebar_data(con,1,today=self.today)['learning_journey_v34']
            draft=build_draft(con,1,today=self.today)
            self.assertEqual(view['verified_next_steps'],1)
            self.assertGreaterEqual(len(draft['items']),1)
        finally:
            con.execute('PRAGMA query_only=OFF')
        self.assertEqual(self.legacy(),before)

    def test_v33_critical_sources_identical(self):
        for file in ('ui/homework_form.py','ui/odev_kontrol.py','db.py','main_window.py'):
            self.assertEqual(sha256((ROOT/file).read_bytes()).hexdigest(),
                             EXPECTED_CRITICAL_SHA256[file], file)
        from tools.v35_reviewed_source_contract import verify_legacy_handlers
        verify_legacy_handlers(ROOT)


if __name__=='__main__':
    unittest.main()
