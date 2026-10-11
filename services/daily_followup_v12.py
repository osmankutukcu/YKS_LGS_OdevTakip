"""V12 daily brief -> evidence-grounded, read-only follow-up calendar draft.

A proposal is not an accepted calendar entry. It only uses a named profile that
is explicitly assigned to the matching student ID. Never invents task duration,
never persists student work, and never interprets assignment history as learning.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any

from services.planning_constraints import availability_for_week, hhmm, to_minutes, find_slot

DONE = {'tamam', 'tamamlandi', 'tamamlandı', 'yapildi', 'yapıldı', 'bitti'}


def _student_id(value: Any) -> int:
    try:
        sid = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Geçerli öğrenci kimliği gerekli.') from exc
    if sid < 1:
        raise ValueError('Geçerli öğrenci kimliği gerekli.')
    return sid


def _due_day(raw: Any) -> date | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw)).date()
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d.%m.%Y'):
        try:
            return datetime.strptime(str(raw), fmt).date()
        except ValueError:
            pass
    return None


def load_open_homework(con, student_id: Any, *, today: date | None = None, limit: int = 250) -> dict:
    """Query ONLY the selected student's incomplete legacy assignment rows.

    V10 daily analysis uses the same `odev` + `odev_kume` relationship. A large
    backlog is intentionally not truncated and presented as a complete list.
    """
    sid = _student_id(student_id)
    now = today or date.today()
    student = con.execute('SELECT id, ad, soyad FROM ogrenci WHERE id=? AND aktif=1', (sid,)).fetchone()
    if student is None:
        raise ValueError('Öğrenci bulunamadı veya artık aktif değil.')
    rows = con.execute('''
        SELECT o.id, o.ders, o.konu_ad, o.kitap_ad, o.saat_dk, o.durum, k.bitis_tarihi
        FROM odev o JOIN odev_kume k
          ON k.id=o.kume_id AND k.ogrenci_id=o.ogrenci_id
        WHERE o.ogrenci_id=?
        ORDER BY o.id LIMIT ?''', (sid, max(1, int(limit))+1)).fetchall()
    if len(rows) > limit:
        raise ValueError('Çok fazla ödev kaydı var. Eksik listeyle plan üretilmedi.')
    tasks, unknown_duration = [], []
    for r in rows:
        row = dict(r) if hasattr(r, 'keys') else dict(zip(
            ('id','ders','konu_ad','kitap_ad','saat_dk','durum','bitis_tarihi'), r))
        if str(row['durum'] or '').strip().casefold() in DONE:
            continue
        if str(row['durum'] or '').strip().casefold() not in ('devam', ''):
            continue  # Unknown statuses aren't silently assumed active.
        due = _due_day(row['bitis_tarihi'])
        if due is None:
            unknown_duration.append(f"#{row['id']} {row['ders']} – {row['konu_ad']}: teslim tarihi doğrulanamadı")
            continue
        if due >= now:
            continue  # Follow-up is for overdue homework, not all pending tasks.
        try:
            minutes = int(row['saat_dk'])
        except (TypeError, ValueError):
            minutes = 0
        if not 1 <= minutes <= 720:
            unknown_duration.append(f"#{row['id']} {row['ders']} – {row['konu_ad']}: süre doğrulanamadı")
            continue
        tasks.append({
            'id': int(row['id']), 'lesson': str(row['ders'] or ''),
            'topic': str(row['konu_ad'] or ''), 'book': str(row['kitap_ad'] or ''),
            'minutes': minutes, 'due': due,
        })
    tasks.sort(key=lambda r: (r['due'], r['id']))
    return {'student_id': sid, 'student_name': f"{student[1]} {student[2]}".strip(),
            'tasks': tasks, 'needs_review': unknown_duration}


def assigned_profile(student_id: Any, profiles: dict, assignments: dict) -> tuple[str, dict] | None:
    """Fail closed rather than silently using somebody else's first profile."""
    sid = str(_student_id(student_id))
    name = assignments.get(sid)
    if not isinstance(name, str) or not name:
        return None
    profile = profiles.get(name)
    if not isinstance(profile, dict) or profile.get('planner_version') != 2:
        return None
    owner = profile.get('_session_advisor_owner')
    if owner is not None and str(owner) != sid:
        raise ValueError('Kişisel profil başka bir öğrenciye ait; kullanılamaz.')
    return name, profile


def make_followup_draft(student_id: Any, facts: dict, profiles: dict,
                        assignments: dict, *, now: datetime | None = None) -> dict:
    """Allocate overdue time into next 7 local dates, respecting saved routine.

    The source `facts` MUST come from load_open_homework. No DB operations or
    writes occur here; no existing manually scheduled tasks are overwritten.
    """
    sid = _student_id(student_id)
    if facts.get('student_id') != sid:
        raise ValueError('Analiz başka öğrenciye ait. Plan oluşturulmadı.')
    instant = now or datetime.now()
    if instant.tzinfo is not None:
        raise ValueError('Plan yerel, saat dilimi içermeyen okul saati bekliyor.')
    result = {'student_id': sid, 'student_name': facts.get('student_name') or f'Öğrenci {sid}',
              'profile_name': None, 'status': 'no_profile', 'slots': [],
              'needs_review': list(facts.get('needs_review') or []),
              'remaining': [], 'note': ''}
    resolved = assigned_profile(sid, profiles, assignments)
    if not resolved:
        result['note'] = ('Öğrenciye bağlı kayıtlı haftalık profil yok. '
                          'Ödev takip formundan profil seçip kaydedin; saat uydurulmadı.')
        return result
    name, profile = resolved
    result['profile_name'] = name
    try:
        windows = availability_for_week(profile)
        daily_default = max(0, min(720, int(profile.get('max', 180))))
        rules = profile.get('advanced_days') or {} if profile.get('advanced_enabled') else {}
        legacy_rules = profile.get('day_overrides') or {}
        if not isinstance(rules, dict) or not isinstance(legacy_rules, dict):
            raise ValueError('Öğrencinin günlük plan sınırları hatalı.')
        session_enabled = bool(profile.get('session_enabled'))
        session_limit = int(profile.get('session_minutes', 45)) if session_enabled else 180
        session_break = int(profile.get('session_break', 10)) if session_enabled else 10
        allow_split = bool(profile.get('session_split', True)) if session_enabled else True
        if not 15 <= session_limit <= 180 or not 0 <= session_break <= 60:
            raise ValueError('Etüt süresi/mola ayarı geçersiz.')
    except (ValueError, TypeError, KeyError) as exc:
        result['status'] = 'invalid_profile'
        result['note'] = f'Kayıtlı rutin okunamadı: {exc}. Plan oluşturulmadı.'
        return result
    tasks = list(facts.get('tasks') or [])
    if not tasks:
        result['status'] = 'no_overdue'
        result['note'] = ('Süresi doğrulanmış açık gecikmiş ödev bulunmadı. '
                          'Görüşme gerekiyorsa öğretmen ayrıca belirlemeli.')
        return result
    daily = []
    for offset in range(7):
        day = instant.date() + timedelta(days=offset)
        wd = day.weekday()
        day_rule = (rules.get(str(wd), legacy_rules.get(str(wd), {}))
                    if profile.get('advanced_enabled') else {})
        try:
            cap = max(0, min(daily_default, int(day_rule.get('max', daily_default))))
        except (AttributeError, TypeError, ValueError):
            result['status'] = 'invalid_profile'
            result['note'] = 'Günlük üst sınır geçersiz. Plan oluşturulmadı.'
            return result
        available = list(windows[wd])
        if offset == 0:
            # Past slots never become proposed future appointments.
            minute = instant.hour * 60 + instant.minute + (1 if instant.second else 0)
            available = [(max(s, minute), e) for s, e in available if e > max(s, minute)]
        daily.append({'day': day, 'windows': available, 'booked': [], 'cap': cap, 'used': 0})

    for task in tasks:
        remaining = int(task['minutes'])
        # The limit is a maximum continuous session, not a requirement to pad.
        if not allow_split and remaining > session_limit:
            result['remaining'].append({**task, 'minutes': remaining, 'reason': 'Bölünemez uzun ödev'})
            continue
        while remaining:
            found = False
            for d in daily:
                cap_left = d['cap'] - d['used']
                if cap_left <= 0:
                    continue
                for start, end in d['windows']:
                    # Split duration to remaining free time, don't invent free time.
                    desired = min(remaining, session_limit, cap_left, end-start)
                    if desired <= 0:
                        continue
                    # Try short durations when a window contains a booked session.
                    for duration in range(desired, 0, -1):
                        slot = find_slot([(start, end)], d['booked'], duration,
                                         gap=session_break)
                        if slot is None:
                            continue
                        d['booked'].append(slot)
                        d['used'] += duration
                        result['slots'].append({
                            'date': d['day'].isoformat(), 'start': hhmm(slot[0]),
                            'end': hhmm(slot[1]), 'minutes': duration,
                            'assignment_id': task['id'], 'lesson': task['lesson'],
                            'topic': task['topic'], 'book': task['book']})
                        remaining -= duration
                        found = True
                        break
                    if found:
                        break
                if found:
                    break
            if not found:
                result['remaining'].append({**task, 'minutes': remaining, 'reason': 'Uygun kapasite yok'})
                break
    result['slots'].sort(key=lambda s: (s['date'], s['start'], s['assignment_id']))
    result['status'] = 'ready' if result['slots'] else 'no_slots'
    result['note'] = ('Yalnızca profil ve kayıtlı gecikmiş ödev sürelerine göre taslak. '
                      'Önceden elle kararlaştırılan ancak sisteme kayıtlı olmayan randevular '
                      'tespit edilemez. Ödev ve takvim kaydedilmedi.')
    return result


def draft_text(draft: dict) -> str:
    lines = [f"Öğrenci: {draft['student_name']}",
             f"Profil: {draft.get('profile_name') or 'Atanmamış'}", '']
    if draft['slots']:
        lines.append('ÖNERİLEN ETÜT TASLAĞI (KAYDEDİLMEDİ)')
        for slot in draft['slots']:
            lines.append(f"{slot['date']} {slot['start']}–{slot['end']}  "
                         f"{slot['lesson']} / {slot['topic']}  ({slot['minutes']} dk, ödev #{slot['assignment_id']})")
    else:
        lines.append('Uygun zamanlı etüt taslağı oluşturulamadı.')
    if draft['remaining']:
        lines.extend(['', 'YERLEŞMEYEN ÇALIŞMALAR'])
        for task in draft['remaining']:
            lines.append(f"#{task['id']} {task['lesson']} / {task['topic']}: "
                         f"{task['minutes']} dk – {task['reason']}")
    if draft['needs_review']:
        lines.extend(['', 'ÖĞRETMEN KONTROLÜ GEREKEN KAYITLAR'])
        lines.extend(draft['needs_review'])
    lines.extend(['', draft.get('note', ''),
                  'Öğretmen onayı olmadan ödev, tik, profil veya onaylı program değiştirilmez.'])
    return '\n'.join(lines)
