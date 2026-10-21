# -*- coding: utf-8 -*-
"""V3592 synthetic evidence and guarded review-plan regression tests."""
from __future__ import annotations
from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tests.test_integrated_report_v3584 import prepared
from services.report_academic_bridge_v3591 import read_academic_evidence
from services.professional_pdf_v3583 import get_report_snapshot
from services.report_intervention_plan_v3592 import plan_teacher_review
from services.integrated_report_v3584 import read_integrated_report, preview_text, export_integrated_pdf

DAY = date(2026,10,21)


def source():
    con = prepared()
    con.execute('ALTER TABLE koc_konu_takip ADD COLUMN ders_adi TEXT')
    con.execute('ALTER TABLE koc_konu_takip ADD COLUMN konu_adi TEXT')
    con.execute("UPDATE koc_konu_takip SET ders_adi='TYT Matematik', konu_adi='Problemler' WHERE id=99")
    con.execute("INSERT INTO koc_konu_takip(id,ogrenci_id,ders_adi,konu_adi,durum) VALUES(100,1,'TYT Matematik','Denklemler',4)")
    return con


class ReviewPlanTests(unittest.TestCase):
    def setUp(self):
        self.db=source()
        self.addCleanup(self.db.close)

    def academic(self, sid=1):
        return read_academic_evidence(self.db,sid,reference_day=DAY)

    def test_bounded_typed_measurements_not_mastery(self):
        evidence=self.academic()
        self.assertTrue(evidence.courses)
        data=evidence.courses[0]
        self.assertEqual(data.course_code,'tyt_matematik')
        self.assertEqual(data.exam_net,8.5)
        self.assertEqual(data.topic_count,2)
        self.assertEqual(data.marked_topics,1)
        plan=plan_teacher_review(evidence)
        self.assertEqual(plan.level,'ölçüm var')
        self.assertEqual(len(plan.steps),2)
        self.assertIn('TYT Matematik',plan.steps[0].instruction)
        self.assertIn('öğretmen',plan.steps[0].instruction)
        self.assertNotIn('öğrenci başarısız',repr(plan))

    def test_multiple_same_exam_measurement_requires_review(self):
        self.db.execute("INSERT INTO deneme_sonuclari(id,deneme_id,ogrenci_id,ders_adi,dogru,yanlis,bos,net) VALUES(202,12,1,'Matematik',15,2,3,14.5)")
        e=self.academic()
        self.assertTrue(e.courses[0].repeated_measurement)
        self.assertIsNone(e.courses[0].exam_net)
        plan=plan_teacher_review(e)
        self.assertEqual(plan.level,'önce doğrula')
        self.assertEqual(len(plan.steps),1)
        self.assertNotIn('14.5 net',repr(plan))

    def test_conflicting_topic_marks_are_not_mastery(self):
        self.db.execute("INSERT INTO koc_konu_takip(id,ogrenci_id,ders_adi,konu_adi,durum) VALUES(201,1,'TYT Matematik','Denklemler',2)")
        e=self.academic()
        self.assertEqual(e.courses[0].conflicting_topics,1)
        self.assertEqual(plan_teacher_review(e).steps[0].heading,'Önce veriyi doğrula')
        self.assertEqual(len(plan_teacher_review(e).steps),1)

    def test_unmatched_course_gives_review_not_diagnosis(self):
        self.db.execute("UPDATE deneme_sonuclari SET ders_adi='Matematik-genel' WHERE ogrenci_id=1")
        e=self.academic()
        plan=plan_teacher_review(e)
        self.assertEqual(plan.level,'önce doğrula')
        self.assertNotIn('TYT Matematik:',repr(plan))

    def test_different_student_never_receives_selected_students_measures(self):
        e=self.academic(2)
        self.assertNotIn('TYT Matematik',e.value)
        plan=plan_teacher_review(e)
        self.assertNotIn('TYT Matematik',repr(plan))
        self.assertNotIn('8.5',repr(plan))

    def test_missing_sources_do_not_give_synthetic_diagnoses(self):
        con=prepared()
        self.addCleanup(con.close)
        e=read_academic_evidence(con,1,reference_day=DAY)
        self.assertEqual(e.status,'doğrulanamadı')
        plan=plan_teacher_review(e)
        self.assertEqual(plan.level,'önce doğrula')
        self.assertEqual(len(plan.steps),1)

    def test_read_only_and_report_keeps_prior_metrics(self):
        before=self.db.total_changes
        self.db.execute('PRAGMA query_only=ON')
        report=read_integrated_report(self.db,1,reference_day=DAY)
        original=get_report_snapshot(self.db,1,30,DAY)
        self.assertEqual((report.homework.done,report.homework.total),
                         (original.done,original.total))
        self.assertIn('ÖĞRETMEN IÇIN KONTROLLÜ SONRAKI ADIMLAR',preview_text(report))
        self.assertEqual(report.section('Öğretmen için kontrollü sonraki adımlar').status,'kayıt')
        self.assertEqual(self.db.total_changes,before)
        with self.assertRaises(ValueError):
            read_academic_evidence(self.db,2.0,reference_day=DAY)

    def test_missing_measurement_no_false_failure_label(self):
        self.db.execute('DELETE FROM deneme_sonuclari WHERE ogrenci_id=1')
        e=self.academic()
        plan=plan_teacher_review(e)
        self.assertEqual(plan.level,'veri yetersiz')
        self.assertEqual(len(plan.steps),1)
        self.assertIn('ölçüm',plan.steps[0].instruction)

    def test_rendered_pdf_stays_two_pages(self):
        import fitz
        report=read_integrated_report(self.db,1,reference_day=DAY)
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'student.pdf')
            export_integrated_pdf(report,path)
            with fitz.open(path) as pdf:
                self.assertEqual(len(pdf),2)
                body=' '.join(p.get_text() for p in pdf)
                self.assertIn('Öğretmen için kontrollü sonraki adımlar',body)
                self.assertNotIn('otomatik kazanım teşhisi yapıldı',body)
                for page in pdf:
                    for block in page.get_text('blocks'):
                        if block[6]==0:
                            self.assertGreaterEqual(block[0],-1)
                            self.assertLessEqual(block[2],page.rect.width+1)
                            self.assertLessEqual(block[3],page.rect.height+1)

    def test_rejects_arbitrary_text_and_does_not_call_outside_services(self):
        with self.assertRaises(TypeError):
            plan_teacher_review('8 net eksik kazanım')

if __name__=='__main__':
    unittest.main()
