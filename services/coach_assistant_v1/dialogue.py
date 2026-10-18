# -*- coding: utf-8 -*-
"""Read-only, evidence-based Turkish teacher dialogue for the existing Coach Assistant.

This is NOT an LLM or a remote web service. It never writes homework or student records.
Remote educational research can be added later via a separately authenticated,
consent-aware connector; student data must not be sent to public search endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
        try:
            coach = read_coach_glance(con, student_id)
        except (sqlite3.Error, ValueError, KeyError):
            coach = None
        try:
            topics = engine.student_topics(con, student_id)
        except (sqlite3.Error, ValueError, KeyError):
            topics = []
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
    )


def _search_fold(value: str) -> str:
    # Turkish İ / I / ı and accented letters must match keyboard query variants.
    source = unicodedata.normalize("NFKD", str(value).casefold().replace("ı", "i"))
    return "".join(ch for ch in source if unicodedata.category(ch) != "Mn")


def answer_question(ctx: CoachContext, question: str) -> CoachAnswer:
    """Bounded factual answers; avoids clinical labels, hallucinated metrics and writes."""
    if type(ctx.student_id) is not int or ctx.student_id <= 0:
        raise ValueError("Geçersiz öğrenci kapsamı")
    q = _search_fold(str(question or "").strip()[:600])
    def _has(*terms: str) -> bool:
        return any(_search_fold(term) in q for term in terms)
    if not q:
        return CoachAnswer("Ne öğrenmek istersiniz?", "Örneğin 'Bu öğrencinin gizli öğrenme açığı ne?' diye sorabilirsiniz.", ())

    measured = [t for t in ctx.topics if t.attempts >= 5 and t.accuracy is not None]
    struggling = sorted((t for t in measured if t.accuracy < 60), key=lambda t: (t.accuracy, -t.attempts))
    no_evidence = [t for t in ctx.topics if t.done > 0 and t.observations == 0]
    coverage = (f"Kontrol: {ctx.completed_homework} tamamlanmış, {ctx.open_homework} açık kayıt",
                f"Kazanım kaydı: {ctx.measured_count}; yeterli örnekli konu: {len(measured)}")
    if _has("internet", "online", "kaynak", "güncel bilgi", "meb", "ösym"):
        return CoachAnswer(
            "Güncel kaynak doğrulaması gerekli",
            "Bu pilot öğrenci verisini internete göndermiyor ve çevrim içi kaynak taraması yapmıyor. "
            "MEB/OGM/ÖSYM kaynakları, ayrı bir güvenli bağlantı ve kaynak-tarih doğrulaması kurulduğunda gösterilebilir. "
            "Şu anda yeni kaynak bulunduğunu iddia edemem.",
            ("Kaynak: yalnızca yerel SQLite kayıtları",), None,
        )
    if _has("neden", "kanıt", "dayanak", "dayan", "hangi veri", "neye göre", "güven", "nasıl bildin"):
        if ctx.priority:
            return CoachAnswer(
                "Önerinin dayanağı",
                f"Mevcut Adaptif Koç önceliği: {ctx.priority}. Önerilen sonraki adım: {ctx.next_step or 'Öğretmen değerlendirmesi gerekli.'} "
                "Bu bir otomatik teşhis değildir.",
                (f"Adaptif Koç dayanağı: {ctx.basis or 'Ayrıntılı kaynak belirtilmemiş'}",
                 f"Ölçüm referans tarihi: {ctx.as_of or 'Belirtilmemiş'}", *coverage),
                "btnOgrenme",
            )
        return CoachAnswer("Dayanak yeterli değil", "Koçluk önceliği için doğrulanmış ayrıntılı veri bulunamadı. Önce Öğrenme ekranını kontrol edin.", coverage, "btnOgrenme")
    if _has("hafta", "program", "plan", "nasıl çalış"):
        priority = ctx.next_step or ("Önce bağımsız öğrenme ölçümü planlayın." if no_evidence else "Güncel deneme ve konu sonuçlarını karşılaştırın.")
        return CoachAnswer(
            "Onay bekleyen plan fikri",
            f"{priority} Mevcut {ctx.open_homework} açık ödevi hesaba katıp yeni görevleri aşırı yük oluşturmayacak şekilde planlayın. "
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
        msg += ("Tamamlanan ödevleri doğrulayan bağımsız kazanım kaydı henüz yok." if ctx.measured_count == 0 else
                f"Ayrıca {ctx.measured_count} kazanım kanıtı var; ödev bitmesi öğrenme kanıtı sayılmaz.")
        return CoachAnswer("Ödev–öğrenme karşılaştırması", msg, coverage, "btnKontrol")
    # Most valuable *invisible* insight: disagreement between completion and evidence.
    if ctx.completed_homework > 0 and ctx.measured_count == 0:
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
        ctx.next_step or "Mevcut ölçümleri ve öğrencinin çalışma planını karşılaştırın. Kayıtlar tek başına kesin öğrenci sınıflandırması sağlamaz.",
        (f"Adaptif Koç önceliği: {ctx.priority or 'Belirlenemedi'}", *coverage), "btnOgrenme",
    )
