"""Opt-in timing wrapper. Only aggregate timings, never method args/student PII."""
from __future__ import annotations
from collections import defaultdict
from functools import wraps
from time import perf_counter_ns
from typing import Any
import json


class MethodStats:
    def __init__(self) -> None:
        self._times: dict[str, list[float]] = defaultdict(list)
        self._errors: dict[str, int] = defaultdict(int)

    def record(self, label: str, elapsed_ns: int, failed: bool = False) -> None:
        # Bounded sampling prevents unbounded memory in long Windows sessions.
        series = self._times[label]
        if len(series) < 10000:
            series.append(round(max(0, elapsed_ns) / 1_000_000, 5))
        if failed:
            self._errors[label] += 1

    def report(self) -> dict[str, Any]:
        methods = {}
        for name, values in sorted(self._times.items()):
            ordered = sorted(values)
            n = len(values)
            methods[name] = {
                'calls_recorded': n,
                'avg_ms': round(sum(values) / n, 3),
                'p50_ms': ordered[(n - 1) // 2],
                'p95_ms': ordered[min(n - 1, int((n - 1) * .95))],
                'max_ms': ordered[-1],
                'exceptions': int(self._errors.get(name, 0)),
            }
        return {'format': 'odevtakip-v32-no-personal-data',
                'limitations': 'Python method wall time, not GPU repaint or mouse-to-photon latency',
                'methods': methods}

    def save(self, path: str) -> None:
        from pathlib import Path
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Do not write PII or DB content; numerical aggregates only.
        target.write_text(json.dumps(self.report(), ensure_ascii=False, indent=2), encoding='utf-8')


def install_method_timing(cls: type, method_name: str, collector: MethodStats, label: str | None = None) -> bool:
    """Wrap a class method, preserving args, return, raised errors and binding.

    For a diagnostic launch only. Calling twice with same class/method is idempotent.
    """
    fn = getattr(cls, method_name, None)
    if fn is None or not callable(fn):
        return False
    if getattr(fn, '_v32_perf_wrapped', False):
        return False
    name = label or f'{cls.__name__}.{method_name}'

    @wraps(fn)
    def measured(*args, **kwargs):
        started = perf_counter_ns()
        failed = False
        try:
            return fn(*args, **kwargs)
        except BaseException:
            failed = True
            raise
        finally:
            collector.record(name, perf_counter_ns() - started, failed)
    measured._v32_perf_wrapped = True
    setattr(cls, method_name, measured)
    return True
