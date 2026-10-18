"""V23.6: teacher summary uses existing student-scoped readers only."""
import sqlite3
from pathlib import Path
import unittest

from services.curriculum_v236 import read_coverage_overview, count_scoped_tasks


class TeacherScopeOverviewTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.executescript('''
        CREATE TABLE ders_tanimlari(id TEXT PRIMARY KEY, ad TEXT);
        INSERT INTO ders_tanimlari VALUES ('fizik','Fizik');
        CREATE TABLE fizik(id INTEGER PRIMARY KEY, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
        INSERT INTO fizik VALUES (1,'Hareket',15,20),(2,'Kuvvet',12,15);
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT,
                             ana_grup TEXT, alt_grup TEXT);
        INSERT INTO ogrenci VALUES (1,'Örnek','Öğrenci','YKS','12-say'),
                                   (2,'İkinci','Öğrenci','YKS','12-ea');
        CREATE TABLE grup_konu_duzen(id INTEGER PRIMARY KEY, ana_grup TEXT,
            alt_grup TEXT, ders TEXT, konu TEXT, ort_soru INTEGER, ort_sure INTEGER);
        INSERT INTO grup_konu_duzen VALUES (7,'YKS','12-say','fizik','İleri Hareket',25,30);
        CREATE TABLE ogrenci_konu_duzen(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
            ders TEXT,konu TEXT,ort_soru INTEGER,ort_sure INTEGER);
        INSERT INTO ogrenci_konu_duzen VALUES (9,1,'fizik','Kişisel Kamp',25,30);
        CREATE TABLE kapsam_odev_v233(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
            ders TEXT,konu_ref TEXT,konu_adi TEXT,kapsam TEXT,kitap_ad TEXT,sure_dk INTEGER,
            bitis_tarihi TEXT,durum TEXT,olusturma_tarihi TEXT,bitis_islem_tarihi TEXT);
        INSERT INTO kapsam_odev_v233 VALUES
           (1,1,'fizik','g:7','İleri Hareket','Grup','A',45,'2026-12-01','devam','2026-10-01',NULL),
           (2,1,'fizik','s:9','Kişisel Kamp','Öğrenci','A',30,'2026-12-01','tamam','2026-10-01',NULL),
           (3,2,'fizik','s:8','Başka Konu','Öğrenci','B',30,'2026-12-01','devam','2026-10-01',NULL),
           (4,1,'kimya','s:10','Kimya','Öğrenci','B',30,'2026-12-01','iptal','2026-10-01',NULL);
        CREATE TABLE odev(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,ders TEXT,
            konu_id INTEGER,kitap_ad TEXT,durum TEXT);
        INSERT INTO odev VALUES (1,1,'fizik',1,'A','devam');
        ''')
        self.matrix = [{'id':1,'konu':'Hareket'},{'id':2,'konu':'Kuvvet'}]

    def tearDown(self):
        self.con.close()

    def read(self, sid=1, rows=None):
        return read_coverage_overview(self.con,lesson='fizik',student_id=sid,
                                      general_rows=self.matrix if rows is None else rows)

    def test_understands_student_name_without_exposing_database_id_as_headline(self):
        summary = self.read()
        self.assertEqual('Örnek Öğrenci',summary.student_label)
        self.assertEqual('YKS / 12-say',summary.group_label)

    def test_matrix_and_scoped_totals_are_separate(self):
        summary = self.read()
        self.assertEqual(2,summary.general_count)
        self.assertEqual(2,summary.extra_count)
        self.assertEqual(1,summary.scoped_tasks.open_count)
        self.assertEqual(1,summary.scoped_tasks.completed_count)
        self.assertEqual(0,summary.scoped_tasks.cancelled_count)

    def test_other_student_and_course_never_included(self):
        first = self.read(1)
        second = self.read(2)
        self.assertEqual(1,first.scoped_tasks.open_count)
        self.assertEqual(0,second.scoped_tasks.completed_count)
        self.assertEqual(1,second.scoped_tasks.open_count)
        self.assertEqual(0,second.extra_count)

    def test_expected_scoped_topics_are_not_false_alarm(self):
        result = self.read()
        self.assertFalse(result.needs_attention, result.problems)
        self.assertIn('ayrı kimlikle',result.teacher_message)

    def test_stale_matrix_reports_without_fixing_rows(self):
        result = self.read(rows=[{'id':1,'konu':'Yanlış Eski Ad'}])
        self.assertTrue(result.needs_attention)
        self.assertTrue(any('uyuşmuyor' in p for p in result.problems))

    def test_different_student_is_rejected(self):
        with self.assertRaises(ValueError): self.read(999)

    def test_reading_writes_nothing_even_in_query_only_mode(self):
        before = '\n'.join(self.con.iterdump())
        self.con.execute('PRAGMA query_only=ON')
        self.read()
        self.assertEqual(before,'\n'.join(self.con.iterdump()))

    def test_preview_is_optional_and_main_checkbox_handler_unchanged(self):
        form = (Path(__file__).resolve().parents[1]/'ui/homework_form.py').read_text()
        self.assertIn('self._tik_degisti(it, table, ders)',form)
        self.assertIn('int(k["id"])',form)
        preview = (Path(__file__).resolve().parents[1]/'ui/curriculum_matrix_preview_v232.py').read_text()
        self.assertIn('self.setModal(True)',preview)
        self.assertIn('student_id != loaded_id',preview)
        self.assertIn('read_coverage_overview',preview)


if __name__ == '__main__':
    unittest.main()
