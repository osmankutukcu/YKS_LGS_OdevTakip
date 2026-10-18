# -*- coding: utf-8 -*-
"""Safe read-only cross-module topic summary.

Uses the existing V18 evidence collector. No DB mutations, no automatic
homework or mastery changes, no student inference, and no merged counters.
"""
from __future__ import annotations
from dataclasses import dataclass
import sqlite3
import unicodedata
from services.topic_evidence_v18 import read_topic_evidence

_LESSON_ALIASES = {
    'tyt matematik': 'tyt_matematik',
    'matematik tyt': 'tyt_matematik',
    'ayt matematik': 'ayt_matematik',
    'matematik ayt': 'ayt_matematik',
    'tyt türkçe': 'tyt_turkce',
    'türkçe tyt': 'tyt_turkce',
    'tyt turkce': 'tyt_turkce',
    'turkce tyt': 'tyt_turkce',
}

def lesson_code(name: str) -> str:
    """Only explicitly-known course aliases; no fuzzy or cross-level inference."""
    token = ' '.join(str(name or '').replace('_', ' ').replace('(', ' ').replace(')', ' ').split()).casefold()
    token = unicodedata.normalize('NFC', token)
    return _LESSON_ALIASES.get(token, token)

@dataclass(frozen=True)
class SharedTopicSummary:
    student_id: int
    student_name: str
    selected_lesson: str
    covered_topics: int
    main_open: int
    main_done: int
    map_open: int
    map_done: int
    teacher_entries: int
    teacher_mastered: int
    question_correct: int
    question_wrong: int
    question_blank: int
    excluded_other_lessons: int
    warnings: tuple[str, ...]

    def lines(self) -> tuple[str, str]:
        first = (f'Ana ödev: {self.main_open} açık / {self.main_done} tamamlandı  ·  '
                 f'Konu Haritası ödevi: {self.map_open} açık / {self.map_done} tamamlandı')
        second = (f'Koçluk işareti: {self.teacher_entries} konu '
                  f'(öğretmen tam hâkimiyet: {self.teacher_mastered})  ·  '
                  f'Onaylı soru: {self.question_correct} D / {self.question_wrong} Y / {self.question_blank} B')
        return first, second

    def note(self) -> str:
        if self.warnings:
            return '⚠️ Bazı kaynaklar inceleme gerektiriyor. Ayrıntı için Birleşik Konu Kanıtları ekranını açın.'
        return ('Sayılar neden farklı? Ana ödev ve Konu Haritası mikro ödevleri farklı kayıtlardır; '      'kart yüzdesi konu işaretlerinden hesaplanır. Ödevin bitmesi öğrenildiğini kanıtlamaz.')

def read_shared_topic_summary(con: sqlite3.Connection, student_id: int, lesson: str | None = None) -> SharedTopicSummary:
    """Reads existing source of truth for one validated student; never writes."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli öğrenci seçilmeli.')
    report = read_topic_evidence(con, student_id)
    selected = str(lesson or '').strip()
    key = lesson_code(selected)
    topics = tuple(t for t in report.topics if not selected or lesson_code(t.lesson) == key)
    other = len(report.topics)-len(topics)
    warnings = list(report.warnings)
    for t in topics:
        if t.source_warning:
            warnings.append(f'{t.lesson} / {t.topic}: {t.source_warning}')
        if t.duplicate_teacher_records:
            warnings.append(f'{t.lesson} / {t.topic}: kitap bazlı çoklu koçluk işareti; otomatik tekilleştirilmedi.')
    return SharedTopicSummary(
        student_id, report.student_name, selected, len(topics),
        sum(t.main_open for t in topics), sum(t.main_done for t in topics),
        sum(t.map_open for t in topics), sum(t.map_done for t in topics),
        sum(t.teacher_state is not None for t in topics),
        sum(t.teacher_state == 4 for t in topics),
        sum(t.question_correct for t in topics), sum(t.question_wrong for t in topics),
        sum(t.question_blank for t in topics), other,
        tuple(dict.fromkeys(warnings))
    )
