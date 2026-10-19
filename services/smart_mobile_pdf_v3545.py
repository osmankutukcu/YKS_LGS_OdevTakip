# -*- coding: utf-8 -*-
"""V3.5.45 - Standalone, read-only, interactive pocket academic PDF.

No dependence on Qt widgets, no writes, no network requests, no PDF JavaScript.
The original mobile agenda PDF remains an independent export path.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable, KeepTogether, CondPageBreak
from reportlab.pdfbase import pdfmetrics

from services.mobile_agenda_pdf_v3541 import (
    _setup_font, whatsapp_actions, call_url, AgendaBookmark, normalize_mobile_number,
)

NAVY = colors.HexColor('#132950')
BLUE = colors.HexColor('#2455b9')
INK = colors.HexColor('#1a2b43')
MUTED = colors.HexColor('#586a83')
EDGE = colors.HexColor('#dfe7f1')
PALE = colors.HexColor('#f4f7fc')
ORANGE = colors.HexColor('#ab5a06')
GREEN = colors.HexColor('#137d55')
PAGE = A5


def _xml(value):
    return escape('' if value is None else str(value))


def _trim(value, n=120):
    value = str(value or '').strip().replace('\n', ' ')
    return value if len(value) <= n else value[:n-1].rstrip() + '…'


def _verified_identifier(value):
    """Only positive integer IDs can be treated as stable student identities.

    A contact row with no trusted ID must remain visible in the printed diary,
    but must never acquire WhatsApp/call actions from that row alone.
    """
    if isinstance(value, bool):
        return None
    raw = str(value).strip() if value is not None else ''
    if not raw or not raw.isascii() or not raw.isdecimal():
        return None
    number = int(raw)
    return str(number) if number > 0 else None


def _normalized_student_name(value):
    return ' '.join(str(value or '').split()).casefold()


def build_pocket_snapshot(schedule, next_7_days):
    """Deterministic evidence-only summary of existing read-only schedule data.

    Students are keyed by the actual ID. Missing IDs never get merged by name.
    Repeated records for one day are retained, but counts are event counts.
    No 'learning success' or exam result is inferred from homework completion.
    """
    students, events_by_day = {}, []
    for di, (day_iso, day_name) in enumerate(next_7_days):
        evs = schedule.get(day_name, ()) or ()
        day_rows = []
        for ei, original in enumerate(evs):
            if not isinstance(original, dict):
                continue
            ev = dict(original)
            ev['meta'] = dict(original.get('meta') or {})
            sid = _verified_identifier(ev.get('oid'))
            identity = ('id', sid) if sid is not None else ('no-id', di, ei)
            if identity not in students:
                students[identity] = {
                    'key': f'pocket_student_{len(students)+1}',
                    'name': _trim(ev.get('ad') or 'Öğrenci adı yok', 90),
                    'id': sid,
                    'events': [],
                    'phone': ev.get('tel_ogr'), 'parent_phone': ev.get('tel_veli'),
                    'contact_conflict': False,
                    'identity_conflict': False,
                }
            student = students[identity]
            # A reused or corrupted student ID can contain multiple names.
            # Do not issue a single recipient's message from ambiguous identity.
            current_name = _normalized_student_name(ev.get('ad'))
            first_name = _normalized_student_name(student['name'])
            if current_name and first_name and current_name != first_name:
                student['identity_conflict'] = True
            # A conflicting number for the same student must be verified;
            # never choose a potentially wrong WhatsApp recipient silently.
            for saved, actual in (('phone', 'tel_ogr'), ('parent_phone', 'tel_veli')):
                old_num = normalize_mobile_number(student[saved])
                new_num = normalize_mobile_number(ev.get(actual))
                if old_num and new_num and old_num != new_num:
                    student['contact_conflict'] = True
                elif not old_num and new_num:
                    student[saved] = ev.get(actual)
            ev['_day_date'], ev['_day_name'] = day_iso, day_name
            student['events'].append(ev)
            day_rows.append((student['key'], ev))
        events_by_day.append((day_iso, day_name, day_rows))
    students = list(students.values())
    students.sort(key=lambda s: (s['name'].casefold().translate(str.maketrans('ıİğĞşŞçÇöÖüÜ', 'iIgGsScCoOuU')), s['id'] or '', s['key']))
    name_counts = Counter(s['name'].casefold() for s in students)
    for s in students:
        s['display_name'] = (f'No {s["id"]} · {s["name"]}' if s['id'] else
                             f'Kimlik doğrulanmadı · {s["name"]}') if name_counts[s['name'].casefold()] > 1 else s['name']
        deadlines = [ev for ev in s['events'] if ev.get('tip') == 'Teslim']
        meetings = [ev for ev in s['events'] if ev.get('tip') == 'Görüşme']
        courses = Counter()
        for ev in deadlines:
            for line in ev.get('meta', {}).get('lines') or []:
                course = str(line).split(' - ', 1)[0].strip()
                if course:
                    courses[_trim(course, 36)] += 1
        s['deadlines'], s['meetings'] = len(deadlines), len(meetings)
        s['subjects'] = courses.most_common(3)
        s['attention'] = bool(any(ev.get('meta', {}).get('status') == 'risk' for ev in s['events']))
        # Legacy 'risk' is only a sign to verify existing records, not a diagnosis.
        s['next_step'] = ('Ödev kayıtları ve teslim durumunu kontrol edin.' if s['attention']
                          else ('Yaklaşan teslim ve görüşme hazırlığını kontrol edin.'
                                if s['events'] else 'Bu hafta için kayıt bulunamadı.'))
    return {
        'students': students, 'days': events_by_day,
        'student_count': len(students),
        'deadline_count': sum(s['deadlines'] for s in students),
        'meeting_count': sum(s['meetings'] for s in students),
        'attention_count': sum(bool(s['attention']) for s in students),
    }


class JumpChip(Flowable):
    """Tap-friendly true PDF GoTo/URI annotations; no JavaScript."""
    def __init__(self, rows, *, font='AgendaTRBold', height=29, background='#f1f6ff'):
        super().__init__()
        self.rows, self.font, self.row_height = rows, font, height
        self.background, self.positions = background, []

    def wrap(self, available_width, available_height):
        self.width, self.positions = available_width, []
        col_width = (available_width - 9) / 2
        for i, (label, kind, target) in enumerate(self.rows):
            col, row = i % 2, i // 2
            self.positions.append((col * (col_width+9), row, col_width, str(label), kind, target))
        self.height = ((len(self.rows)+1)//2) * (self.row_height+6)
        return self.width, self.height

    def draw(self):
        c = self.canv
        for x, row, width, label, kind, target in self.positions:
            y = self.height - row * (self.row_height+6) - self.row_height
            c.setFillColor(colors.HexColor(self.background))
            c.setStrokeColor(EDGE)
            c.roundRect(x, y, width, self.row_height, 6, stroke=1, fill=1)
            c.setFillColor(BLUE)
            c.setFont(self.font, 8.2)
            from services.mobile_agenda_pdf_v3541 import _fit_label
            c.drawString(x+8, y+(self.row_height-8.2)/2+1, _fit_label(label, self.font, 8.2, width-16))
            if kind == 'goto':
                c.linkRect('', target, Rect=(x,y,x+width,y+self.row_height), relative=1, thickness=0)
            elif kind == 'url':
                c.linkURL(target, rect=(x,y,x+width,y+self.row_height), relative=1, thickness=0)


def calendar_meeting_url(day_iso, time_text):
    """Privacy-conscious calendar draft, with no student name or personal data."""
    try:
        date_obj = dt.date.fromisoformat(str(day_iso))
        if not re.fullmatch(r'\d{2}:\d{2}', str(time_text or '')):
            return None
        hour, minute = map(int, time_text.split(':'))
        start = dt.datetime.combine(date_obj, dt.time(hour, minute))
        end = start + dt.timedelta(minutes=30)
    except (TypeError, ValueError):
        return None
    query = urllib.parse.urlencode({
        'action': 'TEMPLATE', 'text': 'Koçluk görüşmesi',
        'dates': f'{start:%Y%m%dT%H%M%S}/{end:%Y%m%dT%H%M%S}',
    })
    return 'https://calendar.google.com/calendar/render?' + query


def _styles(font, bold):
    return {
        'hero': ParagraphStyle('spHero', fontName=bold, fontSize=16, leading=21, textColor=colors.white),
        'sub': ParagraphStyle('spSub', fontName=font, fontSize=9, leading=14, textColor=colors.HexColor('#c7dbfd')),
        'heading': ParagraphStyle('spHeading', fontName=bold, fontSize=11, leading=16, textColor=NAVY, spaceAfter=4),
        'student': ParagraphStyle('spStudent', fontName=bold, fontSize=12, leading=16, textColor=NAVY),
        'body': ParagraphStyle('spBody', fontName=font, fontSize=9, leading=13, textColor=INK),
        'small': ParagraphStyle('spSmall', fontName=font, fontSize=8, leading=11.5, textColor=MUTED),
        'tag': ParagraphStyle('spTag', fontName=bold, fontSize=9, leading=13, textColor=BLUE),
        'warning': ParagraphStyle('spWarning', fontName=font, fontSize=7.8, leading=11.5, textColor=ORANGE),
    }


def _footer(c, doc, font):
    c.saveState()
    c.setStrokeColor(EDGE)
    c.line(24, 26, PAGE[0]-24, 26)
    c.setFont(font, 7)
    c.setFillColor(MUTED)
    c.drawString(24, 16, 'KoçPilot 360 · Statik PDF')
    c.drawRightString(PAGE[0]-24, 16, str(doc.page))
    if doc.page > 1:
        c.setFillColor(BLUE)
        c.drawCentredString(PAGE[0]/2, 16, 'ANA SAYFA')
        c.linkRect('', 'pocket_home', Rect=(PAGE[0]/2-35, 10, PAGE[0]/2+35, 25), relative=0, thickness=0)
    c.restoreState()


def render_smart_pocket_pdf(path, schedule, next_7_days, *, student_message, parent_message,
                            academic_context=None, live_links=None, live_https_origin=None,
                            feedback_links=None, feedback_https_origin=None):
    """Create separate A5 interactive app-like PDF, atomically.

    PDF contains offline pages and links. WhatsApp URI only prepares a draft.
    No internal PDF widget claims to update live student records.
    """
    import tempfile
    font, bold = _setup_font()
    css = _styles(font, bold)
    snap = build_pocket_snapshot(schedule, next_7_days)
    # Offline-first default. Only explicitly authenticated HTTPS gateway may supply
    # current-data links; no bearer credentials/student IDs are in the PDF URI.
    safe_live_links = {}
    if live_links and live_https_origin and academic_context is not None:
        from services.mobile_pdf_live_gateway_v3547 import validate_pdf_live_link
        for sid, url in live_links.items():
            card = (academic_context.get("student_cards") or {}).get(str(sid))
            if card and card.get("verified") and validate_pdf_live_link(url, live_https_origin):
                safe_live_links[str(sid)] = url
    # Two-way response links are NEVER fabricated. An externally authenticated
    # deployment may inject URLs after student/parent ACL checks. The PDF alone
    # is not a credential; each recipient must independently sign in.
    safe_feedback_links = {}
    if feedback_links and feedback_https_origin and academic_context is not None:
        from services.mobile_pdf_feedback_v3550 import validate_feedback_pdf_link
        for sid, audience_links in feedback_links.items():
            card = (academic_context.get('student_cards') or {}).get(str(sid))
            if not (isinstance(card, dict) and card.get('verified') and card.get('contact_allowed')):
                continue
            if not isinstance(audience_links, dict):
                continue
            allowed = {}
            for role in ('student', 'parent'):
                url = audience_links.get(role)
                if isinstance(url, str) and validate_feedback_pdf_link(url, feedback_https_origin):
                    allowed[role] = url
            if allowed:
                safe_feedback_links[str(sid)] = allowed
    path = Path(path)
    if not path.parent.is_dir():
        raise FileNotFoundError('PDF kayıt klasörü bulunamadı.')
    if not next_7_days:
        raise ValueError('Ajandada gün listesi bulunamadı.')
    width = PAGE[0]-48
    story = [AgendaBookmark('pocket_home')]
    hero = Table([[
        Paragraph('AKILLI MOBİL PDF ASİSTANI', css['hero'])],
        [Paragraph('Seçilen dönemin akademik kontrolü · mobil hızlı işlemler', css['sub'])]
    ], colWidths=[width])
    hero.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), NAVY),
        ('LEFTPADDING',(0,0),(-1,-1),14), ('RIGHTPADDING',(0,0),(-1,-1),14),
        ('TOPPADDING',(0,0),(-1,0),12),('BOTTOMPADDING',(0,-1),(-1,-1),13),
    ]))
    story += [hero, Spacer(1,10)]
    now_str = dt.datetime.now().strftime('%d.%m.%Y %H:%M')
    story += [Paragraph(f'<b>Oluşturulma:</b> {_xml(now_str)}', css['small']),Spacer(1,8)]
    metrics = [('Öğrenci', snap['student_count']), ('Teslim kaydı', snap['deadline_count']),
               ('Görüşme', snap['meeting_count']), ('Kontrol işareti', snap['attention_count'])]
    row = [Paragraph(f'<b>{n}</b><br/>{_xml(label)}', css['tag']) for label,n in metrics]
    stats = Table([row], colWidths=[width/4]*4)
    stats.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1), PALE),('BOX',(0,0),(-1,-1),.5,EDGE),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    story += [stats, Spacer(1,11)]
    if academic_context is not None:
        status = academic_context.get('source_state', 'UNVERIFIED')
        checked = academic_context.get('verified_count', 0)
        total = academic_context.get('student_count', 0)
        story.append(Paragraph('SİSTEMLE BÜTÜNLEŞİK AKADEMİK DURUM', css['heading']))
        story.append(Paragraph(_xml(f'Kaynak: yerel ödev / sınav / koçluk / müdahale kayıtları. '
                               f'Doğrulanan öğrenci: {checked}/{total}. Kapsam: {status}.'), css['body']))
        story.append(Paragraph('PDF oluşturulduğu andaki veriyi taşır. Sınav değişimi öğrenme tanısı veya '
                               'bir müdahalenin işe yaradığının kanıtı değildir.', css['small']))
        story.append(Paragraph('Bu çıktı yerel kayıtlara dayanır; öğrenci/veri bağlantısı doğrulanmazsa iletişim kısayolları kapatılır.', css['small']))
        for warning in academic_context.get('warnings',[])[:3]:
            story.append(Paragraph('• '+_xml(_trim(warning,220)),css['warning']))
        story.append(Spacer(1,10))
    story.append(Paragraph('DÖNEMİN AKADEMİK ÖZETİ', css['heading']))
    if snap['attention_count']:
        story.append(Paragraph(f'{snap["attention_count"]} öğrencinin mevcut ödev rozetinde dikkat işareti var. Bu bir öğrenme tanısı değildir; gerçek ödev durumunu öğretmen kontrol etmelidir.', css['warning']))
    else:
        story.append(Paragraph('Bu dönem görünümünde dikkat rozeti tespit edilmedi. Bu, tüm öğrenci kayıtlarının sorunsuz olduğu anlamına gelmez.', css['body']))
    attention = [s for s in snap['students'] if s['attention']]
    if attention:
        story += [Spacer(1,8), Paragraph('ÖNCELİKLİ KONTROL', css['heading'])]
        story.append(JumpChip([(_trim(s['display_name'],38), 'goto', s['key'])
                               for s in attention[:6]], height=27, background='#fff4e9'))
        if len(attention) > 6:
            story.append(Paragraph(f'+ {len(attention)-6} öğrenci daha. Tam liste için Öğrenci Hızlı Erişim bölümüne bakın.', css['small']))
    story += [Spacer(1,10), Paragraph('DÖNEM GÜNLERİ', css['heading'])]
    day_links = []
    for i, (day_iso, day_name, evs) in enumerate(snap['days']):
        day_links.append((f'{day_name} · {len(evs)} kayıt', 'goto', f'pocket_day_{i}'))
    # V3.5.53: 10/14-day menus must split naturally across A5 pages.
    # A single unsplittable 14-day grid previously left the first PDF page
    # almost empty. Keep all the existing named day destinations unchanged.
    for offset in range(0, len(day_links), 7):
        story.append(JumpChip(day_links[offset:offset+7]))
        story.append(Spacer(1, 5 if offset+7 < len(day_links) else 12))
    if snap['students']:
        # Keep the directory title on the same page as its first entry.
        for start in range(0, len(snap['students']), 16):
            chunk = JumpChip([(_trim(s['display_name'],40), 'goto', s['key'])
                              for s in snap['students'][start:start+16]], height=31)
            if start == 0:
                story.append(KeepTogether([Paragraph('ÖĞRENCİ HIZLI ERİŞİM', css['heading']),
                                           Spacer(1,5), chunk]))
            else:
                story.extend([chunk, Spacer(1,5)])
    else:
        story += [Paragraph('ÖĞRENCİ HIZLI ERİŞİM', css['heading']),
                  Paragraph('Bu seçim için kayıt bulunamadı.', css['body'])]
    if academic_context is not None:
        if safe_live_links:
            story.append(Paragraph('CANLI AKADEMİK KART: Yalnızca doğrulanmış erişimler için süreli bağlantı hazırdır. Açarken oturum açmanız gerekebilir.', css['small']))
        else:
            story.append(Paragraph('CANLI AKADEMİK KART: Güvenli HTTPS ve öğretmen oturumu henüz yapılandırılmadığından canlı bağlantılar kapalıdır; bu PDF çevrimdışı kullanılabilir.', css['small']))
    if academic_context is not None and not safe_feedback_links:
        story.append(Paragraph('ÇİFT YÖNLÜ TAKİP: Öğrenci/veli yanıt bağlantıları gerçek HTTPS ve kimlik doğrulamalı alıcı oturumları kurulana kadar kapalıdır. PDF içindeki WhatsApp/Ara işlevleri etkilenmez.', css['small']))
    elif safe_feedback_links:
        story.append(Paragraph('ÇİFT YÖNLÜ TAKİP: Yetkili öğrenci veya veli kendisine gönderilen süreli bağlantıdan oturum açarak durum bildirebilir. Bu bildirim yalnızca öğretmen inceleme kuyruğuna alınır.', css['small']))
    story += [Spacer(1,10), Paragraph('BELGE KULLANIMI', css['heading']),
              Paragraph('Öğrenciye veya güne dokunarak PDF içinde ilerleyin. WhatsApp düğmeleri yalnızca mesaj taslağı açar; gönderim sizin onayınızla yapılır. Ara düğmesi telefon uygulamasını açabilir. PDF çevrimdışı görüntülenir, fakat içindeki akademik bilgiler kendiliğinden güncellenmez.', css['small']), Spacer(1,15)]
    student_key = {s['key']: s for s in snap['students']}
    from services.offline_pdf_message_center_v3549 import prepare_offline_message_pack, MESSAGE_KINDS
    message_hubs = []
    anchored_students=set()
    action_count=0
    for di, (day_iso, day_name, rows) in enumerate(snap['days']):
        story += [AgendaBookmark(f'pocket_day_{di}'),
                  Paragraph(f'{_xml(day_name).upper()} · {_xml(day_iso)}', css['heading']),
                  Spacer(1,5)]
        if not rows:
            story += [Paragraph('Planlanmış teslim veya görüşme bulunmuyor.', css['small']), Spacer(1,14)]
            continue
        for key, ev in rows:
            s = student_key[key]
            if key not in anchored_students:
                story.append(AgendaBookmark(key))
                anchored_students.add(key)
                # Student-scoped period message hub is generated only once.
                if s['id'] is not None:
                    message_hubs.append(s)
            typ = str(ev.get('tip') or 'Kayıt')
            meta = ev.get('meta') or {}
            title = Paragraph(_xml(s['display_name']), css['student'])
            badge = 'TESLİM' if typ == 'Teslim' else ('GÖRÜŞME' if typ == 'Görüşme' else _xml(typ))
            time_text = _trim(ev.get('saat') or '', 20)
            top = Table([[title, Paragraph(f'{badge}<br/>{_xml(time_text)}', css['tag'])]],
                        colWidths=[width*.65, width*.35])
            top.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1), PALE),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),7),
                ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
            story.extend([top, Spacer(1,4)])
            summary = f'{s["deadlines"]} teslim kaydı · {s["meetings"]} görüşme'
            story.append(Paragraph(_xml(summary), css['small']))
            if s['subjects']:
                story.append(Paragraph('Konular: '+_xml(', '.join(k for k,_ in s['subjects'])), css['small']))
            integration = None
            if academic_context is not None and s['id'] is not None and not s['identity_conflict']:
                integration = academic_context.get('student_cards', {}).get(str(s['id']))
            if integration is not None:
                state = integration.get('state', 'UNVERIFIED')
                story.append(Paragraph('Sistem özeti: '+_xml(_trim(integration.get('summary'),260)),
                                        css['warning'] if state in ('LINK_REVIEW','UNVERIFIED','NOT_EVALUATED') else css['body']))
                if integration.get('verified'):
                    hw = integration.get('homework') or {}
                    if hw.get('total') is not None:
                        story.append(Paragraph(_xml(f'Kanonik ödev: {hw.get("total")} kayıt; tamamlanan {hw.get("completed")}; süresi geçen açık {hw.get("overdue")}.'),css['small']))
                    plan = integration.get('coaching_plan') or {}
                    if plan.get('summary'):
                        story.append(Paragraph('Koçluk planı: '+_xml(_trim(plan['summary'],175)),css['small']))
                    exam = integration.get('exam') or {}
                    for signal in exam.get('signals',[])[:2]:
                        course = str(signal.get('course') or 'Ders')[:60]
                        delta = signal.get('net_delta')
                        story.append(Paragraph(_xml(f'Sınav kontrolü: {course} · net değişimi {delta} '
                                                  '(karşılaştırılabilir kayıt; neden doğrulanmadı)'), css['small']))
                    follow = integration.get('followup') or {}
                    if isinstance(follow.get('attention_count'),int) and follow['attention_count']>0:
                        story.append(Paragraph('Müdahale izlemi: '+_xml(str(follow['attention_count']))+
                                               ' onaylı kayıt için takip tarihi geldi.',css['warning']))
            else:
                story.append(Paragraph('Akademik kontrol: ' + _xml(s['next_step']),
                                        css['warning'] if s['attention'] else css['body']))
            if typ == 'Teslim':
                lines = meta.get('lines') or []
                for idx, line in enumerate(lines):
                    story.append(Paragraph('• ' + _xml(_trim(line,700)), css['body']))
                if not lines:
                    story.append(Paragraph('Bu teslim için konu detayı kaydedilmemiş.', css['small']))
            else:
                story.append(Paragraph('Görüşme öncesinde öğrencinin son kayıtlarını gözden geçirin.', css['small']))
            # Independently generated, student-scoped WhatsApp messages.
            d_nice = meta.get('nice_date') or day_iso
            actions=[]
            # A PDF using the system bridge never sends or opens a potentially
            # wrong recipient when ownership proof is missing.
            safe_contact = bool(s['id'] is not None and not s['identity_conflict'] and
                                (academic_context is None or
                                 (integration and integration.get('verified') and
                                  integration.get('contact_allowed'))))
            if s['phone'] and not s['contact_conflict'] and safe_contact:
                actions.extend((label,'url',url) for label, _color, url in whatsapp_actions(
                    s['phone'], student_message(ev, day_name, d_nice),
                    single_label='Öğrenci WhatsApp', multi_label='Öğrenci WA'))
                uri=call_url(s['phone'])
                if uri: actions.append(('Öğrenciyi Ara','url',uri))
            if s['parent_phone'] and not s['contact_conflict'] and safe_contact:
                actions.extend((label,'url',url) for label,_color,url in whatsapp_actions(
                    s['parent_phone'], parent_message(ev,day_name,d_nice),
                    single_label='Veli WhatsApp',multi_label='Veli WA'))
                uri=call_url(s['parent_phone'])
                if uri: actions.append(('Veliyi Ara','url',uri))
            if safe_contact and not s['contact_conflict'] and s['id'] is not None:
                actions.append(('Dönemlik Mesaj Merkezi', 'goto', f'msg_hub_{s["key"]}'))
            if s['id'] is not None and not s['identity_conflict'] and str(s['id']) in safe_live_links:
                actions.append(('Güncel Akademik Kart', 'url', safe_live_links[str(s['id'])]))
            if safe_contact and not s['contact_conflict'] and not s['identity_conflict'] and s['id'] is not None:
                for role, label in (('student','Öğrenci Durum Bildir'),('parent','Veli Durum Bildir')):
                    feedback_url = safe_feedback_links.get(str(s['id']), {}).get(role)
                    if feedback_url:
                        actions.append((label, 'url', feedback_url))
            if typ == 'Görüşme':
                # User-initiated calendar draft only. No student name or phone in URL.
                calendar_uri = calendar_meeting_url(day_iso, ev.get('saat'))
                if calendar_uri:
                    actions.append(('Takvime Ekle', 'url', calendar_uri))
            if not safe_contact:
                story.append(Paragraph('Bu öğrenci için kimlik veya akademik kaynak doğrulanamadı: iletişim bağlantıları güvenlik için kapatıldı.',css['warning']))
            if s['contact_conflict']:
                story.append(Paragraph('İletişim numaraları tutarsız. Yanlış alıcı riskine karşı bağlantılar kapatıldı.',css['warning']))
            if s['identity_conflict']:
                story.append(Paragraph('Aynı öğrenci numarası farklı isimlerle eşleşiyor. Kimlik doğrulanana kadar iletişim bağlantıları kapalıdır.',css['warning']))
            if actions:
                for start in range(0,len(actions),16):
                    story.append(JumpChip(actions[start:start+16],height=30,background='#eef9f4'))
                action_count += sum(1 for _, kind, _ in actions if kind == 'url')
            elif safe_contact:
                story.append(Paragraph('Geçerli iletişim numarası bulunamadı.',css['small']))
            story += [Spacer(1,8),JumpChip([('Ana Sayfaya Dön','goto','pocket_home')],height=24),Spacer(1,14)]
    if message_hubs:
        story += [CondPageBreak(175), Spacer(1,14), Paragraph('DÖNEMLİK MOBİL MESAJ MERKEZİ', css['heading']),
                  Paragraph('Bu bölüm yalnızca PDF oluşturulduğu andaki mesaj taslaklarını içerir. '
                            'Birleştirilmiş PDF öğretmene özeldir; öğrencilerle PDF dosyasının tamamını paylaşmayın. '
                            'WhatsApp açıldığında mesajı kontrol edip Gönder düğmesine siz dokunursunuz.', css['small']), Spacer(1,12)]
    for s in message_hubs:
        story.append(CondPageBreak(115))
        story += [AgendaBookmark(f'msg_hub_{s["key"]}'),
                  Paragraph(_xml(s['display_name']), css['student']),
                  Spacer(1,5)]
        integration = ((academic_context.get('student_cards') or {}).get(str(s['id']))
                       if academic_context is not None else None)
        # New period-wide messages must NEVER become enabled just because a
        # PDF was called directly without the verified SQLite ownership bridge.
        safe_contact = bool(integration and integration.get('verified')
                            and integration.get('contact_allowed'))
        if not safe_contact or s['contact_conflict'] or s['identity_conflict']:
            story.append(Paragraph('Kimlik, öğrenci kayıtları veya alıcı doğrulanamadı. '
                                   'Bu öğrencinin dönemlik iletişim bağlantıları kapatıldı.', css['warning']))
        else:
            templates = prepare_offline_message_pack(s, integration)
            number_actions = 0
            for role, phone, role_label in (
                ('student', s['phone'], 'Öğrenci'),
                ('parent', s['parent_phone'], 'Veli')):
                if not normalize_mobile_number(phone):
                    continue
                rows = []
                for kind, label in MESSAGE_KINDS:
                    message = templates.get((role, kind))
                    if not message:
                        continue
                    # The recipient's link is optional and requires REAL
                    # authenticated HTTPS. Never append another student's link.
                    reply_url = safe_feedback_links.get(str(s['id']), {}).get(role)
                    if reply_url:
                        message += ('\n\nGüvenli durum bildirimi (giriş gerekir): ' + reply_url)
                    try:
                        uri_actions = whatsapp_actions(phone, message,
                                    single_label=f'{role_label} · {label}',
                                    multi_label=f'{role_label} {label}')
                    except ValueError:
                        story.append(Paragraph(_xml(f'{role_label} {label} mesajı uzunluk sınırını '
                                                       'aştığı için bağlantı oluşturulamadı.'), css['warning']))
                        continue
                    rows.extend((action_label, 'url', uri) for action_label, _, uri in uri_actions)
                if rows:
                    story.append(Paragraph(_xml(role_label.upper()+' - HAZIR MESAJLAR'), css['tag']))
                    for chunk_start in range(0, len(rows), 14):
                        story.append(JumpChip(rows[chunk_start:chunk_start+14],
                                              height=32, background='#eef9f4'))
                    number_actions += len(rows)
                reply_url = safe_feedback_links.get(str(s['id']), {}).get(role)
                if reply_url:
                    story.append(JumpChip([(role_label+' Durum Bildir','url',reply_url)],height=30))
                    number_actions += 1
                uri = call_url(phone)
                if uri:
                    story.append(JumpChip([(role_label+' Ara','url',uri)], height=29))
                    number_actions += 1
            action_count += number_actions
            if not number_actions:
                story.append(Paragraph('Geçerli veya doğrulanmış alıcı bulunamadı.', css['small']))
        story += [Spacer(1,5),JumpChip([('Ana Sayfaya Dön', 'goto', 'pocket_home')],height=26),Spacer(1,16)]
    fd,tmp = tempfile.mkstemp(prefix='.pocket_',suffix='.pdf',dir=str(path.parent))
    os.close(fd)
    try:
        doc=SimpleDocTemplate(tmp,pagesize=PAGE,leftMargin=24,rightMargin=24,
             topMargin=24,bottomMargin=39,title='Akıllı Mobil PDF Asistanı',author='KoçPilot 360')
        doc.build(story,onFirstPage=lambda c,d:_footer(c,d,font),
                  onLaterPages=lambda c,d:_footer(c,d,font))
        # Structural validation works without optional PyMuPDF on Windows.
        # Detailed link destinations are independently verified in tests.
        payload = Path(tmp).read_bytes()
        if (payload.count(b'/S /URI') < action_count or
            payload.count(b'/Subtype /Link') < action_count + len(snap['days']) + len(snap['students'])):
            raise IOError('PDF bağlantı doğrulaması başarısız. Mevcut dosya korunuyor.')
        # /Type /Page is emitted for each page in ReportLab output.
        page_count = len(re.findall(rb'/Type\s*/Page(?!s)\b', payload))
        if page_count < 1:
            raise IOError('PDF sayfaları oluşturulamadı.')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return {'path':str(path),'pages':page_count,'live_links':len(safe_live_links), 'external_links':action_count,
            'feedback_links':sum(len(x) for x in safe_feedback_links.values()),
            'students':snap['student_count'],'days':len(snap['days']),
            'deadlines':snap['deadline_count']}
