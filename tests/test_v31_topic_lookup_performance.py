# -*- coding: utf-8 -*-
"""V31: optimize exact original topic list order, protect old homework handlers."""
from tools.v35_reviewed_source_contract import verify_legacy_handlers
import ast
import hashlib
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import importlib.util
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]

# Load this pure-Python helper isolated from db.py's optional Qt imports.
# Avoid leaking a fake db module into other test modules.
_fake_db = ModuleType('v31_db_stub')
with patch.dict(sys.modules, {'db': _fake_db}):
    _spec = importlib.util.spec_from_file_location('v31_konu_helper_under_test',
                                                    ROOT/'utils'/'konu_helper.py')
    konu_helper = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(konu_helper)


def old_sort(reference):
    """Literal reference for V30 sort behavior, including duplicates/fallback."""
    general, outcome = reference
    old_order = [(r['konu'] or '').strip().lower() for r in general]
    def order_key(name):
        try:
            return (0, old_order.index(name.lower()))
        except ValueError:
            return (1, name.lower())
    return sorted(outcome, key=lambda item: order_key(item['konu']))


class TestV31WinTopicOrder(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.con.executescript('''
          CREATE TABLE grup_konu_duzen(ders TEXT, ana_grup TEXT, alt_grup TEXT,
                                       konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
          CREATE TABLE ogrenci_konu_duzen(ders TEXT, ogrenci_id INTEGER,
                                          konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
        ''')

    def tearDown(self):
        self.con.close()

    def verify(self, general, overrides=None, student=None):
        overrides = overrides or []
        student = student or []
        for i in overrides:
            self.con.execute('INSERT INTO grup_konu_duzen VALUES (?,?,?,?,?,?)',
                             ('fizik','YKS','TYT',i['konu'],i.get('ort_soru'),i.get('ort_sure')))
        for i in student:
            self.con.execute('INSERT INTO ogrenci_konu_duzen VALUES (?,?,?,?,?)',
                             ('fizik', 17, i['konu'],i.get('ort_soru'),i.get('ort_sure')))
        # Exactly emulate previous get_active_list dict overwrites and ordering.
        normalized = {}
        for seq in (general, overrides, student):
            for row in seq:
                key = (row['konu'] or '').strip().lower()
                if key:
                    normalized[key] = dict(row)
        expected = old_sort((general, list(normalized.values())))
        with patch.object(konu_helper.db, 'ders_konularini_cek', return_value=general, create=True):
            actual = konu_helper.get_active_list(self.con, 'fizik', ogrenci_id=17,
                                                 ana_grup='YKS', alt_grup='TYT')
        self.assertEqual(actual, expected)
        return actual

    def test_order_of_topics_and_new_topics(self):
        general = [{'konu': x, 'ort_sure': 60, 'ort_soru': 5}
                   for x in ['Madde', 'Enerji', 'Basınç', 'Dalga']]
        result = self.verify(general, [{'konu':'Z-sonradan', 'ort_sure':30,'ort_soru':1}],
                             [{'konu':'Enerji','ort_sure':20,'ort_soru':1}])
        self.assertEqual([x['konu'] for x in result],
                         ['Madde', 'Enerji', 'Basınç', 'Dalga', 'Z-sonradan'])
        self.assertEqual(result[1]['ort_sure'], 20)

    def test_duplicate_general_first_position_preserved(self):
        self.verify([
            {'konu':'A', 'ort_sure':10,'ort_soru':1},
            {'konu':'B', 'ort_sure':20,'ort_soru':2},
            {'konu':'a', 'ort_sure':30,'ort_soru':3},
            {'konu':'C', 'ort_sure':40,'ort_soru':4},
        ])

    def test_case_unicode_and_large_number_of_topics(self):
        self.verify([{'konu':f'Konu {i:04d}', 'ort_sure':i+1, 'ort_soru':i}
                     for i in range(900)] +
                    [{'konu':'İntegral', 'ort_sure':80,'ort_soru':10},
                     {'konu':'ışık', 'ort_sure':45,'ort_soru':9}])

    def test_empty_general_and_only_overrides(self):
        self.verify([], [{'konu':'Zorlu','ort_sure':70,'ort_soru':2},
                         {'konu':'Acemi','ort_sure':20,'ort_soru':8}])


class TestLegacyFileProtection(unittest.TestCase):
    def test_core_files_byte_identical_to_v30(self):
        # Pinned from the V30 source release; works standalone on Windows CI.
        protected = {
            'ui/homework_form.py': 'f015d489390ad0d529aabd2f447eaeaed14ccd54f48aaa81dd4a5ed47aef6cad',
            'ui/odev_kontrol.py': '7ca39f447e4a7cd71cb4eb14fde9bba53fae6c183092d0758a77c8d009cd4d0c',
            'db.py': '0273aa9842fea40e1961728de39c2a04bc796eb66d9dadad2bb2d25e22b75b94',
            'main_window.py': '953aef2a7cb3c4296015b565d145d794c6e86f491c3b215ee4ed03150fa3e668',
        }
        for rel, digest in protected.items():
            with self.subTest(rel=rel):
                self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),digest)

    def test_no_change_to_existing_topic_precedence(self):
        s = (ROOT/'utils/konu_helper.py').read_text(encoding='utf-8')
        self.assertIn('result.update(gmap)', s)
        self.assertIn('result.update(omap)', s)
        self.assertIn('genel_position.setdefault', s)


if __name__ == '__main__':
    unittest.main()
