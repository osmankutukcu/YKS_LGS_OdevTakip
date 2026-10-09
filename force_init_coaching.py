import db
import sqlite3

def force_init():
    try:
        print("Forcing Coaching DB Init...")
        con = db.get_conn()
        cur = con.cursor()
        # db.py içinde tanımladığımız fonksiyonu çağırıyoruz
        # Eğer db.py import edilebiliyorsa bu çalışmalı
        if hasattr(db, '_init_coaching_tables'):
            db._init_coaching_tables(cur)
            con.commit()
            print("Coaching tables created successfully.")
        else:
            print("Error: _init_coaching_tables function not found in db module.")
            # Fallback: Manuel oluştur
            print("Running fallback creation...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS koc_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ogrenci_id INTEGER,
                baslangic_tarihi TEXT,
                bitis_tarihi TEXT,
                notlar TEXT,
                aktif INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
            )""")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS koc_hedef (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER,
                ders_adi TEXT,
                hedef_soru INTEGER DEFAULT 0,
                cozulen_soru INTEGER DEFAULT 0,
                durum TEXT DEFAULT 'devam',
                FOREIGN KEY(plan_id) REFERENCES koc_plan(id) ON DELETE CASCADE
            )""")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_plan_ogr ON koc_plan(ogrenci_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_hedef_plan ON koc_hedef(plan_id)")
            con.commit()
            print("Fallback tables created.")
            
        con.close()
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    force_init()
