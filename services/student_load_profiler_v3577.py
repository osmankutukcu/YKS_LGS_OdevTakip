# -*- coding: utf-8 -*-
"""KoçPilot V1 – low-overhead, privacy-preserving student-load timing.

Does not touch the loading algorithm, progress bar, SQLite, checkbox state,
student selection, or save/undo paths.  Wrappers call the original functions
once with the same arguments and return/raise their original result.
"""
from __future__ import annotations

import contextvars
import functools
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable

_SCHEMA = 'student_load_v1'
_ACTIVE = contextvars.ContextVar('kocpilot_student_load_session', default=None)
_LOCK = threading.RLock()
_MAX_BYTES = 2 * 1024 * 1024


def default_log_path() -> Path:
    """Local per-user diagnostics only; no cloud transfer."""
    if os.name == 'nt':
        root = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        return Path(root) / 'KocPilot360' / 'diagnostics' / 'student_load_v1.jsonl'
    return Path.home() / '.kocpilot360' / 'diagnostics' / 'student_load_v1.jsonl'


class BoundedLocalRecorder:
    def __init__(self, path: Path | None = None, max_bytes: int = _MAX_BYTES):
        self.path = Path(path) if path is not None else default_log_path()
        self.max_bytes = max_bytes

    def append(self, record: dict[str, Any]) -> None:
        """Failures in diagnostics never interrupt student loading."""
        try:
            encoded = json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n'
            with _LOCK:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size + len(encoded.encode('utf-8')) > self.max_bytes:
                    self.path.replace(self.path.with_suffix('.previous.jsonl'))
                with self.path.open('a', encoding='utf-8') as f:
                    f.write(encoded)
                if os.name != 'nt':
                    self.path.chmod(0o600)
        except (OSError, ValueError, TypeError):
            pass


def _bump(active: dict, name: str, elapsed_ns: int) -> None:
    bucket = active['parts'].setdefault(name, {'calls': 0, 'total_ms': 0.0})
    bucket['calls'] += 1
    bucket['total_ms'] += elapsed_ns / 1_000_000


def _round_parts(parts: dict) -> dict:
    return {k: {'calls': v['calls'], 'total_ms': round(v['total_ms'], 3)}
            for k, v in sorted(parts.items())}


def install_student_load_profiler(form_class: type, *, progress_class: type | None = None,
                                  recorder: Any = None) -> bool:
    """Install idempotent timing wrappers; no domain / widget logic changes.

    Nested calls are timed separately. No student id, student name, topic,
    book, homework, phone number, or SQL query is collected.
    """
    if getattr(form_class, '_kocpilot_student_profiler_installed', False):
        return False
    rec = recorder if recorder is not None else BoundedLocalRecorder()

    def make_wrapper(name: str, original: Callable):
        @functools.wraps(original)
        def measured(self, *args, **kwargs):
            active = _ACTIVE.get()
            owns_session = active is None and name in ('_bilgileri_getir', '_ogrenci_degisti_combo_ile')
            token = None
            if owns_session:
                active = {'parts': {}, 'lesson_tables': 0, 'lesson_rows': 0,
                          'lesson_columns': 0, 'reentrant_load_count': 0,
                          'started_ns': time.perf_counter_ns()}
                token = _ACTIVE.set(active)
            elif active is not None and name == '_bilgileri_getir' and active.get('_inside_load'):
                active['reentrant_load_count'] += 1
            entered_load = active is not None and name == '_bilgileri_getir'
            prior_inside = active.get('_inside_load', False) if active is not None else False
            if entered_load:
                active['_inside_load'] = True
            start = time.perf_counter_ns() if active is not None else None
            status = 'ok'
            try:
                try:
                    result = original(self, *args, **kwargs)
                except TypeError as te:
                    if ('positional argument' in str(te) or 'takes 1' in str(te)) and args:
                        result = original(self)
                    else:
                        raise
                if active is not None and name == '_ders_tab_olustur':
                    active['lesson_tables'] += 1
                    try:
                        table = result[1]
                        active['lesson_rows'] += int(table.rowCount())
                        active['lesson_columns'] += int(table.columnCount())
                    except (AttributeError, TypeError, ValueError, IndexError):
                        pass
                return result
            except BaseException:
                status = 'error'
                raise
            finally:
                if active is not None:
                    elapsed = time.perf_counter_ns() - start
                    _bump(active, name, elapsed)
                    if entered_load:
                        active['_inside_load'] = prior_inside
                if owns_session:
                    try:
                        total_ms = (time.perf_counter_ns() - active['started_ns']) / 1_000_000
                        rec.append({
                            'schema': _SCHEMA, 'status': status,
                            'duration_ms': round(total_ms, 3),
                            'lesson_tables': active['lesson_tables'],
                            'lesson_rows': active['lesson_rows'],
                            'lesson_columns': active['lesson_columns'],
                            'reentrant_load_count': active['reentrant_load_count'],
                            'parts': _round_parts(active['parts']),
                        })
                    except Exception:
                        pass
                    finally:
                        _ACTIVE.reset(token)
        measured._kocpilot_wrapped_v3577 = True
        return measured

    # Attribute names intentionally fixed: no dynamic code execution.
    names = (
        '_ogrenci_degisti_combo_ile', '_bilgileri_getir', '_ders_tab_olustur',
        '_update_student_snapshot', '_mark_overdue_cells',
        '_apply_global_done_for_current', '_update_overdue_badges',
        '_tabs_compact_apply', '_tabs_split_long_titles', '_polish_left_tables',
        '_apply_tables_visuals',
    )
    for name in names:
        original = getattr(form_class, name, None)
        if callable(original) and not getattr(original, '_kocpilot_wrapped_v3577', False):
            setattr(form_class, name, make_wrapper(name, original))

    if progress_class is not None:
        original = getattr(progress_class, 'guncelle', None)
        if callable(original) and not getattr(original, '_kocpilot_wrapped_v3577', False):
            @functools.wraps(original)
            def measured_progress(self, *args, **kwargs):
                active = _ACTIVE.get()
                start = time.perf_counter_ns() if active is not None else None
                try:
                    return original(self, *args, **kwargs)
                finally:
                    if active is not None:
                        _bump(active, 'progress_update', time.perf_counter_ns() - start)
            measured_progress._kocpilot_wrapped_v3577 = True
            setattr(progress_class, 'guncelle', measured_progress)

    form_class._kocpilot_student_profiler_installed = True
    return True


def install_default_profiler() -> bool:
    """Called once at app startup, before OdevTakipFormu is instantiated."""
    if os.environ.get('KOCPILOT_LOAD_PROFILE', '1').strip().lower() in ('0', 'off', 'false', 'hayir'):
        return False
    from ui.homework_form import OdevTakipFormu
    try:
        from ui.progress import IlerlemePenceresi
    except ImportError:
        IlerlemePenceresi = None
    return install_student_load_profiler(OdevTakipFormu, progress_class=IlerlemePenceresi)
