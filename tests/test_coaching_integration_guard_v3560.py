import sqlite3
import unittest
from unittest.mock import patch
from datetime import date
from services.coaching_integration_guard_v3560 import read_coaching_snapshot


class CoachingIntegrationGuardTests(unittest.TestCase):
    def test_rejects_invalid_identity(self):
        con = sqlite3.connect(':memory:')
        for value in (None, 0, -1, True, '2'):
            with self.assertRaises(ValueError):
                read_coaching_snapshot(con, value)
        con.close()

    def test_rejects_invalid_day(self):
        with sqlite3.connect(':memory:') as con:
            with self.assertRaises(ValueError):
                read_coaching_snapshot(con, 1, today='2026-10-20')

    def test_delegates_to_existing_verified_card_without_writes(self):
        with sqlite3.connect(':memory:') as con:
            with patch('services.shared_academic_decision_v3530.read_shared_academic_card', return_value={'state': 'UNVERIFIED'}) as reader:
                result = read_coaching_snapshot(con, 7, today=date(2026, 10, 20))
            reader.assert_called_once_with(con, 7, today=date(2026, 10, 20))
            self.assertEqual(result['student_id'], 7)
            self.assertTrue(result['read_only'])
            self.assertEqual(result['academic_card']['state'], 'UNVERIFIED')
