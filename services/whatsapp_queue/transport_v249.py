# -*- coding: utf-8 -*-
"""V24.9 - WhatsApp gönderim yöntemi seçici.

Bu dosya kendiliğinden gönderim yapmaz. Sohbet bağlantısını açmak
mesaj gönderildi/teslim edildi anlamına GELMEZ. Alternatif kanallar
üzerinden sonucu belirsiz işi tekrar göndermek YASAKTIR.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import sys
import urllib.parse
import webbrowser
from typing import Callable

SELENIUM = 'selenium'
DESKTOP_LINK = 'desktop_link'
WEB_LINK = 'web_link'
HEADLESS_DISABLED = 'headless_quarantine'
BAILEYS_BULK = 'baileys_bulk_v258'
MANUAL_LINKS = frozenset((DESKTOP_LINK, WEB_LINK))

@dataclass(frozen=True)
class TransportChoice:
    key: str
    label: str
    explanation: str
    automated: bool
    enabled: bool

CHOICES = (
    TransportChoice(SELENIUM, 'Selenium – eski otomatik gönderim',
        'Mevcut otomatik yol; Chrome/Selenium bileşenleri gerekir. Teslimat doğrulanamaz.', True, True),
    TransportChoice(DESKTOP_LINK, 'WhatsApp Masaüstü – sohbeti aç',
        'Ek Selenium gerekmez. Her tıklamada yalnızca bir sohbet açılır; Gönder öğretmene aittir.', False, True),
    TransportChoice(WEB_LINK, 'WhatsApp Web – sohbeti aç',
        'Ek Selenium gerekmez. Her tıklamada yalnızca bir sohbet açılır; Gönder öğretmene aittir.', False, True),
    TransportChoice(BAILEYS_BULK, 'Baileys – izinli toplu gönderim (Windows / pilot)',
        'En fazla 150 izinli farklı telefon; QR, onay, kontrollü 20 sn aralık. Resmî API değildir.', True, True),
    TransportChoice(HEADLESS_DISABLED, 'Arka plan (Baileys) – güvenlik nedeniyle kapalı',
        'Oturum kasası ve gerçek Windows testleri tamamlanmadı. Bu kanal kullanılamaz.', True, False),
)
CHOICE_BY_KEY = {t.key: t for t in CHOICES}

class UnsafeTransportError(RuntimeError):
    pass

def validate_choice(key: str) -> TransportChoice:
    choice = CHOICE_BY_KEY.get(key)
    if choice is None or not choice.enabled:
        raise UnsafeTransportError('Bu gönderim yöntemi kullanılabilir değil; kuyruk korunuyor.')
    return choice

def chat_url(method: str, phone: str, message: str) -> str:
    if method not in MANUAL_LINKS:
        raise UnsafeTransportError('Sohbet bağlantısı yalnızca manuel yöntemlerle açılabilir.')
    if not re.fullmatch(r'[1-9][0-9]{7,14}', str(phone)):
        raise ValueError('Telefon numarası E.164 biçiminde değil.')
    text = str(message or '')
    if not text.strip():
        raise ValueError('Mesaj boş.')
    params = urllib.parse.urlencode({'phone': str(phone), 'text': text})
    if method == DESKTOP_LINK:
        return 'whatsapp://send?' + params
    return 'https://web.whatsapp.com/send?' + params

def open_chat_link(method: str, phone: str, message: str,
                   opener: Callable[[str], object] | None = None) -> None:
    """Yalnızca sohbet açma talebi verir. GÖNDERME yapmaz.

    Bu işlemden sonra mesaj sonucu kesinlikle bilinmez. Çağıran taraf
    bu işi UNKNOWN olarak işaretlemeli ve tekrar denememelidir.
    """
    url = chat_url(method, phone, message)
    if opener is not None:
        opener(url)
    elif method == DESKTOP_LINK:
        if sys.platform == 'win32':
            os.startfile(url)
        elif sys.platform == 'darwin':
            import subprocess
            subprocess.Popen(['open', url], close_fds=True)
        else:
            webbrowser.open(url, new=0)
    else:
        webbrowser.open(url, new=0)
