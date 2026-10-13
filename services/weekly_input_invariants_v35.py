"""Strict, read-only source checks for weekly-calendar homework inputs.

The classic assignment table already validates minutes.  This separate boundary
protects callers such as future coaching modules from quietly dropping an
invalid task or changing its duration during scheduler normalization.
No DB, GUI, student profile, or assignment state is touched.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _deadline(value: Any) -> date | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError('Ödevin son teslim tarihi geçersiz.')
    text = value.strip()
    if not text:
        return None
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).date()
    except ValueError:
        raise ValueError('Ödevin son teslim tarihi geçersiz.') from None


def validate_homework_source(homework_list: list[dict[str, Any]]) -> dict[str, int]:
    """Fail before scheduling on missing tasks, bad durations, or bad dates.

    Return non-personal aggregate counts for the existing plan validator.
    """
    if not isinstance(homework_list, list):
        raise ValueError('Verilen ödevler listesi geçersiz.')
    total = 0
    for idx, task in enumerate(homework_list, 1):
        if not isinstance(task, dict):
            raise ValueError(f'{idx}. ödevin verisi geçersiz.')
        if not str(task.get('ders') or '').strip() or not str(task.get('konu') or '').strip():
            raise ValueError(f'{idx}. ödevde ders veya konu eksik.')
        duration = task.get('sure')
        # int accepts bool, and int('30.5') rounds nowhere; reject both rather
        # than creating a plausible-looking but incorrect weekly PDF.
        if isinstance(duration, bool) or not isinstance(duration, (int, str)):
            raise ValueError(f'{idx}. ödevin süresi geçersiz.')
        if isinstance(duration, str) and not duration.strip().isdecimal():
            raise ValueError(f'{idx}. ödevin süresi geçersiz.')
        minutes = int(duration)
        if not 5 <= minutes <= 600:
            raise ValueError(f'{idx}. ödevin süresi 5–600 dakika arasında olmalı.')
        total += minutes
        for key in ('deadline', 'bitis', 'bitis_tarihi'):
            if task.get(key) not in (None, ''):
                _deadline(task[key])
    return {'task_count': len(homework_list), 'minutes': total}
