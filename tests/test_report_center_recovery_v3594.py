"""Safe navigation fallback; no Qt or student database required."""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.report_entry_guard_v3594 import (
    LEGACY_REPORT_ROUTES, available_legacy_routes, open_legacy_route,
)


class FakeWindow:
    def __init__(self):
        self.calls = []

    def _ogrenci_detay(self):
        self.calls.append('detail')

    def _rapor_ac(self):
        self.calls.append('class_report')

    def _show_report_guide(self):
        self.calls.append('guide')


def test_fallback_only_shows_existing_legacy_routes():
    win = FakeWindow()
    assert available_legacy_routes(win) == (
        ('Öğrenci Detayı', '_ogrenci_detay'),
        ('Detaylı Raporlar / Sınıf-Kurum', '_rapor_ac'),
        ('Rapor Rehberi', '_show_report_guide'),
    )
    assert win.calls == []


def test_fallback_dispatches_only_selected_original_function():
    win = FakeWindow()
    open_legacy_route(win, '_rapor_ac')
    assert win.calls == ['class_report']


@pytest.mark.parametrize('invalid', ['delete_all', '__class__', '_create_pdf_report', '', None])
def test_fallback_rejects_unavailable_or_unapproved_actions(invalid):
    win = FakeWindow()
    with pytest.raises(ValueError):
        open_legacy_route(win, invalid)
    assert win.calls == []


def test_fallback_cannot_invoke_arbitrary_callable():
    win = FakeWindow()
    win.any_other_action = lambda: win.calls.append('danger')
    with pytest.raises(ValueError):
        open_legacy_route(win, 'any_other_action')
    assert win.calls == []


def test_original_six_routes_are_known():
    assert len(LEGACY_REPORT_ROUTES) == 6
    assert len({key for _, key in LEGACY_REPORT_ROUTES}) == 6


def test_normal_sidebar_remains_simplified_with_no_backup_button():
    source = (ROOT / 'app.py').read_text('utf8')
    tree = ast.parse(source)
    assert tree
    scope = source.split('# 2.1 Rapor Merkezi:', 1)[1].split('# 3. Üst Gri Şeridi', 1)[0]
    assert scope.index('lout.insertWidget(t_idx, btn_rc)') < scope.index('r_btn.hide()')
    assert scope.count('r_btn.hide()') == 1
    assert 'QInputDialog.getItem(' in scope
    assert 'from ui.report_center_v3581 import ReportCenterDialog' in scope
    assert scope.index('def _open_report_center():') < scope.index('from ui.report_center_v3581 import ReportCenterDialog')
    assert 'Yedek Rapor Erişimi' in scope
    assert 'r_btn.show()' in scope  # Only failed menu-installation rollback.


def test_original_report_routes_are_unchanged():
    code = (ROOT / 'ui/report_center_v3581.py').read_text('utf8')
    for route in ('_ogrenci_detay', '_performans_paneli', '_rapor_ac',
                  '_create_pdf_report', '_hedef_analiz_open',
                  '_open_advanced_from_center'):
        assert f'"method": "{route}"' in code
    assert 'Rapor ekranı açılamadı' in code
