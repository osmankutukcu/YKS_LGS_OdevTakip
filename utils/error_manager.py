
import os, sys, traceback, datetime, threading, subprocess
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

def _get_target_log_dirs():
    """Hem sistem AppData/Application Support dizinini hem de proje ve çalışma klasöründeki
    'logs' dizinlerini döndürür. Böylece kullanıcı Finder veya Gezginde logları her zaman doğrudan görür."""
    dirs = []
    primary = _log_dir()
    if primary and primary not in dirs:
        dirs.append(primary)

    # Proje klasöründeki logs (örn. OTPxpython/YKS_LGS_HomeworkManager v2/logs)
    try:
        proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
        if os.path.isdir(proj_dir) and proj_dir not in dirs:
            dirs.append(proj_dir)
    except Exception:
        pass

    # Aktif çalışma dizini altındaki logs
    try:
        cwd_dir = os.path.abspath("logs")
        if os.path.isdir(cwd_dir) and cwd_dir not in dirs:
            dirs.append(cwd_dir)
    except Exception:
        pass

    return dirs

def log_exception(exc_type, exc_value, tb):
    try:
        ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_name = f'error_{ts}.log'
        target_dirs = _get_target_log_dirs()
        saved_paths = []

        content = (
            '== HATA ZAMANI ==\n'
            f'{ts}\n\n'
            '== İSTİSNA ==\n'
            + ''.join(traceback.format_exception(exc_type, exc_value, tb))
        )

        for d in target_dirs:
            try:
                os.makedirs(d, exist_ok=True)
                path = os.path.join(d, log_name)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                saved_paths.append(path)
            except Exception:
                pass

        primary_file = saved_paths[0] if saved_paths else os.path.join(_log_dir(), log_name)
        # Proje dizininde olan bir path varsa kullanıcıya onu göster (Finder'da doğrudan erişilebilir)
        user_visible_file = primary_file
        for p in saved_paths:
            if "YKS_LGS_HomeworkManager" in p and "Library" not in p:
                user_visible_file = p
                break

        # kullanıcıya açılabilir butonlu zengin bildirim
        try:
            from PyQt6.QtWidgets import QMessageBox
            box = QMessageBox()
            box.setWindowTitle('Hata Günlüğü')
            box.setIcon(QMessageBox.Icon.Critical)
            box.setText(f'Bir çalışma zamanı hatası oluştu.\nGünlük dosyası kaydedildi: {log_name}')
            box.setInformativeText(f'Konum:\n{user_visible_file}')

            btn_folder = box.addButton("📁 Klasörü Aç", QMessageBox.ButtonRole.ActionRole)
            btn_file = box.addButton("📄 Logu Aç", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Tamam", QMessageBox.ButtonRole.AcceptRole)

            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_folder:
                if sys.platform == "darwin":
                    subprocess.run(["open", "-R", user_visible_file], check=False)
                elif sys.platform == "win32":
                    subprocess.run(f'explorer /select,"{os.path.abspath(user_visible_file)}"', shell=True)
                else:
                    subprocess.run(["xdg-open", os.path.dirname(user_visible_file)], check=False)
            elif clicked == btn_file:
                if sys.platform == "darwin":
                    subprocess.run(["open", user_visible_file], check=False)
                elif sys.platform == "win32":
                    os.startfile(user_visible_file)
                else:
                    subprocess.run(["xdg-open", user_visible_file], check=False)
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
