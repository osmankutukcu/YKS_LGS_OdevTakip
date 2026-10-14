# -*- coding: utf-8 -*-
"""
web_api/sync_engine.py
======================
Modüler Çevrimdışı (Offline-First) Senkronizasyon Motoru.

Bu modül:
1. Bilgisayardan telefona tüm öğrenci, müfredat, kitap ve ödev durumlarını
   tek bir hafif snapshot paketi olarak aktarır (GET /api/sync/snapshot).
2. Bilgisayar kapalıyken telefondan girilen çevrimdışı ödevleri ve durum güncellemelerini
   bilgisayar açıldığında tek tıkla toplu olarak alır ve SQLite veritabanına
   mevcut masaüstü mantığıyla güvenle işler (POST /api/sync/push).
3. Mevcut masaüstü tablolarına ve dosyalarına dokunmaz; tamamen bağımsız ve modülerdir.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import sqlite3
import db
from utils.homework_status import is_completed
from web_api.homework_store import set_single_line_done

sync_router = APIRouter(prefix="/api/sync", tags=["Offline Sync"])

class MutationItem(BaseModel):
    id: str = Field(min_length=8, max_length=128)
    type: str # 'ASSIGN_HOMEWORK' | 'COMPLETE_HOMEWORK'
    payload: Dict[str, Any]
    created_at: Optional[str] = None

class SyncPushRequest(BaseModel):
    mutations: List[MutationItem] = Field(max_length=200)
    database_id: Optional[str] = Field(default=None, max_length=128)

@sync_router.get("/status")
def get_sync_status():
    """Bilgisayarın açık ve erişilebilir olup olmadığını test eder (Ping)."""
    from web_api.sync_transactions import database_identity, ensure_desktop_schema
    con = db.get_conn()
    try:
        with con:
            required = {'ogrenci', 'odev', 'odev_satir', 'odev_kume'}
            existing = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not required.issubset(existing):
                raise HTTPException(503, 'Geçerli masaüstü veritabanı bulunamadı')
            con.execute('BEGIN IMMEDIATE')
            ensure_desktop_schema(con)
            database_id = database_identity(con)
    finally:
        con.close()
    return {
        "database_id": database_id,
        "status": "online",
        "server_time": datetime.now().isoformat(),
        "database": "connected"
    }

@sync_router.get("/snapshot")
def get_sync_snapshot(student_id: Optional[int] = Query(None)):
    """
    Telefonun çevrimdışı (bilgisayar kapalıyken) çalışabilmesi için
    gerekli tüm verileri tek bir JSON paketi olarak döndürür.
    """
    from web_api.main import (
        get_lessons_list, get_student_books, get_books, 
        get_topics_for_lesson, get_student_tracking
    )
    
    con = db.get_conn()
    cur = con.cursor()
    try:
        from web_api.sync_transactions import database_identity, ensure_desktop_schema
        with con:
            con.execute('BEGIN IMMEDIATE')
            ensure_desktop_schema(con)
            ensure_desktop_schema(con)
            database_id = database_identity(con)
        snapshot_data_version = con.execute('PRAGMA data_version').fetchone()[0]
        # 1. Öğrenciler listesi
        today_str = datetime.now().date().isoformat()
        tmrw_str = (datetime.now().date() + timedelta(days=1)).isoformat()
        week_end_str = (datetime.now().date() + timedelta(days=7)).isoformat()

        cur.execute("""
            SELECT 
                d.ogrenci_id,
                COUNT(CASE WHEN d.durum NOT IN ('tamam', 'yapildi') AND k.bitis_tarihi IS NOT NULL AND substr(k.bitis_tarihi, 1, 10) < ? THEN 1 END) as overdue_cnt,
                COUNT(CASE WHEN d.durum NOT IN ('tamam', 'yapildi') AND substr(k.bitis_tarihi, 1, 10) = ? THEN 1 END) as today_cnt,
                COUNT(CASE WHEN d.durum NOT IN ('tamam', 'yapildi') AND substr(k.bitis_tarihi, 1, 10) = ? THEN 1 END) as tomorrow_cnt,
                COUNT(CASE WHEN d.durum NOT IN ('tamam', 'yapildi') AND substr(k.bitis_tarihi, 1, 10) >= ? AND substr(k.bitis_tarihi, 1, 10) <= ? THEN 1 END) as week_cnt,
                COUNT(CASE WHEN d.durum NOT IN ('tamam', 'yapildi') THEN 1 END) as pending_cnt
            FROM odev d
            JOIN odev_kume k ON d.kume_id = k.id
            GROUP BY d.ogrenci_id
        """, (today_str, today_str, tmrw_str, today_str, week_end_str))

        counts_map = {}
        for cr in cur.fetchall():
            counts_map[cr[0]] = {
                "overdue": cr[1] or 0,
                "today": cr[2] or 0,
                "tomorrow": cr[3] or 0,
                "week": cr[4] or 0,
                "pending": cr[5] or 0,
            }

        cur.execute("PRAGMA table_info(ogrenci)")
        cols = {r[1] for r in cur.fetchall()}
        sel_ogr_tel = "ogr_tel" if "ogr_tel" in cols else "'' as ogr_tel"
        sel_veli2 = "veli_tel2" if "veli_tel2" in cols else "'' as veli_tel2"
        sel_veli_ad = "veli_ad" if "veli_ad" in cols else "'' as veli_ad"
        sel_veli1 = "veli_tel1" if "veli_tel1" in cols else "'' as veli_tel1"

        cur.execute(f"SELECT id, ad, soyad, ana_grup, alt_grup, {sel_veli1}, {sel_ogr_tel}, {sel_veli2}, {sel_veli_ad} FROM ogrenci WHERE aktif=1 ORDER BY ad, soyad")
        students = []
        for r in cur.fetchall():
            s_id = r[0]
            sc = counts_map.get(s_id, {"overdue": 0, "today": 0, "tomorrow": 0, "week": 0, "pending": 0})
            full_name = f"{r[1]} {r[2]}".strip()
            group_label = f"{r[3]} ({r[4]})" if r[4] else (r[3] or "Genel")
            primary_phone = r[5] or r[6] or ""
            students.append({
                "id": s_id,
                "ad": r[1],
                "soyad": r[2],
                "ad_soyad": full_name,
                "sinif": r[4] or "",
                "okul": r[3] or "",
                "ana_grup": r[3],
                "alt_grup": r[4],
                "grup_etiketi": group_label,
                "telefon": primary_phone,
                "veli_tel1": r[5] or "",
                "ogr_tel": r[6] or "",
                "veli_tel2": r[7] or "",
                "veli_ad": r[8] or "",
                "overdue_count": sc["overdue"],
                "today_count": sc["today"],
                "tomorrow_count": sc["tomorrow"],
                "week_count": sc["week"],
                "pending_count": sc["pending"]
            })
            
        target_students = [s for s in students if (student_id is None or s["id"] == student_id)]
        
        # 2. Her öğrenci için dersler, kitaplar, konular ve aktif ödevler
        snapshot_data = {
            "version": 1,
            "generated_at": datetime.now().isoformat(),
            "database_id": database_id,
            "students": target_students,
            "curriculum": {}
        }
        
        for std in target_students:
            s_id = std["id"]
            std_lessons = get_lessons_list(s_id)
            snapshot_data["curriculum"][s_id] = {
                "lessons": std_lessons,
                "books": {},
                "topics": {},
                "active_homeworks": [],
                "status_fingerprints": {}
            }
            
            # Öğrencinin aktif ödevleri (Tab 4 Ödev Kontrol için)
            try:
                tracking = get_student_tracking(s_id)
                snapshot_data["curriculum"][s_id]["active_homeworks"] = tracking.get("items", [])
            except Exception as exc:
                raise HTTPException(503, 'Ödev kontrol verileri hazırlanamadı; eksik snapshot kaydedilmedi') from exc

            # The desktop code may modify assignments through a different
            # connection. Attach fingerprints to preserve pending edits.
            from web_api.sync_transactions import status_fingerprint
            for r in cur.execute('SELECT id,durum,tamamlanma_tarihi FROM odev WHERE ogrenci_id=?', (s_id,)):
                snapshot_data["curriculum"][s_id]["status_fingerprints"][str(r[0])] = status_fingerprint(r[0], r[1], r[2])

            # Her ders için kitaplar ve zengin konu matrisi
            for l in std_lessons:
                l_id = l["id"]
                try:
                    std_b = get_student_books(s_id, l_id)
                    all_b = get_books(l_id)
                    combined_books = std_b + [b for b in all_b if b not in std_b]
                    snapshot_data["curriculum"][s_id]["books"][l_id] = combined_books
                except Exception as exc:
                    raise HTTPException(503, 'Kitap verileri hazırlanamadı; eksik snapshot kaydedilmedi') from exc
                    
                try:
                    # Masaüstüyle birebir hesaplanmış durumlu konular
                    topics = get_topics_for_lesson(lesson_id=l_id, student_id=s_id)
                    snapshot_data["curriculum"][s_id]["topics"][l_id] = topics
                except Exception as exc:
                    raise HTTPException(503, 'Konu verileri hazırlanamadı; eksik snapshot kaydedilmedi') from exc
                    
        # If any other SQLite connection wrote during these many reads,
        # do NOT accept a mixed-time snapshot as a safe offline baseline.
        if con.execute('PRAGMA data_version').fetchone()[0] != snapshot_data_version:
            raise HTTPException(409, 'Veriler indirme sırasında değişti; lütfen yeniden deneyin')
        return snapshot_data
    finally:
        con.close()

@sync_router.post("/push")
def process_sync_push(data: SyncPushRequest):
    """Durable per-mutation acknowledgements and atomic SQLite writes.

    V1 clients only clear their entire outbox on complete success. For partial
    success processed_count is deliberately 0 to stop old clients from erasing
    unacknowledged commands; v2 clients use the results array instead.
    """
    from web_api.sync_transactions import apply_once, SyncConflict
    results = []
    halted = False
    for item in data.mutations:
        if halted:
            results.append({'id': item.id, 'status': 'deferred', 'reason': 'Önceki işlem başarısız; sıra korundu'})
            continue
        conn = None
        try:
            conn = db.get_conn()
            result = apply_once(conn, item, data.database_id)
        except (ValueError, SyncConflict) as exc:
            result = {"id": item.id, "status": "conflict" if isinstance(exc, SyncConflict) else "rejected",
                      "reason": str(exc)}
        except Exception:
            result = {"id": item.id, "status": "retryable", "reason": "Veritabanı işlemi gerçekleştirilemedi"}
        finally:
            if conn is not None:
                conn.close()
        results.append(result)
        if result['status'] not in ('applied', 'already_applied'):
            halted = True

    ok = all(r['status'] in ('applied', 'already_applied') for r in results)
    applied = sum(r['status'] == 'applied' for r in results)
    return {
        'success': ok,
        'processed_count': applied if ok else 0,   # old-client safety
        'applied_count': applied,
        'acknowledged_count': sum(r['status'] in ('applied', 'already_applied') for r in results),
        'results': results,
        'errors': [f"[{r['id']}] {r.get('reason', r['status'])}" for r in results
                   if r['status'] not in ('applied', 'already_applied')],
        'synced_at': datetime.now().isoformat(),
    }
