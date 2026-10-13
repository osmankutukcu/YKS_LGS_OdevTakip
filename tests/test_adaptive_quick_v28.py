# -*- coding: utf-8 -*-
"""Regression contracts for V28: separate notes, student safety, legacy parity."""
import ast
import hashlib
import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from services.adaptive_coaching_v28.quick_notes import (
    CHOICES, set_note, recent_notes, _table_exists,
)
from services.adaptive_coaching_v28.flags import enabled
from services.adaptive_coaching_v27.presenter import sidebar_data

ROOT = Path(__file__).resolve().parents[1]


class QuickEvidenceContract(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.con.execute('PRAGMA foreign_keys=ON')
        self.con.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
                                 verilis_tarihi TEXT, bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER,
                            ogrenci_id INTEGER, ders TEXT,kitap_ad TEXT,
                            konu_ad TEXT,saat_dk INTEGER,durum TEXT,aciklama TEXT);
          INSERT INTO ogrenci VALUES(1,'Ayşe','Bir'),(2,'Ahmet','İki');
          INSERT INTO odev_kume VALUES(7,1,'2026-10-12','2026-10-19'),
                                      (8,2,'2026-10-12','2026-10-19');
          INSERT INTO odev VALUES(31,7,1,'Fizik','345','Enerji',75,'devam','Kalsın'),
                                  (32,7,1,'Fizik','345','Basınç',45,'yapildi','Asıl'),
                                  (33,8,2,'Fizik','345','Enerji',55,'devam','Başka');
        ''')
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def original(self):
        return [tuple(r) for r in self.con.execute('SELECT * FROM odev ORDER BY id')]

    def test_initial_read_no_schema_and_no_learning_inference(self):
        before = self.original()
        self.assertEqual(recent_notes(self.con, 1), [])
        self.assertFalse(_table_exists(self.con))
        model = sidebar_data(self.con, 1, today='2026-10-13')
        self.assertEqual(model['evidence_count'], 0)
        self.assertFalse(model['quick_notes'])
        self.assertEqual(self.original(), before)

    def test_one_click_note_no_legacy_mutation_and_no_mastery(self):
        before = self.original()
        self.assertEqual(set_note(self.con, 1,31,'concept'),'Konu/kazanım anlaşılmadı')
        notes = recent_notes(self.con,1)
        self.assertEqual(notes[0]['homework_id'],31)
        self.assertEqual(notes[0]['code'],'concept')
        self.assertEqual(self.original(),before)
        model = sidebar_data(self.con,1,today='2026-10-13')
        self.assertEqual(model['evidence_count'],0)  # Never treated as quiz mastery
        self.assertEqual(model['quick_notes'][0]['code'],'concept')

    def test_all_choices_supported_and_upsert_one_latest_entry(self):
        for code,_ in CHOICES:
            set_note(self.con,1,31,code)
        notes = recent_notes(self.con,1)
        self.assertEqual(len(notes),1)
        self.assertEqual(notes[0]['code'],CHOICES[-1][0])
        self.assertEqual(self.con.execute('SELECT count(*) FROM adaptive_quick_note_v28').fetchone()[0],1)

    def test_wrong_student_and_wrong_cluster_blocked(self):
        before = self.original()
        with self.assertRaises(ValueError):
            set_note(self.con,2,31,'workload')
        with self.assertRaises(ValueError):
            set_note(self.con,1,33,'time')
        self.con.execute('UPDATE odev_kume SET ogrenci_id=2 WHERE id=7')
        with self.assertRaises(ValueError):
            set_note(self.con,1,31,'concept')
        self.assertFalse(_table_exists(self.con))
        self.con.rollback()
        self.assertEqual(before,self.original())

    def test_invalid_code_no_schema(self):
        with self.assertRaises(ValueError):
            set_note(self.con,1,31,'psychological-diagnosis')
        self.assertFalse(_table_exists(self.con))

    def test_retract_only_quick_note(self):
        before = self.original()
        set_note(self.con,1,31,'difficulty')
        self.assertIsNone(set_note(self.con,1,31,None))
        self.assertEqual(recent_notes(self.con,1),[])
        self.assertEqual(before,self.original())

    def test_deleted_legacy_homework_does_not_erase_coach_history(self):
        set_note(self.con,1,31,'concept')
        self.con.execute('DELETE FROM odev WHERE id=31')
        self.con.commit()
        n = recent_notes(self.con,1)[0]
        self.assertIsNone(n['homework_id'])
        self.assertEqual((n['lesson'],n['topic']),('Fizik','Enerji'))
        self.assertEqual(n['label'],'Konu/kazanım anlaşılmadı')

    def test_student_isolation_and_read_only_compatibility(self):
        set_note(self.con,1,31,'time')
        set_note(self.con,2,33,'easy')
        self.con.execute('PRAGMA query_only=ON')
        one=recent_notes(self.con,1)
        two=recent_notes(self.con,2)
        self.assertEqual([n['student_id'] for n in one],[1])
        self.assertEqual([n['student_id'] for n in two],[2])
        self.assertEqual(sidebar_data(self.con,2)['quick_notes'][0]['code'],'easy')

    def test_disabled_v28_without_disabling_legacy(self):
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V28':'0'}):
            self.assertFalse(enabled())
        with patch.dict(os.environ,{'EDUTRACK_ADAPTIVE_V28':'1','EDUTRACK_ADAPTIVE_V25':'1'}):
            self.assertTrue(enabled())

    def test_comment_never_generated_from_checkbox_signal(self):
        source=(ROOT/'ui/quick_coaching_bridge_v28.py').read_text()
        self.assertNotIn('itemChanged.connect',source)
        self.assertNotIn('cellClicked.connect',source)
        self.assertNotIn('dataChanged.connect',source)
        self.assertNotIn('btnKaydet.clicked.connect',source)

    def test_no_legacy_dml_in_v28(self):
        source=(ROOT/'services/adaptive_coaching_v28/quick_notes.py').read_text()
        for statement in ('UPDATE odev SET','DELETE FROM odev ','INSERT INTO odev '):
            self.assertNotIn(statement,source)


class OriginalCoreProtection(unittest.TestCase):
    # Anchored to original V27 sources, so Windows CI can validate parity
    # even without the private previous-turn work directory.
    V27_HOMEWORK_SHA256 = 'b522636d49cdeaf643fef5704a3c63e39a7b5d7230d7f405f78330ebe5a2d68f'
    V35_REVIEWED_HOMEWORK_SHA256 = '827098c0628bccbac89fbcb37cdf9967467b8971e65457d1d484768c824ffb5b'
    V27_CONTROL_METHOD_SHA20 = {
      '_kume_ac':'cadcdc80be468fc7fd1b',
      '_kaydet':'594371f8d87be1168ed9',
      '_aktar':'b174ac81868246d82b28',
      'aktar_silmeden':'29b7edc5495f3f258a1d',
      '_hepsi_tamam':'ccb4324c70272c601b78',
      '_hepsi_geri':'22fec7893da285721d42',
      '_chk_cell_click':'a31547e745249728c4ee',
      '_on_table_item_changed':'34d657727551cc792f4b',
    }
    V27_CONTROL_METHOD_SHA20_PY39 = {
       '_kume_ac': 'e28ec59b42fd30cfd918',
       '_kaydet': 'a474348ffcc65659c850',
       '_aktar': '534030a148612d1f8294',
       'aktar_silmeden': 'cbd17d57f090b7c6d366',
       '_hepsi_tamam': 'd74ce16fef9af2ea1a75',
       '_hepsi_geri': '1aa7602099e5101dcff6',
       '_chk_cell_click': 'ceaf8b3cbf9a7211e52c',
       '_on_table_item_changed': 'd718d887f49e525a7c2c',
    }

    def test_static_legacy_hash_parity_for_windows_ci(self):
        self.assertEqual(
            hashlib.sha256((ROOT/'ui/homework_form.py').read_bytes()).hexdigest(),
            self.V35_REVIEWED_HOMEWORK_SHA256)
        from tools.v35_reviewed_source_contract import verify_legacy_handlers
        verify_legacy_handlers(ROOT)
        original=self.method_signature(ROOT/'ui/odev_kontrol.py',
            'OdevKontrolDialog', self.V27_CONTROL_METHOD_SHA20)
        actual_hashes = {name:hashlib.sha256(body.encode()).hexdigest()[:20]
                         for name,body in original.items()}
        self.assertTrue(actual_hashes == self.V27_CONTROL_METHOD_SHA20 or
                        actual_hashes == self.V27_CONTROL_METHOD_SHA20_PY39)

    @staticmethod
    def method_signature(file, classname, names):
        tree=ast.parse(Path(file).read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==classname)
        return {m.name:ast.dump(m,include_attributes=False) for m in cls.body
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and m.name in names}

    def test_legacy_methods_against_v27_source_when_available(self):
        base=Path('/mnt/data/v27_work')
        if not (base/'ui/odev_kontrol.py').exists():
            self.skipTest('V27 baseline path is not available')
        compared=(
            ('ui/odev_kontrol.py','OdevKontrolDialog',
              ('_kaydet','_chk_cell_click','_on_table_item_changed','_kume_ac','_aktar',
               '_hepsi_tamam','_hepsi_geri','aktar_silmeden')),
            ('ui/homework_form.py','OdevTakipFormu',
              ('_tik_degisti','_kaydet_kume','_odev_kontrol','_toplam_sure_guncelle',
               '_whatsapp_gonder','_pdf_yazdir','_sync_verilen_rows_from_table')),
        )
        for path,cls,names in compared:
            with self.subTest(path=path):
                self.assertEqual(self.method_signature(base/path,cls,names),
                                 self.method_signature(ROOT/path,cls,names))

    def test_v27_baseline_and_only_reviewed_weekly_change(self):
        # Historical V27 input remains a fixed reference; its weekly PDF
        # launcher intentionally changed in V35, so byte equality is wrong.
        base=Path('/mnt/data/v27_work/ui/homework_form.py')
        if base.exists():
            self.assertEqual(hashlib.sha256(base.read_bytes()).hexdigest(),
                             self.V27_HOMEWORK_SHA256)
        from tools.v35_reviewed_source_contract import (verify_legacy_handlers,
            APPROVED_WEEKLY_HOMEWORK_SHA256, HISTORICAL_V27_HOMEWORK_SHA256)
        self.assertEqual(HISTORICAL_V27_HOMEWORK_SHA256, self.V27_HOMEWORK_SHA256)
        self.assertEqual(APPROVED_WEEKLY_HOMEWORK_SHA256,
                         self.V35_REVIEWED_HOMEWORK_SHA256)
        verify_legacy_handlers(ROOT)
        source=(ROOT/'ui/plan_settings_dialog.py').read_text(encoding='utf-8')
        self.assertIn('snapshot_homework_table(parent.verilen)', source)


if __name__=='__main__':
    unittest.main()
