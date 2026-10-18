# -*- coding: utf-8 -*-
"""V3.5.39 — anonymous, descriptive patterns from teacher-approved V11 outcomes.

No new storage, persistent weights, causal claims, predictions, ranking, homework
writes, notifications or background sends. Only teacher-approved local observations
are summarized. Small groups are suppressed, even if all reviews are positive.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import sqlite3

from services.adaptive_outcomes_v11 import ACTIONS, evaluate_intervention

_REVIEW_CODES = ('helpful', 'not_helpful', 'unclear')
_REQUIRED_INTERVENTION = {'id','student_id','lesson','topic','action_code','applied_on','teacher_review','rationale'}
_REQUIRED_STUDENT = {'id','aktif'}
_REQUIRED_OBSERVATION = {'id','student_id','lesson','topic','correct','wrong','blank','observed_on'}


def _day(as_of):
    if as_of is None:
        return date.today()
    if type(as_of) is date:
        return as_of
    if type(as_of) is str and len(as_of) == 10:
        d = date.fromisoformat(as_of)
        if d.isoformat() == as_of:
            return d
    raise ValueError('Geçerli değerlendirme tarihi YYYY-AA-GG olmalı.')


def _columns(con, table):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return set()
    return {r[1] for r in con.execute('PRAGMA table_info("' + table + '")')}


def _optional_label(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
        raise ValueError(f'{field} geçersiz.')
    return value.strip()


def read_historical_patterns(con: sqlite3.Connection, *, as_of=None,
                             lesson=None, topic=None, max_scan=120, max_groups=3,
                             minimum_students=5) -> dict:
    """Bounded institution-level *descriptive* historical evidence, read-only.

    - Only active learners, teacher-reviewed V11 interventions in last 365 days.
    - At most ONE recent intervention per student+lesson+topic: repeat
      interventions from one learner cannot masquerade as independent cases.
    - At least five distinct learners AND five adequate before/after comparisons
      before exposing outcome directions; never expose learner identifiers.
    - A subset or unavailable schema is never interpreted as no problem.
    - No effect sizes, advice scores, automated priority changes, or claims of
      intervention effectiveness. Outcomes are confounded observational signals.
    """
    day = _day(as_of)
    lesson, topic = _optional_label(lesson, 'Ders'), _optional_label(topic, 'Konu')
    if type(max_scan) is not int or not 1 <= max_scan <= 500:
        raise ValueError('Tarama sınırı 1-500 olmalı.')
    if type(max_groups) is not int or not 1 <= max_groups <= 10:
        raise ValueError('Grup sınırı 1-10 olmalı.')
    if type(minimum_students) is not int or not 5 <= minimum_students <= 20:
        raise ValueError('Anonimlik eşiği en az 5 olmalı.')
    common = {'as_of': day.isoformat(), 'lesson': lesson, 'topic': topic,
              'source': 'local_teacher_approved_v11_and_independent_v25',
              'student_data_written': False, 'recommendation_weights_updated': False,
              'automatic_assignments': False, 'remote_verified': False,
              'causal_claim': False, 'minimum_students': minimum_students,
              'warning': ('Öncesi/sonrası gözlem ve öğretmen yorumu, müdahalenin '
                          'etkisini veya başka öğrencilere uygunluğunu kanıtlamaz.')}
    schema = {
        'adaptive_intervention_v11': _REQUIRED_INTERVENTION,
        'ogrenci': _REQUIRED_STUDENT,
        'adaptive_observation_v25': _REQUIRED_OBSERVATION,
    }
    if not _columns(con, 'adaptive_intervention_v11'):
        return {**common, 'state': 'NO_APPROVED_HISTORY', 'sampled': 0, 'patterns': []}
    if any(not cols.issubset(_columns(con, table)) for table, cols in schema.items()):
        return {**common, 'state': 'SOURCE_UNVERIFIED', 'sampled': 0, 'patterns': []}
    clause = ''
    args = [day.isoformat(), (day - timedelta(days=365)).isoformat()]
    if lesson is not None:
        clause += ' AND i.lesson=?'
        args.append(lesson)
    if topic is not None:
        clause += ' AND i.topic=?'
        args.append(topic)
    # Dates are text, so malformed input is NOT allowed to manufacture evidence.
    # A row limit always declares partial coverage; no cross-institution ranking.
    query = f'''WITH ranked AS (
       SELECT i.id,i.student_id,i.lesson,i.topic,i.action_code,i.applied_on,i.teacher_review,
              ROW_NUMBER() OVER (PARTITION BY i.student_id,i.lesson,i.topic
                 ORDER BY i.applied_on DESC,i.id DESC) rn
       FROM adaptive_intervention_v11 i JOIN ogrenci o ON o.id=i.student_id
       WHERE o.aktif=1 AND i.teacher_review IN ('helpful','not_helpful','unclear')
         AND i.applied_on<=? AND i.applied_on>=? {clause}
    ) SELECT id,student_id,lesson,topic,action_code,applied_on,teacher_review
        FROM ranked WHERE rn=1 ORDER BY applied_on DESC,id DESC LIMIT ?'''
    rows = con.execute(query, (*args, max_scan+1)).fetchall()
    limited = len(rows) > max_scan
    rows = rows[:max_scan]
    groups = defaultdict(list)
    incomplete = 0
    for iid,sid,l,t,code,applied,review in rows:
        try:
            started = _day(applied)
            if started > day or code not in ACTIONS or not l or not t:
                raise ValueError('Invalid historical intervention')
            result = evaluate_intervention(con,int(sid),int(iid),as_of=day)
            if result.get('student_id') != sid or result.get('teacher_review') != review:
                raise ValueError('Mismatched evidence identity')
        except (sqlite3.Error, ValueError, TypeError, KeyError):
            incomplete += 1
            continue
        groups[(l,t,code)].append((sid,review,result))
    patterns = []
    for (l,t,code),records in groups.items():
        distinct_students = len({r[0] for r in records})
        if distinct_students < minimum_students:
            continue  # strict suppression; don't publish tiny groups
        valid = [r for r in records if r[2]['ready'] and type(r[2]['delta_percentage_points']) in (int,float)]
        ready_students = len({r[0] for r in valid})
        if ready_students < minimum_students:
            # No outcome inference with sparse measures; disclose insufficiency
            # only after teacher-reviewed sample reaches anonymity threshold.
            patterns.append({'lesson':l,'topic':t,'action_code':code,'action_name':ACTIONS[code],
                'state':'INSUFFICIENT_INDEPENDENT_MEASUREMENTS',
                'approved_records':len(records),'distinct_students':distinct_students,
                'measured_students':ready_students, 'directions': None,
                'teacher_reviews': None,
                'interpretation':'Öncesi ve sonrası bağımsız ölçüm yeterli değil; yöntem önerilemez.'})
            continue
        directions = {'higher':0,'similar':0,'lower':0}
        reviews = {'helpful':0,'not_helpful':0,'unclear':0}
        for sid,review,result in valid:
            delta = result['delta_percentage_points']
            directions['higher' if delta>=5 else 'lower' if delta<=-5 else 'similar'] += 1
            reviews[review] += 1
        patterns.append({'lesson':l,'topic':t,'action_code':code,'action_name':ACTIONS[code],
            'state':'DESCRIPTIVE_HISTORY','approved_records':len(records),
            'distinct_students':distinct_students,'measured_students':ready_students,
            'directions':directions,'teacher_reviews':reviews,
            'interpretation':('Benzer başlıklardaki geçmiş takip gözlemlerinin dağılımı. '
                              'Farklı öğrenci ve soru zorluğu nedeniyle fayda, tahmin veya sıralama değildir.')})
    patterns.sort(key=lambda p: (-int(p['state']=='DESCRIPTIVE_HISTORY'),
                                 -p['measured_students'], -p['distinct_students'],
                                 p['lesson'],p['topic'],p['action_code']))
    return {**common, 'state':'PARTIAL_COVERAGE' if limited or incomplete else
                   'DESCRIPTIVE_HISTORY' if patterns else 'INSUFFICIENT_GROUP_SIZE',
            'sampled':len(rows),'incomplete_records':incomplete,
            'limited':limited,'patterns':patterns[:max_groups],
            'available_groups':len(patterns)}


def compact_history_line(result: dict) -> str | None:
    """Show descriptive counts, disclosing partial coverage when necessary."""
    if not isinstance(result, dict):
        return None
    state = result.get('state')
    if state == 'SOURCE_UNVERIFIED':
        return 'Geçmiş müdahale kaynağı doğrulanamadı; öneriler değiştirilmedi.'
    for p in result.get('patterns') or []:
        if p.get('state') == 'DESCRIPTIVE_HISTORY':
            d = p['directions']
            prefix = 'Kısmi tarama · ' if state == 'PARTIAL_COVERAGE' else ''
            suffix = (' Tüm kurumu temsil etmez.' if state == 'PARTIAL_COVERAGE' else '')
            return (f"{prefix}{p['lesson']} / {p['topic']} · {p['action_name']}: "
                    f"{p['measured_students']} geçmiş bağımsız izlem; "
                    f"{d['higher']} artış, {d['similar']} benzer, {d['lower']} azalış. "
                    'Nedensellik kanıtı değil; öğretmen değerlendirsin.' + suffix)
    if state == 'PARTIAL_COVERAGE':
        return 'Geçmiş müdahale taraması kısmi; güvenilir örüntü gösterilemiyor.'
    return None
