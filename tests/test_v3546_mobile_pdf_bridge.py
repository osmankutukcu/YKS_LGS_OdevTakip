# -*- coding: utf-8 -*-
"""V3.5.46 synthetic-only connected pocket PDF acceptance tests."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import sqlite3
import unittest
import fitz

from services.mobile_pdf_system_bridge_v3546 import collect_mobile_pdf_context
from services.smart_mobile_pdf_v3545 import render_smart_pocket_pdf
from tests.test_v3536_academic_actions import db
from tools.v3527_core_guard import audit

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026,10,18)
WEEK=[('2026-10-18','Pazar')]


def entry(sid, name='Öğrenci', phone='05551234567'):
    return {'oid':sid, 'ad':name, 'tip':'Teslim', 'saat':'18:00',
            'tel_ogr':phone, 'tel_veli':'05321112233',
            'meta':{'lines':['Fizik - Hareket'],'status':'normal'}}


class V3546BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dbfile=Path(self.tmp.name)/'students.db'
        src=db()
        with sqlite3.connect(self.dbfile) as target:
            src.backup(target)
        with sqlite3.connect(self.dbfile) as actual:
            actual.execute('ALTER TABLE ogrenci ADD COLUMN ogr_tel TEXT')
            actual.execute('UPDATE ogrenci SET ogr_tel=?, veli_tel1=? WHERE id=1',
                           ('05551234567', '05321112233'))
            actual.execute('UPDATE ogrenci SET ogr_tel=?, veli_tel1=? WHERE id=2',
                           ('05559876543', '05321112233'))
        src.close()

    def context(self, *rows, cap=40, file=None):
        return collect_mobile_pdf_context(file if file is not None else self.dbfile,
                    {'Pazar':list(rows)},WEEK,today=DAY,max_students=cap)

    def pdf(self, context, rows):
        target=Path(self.tmp.name)/'connected.pdf'
        render_smart_pocket_pdf(target, {'Pazar':list(rows)},WEEK,
            academic_context=context,
            student_message=lambda e,*args:'Ödev hatırlatması',
            parent_message=lambda e,*args:'Ödev bilgilendirmesi')
        return target

    def test_verified_local_student_uses_canonical_homework_and_real_plan(self):
        ctx=self.context(entry(1,'Test Öğrenci'))
        self.assertEqual(ctx['student_count'],1)
        self.assertEqual(ctx['verified_count'],1)
        self.assertEqual(ctx['evaluated_count'],1)
        card=ctx['student_cards']['1']
        self.assertTrue(card['verified'])
        self.assertTrue(card['contact_allowed'])
        self.assertEqual(card['homework']['total'],1)
        self.assertEqual(card['homework']['overdue'],1)
        self.assertEqual(card['coaching_plan']['state'],'READY')
        self.assertTrue(card['requires_teacher_approval'])
        self.assertFalse(ctx['messages_sent'])
        self.assertFalse(ctx['student_data_written'])

    def test_linked_owner_collision_quarantines_both_students_and_contacts(self):
        with sqlite3.connect(self.dbfile) as conn:
            conn.execute('INSERT INTO odev_satir (id, ogrenci_id, kume_id, odev_id, ders, durum) '
                         "VALUES (305,2,100,101,'Fizik','devam')")
        rows=[entry(1,'Öğrenci A'),entry(2,'Öğrenci B', '05559876543')]
        ctx=self.context(*rows)
        self.assertEqual(ctx['verified_count'],0)
        self.assertEqual(ctx['contact_blocked_count'],2)
        self.assertEqual(ctx['student_cards']['1']['state'],'LINK_REVIEW')
        docpath=self.pdf(ctx,rows)
        with fitz.open(docpath) as doc:
            links=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
            self.assertFalse(any(uri.startswith(('https://wa.me/','tel:')) for uri in links))
            text='\n'.join(p.get_text() for p in doc)
            self.assertIn('kapatıldı',text)

    def test_nonexistent_or_inactive_id_never_produces_contact_link(self):
        rows=[entry(999,'Tanımsız'),entry(3,'Pasif')]
        ctx=self.context(*rows)
        self.assertEqual(ctx['verified_count'],0)
        self.assertTrue(all(not v['contact_allowed'] for v in ctx['student_cards'].values()))
        with fitz.open(self.pdf(ctx,rows)) as doc:
            links=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
            self.assertFalse(any(x.startswith('https://wa.me/') for x in links))

    def test_unreadable_db_never_silently_certifies_any_student(self):
        rows=[entry(1)]
        ctx=self.context(*rows,file=Path(self.tmp.name)/'missing.db')
        self.assertEqual(ctx['source_state'],'UNVERIFIED')
        self.assertEqual(ctx['not_evaluated_count'],1)
        self.assertFalse(ctx['student_cards']['1']['contact_allowed'])
        with fitz.open(self.pdf(ctx,rows)) as doc:
            uris=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
            self.assertFalse(any(x.startswith(('https://wa.me/','tel:')) for x in uris))

    def test_cap_never_represents_untested_student_as_safe(self):
        ctx=self.context(entry(1),entry(2, 'İkinci', '05321117788'),cap=1)
        self.assertEqual(ctx['evaluated_count'],1)
        self.assertEqual(ctx['not_evaluated_count'],1)
        self.assertEqual(ctx['source_state'],'PARTIAL')
        self.assertFalse(ctx['student_cards']['2']['contact_allowed'])
        self.assertEqual(ctx['student_cards']['2']['state'],'NOT_EVALUATED')

    def test_invalid_ids_are_not_merged_and_have_no_contacts(self):
        ctx=self.context(entry(None),entry('invalid','Farklı'))
        self.assertEqual(ctx['student_count'],2)
        self.assertEqual(ctx['verified_count'],0)
        self.assertEqual(ctx['not_evaluated_count'],2)
        self.assertEqual(ctx['source_state'],'PARTIAL')
        with fitz.open(self.pdf(ctx,[entry(None),entry('invalid','Farklı')])) as doc:
            uris=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
            self.assertFalse(any(x.startswith('https://wa.me/') for x in uris))

    def test_pdf_contains_provenance_and_correct_student_external_links(self):
        row=entry(1,'Test Öğrenci')
        ctx=self.context(row)
        with fitz.open(self.pdf(ctx,[row])) as doc:
            text='\n'.join(p.get_text() for p in doc)
            links=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
            self.assertIn('SİSTEMLE BÜTÜNLEŞİK AKADEMİK DURUM',text)
            self.assertIn('Kanonik ödev',text)
            self.assertIn('Koçluk planı',text)
            self.assertTrue(any(x.startswith('https://wa.me/') for x in links))
            self.assertTrue(any(x.startswith('tel:') for x in links))
            self.assertFalse(any('05559998888' in x for x in links))


    def test_changed_recipient_phone_blocks_links_even_with_verified_homework(self):
        row=entry(1,phone='05559998888')
        ctx=self.context(row)
        self.assertEqual(ctx['verified_count'],1)
        self.assertFalse(ctx['student_cards']['1']['contact_allowed'])
        with fitz.open(self.pdf(ctx,[row])) as doc:
            uris=[ln['uri'] for pg in doc for ln in pg.get_links() if ln.get('uri')]
            self.assertFalse(any(x.startswith(('https://wa.me/','tel:')) for x in uris))

    def test_changed_student_name_blocks_links_with_old_schedule(self):
        row=entry(1,name='Başka Öğrenci')
        ctx=self.context(row)
        self.assertEqual(ctx['verified_count'],1)
        self.assertFalse(ctx['student_cards']['1']['contact_allowed'])

    def test_local_source_bytes_and_rows_never_modified(self):
        before=hashlib.sha256(self.dbfile.read_bytes()).hexdigest()
        ctx=self.context(entry(1))
        self.pdf(ctx,[entry(1)])
        after=hashlib.sha256(self.dbfile.read_bytes()).hexdigest()
        self.assertEqual(before,after)
        self.assertEqual(ctx['source_state'] in ('PARTIAL','LOCAL_VERIFIED'),True)

    def test_protected_forms_and_old_mobile_renderer_remain_unchanged(self):
        self.assertEqual(audit(ROOT)['status'],'PASS')
        import ast
        dialog=ast.parse((ROOT/'ui/smart_mobile_pdf_dialog_v3545.py').read_text('utf-8'))
        names={x.name for x in ast.walk(dialog) if isinstance(x,ast.FunctionDef)}
        self.assertIn('_export',names)
        self.assertIn('run',names)
        source=(ROOT/'ui/smart_mobile_pdf_dialog_v3545.py').read_text('utf-8')
        self.assertIn('collect_mobile_pdf_context',source)
        self.assertIn('academic_context=context',source)
        original=(ROOT/'ui/mobile_schedule.py').read_text('utf-8')
        self.assertNotIn('v3546',original)

    def test_bound_range_and_types_are_rejected(self):
        for limit in (0,101,True,1.0,'10'):
            with self.subTest(limit=limit),self.assertRaises(ValueError):
                self.context(entry(1),cap=limit)


if __name__=='__main__': unittest.main()
