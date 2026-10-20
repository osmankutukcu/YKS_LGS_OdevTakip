# -*- coding: utf-8 -*-
"""V3564 synthetic tests: identity, book matching, read-only, workload, UI."""
import ast
from datetime import date
import hashlib
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from services.adaptive_coaching_v30.drafts import fingerprint
from services.science_wizard_alignment_v3564 import (
    align_research_with_existing_draft, read_science_wizard_alignment)

DAY=date(2026,10,20)


def research(sid=1, state='REVIEW_SUGGESTED', **updates):
    base={'schema':'evidence_based_coach_v3563','student_id':sid,
          'as_of':DAY.isoformat(), 'read_only':True,'automatic_actions':False,
          'teacher_approval_required':True,'state':state,
          'cards':[{'kind':'TARGETED_REVIEW','lesson':'Fizik','topic':'Kuvvet',
               'observation':'Ölçümler düşük','strategy':'Hedefli geri bildirim',
               'teacher_activity':'Bağımsız tekrar testi','requires_teacher_approval':True,
               'auto_assignment':False,'suggested_check_on':None}]}
    return {**base,**updates}


def draft(sid=1,book='Fizik Soru Bankası',lesson='Fizik',topic='Kuvvet',
          overloaded=False):
    items=[{'lesson':lesson,'book':book,'topic':topic,'minutes':20,
        'mode':'Hedefli soru','details':'Kısa test','note':None,
        'default_selected':True,'transferable':bool(book)}]
    obj={'student_id':sid,'generated_on':DAY.isoformat(),
         'preferences':{'weekly_minutes':240},'overload_note':overloaded,
         'items':items}
    obj['fingerprint']=fingerprint(obj)
    return obj


class ScienceWizardAlignmentTests(unittest.TestCase):
    def align(self,r=None,d=None,sid=1):
        return align_research_with_existing_draft(
            r if r is not None else research(sid),
            d if d is not None else draft(sid),student_id=sid,today=DAY)

    def test_research_matches_real_draft_and_does_not_change_original(self):
        r,d=research(),draft()
        b=repr(d)
        x=self.align(r,d)
        self.assertEqual(x['state'],'MATCHED')
        self.assertEqual(repr(d),b)
        self.assertEqual(x['matched'][0]['existing_book'],'Fizik Soru Bankası')
        self.assertEqual(x['suggested_minutes'],20)
        for f in ('read_only','teacher_approval_required','requires_live_matrix_recheck'):
            self.assertTrue(x[f])
        for f in ('auto_assignment','auto_selection'):
            self.assertFalse(x[f])

    def test_invalid_students_and_dates_raise(self):
        for sid in (-1,0,True,'1',None):
            with self.assertRaises(ValueError):
                align_research_with_existing_draft(research(),draft(),student_id=sid,today=DAY)
        with self.assertRaises(ValueError):
            self.align(r=research(as_of='2026-09-01'))
        with self.assertRaises(ValueError):
            self.align(r=research(student_id=2))
        with self.assertRaises(ValueError):
            self.align(r=research(read_only=False))
        with self.assertRaises(ValueError):
            self.align(r=research(automatic_actions=True))
        with self.assertRaises(ValueError):
            self.align(r=research(teacher_approval_required=False))

    def test_bad_draft_student_or_date_blocks(self):
        self.assertEqual(self.align(d=draft(2))['state'],'DRAFT_REVIEW')
        d=draft(); d['generated_on']='2026-10-19'
        self.assertEqual(self.align(d=d)['state'],'DRAFT_REVIEW')

    def test_tampered_fingerprint_blocks(self):
        d=draft(); d['items'][0]['topic']='Other'
        self.assertEqual(self.align(d=d)['state'],'DRAFT_REVIEW')
        d=draft(); d['fingerprint']='fake'
        self.assertEqual(self.align(d=d)['state'],'DRAFT_REVIEW')

    def test_no_invented_book_or_topic(self):
        for d in (draft(book=''),draft(topic='Kaldırma Kuvveti'),draft(lesson='Matematik')):
            x=self.align(d=d)
            self.assertEqual(x['state'],'NO_VERIFIED_BOOK_MATCH')
            self.assertEqual(x['matched'],[])
            self.assertFalse(x['auto_assignment'])

    def test_uncertain_research_never_assigns(self):
        for state in ('DATA_REVIEW','UNVERIFIED','NO_SUGGESTION'):
            x=self.align(r=research(state=state))
            self.assertEqual(x['matched'],[])
            self.assertFalse(x['auto_assignment'])
        r=research();r['cards'][0]['auto_assignment']=True
        self.assertEqual(self.align(r=r)['state'],'DATA_REVIEW')

    def test_ambiguous_duplicate_book_candidates_block(self):
        d=draft(); second=dict(d['items'][0]);second['book']='Başka Kitap'
        d['items'].append(second);d['fingerprint']=fingerprint(d)
        self.assertEqual(self.align(d=d)['matched'],[])

    def test_bounded_under_workload_and_dedup(self):
        r=research();r['cards'].append({**r['cards'][0], 'topic':'İş Güç Enerji'})
        d=draft(overloaded=True)
        d['items'].append({**d['items'][0],'topic':'İş Güç Enerji'})
        d['fingerprint']=fingerprint(d)
        x=self.align(r,d)
        self.assertEqual(len(x['matched']),1)
        self.assertEqual(len(x['not_matched']),1)
        self.assertTrue(x['overload_limited'])

    def test_missing_optional_v25_tables_do_not_create_any(self):
        with sqlite3.connect(':memory:') as con:
            before=con.total_changes
            x=read_science_wizard_alignment(con,1,today=DAY,research_card=research())
            self.assertEqual(x['state'],'DRAFT_NOT_INITIALIZED')
            self.assertEqual(con.total_changes,before)
            self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0],0)

    def test_readonly_with_existing_tables_uses_v30_only(self):
        with sqlite3.connect(':memory:') as con:
            for t in ('adaptive_observation_v25','adaptive_profile_v25','adaptive_blocker_v25'):
                con.execute('CREATE TABLE '+t+'(id integer)')
            con.execute('PRAGMA query_only=ON')
            with patch('services.science_wizard_alignment_v3564.build_draft',return_value=draft()) as builder:
                x=read_science_wizard_alignment(con,1,today=DAY,research_card=research())
                self.assertEqual(x['state'],'MATCHED')
                builder.assert_called_once_with(con,1,today=DAY,max_items=12)

    def test_sidecar_inbox_link_only_no_auto_transfer(self):
        root=Path(__file__).resolve().parents[1]
        sidecar=(root/'ui/research_coaching_bridge_v3563.py').read_text(encoding='utf8')
        ast.parse(sidecar)
        self.assertIn('read_science_wizard_alignment(',sidecar)
        self.assertIn('target_key=\'btnOgrenme\'',sidecar)
        self.assertIn("source='checkbox'",sidecar)
        self.assertNotIn('._wizard_transfer_tasks(',sidecar)
        self.assertNotIn('btnSihirbaz.click()',sidecar)
        self.assertNotIn('INSERT INTO odev',sidecar)

    def test_protected_forms_and_legacy_assistant_unchanged_from_v3563(self):
        root=Path(__file__).resolve().parents[1]
        # Stronger golden comparison is performed against the unpacked v3.5.63
        # archive by the release script; here pin protected assistant bytes.
        expected={'6f48b901c3449a0612c16058bc40e6a74a797ee594d34e417970e6f5f7758ae9',
                  'c3d06192cd979a7b6c478d75a4c96f85d9f0509eec05424c978204ce64850329'}
        digest=hashlib.sha256((root/'ui/smart_coach_secretary_toast.py').read_bytes()).hexdigest()
        self.assertIn(digest,expected)

if __name__=='__main__':unittest.main()
