"""Read-only V35 presentation helpers for the weekly planner.

No DB access, no Qt imports, no scheduler changes.  The same assignments and
appointments are used for the dialog overview and the printable details.
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

from services.planning_constraints import parse_details, hhmm


def overview(homework: list[dict] | None, data: dict | None) -> dict:
    """Summarise actual homework and explicit constraints, never invent outcomes."""
    homework = homework or []
    data = data or {}
    minutes = sum(max(0, int(h.get('sure') or 0)) for h in homework if isinstance(h, dict))
    lessons = sorted({str(h.get('ders') or '').strip() for h in homework if isinstance(h, dict)
                      and h.get('ders')}, key=str.casefold)
    school = data.get('school_by_day') or {}
    blocks = list(data.get('blocks') or [])
    return {
        'count': len(homework), 'minutes': minutes, 'lessons': lessons,
        'school_days': len(school), 'routines': len(blocks),
        'wake': str(data.get('wake') or '07:00'),
        'sleep': str(data.get('sleep') or '23:30'),
        'daily_max': int(data.get('max') or 180),
        'after_school': int(data.get('after_school_buffer') or 0),
        'after_routine': int(data.get('after_routine_buffer') or 0),
        'focus': str(data.get('focus') or '').strip(),
        'session_minutes': int(data.get('session_minutes') or 45),
        'session_break': int(data.get('session_break') or 10),
        'split_enabled': bool(data.get('session_enabled') and data.get('session_split', True)),
        'blocks': blocks,
    }


def detailed_section(days: list[Any], profile: dict, details: Any) -> str:
    """Append a legible, precise audit trail to the existing A4 HTML.

    Qt QTextDocument lays out the table across additional pages if needed;
    nothing is silently omitted when homework is large.
    """
    data = parse_details(details) or {}
    placed = [((d.date_), t, s, e) for d in days for t, s, e in d.appointments]
    placed.sort(key=lambda row: (row[0], row[2], row[3]))
    unassigned = list(profile.get('unassigned') or [])
    planned_minutes = sum(t.sure for _, t, _, _ in placed)
    pending_minutes = sum(t.sure for t in unassigned)
    week_text = (f'{days[0].date_.strftime("%d.%m.%Y")} - '
                 f'{days[-1].date_.strftime("%d.%m.%Y")}') if days else 'Belirsiz'
    first_school = data.get('school_by_day') or {}
    school_descriptions = []
    names = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
    for i, val in sorted(first_school.items(), key=lambda kv: int(kv[0])):
        try:
            if len(val) == 2:
                school_descriptions.append(f'{names[int(i)]} {val[0]}-{val[1]}')
        except (ValueError, TypeError, IndexError):
            pass
    rules = [
        ('Hafta', week_text),
        ('Okul', ', '.join(school_descriptions) if school_descriptions else 'Kayıt yok'),
        ('Uyku', f'{data.get("sleep", "-")} - {data.get("wake", "-")}'),
        ('Günlük üst sınır', f'{data.get("max", profile.get("daily_max", "-"))} dk'),
        ('Okul sonrası geçiş', f'{data.get("after_school_buffer", 0)} dk'),
        ('Rutin sonrası geçiş', f'{data.get("after_routine_buffer", 0)} dk'),
        ('Öncelikli ders', data.get('focus') or 'Belirtilmedi'),
    ]
    # A per-plan, teacher-confirmed topic focus is a proposal, not a diagnosed
    # deficit and not a modification to historical homework completion state.
    if data.get('adaptive_topic_focus_v35'):
        from services.weekly_topic_priority_v35 import accepted_topic_pairs
        focus = accepted_topic_pairs(
            [getattr(task, 'raw', {}) for day in days for task in day.tasks] +
            [getattr(task, 'raw', {}) for task in profile.get('unassigned', [])],
            data['adaptive_topic_focus_v35'])
        if focus:
            rules.append(('Öğretmen onaylı konu önceliği', ', '.join(
                f'{entry["lesson"]} / {entry["topic"]}' for entry in focus)))
    if data.get('session_enabled'):
        rules.append(('Oturum', f'{data.get("session_minutes", 45)} dk + '
                         f'{data.get("session_break", 10)} dk mola'))
    for block in (data.get('blocks') or []):
        rules.append(('Sabit rutin', block))
    rows = []
    tr_days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
    for date_, task, start, end in placed:
        deadline = task.deadline.strftime('%d.%m.%Y') if task.deadline else 'Belirtilmedi'
        rows.append('<tr><td>{}</td><td><b>{}</b><br/><span style="color:#64748b">{}</span></td>'
                    '<td>{}</td><td>{}</td><td>{} dk</td><td>{}</td></tr>'.format(
                        escape(tr_days[date_.weekday()] + ' ' + date_.strftime('%d.%m')),
                        escape(task.ders), escape(task.konu), escape(task.kitap or 'Kaynak belirtilmedi'),
                        escape(hhmm(start) + ' - ' + hhmm(end)), task.sure, escape(deadline)))
    if not rows:
        rows.append('<tr><td colspan="6">Uygun zaman aralığına görev yerleştirilemedi.</td></tr>')
    rule_rows = ['<tr><td style="color:#475569;width:19%"><b>{}</b></td><td>{}</td></tr>'.format(
        escape(str(label)), escape(str(value))) for label, value in rules]
    note = escape(str(data.get('note') or '').strip())
    pending = ''.join('<li>{} / {} / {} - {} dk{}</li>'.format(
        escape(t.ders), escape(t.konu), escape(t.kitap or '-'), t.sure,
        (' (son teslim: ' + t.deadline.strftime('%d.%m.%Y') + ')' if t.deadline else ''))
        for t in unassigned)
    pending_block = ('<div style="background:#fffbeb; border:1px solid #f59e0b; padding:5px;">'
                     '<b>Yerleştirilemeyen görevler:</b><ul>' + pending + '</ul></div>') if unassigned else ''
    note_block = ('<p style="font-size:8pt; color:#1e293b"><b>Öğretmen / Koç Notu:</b> '
                  + note + '</p>') if note else ''
    return f'''
    <div class="v35-report" style="margin-top:7px; border-top:2px solid #2563eb; padding-top:6px;">
      <table width="100%" cellspacing="0" cellpadding="5" style="width:100%;background:#eff6ff;border:1px solid #bfdbfe;font-size:8pt;">
        <tr>
          <td><b>PLAN ÖZETİ</b></td>
          <td>Planlanan: <b>{len(placed)} oturum</b></td>
          <td>Süre: <b>{planned_minutes} dk</b></td>
          <td>Yerleştirilemeyen: <b>{len(unassigned)} oturum / {pending_minutes} dk</b></td>
          <td>Kontrol: <b>Öğretmen onayı bekleniyor</b></td>
        </tr>
      </table>
      <p style="font-size:8pt;font-weight:bold;color:#1e3a8a;margin:5px 0 2px">GÜN VE SAAT BAZINDA GÖREVLER</p>
      <table width="100%" cellspacing="0" cellpadding="4" style="width:100%;border-collapse:collapse;font-size:8pt;border:1px solid #e2e8f0;">
        <tr style="background:#e2e8f0;color:#334155;font-weight:bold">
          <td>Gün / Tarih</td><td>Ders / Konu</td><td>Kitap</td><td>Başlangıç - Bitiş</td><td>Süre</td><td>Son teslim</td>
        </tr>
        {''.join(rows)}
      </table>
      <p style="font-size:8pt;font-weight:bold;color:#1e3a8a;margin:6px 0 2px">PLANLAMADA DİKKATE ALINAN KISITLAR</p>
      <table width="100%" cellspacing="0" cellpadding="3" style="width:100%;background:#f8fafc;font-size:7.5pt;border:1px solid #e2e8f0;">
        {''.join(rule_rows)}
      </table>
      {pending_block}
      {note_block}
      <p style="font-size:7pt;color:#64748b;margin-top:4px">Bu belge önerilen çalışma takvimidir. Kutuların boş olması,
      ödevlerin tamamlanma bilgisinin henüz doğrulanmadığını gösterir. Plan, ödev tamamlama kayıtlarını değiştirmez.</p>
    </div>'''


def enhance_html(base_html: str, days: list[Any], profile: dict, details: Any) -> str:
    """Retain existing executive calendar while adding the detailed information."""
    section = detailed_section(days, profile, details)
    marker = '<div class="footer">'
    if marker not in base_html:
        raise ValueError('Haftalık takvim HTML şablonunda altbilgi bulunamadı.')
    return base_html.replace(marker, section + '\n            ' + marker, 1)
