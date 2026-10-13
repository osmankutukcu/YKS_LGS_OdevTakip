# -*- coding: utf-8 -*-
"""V24.3 – hedef/koçluk için salt okunur öğrenci 360° köprüsü.

Var olan V14/V15 kanıt hesaplarını kullanır; ikinci bir yüzdelik/puan
hesaplayıcısı geliştirmez. Veritabanına kayıt, göç ve düzeltme yapmaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import sqlite3

from services.student360_v16.reader import read_student_overview
from services.student360_v16.advisor import suggestions
from services.target_analysis_v24.student_target import read_saved_target


@dataclass(frozen=True)
class CoachingBrief:
    student_id: int
    name: str
    saved_target: str
    homework: str
    overdue: int
    exam: str
    exam_evidence: str
    exam_explanation: str
    coaching_plan: str
    tracked_topics: int
    teacher_marked_topics: int
    recommendations: tuple[str, ...]
    warnings: tuple[str, ...]


def read_coaching_brief(con: sqlite3.Connection, student_id: int, *, as_of: date | None = None) -> CoachingBrief:
    """Yalnızca tam öğrenci ID ile okur; öğrenciler arasında varsayılan seçim yapmaz."""
    overview = read_student_overview(con, student_id, as_of=as_of)
    return CoachingBrief(
        student_id=student_id,
        name=overview.student_name,
        saved_target=read_saved_target(con, student_id),
        homework=overview.homework_last30,
        overdue=overview.homework_overdue,
        exam=overview.exam_summary,
        exam_evidence=overview.exam_evidence,
        exam_explanation=overview.exam_explanation,
        coaching_plan=overview.coaching_plan,
        tracked_topics=overview.tracked_topics,
        teacher_marked_topics=overview.marked_topics,
        recommendations=suggestions(overview),
        warnings=overview.source_warnings,
    )


def render_coaching_brief(brief: CoachingBrief, *, draft_target_name: str | None = None) -> str:
    """Yalnızca kullanıcıya gösterilecek metin; ödev veya hedef yazmaz.

    draft_target_name varsa analiz önizlemesinden alınmıştır, kayıtlı hedef
    değildir ve bunun altı açıkça çizilir.
    """
    parts = [
        f'ÖĞRENCİ 360° – HEDEF VE KOÇLUK',
        f'{brief.name} (Öğrenci ID: {brief.student_id})',
        '',
        'KAYITLI HEDEF', brief.saved_target,
    ]
    if draft_target_name is not None:
        label = str(draft_target_name).strip()[:160]
        if label:
            parts += ['', 'ANALİZ ÖNİZLEMESİNDEKİ TASLAK (KAYDEDİLMEDİ)', label]
    parts += [
        '', 'ÖDEV TAKİBİ', brief.homework,
        f'Gecikmiş açık ödev: {brief.overdue}',
        'Ödev tamamlama akademik başarıyla eşdeğer değildir.',
        '', 'DENEME KANITI', brief.exam,
        f'Kanıt düzeyi: {brief.exam_evidence}', brief.exam_explanation,
        '', 'KOÇLUK', brief.coaching_plan,
        '', 'KONU TAKİBİ',
        f'Takip: {brief.tracked_topics} | Öğretmen işareti: {brief.teacher_marked_topics}',
        'Konu işaretleri kesin öğrenme göstergesi değildir.',
        '', 'ÖĞRETMENİN KONTROL EDEBİLECEĞİ ÖNERİLER',
    ]
    parts += [f'• {rec}' for rec in brief.recommendations]
    if brief.warnings:
        parts += ['', 'VERİ KALİTESİ NOTLARI', *[f'• {w}' for w in brief.warnings]]
    parts += [
        '', 'VERİ KAYNAKLARI / SINIRLAR',
        'Bu özet yerel ödev, deneme ve koçluk kayıtlarından üretilmiştir.',
        'YÖK Atlas/ÖSYM verisi otomatik ithal edilmez; yerleşme olasılığı hesaplanmaz.',
        'Hiçbir öğrenci kaydı veya ödev bu ekran tarafından değiştirilmez.',
    ]
    return '\n'.join(parts)
