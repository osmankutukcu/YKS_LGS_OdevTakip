"""Temporary-database integration smoke for real project's db.py and web_api.main.
No user databases, live data or desktop UI are read/written.
This test process stubs PyQt imports ONLY because PyQt6 is absent from CI container.
"""
import os
import sys
import types
import sqlite3
import shutil
import importlib
from pathlib import Path
from datetime import date

# The production desktop environment has PyQt6. For headless CI only,
# supply import-time placeholders; this test never invokes Qt widgets.
try:
    from PyQt6.QtCore import Qt  # noqa: F401
    from PyQt6.QtGui import QColor  # noqa: F401
    from PyQt6.QtWidgets import QMessageBox, QApplication  # noqa: F401
except ImportError:
    for name, fields in {'PyQt6': [], 'PyQt6.QtCore': ['Qt'],
                         'PyQt6.QtGui': ['QColor'],
                         'PyQt6.QtWidgets': ['QMessageBox', 'QApplication']}.items():
        mod = types.ModuleType(name)
        for field in fields:
            setattr(mod, field, type(field, (), {}))
        sys.modules[name] = mod

import pytest

@pytest.fixture(scope='module')
def fixtures(tmp_path_factory):
    path = tmp_path_factory.mktemp('safe-v3')/'master.sqlite'
    os.environ['YKS_DB_PATH'] = str(path)
    os.environ['YKS_AUTO_ADOPT'] = '0'
    os.environ['YKS_WEB_ACCESS_TOKEN'] = 'local-test-token-only-' + 'z'*32
    import db
    db.DB_PATH = path
    from web_api import main
    from web_api import sync_engine
    from web_api import sync_transactions
    con = db.init_db()
    con.execute("INSERT INTO ogrenci(ad,soyad,aktif,ana_grup,alt_grup) VALUES('Synthetic','Student',1,'YKS','12')")
    student_id = con.execute("SELECT id FROM ogrenci WHERE ad='Synthetic'").fetchone()[0]
    con.commit()
    con.close()
    return path, db, main, sync_engine, sync_transactions, student_id

def test_snapshot_real_schema(fixtures):
    path, db, main, sync, trans, student_id = fixtures
    snapshot = sync.get_sync_snapshot(student_id=None)
    assert student_id in [r['id'] for r in snapshot['students']]
    assert snapshot['database_id']
    assert 'status_fingerprints' in snapshot['curriculum'][student_id]

def test_homework_sql_matches_live_endpoint(fixtures, tmp_path):
    path, db, main, sync, trans, student_id = fixtures
    from web_api.main import HomeworkCreate
    from web_api.sync_engine import MutationItem
    # Byte-for-byte starting database state for both execution paths.
    baseline = tmp_path / 'baseline.sqlite'
    with sqlite3.connect(path) as src, sqlite3.connect(baseline) as dst:
        src.backup(dst)
    input_ = {'student_id':student_id, 'lesson':'fizik', 'book':'Synthetic Book',
              'topics':['Kuvvet','Enerji'], 'due_date':'2026-10-21', 'given_date':'2026-10-12'}
    before_get = db.get_conn
    try:
        db.get_conn = lambda: sqlite3.connect(baseline)
        actual = main.create_homework(HomeworkCreate(**input_))
        assert actual['kume_id']
    finally:
        db.get_conn = before_get
    with sqlite3.connect(path) as conn:
        item = MutationItem(id='test-assignment-123', type='ASSIGN_HOMEWORK',
                            payload={'student_id':student_id,'lesson':'fizik',
                                     'book':'Synthetic Book','topics':['Kuvvet','Enerji'],
                                     'due_date':'2026-10-21', 'assigned_local_date':'2026-10-12'},
                            created_at='2026-10-12T11:00:00+03:00')
        response = trans.apply_once(conn,item)
        assert response['status']=='applied'
    for table in ['odev_kume','odev','odev_satir','kitap']:
        with sqlite3.connect(path) as conn, sqlite3.connect(baseline) as base:
            # Compare only affected lesson/student rows, original seeded kitap names
            if table=='kitap':
                q="SELECT ders,ad FROM kitap WHERE ad='Synthetic Book' ORDER BY ders,ad"
            elif table=='odev_kume':
                q=f'SELECT ogrenci_id,verilis_tarihi,bitis_tarihi FROM odev_kume WHERE ogrenci_id={student_id} ORDER BY id'
            elif table=='odev':
                q=f'SELECT kume_id,ogrenci_id,ders,konu_id,konu_ad,kitap_ad,durum,verilis_tarihi FROM odev WHERE ogrenci_id={student_id} ORDER BY id'
            else:
                q=f'SELECT odev_id,kume_id,ogrenci_id,ders,konu,kitap,durum,tarih FROM odev_satir WHERE ogrenci_id={student_id} ORDER BY id'
            assert conn.execute(q).fetchall()==base.execute(q).fetchall(), table

def test_offline_default_deadline_uses_assigned_day(fixtures):
    _,_,_,_,trans,student_id=fixtures
    from web_api.sync_engine import MutationItem
    item=MutationItem(id='test-default-due-123',type='ASSIGN_HOMEWORK',payload={
        'student_id':student_id,'lesson':'fizik','book':'Default Deadline',
        'topics':['Deney'], 'assigned_local_date':'2026-10-10'},
        created_at='2026-10-10T11:00:00+03:00')
    import db
    with db.get_conn() as con:
        result=trans.apply_once(con,item)
        assert result['status']=='applied'
        deadline=con.execute('SELECT bitis_tarihi FROM odev_kume WHERE id=?',
                             (result['detail']['kume_id'],)).fetchone()[0]
        assert deadline == '2026-10-17'

def test_fingerprint_prevents_lost_desktop_edit(fixtures):
    _,db,_,sync,trans,student_id=fixtures
    from web_api.sync_engine import MutationItem
    with db.get_conn() as conn:
        row=conn.execute('SELECT id,durum,tamamlanma_tarihi FROM odev WHERE ogrenci_id=? ORDER BY id',(student_id,)).fetchone()
        header_id=row[0]
        old_hash=trans.status_fingerprint(*row)
        conn.execute("UPDATE odev SET durum='tamam',tamamlanma_tarihi='2026-10-14 11:30:00' WHERE id=?",(header_id,))
        conn.commit()
    mutation=MutationItem(id='test-conflict-1234',type='SET_HOMEWORK_STATUS',payload={
        'homework_ids':[header_id], 'status':'devam','expected_statuses':{str(header_id):'devam'},
        'expected_fingerprints':{str(header_id):old_hash}})
    response=sync.process_sync_push(sync.SyncPushRequest(mutations=[mutation]))
    assert response['results'][0]['status']=='conflict'
    with db.get_conn() as conn:
        assert conn.execute('SELECT durum FROM odev WHERE id=?',(header_id,)).fetchone()[0]=='tamam'

def test_idempotence_receipt_on_real_schema(fixtures):
    _,db,_,sync,_,student_id=fixtures
    from web_api.sync_engine import MutationItem
    item=MutationItem(id='test-once-12345',type='ASSIGN_HOMEWORK',payload={
        'student_id':student_id,'lesson':'fizik','book':'Once','topics':['Tekrar'],
        'assigned_local_date':'2026-10-14'},created_at='2026-10-14T10:00:00+03:00')
    first=sync.process_sync_push(sync.SyncPushRequest(mutations=[item]))
    again=sync.process_sync_push(sync.SyncPushRequest(mutations=[item]))
    assert first['results'][0]['status']=='applied'
    assert again['results'][0]['status']=='already_applied'
    with db.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM odev WHERE kitap_ad='Once'").fetchone()[0]==1


def test_offline_week_queue_500_idempotent(fixtures):
    _,db,_,sync,_,student_id=fixtures
    from web_api.sync_engine import MutationItem
    import uuid
    batch=[]
    for index in range(500):
        batch.append(MutationItem(id=f'test-week-{index:04d}-unique', type='ASSIGN_HOMEWORK',
            payload={'student_id':student_id,'lesson':'fizik','book':'Week Batch',
                     'topics':[f'Synthetic Topic {index}'],'due_date':'2026-10-21',
                     'assigned_local_date':'2026-10-14'},
            created_at='2026-10-14T10:00:00+03:00'))
    for start in range(0,len(batch),100):
        result=sync.process_sync_push(sync.SyncPushRequest(mutations=batch[start:start+100]))
        assert result['success'] and result['acknowledged_count']==100
        again=sync.process_sync_push(sync.SyncPushRequest(mutations=batch[start:start+100]))
        assert again['success'] and again['acknowledged_count']==100
        assert all(r['status']=='already_applied' for r in again['results'])
    with db.get_conn() as con:
        assert con.execute("SELECT count(*) FROM odev WHERE kitap_ad='Week Batch'").fetchone()[0]==500

def test_partial_batch_keeps_later_commands(fixtures):
    _,db,_,sync,_,student_id=fixtures
    from web_api.sync_engine import MutationItem
    def m(uid,sid):return MutationItem(id=uid,type='ASSIGN_HOMEWORK',payload={
        'student_id':sid,'lesson':'fizik','book':'Partial Batch',
        'topics':['Risk'],'due_date':'2026-10-21','assigned_local_date':'2026-10-14'})
    result=sync.process_sync_push(sync.SyncPushRequest(mutations=[
        m('test-partial-0001',student_id),m('test-partial-0002',999999),m('test-partial-0003',student_id)]))
    assert not result['success']
    assert result['processed_count']==0
    assert [r['status'] for r in result['results']]==['applied','rejected','deferred']
    with db.get_conn() as con:
        assert con.execute("SELECT count(*) FROM odev WHERE kitap_ad='Partial Batch'").fetchone()[0]==1
