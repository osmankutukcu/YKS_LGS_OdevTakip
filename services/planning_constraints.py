"""Deterministic calendar constraint helpers. No Qt/database dependencies.

Times are minutes from local midnight. Intervals are half-open [start, end).
Unknown/invalid rules fail closed at the UI validation boundary, rather than
silently creating apparently available time.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

DAYS = ('Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar')
MARKER = 'PLANNER_V2_JSON:'
TIME_RX = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')
BLOCK_RX = re.compile(r'^(.+?)\s*\[\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*\]\s*(.*)$')


def to_minutes(value: str) -> int:
    match = TIME_RX.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f'Geçersiz saat: {value!r}')
    return int(match.group(1)) * 60 + int(match.group(2))


def hhmm(value: int) -> str:
    return f'{value // 60:02d}:{value % 60:02d}'


def merge_intervals(intervals: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    merged: List[Tuple[int, int]] = []
    for start, end in sorted(intervals):
        if end <= start:
            raise ValueError('Bitiş saati başlangıçtan sonra olmalıdır.')
        if not 0 <= start <= 1440 or not 0 <= end <= 1440:
            raise ValueError('Saatler bir gün içinde olmalıdır.')
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def subtract_intervals(base: Tuple[int, int], busy: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    left, right = base
    if left >= right:
        return []
    segments = []
    for s, e in merge_intervals((max(left, s), min(right, e)) for s, e in busy if s < right and e > left):
        if left < s:
            segments.append((left, s))
        left = max(left, e)
    if left < right:
        segments.append((left, right))
    return segments


def block_days(label: str) -> List[int]:
    label = unicodedata.normalize('NFC', str(label).strip().translate(str.maketrans({'İ':'i','I':'ı'})).lower())
    if label in ('her gün', 'hergun', 'hergun '):
        return list(range(7))
    if label in ('hafta içi', 'hafta içi her gün', 'hafta ici her gun'):
        return list(range(5))
    if label in ('hafta sonu', 'hafta sonu her gün', 'hafta sonu her gun'):
        return [5, 6]
    for i, name in enumerate(DAYS):
        if label == name.casefold():
            return [i]
    raise ValueError(f'Bilinmeyen gün seçimi: {label!r}')


def parse_block(rule: str) -> Tuple[List[int], int, int, str]:
    m = BLOCK_RX.fullmatch(str(rule).strip())
    if not m:
        raise ValueError(f'Geçersiz rutin biçimi: {rule!r}')
    start, end = to_minutes(m.group(2)), to_minutes(m.group(3))
    if start >= end:
        raise ValueError('Rutin bitişi başlangıcından sonra olmalıdır.')
    return block_days(m.group(1)), start, end, m.group(4).strip()


def parse_details(details: Any) -> Optional[Dict[str, Any]]:
    if isinstance(details, dict):
        return details if details.get('planner_version') == 2 else None
    if not isinstance(details, str) or MARKER not in details:
        return None
    token = details.split(MARKER, 1)[1].strip()
    data, _ = json.JSONDecoder().raw_decode(token)
    if not isinstance(data, dict) or data.get('planner_version') != 2:
        raise ValueError('Planlayıcı profil sürümü geçersiz.')
    return data


def serialize_details(data: Dict[str, Any]) -> str:
    body = dict(data)
    body['planner_version'] = 2
    return MARKER + json.dumps(body, ensure_ascii=False, separators=(',', ':'))


def availability_for_week(data: Dict[str, Any]) -> Dict[int, List[Tuple[int, int]]]:
    wake = to_minutes(data.get('wake', '07:00'))
    sleep = to_minutes(data.get('sleep', '23:30'))
    if not 0 <= wake < sleep <= 1440:
        raise ValueError('Uyanma saati yatma saatinden önce olmalıdır.')
    # Personal rest/travel buffers apply as fixed busy blocks set by the user.
    busy = {i: [] for i in range(7)}
    by_day = data.get('school_by_day', {}) or {}
    if not isinstance(by_day, dict):
        raise ValueError('Okul saatleri geçersiz.')
    school_buffer = max(0, min(180, int(data.get('after_school_buffer', 0))))
    for day_str, pair in by_day.items():
        day = int(day_str)
        if day not in range(7):
            raise ValueError('Okul günü geçersiz.')
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError('Okul başlangıç/bitiş saatleri geçersiz.')
        a, b = to_minutes(pair[0]), to_minutes(pair[1])
        if a >= b:
            raise ValueError('Okul bitiş saati başlangıçtan sonra olmalıdır.')
        busy[day].append((a, b))
        if school_buffer and b < 1440:
            busy[day].append((b, min(1440, b + school_buffer)))
    # Optional commute/recovery time after lessons, courses and other fixed
    # commitments. A missing setting means zero: old saved profiles retain
    # their original scheduling behavior.
    routine_buffer = int(data.get('after_routine_buffer', 0))
    if not 0 <= routine_buffer <= 180:
        raise ValueError('Sabit rutin sonrası geçiş süresi 0–180 dakika arasında olmalıdır.')
    for block in data.get('blocks', []) or []:
        days, a, b, _ = parse_block(block)
        for day in days:
            busy[day].append((a, min(1440, b + routine_buffer)))
    day_overrides = data.get('day_overrides') or {}
    if not isinstance(day_overrides, dict):
        raise ValueError('Günlük serbest zaman tanımları geçersiz.')
    advanced = data.get('advanced_days') or {}
    if not isinstance(advanced, dict):
        raise ValueError('İnce ayarların gün kayıtları geçersiz.')
    enabled = bool(data.get('advanced_enabled', False))
    for day_key in advanced:
        if str(day_key) not in {str(d) for d in range(7)}:
            raise ValueError(f'Tanımsız ince ayar günü: {day_key!r}')
    result = {}
    for day, intervals in busy.items():
        rule = advanced.get(str(day)) if enabled else None
        if rule is not None:
            if not isinstance(rule, dict):
                raise ValueError(f'{DAYS[day]}: İnce ayarların biçimi geçersiz.')
            real_wake = to_minutes(rule.get('wake', data.get('wake', '07:00')))
            real_bed = to_minutes(rule.get('bed', data.get('sleep', '23:30')))
            if real_bed <= real_wake:
                raise ValueError(f'{DAYS[day]}: yatış saati uyanmadan sonra, aynı gün içinde olmalı.')
            start = to_minutes(rule.get('study_start', hhmm(real_wake)))
            end = to_minutes(rule.get('study_end', hhmm(real_bed)))
            if not real_wake <= start < end <= real_bed:
                raise ValueError(f'{DAYS[day]}: 1. çalışma aralığı uyanma/yatış sınırlarının içinde olmalı.')
            study_windows = [(start, end)]
            second = rule.get('second_window')
            if second is not None:
                if not isinstance(second, (tuple, list)) or len(second) != 2:
                    raise ValueError(f'{DAYS[day]}: 2. çalışma dilimi iki saatten oluşmalı.')
                second_start, second_end = to_minutes(second[0]), to_minutes(second[1])
                if not real_wake <= second_start < second_end <= real_bed:
                    raise ValueError(f'{DAYS[day]}: 2. çalışma dilimi uyanma/yatış sınırlarının içinde olmalı.')
                if second_start < end and start < second_end:
                    raise ValueError(f'{DAYS[day]}: çalışma dilimleri üst üste gelemez.')
                study_windows.append((second_start, second_end))
            result[day] = sorted([segment
                                  for study_range in study_windows
                                  for segment in subtract_intervals(study_range, intervals)])
        else:
            # A previously saved V2 day override represents a single study
            # window. Without advanced opt-in, preserve original behavior.
            override = (day_overrides.get(str(day), {}) if data.get('advanced_enabled') is not False else {}) or {}
            if not isinstance(override, dict):
                raise ValueError('Günlük serbest zaman tanımı geçersiz.')
            start = to_minutes(override.get('wake', data.get('wake', '07:00')))
            end = to_minutes(override.get('sleep', data.get('sleep', '23:30')))
            if end <= start:
                raise ValueError(f'{DAYS[day]}: çalışma başlangıcı bitişinden önce olmalı.')
            result[day] = subtract_intervals((start, end), intervals)
    holiday = str(data.get('empty', 'Yok'))
    if holiday != 'Yok':
        if holiday == 'Rastgele':
            # A deterministic rest day prevents unpredictable re-planning.
            chosen = min(result, key=lambda d: sum(b-a for a,b in result[d]))
            result[chosen] = []
        else:
            for day in block_days(holiday):
                result[day] = []
    return result


def free_minutes(windows: List[Tuple[int, int]]) -> int:
    return sum(e - s for s, e in windows)


def find_slot(windows: List[Tuple[int, int]], booked: List[Tuple[int, int]], duration: int,
              biorhythm: str = '', gap: int = 10) -> Optional[Tuple[int, int]]:
    """Find a real clock interval that fits between the current busy entries.

    A short transition break is maintained between separately assigned tasks.
    """
    if duration <= 0:
        return None
    blocked = [(max(0, s-gap), min(1440, e+gap)) for s, e in booked]
    candidates = []
    for start, end in windows:
        for s, e in subtract_intervals((start, end), blocked):
            if e-s >= duration:
                candidates.append((s, s+duration))
                if 'Gece' in biorhythm or 'Akşam' in biorhythm:
                    candidates.append((e-duration, e))
    if not candidates:
        return None
    if 'Gece' in biorhythm or 'Akşam' in biorhythm:
        return max(candidates, key=lambda x: (x[0], x[1]))
    return min(candidates, key=lambda x: (x[0], x[1]))
