from __future__ import annotations
"""Immutable, explanatory topic evidence models. Never used as an academic diagnosis."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TopicEvidence:
    lesson: str
    topic: str
    main_open: int = 0
    main_done: int = 0
    map_open: int = 0
    map_done: int = 0
    teacher_state: int | None = None
    teacher_score: int | None = None
    teacher_note: str = ''
    duplicate_teacher_records: int = 0
    source_warning: str = ''
    recommendation: str = ''
    question_correct: int = 0
    question_wrong: int = 0
    question_blank: int = 0
    outcome_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class LessonExamContext:
    lesson: str
    count: int
    latest: str
    note: str = 'Bu deneme verileri ders düzeyindedir; bir konuya otomatik bağlanamaz.'


@dataclass(frozen=True)
class TopicEvidenceReport:
    student_id: int
    student_name: str
    topics: tuple[TopicEvidence, ...]
    exam_context: tuple[LessonExamContext, ...]
    warnings: tuple[str, ...]
    def explain(self) -> str:
        lines = [f'ÖĞRENCİ: {self.student_name} (ID: {self.student_id})',
                 'Konu kanıtı: Ödev bitmesi, konunun öğrenildiğini kanıtlamaz.', '']
        for t in self.topics:
            lines.append(f'{t.lesson} / {t.topic}: ana ödev açık={t.main_open}, biten={t.main_done}; '
                         f'harita açık={t.map_open}, biten={t.map_done}; '
                         f'koçluk işareti={t.teacher_state if t.teacher_state is not None else "yok"}')
            lines.append('  ' + t.recommendation)
            if t.question_correct+t.question_wrong+t.question_blank:
                lines.append(f'  Öğretmen onaylı soru kanıtı: {t.question_correct} doğru / {t.question_wrong} yanlış / {t.question_blank} boş')
            if t.outcome_codes:
                lines.append('  Kaynaktan gelen kazanım kodları (resmî doğrulama yapılmadı): '+', '.join(t.outcome_codes))
            if t.source_warning: lines.append('  Uyarı: ' + t.source_warning)
        lines.append('\nDENEME KAPSAMI (DERS DÜZEYİNDE)')
        for e in self.exam_context:
            lines.append(f'{e.lesson}: {e.count} kayıt; {e.latest}. {e.note}')
        if self.warnings:
            lines.append('\nVERİ UYARILARI')
            lines.extend('• ' + item for item in self.warnings)
        return '\n'.join(lines)
