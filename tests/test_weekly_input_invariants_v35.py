"""Exact-source workload acceptance; no Qt installation needed."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.weekly_input_invariants_v35 import validate_homework_source
from services.calendar_plan_integrity import validate_weekly_plan
from tests.test_planning_constraints_v3511 import SmartCalendarService, sample
from services.planning_constraints import serialize_details


def test_two_real_homeworks_preserved_across_schedule():
    tasks = [
        {'ders':'Fizik', 'konu':'Yay Dalgaları', 'kitap':'FİZİK3', 'sure':75},
        {'ders':'Fizik', 'konu':'Yay Dalgaları', 'kitap':'xxx', 'sure':'75'},
    ]
    assert validate_homework_source(tasks) == {'task_count':2, 'minutes':150}
    data = sample(school_by_day={}, blocks=['Cumartesi [08:00-16:00] Kurs'],
                  wake='08:00',sleep='22:00',max=180,empty='Yok')
    bundle = SmartCalendarService.create_weekly_plan_data('Pilot Öğrenci',tasks,serialize_details(data))
    assert bundle['input_summary'] == {'task_count':2, 'minutes':150}
    assert validate_weekly_plan(bundle) == []
    assert sum(t.sure for t in bundle['tasks']) == 150
    assert all(t.kitap in bundle['html'] for t in bundle['tasks'])


@pytest.mark.parametrize('task', [
    {'ders':'Fizik','konu':'Enerji','sure':0},
    {'ders':'Fizik','konu':'Enerji','sure':601},
    {'ders':'Fizik','konu':'Enerji','sure':'75.5'},
    {'ders':'Fizik','konu':'Enerji','sure':True},
    {'ders':'Fizik','konu':'Enerji','sure':None},
    {'ders':'Fizik','konu':'Enerji','sure':30,'deadline':'not a date'},
    {'ders':'Fizik','sure':30},
    {'konu':'Enerji','sure':30},
    None,
])
def test_invalid_source_fails_before_any_schedule(task):
    data=serialize_details(sample())
    with pytest.raises(ValueError):
        SmartCalendarService.create_weekly_plan_data('Pilot',[task],data)


def test_source_invariants_cannot_be_circumvented_after_generation():
    original = [{'ders':'Fizik','konu':'Enerji','sure':40}]
    data=serialize_details(sample(blocks=[],school_by_day={},empty='Yok'))
    bundle=SmartCalendarService.create_weekly_plan_data('Pilot',original,data)
    assert validate_weekly_plan(bundle)==[]
    bundle['input_summary']['minutes'] += 3
    assert any('toplam süresi' in error for error in validate_weekly_plan(bundle))
