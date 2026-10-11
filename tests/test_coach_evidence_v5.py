import sqlite3
import unittest
from datetime import date
from services.coach_evidence_v5 import (build_coach_brief, build_safe_homework_suggestions,
                                       build_profile_weekly_preview, brief_as_html, brief_as_text)
from services.coach_official_sources import check_source, OFFICIAL_SOURCES

TODAY=date(2026,10,11)

def make_db():
    con=sqlite3.connect(':memory:')
    con.row_factory=sqlite3.Row
    con.executescript('''
        CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT, soyad TEXT, ana_grup TEXT);
        CREATE TABLE odev_kume (id INTEGER PRIMARY KEY, bitis_tarihi TEXT);
        CREATE TABLE odev_satir (id INTEGER PRIMARY KEY, ogrenci_id INTEGER, odev_id INTEGER,
            kume_id INTEGER, ders TEXT, konu TEXT, kitap TEXT, durum TEXT, tarih TEXT,
            tamamlanma_tarihi TEXT, silindi INTEGER DEFAULT 0);
        CREATE TABLE odev (id INTEGER PRIMARY KEY, ogrenci_id INTEGER,kume_id INTEGER,
            ders TEXT, konu_ad TEXT, kitap_ad TEXT, durum TEXT,
            verilis_tarihi TEXT, tamamlanma_tarihi TEXT);
        CREATE TABLE denemeler (id INTEGER PRIMARY KEY,tarih TEXT);
        CREATE TABLE deneme_sonuclari (id INTEGER PRIMARY KEY, deneme_id INTEGER,
            ogrenci_id INTEGER,ders_adi TEXT,dogru INTEGER,yanlis INTEGER,net REAL);
        CREATE TABLE koc_konu_takip (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
            ders_adi TEXT,konu_adi TEXT,hakimiyet_puani REAL);
        CREATE TABLE ogrenci_kitap(ogrenci_id INTEGER,ders TEXT,kitap_ad TEXT);
        INSERT INTO ogrenci VALUES (1,'Örnek','Öğrenci','LGS');
        INSERT INTO ogrenci VALUES (2,'Diğer','Öğrenci','LGS');
        INSERT INTO odev_kume VALUES (1, '2026-10-01'),(2,'2026-10-30'),(3,'2026-10-03');
    ''')
    return con

class CoachEvidenceTest(unittest.TestCase):
    def setUp(self): self.db=make_db()
    def tearDown(self): self.db.close()
    def insert(self, student=1, kume=1, course='Matematik', topic='Üslü Sayılar', book='Kaynak A', status='devam',when=None):
        self.db.execute('''INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,kitap,durum,tamamlanma_tarihi)
                           VALUES(?,?,?,?,?,?,?)''',(student,kume,course,topic,book,status,when))
    def test_empty_not_mastery(self):
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['stats']['assigned'],0)
        self.assertIsNone(r['stats']['completion_percent'])
        self.assertTrue(any('akademik eksik' in x for x in r['warnings']))
    def test_distinct_students(self):
        self.insert(student=2)
        self.assertEqual(build_coach_brief(self.db,1,as_of=TODAY)['stats']['assigned'],0)
    def test_due_overdue(self):
        self.insert()
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['stats']['overdue'],1)
        self.assertEqual(r['actions'][0]['kind'],'overdue')
    def test_complete_no_overdue(self):
        self.insert(status='tamam',when='2026-10-01')
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['stats']['overdue'],0)
        self.assertEqual(r['stats']['completed'],1)
    def test_pending_future(self):
        self.insert(kume=2)
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['stats']['pending'],1)
        self.assertEqual(r['stats']['overdue'],0)
    def test_unknown_due_unverified(self):
        self.insert(kume=None)
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['stats']['unverified'],1)
        self.assertEqual(r['stats']['overdue'],0)
    def test_deleted_excluded(self):
        self.insert()
        self.db.execute('UPDATE odev_satir SET silindi=1')
        self.assertEqual(build_coach_brief(self.db,1,as_of=TODAY)['stats']['assigned'],0)
    def test_linked_legacy_mirror(self):
        self.db.execute('INSERT INTO odev VALUES(7,1,1,?,?,?,"devam",NULL,NULL)',('Matematik','Üslü Sayılar','Kaynak A'))
        self.db.execute('''INSERT INTO odev_satir(ogrenci_id,kume_id,odev_id,ders,konu,kitap,durum)
                           VALUES(1,1,7,'Matematik','Üslü Sayılar','Kaynak A','devam')''')
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['stats']['assigned'],1)
        self.assertEqual(r['sources']['mirrored'],1)
    def test_same_topic_different_cohorts(self):
        self.insert(kume=1);self.insert(kume=3)
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['stats']['assigned'],2)
    def test_only_student_exams(self):
        self.db.executescript('''
        INSERT INTO denemeler VALUES(1,'2026-09-10'),(2,'2026-10-10');
        INSERT INTO deneme_sonuclari VALUES (1,1,1,'Matematik',10,5,8.75);
        INSERT INTO deneme_sonuclari VALUES (2,2,1,'Matematik',8,5,6.75);
        INSERT INTO deneme_sonuclari VALUES (3,2,2,'Matematik',0,10,-2.5);
        ''')
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(len(r['exam_notes']),1)
        self.assertEqual(r['exam_notes'][0]['latest_net'],6.75)
        self.assertEqual(r['actions'][0]['kind'],'exam_follow_up')
    def test_no_available_book_no_recommendation(self):
        self.insert(status='tamam',when='2026-10-01')
        self.assertEqual(build_safe_homework_suggestions(self.db,1,as_of=TODAY),[])
    def test_verified_book_repetition(self):
        self.insert(status='tamam',when='2026-10-01')
        v=build_safe_homework_suggestions(self.db,1,as_of=TODAY,available_books={'Matematik':['Kaynak A']})
        self.assertEqual(len(v),1)
        self.assertFalse(v[0]['auto_selected'])
        self.assertEqual(v[0]['type'],'ebbinghaus')
    def test_same_topic_open_no_duplicate(self):
        self.insert(status='tamam',when='2026-10-01')
        self.insert(kume=2)
        v=build_safe_homework_suggestions(self.db,1,as_of=TODAY,available_books={'Matematik':['Kaynak A']})
        self.assertEqual(v,[])
    def test_total_strict_duration(self):
        for i in range(6):self.insert(course='Matematik',topic=f'Konu {i}',status='tamam',when='2026-10-01')
        v=build_safe_homework_suggestions(self.db,1,as_of=TODAY,target_minutes=52,
                                         available_books={'Matematik':['Kaynak A']})
        self.assertLessEqual(sum(x['dk'] for x in v),52)
        self.assertLessEqual(len(v),2)
    def test_recent_completed_not_due(self):
        self.insert(status='tamam',when='2026-10-10')
        v=build_safe_homework_suggestions(self.db,1,as_of=TODAY,available_books={'Matematik':['Kaynak A']})
        self.assertEqual(v,[])
    def test_no_hardcoded_unseen_gap(self):
        self.insert(status='tamam',when='2026-10-01')
        self.assertTrue(all(x['type']!='curriculum' for x in build_safe_homework_suggestions(self.db,1,as_of=TODAY,
                          available_books={'Matematik':['Kaynak A']})))
    def test_mastery_manual_verified(self):
        self.insert(status='tamam',when='2026-10-01')
        self.db.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi,konu_adi,hakimiyet_puani) VALUES(1,'Matematik','Üslü Sayılar',40)")
        v=build_safe_homework_suggestions(self.db,1,as_of=TODAY,mode='remedial',available_books={'Matematik':['Kaynak A']})
        self.assertEqual(len(v),1)
        self.assertEqual(v[0]['type'],'remedial')
    def test_mastery_no_book_matching_topic(self):
        self.db.execute("INSERT INTO koc_konu_takip(ogrenci_id,ders_adi,konu_adi,hakimiyet_puani) VALUES(1,'Matematik','Başka Konu',40)")
        self.assertEqual(build_safe_homework_suggestions(self.db,1,as_of=TODAY,
                    mode='remedial',available_books={'Matematik':['Kaynak A']}),[])
    def test_html_escape(self):
        self.db.execute("UPDATE ogrenci SET ad='<script>alert(1)</script>' WHERE id=1")
        html=brief_as_html(build_coach_brief(self.db,1,as_of=TODAY))
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;',html)
    def test_text_report(self):
        self.assertIn('VERİ SINIRLARI',brief_as_text(build_coach_brief(self.db,1,as_of=TODAY)))
    def test_online_allowlist(self):
        with self.assertRaises(ValueError):check_source('https://evil.example.test/a')
        self.assertTrue(all(x['url'].startswith('https://') for x in OFFICIAL_SOURCES))
    def test_sql_read_only(self):
        self.insert()
        before=self.db.total_changes
        build_coach_brief(self.db,1,as_of=TODAY)
        build_safe_homework_suggestions(self.db,1,as_of=TODAY,available_books={})
        self.assertEqual(self.db.total_changes,before)
    def test_weekly_profile_rest_day(self):
        self.insert(status='tamam', when='2026-10-01')
        profile={'wake':'08:00','sleep':'22:00','max':90,'empty':'Pazar','school_by_day':{},
                 'session_enabled':True,'session_minutes':45,'session_break':10}
        r=build_profile_weekly_preview(self.db,1,profile,{'Matematik':['Kaynak A']},as_of=TODAY)
        self.assertEqual(r['schedule'][0]['available_minutes'],0)
        self.assertEqual(sum(d['planned_minutes'] for d in r['schedule']),25)
    def test_weekly_one_task_once(self):
        self.insert(status='tamam', when='2026-10-01')
        profile={'wake':'08:00','sleep':'22:00','max':90,'school_by_day':{}}
        r=build_profile_weekly_preview(self.db,1,profile,{'Matematik':['Kaynak A']},as_of=TODAY)
        self.assertEqual(sum(d['planned_minutes'] for d in r['schedule']),25)
        self.assertEqual(len(r['leftovers']),0)
    def test_weekly_zero_capacity_undelivered(self):
        self.insert(status='tamam', when='2026-10-01')
        profile={'wake':'08:00','sleep':'22:00','max':0,'school_by_day':{}}
        r=build_profile_weekly_preview(self.db,1,profile,{'Matematik':['Kaynak A']},as_of=TODAY)
        self.assertEqual(sum(d['planned_minutes'] for d in r['schedule']),0)
        # With zero cap no new review tasks are proposed, no silent omission.
        self.assertEqual(r['total_candidates'],0)
    def test_weekly_no_double_book(self):
        for n in range(2):self.insert(topic=f'Konu {n}',status='tamam',when='2026-10-01')
        profile={'wake':'08:00','sleep':'09:30','max':60,'school_by_day':{},
                 'session_enabled':True,'session_minutes':15,'session_break':10,'session_split':True}
        r=build_profile_weekly_preview(self.db,1,profile,{'Matematik':['Kaynak A']},as_of=TODAY)
        for d in r['schedule']:
            slots = [(x['start'],x['end']) for x in d['items']]
            self.assertEqual(len(slots),len(set(slots)))
            self.assertLessEqual(d['planned_minutes'],d['available_minutes'])
    def test_weekly_school_after_preferred(self):
        self.insert(status='tamam',when='2026-10-01')
        profile={'wake':'07:00','sleep':'22:00','max':90,
                 'school_by_day':{'0':['08:00','15:00']},'after_school_buffer':30}
        r=build_profile_weekly_preview(self.db,1,profile,{'Matematik':['Kaynak A']},as_of=date(2026,10,12))
        self.assertEqual(r['schedule'][0]['items'][0]['start'],'15:30')
    def test_weekly_session_split_disabled(self):
        self.insert(status='tamam',when='2026-10-01')
        profile={'wake':'08:00','sleep':'22:00','max':120,'school_by_day':{},
                 'session_enabled':True,'session_minutes':15,'session_break':10,'session_split':False}
        r=build_profile_weekly_preview(self.db,1,profile,{'Matematik':['Kaynak A']},as_of=TODAY)
        self.assertEqual(len(r['leftovers']),1)
        self.assertEqual(sum(d['planned_minutes'] for d in r['schedule']),0)
    def test_future_exam_data_not_used(self):
        self.db.executescript("\n            INSERT INTO denemeler VALUES(1,'2026-10-12'),(2,'2026-10-13');\n            INSERT INTO deneme_sonuclari VALUES(1,1,1,'Matematik',5,5,3.75);\n            INSERT INTO deneme_sonuclari VALUES(2,2,1,'Matematik',6,5,4.75);\n")
        r=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(r['exam_notes'],[])
    def test_old_schema(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.executescript('CREATE TABLE ogrenci(id INTEGER,ad TEXT,soyad TEXT,ana_grup TEXT); INSERT INTO ogrenci VALUES(1,"A","B","LGS");'
                        'CREATE TABLE odev_satir(id INTEGER,ogrenci_id INTEGER,ders TEXT,konu TEXT,kitap TEXT,durum TEXT);'
                        'INSERT INTO odev_satir VALUES(1,1,"Fen","Madde","Kitap 1","tamam");')
        self.assertEqual(build_coach_brief(db,1,as_of=TODAY)['stats']['completed'],1)
        db.close()

if __name__ == '__main__':unittest.main()
