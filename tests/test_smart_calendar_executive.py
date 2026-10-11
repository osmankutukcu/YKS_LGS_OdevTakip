# -*- coding: utf-8 -*-
import json
import pytest
from services.smart_calendar import SmartCalendarService, _Task


def test_task_splitting_integrity():
    # 75-minute tasks must NEVER be split into small fragments (no 3-minute chunks!)
    t75 = _Task(
        raw={}, ders="Fizik", konu="Su Dalgaları", kitap="3D Fizik",
        sure=75, zorluk=4, priority=3, splitable=True
    )
    parts = SmartCalendarService._split_task_if_needed(t75)
    assert len(parts) == 1
    assert parts[0].sure == 75
    assert "(1/3)" not in parts[0].konu

    # 120-minute task must also stay whole
    t120 = _Task(
        raw={}, ders="Matematik", konu="Türev", kitap="Orijinal",
        sure=120, zorluk=5, priority=4, splitable=True
    )
    parts120 = SmartCalendarService._split_task_if_needed(t120)
    assert len(parts120) == 1
    assert parts120[0].sure == 120

    # > 120 minute task splits into 2 balanced halves
    t180 = _Task(
        raw={}, ders="Genel Deneme", konu="TYT Deneme", kitap="Özdebir",
        sure=180, zorluk=5, priority=5, splitable=True
    )
    parts180 = SmartCalendarService._split_task_if_needed(t180)
    assert len(parts180) == 2
    assert parts180[0].sure == 90
    assert parts180[1].sure == 90
    assert "(1/2)" in parts180[0].konu
    assert "(2/2)" in parts180[1].konu


def test_profile_extraction_no_inverted_school_days():
    data = {
        "profile_idx": 0,
        "student_type": "Okula Gidiyor (Standart Hafta İçi)",
        "school": "08:30 - 15:40",
        "max": 180,
        "weekend_mode": "Dengeli",
        "biorhythm": "Standart Dengeli Dağılım",
        "blocks": ["Cumartesi [08:00-16:00] Yoğun", "Pazar [08:00-16:00] Yoğun"],
        "focus": "Fizik",
        "empty": "Yok",
        "note": ""
    }
    details = json.dumps(data, ensure_ascii=False)
    tasks = SmartCalendarService._normalize_tasks([
        {"ders": "Fizik", "konu": "Su Dalgaları", "sure": 75}
    ])
    prof = SmartCalendarService._extract_profile(details, [], tasks)

    # School days must be Monday-Friday (0..4), NEVER Saturday (5) or Sunday (6)
    assert prof["school_days"] == {0, 1, 2, 3, 4}
    assert 5 not in prof["school_days"]
    assert 6 not in prof["school_days"]

    # Routines must map to Saturday (5) and Sunday (6)
    assert len(prof["routines_by_day"][5]) == 1
    assert prof["routines_by_day"][5][0][:2] == (480, 960) # 08:00 - 16:00
    assert len(prof["routines_by_day"][6]) == 1
    assert prof["routines_by_day"][6][0][:2] == (480, 960)


def test_substring_trap_cumartesi_not_matched_as_cuma():
    details = "!!! ZORUNLU ENGEL !!!: Cumartesi [09:00-12:00] Kurs"
    prof = SmartCalendarService._extract_profile(details, [], [])
    # Cumartesi is day 5, Cuma is day 4
    assert len(prof["routines_by_day"][5]) == 1
    assert len(prof["routines_by_day"][4]) == 0


def test_user_scenario_distribution_and_study_windows():
    data = {
        "profile_idx": 0,
        "student_type": "Okula Gidiyor (Standart Hafta İçi)",
        "school": "08:30 - 15:40",
        "max": 180,
        "weekend_mode": "Dengeli",
        "biorhythm": "Standart Dengeli Dağılım",
        "blocks": ["Cumartesi [08:00-16:00] Yoğun", "Pazar [08:00-16:00] Yoğun"],
        "focus": "Fizik",
        "empty": "Yok",
        "note": ""
    }
    details = json.dumps(data, ensure_ascii=False)
    hw = [
        {"ders": "Fizik", "konu": "Su Dalgaları", "kitap": "3D Fizik", "sure": 75, "zorluk": 4},
        {"ders": "Fizik", "konu": "Ses ve Deprem Dalgaları", "kitap": "3D Fizik", "sure": 75, "zorluk": 3}
    ]

    html = SmartCalendarService.create_weekly_plan_pdf("Test Öğrenci", hw, details)
    assert html is not None

    # Verify no task fragmentation
    assert "(1/3)" not in html
    assert "(3/3)" not in html

    # Verify header metadata
    assert "Hafta İçi (08:30 - 15:40)" in html
    assert "Cmt [08:00-16:00]" in html
    assert "Okul Günleri: Cmt, Paz" not in html

    # Verify weekend days were not assigned study in the middle of routine
    assert "11:00–14:00" not in html


def test_holiday_day_zero_capacity():
    data = {
        "profile_idx": 0,
        "student_type": "Okula Gidiyor",
        "school": "08:30 - 15:40",
        "max": 180,
        "empty": "Pazar",
        "blocks": [],
        "note": ""
    }
    details = json.dumps(data, ensure_ascii=False)
    prof = SmartCalendarService._extract_profile(details, [], [])
    assert 6 in prof["holiday_days"]

    days = SmartCalendarService._build_days(prof)
    sunday = [d for d in days if d.date_.weekday() == 6][0]
    assert sunday.is_holiday is True
    assert sunday.day_cap == 0

    window = SmartCalendarService._suggest_time_window(sunday, prof)
    assert "Tatil" in window
