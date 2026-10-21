import unittest
from tools.v3588_unified_preflight import check, ROOT

class UnifiedSourceTests(unittest.TestCase):
    def test_single_project_root(self):
        self.assertGreater(check(ROOT), 10)

    def test_original_report_shortcuts_preserved(self):
        app=(ROOT/'app.py').read_text('utf-8')
        scope=app.split('# 2.1',1)[1].split('# 3. Üst Gri Şeridi',1)[0]
        self.assertIn('.hide()',scope)
        self.assertIn('ReportCenterDialog',scope)
        self.assertIn('QMessageBox.warning',scope)

    def test_release_requires_manual_acceptance(self):
        s=(ROOT/'.github/workflows/build_installer.yml').read_text('utf-8')
        self.assertIn('Gercek Windows manuel kabul kaydi bulunmuyor',s)
        self.assertIn('Mac/mobil manuel cihaz kabul kaydi yok',s)
