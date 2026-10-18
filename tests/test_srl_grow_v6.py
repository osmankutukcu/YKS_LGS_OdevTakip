"""No real students or PyQt dependency are needed for these security checks."""
import ast
from hashlib import sha256
from pathlib import Path
import tempfile
import shutil
import os
import sys
import zipfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE_ZIP=Path(os.environ.get('SOURCE_ZIP_FOR_TESTS', '/mnt/data/YKS_LGS_HomeworkManager_v2_Son_Hal.zip'))
sys.path.insert(0,str(ROOT))
from services.srl_grow_guide_v6 import PHASES, phase, append_prompt
try:
    from install_srl_grow_v6 import install, rollback, preflight, FILES, EXPECTED
except ImportError:
    install = rollback = preflight = FILES = EXPECTED = None

class GuidanceTests(unittest.TestCase):
    def test_four_unique_phases(self):
        self.assertEqual([x.key for x in PHASES],['R','G','O','W'])
        self.assertTrue(all(len(x.questions)>=3 for x in PHASES))
    def test_append_to_existing_text_without_deleting(self):
        src='Önceden yazılan özgün görüşme notu'
        q=phase('R').questions[0]
        out=append_prompt(src,q,phase_key='R')
        self.assertTrue(out.startswith(src))
        self.assertIn(q,out)
        self.assertEqual(append_prompt(out,q,phase_key='R'),out)
    def test_untrusted_or_mismatched_question_rejected(self):
        with self.assertRaises(ValueError):
            append_prompt('', 'Sahte kesin tanı',phase_key='R')
        with self.assertRaises(ValueError):
            append_prompt('',phase('W').questions[0],phase_key='G')
    def test_no_auto_actions_or_db_in_new_modules(self):
        service=(ROOT/'services/srl_grow_guide_v6.py').read_text()
        ui=(ROOT/'ui/srl_grow_guide_v6.py').read_text()
        for block in (service,ui):
            for forbidden in ('sqlite3','db.get_conn','UPDATE ogrenci','UPDATE odev','INSERT INTO','DELETE FROM','btnKaydet.click','webbrowser','requests.post','urllib.request'):
                self.assertNotIn(forbidden,block)
    @unittest.skipUnless(BASE_ZIP.is_file(), "Orijinal ZIP yok; kaynak karşılaştırması atlandı")
    def test_only_notes_initializer_method_changed(self):
        with zipfile.ZipFile(BASE_ZIP) as z:
            before=ast.parse(z.read('ui/coaching_manager.py').decode())
        after=ast.parse((ROOT/'ui/coaching_manager.py').read_text())
        def functions(t):
            return {n.name:ast.dump(n,include_attributes=False) for cls in t.body
                    if isinstance(cls,ast.ClassDef) and cls.name=='CoachingManager'
                    for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        a,b=functions(before),functions(after)
        self.assertEqual(a.keys(),b.keys())
        self.assertEqual([k for k in a if a[k]!=b[k]],['_init_tab_notes'])
    @unittest.skipUnless(install is not None, "Birleşik V12 kaynağında bağımsız V6 paket testi atlandı")
    def test_homework_form_not_in_bundle(self):
        self.assertFalse((ROOT/'ui/homework_form.py').exists())
        self.assertFalse(any(p.suffix in ('.db','.sqlite') for p in ROOT.rglob('*') if p.is_file()))

@unittest.skipUnless(BASE_ZIP.is_file() and install is not None, "Orijinal ZIP yok; kurulum fixture testi atlandı")
class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'ui').mkdir(); (self.root/'services').mkdir()
        (self.root/'main_window.py').write_text('original main window')
        (self.root/'ui/homework_form.py').write_text('untouched homework')
        with zipfile.ZipFile(BASE_ZIP) as z:
            (self.root/'ui/coaching_manager.py').write_bytes(z.read('ui/coaching_manager.py'))
    def tearDown(self): self.temp.cleanup()
    def test_install_and_rollback_keep_homework_untouched(self):
        original=(self.root/'ui/homework_form.py').read_bytes()
        self.assertIn('UYGUN', install(self.root,ROOT,check=True))
        self.assertIn('kuruldu',install(self.root,ROOT))
        for rel in FILES:self.assertEqual(sha256((self.root/rel).read_bytes()).hexdigest(),EXPECTED[rel])
        self.assertEqual(original,(self.root/'ui/homework_form.py').read_bytes())
        self.assertIn('geri alındı',rollback(self.root))
        self.assertEqual(original,(self.root/'ui/homework_form.py').read_bytes())
        self.assertFalse((self.root/'ui/srl_grow_guide_v6.py').exists())
    def test_modified_coaching_file_rejected(self):
        with (self.root/'ui/coaching_manager.py').open('ab') as f:f.write(b'# custom')
        with self.assertRaises(ValueError):install(self.root,ROOT,check=True)
    def test_duplicate_install_rejected(self):
        install(self.root,ROOT)
        with self.assertRaises(ValueError):install(self.root,ROOT)
    def test_rollback_rejects_post_install_edits(self):
        install(self.root,ROOT)
        with (self.root/'ui/srl_grow_guide_v6.py').open('ab') as f:f.write(b'# edit')
        with self.assertRaises(ValueError):rollback(self.root)

if __name__=='__main__':unittest.main()
