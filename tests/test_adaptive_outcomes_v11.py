# -*- coding: utf-8 -*-
import importlib.util
import sqlite3
from datetime import date, timedelta
from pathlib import Path
import pytest

SRC=Path(__file__).resolve().parents[1]/'services'/'adaptive_outcomes_v11.py'
spec=importlib.util.spec_from_file_location('adaptive_outcomes_v11',SRC)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

@pytest.fixture()
def db():
    con=sqlite3.connect(':memory:')
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT)')
    con.execute('CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,durum TEXT)')
    con.execute("INSERT INTO ogrenci VALUES (1,'Ayşe'),(2,'Mehmet')")
    con.execute("INSERT INTO odev VALUES (100,1,'tamam'),(200,2,'devam')")
    con.execute('''CREATE TABLE adaptive_observation_v25 (
        id INTEGER PRIMARY KEY,student_id INTEGER, lesson TEXT,topic TEXT,
        correct INTEGER,wrong INTEGER,blank INTEGER,observed_on TEXT)''')
    con.commit()
    yield con
    con.close()


def seed(con, today):
    vals=[(-18,6,4,1,'Fizik','Hareket'),(-12,8,2,1,'Fizik','Hareket'),
          (2,9,1,1,'Fizik','Hareket'),(4,8,2,1,'Fizik','Hareket'),
          (2,0,10,2,'Fizik','Hareket'),(4,0,10,2,'Fizik','Hareket'),
          (3,1,9,1,'Kimya','Hareket'),(3,0,10,1,'Fizik','Kuvvet')]
    for i,(delta,c,w,sid,lesson,topic) in enumerate(vals,1):
        con.execute('''INSERT INTO adaptive_observation_v25 VALUES (?,?,?,?,?,?,?,?)''',
                    (i,sid,lesson,topic,c,w,0,(today+timedelta(days=delta)).isoformat()))
    con.commit()


def followup(con,**opts):
    return mod.record_intervention(con,1,'Fizik','Hareket','micro_check',
                                   teacher_confirmed=True,**opts)


def test_no_schema_or_legacy_mutation_on_read(db):
    assert mod.list_interventions(db,1)==[]
    assert not mod._exists(db,'adaptive_intervention_v11')
    assert db.execute('SELECT durum FROM odev WHERE id=100').fetchone()[0]=='tamam'


def test_confirmation_required_and_no_write(db):
    with pytest.raises(ValueError,match='onayı'):
        mod.record_intervention(db,1,'Fizik','Hareket','micro_check')
    assert not mod._exists(db,'adaptive_intervention_v11')


def test_confirmed_intervention_records_only_separate_log(db):
    rid=followup(db)
    assert rid>0
    assert len(mod.list_interventions(db,1))==1
    assert db.execute('SELECT COUNT(*) FROM odev').fetchone()[0]==2
    assert db.execute('SELECT durum FROM odev WHERE id=100').fetchone()[0]=='tamam'


def test_wrong_student_and_ownership_guard(db):
    rid=followup(db)
    with pytest.raises(ValueError):mod.evaluate_intervention(db,2,rid)
    with pytest.raises(ValueError):mod.review_intervention(db,2,rid,'helpful')
    with pytest.raises(ValueError):mod.record_intervention(db,999,'Fizik','Hareket','micro_check',teacher_confirmed=True)


def test_bad_data_rejected(db):
    for args in [('', 'Hareket','micro_check'),('Fizik','', 'micro_check'),
                 ('Fizik','Hareket','unknown')]:
        with pytest.raises(ValueError):
            mod.record_intervention(db,1,*args,teacher_confirmed=True)
    with pytest.raises(ValueError):
        followup(db,applied_on=date.today()+timedelta(days=1))


def test_insufficient_evidence_not_fabricated(db):
    rid=followup(db)
    report=mod.evaluate_intervention(db,1,rid)
    assert not report['ready']
    assert report['delta_percentage_points'] is None
    assert 'yeterli' in report['status']


def test_comparable_measurement_change_not_causal(db):
    applied=date.today()-timedelta(days=8)
    seed(db,applied)
    rid=followup(db,applied_on=applied)
    report=mod.evaluate_intervention(db,1,rid)
    assert report['ready']
    assert report['baseline']['attempts']==20
    assert report['followup']['attempts']==20
    assert report['baseline']['accuracy']==70.0
    assert report['followup']['accuracy']==85.0
    assert report['delta_percentage_points']==15.0
    assert 'nedensellik göstermez' in report['status']
    # No cross-learner or cross-topic observations can change the score.
    assert db.execute('SELECT durum FROM odev WHERE id=100').fetchone()[0]=='tamam'


def test_intervention_day_is_excluded(db):
    applied=date.today()-timedelta(days=8)
    seed(db,applied)
    db.execute('INSERT INTO adaptive_observation_v25 VALUES (99,1,?,?,?,?,?,?)',
               ('Fizik','Hareket',0,50,0,applied.isoformat()))
    rid=followup(db,applied_on=applied)
    assert mod.evaluate_intervention(db,1,rid)['delta_percentage_points']==15.0


def test_future_followup_is_not_counted(db):
    applied=date.today()-timedelta(days=8)
    seed(db,applied)
    rid=followup(db,applied_on=applied)
    past=applied+timedelta(days=2)
    report=mod.evaluate_intervention(db,1,rid,as_of=past)
    assert not report['ready']
    assert report['delta_percentage_points'] is None


def test_minimum_distinct_days_needed(db):
    applied=date.today()-timedelta(days=8)
    seed(db,applied)
    db.execute('DELETE FROM adaptive_observation_v25 WHERE id=4')
    rid=followup(db,applied_on=applied)
    assert not mod.evaluate_intervention(db,1,rid)['ready']


def test_teacher_review_not_adaptive_autoscoring(db):
    rid=followup(db)
    mod.review_intervention(db,1,rid,'unclear')
    assert mod.evaluate_intervention(db,1,rid)['teacher_review']=='unclear'
    with pytest.raises(ValueError):mod.review_intervention(db,1,rid,'diagnosed')
    assert db.execute('SELECT COUNT(*) FROM adaptive_observation_v25').fetchone()[0]==0


def test_read_only_connections_dont_write(db,tmp_path):
    p=tmp_path/'case.db'
    saved=sqlite3.connect(p)
    db.backup(saved)
    saved.close()
    ro=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
    try:
        ro.execute('PRAGMA query_only=ON')
        assert mod.list_interventions(ro,1)==[]
        with pytest.raises(sqlite3.OperationalError):followup(ro)
    finally:ro.close()


def test_latest_compact_student_scoped(db):
    followup(db)
    assert 'Hareket' in mod.compact_followup_text(db,1)
    assert 'Henüz' in mod.compact_followup_text(db,2)
