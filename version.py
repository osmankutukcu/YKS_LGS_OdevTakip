# -*- coding: utf-8 -*-
"""
YKS/LGS Ödev & Takip Yöneticisi - Sürüm Bilgileri ve Karşılaştırma Yardımcıları
"""

import re
from typing import Tuple

# Mevcut Uygulama Sürümü
APP_VERSION = "3.5.8"
APP_BUILD_DATE = "2026-10-10"

# GitHub Deposu (KullanıcıAdı / DepoAdı)
GITHUB_REPO = "osmankutukcu/YKS_LGS_OdevTakip"

# Güncelleme Kontrol URL'leri
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RAW_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/version.json"


def parse_version(ver_str: str) -> Tuple[int, ...]:
    """
    'v3.5.4', '3.5.0', 'v4.0' gibi sürüm dizgelerini tam sayı demetine çevirir.
    Örnek: 'v3.5.4' -> (3, 5, 4)
    """
    if not ver_str:
        return (0, 0, 0)
    clean = re.sub(r'^[vV]', '', str(ver_str).strip())
    parts = []
    for chunk in clean.split('.'):
        digits = re.findall(r'\d+', chunk)
        if digits:
            parts.append(int(digits[0]))
        else:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(remote_ver: str, local_ver: str = APP_VERSION) -> bool:
    """
    Uzak sürüm yerel sürümden daha yeni ise True döndürür.
    Örnek: is_newer_version("3.6.0", "3.5.0") -> True
    """
    return parse_version(remote_ver) > parse_version(local_ver)
