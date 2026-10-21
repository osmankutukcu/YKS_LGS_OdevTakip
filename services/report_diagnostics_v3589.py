# -*- coding: utf-8 -*-
"""Salt-okunur rapor kaynağı tanılayıcısı. Öğrenci adını/ID'sini iletmez.

Aynı öğrenci-küme-ders anahtarının iki tabloda bulunması olası örtüşmedir;
tekrarlı ödev olduğu anlamına gelmez ve otomatik silme/birleştirme yapılmaz.
"""
from __future__ import annotations


def inspect_report_sources(conn):
    """Açık bağlantıda yalnızca SELECT uygular ve anonim toplu sayaç döndürür."""
    schema = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    result = {"main": 0, "rows": 0, "candidate_keys": 0,
              "monthly": "ogrenci_perf_gunluk" in schema,
              "weekly": "ogrenci_perf_hafta_ders" in schema,
              "missing": []}
    for table, key in (("odev", "main"), ("odev_satir", "rows")):
        if table not in schema:
            result["missing"].append(table)
            continue
        result[key] = int(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0])
    if not result["missing"]:
        a = {str(r[1]) for r in conn.execute("PRAGMA table_info(odev)")}
        b = {str(r[1]) for r in conn.execute("PRAGMA table_info(odev_satir)")}
        required = {"ogrenci_id", "kume_id", "ders"}
        if required <= a and required <= b:
            # Only candidate keys; duplicates must be reviewed by a person.
            sql = """SELECT COUNT(*) FROM (
              SELECT ogrenci_id, kume_id, ders FROM odev
              WHERE ogrenci_id IS NOT NULL AND kume_id IS NOT NULL
                AND ders IS NOT NULL
              GROUP BY ogrenci_id,kume_id,ders
              INTERSECT
              SELECT ogrenci_id,kume_id,ders FROM odev_satir
              WHERE ogrenci_id IS NOT NULL AND kume_id IS NOT NULL
                AND ders IS NOT NULL
              GROUP BY ogrenci_id,kume_id,ders
            )"""
            result["candidate_keys"] = int(conn.execute(sql).fetchone()[0])
    return result
