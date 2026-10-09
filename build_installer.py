import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def main():
    system = platform.system()
    print(f"🚀 {system} için Installer Süreci Başlatılıyor...\n")

    # 1. Önce Build Al
    print("--- 1. build_app.py Çalıştırılıyor ---")
    ret = subprocess.call([sys.executable, "build_app.py"])
    if ret != 0:
        print("❌ Build başarısız oldu. Installer oluşturulmadı.")
        return

    # 1.5. macOS Code Signing Check (Segfault Fix)
    if system == "Darwin":
        app_path = "dist/OdevTakip_v2.app"
        if os.path.exists(app_path):
            print("🔏 App İmzalanıyor (Ad-hoc signing)...")
            subprocess.call(["codesign", "--force", "--deep", "-s", "-", app_path])

    # 2. Installer Oluştur
    print("\n--- 2. Installer Hazırlanıyor ---")
    if system == "Darwin":
        # macOS: DMG Oluştur
        if not os.path.exists("create_dmg.py"):
             print("❌ create_dmg.py bulunamadı.")
             return
             
        ret = subprocess.call([sys.executable, "create_dmg.py"])
        if ret == 0:
            print("\n🎉 İŞLEM TAMAMLANDI!")
            print(f"📂 Kurulum Dosyası: {Path('dist').resolve()}/OdevTakip_v2_Installer.dmg")
        else:
            print("❌ DMG oluşturma hatası.")

    elif system == "Windows":
        iss_path = Path("setup.iss").resolve()
        
        # Inno Setup Compiler otomatik arama
        iscc = shutil.which("iscc") or shutil.which("ISCC")
        if not iscc:
            common_paths = [
                Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
                Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
                Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
            ]
            for cp in common_paths:
                if cp.exists():
                    iscc = str(cp)
                    break
        
        if iscc:
            print(f"📦 Inno Setup Compiler bulundu: {iscc}")
            print(f"⚙️ '{iss_path.name}' derleniyor...")
            ret = subprocess.call([iscc, str(iss_path)])
            if ret == 0:
                print("\n🎉 WINDOWS KURULUM DOSYASI (.exe) BAŞARIYLA OLUŞTURULDU!")
                print(f"📂 Konum: {Path('dist').resolve()}\\OdevTakip_v2_Kurulum.exe")
                return
            else:
                print("⚠️ ISCC derleme sırasında hata verdi. Manuel derleme yapabilirsiniz.")

        print(f"""
✅ Build tamamlandı. Installer (.exe) oluşturmak için:

1. "Inno Setup Compiler" programını indirin ve kurun: https://jrsoftware.org/isdl.php
2. Proje klasöründeki '{iss_path.name}' dosyasına çift tıklayın (veya sağ tıklayıp Compile deyin).
3. Inno Setup içinde 'Build' > 'Compile' butonuna basın.

Çıktı dosyası (Setup Exe) `dist` klasörüne (OdevTakip_v2_Kurulum.exe) oluşturulacaktır.
        """)
        
    else:
        print("🐧 Linux veya diğer sistemler için otomatik installer desteği yok.")

if __name__ == "__main__":
    main()
