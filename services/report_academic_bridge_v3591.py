# -*- coding: utf-8 -*-
"""V3.5.91: student-ID-scoped, read-only academic evidence for reports.

An exam result is a lesson-level *measurement*, not an assessment of a named
curriculum outcome. Coach topic status is a teacher *marking*, not proof of
mastery. Never join these by a guessed topic or synthesize exam success.
Reuses the V15 exam-validation reader and V3556's strict lesson aliases.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import sqlite3

from services.performance_coaching_v15 import _load_exam_rows
from services.student_exam_bridge_v3556 import _ALIAS_LOOKUP, _norm
from services.exam_planning_v3555 import COURSE_NAMES


@dataclass(frozen=True)
class CourseMeasurement:
    """A source-scoped observation, never a claim of topic mastery."""
    course_code: str
    display_name: str
    exam_day: date
    exam_net: float | None  # None for multiple ambiguous measurements
    observed_questions: int | None
    topic_count: int | None  # None when topic source cannot be verified
    marked_topics: int | None
    conflicting_topics: int
    repeated_measurement: bool


@dataclass(frozen=True)
class AcademicEvidence:
    status: str  # kayıt | eksik | doğrulanamadı
    value: str
    scope: str
    warnings: tuple[str, ...]
    courses: tuple[CourseMeasurement, ...] = ()  # V3592 typed, limited evidence


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    if not con.execute('SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?',
                       (table,)).fetchone():
        return set()
    return {str(r[1]) for r in con.execute(f'PRAGMA table_info("{table}")')}


def _course(raw_subject: object, raw_kind: object) -> str | None:
    """Reject ambiguous or contradictory exam/subject labels, don't fuzzy match."""
    kind = _norm(raw_kind)
    subject = _norm(raw_subject)
    if kind not in {'tyt', 'ayt', 'lgs', 'msü'}:
        return None
    if subject in {'matematik', 'mat'}:
        return {'tyt': 'tyt_matematik', 'ayt': 'ayt_matematik',
                'lgs': 'lgs_matematik', 'msü': 'tyt_matematik'}[kind]
    if subject in {'türkçe', 'turkce'}:
        return 'lgs_turkce' if kind == 'lgs' else ('turkce' if kind in {'tyt', 'msü'} else None)
    if subject in {'fen bilimleri', 'fen'}:
        return 'lgs_fen' if kind == 'lgs' else None
    code = _ALIAS_LOOKUP.get(subject)
    if code is None:
        return None
    if code.startswith('lgs_') and kind != 'lgs':
        return None
    if code.startswith('tyt_') and kind not in {'tyt', 'msü'}:
        return None
    if code.startswith('ayt_') and kind != 'ayt':
        return None
    if kind == 'lgs' and code not in {'lgs_matematik','lgs_turkce','lgs_fen',
                                      'lgs_inkilap','lgs_dinkulturu','lgs_ingilizce'}:
        return None
    return code


def read_academic_evidence(con: sqlite3.Connection, student_id: int, *,
                           reference_day: date | None = None, lookback_days: int = 90,
                           max_exam_rows: int = 20000, max_topic_rows: int = 5000) -> AcademicEvidence:
    """Never mutate con. Only the explicitly requested student's records.

    V15 may scan exam tables to validate their source semantics; the bounded
    counts below refuse that operation for very large datasets rather than
    claim a complete assessment. It does not send records to a network.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Geçerli öğrenci kimliği gerekli.')
    day = reference_day or date.today()
    if not isinstance(day, date) or isinstance(day, datetime):
        raise ValueError('Geçerli rapor tarihi gerekli.')
    if type(lookback_days) is not int or not 1 <= lookback_days <= 366:
        raise ValueError('Geçerli akademik ölçüm dönemi gerekli.')
    if type(max_exam_rows) is not int or max_exam_rows < 1 or type(max_topic_rows) is not int or max_topic_rows < 1:
        raise ValueError('Satır limitleri pozitif olmalı.')
    base = _cols(con, 'ogrenci')
    if 'id' not in base:
        return AcademicEvidence('doğrulanamadı', 'Öğrenci tablosu okunamıyor.',
                                'Seçili öğrenci', ('Kimlik kaynağı bulunamadı.',))
    active = 'aktif' if 'aktif' in base else '1'
    row = con.execute(f'SELECT id, {active} FROM ogrenci WHERE id=?', (student_id,)).fetchone()
    if row is None or str(row[1]).strip() in {'0', 'False', 'false'}:
        raise ValueError('Öğrenci bulunamadı veya aktif değil.')
    warnings: list[str] = []
    exam_available = (
        {'id','tarih','tur'} <= _cols(con, 'denemeler')
        and {'id','deneme_id','ogrenci_id','ders_adi','dogru','yanlis','net'} <= _cols(con, 'deneme_sonuclari')
    ) or (
        {'id','ogrenci_id','tarih','tur'} <= _cols(con, 'deneme')
        and {'id','deneme_id','ders','net'} <= _cols(con, 'deneme_sonuc')
    )
    exam_records = []
    if exam_available:
        count = 0
        for name in ('deneme_sonuclari', 'deneme_sonuc'):
            if 'id' in _cols(con, name):
                count += int(con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        if count > max_exam_rows:
            warnings.append('Deneme kayıt hacmi denetim sınırını aşıyor; akademik eşleştirme yapılmadı.')
            exam_available = False
        else:
            exams, flags, _ = _load_exam_rows(con, day, {student_id})
            exam_records = [r for r in exams.get(student_id, [])
                            if day-timedelta(days=lookback_days-1) <= r.day <= day]
            if len(flags.get(student_id, set())) > 1:
                warnings.append('İki farklı deneme kayıt kaynağı mevcut; netler toplanmadı.')
            # V15's rejected count can include other students; do not expose
            # an unrelated student's data-quality result in this report.
    else:
        warnings.append('Deneme kayıt şeması bulunamadı veya okunamadı; net verisi yok sayılmadı.')

    topic_cols = _cols(con, 'koc_konu_takip')
    topic_available = {'ogrenci_id', 'ders_adi', 'konu_adi', 'durum'} <= topic_cols
    topics: dict[str, dict[str, list[object]]] = {}
    if topic_available:
        rows = con.execute('''SELECT ders_adi, konu_adi, durum FROM koc_konu_takip
                              WHERE ogrenci_id=? LIMIT ?''', (student_id,max_topic_rows+1)).fetchall()
        if len(rows) > max_topic_rows:
            warnings.append('Konu kayıt hacmi denetim sınırını aşıyor; konu eşleştirmesi yapılmadı.')
            topic_available = False
        else:
            for subject, title, status in rows:
                code = _ALIAS_LOOKUP.get(_norm(subject))
                topic = _norm(title)
                if not code or not topic:
                    continue
                topics.setdefault(code, {}).setdefault(topic, []).append(status)
    else:
        warnings.append('Konu adı/ders/durum alanları yok; kazanım düzeyi uydurulmadı.')

    # Prefer primary evidence within each explicitly identified subject.
    grouped: dict[str, list] = {}
    unmatched = 0
    for r in exam_records:
        code = _course(r.subject, r.kind)
        if code:
            grouped.setdefault(code, []).append(r)
        else:
            unmatched += 1
    if unmatched:
        warnings.append(f'{unmatched} deneme ders satırı kesin ders koduyla eşleşmedi; kullanılmadı.')

    lines = []
    course_measurements: list[CourseMeasurement] = []
    usable_measurements = 0
    for course, vals in sorted(grouped.items(),
                               key=lambda pair: max(r.day for r in pair[1]), reverse=True)[:4]:
        primary = [r for r in vals if r.source == 'yeni']
        available = primary if primary else vals
        available.sort(key=lambda r: (r.day, r.exam_id), reverse=True)
        latest = available[0]
        # Duplicate subject measurements for the *same exam* are ambiguous;
        # no invented average/total/net from them.
        duplicates = sum(r.exam_id == latest.exam_id and r.day == latest.day for r in available)
        if duplicates > 1:
            net_label = f'{latest.day:%d.%m.%Y}: aynı sınav/ders için çoklu net kaydı (kontrol gerekli)'
            warnings.append('Aynı deneme ve derse ait birden fazla ölçüm var; net birleştirilmedi.')
        else:
            usable_measurements += 1
            denom = (f' / {latest.observed_questions} soru' if latest.observed_questions
                     is not None else ' (soru sayısı doğrulanmadı)')
            net_label = f'{latest.net:g} net{denom}, {latest.day:%d.%m.%Y}'
        course_topics = topics.get(course, {}) if topic_available else {}
        if topic_available:
            # 4 is teacher's explicit marking, not measured mastery.
            marked = sum(1 for states in course_topics.values()
                         if states and all(str(s) == '4' for s in states))
            conflicts = sum(1 for states in course_topics.values()
                            if any(str(s) == '4' for s in states)
                            and any(str(s) != '4' for s in states))
            topic_label = f'{marked}/{len(course_topics)} öğretmen konu işareti'
            if conflicts:
                topic_label += f'; {conflicts} çelişkili kayıt'
        else:
            marked, conflicts = None, 0
            topic_label = 'konu işaretleri doğrulanamadı'
        course_measurements.append(CourseMeasurement(
            course_code=course, display_name=COURSE_NAMES.get(course, course),
            exam_day=latest.day, exam_net=None if duplicates > 1 else latest.net,
            observed_questions=None if duplicates > 1 else latest.observed_questions,
            topic_count=len(course_topics) if topic_available else None,
            marked_topics=marked, conflicting_topics=conflicts,
            repeated_measurement=duplicates > 1,
        ))
        lines.append(f'{COURSE_NAMES.get(course, course)}: {net_label} | {topic_label}')
    if len(grouped) > 4:
        warnings.append(f'{len(grouped)-4} ek ders ölçümü özet dışında; deneme modülünde incelenebilir.')
    if not lines and topic_available and topics:
        # A topic-only record cannot prove a subject's exam performance.
        lines.append(f'{len(topics)} ders alanında öğretmen konu kaydı; eşleşen güncel deneme yok.')
    if not lines:
        lines.append('Bu dönemde aynı öğrenciye ait, açık ders koduyla eşleşen ölçüm bulunamadı.')
    status = ('kayıt' if usable_measurements and topic_available else
              'eksik' if exam_available and topic_available else 'doğrulanamadı')
    scope = (f'Deneme: son {lookback_days} gün ({day:%d.%m.%Y} itibarıyla); '
             'konu işaretleri: tarih filtresi olmayan öğretmen kayıtları. '
             'Birlikte gösterim neden-sonuç veya kazanım başarısı kanıtı değildir.')
    return AcademicEvidence(status, ' • '.join(lines), scope,
                            tuple(dict.fromkeys(warnings)), tuple(course_measurements))
