import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.today_priority_v4 import read_today_priority
from services.daily_coach_v10 import collect_student_facts, make_suggestions
from services.daily_brief_v11 import ensure_review_table, set_reviewed

TODAY = date(2026, 10, 15)

class TodayPriorityV4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'Öğrenci test.db'
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT,
                                 dogum_tarihi TEXT, veli_tel1 TEXT, aktif INTEGER);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
                                   verilis_tarihi TEXT, bitis_tarihi TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY,kume_id INTEGER,ogrenci_id INTEGER,
                              ders TEXT,durum TEXT);
            INSERT INTO ogrenci VALUES(1,'Ayşe','Bir',NULL,'11111',1);
            INSERT INTO ogrenci VALUES(2,'Mert','İki',NULL,'22222',1);
            INSERT INTO ogrenci VALUES(3,'Pasif','Üç',NULL,'33333',0);
            INSERT INTO odev_kume VALUES(101,1,'2026-10-01','2026-10-10');
            INSERT INTO odev VALUES(101,101,1,'Matematik','devam');
            INSERT INTO odev_kume VALUES(102,2,'2026-10-01','2026-10-09');
            INSERT INTO odev VALUES(102,102,1,'Matematik','devam');
            INSERT INTO odev_kume VALUES(103,3,'2026-10-01','2026-10-09');
            INSERT INTO odev VALUES(103,103,3,'Fizik','devam');
        ''')
        c.commit();c.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_readonly_priority_without_review_table(self):
        report = read_today_priority(self.path,today=TODAY)
        self.assertEqual(report['priority_count'], 1)
        self.assertEqual(report['first']['student_id'],1)
        self.assertNotIn('11111',str(report))
        self.assertNotIn('Mert',str(report))
        self.assertEqual(report['source'],'local_sqlite_v10_v11')
        c=sqlite3.connect(self.path)
        self.assertFalse(c.execute("SELECT name FROM sqlite_master WHERE name='coach_brief_review_v11'").fetchone())
        c.close()

    def test_reviewed_item_does_not_reappear_until_evidence_changes(self):
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row
        ensure_review_table(c)
        a=next(s for s in make_suggestions(collect_student_facts(c,TODAY),TODAY)
               if s['type']=='overdue' and s['data']['id']==1)
        set_reviewed(c,a,True,TODAY);c.commit();c.close()
        self.assertEqual(read_today_priority(self.path,today=TODAY)['priority_count'],0)
        c=sqlite3.connect(self.path)
        c.execute("INSERT INTO odev_kume VALUES(104,1,'2026-10-05','2026-10-12')")
        c.execute("INSERT INTO odev VALUES(104,104,1,'Fizik','devam')")
        c.commit();c.close()
        self.assertEqual(read_today_priority(self.path,today=TODAY)['priority_count'],1)

    def test_missing_database_cannot_be_created(self):
        with self.assertRaises(sqlite3.OperationalError):
            read_today_priority(Path(self.tmp.name)/'missing.db',today=TODAY)
        self.assertFalse((Path(self.tmp.name)/'missing.db').exists())

    def test_same_read_has_no_side_effects(self):
        c=sqlite3.connect(self.path)
        before=c.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall()
        c.close()
        read_today_priority(self.path,today=TODAY)
        c=sqlite3.connect(self.path)
        after=c.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall()
        self.assertEqual(before,after)
        c.close()

if __name__ == '__main__': unittest.main()
