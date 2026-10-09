# -*- coding: utf-8 -*-
import os
import shutil
import datetime
import zipfile
from PyQt6.QtCore import QObject, pyqtSignal
from utils import settings as appset

class BackupManager(QObject):
    """
    Yedekleme işlemlerini yönetir.
    Google Drive / OneDrive masaüstü klasörüne otomatik zip atar.
    """
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self):
        super().__init__()
        # Ana veritabanı ve olası ek ayar dosyaları
        self.db_files = ["YKS_LGS_HomeworkManager.db", "settings.db", "data.db"]
        
    def get_backup_path(self):
        return appset.ayar_get("yedek_konumu", "")

    def set_backup_path(self, path):
        appset.ayar_set("yedek_konumu", path)

    def is_auto_backup(self):
        return str(appset.ayar_get("yedek_oto", "false")).lower() == "true"

    def set_auto_backup(self, val: bool):
        appset.ayar_set("yedek_oto", "true" if val else "false")

    def create_backup(self, target_dir=None):
        """
        Veritabanlarını zipler ve hedef klasöre kopyalar.
        target_dir verilmezse ayarlardaki konumu kullanır.
        """
        try:
            dest = target_dir if target_dir else self.get_backup_path()
            if not dest or not os.path.isdir(dest):
                return False, "Geçerli bir yedekleme klasörü seçilmemiş."

            # Dosya adı: YKS_Yedek_2025-10-27_14-30.zip
            now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            zip_name = f"YKS_Yedek_{now_str}.zip"
            zip_path = os.path.join(dest, zip_name)

            # Geçici bir zip oluştur
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for db_file in self.db_files:
                    if os.path.exists(db_file):
                        zf.write(db_file)
            
            # Eski yedekleri temizle (Opsiyonel: Son 5 yedeği tut)
            self._cleanup_old_backups(dest)
            
            return True, f"Yedek başarıyla oluşturuldu:\n{zip_path}"
        except Exception as e:
            return False, str(e)

    def _cleanup_old_backups(self, folder):
        """Klasördeki eski yedekleri (5 taneden fazlaysa) sil."""
        try:
            files = []
            for f in os.listdir(folder):
                if f.startswith("YKS_Yedek_") and f.endswith(".zip"):
                    full = os.path.join(folder, f)
                    files.append(full)
            
            # Tarihe göre sırala (yeni en sonda)
            files.sort(key=os.path.getmtime)
            
            # Son 10 taneyi tut, gerisini sil
            while len(files) > 10:
                os.remove(files[0])
                files.pop(0)
        except:
            pass
