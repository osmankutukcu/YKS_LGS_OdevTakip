# -*- coding: utf-8 -*-
"""Cross-platform interactive agenda PDF; independent from PyQt window tests."""
import tempfile
from pathlib import Path
import unittest

from services.mobile_agenda_pdf_v3541 import (
    normalize_mobile_number, whatsapp_url, call_url, render_agenda_pdf
)


def make_event(*, student='0555 123 45 67', parent='0532 111 22 33',
               typ='Teslim', items=None):
    return {
        'tip': typ, 'ad': 'Ayşe Çalışkan', 'saat': '18:00',
        'tel_ogr': student, 'tel_veli': parent,
        'detay': 'Haftalık koçluk görüşmesi', 'renk': '#3b82f6',
        'meta': {'lines': ['Fizik - Ölçme ve Aydınlanma'] if items is None else items,
                 'nice_date': '19.10.2026', 'notes': ['Hataları tekrar et'], 'stats': '4/5',
                 'smart_note': 'Kontrol gerekli'},
    }


class TestAgendaLinks(unittest.TestCase):
    def test_phone_normalization(self):
        for value in ('0555 123 45 67', '+90 (555) 123 45 67', '5551234567',
                      '00905551234567', '905551234567'):
            self.assertEqual(normalize_mobile_number(value), '905551234567')
        for value in ('', None, '123', '000000000000', '05551234567?text=oops'):
            self.assertIsNone(normalize_mobile_number(value))

    def test_encoded_wa_message_and_call(self):
        self.assertIn('%C3%96dev', whatsapp_url('05551234567', 'Ödev:\nFizik'))
        self.assertEqual(call_url('05551234567'), 'tel:+905551234567')

    def _pdf(self, event):
        import fitz
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'agenda.pdf'
        count = render_agenda_pdf(
            path, {'Pazartesi': [event]}, [('2026-10-19', 'Pazartesi')],
            student_message=lambda e, d, x: f"Ödev raporu: {e['ad']}",
            parent_message=lambda e, d, x: f"Sayın veli, {e['ad']} hakkında bilgi",
        )
        doc = fitz.open(path)
        self.addCleanup(doc.close)
        links = [l.get('uri', '') for page in doc for l in page.get_links() if l.get('uri', '')]
        texts = '\n'.join(page.get_text() for page in doc)
        return count, links, texts

    def test_both_student_and_parent_actions_are_visible_and_clickable(self):
        count, links, text = self._pdf(make_event())
        self.assertEqual(count['link_annotations_expected'], 4)
        self.assertEqual(len(links), 4)
        self.assertTrue(any(x.startswith('https://wa.me/905551234567?text=') for x in links))
        self.assertTrue(any(x.startswith('https://wa.me/905321112233?text=') for x in links))
        self.assertIn('tel:+905551234567', links)
        self.assertIn('tel:+905321112233', links)
        for label in ('WhatsApp Raporu', 'Ara', 'Veliye WhatsApp', 'Veliyi Ara',
                      'Ayşe Çalışkan', 'Ölçme ve Aydınlanma'):
            self.assertIn(label, text)

    def test_parent_fallback_uses_parent_facing_message(self):
        count, links, text = self._pdf(make_event(student=''))
        self.assertEqual(count['link_annotations_expected'], 2)
        self.assertEqual(len(links), 2)
        from urllib.parse import unquote
        message = unquote(next(x for x in links if 'wa.me/' in x))
        self.assertIn('Sayın veli', message)
        self.assertNotIn('Ödev raporu:', message)

    def test_invalid_phone_does_not_create_actions(self):
        count, links, text = self._pdf(make_event(student='invalid', parent='???'))
        self.assertEqual(count['link_annotations_expected'], 0)
        self.assertEqual(links, [])
        self.assertIn('Telefon kayıtlı değil', text)

    def test_many_tasks_split_into_pages_without_losing_links(self):
        import fitz
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'long.pdf'
            entries = [f'Fizik - Uzun test {i} - Ünite 1 / Aydınlanma ve Kuvvet' for i in range(100)]
            result = render_agenda_pdf(
                p, {'Pazartesi': [make_event(items=entries)]},
                [('2026-10-19', 'Pazartesi')],
                student_message=lambda e, d, x: 'Fizik çalışma\n' + '\n'.join(e['meta']['lines']),
                parent_message=lambda e, d, x: 'Ödev bilgisi'
            )
            with fitz.open(p) as doc:
                self.assertGreater(len(doc), 1)
                all_text = '\n'.join(page.get_text() for page in doc)
                self.assertIn('Uzun test 0', all_text)
                self.assertIn('Uzun test 99', all_text)
                from urllib.parse import urlsplit, parse_qs
                uris = [link['uri'] for pg in doc for link in pg.get_links() if link.get('uri')]
                self.assertEqual(sum(x.startswith('tel:') for x in uris), 2)
                student_parts = [parse_qs(urlsplit(x).query)['text'][0]
                                 for x in uris if x.startswith('https://wa.me/905551234567?')]
                self.assertGreater(len(student_parts), 1)
                # Numbered parts preserve the entire original message without
                # silently dropping the end of a long homework report.
                reconstructed = ''.join(x.split('\n', 1)[1] for x in student_parts)
                self.assertEqual(reconstructed, 'Fizik çalışma\n' + '\n'.join(entries))
                self.assertEqual(result['link_annotations_expected'], len(uris))
                self.assertEqual(result['events'], 1)

    def test_pdf_does_not_escape_html_as_markup(self):
        _, links, text = self._pdf(make_event(items=['Matematik <script>alert(1)</script> & açı']))
        self.assertIn('<script>', text)
        self.assertEqual(len(links), 4)


if __name__ == '__main__':
    unittest.main()

# Test the current merge function without importing the PyQt window module.
# The form has intentionally not been modified; the AST isolates only this
# purely-data method for portable Linux/Windows CI testing.
class TestAgendaStudentIsolation(unittest.TestCase):
    def test_same_name_different_student_ids_never_merge(self):
        import ast
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'ui/mobile_schedule.py').read_text('utf8')
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MobileScheduleGenerator')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_merge_deadlines')
        scope = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'mobile_schedule.py', 'exec'), scope)
        class Dummy:
            COLOR_DEADLINE = '#f00'
            _merge_deadlines = scope['_merge_deadlines']
        def entry(sid, task):
            return {'tip':'Teslim','oid':sid,'ad':'Ada Yılmaz','tel_ogr':f'05{sid:09d}',
                    'tel_veli':'', 'renk':'#aaa', 'meta':{'lines':[task], 'notes':[], 'status':'steady'}}
        data = {'Pazartesi':[entry(1,'Fizik'),entry(2,'Matematik'),entry(1,'Kimya')]}
        Dummy()._merge_deadlines(data)
        self.assertEqual(len(data['Pazartesi']), 2)
        a = next(x for x in data['Pazartesi'] if x['oid']==1)
        b = next(x for x in data['Pazartesi'] if x['oid']==2)
        self.assertEqual(a['meta']['lines'],['Fizik','Kimya'])
        self.assertEqual(b['meta']['lines'],['Matematik'])
