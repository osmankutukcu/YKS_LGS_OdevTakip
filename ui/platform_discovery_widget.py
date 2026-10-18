# -*- coding: utf-8 -*-
"""Platform Keşif & Pro Taktik Karuseli (Feature Discovery Showcase).

KoçPilot 360'ın derinliklerinde yer alan güçlü koçluk yeteneklerini (Mobil Senkronizasyon,
Konu Haritası, Pomodoro, Hedef Analizi, Veli WhatsApp Karnesi vb.) öğretmenlere
eğlenceli, dinamik ve görsel mikro kartlarla tanıtan interaktif vitrin.
"""
from __future__ import annotations

from typing import List, Dict, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget,
    QGraphicsDropShadowEffect
)

from ui.theme import register_theme_listener
from ui.theme_tokens_v37 import semantic_palette


# İleride yenilerini eklemek veya metinleri düzenlemek için modüler veri modeli:
DISCOVERY_CARDS: List[Dict[str, Any]] = [
    {
        "id": "mobile",
        "tag": "📱 MOBİL ÖZGÜRLÜK",
        "tag_fg": "#0369a1",
        "tag_bg": "#e0f2fe",
        "tag_border": "#bae6fd",
        "icon": "📲",
        "icon_grad": ("#0284c7", "#0369a1"),
        "title": "Masaya bağlı kalmadan sınıfta dolaşarak telefonla kontrol yapın!",
        "desc": "Mobil merkezden QR barkodu telefonunuza bir kez okutun; sınıfta sıralar arasında dolaşırken tüm ödevleri cep telefonunuzdan onaylayın.",
        "btn_text": "Mobil Bağlantıyı Aç →",
        "feature_key": "mobile",
    },
    {
        "id": "topic_map",
        "tag": "🗺️ BİLİŞSEL RÖNTGEN",
        "tag_fg": "#6d28d9",
        "tag_bg": "#ede9fe",
        "tag_border": "#ddd6fe",
        "icon": "🧠",
        "icon_grad": ("#7c3aed", "#5b21b6"),
        "title": "Öğrencinin neden net çıkaramadığını Konu Haritasında görün!",
        "desc": "Konu Haritası modülünü açarak öğrencinin hangi alt kazanımda tıkandığını renklerle inceleyin; eksik noktaya anında telafi ödevi atayın.",
        "btn_text": "Konu Haritasını İncele →",
        "feature_key": "topic_map",
    },
    {
        "id": "pomodoro",
        "tag": "🍅 ODAK & DİKKAT",
        "tag_fg": "#be123c",
        "tag_bg": "#ffe4e6",
        "tag_border": "#fecdd3",
        "icon": "⏳",
        "icon_grad": ("#e11d48", "#be123c"),
        "title": "Birebir görüşmelerde 25 dakikalık canlı Pomodoro seansı başlatın!",
        "desc": "Öğrencinin dikkat süresini ölçün, görüşme esnasında gerçek zamanlı soru çözüm temposunu tutarak odaklanma disiplini kazandırın.",
        "btn_text": "Odak Seansını Başlat →",
        "feature_key": "pomodoro",
    },
    {
        "id": "target",
        "tag": "🎯 HEDEF & MOTİVASYON",
        "tag_fg": "#047857",
        "tag_bg": "#d1fae5",
        "tag_border": "#a7f3d0",
        "icon": "🏆",
        "icon_grad": ("#059669", "#047857"),
        "title": "Öğrencinin hayalindeki üniversiteyi kazanma ihtimalini simüle edin!",
        "desc": "Akıllı Hedef Analizi'ne girip net artış senaryoları kurun; öğrenciye hangi dersten kaç net daha yaparsa kazanacağını canlı gösterin.",
        "btn_text": "Hedef Simülasyonuna Git →",
        "feature_key": "target",
    },
    {
        "id": "whatsapp",
        "tag": "💬 VELİ MEMNUNİYETİ",
        "tag_fg": "#15803d",
        "tag_bg": "#dcfce7",
        "tag_border": "#bbf7d0",
        "icon": "✨",
        "icon_grad": ("#16a34a", "#15803d"),
        "title": "Haftalık durumu tek tek velilere yazmakla vakit kaybetmeyin!",
        "desc": "Öğrencinin haftalık başarı grafiğini ve tamamlanan ödevlerini tek tıkla otomatik WhatsApp şablonuna döküp veliye anında iletin.",
        "btn_text": "Veli Mesajı Hazırla →",
        "feature_key": "whatsapp",
    },
    {
        "id": "simulation",
        "tag": "⏱️ SINAV PROVASI",
        "tag_fg": "#c2410c",
        "tag_bg": "#ffedd5",
        "tag_border": "#fed7aa",
        "icon": "📝",
        "icon_grad": ("#ea580c", "#c2410c"),
        "title": "Gerçek sınav stresini yenmek için Sınav Modu provası yapın!",
        "desc": "Geri sayımlı deneme sınavı kronometresi ile öğrenciye süre baskısı altında soru çözme ve optik kodlama alışkanlığı aşılayın.",
        "btn_text": "Sınav Moduna Geç →",
        "feature_key": "simulation",
    },
]


class PlatformDiscoveryWidget(QFrame):
    """
    Dashboard'un altında yer alan interaktif 'Platform Keşif & Pro Taktik' vitrini.
    Otomatik döner, duraklatılabilir, tek tıkla ilgili özelliği açar.
    """
    sig_action_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlatformDiscoveryWidget")
        self.setFixedHeight(94)  # Ekranı taşmayacak kadar kompakt ve şık
        self._current_index = 0
        self._cards = DISCOVERY_CARDS

        # Yumuşak kart gölgesi
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 1. Sol: Parlayan İkon Rozeti
        self.icon_frame = QFrame()
        self.icon_frame.setFixedSize(48, 48)
        icon_shadow = QGraphicsDropShadowEffect(self.icon_frame)
        icon_shadow.setBlurRadius(10)
        icon_shadow.setOffset(0, 2)
        icon_shadow.setColor(QColor(0, 0, 0, 30))
        self.icon_frame.setGraphicsEffect(icon_shadow)

        icon_lay = QVBoxLayout(self.icon_frame)
        icon_lay.setContentsMargins(0, 0, 0, 0)
        icon_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_icon = QLabel("📲")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setStyleSheet("font-size: 24px; background: transparent; border: none;")
        icon_lay.addWidget(self.lbl_icon)

        layout.addWidget(self.icon_frame)

        # 2. Orta: Metin Alanı (Tag + Başlık + Açıklama)
        center_v = QVBoxLayout()
        center_v.setContentsMargins(0, 0, 0, 0)
        center_v.setSpacing(3)
        center_v.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Üst Etiket Satırı
        top_meta = QHBoxLayout()
        top_meta.setSpacing(8)

        self.lbl_tag = QLabel("📱 MOBİL ASİSTAN")
        self.lbl_tag.setStyleSheet("""
            background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;
            border-radius: 4px; padding: 1px 6px; font-size: 9px; font-weight: 800;
        """)
        top_meta.addWidget(self.lbl_tag)

        self.lbl_hint = QLabel("💡 Platformu Keşfet")
        self.lbl_hint.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 600; border: none; background: transparent;")
        top_meta.addWidget(self.lbl_hint)

        top_meta.addStretch(1)
        center_v.addLayout(top_meta)

        # Ana Başlık
        self.lbl_title = QLabel("Masaya bağlı kalmadan sınıfta telefonla kontrol yapın!")
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #0f172a; border: none; background: transparent;")
        center_v.addWidget(self.lbl_title)

        # Açıklama Metni
        self.lbl_desc = QLabel("Mobil merkezden QR barkodu okutun; sınıfta dolaşırken tüm ödevleri cep telefonunuzdan onaylayın.")
        self.lbl_desc.setStyleSheet("font-size: 11px; font-weight: 500; color: #475569; border: none; background: transparent;")
        self.lbl_desc.setWordWrap(False)
        center_v.addWidget(self.lbl_desc)

        layout.addLayout(center_v, 1)

        # 3. Sağ: Aksiyon Butonu & Karusel Kontrolleri
        right_v = QVBoxLayout()
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(4)
        right_v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Ana Eylem Butonu
        self.btn_action = QPushButton("Mobil Bağlantıyı Aç →")
        self.btn_action.setFixedHeight(30)
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1d4ed8);
                color: #ffffff;
                font-weight: 800;
                font-size: 11px;
                border: 1px solid #1e40af;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
        """)
        self.btn_action.clicked.connect(self._on_action_clicked)
        right_v.addWidget(self.btn_action)

        # Karusel Yönlendirici (Önceki, Noktalar, Sonraki)
        nav_h = QHBoxLayout()
        nav_h.setSpacing(6)
        nav_h.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_prev = QPushButton("‹")
        self.btn_prev.setFixedSize(18, 18)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #cbd5e1;
                border-radius: 9px; color: #64748b; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
        """)
        self.btn_prev.clicked.connect(self._prev_card)
        nav_h.addWidget(self.btn_prev)

        self.lbl_dots = QLabel("● ○ ○ ○ ○ ○")
        self.lbl_dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_dots.setStyleSheet("color: #64748b; font-size: 10px; border: none; background: transparent;")
        nav_h.addWidget(self.lbl_dots)

        self.btn_next = QPushButton("›")
        self.btn_next.setFixedSize(18, 18)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #cbd5e1;
                border-radius: 9px; color: #64748b; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
        """)
        self.btn_next.clicked.connect(self._next_card)
        nav_h.addWidget(self.btn_next)

        right_v.addLayout(nav_h)
        layout.addLayout(right_v)

        # 4. Otomatik Karusel Zamanlayıcısı (8 saniye)
        self._timer = QTimer(self)
        self._timer.setInterval(8500)
        self._timer.timeout.connect(self._next_card)
        self._timer.start()

        # İlk kartı göster
        self._display_card(0)

        register_theme_listener(self)
        self._on_theme_changed()

    def enterEvent(self, event):
        """Kullanıcı fareyi üzerine getirdiğinde otomatik geçişi duraklat."""
        self._timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Kullanıcı fareyi çektiğinde otomatik geçişi yeniden başlat."""
        self._timer.start()
        super().leaveEvent(event)

    def _display_card(self, index: int):
        if not self._cards:
            return
        self._current_index = index % len(self._cards)
        card = self._cards[self._current_index]

        # İkon Rozeti
        c1, c2 = card["icon_grad"]
        self.icon_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c1}, stop:1 {c2});
                border-radius: 24px;
                border: 2px solid rgba(255, 255, 255, 0.4);
            }}
        """)
        self.lbl_icon.setText(card["icon"])

        # Tag
        self.lbl_tag.setText(card["tag"])
        self.lbl_tag.setStyleSheet(f"""
            background: {card['tag_bg']};
            color: {card['tag_fg']};
            border: 1px solid {card['tag_border']};
            border-radius: 4px;
            padding: 1px 6px;
            font-size: 9px;
            font-weight: 800;
        """)

        # Başlık ve Açıklama
        self.lbl_title.setText(card["title"])
        self.lbl_desc.setText(card["desc"])

        # Aksiyon Butonu
        self.btn_action.setText(card["btn_text"])

        # Noktalar
        dots = []
        for i in range(len(self._cards)):
            dots.append("●" if i == self._current_index else "○")
        self.lbl_dots.setText(" ".join(dots))

    def _next_card(self):
        self._display_card(self._current_index + 1)

    def _prev_card(self):
        self._display_card(self._current_index - 1)

    def _on_action_clicked(self):
        if not self._cards:
            return
        card = self._cards[self._current_index]
        self.sig_action_triggered.emit(card.get("feature_key", ""))

    def _on_theme_changed(self):
        c = semantic_palette()
        is_dark = c.get("dark", False)

        bg = "#1e293b" if is_dark else "#ffffff"
        border = "#334155" if is_dark else "#e2e8f0"
        title_fg = "#f8fafc" if is_dark else "#0f172a"
        desc_fg = "#94a3b8" if is_dark else "#475569"

        self.setStyleSheet(f"""
            QFrame#PlatformDiscoveryWidget {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
        """)
        self.lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {title_fg}; border: none; background: transparent;")
        self.lbl_desc.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {desc_fg}; border: none; background: transparent;")
