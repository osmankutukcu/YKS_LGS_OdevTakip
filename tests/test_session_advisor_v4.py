"""No Qt dependency. Tests are isolated from actual student data."""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3, sys, json
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.session_advisor import (record_feedback,recent_feedback,homework_summary,
                                      suggest_session_minutes,personal_profile_update)

class AdvisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'feedback.json'
        self.today = date(2026,10,11)

    def fill(self, sid='123', rating='hard', count=3):
        for i in range(count):
            record_feedback(sid,rating,path=self.path,day=self.today-timedelta(days=i))
        return recent_feedback(sid,path=self.path,today=self.today)

    def test_not_enough_days_does_not_change(self):
        f=self.fill(count=2)
        a=suggest_session_minutes(45,f)
        self.assertFalse(a['ready']);self.assertEqual(a['suggested'],45)

    def test_single_day_repeated_click_counts_one(self):
        record_feedback('1','hard',path=self.path,day=self.today)
        record_feedback('1','easy',path=self.path,day=self.today)
        f=recent_feedback('1',path=self.path,today=self.today)
        self.assertEqual(f,{self.today.isoformat():'easy'})

    def test_zorlanma_reduces_by_ten(self):
        a=suggest_session_minutes(45,self.fill())
        self.assertTrue(a['ready']);self.assertEqual(a['suggested'],35)

    def test_very_short_session_has_floor(self):
        a=suggest_session_minutes(15,self.fill())
        self.assertFalse(a['ready']);self.assertEqual(a['suggested'],15)

    def test_easy_increases_slowly(self):
        a=suggest_session_minutes(90,self.fill(rating='easy'))
        self.assertTrue(a['ready']);self.assertEqual(a['suggested'],95)

    def test_completion_only_never_infers_endurance(self):
        a=suggest_session_minutes(45,{},homework={'available':True,'due':100,'done':100})
        self.assertFalse(a['ready']);self.assertEqual(a['suggested'],45)

    def test_low_completion_blocks_increase(self):
        a=suggest_session_minutes(45,self.fill(rating='easy'),homework={'due':12,'done':4})
        self.assertFalse(a['ready']);self.assertEqual(a['suggested'],45)

    def test_mixed_feedback_not_overconfident(self):
        f=self.fill(rating='easy',count=2)
        record_feedback('123','hard',path=self.path,day=self.today-timedelta(days=3))
        a=suggest_session_minutes(45,recent_feedback('123',path=self.path,today=self.today))
        self.assertFalse(a['ready'])

    def test_no_double_application(self):
        f=self.fill()
        a=suggest_session_minutes(45,f)
        repeat=suggest_session_minutes(35,f,last_applied_signature=a['signature'])
        self.assertFalse(repeat['ready']);self.assertEqual(repeat['suggested'],35)

    def test_isolation_by_student_id(self):
        self.fill('alice')
        self.assertEqual(recent_feedback('bob',path=self.path,today=self.today),{})

    def test_old_feedback_is_not_reused(self):
        record_feedback('1','hard',path=self.path,day=self.today-timedelta(days=60))
        self.assertEqual(recent_feedback('1',path=self.path,today=self.today),{})

    def test_corrupt_feedback_is_never_overwritten(self):
        self.path.write_text('{BROKEN','utf-8')
        with self.assertRaises(json.JSONDecodeError):
            record_feedback('1','hard',path=self.path,day=self.today)
        self.assertEqual(self.path.read_text('utf-8'),'{BROKEN')

    def test_different_student_owns_different_copy(self):
        profiles={'Standart':{'session_minutes':45,'session_enabled':False, 'max':180}}
        sig='a'*64
        p1,n1=personal_profile_update(profiles,'Standart','42',35,sig)
        p2,n2=personal_profile_update(p1,'Standart','43',50,sig)
        self.assertEqual(p2['Standart']['session_minutes'],45)
        self.assertEqual(p2[n1]['session_minutes'],35)
        self.assertEqual(p2[n2]['session_minutes'],50)
        self.assertNotEqual(n1,n2)
        self.assertEqual(profiles,{'Standart':{'session_minutes':45,'session_enabled':False, 'max':180}})

    def test_personal_applied_once_and_new_signal_permitted(self):
        d={'K':{'session_minutes':45}}
        p,name=personal_profile_update(d,'K','42',35,'a'*64)
        with self.assertRaisesRegex(ValueError,'daha önce'):
            personal_profile_update(p,name,'42',25,'a'*64)
        p2,name2=personal_profile_update(p,name,'42',30,'b'*64)
        self.assertEqual(name,name2)
        self.assertEqual(p2[name]['session_minutes'],30)

    def test_no_clobber_manually_changed_personal_via_shared_template(self):
        p,name=personal_profile_update({'K':{'session_minutes':45}},'K','42',35,'a'*64)
        with self.assertRaisesRegex(ValueError,'kişisel profili'):
            personal_profile_update(p,'K','42',50,'b'*64)
        self.assertEqual(p[name]['session_minutes'],35)

    def test_homework_due_read_only(self):
        con=sqlite3.connect(':memory:')
        con.executescript('''CREATE TABLE odev_kume(id INTEGER, bitis_tarihi TEXT);
            CREATE TABLE odev_satir(ogrenci_id INTEGER, kume_id INTEGER, durum TEXT);''')
        old=(self.today-timedelta(days=2)).isoformat()
        future=(self.today+timedelta(days=2)).isoformat()
        con.execute('INSERT INTO odev_kume VALUES (1,?)',(old,))
        con.execute('INSERT INTO odev_kume VALUES (2,?)',(future,))
        con.executemany('INSERT INTO odev_satir VALUES (?,?,?)',[(42,1,'tamamlandı'),(42,1,'devam'),(42,2,'devam'),(43,1,'devam')])
        report=homework_summary(con,'42',today=self.today)
        self.assertEqual((report['due'],report['done']),(2,1))
        self.assertTrue(report['available'])
        self.assertEqual(con.execute('SELECT COUNT(*) FROM odev_satir').fetchone()[0],4)
        con.close()

    def test_missing_tables_gracefully_degrades(self):
        con=sqlite3.connect(':memory:')
        self.assertFalse(homework_summary(con,1)['available'])
        con.close()

    def test_invalid_rating_does_not_create_file(self):
        with self.assertRaises(ValueError):
            record_feedback('1','maybe',path=self.path,day=self.today)
        self.assertFalse(self.path.exists())

if __name__ == '__main__': unittest.main()
