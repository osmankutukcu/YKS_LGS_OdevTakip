# -*- coding: utf-8 -*-
import unittest
from datetime import date
from pathlib import Path
from services.coaching_action_center_v3567 import build_action_center_card, compact_teacher_line

TODAY = date(2026, 10, 20)


def sample():
    return {'schema': 'automatic_coaching_cycle_v3565', 'student_id': 17,
            'as_of': '2026-10-20', 'state': 'ACTION_SUGGESTED',
            'read_only': True, 'teacher_approval_required': True,
            'auto_change_allowed': False, 'automatic_assignments': False,
            'automatic_messages': False, 'homework_is_not_mastery': True,
            'mastery_verified': False, 'causality_verified': False,
            'next_actions': [dict(kind='INTERVENTION_FOLLOWUP', lesson='Fizik', topic='Hareket',
                reason='7. gün kontrolü', next_step='Kısa bağımsız ölçüm yapın',
                priority=0, read_only=True, teacher_approval_required=True,
                auto_assignment=False, auto_message=False,
                mastery_verified=False, causality_verified=False)]}


class ActionCenterTests(unittest.TestCase):
    def test_shared_first_action_and_teacher_line(self):
        x = build_action_center_card(sample(), 17, today=TODAY)
        self.assertEqual(x['state'], 'ACTION_SUGGESTED')
        self.assertEqual(x['title'], 'Müdahale sonrası ölçüm')
        self.assertEqual(x['area'], 'Fizik / Hareket')
        self.assertEqual(x['action_key'], 'btnOgrenme')
        self.assertIn('Öğretmen onayı', compact_teacher_line(x, 17, today=TODAY))

    def test_wrong_student_and_date(self):
        self.assertEqual(build_action_center_card(sample(), 18, today=TODAY)['state'], 'DATA_REVIEW')
        self.assertEqual(build_action_center_card(sample(), 17, today=date(2026,10,21))['state'], 'DATA_REVIEW')
        self.assertEqual(compact_teacher_line(build_action_center_card(sample(), 17,today=TODAY),18,today=TODAY),'')
        with self.assertRaises(ValueError): build_action_center_card(sample(), True,today=TODAY)

    def test_rejects_unsafe_cycle(self):
        for key, value in [('automatic_assignments', True), ('automatic_messages', True),
                           ('read_only', False),('teacher_approval_required',False),
                           ('auto_change_allowed',True),('homework_is_not_mastery',False),
                           ('mastery_verified',True),('causality_verified', True),
                           ('student_id', True)]:
            with self.subTest(key=key):
                bad={**sample(),key:value}
                self.assertEqual(build_action_center_card(bad,17,today=TODAY)['state'],'DATA_REVIEW')

    def test_rejects_unsafe_action_even_when_second(self):
        first=sample()
        for key,value in [('auto_assignment',True),('auto_message',True),
                          ('mastery_verified',True),('causality_verified',True),
                          ('teacher_approval_required',False),('read_only',False),
                          ('priority',True),('kind','MYSTERY')]:
            with self.subTest(key=key):
                other={**first['next_actions'][0],key:value}
                bad={**first,'next_actions':[first['next_actions'][0],other]}
                self.assertEqual(build_action_center_card(bad,17,today=TODAY)['state'],'DATA_REVIEW')

    def test_no_priority_is_not_mastery(self):
        card=sample()
        card.update(state='NO_PRIORITY',next_actions=[])
        x=build_action_center_card(card,17,today=TODAY)
        self.assertEqual(x['state'],'NO_PRIORITY')
        self.assertIn('öğrenme kanıtlanmış sayılmaz',x['reason'])
        self.assertEqual(compact_teacher_line(x,17,today=TODAY),'')

    def test_data_review_is_fail_closed(self):
        x=build_action_center_card({},17,today=TODAY)
        self.assertEqual(x['state'],'DATA_REVIEW')
        self.assertEqual(x['action_key'],'')
        self.assertEqual(compact_teacher_line(x,17,today=TODAY),'')

    def test_core_forms_and_legacy_assistant_untouched(self):
        root=Path(__file__).resolve().parents[1]
        for f in ('ui/homework_form.py','ui/odev_kontrol.py','ui/coach_assistant_v1.py'):
            # last is a directory in most builds; protected guard is authoritative.
            if (root/f).is_file():
                self.assertNotIn('coaching_action_center_v3567',(root/f).read_text(encoding='utf-8'))

if __name__ == '__main__': unittest.main()

class SharedInterfaceContractTests(unittest.TestCase):
    def test_all_three_surfaces_reuse_one_model(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('ui/research_coaching_bridge_v3563.py',
                     'ui/student360_journey_sidecar_v3566.py',
                     'services/teacher_copilot_v5.py'):
            self.assertIn('build_action_center_card', (root / name).read_text(encoding='utf-8'))
        self.assertIn('compact_teacher_line', (root / 'ui/teacher_copilot_strip_v5.py').read_text(encoding='utf-8'))

    def test_fallback_remains_available(self):
        root = Path(__file__).resolve().parents[1]
        code = (root / 'ui/research_coaching_bridge_v3563.py').read_text(encoding='utf-8')
        self.assertIn('self._show_cycle_legacy_v3565(sid, cycle)', code)
        self.assertIn('coaching_action_center_v3567_enabled', code)
        self.assertIn('coaching_action_center_v3567_enabled', (root / 'ui/student360_journey_sidecar_v3566.py').read_text(encoding='utf-8'))
        self.assertIn('coaching_action_center_v3567_enabled', (root / 'ui/teacher_copilot_strip_v5.py').read_text(encoding='utf-8'))

    def test_no_auto_click_or_synthetic_checkbox_actions_in_addon(self):
        root = Path(__file__).resolve().parents[1]
        data = (root / 'services/coaching_action_center_v3567.py').read_text(encoding='utf8')
        for forbidden in ('INSERT INTO', 'UPDATE odev', 'DELETE FROM', '.click()', '.commit('):
            self.assertNotIn(forbidden, data)
