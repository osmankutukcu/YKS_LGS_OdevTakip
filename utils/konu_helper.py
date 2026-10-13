# utils/konu_helper.py
# -*- coding: utf-8 -*-
from typing import Dict, List, Optional
import db

# utils/konu_helper.py

def _rows_to_map(rows):
    """
    DB'den gelen satırları
    { normalized_konu: {"konu": ..., "ort_soru": ..., "ort_sure": ...} }
    formuna çevirir.
    """
    m = {}
    for r in rows:
        d = dict(r)  # <-- Row -> dict, böylece .get kullanabiliriz
        key = (d.get("konu") or "").strip().lower()
        if not key:
            continue

        m[key] = {
            "konu": d.get("konu"),
            "ort_soru": d.get("ort_soru"),
            "ort_sure": d.get("ort_sure"),
        }
    return m

def get_active_list(
    con,
    ders: str,
    *,
    ogrenci_id: Optional[int] = None,
    ana_grup: Optional[str] = None,
    alt_grup: Optional[str] = None,
) -> List[dict]:
    """
    ÖNCELİK: Öğrenci > Grup > Genel
    Dönüş: [{konu, ort_soru, ort_sure}, ...] (konu adına göre tekil)
    """
    cur = con.cursor()

    # 1) GENEL
    genel = db.ders_konularini_cek(con, ders)  # [{id, konu, ort_soru, ort_sure}, ...]
    result = _rows_to_map(genel)

    # 2) GRUP (varsa) -> ekle/override
    if ana_grup or alt_grup:
        g_rows = cur.execute("""
            SELECT konu, ort_soru, ort_sure
            FROM grup_konu_duzen
            WHERE ders=? AND (? IS NULL OR ana_grup=?) AND (? IS NULL OR alt_grup=?)
        """, (ders, ana_grup, ana_grup, alt_grup, alt_grup)).fetchall()
        gmap = _rows_to_map(g_rows)
        result.update(gmap)  # aynı konu varsa grup verisi baskın

    # 3) ÖĞRENCİ (varsa) -> ekle/override
    if ogrenci_id:
        o_rows = cur.execute("""
            SELECT konu, ort_soru, ort_sure
            FROM ogrenci_konu_duzen
            WHERE ders=? AND ogrenci_id=?
        """, (ders, ogrenci_id)).fetchall()
        omap = _rows_to_map(o_rows)
        result.update(omap)  # öğrenci baskın

    # V31/Windows: preserve EXACTLY the old sort policy, but avoid a repeated
    # linear list.index() for every topic. With many curriculum topics that
    # was quadratic on each duration lookup triggered by a checkbox tick.
    # setdefault() preserves the first occurrence for duplicate topic names.
    genel_position = {}
    for position, row in enumerate(genel):
        key = (row["konu"] or "").strip().lower()
        genel_position.setdefault(key, position)

    def order_key(k):
        folded = k.lower()
        position = genel_position.get(folded)
        if position is not None:
            return (0, position)
        return (1, folded)
    items = sorted(result.values(), key=lambda x: order_key(x["konu"]))
    return items