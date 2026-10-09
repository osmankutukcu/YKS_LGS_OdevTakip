import sqlite3
import db

def add_schedule_columns():
    con = db.get_conn()
    cur = con.cursor()
    
    # Tablo bilgisini al
    cur.execute("PRAGMA table_info(ogrenci)")
    cols = [info[1] for info in cur.fetchall()]
    
    added = False
    
    if "kocluk_gunu" not in cols:
        print("Adding kocluk_gunu column...")
        cur.execute("ALTER TABLE ogrenci ADD COLUMN kocluk_gunu TEXT")
        added = True
        
    if "kocluk_saati" not in cols:
        print("Adding kocluk_saati column...")
        cur.execute("ALTER TABLE ogrenci ADD COLUMN kocluk_saati TEXT")
        added = True
        
    if added:
        con.commit()
        print("Student schema updated successfully.")
    else:
        print("Columns already exist.")

if __name__ == "__main__":
    add_schedule_columns()
