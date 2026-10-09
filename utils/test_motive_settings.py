# -*- coding: utf-8 -*-
# test_motive_settings.py
from __future__ import annotations
import sys, os, argparse, time

# Proje kökünden çalıştığından emin ol (gerekliyse düzenle)
# sys.path.append(os.path.abspath("."))

# Uygulamanın ayar arabirimi
from utils import settings as appset

# Motivasyon API (tek dosya)
from ui.motivation_toast import (
    celebrate_saved,    # mevcut (kaydedilmiş) ayarlarla kutlama
    save_settings,      # ayarları kalıcı kaydet
    load_settings,      # ayarları oku (dict döndürür — yoksa defaults)
)

# ---- Ayar anahtarları ve örnek değerler ----
KEYS = [
    "motive_mesaj",
    "motive_renk",
    "motive_sure",
    "motive_font",
    "motive_ses_yolu",
    "motive_ses_seviyesi",
    "motive_confetti",
    "motive_auto_when_100",
    "motive_style",
]

SAMPLE = dict(
    message="Test: Harika, hepsi tamam! 🎉",
    color="#10b981",
    duration=2200,
    font=20,
    sound_path="",           # boş bırak -> ses kapalı (wav yoksa dert olmasın)
    sound_volume=0.2,
    confetti=80,
    auto_when_100=True,
    style="zoom_fade",       # veya "flat_fade" (senin dosyada hangileri varsa)
)

def _print_possible_paths():
    print("\n--- settings modülünde ‘path’ içerikli öznitelikler ---")
    paths = [a for a in dir(appset) if "path" in a.lower()]
    if not paths:
        print("(bulunamadı) -> appset içinden ayar dosyası yolu açıkça verilmiyor olabilir.")
        return
    for a in paths:
        try:
            print(f"{a} =", getattr(appset, a))
        except Exception as e:
            print(f"{a} okunamadı: {e!r}")

def dump():
    """motive_* anahtarlarının tamamını yazdır."""
    print("\n=== DUMP (motive_* anahtarları) ===")
    for k in KEYS:
        try:
            v = appset.ayar_get(k, None)
        except Exception as e:
            v = f"<ERROR: {e!r}>"
        print(f"{k:>22s} = {repr(v)}")
    print("===================================")
    _print_possible_paths()

def write_sample():
    """Örnek ayarları kaydet ve ekrana dök."""
    print("\n>>> ÖRNEK AYARLAR KAYDEDİLİYOR…")
    save_settings(SAMPLE)
    print(">>> KAYDEDİLDİ. Okunan değerler:")
    dump()

def clear_keys():
    """motive_* anahtarlarını temizle/boşalt (ayar_del varsa onu kullan)."""
    print("\n>>> motive_* anahtarları temizleniyor…")
    ayar_del = getattr(appset, "ayar_del", None)
    for k in KEYS:
        try:
            if ayar_del:
                ayar_del(k)
            else:
                # del yoksa boş/None yazarak etkisizleştir
                appset.ayar_set(k, None)
        except Exception as e:
            print(f"- {k} silinemedi: {e!r}")
    print(">>> Temizlik bitti.")
    dump()

def set_key(key: str, value: str):
    """Tek bir anahtarı set et (string veriyorsun; sayısal gerekiyorsa parse et)."""
    if key not in KEYS:
        print(f"Uyarı: {key} motive_* listesinde yok. Yine de yazılıyor…")
    # basit parse: int/float/bool yakala
    v = value
    if value.isdigit():
        v = int(value)
    else:
        try:
            v = float(value)
        except Exception:
            low = value.strip().lower()
            if low in ("true","false"):
                v = (low == "true")
    appset.ayar_set(key, v)
    print(f">>> {key} = {repr(v)} kaydedildi.")
    dump()

def preview():
    """Kaydedilmiş ayarlarla görsel test (toast + confetti + ses)."""
    try:
        from PyQt6.QtWidgets import QApplication, QWidget
    except Exception as e:
        print("PyQt6 bulunamadı veya GUI açılamadı:", e)
        return
    print("\n>>> Önizleme başlıyor (kapatmak için pencereyi kapat)…")

    app = QApplication.instance() or QApplication(sys.argv)
    host = QWidget()
    host.setWindowTitle("Preview Host")
    host.resize(720, 480)
    host.show()

    # Kaydedilmiş ayarları da konsola bas
    print(">>> load_settings():", load_settings())

    # Görsel tetikleyelim (mevcut ayarlarla)
    celebrate_saved(host)

    app.exec()

def main(argv=None):
    ap = argparse.ArgumentParser(description="motive_* ayarlarını test/teşhis aracı")
    ap.add_argument("--dump", action="store_true", help="Sadece motive_* anahtarlarını yazdır")
    ap.add_argument("--write-sample", action="store_true", help="Örnek ayarları kaydet (SAMPLE) ve yazdır")
    ap.add_argument("--clear", action="store_true", help="motive_* anahtarlarını temizle")
    ap.add_argument("--set", nargs=2, metavar=("KEY","VALUE"), help="Tek bir anahtarı yaz (örn: --set motive_sure 2500)")
    ap.add_argument("--preview", action="store_true", help="Kaydedilmiş ayarlarla GUI önizleme yap")
    args = ap.parse_args(argv)

    if not any([args.dump, args.write_sample, args.clear, args.set, args.preview]):
        ap.print_help()
        print("\nÖrnekler:")
        print("  python test_motive_settings.py --dump")
        print("  python test_motive_settings.py --write-sample")
        print("  python test_motive_settings.py --set motive_mesaj 'Bravo! 🎯'")
        print("  python test_motive_settings.py --preview")
        print("  python test_motive_settings.py --clear")
        return 0

    if args.dump:
        dump()
    if args.write_sample:
        write_sample()
    if args.set:
        set_key(args.set[0], args.set[1])
    if args.preview:
        preview()
    if args.clear:
        clear_keys()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())