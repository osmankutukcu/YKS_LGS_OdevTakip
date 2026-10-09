import sys
import os
import sqlite3
import db

def fix_database():
    print(f"Fixing database at: {db.DB_PATH}")
    con = db.get_conn()
    try:
        # 1. Create koc_kitaplar table
        print("Creating table koc_kitaplar...")
        con.execute("""
        CREATE TABLE IF NOT EXISTS koc_kitaplar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER,
            ders_adi TEXT,
            kitap_adi TEXT
        )""")
        
        # 2. Add kitap_id column to koc_konu_takip if missing
        print("Checking koc_konu_takip schema...")
        res = con.execute("PRAGMA table_info(koc_konu_takip)").fetchall()
        columns = [r[1] for r in res]
        
        if "kitap_id" not in columns:
            print("Adding kitap_id column to koc_konu_takip...")
            con.execute("ALTER TABLE koc_konu_takip ADD COLUMN kitap_id INTEGER DEFAULT 0")
        else:
            print("kitap_id column already exists.")
            
        con.commit()
        print("Database fix completed successfully.")
        
    except Exception as e:
        print(f"Error fixing database: {e}")
    finally:
        con.close()

if __name__ == "__main__":
    fix_database()
