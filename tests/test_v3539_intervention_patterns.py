# -*- coding: utf-8 -*-
"""Read-only, privacy and methodological safeguards for V3.5.39."""
import ast
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import pytest

from services.adaptive_outcomes_v11 import record_intervention, review_intervention
from services.intervention_patterns_v3539 import (
    read_historical_patterns, compact_history_line,
)
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]
TODAY = date.today()

@pytest.fixture
def con():
    c = sqlite3.connect(':memory:')
    c.execute('PRAGMA foreign_keys=ON')
    c.executescript('''
       CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,aktif INTEGER DEFAULT 1);
       CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,durum TEXT);
       CREATE TABLE adaptive_observation_v25(
         id INTEGER PRIMARY KEY,student_id INTEGER,lesson TEXT,topic TEXT,
         correct INTEGER,wrong INTEGER,blank INTEGER,observed_on TEXT);
    ''')
    for sid in range(1,20):
        c.execute('INSERT INTO ogrenci VALUES(?,?,?)', (sid,'Öğrenci '+str(sid),int(sid != 19)))
        c.execute('INSERT INTO odev VALUES(?,?,?)',(sid,sid,'devam'))
    c.commit()
    yield c
    c.close()


def add(con,sid=1,*,lesson='Fizik',topic='Hareket',action='micro_check',
        reviewed='helpful',days=30, measured=True, before=5, after=7):
    started=TODAY-timedelta(days=days)
    iid=record_intervention(con,sid,lesson,topic,action,applied_on=started,teacher_confirmed=True)
    if reviewed:
        review_intervention(con,sid,iid,reviewed)
    if measured:
        for offset,c in [(-5,before),(-3,before), (2,after),(4,after)]:
            con.execute('''INSERT INTO adaptive_observation_v25
             (student_id,lesson,topic,correct,wrong,blank,observed_on)
             VALUES (?,?,?,?,?,?,?)''',
             (sid,lesson,topic,c,10-c,0,(started+timedelta(days=offset)).isoformat()))
    con.commit()
    return iid


def populate(con,n=5,**kw):
    for sid in range(1,n+1):
        add(con,sid,**kw)


def test_missing_history_does_not_write_or_invent(con):
    changed=con.total_changes
    out=read_historical_patterns(con)
    assert out['state']=='NO_APPROVED_HISTORY'
    assert out['patterns']==[]
    assert not out['recommendation_weights_updated']
    assert con.total_changes == changed
    assert not con.execute("SELECT 1 FROM sqlite_master WHERE name='adaptive_intervention_v11'").fetchone()


def test_minimum_five_students_and_no_leak(con):
    populate(con,4)
    out=read_historical_patterns(con)
    assert out['state']=='INSUFFICIENT_GROUP_SIZE'
    assert out['patterns']==[]
    assert compact_history_line(out) is None
    assert 'Öğrenci' not in str(out)


def test_five_ready_descriptive_not_prediction(con):
    populate(con)
    initial=con.total_changes
    out=read_historical_patterns(con)
    assert out['state']=='DESCRIPTIVE_HISTORY'
    p=out['patterns'][0]
    assert p['distinct_students']==5
    assert p['measured_students']==5
    assert p['directions']=={'higher':5,'similar':0,'lower':0}
    assert p['teacher_reviews']['helpful']==5
    assert p['state']=='DESCRIPTIVE_HISTORY'
    assert 'nedensellik' not in (compact_history_line(out) or '').lower() or 'Nedensellik kanıtı değil' in compact_history_line(out)
    assert out['causal_claim'] is False
    assert out['recommendation_weights_updated'] is False
    assert out['automatic_assignments'] is False
    assert 'student_id' not in str(out)
    assert con.total_changes == initial
    assert con.execute('SELECT durum FROM odev LIMIT 1').fetchone()[0]=='devam'


def test_five_approved_but_not_enough_measured(con):
    populate(con,5,measured=False)
    r=read_historical_patterns(con)
    assert r['patterns'][0]['state']=='INSUFFICIENT_INDEPENDENT_MEASUREMENTS'
    assert r['patterns'][0]['directions'] is None
    assert compact_history_line(r) is None


def test_one_learner_cannot_masquerade_as_five(con):
    for d in (21,22,23,24,25,26):
        add(con,1,days=d,measured=False)
    r=read_historical_patterns(con)
    assert r['sampled']==1
    assert r['patterns']==[]


def test_distinct_lesson_and_topic_and_action(con):
    populate(con,5)
    for sid in range(6,11):
        add(con,sid,lesson='Fizik',topic='Kuvvet',action='spaced_review',before=8,after=5)
    r=read_historical_patterns(con,lesson='Fizik',topic='Kuvvet')
    assert len(r['patterns'])==1
    assert r['patterns'][0]['topic']=='Kuvvet'
    assert r['patterns'][0]['action_code']=='spaced_review'
    assert r['patterns'][0]['directions']['lower']==5


def test_inactive_students_never_contribute(con):
    populate(con,4)
    add(con,19)
    r=read_historical_patterns(con)
    assert r['patterns']==[]


def test_unreviewed_records_not_counted(con):
    populate(con,4)
    add(con,5,reviewed=None)
    assert read_historical_patterns(con)['patterns']==[]


def test_partial_coverage_discloses_limit_and_no_presentation(con):
    populate(con,6)
    r=read_historical_patterns(con,max_scan=5)
    assert r['state']=='PARTIAL_COVERAGE'
    assert r['limited']
    assert compact_history_line(r).startswith('Kısmi tarama')


def test_wrong_or_missing_observation_schema_is_not_success(con):
    populate(con,5)
    con.execute('DROP TABLE adaptive_observation_v25')
    r=read_historical_patterns(con)
    assert r['state']=='SOURCE_UNVERIFIED'
    assert r['patterns']==[]


def test_bad_date_record_does_not_enter_pattern(con):
    populate(con,4)
    iid=add(con,5)
    con.execute('UPDATE adaptive_intervention_v11 SET applied_on=? WHERE id=?',('bad-date',iid))
    r=read_historical_patterns(con)
    assert r['patterns']==[]


def test_group_distribution_mixed_reviews_and_evidence(con):
    for sid,(before,after,review) in enumerate(((5,8,'helpful'),(5,4,'not_helpful'),
                   (5,5,'unclear'),(5,6,'helpful'),(5,3,'not_helpful')),start=1):
        add(con,sid,before=before,after=after,reviewed=review)
    p=read_historical_patterns(con)['patterns'][0]
    assert p['directions']=={'higher':2,'similar':1,'lower':2}
    assert p['teacher_reviews']=={'helpful':2,'not_helpful':2,'unclear':1}


def test_teacher_feedback_alone_cannot_become_measured_history(con):
    populate(con,5,measured=False,reviewed='helpful')
    p=read_historical_patterns(con)['patterns'][0]
    assert p['measured_students']==0
    assert p['directions'] is None


@pytest.mark.parametrize('kwargs',[
    {'max_scan':0},{'max_scan':True},{'max_scan':501}, {'max_groups':0},
    {'minimum_students':4},{'minimum_students':True}, {'as_of':'yesterday'},
    {'lesson':' '},{'topic':5},
])
def test_bad_arguments_rejected(con,kwargs):
    with pytest.raises(ValueError):
        read_historical_patterns(con,**kwargs)


def test_readonly_sqlite_and_preserved_row_factory(tmp_path):
    f=tmp_path/'readonly.db'
    c=sqlite3.connect(f)
    c.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,aktif INTEGER)')
    c.execute('INSERT INTO ogrenci VALUES(1,1)')
    c.commit();c.close()
    con=sqlite3.connect(f.as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    try:
        r=read_historical_patterns(con)
        assert r['state']=='NO_APPROVED_HISTORY'
        assert con.row_factory is sqlite3.Row
    finally: con.close()


def test_cannot_claim_history_at_date_before_approval(con):
    populate(con,5)
    r=read_historical_patterns(con,as_of=TODAY-timedelta(days=200))
    assert r['patterns']==[]


def test_core_guard_and_integrations_are_opt_in():
    assert audit(ROOT)['status']=='PASS'
    files=['services/intervention_patterns_v3539.py','ui/student360_panel_v16.py',
           'services/teacher_copilot_v5.py','ui/teacher_copilot_strip_v5.py']
    for f in files: ast.parse((ROOT/f).read_text(encoding='utf8'))
    for f in ['ui/homework_form.py','ui/odev_kontrol.py','db.py',
              'services/adaptive_outcomes_v11.py','ui/adaptive_followup_v11.py']:
        assert 'v3539' not in (ROOT/f).read_text('utf8').lower()


def test_same_student_same_topic_different_actions_counts_once(con):
    # The same independent follow-up observations cannot count once per action.
    populate(con, 4)
    add(con, 5, action='micro_check', days=35)
    add(con, 5, action='spaced_review', days=22)
    r=read_historical_patterns(con)
    assert r['state']=='INSUFFICIENT_GROUP_SIZE'
    assert r['patterns']==[]


def test_daily_feed_inherits_optional_history_without_record_writes(tmp_path):
    from services.teacher_copilot_v5 import read_teacher_feed
    f=tmp_path/'historical-coach.db'
    con=sqlite3.connect(f)
    con.executescript('''
      CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,
        dogum_tarihi TEXT,veli_tel1 TEXT,aktif INTEGER);
      CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
        verilis_tarihi TEXT,bitis_tarihi TEXT);
      CREATE TABLE odev(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,
        ders TEXT,durum TEXT);
      CREATE TABLE adaptive_observation_v25(id INTEGER PRIMARY KEY,
        student_id INTEGER,lesson TEXT,topic TEXT,correct INTEGER,
        wrong INTEGER,blank INTEGER,observed_on TEXT);
    ''')
    for sid in range(1,6):
        con.execute('INSERT INTO ogrenci VALUES(?,?,?,NULL,NULL,1)',
                    (sid,'Örnek'+str(sid),'Öğrenci'))
    con.execute('INSERT INTO odev_kume VALUES(1,1,?,?)',
         ((TODAY-timedelta(days=18)).isoformat(),(TODAY-timedelta(days=5)).isoformat()))
    con.execute("INSERT INTO odev VALUES(1,1,1,'Fizik','devam')")
    con.commit()
    for sid in range(1,6):
        add(con,sid)
    con.close()
    before=f.read_bytes()
    feed=read_teacher_feed(f,today=TODAY)
    assert feed['cards']
    assert feed['historical_patterns']['state']=='DESCRIPTIVE_HISTORY'
    assert feed['historical_patterns']['patterns'][0]['measured_students']==5
    assert feed['historical_patterns']['recommendation_weights_updated'] is False
    assert f.read_bytes()==before
