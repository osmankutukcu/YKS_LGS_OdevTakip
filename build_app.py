import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def clean_build():
    """Build klasorlerini temizle."""
    dirs = ["build", "dist"]
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
    print("[OK] Temizlik yapildi.")

def ensure_dependencies():
    """Derleme icin gereken tum bagimliliklarin yuklu oldugundan emin ol."""
    needed = ["PyQt6", "PyInstaller"]
    missing = []
    for mod in needed:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    
    if missing:
        print(f"[UYARI] Eksik derleme bagimliliklari: {', '.join(missing)}")
        print("[BILGI] Paketler kuruluyor...")
        req_file = "requirements_win.txt" if platform.system() == "Windows" else "requirements.txt"
        if os.path.exists(req_file):
            cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
        else:
            cmd = [sys.executable, "-m", "pip", "install"] + missing
        try:
            subprocess.check_call(cmd)
            print("[OK] Bagimliliklar basariyla kuruldu.\n")
        except Exception as e:
            print(f"[HATA] Paket kurulumu hatasi: {e}")

def run_build():
    """Mevcut isletim sistemine gore PyInstaller'i calistir."""
    ensure_dependencies()
    
    spec_file = "OdevTakip_v2.spec"
    if os.path.exists(spec_file):
        args = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            spec_file
        ]
    else:
        args = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--name=OdevTakip_v2",
            "app.py"
        ]

    print(f"[BILGI] Komut calistiriliyor:\n{' '.join(args)}\n")
    subprocess.check_call(args)
    print("\n[OK] Build Tamamlandi!")
    print(f"[BILGI] Cikti konumu: {os.path.abspath('dist')}")

if __name__ == "__main__":
    clean_build()
    run_build()
