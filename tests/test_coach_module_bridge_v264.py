# -*- coding: utf-8 -*-
"""V26.4 — modular cross-screen awareness: no direct UI or homework mutations."""
import ast
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from services.coach_assistant_v1.dialogue import CoachAnswer
from services.coach_assistant_v1.module_bridge_v264 import (
    read_module_review, enrich_answer,
)


def db():
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT)')
    con.execute('INSERT INTO ogrenci VALUES (7,"Test")')
    con.commit()
    con.execute('PRAGMA query_only=ON')
    return con


def stub(monkeypatch, *, adaptive=None, wizard=None):
    from services.adaptive_coaching_v26 import decision
    from services import coach_evidence_v5
    calls = {'adaptive': 0, 'wizard': 0}
    if adaptive is None:
        adaptive = {'student_id':7, 'context':{'coaching_plan':'Bu haftaya ait 1 plan var.'},
                    'actions':[{'lesson':'TYT_FIZIK','topic':'Enerji','next_step':'Fizik tekrar yap','source':'V25'},
                               {'lesson':'LGS_TURKCE','topic':'Fiilimsiler','next_step':'Kısa tanılama yap','source':'V25'}]}
    if wizard is None:
        wizard = {'student':{'id':7}, 'stats':{'completed':49,'pending':13,'overdue':3}}
    def adapt(*args, **kwargs):
        calls['adaptive'] += 1
        if isinstance(adaptive, Exception): raise adaptive
        return adaptive
    def wiz(*args, **kwargs):
        calls['wizard'] += 1
        if isinstance(wizard, Exception): raise wizard
        return wizard
    monkeypatch.setattr(decision, 'student_decisions', adapt)
    monkeypatch.setattr(coach_evidence_v5, 'build_coach_brief', wiz)
    return calls


def ctx():
    return SimpleNamespace(student_id=7, completed_homework=52, open_homework=22)


def answer():
    return CoachAnswer('Öncelikli ihtiyaç: ölçüm', 'Fiilimsiler için kısa yoklama.', ('Öğrenme ölçümü',), 'btnOgrenme')


def test_integration_not_invoked_on_ordinary_topic_question(monkeypatch):
    calls = stub(monkeypatch)
    con=db()
    assert enrich_answer(con,ctx(),answer(),'Hangi konu?',lesson_scope='LGS Türkçe') == answer()
    assert calls == {'adaptive': 0,'wizard':0}
    con.close()


def test_lgs_scope_cannot_leak_tyt_intervention(monkeypatch):
    calls = stub(monkeypatch)
    con=db()
    out=enrich_answer(con,ctx(),answer(),'Önceliğim ne?', lesson_scope='LGS Türkçe')
    assert calls == {'adaptive':1,'wizard':0}
    assert 'Kısa tanılama' in str(out.evidence)
    assert 'Fizik tekrar' not in str(out.evidence)
    assert con.row_factory is None
    con.close()


def test_full_module_review_reuses_wizard_and_flags_disagreement(monkeypatch):
    calls=stub(monkeypatch)
    con=db()
    out=enrich_answer(con,ctx(),answer(),'Öğrenci 360 ve adaptif koç, sihirbaz birlikte ne diyor?')
    assert calls == {'adaptive':1,'wizard':1}
    assert '52' in str(out.evidence) and '49' in str(out.evidence)
    assert 'birleştirilmedi' in str(out.evidence)
    assert 'Tek bir' not in out.message  # Does not produce a fabricated score.
    assert 'Öğrenme' in out.message and 'Akıllı Sihirbaz' in out.message
    con.close()


def test_read_only_sqlite_remains_read_only(monkeypatch):
    stub(monkeypatch)
    con=db()
    before=con.execute('SELECT id,ad FROM ogrenci').fetchall()
    report=read_module_review(con,ctx(),lesson_scope='LGS Türkçe',include_wizard=True)
    assert report.adaptive_status=='available'
    assert report.wizard_status=='available'
    assert report.plan_status.startswith('Bu hafta')
    assert before==con.execute('SELECT id,ad FROM ogrenci').fetchall()
    with pytest.raises(sqlite3.DatabaseError):
        con.execute('UPDATE ogrenci SET ad="changed"')
    con.close()


def test_missing_modules_are_not_reported_as_zero(monkeypatch):
    stub(monkeypatch, adaptive=sqlite3.OperationalError('missing table'), wizard=ValueError('broken'))
    con=db()
    report=read_module_review(con,ctx(),include_wizard=True)
    assert report.adaptive_status=='unavailable'
    assert report.wizard_status=='unavailable'
    assert report.wizard_completed is None
    assert len(report.missing)==2
    con.close()


def test_different_student_in_upstream_source_is_rejected(monkeypatch):
    bad = {'student_id':3, 'actions':[{'lesson':'LGS_TURKCE','next_step':'Yanlış öğrenci'}]}
    stub(monkeypatch, adaptive=bad, wizard={'student':{'id':3},'stats':{'completed':20}})
    con=db()
    review=read_module_review(con,ctx(),include_wizard=True)
    assert review.adaptive_status=='unavailable' and review.wizard_status=='unavailable'
    assert not review.adaptive_step and review.wizard_completed is None
    con.close()


def test_scope_mismatch_question_does_not_run_any_module(monkeypatch):
    calls=stub(monkeypatch)
    con=db()
    ans=CoachAnswer('Ders kapsamı uyuşmuyor','Ders değiştirin',('Ders','LGS Türkçe'),None)
    assert enrich_answer(con,ctx(),ans,'Önceliğim ne?',lesson_scope='LGS Türkçe') is ans
    assert calls == {'adaptive':0,'wizard':0}
    con.close()


def test_invalid_identity_never_uses_default_student(monkeypatch):
    stub(monkeypatch)
    con=db()
    with pytest.raises(ValueError):
        read_module_review(con,SimpleNamespace(student_id=8))
    assert con.row_factory is None
    con.close()


def test_no_remote_access_or_changes_to_teacher_main_form():
    root=Path(__file__).resolve().parents[1]
    bridge=(root/'services/coach_assistant_v1/module_bridge_v264.py').read_text('utf8')
    ui=(root/'ui/coach_dialogue_v121.py').read_text('utf8')
    ast.parse(bridge); ast.parse(ui)
    assert '_module_enrich(con, context, result, self.question,' in ui
    assert 'setFixedWidth(430)' in ui
    assert 'self.setFixedWidth(408)' in (root/'ui/smart_coach_secretary_toast.py').read_text('utf8')
    for banned in ('UPDATE odev', 'INSERT INTO odev', 'DELETE FROM odev', 'urllib.request', 'requests.get', 'CREATE TABLE'):
        assert banned not in bridge
