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
                try:
                    self._check_sqlite_file(path)
                    found.append(path)
                except ValueError:
                    pass
        if len(found) != 1:
            raise ValueError("Etkin veritabanı bulunamadı veya birden fazla eski veritabanı var; doğru kaynak seçilmeli.")
        return found

    @staticmethod
    def _check_sqlite_file(path):
        if not path.is_file() or path.stat().st_size < 100:
            raise ValueError(f"Etkin veritabanı bulunamadı veya boş: {path}")
        with path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise ValueError(f"Etkin dosya SQLite değil: {path}")

    @staticmethod
    def _consistent_copy(source: Path, destination: Path):
        """SQLite online-backup API includes committed WAL contents."""
        uri = source.as_uri() + "?mode=ro"
        source_conn = sqlite3.connect(uri, uri=True, timeout=20)
        dest_conn = sqlite3.connect(str(destination), timeout=20)
        try:
            source_conn.backup(dest_conn, pages=256, sleep=0.05)
            verdict = dest_conn.execute("PRAGMA quick_check").fetchone()[0]
            if verdict != "ok":
                raise RuntimeError(f"Yedek veritabanı bütünlük kontrolü başarısız: {source.name}")
        finally:
            dest_conn.close()
            source_conn.close()

    @staticmethod
    def _collect_profile_files():
        """Gather the exact student routines used by the planner. Read only.

        Profile files are optional on fresh installs. A present, malformed file
        is *not* silently skipped: losing planner rules would be unacceptable.
        """
        from services.plan_profile_store import profile_path, assignment_path, legacy_paths
        profile = profile_path()
        if not profile.is_file():
            profile = next((p for p in legacy_paths() if p.is_file()), None)
        assignments = assignment_path()
        selected = []
        for kind, path, archive_name in (
            ('profiles', profile, 'planner/plan_profiles.json'),
            ('assignments', assignments if assignments.is_file() else None,
             'planner/plan_student_assignments.json')):
            if path is None:
                continue
            if not path.is_file() or path.stat().st_size > 4_000_000:
                raise ValueError(f'{kind} dosyası okunamıyor veya aşırı büyük.')
            payload = path.read_bytes()
            value = json.loads(payload.decode('utf-8'))
            if not isinstance(value, dict):
                raise ValueError(f'{kind} dosyası JSON nesnesi değil.')
            if kind == 'profiles' and not all(isinstance(v, dict) for v in value.values()):
                raise ValueError('Plan profilleri hatalı; yedekleme iptal edildi.')
            if kind == 'assignments' and not all(isinstance(k, str) and isinstance(v, str)
                                                 for k, v in value.items()):
                raise ValueError('Profil eşleştirmeleri hatalı; yedekleme iptal edildi.')
            selected.append((archive_name, payload))
        if selected and not any(name.endswith('plan_profiles.json') for name, _ in selected):
            raise ValueError('Öğrenci eşleştirmesi var ama profil bulunamadı.')
        return selected

    @staticmethod
    def verify_backup(archive_path):
        """Verify manifest, hashes, ZIP and SQLite header; never restore/write."""
        try:
            with zipfile.ZipFile(archive_path) as z:
                if z.testzip() is not None:
                    raise ValueError('ZIP CRC doğrulaması başarısız.')
                manifest = json.loads(z.read('backup_manifest.json'))
                if manifest.get('format_version') not in (1, 2):
                    raise ValueError('Yedek biçimi desteklenmiyor.')
                entries = manifest.get('files', [])
                if not entries or not isinstance(entries, list):
                    raise ValueError('Yedekte veritabanı bulunamadı.')
                seen = set()
                for item in entries:
                    name = item['name']
                    if (not isinstance(name,str) or name in seen or name.startswith('/')
                            or '..' in Path(name).parts or name not in z.namelist()):
                        raise ValueError('Yedek dosya adı geçersiz veya tekrarlı.')
                    seen.add(name)
                    data = z.read(name)
                    if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                        raise ValueError('Yedek SHA256 doğrulaması başarısız.')
                    if item.get('type','sqlite') == 'sqlite' and not data.startswith(b'SQLite format 3\0'):
                        raise ValueError('SQLite yedeği geçersiz.')
                return True, f'Doğrulandı: {len(entries)} dosya; geri yükleme yapılmadı.'
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            return False, f'Yedek doğrulanamadı: {exc}'

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

                # Add student scheduling profiles and assignments to the SAME
                # manifest. This remains compatible with old DB-only v1 backups.
                planner_files = self._collect_profile_files()
                if planner_files:
                    metadata['format_version'] = 2
                for arcname, payload in planner_files:
                    staged_path = scratch / arcname.replace('/', '_')
                    staged_path.write_bytes(payload)
                    metadata['files'].append({
                        'name': arcname, 'type': 'json', 'bytes': len(payload),
                        'sha256': hashlib.sha256(payload).hexdigest()})
                    staged.append((staged_path, arcname))

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
            return True, f"Yedek oluşturuldu ({len(db_paths)} veritabanı, {len(planner_files)} rutin/eşleştirme dosyası; şifresiz ZIP):\n{final_zip}"
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
