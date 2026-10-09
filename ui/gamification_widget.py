from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class GamificationWidget(QFrame):
    """
    Tek bir kart içinde bölünmüş Premium Gamification Görünümü:
    [ 🏆 Başarı Rozetleri & İstatistikler (Sol)  |  ⚡ Akıllı Koç Uyarıları (Sağ) ]
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFixedHeight(190) # İçerik sığması için yükseklik artırıldı
        self.setStyleSheet("""
            GamificationWidget {
                background-color: white;
                border-radius: 16px;
                border: 1px solid #e2e8f0;
            }
            QLabel { font-family: 'Segoe UI', sans-serif; }
        """)
        
        # Ana Layout (Yatay)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- SOL TARAF: ROZETLER & İSTATİSTİK ---
        self.left_widget = QWidget()
        self.left_widget.setStyleSheet("#leftWidget { background-color: white; border-top-left-radius: 16px; border-bottom-left-radius: 16px; }")
        self.left_widget.setObjectName("leftWidget")
        
        l_layout = QVBoxLayout(self.left_widget)
        l_layout.setContentsMargins(25, 20, 20, 15)
        l_layout.setSpacing(10)
        
        # Başlık Sol
        header_l = QLabel("🏆 Haftalık Performans & Rozetler")
        header_l.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a; border:none;")
        l_layout.addWidget(header_l)
        
        # Rozet Alanı
        self.badges_layout = QHBoxLayout()
        self.badges_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.badges_layout.setSpacing(12)
        l_layout.addLayout(self.badges_layout)
        
        # Boş mesajı
        self.lbl_empty = QLabel("Henüz analiz edilen veri yok.")
        self.lbl_empty.setStyleSheet("color: #94a3b8; font-style: italic; font-size: 12px; border:none;")
        l_layout.addWidget(self.lbl_empty)
        self.lbl_empty.hide()
        
        l_layout.addStretch()
        
        # --- ARA ÇİZGİ (Ayırıcı) ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #f1f5f9; width: 1px; border:none;")
        line.setFixedWidth(1)
        
        # --- SAĞ TARAF: UYARILAR ---
        self.right_widget = QWidget()
        self.right_widget.setFixedWidth(360) # Sağ taraf sabit genişlik
        self.right_widget.setStyleSheet("""
            #rightWidget {
                background-color: #fff1f2; 
                border-top-right-radius: 16px; 
                border-bottom-right-radius: 16px;
            }
        """)
        self.right_widget.setObjectName("rightWidget")
        
        r_layout = QVBoxLayout(self.right_widget)
        r_layout.setContentsMargins(20, 15, 20, 15)
        r_layout.setSpacing(8)
        
        # Başlık Sağ
        h_right_box = QHBoxLayout()
        icon_r = QLabel("⚡")
        icon_r.setStyleSheet("font-size:16px; border:none;")
        header_r = QLabel("Kritik Uyarılar & Tavsiyeler")
        header_r.setStyleSheet("font-size: 13px; font-weight: 800; color: #9f1239; border:none;")
        h_right_box.addWidget(icon_r)
        h_right_box.addWidget(header_r)
        h_right_box.addStretch()
        r_layout.addLayout(h_right_box)
        
        # Uyarı Listesi Alanı
        self.alerts_layout = QVBoxLayout()
        self.alerts_layout.setSpacing(8)
        r_layout.addLayout(self.alerts_layout)
        
        r_layout.addStretch()
        
        # Başlangıç durumu
        self._refresh_alerts([])

        # Ekleme
        main_layout.addWidget(self.left_widget, 1) # Esnek
        main_layout.addWidget(line)
        main_layout.addWidget(self.right_widget) # Sabit

    def refresh_badges(self, stats):
        """
        stats: { 'success_rate': 92, 'streak_days': 5, 'weekly_minutes': 320, 'alerts': ... }
        """
        # 1. Rozetleri Temizle
        while self.badges_layout.count():
            item = self.badges_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        rate = stats.get("success_rate", 0)
        streak = stats.get("streak_days", 0)
        mins = stats.get("weekly_minutes", 0)
        total_students = stats.get("total_students", None)
        total_hw = stats.get("total_homeworks", 0)
        
        # Öğrenci Bazlı Veriler
        top_worker = stats.get("top_worker", {})
        top_ratio = stats.get("top_ratio", {})
        top_marathon = stats.get("top_marathon", {})
        
        badges_data = []
        
        # A) KÜRESEL BAŞARI ROZETİ (Sadece aktif öğrenci ve ödev verisi varsa)
        if (total_students is None or total_students > 0) and total_hw > 0:
            if rate >= 90: 
                badges_data.append({"icon": "🌟", "title": "Efsane", "subtitle": f"%{rate} Başarı", "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fef9c3, stop:1 #fde047)", "text": "#854d0e"})
            elif rate >= 75: 
                badges_data.append({"icon": "⭐", "title": " Yıldız", "subtitle": f"%{rate} Başarı", "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #dbeafe, stop:1 #93c5fd)", "text": "#1e40af"})
            elif rate >= 50:
                badges_data.append({"icon": "📈", "title": "Gelişiyor", "subtitle": f"%{rate} Başarı", "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d1fae5, stop:1 #6ee7b7)", "text": "#065f46"})
            else:
                badges_data.append({"icon": "🌱", "title": "Başlangıç", "subtitle": f"%{rate} Başarı", "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f1f5f9, stop:1 #cbd5e1)", "text": "#475569"})
        
        # B) Streak (Zincir) Rozeti
        if streak >= 3 and (total_students is None or total_students > 0):
             badges_data.append({"icon": "🔥", "title": "Seri", "subtitle": f"{streak} Gün", "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffedd5, stop:1 #fdba74)", "text": "#9a3412"})
            
        # C) Çalışma Süresi (Maratoncu - En çok süre harcayan öğrenci)
        top_marathon = stats.get("top_marathon", {})
        marathon_min = top_marathon.get("val", 0) if isinstance(top_marathon, dict) else 0
        
        if marathon_min > 600 and (total_students is None or total_students > 0): # 10 Saat barajı
             m_name = top_marathon.get("name", "Sınıf")
             badges_data.append({
                 "icon": "🏃‍♂️", 
                 "title": "Maraton", 
                 "subtitle": f"{m_name}", 
                 "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f3e8ff, stop:1 #d8b4fe)", 
                 "text": "#6b21a8",
                 "desc_val": int(marathon_min/60) # Detayda görünür: "11 Saat"
             })

        # D) Ödev Canavarı (En çok ödev yapan öğrenci)
        if isinstance(top_worker, dict) and top_worker.get('val', 0) > 10 and (total_students is None or total_students > 0):
             name = top_worker.get('name', 'Öğrenci')
             val = top_worker.get('val', 0)
             badges_data.append({
                 "icon": "📚", 
                 "title": "Canavar", 
                 "subtitle": f"{name}", 
                 "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fce7f3, stop:1 #fbcfe8)", 
                 "text": "#831843", 
                 "desc_val": val 
             })

        # E) Zirve (En yüksek başarı oranına sahip öğrenci)
        if isinstance(top_ratio, dict) and top_ratio.get('val', 0) >= 80 and (total_students is None or total_students > 0):
             name = top_ratio.get('name', 'Öğrenci')
             val = top_ratio.get('val', 0)
             badges_data.append({
                 "icon": "🏔️", 
                 "title": "Zirve", 
                 "subtitle": f"{name}", 
                 "grad": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ccfbf1, stop:1 #99f6e4)", 
                 "text": "#042f2e",
                 "desc_val": val
             })
            
        # D) Rozetleri Ekrana Bas
        if badges_data:
            self.lbl_empty.hide()
            for b_data in badges_data:
                self.badges_layout.addWidget(self._create_badge(b_data))
        else:
            self.lbl_empty.setText("Henüz analiz edilen veri yok.")
            self.lbl_empty.show()
            
        # 2. Uyarıları Yenile
        alerts_raw = stats.get("alerts", [])
        clean_alerts = []
        
        for a in alerts_raw:
            if isinstance(a, dict): clean_alerts.append(a)
            else: clean_alerts.append({"text": str(a), "severity": "medium", "tip": ""})
                
        self._refresh_alerts(clean_alerts, total_hw, total_students)

    def _refresh_alerts(self, alerts, total_hw=0, total_students=None):
        while self.alerts_layout.count():
            item = self.alerts_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if not alerts:
            if total_students == 0:
                lbl = QLabel("Aktif öğrenci kaydı bulunmuyor.")
                lbl.setStyleSheet("color: #94a3b8; font-style: italic; font-size: 11px; border:none;")
            elif total_hw == 0:
                lbl = QLabel("Henüz analiz edilecek veri yok.")
                lbl.setStyleSheet("color: #94a3b8; font-style: italic; font-size: 11px; border:none;")
            else:
                lbl = QLabel("✅ Harika! Hiç eksiğin yok.")
                lbl.setStyleSheet("color: #059669; font-weight: 700; font-size: 13px; border:none;")
            
            self.alerts_layout.addWidget(lbl)
            return
            
        # İlk 3 uyarıyı göster
        for i, item in enumerate(alerts[:3]):
            text = item.get("text", "")
            sev = item.get("severity", "medium")
            tip = item.get("tip", "")
            
            # Renk Ayarları (severity'ye göre)
            if sev == "high":
                border_col = "#f43f5e"; bg_col = "#fff"; icon_bg="#ffe4e6"; txt_col = "#881337"
                icon_char = "!"
            else:
                border_col = "#f59e0b"; bg_col = "#fff"; icon_bg="#fef3c7"; txt_col = "#92400e"
                icon_char = "i"

            # Kart Yapısı
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_col};
                    border-radius: 6px;
                    border-left: 4px solid {border_col};
                    border-bottom: 1px solid #e7e5e4;
                }}
            """)
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(10, 8, 10, 8)
            card_lay.setSpacing(10)
            
            # İkon
            icon = QLabel(icon_char)
            icon.setFixedSize(24, 24)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet(f"background-color: {icon_bg}; color: {txt_col}; border-radius: 12px; font-weight: bold; font-size:12px; border:none;")
            
            # Metin
            v_msg = QVBoxLayout()
            v_msg.setSpacing(2)
            v_msg.setContentsMargins(0,0,0,0)
            
            msg_lbl = QLabel(text)
            msg_lbl.setStyleSheet(f"color: #1e293b; font-weight: 600; font-size: 11px; border:none; background:transparent;")
            v_msg.addWidget(msg_lbl)
            
            if tip:
                sub = QLabel(f"💡 {tip}")
                sub.setStyleSheet("color: #64748b; font-size: 10px; border:none; background:transparent;")
                v_msg.addWidget(sub)
            
            card_lay.addWidget(icon)
            card_lay.addLayout(v_msg)
            
            self.alerts_layout.addWidget(card)
            
    def _create_badge(self, data):
        """ Premium Gradient Kart Badge (Clickable) """
        return ClickableBadge(data, parent=self)

class ClickableBadge(QFrame):
    """ Tıklanabilir Rozet Kartı """
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(80, 105)
        
        # Gradient background
        self.setStyleSheet(f"""
            ClickableBadge {{
                background: {data['grad']};
                border: 1px solid {data['text']}30;
                border-radius: 12px;
            }}
            ClickableBadge:hover {{
                border: 1px solid {data['text']};
                margin-top: -2px; /* Hafif yukarı kalkma efekti */
            }}
        """)
        
        v = QVBoxLayout(self)
        v.setContentsMargins(5, 8, 5, 8)
        v.setSpacing(4)
        
        ic = QLabel(data['icon'])
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setStyleSheet("font-size: 28px; background: transparent; border:none;")
        
        tt = QLabel(data['title'])
        tt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tt.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {data['text']}; background: transparent; border:none;")
        
        sub = QLabel(data['subtitle'])
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"font-size: 9px; font-weight: 600; color: {data['text']}bb; background: transparent; border:none;")
        
        v.addWidget(ic)
        v.addWidget(tt)
        v.addWidget(sub)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            dlg = BadgeDetailDialog(self.data, self)
            dlg.exec()
        super().mousePressEvent(event)

from PyQt6.QtWidgets import QDialog, QPushButton, QGraphicsDropShadowEffect

class BadgeDetailDialog(QDialog):
    """
    Rozet Detay Penceresi - Modern, Profesyonel ve Yönlendirici
    """
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{data['title']} Rozeti Detayları")
        self.setFixedSize(400, 500) # Yüksekliği artırdık
        self.setStyleSheet("""
            QDialog { background-color: white; border-radius: 16px; }
            QLabel { font-family: 'Segoe UI', sans-serif; }
        """)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Ana Kapsayıcı (Gölge için)
        main_frame = QFrame(self)
        main_frame.setGeometry(10, 10, 380, 480) # Yüksekliği artırdık
        main_frame.setStyleSheet("background-color: white; border-radius: 16px;")
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0,0,0,50))
        shadow.setOffset(0, 5)
        main_frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- HEADER (Gradient) ---
        header = QFrame()
        header.setFixedHeight(140)
        header.setStyleSheet(f"""
            border-top-left-radius: 16px; 
            border-top-right-radius: 16px;
            background: {data['grad']};
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel(data['icon'])
        icon.setStyleSheet("font-size: 64px; background: transparent;")
        h_lay.addWidget(icon)
        
        layout.addWidget(header)
        
        # --- BODY ---
        body = QWidget()
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(30, 25, 30, 25)
        b_lay.setSpacing(15)
        
        # Başlık ve Alt Başlık
        lbl_title = QLabel(data['title'])
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #1e293b;")
        
        lbl_sub = QLabel(data['subtitle'])
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet("font-size: 14px; font-weight: 600; color: #64748b; margin-bottom: 5px;")
        
        b_lay.addWidget(lbl_title)
        b_lay.addWidget(lbl_sub)
        
        # Ayrıcı Çizgi
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #f1f5f9;")
        b_lay.addWidget(line)
        
        # Akıllı Tavsiye Metni
        # Rozet tipine göre akıllı mesaj üret
        advice_text = self._get_smart_advice(data)
        
        lbl_advice = QLabel(advice_text)
        lbl_advice.setWordWrap(True)
        lbl_advice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_advice.setStyleSheet("font-size: 14px; line-height: 1.5; color: #475569;")
        b_lay.addWidget(lbl_advice)
        
        b_lay.addStretch()
        
        # Kapat Butonu
        btn_close = QPushButton("Harika, Devam Et! 🚀")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btn_close.setFixedHeight(45)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {data.get('text', '#334155')};
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 10px;
                border: none;
            }}
            QPushButton:hover {{ opacity: 0.9; margin-top: -1px; }}
            QPushButton:pressed {{ margin-top: 1px; }}
        """)
        b_lay.addWidget(btn_close)
        
        layout.addWidget(body)

    def _get_smart_advice(self, data):
        title = data['title']
        sub = data.get('subtitle', '')
        val = data.get('desc_val', '')
        
        if "Efsane" in title or "Mükemmel" in title:
            return "🔥 <b>Genel Performans Harika!</b><br>Tüm sınıfın ortalaması çok yüksek. Bu disiplinli çalışma temposunu korumaları çok önemli."
        elif "Yıldız" in title or "İyi İş" in title:
            return "⭐ <b>Sınıf İyi Gidiyor!</b><br>Genel başarı %75 üzerinde. Eksik kalan öğrencileri belirleyip onlara odaklanırsan 'Efsane' seviyesine çıkabiliriz."
        elif "Gelişiyor" in title:
            return "📈 <b>Gelişim Var.</b><br>Sınıfın genel durumu toparlanıyor. Henüz %75 barajının altındayız, takibi sıkılaştırmakta fayda var."
        elif "Seri" in title:
            return "⛓️ <b>İstikrarlı Günler!</b><br>Son 3 gündür kesintisiz ödev girişi/tamamlaması yapılıyor. Bu alışkanlığı korumak çok değerli."
        elif "Maraton" in title:
            return f"🏃‍♂️ <b>{sub} Durmuyor!</b><br>Son 7 günde yaklaşık <b>{val} saat</b> çalışma süresiyle sınıfın en dayanaklısı oldu. Dinlenmeyi de unutmasın."
        elif "Canavar" in title:
            return f"📚 <b>{sub} Durdurulamıyor!</b><br>Toplam <b>{val}</b> ödevi tamamlayarak sınıfın en çalışkanı oldu. Onu tebrik etmeyi unutma! 👏"
        elif "Zirve" in title:
            return f"🏔️ <b>{sub} Zirvede!</b><br>Tamamlama oranı <b>%{val}</b> ile sınıfın en verimli öğrencisi. Bu başarı taktiğini diğerleriyle paylaşmasını isteyebilirsin."
        else:
            return "🌱 <b>Yeni Hafta, Yeni Hedefler!</b><br>Henüz yeterli veri oluşmadı. Ödev girişlerini düzenli yaparak grafikleri canlandırabilirsin."
