# -*- coding: utf-8 -*-
"""Synthetic, read-only fixture. NEVER uses live students or the app's database."""
from __future__ import annotations
from datetime import date
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from services.professional_pdf_v3583 import get_report_snapshot, export_professional_pdf

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    db = sqlite3.connect(':memory:')
    db.executescript('''
        CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, ana_grup TEXT, alt_grup TEXT, aktif INTEGER);
        CREATE TABLE odev_kume (id INTEGER PRIMARY KEY, ogrenci_id INTEGER, bitis_tarihi TEXT);
        CREATE TABLE odev (id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER, ders TEXT, durum TEXT, silindi INTEGER, aktarildi INTEGER);
        CREATE TABLE odev_satir (id INTEGER PRIMARY KEY, ogrenci_id INTEGER, kume_id INTEGER, ders TEXT, durum TEXT, silindi INTEGER, aktarildi INTEGER);
        INSERT INTO ogrenci VALUES (1,'Örnek','Öğrenci','YKS','12-say',1), (2,'Kaydı','Olmayan','LGS','8. sınıf',1);
        INSERT INTO odev_kume VALUES
          (1,1,'2026-10-17'),(2,1,'2026-10-19'),(3,1,'2026-10-20'),
          (4,1,'2026-10-21'),(5,1,NULL),(6,1,'2026-08-10'),(7,1,'2026-10-11');
        INSERT INTO odev VALUES
          (1,1,1,'tyt_matematik','yapildi',0,0),
          (2,1,1,'tyt_matematik','devam',0,0),
          (3,1,2,'fizik','tamam',0,0),
          (4,1,3,'fizik','devam',0,0),
          (5,1,4,'biyoloji','devam',0,0),
          (6,1,5,'kimya','devam',0,0),
          (7,1,6,'fizik','devam',0,0),
          (8,1,7,'kimya','iptal',0,0),
          (9,1,7,'kimya','belirsiz-durum',0,0),
          (10,1,2,'fizik','tamam',1,0);
        INSERT INTO odev_satir VALUES
          (11,1,1,'tyt_matematik','yapildi',0,0),
          (12,1,7,'türkçe','tamam',0,0);
    ''')
    return db


class ProfessionalPDFV3583Tests(unittest.TestCase):
    def test_correct_cohort_and_no_double_counting(self):
        db = fixture()
        self.addCleanup(db.close)
        before = db.total_changes
        report = get_report_snapshot(db, 1, 30, date(2026,10,20))
        self.assertEqual((report.total, report.done, report.pending), (4, 2, 2))
        self.assertEqual(report.overdue_in_period, 1)
        self.assertEqual(report.overdue_all, 2)
        self.assertEqual((report.shadow_rows, report.unknown_rows, report.undated_rows, report.excluded_rows), (2,1,1,2))
        self.assertEqual(report.evidence.percent, 50.0)
        self.assertEqual(db.total_changes, before)

    def test_unknown_and_empty_do_not_look_failed(self):
        db = fixture()
        self.addCleanup(db.close)
        report = get_report_snapshot(db, 2, 30, date(2026,10,20))
        self.assertEqual(report.total, 0)
        self.assertIsNone(report.evidence.percent)
        self.assertIn('bulunamadı', ' '.join(report.warnings))

    def test_seven_day_cohort(self):
        db = fixture()
        self.addCleanup(db.close)
        report = get_report_snapshot(db, 1, 7, date(2026,10,20))
        self.assertEqual((report.total, report.done), (4, 2))
        self.assertIn('dönemde', report.suggestion.lower() + ' dönemde')

    def test_existing_path_cannot_be_overwritten(self):
        db = fixture()
        self.addCleanup(db.close)
        report = get_report_snapshot(db, 1, 30, date(2026,10,20))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'already.pdf'
            p.write_bytes(b'PRESERVE')
            with self.assertRaises(FileExistsError):
                export_professional_pdf(report, str(p), 'veli')
            self.assertEqual(p.read_bytes(), b'PRESERVE')

    def test_pdf_templates_font_and_pages(self):
        import fitz
        db = fixture()
        self.addCleanup(db.close)
        report = get_report_snapshot(db, 1, 30, date(2026,10,20))
        with tempfile.TemporaryDirectory() as td:
            for template in ('veli', 'ogretmen'):
                output = Path(td)/f'{template}.pdf'
                export_professional_pdf(report, str(output), template)
                self.assertGreater(output.stat().st_size, 2000)
                with fitz.open(str(output)) as pdf:
                    self.assertEqual(len(pdf), 1 if template == 'veli' else 2)
                    text = '\n'.join(page.get_text() for page in pdf)
                    self.assertIn('Örnek Öğrenci', text)
                    self.assertIn('Derse Göre Ödev Takibi', text)
                    self.assertIn('50.0', text)
                    for page in pdf:
                        for block in page.get_text('blocks'):
                            if block[6] == 0:
                                self.assertGreaterEqual(block[0], 0)
                                self.assertLessEqual(block[2], page.rect.width + 1)
                                self.assertLessEqual(block[3], page.rect.height + 1)

    def test_parent_layout_with_twenty_long_subject_names_stays_one_page(self):
        import fitz
        db = fixture()
        self.addCleanup(db.close)
        db.execute("UPDATE ogrenci SET ad='Çok Uzun Türkçe İsim', soyad='Uzun Soyadlı Öğrenci' WHERE id=1")
        for i in range(20):
            db.execute('INSERT INTO odev_kume (id, ogrenci_id, bitis_tarihi) VALUES (?,1,?)',
                       (100+i, '2026-10-17'))
            db.execute('INSERT INTO odev (id,ogrenci_id,kume_id,ders,durum) VALUES (?,?,?,?,?)',
                       (100+i, 1, 100+i, 'Ölçüm ve Değerlendirme / ' * 4 + str(i), 'devam'))
        report = get_report_snapshot(db, 1, 30, date(2026,10,20))
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'veli_stress.pdf'
            export_professional_pdf(report, str(target), 'veli')
            with fitz.open(str(target)) as pdf:
                self.assertEqual(len(pdf), 1)
                self.assertIn('ders daha vardır', pdf[0].get_text())

    def test_pinned_core_sources(self):
        import json
        expected = json.loads((ROOT/'tests/v42_protected_hashes.json').read_text())
        for file, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
