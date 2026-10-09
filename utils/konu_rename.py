# utils/konu_rename.py
# -*- coding: utf-8 -*-
from typing import Optional
import sqlite3

AFFECTED_HISTORY_TABLES = [
    # tablo, alan_adı listesi (ders filtresi de var)
    ("odev", ["konu_ad"]),
    ("odev_satir", ["konu", "konu_ad"]),
    ("cohort_kitap_kapsam", ["konu"]),
    ("konu_istatistik", ["konu"]),
]

def rename_topic(
    con: sqlite3.Connection,
    *,
    ders: str,
    old_name: str,
    new_name: str,
    scope: str = "Genel",        # "Genel" | "Grup" | "Öğrenci"
    ana_grup: Optional[str] = None,
    alt_grup: Optional[str] = None,
    ogrenci_id: Optional[int] = None,
    merge_if_exists: bool = True,
    update_history: bool = True,
) -> None:
    """
    Belirli kapsamda konu adını değiştirir. İstenirse geçmiş tabloları da günceller.
    merge_if_exists=True: hedef ad zaten varsa ilgili istatistik satırlarını birleştirir.
    """
    cur = con.cursor()
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name or old_name == new_name:
        return

    # 1) Kapsam tablosunda değiştir
    if scope == "Genel":
        # hedef konu varsa ve merge istiyorsak ort_soru/süre birleştirme gibi ilerletilebilir;
        # şimdilik sadece ad değiştir:
        cur.execute(f"UPDATE {ders} SET konu=? WHERE konu=?", (new_name, old_name))
    elif scope == "Grup":
        cur.execute("""
            UPDATE grup_konu_duzen
               SET konu=?
             WHERE ders=? AND ana_grup=? AND alt_grup=? AND konu=?
        """, (new_name, ders, ana_grup, alt_grup, old_name))
    else:
        cur.execute("""
            UPDATE ogrenci_konu_duzen
               SET konu=?
             WHERE ders=? AND ogrenci_id=? AND konu=?
        """, (new_name, ders, ogrenci_id, old_name))

    # 2) İstatistik tablolarında birleştirme (hedef varsa)
    if merge_if_exists:
        # konu_istatistik birleştir
        cur.execute("""
            UPDATE konu_istatistik
               SET tamam = tamam + COALESCE((SELECT tamam FROM konu_istatistik k2
                                              WHERE k2.ders=? AND k2.konu=?), 0),
                   yapilmadi = yapilmadi + COALESCE((SELECT yapilmadi FROM konu_istatistik k2
                                              WHERE k2.ders=? AND k2.konu=?), 0)
             WHERE ders=? AND konu=?
        """, (ders, old_name, ders, old_name, ders, new_name))
        cur.execute("DELETE FROM konu_istatistik WHERE ders=? AND konu=?", (ders, old_name))

        # cohort_kitap_kapsam yüzdeleri: eski kayıtları yeni ada aktar (varsa ekle)
        cur.execute("""
            INSERT INTO cohort_kitap_kapsam(ders, kitap, konu, done_count, student_count, pct)
            SELECT ders, kitap, ?, done_count, student_count, pct
              FROM cohort_kitap_kapsam
             WHERE ders=? AND konu=?
             ON CONFLICT(ders, kitap, konu) DO UPDATE SET
                 done_count = cohort_kitap_kapsam.done_count + excluded.done_count,
                 student_count = cohort_kitap_kapsam.student_count + excluded.student_count
        """, (new_name, ders, old_name))
        cur.execute("DELETE FROM cohort_kitap_kapsam WHERE ders=? AND konu=?", (ders, old_name))

    # 3) Geçmiş ödev kayıtlarını güncelle
    if update_history:
        for tbl, cols in AFFECTED_HISTORY_TABLES:
            sets = ", ".join([f"{col}=?" for col in cols])
            cur.execute(f"""
                UPDATE {tbl}
                   SET {sets}
                 WHERE ders=? AND ({' OR '.join([f'{c}=?' for c in cols])})
            """, (*([new_name]*len(cols)), ders, *([old_name]*len(cols))))
    con.commit()