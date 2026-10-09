import os
import shutil
import subprocess
import sys
from pathlib import Path

def create_dmg():
    app_name = "OdevTakip_v2"
    app_path = Path("dist") / f"{app_name}.app"
    dmg_name = f"{app_name}_Installer.dmg"
    dmg_path = Path("dist") / dmg_name
    
    if not app_path.exists():
        print(f"❌ Hata: {app_path} bulunamadı. Önce build alın.")
        return

    print("💿 DMG Oluşturuluyor...")
    
    # Geçici klasör
    tmp_dir = Path("dist/dmg_tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    
    # 1. App'i kopyala
    print(f"   Kopyalanıyor: {app_path.name}")
    shutil.copytree(app_path, tmp_dir / app_path.name)
    
    # 2. Applications kısayolu
    print("   Applications kısayolu oluşturuluyor...")
    os.symlink("/Applications", tmp_dir / "Applications")
    
    # 3. Varsa eski DMG'yi sil
    if dmg_path.exists():
        dmg_path.unlink()
        
    # 4. hdiutil çalıştır
    print("   Disk imajı paketleniyor (hdiutil)...")
    cmd = [
        "hdiutil", "create",
        "-volname", "YKS-LGS Odev Takip Kurulum",
        "-srcfolder", str(tmp_dir),
        "-ov", 
        "-format", "UDZO",
        str(dmg_path)
    ]
    
    subprocess.check_call(cmd)
    
    # 5. Temizlik
    shutil.rmtree(tmp_dir)
    
    print(f"\n✅ DMG Hazır: {dmg_path.resolve()}")

if __name__ == "__main__":
    create_dmg()
