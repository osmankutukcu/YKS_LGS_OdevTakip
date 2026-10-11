"""Opt-in daily lifestyle scheduling and profile preservation regressions."""
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_planning_constraints_v3511 import sample
from services.planning_constraints import availability_for_week, free_minutes, serialize_details, parse_details
from services.smart_calendar import SmartCalendarService


def advanced_config(**extra):
    data = sample(school_by_day={}, blocks=[], empty='Yok', max=180)
    data['advanced_enabled'] = True
    data['advanced_days'] = {
        '0': {'wake': '07:15', 'bed': '22:30', 'study_start': '18:00',
              'study_end': '19:30', 'max': 80,
              'second_window': ['20:00', '21:30']},
        '5': {'wake': '09:00', 'bed': '23:00', 'study_start': '10:00',
              'study_end': '12:00', 'max': 180, 'second_window': ['17:00', '19:00']},
    }
    data.update(extra)
    return data


class AdvancedProfileTests(unittest.TestCase):
    def test_each_day_different_wake_bed_study_windows(self):
        windows = availability_for_week(advanced_config())
        self.assertEqual(windows[0], [(1080, 1170), (1200, 1290)])
        self.assertEqual(windows[5], [(600, 720), (1020, 1140)])
        self.assertEqual(windows[1], [(420, 1320)])

    def test_blocks_carved_out_of_both_sessions(self):
        data = advanced_config(blocks=['Pazartesi [20:45-21:15] Özel ders'])
        self.assertEqual(availability_for_week(data)[0],
                         [(1080, 1170), (1200, 1245), (1275, 1290)])

    def test_second_window_within_sleep_not_worked_after_bed(self):
        data = advanced_config()
        data['advanced_days']['0']['bed'] = '21:00'
        with self.assertRaisesRegex(ValueError, 'yatış'):
            availability_for_week(data)

    def test_overlapping_study_windows_rejected(self):
        data = advanced_config()
        data['advanced_days']['0']['second_window'] = ['19:00', '20:00']
        with self.assertRaisesRegex(ValueError, 'üst üste'):
            availability_for_week(data)

    def test_sleep_and_study_window_invalid_rejected(self):
        data = advanced_config()
        data['advanced_days']['5']['bed'] = '08:00'
        with self.assertRaisesRegex(ValueError, 'yatış'):
            availability_for_week(data)
        data = advanced_config()
        data['advanced_days']['5']['study_start'] = '08:00'
        with self.assertRaisesRegex(ValueError, 'uyanma/yatış'):
            availability_for_week(data)

    def test_explicit_off_preserves_but_does_not_apply_customs(self):
        data = advanced_config()
        data['advanced_enabled'] = False
        data['day_overrides'] = {'0': {'wake': '18:00', 'sleep': '19:30', 'max': 80}}
        parsed = parse_details(serialize_details(data))
        self.assertEqual(parsed['advanced_days'], data['advanced_days'])
        self.assertEqual(free_minutes(availability_for_week(parsed)[0]), 15 * 60)
        # Older V2 saves with day_overrides but without advanced_enabled still work.
        old = dict(data)
        old.pop('advanced_enabled')
        self.assertEqual(availability_for_week(old)[0], [(1080, 1170)])

    def test_full_plan_respects_caps_real_intervals_and_rests(self):
        data = advanced_config(school_by_day={'0': ['08:00', '15:30']},
                               after_school_buffer=30,
                               blocks=['Cumartesi [10:30-11:00] Spor'])
        tasks = [{'ders': 'Fizik', 'konu': f'Soru {i}', 'sure': 45} for i in range(30)]
        norm = SmartCalendarService._normalize_tasks(tasks)
        profile = SmartCalendarService._extract_profile(serialize_details(data), tasks, norm)
        days = SmartCalendarService._build_days(profile)
        SmartCalendarService._smart_distribute(norm, days, profile)
        for day in days:
            self.assertLessEqual(day.total_minutes, day.day_cap)
            if day.date_.weekday() == 0:
                self.assertLessEqual(day.total_minutes, 80)
            for _task, start, end in day.appointments:
                self.assertTrue(any(s <= start and end <= e for s,e in day.windows),
                                (day.date_.weekday(), start, end, day.windows))
        self.assertEqual(sum(len(day.tasks) for day in days) + len(profile['unassigned']), len(norm))

    def test_school_day_prefers_after_school_unless_customized(self):
        data = advanced_config(school_by_day={str(i): ['08:00', '15:40'] for i in range(5)},
                               advanced_enabled=False, after_school_buffer=30)
        tasks = [{'ders': 'Türkçe', 'konu': 'Paragraf', 'sure': 30}]
        norm = SmartCalendarService._normalize_tasks(tasks)
        profile = SmartCalendarService._extract_profile(serialize_details(data), tasks, norm)
        school_day = next(d for d in SmartCalendarService._build_days(profile) if d.is_school_day)
        SmartCalendarService._smart_distribute(norm, [school_day], profile)
        self.assertEqual(len(school_day.appointments), 1)
        self.assertGreaterEqual(school_day.appointments[0][1], 16 * 60 + 10)

    def test_unusable_day_keeps_tasks_unassigned(self):
        data = advanced_config()
        data['advanced_days'] = {str(i): {'wake': '08:00', 'bed': '22:00',
                                         'study_start': '12:00', 'study_end': '12:05', 'max': 180}
                                 for i in range(7)}
        tasks = [{'ders': 'Kimya', 'konu': 'Asitler', 'sure': 40}]
        norm = SmartCalendarService._normalize_tasks(tasks)
        profile = SmartCalendarService._extract_profile(serialize_details(data), tasks, norm)
        days = SmartCalendarService._build_days(profile)
        SmartCalendarService._smart_distribute(norm, days, profile)
        self.assertEqual(sum(d.total_minutes for d in days), 0)
        self.assertEqual(len(profile['unassigned']), 1)

if __name__ == '__main__':
    unittest.main()
