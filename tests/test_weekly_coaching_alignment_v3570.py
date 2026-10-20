"""V3570 alignment of existing scientific coaching with established weekly planner."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import pytest

from services.weekly_coaching_alignment_v3570 import align_coaching_to_existing_week
from services.weekly_topic_priority_v35 import accepted_topic_pairs
from tests.test_coaching_navigation_v3568 import valid_cycle

DAY = date(2026, 10, 20)
SID = 14
HOMEWORK = [
    {'ders':'Matematik','konu':'Polinomlar','kitap':'AYT1','sure':45},
    {'ders':'Fizik','konu':'Dalgalar','kitap':'Fizik1','sure':75},
]


def action(kind='TARGETED_REVIEW', lesson='Matematik', topic='Polinomlar'):
    a=deepcopy(valid_cycle()['next_actions'][0]);a.update(kind=kind,lesson=lesson,topic=topic)
    return a


def build(actions=None, homework=None, overrides=None):
    c=valid_cycle()
    c['next_actions']=[action()] if actions is None else actions
    c['state']='ACTION_SUGGESTED' if c['next_actions'] else 'NO_PRIORITY'
    c.update(overrides or {})
    return align_coaching_to_existing_week(c,SID,HOMEWORK if homework is None else homework,today=DAY)


def test_only_verified_existing_homework_topic_can_be_proposed():
    r=build()
    assert r['state']=='REVIEW_AVAILABLE'
    assert r['focus_candidates']==[{'lesson':'Matematik','topic':'Polinomlar'}]
    assert r['measurement_notes']==[]
    assert r['read_only'] and r['teacher_approval_required']
    assert not r['auto_assignment'] and not r['auto_pdf_change']


def test_unassigned_or_substring_topics_cannot_be_promoted():
    r=build([action(topic='Polinom')])
    assert r['state']=='NO_ACTION' and not r['focus_candidates']
    r=build([action(lesson='Kimya',topic='Polinomlar')])
    assert r['state']=='NO_ACTION'


@pytest.mark.parametrize('kind', [
    'INTERVENTION_FOLLOWUP','SPACED_RETRIEVAL','INDEPENDENT_RECHECK',
    'CLARIFY_OBSERVATION','OPTIONAL_INDEPENDENT_CHECK'])
def test_measurements_never_become_homework_priorities(kind):
    r=build([action(kind=kind)])
    assert r['focus_candidates']==[]
    assert r['measurement_notes'] and r['auto_calendar_write'] is False


def test_aggregate_optional_check_never_fabricates_topic():
    r=build([action(kind='OPTIONAL_INDEPENDENT_CHECK',lesson='',topic='')])
    assert r['state']=='NO_ACTION'


def test_measurement_outside_given_homework_not_in_weekly_plan():
    r=build([action(kind='INTERVENTION_FOLLOWUP',lesson='Kimya',topic='Mol')])
    assert r['state']=='NO_ACTION' and not r['measurement_notes']


def test_confirmed_targeted_review_and_followup_separated():
    r=build([action(),action(kind='INTERVENTION_FOLLOWUP',lesson='Fizik',topic='Dalgalar')])
    assert len(r['focus_candidates'])==1 and len(r['measurement_notes'])==1
    assert r['measurement_notes'][0]['lesson']=='Fizik'


@pytest.mark.parametrize('patch',[
    {'student_id':99}, {'student_id': '14'}, {'as_of':'2026-10-19'},
    {'automatic_assignments': True}, {'automatic_messages': True},
    {'mastery_verified': True}, {'teacher_approval_required': False},
    {'state': 'DATA_REVIEW'}, {'read_only':False},
])
def test_wrong_ownership_date_or_unsafe_claims_fail_closed(patch):
    r=build(overrides=patch)
    assert r['state']=='DATA_REVIEW'
    assert not r['focus_candidates'] and not r['measurement_notes']


def test_corrupt_action_fails_closed_not_partial_approval():
    for patch in ({'auto_assignment':True}, {'read_only':False},
                  {'kind':'AUTO_ADD'}, {'mastery_verified':True}, {'topic':' '*150}):
        good=action();bad=action(lesson='Fizik',topic='Dalgalar');bad.update(patch)
        r=build([good,bad])
        assert r['state']=='DATA_REVIEW' and not r['focus_candidates']


def test_invalid_inputs_rejected():
    for sid in (True, '14', 0, -1):
        with pytest.raises(ValueError):
            align_coaching_to_existing_week(valid_cycle(),sid,HOMEWORK,today=DAY)
    with pytest.raises(ValueError):
        align_coaching_to_existing_week(valid_cycle(),SID,HOMEWORK,today='2026-10-20')
    assert build(homework=None)['read_only']
    assert build(homework='oops')['state']=='DATA_REVIEW'


def test_no_mutation_no_db_no_qt_no_pdf_renderer_change():
    cycle=valid_cycle();home=deepcopy(HOMEWORK)
    before=deepcopy(cycle)
    align_coaching_to_existing_week(cycle,SID,home,today=DAY)
    assert cycle==before and home==HOMEWORK
    root=Path(__file__).resolve().parents[1]
    code=(root/'services/weekly_coaching_alignment_v3570.py').read_text('utf8')
    for bad in ('INSERT INTO','UPDATE odev','DELETE FROM','con.commit','QPushButton','QPrinter'):
        assert bad not in code
    bridge=(root/'ui/weekly_planner_adaptive_bridge_v35.py').read_text('utf8')
    assert 'align_coaching_to_existing_week(' in bridge
    assert 'teacher_approval_required' in code
    assert (root/'services/smart_calendar.py').exists()


def test_known_plan_approved_topic_mechanism_reused():
    from services.planning_constraints import serialize_details
    from services.smart_calendar import SmartCalendarService
    settings={'planner_version':2,'school_by_day':{},'blocks':[],
              'wake':'07:00','sleep':'23:00','max':180,'empty':'Yok',
              'focus':'Kimya','weekend_mode':'Dengeli'}
    base=SmartCalendarService.create_weekly_plan_data('Örnek Öğrenci',HOMEWORK,serialize_details(settings))
    selected=accepted_topic_pairs(HOMEWORK,build()['focus_candidates'])
    with_focus=SmartCalendarService.create_weekly_plan_data('Örnek Öğrenci',HOMEWORK,
                     serialize_details({**settings, 'adaptive_topic_focus_v35':selected}))
    def planned(b):
        return sum(t.sure for d in b['days'] for t in d.tasks)+sum(t.sure for t in b['profile']['unassigned'])
    assert planned(base)==planned(with_focus)==120
    assert HOMEWORK[0]['sure']==45
