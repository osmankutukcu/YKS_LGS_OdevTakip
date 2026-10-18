# -*- coding: utf-8 -*-
"""Unit tests for the modular Coach Assistant (services.coach_assistant_v1 & UI overlay)."""
from __future__ import annotations

from services.coach_assistant_v1 import (
    AssistantInsight,
    build_student_curiosity_insight,
    build_topic_curiosity_insight,
)


def test_student_curiosity_insight_unverified_completed_homeworks():
    insight = build_student_curiosity_insight(
        student_id=128,
        student_name="ALİ VELİ",
        open_hw=5,
        completed_hw=40,
        overdue_hw=1,
        measured_count=0,
        coach_priority="LGS_TURKCE › Sözcükte Anlam",
        coach_next_step="5 soruluk mini kazanım yoklaması",
        topics=[{"lesson": "LGS_TURKCE", "topic": "Sözcükte Anlam", "done_count": 3, "observations": 0}],
    )
    assert isinstance(insight, AssistantInsight)
    assert "Koç Asistanı" in insight.title
    assert insight.target_key == "btnOgrenme"
    assert insight.pointer_caption is not None
    assert "40" in insight.curiosity_hook


def test_student_curiosity_insight_low_accuracy_topic():
    insight = build_student_curiosity_insight(
        student_id=7,
        student_name="AYŞE YILMAZ",
        open_hw=2,
        completed_hw=15,
        overdue_hw=0,
        measured_count=4,
        topics=[{"lesson": "TYT_MATEMATIK", "topic": "Problemler", "done_count": 2, "observations": 2, "accuracy": 40}],
    )
    assert insight.target_key == "btnOgrenme"
    assert "%40" in insight.curiosity_hook
    assert "Darboğaz" in insight.badge


def test_topic_curiosity_insight_prior_done_without_observation():
    insight = build_topic_curiosity_insight(
        lesson="LGS_MATEMATIK",
        topic_name="Üslü İfadeler",
        meta={"done_count": 2, "observations": 0, "accuracy": None},
        draft_rows=1,
        open_hw_count=2,
    )
    assert insight is not None
    assert insight.target_key == "btnOgrenme"
    assert "Üslü İfadeler" in insight.curiosity_hook
    assert insight.pointer_caption is not None


def test_knowledge_bank_v125_loads_and_searches():
    from services.coach_assistant_v1.knowledge_bank_v125 import KnowledgeBank, DEFAULT_LIBRARY_PATH
    assert DEFAULT_LIBRARY_PATH.exists()
    kb = KnowledgeBank(DEFAULT_LIBRARY_PATH)
    results = kb.search("ebbinghaus")
    assert len(results) >= 1
    assert any("ebbinghaus" in r.title.lower() or "tekrar" in r.title.lower() for r in results)


def test_proactive_policy_gate():
    from services.coach_assistant_v1.proactive_policy import ProactiveGate, signal_key, severity
    gate = ProactiveGate()
    key = signal_key("Darboğaz", "Test Hook")
    v1 = gate.decide(student_id=1, key=key, priority=severity("Darboğaz"), mode="balanced", interruptible=True)
    assert v1.show is True
    # Immediate duplicate signal must be throttled
    v2 = gate.decide(student_id=1, key=key, priority=severity("Darboğaz"), mode="balanced", interruptible=True)
    assert v2.show is False


def test_dialogue_answer_grounded():
    from services.coach_assistant_v1.dialogue import CoachContext, CoachTopic, answer_question
    ctx = CoachContext(
        student_id=1,
        student_name="Test Öğrenci",
        open_homework=3,
        completed_homework=12,
        overdue_homework=1,
        measured_count=2,
        topics=(CoachTopic(lesson="Matematik", name="Fonksiyonlar", done=2, observations=0, attempts=0, accuracy=None),),
    )
    ans = answer_question(ctx, "Bu öğrencinin genel durumu nasıl?")
    assert ans is not None
    assert ans.title and ans.message
    assert any("tamamlanmış" in e for e in ans.evidence)
    assert ans.action_target == "btnOgrenme"




