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


from version import __version__


class ModernSplash(QSplashScreen):
    def __init__(self):
        w, h = 540, 350
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
        self.font_author = QFont(font_family, 8, QFont.Weight.Medium)
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
        painter.drawText(0, 134, w, 32, Qt.AlignmentFlag.AlignCenter, "KoçPilot 360")
        
        painter.setPen(QColor("#38bdf8"))
        painter.setFont(self.font_sub)
        painter.drawText(0, 168, w, 20, Qt.AlignmentFlag.AlignCenter, "BÜTÜNLEŞİK KOÇLUK & SINAV PLATFORMU")
        
        # Versiyon Rozeti (Pill Badge)
        badge_text = f"v{__version__} PRO" if '__version__' in globals() else "v3.5 PRO"
        badge_w = 90
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
        bar_y = h - 74
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
            
        # 10. Geliştirici & İletişim Bilgisi
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(self.font_author)
        painter.drawText(bar_x, h - 48, bar_w, 18, Qt.AlignmentFlag.AlignCenter, "👨‍💻 Hazırlayan: Osman Kütükçü   •   ✉ osmankutukcu@gmail.com")

        # 11. Alt Bilgi / Güvenlik
        painter.setPen(QColor("#64748b"))
        painter.setFont(self.font_foot)
        painter.drawText(bar_x, h - 25, bar_w // 2, 18, Qt.AlignmentFlag.AlignLeft, "🔒 Güvenli Veritabanı & Lisans Koruması")
        painter.drawText(bar_x + bar_w // 2, h - 25, bar_w // 2, 18, Qt.AlignmentFlag.AlignRight, "© 2021 - 2026 Tüm Hakları Saklıdır")


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
    # Normal kilit aynıdır; yalnız izole Windows pilotu ayrı kilit kullanır.
    # Böylece normal uygulama açıksa pilot sessizce çıkıp yanlış PASS üretmez.
    from services.pilot_boot_guard_v35 import pilot_instance_key
    app_id = pilot_instance_key("yks_lgs_odev_takip_v2_lock")
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
        # Test DB'sinin gerçek öğrenci DB'si olmadığını yazmadan ÖNCE denetle.
        from services.pilot_boot_guard_v35 import verify_pilot_database, write_pilot_ready
        verify_pilot_database(db.DB_PATH)
        db.init_db()
        # Bu belirteç yalnız başarılı DB açılışından sonra yazılır.
        write_pilot_ready(db.DB_PATH)
        # MÜFREDAT YÖNETİMİ: Özel dersleri yükle
        if hasattr(db, 'load_custom_lessons'):
            db.load_custom_lessons()
    except Exception as e:
        QMessageBox.critical(None, "Veritabanı Hatası", f"Veritabanı güvenle başlatılamadı: {e}")
        sys.exit(1)

    # 3.2) Giriş Ekranı (Login)
    # Login ekranı modülünün import edilmesi de zaman alabilir
    splash.set_progress(50, "Kullanıcı modülleri yükleniyor...")
    try:
        # Yeni kurulumda kullanıcı tablosu boşsa giriş ekranı atlanamaz.
        _security_con = db.get_conn()
        try:
            first_boot = _security_con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
        finally:
            _security_con.close()
        enable_login = first_boot or (appset.ayar_get("enable_login", "1") == "1")
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
        # Giriş hatası güvenliği devre dışı bırakmamalı (fail closed).
        QMessageBox.critical(None, "Güvenli Giriş Hatası", f"Giriş ekranı açılamadı: {e}")
        sys.exit(1)

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
    try:
        from ui.app_settings import _enhance_modern_settings
        _enhance_modern_settings()
    except Exception:
        pass
    from main_window import AnaPencere
    # V3578: Başarılı öğrenci yüklemelerinde dıştaki çift öneri/özet
    # hesaplarını atla. Ortam değişkeniyle kapatılabilir; çekirdek değişmez.
    try:
        from services.student_load_fastpath_v3578 import install_default_fastpath
        install_default_fastpath()
    except Exception:
        pass  # Optimizasyon çalışmazsa mevcut öğrenci yükleme devam eder.
    # V3577: sadece süre ölçümü; mevcut yükleme/progress/checkbox koduna dokunmaz.
    try:
        from services.student_load_profiler_v3577 import install_default_profiler
        install_default_profiler()
    except Exception:
        pass  # Diagnostik arızası programın açılışını engellememeli.
    # Modern & ergonomik ödev kayıt modu seçimi diyalogu (çekirdek dosya hash'i bozulmadan)
    try:
        from ui.homework_form import OdevTakipFormu
        from ui.save_mode_dialog import show_modern_save_mode_dialog
        OdevTakipFormu._kume_kaydet_modu_secimi = show_modern_save_mode_dialog
    except Exception:
        pass
    # V3.5.80+: Haftalık Çalışma Planı PDF dışa aktarma ve otopilot WhatsApp entegrasyonu
    try:
        from ui.homework_form import OdevTakipFormu
        from services.weekly_calendar_export_v35 import wrap_open_smart_calendar_pdf
        wrap_open_smart_calendar_pdf(OdevTakipFormu)
    except Exception:
        pass
    w = AnaPencere()
    w.setWindowTitle("KoçPilot 360 — Bütünleşik Koçluk & Sınav Platformu")
    try:
        from PyQt6.QtWidgets import QLabel, QMenu, QPushButton, QScrollArea
        from ui.brand_card_widget import BrandCardWidget

        # 1. Sol Sidebar: Eski metin etiketi yerine Kurumsal KoçPilot 360 Marka Kartı
        if hasattr(w, "sidebar") and w.sidebar.layout():
            for _lbl in w.sidebar.findChildren(QLabel):
                if "YKS/LGS" in _lbl.text() or "Asistanı" in _lbl.text():
                    _lbl.hide()
                    break
            brand_card = BrandCardWidget()
            w.sidebar.layout().insertWidget(0, brand_card)

            # QScrollArea üzerindeki seçicisiz 'background: transparent;' alt butonların
            # arka planını ezdiği için yalnızca QScrollArea ve doğrudan konteynerine sınırlandır
            for _sa in w.sidebar.findChildren(QScrollArea):
                _sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                _sa.setStyleSheet("""
                    QScrollArea { background: transparent; border: none; }
                    QScrollArea > QWidget { background: transparent; }
                    QScrollArea > QWidget > QWidget { background: transparent; }
                    QScrollBar:vertical {
                        background: transparent; width: 5px; margin: 2px 0px;
                    }
                    QScrollBar::handle:vertical {
                        background: rgba(148, 163, 184, 0.35); border-radius: 2px; min-height: 24px;
                    }
                    QScrollBar::handle:vertical:hover {
                        background: rgba(56, 189, 248, 0.65);
                    }
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        height: 0px; background: none;
                    }
                """)

        # 2. Sol Sidebar Butonları: Aktif hap (pill) durumu (Yaklaşım A: Modül açıkken mavi, kapanıp Genel Bakış'a dönünce otomatik Genel Bakış mavi)
        from PyQt6.QtCore import QEvent, QObject
        all_sidebar_btns = w.sidebar.findChildren(QPushButton)

        def _set_active_btn(target_btn):
            for btn in all_sidebar_btns:
                is_act = (btn == target_btn)
                btn.setProperty("active", "true" if is_act else "false")
                if not is_act and btn.hasFocus():
                    btn.clearFocus()
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()

        def _restore_home_if_on_dashboard():
            if not hasattr(w, "btnHome"):
                return
            # Modal bir pencere hala açıksa mevcut vurguyu koru
            if QApplication.activeModalWidget() is not None:
                return
            # Modal olmayan Detaylı Raporlar penceresi açıksa ve görünürse koru
            rep_dlg = getattr(w, "_report_dashboard", None)
            if rep_dlg is not None and rep_dlg.isVisible():
                return
            if hasattr(w, "stack") and w.stack.currentIndex() == 0:
                _set_active_btn(w.btnHome)

        for btn in all_sidebar_btns:
            # Basıldığı anda (modal dialog açılmadan hemen önce) mavi vurguyu yak
            btn.pressed.connect(lambda b=btn: _set_active_btn(b))
            # Tıklama (ve senkron modal dialog) bittiğinde Genel Bakış'a dönüldüyse vurguyu Genel Bakış'a geri al
            def _on_sidebar_btn_AfterClick(checked=False, b=btn):
                rep_dlg = getattr(w, "_report_dashboard", None)
                if b == getattr(w, "btnRapor", None) and rep_dlg is not None:
                    try:
                        rep_dlg.finished.connect(lambda *_: QTimer.singleShot(0, _restore_home_if_on_dashboard))
                    except Exception:
                        pass
                QTimer.singleShot(0, _restore_home_if_on_dashboard)
            btn.clicked.connect(_on_sidebar_btn_AfterClick)
            btn.released.connect(lambda: QTimer.singleShot(120, _restore_home_if_on_dashboard))

        class _SidebarNavigationSyncGuard(QObject):
            def eventFilter(self, watched, event):
                et = event.type()
                if watched is w and et in (QEvent.Type.WindowActivate, QEvent.Type.Show):
                    QTimer.singleShot(0, _restore_home_if_on_dashboard)
                elif et in (QEvent.Type.Hide, QEvent.Type.Close) and watched is not w:
                    QTimer.singleShot(20, _restore_home_if_on_dashboard)
                return False

        _nav_guard = _SidebarNavigationSyncGuard(w)
        app.installEventFilter(_nav_guard)
        w._sidebar_nav_guard = _nav_guard

        # Başlangıçta Ana Sayfa (Genel Bakış) aktif
        if hasattr(w, "btnHome"):
            _set_active_btn(w.btnHome)

        # 2.1 Rapor Merkezi: normal kullanımda YALNIZCA tek menü girişi görünür.
        # Eski rapor butonları ve bağlı orijinal fonksiyonları korunur. Yeni merkez
        # açılamazsa kullanıcıya sadece o an geçici bir yedek erişim sunulur.
        # Not: Bu blok Ödev Takip, Ödev Kontrol veya diğer analiz kodlarına dokunmaz.
        try:
            redundant_btns = [
                getattr(w, "btnOgrenciDetay", None),
                getattr(w, "btnPerformans", None),
                getattr(w, "btnRapor", None),
                getattr(w, "btnPdf", None),
                getattr(w, "btnGuide", None),
            ]
            btn_rc = QPushButton("📑   Rapor Merkezi")
            btn_rc.setObjectName("ThemeSidebarAction")
            btn_rc.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_rc.setToolTip("Tüm analiz, karne, detaylı rapor, veli PDF ve performans araçları tek merkezde")

            def _open_fallback_report_access():
                """Only invoked after Report Center fails, never a sidebar entry."""
                import logging
                from PyQt6.QtWidgets import QInputDialog, QMessageBox
                from services.report_entry_guard_v3594 import (
                    available_legacy_routes, open_legacy_route,
                )
                routes = available_legacy_routes(w)
                if not routes:
                    QMessageBox.warning(
                        w, "Yedek rapor erişimi",
                        "Mevcut rapor pencereleri bu kurulumda açılamıyor. "
                        "Ödev ve öğrenci kayıtları değiştirilmedi."
                    )
                    return
                options = [title for title, _ in routes]
                selected, ok = QInputDialog.getItem(
                    w, "Yedek Rapor Erişimi",
                    "Rapor Merkezi geçici olarak açılamadı. Kullanmak istediğiniz mevcut raporu seçin:",
                    options, 0, False
                )
                if not ok or selected not in options:
                    return
                method = routes[options.index(selected)][1]
                def _open_original():
                    try:
                        open_legacy_route(w, method)
                    except Exception:
                        logging.getLogger(__name__).exception(
                            "Yedek rapor yolu açılamadı: %s", method
                        )
                        QMessageBox.warning(
                            w, "Rapor açılamadı",
                            "Seçilen rapor şu anda açılamadı. Lütfen daha sonra tekrar deneyin."
                        )
                # Modal geçici seçim penceresi tamamen kapandıktan sonra aç.
                QTimer.singleShot(0, _open_original)

            def _report_center_open_failed():
                from PyQt6.QtWidgets import QMessageBox
                dialog = QMessageBox(w)
                dialog.setIcon(QMessageBox.Icon.Warning)
                dialog.setWindowTitle("Rapor Merkezi")
                dialog.setText("Rapor Merkezi şu anda açılamadı.")
                dialog.setInformativeText(
                    "Mevcut raporlar silinmedi. Tekrar deneyebilir veya "
                    "yalnızca bu hata durumunda yedek rapor listesine erişebilirsiniz."
                )
                retry_btn = dialog.addButton("Tekrar Dene", QMessageBox.ButtonRole.AcceptRole)
                fallback_btn = dialog.addButton("Yedek Rapor Erişimi", QMessageBox.ButtonRole.ActionRole)
                dialog.addButton("Kapat", QMessageBox.ButtonRole.RejectRole)
                dialog.exec()
                if dialog.clickedButton() is retry_btn:
                    QTimer.singleShot(0, _open_report_center)
                elif dialog.clickedButton() is fallback_btn:
                    QTimer.singleShot(0, _open_fallback_report_access)

            def _open_report_center():
                _set_active_btn(btn_rc)
                try:
                    # Tembel yükleme: eksik/bozuk yeni modül ana menüyü bozamaz.
                    from ui.report_center_v3581 import ReportCenterDialog
                    dlg = ReportCenterDialog(w)
                    dlg.exec()
                    intent = dlg.approved_navigation
                    if intent is not None:
                        # Modal pencere kapandıktan sonra mevcut formlar çağrılır.
                        def _go_to_selected_student(request=intent):
                            try:
                                from ui.report_navigation_bridge_v3594 import open_confirmed_navigation
                                open_confirmed_navigation(w, request)
                            except Exception:
                                import logging
                                logging.getLogger(__name__).exception('Kontrollü rapor geçişi engellendi')
                                from PyQt6.QtWidgets import QMessageBox
                                QMessageBox.warning(w, 'Geçiş tamamlanamadı',
                                    'Öğrenci kimliği veya hedef ekran doğrulanamadı. '
                                    'Mevcut kayıtlar değiştirilmedi.')
                        QTimer.singleShot(0, _go_to_selected_student)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Rapor Merkezi açılamadı")
                    _report_center_open_failed()
                finally:
                    QTimer.singleShot(0, _restore_home_if_on_dashboard)

            btn_rc.clicked.connect(_open_report_center)
            btn_rc.pressed.connect(lambda: _set_active_btn(btn_rc))
            btn_rc.released.connect(lambda: QTimer.singleShot(120, _restore_home_if_on_dashboard))

            # Hedef Analizi'nin önüne ekleme başarılı olursa eski BEŞ butonu gizle.
            # Yerleştirme başarısızsa eski menü kullanılabilir kalır.
            lout = None
            if hasattr(w, "btnTarget") and w.btnTarget.parentWidget():
                lout = w.btnTarget.parentWidget().layout()
            if lout is not None:
                t_idx = lout.indexOf(w.btnTarget)
                if t_idx >= 0:
                    lout.insertWidget(t_idx, btn_rc)
                else:
                    lout.addWidget(btn_rc)
                w.btnReportCenter = btn_rc
                all_sidebar_btns.append(btn_rc)
                for r_btn in redundant_btns:
                    if r_btn is not None:
                        r_btn.hide()
        except Exception:
            # Arızalı menü entegrasyonu eski rapor girişlerini yok edemez.
            import logging
            logging.getLogger(__name__).exception("Rapor Merkezi menü entegrasyonu tamamlanamadı")
            for r_btn in (
                getattr(w, "btnOgrenciDetay", None),
                getattr(w, "btnPerformans", None),
                getattr(w, "btnRapor", None),
                getattr(w, "btnPdf", None),
                getattr(w, "btnGuide", None),
            ):
                if r_btn is not None:
                    r_btn.show()

        # 3. Üst Gri Şeridi Gizle (Kompakt Karar Masasına Taşındı - Dikey Alan Tasarrufu)
        if hasattr(w, "_today_focus_v4"):
            w._today_focus_v4.hide()

            # Veri güncellendiğinde Karar Masası rozetini otomatik besle
            orig_present = getattr(w._today_focus_v4, "_present", None)
            if callable(orig_present):
                def _synced_present(result):
                    orig_present(result)
                    try:
                        cards = getattr(w._today_focus_v4, "_cards", [])
                        count = len(cards)
                        preview = ""
                        if cards:
                            preview = f"{cards[0].get('title', '')} — {cards[0].get('reason', '')}"
                        if hasattr(w, "dashboard") and hasattr(w.dashboard, "update_priorities_badge"):
                            w.dashboard.update_priorities_badge(count, preview)
                    except Exception:
                        pass
                w._today_focus_v4._present = _synced_present

            # Karar Masası [🔔 Öncelikler ▾] Butonu: Hızlı Açılır Menü
            if hasattr(w, "dashboard") and hasattr(w.dashboard, "sig_open_priorities"):
                def _show_priorities_dropdown():
                    cards = getattr(w._today_focus_v4, "_cards", [])
                    target_btn = getattr(w.dashboard, "btn_priorities", w.dashboard)
                    menu = QMenu(target_btn)
                    menu.setStyleSheet("""
                        QMenu {
                            background-color: #ffffff;
                            border: 1px solid #cbd5e1;
                            border-radius: 8px;
                            padding: 6px;
                            font-size: 12px;
                        }
                        QMenu::item {
                            padding: 8px 16px;
                            border-radius: 6px;
                            color: #1e293b;
                        }
                        QMenu::item:selected {
                            background-color: #eff6ff;
                            color: #1d4ed8;
                            font-weight: bold;
                        }
                    """)
                    if not cards:
                        act = menu.addAction("✅ Bekleyen acil öncelik bulunmuyor")
                        act.setEnabled(False)
                    else:
                        for c in cards[:8]:
                            sid = int(c.get("student_id", 0))
                            title = c.get("title", "Öğrenci")
                            reason = c.get("reason", "")
                            act = menu.addAction(f"📌 {title} — {reason}")
                            if sid > 0:
                                act.triggered.connect(lambda ch, s=sid: w.open_homework_for_student(s))
                        menu.addSeparator()
                        all_act = menu.addAction("📋 Tüm Öncelikleri Gör (Günün Özeti)...")
                        all_act.triggered.connect(w._smart_asistan)
                    menu.exec(target_btn.mapToGlobal(target_btn.rect().bottomLeft()))

                w.dashboard.sig_open_priorities.connect(_show_priorities_dropdown)

            # Karar Masası [⚡ Günün Özeti] Butonu: Günün Özeti Dialogunu Aç
            if hasattr(w, "dashboard") and hasattr(w.dashboard, "sig_open_summary"):
                def _open_summary_from_dash():
                    if hasattr(w, "btnSmart"):
                        _set_active_btn(w.btnSmart)
                    try:
                        w._smart_asistan()
                    finally:
                        QTimer.singleShot(0, _restore_home_if_on_dashboard)
                w.dashboard.sig_open_summary.connect(_open_summary_from_dash)

            # Platform Keşif Vitrini [Hemen Keşfet →] Butonlarını İlgili Modüle Bağla
            if hasattr(w, "dashboard") and hasattr(w.dashboard, "sig_open_feature"):
                def _handle_feature_launch(f_key: str):
                    try:
                        if f_key == "mobile" and hasattr(w, "_cep_programi"):
                            if hasattr(w, "btnCep"):
                                _set_active_btn(w.btnCep)
                            w._cep_programi()
                        elif f_key == "topic_map" and hasattr(w, "_open_topic_map"):
                            if hasattr(w, "btnKonuHaritasi"):
                                _set_active_btn(w.btnKonuHaritasi)
                            w._open_topic_map()
                        elif f_key == "pomodoro" and hasattr(w, "_open_pomodoro"):
                            if hasattr(w, "btnPomodoro"):
                                _set_active_btn(w.btnPomodoro)
                            w._open_pomodoro()
                        elif f_key == "target" and hasattr(w, "_hedef_analiz_open"):
                            if hasattr(w, "btnTarget"):
                                _set_active_btn(w.btnTarget)
                            w._hedef_analiz_open()
                        elif f_key == "whatsapp" and hasattr(w, "_wp_hizli"):
                            if hasattr(w, "btnWp"):
                                _set_active_btn(w.btnWp)
                            w._wp_hizli()
                        elif f_key == "simulation" and hasattr(w, "_open_exam_simulation"):
                            if hasattr(w, "btnSimulasyon"):
                                _set_active_btn(w.btnSimulasyon)
                            w._open_exam_simulation()
                    except Exception:
                        pass
                    finally:
                        QTimer.singleShot(0, _restore_home_if_on_dashboard)

                w.dashboard.sig_open_feature.connect(_handle_feature_launch)

            # Dashboard her yenilendiğinde öncelik analizini ve aktif menü vurgusunu tazele
            if hasattr(w, "dashboard") and hasattr(w.dashboard, "refresh_stats"):
                orig_refresh_stats = w.dashboard.refresh_stats
                def _synced_refresh():
                    orig_refresh_stats()
                    try:
                        w._today_focus_v4.request_refresh()
                    except Exception:
                        pass
                    QTimer.singleShot(0, _restore_home_if_on_dashboard)
                w.dashboard.refresh_stats = _synced_refresh

    except Exception:
        import logging
        logging.getLogger(__name__).exception("KoçPilot 360 arayüz geliştirmeleri yüklenirken hata oluştu")

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
