# -*- coding: utf-8 -*-
"""
Uygulama giriş noktası
- Türkçe yerel ayarı (QLocale)
- Tema QSS yükleme (koyu/açık)
- (Varsa) utils.calendar_fix ile tüm takvimleri düzeltme
"""

import os
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

# Heavy imports moved to main() to speed up cold start
# from main_window import AnaPencere
# from utils import settings as appset

# calendar_fix opsiyonel: import sorunu olursa uygulama çalışmayı sürdürsün
try:
    from utils.calendar_fix import install_calendar_fix  # type: ignore
except Exception:
    install_calendar_fix = None  # type: ignore


from pathlib import Path
import sys

def resource_path(relative_path: str) -> str:
    """
    PyInstaller ile paketlendiğinde de, normal çalışırken de
    dosya yolunu doğru veren yardımcı fonksiyon.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller (onefile veya onedir)
        if hasattr(sys, '_MEIPASS'):
            # --onefile modu
            base_path = Path(sys._MEIPASS)
        else:
            # --onedir modu
            # macOS .app bundle yapısı kontrolü
            exe_path = Path(sys.executable)
            if sys.platform == "darwin" and exe_path.parent.name == "MacOS":
                 # .../Contents/MacOS/exe -> .../Contents/Resources
                 base_path = exe_path.parent.parent / "Resources"
            else:
                 base_path = exe_path.parent
    else:
        # Normal python çalışması
        base_path = Path(__file__).parent
        
    return str(base_path / relative_path)



def apply_theme(app: QApplication) -> None:
    """
    Ayarlar'daki tema seçimine göre dinamik QSS uygular.
    Yeni 'ui.theme' modülü üzerinden çalışır.
    """
    try:
        from ui import theme
        # Yeni gelişmiş tema motorunu tetikle
        theme.apply(app)
    except Exception as e:
        print(f"Tema uygulanırken hata oluştu: {e}")



from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QPen, QPainterPath
from PyQt6.QtWidgets import QSplashScreen, QProgressBar
from PyQt6.QtNetwork import QLocalSocket, QLocalServer

# Global ref to keep server alive
_single_instance_server = None

def check_single_instance(app_key: str) -> bool:
    """
    True dönerse uygulama zaten çalışıyor demektir.
    False dönerse ilk örnektir, sunucuyu başlatır.
    """
    global _single_instance_server
    socket = QLocalSocket()
    socket.connectToServer(app_key)
    if socket.waitForConnected(500):
        return True  # Zaten çalışıyor
    
    # Çalışmıyor, sunucuyu biz başlatalım
    _single_instance_server = QLocalServer()
    # Unix soket dosyası kalıntısı varsa temizle
    _single_instance_server.removeServer(app_key)
    if not _single_instance_server.listen(app_key):
        # Dinleyemedik (belki yetki sorunu?), ama devam edelim
        pass
    return False


class ModernSplash(QSplashScreen):
    def __init__(self):
        w, h = 520, 320
        pix = QPixmap(w, h)
        pix.fill(Qt.GlobalColor.transparent) 
        super().__init__(pix)
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen 
            | Qt.WindowType.FramelessWindowHint 
            | Qt.WindowType.WindowStaysOnTopHint
        )
        
        # Ekranda tam ortala
        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            geo = primary_screen.availableGeometry()
            self.move((geo.width() - w) // 2, (geo.height() - h) // 2)

        self.prog = 0
        self.msg = "Yükleniyor..."
        
        self.setWindowIcon(QIcon(resource_path("assets/app_icon.png")))

        # Modern Tipografi
        font_family = "Segoe UI" if sys.platform == "win32" else ".AppleSystemUIFont"
        self.font_title = QFont(font_family, 20, QFont.Weight.Bold)
        self.font_sub = QFont(font_family, 10, QFont.Weight.DemiBold)
        self.font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        self.font_badge = QFont(font_family, 8, QFont.Weight.Bold)
        self.font_msg = QFont(font_family, 9, QFont.Weight.Medium)
        self.font_pct = QFont(font_family, 9, QFont.Weight.Bold)
        self.font_foot = QFont(font_family, 8, QFont.Weight.Normal)
    
    def set_progress(self, val, message):
        self.prog = max(0, min(100, val))
        self.msg = message
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter: QPainter):
        w = self.width()
        h = self.height()
        
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        card_rect = QRectF(4, 4, w - 8, h - 8)
        radius = 16.0
        
        # 1. Dış Gölgelendirme Efekti
        for i in range(4):
            shadow_rect = card_rect.adjusted(-i * 0.8, -i * 0.8, i * 0.8, i * 0.8)
            painter.setPen(QColor(0, 0, 0, 16 - i * 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(shadow_rect, radius + i, radius + i)
            
        # 2. Ana Kart Arka Planı (Derin Lacivert / Indigo Slate Gradyan)
        card_path = QPainterPath()
        card_path.addRoundedRect(card_rect, radius, radius)
        
        bg_grad = QLinearGradient(0, 0, w, h)
        bg_grad.setColorAt(0.0, QColor("#0f172a"))   # Slate 900
        bg_grad.setColorAt(0.5, QColor("#141e33"))   # Deep Indigo Slate
        bg_grad.setColorAt(1.0, QColor("#1e293b"))   # Slate 800
        painter.fillPath(card_path, bg_grad)
        
        # 3. Üst Işık Yansıması (Cam efekti)
        top_glow = QLinearGradient(card_rect.left(), card_rect.top(), card_rect.left(), card_rect.top() + 100)
        top_glow.setColorAt(0.0, QColor(255, 255, 255, 22))
        top_glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(top_glow)
        painter.drawRoundedRect(card_rect.adjusted(1, 1, -1, -h * 0.6), radius, radius)
        
        # 4. İnce Çerçeve
        border_pen = QPen(QColor(255, 255, 255, 32), 1.2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(card_rect, radius, radius)
        
        # 5. İkon Kutusu
        icon_size = 64
        icon_x = int((w - icon_size) / 2)
        icon_y = 36
        
        icon_bg_rect = QRectF(icon_x - 6, icon_y - 6, icon_size + 12, icon_size + 12)
        painter.setPen(QPen(QColor(56, 189, 248, 60), 1.5))
        icon_grad = QLinearGradient(icon_bg_rect.topLeft(), icon_bg_rect.bottomRight())
        icon_grad.setColorAt(0.0, QColor(30, 41, 59, 220))
        icon_grad.setColorAt(1.0, QColor(15, 23, 42, 240))
        painter.setBrush(icon_grad)
        painter.drawRoundedRect(icon_bg_rect, 14, 14)
        
        # İkon Çizimi (Varsa temizlenmiş saydam ikon, yoksa orijinal)
        clean_icon_path = resource_path("assets/app_icon_clean.png")
        if Path(clean_icon_path).exists():
            logo = QPixmap(clean_icon_path)
        else:
            logo = QPixmap(resource_path("assets/app_icon.png"))
            
        if not logo.isNull():
            logo_scaled = logo.scaled(
                icon_size, icon_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(icon_x, icon_y, logo_scaled)
            
        # 6. Başlıklar
        painter.setPen(QColor("#f8fafc"))
        painter.setFont(self.font_title)
        painter.drawText(0, 134, w, 32, Qt.AlignmentFlag.AlignCenter, "YKS - LGS")
        
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(self.font_sub)
        painter.drawText(0, 168, w, 20, Qt.AlignmentFlag.AlignCenter, "ÖDEV & TAKİP YÖNETİCİSİ")
        
        # Versiyon Rozeti (Pill Badge)
        badge_text = "v2.5 PRO"
        badge_w = 78
        badge_h = 20
        badge_x = (w - badge_w) // 2
        badge_y = 194
        
        painter.setPen(QPen(QColor(56, 189, 248, 80), 1))
        painter.setBrush(QColor(15, 23, 42, 180))
        painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 10, 10)
        
        painter.setPen(QColor("#38bdf8"))
        painter.setFont(self.font_badge)
        painter.drawText(badge_x, badge_y, badge_w, badge_h, Qt.AlignmentFlag.AlignCenter, badge_text)
        
        # 7. Durum Mesajı ve Yüzde
        bar_x = 44
        bar_w = w - (bar_x * 2)
        bar_y = h - 56
        bar_h = 6
        
        painter.setPen(QColor("#cbd5e1"))
        painter.setFont(self.font_msg)
        painter.drawText(bar_x, bar_y - 24, bar_w - 60, 20, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.msg)
        
        painter.setPen(QColor("#38bdf8"))
        painter.setFont(self.font_pct)
        painter.drawText(bar_x + bar_w - 55, bar_y - 24, 55, 20, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{int(self.prog)}%")
        
        # 8. İlerleme Çubuğu İzi (Track)
        track_path = QPainterPath()
        track_path.addRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 41, 59, 200))
        painter.drawPath(track_path)
        
        # 9. İlerleme Dolgusu (Cyan to Indigo Gradyan)
        if self.prog > 0:
            fill_w = max(6.0, bar_w * (self.prog / 100.0))
            fill_path = QPainterPath()
            fill_path.addRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)
            
            prog_grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
            prog_grad.setColorAt(0.0, QColor("#0284c7"))  # Sky 600
            prog_grad.setColorAt(0.5, QColor("#38bdf8"))  # Sky 400
            prog_grad.setColorAt(1.0, QColor("#818cf8"))  # Indigo 400
            
            painter.setBrush(prog_grad)
            painter.drawPath(fill_path)
            
        # 10. Alt Bilgi / Güvenlik
        painter.setPen(QColor("#64748b"))
        painter.setFont(self.font_foot)
        painter.drawText(bar_x, h - 28, bar_w // 2, 18, Qt.AlignmentFlag.AlignLeft, "🔒 Güvenli Veritabanı & Lisans Koruması")
        painter.drawText(bar_x + bar_w // 2, h - 28, bar_w // 2, 18, Qt.AlignmentFlag.AlignRight, "© 2026 Tüm Hakları Saklıdır")


def main() -> None:
    # 0) Windows Platform İyileştirmeleri (Görev çubuğu ikonu & High-DPI)
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = "ykslgs.homeworkmanager.v2"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    # High-DPI Fractional Scaling
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

    # 1) Türkçe yerel ayarı
    QLocale.setDefault(QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey))

    # 2) Qt uygulaması
    app = QApplication(sys.argv)
    
    # -- SINGLE INSTANCE CHECK --
    app_id = "yks_lgs_odev_takip_v2_lock"
    if check_single_instance(app_id):
        print("Uygulama zaten çalışıyor.")
        sys.exit(0)

    app.setApplicationName("YKS-LGS Ödev Takip")
    # Windows için .ico, Mac/Linux için .png tercih edilir
    if sys.platform == "win32" and Path(resource_path("assets/app_icon.ico")).exists():
        app_icon_path = resource_path("assets/app_icon.ico")
    else:
        app_icon_path = resource_path("assets/app_icon.png")
    app.setWindowIcon(QIcon(app_icon_path))

    # -- SPLASH SCREEN START --
    # Ana modüller yüklenmeden HEMEN göster
    splash = ModernSplash()
    splash.show()
    splash.raise_()
    splash.set_progress(5, "Yükleniyor...")
    
    # Şimdi ağır modülleri içe aktar
    from utils import settings as appset  # Ayarlar
    
    # 3) Tema uygula
    splash.set_progress(15, "Tema ayarları yükleniyor...")
    apply_theme(app)
    
    # 3.1) Veritabanı
    splash.set_progress(30, "Veritabanı başlatılıyor...")
    try:
        import db
        db.init_db()
        # MÜFREDAT YÖNETİMİ: Özel dersleri yükle
        if hasattr(db, 'load_custom_lessons'):
            db.load_custom_lessons()
    except Exception as e:
        print(e)
        
    # 3.2) Giriş Ekranı (Login)
    # Login ekranı modülünün import edilmesi de zaman alabilir
    splash.set_progress(50, "Kullanıcı modülleri yükleniyor...")
    try:
        enable_login = (appset.ayar_get("enable_login", "1") == "1")
        if enable_login:
            # Login varsa Splash kapanır, Login açılır
            from ui.login_window import ModernLoginWindow
            splash.close()
            
            login = ModernLoginWindow()
            if login.exec() != 1:
                sys.exit(0)
            
            # Login sonrası tekrar splash göstermiyoruz, ana pencereye geçeceğiz
            # Belki kısa bir "Hoşgeldiniz" splash'i? Gerek yok, hızlıca açalım.
    except Exception as e:
        print("Login hatası:", e)
        enable_login = False

    # 3.3) Lisans Kontrolü
    splash.set_progress(65, "Lisans durumu doğrulanıyor...")
    from utils.license_manager import manager
    is_dev = not getattr(sys, "frozen", False) and os.environ.get("YKS_FORCE_LICENSE", "0") != "1"
    lic_stat = manager.check_status()
    if not is_dev and lic_stat.get("status") != "valid":
        # Lisans penceresi arkada kalmasın diye splash ekranını hemen gizle!
        splash.hide()
        QApplication.processEvents()
        
        from ui.license_dialog import LicenseDialog
        dlg = LicenseDialog(None, can_cancel=False)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        
        res = dlg.exec()
        if res != 1 or manager.check_status().get("status") != "valid":
            sys.exit(0)
            
        # Lisans girildiyse splash'ı yeniden gösterip devam et
        if not enable_login:
            splash.show()
            splash.raise_()
            splash.set_progress(75, "Lisans aktifleştirildi! Arayüz hazırlanıyor...")

    if not enable_login:
        splash.set_progress(80, "Arayüz oluşturuluyor...")

    # 4) Ana pencere (EN AĞIR KISIM BURASI - Pandas vb. burada yükleniyor)
    from main_window import AnaPencere
    w = AnaPencere()

    splash.set_progress(90, "Takvim ayarları yapılıyor...")
    # 5) Takvim fix
    if callable(install_calendar_fix):
        try:
            install_calendar_fix(app, w, show_week_numbers=False, weekend_color="#e11d48")
        except Exception:
            pass

    splash.set_progress(100, "Hazır!")
    
    # 6) Göster
    def _start_main():
        splash.close()
        if sys.platform.startswith("win"):
            w.showMaximized()
        else:
            w.show()
    
    if not enable_login:
        # Login yoksa splash'ı görebilmek için çok kısa beklet (göz kırpması gibi olmasın)
        QTimer.singleShot(200, _start_main)
    else:
        if sys.platform.startswith("win"):
            w.showMaximized()
        else:
            w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
