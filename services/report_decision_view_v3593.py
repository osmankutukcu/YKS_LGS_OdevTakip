# -*- coding: utf-8 -*-
"""V3.5.93: student-scoped, read-only teacher decision view.

Transforms typed evidence and the V3592 review plan into a bounded, human
readable UI model. No writes, diagnostic labels, external traffic or automation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import sqlite3

from services.report_academic_bridge_v3591 import read_academic_evidence
from services.report_intervention_plan_v3592 import plan_teacher_review


@dataclass(frozen=True)
class CourseRow:
    title: str
    exam_line: str
    topic_line: str


@dataclass(frozen=True)
class DecisionView:
    student_id: int
    as_of: date
    days: int
    status: str
    courses: tuple[CourseRow, ...]
    steps: tuple[tuple[str, str, str], ...]
    warnings: tuple[str, ...]
    scope: str
    limitation: str


def make_decision_view(con: sqlite3.Connection, student_id: int, *,
                       days: int = 90, as_of: date | None = None) -> DecisionView:
    """Read only the requested student's academic sources; never infer mastery.

    Student identity, record scope and reporting date are retained in the result,
    so consumers can reject an obsolete view after a selection change.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Öğrenci seçimi geçersiz.')
    if type(days) is not int or days not in (30, 90, 180):
        raise ValueError('Desteklenmeyen inceleme dönemi.')
    reference = date.today() if as_of is None else as_of
    if type(reference) is not date:
        raise ValueError('Rapor tarihi geçersiz.')
    evidence = read_academic_evidence(con, student_id, reference_day=reference,
                                      lookback_days=days)
    advice = plan_teacher_review(evidence)
    rows: list[CourseRow] = []
    for course in evidence.courses[:4]:
        if course.repeated_measurement:
            exam_line = 'Aynı sınav/ders için mükerrer ölçüm; net doğrulanmadı.'
        elif course.exam_net is None:
            exam_line = 'Doğrulanmış ders neti yok.'
        else:
            net = f'{course.exam_net:g}'.replace('.', ',')
            question_info = (f'{course.observed_questions} soru' if course.observed_questions
                             is not None else 'soru sayısı doğrulanmadı')
            exam_line = f'{course.exam_day:%d.%m.%Y} · {net} net · {question_info}'
        if course.topic_count is None or course.marked_topics is None:
            topic_line = 'Konu takip kaynağı doğrulanamadı.'
        else:
            topic_line = (f'{course.marked_topics}/{course.topic_count} öğretmen konu işareti '
                          '· öğrenme başarısı ölçümü değildir')
            if course.conflicting_topics:
                topic_line += f' · {course.conflicting_topics} çelişkili kayıt'
        rows.append(CourseRow(course.display_name, exam_line, topic_line))
    steps = tuple((s.heading, s.instruction, s.basis) for s in advice.steps[:3])
    return DecisionView(student_id=student_id, as_of=reference, days=days,
                        status=advice.level, courses=tuple(rows), steps=steps,
                        warnings=evidence.warnings[:12], scope=evidence.scope,
                        limitation=advice.limitation)
