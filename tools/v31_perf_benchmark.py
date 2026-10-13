# -*- coding: utf-8 -*-
"""Reproducible V31 *microbenchmarks* (not a GUI/Windows click-latency claim).

Usage: python tools/v31_perf_benchmark.py --topics 500 --repeats 60
No student data, DB file or network is accessed.
"""
from __future__ import annotations
import argparse
import json
import platform
import statistics
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.wizard_integrity_v8 import exact_task_key, _normalized_string


def measure(action, trials=5):
    samples = []
    for _ in range(trials):
        start = time.perf_counter_ns()
        action()
        samples.append((time.perf_counter_ns()-start)/1e6)
    return round(statistics.median(samples), 3)


def run(*, topics=500, repeats=60):
    general = [{'konu':f'Konu-{n:05d}'} for n in range(topics)]
    result = list(reversed(general))
    positions = {}
    for i, r in enumerate(general):
        positions.setdefault(r['konu'].lower(),i)
    general_order = [r['konu'].lower() for r in general]

    def legacy_sort():
        for _ in range(repeats):
            sorted(result, key=lambda x: (0, general_order.index(x['konu'].lower())))

    def optimized_sort():
        for _ in range(repeats):
            sorted(result, key=lambda x: (0, positions[x['konu'].lower()]))

    sample_names = [
        ('fizik','345 TYT fizik',f'Konu-{x%45:02d}')
        for x in range(16000)
    ]

    def legacy_exact_key():
        for triplet in sample_names:
            tuple(' '.join(str(part or '').split()).casefold().replace('\u0307','').replace('ı','i')
                  for part in triplet)

    def optimized_exact_key():
        for triplet in sample_names:
            exact_task_key(*triplet)

    # Warm the cache once, mimicking repeated labels in an actual matrix.
    _normalized_string.cache_clear()
    optimized_exact_key()
    a,b=measure(legacy_sort),measure(optimized_sort)
    c,d=measure(legacy_exact_key),measure(optimized_exact_key)
    return {
        'platform': platform.system(), 'python': platform.python_version(),
        'note': 'Sadece sentetik yardımcı fonksiyon mikrotesti; gerçek UI tıklama gecikmesi değildir.',
        'topics': topics, 'sort_repeats': repeats, 'key_checks': len(sample_names),
        'old_sort_ms': a, 'new_sort_ms': b,
        'old_normalization_ms': c, 'new_normalization_ms': d,
        'sort_ratio_old_over_new': round(a/b,2) if b>0 else None,
        'normalization_ratio_old_over_new': round(c/d,2) if d>0 else None,
    }


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--topics',type=int,default=500)
    p.add_argument('--repeats',type=int,default=60)
    p.add_argument('--json',type=Path,default=None,help='Save aggregate synthetic results locally')
    args=p.parse_args()
    result=run(topics=max(10,args.topics),repeats=max(1,args.repeats))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.json:
        args.json.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
