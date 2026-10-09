# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
import os

# ==== (senin mevcut importların) ====
# from ui.rapor_deneme import RaporDeneme <-- Lazy Loaded
from ui.theme import apply as apply_theme
from ui.deneme_sonuclari import DenemeSonuclari
# from ui.user_manager import UserManager  <-- Removed incorrect import
from ui.responsive import apply_responsive
# from ui.rapor_kok_neden import RaporKokNeden <-- Lazy Loaded
# from ui.rapor_trend import RaporTrend        <-- Lazy Loaded

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox,
    QDialog, QVBoxLayout as QVBL2, QListWidget, QTextEdit, QLabel, QSizePolicy,
    QGridLayout, QInputDialog, QGraphicsDropShadowEffect, QToolButton, QMenu, QLineEdit,
    QTableWidget, QHeaderView, QTableWidgetItem, QAbstractItemView, QApplication,
    QFrame, QScrollArea
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QObject, QEvent, QEasingCurve, QVariantAnimation, QPoint, QRectF
)
from PyQt6.QtGui import (
    QIcon, QFont, QColor, QAction, QShortcut, QKeySequence, QActionGroup,
    QPainter, QLinearGradient, QBrush, QPen
)

from ui.student_form import OgrenciFormu
from ui.homework_form import OdevTakipFormu
# from ui.reports import RaporlarFormu            <-- Lazy Loaded
from ui.topic_editor import DersKonuEditor
# from ui.whatsapp_logs import WhatsappLogRaporu  <-- Lazy Loaded
from ui.modern_settings import ModernSettingsDialog as UygulamaAyarlar
import db
from ui.performans_paneli import PerformansPaneli

# from ui.report_dashboard import ReportDashboard <-- Lazy Loaded
# Kriter ayarları ana formdan açılmayacaksa bunu eklemen gerekmiyor ama
# istersen yine de dursun:
from ui.report_settings import ReportSettingsDialog


# +++ EKLE +++
from ui.student_detail import OgrenciDetayDialog
# from ui.trial_exam_manager import TrialExamManager <-- Lazy Loaded
# from ui.coaching_manager import CoachingManager    <-- Lazy Loaded
# from utils import analytics_engine as ae           <-- Lazy Loaded
import sqlite3
import version

# Hata yakalama (global)
try:
    from utils.error_manager import install_global_hook
except Exception:
    def install_global_hook():  # yoksa boş bırak
        pass


class _FormDialog(QDialog):
    """Formları tam ekran modal göstermek için basit kapsayıcı."""
    def __init__(self, widget_cls, parent):
        super().__init__(parent)
        self.setWindowTitle(widget_cls.__name__)
        lay = QVBL2(self)
        self.inner = widget_cls(self)
        lay.addWidget(self.inner)

        # Eski sabit boyut:
        # self.resize(1200, 800)

        # >>> MAX açılması için:
        from PyQt6.QtCore import Qt
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
# ============================
#   Modern Başlık Bileşeni
# ============================
class TitleLabel(QLabel):
    """
    Animasyonlu gradient + yumuşak glow efektli başlık etiketi.
    Gradient akışı ve hafif glow nabız efektleri korunur.
    """
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(64)                           # ↑ daha yüksek şerit
        f = QFont(self.font().family(), 22, QFont.Weight.Bold)  # ↑ başlık daha büyük
        self.setFont(f)

        # Parlama (glow)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setOffset(0, 0)
        self._glow.setBlurRadius(22)                       # ↑ biraz daha parlak
        self._glow.setColor(QColor(13, 110, 253, 110))
        self.setGraphicsEffect(self._glow)

        # Glow nabız animasyonu
        self._glow_anim = QVariantAnimation(self)
        self._glow_anim.setStartValue(16.0)
        self._glow_anim.setEndValue(26.0)
        self._glow_anim.setDuration(1800)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._glow_anim.valueChanged.connect(lambda v: self._glow.setBlurRadius(float(v)))
        self._glow_anim.finished.connect(self._reverse_glow)
        self._glow_anim.start()

        # Gradient kaydırma animasyonu
        self._grad_pos = 0.0
        self._grad_anim = QVariantAnimation(self)
        self._grad_anim.setStartValue(0.0)
        self._grad_anim.setEndValue(1.0)
        self._grad_anim.setDuration(3500)
        self._grad_anim.setLoopCount(-1)
        self._grad_anim.valueChanged.connect(self._on_grad)
        self._grad_anim.start()

    def _reverse_glow(self, ):
        sv, ev = self._glow_anim.startValue(), self._glow_anim.endValue()
        self._glow_anim.setStartValue(ev); self._glow_anim.setEndValue(sv); self._glow_anim.start()

    def _on_grad(self, v: float):
        self._grad_pos = float(v); self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        rect = self.rect()
        w = rect.width()
        start_x = -w + (2 * w * self._grad_pos)
        grad = QLinearGradient(start_x, 0, start_x + w, 0)
        grad.setColorAt(0.00, QColor("#60a5fa"))
        grad.setColorAt(0.50, QColor("#0d6efd"))
        grad.setColorAt(1.00, QColor("#22d3ee"))

        path = self._text_path(self.text(), rect)
        painter.fillPath(path, QBrush(grad))
        pen = QPen(QColor(0, 0, 0, 40)); pen.setWidthF(1.0)
        painter.setPen(pen); painter.drawPath(path)

    def _text_path(self, text: str, rect):
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(text); th = fm.height()
        x = rect.x() + (rect.width() - tw) / 2
        y = rect.y() + (rect.height() + th) / 2 - fm.descent()
        path.addText(x, y, self.font(), text)
        return path
# ==============================
#   Hover Efektli Modern Buton
# ==============================
class FancyButton(QPushButton):
    """
    Hover'da yumuşak yükselme (gölge artar), basılı tutmada hafif 'press' hissi.
    Renkler stylesheet üzerinden, gölge efektleri burada.
    """
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 2)
        self._shadow.setBlurRadius(10)
        self._shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(self._shadow)

        # Gölge animasyonu
        self._shadow_anim = QVariantAnimation(self)
        self._shadow_anim.setDuration(160)
        self._shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._shadow_anim.valueChanged.connect(self._apply_shadow_value)

    def _apply_shadow_value(self, v: float):
        self._shadow.setBlurRadius(10 + 8 * v)
        self._shadow.setOffset(0, 2 - 1 * v)  # hafif yükselme efekti

    def enterEvent(self, e):
        self._animate_to(1.0)
        return super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_to(0.0)
        return super().leaveEvent(e)

    def mousePressEvent(self, e):
        # basmada hafif 'ink press' için gölge küçült
        self._animate_to(0.2)
        return super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._animate_to(1.0)
        return super().mouseReleaseEvent(e)

    def _animate_to(self, val: float):
        self._shadow_anim.stop()
        self._shadow_anim.setStartValue(self._shadow_anim.currentValue() if self._shadow_anim.state() != QVariantAnimation.State.Stopped else 0.0)
        self._shadow_anim.setEndValue(val)
        self._shadow_anim.start()

# ============================
#        ANA PENCERE
# ============================
class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YKS/LGS Ödev & Takip Yöneticisi")

        # --- LİSANS KONTROLÜ ---
        from ui.license_dialog import LicenseDialog
        from utils.license_manager import manager
        
        is_dev = not getattr(sys, "frozen", False) and os.environ.get("YKS_FORCE_LICENSE", "0") != "1"
        lic_stat = manager.check_status()
        if not is_dev and lic_stat["status"] != "valid":
             for w_top in QApplication.topLevelWidgets():
                 if isinstance(w_top, QSplashScreen):
                     w_top.hide()
             dlg = LicenseDialog(None, can_cancel=False)
             dlg.show()
             dlg.raise_()
             dlg.activateWindow()
             res = dlg.exec()
             if res != 1 or manager.check_status()["status"] != "valid":
                 sys.exit(0)
        # -----------------------
        self._update_window_title()

        # === Ölçüler (tek yerden değiştir) ===
        BUTTON_W, BUTTON_H = 240, 42  # hepsi eşit (Daha kompakt)
        GRID_HSP, GRID_VSP = 8, 8

        # DB & hata kancası
        db.init_db()
        try:
            install_global_hook()
        except Exception:
            pass

        # ---------- Ana layout ----------
        # ---------- Ana layout (SIDEBAR + CONTENT) ----------
        w = QWidget(objectName="RootArea")
        self.setCentralWidget(w)
        
        # Ana yatay yerleşim
        main_h_layout = QHBoxLayout(w)
        main_h_layout.setContentsMargins(0, 0, 0, 0)
        main_h_layout.setSpacing(0)

        # 1. SIDEBAR (SOL MENÜ)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(240)
        self.sidebar.setStyleSheet("""
            QWidget#Sidebar {
                background-color: #f8f9fa;
                border-right: 1px solid #e9ecef;
            }
        """)
        
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(15, 20, 15, 20)
        side_layout.setSpacing(10)
        
        # Başlık ve İkon
        lbl_brand = QLabel("YKS/LGS\nAsistanı v2")
        lbl_brand.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lbl_brand.setStyleSheet("font-size: 20px; font-weight: 800; color: #1e293b; margin-bottom: 10px;")
        side_layout.addWidget(lbl_brand)
        
        # --- MENÜ BUTONLARI ---
        
        # Helper: Sidebar için stil
        def style_sidebar_btn(btn, icon_char=None):
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 10px 15px;
                    border: none;
                    border-radius: 8px;
                    background-color: transparent;
                    color: #475569;
                    font-size: 14px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    color: #0f172a;
                }
                QPushButton:pressed {
                    background-color: #cbd5e1;
                }
            """)
            if icon_char:
                btn.setText(f"{icon_char}   {btn.text()}")
            # Cursor
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            return btn

        # Dashboard Butonu (Ana Sayfa)
        self.btnHome = QPushButton("Genel Bakış")
        self.btnHome = style_sidebar_btn(self.btnHome, "🏠")
        def _go_home():
            self.stack.setCurrentIndex(0)
            if hasattr(self, "dashboard") and self.dashboard:
                self.dashboard.refresh_stats()
        self.btnHome.clicked.connect(_go_home)
        side_layout.addWidget(self.btnHome)
        
        # Ayırıcı
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #e2e8f0;")
        side_layout.addWidget(line)
        
        # Diğer Butonlar (Scroll Area içine alalım eğer çoksa, ama şimdilik düz sığar)
        from PyQt6.QtWidgets import QScrollArea
        scroll_menu = QScrollArea()
        scroll_menu.setWidgetResizable(True)
        scroll_menu.setFrameShape(QFrame.Shape.NoFrame)
        scroll_menu.setStyleSheet("background: transparent;")
        
        menu_container = QWidget()
        menu_layout = QVBoxLayout(menu_container)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(5)
        
        # Buton Tanımları (Grup Grup)
        # 1. Öğrenci İşlemleri
        lbl_grup1 = QLabel("ÖĞRENCİ & TAKİP")
        lbl_grup1.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; margin-top: 10px;")
        menu_layout.addWidget(lbl_grup1)
        
        self.btnOgr = style_sidebar_btn(QPushButton("Öğrenci Kaydı"), "👤")
        self.btnOdev = style_sidebar_btn(QPushButton("Ödev Takip"), "📚")
        self.btnDeneme = style_sidebar_btn(QPushButton("Deneme Sınavları"), "📝")
        # self.btnSimulasyon burada tanımlıydı, aşağı taşıyoruz
        self.btnKoc = style_sidebar_btn(QPushButton("Koçluk Planı"), "🎯")
        self.btnHizli = style_sidebar_btn(QPushButton("Hızlı Görüşme"), "⚡")
        
        menu_layout.addWidget(self.btnOgr)
        menu_layout.addWidget(self.btnOdev)
        menu_layout.addWidget(self.btnDeneme)
        # Sınav Modu taşındı
        menu_layout.addWidget(self.btnKoc)
        menu_layout.addWidget(self.btnHizli)

        # 2. Analiz & Rapor
        lbl_grup2 = QLabel("ANALİZ")
        lbl_grup2.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; margin-top: 15px;")
        menu_layout.addWidget(lbl_grup2)
        
        self.btnOgrenciDetay = style_sidebar_btn(QPushButton("Öğrenci Detayı"), "🆔")
        self.btnPerformans = style_sidebar_btn(QPushButton("Performans Paneli"), "📊")
        self.btnTarget = style_sidebar_btn(QPushButton("Hedef Analizi"), "🎯") # NEW
        self.btnRapor = style_sidebar_btn(QPushButton("Detaylı Raporlar"), "📈")
        self.btnPdf = style_sidebar_btn(QPushButton("Hızlı PDF"), "📄")
        self.btnGuide = style_sidebar_btn(QPushButton("Rapor Rehberi"), "ℹ️")
        
        menu_layout.addWidget(self.btnOgrenciDetay)
        menu_layout.addWidget(self.btnPerformans)
        menu_layout.addWidget(self.btnTarget) # NEW
        menu_layout.addWidget(self.btnRapor)
        
        self.btnCep = style_sidebar_btn(QPushButton("Cep Ajandası"), "📱")
        menu_layout.addWidget(self.btnCep)
        
        self.btnSmart = style_sidebar_btn(QPushButton("Günün Akıllı Özeti"), "🧠")
        menu_layout.addWidget(self.btnSmart)
        
        menu_layout.addWidget(self.btnPdf)
        menu_layout.addWidget(self.btnGuide)

        # 3. Araçlar
        lbl_grup3 = QLabel("ARAÇLAR")
        lbl_grup3.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; margin-top: 15px;")
        menu_layout.addWidget(lbl_grup3)
        
        self.btnDersKonu = style_sidebar_btn(QPushButton("Müfredat"), "📖")
        self.btnMail = style_sidebar_btn(QPushButton("Mail Gönder"), "📧")
        self.btnWp = style_sidebar_btn(QPushButton("WP Toplu Mesaj"), "💬")
        self.btnWpLog = style_sidebar_btn(QPushButton("WP Logları"), "📋")
        self.btnUsers = style_sidebar_btn(QPushButton("Kullanıcılar"), "🔑")
        self.btnOnar = style_sidebar_btn(QPushButton("DB Bakım"), "🛠️")
        self.btnAyar = style_sidebar_btn(QPushButton("Ayarlar"), "⚙️")

        self.btnSimulasyon = style_sidebar_btn(QPushButton("Sınav Modu"), "⏳") # Taşındı
        self.btnKonuHaritasi = style_sidebar_btn(QPushButton("Konu Haritası (Beta)"), "🗺️") # Yeni
        self.btnPomodoro = style_sidebar_btn(QPushButton("Odak / Pomodoro"), "🍅") # Yeni

        menu_layout.addWidget(self.btnSimulasyon) # Buraya eklendi
        menu_layout.addWidget(self.btnDersKonu)
        menu_layout.addWidget(self.btnKonuHaritasi) # Yeni
        menu_layout.addWidget(self.btnPomodoro) # Yeni
        menu_layout.addWidget(self.btnMail)
        menu_layout.addWidget(self.btnWp)
        menu_layout.addWidget(self.btnWpLog)
        menu_layout.addWidget(self.btnUsers)
        menu_layout.addWidget(self.btnOnar)
        menu_layout.addWidget(self.btnAyar)
        
        # Diğer az kullanılanlar / Footer üstü
        self.btnHakkinda = style_sidebar_btn(QPushButton("Hakkında"), "❓")
        self.btnTema = style_sidebar_btn(QPushButton("Tema"), "🎨")
        self.btnGuncelleme = style_sidebar_btn(QPushButton("Güncellemeler"), "🔄")
        self.btnLisans = style_sidebar_btn(QPushButton("Lisans Bilgisi"), "🔑")

        menu_layout.addSpacing(10)
        menu_layout.addWidget(self.btnHakkinda)
        menu_layout.addWidget(self.btnTema)
        menu_layout.addWidget(self.btnGuncelleme)
        menu_layout.addWidget(self.btnLisans)

        menu_layout.addStretch()
        scroll_menu.setWidget(menu_container)
        side_layout.addWidget(scroll_menu)

        # Footer
        foot = QLabel(f"v{version.APP_VERSION}")
        foot.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_layout.addWidget(foot)


        # 2. İÇERİK ALANI (SAĞ T KISIM)
        content_host = QWidget()
        content_host.setStyleSheet("QWidget { background-color: #f1f5f9; }") # Slight gray bg for content area
        content_layout = QVBoxLayout(content_host)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(12)

        # Güncelleme Bildirim Bandı (Banner)
        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        self.update_banner.setStyleSheet("""
            QFrame#UpdateBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ecfdf5, stop:1 #f0fdf4);
                border: 1px solid #10b981;
                border-radius: 8px;
            }
        """)
        lay_b = QHBoxLayout(self.update_banner)
        lay_b.setContentsMargins(14, 8, 14, 8)

        self.lbl_banner_text = QLabel("🎉 Yeni bir güncelleme mevcut!")
        self.lbl_banner_text.setStyleSheet("color: #065f46; font-size: 13px; font-weight: 500;")

        btn_banner_action = QPushButton("🚀 Şimdi İncele ve Güncelle")
        btn_banner_action.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_banner_action.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white; border: none;
                border-radius: 6px; padding: 5px 14px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        btn_banner_action.clicked.connect(self._open_cached_update_dialog)

        btn_banner_close = QPushButton("✕")
        btn_banner_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_banner_close.setFixedSize(24, 24)
        btn_banner_close.setStyleSheet("border: none; color: #065f46; font-weight: bold; font-size: 14px;")
        btn_banner_close.clicked.connect(lambda: self.update_banner.setVisible(False))

        lay_b.addWidget(self.lbl_banner_text)
        lay_b.addStretch(1)
        lay_b.addWidget(btn_banner_action)
        lay_b.addSpacing(6)
        lay_b.addWidget(btn_banner_close)

        self.update_banner.setVisible(False)
        content_layout.addWidget(self.update_banner)

        # Stacked Widget (Sayfalar Arası Geçiş)
        from PyQt6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)

        # --- SAYFA 0: DASHBOARD ---
        from ui.dashboard_widget import DashboardWidget
        from PyQt6.QtWidgets import QScrollArea
        self.dashboard = DashboardWidget()
        self.scroll_dash = QScrollArea()
        self.scroll_dash.setWidget(self.dashboard)
        self.scroll_dash.setWidgetResizable(True)
        self.scroll_dash.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_dash.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.stack.addWidget(self.scroll_dash)

        # --- BAĞLANTI (LAYOUT) ---
        main_h_layout.addWidget(self.sidebar)
        main_h_layout.addWidget(content_host, stretch=1)

        # Sinyalleri bağla (Dashboard Widget içinden gelenler)
        self.dashboard.sig_open_today.connect(lambda: self._open_randevu_filter('today'))
        self.dashboard.sig_open_overdue.connect(lambda: self._open_randevu_filter('overdue'))
        self.dashboard.sig_open_students.connect(self._ogrenci_ac)
        

        
        # Özel Buton Bağlantıları (Standart dışı olanlar)
        self.btnGuide.clicked.connect(self._show_report_guide)

        # Sinyaller
        self.btnOgr.clicked.connect(self._ogrenci_ac)
        self.btnOdev.clicked.connect(self._odev_ac)
        self.btnRapor.clicked.connect(self._rapor_ac)
        self.btnOnar.clicked.connect(self._onar_menu)
        self.btnDersKonu.clicked.connect(self._ders_konu)
        self.btnWpLog.clicked.connect(self._wp_log)
        self.btnAyar.clicked.connect(self._ayarlar)
        self.btnHizli.clicked.connect(self._hizli_gorusme)
        self.btnWp.clicked.connect(self._wp_hizli)
        self.btnMail.clicked.connect(self._mail_gonder)
        self.btnHakkinda.clicked.connect(self._hakkinda)
        self.btnTema.clicked.connect(self._tema_degistir)
        self.btnPerformans.clicked.connect(self._performans_paneli)

        # +++ EKLE +++
        self.btnOgrenciDetay.clicked.connect(self._ogrenci_detay)
        self.btnUsers.clicked.connect(self._user_manager)
        self.btnDeneme.clicked.connect(self._deneme_ac)
        self.btnSimulasyon.clicked.connect(self._open_exam_simulation)
        self.btnKoc.clicked.connect(self._koc_ac)
        
        self.btnPdf.clicked.connect(self._create_pdf_report)
        self.btnCep.clicked.connect(self._cep_programi)
        self.btnSmart.clicked.connect(self._smart_asistan)
        self.btnTarget.clicked.connect(self._hedef_analiz_open)
        
        # Yeni Araçlar
        self.btnKonuHaritasi.clicked.connect(self._open_topic_map)
        self.btnPomodoro.clicked.connect(self._open_pomodoro)
        self.btnGuncelleme.clicked.connect(self._manual_check_update)
        self.btnLisans.clicked.connect(self._lisans_yonetimi_ac)
        try:
             # Lazy analytics load - sadece buton varsa bağla
             if hasattr(self, "btnAnalizYenile"):
                 self.btnAnalizYenile.clicked.connect(self._analiz_yenile)
        except Exception:
             pass

        # Tema & Responsive
        try:
            from PyQt6.QtWidgets import QApplication as _QApp
            apply_theme(_QApp.instance())
        except Exception:
            pass
        try:
            apply_responsive(self)
        except Exception:
            pass

        # Otomatik hatırlatıcı
        try:
            self._setup_auto_reminder()
        except Exception:
            pass

        # Gölge
        self._apply_root_shadow(w)

        # === Pencereyi içeriğe tam oturt (kritik) ===
        # === Pencereyi içeriğe tam oturt (kritik) ===
        # === Pencereyi içeriğe tam oturt (kritik) ===
        # FIX: "SetFixedSize" bazen yarış durumu (race condition) yaratıp pencereyi
        # içeriğin tam yüklenmediği andaki küçük boyuta kilitliyor.
        # Bunun yerine esnek bırakıyoruz ve minimum boyut atıyoruz.
        
        # root.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        # self.adjustSize()
        
        # Pencerenin çok küçülmesini engelle
        self.setMinimumWidth(850)
        self.setMinimumHeight(600)
        
        # Windows'ta ekran alanına göre tam ekran/maximize aç, Mac'te ideal boyutta aç
        if sys.platform.startswith("win"):
            QTimer.singleShot(100, self.showMaximized)
        else:
            QTimer.singleShot(100, lambda: self.resize(self.sizeHint()))

        # === Spotlight (Ctrl+K) ===
        self.shortcut_spot = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut_spot.activated.connect(self._open_spotlight)

        # Otomatik arka plan güncelleme denetimi (3.5 saniye sonra sessizce başlar)
        self._cached_update_info = None
        QTimer.singleShot(3500, self._check_updates_background)

    def _open_spotlight(self):
        try:
            from ui.spotlight import SpotlightDialog
            dlg = SpotlightDialog(self)
            dlg.exec()
        except Exception as e:
            print("Spotlight error:", e)

    # =========================================================================
    # OTOMATİK GÜNCELLEME (AUTO-UPDATE) YÖNETİMİ
    # =========================================================================
    def _check_updates_background(self):
        """Uygulama açılışından birkaç saniye sonra sessizce güncelleme denetler."""
        try:
            from utils.updater import UpdateCheckerThread
            self._bg_update_checker = UpdateCheckerThread(parent=self)
            self._bg_update_checker.check_completed.connect(self._on_background_update_checked)
            self._bg_update_checker.start()
        except Exception as e:
            print(f"Arka plan güncelleme kontrolü başlatılamadı: {e}")

    def _on_background_update_checked(self, res: dict):
        if res and res.get("has_update"):
            self._cached_update_info = res
            self._show_update_banner(res)

    def _show_update_banner(self, info: dict):
        if hasattr(self, "update_banner") and hasattr(self, "lbl_banner_text"):
            new_v = info.get("latest_version", "")
            self.lbl_banner_text.setText(f"🎉 Yeni bir güncelleme mevcut: <b>v{new_v}</b> (En son özellikler ve iyileştirmeler hazır)")
            self.update_banner.setVisible(True)

    def _open_cached_update_dialog(self):
        if self._cached_update_info:
            from ui.update_dialog import UpdateDialog
            dlg = UpdateDialog(self._cached_update_info, parent=self)
            dlg.exec()
        else:
            self._manual_check_update()

    def _manual_check_update(self):
        """Kullanıcı butondan tıkladığında çalışan manuel denetim."""
        from utils.updater import UpdateCheckerThread
        if hasattr(self, "btnGuncelleme"):
            self.btnGuncelleme.setEnabled(False)
            self.btnGuncelleme.setText("🔄 Kontrol Ediliyor...")

        self._manual_checker = UpdateCheckerThread(parent=self)

        def _on_done(res: dict):
            if hasattr(self, "btnGuncelleme"):
                self.btnGuncelleme.setEnabled(True)
                self.btnGuncelleme.setText("🔄   Güncellemeler")

            if res.get("has_update"):
                self._cached_update_info = res
                self._show_update_banner(res)
                from ui.update_dialog import UpdateDialog
                dlg = UpdateDialog(res, parent=self)
                dlg.exec()
            else:
                import version
                QMessageBox.information(
                    self, "Sistem Güncel",
                    f"Tebrikler! En son sürümü (v{version.APP_VERSION}) kullanıyorsunuz.\n\n"
                    "Şu anda yüklenecek yeni bir güncelleme bulunmuyor."
                )

        def _on_err(err_msg: str):
            if hasattr(self, "btnGuncelleme"):
                self.btnGuncelleme.setEnabled(True)
                self.btnGuncelleme.setText("🔄   Güncellemeler")
            QMessageBox.warning(
                self, "Bağlantı Uyarısı",
                f"Güncellemeler kontrol edilirken bağlantı sağlanamadı:\n{err_msg}\n\n"
                "Lütfen internet bağlantınızı kontrol ediniz veya GitHub sayfasını ziyaret ediniz."
            )

        self._manual_checker.check_completed.connect(_on_done)
        self._manual_checker.check_failed.connect(_on_err)
        self._manual_checker.start()

    # --------- Görsel yardımcılar ---------
    def _apply_root_shadow(self, widget: QWidget):
        try:
            shadow = QGraphicsDropShadowEffect(widget)
            shadow.setOffset(0, 4)
            shadow.setBlurRadius(24)
            shadow.setColor(QColor(0, 0, 0, 45))
            widget.setGraphicsEffect(shadow)
        except Exception:
            pass

    # ------------------ Dialog açıcı yardımcı ------------------
    def _show_dialog(self, widget_cls, *, mode: str = "max", hide_main: bool = True):
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QMessageBox, QSizePolicy, QApplication
        )
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication
        import traceback

        # Ana pencerenin durumunu hatırla
        try:
            _prev_geom = self.saveGeometry()
            _was_max = self.isMaximized()
            _was_full = self.isFullScreen()
        except Exception:
            _prev_geom = None
            _was_max = False
            _was_full = False

        dlg = QDialog(self)
        dlg.setWindowTitle(widget_cls.__name__)
        dlg.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setSizeGripEnabled(True)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)

        try:
            inner = widget_cls(dlg)

            # --- İÇ FORMU EKRANA GÖRE ESNEK YAP ---
            try:
                inner.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Expanding
                )
                inner.setMinimumSize(0, 0)
                inner.setMaximumSize(16777215, 16777215)
            except Exception:
                pass

            lay.addWidget(inner)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Açılış Hatası",
                f"{widget_cls.__name__} oluşturulamadı:\n\n{e}\n\n{traceback.format_exc()}"
            )
            dlg.deleteLater()
            return

        if hide_main:
            try:
                self.hide()
            except Exception:
                pass

        # --- PENCEREYİ EKRANA GÖRE AYARLA ---
        screen = None
        try:
            # Mümkünse ana pencerenin ekranı, yoksa primary
            screen = self.windowHandle().screen() if self.windowHandle() else QGuiApplication.primaryScreen()
        except Exception:
            screen = QGuiApplication.primaryScreen()

        if mode == "full":
            dlg.showFullScreen()

        elif mode == "max":
            # Önce ekranın kullanılabilir alanına göre boyut ver
            if screen is not None:
                rect = screen.availableGeometry()  # görev çubuğu hariç alan
                dlg.setMinimumSize(0, 0)
                # İlk açılışta ekranı aşmasın
                dlg.resize(rect.width(), rect.height())
            # Sonra NORMAL maximize çağrısı: görev çubuğu kalır
            dlg.showMaximized()

        else:
            dlg.resize(1200, 800)
            dlg.show()
        # --------------------------------------

        try:
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            pass

        try:
            dlg.exec()
        finally:
            # Ana pencereyi önceki haline döndür
            try:
                if hide_main:
                    if _was_full:
                        self.showFullScreen()
                    elif _was_max:
                        self.showMaximized()
                    else:
                        if _prev_geom and not (_was_max or _was_full):
                            self.restoreGeometry(_prev_geom)
                        self.showNormal()
                else:
                    if _prev_geom and not (_was_max or _was_full):
                        self.restoreGeometry(_prev_geom)

                self.raise_()
                self.activateWindow()
            except Exception:
                pass

            try:
                dlg.deleteLater()
            except Exception:
                pass

            try:
                if hasattr(self, "dashboard") and self.dashboard:
                    self.dashboard.refresh_stats()
            except Exception:
                pass


    # ------------------ Buton handler'ları ------------------
    # ------------------ Buton handler'ları ------------------
    def _ogrenci_ac(self): self._show_dialog(OgrenciFormu)
    def _odev_ac(self):    self._show_dialog(OdevTakipFormu)
    
    def _rapor_ac(self):
        """
        Ana ekrandaki 'Raporlar' butonu:
        Toplu Değerlendirme / Veli Raporu penceresini açar.
        (Artık modal değil, normal pencere olarak açıyoruz.)
        """
        # Zaten açıksa öne getir
        dlg = getattr(self, "_report_dashboard", None)
        if dlg is not None:
            try:
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                pass
            return

        # Yeni pencere oluştur
        try:
            con = db.get_conn()
        except Exception as e:
            self._show_error("Veritabanı", f"Veritabanı bağlantısı açılamadı:\n{e}")
            return

        # LAZY LOAD: Matplotlib
        from ui.report_dashboard import ReportDashboard
        dlg = ReportDashboard(con, self)
        dlg.setModal(False)  # dialog olsa bile modal olmasın
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        # Kapanınca referansı temizle
        dlg.finished.connect(lambda: setattr(self, "_report_dashboard", None))
        
        self._report_dashboard = dlg
        dlg.showMaximized()

    def _show_report_guide(self):
        from ui.report_guide_dialog import ReportGuideDialog
        dlg = ReportGuideDialog(self)
        dlg.exec()

        from ui.report_guide_dialog import ReportGuideDialog
        dlg = ReportGuideDialog(self)
        dlg.exec()

    def _cep_programi(self):
        """Mobil uyumlu, ödev tarihli haftalık ajanda oluşturur."""
        from ui.mobile_schedule import MobileScheduleGenerator
        gen = MobileScheduleGenerator(self)
        gen.generate()

    def _smart_asistan(self):
        """Günün Akıllı Özeti (Koç Asistanı) panelini açar."""
        from ui.smart_assistant_dialog import SmartAssistantDialog
        dlg = SmartAssistantDialog(self)
        dlg.exec()

    def _hedef_analiz_open(self):
        """Akıllı Hedef Analizi penceresini açar."""
        from ui.target_analysis_dialog import TargetAnalysisDialog
        dlg = TargetAnalysisDialog(self)
        dlg.exec()


    def _open_topic_map(self):
        """Konu Haritası (İlerleme Takibi)"""
        from ui.topic_map_dialog import TopicMapDialog
        dlg = TopicMapDialog(self)
        dlg.showMaximized()
        dlg.exec()

    def _open_pomodoro(self):
        """Pomodoro Zamanlayıcı"""
        from ui.pomodoro_dialog import PomodoroDialog
        dlg = PomodoroDialog(self)
        dlg.exec()

    def _ders_konu(self):  self._show_dialog(DersKonuEditor)
    def _wp_log(self):
        # LAZY LOAD
        from ui.whatsapp_logs import WhatsappLogRaporu
        self._show_dialog(WhatsappLogRaporu)
    def _ayarlar(self):    self._show_dialog(UygulamaAyarlar)


    def _performans_paneli(self):
        try:
            dlg = PerformansPaneli(self)
            dlg.setModal(True)
            # dlg.resize(840, 520) 
            dlg.showMaximized()
            dlg.exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            import traceback
    def _update_window_title(self):
        try:
            from utils.license_manager import manager
            lic_stat = manager.check_status()
            if lic_stat.get("is_license"):
                self.setWindowTitle("YKS/LGS Ödev & Takip Yöneticisi  [Lisanslı]")
            else:
                days_left = lic_stat.get("days_left", 0)
                self.setWindowTitle(f"YKS/LGS Ödev & Takip Yöneticisi  [14 Günlük Deneme Sürümü - {days_left} Gün Kaldı]")
        except Exception:
            self.setWindowTitle("YKS/LGS Ödev & Takip Yöneticisi")

    def _lisans_yonetimi_ac(self):
        from ui.license_dialog import LicenseDialog
        dlg = LicenseDialog(self, can_cancel=True)
        dlg.exec()
        self._update_window_title()

    # ---- Hakkında
    def _hakkinda(self):
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, QGridLayout)
        from PyQt6.QtCore import Qt, QUrl
        from PyQt6.QtGui import QFont, QCursor, QDesktopServices
        import sys, platform, sqlite3, os

        dlg = QDialog(self)
        dlg.setWindowTitle("Hakkında ve Sistem Tanısı")
        dlg.resize(580, 520)
        
        dlg.setStyleSheet("""
            QDialog { background-color: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif; }
            QFrame#HeaderBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #0f172a);
                border-radius: 12px;
                padding: 16px;
            }
            QLabel#AppTitle {
                font-size: 18px; font-weight: bold; color: #ffffff;
            }
            QLabel#AppVersion {
                font-size: 13px; color: #38bdf8; font-weight: 600;
            }
            QFrame#DiagCard {
                background-color: #ffffff;
                border-radius: 10px;
                border: 1px solid #e2e8f0;
                padding: 12px;
            }
            QFrame#DiagCard QLabel {
                background: transparent;
                border: none;
            }
            QLabel#DiagTitle {
                font-size: 12px; font-weight: bold; color: #475569; margin-bottom: 4px;
            }
            QLabel#DiagItem {
                font-size: 11px; color: #64748b;
            }
            QLabel#Info {
                font-size: 13px; color: #334155; line-height: 1.6;
            }
            QLabel#Footer {
                font-size: 11px; color: #94a3b8;
            }
            QPushButton#btnOk {
                background-color: #2563eb; color: white; border-radius: 6px;
                padding: 8px 24px; font-weight: 600; border: none; font-size: 13px;
            }
            QPushButton#btnOk:hover { background-color: #1d4ed8; }
            QPushButton#btnGithub {
                background-color: #ffffff; color: #334155; border-radius: 6px;
                border: 1px solid #cbd5e1; padding: 8px 16px; font-weight: 600; font-size: 13px;
            }
            QPushButton#btnGithub:hover { background-color: #f1f5f9; }
            a { color: #2563eb; text-decoration: none; font-weight: 600; }
            a:hover { text-decoration: underline; }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header Banner
        banner = QFrame()
        banner.setObjectName("HeaderBanner")
        b_lay = QVBoxLayout(banner)
        b_lay.setContentsMargins(12, 10, 12, 10)
        b_lay.setSpacing(4)
        
        t_lbl = QLabel("📚 YKS / LGS & KPSS Koçluk & Ödev Takip Yöneticisi")
        t_lbl.setObjectName("AppTitle")
        v_lbl = QLabel("Sürüm 3.5 Pro Ultra • Gelişmiş Deneme & Görev Ekosistemi")
        v_lbl.setObjectName("AppVersion")
        b_lay.addWidget(t_lbl)
        b_lay.addWidget(v_lbl)
        layout.addWidget(banner)

        # DB & System Diagnostics Stats
        try:
            con = db.get_conn()
            st_cnt = con.execute("SELECT COUNT(*) FROM ogrenci").fetchone()[0]
            hw_cnt = con.execute("SELECT COUNT(*) FROM odev").fetchone()[0]
            try:
                exam_cnt = con.execute("SELECT COUNT(*) FROM denemeler").fetchone()[0]
            except Exception:
                exam_cnt = 0
            con.close()
            db_path = self._aktif_db_path()
            db_sz = f"{os.path.getsize(db_path)/(1024*1024):.2f} MB" if db_path and os.path.exists(db_path) else "N/A"
        except Exception:
            st_cnt, hw_cnt, exam_cnt, db_sz = "N/A", "N/A", "N/A", "N/A"

        diag_card = QFrame()
        diag_card.setObjectName("DiagCard")
        d_lay = QGridLayout(diag_card)
        d_lay.setContentsMargins(10, 10, 10, 10)
        d_lay.setSpacing(8)

        lbl_dt = QLabel("🛠️ Sistem ve Çalışma Ortamı Bilgileri")
        lbl_dt.setObjectName("DiagTitle")
        d_lay.addWidget(lbl_dt, 0, 0, 1, 2)

        py_ver = sys.version.split()[0]
        os_info = f"{platform.system()} {platform.release()}"
        d_lay.addWidget(QLabel(f"<b>Python:</b> {py_ver}"), 1, 0)
        d_lay.addWidget(QLabel(f"<b>İşletim Sistemi:</b> {os_info}"), 1, 1)
        d_lay.addWidget(QLabel(f"<b>SQLite Motoru:</b> {sqlite3.sqlite_version}"), 2, 0)
        d_lay.addWidget(QLabel(f"<b>Veritabanı Boyutu:</b> {db_sz}"), 2, 1)
        d_lay.addWidget(QLabel(f"<b>👥 Aktif Öğrenciler:</b> {st_cnt}"), 3, 0)
        d_lay.addWidget(QLabel(f"<b>📋 Toplam Ödevler:</b> {hw_cnt}"), 3, 1)
        d_lay.addWidget(QLabel(f"<b>📝 Kayıtlı Denemeler:</b> {exam_cnt}"), 4, 0)
        d_lay.addWidget(QLabel(f"<b>🎨 Aktif Tema:</b> Canlı Dinamik"), 4, 1)

        layout.addWidget(diag_card)

        # Developer Contact Card
        contact_card = QFrame()
        contact_card.setObjectName("DiagCard")
        c_lay = QVBoxLayout(contact_card)
        c_lay.setContentsMargins(12, 10, 12, 10)
        c_lay.setSpacing(4)
        
        info_html = (
            "<p style='margin:2px 0;'><b>👨‍💻 Geliştirici:</b> Osman Kütükçü</p>"
            "<p style='margin:2px 0;'><b>📧 E-posta:</b> <a href='mailto:osmankutukcu@gmail.com'>osmankutukcu@gmail.com</a></p>"
            "<p style='margin:2px 0;'><b>📱 Telefon:</b> 0546 441 6905</p>"
            "<p style='margin:2px 0;'><b>🌐 GitHub:</b> <a href='https://github.com/osmankutukcu'>github.com/osmankutukcu</a></p>"
        )
        lbl_info = QLabel(info_html)
        lbl_info.setObjectName("Info")
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setOpenExternalLinks(True)
        c_lay.addWidget(lbl_info)
        layout.addWidget(contact_card)

        # Footer
        footer = QLabel("© 2025-2026 Osman Kütükçü. Tüm hakları saklıdır.<br>Özel ders ve koçluk merkezlerinde başarıyı maksimize etmek amacıyla geliştirilmiştir.")
        footer.setObjectName("Footer")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        layout.addWidget(footer)

        # Buton Alanı
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        
        btn_git = QPushButton("🌐 GitHub Sayfası")
        btn_git.setObjectName("btnGithub")
        btn_git.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_git.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/osmankutukcu")))
        btn_box.addWidget(btn_git)

        btn_ok = QPushButton("Kapat")
        btn_ok.setObjectName("btnOk")
        btn_ok.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_ok.clicked.connect(dlg.accept)
        btn_box.addWidget(btn_ok)
        btn_box.addStretch(1)
        
        layout.addLayout(btn_box)

        dlg.exec()

    # ---- Veritabanı işlemleri: Onar / Sıfırla
    def _onar_menu(self):
        self._db_araclari_dialog()

    def _onar(self):
        try:
            db.init_db()
            QMessageBox.information(self, "Tamam", "Veritabanı kontrol/onarım tamamlandı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _sifirla_db(self):
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
            QPushButton, QMessageBox, QFrame
        )
        from PyQt6.QtCore import Qt
        import shutil, datetime, os

        # Özel Güvenlikli Doğrulama Diyaloğu
        dlg = QDialog(self)
        dlg.setWindowTitle("⚠️ Veritabanını Sıfırla (Güvenlik Onayı)")
        dlg.resize(480, 260)
        dlg.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-family: 'Segoe UI', sans-serif; }
            QPushButton { font-family: 'Segoe UI', sans-serif; font-weight: 700; border-radius: 6px; }
        """)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        warn_card = QFrame()
        warn_card.setStyleSheet("background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 12px;")
        w_lay = QVBoxLayout(warn_card)
        w_lay.setSpacing(6)

        lbl_w1 = QLabel("⚠️ <b>DİKKAT: TÜM VERİLER SİLİNECEK!</b>")
        lbl_w1.setStyleSheet("color: #991b1b; font-size: 13px;")
        lbl_w2 = QLabel(
            "Bu işlem kayıtlı tüm öğrenci, ödev, deneme sınavı ve koçluk verilerini kalıcı olarak silecektir.\n"
            "İşlem öncesinde sisteminiz için <b>otomatik güvenlik yedeği</b> alınacaktır."
        )
        lbl_w2.setWordWrap(True)
        lbl_w2.setStyleSheet("color: #7f1d1d; font-size: 11.5px;")
        w_lay.addWidget(lbl_w1)
        w_lay.addWidget(lbl_w2)
        v.addWidget(warn_card)

        lbl_hint = QLabel(
            "İşlemi onaylamak için sıfırlama şifresini (<b>ok55..</b>) veya kutuya büyük harflerle <b>ONAYLIYORUM</b> yazınız:"
        )
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("font-size: 12px; color: #334155;")
        v.addWidget(lbl_hint)

        inp = QLineEdit()
        inp.setPlaceholderText("Şifreyi (ok55..) veya ONAYLIYORUM yazınız...")
        inp.setStyleSheet("padding: 8px 12px; border: 1.5px solid #cbd5e1; border-radius: 6px; font-size: 13px;")
        v.addWidget(inp)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet("background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; padding: 8px 16px;")
        btn_cancel.clicked.connect(dlg.reject)

        btn_confirm = QPushButton("🗑️ Veritabanını Sıfırla")
        btn_confirm.setStyleSheet("background: #dc2626; color: white; border: none; padding: 8px 18px;")

        btn_box.addStretch(1)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_confirm)
        v.addLayout(btn_box)

        def _do_reset():
            val = (inp.text() or "").strip()
            if val != "ok55.." and val.upper() != "ONAYLIYORUM":
                QMessageBox.warning(dlg, "Doğrulama Başarısız", "Girdiğiniz şifre veya onay kelimesi eşleşmedi. İşlem iptal edildi.")
                return

            p = self._aktif_db_path()
            if p and os.path.exists(p):
                bk_dir = os.path.join(os.path.dirname(p), "backups")
                os.makedirs(bk_dir, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safety_dst = os.path.join(bk_dir, f"pre_reset_safety_backup_{ts}.sqlite")
                try:
                    shutil.copy2(p, safety_dst)
                except Exception:
                    pass

            try:
                con = db.get_conn()
                cur = con.cursor()
                try: cur.execute("PRAGMA foreign_keys=OFF")
                except Exception: pass

                tables = [r[0] for r in cur.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()]
                for t in tables:
                    cur.execute(f"DELETE FROM {t}")

                try: cur.execute("DELETE FROM sqlite_sequence")
                except Exception: pass

                con.commit()
                try: cur.execute("PRAGMA foreign_keys=ON")
                except Exception: pass
                try: cur.execute("VACUUM")
                except Exception: pass

                # Müfredat ve varsayılan tabloları sıfırdan yeniden yükle (Fabrika Ayarları)
                try: db.init_db()
                except Exception: pass

                QMessageBox.information(
                    dlg, "Sıfırlandı",
                    "Veritabanındaki tüm veriler başarıyla silindi ve fabrika ayarlarına döndürüldü.\n\n"
                    "Güvenlik amacıyla işlem öncesi yedeğiniz 'backups' klasörüne otomatik kaydedilmiştir."
                )
                dlg.accept()
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Sıfırlama başarısız:\n{e}")

        btn_confirm.clicked.connect(_do_reset)
        dlg.exec()

    # ------------------ Ek rapor pencereleri ------------------
    def _rapor_trend(self):
        # LAZY LOAD
        from ui.rapor_trend import RaporTrend
        dlg = RaporTrend(self); dlg.exec()

    def _rapor_kok(self):
        # LAZY LOAD
        from ui.rapor_kok_neden import RaporKokNeden
        dlg = RaporKokNeden(self); dlg.exec()

    # ------------------ Hata günlüğü görüntüleyici ------------------
    def _hata_gunlugu(self):
        try:
            from ui import app_settings as appset
            import os
            d = appset.ayar_get('log_dir') or 'logs'
            os.makedirs(d, exist_ok=True)
            files = sorted([f for f in os.listdir(d) if f.endswith('.log')], reverse=True)[:50]

            dlg = QDialog(self); dlg.setWindowTitle('Hata Günlüğü'); dlg.resize(840, 600)
            v = QVBL2(dlg); lst = QListWidget(); txt = QTextEdit(); txt.setReadOnly(True)
            v.addWidget(lst); v.addWidget(txt)

            for f in files: lst.addItem(os.path.join(d, f))
            def _open():
                import codecs
                it = lst.currentItem(); p = it.text() if it else None
                if not p: return
                with codecs.open(p, 'r', 'utf-8', errors='ignore') as fh:
                    txt.setPlainText(fh.read())
            lst.itemSelectionChanged.connect(_open)
            dlg.exec()
        except Exception:
            pass

    # ------------------ Otomatik hatırlatıcı ------------------
    def _setup_auto_reminder(self):
        from ui import app_settings as appset
        try:
            enabled = (appset.ayar_get('timer_enabled', '1') == '1')
        except Exception:
            enabled = True
        if not enabled: return

        try:
            from utils.auto_reminder import send_for_due_tomorrow, send_for_overdue
        except Exception:
            return

        self._rem_timer = QTimer(self)
        interval_min = int(appset.ayar_get('timer_interval_min', '60'))
        self._rem_timer.setInterval(max(5, interval_min) * 60 * 1000)

        def tick():
            try:
                sablon = appset.ayar_get('hatirlatma_wp_sablon') or 'Merhaba: {ozet}'
                con = db.get_conn()
                ids = [r[0] for r in con.execute("SELECT id FROM ogrenci")]
                for oid in ids:
                    try:
                        send_for_due_tomorrow(oid, sablon)
                        send_for_overdue(oid, sablon)
                    except Exception:
                        pass
            except Exception:
                pass
        self._rem_timer.timeout.connect(tick)
        self._rem_timer.start()

    # ------------------ Ek modüller ------------------
    def _user_manager(self):
        try:
            from ui.user_manager import UserManagerDialog
            from PyQt6.QtWidgets import QDialog, QVBoxLayout
            
            # Manuel Wrapper Dialog (Sorunsuz açılış ve kapanış için)
            dlg_wrapper = QDialog(self)
            dlg_wrapper.setWindowTitle("Kullanıcı Yönetimi")
            
            # İstenen boyut
            dlg_wrapper.resize(950, 650)
            
            lay = QVBoxLayout(dlg_wrapper)
            lay.setContentsMargins(0, 0, 0, 0)
            
            # İçeriği ekle
            widget = UserManagerDialog(dlg_wrapper)
            lay.addWidget(widget)
            
            dlg_wrapper.exec()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _open_randevu_filter(self, mode):
        try:
            from ui.randevu_takvimi import RandevuTakvimi
            from PyQt6.QtCore import Qt
            dlg = RandevuTakvimi(self)
            
            if mode == 'today':
                # Combobox'ta 'Bugün' seçeneğini bul ve seç
                idx = dlg.cmbTarih.findText("Bugün", Qt.MatchFlag.MatchContains)
                if idx >= 0:
                    dlg.cmbTarih.setCurrentIndex(idx)
            
            elif mode == 'overdue':
                # 'Yalnız geciken' checkbox'ını işaretle
                dlg.chkYalnizGeciken.setChecked(True)
                
            dlg.setModal(True)
            dlg.showMaximized()
            dlg.exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Hata", f"Pencere açılamadı: {e}")

    def _hizli_gorusme(self):
        try:
            from quick_meet import RandevuTakvimi

        except ModuleNotFoundError:
            from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                         QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QMessageBox)
            from PyQt6.QtGui import QColor
            from PyQt6.QtCore import Qt, QDate
            import db

            class RandevuTakvimi(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Hızlı Görüşme / Randevu Takvimi")
                    self.resize(900, 560)
                    # self.setWindowState(Qt.WindowState.WindowMaximized)
                    lay = QVBoxLayout(self)

                    self.tab = QTableWidget(0, 3)
                    self.tab.setHorizontalHeaderLabels(["Öğrenci", "Bitiş Tarihi", "Küme ID"])
                    self.tab.horizontalHeader().setStretchLastSection(True)
                    self.tab.setSelectionBehavior(self.tab.SelectionBehavior.SelectRows)
                    lay.addWidget(self.tab, 1)

                    bar = QHBoxLayout()
                    self.cmbSablon = QComboBox(); self.cmbSablon.addItems(["Genel", "Geciken"])
                    self.chkGeciken = QCheckBox("Yalnız gecikenler")
                    self.btnBugun = QPushButton("Bugün Hatırlat")
                    self.btn24All = QPushButton("24 Saat Kala (Tümü)")
                    self.btn24Sel = QPushButton("24 Saat Kala (Seçili)")
                    bar.addWidget(QLabel("Şablon:")); bar.addWidget(self.cmbSablon)
                    bar.addWidget(self.chkGeciken); bar.addStretch(1)
                    bar.addWidget(self.btnBugun); bar.addWidget(self.btn24All); bar.addWidget(self.btn24Sel)
                    lay.addLayout(bar)

                    self.tab.cellDoubleClicked.connect(self._ac_kontrol)
                    self.btnBugun.clicked.connect(self._send_bugun)
                    self.btn24All.clicked.connect(self._send_24_all)
                    self.btn24Sel.clicked.connect(self._send_24_sel)

                    self._yukle()

                def _yukle(self):
                    con = db.get_conn()
                    rows = con.execute(
                        "SELECT k.id AS kume_id, COALESCE(k.bitis_tarihi,'') AS bitis, "
                        "       o.id AS ogr_id, o.ad, o.soyad "
                        "FROM odev_kume k JOIN ogrenci o ON o.id=k.ogrenci_id "
                        "ORDER BY bitis ASC, k.id ASC"
                    ).fetchall()
                    bugun = QDate.currentDate().toString('yyyy-MM-dd')
                    self.tab.setRowCount(0)
                    for r in rows:
                        if self.chkGeciken.isChecked() and (r["bitis"] or "") >= bugun:
                            continue
                        i = self.tab.rowCount(); self.tab.insertRow(i)
                        self.tab.setItem(i, 0, QTableWidgetItem(f"{r['ad']} {r['soyad']}"))
                        self.tab.setItem(i, 1, QTableWidgetItem(r["bitis"] or ""))
                        it = QTableWidgetItem(str(r["kume_id"]))
                        it.setData(Qt.ItemDataRole.UserRole, int(r["ogr_id"]))
                        self.tab.setItem(i, 2, it)
                        if (r["bitis"] or "") == bugun:
                            for c in range(3):
                                self.tab.item(i, c).setBackground(QColor(255, 204, 204))

                def _secili_ogr_idler(self):
                    ids = []
                    for idx in self.tab.selectionModel().selectedRows():
                        ogr_id = self.tab.item(idx.row(), 2).data(Qt.ItemDataRole.UserRole)
                        if ogr_id: ids.append(int(ogr_id))
                    return ids

                def _ac_kontrol(self, r, c):
                    try:
                        kume_id = int(self.tab.item(r, 2).text())
                        ogr_adsoyad = self.tab.item(r, 0).text()
                        from ui.odev_kontrol import OdevKontrolDialog
                        con = db.get_conn()
                        row = con.execute("SELECT ogrenci_id FROM odev_kume WHERE id=?", (kume_id,)).fetchone()
                        if not row: return
                        dlg = OdevKontrolDialog(int(row["ogrenci_id"]), self)
                        dlg.setWindowTitle(f"Ödev Kontrol - {ogr_adsoyad} (Küme #{kume_id})")
                        dlg.exec()
                        self._yukle()
                    except Exception:
                        pass

                def _sablonget(self, geciken=False):
                    try:
                        from utils import settings as appset
                        if geciken:
                            return appset.ayar_get("hatirlatma_wp_sablon_geciken", "Merhaba, geciken ödevleriniz var: {ozet}")
                        return appset.ayar_get("hatirlatma_wp_sablon", "Merhaba, yarın ödev kontrolünüz var: {ozet}")
                    except Exception:
                        return "Merhaba: {ozet}"

                def _send_bugun(self):
                    try:
                        from utils.auto_reminder import send_for_overdue
                    except Exception:
                        QMessageBox.information(self, "Bilgi", "Hatırlatma modülü yok (utils.auto_reminder)."); return
                    sablon = self._sablonget(geciken=(self.cmbSablon.currentText()=="Geciken"))
                    toplam = 0
                    for oid in (self._secili_ogr_idler() or []):
                        try: toplam += int(send_for_overdue(oid, sablon).get("sent", 0))
                        except Exception: pass
                    QMessageBox.information(self, "Bugün Hatırlat", f"Gönderilen: {toplam}")

                def _send_24_all(self):
                    try:
                        from utils.auto_reminder import send_for_due_tomorrow, send_for_overdue
                    except Exception:
                        QMessageBox.information(self, "Bilgi", "Hatırlatma modülü yok (utils.auto_reminder)."); return
                    sablon = self._sablonget(geciken=(self.cmbSablon.currentText()=="Geciken"))
                    ids = []
                    for r in range(self.tab.rowCount()):
                        oid = self.tab.item(r, 2).data(Qt.ItemDataRole.UserRole)
                        if oid: ids.append(int(oid))
                    toplam = 0
                    for oid in ids:
                        try:
                            if self.cmbSablon.currentText()=="Geciken":
                                toplam += int(send_for_overdue(oid, sablon).get("sent", 0))
                            else:
                                toplam += int(send_for_due_tomorrow(oid, sablon).get("sent", 0))
                        except Exception:
                            pass
                    QMessageBox.information(self, "24 Saat Kala", f"Gönderilen: {toplam}")

                def _send_24_sel(self):
                    try:
                        from utils.auto_reminder import send_for_due_tomorrow, send_for_overdue
                    except Exception:
                        QMessageBox.information(self, "Bilgi", "Hatırlatma modülü yok (utils.auto_reminder)."); return
                    sablon = self._sablonget(geciken=(self.cmbSablon.currentText()=="Geciken"))
                    toplam = 0
                    for oid in (self._secili_ogr_idler() or []):
                        try:
                            if self.cmbSablon.currentText()=="Geciken":
                                toplam += int(send_for_overdue(oid, sablon).get("sent", 0))
                            else:
                                toplam += int(send_for_due_tomorrow(oid, sablon).get("sent", 0))
                        except Exception:
                            pass
                    QMessageBox.information(self, "24 Saat (Seçili)", f"Gönderilen: {toplam}")

        try:
            dlg = RandevuTakvimi(self)
            dlg.setModal(True)
            dlg.showMaximized()
            dlg.exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            import traceback
            QMessageBox.critical(self, "Hızlı Görüşme Hatası", f"{e}\n\n{traceback.format_exc()}")

    def _wp_hizli(self):
        try:
            from ui.whatsapp_quick import WhatsappHizliDialog
            dlg = WhatsappHizliDialog(self)
            dlg.setModal(True)
            # dlg.resize(740, 560)
            dlg.showMaximized()
            dlg.exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            import traceback
            QMessageBox.critical(self, "WhatsApp Hatası", f"{e}\n\n{traceback.format_exc()}")

    def _mail_gonder(self):
        try:
            from ui.mail_send import MailGonderDialog
        except ModuleNotFoundError:
            from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                                         QTextEdit, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
                                         QMessageBox)
            import urllib.parse, pyperclip, webbrowser

            class MailGonderDialog(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Mail Gönder")
                    # self.resize(700, 520)
                    self.setWindowState(Qt.WindowState.WindowMaximized)
                    v = QVBoxLayout(self)

                    row1 = QHBoxLayout(); row1.addWidget(QLabel("Alıcı(lar) (virgülle):")); self.txtTo = QLineEdit(); row1.addWidget(self.txtTo); v.addLayout(row1)
                    row2 = QHBoxLayout(); row2.addWidget(QLabel("Konu:")); self.txtSubject = QLineEdit(); row2.addWidget(self.txtSubject); v.addLayout(row2)

                    v.addWidget(QLabel("İleti:")); self.txtBody = QTextEdit(); v.addWidget(self.txtBody, 1)
                    v.addWidget(QLabel("Ekler (bilgi amaçlı – mailto ile otomatik eklenmez):"))
                    self.lstFiles = QListWidget(); v.addWidget(self.lstFiles, 1)
                    hb = QHBoxLayout(); btnAdd = QPushButton("Dosya Ekle"); btnDel = QPushButton("Seçili Eki Kaldır")
                    hb.addWidget(btnAdd); hb.addWidget(btnDel); hb.addStretch(1); v.addLayout(hb)

                    bottom = QHBoxLayout(); self.btnOpenClient = QPushButton("Varsayılan Mail Uygulamasında Aç")
                    self.btnCopy = QPushButton("İleti Metnini Panoya Kopyala"); self.btnClose = QPushButton("Kapat")
                    bottom.addStretch(1); bottom.addWidget(self.btnCopy); bottom.addWidget(self.btnOpenClient); bottom.addWidget(self.btnClose); v.addLayout(bottom)

                    btnAdd.clicked.connect(self._add_file); btnDel.clicked.connect(self._del_file)
                    self.btnOpenClient.clicked.connect(self._open_mail_app); self.btnCopy.clicked.connect(self._copy_body); self.btnClose.clicked.connect(self.accept)

                def _add_file(self):
                    fn, _ = QFileDialog.getOpenFileName(self, "Ek Seç", "", "Tüm Dosyalar (*.*)")
                    if fn: self.lstFiles.addItem(QListWidgetItem(fn))

                def _del_file(self):
                    it = self.lstFiles.currentItem()
                    if it: self.lstFiles.takeItem(self.lstFiles.row(it))

                def _copy_body(self):
                    pyperclip.copy(self.txtBody.toPlainText() or "")
                    QMessageBox.information(self, "Kopyalandı", "İleti panoya kopyalandı.")

                def _open_mail_app(self):
                    to = (self.txtTo.text() or "").replace(" ", "")
                    subject = urllib.parse.quote(self.txtSubject.text() or "")
                    body = urllib.parse.quote(self.txtBody.toPlainText() or "")
                    url = f"mailto:{to}?subject={subject}&body={body}"
                    try:
                        webbrowser.open(url)
                        QMessageBox.information(self, "Açıldı", "Varsayılan mail uygulaması açıldı.\nNot: Ekler otomatik eklenmez.")
                    except Exception as e:
                        QMessageBox.critical(self, "Hata", str(e))

        try:
            dlg = MailGonderDialog(self)
            dlg.setModal(True)
            dlg.exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            import traceback
            QMessageBox.critical(self, "Mail Hatası", f"{e}\n\n{traceback.format_exc()}")

    def _tema_degistir(self):
        try:
            from ui.theme_selector_dialog import ThemeSelectorDialog
            dlg = ThemeSelectorDialog(self)
            dlg.exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            import traceback
            QMessageBox.critical(self, "Tema Seçici Hatası", f"Tema seçici açılamadı:\n{e}\n\n{traceback.format_exc()}")

    # --veritabanı işlemleri yedek (mevcut kod)
    def _aktif_db_path(self) -> str:
        try:
            con = db.get_conn()
            row = con.execute("PRAGMA database_list").fetchone()
            return (row[2] or "").strip()
        except Exception:
            return ""

    def _db_info_text(self) -> str:
        import os, datetime
        p = self._aktif_db_path()
        if not p or not os.path.exists(p):
            return "Aktif veritabanı: (bulunamadı)"
        size_mb = os.path.getsize(p) / (1024 * 1024)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
        return f"Aktif veritabanı:\n{p}\nBoyut: {size_mb:.2f} MB   •   Güncellendi: {mtime}"

    def _db_araclari_dialog(self):
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
            QMessageBox, QFrame, QGroupBox, QGridLayout
        )
        from PyQt6.QtCore import QUrl, Qt
        from PyQt6.QtGui import QDesktopServices, QFont, QCursor
        import os, shutil, datetime

        dlg = QDialog(self)
        dlg.setWindowTitle("🛠️ Veritabanı Bakım ve Tanı Merkezi")
        dlg.resize(760, 560)
        
        dlg.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                margin-top: 14px;
                background-color: #ffffff;
                color: #1e293b;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #3b82f6;
            }
            QLabel#InfoLabel {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 14px;
                color: #334155;
                font-size: 12px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 600;
                padding: 7px 14px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton#Primary {
                background-color: #2563eb;
                border: 1px solid #1d4ed8;
                color: #ffffff;
            }
            QPushButton#Primary:hover { background-color: #1d4ed8; }
            QPushButton#Success {
                background-color: #10b981;
                border: 1px solid #059669;
                color: #ffffff;
            }
            QPushButton#Success:hover { background-color: #059669; }
            QPushButton#Danger {
                background-color: #fef2f2;
                border: 1px solid #fecaca;
                color: #dc2626;
            }
            QPushButton#Danger:hover {
                background-color: #fee2e2;
                border-color: #f87171;
            }
            QPushButton#Close {
                background-color: #e2e8f0;
                border: none;
                color: #334155;
            }
            QPushButton#Close:hover { background-color: #cbd5e1; }
        """)

        v = QVBoxLayout(dlg)
        v.setSpacing(12)
        v.setContentsMargins(18, 16, 18, 16)

        # 1. CANLI KPI İSTATİSTİK ŞERİDİ
        try:
            con = db.get_conn()
            n_ogr = con.execute("SELECT COUNT(*) FROM ogrenci").fetchone()[0]
            n_odev = con.execute("SELECT COUNT(*) FROM odev").fetchone()[0]
            n_deneme = con.execute("SELECT COUNT(*) FROM denemeler").fetchone()[0]
            con.close()
        except Exception:
            n_ogr, n_odev, n_deneme = 0, 0, 0

        p = self._aktif_db_path()
        size_mb = (os.path.getsize(p) / (1024 * 1024)) if p and os.path.exists(p) else 0.0

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        def make_kpi(icon, title, val):
            card = QFrame()
            card.setStyleSheet("background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px;")
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(8, 6, 8, 6)
            c_lay.setSpacing(2)
            lbl_t = QLabel(f"{icon} {title}")
            lbl_t.setStyleSheet("font-size: 10.5px; color: #64748b; font-weight: 600;")
            lbl_v = QLabel(str(val))
            lbl_v.setStyleSheet("font-size: 15px; color: #1e293b; font-weight: 800;")
            c_lay.addWidget(lbl_t)
            c_lay.addWidget(lbl_v)
            return card

        kpi_row.addWidget(make_kpi("👥", "Kayıtlı Öğrenci", n_ogr))
        kpi_row.addWidget(make_kpi("📋", "Toplam Ödev", n_odev))
        kpi_row.addWidget(make_kpi("📝", "Deneme Sınavı", n_deneme))
        kpi_row.addWidget(make_kpi("💾", "DB Dosya Boyutu", f"{size_mb:.2f} MB"))
        v.addLayout(kpi_row)

        # Bilgi Etiketi
        lbl_info = QLabel(self._db_info_text())
        lbl_info.setObjectName("InfoLabel")
        lbl_info.setWordWrap(True)
        v.addWidget(lbl_info)

        # 1. Grup: Sağlık, Onarım & Optimizasyon
        grp_bakim = QGroupBox("🔍 Sağlık, Onarım ve Optimizasyon")
        grid1 = QGridLayout(grp_bakim)
        grid1.setSpacing(10)
        grid1.setContentsMargins(14, 18, 14, 14)

        btn_onar = QPushButton("🛠️ Tabloları Onar / Kontrol Et")
        btn_onar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        btn_check = QPushButton("🔍 Bütünlük Kontrolü (Integrity)")
        btn_check.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        btn_optimize = QPushButton("⚡ Veritabanını Optimize Et (VACUUM)")
        btn_optimize.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        btn_sifirla = QPushButton("⚠️ Sıfırla (Fabrika Ayarlarına Dön)")
        btn_sifirla.setObjectName("Danger")
        btn_sifirla.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        grid1.addWidget(btn_onar, 0, 0)
        grid1.addWidget(btn_check, 0, 1)
        grid1.addWidget(btn_optimize, 1, 0)
        grid1.addWidget(btn_sifirla, 1, 1)
        v.addWidget(grp_bakim)

        # 2. Grup: Yedekleme İşlemleri
        grp_yedek = QGroupBox("💾 Yedekleme ve Kurtarma İşlemleri")
        row2 = QHBoxLayout(grp_yedek)
        row2.setSpacing(10)
        row2.setContentsMargins(14, 18, 14, 14)

        btn_yedek = QPushButton("💾 Güvenli Yedek Al")
        btn_yedek.setObjectName("Primary")
        btn_yedek.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        btn_don = QPushButton("♻️ Yedekten Geri Yükle")
        btn_don.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        row2.addWidget(btn_yedek)
        row2.addWidget(btn_don)
        v.addWidget(grp_yedek)

        # 3. Grup: Konumlar
        grp_konum = QGroupBox("📂 Dosya ve Klasör Konumları")
        row3 = QHBoxLayout(grp_konum)
        row3.setSpacing(10)
        row3.setContentsMargins(14, 18, 14, 14)

        btn_ac = QPushButton("📂 Veritabanı Klasörünü Aç")
        btn_ac.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        btn_bkp = QPushButton("📂 Yedekler Klasörünü Aç")
        btn_bkp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        row3.addWidget(btn_ac)
        row3.addWidget(btn_bkp)
        v.addWidget(grp_konum)

        v.addStretch(1)

        # Kapat Butonu
        btn_kapat = QPushButton("Kapat")
        btn_kapat.setObjectName("Close")
        btn_kapat.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_kapat.setMinimumWidth(100)
        v.addWidget(btn_kapat, alignment=Qt.AlignmentFlag.AlignRight)

        def refresh():
            lbl_info.setText(self._db_info_text())

        def integrity_check():
            try:
                con = db.get_conn()
                res = con.execute("PRAGMA integrity_check").fetchall()
                fk = con.execute("PRAGMA foreign_key_check").fetchall()
                con.close()
                status = res[0][0] if res else "Bilinmiyor"
                if status == "ok" and not fk:
                    QMessageBox.information(
                        dlg, "Bütünlük Kontrolü",
                        "✅ <b>Veritabanı Bütünlüğü Kusursuz!</b>\n\n"
                        "Tüm tablolar, indeksler, veri sayfaları ve anahtar ilişkileri tam sağlıklı durumda."
                    )
                else:
                    QMessageBox.warning(dlg, "Bütünlük Uyarısı", f"Veritabanı kontrol sonucu:\n{status}\nForeign Key hataları: {len(fk)}")
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Kontrol yapılamadı:\n{e}")

        def optimize_db():
            try:
                con = db.get_conn()
                con.execute("PRAGMA optimize")
                con.execute("VACUUM")
                con.execute("ANALYZE")
                con.close()
                refresh()
                QMessageBox.information(
                    dlg, "Optimizasyon Tamamlandı",
                    "⚡ <b>Veritabanı Başarıyla Optimize Edildi!</b>\n\n"
                    "Gereksiz boş alanlar temizlendi, dosya boyutu küçültüldü ve sorgu indeksleri güncellendi."
                )
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Optimizasyon başarısız:\n{e}")

        def yedek_al():
            p_cur = self._aktif_db_path()
            if not p_cur or not os.path.exists(p_cur):
                QMessageBox.warning(dlg, "Bulunamadı", "Aktif veritabanı dosyası bulunamadı.")
                return
            bk_dir = os.path.join(os.path.dirname(p_cur), "backups")
            os.makedirs(bk_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = os.path.join(bk_dir, f"backup_{ts}.sqlite")
            try:
                shutil.copy2(p_cur, dst)
                QMessageBox.information(dlg, "Yedek Alındı", f"Yedek başarıyla oluşturuldu:\n\n📂 {dst}")
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Yedek alınamadı:\n{e}")

        def yedekten_don():
            p_cur = self._aktif_db_path()
            if not p_cur:
                QMessageBox.warning(dlg, "Bulunamadı", "Aktif veritabanı yolu çözülemedi.")
                return
            src, _ = QFileDialog.getOpenFileName(
                dlg, "Yedek Seç", os.path.dirname(p_cur), "SQLite (*.sqlite *.db);;Tüm Dosyalar (*.*)"
            )
            if not src:
                return
            if QMessageBox.question(
                    dlg, "Onay",
                    "Seçilen yedekten geri yüklenecek.\n\n⚠️ MEVCUT VERİLERİNİZİN ÜZERİNE YAZILACAKTIR.\n\nDevam edilsin mi?"
            ) != QMessageBox.StandardButton.Yes:
                return
            try:
                try:
                    con = db.get_conn()
                    con.commit()
                except Exception:
                    pass
                shutil.copy2(src, p_cur)
                QMessageBox.information(dlg, "Tamam", "Yedekten geri yükleme tamamlandı.\nLütfen değişikliklerin tam olarak yansıması için uygulamayı yeniden başlatın.")
                refresh()
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", f"Geri yükleme başarısız:\n{e}")

        def klasoru_ac():
            p_cur = self._aktif_db_path()
            if not p_cur:
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(p_cur)))

        def yedekler_klasoru_ac():
            p_cur = self._aktif_db_path()
            if not p_cur:
                QMessageBox.warning(dlg, "Bulunamadı", "Aktif veritabanı yolu çözülemedi.")
                return
            backups_dir = os.path.join(os.path.dirname(p_cur), "backups")
            try:
                os.makedirs(backups_dir, exist_ok=True)
            except Exception:
                pass
            QDesktopServices.openUrl(QUrl.fromLocalFile(backups_dir))

        btn_onar.clicked.connect(self._onar)
        btn_check.clicked.connect(integrity_check)
        btn_optimize.clicked.connect(optimize_db)
        btn_sifirla.clicked.connect(self._sifirla_db)
        btn_yedek.clicked.connect(yedek_al)
        btn_don.clicked.connect(yedekten_don)
        btn_ac.clicked.connect(klasoru_ac)
        btn_bkp.clicked.connect(yedekler_klasoru_ac)
        btn_kapat.clicked.connect(dlg.accept)
        dlg.exec()
    #s--
    # +++ EKLE +++
    def _pick_student(self):
        """
        Öğrenci seçim kaynağın yoksa mini seçim penceresi açar.
        Dönüş: (ogrenci_id:int, adsoyad:str) veya None
        """
        try:
            con = db.get_conn()
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT id, ad, soyad FROM ogrenci ORDER BY ad, soyad").fetchall()
            con.close()
        except Exception:
            rows = []

        if not rows:
            QMessageBox.warning(self, "Öğrenci Yok", "Kayıtlı öğrenci bulunamadı.")
            return None

        from PyQt6.QtWidgets import QInputDialog
        items = [f"{r['id']} • {r['ad']} {r['soyad']}" for r in rows]
        text, ok = QInputDialog.getItem(self, "Öğrenci Seç", "Öğrenci:", items, 0, False)
        if not ok or not text:
            return None
        sid = int(text.split("•", 1)[0].strip())
        adsoyad = text.split("•", 1)[1].strip()
        return sid, adsoyad

    def _user_manager(self):
        # LAZY LOAD
        from ui.user_manager import UserManagerDialog
        self._show_dialog(UserManagerDialog)

    def _deneme_ac(self):
        # LAZY LOAD
        from ui.trial_exam_manager import TrialExamManager
        self._show_dialog(TrialExamManager)

    def _open_exam_simulation(self):
        # LAZY LOAD
        from ui.exam_simulation import ExamSimulationDialog
        dlg = ExamSimulationDialog(self)
        dlg.showMaximized()
        dlg.exec()

    def _koc_ac(self):
        # LAZY LOAD
        from ui.coaching_manager import CoachingManager
        self._show_dialog(CoachingManager)

    def _ogrenci_detay(self):
        try:
            from ui.student_detail import OgrenciDetayDialog
            dlg = OgrenciDetayDialog(ogrenci_id=None, adsoyad="", parent=self)
            dlg.setModal(True)
            dlg.showMaximized()
            dlg.exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            import traceback
            QMessageBox.critical(self, "Öğrenci Detayı",
                                 f"Pencere açılamadı:\n{e}\n\n{traceback.format_exc()}")

    def _analiz_yenile(self):
        try:
            con = db.get_conn()
            con.row_factory = sqlite3.Row
            ae.rebuild_all(con)  # günlük + haftalık + kitap + cohort özetlerini tazeler
            con.commit()
            con.close()
            QMessageBox.information(self, "Tamam", "Analiz tabloları güncellendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Analiz güncelleme başarısız:\n{e}")

    # --- PDF RAPOR ---
    def _create_pdf_report(self):
        try:
            # 1. New Custom Dialog (Multi Select)
            from ui.student_selection_dialog import StudentSelectionDialog
            dlg = StudentSelectionDialog(self)
            if dlg.exec() != 1:
                return

            selected_list, auto_save, print_req = dlg.get_data()
            if not selected_list:
                return
            
            # --- BULK MODE if multiple students or forced auto-save ---
            is_bulk = len(selected_list) > 1
            
            if is_bulk and not auto_save and not print_req:
                 # If multi students selected but auto-save OFF, warn user
                 res = QMessageBox.question(self, "Toplu İşlem", 
                                            f"{len(selected_list)} öğrenci seçildi. Hepsi için dosya adı sormamak adına\n"
                                            "otomatik olarak 'Odev_Raporlari' klasörüne kaydedilsin mi?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                 if res == QMessageBox.StandardButton.Yes:
                     auto_save = True

            from utils.pdf_report import PDFReportGenerator
            gen = PDFReportGenerator()
            
            import os
            from pathlib import Path
            from PyQt6.QtWidgets import QProgressDialog, QFileDialog

            # Prepare Folder
            folder = Path.home() / "Desktop" / "Odev_Raporlari"
            if auto_save:
                folder.mkdir(exist_ok=True)

            # Progress Bar Setup
            prog = QProgressDialog("İşlem yapılıyor...", "İptal", 0, len(selected_list), self)
            prog.setWindowModality(Qt.WindowModality.WindowModal)
            prog.setMinimumDuration(0)
            
            success_count = 0
            fail_count = 0
            last_path = ""
            
            # --- HANDLING LOGIC ---
            # If print_req is active, we mostly likely skip PDF saving unless auto_save is ALSO 'Always on' or checked.
            # Logic: If 'Print' clicked, we assume direct print. user might want save too? 
            # The dialog separates "Save" (OK) vs "Print" (Yazdır). 
            # Let's assume Yazdır means ONLY print, unless auto-save checkbox was left on? 
            # Actually, let's allow both if logic permits, but typically 'Print' action is distinct.
            # But here `accept_print` sets print_requested=True and calls accept_selection.
            # So `auto_save` comes from the checkbox state.
            
            for i, (std_id, std_name) in enumerate(selected_list):
                if prog.wasCanceled():
                    break
                
                label_txt = f"İşleniyor ({i+1}/{len(selected_list)}): {std_name}"
                prog.setLabelText(label_txt)
                prog.setValue(i)
                QApplication.processEvents()

                # 1. Direct Print (If requested)
                if print_req:
                    if gen.print_student_report(std_id):
                        success_count += 1
                        # Wait a bit between print jobs to not flood spooler?
                        import time; time.sleep(0.5) 
                    else:
                        fail_count += 1
                    continue # Skip saving if print was the primary action?
                    # Or should we do both?
                    # If user clicks "Yazdır", they usually expect hard copy. Saving might be redundant or desired.
                    # Implementing: If Print is requested, DO NOT prompt for Save file, but DO respect Auto-Save checkbox if checked.
                
                # 2. File Save (If not printed OR if printed+auto-save)
                # If print_req is True, only save if auto_save is True. Don't popup manual save dialogs.
                if print_req and not auto_save:
                    continue

                path = ""
                if auto_save:
                    import datetime
                    date_str = datetime.date.today().strftime("%d-%m-%Y")
                    safe_name = std_name.replace("/", "-").replace("\\", "-").strip()
                    filename = f"{std_id} - {safe_name} - {date_str}.pdf"
                    path = str(folder / filename)
                else:
                    # Manual Save
                    safe_name = std_name.replace(" ", "_")
                    default_name = f"Rapor_{safe_name}.pdf"
                    path, _ = QFileDialog.getSaveFileName(self, "PDF Raporu Kaydet", default_name, "PDF Files (*.pdf)")
                    if not path: 
                        continue

                if gen.generate_student_report(std_id, path):
                    success_count += 1
                    last_path = path
                else:
                    fail_count += 1

            prog.setValue(len(selected_list))
            
            # Summary
            if len(selected_list) == 1:
                if success_count > 0:
                    if print_req:
                        # No popup for print success usually needed, system dialog handles it.
                        pass 
                    else:
                        QMessageBox.information(self, "Başarılı", f"Rapor oluşturuldu:\n{last_path}")
                        try:
                            import subprocess, platform
                            if platform.system() == 'Darwin': subprocess.call(('open', last_path))
                            elif platform.system() == 'Windows': os.startfile(last_path)
                        except: pass
                else:
                     QMessageBox.critical(self, "Hata", "İşlem başarısız.")
            else:
                msg = f"İşlem Tamamlandı.\n\nBaşarılı: {success_count}\nHatalı: {fail_count}"
                if auto_save and last_path:
                    msg += f"\n\nDosyalar burada: {folder}"
                QMessageBox.information(self, "Toplu İşlem", msg)
                if auto_save and last_path:
                    try:
                        import subprocess, platform
                        if platform.system() == 'Darwin': subprocess.call(('open', str(folder)))
                        elif platform.system() == 'Windows': os.startfile(str(folder))
                    except: pass

        except Exception as e:
             QMessageBox.critical(self, "Hata", str(e))

    def closeEvent(self, event):
        """Uygulama kapanırken otomatik yedekleme kontrolü"""
        try:
            from utils.backup_manager import BackupManager
            bm = BackupManager()
            if bm.is_auto_backup() and bm.get_backup_path():
                success, msg = bm.create_backup()
                if not success:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Yedekleme Uyarısı", f"Otomatik yedek alınamadı:\n{msg}")
        except Exception:
            pass
        super().closeEvent(event)
    #f--
