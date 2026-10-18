# -*- coding: utf-8 -*-
"""V26.2: synthetic assessments only; no real student names or private records."""
import sqlite3
from datetime import date, timedelta

from services.coach_assistant_v1.learning_trends_v262 import (
    analyze_topic, enrich_answer, MAX_OBSERVATION_ROWS,
)
from services.coach_assistant_v1.dialogue import CoachAnswer, CoachContext, CoachTopic, answer_question

NOW = date(2026, 10, 18)
LESSON = 'LGS_TURKCE'
TOPIC = 'Fiilimsiler'


def sample_db():
    con = sqlite3.connect(':memory:')
    con.execute('''CREATE TABLE adaptive_observation_v25 (
        id INTEGER PRIMARY KEY, student_id INTEGER, lesson TEXT, topic TEXT,
        mode TEXT, correct INTEGER, wrong INTEGER, blank INTEGER, observed_on TEXT)''')
    return con


def observe(con, *, sid=1, day=5, c=3, w=2, b=0, mode='Hedefli soru',
            topic=TOPIC, lesson=LESSON):
    on = (NOW - timedelta(days=day)).isoformat()
    con.execute('''INSERT INTO adaptive_observation_v25
        (student_id, lesson, topic, mode, correct, wrong, blank, observed_on)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (sid, lesson, topic, mode, c, w, b, on))


def period(con, *, earlier=(2, 8), recent=(4, 6), **kw):
    # Older: -46, -37; recent: -11, -4. Different session days in each window.
    for day, count in [(46, earlier[0]), (37, earlier[1]),
                       (11, recent[0]), (4, recent[1])]:
        observe(con, day=day, c=count, w=10-count, **kw)


def trend(con, **kw):
    return analyze_topic(con, 1, lesson='LGS Türkçe', topic=TOPIC, today=NOW, **kw)


def ctx(*topics, unavailable=()):
    return CoachContext(1, 'ÖRNEK', 5, 15, 0, 4,
                        topics=tuple(topics), unavailable_sources=unavailable)


def topic(*, acc=50, attempts=40, done=2, name=TOPIC, observations=4):
    return CoachTopic(LESSON, name, done=done, observations=observations,
                      attempts=attempts, accuracy=acc)


def test_measured_fall_is_short_temporal_signal_not_prediction():
    c = sample_db(); period(c, earlier=(8, 8), recent=(4, 4))
    before = c.total_changes
    t = trend(c)
    assert t.available and t.direction == 'fall'
    assert t.earlier_accuracy == 80 and t.recent_accuracy == 40
    assert t.delta_points == -40 and t.earlier_days == t.recent_days == 2
    assert 'kesin öğrenme değişimi değildir' in t.short_message()
    assert c.total_changes == before


def test_measured_rise_and_no_significant_claims():
    c = sample_db(); period(c, earlier=(4, 4), recent=(8, 8))
    t = trend(c)
    assert t.available and t.direction == 'rise' and t.delta_points == 40
    assert 'neden-sonuç kanıtlanmadı' in ' '.join(t.evidence())


def test_stable_results_not_presented_as_worsening():
    c = sample_db(); period(c, earlier=(5, 5), recent=(6, 6))
    t = trend(c)
    assert t.direction == 'flat' and t.delta_points == 10


def test_same_day_many_questions_does_not_count_as_two_sessions():
    c = sample_db()
    observe(c, day=35, c=30, w=10)
    observe(c, day=3, c=12, w=28)
    assert trend(c).status == 'insufficient'


def test_one_window_too_few_answers_never_claims_trend():
    c = sample_db()
    for d in (40, 36): observe(c, day=d, c=2, w=1)
    for d in (10, 4): observe(c, day=d, c=7, w=3)
    assert trend(c).status == 'insufficient'


def test_excludes_other_students_courses_topics_and_modes():
    c = sample_db()
    observe(c, day=40)
    observe(c, day=36, sid=2)
    observe(c, day=10, lesson='LGS_MATEMATIK')
    observe(c, day=9, topic='Cümle Türleri')
    observe(c, day=4, mode='Sözlü anlatım')
    assert trend(c).status == 'insufficient'


def test_recent_measurement_stale_and_future_does_not_rescue():
    c = sample_db()
    for d in (45, 35, 26, 20): observe(c, day=d, c=6, w=4)
    observe(c, day=-1, c=9, w=1)
    assert trend(c).status == 'stale'


def test_mode_anchored_by_latest_valid_assessment():
    c = sample_db(); period(c)
    observe(c, day=1, c=4, w=6, mode='Sözlü anlatım')
    # New mode cannot borrow past mode data for trend.
    assert trend(c).status == 'insufficient'


def test_zero_percent_is_not_missing_measurement():
    c = sample_db(); period(c, earlier=(8,8), recent=(0,0))
    t = trend(c)
    assert t.available and t.recent_accuracy == 0 and t.direction == 'fall'


def test_absent_table_and_invalid_student_are_not_zero_percent():
    c = sqlite3.connect(':memory:')
    assert analyze_topic(c, 1, lesson='LGS Türkçe', topic=TOPIC, today=NOW).status == 'missing_source'
    assert analyze_topic(c, -1, lesson='LGS Türkçe', topic=TOPIC, today=NOW).status == 'invalid_scope'


def test_oversize_dataset_suppresses_truncated_trend():
    c = sample_db()
    period(c)
    c.executemany('''INSERT INTO adaptive_observation_v25
        (student_id,lesson,topic,mode,correct,wrong,blank,observed_on)
        VALUES (1,'LGS_MATEMATIK','X','Hedefli soru',2,3,0,?)''',
        [(NOW.isoformat(),)] * MAX_OBSERVATION_ROWS)
    assert trend(c).status == 'oversize'


def test_priority_gets_one_line_without_changing_original_answer(monkeypatch):
    c = sample_db(); period(c, earlier=(8,8), recent=(4,4))
    import services.coach_assistant_v1.learning_trends_v262 as module
    real = module.analyze_topic
    monkeypatch.setattr(module, 'analyze_topic', lambda con, sid, *, lesson, topic: real(
        con, sid, lesson=lesson, topic=topic, today=NOW))
    s = ctx(topic(acc=40))
    a = answer_question(s, 'Öğrencinin öncelikli akademik ihtiyacı ne?', lesson_scope='LGS Türkçe')
    enriched = enrich_answer(c, s, a, 'Öğrencinin öncelikli akademik ihtiyacı ne?',
                             lesson_scope='LGS Türkçe')
    assert 'Gelişim sinyali:' in enriched.message
    assert '%80 → %40' in enriched.message
    assert enriched.action_target == a.action_target
    assert a.message != enriched.message  # immutable primary answer retained


def test_flat_priority_is_quiet_and_does_not_repeat_existing_data(monkeypatch):
    c = sample_db(); period(c, earlier=(5, 5), recent=(6, 6))
    import services.coach_assistant_v1.learning_trends_v262 as module
    real = module.analyze_topic
    monkeypatch.setattr(module, 'analyze_topic', lambda con, sid, *, lesson, topic: real(
        con, sid, lesson=lesson, topic=topic, today=NOW))
    s = ctx(topic(acc=40))
    a = answer_question(s, 'Öncelik ne?', lesson_scope='LGS Türkçe')
    assert enrich_answer(c, s, a, 'Öncelik ne?', lesson_scope='LGS Türkçe') == a


def test_explicit_trend_question_explains_what_was_calculated(monkeypatch):
    c = sample_db(); period(c, earlier=(8, 8), recent=(4, 4))
    import services.coach_assistant_v1.learning_trends_v262 as module
    real = module.analyze_topic
    monkeypatch.setattr(module, 'analyze_topic', lambda con, sid, *, lesson, topic: real(
        con, sid, lesson=lesson, topic=topic, today=NOW))
    original = CoachAnswer('Eski cevap', 'Ödev sayısı', ())
    a = enrich_answer(c, ctx(topic(acc=40)), original, 'Fiilimsiler gelişimi nasıl?',
                      lesson_scope='LGS Türkçe')
    assert 'Konu gelişimi' in a.title and 'soru güçlükleri' in a.message.lower()
    assert 'Fiilimsiler' in a.message and 'Ödev sayısı' not in a.message


def test_course_scope_does_not_use_other_lessons():
    c = sample_db(); period(c, lesson='LGS_MATEMATIK', topic='Üslü')
    s = ctx(CoachTopic('LGS_MATEMATIK', 'Üslü', attempts=50, accuracy=25))
    a = CoachAnswer('Normal', 'Normal yanıt', ())
    actual = enrich_answer(c, s, a, 'Bu dersin gelişimi nasıl?', lesson_scope='LGS Türkçe')
    assert actual.title == 'Gelişim eğilimi için ölçüm gerekli'
    assert 'Üslü' not in actual.message


def test_course_mismatch_rejection_never_bypassed():
    c = sample_db(); period(c)
    a = CoachAnswer('Ders kapsamı uyuşmuyor', 'Seçili ders hatalı', ())
    assert enrich_answer(c, ctx(topic(acc=40)), a, 'Türkçe gelişimi', lesson_scope='LGS Türkçe') == a


def test_missing_topics_source_is_reported_not_zero_accuracy():
    c = sample_db()
    a = enrich_answer(c, ctx(unavailable=('Konu kayıtları okunamadı',)),
                      CoachAnswer('Başlık', 'Eski', ()), 'Gelişim ne durumda?', lesson_scope='LGS Türkçe')
    assert 'okunamadı' in a.message and 'yapılamıyor' in a.title


def test_homework_learning_shortcut_reports_scoped_divergence_not_global_counts():
    c = sample_db()
    observe(c, day=4, c=2, w=8)
    a = enrich_answer(c, ctx(topic(acc=30, attempts=16, done=3)),
                      CoachAnswer('Genel', 'Genel ödev 40', ()),
                      'Ödevler ile öğrenme kanıtı tutarlı mı?', lesson_scope='LGS Türkçe')
    assert 'Ödev–ölçüm' in a.title and 'Fiilimsiler' in a.message
    assert '%20' in a.message and '3 tamamlanmış' in a.message
    assert 'Genel ödev 40' not in a.message


def test_completed_homework_without_assessment_is_not_mastery():
    c = sample_db()
    a = enrich_answer(c, ctx(topic(acc=None, attempts=0, done=4, observations=0)),
                      CoachAnswer('Genel', 'Genel', ()),
                      'Ödev–öğrenme', lesson_scope='LGS Türkçe')
    assert 'güncel öğrenme kanıtı yetersiz' in a.title and '4 tamamlanmış' in a.message


def test_no_homework_not_misrepresented_as_gap():
    c = sample_db()
    a = enrich_answer(c, ctx(topic(acc=20, attempts=14, done=0)),
                      CoachAnswer('Genel', 'Genel', ()),
                      'Ödev–öğrenme', lesson_scope='LGS Türkçe')
    assert 'ayrışması doğrulanamadı' in a.title


def test_other_course_topic_cannot_be_reported_as_turkish_homework_gap():
    c = sample_db()
    a = enrich_answer(c, ctx(CoachTopic('LGS_MATEMATIK', 'Üslü', done=3, attempts=10, accuracy=10)),
                      CoachAnswer('Normal', 'Normal', ()),
                      'Ödevler ile öğrenme kanıtı tutarlı mı?', lesson_scope='LGS Türkçe')
    assert 'Üslü' not in a.message


def test_readonly_connection_integrity_after_analysis(tmp_path):
    src = sample_db(); period(src); src.commit()
    filepath = tmp_path / 'ro.db'
    dest = sqlite3.connect(filepath); src.backup(dest); dest.close(); src.close()
    snapshot = filepath.read_bytes()
    ro = sqlite3.connect(filepath.resolve().as_uri() + '?mode=ro', uri=True)
    ro.execute('PRAGMA query_only=ON')
    assert analyze_topic(ro, 1, lesson='LGS Türkçe', topic=TOPIC, today=NOW).available
    ro.close()
    assert filepath.read_bytes() == snapshot


def test_historic_low_score_is_not_claimed_as_current_gap():
    c = sample_db()
    observe(c, day=120, c=0, w=10)
    a = enrich_answer(c, ctx(topic(acc=0, attempts=10, done=2)),
                      CoachAnswer('Genel', 'Genel', ()),
                      'Ödev–öğrenme', lesson_scope='LGS Türkçe')
    assert 'güncel öğrenme kanıtı yetersiz' in a.title
    assert '%0' not in a.message


def test_missing_table_does_not_infer_no_learning_evidence():
    c = sqlite3.connect(':memory:')
    a = enrich_answer(c, ctx(topic(acc=None, attempts=0, done=2, observations=0)),
                      CoachAnswer('Genel', 'Genel', ()),
                      'Ödev–öğrenme', lesson_scope='LGS Türkçe')
    assert 'kaynağı okunamıyor' in a.title
    assert 'sıfır kabul etmiyorum' in a.message


def test_historic_low_score_is_not_claimed_as_current_gap():
    c = sample_db()
    observe(c, day=120, c=0, w=10)
    a = enrich_answer(c, ctx(topic(acc=0, attempts=10, done=2)),
                      CoachAnswer('Genel', 'Genel', ()),
                      'Ödev–öğrenme', lesson_scope='LGS Türkçe')
    assert 'güncel öğrenme kanıtı yetersiz' in a.title
    assert '%0' not in a.message


def test_missing_table_does_not_infer_no_learning_evidence():
    c = sqlite3.connect(':memory:')
    a = enrich_answer(c, ctx(topic(acc=None, attempts=0, done=2, observations=0)),
                      CoachAnswer('Genel', 'Genel', ()),
                      'Ödev–öğrenme', lesson_scope='LGS Türkçe')
    assert 'kaynağı okunamıyor' in a.title
    assert 'sıfır kabul etmiyorum' in a.message
