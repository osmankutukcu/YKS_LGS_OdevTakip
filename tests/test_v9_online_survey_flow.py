"""Run after installing V9 into a TEST COPY: pytest -q tests/test_v9_online_survey_flow.py.
No real student records. Does not import PyQt or use the production database.
"""
import os,sys,types,sqlite3,json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

@pytest.fixture(scope='module')
def env(tmp_path_factory):
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    dbfile=tmp_path_factory.mktemp('surveys')/'demo.sqlite'
    old={k:os.environ.get(k) for k in ('YKS_DB_PATH','YKS_SURVEY_V9_ENABLED','YKS_SURVEY_PUBLIC_BASE_URL','YKS_WEB_ACCESS_TOKEN')}
    os.environ.update({'YKS_DB_PATH':str(dbfile),'YKS_SURVEY_V9_ENABLED':'1',
                       'YKS_SURVEY_PUBLIC_BASE_URL':'https://school.example','YKS_WEB_ACCESS_TOKEN':'x'*48})
    previous_db=sys.modules.get('db')
    fake=types.ModuleType('db')
    fake.get_conn=lambda:sqlite3.connect(str(dbfile),timeout=5)
    fake.load_custom_lessons=lambda:None
    sys.modules['db']=fake
    con=fake.get_conn()
    con.execute('CREATE TABLE ogrenci (id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER)')
    con.execute('CREATE TABLE ogrenci_anket (id INTEGER PRIMARY KEY AUTOINCREMENT,ogrenci_id INTEGER,anket_kodu TEXT,cevaplar TEXT,tarih TEXT DEFAULT CURRENT_TIMESTAMP)')
    con.executemany('INSERT INTO ogrenci VALUES (?,?,?,?)',[(71,'Test','A',1),(72,'Test','B',1)])
    con.commit();con.close()
    from web_api.main import app
    import services.survey_invite_writer_v9 as _w9
    import services.survey_review_v9 as _r9
    import web_api.survey_invites_v9 as _i9
    for _mod in (_w9, _r9, _i9):
        if hasattr(_mod, 'db'):
            _mod.db = fake
    client=TestClient(app)
    yield client,fake
    if previous_db is None:sys.modules.pop('db',None)
    else:
        sys.modules['db']=previous_db
        for _mod in (_w9, _r9, _i9):
            if hasattr(_mod, 'db'):
                _mod.db = previous_db
    for k,v in old.items():
        if v is None:os.environ.pop(k,None)
        else:os.environ[k]=v


def issue(client,student=71,code='time_management',key=True):
    return client.post('/api/v9/surveys/invites',json={'student_id':student,'survey_code':code},
                       headers={'x-access-key':'x'*48} if key else {})


def test_feature_off_and_admin_secret(env):
    client,_=env
    assert issue(client,key=False).status_code==401
    os.environ['YKS_SURVEY_V9_ENABLED']='0'
    assert issue(client).status_code==503
    os.environ['YKS_SURVEY_V9_ENABLED']='1'
    assert issue(client,code='exam_anxiety').status_code==422
    assert issue(client,code='sleep_energy').status_code==422
    assert issue(client,student=9999).status_code==422 or issue(client,student=9999).status_code==404
    os.environ['YKS_SURVEY_PUBLIC_BASE_URL']='http://school.example'
    assert issue(client).status_code==422
    os.environ['YKS_SURVEY_PUBLIC_BASE_URL']='https://school.example'


def test_one_time_validated_and_review(env):
    client,db=env
    response=issue(client)
    assert response.status_code==200
    result=response.json()
    assert result['student_id']==71 and result['url'].startswith('https://')
    path=urlsplit(result['url']).path
    token=path.rsplit('/',1)[-1]
    con=db.get_conn()
    row=con.execute('SELECT token_sha256 FROM survey_v9_invites ORDER BY id DESC LIMIT 1').fetchone()
    assert token not in row[0] and len(row[0])==64
    con.close()
    page=client.get(path)
    assert page.status_code==200 and 'Test A' not in page.text and 'Test B' not in page.text
    assert 'no-store' in page.headers['Cache-Control']
    assert page.headers['Referrer-Policy']=='no-referrer'
    assert client.post(path,data={}).status_code==422
    catalog=json.loads((Path(__file__).resolve().parents[1]/'services/survey_catalog_v9.json').read_text())
    answers={q['key']:'4' for q in catalog['time_management']['questions']}
    missing=answers.copy();missing.pop('tm_3')
    assert client.post(path,data=missing).status_code==422
    invalid=answers.copy();invalid['tm_2']='0'
    assert client.post(path,data=invalid).status_code==422
    extra=answers.copy();extra['student_id']='72'
    assert client.post(path,data=extra).status_code==422
    assert client.post(path,data=answers).status_code==200
    assert client.get(path).status_code==410
    assert client.post(path,data=answers).status_code==410
    con=db.get_conn()
    assert con.execute('SELECT COUNT(*) FROM ogrenci_anket').fetchone()[0]==0
    con.close()
    assert client.get('/api/v9/surveys/submissions?student_id=71').status_code==401
    inbox=client.get('/api/v9/surveys/submissions?student_id=71',headers={'x-access-key':'x'*48})
    assert inbox.status_code==200 and len(inbox.json())>=1
    sid=inbox.json()[0]['submission_id']
    assert client.get('/api/v9/surveys/submissions?student_id=72',headers={'x-access-key':'x'*48}).json()==[]
    accepted=client.post(f'/api/v9/surveys/submissions/{sid}/approve',headers={'x-access-key':'x'*48})
    assert accepted.status_code==200 and accepted.json()['student_id']==71
    assert client.post(f'/api/v9/surveys/submissions/{sid}/approve',headers={'x-access-key':'x'*48}).status_code==409
    con=db.get_conn()
    assert con.execute('SELECT COUNT(*) FROM ogrenci_anket WHERE ogrenci_id=71').fetchone()[0]==1
    assert con.execute('SELECT COUNT(*) FROM ogrenci_anket WHERE ogrenci_id=72').fetchone()[0]==0
    con.close()


def test_revoke_reject_expiry_and_isolation(env):
    client,db=env
    auth={'x-access-key':'x'*48}
    r=issue(client,student=72,code='digital_distraction')
    assert r.status_code==200
    path=urlsplit(r.json()['url']).path
    con=db.get_conn()
    invite_id=con.execute('SELECT id FROM survey_v9_invites ORDER BY id DESC LIMIT 1').fetchone()[0]
    con.close()
    assert client.post(f'/api/v9/surveys/invites/{invite_id}/revoke',headers=auth).status_code==200
    assert client.get(path).status_code==410
    assert client.post(f'/api/v9/surveys/invites/{invite_id}/revoke',headers=auth).status_code==409
    r=issue(client,student=72,code='digital_distraction')
    path=urlsplit(r.json()['url']).path
    from services.survey_invite_writer_v9 import CATALOG_PATH
    qs=json.loads(CATALOG_PATH.read_text())['digital_distraction']['questions']
    assert client.post(path,data={q['key']:'3' for q in qs}).status_code==200
    result=client.get('/api/v9/surveys/submissions?student_id=72',headers=auth)
    sid=result.json()[0]['submission_id']
    assert client.post(f'/api/v9/surveys/submissions/{sid}/reject',headers=auth).status_code==200
    assert client.post(f'/api/v9/surveys/submissions/{sid}/approve',headers=auth).status_code==409
    con=db.get_conn();assert con.execute('SELECT COUNT(*) FROM ogrenci_anket WHERE ogrenci_id=72').fetchone()[0]==0;con.close()
    r=issue(client,student=72)
    path=urlsplit(r.json()['url']).path
    con=db.get_conn()
    con.execute("UPDATE survey_v9_invites SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=(SELECT MAX(id) FROM survey_v9_invites)")
    con.commit();con.close()
    assert client.get(path).status_code==410
    assert client.get('/s/invalid-token').status_code==404

def test_desktop_link_revocation_restricted_to_selected_student(env):
    client,_=env
    from services.survey_invite_writer_v9 import active_links, revoke_link
    response=issue(client,student=71,code='study_habits')
    assert response.status_code==200
    url=response.json()['url']
    latest=active_links(71)[0]
    assert all('token' not in k for k in latest)
    with pytest.raises(ValueError):
        revoke_link(72,latest['id'])
    assert client.get(urlsplit(url).path).status_code==200
    assert revoke_link(71,latest['id']) is True
    assert client.get(urlsplit(url).path).status_code==410
    assert latest['id'] not in [r['id'] for r in active_links(71)]
