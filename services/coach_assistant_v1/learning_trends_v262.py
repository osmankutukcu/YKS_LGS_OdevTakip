# -*- coding: utf-8 -*-
"""V26.2: bounded, read-only longitudinal learning signals for Koça Sor.

Only independently entered adaptive_observation_v25 responses count as assessment.
An assignment checkbox is *never* treated as learning evidence. The observational
windows DO NOT imply equivalent items/difficulty or a causal improvement/decline.
No peer identities, network requests, database migrations or writes occur here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import sqlite3

from services.coach_assistant_v1.shared_rules_v260 import fold, lesson_key

WINDOW_DAYS = 28
MAX_OBSERVATION_ROWS = 1600
MIN_ANSWERS_PER_WINDOW = 8
MIN_DAYS_PER_WINDOW = 2
MAX_LATEST_AGE_DAYS = 14
DESCRIPTIVE_DELTA_POINTS = 15.0


@dataclass(frozen=True)
class LearningTrend:
    status: str  # available | insufficient | stale | missing_source | oversize | invalid_scope
    lesson: str
    topic: str
    mode: str = ''
    direction: str = ''  # rise | fall | flat
    earlier_accuracy: float | None = None
    recent_accuracy: float | None = None
    delta_points: float | None = None
    earlier_answers: int = 0
    recent_answers: int = 0
    earlier_days: int = 0
    recent_days: int = 0
    latest_on: str = ''
    reason: str = ''

    @property
    def available(self) -> bool:
        return self.status == 'available'

    def short_message(self) -> str:
        if not self.available:
            return ''
        label = {'rise': 'artış', 'fall': 'düşüş', 'flat': 'belirgin yön değişikliği yok'}[self.direction]
        return (f'{self.lesson} / {self.topic}: önceki {WINDOW_DAYS} günde '
                f'%{self.earlier_accuracy:g} ({self.earlier_answers} yanıt), '
                f'son {WINDOW_DAYS} günde %{self.recent_accuracy:g} '
                f'({self.recent_answers} yanıt); {label} sinyali '
                f'({self.delta_points:+g} yüzde puan). '
                'Soru güçlükleri eşdeğer kabul edilemez; kesin öğrenme değişimi değildir.')

    def evidence(self) -> tuple[str, ...]:
        if not self.available:
            return (f'Zaman analizi yapılamadı: {self.reason}',)
        return (
            f'Ölçüm türü: {self.mode}; aynı öğrenci, aynı ders ve konu',
            f'Önceki dönem: {self.earlier_answers} yanıt, {self.earlier_days} ayrı tarih',
            f'Son dönem: {self.recent_answers} yanıt, {self.recent_days} ayrı tarih',
            f'En son ölçüm: {self.latest_on}; fark: {self.delta_points:+g} yüzde puan',
            'Ödev tikleri ölçüm değildir; soruların eşdeğerliği ve neden-sonuç kanıtlanmadı',
        )


def _no(status: str, lesson: str, topic: str, reason: str) -> LearningTrend:
    return LearningTrend(status, lesson, topic, reason=reason)


def analyze_topic(con: sqlite3.Connection, student_id: int, *, lesson: str,
                  topic: str, today: date | None = None) -> LearningTrend:
    """Compare two disjoint 28-day windows; never modify the supplied connection.

    The latest assessment mode anchors both windows; no pooling across modes.
    At least 8 responses on 2 separate days in EACH window are required.
    """
    if type(student_id) is not int or student_id <= 0 or not lesson_key(lesson) or not fold(topic):
        return _no('invalid_scope', lesson, topic, 'Geçerli öğrenci, ders ve konu gerekiyor.')
    now = today or date.today()
    if not isinstance(now, date) or isinstance(now, datetime):
        return _no('invalid_scope', lesson, topic, 'Analiz tarihi geçersiz.')
    source = con.execute('''SELECT 1 FROM sqlite_master
                            WHERE type='table' AND name='adaptive_observation_v25' ''').fetchone()
    if not source:
        return _no('missing_source', lesson, topic, 'Bağımsız ölçüm veri kaynağı bulunamadı.')
    earliest = now - timedelta(days=2 * WINDOW_DAYS - 1)
    boundary = now - timedelta(days=WINDOW_DAYS - 1)
    # Query by indexed student/date; bound the entire input to avoid unbounded work.
    rows = con.execute('''SELECT lesson, topic, mode, correct, wrong, blank, observed_on
                          FROM adaptive_observation_v25
                          WHERE student_id=? AND observed_on BETWEEN ? AND ?
                          ORDER BY observed_on DESC, id DESC LIMIT ?''',
                       (student_id, earliest.isoformat(), now.isoformat(),
                        MAX_OBSERVATION_ROWS + 1)).fetchall()
    if len(rows) > MAX_OBSERVATION_ROWS:
        return _no('oversize', lesson, topic,
                   'Ölçüm kayıt sayısı güvenli sınırı aşıyor; eksik örnekten sonuç üretilmedi.')
    lesson_id, topic_id = lesson_key(lesson), fold(topic)
    valid = []
    for row in rows:
        if lesson_key(row[0]) != lesson_id or fold(row[1]) != topic_id:
            continue
        try:
            d = date.fromisoformat(str(row[6]))
            correct, wrong, blank = (int(row[i]) for i in (3, 4, 5))
            if min(correct, wrong, blank) < 0 or correct + wrong + blank == 0:
                continue
            # Guard against bad or fabricated future dates.
            if not earliest <= d <= now:
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        mode = str(row[2] or '').strip()
        if mode:
            valid.append((d, mode, correct, correct + wrong + blank))
    if not valid:
        return _no('insufficient', lesson, topic,
                   'Son 56 günde bu konuda geçerli bağımsız ölçüm bulunmadı.')
    mode = valid[0][1]  # latest valid assessment mode, no mixed-mode comparisons
    earlier = [r for r in valid if r[1] == mode and r[0] < boundary]
    recent = [r for r in valid if r[1] == mode and r[0] >= boundary]
    if not recent or (now - recent[0][0]).days > MAX_LATEST_AGE_DAYS:
        return _no('stale', lesson, topic,
                   'Son 14 günde güncel, aynı türde ölçüm bulunmadı.')
    n_old = sum(r[3] for r in earlier)
    n_new = sum(r[3] for r in recent)
    days_old, days_new = len({r[0] for r in earlier}), len({r[0] for r in recent})
    if (min(n_old, n_new) < MIN_ANSWERS_PER_WINDOW or
            min(days_old, days_new) < MIN_DAYS_PER_WINDOW):
        return _no('insufficient', lesson, topic,
                   'Her 28 günlük dönemde en az 8 yanıt ve iki ayrı ölçüm günü gerekiyor.')
    old_acc = 100.0 * sum(r[2] for r in earlier) / n_old
    new_acc = 100.0 * sum(r[2] for r in recent) / n_new
    delta = new_acc - old_acc
    direction = ('rise' if delta >= DESCRIPTIVE_DELTA_POINTS else
                 'fall' if delta <= -DESCRIPTIVE_DELTA_POINTS else 'flat')
    return LearningTrend('available', lesson, topic, mode=mode, direction=direction,
                         earlier_accuracy=round(old_acc, 1), recent_accuracy=round(new_acc, 1),
                         delta_points=round(delta, 1),
                         earlier_answers=n_old, recent_answers=n_new,
                         earlier_days=days_old, recent_days=days_new,
                         latest_on=recent[0][0].isoformat())


def _recent_verification(con: sqlite3.Connection, student_id: int, *, lesson: str,
                         topic: str, today: date | None = None):
    """Return (status, accuracy, answers) for recent independent measurements only.

    An unreadable source is distinct from a student having no valid observations.
    The latest assessment mode anchors the 28-day score; modes are never pooled.
    """
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='adaptive_observation_v25'").fetchone():
        return ('missing_source', None, 0)
    now = today or date.today()
    since = (now - timedelta(days=27)).isoformat()
    rows = con.execute('''SELECT lesson,topic,mode,correct,wrong,blank,observed_on
                          FROM adaptive_observation_v25
                          WHERE student_id=? AND observed_on BETWEEN ? AND ?
                          ORDER BY observed_on DESC,id DESC LIMIT ?''',
                       (student_id, since, now.isoformat(), MAX_OBSERVATION_ROWS + 1)).fetchall()
    if len(rows) > MAX_OBSERVATION_ROWS:
        return ('oversize', None, 0)
    mode = None
    totals = [0, 0]
    for row in rows:
        if lesson_key(row[0]) != lesson_key(lesson) or fold(row[1]) != fold(topic):
            continue
        try:
            c, w, b = (int(row[i]) for i in (3, 4, 5))
            d = date.fromisoformat(str(row[6]))
            if min(c, w, b) < 0 or c + w + b == 0 or not (now - timedelta(days=27) <= d <= now):
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        candidate_mode = str(row[2] or '').strip()
        if not candidate_mode:
            continue
        if mode is None:
            mode = candidate_mode
        if mode == candidate_mode:
            totals[0] += c
            totals[1] += c + w + b
    if totals[1] < 5:
        return ('insufficient', None, totals[1])
    return ('available', round(100 * totals[0] / totals[1], 1), totals[1])


def enrich_answer(con: sqlite3.Connection, ctx, answer, question: str,
                  *, lesson_scope: str = '', previous_anchor: str = ''):
    """Append at most one short, course-matched action-worthy signal.

    Explicit trend inquiries receive a concise assessment or a clear insufficiency
    explanation. Other questions remain unchanged unless a priority's principal
    topic has a measured rise/fall; a second paragraph is not shown for flat data.
    """
    from dataclasses import replace
    from services.coach_assistant_v1.dialogue import CoachAnswer
    from services.coach_assistant_v1.shared_rules_v260 import scoped_topics
    q = fold(question)
    anchor = fold(previous_anchor)
    # Preserve the existing single-click 'Ödev–öğrenme' shortcut, but replace
    # broad student-wide counts with a measured COURSE/TOPIC discrepancy when
    # records genuinely support one. A completed homework is NOT evidence of mastery.
    gap_request = (('odev' in q and any(k in q for k in ('ogrenme', 'kanit', 'tutarli')))
                   or 'gizli ogrenme acigi' in q or 'ogrenme boslugu' in q)
    if gap_request and lesson_key(lesson_scope) and answer.title not in (
            'Ders kapsamı uyuşmuyor', 'Ders adı belirsiz'):
        if 'Konu kayıtları okunamadı' in ctx.unavailable_sources:
            return CoachAnswer('Ödev–ölçüm analizi şu anda yapılamıyor',
                               'Konu kayıtları okunamadı; ölçüm yokmuş gibi sonuç çıkarılmadı.',
                               tuple(ctx.unavailable_sources), 'btnOgrenme')
        from services.coach_assistant_v1.shared_rules_v260 import scoped_topics
        scoped = scoped_topics(ctx.topics, lesson_scope)
        completed = sorted((t for t in scoped if t.done > 0),
                           key=lambda t: (t.accuracy is None, t.accuracy if t.accuracy is not None else 101,
                                          -t.done, fold(t.name)))
        stale = None
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='adaptive_observation_v25'").fetchone():
            return CoachAnswer('Bağımsız ölçüm kaynağı okunamıyor',
                               'Ödev kayıtları var ancak bağımsız değerlendirme tablosu bulunmadı. '
                               'Öğrenme düzeyini sıfır kabul etmiyorum.',
                               ('Kaynak: yerel SQLite',), 'btnOgrenme')
        for t in completed[:8]:
            status, current_score, count = _recent_verification(
                con, ctx.student_id, lesson=t.lesson, topic=t.name)
            if status == 'oversize':
                return CoachAnswer('Ödev–ölçüm analizi veri sınırına ulaştı',
                                   'Çok fazla ölçüm kaydı var; kısmi veriden sonuç üretilmedi.',
                                   ('Kaynak: yerel bağımsız konu ölçümleri',), 'btnOgrenme')
            if status == 'available' and current_score < 55:
                return CoachAnswer('Ödev–ölçüm ayrışması: kontrol önerisi',
                                   f'{t.lesson} / {t.name}: {t.done} tamamlanmış çalışma kaydı var; '
                                   f'son 28 gündeki bağımsız ölçümlerde %{current_score:g} doğruluk '
                                   f'({count} yanıt) görünüyor. Ödev bitmesi öğrenmeyi kanıtlamaz. '
                                   'Önce hata türlerini inceleyip eşdeğer güçlükte kısa yoklamayla doğrulayın.',
                                   (f'Konu: {t.lesson} / {t.name}',
                                    f'Tamamlanan çalışma: {t.done} (ödev kontrolü)',
                                    f'Son 28 gündeki bağımsız ölçüm: {count} yanıt, %{current_score:g} doğruluk',
                                    'Neden-sonuç veya kalıcı eksiklik tanısı değildir'), 'btnOgrenme')
            if status == 'insufficient' and stale is None:
                stale = t
        if stale:
            label = ('geçmiş ölçümü olsa da yeterli güncel kanıt bulunmuyor'
                     if stale.observations else 'bağımsız konu ölçümü kaydedilmemiş')
            return CoachAnswer('Ödev tamamlandı; güncel öğrenme kanıtı yetersiz',
                               f'{stale.lesson} / {stale.name}: {stale.done} tamamlanmış çalışma var; '
                               f'{label}. Yeni ödev vermeden önce kısa yoklamayla öğrenmeyi doğrulayın.',
                               (f'Konu: {stale.lesson} / {stale.name}',
                                'Ödev işareti öğrenme ölçümü değildir'), 'btnOgrenme')
        return CoachAnswer('Ödev–ölçüm ayrışması doğrulanamadı',
                           'Seçili derste mevcut kayıtlar belirgin bir ödev–ölçüm ayrışması göstermiyor. '
                           'Bu, konuların öğrenildiğinin kanıtı değildir; sonraki bağımsız ölçümleri izleyin.',
                           (f'Ders: {lesson_scope}', 'Kaynak: seçili öğrencinin yerel kayıtları'), 'btnOgrenme')
    trend_keywords = ('gelisim', 'ilerleme', 'gerile', 'dusus',
                      'onceye gore', 'zamanla', 'zaman icinde', 'gecen aya gore', 'son aylarda')
    explicit = any(k in q for k in trend_keywords)
    priority = any(k in q or k in anchor for k in ('oncelik', 'akademik ihtiyac', 'ilk hangi'))
    if not explicit and not priority:
        return answer
    if answer.title in ('Ders kapsamı uyuşmuyor', 'Ders adı belirsiz'):
        return answer
    if not lesson_key(lesson_scope):
        if explicit:
            return CoachAnswer('Gelişim karşılaştırması için ders seçin',
                               'Öğrencinin zaman içindeki değişimini incelemek için önce ders sekmesini seçin.',
                               ('Kaynak: yerel bağımsız konu ölçümleri',), 'btnOgrenme')
        return answer
    if 'Konu kayıtları okunamadı' in ctx.unavailable_sources:
        if explicit:
            return CoachAnswer('Gelişim analizi şu anda yapılamıyor',
                               'Konu ölçümleri okunamadı; veri yokmuş gibi değerlendirme yapılmadı.',
                               tuple(ctx.unavailable_sources), 'btnOgrenme')
        return answer
    topics = scoped_topics(ctx.topics, lesson_scope)
    # Teachers may name a topic directly. Do not substitute an unrelated topic.
    explicit_topic = [t for t in topics if fold(t.name) and fold(t.name) in q]
    if explicit_topic:
        candidates = sorted(explicit_topic, key=lambda t: (-len(fold(t.name)), fold(t.name)))[:1]
    else:
        measured = [t for t in topics if t.attempts >= MIN_ANSWERS_PER_WINDOW]
        candidates = sorted(measured, key=lambda t: (t.accuracy is None,
                             t.accuracy if t.accuracy is not None else 101,
                             -t.attempts, fold(t.name)))[:(4 if explicit else 1)]
    if not candidates:
        if explicit:
            return CoachAnswer('Gelişim eğilimi için ölçüm gerekli',
                               'Bu derste zaman karşılaştırmasına uygun konu ölçümü bulunmuyor. '
                               'Farklı günlerde bağımsız kısa yoklamalarla başlayın.',
                               ('Ödev tamamlama öğrenme ölçümü değildir.',), 'btnOgrenme')
        return answer
    first_failure = None
    for candidate in candidates:
        trend = analyze_topic(con, ctx.student_id, lesson=candidate.lesson,
                              topic=candidate.name)
        if not trend.available:
            if first_failure is None:
                first_failure = trend
            continue
        if not explicit and trend.direction == 'flat':
            return answer
        if explicit:
            advice = ('Düşüşü yeni ve karşılaştırılabilir kısa yoklamayla doğrulayın; '
                      'nedenini ölçüm olmadan kesinleştirmeyin.' if trend.direction == 'fall'
                      else 'Farklı günlerde gecikmeli yoklamayla kalıcılığı kontrol edin.'
                      if trend.direction == 'rise'
                      else 'Yeni dönemlerde eşdeğer güçlükte kısa yoklamalarla izleyin.')
            return CoachAnswer('Konu gelişimi: temkinli zaman karşılaştırması',
                               trend.short_message() + ' ' + advice,
                               trend.evidence(), 'btnOgrenme')
        if trend.direction == 'fall':
            text = ('Gelişim sinyali: Aynı konunun iki ayrı döneminde doğruluk '
                    f'%{trend.earlier_accuracy:g} → %{trend.recent_accuracy:g} görünüyor. '
                    'Önce benzer güçlükte kısa yoklamayla düşüşü doğrulayın.')
        else:
            text = ('Gelişim sinyali: Aynı konunun iki ayrı döneminde doğruluk '
                    f'%{trend.earlier_accuracy:g} → %{trend.recent_accuracy:g} görünüyor. '
                    'Kalıcı öğrenmeyi başka bir gün yeniden ölçün.')
        return replace(answer, message=answer.message + '\n' + text,
                       evidence=answer.evidence + trend.evidence())
    if explicit:
        # Neither a stale nor a missing assessment source is "0% learning".
        topic = candidates[0]
        return CoachAnswer('Gelişim eğilimi için güvenilir veri yetersiz',
                           f'{topic.lesson} / {topic.name}: '
                           f'{first_failure.reason if first_failure else "Ölçüm bulunamadı."} '
                           'Ödev tamamlanma işaretleri öğrenme göstergesi sayılmaz.',
                           (f'Konu: {topic.lesson} / {topic.name}',), 'btnOgrenme')
    return answer
