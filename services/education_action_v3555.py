# -*- coding: utf-8 -*-
"""Eğitim panosu için mevcut Dashboard V35 ile birebir tutarlı, salt okunur eylem notu.

Sadece tek yönlü veri okur. Görev kaydetmez, öğrenci notu değiştirmez,
ödev kontrol kutularına / Öğretmen Karar Masası koduna dokunmaz.
"""
from __future__ import annotations
from pathlib import Path
import sqlite3


def read_teacher_action(db_path) -> dict | None:
    p = Path(db_path) if db_path else None
    if not p or not p.exists():
        return None
    try:
        from services.dashboard_metrics_v35 import build_snapshot, build_teacher_insight
        with sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as con:
            snapshot = build_snapshot(con)
        detail = build_teacher_insight(snapshot)
        if not detail:
            return None
        return {'source': 'SİSTEM', 'title': detail, 'tags': 'ÖNCELİK,ÖDEV',
                'url': '', 'published': snapshot.computed_for.isoformat(), 'score': 1000}
    except (sqlite3.Error, ImportError, ValueError, TypeError, OSError):
        # Kaynak yoksa 0 gösterip yanlış güven vermeyiz.
        return None
