"""Installer compatibility using synthetic copies of audited source files.

Reads the original/current fixture paths from the build environment only;
never writes to the actual uploaded project.
"""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
try:
    from install_integrated_v4 import verify, install, rollback, digest
except ImportError:
    verify = install = rollback = digest = None

ORIGINAL = Path('/mnt/data/homework_v2_audit')
V1 = Path('/mnt/data/homework_context_v1_build')
V2 = Path('/mnt/data/homework_context_v2_build')
V3 = Path('/mnt/data/homework_live_v3_build')

@unittest.skipIf(install is None or not ORIGINAL.is_dir(), "Tekil V4 kurucusu veya /mnt/data fikstürleri mevcut değil.")
class V4InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for f in ['main_window.py', 'ui/homework_form.py',
                  'ui/student_workspace_panel_v21.py',
                  'ui/homework_workspace_bridge_v21.py',
                  'services/daily_coach_v10.py',
                  'services/daily_brief_v11.py']:
            dest=self.root/f;dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copy2(ORIGINAL/f,dest)

    def tearDown(self):
        self.tmp.cleanup()

    def _prepare(self,version):
        if version=='original':return
        src = V1 if version=='v1' else (V2 if version=='v2' else V3)
        files=['ui/homework_form.py','ui/homework_context_hub_v1.py',
               'ui/homework_context_logic_v1.py']
        if version in ('v2','v3'):
            files+=['ui/homework_context_integrations_v2.py']
        if version=='v3':
            files+=['ui/student_workspace_panel_v21.py',
                    'ui/homework_workspace_bridge_v21.py',
                    'services/live_student_summary_v3.py']
        for f in files:
            dest=self.root/f;dest.parent.mkdir(exist_ok=True,parents=True)
            shutil.copy2(src/f,dest)

    def test_installs_and_rollback_from_each_audited_base(self):
        for version in ('original','v1','v2','v3'):
            with self.subTest(version=version):
                # Reset same sandbox, not the actual source.
                self.tearDown();self.setUp()
                self._prepare(version)
                self.assertEqual(verify(self.root),version)
                originals={f:digest(self.root/f) if (self.root/f).exists() else None
                           for f in ('main_window.py','ui/homework_form.py',
                                     'ui/student_workspace_panel_v21.py')}
                self.assertIn('UYGUN',install(self.root,BASE,check=True))
                self.assertIn('V4 kuruldu',install(self.root,BASE))
                self.assertEqual(digest(self.root/'ui/homework_form.py'),digest(BASE/'ui/homework_form.py'))
                self.assertIn('geri alındı',rollback(self.root))
                for f,h in originals.items():
                    self.assertEqual(digest(self.root/f) if (self.root/f).exists() else None,h)

    def test_modified_original_rejected_without_touching_anything(self):
        p=self.root/'main_window.py';p.write_text(p.read_text()+'\n# user change',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Denetlenmeyen'):
            install(self.root,BASE)
        self.assertFalse((self.root/'.integrated_v4_backups').exists())

    def test_refuses_rollback_after_user_edits(self):
        install(self.root,BASE)
        p=self.root/'services/today_priority_v4.py'
        p.write_text(p.read_text()+'\n# modified')
        with self.assertRaisesRegex(ValueError,'Geri alma güvenliği'):
            rollback(self.root)

if __name__=='__main__':unittest.main()
