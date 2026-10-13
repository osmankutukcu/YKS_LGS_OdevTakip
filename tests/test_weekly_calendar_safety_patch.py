"""Calendar hardening tests runnable without Qt GUI or real student records."""
from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Qt shims live in an existing test that already verifies planning integrity.
from tests.test_planning_constraints_v3511 import SmartCalendarService, sample
from services.planning_constraints import availability_for_week, serialize_details
from services.calendar_plan_integrity import validate_weekly_plan


class WeeklyCalendarSafetyTests(unittest.TestCase):
    def test_hidden_homework_rows_are_still_planned(self):
        from services.calendar_plan_inputs import snapshot_homework_table
        class Item:
            def __init__(self, txt): self.value = txt
            def text(self): return self.value
        class DummyTable:
            def __init__(self):
                self.rows = [
                    ['Fizik', 'FİZİK3', 'Yay Dalgaları', '75'],
                    ['Fizik', 'xxx', 'Yay Dalgaları', '75']]
            def rowCount(self): return len(self.rows)
            def item(self, row, col): return Item(self.rows[row][col])
            def isRowHidden(self, row): return row == 1
        tasks = snapshot_homework_table(DummyTable(), deadline=date.today()+timedelta(days=7))
        self.assertEqual(len(tasks), 2)
        self.assertEqual([t['kitap'] for t in tasks], ['FİZİK3', 'xxx'])
        self.assertEqual(sum(t['sure'] for t in tasks), 150)
        self.assertTrue(all('deadline' in t for t in tasks))

    def test_input_errors_prevent_misleading_pdf(self):
        from services.calendar_plan_inputs import snapshot_homework_table
        class Table:
            def rowCount(self): return 1
            def item(self, r, c):
                class Item:
                    def text(self): return ['Fizik', '345', 'Enerji', 'yanlış'][c]
                return Item()
        with self.assertRaises(ValueError):
            snapshot_homework_table(Table())

    def test_school_and_course_buffer_prevents_early_start(self):
        data = sample(school_by_day={}, blocks=['Cumartesi [08:00-16:00] Kurs'],
                      empty='Yok', after_routine_buffer=25,
                      wake='08:00', sleep='22:00')
        windows = availability_for_week(data)
        self.assertEqual(windows[5], [(985, 1320)])  # 16:25
        self.assertEqual(windows[6], [(480, 1320)])

    def test_legacy_profiles_have_no_implicit_extra_buffer(self):
        data = sample(school_by_day={}, blocks=['Cumartesi [08:00-16:00] Kurs'],
                      empty='Yok', wake='08:00', sleep='22:00')
        self.assertEqual(availability_for_week(data)[5], [(960, 1320)])

    def test_negative_or_excessive_buffer_rejected(self):
        for n in (-1, 181):
            with self.assertRaises(ValueError):
                availability_for_week(sample(after_routine_buffer=n))

    def test_no_homework_minutes_dropped_by_session_split(self):
        for total in (29, 75, 180, 250, 600):
            tasks = SmartCalendarService._normalize_tasks(
                [{'ders':'Fizik', 'konu':'Dalgalar', 'sure':total}],
                session_minutes=15, session_split=True)
            self.assertEqual(sum(t.sure for t in tasks), total)
            self.assertTrue(all(t.sure <= 15 for t in tasks))

    def test_unassigned_and_assigned_conservation_and_real_slots(self):
        data = sample(school_by_day={}, empty='Yok',
                      blocks=['Cumartesi [08:00-16:00] Kurs'],
                      after_routine_buffer=20,
                      wake='08:00', sleep='22:00', max=90)
        hw = [
            {'ders':'Fizik', 'kitap':'FİZİK3', 'konu':'Yay Dalgaları',
             'sure':75, 'deadline':(date.today()+timedelta(days=6)).isoformat()},
            {'ders':'Fizik', 'kitap':'xxx', 'konu':'Yay Dalgaları',
             'sure':75, 'deadline':(date.today()+timedelta(days=6)).isoformat()},
        ]
        bundle = SmartCalendarService.create_weekly_plan_data(
            'Örnek Öğrenci', hw, serialize_details(data))
        self.assertEqual(validate_weekly_plan(bundle), [])
        self.assertEqual(sum(t.sure for d in bundle['days'] for t in d.tasks)
                         + sum(t.sure for t in bundle['profile']['unassigned']), 150)
        self.assertIn('dk', bundle['html'])
        for day in bundle['days']:
            if day.date_.weekday() == 5:
                self.assertTrue(all(s >= 16*60+20 for _,s,_ in day.appointments))

    def test_bad_plan_is_rejected_without_touching_source(self):
        data = sample(school_by_day={}, empty='Yok', blocks=[], max=180)
        bundle = SmartCalendarService.create_weekly_plan_data(
            'Test', [{'ders':'Fizik','konu':'Basınç','sure':30}], serialize_details(data))
        self.assertEqual(validate_weekly_plan(bundle), [])
        day = next(d for d in bundle['days'] if d.appointments)
        task, start, end = day.appointments[0]
        day.appointments[0] = (task, start, end + 10)
        self.assertTrue(any('süre yanlış' in err for err in validate_weekly_plan(bundle)))


if __name__ == '__main__':
    unittest.main()
