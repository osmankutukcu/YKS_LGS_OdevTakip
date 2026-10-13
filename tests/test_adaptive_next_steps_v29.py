# -*- coding: utf-8 -*-
"""V29: explicit teacher-action only, read-only decisions and V27/V28 parity."""
from tools.v35_reviewed_source_contract import verify_legacy_handlers
import ast
import hashlib
import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v28.quick_notes import set_note
from services.adaptive_coaching_v29.flags import enabled
from services.adaptive_coaching_v29.next_steps import (
    next_step_for_homework,student_next_steps,plain_text,
)
from services.adaptive_coaching_v27.presenter import sidebar_data

ROOT=Path(__file__).resolve().parents[1]

class NextStepTests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:')
        self.con.row_factory=sqlite3.Row
        self.con.execute('PRAGMA foreign_keys=ON')
        self.con.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
                             verilis_tarihi TEXT,bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,
                    ders TEXT,konu_ad TEXT,kitap_ad TEXT,saat_dk INTEGER,durum TEXT,aciklama TEXT);
          INSERT INTO ogrenci VALUES(1,'Öğrenci','A'),(2,'Öğrenci','B');
          INSERT INTO odev_kume VALUES(7,1,'2026-10-12','2026-10-20'),
                                      (8,2,'2026-10-12','2026-10-20');
          INSERT INTO odev VALUES(31,7,1,'Fizik','Enerji','345',75,'yapildi','Mevcut'),
                                  (32,7,1,'Fizik','Basınç','345',35,'devam','Diğer'),
                                  (33,8,2,'Fizik','Enerji','345',60,'devam','İkinci');
        ''')
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def snapshot(self):
        return [tuple(r) for r in self.con.execute('SELECT * FROM odev ORDER BY id')]

    def test_default_no_table_no_schema_no_learning_claim(self):
        before=self.snapshot()
        result=next_step_for_homework(self.con,1,31,today='2026-10-13')
        self.assertEqual(result['evidence_attempts'],0)
        self.assertIn('kanıtı değildir',' '.join(result['context']))
        self.assertTrue(result['approval_required'])
        self.assertIn('öğretmen',result['warning'])
        self.assertEqual(student_next_steps(self.con,1,today='2026-10-13'),[])
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.con.execute("SELECT count(*) FROM sqlite_master WHERE name LIKE 'adaptive_%'").fetchone()[0],0)

    def test_time_note_is_not_relabelled_concept(self):
        before=self.snapshot()
        set_note(self.con,1,31,'time')
        result=next_step_for_homework(self.con,1,31,today='2026-10-13')
        self.assertEqual(result['teacher_note'],'time')
        self.assertIn('Zaman',result['title'])
        self.assertIn('süresiz',result['next_step'])
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(len(student_next_steps(self.con,1,today='2026-10-13')),1)

    def test_workload_reduce_not_auto_rollover(self):
        set_note(self.con,1,32,'workload')
        result=next_step_for_homework(self.con,1,32,today='2026-10-13')
        self.assertIn('kritik çekirdek',result['next_step'])
        self.assertIn('tamamlanmadı',result['context'][0])
        self.assertEqual(self.con.execute('SELECT durum FROM odev WHERE id=32').fetchone()[0],'devam')

    def test_wrong_student_cluster_isolation(self):
        set_note(self.con,2,33,'concept')
        with self.assertRaises(ValueError):
            next_step_for_homework(self.con,1,33,today='2026-10-13')
        self.assertEqual(student_next_steps(self.con,1,today='2026-10-13'),[])
        self.assertEqual(student_next_steps(self.con,2,today='2026-10-13')[0]['teacher_note'],'concept')
        self.con.execute('UPDATE odev_kume SET ogrenci_id=2 WHERE id=7')
        with self.assertRaises(ValueError):
            next_step_for_homework(self.con,1,31,today='2026-10-13')
        self.con.rollback()

    def test_evidence_bound_and_not_mastery(self):
        engine.ensure_schema(self.con)
        engine.save_observation(self.con,1,'Fizik','Enerji',homework_id=31,
            correct=2,wrong=5,blank=1,observed_on='2026-10-12',subskill='Enerji dönüşümü')
        result=next_step_for_homework(self.con,1,31,today='2026-10-13')
        self.assertEqual(result['evidence_attempts'],8)
        self.assertIn('2/8',plain_text(result))
        self.assertIn('düşük',plain_text(result))
        self.assertEqual(next_step_for_homework(self.con,2,33,today='2026-10-13')['evidence_attempts'],0)

    def test_readonly_view_and_deleted_homework(self):
        set_note(self.con,1,31,'concept')
        self.con.execute('PRAGMA query_only=ON')
        result=next_step_for_homework(self.con,1,31,today='2026-10-13')
        self.assertEqual(result['teacher_note'],'concept')
        self.assertEqual(len(student_next_steps(self.con,1,today='2026-10-13')),1)
        self.con.execute('PRAGMA query_only=OFF')
        self.con.execute('DELETE FROM odev WHERE id=31')
        self.con.commit()
        self.assertEqual(student_next_steps(self.con,1,today='2026-10-13'),[])

    def test_sidepanel_joins_optional_recommendation_only_if_note(self):
        before=self.snapshot()
        data=sidebar_data(self.con,1,today='2026-10-13')
        self.assertEqual(data['next_steps'],[])
        set_note(self.con,1,32,'attention')
        data=sidebar_data(self.con,1,today='2026-10-13')
        self.assertEqual(data['next_steps'][0]['teacher_note'],'attention')
        other=sidebar_data(self.con,2,today='2026-10-13')
        self.assertEqual(other['next_steps'],[])
        self.assertEqual(self.snapshot(),before)

    def test_toggle_v29_alone_retains_v28(self):
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V29':'0','EDUTRACK_ADAPTIVE_V28':'1','EDUTRACK_ADAPTIVE_V25':'1'}):
            self.assertFalse(enabled())
            self.assertEqual(sidebar_data(self.con,1)['next_steps'],[])
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V29':'1','EDUTRACK_ADAPTIVE_V28':'1','EDUTRACK_ADAPTIVE_V25':'1'}):
            self.assertTrue(enabled())

    def test_legacy_file_hash_and_no_event_listeners(self):
        self.assertEqual(hashlib.sha256((ROOT/'ui/homework_form.py').read_bytes()).hexdigest(),
                         '827098c0628bccbac89fbcb37cdf9967467b8971e65457d1d484768c824ffb5b')
        verify_legacy_handlers(ROOT)
        core=ROOT/'ui/odev_kontrol.py'
        baseline=Path('/mnt/data/v28_work/ui/odev_kontrol.py')
        if baseline.exists():
            self.assertEqual(core.read_bytes(),baseline.read_bytes())
        source=(ROOT/'ui/quick_coaching_bridge_v28.py').read_text()
        for forbidden in ('itemChanged.connect','cellClicked.connect','dataChanged.connect','btnKaydet.clicked.connect'):
            self.assertNotIn(forbidden,source)
        body=(ROOT/'services/adaptive_coaching_v29/next_steps.py').read_text()
        for stmt in ('UPDATE odev SET','DELETE FROM odev ', 'INSERT INTO odev '):
            self.assertNotIn(stmt,body)
        self.assertNotIn('CREATE TABLE',body)

if __name__=='__main__':
    unittest.main()
