"""Run: python -m pytest -q tests/test_backup_manager.py

Test fixtures are synthetic; no real users or production data are accessed.
"""
import importlib.util
import json
import sqlite3
import sys
import types
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def patched(monkeypatch, tmp_path):
    qt = types.ModuleType('PyQt6')
    core = types.ModuleType('PyQt6.QtCore')
    core.QObject = type('QObject', (), {})
    core.pyqtSignal = lambda *a, **k: None
    qt.QtCore = core
    monkeypatch.setitem(sys.modules, 'PyQt6', qt)
    monkeypatch.setitem(sys.modules, 'PyQt6.QtCore', core)
    util = types.ModuleType('utils')
    settings = types.ModuleType('utils.settings')
    state = {}
    settings.ayar_get = lambda k, d=None: state.get(k, d)
    settings.ayar_set = lambda k, v: state.__setitem__(k, v)
    util.settings = settings
    monkeypatch.setitem(sys.modules, 'utils', util)
    monkeypatch.setitem(sys.modules, 'utils.settings', settings)
    monkeypatch.setitem(sys.modules, 'db', types.ModuleType('db'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('YKS_DB_PATH', raising=False)
    module_path = Path(__file__).resolve().parents[1] / 'utils' / 'backup_manager.py'
    spec = importlib.util.spec_from_file_location('patched_backup', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BackupManager(), tmp_path


def make_db(path):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT)')
    con.execute('INSERT INTO ogrenci(ad) VALUES (?)', ('Hayalî Öğrenci',))
    con.commit()
    con.close()


def test_no_false_success_when_database_missing(patched):
    manager, root = patched
    out = root / 'out'; out.mkdir()
    ok, message = manager.create_backup(out)
    assert not ok
    assert 'bulunamadı' in message
    assert list(out.glob('*.zip')) == []


def test_backup_actual_sqlite_with_checksum(patched, monkeypatch):
    manager, root = patched
    d = root / 'data'; d.mkdir()
    db_file = d / 'veritabani.db'
    make_db(db_file)
    monkeypatch.setenv('YKS_DB_PATH', str(db_file))
    out = root / 'out'; out.mkdir()
    ok, message = manager.create_backup(out)
    assert ok, message
    archives = list(out.glob('*.zip')); assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as zf:
        assert zf.testzip() is None
        assert 'veritabani.db' in zf.namelist()
        metadata = json.loads(zf.read('backup_manifest.json'))
        assert metadata['files'][0]['name'] == 'veritabani.db'
        copy = root / 'copy.db'; copy.write_bytes(zf.read('veritabani.db'))
    with sqlite3.connect(copy) as con:
        assert con.execute('SELECT ad FROM ogrenci').fetchone()[0] == 'Hayalî Öğrenci'


def test_unique_archive_names_even_same_second(patched, monkeypatch):
    manager, root = patched
    db_file = root / 'veritabani.db'; make_db(db_file)
    monkeypatch.setenv('YKS_DB_PATH', str(db_file))
    out = root / 'out'; out.mkdir()
    assert manager.create_backup(out)[0]
    assert manager.create_backup(out)[0]
    assert len(list(out.glob('*.zip'))) == 2


def test_wal_uncheckpointed_committed_data_backed_up(patched, monkeypatch):
    manager, root = patched
    db_file = root / 'veritabani.db'; make_db(db_file)
    writer = sqlite3.connect(db_file)
    writer.execute('PRAGMA journal_mode=WAL')
    writer.execute('INSERT INTO ogrenci(ad) VALUES (?)', ('WAL Örnek',))
    writer.commit()
    monkeypatch.setenv('YKS_DB_PATH', str(db_file))
    out = root / 'out'; out.mkdir()
    ok, message = manager.create_backup(out)
    assert ok, message
    with zipfile.ZipFile(next(out.glob('*.zip'))) as zf:
        restore = root / 'restore.db'; restore.write_bytes(zf.read('veritabani.db'))
    with sqlite3.connect(restore) as c:
        assert c.execute('SELECT COUNT(*) FROM ogrenci').fetchone()[0] == 2
    writer.close()


def test_only_blank_placeholder_does_not_pass(patched, monkeypatch):
    manager, root = patched
    db_file = root / 'veritabani.db'; db_file.touch()
    monkeypatch.setenv('YKS_DB_PATH', str(db_file))
    out = root / 'out'; out.mkdir()
    assert manager.create_backup(out)[0] is False
