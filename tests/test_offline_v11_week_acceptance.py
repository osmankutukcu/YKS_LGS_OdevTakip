"""V11 synthetic seven-day transactional acceptance tests.

All tests target a disposable SQLite database.  They are NOT tests on real
phones, Windows executables or customer records.  No live DB path is used.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import types
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

import pytest

# Headless import-only stand-ins (the Windows application uses real PyQt6).
try:
    import PyQt6.QtCore, PyQt6.QtGui, PyQt6.QtWidgets
except ImportError:
    for name, fields in {'PyQt6': [], 'PyQt6.QtCore':['Qt'],
                         'PyQt6.QtGui':['QColor'],
                         'PyQt6.QtWidgets':['QMessageBox','QApplication']}.items():
        if name not in sys.modules:
            mod = types.ModuleType(name)
            for field in fields: setattr(mod,field,type(field,(),{}))
            sys.modules[name] = mod

@pytest.fixture(scope='module')
def master(tmp_path_factory):
    root=tmp_path_factory.mktemp('v11-disposable-db')
    path=root/'v11_synthetic.sqlite'
    old_env={k:os.environ.get(k) for k in ('YKS_DB_PATH','YKS_AUTO_ADOPT','YKS_WEB_ACCESS_TOKEN')}
    # Do not allow the tests to read or overwrite an inherited live path.
    os.environ['YKS_DB_PATH']=str(path)
    os.environ['YKS_AUTO_ADOPT']='0'
    os.environ['YKS_WEB_ACCESS_TOKEN']='v11-test-only-'+ 't'*32
    import db
    old_db_path = getattr(db, 'DB_PATH', None)
    db.DB_PATH = path
    from web_api import sync_transactions as txn
    from web_api import sync_engine as sync
    con=db.init_db()
    con.execute("INSERT INTO ogrenci(ad,soyad,aktif,ana_grup,alt_grup) VALUES('Test','Zero',1,'YKS','12')")
    first=con.execute("SELECT id FROM ogrenci WHERE ad='Test' AND soyad='Zero'").fetchone()[0]
    con.execute("INSERT INTO ogrenci(ad,soyad,aktif,ana_grup,alt_grup) VALUES('Test','One',1,'YKS','12')")
    second=con.execute("SELECT id FROM ogrenci WHERE ad='Test' AND soyad='One'").fetchone()[0]
    con.commit()
    txn.ensure_desktop_schema(con)
    dbid=txn.database_identity(con)
    con.commit();con.close()
    yield db,txn,sync,path,dbid,(first,second)
    if old_db_path is not None:
        db.DB_PATH = old_db_path
    for k,v in old_env.items():
        if v is None: os.environ.pop(k,None)
        else: os.environ[k]=v

def command(i,student,days_ago=0, book='V11 seven-day workload'):
    from web_api.sync_engine import MutationItem
    assigned=(date.today()-timedelta(days=days_ago)).isoformat()
    return MutationItem(
        id=f'v11-seven-day-{i:06d}', type='ASSIGN_HOMEWORK',
        payload={'student_id':student,'lesson':'fizik','book':book,
                 'topics':[f'Test konusu {i}'],'assigned_local_date':assigned,
                 'due_date':(date.today()-timedelta(days=days_ago)+timedelta(days=7)).isoformat()},
        created_at=f'{assigned}T10:00:00+03:00')

def test_seven_days_700_actions_at_least_once_network(master):
    db,txn,sync,path,dbid,students=master
    # 7 days * 100 commands; the synthetic user's work is split across students.
    items=[command(i,students[i%2],days_ago=6-i//100) for i in range(700)]
    observed=[]
    for start in range(0,len(items),100):
        batch=items[start:start+100]
        result=sync.process_sync_push(sync.SyncPushRequest(mutations=batch,database_id=dbid))
        assert result['success'] and result['acknowledged_count']==len(batch)
        assert [r['status'] for r in result['results']]==['applied']*len(batch)
        observed.extend(r['id'] for r in result['results'])
    assert len(set(observed))==700
    # Simulate losing all HTTP responses and re-sending the same commands.
    for start in range(0,len(items),100):
        result=sync.process_sync_push(sync.SyncPushRequest(
            mutations=items[start:start+100],database_id=dbid))
        assert result['success'] and result['applied_count']==0
        assert all(r['status']=='already_applied' for r in result['results'])
    with db.get_conn() as con:
        assert con.execute("SELECT count(*) FROM mobile_sync_receipts WHERE mutation_id LIKE 'v11-seven-day-%'").fetchone()[0]==700
        assert con.execute("SELECT count(*) FROM odev WHERE kitap_ad='V11 seven-day workload'").fetchone()[0]==700
        assert con.execute("SELECT count(*) FROM odev_satir WHERE kitap='V11 seven-day workload'").fetchone()[0]==700
        assert con.execute("SELECT count(DISTINCT verilis_tarihi) FROM odev WHERE kitap_ad='V11 seven-day workload'").fetchone()[0]==7
        assert con.execute("PRAGMA integrity_check").fetchone()[0]=='ok'

def test_partial_rejection_retains_order_and_allows_retry(master):
    db,txn,sync,path,dbid,students=master
    good=command(810,students[0],book='V11 partial batch')
    invalid=command(811,999999,book='V11 partial batch')
    last=command(812,students[1],book='V11 partial batch')
    result=sync.process_sync_push(sync.SyncPushRequest(mutations=[good,invalid,last],database_id=dbid))
    assert [x['status'] for x in result['results']]==['applied','rejected','deferred']
    # Simulate client retaining only unacknowledged IDs and fixing the invalid target.
    fixed=command(813,students[0],book='V11 partial batch')
    result=sync.process_sync_push(sync.SyncPushRequest(mutations=[fixed,last],database_id=dbid))
    assert [x['status'] for x in result['results']]==['applied','applied']
    with db.get_conn() as con:
        assert con.execute("SELECT count(*) FROM odev WHERE kitap_ad='V11 partial batch'").fetchone()[0]==3

def test_wrong_desktop_and_digest_mismatch_do_not_write(master):
    db,txn,sync,path,dbid,students=master
    mutation=command(900,students[0],book='V11 identity guard')
    refused=sync.process_sync_push(sync.SyncPushRequest(mutations=[mutation],database_id='OTHER-DESKTOP-ID'))
    assert refused['results'][0]['status']=='conflict'
    with db.get_conn() as con:
        assert con.execute("SELECT count(*) FROM odev WHERE kitap_ad='V11 identity guard'").fetchone()[0]==0
    accepted=sync.process_sync_push(sync.SyncPushRequest(mutations=[mutation],database_id=dbid))
    assert accepted['results'][0]['status']=='applied'
    replacement=command(900,students[0],book='V11 changed payload')
    refused=sync.process_sync_push(sync.SyncPushRequest(mutations=[replacement],database_id=dbid))
    assert refused['results'][0]['status']=='conflict'
    with db.get_conn() as con:
        assert con.execute("SELECT count(*) FROM odev WHERE kitap_ad='V11 changed payload'").fetchone()[0]==0

def test_stale_header_fingerprint_blocks_cross_device_overwrite(master):
    db,txn,sync,path,dbid,students=master
    result=sync.process_sync_push(sync.SyncPushRequest(
        mutations=[command(950,students[0],book='V11 concurrency')],database_id=dbid))
    header=result['results'][0]['detail']['kume_id']
    with db.get_conn() as con:
        row=con.execute('SELECT id,durum,tamamlanma_tarihi FROM odev WHERE kume_id=?',(header,)).fetchone()
        hid,status,completed_at=row
        fingerprint=txn.status_fingerprint(hid,status,completed_at)
        from web_api.homework_store import set_headers_done
        set_headers_done(con,[hid],True);con.commit()
    from web_api.sync_engine import MutationItem
    stale=MutationItem(id='v11-stale-000001',type='SET_HOMEWORK_STATUS',payload={
        'homework_ids':[hid], 'status':'devam',
        'expected_statuses':{str(hid):'devam'},'expected_fingerprints':{str(hid):fingerprint}},
        created_at=datetime.now(timezone.utc).isoformat())
    answer=sync.process_sync_push(sync.SyncPushRequest(mutations=[stale],database_id=dbid))
    assert answer['results'][0]['status']=='conflict'
    with db.get_conn() as con:
        current=con.execute('SELECT durum FROM odev WHERE id=?',(hid,)).fetchone()[0]
        from utils.homework_status import is_completed
        assert is_completed(current)

def test_read_only_snapshot_and_wrong_database_delta(master):
    db,txn,sync,path,dbid,students=master
    from web_api.delta_pages_v9 import DeltaStart, build_patch, record_hash
    from fastapi.encoders import jsonable_encoder
    before=path.stat().st_size
    snapshot=sync.get_sync_snapshot(student_id=None)
    assert snapshot['database_id']==dbid
    normalized=json.loads(json.dumps(jsonable_encoder(snapshot),ensure_ascii=False))
    manifest={str(s['id']):record_hash(s,normalized['curriculum'][str(s['id'])]) for s in normalized['students']}
    result=build_patch(snapshot,DeltaStart(database_id=dbid,manifest=manifest))
    assert result['changed']=={} and result['removed']==[]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        build_patch(snapshot,DeltaStart(database_id='WRONG-DB',manifest=manifest))
    assert exc.value.status_code==409
    # V11 deliberately does not assert bytewise DB size remains fixed: WAL can grow.
