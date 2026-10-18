# -*- coding: utf-8 -*-
"""Read-only projection for the Homework Form's optional adaptive right panel.

A completed checkbox is NOT diagnostic evidence. No grades, risk scores, or
fictitious dates are generated. The suggested 70/30 ratio is configurable,
not a measured fraction of actual assignments.
"""
from __future__ import annotations
import sqlite3
from datetime import date
from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v26.decision import student_decisions, has_v25_data


def sidebar_data(con, student_id: int, *, today=None):
    sid = int(student_id)
    day = engine._date(today, date.today())
    record = con.execute('SELECT ad, soyad FROM ogrenci WHERE id=?', (sid,)).fetchone()
    if record is None:
        raise ValueError('Öğrenci bulunamadı.')
    # Can be called with a SQLite read-only connection; no schema creation.
    brief = student_decisions(con, sid, today=day, maximum=18)
    obs = has_v25_data(con)
    preferences = engine.load_preferences(con, sid) if obs else dict(engine.DEFAULTS)
    review_pct = preferences['review_percent']
    grouped = {'Hedefli destek':[], 'Ölçüm gerekli':[], 'İlk tanılama':[],
               'Aralıklı tekrar':[], 'Yük dengeleme':[], 'Diğer':[]}
    for action in brief['actions']:
        category = action['category']
        grouped[category if category in grouped else 'Diğer'].append(action)
    recent_blockers = []
    if obs:
        for b in engine.get_blockers(con, sid, limit=15):
            observed = engine._date(b['created_at'])
            if observed is not None and (day - observed).days <= 14 and observed <= max(day, date.today()):
                recent_blockers.append({'reason': b['reason'], 'detail': b['detail'],
                                        'resolution': b['resolution']})
    # V28 is a separate, explicit teacher observation, NOT measured mastery.
    # Read lazily only when the optional right panel is opened/refreshed.
    try:
        from services.adaptive_coaching_v28.flags import enabled as quick_notes_enabled
        if quick_notes_enabled():
            from services.adaptive_coaching_v28.quick_notes import recent_notes
            quick_notes = recent_notes(con, sid, today=day, limit=10)
        else:
            quick_notes = []
    except (ImportError, ValueError):
        quick_notes = []
    # V29 suggestions are strictly read-only, bounded and evaluated only
    # on this explicit sidebar refresh (never on checkbox signals).
    next_steps = []
    try:
        from services.adaptive_coaching_v29.flags import enabled as next_enabled
        if next_enabled():
            from services.adaptive_coaching_v29.next_steps import student_next_steps
            next_steps = student_next_steps(con,sid,today=day,limit=3)
    except (ImportError, sqlite3.Error, ValueError):
        # Optional advisor must not break the original right-hand panel.
        next_steps = []
    # V34 view model reuses already loaded data, without further SQL reads.
    journey = None
    try:
        from services.adaptive_coaching_v34.flags import enabled as v34_enabled
        if v34_enabled():
            from services.adaptive_coaching_v34.journey import compose_journey
            journey = compose_journey(sid, brief, quick_notes, next_steps)
    except ImportError:
        journey = None  # Optional V34 module absent; V27 continues.
    name = ' '.join(str(record[k] or '').strip() for k in ('ad', 'soyad')).strip()
    return {
        'student_id':sid, 'name':name or f'Öğrenci #{sid}',
        'status':brief['status'], 'evidence_count':brief['evidence_count'],
        'metrics':brief['metrics'], 'context':brief.get('context', {}),
        'warnings':brief['warnings'], 'actions':brief['actions'],
        'groups':grouped, 'blockers':recent_blockers, 'quick_notes':quick_notes, 'next_steps':next_steps,
        'learning_journey_v34':journey,
        'has_evidence_storage':obs,
        'suggested_current_percent':100-review_pct,
        'suggested_review_percent':review_pct,
        'weekly_minutes':preferences['weekly_minutes'],
        'suggested_session_minutes':preferences['max_session_minutes'],
        'guidance': ('Öneri için en az bir bağımsız kazanım yoklaması yapın.'
                     if brief['evidence_count']==0 else
                     'Ölçüm sonuçlarını alt kazanım ve farklı günlerdeki tekrarlarla doğrulayın.'),
        'as_of':day.isoformat(),
    }
