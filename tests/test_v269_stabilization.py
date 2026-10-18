# -*- coding: utf-8 -*-
"""V26.9: executable safety checks; no Qt, DB writes, or network needed."""
from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil

import pytest

from tools.v35_reviewed_source_contract import (
    verify_legacy_handlers, APPROVED_WEEKLY_HOMEWORK_SHA256,
    USER_UPLOADED_APPROVED_TIK_AST_SHA256, APPROVED_TIK_AST_HASHES,
)
from services.coach_assistant_v1.event_router_v267 import CoachChange, CoachChangeRouter
from services.coach_assistant_v1.module_events_v268 import publish_saved_coaching_change

ROOT = Path(__file__).resolve().parents[1]
CORE = ('ui/homework_form.py', 'ui/odev_kontrol.py')


def _ast_fingerprint(source: bytes) -> str:
    tree = ast.parse(source.decode('utf-8'))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'OdevTakipFormu']
    assert len(classes) == 1
    methods = [n for n in classes[0].body if isinstance(n, ast.FunctionDef)
               and n.name == '_tik_degisti']
    assert len(methods) == 1
    return sha256(ast.dump(methods[0], include_attributes=False).encode()).hexdigest()


def _mini_reference(tmp):
    for rel in CORE:
        dest = Path(tmp) / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dest)
    return Path(tmp)


def test_original_user_reviewed_full_file_and_protected_handler_are_both_verified():
    source = (ROOT / CORE[0]).read_bytes()
    assert sha256(source).hexdigest() == APPROVED_WEEKLY_HOMEWORK_SHA256
    assert _ast_fingerprint(source) in APPROVED_TIK_AST_HASHES
    verify_legacy_handlers(ROOT)


def test_reviewed_exception_rejected_if_file_changes_even_if_handler_ast_unchanged():
    with TemporaryDirectory() as tmp:
        folder = _mini_reference(tmp)
        original = (folder / CORE[0]).read_text('utf-8')
        (folder / CORE[0]).write_text(original + '\n# unauthorized extra byte\n', 'utf-8')
        assert _ast_fingerprint((folder / CORE[0]).read_bytes()) in APPROVED_TIK_AST_HASHES
        with pytest.raises(ValueError, match='_tik_degisti'):
            verify_legacy_handlers(folder)


def test_reviewed_exception_rejected_if_method_changes():
    with TemporaryDirectory() as tmp:
        folder = _mini_reference(tmp)
        path = folder / CORE[0]
        text = path.read_text('utf-8')
        # Modify the reviewed checkbox handler only, preserving valid Python.
        start = text.index('    def _tik_degisti(')
        end = text.find('\n    def ', start + 5)
        if end == -1:
            end = len(text)
        body = text[start:end]
        assert 'self._toplam_sure_guncelle()' in body
        changed = body.replace('self._toplam_sure_guncelle()', 'self._toplam_sure_guncelle_v269_tampered()', 1)
        path.write_text(text[:start] + changed + text[end:], 'utf-8')
        with pytest.raises(ValueError, match='_tik_degisti'):
            verify_legacy_handlers(folder)


def test_protected_class_shadowing_rejected():
    with TemporaryDirectory() as tmp:
        folder = _mini_reference(tmp)
        p = folder / CORE[0]
        with p.open('a', encoding='utf-8') as f:
            f.write('\nclass OdevTakipFormu: pass\n')
        with pytest.raises(ValueError, match='sınıfı sayısı'):
            verify_legacy_handlers(folder)


@pytest.mark.parametrize('exc', [OSError('offline'), AttributeError('bus not ready'), RuntimeError('router failed')])
def test_best_effort_hint_never_breaks_committed_coach_save(exc):
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router', side_effect=exc):
        assert publish_saved_coaching_change('coaching_plan', 4) is False


@pytest.mark.parametrize('kind', [None, [], {}, 7, 'unknown'])
def test_invalid_event_kind_fails_closed(kind):
    with patch('services.coach_assistant_v1.module_events_v268.get_coach_router') as router:
        assert publish_saved_coaching_change(kind, 4) is False
        router.assert_not_called()


def test_heavy_notification_burst_is_bounded_and_never_leaks_unrelated_student():
    router = CoachChangeRouter(capacity=256)
    cursor = router.cursor
    for i in range(15000):
        router.publish(CoachChange('independent_measurement', student_id=100 + i % 5,
                                   lesson='LGS Türkçe', topic='Fiilimsiler'))
    assert len(router._items) == 256
    # Slow readers safely re-check because history was truncated.
    assert router.check(cursor, student_id=999, lesson='LGS Türkçe').overflow
    next_cursor = router.cursor
    router.publish(CoachChange('coaching_plan', student_id=100, lesson='LGS Türkçe'))
    assert router.check(next_cursor, student_id=100, lesson='LGS Türkçe').changed
    assert not router.check(next_cursor, student_id=101, lesson='LGS Türkçe').changed
    assert not router.check(next_cursor, student_id=100, lesson='TYT Fizik').changed


def test_active_coach_ui_layout_is_unchanged_from_v268_baseline():
    # UI is protected by baseline parity in package audit; assert the documented contract too.
    src = (ROOT / 'ui/coach_dialogue_v121.py').read_text('utf-8')
    assert 'self.setFixedWidth(430)' in src and 'self.setFixedHeight(405)' in src
