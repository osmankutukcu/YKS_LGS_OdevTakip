# -*- coding: utf-8 -*-
"""Fail-safe report access for a *failed* Report Center opening.

This module is intentionally independent of Qt, SQL and report engines.  It
only inventories and dispatches already-existing main-window actions.  Nothing
here changes menu visibility, databases, report calculations or student IDs.
"""
from __future__ import annotations

# Stable, pre-existing main-window entry points (not the new center itself).
LEGACY_REPORT_ROUTES = (
    ("Öğrenci Detayı", "_ogrenci_detay"),
    ("Performans Paneli", "_performans_paneli"),
    ("Detaylı Raporlar / Sınıf-Kurum", "_rapor_ac"),
    ("Hızlı PDF", "_create_pdf_report"),
    ("Rapor Rehberi", "_show_report_guide"),
    ("Hedef Analizi", "_hedef_analiz_open"),
)


def available_legacy_routes(main_window):
    """Return only the original report entry points that remain callable."""
    return tuple(
        (title, method)
        for title, method in LEGACY_REPORT_ROUTES
        if callable(getattr(main_window, method, None))
    )


def open_legacy_route(main_window, method_name):
    """Invoke one specifically allowlisted original action, never arbitrary code."""
    allowed = {method for _, method in available_legacy_routes(main_window)}
    if method_name not in allowed:
        raise ValueError("Seçilen rapor erişimi mevcut değil")
    return getattr(main_window, method_name)()
