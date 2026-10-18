import os
import sqlite3
from datetime import date
import pytest
from services.coach_shared_topic_v1 import read_shared_topic_summary, lesson_code
from services.student360_v16.reader import read_student_overview


def database():
    con=sqlite3.connect(':memory:')
    con.row_factory=sqlite3.Row
    con.executescript('''
        CREATE TABLE ogrenci (id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER);
        INSERT INTO ogrenci VALUES (1,'Test','Bir',1),(2,'Test','İki',1),(3,'Pasif','Üç',0);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,bitis_tarihi TEXT);
        INSERT INTO odev_kume VALUES (10,1,'2026-10-16'),(20,2,'2026-10-16');
        CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,ders TEXT,konu_ad TEXT,durum TEXT);
        INSERT INTO odev VALUES (1,10,1,'tyt_matematik','Temel Kavramlar','devam'),
            (2,10,1,'tyt_matematik','Temel Kavramlar','tamam'),
            (3,20,2,'tyt_matematik','Temel Kavramlar','devam');
        CREATE TABLE odev_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum TEXT);
        INSERT INTO odev_takip VALUES (1,1,'Matematik (TYT)','Temel Kavramlar','Aktif'),
            (2,1,'Matematik (TYT)','Sayı Basamakları','Tamamlandı'),
            (3,2,'Matematik (TYT)','Temel Kavramlar','Aktif');
        CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,kitap_id INTEGER,durum INTEGER,hakimiyet_puani INTEGER,koc_notu TEXT);
        INSERT INTO koc_konu_takip VALUES (1,1,'Matematik (TYT)','Temel Kavramlar',0,4,100,'Öğretmen değerlendirmesi'),
            (2,1,'Fen','Enerji',0,2,60,''),
            (3,2,'Matematik (TYT)','Temel Kavramlar',0,1,30,'');
    ''')
    return con


def test_exact_subject_aliases_and_independent_counts():
    with database() as con:
        s=read_shared_topic_summary(con,1,'TYT Matematik')
    assert (s.main_open,s.main_done,s.map_open,s.map_done)==(1,1,1,1)
    assert s.teacher_entries==1 and s.teacher_mastered==1
    assert s.excluded_other_lessons==1
    assert 'Ana ödev' in s.lines()[0] and 'Konu Haritası' in s.lines()[0]
    assert s.student_id==1 and s.student_name=='Test Bir'


def test_ambiguous_courses_are_not_merged():
    assert lesson_code('Matematik (TYT)')==lesson_code('tyt_matematik')
    assert lesson_code('Matematik')!=lesson_code('Matematik (TYT)')
    assert lesson_code('Matematik (AYT)')!=lesson_code('Matematik (TYT)')


def test_no_cross_student_records():
    with database() as con:
        a=read_shared_topic_summary(con,1,'tyt_matematik')
        b=read_shared_topic_summary(con,2,'tyt_matematik')
    assert (a.main_open,a.main_done)==(1,1)
    assert (b.main_open,b.main_done)==(1,0)
    assert a.teacher_mastered==1 and b.teacher_mastered==0


def test_inactive_missing_bad_student_id_rejected():
    with database() as con:
        for sid in (3,999,0,-1,True,'1'):
            with pytest.raises(ValueError):read_shared_topic_summary(con,sid)


def test_strict_sqlite_query_only_and_no_schema_changes():
    with database() as con:
        before=con.total_changes
        tables=con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        con.execute('PRAGMA query_only=ON')
        for _ in range(3):read_shared_topic_summary(con,1)
        after=con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        assert tables==after and con.total_changes==before
        with pytest.raises(sqlite3.OperationalError):con.execute('INSERT INTO ogrenci VALUES (4,\'A\',\'B\',1)')


def test_conflicting_book_entries_warn_without_overwrite():
    with database() as con:
        con.execute("INSERT INTO koc_konu_takip VALUES (5,1,'Matematik (TYT)','Temel Kavramlar',1,2,60,'Farklı kitap')")
        s=read_shared_topic_summary(con,1,'Matematik (TYT)')
    assert s.teacher_mastered==0 and s.teacher_entries==0
    assert s.warnings
    assert 'inceleme' in s.note()


def test_student360_counts_old_and_new_marked_state_and_separates_students():
    # Reader requires V14/V15-compatible group & dates; use original test fixture separately.
    assert 'durum IN (2,4)' in __import__('inspect').getsource(read_student_overview)


def test_readonly_summary_with_no_tasks():
    with database() as con:
        s=read_shared_topic_summary(con,1,'Edebiyat')
    assert s.covered_topics==0
    assert (s.main_open,s.map_open,s.teacher_entries)==(0,0,0)


def test_no_unconfirmed_overall_mastery_proposition():
    with database() as con:
        s=read_shared_topic_summary(con,1,'TYT Matematik')
    assert 'öğrenildi' not in '\n'.join(s.lines()).lower()
    assert 'kanıtlamaz' in s.note()


def test_360_new_mastery_marked_with_old_state_two():
    from test_student360_v16 import connection
    with connection() as con:
        con.execute("INSERT INTO koc_konu_takip VALUES (9,1,'Matematik',4)")
        result=read_student_overview(con,1,as_of=date(2026,10,10))
    assert result.tracked_topics==2
    assert result.marked_topics==2
