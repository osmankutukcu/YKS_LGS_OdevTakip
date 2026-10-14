"""Static integration guards; works even when PyQt6 is absent on CI."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class OneClickUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / 'ui' / 'weekly_plan.py').read_text(encoding='utf-8')
        root = ast.parse(cls.src)
        cls.klass = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name=='HaftalikPlanDialog')
        cls.methods = {n.name:n for n in cls.klass.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def test_opt_in_button_and_legacy_actions_present(self):
        for name in ('_on_one_click_plan_v35', '_on_btn_auto_clicked', '_accept_with_result', '_collect_plan',
                     '_undo_auto_v35', '_toggle_cell', '_distribute_uniform'):
            self.assertIn(name,self.methods)
        self.assertIn('self.btnOneClick.clicked.connect(self._on_one_click_plan_v35)',self.src)
        self.assertIn('self.btnAuto.clicked.connect(self._on_btn_auto_clicked)',self.src)
        self.assertIn('self.btnUygula.clicked.connect(self._accept_with_result)',self.src)

    def test_selection_change_does_not_trigger_distribution(self):
        method = self.methods['_on_strategy_combo_changed']
        self.assertNotIn('self._auto_distribute(',ast.unparse(method))
        self.assertNotIn('self._distribute_uniform(',ast.unparse(method))

    def test_density_only_refreshes_not_redistributes(self):
        method = self.methods['_density_changed']
        self.assertNotIn('self._auto_distribute(',ast.unparse(method))

    def test_manual_change_is_tracked(self):
        self.assertIn('self._manual_fixed_rows_v35.add(row)',ast.unparse(self.methods['_toggle_cell']))

    def test_apply_requires_confirmation_for_unplaced(self):
        fn=ast.unparse(self.methods['_accept_with_result'])
        self.assertIn("'one_click'", fn)
        self.assertIn('QMessageBox.StandardButton.No',fn)

if __name__=='__main__':unittest.main()
