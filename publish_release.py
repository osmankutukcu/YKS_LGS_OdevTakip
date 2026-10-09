# -*- coding: utf-8 -*-
"""
YKS/LGS Ödev & Takip Yöneticisi - Geliştirici Sürüm Yayınlama Aracı (Publish Release)
Bu araç:
1. Sürüm numarasını ve sürüm notlarını günceller (version.py).
2. Kullanıcı veritabanlarını (.db, .sqlite) ve özel lisans dosyalarını KESİNLİKLE hariç tutarak
   temiz bir 'OdevTakip_vX.X.X_Update.zip' güncelleme paketi üretir.
3. 'version.json' üstveri dosyasını oluşturur.
4. GitHub Releases için hazır yükleme dosyalarını 'dist_release/' klasörüne koyar.
"""

import os
import sys
import json
import hashlib
import zipfile
import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import version

EXCLUDE_DIRS = {
    ".venv", ".venv_old", ".venv_old_2", ".git", ".idea", ".cache",
    "__pycache__", "build", "logs", "scratch", "dist_release",
    "backups", "temp", "tmp"
}

EXCLUDE_EXTS = {
    ".zip", ".pyc", ".DS_Store", ".spec", ".log", ".tmp",
    ".db", ".sqlite", ".sqlite3", ".lic", ".key"
}

EXCLUDE_FILES = {
    "admin_keygen.py",
    "YKS_LGS_Lisans_Uretici.py",
    "YKS_LGS_Lisans_Uretici.spec",
    "Lisans_Uretici.bat",
    "Lisans_Uretici.vbs",
    "Lisans_Uretici_EXE_Yap.bat",
    "license.json",
    "config.json",
    "YKS_LGS_HomeworkManager.db",
    "YKS_LGS_HomeworkManager v2.db",
    "YKS_Kazanimlar.sqlite",
    "database.db",
    "data.db",
    "settings.db",
    "deneme_history.db",
    "ozel_ders.db",
    "veritabani.db"
}

CRLF_EXTS = {".bat", ".cmd", ".vbs", ".iss", ".txt", ".md", ".json"}


def calculate_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def update_version_file(new_ver: str):
    v_path = os.path.join(PROJECT_ROOT, "version.py")
    with open(v_path, "r", encoding="utf-8") as f:
        content = f.read()

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    import re
    content = re.sub(r'APP_VERSION\s*=\s*["\'].*?["\']', f'APP_VERSION = "{new_ver}"', content)
    content = re.sub(r'APP_BUILD_DATE\s*=\s*["\'].*?["\']', f'APP_BUILD_DATE = "{today_str}"', content)

    with open(v_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ version.py güncellendi -> v{new_ver} ({today_str})")


def create_release_package(new_ver: str, notes: str) -> str:
    dist_dir = os.path.join(PROJECT_ROOT, "dist_release")
    os.makedirs(dist_dir, exist_ok=True)

    zip_filename = f"OdevTakip_v{new_ver}_Update.zip"
    zip_path = os.path.join(dist_dir, zip_filename)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    # Paketleme kaynağını belirle: dist/OdevTakip_v2 mi yoksa Proje Kökü mü?
    compiled_dir = os.path.join(PROJECT_ROOT, "dist", "OdevTakip_v2")
    has_compiled = os.path.isdir(compiled_dir) and os.path.exists(os.path.join(compiled_dir, "OdevTakip_v2.exe"))

    mode = "source"
    if has_compiled:
        print("\n🔎 Derlenmiş Windows EXE klasörü tespit edildi (dist/OdevTakip_v2).")
        print("   Bu klasördeki en güncel EXE ve kütüphaneler paketlenecektir.")
        mode = "compiled"
    else:
        print("\nℹ️ Kaynak kod dizininden paketleme yapılıyor.")

    print(f"📦 Temiz güncelleme paketi hazırlanıyor: {zip_filename}...")
    file_count = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if mode == "compiled":
            # Derlenmiş dist/OdevTakip_v2 klasöründeki dosyaları paketle
            for root, dirs, files in os.walk(compiled_dir):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

                for f in files:
                    if f in EXCLUDE_FILES or f.startswith("."):
                        continue
                    _, ext = os.path.splitext(f)
                    if ext.lower() in EXCLUDE_EXTS:
                        continue

                    abs_path = os.path.join(root, f)
                    rel_path = os.path.relpath(abs_path, compiled_dir)

                    zf.write(abs_path, rel_path)
                    file_count += 1

        else:
            # Kaynak kod kök klasöründen paketle
            for root, dirs, files in os.walk(PROJECT_ROOT):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".venv") and d != "dist"]:
                    pass

                for f in files:
                    if f in EXCLUDE_FILES or f.startswith("."):
                        continue
                    _, ext = os.path.splitext(f)
                    if ext.lower() in EXCLUDE_EXTS:
                        continue

                    abs_path = os.path.join(root, f)
                    rel_path = os.path.relpath(abs_path, PROJECT_ROOT)

                    # Windows CRLF dönüşümü
                    if ext.lower() in CRLF_EXTS:
                        try:
                            with open(abs_path, "rb") as fp:
                                raw = fp.read()
                            text = raw.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\n", "\r\n")
                            zf.writestr(rel_path, text.encode("utf-8"))
                            file_count += 1
                            continue
                        except Exception:
                            pass

                    zf.write(abs_path, rel_path)
                    file_count += 1

    file_size = os.path.getsize(zip_path)
    sha256 = calculate_sha256(zip_path)

    print(f"✅ Güncelleme arşivi oluşturuldu! (Toplam {file_count} dosya, {file_size / (1024*1024):.2f} MB)")

    # version.json oluştur
    repo = version.GITHUB_REPO
    version_data = {
        "version": new_ver,
        "name": f"v{new_ver} Güncellemesi",
        "changelog": notes,
        "download_url": f"https://github.com/{repo}/releases/download/v{new_ver}/{zip_filename}",
        "file_size": file_size,
        "sha256": sha256,
        "published_at": datetime.date.today().strftime("%Y-%m-%d")
    }

    v_json_path = os.path.join(dist_dir, "version.json")
    with open(v_json_path, "w", encoding="utf-8") as f:
        json.dump(version_data, f, indent=4, ensure_ascii=False)

    # Proje kökündeki version.json dosyasını da güncelle (GitHub repo ana dizininde durması için)
    root_v_json = os.path.join(PROJECT_ROOT, "version.json")
    with open(root_v_json, "w", encoding="utf-8") as f:
        json.dump(version_data, f, indent=4, ensure_ascii=False)

    print(f"✅ version.json oluşturuldu: {v_json_path}")
    print(f"✅ Kök version.json güncellendi: {root_v_json}")
    return zip_path


def main():
    print("=" * 65)
    print("   YKS/LGS Ödev & Takip Yöneticisi - Sürüm Yayınlama Aracı")
    print("=" * 65)

    cur_ver = version.APP_VERSION
    print(f"Mevcut Sürüm: v{cur_ver}")

    if len(sys.argv) > 1:
        new_ver = sys.argv[1].lstrip("vV")
    else:
        new_ver = input(f"Yeni Sürüm Numarasını Girin (Örn: 3.6.0): ").strip().lstrip("vV")

    if not new_ver:
        print("❌ Sürüm numarası boş bırakılamaz.")
        return

    if not version.is_newer_version(new_ver, cur_ver):
        print(f"⚠️ Uyarı: Yeni sürüm ({new_ver}), mevcut sürümden ({cur_ver}) daha büyük değil!")
        ans = input("Yine de devam edilsin mi? (e/h): ").strip().lower()
        if ans != "e":
            return

    if len(sys.argv) > 2:
        notes = sys.argv[2]
    else:
        print("\nSürüm Değişiklik Notlarını (Changelog) Girin (Bitirmek için boş satırda Enter):")
        lines = []
        while True:
            try:
                line = input()
                if not line and lines:
                    break
                lines.append(line)
            except EOFError:
                break
        notes = "\n".join(lines) if lines else f"v{new_ver} kararlılık ve özellik güncellemeleri."

    # 1. version.py güncelle
    update_version_file(new_ver)

    # 2. Paketi oluştur
    pkg_path = create_release_package(new_ver, notes)

    print("\n" + "=" * 65)
    print(f"🎉 SÜRÜM v{new_ver} BAŞARIYLA PAKETLENDİ!")
    print("=" * 65)
    print(f"1. Paket Dosyası: {pkg_path}")
    print(f"2. Üstveri (version.json): {os.path.join(PROJECT_ROOT, 'version.json')}")
    print("\n📋 GİTHUB'A YÜKLEME ADIMLARI:")
    print(f"  • GitHub Deponuz: https://github.com/{version.GITHUB_REPO}/releases")
    print(f"  • 'Draft a new release' butonuna tıklayın.")
    print(f"  • Tag version: v{new_ver}")
    print(f"  • Release title: v{new_ver} Güncellemesi")
    print(f"  • Açıklamaya sürüm notlarınızı yapıştırın.")
    print(f"  • '{os.path.basename(pkg_path)}' dosyasını sürükleyip bırakın.")
    print(f"  • 'Publish release' butonuna basarak yayınlayın!")
    print("=" * 65)


if __name__ == "__main__":
    main()
