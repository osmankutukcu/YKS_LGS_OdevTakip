import importlib.util
import sqlite3
from pathlib import Path
import pytest

MODULE = Path(__file__).parents[1]/'services'/'coaching_safety_v244.py'
spec=importlib.util.spec_from_file_location('coaching_safety_v244',MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture()
def conn():
    c=sqlite3.connect(':memory:')
    c.execute('PRAGMA foreign_keys=ON')
    c.executescript('''
      CREATE TABLE ogrenci(id INTEGER PRIMARY KEY);
      INSERT INTO ogrenci(id) VALUES(1),(2);
      CREATE TABLE koc_plan(id INTEGER PRIMARY KEY AUTOINCREMENT,ogrenci_id INTEGER,baslangic_tarihi TEXT,bitis_tarihi TEXT,notlar TEXT,
          FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id));
      CREATE TABLE koc_hedef(id INTEGER PRIMARY KEY AUTOINCREMENT,plan_id INTEGER,ders_adi TEXT,hedef_soru INTEGER,cozulen_soru INTEGER,
        hedef_saat REAL,calisilan_saat REAL,durum TEXT, FOREIGN KEY(plan_id) REFERENCES koc_plan(id));
      CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,done INTEGER);
      INSERT INTO odev(id,ogrenci_id,done) VALUES(99,1,0);
    ''')
    yield c
    c.close()

def make(conn,student=1):
    conn.execute('BEGIN IMMEDIATE')
    result=m.upsert_week_plan(conn,student,'2026-10-12','2026-10-18',[('TYT Matematik',100),('Fizik',50)])
    conn.commit()
    return result['plan_id']

def row(conn,plan,subject='TYT Matematik'):
    return conn.execute('SELECT * FROM koc_hedef WHERE plan_id=? AND ders_adi=?',(plan,subject)).fetchone()

def update_with(conn,student,plan,**override):
    old=row(conn,plan)
    kw=dict(id=old[0], target=old[3], solved=old[4], target_hours=old[5], worked_hours=old[6], expected=tuple(old[3:7]))
    kw.update(override)
    conn.execute('BEGIN IMMEDIATE')
    try:
        r=m.save_progress(conn,student,plan,[kw]);conn.commit();return r
    except Exception:
        conn.rollback();raise

def test_replan_preserves_solved_hours_ids_status(conn):
    pid=make(conn)
    orig=row(conn,pid)
    conn.execute("UPDATE koc_hedef SET cozulen_soru=75,hedef_saat=5,calisilan_saat=3,durum='tamam' WHERE id=?",(orig[0],));conn.commit()
    conn.execute('BEGIN IMMEDIATE')
    outcome=m.upsert_week_plan(conn,1,'2026-10-12','2026-10-18',[('TYT Matematik',110),('Kimya',60)]);conn.commit()
    new=row(conn,pid)
    assert (new[0],new[3:8])==(orig[0],(110,75,5,3,'tamam'))
    assert row(conn,pid,'Fizik') is not None
    assert outcome==dict(plan_id=pid,updated=1,added=1,retained=1)

def test_same_week_plan_idempotent(conn):
    pid=make(conn)
    conn.execute('BEGIN IMMEDIATE');new,created=m.get_or_create_week(conn,1,'2026-10-12','2026-10-18');conn.commit()
    assert (new,created)==(pid,False)
    assert conn.execute('SELECT count(*) FROM koc_plan').fetchone()[0]==1

def test_new_week_created(conn):
    pid,created=m.get_or_create_week(conn,1,'2026-10-12','2026-10-18')
    conn.commit()
    assert pid>0 and created

def test_week_duplicate_detected_and_preserved(conn):
    pid=make(conn)
    conn.execute('INSERT INTO koc_plan(ogrenci_id,baslangic_tarihi) VALUES(1,?)',('2026-10-12',));conn.commit()
    with pytest.raises(m.CoachingConflict): m.get_or_create_week(conn,1,'2026-10-12','2026-10-18')
    assert conn.execute('SELECT count(*) FROM koc_plan').fetchone()[0]==2

def test_goals_duplicate_existing_detected(conn):
    pid=make(conn)
    conn.execute("INSERT INTO koc_hedef(plan_id,ders_adi,hedef_soru,cozulen_soru,hedef_saat,calisilan_saat) VALUES(?,?,?,?,?,?)",(pid,'TYT Matematik',30,10,1,1));conn.commit()
    with pytest.raises(m.CoachingConflict):m.upsert_week_plan(conn,1,'2026-10-12','2026-10-18',[('TYT Matematik',120)])
    conn.rollback()
    assert row(conn,pid)[3]==100

def test_proposed_duplicate_rejected(conn):
    with pytest.raises(m.CoachingDataError):m.upsert_week_plan(conn,1,'2026-10-12','2026-10-18',[('Fizik',100),(' fizik ',60)])
    conn.rollback()
    assert conn.execute('SELECT count(*) FROM koc_plan').fetchone()[0]==0

@pytest.mark.parametrize('bad',[None,'','abc','-1','1.5','nan','inf','2e1',-5,True,10000001])
def test_bad_goal_numbers_rejected_no_write(conn,bad):
    pid=make(conn)
    with pytest.raises(m.CoachingDataError):m.upsert_week_plan(conn,1,'2026-10-12','2026-10-18',[('TYT Matematik',bad)])
    conn.rollback()
    assert row(conn,pid)[3]==100

@pytest.mark.parametrize('bad',[None,'','abc','-1','nan','inf','1e999',-3])
def test_bad_solved_rejected_no_write(conn,bad):
    pid=make(conn)
    with pytest.raises(m.CoachingDataError):update_with(conn,1,pid,solved=bad)
    assert row(conn,pid)[4]==0

@pytest.mark.parametrize('bad',['nan','inf','-2','bozuk','1e1000'])
def test_invalid_hours_rejected(conn,bad):
    pid=make(conn)
    with pytest.raises(m.CoachingDataError):update_with(conn,1,pid,worked_hours=bad)
    assert row(conn,pid)[6]==0

def test_progress_id_based_and_preserves_other_subject(conn):
    pid=make(conn)
    update_with(conn,1,pid,target=120,solved=75,target_hours='5,5',worked_hours=3.5)
    assert row(conn,pid)[3:7] == (120,75,5.5,3.5)
    assert row(conn,pid,'Fizik')[3]==50

def test_wrong_student_refuses(conn):
    pid=make(conn)
    with pytest.raises(m.CoachingConflict):update_with(conn,2,pid,solved=90)
    assert row(conn,pid)[4]==0

def test_stale_writes_conflict(conn):
    pid=make(conn)
    orig=row(conn,pid)
    conn.execute('UPDATE koc_hedef SET cozulen_soru=30 WHERE id=?',(orig[0],));conn.commit()
    stale=dict(id=orig[0],expected=tuple(orig[3:7]),target=orig[3],solved=90,target_hours=orig[5],worked_hours=orig[6])
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(m.CoachingConflict):m.save_progress(conn,1,pid,[stale])
    conn.rollback()
    assert row(conn,pid)[4]==30

def test_second_row_validation_rolls_back_everything(conn):
    pid=make(conn)
    a=row(conn,pid); b=row(conn,pid,'Fizik')
    first=dict(id=a[0],expected=tuple(a[3:7]),target=200,solved=150,target_hours=1,worked_hours=1)
    second=dict(id=b[0],expected=tuple(b[3:7]),target=50,solved='bozuk',target_hours=0,worked_hours=0)
    with pytest.raises(m.CoachingDataError): m.save_progress(conn,1,pid,[first,second])
    conn.rollback()
    assert row(conn,pid)[3:5]==(100,0)

def test_legacy_note_and_two_updates_retained(conn):
    pid=make(conn)
    conn.execute('UPDATE koc_plan SET notlar=? WHERE id=?',('eski not',pid));conn.commit()
    conn.execute('BEGIN IMMEDIATE');assert m.append_note(conn,1,pid,'ilk görüşme');conn.commit()
    conn.execute('BEGIN IMMEDIATE');assert m.append_note(conn,1,pid,'ikinci görüşme');conn.commit()
    hist=m.note_history(conn,1)
    assert [x['notes'] for x in hist]==['ikinci görüşme','ilk görüşme','eski not']
    assert conn.execute('SELECT notlar FROM koc_plan WHERE id=?',(pid,)).fetchone()[0]=='ikinci görüşme'

def test_equal_note_idempotent(conn):
    pid=make(conn)
    conn.execute('BEGIN IMMEDIATE');assert m.append_note(conn,1,pid,'aynı');conn.commit()
    conn.execute('BEGIN IMMEDIATE');assert not m.append_note(conn,1,pid,'aynı');conn.commit()
    assert len(m.note_history(conn,1))==1

def test_legacy_note_is_archived_without_duplicate(conn):
    pid=make(conn)
    conn.execute('UPDATE koc_plan SET notlar=? WHERE id=?',('önceki',pid));conn.commit()
    conn.execute('BEGIN IMMEDIATE');assert not m.append_note(conn,1,pid,'önceki');conn.commit()
    assert [e['notes'] for e in m.note_history(conn,1)]==['önceki']

def test_old_weekly_note_read_without_migration(conn):
    pid=make(conn)
    conn.execute('UPDATE koc_plan SET notlar=? WHERE id=?',('eski kayit',pid));conn.commit()
    assert m.note_history(conn,1)[0]['kind']=='weekly'
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='koc_gorusme_gecmis_v244'").fetchone()

def test_note_wrong_student_no_history_table(conn):
    pid=make(conn)
    with pytest.raises(m.CoachingConflict):m.append_note(conn,2,pid,'yanlış öğrenci')
    conn.rollback()
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='koc_gorusme_gecmis_v244'").fetchone()

def test_history_student_isolation(conn):
    p1=make(conn,1);p2=make(conn,2)
    conn.execute('BEGIN IMMEDIATE');m.append_note(conn,1,p1,'birinci öğrenci');m.append_note(conn,2,p2,'ikinci öğrenci');conn.commit()
    assert [e['notes'] for e in m.note_history(conn,1)]==['birinci öğrenci']
    assert [e['notes'] for e in m.note_history(conn,2)]==['ikinci öğrenci']

def test_notes_rollback_not_persistent(conn):
    pid=make(conn)
    conn.execute('BEGIN IMMEDIATE');m.append_note(conn,1,pid,'not');conn.rollback()
    assert not m.note_history(conn,1)

def test_main_homework_table_not_touched(conn):
    pid=make(conn)
    conn.execute('BEGIN IMMEDIATE');m.append_note(conn,1,pid,'görüşme');conn.commit()
    update_with(conn,1,pid,solved=30)
    assert conn.execute('SELECT * FROM odev').fetchall()==[(99,1,0)]

def test_review_draft_source_code_no_fake_meeting_claim():
    text=(Path(__file__).parents[1]/'ui'/'coaching_manager.py').read_text()
    body=text.split('    def _generate_auto_comment(self):')[1].split('    def _compose_notes_text(self):')[0]
    assert 'gerçekleştirildi' not in body and 'TASLAK' in body
    assert 'INSERT INTO koc_gorusme_gecmis_v244' not in body

def test_main_files_identical():
    root=Path(__file__).parents[1]
    for name in ('ui/homework_form.py','ui/odev_kontrol.py','db.py'):
        assert (root/name).is_file()
    assert 'from services.coaching_safety_v244 import' in (root/'ui/coaching_manager.py').read_text()
