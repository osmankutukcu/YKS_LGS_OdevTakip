# -*- coding: utf-8 -*-
import os, sqlite3, datetime, sys
from pathlib import Path

DB_PATH = Path.home() / ".yks_lgs_manager" / "veritabani.db"

def ensure_table_and_columns(con):
    cur = con.cursor()
    # Tablo var mı?
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='whatsapp_log'"
    ).fetchone()
    if not row:
        # Eski şema ile oluştur (uyumlu)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS whatsapp_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zaman TEXT,
            ogrenci_id INTEGER,
            numara TEXT,
            mesaj_onizleme TEXT,
            durum TEXT,
            hata TEXT,
            ekran_goruntusu TEXT
        )
        """)
        con.commit()

    # Mevcut kolonları çek
    cols = {r[1] for r in cur.execute("PRAGMA table_info(whatsapp_log)")}
    # Eksik kolonları ekle
    adds = [
        ("zaman", "ALTER TABLE whatsapp_log ADD COLUMN zaman TEXT"),
        ("ogrenci_id", "ALTER TABLE whatsapp_log ADD COLUMN ogrenci_id INTEGER"),
        ("numara", "ALTER TABLE whatsapp_log ADD COLUMN numara TEXT"),
        ("mesaj_onizleme", "ALTER TABLE whatsapp_log ADD COLUMN mesaj_onizleme TEXT"),
        ("durum", "ALTER TABLE whatsapp_log ADD COLUMN durum TEXT"),
        ("hata", "ALTER TABLE whatsapp_log ADD COLUMN hata TEXT"),
        ("ekran_goruntusu", "ALTER TABLE whatsapp_log ADD COLUMN ekran_goruntusu TEXT"),
    ]
    for name, ddl in adds:
        if name not in cols:
            try:
                cur.execute(ddl)
            except sqlite3.OperationalError:
                pass
    con.commit()

def insert_test(con):
    cur = con.cursor()
    cur.execute("""
        INSERT INTO whatsapp_log(zaman, ogrenci_id, numara, mesaj_onizleme, durum, hata, ekran_goruntusu)
        VALUES(datetime('now'), ?, ?, ?, ?, ?, ?)
    """, (None, "+900000000000", "FIX TEST KAYDI", "OK", None, None))
    con.commit()

def print_summary(con):
    cur = con.cursor()
    cnt = cur.execute("SELECT COUNT(*) FROM whatsapp_log").fetchone()[0]
    last = cur.execute("""
        SELECT id, COALESCE(zaman,''), COALESCE(numara,''), COALESCE(durum,'')
        FROM whatsapp_log ORDER BY id DESC LIMIT 1
    """).fetchone()
    print(f"DB: {DB_PATH}")
    print("Toplam whatsapp_log kaydı:", cnt)
    print("Son kayıt:", last)

def main():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    try:
        ensure_table_and_columns(con)
        insert_test(con)
        print_summary(con)
    finally:
        con.close()

if __name__ == "__main__":
    main()
