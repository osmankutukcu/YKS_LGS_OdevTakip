# -*- coding: utf-8 -*-
"""V3.5.76 Baileys Windows runtime doctor (read only).

No downloads, installations, student data or WhatsApp operations occur here.
The UI separately requests consent before running an official package-manager install.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Mapping

MIN_NODE_MAJOR = 20


@dataclass(frozen=True)
class RuntimeStatus:
    ready: bool
    reason: str
    node: str = ''
    npm: str = ''
    node_version: str = ''
    winget: str = ''


def _candidates(environ: Mapping[str, str], search_path) -> list[str]:
    names = []
    # PATH is not always refreshed when the Windows MSI installation completes.
    names.append(search_path('node.exe') or search_path('node') or '')
    for root_name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        root = environ.get(root_name, '')
        if root:
            p = Path(root)
            names.extend((str(p / 'nodejs' / 'node.exe'),
                          str(p / 'Programs' / 'nodejs' / 'node.exe'),
                          str(p / 'Programs' / 'Node.js' / 'node.exe'),
                          str(p / 'Microsoft' / 'WinGet' / 'Links' / 'node.exe')))
    unique = []
    for item in names:
        if item and item.lower() not in {x.lower() for x in unique}:
            unique.append(item)
    return unique


def detect_runtime(*, platform: str | None = None,
                   environ: Mapping[str, str] | None = None,
                   which=None, run=None, is_file=None) -> RuntimeStatus:
    """Check actual binaries and versions, never trust mere PATH presence.

    Dependency injection keeps these checks testable on non-Windows CI without
    installing Node or reaching an external package registry.
    """
    platform = platform if platform is not None else sys.platform
    if platform != 'win32':
        return RuntimeStatus(False, 'Baileys Windows kurulumu yalnızca Windows üzerinde çalışır.')
    environ = dict(os.environ if environ is None else environ)
    which = shutil.which if which is None else which
    run = subprocess.run if run is None else run
    if is_file is None:
        is_file = lambda x: Path(x).is_file()
    winget = which('winget.exe') or which('winget') or ''
    checked = set()
    out_of_date = False
    for path in _candidates(environ, which):
        if path.lower() in checked:
            continue
        checked.add(path.lower())
        if not is_file(path):
            continue
        try:
            proc = run([path, '--version'], capture_output=True, text=True, timeout=6)
            version = (proc.stdout or '').strip()
            match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.+-]+)?', version)
            if proc.returncode != 0 or not match:
                continue
            if int(match.group(1)) < MIN_NODE_MAJOR:
                out_of_date = True
                continue
            # npm.cmd generally resides beside node.exe even before a newly
            # installed Node.js has been added to the calling process PATH.
            sibling = str(Path(path).parent / 'npm.cmd')
            npm = (sibling if is_file(sibling) else '') or which('npm.cmd') or which('npm') or ''
            if not npm:
                return RuntimeStatus(False, 'Node.js bulundu, ancak npm bulunamadı; Node.js LTS kurulumunu onarın.',
                                     node=path, node_version=version, winget=winget)
            # npm.cmd may be a Windows command script; subprocess.run(shell=False)
            # supports .cmd on Windows, but never interpolate user input.
            try:
                npm_result = run([npm, '--version'], capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError):
                continue
            if npm_result.returncode == 0 and re.match(r'^\d+\.\d+', (npm_result.stdout or '').strip()):
                return RuntimeStatus(True, 'Node.js ve npm çalışma ortamı hazır.',
                                     node=path, npm=npm, node_version=version, winget=winget)
        except (OSError, subprocess.SubprocessError):
            continue
    if out_of_date:
        reason = 'Node.js bulundu ancak sürümü eski (en az 20 gerekli); LTS güncellemesi gerekiyor.'
    else:
        reason = 'Node.js 20+ çalışma ortamı bulunamadı.'
    return RuntimeStatus(False, reason, winget=winget)


def enriched_path(status: RuntimeStatus, current_path: str) -> str:
    """Make the verified node.exe visible to child npm.cmd without changing OS PATH."""
    if not status.node:
        return current_path
    folder = str(Path(status.node).parent)
    # Windows drive prefixes contain ':', so use ';' even in cross-OS unit tests.
    separator = ';' if re.match(r'^[A-Za-z]:[/\\]', folder) else os.pathsep
    pieces = current_path.split(separator) if current_path else []
    if folder.casefold() in (x.casefold() for x in pieces):
        return current_path
    return folder + (separator + current_path if current_path else '')


def setup_failure_message(phase: str, exit_code: int) -> str:
    """Map local installer failure codes to plain-language next actions."""
    if phase == 'node':
        return ('Node.js LTS otomatik kurulamadı. Windows paket yöneticisi izin vermemiş '
                'veya seçilen paket bu Windows sürümüyle uyumsuz olabilir. '
                'Resmî nodejs.org sayfasından LTS kurulumu yapabilirsiniz.')
    reasons = {
        10: 'Node.js bulunamadı. Node.js LTS kurulumunu denetleyin.',
        11: 'npm bulunamadı. Node.js LTS kurulumunu onarın.',
        12: 'Node.js sürümü okunamadı. Kurulumu kontrol edin.',
        13: 'Node.js sürümü eski. En az sürüm 20 gerekir.',
        14: 'Baileys paket kurulumu kullanıcı tarafından onaylanmadı.',
        21: 'Bağımlılık kilidi hazırlanamadı. İnternet ve npm kayıt erişimini kontrol edin.',
        22: 'Baileys bağımlılıkları kurulamadı. İnternet/proxy/antivirüs izinlerini kontrol edin.',
        23: 'Baileys protokol testleri başarısız; QR ve gönderim devre dışı bırakıldı.',
    }
    return reasons.get(exit_code,
                       'Kurulum tamamlanamadı. Sistem izinlerini ve internet erişimini kontrol edin.')
