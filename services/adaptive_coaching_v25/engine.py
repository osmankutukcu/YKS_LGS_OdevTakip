# -*- coding: utf-8 -*-
"""Opt-in adaptive coaching. SQLite data stays separate from legacy checkboxes.

All proposals are heuristics requiring a coach's review; no automatic grades,
mastery declarations, homework assignments, or rollover/deletion of old work.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import json
import math

VERSION = '25.0'
REASONS = ('Kavram eksikliği', 'İşlem hatası', 'Dikkat', 'Zaman yönetimi',
           'Soruyu yorumlama', 'İş yükü', 'Erteleme / motivasyon', 'Diğer', 'Belirtilmedi')
MODES = ('Karma mini sınav', 'Hedefli soru', 'Geri getirme', 'Sözlü anlatım', 'Yanlış analizi')
DEFAULTS = {'weekly_minutes': 240, 'review_percent': 30, 'max_session_minutes': 35,
            'learning_style': 'Dengeli', 'spacing_days': [2, 7, 14, 28]}


def _date(value, default=None):
    if isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    try:
        return date.fromisoformat(str(value or '')[:10])
    except (ValueError, TypeError):
        return default


def ensure_schema(con):
    """Only create V25 tables; migrations never alter legacy homework data."""
    con.executescript('''
        CREATE TABLE IF NOT EXISTS adaptive_observation_v25 (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
          homework_id INTEGER REFERENCES odev(id) ON DELETE SET NULL,
          lesson TEXT NOT NULL, topic TEXT NOT NULL, subskill TEXT NOT NULL DEFAULT '',
          mode TEXT NOT NULL, correct INTEGER NOT NULL DEFAULT 0,
          wrong INTEGER NOT NULL DEFAULT 0, blank INTEGER NOT NULL DEFAULT 0,
          duration_min INTEGER NOT NULL DEFAULT 0,
          reason TEXT NOT NULL DEFAULT 'Belirtilmedi', note TEXT NOT NULL DEFAULT '',
          observed_on TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CHECK(correct>=0 AND wrong>=0 AND blank>=0 AND duration_min>=0)
        );
        CREATE INDEX IF NOT EXISTS idx_adapt_obs_student_topic_v25
          ON adaptive_observation_v25(student_id, lesson, topic, observed_on DESC);
        CREATE TABLE IF NOT EXISTS adaptive_profile_v25 (
          student_id INTEGER PRIMARY KEY REFERENCES ogrenci(id) ON DELETE CASCADE,
          preferences_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS adaptive_blocker_v25 (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
          homework_id INTEGER REFERENCES odev(id) ON DELETE SET NULL,
          reason TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
          resolution TEXT NOT NULL DEFAULT 'Koç değerlendirmesi bekliyor',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_adapt_blocker_v25_student
          ON adaptive_blocker_v25(student_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS adaptive_plan_v25 (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          student_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
          preferences_json TEXT NOT NULL, plan_json TEXT NOT NULL,
          approved INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_adapt_plan_v25_student
          ON adaptive_plan_v25(student_id, created_at DESC);
    ''')
    con.commit()


def _student_exists(con, student_id):
    row = con.execute('SELECT 1 FROM ogrenci WHERE id=?', (int(student_id),)).fetchone()
    if row is None:
        raise ValueError('Öğrenci kimliği bulunamadı; kayıt yapılmadı.')


def save_observation(con, student_id, lesson, topic, *, homework_id=None, subskill='',
                     mode='Hedefli soru', correct=0, wrong=0, blank=0,
                     duration_min=0, reason='Belirtilmedi', note='', observed_on=None):
    """Append-only qualitative/quantitative evidence; never update `odev.durum`."""
    student_id = int(student_id)
    _student_exists(con, student_id)
    lesson, topic, subskill = str(lesson).strip(), str(topic).strip(), str(subskill).strip()
    if not lesson or not topic:
        raise ValueError('Ders ve konu zorunludur.')
    if mode not in MODES or reason not in REASONS:
        raise ValueError('Tanımsız değerlendirme veya neden.')
    correct, wrong, blank, duration_min = map(int, (correct, wrong, blank, duration_min))
    if min(correct, wrong, blank, duration_min) < 0 or max(correct, wrong, blank) > 10000:
        raise ValueError('Soru sayısı ve süre negatif olamaz / sınır aşıldı.')
    if sum((correct, wrong, blank)) == 0 and not str(note).strip():
        raise ValueError('En az bir soru sonucu veya açıklayıcı gözlem yazın.')
    if homework_id is not None:
        homework_id = int(homework_id)
        owner = con.execute('SELECT ogrenci_id, ders, konu_ad FROM odev WHERE id=?', (homework_id,)).fetchone()
        if owner is None or int(owner['ogrenci_id']) != student_id:
            raise ValueError('Ödev ile öğrenci kimliği uyuşmuyor.')
        if (owner['ders'] or '').strip() != lesson or (owner['konu_ad'] or '').strip() != topic:
            raise ValueError('Seçilen ödevin dersi/konusu değişti; yeniden seçin.')
    observed_on = _date(observed_on, date.today()).isoformat()
    with con:
        c = con.execute('''INSERT INTO adaptive_observation_v25
        (student_id, homework_id, lesson, topic, subskill, mode, correct, wrong, blank,
         duration_min, reason, note, observed_on) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
         (student_id, homework_id, lesson, topic, subskill, mode, correct, wrong, blank,
          duration_min, reason, str(note).strip()[:3000], observed_on))
    return c.lastrowid


def observations(con, student_id, limit=200):
    _student_exists(con, student_id)
    return [dict(r) for r in con.execute('''SELECT * FROM adaptive_observation_v25
        WHERE student_id=? ORDER BY observed_on DESC, id DESC LIMIT ?''',
        (int(student_id), max(1, min(int(limit), 1000))))]


def load_preferences(con, student_id):
    _student_exists(con, student_id)
    row = con.execute('SELECT preferences_json FROM adaptive_profile_v25 WHERE student_id=?',
                      (int(student_id),)).fetchone()
    data = {}
    if row:
        try:
            data = json.loads(row['preferences_json'])
        except (TypeError, ValueError):
            pass
    return _validated_preferences(data)


def _validated_preferences(data):
    p = dict(DEFAULTS)
    if not isinstance(data, dict):
        data = {}
    for key, low, high in [('weekly_minutes', 30, 1800),
                           ('review_percent', 0, 60), ('max_session_minutes', 10, 120)]:
        try:
            p[key] = max(low, min(high, int(data.get(key, DEFAULTS[key]))))
        except (ValueError, TypeError):
            pass
    if data.get('learning_style') in ('Dengeli', 'Zaman bloklu', 'Mikro adım', 'Zorlayıcı'):
        p['learning_style'] = data['learning_style']
    return p


def save_preferences(con, student_id, preferences):
    _student_exists(con, student_id)
    p = _validated_preferences(preferences)
    with con:
        con.execute('''INSERT INTO adaptive_profile_v25(student_id, preferences_json, updated_at)
        VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(student_id) DO UPDATE SET
        preferences_json=excluded.preferences_json, updated_at=CURRENT_TIMESTAMP''',
        (int(student_id), json.dumps(p, ensure_ascii=False)))
    return p


def save_blocker(con, student_id, reason, detail='', *, homework_id=None, resolution=None):
    _student_exists(con, student_id)
    if reason not in REASONS[:-1]:
        raise ValueError('Tıkanıklık nedeni tanımlı değil.')
    if homework_id is not None:
        row = con.execute('SELECT ogrenci_id FROM odev WHERE id=?', (int(homework_id),)).fetchone()
        if row is None or int(row['ogrenci_id']) != int(student_id):
            raise ValueError('Ödev öğrenciye ait değil.')
    with con:
        cur = con.execute('''INSERT INTO adaptive_blocker_v25
           (student_id, homework_id, reason, detail, resolution) VALUES(?,?,?,?,?)''',
           (int(student_id), homework_id, reason, str(detail).strip()[:2000],
            (resolution or 'Koç değerlendirmesi bekliyor')[:2000]))
    return cur.lastrowid


def get_blockers(con, student_id, limit=100):
    _student_exists(con, student_id)
    return [dict(r) for r in con.execute('''SELECT * FROM adaptive_blocker_v25
        WHERE student_id=? ORDER BY id DESC LIMIT ?''', (int(student_id), int(limit)))]


def _is_lesson_valid_for_group(lesson: str, ana_grup: str) -> bool:
    if not ana_grup:
        return True
    grup = ana_grup.strip().upper()
    l_lower = lesson.strip().lower()
    if grup == 'LGS':
        if any(marker in l_lower for marker in ('ayt', 'tyt')):
            return False
        if l_lower in ('fizik', 'kimya', 'biyoloji', 'cografya', 'tarih', 'felsefe', 'edebiyat', 'geometri', 'problemler'):
            return False
        return True
    elif grup == 'YKS':
        if 'lgs' in l_lower:
            return False
        return True
    return True


def student_topics(con, student_id):
    """Merge legacy task history, coach topics and assessment data, without counting ticks as knowledge."""
    student_id = int(student_id)
    _student_exists(con, student_id)
    out = {}

    # Öğrencinin müfredat grubunu (LGS / YKS) kontrol et
    ana_grup = ''
    try:
        col_names = {c[1] for c in con.execute('PRAGMA table_info(ogrenci)').fetchall()}
        if 'ana_grup' in col_names:
            s_row = con.execute('SELECT ana_grup FROM ogrenci WHERE id=?', (student_id,)).fetchone()
            if s_row:
                ana_grup = str(s_row[0] or '').strip().upper()
    except Exception:
        pass

    # Öğrencinin aktif tanımlı kitaplarını (ogrenci_kitap) ders bazında yükle
    active_books_by_lesson = defaultdict(set)
    try:
        for b_row in con.execute(
            'SELECT ders, kitap_ad FROM ogrenci_kitap WHERE ogrenci_id=?',
            (student_id,),
        ):
            b_lesson = str(b_row[0] or '').strip().casefold()
            b_name = str(b_row[1] or '').strip().casefold()
            if b_lesson and b_name:
                active_books_by_lesson[b_lesson].add(b_name)
    except Exception:
        pass

    seen_active_cells = set()

    # Legacy `odev` is canonical for homework UI. No unsafe `odev_satir` double counting.
    for row in con.execute('''SELECT o.id AS homework_id, o.ders AS lesson,
       o.konu_ad AS topic, o.kitap_ad AS book, COALESCE(o.saat_dk,0) AS duration_min,
       COALESCE(o.durum,'') AS status, COALESCE(k.verilis_tarihi,'') AS assigned_on,
       COALESCE(k.bitis_tarihi,'') AS deadline
       FROM odev o JOIN odev_kume k ON k.id=o.kume_id
       WHERE o.ogrenci_id=? AND k.ogrenci_id=?
       ORDER BY k.verilis_tarihi DESC, o.id DESC LIMIT 1600''', (student_id, student_id)):
        d = dict(row)
        lesson_raw = (d['lesson'] or '').strip()
        topic_raw = (d['topic'] or '').strip()
        book_raw = (d['book'] or '').strip()
        if not lesson_raw or not topic_raw:
            continue
        if not _is_lesson_valid_for_group(lesson_raw, ana_grup):
            continue
        lesson_cf = lesson_raw.casefold()
        topic_cf = topic_raw.casefold()
        book_cf = book_raw.casefold()
        if lesson_cf in active_books_by_lesson:
            if not book_cf or book_cf not in active_books_by_lesson[lesson_cf]:
                continue
            cell_key = (lesson_cf, topic_cf, book_cf)
            if cell_key in seen_active_cells:
                continue
            seen_active_cells.add(cell_key)
        key = (lesson_cf, topic_cf)
        info = out.setdefault(key, {'lesson': lesson_raw, 'topic': topic_raw, 'book': '',
                                    'last_homework_id': None, 'last_assigned_on': None,
                                    'open_count': 0, 'done_count': 0, 'legacy_tasks': 0})
        if info['last_homework_id'] is None:
            info.update(book=book_raw, last_homework_id=d['homework_id'],
                        last_assigned_on=_date(d['assigned_on']))
        done = str(d['status']).lower() in ('tamam', 'yapildi', 'tamamlandi')
        info['done_count' if done else 'open_count'] += 1
        info['legacy_tasks'] += 1
    try:
        rows = con.execute('''SELECT ders_adi AS lesson, konu_adi AS topic,
           MAX(COALESCE(son_tekrar_tarihi,'')) AS last_review
           FROM koc_konu_takip WHERE ogrenci_id=? GROUP BY ders_adi, konu_adi''', (student_id,))
        for row in rows:
            lesson_raw = str(row['lesson'] or '').strip()
            topic_raw = str(row['topic'] or '').strip()
            if not lesson_raw or not topic_raw:
                continue
            if not _is_lesson_valid_for_group(lesson_raw, ana_grup):
                continue
            key = (lesson_raw.casefold(), topic_raw.casefold())
            info = out.setdefault(key, {'lesson': lesson_raw, 'topic': topic_raw, 'book': '',
                         'last_homework_id': None, 'last_assigned_on': None,
                         'open_count': 0, 'done_count': 0, 'legacy_tasks': 0})
            info['coach_last_review'] = _date(row['last_review'])
    except Exception:  # Older/limited coaching schema; optional input
        pass
    for row in observations(con, student_id, limit=1000):
        lesson_raw = row['lesson'].strip()
        topic_raw = row['topic'].strip()
        if not _is_lesson_valid_for_group(lesson_raw, ana_grup):
            continue
        key = (lesson_raw.casefold(), topic_raw.casefold())
        info = out.setdefault(key, {'lesson': lesson_raw, 'topic': topic_raw, 'book': '',
                    'last_homework_id': None, 'last_assigned_on': None,
                    'open_count': 0, 'done_count': 0, 'legacy_tasks': 0})
        info.setdefault('evidence', []).append(row)
    for topic in out.values():
        evs = sorted(topic.get('evidence', []), key=lambda e: (e['observed_on'],e['id']), reverse=True)
        # Same-day retests are logged, but the most recent evidence sets initial recall due date.
        total = sum(int(e['correct'])+int(e['wrong'])+int(e['blank']) for e in evs)
        correct = sum(int(e['correct']) for e in evs)
        topic['observations'] = len(evs)
        topic['attempts'] = total
        topic['accuracy'] = round(correct / total * 100) if total else None
        topic['last_observed_on'] = _date(evs[0]['observed_on']) if evs else None
        topic['latest_reason'] = next((e['reason'] for e in evs if e['reason'] != 'Belirtilmedi'), None)
        topic['subskills'] = sorted({e['subskill'] for e in evs if e['subskill']})
        # Do not promote checkbox completion to mastery. Two separate, sufficiently sized
        # checks are needed even for a tentative 'strong' evidence label.
        checks = [e for e in evs if e['correct']+e['wrong']+e['blank'] >= 5]
        strong = 0
        seen_days = set()
        # Separate days are required: retesting five times on one day is NOT
        # evidence of spaced retention. A failed recent check resets the streak.
        for e in checks:
            if e['correct'] / (e['correct']+e['wrong']+e['blank']) < .8:
                break
            if e['observed_on'] not in seen_days:
                seen_days.add(e['observed_on'])
                strong += 1
        topic['strong_checks'] = strong
        if not evs or total < 5:
            topic['level'] = 'Ölçüm gerekli'
        elif strong >= 2:
            topic['level'] = 'Olumlu kanıt (tekrar doğrula)'
        elif topic['accuracy'] is not None and topic['accuracy'] < 65:
            topic['level'] = 'Hedefli destek'
        else:
            topic['level'] = 'İzleme / karma tarama'
    return sorted(out.values(), key=lambda r: (r['lesson'].casefold(), r['topic'].casefold()))


def _stage(topic):
    strong = int(topic.get('strong_checks') or 0)
    if strong >= 4:
        return 3
    if strong >= 3:
        return 2
    if strong >= 2:
        return 1
    return 0


def student_overview(con, student_id, today=None):
    today = _date(today, date.today())
    topics = student_topics(con, student_id)
    measured = [x for x in topics if x['attempts'] >= 5]
    due = []
    for t in topics:
        last = t.get('last_observed_on') or t.get('coach_last_review') or t.get('last_assigned_on')
        # A legacy homework assignment is not a validated learning session.
        if (t['observations'] > 0 or t.get('coach_last_review')) and last and \
                today >= last + timedelta(days=DEFAULTS['spacing_days'][_stage(t)]):
            due.append(t)
    return {'topic_count': len(topics), 'measured_topics': len(measured),
            'need_measurement': sum(t['attempts'] < 5 for t in topics),
            'support_topics': sum(t['level'] == 'Hedefli destek' for t in topics),
            'due_topics': len(due), 'open_homework_rows': sum(t['open_count'] for t in topics),
            'blockers': len(get_blockers(con, student_id))}


def make_plan(con, student_id, preferences=None, *, today=None):
    """Deterministic, bounded draft: actual topics, no fictional mastery or auto-assignments."""
    today = _date(today, date.today())
    pref = _validated_preferences(preferences or load_preferences(con, student_id))
    topics = student_topics(con, student_id)
    max_min = pref['weekly_minutes']
    # A recently reported workload/time blocker reduces the proposed load,
    # NOT the student's stored preference and NOT any existing homework.
    recent_blockers = [b for b in get_blockers(con, student_id, limit=30)
        if _date(b['created_at']) and 0 <= (today - _date(b['created_at'])).days <= 14]
    reduced_for_blocker = any(b['reason'] in
        ('İş yükü', 'Zaman yönetimi', 'Erteleme / motivasyon') for b in recent_blockers)
    if reduced_for_blocker:
        max_min = max(30, round(max_min * 0.8))
    review_budget = round(max_min * pref['review_percent'] / 100)
    focus_budget = max_min - review_budget
    all_candidates = []
    for t in topics:
        last = t.get('last_observed_on') or t.get('coach_last_review') or t.get('last_assigned_on')
        due = bool(last and last + timedelta(days=pref['spacing_days'][_stage(t)]) <= today)
        recent = bool(last and (today - last).days < 15)
        is_support = t['level'] == 'Hedefli destek'
        is_unmeasured = t['attempts'] < 5
        # Unmeasured historical homework belongs in diagnosis, not automatic review.
        is_review = due and bool(t['observations'] > 0 or t.get('coach_last_review'))
        priority = (12 if is_support else 6 if is_unmeasured else 2) + (5 if due else 0)
        if t['open_count']:
            priority += 2
        all_candidates.append((priority, is_review, t))
    current = sorted((c for c in all_candidates if not c[1]), key=lambda x: (-x[0], x[2]['lesson'], x[2]['topic']))
    review = sorted((c for c in all_candidates if c[1]), key=lambda x: (-x[0], x[2]['lesson'], x[2]['topic']))
    # Unused budget is never forced to be filled with made-up topics.
    rows = []
    used = set()
    def take(pool, budget, kind):
        total = 0
        for _, _, t in pool:
            if total >= budget or len(rows) >= 25:
                break
            key = (t['lesson'], t['topic'])
            if key in used:
                continue
            if t['attempts'] < 5:
                mode = 'Geri getirme'
                details = 'Önce kısa hatırlama yoklaması; ardından 5–8 soruluk tanılama ve yanlış açıklaması.'
            elif t['level'] == 'Hedefli destek':
                mode = 'Hedefli soru'
                details = 'Önce hata nedenini tartış; alt kazanımı tanıla, seçilmiş az sayıda soru ile yeniden kontrol et.'
            elif kind == 'Aralıklı tekrar':
                mode = 'Karma mini sınav'
                details = 'Önceki konulardan karışık geri getirme ve en az bir yeni bağlam sorusu.'
            else:
                mode = 'Hedefli soru'
                details = 'Seviyeye uygun seçilmiş sorular ve çözüm yolunu kendi cümleleriyle açıklama.'
            if pref['learning_style'] == 'Zaman bloklu':
                details += ' Süre bitince bırak; yetişmeyeni otomatik borçlandırma.'
            elif pref['learning_style'] == 'Mikro adım':
                details += ' Önce örnek göster, sonra bir örnek birlikte çöz, ardından bağımsız dene.'
            elif pref['learning_style'] == 'Zorlayıcı':
                details += ' Hızdan önce gerekçelendirme; bağlamı değişen bir transfer sorusu kullan.'
            if t['subskills']:
                details = f"Odak: {', '.join(t['subskills'][:2])}. " + details
            if t['latest_reason']:
                details += ' Son gözlem: ' + t['latest_reason'] + '.'
            minutes = min(25 if mode == 'Hedefli soru' else 15,
                          pref['max_session_minutes'], budget - total)
            if minutes < 10:
                break
            total += minutes
            used.add(key)
            rows.append({'lesson': t['lesson'], 'topic': t['topic'], 'book': t.get('book',''),
                         'homework_id': t.get('last_homework_id'), 'category': kind,
                         'mode': mode, 'minutes': minutes, 'details': details,
                         'level': t['level'], 'is_legacy_transferable': bool(t.get('book')),
                         'needs_teacher_approval': True})
        return total
    r_minutes = take(review, review_budget, 'Aralıklı tekrar')
    f_minutes = take(current, focus_budget, 'Güncel odak')
    review_rows = [r for r in rows if r['category']=='Aralıklı tekrar']
    # Interleaving needs more than one actual topic. Never call a single-topic
    # assignment a mixed test; attach real partner topics when available.
    for item in review_rows:
        partners = [f"{r['lesson']}/{r['topic']}" for r in review_rows
                    if (r['lesson'],r['topic']) != (item['lesson'],item['topic'])][:3]
        if partners:
            item['mode'] = 'Karma mini sınav'
            item['details'] += ' Karma eşleştirme: ' + '; '.join(partners) + '.'
        elif item['mode']=='Karma mini sınav':
            item['mode'] = 'Geri getirme'
            item['details'] += ' İkinci tekrar konusu bulunmadığı için karma test oluşturulmadı.'
    # Safety: when some categories are empty, use remaining time sparingly, not forced to full.
    return {'version': VERSION, 'student_id': int(student_id), 'generated_on': today.isoformat(),
            'preferences': pref, 'items': rows, 'review_minutes': r_minutes,
            'focus_minutes': f_minutes, 'planned_minutes': r_minutes+f_minutes,
            'unused_minutes': max_min-r_minutes-f_minutes,
            'effective_weekly_minutes': max_min,
            'warnings': (["Yakın tarihli iş yükü/zaman tıkanıklığı: önerilen haftalık süre %20 azaltıldı; mevcut ödevler değişmedi."]
                         if reduced_for_blocker else []) + (["Henüz konu kaydı bulunamadı; öneri oluşturulmadı."] if not topics else []) +
                        (["Kazanım ölçümleri az; öneriler tanılama odaklıdır, ustalık puanı değildir."]
                         if not any(x['attempts']>=5 for x in topics) and topics else []) +
                        (["Yapılmamış eski ödevler doğrudan devredilmez; neden analizi yapın."]
                         if any(t['open_count'] for t in topics) else [])}


def save_plan(con, student_id, plan):
    _student_exists(con, student_id)
    if int(plan.get('student_id', -1)) != int(student_id):
        raise ValueError('Plan öğrenci kimliği uyuşmuyor.')
    with con:
        cur = con.execute('''INSERT INTO adaptive_plan_v25(student_id, preferences_json,plan_json)
        VALUES(?,?,?)''', (int(student_id), json.dumps(plan['preferences'], ensure_ascii=False),
                             json.dumps(plan, ensure_ascii=False)))
    return cur.lastrowid
