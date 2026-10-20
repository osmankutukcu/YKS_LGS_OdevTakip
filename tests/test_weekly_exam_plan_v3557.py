# -*- coding: utf-8 -*-
"""V3557 planner tests: synthetic students/lessons only."""
import hashlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.weekly_exam_plan_v3557 import build_weekly_plan


class V3557PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'synthetic.db'
        with sqlite3.connect(self.db) as con:
            con.executescript('''
            CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, ana_grup TEXT, alt_grup TEXT);
            CREATE TABLE tyt_matematik (id INTEGER PRIMARY KEY, konu TEXT);
            CREATE TABLE problemler (id INTEGER PRIMARY KEY, konu TEXT);
            CREATE TABLE koc_konu_takip (id INTEGER PRIMARY KEY, ogrenci_id INT, ders_adi TEXT, konu_adi TEXT, durum INT);
            INSERT INTO ogrenci VALUES (10,'Öğrenci','Bir','YKS','12-A'),(11,'Öğrenci','Bir','YKS','12-B');
            INSERT INTO tyt_matematik VALUES (1,'Üslü Sayılar'),(2,'Köklü Sayılar'),(3,'Oran Orantı');
            INSERT INTO problemler VALUES (1,'Yaş Problemleri'),(2,'Karışım Problemleri');
            INSERT INTO koc_konu_takip VALUES (1,10,'TYT Matematik','Üslü Sayılar',4),
            (2,10,'TYT Matematik','Üslü Sayılar',4),
            (3,10,'TYT Matematik','Köklü Sayılar',4),
            (4,10,'TYT Matematik','Köklü Sayılar',2),
            (5,10,'TYT Matematik','Oran Orantı',2),
            (6,11,'TYT Matematik','Oran Orantı',4),
            (7,10,'Matematik','Karışım Problemleri',4),
            (8,10,'AYT Matematik','Karışım Problemleri',4);
            ''')
        self.start = date(2026,10,20)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, student=10, days=30, speed=2, buffer=2, revision=7):
        return build_weekly_plan(self.db, student, 'YKS', 'Sayısal (TYT + AYT)',
                                 remaining_days=days, weekly_topics=speed,
                                 buffer_days=buffer, revision_days=revision,
                                 as_of=self.start)

    def test_exact_status_counts_and_conflicts(self):
        p = self.plan()
        self.assertEqual(p.catalog_total, 5)
        self.assertEqual(p.teacher_marked_ready, 1)
        self.assertEqual(p.candidates, 4)
        names = [x.topic for x in p.unplanned_items] + [x.topic for week in p.weeks for x in week.items]
        self.assertEqual(set(names), {'Köklü Sayılar','Oran Orantı','Yaş Problemleri','Karışım Problemleri'})
        self.assertTrue(any(x.evidence.startswith('çelişkili') for week in p.weeks for x in week.items))
        self.assertNotIn('Üslü Sayılar', names)

    def test_student_id_separation(self):
        first, second = self.plan(student=10), self.plan(student=11)
        self.assertEqual(first.teacher_marked_ready, 1)
        self.assertEqual(second.teacher_marked_ready, 1)
        self.assertNotEqual(first.student_id, second.student_id)
        self.assertNotEqual({x.topic for w in first.weeks for x in w.items},
                            {x.topic for w in second.weeks for x in w.items})

    def test_partial_week_is_not_overloaded(self):
        p = self.plan(days=17, speed=3, buffer=0, revision=9)  # 8 study days
        self.assertEqual(p.planned, 3)
        self.assertEqual(p.unscheduled, 1)
        self.assertEqual(len(p.weeks), 1)
        self.assertEqual(p.weeks[0].start, self.start)
        self.assertEqual(p.study_end, date(2026,10,28))

    def test_impossible_study_window(self):
        p = self.plan(days=4, speed=7, buffer=2, revision=7)
        self.assertEqual(p.planned, 0)
        self.assertEqual(p.unscheduled, 4)
        self.assertEqual(p.weeks, ())
        self.assertTrue(any('süre kalmadı' in n for n in p.warnings))

    def test_round_robin_balanced_and_deterministic(self):
        a,b = self.plan(speed=3), self.plan(speed=3)
        self.assertEqual(a, b)
        self.assertTrue(a.weeks)
        first_week = [it.course for it in a.weeks[0].items]
        self.assertIn('tyt_matematik', first_week)
        self.assertIn('problemler', first_week)

    def test_no_write_and_missing_db_not_created(self):
        def digest(): return hashlib.sha256(self.db.read_bytes()).hexdigest()
        before = digest()
        for _ in range(3): self.plan()
        self.assertEqual(before, digest())
        missing = Path(self.temp.name) / 'missing.db'
        with self.assertRaises(FileNotFoundError):
            build_weekly_plan(missing,10,'YKS','Sayısal (TYT + AYT)',remaining_days=10,
                              weekly_topics=3,buffer_days=1,revision_days=2)
        self.assertFalse(missing.exists())

    def test_reject_invalid_inputs_and_identity(self):
        with self.assertRaises(ValueError): self.plan(student=999)
        with self.assertRaises(ValueError): self.plan(days=-1)
        with self.assertRaises(ValueError): self.plan(speed=0)
        with self.assertRaises(ValueError): self.plan(buffer=-1)
        with self.assertRaises(ValueError):
            build_weekly_plan(self.db,10,'YKS','INVALID',remaining_days=20,
                              weekly_topics=3,buffer_days=1,revision_days=2)
        with self.assertRaises(ValueError): self.plan(student=True)

    def test_text_clearly_nonwriting(self):
        text = self.plan().to_text()
        self.assertIn('Taslaktır.', text)
        self.assertIn('Kayıt, ödev atama', text)
        self.assertIn('Öğrenci Bir', text)
        self.assertIn('UYARI', text)


if __name__ == '__main__':
    unittest.main()
