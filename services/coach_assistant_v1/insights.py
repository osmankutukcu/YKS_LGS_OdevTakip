# -*- coding: utf-8 -*-
"""Curiosity-driven, non-bossy insight generator for Coach Assistant (V1).

Instead of imperative commands ("Do this, check that"), this module extracts
original, intriguing patterns from the student's actual records so the teacher
naturally becomes curious about exploring Adaptive Coaching, Student 360°, or
Homework Control.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape as _html_escape

from ui.adaptive_coaching_center_v26 import format_lesson_name, format_action_title


@dataclass(frozen=True)
class AssistantInsight:
    """Immutable descriptor for a single Coach Assistant toast + transparent arrow."""

    title: str
    badge: str
    curiosity_hook: str
    body_html: str
    action_text: str | None = None
    target_key: str | None = None  # "btnOgrenme" | "btnKontrol" | "toggle_360"
    pointer_caption: str | None = None
    border_color: str = "#38bdf8"
    duration_ms: int = 7500


def build_student_curiosity_insight(
    *,
    student_id: int,
    student_name: str,
    open_hw: int,
    completed_hw: int,
    overdue_hw: int,
    measured_count: int,
    coach_priority: str | None = None,
    coach_next_step: str | None = None,
    topics: list[dict] | None = None,
) -> AssistantInsight:
    """Create a curiosity-driven insight when a student is selected."""
    topics = topics or []

    # Find interesting original stats from topic records
    unverified_done_topics = [
        t for t in topics
        if int(t.get("done_count") or 0) > 0 and int(t.get("observations") or 0) == 0
    ]
    low_acc_topics = [
        t for t in topics
        if t.get("accuracy") is not None and int(t.get("accuracy") or 100) < 55
    ]

    pretty_prio = ""
    if coach_priority:
        l_badge, t_title = format_action_title(coach_priority)
        pretty_prio = f"{l_badge} › {t_title}" if l_badge else t_title

    # Case 1: Student has completed many homeworks, but 0 independent learning measurements
    if completed_hw > 0 and measured_count == 0:
        sample_topic_str = ""
        if unverified_done_topics:
            t0 = unverified_done_topics[0]
            l_name = format_lesson_name(str(t0.get("lesson") or ""))
            t_name = str(t0.get("topic") or "")
            sample_topic_str = f" (ör. <b>{_html_escape(l_name)} › {_html_escape(t_name)}</b>)"

        curiosity_hook = (
            f"🔍 İlginç Bir Detay: {completed_hw} ödev tamamlanmış ama kazanım kalıcılığı henüz sürpriz kutu!"
        )
        lines = [
            f"<b>{_html_escape(student_name)}</b> şimdiye kadar <span style='color:#fde047;font-weight:800;'>{completed_hw} ödevi bitirmiş</span> "
            f"görünüyor{sample_topic_str}; ancak bu konuların ne kadarının kalıcı öğrenmeye dönüştüğüne dair <b>henüz bağımsız bir iz yok</b>.",
        ]
        if pretty_prio:
            lines.append(
                f"✨ <b>Adaptif Koç'un Keşfi:</b> Okun işaret ettiği <b>🧠 Öğrenme</b> ekranında "
                f"<span style='color:#7dd3fc;font-weight:700;'>{_html_escape(pretty_prio)}</span> için hazır 5 soruluk mini kazanım analizi sizi bekliyor."
            )
        else:
            lines.append(
                "✨ <b>Merak Edenler İçin:</b> Okun gösterdiği <b>🧠 Öğrenme</b> butonunda, biten ödevlerin gerçek kazanım röntgenini görebilirsiniz."
            )
        if open_hw > 0:
            lines.append(
                f"<span style='color:#cbd5e1;font-size:10.5px;'>📌 Ayrıca öğrencinin <b>{open_hw} açık ödevi</b> mevcut (Kontrol ekranında detayları yer alıyor).</span>"
            )

        return AssistantInsight(
            title=f"✨ Koç Asistanı · {student_name} (#{student_id})",
            badge="💡 Fark Ettiniz mi?",
            curiosity_hook=curiosity_hook,
            body_html="<br>".join(lines),
            action_text="🧠 Kazanım Röntgenine Göz At",
            target_key="btnOgrenme",
            pointer_caption=f"✨ Burada: {completed_hw} biten ödevin gerçek öğrenme analizi",
            border_color="#38bdf8",
            duration_ms=7800,
        )

    # Case 2: Low accuracy detected in measured topics
    if low_acc_topics:
        worst = min(low_acc_topics, key=lambda x: int(x.get("accuracy") or 100))
        w_lesson = format_lesson_name(str(worst.get("lesson") or ""))
        w_topic = str(worst.get("topic") or "")
        w_acc = int(worst.get("accuracy") or 0)
        curiosity_hook = (
            f"📊 Şaşırtıcı Veri: Ödevler yapılıyor ama {w_lesson} › {w_topic} doğruluğu %{w_acc} seviyesinde!"
        )
        body = (
            f"Öğrencinin geçmiş kayıtlarında <b>{_html_escape(w_lesson)} › {_html_escape(w_topic)}</b> konusu "
            f"çalışılmış görünse de son yoklama doğruluğu <span style='color:#fda4af;font-weight:800;'>%{w_acc}</span>.<br>"
            f"✨ Okun gösterdiği <b>🧠 Öğrenme</b> ekranında bu konudaki takılma nedenini ve alternatif kaynak önerisini inceleyebilirsiniz."
        )
        return AssistantInsight(
            title=f"✨ Koç Asistanı · {student_name} (#{student_id})",
            badge="🔬 Gizli Darboğaz",
            curiosity_hook=curiosity_hook,
            body_html=body,
            action_text="🧠 Darboğaz Analizini Gör",
            target_key="btnOgrenme",
            pointer_caption=f"✨ Burada: %{w_acc} doğruluklu konunun kök neden analizi",
            border_color="#f43f5e",
            duration_ms=7800,
        )

    # Case 3: High open homework accumulation
    if open_hw >= 8:
        curiosity_hook = (
            f"📦 Dikkat Çekici Birikim: {student_name} için {open_hw} açık ödev birikmiş durumda!"
        )
        body = (
            f"Yeni konu seçmeden önce ilginç bir istatistik: Öğrencinin şu an açıkta bekleyen "
            f"<span style='color:#fcd34d;font-weight:800;'>{open_hw} ödevi</span> (gecikmiş: {overdue_hw}) var.<br>"
            f"✨ Okun işaret ettiği <b>✅ Kontrol</b> veya <b>🧭 Öğrenci 360°</b> alanında hangi derslerde yığılma olduğunu tek bakışta görebilirsiniz."
        )
        return AssistantInsight(
            title=f"✨ Koç Asistanı · {student_name} (#{student_id})",
            badge="📊 Yük İstatistiği",
            curiosity_hook=curiosity_hook,
            body_html=body,
            action_text="✅ Biriken Ödev Dağılımına Bak",
            target_key="btnKontrol",
            pointer_caption=f"✨ Burada: Bekleyen {open_hw} ödevin ders ve kaynak dökümü",
            border_color="#f59e0b",
            duration_ms=7400,
        )

    # Default Case: Balanced / Fresh student profile
    curiosity_hook = (
        f"🌟 Profil Özeti: {completed_hw} tamamlanan ödev · {measured_count} doğrulanmış kazanım kaydı"
    )
    extra = (
        f"Adaptif Koç bu öğrenci için sıradaki en verimli odak olarak "
        f"<span style='color:#86efac;font-weight:700;'>{_html_escape(pretty_prio)}</span> konusunu işaret ediyor."
        if pretty_prio
        else "Öğrencinin tüm ödev, anket ve kazanım geçmişi Öğrenci 360° ve Öğrenme panellerinde senkronize durumda."
    )
    return AssistantInsight(
        title=f"✨ Koç Asistanı · {student_name} (#{student_id})",
        badge="🧭 Keşif Notu",
        curiosity_hook=curiosity_hook,
        body_html=extra,
        action_text="🧠 Adaptif Koçluk Görünümü",
        target_key="btnOgrenme",
        pointer_caption="✨ Burada: Öğrencinin kişiselleştirilmiş koçluk haritası",
        border_color="#10b981",
        duration_ms=6800,
    )


def build_topic_curiosity_insight(
    *,
    lesson: str,
    topic_name: str,
    meta: dict | None,
    draft_rows: int,
    open_hw_count: int,
) -> AssistantInsight | None:
    """Create a curiosity-driven whisper when the teacher ticks a topic checkbox."""
    pretty_ders = format_lesson_name(lesson)

    if meta:
        done_n = int(meta.get("done_count") or 0)
        obs_n = int(meta.get("observations") or 0)
        acc = meta.get("accuracy")

        # 1. Previously completed homework on this exact topic, but 0 accuracy observations
        if done_n >= 1 and obs_n == 0:
            return AssistantInsight(
                title=f"✨ Koç Asistanı · {pretty_ders}",
                badge="🔍 İlginç Geçmiş Verisi",
                curiosity_hook=f"Fark ettiniz mi? '{topic_name}' konusu daha önce {done_n} kez tamamlanmış!",
                body_html=(
                    f"Öğrenci <b>{_html_escape(topic_name)}</b> konusundan daha önce <b>{done_n} kaynağı bitirmiş</b> "
                    f"ancak sistemde bu konuyu gerçekten kavradığına dair henüz bir doğruluk kaydı yok.<br>"
                    f"✨ Merak ediyorsanız okun gösterdiği <b>🧠 Öğrenme</b> ekranında bu konunun geçmiş izini ve mini yoklama kartını görebilirsiniz."
                ),
                action_text="🔬 Konunun Geçmiş İzine Bak",
                target_key="btnOgrenme",
                pointer_caption=f"✨ Burada: '{topic_name[:22]}' geçmişi & mini yoklama",
                border_color="#f59e0b",
                duration_ms=6500,
            )

        # 2. Low accuracy on this topic in prior measurements
        if acc is not None and int(acc) < 55:
            acc_i = int(acc)
            return AssistantInsight(
                title=f"✨ Koç Asistanı · {pretty_ders}",
                badge=f"📉 Geçmiş Doğruluk: %{acc_i}",
                curiosity_hook=f"İlginç Veri: '{topic_name}' konusunda önceki doğru oranı %{acc_i} kalmış.",
                body_html=(
                    f"Bu konuda öğrencinin önceki kazanım yoklaması <span style='color:#fda4af;font-weight:800;'>%{acc_i}</span> seviyesinde.<br>"
                    f"✨ Okun gösterdiği <b>🧠 Öğrenme</b> ekranında öğrencinin bu konuda neden zorlandığına dair koçluk ipuçları yer alıyor."
                ),
                action_text="🧠 Zorlanma Nedenini Gör",
                target_key="btnOgrenme",
                pointer_caption=f"✨ Burada: %{acc_i} doğruluk detayı ve telafi önerisi",
                border_color="#e11d48",
                duration_ms=6500,
            )

    # 3. High draft + open workload observation (non-bossy, curiosity-framed)
    if draft_rows >= 4 and open_hw_count >= 10:
        total_pending = open_hw_count + draft_rows
        return AssistantInsight(
            title="✨ Koç Asistanı · Yük Dengesi İstatistiği",
            badge=f"📊 Toplam {total_pending} Kalem",
            curiosity_hook=f"Küçük Bir İstatistik: Mevcut {open_hw_count} açık ödev + {draft_rows} yeni seçim = {total_pending} ödev!",
            body_html=(
                f"Öğrencinin geçmiş verilerine göre eşzamanlı ödev sayısı yükseldiğinde tamamlama hızı düşebiliyor.<br>"
                f"✨ Okun işaret ettiği <b>🧭 Öğrenci 360°</b> panelinden öğrencinin haftalık tamamlama temposuna göz atabilirsiniz."
            ),
            action_text="🧭 Öğrenci Temposuna Bak",
            target_key="toggle_360",
            pointer_caption="✨ Burada: Öğrencinin haftalık tamamlama hızı",
            border_color="#38bdf8",
            duration_ms=6200,
        )

    return None
