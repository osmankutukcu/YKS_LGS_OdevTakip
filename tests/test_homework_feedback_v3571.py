"""V3.5.71 only temporary SQLite and synthetic students; no real user data."""
from __future__ import annotations
import hashlib
import os
import sqlite3
import sys
import types
from urllib.parse import urlsplit

import pytest

try:
    import PyQt6  # noqa: F401
except ModuleNotFoundError:
    # Isolate test-only sqlite provider; production always uses real db.py.
    sys.modules.setdefault('db', types.ModuleType('db'))
from services import homework_feedback_v3571 as f


@pytest.fixture
def demo(tmp_path,monkeypatch):
    filename=tmp_path/'test-v3571.sqlite'
    def get_conn():
        con=sqlite3.connect(filename)
        con.execute('PRAGMA foreign_keys=ON')
        return con
    monkeypatch.setattr(f.db,'get_conn',get_conn,raising=False)
    monkeypatch.setenv(f.FEATURE_FLAG,'1')
    monkeypatch.setenv('YKS_SURVEY_PUBLIC_BASE_URL','https://example.edu')
    con=get_conn()
    con.executescript('''
       CREATE TABLE ogrenci (id INTEGER PRIMARY KEY,aktif INTEGER);
       CREATE TABLE odev_kume (id INTEGER PRIMARY KEY, ogrenci_id INTEGER);
       CREATE TABLE odev (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,
                          ders TEXT,konu_ad TEXT,durum TEXT);
       CREATE TABLE adaptive_quick_note_v28 (id INTEGER PRIMARY KEY, student_id INTEGER,reason_code TEXT);
       INSERT INTO ogrenci VALUES (1,1),(2,1),(3,0);
       INSERT INTO odev_kume VALUES (10,1),(20,2),(30,3);
       INSERT INTO odev VALUES (100,1,10,'Fizik','Yay Dalgaları','tamam'),
                              (101,1,10,'Matematik','Polinomlar','bekliyor'),
                              (200,2,20,'Fizik','Kuvvet','bekliyor'),
                              (300,3,30,'Türkçe','Paragraf','bekliyor'),
                              (400,1,20,'Fizik','Çakışan sahiplik','bekliyor');
       INSERT INTO adaptive_quick_note_v28 VALUES (9,1,'difficulty');
    ''')
    con.commit();con.close()
    return get_conn


def answer(obstacle='concept'):
    return {'completion':4,'understanding':2,'time_fit':3,'obstacle':obstacle}


def public_token(invite):
    return urlsplit(invite['url']).path.rsplit('/',1)[-1]


def test_off_by_default(demo,monkeypatch):
    monkeypatch.delenv(f.FEATURE_FLAG)
    with pytest.raises(ValueError,match='etkin değil'):
        f.create_link(1,100,'student')
    monkeypatch.setenv(f.FEATURE_FLAG,'1')


def test_requires_https_without_credentials(demo,monkeypatch):
    for url in ('http://example.edu','https://user:pw@example.edu','https://example.edu/path',
                'https://example.edu?q=1',''):
        monkeypatch.setenv('YKS_SURVEY_PUBLIC_BASE_URL',url)
        with pytest.raises(ValueError):f.create_link(1,100,'student')


@pytest.mark.parametrize('sid,hid',[(2,100),(1,200),(1,400),(3,300),(4,100)])
def test_strict_homework_ownership(demo,sid,hid):
    with pytest.raises(ValueError):f.create_link(sid,hid,'student')


@pytest.mark.parametrize('sid,hid',[(None,100),(True,100),(1,'100'),(0,100)])
def test_invalid_identity(demo,sid,hid):
    with pytest.raises(ValueError):f.create_link(sid,hid,'student')


def test_student_parent_are_distinct_and_no_names_in_public_page(demo):
    student=f.create_link(1,100,'student')
    parent=f.create_link(1,100,'parent')
    assert student['respondent']=='student' and parent['respondent']=='parent'
    assert f.read_invite(public_token(student))['respondent']=='student'
    assert f.read_invite(public_token(parent))['respondent']=='parent'
    assert f.read_invite(public_token(parent))['lesson']=='Fizik'
    assert 'student_id' not in f.read_invite(public_token(student))
    assert f.list_homeworks(1)[0]['homework_id']==101


def test_one_time_submission_teacher_approval_and_no_legacy_changes(demo):
    student=f.create_link(1,100,'student')
    token=public_token(student)
    con=demo()
    before=con.execute('SELECT * FROM odev ORDER BY id').fetchall()
    diagnosis=con.execute('SELECT * FROM adaptive_quick_note_v28').fetchall()
    stored=con.execute('SELECT token_hash FROM homework_feedback_v3571_invites').fetchone()[0]
    assert stored==hashlib.sha256(token.encode()).hexdigest()
    assert token not in stored
    con.close()
    assert f.submit(token,answer())['state']=='pending_teacher_review'
    assert len(f.list_feedback(1))==1
    assert f.list_feedback(2)==[]
    assert f.approved_summary(1)==[]
    with pytest.raises(ValueError):f.submit(token,answer())
    receipt=f.list_feedback(1)[0]
    with pytest.raises(ValueError):f.decide(2,receipt['reply_id'],'approved')
    approved=f.decide(1,receipt['reply_id'],'approved')
    assert approved['state']=='approved'
    summary=f.approved_summary(1)
    assert len(summary)==1 and summary[0]['source']=='Öğrenci beyanı'
    assert summary[0]['not_mastery_evidence'] is True
    assert summary[0]['not_teacher_diagnosis'] is True
    with pytest.raises(ValueError):f.decide(1,receipt['reply_id'],'approved')
    con=demo()
    assert con.execute('SELECT * FROM odev ORDER BY id').fetchall()==before
    assert con.execute('SELECT * FROM adaptive_quick_note_v28').fetchall()==diagnosis
    con.close()


def test_rejected_not_in_summary(demo):
    issued=f.create_link(1,101,'parent')
    f.submit(public_token(issued),answer('time'))
    receipt=f.list_feedback(1)[0]
    assert f.decide(1,receipt['reply_id'],'rejected')['state']=='rejected'
    assert f.approved_summary(1)==[]


def test_no_self_report_can_override_teacher_note(demo):
    issued=f.create_link(1,100,'student')
    f.submit(public_token(issued),answer('workload'))
    row=f.list_feedback(1)[0]
    f.decide(1,row['reply_id'],'approved')
    con=demo()
    assert con.execute('SELECT reason_code FROM adaptive_quick_note_v28 WHERE id=9').fetchone()[0]=='difficulty'
    con.close()


def test_submission_validation_all_fields(demo):
    issued=f.create_link(1,100,'student');token=public_token(issued)
    for bad in ({'completion':5},
                {'completion':6,'understanding':2,'time_fit':4,'obstacle':'none'},
                {'completion':True,'understanding':2,'time_fit':4,'obstacle':'none'},
                {'completion':2,'understanding':2,'time_fit':4,'obstacle':'irrelevant'}):
        with pytest.raises(ValueError):f.submit(token,bad)
    assert f.submit(token,answer('none'))['state']=='pending_teacher_review'


def test_expiry_revoke_and_no_cross_student_revoke(demo):
    issued=f.create_link(1,100,'student');token=public_token(issued)
    con=demo();ident=con.execute('SELECT id FROM homework_feedback_v3571_invites').fetchone()[0];con.close()
    with pytest.raises(ValueError):f.revoke(2,ident)
    f.revoke(1,ident)
    with pytest.raises(ValueError):f.read_invite(token)
    with pytest.raises(ValueError):f.submit(token,answer())
    issued=f.create_link(1,100,'student');token=public_token(issued)
    con=demo();con.execute("UPDATE homework_feedback_v3571_invites SET expires_at='2020-01-01T00:00:00+00:00' WHERE id=(SELECT MAX(id) FROM homework_feedback_v3571_invites)");con.commit();con.close()
    with pytest.raises(ValueError):f.submit(token,answer())


def test_deleted_moved_homework_rejected_at_submission(demo):
    issued=f.create_link(1,100,'student')
    con=demo();con.execute('UPDATE odev_kume SET ogrenci_id=2 WHERE id=10');con.commit();con.close()
    with pytest.raises(ValueError):f.submit(public_token(issued),answer())


def test_read_uninitialized_db_no_auxiliary_write(demo):
    assert f.approved_summary(1)==[]
    con=demo()
    assert con.execute("SELECT name FROM sqlite_master WHERE name LIKE 'homework_feedback_v3571_%'").fetchall()==[]
    con.close()


def test_invalid_token_format(demo):
    with pytest.raises(ValueError):f.read_invite('invalid')


def test_web_api_key_public_form_and_submission(demo,monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('YKS_WEB_ACCESS_TOKEN','x'*48)
    from web_api.main import app
    client=TestClient(app)
    body={'student_id':1,'homework_id':100,'respondent':'student'}
    assert client.post('/api/v12/homework-feedback/invites',json=body).status_code==401
    headers={'x-access-key':'x'*48}
    result=client.post('/api/v12/homework-feedback/invites',json=body,headers=headers)
    assert result.status_code==200, result.text
    path=urlsplit(result.json()['url']).path
    assert path.startswith('/h/')
    page=client.get(path)
    assert page.status_code==200
    assert 'Yay Dalgaları' in page.text
    assert 'Cache-Control' in page.headers and 'no-store' in page.headers['Cache-Control']
    assert 'X-Frame-Options' in page.headers
    assert client.post(path,data={'completion':'5'}).status_code==422
    response=client.post(path,data={'completion':'3','understanding':'2','time_fit':'4','obstacle':'time','consent':'yes'})
    assert response.status_code==200,response.text
    assert client.post(path,data={'completion':'3','understanding':'2','time_fit':'4','obstacle':'time','consent':'yes'}).status_code==410
    assert client.get('/api/v12/homework-feedback/submissions?student_id=1').status_code==401
    rows=client.get('/api/v12/homework-feedback/submissions?student_id=1',headers=headers).json()
    assert len(rows)==1 and rows[0]['respondent']=='student'
    reply=rows[0]['reply_id']
    # A wrong-student review never works.
    assert client.post(f'/api/v12/homework-feedback/submissions/{reply}/approved?student_id=2',headers=headers).status_code==409
    assert client.post(f'/api/v12/homework-feedback/submissions/{reply}/approved?student_id=1',headers=headers).status_code==200
    assert f.approved_summary(1)[0]['not_teacher_diagnosis'] is True
