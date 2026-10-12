"""Kaydet, yeniden adlandır ve sil işlemleri için dar yetkili, atomik servis."""
from __future__ import annotations

from .impact import CurriculumSafetyError, topic_filter, topic_table, find_topic, topic_impact
import unicodedata


def _topic_key(name):
    # Türkçe büyük İ/i ile I/ı eşleştirmesi; aksanları veya farklı kavramları birleştirmez.
    return unicodedata.normalize("NFC", str(name).strip()).replace("İ", "i").replace("I", "ı").casefold()


def _canonical(value):
    value = (value or "").strip()
    if not value or "\x00" in value or "\r" in value or "\n" in value:
        raise CurriculumSafetyError("Boş veya satır sonu içeren konu adı kullanılamaz.")
    return value


def _optional_number(value, label):
    if value is None or str(value).strip() == "":
        return None
    try:
        number = int(str(value).strip())
    except ValueError:
        raise CurriculumSafetyError(f"{label} için sayı giriniz.") from None
    if not 0 <= number <= 1000000:
        raise CurriculumSafetyError(f"{label} 0–1000000 arasında olmalı.")
    return number


def _begin(con):
    # SAVEPOINT içinde rollback: çağıranın açık transaction'ı varsa onu bozmadan geri al.
    con.execute("SAVEPOINT v23_curriculum")


def _finish(con, ok):
    if not ok:
        con.execute("ROLLBACK TO SAVEPOINT v23_curriculum")
    con.execute("RELEASE SAVEPOINT v23_curriculum")


def save_topics(con, *, scope, ders, rows, ana_grup=None, alt_grup=None, ogrenci_id=None,
                expected_names=None):
    """Mevcut adlar sadece yeniden-adlandırma sihirbazından değişebilir.

    Boş/çift kayıt, başka kapsama ait ID veya yarış durumu varsa bütün paket geri alınır.
    Verilmeyen eski satırları asla silmez.
    """
    table = topic_table(con, scope, ders)
    clause, params = topic_filter(scope, ders, ana_grup=ana_grup,
                                   alt_grup=alt_grup, ogrenci_id=ogrenci_id)
    prepared, seen = [], set()
    for raw in rows:
        name = _canonical(raw.get("konu"))
        key = _topic_key(name)
        if key in seen:
            raise CurriculumSafetyError(f"Aynı kapsamda tekrar eden konu: {name}")
        seen.add(key)
        rid = raw.get("id")
        rid = int(rid) if str(rid or "").strip() else None
        prepared.append((rid, name, _optional_number(raw.get("ort_soru"), "Soru hedefi"),
                         _optional_number(raw.get("ort_sure"), "Süre hedefi")))
    _begin(con)
    try:
        for rid, name, soru, sure in prepared:
            if rid is not None:
                found = find_topic(con, scope=scope, ders=ders, topic_id=rid,
                                   ana_grup=ana_grup, alt_grup=alt_grup, ogrenci_id=ogrenci_id)
                old_name = found['konu']
                if old_name != name:
                    raise CurriculumSafetyError("Kayıtlı konunun adı doğrudan hücrede değiştirilemez. "
                                                "'Konu Adını Değiştir' sihirbazını kullanınız.")
                if expected_names is not None and expected_names.get(rid) != old_name:
                    raise CurriculumSafetyError("Konu başka bir pencerede değişmiş. Önce listeyi yenileyiniz.")
                con.execute(f'UPDATE "{table}" SET ort_soru=?, ort_sure=? WHERE id=?{clause}',
                            (soru, sure, rid, *params))
            else:
                existing = con.execute(f'SELECT konu FROM "{table}" WHERE 1=1{clause}',
                                       params).fetchall()
                if any(_topic_key(record[0]) == _topic_key(name) for record in existing):
                    raise CurriculumSafetyError(f"'{name}' zaten kayıtlı; iki kez eklenmedi.")
                if scope == "Genel":
                    con.execute(f'INSERT INTO "{table}"(konu, ort_soru, ort_sure) VALUES(?,?,?)',
                                (name, soru, sure))
                elif scope == "Grup":
                    con.execute('INSERT INTO grup_konu_duzen(ana_grup,alt_grup,ders,konu,ort_soru,ort_sure) VALUES(?,?,?,?,?,?)',
                                (ana_grup, alt_grup, ders, name, soru, sure))
                else:
                    con.execute('INSERT INTO ogrenci_konu_duzen(ogrenci_id,ders,konu,ort_soru,ort_sure) VALUES(?,?,?,?,?)',
                                (int(ogrenci_id), ders, name, soru, sure))
    except Exception:
        _finish(con, False)
        raise
    _finish(con, True)
    con.commit()
    return len(prepared)


def rename_topic_safe(con, *, scope, ders, old_name, new_name, topic_id=None,
                      ana_grup=None, alt_grup=None, ogrenci_id=None, update_history=False):
    """ID korunarak sadece katalog adını değiştirir. Tarihsel ödevler değişmez.

    Tarihçe güncellemesi eski veri şemasında kapsamdan bağımsız olduğundan kapalıdır.
    """
    old_name, new_name = _canonical(old_name), _canonical(new_name)
    if update_history:
        raise CurriculumSafetyError("Geçmiş kayıtları otomatik yeniden adlandırma güvenli değil. "
                                    "Ödev geçmişi korunuyor; sadece katalog adı değiştirilebilir.")
    table = topic_table(con, scope, ders)
    clause, params = topic_filter(scope, ders, ana_grup=ana_grup,
                                   alt_grup=alt_grup, ogrenci_id=ogrenci_id)
    if old_name == new_name:
        return {"changed": False}
    _begin(con)
    try:
        if topic_id is None:
            found = con.execute(f'SELECT id FROM "{table}" WHERE konu=?{clause}', (old_name, *params)).fetchall()
            if len(found) != 1:
                raise CurriculumSafetyError("Aynı adlı konu belirsiz ya da bulunamadı; ID ile yeniden deneyiniz.")
            topic_id = found[0][0]
        row = find_topic(con, scope=scope, ders=ders, topic_id=topic_id,
                         ana_grup=ana_grup, alt_grup=alt_grup, ogrenci_id=ogrenci_id)
        if row["konu"] != old_name:
            raise CurriculumSafetyError("Eski konu adı değişmiş; listeyi yenileyiniz.")
        existing = con.execute(f'SELECT id, konu FROM "{table}" WHERE 1=1{clause}',
                               params).fetchall()
        if any(row[0] != int(topic_id) and _topic_key(row[1]) == _topic_key(new_name)
               for row in existing):
            raise CurriculumSafetyError("Hedef konu adı bu kapsamda zaten var. Otomatik birleştirme yapılmaz.")
        impact = topic_impact(con, scope=scope, ders=ders, name=old_name, topic_id=int(topic_id),
                              ana_grup=ana_grup, alt_grup=alt_grup, ogrenci_id=ogrenci_id)
        cur = con.execute(f'UPDATE "{table}" SET konu=? WHERE id=?{clause}',
                          (new_name, int(topic_id), *params))
        if cur.rowcount != 1:
            raise CurriculumSafetyError("Beklenmeyen değişiklik sayısı; işlem iptal edildi.")
    except Exception:
        _finish(con, False)
        raise
    _finish(con, True)
    con.commit()
    return {"changed": True, "impact": impact, "history_preserved": True}


def delete_unused_topics(con, *, scope, ders, ids, ana_grup=None, alt_grup=None, ogrenci_id=None):
    """Sadece kullanılmayan katalog satırlarını siler; kullanılmış kayıtlar korunur."""
    table = topic_table(con, scope, ders)
    clause, params = topic_filter(scope, ders, ana_grup=ana_grup,
                                   alt_grup=alt_grup, ogrenci_id=ogrenci_id)
    ids = tuple(sorted(set(int(i) for i in ids)))
    _begin(con)
    try:
        for rid in ids:
            row = find_topic(con, scope=scope, ders=ders, topic_id=rid,
                             ana_grup=ana_grup, alt_grup=alt_grup, ogrenci_id=ogrenci_id)
            impact = topic_impact(con, scope=scope, ders=ders, name=row['konu'], topic_id=rid,
                                  ana_grup=ana_grup, alt_grup=alt_grup, ogrenci_id=ogrenci_id)
            if impact['has_history']:
                raise CurriculumSafetyError(f"'{row['konu']}' geçmiş ödev/istatistik kayıtlarında kullanılmış. "
                                            "Kayıt korunuyor; silinemez.")
        for rid in ids:
            con.execute(f'DELETE FROM "{table}" WHERE id=?{clause}', (rid, *params))
    except Exception:
        _finish(con, False)
        raise
    _finish(con, True)
    con.commit()
    return len(ids)
