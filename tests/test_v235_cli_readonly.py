"""CLI acceptance: read-only, no implicit empty DB creation, error exit codes."""
from pathlib import Path
import sqlite3
import subprocess
import sys

TOOL = Path(__file__).resolve().parents[1] / 'tools' / 'audit_integration_v235.py'


def make_database(path, bad=False):
    with sqlite3.connect(path) as con:
        con.executescript('''CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, aktif INTEGER);
        INSERT INTO ogrenci VALUES(1,1);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,durum TEXT);
        INSERT INTO odev VALUES(10,1,'devam');
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,odev_id INTEGER);
        ''')
        if bad:
            con.execute('INSERT INTO odev_satir VALUES(5,1,999)')


def call(path):
    return subprocess.run([sys.executable,str(TOOL),'--db',str(path)],
                          capture_output=True,text=True,timeout=10)


def test_clean_copy_is_read_only(tmp_path):
    path=tmp_path/'test.db';make_database(path)
    before=path.read_bytes()
    result=call(path)
    assert result.returncode==0, result.stderr + result.stdout
    assert 'Ana ödev: 1' in result.stdout
    assert path.read_bytes()==before
    assert not (tmp_path/'test.db-wal').exists()


def test_problematic_copy_returns_nonzero_without_repairs(tmp_path):
    path=tmp_path/'bad.db';make_database(path,bad=True)
    before=path.read_bytes()
    result=call(path)
    assert result.returncode==1
    assert 'Kopuk bağlantı: 1' in result.stdout
    assert path.read_bytes()==before


def test_missing_db_does_not_create_empty_database(tmp_path):
    path=tmp_path/'missing.db'
    result=call(path)
    assert result.returncode!=0
    assert not path.exists()


def test_missing_required_schema_is_fail_closed(tmp_path):
    path=tmp_path/'invalid.db'
    sqlite3.connect(path).close()
    before=path.read_bytes()
    result=call(path)
    assert result.returncode==2
    assert 'DENETİM YAPILAMADI' in result.stdout
    assert path.read_bytes()==before
