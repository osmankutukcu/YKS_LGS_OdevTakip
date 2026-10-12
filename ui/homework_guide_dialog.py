"""Ödev Takip Formu, Öğrenci 360° ve Veri Denetimi Kullanım Rehberi Diyaloğu."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame
)


class OdevTakipRehberDialog(QDialog):
    """Kullanıcının formun tüm bileşenlerini ve yeniliklerini kolayca anlamasını sağlayan modern rehber."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ℹ️ Ödev Takip Formu & Özellikler Rehberi")
        self.setMinimumSize(580, 520)
        self.resize(620, 560)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Başlık ve Rozet
        header = QHBoxLayout()
        lbl_title = QLabel("📚 Ödev Takip & Akıllı Koçluk Rehberi")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a;")
        header.addWidget(lbl_title)
        header.addStretch(1)

        badge_v = QLabel("V23.6 / V3518")
        badge_v.setStyleSheet("""
            font-size: 10.5px; font-weight: 700; color: #2563eb;
            background: #eff6ff; border: 1px solid #bfdbfe;
            border-radius: 10px; padding: 2px 8px;
        """)
        header.addWidget(badge_v)
        root.addLayout(header)

        # Kaydırılabilir İçerik Alanı
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 8, 0)
        inner_lay.setSpacing(10)

        # Kart 1: Ödev Takip Genel Mantığı
        inner_lay.addWidget(self._make_card(
            title="🎯 1. Ödev Takip ve Çalışma Mantığı",
            color="#2563eb",
            bg="#f0f7ff",
            border="#bfdbfe",
            content="""• <b>Ders & Konu Seçimi:</b> Sol taraftan ders sekmesini seçip, öğrencinin kaynak kitabıyla kesişen kutucuğa tıklayarak anında ödev atayabilirsiniz.<br>
• <b>Sağ Tablo (Verilen Ödevler):</b> İşaretlenen ödevler sağdaki listeye dinamik eklenir. İsterseniz süre ve açıklama ekleyebilirsiniz.<br>
• <b>Kaydet (Ctrl+S):</b> Değişiklikleri kalıcı olarak kaydeder. <b>F5</b> ile öğrenci durumunu yenileyebilirsiniz."""
        ))

        # Kart 2: Öğrenci 360° Nedir?
        inner_lay.addWidget(self._make_card(
            title="🧭 2. Öğrenci 360° Nedir ve Ne İşe Yarar?",
            color="#0d9488",
            bg="#f0fdfa",
            border="#99f6e4",
            content="""• <b>Bütünsel Öğrenci Görünümü:</b> Alt bardaki <b>[ 🧭 Öğrenci 360° ]</b> butonuna tıkladığınızda sağda salt okunur bir analiz paneli açılır.<br>
• <b>Ödev Verirken Karne İnceleme:</b> Öğrencinin son deneme sınavı netlerini, konu haritasındaki güçlü/zayıf kazanımlarını ve geçmiş ödev performansını ödev ekranından ayrılmadan incelersiniz.<br>
• <b>Akıllı Eşleşme:</b> Öğrencinin eksik kaldığı konuları görüp ona göre hedef odaklı ödev belirlemenizi sağlar."""
        ))

        # Kart 3: Veri Denetimi Nedir?
        inner_lay.addWidget(self._make_card(
            title="🔎 3. Veri Denetimi Ne İşe Yarar?",
            color="#b45309",
            bg="#fffbeb",
            border="#fde68a",
            content="""• <b>Salt Okunur Tutarlılık Kontrolü:</b> Alt bardaki <b>[ 🔎 Denetim ]</b> butonu sistemin veritabanını tarar.<br>
• <b>Kayıp ve Bağlantısız Ödev Tespiti:</b> Silinmiş veya müfredat ID bağlantısı kopmuş ödevleri, mükerrer işaretlemeleri güvenle denetler.<br>
• <b>Doğruluk Güvencesi:</b> Verilerinize zarar vermeden rapor sunar ve sistem sağlığını garanti eder."""
        ))

        # Kart 4: Üst ve Alt Araç Butonları
        inner_lay.addWidget(self._make_card(
            title="⚡ 4. Hızlı Butonlar ve Kısayollar",
            color="#7c3aed",
            bg="#faf5ff",
            border="#ddd6fe",
            content="""• <b>🔄 Getir (F5):</b> Öğrenci ders ve kitap havuzunu veritabanından tazeleyip yükler.<br>
• <b>📚 Kitaplar:</b> Öğrencinin kaynak kitap havuzunu yönetir.<br>
• <b>💾 Kaydet (Ctrl+S):</b> Yapılan tüm ödevlendirmeleri kaydeder.<br>
• <b>📅 Takvim & Plan:</b> Haftalık çalışma planı ve randevu takvimi oluşturur.<br>
• <b>✅ Kontrol (F2):</b> Ödev kontrol ve değerlendirme ekranını açar.<br>
• <b>💬 WhatsApp:</b> Veli ve öğrenciye tek tıkla şık ödev bildirim mesajı gönderir.<br>
• <b>🔍 Filtre & 🧹 Temizle:</b> Sağ tablodaki filtreleri açar veya tabloyu temizler (öğrencinin geçmiş kayıtları silinmez)."""
        ))

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # Alt Kapat Butonu
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_close = QPushButton("Anladım, Kapat")
        btn_close.setFixedHeight(28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; font-weight: 700;
                font-size: 11.5px; border-radius: 6px; padding: 4px 18px; border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        root.addLayout(btn_box)

    def _make_card(self, title: str, color: str, bg: str, border: str, content: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(5)

        lbl_head = QLabel(title)
        lbl_head.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {color}; border: none; background: transparent;")
        lay.addWidget(lbl_head)

        lbl_body = QLabel(content)
        lbl_body.setWordWrap(True)
        lbl_body.setStyleSheet("font-size: 11px; color: #334155; line-height: 1.4; border: none; background: transparent;")
        lay.addWidget(lbl_body)

        return card
