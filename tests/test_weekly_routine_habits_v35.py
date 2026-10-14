# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from datetime import date
from services.smart_calendar import SmartCalendarService, _Task
from services.planning_constraints import serialize_details


def test_routine_detection_paragraf_and_problem():
    # Detects Paragraf in ders or konu
    assert SmartCalendarService._is_routine_task({'ders': 'Türkçe', 'konu': 'Paragraf Denemesi'}) is True
    assert SmartCalendarService._is_routine_task({'ders': 'PARAGRAF', 'konu': 'Hız Testi'}) is True
    assert SmartCalendarService._is_routine_task({'ders': 'Türkçe', 'konu': 'Cümlede Anlam', 'aciklama': 'Günde 20 soru rutin'}) is True

    # Detects Problemler
    assert SmartCalendarService._is_routine_task({'ders': 'Matematik', 'konu': 'Problemler Rutini'}) is True
    assert SmartCalendarService._is_routine_task({'ders': 'Problemler', 'konu': 'Yaş Problemleri'}) is True

    # Explicit flag
    assert SmartCalendarService._is_routine_task({'ders': 'Geometri', 'konu': 'Üçgenler', 'is_routine': True}) is True

    # Non-routine subjects must return False
    assert SmartCalendarService._is_routine_task({'ders': 'Fizik', 'konu': 'Optik'}) is False
    assert SmartCalendarService._is_routine_task({'ders': 'Kimya', 'konu': 'Gazlar'}) is False
    assert SmartCalendarService._is_routine_task({'ders': 'Tarih', 'konu': 'Osmanlı Tarihi'}) is False


def test_routine_spread_invariants_7_and_5_days():
    # 7-day spread
    hw = [{'ders': 'Türkçe', 'konu': 'Paragraf Rutini', 'sure': 75}]
    spread_7 = SmartCalendarService._spread_routine_tasks(hw, list(range(7)))
    assert len(spread_7) == 7
    assert sum(t['sure'] for t in spread_7) == 75
    assert all(t['is_routine'] is True for t in spread_7)
    assert all(t['sure'] >= 5 for t in spread_7)

    # 5-day spread
    spread_5 = SmartCalendarService._spread_routine_tasks(hw, list(range(5)))
    assert len(spread_5) == 5
    assert sum(t['sure'] for t in spread_5) == 75
    assert all(t['is_routine'] is True for t in spread_5)

    # Small duration (e.g. 15 min) preserves sum and minimum chunk
    hw_small = [{'ders': 'Türkçe', 'konu': 'Paragraf', 'sure': 15}]
    spread_small = SmartCalendarService._spread_routine_tasks(hw_small, list(range(7)))
    assert sum(t['sure'] for t in spread_small) == 15
    assert all(t['sure'] >= 5 for t in spread_small)


def test_weekly_calendar_distribution_7_days():
    hw = [
        {'ders': 'Türkçe', 'konu': 'Paragraf Denemesi', 'kitap': 'Limit Paragraf', 'sure': 75, 'zorluk': 3},
        {'ders': 'Matematik', 'konu': 'Problemler Rutini', 'kitap': 'Apotemi', 'sure': 75, 'zorluk': 3},
    ]
    details = {
        'planner_version': 2,
        'school_by_day': {str(i): ['08:30', '16:00'] for i in range(5)},
        'wake': '07:00',
        'sleep': '23:30',
        'max': 180,
        'routine_spread_enabled': True,
        'routine_spread_days': 7,
        'routine_time_preference': 'after_school'
    }
    res = SmartCalendarService.create_weekly_plan_data('Test Öğrenci', hw, serialize_details(details))
    assert res is not None
    assert len(res['days']) == 7

    total_scheduled = sum(d.total_minutes for d in res['days'])
    assert total_scheduled == 150

    # Every single day must have routine tasks
    for d in res['days']:
        assert d.total_minutes > 0
        routine_tasks = [t for t in d.tasks if t.is_routine]
        assert len(routine_tasks) >= 2


def test_weekly_calendar_distribution_5_weekdays():
    hw = [
        {'ders': 'Türkçe', 'konu': 'Paragraf Rutini', 'sure': 50, 'zorluk': 3},
    ]
    details = {
        'planner_version': 2,
        'school_by_day': {str(i): ['08:30', '16:00'] for i in range(5)},
        'wake': '07:00',
        'sleep': '23:30',
        'max': 180,
        'routine_spread_enabled': True,
        'routine_spread_days': 5,
        'routine_time_preference': 'after_school'
    }
    res = SmartCalendarService.create_weekly_plan_data('Test Öğrenci', hw, serialize_details(details))
    assert res is not None
    assert sum(d.total_minutes for d in res['days']) == 50

    # Weekend days should NOT receive the 5-day routine
    for d in res['days']:
        if d.date_.weekday() in (5, 6):
            routine_tasks = [t for t in d.tasks if t.is_routine]
            assert len(routine_tasks) == 0


def test_routine_card_html_styling():
    hw = [
        {'ders': 'Türkçe', 'konu': 'Paragraf Denemesi', 'sure': 75},
    ]
    details = {
        'planner_version': 2,
        'wake': '07:00',
        'sleep': '23:30',
        'max': 180,
        'routine_spread_enabled': True,
    }
    res = SmartCalendarService.create_weekly_plan_data('Test Öğrenci', hw, serialize_details(details))
    assert res is not None
    html = res['html']

    # HTML contains emerald styling and badge
    assert '🎯 RUTİN' in html
    assert '#059669' in html
    assert '#ecfdf5' in html


def test_routine_spread_opt_out():
    hw = [
        {'ders': 'Türkçe', 'konu': 'Paragraf Denemesi', 'sure': 75},
    ]
    details = {
        'planner_version': 2,
        'wake': '07:00',
        'sleep': '23:30',
        'max': 180,
        'routine_spread_enabled': False,
    }
    res = SmartCalendarService.create_weekly_plan_data('Test Öğrenci', hw, serialize_details(details))
    assert res is not None
    assert sum(d.total_minutes for d in res['days']) == 75

    # Should remain as a single unsplit block
    total_tasks = sum(len(d.tasks) for d in res['days'])
    assert total_tasks == 1
