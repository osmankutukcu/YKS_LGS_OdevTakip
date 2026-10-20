# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from services.coaching_journey_summary_v3566 import format_journey_summary


class CoachingJourneyTests(unittest.TestCase):
    def setUp(self):
        self.card = {
            'schema': 'automatic_coaching_cycle_v3565', 'student_id': 17,
            'as_of': '2026-10-20', 'state': 'ACTION_SUGGESTED',
            'read_only': True, 'teacher_approval_required': True,
            'auto_change_allowed': False, 'automatic_assignments': False,
            'automatic_messages': False,
            'next_actions': [{
                'kind': 'INTERVENTION_FOLLOWUP', 'lesson': 'Fizik', 'topic': 'Hareket',
                'reason': 'İzlem zamanı', 'next_step': 'Kısa bir kontrol yapın',
                'read_only': True, 'teacher_approval_required': True,
                'auto_assignment': False, 'auto_message': False,
            }],
        }

    def test_valid_inbox_data_prints_conservative_next_step(self):
        value = format_journey_summary(self.card, 17)
        self.assertIn('Fizik / Hareket', value)
        self.assertIn('Kısa bir kontrol', value)
        self.assertIn('nedensel', value)
        self.assertIn('öğretmendedir', value)

    def test_rejects_cross_student_and_bool_id(self):
        self.assertNotIn('Fizik', format_journey_summary(self.card, 18))
        with self.assertRaises(ValueError):
            format_journey_summary(self.card, True)

    def test_blocks_unsafe_flags(self):
        for key, value in [('read_only', False), ('auto_change_allowed', True),
                           ('automatic_assignments', True), ('teacher_approval_required', False),
                           ('automatic_messages', True)]:
            with self.subTest(field=key):
                bad = {**self.card, key: value}
                self.assertNotIn('Fizik', format_journey_summary(bad, 17))

    def test_blocks_unsafe_step(self):
        for key, value in [('auto_assignment', True), ('auto_message', True),
                           ('teacher_approval_required', False), ('read_only', False)]:
            with self.subTest(field=key):
                bad = {**self.card, 'next_actions': [{**self.card['next_actions'][0], key: value}]}
                self.assertNotIn('Fizik', format_journey_summary(bad, 17))

    def test_blocks_unknown_step(self):
        bad = {**self.card, 'next_actions': [{**self.card['next_actions'][0], 'kind': 'GUESSED_DIAGNOSIS'}]}
        self.assertNotIn('Fizik', format_journey_summary(bad, 17))

    def test_blocks_too_many_actions(self):
        bad = {**self.card, 'next_actions': self.card['next_actions'] * 4}
        self.assertNotIn('Fizik', format_journey_summary(bad, 17))

    def test_data_review_does_not_disclose_actions(self):
        bad = {**self.card, 'state': 'DATA_REVIEW'}
        self.assertIn('durduruldu', format_journey_summary(bad, 17))
        self.assertNotIn('Hareket', format_journey_summary(bad, 17))

    def test_no_priority_is_not_mastery(self):
        bad = {**self.card, 'state': 'NO_PRIORITY', 'next_actions': []}
        self.assertIn('öğrenmenin kanıtlandığını göstermez', format_journey_summary(bad, 17))

    def test_existing_forms_unchanged_and_no_direct_sql_in_addon(self):
        root = Path(__file__).resolve().parents[1]
        bridge = (root / 'ui/research_coaching_bridge_v3563.py').read_text(encoding='utf8')
        panel = (root / 'ui/student360_panel_v16.py').read_text(encoding='utf8')
        sidecar = (root / 'ui/student360_journey_sidecar_v3566.py').read_text(encoding='utf8')
        self.assertIn('install_live_updates(', bridge)
        self.assertIn('student_attr=\'_secili_ogrenci_id\'', bridge)
        self.assertIn('self._journey_v3566.request(sid)', panel)
        self.assertIn('PRAGMA query_only=ON', sidecar)
        self.assertIn('QThreadPool.globalInstance().start(job)', sidecar)
        self.assertIn('sid != getattr(self.panel', sidecar)
        self.assertNotIn('con.commit(', sidecar)
        self.assertNotIn('INSERT INTO', sidecar)


if __name__ == '__main__':
    unittest.main()
