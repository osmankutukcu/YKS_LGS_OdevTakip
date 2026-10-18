# -*- coding: utf-8 -*-
"""V3.5.32: opt-in, non-destructive SQLite backup and recovery rehearsal.

Does not import db.py, start UI, write application data, overwrite a DB, or
execute SQL from legacy SQL dumps. All outputs contain only aggregate metadata.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
import zlib

MAGIC = b"SQLite format 3\0"
CHUNK = 1024 * 1024
MAX_MANIFEST = 1024 * 1024
MAX_ZIP_ENTRIES = 64
MAX_PREVIEW_SIZE = 16 * 1024**3
MAX_MEMBER_SIZE = 16 * 1024**3
REQUIRED_TABLES = ("ogrenci", "odev", "odev_kume")

class RecoveryError(ValueError):
    """Safe failure; no application databases are changed."""


def _hasher(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_check(path: Path, *, required_tables=REQUIRED_TABLES) -> dict:
    """Read-only complete SQLite integrity check; never upgrades a live DB."""
    with path.open("rb") as handle:
        if handle.read(16) != MAGIC:
            raise RecoveryError("NOT_SQLITE_BINARY")
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3)) as con:
            con.execute("PRAGMA query_only=ON")
            integrity = con.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise RecoveryError("SQLITE_INTEGRITY_FAILED")
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = sorted(set(required_tables) - tables)
            if missing:
                raise RecoveryError("REQUIRED_TABLES_MISSING")
            # No row data or personal details in the result.
            return {"integrity": "ok", "required_tables_present": True,
                    "schema_tables": len(tables), "size_bytes": path.stat().st_size}
    except sqlite3.Error as exc:
        raise RecoveryError("SQLITE_OPEN_OR_CHECK_FAILED") from exc


def _copy_limited(src, dest: Path, *, max_bytes: int | None = None) -> tuple[int, str]:
    if max_bytes is None:
        max_bytes = MAX_PREVIEW_SIZE
    size = 0
    digest = hashlib.sha256()
    with dest.open("xb") as out:
        while True:
            data = src.read(CHUNK)
            if not data:
                break
            size += len(data)
            if size > max_bytes:
                raise RecoveryError("BACKUP_SIZE_LIMIT")
            out.write(data)
            digest.update(data)
        out.flush()
        os.fsync(out.fileno())
    if size < 100:
        raise RecoveryError("BACKUP_TOO_SMALL")
    return size, digest.hexdigest()


def _safe_manifest(path: Path, *, expected_file_sha: str, expected_db_sha: str,
                   expected_db_bytes: int) -> dict:
    """Check a sidecar only if present; missing sidecars give weaker provenance."""
    sidecar = Path(str(path) + ".manifest.json")
    if not sidecar.exists():
        return {"provenance": "UNSIGNED_UNMANIFESTED", "manifest_present": False}
    if sidecar.stat().st_size > MAX_MANIFEST or sidecar.is_symlink():
        raise RecoveryError("MANIFEST_UNSAFE")
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if (payload.get("format_version") != 1
            or payload.get("file_sha256") != expected_file_sha
            or payload.get("database_sha256") != expected_db_sha
            or payload.get("database_bytes") != expected_db_bytes):
            raise RecoveryError("MANIFEST_MISMATCH")
        return {"provenance": "SHA256_MANIFEST_MATCHED", "manifest_present": True}
    except RecoveryError:
        raise
    except (ValueError, UnicodeError, KeyError) as exc:
        raise RecoveryError("MANIFEST_INVALID") from exc


def _materialize_backup(archive: Path, destination: Path) -> dict:
    """Extract at most one database into a private temporary path."""
    if not archive.is_file() or archive.is_symlink():
        raise RecoveryError("BACKUP_NOT_FOUND_OR_LINK")
    suffix = archive.name.lower()
    if suffix.endswith(".db.gz"):
        try:
            with archive.open("rb") as file_handle:
                file_sha = _hash_stream(file_handle)
            with gzip.open(archive, "rb") as data:
                n, db_sha = _copy_limited(data, destination)
        except (OSError, EOFError) as exc:
            raise RecoveryError("GZIP_UNREADABLE") from exc
        provenance = _safe_manifest(archive, expected_file_sha=file_sha,
                                    expected_db_sha=db_sha, expected_db_bytes=n)
        return {"format": "SQLITE_GZIP", "db_sha256": db_sha, **provenance}
    if suffix.endswith(".db"):
        with archive.open("rb") as data:
            n, db_sha = _copy_limited(data, destination)
        provenance = _safe_manifest(archive, expected_file_sha=db_sha,
                                    expected_db_sha=db_sha, expected_db_bytes=n)
        return {"format": "SQLITE_RAW", "db_sha256": db_sha, **provenance}
    if suffix.endswith(".zip"):
        return _from_zip(archive, destination)
    raise RecoveryError("UNSUPPORTED_BACKUP_EXTENSION")


def _hash_stream(handle) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(CHUNK), b""):
        digest.update(block)
    return digest.hexdigest()


def _from_zip(archive: Path, destination: Path) -> dict:
    """Accept the app's manifest ZIP format without extracting arbitrary paths."""
    try:
        with zipfile.ZipFile(archive) as zf:
            members = zf.infolist()
            if len(members) > MAX_ZIP_ENTRIES or len({x.filename for x in members}) != len(members):
                raise RecoveryError("ZIP_MEMBERS_UNSAFE")
            index = {i.filename: i for i in members}
            meta_info = index.get("backup_manifest.json")
            if meta_info is None or meta_info.file_size > MAX_MANIFEST:
                raise RecoveryError("ZIP_MANIFEST_MISSING")
            manifest = json.loads(zf.read(meta_info).decode("utf-8"))
            if manifest.get("format_version") not in (1,2):
                raise RecoveryError("ZIP_MANIFEST_VERSION")
            entries = manifest.get("files")
            if not isinstance(entries, list) or not entries:
                raise RecoveryError("ZIP_MANIFEST_INVALID")
            db_entries = [e for e in entries if isinstance(e, dict) and e.get("type", "sqlite") == "sqlite"]
            if len(db_entries) != 1:
                raise RecoveryError("ZIP_EXPECTED_ONE_DB")
            allowed = set()
            for e in entries:
                if not isinstance(e, dict):
                    raise RecoveryError("ZIP_MANIFEST_INVALID")
                name = e.get("name")
                if not isinstance(name, str) or name.startswith("/") or "\\" in name or ".." in Path(name).parts:
                    raise RecoveryError("ZIP_PATH_UNSAFE")
                if name in allowed or name not in index:
                    raise RecoveryError("ZIP_MANIFEST_DUPLICATE_OR_MISSING")
                allowed.add(name)
                declared_size = e.get("bytes")
                if not isinstance(declared_size, int) or declared_size < 0 or declared_size > MAX_MEMBER_SIZE:
                    raise RecoveryError("ZIP_SIZE_INVALID")
                if index[name].file_size != declared_size:
                    raise RecoveryError("ZIP_SIZE_MISMATCH")
                if not isinstance(e.get("sha256"), str) or len(e["sha256"]) != 64:
                    raise RecoveryError("ZIP_HASH_INVALID")
            if set(index) != allowed | {"backup_manifest.json"}:
                raise RecoveryError("ZIP_UNDECLARED_MEMBERS")
            for e in entries:
                name = e["name"]
                if e in db_entries:
                    with zf.open(name) as data:
                        actual_bytes, actual_sha = _copy_limited(data, destination)
                else:
                    with zf.open(name) as data:
                        digest = hashlib.sha256()
                        actual_bytes = 0
                        while block := data.read(CHUNK):
                            actual_bytes += len(block)
                            if actual_bytes > e["bytes"]:
                                raise RecoveryError("ZIP_SIZE_MISMATCH")
                            digest.update(block)
                        actual_sha = digest.hexdigest()
                if actual_bytes != e["bytes"] or actual_sha != e["sha256"]:
                    raise RecoveryError("ZIP_MANIFEST_HASH_MISMATCH")
            return {"format": "MANIFEST_ZIP", "db_sha256": _hasher(destination),
                    "provenance": "SHA256_MANIFEST_MATCHED", "manifest_present": True,
                    "planner_payloads_present": any(e.get('type') == 'json' for e in entries)}
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, UnicodeError,
            KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RecoveryError("ZIP_UNREADABLE_OR_INVALID") from exc


def preview_restore(backup_path: str | Path, *, require_manifest: bool = False) -> dict:
    """Prove readability in an isolated, automatically deleted directory.

    Never touches the active database or writes to its directory.
    Nothing is restored or installed. Legacy SQL text is deliberately NOT executed.
    """
    requested = Path(backup_path).expanduser()
    if requested.is_symlink():
        return {"status": "REHEARSAL_FAILED", "reason": "BACKUP_NOT_FOUND_OR_LINK",
                "restored_to_live_database": False, "temporary_copy_deleted": True}
    archive = requested.resolve()
    try:
        with tempfile.TemporaryDirectory(prefix="yks_restore_rehearsal_") as temp:
            stage = Path(temp) / "staged.db"
            metadata = _materialize_backup(archive, stage)
            if require_manifest and not metadata.get("manifest_present"):
                raise RecoveryError("MANIFEST_REQUIRED")
            checks = _snapshot_check(stage)
            return {"status": "REHEARSAL_PASSED", "restored_to_live_database": False,
                    "temporary_copy_deleted": True, **checks,
                    "format": metadata["format"], "provenance": metadata["provenance"],
                    "planner_payloads_present": metadata.get("planner_payloads_present", False)}
    except (RecoveryError, OSError, gzip.BadGzipFile, zlib.error) as exc:
        code = str(exc) if isinstance(exc, RecoveryError) else "IO_OR_COMPRESSION_FAILURE"
        return {"status": "REHEARSAL_FAILED", "reason": code,
                "restored_to_live_database": False, "temporary_copy_deleted": True}


def _sync_dir(path: Path) -> None:
    """Best-effort directory sync; some Windows configurations disallow this."""
    if os.name != "posix":
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    except OSError:
        pass


def create_verified_backup(source_path: str | Path, destination_dir: str | Path, *,
                           compress: bool = True, timeout_seconds: float = 30.0,
                           scope_token: str | None = None) -> dict:
    """Online snapshot, verified before atomic publication; explicit opt-in.

    Only two new files are written into destination_dir. No cleanup/rotation or
    live-restore is performed. Caller should use a trusted non-shared folder.
    """
    original_source = Path(source_path).expanduser()
    original_dest = Path(destination_dir).expanduser()
    if original_source.is_symlink() or original_dest.is_symlink():
        return {"status": "BACKUP_FAILED", "reason": "SYMLINK_PATH_REJECTED"}
    source = original_source.resolve()
    dest_dir = original_dest.resolve()
    if not source.is_file() or not dest_dir.is_dir():
        return {"status": "BACKUP_FAILED", "reason": "INVALID_SOURCE_OR_DESTINATION"}
    if source == dest_dir:
        return {"status": "BACKUP_FAILED", "reason": "INVALID_DESTINATION"}
    if scope_token is not None and not (
            isinstance(scope_token, str) and len(scope_token) == 32
            and all(x in '0123456789abcdef' for x in scope_token)):
        return {"status": "BACKUP_FAILED", "reason": "INVALID_SCOPE_TOKEN",
                "live_database_modified": False}
    try:
        with source.open("rb") as handle:
            if handle.read(16) != MAGIC:
                raise RecoveryError("SOURCE_NOT_SQLITE")
        # Do not create a path-based source URI using manual string manipulation.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        name = f"YKS_Kurtarilabilir_{stamp}.db" + (".gz" if compress else "")
        final = dest_dir / name
        manifest_final = Path(str(final) + ".manifest.json")
        created = None
        published = False
        with tempfile.TemporaryDirectory(prefix="yks_verified_", dir=dest_dir) as t:
            work = Path(t)
            staged = work / "snapshot.db"
            started = time.monotonic()
            with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=3)) as src:
                with closing(sqlite3.connect(staged, timeout=3)) as dst:
                    def progress(status, remaining, total):
                        if time.monotonic() - started > max(1, timeout_seconds):
                            raise RecoveryError("SOURCE_BACKUP_TIMED_OUT")
                    src.backup(dst, pages=256, progress=progress, sleep=0.05)
            check = _snapshot_check(staged)
            data_sha = _hasher(staged)
            payload = work / name
            if compress:
                with staged.open("rb") as inp, payload.open("xb") as raw:
                    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
                        shutil.copyfileobj(inp, gz, length=CHUNK)
                    raw.flush();os.fsync(raw.fileno())
            else:
                with staged.open("rb") as inp, payload.open("xb") as out:
                    shutil.copyfileobj(inp,out,length=CHUNK)
                    out.flush();os.fsync(out.fileno())
            manifest = {"format_version": 1,
                        "created_at_utc": datetime.now(timezone.utc).isoformat(),
                        "format": "sqlite_online_backup_gzip" if compress else "sqlite_online_backup_raw",
                        "file_sha256": _hasher(payload),
                        "database_sha256": data_sha,
                        "database_bytes": check["size_bytes"]}
            if scope_token is not None:
                manifest["backup_scope"] = scope_token
            manifest_staged = work / (name + ".manifest.json")
            with manifest_staged.open("x", encoding="utf-8") as out:
                json.dump(manifest,out,indent=2,ensure_ascii=False)
                out.flush();os.fsync(out.fileno())
            if preview_restore(payload, require_manifest=False)["status"] != "REHEARSAL_PASSED":
                raise RecoveryError("PRE_PUBLICATION_REHEARSAL_FAILED")
            if final.exists() or manifest_final.exists():
                raise RecoveryError("BACKUP_NAME_COLLISION")
            os.replace(payload, final)
            published = True
            os.replace(manifest_staged, manifest_final)
            _sync_dir(dest_dir)
            created = final
        final_check = preview_restore(created, require_manifest=True)
        if final_check["status"] != "REHEARSAL_PASSED":
            raise RecoveryError("POST_PUBLICATION_REHEARSAL_FAILED")
        return {"status": "BACKUP_CREATED_AND_REHEARSED", "format": "SQLITE_GZIP" if compress else "SQLITE_RAW",
                "archive_path": str(created), "manifest_path": str(manifest_final),
                "database_bytes": check["size_bytes"], "live_database_modified": False}
    except (OSError, sqlite3.Error, RecoveryError) as exc:
        # Remove only files created by THIS failed attempt; never previous backups.
        if locals().get("published", False):
            try:
                final.unlink(missing_ok=True)
                manifest_final.unlink(missing_ok=True)
            except OSError:
                pass
        reason = str(exc) if isinstance(exc, RecoveryError) else "SOURCE_OR_DESTINATION_IO_FAILURE"
        return {"status": "BACKUP_FAILED", "reason": reason,
                "live_database_modified": False}


def due_for_backup(last_verified_utc: datetime | None, *, now_utc: datetime | None = None,
                   minimum_hours: int = 24) -> bool:
    """Pure decision helper for future opt-in scheduler; does not run itself."""
    if last_verified_utc is None:
        return True
    now = now_utc or datetime.now(timezone.utc)
    if last_verified_utc.tzinfo is None or now.tzinfo is None:
        raise RecoveryError("AWARE_DATETIMES_REQUIRED")
    return (now - last_verified_utc).total_seconds() >= max(1, minimum_hours) * 3600
