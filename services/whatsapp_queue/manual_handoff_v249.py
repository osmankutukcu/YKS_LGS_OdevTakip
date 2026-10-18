# -*- coding: utf-8 -*-
"""V24.9: bilinçli, TEK alıcılık WhatsApp sohbet bağlantısı devri.

Gönderim/tıklama/teslim onayı yoktur. İş UNKNOWN yapılır;
otomatik tekrar veya farklı taşıyıcıya otomatik geçiş YOKTUR.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

from .queue_v246 import SafeWhatsAppQueue, UNKNOWN, PENDING
from .transport_v249 import MANUAL_LINKS, validate_choice, open_chat_link

@dataclass(frozen=True)
class ManualHandoff:
    attempted: bool
    detail: str
    pending: int


def open_one_pending_chat(queue: SafeWhatsAppQueue, batch: str, method: str,
                          opener: Optional[Callable[[str], object]] = None) -> ManualHandoff:
    validate_choice(method)
    if method not in MANUAL_LINKS:
        raise ValueError('Bu yordam yalnızca manuel sohbet bağlantısı içindir.')
    job = queue.claim_next(batch)
    if job is None:
        return ManualHandoff(False, 'Bekleyen mesaj yok.', 0)
    # Job IN_FLIGHT iken uygulama kapansa kurtarma UNKNOWN yapar; tekrar göndermez.
    try:
        open_chat_link(method, str(job['recipient']), str(job['message']), opener=opener)
        detail = 'Sohbet açılması istendi; gönderim ve teslim doğrulanamadı.'
    except Exception:
        # Browser/OS çağrısı kısmen gerçekleşmiş olabilir; FAILED diye tekrar
        # denenebilir iş üretmiyoruz ve kişisel veri içeren hatayı yazmıyoruz.
        detail = 'Sohbet açma sonucu bilinmiyor; öğretmen kontrol etmelidir.'
    queue.finish(job['id'], job['attempt_token'], UNKNOWN, detail)
    return ManualHandoff(True, detail, queue.counts(batch).get(PENDING, 0))
