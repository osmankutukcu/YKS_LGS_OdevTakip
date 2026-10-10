# -*- coding: utf-8 -*-
"""Reliable SQLite backups for YKS/LGS Ödev Takip.

Drop-in replacement. Public BackupManager API intentionally preserved.
Backups are ZIP files but are NOT encrypted; choose a trusted destination.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from PyQt6.QtCore import QObject, pyqtSignal
from utils import settings as appset


class BackupManager(QObject):
    finished = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.db_files = ["YKS_LGS_HomeworkManager.db", "settings.db", "data.db"]

    def get_backup_path(self):
        return appset.ayar_get("yedek_konumu", "")

    def set_backup_path(self, path):
        appset.ayar_set("yedek_konumu", path)

    def is_auto_backup(self):
        return str(appset.ayar_get("yedek_oto", "false")).lower() == "true"

    def set_auto_backup(self, val: bool):
        appset.ayar_set("yedek_oto", "true" if val else "false")

    def _collect_databases(self):
        """Yalnızca uygulamanın GERÇEK aktif veritabanını yedekler.

        Açıkça seçilen/geçerli veritabanı yoksa başka dosyaya sessiz geçmez.
        Portable/eski kurulumlar ancak aktif DB modülü yoksa tekil olarak aranır.
        """
        explicit = os.environ.get("YKS_DB_PATH")
        candidate = None
        if explicit:
            candidate = Path(explicit)
        else:
            try:
                import db
                candidate = Path(db.DB_PATH) if getattr(db, "DB_PATH", None) else None
            except ImportError:
                pass
        if candidate is not None:
            candidate = candidate.expanduser().resolve()
            self._check_sqlite_file(candidate)
            return [candidate]

        legacy = [Path.cwd() / "YKS_LGS_HomeworkManager.db",
                  Path.cwd() / "veritabani.db",
                  Path.home() / ".yks_lgs_manager" / "veritabani.db"]
        found = []
        for path in legacy:
            path = path.expanduser().resolve()
            if path.exists() and path not in found:
                self._check_sqlite_file(path)
                found.append(path)
        if len(found) != 1:
            raise ValueError("Etkin veritabanı bulunamadı veya birden fazla eski veritabanı var; doğru kaynak seçilmeli.")
        return found

    @staticmethod
    def _check_sqlite_file(path):
        if not path.is_file() or path.stat().st_size < 100:
            raise ValueError(f"Etkin veritabanı yok veya boş: {path}")
        with path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise ValueError(f"Etkin dosya SQLite değil: {path}")

    @staticmethod
    def _consistent_copy(source: Path, destination: Path):
        """SQLite online-backup API includes committed WAL contents."""
        uri = source.as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=20) as source_conn:
            with sqlite3.connect(str(destination), timeout=20) as dest_conn:
                source_conn.backup(dest_conn, pages=256, sleep=0.05)
                verdict = dest_conn.execute("PRAGMA quick_check").fetchone()[0]
                if verdict != "ok":
                    raise RuntimeError(f"Yedek veritabanı bütünlük kontrolü başarısız: {source.name}")

    def create_backup(self, target_dir=None):
        dest_value = target_dir if target_dir is not None else self.get_backup_path()
        if not dest_value or not Path(dest_value).is_dir():
            return False, "Geçerli bir yedekleme klasörü seçilmemiş."

        try:
            db_paths = self._collect_databases()
        except (OSError, ValueError) as exc:
            return False, f"Yedekleme yapılmadı: {exc}"
        if not db_paths:
            return False, "Yedeklenecek geçerli SQLite veritabanı bulunamadı; boş ZIP oluşturulmadı."

        dest = Path(dest_value).resolve()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        final_zip = dest / f"YKS_Yedek_{now_str}.zip"
        partial_zip = None
        try:
            with tempfile.TemporaryDirectory(prefix="yks_sqlite_backup_") as temporary:
                scratch = Path(temporary)
                metadata = {"format_version": 1,
                            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            "files": []}
                names = set()
                staged = []
                for i, source in enumerate(db_paths, 1):
                    arcname = source.name
                    if arcname in names:
                        arcname = f"{i}_{arcname}"
                    names.add(arcname)
                    db_copy = scratch / arcname
                    self._consistent_copy(source, db_copy)
                    sha256 = hashlib.sha256(db_copy.read_bytes()).hexdigest()
                    metadata["files"].append({"name": arcname,
                                              "bytes": db_copy.stat().st_size,
                                              "sha256": sha256})
                    staged.append((db_copy, arcname))

                # Create the archive on target volume, then rename atomically.
                with tempfile.NamedTemporaryFile(prefix=".YKS_Yedek_", suffix=".part",
                                                 dir=dest, delete=False) as tmp:
                    partial_zip = Path(tmp.name)
                with zipfile.ZipFile(partial_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                    for src, name in staged:
                        zf.write(src, arcname=name)
                    zf.writestr("backup_manifest.json", json.dumps(metadata, ensure_ascii=False, indent=2))

                with zipfile.ZipFile(partial_zip, "r") as check:
                    if check.testzip() is not None:
                        raise RuntimeError("ZIP bütünlük kontrolü başarısız.")
                    for entry in metadata["files"]:
                        if hashlib.sha256(check.read(entry["name"])).hexdigest() != entry["sha256"]:
                            raise RuntimeError("ZIP içeriği SHA256 doğrulaması başarısız.")
                os.replace(partial_zip, final_zip)
                partial_zip = None

            self._cleanup_old_backups(str(dest))
            return True, f"Yedek başarıyla oluşturuldu ({len(db_paths)} veritabanı):\n{final_zip}"
        except Exception as exc:
            return False, f"Yedekleme başarısız: {exc}"
        finally:
            if partial_zip is not None:
                try:
                    partial_zip.unlink(missing_ok=True)
                except OSError:
                    pass

    def _cleanup_old_backups(self, folder):
        # Only prune after creating a verified backup; keep last 10 files.
        try:
            files = [p for p in Path(folder).iterdir()
                     if p.is_file() and p.name.startswith("YKS_Yedek_") and p.suffix == ".zip"]
            files.sort(key=lambda p: p.stat().st_mtime)
            for old in files[:-10]:
                old.unlink()
        except OSError:
            pass
