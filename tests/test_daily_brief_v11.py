"""V11 Günün Akıllı Özeti: teacher brief, review & data isolation."""
import sqlite3
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.daily_brief_v11 import (
    ensure_review_table, set_reviewed, load_reviewed, daily_brief,
    review_identity, brief_stats,
)
from services.daily_coach_v10 import collect_student_facts, make_suggestions

TODAY = date(2026, 10, 11)


def suggestion(sid, kind='overdue', recent=0, old=0, completed=0, history=True,
               elapsed=2, last='2026-10-10'):
    return {
        'type':kind, 'title':f'{sid}-{kind}', 'priority':1,
        'data':{'id':sid, 'ad':f'Test {sid}', 'soyad':'Kisi', 'veli_tel1':'12345',
            'has_assignment_history':history,'overdue_recent':recent,'overdue_old':old,
            'completed_in_recent_set':completed,'days_since_assigned':elapsed,
            'last_assignment_date':last,'problem_lesson':'Matematik',
            'problem_count':recent+old},
    }


class DailyBriefV11Tests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        ensure_review_table(self.db)

    def tearDown(self):
        self.db.close()

    def test_review_table_idempotent(self):
        ensure_review_table(self.db)
        ensure_review_table(self.db)

    def test_no_student_identity_ignored(self):
        self.assertIsNone(review_identity({'type':'overdue','data':{'id':None}}))

    def test_error_never_reviewable(self):
        self.assertIsNone(review_identity(suggestion(1,'error',recent=10)))

    def test_fingerprint_contains_no_phone_or_name(self):
        a=suggestion(1,recent=3)
        signature=review_identity(a)[2]
        self.assertNotIn('12345', signature)
        a['data']['ad']='Different'
        a['data']['veli_tel1']='PRIVATE'
        self.assertEqual(review_identity(a)[2], signature)

    def test_review_insert_and_reload(self):
        a=suggestion(1,recent=1)
        self.assertTrue(set_reviewed(self.db,a,True,TODAY))
        self.db.commit()
        self.assertIn(review_identity(a),load_reviewed(self.db,TODAY))

    def test_repeated_review_is_idempotent(self):
        a=suggestion(1,recent=1)
        for _ in range(3): set_reviewed(self.db,a,True,TODAY)
        self.assertEqual(self.db.execute('select count(*) from coach_brief_review_v11').fetchone()[0],1)

    def test_review_undo(self):
        a=suggestion(1,recent=1)
        set_reviewed(self.db,a,True,TODAY)
        set_reviewed(self.db,a,False,TODAY)
        self.assertNotIn(review_identity(a),load_reviewed(self.db,TODAY))

    def test_review_is_day_scoped(self):
        a=suggestion(1,recent=1)
        set_reviewed(self.db,a,True,TODAY)
        self.assertFalse(load_reviewed(self.db,TODAY+timedelta(days=1)))

    def test_changed_evidence_reopens_review(self):
        a=suggestion(1,recent=1)
        set_reviewed(self.db,a,True,TODAY)
        b=suggestion(1,recent=2)
        self.assertNotEqual(review_identity(a), review_identity(b))
        self.assertEqual(daily_brief([b],load_reviewed(self.db,TODAY)),[b])

    def test_same_overdue_count_but_different_assignment_reopens(self):
        a=suggestion(1,recent=1)
        a['data']['overdue_refs']=['17:2026-10-08']
        b=suggestion(1,recent=1)
        b['data']['overdue_refs']=['42:2026-10-08']
        set_reviewed(self.db,a,True,TODAY)
        self.assertNotEqual(review_identity(a),review_identity(b))
        self.assertEqual(daily_brief([b],load_reviewed(self.db,TODAY)),[b])

    def test_unknown_history_not_top5(self):
        arr=[suggestion(i,'silent',history=False,elapsed=999) for i in range(1,20)]
        self.assertEqual(daily_brief(arr),[])
        self.assertEqual(brief_stats(arr)['no_history_count'],19)

    def test_recent_overdue_first(self):
        arr=[suggestion(1,'silent',history=True,elapsed=30),suggestion(2,'overdue',old=17),
             suggestion(3,'overdue',recent=2),suggestion(4,'birthday')]
        got=daily_brief(arr)
        self.assertEqual([v['data']['id'] for v in got],[3,4,2,1])

    def test_more_recent_overdue_sorted_first(self):
        arr=[suggestion(1,recent=1), suggestion(2,recent=7), suggestion(3,recent=4)]
        self.assertEqual([v['data']['id'] for v in daily_brief(arr)],[2,3,1])

    def test_limit_five(self):
        self.assertEqual(len(daily_brief([suggestion(i,recent=i) for i in range(1,30)])),5)

    def test_respects_small_limit(self):
        self.assertEqual(len(daily_brief([suggestion(i,recent=3) for i in range(1,4)], limit=2)),2)
        self.assertEqual(daily_brief([suggestion(1,recent=3)], limit=0),[])

    def test_student_diversity(self):
        arr=[suggestion(1,recent=5),suggestion(1,'birthday'),suggestion(2,'star',completed=8)]
        self.assertEqual([v['data']['id'] for v in daily_brief(arr)],[1,2])

    def test_silent_without_records_absent_even_when_many(self):
        arr=[suggestion(99,'silent',history=False,elapsed=999),suggestion(1,recent=1)]
        self.assertEqual([v['data']['id'] for v in daily_brief(arr)],[1])

    def test_reviewed_filter_only_when_marked(self):
        arr=[suggestion(1,recent=5),suggestion(2,recent=2)]
        set_reviewed(self.db,arr[0],True,TODAY)
        out=daily_brief(arr,load_reviewed(self.db,TODAY))
        self.assertEqual(out,[arr[1]])
        self.assertEqual(brief_stats(arr,load_reviewed(self.db,TODAY))['reviewed_count'],1)

    def test_filter_no_automatic_homework_mutation(self):
        self.db.executescript('CREATE TABLE odev(id INTEGER PRIMARY KEY, durum TEXT);INSERT INTO odev VALUES(1,"devam");')
        arr=[suggestion(1,recent=1)]
        set_reviewed(self.db,arr[0],True,TODAY)
        self.assertEqual(self.db.execute('SELECT durum FROM odev WHERE id=1').fetchone()[0],'devam')

    def test_no_insert_for_invalid_review(self):
        self.assertFalse(set_reviewed(self.db,{'type':'error','data':{}},True,TODAY))
        self.assertEqual(self.db.execute('select count(*) from coach_brief_review_v11').fetchone()[0],0)

    def test_conflict_across_students(self):
        a=suggestion(1,recent=3)
        b=suggestion(2,recent=3)
        set_reviewed(self.db,a,True,TODAY)
        self.assertEqual(daily_brief([a,b],load_reviewed(self.db,TODAY)),[b])

    def test_review_not_permanent_next_day(self):
        a=suggestion(1,recent=3)
        set_reviewed(self.db,a,True,TODAY)
        self.assertEqual(daily_brief([a],load_reviewed(self.db,TODAY+timedelta(days=1))),[a])

    def test_overdue_no_evidence_not_priority(self):
        self.assertEqual(daily_brief([suggestion(1,'overdue',recent=0,old=0)]),[])

    def test_integration_with_daily_coach_v10(self):
        con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
        con.executescript('''
          CREATE TABLE ogrenci(id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, dogum_tarihi TEXT, veli_tel1 TEXT, aktif INTEGER);
          CREATE TABLE odev_kume(id INTEGER PRIMARY KEY, ogrenci_id INTEGER, verilis_tarihi TEXT, bitis_tarihi TEXT);
          CREATE TABLE odev(id INTEGER PRIMARY KEY, kume_id INTEGER, ogrenci_id INTEGER, ders TEXT, durum TEXT);
          INSERT INTO ogrenci VALUES(1,'Bir','Ogrenci',NULL,NULL,1);
          INSERT INTO ogrenci VALUES(2,'Iki','Ogrenci',NULL,NULL,1);
          INSERT INTO odev_kume VALUES(1,1,'2026-10-01','2026-10-09');
          INSERT INTO odev VALUES(1,1,1,'Fizik','devam');
        ''')
        evidence=collect_student_facts(con,TODAY)
        sug=make_suggestions(evidence,TODAY)
        self.assertEqual([x['data']['id'] for x in daily_brief(sug)],[1])
        self.assertEqual(len(sug),2)
        con.close()

class BriefUIWiringTests(unittest.TestCase):
    def test_ui_v11_contract_in_source(self):
        s=(Path(__file__).parents[1]/'ui'/'smart_assistant_dialog.py').read_text()
        self.assertIn('self.active_filter = "priority"',s)
        self.assertIn('self._set_card_reviewed',s)
        self.assertIn('load_reviewed(con)',s)
        self.assertIn('set_reviewed(con, data, reviewed)',s)
        self.assertIn('"↶ Geri Al" if was_reviewed else "✓ İnceledim"',s)
        self.assertIn('self._reviewed_today',s)
        self.assertIn('elif self.active_filter == "all":',s)
        self.assertIn('("risk", "⚠️ Riskler")',s)

if __name__=='__main__': unittest.main()

# Kept as a separate contract guard because GUI tests require PyQt6.
class GUIRegressionContractTests(unittest.TestCase):
    def test_error_not_hidden_by_priority_filter(self):
        s=(Path(__file__).parents[1]/'ui'/'smart_assistant_dialog.py').read_text()
        self.assertIn('if errors:\n            filtered = errors',s)
    def test_dialog_stops_queue_timers_on_close(self):
        s=(Path(__file__).parents[1]/'ui'/'smart_assistant_dialog.py').read_text()
        self.assertIn('def done(self, result):',s)
        self.assertIn('timer.stop()',s)
        self.assertIn('conn.close()',s)
    def test_whatsapp_queue_claim_is_atomic(self):
        s=(Path(__file__).parents[1]/'ui'/'smart_assistant_dialog.py').read_text()
        self.assertIn('if claim.rowcount != 1:',s)
