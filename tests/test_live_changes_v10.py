"""V10 local desktop change hints - no student DB writes from observer."""
import sqlite3
from pathlib import Path
from fastapi import HTTPException
import pytest
from web_api.live_changes_v10 import _Observer


def database(path: Path):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE mobile_sync_identity(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    con.execute("INSERT INTO mobile_sync_identity VALUES('database_id','pilot-db-123')")
    con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT)')
    con.execute('INSERT INTO ogrenci VALUES (1,\'Demo\')')
    con.commit()
    con.close()


def test_change_and_read_only(tmp_path):
    path = tmp_path / 'student.db'
    database(path)
    observer = _Observer()
    first = observer.read(path)
    assert first['revision'] == 0
    assert first['cloud_verified'] is False
    assert first['database_id'] == 'pilot-db-123'
    assert set(first) == {'version', 'database_id','epoch','revision','scope','cloud_verified'}
    assert observer.read(path)['revision'] == 0
    con = sqlite3.connect(path)
    con.execute("UPDATE ogrenci SET ad='Yeni' WHERE id=1")
    con.commit()
    con.close()
    next_state = observer.read(path)
    assert next_state['revision'] > first['revision']
    assert next_state['epoch'] == first['epoch']
    assert observer.read(path)['revision'] == next_state['revision']
    con = sqlite3.connect(path)
    assert con.execute('SELECT ad FROM ogrenci WHERE id=1').fetchone()[0] == 'Yeni'
    assert con.execute('SELECT COUNT(*) FROM sqlite_master WHERE name LIKE "%live10%"').fetchone()[0] == 0
    con.close()
    observer.monitor.close()


def test_reject_missing_identity(tmp_path):
    path = tmp_path / 'blank.db'
    with sqlite3.connect(path) as con:
        con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY)')
    observer = _Observer()
    with pytest.raises(HTTPException) as exc:
        observer.read(path)
    assert exc.value.status_code == 503
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='mobile_sync_identity'").fetchone()[0] == 0


def test_missing_db_is_not_created(tmp_path):
    path = tmp_path / 'not-there.db'
    with pytest.raises(HTTPException):
        _Observer().read(path)
    assert not path.exists()


def test_database_replacement_changes_epoch(tmp_path):
    path = tmp_path / 'db.sqlite'
    database(path)
    watcher = _Observer()
    a = watcher.read(path)
    alternate = tmp_path / 'replacement.sqlite'
    database(alternate)
    # Replace DB (not edit a running production DB!) to test fail-safe epoch.
    alternate.replace(path)
    b = watcher.read(path)
    assert b['epoch'] == a['epoch']
    assert b['revision'] > a['revision']
    watcher.monitor.close()
