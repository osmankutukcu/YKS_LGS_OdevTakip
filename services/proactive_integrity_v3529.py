# -*- coding: utf-8 -*-
"""V3.5.29: bounded, read-only, identity-free proactive homework link audit.

Runs only when a background caller requests a check (UI uses 10-minute cadence).
Returns aggregate codes/counts without student names, phones or row references.
Errors/timeouts mean UNVERIFIED, never GREEN. No repair and no schema changes.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sqlite3
import time
from contextlib import closing

from services.homework_integrity_v135 import audit_database


def read_integrity_overview(db_path: Path | str, *, time_budget_seconds: float = 1.6) -> dict:
    path = Path(db_path).expanduser().resolve()
    if not path.is_file():
        return {'state': 'UNAVAILABLE', 'checked': False, 'urgent_count': None,
                'finding_count': None, 'codes': [], 'read_only': True}
    deadline = time.monotonic() + max(0.05, min(float(time_budget_seconds), 5.0))
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True,
                                     timeout=0.2)) as con:
            con.execute('PRAGMA query_only=ON')
            # Interrupt expensive/locked work instead of holding a teacher's UI.
            con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            report = audit_database(con, sample_limit=0)
        severity = Counter()
        codes = []
        for finding in report.findings:
            severity[finding.severity] += int(finding.count)
            codes.append(finding.code)
        urgent = severity['critical'] + severity['high']
        return {'state': 'REVIEW' if report.findings else 'NO_FINDINGS_IN_SCOPE',
                'checked': True, 'urgent_count': urgent,
                'finding_count': sum(severity.values()),
                'codes': sorted(set(codes)), 'read_only': True,
                'scope': 'homework_student_group_links_only',
                'not_full_system_health': True}
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return {'state': 'UNVERIFIED', 'checked': False, 'urgent_count': None,
                'finding_count': None, 'codes': [], 'read_only': True}
