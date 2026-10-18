# -*- coding: utf-8 -*-
"""V7 read-only student survey evidence tests, independent of PyQt.
Execute with PYTHONPATH=<bundle_dir> pytest ...
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from services.survey_evidence_v7 import read_survey_evidence, brief_lines, META, KEYS
try:
    from install_survey_evidence_v7 import install, rollback
except ImportError:
    install = rollback = None

BUNDLE=Path(__file__).resolve().parents[1]


def create_db():
    con=sqlite3.connect(':memory:')
    con.execute('CREATE TABLE ogrenci_anket (id INTEGER PRIMARY KEY, ogrenci_id INTEGER NOT NULL, anket_kodu TEXT, cevaplar TEXT, tarih TEXT)')
    return con


def add(con, student, code, answers, date='2026-10-15 12:00'):
    con.execute('INSERT INTO ogrenci_anket (ogrenci_id,anket_kodu,cevaplar,tarih) VALUES (?,?,?,?)',
                (student,code, json.dumps(answers,ensure_ascii=False) if not isinstance(answers,str) else answers,date))
    con.commit()


class SurveySafetyTests(unittest.TestCase):
    def test_student_isolation(self):
        con=create_db()
        add(con,2,'study_habits',{'sh_1':5})
        self.assertEqual(read_survey_evidence(con,1).records, ())
        self.assertEqual(read_survey_evidence(con,2).records[0].answered,1)

    def test_zero_preset_and_no_imputation(self):
        con=create_db();add(con,1,'study_habits',{'sh_1':5,'sh_2':None, 'sh_3':False,'sh_4':0,'sh_5':6,'bad':5})
        e=read_survey_evidence(con,1)
        self.assertEqual(e.records[0].answered,1)
        self.assertIn('1/10', '\n'.join(brief_lines(e)))
        self.assertNotIn('puan', '\n'.join(brief_lines(e)).lower())

    def test_latest_per_survey_by_id(self):
        con=create_db()
        add(con,1,'study_habits',{'sh_1':5, 'sh_2':4},date='2026-10-13 12:00')
        add(con,1,'study_habits',{'sh_1':1},date='2026-10-15 12:00')
        rec=read_survey_evidence(con,1).records
        self.assertEqual(len(rec),1);self.assertEqual(rec[0].answered,1)

    def test_corrupt_newest_does_not_use_old(self):
        con=create_db()
        add(con,1,'study_habits',{'sh_1':5})
        add(con,1,'study_habits','{BAD')
        e=read_survey_evidence(con,1)
        self.assertFalse(e.records)
        self.assertEqual(e.malformed,1)

    def test_sensitive_omitted_from_overview(self):
        con=create_db();add(con,1,'exam_anxiety',{'ea_1':5});add(con,1,'sleep_energy',{'se_1':5})
        e=read_survey_evidence(con,1)
        lines='\n'.join(brief_lines(e))
        self.assertNotIn('Sınav deneyimi', lines)
        self.assertNotIn('Uyku ve enerji',lines)
        self.assertNotIn('5/10', lines)
        self.assertNotIn('2/9',lines)

    def test_stale_and_incomplete(self):
        con=create_db()
        add(con,1,'time_management',{'tm_1':1},'2026-04-01 12:00')
        e=read_survey_evidence(con,1,as_of=datetime(2026,10,15,18))
        self.assertTrue(e.records[0].possibly_stale)
        self.assertIn('güncelliği', '\n'.join(brief_lines(e)))

    def test_missing_table_and_invalid_student(self):
        con=sqlite3.connect(':memory:')
        self.assertFalse(read_survey_evidence(con,1).records)
        for bad in (0, -1, '1',True):
            with self.assertRaises(ValueError):read_survey_evidence(con,bad)

    def test_readonly_and_no_write(self):
        con=create_db();add(con,1,'study_habits',{'sh_1':3})
        con.execute('PRAGMA query_only=ON')
        before=con.execute('SELECT COUNT(*) FROM ogrenci_anket').fetchone()
        read_survey_evidence(con,1)
        after=con.execute('SELECT COUNT(*) FROM ogrenci_anket').fetchone()
        self.assertEqual(before,after)

    def test_meta_key_lengths(self):
        self.assertEqual(set(META),set(KEYS))
        for code,(_,length,_) in META.items():self.assertEqual(length,len(KEYS[code]))

    def test_no_dashboard_hard_diagnosis(self):
        con=create_db();add(con,1,'procrastination',{'p_1':5,'p_2':5,'p_3':5,'p_4':5})
        t=' '.join(brief_lines(read_survey_evidence(con,1)))
        for label in ('tembel','yüksek risk','sahte çalışan','tükenmişlik','mükemmeliyetçi erteleyen'):
            self.assertNotIn(label,t.lower())

    def test_surveys_not_duplicated(self):
        root=BUNDLE
        if install is not None:
            self.assertFalse((root/'ui/survey_manager.py').exists())
            self.assertFalse((root/'ui/homework_form.py').exists())
        self.assertTrue((root/'services/survey_evidence_v7.py').exists())

@unittest.skipUnless(install is not None, "Birleşik V12 kaynağında bağımsız V7 kurulum testi atlandı")
class InstallTests(unittest.TestCase):
    def fixture(self,workspace_v5=False):
        root=Path(tempfile.mkdtemp(prefix='v7_install_'))
        fixtures=BUNDLE/'tests/fixtures'
        for n in ('main_window.py','ui/homework_form.py'):
            target=root/n;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text('# Test için boş güvenlik sabiti\n',encoding='utf-8')
        srcs={
            'ui/student360_panel_v16.py': fixtures/'original_student360_panel_v16.py',
            'ui/student_workspace_panel_v21.py': fixtures/('v5_student_workspace_panel_v21.py' if workspace_v5
                                                else 'original_student_workspace_panel_v21.py'),
        }
        for name,src in srcs.items():
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(src.read_bytes())
        (root/'services').mkdir(exist_ok=True)
        return root

    def test_install_original_roundtrip(self):
        root=self.fixture()
        homework=hashlib.sha256((root/'ui/homework_form.py').read_bytes()).hexdigest()
        existing={n:(root/n).read_bytes() for n in ('ui/student360_panel_v16.py','ui/student_workspace_panel_v21.py')}
        self.assertIn('UYGUN', install(root,BUNDLE,check=True))
        self.assertFalse((root/'services/survey_evidence_v7.py').exists())
        self.assertIn('V7 kuruldu', install(root,BUNDLE))
        self.assertEqual(homework,hashlib.sha256((root/'ui/homework_form.py').read_bytes()).hexdigest())
        self.assertIn('geri alındı',rollback(root))
        for n,data in existing.items():self.assertEqual((root/n).read_bytes(),data)
        self.assertFalse((root/'services/survey_evidence_v7.py').exists())

    def test_install_v5_variant(self):
        root=self.fixture(workspace_v5=True)
        self.assertIn('UYGUN',install(root,BUNDLE,check=True))
        install(root,BUNDLE)
        target=root/'ui/student_workspace_panel_v21.py'
        self.assertEqual(target.read_bytes(),(BUNDLE/'variants/student_workspace_panel_v21_v5.py').read_bytes())
        self.assertIn('geri alındı',rollback(root))

    def test_modified_unsupported_source_refused(self):
        root=self.fixture()
        with (root/'ui/student360_panel_v16.py').open('a') as f:f.write('\n# user special change\n')
        with self.assertRaises(ValueError):install(root,BUNDLE)
        self.assertFalse((root/'services/survey_evidence_v7.py').exists())

    def test_second_install_refused(self):
        root=self.fixture();install(root,BUNDLE)
        with self.assertRaises(ValueError):install(root,BUNDLE)

    def test_tampered_after_install_cannot_rollback(self):
        root=self.fixture();install(root,BUNDLE)
        with (root/'ui/student360_panel_v16.py').open('a') as f:f.write('\n# post install custom\n')
        with self.assertRaises(ValueError):rollback(root)

if __name__ == '__main__':unittest.main()
