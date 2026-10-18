from contextlib import closing
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.teacher_copilot_v5 import read_teacher_feed, sort_for_teacher
from services.teacher_feedback_v5 import vote, read_feedback, preference
from services.daily_brief_v11 import ensure_review_table, set_reviewed
from services.daily_coach_v10 import collect_student_facts, make_suggestions

TODAY = date(2026, 10, 15)


class CopilotV5Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'pilot öğrenci.db'
        self.feedback = Path(self.tmp.name) / 'feedback.json'
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,
               dogum_tarihi TEXT,veli_tel1 TEXT,aktif INTEGER);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
               verilis_tarihi TEXT,bitis_tarihi TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,
               ogrenci_id INTEGER,ders TEXT,durum TEXT);
            INSERT INTO ogrenci VALUES(1,'Deniz','Bir',NULL,'05551111111',1);
            INSERT INTO ogrenci VALUES(2,'Bora','İki',NULL,'05552222222',1);
            INSERT INTO ogrenci VALUES(3,'Pasif','Üç',NULL,'05553333333',0);
            INSERT INTO odev_kume VALUES(11,1,'2026-10-01','2026-10-12');
            INSERT INTO odev VALUES(101,11,1,'Matematik','devam');
            INSERT INTO odev_kume VALUES(12,2,'2026-10-01','2026-10-12');
            INSERT INTO odev VALUES(102,12,2,'Fizik','devam');
            INSERT INTO odev_kume VALUES(13,3,'2026-10-01','2026-10-12');
            INSERT INTO odev VALUES(103,13,3,'Biyoloji','devam');
            -- Cross-student join must not count below row for Deniz.
            INSERT INTO odev VALUES(104,12,1,'Türkçe','devam');
        ''')
        con.commit();con.close()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def advisor(con, sid):
        return {'student_id': sid, 'evidence_count': 0,
                'status': 'Kontrol', 'actions': [{'title':'Ölçüm gerek',
                      'next_step':'Bağımsız tanılama', 'source':'V27 test'}],
                'warnings': [], 'as_of': TODAY.isoformat()}

    def test_snapshot_is_readonly_and_cross_student_safe(self):
        before = self.db.read_bytes()
        feed = read_teacher_feed(self.db, today=TODAY,
                  feedback_path=self.feedback, advisor=self.advisor)
        self.assertEqual(len(feed['cards']), 2)
        self.assertEqual(feed['cards'][0]['student_id'], 1)
        self.assertEqual(feed['cards'][0]['coach']['evidence_count'], 0)
        self.assertIn('Ölçüm gerek',feed['cards'][0]['coach']['priority'])
        self.assertEqual(before, self.db.read_bytes())
        text = json.dumps(feed, ensure_ascii=False)
        self.assertNotIn('0555',text)
        self.assertNotIn('Türkçe',text)
        self.assertNotIn('Pasif',text)
        self.assertFalse(self.feedback.exists())
        self.assertFalse(feed['remote_verified'])

    def test_reviewed_priority_is_hidden_and_new_evidence_returns(self):
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        ensure_review_table(con)
        s = next(s for s in make_suggestions(collect_student_facts(con,TODAY),TODAY)
                 if s['type']=='overdue' and s['data']['id']==1)
        set_reviewed(con,s,True,TODAY)
        con.commit();con.close()
        feed = read_teacher_feed(self.db,today=TODAY,feedback_path=self.feedback,
                                 advisor=self.advisor)
        self.assertEqual([x['student_id'] for x in feed['cards']],[2])
        with closing(sqlite3.connect(self.db)) as con:
            con.execute("INSERT INTO odev_kume VALUES(14,1,'2026-10-03','2026-10-14')")
            con.execute("INSERT INTO odev VALUES(105,14,1,'Fen','devam')")
            con.commit()
        feed=read_teacher_feed(self.db,today=TODAY,feedback_path=self.feedback,advisor=self.advisor)
        self.assertIn(1,[x['student_id'] for x in feed['cards']])

    def test_missing_db_does_not_create_a_new_database(self):
        target = Path(self.tmp.name)/'absent.db'
        with self.assertRaises(FileNotFoundError):
            read_teacher_feed(target,today=TODAY)
        self.assertFalse(target.exists())

    def test_advisor_exception_does_not_break_homework_summary(self):
        def bad(con, sid): raise RuntimeError('error')
        feed=read_teacher_feed(self.db,today=TODAY,feedback_path=self.feedback,advisor=bad)
        self.assertEqual(len(feed['cards']),2)
        self.assertIsNone(feed['cards'][0]['coach'])

    def test_feedback_contains_no_student_records(self):
        vote('star','useful',self.feedback)
        vote('star','useful',self.feedback)
        vote('silent','not_useful',self.feedback)
        self.assertEqual(preference(read_feedback(self.feedback),'star'),2)
        self.assertEqual(preference(read_feedback(self.feedback),'silent'),-1)
        self.assertNotIn('student',self.feedback.read_text())
        with self.assertRaises(ValueError):
            vote('student_1','useful',self.feedback)
        self.assertEqual(len(read_feedback(self.feedback)),2)

    def test_ordering_preserves_overdue_first(self):
        x=[{'type':'birthday','title':'b'},{'type':'overdue','title':'u1'},
           {'type':'star','title':'s'},{'type':'overdue','title':'u2'}]
        prefs={'birthday':{'useful':0,'not_useful':5}, 'star':{'useful':6,'not_useful':0}}
        ordered=sort_for_teacher(x,prefs)
        self.assertEqual([i['title'] for i in ordered],['u1','u2','s','b'])

if __name__=='__main__': unittest.main()
