"""V26.7: no Qt, real data, schema or network needed."""
from pathlib import Path
import ast
import hashlib
import pytest

from services.coach_assistant_v1.event_router_v267 import (
    CoachChange, CoachChangeRouter, affects,
)


def test_only_matching_student_receives_scoped_hint():
    r = CoachChangeRouter()
    old = r.cursor
    r.publish(CoachChange('independent_measurement', 7, 'LGS Türkçe', 'Fiilimsiler'))
    assert r.check(old, student_id=7, lesson='LGS Türkçe').changed
    assert not r.check(old, student_id=8, lesson='LGS Türkçe').changed
    assert not r.check(old, student_id=7, lesson='LGS Matematik').changed


def test_all_lessons_viewer_gets_specific_course_changes():
    e = CoachChange('homework', 2, 'TYT Fizik', 'Enerji')
    assert affects(e, student_id=2)
    assert affects(e, student_id=2, lesson='TYT Fizik')
    assert not affects(e, student_id=2, lesson='AYT Matematik')
    assert not affects(e, student_id=3)


def test_topic_filter_and_unknown_topic():
    e = CoachChange('independent_measurement', 2, 'TYT Fizik', 'Elektrik')
    assert affects(e, student_id=2, lesson='TYT Fizik', topic='Elektrik')
    assert not affects(e, student_id=2, lesson='TYT Fizik', topic='Basınç')
    assert affects(CoachChange('coaching_plan', 2, 'TYT Fizik'),
                   student_id=2, lesson='TYT Fizik', topic='Basınç')


def test_legacy_unknown_sqlite_change_is_never_mistaken_for_specific_student():
    unknown = CoachChange('database_unknown')
    for sid in (1, 22, 200):
        assert affects(unknown, student_id=sid, lesson='LGS Türkçe')
    for kwargs in ({'student_id': 5}, {'lesson': 'LGS Türkçe'}, {'topic': 'Fiilimsiler'}):
        with pytest.raises(ValueError):
            CoachChange('database_unknown', **kwargs)


def test_scoped_hints_must_include_valid_student_id():
    for candidate in (None, 0, -1, True, '5', 1.5):
        with pytest.raises(ValueError):
            CoachChange('control', student_id=candidate)
    with pytest.raises(ValueError):
        CoachChange('not_a_coaching_kind', student_id=1)


def test_invalid_scopes_fail_closed():
    with pytest.raises(ValueError):
        CoachChange('homework', student_id=2, lesson='')
    with pytest.raises(ValueError):
        CoachChange('homework', student_id=2, topic='Basınç')
    with pytest.raises(ValueError):
        CoachChange('homework', student_id=2, lesson='TYT Fizik', topic=' ')
    with pytest.raises(ValueError):
        CoachChange('homework', student_id=2, revision='a' * 161)


def test_queued_events_are_pulled_without_callbacks():
    r = CoachChangeRouter()
    state = r.cursor
    r.publish(CoachChange('exam', student_id=3, lesson='TYT Fizik'))
    r.publish(CoachChange('student_profile', student_id=4))
    view = r.check(state, student_id=4)
    assert view.changed and view.cursor == 2
    assert not r.check(view.cursor, student_id=4).changed
    assert not r.check(state, student_id=5).changed


def test_distinct_database_revisions_are_distinct_hints():
    r = CoachChangeRouter()
    assert r.publish(CoachChange('database_unknown', revision='db-rev-1')) == 1
    assert r.publish(CoachChange('database_unknown', revision='db-rev-1')) == 1
    assert r.publish(CoachChange('database_unknown', revision='db-rev-2')) == 2


def test_events_without_revision_remain_separate_real_updates():
    r = CoachChangeRouter()
    e = CoachChange('homework', student_id=10)
    assert r.publish(e) == 1
    assert r.publish(e) == 2


def test_repeated_identical_change_does_not_duplicate_work():
    r = CoachChangeRouter()
    event = CoachChange('exam', student_id=7, lesson='LGS Matematik', revision='fixed-123')
    assert r.publish(event) == 1
    assert r.publish(event) == 1
    assert r.cursor == 1
    assert r.publish(CoachChange('exam', student_id=7,
                                 lesson='LGS Matematik', revision='fixed-124')) == 2


def test_queue_overflow_is_safe_global_invalidation():
    r = CoachChangeRouter(capacity=2)
    old = r.cursor
    for i in range(5):
        r.publish(CoachChange('control', student_id=2, revision=str(i)))
    result = r.check(old, student_id=1, lesson='LGS Türkçe')
    assert result.overflow and result.changed and result.cursor == 5
    assert not r.check(result.cursor, student_id=1).changed


def test_invalid_viewer_id_never_receives_scoped_event():
    r = CoachChangeRouter()
    r.publish(CoachChange('control', student_id=1))
    for sid in (0, -1, None, True):
        assert not r.check(0, student_id=sid).changed


def test_router_cannot_receive_unvalidated_dict():
    r = CoachChangeRouter()
    with pytest.raises(TypeError):
        r.publish({'kind': 'homework', 'student_id': 1})
    with pytest.raises(ValueError):
        r.check(-1, student_id=1)


def test_protected_cores_and_previous_coaching_modules_stay_identical():
    root = Path(__file__).resolve().parents[1]
    hashes = {
        'ui/homework_form.py': '53e6b12db96cf81fd622947e7d343b4130a1a8e42a0e30d5c5ec58e64e456314',
        'db.py': '8b295f375a18b41bdb92f120170bafb9a2cb93863be9e98b789241ceb32c4d6b',
        'services/student_workspace_v21.py': '7f9f64c09723938a9bf9bb34712a2bc18101c67527bc5cac129e1cb06e17c49f',
        'ui/adaptive_coaching_center_v26.py': 'f93056b4df379e702572495198e3cd116bb8a0af351e9acedc62841209feb646',
        'ui/smart_coach_secretary_toast.py': (
            '6f48b901c3449a0612c16058bc40e6a74a797ee594d34e417970e6f5f7758ae9',
            'c3d06192cd979a7b6c478d75a4c96f85d9f0509eec05424c978204ce64850329',
        ),
    }
    for name, expected in hashes.items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if isinstance(expected, tuple):
            assert actual in expected, name
        else:
            assert actual == expected, name


def test_existing_dialogue_layout_unchanged_and_event_bus_opt_in():
    root = Path(__file__).resolve().parents[1]
    code = (root / 'ui/coach_dialogue_v121.py').read_text()
    ast.parse(code)
    assert 'self.setFixedWidth(430)' in code
    assert 'self.setFixedHeight(405)' in code
    assert "'database_unknown', revision=repr(observed_revision)[:160]" in code
    assert 'self._coach_router.check' in code
    assert 'PRAGMA query_only=ON' in code
    assert '_last_scope == self._scope_for_question()' in code
    assert 'self._refresh_waiting' in code
    assert 'class CoachChangeRouter:' in (root / 'services/coach_assistant_v1/event_router_v267.py').read_text()
