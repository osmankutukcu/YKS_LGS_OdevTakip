# -*- coding: utf-8 -*-
"""Read-only opt-in between adaptive observations and the weekly planner.

Only existing lesson/topic pairs are eligible. The coach suggests an optional
lesson focus, not a diagnosis, grade, new task, or automatically approved plan.
No Qt, schema migrations, writes, or implicit homework changes.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from services.adaptive_coaching_v29.next_steps import student_next_steps


def _day(value):
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _key(value):
    return str(value or '').strip().casefold()


def suggested_lesson_focus(con, student_id, assigned_tasks, *, today=None):
    """Bounded, student-owned suggestions. No writes; never adds homework."""
    sid = int(student_id)
    if sid <= 0 or not con.execute('SELECT 1 FROM ogrenci WHERE id=?', (sid,)).fetchone():
        raise ValueError('Geçerli öğrenci bulunamadı.')
    day = _day(today)
    eligible = {}
    for task in list(assigned_tasks or [])[:250]:
        if not isinstance(task, dict):
            continue
        lesson, topic = str(task.get('ders') or '').strip(), str(task.get('konu') or '').strip()
        if lesson and topic:
            eligible.setdefault((_key(lesson), _key(topic)), (lesson, topic))
    if not eligible:
        return []

    reasons = {}
    # Explicit teacher notes are hypotheses, not proof of mastery or diagnosis.
    # Workload and ease notes must not automatically increase study load.
    for note in student_next_steps(con, sid, today=day, limit=5):
        pair = (_key(note.get('lesson')), _key(note.get('topic')))
        if pair in eligible and note.get('teacher_note') in ('concept', 'difficulty', 'attention', 'time'):
            reasons.setdefault(pair, []).append('Öğretmen notu: ' + str(note.get('title') or 'Kısa yoklama')[:100])

    present = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='adaptive_observation_v25'").fetchone()
    if present:
        since = (day - timedelta(days=28)).isoformat()
        for pair, (lesson, topic) in list(eligible.items())[:50]:
            obs = con.execute('''SELECT correct,wrong,blank,observed_on
                FROM adaptive_observation_v25 WHERE student_id=? AND lesson=? AND topic=?
                AND observed_on BETWEEN ? AND ? ORDER BY observed_on DESC,id DESC LIMIT 2''',
                (sid, lesson, topic, since, day.isoformat())).fetchall()
            if obs:
                correct, wrong, blank = (max(0, int(obs[0][k] or 0)) for k in ('correct', 'wrong', 'blank'))
                total = correct + wrong + blank
                if total >= 5 and correct / total < 0.65:
                    reasons.setdefault(pair, []).append(
                        f'Son bağımsız ölçüm {correct}/{total} doğru: kısa yeniden yoklama önerisi')

    focus = {}
    for pair, notes in reasons.items():
        lesson, topic = eligible[pair]
        bucket = focus.setdefault(_key(lesson), {'lesson': lesson, 'topics': [], 'reasons': []})
        if topic not in bucket['topics']:
            bucket['topics'].append(topic)
        for message in notes:
            bucket['reasons'].append(f'{topic}: {message}')
    result = list(focus.values())
    result.sort(key=lambda entry: (-len(entry['reasons']), entry['lesson'].casefold()))
    return result[:5]


def merge_teacher_approved_focus(existing_focus, candidates):
    """Preserve the existing manual list. Called only after teacher approval."""
    original = [s.strip() for s in str(existing_focus or '').split(',') if s.strip()]
    known = {_key(x) for x in original}
    for suggestion in candidates:
        lesson = str(suggestion.get('lesson') or '').strip()
        if lesson and _key(lesson) not in known:
            original.append(lesson)
            known.add(_key(lesson))
    return ', '.join(original)
