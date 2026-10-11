"""Günün Akıllı Özeti: conservative, read-only evidence layer.

No student activity or learning outcome is inferred from the date an assignment
was created. The result is a teacher review queue, not a clinical risk score.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

DONE = frozenset(('tamam', 'yapildi', 'bitti'))


def parse_day(value: Any) -> date | None:
    if isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value
    value = str(value or '').strip()
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def days_since(value: Any, today: date) -> int | None:
    parsed = parse_day(value)
    if parsed is None or parsed > today:
        return None
    return (today - parsed).days


def tracking_indicator(facts: dict) -> int | None:
    """0–100 non-validated workload FOLLOW-UP indicator; None => no evidence."""
    if not facts.get('has_assignment_history'):
        return None
    new_overdue = max(int(facts.get('overdue_recent', 0)), 0)
    old_overdue = max(int(facts.get('overdue_old', 0)), 0)
    days = facts.get('days_since_assigned')
    score = min(8 * new_overdue, 48) + min(2 * old_overdue, 16)
    # Absence of NEW teacher assignment is not evidence of student inactivity.
    # It is reported as administrative follow-up, not added to the student indicator.
    return max(0, min(100, score))


def collect_student_facts(con, today: date | None = None) -> list[dict]:
    today = today or date.today()
    cutoff = today - timedelta(days=30)
    week = today - timedelta(days=7)
    students = [dict(r) for r in con.execute(
        "SELECT id, ad, soyad, dogum_tarihi, veli_tel1 FROM ogrenci WHERE aktif=1"
    ).fetchall()]
    facts_by_id = {}
    for st in students:
        st.update(overdue_recent=0, overdue_old=0, completed_in_recent_set=0,
                  has_assignment_history=False, last_assignment_date=None,
                  days_since_assigned=None, problem_lesson=None, problem_count=0, overdue_refs=[],
                  best_lesson=None, best_count=0)
        facts_by_id[int(st['id'])] = st
    overdue_by_lesson = defaultdict(lambda: defaultdict(int))
    done_by_lesson = defaultdict(lambda: defaultdict(int))
    # SQL JOIN also ensures student_id matches both sides; orphaned cross-student
    # rows must never be silently attributed to another student.
    rows = con.execute('''
        SELECT o.id AS assignment_id, o.ogrenci_id, o.ders, o.durum, k.verilis_tarihi, k.bitis_tarihi
        FROM odev AS o JOIN odev_kume AS k
          ON k.id=o.kume_id AND k.ogrenci_id=o.ogrenci_id
        JOIN ogrenci AS s ON s.id=o.ogrenci_id AND s.aktif=1
    ''').fetchall()
    for row in rows:
        r = dict(row)
        sid = int(r['ogrenci_id'])
        facts = facts_by_id.get(sid)
        if facts is None:
            continue
        facts['has_assignment_history'] = True
        issued = parse_day(r.get('verilis_tarihi'))
        due = parse_day(r.get('bitis_tarihi'))
        last = facts['last_assignment_date']
        if issued and issued <= today and (last is None or issued > last):
            facts['last_assignment_date'] = issued
        status = str(r.get('durum') or 'devam').strip().lower()
        lesson = str(r.get('ders') or 'Bilinmeyen Ders').strip()
        if status in DONE:
            if issued and week <= issued <= today:
                facts['completed_in_recent_set'] += 1
                done_by_lesson[sid][lesson] += 1
        elif status == 'devam' and due is not None and due < today:
            kind = 'overdue_recent' if due >= cutoff else 'overdue_old'
            facts[kind] += 1
            # Identifies changed overdue evidence even when aggregate counts stay the same.
            facts['overdue_refs'].append(f"{r['assignment_id']}:{due.isoformat()}")
            overdue_by_lesson[sid][lesson] += 1
    for sid, f in facts_by_id.items():
        f['days_since_assigned'] = days_since(f['last_assignment_date'], today)
        if overdue_by_lesson[sid]:
            f['problem_lesson'], f['problem_count'] = max(
                overdue_by_lesson[sid].items(), key=lambda kv: (kv[1], kv[0]))
        if done_by_lesson[sid]:
            f['best_lesson'], f['best_count'] = max(
                done_by_lesson[sid].items(), key=lambda kv: (kv[1], kv[0]))
        f['tracking_indicator'] = tracking_indicator(f)
    return list(facts_by_id.values())


def make_suggestions(facts: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    tomorrow = today + timedelta(days=1)
    out = []

    def push(kind, priority, f, title, desc, reasons, action=None, icon='🔎',
             color='#EFF6FF', border='#64748B'):
        out.append({'type': kind, 'priority': priority, 'title': title,
                    'desc': desc, 'reasons': reasons, 'data': f, 'risk': f.get('tracking_indicator'),
                    'action': action, 'icon': icon, 'color': color, 'border': border})

    for f in facts:
        ad = str(f.get('ad') or 'Öğrenci').strip()
        recent = int(f.get('overdue_recent') or 0)
        old = int(f.get('overdue_old') or 0)
        elapsed = f.get('days_since_assigned')
        if recent or old:
            bits = []
            if recent:
                bits.append(f'Son 30 günde süresi dolan {recent} açık ödev')
            if old:
                bits.append(f'Daha eski {old} açık ödev')
            reasons = bits + ['Yalnızca ödev kayıtları incelendi; öğrenme düzeyi belirlenmedi.']
            if f.get('problem_lesson'):
                reasons.append(f"En çok gecikme kaydı: {f['problem_lesson']} ({f['problem_count']} ödev)")
            push('overdue', 1, f, f'⚠️ {ad} • Geciken ödev kontrolü',
                 ' · '.join(bits) + '. Listeyi ve güncel durumu doğrulayın.',
                 reasons, 'Uyar', '⏳', '#FFF7ED', '#EA580C')
        elif elapsed is not None and elapsed >= 14:
            push('silent', 2, f, f'📋 {ad} • Yeni ödev kaydı yok',
                 f'{elapsed} gündür yeni ödev verilmemiş görünüyor. Öğrencinin çalışmadığı anlamına gelmez.',
                 ['Ödev kümesinin son veriliş tarihi esas alındı.',
                  'Ders çalışma, takip görüşmesi veya başka uygulamadaki çalışmalar ölçülmedi.'],
                 'Planla', '📋', '#F1F5F9', '#64748B')
        elif not f.get('has_assignment_history'):
            push('silent', 5, f, f'📋 {ad} • Takip kaydı bulunamadı',
                 'Bu uygulamada ödev kaydı yok. Öğrencinin çalışmadığı sonucuna varılamaz.',
                 ['Ödev veri kaynağında kayıt bulunamadı.'],
                 'Planla', '📋', '#F8FAFC', '#94A3B8')
        elif f['completed_in_recent_set'] >= 5:
            push('star', 3, f, f'🌟 {ad} • Tamamlanan ödevler',
                 f"Son 7 günde verilen ödevlerden {f['completed_in_recent_set']} tanesi tamamlandı durumunda.",
                 ['Tamamlanma tarihi ayrı tutulmadığı için bu hafta ne zaman yapıldığı bilinmiyor.',
                  'Ödev tamamlanması sınav başarısının doğrudan kanıtı değildir.'],
                 'Tebrik Et', '🌟', '#FFFBEB', '#D97706')

        birthday = parse_day(f.get('dogum_tarihi'))
        if birthday:
            bday = (birthday.month, birthday.day)
            if bday in ((today.month, today.day), (tomorrow.month, tomorrow.day)):
                is_today = bday == (today.month, today.day)
                push('birthday', 4, f,
                     f"🎂 {'Bugün' if is_today else 'Yarın'} {ad} için özel gün",
                     'Kayıtlı doğum tarihine dayalı hatırlatma.',
                     ['Öğrenci kartındaki doğum tarihi takvimle eşleşti.'],
                     'Kutla' if is_today else 'Planla', '🎂', '#FDF2F8', '#DB2777')
    return sorted(out, key=lambda s: (s['priority'], -(s['data'].get('overdue_recent') or 0),
                                      str(s['data'].get('ad') or '')))
