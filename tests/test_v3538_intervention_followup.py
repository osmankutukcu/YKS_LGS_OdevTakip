# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path
import sqlite3

import pytest

from services.adaptive_outcomes_v11 import record_intervention, review_intervention
from services.intervention_followup_v3538 import (
    read_student_followups, scan_cohort_followups,
)
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]
DAY = date.today()


@pytest.fixture
def con():
    c = sqlite3.connect(':memory:')
    c.execute('PRAGMA foreign_keys=ON')
    c.executescript('''
      CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, aktif INTEGER DEFAULT 1);
      INSERT INTO ogrenci(id,ad,aktif) VALUES (1,'Öğrenci A',1),(2,'Öğrenci B',1),(3,'Öğrenci C',0);
      CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,durum TEXT);
      INSERT INTO odev VALUES (101,1,'devam'),(202,2,'tamam');
      CREATE TABLE adaptive_observation_v25(
        id INTEGER PRIMARY KEY, student_id INTEGER,lesson TEXT,topic TEXT,
        correct INTEGER,wrong INTEGER,blank INTEGER,observed_on TEXT);
    ''')
    yield c
    c.close()


def add(c, sid=1, days=8, lesson='Fizik', topic='Kuvvet'):
    return record_intervention(c, sid, lesson, topic, 'micro_check',
        applied_on=DAY - timedelta(days=days), teacher_confirmed=True)


def measure(c, sid=1, days=8, *, lesson='Fizik', topic='Kuvvet'):
    applied = DAY - timedelta(days=days)
    for d, cc, ww in [(-5, 5, 5), (-3, 6, 4), (2, 7, 3), (4, 8, 2)]:
        c.execute('''INSERT INTO adaptive_observation_v25
           (student_id,lesson,topic,correct,wrong,blank,observed_on)
           VALUES (?,?,?,?,?,?,?)''', (sid, lesson,topic,cc,ww,0,(applied+timedelta(days=d)).isoformat()))


def test_no_approved_intervention_no_schema_created(con):
    changes = con.total_changes
    r = read_student_followups(con, 1)
    assert r['state'] == 'NO_APPROVED_INTERVENTION'
    assert r['records'] == []
    assert con.total_changes == changes
    assert con.execute("SELECT 1 FROM sqlite_master WHERE name='adaptive_intervention_v11'").fetchone() is None


def test_teacher_approval_required_by_existing_service(con):
    with pytest.raises(ValueError):
        record_intervention(con,1,'Fizik','Kuvvet','micro_check')
    assert read_student_followups(con,1)['records'] == []


def test_day7_and_day14_dates_and_no_auto_writes(con):
    add(con, days=8)
    changes = con.total_changes
    r = read_student_followups(con, 1, as_of=DAY)
    assert r['records'][0]['status'] == 'DAY7_RECHECK_DUE'
    assert r['records'][0]['day14'] == (DAY+timedelta(days=6)).isoformat()
    assert r['attention_count'] == 1
    assert con.total_changes == changes
    assert con.execute('SELECT durum FROM odev WHERE id=101').fetchone()[0] == 'devam'
    assert r['messages_sent'] is False if 'messages_sent' in r else r['automated_records'] is False


def test_before_first_followup_is_quiet(con):
    add(con, days=2)
    r = read_student_followups(con,1)
    assert r['records'][0]['status'] == 'WAITING_FOR_DAY7'
    assert r['attention_count'] == 0
    assert scan_cohort_followups(con)['date_due_candidates'] == 0


def test_day14_and_overdue_measurements(con):
    add(con, days=15)
    assert read_student_followups(con, 1)['records'][0]['status'] == 'DAY14_RECHECK_DUE'
    con.execute('DELETE FROM adaptive_intervention_v11')
    add(con, days=60)
    assert read_student_followups(con, 1)['records'][0]['status'] == 'MEASUREMENT_OVERDUE'


def test_quality_measurements_without_causal_claim(con):
    iid = add(con, days=8)
    measure(con, days=8)
    r = read_student_followups(con,1)['records'][0]
    assert r['id'] == iid
    assert r['measurement_ready'] is True
    assert r['status'] == 'MEASUREMENT_REVIEW_DUE'
    assert r['delta_percentage_points'] == 20.0
    assert r['causality_not_established']
    assert 'nedensellik' in read_student_followups(con,1)['warning']


def test_teacher_qualitative_review_does_not_prove_effect(con):
    iid = add(con,days=19)
    review_intervention(con,1,iid,'helpful')
    r=read_student_followups(con,1)['records'][0]
    assert r['status'] == 'TEACHER_REVIEWED'
    assert r['measurement_ready'] is False
    assert r['delta_percentage_points'] is None
    assert scan_cohort_followups(con)['date_due_candidates'] == 0


def test_wrong_identity_and_other_student_data_excluded(con):
    add(con,1,days=8)
    add(con,2,days=10,topic='Hareket')
    for other in (0,2.0,True,'1',None):
        with pytest.raises(ValueError):
            read_student_followups(con, other)
    a = read_student_followups(con,1)
    assert a['records'][0]['topic'] == 'Kuvvet'
    assert a['records'][0]['student_id'] == 1
    assert len(scan_cohort_followups(con)['priority_cards']) == 2


def test_inactive_student_excluded_from_cohort(con):
    add(con,1,days=8)
    add(con,3,days=20)
    r=scan_cohort_followups(con)
    assert r['date_due_candidates'] == 1
    assert [x['student_id'] for x in r['priority_cards']] == [1]


def test_cohort_cap_declared_partial(con):
    add(con,1,days=8)
    add(con,2,days=10)
    r=scan_cohort_followups(con,max_scan=1)
    assert r['state'] == 'PARTIAL_COVERAGE'
    assert r['evaluated_records']==1
    assert r['date_due_candidates']==1


def test_malformed_applied_date_disclosed(con):
    add(con,days=8)
    con.execute('UPDATE adaptive_intervention_v11 SET applied_on=?',('bogus',))
    r=scan_cohort_followups(con)
    assert r['state']=='PARTIAL_COVERAGE'
    assert r['invalid_date_rows']==1


def test_latest_per_student_not_first_global(con):
    add(con,1,days=28)
    add(con,1,days=2)
    add(con,2,days=9)
    r=scan_cohort_followups(con)
    assert r['date_due_candidates']==1
    assert r['priority_cards'][0]['student_id']==2


def test_readonly_db_is_safe(tmp_path):
    path=tmp_path/'safe.db'
    c=sqlite3.connect(path)
    c.execute('CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, aktif INTEGER)')
    c.execute('INSERT INTO ogrenci VALUES(1,1)')
    c.commit();c.close()
    c=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    c.execute('PRAGMA query_only=ON')
    try:
        assert scan_cohort_followups(c)['state']=='NO_APPROVED_INTERVENTIONS'
        assert read_student_followups(c,1)['records']==[]
    finally:
        c.close()


def test_row_factory_kept(con):
    add(con)
    con.row_factory=sqlite3.Row
    assert read_student_followups(con,1)['student_id']==1
    assert scan_cohort_followups(con)['date_due_candidates']==1
    assert con.row_factory is sqlite3.Row


def test_future_as_of_cannot_claim_scheduled_record(con):
    add(con,days=2)
    earlier=DAY-timedelta(days=20)
    r=read_student_followups(con,1,as_of=earlier)
    assert r['records']==[]
    assert r['attention_count']==0



def test_automatic_teacher_feed_contains_due_reminder(tmp_path):
    from services.teacher_copilot_v5 import read_teacher_feed
    db=tmp_path/'koc-test.db'
    with sqlite3.connect(db) as c:
        c.executescript('''CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,
            dogum_tarihi TEXT,veli_tel1 TEXT,aktif INTEGER);
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
            verilis_tarihi TEXT,bitis_tarihi TEXT);
        CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,
            ders TEXT,durum TEXT);
        INSERT INTO ogrenci VALUES(1,'Test','Öğrenci',NULL,NULL,1);''')
        add(c,days=8)
    old=db.read_bytes()
    r=read_teacher_feed(db,today=DAY)
    assert r['intervention_followups']['state']=='OBSERVED'
    assert r['intervention_followups']['date_due_candidates']==1
    assert r['intervention_followups']['priority_cards'][0]['student_id']==1
    assert db.read_bytes()==old  # V3.5.38 cannot change homework or followup notes

def test_core_guards_and_compiles():
    assert audit(ROOT)['status']=='PASS'
    for rel in ('services/intervention_followup_v3538.py','ui/student360_panel_v16.py',
                'ui/teacher_copilot_strip_v5.py','services/teacher_copilot_v5.py'):
        ast.parse((ROOT/rel).read_text('utf8'))
    for rel in ('ui/homework_form.py','ui/odev_kontrol.py','db.py',
                'services/adaptive_outcomes_v11.py'):
        assert 'v3538' not in (ROOT/rel).read_text('utf8').lower()
