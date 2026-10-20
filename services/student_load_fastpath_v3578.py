# -*- coding: utf-8 -*-
"""KoçPilot 360 V3578: Conservative student-switch duplicate-work fast path.

No changes to homework matrices, progress, sqlite, signals, saving or undo.
Only avoids the outer *duplicate* recommendation + snapshot calls when the
existing `_bilgileri_getir` has successfully loaded the selected student.

Use KOCPILOT_STUDENT_LOAD_FASTPATH=0 to restore the original selection method.
"""
from __future__ import annotations

import functools
import os
from typing import Any


def _enabled() -> bool:
    return os.environ.get('KOCPILOT_STUDENT_LOAD_FASTPATH', '1').strip().lower() not in (
        '0', 'off', 'false', 'hayir', 'no'
    )


def install_student_load_fastpath(form_class: type) -> bool:
    """Install once, before the V3577 timing wrapper. Never mutates records."""
    if not _enabled() or getattr(form_class, '_student_fastpath_v3578_installed', False):
        return False
    original = getattr(form_class, '_ogrenci_degisti_combo_ile', None)
    if not callable(original):
        return False

    @functools.wraps(original)
    def switch(self: Any, *args: Any, **kwargs: Any):
        # Preserve original functionality when the class contract is unclear.
        try:
            selected = self._secili_ogrenci_id()
        except Exception:
            return original(self, *args, **kwargs)
        if not selected or not callable(getattr(self, '_bilgileri_getir', None)):
            return original(self, *args, **kwargs)

        # The original _bilgileri_getir refreshes recommendations and snapshot,
        # then sets _loaded_student_id to the selected id on success.
        try:
            self._bilgileri_getir()
        except Exception:
            # Legacy outer handler silently ignores errors and still refreshes
            # snapshot. Never retry the load, because it may have side effects.
            try:
                getattr(self.oneri, '_yenile_click', lambda: None)()
            except Exception:
                pass
            try:
                self._update_student_snapshot()
            except Exception:
                pass
            return None

        try:
            success = self._loaded_student_id == selected
        except Exception:
            success = False
        if success:
            # _bilgileri_getir already called oneri and snapshot. Do not run
            # them twice. Progress and matrix paths remain the original ones.
            return None

        # For partial/early-return loads, retain the legacy outer refreshes.
        try:
            getattr(self.oneri, '_yenile_click', lambda: None)()
        except Exception:
            pass
        try:
            self._update_student_snapshot()
        except Exception:
            pass
        return None

    switch._student_fastpath_v3578 = True
    form_class._ogrenci_degisti_combo_ile = switch
    form_class._student_fastpath_v3578_installed = True
    form_class._student_fastpath_v3578_original = original
    return True


def install_default_fastpath() -> bool:
    if not _enabled():
        return False
    from ui.homework_form import OdevTakipFormu
    return install_student_load_fastpath(OdevTakipFormu)
