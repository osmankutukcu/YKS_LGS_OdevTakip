# -*- coding: utf-8 -*-
"""V3.5.63: evidence mapping, safety and assistant wiring (synthetic only)."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
import ast
import sqlite3
import unittest

from services.evidence_based_coach_v3563 import (
    STRATEGIES, SOURCES, map_learning_to_evidence_card, read_evidence_based_coach
)
from tests.test_learning_intervention_bridge_v3562 import schema, obs, note, db

TODAY = date(2026, 10, 20)


def learning(kind='SPACED_CHECK', sid=1):
    return {'schema':'learning_intervention_bridge_v3562', 'student_id':sid,
            'as_of':TODAY.isoformat(),'read_only':True,'auto_change_allowed':False,
            'state':'REVIEW_SUGGESTED','source_quality':'LOCAL_RECORDED_OBSERVATIONS',
            'recommendations':[{'kind':kind,'lesson':'Fizik','topic':'Kuvvet',
            'basis':'Kısa bağımsız yoklama','why':'Ölçüm kontrol adayı',
            'requires_teacher_approval':True,'auto_assignment':False,
            'suggested_check_on':None}]}


class EvidenceBasedCoachTests(unittest.TestCase):
    def test_mapping_uses_named_research_and_no_false_effect_claim(self):
        for kind in STRATEGIES:
            with self.subTest(kind=kind):
                result=map_learning_to_evidence_card(learning(kind),student_id=1,today=TODAY)
                self.assertEqual(result['state'],'REVIEW_SUGGESTED')
                self.assertFalse(result['scientific_effect_for_this_student_proven'])
                self.assertFalse(result['automatic_actions'])
                self.assertTrue(result['teacher_approval_required'])
                card=result['cards'][0]
                self.assertFalse(card['auto_assignment'])
                self.assertEqual(card['kind'],kind)
                self.assertTrue(card['reflection_question'])
                for source in card['references']:
                    self.assertIn(source['id'],SOURCES)
                    self.assertTrue(source['url'].startswith('https://'))

    def test_reject_mismatched_student_and_stale_date(self):
        for update in ({'student_id':2},{'as_of':'2026-09-01'},
                       {'read_only':False},{'auto_change_allowed':True},{'schema':'wrong'}):
            x={**learning(),**update}
            with self.assertRaises(ValueError):
                map_learning_to_evidence_card(x,student_id=1,today=TODAY)

    def test_insecure_assignment_cannot_be_promoted(self):
        for key,val in (('requires_teacher_approval',False),('auto_assignment',True)):
            source=learning()
            source['recommendations'][0][key]=val
            result=map_learning_to_evidence_card(source,student_id=1,today=TODAY)
            self.assertEqual(result['state'],'UNVERIFIED')
            self.assertFalse(result['cards'])

    def test_unknown_kind_and_missing_topic_fail_closed(self):
        x=learning('MIND_READING')
        self.assertEqual(map_learning_to_evidence_card(x,student_id=1,today=TODAY)['state'],'UNVERIFIED')
        x=learning()
        x['recommendations'][0]['topic']=''
        self.assertEqual(map_learning_to_evidence_card(x,student_id=1,today=TODAY)['state'],'UNVERIFIED')

    def test_blocked_and_no_data_do_not_create_diagnosis(self):
        for state,want in [('DATA_REVIEW','DATA_REVIEW'),('SOURCE_REVIEW','DATA_REVIEW'),
                           ('NO_LEARNING_PRIORITY','NO_SUGGESTION')]:
            x=learning()
            x['state']=state
            result=map_learning_to_evidence_card(x,student_id=1,today=TODAY)
            self.assertEqual(result['state'],want)
            self.assertEqual(result['cards'],[])

    def test_topic_dedup(self):
        x=learning()
        x['recommendations'].append({**x['recommendations'][0], 'kind':'CHECK_ERRORS'})
        r=map_learning_to_evidence_card(x,student_id=1,today=TODAY)
        self.assertEqual(len(r['cards']),1)

    def test_read_actual_synthetic_tables_does_not_write(self):
        con=db()
        schema(con)
        try:
            obs(con,when='2026-10-10')
            obs(con,when='2026-10-18')
            before=con.total_changes
            with patch('services.learning_intervention_bridge_v3562.read_coaching_evidence_hub') as mock:
                mock.return_value={'schema':'coaching_evidence_hub_v3561','student_id':1,
                    'as_of':TODAY.isoformat(),'read_only':True,'auto_change_allowed':False,
                    'state':'HOMEWORK_FOLLOWUP','evidence_level':'VERIFIED_LOCAL_HOMEWORK'}
                result=read_evidence_based_coach(con,1,today=TODAY)
            self.assertEqual(before,con.total_changes)
            self.assertEqual(result['state'],'REVIEW_SUGGESTED')
            self.assertEqual(result['cards'][0]['kind'],'TARGETED_REVIEW')
        finally:
            con.close()

    def test_sidecar_wires_background_read_and_uses_unchanged_inbox(self):
        root=Path(__file__).resolve().parents[1]
        source=(root/'ui/research_coaching_bridge_v3563.py').read_text(encoding='utf8')
        wiring=(root/'ui/homework_workspace_bridge_v21.py').read_text(encoding='utf8')
        ast.parse(source); ast.parse(wiring)
        self.assertIn('read_evidence_based_coach(con, self.sid)',source)
        self.assertIn('QThreadPool.globalInstance().start(job)',source)
        self.assertIn('source=\'checkbox\'',source)
        self.assertIn('serial != self._serial or sid != self._current_sid',source)
        self.assertIn('con.set_progress_handler',source)
        self.assertIn('ResearchCoachingBridgeV3563(form, self.secretary)',wiring)
        self.assertIn('self.research_coach.on_student_changed(sid)',wiring)
        for token in ('INSERT INTO odev','UPDATE odev SET','DELETE FROM odev'):
            self.assertNotIn(token,source)

    def test_unchanged_assistant_file_hash(self):
        import hashlib
        root=Path(__file__).resolve().parents[1]
        data=(root/'ui/smart_coach_secretary_toast.py').read_bytes()
        self.assertIn(hashlib.sha256(data).hexdigest(),{
            '6f48b901c3449a0612c16058bc40e6a74a797ee594d34e417970e6f5f7758ae9',
            'c3d06192cd979a7b6c478d75a4c96f85d9f0509eec05424c978204ce64850329',
        })

if __name__=='__main__': unittest.main()
