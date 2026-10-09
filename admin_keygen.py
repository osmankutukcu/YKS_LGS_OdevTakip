# -*- coding: utf-8 -*-
"""
YKS-LGS Ödev & Takip Yöneticisi
Lisans Anahtarı Üretici (Admin Keygen GUI)
RSA-1024 Tabanlı Dijital İmzalı Lisanslama Aracı
"""

import sys
import os
import json
import base64
import hashlib
import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QComboBox, QSpinBox, QTextEdit, QFrame, 
    QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor

# --- RSA GÜVENLİK BİLEŞENLERİ (Gömülü Özel Anahtar) ---
RSA_N = 63596016435869199758595184650300680785102965001811426742530826267903030966068348475018147447679804548745840937391644961322478211825474436927570514904872183221096968649670640693766154323609305912491672225459870900893484653869132287389129929700182896257220340237660290286910826360144916404692757705278482529801
RSA_E = 65537
RSA_D = 55288564207242985267035708693341648052428804094529927370530179248974519619798132699278788607641554297104582651766580150393053063108903848488415058016387637270019385785171130497064971114350067073617443391162581164643143391955448540943047272829188423793426476373605588248832569373743111505130039334440959505665


def hash_payload(payload_b64: str) -> int:
    h = hashlib.sha256(payload_b64.encode("utf-8")).hexdigest()
    return int(h, 16)


def generate_license_key(machine_id: str, days_valid: int) -> str:
    """Makine kimliğine özel RSA imzalı lisans anahtarı üretir."""
    exp_date = datetime.date.today() + datetime.timedelta(days=days_valid)
    payload = {
        "mid": machine_id.strip().upper(),
        "exp": exp_date.isoformat(),
        "nonce": os.urandom(4).hex()
    }
    payload_json = json.dumps(payload, sort_keys=True)
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")
    
    h_int = hash_payload(payload_b64)
    sig_int = pow(h_int, RSA_D, RSA_N)
    sig_hex = hex(sig_int)[2:]
    return f"{payload_b64}.{sig_hex}"


def verify_license_key(key: str, machine_id: str):
    """Anahtarı genel anahtarla (Public Key) doğrular."""
    try:
        if "." not in key:
            return False, "Geçersiz format: Anahtar noktayla ayrılmamış."
        payload_b64, sig_hex = key.split(".")
        sig_int = int(sig_hex, 16)
        decrypted_hash = pow(sig_int, RSA_E, RSA_N)
        expected_hash = hash_payload(payload_b64)
        
        if decrypted_hash != expected_hash:
            return False, "İmza doğrulanamadı (Anahtar hatalı veya tahrif edilmiş)."
            
        data = json.loads(base64.b64decode(payload_b64).decode("utf-8"))
        if data["mid"].upper() != machine_id.strip().upper():
            return False, f"Makine Kimliği Uyuşmazlığı (Kayıtlı: {data['mid']}, Girilen: {machine_id})."
            
        exp_date = datetime.date.fromisoformat(data["exp"])
        if exp_date < datetime.date.today():
            return False, f"Lisans süresi dolmuş! Bitiş: {data['exp']}"
            
        return True, f"Lisans 100% Geçerli!\nBitiş Tarihi: {data['exp']}\nMakine Kimliği: {data['mid']}"
    except Exception as e:
        return False, f"Doğrulama hatası: {e}"


class KeygenWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YKS-LGS Ödev Takip - Lisans Anahtarı Üretici (Yönetici Paneli)")
        self.setFixedWidth(580)
        
        # UI Setup
        self._init_ui()
        self._apply_styling()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header Banner
        header = QFrame()
        header.setObjectName("headerCard")
        h_box = QHBoxLayout(header)
        h_box.setContentsMargins(16, 12, 16, 12)
        h_box.setSpacing(14)
        
        icon_lbl = QLabel("🔑")
        icon_lbl.setStyleSheet("font-size: 32px; background: transparent;")
        h_box.addWidget(icon_lbl)
        
        t_box = QVBoxLayout()
        t_box.setSpacing(2)
        title_lbl = QLabel("Lisans Anahtarı Üretici")
        title_lbl.setStyleSheet("color: #ffffff; font-size: 17px; font-weight: bold; background: transparent;")
        sub_lbl = QLabel("YKS-LGS Ödev & Takip Yönetim Sistemi v2 (Admin Panel)")
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent;")
        t_box.addWidget(title_lbl)
        t_box.addWidget(sub_lbl)
        h_box.addLayout(t_box)
        h_box.addStretch()
        main_layout.addWidget(header)

        # 2. Input Fields Frame
        input_frame = QFrame()
        input_frame.setObjectName("inputCard")
        in_layout = QVBoxLayout(input_frame)
        in_layout.setContentsMargins(16, 14, 16, 14)
        in_layout.setSpacing(12)

        # Müşteri / Not
        lbl_client = QLabel("Müşteri / Kurum Adı (İsteğe Bağlı):")
        lbl_client.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155;")
        in_layout.addWidget(lbl_client)
        
        self.txt_client = QLineEdit()
        self.txt_client.setPlaceholderText("Örn: Başarı Dershanesi / Mehmet Hoca")
        in_layout.addWidget(self.txt_client)

        # Makine Kimliği
        lbl_mid = QLabel("Makine Kimliği (Hardware ID): *")
        lbl_mid.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155;")
        in_layout.addWidget(lbl_mid)

        mid_box = QHBoxLayout()
        self.txt_mid = QLineEdit()
        self.txt_mid.setPlaceholderText("Örn: EC92A416D644931E (16 Haneli Kod)")
        self.txt_mid.setStyleSheet("font-family: Consolas, monospace; font-weight: bold; color: #0369a1;")
        mid_box.addWidget(self.txt_mid)

        btn_paste_mid = QPushButton("📋 Yapıştır")
        btn_paste_mid.setObjectName("btnSmall")
        btn_paste_mid.clicked.connect(self._paste_mid)
        mid_box.addWidget(btn_paste_mid)
        in_layout.addLayout(mid_box)

        # Süre Seçimi
        lbl_dur = QLabel("Lisans Süresi:")
        lbl_dur.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155;")
        in_layout.addWidget(lbl_dur)

        dur_box = QHBoxLayout()
        self.cmb_duration = QComboBox()
        self.cmb_duration.addItem("1 Yıl (365 Gün) - Standart", 365)
        self.cmb_duration.addItem("2 Yıl (730 Gün) - Uzatılmış", 730)
        self.cmb_duration.addItem("6 Ay (180 Gün) - Dönemlik", 180)
        self.cmb_duration.addItem("3 Ay (90 Gün) - Kısa Dönem", 90)
        self.cmb_duration.addItem("15 Gün (Demo)", 15)
        self.cmb_duration.addItem("Süresiz / Ömür Boyu (100 Yıl)", 36500)
        self.cmb_duration.addItem("Özel Gün Sayısı...", -1)
        self.cmb_duration.currentIndexChanged.connect(self._on_duration_changed)
        dur_box.addWidget(self.cmb_duration, stretch=2)

        self.spin_custom = QSpinBox()
        self.spin_custom.setRange(1, 36500)
        self.spin_custom.setValue(365)
        self.spin_custom.setSuffix(" Gün")
        self.spin_custom.setVisible(False)
        self.spin_custom.valueChanged.connect(self._update_expiry_preview)
        dur_box.addWidget(self.spin_custom, stretch=1)
        in_layout.addLayout(dur_box)

        # Bitiş Tarihi Bilgisi
        self.lbl_exp_preview = QLabel("Bitiş Tarihi: -")
        self.lbl_exp_preview.setStyleSheet("font-size: 11px; color: #0284c7; font-weight: 600;")
        in_layout.addWidget(self.lbl_exp_preview)

        main_layout.addWidget(input_frame)

        # 3. Generate Button
        self.btn_generate = QPushButton("⚡ LİSANS ANAHTARI ÜRET")
        self.btn_generate.setObjectName("btnPrimary")
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.clicked.connect(self._generate_key)
        main_layout.addWidget(self.btn_generate)

        # 4. Output Frame
        out_frame = QFrame()
        out_frame.setObjectName("outputCard")
        out_layout = QVBoxLayout(out_frame)
        out_layout.setContentsMargins(16, 12, 16, 12)
        out_layout.setSpacing(10)

        out_lbl = QLabel("Üretilen Lisans Anahtarı:")
        out_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #334155;")
        out_layout.addWidget(out_lbl)

        self.txt_output = QTextEdit()
        self.txt_output.setPlaceholderText("Üretilen lisans anahtarı burada görünecektir...")
        self.txt_output.setReadOnly(True)
        self.txt_output.setFixedHeight(85)
        self.txt_output.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; background-color: #f8fafc;")
        out_layout.addWidget(self.txt_output)

        # Action buttons row
        act_box = QHBoxLayout()
        act_box.setSpacing(8)

        self.btn_copy_key = QPushButton("📋 Anahtarı Kopyala")
        self.btn_copy_key.setObjectName("btnAction")
        self.btn_copy_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_key.clicked.connect(self._copy_key)
        act_box.addWidget(self.btn_copy_key)

        self.btn_copy_msg = QPushButton("💬 Müşteri Mesajını Kopyala")
        self.btn_copy_msg.setObjectName("btnAction")
        self.btn_copy_msg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_msg.clicked.connect(self._copy_customer_message)
        act_box.addWidget(self.btn_copy_msg)

        self.btn_verify = QPushButton("✅ Test Et / Doğrula")
        self.btn_verify.setObjectName("btnAction")
        self.btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_verify.clicked.connect(self._test_verify)
        act_box.addWidget(self.btn_verify)

        out_layout.addLayout(act_box)
        main_layout.addWidget(out_frame)

        self._update_expiry_preview()

    def _apply_styling(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f1f5f9;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QFrame#headerCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e293b);
                border-radius: 12px;
            }
            QFrame#inputCard, QFrame#outputCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #ffffff;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 13px;
                color: #0f172a;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #3b82f6;
            }
            QPushButton#btnPrimary {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                padding: 12px;
                border-radius: 8px;
                border: none;
            }
            QPushButton#btnPrimary:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
            }
            QPushButton#btnSmall {
                background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#btnSmall:hover {
                background-color: #e2e8f0;
            }
            QPushButton#btnAction {
                background-color: #f8fafc;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btnAction:hover {
                background-color: #e2e8f0;
                color: #0f172a;
            }
        """)

    def _on_duration_changed(self):
        val = self.cmb_duration.currentData()
        self.spin_custom.setVisible(val == -1)
        self._update_expiry_preview()

    def _get_days_valid(self) -> int:
        val = self.cmb_duration.currentData()
        if val == -1:
            return self.spin_custom.value()
        return val

    def _update_expiry_preview(self):
        days = self._get_days_valid()
        exp_date = datetime.date.today() + datetime.timedelta(days=days)
        self.lbl_exp_preview.setText(f"📅 Bitiş Tarihi: {exp_date.strftime('%d.%m.%Y')} ({days} gün sonra)")

    def _paste_mid(self):
        t = QApplication.clipboard().text().strip()
        if t:
            self.txt_mid.setText(t.upper())

    def _generate_key(self):
        mid = self.txt_mid.text().strip().upper()
        if not mid:
            QMessageBox.warning(self, "Uyarı", "Lütfen müşteriden aldığınız 16 haneli Makine Kimliğini giriniz.")
            self.txt_mid.setFocus()
            return

        days = self._get_days_valid()
        try:
            key = generate_license_key(mid, days)
            self.txt_output.setPlainText(key)
            self.btn_copy_key.setText("📋 Anahtarı Kopyala")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Anahtar üretilirken hata oluştu: {e}")

    def _copy_key(self):
        key = self.txt_output.toPlainText().strip()
        if not key:
            return
        QApplication.clipboard().setText(key)
        self.btn_copy_key.setText("✓ Kopyalandı!")
        QTimer.singleShot(2000, lambda: self.btn_copy_key.setText("📋 Anahtarı Kopyala"))

    def _copy_customer_message(self):
        key = self.txt_output.toPlainText().strip()
        mid = self.txt_mid.text().strip().upper()
        client = self.txt_client.text().strip()
        days = self._get_days_valid()
        exp_date = datetime.date.today() + datetime.timedelta(days=days)

        if not key:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce lisans anahtarı üretiniz.")
            return

        greeting = f"Sayın {client},\n" if client else "Merhaba,\n"
        dur_name = self.cmb_duration.currentText()
        if self.cmb_duration.currentData() == -1:
            dur_name = f"{days} Gün"

        msg = (
            f"{greeting}"
            f"YKS-LGS Ödev & Takip Yönetim Sistemi lisansınız başarıyla tanımlanmıştır.\n\n"
            f"💻 Makine Kimliğiniz: {mid}\n"
            f"⏳ Lisans Süresi: {dur_name}\n"
            f"📅 Bitiş Tarihi: {exp_date.strftime('%d.%m.%Y')}\n\n"
            f"🔑 LİSANS ANAHTARINIZ:\n{key}\n\n"
            f"Programı açtığınızda ekrana gelen 'Lisans Aktivasyonu' penceresine bu anahtarı yapıştırıp "
            f"'Lisansı Aktifleştir' butonuna basarak programınızı kullanmaya başlayabilirsiniz.\n\n"
            f"İyi çalışmalar dileriz!"
        )

        QApplication.clipboard().setText(msg)
        self.btn_copy_msg.setText("✓ Mesaj Kopyalandı!")
        QTimer.singleShot(2000, lambda: self.btn_copy_msg.setText("💬 Müşteri Mesajını Kopyala"))

    def _test_verify(self):
        key = self.txt_output.toPlainText().strip()
        mid = self.txt_mid.text().strip().upper()
        if not key or not mid:
            QMessageBox.warning(self, "Uyarı", "Doğrulamak için Makine Kimliği ve Lisans Anahtarı gereklidir.")
            return

        valid, msg = verify_license_key(key, mid)
        if valid:
            QMessageBox.information(self, "Doğrulama Başarılı", f"✅ {msg}")
        else:
            QMessageBox.critical(self, "Doğrulama Başarısız", f"❌ {msg}")


def main():
    app = QApplication(sys.argv)
    win = KeygenWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
