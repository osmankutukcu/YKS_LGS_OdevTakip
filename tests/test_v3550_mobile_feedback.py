# -*- coding: utf-8 -*-
"""Synthetic-only regression tests for future opt-in feedback ingress."""
import hashlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode, urlsplit, parse_qs
from datetime import date, timedelta
from contextlib import closing
import sqlite3
import unittest
import fitz

from services.mobile_pdf_feedback_v3550 import (
    FeedbackInbox, RecipientPrincipal, TeacherPrincipal, create_feedback_wsgi_app,
    prepare_feedback_links, validate_feedback_pdf_link, FEEDBACK_PREFIX
)
from services.smart_mobile_pdf_v3545 import render_smart_pocket_pdf
from tests.test_v3549_offline_mobile_center import event, DAYS, LABELS

ORIGIN='https://okul.eger.edu.tr'


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self._safe_cleanup)
        self.now=[100000.0]
        self.path=Path(self.temp.name)/'feedback.sqlite'
        self.store=FeedbackInbox(self.path,clock=lambda:self.now[0])
        self.teacher=TeacherPrincipal('kurumA','teacher1',self.now[0]+7200)
        self.sid=17
        self.student=RecipientPrincipal('kurumA','account17',self.sid,'student','session17',self.now[0]+7200)
        self.parent=RecipientPrincipal('kurumA','parent17',self.sid,'parent','sessionP17',self.now[0]+7200)
        self.ref=self.store.issue(student_id=self.sid,tenant_id='kurumA',
            teacher_id='teacher1',role='student',verified=True,ttl_seconds=3600)
        self.context={'student_cards':{'17':{'verified':True,'contact_allowed':True},
                                       '18':{'verified':False,'contact_allowed':True}}}
        self.csrf_secret=b'a'*32

    def _safe_cleanup(self):
        import gc
        gc.collect()
        try:
            self.temp.cleanup()
        except OSError:
            pass

    def app(self, principal=None, allowed=True):
        return create_feedback_wsgi_app(self.store,origin=ORIGIN,
            authenticate_session=lambda env: self.student if principal is None else principal,
            authorize_recipient=lambda p,sid,role:allowed and sid==self.sid and role==p.role,
            csrf_secret=self.csrf_secret, deployment_ready=True,clock=lambda:self.now[0])

    def call(self, *, ref=None, principal=None, method='GET', params=None, allowed=True,
             scheme='https', host='okul.eger.edu.tr', origin=ORIGIN, content_type='application/x-www-form-urlencoded'):
        responses=[]
        def start(st,headers):responses.append((st,dict(headers)))
        data=urlencode(params).encode('utf-8') if params is not None else b''
        env={'PATH_INFO':FEEDBACK_PREFIX+(ref or self.ref),'REQUEST_METHOD':method,
             'wsgi.url_scheme':scheme,'HTTP_HOST':host,'HTTP_ORIGIN':origin,
             'CONTENT_TYPE':content_type,'CONTENT_LENGTH':str(len(data)),
             'wsgi.input':io.BytesIO(data)}
        content=b''.join(self.app(principal,allowed)(env,start))
        return responses[0][0],responses[0][1],content

    def form_token(self,**kw):
        st,_,body=self.call(**kw)
        self.assertEqual(st,'200 OK')
        return body.decode().split('name="csrf" value="')[1].split('"')[0]

    def test_disabled_server_refuses_to_start_and_no_issue(self):
        with self.assertRaises(ValueError):
            create_feedback_wsgi_app(self.store,origin=ORIGIN,
                authenticate_session=lambda e:self.student,
                authorize_recipient=lambda *a:True,csrf_secret=b'b'*32)
        self.assertEqual(prepare_feedback_links(self.context,self.store,
            principal=self.teacher,authorize_student=lambda *x:True,
            recipient_eligible=lambda *x:True,origin=ORIGIN),{})

    def test_issue_requires_verified_student_role_and_limits(self):
        args=dict(student_id=17,tenant_id='kurumA',teacher_id='teacher1',role='student',verified=True)
        for delta in ({'verified':False},{'student_id':0},{'student_id':True},
                      {'role':'teacher'},{'tenant_id':'other domain'},{'ttl_seconds':8}):
            with self.subTest(delta=delta),self.assertRaises(ValueError):
                self.store.issue(**(args|delta))

    def test_issue_scopes_and_external_eligibility(self):
        kw=dict(principal=self.teacher,authorize_student=lambda p,s:s==17,
                recipient_eligible=lambda p,s,r:r=='parent',origin=ORIGIN,
                explicit_opt_in=True,deployment_ready=True,clock=lambda:self.now[0])
        links=prepare_feedback_links(self.context,self.store,**kw)
        self.assertEqual(list(links),['17'])
        self.assertEqual(list(links['17']),['parent'])
        self.assertTrue(validate_feedback_pdf_link(links['17']['parent'],ORIGIN))
        self.assertNotIn('/17',links['17']['parent'])
        self.assertEqual(self.store.get(links['17']['parent'].split('/')[-1]).role,'parent')

    def test_wrong_tenant_student_role_and_unverified_cannot_read(self):
        for bad in (RecipientPrincipal('kurumB','x',17,'student','s',self.now[0]+60),
                    RecipientPrincipal('kurumA','x',18,'student','s',self.now[0]+60),
                    self.parent):
            self.assertEqual(self.call(principal=bad)[0],'403 Forbidden')
        self.assertEqual(self.call(allowed=False)[0],'403 Forbidden')
        self.assertEqual(self.call(principal=False)[0],'401 Unauthorized')
        self.assertEqual(self.call(scheme='http')[0],'403 Forbidden')
        self.assertEqual(self.call(host='evil.edu.tr')[0],'403 Forbidden')

    def test_get_form_exposes_no_private_identity(self):
        st,headers,body=self.call()
        self.assertEqual(st,'200 OK')
        self.assertEqual(headers['Cache-Control'],'no-store, private')
        self.assertNotIn(b'account17',body)
        self.assertNotIn(b'teacher1',body)
        self.assertNotIn(b'phone',body)
        self.assertIn(b'name="csrf"',body)

    def test_post_requires_csrf_same_origin_and_expected_fields(self):
        key=self.form_token()
        fields={'status':'need_help','reason':'difficult','csrf':key}
        self.assertEqual(self.call(method='POST',params=fields|{'csrf':'BAD'})[0],'403 Forbidden')
        self.assertEqual(self.call(method='POST',params=fields,origin='https://evil.edu.tr')[0],'403 Forbidden')
        self.assertEqual(self.call(method='POST',params=fields|{'student_id':'999'})[0],'400 Bad Request')
        self.assertEqual(self.call(method='POST',params=fields|{'status':'unknown'})[0],'400 Bad Request')
        self.assertEqual(self.call(method='POST',params=fields,content_type='application/json')[0],'415 Unsupported Media Type')
        self.assertEqual(self.store.teacher_inbox(principal=self.teacher),[])

    def test_post_to_inbox_only_and_one_time_replay(self):
        token=self.form_token()
        fields={'status':'completed_claim','reason':'none','csrf':token}
        self.assertEqual(self.call(method='POST',params=fields)[0],'200 OK')
        self.assertEqual(self.call(method='POST',params=fields)[0],'409 Conflict')
        inbox=self.store.teacher_inbox(principal=self.teacher)
        self.assertEqual(len(inbox),1)
        self.assertEqual(inbox[0]['status'],'completed_claim')
        self.assertEqual(inbox[0]['student_id'],17)
        self.assertIsNone(inbox[0]['reviewed_at'])
        self.assertTrue(self.store.mark_reviewed(inbox[0]['id'],principal=self.teacher))
        self.assertFalse(self.store.mark_reviewed(inbox[0]['id'],principal=self.teacher))
        self.assertIsNotNone(self.store.teacher_inbox(principal=self.teacher)[0]['reviewed_at'])

    def test_wrong_teacher_cannot_read_review(self):
        key=self.form_token()
        self.call(method='POST',params={'status':'started','reason':'time','csrf':key})
        other=TeacherPrincipal('kurumA','teacher2',self.now[0]+3600)
        self.assertEqual(self.store.teacher_inbox(principal=other),[])
        self.assertFalse(self.store.mark_reviewed(1,principal=other))
        with self.assertRaises(PermissionError):
            self.store.teacher_inbox(principal=TeacherPrincipal('kurumA','teacher1',1))

    def test_parent_has_independent_login_and_response(self):
        p_ref=self.store.issue(student_id=17,tenant_id='kurumA',
                               teacher_id='teacher1',role='parent',verified=True)
        self.assertEqual(self.call(ref=p_ref,principal=self.student)[0],'403 Forbidden')
        token=self.form_token(ref=p_ref,principal=self.parent)
        data={'status':'meeting_request','reason':'none','csrf':token}
        self.assertEqual(self.call(ref=p_ref,principal=self.parent,method='POST',params=data)[0],'200 OK')
        self.assertEqual(self.store.teacher_inbox(principal=self.teacher)[0]['recipient_role'],'parent')

    def test_parallel_posts_only_one_persists(self):
        from concurrent.futures import ThreadPoolExecutor
        token=self.form_token()
        data={'status':'started','reason':'none','csrf':token}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _: self.call(method='POST',params=data)[0], range(4)))
        self.assertEqual(results.count('200 OK'),1)
        self.assertEqual(results.count('409 Conflict'),3)
        self.assertEqual(len(self.store.teacher_inbox(principal=self.teacher)),1)

    def test_origin_scoped_urls_require_exact_route_and_nosecrets(self):
        reference='A'*43
        good=ORIGIN+FEEDBACK_PREFIX+reference
        self.assertTrue(validate_feedback_pdf_link(good,ORIGIN))
        self.assertFalse(validate_feedback_pdf_link(good+'?other=1',ORIGIN))
        self.assertFalse(validate_feedback_pdf_link('https://okul.eger.edu.tr:444'+FEEDBACK_PREFIX+reference,ORIGIN))
        self.assertFalse(validate_feedback_pdf_link('https://okul.eger.edu.tr@evil.tld'+FEEDBACK_PREFIX+reference,ORIGIN))

    def test_expiry_restart_revocation_and_no_raw_tokens(self):
        self.assertEqual(FeedbackInbox(self.path,clock=lambda:self.now[0]).get(self.ref).student_id,17)
        self.assertNotIn(self.ref.encode('ascii'),self.path.read_bytes())
        self.assertTrue(self.store.revoke(self.ref))
        self.assertIsNone(self.store.get(self.ref))
        newer=self.store.issue(student_id=17,tenant_id='kurumA',teacher_id='teacher1',role='student',verified=True,ttl_seconds=60)
        self.now[0]+=60
        self.assertIsNone(self.store.get(newer))

    def test_revoke_teacher_prevents_pending_but_preserves_submissions(self):
        token=self.form_token()
        self.call(method='POST',params={'status':'need_help','reason':'time','csrf':token})
        new=self.store.issue(student_id=17,tenant_id='kurumA',teacher_id='teacher1',role='parent',verified=True)
        self.assertEqual(self.store.revoke_teacher('kurumA','teacher1'),1)
        self.assertIsNone(self.store.get(new))
        self.assertEqual(len(self.store.teacher_inbox(principal=self.teacher)),1)

    def test_no_academic_db_changes_or_user_notes(self):
        academic=Path(self.temp.name)/'academic.sqlite'
        with closing(sqlite3.connect(academic)) as db:
            db.execute('CREATE TABLE odev (id INTEGER PRIMARY KEY, completed INTEGER)')
            db.execute('INSERT INTO odev VALUES (1,0)')
            db.commit()
        before=hashlib.sha256(academic.read_bytes()).hexdigest()
        token=self.form_token()
        self.call(method='POST',params={'status':'completed_claim','reason':'other','csrf':token})
        self.assertEqual(hashlib.sha256(academic.read_bytes()).hexdigest(),before)
        self.assertNotIn(b'account17',self.path.read_bytes())

    def test_pdf_integration_absent_default_and_auth_urls_separated(self):
        days=DAYS
        schedule={d:[] for _,d in days}
        schedule[days[0][1]]=[event(sid=17,name='Deniz Test')]
        ctx={'source_state':'LOCAL_VERIFIED','student_count':1,'verified_count':1,
             'student_cards':{'17':{'verified':True,'contact_allowed':True,
                              'homework':{'total':1,'completed':0,'overdue':0}}}}
        ref1=self.ref
        ref2=self.store.issue(student_id=17,tenant_id='kurumA',teacher_id='teacher1',role='parent',verified=True)
        role_links={'17':{'student':ORIGIN+FEEDBACK_PREFIX+ref1,
                          'parent':ORIGIN+FEEDBACK_PREFIX+ref2}}
        with TemporaryDirectory() as td:
            f1=Path(td)/'default.pdf'
            kwargs={'student_message':lambda e,*args:'OGRENCI MESAJ',
                    'parent_message':lambda e,*args:'VELI MESAJ', 'academic_context':ctx}
            out=render_smart_pocket_pdf(f1,schedule,days,**kwargs)
            self.assertEqual(out['feedback_links'],0)
            f2=Path(td)/'connected.pdf'
            result=render_smart_pocket_pdf(f2,schedule,days,feedback_links=role_links,
                                           feedback_https_origin=ORIGIN,**kwargs)
            self.assertEqual(result['feedback_links'],2)
            with fitz.open(f2) as doc:
                links=[q['uri'] for p in doc for q in p.get_links() if q.get('uri')]
                self.assertIn(role_links['17']['student'],links)
                self.assertIn(role_links['17']['parent'],links)
                messages=[parse_qs(urlsplit(u).query).get('text',[''])[0]
                          for u in links if u.startswith('https://wa.me/')]
                self.assertTrue(any(role_links['17']['student'] in t for t in messages))
                self.assertTrue(any(role_links['17']['parent'] in t for t in messages))
                self.assertFalse(any(role_links['17']['parent'] in t and 'OGRENCI MESAJ' in t for t in messages))
            with fitz.open(f1) as doc:
                self.assertFalse(any(q.get('uri','').startswith(ORIGIN+FEEDBACK_PREFIX)
                                     for p in doc for q in p.get_links()))

    def test_invalid_pdf_urls_or_card_disables_feedback(self):
        card=self.context['student_cards']['17']
        card['contact_allowed']=False
        self.assertEqual(prepare_feedback_links(self.context,self.store,
                         principal=self.teacher,authorize_student=lambda *x:True,
                         recipient_eligible=lambda *x:True,
                         origin=ORIGIN,explicit_opt_in=True,deployment_ready=True),{})
        for bad in ('http://okul.eger.edu.tr/mobile/feedback/abc',
                    'https://evil.edu.tr/mobile/feedback/abc',
                    ORIGIN+'/mobile/feedback/aaa?student=17',
                    ORIGIN+'/mobile/feedback/aaa'):
            self.assertFalse(validate_feedback_pdf_link(bad,ORIGIN))


if __name__=='__main__':unittest.main()
