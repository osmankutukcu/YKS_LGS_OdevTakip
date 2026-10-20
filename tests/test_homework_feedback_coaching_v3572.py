# -*- coding: utf-8 -*-
"""Read-only student/parent feedback in Student360 + Coach Assistant."""
import sqlite3
import sys
import types
from pathlib import Path

import pytest

try:
    import PyQt6
except ModuleNotFoundError:
    sys.modules.setdefault('db', types.ModuleType('db'))

from services import homework_feedback_v3571 as stage12
from services.homework_feedback_coaching_v3572 import (
    read_coaching_feedback, format_student360_feedback, assistant_feedback_hint)


@pytest.fixture
def store(tmp_path, monkeypatch):
    path=tmp_path/'feedback.sqlite'
    def conn():
        c=sqlite3.connect(path)
        c.execute('PRAGMA foreign_keys=ON')
        return c
    monkeypatch.setattr(stage12.db,'get_conn',conn,raising=False)
    monkeypatch.setenv(stage12.FEATURE_FLAG,'1')
    monkeypatch.setenv('YKS_SURVEY_PUBLIC_BASE_URL','https://pilot.example.org')
    c=conn()
    c.executescript('''
       CREATE TABLE ogrenci (id INTEGER PRIMARY KEY,aktif INTEGER);
       CREATE TABLE odev_kume (id INTEGER PRIMARY KEY,ogrenci_id INTEGER);
       CREATE TABLE odev (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,ders TEXT,konu_ad TEXT,durum TEXT);
       CREATE TABLE adaptive_quick_note_v28 (id INTEGER PRIMARY KEY,student_id INTEGER,reason_code TEXT);
       INSERT INTO ogrenci VALUES (1,1),(2,1),(3,0);
       INSERT INTO odev_kume VALUES (10,1),(20,2),(30,3);
       INSERT INTO odev VALUES (100,1,10,'Fizik','Yay Dalgaları','tamam'),
                               (101,1,10,'Matematik','Polinomlar','bekliyor'),
                               (200,2,20,'Biyoloji','Hücre','bekliyor');
       INSERT INTO adaptive_quick_note_v28 VALUES (8,1,'difficulty');
    ''')
    c.commit();c.close()
    return conn


def _send(store, role='student', homework=100, *, approval='approved', answer=None):
    from urllib.parse import urlsplit
    link=stage12.create_link(1,homework,role)
    token=urlsplit(link['url']).path.rsplit('/',1)[-1]
    stage12.submit(token,answer or {'completion':4,'understanding':2,'time_fit':3,'obstacle':'concept'})
    r=stage12.list_feedback(1)[0]
    if approval:
        stage12.decide(1,r['reply_id'],approval)
    return r['reply_id']


def _read(store,sid=1):
    c=store()
    try:
        c.execute('PRAGMA query_only=ON')
        return read_coaching_feedback(c,sid)
    finally:c.close()


def test_empty_db_no_schema_or_writes(store):
    assert _read(store)['state']=='NO_PILOT_DATA'
    c=store()
    assert not c.execute("SELECT name FROM sqlite_master WHERE name LIKE 'homework_feedback_v3571_%'").fetchall()
    c.close()


def test_review_required_without_auto_promotion(store):
    _send(store,approval=None)
    assert _read(store)['state']=='NO_APPROVED_FEEDBACK'
    stage12.decide(1,stage12.list_feedback(1)[0]['reply_id'],'rejected')
    assert _read(store)['state']=='NO_APPROVED_FEEDBACK'
    assert assistant_feedback_hint(_read(store),1) is None


def test_approved_student_and_parent_distinct(store):
    student_id=_send(store,'student')
    parent_id=_send(store,'parent',answer={'completion':4,'understanding':3,'time_fit':2,'obstacle':'time'})
    card=_read(store)
    assert card['state']=='APPROVED_OBSERVATIONS'
    assert [x['reply_id'] for x in card['items']]==[parent_id,student_id]
    assert [x['source'] for x in card['items']]==['Veli gözlemi','Öğrenci öz değerlendirmesi']
    assert card['is_learning_evidence'] is False
    assert card['is_teacher_diagnosis'] is False
    assert card['changes_homework'] is False
    summary=format_student360_feedback(card,1)
    assert 'Veli gözlemi' in summary and 'Öğrenci öz değerlendirmesi' in summary
    assert 'öğrenme başarısı değildir' in summary
    hint=assistant_feedback_hint(card,1)
    assert hint['source']=='Veli gözlemi' and hint['auto_assignment'] is False
    assert hint['reply_id']==parent_id


def test_cannot_cross_student_or_inactive(store):
    _send(store)
    assert _read(store,2)['items']==[]
    assert _read(store,3)['state']=='STUDENT_UNVERIFIED'
    assert assistant_feedback_hint(_read(store),2) is None
    with pytest.raises(ValueError):_read(store,True)
    with pytest.raises(ValueError):_read(store,'1')
    assert format_student360_feedback(_read(store),2)==''


def test_stale_owner_and_changed_subject_blocked(store):
    _send(store)
    c=store();c.execute('UPDATE odev SET konu_ad=? WHERE id=100',('Farklı Konu',));c.commit();c.close()
    assert _read(store)['state']=='NO_APPROVED_FEEDBACK'
    c=store();c.execute('UPDATE odev SET konu_ad=?,ogrenci_id=? WHERE id=100',('Yay Dalgaları',2));c.commit();c.close()
    assert _read(store)['state']=='NO_APPROVED_FEEDBACK'


def test_tampered_answer_invalid_never_promoted(store):
    rid=_send(store)
    c=store();c.execute('UPDATE homework_feedback_v3571_replies SET answers_json=? WHERE id=?',
                        ('{"completion": 99, "understanding": 2, "time_fit": 3, "obstacle": "concept"}',rid));c.commit();c.close()
    assert _read(store)['state']=='NO_APPROVED_FEEDBACK'


def test_strict_output_guards(store):
    _send(store)
    card=_read(store)
    assert format_student360_feedback({**card,'student_id':2},1)==''
    assert assistant_feedback_hint({**card,'student_id':2},1) is None
    assert assistant_feedback_hint({**card,'is_learning_evidence':True},1) is None
    assert format_student360_feedback({**card,'changes_homework':True},1)==''
    with pytest.raises(ValueError):
        c=store()
        try: read_coaching_feedback(c,1,limit=99)
        finally:c.close()


def test_legacy_tables_unchanged_and_read_only(store):
    _send(store)
    c=store()
    before=c.execute('SELECT * FROM odev').fetchall()
    quick=c.execute('SELECT * FROM adaptive_quick_note_v28').fetchall()
    c.execute('PRAGMA query_only=ON')
    card=read_coaching_feedback(c,1)
    assert card['state']=='APPROVED_OBSERVATIONS'
    c.close()
    c=store()
    assert c.execute('SELECT * FROM odev').fetchall()==before
    assert c.execute('SELECT * FROM adaptive_quick_note_v28').fetchall()==quick
    c.close()


def test_sidecar_uses_optional_worker_no_core_form_edits():
    source=Path(__file__).resolve().parents[1]
    sidecar=(source/'ui/student360_journey_sidecar_v3566.py').read_text(encoding='utf-8')
    assistant=(source/'ui/research_coaching_bridge_v3563.py').read_text(encoding='utf-8')
    assert 'read_coaching_feedback(con, self.sid)' in sidecar
    assert 'format_student360_feedback' in sidecar
    assert 'read_coaching_feedback(con,self.sid)' in assistant
    assert '_show_feedback_v3572' in assistant
    assert 'self.assistant._present_insight(' in assistant
    assert "os.getenv('YKS_HOMEWORK_FEEDBACK_V12_ENABLED')" in sidecar
