"""V23.7/V23.8 pure behaviour and read-only contract tests (no GUI required)."""
import unittest
import ast
from pathlib import Path
from types import SimpleNamespace
from services.curriculum_v237 import teacher_guidance
from services.curriculum_v238 import coverage_notice

ROOT=Path(__file__).resolve().parents[1]

def fake(*, problems=(), count=0):
    return SimpleNamespace(needs_attention=bool(problems),problems=tuple(problems),
       scoped_tasks=SimpleNamespace(open_count=count))

class GuidanceTests(unittest.TestCase):
    def test_healthy_does_not_require_click(self):
        g=teacher_guidance(fake())
        self.assertFalse(g.needs_review)
        self.assertIn('işlem yapmanız gerekmiyor',g.message)
        self.assertIsNone(coverage_notice(fake(),'matematik'))
    def test_special_topic_is_not_false_alarm(self):
        g=teacher_guidance(fake(count=3))
        self.assertFalse(g.needs_review)
        self.assertIn('3 açık özel ödev',g.message)
        self.assertIsNone(coverage_notice(fake(count=3),'matematik'))
    def test_identity_problem_guides_without_auto_repair(self):
        data=fake(problems=('Kimlik uyuşmazlığı',))
        g=teacher_guidance(data)
        self.assertTrue(g.needs_review)
        self.assertIn('Konu',g.message)
        notice=coverage_notice(data,'tyt_matematik')
        self.assertEqual(notice.warning_count,1)
        self.assertIn('tyt_matematik',notice.heading)
    def test_an_empty_lesson_never_generates_automatic_warning(self):
        self.assertIsNone(coverage_notice(fake(problems=('x',)),''))
    def test_no_unverified_mufredat_claim(self):
        guide=teacher_guidance(fake())
        self.assertNotIn('MEB ile doğrulandı',guide.message)
    def test_source_keeps_old_checkbox_handler(self):
        src=(ROOT/'ui/homework_form.py').read_text()
        self.assertIn('self._tik_degisti(it, table, ders)',src)
    def test_core_schema_unchanged_by_new_service(self):
        for file in ('services/curriculum_v237/guidance.py','services/curriculum_v238/notice.py','ui/curriculum_guidance_v238.py'):
            data=(ROOT/file).read_text()
            ast.parse(data)
            self.assertNotIn('UPDATE odev',data)
            self.assertNotIn('DELETE FROM odev',data)
    def test_no_automatic_fix_or_publish(self):
        source=(ROOT/'ui/curriculum_guidance_v238.py').read_text()
        self.assertIn('if not overview.needs_attention',source) if 'if not overview.needs_attention' in source else self.assertIn('coverage_notice(overview, lesson)',source)
        self.assertIn("str(sid) != str(loaded)",source)
        self.assertIn('assistant.is_enabled()',source)
        self.assertIn("source='coverage'",source)
    def test_existing_dialog_still_opens_scoped_homework(self):
        src=(ROOT/'ui/curriculum_matrix_preview_v232.py').read_text()
        self.assertIn('self._open_scoped_homework',src)
        self.assertIn('ScopedHomeworkDialog(',src)
        self.assertIn('self.setModal(True)',src)
    def test_existing_editor_not_new_writer(self):
        src=(ROOT/'ui/curriculum_matrix_preview_v232.py').read_text()
        self.assertIn('from ui.topic_editor import DersKonuEditor',src)
        self.assertIn("editor.cmbKapsam.setCurrentText('Genel')",src)
        self.assertIn('self.review_button.setVisible',src)
    def test_existing_assistant_alert_budget(self):
        src=(ROOT/'ui/smart_coach_secretary_toast.py').read_text()
        self.assertIn('curriculum_coverage',src)
        self.assertIn('button.click',src)
        self.assertIn('self._proactive.decide(',src)
    def test_no_background_alert_without_loaded_student(self):
        src=(ROOT/'ui/curriculum_guidance_v238.py').read_text()
        self.assertIn("str(sid) != str(loaded)",src)
        self.assertIn("if not context:",src)
        self.assertIn('if not self.form.isVisible():',src)

if __name__=='__main__': unittest.main()
