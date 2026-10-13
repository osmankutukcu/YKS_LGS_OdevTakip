# -*- coding: utf-8 -*-
"""Resmî sitelere güvenli navigasyon ve bağlantı kontrolü.

Bu katman ÖSYM/YÖK veri çıkarmaz, öngörü sıralaması hesaplamaz,
öğrenci kimliği/adı/neti göndermez. HTTP yanıtı sadece erişim sinyalidir.
"""
from __future__ import annotations
from urllib.parse import urlsplit

_URLS = {
    'YKS': 'https://yokatlas.yok.gov.tr/netler-tablo.php',
    'YKS_OSYM': 'https://www.osym.gov.tr/SinavGrubu/Index/2',
    'LGS': 'https://www.meb.gov.tr/',
}


def official_source(exam_type: str) -> tuple[str, str]:
    if (exam_type or '').strip().upper().startswith('YKS'):
        return 'YÖK Atlas – TYT/AYT Net Sihirbazı', _URLS['YKS']
    return 'Millî Eğitim Bakanlığı', _URLS['LGS']


def safe_official_url(exam_type: str) -> str:
    return official_source(exam_type)[1]


def is_allowlisted_url(url: str) -> bool:
    """Sabit başlangıç noktaları dışında keyfî URL/profil bilgisi gönderilmez."""
    return url in _URLS.values() and urlsplit(url).scheme == 'https'


def connectivity_description(http_code: int | None, network_error: str = '') -> str:
    if http_code is not None and 200 <= int(http_code) < 300:
        return 'Resmî web sayfasına erişildi. Program/hedef verisi otomatik doğrulanmadı.'
    if network_error:
        return 'Bağlantı kontrol edilemedi: ' + str(network_error)[:160]
    return 'Kaynağa erişim doğrulanamadı. Yerleşme verileri güncel kabul edilmedi.'
