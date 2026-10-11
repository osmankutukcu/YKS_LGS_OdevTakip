"""V7 grade-locked, evidence-first curriculum proposal checks."""
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from services.coach_curriculum_v7 import (
    load_catalog, detect_grade, exact_outcome, build_outcome_review,
    outcome_as_html, outcome_as_text, _source_is_official,
)

TODAY = date(2026, 10, 11)


def database():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,ana_grup TEXT,alt_grup TEXT);
        INSERT INTO ogrenci VALUES(1,'Deneme','Kişisi','YKS','9. Sınıf'),
            (2,'Başka','Kişi','YKS','11-SAY'),(3,'Mezun','Aday','YKS','Mezun');
        CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,bitis_tarihi TEXT);
        INSERT INTO odev_kume VALUES (1,'2026-10-01'),(2,'2026-10-30');
        CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
            odev_id INTEGER, kume_id INTEGER,ders TEXT,konu TEXT,kitap TEXT,
            durum TEXT,tarih TEXT,tamamlanma_tarihi TEXT,silindi INTEGER DEFAULT 0);
        CREATE TABLE koc_konu_takip(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
            ders_adi TEXT,konu_adi TEXT,hakimiyet_puani REAL,updated_at TEXT);
    ''')
    return db


class CurriculumTest(unittest.TestCase):
    def setUp(self):
        self.db = database()
        self.catalog = load_catalog()
    def tearDown(self):
        self.db.close()
    def row(self, student=1, topic='Basınç', subject='Fizik', group=1, status='devam',deleted=0):
        self.db.execute('''INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,kitap,durum,silindi)
                           VALUES(?,?,?,?,?,?,?)''', (student,group,subject,topic,'Kitap A',status,deleted))
    def rate(self,score, student=1, topic='Basınç', dated='2026-10-10'):
        self.db.execute('''INSERT INTO koc_konu_takip(ogrenci_id,ders_adi,konu_adi,hakimiyet_puani,updated_at)
        VALUES(?,?,?,?,?)''',(student,'Fizik',topic,score,dated))
    def review(self,student=1,**kw):
        return build_outcome_review(self.db,student,as_of=TODAY,**kw)

    def test_verified_example_catalog_is_tiny_not_all_curriculum(self):
        self.assertEqual(len(self.catalog),4)
    def test_exact_alias_maps_only_own_subject_and_grade(self):
        self.assertIsNotNone(exact_outcome('Fizik','Basınç',9,self.catalog))
        self.assertIsNone(exact_outcome('Kimya','Basınç',9,self.catalog))
        self.assertIsNone(exact_outcome('Fizik','Basınç',10,self.catalog))
        self.assertIsNone(exact_outcome('Fizik','Basınç konusu',9,self.catalog))
    def test_grade_parser_avoids_exam_track_inference(self):
        self.assertEqual(detect_grade({'alt_grup':'11-SAY'}),11)
        self.assertEqual(detect_grade({'alt_grup':'9. Sınıf'}),9)
        for value in ('', 'Mezun', '9abc', 'LGS', '2026-grup'):
            self.assertIsNone(detect_grade({'alt_grup':value}))
    def test_grade_unknown_does_not_guess(self):
        self.row(student=3)
        self.assertEqual(self.review(3)['actions'],[])
    def test_no_tasks_no_fake_missing_outcomes(self):
        self.assertEqual(self.review()['actions'],[])
    def test_real_overdue_prompts_verification_not_new_work(self):
        self.row()
        r=self.review()
        self.assertEqual(r['actions'][0]['type'],'overdue_check')
        self.assertEqual(r['total_minutes'],0)
        self.assertTrue(r['actions'][0]['approval_required'])
    def test_pending_not_overdue(self):
        self.row(group=2)
        self.assertEqual(self.review()['actions'][0]['type'],'pending_check')
    def test_completed_does_not_prove_mastery(self):
        self.row(status='tamam')
        action=self.review()['actions'][0]
        self.assertEqual(action['type'],'retention_check')
        self.assertIn('ölçülmedi',action['evidence'])
    def test_no_cross_student_homework(self):
        self.row(student=2,topic='Newton Hareket Yasaları')
        self.assertEqual(self.review()['actions'],[])
        self.assertEqual(self.review(2)['actions'][0]['grade'],11)
    def test_deleted_does_not_match(self):
        self.row(deleted=1)
        self.assertEqual(self.review()['mapped_topics'],0)
    def test_low_valid_teacher_score_adds_measurement(self):
        self.rate(35)
        action=self.review()['actions'][0]
        self.assertEqual(action['type'],'teacher_review')
        self.assertEqual(action['minutes'],20)
    def test_score_zero_is_not_evidence(self):
        self.rate(0)
        self.assertEqual(self.review()['actions'],[])
    def test_score_nan_not_accepted(self):
        self.rate(float('nan'))
        self.assertEqual(self.review()['actions'],[])
    def test_future_and_stale_scores_rejected(self):
        self.rate(20,dated='2026-10-12')
        self.rate(25,dated='2025-09-12')
        self.assertEqual(self.review()['actions'],[])
    def test_other_student_score_not_leak(self):
        self.rate(20,student=2,topic='Newton Hareket Yasaları')
        self.assertEqual(self.review()['actions'],[])
    def test_strict_daily_time_cap(self):
        self.row(status='tamam',topic='Basınç')
        self.row(status='tamam',topic='Isıl Denge')
        r=self.review(max_minutes=15)
        self.assertEqual(len(r['actions']),1)
        self.assertLessEqual(r['total_minutes'],15)
    def test_none_negative_budget_fails(self):
        with self.assertRaises(ValueError): self.review(max_minutes=-1)
    def test_crosswalk_has_no_outbound_requests_or_db_changes(self):
        self.row()
        before=self.db.total_changes
        out=self.review()
        self.assertEqual(before,self.db.total_changes)
        self.assertFalse(out['write_performed'])
    def test_injecting_topic_html_escaped(self):
        entries=[dict(self.catalog[0],topic_aliases=['<img onerror=alert(1)>'])]
        self.row(topic='<img onerror=alert(1)>')
        html=outcome_as_html(self.review(catalog=entries))
        self.assertNotIn('<img',html)
        self.assertNotIn('onerror=',html)
    def test_text_export_has_evidence_and_source(self):
        self.row()
        output=outcome_as_text(self.review())
        self.assertIn('https://ttkbyayin.meb.gov.tr/yayin/300',output)
    def test_official_url_checks(self):
        for bad in ['http://tymm.meb.gov.tr/x','https://tymm.meb.gov.tr.evil.test/a',
                    'https://u@tymm.meb.gov.tr/a','https://tymm.meb.gov.tr:8888/a',
                    'file:///etc/passwd']:
            self.assertFalse(_source_is_official(bad))
    def test_bad_catalog_rejected(self):
        src=json.loads((Path(__file__).parent.parent/'assets'/'coach_curriculum_v7.json').read_text(encoding='utf8'))
        src['outcomes'][0]['source_url']='https://evil.test/x'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'in.json'
            p.write_text(json.dumps(src),encoding='utf8')
            with self.assertRaises(ValueError):load_catalog(p)
    def test_ambiguous_alias_rejected_not_picked(self):
        two=dict(self.catalog[1], topic_aliases=['Basınç'])
        self.assertIsNone(exact_outcome('Fizik','Basınç',9,[self.catalog[0],two]))
    def test_unknown_topic_not_classed_as_weakness(self):
        self.row(topic='Atom Modelleri')
        r=self.review()
        self.assertEqual(len(r['actions']),0)
        self.assertEqual(r['unmapped_topics'],1)
    def test_english_casefold_turkish_title(self):
        self.row(topic='Basınç',subject='FİZİK')
        self.assertEqual(self.review()['mapped_topics'],1)
    def test_unmatched_teacher_rating_still_prompts_review(self):
        self.rate(30,topic='Elektrik')
        report=self.review()
        self.assertEqual(report['actions'],[])
        self.assertEqual(report['general_actions'][0]['topic'],'Elektrik')
        self.assertEqual(report['general_actions'][0]['source_status'],'no_official_match')
    def test_high_teacher_rating_no_review(self):
        self.rate(85,topic='Elektrik')
        self.assertEqual(self.review()['general_actions'],[])
    def test_generic_review_preserves_budget(self):
        self.rate(30,topic='Elektrik')
        self.rate(20,topic='Biyofizik')
        report=self.review(max_minutes=20)
        self.assertEqual(report['total_minutes'],20)
        self.assertEqual(len(report['general_actions']),1)
    def test_unmatched_student_data_never_crosses(self):
        self.rate(20,student=2,topic='Elektrik')
        self.assertEqual(self.review()['general_actions'],[])
    def test_grade_override_is_preview_only(self):
        self.row(student=3,topic='Newton Hareket Yasaları')
        self.assertEqual(self.review(3)['actions'],[])
        report=self.review(3,grade_override=11)
        self.assertEqual(report['actions'][0]['grade'],11)
        self.assertEqual(self.db.execute('SELECT alt_grup FROM ogrenci WHERE id=3').fetchone()[0],'Mezun')
    def test_invalid_grade_override_rejected(self):
        for val in (0,13,'9',True):
            with self.assertRaises(ValueError):self.review(grade_override=val)


if __name__=='__main__':unittest.main()
