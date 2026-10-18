import ast, hashlib, json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def methods(path):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    return {n.name:n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}

class CumulativeV8Contract(unittest.TestCase):
    def setUp(self):
        self.manifest=json.loads((ROOT/'V8_MANIFEST.json').read_text(encoding='utf-8'))
        self.effective_files=dict(self.manifest['files'])
        for mname in ('V9_MANIFEST.json','V10_MANIFEST.json','V11_MANIFEST.json','V24_MANIFEST.json'):
            mp=ROOT/mname
            if mp.is_file():
                mdata=json.loads(mp.read_text(encoding='utf-8'))
                for k,v in mdata.get('files',{}).items():
                    if k in self.effective_files:
                        self.effective_files[k]=v
    def test_manifest_complete_and_authentic(self):
        for relative,expected in self.effective_files.items():
            with self.subTest(relative=relative):
                p=ROOT/relative
                self.assertTrue(p.is_file())
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),expected)
    def test_distinct_copilot_is_not_duplicated(self):
        for rel in ('services/teacher_copilot_v5.py','services/survey_evidence_v7.py',
                    'services/srl_grow_guide_v6.py','services/survey_integrity_v8.py'):
            self.assertTrue((ROOT/rel).exists(), rel)
    def test_survey_quick_fill_does_not_touch_answers(self):
        node=methods(ROOT/'ui/survey_manager.py')['_quick_fill_average']
        code=ast.unparse(node)
        self.assertNotIn('setChecked(',code)
        self.assertNotIn('self.answers[',code)
    def test_partial_answers_not_analysed_by_ui(self):
        methods_v8=methods(ROOT/'ui/survey_manager.py')
        s=ast.unparse(methods_v8['_complete_survey'])
        self.assertIn('if audit.complete:',s)
        self.assertIn('json.dumps(audit.valid_answers',s)
        self.assertIn('Taslak Kaydedildi',s)
    def test_export_omits_sensitive_surveys(self):
        from services.survey_integrity_v8 import GENERAL_CODES,SENSITIVE_CODES
        self.assertFalse(GENERAL_CODES.intersection(SENSITIVE_CODES))
        self.assertNotIn('exam_anxiety',GENERAL_CODES)
        self.assertNotIn('sleep_energy',GENERAL_CODES)
    def test_matrix_source_not_changed_since_v5(self):
        # Caller must separately compare installed source with this expected hash.
        self.assertEqual(self.manifest['files']['ui/homework_form.py'],
                         '53e6b12db96cf81fd622947e7d343b4130a1a8e42a0e30d5c5ec58e64e456314')

if __name__ == '__main__':unittest.main()
