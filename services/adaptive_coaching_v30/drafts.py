# -*- coding: utf-8 -*-
"""V30: deterministic plan -> review -> exact legacy-checkbox task candidates.

Read-only planning. NEVER writes an old/new task, ticks a checkbox or persists approval.
Final application is delegated exclusively to HomeworkForm._wizard_transfer_tasks.
A checkbox means assigned/completed in the legacy workflow, never mastery.
"""
from __future__ import annotations
from datetime import date
import hashlib
import json

from services.adaptive_coaching_v25 import engine
from services.adaptive_coaching_v29.next_steps import student_next_steps
from utils.wizard_integrity_v8 import exact_task_key, same_student, valid_task

MAX_ITEMS = 12


def fingerprint(draft):
    """Stable stamp to refuse committing a proposal whose source has changed."""
    projection = {'student_id': draft['student_id'], 'generated_on': draft['generated_on'],
                  'preferences': draft['preferences'], 'overload_note': draft['overload_note'], 'items': [
         (x['lesson'], x['book'], x['topic'], x['minutes'], x['mode'], x['details'], x['note'], x['default_selected'])
         for x in draft['items']]}
    payload = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def build_draft(con, student_id, *, today=None, max_items=MAX_ITEMS):
    """Read a bounded V25 candidate plan and attach V29 teacher notes, if present.

    Only the selected student's records may contribute. No imaginary books, topics,
    correct answers or mastery scores. Workload notes reduce DEFAULT selection, not
    stored preferences or old tasks.
    """
    sid = int(student_id)
    if sid <= 0:
        raise ValueError('Öğrenci seçimi geçersiz.')
    cap = max(1, min(int(max_items), MAX_ITEMS))
    day = date.fromisoformat(str(today)[:10]) if today is not None else date.today()
    plan = engine.make_plan(con, sid, today=day)
    # The V29 API re-verifies homework ownership and matches the current topic.
    steps = student_next_steps(con, sid, today=day, limit=5)
    notes_by_key = {}
    for s in steps:
        key = exact_task_key(s['lesson'], '', s['topic'])
        notes_by_key.setdefault(key, s)
    items = []
    for row in plan['items'][:cap]:
        lesson, topic, book = (str(row.get(n) or '').strip() for n in ('lesson','topic','book'))
        key = exact_task_key(lesson, '', topic)
        note = notes_by_key.get(key)
        transferable = bool(lesson and topic and book)
        items.append({
            'lesson': lesson, 'topic': topic, 'book': book,
            'minutes': max(1, min(120, int(row['minutes']))),
            'mode': row['mode'], 'category': row['category'],
            'details': row['details'], 'level': row['level'],
            'note': (note['title'] + ': ' + note['next_step']) if note else None,
            'transferable': transferable,
            'default_selected': transferable,
            'reason': 'Kitap eşleşmesi yok; yalnızca koçluk önerisidir.' if not transferable else '',
        })
    # If overload was explicitly noted for this learner recently, do not silently
    # default-select the entire weekly plan. The teacher may select more manually.
    overloaded = any(s.get('teacher_note') == 'workload' for s in steps)
    if overloaded:
        allowed = 2
        for r in items:
            if r['transferable'] and allowed:
                allowed -= 1
            else:
                r['default_selected'] = False
    result = {'student_id':sid, 'generated_on':plan['generated_on'],
              'preferences':plan['preferences'], 'items':items,
              'total_suggested':len(plan['items']),
              'proposed_minutes':sum(r['minutes'] for r in items),
              'overload_note':overloaded,
              'warnings':list(plan.get('warnings') or [])}
    result['fingerprint'] = fingerprint(result)
    return result


def evaluate_candidates(items, availability):
    """Annotate proposal items without causing any checkbox change.

    availability(item) -> (bool, explanation). Final legacy transfer rechecks.
    """
    checked = set()
    evaluated = []
    for row in items:
        item = dict(row)
        key = exact_task_key(item['lesson'], item['book'], item['topic'])
        if not item['transferable'] or not valid_task({
                'ders': item['lesson'], 'kitap':item['book'], 'konu':item['topic']}):
            item['eligible'], item['reason'] = False, item.get('reason') or 'Kaynak eşleşmesi eksik.'
        elif key in checked:
            item['eligible'],item['reason'] = False,'Taslak içinde yinelenen ödev.'
        else:
            item['eligible'],item['reason'] = availability(item)
        item['default_selected'] = bool(item['eligible'] and item['default_selected'])
        if item['eligible']:
            checked.add(key)
        evaluated.append(item)
    return evaluated


def select_transfer_tasks(draft, selected_keys, *, expected_student_id, fresh_draft=None):
    """Pure approval boundary; refuses wrong learner and stale source proposal.

    Selected keys MUST be proposed; final unique/locked/checked check still lives
    in the existing _wizard_transfer_tasks. No bypass or direct DB insert.
    """
    if not same_student(draft['student_id'], expected_student_id):
        raise ValueError('Öğrenci değişti; aktarım yapılmadı.')
    if fresh_draft is None or fresh_draft.get('fingerprint') != draft.get('fingerprint'):
        raise ValueError('Öneri verisi güncellendi. Yeni taslağı açıp tekrar onaylayın.')
    requested = set(selected_keys)
    allowed = {exact_task_key(x['lesson'], x['book'], x['topic']) for x in draft['items']
               if x['transferable']}
    if not requested or not requested.issubset(allowed):
        raise ValueError('Seçilen ödevler onaylı taslakta bulunamadı.')
    tasks = []
    for item in draft['items']:
        key = exact_task_key(item['lesson'], item['book'], item['topic'])
        if key in requested:
            # Reusing the old manual assignment pipeline; no direct INSERT.
            description = f"{item['mode']}: {item['details']}"
            if item['note']:
                description += ' | Öğretmen gözlemi: ' + item['note']
            tasks.append({'ders':item['lesson'],'kitap':item['book'],
                          'konu':item['topic'],'dk':item['minutes'],
                          'aciklama':description[:1500]})
    if len(tasks) != len(requested):
        raise ValueError('Öneride yinelenen ders/kitap/konu tespit edildi.')
    return tasks
