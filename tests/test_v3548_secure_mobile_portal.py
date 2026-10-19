# -*- coding: utf-8 -*-
"""V3.5.48 - persistent scoped mobile gateway (synthetic students only)."""
import datetime as dt
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

from services.mobile_pdf_secure_portal_v3548 import (
    TeacherPrincipal, PersistentStudentLinkStore, prepare_scoped_pdf_links,
    create_scoped_mobile_wsgi_app,
)
from services.mobile_pdf_live_gateway_v3547 import PREFIX
from tests.test_v3546_mobile_pdf_bridge import V3546BridgeTests


class SecurePortalTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now=[50000.0]
        self.path=Path(self.temp.name)/'links.db'
        self.store=PersistentStudentLinkStore(self.path,clock=lambda:self.now[0])
        self.teacher=TeacherPrincipal('kurumA','ogretmen1',self.now[0]+3600)
        self.teacher2=TeacherPrincipal('kurumA','ogretmen2',self.now[0]+3600)
        self.other=TeacherPrincipal('kurumB','ogretmen1',self.now[0]+3600)
        self.sample={'verified':True,'homework':{'total':2,'completed':1,'overdue':1},
                     'coaching_plan':{'summary':'Plan var'},'exam':{'state':'PARTIAL'},
                     'followup':{'state':'DUE'},'summary':'Ödev & sınav kontrolü'}
        self.ref=self.store.issue(student_id=1,tenant_id='kurumA',teacher_id='ogretmen1',verified=True,ttl_seconds=600)

    def app(self, principal=None, acl=lambda p,s: s==1, reader=None, **kwargs):
        session=(lambda env: principal if principal is not None else self.teacher)
        if reader is None:
            reader=lambda sid: ('<script>Student</script>', self.sample)
        return create_scoped_mobile_wsgi_app(self.store,'academic.db',
            origin='https://koc.okul.edu.tr',authenticate_session=session,
            authorize_student=acl,card_reader=reader,clock=lambda:self.now[0],**kwargs)

    def invoke(self, app=None, ref=None, method='GET', scheme='https', host='koc.okul.edu.tr', path=None):
        seen=[]
        def respond(status,headers): seen.extend([status,dict(headers)])
        env={'REQUEST_METHOD':method,'PATH_INFO':path or PREFIX+(ref or self.ref),
             'wsgi.url_scheme':scheme,'HTTP_HOST':host}
        content=b''.join((app or self.app())(env,respond))
        return seen[0],seen[1],content

    def test_persistent_hash_only_restarts_without_losing_link(self):
        other=PersistentStudentLinkStore(self.path,clock=lambda:self.now[0])
        self.assertEqual(other.resolve(self.ref).student_id,1)
        raw=self.path.read_bytes()
        self.assertNotIn(self.ref.encode('ascii'),raw)
        self.assertNotIn(b'Student',raw)
        self.assertNotIn(b'0555',raw)

    def test_revoke_single_and_teacher_all(self):
        self.assertTrue(self.store.revoke(self.ref))
        self.assertFalse(self.store.revoke(self.ref))
        second=self.store.issue(student_id=2,tenant_id='kurumA',teacher_id='ogretmen1',verified=True)
        third=self.store.issue(student_id=3,tenant_id='kurumA',teacher_id='ogretmen2',verified=True)
        self.assertEqual(self.store.revoke_teacher('kurumA','ogretmen1'),1)
        self.assertIsNone(self.store.resolve(second))
        self.assertIsNotNone(self.store.resolve(third))

    def test_ttl_boundary_exact(self):
        self.now[0] += 599.99
        self.assertIsNotNone(self.store.resolve(self.ref))
        self.now[0] += .01
        self.assertIsNone(self.store.resolve(self.ref))

    def test_verified_student_and_ttl_and_scope_required(self):
        for kwargs in ({'verified':False},{'student_id':0,'verified':True},
                       {'student_id':True,'verified':True},{'ttl_seconds':59,'verified':True},
                       {'ttl_seconds':864000,'verified':True},
                       {'tenant_id':'bad tenant','verified':True}):
            args=dict(student_id=1,tenant_id='kurumA',teacher_id='ogretmen1',verified=True)
            args.update(kwargs)
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                self.store.issue(**args)

    def test_no_automatic_pdf_links_without_explicit_readiness(self):
        ctx={'student_cards':{'1':{'verified':True},'2':{'verified':False}}}
        kw=dict(principal=self.teacher,authorize_student=lambda p,s: True,
                origin='https://koc.okul.edu.tr',clock=lambda:self.now[0])
        self.assertEqual(prepare_scoped_pdf_links(ctx,self.store,**kw),{})
        self.assertEqual(prepare_scoped_pdf_links(ctx,self.store,explicit_opt_in=True,**kw),{})
        self.assertEqual(prepare_scoped_pdf_links(ctx,self.store,deployment_ready=True,**kw),{})
        made=prepare_scoped_pdf_links(ctx,self.store,explicit_opt_in=True,deployment_ready=True,**kw)
        self.assertEqual(list(made),['1'])
        self.assertEqual(self.store.resolve(made['1'].split('/')[-1]).student_id,1)
        self.assertNotIn('/1',made['1'])

    def test_pdf_issue_requires_live_acl(self):
        ctx={'student_cards':{'1':{'verified':True},'2':{'verified':True}}}
        kw=dict(principal=self.teacher,authorize_student=lambda p,s:s==1,
                origin='https://koc.okul.edu.tr',clock=lambda:self.now[0],
                explicit_opt_in=True,deployment_ready=True)
        self.assertEqual(list(prepare_scoped_pdf_links(ctx,self.store,**kw)),['1'])
        self.assertEqual(prepare_scoped_pdf_links(ctx,self.store,**(kw|{'principal':self.teacher2,
                        'authorize_student':lambda p,s: False})),{})

    def test_session_timeout_blocks_pdf(self):
        expired=TeacherPrincipal('kurumA','ogretmen1',self.now[0])
        self.assertEqual(self.invoke(self.app(principal=expired))[0],'401 Unauthorized')
        ctx={'student_cards':{'1':{'verified':True}}}
        self.assertEqual(prepare_scoped_pdf_links(ctx,self.store,principal=expired,
                       authorize_student=lambda p,s:True,origin='https://koc.okul.edu.tr',
                       explicit_opt_in=True,deployment_ready=True,clock=lambda:self.now[0]),{})

    def test_requires_external_auth_and_acl_callbacks(self):
        for auth,acl in ((None,None),(lambda env:self.teacher,None),(None,lambda p,s:True)):
            with self.subTest(auth=auth,acl=acl),self.assertRaises(ValueError):
                create_scoped_mobile_wsgi_app(self.store,'academic.db',
                    origin='https://koc.okul.edu.tr',authenticate_session=auth,authorize_student=acl)

    def test_tls_and_exact_host_do_not_trust_forwarded_headers(self):
        self.assertEqual(self.invoke(scheme='http')[0],'404 Not Found')
        self.assertEqual(self.invoke(host='evil.edu.tr')[0],'404 Not Found')
        self.assertEqual(self.invoke(host='koc.okul.edu.tr:8000')[0],'404 Not Found')
        self.assertEqual(self.invoke()[0],'200 OK')

    def test_distinct_teachers_and_tenants_cannot_reuse_reference(self):
        self.assertEqual(self.invoke(self.app(principal=self.teacher2))[0],'404 Not Found')
        self.assertEqual(self.invoke(self.app(principal=self.other))[0],'404 Not Found')
        self.assertEqual(self.invoke()[0],'200 OK')

    def test_independent_acl_is_checked_on_every_request(self):
        count=[0]
        def acl(principal,sid):
            count[0]+=1
            return count[0] == 1
        app=self.app(acl=acl)
        self.assertEqual(self.invoke(app)[0],'200 OK')
        self.assertEqual(self.invoke(app)[0],'403 Forbidden')
        self.assertEqual(count[0],2)

    def test_no_post_or_head_body_and_xss(self):
        self.assertEqual(self.invoke(method='POST')[0],'405 Method Not Allowed')
        status,headers,body=self.invoke(method='HEAD')
        self.assertEqual(status,'200 OK')
        self.assertEqual(body,b'')
        self.assertIn('no-store',headers['Cache-Control'])
        _,_,html=self.invoke()
        self.assertIn(b'&lt;script&gt;',html)
        self.assertNotIn(b'<script>',html)

    def test_authenticated_rate_limit_persists_across_restart(self):
        app=self.app(max_per_minute=2)
        self.assertEqual(self.invoke(app)[0],'200 OK')
        self.assertEqual(self.invoke(app)[0],'200 OK')
        self.assertEqual(self.invoke(app)[0],'429 Too Many Requests')
        reloaded=PersistentStudentLinkStore(self.path,clock=lambda:self.now[0])
        self.assertFalse(reloaded.check_rate('kurumA','ogretmen1',maximum=2))
        self.now[0]+=61
        self.assertEqual(self.invoke(app)[0],'200 OK')

    def test_token_not_exposed_via_wrong_student_request(self):
        self.assertEqual(self.invoke(ref='A'*43)[0],'404 Not Found')
        self.assertEqual(self.invoke(path=PREFIX+self.ref+'/extra')[0],'404 Not Found')
        self.assertEqual(self.invoke(path='/other/'+self.ref)[0],'404 Not Found')

    def test_db_fail_closed(self):
        def bad(sid):raise RuntimeError('database offline')
        self.assertEqual(self.invoke(self.app(reader=bad))[0],'404 Not Found')
        self.assertEqual(self.invoke(self.app(reader=lambda sid:('Name',{'verified':False})))[0],'404 Not Found')

    def test_no_mutation_of_real_academic_test_sqlite(self):
        from services.mobile_pdf_live_gateway_v3547 import _read_verified_card
        fixture=V3546BridgeTests('test_verified_local_student_uses_canonical_homework_and_real_plan')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        before=hashlib.sha256(fixture.dbfile.read_bytes()).hexdigest()
        app=self.app(reader=lambda sid:_read_verified_card(fixture.dbfile,sid))
        self.assertEqual(self.invoke(app)[0],'200 OK')
        self.assertEqual(hashlib.sha256(fixture.dbfile.read_bytes()).hexdigest(),before)


if __name__=='__main__':unittest.main()
