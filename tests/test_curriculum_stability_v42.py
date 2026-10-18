"""V42 read-only and source-protection acceptance tests, using invented student data."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import pytest

from services.curriculum_stability_v42 import (
    inspect_student_contract, source_integrity, to_public_report, PROTECTED_RELATIVE,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT/'tests'/'v42_protected_hashes.json').read_text(encoding='utf-8'))


@pytest.fixture
def pilot(tmp_path):
    p = tmp_path/'invented_pilot.sqlite'
    with sqlite3.connect(p) as c:
        c.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,ana_grup TEXT,alt_grup TEXT);
        CREATE TABLE ders_tanimlari(id TEXT PRIMARY KEY,ad TEXT,grup TEXT,aktif INT,ozel INT,siralama INT);
        CREATE TABLE grup_dersleri(grup_adi TEXT,ders_id TEXT);
        CREATE TABLE ozel_ek(id INTEGER PRIMARY KEY, konu TEXT);
        CREATE TABLE grup_konu_duzen(ders TEXT,ana_grup TEXT,alt_grup TEXT,konu TEXT);
        CREATE TABLE ogrenci_konu_duzen(ders TEXT,ogrenci_id INTEGER,konu TEXT);
        CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT);
        CREATE TABLE koc_kitaplar(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT);
        CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INT, ders TEXT);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INT,ders TEXT);
        CREATE TABLE ogrenci_kitap(id INTEGER PRIMARY KEY,ogrenci_id INT, ders TEXT);
        CREATE TABLE odev_takip(id INTEGER PRIMARY KEY,ogrenci_id INT,ders_adi TEXT);
        CREATE TABLE kapsam_odev_v233(id INTEGER PRIMARY KEY,ogrenci_id INT,ders TEXT);
        ''')
        c.executemany('INSERT INTO ogrenci VALUES(?,?,?,?)', [
            (1,'TEST A','YKS','12-say'), (2,'TEST B','YKS','11-say'),
        ])
        c.executemany('INSERT INTO ders_tanimlari VALUES (?,?,?,?,?,?)', [
            ('tyt_matematik','TYT Matematik','YKS',1,0,1),
            ('ozel_ek','İleri Fizik','YKS',1,1,2),
            ('ozel_eski','Arşiv','YKS',0,1,3),
        ])
        c.executemany('INSERT INTO grup_dersleri VALUES(?,?)', [
            ('12-say','tyt_matematik'),('12-say','ozel_ek'),
            ('12-say','ozel_eski'),('11-say','tyt_matematik')
        ])
        c.execute("INSERT INTO ozel_ek(konu) VALUES ('Basınç')")
        c.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi,konu_adi) VALUES(1,'Bilinmeyen Öğretmen Dersi','Dönüşüm')")
        c.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi,konu_adi) VALUES(2,'Kişisel Diğer','Gizli')")
        c.execute("INSERT INTO odev(ogrenci_id,ders) VALUES(1,'ozel_eski')")
        c.execute("INSERT INTO ogrenci_kitap(ogrenci_id,ders) VALUES(1,'ozel_ek')")
    return p


def test_v41_immutable_source_hashes_unchanged():
    assert not source_integrity(ROOT, BASELINE)
    assert len(BASELINE) == len(PROTECTED_RELATIVE)


def test_protected_change_rejected(tmp_path):
    (tmp_path/'ui').mkdir()
    (tmp_path/'ui'/'homework_form.py').write_text('changed', encoding='utf-8')
    alerts = source_integrity(tmp_path, BASELINE)
    assert any(x.code=='PROTECTED_SOURCE_CHANGED' for x in alerts)
    assert any('ui/homework_form.py' in x.message for x in alerts)


def test_curriculum_coaching_book_and_homework_crosscheck(pilot):
    before=hashlib.sha256(pilot.read_bytes()).hexdigest()
    result=inspect_student_contract(pilot,student_id=1,db_source=ROOT/'db.py')
    assert hashlib.sha256(pilot.read_bytes()).hexdigest()==before
    assert result.assignment_mode=='Gruba özel'
    assert set(result.active_lessons)=={'tyt_matematik','ozel_ek'}
    assert result.assigned_custom_lessons==('ozel_ek',)
    assert result.coaching_custom_lessons==('ozel_ek',)
    assert dict(result.student_source_counts)['odev']==1
    assert dict(result.student_source_counts)['ogrenci_kitap']==1
    assert any(x.code=='INACTIVE_ASSIGNMENT' for x in result.findings)
    assert any(x.code=='UNRESOLVED_COACH_LABEL' for x in result.findings)
    assert not [x for x in result.findings if x.severity=='ERROR']


def test_active_custom_with_prior_coaching_history_still_counted(pilot):
    with sqlite3.connect(pilot) as c:
        c.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi,konu_adi) VALUES(1,'ozel_ek','Basınç')")
    c=inspect_student_contract(pilot,student_id=1,db_source=ROOT/'db.py')
    assert c.coaching_custom_lessons==('ozel_ek',)
    assert not any(f.code=='CUSTOM_COURSE_MISSING_IN_COACHING' for f in c.findings)


def test_older_history_not_confused_with_current_lessons(pilot):
    c=inspect_student_contract(pilot,student_id=2,db_source=ROOT/'db.py')
    assert 'ozel_ek' not in c.coaching_custom_lessons
    assert c.assigned_custom_lessons==()
    assert dict(c.student_source_counts)['odev']==0
    assert c.assignment_mode=='Gruba özel'


def test_unknown_group_mapping_is_flagged(pilot):
    with sqlite3.connect(pilot) as c:
        c.execute("INSERT INTO grup_dersleri VALUES('12-say','kayip_ders')")
    c=inspect_student_contract(pilot,student_id=1,db_source=ROOT/'db.py')
    assert any(f.code=='UNKNOWN_ASSIGNED_LESSON' for f in c.findings)
    assert 'kayip_ders' not in c.active_lessons


def test_group_collision_is_review_only(pilot):
    with sqlite3.connect(pilot) as c:
        c.execute("INSERT INTO ogrenci VALUES(3,'TEST C','LGS','12-say')")
    c=inspect_student_contract(pilot,student_id=1,db_source=ROOT/'db.py')
    assert any(f.code=='GROUP_NAME_COLLISION' and f.severity=='REVIEW' for f in c.findings)


def test_missing_file_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_student_contract(tmp_path/'missing.sqlite',student_id=1,db_source=ROOT/'db.py')
    assert not (tmp_path/'missing.sqlite').exists()


@pytest.mark.parametrize('bad',[0,-1,True,'1',None])
def test_invalid_student_identity_rejected(pilot,bad):
    with pytest.raises(ValueError):
        inspect_student_contract(pilot,student_id=bad,db_source=ROOT/'db.py')


def test_no_student_personal_details_in_export(pilot):
    c=inspect_student_contract(pilot,student_id=1,db_source=ROOT/'db.py')
    public=json.dumps(to_public_report(c),ensure_ascii=False)
    assert 'TEST A' not in public and 'TEST B' not in public
    assert '12-say' not in public
    assert 'Bilinmeyen Öğretmen Dersi' not in public
    assert 'student_id' not in public
    assert to_public_report(c)['desktop_ui_accepted'] is False


def test_missing_coaching_table_is_visible_not_auto_fixed(tmp_path):
    db=tmp_path/'old.sqlite'
    with sqlite3.connect(db) as c:
        c.executescript('''
        CREATE TABLE ogrenci(id INT PRIMARY KEY,ana_grup TEXT,alt_grup TEXT);
        CREATE TABLE ders_tanimlari(id TEXT PRIMARY KEY,ad TEXT,aktif INT,ozel INT,siralama INT);
        INSERT INTO ogrenci VALUES(1,'YKS','12-ea');
        INSERT INTO ders_tanimlari VALUES('tyt_matematik','TYT Matematik',1,0,1);
        ''')
    res=inspect_student_contract(db,student_id=1,db_source=ROOT/'db.py')
    assert any(x.code=='COACH_SOURCE_ABSENT' for x in res.findings)
    with sqlite3.connect(db) as c:
        assert not c.execute("SELECT name FROM sqlite_master WHERE name='koc_konu_takip'").fetchone()
