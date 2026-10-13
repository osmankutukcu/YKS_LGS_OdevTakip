"""Read-only safety audit for the existing weekly calendar output.

Does not write assignments, dates, checkbox states or student records.
Return localized errors only when generated appointments violate constraints;
unassigned tasks are legitimate and already reported in the PDF preview.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def validate_weekly_plan(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profile = bundle.get('profile') or {}
    tasks = bundle.get('tasks') or []
    days = bundle.get('days') or []
    unassigned = profile.get('unassigned') or []
    source_summary = bundle.get('input_summary')
    if source_summary is not None:
        if sum(t.sure for t in tasks) != source_summary['minutes']:
            errors.append('Ödevlerin toplam süresi, Verilen Ödevler tablosuyla eşleşmiyor.')
    all_expected = Counter(id(task) for task in tasks)
    all_seen = Counter(id(task) for task in unassigned)
    strict_clock = profile.get('availability_by_day') is not None

    for day in days:
        label = day.date_.strftime('%d.%m.%Y')
        all_seen.update(id(task) for task in day.tasks)
        if day.total_minutes > day.day_cap:
            errors.append(f'{label}: günlük çalışma sınırı aşıldı.')
        for task in day.tasks:
            if task.deadline is not None and day.date_ > task.deadline:
                errors.append(f'{label}: {task.konu} teslim tarihinden sonraya yerleştirildi.')
        if not strict_clock:
            continue
        windows = day.windows
        if len(day.appointments) != len(day.tasks):
            errors.append(f'{label}: yerleştirilmiş ödevin saat bilgisi eksik.')
        apt_tasks = Counter(id(task) for task, _, _ in day.appointments)
        if apt_tasks != Counter(id(task) for task in day.tasks):
            errors.append(f'{label}: saat tablosuyla ödev listesi eşleşmiyor.')
        previous_end = None
        for task, start, end in sorted(day.appointments, key=lambda a: a[1]):
            if end - start != task.sure:
                errors.append(f'{label}: {task.konu} için süre yanlış.')
            if not any(a <= start and end <= b for a, b in windows):
                errors.append(f'{label}: {task.konu} okul veya rutin saatine taşmış.')
            if previous_end is not None and start < previous_end:
                errors.append(f'{label}: iki ödev aynı saate yerleştirilmiş.')
            previous_end = end
    if all_seen != all_expected:
        errors.append('Planlanan ve planlanamayan ödevlerin toplamı, verilen ödevlerle eşleşmiyor.')
    return errors
