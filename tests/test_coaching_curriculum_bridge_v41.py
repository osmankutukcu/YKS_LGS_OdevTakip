from __future__ import annotations
"""V41: student-local curriculum reads; protected homework/control not touched."""
import ast
import hashlib
import sqlite3
from pathlib import Path
import pytest
from services.coaching_curriculum_bridge_v41 import read_student_coach_subjects, read_scoped_topics

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def database(tmp_path):
    path = tmp_path/'coach.sqlite'
    con=sqlite3.connect(path)
    con.executescript('''
    CREATE TABLE ders_tanimlari(id TEXT PRIMARY KEY,ad TEXT,grup TEXT,aktif INTEGER,ozel INTEGER,siralama INTEGER);
    CREATE TABLE grup_dersleri(grup_adi TEXT,ders_id TEXT);
    CREATE TABLE tyt_matematik(id INTEGER PRIMARY KEY,konu TEXT);
    CREATE TABLE lgs_fen(id INTEGER PRIMARY KEY,konu TEXT);
    CREATE TABLE ozel_fizik(id INTEGER PRIMARY KEY,konu TEXT);
    CREATE TABLE ozel_eski(id INTEGER PRIMARY KEY,konu TEXT);
    CREATE TABLE grup_konu_duzen(ders TEXT,ana_grup TEXT,alt_grup TEXT,konu TEXT);
    CREATE TABLE ogrenci_konu_duzen(ders TEXT,ogrenci_id INT,konu TEXT);
    CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INT,ders_adi TEXT,konu_adi TEXT);
    CREATE TABLE koc_kitaplar(id INTEGER PRIMARY KEY,ogrenci_id INT,ders_adi TEXT);
    ''')
    con.executemany('INSERT INTO ders_tanimlari VALUES(?,?,?,?,?,?)', [
        ('tyt_matematik','TYT Matematik','YKS',1,0,1),
        ('lgs_fen','LGS Fen','LGS',1,0,2),
        ('ozel_fizik','İleri Fizik','YKS',1,1,3),
        ('ozel_eski','Terk Edilmiş','YKS',0,1,4),
        ('ozel_baska','Başka Sınıfın Dersi','YKS',1,1,5),
    ])
    con.executemany('INSERT INTO grup_dersleri VALUES(?,?)', [
        ('12-say','tyt_matematik'), ('12-say','ozel_fizik'),
        ('11-say','ozel_baska'), ('8.sınıf','lgs_fen')
    ])
    con.executemany('INSERT INTO tyt_matematik(konu) VALUES(?)', [('Genel Matematik',)])
    con.executemany('INSERT INTO lgs_fen(konu) VALUES(?)', [('LGS Birinci Konu',)])
    con.executemany('INSERT INTO ozel_fizik(konu) VALUES(?)', [('Elektrik',),('Basınç',)])
    con.execute("INSERT INTO grup_konu_duzen VALUES('ozel_fizik','YKS','12-say','Gruba Özel')")
    con.execute("INSERT INTO ogrenci_konu_duzen VALUES('ozel_fizik',7,'Öğrenciye Özel')")
    con.executemany('INSERT INTO koc_konu_takip(ogrenci_id,ders_adi,konu_adi) VALUES(?,?,?)', [
        (7,'ozel_fizik','Geçmişte Kaldırılmış Konu'),(7,'Eski Fizik','Arşivdeki Konu'),
        (7,'ozel_eski','Pasif Ders Konusu'),(8,'Özel Gizli','Başkasının Notu')
    ])
    con.commit();con.close()
    return path

LEGACY={'(TYT) Matematik':['Klasik TYT'], '(LGS) Fen':['Eski LGS'], 'Matematik (TYT)':[]}
CODES={'tyt_matematik':'(TYT) Matematik','lgs_fen':'(LGS) Fen'}
DEFAULT={'YKS':['tyt_matematik'],'LGS':['lgs_fen']}

def opts(path, sid=7, main='YKS', group='12-say'):
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as c:
        return read_student_coach_subjects(
            c,student_id=sid,main_group=main,sub_group=group,
            legacy_topics=LEGACY,legacy_code_labels=CODES,default_group_lessons=DEFAULT)

def test_assigned_custom_has_immutable_storage_id(database):
    bykey={o.storage_key:o for o in opts(database)}
    assert bykey['ozel_fizik'].title.startswith('İleri Fizik')
    assert bykey['ozel_fizik'].storage_key == 'ozel_fizik'
    assert 'ozel_baska' not in bykey
    assert '(TYT) Matematik' in bykey
    assert '(LGS) Fen' not in bykey

def test_topic_scopes_and_archived_rows_preserved(database):
    bykey={o.storage_key:o for o in opts(database)}
    assert bykey['ozel_fizik'].topics == (
        'Elektrik','Basınç','Gruba Özel','Öğrenciye Özel','Geçmişte Kaldırılmış Konu')
    assert bykey['Eski Fizik'].topics==('Arşivdeki Konu',)
    assert bykey['ozel_eski'].topics==('Pasif Ders Konusu',)

def test_no_cross_student_leakage(database):
    bykey={o.storage_key:o for o in opts(database,sid=9)}
    assert 'ozel_eski' not in bykey
    assert 'Eski Fizik' not in bykey
    assert all('Başkasının Notu' not in o.topics for o in bykey.values())
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as c:
        topics=read_scoped_topics(c,'ozel_fizik',student_id=9,main_group='YKS',sub_group='12-say')
    assert 'Öğrenciye Özel' not in topics

def test_student_lgs_uses_actual_main_group(database):
    bykey={o.storage_key:o for o in opts(database,sid=9,main='LGS',group='8.sınıf')}
    assert '(LGS) Fen' in bykey and '(TYT) Matematik' not in bykey
    assert 'ozel_fizik' not in bykey

def test_rename_does_not_alter_key(database):
    with sqlite3.connect(database) as c:
        c.execute("UPDATE ders_tanimlari SET ad='Fizik Destek Atölyesi' WHERE id='ozel_fizik'")
    bykey={o.storage_key:o for o in opts(database)}
    assert 'Fizik Destek Atölyesi' in bykey['ozel_fizik'].title
    assert bykey['ozel_fizik'].storage_key=='ozel_fizik'

def test_no_sql_identifier_injection(database):
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as c:
        assert read_scoped_topics(c,'ozel_fizik;DROP TABLE ogrenci')==()

def test_readonly_never_modifies_database(database):
    before=hashlib.sha256(database.read_bytes()).hexdigest()
    opts(database)
    assert hashlib.sha256(database.read_bytes()).hexdigest()==before

def test_old_db_without_catalog(tmp_path):
    path=tmp_path/'old.db'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE x(y TEXT)')
    bykey={o.storage_key:o for o in opts(path)}
    assert '(TYT) Matematik' in bykey


def test_code_refreshed_without_changing_homework_files():
    src=(ROOT/'ui'/'coaching_manager.py').read_text(encoding='utf8')
    tree=ast.parse(src)
    assert '_coach_subject_key_v41' in src
    assert 'read_student_coach_subjects' in src
    assert 'btn_refresh_topics.clicked.connect(self._refresh_coach_catalog_v41)' in src
    assert 'self.cmb_topic_subject.addItem(title, key)' in src
    protected=(ROOT/'tests'/'v40_protected_hashes.txt').read_text(encoding='utf8').splitlines()
    for row in protected:
        if row.strip():
            name,digest=row.split(' ',1)
            if name!='ui/coaching_manager.py':
                assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
