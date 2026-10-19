# -*- coding: utf-8 -*-
"""V3.5.42: PDF internal navigation + iPhone-facing layout regression checks."""
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import fitz
from services.mobile_agenda_pdf_v3541 import render_agenda_pdf


class TestMobileAgendaV3542(unittest.TestCase):
    def _make(self, long=False, no_phone=False):
        names = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
        days = [((date(2026, 10, 19) + timedelta(days=i)).isoformat(), x) for i, x in enumerate(names)]
        ev = {'oid': 55, 'ad': 'Test Öğrencisi', 'tip': 'Teslim', 'saat': '18:00',
              'tel_ogr': '' if no_phone else '05551234567', 'tel_veli': '',
              'meta': {'lines': [f'Fizik - Problem {i}' for i in range(100 if long else 2)],
                       'nice_date': '19.10.2026', 'notes': []}}
        schedule = {x: [ev] if x == 'Pazartesi' else [] for x in names}
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'ajanda.pdf'
        result = render_agenda_pdf(path, schedule, days,
                     student_message=lambda *x: 'Fizik ödevi',
                     parent_message=lambda *x: 'Veli bilgilendirmesi')
        doc = fitz.open(path)
        self.addCleanup(doc.close)
        return result, doc

    def test_seven_day_index_creates_explicit_internal_destinations(self):
        result, doc = self._make()
        self.assertEqual(result['navigation_days'], 7)
        self.assertEqual(len(doc.get_toc()), 7)
        links = [l for page in doc for l in page.get_links()]
        goto = [l for l in links if l.get('kind') in (fitz.LINK_GOTO, fitz.LINK_NAMED)]
        self.assertGreaterEqual(len(goto), 7)
        self.assertIn('HAFTALIK HIZLI ERİŞİM', doc[0].get_text())
        for day in ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']:
            self.assertTrue(any(day in toc[1] for toc in doc.get_toc()))
        # Multiple days may share one page. Links must jump to a precise
        # vertical position, not just to the page top.
        index_links = [l for l in doc[0].get_links() if l.get('kind') == fitz.LINK_GOTO]
        self.assertGreaterEqual(len(index_links), 7)
        self.assertGreater(len({round(l['to'].y) for l in index_links[:4]}), 1)


    def test_external_student_actions_survive_internal_navigation(self):
        result, doc = self._make()
        uris = [ln['uri'] for page in doc for ln in page.get_links() if ln.get('uri')]
        self.assertEqual(result['link_annotations_expected'], 2)
        self.assertEqual(len(uris), 2)
        self.assertTrue(any('wa.me/905551234567' in x for x in uris))
        self.assertTrue(any(x == 'tel:+905551234567' for x in uris))

    def test_missing_phone_does_not_accidentally_create_external_link(self):
        result, doc = self._make(no_phone=True)
        self.assertEqual(result['link_annotations_expected'], 0)
        self.assertEqual([l['uri'] for p in doc for l in p.get_links() if l.get('uri')], [])
        self.assertGreaterEqual(len([l for p in doc for l in p.get_links()]), 7)

    def test_student_actions_appear_before_long_homework_list(self):
        result, doc = self._make(long=True)
        self.assertGreater(len(doc), 2)
        first = doc[0]
        student_name = first.search_for('Test Öğrencisi')
        action = first.search_for('WhatsApp Raporu')
        first_task = first.search_for('Fizik - Problem 0')
        self.assertTrue(student_name and action and first_task)
        self.assertLess(student_name[0].y0, action[0].y0)
        self.assertLess(action[0].y0, first_task[0].y0)
        text = '\n'.join(page.get_text() for page in doc)
        self.assertIn('Problem 99', text)
        self.assertEqual(sum(bool(l.get('uri')) for p in doc for l in p.get_links()), 2)

    def test_non_first_pages_have_navigate_back_to_week_link(self):
        _, doc = self._make()
        self.assertGreaterEqual(len(doc), 2)
        for page in list(doc)[1:]:
            self.assertIn('HAFTAYA DÖN', page.get_text())
            self.assertTrue(any(l.get('kind') in (fitz.LINK_GOTO, fitz.LINK_NAMED) for l in page.get_links()))


if __name__ == '__main__':
    unittest.main()
