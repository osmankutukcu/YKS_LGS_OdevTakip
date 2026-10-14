"""Pure, optional, explainable one-click week planner.

This module NEVER writes database records or changes the original task list.
Manual edits are pinned by task-row indices: a pinned row can be assigned to
one or more days or deliberately excluded.  Other rows are placed at most once.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from services.weekly_equal_distribution_v35 import DayLimit, Placement


@dataclass(frozen=True)
class OneClickPlan:
    placements: tuple[Placement, ...]
    unplaced: tuple[int, ...]
    excluded: tuple[int, ...]
    totals: tuple[int, ...]
    counts: tuple[int, ...]
    warnings: tuple[str, ...]
    requested_minutes: int
    scheduled_minutes: int
    manual_rows: tuple[int, ...]


def plan_one_click(
    tasks: Sequence[dict],
    days: Sequence[DayLimit],
    *,
    manual_assignments: Mapping[int, Sequence[int]] | None = None,
    tolerance: int = 0,
    avoid_same_subject: bool = False,
) -> OneClickPlan:
    """Distribute unpinned tasks as evenly as capacity allows.

    - Each automatic row has exactly one placement or an explicit unplaced ID.
    - Manually pinned rows are left intact, including intentional exclusions.
    - Existing pinned over-capacity placements are reported, never silently moved.
    - Non-pinned rows never exceed the requested daily maximum or task cap.
    """
    if len(days) != 7:
        raise ValueError('Haftalık plan 7 gün içermelidir.')
    if not isinstance(tolerance, int) or not 0 <= tolerance <= 240:
        raise ValueError('Tolerans 0–240 dakika aralığında olmalıdır.')
    durations = []
    subjects = []
    for row, task in enumerate(tasks):
        try:
            raw = task.get('dk')
            if isinstance(raw, bool):
                raise ValueError
            minute = int(raw)
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f'{row+1}. ödev süresi geçersiz.') from None
        if not 1 <= minute <= 1000:
            raise ValueError(f'{row+1}. ödev süresi 1–1000 dk olmalıdır.')
        durations.append(minute)
        subjects.append(str(task.get('ders') or '').strip().casefold())
    for day in days:
        if not isinstance(day.minutes, int) or not 0 <= day.minutes <= 1000:
            raise ValueError('Günlük süre 0–1000 dk aralığında olmalıdır.')
        if not isinstance(day.max_tasks, int) or not 0 <= day.max_tasks <= 20:
            raise ValueError('Günlük görev sınırı 0–20 aralığında olmalıdır.')

    pinned = {}
    for row, chosen in (manual_assignments or {}).items():
        if type(row) is not int or not 0 <= row < len(tasks):
            raise ValueError('Elle sabitlenen ödev numarası geçersiz.')
        vals = tuple(chosen)
        if len(set(vals)) != len(vals) or any(type(g) is not int or g not in range(7) for g in vals):
            raise ValueError(f'{row+1}. ödevin sabit günleri geçersiz.')
        pinned[row] = vals

    totals = [0] * 7
    counts = [0] * 7
    per_subject = [set() for _ in range(7)]
    placements = []
    warnings = []
    excluded = []
    for row, chosen in sorted(pinned.items()):
        if not chosen:
            excluded.append(row)
        if len(chosen) > 1:
            warnings.append(f'{row+1}. ödev elle {len(chosen)} güne işaretlenmiş; bu tekrarlar korunmuştur.')
        for day_idx in chosen:
            totals[day_idx] += durations[row]
            counts[day_idx] += 1
            placements.append(Placement(row, day_idx, durations[row]))
            if subjects[row]:
                per_subject[day_idx].add(subjects[row])

    for g, day in enumerate(days):
        if totals[g] > day.minutes + tolerance or counts[g] > day.max_tasks:
            warnings.append(f'{day.label}: elle sabitlenen ödevler günlük sınırı aşıyor; değiştirilmedi.')

    unplaced = []
    for row in sorted((r for r in range(len(tasks)) if r not in pinned), key=lambda r: (-durations[r], r)):
        minutes = durations[row]
        eligible = []
        for g, day in enumerate(days):
            if day.minutes <= 0 or counts[g] >= day.max_tasks:
                continue
            if totals[g] + minutes > day.minutes + tolerance:
                continue
            # Capacity-relative load spreads work onto free days. Tie-breaks
            # preserve stable original day ordering for reproducible results.
            concentration = 0.15 if (avoid_same_subject and subjects[row] and subjects[row] in per_subject[g]) else 0
            eligible.append((totals[g] / day.minutes + concentration, totals[g], g))
        if not eligible:
            unplaced.append(row)
            continue
        _, _, chosen = min(eligible)
        placements.append(Placement(row, chosen, minutes))
        counts[chosen] += 1
        totals[chosen] += minutes
        if subjects[row]:
            per_subject[chosen].add(subjects[row])

    unplaced.sort()
    if unplaced:
        missing = sum(durations[r] for r in unplaced)
        warnings.append(f'{len(unplaced)} ödev ({missing} dk) hiçbir uygun güne sığmadı; listede korunuyor.')
    if sum(durations) < sum(d.minutes for d in days):
        delta = sum(d.minutes for d in days) - sum(durations)
        warnings.append(f'Haftalık hedef, mevcut görevlerden {delta} dk fazla; boşluğu hayalî görevlerle doldurmadım.')
    if durations and len(set(durations)) == 1:
        dur = durations[0]
        for day in days:
            if day.minutes > 0 and day.max_tasks > 0 and day.max_tasks * dur < day.minutes:
                warnings.append(f'{day.label}: {day.max_tasks} görev sınırıyla en fazla {day.max_tasks*dur} dk yerleştirilebilir.')
                break
    if avoid_same_subject:
        warnings.append('Aynı dersin aynı güne gelmemesi bir tercih; mümkün değilse çalışma yine yerleştirilebilir.')

    auto_rows = set(range(len(tasks))) - set(pinned)
    auto_assigned = [p.task_index for p in placements if p.task_index in auto_rows]
    if set(auto_assigned).intersection(unplaced) or len(auto_assigned) != len(set(auto_assigned)):
        raise AssertionError('Bir otomatik ödev iki kez dağıtıldı.')
    if set(auto_assigned) | set(unplaced) != auto_rows:
        raise AssertionError('Ödev kaybı var.')
    if tuple(sum(p.minutes for p in placements if p.day_index == g) for g in range(7)) != tuple(totals):
        raise AssertionError('Günlük süre toplamları tutmuyor.')

    return OneClickPlan(
        placements=tuple(sorted(placements, key=lambda p: (p.task_index, p.day_index))),
        unplaced=tuple(unplaced), excluded=tuple(excluded), totals=tuple(totals),
        counts=tuple(counts), warnings=tuple(warnings), requested_minutes=sum(durations),
        scheduled_minutes=sum(totals), manual_rows=tuple(sorted(pinned)),
    )
