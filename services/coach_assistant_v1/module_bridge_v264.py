# -*- coding: utf-8 -*-
"""V26.4: existing coaching modules' evidence-aware, optional READ-ONLY bridge.

Reads the actual same-student sources, never UI widgets. No records, homework,
profile, progress or recommendation is written. It does not fetch online data.
The question worker supplies a sqlite URI with mode=ro and PRAGMA query_only=ON.
Non-comparable homework counters are NEVER merged into a mastery metric.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
import sqlite3

from services.coach_assistant_v1.shared_rules_v260 import fold, lesson_key


@dataclass(frozen=True)
class ModuleReview:
    student_id: int
    adaptive_status: str = 'unavailable'
    adaptive_step: str = ''
    adaptive_source: str = ''
    adaptive_scope: str = ''
    wizard_status: str = 'not_requested'
    wizard_completed: int | None = None
    wizard_pending: int | None = None
    wizard_overdue: int | None = None
    plan_status: str = 'unavailable'
    discrepancy: str = ''
    missing: tuple[str, ...] = ()


def _same_lesson(item_lesson: str, scope: str) -> bool:
    return not scope or (bool(item_lesson) and lesson_key(item_lesson) == lesson_key(scope))


def _safe_text(value: Any, limit=150) -> str:
    return ' '.join(str(value or '').split())[:limit]


def read_module_review(con: sqlite3.Connection, context, *, lesson_scope: str = '',
                       include_wizard: bool = False, today: date | None = None) -> ModuleReview:
    """Best effort same-student module evidence. Never silently equate missing with zero.

    Source result scope is verified; unrelated course recommendations excluded.
    The wizard report is opt-in for full cross-module requests, since its
    historical joins may be expensive on a large database.
    """
    sid = getattr(context, 'student_id', None)
    if type(sid) is not int or sid <= 0:
        raise ValueError('Geçersiz öğrenci kimliği')
    prev = con.row_factory
    fields = dict(student_id=sid)
    missing = []
    con.row_factory = sqlite3.Row
    try:
        row = con.execute('SELECT id FROM ogrenci WHERE id=?', (sid,)).fetchone()
        if row is None:
            raise ValueError('Seçili öğrenci bulunamadı')
        try:
            from services.adaptive_coaching_v26.decision import student_decisions
            brief = student_decisions(con, sid, today=today, maximum=12)
            if int(brief.get('student_id', -1)) != sid:
                raise ValueError('Adaptif öğrenci kapsamı uyuşmuyor')
            fields['adaptive_status'] = 'available'
            for action in brief.get('actions', ()):
                if not _same_lesson(str(action.get('lesson') or ''), lesson_scope):
                    continue
                if lesson_scope and not action.get('lesson'):
                    # General student workload, not evidence for a specific subject.
                    continue
                fields['adaptive_step'] = _safe_text(action.get('next_step'), 170)
                fields['adaptive_source'] = _safe_text(action.get('source') or 'Adaptif Koçluk', 90)
                fields['adaptive_scope'] = _safe_text(
                    ' / '.join(filter(None, (str(action.get('lesson') or ''),
                                              str(action.get('topic') or '')))), 120)
                break
            info = brief.get('context') or {}
            fields['plan_status'] = _safe_text(info.get('coaching_plan'), 90) or 'unavailable'
        except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError, AttributeError) as exc:
            missing.append('Adaptif Koçluk: ' + type(exc).__name__)

        if include_wizard:
            try:
                from services.coach_evidence_v5 import build_coach_brief
                wiz = build_coach_brief(con, sid, as_of=today, max_actions=3)
                if int(wiz.get('student', {}).get('id', -1)) != sid:
                    raise ValueError('Sihirbaz öğrenci kapsamı uyuşmuyor')
                stats = wiz['stats']
                fields['wizard_status'] = 'available'
                for key, target in (('completed', 'wizard_completed'),
                                    ('pending', 'wizard_pending'),
                                    ('overdue', 'wizard_overdue')):
                    val = stats.get(key)
                    fields[target] = int(val) if type(val) is int and val >= 0 else None
                current_done = getattr(context, 'completed_homework', None)
                wiz_done = fields.get('wizard_completed')
                if current_done is not None and wiz_done is not None and int(current_done) != wiz_done:
                    fields['discrepancy'] = (
                        f'Öğrenci 360° Kontrol ({current_done} tamamlanan) ile '
                        f'Akıllı Sihirbaz ({wiz_done} tamamlanan) aynı sayımı vermiyor; '
                        'farklı kayıt kapsamları olabilir. Sayılar birleştirilmedi.')
            except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError, AttributeError) as exc:
                fields['wizard_status'] = 'unavailable'
                missing.append('Akıllı Sihirbaz: ' + type(exc).__name__)
    finally:
        con.row_factory = prev

    fields['missing'] = tuple(missing)
    return ModuleReview(**fields)


def enrich_answer(con: sqlite3.Connection, context, answer, question: str,
                  *, lesson_scope: str = ''):
    """Short integration notice; no new UI controls or unauthorized actions.

    Intentionally skips uncertain course and online queries. Uses established
    answer and one extra evidence line for normal academic-priority prompts.
    """
    from services.coach_assistant_v1.dialogue import CoachAnswer
    q = fold(question)
    if not q or answer.action_target is None or answer.title in (
        'Ders kapsamı uyuşmuyor', 'Ders adı belirsiz'):
        return answer
    if any(term in q for term in ('internet', 'online', 'meb', 'osym')):
        return answer
    explicit = any(term in q for term in (
        'modul', 'ekran', 'sihirbaz', 'ogrenci 360', '360', 'adaptif koc',
        'bilimsel koc', 'birlikte ne', 'butun sistem', 'sistemler',
        'hangi kaynaktan', 'kocluk merkezi'))
    priority = any(term in q for term in ('oncelik', 'oncelig', 'akademik ihtiyac', 'ilk ne', 'ne yapalim', 'plan'))
    evidence_question = 'odev' in q and any(term in q for term in ('ogrenme', 'kanit', 'tutarli'))
    if not (explicit or priority or evidence_question):
        return answer
    review = read_module_review(con, context, lesson_scope=lesson_scope,
                                include_wizard=(explicit or evidence_question))
    evidence = list(answer.evidence)
    note = ''
    if review.adaptive_status == 'available':
        if review.adaptive_step:
            course = f' ({review.adaptive_scope})' if review.adaptive_scope else ''
            evidence.append(f'Adaptif Koçluk{course}: {review.adaptive_step} '
                            f'[Kaynak: {review.adaptive_source}]')
        elif lesson_scope:
            evidence.append('Adaptif Koçluk: seçili derste ek bir müdahale önerisi yok; '
                            'öğrencinin genel önerisi ders sonucu gibi kullanılmadı.')
    if explicit:
        evidence.append('Öğrenci 360°: güncel Kontrol verileri zaten bu yanıtın temelinde.')
        evidence.append('Öğrenme: bağımsız V25 ölçümleri ve V26.2 gelişim analizi ayrı kanıt katmanlarıdır.')
        if review.plan_status not in ('unavailable', ''):
            evidence.append('Haftalık koçluk: ' + review.plan_status)
    if review.wizard_status == 'available':
        evidence.append('Akıllı Ödev Sihirbazı: geçmiş ödev/deneme değerlendirmesi; '
                        'tamamlanma, akademik öğrenme puanı değildir.')
    # V3.5.30 same-student bridge for unscoped cross-module requests only.
    # Never pass a general lesson recommendation as if it proved a scoped result.
    if explicit and not lesson_scope:
        try:
            from services.shared_academic_decision_v3530 import read_verified_plan_context
            shared = read_verified_plan_context(con, context.student_id)
            if shared['state'] == 'LINK_REVIEW':
                evidence.append('Ortak veri kontrolü: öğrenci–ödev bağlantıları gözden geçirilmeli; akademik öneri bastırıldı.')
            elif shared['state'] in ('MISSING', 'CONFLICT', 'NO_BLOCKS', 'PARTIAL'):
                evidence.append('Koçluk planı bağlamı: ' + shared['summary'])
        except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError):
            # The optional bridge never replaces the original coach answer.
            pass
    # V3.5.36 read-only canonical proof; never blend into a scoped lesson
    # claim, and never let source errors become a false "nothing to do".
    if (explicit or priority) and not lesson_scope:
        try:
            from services.academic_actions_v3536 import read_student_action_card
            action_card = read_student_action_card(con, context.student_id)
            if action_card['student_id'] == context.student_id:
                evidence.append('Ortak akademik kanıt: ' + _safe_text(action_card['next_step'], 210))
                # V3.5.37: extra review guidance only for GENERAL, non-lesson questions.
                try:
                    from services.intervention_advisor_v3537 import build_intervention_draft
                    draft = build_intervention_draft(con, context.student_id, action_card=action_card)
                    if draft['student_id'] == context.student_id and draft['recommendations']:
                        item = draft['recommendations'][0]
                        evidence.append('Telafi taslağı (öğretmen onayı): ' +
                                        _safe_text(item['title'] + ' — ' + item['teacher_next_step'], 190))
                except (sqlite3.Error, ValueError, TypeError, KeyError):
                    pass
                if action_card['state'] == 'LINK_REVIEW':
                    evidence.append('Uyarı: Bu öğrenci için ödev sayıları güvenilir kabul edilmiyor.')
        except (sqlite3.Error, ValueError, TypeError, KeyError, ImportError):
            evidence.append('Ortak ödev kanıtı: kaynak doğrulanamadı; eksik veri başarı anlamına gelmez.')
    if review.discrepancy:
        evidence.append('Kapsam kontrolü: ' + review.discrepancy)
        if explicit or evidence_question:
            note = ' Ödev sayılarının tanımları farklı olabildiğinden önce kayıt kapsamını doğrulayın.'
    if review.missing and explicit:
        evidence.append('Bazı modüller şu anda doğrulanamadı: ' + '; '.join(review.missing))
    if explicit:
        # First action is a grounded suggestion from the existing decision engine,
        # not a second algorithm replacing the teacher's current decision.
        next_step = review.adaptive_step or _safe_text(answer.message, 185)
        summary = ('İlk değerlendirilecek adım: ' + next_step + ' '
                   'Öğrenci 360° güncel ödev/kontrolü; Adaptif Koçluk bağımsız konu gözlemlerini; '
                   'Öğrenme analizleri gelişim sinyalini; Akıllı Sihirbaz geçmiş ödev/deneme '
                   'kanıtlarını sağlar. Bunlar tek bir başarı puanı değildir. '
                   'Öğretmen onayı olmadan hiçbir kayıt değişmez.')
        return CoachAnswer('Mevcut koçluk modüllerinin ortak değerlendirmesi',
                           summary + note, tuple(dict.fromkeys(evidence))[-9:],
                           answer.action_target)
    if not review.discrepancy and not review.adaptive_step and not review.missing:
        return answer
    return CoachAnswer(answer.title, answer.message + note,
                       tuple(dict.fromkeys(evidence))[-9:], answer.action_target)
