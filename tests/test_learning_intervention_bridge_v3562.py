# -*- coding: utf-8 -*-
"""Synthetic, no production student DB used."""
from __future__ import annotations

from datetime import date, datetime
import sqlite3
import unittest
from unittest.mock import patch

from services.learning_intervention_bridge_v3562 import read_learning_intervention_draft
from tests.test_v3536_academic_actions import db

DAY = date(2026, 10, 20)


def hub(sid=1, day=DAY, state='HOMEWORK_FOLLOWUP'):
    return {'schema':'coaching_evidence_hub_v3561', 'student_id':sid,
            'as_of':day.isoformat(), 'state':state,
            'read_only':True, 'auto_change_allowed':False,
            'evidence_level': 'VERIFIED_LOCAL_HOMEWORK'}


def schema(con):
    con.executescript('''
    CREATE TABLE adaptive_observation_v25 (
      id INTEGER PRIMARY KEY, student_id INTEGER, homework_id INTEGER,
      lesson TEXT, topic TEXT, mode TEXT, reason TEXT,
      correct INTEGER, wrong INTEGER, blank INTEGER, observed_on TEXT);
    CREATE TABLE adaptive_quick_note_v28 (
      id INTEGER PRIMARY KEY, student_id INTEGER, homework_id INTEGER,
      lesson TEXT, topic TEXT, reason_code TEXT, updated_at TEXT);
    ''')


def obs(con, sid=1, when='2026-10-18', lesson='Fizik', topic='Kuvvet',
        correct=2, wrong=4, blank=0, homework_id=101):
    con.execute('''INSERT INTO adaptive_observation_v25
       (student_id,homework_id,lesson,topic,mode,reason,correct,wrong,blank,observed_on)
       VALUES (?,?,?,?,'Hedefli soru','Belirtilmedi',?,?,?,?)''',
        (sid,homework_id,lesson,topic,correct,wrong,blank,when))


def note(con,sid=1,code='concept',when='2026-10-19',homework_id=101):
    con.execute('''INSERT INTO adaptive_quick_note_v28
        (student_id,homework_id,lesson,topic,reason_code,updated_at)
        VALUES (?,?,'Fizik','Kuvvet',?,?)''',(sid,homework_id,code,when))


class LearningInterventionTests(unittest.TestCase):
    def setUp(self):
        self.con = db()
        schema(self.con)
    def tearDown(self):
        self.con.close()
    def read(self,sid=1,**kwargs):
        return read_learning_intervention_draft(self.con,sid,today=DAY,
                hub_card=hub(sid), **kwargs)

    def test_reject_invalid_identity_and_date_and_limit(self):
        for sid in (-1,0,True,'1',1.0,None):
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                read_learning_intervention_draft(self.con,sid,today=DAY,hub_card=hub())
        for bad in ('2026-10-20',datetime(2026,10,20)):
            with self.assertRaises(ValueError):
                read_learning_intervention_draft(self.con,1,today=bad,hub_card=hub())
        for bad in (0, 4, True):
            with self.assertRaises(ValueError): self.read(max_recommendations=bad)
        for sid in (3,999):
            with self.assertRaises(ValueError): self.read(sid)

    def test_read_only_and_no_automatic_assignment(self):
        obs(self.con)
        before=self.con.total_changes
        output=self.read()
        self.assertEqual(before,self.con.total_changes)
        self.assertTrue(output['read_only'])
        self.assertFalse(output['auto_change_allowed'])
        self.assertFalse(output['automatic_assignments'])
        self.assertFalse(output['mastery_verified'])
        self.assertTrue(output['homework_is_not_mastery'])

    def test_two_low_days_targeted_review(self):
        obs(self.con, when='2026-10-10')
        obs(self.con, when='2026-10-18')
        result=self.read()
        self.assertEqual(result['recommendations'][0]['kind'],'TARGETED_REVIEW')
        self.assertIn('Fizik',result['recommendations'][0]['lesson'])
        self.assertIn('farklı ölçüm günleri',result['recommendations'][0]['basis'])

    def test_one_low_day_only_checks_errors(self):
        obs(self.con)
        result=self.read()
        self.assertEqual(result['recommendations'][0]['kind'],'CHECK_ERRORS')
        self.assertFalse(result['recommendations'][0]['learning_diagnosis'])

    def test_two_same_day_results_not_independent(self):
        obs(self.con,when='2026-10-18')
        obs(self.con,when='2026-10-18')
        self.assertEqual(self.read()['recommendations'][0]['kind'],'CHECK_ERRORS')

    def test_spaced_review_never_claims_forgetting(self):
        obs(self.con,when='2026-10-11',correct=5,wrong=1)
        result=self.read()
        self.assertEqual(result['recommendations'][0]['kind'],'SPACED_CHECK')
        self.assertEqual(result['recommendations'][0]['suggested_check_on'],'2026-10-13')
        self.assertNotIn('%',str(result['recommendations']))

    def test_quick_note_not_diagnosis(self):
        note(self.con)
        result=self.read()
        self.assertEqual(result['recommendations'][0]['kind'],'CLARIFY_OBSERVATION')
        self.assertIn('kesin neden değildir',result['recommendations'][0]['why'])

    def test_quick_note_easy_never_labels_mastery(self):
        note(self.con,code='easy')
        self.assertEqual(self.read()['state'],'NO_LEARNING_PRIORITY')

    def test_no_observation_not_false_healthy(self):
        result=self.read()
        self.assertEqual(result['source_quality'],'NO_OBSERVATIONS')
        self.assertFalse(result['mastery_verified'])
        self.assertEqual(result['recommendations'],[])

    def test_old_schema_no_migration_or_write(self):
        self.con.execute('DROP TABLE adaptive_observation_v25')
        self.con.execute('DROP TABLE adaptive_quick_note_v28')
        before=self.con.total_changes
        result=self.read()
        self.assertEqual(result['state'],'NO_LEARNING_PRIORITY')
        self.assertEqual(before,self.con.total_changes)

    def test_source_schema_partial_blocks(self):
        self.con.execute('DROP TABLE adaptive_observation_v25')
        self.con.execute('CREATE TABLE adaptive_observation_v25(student_id INTEGER)')
        self.assertEqual(self.read()['state'],'SOURCE_REVIEW')

    def test_wrong_owner_for_check_or_note_blocks_all(self):
        obs(self.con,sid=1,homework_id=201)
        self.assertEqual(self.read()['state'],'DATA_REVIEW')
        self.con.execute('DELETE FROM adaptive_observation_v25')
        note(self.con,homework_id=201)
        self.assertEqual(self.read()['state'],'DATA_REVIEW')

    def test_missing_related_homework_blocks(self):
        obs(self.con,homework_id=9999)
        self.assertEqual(self.read()['state'],'DATA_REVIEW')

    def test_bad_and_future_observations_excluded(self):
        obs(self.con,when='2026-11-01')
        obs(self.con,when='bad-date')
        obs(self.con,when='2026-10-10',correct=-3)
        result=self.read()
        self.assertEqual(result['evidence_counts']['excluded_checks'],3)
        self.assertEqual(result['recommendations'],[])

    def test_student_data_isolation(self):
        obs(self.con,sid=1)
        obs(self.con,sid=2,homework_id=201,lesson='Biyoloji',topic='Hücre')
        one=self.read(1)
        two=self.read(2)
        self.assertNotIn('Biyoloji',repr(one))
        self.assertNotIn('Fizik',repr(two))

    def test_source_link_review_blocks_with_no_data_leak(self):
        obs(self.con)
        result=read_learning_intervention_draft(self.con,1,today=DAY,hub_card=hub(state='LINK_REVIEW'))
        self.assertEqual(result['state'],'DATA_REVIEW')
        self.assertEqual(result['recommendations'],[])

    def test_stale_or_other_student_hub_rejected(self):
        for broken in [hub(2), hub(1,date(2026,10,19)), {'student_id':1},
                       {**hub(), 'read_only':False}]:
            with self.assertRaises(ValueError):
                read_learning_intervention_draft(self.con,1,today=DAY,hub_card=broken)

    def test_default_hub_blocks_unverified_legacy(self):
        result=read_learning_intervention_draft(self.con,1,today=DAY)
        self.assertEqual(result['state'],'DATA_REVIEW')
        self.assertEqual(result['recommendations'],[])

    def test_row_factory_preserved_and_query_only(self):
        obs(self.con)
        for factory in (None,sqlite3.Row):
            self.con.row_factory=factory
            self.con.execute('PRAGMA query_only=ON')
            try:
                result=self.read()
                self.assertEqual(result['recommendations'][0]['kind'],'CHECK_ERRORS')
                self.assertIs(self.con.row_factory,factory)
            finally:
                self.con.execute('PRAGMA query_only=OFF')

    def test_bounded_deduplicated_and_sorted(self):
        for idx in range(9):
            obs(self.con,lesson='Fizik',topic='Konular '+str(idx),correct=1,wrong=5)
        result=self.read()
        self.assertEqual(len(result['recommendations']),3)
        self.assertEqual(len({r['topic'] for r in result['recommendations']}),3)


if __name__ == '__main__':
    unittest.main()
