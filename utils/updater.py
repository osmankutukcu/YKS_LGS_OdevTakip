# -*- coding: utf-8 -*-
"""
YKS/LGS Ödev & Takip Yöneticisi - Otomatik Güncelleme Motoru (Auto-Updater)
- GitHub Releases ve Raw JSON Çift Katmanlı Kontrol
- Asenkron QThread İndirme ve Canlı İlerleme Bildirimi
- Veritabanı ve Lisans Koruma Garantisi (Otomatik Ön-Yedekleme)
- Windows Çalışırken Değiştirme (Hot-Swap) ve Otomatik Yeniden Başlatma
"""

import os
import sys
import json
import shutil
import zipfile
import datetime
import subprocess
import ssl
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import QThread, pyqtSignal

import version

def _get_ssl_context():
    """Güvenli ve sertifika uyumlu SSL context döndürür."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        pass
    return ssl._create_unverified_context()

PROTECTED_EXTENSIONS = {".db", ".sqlite", ".sqlite3", ".lic", ".key"}
PROTECTED_FILENAMES = {
    "license.json", "config.json", "YKS_LGS_HomeworkManager.db",
    "YKS_LGS_HomeworkManager v2.db", "YKS_Kazanimlar.sqlite"
}


def get_application_root() -> str:
    """Uygulamanın çalıştığı kök dizini verir."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_for_updates(repo: str = version.GITHUB_REPO, current_ver: str = version.APP_VERSION) -> Dict[str, Any]:
    """
    GitHub Releases API veya Raw version.json üzerinden en son sürümü denetler.
    Dönüş:
      {
         "has_update": bool,
         "current_version": str,
         "latest_version": str,
         "release_name": str,
         "changelog": str,
         "download_url": str,
         "file_size": int,
         "published_at": str,
         "html_url": str
      }
    """
    result = {
        "has_update": False,
        "current_version": current_ver,
        "latest_version": current_ver,
        "release_name": "",
        "changelog": "",
        "download_url": "",
        "file_size": 0,
        "published_at": "",
        "html_url": f"https://github.com/{repo}/releases",
        "error": None
    }

    headers = {
        "User-Agent": "YKS-LGS-HomeworkManager-Updater/3.5",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. Deneme: GitHub Releases API
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    release_data = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8, context=_get_ssl_context()) as resp:
            if resp.status == 200:
                release_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        # API 404 veya rate-limit hatası durumunda 2. denemeye geç
        pass

    if release_data:
        tag_name = release_data.get("tag_name", "")
        clean_tag = tag_name.lstrip("vV")
        result["latest_version"] = clean_tag
        result["release_name"] = release_data.get("name") or f"Sürüm {tag_name}"
        result["changelog"] = release_data.get("body") or "Bu sürüm için detaylı not bulunmuyor."
        result["published_at"] = release_data.get("published_at", "")[:10]
        result["html_url"] = release_data.get("html_url", result["html_url"])

        # Zip asset'i ara
        assets = release_data.get("assets", [])
        for asset in assets:
            a_name = asset.get("name", "").lower()
            if a_name.endswith(".zip") or a_name.endswith(".exe"):
                result["download_url"] = asset.get("browser_download_url", "")
                result["file_size"] = asset.get("size", 0)
                break

        # Eğer release assets boşsa doğrudan zipball kullanabilir
        if not result["download_url"] and release_data.get("zipball_url"):
            result["download_url"] = release_data["zipball_url"]

        if version.is_newer_version(clean_tag, current_ver):
            result["has_update"] = True
            return result

    # 2. Deneme: Raw version.json (Rate-Limit Riski Sıfır)
    raw_url = f"https://raw.githubusercontent.com/{repo}/main/version.json"
    try:
        req_raw = urllib.request.Request(raw_url, headers=headers)
        with urllib.request.urlopen(req_raw, timeout=8, context=_get_ssl_context()) as resp:
            if resp.status == 200:
                raw_data = json.loads(resp.read().decode("utf-8"))
                remote_ver = raw_data.get("version", "").lstrip("vV")
                result["latest_version"] = remote_ver
                result["release_name"] = raw_data.get("name", f"Sürüm v{remote_ver}")
                result["changelog"] = raw_data.get("changelog", "")
                result["download_url"] = raw_data.get("download_url", "")
                result["file_size"] = raw_data.get("file_size", 0)
                result["published_at"] = raw_data.get("published_at", "")

                if version.is_newer_version(remote_ver, current_ver):
                    result["has_update"] = True
                    return result
    except Exception as e:
        if not release_data:
            result["error"] = str(e)

    return result


class UpdateCheckerThread(QThread):
    """Arka planda UI'ı kilitlemeden güncelleme kontrolü yapan thread."""
    check_completed = pyqtSignal(dict)
    check_failed = pyqtSignal(str)

    def __init__(self, repo: str = version.GITHUB_REPO, parent=None):
        super().__init__(parent)
        self.repo = repo

    def run(self):
        try:
            res = check_for_updates(self.repo)
            self.check_completed.emit(res)
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDownloaderThread(QThread):
    """Güncelleme dosyasını parça parça indirip canlı ilerleme yayan thread."""
    progress = pyqtSignal(int, int, float)  # indirilen_bytes, toplam_bytes, yuzde
    download_completed = pyqtSignal(str)   # indirilen zip dosyasının yolu
    download_failed = pyqtSignal(str)

    def __init__(self, download_url: str, dest_dir: str = None, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.dest_dir = dest_dir or get_application_root()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not self.download_url:
                raise ValueError("İndirme bağlantısı bulunamadı.")

            os.makedirs(self.dest_dir, exist_ok=True)
            save_path = os.path.join(self.dest_dir, "_downloaded_update.zip")
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception:
                    pass

            req = urllib.request.Request(self.download_url, headers={
                "User-Agent": "YKS-LGS-HomeworkManager-Updater/3.5"
            })

            with urllib.request.urlopen(req, timeout=30, context=_get_ssl_context()) as response, open(save_path, "wb") as out_file:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB

                while True:
                    if self._is_cancelled:
                        out_file.close()
                        if os.path.exists(save_path):
                            os.remove(save_path)
                        self.download_failed.emit("İndirme kullanıcı tarafından iptal edildi.")
                        return

                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    out_file.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        pct = (downloaded / total_size) * 100.0
                    else:
                        pct = 0.0

                    self.progress.emit(downloaded, total_size, pct)

            self.download_completed.emit(save_path)

        except Exception as e:
            self.download_failed.emit(f"İndirme hatası: {str(e)}")


def backup_database_before_update(app_dir: str = None) -> List[str]:
    """
    Güncelleme öncesi mevcut tüm .db ve veritabanı dosyalarını backups/ klasörüne
    zaman damgalı olarak güvenle kopyalar.
    """
    root = app_dir or get_application_root()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = os.path.join(root, "backups", f"guncelleme_yedegi_{ts}")
    os.makedirs(backup_folder, exist_ok=True)

    backed_up = []
    try:
        for f in os.listdir(root):
            lower = f.lower()
            if lower.endswith(".db") or lower.endswith(".sqlite") or lower.endswith(".sqlite3"):
                src = os.path.join(root, f)
                if os.path.isfile(src):
                    dst = os.path.join(backup_folder, f)
                    shutil.copy2(src, dst)
                    backed_up.append(dst)
    except Exception as e:
        print(f"Yedekleme uyarısı: {e}")

    return backed_up


def prepare_staging_directory(zip_path: str, app_dir: str = None) -> str:
    """
    İndirilen zip paketini _update_staging klasörüne açar.
    GÜVENLİK: Paketin içinde yanlışlıkla bile olsa .db veya lisans dosyası
    varsa onları staging klasöründen kesin olarak siler!
    """
    root = app_dir or get_application_root()
    staging_dir = os.path.join(root, "_update_staging")

    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir, ignore_errors=True)
    os.makedirs(staging_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(staging_dir)

    # Eğer zip içinde tek bir üst klasör varsa (örn. YKS_LGS_HomeworkManager_v2/)
    entries = os.listdir(staging_dir)
    if len(entries) == 1:
        single_path = os.path.join(staging_dir, entries[0])
        if os.path.isdir(single_path):
            # Dosyaları bir üst basamağa (staging_dir köküne) taşı
            for item in os.listdir(single_path):
                shutil.move(os.path.join(single_path, item), staging_dir)
            os.rmdir(single_path)

    # GÜVENLİK FİLTRESİ: Kullanıcı veritabanlarını ve lisanslarını asla ezme!
    for root_dir, dirs, files in os.walk(staging_dir):
        for f in files:
            f_lower = f.lower()
            _, ext = os.path.splitext(f_lower)
            if ext in PROTECTED_EXTENSIONS or f_lower in PROTECTED_FILENAMES:
                safe_delete_path = os.path.join(root_dir, f)
                try:
                    os.remove(safe_delete_path)
                    print(f"Güvenlik gereği korumalı dosya güncelleme paketinden elendi: {f}")
                except Exception:
                    pass

    return staging_dir


def apply_update_and_restart(app_dir: str = None) -> bool:
    """
    Windows üzerinde update_helper.bat veya macOS üzerinde update_helper.sh
    yardımcısını oluşturup arka planda başlatır ve mevcut uygulamayı kapatır.
    """
    root = app_dir or get_application_root()
    staging_dir = os.path.join(root, "_update_staging")
    if not os.path.exists(staging_dir):
        return False

    # 1. Adım: Veritabanı ön-yedeğini al
    backup_database_before_update(root)

    # 2. Adım: İşletim sistemine uygun yardımcısını oluştur
    if sys.platform.startswith("win"):
        helper_path = os.path.join(root, "update_helper.bat")
        bat_content = f"""@echo off
chcp 65001 >nul
title YKS/LGS Odev Takip Yoneticisi - Guncelleme
cls
echo ========================================================
echo   YKS/LGS Odev Takip Yoneticisi Guncelleniyor...
echo ========================================================
echo Eski surumun kapanmasi bekleniyor...
timeout /t 2 /nobreak >nul
taskkill /F /IM OdevTakip_v2.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo Yeni surum dosyalari kopyalaniyor...
xcopy /s /e /y "{staging_dir}\\*" "{root}\\" >nul

echo Gecici yukleme dosyalari temizleniyor...
rmdir /s /q "{staging_dir}" >nul
if exist "{os.path.join(root, '_downloaded_update.zip')}" del /f /q "{os.path.join(root, '_downloaded_update.zip')}" >nul

echo ========================================================
echo Guncelleme basariyla tamamlandi!
echo Uygulama yeniden baslatiliyor...
echo ========================================================
timeout /t 1 /nobreak >nul

if exist "{root}\\OdevTakip_v2.exe" (
    start "" "{root}\\OdevTakip_v2.exe"
) else if exist "{root}\\Başlat_Windows.bat" (
    start "" "{root}\\Başlat_Windows.bat"
) else (
    start "" python app.py
)

:: Yardimci betik kendini siler
(goto) 2>nul & del "%~f0"
"""
        with open(helper_path, "w", encoding="utf-8") as f:
            f.write(bat_content)

        subprocess.Popen(
            ["cmd.exe", "/c", helper_path],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            close_fds=True
        )

    else:
        # macOS / Linux desteği
        helper_path = os.path.join(root, "update_helper.sh")
        sh_content = f"""#!/bin/bash
sleep 2
pkill -f "python.*app.py" 2>/dev/null
cp -R "{staging_dir}/"* "{root}/"
rm -rf "{staging_dir}"
rm -f "{os.path.join(root, '_downloaded_update.zip')}"
if [ -f "{root}/Başlat.command" ]; then
    open "{root}/Başlat.command"
elif [ -f "{root}/app.py" ]; then
    python3 "{root}/app.py" &
fi
rm -f "$0"
"""
        with open(helper_path, "w", encoding="utf-8") as f:
            f.write(sh_content)
        os.chmod(helper_path, 0o755)

        subprocess.Popen(["/bin/bash", helper_path], close_fds=True)

    # 3. Adım: Mevcut uygulamadan çık
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        app.quit()
    sys.exit(0)
    return True
