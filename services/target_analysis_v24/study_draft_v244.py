# -*- coding: utf-8 -*-
"""V24.4 – Öğretmenin seçeceği, salt okunur kanıta dayalı çalışma taslağı.

Ödev/kazanım/hedef yazmaz. V18 konu ve V16/V24 koçluk okuyucularını
kullanır. Ders netinden konu zayıflığı, başarı sırası veya hedef net üretmez.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import sqlite3

from services.target_analysis_v24.coaching_bridge_v243 import read_coaching_brief
from services.topic_evidence_v18.reader import read_topic_evidence


@dataclass(frozen=True)
class DraftAction:
    action_id: str
    title: str
    reason: str
    proposed_step: str
    evidence_source: str
    requires_review: bool = False


@dataclass(frozen=True)
class StudyDraft:
    student_id: int
    student_name: str
    as_of: date
    saved_target: str
    actions: tuple[DraftAction, ...]
    warnings: tuple[str, ...]


def _clean(value: object, limit: int = 100) -> str:
    return ' '.join(str(value or '').split())[:limit]


def read_study_draft(con: sqlite3.Connection, student_id: int, *, as_of: date | None = None) -> StudyDraft:
    """No fallback student ID; all sources must match the same active student."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Öğrenci kimliği geçersiz.')
    day = as_of or date.today()
    brief = read_coaching_brief(con, student_id, as_of=day)
    topics = read_topic_evidence(con, student_id, as_of=day)
    if topics.student_id != brief.student_id or topics.student_name != brief.name:
        raise ValueError('Öğrenci bilgileri kaynaklar arasında farklı; taslak oluşturulmadı.')

    actions: list[DraftAction] = []
    warnings = list(dict.fromkeys((*brief.warnings, *topics.warnings)))

    if brief.overdue:
        actions.append(DraftAction('overdue', 'Gecikmiş ödevleri kontrol',
            f'{brief.overdue} gecikmiş açık ödev var.',
            'Önce mevcut ödevlerin teslim ve tamamlanma durumunu öğrenciyle doğrulayın; aynı ödevi ikinci kez oluşturmayın.',
            'Ödev Takip / V16 öğrenci özeti'))
    if brief.exam_evidence in ('Yok', 'Tek ölçüm'):
        actions.append(DraftAction('exam_check', 'Deneme kanıtını tamamla',
            f'Deneme kanıt düzeyi: {brief.exam_evidence}.',
            'Aynı sınav türünden karşılaştırılabilir ve eksiksiz bir ölçüm olup olmadığını kontrol edin.',
            'Deneme Sınavları / V15 kanıt modeli'))
    if 'kayıtlı değil' in brief.coaching_plan.casefold():
        actions.append(DraftAction('coaching_plan', 'Haftalık koçluk hedefini gözden geçir',
            'Seçilen hafta için koçluk planı görünmüyor.',
            'Öğrenciye uygun küçük bir çalışma hedefi belirleyin; kaydetmeden önce öğretmen onayı alın.',
            'Koçluk Planı / V16 özeti'))

    # Belirsiz konu kaynaklarını sessizce güvenli kanıt olarak kullanmayın.
    candidates = []
    unsafe_count = 0
    for t in topics.topics:
        if t.source_warning or t.duplicate_teacher_records:
            unsafe_count += 1
            continue
        incorrect = int(t.question_wrong) + int(t.question_blank)
        active = int(t.main_open) + int(t.map_open)
        if incorrect:
            candidates.append((0, -incorrect, t.lesson.casefold(), t.topic.casefold(), t,
                               f'Öğretmen onaylı soru eşlemesinde {t.question_wrong} yanlış, {t.question_blank} boş.',
                               'Kısa konu tekrarı ve birkaç doğrulama sorusu için öğretmen uygunluk kontrolü yapsın.',
                               'Deneme Sınavları / V19 soru–konu kanıtı'))
        elif active:
            candidates.append((1, -active, t.lesson.casefold(), t.topic.casefold(), t,
                               f'Açık ödev/konu takibi: {active} kayıt (farklı kaynaklar eşdeğer olmayabilir).',
                               'Önce açık çalışma durumunu doğrulayın; mükerrer ödev oluşturmayın.',
                               'Ödev Takip / Konu Haritası'))
    if unsafe_count:
        warnings.append(f'{unsafe_count} konu satırının kaynak bilgisi belirsiz/çakışmalı; bu satırlardan otomatik çalışma önerisi üretilmedi.')

    for ix, item in enumerate(sorted(candidates)[:5], start=1):
        _, _, _, _, t, reason, step, source = item
        actions.append(DraftAction(f'topic:{ix}', f'{_clean(t.lesson, 60)} / {_clean(t.topic, 100)}',
                                   reason, step, source))
    if not topics.topics:
        actions.append(DraftAction('no_topics', 'Konu kanıtını tamamla',
            'Seçili öğrenci için konu düzeyinde eşleşmiş kayıt bulunamadı.',
            'Konu Haritası veya soru–konu kanıtlarını kontrol edin; ders netinden konu eksiği üretmeyin.',
            'Konu Haritası / V18 kanıt modeli'))

    # Ölçülen ve yorumlanan şeyleri öğretmen için ayrı gösterin.
    if not actions:
        actions.append(DraftAction('review', 'Mevcut çalışma düzenini değerlendir',
            'Kayıtlardan belirli bir müdahale zorunluluğu çıkmıyor.',
            'Öğrenciyle mevcut çalışma düzenini görüşün; ek ödev gerekliliğini öğretmen belirlesin.',
            'Öğrenci 360° / V16 ve V18'))
    warnings.append('Bu taslak resmî net hedefi, başarı sıralaması veya yerleşme olasılığı hesaplamaz.')
    return StudyDraft(student_id, brief.name, day, brief.saved_target, tuple(actions[:9]),
                      tuple(dict.fromkeys(warnings)))


def render_selected_draft(draft: StudyDraft, selected_ids: tuple[str, ...], *, teacher_note: str = '') -> str:
    """Açık öğretmen seçimi dışında eylem eklemeyin, hiçbir yere kaydetmeyin."""
    if not selected_ids or len(set(selected_ids)) != len(selected_ids):
        raise ValueError('En az bir farklı çalışma önerisi seçin.')
    known = {a.action_id: a for a in draft.actions}
    if any(action_id not in known for action_id in selected_ids):
        raise ValueError('Taslak ile uyumsuz öneri seçimi.')
    if len(str(teacher_note)) > 500:
        raise ValueError('Öğretmen notu 500 karakteri aşamaz.')
    lines = [
        'ÖĞRETMEN KONTROLÜ İÇİN ÇALIŞMA TASLAĞI – KAYDEDİLMEDİ',
        f'Öğrenci: {draft.student_name} (ID: {draft.student_id})',
        f'Değerlendirme tarihi: {draft.as_of.isoformat()}',
        'Kayıtlı hedef (bilgi amaçlı): ' + draft.saved_target,
        'Bu metin Ödev Sepetine veya Koçluk Planına otomatik aktarılmamıştır.', '',
    ]
    for index, action_id in enumerate(selected_ids, 1):
        action = known[action_id]
        lines += [f'{index}. {_clean(action.title, 200)}',
                  f'Gerekçe: {action.reason}', f'Öğretmen için önerilen adım: {action.proposed_step}',
                  f'Kanıt kaynağı: {action.evidence_source}', '']
    if teacher_note.strip():
        lines += ['Öğretmen notu: ' + _clean(teacher_note, 500), '']
    if draft.warnings:
        lines += ['VERİ GÜVENİLİRLİĞİ / SINIRLAR', *[f'• {w}' for w in draft.warnings], '']
    lines += ['Kaydetme/ödev atama yapılmadı. Öğretmen kontrolünden sonra ilgili ekrandan ayrıca işlem yapılmalıdır.']
    return '\n'.join(lines)
