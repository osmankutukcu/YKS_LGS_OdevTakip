"""All tests use synthetic records; no actual student data."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import zipfile
from datetime import date
from test_backup_manager import patched, make_db
from services.daily_followup_v12 import load_open_homework

ROOT=Path(__file__).resolve().parents[1]

def _audit():
    spec=importlib.util.spec_from_file_location('v13audit',ROOT/'tools'/'audit_odev_links_v13.py')
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_readonly_audit_detects_orphan_and_cross_student(tmp_path):
    db=tmp_path/'sample.db'
    with sqlite3.connect(db) as c:
        c.executescript('''CREATE TABLE ogrenci(id INTEGER PRIMARY KEY);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY);
        CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,odev_id INTEGER,ogrenci_id INTEGER,kume_id INTEGER);
        INSERT INTO ogrenci VALUES(1); INSERT INTO odev_kume VALUES(10);
        INSERT INTO odev VALUES(4,1,10);
        INSERT INTO odev_satir VALUES(8,99,1,10);
        INSERT INTO odev_satir VALUES(9,4,2,10);''')
    before=db.read_bytes()
    result=_audit().audit_path(db)
    assert result['orphan_links']==[8]
    assert result['cross_student_links']==[9]
    assert db.read_bytes()==before


def test_profiles_and_assignments_in_same_verified_backup(patched,monkeypatch):
    mgr,root=patched
    db=root/'veritabani.db';make_db(db)
    monkeypatch.setenv('YKS_DB_PATH',str(db))
    profile=root/'plan_profiles.json';profile.write_text(json.dumps({'Örnek':{'max':120}}),encoding='utf8')
    assignments=root/'plan_student_assignments.json';assignments.write_text('{"1":"Örnek"}',encoding='utf8')
    import services.plan_profile_store as store
    monkeypatch.setattr(store,'profile_path',lambda: profile)
    monkeypatch.setattr(store,'assignment_path',lambda: assignments)
    monkeypatch.setattr(store,'legacy_paths',lambda: [])
    out=root/'out';out.mkdir()
    ok,message=mgr.create_backup(out)
    assert ok,message
    arc=next(out.glob('*.zip'))
    with zipfile.ZipFile(arc) as z:
        meta=json.loads(z.read('backup_manifest.json'))
        assert meta['format_version']==2
        assert 'planner/plan_profiles.json' in z.namelist()
        assert json.loads(z.read('planner/plan_student_assignments.json'))['1']=='Örnek'
    assert mgr.verify_backup(arc)[0]


def test_invalid_profile_blocks_successful_backup(patched,monkeypatch):
    mgr,root=patched
    db=root/'veritabani.db';make_db(db)
    monkeypatch.setenv('YKS_DB_PATH',str(db))
    profile=root/'plan_profiles.json';profile.write_text('corrupted JSON',encoding='utf8')
    import services.plan_profile_store as store
    monkeypatch.setattr(store,'profile_path',lambda: profile)
    monkeypatch.setattr(store,'assignment_path',lambda: root/'missing.json')
    monkeypatch.setattr(store,'legacy_paths',lambda: [])
    out=root/'out';out.mkdir()
    assert not mgr.create_backup(out)[0]
    assert list(out.glob('*.zip'))==[]


def _followup_db():
    c=sqlite3.connect(':memory:')
    c.executescript('''CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER);
    CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,bitis_tarihi TEXT);
    CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,ders TEXT,
      konu_ad TEXT,kitap_ad TEXT,saat_dk INTEGER,durum TEXT, silindi INTEGER DEFAULT 0);
    INSERT INTO ogrenci VALUES(1,'Örnek','Öğrenci',1);
    INSERT INTO odev_kume VALUES(1,1,'2026-10-01');
    INSERT INTO odev_kume VALUES(2,1,'2026-10-19');''')
    return c


def test_old_completed_records_do_not_hide_recent_overdue():
    c=_followup_db()
    c.executemany('INSERT INTO odev(id,kume_id,ogrenci_id,ders,konu_ad,kitap_ad,saat_dk,durum) VALUES(?,1,1,?,?,?,?,?)',
       [(i,'Fizik','Tamamlandı','Kitap',40,'tamam') for i in range(1,400)])
    c.execute("INSERT INTO odev VALUES(500,1,1,'Fizik','Enerji','Kitap',45,'devam',0)")
    result=load_open_homework(c,1,today=date(2026,10,12),limit=2)
    assert [t['id'] for t in result['tasks']]==[500]
    c.close()


def test_future_or_deleted_tasks_do_not_consume_limit():
    c=_followup_db()
    c.executescript('''INSERT INTO odev VALUES(11,1,1,'Fizik','A','K',40,'devam',1);
    INSERT INTO odev VALUES(12,2,1,'Fizik','B','K',40,'devam',0);
    INSERT INTO odev VALUES(13,1,1,'Fizik','C','K',40,'devam',0);''')
    result=load_open_homework(c,1,today=date(2026,10,12),limit=1)
    assert [t['id'] for t in result['tasks']]==[13]
    c.close()
