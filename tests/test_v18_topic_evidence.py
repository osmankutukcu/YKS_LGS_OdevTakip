"""V18 topic/lesson evidence is read-only, per-student, never a diagnosis."""
from datetime import date
import sqlite3
import pytest
from services.topic_evidence_v18 import read_topic_evidence


def make_db():
    c=sqlite3.connect(':memory:')
    c.executescript('''
       CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER);
       INSERT INTO ogrenci VALUES(1,'Örnek','Bir',1),(2,'Örnek','İki',1),(3,'Pasif','Üç',0);
       CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER, bitis_tarihi TEXT);
       INSERT INTO odev_kume VALUES(10,1,'2026-10-10'),(11,2,'2026-10-10'),(12,1,'2026-10-10');
       CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER,ogrenci_id INTEGER, ders TEXT, konu_ad TEXT, durum TEXT);
       INSERT INTO odev VALUES(1,10,1,'Fizik','Elektrostatik','devam'),
                              (2,11,2,'Fizik','Elektrostatik','tamam');
       CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER, ders TEXT, konu TEXT, durum TEXT);
       INSERT INTO odev_satir VALUES(1,10,1,'Fizik','Elektrostatik','devam'),
                                    (2,12,1,'Fizik','Basınç','tamam'),
                                    (3,11,1,'Fizik','Dalga','tamam');
       CREATE TABLE odev_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum TEXT);
       INSERT INTO odev_takip VALUES(1,1,'Fizik','Elektrostatik','Tamamlandı'),
                                    (2,2,'Fizik','Optik','Aktif');
       CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum INTEGER,hakimiyet_puani INTEGER,koc_notu TEXT);
       INSERT INTO koc_konu_takip VALUES(1,1,'Fizik','Elektrostatik',2,100,'Öğretmen işareti'),
                                        (2,2,'Fizik','Optik',2,100,'Karışmamalı');
       CREATE TABLE denemeler(id INTEGER PRIMARY KEY,tarih TEXT,tur TEXT);
       CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY,deneme_id INTEGER,ogrenci_id INTEGER,ders_adi TEXT,dogru INTEGER,yanlis INTEGER,bos INTEGER,net REAL);
       INSERT INTO denemeler VALUES(5,'2026-10-08','TYT');
       INSERT INTO deneme_sonuclari VALUES(1,5,1,'Fizik',4,2,1,3.5),(2,5,2,'Fizik',1,4,2,0.0);
    ''')
    return c


def topic(report, text):
    return next(t for t in report.topics if t.topic == text)


def test_student_protected():
    c=make_db()
    r=read_topic_evidence(c,1,as_of=date(2026,10,12))
    assert r.student_name == 'Örnek Bir'
    assert all(t.topic != 'Optik' for t in r.topics)
    assert topic(r,'Elektrostatik').teacher_note == 'Öğretmen işareti'
    assert topic(r,'Basınç').main_done == 1
    assert all(t.topic != 'Dalga' for t in r.topics)


def test_double_source_counted_once_with_warning():
    r=read_topic_evidence(make_db(),1,as_of=date(2026,10,12))
    t=topic(r,'Elektrostatik')
    assert t.main_open == 1 and t.main_done == 0
    assert t.map_done == 1 and t.map_open == 0
    assert any('ayrıca sayılmadı' in w for w in r.warnings)


def test_exam_only_course_not_topic():
    r=read_topic_evidence(make_db(),1,as_of=date(2026,10,12))
    assert len(r.exam_context) == 1
    assert r.exam_context[0].lesson == 'Fizik'
    assert 'net' in r.exam_context[0].latest
    assert 'ölç' in topic(r,'Elektrostatik').recommendation or 'Açık çalışma' in topic(r,'Elektrostatik').recommendation
    assert 'net' not in topic(r,'Elektrostatik').recommendation


def test_invalid_student_does_not_fallback():
    c=make_db()
    for sid in (0,999,3,'1',None,-1):
        with pytest.raises(ValueError): read_topic_evidence(c,sid)


def test_no_database_write():
    c=make_db()
    c.execute('PRAGMA query_only=ON')
    before=c.total_changes
    r=read_topic_evidence(c,1)
    assert r.topics and c.total_changes == before


def test_missing_optional_tables():
    c=sqlite3.connect(':memory:')
    c.execute('CREATE TABLE ogrenci(id INTEGER,ad TEXT,soyad TEXT)')
    c.execute("INSERT INTO ogrenci VALUES(1,'Test','Kişi')")
    r=read_topic_evidence(c,1)
    assert not r.topics and not r.exam_context


def test_exact_topic_not_partial_match():
    c=make_db()
    c.execute("INSERT INTO odev_takip VALUES(3,1,'Fizik','Elektrostatik Ek','Aktif')")
    r=read_topic_evidence(c,1)
    assert topic(r,'Elektrostatik Ek').map_open == 1
    assert topic(r,'Elektrostatik').map_open == 0


def test_duplicate_teacher_marks_not_fake_mastery():
    c=make_db()
    c.execute("INSERT INTO koc_konu_takip VALUES(3,1,'Fizik','Elektrostatik',0,0,'çelişki')")
    r=read_topic_evidence(c,1)
    t=topic(r,'Elektrostatik')
    assert t.teacher_state is None and t.teacher_score is None and t.duplicate_teacher_records == 1
    assert 'belirsiz' not in t.recommendation.lower() or t.source_warning


def test_course_exam_does_not_create_topic():
    c=make_db()
    c.execute('DELETE FROM odev WHERE ogrenci_id=1')
    c.execute('DELETE FROM odev_satir WHERE ogrenci_id=1')
    c.execute('DELETE FROM odev_takip WHERE ogrenci_id=1')
    c.execute('DELETE FROM koc_konu_takip WHERE ogrenci_id=1')
    r=read_topic_evidence(c,1,as_of=date(2026,10,12))
    assert r.topics == () and len(r.exam_context) == 1


def test_ignored_cancelled_homework_and_unknown_status():
    c=make_db()
    c.execute("INSERT INTO odev_takip VALUES(5,1,'Fizik','Basınç','iptal')")
    c.execute("INSERT INTO odev_takip VALUES(6,1,'Fizik','Basınç','garip')")
    r=read_topic_evidence(c,1)
    t=topic(r,'Basınç')
    assert t.map_open == 0 and t.map_done == 0 and t.source_warning


def test_report_text_explains_limitations():
    t=read_topic_evidence(make_db(),1)
    text=t.explain()
    assert 'öğrenildiğini kanıtlamaz' in text
    assert 'konuya otomatik bağlanamaz' in text


def test_ui_is_connected_in_both_locations():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'ui'
    assert "self.btn_topic_evidence_v18.clicked.connect" in (root/'topic_map_dialog.py').read_text()
    assert 'self.btn_topic_evidence.clicked.connect' in (root/'student360_panel_v16.py').read_text()
