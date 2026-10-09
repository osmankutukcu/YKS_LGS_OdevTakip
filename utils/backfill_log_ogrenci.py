# -*- coding: utf-8 -*-
import os, sqlite3, re
from pathlib import Path

DB = Path.home() / ".yks_lgs_manager" / "veritabani.db"

def norm(s):
    if not s: return ""
    t = re.sub(r"[^\d+]", "", str(s))
    if t.startswith("+"): return t
    if t.startswith("0"): t = t[1:]
    return "+90" + t if len(t) == 10 else t  # TR varsayılanı

def main():
    if not DB.exists():
        print(f"Veritabanı bulunamadı: {DB}")
        return

    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ogrenci -> temizlenmiş numara seti
    ogr_map = {}   # numara -> ogrenci_id
    for r in cur.execute("SELECT id, veli_tel1, veli_tel2, ogr_tel FROM ogrenci"):
        for k in ("veli_tel1","veli_tel2","ogr_tel"):
            n = norm(r[k])
            if n:
                ogr_map[n] = int(r["id"])

    # NULL ogrenci_id olan logları çek
    rows = cur.execute("SELECT id, COALESCE(numara, numaralar) AS nums FROM whatsapp_log WHERE ogrenci_id IS NULL").fetchall()
    upd = 0
    for r in rows:
        nums = (r["nums"] or "").split(",")
        oid = None
        for raw in nums:
            n = norm(raw)
            if n in ogr_map:
                oid = ogr_map[n]
                break
        if oid:
            cur.execute("UPDATE whatsapp_log SET ogrenci_id=? WHERE id=?", (oid, int(r["id"])))
            upd += 1

    con.commit(); con.close()
    print(f"Tamamlandı. Güncellenen satır: {upd}")

if __name__ == '__main__':
    main()
