# -*- coding: utf-8 -*-
"""V3.5.31 automatic, bounded, read-only local health observations.

No student/phone/message records, network calls, queues, restoration, repairs,
permission changes or backups. A result never certifies the whole system.
Works from an explicit SQLite path; does not import db.py or trigger migrations.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import gzip
import sqlite3
import time

_REQUIRED = ("ogrenci", "odev", "odev_kume")
_SQLITE_MAGIC = b"SQLite format 3\x00"


def _status(code: str, *, level: str = "unknown", **extra) -> dict:
    return {"state": code, "level": level, **extra}


def check_database(path: str | Path, *, seconds: float = 1.0) -> dict:
    """Bounded schema/quick integrity probe. No writes or student row reads."""
    db = Path(path).expanduser().resolve()
    if not db.is_file():
        return _status("DB_NOT_FOUND", level="warning", checked=False)
    deadline = time.monotonic() + max(0.05, min(float(seconds), 2.5))
    try:
        with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=0.2)) as con:
            con.execute("PRAGMA query_only=ON")
            con.set_progress_handler(lambda: int(time.monotonic() >= deadline), 400)
            con.execute("SELECT 1").fetchone()
            available = {str(row[0]) for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
            missing = [table for table in _REQUIRED if table not in available]
            if missing:
                return _status("SCHEMA_INCOMPLETE", level="warning", checked=True,
                               missing_tables=missing)
            # quick_check(1) is a limited internal consistency signal, not a
            # backup restore test or an exhaustive foreign-key/relational audit.
            quick = con.execute("PRAGMA quick_check(1)").fetchone()
            if quick is None or quick[0] != "ok":
                return _status("SQLITE_QUICK_CHECK_REVIEW", level="warning", checked=True)
            return _status("LOCAL_DB_CHECKS_OK", level="ok", checked=True)
    except (sqlite3.Error, OSError, ValueError):
        return _status("DB_PROBE_UNVERIFIED", level="unknown", checked=False)


def _backup_signature(path: Path) -> str:
    """Inspect at most 16 decoded bytes, never trust filename extensions."""
    try:
        if path.name.lower().endswith(".gz"):
            with gzip.open(path, "rb") as stream:
                head = stream.read(16)
        else:
            with path.open("rb") as stream:
                head = stream.read(16)
        if head == _SQLITE_MAGIC:
            return "SQLITE_HEADER"
        if head.lstrip().upper().startswith((b"BEGIN TRANSACT", b"PRAGMA", b"CREATE TABLE", b"--")):
            return "SQL_TEXT_NOT_SQLITE"
        return "UNKNOWN_FORMAT"
    except (OSError, EOFError, ValueError):
        return "UNREADABLE"


def check_backup(db_path: str | Path, *, backup_dir: str | Path | None = None,
                 now_timestamp: float | None = None, stale_days: int = 7) -> dict:
    """Evidence-only check of a SINGLE directory, not proof of recoverability.

    If no explicit directory is provided, inspect the conventional sibling
    'backups' directory, without creating it or assuming other dirs are empty.
    """
    db = Path(db_path).expanduser().resolve()
    folder = Path(backup_dir).expanduser() if backup_dir is not None else db.parent / "backups"
    if not folder.is_dir():
        return _status("NO_BACKUPS_IN_OBSERVED_DIR", checked=False,
                       scope="explicit" if backup_dir else "default_only")
    try:
        # Bounded enumeration. Only backup file names; never inspect contents
        # other than the latest candidate's 16-byte decompressed header.
        eligible = []
        for index, child in enumerate(folder.iterdir()):
            if index >= 2000:
                return _status("BACKUP_LIST_TOO_LARGE", level="unknown", checked=False)
            if not child.is_file():
                continue
            name = child.name.lower()
            if name.endswith((".db", ".db.gz")):
                eligible.append((child.stat().st_mtime, child))
        if not eligible:
            return _status("NO_BACKUPS_IN_OBSERVED_DIR", checked=True,
                           scope="explicit" if backup_dir else "default_only")
        latest, candidate = max(eligible, key=lambda item: item[0])
        signature = _backup_signature(candidate)
        fmt = "GZIP" if candidate.name.lower().endswith(".gz") else "RAW_DB"
        age_days = max(0, (float(time.time() if now_timestamp is None else now_timestamp)-latest)/86400)
        # The existing UI restore dialog supports .db / .zip, NOT .db.gz.
        if signature == "SQL_TEXT_NOT_SQLITE":
            state, severity = "BACKUP_SQL_DUMP_MISLABELED", "warning"
        elif signature in ("UNREADABLE", "UNKNOWN_FORMAT"):
            state, severity = "BACKUP_FORMAT_UNVERIFIED", "warning"
        elif fmt == "GZIP":
            state, severity = "GZIP_BACKUP_RESTORE_NOT_SUPPORTED_BY_UI", "warning"
        elif age_days > max(1, stale_days):
            state, severity = "OBSERVED_BACKUP_STALE", "warning"
        else:
            state, severity = "BACKUP_HEADER_PRESENT_ONLY", "ok"
        return _status(state, level=severity, checked=True,
                       format=fmt, signature=signature, age_days=int(age_days),
                       recovery_tested=False, scope="explicit" if backup_dir else "default_only")
    except (OSError, ValueError):
        return _status("BACKUP_CHECK_UNVERIFIED", checked=False)


def observe_local_health(db_path: str | Path, *, backup_dir: str | Path | None = None,
                         now_timestamp: float | None = None,
                         project_root: str | Path | None = None) -> dict:
    """Independent check results. Unknown is never silently considered healthy."""
    database = check_database(db_path)
    backup = check_backup(db_path, backup_dir=backup_dir,
                          now_timestamp=now_timestamp)
    issues = []
    for group, result in (("database", database), ("backup", backup)):
        if result.get("level") == "warning":
            issues.append({"area": group, "state": result["state"]})
    catalog = None
    if project_root is not None:
        try:
            from services.system_registry_v3528 import validate_registry
            check = validate_registry(Path(project_root))
            catalog = {
                "state": "SOURCE_PATHS_PRESENT" if check["status"] == "PASS" else "SOURCE_PATHS_REVIEW",
                "catalog_count": check["catalog_count"],
                "source_present": check["source_present"],
                "runtime_tested": False,
            }
            if check["status"] != "PASS":
                issues.append({"area": "modules", "state": "SOURCE_PATHS_REVIEW"})
        except (OSError, ValueError, TypeError):
            catalog = {"state": "SOURCE_CATALOG_UNVERIFIED", "runtime_tested": False}
    uncertain = database["level"] == "unknown" or backup["state"] == "BACKUP_CHECK_UNVERIFIED"
    return {
        "version": "3.5.31", "state": "REVIEW" if issues else (
            "UNVERIFIED" if uncertain else "SCOPED_OBSERVATION"),
        "issues": issues, "database": database, "backup": backup,
        "module_sources": catalog,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "read_only": True, "automatic_repair": False,
        "backup_restore_tested": False, "network_sync_verified": False,
        "whatsapp_delivery_verified": False, "windows_uat_verified": False,
        "scope": "local_database_and_one_backup_directory_only",
    }
