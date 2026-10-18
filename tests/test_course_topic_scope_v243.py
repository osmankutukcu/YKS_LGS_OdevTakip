import sqlite3
from services.student_change_scope_v242 import StudentChangeRouter, StudentDataChange
from services.course_topic_scope_v243 import CourseTopicScope, course_key


def db():
    c=sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT,konu_ad TEXT,durum TEXT);
        CREATE TABLE odev_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum TEXT);
        CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum INT);
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders TEXT,konu TEXT,durum TEXT);
        CREATE TABLE koc_kitaplar(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,kitap_adi TEXT);
        CREATE TABLE koc_plan(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,icerik TEXT);
    ''')
    return c


def baseline(c,sid=1,subject='LGS Matematik'):
    a=StudentChangeRouter();b=CourseTopicScope()
    a.baseline(c,sid);b.baseline(c,sid,subject)
    return a,b


def decide(c,a,b,sid=1,subject='LGS Matematik'):
    event=a.after_commit(c,[sid])[sid]
    return b.on_commit(c,event,subject)


def test_aliases_are_exam_level_safe():
    assert course_key('lgs_matematik')==course_key('LGS Matematik')
    assert course_key('Matematik (TYT)')==course_key('TYT_MATEMATİK')
    assert course_key('LGS Matematik')!=course_key('TYT Matematik')
    assert course_key('')==''


def test_unrelated_course_is_skipped_and_correct_one_refreshes():
    c=db();a,b=baseline(c)
    c.execute("INSERT INTO odev VALUES(1,1,'TYT Matematik','Kümeler','devam')")
    assert decide(c,a,b).refresh is False
    c.execute("INSERT INTO odev VALUES(2,1,'LGS Matematik','Üslü Sayılar','devam')")
    d=decide(c,a,b)
    assert d.refresh and d.changed_topics==('üslü sayılar',) and not d.uncertain
    c.execute("UPDATE odev SET durum='tamam' WHERE id=2")
    assert decide(c,a,b).changed_topics==('üslü sayılar',)
    c.execute("DELETE FROM odev WHERE id=2")
    assert decide(c,a,b).changed_topics==('üslü sayılar',)
    c.close()


def test_changed_topic_move_refreshes_relevant_subjects():
    c=db()
    c.execute("INSERT INTO odev VALUES(1,1,'LGS Matematik','Eşitsizlikler','devam')")
    a=StudentChangeRouter();b=CourseTopicScope()
    a.baseline(c,1);b.baseline(c,1,'LGS Matematik');b.baseline(c,1,'LGS Fen')
    c.execute("UPDATE odev SET ders='LGS Fen', konu_ad='Basınç' WHERE id=1")
    ev=a.after_commit(c,[1])[1]
    assert b.on_commit(c,ev,'LGS Matematik').changed_topics==('eşitsizlikler',)
    assert b.on_commit(c,ev,'LGS Fen').changed_topics==('basınç',)
    c.close()


def test_course_book_change_has_no_topic_precision():
    c=db();a,b=baseline(c)
    c.execute("INSERT INTO koc_kitaplar VALUES(1,1,'LGS Matematik','Kitap X')")
    d=decide(c,a,b)
    assert d.refresh and d.uncertain and d.changed_topics==()
    c.close()


def test_microhomework_and_coaching_refresh():
    c=db();a,b=baseline(c)
    c.execute("INSERT INTO odev_takip VALUES(1,1,'LGS Matematik','Oran','devam')")
    assert decide(c,a,b).changed_topics==('oran',)
    c.execute("INSERT INTO koc_konu_takip VALUES(1,1,'LGS Matematik','Oran',4)")
    assert decide(c,a,b).changed_topics==('oran',)
    c.close()


def test_unscoped_student_record_fails_open():
    c=db();a,b=baseline(c)
    c.execute("INSERT INTO koc_plan VALUES(1,1,'plan')")
    d=decide(c,a,b)
    assert d.refresh and d.uncertain and d.changed_topics==()
    c.close()


def test_first_use_and_missing_course_must_refresh():
    c=db();b=CourseTopicScope()
    ev=StudentDataChange(1,('homework',),False,('odev',))
    assert b.on_commit(c,ev,'LGS Matematik').refresh
    assert b.on_commit(c,ev,'').refresh
    assert b.on_commit(c,StudentDataChange(1,('unknown',),True),'LGS Matematik').refresh
    c.close()


def test_missing_column_and_oversized_source_fallback():
    c=db();a,b=baseline(c)
    c.execute("DROP TABLE odev_takip")
    c.execute("CREATE TABLE odev_takip(ogrenci_id INTEGER,ders_adi TEXT)")
    c.execute("INSERT INTO odev_takip VALUES(1,'LGS Matematik')")
    d=decide(c,a,b)
    assert d.refresh and d.uncertain
    c.close()
    c=db();a,b=baseline(c)
    from services.course_topic_scope_v243 import MAX_ROWS_PER_TABLE
    c.executemany("INSERT INTO odev VALUES(?,?, 'LGS Matematik','Konu','devam')",
                  [(i,1) for i in range(MAX_ROWS_PER_TABLE+1)])
    d=decide(c,a,b)
    assert d.refresh and d.uncertain
    c.close()


def test_unlabeled_course_never_suppressed():
    c=db();a,b=baseline(c)
    c.execute("INSERT INTO odev VALUES(1,1,NULL,'Konu','devam')")
    d=decide(c,a,b)
    assert d.refresh and d.uncertain
    c.close()


def test_read_only_database_unchanged():
    c=db();a,b=baseline(c)
    before=c.total_changes
    b.baseline(c,1,'TYT Matematik')
    ev=StudentDataChange(1,('homework',),False,('odev',))
    b.on_commit(c,ev,'LGS Matematik')
    assert c.total_changes==before
    c.close()


def test_schema_keeps_legacy_comparison():
    assert StudentDataChange(1,('homework',),False,('odev',)) == StudentDataChange(1,('homework',))


def test_no_unintended_sql_writes_or_unsafe_query():
    import inspect,services.course_topic_scope_v243 as m
    txt=inspect.getsource(m)
    assert 'CREATE TRIGGER' not in txt and 'commit()' not in txt and 'UPDATE odev' not in txt
    assert 'ogrenci_id' in txt and 'LIMIT ?' in txt
