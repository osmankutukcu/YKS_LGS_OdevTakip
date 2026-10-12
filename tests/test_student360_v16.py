"""V16 module-level tests: no Qt or user database necessary."""
from datetime import date
from pathlib import Path
import sqlite3
import pytest

from services.student360_v16.reader import read_student_overview
from services.student360_v16.advisor import suggestions
from services.student360_v16.profile import student_routine_status


def connection():
    con = sqlite3.connect(':memory:')
    con.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,bitis_tarihi TEXT);
        CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,durum TEXT);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,durum TEXT,odev_id INTEGER);
        CREATE TABLE denemeler(id INTEGER PRIMARY KEY,tarih TEXT,tur TEXT);
        CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY,deneme_id INTEGER,ogrenci_id INTEGER,ders_adi TEXT,dogru INTEGER,yanlis INTEGER,bos INTEGER,net REAL);
        CREATE TABLE koc_plan(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,baslangic_tarihi TEXT,bitis_tarihi TEXT);
        CREATE TABLE koc_hedef(id INTEGER PRIMARY KEY,plan_id INTEGER);
        CREATE TABLE koc_program(id INTEGER PRIMARY KEY,plan_id INTEGER);
        CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,durum INTEGER);
        INSERT INTO ogrenci VALUES (1,'Deniz','Örnek',1),(2,'Ece','Test',1),(3,'Pasif','Öğrenci',0);
        INSERT INTO odev_kume VALUES (10,1,'2026-10-10'),(20,2,'2026-10-10');
        INSERT INTO odev VALUES (100,10,1,'devam'),(200,20,2,'tamam');
        INSERT INTO odev_satir VALUES (1,10,1,'devam',100);
        INSERT INTO denemeler VALUES (1,'2026-10-05','TYT'),(2,'2026-10-09','TYT');
        INSERT INTO deneme_sonuclari VALUES (1,1,1,'Matematik',10,10,20,7.5);
        INSERT INTO deneme_sonuclari VALUES (2,2,1,'Matematik',12,8,20,10);
        INSERT INTO koc_plan VALUES (1,1,'2026-10-05','2026-10-11');
        INSERT INTO koc_hedef VALUES (1,1);
        INSERT INTO koc_program VALUES (1,1);
        INSERT INTO koc_konu_takip VALUES (1,1,'Matematik',2),(2,2,'Fen',2);
    ''')
    return con


def test_selected_student_only():
    with connection() as con:
        a = read_student_overview(con,1,as_of=date(2026,10,10))
        b = read_student_overview(con,2,as_of=date(2026,10,10))
    assert a.student_name == 'Deniz Örnek'
    assert a.homework_overdue == 0  # Due today, not overdue
    assert a.homework_sample == 1
    assert b.homework_sample == 1
    assert b.exam_evidence == 'Yok'
    assert b.coaching_goals == 0
    assert b.tracked_topics == 1
    assert a.tracked_topics == 1


def test_overdue_is_only_old_open_assignment():
    with connection() as con:
        a = read_student_overview(con,1,as_of=date(2026,10,12))
    assert a.homework_overdue == 1
    assert a.homework_sample == 1
    assert a.homework_uncertainty == 1  # odev_satir is shadow, not double counted
    assert 'Denetim' in suggestions(a)[0]


def test_coach_goals_week_scoped():
    with connection() as con:
        inside = read_student_overview(con,1,as_of=date(2026,10,10))
        outside = read_student_overview(con,1,as_of=date(2026,10,12))
    assert inside.coaching_goals == 1 and inside.coaching_program_entries == 1
    assert outside.coaching_goals == 0
    assert 'planı kayıtlı değil' in outside.coaching_plan


def test_exam_comparison_is_limited_not_mastery():
    with connection() as con:
        d = read_student_overview(con,1,as_of=date(2026,10,12))
    assert d.exam_evidence == 'Sınırlı karşılaştırma'
    assert '7.5' in d.exam_summary
    assert '10' in d.exam_summary
    assert 'güçlüğünün eşitliği doğrulanmadı' in d.exam_explanation


def test_missing_inactive_or_bad_id_refused():
    with connection() as con:
        for sid in (3, 999, 0, -1, True, '1'):
            with pytest.raises(ValueError):
                read_student_overview(con,sid)


def test_reader_makes_no_writes_even_when_query_only():
    with connection() as con:
        before=con.total_changes
        con.execute('PRAGMA query_only=ON')
        read_student_overview(con,1,as_of=date(2026,10,12))
        assert con.total_changes==before


def test_profile_absence_does_not_create_anything(monkeypatch):
    import services.student360_v16.profile as mod
    monkeypatch.setattr(mod,'load_assignments',lambda: {})
    assert 'eşleştirilmemiş' in mod.student_routine_status(1)
    monkeypatch.setattr(mod,'load_assignments',lambda: {'1':'ABC'})
    monkeypatch.setattr(mod,'load_profiles',lambda: {})
    assert 'bulunamıyor' in mod.student_routine_status(1)
    monkeypatch.setattr(mod,'load_profiles',lambda: {'ABC':{}})
    assert 'eşleştirilmiş' in mod.student_routine_status(1)


def test_no_homework_does_not_imply_poor_achievement():
    with connection() as con:
        con.execute('DELETE FROM odev WHERE ogrenci_id=2')
        row=read_student_overview(con,2,as_of=date(2026,10,12))
    assert row.homework_sample == 0
    assert any('Çalışılmadığı sonucuna varmayın' in x for x in suggestions(row))
