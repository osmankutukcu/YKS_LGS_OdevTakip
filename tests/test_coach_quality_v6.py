"""V6 exam-denominator and opt-in source-provenance regression checks."""
import sqlite3
import unittest
from datetime import date
from io import BytesIO
from unittest.mock import Mock

from services.coach_exam_quality_v6 import compare_exam_records
from services.coach_evidence_v5 import build_coach_brief, brief_as_html
from services.coach_official_sources import inspect_source, _is_allowed, MAX_BYTES

TODAY = date(2026, 10, 11)


def new_db():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
    CREATE TABLE ogrenci(id INTEGER PRIMARY KEY,ad TEXT,soyad TEXT,ana_grup TEXT);
    INSERT INTO ogrenci VALUES(1,'Örnek','Öğrenci','11'),(2,'Başka','Öğrenci','11');
    CREATE TABLE denemeler(id INTEGER PRIMARY KEY,tarih TEXT,tur TEXT);
    CREATE TABLE deneme_sonuclari(id INTEGER PRIMARY KEY,deneme_id INTEGER,
       ogrenci_id INTEGER,ders_adi TEXT,net REAL,dogru INTEGER,yanlis INTEGER,bos INTEGER);
    CREATE TABLE odev_kume(id INTEGER PRIMARY KEY,bitis_tarihi TEXT);
    CREATE TABLE odev_satir(id INTEGER PRIMARY KEY,ogrenci_id INTEGER,kume_id INTEGER,
       ders TEXT,konu TEXT,kitap TEXT,durum TEXT,silindi INTEGER DEFAULT 0);
    INSERT INTO odev_kume VALUES(1,'2026-10-30'),(2,'2026-10-01');
    ''')
    return con


def add_exam(con, i, when, kind, net, correct, wrong, blank, *, student=1, subject='Matematik'):
    con.execute('INSERT INTO denemeler VALUES(?,?,?)', (i, when, kind))
    con.execute('INSERT INTO deneme_sonuclari VALUES(?,?,?,?,?,?,?,?)',
                (i, i, student, subject, net, correct, wrong, blank))


class ExamQualityTests(unittest.TestCase):
    def setUp(self):
        self.db = new_db()

    def tearDown(self):
        self.db.close()

    def test_different_exam_types_not_compared(self):
        add_exam(self.db,1,'2026-09-01','TYT',20,25,20,5)
        add_exam(self.db,2,'2026-10-01','AYT',12,15,12,23)
        notes, caveats = compare_exam_records(self.db,1,as_of=TODAY)
        self.assertEqual(notes,[])
        self.assertTrue(any('türü' in c for c in caveats))

    def test_different_question_counts_not_compared(self):
        add_exam(self.db,1,'2026-09-01','TYT',17,21,16,2)
        add_exam(self.db,2,'2026-10-01','TYT',12,16,16,8)
        self.assertEqual(compare_exam_records(self.db,1,as_of=TODAY)[0],[])

    def test_same_question_count_and_type_has_context(self):
        add_exam(self.db,1,'2026-09-01','TYT',12,16,16,8)
        add_exam(self.db,2,'2026-10-01','TYT',15,18,12,10)
        notes, _ = compare_exam_records(self.db,1,as_of=TODAY)
        self.assertEqual(len(notes),1)
        self.assertEqual(notes[0]['question_count'],40)
        self.assertEqual(notes[0]['comparison_quality'],'uyumlu kayıt')

    def test_same_day_is_not_independent_measurement(self):
        add_exam(self.db,1,'2026-10-01','TYT',12,16,16,8)
        add_exam(self.db,2,'2026-10-01','TYT',15,18,12,10)
        self.assertEqual(compare_exam_records(self.db,1,as_of=TODAY)[0],[])

    def test_future_exam_excluded(self):
        add_exam(self.db,1,'2026-09-01','TYT',12,16,16,8)
        add_exam(self.db,2,'2026-11-01','TYT',15,18,12,10)
        self.assertEqual(compare_exam_records(self.db,1,as_of=TODAY)[0],[])

    def test_bad_scores_excluded(self):
        add_exam(self.db,1,'2026-09-01','TYT',float('nan'),16,16,8)
        add_exam(self.db,2,'2026-10-01','TYT',15,18,12,10)
        self.assertEqual(compare_exam_records(self.db,1,as_of=TODAY)[0],[])

    def test_no_cross_student_leakage(self):
        add_exam(self.db,1,'2026-09-01','TYT',12,16,16,8,student=2)
        add_exam(self.db,2,'2026-10-01','TYT',15,18,12,10,student=1)
        self.assertEqual(compare_exam_records(self.db,1,as_of=TODAY)[0],[])

    def test_partial_task_future_not_overdue(self):
        self.db.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,durum) VALUES(1,1,'Fizik','İş','eksik')")
        report = build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(report['stats']['overdue'],0)
        self.assertEqual(report['stats']['needs_review'],1)

    def test_partially_completed_past_due(self):
        self.db.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,durum) VALUES(1,2,'Fizik','İş','eksik')")
        report=build_coach_brief(self.db,1,as_of=TODAY)
        self.assertEqual(report['stats']['overdue'],1)
        self.assertEqual(report['stats']['needs_review'],0)

    def test_html_escapes_exam_subject(self):
        add_exam(self.db,1,'2026-09-01','TYT',20,25,10,5,subject='<img src=x onerror=alert(1)>')
        add_exam(self.db,2,'2026-10-01','TYT',10,15,15,10,subject='<img src=x onerror=alert(1)>')
        html = brief_as_html(build_coach_brief(self.db,1,as_of=TODAY))
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)


class FakeResponse:
    status=200
    headers={'Content-Type':'text/html; charset=utf-8'}
    def __init__(self,data,url):
        self.data=BytesIO(data)
        self.url=url
        self.bytes_read=0
    def geturl(self):return self.url
    def read(self,n):
        self.bytes_read += n
        return self.data.read(n)
    def __enter__(self):return self
    def __exit__(self,*args):return False

class SourceTests(unittest.TestCase):
    def test_allowlist_rejects_evil_ports_credentials(self):
        for u in ['http://tymm.meb.gov.tr/', 'https://tymm.meb.gov.tr.evil.test/',
                  'https://a@tymm.meb.gov.tr/', 'https://tymm.meb.gov.tr:9999/',
                  'https://evil.test/']:
            self.assertFalse(_is_allowed(u))
            with self.assertRaises(ValueError):inspect_source(u)

    def test_metadata_title_bounded_and_provenance(self):
        resp=FakeResponse(b'<html><head><title>Resmi kaynak</title></head></html>',
                          'https://tymm.meb.gov.tr/ogretim-programlari/')
        out=inspect_source(resp.url,opener=Mock(open=lambda req,timeout:resp))
        self.assertTrue(out['content_checked'])
        self.assertEqual(out['title'],'Resmi kaynak')
        self.assertEqual(out['http_status'],200)
        self.assertEqual(resp.bytes_read,MAX_BYTES)
        self.assertNotIn('ogrenci',out)

    def test_redirect_final_host_denied_even_with_mock(self):
        r=FakeResponse(b'<title>Fake</title>','https://evil.test/steal')
        with self.assertRaises(ValueError):
            inspect_source('https://tymm.meb.gov.tr/ogretim-programlari/',opener=Mock(open=lambda req,timeout:r))

    def test_pdf_not_curriculum_verified(self):
        r=FakeResponse(b'%PDF', 'https://tymm.meb.gov.tr/ogretim-programlari/')
        r.headers={'Content-Type':'application/pdf'}
        result=inspect_source(r.url,opener=Mock(open=lambda req,timeout:r))
        self.assertFalse(result['content_checked'])


if __name__=='__main__':unittest.main()

class PrioritizationTests(unittest.TestCase):
    def setUp(self):
        self.db=new_db()
    def tearDown(self):self.db.close()
    def test_overdue_across_subjects(self):
        for i in range(7):
            self.db.execute('INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,durum) VALUES(1,2,?,?,?)',
                            ('Matematik',f'Konu {i}','devam'))
        self.db.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,durum) VALUES(1,2,'Fizik','Enerji','devam')")
        r=build_coach_brief(self.db,1,as_of=TODAY,max_actions=3)
        self.assertEqual(len(r['actions']),3)
        self.assertIn('Fizik',[a['subject'] for a in r['actions']])
        self.assertEqual(r['stats']['overdue'],8)
    def test_zero_actions(self):
        self.db.execute("INSERT INTO odev_satir(ogrenci_id,kume_id,ders,konu,durum) VALUES(1,1,'Fizik','İş','tamam')")
        r=build_coach_brief(self.db,1,as_of=TODAY,max_actions=0)
        self.assertEqual(r['actions'],[])
