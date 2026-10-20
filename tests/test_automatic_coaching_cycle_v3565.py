# -*- coding: utf-8 -*-
"""v3.5.65 synthetic tests; never use real students or production files."""
from datetime import date
from pathlib import Path
import ast
import hashlib
import sqlite3
import unittest

from services.automatic_coaching_cycle_v3565 import (
    combine_cycle_sources, read_automatic_coaching_cycle)
from tests.test_v3536_academic_actions import db
from tests.test_learning_intervention_bridge_v3562 import schema, obs

DAY = date(2026, 10, 20)


def hub(sid=1, **extra):
    return {'schema':'coaching_evidence_hub_v3561','student_id':sid,
            'as_of':DAY.isoformat(),'read_only':True,'auto_change_allowed':False,
            'state':'NO_VERIFIED_PRIORITY','priority':'ROUTINE',
            'evidence_level':'LOCAL_RECORDS_ONLY','sources':{}, **extra}


def learning(sid=1, actions=None, **extra):
    return {'schema':'learning_intervention_bridge_v3562','student_id':sid,
            'as_of':DAY.isoformat(),'read_only':True,'auto_change_allowed':False,
            'automatic_assignments':False,'state':'REVIEW_SUGGESTED' if actions else 'NO_LEARNING_PRIORITY',
            'source_quality':'LOCAL_RECORDED_OBSERVATIONS' if actions else 'NO_OBSERVATIONS',
            'recommendations':actions or [],
            'evidence_counts':{'valid_checks':2 if actions else 0,'quick_notes':0}, **extra}


def action(kind='CHECK_ERRORS', lesson='Fizik', topic='Kuvvet'):
    return {'kind':kind,'lesson':lesson,'topic':topic,'why':'Gözlenen düşük doğruluk',
            'teacher_next_step':'Bağımsız kısa ölçüm yapın.', 'suggested_check_on':None,
            'basis':'V25 kayıtları', 'requires_teacher_approval':True,'auto_assignment':False}


def followup(sid=1,status='DAY7_RECHECK_DUE'):
    return {'student_id':sid,'as_of':DAY.isoformat(), 'state':'OBSERVED',
            'student_data_written':False,
            'records':[{'student_id':sid,'status':status,'lesson':'Fizik','topic':'Kuvvet',
                        'reason':'Kontrol zamanı'}]}


class AutomaticCoachingCycleTests(unittest.TestCase):
    def make(self,h=None,l=None,f=None,sid=1):
        return combine_cycle_sources(h or hub(sid),l or learning(sid),f,
                                     student_id=sid,today=DAY)

    def test_source_identity_and_timestamp_fail_closed(self):
        for h in [hub(2),{**hub(), 'as_of':'2026-10-19'}, {**hub(),'auto_change_allowed':True}]:
            x=self.make(h=h)
            self.assertEqual(x['state'],'DATA_REVIEW')
            self.assertEqual(x['next_actions'],[])
        for l in [learning(2),learning(read_only=False), learning(automatic_assignments=True)]:
            self.assertEqual(self.make(l=l)['state'],'DATA_REVIEW')
        for bad in (0,True,'1',None,-4):
            with self.assertRaises(ValueError):
                combine_cycle_sources(hub(), learning(), None,student_id=bad,today=DAY)

    def test_unverified_and_link_review_never_recommend(self):
        for state in ['LINK_REVIEW','IDENTITY_MISMATCH','UNVERIFIED','REVIEW']:
            self.assertEqual(self.make(h=hub(state=state))['next_actions'], [])
        self.assertEqual(self.make(h=hub(priority='DATA_REVIEW'))['state'],'DATA_REVIEW')
        self.assertEqual(self.make(l=learning(state='SOURCE_REVIEW'))['next_actions'],[])
        self.assertEqual(self.make(l=learning(state='UNVERIFIED'))['next_actions'],[])

    def test_independent_checks_generate_approved_action_only(self):
        card=self.make(l=learning(actions=[action()]))
        self.assertEqual(card['state'],'ACTION_SUGGESTED')
        self.assertEqual(card['next_actions'][0]['kind'],'INDEPENDENT_RECHECK')
        self.assertTrue(card['read_only'])
        self.assertTrue(card['homework_is_not_mastery'])
        self.assertFalse(card['automatic_assignments'])
        self.assertFalse(card['automatic_messages'])
        self.assertFalse(card['causality_verified'])

    def test_approved_followup_preferred_and_deduped_with_same_topic(self):
        card=self.make(l=learning(actions=[action('TARGETED_REVIEW')]),f=followup())
        self.assertEqual([x['kind'] for x in card['next_actions']], ['INTERVENTION_FOLLOWUP'])
        self.assertEqual(card['pending_count'],1)
        self.assertFalse(card['next_actions'][0]['auto_assignment'])

    def test_teacher_reviewed_intervention_does_not_renotify(self):
        self.assertEqual(self.make(f=followup(status='TEACHER_REVIEWED'))['state'],'NO_PRIORITY')

    def test_approval_source_wrong_student_fails_closed(self):
        self.assertEqual(self.make(f=followup(2))['state'],'DATA_REVIEW')
        f=followup();f['records'][0]['student_id']=2
        self.assertEqual(self.make(f=f)['state'],'DATA_REVIEW')

    def test_due_future_check_not_advertised_today(self):
        a=action('SPACED_CHECK');a['suggested_check_on']='2026-10-25'
        self.assertEqual(self.make(l=learning(actions=[a]))['next_actions'],[])
        a['suggested_check_on']='2026-10-19'
        self.assertEqual(self.make(l=learning(actions=[a]))['next_actions'][0]['kind'], 'SPACED_RETRIEVAL')

    def test_no_claim_of_completion_without_canonical_counts(self):
        self.assertEqual(self.make()['next_actions'],[])
        h=hub(canonical_focus={'student_id':1,'state':'OBSERVED','completed_tasks':2})
        x=self.make(h=h)
        self.assertEqual(x['next_actions'][0]['kind'],'OPTIONAL_INDEPENDENT_CHECK')
        self.assertEqual(x['next_actions'][0]['topic'],'')
        self.assertNotIn('öğrendi',repr(x))

    def test_completed_not_if_canonical_uncertain_or_other_student(self):
        for focus in ({'student_id':2,'state':'OBSERVED','completed_tasks':2},
                      {'student_id':1,'state':'LINK_REVIEW','completed_tasks':2},
                      {'student_id':1,'state':'OBSERVED','completed_tasks':0}):
            self.assertEqual(self.make(h=hub(canonical_focus=focus))['next_actions'],[])

    def test_bounded_priority_and_unique_topics(self):
        acts=[action(topic=f'Konu {i}') for i in range(9)]
        x=self.make(l=learning(actions=acts))
        self.assertLessEqual(len(x['next_actions']),2)
        self.assertEqual(len({(a['lesson'],a['topic']) for a in x['next_actions']}),len(x['next_actions']))
        self.assertEqual(self.make(l=learning(actions=acts), f=followup())['next_actions'][0]['kind'],
                         'INTERVENTION_FOLLOWUP')

    def test_actual_read_only_sqlite_with_no_intervention_table(self):
        with db() as con:
            schema(con)
            obs(con)
            before=con.total_changes
            con.execute('PRAGMA query_only=ON')
            x=read_automatic_coaching_cycle(con,1,today=DAY)
            self.assertTrue(x['read_only'])
            self.assertEqual(con.total_changes,before)
            self.assertEqual(x['student_id'],1)
            self.assertIn(x['state'], ('ACTION_SUGGESTED','DATA_REVIEW','NO_PRIORITY'))
            self.assertFalse(x['automatic_assignments'])

    def test_invalid_student_rejected_before_query(self):
        with sqlite3.connect(':memory:') as con:
            for bad in (0,-1,True,'1',None):
                with self.assertRaises(ValueError):
                    read_automatic_coaching_cycle(con,bad,today=DAY)

    def test_read_only_optional_completed_homework_case(self):
        with db() as con:
            before=con.total_changes
            con.execute('PRAGMA query_only=ON')
            con.execute('PRAGMA query_only=OFF')
            con.execute("UPDATE odev SET durum='tamam' WHERE id=101")
            con.execute('PRAGMA query_only=ON')
            before=con.total_changes
            result=read_automatic_coaching_cycle(con,1,today=DAY)
            self.assertEqual(con.total_changes,before)
            self.assertEqual(result['student_id'],1)
            # The synthetic DB lacks a required V3529 evidence source; even a
            # completed task must NOT bypass that source-integrity gate.
            self.assertEqual(result['state'],'DATA_REVIEW')
            self.assertEqual(result['next_actions'],[])

    def test_no_protected_files_modified_and_sidecar_hook_is_noninvasive(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'ui/research_coaching_bridge_v3563.py').read_text(encoding='utf8')
        ast.parse(source)
        self.assertIn('read_automatic_coaching_cycle(con, self.sid)',source)
        self.assertIn("button.clicked.connect(self._schedule_refresh)",source)
        self.assertIn("source='checkbox'",source)
        self.assertNotIn('._wizard_transfer_tasks(',source)
        self.assertNotIn('INSERT INTO odev',source)
        self.assertNotIn('btnKontrol.clicked.connect(',source)
        digest=hashlib.sha256((root/'ui/smart_coach_secretary_toast.py').read_bytes()).hexdigest()
        self.assertIn(digest,{
            '6f48b901c3449a0612c16058bc40e6a74a797ee594d34e417970e6f5f7758ae9',
            'c3d06192cd979a7b6c478d75a4c96f85d9f0509eec05424c978204ce64850329',
        })

if __name__=='__main__': unittest.main()
