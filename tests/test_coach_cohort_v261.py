# -*- coding: utf-8 -*-
"""V26.1 integration-level SQLite tests with synthetic students; zero personal data."""
from __future__ import annotations
import sqlite3
from datetime import date, timedelta

from services.coach_assistant_v1.cohort_comparison_v261 import compare_topic, enrich_answer
from services.coach_assistant_v1.dialogue import CoachContext, CoachTopic, answer_question

NOW = date(2026, 10, 18)


def fixture_db():
    c = sqlite3.connect(':memory:')
    c.executescript('''
        CREATE TABLE ogrenci (id INTEGER PRIMARY KEY, ad TEXT, ana_grup TEXT,
                              alt_grup TEXT, aktif INTEGER DEFAULT 1);
        CREATE TABLE adaptive_observation_v25 (
          id INTEGER PRIMARY KEY, student_id INTEGER, lesson TEXT, topic TEXT,
          mode TEXT, correct INTEGER, wrong INTEGER, blank INTEGER,
          observed_on TEXT);
    ''')
    c.execute('INSERT INTO ogrenci VALUES (1,\'SEÇİLİ\',\'LGS\',\'8-A\',1)')
    for i in range(2, 9):
        c.execute('INSERT INTO ogrenci VALUES (?,?,?,?,1)', (i, f'PEER-{i}', 'LGS', '8-A'))
    c.execute('INSERT INTO ogrenci VALUES (9,\'BAŞKA\',\'LGS\',\'8-B\',1)')
    c.execute('INSERT INTO ogrenci VALUES (10,\'YKS\',\'YKS\',\'8-A\',1)')
    return c


def observation(c, sid=1, lesson='LGS_TURKCE', topic='Fiilimsiler', mode='Hedefli soru',
                yes=4, no=6, on=NOW):
    c.execute('''INSERT INTO adaptive_observation_v25
       (student_id, lesson, topic, mode, correct, wrong, blank, observed_on)
       VALUES(?,?,?,?,?,?,?,?)''',
              (sid, lesson, topic, mode, yes, no, 0, on.isoformat()))


def prepare(n=7):
    c = fixture_db()
    observation(c)
    for i in range(2, n+2):
        observation(c, sid=i, yes=8, no=2)
    return c


def compare(c, **kw):
    return compare_topic(c, 1, lesson='LGS Türkçe', topic='Fiilimsiler', today=NOW, **kw)


def test_success_median_independent_of_homework_and_no_peer_names():
    c = prepare()
    before = c.total_changes
    result = compare(c)
    assert result.available
    assert result.peers == 7
    assert result.student_accuracy == 40 and result.peer_median == 80
    assert 'SEÇİLİ' not in result.short_message() and 'PEER' not in result.short_message()
    assert 'soru eşdeğerliği doğrulanmadı' in result.short_message()
    assert c.total_changes == before


def test_fewer_than_five_distinct_valid_peers_hides_aggregate():
    c = prepare(n=4)
    result = compare(c)
    assert result.status == 'insufficient' and result.peer_median is None
    assert '5' in result.reason


def test_single_peer_with_many_observations_is_not_five_peers():
    c = prepare(n=1)
    for _ in range(100):
        observation(c, sid=2)
    assert not compare(c).available


def test_foreign_group_course_topic_and_mode_do_not_contaminate():
    c = fixture_db()
    observation(c)
    for i in range(2, 7):
        observation(c, sid=i, lesson='LGS_MATEMATIK')
        observation(c, sid=i, topic='Cümle Türleri')
        observation(c, sid=i, mode='Sözlü anlatım')
    observation(c, sid=9)
    observation(c, sid=10)
    result = compare(c)
    assert not result.available and result.peer_median is None


def test_old_data_and_future_data_are_ignored():
    c = fixture_db()
    observation(c)
    for i in range(2, 9):
        observation(c, sid=i, on=NOW-timedelta(days=40))
        observation(c, sid=i, on=NOW+timedelta(days=1))
    assert compare(c).status == 'insufficient'


def test_target_too_few_recent_responses_not_compared():
    c = prepare()
    c.execute('DELETE FROM adaptive_observation_v25 WHERE student_id=1')
    observation(c, yes=1, no=2)
    assert compare(c).status == 'insufficient'


def test_missing_table_is_not_treated_as_zero_performance():
    c = fixture_db()
    c.execute('DROP TABLE adaptive_observation_v25')
    result = compare(c)
    assert result.status == 'missing_source' and result.student_accuracy is None


def test_inactive_target_or_missing_group_disables_comparison():
    c = prepare()
    c.execute('UPDATE ogrenci SET aktif=0 WHERE id=1')
    assert compare(c).status == 'invalid_scope'
    c.execute('UPDATE ogrenci SET aktif=1, alt_grup=NULL WHERE id=1')
    assert compare(c).status == 'invalid_scope'


def test_bounded_group_never_uses_truncated_comparison():
    c = prepare()
    for i in range(11, 135):
        c.execute('INSERT INTO ogrenci VALUES (?,?,?,?,1)', (i, 'FAKE', 'LGS', '8-A'))
    result = compare(c)
    assert result.status == 'oversize' and result.peer_median is None


def test_priority_adds_one_line_without_new_user_click_or_ui_change(monkeypatch):
    c = prepare()
    ctx = CoachContext(1, 'SEÇİLİ', 4, 40, 1, 3,
                       topics=(CoachTopic('LGS_TURKCE', 'Fiilimsiler', attempts=10,
                                          accuracy=40, observations=1),))
    a = answer_question(ctx, 'Öğrencinin öncelikli akademik ihtiyacı ne?', lesson_scope='LGS Türkçe')
    # Override only time for deterministic synthetic test, not real runtime.
    import services.coach_assistant_v1.cohort_comparison_v261 as module
    actual = module.compare_topic
    def fixed(con, sid, *, lesson, topic):
        return actual(con, sid, lesson=lesson, topic=topic, today=NOW)
    monkeypatch.setattr(module, 'compare_topic', fixed)
    enriched = enrich_answer(c, ctx, a, 'Öğrencinin öncelikli akademik ihtiyacı ne?', lesson_scope='LGS Türkçe')
    assert 'Grup sinyali:' in enriched.message
    assert 'ortanca doğruluk %80' in enriched.message
    assert 'Fiilimsiler' in enriched.message and 'Konu' in ' '.join(enriched.evidence)
    assert enriched.action_target == a.action_target


def test_no_cohort_does_not_override_primary_local_priority():
    c = prepare(n=3)
    ctx = CoachContext(1, 'SEÇİLİ', 4, 40, 1, 3,
                       topics=(CoachTopic('LGS_TURKCE','Fiilimsiler',attempts=10,accuracy=40),))
    a = answer_question(ctx, 'Öncelik ne?', lesson_scope='LGS Türkçe')
    enriched = enrich_answer(c, ctx, a, 'Öncelik ne?', lesson_scope='LGS Türkçe')
    assert enriched == a


def test_explicit_group_question_requires_selected_lesson():
    c = prepare()
    ctx = CoachContext(1, 'SEÇİLİ', 4, 40, 1, 3,
                       topics=(CoachTopic('LGS_TURKCE','Fiilimsiler',attempts=10,accuracy=40),))
    base = answer_question(ctx, 'Durum?')
    a = enrich_answer(c, ctx, base, 'Sınıfla karşılaştır')
    assert 'ders seçin' in a.title.lower()
    assert '80' not in a.message


def test_explicit_comparison_works_on_same_scope(monkeypatch):
    c = prepare()
    ctx = CoachContext(1, 'SEÇİLİ', 4, 40, 1, 3,
                       topics=(CoachTopic('LGS_TURKCE','Fiilimsiler',attempts=10,accuracy=40),))
    base = answer_question(ctx, 'Durum?')
    import services.coach_assistant_v1.cohort_comparison_v261 as module
    actual = module.compare_topic
    monkeypatch.setattr(module,'compare_topic',lambda con,sid,*,lesson,topic: actual(con,sid,lesson=lesson,topic=topic,today=NOW))
    a = enrich_answer(c, ctx, base, 'Sınıfla karşılaştır', lesson_scope='LGS Türkçe')
    assert 'ortanca doğruluk %80' in a.message
    assert 'Konuya göre' in a.title


def test_read_only_uri_with_query_only_keeps_records_unchanged(tmp_path):
    file = tmp_path / 'teacher_test.db'
    original = prepare()
    original.commit()
    dst = sqlite3.connect(file)
    original.backup(dst)
    dst.close(); original.close()
    before = file.read_bytes()
    readonly = sqlite3.connect(file.resolve().as_uri()+'?mode=ro', uri=True)
    readonly.execute('PRAGMA query_only=ON')
    assert compare(readonly).available
    readonly.close()
    assert file.read_bytes() == before


def test_rejected_cross_course_request_cannot_be_replaced_by_group_result():
    c = prepare()
    ctx = CoachContext(1, 'SEÇİLİ', 4, 40, 1, 3,
                       topics=(CoachTopic('LGS_TURKCE', 'Fiilimsiler', attempts=10, accuracy=40),
                               CoachTopic('LGS_MATEMATIK', 'Üslü İfadeler', attempts=10, accuracy=30)))
    question = 'LGS Matematik sınıfındaki durumum nasıl?'
    blocked = answer_question(ctx, question, lesson_scope='LGS Türkçe')
    assert blocked.title == 'Ders kapsamı uyuşmuyor'
    assert enrich_answer(c, ctx, blocked, question, lesson_scope='LGS Türkçe') == blocked


def test_healthy_course_priority_remains_quiet_even_with_comparable_peers():
    c = prepare()
    ctx = CoachContext(1, 'SEÇİLİ', 4, 40, 1, 3,
                       topics=(CoachTopic('LGS_TURKCE','Fiilimsiler',attempts=10,accuracy=90),))
    question = 'Öğrencinin öncelikli akademik ihtiyacı ne?'
    a = answer_question(ctx, question, lesson_scope='LGS Türkçe')
    assert enrich_answer(c, ctx, a, question, lesson_scope='LGS Türkçe') == a
