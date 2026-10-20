"""Curriculum Catalog Registry for KocPilot 360.

Provides modular switching between MEB curricula:
- MEB YKS Tam Müfredat (861 Kazanım, Tüm Dersler)
- Türkiye Yüzyılı Maarif Modeli (tymm.meb.gov.tr)
- Klasik TTKB Pilot (Numune - 4 Kazanım)
- Devre Dışı (Kullanıcı tarafından kapatılmış)

Persists preference safely via SQLite ayar table.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.coach_curriculum_v7 import load_catalog

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

CATALOG_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "yks_full": {
        "id": "yks_full",
        "title": "MEB YKS Tam Müfredat (Tüm Dersler - 861 Kazanım)",
        "short_title": "MEB YKS Tam Müfredat",
        "path": ASSETS_DIR / "coach_curriculum_yks_full.json",
        "official_domain": "mufredat.meb.gov.tr",
        "source_name": "MEB Talim ve Terbiye Kurulu Resmî YKS Programı",
        "description": "Fizik, Kimya, Biyoloji, Matematik, Türkçe, Edebiyat, Tarih, Coğrafya ve Felsefe derslerinin tüm 9, 10, 11 ve 12. sınıf resmi MEB kazanımlarını kapsar.",
        "badge": "🟢 Aktif (861 Kazanım)",
        "enabled": True,
    },
    "maarif_modeli": {
        "id": "maarif_modeli",
        "title": "Türkiye Yüzyılı Maarif Modeli (Kademeli Yeni Müfredat)",
        "short_title": "Türkiye Yüzyılı Maarif Modeli",
        "path": ASSETS_DIR / "coach_curriculum_maarif.json",
        "official_domain": "tymm.meb.gov.tr",
        "source_name": "MEB Talim ve Terbiye Kurulu (Maarif Modeli)",
        "description": "Yeni Maarif Modeli beceri ve kazanım temelli çerçevesi. Kademeli yürürlüğe giren yeni öğretim programlarını içerir.",
        "badge": "📘 Maarif Modeli",
        "enabled": True,
    },
    "meb_pilot": {
        "id": "meb_pilot",
        "title": "Klasik TTKB Pilot (Numune - 4 Kazanım)",
        "short_title": "Klasik TTKB Pilot",
        "path": ASSETS_DIR / "coach_curriculum_v7.json",
        "official_domain": "ttkbyayin.meb.gov.tr",
        "source_name": "TTKB Yayın Örnekleri",
        "description": "V7 sürümünün orijinal 4 maddelik bağlantı doğrulama pilot şablonu.",
        "badge": "🔍 Numune Pilot",
        "enabled": True,
    },
    "disabled": {
        "id": "disabled",
        "title": "Devre Dışı (Kazanım Kontrolünü Kapat)",
        "short_title": "Devre Dışı / Kapalı",
        "path": None,
        "official_domain": "-",
        "source_name": "Yok",
        "description": "Otomatik kazanım ve müfredat kontrolü kapalıdır. Yalnızca manuel koçluk notları ve standart ödevler kullanılır.",
        "badge": "⚪ Kapalı",
        "enabled": False,
    },
}

DEFAULT_CATALOG_ID = "yks_full"
SETTING_KEY = "coach_curriculum_active_catalog"

# Simple in-process cache
_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def list_available_catalogs() -> List[Dict[str, Any]]:
    """Return all catalog options for UI dropdowns or settings."""
    active_id = get_active_catalog_id()
    results = []
    for cid, meta in CATALOG_DEFINITIONS.items():
        item = dict(meta)
        item["is_active"] = (cid == active_id)
        results.append(item)
    return results


def get_active_catalog_id() -> str:
    """Read active catalog id from SQLite settings."""
    try:
        from utils.settings import ayar_get
        val = ayar_get(SETTING_KEY, DEFAULT_CATALOG_ID)
        return str(val) if str(val) in CATALOG_DEFINITIONS else DEFAULT_CATALOG_ID
    except Exception:
        return DEFAULT_CATALOG_ID


def set_active_catalog_id(catalog_id: str) -> bool:
    """Save active catalog id to SQLite settings."""
    if catalog_id not in CATALOG_DEFINITIONS:
        return False
    try:
        from utils.settings import ayar_set
        ayar_set(SETTING_KEY, str(catalog_id))
        return True
    except Exception:
        return False


def is_curriculum_enabled() -> bool:
    """True if curriculum crosswalk is currently enabled."""
    return get_active_catalog_id() != "disabled"


def get_catalog_metadata(catalog_id: Optional[str] = None) -> Dict[str, Any]:
    """Get metadata dictionary for given or active catalog."""
    cid = catalog_id or get_active_catalog_id()
    return CATALOG_DEFINITIONS.get(cid, CATALOG_DEFINITIONS[DEFAULT_CATALOG_ID])


def load_catalog_by_id(catalog_id: str) -> List[Dict[str, Any]]:
    """Load and validate catalog outcomes for a specific catalog ID."""
    if catalog_id == "disabled" or catalog_id not in CATALOG_DEFINITIONS:
        return []
    if catalog_id in _CACHE:
        return _CACHE[catalog_id]
    
    meta = CATALOG_DEFINITIONS[catalog_id]
    path = meta.get("path")
    if not path or not Path(path).is_file():
        return []
    
    data = load_catalog(path)
    _CACHE[catalog_id] = data
    return data


def get_active_catalog_data() -> List[Dict[str, Any]]:
    """Load and validate the outcomes for the currently active catalog."""
    cid = get_active_catalog_id()
    return load_catalog_by_id(cid)


def clear_cache() -> None:
    """Clear in-memory cache (e.g. after catalog rebuild)."""
    _CACHE.clear()
