# -*- coding: utf-8 -*-
"""V26.3 evidence-aware attention policy (no Qt or student database needed)."""
from datetime import date, timedelta
from pathlib import Path
import ast
from types import SimpleNamespace

from services.coach_assistant_v1.attention_v263 import attention_decision
from services.coach_assistant_v1.proactive_policy import ProactiveGate

TODAY = date(2026, 10, 18)


def insight(badge='🔬 Gizli Darboğaz', hook='Öğrenci başarı %40', target='btnOgrenme'):
    return SimpleNamespace(badge=badge, curiosity_hook=hook, target_key=target)


def topic(*, course='LGS Türkçe', name='Fiilimsiler', pct=40, day=None, days=2, correct=4, wrong=6):
    day = day or TODAY
    evs = []
    for i in range(days):
        evs.append({'observed_on': (day - timedelta(days=i * 7)).isoformat(),
                    'correct': correct, 'wrong': wrong, 'blank': 0})
    return {'lesson': course, 'topic': name, 'accuracy': pct, 'attempts': (correct + wrong) * days,
            'observations': days, 'last_observed_on': day.isoformat(), 'evidence': evs}


def test_recent_independent_evidence_auto_eligible():
    v = attention_decision(insight(), topics=(topic(),), today=TODAY)
    assert v.auto_eligible and v.priority == 3


def test_score_0_with_recent_measurement_is_not_ignored():
    v = attention_decision(insight(hook='Öğrenci %0'), topics=(topic(pct=0, correct=0, wrong=10),), today=TODAY)
    assert v.priority == 3


def test_one_day_measurement_stays_inbox():
    v = attention_decision(insight(), topics=(topic(days=1),), today=TODAY)
    assert not v.auto_eligible and v.priority == 1


def test_stale_measurement_stays_inbox():
    v = attention_decision(insight(), topics=(topic(day=TODAY - timedelta(days=65)),), today=TODAY)
    assert not v.auto_eligible and v.reason == 'limited_or_old_measurement'


def test_no_dated_itemized_evidence_stays_inbox():
    t = topic()
    t.pop('evidence')
    assert not attention_decision(insight(), topics=(t,), today=TODAY).auto_eligible


def test_aggregate_low_but_recent_results_good_do_not_alarm():
    t = topic(pct=20, correct=9, wrong=1)
    assert not attention_decision(insight(), topics=(t,), today=TODAY).auto_eligible


def test_future_measurement_does_not_count():
    t = topic(day=TODAY + timedelta(days=7))
    assert not attention_decision(insight(), topics=(t,), today=TODAY).auto_eligible


def test_duplicate_key_stable_when_the_counts_change():
    a = attention_decision(insight(hook='Ödev sayısı 8, başarı %40'), topics=(topic(),), today=TODAY)
    b = attention_decision(insight(hook='Ödev sayısı 9, başarı %38'), topics=(topic(pct=38),), today=TODAY)
    assert a.key == b.key
    clock = [1000.0]
    gate = ProactiveGate(clock=lambda: clock[0])
    assert gate.decide(student_id=8, key=a.key, priority=a.priority, mode='balanced').show
    clock[0] += 400
    assert not gate.decide(student_id=8, key=b.key, priority=b.priority, mode='balanced').show


def test_key_is_scoped_by_course_and_topic():
    x = attention_decision(insight(), topics=(topic(),), today=TODAY).key
    y = attention_decision(insight(), topics=(topic(course='LGS Matematik'),), today=TODAY).key
    z = attention_decision(insight(), topics=(topic(name='Söz Sanatları'),), today=TODAY).key
    assert x != y and x != z and y != z


def test_checkbox_never_pops_but_keys_are_stable():
    a = attention_decision(insight('📉 Geçmiş Doğruluk %40', '40%'), source='checkbox',
                           lesson='LGS Türkçe', topic_name='Fiilimsiler', today=TODAY)
    b = attention_decision(insight('📉 Geçmiş Doğruluk %30', '30%'), source='checkbox',
                           lesson='LGS Türkçe', topic_name='Fiilimsiler', today=TODAY)
    assert not a.auto_eligible and a.priority == 1 and a.key == b.key


def test_no_measurement_is_not_failure_diagnosis():
    a = attention_decision(insight('💡 Fark Ettiniz mi?'), source='student', completed_hw=45)
    b = attention_decision(insight('💡 Fark Ettiniz mi?'), source='student', completed_hw=46)
    assert a.priority == 2 and a.key == b.key and a.reason == 'verification_gap'


def test_workload_requires_overdue_for_popup():
    i = insight('📊 Yük İstatistiği')
    assert not attention_decision(i, open_hw=12, overdue_hw=0).auto_eligible
    assert attention_decision(i, open_hw=12, overdue_hw=4).priority == 3


def test_unknown_and_summary_are_inbox_only():
    assert not attention_decision(insight('⚠️ Veri Doğrulama')).auto_eligible
    assert not attention_decision(insight('🧭 Keşif Notu')).auto_eligible


def test_integrated_source_has_no_homework_mutations_and_no_visual_relayout():
    root = Path(__file__).resolve().parents[1]
    ui = (root / 'ui/smart_coach_secretary_toast.py').read_text(encoding='utf-8')
    service = (root / 'services/coach_assistant_v1/attention_v263.py').read_text(encoding='utf-8')
    ast.parse(ui); ast.parse(service)
    assert 'attention_decision(insight' in ui
    assert 'self._proactive.decide(' in ui
    assert 'source="checkbox", lesson=ders, topic_name=topic_name' in ui
    assert 'if not decision.auto_eligible:' in ui
    assert 'setFixedWidth(408)' in ui
    for x in ('INSERT INTO odev', 'UPDATE odev', 'DELETE FROM odev', 'requests.', 'urllib.request'):
        assert x not in service


def test_concise_auto_message_evidence_without_student_identity():
    v = attention_decision(insight(), topics=(topic(),), today=TODAY)
    assert v.brief_hook and 'Fiilimsiler' in v.brief_hook
    assert '20 yanıt' in v.brief_body
    assert 'doğrulayın' in v.brief_body
    assert 'Öğrenci başarı' not in v.brief_hook


def test_critical_old_measurement_never_auto_even_with_large_homework_count():
    v = attention_decision(insight(), topics=(topic(day=TODAY - timedelta(days=45)),),
                           open_hw=20, overdue_hw=10, completed_hw=30, today=TODAY)
    assert not v.auto_eligible and v.brief_body is None


def test_gate_quiet_mode_preserves_manual_access_through_inbox():
    gate = ProactiveGate(clock=lambda: 500.)
    v = attention_decision(insight(), topics=(topic(),), today=TODAY)
    assert not gate.decide(student_id=22, key=v.key, priority=v.priority, mode='quiet').show
    assert v.auto_eligible  # the UI can still save it in its existing menu


def test_source_preserves_toast_and_question_panel_sizes():
    root = Path(__file__).resolve().parents[1]
    toast_src = (root/'ui/smart_coach_secretary_toast.py').read_text(encoding='utf-8')
    dialogue_src = (root/'ui/coach_dialogue_v121.py').read_text(encoding='utf-8')
    assert 'self.setFixedWidth(408)' in toast_src
    assert 'self.setFixedWidth(430)' in dialogue_src or 'setFixedWidth(430)' in dialogue_src
    assert 'self._present_insight(insight, manual=False, source="checkbox"' in toast_src
