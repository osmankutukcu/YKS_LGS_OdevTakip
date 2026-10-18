"""V12 evidence and shell preflight, does not touch a user SQLite database."""
from __future__ import annotations
from datetime import date, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v12_release_readiness import (shell_preflight, original_provenance,
    evidence_template, validate_evidence, EXPECTED_PLATFORMS,
    REQUIRED_DEVICE_STEPS)

class V12ReadinessTests(unittest.TestCase):
    def test_all_pwa_assets_and_versions_are_consistent(self):
        report=shell_preflight(ROOT)
        self.assertEqual('PASS',report['result'])
        self.assertGreaterEqual(report['cached_assets'],15)
        self.assertEqual([],report['missing_assets'])

    def test_missing_one_js_asset_causes_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'web_api/static/js').mkdir(parents=True)
            (root/'web_api/templates').mkdir(parents=True)
            files=['web_api/static/sw.js','web_api/static/js/offline_health_v6.js',
                   'web_api/templates/index.html']
            for f in files:
                (root/f).write_bytes((ROOT/f).read_bytes())
            report=shell_preflight(root)
            self.assertEqual('FAIL',report['result'])
            self.assertIn('/static/js/offline_sync.js',report['missing_assets'])

    def test_pending_device_evidence_is_always_blocked(self):
        report=validate_evidence(evidence_template())
        self.assertTrue(report)
        self.assertTrue(any('iphone_safari' in e for e in report))
        self.assertTrue(any('windows_11' in e for e in report))

    def test_seven_days_must_be_real_calendar_span(self):
        form=evidence_template()
        form['project_commit']='a'*40
        form['reviewer']='Real Pilot Reviewer'
        form['manual_windows_acceptance']='PASS'
        form['protected_source_review']='PASS'
        for entry in form['devices'].values():
            entry['device_model']='Test model'
            entry['os_version']='OS 17.0'
            entry['tested_from']=(date.today()-timedelta(days=6)).isoformat()
            entry['tested_until']=date.today().isoformat()
            entry['steps']={step:'PASS' for step in REQUIRED_DEVICE_STEPS}
        self.assertTrue(any('yedi günlük' in p for p in validate_evidence(form)))
        for entry in form['devices'].values():
            entry['tested_from']=(date.today()-timedelta(days=7)).isoformat()
        self.assertEqual([],validate_evidence(form))

    def test_v11_existing_source_gate_still_blocks_release(self):
        from tools.v35_release_gate import check_source
        res = check_source(ROOT)
        self.assertEqual(res['source_status'], 'PASS')
        self.assertEqual(res['manual_windows_acceptance'], 'NOT_VERIFIED')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'ui').mkdir(parents=True)
            for f in ('ui/homework_form.py', 'ui/odev_kontrol.py', 'db.py', 'main_window.py', 'version.py', 'setup.iss'):
                (root / f).write_bytes((ROOT / f).read_bytes())
            (root / 'ui/homework_form.py').write_text('unreviewed change', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'ui/homework_form.py'):
                check_source(root)

    def test_original_zip_does_not_count_new_modules_as_changed(self):
        # Small fixture: additional modern files are NOT comparable to historical root.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'ui').mkdir(parents=True)
            (root/'ui/homework_form.py').write_text('legacy',encoding='utf-8')
            from zipfile import ZipFile
            z=Path(d)/'original.zip'
            with ZipFile(z,'w') as f: f.writestr('ui/homework_form.py','legacy')
            a=original_provenance(root,z)
            self.assertEqual('MATCH',a['result'])
            self.assertEqual('IDENTICAL',a['files']['ui/homework_form.py'])
            self.assertEqual('NOT_IN_ORIGINAL',a['files']['web_api/sync_transactions.py'])
            (root/'ui/homework_form.py').write_text('tampered',encoding='utf-8')
            self.assertEqual('MISMATCH',original_provenance(root,z)['result'])

    def test_production_flag_cannot_auto_grant_public_release(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'report.json'
            proc=subprocess.run([sys.executable,str(ROOT/'tools/v12_release_readiness.py'),
                '--require-production','--out',str(out)],cwd=ROOT,
                capture_output=True,text=True,timeout=35)
            self.assertNotEqual(proc.returncode,0)
            report=json.loads(out.read_text(encoding='utf-8'))
            self.assertFalse(report['production_release_approved'])
            self.assertIn(report['v35_protected_source_gate']['status'], ('PASS', 'BLOCKED'))

if __name__=='__main__':unittest.main()
