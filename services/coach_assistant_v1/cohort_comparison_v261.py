# -*- coding: utf-8 -*-
"""V26.1 — conservative, read-only, privacy-preserving *exploratory* cohort signal.

NOT a class rank, standardized test comparison, predictive model or online request.
Only locally stored V25 independent assessments count. Legacy homework ticks do not.
The only cohort linkage in this schema is ana_grup + alt_grup; this can be an
educational level instead of an actual class/branch. Never expose peer identities.

Hard safety gates: same group label, course, exact topic, assessment mode, recent
30-day window, >=5 responses per student, >=5 *distinct* peers. A difference is
only descriptive since common question IDs/difficulty are not recorded.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
import sqlite3

from services.coach_assistant_v1.shared_rules_v260 import fold, lesson_key

WINDOW_DAYS = 30
MIN_ATTEMPTS = 5
MIN_PEERS = 5
MAX_GROUP = 120
MAX_OBSERVATION_ROWS = 4000


@dataclass(frozen=True)
class CohortComparison:
    status: str  # available | missing_source | insufficient | oversize | invalid_scope
    lesson: str
    topic: str
    student_accuracy: float | None = None
    peer_median: float | None = None
    peers: int = 0
    student_attempts: int = 0
    mode: str = ''
    window_days: int = WINDOW_DAYS
    reason: str = ''

    @property
    def available(self):
        return self.status == 'available'

    def short_message(self) -> str:
        if not self.available:
            return ''
        # No claim of a standardized rank: item sets/difficulty unknown.
        return (f'Aynı grup etiketindeki {self.peers} öğrencinin son {self.window_days} gündeki '
                f'{self.mode} ölçümlerinde ortanca doğruluk %{self.peer_median:g}; '
                f'bu öğrencinin %{self.student_accuracy:g} ({self.student_attempts} yanıt). '
                'Fark yalnızca ön sinyaldir; soru eşdeğerliği doğrulanmadı.')

    def evidence(self) -> tuple[str, ...]:
        if not self.available:
            return (f'Grup karşılaştırması yapılamadı: {self.reason}',)
        return (f'Kapsam: aynı ana_grup + alt_grup; {self.peers} ayrı karşılaştırma öğrencisi',
                f'Aynı ders/konu ve ölçüm türü: {self.lesson} / {self.topic} / {self.mode}',
                f'Son {self.window_days} gün; öğrenci {self.student_attempts} yanıt',
                'Güçlük, soru kimliği ve gerçek sınıf/şube eşitliği kayıtlarda doğrulanmadı',
                'Kişisel öğrenci listesi okunmaz, gösterilmez; yalnızca grup ortancası sunulur')


def _result(status, lesson, topic, reason):
    return CohortComparison(status=status, lesson=lesson, topic=topic, reason=reason)


def _has_source(con):
    return all(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
               for table in ('ogrenci', 'adaptive_observation_v25'))


def compare_topic(con: sqlite3.Connection, student_id: int, *, lesson: str,
                  topic: str, today: date | None = None) -> CohortComparison:
    """No DDL, connection mutation, student names, peer-level result or network access.

    Precondition: caller has already authorized teacher access to selected student;
    group aggregates are from the teacher's *local* database, not another institution.
    """
    if type(student_id) is not int or student_id <= 0 or not lesson_key(lesson) or not fold(topic):
        return _result('invalid_scope', lesson, topic, 'Geçerli öğrenci, ders ve konu gerekiyor.')
    if not _has_source(con):
        return _result('missing_source', lesson, topic, 'Uyarlanabilir kazanım ölçüm tablosu bulunmuyor.')
    current = today or date.today()
    if not isinstance(current, date):
        raise ValueError('Geçersiz analiz tarihi')
    start = (current - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    end = current.isoformat()
    target = con.execute('SELECT ana_grup, alt_grup, COALESCE(aktif,1) FROM ogrenci WHERE id=?',
                         (student_id,)).fetchone()
    if not target or not target[2] or not str(target[0] or '').strip() or not str(target[1] or '').strip():
        return _result('invalid_scope', lesson, topic,
                       'Öğrencinin aktif grup/kademe etiketi eksik; karşılaştırma yapılamaz.')
    ana, alt = str(target[0]).strip().upper(), str(target[1]).strip()
    if ana not in ('LGS', 'YKS'):
        return _result('invalid_scope', lesson, topic, 'Aynı müfredat düzeyi belirlenemedi.')
    # Exceeding the fixed cap suppresses the comparison instead of emitting a
    # biased estimate from a truncated class/group sample.
    group_ids = [int(r[0]) for r in con.execute(
        '''SELECT id FROM ogrenci WHERE id<>? AND COALESCE(aktif,1)=1
           AND UPPER(TRIM(COALESCE(ana_grup,'')))=?
           AND TRIM(COALESCE(alt_grup,''))=? ORDER BY id LIMIT ?''',
        (student_id, ana, alt, MAX_GROUP + 1))]
    if len(group_ids) > MAX_GROUP:
        return _result('oversize', lesson, topic,
                       'Grup çok geniş; örneklem kesilerek yanıltıcı karşılaştırma yapılmadı.')
    if len(group_ids) < MIN_PEERS:
        return _result('insufficient', lesson, topic,
                       'Gizlilik ve karşılaştırma için en az 5 başka aktif öğrenci gerekli.')

    # Pull bounded rows and aggregate only; no peer names/ids escape this function.
    # Using group-membership placeholders rather than a global full-table scan.
    ids = [student_id] + group_ids
    placeholders = ','.join('?' for _ in ids)
    rows = con.execute(
        f'''SELECT student_id, lesson, topic, mode, correct, wrong, blank, observed_on
            FROM adaptive_observation_v25
            WHERE student_id IN ({placeholders}) AND observed_on BETWEEN ? AND ?
            ORDER BY observed_on DESC, id DESC LIMIT ?''',
        (*ids, start, end, MAX_OBSERVATION_ROWS + 1)).fetchall()
    if len(rows) > MAX_OBSERVATION_ROWS:
        return _result('oversize', lesson, topic,
                       'Çok sayıda ölçüm kaydı var; kısmi veriden ortanca üretilmedi.')
    key_l, key_t = lesson_key(lesson), fold(topic)
    matched = []
    for r in rows:
        if lesson_key(r[1]) != key_l or fold(r[2]) != key_t:
            continue
        try:
            c, w, b = (int(r[i]) for i in (4, 5, 6))
            if min(c, w, b) < 0 or c + w + b == 0:
                continue
        except (ValueError, TypeError):
            continue
        matched.append((int(r[0]), str(r[3] or ''), c, c + w + b))
    # Assessment MODE must match; newer students/assessment cannot be compared
    # with old modes even within the same course and topic.
    target_modes = [mode for sid, mode, c, total in matched if sid == student_id and mode]
    if not target_modes:
        return _result('insufficient', lesson, topic,
                       'Seçili öğrencide son 30 güne ait bağımsız konu ölçümü bulunamadı.')
    mode = target_modes[0]  # records are ordered newest first
    tally: dict[int, list[int]] = {}
    for sid, row_mode, correct, total in matched:
        if row_mode != mode:
            continue
        current_totals = tally.setdefault(sid, [0, 0])
        current_totals[0] += correct
        current_totals[1] += total
    student = tally.get(student_id, [0, 0])
    if student[1] < MIN_ATTEMPTS:
        return _result('insufficient', lesson, topic,
                       'Öğrencinin aynı türde en az 5 yanıtı bulunmalı.')
    # The median weights *students* equally, not high-volume question counts.
    valid_peers = [100.0 * c / n for sid, (c, n) in tally.items()
                   if sid != student_id and n >= MIN_ATTEMPTS]
    if len(valid_peers) < MIN_PEERS:
        return _result('insufficient', lesson, topic,
                       'Aynı konu ve ölçüm türünde en az 5 ayrı karşılaştırılabilir öğrenci bulunmadı.')
    return CohortComparison(
        status='available', lesson=lesson, topic=topic,
        student_accuracy=round(100.0 * student[0] / student[1], 1),
        peer_median=round(float(median(valid_peers)), 1),
        peers=len(valid_peers), student_attempts=student[1], mode=mode,
    )


def enrich_answer(con, ctx, answer, question: str, *, lesson_scope: str = '',
                  previous_anchor: str = ''):
    """Quiet one-line extra for priority queries; explicit cohort question is supported.

    Preserves original answer when there is no comparable cohort evidence. Never
    changes the homework/control UI; service runs in the existing question worker.
    """
    from dataclasses import replace
    from services.coach_assistant_v1.dialogue import CoachAnswer, _search_fold
    from services.coach_assistant_v1.shared_rules_v260 import scoped_topics

    text = _search_fold(question)
    anchor = _search_fold(previous_anchor)
    is_group = any(x in text for x in ('sinif', 'grup', 'akran', 'diger ogrenci', 'karsilastir'))
    is_priority = any(x in text or x in anchor for x in ('oncelik', 'akademik ihtiyac', 'ilk hangi'))
    if not (is_group or is_priority):
        return answer
    if answer.title in ('Ders kapsamı uyuşmuyor', 'Ders adı belirsiz'):
        return answer  # A rejected mismatched question cannot be rescued by peer data.
    # Never use an unscoped subject, inferred guessed curriculum, or stale teacher scope.
    if not lesson_scope:
        if is_group:
            return CoachAnswer('Grup karşılaştırması için ders seçin',
                               'Önce ders sekmesini seçin. Dersler arasında karışık ölçümler karşılaştırılmaz.',
                               ('Kaynak: yerel akademik ölçümler',), 'btnOgrenme')
        return answer
    topics = scoped_topics(ctx.topics, lesson_scope)
    eligible = sorted((t for t in topics if t.attempts >= MIN_ATTEMPTS and t.accuracy is not None),
                      key=lambda t: (t.accuracy, -t.attempts, fold(t.name)))
    if not eligible:
        if is_group:
            return CoachAnswer('Grup karşılaştırması için ölçüm gerekli',
                               'Seçili dersin konu ölçümleri yeterli değil. Önce bağımsız kısa yoklama uygulayın.',
                               ('Ödev tamamlanması ölçüm sayılmaz.',), 'btnOgrenme')
        return answer
    # Compare only *the one topic* already identified as the student's priority
    # (worst reliable score); no class-wide ranking or peer records disclosed.
    chosen = eligible[0]
    if not is_group and chosen.accuracy >= 55:
        return answer  # Quiet mode: no extra notification for a non-critical topic.
    try:
        comparison = compare_topic(con, ctx.student_id, lesson=chosen.lesson, topic=chosen.name)
    except (sqlite3.Error, ValueError, OverflowError):
        comparison = _result('missing_source', chosen.lesson, chosen.name, 'Yerel veri okunamadı.')
    if is_group:
        if not comparison.available:
            return CoachAnswer('Grup karşılaştırması için kanıt yetersiz',
                               f'{chosen.lesson} / {chosen.name}: {comparison.reason} '
                               'Diğer öğrenciler hakkında tahmin yapılmadı.',
                               comparison.evidence(), 'btnOgrenme')
        return CoachAnswer('Konuya göre keşif amaçlı grup sinyali',
                           f'{chosen.lesson} / {chosen.name}: {comparison.short_message()} '
                           'İlk adım farklı gün kısa doğrulama yoklamasıdır.',
                           comparison.evidence(), 'btnOgrenme')
    if comparison.available:
        return replace(answer, message=answer.message + '\nGrup sinyali: ' + comparison.short_message(),
                       evidence=answer.evidence + comparison.evidence())
    return answer
