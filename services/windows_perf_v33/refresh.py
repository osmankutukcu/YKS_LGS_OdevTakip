"""V33: optional trial to coalesce table *style* refresh events.

The normal Ödev Takip and Ödev Kontrol source files are unchanged. This module
may only be activated by the separate V33 Windows diagnostic launcher.

There is no promise of a speedup before testing on the user's Windows device.
"""
from __future__ import annotations
from collections.abc import Callable
from functools import wraps
from time import perf_counter_ns
from typing import Any


class RefreshGate:
    """Combine multiple same-event-loop refresh requests into one.

    Deliberately has no dependency on Qt and does not change checkbox state,
    data records, save behavior or other signal connections.
    """
    def __init__(self, submit: Callable[[Callable[[], None]], None], refresh: Callable[[], None]):
        self._submit = submit
        self._refresh = refresh
        self.pending = False
        self.running = False
        self.requests = 0
        self.refreshes = 0
        self.coalesced = 0

    def request(self) -> None:
        self.requests += 1
        if self.pending or self.running:
            self.coalesced += 1
            return
        self.pending = True
        try:
            self._submit(self.flush)
        except BaseException:
            self.pending = False
            raise

    def flush(self) -> None:
        if not self.pending or self.running:
            return
        self.pending = False
        self.running = True
        try:
            self._refresh()
            self.refreshes += 1
        finally:
            self.running = False


def install_experimental_style_coalescing(dialog_cls: type, *,
                                           submit: Callable[[Callable[[], None]], None] | None = None,
                                           blocker_factory: Callable[[Any], Any] | None = None,
                                           record_actual_ns: Callable[[int], None] | None = None) -> bool:
    """Patch only style refresh, only on the caller's explicit opt-in.

    The production app does not call this. If Qt is absent, the caller may
    inject fake scheduler/blocker for non-GUI unit testing. Qt signal blocking
    is limited to the style writes, then the viewport is requested to repaint.

    Returns False if already installed (safe for repeated invocations).
    """
    old = getattr(dialog_cls, '_refresh_right_table_styles', None)
    if old is None or not callable(old) or getattr(old, '_v33_style_patch', False):
        return False
    if submit is None or blocker_factory is None:
        from PyQt6.QtCore import QTimer, QSignalBlocker
        submit = submit or (lambda fn: QTimer.singleShot(0, fn))
        blocker_factory = blocker_factory or QSignalBlocker

    @wraps(old)
    def scheduled(self, *args, **kwargs):
        gate = getattr(self, '_v33_style_refresh_gate', None)
        if gate is None:
            def run_legacy_style_once():
                table = getattr(self, 'tab', None)
                if table is None:
                    return
                try:
                    model = table.model()
                    blocker = blocker_factory(model)
                    started = perf_counter_ns()
                    try:
                        old(self)
                    finally:
                        if record_actual_ns is not None:
                            record_actual_ns(perf_counter_ns() - started)
                        # Deletion is important: Qt blocks signals only inside this scope.
                        del blocker
                    table.viewport().update()
                except RuntimeError:
                    # Window is being disposed; no background work or DB access.
                    return
            gate = RefreshGate(submit, run_legacy_style_once)
            self._v33_style_refresh_gate = gate
        gate.request()

    scheduled._v33_style_patch = True
    setattr(dialog_cls, '_refresh_right_table_styles', scheduled)
    return True
