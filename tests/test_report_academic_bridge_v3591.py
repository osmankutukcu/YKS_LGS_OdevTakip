# -*- coding: utf-8 -*-
"""Isolated synthetic academic bridge regression tests; no live data, network, Qt."""
from datetime import date
import sqlite3
import unittest

from services.report_academic_bridge_v3591 import read_academic_evidence, _course
from services.integrated_report_v3584 import read_integrated_report, preview_text
from tests.test_integrated_report_v3584 import prepared

DAY = date(2026, 10, 21)


class AcademicBridgeTests(unittest.TestCase):
    def setUp(self):
        self.db = prepared()
        self.addCleanup(self.db.close)
        # Upgrade the minimal prior fixture without altering production migrations.
        self.db.execute('ALTER TABLE koc_konu_takip ADD COLUMN ders_adi TEXT')
        self.db.execute('ALTER TABLE koc_konu_takip ADD COLUMN konu_adi TEXT')
        self.db.execute("UPDATE koc_konu_takip SET ders_adi='TYT Matematik',konu_adi='Problemler' WHERE id=99")
        self.db.execute("INSERT INTO koc_konu_takip(id,ogrenci_id,ders_adi,konu_adi,durum) "
                        "VALUES(100,1,'TYT Matematik','Denklemler',4)")
        self.db.commit()

    def read(self, sid=1, **kwargs):
        return read_academic_evidence(self.db, sid, **({"reference_day": DAY} | kwargs))

    def test_one_student_exam_and_topic_not_merged_as_mastery(self):
        self.db.execute('PRAGMA query_only=ON')
        before=self.db.total_changes
        result=self.read()
        self.assertEqual(result.status, 'kayıt')
        self.assertIn('TYT Matematik',result.value)
        self.assertIn('8.5 net', result.value)
        self.assertIn('1/2 öğretmen konu işareti', result.value)
        self.assertIn('neden-sonuç',result.scope)
        self.assertEqual(self.db.total_changes,before)

    def test_student_id_never_substituted(self):
        result=self.read(2)
        self.assertIn('Türkçe',result.value)
        self.assertNotIn('TYT Matematik',result.value)
        for bad in (False, '1', 0, -1, 999):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.read(bad)

    def test_exam_kind_disambiguation(self):
        self.assertEqual(_course('Matematik','TYT'),'tyt_matematik')
        self.assertEqual(_course('Matematik','AYT'),'ayt_matematik')
        self.assertEqual(_course('Matematik','LGS'),'lgs_matematik')
        self.assertIsNone(_course('TYT Matematik','LGS'))
        self.assertIsNone(_course('Matematik','Deneme'))
        self.assertIsNone(_course('Türkçe','AYT'))
        self.assertIsNone(_course('Matematik',''))
        self.assertEqual(_course('Fen Bilimleri','LGS'),'lgs_fen')

    def test_unknown_subject_not_assigned_to_mathematics(self):
        self.db.execute("UPDATE deneme_sonuclari SET ders_adi='Matematik-genel' WHERE ogrenci_id=1")
        result=self.read()
        self.assertIn('2 deneme ders satırı kesin ders koduyla eşleşmedi', ' '.join(result.warnings))
        self.assertNotIn('8.5 net',result.value)

    def test_contradictory_topic_marks_not_counted(self):
        self.db.execute("INSERT INTO koc_konu_takip(id,ogrenci_id,ders_adi,konu_adi,durum) "
                        "VALUES(102,1,'TYT Matematik','Denklemler',2)")
        result=self.read()
        self.assertIn('0/2 öğretmen',result.value)
        self.assertIn('1 çelişkili kayıt',result.value)

    def test_multiple_same_exam_subject_refuses_sum(self):
        self.db.execute("INSERT INTO deneme_sonuclari(id,deneme_id,ogrenci_id,ders_adi,dogru,yanlis,bos,net) "
                        "VALUES(222,12,1,'Matematik',15,2,3,14.5)")
        result=self.read()
        self.assertIn('çoklu net kaydı',result.value)
        self.assertNotIn('14.5 net',result.value)

    def test_old_exam_records_not_combined_with_new(self):
        self.db.executescript('''
            CREATE TABLE deneme(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,tarih TEXT,tur TEXT);
            CREATE TABLE deneme_sonuc(id INTEGER PRIMARY KEY,deneme_id INTEGER,ders TEXT,net REAL);
            INSERT INTO deneme VALUES(91,1,'2026-10-20','TYT');
            INSERT INTO deneme_sonuc VALUES(1111,91,'Matematik',34);
        ''')
        result=self.read()
        self.assertIn('8.5 net', result.value)
        self.assertNotIn('34 net', result.value)
        self.assertIn('İki farklı deneme', ' '.join(result.warnings))

    def test_unrelated_student_topic_not_in_count(self):
        self.db.execute("INSERT INTO koc_konu_takip(id,ogrenci_id,ders_adi,konu_adi,durum) "
                        "VALUES(103,2,'TYT Matematik','Büyük Konu',4)")
        self.assertIn('1/2 öğretmen', self.read().value)

    def test_too_many_rows_not_claimed_audit(self):
        result=self.read(max_exam_rows=1)
        self.assertEqual(result.status,'doğrulanamadı')
        self.assertIn('sınırını aşıyor',' '.join(result.warnings))
        result2=self.read(max_topic_rows=1)
        self.assertIn('sınırını aşıyor',' '.join(result2.warnings))

    def test_missing_schema_and_expired_or_future_results(self):
        self.db.execute("UPDATE denemeler SET tarih='2025-01-01'")
        result=self.read()
        self.assertNotIn('8.5 net',result.value)
        self.db.execute("UPDATE denemeler SET tarih='2027-01-01'")
        result=self.read()
        self.assertNotIn('8.5 net',result.value)

    def test_report_integration_adds_only_one_section(self):
        self.db.execute('PRAGMA query_only=ON')
        report=read_integrated_report(self.db,1,reference_day=DAY)
        names=[s.title for s in report.sections]
        self.assertEqual(names.count('Ders ölçümleri ve konu işaretleri'),1)
        self.assertIn('8.5 net',preview_text(report))
        self.assertEqual(report.homework.done,2)
        self.assertEqual(report.homework.total,5)

    def test_incomplete_topic_schema_marked_not_invented(self):
        db=sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, aktif INTEGER);
          INSERT INTO ogrenci VALUES(1,1);
          CREATE TABLE koc_konu_takip(ogrenci_id INTEGER, durum INTEGER);
          INSERT INTO koc_konu_takip VALUES(1,4);
        ''')
        r=read_academic_evidence(db,1,reference_day=DAY)
        self.assertEqual(r.status,'doğrulanamadı')
        self.assertNotIn('başarısız',r.value)
        self.assertIn('Konu adı/ders/durum alanları yok',' '.join(r.warnings))

    def test_bad_inputs(self):
        for kwargs in ({'lookback_days':0},{'lookback_days':367},{'max_topic_rows':0},{'reference_day':'2026-10-21'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                self.read(**kwargs)


if __name__ == '__main__':
    unittest.main()
