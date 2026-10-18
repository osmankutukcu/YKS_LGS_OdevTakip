# -*- coding: utf-8 -*-
"""V26.8: safe post-commit hint producer and non-invasive UI integration contract."""
import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from services.coach_assistant_v1.event_router_v267 import CoachChangeRouter
from services.coach_assistant_v1.module_events_v268 import publish_saved_coaching_change

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['independent_measurement','coaching_plan','student_profile','exam'])
def test_valid_event_only_contains_scoped_metadata(kind):
    router = CoachChangeRouter()
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router', return_value=router):
        assert publish_saved_coaching_change(kind, 7, lesson='LGS Türkçe', topic='Fiilimsiler')
    assert router.check(0, student_id=7, lesson='LGS Türkçe', topic='Fiilimsiler').changed
    assert not router.check(0, student_id=8, lesson='LGS Türkçe').changed
    assert not router.check(0, student_id=7, lesson='TYT Fizik').changed


@pytest.mark.parametrize('student_id', [None, 0, -2, True, '7', 7.0])
def test_reject_invalid_student_ids(student_id):
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router') as fake:
        assert not publish_saved_coaching_change('coaching_plan', student_id)
        fake.assert_not_called()


def test_reject_unknown_kind():
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router') as fake:
        assert not publish_saved_coaching_change('homework', 7)
        fake.assert_not_called()


def test_topic_without_subject_does_not_claim_false_scope():
    router = CoachChangeRouter()
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router', return_value=router):
        assert publish_saved_coaching_change('coaching_plan', 7, topic='Some Topic')
    assert router.check(0, student_id=7, lesson='LGS Türkçe').changed


def test_bus_failure_cannot_fail_committed_save():
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router', side_effect=RuntimeError):
        assert not publish_saved_coaching_change('coaching_plan', 7)


def test_no_personal_notes_in_payload():
    router = CoachChangeRouter()
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router', return_value=router):
        publish_saved_coaching_change('coaching_plan', 7)
    event = router._items[-1][1]
    assert event.student_id == 7 and event.revision == ''
    assert not hasattr(event, 'student_name')
    assert not hasattr(event, 'note')


def _method(name, meth):
    module = ast.parse((ROOT / name).read_text())
    classes = [n for n in module.body if isinstance(n, ast.ClassDef)]
    for cls in classes:
        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == meth:
                return node
    raise AssertionError(f'{name}:{meth} absent')


@pytest.mark.parametrize('method,kind', [
    ('_save_observation','independent_measurement'),
    ('_save_blocker','coaching_plan'),
    ('_save_preferences','student_profile'),
    ('_save_plan','coaching_plan'),
])
def test_publish_after_save_connection_scope(method, kind):
    node = _method('ui/adaptive_coaching_dialog_v25.py', method)
    body = ast.get_source_segment((ROOT / 'ui/adaptive_coaching_dialog_v25.py').read_text(), node)
    assert f"publish_saved_coaching_change('{kind}'" in body
    # Specifically ensure emission follows the end of the context-managing with:
    trys = [x for x in node.body if isinstance(x, ast.Try)]
    assert trys
    block = trys[0].body
    withs = [x for x in block if isinstance(x, ast.With)]
    pubs = [x for x in block if isinstance(x, ast.Expr) and isinstance(x.value, ast.Call)
            and isinstance(x.value.func, ast.Name) and x.value.func.id == 'publish_saved_coaching_change']
    assert withs and len(pubs) == 1
    assert pubs[0].lineno > withs[-1].end_lineno


def test_workspace_uses_existing_poll_and_never_changes_main_form():
    ws = (ROOT / 'ui/student_workspace_panel_v21.py').read_text()
    assert 'self._live_timer.setInterval(15000)' in ws
    assert 'self._coach_router.check(self._coach_cursor, student_id=self._student_id)' in ws
    assert 'self.mark_dirty()' in ws


def test_wizard_never_overwrites_teacher_task_selection_on_event():
    method = _method('ui/smart_wizard_dialog.py', '_check_coach_freshness')
    src = ast.get_source_segment((ROOT/'ui/smart_wizard_dialog.py').read_text(), method)
    assert 'lblProfileBadge.setText' in src
    for forbidden in ('_run_analysis(', '_fill_table(', '_transfer(', 'self.suggested_tasks ='):
        assert forbidden not in src


def test_legacy_core_file_names_not_rewritten_by_patch():
    for path in ['ui/homework_form.py', 'ui/odev_kontrol.py', 'db.py']:
        assert (ROOT / path).is_file()
