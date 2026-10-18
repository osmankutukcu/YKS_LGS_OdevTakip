# -*- coding: utf-8 -*-
"""V25.0 Windows user-scoped DPAPI adapter. No WhatsApp network operations.

Security boundary: Windows account DPAPI, NOT machine scope and NOT cross-machine.
The caller is responsible for choosing a private data directory and backups.
"""
from __future__ import annotations
import ctypes
import os
from ctypes import wintypes

class PlatformProtectionUnavailable(RuntimeError):
    pass

class ProtectionError(RuntimeError):
    pass

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _input_blob(raw: bytes):
    data = bytes(raw)
    buf = ctypes.create_string_buffer(data, max(len(data), 1))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))), buf


class WindowsDPAPI:
    def __init__(self, purpose: str = "whatsapp-queue-v250"):
        if os.name != 'nt':
            raise PlatformProtectionUnavailable('DPAPI yalnızca Windows üzerinde kullanılabilir.')
        if not purpose or len(purpose) > 512:
            raise ValueError('Kasa amacı belirtilmeli.')
        self._entropy = ('EduTrack|V25.0|' + purpose).encode('utf-8')
        try:
            self._crypt = ctypes.WinDLL('crypt32', use_last_error=True)
            self._kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            blobptr = ctypes.POINTER(_DATA_BLOB)
            self._crypt.CryptProtectData.argtypes = [blobptr, wintypes.LPCWSTR, blobptr,
                ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, blobptr]
            self._crypt.CryptProtectData.restype = wintypes.BOOL
            self._crypt.CryptUnprotectData.argtypes = [blobptr, ctypes.POINTER(wintypes.LPWSTR),
                blobptr, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, blobptr]
            self._crypt.CryptUnprotectData.restype = wintypes.BOOL
            self._kernel.LocalFree.argtypes = [ctypes.c_void_p]
            self._kernel.LocalFree.restype = ctypes.c_void_p
        except (AttributeError, OSError) as exc:
            raise PlatformProtectionUnavailable('Windows DPAPI kullanılamıyor.') from exc

    def _execute(self, payload: bytes, encrypt: bool) -> bytes:
        inp, keep_in = _input_blob(payload)
        entropy, keep_ent = _input_blob(self._entropy)
        out = _DATA_BLOB()
        try:
            if encrypt:
                ok = self._crypt.CryptProtectData(ctypes.byref(inp),
                    'EduTrack WhatsApp protected data', ctypes.byref(entropy),
                    None, None, 0x01, ctypes.byref(out))
            else:
                ok = self._crypt.CryptUnprotectData(ctypes.byref(inp),
                    None, ctypes.byref(entropy), None, None, 0x01, ctypes.byref(out))
            if not ok:
                # No raw Windows exception details: may contain environment paths.
                raise ProtectionError('Korunan veri bu Windows kullanıcısıyla açılamadı; işlem durduruldu.')
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            # Retain buffers until native call returns.
            _ = (keep_in, keep_ent)
            if out.pbData:
                self._kernel.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))

    def seal(self, data: bytes) -> bytes:
        return self._execute(bytes(data), True)

    def open(self, blob: bytes) -> bytes:
        return self._execute(bytes(blob), False)
