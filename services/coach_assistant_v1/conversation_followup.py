# -*- coding: utf-8 -*-
"""Bounded, same-student, read-only follow-up questions for the Koça Sor window.

This is intentionally NOT a remote AI model or an independent recommendation engine.
All answers are re-grounded in a freshly read CoachContext and existing dialogue logic.
No database, student identity or answer history is persisted by this module.
"""
from __future__ import annotations
from dataclasses import dataclass

from services.coach_assistant_v1.dialogue import (
    CoachAnswer, CoachContext, answer_question, _search_fold,
)
from services.coach_assistant_v1.shared_rules_v260 import (
    scoped_topics, lesson_key, is_low_accuracy, MIN_RELIABLE_ATTEMPTS,
)


@dataclass(frozen=True)
class ConversationMemory:
    student_id: int
    anchor_question: str  # Last independent question, not a chain of stale responses
    last_mode: str = ""
    other_index: int = 0
    lesson_scope: str = ""


def _intent(question: str) -> str | None:
    q = _search_fold(str(question or '').strip()[:600]).rstrip(' ?!.')
    if not q:
        return None
    if q in ('neden', 'neden?', 'neden boyle', 'neden boyle?', 'niye',
             'neye gore', 'nasil bildin', 'hangi kanit', 'kaniti ne',
             'bunu neye dayandirdin', 'buna neden karar verdin'):
        return 'why'
    if q in ('baska', 'baska?', 'baska konu', 'baska hangi konu',
             'ikinci konu', 'bir sonraki', 'bir sonraki konu'):
        return 'another'
    if q in ('peki', 'peki?', 'ne yapalim', 'simdi ne yapalim', 'sonraki adim',
             'peki ne yapalim', 'peki simdi ne yapalim', 'bu hafta ne yapalim',
             'peki bu hafta ne yapalim', 'nasil baslayalim',
             'bu hafta ne yapmaliyim', 'peki bu hafta ne yapmaliyim'):
        return 'next'
    if q in ('detay', 'ayrinti', 'biraz ac', 'biraz acar misin', 'acikla',
             'daha detayli anlat', 'biraz daha acikla', 'biraz acikla'):
        return 'detail'
    if q in ('bunu uygula', 'odev ver', 'otomatik odev ver', 'hemen uygula'):
        return 'action'
    # Do not absorb genuine independent questions into a previous response.
    if any(token in q for token in (
        'internetten', 'meb ', 'osym ', 'anket', 'deneme', 'yeni ogrenci',
        'hangi konuda', 'hangi konu', 'odevler', 'tum odev',
    )):
        return None
    return None


def is_followup(question: str) -> bool:
    return _intent(question) is not None


def _measured_topics(ctx: CoachContext):
    return sorted((t for t in ctx.topics if is_low_accuracy(t.accuracy, attempts=t.attempts, reliable_only=True)),
                  key=lambda t: (t.accuracy, -t.attempts, t.lesson, t.name))


def _gap_topics(ctx: CoachContext):
    return [t for t in ctx.topics if t.done > 0 and t.observations == 0]


def answer_with_memory(ctx: CoachContext, question: str,
                       memory: ConversationMemory | None = None, *,
                       lesson_scope: str = "") -> CoachAnswer:
    """Return live evidence, never copy the previous student's answer or stale counts."""
    if type(ctx.student_id) is not int or ctx.student_id <= 0:
        raise ValueError('Geçersiz öğrenci kimliği')
    intent = _intent(question)
    if (memory is None or memory.student_id != ctx.student_id or intent is None
            or lesson_key(memory.lesson_scope) != lesson_key(lesson_scope)):
        return answer_question(ctx, question, lesson_scope=lesson_scope)
    previous = answer_question(ctx, memory.anchor_question, lesson_scope=lesson_scope)
    if lesson_scope:
        from dataclasses import replace
        ctx = replace(ctx, topics=scoped_topics(ctx.topics, lesson_scope),
                      priority='', next_step='', basis='')
    if intent in ('why', 'detail', 'action') and memory.other_index:
        previous = _other_answer(ctx, memory.other_index)
    elif intent in ('why', 'detail', 'action') and memory.last_mode == 'next':
        previous = _next_answer(ctx, memory.anchor_question)
    if intent == 'why':
        return CoachAnswer(
            'Bu değerlendirmenin güncel dayanağı',
            'Önceki soruyu mevcut kayıtlarla yeniden değerlendirdim. ' + previous.message,
            previous.evidence or ('Bu konuda yeterli doğrulanabilir kanıt bulunamadı.',),
            previous.action_target,
        )
    if intent == 'detail':
        return CoachAnswer(
            'Biraz daha ayrıntı',
            previous.message + ' Bu ilişki tek başına nedensellik veya kesin öğrenme düzeyi '
            'göstermez. Farklı günlerde bağımsız ölçümlerle doğrulama önerilir.',
            previous.evidence, previous.action_target,
        )
    if intent == 'action':
        return CoachAnswer(
            'Öğretmen onayı gerekli',
            'Ödev işaretleme, öğrenci kaydı değiştirme veya mesaj gönderme işlemini '
            'kendiliğimden yapmıyorum. İlgili mevcut ekrana giderek kapsamı kontrol '
            'edip işlemi siz onaylayabilirsiniz.',
            previous.evidence, previous.action_target,
        )
    if intent == 'another':
        return _other_answer(ctx, memory.other_index + 1)
    if intent == 'next':
        return _next_answer(ctx, memory.anchor_question)
    return answer_question(ctx, question, lesson_scope=lesson_scope)


def _other_answer(ctx: CoachContext, index: int) -> CoachAnswer:
    lows = _measured_topics(ctx)
    gaps = _gap_topics(ctx)
    candidates = list(lows) + [t for t in gaps if t not in lows]
    if len(candidates) > index:
        t = candidates[index]
        description = (f'%{t.accuracy:g} doğruluk, {t.attempts} yanıt' if
                       t.accuracy is not None and t.attempts >= 5 else
                       'tamamlanmış ödev var, bağımsız ölçüm yok')
        return CoachAnswer(
            'İncelenebilecek başka konu',
            f'{t.lesson} / {t.name}: {description}. Bu kesin başarı etiketi değil; '
            'öğretmenin doğrulayabileceği bir sonraki adaydır.',
            (f'Güncel konu kontrolü: {t.observations} ölçüm',), 'btnOgrenme',
        )
    return CoachAnswer(
        'Başka konu için kanıt yeterli değil',
        'Güncel konu kayıtlarında bundan sonraki ölçüm düşüklüğü veya ölçüm boşluğu '
        'tespit edilemedi. Bu, başka eksik olmadığı anlamına gelmez.',
        ('Kaynak: seçili öğrenciye ait güncel konu kanıtları',), 'btnOgrenme',
    )


def _next_answer(ctx: CoachContext, anchor: str) -> CoachAnswer:
    anchored = _search_fold(anchor)
    lows = _measured_topics(ctx)
    gaps = _gap_topics(ctx)
    if any(word in anchored for word in ('konu', 'zayif', 'zorlan', 'yanlis', 'darbogaz')) and lows:
        t = lows[0]
        task = (f'{t.lesson} / {t.name} için önce mevcut ölçümün soru güçlüğünü '
                'kontrol edin; ardından başka gün kısa bağımsız yoklama planlayın.')
    elif any(word in anchored for word in ('konu', 'zayif', 'zorlan', 'ogrenme', 'gizli')) and gaps:
        t = gaps[0]
        task = f'{t.lesson} / {t.name} için kısa bağımsız kazanım yoklaması planlayın.'
    elif ctx.overdue_homework > 0:
        task = (f'Önce {ctx.overdue_homework} gecikmiş kaydın nedenini öğrenciyle '
                'doğrulayın; yeni ödevi mevcut yükle dengeleyin.')
    elif ctx.next_step:
        task = ctx.next_step
    else:
        task = 'Önce güncel ve karşılaştırılabilir konu ölçümü oluşturmayı değerlendirin.'
    return CoachAnswer(
        'Bu hafta için değerlendirilecek ilk adım',
        task + ' Bu öneri bir taslaktır; öğrenciye ödev atanmadı ve plan kaydedilmedi.',
        (f'Güncel açık ödev kaydı: {ctx.open_homework}',
         f'Öğrenci genelinde bağımsız kanıt: {ctx.measured_count}',
         f'Adaptif Koç dayanağı: {ctx.basis or "Belirtilmemiş"}'),
        'btnOgrenme',
    )


def next_memory(student_id: int, question: str,
                previous: ConversationMemory | None = None, *,
                lesson_scope: str = "") -> ConversationMemory:
    """Remember only a same-student anchor question, never an old answer or metrics."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçersiz öğrenci kimliği')
    intent = _intent(question)
    if (previous is not None and previous.student_id == student_id and intent
            and lesson_key(previous.lesson_scope) == lesson_key(lesson_scope)):
        return ConversationMemory(student_id, previous.anchor_question, intent,
                                  previous.other_index + 1 if intent == 'another' else previous.other_index,
                                  lesson_scope)
    return ConversationMemory(student_id, str(question or '').strip()[:600],
                              lesson_scope=lesson_scope)
