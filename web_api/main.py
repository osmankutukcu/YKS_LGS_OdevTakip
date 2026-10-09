from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add parent directory to path to import existing modules like db.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# FORCE SYNC: Use the DB in the root directory if environment var is missing
import os
from pathlib import Path
_root_dir = Path(__file__).resolve().parent.parent
_candidate_db = _root_dir / "YKS_LGS_HomeworkManager.db"
if "YKS_DB_PATH" not in os.environ and _candidate_db.exists():
    print(f"[*] Web API forcing DB path to: {_candidate_db}")
    os.environ["YKS_DB_PATH"] = str(_candidate_db)

# Import existing DB module (will need to ensure dependencies are met)
try:
    import db
    # MÜFREDAT YÖNETİMİ: Web Sunucusu için özel dersleri yükle
    if hasattr(db, 'load_custom_lessons'):
        try: db.load_custom_lessons()
        except: pass
except ImportError as e:
    print(f"Warning: Could not import db module. Details: {e}")

app = FastAPI(title="YKS/LGS Manager API", version="1.0.0")

# CORS (Cross-Origin Resource Sharing) - Allow Frontend to access this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import random
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

# --- Pydantic Models ---
class DashboardStats(BaseModel):
    student_count: int
    pending_tasks: int
    success_rate: int
    quote: str

class Student(BaseModel):
    id: int
    ad_soyad: str
    sinif: Optional[str] = None
    okul: Optional[str] = None
    telefon: Optional[str] = None

# --- Helpers ---
def get_random_quote():
    quotes = [
        "Başarı, her gün tekrarlanan küçük çabaların toplamıdır.",
        "Gelecek, onu bugün hazırlayanlara aittir.",
        "Yarınlar yorgun olanların değil, rahatından vazgeçenlerindir.",
        "Hiçbir zafere çiçekli yollardan gidilmez.",
        "Vazgeçmediğin sürece, başarısız olmuş sayılmazsın.",
        "Zafer, 'Zafer benimdir' diyebilenindir.",
        "Başarı, sabırla yürüyenlerin yol arkadaşıdır.",
        "Bugün çekilen zahmet, yarının mutluluğudur.",
        "Disiplin, hayallerin gerçeğe dönüşme sürecidir.",
        "Zor zamanlar, güçlü insanları yetiştirir.",
        "Emek verilen hiçbir hedef karşılıksız kalmaz.",
        "Başlamak cesaret, devam etmek kararlılık ister.",
        "Yorulabilirsin ama vazgeçmemelisin.",
        "Küçük adımlar, büyük değişimler yaratır.",
        "Konfor alanından çıkmadan başarıya ulaşılamaz.",
        "Çalışan kazanır, sabreden başarır.",
        "Bugünün emeği, yarının gururudur.",
        "İnanan insan için imkânsız yoktur.",
        "Başarı, bahaneleri değil çözümleri seçenlerindir.",
        "Her gün biraz daha ilerlemek yeterlidir."
    ]
    return random.choice(quotes)

# --- Endpoints ---

@app.get("/api/dashboard", response_model=DashboardStats)
def get_dashboard_stats():
    """
    Returns statistics for the dashboard cards.
    """
    con = db.get_conn()
    cur = con.cursor()
    
    # 1. Student Count
    cur.execute("SELECT COUNT(*) FROM ogrenci")
    std_count = cur.fetchone()[0]
    
    # 2. Pending Tasks
    try:
        cur.execute("SELECT COUNT(*) FROM odev_satir WHERE tamamlandi=0")
        pending = cur.fetchone()[0]
    except:
        pending = 0
        
    # 3. Success Rate (General)
    ratio = 0
    try:
        cur.execute("SELECT COUNT(*), SUM(CASE WHEN tamamlandi=1 THEN 1 ELSE 0 END) FROM odev_satir")
        row = cur.fetchone()
        if row and row[0] > 0:
            ratio = int((row[1] / row[0]) * 100)
    except:
        pass
        
    return DashboardStats(
        student_count=std_count,
        pending_tasks=pending,
        success_rate=ratio,
        quote=get_random_quote()
    )

@app.get("/api/students", response_model=List[Student])
def get_students():
    """
    Returns a list of all active students.
    """
    con = db.get_conn()
    cur = con.cursor()
    # Assuming 'aktif' column exists or just grabbing all
    # Checking db schema effectively allows us to be more precise soon.
    # For now, select basic columns.
    # Valid columns: id, ad, soyad, ogr_no, ana_grup, alt_grup, veli_tel1
    cur.execute("SELECT id, ad, soyad, alt_grup, ana_grup, veli_tel1 FROM ogrenci WHERE aktif=1 ORDER BY ad, soyad")
    rows = cur.fetchall()
    
    students = []
    for r in rows:
        students.append(Student(
            id=r[0],
            ad_soyad=f"{r[1]} {r[2]}", # Combine ad + soyad
            sinif=r[3], # alt_grup -> sinif
            okul=r[4],  # ana_grup -> okul
            telefon=r[5] # veli_tel1
        ))
    return students

class Homework(BaseModel):
    id: int
    student_name: str
    lesson: str
    book: Optional[str] = None
    subject: Optional[str] = None
    due_date: Optional[str] = None
    is_completed: bool

@app.get("/api/homework", response_model=List[Homework])
def get_homework_list(limit: int = 50):
    """
    Returns latest homework tasks.
    """
    con = db.get_conn()
    cur = con.cursor()
    
    # query fields: s.id, o.ad, o.soyad, s.ders, s.kitap, s.konu, s.tamamlanma_tarihi, s.durum
    # Note: s.durum is 'devam' or 'tamam'. 'tamamlandi' column does not exist.
    query = """
        SELECT s.id, o.ad, o.soyad, s.ders, s.kitap, s.konu, s.tamamlanma_tarihi, s.durum
        FROM odev_satir s
        JOIN ogrenci o ON s.ogrenci_id = o.id
        WHERE s.durum != 'tamam'
        ORDER BY s.id DESC
        LIMIT ?
    """
    cur.execute(query, (limit,))
    rows = cur.fetchall()
    
    homeworks = []
    for r in rows:
        homeworks.append(Homework(
            id=r[0],
            student_name=f"{r[1]} {r[2]}",
            lesson=r[3],
            book=r[4],
            subject=r[5],
            due_date=r[6], # tamamlanma_tarihi (or tarih?) - let's use what we have. Actually due_date is usually future. s.tarih is creation.
            is_completed=(r[7] == 'tamam')
        ))
    return homeworks

class HomeworkUpdate(BaseModel):
    is_completed: bool

@app.post("/api/homework/{homework_id}/complete")
def complete_homework(homework_id: int):
    """
    Marks a specific homework as completed.
    """
    con = db.get_conn()
    cur = con.cursor()
    
    # Update durum='tamam' and set tamamlanma_tarihi
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("UPDATE odev_satir SET durum='tamam', tamamlanma_tarihi=? WHERE id=?", (now_str, homework_id))
        con.commit()
        return {"status": "success", "message": "Homework marked as completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class HomeworkCreate(BaseModel):
    student_id: int
    lesson: str
    book: str
    topic: Optional[str] = None
    topics: Optional[List[str]] = None # New field for multiple selection
    due_date: Optional[str] = None # YYYY-MM-DD

@app.post("/api/homework")
def create_homework(hw: HomeworkCreate):
    """
    Creates a new homework assignment.
    Inserts into odev_kume, odev, and odev_satir.
    """
    con = db.get_conn()
    cur = con.cursor()
    try:
        # 1. Create odev_kume (Homework Set)
        verilis = datetime.now().strftime("%Y-%m-%d")
        # Default due date 7 days if not provided
        if hw.due_date:
            bitis = hw.due_date
        else:
            # Simple 7 days add
            from datetime import timedelta
            bitis = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            
        cur.execute(
            "INSERT INTO odev_kume(ogrenci_id, verilis_tarihi, bitis_tarihi) VALUES(?,?,?)",
            (hw.student_id, verilis, bitis)
        )
        kume_id = cur.lastrowid
        
        # 2. Resolve konu_id (try to find if table exists, otherwise 0)
        konu_id = 0
        try:
            # Check if lesson table exists (Sanitized/Safe way? Lesson comes from user input...)
            # We will just skip this for now and use 0 to avoid SQL injection risks with dynamic table names
            # or complex logic. The desktop app does it, but we can survive with 0.
            pass
        except:
            pass
            
        # Prepare list of topics
        topic_list = []
        if hw.topics:
            topic_list = hw.topics
        elif hw.topic:
            topic_list = [hw.topic]
            
        if not topic_list:
             return {"status": "error", "message": "No topics selected"}

        # Auto-add book to global pool if provided
        if hw.book and hw.book.strip():
             try:
                 cur.execute("INSERT OR IGNORE INTO kitap(ders, ad) VALUES(?,?)", (hw.lesson, hw.book.strip()))
             except:
                 pass

        # Loop through each topic and create an assignment entry
        # Note: We create ONE homework set (odev_kume), but multiple odev/odev_satir entries?
        # Or one odev per topic? The schema allows multiple 'odev' rows for one 'kume_id'.
        # Let's create one 'odev' entry per topic to be safe and consistent with desktop app likely structure.
        
        for t_name in topic_list:
            # Try to resolve real Topic ID to avoid UNIQUE constraint violation on (kume_id, ders, konu_id, kitap_ad)
            # if we use 0 for all topics, only the first one succeeds!
            real_topic_id = 0
            try:
                # Sanitize table name
                import re
                table_cand = re.sub(r'[^a-zA-Z0-9_ğüşıöçĞÜŞİÖÇ]', '', hw.lesson)
                # Check if it is a valid lesson table (simple heuristic: exists in db)
                cur.execute(f"SELECT id FROM {table_cand} WHERE konu=?", (t_name,))
                row = cur.fetchone()
                if row: 
                    real_topic_id = row[0]
                else:
                    # Fallback: Generate a pseudo-unique ID from string hash to avoid collision
                    # Ensure it fits in integer
                    real_topic_id = abs(hash(t_name)) % 1000000
            except:
                real_topic_id = abs(hash(t_name)) % 1000000

            # 3. Insert into odev (Header)
            cur.execute(
                """INSERT INTO odev
                   (kume_id, ogrenci_id, ders, konu_id, konu_ad, kitap_ad, saat_dk, aciklama, durum, verilis_tarihi)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (kume_id, hw.student_id, hw.lesson, real_topic_id, t_name, hw.book, 0, "", "devam", verilis)
            )
            odev_id = cur.lastrowid
            
            # 4. Insert into odev_satir (Line Item - The one we list)
            # Schema uses 'kitap' not 'kitap_ad', and 'konu' not 'konu_ad' (based on db.py inspection)
            # Correction: db.py says: ders TEXT, kitap TEXT, konu TEXT
            cur.execute(
                """INSERT INTO odev_satir
                   (odev_id, kume_id, ogrenci_id, ders, konu, kitap, durum, tarih)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (odev_id, kume_id, hw.student_id, hw.lesson, t_name, hw.book, "devam", verilis)
            )
            
        con.commit()
        return {"status": "success", "message": f"Homework created for {len(topic_list)} topics", "kume_id": kume_id}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        if con: con.close()

# --- Matrix UI Helpers ---

GRUP_DERSLER = {
    "YKS": ["tyt_matematik", "problemler", "ayt_matematik", "geometri", "fizik", "kimya",
            "biyoloji", "turkce", "paragraf", "tarih", "cografya", "felsefe", "edebiyat"],
    "Ara Sınıf": ["geometri", "fizik", "kimya", "biyoloji", "turkce", "tarih", "cografya",
                  "felsefe", "edebiyat", "tyt_matematik", "problemler"],
    "LGS": ["lgs_matematik", "lgs_fen", "lgs_turkce", "lgs_inkilap", "lgs_dinkulturu", "lgs_ingilizce"]
}

def clean_lesson_name(table_name: str) -> str:
    """Converts table name to display name (e.g. tyt_matematik -> TYT Matematik)."""
    parts = table_name.split("_")
    capped = []
    for p in parts:
        if p in ["tyt", "ayt", "lgs", "yks"]:
            capped.append(p.upper())
        else:
            capped.append(p.capitalize())
    return " ".join(capped)

@app.get("/api/matrix/init")
def get_matrix_init():
    """Returns lesson groups and their display names."""
    groups = {}
    for grp, tables in GRUP_DERSLER.items():
        groups[grp] = []
        for tbl in tables:
            groups[grp].append({
                "table": tbl,
                "name": clean_lesson_name(tbl)
            })
    return groups

class Topic(BaseModel):
    id: int
    name: str

class MatrixData(BaseModel):
    topics: List[Topic]
    books: List[str]
    existing: List[dict] # New field: [{topic_id: 1, book: "X", status: "devam"}]

@app.get("/api/matrix/{table_name}", response_model=MatrixData)
def get_matrix_data(table_name: str, student_id: int = Query(None)):
    con = db.get_conn()
    cur = con.cursor()
    
    # 1. Get Topics
    try:
        cur.execute(f"SELECT id, konu FROM {table_name} ORDER BY id")
        topics = [Topic(id=r[0], name=r[1]) for r in cur.fetchall()]
    except Exception:
        return MatrixData(topics=[], books=[], existing=[])

    # 2. Get Books (from columns AND 'kitap' table)
    # Hybrid approach: Supports both old-style (column-based) and new-style (row-based) book management
    
    # A) Column-based (Legacy)
    cur.execute(f"PRAGMA table_info({table_name})")
    cols = [r[1] for r in cur.fetchall()]
    books_cols = [c for c in cols if c not in ('id', 'konu', 'sinif', 'video_suresi', 'Sınıf')]
    
    # B) Row-based (New Standard via 'kitap' table)
    # Ensure we look for the exact table name
    cur.execute("SELECT ad FROM kitap WHERE ders=? ORDER BY ad", (table_name,))
    books_rows = [r[0] for r in cur.fetchall()]
    
    # Merge and Dedup
    books = sorted(list(set(books_cols + books_rows)))

    # 3. Get Existing Assignments (if student_id provided)
    # 3. Get Existing Assignments (if student_id provided)
    existing = []
    if student_id:
        try:
            # Get existing homeworks for this student and this lesson table (normalized name)
            # The 'ders' column in 'odev' usually matches the table name or a variation.
            # We strictly compare UPPER(ders) with table_name.
            clean_name = table_name.upper()
            cur.execute(
                "SELECT konu_id, kitap_ad, durum FROM odev WHERE ogrenci_id=? AND REPLACE(UPPER(ders), ' ', '_') = ?", 
                (student_id, clean_name)
            )
            for r in cur.fetchall():
                existing.append({
                    "topic_id": r[0],
                    "book": r[1],
                    "status": r[2]
                })
        except Exception as e:
            print(f"Error fetching existing: {e}")

    return {
        "topics": topics,
        "books": books,
        "existing": existing
    }

class BulkHomeworkItem(BaseModel):
    topic_id: int
    topic_name: str
    book_name: str
    
class BulkHomeworkCreate(BaseModel):
    student_id: int
    lesson_table: str
    lesson_name: str
    items: List[BulkHomeworkItem]
    due_date: Optional[str] = None

@app.post("/api/homework/bulk")
def create_bulk_homework(data: BulkHomeworkCreate):
    """
    Creates multiple homeworks at once (Matrix save).
    """
    con = db.get_conn()
    cur = con.cursor()
    try:
        # 1. Create odev_kume
        verilis = datetime.now().strftime("%Y-%m-%d")
        if data.due_date:
            bitis = data.due_date
        else:
            from datetime import timedelta
            bitis = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            
        cur.execute(
            "INSERT INTO odev_kume(ogrenci_id, verilis_tarihi, bitis_tarihi) VALUES(?,?,?)",
            (data.student_id, verilis, bitis)
        )
        kume_id = cur.lastrowid
        
        count = 0
        for item in data.items:
            # Auto-save book
            if item.book_name and item.book_name.strip():
                 try:
                     cur.execute("INSERT OR IGNORE INTO kitap(ders, ad) VALUES(?,?)", (data.lesson_table, item.book_name.strip()))
                 except: pass

            # Inser into odev
            cur.execute(
                """INSERT INTO odev
                (kume_id, ogrenci_id, ders, konu_id, konu_ad, kitap_ad, saat_dk, aciklama, durum, verilis_tarihi)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (kume_id, data.student_id, data.lesson_table, item.topic_id, item.topic_name, item.book_name, 0, "", "devam", verilis)
            )
            odev_id = cur.lastrowid
            
            # Insert into odev_satir
            cur.execute(
                """INSERT INTO odev_satir
                (ogrenci_id, kume_id, odev_id, ders, kitap, konu, tarih, durum)
                VALUES(?,?,?,?,?,?,?,?)""",
                (data.student_id, kume_id, odev_id, data.lesson_name, item.book_name, item.topic_name, verilis, "devam")
            )
            count += 1
            
        con.commit()
        return {"status": "success", "message": f"{count} homeworks created", "kume_id": kume_id}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Book Management APIs ---

class BookCreate(BaseModel):
    lesson_table: str
    book_name: str

@app.post("/api/books")
def create_book(book: BookCreate):
    """Adds a new book to the global pool (kitap table)."""
    con = db.get_conn()
    try:
        con.execute("INSERT OR IGNORE INTO kitap(ders, ad) VALUES(?,?)", (book.lesson_table, book.book_name))
        con.commit()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/books/{lesson_table}")
def get_books(lesson_table: str):
    """Returns all books for a lesson from the pool."""
    con = db.get_conn()
    cur = con.execute("SELECT ad FROM kitap WHERE ders=? ORDER BY ad", (lesson_table,))
    return [r[0] for r in cur.fetchall()]

class StudentBookAssign(BaseModel):
    student_id: int
    lesson_table: str
    book_name: str
    action: str = "add" # add or remove

@app.post("/api/student/books")
def assign_student_book(data: StudentBookAssign):
    """Assigns or removes a book for a student."""
    con = db.get_conn()
    try:
        if data.action == "add":
            verilis = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Ensure column exists (legacy db protection)
            try:
                con.execute(f"ALTER TABLE ogrenci_kitap ADD COLUMN eklenme_tarih TEXT")
            except:
                pass
                
            con.execute(
                "INSERT OR IGNORE INTO ogrenci_kitap(ogrenci_id, ders, kitap_ad, eklenme_tarih) VALUES(?,?,?,?)",
                (data.student_id, data.lesson_table, data.book_name, verilis)
            )
        else:
            con.execute(
                "DELETE FROM ogrenci_kitap WHERE ogrenci_id=? AND ders=? AND kitap_ad=?",
                (data.student_id, data.lesson_table, data.book_name)
            )
        con.commit()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/student/{student_id}/books/{lesson_table}")
def get_student_books(student_id: int, lesson_table: str):
    """Returns books assigned to a specific student for a lesson."""
    con = db.get_conn()
    cur = con.execute("SELECT kitap_ad FROM ogrenci_kitap WHERE ogrenci_id=? AND ders=?", (student_id, lesson_table))
    return [r[0] for r in cur.fetchall()]

# --- Homework Tracking & Control (Screenshot 4) ---

class HomeworkItemDetail(BaseModel):
    id: int
    lesson: str
    book: str
    topic: str
    duration: int
    status: str # 'tamam' or 'devam'
    date: str
    
class TrackingStats(BaseModel):
    total: int
    completed: int
    percent: int
    active: int

@app.get("/api/student/{student_id}/tracking")
def get_student_tracking(student_id: int, lesson: Optional[str] = None, status: Optional[str] = None, cluster_id: Optional[int] = None):
    """
    Returns detailed homework list for a student with filters.
    Switched to use 'odev' table to match desktop app data.
    """
    con = db.get_conn()
    cur = con.cursor()
    
    # Base query: odev JOIN odev_kume
    # odev columns: id, kume_id, ders, kitap_ad, konu_ad, saat_dk, durum
    # odev_kume columns: verilis_tarihi
    query = """
        SELECT d.id, d.ders, d.kitap_ad, d.konu_ad, d.saat_dk, d.durum, k.verilis_tarihi
        FROM odev d
        JOIN odev_kume k ON d.kume_id = k.id
        WHERE d.ogrenci_id = ?
    """
    params = [student_id]
    
    if cluster_id:
        query += " AND d.kume_id = ?"
        params.append(cluster_id)
        
    # Filters
    if lesson and lesson != "Hepsi":
        query += " AND d.ders = ?"
        params.append(lesson)
        
    if status and status != "Hepsi":
        # Desktop app uses 'yapildi' for done, 'devam' for pending.
        # Checkboxes in frontend send 'tamam'/'devam'. We need to map properly.
        # Frontend 'tamam' should map to DB 'yapildi'.
        if status == "Yapılanlar":
            query += " AND d.durum = 'yapildi'"
        elif status == "Yapılmayanlar":
             query += " AND d.durum != 'yapildi'"
    
    query += " ORDER BY d.id DESC"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    items = []
    completed_count = 0
    total_count = 0
    
    for r in rows:
        # DB 'yapildi' -> Frontend 'tamam' (or keep 'yapildi' if we update frontend)
        # Let's standardize on Frontend using 'tamam' and API mapping it.
        # But wait, frontend logic: isDone = currentStatus === 'tamam'.
        # If DB returns 'yapildi', frontend won't check the box unless we map it.
        
        db_status = r[5]
        status_mapped = "tamam" if db_status == "yapildi" else "devam"
        
        is_done = (status_mapped == 'tamam')
        total_count += 1
        if is_done: completed_count += 1
        
        items.append(HomeworkItemDetail(
            id=r[0],
            lesson=r[1] or "",
            book=r[2] or "",
            topic=r[3] or "",
            duration=r[4] or 0,
            status=status_mapped, 
            date=r[6] or ""
        ))
        
    percent = int((completed_count / total_count * 100)) if total_count > 0 else 0
    
    stats = TrackingStats(
        total=total_count,
        completed=completed_count,
        percent=percent,
        active=total_count - completed_count
    )
    
    return {"stats": stats, "items": items}

class StatusUpdate(BaseModel):
    homework_ids: List[int]
    status: str # 'tamam' or 'devam'

@app.post("/api/homework/status/bulk")
def update_homework_status_bulk(data: StatusUpdate):
    """
    Updates status of multiple homework items in 'odev' table.
    """
    con = db.get_conn()
    cur = con.cursor()
    try:
        # Map frontend 'tamam' -> DB 'yapildi'
        db_status = "yapildi" if data.status == "tamam" else "devam"
        
        # Build query
        ids_placeholder = ",".join("?" for _ in data.homework_ids)
        if not ids_placeholder:
            return {"status": "success", "message": "No IDs provided"}
            
        params = [db_status]
        query = f"UPDATE odev SET durum=? WHERE id IN ({ids_placeholder})"
        params.extend(data.homework_ids)
        
        cur.execute(query, params)
        con.commit()
        return {"status": "success", "updated": cur.rowcount}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Clusters API (For Split View) ---

class ClusterStats(BaseModel):
    id: int
    given_date: str
    due_date: str
    total_items: int
    completed_items: int
    percent: int
    status_label: str # "Son: 2025-12-23" etc

@app.get("/api/student/{student_id}/clusters")
def get_student_clusters(student_id: int):
    """
    Returns list of homework clusters (assignments) for the student.
    Calculates progress for each cluster.
    """
    con = db.get_conn()
    cur = con.cursor()
    
    # Get all clusters for student
    # Join with odev to calculate stats
    query = """
        SELECT k.id, k.verilis_tarihi, k.bitis_tarihi, 
               COUNT(d.id) as total,
               SUM(CASE WHEN d.durum='yapildi' THEN 1 ELSE 0 END) as done
        FROM odev_kume k
        LEFT JOIN odev d ON d.kume_id = k.id
        WHERE k.ogrenci_id = ?
        GROUP BY k.id
        ORDER BY k.id DESC
    """
    cur.execute(query, (student_id,))
    rows = cur.fetchall()
    
    clusters = []
    for r in rows:
        total = r[3] or 0
        done = r[4] or 0
        pct = int((done / total * 100)) if total > 0 else 0
        
        clusters.append(ClusterStats(
            id=r[0],
            given_date=r[1] or "",
            due_date=r[2] or "",
            total_items=total,
            completed_items=done,
            percent=pct,
            status_label=f"Son: {r[2]}" if r[2] else "Süresiz"
        ))
        
    return clusters

# --- Suggestions API (For Homework Tracking Form) ---

@app.get("/api/student/{student_id}/suggestions")
def get_student_suggestions(student_id: int):
    """
    Returns 'Related Homeworks' (Öneriler) for the tracking form.
    Logic mimics desktop app's OneriPaneli:
    - Overdue items (Gecikmiş) -> Red
    - Active items (Devam) -> Normal/Yellow
    """
    con = db.get_conn()
    cur = con.cursor()
    
    # 1. Fetch 'Overdue' or 'Active' homeworks
    # In desktop app, 'gecikmis' means due_date passed and not done.
    # 'odev_kume' has 'bitis_tarihi'.
    now_str = datetime.now().strftime("%Y-%m-%d")
    
    query = """
        SELECT d.id, d.ders, d.kitap_ad, d.konu_ad, d.saat_dk, d.durum, k.bitis_tarihi
        FROM odev d
        JOIN odev_kume k ON d.kume_id = k.id
        WHERE d.ogrenci_id = ? 
          AND d.durum != 'yapildi'
        ORDER BY k.bitis_tarihi ASC
    """
    cur.execute(query, (student_id,))
    rows = cur.fetchall()
    
    suggestions = []
    seen_keys = set()
    
    for r in rows:
        # Key for dedup
        key = f"{r[1]}|{r[2]}|{r[3]}"
        if key in seen_keys: continue
        seen_keys.add(key)
        
        # Determine status/color logic
        due_date = r[6]
        status = "normal"
        if due_date and due_date < now_str:
            status = "gecikmis"
        elif due_date and due_date == now_str:
             status = "yakinda"
             
        suggestions.append({
            "id": r[0],
            "lesson": r[1],
            "book": r[2],
            "topic": r[3],
            "duration": r[4],
            "status": status,
            "due_date": due_date
        })
        
    return suggestions

# --- WhatsApp Reporting (Screenshot 4, Item 58) ---
@app.post("/api/student/{student_id}/whatsapp")
def generate_whatsapp_text(student_id: int, lesson: Optional[str] = None, status: Optional[str] = None):
    """
    Generates the WhatsApp report text for the student's homework.
    Uses 'odev' table.
    """
    con = db.get_conn()
    cur = con.cursor()
    
    query = """
        SELECT d.id, d.ders, d.kitap_ad, d.konu_ad, d.saat_dk, d.durum, k.verilis_tarihi
        FROM odev d
        JOIN odev_kume k ON d.kume_id = k.id
        WHERE d.ogrenci_id = ?
    """
    params = [student_id]
    
    if lesson and lesson != "Hepsi":
         query += " AND d.ders = ?"
         params.append(lesson)
    
    if status and status != "Hepsi":
         if status == "Yapılanlar": query += " AND d.durum = 'yapildi'"
         elif status == "Yapılmayanlar": query += " AND d.durum != 'yapildi'"
         
    query += " ORDER BY d.id DESC LIMIT 50"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    if not rows:
        return {"text": "Gösterilecek ödev bulunamadı."}
        
    # Get Student Name
    s_row = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (student_id,)).fetchone()
    student_name = f"{s_row[0]} {s_row[1]}" if s_row else "Öğrenci"
    
    # Build Text
    parts = []
    parts.append(f"🎓 *Ödev Özeti* - {student_name}")
    parts.append(f"📅 *Tarih:* {datetime.now().strftime('%d.%m.%Y')}")
    parts.append("")
    
    table_lines = []
    total_minutes = 0
    completed_count = 0
    
    for r in rows:
        db_status = r[5]
        is_done = (db_status == 'yapildi')
        icon = "✅" if is_done else "⏳"
        
        line = f"{icon} {r[1]} / {r[2]} / {r[3]}"
        dk = r[4] or 0
        if dk > 0:
            line += f" ({dk} dk)"
            if is_done: total_minutes += dk
            
        if is_done: completed_count += 1
        table_lines.append(line)
        
    if table_lines:
        parts.append("```")
        parts.extend(table_lines)
        parts.append("```")
        
    parts.append("")
    
    stats_lines = []
    stats_lines.append(f"📊 *İlerleme:* {completed_count}/{len(rows)}")
    if total_minutes > 0:
         stats_lines.append(f"⏱️ *Toplam Süre:* {total_minutes} dk")
         
    stats_lines.append("🚀 _Başarılar dileriz._")
    
    parts.extend(stats_lines)
    
# --- Embedded HTML Dashboard (Lite) ---
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Create templates dir if not exists
import os
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
    
# Create static dir if not exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Mount Static Files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Serves the Single Page Application (SPA) dashboard.
    """
    index_path = os.path.join(templates_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Mobil Panel Hazırlanıyor...</h1><p>Lütfen 'index.html' dosyasının templates klasöründe olduğundan emin olun.</p>"

@app.get("/report", response_class=HTMLResponse)
def get_html_report():
    """
    Serves a standalone HTML dashboard for quick reporting without Node.js.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YKS/LGS Takip Raporu</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #f8fafc; }
            .card { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
            .gradient-text { background: linear-gradient(to right, #2563eb, #7c3aed); -webkit-background-clip: text; color: transparent; }
        </style>
    </head>
    <body class="p-6 md:p-12">
        <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="flex justify-between items-center mb-10">
                <div>
                    <h1 class="text-3xl font-extrabold text-slate-800">YKS/LGS <span class="gradient-text">Takip Sistemi</span></h1>
                    <p class="text-slate-500 mt-1">Detaylı Performans Raporu</p>
                </div>
                <button onclick="window.print()" class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-medium shadow-lg transition flex items-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
                    Yazdır / PDF
                </button>
            </div>

            <!-- Stats Grid -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
                <div class="card border-l-4 border-blue-500">
                    <div class="text-slate-500 text-sm font-medium mb-1">Toplam Öğrenci</div>
                    <div class="text-4xl font-bold text-slate-800" id="stat-students">-</div>
                </div>
                <div class="card border-l-4 border-yellow-500">
                    <div class="text-slate-500 text-sm font-medium mb-1">Bekleyen Ödevler</div>
                    <div class="text-4xl font-bold text-slate-800" id="stat-pending">-</div>
                </div>
                <div class="card border-l-4 border-green-500">
                    <div class="text-slate-500 text-sm font-medium mb-1">Başarı Oranı</div>
                    <div class="text-4xl font-bold text-slate-800" id="stat-success">-%</div>
                </div>
                <div class="card bg-gradient-to-br from-indigo-600 to-violet-600 text-white">
                    <div class="text-indigo-100 text-xs font-semibold uppercase tracking-wider mb-2">Günün Sözü</div>
                    <p class="text-sm font-medium italic" id="stat-quote">"Yükleniyor..."</p>
                </div>
            </div>

            <!-- Charts & Content -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <!-- Students List -->
                <div class="card lg:col-span-2">
                    <h2 class="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
                        <span class="w-2 h-6 bg-indigo-500 rounded-full"></span>
                        Öğrenci Listesi
                    </h2>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse">
                            <thead>
                                <tr class="text-slate-400 text-xs uppercase border-b border-slate-100">
                                    <th class="pb-3 pl-2">Ad Soyad</th>
                                    <th class="pb-3">Sınıf</th>
                                    <th class="pb-3">Okul</th>
                                    <th class="pb-3 text-right pr-2">Durum</th>
                                </tr>
                            </thead>
                            <tbody id="table-students" class="text-sm text-slate-600">
                                <tr><td colspan="4" class="py-4 text-center">Yükleniyor...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Simple Chart -->
                <div class="card">
                    <h2 class="text-xl font-bold text-slate-800 mb-6">Genel Durum</h2>
                    <canvas id="myChart"></canvas>
                    <div class="mt-6 space-y-3">
                        <div class="flex justify-between items-center text-sm">
                            <span class="flex items-center gap-2 text-slate-600"><span class="w-3 h-3 rounded-full bg-green-500"></span>Tamamlanan</span>
                            <span class="font-bold text-slate-800" id="lbl-done">0</span>
                        </div>
                        <div class="flex justify-between items-center text-sm">
                            <span class="flex items-center gap-2 text-slate-600"><span class="w-3 h-3 rounded-full bg-yellow-400"></span>Devam Eden</span>
                            <span class="font-bold text-slate-800" id="lbl-pending">0</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // API Fetcher
            async function loadData() {
                try {
                    // 1. Dashboard Stats
                    const resStats = await fetch('/api/dashboard');
                    const stats = await resStats.json();
                    
                    document.getElementById('stat-students').innerText = stats.student_count;
                    document.getElementById('stat-pending').innerText = stats.pending_tasks;
                    document.getElementById('stat-success').innerText = `%${stats.success_rate}`;
                    document.getElementById('stat-quote').innerText = `"${stats.quote}"`;

                    // Chart Data Setup (Approximate from success rate)
                    const done = stats.success_rate; 
                    const pending = 100 - done;
                    
                    document.getElementById('lbl-done').innerText = `${done}%`;
                    document.getElementById('lbl-pending').innerText = `${pending}%`;

                    new Chart(document.getElementById('myChart'), {
                        type: 'doughnut',
                        data: {
                            labels: ['Tamamlanan', 'Bekleyen'],
                            datasets: [{
                                data: [done, pending],
                                backgroundColor: ['#22c55e', '#facc15'],
                                borderWidth: 0
                            }]
                        },
                        options: { cutout: '70%', plugins: { legend: { display: false } } }
                    });

                    // 2. Students Table
                    const resStd = await fetch('/api/students');
                    const students = await resStd.json();
                    const tbody = document.getElementById('table-students');
                    tbody.innerHTML = '';
                    
                    students.forEach((s, i) => {
                        const tr = document.createElement('tr');
                        tr.className = "border-b border-slate-50 last:border-0 hover:bg-slate-50 transition";
                        tr.innerHTML = `
                            <td class="py-3 pl-2 font-medium text-slate-800">${s.ad_soyad}</td>
                            <td class="py-3 text-slate-500">${s.sinif || '-'}</td>
                            <td class="py-3 text-slate-500">${s.okul || '-'}</td>
                            <td class="py-3 pr-2 text-right"><span class="bg-green-100 text-green-700 px-2 py-1 rounded text-xs font-bold">Aktif</span></td>
                        `;
                        tbody.appendChild(tr);
                    });

                } catch (e) {
                    console.error(e);
                    alert("Veri yüklenirken hata oluştu.");
                }
            }
            loadData();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- Mobile Assignment Helpers ---

@app.get("/api/lessons/list")
def get_lessons_list(student_id: Optional[int] = Query(None)):
    """Returns a list of available lessons. If student_id is provided, filters by their curriculum."""
    lessons = []
    seen = set()
    
    # 1. Try to get lessons for specific student
    if student_id and hasattr(db, 'get_student_curriculum'):
        try:
            student_lessons = db.get_student_curriculum(student_id)
            if student_lessons:
                for tbl in student_lessons:
                    if tbl not in seen:
                        # Try to get display name from db.get_lesson_config if available, else clean_name
                        display_name = clean_lesson_name(tbl)
                        if hasattr(db, 'get_lesson_config'):
                            try:
                                configs = db.get_lesson_config(db.get_conn())
                                for c in configs:
                                    if c['id'] == tbl:
                                        display_name = c['ad']
                                        break
                            except: pass
                        
                        lessons.append({"id": tbl, "name": display_name})
                        seen.add(tbl)
                return sorted(lessons, key=lambda x: x["name"])
        except Exception as e:
            print(f"Error getting student curriculum: {e}")

    # 2. Fallback: Return ALL lessons (from DB DERS_TABLOLARI if available, else hardcoded)
    all_tables = []
    if hasattr(db, 'DERS_TABLOLARI') and db.DERS_TABLOLARI:
         all_tables = db.DERS_TABLOLARI
    else:
         for grp, tables in GRUP_DERSLER.items():
            all_tables.extend(tables)
            
    for tbl in all_tables:
        if tbl not in seen:
            display_name = clean_lesson_name(tbl)
            # Try to get nicer name from DB if possible
            if hasattr(db, 'get_lesson_config'):
                try:
                    configs = db.get_lesson_config(db.get_conn())
                    for c in configs:
                        if c['id'] == tbl:
                            display_name = c['ad']
                            break
                except: pass

            lessons.append({"id": tbl, "name": display_name})
            seen.add(tbl)
            
    return sorted(lessons, key=lambda x: x["name"])

@app.get("/api/books/list")
def get_books_for_lesson(lesson_id: str = Query(...)):
    """Returns available books for a given lesson table."""
    con = db.get_conn()
    cur = con.cursor()
    
    books = []
    
    # Debug info
    print(f"[*] API Books Request: lesson_id='{lesson_id}' | DB: {db.DB_PATH}")
    
    # 0. Clean input and Normalize (Critical Step)
    # Frontend sends "TYT Matematik" (Display Name) but DB needs "tyt_matematik" (Key)
    raw_input = lesson_id.strip()
    
    # Try to find the correct DB key corresponding to this display name
    # 1. Check if it matches a key directly
    target_key = raw_input
    
    # 2. If it has spaces or uppercase, it might be a display name. 
    # Let's try to reverse-map it using our helpers.
    found_key = None
    
    # Normalize input for comparison (e.g. "TYT Matematik" -> "tyt matematik")
    norm_input = raw_input.lower().replace("ı", "i").replace("İ", "i")
    
    for grp_key, tables in GRUP_DERSLER.items():
        if found_key: break
        for tbl in tables:
            # Generate display name for this table
            d_name = clean_lesson_name(tbl)
            # Compare normalized versions
            norm_d_name = d_name.lower().replace("ı", "i").replace("İ", "i")
            
            # Exact match (tyt_matematik == input)
            if tbl == raw_input:
                found_key = tbl
                break
                
            # Display match (TYT Matematik == input)
            if norm_d_name == norm_input:
                found_key = tbl
                break
                
            # Flexible match (tyt matematik == input)
            if tbl.replace("_", " ") == norm_input:
                found_key = tbl
                break
                
    if found_key:
        print(f"[*] RESOLVED: '{raw_input}' -> '{found_key}'")
        target_key = found_key
    else:
        # Fallback: simple snake_case conversion
        print(f"[*] FALLBACK: '{raw_input}' -> snake_case")
        target_key = raw_input.lower().replace(" ", "_").replace("ı", "i").replace("İ", "i")

    
    # 1. 'kitap' tablosundan global kitaplar (Case Insensitive)
    try:
        # Use the resolved key (target_key)
        cur.execute("SELECT ad FROM kitap WHERE LOWER(ders)=LOWER(?) ORDER BY ad", (target_key,))
        global_books = [r[0] for r in cur.fetchall()]
        books.extend(global_books)
        print(f"[*] Found {len(global_books)} books in 'kitap' table for '{target_key}'.")
    except Exception as e:
        print(f"Error fetching global books: {e}")

    # 2. Tablo yapısından kitapları çek (Matrix mantığı - Legacy)
    try:
        # Sanitize for table name usage
        # Use target_key which should be 'tyt_matematik' style
        import re
        safe_tbl = re.sub(r'[^a-zA-Z0-9_ğüşıöçĞÜŞİÖÇ]', '', target_key)
        
        target_tbl = None
        
        # Check explicit table existence
        try:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (safe_tbl,))
            if cur.fetchone():
                target_tbl = safe_tbl
        except:
             pass
             
        # Look in GROUP map if not found
        if not target_tbl:
            for grp_key, tables in GRUP_DERSLER.items():
                if safe_tbl in tables:
                     try:
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (safe_tbl,))
                        if cur.fetchone():
                            target_tbl = safe_tbl
                            break
                     except: pass
                     try:
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (safe_tbl,))
                        if cur.fetchone():
                            target_tbl = safe_tbl
                            break
                     except: pass
                        
        if target_tbl:
            # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
            cur.execute(f"PRAGMA table_info({target_tbl})")
            cols = [r[1] for r in cur.fetchall()]
            
            ignored_cols = {
                'id', 'konu', 'konu_kodu', 'sinif', 'alt_konu', 'video_suresi', 'Sınıf', 'Konu', 
                'video_link', 'tamamlanma', 'soru_sayisi', 'index', 'level_0', 'tarih', 'durum'
            }
            
            col_books = []
            for c in cols:
                # Filter out system cols or standard non-book cols
                if c not in ignored_cols and not c.startswith('_') and not c.startswith('level_') and not c[0].isdigit():
                     col_books.append(c)
            
            books.extend(col_books)
            print(f"[*] Found {len(col_books)} books in table columns of '{target_tbl}'.")
            
    except Exception as e:
        print(f"Error fetching table books for {lesson_id}: {e}")

    # Final check
    if not books:
         print("[!] No books found. Adding debug entry.")
         # Return granular debug info
         books.append(f"DBG_INPUT: {lesson_id}")
         books.append(f"DBG_RESOLVED: {target_key}")
         books.append(f"DBG_DB_PATH: {db.DB_PATH}")
         
         # Test a direct query to see if connection is even working on the right DB
         try:
             chk = cur.execute("SELECT count(*) FROM kitap").fetchone()
             books.append(f"DBG_KITAP_COUNT: {chk[0]}")
             chk2 = cur.execute("SELECT count(*) FROM kitap WHERE ders='tyt_matematik'").fetchone()
             books.append(f"DBG_TYT_MAT_EXACT: {chk2[0]}")
         except Exception as e:
             books.append(f"DBG_ERR: {str(e)}")

    # Tekilleştir ve Sırala
    try:
        con.close()
    except:
        pass
        
    return sorted(list(set(books)))

@app.get("/api/student/{student_id}/info")
def get_student_detail(student_id: int):
    """Returns detailed info for the Profile screen."""
    con = db.get_conn()
    cur = con.cursor()
    # ogrenci columns: id, ad, soyad, veli_ad, veli_tel1, veli_tel2, ogrenci_tel, notlar, ...
    # Mevcut şemayı tahmin ederek çekiyoruz, hata olursa handle ederiz.
    try:
        cur.execute("SELECT * FROM ogrenci WHERE id=?", (student_id,))
        # Kolon isimlerini al
        col_names = [description[0] for description in cur.description]
        row = cur.fetchone()
        
        if not row:
            return {"error": "Öğrenci bulunamadı"}
            
        data = dict(zip(col_names, row))
        
        # Gereksiz/Hassas olmayan verileri temizle veya formatla
        return {
            "ad_soyad": f"{data.get('ad', '')} {data.get('soyad', '')}",
            "sinif": data.get('alt_grup', '') or data.get('sinif', ''),
            "okul": data.get('ana_grup', '') or data.get('okul', ''),
            "ogrenci_tel": data.get('ogrenci_tel', '') or data.get('telefon', '-'),
            "veli_ad": data.get('veli_ad', '-'),
            "veli_tel1": data.get('veli_tel1', '-'),
            "notlar": data.get('aciklama', '') or data.get('notlar', '')
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/topics/list")
def get_topics_for_lesson(lesson_id: str = Query(...), student_id: Optional[int] = None):
    """
    Returns topics for a given lesson table (e.g. tyt_matematik).
    If student_id is provided, also returns the assignment status for each topic.
    """
    con = db.get_conn()
    cur = con.cursor()
    try:
        # Validate table name to prevent SQL Injection (basic check)
        valid_tables = []
        for grp in GRUP_DERSLER.values():
            valid_tables.extend(grp)
            
        if lesson_id not in valid_tables:
            return []
            
        # 1. Get all topics from the lesson table
        cur.execute(f"SELECT id, konu FROM {lesson_id} ORDER BY id")
        topics_rows = cur.fetchall()
        
        # 2. If student_id is present, fetch existing assignments
        assignments_map = {} # topic_name -> list of {book, status}
        if student_id:
            # Fetch from odev_satir
            # We match by 'ders' (lesson_id) and 'konu_ad'
            # Note: in desktop app, lesson names might be mapped. 
            # Ideally we match by 'ders' column which stores 'lesson_id' (table name) or pretty name?
            # Let's try both exact status match
            cur.execute(
                "SELECT konu_ad, kitap, durum FROM odev_satir WHERE ogrenci_id=? AND ders=?",
                (student_id, lesson_id)
            )
            assign_rows = cur.fetchall()
            for r in assign_rows:
                k_ad, kitap, durum = r[0], r[1], r[2]
                if k_ad not in assignments_map:
                    assignments_map[k_ad] = []
                assignments_map[k_ad].append({"book": kitap, "status": durum})

        # 3. Build response
        topics = []
        for r in topics_rows:
            t_id, t_name = r[0], r[1]
            status_info = assignments_map.get(t_name, [])
            topics.append({
                "id": t_id, 
                "name": t_name,
                "assignments": status_info
            })
            
            
        return topics
    except Exception as e:
        print(f"Error fetching topics for {lesson_id}: {e}")
        return []
    finally:
        if con: con.close()

