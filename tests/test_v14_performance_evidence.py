"""V14 performance evidence: read-only, precise denominators, safe legacy merges."""
import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path
import ast

from services.performance_evidence_v14 import compute_evidence, MIN_RECOGNITION_SAMPLE

TODAY = date(2026, 10, 12)  # Monday


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, aktif INTEGER);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, bitis_tarihi TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER, durum TEXT, silindi INTEGER, aktarildi INTEGER);
            CREATE TABLE odev_satir(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER, durum TEXT, odev_id INTEGER, silindi INTEGER, aktarildi INTEGER);
            INSERT INTO ogrenci VALUES(1,'Örnek','A',1);
            INSERT INTO ogrenci VALUES(2,'Örnek','B',1);
            INSERT INTO ogrenci VALUES(3,'Pasif','Öğrenci',0);
        ''')

    def tearDown(self):
        self.con.close()

    def group(self, gid, sid=1, due=TODAY):
        self.con.execute('INSERT INTO odev_kume VALUES(?,?,?)',(gid,sid,due.isoformat() if isinstance(due,date) else due))

    def task(self, tid, gid=10, sid=1, status='devam', deleted=0, transferred=0):
        self.con.execute('INSERT INTO odev VALUES(?,?,?,?,?,?)',(tid,gid,sid,status,deleted,transferred))

    def satir(self, rid,gid=10,sid=1,status='devam',odev_id=None):
        self.con.execute('INSERT INTO odev_satir VALUES(?,?,?,?,?,?,?)',(rid,gid,sid,status,odev_id,0,0))

    def get(self, sid=1):
        result = compute_evidence(self.con,TODAY)
        return next(s for s in result.students if s.student_id==sid)

    def test_empty_is_none_not_0_percent(self):
        s=self.get()
        self.assertIsNone(s.week.percent)
        self.assertEqual(s.week.total,0)

    def test_completed_status_yapildi(self):
        self.group(10)
        self.task(1,status='yapildi')
        s=self.get()
        self.assertEqual((s.week.completed,s.week.total,s.week.percent),(1,1,100.0))

    def test_one_task_not_leader_or_club(self):
        self.group(10);self.task(1,status='yapildi')
        e=compute_evidence(self.con,TODAY)
        self.assertEqual(e.top5(),[])
        self.assertEqual(e.club(),[])

    def test_five_tasks_leader(self):
        self.group(10)
        for n in range(5):self.task(n+1,status='yapildi')
        self.assertEqual(len(compute_evidence(self.con,TODAY).top5()),1)
        self.assertEqual(len(compute_evidence(self.con,TODAY).club()),1)

    def test_future_due_does_not_reduce_week(self):
        self.group(10,due=TODAY)
        self.task(1,status='yapildi')
        self.group(11,due=TODAY+timedelta(days=2))
        self.task(2,11,status='devam')
        self.assertEqual(self.get().week.total,1)

    def test_overdue_only_past_due_open(self):
        self.group(10,due=TODAY-timedelta(days=1)); self.task(1)
        self.group(11,due=TODAY); self.task(2,11)
        self.assertEqual(self.get().last30.overdue,1)

    def test_transferred_or_deleted_not_counted(self):
        self.group(10);self.task(1,status='aktarildi');self.task(2,deleted=1);self.task(3,transferred=1)
        s=self.get()
        self.assertEqual(s.week.total,0)
        self.assertEqual(s.excluded_rows,3)

    def test_one_source_core_and_satir_no_double_count(self):
        self.group(10);self.task(1,status='yapildi');self.satir(2,odev_id=1,status='yapildi')
        s=self.get()
        self.assertEqual(s.week.total,1)
        self.assertEqual(s.uncertain_count,1)
        self.assertFalse(compute_evidence(self.con,TODAY).top5())

    def test_fallback_satir_when_no_core(self):
        self.group(10);self.satir(1,status='tamam')
        self.assertEqual(self.get().week.completed,1)

    def test_broken_satir_link_not_guessed(self):
        self.group(10);self.satir(1,status='devam',odev_id=999)
        self.assertEqual(self.get().week.total,1)
        self.assertEqual(self.con.execute('SELECT odev_id FROM odev_satir').fetchone()[0],999)

    def test_student_group_mismatch_skipped(self):
        self.group(10,sid=1);self.task(1,sid=2)
        self.assertEqual(self.get(2).week.total,0)
        self.assertEqual(compute_evidence(self.con,TODAY).skipped,1)

    def test_separate_students(self):
        self.group(10,1); self.task(1,10,1,'yapildi')
        self.group(11,2); self.task(2,11,2,'devam')
        self.assertEqual(self.get(1).week.completed,1)
        self.assertEqual(self.get(2).week.completed,0)

    def test_inactive_hidden(self):
        self.group(10,sid=3);self.task(1,10,3,'yapildi')
        self.assertEqual(len(compute_evidence(self.con,TODAY).students),2)

    def test_undated_not_in_denominator(self):
        self.group(10,due=None);self.task(1)
        self.assertEqual(self.get().week.total,0)
        self.assertEqual(self.get().undated_count,1)

    def test_non_iso_date(self):
        self.group(10,due='12.10.2026');self.task(1,status='tamam')
        self.assertEqual(self.get().week.completed,1)

    def test_unknown_status_not_assumed_done(self):
        self.group(10);self.task(1,status='anlasilmiyor')
        self.assertEqual(self.get().week.total,0)
        self.assertEqual(self.get().uncertain_count,1)

    def test_non_overlapping_previous30(self):
        self.group(10,due=TODAY-timedelta(days=45));self.task(1)
        self.group(11,due=TODAY-timedelta(days=5));self.task(2,11)
        s=self.get()
        self.assertEqual(s.previous30.overdue,1)
        self.assertEqual(s.last30.overdue,1)
        self.assertEqual(compute_evidence(self.con,TODAY).trend(),[])

    def test_database_query_only(self):
        self.group(10);self.task(1)
        self.con.commit()
        self.con.execute('PRAGMA query_only=ON')
        self.assertEqual(self.get().week.total,1)
        self.con.execute('PRAGMA query_only=OFF')
        self.assertEqual(self.con.execute('SELECT count(*) FROM odev').fetchone()[0],1)

    def test_no_daily_cache_needed(self):
        self.assertEqual(len(compute_evidence(self.con,TODAY).students),2)

    def test_omit_incomplete_missing_tables(self):
        self.con.execute('DROP TABLE odev')
        with self.assertRaisesRegex(ValueError,'odev'):compute_evidence(self.con,TODAY)

    def test_older_due_yesterday_not_in_new_week(self):
        self.group(10,due=TODAY-timedelta(days=1));self.task(1)
        self.assertEqual(self.get().week.total,0)
        self.assertEqual(self.get().last30.total,1)

    def test_missing_group_skipped(self):
        self.task(1,gid=12345)
        self.assertEqual(compute_evidence(self.con,TODAY).skipped,1)

    def test_no_mutating_code_in_ui_rebuild(self):
        panel=Path(__file__).resolve().parents[1]/'ui'/'performans_paneli.py'
        text=panel.read_text(encoding='utf-8')
        self.assertNotIn('db.rebuild_performance_current_week(con)',text)
        self.assertNotIn('db.rebuild_performance_last_30_days(con)',text)
        ast.parse(text)
        self.assertIn('self.tabEvidence',text)
        self.assertIn('def _fill_all_students',text)


if __name__ == '__main__':unittest.main()
