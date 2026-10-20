# -*- coding: utf-8 -*-
"""V3557 dashboard freeze acceptance: General Overview visual code is immutable."""
import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DashboardFreezeContract(unittest.TestCase):
    def test_main_dashboard_class_is_identical_to_v3556(self):
        text = (ROOT / 'ui/info_board_widget.py').read_text(encoding='utf-8')
        suffix = text[text.index('class InfoBoardWidget(QFrame):'):].encode()
        self.assertEqual(hashlib.sha256(suffix).hexdigest(),
                         '720a589feb73fef43cd9ba08250d44db8b7994777cc0f14a7bd06835ccbf8af4')

    def test_preview_is_in_modal_not_main_dashboard(self):
        text = (ROOT / 'ui/info_board_widget.py').read_text(encoding='utf-8')
        before, after = text.split('class InfoBoardWidget(QFrame):', 1)
        self.assertIn('Haftalık Planı Önizle', before)
        self.assertNotIn('Haftalık Planı Önizle', after)
        self.assertIn('Simülasyonu Kapat (Kaydedilmez)', before)

    def test_no_db_write_in_v3557_service(self):
        text = (ROOT / 'services/weekly_exam_plan_v3557.py').read_text(encoding='utf-8')
        import ast
        ast.parse(text)
        self.assertIn('_connection(db_path)', text)
        self.assertNotIn('sqlite3.connect(', text)


if __name__ == '__main__':
    unittest.main()
