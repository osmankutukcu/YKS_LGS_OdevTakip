import db
import sqlite3

def force_init():
    try:
        print("Forcing DB Init...")
        con = db.get_conn()
        cur = con.cursor()
        db._init_deneme_tables(cur)
        con.commit()
        con.close()
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    force_init()
