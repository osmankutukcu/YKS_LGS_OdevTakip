# -*- coding: utf-8 -*-
"""KoçPilot 360: V3.5.87 source-only patch integrity check (offline)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile


def verify(base_file: str, patch_file: str) -> tuple[int, int]:
    with zipfile.ZipFile(base_file) as base, zipfile.ZipFile(patch_file) as patch:
        if base.testzip() is not None or patch.testzip() is not None:
            raise ValueError('ZIP CRC testi başarısız.')
        entries = patch.namelist()
        if len(entries) != len(set(entries)):
            raise ValueError('Yamada tekrar eden dosya adı var.')
        for entry in entries:
            p = PurePosixPath(entry)
            if p.is_absolute() or '..' in p.parts or '\\' in entry or entry.startswith('/'):
                raise ValueError('Güvensiz ZIP dosya yolu: ' + entry)
            lower = entry.lower()
            if lower.endswith(('.db', '.db-wal', '.db-shm', '.sqlite', '.sqlite3', '.exe', '.pem', '.key', '.env')):
                raise ValueError('Yamada veri veya gizli anahtar içerebilecek dosya var: ' + entry)
        meta = json.loads(patch.read('V3587_PATCH_MANIFEST.json'))
        if meta.get('release') != 'V3.5.87' or meta.get('manual_gui_exe_windows_mac_tested') is not False:
            raise ValueError('Sürüm veya doğrulanmamış GUI test işareti hatalı.')
        files = meta['files']
        if sorted(entries) != sorted(list(files) + ['V3587_PATCH_MANIFEST.json']):
            raise ValueError('Manifest ile ZIP dosya listesi uyuşmuyor.')
        for name, info in files.items():
            data = patch.read(name)
            if hashlib.sha256(data).hexdigest() != info['sha256'] or len(data) != info['bytes']:
                raise ValueError('Yama dosyası bütünlüğü bozuk: ' + name)
            if name.endswith('.py'):
                compile(data, name, 'exec')
        base_names = base.namelist()
        protected = meta['protected_base_files']
        if any(name in files for name in protected):
            raise ValueError('Yama korumalı bir temel dosyayı değiştirmeye çalışıyor.')
        for path, sha256 in protected.items():
            matches = [name for name in base_names if name.endswith('/'+path) or name == path]
            if len(matches) != 1 or hashlib.sha256(base.read(matches[0])).hexdigest() != sha256:
                raise ValueError('Orijinal paket veya temel dosya sürümü eşleşmiyor: ' + path)
        return len(files), len(protected)


def main(args):
    if len(args) != 3:
        print('Kullanım: python tools/v3587_release_gate.py ORIJINAL_V3580.zip BIRLESIK_V3587_PILOT.zip')
        return 2
    try:
        files, protected = verify(args[1], args[2])
    except Exception as exc:
        print('RED / YAMA KURULMAMALI:', exc)
        return 1
    print(f'GEÇTİ: {files} kaynak/test/not dosyası, {protected} korumalı kaynak; veri/gizli dosya yok.')
    print('Bu kontrol GUI, EXE, Windows/macOS yazıcı veya kurum yetkisi testinin yerine geçmez.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
