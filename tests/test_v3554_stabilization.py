# -*- coding: utf-8 -*-
"""V3.5.54 synthetic-only stabilization of independent mobile PDF option."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from urllib.parse import urlsplit, parse_qs
import hashlib

import fitz

from services.smart_mobile_pdf_v3545 import build_pocket_snapshot, render_smart_pocket_pdf
from tools.v3554_pdf_audit import audit_pdf, check_uri

WEEK = [((date(2026, 10, 19)+timedelta(days=i)).isoformat(),
         ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar'][i]) for i in range(7)]


def ev(sid, name, phone='05551234567', parent='05321112233', typ='Teslim'):
    return {'oid': sid, 'ad': name, 'tel_ogr': phone, 'tel_veli': parent, 'tip':typ,
            'saat':'16:00', 'meta':{'lines':['Fizik - Basınç'],
                                  'notes':['ÖĞRETMENİN ÖZEL NOTU'], 'status':'normal'}}


def export(path, schedule, **kwargs):
    return render_smart_pocket_pdf(path, schedule, WEEK,
        student_message=lambda event,*a:'Merhaba '+event['ad']+'\nFizik - Basınç',
        parent_message=lambda event,*a:'Sayın Velimiz '+event['ad'], **kwargs)


class StabilizationTests(TestCase):
    def test_no_id_cannot_start_any_recipient_contact(self):
        for bad_id in (None, '', 0, True, 'bad-id', '-4'):
            with self.subTest(sid=repr(bad_id)), TemporaryDirectory() as td:
                schedule={'Pazartesi':[ev(bad_id,'Kimliği Eksik Öğrenci')]}
                snap=build_pocket_snapshot(schedule,WEEK)
                self.assertIsNone(snap['students'][0]['id'])
                pdf=Path(td)/'missing.pdf'
                export(pdf,schedule)
                with fitz.open(pdf) as doc:
                    uris=[link.get('uri') for pg in doc for link in pg.get_links() if link.get('uri')]
                    self.assertFalse(any(u.startswith(('https://wa.me/','tel:')) for u in uris))
                    self.assertIn('güvenlik için kapatıldı', '\n'.join(pg.get_text() for pg in doc))

    def test_same_student_id_with_different_names_blocks_all_contact(self):
        schedule={'Pazartesi':[ev(21,'Deniz Yılmaz')],
                  'Salı':[ev(21,'Emre Yılmaz')]}
        snapshot=build_pocket_snapshot(schedule,WEEK)
        self.assertEqual(snapshot['student_count'],1)
        self.assertTrue(snapshot['students'][0]['identity_conflict'])
        with TemporaryDirectory() as td:
            path=Path(td)/'conflict.pdf'
            original=deepcopy(schedule)
            export(path,schedule, academic_context={'student_cards':{'21':{
                'verified':True,'contact_allowed':True,'summary':'Verified'}},
                'source_state':'LOCAL_VERIFIED','verified_count':1,'student_count':1})
            self.assertEqual(schedule,original)
            with fitz.open(path) as doc:
                text='\n'.join(pg.get_text() for pg in doc)
                self.assertIn('farklı isimlerle',text)
                urls=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
                self.assertFalse(any(uri.startswith(('https://wa.me/','tel:')) for uri in urls))
                self.assertNotIn('Verified',text)

    def test_normal_verified_same_student_preserves_wa_call_and_calendar(self):
        schedule={'Pazartesi':[ev(21,'Deniz Yılmaz')],
                  'Salı':[ev(21,'deniz   yılmaz',typ='Görüşme')]}
        self.assertFalse(build_pocket_snapshot(schedule,WEEK)['students'][0]['identity_conflict'])
        with TemporaryDirectory() as td:
            path=Path(td)/'ok.pdf'
            export(path,schedule)
            result=audit_pdf(path)
            self.assertEqual(result['status'],'PASS',result)
            with fitz.open(path) as doc:
                links=[ln.get('uri') for pg in doc for ln in pg.get_links() if ln.get('uri')]
                self.assertTrue(any(x.startswith('https://wa.me/') for x in links))
                self.assertTrue(any(x.startswith('tel:') for x in links))
                self.assertTrue(any(x.startswith('https://calendar.google.com/') for x in links))

    def test_pdf_auditor_rejects_untrusted_uris(self):
        for bad,expected in [
            ('javascript:alert(1)','DISALLOWED_SCHEME'),
            ('https://example.com/student/123','UNAPPROVED_EXTERNAL_HOST'),
            ('tel:+1234','INVALID_PHONE_LINK'),
            ('https://wa.me/1234?text=x','INVALID_WHATSAPP_LINK'),
            ('file:///etc/passwd','DISALLOWED_SCHEME'),
        ]:
            with self.subTest(uri=bad):
                self.assertEqual(check_uri(bad),expected)

    def test_pdf_fails_closed_if_academic_context_cannot_verify_student(self):
        with TemporaryDirectory() as td:
            path=Path(td)/'unsafe.pdf'
            export(path,{'Pazartesi':[ev(1,'Öğrenci')]}, academic_context={
                'source_state':'UNVERIFIED', 'student_count':1,'verified_count':0,
                'student_cards':{'1':{'verified':False,'contact_allowed':False}}})
            with fitz.open(path) as doc:
                urls=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
                self.assertFalse(any(x.startswith(('https://wa.me/','tel:')) for x in urls))
                self.assertEqual(audit_pdf(path)['status'],'PASS')

    def test_existing_output_survives_failed_generation(self):
        with TemporaryDirectory() as td:
            path=Path(td)/'existing.pdf'
            data=b'ORIGINAL FILE TO PRESERVE'
            path.write_bytes(data)
            before=hashlib.sha256(path.read_bytes()).digest()
            with self.assertRaises(ValueError):
                render_smart_pocket_pdf(path, {}, [], student_message=lambda e,*a:'',
                                        parent_message=lambda e,*a:'')
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),before)
