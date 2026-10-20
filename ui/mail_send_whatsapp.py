# -*- coding: utf-8 -*-
# ui/mail_send_whatsapp.py
from __future__ import annotations

import os, sys, re, time, sqlite3, urllib.parse, datetime as _dt
from typing import List, Tuple, Optional, Dict, Any

from services.whatsapp_queue.queue_v246 import (
    SafeWhatsAppQueue, queue_path_for, normalize_phone,
    PENDING, UI_UNVERIFIED, UNKNOWN, INVALID, FAILED, QueueBusyError
)

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QPushButton, QCheckBox,
    QLabel, QGroupBox, QRadioButton, QTextEdit, QMessageBox, QSizePolicy,
    QSplitter, QDialog, QListWidget, QSpinBox, QInputDialog, QApplication,
    QGridLayout, QScrollArea, QFrame, QComboBox
)

from services.whatsapp_queue.transport_v249 import (
    CHOICES, SELENIUM, BAILEYS_BULK, MANUAL_LINKS, validate_choice,
)
from services.whatsapp_queue.manual_handoff_v249 import open_one_pending_chat

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

def _get_check_icon_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    icon_path = os.path.join(assets_dir, "check_white.png")
    if not os.path.exists(icon_path):
        from PyQt6.QtGui import QImage, QPainter, QColor, QPen
        from PyQt6.QtCore import QPoint
        img = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(255, 255, 255), 3.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline([QPoint(7, 16), QPoint(13, 23), QPoint(25, 9)])
        p.end()
        img.save(icon_path)
    return icon_path.replace("\\", "/")

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
    """Bağımlılık yoksa ASLA pip yüklemeye çalışma; Windows EXE'yi bozma."""
    try:
        import selenium  # noqa: F401
        from selenium import webdriver  # noqa: F401
        from webdriver_manager.chrome import ChromeDriverManager  # noqa: F401
        return True
    except ImportError:
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
        """Tek gönderim denemesi. UI hareketi teslim kanıtı değildir.

        UI_UNVERIFIED: WhatsApp kutusu boşaldı, teslim doğrulanmadı.
        UNKNOWN: Gönder tuşuna basılmış olabilir ama sonucu belirsiz.
        FAILED: Gönderim girişimi başlamadan güvenli şekilde duruldu.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        attempted = False
        try:
            q = urllib.parse.quote(message)
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone_e164}&text={q}")
            w = WebDriverWait(self.driver, per_number_timeout)
            w.until(EC.presence_of_element_located((By.ID, "main")))
            # Arama kutusunu mesaj alanı sanmamak için sohbet alt bölümüne kısıtla.
            box = w.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#main footer [contenteditable='true']")))
            # WhatsApp arayüzünde gönder düğmesi değişmiş olabilir.
            # Bilinmeyen öğeye Enter uygulayıp yanlış kişiye gönderme.
            btn = self.driver.execute_script("""
                let footer = document.querySelector('#main footer');
                if (!footer) return null;
                let el = footer.querySelector('[data-testid="send"]') ||
                    footer.querySelector('[data-icon="send"]') ||
                    footer.querySelector('button[aria-label="Send"]') ||
                    footer.querySelector('button[aria-label="Gönder"]');
                return el && (el.closest('button') || el);
            """)
            if not btn or not box.text.strip():
                return FAILED
            # Kritik sınır: yalnızca BİR defa tıkla, belirsizde tekrar deneme.
            attempted = True
            self.driver.execute_script("arguments[0].click();", btn)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    if not box.text.strip():
                        return UI_UNVERIFIED
                except Exception:
                    return UNKNOWN
                time.sleep(.25)
            return UNKNOWN
        except Exception:
            return UNKNOWN if attempted else FAILED

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
    progress = pyqtSignal(str)                     # Kullanıcıya kısa kuyruk durumu

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
        parent=None,
        resume_batch_id: Optional[str] = None,
        transport_key: str = SELENIUM,
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
        self.resume_batch_id = resume_batch_id
        self.transport_key = transport_key

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

    def _prepare_snapshot(self, con: sqlite3.Connection) -> list[dict]:
        """Mesajları hazırlarken öğrenci kimliğini daima kaynaktan teyit et."""
        jobs: list[dict] = []
        has_filters = any((self.verilis_bugun, self.kontrol_bugun, self.kontrol_yarin,
                           self.kontrol_2gun, self.kontrol_gecmis))
        for sid, _adsoyad, raw_nums in self.rows_snapshot:
            stu = con.execute("SELECT * FROM ogrenci WHERE id=? AND aktif=1", (sid,)).fetchone()
            if stu is None:
                continue
            ad, soyad = str(stu["ad"] or ""), str(stu["soyad"] or "")
            text_i = self.text_base.replace("{ad}", ad).replace("{soyad}", soyad)
            if self.personal_mode:
                extras = []
                if self.add_stuinfo:
                    extras.append("• " + _ogrenci_bilgi_satiri(stu))
                if self.add_lastkume_full:
                    extras.append("\n" + _son_kume_detay(con, sid, emoji_headers=self.use_emoji_headers))
                if has_filters:
                    detail = _kumeler_detay_tarih_filtre(
                        con, sid, verilis_bugun=self.verilis_bugun,
                        kontrol_bugun=self.kontrol_bugun, kontrol_yarin=self.kontrol_yarin,
                        kontrol_2gun=self.kontrol_2gun, kontrol_gecmis=self.kontrol_gecmis,
                        emoji_headers=self.use_emoji_headers)
                    if not detail:
                        continue
                    extras.append("\n" + detail)
                elif self.add_allkume:
                    extras.append("\n" + _tum_kumeler_detay(con, sid, emoji_headers=self.use_emoji_headers))
                if extras:
                    text_i = (text_i + "\n\n" + "\n".join(extras)).strip()
            for raw in dict.fromkeys(raw_nums or [""]):
                jobs.append({"student_id": int(sid), "recipient": raw,
                             "message": text_i, "country_code": self.cc_text})
        return jobs

    def _log_legacy(self, con: sqlite3.Connection, job: dict, result: str) -> None:
        """Eski tabloda yalnızca OK/FAIL var. Doğrulanmamışa ASLA OK yazma."""
        try:
            sid = int(job["student_id"])
            stu = con.execute("SELECT ad, soyad FROM ogrenci WHERE id=?", (sid,)).fetchone()
            ad = str(stu["ad"] or "") if stu else ""
            soyad = str(stu["soyad"] or "") if stu else ""
            message = str(job["message"])
            num = "+" + str(job["recipient"])
            con.execute("""
                INSERT INTO whatsapp_log
                (ogrenci_id,numara,mesaj_onizleme,durum,hata,ts,
                 numaralar,mesaj,ogrenci_ad,ogrenci_soyad,ogrenci_adsoyad)
                VALUES(?,?,?,?,?,datetime('now'),?,?,?,?,?)""",
                (sid, num, message[:200], "FAIL", result,
                 num, message, ad, soyad, f"{ad} {soyad}"))
            con.commit()
        except Exception:
            # Esas detaylı günlük kuyruk SQLite içindedir; eski log uyumsuzluğu
            # hiçbir zaman gerçek gönderimi yeniden tetiklemez.
            try:
                con.rollback()
            except Exception:
                pass

    def run(self):
        """Kalıcı kuyrukla seri işle. Bir alıcının hatası diğerlerini silmez."""
        try:
            q = SafeWhatsAppQueue(queue_path_for(self.db_path, _appdata_dir()))
            lock_fd = q.acquire_lock()
            try:
                con = sqlite3.connect(self.db_path)
                con.row_factory = sqlite3.Row
            except BaseException:
                q.release_lock(lock_fd)
                raise
        except Exception as exc:
            self.error.emit("Veritabanı/Kuyruk Hatası", str(exc))
            return
        wa = None
        try:
            if self.resume_batch_id:
                batch_id = self.resume_batch_id
            else:
                try:
                    jobs = self._prepare_snapshot(con)
                except Exception as exc:
                    self.error.emit("Mesaj Hazırlama Hatası", str(exc))
                    return
                if not jobs:
                    self.error.emit("Boş Kuyruk", "Gönderilecek uygun mesaj bulunamadı.")
                    return
                try:
                    batch_id = q.create_batch(self.db_path, jobs)
                except Exception as exc:
                    self.error.emit("Kuyruk Oluşturulamadı", str(exc))
                    return
            # Otomatik tekrar yok: yarım kalan gönderim belirsiz olarak işaretlenir.
            recovered = q.recover_interrupted(batch_id)
            if recovered:
                self.progress.emit(f"{recovered} yarım kalan gönderimin sonucu belirsiz; tekrar denenmeyecek.")
            counts = q.counts(batch_id)
            pending = counts.get(PENDING, 0)
            self.progress.emit(f"Kuyruk kaydedildi: {pending} bekleyen alıcı.")
            if not pending:
                self.finishedSummary.emit(counts.get(UI_UNVERIFIED, 0), counts.get(INVALID, 0),
                                          counts.get(UNKNOWN, 0) + counts.get(FAILED, 0))
                return
            # Yöntem kesin olarak kullanıcı tarafından seçilir. Bilinmeyen veya
            # güvenlik karantinasındaki kanala otomatik geçiş yapılmaz.
            try:
                choice = validate_choice(self.transport_key)
            except Exception as exc:
                self.error.emit('Yöntem Kullanılamıyor', str(exc))
                return
            if self.transport_key in MANUAL_LINKS:
                # Öğretmenin her gerçek tıklaması yalnızca bir sohbet açar.
                # İzinli manuel devir bile gerçek gönderim onayı değildir.
                handoff = open_one_pending_chat(q, batch_id, self.transport_key)
                if handoff.attempted:
                    self.progress.emit(
                        'Bir sohbet açılmaya çalışıldı. WhatsApp Gönder öğretmene aittir. '
                        f'{handoff.pending} alıcı kuyrukta bekliyor.')
                counts = q.counts(batch_id)
                self.finishedSummary.emit(counts.get(UI_UNVERIFIED, 0),
                    counts.get(INVALID, 0), counts.get(UNKNOWN, 0) + counts.get(FAILED, 0))
                return
            if not choice.automated:
                self.error.emit('Yöntem', 'Bu yöntem otomatik gönderimi desteklemiyor.')
                return
            if not _try_import_selenium():
                self.error.emit("Gönderim motoru kullanılamıyor",
                    "Mesajlar güvenli kuyrukta saklandı. Bu sürümün otomatik gönderim "
                    "motoru Selenium gerektiriyor; uygulama onu kendiliğinden kurmayacak. "
                    "Mevcut WhatsApp masaüstü yöntemini kullanabilir veya "
                    "desteklenen başka bir taşıyıcı eklenmesini bekleyebilirsiniz.")
                return
            try:
                wa = WhatsAppWebClient(os.path.join(_appdata_dir(), "wa_web_profile"))
                wa.ensure_login(timeout_sec=150)
            except Exception as exc:
                self.error.emit("WhatsApp Oturumu Açılmadı",
                                f"Kuyruk korundu. WhatsApp Web/Chrome oturumunu kontrol edin: {exc}")
                return
            while True:
                try:
                    job = q.claim_next(batch_id)
                except QueueBusyError as exc:
                    self.error.emit("Kuyruk Meşgul", str(exc))
                    return
                if not job:
                    break
                try:
                    result = wa.send_text(job["recipient"], job["message"],
                                          per_number_timeout=self.per_chat_timeout)
                except Exception:
                    result = UNKNOWN
                if result not in (UI_UNVERIFIED, UNKNOWN, FAILED):
                    result = UNKNOWN
                try:
                    q.finish(job["id"], job["attempt_token"], result)
                except Exception as exc:
                    self.error.emit("Kuyruk Durumu Kaydedilemedi", str(exc))
                    return
                self._log_legacy(con, job, result)
                counts = q.counts(batch_id)
                self.progress.emit(
                    f"İşlendi: {sum(v for k,v in counts.items() if k != PENDING)} / {sum(counts.values())}; "
                    f"teslimi belirsiz: {counts.get(UI_UNVERIFIED,0) + counts.get(UNKNOWN,0)}")
                if result == FAILED:
                    # Arayüz bozulmuş olabilir; hepsine başarısız denemesi yapma.
                    self.error.emit("WhatsApp Arayüzü Değişmiş Olabilir",
                        "Gönderim öğesi bulunamadı. Diğer bekleyen işler kuyrukta korundu. "
                        "Uygulama güncellemesini/oturumu kontrol edin.")
                    break
                time.sleep(self.wait_between)
            counts = q.counts(batch_id)
            self.finishedSummary.emit(counts.get(UI_UNVERIFIED, 0), counts.get(INVALID, 0),
                                      counts.get(UNKNOWN, 0) + counts.get(FAILED, 0))
        finally:
            if wa:
                try: wa.close()
                except Exception: pass
            con.close()
            q.release_lock(lock_fd)


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
        chk_icon = _get_check_icon_path()
        style = """
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
            QCheckBox::indicator:checked {
                background-color: #2563eb;
                border-color: #2563eb;
                image: url("__CHECK_ICON__");
            }
            QRadioButton::indicator {
                border-radius: 8px;
            }
            QRadioButton::indicator:checked {
                border-color: #2563eb;
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #ffffff, stop:0.42 #ffffff, stop:0.43 #2563eb, stop:1 #2563eb);
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
        """.replace("__CHECK_ICON__", chk_icon)
        # V41: the WA composer remains an intentionally light panel; harmonize
        # its local scrollbars with that panel, including hover/pressed states.
        from ui.theme_scrollbar_v41 import scrollbar_qss
        style += scrollbar_qss('#f1f5f9', '#334155', '#2563eb', 10)
        self.setStyleSheet(style)
        
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

    def _open_baileys_test_v257(self):
        """Separate gated single-contact test; never switches the actual send transport."""
        from ui.baileys_test_v257 import BaileysSingleTestDialog
        dialog = BaileysSingleTestDialog(self)
        dialog.exec()

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
        self.tblWA.setHorizontalHeaderLabels(["#", "ÖĞRENCİ", "ÖĞR. TEL", "VELİ TEL1", "VELİ TEL2", "SEÇ"])
        hh = self.tblWA.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.tblWA.setColumnWidth(5, 52)
        self.tblWA.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tblWA.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tblWA.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tblWA.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lv.addWidget(self.tblWA, 1)

        bar = QHBoxLayout()
        self.btnHepsiWA = QPushButton("Tümünü İşaretle")
        self.btnGonderWA = QPushButton("📤 Gönder (WhatsApp)")
        bar.addWidget(self.btnHepsiWA)
        bar.addStretch(1)
        bar.addWidget(self.btnGonderWA)
        lv.addLayout(bar)
        # V24.9 - alternatifler: kullanıcı açıkça seçer, arka planda otomatik
        # taşıyıcı değiştirilmez. Baileys karantinadadır.
        method_line = QHBoxLayout()
        method_line.addWidget(QLabel('Gönderim yöntemi:'))
        self.cmbWAMethod = QComboBox()
        for choice in CHOICES:
            self.cmbWAMethod.addItem(choice.label, choice.key)
            if not choice.enabled:
                self.cmbWAMethod.model().item(self.cmbWAMethod.count() - 1).setEnabled(False)
        method_line.addWidget(self.cmbWAMethod, 1)
        lv.addLayout(method_line)
        self.lblWAMethodInfo = QLabel('')
        self.lblWAMethodInfo.setWordWrap(True)
        self.lblWAMethodInfo.setStyleSheet('color: #64748b; font-size: 11px;')
        lv.addWidget(self.lblWAMethodInfo)
        self.cmbWAMethod.currentIndexChanged.connect(self._on_method_changed)
        self._on_method_changed()

        spl.addWidget(left)

        # SAĞ: ayarlar + mesaj (Scrollable ve responsive)
        right_container = QWidget()
        right_container.setMinimumWidth(500)
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
        nv.setSpacing(16)
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
        optGrp.setMinimumHeight(180)
        og = QGridLayout(optGrp)
        og.setContentsMargins(12, 12, 12, 12)
        og.setHorizontalSpacing(20)
        og.setVerticalSpacing(8)

        self.chkStuInfoWA = QCheckBox("Öğrenci bilgisi eklensin")
        self.chkStuInfoWA.setToolTip("Mesaja öğrencinin sınıf, okul ve veli irtibat bilgilerini ekler.")
        self.chkLastKumeWA = QCheckBox("Son ödev kümesi (Tamamı)")
        self.chkLastKumeWA.setToolTip("Son verilen ödev kümesindeki tüm ders ve görevleri eksiksiz ekler.")
        self.chkAllKumeWA = QCheckBox("Tüm ödev kümeleri ve içerik")
        self.chkAllKumeWA.setToolTip("Öğrenciye tanımlı tüm ödev kümelerini ve içeriklerini detaylı ekler.")
        self.chkEmojiHeaders = QCheckBox("Küme başlıklarına emoji")
        self.chkEmojiHeaders.setToolTip("Ödev kümelerinin başlıklarına görsel ikon/emoji ekler.")
        self.chkPdfSummary = QCheckBox("PDF özet raporu (Beta)")
        self.chkPdfSummary.setToolTip("Her öğrenci için ödev özetini ek PDF dosyası olarak hazırlar.")

        self.chkBugunVerilen = QCheckBox("Bugün verilen ödevler")
        self.chkBugunVerilen.setToolTip("Yalnızca bugün tarihiyle verilmiş olan ödev kümelerini içerir.")
        self.chkKontrolBugun = QCheckBox("Kontrolü BUGÜN olanlar")
        self.chkKontrolBugun.setToolTip("Kontrol tarihi bugün olan ödevleri filtreler.")
        self.chkKontrolYarin = QCheckBox("Kontrolü YARIN olanlar")
        self.chkKontrolYarin.setToolTip("Kontrol tarihi yarın olan ödevleri filtreler.")
        self.chkKontrol2Gun = QCheckBox("Kontrolü 2 gün sonra")
        self.chkKontrol2Gun.setToolTip("Kontrol tarihi iki gün sonra olan ödevleri filtreler.")
        self.chkKontrolGecmis = QCheckBox("Kontrolü GEÇMİŞ (gecikmiş)")
        self.chkKontrolGecmis.setToolTip("Kontrol tarihi geçmiş ancak henüz tamamlanmamış ödevleri filtreler.")

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
            "ℹ️ Selenium yönteminde ilk kullanımda WhatsApp Web QR eşleştirmesi gerekebilir.\n"
            "Masaüstü/Web bağlantıları ise yalnızca sohbeti hazırlar; gönderme kullanıcıdadır."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #64748b; font-size: 11px;")
        rv.addWidget(info)

        right_scroll.setWidget(right_body)
        rc_lay.addWidget(right_scroll, 1)

        spl.addWidget(right_container)
        spl.setStretchFactor(0, 4)
        spl.setStretchFactor(1, 3)
        spl.setSizes([640, 480])

        # Alt bar: Kuyruk ve Ayarlar butonları
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 4, 0, 0)
        bottom.setSpacing(10)
        self.lblKuyrukWA = QLabel("Mesaj sonucu WhatsApp teslimatı doğrulanmadan başarılı sayılmaz.")
        self.lblKuyrukWA.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lblKuyrukWA.setWordWrap(True)
        bottom.addWidget(self.lblKuyrukWA, 1)
        self.btnBaileysTest = QPushButton("🧪 Baileys Testi (tek alıcı)")
        self.btnKuyrukWA = QPushButton("📋 Kuyruğu Gör / Sürdür")
        self.btnKuyrukSifirlaWA = QPushButton("🗑️ Kuyruğu Sıfırla")
        self.btnSettingsWA = QPushButton("⚙️ Ayarlar / Şablonlar")
        bottom.addWidget(self.btnBaileysTest)
        bottom.addWidget(self.btnKuyrukWA)
        bottom.addWidget(self.btnKuyrukSifirlaWA)
        bottom.addWidget(self.btnSettingsWA)
        root.addLayout(bottom)

        # sinyaller
        self.btnBulWA.clicked.connect(self._do_search_wa)
        self.btnHepsiWA.clicked.connect(self._toggle_all_wa)
        self.btnGonderWA.clicked.connect(self._on_send_clicked)
        self.btnBaileysTest.clicked.connect(self._open_baileys_test_v257)
        self.btnKuyrukWA.clicked.connect(self._on_queue_clicked)
        self.btnKuyrukSifirlaWA.clicked.connect(self._on_queue_reset_clicked)
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

    def _selected_transport(self) -> str:
        return str(self.cmbWAMethod.currentData() or SELENIUM)

    def _on_method_changed(self, *args):
        try:
            choice = validate_choice(self._selected_transport())
            self.lblWAMethodInfo.setText(choice.explanation +
                ' Yöntem değişikliği bekleyen/belirsiz işleri yeniden göndermez.')
            self.btnGonderWA.setEnabled(not (self.worker and self.worker.isRunning()))
        except Exception:
            self.lblWAMethodInfo.setText('Bu yöntem güvenlik kontrolü nedeniyle kapalıdır.')
            self.btnGonderWA.setEnabled(False)

    def _on_queue_clicked(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Kuyruk", "Gönderim zaten sürüyor.")
            return
        if self._selected_transport() == BAILEYS_BULK:
            from services.whatsapp_queue.baileys_bulk_v258 import open_baileys_queue
            try:
                q = open_baileys_queue(self.db_path, _appdata_dir())
            except Exception as exc:
                QMessageBox.warning(self, 'Baileys şifreli kuyruk', str(exc))
                return
        else:
            q = SafeWhatsAppQueue(queue_path_for(self.db_path, _appdata_dir()))
        # Önce bekleyen işler; yalnızca yoksa son tamamlanmış parti.
        batch = q.current_batch(self.db_path) or q.latest_batch(self.db_path)
        if not batch:
            QMessageBox.information(self, "Kuyruk", "Henüz kayıtlı WhatsApp gönderim kuyruğu yok.")
            return
        # Geçmiş süreç yarım kaldıysa kilit altında belirsiz olarak işaretle;
        # bu kayıtları hiçbir koşulda otomatik yeniden gönderme.
        try:
            fd = q.acquire_lock()
            try:
                q.recover_interrupted(batch)
            finally:
                q.release_lock(fd)
        except QueueBusyError as exc:
            QMessageBox.information(self, "Kuyruk Meşgul", str(exc))
            return
        # V25.8: A previously saved Baileys queue MUST NOT be resumed using
        # Selenium/Desktop/Web. Likewise a legacy queue cannot be switched to
        # Baileys without fresh approval and an attributable transport marker.
        from services.whatsapp_queue.baileys_bulk_v258 import batch_transport, TRANSPORT_MARKER
        existing_method = batch_transport(q, batch)
        requested_baileys = self._selected_transport() == BAILEYS_BULK
        if (existing_method == TRANSPORT_MARKER) != requested_baileys:
            QMessageBox.warning(self, 'Kuyruk yöntem uyuşmazlığı',
                'Bu kuyruk farklı bir WhatsApp gönderim yöntemiyle oluşturuldu. '
                'Lütfen ilk gönderim yöntemini seçin. Sonucu belirsiz işler tekrar gönderilmez.')
            return
        counts = q.counts(batch)
        pending = counts.get(PENDING, 0)
        lines = [f"Bekleyen: {pending}",
                 f"Numara geçersiz: {counts.get(INVALID, 0)}",
                 f"Arayüzce işlenen (teslim belirsiz): {counts.get(UI_UNVERIFIED, 0)}",
                 f"Sonucu belirsiz: {counts.get(UNKNOWN, 0)}",
                 f"Gönderilmedi: {counts.get(FAILED, 0)}"]
        errors = [r for r in q.rows(batch) if r['state'] in (INVALID, UNKNOWN, FAILED)]
        if errors:
            lines.append("\nİncelenecek alıcılar (son 4 hane):")
            for row in errors[:8]:
                lines.append(f"• ***{str(row['recipient'])[-4:]} — {row['state']}")
            if len(errors) > 8:
                lines.append(f"… {len(errors)-8} kayıt daha")
        summary = "\n".join(lines)
        if not pending:
            msg = QMessageBox(self)
            msg.setWindowTitle("Son Gönderim Sonuçları")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(summary + "\n\nTeslim durumları kişisel WhatsApp üzerinden kesin doğrulanamaz.")
            btn_ok = msg.addButton("Tamam", QMessageBox.ButtonRole.AcceptRole)
            btn_clear = msg.addButton("🗑️ Geçmişi / Kuyruğu Sıfırla", QMessageBox.ButtonRole.DestructiveRole)
            msg.exec()
            if msg.clickedButton() == btn_clear:
                confirm = QMessageBox.question(
                    self, "Kuyruğu Temizle",
                    "Geçmiş gönderim sonuçları kuyruktan tamamen temizlensin mi?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if confirm == QMessageBox.StandardButton.Yes:
                    try:
                        q.purge_batch(batch)
                        q.clean_stale_lock()
                        self.lblKuyrukWA.setText("WhatsApp kuyruk geçmişi sıfırlandı.")
                        QMessageBox.information(self, "Temizlendi", "WhatsApp kuyruğu başarıyla sıfırlandı.")
                    except Exception as exc:
                        QMessageBox.warning(self, "Hata", f"Temizleme hatası: {exc}")
            return
        manual_reminder = ("\n\nSeçili manuel bağlantı yöntemi HER TIKLAMADA yalnızca BİR sohbet açar. "
            "Gönderme işlemini siz yaparsınız." if self._selected_transport() in MANUAL_LINKS else "")

        msg = QMessageBox(self)
        msg.setWindowTitle("Kaydedilmiş Kuyruğu Sürdür")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(summary + "\n\nBekleyen mesajlar eski içerikleriyle işlenecek. "
            "Sonucu belirsiz mesajlar tekrar gönderilmeyecek." + manual_reminder + "\n\nDevam edilsin mi?")

        btn_yes = msg.addButton("Devam Et (Sürdür)", QMessageBox.ButtonRole.AcceptRole)
        btn_reset = msg.addButton("🗑️ Kuyruğu Sıfırla / İptal Et", QMessageBox.ButtonRole.DestructiveRole)
        btn_no = msg.addButton("Vazgeç / Kapat", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_yes)

        msg.exec()
        clicked = msg.clickedButton()

        if clicked == btn_reset:
            confirm = QMessageBox.question(
                self,
                "Kuyruğu Sıfırla",
                f"Kuyruktaki {pending} adet bekleyen mesaj iptal edilecek ve kuyruk tamamen sıfırlanacaktır.\n\n"
                "Bu işlemi onaylıyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                try:
                    q.purge_batch(batch)
                    q.clean_stale_lock()
                    self.lblKuyrukWA.setText("WhatsApp gönderim kuyruğu sıfırlandı.")
                    QMessageBox.information(self, "Kuyruk Sıfırlandı", "WhatsApp gönderim kuyruğu başarıyla temizlendi ve sıfırlandı.")
                except Exception as exc:
                    QMessageBox.warning(self, "Hata", f"Kuyruk sıfırlanırken hata oluştu: {exc}")
            return
        elif clicked != btn_yes:
            return

        if requested_baileys:
            self._open_baileys_bulk_v258(resume_batch=batch)
        else:
            self._start_worker(resume_batch_id=batch)

    def _on_queue_reset_clicked(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Kuyruk Meşgul", "WhatsApp gönderimi devam ederken kuyruk sıfırlanamaz. Lütfen önce gönderimin bitmesini bekleyin.")
            return
        if self._selected_transport() == BAILEYS_BULK:
            from services.whatsapp_queue.baileys_bulk_v258 import open_baileys_queue
            try:
                q = open_baileys_queue(self.db_path, _appdata_dir())
            except Exception as exc:
                QMessageBox.warning(self, 'Baileys şifreli kuyruk', str(exc))
                return
        else:
            q = SafeWhatsAppQueue(queue_path_for(self.db_path, _appdata_dir()))

        batch = q.current_batch(self.db_path) or q.latest_batch(self.db_path)
        if not batch:
            QMessageBox.information(self, "Kuyruk Boş", "Temizlenecek aktif veya kayıtlı WhatsApp gönderim kuyruğu bulunmuyor.")
            return

        counts = q.counts(batch)
        pending = counts.get(PENDING, 0)
        total = sum(counts.values())

        reply = QMessageBox.question(
            self,
            "Kuyruğu Sıfırla",
            f"Kayıtlı WhatsApp kuyruğu sıfırlanacak:\n\n"
            f"• Bekleyen Mesajlar: {pending}\n"
            f"• Toplam Kuyruk Kaydı: {total}\n\n"
            "Kuyruktaki işler iptal edilecek ve kuyruk tamamen temizlenecektir.\n\n"
            "Bu işlemi onaylıyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                q.purge_batch(batch)
                q.clean_stale_lock()
                self.lblKuyrukWA.setText("WhatsApp gönderim kuyruğu başarıyla sıfırlandı.")
                QMessageBox.information(self, "Kuyruk Sıfırlandı", "WhatsApp gönderim kuyruğu başarıyla temizlendi ve sıfırlandı.")
            except Exception as exc:
                QMessageBox.warning(self, "Hata", f"Kuyruk sıfırlanırken hata oluştu: {exc}")

    def _start_worker(self, resume_batch_id=None):
        if self.worker and self.worker.isRunning():
            return
        if resume_batch_id is not None:
            self.btnGonderWA.setEnabled(False)
            self.worker = WhatsAppWorker(self.db_path, [], "", "90", False, False,
                False, False, False, False, False, False, False, 45, 2,
                False, False, parent=self, resume_batch_id=resume_batch_id,
                transport_key=self._selected_transport())
            self.worker.finishedSummary.connect(self._on_worker_finished)
            self.worker.error.connect(self._on_worker_error)
            self.worker.progress.connect(self.lblKuyrukWA.setText)
            self.worker.finished.connect(lambda: self.btnGonderWA.setEnabled(True))
            self.worker.start()

    # --- Gönder butonu ---
    def _on_send_clicked(self):
        try:
            choice = validate_choice(self._selected_transport())
        except Exception as exc:
            QMessageBox.warning(self, 'Yöntem Kullanılamıyor', str(exc))
            return
        if self._selected_transport() in MANUAL_LINKS:
            reply = QMessageBox.question(self, 'Manuel WhatsApp Bağlantısı',
                'Bu yöntem 30 mesajı kendi kendine GÖNDERMEZ. Her seferinde '
                'yalnızca bir sohbeti açar. Gönder tuşunu siz kullanırsınız. '
                'İşlenen alıcının sonucu BELİRSİZ kalır ve otomatik tekrar edilmez. '
                'Devam edilsin mi?')
            if reply != QMessageBox.StandardButton.Yes:
                return
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Gönderim", "Başka bir gönderim işlemi sürüyor.")
            return
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

        # Korumalı Baileys kuyruğunda bekleyen işler varken başka kanaldan
        # aynı numaralara yanlışlıkla ikinci otomatik işlem başlatma.
        try:
            from services.whatsapp_queue.baileys_bulk_v258 import open_baileys_queue
            if sys.platform == 'win32':
                _secure_q = open_baileys_queue(self.db_path, _appdata_dir())
                if _secure_q.current_batch(self.db_path):
                    QMessageBox.warning(self, 'Baileys bekleyen kuyruk',
                        'Önce Baileys yöntemini seçerek bekleyen işleri gözden geçirin. '
                        'Yeni bir parti başlatılmadı.')
                    return
        except Exception as exc:
            QMessageBox.warning(self, 'Baileys kuyruk doğrulaması', str(exc))
            return

        # Daha önce başlatılmış gönderimler kaybolmadan yeni bir toplu gönderime
        # geçilirse aynı veliye istemeden ikinci mesaj gitme riski doğar.
        try:
            _q = SafeWhatsAppQueue(queue_path_for(self.db_path, _appdata_dir()))
            _prior = _q.current_batch(self.db_path)
            if _prior and (_q.counts(_prior).get(PENDING, 0) or _q.counts(_prior).get("DENENIYOR", 0)):
                QMessageBox.warning(self, "Bekleyen WhatsApp Kuyruğu",
                    "Önceki gönderimden bekleyen mesajlar var. "
                    "Lütfen önce 'Kuyruğu Gör / Sürdür' bölümünü açın. "
                    "Yeni bir parti oluşturulmadı.")
                return
        except Exception as exc:
            QMessageBox.warning(self, "Kuyruk Kontrolü", f"Güvenli kontrol yapılamadı: {exc}")
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

        if self._selected_transport() == BAILEYS_BULK:
            # Reuse EXACTLY the existing per-student message preparation;
            # do not touch either Homework Follow-up or Homework Control saves.
            preparer = WhatsAppWorker(
                self.db_path, rows_snapshot, text_base, cc_text, add_stuinfo,
                add_lastkume_full, add_allkume, verilis_bugun, kontrol_bugun,
                kontrol_yarin, kontrol_2gun, kontrol_gecmis, personal_mode,
                per_chat_timeout, wait_between, use_emoji_headers, pdf_summary,
                parent=self, transport_key=BAILEYS_BULK)
            try:
                with sqlite3.connect(self.db_path) as reader:
                    reader.row_factory = sqlite3.Row
                    jobs = preparer._prepare_snapshot(reader)
                self._open_baileys_bulk_v258(raw_jobs=jobs)
            except Exception as exc:
                QMessageBox.warning(self, 'Baileys ön kontrolü', str(exc))
            return

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
            transport_key=self._selected_transport(),
        )
        self.worker.finishedSummary.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.progress.connect(self.lblKuyrukWA.setText)
        self.worker.finished.connect(lambda: self.btnGonderWA.setEnabled(True))
        self.worker.start()

    def _on_worker_error(self, title: str, msg: str):
        QMessageBox.warning(self, title, msg)

    def _on_worker_finished(self, sent: int, invalid: int, failed: int):
        QMessageBox.information(
            self,
            "WhatsApp",
            f"İşlem sona erdi.\n\nArayüzde gönderim denemesi görülen (teslim onayı yok): {sent}"
            f"\nGeçersiz Numara: {invalid}\nBelirsiz / İşlenemeyen: {failed}"
            "\n\nBekleyen mesajlar kuyrukta korunur. Kuyruğu Gör / Sürdür bölümünü kullanabilirsiniz."
        )

    def _open_baileys_bulk_v258(self, *, raw_jobs=None, resume_batch=None):
        """Independent modal wizard; current send transport untouched."""
        try:
            from ui.baileys_bulk_v258 import BaileysBulkDialog
            dialog = BaileysBulkDialog(self, self.db_path, _appdata_dir(),
                                       raw_jobs=raw_jobs, resume_batch=resume_batch)
            dialog.exec()
            self.lblKuyrukWA.setText('Baileys toplu gönderimi: Kuyruğu Gör / Sürdür üzerinden sonuçları kontrol edin.')
        except Exception as exc:
            QMessageBox.warning(self, 'Baileys toplu pilotu', str(exc))