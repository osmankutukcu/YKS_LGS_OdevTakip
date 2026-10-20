# -*- coding: utf-8 -*-
from datetime import date, datetime
from unittest.mock import patch
import sqlite3
import unittest

from services.coaching_evidence_hub_v3561 import read_coaching_evidence_hub
from tests.test_v3536_academic_actions import db

DAY = date(2026, 10, 18)


class CoachingEvidenceHubTests(unittest.TestCase):
    def setUp(self):
        self.con = db()

    def tearDown(self):
        self.con.close()

    def test_bad_identity_and_day_rejected(self):
        for sid in (None, '1', 0, -1, True, 1.0):
            with self.subTest(sid=sid), self.assertRaises(ValueError):
                read_coaching_evidence_hub(self.con, sid, today=DAY)
        for bad in ('2026-10-18', datetime(2026,10,18)):
            with self.assertRaises(ValueError):
                read_coaching_evidence_hub(self.con, 1, today=bad)

    def test_homework_priority_when_both_sources_verified(self):
        before = self.con.total_changes
        def verified(_con, sid, *, today):
            return {'student_id': sid, 'state': 'PLAN_SUGGESTION', 'academic_card': {'student_id': sid,
                    'state': 'PLAN_SUGGESTION', 'next_step': 'Haftalık plan kontrolü',
                    'basis': 'Koçluk planı'}}
        with patch('services.coaching_evidence_hub_v3561.read_coaching_snapshot', side_effect=verified):
            result = read_coaching_evidence_hub(self.con, 1, today=DAY)
        self.assertEqual(result['state'], 'HOMEWORK_FOLLOWUP')
        self.assertEqual(result['priority'], 'HOMEWORK_REVIEW')
        self.assertEqual(result['student_id'], 1)
        self.assertIn('Fizik', result['next_step'])
        self.assertEqual(self.con.total_changes, before)
        self.assertTrue(result['homework_is_not_mastery'])
        self.assertFalse(result['auto_change_allowed'])
        self.assertEqual(len(result['suggestions']), 1)

    def test_other_student_not_leaked(self):
        one = read_coaching_evidence_hub(self.con, 1, today=DAY)
        two = read_coaching_evidence_hub(self.con, 2, today=DAY)
        self.assertNotEqual(one['student_id'], two['student_id'])
        self.assertNotIn('Biyoloji', repr(one))
        self.assertNotIn('Fizik', repr(two))
        self.assertNotIn('05551234567', repr(one))

    def test_conflicting_owner_blocks_suggestions(self):
        self.con.execute("INSERT INTO odev_satir(id,ogrenci_id,kume_id,odev_id,ders,durum) VALUES(301,2,100,101,'Fizik','devam')")
        for sid in (1,2):
            result = read_coaching_evidence_hub(self.con,sid,today=DAY)
            self.assertEqual(result['state'], 'LINK_REVIEW')
            self.assertEqual(result['suggestions'], [])

    def test_missing_source_is_not_no_priority(self):
        self.con.execute('DROP TABLE odev_satir')
        result = read_coaching_evidence_hub(self.con, 1, today=DAY)
        self.assertEqual(result['state'], 'UNVERIFIED')
        self.assertEqual(result['suggestions'], [])

    def test_row_factory_preserved(self):
        for factory in (None, sqlite3.Row):
            with self.subTest(factory=factory):
                self.con.row_factory = factory
                read_coaching_evidence_hub(self.con, 1, today=DAY)
                self.assertIs(self.con.row_factory, factory)

    def test_readonly_connection_and_coherent_snapshot(self):
        # SQLite query_only verifies no update regardless of read adapter.
        self.con.execute('PRAGMA query_only = ON')
        self.con.execute('BEGIN')
        try:
            result = read_coaching_evidence_hub(self.con,1,today=DAY)
            self.assertEqual(result['state'], 'UNVERIFIED')
            self.assertEqual(result['suggestions'], [])
        finally:
            self.con.rollback()

    def test_missing_student_never_looks_like_clean_student(self):
        result = read_coaching_evidence_hub(self.con,999,today=DAY)
        self.assertEqual(result['state'], 'UNVERIFIED')

    def test_mismatched_action_source_blocks(self):
        def wrong(*args,**kwargs):
            return {'student_id': 2, 'state': 'HOMEWORK_FOLLOWUP', 'next_step': 'Wrong'}
        with patch('services.coaching_evidence_hub_v3561.read_student_action_card', side_effect=wrong):
            result=read_coaching_evidence_hub(self.con,1,today=DAY)
        self.assertEqual(result['state'], 'IDENTITY_MISMATCH')
        self.assertEqual(result['suggestions'],[])

    def test_mismatched_inner_shared_card_blocked(self):
        def wrong(*args,**kwargs):
            return {'student_id': 1, 'academic_card': {'student_id': 2, 'state': 'RECOMMENDATION'}}
        with patch('services.coaching_evidence_hub_v3561.read_coaching_snapshot', side_effect=wrong):
            result=read_coaching_evidence_hub(self.con,1,today=DAY)
        self.assertEqual(result['state'], 'IDENTITY_MISMATCH')
        self.assertEqual(result['suggestions'],[])

    def test_no_duplicate_plan_advice(self):
        self.con.execute('DELETE FROM odev WHERE ogrenci_id=1')
        card=read_coaching_evidence_hub(self.con,1,today=DAY)
        self.assertLessEqual(len(card['suggestions']),1)

    def test_no_unverified_claim_of_weekly_calendar_or_remote(self):
        card=read_coaching_evidence_hub(self.con,1,today=DAY)
        self.assertFalse(card['weekly_calendar_verified'])
        self.assertFalse(card['remote_data_verified'])
        self.assertTrue(card['requires_teacher_approval'])


if __name__ == '__main__': unittest.main()
