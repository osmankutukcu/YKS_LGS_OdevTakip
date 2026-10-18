# -*- coding: utf-8 -*-
"""V26.0 regression: isolated LGS Turkish priority, evidence and read-only dialogue."""
from __future__ import annotations
from dataclasses import replace

from services.coach_assistant_v1.dialogue import (
    CoachContext, CoachTopic, answer_question,
)
from services.coach_assistant_v1.conversation_followup import (
    answer_with_memory, next_memory,
)
from services.coach_assistant_v1.shared_rules_v260 import (
    lesson_key, is_low_accuracy, question_lesson, scoped_topics,
)


def sample(*topics, unavailable=()):
    return CoachContext(student_id=12, student_name='TEST ÖĞRENCİ',
                        completed_homework=40, open_homework=9, overdue_homework=2,
                        measured_count=18, priority='TYT Fizik / Enerji',
                        next_step='Fizik ödevi ver', basis='öğrenci genelinde',
                        topics=topics, unavailable_sources=unavailable)


def ask(ctx, question='Öğrencinin öncelikli akademik ihtiyacı ne?', course='LGS Türkçe'):
    return answer_question(ctx, question, lesson_scope=course)


def test_lgs_turkish_is_same_key_in_db_and_current_tab():
    assert lesson_key('LGS_TURKCE') == lesson_key('LGS Türkçe')
    assert lesson_key('LGS_TURKCE') != lesson_key('TYT_TURKCE')


def test_priority_low_accuracy_turkish_ignores_worse_other_course():
    ctx = sample(CoachTopic('LGS_TURKCE', 'Fiilimsiler', attempts=10, observations=2, accuracy=40),
                 CoachTopic('LGS_TURKCE', 'Cümlenin Ögeleri', attempts=9, observations=3, accuracy=75),
                 CoachTopic('TYT_FIZIK', 'Enerji', attempts=18, observations=1, accuracy=0))
    ans = ask(ctx)
    assert 'Fiilimsiler' in ans.message and '%40' in ans.message
    assert 'TYT' not in ans.message and 'Fizik ödevi' not in ans.message
    assert any('Öğrenci geneli:' in e for e in ans.evidence)
    assert any('genel ödev sayıları' in e for e in ans.evidence)


def test_zero_percent_is_real_low_accuracy():
    t = CoachTopic('LGS_TURKCE', 'Yazım Kuralları', attempts=8, observations=1, accuracy=0)
    ans = ask(sample(t))
    assert '%0' in ans.message and 'Yazım Kuralları' in ans.message
    assert is_low_accuracy(0, attempts=5, reliable_only=True)


def test_priority_completed_but_unmeasured():
    ans = ask(sample(CoachTopic('LGS_TURKCE', 'Deyimler', done=4, attempts=0, observations=0)))
    assert 'ölçme' in ans.title.lower()
    assert 'Deyimler' in ans.message
    assert 'öğrenemediğini' in ans.message


def test_priority_partial_responses_insufficient():
    ans = ask(sample(CoachTopic('LGS_TURKCE', 'Söz Sanatları', attempts=3, observations=1, accuracy=25)))
    assert 'örnek' in ans.title.lower() and '3 yanıt' in ans.message
    assert 'telafi' not in ans.title.lower()


def test_priority_with_measurements_but_no_risk_does_not_claim_full_mastery():
    ans = ask(sample(CoachTopic('LGS_TURKCE', 'Noktalama İşaretleri', attempts=15, observations=2, accuracy=92)))
    assert 'kritik ihtiyaç' in ans.title
    assert 'eksik olmadığı anlamına' in ans.message


def test_priority_no_topic_data_does_not_invent_turkish_weakness():
    ans = ask(sample(CoachTopic('TYT_FIZIK', 'Elektrik', attempts=18, observations=2, accuracy=10)))
    assert 'yeterli kayıt' in ans.title
    assert 'Elektrik' not in ans.message


def test_read_failure_does_not_mean_no_learning_measurement():
    ans = ask(sample(CoachTopic('LGS_TURKCE', 'Fiilimsiler', done=4),
                     unavailable=('Konu kayıtları okunamadı',)))
    assert 'okunamadığı' in ans.message and 'Öncelik' in ans.title
    assert 'Fiilimsiler' not in ans.message


def test_different_lesson_explicit_question_is_rejected():
    ctx = sample(CoachTopic('LGS_TURKCE', 'Fiilimsiler', attempts=8, accuracy=15),
                 CoachTopic('LGS_MATEMATIK', 'Üslü İfadeler', attempts=8, accuracy=10))
    ans = ask(ctx, 'LGS Matematikte önceliğim ne?')
    assert 'uyuşmuyor' in ans.title


def test_ambiguous_course_question_requires_level_in_all_courses():
    ctx = sample(CoachTopic('TYT_MATEMATIK', 'Problemler'),
                 CoachTopic('AYT_MATEMATIK', 'Türev'))
    assert question_lesson(ctx.topics, 'Matematikte zorlanıyor mu?')[1]
    ans = answer_question(ctx, 'Matematikte zorlanıyor mu?')
    assert 'belirsiz' in ans.title


def test_homework_learning_shortcut_gets_comparison_not_generic_reason():
    ans = ask(sample(CoachTopic('LGS_TURKCE', 'Deyimler', done=4)),
              'Ödevler ile öğrenme kanıtı tutarlı mı?')
    assert 'karşılaştırması' in ans.title
    assert 'tamamlanmış' in ans.message


def test_another_topic_followup_keeps_lgs_turkish_scope():
    ctx = sample(CoachTopic('LGS_TURKCE', 'Fiilimsiler', attempts=12, observations=2, accuracy=15),
                 CoachTopic('LGS_TURKCE', 'Yazım Kuralları', attempts=9, observations=2, accuracy=38),
                 CoachTopic('TYT_FIZIK', 'Elektrik', attempts=20, observations=2, accuracy=1))
    memory = next_memory(12, 'Hangi konuda zorlanıyor?', lesson_scope='LGS Türkçe')
    ans = answer_with_memory(ctx, 'Başka hangi konu?', memory, lesson_scope='LGS Türkçe')
    assert 'Yazım Kuralları' in ans.message and 'Elektrik' not in ans.message
    next_mem = next_memory(12, 'Başka hangi konu?', memory, lesson_scope='LGS Türkçe')
    ans = answer_with_memory(ctx, 'Neden?', next_mem, lesson_scope='LGS Türkçe')
    assert 'Yazım Kuralları' in ans.message


def test_memory_not_carried_to_different_lesson():
    ctx = sample(CoachTopic('LGS_TURKCE', 'Yazım', done=4),
                 CoachTopic('LGS_MATEMATIK', 'Üslü', done=1))
    mem = next_memory(12, 'Hangi konuda zorlanıyor?', lesson_scope='LGS Türkçe')
    ans = answer_with_memory(ctx, 'Başka hangi konu?', mem, lesson_scope='LGS Matematik')
    assert 'Yazım' not in ans.message


def test_priority_general_case_not_misrepresented_as_lgs_specific():
    ctx = sample()
    ans = answer_question(ctx, 'Öğrencinin öncelikli akademik ihtiyacı ne?')
    assert 'genel' in ans.title.lower() and 'TYT Fizik' in ans.message


def test_only_read_only_properties_and_pure_immutable_contexts():
    t = CoachTopic('LGS_TURKCE', 'Fiilimsiler', done=1, observations=0)
    ctx = sample(t)
    before = repr(ctx)
    for _ in range(3):
        ask(ctx)
    assert repr(ctx) == before
    assert tuple(scoped_topics(ctx.topics, 'LGS TÜRKÇE')) == (t,)
