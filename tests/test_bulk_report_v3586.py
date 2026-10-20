# -*- coding: utf-8 -*-
"""V3586 synthetic fixtures only; no live database, network or Qt required."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import hashlib
import tempfile
import unittest

from tests.test_professional_pdf_v3583 import fixture
from tests.test_integrated_report_v3584 import prepared
from services.bulk_reports_v3586 import (active_students, validate_selection, export_batch_pdf, MAX_BATCH_STUDENTS)
from ui.pdf_page_preview_v3586 import rasterize_page

DAY=date(2026,10,20)
ROOT=Path(__file__).resolve().parents[1]


class BulkReportsV3586Tests(unittest.TestCase):
    def setUp(self):
        self.db=fixture()
        self.addCleanup(self.db.close)

    def test_exact_active_student_selection_and_group(self):
        self.assertEqual(tuple(x[0] for x in active_students(self.db)),(2,1))  # sorted by names
        self.assertEqual(validate_selection(self.db,[1,2]),(1,2))
        for invalid in ([],[0],[True],[False],['1'],[1,1],[1,999],[1]*61):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_selection(self.db,invalid)
        self.db.execute('UPDATE ogrenci SET aktif=0 WHERE id=2')
        with self.assertRaises(ValueError):validate_selection(self.db,[2])

    def test_parent_batch_no_cross_student_or_double_count(self):
        import fitz
        self.db.execute('PRAGMA query_only=ON')
        before=self.db.total_changes
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'batch.pdf'
            saved, rows=export_batch_pdf(self.db,[1,2],str(path),period_days=30,template='veli',reference_day=DAY)
            self.assertEqual(saved,str(path))
            self.assertEqual([(r.student_id,r.done,r.total) for r in rows],[(1,2,4),(2,0,0)])
            self.assertEqual(rows[0].percent,50)
            self.assertIsNone(rows[1].percent)
            with fitz.open(path) as pdf:
                self.assertEqual(pdf.page_count,3)
                cover=pdf[0].get_text(); one=pdf[1].get_text(); two=pdf[2].get_text()
                self.assertIn('Örnek Öğrenci',cover)
                self.assertIn('Örnek Öğrenci',one)
                self.assertNotIn('Kaydı Olmayan',one)
                self.assertIn('Kaydı Olmayan',two)
                self.assertNotIn('Örnek Öğrenci',two)
                self.assertIn('Veri yok',two)
                raw,n=rasterize_page(str(path),1,1.0)
                self.assertTrue(raw.startswith(b'\x89PNG'))
                self.assertEqual(n,3)
                with self.assertRaises(IndexError):rasterize_page(str(path),4)
                with self.assertRaises(ValueError):rasterize_page(str(path),0,5.0)
            self.assertEqual(self.db.total_changes,before)

    def test_atomic_no_overwrite_and_recovery_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'do_not_touch.pdf'
            path.write_bytes(b'KEEP OLD FILE')
            with self.assertRaises(FileExistsError):
                export_batch_pdf(self.db,[1],str(path),reference_day=DAY)
            self.assertEqual(path.read_bytes(),b'KEEP OLD FILE')
            new=Path(folder)/'cancel.pdf'
            def cancel(i,n):raise InterruptedError('cancel')
            with self.assertRaises(InterruptedError):
                export_batch_pdf(self.db,[1],str(new),reference_day=DAY, progress=cancel)
            self.assertFalse(new.exists())
            with self.assertRaises(ValueError):
                export_batch_pdf(self.db,[1,2],str(new),template='unknown',reference_day=DAY)
            self.assertFalse(new.exists())

    def test_integrated_batch_student_identity_and_pdf(self):
        import fitz
        self.db.close()
        self.db=prepared()
        self.addCleanup(self.db.close)
        self.db.execute('PRAGMA query_only=ON')
        with tempfile.TemporaryDirectory() as folder:
            pdf_path=Path(folder)/'integrated.pdf'
            _,rows=export_batch_pdf(self.db,[1,2],str(pdf_path),template='butunlesik',reference_day=DAY)
            self.assertEqual(tuple(r.student_id for r in rows),(1,2))
            with fitz.open(pdf_path) as doc:
                self.assertGreaterEqual(doc.page_count,5)
                text='\n'.join(page.get_text() for page in doc)
                self.assertIn('Fizik Öğretmenliği',text)
                self.assertIn('Tıp',text)
                self.assertIn('Haftalık çalışma planı',text)

    def test_existing_core_files_unchanged(self):
        import json
        reference=json.loads((ROOT/'tests/v42_protected_hashes.json').read_text())
        for source,digest in reference.items():
            self.assertEqual(hashlib.sha256((ROOT/source).read_bytes()).hexdigest(),digest)
        center=(ROOT/'ui/report_center_v3581.py').read_text()
        self.assertIn('Toplu PDF + Önizleme',center)
        self.assertIn('def _open_bulk_pdf(',center)
        self.assertIn('def _preview_pages(', (ROOT/'ui/professional_pdf_dialog_v3583.py').read_text())

if __name__=='__main__':unittest.main()
