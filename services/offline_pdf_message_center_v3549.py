# -*- coding: utf-8 -*-
"""V3.5.49 - precomputed, offline-first, STUDENT-scoped WhatsApp draft packs.

No QWidgets, database writes, web requests, auto-send, or PDF JavaScript.
Only a teacher-kept PDF contains these links; never share the combined PDF
with recipients. Recipient ownership is verified upstream before rendering.
"""
from __future__ import annotations

from datetime import date, datetime


def _as_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _clean(value):
    # WhatsApp is plain text. Remove control chars and keep newlines in notes
    # out of messages; never import teachers' free-form internal notes.
    return ''.join(c if (ord(c) >= 32 or c == '\n') else ' ' for c in str(value or '')).strip()


def _outline(student):
    tasks, meetings = [], []
    # Preserve the complete, source-provided homework list and each date.
    for event in student.get('events', ()):
        day = _as_date(event.get('_day_date'))
        if not day:
            continue
        pretty = day.strftime('%d.%m.%Y')
        if event.get('tip') == 'Teslim':
            tasks.append((day, pretty, [_clean(x) for x in (event.get('meta') or {}).get('lines', ()) if _clean(x)]))
        elif event.get('tip') == 'Görüşme':
            time_text = _clean(event.get('saat'))
            meetings.append((day, pretty, time_text))
    tasks.sort(key=lambda row: row[0])
    meetings.sort(key=lambda row: row[0])
    return tasks, meetings


def prepare_offline_message_pack(student, academic_card=None, *, generated_on=None):
    """Return {(role, kind): immutable-at-export message}.

    Only verified academic cards may produce academic summaries; daily tasks
    and meetings come from the student's schedule, not a guessed success state.
    Messages carry a snapshot timestamp to prevent the impression of live data.
    No message is sent or recorded as sent by preparing it.
    """
    created = generated_on or datetime.now()
    if not isinstance(created, (date, datetime)):
        raise TypeError('Geçersiz oluşturulma tarihi')
    if not student.get('id') or student.get('contact_conflict'):
        return {}
    name = _clean(student.get('name') or 'Öğrenci')
    tasks, meetings = _outline(student)
    days = [ev[0] for ev in tasks] + [ev[0] for ev in meetings]
    if not days:
        return {}
    coverage = f'{min(days):%d.%m.%Y} - {max(days):%d.%m.%Y}'
    when = f'{created:%d.%m.%Y %H:%M}' if isinstance(created, datetime) else f'{created:%d.%m.%Y}'
    footer = (f'\n\nNot: Bu mesaj {when} tarihinde hazırlanan ajandaya dayanır. '
              'Göndermeden önce güncelliğini kontrol ediniz.')
    greeting = {'student':f'Merhaba {name},',
                'parent':f'Sayın Velimiz, öğrencimiz {name} için bilgilendirme:'}
    result = {}
    homework_lines = []
    for _, pretty, lines in tasks:
        homework_lines.append(f'📅 {pretty} teslim:')
        homework_lines.extend('  • '+x for x in lines)
        if not lines:
            homework_lines.append('  • Ayrıntılı ödev konusu ajandada belirtilmemiş.')
    meeting_lines = [f'📅 {pretty} - {hour if hour and hour != "??:??" else "Saat teyidi gerekli"}'
                     for _,pretty,hour in meetings]
    # Repeat recipient-specific greeting and include period to prevent accidental reuse.
    for role in ('student','parent'):
        prefix = greeting[role]+'\n'
        if tasks:
            result[(role,'homework')] = (prefix + f'\n{coverage} dönemi ödev ve teslim planı:\n\n'
                                         + '\n'.join(homework_lines) + footer)
            result[(role,'reminder')] = (prefix + f'\n{coverage} dönemi teslim hatırlatması:\n'
                                         + '\n'.join(f'• {pretty} - {len(lines)} çalışma maddesi'
                                                     for _,pretty,lines in tasks)
                                         + '\n\nÖdevlerin güncel durumunu birlikte kontrol edelim.' + footer)
        if meetings:
            result[(role,'meeting')] = (prefix + f'\n{coverage} dönemi görüşme hatırlatmaları:\n\n'
                                        + '\n'.join(meeting_lines) + footer)
        # No internal free-text notes, raw diagnoses, or unverified exam inferences.
        if academic_card and academic_card.get('verified') and academic_card.get('contact_allowed'):
            hw = academic_card.get('homework') or {}
            data = []
            if isinstance(hw.get('total'), int) and isinstance(hw.get('completed'), int):
                data.append(f'Kayıtlı ödev: {hw["total"]}; tamamlanan: {hw["completed"]}.')
            if isinstance(hw.get('overdue'), int) and hw['overdue'] > 0:
                data.append(f'Kayda göre teslim tarihi geçen açık ödev: {hw["overdue"]}.')
            if data:
                data.append('Tamamlama sayıları öğrenme düzeyinin doğrudan ölçümü değildir.')
                result[(role,'analysis')] = (prefix + f'\n{coverage} akademik takip özeti:\n'
                                              + '\n'.join(data) + '\nGerekirse öğretmenle birlikte değerlendirelim.' + footer)
        # Full follow-up, with no fabricated assessment and no implicit database update.
        parts = []
        if tasks:
            parts.append(f'Ödev teslim kaydı: {len(tasks)} gün/görev.\n' + '\n'.join(homework_lines))
        if meetings:
            parts.append('Görüşmeler:\n' + '\n'.join(meeting_lines))
        if parts:
            result[(role,'followup')] = (prefix + f'\n{coverage} dönemlik takip:\n\n'
                                              + '\n\n'.join(parts) + footer)
    return result


MESSAGE_KINDS = (
    ('homework', 'Ödevleri Gönder'),
    ('reminder', 'Teslim Hatırlat'),
    ('meeting', 'Görüşme Hatırlat'),
    ('followup', 'Dönemlik Takip'),
    ('analysis', 'Akademik Özet'),
)
