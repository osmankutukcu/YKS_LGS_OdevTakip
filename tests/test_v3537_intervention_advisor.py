"""V3.5.37 synthetic-only conservative non-writing intervention tests."""
from datetime import date
from pathlib import Path
import ast
import sqlite3
import unittest

from services.intervention_advisor_v3537 import (build_intervention_draft,
                                                       read_comparable_exam_signals)
from tests.test_v3536_academic_actions import db
from services.academic_actions_v3536 import read_student_action_card
from tools.v3527_core_guard import audit

DAY=date(2026,10,18)
ROOT=Path(__file__).resolve().parents[1]


def exams(con):
    con.executescript('''
    CREATE TABLE denemeler(id INTEGER PRIMARY KEY,tarih TEXT,tur TEXT);
    CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY,deneme_id INTEGER,
      ogrenci_id INTEGER,ders_adi TEXT,dogru INTEGER,yanlis INTEGER,bos INTEGER,net REAL);
    CREATE TABLE deneme(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,tur TEXT,tarih TEXT);
    CREATE TABLE deneme_sonuc(id INTEGER PRIMARY KEY,deneme_id INTEGER,ders TEXT,net REAL);
    INSERT INTO denemeler VALUES (11,'2026-09-20','TYT');
    INSERT INTO denemeler VALUES (12,'2026-10-10','TYT');
    INSERT INTO denemeler VALUES (13,'2026-10-11','AYT');
    INSERT INTO deneme_sonuclari VALUES (111,11,1,'Fizik',9,5,6,7.75);
    INSERT INTO deneme_sonuclari VALUES (112,12,1,'Fizik',7,7,6,5.25);
    INSERT INTO deneme_sonuclari VALUES (113,11,2,'Fizik',14,2,4,13.5);
    INSERT INTO deneme_sonuclari VALUES (114,12,2,'Fizik',12,4,4,11.0);
    ''')

class InterventionTests(unittest.TestCase):
    def setUp(self):
        self.con=db()
    def tearDown(self):
        self.con.close()

    def test_student_specific_tyt_measurements(self):
        exams(self.con)
        review=read_comparable_exam_signals(self.con,1,today=DAY)
        self.assertEqual(review['state'],'COMPARABLE_RECORDS')
        self.assertEqual(len(review['signals']),1)
        self.assertEqual(review['signals'][0]['net_delta'],-2.5)
        self.assertEqual(review['signals'][0]['recorded_question_count'],20)
        self.assertFalse(review['signals'][0]['difficulty_equivalence_verified'])

    def test_interventions_order_and_read_only(self):
        exams(self.con)
        before=self.con.total_changes
        old_factory=self.con.row_factory
        draft=build_intervention_draft(self.con,1,today=DAY)
        self.assertEqual([x['type'] for x in draft['recommendations']],
                         ['FOLLOWUP_OVERDUE','REVIEW_EXAM_CHANGE'])
        self.assertEqual(draft['recommendations'][1]['subject'],'Fizik')
        self.assertFalse(draft['auto_change_allowed'])
        self.assertFalse(draft['assignments_created'])
        self.assertFalse(draft['messages_sent'])
        self.assertFalse(draft['calendar_written'])
        self.assertEqual(before,self.con.total_changes)
        self.assertIs(old_factory,self.con.row_factory)

    def test_wrong_identity_card_always_rejected(self):
        card=read_student_action_card(self.con,1,today=DAY)
        for sid in (2,3,0,-1,True,'1',None):
            with self.subTest(sid=sid),self.assertRaises(ValueError):
                build_intervention_draft(self.con,sid,today=DAY,action_card=card)
        with self.assertRaises(ValueError):
            build_intervention_draft(self.con,1,today=date(2026,10,17),action_card=card)

    def test_inactive_student_rejected_even_when_card_was_precomputed(self):
        card=read_student_action_card(self.con,1,today=DAY)
        self.con.execute('UPDATE ogrenci SET aktif=0 WHERE id=1')
        with self.assertRaises(ValueError):
            build_intervention_draft(self.con,1,today=DAY,action_card=card)

    def test_wrong_owner_blocks_academic_and_exam_numbers(self):
        exams(self.con)
        self.con.execute("INSERT INTO odev_satir VALUES(391,2,100,101,'Fizik','devam',0,0)")
        for sid in (1,2):
            with self.subTest(sid=sid):
                result=build_intervention_draft(self.con,sid,today=DAY)
                self.assertEqual(result['state'],'DATA_REVIEW')
                self.assertEqual(result['exam']['state'],'WITHHELD')
                self.assertEqual([r['type'] for r in result['recommendations']],['VERIFY_LINKS'])
                self.assertNotIn('13.5',repr(result))

    def test_missing_exam_table_no_false_clean(self):
        result=build_intervention_draft(self.con,1,today=DAY)
        self.assertEqual(result['exam']['state'],'SOURCE_UNVERIFIED')
        self.assertIn('FOLLOWUP_OVERDUE',[x['type'] for x in result['recommendations']])

    def test_missing_blank_coverage_skips_comparison(self):
        exams(self.con)
        self.con.execute('UPDATE deneme_sonuclari SET bos=0 WHERE ogrenci_id=1')
        result=read_comparable_exam_signals(self.con,1,today=DAY)
        self.assertEqual(result['state'],'INSUFFICIENT_COMPARABLE')
        self.assertEqual(result['signals'],[])

    def test_mixed_exam_types_and_denominators_not_compared(self):
        exams(self.con)
        self.con.execute("UPDATE denemeler SET tur='AYT' WHERE id=12")
        self.assertEqual(read_comparable_exam_signals(self.con,1,today=DAY)['signals'],[])
        self.con.execute("UPDATE denemeler SET tur='TYT' WHERE id=12")
        self.con.execute('UPDATE deneme_sonuclari SET bos=3 WHERE id=112')
        self.assertEqual(read_comparable_exam_signals(self.con,1,today=DAY)['signals'],[])

    def test_future_invalid_and_same_day_not_compared(self):
        exams(self.con)
        self.con.execute("UPDATE denemeler SET tarih='2027-10-10' WHERE id=12")
        self.assertEqual(read_comparable_exam_signals(self.con,1,today=DAY)['signals'],[])
        self.con.execute("UPDATE denemeler SET tarih='2026-09-20' WHERE id=12")
        self.assertEqual(read_comparable_exam_signals(self.con,1,today=DAY)['signals'],[])
        self.con.execute("UPDATE denemeler SET tarih='bad_date' WHERE id=12")
        self.assertGreater(read_comparable_exam_signals(self.con,1,today=DAY)['excluded_rows'],0)

    def test_legacy_exam_never_merged_as_new(self):
        exams(self.con)
        self.con.execute('DELETE FROM deneme_sonuclari WHERE id=112')
        self.con.execute("INSERT INTO deneme VALUES(101,1,'TYT','2026-10-10')")
        self.con.execute("INSERT INTO deneme_sonuc VALUES(101,101,'Fizik',5.25)")
        self.assertEqual(read_comparable_exam_signals(self.con,1,today=DAY)['signals'],[])

    def test_plan_review_when_missing(self):
        self.con.execute('DELETE FROM odev WHERE ogrenci_id=1')
        self.con.execute('DELETE FROM koc_program')
        self.con.execute('DELETE FROM koc_plan')
        result=build_intervention_draft(self.con,1,today=DAY)
        self.assertEqual(result['recommendations'][0]['type'],'REVIEW_PLAN')
        self.assertTrue(result['requires_teacher_approval'])

    def test_no_change_does_not_create_diagnosis(self):
        exams(self.con)
        self.con.execute('UPDATE deneme_sonuclari SET net=8.25 WHERE id=112')
        self.con.execute("UPDATE odev SET durum='tamam' WHERE id=101")
        result=build_intervention_draft(self.con,1,today=DAY)
        self.assertEqual(result['state'],'NO_VERIFIED_INTERVENTION')
        self.assertTrue(result['not_learning_or_risk_diagnosis'])
        self.assertEqual(result['recommendations'],[])

    def test_draft_reuses_existing_action_card(self):
        exams(self.con)
        card=read_student_action_card(self.con,1,today=DAY)
        self.con.execute('DROP TABLE odev_satir')
        result=build_intervention_draft(self.con,1,today=DAY,action_card=card)
        self.assertEqual(result['student_id'],1)
        self.assertEqual(result['exam']['state'],'COMPARABLE_RECORDS')

    def test_unverified_cohort_partial_not_false_certainty(self):
        self.con.execute("UPDATE odev_kume SET bitis_tarihi='?' WHERE id=100")
        result=build_intervention_draft(self.con,1,today=DAY)
        self.assertEqual(result['state'],'NO_VERIFIED_INTERVENTION')
        self.assertTrue(any('kısmi' in x for x in result['limitations']))

    def test_contact_never_in_plan(self):
        exams(self.con)
        r=build_intervention_draft(self.con,1,today=DAY)
        self.assertNotIn('05551234567',repr(r))
        self.assertNotIn('Test Öğrenci',repr(r))

    def test_row_factory_both(self):
        exams(self.con)
        self.con.row_factory=sqlite3.Row
        r=build_intervention_draft(self.con,1,today=DAY)
        self.assertEqual(r['student_id'],1)
        self.assertIs(self.con.row_factory,sqlite3.Row)

    def test_core_and_python_integration(self):
        self.assertEqual(audit(ROOT)['status'],'PASS')
        for rel in ('services/intervention_advisor_v3537.py','ui/student360_panel_v16.py',
                    'ui/teacher_copilot_strip_v5.py','services/teacher_copilot_v5.py',
                    'services/coach_assistant_v1/module_bridge_v264.py'):
            ast.parse((ROOT/rel).read_text('utf8'))
        for rel in ('ui/homework_form.py','ui/odev_kontrol.py','db.py'):
            self.assertNotIn('v3537', (ROOT/rel).read_text('utf8').lower())

if __name__=='__main__': unittest.main()
