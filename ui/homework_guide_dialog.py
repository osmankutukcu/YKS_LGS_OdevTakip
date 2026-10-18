"""Ödev Takip Formu, Öğrenci 360°, Adaptif Koçluk ve Karar Masası Kapsamlı Kullanım Rehberi."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from ui.theme import register_theme_listener, _contrast_safe_background
from ui.theme_tokens_v37 import semantic_palette
from ui.theme_special_v42 import legible_accent
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QTabWidget, QTextBrowser
)


class OdevTakipRehberDialog(QDialog):
    """Kullanıcının tüm modülleri, aralarındaki farkları, somut senaryoları ve

    karar alma mekanizmalarını adım adım anlamasını sağlayan kapsamlı modern rehber.
    """

    def __init__(self, parent=None, initial_tab: int = 0):
        super().__init__(parent)
        self.setWindowTitle("ℹ️ Akıllı Koçluk, Öğrenci 360° ve Ödev Yönetimi Kılavuzu")
        self.setMinimumSize(780, 620)
        self.resize(840, 680)
        self.setModal(True)
        self._initial_tab = initial_tab
        self._init_ui()
        self._on_theme_changed()
        register_theme_listener(self)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # Üst Başlık ve Rozet
        header = QHBoxLayout()
        icon_title = QLabel("🧠 Akıllı Koçluk & Ödev Yönetimi Karar Destek Rehberi")
        icon_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0f172a;")
        self._theme_header = icon_title
        header.addWidget(icon_title)
        header.addStretch(1)

        badge = QLabel("V35 · Pedagojik Karar Modeli")
        badge.setStyleSheet("""
            font-size: 11px; font-weight: 700; color: #1d4ed8;
            background: #eff6ff; border: 1px solid #bfdbfe;
            border-radius: 10px; padding: 3px 10px;
        """)
        header.addWidget(badge)
        root.addLayout(header)

        sub_desc = QLabel(
            "Bu rehber; Ödev Takip, Öğrenci 360°, Adaptif Koçluk ve Haftalık Planlama "
            "işlevlerinin ne amaçla, hangi durumda ve nasıl kullanılması gerektiğini somut örneklerle açıklar."
        )
        sub_desc.setWordWrap(True)
        sub_desc.setStyleSheet("font-size: 12px; color: #475569; margin-bottom: 4px;")
        self._theme_subtitle = sub_desc
        root.addWidget(sub_desc)

        # Sekmeli Yapı
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #334155;
                font-weight: 600;
                font-size: 11.5px;
                padding: 8px 14px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1d4ed8;
                font-weight: 700;
                border-bottom: 1px solid #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
            
                color: #15191E;}
        """)

        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        # Sekme 1: Karşılaştırma (360 vs Adaptif Koçluk)
        self.tabs.addTab(self._build_tab_comparison(), "🧭 360° vs Adaptif Koçluk")
        # Sekme 2: Somut Yaşam Senaryoları
        self.tabs.addTab(self._build_tab_scenarios(), "💡 Somut Senaryolar")
        # Sekme 3: Karar Matrisi
        self.tabs.addTab(self._build_tab_matrix(), "🔄 Karar Matrisi")
        # Sekme 4: Form & Yan Panel & Koçluk Masası
        self.tabs.addTab(self._build_tab_screens(), "📋 Ekranlar & Sekmeler")
        # Sekme 5: Güvenlik, İlkeler & Kısayollar
        self.tabs.addTab(self._build_tab_rules(), "⚡ İlkeler & Kısayollar")

        if 0 <= self._initial_tab < self.tabs.count():
            self.tabs.setCurrentIndex(self._initial_tab)

        root.addWidget(self.tabs, 1)

        # Alt Kapat Butonu
        footer = QHBoxLayout()
        tip_lbl = QLabel("💡 İpucu: Ödev formunda 'F5' ile listeyi tazeleyebilir, 'Ctrl+S' ile kaydedebilirsiniz.")
        tip_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-style: italic;")
        self._theme_footer = tip_lbl
        footer.addWidget(tip_lbl)
        footer.addStretch(1)

        btn_close = QPushButton("Anladım, Kapat")
        btn_close.setFixedHeight(30)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #2563eb; color: white; font-weight: 700;
                font-size: 12px; border-radius: 6px; padding: 4px 22px; border: none;
            }
            QPushButton:hover { background: #1d4ed8; 
                color: #FFFFFF;}
        """)
        self._theme_close_btn = btn_close
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        root.addLayout(footer)

    def _on_theme_changed(self):
        c = semantic_palette()
        strong = c['fg']
        muted = legible_accent(c['bg'], '#94A3B8' if c['dark'] else '#64748B')
        self.setStyleSheet(f"QDialog {{background:{c['bg']}; color:{strong};}}")
        self._theme_header.setStyleSheet(
            f"font-size:16px; font-weight:800; color:{strong};")
        self._theme_subtitle.setStyleSheet(
            f"font-size:12px; color:{muted}; margin-bottom:4px;")
        self._theme_footer.setStyleSheet(
            f"font-size:11px; color:{muted}; font-style:italic;")
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{background:#FFFFFF; border:1px solid {c['border']};
                border-radius:8px; top:-1px;}}
            QTabBar::tab {{background:{c['alt']}; color:{c['alt_fg']};
                font-weight:600; font-size:11.5px; padding:8px 14px;
                border:1px solid {c['border']}; margin-right:3px;}}
            QTabBar::tab:selected {{background:#FFFFFF; color:#172033;
                font-weight:700; border-bottom:1px solid #FFFFFF;}}
            QTabBar::tab:hover:!selected {{background:{c['tab_hover']};
                color:{c['tab_hover_fg']};}}
        """)
        button_bg = _contrast_safe_background(c['primary'], '#FFFFFF')
        hover_bg = _contrast_safe_background(c['btn_hover'], '#FFFFFF')
        self._theme_close_btn.setStyleSheet(f"""
            QPushButton {{background:{button_bg}; color:#FFFFFF;
                font-weight:700; font-size:12px; border-radius:6px;
                padding:4px 22px; border:none;}}
            QPushButton:hover {{background:{hover_bg}; color:#FFFFFF;}}
        """)

    def _create_scroll_page(self, html_content: str) -> QWidget:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(html_content)
        browser.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: none;
                padding: 12px 14px;
                color: #1e293b;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                font-size: 12px;
                line-height: 1.5;
            }
        """)
        return browser

    def _build_tab_comparison(self) -> QWidget:
        html = """
        <div style='color: #0f172a;'>
            <h2 style='color: #1e3a8a; font-size: 15px; margin-top: 0;'>
                🧭 Öğrenci 360° ile 🧠 Adaptif Koçluk Arasındaki Temel Farklar
            </h2>
            <p>
                Programda iki özellik de öğrenciyi analiz eder; ancak <b>amaçları</b>, <b>zaman pencereleri</b> 
                ve <b>öğretmene sundukları sorular</b> birbirinden tamamen farklıdır:
            </p>

            <table border='0' cellspacing='0' cellpadding='8' style='width: 100%; border-collapse: collapse; margin: 12px 0;'>
                <tr style='background-color: #f1f5f9; color: #0f172a; font-weight: 700; border-bottom: 2px solid #cbd5e1;'>
                    <th style='text-align: left; width: 22%; border: 1px solid #cbd5e1;'>Kriter</th>
                    <th style='text-align: left; width: 39%; border: 1px solid #cbd5e1; color: #0d9488;'>🧭 Öğrenci 360° (Makro Röntgen)</th>
                    <th style='text-align: left; width: 39%; border: 1px solid #cbd5e1; color: #2563eb;'>🧠 Adaptif Koçluk (Mikro Eylem)</th>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0;'>
                    <td style='font-weight: 700; border: 1px solid #cbd5e1; background: #f8fafc;'>Cevap Aradığı Temel Soru</td>
                    <td style='border: 1px solid #cbd5e1;'><i>"Öğrenci bugüne kadar ne yaptı? Genel alışkanlıkları ve karnesi nedir?"</i></td>
                    <td style='border: 1px solid #cbd5e1;'><i>"Öğrenci bu konuyu GERÇEKTEN öğrendi mi? Bir sonraki ödev/adım ne olmalı?"</i></td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0; background: #fcfdfe;'>
                    <td style='font-weight: 700; border: 1px solid #cbd5e1; background: #f8fafc;'>Zaman Ölçeği</td>
                    <td style='border: 1px solid #cbd5e1;'><b>Geniş Açı / Tarihsel Geçmiş</b><br>(Haftalar, aylar, tüm dönem)</td>
                    <td style='border: 1px solid #cbd5e1;'><b>Anlık & Gelecek Eylem</b><br>(Bugün, bu ders, sıradaki ödev)</td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0;'>
                    <td style='font-weight: 700; border: 1px solid #cbd5e1; background: #f8fafc;'>Kullandığı Veri</td>
                    <td style='border: 1px solid #cbd5e1;'>Ödev teslim oranları (%), deneme sınavı netleri, geçmiş kitaplar, veli notları.</td>
                    <td style='border: 1px solid #cbd5e1;'>Bağımsız mini yoklamalar (D/Y/B), hata analizi türü, Ebbinghaus unutma gün sayısı.</td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0; background: #fcfdfe;'>
                    <td style='font-weight: 700; border: 1px solid #cbd5e1; background: #f8fafc;'>Ne Zaman Açmalıyım?</td>
                    <td style='border: 1px solid #cbd5e1;'>Veli toplantısı öncesi, aylık durum değerlendirmesi, öğrenci ilk geldiğinde.</td>
                    <td style='border: 1px solid #cbd5e1;'>Masa başında yeni ödev verirken, ders anlatırken, alt kazanım eksiği ararken.</td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0;'>
                    <td style='font-weight: 700; border: 1px solid #cbd5e1; background: #f8fafc;'>Ödev Tiklerine Bakışı</td>
                    <td style='border: 1px solid #cbd5e1;'>Tik = "Ödev yapıldı / görev tamamlandı" olarak kaydeder.</td>
                    <td style='border: 1px solid #cbd5e1;'><b>Tik ≠ Öğrenme!</b> Ödev yapılmış olsa bile bağımsız kanıt yoksa 'Ölçüm Gerekli' der.</td>
                </tr>
            </table>

            <div style='background: #f0fdf4; border-left: 4px solid #16a34a; padding: 10px 14px; border-radius: 4px; margin-top: 14px;'>
                <b>💡 Altın Kural:</b> Önce <b>Öğrenci 360°</b> ile öğrencinin genel resmini ve alışkanlıklarını görün; 
                ardından <b>Adaptif Koçluk</b> ile bugün öğrenciye hangi konudan nasıl bir ödev veya takviye vereceğinizi kesinleştirin.
            </div>
        </div>
        """
        return self._create_scroll_page(html)

    def _build_tab_scenarios(self) -> QWidget:
        html = """
        <div style='color: #0f172a;'>
            <h2 style='color: #1e3a8a; font-size: 15px; margin-top: 0;'>
                💡 Somut Örneklerle Koçluk Senaryoları
            </h2>
            <p>Sistemin arkasındaki mantığı anlamak için şu üç gerçek öğretmen senaryosunu inceleyin:</p>

            <!-- Senaryo 1 -->
            <div style='background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 14px;'>
                <div style='font-weight: 800; color: #dc2626; font-size: 13px; margin-bottom: 6px;'>
                    📌 SENARYO 1: Ali (Ödevini Eksiksiz Teslim Etti Ama Konuyu Anlamadı)
                </div>
                <ul style='margin: 0; padding-left: 20px;'>
                    <li><b>Olay:</b> Ali (LGS 8. sınıf), "lgs_fen / Asitler ve Bazlar" test ödevini %100 tamamladı ve öğretmene getirdi.</li>
                    <li><b>Öğrenci 360° Nasıl Görür?:</b> Ödev tamamlama grafiği %100 ve yeşildir. Öğrenci görevini yapmış görünür.</li>
                    <li><b>Adaptif Koçluk Nasıl Görür?:</b> Sistem <i>'Ölçüm Gerekli'</i> uyarısı verir. Çünkü evde çözülen testte kopya çekilmiş, video çözümünden bakılmış veya şıklar tahmin edilmiş olabilir.</li>
                    <li><b>Öğretmenin Eylemi:</b> Öğretmen derste Ali'ye 6 soruluk bağımsız bir mini yoklama uygular. Ali 2 doğru, 4 yanlış yapar. Hata nedeni olarak <i>'Kavram Yanılgısı - Asit/Baz Ayıraçları'</i> girilir.</li>
                    <li><b>Sistemin Karar Desteği:</b> Sistem Ali'ye anında <b>'Hedefli Destek'</b> sinyali üretir ve öğretmene der ki: <i>'Yeni konu olan Maddenin Isı ile Etkileşimi'ne geçmeyin; önce Ayıraçlar alt kazanımına odaklı 8 soru çözdürün.'</i></li>
                    <li><b>Sonuç:</b> Ali konuyu anlamadan bir sonraki konunun altında ezilmekten kurtarılır.</li>
                </ul>
            </div>

            <!-- Senaryo 2 -->
            <div style='background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 14px;'>
                <div style='font-weight: 800; color: #d97706; font-size: 13px; margin-bottom: 6px;'>
                    📌 SENARYO 2: Zeynep (Konuyu Biliyor Ama 3 Hafta Geçti — Unutma Eğrisi)
                </div>
                <ul style='margin: 0; padding-left: 20px;'>
                    <li><b>Olay:</b> Zeynep (YKS 11. sınıf), 1 ay önce 'Fonksiyonlar' konusunu çok iyi öğrendi ve denemede ful yaptı. Fakat son 3 haftadır fonksiyon çözmedi.</li>
                    <li><b>Öğrenci 360° Nasıl Görür?:</b> Fonksiyonlar konusu tamamlanmış ve başarılı görünür.</li>
                    <li><b>Adaptif Koçluk Nasıl Görür?:</b> Ebbinghaus Unutma Eğrisi devreye girer ve yan panelde <b>'Tekrar Kontrolü'</b> sinyali yanar. <i>'24 gündür bu konudan soru çözülmedi; nörolojik unutulma riski yüksek'</i> uyarısı verir.</li>
                    <li><b>Öğretmenin Eylemi:</b> Zeynep'e tüm fonksiyon kitabını baştan çözdürmek öğrenciyi bıktırır ve zaman kaybettirir. Bunun yerine <b>Spiral Ödev Taslağı</b>'ndan %70 Yeni Konu (Polinomlar) + %30 Eski Konu (8 soru Fonksiyon) harmanlayarak ödev verir.</li>
                    <li><b>Sonuç:</b> Öğrenci sıkılmadan eski konuyu taze tutar ve gerçek kalıcı öğrenme sağlanır.</li>
                </ul>
            </div>

            <!-- Senaryo 3 -->
            <div style='background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px;'>
                <div style='font-weight: 800; color: #7c3aed; font-size: 13px; margin-bottom: 6px;'>
                    📌 SENARYO 3: Mehmet (Aşırı Ödev Yükü ve Bilişsel Kilitlenme)
                </div>
                <ul style='margin: 0; padding-left: 20px;'>
                    <li><b>Olay:</b> Mehmet'in üzerinde farklı derslerden 18 teslim edilmemiş açık ödev birikmiştir. Mehmet paniklemiş ve ödev yapmayı tamamen bırakmıştır.</li>
                    <li><b>Adaptif Koçluk Nasıl Görür?:</b> 'Tıkanıklık Analizi' sekmesinde <b>'Bilişsel Aşırı Yük'</b> alarmı verir.</li>
                    <li><b>Sistemin Karar Desteği:</b> <i>'Öğrenciye bu hafta yeni ödev yazmayın! Açık ödevlerden en eskilerini seyreltin veya iptal edin; kalanları 3 güne dengeli yayın.'</i></li>
                    <li><b>Sonuç:</b> Öğrenci suçluluk ve kilitlenme psikolojisinden kurtarılıp yeniden çalışma masasına döndürülür.</li>
                </ul>
            </div>
        </div>
        """
        return self._create_scroll_page(html)

    def _build_tab_matrix(self) -> QWidget:
        html = """
        <div style='color: #0f172a;'>
            <h2 style='color: #1e3a8a; font-size: 15px; margin-top: 0;'>
                🔄 Adım Adım Karar Matrisi: Hangi Durumda Nereye Bakmalı?
            </h2>
            <p>Günlük öğretmenlik pratiğinizde hangi ekrana ne zaman başvuracağınızın net haritası:</p>

            <table border='0' cellspacing='0' cellpadding='8' style='width: 100%; border-collapse: collapse; margin-top: 10px;'>
                <tr style='background-color: #f1f5f9; color: #0f172a; font-weight: 700; border-bottom: 2px solid #cbd5e1;'>
                    <th style='width: 32%; text-align: left; border: 1px solid #cbd5e1;'>Öğretmenin Karşılaştığı Durum</th>
                    <th style='width: 28%; text-align: left; border: 1px solid #cbd5e1;'>Hangi Ekran Açılmalı?</th>
                    <th style='width: 40%; text-align: left; border: 1px solid #cbd5e1;'>Ekranda Neye Bakılmalı?</th>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0;'>
                    <td style='border: 1px solid #cbd5e1; font-weight: 600;'>1. Veli toplantısı var veya öğrencinin genel karnesini konuşacaksınız.</td>
                    <td style='border: 1px solid #cbd5e1; color: #0d9488; font-weight: 700;'>🧭 Öğrenci 360°</td>
                    <td style='border: 1px solid #cbd5e1;'>Toplam teslim oranı (%), deneme neti gelişim grafiği, veli iletişim notları.</td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0; background: #fcfdfe;'>
                    <td style='border: 1px solid #cbd5e1; font-weight: 600;'>2. Masa başında öğrenciye yeni ödev yazıyorsunuz.</td>
                    <td style='border: 1px solid #cbd5e1; color: #2563eb; font-weight: 700;'>📋 Ödev Takip Formu + Sağ Adaptif Panel</td>
                    <td style='border: 1px solid #cbd5e1;'>Sağ paneldeki <b>'Öneriler'</b> ve <b>'Tekrar'</b> sekmelerine bakarak unutulan veya eksik konudan ödev seçilir.</td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0;'>
                    <td style='border: 1px solid #cbd5e1; font-weight: 600;'>3. Bir öğrencinin konuyu gerçekten anlayıp anlamadığını tespit etmek istiyorsunuz.</td>
                    <td style='border: 1px solid #cbd5e1; color: #7c3aed; font-weight: 700;'>🧠 Koçluk Masası & Kazanım Teşhisi</td>
                    <td style='border: 1px solid #cbd5e1;'>Derste çözülen 5–8 soruluk mini yoklamanın D/Y/B sayıları ve hata nedeni girilir.</td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0; background: #fcfdfe;'>
                    <td style='border: 1px solid #cbd5e1; font-weight: 600;'>4. "Tüm kurumda/sınıfta kime acil müdahale etmeliyim?" diye bakıyorsunuz.</td>
                    <td style='border: 1px solid #cbd5e1; color: #b45309; font-weight: 700;'>🏢 Adaptif Koçluk Merkezi (Kurum Masası)</td>
                    <td style='border: 1px solid #cbd5e1;'>Öğrenci listesindeki <b>'Hedefli destek'</b> ve <b>'Ölçüm gerekli'</b> rozetleri yüksek olan öğrencilere öncelik verilir.</td>
                </tr>
                <tr style='border-bottom: 1px solid #e2e8f0;'>
                    <td style='border: 1px solid #cbd5e1; font-weight: 600;'>5. Öğrenciye haftalık dengeli bir çalışma ve etüt takvimi hazırlıyorsunuz.</td>
                    <td style='border: 1px solid #cbd5e1; color: #0284c7; font-weight: 700;'>📅 Haftalık Çalışma & Akıllı Takvim Planlayıcı</td>
                    <td style='border: 1px solid #cbd5e1;'>Gün gün soru hedefleri, ders blokları ve boş günlerin aşırı yük olmadan dağıtılması.</td>
                </tr>
            </table>
        </div>
        """
        return self._create_scroll_page(html)

    def _build_tab_screens(self) -> QWidget:
        html = """
        <div style='color: #0f172a;'>
            <h2 style='color: #1e3a8a; font-size: 15px; margin-top: 0;'>
                📋 Ekranlar ve Sekmelerin Anlamı
            </h2>

            <h3 style='color: #2563eb; font-size: 13px; margin-bottom: 4px;'>
                1. Ödev Takip Formu — Sağ Yan Panel Sekmeleri (Adaptive Homework Sidebar):
            </h3>
            <ul style='margin-top: 4px;'>
                <li><b>Genel Bakış:</b> Seçili öğrencinin açık ödev yükünü, toplam ödevlerini ve haftalık hedefini tek ekranda özetler.</li>
                <li><b>Öneriler:</b> Sistemin kural tabanlı motoru tarafından tespit edilen en acil pedagojik adımlar (örn: <i>'lgs_fen / Asitler ve Bazlar konusunda bağımsız ölçüm yap'</i>).</li>
                <li><b>Tekrar (Aralıklı Tekrar):</b> Öğrencinin üzerinden 7, 14 veya 30 gün geçmiş konuları. Yeni ödev verirken buradan 8-10 soruluk bir tekrar seçebilirsiniz.</li>
                <li><b>Tıkanıklık:</b> Öğrencinin açık ödev sayısı kritik seviyeyi aştığında veya ders çalışmayı kilitleyen bir durum olduğunda uyarı verir.</li>
            </ul>

            <h3 style='color: #0d9488; font-size: 13px; margin-bottom: 4px;'>
                2. Öğrencinin Koçluk Masası Sekmeleri (Adaptive Coaching Dialog):
            </h3>
            <ul style='margin-top: 4px;'>
                <li><b>🎯 Koç Karar Masası:</b> Öğrencinin genel teşhisi, hedef neti ve sıradaki en yararlı öğretmen müdahalesi.</li>
                <li><b>📊 Öğrenme Panosu:</b> Konu konu çözülen soru sayıları, başarı yüzdeleri ve kanıt seviyeleri (Yetersiz, Gözlem, Ölçülmüş, Pekiştirilmiş).</li>
                <li><b>📝 Kazanım Teşhisi:</b> Öğretmenin 5–8 soruluk mini yoklama ve hata nedenlerini girdiği tanı ekranı.</li>
                <li><b>🌀 Spiral Ödev Taslağı:</b> %70 yeni konu + %30 geçmiş aralıklı tekrar harmanlanmış hazır ödev taslağı önerir.</li>
                <li><b>🛑 Tıkanıklık Analizi:</b> Bilişsel aşırı yük, zaman yönetimi veya sınav kaygısı blokajlarını takip ve telafi eder.</li>
            </ul>
        </div>
        """
        return self._create_scroll_page(html)

    def _build_tab_rules(self) -> QWidget:
        html = """
        <div style='color: #0f172a;'>
            <h2 style='color: #1e3a8a; font-size: 15px; margin-top: 0;'>
                ⚡ İlkeler, Kısayollar ve Sistem Güvenliği
            </h2>

            <div style='background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px; margin-bottom: 12px;'>
                <b style='color: #1e40af;'>🛡️ 1. Öğretmen İradesi İlkesi (Teacher-in-the-Loop):</b><br>
                Sistem hiçbir zaman öğretmenin onayı olmadan kendi kafasına göre öğrenciye ödev yazmaz, mevcut ödevi silmez veya tarihini değiştirmez. 
                Tüm öneriler salt-okunurdur ve öğretmenin onayına sunulur.
            </div>

            <div style='background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px; margin-bottom: 12px;'>
                <b style='color: #15803d;'>🔒 2. LGS ve YKS Müfredat İzolasyonu:</b><br>
                LGS öğrencilerine (8. sınıf vb.) asla AYT/TYT lise dersleri gelmez. Aynı şekilde YKS öğrencilerine LGS konuları önerilmez. 
                Sistem öğrencinin grubunu sıkı bir şekilde izole eder.
            </div>

            <div style='background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 10px; margin-bottom: 12px;'>
                <b style='color: #b45309;'>💾 3. Windows Yetki Güvenliği:</b><br>
                Program C:\\Program Files altında çalışsa dahi, kullanıcı verileri ve profiller standart kullanıcı izinleriyle yazılabilen 
                güvenli uygulama alanında (<i>%LOCALAPPDATA%\\YKS_LGS_HomeworkManager</i>) saklanır; yetki hatası vermez.
            </div>

            <h3 style='color: #334155; font-size: 13px;'>⌨️ Hızlı Kısayol Tuşları:</h3>
            <ul>
                <li><b>F5 (Getir):</b> Öğrenci ders, kitap ve ödev havuzunu anında tazeleyip ekrana yükler.</li>
                <li><b>Ctrl+S (Kaydet):</b> Seçilen ve düzenlenen ödevleri anında veritabanına kaydeder.</li>
                <li><b>F2 (Kontrol Et):</b> Ödev kontrol ve değerlendirme tablosunu açar.</li>
            </ul>
        </div>
        """
        return self._create_scroll_page(html)
