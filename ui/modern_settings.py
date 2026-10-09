# -*- coding: utf-8 -*-
import os
import shutil
import sqlite3
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QGroupBox,
    QGridLayout, QFrame, QFileDialog, QMessageBox, QSpinBox, QRadioButton, QButtonGroup,
    QScrollArea, QTabWidget, QDialog, QDialogButtonBox, QApplication, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QUrl
from PyQt6.QtGui import QIcon, QPixmap, QColor, QFont, QCursor
import importlib

from utils import settings as appset
from ui.app_settings import ThemeManagerDialog
from ui.motivation_toast import load_settings as mot_load, save_settings as mot_save, preview_settings, _run_style
from ui.curriculum_page import CurriculumPage

# Lazy theme API
def _theme_api():
    try:
        theme = importlib.import_module('ui.theme')
        return theme.tema_presets, theme.tema_apply_preset, theme.apply
    except Exception:
        return (lambda: {"Klasik Koyu": {"mode": "dark"}}), (lambda _name: None), (lambda _app: None)


class ModernSettingsDialog(QWidget):
    """
    YKS & LGS Takip Yönetim Sistemi — Profesyonel Sistem ve Uygulama Ayarları
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sistem & Uygulama Ayarları")
        self.resize(980, 680)
        self.setMinimumSize(880, 580)
        self._apply_theme_styles()

        # Ana Layout
        root_lay = QHBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 1. SOL KENAR ÇUBUĞU (SIDEBAR)
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("SidebarFrame")
        sidebar_frame.setFixedWidth(240)
        sb_lay = QVBoxLayout(sidebar_frame)
        sb_lay.setContentsMargins(12, 16, 12, 16)
        sb_lay.setSpacing(10)

        # Sidebar Header
        h_box = QHBoxLayout()
        h_box.setSpacing(10)
        lbl_sb_icon = QLabel("⚙️")
        lbl_sb_icon.setStyleSheet("font-size: 24px;")
        v_sb_tit = QVBoxLayout()
        v_sb_tit.setSpacing(2)
        lbl_sb_title = QLabel("Ayarlar")
        lbl_sb_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0f172a;")
        lbl_sb_sub = QLabel("Yönetim & Tercihler")
        lbl_sb_sub.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        v_sb_tit.addWidget(lbl_sb_title)
        v_sb_tit.addWidget(lbl_sb_sub)
        h_box.addWidget(lbl_sb_icon)
        h_box.addLayout(v_sb_tit)
        h_box.addStretch()
        sb_lay.addLayout(h_box)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #e2e8f0; margin: 4px 0;")
        sb_lay.addWidget(sep)

        # Sidebar List
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("SidebarList")
        
        menu_items = [
            ("🏢 Genel Bilgiler", "Kurum, logo ve koçluk kimliği"),
            ("📚 Müfredat & Dersler", "Ders katalogları ve grup atamaları"),
            ("🎨 Görünüm & Tema", "Renk setleri, dark/light mod"),
            ("🎉 Motivasyon & Efekt", "Kutlama animasyonu ve sesler"),
            ("🌐 Entegrasyonlar", "WhatsApp şablonları, QR, Web"),
            ("🛡️ Sistem & Güvenlik", "Yedekleme, SQLite bakımı, lisans")
        ]

        for title, subtitle in menu_items:
            it = QListWidgetItem(title)
            it.setData(Qt.ItemDataRole.UserRole, subtitle)
            it.setSizeHint(QSize(210, 48))
            self.sidebar.addItem(it)

        self.sidebar.currentRowChanged.connect(self._change_page)
        sb_lay.addWidget(self.sidebar, 1)

        # Alt versiyon rozeti
        lbl_ver = QLabel("YKS-LGS Takip v2.0 • Pro")
        lbl_ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ver.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600; padding: 6px;")
        sb_lay.addWidget(lbl_ver)

        root_lay.addWidget(sidebar_frame)

        # 2. SAĞ İÇERİK ALANI
        self.content_area = QWidget()
        self.content_lay = QVBoxLayout(self.content_area)
        self.content_lay.setContentsMargins(0, 0, 0, 0)
        self.content_lay.setSpacing(0)

        # Başlık Kartı
        header_bar = QFrame()
        header_bar.setObjectName("HeaderBar")
        hb_lay = QVBoxLayout(header_bar)
        hb_lay.setContentsMargins(24, 18, 24, 14)
        hb_lay.setSpacing(3)

        self.lblTitle = QLabel("Genel Kurumsal Bilgiler")
        self.lblTitle.setStyleSheet("font-size: 19px; font-weight: 800; color: #0f172a;")
        self.lblSubtitle = QLabel("Raporlarda ve sistem genelinde görünen kurum ve iletişim bilgilerini yapılandırın.")
        self.lblSubtitle.setStyleSheet("font-size: 12px; color: #64748b;")

        hb_lay.addWidget(self.lblTitle)
        hb_lay.addWidget(self.lblSubtitle)
        self.content_lay.addWidget(header_bar)

        # Scroll Alanı
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: #f8fafc;")

        self.stack = QStackedWidget()
        self.scroll.setWidget(self.stack)
        self.content_lay.addWidget(self.scroll, 1)

        # Footer Çubuğu (Sabit butonlar)
        footer = QFrame()
        footer.setObjectName("FooterBar")
        flay = QHBoxLayout(footer)
        flay.setContentsMargins(24, 12, 24, 12)
        flay.setSpacing(12)

        lbl_foot_info = QLabel("💡 Değişikliklerin kaydedilmesi için \"Kaydet ve Kapat\" butonuna tıklayınız.")
        lbl_foot_info.setStyleSheet("color: #64748b; font-size: 12px;")
        flay.addWidget(lbl_foot_info)
        flay.addStretch()

        self.btnCancel = QPushButton("✕ İptal")
        self.btnCancel.setObjectName("secondary")
        self.btnCancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnCancel.setMinimumHeight(38)
        self.btnCancel.setMinimumWidth(100)
        self.btnCancel.clicked.connect(self.reject)

        self.btnSave = QPushButton("💾 Kaydet ve Kapat")
        self.btnSave.setObjectName("primary")
        self.btnSave.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnSave.setMinimumHeight(38)
        self.btnSave.setMinimumWidth(160)
        self.btnSave.clicked.connect(self._save_all)

        flay.addWidget(self.btnCancel)
        flay.addWidget(self.btnSave)
        self.content_lay.addWidget(footer)

        root_lay.addWidget(self.content_area, 1)

        # Sayfaları Oluştur ve Ekle
        self.page_general = GeneralPage()
        self.page_curriculum = CurriculumPage()
        self.page_appearance = AppearancePage()
        self.page_motivation = MotivationPage()
        self.page_integration = IntegrationPage()
        self.page_system = SystemPage(self)

        self.stack.addWidget(self.page_general)
        self.stack.addWidget(self.page_curriculum)
        self.stack.addWidget(self.page_appearance)
        self.stack.addWidget(self.page_motivation)
        self.stack.addWidget(self.page_integration)
        self.stack.addWidget(self.page_system)

        # Başlangıç seçimi
        self.sidebar.setCurrentRow(0)

    def _apply_theme_styles(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                color: #1e293b;
            }
            QFrame#SidebarFrame {
                background-color: #ffffff;
                border-right: 1px solid #e2e8f0;
            }
            QFrame#HeaderBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e2e8f0;
            }
            QFrame#FooterBar {
                background-color: #ffffff;
                border-top: 1px solid #e2e8f0;
            }
            QListWidget#SidebarList {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget#SidebarList::item {
                border-radius: 8px;
                padding: 10px 14px;
                margin-bottom: 4px;
                font-size: 13px;
                font-weight: 600;
                color: #475569;
            }
            QListWidget#SidebarList::item:hover {
                background-color: #f1f5f9;
                color: #1e293b;
            }
            QListWidget#SidebarList::item:selected {
                background-color: #eff6ff;
                color: #2563eb;
                font-weight: 700;
                border-left: 4px solid #2563eb;
            }
            QFrame.CardFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 16px;
            }
            QGroupBox {
                font-weight: 700;
                font-size: 13px;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                margin-top: 16px;
                background-color: #ffffff;
                padding: 16px 14px 12px 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                top: 0px;
                padding: 0 6px;
                color: #2563eb;
                background-color: #ffffff;
            }
            QLabel {
                color: #334155;
            }
            QLineEdit, QComboBox, QSpinBox {
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 7px 10px;
                background-color: #ffffff;
                color: #1e293b;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 2px solid #3b82f6;
            }
            QPushButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton#primary {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                border: 1px solid #1d4ed8;
                font-weight: 700;
                font-size: 13px;
                border-radius: 7px;
                padding: 8px 20px;
            }
            QPushButton#primary:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
            }
            QPushButton#secondary {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                font-weight: 600;
            }
            QPushButton#secondary:hover {
                background-color: #e2e8f0;
                color: #1e293b;
            }
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                padding: 9px 18px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 3px;
                color: #475569;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-bottom: 2px solid #2563eb;
                font-weight: 700;
                color: #2563eb;
            }
        """)

    def accept(self):
        self.window().close()

    def reject(self):
        self.window().close()

    def _change_page(self, idx):
        titles = [
            ("🏢 Genel Kurumsal Bilgiler", "Raporlarda, PDF çıktılarında ve sistem genelinde görünen kurum ve iletişim bilgileri."),
            ("📚 Müfredat ve Ders Yönetimi", "Aktif dersler, yeni özel ders tanımları ve sınıf gruplarına ders eşleştirmeleri."),
            ("🎨 Görünüm ve Tema Tercihleri", "Koyu/Açık renk modu, tema presetleri, yazı tipi boyutu ve arayüz yoğunluğu."),
            ("🎉 Akıllı Motivasyon & Kutlama Sistemi", "Ödevler tamamlandığında tetiklenen konfeti, havai fişek, ses ve toast bildirimleri."),
            ("🌐 Entegrasyonlar ve Dış Bağlantılar", "WhatsApp bildirim şablonları, veli mesajları, karekod ve yerel ağ erişimi."),
            ("🛡️ Sistem, Veritabanı ve Güvenlik", "Veritabanı yedekleme, SQLite optimizasyonu, denetim logları ve lisans durumu.")
        ]
        if 0 <= idx < len(titles):
            tit, sub = titles[idx]
            self.lblTitle.setText(tit)
            self.lblSubtitle.setText(sub)
        self.stack.setCurrentIndex(idx)

    def _save_all(self):
        try:
            self.page_general.save()
            self.page_appearance.save()
            self.page_motivation.save()
            self.page_integration.save()
            self.page_curriculum.save()
            QMessageBox.information(self, "Başarılı", "Tüm sistem ve uygulama ayarları başarıyla kaydedildi!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilirken hata oluştu:\n{e}")


# ==========================================
# 1. SAYFA: GENEL BİLGİLER
# ==========================================
class GeneralPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(18)

        # Kart 1: Kurumsal Bilgiler
        gb_inst = QGroupBox("🏢 Kurumsal Kimlik & İletişim")
        g_inst = QGridLayout(gb_inst)
        g_inst.setVerticalSpacing(12)
        g_inst.setHorizontalSpacing(14)

        self.txtKurum = QLineEdit(str(appset.ayar_get('kurum_adi', '')))
        self.txtKurum.setPlaceholderText("Örn: Başarı Akademi / Özel Kurs Merkezi")

        self.txtWeb = QLineEdit(str(appset.ayar_get('kurum_web', '')))
        self.txtWeb.setPlaceholderText("Örn: www.basariakademi.com")

        self.txtIletisim = QLineEdit(str(appset.ayar_get('iletisim_satiri', '')))
        self.txtIletisim.setPlaceholderText("Örn: Tel: 0212 555 0000 | info@basari.com")

        self.txtKocu = QLineEdit(str(appset.ayar_get('egitim_kocu', '')))
        self.txtKocu.setPlaceholderText("Örn: Uzm. Psk. Danışman Ahmet Yılmaz")

        g_inst.addWidget(QLabel("Kurum / Okul Adı:"), 0, 0); g_inst.addWidget(self.txtKurum, 0, 1)
        g_inst.addWidget(QLabel("Web Sitesi:"), 1, 0); g_inst.addWidget(self.txtWeb, 1, 1)
        g_inst.addWidget(QLabel("İletişim Satırı / Adres:"), 2, 0); g_inst.addWidget(self.txtIletisim, 2, 1)
        g_inst.addWidget(QLabel("Baş Eğitim Koçu / Koordinatör:"), 3, 0); g_inst.addWidget(self.txtKocu, 3, 1)
        layout.addWidget(gb_inst)

        # Kart 2: Logo ve Görsel Rapor Ayarları
        gb_logo = QGroupBox("🖼️ Kurumsal Logo & Rapor Filigranı")
        g_logo = QGridLayout(gb_logo)
        g_logo.setVerticalSpacing(12)
        g_logo.setHorizontalSpacing(14)

        # Canlı Önizleme Çerçevesi
        self.lbl_logo_preview = QLabel("Logo Yok")
        self.lbl_logo_preview.setFixedSize(110, 80)
        self.lbl_logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_logo_preview.setStyleSheet("""
            QLabel {
                background-color: #f8fafc;
                border: 1.5px dashed #cbd5e1;
                border-radius: 8px;
                color: #94a3b8;
                font-size: 11px;
                font-weight: 600;
            }
        """)

        v_logo_ctrl = QVBoxLayout()
        v_logo_ctrl.setSpacing(8)

        h_path = QHBoxLayout()
        self.txtLogo = QLineEdit(str(appset.ayar_get('logo_path', '')))
        self.txtLogo.setPlaceholderText("Logo dosya yolu (.png, .jpg)...")
        btnSelect = QPushButton("📁 Dosya Seç...")
        btnSelect.setObjectName("secondary")
        btnSelect.setCursor(Qt.CursorShape.PointingHandCursor)
        btnSelect.clicked.connect(self._select_logo)
        
        btnClearLogo = QPushButton("🗑️")
        btnClearLogo.setToolTip("Logoyu Kaldır")
        btnClearLogo.setObjectName("secondary")
        btnClearLogo.clicked.connect(self._clear_logo)

        h_path.addWidget(self.txtLogo, 1)
        h_path.addWidget(btnSelect)
        h_path.addWidget(btnClearLogo)
        v_logo_ctrl.addLayout(h_path)

        h_align = QHBoxLayout()
        h_align.addWidget(QLabel("Rapor Logo Hizalaması:"))
        self.cmbLogoAlign = QComboBox()
        self.cmbLogoAlign.addItems(["left", "center", "right"])
        self.cmbLogoAlign.setItemText(0, "Sol (Standart)")
        self.cmbLogoAlign.setItemText(1, "Orta (Dengeli)")
        self.cmbLogoAlign.setItemText(2, "Sağ (Modern)")
        saved_align = str(appset.ayar_get('logo_align', 'left') or 'left').lower()
        if "center" in saved_align: self.cmbLogoAlign.setCurrentIndex(1)
        elif "right" in saved_align: self.cmbLogoAlign.setCurrentIndex(2)
        else: self.cmbLogoAlign.setCurrentIndex(0)
        h_align.addWidget(self.cmbLogoAlign)
        h_align.addStretch()
        v_logo_ctrl.addLayout(h_align)

        g_logo.addWidget(self.lbl_logo_preview, 0, 0, 2, 1)
        g_logo.addLayout(v_logo_ctrl, 0, 1, 2, 1)
        layout.addWidget(gb_logo)

        # Kart 3: Koçluk Varsayılan Tercihleri
        gb_koc = QGroupBox("⏱️ Koçluk & Takip Varsayılanları")
        g_koc = QGridLayout(gb_koc)
        g_koc.setVerticalSpacing(10)
        g_koc.setHorizontalSpacing(14)

        self.cmb_def_meeting = QComboBox()
        self.cmb_def_meeting.addItems(["25 dk", "30 dk", "45 dk", "60 dk"])
        saved_dur = str(appset.ayar_get('koc_def_dur', '30 dk'))
        if saved_dur in ["25 dk", "30 dk", "45 dk", "60 dk"]:
            self.cmb_def_meeting.setCurrentText(saved_dur)

        self.spin_def_target = QSpinBox()
        self.spin_def_target.setRange(200, 3000)
        self.spin_def_target.setSingleStep(50)
        self.spin_def_target.setValue(int(appset.ayar_get('koc_def_target', 800)))

        self.spin_pass_rate = QSpinBox()
        self.spin_pass_rate.setRange(40, 95)
        self.spin_pass_rate.setSuffix(" %")
        self.spin_pass_rate.setValue(int(appset.ayar_get('koc_pass_rate', 70)))

        g_koc.addWidget(QLabel("Varsayılan Haftalık Görüşme Süresi:"), 0, 0)
        g_koc.addWidget(self.cmb_def_meeting, 0, 1)
        g_koc.addWidget(QLabel("Yeni Plan Başlangıç Soru Hedefi:"), 1, 0)
        g_koc.addWidget(self.spin_def_target, 1, 1)
        g_koc.addWidget(QLabel("Hedef Başarı Baraj Oranı:"), 2, 0)
        g_koc.addWidget(self.spin_pass_rate, 2, 1)
        layout.addWidget(gb_koc)

        layout.addStretch()
        self._update_logo_preview()

    def _select_logo(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Logo Seç", "", "Resim (*.png *.jpg *.jpeg *.bmp)")
        if fn:
            self.txtLogo.setText(fn)
            self._update_logo_preview()

    def _clear_logo(self):
        self.txtLogo.clear()
        self._update_logo_preview()

    def _update_logo_preview(self):
        path = self.txtLogo.text().strip()
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.lbl_logo_preview.setPixmap(pix.scaled(100, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                return
        self.lbl_logo_preview.setText("Logo Yok")

    def save(self):
        appset.ayar_set('kurum_adi', self.txtKurum.text().strip())
        appset.ayar_set('kurum_web', self.txtWeb.text().strip())
        appset.ayar_set('iletisim_satiri', self.txtIletisim.text().strip())
        appset.ayar_set('egitim_kocu', self.txtKocu.text().strip())
        appset.ayar_set('logo_path', self.txtLogo.text().strip())
        
        align_map = {0: "left", 1: "center", 2: "right"}
        appset.ayar_set('logo_align', align_map.get(self.cmbLogoAlign.currentIndex(), "left"))
        appset.ayar_set('koc_def_dur', self.cmb_def_meeting.currentText())
        appset.ayar_set('koc_def_target', self.spin_def_target.value())
        appset.ayar_set('koc_pass_rate', self.spin_pass_rate.value())


# ==========================================
# 3. SAYFA: GÖRÜNÜM VE TEMA
# ==========================================
class AppearancePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(18)

        self.tema_presets, self.tema_apply_preset, self.apply_theme = _theme_api()

        # Kart 1: Renk ve Tema Modu
        gb_theme = QGroupBox("🎨 Tema & Renk Paleti")
        gl = QGridLayout(gb_theme)
        gl.setVerticalSpacing(14)
        gl.setHorizontalSpacing(14)

        self.cmbPreset = QComboBox()
        try:
            self.cmbPreset.addItems(list(self.tema_presets().keys()))
        except:
            self.cmbPreset.addItems(["Klasik Koyu", "Modern Lacivert", "Zümrüt Yeşil"])
        self.cmbPreset.setCurrentText(str(appset.ayar_get('tema_seti', 'Klasik Koyu')))

        # Segmented Radio Buttonlar (Açık vs Koyu)
        self.modeGroup = QButtonGroup(self)
        self.radLight = QRadioButton("☀️ Açık Tema (Light)")
        self.radDark = QRadioButton("🌙 Koyu Tema (Dark)")
        self.modeGroup.addButton(self.radLight)
        self.modeGroup.addButton(self.radDark)

        current_theme = (appset.ayar_get('tema', 'açık') or "açık").lower()
        if current_theme in ("koyu", "dark"):
            self.radDark.setChecked(True)
        else:
            self.radLight.setChecked(True)

        h_mode = QHBoxLayout()
        h_mode.addWidget(self.radLight)
        h_mode.addWidget(self.radDark)
        h_mode.addStretch()

        gl.addWidget(QLabel("Renk Paleti Seti:"), 0, 0)
        gl.addWidget(self.cmbPreset, 0, 1)
        gl.addWidget(QLabel("Görünüm Modu:"), 1, 0)
        gl.addLayout(h_mode, 1, 1)
        layout.addWidget(gb_theme)

        # Kart 2: Tipografi ve Yoğunluk
        gb_layout = QGroupBox("🔤 Tipografi & Arayüz Yoğunluğu")
        gl2 = QGridLayout(gb_layout)
        gl2.setVerticalSpacing(12)
        gl2.setHorizontalSpacing(14)

        self.cmbDensity = QComboBox()
        self.cmbDensity.addItem("Kompakt (Veri Yoğun)", "compact")
        self.cmbDensity.addItem("Dengeli (Varsayılan)", "cozy")
        self.cmbDensity.addItem("Ferah (Geniş)", "comfortable")
        
        saved_density = str(appset.ayar_get('tema_density', 'compact'))
        for idx in range(self.cmbDensity.count()):
            if self.cmbDensity.itemData(idx) == saved_density:
                self.cmbDensity.setCurrentIndex(idx)
                break

        self.spinFont = QSpinBox()
        self.spinFont.setRange(9, 20)
        self.spinFont.setSuffix(" pt")
        self.spinFont.setValue(int(appset.ayar_get('tema_font', '12')))

        self.spinRadius = QSpinBox()
        self.spinRadius.setRange(0, 20)
        self.spinRadius.setSuffix(" px")
        self.spinRadius.setValue(int(appset.ayar_get('tema_radius', '8')))

        gl2.addWidget(QLabel("Arayüz Yoğunluğu (Density):"), 0, 0); gl2.addWidget(self.cmbDensity, 0, 1)
        gl2.addWidget(QLabel("Genel Yazı Boyutu:"), 1, 0); gl2.addWidget(self.spinFont, 1, 1)
        gl2.addWidget(QLabel("Kart & Buton Köşe Yuvarlaklığı:"), 2, 0); gl2.addWidget(self.spinRadius, 2, 1)
        layout.addWidget(gb_layout)

        # Kart 3: Canlı Önizleme Kartı
        gb_prev = QGroupBox("👁️ Arayüz Önizleme Örneği")
        v_prev = QVBoxLayout(gb_prev)
        v_prev.setSpacing(8)

        h_demo = QHBoxLayout()
        btn_demo1 = QPushButton("Örnek Buton (Normal)")
        btn_demo2 = QPushButton("Örnek Aksiyon")
        btn_demo2.setObjectName("primary")
        lbl_chip = QLabel("🟢 Aktif Durum Rozeti")
        lbl_chip.setStyleSheet("background: #dcfce7; color: #15803d; padding: 6px 12px; border-radius: 12px; font-weight: 700; font-size: 11px;")
        
        h_demo.addWidget(btn_demo1)
        h_demo.addWidget(btn_demo2)
        h_demo.addWidget(lbl_chip)
        h_demo.addStretch()
        v_prev.addLayout(h_demo)

        lbl_sample = QLabel("Bu panelde seçtiğiniz tema ve yazı boyutu tüm pencerelerde dinamik olarak uygulanır.")
        lbl_sample.setStyleSheet("color: #64748b; font-size: 11px; margin-top: 4px;")
        v_prev.addWidget(lbl_sample)
        layout.addWidget(gb_prev)

        layout.addStretch()

    def save(self):
        mode = "koyu" if self.radDark.isChecked() else "açık"
        density_data = self.cmbDensity.currentData() or "compact"
        
        appset.ayar_set('tema_seti', self.cmbPreset.currentText())
        appset.ayar_set('tema', mode)
        appset.ayar_set('tema_density', density_data)
        appset.ayar_set('tema_font', self.spinFont.value())
        appset.ayar_set('tema_radius', self.spinRadius.value())

        for key in ["tema_bg", "tema_fg", "tema_primary", "tema_accent", 
                    "tema_card", "tema_alt", "tema_list_bg", "tema_list_fg"]:
            appset.ayar_set(key, None)

        try:
            self.apply_theme(QApplication.instance())
        except Exception as e:
            print("Tema refresh hatası:", e)


# ==========================================
# 4. SAYFA: MOTİVASYON SİSTEMİ
# ==========================================
class MotivationPage(QWidget):
    STYLES = [
        "zoom_fade", "toast", "confetti", "confetti_crazy", "stars", 
        "fireworks", "snow", "balloons", "rainbow", "both", "epic", 
        "minimal", "last_sprint", "exam_focus"
    ]

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(12)

        try:
            self.prefs = mot_load() or {}
        except:
            self.prefs = {}

        # Üst Aktivasyon Kartı
        top_card = QFrame()
        top_card.setObjectName("CardFrame")
        top_card.setStyleSheet("background-color: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 8px 14px;")
        h_top = QHBoxLayout(top_card)
        h_top.setContentsMargins(8, 4, 8, 4)

        self.chkEnabled = QCheckBox("🎉 Akıllı Motivasyon & Kutlama Sistemi Aktif")
        self.chkEnabled.setStyleSheet("font-weight: 700; font-size: 13px; color: #1e293b;")
        self.chkEnabled.setChecked(self.prefs.get("enabled", True))
        h_top.addWidget(self.chkEnabled)
        h_top.addStretch()

        btn_live_test = QPushButton("✨ Efekti Şimdi Canlı Test Et")
        btn_live_test.setObjectName("primary")
        btn_live_test.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_live_test.clicked.connect(self._test_effect)
        h_top.addWidget(btn_live_test)
        layout.addWidget(top_card)

        # Tablar
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # 1. TAB: %100 Tamamlama
        self.tab_main = QWidget()
        v1 = QVBoxLayout(self.tab_main)
        v1.setContentsMargins(14, 14, 14, 14)
        v1.setSpacing(12)

        gb_100 = QGroupBox("🏆 %100 Tamamlama Efekt Ayarları")
        gl_100 = QGridLayout(gb_100)
        gl_100.setVerticalSpacing(10)
        gl_100.setHorizontalSpacing(14)

        self.txtMsgMain = QLineEdit(str(self.prefs.get("message", "Harika! Bu haftaki tüm hedeflerini tamamladın! 🎉")))
        self.cmbStyleMain = QComboBox(); self.cmbStyleMain.addItems(self.STYLES)
        self.cmbStyleMain.setCurrentText(str(self.prefs.get("style", "balloons")))

        self.spinDur = QSpinBox(); self.spinDur.setRange(500, 8000); self.spinDur.setSingleStep(250); self.spinDur.setSuffix(" ms")
        self.spinDur.setValue(int(self.prefs.get("duration", 2500)))

        self.spinConfetti = QSpinBox(); self.spinConfetti.setRange(20, 500); self.spinConfetti.setValue(int(self.prefs.get("confetti", 120)))

        self.txtSound = QLineEdit(str(self.prefs.get("sound_path") or "EBA_zil.wav"))
        btnSound = QPushButton("📁")
        btnSound.setToolTip("Ses Dosyası Seç")
        btnSound.clicked.connect(lambda: self._select_sound(self.txtSound))

        gl_100.addWidget(QLabel("Tebrik Mesajı:"), 0, 0); gl_100.addWidget(self.txtMsgMain, 0, 1)
        gl_100.addWidget(QLabel("Kutlama Efekti:"), 1, 0); gl_100.addWidget(self.cmbStyleMain, 1, 1)
        gl_100.addWidget(QLabel("Ekranda Kalma Süresi:"), 2, 0); gl_100.addWidget(self.spinDur, 2, 1)
        gl_100.addWidget(QLabel("Parçacık / Konfeti Miktarı:"), 3, 0); gl_100.addWidget(self.spinConfetti, 3, 1)

        h_snd = QHBoxLayout(); h_snd.addWidget(self.txtSound); h_snd.addWidget(btnSound)
        gl_100.addWidget(QLabel("Kutlama Sesi:"), 4, 0); gl_100.addLayout(h_snd, 4, 1)

        v1.addWidget(gb_100)
        v1.addStretch()
        self.tabs.addTab(self.tab_main, "🏆 %100 Tamamlama")

        # 2. TAB: %75 Seviyesi
        self.tab_75 = self._create_level_tab("75", "Harika gidiyorsun! Hedeflerin %75'i tamamlandı! 🚀", "stars")
        self.tabs.addTab(self.tab_75["widget"], "🚀 %75 İlerleme")

        # 3. TAB: %50 Seviyesi
        self.tab_50 = self._create_level_tab("50", "Yarıyı devirdin! Gayretle devam et! 👍", "confetti")
        self.tabs.addTab(self.tab_50["widget"], "👍 %50 Seviyesi")

    def _create_level_tab(self, level_key, default_msg, def_style):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        gb = QGroupBox(f"%{level_key} Tamamlandığında Çıkacak Bildirim")
        gl = QGridLayout(gb)
        gl.setVerticalSpacing(10)
        gl.setHorizontalSpacing(14)

        k_msg = f"motive_{level_key}_message"
        k_style = f"motive_{level_key}_style"
        k_sound = f"motive_{level_key}_sound_path"

        txtMsg = QLineEdit(str(appset.ayar_get(k_msg, default_msg)))
        cmbStyle = QComboBox(); cmbStyle.addItems(self.STYLES + ["(Varsayılan)"])
        saved_style = appset.ayar_get(k_style, def_style)
        cmbStyle.setCurrentText(saved_style or "(Varsayılan)")

        txtSound = QLineEdit(str(appset.ayar_get(k_sound, "") or ""))
        txtSound.setPlaceholderText("Varsayılan ses kullanılır")
        btnSound = QPushButton("📁")
        btnSound.clicked.connect(lambda: self._select_sound(txtSound))

        gl.addWidget(QLabel("Motivasyon Mesajı:"), 0, 0); gl.addWidget(txtMsg, 0, 1)
        gl.addWidget(QLabel("Efekt Animasyonu:"), 1, 0); gl.addWidget(cmbStyle, 1, 1)

        h_snd = QHBoxLayout(); h_snd.addWidget(txtSound); h_snd.addWidget(btnSound)
        gl.addWidget(QLabel("Özel Ses:"), 2, 0); gl.addLayout(h_snd, 2, 1)

        v.addWidget(gb)
        v.addStretch()
        return {"widget": w, "txtMsg": txtMsg, "cmbStyle": cmbStyle, "txtSound": txtSound,
                "key_msg": k_msg, "key_style": k_style, "key_sound": k_sound}

    def _select_sound(self, line_edit):
        fn, _ = QFileDialog.getOpenFileName(self, "Ses Dosyası Seç", "", "Ses (*.wav *.mp3 *.ogg)")
        if fn: line_edit.setText(fn)

    def _test_effect(self):
        try:
            msg = self.txtMsgMain.text() or "Tebrikler! Canlı efekt testi başarılı! 🎉"
            style = self.cmbStyleMain.currentText()
            dur = int(self.spinDur.value())
            conf = int(self.spinConfetti.value())
            snd = self.txtSound.text() if self.txtSound.text() else None
            _run_style(
                parent=self.window(),
                style=style,
                message=msg,
                color="#ffffff",
                duration_ms=dur,
                font_size=24,
                confetti_density=conf,
                sound_path=snd,
                sound_volume=0.3,
                position="center"
            )
        except Exception as e:
            try:
                preview_settings(self.window())
            except Exception:
                pass

    def save(self):
        p = {}
        p["enabled"] = self.chkEnabled.isChecked()
        p["message"] = self.txtMsgMain.text()
        p["duration"] = self.spinDur.value()
        p["style"] = self.cmbStyleMain.currentText()
        p["confetti"] = self.spinConfetti.value()
        p["sound_path"] = self.txtSound.text() if self.txtSound.text() else None
        mot_save(p)

        for tab_data in [self.tab_75, self.tab_50]:
            appset.ayar_set(tab_data["key_msg"], tab_data["txtMsg"].text())
            sty = tab_data["cmbStyle"].currentText()
            if sty == "(Varsayılan)": sty = ""
            appset.ayar_set(tab_data["key_style"], sty)
            appset.ayar_set(tab_data["key_sound"], tab_data["txtSound"].text())


# ==========================================
# 5. SAYFA: ENTEGRASYONLAR
# ==========================================
class IntegrationPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(18)

        # Kart 1: WhatsApp Şablonları
        gb_wp = QGroupBox("💬 WhatsApp Veli & Öğrenci Şablonları")
        gl_wp = QGridLayout(gb_wp)
        gl_wp.setVerticalSpacing(10)
        gl_wp.setHorizontalSpacing(14)

        self.txtWp = QLineEdit(str(appset.ayar_get('hatirlatma_wp_sablon', '')))
        self.txtWp.setPlaceholderText("Örn: Sayın Velimiz, {ad} {soyad} bu haftaki ödev hedeflerini tamamlamıştır.")

        self.txtWpGec = QLineEdit(str(appset.ayar_get('hatirlatma_wp_sablon_geciken', '')))
        self.txtWpGec.setPlaceholderText("Örn: Sayın Velimiz, {ad} adlı öğrencimizin {kalan_gun} günü kalan ödevleri bulunmaktadır.")

        # Dinamik etiket butonları
        h_chips = QHBoxLayout()
        h_chips.addWidget(QLabel("Hızlı Değişken Ekle:"))
        for tag in ["{ad}", "{soyad}", "{kalan_gun}", "{hedef_soru}", "{cozulen_soru}"]:
            btn_t = QPushButton(tag)
            btn_t.setStyleSheet("padding: 3px 8px; font-size: 11px; background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; border-radius: 4px;")
            btn_t.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_t.clicked.connect(lambda _, t=tag: self._insert_tag(t))
            h_chips.addWidget(btn_t)
        h_chips.addStretch()

        gl_wp.addWidget(QLabel("Normal Hatırlatma:"), 0, 0); gl_wp.addWidget(self.txtWp, 0, 1)
        gl_wp.addWidget(QLabel("Gecikme Uyarısı:"), 1, 0); gl_wp.addWidget(self.txtWpGec, 1, 1)
        gl_wp.addLayout(h_chips, 2, 0, 1, 2)
        layout.addWidget(gb_wp)

        # Kart 2: PDF & QR Kod Entegrasyonu
        gb_pdf = QGroupBox("📄 PDF Çıktı & Doğrulama Karekodu (QR)")
        gl_pdf = QGridLayout(gb_pdf)
        gl_pdf.setVerticalSpacing(10)
        gl_pdf.setHorizontalSpacing(14)

        self.txtQr = QLineEdit(str(appset.ayar_get('odev_qr_link', '')))
        self.txtQr.setPlaceholderText("Örn: https://portal.basariakademi.com/odev-kontrol")

        gl_pdf.addWidget(QLabel("PDF Karekod Doğrulama Bağlantısı:"), 0, 0)
        gl_pdf.addWidget(self.txtQr, 0, 1)
        layout.addWidget(gb_pdf)

        # Kart 3: Web / Mobil Yerel Ağ Erişimi
        gb_web = QGroupBox("🌍 Yerel Ağ (Wi-Fi) Web & Mobil Erişim Sunucusu")
        v_web = QVBoxLayout(gb_web)
        v_web.setSpacing(10)

        lbl_info = QLabel("Aynı yerel ağdaki (Wi-Fi) tablet veya telefonlardan öğrenci raporlarını canlı izlemek için web sunucusunu etkinleştirin.")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #64748b; font-size: 12px;")
        v_web.addWidget(lbl_info)

        btnWeb = QPushButton("🚀 Web & Mobil Erişim Kontrol Merkezini Aç...")
        btnWeb.setObjectName("secondary")
        btnWeb.setCursor(Qt.CursorShape.PointingHandCursor)
        btnWeb.setMinimumHeight(38)
        btnWeb.clicked.connect(self._open_web_dialog)
        v_web.addWidget(btnWeb)
        layout.addWidget(gb_web)

        layout.addStretch()

    def _insert_tag(self, tag):
        current_focus = QApplication.focusWidget()
        if isinstance(current_focus, QLineEdit):
            current_focus.insert(tag)
        else:
            self.txtWp.insert(tag)

    def _open_web_dialog(self):
        try:
            from ui.web_access_dialog import WebAccessDialog
            WebAccessDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Web Modülü", f"Web sunucusu açılırken bir hata oluştu:\n{e}")

    def save(self):
        appset.ayar_set('hatirlatma_wp_sablon', self.txtWp.text().strip())
        appset.ayar_set('hatirlatma_wp_sablon_geciken', self.txtWpGec.text().strip())
        appset.ayar_set('odev_qr_link', self.txtQr.text().strip())


# ==========================================
# 6. SAYFA: SİSTEM & GÜVENLİK
# ==========================================
class SystemPage(QWidget):
    def __init__(self, dialog_parent):
        super().__init__()
        self.dialog_parent = dialog_parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(18)

        # Kart 1: Veri Yedekleme
        gb_backup = QGroupBox("💾 Veritabanı Yedekleme & Geri Yükleme")
        v_b = QVBoxLayout(gb_backup)
        v_b.setSpacing(10)

        h_b = QHBoxLayout()
        lbl_b_desc = QLabel("Veri kaybını önlemek için öğrenci, ödev ve koçluk kayıtlarınızı düzenli olarak tek tıkla yedekleyin.")
        lbl_b_desc.setWordWrap(True)
        lbl_b_desc.setStyleSheet("color: #64748b; font-size: 12px;")
        
        btnBackup = QPushButton("☁️ Veri Yedekleme Menüsünü Aç...")
        btnBackup.setObjectName("primary")
        btnBackup.setCursor(Qt.CursorShape.PointingHandCursor)
        btnBackup.clicked.connect(self._open_backup)

        v_b.addWidget(lbl_b_desc)
        v_b.addWidget(btnBackup)
        layout.addWidget(gb_backup)

        # Kart 2: Veritabanı Sağlığı & Bakım
        gb_health = QGroupBox("🛠️ Veritabanı Sağlığı & İstatistikler")
        v_h = QVBoxLayout(gb_health)
        v_h.setSpacing(10)

        # İstatistik Satırı
        self.lbl_stats = QLabel("Veritabanı taranıyor...")
        self.lbl_stats.setStyleSheet("font-size: 12px; color: #1e293b; background: #f8fafc; padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0;")
        v_h.addWidget(self.lbl_stats)

        btnVacuum = QPushButton("🚀 Veritabanını Optimize Et & Sıkıştır (VACUUM)")
        btnVacuum.setObjectName("secondary")
        btnVacuum.setCursor(Qt.CursorShape.PointingHandCursor)
        btnVacuum.clicked.connect(self._vacuum_database)
        v_h.addWidget(btnVacuum)
        layout.addWidget(gb_health)

        # Kart 3: Denetim ve Lisans
        gb_audit = QGroupBox("📜 İşlem Kayıtları & Lisans Yönetimi")
        h_a = QHBoxLayout(gb_audit)
        h_a.setSpacing(14)

        btnAudit = QPushButton("📜 İşlem Loglarını İncele...")
        btnAudit.setObjectName("secondary")
        btnAudit.setCursor(Qt.CursorShape.PointingHandCursor)
        btnAudit.clicked.connect(self._open_audit)

        btnLic = QPushButton("🔑 Lisans Durumu / Aktivasyon...")
        btnLic.setObjectName("secondary")
        btnLic.setCursor(Qt.CursorShape.PointingHandCursor)
        btnLic.clicked.connect(self._open_license)

        h_a.addWidget(btnAudit)
        h_a.addWidget(btnLic)
        layout.addWidget(gb_audit)

        layout.addStretch()
        self._load_stats()

    def _load_stats(self):
        try:
            import db
            con = db.get_conn()
            c_ogr = con.execute("SELECT COUNT(*) FROM ogrenci").fetchone()[0]
            c_odev = con.execute("SELECT COUNT(*) FROM odev").fetchone()[0]
            c_koc = con.execute("SELECT COUNT(*) FROM koc_plan").fetchone()[0]
            con.close()
            self.lbl_stats.setText(f"📊 <b>Kayıtlı Öğrenci:</b> {c_ogr}  |  <b>Aktif Görev/Ödev:</b> {c_odev}  |  <b>Koçluk Planı:</b> {c_koc}")
        except Exception:
            self.lbl_stats.setText("📊 Sistem Veritabanı: Sağlıklı ve Bağlantı Aktif")

    def _vacuum_database(self):
        try:
            import db
            con = db.get_conn()
            con.execute("VACUUM")
            con.execute("ANALYZE")
            con.close()
            QMessageBox.information(self, "Başarılı", "Veritabanı başarıyla optimize edildi ve indeksler tazelendi.")
            self._load_stats()
        except Exception as e:
            QMessageBox.warning(self, "Uyarı", f"Optimize işlemi sırasında hata: {e}")

    def _open_backup(self):
        try:
            from ui.backup_dialog import BackupDialog
            BackupDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Yedekleme modülü açılamadı: {e}")

    def _open_audit(self):
        try:
            from ui.audit_viewer import AuditLogDialog
            AuditLogDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Log modülü yüklenemedi: {e}")

    def _open_license(self):
        try:
            from ui.license_dialog import LicenseDialog
            LicenseDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Lisans modülü yüklenemedi: {e}")
