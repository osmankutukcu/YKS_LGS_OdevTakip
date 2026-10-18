# -*- coding: utf-8 -*-
"""Read-only, evidence-based Turkish teacher dialogue for the existing Coach Assistant.

This is NOT an LLM or a remote web service. It never writes homework or student records.
Remote educational research can be added later via a separately authenticated,
consent-aware connector; student data must not be sent to public search endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from services.coach_assistant_v1.shared_rules_v260 import (
    lesson_key, scoped_topics, question_lesson, is_low_accuracy,
    MIN_RELIABLE_ATTEMPTS,
)
import sqlite3
import unicodedata


@dataclass(frozen=True)
class CoachTopic:
    lesson: str
    name: str
    done: int = 0
    observations: int = 0
    attempts: int = 0
    accuracy: float | None = None


@dataclass(frozen=True)
class CoachContext:
    student_id: int
    student_name: str
    open_homework: int
    completed_homework: int
    overdue_homework: int
    measured_count: int
    priority: str = ""
    next_step: str = ""
    basis: str = ""
    as_of: str = ""
    topics: tuple[CoachTopic, ...] = field(default_factory=tuple)
    unavailable_sources: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CoachAnswer:
    title: str
    message: str
    evidence: tuple[str, ...]
    action_target: str | None = None


def read_context(con: sqlite3.Connection, student_id: int) -> CoachContext:
    """Use the EXISTING Student360 / Adaptive readers; a single student scope only."""
    if type(student_id) is not int or student_id <= 0:
        raise ValueError("Geçersiz öğrenci kimliği")
    from services.student_workspace_v21 import read_workspace_report
    from services.live_student_summary_v3 import read_coach_glance
    from services.adaptive_coaching_v25 import engine

    prev = con.row_factory
    try:
        con.row_factory = sqlite3.Row
        report = read_workspace_report(con, student_id)
        if report.student.student_id != student_id:
            raise ValueError("Öğrenci kimliği uyuşmazlığı")
        # Coach / topic reader failure must be visible as missing evidence, never invented.
        coach = None
        topics = []
        unavailable = []
        try:
            coach = read_coach_glance(con, student_id)
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            unavailable.append('Koçluk özeti okunamadı')
        try:
            topics = engine.student_topics(con, student_id)
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            unavailable.append('Konu kayıtları okunamadı')
    finally:
        con.row_factory = prev
    prepared = []
    for item in topics[:1000]:
        try:
            raw_accuracy = item.get("accuracy")
            accuracy = None if raw_accuracy is None else max(0.0, min(100.0, float(raw_accuracy)))
            prepared.append(CoachTopic(
                lesson=str(item.get("lesson") or "")[:90],
                name=str(item.get("topic") or "")[:140],
                done=max(0, int(item.get("done_count") or 0)),
                observations=max(0, int(item.get("observations") or 0)),
                attempts=max(0, int(item.get("attempts") or 0)),
                accuracy=accuracy,
            ))
        except (TypeError, ValueError, AttributeError):
            continue
    return CoachContext(
        student_id=student_id,
        student_name=str(report.student.student_name)[:120],
        open_homework=report.control.open,
        completed_homework=report.control.completed,
        overdue_homework=max(0, int(report.student.homework_overdue or 0)),
        measured_count=max(0, int(coach.evidence_count or 0)) if coach else 0,
        priority=str(coach.priority)[:180] if coach else "",
        next_step=str(coach.next_step)[:260] if coach else "",
        basis=str(coach.basis)[:180] if coach else "",
        as_of=str(coach.as_of)[:30] if coach else "",
        topics=tuple(prepared),
        unavailable_sources=tuple(unavailable),
    )


def _search_fold(value: str) -> str:
    # Turkish İ / I / ı and accented letters must match keyboard query variants.
    source = unicodedata.normalize("NFKD", str(value).casefold().replace("ı", "i"))
    return "".join(ch for ch in source if unicodedata.category(ch) != "Mn")


def _academic_priority(ctx: CoachContext, topics, lesson: str, coverage: tuple[str, ...], *,
                       is_scoped: bool, struggling, no_evidence) -> CoachAnswer:
    """A conservative, explainable academic need based only on recorded evidence.

    Priorities follow measured low accuracy > completed work missing verification >
    insufficient response sample > no established priority. Counts outside the
    course are explicitly marked as student-wide. There is NO diagnostic inference.
    """
    course = lesson or 'tüm dersler'
    if 'Konu kayıtları okunamadı' in ctx.unavailable_sources:
        return CoachAnswer('Öncelik henüz güvenle belirlenemiyor',
                           f'{course} konu kayıtları okunamadığı için akademik ihtiyaç sıralayamıyorum. '
                           'Önce veri erişimini doğrulayın; veri yokmuş gibi karar vermeyin.',
                           coverage, 'btnOgrenme')
    if struggling:
        t = struggling[0]
        return CoachAnswer(
            'Öncelikli akademik ihtiyaç: doğrulama ve telafi',
            f'{t.lesson} / {t.name}: kaydedilmiş {t.attempts} yanıtta %{t.accuracy:g} doğruluk var. '
            'Bu nedenle ilk öncelik, hata türlerini öğretmenle incelemek ve başka bir gün '
            'bağımsız kısa yoklamayla sonucu doğrulamaktır. Sonuca göre konu telafisi planlanabilir. '
            'Bu sonuç tek başına kalıcı öğrenme eksikliği kanıtı değildir.',
            (f'Konu: {t.lesson} / {t.name}',
             f'Soru yanıtı: {t.attempts}; kayıtlı ölçüm: {t.observations}; doğruluk: %{t.accuracy:g}',
             f'İşaretleme kuralı: en az {MIN_RELIABLE_ATTEMPTS} yanıt, %{55:g} altı doğruluk',
             *coverage), 'btnOgrenme')
    if no_evidence:
        t = sorted(no_evidence, key=lambda x: (-x.done, x.lesson, x.name))[0]
        return CoachAnswer(
            'Öncelikli akademik ihtiyaç: öğrenmeyi ölçme',
            f'{t.lesson} / {t.name} konusunda {t.done} tamamlanmış çalışma görünmesine rağmen '
            'kayıtlı bağımsız konu ölçümü bulunmuyor. İlk iş kısa, farklı güçlüklerde '
            'sorulardan oluşan öğretmen onaylı yoklamayla öğrenmeyi ölçmek olmalı. '
            'Ödev tamamlamak tek başına konuyu öğrendiğini veya öğrenemediğini göstermez.',
            (f'Konu: {t.lesson} / {t.name}; tamamlanan çalışma: {t.done}; ölçüm: 0',
             *coverage), 'btnOgrenme')
    partial = sorted((t for t in topics if t.attempts > 0 and
                      (t.attempts < MIN_RELIABLE_ATTEMPTS or t.accuracy is None)),
                     key=lambda x: (-x.attempts, x.lesson, x.name))
    if partial:
        t = partial[0]
        return CoachAnswer(
            'Öncelikli akademik ihtiyaç: yeterli örnek toplama',
            f'{t.lesson} / {t.name}: {t.attempts} yanıt kaydı var; bu miktar mevcut '
            f'basit eşik olan {MIN_RELIABLE_ATTEMPTS} yanıtın altında veya doğruluk kaydı eksik. '
            'Farklı günlerden kısa yoklamalarla daha karşılaştırılabilir veri oluşturun.',
            (f'Konu: {t.lesson} / {t.name}; yanıt: {t.attempts}', *coverage), 'btnOgrenme')
    if is_scoped:
        return CoachAnswer(
            'Bu ders için doğrulanmış kritik ihtiyaç yok',
            f'{course} kayıtlarında mevcut ölçüm eşiğine göre açıkça düşük doğruluk '
            'veya tamamlanan ödevde ölçüm boşluğu bulunamadı. Bu, eksik olmadığı anlamına '
            'gelmez. Farklı günlerdeki kazanım sonuçlarını ve öğretmen gözlemlerini karşılaştırın.',
            coverage, 'btnOgrenme')
    if ctx.priority:
        return CoachAnswer('Öğrencinin genel koçluk önceliği',
                           f'Adaptif Koç kaydında öncelik: {ctx.priority}. '
                           f'Önerilen sonraki adım: {ctx.next_step or "Öğretmen değerlendirmesi gerekli."} '
                           'Bu genel öğrenci önerisi, belirli bir dersin ölçülmüş sonucu değildir.',
                           (f'Adaptif Koç dayanağı: {ctx.basis or "Belirtilmemiş"}', *coverage),
                           'btnOgrenme')
    return CoachAnswer('Akademik öncelik için ek kanıt gerekli',
                       'Mevcut öğrenci kayıtları tek bir akademik ihtiyacı güvenilir '
                       'şekilde öne çıkarmıyor. Önce ders ve konu seçerek ölçümleri kontrol edin.',
                       coverage, 'btnOgrenme')


def answer_question(ctx: CoachContext, question: str, *, lesson_scope: str = "") -> CoachAnswer:
    """Bounded factual answers; avoids clinical labels, hallucinated metrics and writes."""
    if type(ctx.student_id) is not int or ctx.student_id <= 0:
        raise ValueError("Geçersiz öğrenci kapsamı")
    q = _search_fold(str(question or "").strip()[:600])
    def _has(*terms: str) -> bool:
        return any(_search_fold(term) in q for term in terms)
    if not q:
        return CoachAnswer("Ne öğrenmek istersiniz?", "Örneğin 'Bu öğrencinin gizli öğrenme açığı ne?' diye sorabilirsiniz.", ())

    # The selected course and a course named in the question must not silently
    # contaminate each other. Homework counters are student-wide, NOT course-wide.
    mentioned, ambiguous = question_lesson(ctx.topics, question)
    selected = lesson_key(lesson_scope)
    if selected and mentioned and mentioned != selected:
        return CoachAnswer('Ders kapsamı uyuşmuyor',
                           'Soru başka bir derse ait görünüyor. Koça Sor içinde "Tüm dersler" kapsamını seçip tekrar sorun.',
                           (f'Seçili ders: {lesson_scope}',), None)
    if not selected and ambiguous:
        return CoachAnswer('Ders adı belirsiz',
                           'Birden fazla düzeyde aynı ders bulundu. TYT, AYT veya LGS düzeyini belirterek tekrar sorun.',
                           ('Kaynak: seçili öğrencinin kayıtlı ders adları',), None)
    effective = selected or mentioned or ''
    is_scoped = bool(effective)
    topics = scoped_topics(ctx.topics, effective) if is_scoped else ctx.topics
    # Coach priority and next-step are general; never claim they are scoped.
    priority = ctx.priority if not is_scoped else ''
    next_step = ctx.next_step if not is_scoped else ''
    basis = ctx.basis if not is_scoped else ''
    measured = [t for t in topics if t.attempts >= MIN_RELIABLE_ATTEMPTS and t.accuracy is not None]
    struggling = sorted((t for t in measured if is_low_accuracy(t.accuracy, attempts=t.attempts, reliable_only=True)),
                        key=lambda t: (t.accuracy, -t.attempts, t.lesson, t.name))
    no_evidence = [t for t in topics if t.done > 0 and t.observations == 0]
    coverage = (f"Öğrenci geneli: {ctx.completed_homework} tamamlanmış, {ctx.open_homework} açık ödev",
                (f"Öğrenci genelinde kazanım kanıtı: {ctx.measured_count}"
                 if "Koçluk özeti okunamadı" not in ctx.unavailable_sources
                 else "Öğrenci genelinde kazanım kanıtı: okunamadı"),
                f"{('Seçili derste' if selected else 'Sorulan derste') if is_scoped else 'Tüm derslerde'} "
                f"yeterli örnekli konu: {len(measured)}")
    if is_scoped:
        coverage += (f'Ders filtresi: {lesson_scope if selected else effective}; genel ödev sayıları bu filtreye ait değildir',)
    if ctx.unavailable_sources:
        coverage += tuple('Veri eksikliği: ' + x for x in ctx.unavailable_sources)
    if is_scoped and not topics and 'Konu kayıtları okunamadı' not in ctx.unavailable_sources:
        return CoachAnswer('Seçili ders için yeterli kayıt bulunamadı',
                           'Bu derse ait konu kanıtı bulunamadı veya henüz okunamadı. Bu durum başarı veya başarısızlık göstermez.',
                           coverage, 'btnOgrenme')
    # Explicit academic-priority intent must precede the generic evidence and
    # keyword branches. Only scoped topic observations support a course priority.
    if _has('öncelik', 'oncelik', 'akademik ihtiyaç', 'akademik ihtiyac', 'ilk neye odaklan',
            'ilk hangi', 'en önemli ihtiyaç', 'en onemli ihtiyac', 'en önemli sorun',
            'en onemli sorun', 'ilk adım ne', 'ilk adim ne'):
        return _academic_priority(ctx, topics, lesson_scope if selected else effective, coverage,
                                  is_scoped=is_scoped, struggling=struggling,
                                  no_evidence=no_evidence)
    if _has("internet", "online", "kaynak", "güncel bilgi", "meb", "ösym"):
        return CoachAnswer(
            "Güncel kaynak doğrulaması gerekli",
            "Bu pilot öğrenci verisini internete göndermiyor ve çevrim içi kaynak taraması yapmıyor. "
            "MEB/OGM/ÖSYM kaynakları, ayrı bir güvenli bağlantı ve kaynak-tarih doğrulaması kurulduğunda gösterilebilir. "
            "Şu anda yeni kaynak bulunduğunu iddia edemem.",
            ("Kaynak: yalnızca yerel SQLite kayıtları",), None,
        )
    if _has('ödev', 'odev') and _has('öğrenme', 'ogrenme', 'kanıt', 'kanit', 'tutarlı', 'tutarli'):
        msg = (f"Öğrenci genelinde {ctx.completed_homework} tamamlanmış ve {ctx.open_homework} açık ödev var. "
               + ("Koçluk özeti okunamadı; kanıt sayısı bilinmiyor. " if 'Koçluk özeti okunamadı' in ctx.unavailable_sources else
                  "Henüz bağımsız kazanım kanıtı kaydı yok. " if ctx.measured_count == 0 else
                  f"Kayıtlarda {ctx.measured_count} kazanım kanıtı var. ")
               + "Ödev tamamlanması tek başına öğrenmeyi doğrulamaz.")
        return CoachAnswer('Ödev–öğrenme karşılaştırması', msg, coverage, 'btnKontrol')
    if _has("neden", "kanıt", "dayanak", "dayan", "hangi veri", "neye göre", "güven", "nasıl bildin"):
        if priority:
            return CoachAnswer(
                "Önerinin dayanağı",
                f"Mevcut Adaptif Koç önceliği: {priority}. Önerilen sonraki adım: {next_step or 'Öğretmen değerlendirmesi gerekli.'} "
                "Bu bir otomatik teşhis değildir.",
                (f"Adaptif Koç dayanağı: {basis or 'Ayrıntılı kaynak belirtilmemiş'}",
                 f"Ölçüm referans tarihi: {ctx.as_of or 'Belirtilmemiş'}", *coverage),
                "btnOgrenme",
            )
        return CoachAnswer("Dayanak yeterli değil", "Koçluk önceliği için doğrulanmış ayrıntılı veri bulunamadı. Önce Öğrenme ekranını kontrol edin.", coverage, "btnOgrenme")
    if _has("hafta", "program", "plan", "nasıl çalış"):
        priority_text = next_step or ("Önce bağımsız öğrenme ölçümü planlayın." if no_evidence else "Güncel deneme ve konu sonuçlarını karşılaştırın.")
        return CoachAnswer(
            "Onay bekleyen plan fikri",
            f"{priority_text} Öğrencinin genelinde {ctx.open_homework} açık ödevi hesaba katıp yeni görevleri aşırı yük oluşturmayacak şekilde planlayın. "
            "Bu bir taslaktır; ödev veya program kaydı yapılmadı.",
            coverage, "btnOgrenme",
        )
    if _has("konu", "zayıf", "zorlan", "doğruluk", "yanlış", "darboğaz"):
        if struggling:
            topic = struggling[0]
            return CoachAnswer(
                "Ölçümlerde dikkat çeken konu",
                f"{topic.lesson} / {topic.name}: mevcut kayıtlarda %{topic.accuracy:g} doğru ({topic.attempts} cevap). "
                "Soru güçlükleri ve uygulama koşulları bilinmeden kesin öğrenme düzeyi çıkarılamaz.",
                (f"Kaynak: {topic.observations} bağımsız konu ölçümü", *coverage), "btnOgrenme",
            )
        if no_evidence:
            topic = no_evidence[0]
            return CoachAnswer(
                "Ölçüm boşluğu",
                f"{topic.lesson} / {topic.name} konusunda {topic.done} tamamlanmış çalışma kaydı var, "
                "fakat bağımsız konu ölçümü yok. Önce kısa bir yoklama önerilir.",
                coverage, "btnOgrenme",
            )
        return CoachAnswer("Konu için ek veri gerekli", "Güvenilir düşük doğruluk kanıtı bulunamadı; bu, tüm konuların öğrenildiği anlamına gelmez.", coverage, "btnOgrenme")
    if _has("ödev", "biten", "tamam", "bekleyen", "gecik"):
        msg = (f"Kontrol kayıtlarında {ctx.completed_homework} tamamlanmış ve {ctx.open_homework} açık ödev var. "
               f"Öğrenci 360°'nin teslim tarihi değerlendirmesinde {ctx.overdue_homework} gecikmiş kayıt bulunuyor. ")
        msg += ("Koçluk özeti okunamadığı için bağımsız kanıt durumu bilinmiyor." if "Koçluk özeti okunamadı" in ctx.unavailable_sources else "Tamamlanan ödevleri doğrulayan bağımsız kazanım kaydı henüz yok." if ctx.measured_count == 0 else
                f"Ayrıca {ctx.measured_count} kazanım kanıtı var; ödev bitmesi öğrenme kanıtı sayılmaz.")
        return CoachAnswer("Ödev–öğrenme karşılaştırması", msg, coverage, "btnKontrol")
    # Most valuable *invisible* insight: disagreement between completion and evidence.
    if ctx.completed_homework > 0 and ctx.measured_count == 0 and not ctx.unavailable_sources:
        return CoachAnswer(
            "Gizli takip ihtiyacı: kanıt boşluğu",
            f"{ctx.completed_homework} tamamlanmış ödev bulunuyor, ancak kayıtlı bağımsız öğrenme ölçümü yok. "
            "Bu nedenle ödev bitirme oranına dayanarak öğrenme başarısı sonucu çıkaramam. "
            "Önce önemli bir konudan kısa yoklama yapmayı değerlendirin.",
            coverage, "btnOgrenme",
        )
    if struggling:
        t = struggling[0]
        return CoachAnswer(
            "Gizli takip ihtiyacı: ölçüm uyuşmazlığı",
            f"{t.lesson} / {t.name} konusundaki %{t.accuracy:g} doğruluk, yeni ödev vermeden önce gözden geçirilmeyi hak ediyor. "
            "Farklı güçlükte bir doğrulama yoklaması yapılabilir.",
            (f"Ölçüm sayısı: {t.observations}; toplam cevap: {t.attempts}", *coverage), "btnOgrenme",
        )
    if ctx.open_homework >= 8:
        return CoachAnswer("İş yükü birikimi", f"{ctx.open_homework} açık ödev var. Sonraki görevleri eklemeden mevcut iş yükünü öğretmenle değerlendirin.", coverage, "btnKontrol")
    return CoachAnswer(
        "İncelenecek ilk adım",
        next_step or "Mevcut ölçümleri ve öğrencinin çalışma planını karşılaştırın. Kayıtlar tek başına kesin öğrenci sınıflandırması sağlamaz.",
        (f"Adaptif Koç önceliği: {priority or 'Seçili ders için doğrulanmadı'}", *coverage), "btnOgrenme",
    )
