# -*- coding: utf-8 -*-
"""V3.5.45: fourth independent mobile PDF option, no protected-core mutation."""
import datetime as dt
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlsplit, parse_qs
import fitz
from services.smart_mobile_pdf_v3545 import (
    render_smart_pocket_pdf, build_pocket_snapshot, calendar_meeting_url,
)

DAYS=['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
WEEK=[((dt.date(2026,10,19)+dt.timedelta(days=i)).isoformat(),day) for i,day in enumerate(DAYS)]

def ev(oid,name,typ='Teslim',phone='05551234567',lines=None):
    return {'oid':oid,'ad':name,'tip':typ,'saat':'18:00',
            'tel_ogr':phone,'tel_veli':'05321112233',
            'meta':{'lines':lines if lines is not None else ['Fizik - Hareket'],
                    'status':'normal'}}

def export(sched, target):
    return render_smart_pocket_pdf(target,sched,WEEK,
            student_message=lambda e,*x:'Merhaba '+e['ad']+'\n'+'\n'.join(e['meta'].get('lines',[])),
            parent_message=lambda e,*x:'Sayın veli '+e['ad'])

class SmartPDFTests(unittest.TestCase):
    def test_separate_mobile_pdf_actions_and_navigation(self):
        sched={day:[] for day in DAYS}
        sched['Pazartesi']=[ev(1,'Ayşe Yılmaz')]
        sched['Salı']=[ev(2,'Ali Karaca','Görüşme')]
        with TemporaryDirectory() as t:
            pdf=Path(t)/'new.pdf'
            result=export(sched,pdf)
            with fitz.open(pdf) as doc:
                uris=[ln['uri'] for page in doc for ln in page.get_links() if ln.get('uri')]
                goto=sum(ln['kind']==fitz.LINK_GOTO for page in doc for ln in page.get_links())
                text='\n'.join(p.get_text() for p in doc)
                self.assertIn('AKILLI MOBİL PDF ASİSTANI',text)
                self.assertIn('ÖĞRENCİ HIZLI ERİŞİM',text)
                self.assertIn('Ayşe Yılmaz',text)
                self.assertTrue(any(x.startswith('https://wa.me/') for x in uris))
                self.assertTrue(any(x.startswith('tel:+') for x in uris))
                self.assertTrue(any(x.startswith('https://calendar.google.com/') for x in uris))
                self.assertEqual(len(uris),result['external_links'])
                self.assertGreaterEqual(goto,7+2)

    def test_same_name_distinct_id_preserves_separate_index(self):
        sched={day:[] for day in DAYS}
        sched['Pazartesi']=[ev(11,'Deniz Yılmaz'),ev(22,'Deniz Yılmaz',phone='05321119999')]
        s=build_pocket_snapshot(sched,WEEK)
        self.assertEqual(s['student_count'],2)
        self.assertEqual(len(set(x['key'] for x in s['students'])),2)
        self.assertIn('No 11', '\n'.join(x['display_name'] for x in s['students']))
        with TemporaryDirectory() as td:
            path=Path(td)/'a.pdf'; export(sched,path)
            with fitz.open(path) as doc:
                all_text='\n'.join(p.get_text() for p in doc)
                self.assertIn('No 11',all_text)
                self.assertIn('No 22',all_text)

    def test_conflicting_contact_is_not_linked_to_wrong_recipient(self):
        sched={day:[] for day in DAYS}
        sched['Pazartesi']=[ev(11,'Ayşe',phone='05551234567')]
        sched['Salı']=[ev(11,'Ayşe',phone='05329998877')]
        s=build_pocket_snapshot(sched,WEEK)
        self.assertEqual(s['student_count'],1)
        self.assertTrue(s['students'][0]['contact_conflict'])
        with TemporaryDirectory() as t:
            target=Path(t)/'a.pdf'; export(sched,target)
            with fitz.open(target) as doc:
                all_links=[x['uri'] for p in doc for x in p.get_links() if x.get('uri')]
                self.assertFalse(any(x.startswith('https://wa.me/') or x.startswith('tel:') for x in all_links))

    def test_calendar_never_contains_student_pii(self):
        url=calendar_meeting_url('2026-10-20','15:30')
        self.assertTrue(url.startswith('https://calendar.google.com/'))
        self.assertEqual(parse_qs(urlsplit(url).query)['text'],['Koçluk görüşmesi'])
        self.assertIsNone(calendar_meeting_url('2026-10-20','??:??'))
        self.assertIsNone(calendar_meeting_url('2026-10-20','88:88'))

    def test_many_students_long_tasks_no_truncation(self):
        sched={day:[] for day in DAYS}
        for i in range(85):
            sched[DAYS[i%7]].append(ev(i+1,f'Öğrenci {i+1:03d}',phone='',lines=['Fizik - Hareket']*20))
        with TemporaryDirectory() as t:
            target=Path(t)/'a.pdf'; result=export(sched,target)
            with fitz.open(target) as doc:
                text='\n'.join(pg.get_text() for pg in doc)
                self.assertEqual(result['students'],85)
                self.assertIn('Öğrenci 085',text)
                self.assertGreater(len(doc),20)

    def test_missing_student_id_keeps_separate_entries(self):
        sched={day:[] for day in DAYS}
        sched['Pazartesi']=[ev(None,'Adı Aynı'),ev(None,'Adı Aynı')]
        s=build_pocket_snapshot(sched,WEEK)
        self.assertEqual(s['student_count'],2)
        self.assertTrue(all('Kimlik doğrulanmadı' in x['display_name'] for x in s['students']))

    def test_source_schedule_unchanged_by_snapshot(self):
        sched={day:[] for day in DAYS}
        sched['Pazartesi']=[ev(1,'Ayşe')]
        import copy
        original=copy.deepcopy(sched)
        build_pocket_snapshot(sched,WEEK)
        self.assertEqual(sched,original)

if __name__=='__main__':unittest.main()
