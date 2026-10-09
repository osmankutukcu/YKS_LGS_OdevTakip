import db
import sqlite3

def force_create():
    try:
        print("Forcing Table Creation: koc_program...")
        con = db.get_conn()
        cur = con.cursor()
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS koc_program (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            gun TEXT,       -- Pazartesi, Salı...
            saat TEXT,      -- 09:00 - 10:00 vb
            icerik TEXT,
            FOREIGN KEY(plan_id) REFERENCES koc_plan(id) ON DELETE CASCADE
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_prog_plan ON koc_program(plan_id)")
        
        con.commit()
        con.close()
        print("Table created successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    force_create()
