"""V12: student-isolated, no-write, clock-aware daily follow-up drafts."""
import sqlite3
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.daily_followup_v12 import (
    load_open_homework, assigned_profile, make_followup_draft, draft_text)

NOW = datetime(2026, 10, 12, 8, 30, 0)  # Monday


def profile(**changes):
    x = {'planner_version': 2, 'wake': '07:00', 'sleep': '23:00',
         'advanced_enabled': True,
         'advanced_days': {str(i): {'wake': '07:00', 'bed': '23:00',
                                    'study_start':'17:00', 'study_end':'20:00',
                                    'max': 60} for i in range(7)},
         'school_by_day': {}, 'blocks': [], 'max': 90,
         'session_enabled': True, 'session_minutes': 45,
         'session_break': 15, 'session_split': True, 'empty': 'Yok'}
    x.update(changes)
    return x


def facts(sid=1, tasks=None, review=None):
    return {'student_id':sid, 'student_name':'Öğrenci Test',
            'tasks': tasks or [], 'needs_review': review or []}


def task(tid, mins, due=date(2026,10,9)):
    return {'id':tid,'lesson':'Fizik','topic':'Hareket','book':'Kitap',
            'minutes':mins,'due':due}


class DailyFollowupV12Tests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.con.executescript('''
            CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, aktif INTEGER);
            CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER,
                verilis_tarihi TEXT, bitis_tarihi TEXT);
            CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER,
                ders TEXT, konu_ad TEXT, kitap_ad TEXT, saat_dk INTEGER, durum TEXT);
        ''')
        self.con.executemany('INSERT INTO ogrenci VALUES (?, ?, ?, 1)',
                             [(1, 'Öğrenci', 'Bir'), (2, 'Öğrenci', 'İki')])
        self.con.executemany('INSERT INTO odev_kume VALUES (?, ?, ?, ?)',
            [(10,1,'2026-10-01','2026-10-06'), (20,2,'2026-10-01','2026-10-05'),
             (30,1,'2026-10-09','2026-10-20')])
        self.con.executemany('INSERT INTO odev VALUES (?, ?, ?, ?, ?, ?, ?, ?)',[
            (11,10,1,'Fizik','Hareket','K1',60,'devam'),
            (12,10,1,'Kimya','Asit','K2',30,'tamam'),
            (13,20,2,'Tarih','Geçmiş','K3',99,'devam'),
            (14,30,1,'Fizik','Enerji','K1',70,'devam'),
        ])

    def tearDown(self): self.con.close()

    def _make(self, *, p=None, f=None, at=NOW):
        return make_followup_draft(1, f or facts(tasks=[task(11,60)]),
                                   {'A':p or profile()}, {'1':'A'}, now=at)

    def test_selected_student_only(self):
        f=load_open_homework(self.con,1,today=NOW.date())
        self.assertEqual([x['id'] for x in f['tasks']],[11])
        self.assertNotIn('Tarih',repr(f))
    def test_other_student_only(self):
        f=load_open_homework(self.con,2,today=NOW.date())
        self.assertEqual([x['id'] for x in f['tasks']],[13])
    def test_missing_student_rejected(self):
        with self.assertRaises(ValueError): load_open_homework(self.con,3)
    def test_cross_student_inconsistent_join_rejected(self):
        self.con.execute("INSERT INTO odev VALUES(88,20,1,'Fizik','Sahte','K',40,'devam')")
        f=load_open_homework(self.con,1,today=NOW.date())
        self.assertEqual([x['id'] for x in f['tasks']],[11])
    def test_unknown_duration_flagged_not_guessed(self):
        self.con.execute("INSERT INTO odev VALUES(66,10,1,'Fizik','Ses','K',NULL,'devam')")
        f=load_open_homework(self.con,1,today=NOW.date())
        self.assertEqual(len(f['tasks']),1)
        self.assertEqual(len(f['needs_review']),1)
    def test_missing_due_date_not_assumed_overdue(self):
        self.con.execute("UPDATE odev_kume SET bitis_tarihi=NULL WHERE id=10")
        f=load_open_homework(self.con,1,today=NOW.date())
        self.assertEqual(f['tasks'],[])
        self.assertTrue(f['needs_review'])
    def test_unknown_status_ignored(self):
        self.con.execute("UPDATE odev SET durum='silindi' WHERE id=11")
        f=load_open_homework(self.con,1,today=NOW.date())
        self.assertFalse(f['tasks'])
    def test_missing_profile_fail_closed(self):
        d=make_followup_draft(1,facts(tasks=[task(11,60)]),{'A':profile()}, {},now=NOW)
        self.assertEqual(d['status'],'no_profile')
        self.assertFalse(d['slots'])
    def test_unowned_shared_profile_assign_by_id(self):
        self.assertIsNone(assigned_profile(1, {'A':profile()}, {'2':'A'}))
    def test_owned_by_other_student_fails(self):
        p=profile(_session_advisor_owner='2')
        with self.assertRaises(ValueError): self._make(p=p)
    def test_mismatched_facts_fails(self):
        with self.assertRaises(ValueError): self._make(f=facts(sid=2,tasks=[task(11,60)]))
    def test_valid_slot_on_appropriate_day(self):
        d=self._make()
        self.assertEqual(d['status'],'ready')
        self.assertEqual(sum(x['minutes'] for x in d['slots']),60)
        self.assertEqual(d['slots'][0]['start'],'17:00')
    def test_session_limit(self):
        d=self._make()
        self.assertTrue(all(x['minutes']<=45 for x in d['slots']))
    def test_break_enforced(self):
        d=self._make()
        monday=[x for x in d['slots'] if x['date']=='2026-10-12']
        self.assertEqual(len(monday),2)
        s=sorted(monday,key=lambda x:x['start'])
        def minute(t): return int(t[:2])*60+int(t[3:])
        self.assertGreaterEqual(minute(s[1]['start'])-minute(s[0]['end']),15)
    def test_daily_cap(self):
        d=self._make(f=facts(tasks=[task(11,180)]))
        byday={}
        for s in d['slots']: byday[s['date']]=byday.get(s['date'],0)+s['minutes']
        self.assertTrue(all(v<=60 for v in byday.values()))
    def test_inadequate_capacity_is_explicit(self):
        p=profile(max=0)
        d=self._make(p=p)
        self.assertEqual(d['status'],'no_slots')
        self.assertEqual(d['remaining'][0]['minutes'],60)
    def test_holiday_respected(self):
        p=profile(empty='Pazartesi')
        d=self._make(p=p)
        self.assertNotEqual(d['slots'][0]['date'],'2026-10-12')
    def test_course_block_respected(self):
        p=profile(blocks=['Pazartesi [17:00-19:00] Kurs'])
        d=self._make(p=p)
        self.assertTrue(all(x['start']>='19:00' for x in d['slots'] if x['date']=='2026-10-12'))
    def test_past_slots_omitted(self):
        d=self._make(at=datetime(2026,10,12,19,55))
        self.assertFalse(any(x['date']=='2026-10-12' and x['start']<'19:55' for x in d['slots']))
    def test_no_split_long_task(self):
        p=profile(session_split=False)
        d=self._make(p=p)
        self.assertFalse(d['slots'])
        self.assertEqual(d['remaining'][0]['reason'],'Bölünemez uzun ödev')
    def test_invalid_profile_reports_error(self):
        d=self._make(p=profile(session_minutes=400))
        self.assertEqual(d['status'],'invalid_profile')
    def test_non_existing_tasks_not_invented(self):
        d=self._make(f=facts(tasks=[]))
        self.assertEqual(d['status'],'no_overdue')
        self.assertFalse(d['slots'])
    def test_unassigned_displayed(self):
        d=self._make(p=profile(max=0))
        self.assertIn('YERLEŞMEYEN',draft_text(d))
        self.assertIn('KAYDEDİLMEDİ' if d['slots'] else 'oluşturulamadı',draft_text(d))
    def test_no_db_write(self):
        before=self.con.total_changes
        f=load_open_homework(self.con,1,today=NOW.date())
        make_followup_draft(1,f,{'A':profile()},{'1':'A'},now=NOW)
        self.assertEqual(self.con.total_changes,before)
    def test_no_truncation_silent(self):
        for i in range(251):
            self.con.execute('INSERT INTO odev VALUES (?,10,1,?,?,?,?,?)',
                             (100+i,'Fizik','Hareket','K',30,'devam'))
        with self.assertRaises(ValueError): load_open_homework(self.con,1,today=NOW.date())

if __name__ == '__main__': unittest.main()

class FollowupUIWiringTests(unittest.TestCase):
    def test_plan_button_goes_to_preview_not_message_sender(self):
        code=(Path(__file__).resolve().parents[1]/'ui'/'smart_assistant_dialog.py').read_text(encoding='utf-8')
        self.assertIn("btn_plan.clicked.connect(lambda checked=False, d=data: self.show_followup_draft(d))", code)
    def test_plan_preview_does_not_mutate_homework(self):
        import ast
        code=(Path(__file__).resolve().parents[1]/'ui'/'smart_assistant_dialog.py').read_text(encoding='utf-8')
        tree=ast.parse(code)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SmartAssistantDialog')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='show_followup_draft')
        body=ast.get_source_segment(code,method)
        self.assertNotIn('UPDATE odev',body)
        self.assertNotIn('INSERT INTO odev',body)
        self.assertIn('load_open_homework',body)
        self.assertIn('load_assignments',body)
    def test_silent_form_navigation_still_exists(self):
        code=(Path(__file__).resolve().parents[1]/'ui'/'smart_assistant_dialog.py').read_text(encoding='utf-8')
        self.assertIn('open_homework_for_student',code)
