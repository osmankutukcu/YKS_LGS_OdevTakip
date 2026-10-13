"""V24.4 – two source read-only draft, no implicit assignments."""
from __future__ import annotations
from dataclasses import replace
from datetime import date
from pathlib import Path
import sqlite3
import pytest

from tests.test_student360_v16 import connection
from services.target_analysis_v24.study_draft_v244 import (
    DraftAction, StudyDraft, read_study_draft, render_selected_draft,
)


def fixture_db():
    con = connection()
    con.executescript('''
        ALTER TABLE ogrenci ADD COLUMN hedef_bolum TEXT;
        ALTER TABLE ogrenci ADD COLUMN hedef_tyt REAL;
        ALTER TABLE ogrenci ADD COLUMN hedef_ayt REAL;
        ALTER TABLE ogrenci ADD COLUMN hedef_lgs REAL;
        UPDATE ogrenci SET hedef_bolum='Mimarlık', hedef_tyt=60, hedef_ayt=40 WHERE id=1;
        UPDATE ogrenci SET hedef_bolum='Ebelik', hedef_tyt=80, hedef_ayt=50 WHERE id=2;
        CREATE TABLE odev_takip (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
                                  ders_adi TEXT,konu_adi TEXT,durum TEXT);
        INSERT INTO odev_takip VALUES
          (1,1,'Matematik','Fonksiyonlar','aktif'),
          (2,2,'Fizik','Işık','aktif');
        CREATE TABLE soru_konu_kanit_v19(
            deneme_id INTEGER,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,
            soru_no INTEGER,sonuc TEXT,kazanim_kodu TEXT);
        INSERT INTO soru_konu_kanit_v19 VALUES
          (1,1,'Matematik','Fonksiyonlar',1,'yanlis',''),
          (1,1,'Matematik','Fonksiyonlar',2,'bos',''),
          (2,1,'Matematik','Trigonometri',3,'yanlis',''),
          (1,2,'Matematik','Fonksiyonlar',1,'yanlis','');
    ''')
    return con


def test_identity_and_specific_sources_and_no_grade_inference():
    with fixture_db() as con:
        d = read_study_draft(con, 1, as_of=date(2026, 10, 12))
    assert d.student_id == 1 and d.student_name == 'Deniz Örnek'
    assert 'Mimarlık' in d.saved_target and 'Ebelik' not in d.saved_target
    assert any(a.title == 'Matematik / Fonksiyonlar' for a in d.actions)
    topic = next(a for a in d.actions if a.title == 'Matematik / Fonksiyonlar')
    assert '1 yanlış, 1 boş' in topic.reason
    assert 'V19' in topic.evidence_source
    assert all('Işık' not in a.title for a in d.actions)
    assert all('Ebelik' not in a.reason for a in d.actions)
    assert all('kesin' not in a.proposed_step.lower() for a in d.actions)


def test_other_student_cannot_see_first_student_topics():
    with fixture_db() as con:
        d = read_study_draft(con, 2, as_of=date(2026, 10, 12))
    assert 'Ebelik' in d.saved_target
    assert all('Fonksiyonlar' not in a.title for a in d.actions)


def test_student_id_rejected_and_query_only():
    with fixture_db() as con:
        for bad in (0, -1, 3, 90, '1', True, None):
            with pytest.raises(ValueError):
                read_study_draft(con, bad)
        con.execute('PRAGMA query_only=ON')
        before = con.total_changes
        d = read_study_draft(con, 1, as_of=date(2026, 10, 12))
        assert d.actions and before == con.total_changes


def test_selected_only_and_no_auto_save():
    with fixture_db() as con:
        d = read_study_draft(con, 1, as_of=date(2026, 10, 12))
        before = con.total_changes
        selected = ('overdue',)
        text = render_selected_draft(d, selected, teacher_note='Planı sınıfta görüşelim')
        assert con.total_changes == before
    assert 'KAYDEDİLMEDİ' in text
    assert 'Ödev Sepetine' in text and 'otomatik aktarılmamıştır' in text
    assert 'Gecikmiş' in text and 'Planı sınıfta görüşelim' in text
    assert '1. ' in text and '2. ' not in text
    assert 'Matematik / Fonksiyonlar' not in text


def test_selection_rejects_missing_duplicate_and_stale_action():
    with fixture_db() as con:
        d = read_study_draft(con, 1)
    for ids in ((), ('fake',), ('overdue', 'overdue')):
        with pytest.raises(ValueError):
            render_selected_draft(d, ids)
    with pytest.raises(ValueError):
        render_selected_draft(d, ('overdue',), teacher_note='x' * 501)


def test_unknown_lesson_net_does_not_generate_topic():
    with fixture_db() as con:
        con.execute('DELETE FROM odev_takip WHERE ogrenci_id=1')
        con.execute('DELETE FROM soru_konu_kanit_v19 WHERE ogrenci_id=1')
        d = read_study_draft(con, 1)
    assert all(not a.action_id.startswith('topic:') for a in d.actions)
    assert any(a.action_id == 'no_topics' for a in d.actions)


def test_unsafe_source_not_used(monkeypatch):
    import services.target_analysis_v24.study_draft_v244 as mod
    original = mod.read_topic_evidence
    def spoiled(*args, **kw):
        rpt = original(*args, **kw)
        return replace(rpt, topics=tuple(replace(x, source_warning='Çakışma') for x in rpt.topics))
    monkeypatch.setattr(mod, 'read_topic_evidence', spoiled)
    with fixture_db() as con:
        d = mod.read_study_draft(con, 1)
    assert all(not a.action_id.startswith('topic:') for a in d.actions)
    assert any('çakışmalı' in w for w in d.warnings)


def test_wrong_student_from_source_fails_closed(monkeypatch):
    import services.target_analysis_v24.study_draft_v244 as mod
    original = mod.read_topic_evidence
    monkeypatch.setattr(mod, 'read_topic_evidence', lambda *a, **k: replace(original(*a, **k), student_id=2))
    with fixture_db() as con:
        with pytest.raises(ValueError):
            mod.read_study_draft(con, 1)


def test_ui_links_are_display_only_and_no_core_method_changed():
    root = Path(__file__).resolve().parents[1]
    old_ui = (root / 'ui/target_coaching_brief_v243.py').read_text(encoding='utf-8')
    draft_ui = (root / 'ui/target_study_draft_v244.py').read_text(encoding='utf-8')
    assert 'open_study_draft_v244' in old_ui
    assert "'?mode=ro'" in draft_ui
    assert 'PRAGMA query_only=ON' in draft_ui
    assert 'setReadOnly(True)' in draft_ui
    assert 'QApplication.clipboard().setText' in draft_ui
    assert 'QCheckBox' in draft_ui and 'self.approve.isChecked()' in draft_ui
    for forbidden in ('INSERT INTO', 'UPDATE ogrenci', 'DELETE FROM odev', 'db.get_conn()'):
        assert forbidden not in draft_ui
