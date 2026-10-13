from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect, QPushButton
)
from ui.gamification_widget import GamificationWidget
from ui.info_board_widget import InfoBoardWidget
from services.smart_tips import SmartTipGenerator
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QBrush, QPalette, QFont, QPainter, QPainterPath, QPen

import random
import datetime
from datetime import date
import db

class SimpleDonutChart(QWidget):
    """Basit bir Donut grafik (QPainter ile)."""
    def __init__(self, title, percent, color="#3b82f6", parent=None):
        super().__init__(parent)
        self.title = title
        self.percent = percent
        self.color = color
        self.setMinimumSize(120, 100)  # Biraz daha kompakt
        self.setSizePolicy(
            db.sys.modules['PyQt6.QtWidgets'].QSizePolicy.Policy.Expanding,
            db.sys.modules['PyQt6.QtWidgets'].QSizePolicy.Policy.Fixed
        )

    def set_data(self, percent):
        self.percent = percent
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        
        # Merkez
        cx, cy = rect.center().x(), rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 - 8
        thickness = 10
        
        # Arka plan halkası
        p.setPen(QPen(QColor("#e2e8f0"), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawEllipse(QPointF(cx, cy), radius, radius)
        
        # Dolu kısım
        p.setPen(QPen(QColor(self.color), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        # 0 derece saat 3'te, -90 saat 12'de
        # PyQt drawArc: 1 birim = 1/16 derece
        if self.percent is not None:
            span_angle = int(-self.percent * 3.6 * 16)
            p.drawArc(int(cx-radius), int(cy-radius), int(radius*2), int(radius*2), 90*16, span_angle)
        
        # Ortadaki yazı
        p.setPen(QColor("#1e293b"))
        f = p.font(); f.setBold(True); f.setPixelSize(16); p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—" if self.percent is None else f"%{int(self.percent)}")


class DashboardCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, title: str, icon: str, bg_gradient: tuple[str, str], parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFixedHeight(100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg_gradient[0]}, stop:1 {bg_gradient[1]});
                border-radius: 12px;
                border: 1px solid rgba(255,255,255, 0.3);
            }}
            QLabel {{
                background: transparent;
                color: white;
                border: none;
            }}
        """)
        
        # Layout
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        
        # Header (Icon + Title)
        h = QHBoxLayout()
        self.lblIcon = QLabel(icon)
        self.lblIcon.setStyleSheet("font-size: 24px;")
        self.lblTitle = QLabel(title)
        self.lblTitle.setStyleSheet("font-size: 14px; font-weight: 600; opacity: 0.9;")
        
        h.addWidget(self.lblIcon)
        h.addWidget(self.lblTitle)
        h.addStretch(1)
        v.addLayout(h)
        
        # Value
        self.lblValue = QLabel("-")
        self.lblValue.setStyleSheet("font-size: 28px; font-weight: 800; margin-top: 4px;")
        self.lblValue.setAlignment(Qt.AlignmentFlag.AlignLeft)
        v.addWidget(self.lblValue)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0,0,0, 40))
        self.setGraphicsEffect(shadow)

    def set_value(self, val: str):
        self.lblValue.setText(str(val))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()


class SmartInsightCard(QFrame):
    """
    Akıllı öneri kartı.
    Yapay zeka (basit kural tabanlı) ile öğrenci durumuna göre öneri verir.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(100) # Diğer kartlarla aynı boy
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8b5cf6, stop:1 #7c3aed);
                border-radius: 12px;
                border: 1px solid rgba(255,255,255, 0.3);
            }
            QLabel {
                background: transparent;
                color: white;
                border: none;
            }
        """)

        h = QHBoxLayout(self)
        h.setContentsMargins(16, 10, 16, 10)
        
        # İkon
        self.lblIcon = QLabel("💡")
        self.lblIcon.setStyleSheet("font-size: 32px;")
        h.addWidget(self.lblIcon)
        
        # Metin Alanı
        v = QVBoxLayout()
        v.setSpacing(4)
        self.lblTitle = QLabel("Günün İpucu")
        self.lblTitle.setStyleSheet("font-size: 12px; font-weight: 700; opacity: 0.8; text-transform: uppercase;")
        
        self.lblMsg = QLabel("Veriler analiz ediliyor...")
        self.lblMsg.setWordWrap(True)
        self.lblMsg.setStyleSheet("font-size: 13px; font-weight: 500; line-height: 1.2;")
        
        v.addWidget(self.lblTitle)
        v.addWidget(self.lblMsg)
        v.addStretch()
        h.addLayout(v, 1) # Stretch 1
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0,0,0, 40))
        self.setGraphicsEffect(shadow)

    def set_insight(self, msg, icon="💡", colors=None):
        self.lblMsg.setText(msg)
        self.lblIcon.setText(icon)
        
        c1, c2 = ("#8b5cf6", "#7c3aed") # Default Purple
        if colors and len(colors) >= 2:
            c1, c2 = colors
            
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c1}, stop:1 {c2});
                border-radius: 12px;
                border: 1px solid rgba(255,255,255, 0.3);
            }}
            QLabel {{
                background: transparent;
                color: white;
                border: none;
            }}
        """)

class _SimpleBarChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = [] # [{'day': '...', 'val': 0..100}]
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, e):
        if not self.data: return
        
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        n = len(self.data)
        if n == 0: return

        # Barlar arası boşluk hesabı
        bar_width = (w / n) * 0.6
        spacing = (w / n) * 0.4
        max_val = 100 # Maksimum %100 kabul edelim
        
        # Yazı fontu
        f = p.font()
        f.setPixelSize(10)
        p.setFont(f)
        
        start_x = spacing / 2
        
        for i, item in enumerate(self.data):
            val = item['val']
            day_str = item['day']
            has_data = item.get('total', 1) > 0
            
            # Yükseklik
            bar_h = (val / max_val) * (h - 20) # 20px alttan metin payı
            if bar_h < 4: bar_h = 4 # Min yükseklik
            
            x = int(start_x + i * (bar_width + spacing))
            y = int(h - 20 - bar_h)
            
            # Renk (Value'ya göre)
            color = QColor("#3b82f6") # Blue
            if val < 50: color = QColor("#ef4444") # Red
            elif val >= 85: color = QColor("#10b981") # Green
            
            # Barı çiz
            path = QPainterPath()
            path.addRoundedRect(QRectF(float(x), float(y), float(bar_width), float(bar_h)), 4.0, 4.0)
            if has_data:
                p.fillPath(path, color)
            
            # Etiket (Gün)
            p.setPen(QColor("#64748b"))
            rect_txt = QRectF(float(x) - 5, float(h) - 20, float(bar_width) + 10, 20.0)
            p.drawText(rect_txt, Qt.AlignmentFlag.AlignCenter, day_str)
            
            # Etiket (Değer - Barın üstüne)
            # Sadece yer varsa çizelim
            p.setPen(QColor("#334155"))
            val_rect = QRectF(float(x) - 5, float(y) - 15, float(bar_width) + 10, 15.0)
            p.drawText(val_rect, Qt.AlignmentFlag.AlignCenter, str(int(val)) if has_data else "—")

class WeeklyTrendWidget(QFrame):
    """
    Son 7 günün soru çözüm/ödev tamamlama performansını gösteren özel görselleştirme.
    Minimalist bir 'Activity Graph' (Github katkı grafiği veya bar chart karışımı).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(180) # Biraz genişçe
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
        """)
        
        # Gölge
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10); shadow.setOffset(0, 3); shadow.setColor(QColor(0,0,0,15))
        self.setGraphicsEffect(shadow)
        
        # Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(6)
        
        # Başlık ve Özet
        top_h = QHBoxLayout()
        
        title_v = QVBoxLayout()
        title_v.setSpacing(2)
        lbl_h = QLabel("Haftalık Performans Trendi")
        lbl_h.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e293b; border:none; background:transparent;")
        lbl_desc = QLabel("Son 7 günde teslim günü gelen ödevlerin durumu")
        lbl_desc.setStyleSheet("font-size: 11px; color: #64748b; border:none; background:transparent;")
        title_v.addWidget(lbl_h); title_v.addWidget(lbl_desc)
        top_h.addLayout(title_v)
        
        top_h.addStretch()
        
        # Sağ üstte basit bir "Haftalık Ortalama" göstergesi
        self.lbl_week_avg = QLabel("%0")
        self.lbl_week_avg.setStyleSheet("font-size: 20px; font-weight: 800; color: #3b82f6; border:none; background:transparent;")
        top_h.addWidget(self.lbl_week_avg)
        
        self.main_layout.addLayout(top_h)
        self.main_layout.addSpacing(10)
        
        # Grafik Alanı
        self.chart_area = _SimpleBarChart()
        self.main_layout.addWidget(self.chart_area)

    def set_data(self, daily_stats):
        """
        daily_stats: List[dict] -> [{'day': 'Pzt', 'val': 45}, ...] 
        (Son 7 gün)
        """
        self.chart_area.data = daily_stats
        self.chart_area.update()
        
        # Ortalamayı hesapla
        total = sum(d.get('total', 1) for d in daily_stats)
        if total:
            # Weighted by homework item, not by number of calendar days.
            if all('done' in d for d in daily_stats):
                avg = 100 * sum(d['done'] for d in daily_stats) / total
            else:
                avg = sum(d['val'] for d in daily_stats) / len(daily_stats)
            self.lbl_week_avg.setText(f"%{int(avg)}")
        else:
            self.lbl_week_avg.setText("—")

class DashboardWidget(QWidget):
    sig_open_today = pyqtSignal()
    sig_open_students = pyqtSignal()
    sig_open_overdue = pyqtSignal()
    sig_open_adaptive = pyqtSignal()
    


    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        # Timer ile başlat
        QTimer.singleShot(100, self.refresh_stats)

    def init_ui(self):
        # Ana Dikey Layout (Üstte kartlar, altta geniş Smart Card)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 0, 4, 8)
        main_layout.setSpacing(16) # Spacing arttı

        # --- 0. BİLGİ PANOSU (YENİ - WEB) ---
        self.info_board = InfoBoardWidget()
        main_layout.addWidget(self.info_board)
        # V26: visible decision workflow; never calculates false mastery scores.
        from services.adaptive_coaching_v26.flags import enabled as adaptive_v26_enabled
        if adaptive_v26_enabled():
            coachbar = QFrame()
            coachbar.setStyleSheet("QFrame {background:#eaf1fb;border:1px solid #d5e3f4;border-radius:9px;}")
            coachrow = QHBoxLayout(coachbar)
            coachrow.setContentsMargins(12,7,12,7)
            prompt = QLabel('🧠  Öğretmen Karar Masası · Önce kazanımı ölç, sonra kişisel ödev öner')
            prompt.setWordWrap(True)
            prompt.setStyleSheet('font-size:12px;font-weight:600;color:#173354;border:0;background:transparent;')
            coachrow.addWidget(prompt,1)
            opencoach = QPushButton('Adaptif Koçluk Merkezi  →')
            opencoach.setStyleSheet('background:white;color:#1d4ed8;padding:8px 10px;border:1px solid #b9cfee;border-radius:7px;font-weight:700;')
            opencoach.clicked.connect(self.sig_open_adaptive.emit)
            coachrow.addWidget(opencoach)
            main_layout.addWidget(coachbar)

        # Üst Sıra (Mevcut Kartlar)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        
        # 1. Bugünkü Ödevler (Mavi)
        self.card_tasks = DashboardCard(
            "Bugünkü Ödev Kontrolü", "📚", ("#3b82f6", "#2563eb") # Blue
        )
        self.card_tasks.clicked.connect(self.sig_open_today.emit)

        # 2. Aktif Öğrenciler (Yeşil)
        self.card_students = DashboardCard(
            "Aktif Öğrenciler", "👥", ("#10b981", "#059669") # Green
        )
        self.card_students.clicked.connect(self.sig_open_students.emit)

        # 3. Geciken Ödevler (Kırmızı)
        self.card_overdue = DashboardCard(
            "Geciken Ödevler", "⚠️", ("#ef4444", "#b91c1c") # Red
        )
        self.card_overdue.clicked.connect(self.sig_open_overdue.emit)

        # 4. Genel Başarı Grafiği
        self.frame_chart = QFrame()
        self.frame_chart.setFixedHeight(100)
        self.frame_chart.setFixedWidth(140) # Sabit genişlik, grafiğin çok uzamasını engeller
        self.frame_chart.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
            }
        """)
        lay_chart = QVBoxLayout(self.frame_chart)
        lay_chart.setContentsMargins(0, 5, 0, 5)
        
        self.chart = SimpleDonutChart("Genel Başarı", 0, "#8b5cf6")
        
        lbl_chart_title = QLabel("Tamamlama")
        lbl_chart_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_chart_title.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: 600;")
        
        lay_chart.addWidget(self.chart, 1)
        lay_chart.addWidget(lbl_chart_title)
        
        # Gölge
        shadow = QGraphicsDropShadowEffect(self.frame_chart)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0,0,0, 20))
        self.frame_chart.setGraphicsEffect(shadow)

        top_row.addWidget(self.card_tasks)
        top_row.addWidget(self.card_students)
        top_row.addWidget(self.card_overdue)
        top_row.addWidget(self.frame_chart)
        
        main_layout.addLayout(top_row)
        
        # --- ORTA GRUP: HAFTALIK TREND GRAFİĞİ (YENİ) ---
        self.trend_widget = WeeklyTrendWidget()
        main_layout.addWidget(self.trend_widget)
        
        # --- ROZET ALANI (YENİ) ---
        self.badge_widget = GamificationWidget()
        main_layout.addWidget(self.badge_widget)
        


        
        # Alt Sıra: AKILLI ÖNERİ KARTI
        self.smart_card = SmartInsightCard()
        main_layout.addWidget(self.smart_card)


    def refresh_stats(self):
        """Read one reliable snapshot, then refresh the *existing* UI widgets.

        No homework writes; the navigation signals, layouts and paint styles
        retain their old behavior. Errors remain visible rather than becoming 0.
        """
        import logging
        from services.dashboard_metrics_v35 import build_snapshot, build_teacher_insight

        con = None
        try:
            con = db.get_conn()
            snapshot = build_snapshot(con)
        except Exception:
            logging.getLogger(__name__).exception("Dashboard KPI computation failed")
            self.card_students.set_value("—")
            self.card_tasks.set_value("—")
            self.card_overdue.set_value("—")
            self.chart.set_data(None)
            self.trend_widget.set_data([])
            self.badge_widget.refresh_badges({"total_students": None,
                                             "total_homeworks": 0,
                                             "alerts": [{"text": "İstatistikler şu anda hesaplanamadı.",
                                                         "severity": "medium",
                                                         "tip": "Veritabanını kontrol edip yenileyin."}]})
            self.smart_card.set_insight(
                "Veriler hesaplanamadı. Yeniden deneyin; sonuçları sıfır olarak yorumlamayın.",
                "⚠️")
            return
        finally:
            if con is not None:
                con.close()

        self.card_students.set_value(snapshot.active_students)
        self.card_tasks.set_value(snapshot.due_today_sets)
        self.card_overdue.set_value(snapshot.overdue_items)
        self.chart.set_data(snapshot.completion_pct)
        self.trend_widget.set_data(snapshot.trend)
        self.badge_widget.refresh_badges(snapshot.to_gamification_stats())
        self.smart_card.set_insight(build_teacher_insight(snapshot), "🎯")

        # Same widgets and dimensions.  Only their metric definitions are
        # clarified using lightweight native tooltips.
        self.card_tasks.setToolTip("Teslim tarihi bugün olan, en az bir açık ödev içeren küme sayısı.")
        self.card_overdue.setToolTip("Teslim tarihi geçmiş, henüz tamamlanmamış ödev SATIRI sayısı.")
        self.frame_chart.setToolTip("Aktif öğrencilerin ödev tamamlama yüzdesi; akademik kazanım başarısı değildir.")
        self.trend_widget.setToolTip(
            "Son 7 günde teslim tarihi gelen ödevlerde mevcut tamamlama durumu. "
            "Çalışmanın tamamlandığı gün veya öğrenme başarısı değildir.")
