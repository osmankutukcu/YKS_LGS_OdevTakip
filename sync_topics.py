import sqlite3
import json
import os

DB_PATH = "YKS_LGS_HomeworkManager_v2.db"
JSON_PATH = "assets/curriculum.json"

# Tables containing curriculum topics
TABLES = [
    'tyt_matematik', 'ayt_matematik', 'problemler', 'geometri',
    'fizik', 'kimya', 'biyoloji',
    'turkce', 'paragraf', 'tarih', 'cografya', 'felsefe', 'edebiyat',
    'lgs_matematik', 'lgs_fen', 'lgs_turkce', 'lgs_inkilap', 'lgs_ingilizce', 'lgs_din', 'lgs_dinkulturu'
]

def load_existing():
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("topics", {})
        except: return {}
    return {}

def run_sync():
    existing_data = load_existing()
    print(f"Loaded {len(existing_data)} existing high-quality topics.")
    
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    new_count = 0
    
    for tbl in TABLES:
        try:
            # Check table existence
            cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'")
            if not cur.fetchone():
                continue
            
            # Get topics
            cur.execute(f"SELECT konu FROM {tbl}")
            rows = cur.fetchall()
            
            for r in rows:
                konu = r[0]
                if not konu: continue
                konu = konu.strip()
                
                # If topic is not in our Manual/Existing DB, add it
                if konu not in existing_data:
                    # Contextual Default Tip
                    tip = f"{konu} konusu için bol soru çözün."
                    if "fizik" in tbl: tip = "Görsel hafıza ve formül kartları kullanın."
                    if "matematik" in tbl: tip = "İşlem hatası yapmamaya dikkat edin."
                    if "paragraf" in tbl: tip = "Her gün süre tutarak çözün."
                    
                    existing_data[konu] = {
                        "importance": "Belirleniyor...",
                        "questions": "?",
                        "tip": f"YKS/LGS Koçu: {tip}"
                    }
                    new_count += 1
                    
        except Exception as e:
            print(f"Skipping {tbl}: {e}")
            
    con.close()
    
    # Save merged data
    final_data = {"topics": existing_data}
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
        
    print(f"Sync Complete. Added {new_count} new topics from DB. Total: {len(existing_data)}")

if __name__ == "__main__":
    run_sync()
