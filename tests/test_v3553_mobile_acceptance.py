# -*- coding: utf-8 -*-
"""Synthetic acceptance. These tests NEVER claim physical iPhone/Android testing."""
from __future__ import annotations

from copy import deepcopy
from datetime import date,timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlsplit,parse_qs

from tools.v3553_mobile_acceptance import (
    REQUIRED,template,validate_device_acceptance,check_mobile_source,
)
from services.smart_mobile_pdf_v3545 import render_smart_pocket_pdf

ROOT=Path(__file__).resolve().parents[1]
SHA='a'*40
NOW=date(2026,10,19)


def completed():
    item=template('3.5.53')
    item.update(git_commit=SHA,tested_at=NOW.isoformat())
    for platform in REQUIRED:
        item['devices'][platform]['tester']='Synthetic Tester'
        item['devices'][platform]['device']='Test Device OS 1 / PDF Reader'
        item['devices'][platform]['checks']={k:'PASS' for k in REQUIRED[platform]}
    return item


def demo_pdf(target,days=7,untrusted=False):
    period=[];schedule={}
    start=date(2026,10,19)
    for i in range(days):
        d=start+timedelta(days=i)
        wd=['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar'][i%7]
        label=f'{wd} {d.isoformat()}'
        period.append((d.isoformat(),label))
        schedule[label]=[]
    schedule[period[0][1]].append({'oid':11,'ad':'Deniz Test','tel_ogr':'05551234567',
                                   'tel_veli':'05321112233','tip':'Teslim','saat':'16:00',
                                   'meta':{'lines':['Fizik - Hareket','Matematik - Polinomlar'],
                                           'notes':['PRIVATE_TEACHER_NOTE'], 'status':'normal'}})
    schedule[period[-1][1]].append({'oid':22,'ad':'Deniz Test','tel_ogr':'05559876543',
                                   'tel_veli':'05321119999','tip':'Görüşme','saat':'16:30',
                                   'meta':{'lines':[], 'status':'normal'}})
    cards={'11':{'verified':True,'contact_allowed':True,'state':'READY',
                 'homework':{'total':2,'completed':1,'overdue':1},'summary':'Kontrol'},
           '22':{'verified':True,'contact_allowed':not untrusted,'state':'READY',
                 'homework':{'total':1,'completed':0,'overdue':0},'summary':'Kontrol'}}
    context={'source_state':'LOCAL_VERIFIED','student_count':2,'verified_count':2,
             'student_cards':cards,'warnings':[]}
    before=deepcopy(schedule)
    result=render_smart_pocket_pdf(target,schedule,period,academic_context=context,
                student_message=lambda ev,*x:'Öğrenci için ödev '+ev['ad'],
                parent_message=lambda ev,*x:'Veli için ödev '+ev['ad'])
    assert schedule==before
    return result


class MobileManualGateTests(unittest.TestCase):
    def test_unfilled_template_denied(self):
        with self.assertRaises(ValueError):
            validate_device_acceptance(template('3.5.53'),version='3.5.53',commit=SHA,today=NOW)

    def test_acceptance_is_bound_to_version_commit_date_and_synthetic_records(self):
        doc=completed()
        self.assertEqual(validate_device_acceptance(doc,version='3.5.53',commit=SHA,today=NOW)['mobile_pdf_device_status'],'PASS')
        for key,bad in [('version','3.5.52'),('git_commit','b'*40),('test_data','LIVE_STUDENTS'),
                        ('tested_at','2026-09-01'),('tested_at','2026-11-01')]:
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                changed=deepcopy(doc); changed[key]=bad
                validate_device_acceptance(changed,version='3.5.53',commit=SHA,today=NOW)

    def test_platforms_and_each_required_check_must_pass(self):
        doc=completed()
        for platform,checks in REQUIRED.items():
            with self.subTest(platform=platform),self.assertRaises(ValueError):
                c=deepcopy(doc);del c['devices'][platform]
                validate_device_acceptance(c,version='3.5.53',commit=SHA,today=NOW)
            for check in checks:
                with self.subTest(platform=platform,check=check),self.assertRaises(ValueError):
                    c=deepcopy(doc);c['devices'][platform]['checks'][check]='PENDING'
                    validate_device_acceptance(c,version='3.5.53',commit=SHA,today=NOW)

    def test_no_generic_pass_without_named_tester_device(self):
        for field,val in [('tester','<filled>'),('device','TODO')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                c=completed();c['devices']['iphone'][field]=val
                validate_device_acceptance(c,version='3.5.53',commit=SHA,today=NOW)

    def test_source_gate_keeps_protected_forms(self):
        self.assertEqual(check_mobile_source(ROOT)['protected_core'],'PASS')
        self.assertEqual(check_mobile_source(ROOT)['actual_device_acceptance'],'NOT_VERIFIED')

    def test_tag_release_has_both_windows_and_mobile_gates(self):
        text=(ROOT/'.github/workflows/build_installer.yml').read_text(encoding='utf8')
        self.assertIn('tools/v35_release_gate.py --require-acceptance',text)
        self.assertIn('tools/v3553_mobile_acceptance.py --require-device-acceptance',text)
        self.assertIn('V3553_MOBILE_DEVICE_ACCEPTANCE_JSON',text)
        self.assertIn('if ($LASTEXITCODE -ne 0)',text)


class MobilePDFAcceptanceTests(unittest.TestCase):
    def test_7_10_14_days_preserve_navigation_and_contact_actions(self):
        import fitz
        for length in (7,10,14):
            with self.subTest(days=length),TemporaryDirectory() as td:
                path=Path(td)/'preview.pdf'
                out=demo_pdf(path,length)
                with fitz.open(path) as document:
                    self.assertEqual(out['days'],length)
                    self.assertGreaterEqual(document.page_count,1)
                    text='\n'.join(p.get_text() for p in document)
                    self.assertIn('DÖNEMLİK MOBİL MESAJ MERKEZİ',text)
                    self.assertIn('ÖĞRENCİ HIZLI ERİŞİM',text)
                    if length==14:
                        self.assertIn('Pazartesi', document[0].get_text())  # day menu no longer pushed entirely to page 2
                    self.assertIn('No 11',text)
                    self.assertIn('No 22',text)
                    self.assertNotIn('PRIVATE_TEACHER_NOTE',text)
                    links=[(p, link) for p in document for link in p.get_links()]
                    kinds=[link.get('kind') for _,link in links]
                    self.assertGreaterEqual(kinds.count(fitz.LINK_GOTO),length+2)
                    external=[link['uri'] for _,link in links if link.get('uri')]
                    self.assertEqual(len(external),out['external_links'])
                    self.assertTrue(any(uri.startswith('https://wa.me/') for uri in external))
                    self.assertTrue(any(uri.startswith('tel:') for uri in external))
                    self.assertTrue(any(uri.startswith('https://calendar.google.com/') for uri in external))
                    for p,link in links:
                        rect=link['from']
                        self.assertGreater(rect.width,0)
                        self.assertGreater(rect.height,0)
                        self.assertTrue(p.rect.contains(rect))
                        if link.get('kind')==fitz.LINK_GOTO:
                            self.assertTrue(0 <= link['page'] < len(document))
                    msgs=[parse_qs(urlsplit(u).query).get('text',[''])[0]
                          for u in external if u.startswith('https://wa.me/')]
                    self.assertTrue(any('Fizik - Hareket' in x for x in msgs))
                    self.assertTrue(any('Sayın Velimiz' in x for x in msgs))
                    self.assertTrue(any('Merhaba' in x for x in msgs))

    def test_unverified_recipient_blocks_communication_without_breaking_pdf(self):
        import fitz
        with TemporaryDirectory() as td:
            path=Path(td)/'test.pdf'
            demo_pdf(path,7,untrusted=True)
            with fitz.open(path) as doc:
                uris=[ln['uri'] for page in doc for ln in page.get_links() if ln.get('uri')]
                self.assertFalse(any('/905559876543?' in u or 'tel:+905559876543' in u for u in uris))
                self.assertTrue(any('/905551234567?' in u for u in uris))

    def test_pdf_integrity_and_static_snapshot_remain_offline(self):
        import fitz
        with TemporaryDirectory() as td:
            path=Path(td)/'preview.pdf'
            demo_pdf(path,7)
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            with fitz.open(path) as doc:
                self.assertTrue(all(page.get_text() for page in doc))
                uri_list=[ln['uri'] for page in doc for ln in page.get_links() if ln.get('uri')]
                self.assertFalse(any('javascript:' in x.lower() for x in uri_list))
                self.assertFalse(any('127.0.0.1' in x or 'localhost' in x for x in uri_list))
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()
