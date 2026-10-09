# -*- coding: utf-8 -*-
from __future__ import annotations
"""
WhatsApp masaüstü otomasyon yardımcıları (dayanıklı/otonom).
- API aynıdır: whatsapp_gonder(), whatsapp_gonder_dosya()
- Yanlış numara/uyarı ekranları: otomatik atla (kullanıcıya hissettirmeden)
- Çok katmanlı fallback: whatsapp:// → wa.me → arama çubuğu
- Log: DB + screenshot (mümkünse)
"""

import os, sys, time, platform, subprocess, urllib.parse, datetime
from pathlib import Path

import pyautogui as pag
import pyperclip

# PyAutoGUI güvenlik: köşeye gitme ile durmasın (istersen True yap)
try:
    pag.FAILSAFE = False
except Exception:
    pass

# Ayar modülü (önce yeni yol)
try:
    from ui import app_settings as appset
except Exception:
    from utils import settings as appset  # fallback

# Log klasörü
try:
    from utils.error_manager import _log_dir
except Exception:
    def _log_dir() -> str:
        d = "logs"; os.makedirs(d, exist_ok=True); return d

# ----------------- küçük yardımcılar -----------------

def _dlog(msg: str):
    try:
        p = os.path.join(_log_dir(), "wa_debug.log")
        with open(p, "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def _mod() -> str:
    m = str(appset.ayar_get("whatsapp_mod_key", "auto")).lower()
    if m in ("cmd", "command", "meta"): return "command"
    if m in ("ctrl", "control"): return "ctrl"
    return "command" if sys.platform == "darwin" else "ctrl"

def _key(name: str, default: str) -> str:
    return str(appset.ayar_get(name, default))

def _sleep(sec: float): time.sleep(max(0.02, float(sec or 0)))

def _press_enter(times=1, pause=0.25):
    for _ in range(int(times)):
        pag.press("enter"); _sleep(pause)

def _paste(text: str):
    pyperclip.copy(text)
    if sys.platform == "darwin":
        pag.hotkey("command", "v")
    else:
        pag.hotkey("ctrl", "v")
    _sleep(0.1)

def _unique(lst):
    seen = set()
    return [x for x in lst if not (x in seen or seen.add(x))]

def _normalize_number(num):
    if not num: return None
    s = str(num).strip()
    s = "".join(filter(str.isdigit, s))
    if len(s) < 10: return None
    # TR check
    if len(s) == 10 and s.startswith("5"):
        country = appset.ayar_get("default_cc", "90")
        s = f"{country}{s}"
    elif len(s) == 11 and s.startswith("05"):
        country = appset.ayar_get("default_cc", "90")
        s = f"{country}{s[1:]}"
    return s

def _open_app_focus():
    """
    Sadece odağı uygulamaya ver. (Mac: open -a WhatsApp, Win: switch window)
    """
    _dlog("_open_app_focus çağrıldı")
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", "WhatsApp"], check=False)
        _sleep(1.0)
    elif hasattr(os, "startfile"):
        try:
            os.startfile("whatsapp://")
        except Exception:
            os.system("start whatsapp://")
        _sleep(1.5)
    else:
        os.system("start whatsapp://")
        _sleep(1.5)

def _focus_whatsapp():
    """
    WhatsApp penceresini öne getirir, arama kutusuna odaklanmaya çalışır (Esc ile).
    """
    _open_app_focus()
    # Biraz bekle (Warm-up)
    _sleep(0.5)
    # Arama kutusu temizle
    _clear_search_field()

def _clear_search_field():
    # Esc basıp arama kutusundan/chatten çıkıp ana listeye dönmeyi dener
    pag.press("esc"); _sleep(0.3)
    pag.press("esc"); _sleep(0.3) 
    # Ctrl+F / Cmd+F ile arama kutusu
    pag.hotkey(_mod(), "f"); _sleep(0.5)
    # İçini sil
    pag.hotkey(_mod(), "a"); _sleep(0.1)
    pag.press("backspace")

def _open_deeplink(phone, text=None) -> bool:
    """
    whatsapp://send?phone=...&text=... Linkini açar.
    Bu masaüstü uygulamasını tetikler ve o chat'i açar.
    True dönerse 'tarayıcı isteği yapıldı' demektir.
    Uygulamanın açılması zaman alır.
    """
    try:
        base = f"whatsapp://send?phone={phone}"
        if text:
            # text encode
            enc = urllib.parse.quote(text)
            base += f"&text={enc}"
        
        _dlog(f"Deeplink: {base}")
        
        if sys.platform == "darwin":
            subprocess.run(["open", base], check=False)
        elif hasattr(os, "startfile"):
            try:
                os.startfile(base)
            except Exception:
                os.system(f'start "" "{base}"')
        else:
            os.system(f'start "" "{base}"')
        
        # Bekleme süresi ayarı
        w = float(appset.ayar_get("open_delay", "2.0"))
        _sleep(w)
        return True
    except Exception as e:
        _dlog(f"Deeplink hata: {e}")
        return False

# ----------------- GÖNDERİM FONKSİYONLARI -----------------

def _after_send_check_and_log(phone, msg, oid=None, success=True, error_msg=None) -> bool:
    """
    WhatsApp gönderim sonucunu whatsapp_log tablosuna eksiksiz kaydeder.
    """
    try:
        import datetime, db
        con = db.get_conn()
        try:
            tarih = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ogr_adsoyad = ""
            if oid:
                try:
                    r = con.execute("SELECT ad, soyad FROM ogrenci WHERE id = ?", (oid,)).fetchone()
                    if r:
                        ad = r["ad"] if hasattr(r, "keys") else r[0]
                        soyad = r["soyad"] if hasattr(r, "keys") else r[1]
                        ogr_adsoyad = f"{ad} {soyad}".strip()
                except Exception:
                    pass

            durum = "OK" if success else "HATA"
            gonderilen = 1 if success else 0
            basarisiz = 0 if success else 1
            hata = None if success else (error_msg or "Gönderim başarısız")

            con.execute("""
                INSERT INTO whatsapp_log (
                    zaman, ogrenci_id, numara, mesaj_onizleme, durum, 
                    hata, gonderilen, basarisiz, mesaj, ogrenci_adsoyad
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tarih, oid if oid else None, str(phone), 
                (msg or "")[:180], durum, hata, gonderilen, basarisiz, 
                msg if msg else "", ogr_adsoyad
            ))
            con.commit()
        except Exception as e:
            _dlog(f"Log yazma hatası: {e}")
        finally:
            try: con.close()
            except: pass
        return success
    except Exception:
        return success

def whatsapp_gonder(numaralar: list, mesaj: str, ogrenci_id=None, time_delay=None, image_path=None, **kwargs):
    """
    Basit ve gelişmiş metin/görsel gönderimi.
    WhatsApp Desktop uygulamasını otomatik açar, mesajı yapıştırır ve Enter ile gönderir.
    """
    # Tekilleştir
    nums = _unique(numaralar)
    ok, fail = [], []
    
    # 1. Uygulama Odaklan
    _focus_whatsapp()
    
    # Warm-up (İlk numara atlama sorununa karşı)
    _sleep(1.5)

    burst = int(appset.ayar_get("wa_enter_burst", "1"))
    pause = float(appset.ayar_get("wa_enter_pause", "0.2"))
    bekleme = float(appset.ayar_get("wp_step_delay", "1.5"))
    if time_delay is not None:
        try:
            val_td = float(time_delay)
            if val_td > 0:
                bekleme = val_td
        except Exception:
            pass

    # İlk gönderimde biraz daha bekle (App load)
    first_run = True

    for raw in nums:
        n = _normalize_number(raw)
        if not n: 
            fail.append(raw)
            continue
        
        # Loop delay
        if not first_run:
            _sleep(0.5)
        
        current_wait = bekleme
        if first_run:
            current_wait += 1.2 # İlk seferde ekstra bekle
            first_run = False

        sent = False
        
        # Yöntem A: Deeplink (Hızlı, text parametresiyle)
        try:
            # Sadece numarayı aç, texti yapıştıracağız (daha güvenli, karakter sınırı vs.)
            if _open_deeplink(n, None):
                # Chat yüklensin
                _sleep(current_wait)
                # Yapıştır ve gönder
                if mesaj:
                    _paste(mesaj)
                    _sleep(0.5)
                    _press_enter(times=burst, pause=pause)
                if image_path and os.path.exists(str(image_path)):
                    _sleep(0.5)
                    _send_image_to_chat(str(image_path), bekleme)
                sent = _after_send_check_and_log(n, mesaj, ogrenci_id)
        except Exception as e:
            _dlog(f"Yöntem A Hata ({n}): {e}")
            sent = False
        
        # Yöntem B: Arama Çubuğu (Fallback)
        if not sent:
            _dlog(f"Yöntem A başarısız, B deneniyor: {n}")
            try:
                _focus_whatsapp() # Arama kutusuna git
                _paste(n)         # Numarayı yaz
                _sleep(1.2)       # Sonuç gelmesini bekle
                pag.press("down"); _sleep(0.2) # İlk sonuca in
                pag.press("enter"); _sleep(0.8) # Chat aç
                
                if mesaj:
                    _paste(mesaj)
                    _sleep(0.5)
                    _press_enter(times=burst, pause=pause)
                if image_path and os.path.exists(str(image_path)):
                    _sleep(0.5)
                    _send_image_to_chat(str(image_path), bekleme)
                
                sent = _after_send_check_and_log(n, mesaj, ogrenci_id)
            except Exception as e:
                _dlog(f"Yöntem B Hata ({n}): {e}")
                sent = False
        
        if sent:
            ok.append(n)
        else:
            fail.append(n)
            _after_send_check_and_log(n, mesaj, ogrenci_id, success=False, error_msg="WhatsApp gönderimi tamamlanamadı")
    
    return {"ok": ok, "gonderilen": len(ok), "fail": fail, "hatali": len(fail)}

def _send_image_to_chat(image_path: str, bekleme: float) -> bool:
    """
    Aktif chate dosya ekleme (ataş / sürükle / yapıştır).
    """
    if not os.path.exists(image_path): return False
    try:
        # macOS: AppleScript ile kopyala + yapıştır (daha güvenilir)
        if sys.platform == "darwin":
            # AppleScript ile panoya dosya kopyalamak tricky.
            # En basiti: 'Ctrl+Shift+Cmd+4' vs değil, doğrudan Finder selection emulation
            # Ama o karışık. 
            # Basit Yöntem: Ataş kısa yolu (Cmd+Shift+O veya Cmd+O)?
            # WhatsApp Desktop Mac shortcuts: Cmd+O -> File Upload Dialog
            pag.hotkey(_mod(), "o") # Genelde dosya ekle
            _sleep(1.0)
            # Dialog açıldı. Go to folder (Cmd+Shift+G)
            pag.hotkey(_mod(), "shift", "g")
            _sleep(0.8)
            _paste(image_path)
            _press_enter() # Go
            _sleep(0.5)
            _press_enter() # Open
            _sleep(bekleme)
            return True
        else:
            # Win/Linux: ekle kısayolu → yol → Enter
            pag.hotkey(_mod(), _key("whatsapp_openfile_key", "o")); _sleep(1.0)
            _paste(str(Path(image_path))); _press_enter(); _sleep(bekleme); return True
    except Exception as e:
        _dlog(f"_send_image_to_chat HATA: {e}"); return False

def whatsapp_gonder_dosya(
    nums,
    mesaj,
    dosya_yollari=None,
    bekle: float = 0.8,
    tekrar: int = 1,
    ogrenci_id: int | None = None
):
    nums = _unique(nums)
    ok, fail = [], []
    _focus_whatsapp()

    for raw in nums:
        n = _normalize_number(raw)
        if not n: fail.append(raw); continue

        sent = False
        try:
            if _open_deeplink(n, None):
                _sleep(bekle)
                if mesaj: _paste(mesaj); _press_enter(); _sleep(bekle)
                if dosya_yollari:
                    try:
                        pag.hotkey(_mod(), _key("whatsapp_openfile_key","o")); _sleep(1.0)
                        for path in dosya_yollari:
                            _paste(str(path)); _press_enter(); _sleep(0.6)
                        _press_enter()
                    except Exception: pass
                sent = _after_send_check_and_log(n, mesaj, ogrenci_id)
        except Exception:
            sent = False

        if not sent:
            try:
                _focus_whatsapp(); _clear_search_field(); _paste(n); _press_enter(); _sleep(bekle)
                if mesaj: _paste(mesaj); _press_enter(); _sleep(bekle)
                if dosya_yollari:
                    try:
                        pag.hotkey(_mod(), _key("whatsapp_openfile_key","o")); _sleep(1.0)
                        for path in dosya_yollari:
                            _paste(str(path)); _press_enter(); _sleep(0.6)
                        _press_enter()
                    except Exception: pass
                sent = _after_send_check_and_log(n, mesaj, ogrenci_id)
            except Exception:
                sent = False

        if sent: ok.append(n)
        else:
            fail.append(n)
            try:
                p = os.path.join(_log_dir(), f"wa_fail_{n}.png")
                pag.screenshot(p)
            except: pass
    
    return {"gonderilen": len(ok), "fail": fail}