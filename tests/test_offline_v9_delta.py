"""Changed-record transfer: synthetic data only, no edits to SQLite."""
import copy
import hashlib
import json
import time
import pytest
from fastapi import HTTPException
from web_api import delta_pages_v9 as d


def snapshot(n=120):
    s = [{'id':i,'ad':'Öğrenci 🎓'+str(i),'soyad':'Test'} for i in range(1,n+1)]
    return {'version':1,'database_id':'testdb-001', 'generated_at':'2026-10-15T08:00:00',
            'students':s,'curriculum':{str(i):{'lessons':[], 'books':{'10':['Türkçe','Matematik']},
            'topics':{'2':[{'value':1.0, 'text':'Fizik'}]}} for i in range(1,n+1)}}


def manifest(snap):
    return {str(s['id']):d.record_hash(s, snap['curriculum'][str(s['id'])]) for s in snap['students']}


def test_changed_and_deleted_patch_keeps_previous_snapshot_immutable():
    base=snapshot()
    old=manifest(base)
    new=copy.deepcopy(base)
    new['students'][3]['ad']='Updated'
    new['curriculum']['9']['topics']['2']=[{'value': 2,'text':'new'}]
    new['students'].pop(9) # student #10 removed
    del new['curriculum']['10']
    new['students'].append({'id':200,'ad':'Yeni','soyad':'Öğrenci'})
    new['curriculum']['200']={'lessons':[], 'books':{},'topics':{}}
    result=d.build_patch(new,d.DeltaStart(database_id='testdb-001',manifest=old))
    assert set(result['changed'])=={'4','9','200'}
    assert result['removed']==['10']
    assert result['order'][-1]=='200'
    assert len(result['index'])==120
    started=d.make_session(new,d.DeltaStart(database_id='testdb-001',manifest=old))
    new['students'][3]['ad']='MUTATED AFTER SESSION'
    payload=''.join(d.delta_page(started['token'],p)['chunk'] for p in range(started['pages']))
    assert hashlib.sha256(payload.encode('ascii')).hexdigest()==started['sha256']
    assert json.loads(payload)['changed']['4']['student']['ad']=='Updated'
    assert d.delta_close(started['token'])=={'ok':True}
    with pytest.raises(HTTPException) as e:d.delta_page(started['token'],0)
    assert e.value.status_code==410


def test_unchanged_is_small_and_wrong_db_rejected():
    snap=snapshot(1000)
    patch=d.build_patch(snap,d.DeltaStart(database_id='testdb-001', manifest=manifest(snap)))
    assert patch['changed']=={} and len(patch['order'])==1000
    assert len(json.dumps(patch))<115000
    with pytest.raises(HTTPException) as err:
        d.build_patch(snap,d.DeltaStart(database_id='other',manifest={}))
    assert err.value.status_code==409


def test_input_guards_and_expiration(monkeypatch):
    snap=snapshot(3)
    for bad in [{'abc':'0'*64},{'1':'BAD'},{'1':'b'*63}]:
        with pytest.raises(HTTPException):
            d.build_patch(snap,d.DeltaStart(database_id='testdb-001',manifest=bad))
    token=d.make_session(snap,d.DeltaStart(database_id='testdb-001',manifest={}))['token']
    with pytest.raises(HTTPException) as e:d.delta_page(token,-1)
    assert e.value.status_code==404
    d.delta_close(token)
    monkeypatch.setattr(d,'MAX_PATCH_CHARS',10)
    with pytest.raises(HTTPException) as e:d.make_session(snap,d.DeltaStart(database_id='testdb-001',manifest={}))
    assert e.value.status_code==413
    monkeypatch.setattr(d,'MAX_PATCH_CHARS',24*1024*1024)
    d._sessions['expired'] = d.DeltaSession('{}', 'a'*64,time.monotonic()-d.SESSION_TTL_SEC-1)
    with pytest.raises(HTTPException) as e:d.delta_page('expired',0)
    assert e.value.status_code==410


def test_real_api_endpoint_is_only_additive():
    from pathlib import Path
    paths={x.path for x in d.router.routes}
    assert '/delta9/start' in paths
    assert '/delta9/{token}/{page}' in paths
    original=Path(__file__).parents[1].joinpath('web_api/sync_engine.py').read_text(encoding='utf-8')
    assert 'sync_router.include_router(delta_router)' in original
    assert '@sync_router.post("/push")' in original
    assert '@sync_router.get("/snapshot")' in original
