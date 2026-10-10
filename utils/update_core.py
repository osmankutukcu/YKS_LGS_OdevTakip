# -*- coding: utf-8 -*-
"""Windows Inno Setup Releases updater: pure-python security and backup helpers.

No GUI, no background installer actions. Release assets are from the configured
GitHub repository; a SHA256 sidecar or GitHub asset digest is required.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile
import datetime
import shutil
from pathlib import Path
from urllib.parse import urlparse

INSTALLER_NAME = 'OdevTakip_v2_Kurulum.exe'
CHECKSUM_NAME = INSTALLER_NAME + '.sha256'
MAX_INSTALLER_BYTES = 1_500_000_000
VERSION_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$', re.I)
HEX_RE = re.compile(r'^[a-f0-9]{64}$', re.I)


class UpdateSecurityError(ValueError):
    pass


def user_update_directory():
    """Writable download/backup dir independent from Program Files."""
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'YKS_LGS_HomeworkManager' / 'updates'


def strictly_newer(remote, local):
    m1, m2 = VERSION_RE.fullmatch(str(remote).strip()), VERSION_RE.fullmatch(str(local).strip())
    return bool(m1 and m2 and tuple(map(int, m1.groups())) > tuple(map(int, m2.groups())))


def allowed_release_url(url, repo):
    """Reject source ZIP, http, off-domain, or another repository releases."""
    u = urlparse(str(url))
    return (u.scheme == 'https' and u.hostname == 'github.com' and not u.username
            and not u.password and (u.port in (None, 443))
            and u.path.startswith('/' + repo + '/releases/download/')
            and '..' not in u.path and '\\' not in u.path)


def allowed_redirect_url(url):
    u = urlparse(str(url))
    host = (u.hostname or '').lower()
    return (u.scheme == 'https' and not u.username and not u.password
            and (u.port is None or u.port == 443)
            and (host == 'github.com' or host in ('objects.githubusercontent.com',
                                                  'release-assets.githubusercontent.com')))


def parse_digest(value):
    value = str(value or '').strip()
    if value.startswith('sha256:'):
        value = value[7:]
    return value.lower() if HEX_RE.fullmatch(value) else None


def parse_checksum_file(content, filename=INSTALLER_NAME):
    """Parse sha256sum-style file; reject ambiguous or wrong-file lines."""
    try:
        lines = content.decode('utf-8-sig').strip().splitlines() if isinstance(content, bytes) else str(content).strip().splitlines()
    except UnicodeError as exc:
        raise UpdateSecurityError('SHA-256 dosyası okunamadı') from exc
    if len(lines) != 1:
        raise UpdateSecurityError('SHA-256 dosyasında tek satır olmalı')
    match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?([^\\/\r\n]+)', lines[0].strip())
    if not match or match.group(2) != filename:
        raise UpdateSecurityError('SHA-256 dosyasının adı / içeriği uyuşmuyor')
    return match.group(1).lower()


def release_candidate(release, repo, installed_version):
    """Known installer asset only: never use github zipball source archives."""
    tag = str(release.get('tag_name') or '').strip()
    if not VERSION_RE.fullmatch(tag):
        raise UpdateSecurityError('GitHub sürüm etiketi geçersiz')
    newest = tag.lstrip('vV')
    html = f'https://github.com/{repo}/releases/tag/{tag}'
    result = {
        'has_update': strictly_newer(newest, installed_version),
        'current_version': installed_version, 'latest_version': newest,
        'release_name': release.get('name') or tag,
        'changelog': release.get('body') or 'Sürüm notu verilmemiş.',
        'published_at': str(release.get('published_at') or '')[:10],
        'html_url': html, 'download_url': '', 'checksum_url': '',
        'sha256': '', 'file_size': 0, 'installable': False, 'error': None,
    }
    if not result['has_update']:
        return result
    assets = {a.get('name'): a for a in release.get('assets', []) if isinstance(a, dict)}
    installer = assets.get(INSTALLER_NAME)
    sidecar = assets.get(CHECKSUM_NAME)
    if not installer:
        result['error'] = 'Yeni sürüm var ancak Windows kurulum dosyası henüz yayımlanmamış.'
        return result
    url = installer.get('browser_download_url', '')
    if not allowed_release_url(url, repo):
        result['error'] = 'Kurulum bağlantısı güvenli / beklenen GitHub adresi değil.'
        return result
    size = installer.get('size', 0)
    if not isinstance(size, int) or not (0 < size <= MAX_INSTALLER_BYTES):
        result['error'] = 'Kurulum dosyasının boyutu geçersiz.'
        return result
    digest = parse_digest(installer.get('digest'))
    checksum_url = (sidecar or {}).get('browser_download_url') or ''
    if checksum_url and not allowed_release_url(checksum_url, repo):
        checksum_url = ''
    if not digest and not checksum_url:
        result['error'] = 'Kurulumun SHA-256 doğrulama bilgisi henüz yayımlanmamış.'
        return result
    result.update(download_url=url, file_size=size, sha256=digest or '',
                  checksum_url=checksum_url, installable=True)
    return result


def checksum_of_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_installer(path, expected_hash, expected_size):
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != '.exe':
        raise UpdateSecurityError('İndirilen dosya Windows kurulum EXE değil.')
    if expected_size <= 0 or path.stat().st_size != expected_size:
        raise UpdateSecurityError('Kurulum dosyasının boyutu uyuşmuyor.')
    if parse_digest(expected_hash) is None or checksum_of_file(path) != expected_hash.lower():
        raise UpdateSecurityError('SHA-256 doğrulaması başarısız; kurulum engellendi.')
    with path.open('rb') as fh:
        if fh.read(2) != b'MZ':
            raise UpdateSecurityError('İndirilen dosya geçerli Windows EXE başlığı taşımıyor.')
    return True


def backup_sqlite_for_update(db_path, backup_root=None):
    """Read real live SQLite DB through SQLite backup API (handles WAL)."""
    source = Path(db_path).expanduser().resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise UpdateSecurityError('Kullanılan veritabanı bulunamadı, güncelleme durduruldu.')
    root = Path(backup_root) if backup_root else user_update_directory() / 'backups'
    root.mkdir(parents=True, exist_ok=True)
    folder = root / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir()
    dest = folder / source.name
    try:
        src = sqlite3.connect(str(source), timeout=15)
        dst = sqlite3.connect(str(dest), timeout=15)
        try:
            src.backup(dst, pages=128, sleep=.05)
        finally:
            dst.close()
            src.close()
        check = sqlite3.connect(str(dest), timeout=15)
        try:
            result = check.execute('PRAGMA quick_check').fetchone()
            if not result or result[0] != 'ok':
                raise UpdateSecurityError('Yedeklenen veritabanının bütünlük kontrolü başarısız.')
        finally:
            check.close()
        return dest
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
