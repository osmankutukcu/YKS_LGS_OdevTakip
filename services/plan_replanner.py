"""Non-destructive weekly-plan drafts and explicit acceptance.

The snapshot store contains plans approved by a teacher; it never writes to the
homework DB, checked assignments, or the teacher's manually edited weekly plan.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from services.plan_profile_store import profile_path


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         default=str, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def student_key(student_id: Any) -> str | None:
    if student_id is None or not str(student_id).strip():
        return None  # Never mix same-name students when an ID is unavailable.
    return _digest({'student_id': str(student_id).strip()})


def snapshot_path() -> Path:
    return profile_path().with_name('approved_weekly_plan_snapshots.json')


def read_snapshots(path: Path | None = None) -> dict:
    target = path or snapshot_path()
    if not target.exists():
        return {}
    try:
        with target.open('r', encoding='utf-8') as stream:
            data = json.load(stream)
    except (OSError, ValueError) as exc:
        raise ValueError('Kayıtlı haftalık plan taslakları okunamadı; önce yedekleyin.') from exc
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, dict)
                                             for k, v in data.items()):
        raise ValueError('Kayıtlı haftalık plan taslakları okunamadı; önce yedekleyin.')
    return data


def load_approved(student_id: Any, path: Path | None = None) -> dict | None:
    key = student_key(student_id)
    if not key:
        return None
    return read_snapshots(path).get(key)


def approve_snapshot(student_id: Any, snapshot: dict, path: Path | None = None) -> Path:
    key = student_key(student_id)
    if not key:
        raise ValueError('Öğrenci kimliği doğrulanmadan plan kaydedilemez.')
    target = path or snapshot_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    all_snapshots = read_snapshots(target)
    all_snapshots[key] = snapshot
    fd, temp = tempfile.mkstemp(dir=target.parent, prefix='.plan-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(all_snapshots, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return target


def _task_signature(task: Any) -> str:
    """Groups duplicate homework consistently and detects source changes."""
    raw = getattr(task, 'raw', {}) or {}
    source = {k: raw.get(k) for k in ('ders', 'kitap', 'konu', 'sure', 'deadline',
                                       'bitis', 'bitis_tarihi', 'priority', 'zorluk',
                                       'splitable', 'id') if k in raw}
    return _digest(source)


def create_snapshot(plan: dict, original_homework: list[dict], settings: Any) -> dict:
    tasks = plan.get('tasks', [])
    placed = []
    for day in plan['days']:
        for task, start, end in day.appointments:
            placed.append({'source': _task_signature(task), 'date': day.date_.isoformat(),
                           'start': start, 'end': end, 'minutes': task.sure})
    pending = Counter(_task_signature(task) for task in plan['profile'].get('unassigned', []))
    # Include both source workload changes and scheduling settings changes.
    return {
        'schema': 1,
        'created_on': date.today().isoformat(),
        'homework_hash': _digest(original_homework),
        'settings_hash': _digest(settings),
        'placed': sorted(placed, key=lambda r: (r['source'], r['date'], r['start'])),
        'pending': dict(pending),
        'placed_minutes': sum(row['minutes'] for row in placed),
        'pending_minutes': sum(task.sure for task in plan['profile'].get('unassigned', [])),
        'source_count': len(original_homework),
        'work_units': len(tasks),
    }


def compare_snapshots(previous: dict | None, proposed: dict) -> dict:
    if previous is None:
        return {'first': True, 'changed': True,
                'new_units': len(proposed.get('placed', [])),
                'pending_minutes': proposed.get('pending_minutes', 0)}
    def pairs(s):
        return Counter((x['source'], x['date'], x['start'], x['end'])
                       for x in s.get('placed', []))
    old_p, new_p = pairs(previous), pairs(proposed)
    old_groups = Counter(x['source'] for x in previous.get('placed', []))
    new_groups = Counter(x['source'] for x in proposed.get('placed', []))
    added = sum((new_groups - old_groups).values())
    removed = sum((old_groups - new_groups).values())
    # Changes to time/date within the same source are not new homework.
    unchanged_slots = sum((old_p & new_p).values())
    moved = max(0, min(sum(old_p.values()), sum(new_p.values())) - unchanged_slots
                - min(added, removed))
    changed_tasks = previous.get('homework_hash') != proposed.get('homework_hash')
    changed_settings = previous.get('settings_hash') != proposed.get('settings_hash')
    return {
        'first': False,
        'changed': changed_tasks or changed_settings or old_p != new_p or
                   previous.get('pending') != proposed.get('pending'),
        'homework_changed': changed_tasks,
        'settings_changed': changed_settings,
        'new_units': added, 'removed_units': removed, 'moved_units': moved,
        'old_pending_minutes': previous.get('pending_minutes', 0),
        'pending_minutes': proposed.get('pending_minutes', 0),
    }


def summary_text(diff: dict) -> str:
    if diff.get('first'):
        return ('Bu öğrenci için önceki onaylanmış plan bulunamadı.\n'
                f'Yeni taslak: {diff["new_units"]} çalışma parçası, '
                f'{diff["pending_minutes"]} dk yerleşmeyen ödev.')
    if not diff['changed']:
        return 'Önceki onaylanmış planla fark yok. Mevcut plan korunuyor.'
    return ('Önceki onaylı plana göre yeni taslak:\n'
            f'• Ödev listesi değişti: {"Evet" if diff["homework_changed"] else "Hayır"}\n'
            f'• Öğrenci rutinleri değişti: {"Evet" if diff["settings_changed"] else "Hayır"}\n'
            f'• Yeni parçalar: {diff["new_units"]}, kaldırılan: {diff["removed_units"]}\n'
            f'• Günü/saati değişen parça (yaklaşık): {diff["moved_units"]}\n'
            f'• Yerleşmeyen: {diff["old_pending_minutes"]} → {diff["pending_minutes"]} dk\n\n'
            'Önceki plan ve elle düzenlenen haftalık tablo değiştirilmez. '
            'Bu sadece yeni planın önizleme taslağıdır.')
