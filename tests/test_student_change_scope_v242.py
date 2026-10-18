import sqlite3, pytest
from services.student_change_scope_v242 import (
    student_snapshot, StudentChangeRouter, ScopeNotReliable, StudentDataChange)

@pytest.fixture
def db():
    con=sqlite3.connect(':memory:')
    con.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,ders TEXT,konu_ad TEXT,durum TEXT);
        CREATE TABLE odev_takip(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum TEXT);
        CREATE TABLE koc_plan(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,notlar TEXT);
        CREATE TABLE koc_hedef(id INTEGER PRIMARY KEY,plan_id INTEGER,ders_adi TEXT,hedef_soru INTEGER);
        CREATE TABLE koc_program(id INTEGER PRIMARY KEY,plan_id INTEGER,gun TEXT,icerik TEXT);
        CREATE TABLE deneme(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,tarih TEXT);
        CREATE TABLE deneme_sonuc(id INTEGER PRIMARY KEY,deneme_id INTEGER,ders TEXT,net FLOAT);
        CREATE TABLE unrelated(rowid INTEGER PRIMARY KEY, text TEXT);
        INSERT INTO ogrenci VALUES(1,'Student','A'),(2,'Student','B');
        INSERT INTO koc_plan VALUES(11,1,'Plan 1'),(22,2,'Plan 2');
        INSERT INTO deneme VALUES(31,1,'2026-01-01'),(32,2,'2026-01-02');
    ''')
    yield con
    con.close()

def test_student_isolation(db):
    router=StudentChangeRouter()
    router.baseline(db,1);router.baseline(db,2)
    db.execute("INSERT INTO odev VALUES(1,1,'LGS Matematik','Uslu Sayilar','devam')")
    r=router.after_commit(db,[1,2])
    assert r=={1:StudentDataChange(1,('homework',))}
    assert router.after_commit(db,[1,2])=={}

def test_single_student_selection_and_ignored_table(db):
    router=StudentChangeRouter()
    router.baseline(db,1)
    db.execute("INSERT INTO unrelated(text) VALUES('not student evidence')")
    assert router.after_commit(db,[1])=={}
    db.execute("INSERT INTO odev VALUES(9,2,'LGS Matematik','Olasilik','devam')")
    assert router.after_commit(db,[1])=={}
    assert router.after_commit(db,[2])=={2:StudentDataChange(2,('unknown',),True)}

def test_changed_status_without_timestamp(db):
    db.execute("INSERT INTO odev VALUES(1,1,'math','topics','devam')")
    router=StudentChangeRouter();router.baseline(db,1)
    db.execute("UPDATE odev SET durum='tamam' WHERE id=1")
    assert router.after_commit(db,[1])[1].kinds==('homework',)
    db.execute('DELETE FROM odev WHERE id=1')
    assert router.after_commit(db,[1])[1].kinds==('homework',)

def test_micro_homework_and_coaching_categories(db):
    router=StudentChangeRouter();router.baseline(db,1)
    db.execute("INSERT INTO odev_takip VALUES(9,1,'LGS Matematik','Uslu Sayilar','Aktif')")
    db.execute("INSERT INTO koc_hedef VALUES(4,11,'LGS Matematik',30)")
    assert router.after_commit(db,[1])[1].kinds==('coaching','topic_map')
    db.execute('UPDATE koc_hedef SET hedef_soru=50 WHERE id=4')
    assert router.after_commit(db,[1])[1].kinds==('coaching',)

def test_indirect_plan_and_exam_scopes(db):
    router=StudentChangeRouter();router.baseline(db,1);router.baseline(db,2)
    db.execute("INSERT INTO koc_program VALUES(4,22,'Monday','changed')")
    db.execute("INSERT INTO deneme_sonuc VALUES(5,32,'Math',10.2)")
    assert router.after_commit(db,[1,2])=={2:StudentDataChange(2,('coaching','exam'))}

def test_student_profile_changes(db):
    router=StudentChangeRouter();router.baseline(db,1)
    db.execute("UPDATE ogrenci SET ad='Updated' WHERE id=1")
    assert router.after_commit(db,[1])[1].kinds==('student',)

def test_source_limit_is_fail_open(db):
    import services.student_change_scope_v242 as mod
    router=StudentChangeRouter();router.baseline(db,1)
    for i in range(mod.MAX_ROWS_PER_SOURCE+1):
        db.execute('INSERT INTO odev(id,ogrenci_id,ders,konu_ad,durum) VALUES(?,?,?, ?,?)',
                   (i+1,1,'m','t','open'))
    changed=router.after_commit(db,[1])
    assert changed[1].uncertain and changed[1].kinds==('unknown',)
    assert 1 not in router._baseline

def test_bad_student_ids(db):
    for sid in (0,-1,True,1.0,'1'):
        with pytest.raises(ValueError):student_snapshot(db,sid)
    assert StudentChangeRouter().after_commit(db,[None,-1,True])=={}

def test_missing_student_owner_column_is_uncertain(db):
    db.execute('DROP TABLE odev')
    db.execute('CREATE TABLE odev(id INTEGER)')
    router=StudentChangeRouter()
    assert router.after_commit(db,[1])[1].uncertain is True

def test_snapshot_order_is_immaterial(db):
    db.execute("INSERT INTO odev VALUES(1,1,'math','a','devam')")
    db.execute("INSERT INTO odev VALUES(2,1,'math','b','tamam')")
    old=student_snapshot(db,1)
    db.execute('DELETE FROM odev')
    db.execute("INSERT INTO odev VALUES(2,1,'math','b','tamam')")
    db.execute("INSERT INTO odev VALUES(1,1,'math','a','devam')")
    assert old==student_snapshot(db,1)

def test_no_new_ddl_or_write_code_in_snapshot_module():
    import inspect,services.student_change_scope_v242 as s
    txt=inspect.getsource(s)
    assert 'CREATE TABLE' not in txt and 'CREATE TRIGGER' not in txt
    assert 'commit()' not in txt
