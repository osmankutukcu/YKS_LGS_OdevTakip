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
        span_angle = int(-self.percent * 3.6 * 16)
        p.drawArc(int(cx-radius), int(cy-radius), int(radius*2), int(radius*2), 90*16, span_angle)
        
        # Ortadaki yazı
        p.setPen(QColor("#1e293b"))
        f = p.font(); f.setBold(True); f.setPixelSize(16); p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"%{int(self.percent)}")


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
            p.fillPath(path, color)
            
            # Etiket (Gün)
            p.setPen(QColor("#64748b"))
            rect_txt = QRectF(float(x) - 5, float(h) - 20, float(bar_width) + 10, 20.0)
            p.drawText(rect_txt, Qt.AlignmentFlag.AlignCenter, day_str)
            
            # Etiket (Değer - Barın üstüne)
            # Sadece yer varsa çizelim
            p.setPen(QColor("#334155"))
            val_rect = QRectF(float(x) - 5, float(y) - 15, float(bar_width) + 10, 15.0)
            p.drawText(val_rect, Qt.AlignmentFlag.AlignCenter, str(int(val)))

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
        lbl_desc = QLabel("Son 7 gündeki ödev tamamlama oranları")
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
        if daily_stats:
            avg = sum(d['val'] for d in daily_stats) / len(daily_stats)
            self.lbl_week_avg.setText(f"%{int(avg)}")
        else:
            self.lbl_week_avg.setText("-")

class DashboardWidget(QWidget):
    sig_open_today = pyqtSignal()
    sig_open_students = pyqtSignal()
    sig_open_overdue = pyqtSignal()
    


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
        
        lbl_chart_title = QLabel("Başarı")
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
        try:
            con = db.get_conn()
            today_str = date.today().strftime("%Y-%m-%d")
            
            # --- 1) AKTİF ÖĞRENCİ SAYISI ---
            try:
                count_std = con.execute("SELECT COUNT(*) FROM ogrenci WHERE aktif = 1").fetchone()[0]
                self.card_students.set_value(f"{count_std}")
            except Exception:
                count_std = 0
                self.card_students.set_value("0")

            # --- EĞER HİÇ AKTİF ÖĞRENCİ YOKSA: TÜM METRİKLERİ TEMİZ VE SIFIR GÖSTER ---
            if count_std == 0:
                self.card_tasks.set_value("0")
                self.card_overdue.set_value("0")
                self.chart.set_data(0)
                
                # Trend grafiğini sıfırla
                days_tr = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
                dt_today = date.today()
                empty_trend = []
                for i in range(6, -1, -1):
                    d = dt_today - datetime.timedelta(days=i)
                    empty_trend.append({'day': days_tr[d.weekday()], 'val': 0})
                self.trend_widget.set_data(empty_trend)
                
                # Rozetleri sıfırla
                empty_stats = {
                    "success_rate": 0,
                    "total_homeworks": 0,
                    "total_students": 0,
                    "streak_days": 0,
                    "weekly_minutes": 0,
                    "alerts": [],
                    "top_worker": None,
                    "top_ratio": None,
                    "top_marathon": None
                }
                if hasattr(self, "badge_widget"):
                    self.badge_widget.refresh_badges(empty_stats)
                    
                # Karşılama İpucu
                self.smart_card.set_insight(
                    "Hoş geldiniz! Sisteme henüz kayıtlı aktif öğrenci bulunmuyor. Sol menüdeki 'Öğrenci Kaydı' bölümünden ilk öğrencilerinizi ekleyerek ödev ve performans takibine başlayabilirsiniz.",
                    "🌱",
                    ("#3b82f6", "#1d4ed8")
                )
                return

            # --- 2) AKTİF ÖĞRENCİLER VARSA İSTATİSTİKLERİ ÇEK ---
            
            # 2.1) BUGÜNKÜ ÖDEVLER (Sadece aktif öğrencilere ait)
            sql_today = """
                SELECT COUNT(DISTINCT k.id) FROM odev_kume k
                JOIN ogrenci o ON o.id = k.ogrenci_id
                WHERE o.aktif = 1 AND k.bitis_tarihi = ?
                AND EXISTS (
                    SELECT 1 FROM odev od 
                    WHERE od.kume_id = k.id 
                    AND (od.durum IS NULL OR lower(od.durum) NOT IN ('yapildi', 'tamam', 'tamamlandı', 'tamamlandi'))
                )
            """
            try:
                count_today = con.execute(sql_today, (today_str,)).fetchone()[0]
                self.card_tasks.set_value(f"{count_today}")
            except Exception:
                count_today = 0
                self.card_tasks.set_value("0")

            # 2.2) GECİKENLER (Sadece aktif öğrencilere ait)
            sql_overdue = """
                SELECT COUNT(DISTINCT k.id) FROM odev_kume k
                JOIN ogrenci o ON o.id = k.ogrenci_id
                WHERE o.aktif = 1 AND k.bitis_tarihi < ? AND k.bitis_tarihi != ''
                AND EXISTS (
                    SELECT 1 FROM odev od 
                    WHERE od.kume_id = k.id 
                    AND (od.durum IS NULL OR lower(od.durum) NOT IN ('yapildi', 'tamam', 'tamamlandı', 'tamamlandi'))
                )
            """
            try:
                count_overdue = con.execute(sql_overdue, (today_str,)).fetchone()[0]
                self.card_overdue.set_value(f"{count_overdue}")
            except Exception:
                count_overdue = 0
                self.card_overdue.set_value("0")
            
            # 2.3) GENEL BAŞARI (Sadece aktif öğrencilere ait)
            total_q = 0
            done_q = 0
            ratio = 0
            try:
                sql_ratio = """
                    SELECT 
                        COUNT(od.id) as total_q,
                        SUM(CASE WHEN lower(od.durum) IN ('yapildi', 'tamam', 'tamamlandı', 'tamamlandi') THEN 1 ELSE 0 END) as done_q
                    FROM odev od
                    JOIN odev_kume k ON k.id = od.kume_id
                    JOIN ogrenci o ON o.id = k.ogrenci_id
                    WHERE o.aktif = 1
                """
                row_r = con.execute(sql_ratio).fetchone()
                if row_r:
                    total_q = row_r[0] or 0
                    done_q = row_r[1] or 0
                    ratio = (done_q / total_q * 100) if total_q > 0 else 0
                self.chart.set_data(ratio)
                
                # Rozet ve Uyarılar güncelleme
                alerts = []
                try:
                    # Gecikenleri isimle çek (Sadece aktif öğrenciler)
                    sql_alerts = """
                        SELECT o.ad, o.soyad, COUNT(k.id) as cnt
                        FROM odev_kume k
                        JOIN ogrenci o ON o.id = k.ogrenci_id
                        WHERE o.aktif = 1 AND k.bitis_tarihi < ? AND k.bitis_tarihi != ''
                        AND EXISTS (
                             SELECT 1 FROM odev od 
                             WHERE od.kume_id = k.id 
                             AND (od.durum IS NULL OR lower(od.durum) NOT IN ('yapildi', 'tamam', 'tamamlandı', 'tamamlandi'))
                        )
                        GROUP BY o.id
                        ORDER BY cnt DESC
                        LIMIT 3
                    """
                    recs = con.execute(sql_alerts, (today_str,)).fetchall()
                    for r in recs:
                        ad = (r[0] or "")
                        soyad = (r[1] or "")
                        tam_ad = f"{ad} {soyad[0]}." if soyad else ad
                        
                        cnt = r[2]
                        sev = "high" if cnt > 5 else "medium"
                        tip = "Acil görüşme planla." if cnt > 5 else "Kısa bir telafi programı oluştur."
                        
                        alerts.append({
                            "text": f"{tam_ad} - {cnt} ödev gecikmiş",
                            "severity": sev,
                            "tip": tip
                        })
                        
                    if not alerts and count_overdue > 0:
                        alerts.append({
                            "text": f"{count_overdue} genel gecikme var",
                            "severity": "medium",
                            "tip": "Listeyi kontrol et."
                        })
                except Exception:
                    pass

                # --- Streak & Dakika Hesabı ---
                streak_days = 0
                weekly_minutes = 0
                try:
                    days_check = [date.today() - datetime.timedelta(days=i) for i in range(14)]
                    qs = ",".join(f"'{d.strftime('%Y-%m-%d')}'" for d in days_check)
                    
                    try:
                        sql_streak = f"""
                            SELECT k.bitis_tarihi, SUM(od.sure)
                            FROM odev_kume k
                            JOIN odev od ON od.kume_id = k.id
                            JOIN ogrenci o ON o.id = k.ogrenci_id
                            WHERE o.aktif = 1 AND k.bitis_tarihi IN ({qs})
                            AND lower(od.durum) IN ('yapildi','tamam','tamamlandı','tamamlandi')
                            GROUP BY k.bitis_tarihi
                        """
                        rows_st = con.execute(sql_streak).fetchall()
                        map_st = {r[0]: (r[1] or 0) for r in rows_st} 
                    except Exception:
                        sql_streak_fallback = f"""
                            SELECT k.bitis_tarihi, COUNT(od.id)
                            FROM odev_kume k
                            JOIN odev od ON od.kume_id = k.id
                            JOIN ogrenci o ON o.id = k.ogrenci_id
                            WHERE o.aktif = 1 AND k.bitis_tarihi IN ({qs})
                            AND lower(od.durum) IN ('yapildi','tamam','tamamlandı','tamamlandi')
                            GROUP BY k.bitis_tarihi
                        """
                        rows_st = con.execute(sql_streak_fallback).fetchall()
                        map_st = {r[0]: (r[1] * 40) for r in rows_st}
                    
                    # Streak
                    current_streak = 0
                    for i in range(14):
                        d_chk = (date.today() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                        if d_chk in map_st and map_st[d_chk] > 0:
                            current_streak += 1
                        elif i == 0:
                            continue
                        else:
                            break
                    streak_days = current_streak
                    
                    # Weekly Minutes (Son 7 gün)
                    d7 = (date.today() - datetime.timedelta(days=6)).strftime("%Y-%m-%d")
                    weekly_minutes = sum(val for d, val in map_st.items() if d >= d7)
                except Exception as e:
                    print("Stats calc error:", e)

                # --- MVP Analizi (Sadece aktif öğrenciler) ---
                top_worker_name = None
                top_worker_count = 0
                
                best_ratio_name = None
                best_ratio_val = 0
                
                try:
                    # 1. En çok ödev yapan (Canavar)
                    sql_top_worker = """
                        SELECT o.ad, COUNT(od.id) as cnt
                        FROM odev od
                        JOIN odev_kume k ON k.id = od.kume_id
                        JOIN ogrenci o ON o.id = k.ogrenci_id
                        WHERE o.aktif = 1 AND lower(od.durum) IN ('yapildi','tamam','tamamlandı','tamamlandi')
                        GROUP BY o.id
                        ORDER BY cnt DESC
                        LIMIT 1
                    """
                    row_w = con.execute(sql_top_worker).fetchone()
                    if row_w and row_w[1] > 0:
                        top_worker_name = row_w[0]
                        top_worker_count = row_w[1]

                    # 2. En yüksek oran (Zirve) - En az 5 ödevi olan aktif öğrenciler
                    sql_best_ratio = """
                        SELECT o.ad, 
                               CAST(SUM(CASE WHEN lower(od.durum) IN ('yapildi','tamam','tamamlandı','tamamlandi') THEN 1 ELSE 0 END) AS FLOAT) / COUNT(od.id) * 100 as ratio
                        FROM odev od
                        JOIN odev_kume k ON k.id = od.kume_id
                        JOIN ogrenci o ON o.id = k.ogrenci_id
                        WHERE o.aktif = 1
                        GROUP BY o.id
                        HAVING COUNT(od.id) >= 5
                        ORDER BY ratio DESC
                        LIMIT 1
                    """
                    row_br = con.execute(sql_best_ratio).fetchone()
                    if row_br:
                        best_ratio_name = row_br[0]
                        best_ratio_val = int(row_br[1])
                except Exception as e:
                    print("MVP Calc Error:", e)

                # --- 3. Maratoncu Analizi (Sadece aktif öğrenciler) ---
                top_marathon_name = None
                top_marathon_min = 0
                try:
                    sql_marathon = """
                        SELECT o.ad, SUM(od.sure) as total_min
                        FROM odev od
                        JOIN odev_kume k ON k.id = od.kume_id
                        JOIN ogrenci o ON o.id = k.ogrenci_id
                        WHERE o.aktif = 1
                        AND lower(od.durum) IN ('yapildi','tamam','tamamlandı','tamamlandi')
                        AND date(k.verilis_tarihi) > date('now', '-7 days')
                        GROUP BY o.id
                        ORDER BY total_min DESC
                        LIMIT 1
                    """
                    row_m = con.execute(sql_marathon).fetchone()
                    if row_m and (row_m[1] or 0) > 0:
                        top_marathon_name = row_m[0]
                        top_marathon_min = row_m[1] or 0
                except Exception:
                    if top_worker_name:
                        top_marathon_name = top_worker_name
                        top_marathon_min = top_worker_count * 40

                g_stats = {
                    "success_rate": int(ratio),
                    "total_homeworks": total_q,
                    "total_students": count_std,
                    "streak_days": streak_days,
                    "weekly_minutes": int(weekly_minutes),
                    "alerts": alerts,
                    "top_worker": {"name": top_worker_name, "val": top_worker_count} if top_worker_name else None,
                    "top_ratio": {"name": best_ratio_name, "val": best_ratio_val} if best_ratio_name else None,
                    "top_marathon": {"name": top_marathon_name, "val": top_marathon_min} if top_marathon_name else None
                }
                if hasattr(self, "badge_widget"):
                    self.badge_widget.refresh_badges(g_stats)

            except Exception as e:
                print("Global Stats Error:", e)
                self.chart.set_data(0)
            
            # --- 2.4) TREND VERİSİ (SON 7 GÜN - Sadece aktif öğrenciler) ---
            dt_today = date.today()
            last_7_days_stats = []
            days_range = [dt_today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
            placeholders = ",".join(f"'{d.strftime('%Y-%m-%d')}'" for d in days_range)
            
            sql_trend = f"""
                SELECT k.bitis_tarihi,
                       COUNT(od.id) as total_hw,
                       SUM(CASE WHEN lower(od.durum) IN ('yapildi','tamam','tamamlandı','tamamlandi') THEN 1 ELSE 0 END) as done_hw
                FROM odev_kume k
                JOIN odev od ON od.kume_id = k.id
                JOIN ogrenci o ON o.id = k.ogrenci_id
                WHERE o.aktif = 1 AND k.bitis_tarihi IN ({placeholders})
                GROUP BY k.bitis_tarihi
            """
            rows_trend = []
            try:
                rows_trend = con.execute(sql_trend).fetchall()
            except Exception:
                pass
            
            trend_map = {}
            for r in rows_trend:
                t_date = r[0]
                total_h = r[1]
                done_h = r[2]
                pct = (done_h / total_h * 100) if total_h > 0 else 0
                trend_map[t_date] = pct
                
            days_tr = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
            
            for d in days_range:
                d_str = d.strftime("%Y-%m-%d")
                d_label = days_tr[d.weekday()]
                val = trend_map.get(d_str, 0)
                last_7_days_stats.append({'day': d_label, 'val': val})
            
            self.trend_widget.set_data(last_7_days_stats)
            
            # --- 2.5) AKILLI ÖNERİ ALGORİTMASI ---
            try:
                from services.trend_analyzer import analyze_performance_trend
                trend_res = analyze_performance_trend(last_7_days_stats)
                
                tip_data = SmartTipGenerator.generate(g_stats, trend_res)
                
                self.smart_card.set_insight(
                    tip_data["text"], 
                    tip_data["icon"],
                    tip_data["colors"]
                )
                        
            except Exception as e:
                print("Insight Error:", e)
                self.smart_card.set_insight("Verileriniz analiz ediliyor...", "⏳")

        except Exception as e:
            print("Dashboard refresh error:", e)
