# -*- coding: utf-8 -*-
"""
services/report_settings.py

Rapor / analiz kriterlerini basit bir key-value tablo içinde saklar.
- aktarilan_sayilma_sekli : "done" | "not_done"
- gunluk_son_gun           : "30" gibi metin (int'e çevrilerek kullanılır)
- gecikmis_kume_vurgula    : "1" | "0"
"""

from __future__ import annotations
from typing import Dict, Any
import sqlite3

TABLE_NAME = "app_report_settings"

# Varsayılanlar
DEFAULT_SETTINGS: Dict[str, Any] = {
    "aktarilan_sayilma_sekli": "done",  # aktarılan ödevleri "YAPILDI" say
    "gunluk_son_gun": "30",             # son 30 gün günlük özet
    "gecikmis_kume_vurgula": "1",       # gecikmiş kümeleri vurgula (varsayılan: açık)
}


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    con.commit()


def load_settings(con: sqlite3.Connection) -> Dict[str, Any]:
    """
    DB'den ayarları okur, eksik olanları DEFAULT ile tamamlar.
    """
    con.row_factory = sqlite3.Row
    _ensure_schema(con)

    cur = con.execute(f"SELECT key, value FROM {TABLE_NAME}")
    data = {row["key"]: row["value"] for row in cur.fetchall()}

    # varsayılanlarla birleştir
    merged: Dict[str, Any] = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(con: sqlite3.Connection, settings: Dict[str, Any]) -> None:
    """
    settings dict'ini tabloya yazar. (REPLACE INTO)
    """
    _ensure_schema(con)
    cur = con.cursor()
    for k, v in settings.items():
        cur.execute(
            f"REPLACE INTO {TABLE_NAME}(key, value) VALUES (?, ?)",
            (str(k), "" if v is None else str(v))
        )
    con.commit()


# ----------------- Küçük yardımcılar -----------------

def get_aktarilan_sayilma_sekli(con: sqlite3.Connection) -> str:
    """
    "done" | "not_done" döner.
    """
    return load_settings(con).get(
        "aktarilan_sayilma_sekli",
        DEFAULT_SETTINGS["aktarilan_sayilma_sekli"],
    )


def get_gunluk_son_gun(con: sqlite3.Connection) -> int:
    """
    Son kaç günü analiz edeceğini int olarak döner.
    """
    val = load_settings(con).get(
        "gunluk_son_gun",
        DEFAULT_SETTINGS["gunluk_son_gun"],
    )
    try:
        return int(val)
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS["gunluk_son_gun"])


def is_gecikmis_kume_vurgula(con: sqlite3.Connection) -> bool:
    """
    Gecikmiş kümeler raporda ayrıca vurgulansın mı? True / False.
    """
    val = load_settings(con).get(
        "gecikmis_kume_vurgula",
        DEFAULT_SETTINGS["gecikmis_kume_vurgula"],
    )
    return str(val) == "1"
