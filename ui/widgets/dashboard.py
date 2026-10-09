# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QGraphicsDropShadowEffect, QSizePolicy, QGridLayout, QPushButton)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QLinearGradient, QBrush, QPen, QFont
import db
import datetime

class InfoCard(QFrame):
    """
    Tek bir istatistik kartı.
    - Başlık (Küçük)
    - Değer (Büyük)
    - İkon (Emoji veya SVG path)
    - Değişim oranı (Yeşil/Kırmızı ok)
    """
    def __init__(self, title, value, icon, subtext="", color_start="#4facfe", color_end="#00f2fe", parent=None):
        super().__init__(parent)
        self.setObjectName("InfoCard")
        self.setMinimumHeight(100)
        self.color_start = color_start
        self.color_end = color_end
        
        # Gölge
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0,0,0, 40))
        shadow.setOffset(0,4)
        self.setGraphicsEffect(shadow)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(15,12,15,12)
        
        # Üst kısım: Başlık + İkon
        top = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 13px; font-weight: 500;")
        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 20px; background: rgba(255,255,255,0.2); border-radius: 8px; padding: 4px;")
        
        top.addWidget(lbl_title)
        top.addStretch(1)
        top.addWidget(lbl_icon)
        lay.addLayout(top)
        
        # Orta: Değer
        self.lbl_val = QLabel(str(value))
        self.lbl_val.setStyleSheet("color: #FFFFFF; font-size: 26px; font-weight: 800;")
        lay.addWidget(self.lbl_val)
        
        # Alt: Alt metin
        if subtext:
            lbl_sub = QLabel(subtext)
            lbl_sub.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 11px;")
            lay.addWidget(lbl_sub)
        
        lay.addStretch(1)

    def set_value(self, val):
        self.lbl_val.setText(str(val))

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Gradient Arka Plan
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor(self.color_start))
        grad.setColorAt(1, QColor(self.color_end))
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        
        painter.fillPath(path, grad)

class SimpleDonutChart(QWidget):
    """Basit bir Donut grafik (QPainter ile)."""
    def __init__(self, title, percent, color="#3b82f6"):
        super().__init__()
        self.title = title
        self.percent = percent
        self.color = color
        self.setMinimumSize(140, 140)

    def set_data(self, percent):
        self.percent = percent
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        
        # Merkez
        cx, cy = rect.center().x(), rect.center().y()
        radius = min(rect.width(), rect.height()) / 2 - 10
        thickness = 12
        
        # Arka plan halkası
        p.setPen(QPen(QColor("#e2e8f0"), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawEllipse(QPointF(cx, cy), radius, radius)
        
        # Dolu kısım
        p.setPen(QPen(QColor(self.color), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        # 0 derece saat 3'te, -90 saat 12'de
        span_angle = int(-self.percent * 3.6 * 16)
        p.drawArc(int(cx-radius), int(cy-radius), int(radius*2), int(radius*2), 90*16, span_angle)
        
        # Ortadaki yazı
        p.setPen(QColor("#1e293b"))
        f = p.font(); f.setBold(True); f.setPixelSize(18); p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"%{int(self.percent)}")
        
        # Alt başlık
        f.setPixelSize(10); f.setBold(False); p.setFont(f)
        r2 = QRectF(rect)
        r2.moveTop(20)
        p.setPen(QColor("#64748b"))
        p.drawText(r2, Qt.AlignmentFlag.AlignCenter, self.title)

class DashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(180) # Sabit yükseklik, çok yer kaplamasın
        
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 5, 0, 10)
        lay.setSpacing(15)
        
        # Kartlar
        self.card_student = InfoCard("Toplam Öğrenci", "0", "👥", "Aktif Kayıtlı", "#4facfe", "#00f2fe")
        self.card_hw = InfoCard("Bu Hafta Ödev", "0", "📚", "Verilen Küme Sayısı", "#43e97b", "#38f9d7")
        self.card_perf = InfoCard("Başarı Ort.", "%0", "🔥", "Son 7 Gün", "#fa709a", "#fee140")
        
        # Grafik
        self.chart = SimpleDonutChart("Genel Tamamlama", 0, "#3b82f6")
        
        # Layout
        lay.addWidget(self.card_student, 1)
        lay.addWidget(self.card_hw, 1)
        lay.addWidget(self.card_perf, 1)
        # Grafik biraz daha sağda dursun
        # lay.addSpacing(10)
        lay.addWidget(self.chart)
        
        # Timer ile başlatınca yükle (veritabanı kasmasın)
        QTimer.singleShot(100, self.refresh)

    def refresh(self):
        try:
            con = db.get_conn()
            
            # Öğrenci Sayısı
            total_students = con.execute("SELECT COUNT(*) FROM ogrenci").fetchone()[0]
            
            # Bu hafta verilen ödev kümeleri
            hafta_basi = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            hw_count = con.execute("SELECT COUNT(*) FROM odev_kume WHERE verilis_tarihi >= ?", (hafta_basi,)).fetchone()[0]
            
            # Genel Performans (Tüm zamanlar yerine son 30 gün daha anlamlı olabilir ama basit tutalım)
            # Tamamlanan / Toplam
            stats = con.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN LOWER(COALESCE(durum,'')) IN ('yapildi', 'tamam') THEN 1 ELSE 0 END) as done
                FROM odev
            """).fetchone()
            
            done = stats[1] if stats and stats[1] else 0 # stats['done'] Row factory yoksa index ile al
            total = stats[0] if stats and stats[0] else 1
            ratio = (done / total) * 100
            
            # UI Güncelle - Artık temiz metodla
            self.card_student.set_value(total_students)
            self.card_hw.set_value(hw_count)
            self.card_perf.set_value(f"%{int(ratio)}")
            
            self.chart.set_data(ratio)
            
        except Exception as e:
            print("Dashboard refresh error:", e)
            # Hata durumunda UI'da da göster (Developer mode)
            self.card_student.set_value("Err")
            print(f"DB Error Details: {e}")
