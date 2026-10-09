
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
            shutil.rmtree(d)
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
    system = platform.system()
    sep = os.pathsep
    
    app_name = "OdevTakip_v2"
    main_script = "app.py"
    
    # Ortak parametreler
    # --noconsole: Konsol penceresi açılmasın
    # --onefile: Tek dosya (exe) olsun (Mac için app bundle daha iyi ama onefile da olur, biz app bundle yapacagiz mac için -w yetiyor)
    # --name: Çıktı adı
    
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # Konsol yok
        f"--name={app_name}",
        
        # Veri dosyaları: src:dest (Windows için ';' Mac/Linux için ':')
        f"--add-data=assets{sep}assets",
        f"--add-data=themes{sep}themes",
        f"--add-data=ui{sep}ui",
        f"--add-data=utils{sep}utils",
        f"--add-data=seed{sep}seed",
        f"--add-data=services{sep}services",
        f"--add-data=web_api{sep}web_api",
        f"--add-data=YKS_LGS_HomeworkManager.db{sep}.",
        
        # Gerekli importlar
        "--hidden-import=sqlite3",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtPrintSupport",
        "--hidden-import=openpyxl",
        "--hidden-import=pandas",
        "--hidden-import=pyautogui",
        "--hidden-import=reportlab",
        "--hidden-import=fastapi",
        "--hidden-import=uvicorn",
        "--hidden-import=pydantic",
        "--hidden-import=multipart",
        "--hidden-import=certifi",
        
        # Gerekli veri paketleri
        "--collect-all=certifi",
    ]

    if os.path.exists("fonts"):
        args.append(f"--add-data=fonts{sep}fonts")

    # OS Spesifik Ayarlar
    if system == "Darwin":  # macOS
        print("🍎 macOS Build Algılandı...")
        icon = "assets/app.icns"
        if os.path.exists(icon):
            args.append(f"--icon={icon}")
        else:
            print("⚠️ Uyarı: assets/app.icns bulunamadı.")
            
        # Mac için --onefile yerine klasör veya .app paketi daha standarttır ama 
        # PyInstaller --windowed ile otomatik .app yapar dist içinde.
        # Biz yine de tek dosya mantığı ekleyebiliriz ama .app daha iyi.
        # --onedir varsayılan.
        
    elif system == "Windows":
        print("🪟 Windows Build Algılandı...")
        # icon.ico arayalım, yoksa png deneyelim (uyarı verir)
        icon = "assets/app_icon.ico"
        if not os.path.exists(icon):
            # Basit png varsa onu .ico gibi verelim ama user convert etmeli
            icon = "assets/app_icon.png"
            print("⚠️ Uyarı: app_icon.ico bulunamadı, png kullanılıyor. Exe simgesi için .ico önerilir.")
        
        args.append(f"--icon={icon}")
    
    else:
        print(f"🐧 Linux veya Diğer ({system}) Build...")

    # Ana çalıştırıcı script
    args.append(main_script)

    print(f"🚀 Komut çalıştırılıyor:\n{' '.join(args)}\n")
    subprocess.check_call(args)

    print("\n✅ Build Tamamlandı!")
    print(f"📂 Çıktı konumu: {os.path.abspath('dist')}")

if __name__ == "__main__":
    clean_build()
    run_build()
