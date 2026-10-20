# -*- coding: utf-8 -*-
"""Readable, anonymous V1 student load timing report; stdlib only."""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from services.student_load_profiler_v3577 import default_log_path


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile, no interpolation and no dependency."""
    if not values:
        return 0.0
    values = sorted(values)
    return values[max(0, math.ceil(pct / 100.0 * len(values)) - 1)]


def summarise(records: list[dict]) -> dict:
    clean = [r for r in records if r.get('schema') == 'student_load_v1'
             and isinstance(r.get('duration_ms'), (float, int))]
    good = [r for r in clean if r.get('status') == 'ok']
    times = [r['duration_ms'] for r in good]
    parts = defaultdict(list)
    for record in good:
        for name, stat in record.get('parts', {}).items():
            if isinstance(stat, dict) and isinstance(stat.get('total_ms'), (int, float)):
                parts[name].append(stat['total_ms'])
    return {
        'total': len(clean), 'successful': len(good), 'errors': len(clean) - len(good),
        'median_ms': percentile(times, 50), 'p95_ms': percentile(times, 95),
        'lessons_median': percentile([r.get('lesson_tables', 0) for r in good], 50),
        'part_medians_ms': {k: percentile(v, 50) for k, v in sorted(parts.items())},
    }


def read_records(path: Path) -> list[dict]:
    rows = []
    for p in (path.with_suffix('.previous.jsonl'), path):
        if not p.is_file():
            continue
        with p.open(encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        rows.append(record)
                except (ValueError, TypeError):
                    continue
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description='KoçPilot anonim öğrenci yükleme süre raporu')
    parser.add_argument('--input', type=Path, default=default_log_path())
    args = parser.parse_args()
    result = summarise(read_records(args.input))
    print('KoçPilot 360 — Öğrenci Yükleme V1')
    print(f"Ölçülen yükleme: {result['total']} | Başarılı: {result['successful']} | Hatalı: {result['errors']}")
    if not result['successful']:
        print('Henüz ölçüm yok. Uygulamayı açıp öğrenci değiştirin.')
        return 0
    print(f"Ortanca: {result['median_ms']:.1f} ms | P95: {result['p95_ms']:.1f} ms")
    print(f"Ortanca ders sekmesi sayısı: {result['lessons_median']}")
    print('Ölçülen parçaların ortanca toplam süresi:')
    for name, ms in sorted(result['part_medians_ms'].items(), key=lambda kv: kv[1], reverse=True):
        print(f'  {name}: {ms:.1f} ms')
    print('Not: Parçaların süreleri iç içe ölçülebilir; toplamları yükleme süresine eşit değildir.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
