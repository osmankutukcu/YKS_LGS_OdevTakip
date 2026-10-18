# -*- coding: utf-8 -*-
"""V30 pure planning, eligibility and legacy-lifecycle no-mutation contract."""
from __future__ import annotations
from tools.v35_reviewed_source_contract import verify_legacy_handlers
import ast
from datetime import date
import hashlib
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v28.quick_notes import set_note
from services.adaptive_coaching_v30.drafts import (
    build_draft, fingerprint, evaluate_candidates, select_transfer_tasks
)
from services.adaptive_coaching_v30.flags import enabled
from utils.wizard_integrity_v8 import exact_task_key

ROOT=Path(__file__).resolve().parents[1]


class V30Tests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:')
        self.con.row_factory=sqlite3.Row
        self.con.execute('PRAGMA foreign_keys=ON')
        self.con.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
                                verilis_tarihi TEXT, bitis_tarihi TEXT);
        CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,
                     ders TEXT, konu_ad TEXT,kitap_ad TEXT,saat_dk INTEGER,durum TEXT,aciklama TEXT);
        INSERT INTO ogrenci VALUES(1,'Osman','Fizik'),(2,'Ali','Veli');
        INSERT INTO odev_kume VALUES(7,1,'2026-10-12','2026-10-20'),
                                    (8,2,'2026-10-12','2026-10-20');
        INSERT INTO odev VALUES
           (11,7,1,'Fizik','Enerji','345',45,'devam','Korunan mevcut açıklama'),
           (12,7,1,'Fizik','Basınç','Bilgi Sarmal',45,'devam','Korunan'),
           (13,7,1,'Fizik','Elektrik ve Manyetizma','',25,'devam','Kitapsız'),
           (20,8,2,'Fizik','Enerji','345',40,'devam','Başka öğrencinin');
        ''')
        engine.ensure_schema(self.con)
        self.today=date.today()

    def tearDown(self):
        self.con.close()

    def snapshot(self):
        return [tuple(x) for x in self.con.execute('SELECT * FROM odev ORDER BY id')]

    def test_legacy_no_changes_and_missing_book_untransferable(self):
        before=self.snapshot()
        draft=build_draft(self.con,1,today=self.today)
        self.assertEqual(draft['student_id'],1)
        self.assertEqual(draft['fingerprint'],fingerprint(draft))
        self.assertTrue(any(x['book']=='' and not x['transferable'] for x in draft['items']))
        self.assertTrue(all(x['lesson']=='Fizik' for x in draft['items']))
        self.assertEqual(self.snapshot(),before)

    def test_teacher_observation_is_context_not_mastery(self):
        set_note(self.con,1,11,'time')
        draft=build_draft(self.con,1,today=self.today)
        energy=next(x for x in draft['items'] if x['topic']=='Enerji')
        self.assertIn('Zaman',energy['note'])
        self.assertIn('Ölçüm gerekli',energy['level'])
        other=build_draft(self.con,2,today=self.today)
        self.assertTrue(all(x['note'] is None for x in other['items']))

    def test_overload_reduces_default_not_assignments(self):
        before=self.snapshot()
        set_note(self.con,1,11,'workload')
        draft=build_draft(self.con,1,today=self.today)
        self.assertTrue(draft['overload_note'])
        self.assertLessEqual(sum(x['default_selected'] for x in draft['items']),2)
        self.assertEqual(self.snapshot(),before)

    def test_eligibility_fail_closed_and_nothing_mutated(self):
        draft=build_draft(self.con,1,today=self.today)
        calls=[]
        def check(r):
            calls.append(r['topic'])
            return (r['topic']!='Basınç', 'Zaten işaretli' if r['topic']=='Basınç' else 'Uygun')
        rows=evaluate_candidates(draft['items'],check)
        self.assertTrue(all(not r['eligible'] for r in rows if not r['book']))
        self.assertTrue(all(not r['default_selected'] for r in rows if not r['eligible']))
        self.assertNotIn('Elektrik ve Manyetizma',calls)

    def test_wrong_student_and_stale_plan_refused(self):
        draft=build_draft(self.con,1,today=self.today)
        selected={exact_task_key(x['lesson'],x['book'],x['topic']) for x in draft['items'] if x['book']}
        with self.assertRaisesRegex(ValueError,'Öğrenci değişti'):
            select_transfer_tasks(draft,selected,expected_student_id=2,fresh_draft=draft)
        changed=dict(draft, fingerprint='bad')
        with self.assertRaisesRegex(ValueError,'güncellendi'):
            select_transfer_tasks(draft,selected,expected_student_id=1,fresh_draft=changed)
        engine.save_observation(self.con,1,'Fizik','Enerji',homework_id=11,correct=1,wrong=6,
                                observed_on=self.today)
        altered=build_draft(self.con,1,today=self.today)
        self.assertNotEqual(draft['fingerprint'],altered['fingerprint'])
        with self.assertRaisesRegex(ValueError,'güncellendi'):
            select_transfer_tasks(draft,selected,expected_student_id=1,fresh_draft=altered)

    def test_only_selected_exact_matches_and_descriptions(self):
        draft=build_draft(self.con,1,today=self.today)
        row=next(x for x in draft['items'] if x['book'])
        key=exact_task_key(row['lesson'],row['book'],row['topic'])
        result=select_transfer_tasks(draft,{key},expected_student_id=1,fresh_draft=draft)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['kitap'],row['book'])
        self.assertIn('aciklama',result[0])
        self.assertTrue(result[0]['dk']>0)
        with self.assertRaises(ValueError):
            select_transfer_tasks(draft,{('matematik','başka kitap','bilinmeyen')},
                                  expected_student_id=1,fresh_draft=draft)
        with self.assertRaises(ValueError):
            select_transfer_tasks(draft,set(),expected_student_id=1,fresh_draft=draft)

    def test_flag_independent_shutdown(self):
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V30':'0', 'EDUTRACK_ADAPTIVE_V29':'1'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V30':'1', 'EDUTRACK_ADAPTIVE_V29':'0'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V30':'1','EDUTRACK_ADAPTIVE_V29':'1',
                       'EDUTRACK_ADAPTIVE_V28':'1','EDUTRACK_ADAPTIVE_V25':'1'}):
            self.assertTrue(enabled())

    def test_no_legacy_updates_or_event_hooks(self):
        expected={
          'ui/homework_form.py':'53e6b12db96cf81fd622947e7d343b4130a1a8e42a0e30d5c5ec58e64e456314',
          'ui/odev_kontrol.py':'da0f9c272f528f18dcadf4548b837039371780b9509039df5da2585ab51b095e',
          'db.py':'8b295f375a18b41bdb92f120170bafb9a2cb93863be9e98b789241ceb32c4d6b',
        }
        for path,digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)
        verify_legacy_handlers(ROOT)
        ui=(ROOT/'ui/adaptive_draft_review_v30.py').read_text()
        self.assertIn('host._wizard_transfer_tasks',ui)
        for forbidden in ('itemChanged.connect','cellClicked.connect','dataChanged.connect',
                          'btnKaydet.clicked.connect', 'UPDATE odev', 'INSERT INTO odev'):
            self.assertNotIn(forbidden,ui)
        for path in ('services/adaptive_coaching_v30/drafts.py','ui/adaptive_draft_review_v30.py'):
            ast.parse((ROOT/path).read_text())

if __name__=='__main__': unittest.main()
