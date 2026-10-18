from pathlib import Path
import sqlite3
from services.live_change_probe_v241 import DatabaseChangeProbe
from services.student_change_scope_v242 import StudentChangeRouter

def test_end_to_end_committed_changes_correct_student(tmp_path):
    p=tmp_path/'live.db'
    with sqlite3.connect(p) as con:
        con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,ders TEXT,konu_ad TEXT,durum TEXT);
            INSERT INTO ogrenci VALUES(1,'Ali','A'),(2,'Beyza','B');
        ''')
    watcher=DatabaseChangeProbe(p)
    assert watcher.poll() is False
    scopes=StudentChangeRouter()
    scopes.baseline(watcher._connection,1)
    scopes.baseline(watcher._connection,2)
    writer=sqlite3.connect(p)
    writer.execute('INSERT INTO odev VALUES(1,2,?,?,?)',('LGS Mat','Uslu','devam'))
    assert watcher.poll() is False
    writer.rollback()
    assert watcher.poll() is False
    writer.execute('INSERT INTO odev VALUES(2,2,?,?,?)',('LGS Mat','Koklu','devam'))
    writer.commit()
    assert watcher.poll() is True
    changes=scopes.after_commit(watcher._connection,[1,2])
    assert 1 not in changes and changes[2].kinds==('homework',)
    writer.execute('UPDATE odev SET durum=? WHERE id=2',('tamam',))
    writer.commit()
    assert watcher.poll() is True
    changes=scopes.after_commit(watcher._connection,[1,2])
    assert 1 not in changes and changes[2].kinds==('homework',)
    writer.close();watcher.close()

def test_readonly_scope_does_not_modify_student_database(tmp_path):
    p=tmp_path/'test.db'
    with sqlite3.connect(p) as con:
        con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT)')
        con.execute('INSERT INTO ogrenci VALUES(1,?,?)',('Student','Name'))
    before=p.read_bytes()
    with DatabaseChangeProbe(p) as probe:
        assert probe.poll() is False
        tracker=StudentChangeRouter()
        tracker.baseline(probe._connection,1)
        assert tracker.after_commit(probe._connection,[1])=={}
    assert before==p.read_bytes()
