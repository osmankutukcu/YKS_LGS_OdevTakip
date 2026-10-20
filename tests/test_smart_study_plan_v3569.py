"""V3569 synthetic, read-only planning contract. No personal data or Qt."""
from datetime import date, timedelta
from copy import deepcopy
from pathlib import Path
import hashlib

import pytest

from tests.test_coaching_navigation_v3568 import valid_cycle, valid_alignment
from services.smart_study_plan_v3569 import build_smart_study_plan, compact_study_plan_hint

DAY = date(2026,10,20)
SID = 14


def plan(cycle=None, align=None, **kw):
    c=valid_cycle() if cycle is None else cycle
    a=valid_alignment() if align is None else align
    a=deepcopy(a)
    a['suggested_minutes']=20
    a['overload_limited']=False
    return build_smart_study_plan(c,a,SID,today=DAY,**kw)


def test_matching_real_wizard_book_without_inventing_calendar_or_assignment():
    x=plan()
    assert x['state']=='REVIEW_SUGGESTED'
    s=x['planning_steps'][0]
    assert s['kind']=='WIZARD_PREVIEW' and s['existing_book']=='AYT 1'
    assert s['candidate_minutes']==20 and s['capacity_status']=='UNKNOWN'
    assert not s['scheduled'] and not x['calendar_verified']
    assert x['auto_assignment'] is False and x['auto_calendar_write'] is False
    assert x['unallocated_minutes_verified'] is False
    assert 'Takvime uygunluk doğrulanmadı' in compact_study_plan_hint(
        x,SID,today=DAY,expected_lesson='Matematik',expected_topic='Polinomlar')


def test_verified_budget_must_be_explicit_and_never_treated_as_clock_slot():
    x=plan(verified_unallocated_minutes=20)
    assert x['planning_steps'][0]['capacity_status']=='VERIFIED_BUDGET_FITS'
    assert x['planning_steps'][0]['scheduled'] is False
    assert x['calendar_verified'] is False
    y=plan(verified_unallocated_minutes=19)
    assert y['planning_steps'][0]['kind']=='LEARNING_REVIEW'
    assert y['planning_steps'][0]['capacity_status']=='INSUFFICIENT'
    assert y['candidate_minutes']==0


def test_overload_blocks_extra_wizard_work_even_if_budget_available():
    a=valid_alignment();a['suggested_minutes']=20;a['overload_limited']=True
    x=build_smart_study_plan(valid_cycle(),a,SID,today=DAY,verified_unallocated_minutes=200)
    assert x['planning_steps'][0]['kind']=='LEARNING_REVIEW'
    assert x['planning_steps'][0]['capacity_status']=='OVERLOAD_REVIEW'


def test_wrong_student_day_or_unsafe_cycle_never_produces_plan():
    for patch in ({'student_id':15},{'as_of':'2026-10-19'},
                  {'automatic_assignments':True},{'mastery_verified':True},
                  {'teacher_approval_required':False}):
        x=plan(cycle={**valid_cycle(),**patch})
        assert x['state']=='DATA_REVIEW' and not x['planning_steps']
    for patch in ({'student_id':15},{'as_of':'2026-10-19'},
                  {'auto_assignment':True},{'auto_selection':True}):
        a=valid_alignment();a.update(patch)
        x=plan(align=a)
        assert x['state']=='DATA_REVIEW' and x['candidate_minutes']==0


def test_tampered_match_invalidates_entire_plan():
    for change in ({'automatic_transfer':True}, {'teacher_must_review_in_existing_wizard':False},
                   {'minutes':True}, {'existing_book':''}, {'minutes':200}):
        a=valid_alignment();a['matched'][0].update(change)
        x=plan(align=a)
        assert x['state']=='DATA_REVIEW' and not x['planning_steps']
    a=valid_alignment();a['suggested_minutes']=400
    # Explicit helper below does not overwrite the forged total.
    x=build_smart_study_plan(valid_cycle(),a,SID,today=DAY)
    assert x['state']=='DATA_REVIEW'


def test_missing_wizard_allowed_for_learning_only_without_invented_book():
    x=build_smart_study_plan(valid_cycle(),None,SID,today=DAY)
    assert x['state']=='REVIEW_SUGGESTED'
    assert x['planning_steps'][0]['kind']=='LEARNING_REVIEW'
    assert x['planning_steps'][0]['existing_book']==''
    assert x['candidate_minutes']==0


def test_followup_priority_not_promoted_into_new_homework():
    c=valid_cycle()
    c['next_actions'][0]['kind']='INTERVENTION_FOLLOWUP'
    x=plan(cycle=c,verified_unallocated_minutes=1000)
    assert x['planning_steps'][0]['kind']=='LEARNING_REVIEW'
    assert x['planning_steps'][0]['source_kind']=='INTERVENTION_FOLLOWUP'


def test_no_action_is_not_proven_learning():
    c=valid_cycle();c['next_actions']=[];c['state']='NO_PRIORITY'
    x=plan(cycle=c)
    assert x['state']=='NO_PRIORITY' and not x['planning_steps']
    assert x['mastery_verified'] is False


def test_missing_capacity_rejected_bad_inputs():
    for invalid in (-1,10081,True,'60',0.5):
        with pytest.raises(ValueError):
            plan(verified_unallocated_minutes=invalid)
    for invalid in (True,0,'14',-1):
        with pytest.raises(ValueError):
            build_smart_study_plan(valid_cycle(),valid_alignment(),invalid,today=DAY)
    with pytest.raises(ValueError):
        build_smart_study_plan(valid_cycle(),valid_alignment(),SID,today='2026-10-20')


def test_stale_or_mismatched_plan_suppressed_in_existing_assistant():
    x=plan()
    assert compact_study_plan_hint(x,15,today=DAY)==''
    assert compact_study_plan_hint(x,SID,today=DAY+timedelta(days=1))==''
    assert compact_study_plan_hint(x,SID,today=DAY,expected_lesson='Fizik',expected_topic='Polinomlar')==''
    x['auto_message']=True
    assert compact_study_plan_hint(x,SID,today=DAY,expected_lesson='Matematik',expected_topic='Polinomlar')==''


def test_source_readonly_and_protected_core_untouched():
    root=Path(__file__).resolve().parents[1]
    code=(root/'services/smart_study_plan_v3569.py').read_text('utf-8')
    for banned in ('INSERT INTO', 'UPDATE odev', 'DELETE FROM', 'con.commit(', '.click()', 'QTimer('):
        assert banned not in code
    adapter=(root/'ui/research_coaching_bridge_v3563.py').read_text('utf-8')
    assert 'build_smart_study_plan(' in adapter
    assert 'compact_study_plan_hint(' in adapter
    assert 'smart_study_plan_v3569_enabled' in adapter
    assert 'verified_unallocated_minutes=' not in adapter  # unknown time, not invented
    for rel in ('ui/homework_form.py','ui/odev_kontrol.py','ui/smart_coach_secretary_toast.py'):
        assert 'smart_study_plan_v3569' not in (root/rel).read_text('utf-8')


def test_multiple_ranked_actions_respect_confirmed_weekly_capacity():
    c=valid_cycle()
    second=deepcopy(c['next_actions'][0]); second['topic']='Fonksiyonlar';second['priority']=2
    c['next_actions'].append(second)
    a=valid_alignment()
    a['matched'].append({**a['matched'][0], 'topic':'Fonksiyonlar', 'minutes':25})
    a['suggested_minutes']=45;a['overload_limited']=False
    x=build_smart_study_plan(c,a,SID,today=DAY,verified_unallocated_minutes=30)
    assert [t['kind'] for t in x['planning_steps']]==['WIZARD_PREVIEW','LEARNING_REVIEW']
    assert x['planning_steps'][1]['capacity_status']=='INSUFFICIENT'
    assert x['candidate_minutes']==20


def test_duplicate_topic_or_negative_tamper_fail_closed():
    c=valid_cycle(); a=valid_alignment();a['suggested_minutes']=20;a['overload_limited']=False
    a['matched'].append(deepcopy(a['matched'][0]))
    assert build_smart_study_plan(c,a,SID,today=DAY)['state']=='DATA_REVIEW'
    a['matched'][1]['topic']='Fonksiyonlar'
    assert build_smart_study_plan(c,a,SID,today=DAY)['state']=='DATA_REVIEW'  # total mismatch


def test_pure_function_does_not_mutate_input_records():
    c,a=valid_cycle(),valid_alignment();a['suggested_minutes']=20;a['overload_limited']=False
    before=(deepcopy(c),deepcopy(a))
    build_smart_study_plan(c,a,SID,today=DAY)
    assert (c,a)==before
