"""V15 academic/assignment signal separation and read-only integration."""
import ast
from datetime import date, timedelta
from pathlib import Path
import sqlite3
import unittest

from services.performance_evidence_v14 import compute_evidence
from services.performance_coaching_v15 import compute_coach_rows

NOW=date(2026,10,12)

class CoachingTests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:')
        self.con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, aktif INTEGER);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, bitis_tarihi TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER, durum TEXT, silindi INTEGER, aktarildi INTEGER);
            CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER, durum TEXT, odev_id INTEGER, silindi INTEGER, aktarildi INTEGER);
            CREATE TABLE denemeler(id INTEGER PRIMARY KEY, tarih TEXT, tur TEXT);
            CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY, deneme_id INTEGER, ogrenci_id INTEGER,
                ders_adi TEXT, dogru INTEGER, yanlis INTEGER, bos INTEGER, net REAL);
            CREATE TABLE deneme(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, tur TEXT, tarih TEXT);
            CREATE TABLE deneme_sonuc(id INTEGER PRIMARY KEY, deneme_id INTEGER, ders TEXT, net REAL);
            INSERT INTO ogrenci VALUES (1,'Test','Bir',1), (2,'Test','İki',1), (3,'Kapalı','Öğrenci',0);
        ''')
    def tearDown(self):self.con.close()
    def exam(self, eid, sid=1, day=NOW, kind='TYT', subject='Matematik', correct=15, wrong=5, blank=20, net=13.75):
        self.con.execute('INSERT OR IGNORE INTO denemeler VALUES (?,?,?)',(eid,day.isoformat() if isinstance(day,date) else day,kind))
        self.con.execute('INSERT INTO deneme_sonuclari VALUES (NULL,?,?,?,?,?,?,?)',(eid,sid,subject,correct,wrong,blank,net))
    def legacy(self,eid,sid=1,day=NOW,kind='TYT',subject='Matematik',net=14):
        self.con.execute('INSERT INTO deneme VALUES (?,?,?,?)',(eid,sid,kind,day.isoformat() if isinstance(day,date) else day))
        self.con.execute('INSERT INTO deneme_sonuc VALUES (NULL,?,?,?)',(eid,subject,net))
    def hw(self,gid,sid=1,status='devam',day=NOW-timedelta(days=1)):
        self.con.execute('INSERT INTO odev_kume VALUES (?,?,?)',(gid,sid,day.isoformat()))
        self.con.execute('INSERT INTO odev VALUES (?,?,?,?,0,0)',(gid,gid,sid,status))
    def rows(self):
        evidence=compute_evidence(self.con,NOW)
        return compute_coach_rows(self.con,evidence,as_of=NOW)
    def by(self,sid): return next(x for x in self.rows() if x.student_id==sid)

    def test_empty_data_not_mastery_or_failure(self):
        r=self.by(1);self.assertEqual(r.exam_label,'Deneme verisi yok')
        self.assertIn('veri',r.exam_label.lower())
    def test_readonly_query_only(self):
        self.exam(1);self.con.commit();self.con.execute('PRAGMA query_only=ON')
        self.assertEqual(len(self.rows()),2)
    def test_exam_one_not_comparable(self):
        self.exam(1);self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_two_equal_kind_subject_size(self):
        self.exam(1,day=NOW-timedelta(days=15),net=14)
        self.exam(2,net=11)
        r=self.by(1)
        self.assertEqual(r.evidence_level,'Sınırlı karşılaştırma')
        self.assertIn('-3.0',r.exam_label)
        self.assertIn('güçlüğ',r.detail)
    def test_zero_blank_defaults_do_not_prove_question_count(self):
        self.exam(1,day=NOW-timedelta(days=15),blank=0,net=16)
        self.exam(2,blank=0,net=13)
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_invalid_net_outside_correct_count_rejected(self):
        self.exam(1,net=55,correct=15)
        self.assertEqual(self.by(1).evidence_level,'Yok')
    def test_different_exam_type_never_compared(self):
        self.exam(1,day=NOW-timedelta(days=15),kind='AYT',net=16)
        self.exam(2,kind='TYT',net=13)
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_different_question_count_never_compared(self):
        self.exam(1,day=NOW-timedelta(days=15),blank=10)
        self.exam(2,blank=20)
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_different_subject_not_compared(self):
        self.exam(1,day=NOW-timedelta(days=15),subject='Fizik')
        self.exam(2,subject='Matematik')
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_different_student_not_compared(self):
        self.exam(1,sid=1,day=NOW-timedelta(days=15))
        self.exam(2,sid=2)
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
        self.assertEqual(self.by(2).evidence_level,'Tek ölçüm')
    def test_same_day_not_compared(self):
        self.exam(1,net=12);self.exam(2,net=17)
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_future_excluded(self):
        self.exam(1,day=NOW+timedelta(days=2))
        self.assertEqual(self.by(1).evidence_level,'Yok')
    def test_legacy_localized_date(self):
        self.legacy(1,day='11.10.2026')
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_broken_date_excluded(self):
        self.exam(1,day='not-a-date')
        self.assertEqual(self.by(1).evidence_level,'Yok')
    def test_nonfinite_net_excluded(self):
        self.exam(1,net=float('nan'))
        self.assertEqual(self.by(1).evidence_level,'Yok')
    def test_negative_answer_counts_excluded(self):
        self.exam(1,correct=-1)
        self.assertEqual(self.by(1).evidence_level,'Yok')
    def test_inactive_student_not_shown(self):
        self.exam(1,sid=3)
        self.assertEqual(len(self.rows()),2)
    def test_two_schema_not_cross_compared(self):
        self.exam(1)
        self.legacy(2,day=NOW-timedelta(days=12),net=24)
        r=self.by(1)
        self.assertEqual(r.evidence_level,'Tek ölçüm')
        self.assertIn('birleştirilmedi',r.detail)
    def test_legacy_can_show_latest_without_pair(self):
        self.legacy(1,net=22)
        self.legacy(2,day=NOW-timedelta(days=15),net=11)
        self.assertEqual(self.by(1).evidence_level,'Tek ölçüm')
    def test_overdue_prioritized_without_exam(self):
        self.hw(1,sid=2)
        self.assertEqual(self.rows()[0].student_id,2)
        self.assertIn('gecikmiş',self.by(2).action)
    def test_uncertain_data_not_graded(self):
        self.con.execute('INSERT INTO odev_kume VALUES (10,1,?)',((NOW-timedelta(days=1)).isoformat(),))
        self.con.execute('INSERT INTO odev VALUES (10,10,1,"devam",0,0)')
        self.con.execute('INSERT INTO odev_satir VALUES (20,10,1,"devam",10,0,0)')
        self.assertEqual(self.rows()[0].student_id,1)
        self.assertIn('tutarsız',self.by(1).action)
    def test_exam_difference_never_auto_assignment(self):
        self.exam(1,day=NOW-timedelta(days=15),net=14);self.exam(2,net=11)
        before=list(self.con.execute('SELECT * FROM odev'))
        self.rows()
        self.assertEqual(before,list(self.con.execute('SELECT * FROM odev')))
    def test_missing_exam_tables_keeps_homework_panel(self):
        self.con.execute('DROP TABLE deneme_sonuclari');self.con.execute('DROP TABLE denemeler')
        self.con.execute('DROP TABLE deneme_sonuc');self.con.execute('DROP TABLE deneme')
        self.assertEqual(self.by(1).evidence_level,'Yok')
    def test_ui_fifth_tab_and_all_exports(self):
        text=(Path(__file__).resolve().parents[1]/'ui'/'performans_paneli.py').read_text(encoding='utf8')
        ast.parse(text)
        self.assertIn('self.tabCoach = QTableWidget()',text)
        self.assertIn('with tempfile.TemporaryDirectory(',text)
        self.assertIn('shutil.rmtree(tmpdir, ignore_errors=True)',text)
        self.assertIn('self.tabCoach)',text)
        self.assertIn('self._fill_coaching(con)',text)
        self.assertEqual(text.count('elif current_idx == 4: table = self.tabCoach'),2)
        self.assertIn('self.tabClub, self.tabEvidence, self.tabCoach',text)

if __name__=='__main__':unittest.main()
