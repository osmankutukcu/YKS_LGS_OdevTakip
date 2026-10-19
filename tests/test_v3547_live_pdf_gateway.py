# -*- coding: utf-8 -*-
"""V3.5.47: read-only, deny-by-default mobile gateway and PDF link tests."""
from __future__ import annotations
import datetime as dt
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import fitz

from services.mobile_pdf_live_gateway_v3547 import (
    StudentLinkRegistry, create_readonly_wsgi_app, prepare_pdf_links,
    validate_https_origin, validate_pdf_live_link, PREFIX,
)
from services.smart_mobile_pdf_v3545 import render_smart_pocket_pdf
from tests.test_v3546_mobile_pdf_bridge import entry, V3546BridgeTests, WEEK


class LiveGatewayTests(unittest.TestCase):
    def setUp(self):
        self.now=[1000.0]
        self.registry=StudentLinkRegistry(clock=lambda:self.now[0])
        self.ref=self.registry.issue(1,verified=True,ttl_seconds=600)
        self.calls=[]

    def app(self, auth=lambda e:'teacher', acl=lambda p,s: s==1, reader=None):
        card={'verified':True, 'homework':{'total':2,'completed':1,'overdue':1},
              'summary':'Fizik & matematik kontrolü',
              'coaching_plan':{'summary':'Öğretmen takibi'},
              'exam':{'state':'PARTIAL'},'followup':{'state':'DUE'},'partial':False}
        return create_readonly_wsgi_app(self.registry, 'irrelevant.db',authenticate=auth,
                         authorize=acl,card_reader=reader or (lambda sid:('<script>alert(1)</script>',card)))

    def invoke(self, app, *,ref=None, method='GET'):
        hdr=[]
        def start(status,headers):hdr.extend([status,dict(headers)])
        env={'REQUEST_METHOD':method,'PATH_INFO':PREFIX+(ref or self.ref)}
        raw=b''.join(app(env,start))
        return hdr[0],hdr[1],raw

    def test_no_anonymous_gateway_construction(self):
        for x,y in ((None,None),(lambda e:None,None),(None,lambda p,s: True)):
            with self.subTest(x=x,y=y),self.assertRaises(ValueError):
                create_readonly_wsgi_app(self.registry, 'a',authenticate=x,authorize=y)

    def test_authenticated_authorized_reads_and_xss_escaped(self):
        status,headers,html=self.invoke(self.app())
        self.assertEqual(status,'200 OK')
        self.assertIn(b'&lt;script&gt;',html)
        self.assertNotIn(b'<script>',html)
        self.assertIn(b'Fizik &amp; matematik',html)
        self.assertEqual(headers['Cache-Control'],'no-store, private')
        self.assertIn("default-src 'none'",headers['Content-Security-Policy'])
        self.assertEqual(headers['Referrer-Policy'],'no-referrer')
        self.assertNotIn(b'0555',html)

    def test_missing_login_does_not_expose(self):
        status,headers,body=self.invoke(self.app(auth=lambda e:None))
        self.assertEqual(status,'401 Unauthorized')
        self.assertNotIn(b'Fizik',body)

    def test_wrong_teacher_cannot_read_student(self):
        status,_,body=self.invoke(self.app(acl=lambda p,s: False))
        self.assertEqual(status,'403 Forbidden')
        self.assertNotIn(b'Fizik',body)

    def test_missing_expired_or_revoked_ref(self):
        self.assertEqual(self.invoke(self.app(),ref='random')[0],'404 Not Found')
        self.now[0]+=600
        self.assertEqual(self.invoke(self.app())[0],'404 Not Found')
        r=self.registry.issue(1,verified=True,ttl_seconds=600)
        self.registry.revoke(r)
        self.assertIsNone(self.registry.resolve(r))

    def test_fail_closed_reader(self):
        self.assertEqual(self.invoke(self.app(reader=lambda s:None))[0],'404 Not Found')
        def bad(_): raise RuntimeError('DB offline')
        self.assertEqual(self.invoke(self.app(reader=bad))[0],'404 Not Found')

    def test_ref_does_not_allow_http_mutation(self):
        status,_,body=self.invoke(self.app(),method='POST')
        self.assertEqual(status,'405 Method Not Allowed')
        self.assertEqual(self.invoke(self.app(),method='DELETE')[0],'405 Method Not Allowed')

    def test_scoped_and_non_identifying_refs(self):
        self.assertEqual(self.registry.resolve(self.ref),1)
        self.assertNotIn('student',self.ref.lower())
        self.assertGreaterEqual(len(self.ref),32)
        for bad in (0,True,'0',None,3.3):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.registry.issue(bad,verified=True)
        with self.assertRaises(ValueError):
            self.registry.issue(2,verified=False)
        for bad in (False,1.2,0,59,604801):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.registry.issue(2,verified=True,ttl_seconds=bad)

    def test_https_restrictions_no_credentials_or_ip(self):
        for bad in ('http://school.edu.tr','https://user:pw@school.edu.tr',
                    'https://127.0.0.1','https://school.local',
                    'https://school.edu.tr/x','https://school.edu.tr?a=1',
                    'https://school.edu.tr:8000','https://example.com',
                    'javascript:alert(1)'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                validate_https_origin(bad)
        origin=validate_https_origin('https://koc.okul.edu.tr')
        self.assertEqual(origin,'https://koc.okul.edu.tr')
        good=origin+PREFIX+self.ref
        self.assertTrue(validate_pdf_live_link(good,origin))
        for bad in ('https://bad.edu.tr'+PREFIX+self.ref,
                    good+'?redirect=https://bad.edu.tr', good+'#x',
                    good.replace('https','http',1),
                    origin+'/student/1'):
            self.assertFalse(validate_pdf_live_link(bad,origin))

    def test_pdf_links_disabled_by_default_even_with_verified_student(self):
        ctx={'student_cards':{'1':{'verified':True},'2':{'verified':False}}}
        self.assertEqual(prepare_pdf_links(ctx,self.registry),{})
        self.assertEqual(prepare_pdf_links(ctx,self.registry,enabled=True,
                     https_origin='https://koc.okul.edu.tr'),{})
        urls=prepare_pdf_links(ctx,self.registry,enabled=True,authenticated_gateway_ready=True,
                     https_origin='https://koc.okul.edu.tr')
        self.assertEqual(list(urls),['1'])
        self.assertTrue(validate_pdf_live_link(urls['1'],'https://koc.okul.edu.tr'))
        self.assertNotIn('/1',urls['1'])

    def test_no_link_for_wrong_student_inside_pdf(self):
        from tests.test_v3546_mobile_pdf_bridge import entry
        ctx={'student_cards':{'1':{'verified':True},'2':{'verified':False}},'source_state':'PARTIAL',
             'verified_count':1,'student_count':2,'warnings':[]}
        origin='https://koc.okul.edu.tr'
        urls=prepare_pdf_links(ctx,self.registry,enabled=True,authenticated_gateway_ready=True,
                              https_origin=origin)
        rows=[entry(1,'Test Öğrenci'),entry(2,'İkinci Öğrenci')]
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'live.pdf'
            result=render_smart_pocket_pdf(path,{'Pazar':rows},WEEK,
                 academic_context=ctx, live_links=urls,live_https_origin=origin,
                 student_message=lambda *args:'Test',parent_message=lambda *args:'Test')
            self.assertEqual(result['live_links'],1)
            with fitz.open(path) as doc:
                links=[d['uri'] for p in doc for d in p.get_links() if d.get('uri')]
            self.assertEqual([x for x in links if PREFIX in x],list(urls.values()))

    def test_actual_sqlite_reader_uses_current_verified_student_and_is_readonly(self):
        import hashlib
        from services.mobile_pdf_live_gateway_v3547 import _read_verified_card
        fixture=V3546BridgeTests('test_verified_local_student_uses_canonical_homework_and_real_plan')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        before=hashlib.sha256(fixture.dbfile.read_bytes()).hexdigest()
        name, card=_read_verified_card(fixture.dbfile,1)
        self.assertEqual(name,'Test Öğrenci')
        self.assertTrue(card['verified'])
        self.assertEqual(card['homework']['overdue'],1)
        self.assertIsNone(_read_verified_card(fixture.dbfile,999))
        self.assertEqual(hashlib.sha256(fixture.dbfile.read_bytes()).hexdigest(),before)

    def test_malicious_pdf_link_rejected(self):
        self.assertFalse(validate_pdf_live_link('https://evil.edu.tr/mobile/academic/r/'+'a'*43,
                                      'https://koc.okul.edu.tr'))


if __name__=='__main__':
    unittest.main()
