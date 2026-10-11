import sqlite3
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.daily_coach_v10 import (parse_day, days_since, tracking_indicator,
                                       collect_student_facts, make_suggestions)

TODAY = date(2026, 10, 11)


def fixture():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript('''
    CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, dogum_tarihi TEXT, veli_tel1 TEXT, aktif INTEGER);
    CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, verilis_tarihi TEXT, bitis_tarihi TEXT);
    CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER, ders TEXT, durum TEXT);
    INSERT INTO ogrenci VALUES(1,'Osman','Fizik',NULL,'555',1);
    INSERT INTO ogrenci VALUES(2,'Ali','Veli',NULL,NULL,1);
    INSERT INTO ogrenci VALUES(3,'Pasif','Kisi',NULL,NULL,0);
    ''')
    return c


def add_task(con, kid, sid, issued, due, status='devam', lesson='Fizik', row_sid=None):
    con.execute('INSERT INTO odev_kume VALUES(?,?,?,?)',
                (kid, sid, issued.isoformat() if issued else None, due.isoformat() if due else None))
    con.execute('INSERT INTO odev VALUES(?,?,?,?,?)',
                (kid, kid, row_sid if row_sid is not None else sid, lesson, status))


class DailyCoachTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(parse_day('11.10.2026'), TODAY)
        self.assertEqual(parse_day('2026-10-11'), TODAY)
        self.assertEqual(parse_day('2026-10-11 10:10:00'), TODAY)
        self.assertIsNone(parse_day('not_a_date'))
        self.assertIsNone(days_since('2027-01-01', TODAY))
    def test_no_task_is_unknown_not_999(self):
        c=fixture()
        f=collect_student_facts(c,TODAY)[0]
        self.assertIsNone(f['days_since_assigned'])
        self.assertIsNone(f['tracking_indicator'])
        suggestions=make_suggestions([f],TODAY)
        self.assertIn('Takip kaydı',suggestions[0]['title'])
        self.assertNotIn('999',str(suggestions))
    def test_assignment_date_not_activity(self):
        c=fixture(); add_task(c,1,1,TODAY-timedelta(days=287),TODAY-timedelta(days=200))
        f=collect_student_facts(c,TODAY)[0]
        self.assertEqual(f['days_since_assigned'],287)
        s=make_suggestions([f],TODAY)[0]
        self.assertNotIn('287 gündür hareket yok',str(s))
        self.assertEqual(s['type'],'overdue')
    def test_overdue_categories(self):
        c=fixture(); add_task(c,1,1,TODAY-timedelta(days=50),TODAY-timedelta(days=10))
        add_task(c,2,1,TODAY-timedelta(days=100),TODAY-timedelta(days=60))
        f=collect_student_facts(c,TODAY)[0]
        self.assertEqual(f['overdue_recent'],1)
        self.assertEqual(f['overdue_old'],1)
        self.assertEqual(f['tracking_indicator'],10)
    def test_completed_is_not_overdue(self):
        c=fixture(); add_task(c,1,1,TODAY-timedelta(days=1),TODAY-timedelta(days=1),'tamam')
        f=collect_student_facts(c,TODAY)[0]
        self.assertEqual(f['overdue_recent'],0)
        self.assertEqual(f['completed_in_recent_set'],1)
    def test_done_in_recently_issued_not_claim_done_recent(self):
        c=fixture()
        for i in range(1,6):add_task(c,i,1,TODAY-timedelta(days=1),TODAY+timedelta(days=6),'tamam')
        f=collect_student_facts(c,TODAY)[0]
        s=make_suggestions([f],TODAY)[0]
        self.assertEqual(s['type'],'star')
        self.assertIn('verilen',s['desc'])
        self.assertIn('tutulmadığı',s['reasons'][0])
    def test_birthdays_are_not_risk(self):
        c=fixture(); c.execute('UPDATE ogrenci SET dogum_tarihi=? WHERE id=1',('2009-10-11',))
        add_task(c,1,1,TODAY,TODAY+timedelta(days=7))
        f=collect_student_facts(c,TODAY)[0]
        self.assertEqual(f['tracking_indicator'],0)
        s=make_suggestions([f],TODAY)
        self.assertEqual([x['type'] for x in s],['birthday'])
    def test_missing_birthday_does_not_invent_risk(self):
        c=fixture()
        self.assertIsNone(collect_student_facts(c,TODAY)[0]['tracking_indicator'])
    def test_mismatched_student_ids_not_attributed(self):
        c=fixture(); add_task(c,1,1,TODAY,TODAY-timedelta(days=3),row_sid=2)
        facts={x['id']:x for x in collect_student_facts(c,TODAY)}
        self.assertEqual(facts[1]['overdue_recent'],0)
        self.assertEqual(facts[2]['overdue_recent'],0)
    def test_inactive_student_never_in_suggestions(self):
        c=fixture(); add_task(c,1,3,TODAY,TODAY-timedelta(days=1))
        self.assertNotIn(3,[x['id'] for x in collect_student_facts(c,TODAY)])
    def test_silent_means_no_new_assignment(self):
        c=fixture(); add_task(c,1,1,TODAY-timedelta(days=20),TODAY+timedelta(days=60))
        s=make_suggestions(collect_student_facts(c,TODAY),TODAY)
        osman=next(x for x in s if x['data']['id']==1)
        self.assertIn('Yeni ödev kaydı',osman['title'])
        self.assertIn('çalışmadığı anlamına gelmez',osman['desc'])
    def test_five_tasks_no_bogus_silent(self):
        c=fixture(); add_task(c,1,1,TODAY-timedelta(days=1),TODAY+timedelta(days=7))
        self.assertFalse(any(x['type']=='silent' and x['data']['id']==1 for x in make_suggestions(collect_student_facts(c,TODAY),TODAY)))
    def test_aging_overdue_never_claim_last30(self):
        c=fixture(); add_task(c,1,1,TODAY-timedelta(days=300),TODAY-timedelta(days=289))
        osman=next(x for x in make_suggestions(collect_student_facts(c,TODAY),TODAY) if x['data']['id']==1)
        self.assertIn('Daha eski',osman['desc'])
        self.assertNotIn('Son 30 günde süresi dolan',osman['desc'])
    def test_indicator_bounded(self):
        self.assertEqual(tracking_indicator({'has_assignment_history':True,'overdue_recent':1000}),48)
        self.assertIsNone(tracking_indicator({'has_assignment_history':False,'overdue_recent':1000}))
    def test_students_do_not_leak(self):
        c=fixture();add_task(c,1,1,TODAY,TODAY-timedelta(days=1),'devam','Fizik')
        fact={x['id']:x for x in collect_student_facts(c,TODAY)}
        self.assertEqual(fact[1]['problem_lesson'],'Fizik')
        self.assertIsNone(fact[2]['problem_lesson'])

if __name__=='__main__':unittest.main()
