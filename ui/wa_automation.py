import os, pyautogui as pag, time, urllib.parse, webbrowser, platform, subprocess

def _sleep(t=0.3):
    time.sleep(t)

def _mod():
    return "command" if platform.system() == "Darwin" else "ctrl"

def _focus_whatsapp():
    """WhatsApp Desktop'ı öne getirir."""
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", "-a", "WhatsApp"], check=False)
        elif hasattr(os, "startfile"):
            try:
                os.startfile("whatsapp://")
            except Exception:
                subprocess.Popen("start whatsapp://", shell=True)
        else:
            subprocess.Popen("start whatsapp://", shell=True)
        _sleep(1)
    except Exception:
        pass

def _commit_send():
    """Mesajı gönderme girişimi: Enter → Mod+Enter → (varsa) buton."""
    try:
        pag.press("enter")
        _sleep(0.15)
        pag.hotkey(_mod(), "enter")
        _sleep(0.15)
    except Exception:
        pass

def whatsapp_gonder(numaralar, mesaj, ogrenci_id=None, image_path=None, **kwargs):
    """
    Belirtilen numaralara WhatsApp Desktop üzerinden mesaj gönderir.
    """
    gonderilen = 0
    ok = []
    for num in numaralar:
        try:
            num_clean = str(num).replace(" ", "").replace("+", "")
            if not num_clean.startswith("90") and not num_clean.startswith("905"):
                if num_clean.startswith("5"):
                    num_clean = "90" + num_clean
            link = f"https://wa.me/{num_clean}?text={urllib.parse.quote(mesaj)}"
            webbrowser.open(link)
            _sleep(2.5)
            _focus_whatsapp()
            _sleep(0.8)
            _commit_send()
            gonderilen += 1
            ok.append(num)
            _sleep(1)
        except Exception:
            pass
    return {"ok": ok, "gonderilen": gonderilen, "fail": [x for x in numaralar if x not in ok]}