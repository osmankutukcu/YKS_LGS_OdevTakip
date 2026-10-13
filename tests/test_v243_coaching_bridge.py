"""V24.3: only per-student, read-only, traceable coaching summary."""
from __future__ import annotations
import ast
from datetime import date
from pathlib import Path
import sqlite3

import pytest

from services.target_analysis_v24.coaching_bridge_v243 import (
    CoachingBrief, read_coaching_brief, render_coaching_brief,
)
from tests.test_student360_v16 import connection


@pytest.fixture
def con():
    db = connection()
    db.execute('ALTER TABLE ogrenci ADD COLUMN hedef_bolum TEXT')
    db.execute('ALTER TABLE ogrenci ADD COLUMN hedef_tyt REAL')
    db.execute('ALTER TABLE ogrenci ADD COLUMN hedef_ayt REAL')
    db.execute('ALTER TABLE ogrenci ADD COLUMN hedef_lgs REAL')
    db.execute("UPDATE ogrenci SET hedef_bolum='Matematik Öğretmenliği',hedef_tyt=65,hedef_ayt=42 WHERE id=1")
    db.execute("UPDATE ogrenci SET hedef_bolum='Tıp Fakültesi',hedef_tyt=95,hedef_ayt=70 WHERE id=2")
    db.commit()
    try:
        yield db
    finally:
        db.close()


def test_student_specific_target_and_homework(con):
    deniz = read_coaching_brief(con, 1, as_of=date(2026, 10, 12))
    ece = read_coaching_brief(con, 2, as_of=date(2026, 10, 12))
    assert deniz.student_id == 1 and ece.student_id == 2
    assert 'Matematik Öğretmenliği' in deniz.saved_target
    assert 'Tıp Fakültesi' not in deniz.saved_target
    assert 'Tıp Fakültesi' in ece.saved_target
    assert ece.exam_evidence == 'Yok'
    assert deniz.overdue == 1


def test_missing_and_inactive_student_fail_closed(con):
    for sid in (0, -1, '1', True, 3, 900):
        with pytest.raises(ValueError):
            read_coaching_brief(con, sid, as_of=date(2026, 10, 12))


def test_only_read_under_query_only(con):
    before = con.total_changes
    con.execute('PRAGMA query_only=ON')
    brief = read_coaching_brief(con, 1, as_of=date(2026, 10, 12))
    assert 'Matematik Öğretmenliği' in brief.saved_target
    assert con.total_changes == before


def test_unsaved_draft_is_not_confused_with_saved_target(con):
    brief = read_coaching_brief(con, 1, as_of=date(2026, 10, 12))
    txt = render_coaching_brief(brief, draft_target_name='Özel Fizik Hedefi')
    assert 'TASLAK (KAYDEDİLMEDİ)' in txt
    assert 'Özel Fizik Hedefi' in txt
    assert 'Matematik Öğretmenliği' in txt
    assert 'Özel Fizik Hedefi' not in brief.saved_target


def test_no_rank_prediction_and_no_automatic_assignments(con):
    brief = read_coaching_brief(con, 1, as_of=date(2026, 10, 12))
    txt = render_coaching_brief(brief)
    assert 'yerleşme olasılığı hesaplanmaz' in txt
    assert 'kendiliğinden' not in txt
    assert 'hiçbir öğrenci kaydı' in txt.lower()
    assert brief.recommendations


def test_source_warnings_remain_visible(con):
    brief = read_coaching_brief(con, 1, as_of=date(2026, 10, 12))
    assert brief.warnings
    txt = render_coaching_brief(brief)
    assert 'VERİ KALİTESİ NOTLARI' in txt
    for warning in brief.warnings:
        assert warning in txt


def test_missing_target_columns_give_explicit_uncertainty():
    with connection() as db:
        brief = read_coaching_brief(db, 1, as_of=date(2026, 10, 12))
    assert 'hedef alanları' in brief.saved_target


def test_no_ui_changes_to_core_save_or_exam_methods():
    root = Path(__file__).resolve().parents[1]
    target = (root / 'ui' / 'target_analysis_dialog.py').read_text(encoding='utf-8')
    tree = ast.parse(target)
    method_names = {x.name for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)}
    assert '_open_coaching_brief_v243' in method_names
    method = next(x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef) and x.name == '_open_coaching_brief_v243')
    code = ast.get_source_segment(target, method)
    assert 'selected_id != self.student_id' in code
    assert '_analysis_signature()' in code
    assert 'UPDATE ogrenci' not in code
    ui = (root / 'ui' / 'target_coaching_brief_v243.py').read_text(encoding='utf-8')
    assert "'?mode=ro'" in ui
    assert 'PRAGMA query_only=ON' in ui
    assert 'setReadOnly(True)' in ui
    assert 'QApplication.clipboard()' in ui
