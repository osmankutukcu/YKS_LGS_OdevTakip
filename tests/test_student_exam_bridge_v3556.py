# -*- coding: utf-8 -*-
"""Isolated, wholly fictional fixture. Does not touch project/production DBs."""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.student_exam_bridge_v3556 import search_students, read_student_progress


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'fixture.sqlite'
        with sqlite3.connect(self.path) as c:
            c.executescript('''
                CREATE TABLE ogrenci (id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,ana_grup TEXT,alt_grup TEXT);
                CREATE TABLE tyt_matematik (id INTEGER PRIMARY KEY,konu TEXT);
                CREATE TABLE problemler (id INTEGER PRIMARY KEY,konu TEXT);
                CREATE TABLE koc_konu_takip (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,ders_adi TEXT,konu_adi TEXT,durum INTEGER,kitap_id INTEGER);
                INSERT INTO ogrenci VALUES (1,'Ada','Kaya','YKS','12-A'),(2,'Ada','Kaya','YKS','12-B'),(3,'Deniz','Yılmaz','LGS','8-A');
                INSERT INTO tyt_matematik VALUES (1,'Üslü Sayılar'),(2,'Köklü Sayılar'),(3,'Oran Orantı');
                INSERT INTO problemler VALUES (1,'Yaş Problemleri');
                INSERT INTO koc_konu_takip VALUES (1,1,'(TYT) Matematik','Üslü Sayılar',4,1);
                INSERT INTO koc_konu_takip VALUES (2,1,'TYT Matematik','Üslü Sayılar',4,2);
                INSERT INTO koc_konu_takip VALUES (3,1,'Matematik (TYT)','Köklü Sayılar',4,1);
                INSERT INTO koc_konu_takip VALUES (4,1,'(TYT) Matematik','Köklü Sayılar',2,2);
                INSERT INTO koc_konu_takip VALUES (5,1,'AYT Matematik','Üslü Sayılar',4,1);
                INSERT INTO koc_konu_takip VALUES (6,1,'TYT Matematik','Bilinmeyen Başlık',4,1);
                INSERT INTO koc_konu_takip VALUES (7,2,'TYT Matematik','Oran Orantı',4,2);
                INSERT INTO koc_konu_takip VALUES (8,1,'TYT Matematik','Oran Orantı',2,3);
            ''')

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_teacher_marked_only_and_conflicts(self):
        report = read_student_progress(self.path, 1, 'YKS', 'Sayısal (TYT + AYT)', as_of=date(2026, 10, 19))
        self.assertEqual(report.completed, 1)
        self.assertEqual(report.conflicts, 1)
        self.assertEqual(report.in_progress, 2)
        self.assertEqual(report.total, 4)
        self.assertEqual(report.remaining_ceiling, 3)
        self.assertEqual(report.unmatched_records, 2)
        self.assertEqual(report.homework_total, 0)
        self.assertTrue(report.unknown == 1)

    def test_separate_students_same_names(self):
        a = read_student_progress(self.path, 1, 'YKS', 'Sayısal (TYT + AYT)')
        b = read_student_progress(self.path, 2, 'YKS', 'Sayısal (TYT + AYT)')
        self.assertEqual(a.completed, 1)
        self.assertEqual(b.completed, 1)
        self.assertEqual(a.conflicts, 1)
        self.assertEqual(b.conflicts, 0)
        students = search_students(self.path, 'Ada')
        self.assertEqual({r.id for r in students}, {1, 2})
        self.assertNotEqual(students[0].label, students[1].label)

    def test_no_foreign_course_completion(self):
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE koc_konu_takip SET durum=1 WHERE id=7")
        b = read_student_progress(self.path, 2, 'YKS', 'Sayısal (TYT + AYT)')
        self.assertEqual(b.completed, 0)
        self.assertEqual(b.in_progress, 1)

    def test_unknown_student_does_not_fallback_to_first(self):
        with self.assertRaisesRegex(ValueError, 'bulunamadı'):
            read_student_progress(self.path, 9999, 'YKS', 'Sayısal (TYT + AYT)')

    def test_missing_database_is_never_created(self):
        missing = Path(self.temp.name) / 'not-created.sqlite'
        self.assertEqual(search_students(missing), ())
        with self.assertRaises(FileNotFoundError):
            read_student_progress(missing, 1, 'YKS', 'Sayısal (TYT + AYT)')
        self.assertFalse(missing.exists())

    def test_read_only_fixture_bytes_unchanged(self):
        before = self.path.read_bytes()
        for _ in range(2):
            search_students(self.path, 'Ada')
            read_student_progress(self.path, 1, 'YKS', 'Sayısal (TYT + AYT)')
        self.assertEqual(self.path.read_bytes(), before)

    def test_student_scoped_topic_added(self):
        with sqlite3.connect(self.path) as c:
            c.execute('CREATE TABLE ogrenci_konu_duzen(ders TEXT, ogrenci_id INTEGER,konu TEXT)')
            c.execute('INSERT INTO ogrenci_konu_duzen VALUES (?,?,?)', ('tyt_matematik',2,'Yeni Başlık'))
            c.execute('INSERT INTO koc_konu_takip (ogrenci_id,ders_adi,konu_adi,durum) VALUES (?,?,?,?)',
                      (2,'TYT Matematik','Yeni Başlık',4))
        a = read_student_progress(self.path, 1, 'YKS', 'Sayısal (TYT + AYT)')
        b = read_student_progress(self.path, 2, 'YKS', 'Sayısal (TYT + AYT)')
        self.assertEqual(a.total, 4)
        self.assertEqual(b.total, 5)
        self.assertEqual(b.completed, 2)

    def test_unscoped_course_not_misclassified(self):
        with sqlite3.connect(self.path) as c:
            c.execute("INSERT INTO koc_konu_takip (ogrenci_id,ders_adi,konu_adi,durum) VALUES (1,'Matematik','Yaş Problemleri',4)")
        result = read_student_progress(self.path, 1, 'YKS', 'Sayısal (TYT + AYT)')
        self.assertEqual(result.completed, 1)

    def test_escaped_wildcard_search(self):
        self.assertEqual(search_students(self.path, '%'), ())
        self.assertEqual(search_students(self.path, '_'), ())


if __name__ == '__main__':
    unittest.main()
