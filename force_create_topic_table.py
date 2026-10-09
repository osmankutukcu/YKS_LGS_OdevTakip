import db
import sqlite3

def force_create():
    try:
        print("Forcing Table Creation: koc_konu_takip...")
        con = db.get_conn()
        cur = con.cursor()
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS koc_konu_takip (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER,
            ders_adi TEXT,
            konu_adi TEXT,
            durum INTEGER DEFAULT 0, -- 0:Başlanmadı, 1:Çalışılıyor, 2:Bitti
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_konu_ogr ON koc_konu_takip(ogrenci_id)")
        
        con.commit()
        con.close()
        print("Table 'koc_konu_takip' created successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    force_create()
