# -*- coding: utf-8 -*-
"""V35 release blocker and Windows smoke safety tests; no PyQt6 needed."""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v35_release_gate import (MANUAL_CHECKS, app_version, check_source,
                                    template, validate_acceptance)
from tools.v35_windows_smoke import smoke


class ReleaseGates(unittest.TestCase):
    def fake(self):
        payload=template(app_version())
        payload.update({'git_commit':'a'*40,'tested_at':date.today().isoformat(),
                        'tester':'Windows pilot test sorumlusu', 'windows':'Windows 11 x64'})
        payload['checks']={c:'PASS' for c in MANUAL_CHECKS}
        return payload

    def test_protected_sources_unchanged_and_version_consistent(self):
        result=check_source(ROOT)
        self.assertEqual('PASS',result['source_status'])
        self.assertEqual('NOT_VERIFIED',result['manual_windows_acceptance'])
        self.assertGreaterEqual(result['protected_files'],4)

    def test_template_never_claims_approval(self):
        self.assertTrue(all(v=='PENDING' for v in template()['checks'].values()))

    def test_manual_no_record_blocks(self):
        proc=subprocess.run([sys.executable,str(ROOT/'tools/v35_release_gate.py'),
                             '--require-acceptance','--acceptance',
                             'release/does_not_exist.json'],cwd=ROOT,capture_output=True,text=True)
        self.assertNotEqual(0,proc.returncode)
        self.assertIn('ENGEL',proc.stderr)

    def test_acceptance_exact_commit(self):
        result=validate_acceptance(self.fake(),version=app_version(),commit='a'*40)
        self.assertEqual(len(MANUAL_CHECKS),result['manual_checks'])
        with self.assertRaisesRegex(ValueError,'commit'):
            validate_acceptance(self.fake(),version=app_version(),commit='b'*40)

    def test_missing_manual_checks_block(self):
        obj=self.fake();obj['checks']['control_checkbox_save_reopen']='PENDING'
        with self.assertRaisesRegex(ValueError,'PASS'):
            validate_acceptance(obj,version=app_version(),commit='a'*40)

    def test_expired_future_and_placeholder_evidence_block(self):
        obj=self.fake();obj['tested_at']=(date.today()-timedelta(days=31)).isoformat()
        with self.assertRaisesRegex(ValueError,'30 günden'):
            validate_acceptance(obj,version=app_version(),commit='a'*40)
        obj=self.fake();obj['tested_at']=(date.today()+timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError,'gelecek'):
            validate_acceptance(obj,version=app_version(),commit='a'*40)
        obj=self.fake();obj['tester']='<test>'
        with self.assertRaisesRegex(ValueError,'tester'):
            validate_acceptance(obj,version=app_version(),commit='a'*40)

    def test_source_tamper_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'ui').mkdir()
            for f in ('ui/homework_form.py','ui/odev_kontrol.py','db.py',
                      'main_window.py','version.py','setup.iss'):
                p=root/f;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes((ROOT/f).read_bytes())
            self.assertEqual('PASS',check_source(root)['source_status'])
            (root/'ui/homework_form.py').write_text('CHANGED',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Korunan kaynak'):
                check_source(root)

    def test_ci_tag_gate_and_smoke_presence(self):
        text=(ROOT/'.github/workflows/build_installer.yml').read_text(encoding='utf-8')
        self.assertIn('tools/v35_release_gate.py --require-acceptance',text)
        self.assertIn('tools/v35_windows_smoke.py --exe',text)
        self.assertIn('dist/v35_windows_smoke.json',text)


class SmokeSafety(unittest.TestCase):
    def test_non_windows_refuses(self):
        with self.assertRaisesRegex(ValueError,'Windows'):
            smoke('irrelevant.exe',platform='linux')

    def test_refuse_non_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt=Path(tmp)/'not_an_exe.txt';txt.write_text('not an exe',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'EXE'):
                smoke(txt,platform='win32',seconds=2)

    def test_smoke_temp_test_db_never_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/'test.exe';exe.write_bytes(b'MZdummy')
            captured=[]
            class FakeProc:
                def poll(self):return None
                def terminate(self):pass
                def wait(self,timeout=None):pass
            def fake_popen(cmd,**kwargs):
                from services.pilot_boot_guard_v35 import write_pilot_ready
                env=kwargs['env']
                write_pilot_ready(Path(env['YKS_DB_PATH']),env)
                captured.append((cmd,kwargs));return FakeProc()
            with patch.dict(os.environ,{'YKS_DB_PATH':'C:/DO_NOT_TOUCH/live.db'}):
                report=smoke(exe,platform='win32',seconds=2,popen=fake_popen,
                             sleep=lambda _:None)
            self.assertEqual('PASS',report['result'])
            self.assertEqual(Path(exe).resolve(), Path(captured[0][0][0]).resolve())
            self.assertTrue(captured[0][1]['env']['YKS_DB_PATH'].endswith('synthetic_only.db'))
            self.assertNotEqual(captured[0][1]['env']['YKS_DB_PATH'],'C:/DO_NOT_TOUCH/live.db')
            self.assertIn('checkbox',report['not_verified'])

if __name__=='__main__': unittest.main()
