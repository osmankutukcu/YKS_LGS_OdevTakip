"""Opt-in, deterministic, per-day weekly homework distribution.

No Qt dependency, database access or side effects.  Each input task may be
assigned to exactly one day, or explicitly returned as unplaced.  Targets are
capacities, not promises that the available homework will fill every day.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class DayLimit:
    label: str
    minutes: int
    max_tasks: int


@dataclass(frozen=True)
class Placement:
    task_index: int
    day_index: int
    minutes: int


@dataclass(frozen=True)
class WeeklyDistribution:
    placements: tuple[Placement, ...]
    unplaced: tuple[int, ...]
    totals: tuple[int, ...]
    counts: tuple[int, ...]
    warnings: tuple[str, ...]
    requested_minutes: int


def distribute_week(
    tasks: Sequence[dict],
    days: Sequence[DayLimit],
    *,
    tolerance: int = 0,
    avoid_same_subject: bool = False,
    weekend_days: frozenset[int] = frozenset(),
) -> WeeklyDistribution:
    if len(days) != 7:
        raise ValueError("Haftalık plan tam 7 gün içermelidir.")
    if not isinstance(tolerance, int) or not 0 <= tolerance <= 240:
        raise ValueError("Tolerans 0–240 dakika arasında olmalıdır.")
    for day in days:
        if not isinstance(day.minutes, int) or not 0 <= day.minutes <= 1000:
            raise ValueError("Günlük hedef 0–1000 dakika arasında olmalıdır.")
        if not isinstance(day.max_tasks, int) or not 0 <= day.max_tasks <= 20:
            raise ValueError("Günlük maksimum görev 0–20 arasında olmalıdır.")
    durations: list[int] = []
    subjects: list[str] = []
    for i, task in enumerate(tasks):
        raw = task.get("dk", None)
        if isinstance(raw, bool):
            raise ValueError(f"{i + 1}. ödevin süresi geçersiz.")
        try:
            minutes = int(raw)
        except (ValueError, TypeError):
            raise ValueError(f"{i + 1}. ödevin süresi geçersiz.") from None
        if not 1 <= minutes <= 1000:
            raise ValueError(f"{i + 1}. ödevin süresi 1–1000 dk olmalıdır.")
        durations.append(minutes)
        subjects.append(str(task.get("ders") or "").strip().casefold())

    totals = [0] * 7
    counts = [0] * 7
    subjects_by_day = [set() for _ in range(7)]
    placed: list[Placement] = []
    unplaced: list[int] = []

    # Largest first prevents a small task from consuming the only slot that
    # can accommodate a longer one. Original index is stable across retries.
    for row in sorted(range(len(tasks)), key=lambda r: (-durations[r], r)):
        minutes = durations[row]
        candidates: list[tuple[tuple[float, float, int], int]] = []
        for g, day in enumerate(days):
            if day.minutes <= 0 or day.max_tasks <= 0:
                continue
            if counts[g] >= day.max_tasks:
                continue
            if totals[g] + minutes > day.minutes + tolerance:
                continue
            ratio = totals[g] / day.minutes
            same_subject_penalty = 0.12 if (avoid_same_subject and subjects[row] and subjects[row] in subjects_by_day[g]) else 0.0
            weekend_bonus = 0.07 if g in weekend_days else 0.0
            # Fairness is the first-order criterion, then avoid same-subject
            # concentration and optionally favor weekends on near-ties.
            score = ratio + same_subject_penalty - weekend_bonus
            candidates.append(((score, totals[g], g), g))
        if not candidates:
            unplaced.append(row)
            continue
        _, chosen = min(candidates)
        totals[chosen] += minutes
        counts[chosen] += 1
        if subjects[row]:
            subjects_by_day[chosen].add(subjects[row])
        placed.append(Placement(row, chosen, minutes))

    placed.sort(key=lambda p: p.task_index)
    unplaced.sort()
    requested = sum(durations)
    warnings: list[str] = []
    available = sum(max(0, d.minutes) for d in days)
    if requested < available:
        warnings.append(
            f"Toplam ödev {requested} dk; günlük hedeflerin toplamı {available} dk. "
            f"Her günün hedefini doldurmak için {available-requested} dk daha görev gerekir."
        )
    if durations and len(set(durations)) == 1:
        duration = durations[0]
        for day in days:
            if day.minutes > 0 and day.max_tasks > 0 and day.max_tasks * duration < day.minutes:
                warnings.append(
                    f"{day.label}: {day.minutes} dk hedefe, {day.max_tasks} görev × {duration} dk "
                    f"ile en fazla {day.max_tasks * duration} dk ulaşılabilir."
                )
                break  # One concise example instead of seven repeated warnings.
    if unplaced:
        missing = sum(durations[r] for r in unplaced)
        warnings.append(
            f"{len(unplaced)} ödev ({missing} dk) günlük süre/ödev sınırlarına sığmadı; "
            "görevler silinmedi, lütfen hedef ve sınırları kontrol edin."
        )
    if avoid_same_subject:
        warnings.append("'Aynı dersi yığma' eşit gün dağılımında tercih olarak uygulanır; zorunlu yasak değildir.")
    if requested != sum(totals) + sum(durations[r] for r in unplaced):
        raise AssertionError("Ödev dakika bütünlüğü bozuldu")
    if len(placed) + len(unplaced) != len(tasks):
        raise AssertionError("Ödev sayısı bütünlüğü bozuldu")
    return WeeklyDistribution(
        placements=tuple(placed), unplaced=tuple(unplaced),
        totals=tuple(totals), counts=tuple(counts), warnings=tuple(warnings),
        requested_minutes=requested,
    )
