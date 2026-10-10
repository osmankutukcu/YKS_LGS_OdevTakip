# -*- coding: utf-8 -*-
"""
Mobil & Web Erişim Kontrol Merkezi (WebAccessDialog)
Ultra-Modern, Sıfır-Ayar (Zero-Config) Mobil Erişim Paneli:
- Büyük ve net QR Kod ile telefon kamerasından anında bağlantı
- Tek tıkla WhatsApp ve Bağlantıyı Kopyalama araçları
- Otomatik yerel Wi-Fi IP ve çakışmasız port tespiti
- Kolay bulut modu (Ngrok) ve Güvenlik/PIN ayarları
- Canlı durum ve bağlantı günlüğü
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox, 
    QTextEdit, QProgressBar, QCheckBox, QLineEdit, QGroupBox, 
    QFormLayout, QApplication, QHBoxLayout, QTabWidget, QWidget,
    QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QSettings
from PyQt6.QtGui import QFont, QImage, QPixmap, QDesktopServices, QCursor

import socket
import sys
import os
import threading
from io import BytesIO

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

def get_best_local_ip():
    """Gerçek yerel Wi-Fi/Ethernet IP adresini bulur (Sanal ağ bağdaştırıcılarını eler)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127.") and not ip.startswith("169.254"):
            return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"

def find_free_port(start_port=8085, max_tries=10):
    """Belirtilen porttan başlayarak boş bir port bulur."""
    for p in range(start_port, start_port + max_tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                res = s.connect_ex(('127.0.0.1', p))
                if res != 0:
                    return p
        except Exception:
            return p
    return start_port

def generate_qr_pixmap(data_url: str, size: int = 210) -> QPixmap:
    """Verilen URL için yüksek kaliteli, net bir QPixmap QR kod üretir."""
    if not HAS_QRCODE:
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.white)
        return pix
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(data_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qimg = QImage.fromData(buffer.getvalue())
        pix = QPixmap.fromImage(qimg)
        return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    except Exception as e:
        print("QR generation error:", e)
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.white)
        return pix

class WebServerThread(QThread):
    started_sig = pyqtSignal(str)
    error_sig = pyqtSignal(str)
    
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.keep_running = True
        self.server = None

    def run(self):
        try:
            try:
                import uvicorn
                try:
                    import uvicorn.logging
                except Exception:
                    pass
            except ImportError:
                self.error_sig.emit("Web sunucusu bileşeni 'uvicorn' bulunamadı.\nLütfen terminalden 'pip install uvicorn fastapi' kurun.")
                return

            sys.path.append(os.getcwd())
            try:
                from web_api.main import app as fastapi_app
                app_target = fastapi_app
            except Exception:
                app_target = "web_api.main:app"

            config = uvicorn.Config(
                app_target, 
                host=self.host,
                port=self.port, 
                log_level="warning",
                log_config=None,
                reload=False
            )
            self.server = uvicorn.Server(config)
            self.started_sig.emit(f"Running on http://{self.host}:{self.port}")
            self.server.run()
        except Exception as e:
            self.error_sig.emit(str(e))

    def stop_server(self):
        if self.server:
            self.server.should_exit = True

class WebAccessDialog(QDialog):
    """
    Ultra-Modern, Sıfır-Ayar (Zero-Config) Mobil & Web Erişim Kontrol Merkezi.
    - Büyük ve net QR Kod ile telefon kamerasından anında bağlantı
    - Tek tıkla WhatsApp ve Bağlantıyı Kopyalama araçları
    - Otomatik yerel Wi-Fi IP ve boş port tespiti
    - Kolay bulut modu rehberi ve güvenlik PIN ayarları
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📱 Mobil & Web Erişim Kontrol Merkezi")
        self.resize(660, 700)
        self.setMinimumSize(620, 640)
        
        self.thread = None
        self.local_ip = get_best_local_ip()
        self.port = 8085
        self.public_url = None
        self.settings = QSettings("YKS_LGS_Manager", "v2")
        # Önceki sürümde açık metin olarak saklanan tünel tokenini temizle.
        self.settings.remove("ngrok_token")
        
        self._apply_styling()
        self._init_ui()

    def _apply_styling(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QFrame#HeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #0f172a);
                border-radius: 12px;
                padding: 16px;
            }
            QFrame#HeaderCard QLabel {
                background: transparent;
                border: none;
            }
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                background-color: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                padding: 8px 14px;
                font-weight: 700;
                color: #475569;
                font-size: 12px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom-color: #ffffff;
                color: #2563eb;
            }
            QTabBar::tab:hover {
                background: #e2e8f0;
            }
            QFrame#QRCard {
                background-color: #ffffff;
                border: 2px dashed #cbd5e1;
                border-radius: 14px;
                padding: 16px;
            }
            QFrame#StatusBadge {
                border-radius: 8px;
                padding: 10px 16px;
            }
            QPushButton {
                border-radius: 8px;
                padding: 9px 16px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton#btnStart {
                background-color: #2563eb;
                color: white;
                border: none;
                font-size: 14px;
                padding: 12px 20px;
            }
            QPushButton#btnStart:hover { background-color: #1d4ed8; }
            QPushButton#btnStop {
                background-color: #ef4444;
                color: white;
                border: none;
                font-size: 14px;
                padding: 12px 20px;
            }
            QPushButton#btnStop:hover { background-color: #dc2626; }
            QPushButton#btnAction {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                color: #334155;
            }
            QPushButton#btnAction:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }
            QPushButton#btnWhatsApp {
                background-color: #dcfce7;
                border: 1px solid #86efac;
                color: #166534;
            }
            QPushButton#btnWhatsApp:hover {
                background-color: #bbf7d0;
            }
            QLineEdit {
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 10px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)

    def _init_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(18, 18, 18, 18)
        root_lay.setSpacing(14)

        # 1. Başlık Kartı
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        h_lay = QVBoxLayout(header_card)
        h_lay.setContentsMargins(12, 10, 12, 10)
        h_lay.setSpacing(4)
        
        lbl_t = QLabel("🌐 Mobil & Web Erişim Kontrol Merkezi")
        lbl_t.setStyleSheet("color: white; font-size: 18px; font-weight: 800;")
        lbl_sub = QLabel("Telefon ve tabletlerden öğrenci raporlarına anında, kablosuz ve canlı erişim")
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 12px;")
        h_lay.addWidget(lbl_t)
        h_lay.addWidget(lbl_sub)
        root_lay.addWidget(header_card)

        # 2. Sekmeler
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(False)
        
        # TAB 1: Hızlı QR Kod & Mobil Erişim
        self.tab_qr = QWidget()
        self._init_tab_qr()
        self.tabs.addTab(self.tab_qr, "📱 QR Kod ile Bağlan")

        # TAB 2: İnternet / Dış Ağ (Bulut Modu)
        self.tab_cloud = QWidget()
        self._init_tab_cloud()
        self.tabs.addTab(self.tab_cloud, "☁️ Bulut Erişimi")

        # TAB 3: Güvenlik & PIN
        self.tab_security = QWidget()
        self._init_tab_security()
        self.tabs.addTab(self.tab_security, "🔒 Güvenlik & PIN")

        # TAB 4: Canlı Günlük
        self.tab_log = QWidget()
        self._init_tab_log()
        self.tabs.addTab(self.tab_log, "📋 Durum & Günlük")

        root_lay.addWidget(self.tabs, stretch=1)

        # 3. Alt Başlat/Durdur Çubuğu
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.btnStart = QPushButton("⚡ Sunucuyu Başlat (1-Tıkla)")
        self.btnStart.setObjectName("btnStart")
        self.btnStart.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnStart.clicked.connect(self.start_server)
        bottom_bar.addWidget(self.btnStart, stretch=2)

        self.btnStop = QPushButton("⏹️ Sunucuyu Durdur")
        self.btnStop.setObjectName("btnStop")
        self.btnStop.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnStop.setEnabled(False)
        self.btnStop.clicked.connect(self.stop_server)
        bottom_bar.addWidget(self.btnStop, stretch=1)

        root_lay.addLayout(bottom_bar)

    def _init_tab_qr(self):
        lay = QVBoxLayout(self.tab_qr)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        # Durum Gösterge Şeridi
        self.status_frame = QFrame()
        self.status_frame.setObjectName("StatusBadge")
        self.status_frame.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1;")
        s_lay = QHBoxLayout(self.status_frame)
        s_lay.setContentsMargins(12, 8, 12, 8)
        
        self.lbl_status_icon = QLabel("⚪")
        self.lbl_status_icon.setStyleSheet("font-size: 16px; background: transparent;")
        s_lay.addWidget(self.lbl_status_icon)

        self.lbl_status_text = QLabel("Sunucu Kapalı — Başlatmak için aşağıdaki butona tıklayın")
        self.lbl_status_text.setStyleSheet("font-weight: 700; color: #475569; font-size: 13px; background: transparent;")
        s_lay.addWidget(self.lbl_status_text)
        s_lay.addStretch()
        lay.addWidget(self.status_frame)

        # QR Kod ve Bilgi Alanı (Ortalı)
        center_row = QHBoxLayout()
        center_row.setSpacing(16)

        # QR Kartı
        qr_card = QFrame()
        qr_card.setObjectName("QRCard")
        qr_card.setFixedSize(230, 230)
        qr_lay = QVBoxLayout(qr_card)
        qr_lay.setContentsMargins(8, 8, 8, 8)
        qr_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_qr = QLabel()
        self.lbl_qr.setFixedSize(210, 210)
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_qr_placeholder()
        qr_lay.addWidget(self.lbl_qr)
        center_row.addWidget(qr_card)

        # Yan Panel: Açıklama ve URL Kutusu
        side_lay = QVBoxLayout()
        side_lay.setSpacing(8)

        lbl_guide_title = QLabel("📱 Telefonunuzdan Nasıl Açılır?")
        lbl_guide_title.setStyleSheet("font-weight: 800; font-size: 14px; color: #1e293b;")
        side_lay.addWidget(lbl_guide_title)

        lbl_step1 = QLabel("1. Cep telefonunuzun <b>kamerasını</b> açın.")
        lbl_step1.setStyleSheet("color: #334155; font-size: 12px;")
        lbl_step2 = QLabel("2. Kamerayı ekrandaki <b>QR Koda</b> doğru tutun.")
        lbl_step2.setStyleSheet("color: #334155; font-size: 12px;")
        lbl_step3 = QLabel("3. Ekranda beliren <b>bağlantıya</b> dokunun!")
        lbl_step3.setStyleSheet("color: #334155; font-size: 12px;")
        side_lay.addWidget(lbl_step1)
        side_lay.addWidget(lbl_step2)
        side_lay.addWidget(lbl_step3)

        side_lay.addSpacing(6)
        lbl_url_title = QLabel("🔗 Canlı Web Adresi (Tarayıcı İçin):")
        lbl_url_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #64748b;")
        side_lay.addWidget(lbl_url_title)

        self.txt_url_display = QLineEdit()
        self.txt_url_display.setReadOnly(True)
        self.txt_url_display.setText("Sunucu henüz başlatılmadı")
        self.txt_url_display.setStyleSheet("background-color: #f8fafc; font-family: monospace; font-weight: bold; color: #2563eb;")
        side_lay.addWidget(self.txt_url_display)

        center_row.addLayout(side_lay)
        lay.addLayout(center_row)

        # Hızlı Aksiyon Butonları
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.btnCopy = QPushButton("📋 Bağlantıyı Kopyala")
        self.btnCopy.setObjectName("btnAction")
        self.btnCopy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnCopy.setEnabled(False)
        self.btnCopy.clicked.connect(self.copy_link)
        action_row.addWidget(self.btnCopy)

        self.btnWhatsApp = QPushButton("📲 WhatsApp'la Gönder")
        self.btnWhatsApp.setObjectName("btnWhatsApp")
        self.btnWhatsApp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnWhatsApp.setEnabled(False)
        self.btnWhatsApp.clicked.connect(self.send_whatsapp)
        action_row.addWidget(self.btnWhatsApp)

        self.btnBrowser = QPushButton("🌐 Tarayıcıda Aç")
        self.btnBrowser.setObjectName("btnAction")
        self.btnBrowser.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btnBrowser.setEnabled(False)
        self.btnBrowser.clicked.connect(self.open_browser)
        self.btnTest = self.btnBrowser  # Backward compatibility alias
        action_row.addWidget(self.btnBrowser)

        lay.addLayout(action_row)

        # Wi-Fi Uyarısı Bilgi Kutusu
        wifi_info = QFrame()
        wifi_info.setStyleSheet("background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 8px;")
        wi_lay = QHBoxLayout(wifi_info)
        wi_lay.setContentsMargins(10, 6, 10, 6)
        lbl_wi = QLabel("💡 <b>Önemli İpucu:</b> Telefon veya tabletinizin bu bilgisayar ile <b>AYNI Wi-Fi (kablosuz)</b> ağına bağlı olması yeterlidir. İnternet kotası harcamaz, yerel ağdan son derece hızlı çalışır.")
        lbl_wi.setStyleSheet("font-size: 11.5px; color: #1e40af; background: transparent;")
        lbl_wi.setWordWrap(True)
        wi_lay.addWidget(lbl_wi)
        lay.addWidget(wifi_info)

    def _init_tab_cloud(self):
        lay = QVBoxLayout(self.tab_cloud)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        lbl_c_info = QLabel("Dünyanın her yerinden (ev dışındayken veya telefonunuzun mobil verisiyle) bağlanmak için bulut modunu açabilirsiniz.")
        lbl_c_info.setStyleSheet("color: #475569; font-size: 12.5px;")
        lbl_c_info.setWordWrap(True)
        lay.addWidget(lbl_c_info)

        grp_ngrok = QGroupBox("Ngrok Güvenli Tünel (Ücretsiz)")
        grp_ngrok.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 8px; margin-top: 10px; padding: 12px; }")
        g_lay = QVBoxLayout(grp_ngrok)
        g_lay.setSpacing(10)

        self.chkCloud = QCheckBox("Ngrok Bulut Tünelini Etkinleştir")
        self.chkCloud.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 13px;")
        g_lay.addWidget(self.chkCloud)

        t_row = QHBoxLayout()
        self.txtNgrokToken = QLineEdit()
        self.txtNgrokToken.setPlaceholderText("Ngrok Auth Token yapıştırın...")
        saved_tok = ""  # eski düz metin token tekrar gösterilmez
        self.txtNgrokToken.setText(saved_tok)
        t_row.addWidget(self.txtNgrokToken)

        btn_tok_help = QPushButton("🔑 Token Nasıl Alınır?")
        btn_tok_help.setStyleSheet("background-color: #f59e0b; color: white; border: none; font-weight: bold;")
        btn_tok_help.clicked.connect(self.show_ngrok_help)
        t_row.addWidget(btn_tok_help)
        g_lay.addLayout(t_row)

        lbl_tok_sub = QLabel("Ücretsiz hesap: ngrok.com adresinden alınıp 1 kez yapıştırılması yeterlidir.")
        lbl_tok_sub.setStyleSheet("color: #64748b; font-size: 11px;")
        g_lay.addWidget(lbl_tok_sub)

        lay.addWidget(grp_ngrok)
        lay.addStretch()

    def _init_tab_security(self):
        lay = QVBoxLayout(self.tab_security)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        grp_sec = QGroupBox("Mobil Erişim Güvenliği")
        grp_sec.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 8px; margin-top: 10px; padding: 12px; }")
        s_lay = QFormLayout(grp_sec)
        s_lay.setSpacing(12)

        from web_api.auth import get_access_token
        self.txtAccessKey = QLineEdit()
        self.txtAccessKey.setReadOnly(True)
        self.txtAccessKey.setEchoMode(QLineEdit.EchoMode.Password)
        self.txtAccessKey.setText(get_access_token())
        s_lay.addRow("Web erişim anahtarı:", self.txtAccessKey)
        btn_copy_key = QPushButton("🔑 Anahtarı Kopyala")
        btn_copy_key.clicked.connect(lambda: QApplication.clipboard().setText(get_access_token()))
        s_lay.addRow(btn_copy_key)
        warning = QLabel("Bu anahtar tüm mobil verilere erişim verir. Yalnızca güvendiğiniz kişilere verin. "
                         "Ağdaki HTTP bağlantısı şifreli değildir; internette HTTPS kullanın.")
        warning.setWordWrap(True)
        s_lay.addRow(warning)

        lay.addWidget(grp_sec)
        lay.addStretch()

    def _init_tab_log(self):
        lay = QVBoxLayout(self.tab_log)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        self.txtLog = QTextEdit()
        self.txtLog.setReadOnly(True)
        self.txtLog.setStyleSheet("background-color: #0f172a; color: #38bdf8; font-family: monospace; font-size: 12px; border-radius: 8px; padding: 10px;")
        self.txtLog.append("--- Mobil & Web Sunucusu Günlük Kaydı Başlatıldı ---")
        self.txtLog.append(f"[*] Algılanan Yerel IP: {self.local_ip}")
        lay.addWidget(self.txtLog)

    def _set_qr_placeholder(self):
        pix = QPixmap(210, 210)
        pix.fill(Qt.GlobalColor.white)
        self.lbl_qr.setPixmap(pix)
        self.lbl_qr.setText("Sunucuyu Başlattığınızda\nBurada QR Kod Görünecektir")
        self.lbl_qr.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 12px; background: #ffffff;")

    def get_active_url(self):
        if self.public_url:
            return self.public_url
        return f"http://{self.local_ip}:{self.port}/"

    def start_server(self):
        if self.thread and self.thread.isRunning():
            return

        self.port = find_free_port(8085, 10)
        self.local_ip = get_best_local_ip()

        self.lbl_status_icon.setText("⏳")
        self.lbl_status_text.setText(f"Sunucu başlatılıyor (Port {self.port})...")
        self.btnStart.setEnabled(False)
        QApplication.processEvents()

        # Database Path Sync
        try:
            import db
            current_db_path = str(db.DB_PATH)
            os.environ["YKS_DB_PATH"] = current_db_path
            self.txtLog.append(f"[*] Veritabanı Yolu: {current_db_path}")
        except Exception as e:
            self.txtLog.append(f"[!] Veritabanı yolu alınamadı: {e}")
            
        self.txtLog.append(f"[*] Sunucu Portu: {self.port}")

        # Cloud Tunnel Check
        public_url = None
        if self.chkCloud.isChecked():
            token = self.txtNgrokToken.text().strip()
            if not token:
                QMessageBox.warning(self, "Eksik Token", "Bulut erişimi için lütfen Ngrok Token giriniz.")
                self._after_stop()
                return
            # Ngrok token artık düz metin uygulama ayarına yazılmaz.
            try:
                from pyngrok import ngrok, conf
                conf.get_default().auth_token = token
                tunnel = ngrok.connect(self.port, "http")
                public_url = tunnel.public_url
                self.txtLog.append(f"[+] Ngrok Bulut Tüneli Açıldı: {public_url}")
            except Exception as e:
                QMessageBox.critical(self, "Bulut Hatası", f"Ngrok başlatılamadı:\n{e}")

        self.public_url = public_url

        self.thread = WebServerThread("0.0.0.0", self.port)
        self.thread.started_sig.connect(self.on_started)
        self.thread.error_sig.connect(self.on_error)
        self.thread.start()

    def on_started(self, msg):
        active_url = self.get_active_url()
        self.lbl_status_icon.setText("🟢")
        self.lbl_status_text.setText(f"Sunucu Aktif & Yayında! (Port {self.port})")
        self.status_frame.setStyleSheet("background-color: #dcfce7; border: 1.5px solid #86efac;")
        self.lbl_status_text.setStyleSheet("color: #166534; font-weight: 800; font-size: 13px; background: transparent;")

        self.txt_url_display.setText(active_url)
        self.txtLog.append(f"[+] Sunucu Yayında: {active_url}")

        # Generate & Show QR Code
        qr_pix = generate_qr_pixmap(active_url, size=210)
        self.lbl_qr.setPixmap(qr_pix)
        self.lbl_qr.setText("")

        self.btnStart.setEnabled(False)
        self.btnStop.setEnabled(True)
        self.btnCopy.setEnabled(True)
        self.btnWhatsApp.setEnabled(True)
        self.btnBrowser.setEnabled(True)

    def on_error(self, err):
        self.lbl_status_icon.setText("🔴")
        self.lbl_status_text.setText("Sunucu Başlatılamadı!")
        self.status_frame.setStyleSheet("background-color: #fee2e2; border: 1.5px solid #fca5a5;")
        self.lbl_status_text.setStyleSheet("color: #991b1b; font-weight: 800; font-size: 13px; background: transparent;")
        self.btnStart.setEnabled(True)
        self.txtLog.append(f"[!] HATA: {err}")
        QMessageBox.critical(self, "Hata", f"Sunucu hatası:\n{err}")

    def stop_server(self):
        if self.thread:
            self.thread.stop_server()
            try:
                from pyngrok import ngrok
                ngrok.kill()
            except Exception:
                pass
            self.lbl_status_text.setText("Sunucu durduruluyor...")
            QTimer.singleShot(1000, self._after_stop)
        else:
            self._after_stop()

    def _after_stop(self):
        self.lbl_status_icon.setText("⚪")
        self.lbl_status_text.setText("Sunucu Kapalı")
        self.status_frame.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1;")
        self.lbl_status_text.setStyleSheet("color: #475569; font-weight: 700; font-size: 13px; background: transparent;")
        self.txt_url_display.setText("Sunucu kapalı")
        self._set_qr_placeholder()
        self.btnStart.setEnabled(True)
        self.btnStop.setEnabled(False)
        self.btnCopy.setEnabled(False)
        self.btnWhatsApp.setEnabled(False)
        self.btnBrowser.setEnabled(False)
        self.txtLog.append("[-] Sunucu durduruldu.")

    def copy_link(self):
        url = self.get_active_url()
        QApplication.clipboard().setText(url)
        self.btnCopy.setText("✅ Kopyalandı!")
        QTimer.singleShot(2000, lambda: self.btnCopy.setText("📋 Bağlantıyı Kopyala"))

    def send_whatsapp(self):
        url = self.get_active_url()
        msg = f"📱 YKS/LGS Takip Mobil Web Paneli Bağlantısı:\n{url}\n\n(Aynı Wi-Fi ağına bağlıyken telefonunuzdan tıklayarak açabilirsiniz)"
        import urllib.parse
        encoded = urllib.parse.quote(msg)
        QDesktopServices.openUrl(QUrl(f"https://api.whatsapp.com/send?text={encoded}"))

    def open_browser(self):
        url = f"http://127.0.0.1:{self.port}/"
        QDesktopServices.openUrl(QUrl(url))

    def save_security_settings(self):
        QMessageBox.information(self, "Erişim Anahtarı", "Web anahtarını Güvenlik sekmesinden kopyalayabilirsiniz.")

    def show_ngrok_help(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Ngrok Token Rehberi")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText("""
        <h3 style='color:#2563eb;'>Ücretsiz Bulut Erişimi Nasıl Açılır?</h3>
        <p>Herhangi bir internetten bağlanmak için:</p>
        <ol style='font-size:13px;'>
            <li><b>ngrok.com</b> sitesine gidip ücretsiz kayıt olun.</li>
            <li>Dashboard'da <b>'Your Authtoken'</b> sayfasından tokeni kopyalayın.</li>
            <li>Buradaki kutucuğa yapıştırıp sunucuyu başlatın!</li>
        </ol>
        """)
        btn_go = msg.addButton("🌐 Siteye Git", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Tamam", QMessageBox.ButtonRole.AcceptRole)
        msg.exec()
        if msg.clickedButton() == btn_go:
            QDesktopServices.openUrl(QUrl("https://dashboard.ngrok.com/signup"))

ModernWebAccessDialog = WebAccessDialog
