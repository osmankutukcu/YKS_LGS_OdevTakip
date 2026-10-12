"""V21 read-only workspace: student identity, status policy and compatibility."""
from datetime import date
from pathlib import Path
import sqlite3
import pytest
from services.student_workspace_v21 import read_control_counts, read_workspace_report


def conn():
    con=sqlite3.connect(':memory:')
    con.executescript('''
      CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER);
      CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,bitis_tarihi TEXT);
      CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,durum TEXT,silindi INTEGER DEFAULT 0,aktarildi INTEGER DEFAULT 0,ders TEXT,konu_ad TEXT);
      CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,durum TEXT,odev_id INTEGER);
      CREATE TABLE denemeler(id INTEGER PRIMARY KEY,tarih TEXT,tur TEXT);
      CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY,deneme_id INTEGER,ogrenci_id INTEGER,ders_adi TEXT,dogru INTEGER,yanlis INTEGER,bos INTEGER,net REAL);
      CREATE TABLE koc_plan(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,baslangic_tarihi TEXT,bitis_tarihi TEXT);
      CREATE TABLE koc_hedef(id INTEGER PRIMARY KEY,plan_id INTEGER);
      CREATE TABLE koc_program(id INTEGER PRIMARY KEY,plan_id INTEGER);
      CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,durum INTEGER);
      INSERT INTO ogrenci VALUES (1,'Örnek','Bir',1),(2,'Örnek','İki',1),(3,'Kapalı','Kayıt',0);
      INSERT INTO odev_kume VALUES (10,1,'2026-10-09'),(20,2,'2026-10-09');
      INSERT INTO odev VALUES (11,10,1,'devam',0,0,'Fizik','Hareket'),(12,10,1,'tamam',0,0,'Fizik','Kuvvet'),
          (13,10,1,'aktarıldı',0,1,'Fizik','Atılan'),(14,10,1,'tanımsız',0,0,'Matematik','Denklem'),
          (15,10,1,'tamam',1,0,'Fizik','Enerji'),(21,20,2,'tamam',0,0,'Türkçe','Paragraf');
      INSERT INTO odev_satir VALUES (4,10,1,'devam',11);
      INSERT INTO koc_konu_takip VALUES (1,1,2);
    ''')
    return con


def test_control_counts_use_primary_records_only():
    with conn() as con:
        count=read_control_counts(con,1)
    assert (count.completed,count.open,count.unknown,count.excluded)==(1,1,1,2)


def test_separate_student_counts_even_with_same_first_name():
    with conn() as con:
        assert read_control_counts(con,2).completed==1
        assert read_control_counts(con,2).open==0
        assert read_control_counts(con,1).completed==1


def test_full_overview_not_confused_with_shadow_records():
    with conn() as con:
        r=read_workspace_report(con,1,as_of=date(2026,10,12))
    assert r.student.student_id==1
    assert r.student.student_name=='Örnek Bir'
    assert r.control.unknown==1
    assert len(r.recent_control)==3  # Deleted/transferred records excluded
    assert r.recent_control[0].topic=='Denklem'
    assert any('belirsiz' in msg.lower() for msg in r.notes)


def test_other_student_not_exposed():
    with conn() as con:
        r=read_workspace_report(con,2,as_of=date(2026,10,12))
    assert r.student.student_id==2
    assert r.student.student_name=='Örnek İki'
    assert r.control.open==0
    assert r.student.homework_uncertainty==0


@pytest.mark.parametrize('sid',[0,-1,True,'1',1.0,None])
def test_invalid_id_rejected(sid):
    with conn() as con:
        with pytest.raises(ValueError):
            read_workspace_report(con,sid)


def test_inactive_student_rejected():
    with conn() as con:
        with pytest.raises(ValueError):
            read_workspace_report(con,3)


def test_missing_student_rejected():
    with conn() as con:
        with pytest.raises(ValueError):
            read_workspace_report(con,999)


def test_query_only_does_not_mutate_db():
    with conn() as con:
        original=con.total_changes
        con.execute('PRAGMA query_only=ON')
        read_workspace_report(con,1,as_of=date(2026,10,12))
        assert con.total_changes==original


def test_read_control_missing_columns_fails_closed():
    con=sqlite3.connect(':memory:')
    con.execute('CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER)')
    with pytest.raises(ValueError):
        read_control_counts(con,1)
    con.close()


def test_compatibility_original_form_paths_stay_intact():
    path=Path(__file__).resolve().parents[1]/'ui/homework_form.py'
    text=path.read_text(encoding='utf-8')
    assert 'HomeworkWorkspaceBridgeV21(self, mid_split, bottom)' in text
    assert 'self.btnKaydet.clicked.connect(self._kaydet_kume)' in text
    assert 'self.btnKontrol.clicked.connect(self._odev_kontrol)' in text
    assert 'self._workspace_v21.selection_changed()' in text


def test_bridge_calls_legacy_control_not_new_writer():
    path=Path(__file__).resolve().parents[1]/'ui/homework_workspace_bridge_v21.py'
    text=path.read_text(encoding='utf-8')
    assert 'self.form.btnKontrol.click()' in text
    assert 'sqlite3.connect' not in text
