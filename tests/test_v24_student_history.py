"""V24 öğrenci kimliği ayrılmış trend kayıtlarının SQLite uyumluluğu."""
import datetime as dt
import json
import sqlite3
import pytest
from services.target_analysis_v24.student_history import StudentTrendStore


def test_scoped_history_does_not_mix_students(tmp_path):
    p = tmp_path/'deneme_history.db'
    store = StudentTrendStore(str(p))
    store.add(1,dt.date(2026,10,1),'YKS','SAY',{'tyt_total':30},'deneme:12:SAY')
    store.add(2,dt.date(2026,10,1),'YKS','SAY',{'tyt_total':70},'deneme:12:SAY')
    assert store.list_last(1,'YKS','SAY')[0][1]['tyt_total'] == 30
    assert store.list_last(2,'YKS','SAY')[0][1]['tyt_total'] == 70
    assert store.list_last(3,'YKS','SAY') == []


def test_idempotent_exam_sync_and_manual_history(tmp_path):
    store = StudentTrendStore(str(tmp_path/'history.sqlite'))
    day=dt.date(2026,10,2)
    assert store.add(1,day,'YKS','EA',{'tyt_total':50},'deneme:44:EA')
    assert not store.add(1,day,'YKS','EA',{'tyt_total':50},'deneme:44:EA')
    assert store.add(1,day,'YKS','EA',{'tyt_total':51})
    assert store.add(1,day,'YKS','EA',{'tyt_total':52})
    assert len(store.list_last(1,'YKS','EA')) == 3


def test_existing_anonymous_legacy_deneme_not_assigned(tmp_path):
    p=tmp_path/'history.db'
    with sqlite3.connect(p) as con:
        con.execute('CREATE TABLE deneme(id INTEGER PRIMARY KEY,d TEXT,exam TEXT,alan TEXT,payload TEXT)')
        con.execute('INSERT INTO deneme VALUES (1,?,?,?,?)',('2026-10-02','YKS','SAY',json.dumps({'tyt_total':90})))
    store=StudentTrendStore(str(p))
    assert store.list_last(1,'YKS','SAY') == []
    with sqlite3.connect(p) as con:
        assert con.execute('SELECT COUNT(*) FROM deneme').fetchone()[0] == 1
        assert con.execute('SELECT payload FROM deneme').fetchone()[0] == json.dumps({'tyt_total':90})


def test_last_entries_are_last_by_date_not_oldest(tmp_path):
    store = StudentTrendStore(str(tmp_path/'history.db'))
    for i in range(30):
        store.add(1,dt.date(2026,1,1)+dt.timedelta(days=i),'LGS','LGS',{'n':i})
    rows=store.list_last(1,'LGS','LGS',n=20)
    assert len(rows)==20
    assert rows[0][1]['n']==10
    assert rows[-1][1]['n']==29


def test_invalid_student_rejected(tmp_path):
    store=StudentTrendStore(str(tmp_path/'history.db'))
    with pytest.raises(ValueError):store.add(0,dt.date.today(),'YKS','SAY',{})
    assert store.list_last(0,'YKS','SAY') == []


def test_source_import_never_writes_legacy_data(tmp_path):
    p=tmp_path/'history.db'
    store=StudentTrendStore(str(p))
    store.add(2,dt.date(2026,10,12),'YKS','SAY',{'tyt_total':55})
    with sqlite3.connect(p) as con:
        assert con.execute('SELECT COUNT(*) FROM deneme_student_v24').fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='deneme'").fetchone()[0] == 0
