
# utils/settings.py
# -*- coding: utf-8 -*-
"""
Ayar depolama (DB tabanlı).
- API: ayar_get(anahtar, varsayilan), ayar_set(anahtar, deger)
- 'ayar' tablosu yoksa oluşturur.
- İsteğe bağlı 'guncel_tarih' sütununu ekleyip damgalar.
- Tipli okuma yardımcıları: ayar_get_int/float/bool
- Teşhis yardımcıları: ayar_clear_prefix, ayar_dump_prefix
"""
from __future__ import annotations
from typing import Any, Optional, List, Tuple, Set
import threading
import builtins as _bi

def _get_conn():
    """
    Projedeki DB bağlantısını ortak yerden al.
    db.get_conn() Row döndürmüyorsa, row_factory ayarlanır.
    """
    try:
        from db import get_conn
        con = get_conn()
    except Exception:
        import sqlite3
        # Fallback: proje köküne küçük bir settings.db (sadece güvenlik ağı)
        con = sqlite3.connect("settings.db")
    try:
        import sqlite3 as _sqlite3
        con.row_factory = getattr(_sqlite3, "Row", None) or con.row_factory
    except Exception:
        pass
    return con

# --- İç yardımcılar ---------------------------------------------------------
def _table_info_cols(con, table: str) -> Set[str]:
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        cols: Set[str] = _bi.set()
        for r in rows or []:
            # sqlite3.Row veya tuple gelebilir
            name = (r[1] if not hasattr(r, "keys") else r["name"])
            cols.add(name)
        return cols
    except Exception:
        return _bi.set()

def _ensure_ayar_table(con) -> None:
    """
    Eski şemayla uyumlu ayar tablosu: (anahtar TEXT PK, deger TEXT)
    """
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ayar (
                anahtar TEXT PRIMARY KEY,
                deger   TEXT
            )
        """)
        con.commit()
    except Exception:
        pass

def _ensure_guncel_tarih_column(con) -> None:
    """
    Mevcut tabloda 'guncel_tarih' kolonu yoksa ekler; mevcut satırları damgalar.
    DEFAULT kullanmadan ekler (eski SQLite sürümleriyle uyum).
    """
    try:
        cols = _table_info_cols(con, "ayar")
        if "guncel_tarih" not in cols:
            con.execute("ALTER TABLE ayar ADD COLUMN guncel_tarih TEXT")
            con.execute(
                "UPDATE ayar SET guncel_tarih = datetime('now','localtime') "
                "WHERE guncel_tarih IS NULL"
            )
            con.commit()
    except Exception:
        # çok eski sürümlerde sessiz düş (işlevsellik bozulmaz)
        pass

# Thread güvenliği
_lock = threading.RLock()

# --- Genel API --------------------------------------------------------------
def ayar_get(anahtar: str, varsayilan: Optional[Any] = None) -> Optional[str]:
    """
    Ayarı string olarak döndürür (DB'ye hep TEXT yazıyoruz).
    Yoksa varsayilan.
    """
    con = _get_conn()
    _ensure_ayar_table(con)
    try:
        row = con.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
        if not row:
            return varsayilan
        return row[0] if not hasattr(row, "keys") else row["deger"]
    except Exception:
        return varsayilan

def ayar_set(anahtar: str, deger: Any) -> None:
    """
    Ayarı TEXT olarak yazar. 'guncel_tarih' varsa günceller, yoksa klasik şemayla çalışır.
    INSERT/UPDATE uyumlu; ikinci denemede 'DELETE+INSERT' ile garanti altına alır.
    """
    con = _get_conn()
    _ensure_ayar_table(con)
    _ensure_guncel_tarih_column(con)
    cols = _table_info_cols(con, "ayar")
    val = "" if deger is None else str(deger)

    with _lock:
        try:
            if "guncel_tarih" in cols:
                cur = con.execute(
                    "UPDATE ayar SET deger=?, guncel_tarih=datetime('now','localtime') "
                    "WHERE anahtar=?",
                    (val, anahtar),
                )
                if getattr(cur, "rowcount", 0) == 0:
                    con.execute(
                        "INSERT INTO ayar (anahtar, deger, guncel_tarih) "
                        "VALUES (?,?,datetime('now','localtime'))",
                        (anahtar, val),
                    )
            else:
                cur = con.execute(
                    "UPDATE ayar SET deger=? WHERE anahtar=?",
                    (val, anahtar),
                )
                if getattr(cur, "rowcount", 0) == 0:
                    con.execute(
                        "INSERT INTO ayar (anahtar, deger) VALUES (?,?)",
                        (anahtar, val),
                    )
            con.commit()
        except Exception:
            try:
                con.execute("DELETE FROM ayar WHERE anahtar=?", (anahtar,))
                if "guncel_tarih" in cols:
                    con.execute(
                        "INSERT INTO ayar (anahtar, deger, guncel_tarih) "
                        "VALUES (?,?,datetime('now','localtime'))",
                        (anahtar, val),
                    )
                else:
                    con.execute(
                        "INSERT INTO ayar (anahtar, deger) VALUES (?,?)",
                        (anahtar, val),
                    )
                con.commit()
            except Exception:
                pass


# --- Tipli okuma yardımcıları ----------------------------------------------
def ayar_get_int(anahtar: str, varsayilan: int = 0) -> int:
    v = ayar_get(anahtar, None)
    try:
        return int(v)
    except Exception:
        return varsayilan

def ayar_get_float(anahtar: str, varsayilan: float = 0.0) -> float:
    v = ayar_get(anahtar, None)
    try:
        return float(v)
    except Exception:
        return varsayilan

def ayar_get_bool(anahtar: str, varsayilan: bool = False) -> bool:
    v = ayar_get(anahtar, None)
    if v is None:
        return varsayilan
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return varsayilan

# --- Teşhis/yardımcı --------------------------------------------------------
def ayar_clear_prefix(prefix: str) -> int:
    """Belirli önekle başlayan anahtarları siler. Dönen: silinen kayıt adedi."""
    con = _get_conn()
    _ensure_ayar_table(con)
    with _lock:
        try:
            cur = con.execute("DELETE FROM ayar WHERE anahtar LIKE ?", (f"{prefix}%",))
            con.commit()
            return getattr(cur, "rowcount", 0) or 0
        except Exception:
            return 0

def ayar_dump_prefix(prefix: str = "") -> List[Tuple[str, str]]:
    """Prefix'e uyan (ya da boşsa tüm) ayarları [(anahtar, deger)] döndürür."""
    con = _get_conn()
    _ensure_ayar_table(con)
    try:
        if prefix:
            rows = con.execute(
                "SELECT anahtar, deger FROM ayar WHERE anahtar LIKE ? ORDER BY anahtar",
                (f"{prefix}%",),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT anahtar, deger FROM ayar ORDER BY anahtar"
            ).fetchall()
        out: List[Tuple[str, str]] = []
        for r in rows or []:
            if hasattr(r, "keys"):
                out.append((r["anahtar"], r["deger"]))
            else:
                out.append((r[0], r[1]))
        return out
    except Exception:
        return []

