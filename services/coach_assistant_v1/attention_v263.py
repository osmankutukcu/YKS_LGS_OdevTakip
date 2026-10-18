# -*- coding: utf-8 -*-
"""V26.3: read-only, conservative priority & semantic deduplication for coach toasts.

This module only decides whether a *pre-existing* insight merits an automatic
interruption. It does not invent student data, perform IO or change homework.
An omitted / untrustworthy measurement must never become a high-priority popup.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from typing import Mapping, Sequence

from .proactive_policy import signal_key
from .shared_rules_v260 import is_low_accuracy, lesson_key, fold


@dataclass(frozen=True)
class AttentionDecision:
    key: str
    priority: int
    auto_eligible: bool
    reason: str
    brief_hook: str | None = None
    brief_body: str | None = None


def _recent_day(value: object, today: date) -> bool:
    if isinstance(value, datetime):
        day = value.date()
    elif isinstance(value, date):
        day = value
    elif isinstance(value, str):
        try:
            day = date.fromisoformat(value[:10])
        except ValueError:
            return False
    else:
        return False
    return 0 <= (today - day).days <= 35


def _safe_int(v, default: int = 0) -> int:
    try:
        return max(0, int(v))
    except (ValueError, TypeError, OverflowError):
        return default


def _recent_low_evidence(topic: Mapping, today: date) -> bool:
    """Require >=8 answered items over >=2 recent independent check days."""
    evidence = topic.get('evidence') or ()
    valid = [e for e in evidence if isinstance(e, Mapping)
             and _recent_day(e.get('observed_on'), today)]
    days = {str(e.get('observed_on'))[:10] for e in valid}
    count = sum(_safe_int(e.get('correct')) + _safe_int(e.get('wrong')) + _safe_int(e.get('blank')) for e in valid)
    right = sum(_safe_int(e.get('correct')) for e in valid)
    return len(days) >= 2 and count >= 8 and (100.0 * right / count) < 55.0


def attention_decision(
    insight,
    *,
    source: str = 'student',
    topics: Sequence[Mapping] = (),
    overdue_hw: int = 0,
    open_hw: int = 0,
    completed_hw: int = 0,
    lesson: str = '',
    topic_name: str = '',
    today: date | None = None,
) -> AttentionDecision:
    """Assign an evidence-aware priority, not a diagnosis or student ranking.

    Priorities: 1 = inbox only; 2 = actionable; 3 = reliably measured concern.
    The selected student is scoped by ProactiveGate separately; key contains no
    student ID/name. For UI checkbox events notifications are always inbox-only.
    """
    today = today or date.today()
    source = str(source or 'other').casefold()
    badge = fold(getattr(insight, 'badge', ''))
    target = str(getattr(insight, 'target_key', '') or '')

    # Teacher is literally interacting with the homework matrix. Never overlay
    # their workflow; they can inspect the result from the existing menu.
    if source == 'checkbox':
        lesson = lesson or str(getattr(insight, 'lesson', '') or '')
        topic = topic_name or str(getattr(insight, 'topic', '') or '')
        # Legacy topic insights don't have typed course fields. Fall back to a
        # hashed text token for inbox dedupe, not to an interruption.
        key = signal_key('checkbox:' + lesson_key(lesson), topic or str(getattr(insight, 'curiosity_hook', '')))
        return AttentionDecision(key, 1, False, 'checkbox_no_interrupt')

    if source == 'student':
        if 'veri dogrulama' in badge:
            return AttentionDecision(signal_key('student', 'data_unavailable'), 1, False, 'source_unavailable')

        if 'darbogaz' in badge:
            weak = [t for t in topics if is_low_accuracy(t.get('accuracy'))]
            if weak:
                # Match the exact topic selected by the existing presenter.
                selected = min(weak, key=lambda t: float(t.get('accuracy')))
                lesson = lesson_key(str(selected.get('lesson') or ''))
                topic = lesson_key(str(selected.get('topic') or ''))
                key = signal_key('student:low_accuracy:' + lesson, topic)
                sufficient = _recent_low_evidence(selected, today)
                if sufficient:
                    evs = [e for e in selected.get('evidence', ()) if isinstance(e, Mapping)
                           and _recent_day(e.get('observed_on'), today)]
                    right = sum(_safe_int(e.get('correct')) for e in evs)
                    count = sum(_safe_int(e.get('correct')) + _safe_int(e.get('wrong'))
                                + _safe_int(e.get('blank')) for e in evs)
                    measured_pct = int(round(100.0 * right / count))
                    label = escape(str(selected.get('lesson') or 'Ders')) + ' › ' + escape(str(selected.get('topic') or 'Konu'))
                    return AttentionDecision(
                        key, 3, True, 'recent_measured_gap',
                        brief_hook=f'🎯 {label}: güncel ölçümlerde düşük doğruluk (%{measured_pct}).',
                        brief_body=(f'Son 35 günde {len(set(str(e.get("observed_on"))[:10] for e in evs))} ayrı günde '
                                    f'{count} yanıt incelendi. <b>Öneri:</b> Eşdeğer güçlükte kısa bir yoklamayla doğrulayın; '
                                    'tek başına kalıcı öğrenme kaybı anlamına gelmez.'),
                    )
                return AttentionDecision(key, 1, False, 'limited_or_old_measurement')
            return AttentionDecision(signal_key('student', 'low_accuracy_unknown'), 1, False, 'no_topic_evidence')

        if 'yuk istatistigi' in badge:
            priority = 3 if overdue_hw >= 4 and open_hw >= 8 else (2 if overdue_hw >= 1 and open_hw >= 8 else 1)
            return AttentionDecision(
                signal_key('student', 'workload'), priority, priority >= 2,
                'overdue_workload' if priority >= 2 else 'workload_nonurgent',
                brief_hook=f'📌 {overdue_hw} gecikmiş, {open_hw} açık ödev mevcut.' if priority >= 2 else None,
                brief_body='<b>Öneri:</b> Yeni ödev yüklemeden önce geciken işlerin ders dağılımını inceleyin.' if priority >= 2 else None,
            )

        if 'fark ettiniz mi' in badge:
            # Completion shows effort, not learning. Missing a *separate* check
            # warrants a cautious suggestion, not a failure diagnosis.
            priority = 2 if completed_hw >= 3 else 1
            return AttentionDecision(
                signal_key('student', 'unmeasured_learning'), priority, priority >= 2,
                'verification_gap',
                brief_hook=f'🔍 {completed_hw} tamamlanan ödev için bağımsız kazanım ölçümü bulunamadı.' if priority >= 2 else None,
                brief_body='<b>Öneri:</b> Seçilecek bir konuda kısa kazanım yoklaması planlayın. Ölçüm yokluğu, başarısızlık anlamına gelmez.' if priority >= 2 else None,
            )

        return AttentionDecision(signal_key('student', 'general_summary'), 1, False, 'summary_inbox_only')

    # Other feature integrations keep their legacy gate; ensure no automatic
    # escalation of unspecified notices to critical solely from badge wording.
    key = signal_key(source + ':' + badge, target or getattr(insight, 'curiosity_hook', ''))
    return AttentionDecision(key, 2, True, 'external_module')
