# -*- coding: utf-8 -*-
"""Veri yazmadan çalışan kanıt ve SQL geri dönüş testleri; Qt gerektirmez."""
import ast
import hashlib
import json
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from services.report_evidence_v3582 import (
    completion_evidence, observed_rate_evidence, cohort_overview,
    MIN_REPORT_SAMPLE,
)

ROOT = Path(__file__).resolve().parents[1]


class EvidenceLogicTests(unittest.TestCase):
    def test_zero_data_is_not_zero_percent(self):
        e = completion_evidence(0, 0)
        self.assertIsNone(e.percent)
        self.assertEqual(e.status, 'no_data')
        self.assertFalse(e.is_classifiable)

    def test_one_of_one_is_small_sample(self):
        e = completion_evidence(1, 1)
        self.assertEqual(e.percent, 100.0)
        self.assertEqual(e.status, 'limited')
        self.assertFalse(e.is_classifiable)

    def test_five_task_threshold_and_zero_completions(self):
        self.assertEqual(MIN_REPORT_SAMPLE, 5)
        self.assertEqual(completion_evidence(0, 5).percent, 0.0)
        self.assertEqual(completion_evidence(0, 5).status, 'sufficient')
        self.assertEqual(completion_evidence(5, 5).percent, 100.0)

    def test_daily_missing_null_is_not_failure(self):
        self.assertEqual(observed_rate_evidence([None, None]), (None, 0, 'no_data'))
        self.assertEqual(observed_rate_evidence([None, 80.0]), (80.0, 1, 'limited'))
        self.assertEqual(observed_rate_evidence([0, 20, 40, 60, 80]), (40.0, 5, 'sufficient'))

    def test_cohort_excludes_missing_and_small_sample_from_labels(self):
        rows = [
            {'gorev_toplam': 0, 'basari_pct': 0.0},
            {'gorev_toplam': 1, 'basari_pct': 100.0},
            {'gorev_toplam': 5, 'basari_pct': 100.0},
            {'gorev_toplam': 5, 'basari_pct': 20.0},
        ]
        stats = cohort_overview(rows)
        self.assertEqual((stats['no_data'], stats['limited'], stats['high'], stats['followup']), (1, 1, 1, 1))
        self.assertEqual(stats['avg'], 73.3)
        self.assertEqual(cohort_overview([rows[0]])['avg'], None)


class ReportDashboardSQLTests(unittest.TestCase):
    """Eski etkili _get_summary_rows SQL yöntemini PyQt olmadan çalıştırır."""
    @staticmethod
    def _method():
        tree = ast.parse((ROOT / 'ui/report_dashboard.py').read_text(encoding='utf-8'))
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'ReportDashboard')
        funcs = [x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '_get_summary_rows']
        assert len(funcs) == 1, 'Shadowed summary rows should be removed'
        single = ast.Module(body=[funcs[0]], type_ignores=[])
        ast.fix_missing_locations(single)
        from services.report_evidence_v3582 import completion_evidence
        namespace = {'Any': Any, 'completion_evidence': completion_evidence}
        exec(compile(single, '<summary>', 'exec'), namespace)
        return namespace['_get_summary_rows']

    def test_sql_data_none_small_full_class_filter_and_transfer(self):
        con = sqlite3.connect(':memory:')
        con.row_factory = sqlite3.Row
        con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,alt_grup TEXT,aktif INTEGER);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER);
            CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,durum TEXT);
            INSERT INTO ogrenci VALUES (1,'Yok','Görev','A',1),(2,'Tek','Görev','A',1),
               (3,'Dolu','Görev','A',1),(4,'Kapalı','Öğrenci','A',0),(5,'B','Öğrenci','B',1);
            INSERT INTO odev_kume VALUES (11,2),(12,3),(13,4),(14,5);
            INSERT INTO odev VALUES (21,11,'tamam'),(31,12,'tamam'),(32,12,'bitti'),
              (33,12,'devam'),(34,12,'tamam'),(35,12,'tamam'),(41,13,'tamam'),(51,14,'aktarildi');
        ''')
        class Combo:
            def __init__(self, value): self.value=value
            def currentText(self): return self.value
        class Spin:
            def __init__(self, number): self.number=number
            def value(self): return self.number
        obj=SimpleNamespace(con=con,cmb_sinif=Combo('Hepsi'),spin_min_pct=Spin(0),settings={'aktarilan_sayilma_sekli':'done'})
        fn=self._method()
        rows=fn(obj)
        self.assertEqual(len(rows),4)
        byid={r['ogrenci_id']:r for r in rows}
        self.assertFalse(byid[1]['veri_var'])
        self.assertEqual(byid[1]['kanit_durumu'],'no_data')
        self.assertEqual(byid[2]['kanit_durumu'],'limited')
        self.assertEqual(byid[3]['gorev_toplam'],5)
        self.assertEqual(byid[3]['basari_pct'],80.0)
        self.assertEqual(byid[5]['basari_pct'],100.0)
        obj.cmb_sinif=Combo('A')
        rows=fn(obj)
        self.assertEqual({r['ogrenci_id'] for r in rows},{1,2,3})
        obj.spin_min_pct=Spin(80)
        self.assertEqual({r['ogrenci_id'] for r in fn(obj)},{2,3})
        obj.cmb_sinif=Combo('Hepsi')
        obj.spin_min_pct=Spin(0)
        obj.settings={'aktarilan_sayilma_sekli':'open'}
        rows=fn(obj)
        byid={r['ogrenci_id']:r for r in rows}
        self.assertEqual(byid[5]['basari_pct'],0.0)
        con.close()

    def test_protected_core_sources_untouched(self):
        hashes=json.loads((ROOT/'tests/v42_protected_hashes.json').read_text(encoding='utf-8'))
        for rel,expected in hashes.items():
            with self.subTest(path=rel):
                actual=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
                self.assertEqual(actual,expected)

    def test_ui_read_only_logic_present(self):
        dash=(ROOT/'ui/report_dashboard.py').read_text(encoding='utf-8')
        detail=(ROOT/'ui/student_detail.py').read_text(encoding='utf-8')
        self.assertIn('cohort_overview(rows)',dash)
        self.assertIn('if r["veri_var"] else "—"',dash)
        self.assertIn('observed_rate_evidence(',detail)
        self.assertIn('"📋 Veri Yok"',detail)
        self.assertNotIn('"🚨 Riskli"',detail)

if __name__=='__main__':
    unittest.main()
