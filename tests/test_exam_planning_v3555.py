# -*- coding: utf-8 -*-
"""Kritik Ödev Takip/Ödev Kontrol tablolarına dokunmayan salt-okunur planlama testleri."""
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.exam_planning_v3555 import read_track_counts, read_calendar, plan_projection
from services.education_action_v3555 import read_teacher_action


class ExamPlanning3555Tests(unittest.TestCase):
    def test_local_lgs_catalog_is_not_legacy_default(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'topics.db'
            con = sqlite3.connect(database)
            con.execute('CREATE TABLE lgs_matematik (id INTEGER PRIMARY KEY, konu TEXT)')
            con.executemany('INSERT INTO lgs_matematik (konu) VALUES (?)',
                            [('Çarpanlar',), ('Çarpanlar',), ('Kareköklü',), ('',), (None,)])
            con.commit()
            con.close()
            before = database.read_bytes()
            only_track = next(iter(read_track_counts(database, 'LGS').values()))
            self.assertEqual(only_track.total, 2)
            self.assertEqual(only_track.courses[0].title, 'LGS Matematik')
            self.assertGreater(len(only_track.missing), 0)
            self.assertEqual(database.read_bytes(), before)  # DB write-free

    def test_invalid_database_provides_no_invented_topic_number(self):
        totals = read_track_counts('/does-not-exist/whatever.sqlite', 'YKS')
        self.assertTrue(all(item.total == 0 for item in totals.values()))

    def test_unverified_date_is_labeled_estimate(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'calendar.json'
            p.write_text(json.dumps({'years': {'2027': {
                'YKS': {'date': '2027-06-19', 'status': 'official', 'source_url': 'https://random.example.edu/xyz'},
                'LGS': {'date': '2027-06-13', 'status': 'estimate', 'source_url': ''}
            }}}), encoding='utf-8')
            cal = read_calendar(dt.date(2026,10,19), p)
            self.assertEqual(cal['YKS']['status'], 'estimate')
            self.assertEqual(cal['YKS']['days'], 243)
            self.assertEqual(cal['MSÜ']['status'], 'unknown')
            self.assertIsNone(cal['MSÜ']['days'])

    def test_projection_reserves_revision_and_uses_seven_day_week(self):
        p = plan_projection(65, 4, 7, 30, 245)
        self.assertEqual(p['study_days'], 114)
        self.assertEqual(p['available_days'], 208)
        self.assertEqual(p['margin_before_revision'], 94)
        self.assertEqual(plan_projection(0, 4, 7, 30, 245)['study_days'], 0)

    def test_missing_teacher_dashboard_does_not_invent_zero(self):
        self.assertIsNone(read_teacher_action('/path/not/here.db'))

    def test_projection_does_not_report_success_when_time_insufficient(self):
        p = plan_projection(200, 2, 7, 30, 100)
        self.assertFalse(p['feasible'])
        self.assertGreater(p['required_weekly'], 2)


if __name__ == '__main__':
    unittest.main()
