"""Evidence-first one-click coaching brief.

Read-only. Completion is NOT mastery. A topic without homework is NOT a deficit.
No network usage, no student PII transmission, no writes in this module.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from typing import Any, Dict, Optional

DONE = {'tamam', 'tamamlandi', 'tamamlandı', 'yapildi', 'yapıldı', 'bitti', 'completed', 'done'}
ISSUES = {'yapilmadi', 'yapılmadı', 'eksik', 'kismi', 'kısmi', 'incomplete'}


def _norm(value: Any) -> str:
    return ' '.join(str(value or '').strip().casefold().split())


def _day(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _columns(con, table: str) -> set[str]:
    try:
        return {r[1] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}
    except Exception:
        return set()


def _field(cols: set[str], name: str, alias: str = None) -> str:
    # Query columns are static internal identifiers, never user supplied.
    return name if name in cols else ('NULL AS ' + (alias or name))


def _assignment_rows(con, student_id: int) -> tuple[list[dict], dict]:
    items: list[dict] = []
    source_stats = {'odev_satir': 0, 'odev': 0, 'mirrored': 0}
    modern_cols = _columns(con, 'odev_satir')
    legacy_cols = _columns(con, 'odev')
    kume_cols = _columns(con, 'odev_kume')
    has_kume = bool(kume_cols)

    # Modern rows take precedence when legacy and modern tables mirror a task.
    if modern_cols and 'ogrenci_id' in modern_cols:
        names = ['id', 'odev_id', 'kume_id', 'ders', 'konu', 'kitap', 'durum',
                 'tarih', 'tamamlanma_tarihi', 'silindi']
        sql = f"SELECT {', '.join(_field(modern_cols, x) for x in names)} FROM odev_satir WHERE ogrenci_id=?"
        for r in con.execute(sql, (student_id,)).fetchall():
            v = dict(r)
            if int(v.get('silindi') or 0) == 1:
                continue
            items.append({'origin': 'odev_satir', 'id': v.get('id'),
                          'odev_id': v.get('odev_id'), 'kume_id': v.get('kume_id'),
                          'ders': str(v.get('ders') or '').strip(),
                          'konu': str(v.get('konu') or '').strip(),
                          'kitap': str(v.get('kitap') or '').strip(),
                          'durum': _norm(v.get('durum')),
                          'date': _day(v.get('tamamlanma_tarihi')) or _day(v.get('tarih')),
                          'completed_at': _day(v.get('tamamlanma_tarihi'))})
        source_stats['odev_satir'] = len(items)

    if legacy_cols and 'ogrenci_id' in legacy_cols:
        names = ['id', 'kume_id', 'ders', 'konu_ad', 'kitap_ad', 'durum',
                 'verilis_tarihi', 'tamamlanma_tarihi']
        for r in con.execute(f"SELECT {', '.join(_field(legacy_cols, x) for x in names)} FROM odev WHERE ogrenci_id=?", (student_id,)).fetchall():
            v = dict(r)
            items.append({'origin': 'odev', 'id': v.get('id'), 'odev_id': None,
                          'kume_id': v.get('kume_id'),
                          'ders': str(v.get('ders') or '').strip(),
                          'konu': str(v.get('konu_ad') or '').strip(),
                          'kitap': str(v.get('kitap_ad') or '').strip(),
                          'durum': _norm(v.get('durum')),
                          'date': _day(v.get('tamamlanma_tarihi')) or _day(v.get('verilis_tarihi')),
                          'completed_at': _day(v.get('tamamlanma_tarihi'))})
            source_stats['odev'] += 1

    due_map = {}
    if has_kume and 'id' in kume_cols:
        fields = ['id', 'bitis_tarihi']
        due_map = {r['id']: _day(r['bitis_tarihi']) for r in
                   con.execute(f"SELECT {', '.join(_field(kume_cols, f) for f in fields)} FROM odev_kume").fetchall()}

    # Only collapse explicit linked IDs or same set/topic/book within same group;
    # distinct groups stay distinct, even if teacher gave identical tasks again.
    modern_by_legacy_id = {str(x['odev_id']) for x in items
                           if x['origin'] == 'odev_satir' and x['odev_id'] is not None}
    modern_keys = {(_norm(x['ders']), _norm(x['konu']), _norm(x['kitap']), str(x['kume_id']))
                   for x in items if x['origin'] == 'odev_satir' and x['kume_id'] is not None}
    filtered = []
    for item in items:
        key = (_norm(item['ders']), _norm(item['konu']), _norm(item['kitap']), str(item['kume_id']))
        duplicate = item['origin'] == 'odev' and (
            str(item['id']) in modern_by_legacy_id or
            (item['kume_id'] is not None and key in modern_keys))
        if duplicate:
            source_stats['mirrored'] += 1
            continue
        item['due'] = due_map.get(item['kume_id'])
        filtered.append(item)
    return filtered, source_stats


def build_coach_brief(con, student_id: int, *, as_of: Optional[date] = None,
                      max_actions: int = 5) -> Dict[str, Any]:
    """Read-only data-backed summary for a single student ID."""
    today = as_of or date.today()
    students = _columns(con, 'ogrenci')
    if not students:
        raise ValueError('Öğrenci tablosu bulunamadı.')
    s = con.execute('SELECT id, ad, soyad, ana_grup FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if s is None:
        raise ValueError('Öğrenci kaydı bulunamadı.')
    person = {'id': int(s['id']), 'name': ' '.join(filter(None, (s['ad'], s['soyad']))),
              'group': s['ana_grup'] or ''}
    rows, coverage = _assignment_rows(con, student_id)
    stats = {'assigned': len(rows), 'completed': 0, 'overdue': 0,
             'pending': 0, 'unverified': 0, 'recent_completed': 0, 'needs_review': 0}
    subjects = defaultdict(lambda: {'assigned': 0, 'completed': 0, 'overdue': 0})
    overdue = []
    recently_done = []
    needs_review_rows = []
    for r in rows:
        status = r['durum']
        done = status in DONE
        due = r['due']
        issue = status in ISSUES
        late = not done and bool(due and due < today)
        key = r['ders'] or 'Belirtilmeyen ders'
        subjects[key]['assigned'] += 1
        if done:
            stats['completed'] += 1
            subjects[key]['completed'] += 1
            if r['completed_at'] and (today - r['completed_at']).days in range(0, 15):
                stats['recent_completed'] += 1
                recently_done.append(r)
        elif late:
            stats['overdue'] += 1
            subjects[key]['overdue'] += 1
            overdue.append(r)
        else:
            stats['pending'] += 1
        if issue and not done and not late:
            stats['needs_review'] += 1
            needs_review_rows.append(r)
        if not due and not done and not issue:
            stats['unverified'] += 1

    stats['completion_percent'] = round(stats['completed'] * 100 / len(rows)) if rows else None
    # Classroom tasks and legacy status are not diagnostic tests of mastery.
    actions: list[dict] = []
    # Spread attention across subjects; avoid showing five copies of the same
    # overdue topic while hiding other subjects. No silent alteration of work.
    per_subject = defaultdict(int)
    priority_rows = sorted(overdue, key=lambda v: (v['due'] or today, v['ders']))
    chosen = []
    for row in priority_rows:
        if len(chosen) >= max(0, max_actions):
            break
        subject_key = _norm(row['ders'])
        if per_subject[subject_key] >= 2:
            continue
        per_subject[subject_key] += 1
        chosen.append(row)
    for row in chosen:
        due_txt = row['due'].isoformat() if row['due'] else 'tarih belirtilmemiş'
        actions.append({'kind': 'overdue', 'priority': 'Yüksek', 'subject': row['ders'],
                        'topic': row['konu'], 'source': f"Kayıtlı ödev / teslim: {due_txt}",
                        'text': f"{row['ders']} – {row['konu'] or 'Konu belirtilmemiş'}: tamamlanma durumunu doğrula, gerekirse telafi süresi ayır.",
                        'confidence': 'Doğrudan kayıt', 'requires_approval': True})
    if needs_review_rows and len(actions) < max_actions:
        row = sorted(needs_review_rows, key=lambda r: (r['due'] or today, r['ders']))[0]
        actions.append({'kind': 'homework_review', 'priority': 'Orta', 'subject': row['ders'],
                        'topic': row['konu'], 'source': 'Kayıtlı eksik/kısmi ödev durumu',
                        'text': f"{row['ders']} – {row['konu'] or 'Konu belirtilmemiş'}: eksik kısmı öğretmenle netleştir.",
                        'confidence': 'Doğrudan kayıt', 'requires_approval': True})

    # Only show observed exam performance, never infer unseen topic mastery.
    # V6: exam types and available question denominators are checked first.
    # Never treat a raw change in net score as diagnosis or proven regression.
    from services.coach_exam_quality_v6 import compare_exam_records
    exam_notes, exam_warnings = compare_exam_records(con, student_id, as_of=today)
    if exam_notes and len(actions) < max_actions:
        falling = [x for x in exam_notes if x['latest_net'] < x['previous_net']]
        for note in falling[:max_actions - len(actions)]:
            actions.append({'kind': 'exam_follow_up', 'priority': 'Orta', 'subject': note['subject'],
                            'topic': '', 'source': f"Deneme sonuçları: {note['previous_net']} → {note['latest_net']} net ({note['comparison_quality']})",
                            'text': f"{note['subject']} deneme değişimini sınav türü, soru sayısı, yanlış türleri ve güçlükle birlikte kontrol et.",
                            'confidence': note['comparison_quality'], 'requires_approval': True})

    warnings = []
    warnings.extend(exam_warnings)
    if stats['assigned'] == 0:
        warnings.append('Ödev geçmişi bulunamadı; öğrenciye akademik eksik atfedilemez.')
    if not exam_notes:
        warnings.append('Karşılaştırılabilir iki deneme sonucu bulunmadı; net değişimi veya konu hâkimiyeti hakkında çıkarım yapılamaz.')
    if stats['needs_review']:
        warnings.append(f"{stats['needs_review']} eksik/kısmi ödev kaydı var; teslim tarihi geçmediyse gecikme olarak etiketlenmedi.")
    if stats['unverified']:
        warnings.append(f"{stats['unverified']} açık ödevin teslim tarihi bilinmiyor; gecikmiş sayılmadı.")
    if coverage['mirrored']:
        warnings.append(f"{coverage['mirrored']} eşleşen eski/yeni ödev kaydı çift sayılmadı.")
    if not actions and stats['assigned'] > 0 and max_actions > 0:
        actions.append({'kind':'check', 'priority':'Normal', 'subject':'Genel', 'topic':'',
                        'source':'Mevcut ödev tablosu', 'text':'Acil gecikme görünmüyor. Tamamlanma kalitesini kısa bir kontrolle doğrula.',
                        'confidence':'Kayıt bazlı', 'requires_approval': True})
    return {'student': person, 'stats': stats, 'sources': coverage,
            'subjects': dict(subjects), 'actions': actions, 'exam_notes': exam_notes,
            'warnings': warnings, 'as_of': today.isoformat(),
            'note': 'Ödev tamamlama oranı çalışma takibidir; konu hâkimiyeti, öğrenme güçlüğü veya psikolojik tanı değildir.'}


def brief_as_html(report: Dict[str, Any]) -> str:
    def esc(v):
        return escape(str(v or ''))
    s, st = report['student'], report['stats']
    ratio = f"%{st['completion_percent']}" if st['completion_percent'] is not None else 'Veri yok'
    body = [f"<h2>Öğretmen için tek bakışta koçluk özeti</h2>",
            f"<p><b>{esc(s['name'])}</b> · {esc(s['group'])} · {esc(report['as_of'])}</p>",
            f"<p>Ödevler: <b>{st['assigned']}</b> · Tamamlanan: <b>{st['completed']}</b> "
            f"· Geciken: <b>{st['overdue']}</b> · Eksik/kısmi: <b>{st.get('needs_review', 0)}</b> · Tamamlama: <b>{ratio}</b></p>",
            '<p><b>Öncelikli kontroller (öğretmen onayına tabi):</b></p><ol>']
    for a in report['actions']:
        body.append(f"<li><b>{esc(a['text'])}</b><br/><small>Dayanak: {esc(a['source'])} "
                    f"· Kanıt: {esc(a['confidence'])}</small></li>")
    body.append('</ol>')
    if report['exam_notes']:
        body.append('<p><b>Kayıtlı deneme karşılaştırmaları:</b></p><ul>')
        for v in report['exam_notes'][:5]:
            body.append(f"<li>{esc(v['subject'])}: {v['previous_net']} → {v['latest_net']} net "
                        f"({esc(v['date'])}; {esc(v['exam_type'])}; {esc(v['comparison_quality'])}) — ölçüm koşulları değerlendirilmelidir.</li>")
        body.append('</ul>')
    if report['warnings']:
        body.append('<p><b>Veri sınırları:</b></p><ul>')
        body.extend(f'<li>{esc(x)}</li>' for x in report['warnings'])
        body.append('</ul>')
    body.append(f"<p><i>{esc(report['note'])}</i></p>")
    return '<div style="font-family:Segoe UI,Arial,sans-serif;font-size:13px;line-height:1.5">' + ''.join(body) + '</div>'


def brief_as_text(report: Dict[str, Any]) -> str:
    s, st = report['student'], report['stats']
    return '\n'.join([
        f"KOÇLUK ÖZETİ – {s['name']} ({report['as_of']})",
        f"Ödev: {st['assigned']} | Tamamlanan: {st['completed']} | Geciken: {st['overdue']}",
        'ÖNCELİKLİ KONTROLLER:',
        *[f"- {a['text']} [Dayanak: {a['source']}]" for a in report['actions']],
        'VERİ SINIRLARI:', *[f"- {w}" for w in report['warnings']], report['note'],
    ])


def build_safe_homework_suggestions(con, student_id: int, *, available_books: Optional[Dict[str, list[str]]] = None,
                                    target_minutes: int = 120, mode: str = 'balanced', limit: int = 12,
                                    as_of: Optional[date] = None) -> list[dict]:
    """Suggest only source-verified review/practice. Never duplicate outstanding work.

    target_minutes is a strict upper bound. At most two tasks per subject.
    """
    today = as_of or date.today()
    # No official, topic-level exam-frequency or curriculum match was verified:
    # do not produce made-up subject/topic recommendations for those modes.
    if mode in ('exam_focus', 'curriculum'):
        return []
    rows, _ = _assignment_rows(con, student_id)
    verified_books = available_books or {}
    if not verified_books and _columns(con, 'ogrenci_kitap'):
        verified_books = defaultdict(list)
        for r in con.execute('SELECT ders, kitap_ad FROM ogrenci_kitap WHERE ogrenci_id=?', (student_id,)).fetchall():
            verified_books[r['ders']].append(r['kitap_ad'])
    normalized_books = defaultdict(dict)
    for subject, books in verified_books.items():
        for book in books:
            if _norm(book):
                normalized_books[_norm(subject)][_norm(book)] = str(book)
    open_keys = {(_norm(r['ders']), _norm(r['konu']), _norm(r['kitap'])) for r in rows if r['durum'] not in DONE}
    completed_by_topic = {}
    for r in rows:
        if r['durum'] not in DONE or not r['completed_at'] or not r['ders'] or not r['konu']:
            continue
        key = (_norm(r['ders']), _norm(r['konu']), _norm(r['kitap']))
        if key in open_keys:
            continue
        old = completed_by_topic.get(key)
        if old is None or r['completed_at'] > old['completed_at']:
            completed_by_topic[key] = r

    candidates = []
    if mode not in ('remedial',):
        for r in completed_by_topic.values():
            age = (today - r['completed_at']).days
            if age < 7 or age > 60:
                continue
            subj, book = _norm(r['ders']), _norm(r['kitap'])
            verified_book = normalized_books.get(subj, {}).get(book)
            if not verified_book:
                continue
            candidates.append({'type': 'ebbinghaus', 'badge': '🧠 Tekrar Adayı', 'badge_color':'#7c3aed',
                               'ders':r['ders'], 'konu':r['konu'], 'kitap':verified_book,
                               'dk':25, 'soru':12, 'priority':2, 'score': 80 + min(age, 30),
                               'reason': f"Kayıtlı ödev {r['completed_at'].isoformat()} tarihinde tamamlanmış; 10-15 soruluk kısa hatırlama kontrolü önerilir. Gerçek unutma ölçülmedi.",
                               'auto_selected': False, 'evidence':'Tamamlanan ödev ve öğrenci kaynak kitabı'})

    mastery_cols = _columns(con, 'koc_konu_takip')
    if {'ogrenci_id','ders_adi','konu_adi','hakimiyet_puani'} <= mastery_cols and mode != 'ebbinghaus':
        known_keys = {(_norm(c['ders']),_norm(c['konu']),_norm(c['kitap'])) for c in candidates}
        for r in con.execute('SELECT ders_adi, konu_adi, hakimiyet_puani FROM koc_konu_takip WHERE ogrenci_id=?', (student_id,)).fetchall():
            val = r['hakimiyet_puani']
            if val is None or not (0 < float(val) <= 50):
                continue
            subject, topic = str(r['ders_adi'] or ''), str(r['konu_adi'] or '')
            owned = normalized_books.get(_norm(subject), {})
            if not topic or not owned:
                continue
            # No evidence connecting a particular book's contents to this topic.
            # Only propose if previous work in that same book and topic exists.
            matching_books = [book for book in owned.values()
                              if any(_norm(x['ders']) == _norm(subject) and _norm(x['konu']) == _norm(topic)
                                     and _norm(x['kitap']) == _norm(book) for x in rows)]
            if not matching_books:
                continue
            book = matching_books[0]
            key = (_norm(subject),_norm(topic),_norm(book))
            if key in open_keys or key in known_keys:
                continue
            known_keys.add(key)
            candidates.append({'type':'remedial', 'badge':'🎯 Koçluk Kontrolü', 'badge_color':'#d97706',
                               'ders':subject, 'konu':topic, 'kitap':book, 'dk':30, 'soru':15,
                               'priority':1, 'score':150-float(val),
                               'reason': f"Kayıtlı koçluk puanı {float(val):g}/100; kısa ölçme ve gerekirse telafi önerilir. Puan tanı değildir.",
                               'auto_selected':False, 'evidence':'Koçluk puanı + doğrulanmış kitap/konu geçmişi'})

    if mode == 'ebbinghaus':
        candidates = [x for x in candidates if x['type']=='ebbinghaus']
    if mode == 'remedial':
        candidates = [x for x in candidates if x['type']=='remedial']
    # No ranking based on unverified historical exam question-frequency tables.
    candidates.sort(key=lambda c:(-c['score'], _norm(c['ders']),_norm(c['konu'])))
    selected = []
    remaining = max(0, int(target_minutes))
    subject_counts = defaultdict(int)
    for item in candidates:
        if len(selected) >= max(0, int(limit)):
            break
        subject = _norm(item['ders'])
        duration = int(item['dk'])
        if duration > remaining or subject_counts[subject] >= 2:
            continue
        selected.append(item)
        remaining -= duration
        subject_counts[subject] += 1
    return selected


def build_profile_weekly_preview(con, student_id: int, profile: dict,
                                 available_books: Optional[Dict[str, list[str]]] = None,
                                 *, as_of: Optional[date] = None) -> dict:
    """Non-mutating *clock-time* preview, respecting existing V4 profile rules.

    Tasks are assigned at most once. No task disappears silently.
    """
    from services.planning_constraints import availability_for_week, free_minutes, find_slot, hhmm, to_minutes
    start_day = as_of or date.today()
    windows = availability_for_week(profile)
    base_limit = max(0, int(profile.get('max', 180)))
    override_days = profile.get('advanced_days', {}) if profile.get('advanced_enabled') else {}
    candidates = build_safe_homework_suggestions(con, student_id,
             available_books=available_books, target_minutes=sum(max(0, base_limit) for _ in range(7)),
             limit=25, as_of=start_day)
    result = []
    booked = {i: [] for i in range(7)}
    capacities = {}
    durations = {}
    for offset in range(7):
        day = (start_day + timedelta(days=offset)).weekday()
        detail = override_days.get(str(day), {}) if isinstance(override_days, dict) else {}
        daily_max = min(base_limit, max(0, int(detail.get('max', base_limit))),free_minutes(windows[day]))
        capacities[offset] = daily_max
        durations[offset] = 0
        result.append({'date': (start_day + timedelta(days=offset)).isoformat(),
                       'available_minutes': daily_max, 'planned_minutes': 0, 'items': []})
    enabled = bool(profile.get('session_enabled', False))
    session_size = max(15, int(profile.get('session_minutes', 45))) if enabled else 180
    gap = max(0, min(120, int(profile.get('session_break', 10)))) if enabled else 10
    split = bool(profile.get('session_split', False)) if enabled else False
    leftovers = []
    for task in candidates:
        total = int(task['dk'])
        if total > session_size and not split:
            leftovers.append({'task': task, 'reason':'Etüt sınırından uzun; bölme kapalı.'})
            continue
        chunks = []
        rest = total
        while rest:
            size = min(rest, session_size)
            chunks.append(size)
            rest -= size
        placed = False
        for offset in range(7):
            weekday = (start_day + timedelta(days=offset)).weekday()
            if durations[offset] + total > capacities[offset]:
                continue
            tentative = list(booked[offset])
            new_slots = []
            for size in chunks:
                biorhythm = str(profile.get('biorhythm', ''))
                slot = None
                school = (profile.get('school_by_day', {}) or {}).get(str(weekday))
                if school and len(school) == 2 and not any(x in biorhythm for x in ('Sabah', 'Erken')):
                    end_school = to_minutes(school[1]) + max(0, int(profile.get('after_school_buffer', 0)))
                    after_school = [(max(a,end_school),b) for a,b in windows[weekday] if b > max(a,end_school)]
                    slot = find_slot(after_school, tentative, size, biorhythm=biorhythm, gap=gap)
                if slot is None:
                    slot = find_slot(windows[weekday], tentative, size, biorhythm=biorhythm, gap=gap)
                if slot is None:
                    break
                tentative.append(slot)
                new_slots.append((slot, size))
            if len(new_slots) != len(chunks):
                continue
            booked[offset] = tentative
            durations[offset] += total
            for slot, size in new_slots:
                result[offset]['items'].append({'ders':task['ders'], 'konu':task['konu'],
                      'kitap':task['kitap'], 'dk':size, 'neden':task['reason'],
                      'start':hhmm(slot[0]), 'end':hhmm(slot[1])})
            placed = True
            break
        if not placed:
            leftovers.append({'task':task, 'reason':'Uygun boş saat/günlük kapasite bulunamadı.'})
    for offset, day in enumerate(result):
        day['items'].sort(key=lambda it: it['start'])
        day['planned_minutes'] = durations[offset]
    return {'schedule':result,'leftovers':leftovers,'total_candidates':len(candidates),
            'profile':profile.get('profile_idx'),
            'notice':'Bu bir öneri önizlemesidir; ödev tablosunu veya onaylı programı değiştirmez.'}
