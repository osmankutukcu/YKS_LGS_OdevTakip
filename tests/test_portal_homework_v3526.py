# -*- coding: utf-8 -*-
"""V3.5.26 report fidelity + HTML hardening, synthetic data only, no Qt."""
from __future__ import annotations
import hashlib
import ast
from html import escape as html_escape
import json
from pathlib import Path
import sqlite3
import unittest
import importlib.util
import types
import sys
from unittest.mock import patch

from services.portal_homework_v3526 import subject_progress, pending_homework

ROOT = Path(__file__).resolve().parents[1]


class PortalCountContract(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.addCleanup(self.c.close)
        self.c.executescript('''
            CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT,
                              kitap_ad TEXT,konu_ad TEXT,durum TEXT);
            CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,odev_id INTEGER,ogrenci_id INTEGER,
                                    ders TEXT,kitap TEXT,konu TEXT,tarih TEXT,durum TEXT);
            INSERT INTO odev VALUES(10,1,'Fizik','Kaynak','İvme','devam');
            INSERT INTO odev VALUES(11,1,'Fizik','Kaynak','Enerji','yapildi');
            INSERT INTO odev VALUES(20,2,'Fizik','Kaynak','İvme','tamam');
            INSERT INTO odev_satir VALUES(100,10,1,'Fizik','Kaynak','İvme','2026-10-18','tamam');
        ''')

    def test_linked_row_not_double_counted_and_child_status_wins(self):
        # ID 10 parent pending + linked child completed, ID 11 independent completed.
        self.assertEqual(subject_progress(self.c, 1), (['Fizik'], [100]))
        self.assertEqual(pending_homework(self.c, 1), [])

    def test_legacy_null_link_counts_as_separate_task(self):
        self.c.execute('INSERT INTO odev_satir VALUES(101,NULL,1,\'Fizik\',\'K\',\'Legacy\',\'2026-10-15\',\'devam\')')
        self.assertEqual(subject_progress(self.c, 1), (['Fizik'], [66]))
        self.assertEqual([r['konu'] for r in pending_homework(self.c, 1)], ['Legacy'])

    def test_cross_student_wrong_link_does_not_hide_parent(self):
        # Damaged B->A link must not make A's parent disappear.
        self.c.execute("INSERT INTO odev_satir VALUES(102,11,2,'Fizik','K','Wrong','2026-10-18','devam')")
        self.assertEqual(subject_progress(self.c, 1), (['Fizik'], [100]))
        self.assertEqual(subject_progress(self.c, 2), (['Fizik'], [50]))

    def test_multiple_linked_child_rows_are_not_assumed_duplicates(self):
        self.c.execute("INSERT INTO odev_satir VALUES(103,10,1,'Fizik','K','Alt Görev','2026-10-18','devam')")
        self.assertEqual(subject_progress(self.c, 1), (['Fizik'], [66]))
        self.assertEqual(len(pending_homework(self.c, 1)), 1)

    def test_legacy_schema_without_explicit_link_keeps_both(self):
        self.c.executescript('DROP TABLE odev_satir;'
            'CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT,kitap TEXT,konu TEXT,tarih TEXT,durum TEXT);'
            "INSERT INTO odev_satir VALUES(100,1,'Fizik','Kaynak','İvme','2026-10-18','tamam');")
        self.assertEqual(subject_progress(self.c, 1), (['Fizik'], [66]))


    def test_full_portal_data_reuses_projection_for_both_sections(self):
        self.c.executescript('''
        CREATE TABLE ogrenci_perf_gunluk(ogrenci_id INTEGER, gun TEXT, tamam INTEGER);
        INSERT INTO ogrenci_perf_gunluk VALUES(1,'2026-10-18',1);
        ''')
        # Import portal with a db stub only for this call, not global Qt/db effects.
        fake_db = types.ModuleType('db')
        analytics = types.ModuleType('utils.analytics_engine')
        analytics.rebuild_daily = lambda *_args: None
        analytics.rebuild_weekly_by_ders = lambda *_args: None
        spec = importlib.util.spec_from_file_location('isolated_portal_v3526', ROOT/'utils/web_portal.py')
        portal = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'db': fake_db, 'utils.analytics_engine':analytics}):
            spec.loader.exec_module(portal)
            obj = portal.WebPortalGenerator.__new__(portal.WebPortalGenerator)
            obj.sid, obj.name, obj.con = 1, 'Test Öğrenci', self.c
            result = obj._fetch_data()
        self.assertEqual(result['charts']['subjects'], ['Fizik'])
        self.assertEqual(result['charts']['subj_rates'], [100])
        self.assertEqual(result['pending'], [])

    def test_invalid_limit_does_not_query(self):
        for value in (-1, 0, 101, '10'):
            with self.subTest(limit=value), self.assertRaises(ValueError):
                pending_homework(self.c, 1, limit=value)

    def test_queries_never_write(self):
        before = '\n'.join(self.c.iterdump())
        for _ in range(3):
            subject_progress(self.c, 1)
            pending_homework(self.c, 1)
        self.assertEqual(before, '\n'.join(self.c.iterdump()))


class HtmlExportContract(unittest.TestCase):
    def test_student_and_task_data_cannot_inject_html(self):
        source = {'student_name': 'A <script>alert(1)</script>',
                  'generated_at': '18.10.2026',
                  'stats': {'success_rate': 0, 'done_tasks_30d': 0,'total_tasks_30d': 0},
                  'charts': {'subjects': ["Ders'</script><img src=x onerror=alert(1)>"],
                             'subj_rates': [0], 'weeks': [], 'weekly_rates': []},
                  'pending': [{'ders': '<img src=x>', 'kitap':'A&B',
                               'konu': '<script>alert(2)</script>', 'tarih':'" onmouseover="x'}]}
        # Extract only the pure HTML renderer; importing db.py would load PyQt6.
        node = ast.parse((ROOT/'utils/web_portal.py').read_text('utf8'))
        klass = next(n for n in node.body if isinstance(n,ast.ClassDef) and n.name=='WebPortalGenerator')
        method = next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='_render_html')
        scope = {'json':json, 'html_escape':html_escape}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])), '<portal>', 'exec'), scope)
        html = scope['_render_html'](None, source)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('<script>alert(2)</script>', html)
        self.assertNotIn('<img src=x>', html)
        self.assertNotIn('</script><img src=x onerror=alert(1)>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',html)
        self.assertIn('A&amp;B', html)
        self.assertIn('const data = {', html)
        self.assertNotIn('JSON.parse(', html)


class ProtectedCoreContract(unittest.TestCase):
    def test_core_files_identical_to_approved_v42_baseline(self):
        baseline = json.loads((ROOT/'tests/v42_protected_hashes.json').read_text('utf8'))
        for name, digest in baseline.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)



class StabilizationGateContract(unittest.TestCase):
    def test_gate_reports_duplicate_handlers_without_modifying(self):
        from tools.v3526_stabilization_gate import source_gate
        report = source_gate(ROOT)
        self.assertEqual(report['pilot_source_status'], 'PASS')
        self.assertEqual(report['protected_files_changed'], [])
        self.assertTrue(report['report_linked'])
        self.assertEqual(report['windows_user_acceptance'], 'NOT_VERIFIED')
        self.assertFalse(report['public_release_ready'])
        self.assertTrue(report['duplicate_handlers_observed_not_deleted']['ui/homework_form.py'])

    def test_gate_detects_unapproved_core_change(self):
        from tools.v3526_stabilization_gate import source_gate
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'tests').mkdir()
            (folder/'ui').mkdir()
            (folder/'services').mkdir()
            shutil.copy2(ROOT/'tests/v42_protected_hashes.json',folder/'tests/v42_protected_hashes.json')
            baseline = json.loads((ROOT/'tests/v42_protected_hashes.json').read_text('utf8'))
            for name in baseline:
                target=folder/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/name,target)
            shutil.copy2(ROOT/'services/portal_homework_v3526.py',folder/'services/portal_homework_v3526.py')
            shutil.copy2(ROOT/'utils/web_portal.py', (folder/'utils/web_portal.py') if (folder/'utils').mkdir(exist_ok=True) is None else folder/'utils/web_portal.py')
            with (folder/'ui/homework_form.py').open('a',encoding='utf8') as out:out.write('\n# unapproved core mutation\n')
            self.assertEqual(source_gate(folder)['pilot_source_status'],'BLOCK')


if __name__ == '__main__':
    unittest.main()
