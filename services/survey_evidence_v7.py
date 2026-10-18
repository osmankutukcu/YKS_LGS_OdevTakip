# -*- coding: utf-8 -*-
"""V7: non-diagnostic, read-only bridge from EXISTING student surveys to Student 360.

No CREATE/UPDATE/INSERT, external calls, behavioral prescriptions, or psychometric
thresholds. Old answers might be coach-entered or quick-filled, so their authorship
cannot be inferred; observed answer counts are NOT scores for personal traits.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
import sqlite3
from typing import Optional

# Catalog metadata follows existing ui/survey_manager.py. Do not copy question text
# or create a competing questionnaire or scoring/diagnosis engine.
META = {
    'study_habits': ('Çalışma stratejileri', 10, 'Geçen hafta hangi çalışma yöntemi işine yaradı?'),
    'time_management': ('Planlama ve zaman', 10, 'Planını uygularken en sık ne engel oluyor?'),
    'procrastination': ('Çalışmaya başlama', 10, 'Başlamayı kolaylaştıracak küçük ilk adım ne olabilir?'),
    'self_efficacy': ('Akademik öz değerlendirme', 10, 'Son dönemde başarabildiğin bir öğrenme örneği neydi?'),
    'mindset_resilience': ('Gelişim ve yeniden deneme', 10, 'Zor bir sorudan sonra hangi stratejiyi değiştirdin?'),
    'digital_distraction': ('Dijital dikkat dağıtıcılar', 8, 'Çalışma sırasında en çok hangi bildirim bölüyor?'),
    'exam_anxiety': ('Sınav deneyimi (hassas)', 10, 'Sınav ortamında zorlandığın anları konuşmak ister misin?'),
    'sleep_energy': ('Uyku ve enerji alışkanlıkları (hassas)', 8, 'Çalışma planındaki enerji ve dinlenme düzenini konuşmak ister misin?'),
    'vark_learning': ('Çalışma tercihleri', 12, 'Hangi öğrenme araçlarını kullanmayı seviyorsun?'),
}

# Real question keys in the existing catalog; no fabrication of unanswered items.
KEYS = {
    'study_habits': tuple(f'sh_{i}' for i in range(1, 11)),
    'time_management': tuple(f'tm_{i}' for i in range(1, 11)),
    'procrastination': tuple(f'p_{i}' for i in range(1, 11)),
    'self_efficacy': tuple(f'se_{i}' for i in range(1, 11)),
    'mindset_resilience': tuple(f'ms_{i}' for i in range(1, 11)),
    'digital_distraction': tuple(f'dd_{i}' for i in range(1, 9)),
    'exam_anxiety': tuple(f'ea_{i}' for i in range(1, 11)),
    'sleep_energy': tuple(f'se_{i}' for i in range(1, 9)),
    'vark_learning': tuple([f'v_{i}' for i in range(1,4)] + [f'a_{i}' for i in range(1,4)] +
                          [f'r_{i}' for i in range(1,4)] + [f'k_{i}' for i in range(1,4)]),
}
# IMPORTANT: self_efficacy and sleep_energy both use se_ prefix, but belong to
# different survey codes; they must never be mixed across students/survey codes.

@dataclass(frozen=True)
class SurveyRecord:
    code: str
    title: str
    recorded_at: str
    answered: int
    total: int
    question_for_conversation: str
    possibly_stale: bool

@dataclass(frozen=True)
class SurveyEvidence:
    student_id: int
    records: tuple[SurveyRecord, ...]
    truncated: bool = False
    malformed: int = 0


def _answered(answers: object, code: str) -> int:
    if not isinstance(answers, dict):
        return 0
    return sum(1 for key in KEYS[code]
               if (type(answers.get(key)) is int and 1 <= answers[key] <= 5))


def _date_age(value, as_of: Optional[datetime]) -> bool:
    if not as_of or not value:
        return False
    try:
        recorded = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if (as_of.tzinfo is None) != (recorded.tzinfo is None):
            return False
        return (as_of - recorded).days > 90
    except (TypeError, ValueError, OverflowError):
        return False


def read_survey_evidence(con: sqlite3.Connection, student_id: int, *, as_of: Optional[datetime] = None, limit: int = 160) -> SurveyEvidence:
    """Use caller's own read-only connection. Filter by exact student ID at SQL level.

    If the existing table is missing this returns an empty evidence summary, never
    creates schema or writes. Order by append-only ID for the latest record per code.
    """
    if type(student_id) is not int or student_id <= 0:
        raise ValueError('Öğrenci kimliği geçersiz.')
    if as_of is None:
        as_of = datetime.now()
    if not (1 <= limit <= 500):
        raise ValueError('Kayıt sınırı geçersiz.')
    table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ogrenci_anket'").fetchone()
    if not table:
        return SurveyEvidence(student_id, ())
    rows = con.execute(
        'SELECT anket_kodu, cevaplar, tarih FROM ogrenci_anket '
        'WHERE ogrenci_id=? ORDER BY id DESC LIMIT ?', (student_id, limit + 1)
    ).fetchall()
    latest = set()
    result = []
    malformed = 0
    for code, payload, date_text in rows[:limit]:
        if code not in META or code in latest:
            continue
        latest.add(code)
        try:
            answers = json.loads(payload) if isinstance(payload, str) else payload
            if not isinstance(answers, dict):
                raise ValueError('Geçersiz yanıt yapısı')
        except (ValueError, TypeError):
            malformed += 1
            continue
        name, total, question = META[code]
        count = _answered(answers, code)
        result.append(SurveyRecord(code, name, str(date_text or 'Tarih belirtilmemiş')[:16],
                                   count, total, question, _date_age(date_text, as_of)))
    return SurveyEvidence(student_id, tuple(result), len(rows) > limit, malformed)


def brief_lines(evidence: SurveyEvidence, *, max_items: int = 3) -> tuple[str, ...]:
    """Short teacher-facing context, not a test result or diagnosis."""
    if not isinstance(evidence, SurveyEvidence):
        return ('Anket özeti geçici olarak alınamadı.',)
    if not evidence.records:
        return ('Mevcut anket kaydı bulunmadı. Koçluk → Anketler ekranında isteğe bağlı değerlendirme yapılabilir.',)
    # Overview/copy panels lack an explicit health-data role check. Do not
    # reveal whether anxiety/sleep questionnaires exist in these previews.
    visible = [r for r in evidence.records if r.code not in {'exam_anxiety', 'sleep_energy'}]
    if not visible:
        return ('Genel öğrenci özetinde gösterilebilecek çalışma alışkanlığı anketi bulunmuyor.',
                'Hassas anketler bu bölümde görüntülenmez; yetkili görüşme alanını kullanın.')
    lines = [f'Çalışma alışkanlığı/tercihi anket kaydı: {len(visible)} (yanıtlayan eski kayıtlarda doğrulanmıyor).']
    for rec in visible[:max_items]:
        status = 'eksik yanıtlı' if rec.answered < rec.total else 'yanıtlanmış'
        old = ' · güncelliği görüşmede kontrol edin' if rec.possibly_stale else ''
        lines.append(f'• {rec.title}: {rec.answered}/{rec.total} {status} · {rec.recorded_at}{old}')
        # Never draw conclusions about a student's mental health from answers.
        lines.append(f'  Görüşme önerisi: {rec.question_for_conversation}')
    if len(visible) > max_items:
        lines.append(f'• Diğer {len(visible)-max_items} çalışma anketi mevcut; ayrıntıları mevcut Anketler sekmesinde.')
    if evidence.malformed or evidence.truncated:
        lines.append('• Bazı geçmiş kayıtların biçimi/tamlığı doğrulanamadı; ayrıntıyı kontrol edin.')
    lines.append('Bu bir öz değerlendirme kaydıdır, psikolojik tanı veya öğrenme başarısı ölçümü değildir.')
    lines.append('Hassas anket yanıtlarını veliye ya da üçüncü kişilere otomatik göndermeyin.')
    return tuple(lines)
