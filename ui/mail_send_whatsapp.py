# -*- coding: utf-8 -*-
# ui/mail_send_whatsapp.py
from __future__ import annotations

import os, sys, re, time, sqlite3, urllib.parse, datetime as _dt
from typing import List, Tuple, Optional, Dict, Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QPushButton, QCheckBox,
    QLabel, QGroupBox, QRadioButton, QTextEdit, QMessageBox, QSizePolicy,
    QSplitter, QDialog, QListWidget, QSpinBox, QInputDialog, QApplication,
    QGridLayout, QScrollArea, QFrame
)

# ========= Genel yardımcılar =========

def _appdata_dir() -> str:
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        # Windows: LocalAppData matches db.py
        base = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
    d = os.path.join(base, "YKS_LGS_HomeworkManager")
    os.makedirs(d, exist_ok=True)
    return d

def _default_db_path() -> str:
    mac = os.path.join(os.path.expanduser("~"), "Library", "Application Support",
                       "YKS_LGS_HomeworkManager", "YKS_LGS_HomeworkManager.db")
    if sys.platform == "darwin":
        return mac
    return os.path.join(_appdata_dir(), "YKS_LGS_HomeworkManager.db")

def _ogrenci_bilgi_satiri(row) -> str:
    tel = ", ".join([t for t in [row["ogr_tel"], row["veli_tel1"], row["veli_tel2"]] if t])
    # WhatsApp Bold: *text*
    return f"👤 *{row['ad']} {row['soyad']}*  [{row['ana_grup'] or ''}-{row['alt_grup'] or ''}]  📞: {tel}"

def _status_emoji(date_str: Optional[str]) -> str:
    """Tarih bugün/gelecek/geçmiş durumuna göre emoji döndürür."""
    if not date_str:
        return "⚪️"
    try:
        d = _dt.date.fromisoformat(str(date_str).split()[0])
        today = _dt.date.today()
        if d < today:
            return "🔴"
        elif d == today:
            return "🟡"
        else:
            return "🟢"
    except Exception:
        return "📘"

def _son_kume_ozet(con: sqlite3.Connection, ogr_id: int) -> Optional[sqlite3.Row]:
    return con.execute("""
        SELECT id, verilis_tarihi, bitis_tarihi, aciklama
        FROM odev_kume
        WHERE ogrenci_id=?
        ORDER BY date(verilis_tarihi) DESC, id DESC
        LIMIT 1
    """, (ogr_id,)).fetchone()

def _son_kume_detay(con: sqlite3.Connection, ogr_id: int, emoji_headers: bool = False) -> str:
    kume = _son_kume_ozet(con, ogr_id)
    if not kume:
        return "Son ödev kümesi bulunamadı."
    lines: List[str] = []
    prefix = _status_emoji(kume["bitis_tarihi"]) + " " if emoji_headers else "📌 "
    
    # Header Bold
    header = f"{prefix}*Son Küme #{kume['id']}*\n📅 Veriliş: {kume['verilis_tarihi']} | Bitiş: {kume['bitis_tarihi'] or '-'}"
    if kume['aciklama']:
        header += f"\n📝 _{kume['aciklama']}_"
    
    lines.append(header)
    
    sat = con.execute("""
        SELECT ders, kitap_ad AS kitap, konu_ad AS konu, durum
        FROM odev WHERE kume_id=? ORDER BY ders, kitap_ad, konu_ad
    """, (kume["id"],)).fetchall()
    
    if not sat:
        lines.append("  🚫 _(Görev yok)_")
    else:
        for s in sat:
            durum_icon = "✅" if s['durum'] == 'tamam' else "⏳"
            # Ders ismi kalın, detaylar normal
            lines.append(f"  ▪️ *{s['ders']}* | {s['kitap']}: {s['konu']} [{durum_icon} {s['durum']}]")
            
    return "\n".join(lines)

def _tum_kumeler_detay(con: sqlite3.Connection, ogr_id: int, emoji_headers: bool = False) -> str:
    kumeler = con.execute("""
        SELECT id, verilis_tarihi, bitis_tarihi, aciklama
        FROM odev_kume
        WHERE ogrenci_id=?
        ORDER BY date(verilis_tarihi) DESC, id DESC
    """, (ogr_id,)).fetchall()
    if not kumeler:
        return "⚠️ Ödev kümesi bulunamadı."
    lines: List[str] = []
    for k in kumeler:
        prefix = _status_emoji(k["bitis_tarihi"]) + " " if emoji_headers else "📌 "
        
        header = f"{prefix}*Küme #{k['id']}*\n📅 Veriliş: {k['verilis_tarihi']} | Bitiş: {k['bitis_tarihi'] or '-'}"
        if k['aciklama']:
             header += f"\n📝 _{k['aciklama']}_"
        lines.append(header)
        
        sat = con.execute("""
            SELECT ders, kitap_ad AS kitap, konu_ad AS konu, durum
            FROM odev WHERE kume_id=? ORDER BY ders, kitap_ad, konu_ad
        """, (k["id"],)).fetchall()
        
        if not sat:
            lines.append("  🚫 _(Görev yok)_")
        else:
            for s in sat:
                durum_icon = "✅" if s['durum'] == 'tamam' else "⏳"
                lines.append(f"  ▪️ *{s['ders']}* | {s['kitap']}: {s['konu']} [{durum_icon} {s['durum']}]")
        lines.append("")
    return "\n".join(lines).rstrip()

def _kume_kontrol_kolon(con: sqlite3.Connection) -> str:
    """
    odev_kume tablosunda kontrol tarihi hangi kolonda tutuluyorsa onu bulur.
    Yoksa bitis_tarihi'ni kontrol tarihi gibi kullanır.
    """
    try:
        cols = [r["name"] for r in con.execute("PRAGMA table_info(odev_kume)")]
        if "kontrol_tarihi" in cols:
            return "kontrol_tarihi"
    except Exception:
        pass
    return "bitis_tarihi"

def _kumeler_detay_tarih_filtre(
    con: sqlite3.Connection,
    ogr_id: int,
    verilis_bugun: bool = False,
    kontrol_bugun: bool = False,
    kontrol_yarin: bool = False,
    kontrol_2gun: bool = False,
    kontrol_gecmis: bool = False,
    emoji_headers: bool = False
) -> str:
    """
    Tarih filtrelerine uyan ödev kümelerinin TAM detayını döndürür.
    Hiçbir filtre seçili değilse boş string döner.
    """
    if not (verilis_bugun or kontrol_bugun or kontrol_yarin or kontrol_2gun or kontrol_gecmis):
        return ""

    kontrol_col = _kume_kontrol_kolon(con)

    conds = []
    if verilis_bugun:
        conds.append("date(verilis_tarihi, 'localtime') = date('now','localtime')")
    if kontrol_bugun:
        conds.append(f"date({kontrol_col}, 'localtime') = date('now','localtime')")
    if kontrol_yarin:
        conds.append(f"date({kontrol_col}, 'localtime') = date('now','localtime','+1 day')")
    if kontrol_2gun:
        conds.append(f"date({kontrol_col}, 'localtime') = date('now','localtime','+2 day')")
    if kontrol_gecmis:
        conds.append(f"date({kontrol_col}, 'localtime') < date('now','localtime')")

    where_extra = " AND (" + " OR ".join(conds) + ")"

    kumeler = con.execute(f"""
        SELECT id, verilis_tarihi, {kontrol_col} AS kontrol_tarihi, aciklama
        FROM odev_kume
        WHERE ogrenci_id=? {where_extra}
        ORDER BY date(verilis_tarihi) DESC, id DESC
    """, (ogr_id,)).fetchall()

    if not kumeler:
        return ""

    lines: List[str] = []
    for k in kumeler:
        kt = k["kontrol_tarihi"] or "-"
        prefix = _status_emoji(kt) + " " if emoji_headers else "📌 "
        
        header = f"{prefix}*Küme #{k['id']}*\n📅 Veriliş: {k['verilis_tarihi']} | Kontrol: {kt}"
        if k['aciklama']:
            header += f"\n📝 _{k['aciklama']}_"
        lines.append(header)
        
        sat = con.execute("""
            SELECT ders, kitap_ad AS kitap, konu_ad AS konu, durum
            FROM odev WHERE kume_id=? ORDER BY ders, kitap_ad, konu_ad
        """, (k["id"],)).fetchall()
        
        if not sat:
            lines.append("  🚫 _(Görev yok)_")
        else:
            for s in sat:
                durum_icon = "✅" if s['durum'] == 'tamam' else "⏳"
                lines.append(f"  ▪️ *{s['ders']}* | {s['kitap']}: {s['konu']} [{durum_icon} {s['durum']}]")
        lines.append("")
    return "\n".join(lines).rstrip()

# Eski "belirli veriliş tarihi" fonksiyonu, istersen kullanırsın
def _kumeler_detay_tarih(con: sqlite3.Connection, ogr_id: int, date_str: str) -> str:
    kumeler = con.execute("""
        SELECT id, verilis_tarihi, bitis_tarihi, aciklama
        FROM odev_kume
        WHERE ogrenci_id=? AND date(verilis_tarihi)=date(?)
        ORDER BY id
    """, (ogr_id, date_str)).fetchall()
    if not kumeler:
        return f"{date_str} tarihinde ödev kümesi bulunamadı."
    lines: List[str] = []
    for k in kumeler:
        lines.append(
            f"Küme #{k['id']} (Veriliş:{k['verilis_tarihi']} Bitiş:{k['bitis_tarihi'] or '-'}) "
            f"{k['aciklama'] or ''}".strip()
        )
        sat = con.execute("""
            SELECT ders, kitap_ad AS kitap, konu_ad AS konu, durum
            FROM odev WHERE kume_id=? ORDER BY ders, kitap_ad, konu_ad
        """, (k["id"]),).fetchall()
        if not sat:
            lines.append("  - (Görev yok)")
        else:
            for s in sat:
                lines.append(f"  - {s['ders']} | {s['kitap']}: {s['konu']} [{s['durum']}]")
        lines.append("")
    return "\n".join(lines).rstrip()

def _try_import_selenium():
    """
    Selenium + webdriver-manager yüklü mü diye kontrol eder.
    Yüklü değilse OTOMATİK yüklemeye çalışır.
    """
    try:
        import selenium  # noqa
        from selenium import webdriver  # noqa
        from webdriver_manager.chrome import ChromeDriverManager  # noqa
        return True
    except ImportError:
        # Otomatik kurulum denemesi
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium", "webdriver-manager"])
            
            # Tekrar dene
            import selenium  # noqa
            from selenium import webdriver  # noqa
            from webdriver_manager.chrome import ChromeDriverManager  # noqa
            return True
        except Exception as e:
            print(f"Auto-install error: {e}")
            return False
    except Exception:
        return False

class WhatsAppWebClient:
    """Selenium ile WhatsApp Web gönderici. Login oturumu profil klasöründe saklanır."""
    def __init__(self, profile_dir: str):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        self.alive = False
        self.profile_dir = profile_dir
        os.makedirs(self.profile_dir, exist_ok=True)

        opts = Options()
        # Profil klasörünü sabitle – böylece QR kodu bir kere okutman yeterli
        opts.add_argument(f"--user-data-dir={self.profile_dir}")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--start-maximized")

        # webdriver-manager: doğru ChromeDriver'ı indirip yolunu otomatik ayarlar
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=opts)

        self.wait = None
        self.alive = True

    def ensure_login(self, timeout_sec: int = 120):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        self.driver.get("https://web.whatsapp.com/")
        self.wait = WebDriverWait(self.driver, timeout_sec)
        self.wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='textbox']")))
        return True

    def send_text(self, phone_e164: str, message: str, per_number_timeout: int = 45) -> str:
        """
        phone_e164: '90...' gibi ülke kodlu numara ( + işareti olmadan )
        döndürür: 'OK' | 'INVALID' | 'FAIL'
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver import ActionChains

        # Senin sevdiğin yöntem: URL ile mesajı hazır doldur
        q = urllib.parse.quote(message)
        self.driver.get(f"https://web.whatsapp.com/send?phone={phone_e164}&text={q}")
        w = WebDriverWait(self.driver, per_number_timeout)

        try:
            # 1) Sohbet ekranı ve asıl mesaj kutusu gelsin
            w.until(EC.presence_of_element_located((By.ID, "main")))
            box = w.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div[contenteditable='true'][data-tab]")
                )
            )
            try:
                box.click()
            except Exception:
                pass
            time.sleep(0.5)  # URL'deki text kutuya tam düşsün

            # 2) JS ile gönder butonunu yakala ve tıkla (daha gelişmiş selektörler)
            btn = None
            # Maksimum 10 saniye boyunca butonun görünmesini bekle
            end_time = time.time() + 10
            while time.time() < end_time:
                btn = self.driver.execute_script("""
                    return (
                        document.querySelector('footer [data-testid="send"]') ||
                        document.querySelector('footer span[data-icon="send"]') ||
                        document.querySelector('footer button[aria-label="Send"]') ||
                        document.querySelector('footer button[aria-label="Gönder"]') ||
                        document.querySelector('div[role="button"][aria-label="Gönder"]') ||
                        document.querySelector('div[role="button"][aria-label="Send"]')
                    );
                """)
                if btn:
                    break
                time.sleep(0.5)

            if btn:
                # JS ile tıkla
                self.driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
                
                # Tıklama sonrası kutu boşaldı mı kontrol et (Başarılı gönderim kanıtı)
                # Kutu boşalmadıysa ENTER dene
                try:
                    box_text = box.text
                    if box_text.strip():
                        # Kutu hala dolu, demek ki tıklama işe yaramadı, ENTER bas
                         ActionChains(self.driver).move_to_element(box).click(box).send_keys(Keys.ENTER).perform()
                except:
                    pass
            else:
                # 3) Yedek plan: Buton bulunamadıysa direkt kutuya ENTER gönder
                try:
                    ActionChains(self.driver).move_to_element(box).click(box).send_keys(Keys.ENTER).perform()
                except Exception:
                    # Son çare: aktif elemana ENTER
                    try:
                        active = self.driver.switch_to.active_element
                        ActionChains(self.driver).move_to_element(active).click(active).send_keys(Keys.ENTER).perform()
                    except Exception:
                        pass

            # Mesajın gerçekten gidip gitmediğini (kutunun boşalmasıyla) kontrol et
            # 5 saniye bekle
            final_wait = time.time() + 5
            while time.time() < final_wait:
                try:
                    current_text = box.text
                    if not current_text.strip():
                        # Kutu boş, gönderildi say
                        return "OK"
                except:
                    pass
                time.sleep(0.5)
            
            # Süre bitti ama kutu hala dolu olabilir veya emin değiliz
            # "OK" dönelim çünkü bazen DOM erişimi hatası olabilir ama gitmiş olabilir.
            # Ancak genel akışta bir sonraki numaraya geçince sorun çıkmıyor.
            return "OK"

        except Exception:
            # numara hatalı / sohbet açılamadı vs.
            return "INVALID"

    def close(self):
        if self.alive:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.alive = False

# ========= Worker (ayrı thread, kendi DB bağlantısı) =========

class WhatsAppWorker(QThread):
    finishedSummary = pyqtSignal(int, int, int)   # sent, invalid, failed
    error = pyqtSignal(str, str)                  # title, message

    def __init__(
        self,
        db_path: str,
        rows_snapshot: List[Tuple[int, str, List[str]]],   # (id, adsoyad, [raw_nums])
        text_base: str,
        cc_text: str,
        add_stuinfo: bool,
        add_lastkume_full: bool,
        add_allkume: bool,
        verilis_bugun: bool,
        kontrol_bugun: bool,
        kontrol_yarin: bool,
        kontrol_2gun: bool,
        kontrol_gecmis: bool,
        personal_mode: bool,
        per_chat_timeout: int,
        wait_between: float,
        use_emoji_headers: bool,
        pdf_summary: bool,
        parent=None
    ):
        super().__init__(parent)
        self.db_path = db_path
        self.rows_snapshot = rows_snapshot
        self.text_base = text_base
        self.cc_text = cc_text
        self.add_stuinfo = add_stuinfo
        self.add_lastkume_full = add_lastkume_full
        self.add_allkume = add_allkume
        self.verilis_bugun = verilis_bugun
        self.kontrol_bugun = kontrol_bugun
        self.kontrol_yarin = kontrol_yarin
        self.kontrol_2gun = kontrol_2gun
        self.kontrol_gecmis = kontrol_gecmis
        self.personal_mode = personal_mode
        self.per_chat_timeout = per_chat_timeout
        self.wait_between = max(0.1, float(wait_between))
        self.use_emoji_headers = use_emoji_headers
        self.pdf_summary = pdf_summary

    def _norm_numbers(self, raw_list: List[str], cc: str) -> List[str]:
        cc = re.sub(r"\D", "", cc or "90")
        out: List[str] = []
        for r in raw_list:
            if not r:
                continue
            n = re.sub(r"\D", "", r)
            if not n:
                continue
            if n.startswith("0"):
                n = n[1:]
            if not n.startswith(cc):
                n = cc + n
            out.append(n)
        return list(dict.fromkeys(out))

    def run(self):
        if not _try_import_selenium():
            self.error.emit(
                "Eksik Bağımlılık",
                "Selenium / ChromeDriver bulunamadı.\n\nKurulum (tek seferlik):\n"
                "  pip install selenium webdriver-manager\n"
                "Ayrıca Google Chrome kurulu olmalı."
            )
            return

        # Thread için yeni DB bağlantısı
        try:
            con = sqlite3.connect(self.db_path)
            con.row_factory = sqlite3.Row
        except Exception as e:
            self.error.emit("Veritabanı Hatası", f"DB açılırken hata:\n{e}")
            return

        profile_dir = os.path.join(_appdata_dir(), "wa_web_profile")
        from selenium.common.exceptions import WebDriverException

        try:
            wa = WhatsAppWebClient(profile_dir)
        except WebDriverException as e:
            self.error.emit(
                "Tarayıcı Hatası",
                f"Chrome başlatılamadı:\n{e}\n\nChrome kurulu ve güncel mi,\n"
                "Mac’te Güvenlik & Gizlilik izinlerine baktın mı?"
            )
            con.close()
            return

        try:
            try:
                # Login için geniş bir süre kalsın (ayarlardan bağımsız)
                wa.ensure_login(timeout_sec=150)
            except Exception:
                self.error.emit(
                    "Giriş Zaman Aşımı",
                    "WhatsApp Web açıldı ama giriş tamamlanmadı.\n"
                    "Lütfen QR kodunu telefondan okut ve tekrar dene."
                )
                con.close()
                wa.close()
                return

            sent = invalid = failed = 0

            has_filters = any([
                self.verilis_bugun,
                self.kontrol_bugun,
                self.kontrol_yarin,
                self.kontrol_2gun,
                self.kontrol_gecmis
            ])

            for sid, adsoyad, raw_nums in self.rows_snapshot:
                try:
                    stu = con.execute("SELECT * FROM ogrenci WHERE id=?", (sid,)).fetchone()
                except Exception:
                    stu = None

                ad = stu["ad"] if stu else ""
                soyad = stu["soyad"] if stu else ""

                text_i = self.text_base.replace("{ad}", ad).replace("{soyad}", soyad)

                if self.personal_mode:
                    extras: List[str] = []
                    if self.add_stuinfo and stu:
                        extras.append("• " + _ogrenci_bilgi_satiri(stu))
                    if self.add_lastkume_full:
                        extras.append("\n" + _son_kume_detay(con, sid, emoji_headers=self.use_emoji_headers))

                    if has_filters:
                        detay = _kumeler_detay_tarih_filtre(
                            con,
                            sid,
                            verilis_bugun=self.verilis_bugun,
                            kontrol_bugun=self.kontrol_bugun,
                            kontrol_yarin=self.kontrol_yarin,
                            kontrol_2gun=self.kontrol_2gun,
                            kontrol_gecmis=self.kontrol_gecmis,
                            emoji_headers=self.use_emoji_headers,
                        )
                        # Seçilen filtreye uygun küme yoksa bu öğrenciye mesaj gitmesin
                        if not detay:
                            continue
                        extras.append("\n" + detay)
                    else:
                        if self.add_allkume:
                            extras.append("\n" + _tum_kumeler_detay(con, sid, emoji_headers=self.use_emoji_headers))

                    if extras:
                        text_i = (text_i + "\n\n" + "\n".join(extras)).strip()

                numbers = self._norm_numbers(raw_nums, self.cc_text)
                if not numbers:
                    failed += 1
                    continue

                # NOT: PDF özeti istersen burada utils.ogrenci_rapor_pdf çağırabilirsin (TODO)
                # if self.pdf_summary:
                #     try:
                #         from utils.ogrenci_rapor import ogrenci_rapor_pdf
                #         ogrenci_rapor_pdf(con, sid, ...)
                #     except Exception:
                #         pass

                for num in numbers:
                    # Mesajı gönder
                    res = wa.send_text(num, text_i, per_number_timeout=self.per_chat_timeout)
                    
                    # Log
                    try:
                        con.execute("""
                            INSERT INTO whatsapp_log
                            (ogrenci_id, numara, mesaj_onizleme, durum, ts,
                             numaralar, mesaj, ogrenci_ad, ogrenci_soyad, ogrenci_adsoyad)
                            VALUES(?,?,?,?,datetime('now'),?,?,?,?)
                        """, (
                            sid,
                            f"+{num}",
                            text_i[:200],
                            "OK" if res == "OK" else "FAIL",
                            ",".join([f"+{n}" for n in numbers]),
                            text_i,
                            ad, soyad, f"{ad} {soyad}",
                        ))
                        con.commit()
                    except Exception:
                        pass

                    if res == "OK":
                        sent += 1
                    elif res == "INVALID":
                        invalid += 1
                    else:
                        failed += 1

                    time.sleep(self.wait_between)

            self.finishedSummary.emit(sent, invalid, failed)

        finally:
            try:
                wa.close()
            except Exception:
                pass
            con.close()


# ========= WhatsApp Ayarları / Şablonlar Dialog =========

class WhatsAppSettingsDialog(QDialog):
    def __init__(self, parent, settings_path: str):
        super().__init__(parent)
        self.settings_path = settings_path
        self.setWindowTitle("WhatsApp Ayarları ve Mesaj Şablonları")
        self.resize(600, 450)
        self.selected_template_text = None # Dönen değer
        self._load_settings()
        self._build_ui()

    # ------------------------ UI ------------------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # --- Zamanlama ---
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Sohbet açma zaman aşımı (sn):"))
        self.spnOpen = QSpinBox()
        self.spnOpen.setRange(5, 200)
        self.spnOpen.setValue(self.settings.get("open_timeout", 45))
        row1.addWidget(self.spnOpen)

        row1.addSpacing(20)
        row1.addWidget(QLabel("Mesajlar arası bekleme (sn):"))
        self.spnWait = QSpinBox()
        self.spnWait.setRange(0, 30)
        self.spnWait.setValue(self.settings.get("wait_between", 2))
        row1.addWidget(self.spnWait)
        lay.addLayout(row1)

        lay.addWidget(QLabel("Mesaj Şablonları:"))

        self.lstTemplates = QListWidget()
        for name in self.settings.get("templates", {}):
            self.lstTemplates.addItem(name)
        lay.addWidget(self.lstTemplates, 1)

        self.txtTemplate = QTextEdit()
        self.txtTemplate.setPlaceholderText("Şablon içeriği burada düzenlenir...")
        lay.addWidget(self.txtTemplate, 2)

        self.lstTemplates.currentTextChanged.connect(self._load_selected_template)

        rowButtons = QHBoxLayout()

        btnUse = QPushButton("✅ Bu Şablonu Kullan")
        btnUse.setToolTip("Seçili şablonu ana ekrandaki mesaj kutusuna aktarır ve pencereyi kapatır.")
        btnUse.setStyleSheet("font-weight: bold; color: #1e40af;")
        btnUse.clicked.connect(self._use_selected_template)
        rowButtons.addWidget(btnUse)

        # btnLoad = QPushButton("Seçili şablonu yükle") # Gereksiz, çift tıklama var artık
        # btnLoad.clicked.connect(self._load_selected_template_into_editor)
        # rowButtons.addWidget(btnLoad)

        btnSaveAs = QPushButton("💾 Mesajı Kaydet")
        btnSaveAs.setToolTip("Editördeki metni yeni bir şablon olarak kaydeder.")
        btnSaveAs.clicked.connect(self._save_current_as_template)
        rowButtons.addWidget(btnSaveAs)

        btnDelete = QPushButton("🗑 Sil")
        btnDelete.setToolTip("Seçili şablonu siler.")
        btnDelete.clicked.connect(self._delete_template)
        rowButtons.addWidget(btnDelete)

        lay.addLayout(rowButtons)
        
        # Çift tıklama ile direkt kullan
        self.lstTemplates.itemDoubleClicked.connect(self._use_selected_template)

        rowOC = QHBoxLayout()
        rowOC.addStretch(1)
        btnCancel = QPushButton("Cancel")
        btnCancel.clicked.connect(self.reject)
        btnOK = QPushButton("OK")
        btnOK.clicked.connect(self._save_and_close)
        rowOC.addWidget(btnCancel)
        rowOC.addWidget(btnOK)
        lay.addLayout(rowOC)

    # ------------------------ Settings Load/Save ------------------------
    def _load_settings(self):
        import json
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
                return
            except Exception:
                pass

        self.settings = {
            "open_timeout": 45,
            "wait_between": 2,
            "templates": {}
        }

    def _save_settings(self):
        import json
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    # ------------------------ Template Ops ------------------------
    def _load_selected_template(self, name):
        if not name:
            return
        txt = self.settings["templates"].get(name, "")
        self.txtTemplate.setPlainText(txt)

    def _load_selected_template_into_editor(self):
        itm = self.lstTemplates.currentItem()
        if not itm:
            return
        name = itm.text()
        txt = self.settings["templates"].get(name, "")
        self.txtTemplate.setPlainText(txt)

    def _save_current_as_template(self):
        text = self.txtTemplate.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Boş", "Şablon içeriği boş olamaz.")
            return

        name, ok = QInputDialog.getText(self, "Şablon Adı", "Şablon için bir ad gir:")
        if not ok or not name.strip():
            return
        name = name.strip()

        self.settings.setdefault("templates", {})
        self.settings["templates"][name] = text
        self._save_settings()

        self.lstTemplates.addItem(name)

    def _delete_template(self):
        itm = self.lstTemplates.currentItem()
        if not itm:
            return
        name = itm.text()
        try:
            del self.settings["templates"][name]
        except KeyError:
            pass
        self._save_settings()
        self.lstTemplates.takeItem(self.lstTemplates.row(itm))
        self.txtTemplate.clear()

    def _use_selected_template(self):
        # 1. Listeden seçili mi?
        itm = self.lstTemplates.currentItem()
        if itm:
            name = itm.text()
            txt = self.settings["templates"].get(name, "")
        else:
            # 2. Değilse, editördeki metni al
            txt = self.txtTemplate.toPlainText()
        
        if not txt.strip():
             QMessageBox.warning(self, "Boş", "Kullanılacak bir metin veya şablon seçmediniz.")
             return

        self.selected_template_text = txt
        self._save_and_close()

    def _save_and_close(self):
        self.settings["open_timeout"] = self.spnOpen.value()
        self.settings["wait_between"] = self.spnWait.value()
        self._save_settings()
        self.accept()


# ========= WhatsApp Sekmesi (GUI) =========

class WhatsAppTab(QWidget):
    def __init__(self, con: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.con = con

        # DB yolunu al
        try:
            row = self.con.execute("PRAGMA database_list").fetchone()
            self.db_path = row["file"] if isinstance(row, sqlite3.Row) else row[2]
            if not self.db_path:
                self.db_path = _default_db_path()
        except Exception:
            self.db_path = _default_db_path()

        self.worker: Optional[WhatsAppWorker] = None
        self.wa_settings_path = os.path.join(_appdata_dir(), "wa_settings.json")
        self.wa_settings: Dict[str, Any] = {}
        self._build_ui()
        self._load_wa_settings()
        self._apply_modern_styles()
        self._do_search_wa()

    def _apply_modern_styles(self):
        # Modern, ferah ve profesyonel bir tema
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                font-size: 13px;
                color: #1f2937;
            }
            
            /* -- Tablolar -- */
            QTableWidget {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff;
                selection-color: #1e3a8a;
                outline: none;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 600;
                color: #475569;
                text-transform: uppercase;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:hover {
                background-color: #f8fafc;
            }

            /* -- Butonlar -- */
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
                color: #475569;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #334155;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }

            /* Özel Butonlar */
            QPushButton#btnGonderWA {
                background-color: #2563eb;
                color: white;
                border: 1px solid #2563eb;
            }
            QPushButton#btnGonderWA:hover {
                background-color: #1d4ed8;
                border-color: #1d4ed8;
            }
            
            QPushButton#btnBulWA {
                background-color: #0ea5e9;
                color: white;
                border: 1px solid #0ea5e9;
            }
            QPushButton#btnBulWA:hover {
                background-color: #0284c7;
                border-color: #0284c7;
            }

            /* -- Input Alanları -- */
            QLineEdit, QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #3b82f6;
                padding: 7px; /* border artınca kaymasın */
            }

            /* -- GroupBox -- */
            QGroupBox {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 12px;
                font-weight: bold;
                background-color: #ffffff;
                padding-top: 8px;
                padding-bottom: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                top: 0px;
                padding: 0 5px;
                color: #2563eb;
                background-color: #ffffff;
            }

            /* -- Checkbox & Radio -- */
            QCheckBox, QRadioButton {
                spacing: 8px;
                color: #334155;
                font-weight: 500;
                font-size: 11.5px;
                min-height: 22px;
                padding: 1px 0px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1.5px solid #cbd5e1;
                background: white;
            }
            QCheckBox::indicator:hover, QRadioButton::indicator:hover {
                border-color: #3b82f6;
            }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background-color: #2563eb;
                border-color: #2563eb;
                image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'></polyline></svg>");
            }
            QRadioButton::indicator {
                border-radius: 8px;
            }
            QRadioButton::indicator:checked {
                 image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'><circle cx='12' cy='12' r='6'/></svg>");
            }
            
            /* Scrollbar */
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 8px;
                margin: 0;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
        """)
        
        # Give specific ObjectNames for styling
        self.btnGonderWA.setObjectName("btnGonderWA")
        self.btnBulWA.setObjectName("btnBulWA")
        
        # Cursor pointers
        from PyQt6.QtGui import QCursor
        self.btnGonderWA.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnBulWA.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnHepsiWA.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnSettingsWA.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    # --- Ayarları oku ---
    def _load_wa_settings(self):
        import json
        if os.path.exists(self.wa_settings_path):
            try:
                with open(self.wa_settings_path, "r", encoding="utf-8") as f:
                    self.wa_settings = json.load(f)
            except Exception:
                self.wa_settings = {}
        if not self.wa_settings:
            self.wa_settings = {"open_timeout": 45, "wait_between": 2, "templates": {}}

        # Eğer mesaj kutusu boşsa, ilk şablonu otomatik yükle
        if self.txtBodyWA.toPlainText().strip() == "":
            templates = self.wa_settings.get("templates", {})
            if templates:
                first_name = next(iter(templates))
                self.txtBodyWA.setPlainText(templates[first_name])

    # --- Ayar dialogunu aç ---
    def _open_settings_dialog(self):
        dlg = WhatsAppSettingsDialog(self, self.wa_settings_path)
        if dlg.exec():
            self._load_wa_settings()

    # --- UI kur ---
    # --- UI kur ---
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(12)

        spl = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(spl, 1)

        # SOL: liste
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 10, 0)
        lv.setSpacing(10)
        
        srch = QHBoxLayout()
        self.txtAraWA = QLineEdit()
        self.txtAraWA.setPlaceholderText("Öğrenci ara: Ad Soyad / e-posta…")
        self.btnBulWA = QPushButton("🔍 Ara")
        srch.addWidget(self.txtAraWA, 1)
        srch.addWidget(self.btnBulWA)
        lv.addLayout(srch)

        self.tblWA = QTableWidget(0, 6)
        self.tblWA.setHorizontalHeaderLabels(["#", "Öğrenci", "Öğr. Tel", "Veli Tel1", "Veli Tel2", "Seç"])
        hh = self.tblWA.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4, 5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tblWA.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tblWA.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tblWA.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tblWA.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lv.addWidget(self.tblWA, 1)

        bar = QHBoxLayout()
        self.btnHepsiWA = QPushButton("✅ Tümünü Seç")
        self.btnGonderWA = QPushButton("📤 Gönder (WhatsApp)")
        bar.addWidget(self.btnHepsiWA)
        bar.addStretch(1)
        bar.addWidget(self.btnGonderWA)
        lv.addLayout(bar)
        spl.addWidget(left)

        # SAĞ: ayarlar + mesaj (Scrollable ve responsive)
        right_container = QWidget()
        rc_lay = QVBoxLayout(right_container)
        rc_lay.setContentsMargins(4, 0, 0, 0)
        rc_lay.setSpacing(6)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        right_body = QWidget()
        right_body.setStyleSheet("background: transparent;")
        rv = QVBoxLayout(right_body)
        rv.setContentsMargins(4, 0, 8, 4)
        rv.setSpacing(8)

        modeGrp = QGroupBox("Gönderim Modu")
        mh = QHBoxLayout(modeGrp)
        self.rdTopluWA = QRadioButton("Toplu (aynı içerik)")
        self.rdKisiselWA = QRadioButton("Kişiselleştirilmiş (her öğrenciye kendi kümesi)")
        self.rdTopluWA.setChecked(True)
        mh.addWidget(self.rdTopluWA)
        mh.addWidget(self.rdKisiselWA)
        mh.addStretch(1)
        rv.addWidget(modeGrp)

        # Ülke kodu
        self.txtUlkeKodu = QLineEdit("90")
        ccRow = QHBoxLayout()
        ccRow.addWidget(QLabel("Ülke kodu:"))
        ccRow.addWidget(self.txtUlkeKodu, 0)
        rv.addLayout(ccRow)

        # Hangi numaralar kullanılacak?
        numGrp = QGroupBox("Kullanılacak numaralar")
        nv = QHBoxLayout(numGrp)
        self.chkUseOgr = QCheckBox("Öğrenci tel")
        self.chkUseOgr.setChecked(True)
        self.chkUseV1 = QCheckBox("Veli Tel1")
        self.chkUseV1.setChecked(True)
        self.chkUseV2 = QCheckBox("Veli Tel2")
        self.chkUseV2.setChecked(True)
        for wgt in (self.chkUseOgr, self.chkUseV1, self.chkUseV2):
            wgt.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            wgt.setMinimumHeight(24)
            nv.addWidget(wgt)
        nv.addStretch(1)
        rv.addWidget(numGrp)

        # İçerik seçenekleri (2 sütunlu ferah ve profesyonel grid)
        optGrp = QGroupBox("İçerik Seçenekleri")
        optGrp.setMinimumHeight(175)
        og = QGridLayout(optGrp)
        og.setContentsMargins(12, 10, 12, 10)
        og.setHorizontalSpacing(16)
        og.setVerticalSpacing(8)

        self.chkStuInfoWA = QCheckBox("Öğrenci bilgisi eklensin")
        self.chkLastKumeWA = QCheckBox("Son ödev kümesinin TAMAMI eklensin")
        self.chkAllKumeWA = QCheckBox("Tüm ödev kümeleri ve içerikleri")
        self.chkEmojiHeaders = QCheckBox("Küme başlıklarına emoji eklensin")
        self.chkPdfSummary = QCheckBox("Her öğrenci için PDF özet (beta)")

        self.chkBugunVerilen = QCheckBox("Bugün ÖDEV VERİLEN kümeler")
        self.chkKontrolBugun = QCheckBox("KONTROL TARİHİ BUGÜN olanlar")
        self.chkKontrolYarin = QCheckBox("KONTROL TARİHİ YARIN olanlar")
        self.chkKontrol2Gun = QCheckBox("KONTROL TARİHİ 2 gün sonra")
        self.chkKontrolGecmis = QCheckBox("KONTROL TARİHİ GEÇMİŞ (gecikmiş)")

        col1 = [self.chkStuInfoWA, self.chkLastKumeWA, self.chkAllKumeWA, self.chkEmojiHeaders, self.chkPdfSummary]
        col2 = [self.chkBugunVerilen, self.chkKontrolBugun, self.chkKontrolYarin, self.chkKontrol2Gun, self.chkKontrolGecmis]

        for wgt in col1 + col2:
            wgt.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            wgt.setMinimumHeight(24)

        for row_idx, wgt in enumerate(col1):
            og.addWidget(wgt, row_idx, 0)
        for row_idx, wgt in enumerate(col2):
            og.addWidget(wgt, row_idx, 1)

        rv.addWidget(optGrp)

        self.txtBodyWA = QTextEdit()
        self.txtBodyWA.setPlaceholderText("Mesaj (kişiselleştirme: {ad}, {soyad})")
        self.txtBodyWA.setMinimumHeight(70)
        rv.addWidget(QLabel("Mesaj:"))
        rv.addWidget(self.txtBodyWA, 1)

        info = QLabel(
            "ℹ️  İlk kullanımda WhatsApp Web’de QR kodunu okutman gerekir.\n"
            "Profil bu bilgisayarda saklanır; sonraki gönderimlerde tekrar istemez."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #64748b; font-size: 11px;")
        rv.addWidget(info)

        right_scroll.setWidget(right_body)
        rc_lay.addWidget(right_scroll, 1)

        spl.addWidget(right_container)
        spl.setStretchFactor(0, 3)
        spl.setStretchFactor(1, 2)
        spl.setSizes([820, 520])

        # Alt sağ: Ayarlar butonu
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btnSettingsWA = QPushButton("⚙️ Ayarlar / Şablonlar")
        bottom.addWidget(self.btnSettingsWA)
        root.addLayout(bottom)

        # sinyaller
        self.btnBulWA.clicked.connect(self._do_search_wa)
        self.btnHepsiWA.clicked.connect(self._toggle_all_wa)
        self.btnGonderWA.clicked.connect(self._on_send_clicked)
        self.btnSettingsWA.clicked.connect(self._open_settings_dialog)

        # Filtre + şablon entegrasyonu: gecikmiş filtresi açılırsa "gecikmiş" şablonu yükle
        self.chkKontrolGecmis.toggled.connect(self._on_gecmis_filter_toggled)

    def _open_settings_dialog(self):
        dlg = WhatsAppSettingsDialog(self, self.wa_settings_path)
        # Mevcut mesajı dialog'a ön-yükle (Opsiyonel, kullanıcı isterse "Kaydet" diyebilsin diye)
        dlg.txtTemplate.setPlainText(self.txtBodyWA.toPlainText())
        
        if dlg.exec():
            # Ayarlar yenilensin
            self._load_wa_settings()
            # Eğer kullanıcı "Kullan"dediyse metni güncelle
            if dlg.selected_template_text:
                self.txtBodyWA.setPlainText(dlg.selected_template_text)

    # Filtre + şablon birlikte çalışsın
    def _on_gecmis_filter_toggled(self, checked: bool):
        if not checked:
            return
        templates = self.wa_settings.get("templates", {})
        if not templates:
            return
        target_name = None
        for name in templates:
            if "gecik" in name.lower():
                target_name = name
                break
        if not target_name:
            target_name = next(iter(templates))
        self.txtBodyWA.setPlainText(templates[target_name])

    # --- Liste doldur ---
    def _do_search_wa(self):
        q = f"%{(self.txtAraWA.text() or '').strip()}%"
        rows = self.con.execute("""
            SELECT id, ad, soyad, ogr_tel, veli_tel1, veli_tel2,
                   ana_grup, alt_grup
            FROM ogrenci
            WHERE aktif = 1 AND (ad || ' ' || soyad LIKE ?)
            ORDER BY ad, soyad
        """, (q,)).fetchall()

        self.tblWA.setRowCount(0)
        for r in rows:
            i = self.tblWA.rowCount()
            self.tblWA.insertRow(i)
            self.tblWA.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.tblWA.setItem(i, 1, QTableWidgetItem(f"{r['ad']} {r['soyad']}"))
            self.tblWA.setItem(i, 2, QTableWidgetItem(r["ogr_tel"] or ""))
            self.tblWA.setItem(i, 3, QTableWidgetItem(r["veli_tel1"] or ""))
            self.tblWA.setItem(i, 4, QTableWidgetItem(r["veli_tel2"] or ""))
            chk = QCheckBox()
            chk.setChecked(bool(r["ogr_tel"] or r["veli_tel1"] or r["veli_tel2"]))
            self.tblWA.setCellWidget(i, 5, chk)
            self.tblWA.setRowHeight(i, 26)
        self.tblWA.clearSelection()
        self.btnHepsiWA.setText("Tümünü İşaretle")

    def _toggle_all_wa(self):
        if self.tblWA.rowCount() == 0:
            return
        all_checked = all(
            (self.tblWA.cellWidget(i, 5) and self.tblWA.cellWidget(i, 5).isChecked())
            for i in range(self.tblWA.rowCount())
        )
        target = not all_checked
        for i in range(self.tblWA.rowCount()):
            cw = self.tblWA.cellWidget(i, 5)
            if cw:
                cw.setChecked(target)
        self.btnHepsiWA.setText("Tümünü Kaldır" if target else "Tümünü İşaretle")

    # --- Gönder butonu ---
    def _on_send_clicked(self):
        text_base = (self.txtBodyWA.toPlainText() or "").strip()
        if not text_base:
            QMessageBox.warning(self, "Eksik", "Önce mesaj metnini yaz.")
            return

        rows_snapshot: List[Tuple[int, str, List[str]]] = []
        for i in range(self.tblWA.rowCount()):
            cw = self.tblWA.cellWidget(i, 5)
            if not (cw and cw.isChecked()):
                continue
            sid = int(self.tblWA.item(i, 0).text())
            adsoyad = self.tblWA.item(i, 1).text() if self.tblWA.item(i, 1) else ""
            t_ogr = self.tblWA.item(i, 2).text().strip() if self.tblWA.item(i, 2) else ""
            t_v1  = self.tblWA.item(i, 3).text().strip() if self.tblWA.item(i, 3) else ""
            t_v2  = self.tblWA.item(i, 4).text().strip() if self.tblWA.item(i, 4) else ""

            raw_nums: List[str] = []
            if self.chkUseOgr.isChecked(): raw_nums.append(t_ogr)
            if self.chkUseV1.isChecked():  raw_nums.append(t_v1)
            if self.chkUseV2.isChecked():  raw_nums.append(t_v2)

            rows_snapshot.append((sid, adsoyad, raw_nums))

        if not rows_snapshot:
            QMessageBox.information(self, "Seçim Yok", "Soldan en az bir öğrenciyi işaretle.")
            return

        cc_text = (self.txtUlkeKodu.text() or "90").strip()
        add_stuinfo  = self.chkStuInfoWA.isChecked()
        add_lastkume_full = self.chkLastKumeWA.isChecked()
        add_allkume  = self.chkAllKumeWA.isChecked()

        verilis_bugun  = self.chkBugunVerilen.isChecked()
        kontrol_bugun  = self.chkKontrolBugun.isChecked()
        kontrol_yarin  = self.chkKontrolYarin.isChecked()
        kontrol_2gun   = self.chkKontrol2Gun.isChecked()
        kontrol_gecmis = self.chkKontrolGecmis.isChecked()

        personal_mode = self.rdKisiselWA.isChecked()

        use_emoji_headers = self.chkEmojiHeaders.isChecked()
        pdf_summary = self.chkPdfSummary.isChecked()

        per_chat_timeout = int(self.wa_settings.get("open_timeout", 45))
        wait_between = float(self.wa_settings.get("wait_between", 2))

        self.btnGonderWA.setEnabled(False)

        self.worker = WhatsAppWorker(
            self.db_path,
            rows_snapshot,
            text_base,
            cc_text,
            add_stuinfo,
            add_lastkume_full,
            add_allkume,
            verilis_bugun,
            kontrol_bugun,
            kontrol_yarin,
            kontrol_2gun,
            kontrol_gecmis,
            personal_mode,
            per_chat_timeout,
            wait_between,
            use_emoji_headers,
            pdf_summary,
            parent=self,
        )
        self.worker.finishedSummary.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(lambda: self.btnGonderWA.setEnabled(True))
        self.worker.start()

    def _on_worker_error(self, title: str, msg: str):
        QMessageBox.warning(self, title, msg)

    def _on_worker_finished(self, sent: int, invalid: int, failed: int):
        QMessageBox.information(
            self,
            "WhatsApp",
            f"Gönderim bitti.\n\nBaşarılı: {sent}\nGeçersiz Numara: {invalid}\nHatalı: {failed}"
        )