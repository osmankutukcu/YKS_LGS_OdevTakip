# -*- coding: utf-8 -*-
"""Synthetic-only authorization and integration tests for V3.5.51."""
from __future__ import annotations

import ast
import hashlib
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
import gc

from services.mobile_pdf_feedback_v3550 import FeedbackInbox, RecipientPrincipal
from services.mobile_pdf_secure_portal_v3548 import TeacherPrincipal
from services.mobile_pdf_feedback_center_v3551 import FeedbackCenter, readable_time


class CenterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self._safe_cleanup)
        self.now = [100_000.0]
        self.store = FeedbackInbox(Path(self.tmp.name)/'inbox.sqlite', clock=lambda: self.now[0])
        self.teacher = TeacherPrincipal('schoolA','teacherA',self.now[0]+3600)
        self.teacher2 = TeacherPrincipal('schoolA','teacherB',self.now[0]+3600)
        self.tenantB = TeacherPrincipal('schoolB','teacherA',self.now[0]+3600)
        self.principal = [self.teacher]
        self.grants = {17,18,19}
        self.center = FeedbackCenter(self.store,principal_provider=lambda:self.principal[0],
            authorize_student=lambda p,sid: sid in self.grants,
            student_label=lambda p,sid: {17:'Ayşe Test',18:'Zeynep Test'}.get(sid))

    def _safe_cleanup(self):
        gc.collect()
        try:
            self.tmp.cleanup()
        except OSError:
            pass

    def submit(self, sid, status, *, role='student', teacher='teacherA', tenant='schoolA', reason='none'):
        ref = self.store.issue(student_id=sid,tenant_id=tenant,teacher_id=teacher,
                               role=role,verified=True,ttl_seconds=3600)
        p = RecipientPrincipal(tenant,'recipient-'+str(sid),sid,role,'session-'+str(sid),
                               self.now[0]+3600)
        self.assertTrue(self.store.submit(ref,principal=p,status=status,reason=reason))
        return self.store.teacher_inbox(principal=TeacherPrincipal(tenant,teacher,self.now[0]+3600))[0]['id']

    def test_empty_list_does_not_fake_messages(self):
        snap=self.center.snapshot()
        self.assertEqual(snap.visible_count,0)
        self.assertEqual(snap.pending_count,0)
        self.assertEqual(snap.groups,())

    def test_groups_by_student_priorities_and_sender(self):
        self.submit(17,'started')
        self.now[0]+=1
        self.submit(17,'need_help',role='parent',reason='difficult')
        self.now[0]+=1
        self.submit(18,'meeting_request')
        snap=self.center.snapshot()
        self.assertEqual(snap.pending_count,3)
        self.assertEqual(snap.groups[0]['student_id'],17)
        self.assertEqual(snap.groups[0]['label'],'Ayşe Test')
        self.assertEqual(snap.groups[0]['items'][0]['status_code'],'need_help')
        self.assertEqual(snap.groups[0]['items'][0]['recipient'],'Veli')
        self.assertEqual(snap.groups[0]['items'][0]['reason'],'Sorular zorlayıcı')
        self.assertEqual(snap.groups[1]['student_id'],18)

    def test_review_only_changes_feedback_inbox(self):
        db=Path(self.tmp.name)/'real_homework.sqlite'
        with closing(sqlite3.connect(db)) as c:
            c.execute('CREATE TABLE homework(id INTEGER PRIMARY KEY, completed INTEGER)')
            c.execute('INSERT INTO homework VALUES (1,0)')
            c.commit()
        baseline=hashlib.sha256(db.read_bytes()).digest()
        feedback=self.submit(17,'completed_claim')
        self.assertTrue(self.center.review(feedback))
        self.assertFalse(self.center.review(feedback))
        self.assertEqual(self.center.snapshot().pending_count,0)
        self.assertEqual(self.center.snapshot().reviewed_count,1)
        self.assertEqual(self.center.snapshot(include_reviewed=False).visible_count,0)
        self.assertEqual(hashlib.sha256(db.read_bytes()).digest(),baseline)

    def test_wrong_teacher_and_tenant_never_leak(self):
        self.submit(17,'need_help',teacher='teacherB')
        self.submit(18,'started',tenant='schoolB')
        self.assertEqual(self.center.snapshot().visible_count,0)
        self.principal[0]=self.teacher2
        snap=self.center.snapshot()
        self.assertEqual(snap.visible_count,1)
        self.assertEqual(snap.groups[0]['student_id'],17)
        self.principal[0]=self.tenantB
        self.assertEqual(self.center.snapshot().groups[0]['student_id'],18)

    def test_access_revoked_between_snapshot_and_review(self):
        feedback=self.submit(17,'need_help')
        self.assertEqual(self.center.snapshot().visible_count,1)
        self.grants.clear()
        self.assertEqual(self.center.snapshot().visible_count,0)
        with self.assertRaises(PermissionError): self.center.review(feedback)
        self.assertIsNone(self.store.teacher_inbox(principal=self.teacher)[0]['reviewed_at'])

    def test_no_session_or_expired_session_fails_closed(self):
        self.submit(17,'started')
        self.principal[0]=None
        with self.assertRaises(PermissionError): self.center.snapshot()
        with self.assertRaises(PermissionError): self.center.review(1)
        self.principal[0]=self.teacher
        self.now[0]+=3600
        with self.assertRaises(PermissionError): self.center.snapshot()

    def test_acl_exceptions_fail_closed(self):
        self.submit(17,'need_help')
        center=FeedbackCenter(self.store,principal_provider=lambda:self.teacher,
            authorize_student=lambda *_: 1/0)
        self.assertEqual(center.snapshot().visible_count,0)
        with self.assertRaises(PermissionError): center.review(1)

    def test_bad_principal_and_bad_constructor(self):
        with self.assertRaises(ValueError): FeedbackCenter(self.store, principal_provider=None, authorize_student=lambda *_:True)
        with self.assertRaises(ValueError): FeedbackCenter(self.store, principal_provider=lambda:self.teacher, authorize_student=None)
        with self.assertRaises(TypeError): FeedbackCenter(object(), principal_provider=lambda:self.teacher, authorize_student=lambda *_:True)
        with self.assertRaises(ValueError): self.center.snapshot(limit=0)
        with self.assertRaises(ValueError): self.center.snapshot(limit=201)
        with self.assertRaises(ValueError): self.center.review(True)

    def test_names_from_provider_not_backend_storage(self):
        self.submit(17,'started')
        self.assertNotIn(b'Ayse',self.store.path.read_bytes())
        fallback=FeedbackCenter(self.store,principal_provider=lambda:self.teacher,
                authorize_student=lambda *_:True,student_label=lambda *_: (_ for _ in ()).throw(KeyError('lookup')))
        self.assertEqual(fallback.snapshot().groups[0]['label'],'Öğrenci kaydı #17')

    def test_page_size_disclosed_as_partial(self):
        self.submit(17,'started')
        self.submit(18,'started')
        self.assertTrue(self.center.snapshot(limit=1).is_partial)
        self.assertFalse(self.center.snapshot(limit=20).is_partial)

    def test_old_ui_exports_still_have_separate_module(self):
        src=Path(__file__).resolve().parents[1]/'ui'/'smart_mobile_pdf_dialog_v3545.py'
        text=src.read_text(encoding='utf-8')
        ast.parse(text)
        self.assertIn('mobile_pdf_feedback_center_provider',text)
        self.assertIn('Öğretmen Geri Bildirim Merkezi',text)
        self.assertIn('Ayrı Mobil PDF Oluştur ve Aç',text)
        self.assertIn('_open_feedback_center',text)
        dialog=Path(__file__).resolve().parents[1]/'ui'/'mobile_pdf_feedback_center_v3551.py'
        tree=ast.parse(dialog.read_text(encoding='utf-8'))
        self.assertTrue(any(isinstance(n,ast.ClassDef) and n.name=='MobileFeedbackCenterDialog' for n in tree.body))

    def test_no_sensitive_message_details_in_snapshot(self):
        self.submit(17,'completed_claim',role='parent')
        row=self.center.snapshot().groups[0]['items'][0]
        for forbidden in ('phone','text','message','subject_id','token','invite_digest'):
            self.assertNotIn(forbidden,row)

    def test_utc_time_is_explicit(self):
        self.assertEqual(readable_time(0),'1970-01-01 00:00 UTC')


if __name__=='__main__': unittest.main()
