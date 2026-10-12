"""V19: teacher-reviewed item evidence, non-destructive, atomic integration."""
import csv
import sqlite3
from pathlib import Path
import pytest
from services.question_evidence_v19 import (prepare,apply,parse_file,
    EvidenceImportError,fetch_exams_for_student)
from services.topic_evidence_v18 import read_topic_evidence


def db():
    c=sqlite3.connect(':memory:')
    c.executescript('''
     CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,aktif INTEGER);
     INSERT INTO ogrenci VALUES(1,'Örnek','Bir',1),(2,'Örnek','İki',1),(3,'Pasif','Üç',0);
     CREATE TABLE denemeler(id INTEGER PRIMARY KEY,deneme_adi TEXT,tarih TEXT,tur TEXT);
     INSERT INTO denemeler VALUES(9,'Test A','2026-10-11','TYT'),(10,'Test B','2026-10-12','AYT');
     CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY,deneme_id INTEGER,ogrenci_id INTEGER,
       ders_adi TEXT,dogru INTEGER,yanlis INTEGER,bos INTEGER,net REAL);
     INSERT INTO deneme_sonuclari VALUES(1,9,1,'Fizik',5,3,2,4.25),
       (2,9,2,'Fizik',6,2,2,5.5),(3,10,1,'Matematik',5,2,3,4.5);
     CREATE TABLE odev_takip(id INTEGER,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum TEXT);
     INSERT INTO odev_takip VALUES(1,1,'Fizik','Elektrostatik','Aktif');
    ''')
    c.commit()
    return c


def data(**kw):
    return {**dict(ogrenci_id='1',deneme_id='9',ders='Fizik',soru_no='3',
                   sonuc='yanlış',konu='Elektrostatik',kazanim_kodu='FIZ.9.1',_row=2),**kw}


def test_approved_import_and_topic_view():
    c=db();p=prepare(c,9,1,[data()]);assert p.counts['new']==1 and not p.errors
    assert apply(c,p,teacher_confirmed=True)['new']==1
    report=read_topic_evidence(c,1)
    topic=next(t for t in report.topics if t.topic=='Elektrostatik')
    assert topic.question_wrong==1 and topic.question_correct==0
    assert topic.outcome_codes==('FIZ.9.1',)
    assert 'resmî doğrulama' in report.explain()
    assert 'kontrolü' in topic.recommendation


def test_requires_teacher_confirmation():
    c=db();p=prepare(c,9,1,[data()])
    with pytest.raises(EvidenceImportError):apply(c,p)
    assert c.execute("SELECT name FROM sqlite_master WHERE name='soru_konu_kanit_v19'").fetchone() is None


@pytest.mark.parametrize('change',[
    dict(ogrenci_id='2'),dict(deneme_id='10'),dict(ders='Kimya'),dict(soru_no='0'),
    dict(soru_no='201'),dict(soru_no='3.2'),dict(sonuc='bilinmiyor'),
    dict(konu=''),dict(kazanim_kodu='a'*101),dict(konu='A\nB')
])
def test_validation_rejects_unsafe_rows(change):
    c=db();p=prepare(c,9,1,[data(**change)]);assert p.errors
    with pytest.raises(EvidenceImportError):apply(c,p,teacher_confirmed=True)


def test_multiple_students_cannot_mix_in_same_batch():
    c=db();p=prepare(c,9,1,[data(),data(ogrenci_id='2',soru_no='4')])
    assert p.errors


def test_duplicated_question_rejected():
    c=db();p=prepare(c,9,1,[data(),data()]); assert p.errors


def test_unknown_topic_warning_but_explicit_confirmation_possible():
    c=db();p=prepare(c,9,1,[data(konu='Elektrostatik Ek')])
    assert not p.errors and p.warnings
    apply(c,p,teacher_confirmed=True)
    r=read_topic_evidence(c,1)
    assert any(t.topic=='Elektrostatik Ek' for t in r.topics)
    assert next(t for t in r.topics if t.topic=='Elektrostatik').question_wrong==0


def test_idempotent_second_apply():
    c=db();p=prepare(c,9,1,[data()]);apply(c,p,teacher_confirmed=True)
    q=prepare(c,9,1,[data()]);assert q.counts['same']==1
    n=c.execute('SELECT COUNT(*) FROM soru_konu_kanit_log_v19').fetchone()[0]
    assert apply(c,q,teacher_confirmed=True)['same']==1
    assert c.execute('SELECT COUNT(*) FROM soru_konu_kanit_log_v19').fetchone()[0]==n

@pytest.mark.parametrize('change',[
    dict(sonuc='doğru'),dict(konu='Elektrostatik Ek'),dict(kazanim_kodu='FIZ.9.2')
])
def test_update_keeps_single_row_with_audit(change):
    c=db();apply(c,prepare(c,9,1,[data()]),teacher_confirmed=True)
    p=prepare(c,9,1,[data(**change)])
    assert p.counts['update']==1
    apply(c,p,teacher_confirmed=True)
    assert c.execute('SELECT COUNT(*) FROM soru_konu_kanit_v19').fetchone()[0]==1
    assert c.execute('SELECT COUNT(*) FROM soru_konu_kanit_log_v19').fetchone()[0]==2
    assert c.execute('SELECT COUNT(*) FROM deneme_sonuclari').fetchone()[0]==3


def test_stale_preview_rejected_and_rolled_back():
    c=db();p=prepare(c,9,1,[data()]);c.execute('UPDATE deneme_sonuclari SET yanlis=4 WHERE id=1');c.commit()
    with pytest.raises(EvidenceImportError,match='değişti'):
        apply(c,p,teacher_confirmed=True)
    assert not c.in_transaction
    assert c.execute("SELECT name FROM sqlite_master WHERE name='soru_konu_kanit_v19'").fetchone() is None


def test_stale_question_change_rejected():
    c=db();apply(c,prepare(c,9,1,[data()]),teacher_confirmed=True)
    p=prepare(c,9,1,[data(konu='Elektrostatik Ek')])
    c.execute('UPDATE soru_konu_kanit_v19 SET sonuc="dogru"');c.commit()
    with pytest.raises(EvidenceImportError,match='değişti'):
        apply(c,p,teacher_confirmed=True)


def test_source_scores_are_never_modified():
    c=db();before=c.execute('SELECT * FROM deneme_sonuclari').fetchall()
    apply(c,prepare(c,9,1,[data()]),teacher_confirmed=True)
    assert c.execute('SELECT * FROM deneme_sonuclari').fetchall()==before
    other=read_topic_evidence(c,2)
    assert not any(t.question_wrong for t in other.topics)


def test_unlinked_or_deleted_exam_score_not_evidence():
    c=db();apply(c,prepare(c,9,1,[data()]),teacher_confirmed=True)
    c.execute('DELETE FROM deneme_sonuclari WHERE id=1');c.commit()
    r=read_topic_evidence(c,1)
    assert any('artık geçerli' in s for s in r.warnings)
    assert all(t.question_wrong==0 for t in r.topics)


def test_aggregation_is_not_exams_inferred_topic():
    c=db();r=read_topic_evidence(c,1)
    assert all(t.question_wrong==0 for t in r.topics)
    assert r.exam_context


def test_missing_exam_result_rejects_course():
    c=db();p=prepare(c,9,1,[data(ders='Matematik')]);assert p.errors


def test_question_count_exceeding_wrong_rejected():
    c=db();p=prepare(c,9,1,[data(soru_no=str(x)) for x in (1,2,3,4)])
    assert any('aşıyor' in x for x in p.errors)


def test_file_parsing_csv_and_header_aliases(tmp_path):
    p=tmp_path/'items.csv';p.write_text('ogrenci id;deneme id;ders;soru no;sonuc;konu;kazanim\n'
        '1;9;Fizik;3;Yanlış;Elektrostatik;FIZ.9.1\n',encoding='utf-8-sig')
    rows=parse_file(p);assert rows[0]['konu']=='Elektrostatik' and rows[0]['soru_no']=='3'
    assert not prepare(db(),9,1,rows).errors


def test_missing_header_rejected(tmp_path):
    p=tmp_path/'items.csv';p.write_text('a,b,c\n1,2,3\n',encoding='utf-8')
    with pytest.raises(EvidenceImportError,match='Eksik'):
        parse_file(p)


def test_fetch_exams_student_scoped():
    c=db();ids=[x[0] for x in fetch_exams_for_student(c,2)]
    assert ids==[9]


def test_read_only_review():
    c=db();apply(c,prepare(c,9,1,[data()]),teacher_confirmed=True)
    c.execute('PRAGMA query_only=ON')
    before=c.total_changes;r=read_topic_evidence(c,1)
    assert c.total_changes==before and r.topics


def test_rollback_if_second_record_is_changed():
    c=db();p=prepare(c,9,1,[data(soru_no='3'),data(soru_no='4')])
    # Force another writer's record to appear at #4
    c.execute('''CREATE TABLE soru_konu_kanit_v19 (deneme_id INTEGER,ogrenci_id INTEGER,ders_adi TEXT,
      soru_no INTEGER,sonuc TEXT,konu_adi TEXT,kazanim_kodu TEXT)''')
    c.execute("INSERT INTO soru_konu_kanit_v19 VALUES(9,1,'Fizik',4,'dogru','Başka','')");c.commit()
    with pytest.raises(EvidenceImportError):apply(c,p,teacher_confirmed=True)
    assert c.execute("SELECT COUNT(*) FROM soru_konu_kanit_v19 WHERE soru_no=3").fetchone()[0]==0


def test_incremental_import_cannot_exceed_exam_wrong_total():
    c=db()
    apply(c,prepare(c,9,1,[data(soru_no=str(i)) for i in (1,2,3)]),teacher_confirmed=True)
    p=prepare(c,9,1,[data(soru_no='4')])
    assert any('aşıyor' in e for e in p.errors)
    with pytest.raises(EvidenceImportError): apply(c,p,teacher_confirmed=True)


def test_aggregate_subject_remains_untouched_after_review():
    c=db();before=c.execute('SELECT net FROM deneme_sonuclari WHERE id=1').fetchone()[0]
    apply(c,prepare(c,9,1,[data(sonuc='doğru')]),teacher_confirmed=True)
    assert c.execute('SELECT net FROM deneme_sonuclari WHERE id=1').fetchone()[0]==before
