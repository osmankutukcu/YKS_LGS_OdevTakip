"""V22 pure layout and regression checks; no GUI dependency required."""
from pathlib import Path
import ast

from services.responsive_v22 import (
    compact_main_shell, compact_homework_workspace,
    minimum_form_columns, screen_bound_minimum,
)

ROOT = Path(__file__).resolve().parents[1]


def test_main_sidebar_switches_on_logical_pixels():
    assert compact_main_shell(1093)
    assert compact_main_shell(1024)
    assert not compact_main_shell(1280)
    assert not compact_main_shell(1920)


def test_homework_360_two_column_compact_mode():
    assert compact_homework_workspace(950)
    assert compact_homework_workspace(1366)
    assert not compact_homework_workspace(1440)
    assert not compact_homework_workspace(1680)


def test_transient_zero_width_does_not_force_compact():
    assert not compact_main_shell(0)
    assert not compact_homework_workspace(0)


def test_compact_minimums_allow_standard_windows_laptop():
    left, right = minimum_form_columns(900)
    assert left + right <= 720
    assert min(left, right) > 0


def test_wide_minimums_prefer_more_table_space():
    assert minimum_form_columns(1920)[0] > minimum_form_columns(1024)[0]


def test_original_homework_write_entrypoints_preserved():
    source = (ROOT / 'ui' / 'homework_form.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    methods = {item.name for c in ast.walk(tree) if isinstance(c, ast.ClassDef)
               for item in c.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert {'_kaydet_kume', '_odev_kontrol', '_open_weekly_plan_dialog'}.issubset(methods)
    assert 'self.btnKaydet.clicked.connect(self._kaydet_kume)' in source
    assert 'self.btnKontrol.clicked.connect(self._odev_kontrol)' in source


def test_existing_bridge_remains_and_adapts():
    source = (ROOT/'ui/homework_workspace_bridge_v21.py').read_text(encoding='utf-8')
    assert 'self.panel.set_open(want)' in source
    assert 'self.form.btnKontrol.click()' in source
    assert 'ResponsiveHomeworkV22' in source


def test_adaptive_shell_triggers_original_buttons():
    source = (ROOT/'ui/responsive_shell_v22.py').read_text(encoding='utf-8')
    assert 'target.click()' in source
    assert 'self.sidebar.setVisible(not compact)' in source


def test_no_new_db_write_in_responsive_modules():
    for path in [ROOT/'ui/responsive_shell_v22.py', ROOT/'ui/responsive_homework_v22.py',
                 ROOT/'ui/responsive_toolbar_v22.py', ROOT/'services/responsive_v22.py']:
        contents = path.read_text(encoding='utf-8')
        assert 'sqlite3' not in contents
        assert 'get_conn(' not in contents


def test_dialog_minimum_never_exceeds_windows_logical_work_area():
    assert screen_bound_minimum((960, 600), (900, 500)) == (876, 476)
    assert screen_bound_minimum((960, 600), (1920, 1040)) == (960, 600)
    assert screen_bound_minimum((960, 600), (640, 400)) == (616, 376)
