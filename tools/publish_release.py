# -*- coding: utf-8 -*-
"""Offline local Release staging: copy EXISTING Inno Setup exe + SHA256.
No version rewriting and no source ZIP pretending to be a Windows update.
"""
from pathlib import Path
import shutil
from tools.validate_release import read_versions, emit_checksum

ROOT = Path(__file__).resolve().parent.parent


def create_release_package(ver=None, notes=''):
    actual = read_versions(ROOT)
    if ver and ver.lstrip('vV') != actual:
        raise ValueError(f'Surum uyusmazligi: talep {ver}, proje {actual}')
    installer = ROOT / 'dist' / 'OdevTakip_v2_Kurulum.exe'
    if not installer.is_file():
        raise FileNotFoundError('Once Windows EXE ve Inno Setup installer uretmelisiniz: ' + str(installer))
    target = ROOT / 'dist_release'
    target.mkdir(exist_ok=True)
    copied = target / installer.name
    shutil.copy2(installer, copied)
    digest = emit_checksum(copied)
    print('Release surumu:', actual)
    print('GitHub tag: v' + actual)
    print('Kurulum:', copied)
    print('Checksum:', digest)
    print('Not: GitHub Releases otomatik yayini, v' + actual + ' etiketini push edince GitHub Actions tarafindan yapilir.')
    return str(copied)


if __name__ == '__main__':
    import sys
    create_release_package(sys.argv[1] if len(sys.argv) > 1 else None)
