# -*- coding: utf-8 -*-
"""V3.5.44: Mobile PDF student directory, identity and link safety."""
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fitz

from services.mobile_agenda_pdf_v3541 import (
    _student_directory, _fit_label, render_agenda_pdf,
    normalize_mobile_number,
)
from reportlab.pdfbase import pdfmetrics
from services.mobile_agenda_pdf_v3541 import _setup_font


DAYS = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
WEEK = [((date(2026, 10, 19) + timedelta(days=i)).isoformat(), day)
        for i, day in enumerate(DAYS)]


def event(oid, name, phone='05551234567', lines=None):
    return {'oid': oid, 'ad': name, 'tip': 'Teslim', 'saat': '18:00',
            'tel_ogr': phone, 'tel_veli': '',
            'meta': {'lines': lines or ['Fizik - Hareket'], 'notes': []}}


def make_pdf(schedule, days=WEEK):
    td = tempfile.TemporaryDirectory()
    target = Path(td.name) / 'test.pdf'
    result = render_agenda_pdf(target, schedule, days,
                               student_message=lambda e, *_: 'Rapor ' + e['ad'],
                               parent_message=lambda e, *_: 'Veli ' + e['ad'])
    return td, result, target


class TestStudentDirectory(unittest.TestCase):
    def test_same_student_several_days_indexed_once_and_first_card_targeted(self):
        p = event(11, 'Zehra Çelik')
        schedule = {day: [] for day in DAYS}
        schedule['Pazartesi'] = [p]
        schedule['Perşembe'] = [event(11, 'Zehra Çelik')]
        entries, bookmarks = _student_directory(schedule, WEEK)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['count'], 2)
        self.assertEqual(bookmarks, {(0, 0): 'student_1'})
        td, result, target = make_pdf(schedule)
        try:
            with fitz.open(target) as doc:
                self.assertEqual(result['navigation_students'], 1)
                self.assertEqual(len(doc.get_toc()), 7)  # Existing day TOC unchanged
                index_text = '\n'.join(p.get_text() for p in doc[:1])
                self.assertIn('ÖĞRENCİ HIZLI ERİŞİM', index_text)
                self.assertIn('2 kayıt', index_text)
                internal = [x for x in doc[0].get_links() if x.get('kind') == fitz.LINK_GOTO]
                self.assertGreaterEqual(len(internal), 8)
                self.assertEqual(len([u for page in doc for u in page.get_links() if u.get('uri')]), 4)
        finally:
            td.cleanup()

    def test_identical_names_distinct_stable_ids_and_independent_pdf_links(self):
        schedule = {day: [] for day in DAYS}
        schedule['Pazartesi'] = [event(12, 'Deniz Yılmaz', phone='05551234567'),
                                event(22, 'Deniz Yılmaz', phone='05321112233')]
        entries, bookmarks = _student_directory(schedule, WEEK)
        self.assertEqual(len(entries), 2)
        self.assertEqual(len(set(x['key'] for x in entries)), 2)
        self.assertTrue(any('No 12' in e['label'] for e in entries))
        self.assertTrue(any('No 22' in e['label'] for e in entries))
        td, result, target = make_pdf(schedule)
        try:
            with fitz.open(target) as doc:
                txt = '\n'.join(p.get_text() for p in doc)
                self.assertIn('No 12', txt)
                self.assertIn('No 22', txt)
                # Both student index destinations are distinct, not a
                # two-row index pointing at the first same-name student.
                student_index_links = [l for l in doc[0].get_links()
                                       if l.get('kind') == fitz.LINK_GOTO]
                self.assertGreaterEqual(len(student_index_links), 9)
                student_links = student_index_links[-2:]
                self.assertEqual(len({(x['page'], round(x['to'].y, 1))
                                      for x in student_links}), 2)
                uris = [l['uri'] for pg in doc for l in pg.get_links() if l.get('uri')]
                self.assertTrue(any('/905551234567?' in x for x in uris))
                self.assertTrue(any('/905321112233?' in x for x in uris))
        finally:
            td.cleanup()

    def test_no_student_id_does_not_auto_merge_even_with_same_name_and_phone(self):
        schedule = {'Pazartesi': [event(None, 'Belirsiz Kayıt'),
                                  event(None, 'Belirsiz Kayıt')]}
        entries, bookmarks = _student_directory(schedule, WEEK[:1])
        self.assertEqual(len(entries), 2)
        self.assertTrue(all('Kimlik yok' in item['label'] for item in entries))
        self.assertNotEqual(bookmarks[(0, 0)], bookmarks[(0, 1)])

    def test_large_class_directory_paginates_without_dropping_students(self):
        schedule = {day: [] for day in DAYS}
        for i in range(1, 101):
            schedule[DAYS[i % 7]].append(event(i, f'Kayıt {i:03d}', phone=''))
        td, result, target = make_pdf(schedule)
        try:
            with fitz.open(target) as doc:
                all_text = '\n'.join(pg.get_text() for pg in doc)
                self.assertGreaterEqual(len(doc), 9)
                self.assertEqual(result['navigation_students'], 100)
                self.assertIn('Kayıt 001', all_text)
                self.assertIn('Kayıt 100', all_text)
                self.assertIn('ÖĞRENCİ DİZİNİ', all_text)
                self.assertTrue(any('ÖĞRENCİLER' in p.get_text() for p in list(doc)[1:]))
                self.assertEqual(sum(bool(l.get('uri')) for pg in doc for l in pg.get_links()), 0)
                n_internal = sum(l.get('kind') == fitz.LINK_GOTO for pg in doc for l in pg.get_links())
                self.assertGreaterEqual(n_internal, 107)  # 100 student + seven day links
        finally:
            td.cleanup()

    def test_very_long_duplicate_name_keeps_unique_prefix_and_no_overflow(self):
        _setup_font()
        schedule = {'Pazartesi': [event(101, 'Anadolu ' * 25),
                                  event(102, 'Anadolu ' * 25)]}
        entries, _ = _student_directory(schedule, WEEK[:1])
        self.assertTrue(all(e['label'].startswith('No ') for e in entries))
        for e in entries:
            fitted = _fit_label(e['label'], 'AgendaTRBold', 8.5, 150)
            self.assertTrue(fitted.startswith('No '))
            self.assertLessEqual(pdfmetrics.stringWidth(fitted, 'AgendaTRBold', 8.5), 150)
        td, result, target = make_pdf(schedule, WEEK[:1])
        try:
            with fitz.open(target) as doc:
                self.assertEqual(result['navigation_students'], 2)
                self.assertEqual(len(doc.get_toc()), 1)
        finally:
            td.cleanup()

    def test_existing_whatsapp_and_call_uris_not_changed_by_student_index(self):
        sched = {day: [] for day in DAYS}
        sched['Salı'] = [event(99, 'Şule', phone='05321112233')]
        td, result, path = make_pdf(sched)
        try:
            with fitz.open(path) as doc:
                urls = [l['uri'] for p in doc for l in p.get_links() if l.get('uri')]
                self.assertEqual(len(urls), 2)
                self.assertTrue(any(u == 'tel:+905321112233' for u in urls))
                self.assertTrue(any(u.startswith('https://wa.me/905321112233?') for u in urls))
                self.assertEqual(len(doc.get_toc()), 7)
        finally:
            td.cleanup()


if __name__ == '__main__':
    unittest.main()
