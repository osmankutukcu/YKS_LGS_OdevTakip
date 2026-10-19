"""V3.5.43: safe long-message splitting, recipient isolation and clickable links."""
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import unittest

import fitz

from services.mobile_agenda_pdf_v3541 import (
    MAX_WHATSAPP_URL_LENGTH,
    call_url,
    normalize_mobile_number,
    render_agenda_pdf,
    whatsapp_message_parts,
    whatsapp_actions,
)


class TestLongWhatsAppMessages(unittest.TestCase):
    def test_short_message_retains_exact_content_and_single_button(self):
        message = 'Merhaba Ayşe!\nMatematik ödevi: 4 soru. 📚'
        self.assertEqual(whatsapp_message_parts(message), [message])
        actions = whatsapp_actions('05551234567', message,
                                  single_label='WhatsApp Raporu', multi_label='WhatsApp')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0][0], 'WhatsApp Raporu')
        uri = actions[0][2]
        self.assertEqual(parse_qs(urlsplit(uri).query)['text'], [message])

    def test_long_message_preserved_exactly_and_numbered(self):
        message = 'Sevgili öğrencim,\n' + ''.join(
            f'{i}: Matematik problemlerini çöz; kolay gelsin. 🎯\n' for i in range(220))
        chunks = whatsapp_message_parts(message)
        self.assertGreater(len(chunks), 3)
        self.assertEqual(
            ''.join(c.split('\n', 1)[1] for c in chunks), message)
        for i, chunk in enumerate(chunks, 1):
            self.assertTrue(chunk.startswith(f'Bölüm {i}/{len(chunks)}\n'))
            self.assertLessEqual(
                len('https://wa.me/' + '9' * 15 + '?text=' + __import__('urllib.parse').parse.quote(chunk, safe='')),
                MAX_WHATSAPP_URL_LENGTH)

    def test_no_newline_long_text_does_not_truncate(self):
        message = 'ğöşçü🔬' * 1100
        chunks = whatsapp_message_parts(message)
        self.assertGreater(len(chunks), 2)
        self.assertEqual(''.join(c.split('\n', 1)[1] for c in chunks), message)

    def test_invalid_contact_labels_cannot_turn_into_valid_number(self):
        for raw in ['Veli: 05551234567', '05551234567 dahili 23',
                    '05551234567/05443332211', '+90+5551234567',
                    '05551234567?text=merhaba']:
            self.assertIsNone(normalize_mobile_number(raw))
        for raw in ['+90 (555) 123-45-67', '0555 123 45 67', '0090 555 123 45 67']:
            self.assertEqual(normalize_mobile_number(raw), '905551234567')
        self.assertIsNone(call_url('Ara: 905551234567'))

    def test_different_student_parent_messages_and_links_in_actual_pdf(self):
        lines = [f'Fizik - Görev {i} - Örnek çözümü ve konu tekrarı' for i in range(100)]
        event = dict(tip='Teslim', ad='Deneme Öğrenci', tel_ogr='05551234567',
                     tel_veli='05321112233', saat='18:00',
                     meta={'lines': lines, 'notes': [], 'nice_date': '19.10.2026'})
        student_text = 'Öğrenciye mesaj:\n' + '\n'.join(lines)
        parent_text = 'Sayın veli,\n' + '\n'.join('Takip: ' + line for line in lines)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'agenda.pdf'
            result = render_agenda_pdf(path, {'Pazartesi': [event]},
                                       [('2026-10-19', 'Pazartesi')],
                                       student_message=lambda *_: student_text,
                                       parent_message=lambda *_: parent_text)
            with fitz.open(path) as document:
                links = [link['uri'] for page in document for link in page.get_links() if link.get('uri')]
                all_text = '\n'.join(page.get_text() for page in document)
                self.assertIn('Görev 99', all_text)
                self.assertIn('Uzun WhatsApp raporu', all_text)
                self.assertEqual(sum(x.startswith('tel:') for x in links), 2)
                self.assertEqual(result['link_annotations_expected'], len(links))
                recipients = {
                    '905551234567': student_text,
                    '905321112233': parent_text,
                }
                for phone, expected in recipients.items():
                    uris = [x for x in links if x.startswith(f'https://wa.me/{phone}?')]
                    self.assertGreater(len(uris), 1)
                    segments = [parse_qs(urlsplit(u).query)['text'][0] for u in uris]
                    self.assertEqual(''.join(x.split('\n', 1)[1] for x in segments), expected)
                    self.assertTrue(all(len(x) <= MAX_WHATSAPP_URL_LENGTH for x in uris))
                self.assertTrue(all('/905321112233?' not in uri or 'Öğrenciye mesaj' not in uri for uri in links))

    def test_very_long_agenda_stays_exportable(self):
        lines = [f'Fizik uzun ödev {i}: grafik yorumlama ve test' for i in range(800)]
        event = dict(tip='Teslim', ad='DEMO öğrenci', tel_ogr='05551234567',
                     tel_veli='05321112233', meta={'lines': lines})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'çok-uzun.pdf'
            result = render_agenda_pdf(
                path, {'Pazartesi': [event]}, [('2026-10-19', 'Pazartesi')],
                student_message=lambda *_: '\n'.join(lines),
                parent_message=lambda *_: 'Sayın veli\n' + '\n'.join(lines))
            with fitz.open(path) as pdf:
                self.assertIn('Fizik uzun ödev 799', '\n'.join(p.get_text() for p in pdf))
                self.assertGreater(len(pdf), 5)
                urls = [l['uri'] for page in pdf for l in page.get_links() if l.get('uri')]
                self.assertEqual(len(urls), result['link_annotations_expected'])
                self.assertTrue(all(len(u) <= MAX_WHATSAPP_URL_LENGTH
                                    for u in urls if u.startswith('https://wa.me/')))

    def test_invalid_phone_does_not_receive_a_message_in_pdf(self):
        event = dict(tip='Teslim', ad='Öğrenci', tel_ogr='Veli: 05551234567',
                     tel_veli='05321112233', saat='18:00', meta={'lines':['Ödev 1']})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'agenda.pdf'
            render_agenda_pdf(path, {'Pazartesi': [event]}, [('2026-10-19', 'Pazartesi')],
                              student_message=lambda *_: 'ÖĞRENCİ',
                              parent_message=lambda *_: 'VELİ')
            with fitz.open(path) as document:
                urls = [x['uri'] for p in document for x in p.get_links() if x.get('uri')]
                self.assertFalse(any('905551234567' in x for x in urls))
                wa = [x for x in urls if 'wa.me/' in x]
                self.assertEqual(len(wa), 1)
                self.assertEqual(parse_qs(urlsplit(wa[0]).query)['text'], ['VELİ'])


if __name__ == '__main__':
    unittest.main()
