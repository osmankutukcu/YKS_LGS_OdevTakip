import db
import sqlite3

def force_alter():
    try:
        print("Forcing Column Addition...")
        con = db.get_conn()
        cur = con.cursor()
        
        # 1. hedef_saat
        try:
            print("Adding hedef_saat...")
            cur.execute("ALTER TABLE koc_hedef ADD COLUMN hedef_saat REAL DEFAULT 0")
            print("hedef_saat added.")
        except Exception as e:
            print(f"hedef_saat skip/error: {e}")

        # 2. calisilan_saat
        try:
            print("Adding calisilan_saat...")
            cur.execute("ALTER TABLE koc_hedef ADD COLUMN calisilan_saat REAL DEFAULT 0")
            print("calisilan_saat added.")
        except Exception as e:
            print(f"calisilan_saat skip/error: {e}")

        con.commit()
        con.close()
        print("Done.")
    except Exception as e:
        print(f"Fatal Error: {e}")

if __name__ == "__main__":
    force_alter()
