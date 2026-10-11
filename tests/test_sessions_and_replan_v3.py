"""Student-specific study session limits and opt-in replan snapshots."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_planning_constraints_v3511 import sample
from services.smart_calendar import SmartCalendarService
from services.planning_constraints import serialize_details, DAYS
from services.plan_replanner import (create_snapshot, compare_snapshots, approve_snapshot,
                                     load_approved, student_key, read_snapshots, summary_text)


def session_profile(**overrides):
    p = sample(school_by_day={}, blocks=[], empty='Yok', max=180,
               wake='09:00', sleep='13:00', advanced_enabled=False,
               session_enabled=True, session_minutes=45, session_break=10,
               session_split=True)
    p.update(overrides)
    return p


def run_plan(data, tasks):
    return SmartCalendarService.create_weekly_plan_data('Öğrenci', deepcopy(tasks), serialize_details(data))


class StudySessionsTests(unittest.TestCase):
    def test_90_minute_student_is_not_forced_to_45(self):
        bundle = run_plan(session_profile(session_minutes=90),
                          [{'ders':'Fizik','konu':'Kuvvet','sure':90}])
        self.assertEqual(sum(t.sure for t in bundle['tasks']), 90)
        self.assertEqual(len(bundle['tasks']), 1)
        self.assertEqual(len(bundle['profile']['unassigned']), 0)

    def test_45_minute_student_120_minute_homework_is_split_without_loss(self):
        bundle = run_plan(session_profile(), [{'ders':'Matematik', 'konu':'Problemler', 'sure':120}])
        self.assertEqual(sum(t.sure for t in bundle['tasks']), 120)
        self.assertEqual([t.sure for t in bundle['tasks']], [45,45,30])
        self.assertTrue(all(t.sure <= 45 for t in bundle['tasks']))
        self.assertEqual(len(bundle['profile']['unassigned']), 0)

    def test_46_minute_task_does_not_create_one_minute_leftover(self):
        b = run_plan(session_profile(), [{'ders':'Türkçe', 'konu':'Paragraf','sure':46}])
        self.assertEqual([t.sure for t in b['tasks']], [23,23])

    def test_breaks_are_clock_time_and_not_counted_as_study(self):
        blocks = [f'{name} [17:00-19:00] Kurs' for i, name in enumerate(DAYS)
                  if i != date.today().weekday()]
        b = run_plan(session_profile(wake='17:00', sleep='19:00', max=120,
                                     blocks=blocks),
                     [{'ders':'Kimya','konu':'Mol','sure':90}])
        day = next(d for d in b['days'] if d.appointments)
        slots = [(st,en) for _,st,en in day.appointments]
        self.assertEqual(len(slots), 2)
        self.assertGreaterEqual(slots[1][0]-slots[0][1],10)
        self.assertEqual(day.total_minutes,90)

    def test_custom_long_break_can_prevent_fit(self):
        data = session_profile(session_minutes=45, session_break=30,
                               wake='17:00', sleep='18:40',max=180)
        b = run_plan(data, [{'ders':'Fizik','konu':'Sınav','sure':90}])
        # Across all seven days, each day has 100 minutes available; both 45's
        # only fit if separated by no more than 10 minutes, not 30.
        self.assertTrue(all(len(d.appointments) <= 1 for d in b['days']))
        self.assertEqual(sum(d.total_minutes for d in b['days']),90)

    def test_non_split_task_never_bypasses_max_session(self):
        b = run_plan(session_profile(), [{'ders':'Fizik','konu':'Deneme', 'sure':90,
                                          'splitable':False}])
        self.assertEqual(len(b['profile']['unassigned']), 1)
        self.assertEqual(sum(d.total_minutes for d in b['days']),0)
        self.assertIn('KAPASİTE AŞIMI',b['html'])

    def test_teacher_disables_split_all_long_tasks_are_reported(self):
        b = run_plan(session_profile(session_split=False),
                     [{'ders':'Fizik','konu':'Deneme','sure':91}])
        self.assertEqual(len(b['profile']['unassigned']),1)
        self.assertEqual(b['profile']['unassigned'][0].sure,91)

    def test_session_disabled_matches_legacy_45_to_55_split(self):
        p = session_profile(session_enabled=False)
        b = run_plan(p,[{'ders':'Matematik','konu':'Test','sure':120}])
        self.assertEqual(sum(t.sure for t in b['tasks']),120)
        self.assertEqual(sum(d.total_minutes for d in b['days']),120)
        self.assertNotIn('Tek Etüt:',b['html'])

    def test_profile_setting_round_trip(self):
        p = session_profile(session_minutes=60,session_break=15)
        b = run_plan(p,[{'ders':'Matematik','konu':'Test','sure':60}])
        self.assertEqual(b['profile']['session_rules'],
                         {'enabled':True,'minutes':60,'break_minutes':15})
        self.assertIn('Tek Etüt:', b['html'])

    def test_invalid_external_session_settings_fail(self):
        with self.assertRaisesRegex(ValueError,'oturum süresi'):
            run_plan(session_profile(session_minutes=2),[{'ders':'D','konu':'K','sure':20}])
        with self.assertRaisesRegex(ValueError,'molası'):
            run_plan(session_profile(session_break=90),[{'ders':'D','konu':'K','sure':20}])

    def test_sessions_do_not_override_daily_cap_and_holiday(self):
        p = session_profile(max=45, empty='Pazar')
        b = run_plan(p,[{'ders':'Fizik','konu':'Test','sure':300}])
        for d in b['days']:
            self.assertLessEqual(d.total_minutes,45)
            self.assertTrue(all(t.sure<=45 for t in d.tasks))
            if d.date_.weekday()==6: self.assertEqual(d.total_minutes,0)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.data = session_profile()
        self.homework = [{'ders':'Türkçe','kitap':'Kitap1','konu':'Test1','sure':45}]
        self.bundle = run_plan(self.data,self.homework)
        self.first = create_snapshot(self.bundle,self.homework,serialize_details(self.data))

    def test_snapshot_first_and_unchanged(self):
        self.assertTrue(compare_snapshots(None,self.first)['first'])
        self.assertFalse(compare_snapshots(self.first,self.first)['changed'])

    def test_new_homework_marks_modified_draft(self):
        new = self.homework + [{'ders':'Fizik','kitap':'Kitap2','konu':'Test2','sure':30}]
        nxt = create_snapshot(run_plan(self.data,new),new,serialize_details(self.data))
        diff = compare_snapshots(self.first,nxt)
        self.assertTrue(diff['changed'])
        self.assertTrue(diff['homework_changed'])
        self.assertGreaterEqual(diff['new_units'],1)
        self.assertIn('Yeni parçalar:',summary_text(diff))

    def test_routine_change_causes_new_draft_not_overwrite(self):
        changed=deepcopy(self.data)
        changed['blocks']=['Her Gün [09:00-11:00] Kurs']
        nxt = create_snapshot(run_plan(changed,self.homework), self.homework, serialize_details(changed))
        self.assertTrue(compare_snapshots(self.first,nxt)['settings_changed'])
        with TemporaryDirectory() as directory:
            path=Path(directory)/'accepted.json'
            approve_snapshot('student-A',self.first,path)
            self.assertEqual(load_approved('student-A',path),self.first)
            self.assertNotEqual(load_approved('student-A',path),nxt)
            approve_snapshot('student-A',nxt,path)
            self.assertEqual(load_approved('student-A',path),nxt)

    def test_different_students_never_share_profile_snapshot(self):
        with TemporaryDirectory() as directory:
            target=Path(directory)/'approved.json'
            approve_snapshot('123',self.first,target)
            self.assertIsNone(load_approved('456',target))
            self.assertNotEqual(student_key('123'), student_key('456'))
            self.assertIsNone(student_key('  '))
            with self.assertRaisesRegex(ValueError,'kimliği'):
                approve_snapshot(None,self.first,target)

    def test_corrupt_snapshot_not_silently_overwritten(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'approved.json'
            path.write_text('not json','utf-8')
            with self.assertRaises(ValueError):
                # Parsing reports a fault; did not destroy the original.
                try: read_snapshots(path)
                except Exception as e: raise ValueError(str(e)) from e
            self.assertEqual(path.read_text('utf-8'),'not json')


if __name__=='__main__': unittest.main()
