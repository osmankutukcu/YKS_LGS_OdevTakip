"""V8 immutable snapshot paging; uses only synthetic student data."""
import hashlib
import json
import time
import pytest
from fastapi import HTTPException
from web_api import snapshot_pages_v8 as pages


def synthetic(count=1200):
    students=[{'id':i,'ad_soyad':f'Test {i}'} for i in range(1,count+1)]
    return {'version':1,'database_id':'synthetic-db-id','generated_at':'2026-10-15T10:00:00',
            'students':students,'curriculum':{str(i):{'lessons':[], 'books':{'physics':['synthetic'*60]},'topics':{},'active_homeworks': []} for i in range(1,count+1)}}


def test_pages_keep_consistent_snapshot_and_sha():
    data=synthetic()
    start=pages.make_session(data)
    assert start['version']==8 and start['pages']>=2
    # Mutation after session creation does not change the downloaded bytes.
    data['students'][0]['ad_soyad']='AFTER-SESSION'
    chunks=[]
    for number in range(start['pages']):
        page=pages.paged_get(start['token'], number)
        assert page['page']==number and page['pages']==start['pages']
        chunks.append(page['chunk'])
    raw=''.join(chunks)
    assert hashlib.sha256(raw.encode()).hexdigest()==start['sha256']
    loaded=json.loads(raw)
    assert loaded['students'][0]['ad_soyad']=='Test 1'
    assert loaded['database_id']=='synthetic-db-id'
    assert pages.paged_close(start['token'])=={'ok':True}
    with pytest.raises(HTTPException) as err:
        pages.paged_get(start['token'],0)
    assert err.value.status_code==410


def test_expiration_invalid_page_and_limits(monkeypatch):
    start=pages.make_session(synthetic(3))
    with pytest.raises(HTTPException) as err:
        pages.paged_get(start['token'], 99)
    assert err.value.status_code==404
    pages.paged_close(start['token'])
    monkeypatch.setattr(pages, 'MAX_SNAPSHOT_CHARS', 10)
    with pytest.raises(HTTPException) as err:
        pages.make_session(synthetic(1))
    assert err.value.status_code==413
    monkeypatch.setattr(pages, 'MAX_SNAPSHOT_CHARS',24 * 1024 * 1024)
    now=time.monotonic()
    pages._sessions['expired-session'] = pages.SnapshotSession('{}','synthetic','x'*64,now-pages.SESSION_TTL_SEC-1)
    with pytest.raises(HTTPException) as err:
        pages.paged_get('expired-session',0)
    assert err.value.status_code==410


def test_router_paths_are_additive():
    paths={route.path for route in pages.router.routes}
    assert '/paged/start' in paths
    assert '/paged/{token}/{page}' in paths
    assert '/paged/{token}/close' in paths
