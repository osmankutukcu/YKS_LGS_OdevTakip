"""Konu değişikliği etki analizi: yalnızca SELECT ve kapsam kontrolü."""
from __future__ import annotations

import re
from typing import Optional


class CurriculumSafetyError(ValueError):
    """İşlem güvenliği veya kapsam belirsizliği nedeniyle durduruldu."""


_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z_0-9]*$")
_SCOPE_TABLES = {"Grup": "grup_konu_duzen", "Öğrenci": "ogrenci_konu_duzen"}


def _existing_table(con, name: str) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def topic_table(con, scope: str, ders: str) -> str:
    if scope not in ("Genel", "Grup", "Öğrenci"):
        raise CurriculumSafetyError("Geçersiz müfredat kapsamı.")
    if scope == "Genel":
        if not _IDENTIFIER.fullmatch(ders or "") or not _existing_table(con, ders):
            raise CurriculumSafetyError("Geçerli bir ders tablosu seçilmedi.")
        # yalnız ders tanımları veya sistemin ders kataloğunda bulunan gerçek tablolar
        from_catalog = False
        if _existing_table(con, "ders_tanimlari"):
            from_catalog = bool(con.execute("SELECT 1 FROM ders_tanimlari WHERE id=?", (ders,)).fetchone())
        if not from_catalog:
            # Uyumluluk: eski dersler henüz ders_tanimlari tablosuna işlenmemiş olabilir.
            try:
                import db
                from_catalog = ders in getattr(db, "DERS_TABLOLARI", [])
            except ImportError:
                pass
        if not from_catalog:
            raise CurriculumSafetyError("Seçilen tablo tanımlı bir ders değil.")
        return ders
    name = _SCOPE_TABLES[scope]
    if not _existing_table(con, name):
        raise CurriculumSafetyError("Kapsama ait konu tablosu henüz oluşturulmamış.")
    return name


def _cols(con, table):
    if not _IDENTIFIER.fullmatch(table or "") or not _existing_table(con, table):
        return set()
    return {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}


def topic_filter(scope: str, ders: str, *, ana_grup=None, alt_grup=None, ogrenci_id=None):
    if not (ders or "").strip():
        raise CurriculumSafetyError("Ders seçiniz.")
    if scope == "Genel":
        return "", ()
    if scope == "Grup":
        if not ana_grup or not alt_grup:
            raise CurriculumSafetyError("Grup ve alt grup seçiniz.")
        return " AND ders=? AND ana_grup=? AND alt_grup=?", (ders, ana_grup, alt_grup)
    if scope == "Öğrenci":
        if ogrenci_id is None or int(ogrenci_id) <= 0:
            raise CurriculumSafetyError("Öğrenci seçiniz.")
        return " AND ders=? AND ogrenci_id=?", (ders, int(ogrenci_id))
    raise CurriculumSafetyError("Geçersiz kapsam.")


def find_topic(con, *, scope, ders, topic_id, ana_grup=None, alt_grup=None, ogrenci_id=None):
    table = topic_table(con, scope, ders)
    clause, params = topic_filter(scope, ders, ana_grup=ana_grup,
                                   alt_grup=alt_grup, ogrenci_id=ogrenci_id)
    try:
        topic_id = int(topic_id)
    except (TypeError, ValueError):
        raise CurriculumSafetyError("Geçerli konu kimliği gerekli.") from None
    row = con.execute(f'SELECT id, konu FROM "{table}" WHERE id=?{clause}', (topic_id, *params)).fetchone()
    if not row:
        raise CurriculumSafetyError("Konu kaydı değişmiş veya farklı kapsamda; listeyi yenileyiniz.")
    return {"id": row[0], "konu": row[1]}


def topic_impact(con, *, scope: str, ders: str, name: str, topic_id: Optional[int] = None,
                 ana_grup=None, alt_grup=None, ogrenci_id=None) -> dict:
    """Belirli konunun ad/ID bazında geçmiş temaslarını sayar; yazma işlemi yapmaz.

    Sayılar her tabloda ayrı tutulur, toplam öğrenci/ödev sayısı diye toplanamaz.
    Grup/öğrenci etkisinin tarihsel kapsamı eski tablolarda belirsizdir: korumacı sayım.
    """
    topic_table(con, scope, ders)
    name = (name or "").strip()
    if not name:
        raise CurriculumSafetyError("Konu adı boş.")
    if topic_id is not None:
        found = find_topic(con, scope=scope, ders=ders, topic_id=topic_id,
                           ana_grup=ana_grup, alt_grup=alt_grup, ogrenci_id=ogrenci_id)
        if found['konu'] != name:
            raise CurriculumSafetyError("Konu listesi başka bir işlemle değişti; yenileyiniz.")
    counts = {}
    for table, name_cols in (("odev", ("konu_ad",)), ("odev_satir", ("konu", "konu_ad")),
                             ("konu_istatistik", ("konu",)), ("cohort_kitap_kapsam", ("konu",))):
        cols = _cols(con, table)
        present = [c for c in name_cols if c in cols]
        if not present or "ders" not in cols:
            continue
        clauses = [f'"{c}"=?' for c in present]
        wh = f'ders=? AND ({" OR ".join(clauses)})'
        args = [ders] + [name] * len(present)
        if table == "odev" and scope == "Genel" and topic_id is not None and "konu_id" in cols:
            wh = f'ders=? AND (konu_id=? OR ({" OR ".join(clauses)}))'
            args = [ders, int(topic_id)] + [name] * len(present)
        counts[table] = con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {wh}', args).fetchone()[0]
    return {"scope": scope, "ders": ders, "topic_id": topic_id, "name": name,
            "references": counts, "has_history": any(counts.values()),
            "scope_ambiguous": scope != "Genel" and any(counts.values())}
