# -*- coding: utf-8 -*-
"""KoçPilot 360 v3.5.64 -- science-to-existing-wizard advisory bridge.

Read-only and fail-closed. This does NOT alter the existing V30 draft, select
checkboxes, approve a transfer, write any database rows, or claim to have
created a ready-to-assign new task. Only actual book+topic candidates already
proposed by V30 may be aligned with a recorded-learning intervention.
"""
from __future__ import annotations

from datetime import date
import sqlite3

from services.adaptive_coaching_v30.drafts import build_draft, fingerprint
from utils.wizard_integrity_v8 import exact_task_key, valid_task

_EXPECTED_RESEARCH_SCHEMA = 'evidence_based_coach_v3563'
_BLOCKED = frozenset({'DATA_REVIEW', 'UNVERIFIED'})
_REQUIRED_V25_TABLES = frozenset({
    'adaptive_observation_v25', 'adaptive_profile_v25', 'adaptive_blocker_v25',
})


def _blocked(student_id, today, state, message, *, source=None):
    return {
        'schema': 'science_wizard_alignment_v3564',
        'student_id': student_id, 'as_of': today.isoformat(),
        'state': state, 'reason': message, 'source_state': source,
        'read_only': True, 'teacher_approval_required': True,
        'auto_assignment': False, 'auto_selection': False,
        'requires_live_matrix_recheck': True, 'matched': [],
        'not_matched': [], 'suggested_minutes': 0,
        'existing_wizard_unchanged': True,
    }


def align_research_with_existing_draft(research: dict, draft: dict, *,
                                       student_id: int, today: date) -> dict:
    """Pure mapper for existing V30 draft. No invented books or default ticks."""
    if type(student_id) is not int or student_id <= 0 or type(today) is not date:
        raise ValueError('Validated student and date required')
    if (not isinstance(research, dict)
        or research.get('schema') != _EXPECTED_RESEARCH_SCHEMA
        or research.get('student_id') != student_id
        or research.get('as_of') != today.isoformat()
        or research.get('read_only') is not True
        or research.get('automatic_actions') is not False
        or research.get('teacher_approval_required') is not True):
        raise ValueError('Untrusted or stale research card')
    if research.get('state') in _BLOCKED:
        return _blocked(student_id, today, 'DATA_REVIEW',
            'Akademik kanıt doğrulanmadı; sihirbaz önerisi hazırlanmadı.',
            source=research.get('state'))
    if research.get('state') != 'REVIEW_SUGGESTED':
        return _blocked(student_id, today, 'NO_LEARNING_PROPOSAL',
            'Güncel bağımsız öğrenme kontrolü önerisi bulunmuyor.',
            source=research.get('state'))
    cards = research.get('cards')
    if not isinstance(cards, list) or not 1 <= len(cards) <= 3:
        return _blocked(student_id, today, 'DATA_REVIEW', 'Öneri listesi doğrulanamadı.')
    for card in cards:
        if (not isinstance(card,dict) or card.get('requires_teacher_approval') is not True
            or card.get('auto_assignment') is not False
            or card.get('kind') not in ('TARGETED_REVIEW','CHECK_ERRORS',
                                       'CLARIFY_OBSERVATION','SPACED_CHECK')
            or not isinstance(card.get('lesson'),str) or not card['lesson'].strip()
            or not isinstance(card.get('topic'),str) or not card['topic'].strip()):
            return _blocked(student_id,today,'DATA_REVIEW','Öneri güvenlik alanları doğrulanamadı.')
    if (not isinstance(draft,dict) or type(draft.get('student_id')) is not int
        or draft['student_id'] != student_id
        or draft.get('generated_on') != today.isoformat()
        or not isinstance(draft.get('items'),list)
        or not isinstance(draft.get('preferences'),dict)
        or type(draft.get('overload_note')) is not bool
        or not isinstance(draft.get('fingerprint'),str)):
        return _blocked(student_id,today,'DRAFT_REVIEW',
            'Mevcut ödev taslağı güncel öğrenciye ait değil veya doğrulanamadı.')
    try:
        if fingerprint(draft) != draft['fingerprint']:
            raise ValueError('Stale or tampered draft')
    except (ValueError,KeyError,TypeError,AttributeError):
        return _blocked(student_id,today,'DRAFT_REVIEW','Ödev taslağının bütünlüğü doğrulanamadı.')

    actual = {}
    ambiguous = set()
    for item in draft['items'][:12]:
        if not isinstance(item,dict):
            return _blocked(student_id,today,'DRAFT_REVIEW','Taslak maddesi bozuk.')
        lesson,topic,book = (item.get(k) for k in ('lesson','topic','book'))
        if any(not isinstance(x,str) for x in (lesson,topic,book)):
            return _blocked(student_id,today,'DRAFT_REVIEW','Taslak konu/kitap bilgisi doğrulanamadı.')
        # No virtual book, no automatic transfer, no duplicate ambiguous target.
        if not item.get('transferable') or not book.strip() or not valid_task({
                'ders':lesson, 'kitap':book, 'konu':topic}):
            continue
        key = exact_task_key(lesson,'',topic)
        if key in actual: ambiguous.add(key)
        else: actual[key] = item
    for key in ambiguous:
        actual.pop(key,None)

    chosen, missing, used = [], [], set()
    limit = 1 if draft['overload_note'] else 2
    for card in cards:
        key = exact_task_key(card['lesson'],'',card['topic'])
        if key in used: continue
        used.add(key)
        draft_item = actual.get(key)
        if draft_item is None:
            missing.append({'lesson':card['lesson'][:90], 'topic':card['topic'][:140],
                'reason':'Aynı öğrencinin mevcut Sihirbaz taslağında doğrulanmış kitap/konu eşleşmesi yok.',
                'suggested_action':'Öğrenme ekranında kısa kontrolü inceleyin; hayalî kitap atanmadı.'})
            continue
        if len(chosen) >= limit:
            missing.append({'lesson':card['lesson'][:90], 'topic':card['topic'][:140],
                'reason':'İş yükünü sınırlamak amacıyla otomatik öncelik listesine eklenmedi.',
                'suggested_action':'Öğretmen isterse mevcut Sihirbazdan manuel değerlendirebilir.'})
            continue
        try:
            minutes = int(draft_item.get('minutes'))
        except (TypeError,ValueError):
            continue
        if not 1 <= minutes <= 120:
            continue
        chosen.append({
            'lesson':draft_item['lesson'][:90], 'topic':draft_item['topic'][:140],
            'existing_book':draft_item['book'][:140], 'minutes':minutes,
            'kind':card['kind'], 'strategy':str(card.get('strategy') or '')[:160],
            'evidence_reason':str(card.get('observation') or '')[:240],
            'teacher_activity':str(card.get('teacher_activity') or '')[:350],
            'teacher_must_review_in_existing_wizard':True,
            'suggested_check_on':card.get('suggested_check_on'),
            'automatic_transfer':False,
        })

    result = _blocked(student_id,today,
        'MATCHED' if chosen else 'NO_VERIFIED_BOOK_MATCH',
        ('Mevcut taslakla eşleşen çalışmalar öğretmen incelemesine sunulabilir.' if chosen
         else 'Öneriler mevcut öğrenci/kitap taslağıyla birebir eşleşmiyor.'),
        source=research.get('state'))
    result.update(matched=chosen, not_matched=missing,
                  suggested_minutes=sum(x['minutes'] for x in chosen),
                  overload_limited=draft['overload_note'],
                  v30_draft_fingerprint=draft['fingerprint'],
                  note=('Bu yalnızca bir eşleştirme önizlemesidir. Sihirbaz açıldığında '
                        'taslak ve hücre uygunluğu yeniden değerlendirilir; hiçbir '
                        'seçim veya ödev aktarımı yapılmadı.'))
    return result


def read_science_wizard_alignment(con: sqlite3.Connection, student_id: int, *,
                                  today: date | None = None,
                                  research_card: dict | None = None) -> dict:
    """Read-only advisor for a verified research card in same snapshot.

    Never creates V25 tables: old installs lacking opt-in tables are supported
    without schema migration. Caller should use a query_only SQLite snapshot.
    """
    day = date.today() if today is None else today
    if type(student_id) is not int or student_id <= 0 or type(day) is not date:
        raise ValueError('Invalid student / date')
    if research_card is None:
        from services.evidence_based_coach_v3563 import read_evidence_based_coach
        research_card=read_evidence_based_coach(con,student_id,today=day)
    # Check card before ANY wizard queries to prevent student cross-contamination.
    if (not isinstance(research_card,dict)
        or research_card.get('schema')!=_EXPECTED_RESEARCH_SCHEMA
        or research_card.get('student_id')!=student_id
        or research_card.get('as_of')!=day.isoformat()
        or research_card.get('read_only') is not True
        or research_card.get('automatic_actions') is not False
        or research_card.get('teacher_approval_required') is not True):
        raise ValueError('Untrusted science context')
    if research_card.get('state') != 'REVIEW_SUGGESTED':
        return _blocked(student_id,day,'NO_LEARNING_PROPOSAL',
                        'Ödev eşleştirmesi için doğrulanmış öğrenme önerisi yok.',
                        source=research_card.get('state'))
    present={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN (?,?,?)",
                                  tuple(sorted(_REQUIRED_V25_TABLES)))}
    if not _REQUIRED_V25_TABLES <= present:
        return _blocked(student_id,day,'DRAFT_NOT_INITIALIZED',
            'Adaptif ödev taslağı tabloları henüz etkin değil; otomatik oluşturulmadı.',
            source=research_card.get('state'))
    try:
        draft=build_draft(con,student_id,today=day,max_items=12)
    except (sqlite3.Error,ValueError,TypeError,KeyError,AttributeError,IndexError):
        return _blocked(student_id,day,'DRAFT_REVIEW',
            'Mevcut Sihirbaz taslağı okunamadı; eski işlevler etkilenmedi.',
            source=research_card.get('state'))
    return align_research_with_existing_draft(research_card,draft,
                                              student_id=student_id,today=day)
