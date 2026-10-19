# -*- coding: utf-8 -*-
"""Fail-closed synthetic tests: no real student data, TLS server or fake SSO deployed."""
from __future__ import annotations
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

from services.mobile_pdf_deployment_v3552 import (
    MobileDeploymentConfig, create_mobile_gateway, deployment_status,
)
from services.mobile_pdf_secure_portal_v3548 import TeacherPrincipal, PersistentStudentLinkStore
from services.mobile_pdf_feedback_v3550 import RecipientPrincipal, FeedbackInbox
from services.mobile_pdf_live_gateway_v3547 import PREFIX
from services.mobile_pdf_feedback_v3550 import FEEDBACK_PREFIX


class MobileDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.db = self.base/'academic_snapshot.sqlite'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT)')
        self.now = [10000.0]
        self.last_sync = [10000.0]
        self.config = MobileDeploymentConfig('https://portal.school.edu.tr',self.db,
                          self.base/'private-links.sqlite', self.base/'private-feedback.sqlite', b'k'*32,900)
        self.teacher = TeacherPrincipal('schoolA','teacher1',20000.)
        self.recipient = RecipientPrincipal('schoolA','parent1',17,'parent','session-1',20000.)
        self.teacher_acl = lambda p,s: p.tenant_id=='schoolA' and s==17
        self.recipient_acl = lambda p,s,r: p.tenant_id=='schoolA' and s==17 and r=='parent'
        self.kw=dict(teacher_session=lambda env:self.teacher,
                     recipient_session=lambda env:self.recipient,
                     authorize_teacher_student=self.teacher_acl,
                     authorize_recipient=self.recipient_acl,
                     desktop_teacher_session=lambda:self.teacher,
                     last_confirmed_sync=lambda:self.last_sync[0],
                     card_reader=lambda sid:('Demo Öğrenci',{'verified':True,'homework':{'total':2,'overdue':1},'summary':'Ödev kontrolü'}),
                     clock=lambda:self.now[0],
                     explicit_opt_in=True,trusted_https_ready=True,
                     identity_provider_verified=True,school_acl_verified=True,
                     server_snapshot_sync_verified=True)

    def runtime(self, **changes):
        return create_mobile_gateway(self.config,**(self.kw|changes))

    def invoke(self, app, path='/',method='GET',scheme='https',host='portal.school.edu.tr',
               body=b'', extra=None):
        seen=[]
        env={'wsgi.url_scheme':scheme, 'HTTP_HOST':host, 'REQUEST_METHOD':method,
             'PATH_INFO':path,'wsgi.input':io.BytesIO(body),'CONTENT_LENGTH':str(len(body))}
        env.update(extra or {})
        def respond(status,headers):seen.extend([status,dict(headers)])
        reply=b''.join(app(env,respond))
        return seen[0],seen[1],reply

    def test_default_off_creates_no_database_and_no_feedback_provider(self):
        runtime=create_mobile_gateway(self.config)
        self.assertFalse(runtime.enabled)
        self.assertIsNone(runtime.teacher_feedback_provider)
        self.assertEqual(self.invoke(runtime.app)[0],'503 Service Unavailable')
        self.assertFalse(self.config.link_registry.exists())
        self.assertFalse(self.config.feedback_registry.exists())

    def test_every_attestation_is_required(self):
        flags=('explicit_opt_in','trusted_https_ready','identity_provider_verified',
               'school_acl_verified','server_snapshot_sync_verified')
        for name in flags:
            with self.subTest(flag=name):
                self.assertFalse(self.runtime(**{name:False}).enabled)

    def test_no_fake_session_callbacks_or_insecure_db_paths(self):
        for name in ('teacher_session','recipient_session','authorize_teacher_student',
                     'authorize_recipient','desktop_teacher_session','last_confirmed_sync'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.runtime(**{name:None})
        with self.assertRaises(ValueError):
            MobileDeploymentConfig(self.config.origin,self.db,self.db,self.base/'other.sqlite',b'k'*32)
        with self.assertRaises(ValueError):
            MobileDeploymentConfig(self.config.origin,self.db,self.base/'a.sqlite',self.base/'b.sqlite',b'weak')
        with self.assertRaises(ValueError):
            MobileDeploymentConfig('http://portal.school.edu.tr',self.db,self.base/'a',self.base/'b',b'k'*32)

    def test_snapshot_unavailable_or_stale_fails_closed(self):
        self.now[0]+=2000
        self.assertFalse(deployment_status(self.config,last_confirmed_sync=self.kw['last_confirmed_sync'],now=self.now[0])['snapshot_fresh'])
        stale=lambda:self.now[0]-2000
        self.assertFalse(deployment_status(self.config,last_confirmed_sync=stale,now=self.now[0])['ready_for_traffic'])
        with self.assertRaises(RuntimeError):self.runtime(last_confirmed_sync=stale)
        self.db.write_bytes(b'not sqlite')
        with self.assertRaises(RuntimeError):self.runtime()

    def test_live_card_belongs_only_to_authenticated_teacher(self):
        runtime=self.runtime()
        links=PersistentStudentLinkStore(self.config.link_registry,clock=lambda:self.now[0])
        ref=links.issue(student_id=17,tenant_id='schoolA',teacher_id='teacher1',verified=True,ttl_seconds=600)
        path=PREFIX+ref
        status,headers,body=self.invoke(runtime.app,path)
        self.assertEqual(status,'200 OK')
        self.assertIn(b'2',body)
        self.assertIn('no-store',headers['Cache-Control'])
        self.assertEqual(self.invoke(runtime.app,path,scheme='http')[0],'403 Forbidden')
        self.assertEqual(self.invoke(runtime.app,path,host='evil.edu.tr')[0],'403 Forbidden')
        self.assertEqual(self.invoke(runtime.app,path,method='POST')[0],'405 Method Not Allowed')
        wrong=TeacherPrincipal('schoolB','teacher1',20000.)
        app=self.runtime(teacher_session=lambda env:wrong).app
        self.assertEqual(self.invoke(app,path)[0],'404 Not Found')
        self.assertEqual(self.invoke(self.runtime(authorize_teacher_student=lambda *_:False).app,path)[0],'403 Forbidden')

    def test_gateway_denies_stale_snapshot_on_every_request(self):
        runtime=self.runtime()
        ref=PersistentStudentLinkStore(self.config.link_registry,clock=lambda:self.now[0]).issue(
            student_id=17,tenant_id='schoolA',teacher_id='teacher1',verified=True)
        self.assertEqual(self.invoke(runtime.app,PREFIX+ref)[0],'200 OK')
        self.now[0]+=901
        self.assertEqual(self.invoke(runtime.app,PREFIX+ref)[0],'503 Service Unavailable')

    def test_feedback_form_parent_scope_and_inbox_integration(self):
        runtime=self.runtime()
        store=FeedbackInbox(self.config.feedback_registry,clock=lambda:self.now[0])
        ref=store.issue(student_id=17,tenant_id='schoolA',teacher_id='teacher1',role='parent',verified=True)
        uri=FEEDBACK_PREFIX+ref
        status,headers,body=self.invoke(runtime.app,uri)
        self.assertEqual(status,'200 OK')
        import re
        match=re.search(rb'name="csrf" value="([0-9a-f]+)"',body)
        self.assertIsNotNone(match)
        encoded=urlencode({'status':'need_help','reason':'difficult','csrf':match.group(1).decode()}).encode()
        status,_,_=self.invoke(runtime.app,uri,method='POST',body=encoded,
                extra={'CONTENT_TYPE':'application/x-www-form-urlencoded','HTTP_ORIGIN':self.config.origin})
        self.assertEqual(status,'200 OK')
        self.assertEqual(self.invoke(runtime.app,uri)[0],'409 Conflict')
        center=runtime.teacher_feedback_provider()
        self.assertEqual(center.snapshot().pending_count,1)
        response_id=center.snapshot().groups[0]['items'][0]['id']
        self.assertTrue(center.review(response_id))
        self.assertEqual(center.snapshot().pending_count,0)
        self.assertEqual(self.invoke(runtime.app,uri,method='POST',body=encoded,
             extra={'CONTENT_TYPE':'application/x-www-form-urlencoded','HTTP_ORIGIN':self.config.origin})[0], '409 Conflict')

    def test_wrong_student_and_expired_recipient_deny(self):
        runtime=self.runtime()
        ref=FeedbackInbox(self.config.feedback_registry,clock=lambda:self.now[0]).issue(
            student_id=17,tenant_id='schoolA',teacher_id='teacher1',role='parent',verified=True)
        unauthorized=RecipientPrincipal('schoolB','parent1',17,'parent','sess1',20000)
        denied=self.runtime(recipient_session=lambda env:unauthorized)
        self.assertEqual(self.invoke(denied.app,FEEDBACK_PREFIX+ref)[0],'403 Forbidden')
        denied=self.runtime(recipient_session=lambda env:RecipientPrincipal('schoolA','kid1',17,'student','sess2',20000))
        self.assertEqual(self.invoke(denied.app,FEEDBACK_PREFIX+ref)[0],'403 Forbidden')

    def test_teacher_provider_does_not_create_session_from_pdf(self):
        runtime=self.runtime(desktop_teacher_session=lambda:None)
        with self.assertRaises(PermissionError):runtime.teacher_feedback_provider().snapshot()

    def test_unknown_routes_no_data_and_strict_method(self):
        runtime=self.runtime()
        result=self.invoke(runtime.app,'/private/academic.sqlite')
        self.assertEqual(result[0],'404 Not Found')
        self.assertNotIn(b'Demo',result[2])


if __name__=='__main__':
    unittest.main()
