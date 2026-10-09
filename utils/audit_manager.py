# -*- coding: utf-8 -*-
import sqlite3
import datetime
import db

def log(action_type: str, category: str, details: str, username: str = "system"):
    """
    Yeni bir işlem kaydı oluşturur.
    action_type: CREATE, UPDATE, DELETE, LOGIN, ERROR...
    category: STUDENT, HOMEWORK, SETTINGS, BACKUP...
    details: 'Ahmet kullanıcısı YKS grubunu sildi' vb.
    username: İşlemi yapan kişi (varsayılan: system)
    """
    try:
        con = db.get_conn()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO audit_log (username, action_type, category, details)
            VALUES (?, ?, ?, ?)
        """, (username, action_type, category, details))
        con.commit()
    except Exception as e:
        print(f"Audit log error: {e}")

def get_logs(limit: int = 200, search: str = "") -> list[dict]:
    """Son kayıtları getirir. Arama opsiyonel."""
    try:
        con = db.get_conn()
        con.row_factory = sqlite3.Row
        
        sql = "SELECT * FROM audit_log"
        params = []
        
        if search:
            sql += " WHERE username LIKE ? OR details LIKE ? OR category LIKE ?"
            s = f"%{search}%"
            params = [s, s, s]
            
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        
        cur = con.execute(sql, tuple(params))
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Audit read error: {e}")
        return []

def clear_logs(days: int = 365):
    """Belli günden eski logları siler (bakım için)."""
    try:
        con = db.get_conn()
        # sqlite 'now', '-365 days'
        sql = f"DELETE FROM audit_log WHERE timestamp < datetime('now', '-{days} days')"
        con.execute(sql)
        con.commit()
    except Exception:
        pass
