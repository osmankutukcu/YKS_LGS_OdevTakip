# -*- coding: utf-8 -*-
"""V3.5.40 release regression; no Qt, network, or real student records."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.v3540_preflight import (
    ROOT, inspect_source, inventory_sensitive_source, verify_workflow, _step,
)
from tools.v35_release_gate import template

WORKFLOW = (ROOT/'.github/workflows/build_installer.yml').read_text('utf8')


class ReleaseSafetyV3540(unittest.TestCase):
    def test_full_preflight_reports_not_release_authorized(self):
        data = inspect_source(ROOT)
        self.assertEqual('PASS', data['source_status'], data['blockers'])
        self.assertFalse(data['production_release_authorized'])
        self.assertEqual('NOT_VERIFIED', data['manual_windows_uat'])
        self.assertEqual('NOT_VERIFIED', data['windows_installer_smoke'])
        self.assertEqual(10, data['details']['protected_core']['protected_files'])

    def test_release_source_version_triple_agree(self):
        from version import APP_VERSION
        data = inspect_source(ROOT)
        self.assertEqual(APP_VERSION, data['details']['version'])
        self.assertGreater(data['details']['python_files_parsed'], 500)
        self.assertEqual(0, data['details']['python_syntax_failures'])

    def test_windows_smoke_step_present(self):
        step = _step(WORKFLOW, 'Gercek Windows EXE izole sahte veritabani acilis testi')
        self.assertIn('tools/v35_windows_smoke.py --exe', step)
        self.assertFalse(verify_workflow(WORKFLOW))

    def test_missing_windows_acceptance_gate_verified(self):
        step = _step(WORKFLOW, 'Etiket icin gercek Windows manuel kabul kaydi zorunlu')
        self.assertIn('--require-acceptance', step)
        self.assertIn('throw', step)
        self.assertFalse(verify_workflow(WORKFLOW))

    def test_manual_validator_failure_must_throw(self):
        changed = WORKFLOW.replace("if ($LASTEXITCODE -ne 0) { throw", "Write-Host 'ignore")
        self.assertIn('WINDOWS_MANUAL_FAILED_VALIDATION_NOT_BLOCKING', verify_workflow(changed))

    def test_release_only_on_tag(self):
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", _step(WORKFLOW, 'v3.5.4 gibi etiketlerde Release yayinla'))
        self.assertIn('V3540_IN_CI_NOT_ENFORCED', verify_workflow(WORKFLOW.replace('python tools/v3540_preflight.py', 'Write-Host bypass')))

    def test_sensitive_filename_blocks_without_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d/'private.db').write_bytes(b'sensitive bytes not to read')
            (d/'.env').write_text('TOKEN=secret')
            (d/'license.json').write_text('secret')
            paths = inventory_sensitive_source(d)
            self.assertEqual({'.env','license.json','private.db'}, set(paths))

    def test_public_curriculum_reference_allowed_only_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            (d/'YKS_Kazanimlar.sqlite').write_bytes(b'catalog')
            (d/'ogrenci.sqlite').write_bytes(b'no')
            self.assertEqual(['ogrenci.sqlite'], inventory_sensitive_source(d))

    def test_template_must_remain_pending(self):
        self.assertTrue(all(x == 'PENDING' for x in template()['checks'].values()))

    def test_cli_source_only_return_success_does_not_approve_release(self):
        call = subprocess.run([sys.executable, str(ROOT/'tools/v3540_preflight.py')],cwd=ROOT,
                              text=True,capture_output=True,check=False)
        self.assertEqual(0,call.returncode,call.stderr)
        report=json.loads(call.stdout)
        self.assertFalse(report['production_release_authorized'])
        self.assertEqual('NOT_VERIFIED',report['manual_windows_uat'])


if __name__=='__main__':
    unittest.main()
