# -*- coding: utf-8 -*-
"""V25.0 encrypted local credential blob vault, pilot only (Baileys remains disabled).

Not a substitute for a complete safe Baileys multi-file auth lifecycle. This
vault is not wired to Baileys or WhatsApp sending. Never logs secret material.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import tempfile

from .dpapi_v250 import WindowsDPAPI, ProtectionError

class SecureLocalVault:
    def __init__(self, folder: str, protector=None):
        untrusted_folder = Path(folder).expanduser()
        if untrusted_folder.is_symlink():
            raise ProtectionError('Bağlantı dizinine kimlik bilgisi yazılamaz.')
        self.folder = untrusted_folder.resolve()
        self.protector = protector if protector is not None else WindowsDPAPI('wa-auth-v250')
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.folder.is_symlink():
            raise ProtectionError('Bağlantı dizinine kimlik bilgisi yazılamaz.')

    def _file(self, name: str) -> Path:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', str(name)):
            raise ValueError('Geçersiz kasa kaydı adı.')
        return self.folder / (name + '.dpapi')

    def put(self, name: str, data: bytes):
        if not isinstance(data, bytes) or len(data) > 2 * 1024 * 1024:
            raise ValueError('Kasa verisi bayt olmalı ve 2 MB sınırını aşmamalı.')
        target = self._file(name)
        if target.is_symlink():
            raise ProtectionError('Bağlantı dosyasına kimlik bilgisi yazılamaz.')
        sealed = self.protector.seal(data)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.folder, prefix='.private_', delete=False) as f:
                temp = Path(f.name)
                os.chmod(f.name, 0o600)
                f.write(b'ODEVTAKIP-DPAPI-VAULT-V1\n' + sealed)
                f.flush(); os.fsync(f.fileno())
            os.replace(temp, target)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()

    def get(self, name: str) -> bytes:
        target = self._file(name)
        if target.is_symlink():
            raise ProtectionError('Bağlantı dosyasından kimlik bilgisi okunamaz.')
        raw = target.read_bytes()
        magic = b'ODEVTAKIP-DPAPI-VAULT-V1\n'
        if not raw.startswith(magic):
            raise ProtectionError('Kasa dosyasının biçimi bozuk.')
        return self.protector.open(raw[len(magic):])

    def delete(self, name: str) -> bool:
        """Removes entry; snapshots/backups could retain copies."""
        target = self._file(name)
        if target.is_symlink():
            raise ProtectionError('Bağlantı dosyası silme reddedildi.')
        try:
            target.unlink()
            return True
        except FileNotFoundError:
            return False
