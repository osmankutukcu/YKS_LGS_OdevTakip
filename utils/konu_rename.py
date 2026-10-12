# -*- coding: utf-8 -*-
"""Eski yeniden adlandırma API'sı için V23 güvenlik uyumluluk katmanı.

Kapsam dışında toplu tarihçe yazma ve istatistik kaybı riskini önler.
"""
from typing import Optional
import sqlite3
from services.curriculum_v23.changes import rename_topic_safe


def rename_topic(con: sqlite3.Connection, *, ders: str, old_name: str, new_name: str,
                 scope: str = "Genel", ana_grup: Optional[str] = None,
                 alt_grup: Optional[str] = None, ogrenci_id: Optional[int] = None,
                 merge_if_exists: bool = True, update_history: bool = False,
                 topic_id: Optional[int] = None):
    """ID sabit kalır; mevcut ders/ödev geçmişi değiştirilmez.

    Önceki `update_history=True` çağrıları güvenli olmadığı için açık hata verir.
    `merge_if_exists` geriye uyumlu imzada tutulur; kayıtlar otomatik birleşmez.
    """
    return rename_topic_safe(con, ders=ders, old_name=old_name, new_name=new_name,
                             scope=scope, ana_grup=ana_grup, alt_grup=alt_grup,
                             ogrenci_id=ogrenci_id, topic_id=topic_id,
                             update_history=update_history)
