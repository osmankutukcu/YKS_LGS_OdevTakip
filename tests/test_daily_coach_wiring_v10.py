"""Source-level guardrails that do not require macOS/Windows Qt installation."""
import ast
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

class WiringTests(unittest.TestCase):
    def test_main_window_routes_to_existing_form(self):
        src=(ROOT/'main_window.py').read_text()
        ast.parse(src)
        self.assertIn('def open_homework_for_student(',src)
        self.assertIn('self._show_dialog(OdevTakipFormu, student_id=int(student_id))',src)
        self.assertIn('inner._pending_student_id = int(student_id)',src)
    def test_summary_uses_safe_read_only_engine(self):
        src=(ROOT/'ui/smart_assistant_dialog.py').read_text()
        ast.parse(src)
        self.assertIn('self.all_suggestions = make_suggestions(facts)',src)
        self.assertIn('coach_tracking_snapshot_v10',src)
        self.assertIn('self._watch_conn.execute("PRAGMA data_version")',src)
    def test_whatsapp_requires_confirmed_dialog(self):
        src=(ROOT/'ui/smart_assistant_dialog.py').read_text()
        self.assertIn("'sent' if outcome == QDialog.DialogCode.Accepted else 'needs_review'",src)
        self.assertIn('def retry_selected(',src)

if __name__=='__main__':unittest.main()
