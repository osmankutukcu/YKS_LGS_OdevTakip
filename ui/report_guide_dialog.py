# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor

class ReportGuideDialog(QDialog):
    """
    Koçun doğru zamanda en doğru raporlama aracını seçmesini sağlayan,
    tek tıkla ilgili rapora doğrudan geçiş imkânı sunan interaktif rehber.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ℹ️ Koçluk Rapor ve Analiz Rehberi")
        self.resize(880, 640)
        self.setMinimumSize(780, 520)

        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QLabel { font-family: 'Segoe UI', Arial, sans-serif; }
            QPushButton { font-family: 'Segoe UI', Arial, sans-serif; }
            QFrame#Card { 
                background-color: #ffffff; 
                border: 1px solid #e2e8f0; 
                border-radius: 10px; 
            }
            QFrame#Card:hover {
                border: 1px solid #94a3b8;
                background-color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # 1. ÜST BAŞLIK BARI
        top_box = QHBoxLayout()
        v_title = QVBoxLayout()
        lbl_h = QLabel("ℹ️ Hangi Durumda Hangi Raporu Kullanmalıyım?")
        lbl_h.setStyleSheet("font-size: 17px; font-weight: 800; color: #0f172a;")
        lbl_sub = QLabel("Öğrenci, veli veya kurum değerlendirmelerinde en doğru aracı seçmek için aşağıdaki rehberden yararlanabilir, doğrudan açabilirsiniz.")
        lbl_sub.setStyleSheet("font-size: 11.5px; color: #64748b;")
        v_title.addWidget(lbl_h)
        v_title.addWidget(lbl_sub)
        top_box.addLayout(v_title, 1)
        layout.addLayout(top_box)

        # 2. HIZLI KARAR MATRİSİ (ÖZET KART)
        matrix_card = QFrame()
        matrix_card.setStyleSheet("background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 6px;")
        m_lay = QHBoxLayout(matrix_card)
        m_lay.setContentsMargins(12, 8, 12, 8)
        m_lay.setSpacing(12)

        def make_matrix_tip(icon, scenario, solution):
            tip = QLabel(f"<b>{icon} {scenario}:</b> <span style='color: #1d4ed8;'>{solution}</span>")
            tip.setStyleSheet("font-size: 11px; color: #1e3a8a;")
            return tip

        m_lay.addWidget(make_matrix_tip("👨‍👩‍👧", "Veliyi Bilgilendirme", "Hızlı PDF"))
        m_lay.addWidget(make_matrix_tip("📌", "Sınıf Panosuna Asma", "Performans Posteri"))
        m_lay.addWidget(make_matrix_tip("🎯", "Hedef ve Net Açığı", "Hedef Analizi"))
        m_lay.addWidget(make_matrix_tip("📊", "Genel Sınıf Grafiği", "Detaylı Raporlar"))
        layout.addWidget(matrix_card)

        # 3. KARTLAR IZGARASI (SCROLL AREA)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 4, 2, 4)
        content_layout.setSpacing(12)

        reports = [
            {
                "id": "pdf",
                "title": "1. Hızlı PDF & Veli Ödev Karnesi",
                "icon": "📄",
                "accent": "#2563eb",
                "badge": "En Çok Tercih Edilen",
                "uses": [
                    "Veli veya öğrenciyle WhatsApp veya elden paylaşmak için idealdir.",
                    "Son 30 günlük tamamlanan ödevleri ve kitap bitirme oranlarını tek sayfada özetler.",
                    "Eksik konular, çözülen soru sayıları ve koç değerlendirmesini içerir."
                ],
                "action": "📄 Hızlı PDF'yi Aç",
                "handler": self._open_pdf_action
            },
            {
                "id": "perf",
                "title": "2. Performans Paneli & Renkli A4 Pano Posteri",
                "icon": "🏆",
                "accent": "#f59e0b",
                "badge": "Duvar / Pano Çıktısı",
                "uses": [
                    "Haftanın 1., 2. ve 3. şampiyonlarını ve ilk 5'i liderlik kürsüsünde gösterir.",
                    "%80+ Başarı Kulübü gurur tablosu ve gelişim gösteren yıldızları listeler.",
                    "Tek tıkla panoya asılmaya hazır, tam sayfa renkli A4 Pano Posteri (PDF) üretir."
                ],
                "action": "🏆 Performans Paneline Git",
                "handler": self._open_perf_action
            },
            {
                "id": "target",
                "title": "3. Akıllı Hedef ve Net Analizi",
                "icon": "🎯",
                "accent": "#10b981",
                "badge": "Stratejik Planlama",
                "uses": [
                    "Öğrencinin hedeflediği üniversite/lise için gereken netler ile mevcut netlerini kıyaslar.",
                    "Kalan net açıklarını branş branş tespit eder ve nokta atışı çalışma tavsiyesi verir.",
                    "YKS/LGS yığılma ve sıralama simülasyonları sunar."
                ],
                "action": "🎯 Hedef Analizini Aç",
                "handler": self._open_target_action
            },
            {
                "id": "report",
                "title": "4. Detaylı Raporlar & Toplu Değerlendirme",
                "icon": "📈",
                "accent": "#8b5cf6",
                "badge": "Kurumsal / İdari",
                "uses": [
                    "Tüm şube ve grupların haftalık başarı dağılımını grafiklerle gösterir.",
                    "Ders bazlı genel sınıf ortalamalarını ve riskli öğrencileri listeler.",
                    "Tüm listeyi Excel (.xlsx) veya arşivlik PDF olarak dışa aktarır."
                ],
                "action": "📈 Detaylı Raporları Aç",
                "handler": self._open_report_action
            },
            {
                "id": "smart",
                "title": "5. Günün Akıllı Özeti (Koç Asistanı)",
                "icon": "🧠",
                "accent": "#06b6d4",
                "badge": "Günlük Koçluk",
                "uses": [
                    "Bugün randevusu olan, teslim süresi yaklaşan veya geciken öğrencileri özetler.",
                    "Koçun güne başlarken 2 dakikada tüm kurumun kontrolünü eline almasını sağlar.",
                    "Akıllı aksiyon önerileri ile otomatik WhatsApp hatırlatması başlatır."
                ],
                "action": "🧠 Günün Özetini Aç",
                "handler": self._open_smart_action
            },
            {
                "id": "topic",
                "title": "6. Konu Hakimiyet Haritası & ÖSYM Stratejisi",
                "icon": "🗺️",
                "accent": "#ec4899",
                "badge": "Müfredat Takibi",
                "uses": [
                    "Ders ders tüm YKS/LGS konularının ne kadarının bittiğini daire grafiklerle görselleştirir.",
                    "ÖSYM'nin son 5 yılda en çok soru sorduğu kritik konuları öne çıkarır.",
                    "Öğrenciye özel A4 Pano Konu Takip Çizelgesi çıktısı verir."
                ],
                "action": "🗺️ Konu Haritasını Aç",
                "handler": self._open_topic_action
            }
        ]

        for rep in reports:
            card = QFrame(objectName="Card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(8)

            # Başlık Satırı
            trow = QHBoxLayout()
            icon_lbl = QLabel(rep["icon"])
            icon_lbl.setStyleSheet("font-size: 24px;")
            
            title_lbl = QLabel(rep["title"])
            title_lbl.setStyleSheet(f"font-size: 13.5px; font-weight: 800; color: #0f172a;")

            badge_lbl = QLabel(rep["badge"])
            badge_lbl.setStyleSheet(f"background: #f1f5f9; color: {rep['accent']}; font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 5px; border: 1px solid #cbd5e1;")

            trow.addWidget(icon_lbl)
            trow.addWidget(title_lbl)
            trow.addWidget(badge_lbl)
            trow.addStretch(1)

            btn_act = QPushButton(rep["action"])
            btn_act.setStyleSheet(f"background: {rep['accent']}; color: white; font-weight: 700; font-size: 11px; padding: 6px 14px; border-radius: 6px; border: none;")
            btn_act.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_act.clicked.connect(rep["handler"])
            trow.addWidget(btn_act)

            cl.addLayout(trow)

            # Açıklama Maddeleri
            ul_text = "<ul style='margin: 0; padding-left: 18px; color: #475569; font-size: 11.5px; line-height: 1.4;'>"
            for u in rep["uses"]:
                ul_text += f"<li style='margin-bottom: 2px;'>{u}</li>"
            ul_text += "</ul>"

            body = QLabel(ul_text)
            body.setWordWrap(True)
            cl.addWidget(body)

            content_layout.addWidget(card)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Alt Buton
        btn_close = QPushButton("✓ Rehberi Kapat")
        btn_close.setStyleSheet("background: #e2e8f0; color: #334155; font-weight: 700; padding: 8px 24px; border-radius: 6px; border: none;")
        btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignCenter)

    # --- AKSİYON YÖNLENDİRMELERİ ---
    def _open_pdf_action(self):
        self.accept()
        p = self.parent()
        if p and hasattr(p, "_create_pdf_report"):
            p._create_pdf_report()

    def _open_perf_action(self):
        self.accept()
        p = self.parent()
        if p and hasattr(p, "_performans_paneli"):
            p._performans_paneli()

    def _open_target_action(self):
        self.accept()
        p = self.parent()
        if p and hasattr(p, "_hedef_analiz_open"):
            p._hedef_analiz_open()

    def _open_report_action(self):
        self.accept()
        p = self.parent()
        if p and hasattr(p, "_rapor_ac"):
            p._rapor_ac()

    def _open_smart_action(self):
        self.accept()
        p = self.parent()
        if p and hasattr(p, "_smart_asistan"):
            p._smart_asistan()

    def _open_topic_action(self):
        self.accept()
        p = self.parent()
        if p and hasattr(p, "_open_topic_map"):
            p._open_topic_map()
