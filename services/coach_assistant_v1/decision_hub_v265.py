# -*- coding: utf-8 -*-
"""V26.5 - one concise decision from existing read-only coaching outputs.

No new mastery computation: Student 360, V25 Adaptive Coaching, longitudinal
and cohort signals remain their own authoritative sources. This pure presenter
only resolves duplicated textual evidence for explicit cross-module questions.
It never writes student records or changes the teacher's proposed action.
"""
from __future__ import annotations
from dataclasses import replace
from services.coach_assistant_v1.shared_rules_v260 import fold

# Types are *sources*, not grades, probabilities or competing success scores.
_SOURCE_TAGS = (
    ('kapsam kontrolu', 'scope'),
    ('bazi moduller', 'unavailable'),
    ('veri eksikligi', 'unavailable'),
    ('ders filtresi', 'scope'),
    ('adaptif kocluk', 'adaptive'),
    ('grup sinyali', 'peer'),
    ('sinif', 'peer'),
    ('gelisim', 'trend'),
    ('olcen', 'learning'),
    ('ogrenme', 'learning'),
    ('akilli odev sihirbazi', 'wizard'),
    ('ogrenci 360', 'workspace'),
    ('haftalik kocluk', 'plan'),
)


def _kind(line: str) -> str:
    normalized = fold(line)
    for fragment, kind in _SOURCE_TAGS:
        if fragment in normalized:
            return kind
    return 'other'


def _is_cross_module(question: str) -> bool:
    q = fold(question)
    return any(term in q for term in (
        'birlikte', 'tum sistem', 'butun sistem', 'moduller', 'modul',
        'ekranlar', 'ogrenci 360', 'akilli sihirbaz', 'kaynaklari karsilastir',
        'kocluk sistemleri', 'adaptif koc ve',
    ))


def coordinate_answer(answer, question: str, *, student_id: int, lesson_scope: str = ''):
    """Minimal-distracting presentation only for explicit cross-screen requests.

    The source modules have already performed student/scope checks. A rejected
    request stays rejected. Evidence is limited by source type, with mismatch
    and read failures always preserved. A fresh DB read happens for each user
    question; no cross-student cache or shared mutable state exists here.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Öğrenci kapsamı doğrulanamadı')
    if (not _is_cross_module(question) or answer.action_target is None or
            answer.title in ('Ders kapsamı uyuşmuyor', 'Ders adı belirsiz')):
        return answer
    evidence = tuple(str(x).strip() for x in answer.evidence if str(x).strip())
    # Preserve one of each distinct source (plus one unmatched line), not five
    # repetitions of already-visible homework counts.
    found = {}
    for line in evidence:
        kind = _kind(line)
        if kind not in found:
            found[kind] = line[:300]
    ordered = ('scope', 'unavailable', 'adaptive', 'trend', 'peer', 'learning',
               'wizard', 'workspace', 'plan', 'other')
    selected = [found[key] for key in ordered if key in found][:6]
    # Prior context disagreement must never disappear behind the evidence cap.
    for protected in ('scope', 'unavailable'):
        if protected in found and found[protected] not in selected:
            selected = selected[:5] + [found[protected]]
    qscope = ('Seçili ders: ' + lesson_scope.strip() + '. ') if lesson_scope else 'Öğrenci genelinde. '
    lead = ('Tek öneri, farklı kanıtlar: ') if answer.title == 'Mevcut koçluk modüllerinin ortak değerlendirmesi' else ''
    # Content is still derived from the previous verified analysis, not invented.
    message = answer.message.strip()
    if lead and not message.startswith(lead):
        message = lead + message
    if len(message) > 540:
        cut = message.rfind('. ', 0, 510)
        if cut > 160:
            message = message[:cut + 1]
        else:
            message = message[:537].rstrip() + '…'
    disclaimer = 'Ödev tamamlama, öğrenme ölçümü değildir; öneri öğretmen onayına tabidir.'
    if disclaimer not in message:
        message = message.rstrip() + '\n' + qscope + disclaimer
    return replace(answer, message=message, evidence=tuple(selected))
