# -*- coding: utf-8 -*-
"""GitHub Releases Windows setup updater; PyQt6 integration.

Always ask the user before installing. No zip extraction / destructive copy.
"""
import os
import sys
import ssl
import urllib.request
import json
import subprocess
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
import version
from utils.update_core import (
    INSTALLER_NAME, MAX_INSTALLER_BYTES, UpdateSecurityError, release_candidate,
    parse_checksum_file, parse_digest, allowed_redirect_url, allowed_release_url,
    user_update_directory, validate_installer, backup_sqlite_for_update,
)

_HEADERS = {'User-Agent': 'YKS-LGS-HomeworkManager-Updater/3.5.4', 'Accept': 'application/vnd.github+json'}


def _urlopen_https(url, *, timeout=15):
    # Validate both original URL and EVERY redirect, before sending the request.
    from urllib.parse import urlparse
    first = urlparse(url)
    if first.scheme != 'https' or first.hostname not in (
        'api.github.com', 'github.com'
    ):
        raise UpdateSecurityError('Baslangic HTTPS adresi beklenen GitHub sunucusu degil.')

    class _SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            h = urlparse(newurl).hostname
            if not (allowed_redirect_url(newurl) or
                    (h == 'api.github.com' and newurl.startswith('https://api.github.com/'))):
                raise UpdateSecurityError('GitHub baglantisi izinsiz sunucuya yonlendirildi.')
            return super().redirect_request(req, fp, code, msg, hdrs, newurl)

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        _SafeRedirect(),
    )
    request = urllib.request.Request(url, headers=_HEADERS)
    response = opener.open(request, timeout=timeout)
    final = response.geturl()
    if not (allowed_redirect_url(final) or final.startswith('https://api.github.com/')):
        response.close()
        raise UpdateSecurityError('Baglanti beklenen GitHub sunucusuna ulasmadi.')
    return response


def get_application_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_for_updates(repo=version.GITHUB_REPO, current_ver=version.APP_VERSION):
    api_url = f'https://api.github.com/repos/{repo}/releases/latest'
    result = {'has_update': False, 'error': None, 'current_version': current_ver,
              'latest_version': current_ver}
    try:
        with _urlopen_https(api_url, timeout=12) as r:
            data = json.loads(r.read(1024 * 1024).decode('utf-8'))
        result = release_candidate(data, repo, current_ver)
    except Exception as exc:
        result['error'] = f'GitHub sürüm kontrolü başarısız: {exc}'
    return result


class UpdateCheckerThread(QThread):
    check_completed = pyqtSignal(dict)
    check_failed = pyqtSignal(str)

    def __init__(self, repo=version.GITHUB_REPO, parent=None):
        super().__init__(parent)
        self.repo = repo

    def run(self):
        try:
            res = check_for_updates(self.repo)
            if res.get('error') and not res.get('has_update'):
                self.check_failed.emit(res['error'])
            else:
                self.check_completed.emit(res)
        except Exception as exc:
            self.check_failed.emit(str(exc))


def _expected_hash(info):
    h = parse_digest(info.get('sha256'))
    if h:
        return h
    sidecar = info.get('checksum_url') or ''
    if not allowed_release_url(sidecar, version.GITHUB_REPO):
        raise UpdateSecurityError('SHA-256 doğrulama dosyası güvenilir değil / bulunamadı.')
    with _urlopen_https(sidecar, timeout=12) as resp:
        data = resp.read(2048)
    return parse_checksum_file(data, INSTALLER_NAME)


class UpdateDownloaderThread(QThread):
    progress = pyqtSignal(int, int, float)
    download_completed = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def __init__(self, update_info, dest_dir=None, parent=None):
        super().__init__(parent)
        self.update_info = dict(update_info)
        self.dest_dir = Path(dest_dir) if dest_dir else user_update_directory()
        self._is_cancelled = False
        self.verified_digest = None

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        path = None
        try:
            if not self.update_info.get('installable'):
                raise UpdateSecurityError('Sürüm henüz doğrulanabilir kurulum paketi içermiyor.')
            url = self.update_info.get('download_url', '')
            if not allowed_release_url(url, version.GITHUB_REPO) or not url.endswith('/' + INSTALLER_NAME):
                raise UpdateSecurityError('Beklenmeyen indirme bağlantısı.')
            expected_size = int(self.update_info.get('file_size') or 0)
            if not (0 < expected_size <= MAX_INSTALLER_BYTES):
                raise UpdateSecurityError('Dosya boyutu güvenli sınırın dışında.')
            checksum = _expected_hash(self.update_info)
            self.dest_dir.mkdir(parents=True, exist_ok=True)
            path = self.dest_dir / (INSTALLER_NAME + '.part')
            with _urlopen_https(url, timeout=40) as response, path.open('wb') as output:
                downloaded = 0
                while True:
                    if self._is_cancelled:
                        raise UpdateSecurityError('İndirme iptal edildi.')
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > expected_size:
                        raise UpdateSecurityError('Kurulum beklenen boyuttan büyük.')
                    output.write(chunk)
                    self.progress.emit(downloaded, expected_size, downloaded * 100 / expected_size)
            if self._is_cancelled:
                raise UpdateSecurityError('İndirme iptal edildi.')
            dest = self.dest_dir / INSTALLER_NAME
            # Verify before rename and again immediately before execution.
            from utils.update_core import checksum_of_file
            if downloaded != expected_size or checksum_of_file(path) != checksum:
                raise UpdateSecurityError('İndirme bütünlük doğrulaması başarısız.')
            with path.open('rb') as fh:
                if fh.read(2) != b'MZ':
                    raise UpdateSecurityError('Kurulum dosyası Windows EXE değil.')
            os.replace(path, dest)
            self.verified_digest = checksum
            self.download_completed.emit(str(dest))
        except Exception as exc:
            if path is not None:
                try: path.unlink(missing_ok=True)
                except OSError: pass
            self.download_failed.emit(str(exc))


def backup_database_before_update(app_dir=None):
    # Never guess a DB from the installation directory.
    import db
    return [str(backup_sqlite_for_update(db.DB_PATH))]


def prepare_staging_directory(*_args, **_kwargs):
    raise UpdateSecurityError('ZIP hot-swap kaldırıldı; doğrulanmış kurulum EXE kullanılmalı.')


def apply_update_and_restart(installer_path, expected_hash, expected_size):
    """Launch verified Windows installer after successful online backup."""
    if not sys.platform.startswith('win') or not getattr(sys, 'frozen', False):
        raise UpdateSecurityError('Otomatik kurulum yalnızca kurulu Windows EXE sürümünde kullanılabilir.')
    validate_installer(installer_path, expected_hash, expected_size)
    backup_database_before_update()
    installer = Path(installer_path).resolve()
    # Inno Setup keeps current AppId to install in-place. Avoid killing python.exe.
    subprocess.Popen([str(installer), '/NORESTART', '/CLOSEAPPLICATIONS'],
                     cwd=str(installer.parent), close_fds=True)
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.quit()
    return True
