# -*- coding: utf-8 -*-
"""Yerel masaüstü ile web paneli için bilgisayara özel gizli erişim anahtarı.

Token URL'ye eklenmez; kullanıcı güvenlik ekranından kopyalayıp panelde girer.
Rol bazlı kimlik yönetimi DEĞİLDİR: tek yönetici anahtarıdır.
"""
import os
import secrets
import hmac
from pathlib import Path

_TOKEN_CACHE = None

def _token_path():
    from os import environ
    base = Path(environ.get('LOCALAPPDATA') or (Path.home() / '.local' / 'share'))
    return base / 'YKS_LGS_Manager' / 'web_access_token'

def get_access_token():
    global _TOKEN_CACHE
    configured = os.environ.get('YKS_WEB_ACCESS_TOKEN')
    if configured is not None:
        if len(configured) < 32:
            raise RuntimeError('YKS_WEB_ACCESS_TOKEN en az 32 karakter olmalı.')
        return configured
    if _TOKEN_CACHE:
        return _TOKEN_CACHE
    destination = _token_path()
    destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w',encoding='ascii') as out:
            out.write(secrets.token_urlsafe(36))
    token = destination.read_text(encoding='ascii').strip()
    if len(token) < 32:
        raise RuntimeError('Web erişim anahtarı geçersiz; güvenli anahtar oluşturulmalı.')
    _TOKEN_CACHE = token
    return token

def authorized(presented):
    return bool(presented) and hmac.compare_digest(str(presented),get_access_token())
