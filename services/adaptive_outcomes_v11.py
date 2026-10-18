# -*- coding: utf-8 -*-
"""V11: teacher-approved intervention follow-up for existing V25 evidence.

Never writes homework, student records or learning measurements. A teacher
creates a follow-up entry explicitly; evidence comparison is read-only and
cannot establish causality. No psychological diagnosis or automatic assignments.
"""
from __future__ import annotations

from datetime import date, timedelta
import sqlite3

ACTIONS = {
    'micro_check': 'Kısa bağımsız yoklama',
    'spaced_review': 'Aralıklı tekrar denemesi',
    'error_review': 'Yanlış çözümünü inceleme',
    'study_adjust': 'Çalışma stratejisini değiştirme',
    'prerequisite': 'Önkoşul kazanımı yoklama',
}
REVIEWS = {'helpful': 'Yararlı bulundu', 'not_helpful': 'Yararlı bulunmadı',
           'unclear': 'Sonuç belirsiz'}


def _day(value, *, default=None):
    if value is None:
        return default or date.today()
    if type(value) is date:
        return value
    if type(value) is str and len(value) == 10:
        return date.fromisoformat(value)
    raise ValueError('Tarih YYYY-AA-GG biçiminde olmalıdır.')


def _id(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} geçersiz.')
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} geçersiz.') from exc
    if result <= 0:
        raise ValueError(f'{name} geçersiz.')
    return result


def _text(value, name, limit=140):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f'{name} boş veya fazla uzun.')
    return value.strip()


def _exists(con, table):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def _owns_student(con, sid):
    if not con.execute('SELECT 1 FROM ogrenci WHERE id=?', (sid,)).fetchone():
        raise ValueError('Öğrenci bulunamadı; işlem yapılmadı.')


def ensure_schema(con):
    """Called *only* after a teacher clicks to record a follow-up."""
    con.execute('''CREATE TABLE IF NOT EXISTS adaptive_intervention_v11 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
        lesson TEXT NOT NULL, topic TEXT NOT NULL,
        action_code TEXT NOT NULL, applied_on TEXT NOT NULL,
        rationale TEXT NOT NULL DEFAULT '',
        teacher_review TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK(length(lesson)>0 AND length(topic)>0)
    )''')
    con.execute('''CREATE INDEX IF NOT EXISTS idx_adaptive_intervention_v11_student
        ON adaptive_intervention_v11(student_id, applied_on DESC, id DESC)''')


def record_intervention(con, student_id, lesson, topic, action_code, *,
                        applied_on=None, rationale='', teacher_confirmed=False):
    """Explicit teacher-initiated write. Commits only V11 ledger, not legacy homework."""
    if teacher_confirmed is not True:
        raise ValueError('Öğretmen onayı olmadan müdahale kaydedilemez.')
    sid = _id(student_id, 'Öğrenci')
    lesson, topic = _text(lesson, 'Ders'), _text(topic, 'Konu')
    if action_code not in ACTIONS:
        raise ValueError('Tanımsız takip adımı.')
    day = _day(applied_on)
    if day > date.today():
        raise ValueError('Gelecekte yapılmamış bir müdahale kaydedilemez.')
    if day < date.today() - timedelta(days=365):
        raise ValueError('Takip başlangıcı bir yıldan eski olamaz.')
    if not isinstance(rationale, str) or len(rationale) > 500:
        raise ValueError('Açıklama uzunluğu geçersiz.')
    _owns_student(con, sid)
    # BEGIN/commit via with con: only action log and its index created.
    with con:
        ensure_schema(con)
        cur = con.execute('''INSERT INTO adaptive_intervention_v11
           (student_id,lesson,topic,action_code,applied_on,rationale)
           VALUES (?,?,?,?,?,?)''',
           (sid,lesson,topic,action_code,day.isoformat(),rationale.strip()))
        return int(cur.lastrowid)


def list_interventions(con, student_id, *, limit=15):
    """No schema changes, strict student-scoped read."""
    sid = _id(student_id, 'Öğrenci')
    _owns_student(con, sid)
    if not _exists(con, 'adaptive_intervention_v11'):
        return []
    n = max(1, min(30, int(limit)))
    cur = con.execute('''SELECT id,student_id,lesson,topic,action_code,
                     applied_on,rationale,teacher_review FROM adaptive_intervention_v11
                     WHERE student_id=? ORDER BY applied_on DESC, id DESC LIMIT ?''',(sid,n))
    return [dict(zip([c[0] for c in cur.description],r)) for r in cur.fetchall()]


def _aggregate(con, sid, lesson, topic, from_day, to_day):
    """Exact student, subject and topic; no assignment-tick proxy as evidence."""
    if not _exists(con, 'adaptive_observation_v25'):
        return {'days': 0, 'items': 0, 'correct': 0, 'attempts': 0, 'accuracy': None}
    rows = con.execute('''SELECT observed_on,correct,wrong,blank
        FROM adaptive_observation_v25
        WHERE student_id=? AND lesson=? AND topic=?
          AND observed_on>=? AND observed_on<=?
        ORDER BY observed_on DESC,id DESC LIMIT 300''',
        (sid,lesson,topic,from_day.isoformat(),to_day.isoformat())).fetchall()
    valid = []
    for day,c,w,b in rows:
        if any(type(x) is not int or x < 0 for x in (c,w,b)):
            continue
        total = c+w+b
        if total >= 5:
            valid.append((str(day)[:10], c, total))
    attempts = sum(x[2] for x in valid)
    correct = sum(x[1] for x in valid)
    return {'days': len({x[0] for x in valid}), 'items':len(valid),
            'correct': correct,'attempts': attempts,
            'accuracy':round(100 * correct / attempts,1) if attempts else None}


def evaluate_intervention(con, student_id, intervention_id, *, as_of=None):
    """Read-only description of *observed association*, NEVER inferred causal effect.

    Baseline excludes intervention day; follow-up excludes that day as well.
    Requires >=2 distinct observation days and >=10 questions in EACH period
    before exposing difference. Max 45-day windows; no cross-topic evidence.
    """
    sid, iid = _id(student_id,'Öğrenci'), _id(intervention_id,'Müdahale')
    day = _day(as_of)
    _owns_student(con,sid)
    if not _exists(con,'adaptive_intervention_v11'):
        raise ValueError('Bu öğrenci için takip kaydı bulunamadı.')
    row = con.execute('''SELECT id,student_id,lesson,topic,action_code,
        applied_on,rationale,teacher_review FROM adaptive_intervention_v11
        WHERE id=? AND student_id=?''',(iid,sid)).fetchone()
    if row is None:
        raise ValueError('Takip kaydı bu öğrenciye ait değil.')
    rid,rsid,lesson,topic,code,when,rationale,review=row
    started = _day(when)
    baseline = _aggregate(con,sid,lesson,topic,started-timedelta(days=45),started-timedelta(days=1))
    follow_end = min(day,started+timedelta(days=45))
    followup = (_aggregate(con,sid,lesson,topic,started+timedelta(days=1),follow_end)
                if follow_end > started else {'days':0,'items':0,'correct':0,'attempts':0,'accuracy':None})
    ready = all(x['days']>=2 and x['attempts']>=10 for x in (baseline,followup))
    delta = (round(followup['accuracy']-baseline['accuracy'],1) if ready else None)
    if not ready:
        status = 'Karşılaştırma için yeterli bağımsız ölçüm yok'
        advice = 'Öncesinde ve sonrasında en az iki ayrı günde ≥5 soruluk ölçüm gerekir.'
    else:
        status = f'Doğruluk değişimi: {delta:+.1f} yüzde puan (nedensellik göstermez)'
        advice = ('Farklı soru güçlükleri ve başka etkenler sonucu değiştirmiş olabilir; '
                  'öğretmen, yöntemi gözden geçirerek sonraki ölçümü planlamalı.')
    return {'id':rid,'student_id':rsid,'lesson':lesson,'topic':topic,
            'action_code':code,'action_name':ACTIONS.get(code,'Bilinmeyen adım'),
            'applied_on':when,'teacher_review':review,'baseline':baseline,
            'followup':followup,'ready':ready,'delta_percentage_points':delta,
            'status':status,'next_step':advice,
            'warning':'Ödev tiki, tanı veya müdahalenin etkisine dair nedensel kanıt değildir.'}


def review_intervention(con, student_id, intervention_id, review):
    """Teacher-only qualitative feedback; does not change recommendation weights."""
    sid,iid = _id(student_id,'Öğrenci'),_id(intervention_id,'Müdahale')
    if review not in REVIEWS:
        raise ValueError('Değerlendirme geçersiz.')
    _owns_student(con,sid)
    if not _exists(con,'adaptive_intervention_v11'):
        raise ValueError('Takip kaydı bulunamadı.')
    with con:
        cur=con.execute('''UPDATE adaptive_intervention_v11 SET teacher_review=?
                 WHERE student_id=? AND id=?''',(review,sid,iid))
        if cur.rowcount!=1:
            raise ValueError('Değerlendirme bu öğrenciye ait değil.')


def compact_followup_text(con, student_id, *, as_of=None):
    """One short safe snippet for the existing Student 360 workspace."""
    rows = list_interventions(con,student_id,limit=1)
    if not rows:
        return 'Henüz onaylanmış müdahale takibi yok.'
    r = evaluate_intervention(con,student_id,rows[0]['id'],as_of=as_of)
    return (f"{r['lesson']} / {r['topic']} · {r['action_name']} ({r['applied_on']})\n"
            f"{r['status']}\n{r['next_step']}")
