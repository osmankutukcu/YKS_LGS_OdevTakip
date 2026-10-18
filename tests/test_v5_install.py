import shutil
import os
import zipfile
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from install_integrated_v5 import install,rollback,digest,FILES
except ImportError:
    install = rollback = digest = None
    FILES = ()

BASE=Path(__file__).resolve().parents[1]
ORIGINAL_ZIP=Path(os.environ.get('V5_ORIGINAL_ZIP','/mnt/data/YKS_LGS_HomeworkManager_v2_Son_Hal.zip'))
V4_PATCH=Path(os.environ.get('V5_V4_ZIP','/mnt/data/OdevTakip_V4_TekEkran_Akilli_Oncelik_Kumulatif_Guvenli.zip'))
V1_PATCH=Path(os.environ.get('V5_V1_ZIP','/mnt/data/OdevTakip_Akilli_Konu_Menu_V1_Guvenli_Eklenti.zip'))
V2_PATCH=Path(os.environ.get('V5_V2_ZIP','/mnt/data/OdevTakip_V2_Mevcut_Modul_Entegrasyon_Guvenli.zip'))
V3_PATCH=Path(os.environ.get('V5_V3_ZIP','/mnt/data/OdevTakip_V3_Ogrenci360_AdaptifKoc_YerelCanli_Entegre_Guvenli.zip'))


class V5InstallTests(unittest.TestCase):
    def setUp(self):
        if install is None or not ORIGINAL_ZIP.is_file() or not V4_PATCH.is_file():
            self.skipTest('Kurulum testleri için install_integrated_v5, V5_ORIGINAL_ZIP ve V5_V4_ZIP gereklidir.')
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        for rel in ['main_window.py','ui/homework_form.py',
                    'ui/student_workspace_panel_v21.py',
                    'ui/homework_workspace_bridge_v21.py',
                    'services/daily_coach_v10.py','services/daily_brief_v11.py']:
            dest=self.root/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            with zipfile.ZipFile(ORIGINAL_ZIP) as z:
                dest.write_bytes(z.read(rel))

    def tearDown(self):self.tmp.cleanup()

    def _set_v4(self):
        for rel in FILES:
            if rel in ('services/teacher_feedback_v5.py','services/teacher_copilot_v5.py',
                       'ui/teacher_copilot_strip_v5.py'):
                continue
            target=self.root/rel
            target.parent.mkdir(exist_ok=True,parents=True)
            with zipfile.ZipFile(V4_PATCH) as z:
                target.write_bytes(z.read(rel))

    def test_original_v4_install_rollback(self):
        for base in ('original','v4'):
            with self.subTest(base=base):
                if base == 'v4':self._set_v4()
                original=digest(self.root/'ui/homework_form.py')
                result=install(self.root,BASE,check=True)
                self.assertIn('UYGUN',result)
                self.assertEqual(digest(self.root/'ui/homework_form.py'),original)
                self.assertIn('V5 kuruldu',install(self.root,BASE))
                self.assertEqual(digest(self.root/'ui/homework_form.py'),
                                 digest(BASE/'ui/homework_form.py'))
                self.assertIn('geri alındı',rollback(self.root))
                self.assertEqual(digest(self.root/'ui/homework_form.py'),original)
                if base=='original':
                    self._set_v4()

    def test_older_audited_upgrades(self):
        import zipfile
        sources = {'v1':V1_PATCH, 'v2':V2_PATCH, 'v3':V3_PATCH}
        for name, filename in sources.items():
            with self.subTest(name=name):
                if not filename.is_file():
                    self.skipTest('V1/V2/V3 ZIP testleri için ilgili ortam değişkenini ayarlayın.')
                self.tearDown(); self.setUp()
                with zipfile.ZipFile(filename) as z:
                    for rel in z.namelist():
                        if rel in FILES and rel != 'main_window.py':
                            p = self.root/rel
                            p.parent.mkdir(parents=True,exist_ok=True)
                            p.write_bytes(z.read(rel))
                self.assertIn('UYGUN',install(self.root,BASE,check=True))
                self.assertIn('V5 kuruldu',install(self.root,BASE))
                self.assertIn('geri alındı',rollback(self.root))

    def test_custom_main_rejected_untouched(self):
        p=self.root/'main_window.py'
        p.write_text(p.read_text()+'\n# changed')
        with self.assertRaises(ValueError):install(self.root,BASE)
        self.assertFalse((self.root/'.integrated_v5_backups').exists())

    def test_rollback_rejects_changes(self):
        install(self.root,BASE)
        p=self.root/'services/teacher_copilot_v5.py'
        p.write_text(p.read_text()+'\n# edited')
        with self.assertRaises(ValueError):rollback(self.root)

if __name__=='__main__':unittest.main()
