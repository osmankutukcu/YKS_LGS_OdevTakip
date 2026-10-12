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


def test_plan_profiles_path_safety(monkeypatch, tmp_path):
    from ui.plan_settings_dialog import get_profiles_file_path
    from pathlib import Path
    
    # Path returned should be a Path object ending in plan_profiles.json
    path = get_profiles_file_path()
    assert isinstance(path, Path)
    assert path.name == "plan_profiles.json"
    # Ensure parent dir exists or is writable
    assert path.parent.exists()


def test_plan_settings_dialog_flags():
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication
    from ui.plan_settings_dialog import PlanSettingsDialog
    from PyQt6.QtCore import Qt
    
    app = QApplication.instance() or QApplication([])
    dlg = PlanSettingsDialog(lesson_names=["Fizik", "Matematik"], student_name="Ali Veli")
    flags = dlg.windowFlags()
    # Check maximize button hint is enabled for low-res monitors
    assert bool(flags & Qt.WindowType.WindowMaximizeButtonHint) is True
    # Check minimum size is responsive
    assert dlg.minimumWidth() <= 500
    assert dlg.minimumHeight() <= 400


def test_weekly_plan_landscape_and_single_page_capacity():
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtPrintSupport import QPrinter
    from PyQt6.QtGui import QTextDocument, QPageSize, QPageLayout
    from PyQt6.QtCore import QMarginsF
    
    app = QApplication.instance() or QApplication([])
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape)
    printer.setPageMargins(QMarginsF(5, 5, 5, 5), QPageLayout.Unit.Millimeter)

    hw = [
        {"ders": "LGS Matematik", "konu": "Eşlik ve Benzerlik", "kitap": "3D", "sure": 75, "zorluk": 4},
        {"ders": "LGS Fen", "konu": "Mevsimler", "kitap": "Fen Kaynak", "sure": 45, "zorluk": 3},
        {"ders": "LGS Türkçe", "konu": "Fiilimsiler", "kitap": "Türkçe", "sure": 40, "zorluk": 2},
    ]
    html = SmartCalendarService.create_weekly_plan_pdf("ALİ VELİ", hw, {"max": 180, "school": "08:30 - 15:40"})
    
    assert "@page { size: A4 landscape;" in html
    
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
    doc.setHtml(html)
    assert doc.pageCount() == 1


def test_suggest_time_window_uses_actual_appointments():
    from services.smart_calendar import _DayPlan, _Task
    from datetime import date
    import json

    # 1. Day with actual appointments
    task1 = _Task(raw={}, ders="Matematik", konu="Fonksiyonlar", sure=60, zorluk=3, priority=3, deadline=None, kitap="")
    task2 = _Task(raw={}, ders="Fizik", konu="Kuvvet", sure=45, zorluk=3, priority=3, deadline=None, kitap="")
    day = _DayPlan(
        label="Cumartesi",
        date_=date(2026, 10, 17),
        tasks=[task1, task2],
        is_school_day=False,
        day_cap=180,
        day_target=105,
        windows=[(840, 1080)],  # 14:00 - 18:00
        appointments=[(task1, 840, 900), (task2, 910, 955)]  # 14:00-15:00, 15:10-15:55
    )
    window_text = SmartCalendarService._suggest_time_window(day)
    # The merged study window should show 14:00 - 15:55
    assert window_text == "14:00 – 15:55"

    # 2. End-to-end plan generation with blocked weekend hours
    hw = [
        {"ders": "Matematik", "konu": f"Konu {i}", "sure": 120, "soru_sayisi": 30}
        for i in range(7)
    ]
    profile_data = {
        "planner_version": 2,
        "school_by_day": {"0": ["08:30", "15:40"], "1": ["08:30", "15:40"], "2": ["08:30", "15:40"], "3": ["08:30", "15:40"], "4": ["08:30", "15:40"]},
        "after_school_buffer": 30,
        "wake": "07:00",
        "sleep": "23:30",
        "max": 180,
        "blocks": ["Cumartesi [11:00-13:00] Kurs", "Pazar [11:00-13:00] Kurs"]
    }
    details_str = "PLANNER_V2_JSON:" + json.dumps(profile_data)
    res = SmartCalendarService.create_weekly_plan_data("Test Öğrenci", hw, details_str)
    
    # Check that Saturday and Sunday header does NOT display the blocked 11:00-13:15
    for d in res["days"]:
        if d.date_.weekday() in (5, 6) and d.appointments:
            win = SmartCalendarService._suggest_time_window(d, res["profile"])
            assert "11:00" not in win, f"Blocked hour appeared in window: {win}"


