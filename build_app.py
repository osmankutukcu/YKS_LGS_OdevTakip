import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def clean_build():
    """Build klasörlerini temizle."""
    dirs = ["build", "dist"]
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
    print("🧹 Temizlik yapıldı.")

def ensure_dependencies():
    """Derleme için gereken tüm bağımlılıkların yüklü olduğundan emin ol."""
    needed = ["PyQt6", "PyInstaller"]
    missing = []
    for mod in needed:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    
    if missing:
        print(f"⚠️ Eksik derleme bağımlılıkları tespit edildi: {', '.join(missing)}")
        print("📦 Gerekli paketler derleme ortamına otomatik kuruluyor...")
        req_file = "requirements_win.txt" if platform.system() == "Windows" else "requirements.txt"
        if os.path.exists(req_file):
            cmd = [sys.executable, "-m", "pip", "install", "-r", req_file]
        else:
            cmd = [sys.executable, "-m", "pip", "install"] + missing
        try:
            subprocess.check_call(cmd)
            print("✅ Bağımlılıklar başarıyla kuruldu.\n")
        except Exception as e:
            print(f"⚠️ Paket kurulumu sırasında hata: {e}")

def run_build():
    """Mevcut işletim sistemine göre PyInstaller'ı çalıştır."""
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

    print(f"🚀 Komut çalıştırılıyor:\n{' '.join(args)}\n")
    subprocess.check_call(args)
    print("\n✅ Build Tamamlandı!")
    print(f"📂 Çıktı konumu: {os.path.abspath('dist')}")

if __name__ == "__main__":
    clean_build()
    run_build()
