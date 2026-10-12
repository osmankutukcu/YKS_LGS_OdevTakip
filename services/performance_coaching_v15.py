"""V15: read-only performance/coach decision support.

Separate assignment-follow-up evidence from exam measurements. Exam comparisons
are only between different dates in the same exam type, subject and sufficiently documented
question count; neither comparable records nor net changes establish mastery.
Never updates the database, generates assignments, or contacts online services.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from collections import defaultdict
import sqlite3

from services.performance_evidence_v14 import EvidenceResult, StudentEvidence


def _exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in con.execute(f'PRAGMA table_info("{table}")')}


def _day(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    raw = str(value).strip()
    try:
        return date.fromisoformat(raw[:10])
    except (ValueError, TypeError):
        for fmt in ('%d.%m.%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(raw.split()[0], fmt).date()
            except ValueError:
                pass
        return None


def _number(value) -> float | None:
    try:
        v = float(value)
        return v if isfinite(v) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _name(value) -> str:
    return " ".join(str(value or '').split())


@dataclass(frozen=True)
class ExamObservation:
    day: date
    kind: str
    subject: str
    net: float
    observed_questions: int | None
    source: str
    exam_id: int


@dataclass(frozen=True)
class CoachRow:
    student_id: int
    student_name: str
    homework_label: str
    overdue_count: int
    exam_label: str
    evidence_level: str
    action: str
    detail: str
    priority: int


def _load_exam_rows(con: sqlite3.Connection, as_of: date, active_ids: set[int]) -> tuple[dict[int, list[ExamObservation]], dict[int, set[str]], int]:
    """Keep primary and legacy schemas distinct, do not merge or deduplicate by name."""
    records: dict[int, list[ExamObservation]] = defaultdict(list)
    sources: dict[int, set[str]] = defaultdict(set)
    rejected = 0
    # New denemeler schema: explicitly registered blank counts.
    if _exists(con, 'denemeler') and _exists(con, 'deneme_sonuclari'):
        ecols, scols = _cols(con, 'denemeler'), _cols(con, 'deneme_sonuclari')
        if {'id', 'tarih', 'tur'} <= ecols and {'id', 'deneme_id', 'ogrenci_id', 'ders_adi', 'dogru', 'yanlis', 'net'} <= scols:
            blank = 's.bos' if 'bos' in scols else 'NULL'
            sql = f'''SELECT s.ogrenci_id, s.id, d.id, d.tarih, d.tur,
                        s.ders_adi, s.dogru, s.yanlis, {blank}, s.net
                     FROM deneme_sonuclari s
                     INNER JOIN denemeler d ON d.id=s.deneme_id'''
            for sid, rid, eid, dayraw, kindraw, subjectraw, correct, wrong, empty, netraw in con.execute(sql):
                try: sid = int(sid)
                except (TypeError, ValueError):
                    rejected += 1; continue
                if sid not in active_ids:
                    continue
                sources[sid].add('yeni')
                day = _day(dayraw)
                kind, subject = _name(kindraw), _name(subjectraw)
                right, wrong_n, blank_n, net = map(_number, (correct, wrong, empty, netraw))
                if (day is None or day > as_of or not kind or not subject or net is None
                    or right is None or wrong_n is None or right < 0 or wrong_n < 0
                    or (blank_n is not None and blank_n < 0)):
                    rejected += 1; continue
                # The current application's exam entry often omits `bos` and
                # SQLite supplies its DEFAULT 0. In that case right+wrong is
                # only an answered count, NOT an official question total.
                # Conservative policy: zero/unknown blanks cannot establish
                # an equal denominator, even if the pupil answered all items.
                if (not right.is_integer() or not wrong_n.is_integer()
                    or (blank_n is not None and not blank_n.is_integer())
                    or net > right + 1e-6 or net < -wrong_n - 1e-6):
                    rejected += 1; continue
                observed = None
                if blank_n is not None and blank_n > 0:
                    size = right + wrong_n + blank_n
                    if size >= 1 and size.is_integer():
                        observed = int(size)
                records[sid].append(ExamObservation(day,kind,subject,net,observed,'yeni',int(eid)))
    # Legacy exam format lacks blank counts: display recent result, but don't infer denominator.
    if _exists(con, 'deneme') and _exists(con, 'deneme_sonuc'):
        ecols, scols = _cols(con,'deneme'),_cols(con,'deneme_sonuc')
        if {'id', 'ogrenci_id', 'tarih', 'tur'} <= ecols and {'id', 'deneme_id', 'ders', 'net'} <= scols:
            sql = '''SELECT d.ogrenci_id, d.id, d.tarih, d.tur, s.ders, s.net
                     FROM deneme_sonuc s JOIN deneme d ON d.id=s.deneme_id'''
            for sid, eid, dayraw, kindraw, subjectraw, netraw in con.execute(sql):
                try: sid = int(sid)
                except (TypeError, ValueError):
                    rejected += 1; continue
                if sid not in active_ids:
                    continue
                sources[sid].add('eski')
                day, kind, subject, net = _day(dayraw), _name(kindraw), _name(subjectraw), _number(netraw)
                if day is None or day > as_of or not kind or not subject or net is None:
                    rejected += 1; continue
                records[sid].append(ExamObservation(day,kind,subject,net,None,'eski',int(eid)))
    return records, sources, rejected


def _exam_summary(observations: list[ExamObservation], sources: set[str]) -> tuple[str,str,str,str]:
    if not observations:
        return 'Deneme verisi yok', 'Yok', 'Sınav verisi varsa ekleyin; ödev takibini ayrı değerlendirin', 'Kaydedilmiş ve tarihi geçerli ders sonucu bulunamadı.'
    ordered = sorted(observations, key=lambda x:(x.day,x.exam_id), reverse=True)
    # If multiple storages are populated, favor primary but do not compare across sources.
    pool = [x for x in ordered if x.source == 'yeni'] if 'yeni' in {x.source for x in ordered} else ordered
    details = []
    candidate_pairs = []
    for latest in pool:
        for earlier in pool:
            if (latest.day <= earlier.day or latest.source != earlier.source
                or latest.kind.casefold() != earlier.kind.casefold()
                or latest.subject.casefold() != earlier.subject.casefold()
                or latest.observed_questions is None or earlier.observed_questions is None
                or latest.observed_questions != earlier.observed_questions):
                continue
            delta = latest.net - earlier.net
            candidate_pairs.append((latest,earlier,delta))
            break
    other_source = ' Diğer sınav kayıt kaynağı ayrıca mevcut; sonuçlar birleştirilmedi.' if len(sources) > 1 else ''
    if candidate_pairs:
        # One useful, recent comparison per student; do not overemphasize any small change.
        candidate_pairs.sort(key=lambda p:(p[0].day,p[1].day), reverse=True)
        latest, earlier, delta = candidate_pairs[0]
        label = f'{latest.kind} / {latest.subject}: {earlier.net:g} → {latest.net:g} net ({delta:+.1f})'
        detail = (f'Karşılaştırılan tarihler: {earlier.day:%d.%m.%Y} ve {latest.day:%d.%m.%Y}. '
                  f'Kaydedilmiş soru adedi: {latest.observed_questions}. Sınavların güçlüğünün eşitliği doğrulanmadı.' + other_source)
        if delta < 0:
            return label, 'Sınırlı karşılaştırma', 'Net farkının nedenini ve ölçme koşullarını kontrol edin', detail
        return label, 'Sınırlı karşılaştırma', 'Düzeni izleyin; net değişimi öğrenme kanıtı değildir', detail
    latest = pool[0]
    label = f'{latest.kind} / {latest.subject}: {latest.net:g} net ({latest.day:%d.%m.%Y})'
    detail = 'Karşılaştırılabilir iki farklı tarihli, aynı tür/ders/soru sayısında sonuç bulunamadı.' + other_source
    return label, 'Tek ölçüm', 'Benzer kapsamda başka ölçüm olmadan ilerleme yorumu yapmayın', detail


def compute_coach_rows(con: sqlite3.Connection, evidence: EvidenceResult, *, as_of: date | None = None) -> tuple[CoachRow, ...]:
    """Deterministic, read-only coach panel; no database writes or state changes."""
    today = as_of or date.today()
    active = {student.student_id for student in evidence.students}
    exams, sources, rejected = _load_exam_rows(con, today, active)
    result = []
    for student in evidence.students:
        label, confidence, action, detail = _exam_summary(exams.get(student.student_id,[]),sources.get(student.student_id,set()))
        overdue = student.overdue_all
        if student.uncertain_count:
            action = 'Önce ödev kaynak tutarsızlığını kontrol edin; ' + action
            priority = 0
        elif overdue:
            action = f'{overdue} gecikmiş açık ödevi kontrol edin; ' + action
            priority = 1
        elif confidence == 'Sınırlı karşılaştırma' and 'nedenini' in action:
            priority = 2
        else:
            priority = 3
        hw = (f'{student.last30.completed}/{student.last30.total}'
              + (' (veri sınırlı)' if student.last30.total < 5 else ''))
        detail += (' Ödev tamamlama oranı akademik kazanım değildir; ölçülen net farklılığı neden-sonuç ilişkisi göstermez.'
                   ' Ödev kayıtları geçmişe dönük gerçek durum fotoğrafı değildir.')
        result.append(CoachRow(student.student_id,student.name,hw,overdue,label,confidence,action,detail,priority))
    return tuple(sorted(result,key=lambda x:(x.priority,-x.overdue_count,x.student_name.casefold(),x.student_id)))
