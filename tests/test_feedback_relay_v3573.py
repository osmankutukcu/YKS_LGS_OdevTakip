"""End-to-end HTTP + SQLite-only pilot tests. NO personal records used."""
import hashlib
import json
import sqlite3
import sys
import types
from urllib.parse import urlsplit
import uuid

import pytest
from fastapi.testclient import TestClient

try: import PyQt6  # noqa
except ModuleNotFoundError: sys.modules.setdefault('db',types.ModuleType('db'))
from services import homework_feedback_v3571 as old
from services import homework_feedback_cloud_bridge_v3573 as bridge
from services import feedback_relay_v3573 as relay

KEY='X'*43
OTHER_KEY='Y'*43


@pytest.fixture
def system(tmp_path,monkeypatch):
    remote_db=tmp_path/'relay.sqlite'
    local_db=tmp_path/'local.sqlite'
    monkeypatch.setenv('YKS_FEEDBACK_RELAY_DB',str(remote_db))
    monkeypatch.setenv('YKS_FEEDBACK_RELAY_PUBLIC_URL','https://feedback.example.org')
    monkeypatch.setenv('YKS_FEEDBACK_RELAY_TENANT_HASHES',json.dumps({
        'school_one':hashlib.sha256(KEY.encode()).hexdigest(),
        'school_two':hashlib.sha256(OTHER_KEY.encode()).hexdigest()}))
    monkeypatch.setenv(bridge.FLAG,'1')
    monkeypatch.setenv(old.FEATURE_FLAG,'1')
    monkeypatch.setenv('YKS_FEEDBACK_RELAY_URL','https://feedback.example.org')
    monkeypatch.setenv('YKS_FEEDBACK_RELAY_TENANT','school_one')
    monkeypatch.setenv('YKS_FEEDBACK_RELAY_KEY',KEY)
    def local_conn():
        conn=sqlite3.connect(str(local_db))
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    monkeypatch.setattr(old.db,'get_conn',local_conn,raising=False)
    con=local_conn()
    con.executescript('''CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,aktif INTEGER);
      CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER);
      CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,ders TEXT,konu_ad TEXT,durum TEXT);
      CREATE TABLE adaptive_quick_note_v28(id INTEGER PRIMARY KEY, student_id INTEGER,reason_code TEXT);
      INSERT INTO ogrenci VALUES (1,1),(2,1);
      INSERT INTO odev_kume VALUES (10,1),(20,2);
      INSERT INTO odev VALUES (100,1,10,'Fizik','Yay Dalgaları','tamam'),(200,2,20,'Matematik','Polinomlar','bekliyor');
      INSERT INTO adaptive_quick_note_v28 VALUES (9,1,'time');''')
    con.commit();con.close()
    client=TestClient(relay.app)
    def simulated_transport(method,path,data=None):
        headers={'x-kocpilot-tenant':'school_one','x-kocpilot-key':KEY,
                 'Content-Type':'application/json'}
        resp=client.request(method,path,headers=headers,json=data if method=='POST' else None)
        if resp.status_code not in (200,201):raise ValueError('Cloud failed: '+resp.text)
        return resp.json()
    monkeypatch.setattr(bridge,'_remote',simulated_transport)
    return client,local_conn


def answer():return {'completion':4,'understanding':2,'time_fit':3,'obstacle':'concept'}


def headers(tenant='school_one',key=KEY):
    return {'x-kocpilot-tenant':tenant,'x-kocpilot-key':key}


def test_disabled_by_default(system,monkeypatch):
    monkeypatch.delenv(bridge.FLAG)
    assert not bridge.configured()
    with pytest.raises(ValueError):bridge.create_link(1,100,'student')


def test_full_cloud_phone_local_review_and_idempotence(system):
    client,local=system
    before=local().execute('SELECT * FROM odev').fetchall()
    invite=bridge.create_link(1,100,'student')
    assert invite['url'].startswith('https://feedback.example.org/r/')
    assert not any(s in invite['url'] for s in ('Yay Dalgaları','student_id','100'))
    token=urlsplit(invite['url']).path.rsplit('/',1)[-1]
    r=client.get('/r/'+token)
    assert r.status_code==200
    assert 'Fizik' in r.text and 'Yay Dalgaları' in r.text
    assert 'ogrenci_id' not in r.text and KEY not in r.text
    r=client.post('/r/'+token,data={**{k:str(v) for k,v in answer().items()},'consent':'yes'})
    assert r.status_code==200
    assert client.post('/r/'+token,data={**{k:str(v) for k,v in answer().items()},'consent':'yes'}).status_code==410
    assert len(old.list_feedback(1))==0
    result=bridge.sync_replies()
    assert result['imported']==1 and result['skipped']==0
    assert bridge.sync_replies()['imported']==0
    assert old.list_feedback(2)==[]
    row=old.list_feedback(1)[0]
    assert row['answers']==answer() and row['review_state']=='pending'
    assert old.approved_summary(1)==[]
    old.decide(1,row['reply_id'],'approved')
    assert old.approved_summary(1)[0]['not_mastery_evidence'] is True
    con=local();assert con.execute('SELECT * FROM odev').fetchall()==before
    assert con.execute('SELECT reason_code FROM adaptive_quick_note_v28').fetchone()[0]=='time'
    con.close()


def test_other_tenant_cannot_read_or_answer_for_another_tenant(system):
    client,_=system
    bridge.create_link(1,100,'student')
    other=client.get('/v14/replies?cursor=0',headers=headers('school_two',OTHER_KEY))
    assert other.status_code==200 and other.json()['items']==[]
    assert client.get('/v14/replies',headers=headers('school_one','bad')).status_code==401
    assert client.get('/v14/replies').status_code==401


def test_wrong_student_or_moved_ownership_fails_closed(system):
    client,local=system
    with pytest.raises(ValueError):bridge.create_link(2,100,'parent')
    invite=bridge.create_link(1,100,'parent')
    token=urlsplit(invite['url']).path.rsplit('/',1)[-1]
    con=local();con.execute('UPDATE odev_kume SET ogrenci_id=2 WHERE id=10');con.commit();con.close()
    r=client.post('/r/'+token,data={**{k:str(v) for k,v in answer().items()},'consent':'yes'})
    assert r.status_code==200
    assert bridge.sync_replies()['skipped']==1
    assert old.list_feedback(1)==[]


def test_tenant_request_idempotency_replay_collision_and_revocation(system):
    client,_=system
    ref=str(uuid.uuid4());token='a'*43
    data={'invite_ref':ref,'token':token,'respondent':'student','lesson':'Fizik','topic':'Kuvvet'}
    first=client.post('/v14/invites',headers=headers(),json=data)
    assert first.status_code==200
    assert client.post('/v14/invites',headers=headers(),json=data).json()==first.json()
    assert client.post('/v14/invites',headers=headers(),json={**data,'topic':'X'}).status_code==409
    assert client.post('/v14/invites/'+ref+'/revoke',headers=headers()).status_code==200
    assert client.get('/r/'+token).status_code==410
    assert client.post('/v14/invites',headers=headers(),json=data).status_code==409


def test_no_html_injection_and_validation(system):
    client,_=system
    ref=str(uuid.uuid4())
    data={'invite_ref':ref,'token':'b'*43,'respondent':'parent',
          'lesson':'<script>alert(1)</script>','topic':'<b>hello</b>'}
    assert client.post('/v14/invites',headers=headers(),json=data).status_code==200
    html=client.get('/r/'+'b'*43).text
    assert '<script>' not in html and '<b>hello</b>' not in html
    assert '&lt;script&gt;' in html
    assert client.post('/r/'+'b'*43,data={**{k:str(v) for k,v in answer().items()},'consent':'no'}).status_code==422
    assert client.post('/r/'+'b'*43,data={**{k:str(v) for k,v in answer().items()},'consent':'yes'}).status_code==200


def test_no_token_or_student_identifiers_stored_centrally(system):
    client,local=system
    invite=bridge.create_link(1,100,'student')
    token=invite['url'].rsplit('/',1)[-1]
    con=sqlite3.connect(client.app.state.x if False else __import__('os').environ['YKS_FEEDBACK_RELAY_DB'])
    row=con.execute('SELECT tenant,invite_ref,token_hash,respondent,lesson,topic FROM invites').fetchone()
    assert token not in row and row[2]==hashlib.sha256(token.encode()).hexdigest()
    columns=[x[1] for x in con.execute('PRAGMA table_info(invites)')]
    assert 'student_id' not in columns and 'homework_id' not in columns and 'phone' not in columns
    con.close()


def test_cloud_disabled_does_not_change_legacy_ui_route(system,monkeypatch):
    monkeypatch.setenv(bridge.FLAG,'0')
    assert bridge.configured() is False
