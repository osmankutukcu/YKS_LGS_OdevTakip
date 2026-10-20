"""Syntax and name alignment checks work without a GUI toolkit."""
import ast
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.exam_planning_v3555 import TRACK_TABLES


class UiContractTests(unittest.TestCase):
    def test_legacy_track_order_matches_canonical(self):
        tree = ast.parse((ROOT / 'ui' / 'info_board_widget.py').read_text(encoding='utf8'))
        node = next(n for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == '_SIMULATION_CONFIGS' for t in n.targets))
        config = ast.literal_eval(node.value)
        for exam in ('YKS', 'MSÜ', 'LGS'):
            self.assertEqual(len(config[exam]['tracks']), len(TRACK_TABLES[exam]))
        ui_source = (ROOT / 'ui' / 'info_board_widget.py').read_text(encoding='utf8')
        self.assertIn('canonical_track = list(TRACK_TABLES[self.exam_key])[position]', ui_source)

    def test_old_dashboard_no_core_module_import(self):
        tree = ast.parse((ROOT / 'ui' / 'info_board_widget.py').read_text(encoding='utf8'))
        imports = [getattr(n, 'module', '') or '' for n in tree.body if isinstance(n, ast.ImportFrom)]
        self.assertIn('services.student_exam_bridge_v3556', imports)
        self.assertFalse(any(x in imports for x in ('ui.homework_form', 'ui.homework_control_form')))


if __name__ == '__main__':
    unittest.main()
