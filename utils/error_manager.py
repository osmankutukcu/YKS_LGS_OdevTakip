
import os, sys, traceback, datetime, threading
from ui import app_settings as appset

def _log_dir():
    d = appset.ayar_get('log_dir')
    if d:
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            pass
    try:
        from db import _platform_appdata_dir
        p = _platform_appdata_dir() / "logs"
    except Exception:
        from pathlib import Path
        p = Path.home() / ".yks_lgs_manager" / "logs"
    try:
        p.mkdir(parents=True, exist_ok=True)
        return str(p)
    except Exception:
        import tempfile
        return tempfile.gettempdir()

def log_exception(exc_type, exc_value, tb):
    try:
        ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        fname = os.path.join(_log_dir(), f'error_{ts}.log')
        with open(fname, 'w', encoding='utf-8') as f:
            f.write('== HATA ZAMANI ==\n')
            f.write(ts + '\n\n')
            f.write('== İSTİSNA ==\n')
            traceback.print_exception(exc_type, exc_value, tb, file=f)
        # kullanıcıya kısa bildirim
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, 'Hata Günlüğü', f'Bir hata oluştu. Günlük: {fname}')
        except Exception:
            pass
    except Exception:
        pass

def install_global_hook():
    sys.excepthook = log_exception

def safe_slot(fn):
    def wrap(*a, **k):
        try:
            return fn(*a, **k)
        except Exception:
            ex = sys.exc_info()
            log_exception(*ex)
    return wrap
