# -*- coding: utf-8 -*-
# ui/mail_send.py
from __future__ import annotations

import os, sys, re, ssl, smtplib, sqlite3
from typing import List, Optional

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
    QMessageBox, QSplitter, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QCheckBox, QComboBox, QGroupBox, QFormLayout, QRadioButton, QSizePolicy, QTabWidget,
    QFrame, QWizard, QWizardPage, QGridLayout, QApplication, QScrollArea
)
from PyQt6.QtGui import QColor, QFont

# >>> WHATSAPP SEKMEYİ DIŞARIDAN AL
from ui.mail_send_whatsapp import WhatsAppTab

# ========== ORTAK: DB yardımcıları ==========
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

def _connect_db() -> sqlite3.Connection:
    try:
        import db
        if hasattr(db, "get_conn"):
            con = db.get_conn(); con.row_factory = sqlite3.Row; return con
        if hasattr(db, "con"):
            con = db.con; con.row_factory = sqlite3.Row; return con
    except Exception:
        pass
    path = _default_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path); con.row_factory = sqlite3.Row
    return con

def _ayar_get(con: sqlite3.Connection, key: str, default: Optional[str]=None) -> Optional[str]:
    try:
        r = con.execute("SELECT deger FROM ayar WHERE anahtar=?", (key,)).fetchone()
        return r["deger"] if r else default
    except Exception:
        return default

def _ayar_set(con: sqlite3.Connection, key: str, val: str) -> None:
    con.execute(
        "INSERT INTO ayar(anahtar,deger,guncel_tarih) VALUES(?,?,datetime('now')) "
        "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger, guncel_tarih=datetime('now')",
        (key, val))
    con.commit()

# ========== ORTAK: Öğrenci veri/özet ==========
def _ogrenci_ara(con: sqlite3.Connection, q: str):
    q = f"%{(q or '').strip()}%"
    return con.execute("""
        SELECT id, ad, soyad, ogr_mail, veli_mail, ana_grup, alt_grup
        FROM ogrenci
        WHERE aktif=1 AND (ad || ' ' || soyad LIKE ? OR ogr_mail LIKE ? OR veli_mail LIKE ?)
        ORDER BY ad, soyad
    """, (q, q, q)).fetchall()

def _ogrenci_bilgi_satiri(row) -> str:
    return f"{row['ad']} {row['soyad']}  [{row['ana_grup'] or ''}-{row['alt_grup'] or ''}]"

def _son_kume_ozeti(con: sqlite3.Connection, ogr_id: int) -> str:
    kume = con.execute("""
        SELECT id, verilis_tarihi, bitis_tarihi
        FROM odev_kume
        WHERE ogrenci_id=?
        ORDER BY date(verilis_tarihi) DESC, id DESC
        LIMIT 1
    """, (ogr_id,)).fetchone()
    if not kume: return "Kayıtlı ödev kümesi bulunamadı."
    say = con.execute("""
        SELECT COUNT(*) AS toplam,
        SUM(CASE WHEN durum='tamam' THEN 1 ELSE 0 END) AS bitti
        FROM odev WHERE kume_id=?
    """, (kume["id"],)).fetchone()
    toplam = say["toplam"] or 0; bitti = say["bitti"] or 0
    yuzde  = int(round(100.0*(bitti/ toplam), 0)) if toplam else 0
    return (f"Son Küme #{kume['id']} (Veriliş: {kume['verilis_tarihi']}, "
            f"Bitiş: {kume['bitis_tarihi'] or '-'}) Toplam {toplam}, Tamam {bitti} (%{yuzde}).").strip()

def _tum_kumeler_detay(con: sqlite3.Connection, ogr_id: int) -> str:
    kumeler = con.execute("""
        SELECT id, verilis_tarihi, bitis_tarihi
        FROM odev_kume
        WHERE ogrenci_id=?
        ORDER BY date(verilis_tarihi) DESC, id DESC
    """, (ogr_id,)).fetchall()
    if not kumeler: return "Ödev kümesi bulunamadı."
    lines: List[str] = []
    for k in kumeler:
        lines.append(f"Küme #{k['id']} (Veriliş:{k['verilis_tarihi']} Bitiş:{k['bitis_tarihi'] or '-'})")
        sat = con.execute("""
            SELECT ders, kitap_ad AS kitap, konu_ad AS konu, durum
            FROM odev WHERE kume_id=? ORDER BY ders, kitap_ad, konu_ad
        """, (k["id"],)).fetchall()
        if not sat: lines.append("  - (Görev yok)")
        else:
            for s in sat:
                lines.append(f"  - {s['ders']} | {s['kitap']}: {s['konu']} [{s['durum']}]")
        lines.append("")
    return "\n".join(lines).rstrip()

# ========== E-POSTA ALTYAPISI ==========
PROVIDERS = {
    "Gmail":            {"host": "smtp.gmail.com",      "port": 587, "security": "TLS"},
    "Outlook/Hotmail":  {"host": "smtp.office365.com",  "port": 587, "security": "TLS"},
    "Yahoo":            {"host": "smtp.mail.yahoo.com", "port": 465, "security": "SSL"},
    "Yandex":           {"host": "smtp.yandex.com",     "port": 465, "security": "SSL"},
    "Özel":             {"host": "",                    "port": 587, "security": "TLS"},
}

class SmtpSettings:
    def __init__(self, provider="Gmail", host="", port=587, security="TLS",
                 user="", password="", display_name="", bcc_self=False):
        self.provider = provider; self.host = host; self.port = int(port)
        self.security = security; self.user = user; self.password = password
        self.display_name = display_name; self.bcc_self = bcc_self

    @staticmethod
    def load(con: sqlite3.Connection) -> "SmtpSettings":
        provider = _ayar_get(con, "mail.provider", "Gmail") or "Gmail"
        p = PROVIDERS.get(provider, PROVIDERS["Gmail"])
        host = _ayar_get(con, "mail.host", p["host"]) or p["host"]
        port = int(_ayar_get(con, "mail.port", str(p["port"])) or p["port"])
        security = _ayar_get(con, "mail.security", p["security"]) or p["security"]
        user = _ayar_get(con, "mail.user", "") or ""
        password = _ayar_get(con, "mail.password", "") or ""
        display_name = _ayar_get(con, "mail.display_name", "") or ""
        bcc_self = (_ayar_get(con, "mail.bcc_self", "0") == "1")
        return SmtpSettings(provider, host, port, security, user, password, display_name, bcc_self)

    def save(self, con: sqlite3.Connection) -> None:
        _ayar_set(con, "mail.provider", self.provider)
        _ayar_set(con, "mail.host", self.host)
        _ayar_set(con, "mail.port", str(self.port))
        _ayar_set(con, "mail.security", self.security)
        _ayar_set(con, "mail.user", self.user)
        _ayar_set(con, "mail.password", self.password)
        _ayar_set(con, "mail.display_name", self.display_name)
        _ayar_set(con, "mail.bcc_self", "1" if self.bcc_self else "0")

class SmtpClient:
    def __init__(self, s: SmtpSettings): self.s = s

    def send(self, to_list: List[str], subject: str, html_body: str, text_fallback: str="") -> None:
        if not self.s.user or not self.s.password:
            raise RuntimeError("Gönderen adres/parola ayarlı değil.")
        if not to_list:
            raise RuntimeError("En az bir alıcı gerekli.")
        bcc = [self.s.user] if self.s.bcc_self else []
        msg = MIMEMultipart("alternative")
        from_header = f"{self.s.display_name} <{self.s.user}>" if self.s.display_name else self.s.user
        msg["From"] = from_header; msg["To"] = ", ".join(to_list); msg["Subject"] = subject
        if not text_fallback:
            text_fallback = re.sub("<[^<]+?>", "", html_body).strip()
        msg.attach(MIMEText(text_fallback, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        if self.s.security.upper() == "SSL":
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.s.host, self.s.port, context=ctx, timeout=30) as server:
                server.login(self.s.user, self.s.password)
                server.sendmail(self.s.user, to_list + bcc, msg.as_string())
        else:
            with smtplib.SMTP(self.s.host, self.s.port, timeout=30) as server:
                try:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.login(self.s.user, self.s.password)
                    server.sendmail(self.s.user, to_list + bcc, msg.as_string())
                except smtplib.SMTPException as e:
                    # Bazı durumlarda SSL ile ilgili hata olabilir, Exception fırlat
                    raise e


# ========== ANA DİYALOG ==========
class MailGonderDialog(QDialog):
    def __init__(self, ebeveyn=None, con: Optional[sqlite3.Connection]=None):
        super().__init__(ebeveyn)
        self.setWindowTitle("İletişim – Mail & WhatsApp")
        
        # Ekran boyutuna duyarlı akıllı boyutlandırma (laptop ekranlarında butonların taşmasını önler)
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            w = min(1200, max(900, int(avail.width() * 0.92)))
            h = min(670, max(520, int(avail.height() * 0.86)))
            self.resize(w, h)
        else:
            self.resize(1100, 640)
        self.setMinimumSize(860, 490)
        self.con = con or _connect_db()
        self.smtp = SmtpSettings.load(self.con)
        
        self._apply_modern_styles()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # E-posta sekmesi
        self.emailTab = self._build_email_tab()
        self.tabs.addTab(self.emailTab, "✉️ E-posta")

        # WhatsApp sekmesi
        self.tabs.addTab(WhatsAppTab(self.con), "💬 WhatsApp")

    def _apply_modern_styles(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
                color: #1e293b;
            }
            /* --- Tab Widget --- */
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                background: #f8fafc;
                border-radius: 8px;
                top: -1px; 
            }
            QTabBar::tab {
                background: #e2e8f0;
                border: 1px solid #cbd5e1;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                color: #475569;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #2563eb; 
                border-bottom-color: #ffffff;
            }
            
            /* --- Tablolar --- */
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #f1f5f9;
                selection-background-color: #eff6ff; 
                selection-color: #1e293b;
                outline: none;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:focus {
                outline: none;
                border: none; 
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 12px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 700;
                color: #475569;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            /* --- Butonlar --- */
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                color: #334155;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
            QPushButton#btnSend {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: white; 
                border: 1px solid #1d4ed8;
                font-weight: 700;
                font-size: 13px;
                border-radius: 8px;
                padding: 8px 18px;
            }
            QPushButton#btnSend:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
                border-color: #2563eb;
            }
            QPushButton#btnClose {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton#btnClose:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
            QPushButton#btnBul {
                background-color: #2563eb; 
                color: white; 
                border: 1px solid #2563eb;
            }
            QPushButton#btnBul:hover {
                background-color: #1d4ed8;
            }
            QPushButton#btnEkle {
                background-color: #10b981; 
                color: white; 
                border: 1px solid #10b981;
            }
            QPushButton#btnEkle:hover {
                background-color: #059669;
            }

            /* --- Inputlar --- */
            QLineEdit, QTextEdit, QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px;
                background-color: #ffffff;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 2px solid #3b82f6; 
            }

            /* --- GroupBox --- */
            QGroupBox {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 14px;
                font-weight: bold;
                background-color: #ffffff;
                padding: 10px 12px 8px 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                top: 0px; 
                padding: 0 6px;
                color: #2563eb;
                background-color: #ffffff;
                font-size: 12px;
            }

            /* --- Checkbox & Radio --- */
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
        """)

    # ======== E-POSTA SEKME ========
    def _build_email_tab(self) -> QWidget:
        w = QWidget(); root = QVBoxLayout(w)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        
        # Üst Bar
        tb = QHBoxLayout()
        self.btnAyar = QPushButton("⚙️ Ayarlar (Sihirbaz)"); self.btnYardim = QPushButton("❓ Yardım")
        tb.addWidget(self.btnAyar); tb.addWidget(self.btnYardim); tb.addStretch(1)
        root.addLayout(tb)

        spl = QSplitter(Qt.Orientation.Horizontal); 
        spl.setHandleWidth(2)
        root.addWidget(spl, 1)

        # SOL: liste
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0,0,10,0)
        lv.setSpacing(8)
        
        # Arama
        srch = QHBoxLayout()
        self.txtAra = QLineEdit(); self.txtAra.setPlaceholderText("Öğrenci ara: Ad Soyad / e-posta…")
        self.btnBul = QPushButton("🔍 Ara"); 
        self.btnBul.setObjectName("btnBul")
        srch.addWidget(self.txtAra, 1); srch.addWidget(self.btnBul)
        lv.addLayout(srch)

        # Tablo
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["#", "Öğrenci", "Öğr. Mail", "Veli Mail", "Öğr.", "Veli"])
        hh = self.tbl.horizontalHeader()
        
        # Sütun ayarları
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # İsim
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive); self.tbl.setColumnWidth(2, 125)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive); self.tbl.setColumnWidth(3, 125)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed); self.tbl.setColumnWidth(4, 48)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed); self.tbl.setColumnWidth(5, 48)

        # Tablo stil
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setShowGrid(False)  
        self.tbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbl.verticalHeader().setDefaultSectionSize(34) # Kompakt & şık satır yüksekliği
        
        lv.addWidget(self.tbl, 1)

        # Alt Bar
        btnbar = QHBoxLayout()
        self.btnHepsiniSec = QPushButton("Tümünü İşaretle")
        self.btnEkle = QPushButton("Seçili Adresleri Alıcıya Ekle →")
        self.btnEkle.setObjectName("btnEkle")
        self.btnEkle.setMinimumHeight(36)
        btnbar.addWidget(self.btnHepsiniSec); btnbar.addStretch(1); btnbar.addWidget(self.btnEkle)
        lv.addLayout(btnbar)
        
        spl.addWidget(left)

        # SAĞ: içerik (Scrollable ve her çözünürlükte taşmaz)
        right_container = QWidget()
        rc_lay = QVBoxLayout(right_container)
        rc_lay.setContentsMargins(10, 0, 0, 0)
        rc_lay.setSpacing(6)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        right_body = QWidget()
        right_body.setStyleSheet("background: transparent;")
        rv = QVBoxLayout(right_body)
        rv.setContentsMargins(0, 0, 8, 4)
        rv.setSpacing(8)
        
        # Gönderim Modu
        modeGrp = QGroupBox("Gönderim Modu"); mh = QHBoxLayout(modeGrp)
        mh.setContentsMargins(10, 6, 10, 6)
        self.rdToplu = QRadioButton("Toplu (aynı içerik)")
        self.rdKisisel = QRadioButton("Kişiselleştirilmiş (her öğrenciye kendi kümesi)")
        self.rdToplu.setChecked(True)
        mh.addWidget(self.rdToplu); mh.addWidget(self.rdKisisel); mh.addStretch(1)
        rv.addWidget(modeGrp)

        # Inputs (Alıcı ve Konu yan yana 2 sütunlu kompakt ızgara - dikeyde 50px kazandırır)
        grid_inputs = QGridLayout()
        grid_inputs.setContentsMargins(0, 0, 0, 0)
        grid_inputs.setHorizontalSpacing(10)
        grid_inputs.setVerticalSpacing(2)

        l_to = QLabel("Alıcı(lar):"); l_to.setStyleSheet("color:#64748b; font-weight:700; font-size:11px;")
        l_sub = QLabel("Konu:"); l_sub.setStyleSheet("color:#64748b; font-weight:700; font-size:11px;")
        self.txtTo = QLineEdit(); self.txtTo.setPlaceholderText("Toplu modda: alıcı(lar) (virgülle çoklu)")
        self.txtSub = QLineEdit(); self.txtSub.setPlaceholderText("Konu veya şablondan otomatik")

        grid_inputs.addWidget(l_to, 0, 0)
        grid_inputs.addWidget(l_sub, 0, 1)
        grid_inputs.addWidget(self.txtTo, 1, 0)
        grid_inputs.addWidget(self.txtSub, 1, 1)
        rv.addLayout(grid_inputs)

        # İçerik Seçenekleri (2x2 grid ile ferah görünüm)
        optGrp = QGroupBox("İçerik Seçenekleri")
        optGrp.setMinimumHeight(130)
        ov = QVBoxLayout(optGrp)
        ov.setContentsMargins(10, 8, 10, 8)
        ov.setSpacing(6)
        
        rowTempl = QHBoxLayout()
        lbl_t_hdr = QLabel("Hızlı Şablon:"); lbl_t_hdr.setStyleSheet("color:#64748b; font-weight:600; font-size:11px;")
        self.cmbTemplate = QComboBox(); self.cmbTemplate.addItems(["Şablon seç…", "Haftalık ödev durumu", "Genel duyuru"])
        rowTempl.addWidget(lbl_t_hdr); rowTempl.addWidget(self.cmbTemplate, 1)
        ov.addLayout(rowTempl)
        
        grid_opts = QGridLayout()
        grid_opts.setHorizontalSpacing(16)
        grid_opts.setVerticalSpacing(8)

        self.chkStuInfo  = QCheckBox("Öğrenci bilgisi eklensin")
        self.chkBcc      = QCheckBox("Kendime BCC"); self.chkBcc.setChecked(SmtpSettings.load(self.con).bcc_self)
        self.chkLastKume = QCheckBox("Son ödev kümesi özeti")
        self.chkAllKume  = QCheckBox("Tüm ödev kümeleri & içerikleri")

        for chk in (self.chkStuInfo, self.chkBcc, self.chkLastKume, self.chkAllKume):
            chk.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            chk.setMinimumHeight(24)

        grid_opts.addWidget(self.chkStuInfo, 0, 0)
        grid_opts.addWidget(self.chkBcc, 0, 1)
        grid_opts.addWidget(self.chkLastKume, 1, 0)
        grid_opts.addWidget(self.chkAllKume, 1, 1)
        ov.addLayout(grid_opts)
        rv.addWidget(optGrp)

        # Mesaj Gövdesi
        l_body = QLabel("Mesaj İçeriği:"); l_body.setStyleSheet("color:#64748b; font-weight:700; font-size:11px; margin-top: 2px;")
        rv.addWidget(l_body)
        self.txtBody = QTextEdit(); self.txtBody.setPlaceholderText("Merhaba {ad}, ...")
        self.txtBody.setMinimumHeight(80)
        rv.addWidget(self.txtBody, 1)

        right_scroll.setWidget(right_body)
        rc_lay.addWidget(right_scroll, 1)

        # En Alt Butonlar (Sabit alt çubuk - her zaman görünür, asla taşmaz)
        sendbar = QHBoxLayout()
        sendbar.setContentsMargins(0, 4, 0, 0)
        sendbar.setSpacing(10)
        sendbar.addStretch(1)

        self.btnClose = QPushButton("✕ Kapat")
        self.btnClose.setObjectName("btnClose")
        self.btnClose.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnClose.setMinimumHeight(38)
        self.btnClose.setMinimumWidth(110)

        self.btnSend = QPushButton("📤 Gönder (E-Posta)")
        self.btnSend.setObjectName("btnSend")
        self.btnSend.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnSend.setMinimumHeight(38)
        self.btnSend.setMinimumWidth(160)
        
        sendbar.addWidget(self.btnClose); sendbar.addWidget(self.btnSend)
        rc_lay.addLayout(sendbar)
        
        spl.addWidget(right_container)
        spl.setStretchFactor(0, 5); spl.setStretchFactor(1, 6)
        spl.setSizes([550, 500])

        # sinyaller
        self.btnAyar.clicked.connect(self._open_settings)
        self.btnYardim.clicked.connect(self._show_help_email)
        self.btnClose.clicked.connect(self.reject)
        self.btnBul.clicked.connect(self._do_search)
        self.btnHepsiniSec.clicked.connect(self._toggle_all_checks)
        self.btnEkle.clicked.connect(self._add_selected_addresses)
        self.btnSend.clicked.connect(self._send_email)
        self.cmbTemplate.currentIndexChanged.connect(self._apply_template)
        self.rdToplu.toggled.connect(self._mode_changed_email)

        self.txtSub.setText(_ayar_get(self.con, "mail.last_subject", "") or "")
        self.txtBody.setPlainText(_ayar_get(self.con, "mail.last_body", "") or "")

        self._do_search(); self._mode_changed_email()
        return w

    # ==== e-posta yardımcıları ====
    def _create_centered_checkbox(self, checked=False) -> QWidget:
        """Tablo hücresi içine ortalanmış checkbox widget'ı döndürür."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setContentsMargins(0,0,0,0)
        c = QCheckBox()
        c.setChecked(checked)
        lay.addWidget(c)
        return w

    def _do_search(self):
        rows = _ogrenci_ara(self.con, self.txtAra.text())
        self.tbl.setRowCount(0)
        for r in rows:
            i = self.tbl.rowCount(); self.tbl.insertRow(i)
            self.tbl.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.tbl.setItem(i, 1, QTableWidgetItem(f"{r['ad']} {r['soyad']}"))
            self.tbl.setItem(i, 2, QTableWidgetItem(r["ogr_mail"] or ""))
            self.tbl.setItem(i, 3, QTableWidgetItem(r["veli_mail"] or ""))
            
            # Checkboxları wrapper içine koy
            chkO = self._create_centered_checkbox(bool(r["ogr_mail"]))
            chkV = self._create_centered_checkbox(bool(r["veli_mail"]))
            self.tbl.setCellWidget(i, 4, chkO)
            self.tbl.setCellWidget(i, 5, chkV)

        self.tbl.clearSelection()

    def _get_check_state(self, row, col) -> bool:
        w = self.tbl.cellWidget(row, col)
        if w:
            cb = w.findChild(QCheckBox)
            if cb: return cb.isChecked()
        return False

    def _set_check_state(self, row, col, state: bool):
        w = self.tbl.cellWidget(row, col)
        if w:
            cb = w.findChild(QCheckBox)
            if cb: cb.setChecked(state)

    def _toggle_all_checks(self):
        if not self.tbl.rowCount(): return
        # İlk satırdaki duruma göre tersini yap
        target = not self._get_check_state(0, 4)
        for i in range(self.tbl.rowCount()):
            self._set_check_state(i, 4, target)
            self._set_check_state(i, 5, target)

    def _add_selected_addresses(self):
        if not self.rdToplu.isChecked():
            QMessageBox.information(self, "Bilgi", "Kişiselleştirilmiş modda alıcılar satırlardaki kutulardan alınır.")
            return
        emails: List[str] = []
        for i in range(self.tbl.rowCount()):
            if self._get_check_state(i, 4) and self.tbl.item(i,2):
                m = self.tbl.item(i,2).text().strip(); 
                if m: emails.append(m)
            if self._get_check_state(i, 5) and self.tbl.item(i,3):
                m = self.tbl.item(i,3).text().strip(); 
                if m: emails.append(m)

        cur = [e.strip() for e in self.txtTo.text().split(",") if e.strip()]
        allm = list(dict.fromkeys(cur + emails))
        self.txtTo.setText(", ".join(allm))

    def _apply_template(self, idx: int):
        if idx <= 0: return
        if idx == 1:
            self.txtSub.setText("Haftalık Ödev Durumu – {ad}")
            self.txtBody.setPlainText(
                "Merhaba {ad},\n\nBu haftanın özeti:\n• Tamamlanan: __\n• Devam: __\n• Geciken: __\n\nİyi çalışmalar.")
        elif idx == 2:
            self.txtSub.setText("Bilgilendirme / Duyuru")
            self.txtBody.setPlainText("Merhaba,\n\nAşağıdaki konuda bilgilendirme için yazıyorum:\n• __\n\nSevgiler.")

    def _mode_changed_email(self):
        self.txtTo.setEnabled(self.rdToplu.isChecked())

    def _selected_students(self) -> List[int]:
        ids: List[int] = []
        for i in range(self.tbl.rowCount()):
            if self._get_check_state(i, 4) or self._get_check_state(i, 5):
                ids.append(int(self.tbl.item(i,0).text()))
        return ids

    def _send_email(self):
        subject = self.txtSub.text().strip()
        body_base = self.txtBody.toPlainText().strip()
        if not subject:
            QMessageBox.warning(self, "Eksik", "Konu boş olamaz."); return
        
        # Güncel ayarları kaydet
        self.smtp.bcc_self = self.chkBcc.isChecked()
        self.smtp.save(self.con)
        
        try:
            client = SmtpClient(self.smtp)
        except Exception:
            QMessageBox.warning(self, "Hata", "Mail ayarlarında eksik var. Lütfen ayarlara girin.")
            return

        if self.rdToplu.isChecked():
            to_text = self.txtTo.text().strip()
            to_list = [x.strip() for x in to_text.split(",") if re.match(r"^[^@]+@[^@]+\.[^@]+$", x.strip())]
            if not to_list:
                QMessageBox.warning(self, "Eksik", "Toplu modda en az bir alıcı girin."); return
            html_body = "<html><body><pre style='white-space:pre-wrap; font-family:sans-serif; font-size:14px;'>" + body_base + "</pre></body></html>"
            try:
                client.send(to_list, subject, html_body, text_fallback=body_base)
                _ayar_set(self.con, "mail.last_subject", subject)
                _ayar_set(self.con, "mail.last_body", body_base)
                QMessageBox.information(self, "Mail", "Mail(ler) gönderildi.")
                self.accept()
            except Exception as e:
                msg = str(e)
                if "5.7.139" in msg or "basic authentication" in msg.lower():
                    QMessageBox.warning(self, "Outlook Güvenliği",
                        "Outlook/Office365 hesabında temel SMTP kapalı. Kurumsal hesapta 'Authenticated SMTP' açılmalı "
                        "ya da Gmail + uygulama şifresi kullanın.")
                else:
                    QMessageBox.warning(self, "Gönderim Hatası", f"Mail gönderilemedi:\n{e}")
            return

        ids = self._selected_students()
        if not ids:
            QMessageBox.information(self, "Seçim yok", "Kişiselleştirilmiş modda soldan en az bir öğrenci işaretleyin.")
            return
        ok = 0; fail = 0
        for i in range(self.tbl.rowCount()):
            sid = int(self.tbl.item(i,0).text())
            if sid not in ids: continue
            
            to_list: List[str] = []
            if self._get_check_state(i, 4) and self.tbl.item(i,2):
                m = self.tbl.item(i,2).text().strip()
                if m: to_list.append(m)
            if self._get_check_state(i, 5) and self.tbl.item(i,3):
                m = self.tbl.item(i,3).text().strip()
                if m: to_list.append(m)
            
            to_list = list(dict.fromkeys([x for x in to_list if re.match(r"^[^@]+@[^@]+\.[^@]+$", x)]))
            if not to_list:
                fail += 1; continue
            
            stu = self.con.execute("SELECT * FROM ogrenci WHERE id=?", (sid,)).fetchone()
            ad = stu["ad"] if stu else ""; soyad = stu["soyad"] if stu else ""
            extras = []
            if self.chkStuInfo.isChecked() and stu: extras.append("• " + _ogrenci_bilgi_satiri(stu))
            if self.chkLastKume.isChecked():     extras.append("   " + _son_kume_ozeti(self.con, sid))
            if self.chkAllKume.isChecked():      extras.append("\n" + _tum_kumeler_detay(self.con, sid))
            
            subj_i = subject.replace("{ad}", ad).replace("{soyad}", soyad)
            body_i = body_base.replace("{ad}", ad).replace("{soyad}", soyad)
            if extras: body_i = (body_i + "\n\n" + "\n".join(extras)).strip()
            
            html_body = "<html><body><pre style='white-space:pre-wrap; font-family:sans-serif; font-size:14px;'>" + body_i + "</pre></body></html>"
            try:
                client.send(to_list, subj_i, html_body, text_fallback=body_i); ok += 1
            except Exception:
                fail += 1
        
        _ayar_set(self.con, "mail.last_subject", subject)
        _ayar_set(self.con, "mail.last_body", body_base)
        
        if fail == 0:
            QMessageBox.information(self, "Tamam", f"{ok} mail gönderildi."); self.accept()
        else:
            QMessageBox.warning(self, "Özet", f"{ok} başarılı, {fail} hatalı.")

    def _open_settings(self):
        wizard = MailSettingsWizard(self, self.con)
        if wizard.exec():
            # Ayarlar değişti, yeniden yükle
            self.smtp = SmtpSettings.load(self.con)
            QMessageBox.information(self, "Ayarlar", "Mail ayarları güncellendi.")

    def _show_help_email(self):
        QMessageBox.information(self, "Mail Yardım",
            ("Gmail: 2 Adımlı Doğrulama + Uygulama Şifresi kullanın.\n"
             "Outlook: Genellikle temel SMTP kapalıdır, kurumsal hesap önerilir."))

# ========== MAIL AYARLAR SİHİRBAZI (YENİ) ==========
class MailSettingsWizard(QWizard):
    PID_INTRO = 0
    PID_SERVER = 1
    PID_CREDS = 2
    PID_FINAL = 3

    def __init__(self, parent=None, con: Optional[sqlite3.Connection]=None):
        super().__init__(parent)
        self.setWindowTitle("Mail Kurulum Sihirbazı")
        self.resize(600, 500)
        self.con = con or _connect_db()
        self.current_settings = SmtpSettings.load(self.con)
        
        # Stil
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle) 
        self.setTitleFormat(Qt.TextFormat.RichText)
        self.setSubTitleFormat(Qt.TextFormat.RichText)
        
        # Sayfalar (Explicit IDs)
        self.setPage(self.PID_INTRO, IntroPage(self))
        self.setPage(self.PID_SERVER, ServerPage(self))
        self.setPage(self.PID_CREDS, CredentialsPage(self))
        self.setPage(self.PID_FINAL, ConclusionPage(self))
        
        self.setStyleSheet("""
             QWizard { background-color: #ffffff; }
             QWizardPage { background-color: #ffffff; padding: 20px; }
             QLabel { font-size: 13px; color: #334155; }
             QLineEdit, QComboBox { 
                 border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; font-size: 13px; min-height: 20px;
             }
             QLineEdit:focus { border: 2px solid #3b82f6; }
        """)

class IntroPage(QWizardPage):
    def __init__(self, wizard: MailSettingsWizard):
        super().__init__()
        self.wiz = wizard
        self.setTitle("<h3 style='color:#2563eb'>1. Mail Sağlayıcısı Seç</h3>")
        self.setSubTitle("Kullanmak istediğiniz e-posta servisini seçin.")
        
        lay = QVBoxLayout(self); lay.setSpacing(15)
        
        self.cmbProvider = QComboBox()
        self.cmbProvider.addItems(list(PROVIDERS.keys()))
        self.cmbProvider.setCurrentText(self.wiz.current_settings.provider)
        
        lay.addWidget(QLabel("Servis Sağlayıcı:"))
        lay.addWidget(self.cmbProvider)
        
        info = QLabel(
            "ℹ️ <b>Bilgi:</b> Gmail veya Yahoo kullanıyorsanız, normal şifreniz yerine "
            "<b>Uygulama Şifresi (App Password)</b> oluşturmalısınız.<br><br>"
            "Outlook/Hotmail hesaplarında ise güvenlik politikaları nedeniyle SMTP gönderimi "
            "genellikle varsayılan olarak kapalıdır."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #64748b; background: #f8fafc; padding: 10px; border-radius: 6px;")
        lay.addWidget(info)
        lay.addStretch(1)

        self.registerField("provider", self.cmbProvider, "currentText")

    def nextId(self) -> int:
        return MailSettingsWizard.PID_SERVER

class ServerPage(QWizardPage):
    def __init__(self, wizard: MailSettingsWizard):
        super().__init__()
        self.wiz = wizard
        self.setTitle("<h3 style='color:#2563eb'>2. Sunucu Ayarları</h3>")
        self.setSubTitle("Genellikle otomatik doldurulur. Özel sunucu kullanmıyorsanız değiştirmeyin.")
        
        lay = QFormLayout(self); lay.setVerticalSpacing(15)
        
        self.chkAuto = QCheckBox("Otomatik Ayarla (Önerilen)")
        self.chkAuto.setChecked(True)
        self.chkAuto.toggled.connect(self._toggle_editable)
        
        self.txtHost = QLineEdit(); self.registerField("host", self.txtHost)
        self.txtPort = QLineEdit(); self.registerField("port", self.txtPort)
        self.cmbSec = QComboBox(); self.cmbSec.addItems(["TLS", "SSL"])
        self.registerField("security", self.cmbSec, "currentText")
        
        lay.addRow("", self.chkAuto)
        lay.addRow("Sunucu (SMTP):", self.txtHost)
        lay.addRow("Port:", self.txtPort)
        lay.addRow("Güvenlik:", self.cmbSec)
        
    def initializePage(self):
        p = self.field("provider")
        data = PROVIDERS.get(p, {})
        if data:
            self.txtHost.setText(data.get("host", ""))
            self.txtPort.setText(str(data.get("port", 587)))
            self.cmbSec.setCurrentText(data.get("security", "TLS"))
            
        saved = self.wiz.current_settings
        if saved.provider == p:
             self.txtHost.setText(saved.host)
             self.txtPort.setText(str(saved.port))
             self.cmbSec.setCurrentText(saved.security)
             
        self._toggle_editable(self.chkAuto.isChecked())
        
    def _toggle_editable(self, auto):
        self.txtHost.setEnabled(not auto)
        self.txtPort.setEnabled(not auto)
        self.cmbSec.setEnabled(not auto)
    
    def nextId(self) -> int:
        return MailSettingsWizard.PID_CREDS

class CredentialsPage(QWizardPage):
    def __init__(self, wizard: MailSettingsWizard):
        super().__init__()
        self.wiz = wizard
        self.setTitle("<h3 style='color:#2563eb'>3. Hesap Bilgileri</h3>")
        self.setSubTitle("Mail adresinizi ve şifrenizi girin.")
        
        lay = QVBoxLayout(self); lay.setSpacing(15)
        
        form = QFormLayout()
        self.txtUser = QLineEdit(); self.txtUser.setPlaceholderText("ornek@gmail.com")
        self.txtPass = QLineEdit(); self.txtPass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txtDisp = QLineEdit(); self.txtDisp.setPlaceholderText("Örn: Matematik Öğretmeni")
        
        # Kayıtlı veriyi yükle
        s = self.wiz.current_settings
        self.txtUser.setText(s.user)
        self.txtPass.setText(s.password)
        self.txtDisp.setText(s.display_name)
        
        # Manuel validation için field kaydı (* yok)
        self.registerField("user", self.txtUser)
        self.registerField("password", self.txtPass)
        self.registerField("display", self.txtDisp)
        
        # Sinyaller
        self.txtUser.textChanged.connect(self.completeChanged)
        self.txtPass.textChanged.connect(self.completeChanged)
        
        form.addRow("E-Mail Adresi:", self.txtUser)
        form.addRow("Şifre / App Pwd:", self.txtPass)
        form.addRow("Görünen İsim:", self.txtDisp)
        
        lay.addLayout(form)
        lay.addWidget(QLabel("<small style='color:gray'>Şifreniz sadece bu bilgisayarda, yerel veritabanında saklanır.</small>"))
        lay.addStretch(1)

    def isComplete(self) -> bool:
        # Alanlar doluysa true döner, Buton aktif olur
        u = self.txtUser.text().strip()
        p = self.txtPass.text().strip()
        return bool(u and p)

    def nextId(self) -> int:
        return MailSettingsWizard.PID_FINAL

class ConclusionPage(QWizardPage):
    def __init__(self, wizard: MailSettingsWizard):
        super().__init__()
        self.wiz = wizard
        self.setTitle("<h3 style='color:#2563eb'>4. Test ve Tamamla</h3>")
        self.setSubTitle("Ayarları test edin ve kaydedin.")
        
        lay = QVBoxLayout(self); lay.setSpacing(20)
        
        self.btnTest = QPushButton("⚡ Bağlantıyı Test Et")
        self.btnTest.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; padding: 10px;")
        self.btnTest.clicked.connect(self._do_test)
        
        self.lblStatus = QLabel("Test bekleniyor...")
        self.lblStatus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblStatus.setStyleSheet("font-weight: bold; padding: 10px; border: 1px dashed gray; border-radius: 6px;")
        
        lay.addStretch(1)
        lay.addWidget(self.btnTest)
        lay.addWidget(self.lblStatus)
        lay.addStretch(2)
        
    def _do_test(self):
        self.lblStatus.setText("Bağlanıyor...")
        self.lblStatus.setStyleSheet("font-weight: bold; padding: 10px; background-color: #e2e8f0;")
        QApplication.processEvents()
        
        # Geçici ayar objesi oluştur
        s = SmtpSettings(
            provider=self.field("provider"),
            host=self.field("host"),
            port=int(self.field("port") or 587),
            security=self.field("security"),
            user=self.field("user"),
            password=self.field("password"),
            display_name=self.field("display")
        )
        
        try:
            client = SmtpClient(s)
            # Kendine mail at
            client.send([s.user], "TEST MAIL", "<p>Bağlantı başarılı!</p>", "Bağlantı başarılı!")
            self.lblStatus.setText("✅ BAŞARILI! Mail gönderildi.")
            self.lblStatus.setStyleSheet("font-weight: bold; padding: 10px; background-color: #dcfce7; color: #166534;")
        except Exception as e:
            self.lblStatus.setText(f"❌ HATA: {e}")
            self.lblStatus.setStyleSheet("font-weight: bold; padding: 10px; background-color: #fee2e2; color: #991b1b;")

    def validatePage(self) -> bool:
        # Save on finish
        s = SmtpSettings(
            provider=self.field("provider"),
            host=self.field("host"),
            port=int(self.field("port") or 587),
            security=self.field("security"),
            user=self.field("user"),
            password=self.field("password"),
            display_name=self.field("display")
        )
        s.save(self.wiz.con)
        return True

    def nextId(self) -> int:
        return -1

# ---- tek başına çalıştırma
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = MailGonderDialog()
    dlg.show()
    sys.exit(app.exec())