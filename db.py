# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox, QApplication

"""
SQLite veritabanı yardımcıları.
- İlk çalıştırmada ders tablolarını oluşturur.
- seed/*.json dosyalarından konuları ilgili ders tablolarına yükler (sadece boşsa).
- Öğrenci, kitap ve ödev (küme/satır) tablolarını yönetir.
- v19 ile uyumlu whatsapp_log şemasını kurar.
"""
import sqlite3, json
from pathlib import Path
from typing import List, Optional

#DB_PATH = Path.home() / ".yks_lgs_manager" / "veritabani.db"
import sys
if getattr(sys, 'frozen', False):
    if hasattr(sys, '_MEIPASS'):
        # --onefile
        SEED_DIR = Path(sys._MEIPASS) / "seed"
    else:
        # --onedir
        exe_path = Path(sys.executable)
        if sys.platform == "darwin" and exe_path.parent.name == "MacOS":
             SEED_DIR = exe_path.parent.parent / "Resources" / "seed"
        else:
             SEED_DIR = exe_path.parent / "seed"
else:
    SEED_DIR = Path(__file__).resolve().parent / "seed"

#s
# --- Platforma uygun ve taşınabilir veritabanı konumu (OTOMATİK + MODLAR) ---
from pathlib import Path
import os, sys, shutil

from datetime import date, timedelta, datetime
# --- Performans analiz motoru (utils/analytics_engine.py) ---
from utils import analytics_engine as ae






APP_DIR_NAME   = "YKS_LGS_HomeworkManager"
DB_FILE_NAME   = "YKS_LGS_HomeworkManager.db"
ENV_DB_PATH    = "YKS_DB_PATH"     # tam yol override
ENV_DATA_DIR   = "YKS_DATA_DIR"    # klasör override (dosya adı otomatik eklenir)
LEGACY_HOME_DB = Path.home() / ".yks_lgs_manager" / "veritabani.db"

def _is_frozen():
    return getattr(sys, "frozen", False)

def _exe_dir():
    return Path(sys.executable).resolve().parent if _is_frozen() else Path(__file__).resolve().parent

def _arg_present(flag: str) -> bool:
    try:
        return any(a.strip().lower() == flag for a in sys.argv[1:])
    except Exception:
        return False

def _portable_mode_flag():
    """Komut satırı '--portable' ise True."""
    return _arg_present("--portable")

def _portable_mode_file():
    """Çalıştığı klasörde portable.mode dosyası var mı?"""
    return (_exe_dir() / "portable.mode").exists()

def _is_windows_removable_drive(path: Path) -> bool:
    """Windows’ta sürücü tipi removable mı? (ctypes ile)"""
    if os.name != "nt":
        return False
    try:
        import ctypes
        DRIVE_REMOVABLE = 2
        root = str(path.drive) if path.drive else str(Path(path.anchor))
        if not root.endswith("\\"):
            root += "\\"
        GetDriveType = ctypes.windll.kernel32.GetDriveTypeW
        t = GetDriveType(root)
        return t == DRIVE_REMOVABLE
    except Exception:
        return False

def _is_unix_removable_mount(path: Path) -> bool:
    """macOS/Linux’ta tipik removable mount yollarını kaba tahmin et."""
    p = path.resolve()
    # macOS: /Volumes/<usb>, Linux: /media/<user>/<usb> veya /run/media/<user>/<usb>
    return any(str(p).startswith(prefix) for prefix in ("/Volumes/", "/media/", "/run/media/"))

def _running_from_removable() -> bool:
    base = _exe_dir()
    if sys.platform.startswith("win"):
        return _is_windows_removable_drive(base)
    else:
        return _is_unix_removable_mount(base)

def _platform_appdata_dir():
    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return base / APP_DIR_NAME
    elif sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_DIR_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        return base / APP_DIR_NAME

def _is_in_program_files(path: Path) -> bool:
    """Yol Program Files veya sistem korumalı dizin altında mı?"""
    if os.name != "nt":
        return False
    try:
        p_str = str(path.resolve()).lower()
        pf = os.environ.get("ProgramFiles", "c:\\program files").lower()
        pf86 = os.environ.get("ProgramFiles(x86)", "c:\\program files (x86)").lower()
        return p_str.startswith(pf) or p_str.startswith(pf86)
    except Exception:
        return False

def _is_dir_writable(path: Path) -> bool:
    """Klasöre yazma yetkisi var mı?"""
    try:
        test_file = path / f".writable_test_{os.getpid()}.tmp"
        with open(test_file, "w") as f:
            f.write("test")
        if test_file.exists():
            os.remove(test_file)
        return True
    except Exception:
        return False

def _portable_data_root():
    """Portable modda kullanılacak kök klasör: exe yanında 'data/'."""
    return _exe_dir() / "data"

def _pick_db_path() -> Path:
    # 1) ENV tam yol (Web App uses this)
    env_full = os.environ.get("YKS_DB_PATH")
    if env_full:
        p = Path(env_full).expanduser().resolve()
        print(f"DEBUG: Found ENV_DB_PATH: {p}")
        return p

    # 2) ENV data dir
    env_dir = os.environ.get(ENV_DATA_DIR)
    if env_dir:
        return (Path(env_dir).expanduser().resolve() / DB_FILE_NAME)

    # 3) Check locally in exe dir (Program Files dışında ve yazılabilir ise)
    # Bu sayede zip'i masaüstünde çalıştıran kişi yanındaki DB'yi kullanır;
    # Program Files içine kurulduğunda ise Windows UAC izin hatası vermemesi için
    # doğrudan AppData/Local konumuna yönlendirilir.
    if not _is_in_program_files(_exe_dir()) and _is_dir_writable(_exe_dir()):
        local_db = (_exe_dir() / DB_FILE_NAME).resolve()
        if local_db.exists():
            return local_db

    # 4) Komut satırı --portable
    if _portable_mode_flag():
        return (_portable_data_root() / DB_FILE_NAME).resolve()

    # 5) portable.mode dosyası
    if _portable_mode_file():
        return (_portable_data_root() / DB_FILE_NAME).resolve()

    # 6) Çalıştığı disk removable ise otomatik portable
    if _running_from_removable():
        return (_portable_data_root() / DB_FILE_NAME).resolve()

    # 7) Varsayılan: platform app data (Original Desktop default)
    target = (_platform_appdata_dir() / DB_FILE_NAME).resolve()
    if not target.exists():
        _find_and_migrate_previous_db(target)
    return target

def _find_and_migrate_previous_db(target: Path) -> bool:
    """Eski sürümlerden kalma veritabanı varsa (VirtualStore veya ~/.yks_lgs_manager),
    kullanıcının mevcut verilerini kaybetmemesi için güvenle yeni AppData konumuna taşır."""
    if target.exists():
        return False

    potential_sources = []
    
    # 1. VirtualStore yolları (Windows'ta Program Files'a yazmaya çalışan eski sürümler için)
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            vs_base = Path(local_app_data) / "VirtualStore"
            for pf_name in ["Program Files", "Program Files (x86)"]:
                for app_folder in ["YKS-LGS Odev Takip", "YKS_LGS_HomeworkManager", "YKS-LGS Odev Takip v2"]:
                    potential_sources.append(vs_base / pf_name / app_folder / DB_FILE_NAME)
                    potential_sources.append(vs_base / pf_name / app_folder / "veritabani.db")

    # 2. Eski ev dizini konumu (~/.yks_lgs_manager/veritabani.db)
    potential_sources.append(LEGACY_HOME_DB)
    potential_sources.append(Path.home() / ".yks_lgs_manager" / DB_FILE_NAME)

    for src in potential_sources:
        try:
            if src.exists() and src.is_file() and src.stat().st_size > 0:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(target))
                return True
        except Exception:
            continue

    return False

def _migrate_legacy_db_if_needed(target: Path):
    try:
        if LEGACY_HOME_DB.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(LEGACY_HOME_DB), str(target))
    except Exception:
        pass

def _ensure_db_dir(db_path: Path):
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(db_path.parent, 0o700)
    except Exception:
        pass

#s haftalık plan için
def son_kume_kaydi(con: sqlite3.Connection, ogrenci_id: int):
    if not ogrenci_id:
        return None
    return con.execute("""
        SELECT * FROM odev_kume
        WHERE ogrenci_id=?
        ORDER BY datetime(verilis_tarihi) DESC, id DESC
        LIMIT 1
    """, (ogrenci_id,)).fetchone()

def kume_satirlari(con: sqlite3.Connection, kume_id: int):
    if not kume_id:
        return []
    rows = con.execute("""
        SELECT ders, kitap, konu
        FROM odev_satir
        WHERE kume_id=?
        ORDER BY id
    """, (kume_id,)).fetchall()
    return [{
        "ders":  (r["ders"]  or "").strip(),
        "kitap": (r["kitap"] or "").strip(),
        "konu":  (r["konu"]  or "").strip(),
        "dk":    0
    } for r in rows]
#f

#s
# ... yukarıda sizin mevcut seçicileriniz ...

DB_PATH = _pick_db_path()
_migrate_legacy_db_if_needed(DB_PATH)
_ensure_db_dir(DB_PATH)

# === OTOMATİK “MEVCUT EN İYİ DB’Yİ BUL VE BENİMSER” KATMANI ===
import time

# Daha önce kullanılmış olabilecek dosya adları/klasörler
CANDIDATE_FILE_NAMES = [
    DB_FILE_NAME,                 # yeni standart adınız
    "veritabani.db",              # eski ad
    "yks_lgs.db",                 # olası ara ad
]

def _candidate_dirs() -> list[Path]:
    """Muhtemel klasörleri sırala (öncelik yüksekten düşüğe)."""
    dirs = []

    # 1) Aktif DB hedef klasörünüz
    dirs.append(DB_PATH.parent)

    # 2) Çalıştırılan exe/py klasörü (Program Files içinde değilse)
    try:
        if not _is_in_program_files(_exe_dir()):
            dirs.append(_exe_dir())
    except Exception: pass

    # 3) Çalışılan dizin (Program Files içinde değilse)
    try:
        if not _is_in_program_files(Path.cwd()):
            dirs.append(Path.cwd())
    except Exception: pass

    # 4) Eski “home gizli” klasör
    try: dirs.append(LEGACY_HOME_DB.parent)
    except Exception: pass

    # 5) Platform standart AppData
    try: dirs.append(_platform_appdata_dir())
    except Exception: pass

    # 6) VirtualStore (Windows Program Files UAC)
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            vs_base = Path(local_app_data) / "VirtualStore"
            for pf_name in ["Program Files", "Program Files (x86)"]:
                for app_folder in ["YKS-LGS Odev Takip", "YKS_LGS_HomeworkManager", "YKS-LGS Odev Takip v2"]:
                    dirs.append(vs_base / pf_name / app_folder)

    # 7) Portable data/
    try: dirs.append(_portable_data_root())
    except Exception: pass

    # Yineleri at
    uniq = []
    seen = set()
    for d in dirs:
        p = d.resolve()
        if p not in seen:
            uniq.append(p); seen.add(p)
    return [d for d in uniq if d and d.exists()]

def _is_sqlite(p: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True) as con:
            con.execute("PRAGMA schema_version").fetchone()
        return True
    except Exception:
        return False

def _table_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        c = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        ).fetchone()
        if not c:
            return 0
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0

def _db_score(p: Path) -> int:
    """Veri doluluğuna göre skor ver (yüksek=iyi)."""
    try:
        con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        try:
            kume = _table_count(con, "odev_kume")
            satir = _table_count(con, "odev_satir")
            ogr   = _table_count(con, "ogrenci")
        finally:
            con.close()
    except Exception:
        return -1

    # Ağırlıklar
    score = 0
    score += min(kume, 100000) * 100    # küme en değerli
    score += min(satir, 100000) * 10
    score += min(ogr,   100000) * 5

    # Dosya tazeliği (son 180 günde bonus)
    try:
        age_days = max(0.0, (time.time() - p.stat().st_mtime) / 86400.0)
        fresh_bonus = max(0, int(1000 - min(1000, age_days * 5)))
        score += fresh_bonus
    except Exception:
        pass

    return score

def _pick_best_existing_db() -> Path | None:
    cands = []
    for d in _candidate_dirs():
        for name in CANDIDATE_FILE_NAMES:
            p = (d / name)
            if p.exists() and p.is_file() and p.stat().st_size > 0 and _is_sqlite(p):
                try:
                    cands.append((p, _db_score(p)))
                except Exception:
                    pass
    if not cands:
        return None
    # En yüksek skorlu aday
    cands.sort(key=lambda t: t[1], reverse=True)
    return cands[0][0]

def _is_target_db_empty_or_missing(t: Path) -> bool:
    if not t.exists() or t.stat().st_size == 0:
        return True
    # “Boş” sayılabilecek: ogrenci/odev_kume/odev_satir toplamı 0
    try:
        con = sqlite3.connect(f"file:{t.as_posix()}?mode=ro", uri=True)
        try:
            total = 0
            for table in ("ogrenci", "odev_kume", "odev_satir"):
                total += _table_count(con, table)
            return total == 0
        finally:
            con.close()
    except Exception:
        # Açılmıyorsa “boş” muamelesi yapıp üzerine yazalım
        return True

def _adopt_best_db_if_needed(target: Path):
    """Hedef yok/boş ise en iyi mevcut DB’yi bul ve hedefe kopyala."""
    if not _is_target_db_empty_or_missing(target):
        return
    best = _pick_best_existing_db()
    if best and best.resolve() != target.resolve():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best, target)
        except Exception:
            # sessiz geç
            pass


# İsteğe bağlı otomatik benimseme (varsayılan KAPALI)
AUTO_ADOPT = os.getenv("YKS_AUTO_ADOPT", "0") == "1"
if AUTO_ADOPT:
    _adopt_best_db_if_needed(DB_PATH)
# === /OTOMATİK BENİMSEME SONU ===


# --- Hızlı teşhis için yardımcılar ---
def _safe_count(con, table: str) -> int:
    try:
        r = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(r[0]) if r else 0
    except Exception:
        return -1

def current_db_info() -> dict:
    """Açık DB hakkında: yol, var mı, boyut ve kritik tablo sayıları."""
    from pathlib import Path
    p = Path(DB_PATH)
    info = {
        "db_path": str(p),
        "exists": p.exists(),
        "size": (p.stat().st_size if p.exists() else 0),
        "module_file": __file__,
        "counts": {},
    }
    try:
        con = get_conn()
        info["counts"] = {
            "ogrenci": _safe_count(con, "ogrenci"),
            "odev_kume": _safe_count(con, "odev_kume"),
            "odev_satir": _safe_count(con, "odev_satir"),
        }
        con.close()
    except Exception:
        pass
    return info
#f
#f

# Ders tablo adları (sqlite tablo isimleri)
# Not: Hem 'lgs_din' hem de 'lgs_dinkulturu' eklenerek ad farkı tolere edilir.
DERS_TABLOLARI = [
    "tyt_matematik", "problemler", "ayt_matematik", "geometri", "fizik", "kimya", "biyoloji",
    "turkce", "paragraf", "tarih", "cografya", "felsefe", "edebiyat",
    "lgs_matematik", "lgs_fen", "lgs_turkce", "lgs_inkilap", "lgs_din", "lgs_dinkulturu",
    "lgs_ingilizce"
]

def _sql_greatest(*args):
    vals = [v for v in args if v is not None]
    if not vals:
        return None
    try:
        return max(vals)
    except Exception:
        return max(map(str, vals))

def _sql_least(*args):
    vals = [v for v in args if v is not None]
    if not vals:
        return None
    try:
        return min(vals)
    except Exception:
        return min(map(str, vals))

def get_conn() -> sqlite3.Connection:
    """
    Veritabanı bağlantısını açar, gerekli SQLite ayarlarını yapar ve
    GREATEST/LEAST gibi eksik fonksiyonları tanımlar.
    """

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=20)
    con.row_factory = sqlite3.Row

    # --- SQLite ayarları ---
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")

    # ============================================================
    #  Performans Paneli için gereken ek fonksiyonlar
    # ============================================================

    # Eğer senin _sql_greatest ve _sql_least fonksiyonların zaten varsa
    # onları kullanmaya devam ediyoruz.
    # Ancak GREATEST bazen None (boş) değerleri görünce hata verebiliyor,
    # bu yüzden biraz daha güvenli hale getiriyoruz.
    def _safe_greatest(*args):
        vals = [a for a in args if a is not None]
        if not vals:
            return None
        try:
            return max(vals)
        except Exception:
            try:
                return max(float(v) for v in vals)
            except Exception:
                return None

    def _safe_least(*args):
        vals = [a for a in args if a is not None]
        if not vals:
            return None
        try:
            return min(vals)
        except Exception:
            try:
                return min(float(v) for v in vals)
            except Exception:
                return None

    # --- Eksik fonksiyonları (MySQL/Postgre benzeri) ekle ---
    # Eğer zaten _sql_greatest ve _sql_least tanımlıysa onları,
    # yoksa bu güvenli sürümleri kaydedecek:
    try:
        con.create_function("GREATEST", -1, _sql_greatest)
    except NameError:
        con.create_function("GREATEST", -1, _safe_greatest)

    try:
        con.create_function("LEAST", -1, _sql_least)
    except NameError:
        con.create_function("LEAST", -1, _safe_least)

    return con

def _init_deneme_tables(cur: sqlite3.Cursor):
    """Deneme sınavı ve sonuçları için tabloları oluşturur."""
    # 1. Deneme Sınavları
    cur.execute("""
    CREATE TABLE IF NOT EXISTS denemeler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih TEXT,          -- YYYY-MM-DD
        deneme_adi TEXT,     -- Örn: Özdebir 1
        yayin_adi TEXT,      -- Örn: Özdebir
        tur TEXT,            -- TYT, AYT, LGS, KDS
        aciklama TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # 2. Deneme Sonuçları (Öğrenci bazlı)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS deneme_sonuclari (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deneme_id INTEGER,
        ogrenci_id INTEGER,
        ders_adi TEXT,       -- Matematik, Türkçe, Fizik vs.
        dogru INTEGER DEFAULT 0,
        yanlis INTEGER DEFAULT 0,
        bos INTEGER DEFAULT 0,
        net REAL DEFAULT 0.0,
        FOREIGN KEY(deneme_id) REFERENCES denemeler(id) ON DELETE CASCADE,
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")
    
    # 3. İndeksler (Hız için)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sonuc_deneme ON deneme_sonuclari(deneme_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sonuc_ogrenci ON deneme_sonuclari(ogrenci_id)")

def _init_coaching_tables(cur: sqlite3.Cursor):
    """Koçluk ve Soru Hedef Takibi Modülü"""
    # 1. Haftalık Koçluk Planı (Her öğrenci için her hafta 1 tane)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS koc_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        baslangic_tarihi TEXT,  -- YYYY-MM-DD (Haftanın pazartesisi)
        bitis_tarihi TEXT,      -- YYYY-MM-DD (Haftanın pazarı)
        notlar TEXT,            -- Koçun o hafta için notu
        aktif INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")

    # 2. Ders Hedefleri (Örn: Matematik - 150 Soru)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS koc_hedef (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER,
        ders_adi TEXT,
        hedef_soru INTEGER DEFAULT 0,
        cozulen_soru INTEGER DEFAULT 0,
        hedef_saat REAL DEFAULT 0,      -- Yeni: Hedeflenen Saat
        calisilan_saat REAL DEFAULT 0,  -- Yeni: Çalışılan Saat
        durum TEXT DEFAULT 'devam', 
        FOREIGN KEY(plan_id) REFERENCES koc_plan(id) ON DELETE CASCADE
    )""")
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_plan_ogr ON koc_plan(ogrenci_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_hedef_plan ON koc_hedef(plan_id)")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS koc_program (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER,
        gun TEXT,       -- Pazartesi, Salı...
        saat TEXT,      -- 09:00 - 10:00 vb
        icerik TEXT,
        renk TEXT,      -- Hücre rengi (hex)
        FOREIGN KEY(plan_id) REFERENCES koc_plan(id) ON DELETE CASCADE
    )""")
    
    # Migrasyon: Renk kolonu yoksa ekle
    try:
        cur.execute("ALTER TABLE koc_program ADD COLUMN renk TEXT")
    except Exception:
        pass # Zaten varsa hata verir, geç
    cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_prog_plan ON koc_program(plan_id)")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS koc_konu_takip (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        ders_adi TEXT,
        konu_adi TEXT,
        durum INTEGER DEFAULT 0, -- 0:Başlanmadı, 1:Çalışılıyor, 2:Bitti
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_konu_ogr ON koc_konu_takip(ogrenci_id)")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS koc_kitaplar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        ders_adi TEXT,
        kitap_adi TEXT,
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_koc_kitaplar_ogr ON koc_kitaplar(ogrenci_id)")

    try:
        cur.execute("ALTER TABLE odev ADD COLUMN zorluk TEXT DEFAULT 'Orta'") # Kolay, Orta, Zor
    except Exception:
        pass

    # Mevcut veritabanları için sütun ekleme (Migration)
    try:
        cur.execute("ALTER TABLE koc_hedef ADD COLUMN hedef_saat REAL DEFAULT 0")
        cur.execute("ALTER TABLE koc_hedef ADD COLUMN calisilan_saat REAL DEFAULT 0")
    except:
        pass # Zaten varsa hata verir, geç

    try:
        cur.execute("ALTER TABLE koc_konu_takip ADD COLUMN kitap_id INTEGER DEFAULT 0")
    except:
        pass

    # Koçluk Konu Hakimiyeti Analitik Kolonları (Migration)
    for col_def in [
        ("hakimiyet_puani", "INTEGER DEFAULT 0"),
        ("cozulen_soru", "INTEGER DEFAULT 0"),
        ("hedef_soru", "INTEGER DEFAULT 0"),
        ("tekrar_durumu", "TEXT DEFAULT ''"),
        ("son_tekrar_tarihi", "TEXT DEFAULT ''"),
        ("koc_notu", "TEXT DEFAULT ''"),
    ]:
        try:
            cur.execute(f"ALTER TABLE koc_konu_takip ADD COLUMN {col_def[0]} {col_def[1]}")
        except Exception:
            pass


def _init_extra_tables(cur: sqlite3.Cursor):
    """Tüm ek modül tablolarını (deneme, koçluk, anket, randevu vb.) oluşturur ve garantiler."""
    _init_deneme_tables(cur)
    _init_coaching_tables(cur)
    
    # Hızlı/Klasik deneme tabloları (deneme_sonuclari.py ve rapor_deneme.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS deneme (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        tur TEXT,
        ad TEXT,
        tarih TEXT,
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS deneme_sonuc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deneme_id INTEGER,
        ders TEXT,
        dogru INTEGER DEFAULT 0,
        yanlis INTEGER DEFAULT 0,
        net REAL DEFAULT 0.0,
        FOREIGN KEY(deneme_id) REFERENCES deneme(id) ON DELETE CASCADE
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_deneme_sonuc_did ON deneme_sonuc(deneme_id)")

    # Randevu tablosu (randevu_takvimi.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS randevu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        kontrol_tarihi TEXT,
        randevu_tarihi TEXT,
        tarih TEXT,
        ders TEXT,
        konu TEXT,
        aciklama TEXT,
        durum TEXT DEFAULT 'bekliyor',
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_randevu_ogr ON randevu(ogrenci_id)")

    # Konu düzenleme tabloları (topic_editor.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ogrenci_konu_duzen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER NOT NULL,
        ders TEXT NOT NULL,
        konu TEXT NOT NULL,
        ort_soru INTEGER,
        ort_sure INTEGER,
        UNIQUE(ogrenci_id, ders, konu)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS grup_konu_duzen (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ana_grup TEXT,
        alt_grup TEXT,
        ders TEXT NOT NULL,
        konu TEXT NOT NULL,
        ort_soru INTEGER,
        ort_sure INTEGER,
        UNIQUE(ana_grup, alt_grup, ders, konu)
    )""")

    # Kitap özellikleri (book_dialog.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kitap_ozellik (
        ders TEXT NOT NULL,
        kitap_ad TEXT NOT NULL,
        key TEXT NOT NULL,
        val TEXT,
        PRIMARY KEY(ders, kitap_ad, key)
    )""")

    # Çoklu Ödev Takip (topic_map_dialog.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS odev_takip (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        ders_adi TEXT,
        konu_adi TEXT,
        kitap_adi TEXT,
        baslangic_tarihi TEXT,
        kontrol_tarihi TEXT,
        durum TEXT,
        created_at DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_odev_takip_ogr ON odev_takip(ogrenci_id)")

    # Öğrenci Anket Sistemi (survey_manager.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ogrenci_anket (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        anket_kodu TEXT,
        cevaplar TEXT,
        tarih TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ogrenci_id) REFERENCES ogrenci(id) ON DELETE CASCADE
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ogrenci_anket_ogr ON ogrenci_anket(ogrenci_id)")

    # Akıllı Asistan ve Risk Analizi (smart_assistant_dialog.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sistem_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anahtar TEXT NOT NULL,
        tarih TEXT NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        student_name TEXT,
        phone TEXT,
        stype TEXT,
        message TEXT,
        send_at TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS risk_snapshot (
        snapshot_date TEXT NOT NULL,
        student_id INTEGER NOT NULL,
        risk_score INTEGER NOT NULL,
        overdue_count INTEGER DEFAULT 0,
        silent_days INTEGER DEFAULT 0,
        completed_last_week INTEGER DEFAULT 0,
        birthday_today INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (snapshot_date, student_id)
    )""")

    # Rapor Ayarları (report_settings.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_report_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # Web Önbellekleri (web_service.py)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS web_note_cache (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS exam_date_cache (
        key TEXT PRIMARY KEY,
        date_val TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")




def init_db():
    """Tüm tabloları oluşturur/yükseltir ve seed verileri yükler."""
    con = get_conn()
    cur = con.cursor()

    # --- Öğrenci
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ogrenci(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT NOT NULL,
        soyad TEXT NOT NULL,
        ogr_no TEXT,
        ana_grup TEXT,    -- YKS / LGS / Ara Sınıf
        alt_grup TEXT,    -- 12-say, 11-ea, 8.sınıf vb.
        veli_ad TEXT,
        veli_yakinlik TEXT,
        veli_tel1 TEXT,
        veli_tel2 TEXT,
        ogr_tel TEXT,
        ogr_mail TEXT,
        veli_mail TEXT,
        dogum_tarihi TEXT,
        kisisel_bilgiler TEXT,
        aktif INTEGER DEFAULT 1,
        kocluk_gunu TEXT,
        kocluk_saati TEXT,
        hedef_bolum TEXT,
        hedef_tyt REAL,
        hedef_ayt REAL,
        hedef_lgs REAL
    )""")

    # --- Kitap havuzu
    cur.execute("""
    CREATE TABLE IF NOT EXISTS kitap(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ders TEXT NOT NULL,
        ad TEXT NOT NULL,
        UNIQUE(ders, ad)
    )""")

    # --- Öğrenciye tanımlı kitaplar
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ogrenci_kitap(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
        ders TEXT NOT NULL,
        kitap_ad TEXT NOT NULL,
        UNIQUE(ogrenci_id, ders, kitap_ad)
    )""")

    # --- Ödev kümesi
    cur.execute("""
    CREATE TABLE IF NOT EXISTS odev_kume(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
        verilis_tarihi TEXT NOT NULL,
        bitis_tarihi TEXT,
        aciklama TEXT
    )""")

    # --- Genel ayarlar
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ayar(
        anahtar TEXT PRIMARY KEY,
        deger TEXT
    )""")

    # --- Ödev (satırları tek tabloda tutan eski yaklaşım; koruyoruz)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS odev(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kume_id INTEGER NOT NULL REFERENCES odev_kume(id) ON DELETE CASCADE,
        ogrenci_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
        ders TEXT NOT NULL,
        konu_id INTEGER NOT NULL,
        konu_ad TEXT NOT NULL,
        kitap_ad TEXT NOT NULL,
        saat_dk INTEGER DEFAULT 0,
        aciklama TEXT,
        durum TEXT DEFAULT 'devam',
        UNIQUE(kume_id, ders, konu_id, kitap_ad)
    )""")

    # --- Rapor/akış ile uyumlu 'odev_satir' (v19 sürümlerinde kullanılıyor)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS odev_satir(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER REFERENCES ogrenci(id) ON DELETE CASCADE,
        kume_id INTEGER REFERENCES odev_kume(id) ON DELETE CASCADE,
        ders TEXT,
        kitap TEXT,
        konu TEXT,
        tarih TEXT,              -- veriliş/kayıt tarihi için
        durum TEXT DEFAULT 'devam',  -- 'devam' / 'tamam'
        gerekce TEXT,
        koc TEXT
    )""")
    # Güvenli ALTER'lar (idempotent)
    for sql in [
        "ALTER TABLE odev_satir ADD COLUMN tarih TEXT",
        "ALTER TABLE odev_satir ADD COLUMN durum TEXT DEFAULT 'devam'",
        "ALTER TABLE odev_satir ADD COLUMN gerekce TEXT",
        "ALTER TABLE odev_satir ADD COLUMN koc TEXT",
    ]:
        try:
            cur.execute(sql)
        except Exception:
            pass

    # --- Ders konu tabloları + zorluk kolonu
    for ders in DERS_TABLOLARI:
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {ders}(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konu TEXT NOT NULL,
            ort_soru INTEGER,
            ort_sure INTEGER,
            aciklama TEXT
        )""")
        try:
            cur.execute(f"ALTER TABLE {ders} ADD COLUMN zorluk INTEGER")
        except Exception:
            pass

    # --- Konu istatistikleri
    cur.execute("""
    CREATE TABLE IF NOT EXISTS konu_istatistik(
        ders TEXT,
        konu TEXT,
        tamam INTEGER DEFAULT 0,
        yapilmadi INTEGER DEFAULT 0,
        PRIMARY KEY(ders, konu)
    )""")

    # --- v19: WhatsApp log şeması (yeni)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zaman TEXT DEFAULT (datetime('now')),    -- otomatik tarih
        ogrenci_id INTEGER REFERENCES ogrenci(id) ON DELETE SET NULL,
        numara TEXT,                             -- tek numara (örn. +905xxxxxxxxx)
        mesaj_onizleme TEXT,                     -- ilk 200 karakteri saklanır
        durum TEXT CHECK(durum IN ('OK','FAIL')) DEFAULT 'OK',
        hata TEXT,                               -- 'NO_CHAT' / 'INVALID_NUMBER' / 'gonderim' vb.
        ekran_goruntusu TEXT,                    -- screenshot dosya yolu
        gonderilen INTEGER DEFAULT 0,            -- toplu istatistik desteği
        basarisiz INTEGER DEFAULT 0              -- toplu istatistik desteği
    )
    """)

    # 💡 Tam bu satırın hemen altına ekle:
    migrate_whatsapp_log(con)
    migrate_ogrenci(con)
    migrate_kitap(con)
    migrate_odev(con)
    migrate_odev_aktar_log(con)
    migrate_ogrenci_kitap(con)
    migrate_ogrenci_performans(con)
    migrate_perf_derinlik(con)
    migrate_koc_kitaplar(con)
    migrate_ogrenci_hedef(con)

    # --- v20: Kullanıcı Yetkilendirme (feature id: 13)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    # Varsayılan admin (Şifre: admin -> SHA256)
    # sha256("admin") = 8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918
    chk_admin = cur.execute("SELECT 1 FROM users WHERE username='admin'").fetchone()
    if not chk_admin:
        import hashlib
        h = hashlib.sha256("admin".encode()).hexdigest()
        cur.execute("INSERT INTO users(username, password_hash, role) VALUES(?, ?, ?)", ('admin', h, 'admin'))

    # --- v21: Audit Log (İşlem Geçmişi)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now', 'localtime')),
        username TEXT,
        action_type TEXT,   -- 'CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'EXPORT'
        category TEXT,      -- 'STUDENT', 'HOMEWORK', 'SETTINGS', 'BACKUP'
        details TEXT        -- Kim neyi değiştirdi (JSON veya metin)
    )""")

    # --- Tüm Ek Modül Tabloları (Koçluk, Deneme, Müfredat, Randevu, Anket vb.) ---
    _init_extra_tables(cur)
    init_curriculum(con)
    init_group_lessons(con)

    con.commit()
    _seed_if_needed(con)
    con.commit()
    return con
# ====================== BACKUP / YEDEKLEME ======================

import os, shutil, gzip, io, datetime as dt
from typing import Dict, Any

def _data_root() -> Path:
    """DB_PATH zaten sizde platforma göre belirleniyor. Kök klasör = DB_PATH.parent"""
    try:
        return DB_PATH.parent
    except Exception:
        return Path.home() / ".yks_lgs_manager"

def backup_default_dir() -> Path:
    d = _data_root() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d

def backup_policy_defaults() -> Dict[str, Any]:
    """
    Varsayılan politika:
    - günlük 03:00
    - tutulma: 30 gün, max 50 kopya
    - sıkıştır: evet (.db.gz)
    """
    return {
        "backup_enabled": "1",          # "0" kapalı, "1" açık
        "backup_frequency": "daily",    # "daily" | "weekly"
        "backup_time": "03:00",         # HH:MM (24s)
        "backup_weekday": "1",          # 1=Monday ... 7=Sunday (haftalıkta)
        "backup_keep_days": "30",
        "backup_keep_copies": "50",
        "backup_dir": str(backup_default_dir()),
        "backup_compress": "1",         # 1 => .gz
    }

def get_backup_policy(con: sqlite3.Connection) -> Dict[str, Any]:
    pol = backup_policy_defaults()
    try:
        rows = con.execute("SELECT anahtar, deger FROM ayar WHERE anahtar LIKE 'backup_%'").fetchall()
        for r in rows:
            pol[str(r["anahtar"])] = str(r["deger"])
    except Exception:
        pass
    # doğrulama/normalize
    pol["backup_enabled"] = "1" if pol.get("backup_enabled", "1") not in ("0", "false", "False", "FALSE") else "0"
    pol["backup_frequency"] = "weekly" if str(pol.get("backup_frequency","daily")).lower()=="weekly" else "daily"
    pol["backup_time"] = pol.get("backup_time","03:00")
    pol["backup_weekday"] = str(pol.get("backup_weekday","1"))
    pol["backup_keep_days"] = str(pol.get("backup_keep_days","30"))
    pol["backup_keep_copies"] = str(pol.get("backup_keep_copies","50"))
    pol["backup_dir"] = pol.get("backup_dir") or str(backup_default_dir())
    pol["backup_compress"] = "1" if pol.get("backup_compress","1") in ("1","true","True","TRUE") else "0"
    # klasör garanti
    try:
        Path(pol["backup_dir"]).mkdir(parents=True, exist_ok=True)
    except Exception:
        pol["backup_dir"] = str(backup_default_dir())
    return pol

def set_backup_policy(con: sqlite3.Connection, **kwargs):
    """
    İsterseniz GUI’den güncellemek için kullanın:
    set_backup_policy(con, backup_enabled="0", backup_frequency="weekly", backup_weekday="7", ...)
    """
    cur = con.cursor()
    for k, v in kwargs.items():
        if not str(k).startswith("backup_"):
            continue
        try:
            cur.execute("INSERT INTO ayar(anahtar,deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                        (str(k), str(v)))
        except Exception:
            pass
    con.commit()

def _sqlite_online_backup(src_path: Path) -> bytes:
    """
    SQLite online backup ile .db içeriğini RAM'e alır (bytes döner).
    Kilitlenme riskini azaltır. Sıkıştırma ayırdık.
    """
    mem = io.BytesIO()
    # Kaynak dosya salt-okunur bağlantı aç, hedef = bellek DB
    src = sqlite3.connect(f"file:{src_path.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(":memory:")
    try:
        src.backup(dst)
        dst.commit()
        # Bellek DB'yi dosyaya dökmek için .iterdump (en uyumlu yol)
        dump = "\n".join(dst.iterdump()).encode("utf-8")
        mem.write(dump)
        return mem.getvalue()
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def backup_now(dest_dir: Path|None=None, compress: bool=True) -> Path:
    """
    ŞİMDİ YEDEKLE: DB’yi tarih damgalı dosyaya kaydet, Path döndürür.
    Varsayılan: <data>/backups/veritabani_YYYYMMDD_HHMMSS.db[.gz]
    """
    src = Path(DB_PATH)
    dest_dir = Path(dest_dir) if dest_dir else backup_default_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{src.stem}_{ts}.db"
    out = dest_dir / (base + (".gz" if compress else ""))

    # 1) Online backup ile bir "sql dump" bytes üret
    data = _sqlite_online_backup(src)

    # 2) Yaz
    if compress:
        with gzip.open(out, "wb") as f:
            f.write(data)
    else:
        with open(out, "wb") as f:
            f.write(data)

    return out

def cleanup_backups(dest_dir: Path|None=None, keep_days: int=30, keep_copies: int=50):
    """
    Yedek klasörünü limitlere göre temizle.
    - *Yaşa* göre: keep_days üstü silinir
    - *Kopya* sayısına göre: en yeni keep_copies tutulur, diğerleri silinir
    """
    d = Path(dest_dir) if dest_dir else backup_default_dir()
    if not d.exists():
        return
    files = sorted([p for p in d.glob("*.db*") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)

    # 1) kopya sınırı
    extra = files[keep_copies:]
    # 2) yaş sınırı
    cutoff_t = (dt.datetime.now() - dt.timedelta(days=max(0, keep_days))).timestamp()
    old = [p for p in files if p.stat().st_mtime < cutoff_t]

    to_delete = set(extra) | set(old)
    for p in to_delete:
        try: p.unlink()
        except Exception: pass

def backup_run_by_policy(con: sqlite3.Connection|None=None) -> Path|None:
    """
    Politikaya göre bir yedek çalıştır ve temizlik yap. Yol döner (veya None).
    """
    if con is None:
        con = get_conn()
    pol = get_backup_policy(con)
    if pol.get("backup_enabled") != "1":
        return None
    out = backup_now(dest_dir=Path(pol["backup_dir"]), compress=(pol.get("backup_compress")=="1"))
    try:
        cleanup_backups(dest_dir=Path(pol["backup_dir"]),
                        keep_days=int(pol.get("backup_keep_days","30") or 30),
                        keep_copies=int(pol.get("backup_keep_copies","50") or 50))
    except Exception:
        pass
    return out

def _add_column_if_missing(cur: sqlite3.Cursor, table: str, coldef: str):
    """Eksikse tabloya yeni sütun ekler (örnek: coldef='aciklama TEXT')."""
    try:
        colname = coldef.split()[0]
        info = cur.execute(f"PRAGMA table_info({table})").fetchall()
        mevcut = {(r[1] if isinstance(r, (tuple, list)) else r["name"]) for r in info}
        if colname not in mevcut:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
    except Exception:
        pass


def migrate_whatsapp_log(con: sqlite3.Connection):
    """whatsapp_log'u farklı sürümlerle uyumlu hale getirir (idempotent)."""
    cur = con.cursor()

    # 1) Eksik kolonları ekle (eski/yeni sürümlerle uyum)
    _add_column_if_missing(cur, "whatsapp_log", "ts TEXT")
    _add_column_if_missing(cur, "whatsapp_log", "numaralar TEXT")
    _add_column_if_missing(cur, "whatsapp_log", "mesaj TEXT")
    _add_column_if_missing(cur, "whatsapp_log", "ogrenci_ad TEXT")
    _add_column_if_missing(cur, "whatsapp_log", "ogrenci_soyad TEXT")
    _add_column_if_missing(cur, "whatsapp_log", "ogrenci_adsoyad TEXT")

    # 🔧 EKSİK OLANLAR: Windows'taki hatayı kesen iki kolon
    _add_column_if_missing(cur, "whatsapp_log", "gonderilen INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "whatsapp_log", "basarisiz INTEGER DEFAULT 0")

    # 2) Faydalı indexler
    try: cur.execute("CREATE INDEX IF NOT EXISTS idx_wp_ogr ON whatsapp_log(ogrenci_id)")
    except Exception: pass
    try: cur.execute("CREATE INDEX IF NOT EXISTS idx_wp_zaman ON whatsapp_log(zaman)")
    except Exception: pass
    try: cur.execute("CREATE INDEX IF NOT EXISTS idx_wp_ts ON whatsapp_log(ts)")
    except Exception: pass

    con.commit()

    # 3) Hafif backfill
    try:
        # mesaj_onizleme boşsa mesajdan doldur
        cur.execute("""
            UPDATE whatsapp_log
               SET mesaj_onizleme = substr(COALESCE(mesaj,''), 1, 200)
             WHERE (mesaj_onizleme IS NULL OR mesaj_onizleme='')
               AND (mesaj IS NOT NULL AND mesaj!='')
        """)
    except Exception: pass

    try:
        # ogrenci_adsoyad boşsa ogrenci tablosundan doldur
        cur.execute("""
            UPDATE whatsapp_log
               SET ogrenci_ad = (SELECT ad FROM ogrenci o WHERE o.id = whatsapp_log.ogrenci_id),
                   ogrenci_soyad = (SELECT soyad FROM ogrenci o WHERE o.id = whatsapp_log.ogrenci_id)
             WHERE (ogrenci_id IS NOT NULL)
               AND ( (ogrenci_ad IS NULL OR ogrenci_ad='') OR (ogrenci_soyad IS NULL OR ogrenci_soyad='') )
        """)
        cur.execute("""
            UPDATE whatsapp_log
               SET ogrenci_adsoyad = TRIM(COALESCE(ogrenci_ad,'') || ' ' || COALESCE(ogrenci_soyad,''))
             WHERE (ogrenci_adsoyad IS NULL OR ogrenci_adsoyad='')
               AND (COALESCE(ogrenci_ad,'')!='' OR COALESCE(ogrenci_soyad,'')!='')
        """)
    except Exception: pass

    # 4) Yeni kolonların geçmiş kayıtları için hızlı “geriye dönük” doldurma
    try:
        cur.execute("""
            UPDATE whatsapp_log
               SET gonderilen = CASE
                                  WHEN UPPER(COALESCE(durum,''))='OK' THEN 1
                                  ELSE COALESCE(gonderilen,0)
                                END,
                   basarisiz = CASE
                                  WHEN UPPER(COALESCE(durum,''))='OK' THEN COALESCE(basarisiz,0)
                                  ELSE CASE WHEN COALESCE(basarisiz,0)>0 THEN basarisiz ELSE 1 END
                               END
             WHERE COALESCE(gonderilen,NULL) IS NULL
                OR COALESCE(basarisiz,NULL) IS NULL
        """)
    except Exception: pass

    # 5) Son bir temizlik
    try:
        cur.execute("UPDATE whatsapp_log SET ogrenci_adsoyad = '' WHERE ogrenci_adsoyad IS NULL")
    except Exception: pass

    con.commit()
# === EKLENENLER: diğer tabloların migrasyonları ===

def migrate_ogrenci(con):
    cur = con.cursor()
    _add_column_if_missing(cur, "ogrenci", "ogr_no TEXT")
    _add_column_if_missing(cur, "ogrenci", "ana_grup TEXT")
    _add_column_if_missing(cur, "ogrenci", "alt_grup TEXT")
    _add_column_if_missing(cur, "ogrenci", "veli_ad TEXT")
    _add_column_if_missing(cur, "ogrenci", "veli_yakinlik TEXT")
    _add_column_if_missing(cur, "ogrenci", "veli_tel1 TEXT")
    _add_column_if_missing(cur, "ogrenci", "veli_tel2 TEXT")
    _add_column_if_missing(cur, "ogrenci", "ogr_tel TEXT")
    _add_column_if_missing(cur, "ogrenci", "ogr_mail TEXT")
    _add_column_if_missing(cur, "ogrenci", "veli_mail TEXT")
    _add_column_if_missing(cur, "ogrenci", "dogum_tarihi TEXT")
    _add_column_if_missing(cur, "ogrenci", "kisisel_bilgiler TEXT")
    _add_column_if_missing(cur, "ogrenci", "aktif INTEGER DEFAULT 1")
    _add_column_if_missing(cur, "ogrenci", "kocluk_gunu TEXT")
    _add_column_if_missing(cur, "ogrenci", "kocluk_saati TEXT")
    _add_column_if_missing(cur, "ogrenci", "hedef_bolum TEXT")
    _add_column_if_missing(cur, "ogrenci", "hedef_tyt REAL")
    _add_column_if_missing(cur, "ogrenci", "hedef_ayt REAL")
    _add_column_if_missing(cur, "ogrenci", "hedef_lgs REAL")
    con.commit()


def migrate_kitap(con):
    cur = con.cursor()
    _add_column_if_missing(cur, "kitap", "ders TEXT")
    _add_column_if_missing(cur, "kitap", "ad TEXT")
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_kitap_ders_ad ON kitap(ders, ad)")
    except Exception:
        pass
    con.commit()



def migrate_odev(con):
    cur = con.cursor()

    # =====================================================
    # 🟩 1️⃣ ODEV_KUME: küme seviyesinde genel bilgiler
    # =====================================================
    _add_column_if_missing(cur, "odev_kume", "bitis_tarihi TEXT")
    _add_column_if_missing(cur, "odev_kume", "aciklama TEXT")
    _add_column_if_missing(cur, "odev_kume", "olusturma_tarihi TEXT")
    _add_column_if_missing(cur, "odev_kume", "hedef_bitis_tarihi TEXT")
    _add_column_if_missing(cur, "odev_kume", "tamamlanma_orani REAL DEFAULT 0")
    _add_column_if_missing(cur, "odev_kume", "kategori TEXT")
    _add_column_if_missing(cur, "odev_kume", "olusturan TEXT")

    # =====================================================
    # 🟩 2️⃣ ODEV: ödevin kendisi (genel başlık)
    # =====================================================
    _add_column_if_missing(cur, "odev", "saat_dk INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "odev", "aciklama TEXT")
    _add_column_if_missing(cur, "odev", "durum TEXT DEFAULT 'devam'")
    _add_column_if_missing(cur, "odev", "verilis_tarihi TEXT")
    _add_column_if_missing(cur, "odev", "tamamlanma_tarihi TEXT")
    _add_column_if_missing(cur, "odev", "oncelik INTEGER DEFAULT 3")
    _add_column_if_missing(cur, "odev", "kategori TEXT")
    _add_column_if_missing(cur, "odev", "etiketler TEXT")
    _add_column_if_missing(cur, "odev", "puan_degeri REAL DEFAULT 0")
    _add_column_if_missing(cur, "odev", "revizyon_sayisi INTEGER DEFAULT 0")

    # Aktarım ve silme işlemleri için alanlar
    _add_column_if_missing(cur, "odev", "aktarildi INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "odev", "aktarim_tarihi TEXT")
    _add_column_if_missing(cur, "odev", "aktarim_hedef_kume_id INTEGER")
    _add_column_if_missing(cur, "odev", "silindi INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "odev", "silinme_tarihi TEXT")
    _add_column_if_missing(cur, "odev", "silinme_nedeni TEXT")
    _add_column_if_missing(cur, "odev", "durum_degisti_tarihi TEXT")

    # =====================================================
    # 🟩 3️⃣ ODEV_SATIR: ödevin alt maddeleri
    # =====================================================
    _add_column_if_missing(cur, "odev_satir", "tarih TEXT")
    _add_column_if_missing(cur, "odev_satir", "durum TEXT DEFAULT 'devam'")
    _add_column_if_missing(cur, "odev_satir", "gerekce TEXT")
    _add_column_if_missing(cur, "odev_satir", "koc TEXT")

    # Öğrenci ilerleme / AI analizleri için
    _add_column_if_missing(cur, "odev_satir", "odev_id INTEGER")
    # Web ve masaüstü ödevlerinin bağlantısı; mevcut NULL kayıtlar korunur.
    cur.execute("CREATE INDEX IF NOT EXISTS idx_odev_satir_link ON odev_satir(odev_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_odev_satir_ogrenci ON odev_satir(ogrenci_id)")
    _add_column_if_missing(cur, "odev_satir", "tamamlanma_tarihi TEXT")
    _add_column_if_missing(cur, "odev_satir", "sure_dk INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "odev_satir", "puan REAL DEFAULT 0")
    _add_column_if_missing(cur, "odev_satir", "zorluk INTEGER DEFAULT 3")
    _add_column_if_missing(cur, "odev_satir", "geri_bildirim TEXT")
    _add_column_if_missing(cur, "odev_satir", "kontrol_eden TEXT")
    _add_column_if_missing(cur, "odev_satir", "otomatik_tespit INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "odev_satir", "yineleme_no INTEGER DEFAULT 0")

    # Aktarım ve soft delete alanları
    _add_column_if_missing(cur, "odev_satir", "aktarildi INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "odev_satir", "aktarim_tarihi TEXT")
    _add_column_if_missing(cur, "odev_satir", "silindi INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "odev_satir", "silinme_tarihi TEXT")
    _add_column_if_missing(cur, "odev_satir", "silinme_nedeni TEXT")

    con.commit()
def migrate_odev_log(con):
    """İşlem geçmişi (audit log) tablosu - yalnızca bir defa oluşturulur"""
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odev_islem_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            odev_id INTEGER,
            kume_id INTEGER,
            ogrenci_id INTEGER,
            islem TEXT,
            eski_durum TEXT,
            yeni_durum TEXT,
            aciklama TEXT,
            ekstra TEXT,
            ts TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    con.commit()
#ödevleri silmeden aktar için
def migrate_odev_aktar_log(con: sqlite3.Connection):
    """
    Ödev aktarım geçmişi için log tablosu.
    Eski sürümlerde olmayabilir; bu yüzden idempotent kuruyoruz.
    """
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS odev_aktar_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id        INTEGER,   -- raporda ogr_id ile filtre
            kaynak_kume_id    INTEGER,   -- nereden aktarıldı
            hedef_kume_id     INTEGER,   -- nereye aktarıldı
            kaynak_tarih      TEXT,
            hedef_tarih       TEXT,
            islem             TEXT,      -- 'AKTAR', 'KOPYALA' vb.
            aciklama          TEXT,
            ts                TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    # Kullanışlı index (raporda ogrenci_id ile arıyorsun muhtemelen)
    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_odev_aktar_ogr
            ON odev_aktar_log(ogrenci_id)
        """)
    except Exception:
        pass

    con.commit()



def migrate_ogrenci_kitap(con):
    cur = con.cursor()
    _add_column_if_missing(cur, "ogrenci_kitap", "ders TEXT")
    _add_column_if_missing(cur, "ogrenci_kitap", "kitap_ad TEXT")
    try:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ogr_kitap ON ogrenci_kitap(ogrenci_id, ders, kitap_ad)")
    except Exception:
        pass
    con.commit()

def migrate_koc_kitaplar(con):
    """
    Koçluk modülü kitap takibi için şema.
    """
    cur = con.cursor()
    # 1. koc_kitaplar tablosu
    cur.execute("""
    CREATE TABLE IF NOT EXISTS koc_kitaplar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ogrenci_id INTEGER,
        ders_adi TEXT,
        kitap_adi TEXT
    )""")
    
    # 2. koc_konu_takip tablosuna kitap_id sütunu ekle
    _add_column_if_missing(cur, "koc_konu_takip", "kitap_id INTEGER DEFAULT 0")
    
    con.commit()

#s--şema ekleri
def migrate_perf_derinlik(con: sqlite3.Connection):
    cur = con.cursor()

    # 1) odev_satir: tamamlama zaman damgası
    _add_column_if_missing(cur, "odev_satir", "durum_ts TEXT")

    # 2) Günlük özet
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ogrenci_perf_gunluk(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ogrenci_id INTEGER NOT NULL,
      gun TEXT NOT NULL,
      tamam INTEGER DEFAULT 0,
      kismi INTEGER DEFAULT 0,
      yapilmadi INTEGER DEFAULT 0,
      geciken INTEGER DEFAULT 0,
      UNIQUE(ogrenci_id, gun)
    )
    """)

    # 3) Haftalık ders kırılımı
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ogrenci_perf_hafta_ders(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ogrenci_id INTEGER NOT NULL,
      week_start TEXT NOT NULL,
      week_end   TEXT NOT NULL,
      ders TEXT NOT NULL,
      toplam INTEGER DEFAULT 0,
      bitti  INTEGER DEFAULT 0,
      yuzde  INTEGER DEFAULT 0,
      UNIQUE(ogrenci_id, week_start, week_end, ders)
    )
    """)

    # 4) Öğrenci kitap ilerleme özeti
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ogrenci_kitap_ilerleme(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ogrenci_id INTEGER NOT NULL,
      ders TEXT,
      kitap TEXT,
      konu_say INTEGER DEFAULT 0,
      bitti_say INTEGER DEFAULT 0,
      yuzde INTEGER DEFAULT 0,
      last_done_ts TEXT,
      UNIQUE(ogrenci_id, ders, kitap)
    )
    """)

    # 5) Cohort kıyas tablosu (tamamlayan öğrenci sayısı)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cohort_kitap_kapsam(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ders TEXT,
      kitap TEXT,
      konu TEXT,
      done_count INTEGER DEFAULT 0,
      student_count INTEGER DEFAULT 0,
      pct INTEGER DEFAULT 0,
      UNIQUE(ders, kitap, konu)
    )
    """)

    # faydalı indexler
    try: cur.execute("CREATE INDEX IF NOT EXISTS idx_gunluk_ogr_gun ON ogrenci_perf_gunluk(ogrenci_id, gun)")
    except: pass
    try: cur.execute("CREATE INDEX IF NOT EXISTS idx_hd_ogr_week ON ogrenci_perf_hafta_ders(ogrenci_id, week_start)")
    except: pass
    try: cur.execute("CREATE INDEX IF NOT EXISTS idx_kitap_ogr ON ogrenci_kitap_ilerleme(ogrenci_id)")
    except: pass
    try: cur.execute("CREATE INDEX IF NOT EXISTS idx_cohort_ders_kitap ON cohort_kitap_kapsam(ders, kitap)")
    except: pass

    con.commit()
#f--

#s--
def migrate_ogrenci_performans(con: sqlite3.Connection):
    """
    Öğrenci başına belirli bir dönem (ör. haftalık) performans özetini saklar.
    Bu tablo uygulamayı bozmaz; sadece raporlama/dashboards için hızlı okuma sağlar.
    """
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_performans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL REFERENCES ogrenci(id) ON DELETE CASCADE,
            period_start TEXT NOT NULL,     -- ISO tarih (örn. 2025-11-03)
            period_end   TEXT NOT NULL,     -- ISO tarih (örn. 2025-11-09) dahil
            kume_sayisi  INTEGER DEFAULT 0, -- bu dönemde bitiş tarihi pencereye düşen küme sayısı
            gorev_toplam INTEGER DEFAULT 0, -- o küme(ler)deki toplam ödev satırı (odev + odev_satir birleşik)
            gorev_bitti  INTEGER DEFAULT 0, -- 'tamam' / 'yapildi' vb. olan satır sayısı
            ilerleme_yuzde INTEGER DEFAULT 0, -- (bitti/toplam)*100
            gecikmis_kume INTEGER DEFAULT 0,  -- bitiş < bugün ve ilerleme < 100 olan kümeler
            notlar TEXT,                      -- serbest alan: JSON/diagnostic vs.
            guncel_ts TEXT DEFAULT (datetime('now')),

            UNIQUE(ogrenci_id, period_start, period_end)
        )
    """)
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_perf_ogr ON ogrenci_performans(ogrenci_id)")
    except Exception:
        pass
    con.commit()

#Haftalık snapshot üretici (tek komutla günceller)
def _week_bounds(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())     # Pazartesi
    end   = start + timedelta(days=6)           # Pazar
    return start, end
def rebuild_performance_current_week(con: sqlite3.Connection) -> None:
    """
    İç mantık:
      - Haftanın tarih aralığını al.
      - Bu aralığa düşen 'bitiş_tarihi' olan kümeleri say.
      - Bu kümelerdeki odev + odev_satir satırlarını birleştirip toplam/bitti hesapla.
      - 'gecikmis_kume' = bitiş < bugün ve ilerleme < 100
      - Sonucu ogrenci_performans tablosuna UPSERT et (ogrenci_id + dönem eşsiz).
    """
    cur = con.cursor()
    today = date.today()
    ws, we = _week_bounds(today)
    ws_s, we_s = ws.isoformat(), we.isoformat()
    today_s = today.isoformat()

    # Tüm aktif öğrenciler
    ogr_rows = cur.execute("SELECT id FROM ogrenci WHERE COALESCE(aktif,1)=1").fetchall()
    ogr_ids = [int(r["id"]) if isinstance(r, sqlite3.Row) else int(r[0]) for r in ogr_rows]

    for oid in ogr_ids:
        # Bu haftaya düşen KÜMELER (bitiş_tarihi mevcut ve aralıkta)
        kume_rows = cur.execute("""
            SELECT id, COALESCE(bitis_tarihi,'') AS bitis
              FROM odev_kume
             WHERE ogrenci_id=?
               AND bitis_tarihi IS NOT NULL
               AND date(bitis_tarihi) BETWEEN date(?) AND date(?)
        """, (oid, ws_s, we_s)).fetchall()
        kume_ids = [int(r["id"]) for r in kume_rows]
        if not kume_ids:
            # Kayıt yoksa yine de bir satır yazıp 0’larla tutmak istersek:
            cur.execute("""
                INSERT INTO ogrenci_performans(ogrenci_id,period_start,period_end,
                                               kume_sayisi,gorev_toplam,gorev_bitti,ilerleme_yuzde,gecikmis_kume,notlar,guncel_ts)
                VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))
                ON CONFLICT(ogrenci_id,period_start,period_end) DO UPDATE SET
                    kume_sayisi=excluded.kume_sayisi,
                    gorev_toplam=excluded.gorev_toplam,
                    gorev_bitti=excluded.gorev_bitti,
                    ilerleme_yuzde=excluded.ilerleme_yuzde,
                    gecikmis_kume=excluded.gecikmis_kume,
                    notlar=excluded.notlar,
                    guncel_ts=datetime('now')
            """, (oid, ws_s, we_s, 0, 0, 0, 0, 0, None))
            continue

        # UNION ile görev sayımı
        q_marks = ",".join(["?"] * len(kume_ids))
        params = tuple(kume_ids)

        # toplam/bitti
        row = cur.execute(f"""
            WITH src(durum) AS (
                SELECT LOWER(COALESCE(durum,'')) FROM odev       WHERE kume_id IN ({q_marks})
                UNION ALL
                SELECT LOWER(COALESCE(durum,'')) FROM odev_satir WHERE kume_id IN ({q_marks})
            )
            SELECT
                COUNT(*) AS toplam,
                SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','ok','done','bitti') THEN 1 ELSE 0 END) AS bitti
            FROM src
        """, params + params).fetchone()
        toplam = int(row["toplam"] or 0)
        bitti  = int(row["bitti"]  or 0)
        yuzde  = (bitti * 100 // toplam) if toplam > 0 else 0

        # gecikmis_kume: bitiş < bugün ve ilerleme < 100
        gecikmis = 0
        for kr in kume_rows:
            kid   = int(kr["id"])
            bitis = (kr["bitis"] or "")
            if not bitis:
                continue
            # ilgili kümenin kendi ilerlemesi
            crow = cur.execute("""
                WITH src(durum) AS (
                    SELECT LOWER(COALESCE(durum,'')) FROM odev       WHERE kume_id=?
                    UNION ALL
                    SELECT LOWER(COALESCE(durum,'')) FROM odev_satir WHERE kume_id=?
                )
                SELECT
                    COUNT(*) AS t,
                    SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','ok','done','bitti') THEN 1 ELSE 0 END) AS b
            """, (kid, kid)).fetchone()
            t = int(crow["t"] or 0)
            b = int(crow["b"] or 0)
            p = (b * 100 // t) if t > 0 else 0
            if bitis < today_s and p < 100:
                gecikmis += 1

        # serbest not alanı (istersen JSON gibi kullan)
        notlar = None

        # UPSERT
        cur.execute("""
            INSERT INTO ogrenci_performans(
                ogrenci_id, period_start, period_end,
                kume_sayisi, gorev_toplam, gorev_bitti, ilerleme_yuzde, gecikmis_kume, notlar, guncel_ts
            )
            VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))
            ON CONFLICT(ogrenci_id,period_start,period_end) DO UPDATE SET
                kume_sayisi   = excluded.kume_sayisi,
                gorev_toplam  = excluded.gorev_toplam,
                gorev_bitti   = excluded.gorev_bitti,
                ilerleme_yuzde= excluded.ilerleme_yuzde,
                gecikmis_kume = excluded.gecikmis_kume,
                notlar        = excluded.notlar,
                guncel_ts     = datetime('now')
        """, (oid, ws_s, we_s, len(kume_ids), toplam, bitti, yuzde, gecikmis, notlar))

    con.commit()

# --- 30 Günlük Özet ---
def _last30_bounds(d: date) -> tuple[date, date]:
    start = d - timedelta(days=29)  # bugün dahil 30 gün
    end   = d
    return start, end
def rebuild_performance_last_30_days(con: sqlite3.Connection) -> None:
    """
    Son 30 gün için (bugün dahil) ogrenci_performans tablosunu UPSERT eder.
    Haftalık olana benzer mantıkta toplar.
    """
    cur = con.cursor()
    today = date.today()
    s, e = _last30_bounds(today)
    s_s, e_s = s.isoformat(), e.isoformat()
    today_s = today.isoformat()

    ogr_rows = cur.execute("SELECT id FROM ogrenci WHERE COALESCE(aktif,1)=1").fetchall()
    ogr_ids = [int(r["id"]) if isinstance(r, sqlite3.Row) else int(r[0]) for r in ogr_rows]

    for oid in ogr_ids:
        kume_rows = cur.execute("""
            SELECT id, COALESCE(bitis_tarihi,'') AS bitis
              FROM odev_kume
             WHERE ogrenci_id=?
               AND bitis_tarihi IS NOT NULL
               AND date(bitis_tarihi) BETWEEN date(?) AND date(?)
        """, (oid, s_s, e_s)).fetchall()
        kume_ids = [int(r["id"]) for r in kume_rows]

        if not kume_ids:
            cur.execute("""
                INSERT INTO ogrenci_performans(ogrenci_id,period_start,period_end,
                                               kume_sayisi,gorev_toplam,gorev_bitti,ilerleme_yuzde,gecikmis_kume,notlar,guncel_ts)
                VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))
                ON CONFLICT(ogrenci_id,period_start,period_end) DO UPDATE SET
                    kume_sayisi   = excluded.kume_sayisi,
                    gorev_toplam  = excluded.gorev_toplam,
                    gorev_bitti   = excluded.gorev_bitti,
                    ilerleme_yuzde= excluded.ilerleme_yuzde,
                    gecikmis_kume = excluded.gecikmis_kume,
                    notlar        = excluded.notlar,
                    guncel_ts     = datetime('now')
            """, (oid, s_s, e_s, 0, 0, 0, 0, 0, None))
            continue

        q_marks = ",".join(["?"] * len(kume_ids))
        params = tuple(kume_ids)

        row = cur.execute(f"""
            WITH src(durum) AS (
                SELECT LOWER(COALESCE(durum,'')) FROM odev       WHERE kume_id IN ({q_marks})
                UNION ALL
                SELECT LOWER(COALESCE(durum,'')) FROM odev_satir WHERE kume_id IN ({q_marks})
            )
            SELECT
                COUNT(*) AS toplam,
                SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','ok','done','bitti') THEN 1 ELSE 0 END) AS bitti
            FROM src
        """, params + params).fetchone()

        toplam = int(row["toplam"] or 0)
        bitti  = int(row["bitti"]  or 0)
        yuzde  = (bitti * 100 // toplam) if toplam > 0 else 0

        gecikmis = 0
        for kr in kume_rows:
            kid   = int(kr["id"])
            bitis = (kr["bitis"] or "")
            if not bitis:
                continue
            crow = cur.execute("""
                WITH src(durum) AS (
                    SELECT LOWER(COALESCE(durum,'')) FROM odev       WHERE kume_id=?
                    UNION ALL
                    SELECT LOWER(COALESCE(durum,'')) FROM odev_satir WHERE kume_id=?
                )
                SELECT
                    COUNT(*) AS t,
                    SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','ok','done','bitti') THEN 1 ELSE 0 END) AS b
            """, (kid, kid)).fetchone()
            t = int(crow["t"] or 0)
            b = int(crow["b"] or 0)
            p = (b * 100 // t) if t > 0 else 0
            if bitis < today_s and p < 100:
                gecikmis += 1

        cur.execute("""
            INSERT INTO ogrenci_performans(
                ogrenci_id, period_start, period_end,
                kume_sayisi, gorev_toplam, gorev_bitti, ilerleme_yuzde, gecikmis_kume, notlar, guncel_ts
            )
            VALUES(?,?,?,?,?,?,?,?,?,datetime('now'))
            ON CONFLICT(ogrenci_id,period_start,period_end) DO UPDATE SET
                kume_sayisi   = excluded.kume_sayisi,
                gorev_toplam  = excluded.gorev_toplam,
                gorev_bitti   = excluded.gorev_bitti,
                ilerleme_yuzde= excluded.ilerleme_yuzde,
                gecikmis_kume = excluded.gecikmis_kume,
                notlar        = excluded.notlar,
                guncel_ts     = datetime('now')
        """, (oid, s_s, e_s, len(kume_ids), toplam, bitti, yuzde, gecikmis, None))

    con.commit()
#f--

def _seed_if_needed(con: sqlite3.Connection):
    """Eğer ders tabloları boşsa seed klasöründen json ile doldur."""
    cur = con.cursor()
    for ders in DERS_TABLOLARI:
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM {ders}").fetchone()[0]
        except sqlite3.Error:
            # (Tablo adı beklenmedik bir nedenle yoksa sessiz atla)
            continue
        if cnt == 0:
            f = SEED_DIR / f"{ders}.json"
            if f.exists():
                try:
                    topics = json.loads(f.read_text(encoding="utf-8"))
                    cur.executemany(
                        f"INSERT INTO {ders}(konu) VALUES (?)",
                        [(t,) for t in topics]
                    )
                except Exception:
                    # Seed dosyası bozuksa atla
                    pass


# ---------------- Basit yardımcılar ----------------

def listele_ogrenciler(con, aktif_yalniz: bool = True):
    sql = "SELECT * FROM ogrenci"
    if aktif_yalniz:
        sql += " WHERE aktif=1"
    sql += " ORDER BY ad, soyad"
    return con.execute(sql).fetchall()

def ders_konularini_cek(con, ders: str):
    return con.execute(f"SELECT * FROM {ders} ORDER BY id").fetchall()

def ogrenci_kitaplarini_cek(con, ogrenci_id: int, ders: str):
    return con.execute(
        "SELECT kitap_ad FROM ogrenci_kitap WHERE ogrenci_id=? AND ders=? ORDER BY kitap_ad",
        (ogrenci_id, ders)
    ).fetchall()

def kitap_havuzu(con, ders: Optional[str] = None):
    if ders:
        return con.execute("SELECT ad FROM kitap WHERE ders=? ORDER BY ad", (ders,)).fetchall()
    return con.execute("SELECT ders, ad FROM kitap ORDER BY ders, ad").fetchall()

def kitap_ekle_havuz(con, ders: str, adlar: List[str]):
    cur = con.cursor()
    for a in adlar:
        a = (a or "").strip()
        if not a:
            continue
        try:
            cur.execute("INSERT OR IGNORE INTO kitap(ders, ad) VALUES(?,?)", (ders, a))
        except Exception:
            pass
    con.commit()

def ogrenciye_kitap_ekle(con, ogrenci_ids: List[int], ders: str, kitap_adlar: List[str]):
    cur = con.cursor()
    for oid in ogrenci_ids:
        for a in kitap_adlar:
            a = (a or "").strip()
            if not a:
                continue
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO ogrenci_kitap(ogrenci_id, ders, kitap_ad) VALUES(?,?,?)",
                    (oid, ders, a)
                )
            except Exception:
                pass
    con.commit()

def ogrenciden_kitap_sil(con, ogrenci_ids: List[int], ders: str, kitap_adlar: List[str]):
    cur = con.cursor()
    for oid in ogrenci_ids:
        for a in kitap_adlar:
            cur.execute(
                "DELETE FROM ogrenci_kitap WHERE ogrenci_id=? AND ders=? AND kitap_ad=?",
                (oid, ders, (a or "").strip())
            )
    con.commit()

def kitap_sil_havuz(con, ders: str, adlar: List[str], odevleri_de_temizle: bool = False):
    """
    Kitapları ana 'kitap' havuzundan, öğrenci atamalarından ('ogrenci_kitap')
    ve özelliklerinden ('kitap_ozellik') tamamen siler.
    İsteğe bağlı olarak tamamlanmamış ilgili 'odev' satırlarını da temizleyebilir.
    """
    cur = con.cursor()
    for a in adlar:
        a = (a or "").strip()
        if not a:
            continue
        try:
            # 1. Ana kitap havuzundan sil
            cur.execute("DELETE FROM kitap WHERE ders=? AND ad=?", (ders, a))
            # 2. Öğrenci atamalarından sil
            cur.execute("DELETE FROM ogrenci_kitap WHERE ders=? AND kitap_ad=?", (ders, a))
            # 3. Kitap özelliklerinden sil
            try:
                cur.execute("DELETE FROM kitap_ozellik WHERE ders=? AND kitap_ad=?", (ders, a))
            except Exception:
                pass
            # 4. İsteğe bağlı: bu kitaba ait ödev kayıtlarını sil
            if odevleri_de_temizle:
                try:
                    cur.execute("DELETE FROM odev WHERE ders=? AND kitap_ad=?", (ders, a))
                except Exception:
                    pass
        except Exception as e:
            print(f"Kitap silme hatası ({a}): {e}")
    con.commit()

def kitap_atanan_ogrenciler(con, ders: str, kitap_ad: str) -> List[sqlite3.Row]:
    """Bu kitabın atanmış olduğu öğrencileri döndürür."""
    return con.execute(
        """
        SELECT o.id, o.ad, o.soyad 
        FROM ogrenci o
        JOIN ogrenci_kitap ok ON ok.ogrenci_id = o.id
        WHERE ok.ders=? AND ok.kitap_ad=?
        ORDER BY o.ad, o.soyad
        """,
        (ders, kitap_ad)
    ).fetchall()

def son_kume_kaydi(con: sqlite3.Connection, ogrenci_id: int):
    """
    Bu öğrencinin 'son' kümesini güvenli şekilde döndürür.
    Öncelik: odev_kume.verilis_tarihi DESC, id DESC.
    Eğer hiç odev_kume yoksa ama odev_satir varsa, en büyük kume_id'yi alıp
    sahte bir kayıt objesi döndürür {'id': kume_id, 'verilis_tarihi': None, ...}.
    Bulunamazsa None.
    """
    try:
        row = con.execute(
            """
            SELECT *
              FROM odev_kume
             WHERE ogrenci_id=?
             ORDER BY date(verilis_tarihi) DESC, id DESC
             LIMIT 1
            """,
            (int(ogrenci_id),)
        ).fetchone()
        if row:
            return row
    except Exception:
        pass

    # odev_kume yoksa: odev_satir'dan türet
    try:
        r2 = con.execute(
            """
            SELECT MAX(COALESCE(kume_id,0)) AS kid
              FROM odev_satir
             WHERE ogrenci_id=?
            """,
            (int(ogrenci_id),)
        ).fetchone()
        kid = int(r2["kid"] or 0) if r2 else 0
        if kid > 0:
            # sahte obje: sqlite3.Row benzeri dict
            return {"id": kid, "ogrenci_id": int(ogrenci_id),
                    "verilis_tarihi": None, "bitis_tarihi": None, "aciklama": None}
    except Exception:
        pass

    return None


def kume_satirlari(con: sqlite3.Connection, kume_id: int):
    """
    Verilen kume_id için ödev satırlarını getirir.
    Hem eski 'odev' tablosunu hem yeni 'odev_satir'ı destekler.
    Dönüş: [{'ders':..,'kitap':..,'konu':..,'saat_dk':..,'tarih':..,'durum':..}, ...]
    """
    out = []

    # Yeni şema (odev_satir)
    try:
        rows = con.execute(
            """SELECT ders AS ders, kitap AS kitap, konu AS konu,
                      NULL AS saat_dk, tarih, durum
                 FROM odev_satir
                WHERE kume_id=?""",
            (int(kume_id),)
        ).fetchall()
        for r in rows:
            out.append(dict(r))
    except Exception:
        pass

    # Eski şema (odev) – var ise ekle
    try:
        rows = con.execute(
            """SELECT ders AS ders, kitap_ad AS kitap, konu_ad AS konu,
                      saat_dk AS saat_dk, NULL AS tarih, durum
                 FROM odev
                WHERE kume_id=?""",
            (int(kume_id),)
        ).fetchall()
        for r in rows:
            out.append(dict(r))
    except Exception:
        pass

    return out

# --- Güvenli ders tablosu oluşturucu ve kontrol ---

def ensure_ders_tablosu(con, ders: str):
    """
    İstenen ders tablosu yoksa oluşturur (uyumlu şema).
    Varsa dokunmaz.
    """
    cur = con.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {ders}(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konu TEXT NOT NULL,
            ort_soru INTEGER,
            ort_sure INTEGER,
            aciklama TEXT,
            zorluk INTEGER
        )
    """)
    con.commit()

def ders_tablosu_var_mi(con, ders: str) -> bool:
    row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (ders,)).fetchone()
    return bool(row)

#S--
# ================== PERFORMANS TABLOSU ve YENİDEN-BEREKETLEME ==================

def ensure_performance_schema(con: sqlite3.Connection):
    """
    ogrenci_performans şemasını güvenceye alır (idempotent).
    - Tablo yoksa minimal şemayla oluşturur.
    - Varsa eksik kolonları ALTER ile ekler.
    - Gerekli indexleri oluşturur (varsa dokunmaz).
    """
    cur = con.cursor()

    # 1) Yoksa minimal tabloyu aç (sadece id + ogrenci_id ile başlatıyoruz)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_performans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL
        )
    """)

    # 2) Eksik kolonları tek tek ekle
    _add_column_if_missing(cur, "ogrenci_performans", "gun TEXT")
    _add_column_if_missing(cur, "ogrenci_performans", "aralik TEXT")
    _add_column_if_missing(cur, "ogrenci_performans", "tamam INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "ogrenci_performans", "kismi INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "ogrenci_performans", "yapilmadi INTEGER DEFAULT 0")
    _add_column_if_missing(cur, "ogrenci_performans", "geciken INTEGER DEFAULT 0")

    # 3) (Opsiyonel) Bozuk/yarım kalmış eski index varsa sorunsuz devam edelim
    #    Index oluştururken kolonlar artık mevcut.
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_op_ogr_gun ON ogrenci_performans(ogrenci_id, gun)")
    except Exception:
        pass
    try:
        # UNIQUE kısıtını tablo oluşturduktan sonra index ile sağlıyoruz
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_op_ogr_gun_aralik ON ogrenci_performans(ogrenci_id, gun, aralik)")
    except Exception:
        pass

    con.commit()


def _normalized_satir_sql():
    """
    'odev_satir' + (varsa) 'odev' tablosunu tek biçime indirger.
    Her satır: ogrenci_id, kume_id, gun, durum ('TAMAM' / 'DEVAM')
    """
    return """
    WITH satir AS (
        SELECT
            s.ogrenci_id           AS ogrenci_id,
            s.kume_id              AS kume_id,
            DATE(COALESCE(s.tarih, k.bitis_tarihi)) AS gun,
            UPPER(COALESCE(s.durum,'devam')) AS durum,
            k.bitis_tarihi         AS bitis
        FROM odev_satir s
        LEFT JOIN odev_kume k ON k.id = s.kume_id

        UNION ALL

        SELECT
            o.ogrenci_id           AS ogrenci_id,
            o.kume_id              AS kume_id,
            DATE(k.bitis_tarihi)   AS gun,
            UPPER(COALESCE(o.durum,'devam')) AS durum,
            k.bitis_tarihi         AS bitis
        FROM odev o
        LEFT JOIN odev_kume k ON k.id = o.kume_id
    ),
    filt AS (
        -- gun (rapor günü) belirlenemeyenleri at
        SELECT * FROM satir
        WHERE gun IS NOT NULL
    ),
    kume_ozet AS (
        SELECT
            ogrenci_id, gun, kume_id,
            SUM(CASE WHEN durum='TAMAM' THEN 1 ELSE 0 END) AS s_tamam,
            SUM(CASE WHEN durum='DEVAM' THEN 1 ELSE 0 END) AS s_devam,
            MIN(bitis) AS bitis
        FROM filt
        GROUP BY ogrenci_id, gun, kume_id
    ),
    kume_sinif AS (
        -- Küme bazında sınıflandırma:
        --  - 'tamam': en az bir satır 'TAMAM' var ve 'DEVAM' yok
        --  - 'kismi' : hem 'TAMAM' hem 'DEVAM' var
        --  - 'yapilmadi': hiç 'TAMAM' yok, sadece 'DEVAM' var
        SELECT
            ogrenci_id, gun, kume_id, bitis,
            CASE WHEN s_tamam>0 AND s_devam=0 THEN 1 ELSE 0 END AS is_tamam,
            CASE WHEN s_tamam>0 AND s_devam>0 THEN 1 ELSE 0 END AS is_kismi,
            CASE WHEN s_tamam=0 AND s_devam>0 THEN 1 ELSE 0 END AS is_yapilmadi
        FROM kume_ozet
    )
    SELECT * FROM kume_sinif
    """


def _write_perf(con: sqlite3.Connection, aralik: str, date_start: str, date_end: str):
    """
    [date_start, date_end] aralığı için ogrenci_performans tablosunu yeniden yazar.
    """
    ensure_performance_schema(con)
    cur = con.cursor()

    norm_sql = _normalized_satir_sql()

    # İlgili aralıkta kalanları çek → günlük toplama
    rows = cur.execute(f"""
        WITH ks AS ({norm_sql})
        SELECT
            ogrenci_id,
            gun,
            SUM(is_tamam)     AS tamam,
            SUM(is_kismi)     AS kismi,
            SUM(is_yapilmadi) AS yapilmadi,
            SUM(CASE WHEN (is_yapilmadi=1 AND bitis IS NOT NULL AND date(bitis) < date('now')) THEN 1 ELSE 0 END) AS geciken
        FROM ks
        WHERE date(gun) BETWEEN date(?) AND date(?)
        GROUP BY ogrenci_id, gun
        ORDER BY ogrenci_id, gun
    """, (date_start, date_end)).fetchall()

    # Aynı aralık için eski kayıtları sil → taze yaz
    cur.execute("DELETE FROM ogrenci_performans WHERE aralik=? AND date(gun) BETWEEN date(?) AND date(?)",
                (aralik, date_start, date_end))

    cur.executemany("""
        INSERT OR IGNORE INTO ogrenci_performans(ogrenci_id, gun, aralik, tamam, kismi, yapilmadi, geciken)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [(r["ogrenci_id"], r["gun"], aralik, r["tamam"] or 0, r["kismi"] or 0, r["yapilmadi"] or 0, r["geciken"] or 0)
          for r in rows])

    con.commit()


def rebuild_performance_current_week(con: sqlite3.Connection):
    """
    Pazartesi–Pazar aralığı (içinde bulunduğumuz hafta) için yeniden hesaplar.
    """
    from datetime import date, timedelta
    today = date.today()
    start = today - timedelta(days=today.weekday())   # Pazartesi
    end   = start + timedelta(days=6)                 # Pazar
    _write_perf(con, "week", start.isoformat(), end.isoformat())


def rebuild_performance_last_30_days(con: sqlite3.Connection):
    """
    Bugün dahil son 30 gün için yeniden hesaplar.
    """
    from datetime import date, timedelta
    end   = date.today()
    start = end - timedelta(days=29)
    _write_perf(con, "30d", start.isoformat(), end.isoformat())
#F--


#--*-*-*-*-*-*-*-*-*-*-*
# ================== DEMO / TEST SEED – TEK FONKSİYON ==================
'''
Bu haftayı/son 30 günü şu anki tarihe hizalayarak tekrar doldur:
python -c "import db; from datetime import date; db.perf_demo_seed('insert', n_students=40, base_date=date.today())"

python -c "import db; db.perf_demo_seed('delete')"
Önemli not: Sadece fonksiyonu dosyadan silmek, daha önce eklenmiş demo verilerini silmez. 
Bu yüzden önce delete komutunu çalıştırmak şart.
'''

# ================== DEMO SEED (PANELİ DOLUM İÇİN) ==================
def perf_demo_seed(action="insert", n_students=25, base_date=None):
    """
    Paneli hızlıca denemek için örnek veri ekler/siler.

    Kullanım:
      - Ekle:  perf_demo_seed("insert", n_students=40)
      - Sil:   perf_demo_seed("delete")

    Notlar:
      - Öğrenciler ogrenci.kisisel_bilgiler içinde 'DEMO SEED' etiketiyle işaretlenir.
      - Panelin okuduğu alanlar: period_start/period_end, ilerleme_yuzde, gorev_bitti,
        gorev_toplam, kume_sayisi, gecikmis_kume.
      - Python 3.9 uyumludur (X | Y yok).
    """
    import random, sqlite3
    from datetime import date, timedelta

    # ---- tarih yardımcıları ----
    def _week_bounds(d: date):
        start = d - timedelta(days=d.weekday())  # Pazartesi
        end = start + timedelta(days=6)          # Pazar
        return start, end

    def _last30_bounds(d: date):
        return d - timedelta(days=29), d

    today = base_date if isinstance(base_date, date) else date.today()
    ws, we = _week_bounds(today)
    l30s, l30e = _last30_bounds(today)
    prev30e = l30s - timedelta(days=1)
    prev30s = prev30e - timedelta(days=29)

    con = get_conn()
    cur = con.cursor()

    # ---- küçük yardımcı: kolon yoksa ekle ----
    def _add_col_if_missing(table: str, coldef: str):
        try:
            colname = coldef.split()[0]
            info = cur.execute(f"PRAGMA table_info({table})").fetchall()
            mevcut = { (r[1] if isinstance(r, (tuple,list)) else r["name"]) for r in info }
            if colname not in mevcut:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
        except Exception:
            pass

    # ---- asgari şema garantisi (idempotent) ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            soyad TEXT NOT NULL,
            ogr_no TEXT,
            ana_grup TEXT,
            alt_grup TEXT,
            veli_ad TEXT,
            veli_yakinlik TEXT,
            veli_tel1 TEXT,
            veli_tel2 TEXT,
            ogr_tel TEXT,
            ogr_mail TEXT,
            veli_mail TEXT,
            dogum_tarihi TEXT,
            kisisel_bilgiler TEXT,
            aktif INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ogrenci_performans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER
        )
    """)
    # Panelin beklediği kolonları tek tek garanti et (varsa dokunmaz)
    for col in [
        "gun TEXT",
        "aralik TEXT",
        "period_start TEXT",
        "period_end TEXT",
        "ilerleme_yuzde INTEGER",
        "gorev_bitti INTEGER",
        "gorev_toplam INTEGER",
        "kume_sayisi INTEGER",
        "gecikmis_kume INTEGER"
    ]:
        _add_col_if_missing("ogrenci_performans", col)

    con.commit()

    # ---- silme modu ----
    if str(action).lower() == "delete":
        try:
            demo_ids = [r[0] for r in cur.execute(
                "SELECT id FROM ogrenci WHERE COALESCE(kisisel_bilgiler,'') LIKE '%DEMO SEED%'"
            ).fetchall()]
            if demo_ids:
                cur.executemany("DELETE FROM ogrenci_performans WHERE ogrenci_id=?", [(i,) for i in demo_ids])
                cur.execute("DELETE FROM ogrenci WHERE COALESCE(kisisel_bilgiler,'') LIKE '%DEMO SEED%'")
            # Eski işaretli satırlar
            cur.execute("""
                DELETE FROM ogrenci_performans
                 WHERE COALESCE(aralik,'') LIKE '%DEMO MARK%'
                    OR COALESCE(gun,'')    LIKE '%DEMO MARK%'
            """)
            con.commit()
        finally:
            con.close()
        return

    # ---- ekleme modu ----
    random.seed(42)
    demo_ids = []

    # DEMO öğrencileri
    for i in range(int(n_students)):
        ad = f"Demo{i+1}"
        soyad = "Öğrenci"
        cur.execute(
            "INSERT INTO ogrenci(ad, soyad, aktif, kisisel_bilgiler) VALUES(?,?,1,?)",
            (ad, soyad, "DEMO SEED – panel test verisi")
        )
        demo_ids.append(cur.lastrowid)

    ws_s, we_s   = ws.isoformat(), we.isoformat()
    l30s_s, l30e_s = l30s.isoformat(), l30e.isoformat()
    p30s_s, p30e_s = prev30s.isoformat(), prev30e.isoformat()

    rows = []
    for oid in demo_ids:
        # Haftalık
        gorev_toplam_w = random.randint(8, 20)
        gorev_bitti_w  = random.randint(max(1, int(gorev_toplam_w*0.4)), gorev_toplam_w)
        kume_sayisi_w  = random.randint(1, 4)
        ilerleme_w     = int(round((gorev_bitti_w / max(1, gorev_toplam_w)) * 100))

        # Son 30 gün
        gorev_toplam_m = random.randint(20, 60)
        gorev_bitti_m  = random.randint(max(1, int(gorev_toplam_m*0.5)), gorev_toplam_m)
        kume_sayisi_m  = random.randint(2, 8)
        ilerleme_m     = int(round((gorev_bitti_m / max(1, gorev_toplam_m)) * 100))

        # Gecikme trendi (önceki 30 → son 30)
        gecikme_prev = random.randint(0, 6)
        gecikme_curr = max(0, gecikme_prev + random.randint(-2, 4))

        # Haftalık satır
        rows.append((oid, None, None, ws_s, we_s,
                     ilerleme_w, gorev_bitti_w, gorev_toplam_w, kume_sayisi_w, None))

        # Son 30 gün satır
        rows.append((oid, None, None, l30s_s, l30e_s,
                     ilerleme_m, gorev_bitti_m, gorev_toplam_m, kume_sayisi_m, gecikme_curr))

        # Önceki 30 gün (trend referansı)
        rows.append((oid, None, None, p30s_s, p30e_s,
                     max(0, ilerleme_m - random.randint(0, 10)),
                     max(0, gorev_bitti_m - random.randint(0, 10)),
                     max(1, gorev_toplam_m - random.randint(0, 5)),
                     max(1, kume_sayisi_m - random.randint(0, 2)),
                     gecikme_prev))

    cur.executemany("""
        INSERT INTO ogrenci_performans
            (ogrenci_id, gun, aralik, period_start, period_end,
             ilerleme_yuzde, gorev_bitti, gorev_toplam, kume_sayisi, gecikmis_kume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    # İşaret
    cur.execute("""
        UPDATE ogrenci_performans
           SET aralik = TRIM(COALESCE(aralik,'')) || ' DEMO MARK'
         WHERE period_start IN (?, ?, ?)
           AND period_end   IN (?, ?, ?)
    """, (ws_s, l30s_s, p30s_s, we_s, l30e_s, p30e_s))

    # --- Yeni Deneme Sınavı Modülü ---
    _init_deneme_tables(cur)
    # --- Yeni Koçluk Modülü ---
    _init_coaching_tables(cur)

    # --- Yeni Müfredat ve Grup Yönetimi (v23) ---
    init_curriculum(con)
    init_group_lessons(con)

    con.commit()
    con.close()

# ====================== MÜFREDAT YÖNETİMİ (v22) ======================

def init_curriculum(con: sqlite3.Connection):
    """Müfredat tablosunu oluştur ve mevcut dersleri listeye kaydet."""
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ders_tanimlari(
        id TEXT PRIMARY KEY,       -- Örn: 'tyt_matematik' (aynı zamanda tablo adı)
        ad TEXT NOT NULL,          -- Örn: 'TYT Matematik' (görünen ad)
        grup TEXT,                 -- Örn: 'YKS', 'LGS', 'Ara Sınıf'
        aktif INTEGER DEFAULT 1,   -- 1: Kullanımda, 0: Gizli
        ozel INTEGER DEFAULT 0,    -- 0: Sistem Dersi, 1: Kullanıcı Dersi
        siralama INTEGER DEFAULT 99
    )""")
    con.commit()
    
    # Mevcut DERS_TABLOLARI'ndaki dersleri seed et (eğer yoksa)
    # Not: DERS_TABLOLARI bu dosyanın başında tanımlı.
    try:
        count_row = cur.execute("SELECT COUNT(*) FROM ders_tanimlari").fetchone()
        count = count_row[0] if count_row else 0
    except:
        count = 0

    if count == 0 and 'DERS_TABLOLARI' in globals():
        data = []
        for i, d in enumerate(DERS_TABLOLARI):
            # Basit etiketleme mantığı
            grup = "YKS"
            if d.startswith("lgs"): grup = "LGS"
            elif d in ("geometri", "fizik", "kimya", "biyoloji", "turkce", "tarih", "cografya"): grup = "Ara Sınıf" # Ortak
            
            # Görünen Ad
            ad = d.replace("_", " ").title()
            # Düzeltmeler
            ad = ad.replace("Tyt", "TYT").replace("Ayt", "AYT").replace("Lgs", "LGS").replace("Kpss", "KPSS")
            ad = ad.replace("Matematik", "Matematik").replace("Turkce", "Türkçe").replace("Cografya", "Coğrafya")
            
            data.append((d, ad, grup, 1, 0, i+1))
            
        cur.executemany("INSERT OR IGNORE INTO ders_tanimlari(id, ad, grup, aktif, ozel, siralama) VALUES(?, ?, ?, ?, ?, ?)", data)
        con.commit()

def get_lesson_config(con=None):
    """Tüm ders yapılandırmasını {id: {ad, grup, aktif}} formatında döner."""
    if not con: con = get_conn()
    try:
        rows = con.execute("SELECT * FROM ders_tanimlari ORDER BY siralama, id").fetchall()
        # Row objesini dict'e çevir
        res = {}
        for r in rows:
            # sqlite3.Row ise dict gibi davranır ama emin olalım
            d = dict(r) if hasattr(r, 'keys') else {
                'id': r[0], 'ad': r[1], 'grup': r[2], 'aktif': r[3], 'ozel': r[4], 'siralama': r[5]
            }
            res[d['id']] = d
        return res
    except:
        return {}

def add_custom_lesson(ad_gosterim, grup, tablo_adi=None):
    """
    Yeni bir ders ekler. 
    1. Tablo adı üretilir.
    2. Tablo oluşturulur.
    3. Config'e eklenir.
    4. DERS_TABLOLARI listesine eklenir.
    """
    if not tablo_adi:
        # Otomatik üret: "Hızlı Okuma" -> "hizli_okuma"
        import unicodedata
        s = ad_gosterim.lower().strip()
        # Türkçe karakterleri basitçe değiştir
        replacements = {'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c'}
        for tr, eng in replacements.items():
            s = s.replace(tr, eng)
            
        s = "".join([c if c.isalnum() else "_" for c in s])
        tablo_adi = "ozel_" + s # Çakışmayı önlemek için prefix
    
    con = get_conn()
    cur = con.cursor()
    
    # 1. Ders tablosunu oluştur
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {tablo_adi}(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        konu TEXT NOT NULL,
        ort_soru INTEGER,
        ort_sure INTEGER,
        aciklama TEXT,
        zorluk INTEGER
    )""")
    
    # 2. Tanımlara ekle
    try:
        cur.execute("INSERT INTO ders_tanimlari(id, ad, grup, aktif, ozel, siralama) VALUES(?, ?, ?, 1, 1, 999)",
                   (tablo_adi, ad_gosterim, grup))
        con.commit()
    except Exception as e:
        return False, f"Ders eklenemedi (Zaten var olabilir): {e}"
        
    # 3. Global listeye yansıt (Runtime)
    if 'DERS_TABLOLARI' in globals() and tablo_adi not in DERS_TABLOLARI:
        DERS_TABLOLARI.append(tablo_adi)
        
    return True, f"'{ad_gosterim}' dersi eklendi.", tablo_adi

def update_lesson_status(lesson_id, is_active: bool):
    """Dersin aktif/pasif durumunu değiştirir."""
    con = get_conn()
    val = 1 if is_active else 0
    con.execute("UPDATE ders_tanimlari SET aktif=? WHERE id=?", (val, lesson_id))
    con.commit()

def load_custom_lessons():
    """DB'deki özel dersleri global DERS_TABLOLARI listesine ekler (Başlangıçta çağrılmalı)."""
    if 'DERS_TABLOLARI' not in globals():
        return
        
    con = get_conn()
    try:
        # Tablo yoksa henüz init edilmemiştir
        cur = con.execute("SELECT id FROM ders_tanimlari WHERE ozel=1 AND aktif=1")
        rows = cur.fetchall()
        for r in rows:
            lid = r[0]
            if lid not in DERS_TABLOLARI:
                DERS_TABLOLARI.append(lid)
                #print(f"Loaded custom lesson: {lid}")
    except:
        pass

# ====================== GRUP DERS EŞLEŞTİRME (v23) ======================

def init_group_lessons(con: sqlite3.Connection):
    """Grup-Ders eşleşme tablosunu oluştur."""
    con.execute("""
    CREATE TABLE IF NOT EXISTS grup_dersleri(
        grup_adi TEXT,  -- Örn: '11-say', '12-ea' (alt_grup)
        ders_id TEXT,   -- Örn: 'fizik', 'tyt_matematik'
        PRIMARY KEY(grup_adi, ders_id)
    )""")
    con.commit()

def get_lessons_for_group(grup_adi: str) -> list:
    """Belirtilen grubun ders ID listesini döner."""
    con = get_conn()
    try:
        rows = con.execute("SELECT ders_id FROM grup_dersleri WHERE grup_adi=?", (grup_adi,)).fetchall()
        return [r[0] for r in rows]
    except:
        return []

def set_lessons_for_group(grup_adi: str, lesson_ids: list):
    """Bir grubun derslerini günceller (önce siler sonra ekler)."""
    con = get_conn()
    cur = con.cursor()
    
    # Tablo yoksa oluştur (her ihtimale karşı)
    init_group_lessons(con)
    
    cur.execute("DELETE FROM grup_dersleri WHERE grup_adi=?", (grup_adi,))
    if lesson_ids:
        data = [(grup_adi, lid) for lid in lesson_ids]
        cur.executemany("INSERT INTO grup_dersleri(grup_adi, ders_id) VALUES(?,?)", data)
    con.commit()

DEFAULT_GRUP_DERSLER = {
    "YKS": ["tyt_matematik", "problemler", "ayt_matematik", "geometri", "fizik", "kimya",
            "biyoloji", "turkce", "paragraf", "tarih", "cografya", "felsefe", "edebiyat"],
    "Ara Sınıf": ["geometri", "fizik", "kimya", "biyoloji", "turkce", "tarih", "cografya",
                  "felsefe", "edebiyat", "tyt_matematik", "problemler"],
    "LGS": ["lgs_matematik", "lgs_fen", "lgs_turkce", "lgs_inkilap", "lgs_dinkulturu", "lgs_ingilizce"]
}

def get_student_curriculum(student_id: int) -> list:
    """
    Öğrencinin grubuna (alt_grup) göre atanmış ders listesini döner.
    1. Eğer özel grup ataması varsa onu döner.
    2. Yoksa, 'ana_grup' bilgisine göre varsayılan orjinal listeyi döner.
    """
    con = get_conn()
    try:
        # ana_grup bilgisini de çekiyoruz
        row = con.execute("SELECT alt_grup, ana_grup FROM ogrenci WHERE id=?", (student_id,)).fetchone()
        if not row:
            return []
            
        alt_grup = row[0]
        ana_grup = row[1] or "YKS"
        
        # 1. Özel atama var mı?
        if alt_grup:
            ozel_liste = get_lessons_for_group(alt_grup)
            if ozel_liste:
                return ozel_liste

        # 2. Yoksa varsayılan listeye dön (Orjinal Yapı)
        return DEFAULT_GRUP_DERSLER.get(ana_grup, DEFAULT_GRUP_DERSLER.get("YKS", []))

    except Exception as e:
        print(f"Curriculum Error: {e}")
        return []




def migrate_ogrenci_hedef(con):
    """
    Her öğrenci için 'hedef' bilgilerini tutacak kolonları ekler.
    """
    cur = con.cursor()
    cols = ["hedef_bolum TEXT", "hedef_tyt REAL", "hedef_ayt REAL", "hedef_lgs REAL"]
    
    # Pragma ile kontrol ederek ekle
    # (sqlite eski sürümlerde add column if not exists yok, try-except safer)
    for c in cols:
        try:
            cur.execute(f"ALTER TABLE ogrenci ADD COLUMN {c}")
        except Exception:
            pass
            
    con.commit()
