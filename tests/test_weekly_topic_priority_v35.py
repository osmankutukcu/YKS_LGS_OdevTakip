# -*- coding: utf-8 -*-
"""Topic-scoped weekly priority: teacher consent, exact match, no writes."""
from __future__ import annotations
import copy
import sys
import types
from datetime import date, timedelta

# Calendar's legacy Qt imports are for printing only; scheduling needs none.
# Keep this focused suite runnable in dependency-light CI without claiming
# that real PyQt6 windows were exercised.
try:
    from PyQt6.QtPrintSupport import QPrinter
except ImportError:
    sys.modules.setdefault('PyQt6', types.ModuleType('PyQt6'))
    for sub_name, names in {
        'QtPrintSupport': ('QPrinter',),
        'QtGui': ('QTextDocument', 'QPageSize'),
        'QtCore': ('QUrl',),
    }.items():
        fullname = 'PyQt6.' + sub_name
        mod = sys.modules.setdefault(fullname, types.ModuleType(fullname))
        for name in names:
            if not hasattr(mod, name):
                setattr(mod, name, type(name, (), {}))


from services.weekly_topic_priority_v35 import accepted_topic_pairs, promote_topics, topic_focused
from services.weekly_adaptive_bridge_v35 import suggested_lesson_focus

ASSIGNMENTS = [
    {'ders': 'Fizik', 'konu': 'Enerji', 'kitap': 'Kaynak A', 'sure': 75},
    {'ders': 'Fizik', 'konu': 'Basınç', 'kitap': 'Kaynak B', 'sure': 40},
    {'ders': 'Fizik', 'konu': 'Enerji ve Güç', 'kitap': 'Kaynak C', 'sure': 30},
    {'ders': 'Kimya', 'konu': 'Enerji', 'kitap': 'Kaynak D', 'sure': 35},
]


def settings():
    return {'planner_version': 2, 'school_by_day': {}, 'blocks': [],
            'wake': '08:00', 'sleep': '22:00', 'max': 180,
            'focus': '', 'weekend_mode': 'Dengeli', 'empty': 'Yok'}


def test_consent_filter_is_lesson_and_topic_exact():
    approved = accepted_topic_pairs(ASSIGNMENTS, [
        {'lesson': 'Fizik', 'topic': 'Enerji'},
        {'lesson': 'Fizik', 'topic': 'Enerji'},
        {'lesson': 'Fizik', 'topic': 'Enerj'},
        {'lesson': 'Matematik', 'topic': 'Enerji'},
        {'lesson': 'Fizik', 'topic': 'ENERJİ VE GÜÇ'},
    ])
    assert approved == [{'lesson':'Fizik','topic':'Enerji'},
                        {'lesson':'Fizik','topic':'ENERJİ VE GÜÇ'}]


def test_turkish_dotted_and_dotless_i_do_not_leak_to_unrelated_topic():
    choices = accepted_topic_pairs(
        [{'ders':'Fizik','konu':'Işık ve Gölge'}],
        [{'lesson':'Fizik','topic':'IŞIK VE GÖLGE'},
         {'lesson':'Fizik','topic':'İşik ve Gölge'}])
    assert choices == [{'lesson':'Fizik','topic':'IŞIK VE GÖLGE'}]


def test_no_approval_no_change_to_original_priority_or_order():
    from services.smart_calendar import SmartCalendarService
    original = SmartCalendarService._normalize_tasks(copy.deepcopy(ASSIGNMENTS))
    snap = [(t.ders,t.konu,t.priority,t.kind,t.sure,t.deadline) for t in original]
    assert promote_topics(original, [], SmartCalendarService._deadline_score) == 0
    assert snap == [(t.ders,t.konu,t.priority,t.kind,t.sure,t.deadline) for t in original]


def test_only_one_topic_not_whole_lesson_or_nearby_topic():
    from services.smart_calendar import SmartCalendarService
    tasks = SmartCalendarService._normalize_tasks(copy.deepcopy(ASSIGNMENTS))
    assert promote_topics(tasks,[{'lesson':'Fizik','topic':'Enerji'}],SmartCalendarService._deadline_score) == 1
    selected = [(t.ders,t.konu) for t in tasks if t.kind == 'konu_odak']
    assert selected == [('Fizik','Enerji')]
    assert all(t.kind != 'konu_odak' for t in tasks if t.konu != 'Enerji' or t.ders != 'Fizik')
    assert sum(t.sure for t in tasks) == 180


def test_exact_original_topic_for_split_sessions():
    from services.smart_calendar import SmartCalendarService
    source=[{'ders':'Fizik','konu':'Enerji','kitap':'A','sure':95},
            {'ders':'Fizik','konu':'Basınç','kitap':'B','sure':45}]
    tasks=SmartCalendarService._normalize_tasks(source,session_minutes=30,session_split=True)
    assert promote_topics(tasks,[{'lesson':'Fizik','topic':'Enerji'}],SmartCalendarService._deadline_score)==4
    focused = [t for t in tasks if t.kind == 'konu_odak']
    assert sum(t.sure for t in focused)==95
    assert sum(t.sure for t in tasks)==140


def test_date_is_primary_even_if_topic_is_preferred():
    from services.smart_calendar import SmartCalendarService
    early=(date.today()+timedelta(days=1)).isoformat()
    late=(date.today()+timedelta(days=5)).isoformat()
    tasks=SmartCalendarService._normalize_tasks([
        {'ders':'Fizik','konu':'Enerji','sure':30,'deadline':late},
        {'ders':'Fizik','konu':'Basınç','sure':30,'deadline':early},
    ])
    promote_topics(tasks,[{'lesson':'Fizik','topic':'Enerji'}],SmartCalendarService._deadline_score)
    assert tasks[0].konu=='Basınç'


def test_plan_opt_in_uses_no_new_homework_and_changes_only_target_priority():
    from services.smart_calendar import SmartCalendarService
    from services.planning_constraints import serialize_details
    assigned=copy.deepcopy(ASSIGNMENTS)
    raw=SmartCalendarService.create_weekly_plan_data('Test',assigned,serialize_details(settings()))
    updated=dict(settings(),adaptive_topic_focus_v35=[{'lesson':'Fizik','topic':'Enerji'}])
    plan=SmartCalendarService.create_weekly_plan_data('Test',assigned,serialize_details(updated))
    def sessions(bundle):
        return bundle['tasks']
    def all_minutes(bundle):
        return (sum(t.sure for day in bundle['days'] for t in day.tasks)
                + sum(t.sure for t in bundle['profile']['unassigned']))
    assert all_minutes(raw)==all_minutes(plan)==180
    assert all(t.kind!='konu_odak' for t in sessions(raw))
    assert {(t.ders,t.konu) for t in sessions(plan) if t.kind=='konu_odak'}=={('Fizik','Enerji')}
    assert assigned == ASSIGNMENTS
    assert all(row.get('priority') is None for row in assigned)
    assert 'Öğretmen onaylı konu önceliği' in plan['html']
    assert 'Fizik / Enerji' in plan['html']
    assert 'Öğretmen onaylı konu önceliği' not in raw['html']


def test_manual_lesson_preference_stays_unmodified_when_topic_focus_added():
    from services.smart_calendar import SmartCalendarService
    from services.planning_constraints import serialize_details
    prefs=dict(settings(),focus='Kimya')
    updated=dict(prefs,adaptive_topic_focus_v35=[{'lesson':'Fizik','topic':'Enerji'}])
    plan=SmartCalendarService.create_weekly_plan_data('Test',ASSIGNMENTS,serialize_details(updated))
    assert updated['focus']=='Kimya' and prefs['focus']=='Kimya'
    assert ('Fizik','Enerji') in [(t.ders,t.konu) for t in plan['tasks'] if t.kind=='konu_odak']
    assert all(t.kind!='konu_odak' for t in plan['tasks'] if t.ders=='Kimya')


def test_invalid_topic_from_other_student_does_not_apply():
    from services.smart_calendar import SmartCalendarService
    from services.planning_constraints import serialize_details
    updated=dict(settings(),adaptive_topic_focus_v35=[{'lesson':'Matematik','topic':'Oran'}])
    bundle=SmartCalendarService.create_weekly_plan_data('Test',ASSIGNMENTS,serialize_details(updated))
    assert all(t.kind!='konu_odak' for t in bundle['tasks'])


def test_old_planner_document_stays_unchanged_and_approval_is_transient():
    from services.planning_constraints import serialize_details,parse_details
    data=settings()
    before=serialize_details(data)
    proposal=[{'lesson':'Fizik','topic':'Enerji'}]
    approved=accepted_topic_pairs(ASSIGNMENTS,proposal)
    payload=dict(data,adaptive_topic_focus_v35=approved)
    assert parse_details(before).get('adaptive_topic_focus_v35') is None
    assert parse_details(serialize_details(payload))['adaptive_topic_focus_v35']==approved
    assert data==settings()
