# -*- coding: utf-8 -*-
"""Offline academic teacher pocket PDF: synthetic only, no external sends."""
from __future__ import annotations

from datetime import datetime, date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, parse_qs
from copy import deepcopy
import sqlite3
import hashlib
import unittest
import fitz

from services.smart_mobile_pdf_v3545 import render_smart_pocket_pdf, build_pocket_snapshot
from services.offline_pdf_message_center_v3549 import prepare_offline_message_pack
from services.mobile_pdf_schedule_range_v3549 import fetch_mobile_pdf_schedule_range

DAY0=date(2026,10,19)
LABELS=['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
DAYS=[((DAY0+timedelta(days=i)).isoformat(), LABELS[i]) for i in range(7)]


def event(sid=1, name='Örnek Öğrenci', number='+999123456789', typ='Teslim',
          details=None, parent='+999123456788'):
    return {'oid':sid,'ad':name,'tel_ogr':number,'tel_veli':parent,
            'tip':typ, 'saat':'16:30','meta':{'lines':list(details or ['Fizik - Hareket']),
                                          'notes':['ÖZEL ÖĞRETMEN NOTU!'],
                                          'status':'normal'}}


def render(schedule, days=DAYS, academic_context=None):
    temp=TemporaryDirectory()
    output=Path(temp.name)/'pocket.pdf'
    result=render_smart_pocket_pdf(output, schedule, days,
                    academic_context=academic_context,
                    student_message=lambda ev,*x:'ESKİ GÜNLÜK MESAJ '+ev['ad'],
                    parent_message=lambda ev,*x:'ESKİ VELİ MESAJI '+ev['ad'])
    return temp,output,result


class V3549OfflinePackTests(unittest.TestCase):
    def test_separate_student_parent_and_distinct_messages(self):
        e1=event(details=['Fizik - Hareket','Matematik - Polinomlar'])
        e2=event(typ='Görüşme')
        snap=build_pocket_snapshot({'Pazartesi':[e1],'Salı':[e2],**{d:[] for d in LABELS[2:]}},DAYS)
        card={'verified':True,'contact_allowed':True,
              'homework':{'total':6,'completed':2,'overdue':1}}
        pack=prepare_offline_message_pack(snap['students'][0],card,
                                          generated_on=datetime(2026,10,19,12,0))
        self.assertEqual(len(pack),10)
        self.assertIn('Fizik - Hareket',pack[('student','homework')])
        self.assertIn('Matematik - Polinomlar',pack[('parent','followup')])
        self.assertIn('16:30',pack[('parent','meeting')])
        self.assertIn('6',pack[('student','analysis')])
        self.assertNotIn('ÖZEL ÖĞRETMEN NOTU',str(pack))
        self.assertIn('19.10.2026',pack[('student','homework')])
        self.assertIn('Göndermeden önce güncelliğini kontrol',pack[('parent','homework')])
        self.assertTrue(pack[('student','homework')].startswith('Merhaba'))
        self.assertTrue(pack[('parent','homework')].startswith('Sayın Velimiz'))

    def test_no_unverified_analysis_or_invented_meeting(self):
        snap=build_pocket_snapshot({'Pazartesi':[event()], **{d:[] for d in LABELS[1:]}},DAYS)
        p=prepare_offline_message_pack(snap['students'][0],{'verified':False,'contact_allowed':True})
        self.assertNotIn(('student','analysis'),p)
        self.assertNotIn(('parent','meeting'),p)
        self.assertIn(('parent','homework'),p)

    def test_full_pdf_link_integrity_and_no_cross_student_leak(self):
        schedule={d:[] for d in LABELS}
        schedule['Pazartesi']=[event(sid=101,name='Deniz Tek',number='+999123456789',parent='+999123456786'),
                                event(sid=102,name='Deniz Tek',number='+999123456788',parent='+999123456787')]
        context={'student_cards':{
            '101':{'verified':True,'contact_allowed':True,'homework':{'total':3,'completed':1,'overdue':1}},
            '102':{'verified':True,'contact_allowed':False,'homework':{'total':5,'completed':1,'overdue':4}}},
            'source_state':'PARTIAL','student_count':2,'verified_count':2}
        before=deepcopy(schedule)
        tmp,pdf,ret=render(schedule,academic_context=context)
        self.addCleanup(tmp.cleanup)
        self.assertEqual(schedule,before)
        with fitz.open(pdf) as doc:
            uris=[l['uri'] for p in doc for l in p.get_links() if l.get('uri')]
            text='\n'.join(p.get_text() for p in doc)
            self.assertIn('DÖNEMLİK MOBİL MESAJ MERKEZİ',text)
            self.assertIn('Ödevleri Gönder',text)
            self.assertIn('Dönemlik Takip',text)
            self.assertTrue(any('/999123456789?' in u for u in uris))
            self.assertFalse(any('/999123456788?' in u or '/999123456787?' in u for u in uris))
            self.assertEqual(ret['external_links'],len(uris))
            msgs=[parse_qs(urlsplit(u).query).get('text',[''])[0] for u in uris if u.startswith('https://wa.me/')]
            self.assertTrue(any('Fizik - Hareket' in m for m in msgs))
            self.assertTrue(any('3' in m for m in msgs))
            self.assertFalse(any('Kayıtlı ödev: 5;' in m for m in msgs))

    def test_split_long_whatsapp_keeps_every_source_line(self):
        lines=[f'Matematik - Soru {i:03d} - ÖzelKonu{i}' for i in range(130)]
        schedule={d:[] for d in LABELS}
        schedule['Pazartesi']=[event(details=lines)]
        ctx={'source_state':'LOCAL_VERIFIED','student_count':1,'verified_count':1,
             'student_cards':{'1':{'verified':True,'contact_allowed':True,
                                      'homework':{'total':130,'completed':0,'overdue':0}}}}
        tmp,pdf,_=render(schedule,academic_context=ctx)
        self.addCleanup(tmp.cleanup)
        with fitz.open(pdf) as doc:
            links=[l['uri'] for pg in doc for l in pg.get_links() if l.get('uri','').startswith('https://wa.me/')]
            payloads=[parse_qs(urlsplit(u).query).get('text',[''])[0] for u in links]
            # Event's old one-liner is distinct, period plan chunks contain the whole list.
            self.assertGreater(len(payloads),10)
            self.assertTrue(all(len(u)<1801 for u in links))
            self.assertTrue(any('ÖzelKonu129' in x for x in payloads))
            self.assertTrue(any('Bölüm 1/' in x for x in payloads))

    def test_unidentified_student_has_no_new_hub_contact(self):
        schedule={d:[] for d in LABELS}
        schedule['Pazartesi']=[event(sid=None)]
        snap=build_pocket_snapshot(schedule,DAYS)
        self.assertEqual(prepare_offline_message_pack(snap['students'][0]),{})


class RangeTests(unittest.TestCase):
    def make_db(self, where):
        path=Path(where)/'synthetic.db'
        with sqlite3.connect(path) as db:
            db.executescript('''
                CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT,soyad TEXT,
                    ogr_tel TEXT,veli_tel1 TEXT,kocluk_gunu TEXT,kocluk_saati TEXT,
                    ana_grup TEXT,aktif INTEGER);
                CREATE TABLE odev_kume (id INTEGER PRIMARY KEY,ogrenci_id INTEGER,
                    bitis_tarihi TEXT,aciklama TEXT);
                CREATE TABLE odev (id INTEGER PRIMARY KEY,kume_id INTEGER,
                    ders TEXT,kitap_ad TEXT,konu_ad TEXT);
                INSERT INTO ogrenci VALUES (1,'Test','Bir','+999123456789',
                    '+999123456788','Pazartesi','15:30','YKS',1);
                INSERT INTO ogrenci VALUES (2,'Test','İki','+999123456787',
                    '+999123456786','Pazartesi','16:30','LGS',1);
                INSERT INTO odev_kume VALUES (5,1,'2026-10-29',NULL);
                INSERT INTO odev VALUES (10,5,'Fizik','Kitap','Basınç');
            ''')
        return path

    def test_10_14_days_repeat_monday_distinct_date_and_out_of_7_due(self):
        with TemporaryDirectory() as td:
            p=self.make_db(td)
            before=hashlib.sha256(p.read_bytes()).hexdigest()
            for length in (10,14):
                with self.subTest(length=length):
                    schedule,days=fetch_mobile_pdf_schedule_range(p,group_filter='YKS',
                                                 days_count=length,today=DAY0)
                    self.assertEqual(len(days),length)
                    self.assertEqual(len(schedule),length)
                    self.assertEqual(len([k for k in schedule if k.startswith('Pazartesi')]),2)
                    self.assertEqual(sum(ev['tip']=='Görüşme' for evs in schedule.values() for ev in evs),2)
                    self.assertEqual(sum(ev['tip']=='Teslim' for evs in schedule.values() for ev in evs),
                                    1 if length==14 else 0)
                    self.assertFalse(any(ev['oid']==2 for evs in schedule.values() for ev in evs))
            self.assertEqual(before,hashlib.sha256(p.read_bytes()).hexdigest())

    def test_period_rejects_unsafe_inputs(self):
        with TemporaryDirectory() as td:
            p=self.make_db(td)
            for arg in (0,15,True,'14'):
                with self.subTest(value=arg),self.assertRaises(ValueError):
                    fetch_mobile_pdf_schedule_range(p,days_count=arg,today=DAY0)

    def test_extended_period_pdf_message_dates(self):
        with TemporaryDirectory() as td:
            db=self.make_db(td)
            schedule,days=fetch_mobile_pdf_schedule_range(db,group_filter='YKS',
                                days_count=14,today=DAY0)
            tmp,pdf,_=render(schedule,days)
            self.addCleanup(tmp.cleanup)
            with fitz.open(pdf) as doc:
                text='\n'.join(p.get_text() for p in doc)
                self.assertIn('2026-10-29',text)
                self.assertIn('Basınç',text)
                self.assertIn('Görüşme',text)
                links=[l['uri'] for page in doc for l in page.get_links() if l.get('uri')]
                self.assertTrue(any(u.startswith('https://wa.me/') for u in links))

if __name__=='__main__': unittest.main()
