# -*- coding: utf-8 -*-
"""No live student data. V3584 cross-module read-only and PDF safety tests."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import unittest

from tests.test_professional_pdf_v3583 import fixture
from services.integrated_report_v3584 import (
    read_integrated_report, preview_text, export_integrated_pdf,
)

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 20)


def prepared():
    db = fixture()
    db.executescript('''
      ALTER TABLE ogrenci ADD COLUMN hedef_bolum TEXT;
      ALTER TABLE ogrenci ADD COLUMN hedef_tyt REAL;
      ALTER TABLE ogrenci ADD COLUMN hedef_ayt REAL;
      ALTER TABLE ogrenci ADD COLUMN hedef_lgs REAL;
      UPDATE ogrenci SET hedef_bolum='Fizik Öğretmenliği',hedef_tyt=70,hedef_ayt=40 WHERE id=1;
      UPDATE ogrenci SET hedef_bolum='Tıp',hedef_tyt=110,hedef_ayt=75 WHERE id=2;
      CREATE TABLE denemeler(id INTEGER PRIMARY KEY,tarih TEXT,tur TEXT);
      CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY,deneme_id INTEGER,ogrenci_id INTEGER,
          ders_adi TEXT,dogru INTEGER,yanlis INTEGER,bos INTEGER,net REAL);
      INSERT INTO denemeler VALUES (11,'2026-10-06','TYT'),(12,'2026-10-19','TYT');
      INSERT INTO deneme_sonuclari VALUES
           (101,11,1,'Matematik',8,8,4,6), (102,12,1,'Matematik',10,6,4,8.5),
           (103,12,2,'Türkçe',15,5,0,13.75);
      CREATE TABLE koc_plan(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
          baslangic_tarihi TEXT,bitis_tarihi TEXT);
      CREATE TABLE koc_hedef(id INTEGER PRIMARY KEY,plan_id INTEGER);
      CREATE TABLE koc_program(id INTEGER PRIMARY KEY,plan_id INTEGER);
      CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,durum INTEGER);
      INSERT INTO koc_plan VALUES(90,1,'2026-10-19','2026-10-25');
      INSERT INTO koc_hedef VALUES(91,90);
      INSERT INTO koc_program VALUES(92,90);
      INSERT INTO koc_konu_takip VALUES(99,1,2);
    ''')
    return db


class IntegratedReportTests(unittest.TestCase):
    def test_correct_student_and_source_labeling(self):
        db = prepared()
        self.addCleanup(db.close)
        before = db.total_changes
        db.execute('PRAGMA query_only=ON')
        report = read_integrated_report(db, 1, period_days=30, reference_day=DAY)
        self.assertEqual(report.homework.name, 'Örnek Öğrenci')
        self.assertEqual((report.homework.done, report.homework.total), (2, 4))
        exam = report.section('Deneme sonuçları')
        self.assertIn('8.5', exam.value)
        self.assertIn('Sınırlı karşılaştırma', exam.value)
        self.assertIn('V15', exam.source)
        self.assertEqual(report.section('Kayıtlı hedef').status, 'kayıt')
        self.assertIn('Fizik Öğretmenliği', report.section('Kayıtlı hedef').value)
        self.assertNotIn('Tıp', preview_text(report))
        self.assertIn('1, program girdisi: 1', report.section('Koçluk planı').value)
        self.assertIn('ID ile ilişkilendirilmiş', report.section('Haftalık çalışma planı').scope) if report.section('Haftalık çalışma planı').status == 'kayıt' else self.assertEqual(report.section('Haftalık çalışma planı').status, 'eksik')
        self.assertEqual(db.total_changes, before)

    def test_missing_module_is_explicit_no_fabricated_exam(self):
        db = fixture()
        self.addCleanup(db.close)
        report = read_integrated_report(db, 2, reference_day=DAY)
        self.assertIsNone(report.homework.evidence.percent)
        self.assertEqual(report.section('Deneme sonuçları').status, 'doğrulanamadı')
        self.assertEqual(report.section('Kayıtlı hedef').status, 'doğrulanamadı')
        self.assertIn('Veri yok', preview_text(report))
        self.assertNotIn('başarı %0', preview_text(report))

    def test_cannot_swap_selected_student(self):
        db = prepared()
        self.addCleanup(db.close)
        for sid in (0, -1, 999, True, '1'):
            with self.assertRaises(ValueError):
                read_integrated_report(db, sid, reference_day=DAY)
        db.execute('UPDATE ogrenci SET aktif=0 WHERE id=2')
        with self.assertRaises(ValueError):
            read_integrated_report(db, 2, reference_day=DAY)

    def test_pdf_real_text_and_no_overwrite(self):
        import fitz
        db = prepared()
        self.addCleanup(db.close)
        report = read_integrated_report(db, 1, reference_day=DAY)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'integrated.pdf'
            export_integrated_pdf(report, str(target))
            with fitz.open(target) as pdf:
                self.assertGreaterEqual(len(pdf), 2)
                all_text = '\n'.join(page.get_text() for page in pdf)
                for word in ('Örnek Öğrenci', 'Deneme sonuçları', 'Fizik Öğretmenliği',
                             'Haftalık çalışma planı', 'Sınırlı karşılaştırma'):
                    self.assertIn(word, all_text)
                self.assertNotIn('Tıp', all_text)
                for page in pdf:
                    for block in page.get_text('blocks'):
                        if block[6] == 0:
                            self.assertGreaterEqual(block[0], -1)
                            self.assertLessEqual(block[2], page.rect.width + 1)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            with self.assertRaises(FileExistsError):
                export_integrated_pdf(report, str(target))
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), digest)

    def test_optional_target_reader_failure_is_marked_not_invented(self):
        from unittest.mock import patch
        db = prepared()
        self.addCleanup(db.close)
        with patch('services.integrated_report_v3584.read_saved_target', side_effect=sqlite3.OperationalError('bad table')):
            report = read_integrated_report(db, 1, reference_day=DAY)
        self.assertEqual(report.section('Kayıtlı hedef').status, 'doğrulanamadı')
        self.assertNotIn('Fizik Öğretmenliği', preview_text(report))
        self.assertIn('Hedef Analizi kaynağı okunamadı', ' '.join(report.notes))

    def test_many_subjects_do_not_break_pdf_layout(self):
        import fitz
        db = prepared()
        self.addCleanup(db.close)
        for i in range(25):
            db.execute('INSERT INTO odev_kume (id, ogrenci_id, bitis_tarihi) VALUES (?,1,?)',
                       (1100+i, '2026-10-17'))
            db.execute('INSERT INTO odev (id,ogrenci_id,kume_id,ders,durum) VALUES (?,?,?,?,?)',
                       (1200+i, 1, 1100+i, 'Çok Uzun Türkçe Ders Adı • ' * 4 + str(i), 'devam'))
        report = read_integrated_report(db, 1, reference_day=DAY)
        with tempfile.TemporaryDirectory() as td:
            target = str(Path(td) / 'report.pdf')
            export_integrated_pdf(report, target)
            with fitz.open(target) as pdf:
                self.assertGreaterEqual(len(pdf), 2)
                self.assertLessEqual(len(pdf), 3)
                text = '\n'.join(page.get_text() for page in pdf)
                self.assertIn('ders daha var', text)
                self.assertIn('Deneme sonuçları', text)
                for page in pdf:
                    for block in page.get_text('blocks'):
                        if block[6] == 0:
                            self.assertGreaterEqual(block[0], -1)
                            self.assertLessEqual(block[2], page.rect.width + 1)
                            self.assertLessEqual(block[3], page.rect.height + 1)

    def test_pdf_shortcut_resets_after_student_switch(self):
        import ast
        dialog = (ROOT/'ui/professional_pdf_dialog_v3583.py').read_text(encoding='utf-8')
        tree = ast.parse(dialog)
        methods = [m for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ProfessionalPDFDialog'
                   for m in n.body if isinstance(m, ast.FunctionDef) and m.name == '_preview']
        self.assertEqual(len(methods), 1)
        body = ast.get_source_segment(dialog, methods[0])
        self.assertIn('self._last_file = None', body)
        self.assertIn('self.open_pdf.setEnabled(False)', body)
        self.assertIn("self.template.addItem('Bütünleşik Öğrenci 360", dialog)

    def test_core_sources_not_modified(self):
        import json
        expected = json.loads((ROOT/'tests/v42_protected_hashes.json').read_text())
        for file, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/file).read_bytes()).hexdigest(), digest, file)


if __name__ == '__main__':
    unittest.main()
