# V40 – YKS/LGS Tema, Özel Uyarı Kartı, Grafik ve HTML Rapor Teknik Raporu

**Temel paket:** V39 güvenli pilot (V36–V38 dahildir). **Durum:** Kod ve kontrast testleri başarılı; Windows/macOS'ta gerçek GUI kabul testi bekleniyor.

## Somut sorunlar

1. Ana ekrandaki `SimpleDonutChart` ve `_SimpleBarChart` üzerindeki yüzde, gün ve değer yazıları QPainter ile sabit koyu tonlarda çiziliyordu; genel QSS bu kaleme etki etmiyordu. Koyu temada yazı kaybolabiliyordu.
2. Haftalık trend ve özet/grafik kutuları sabit beyaz renk kullanıyordu. Tema değiştirilince güncel renk şemasını takip etmiyordu.
3. Başarı kartı ve günün ipucu gradyanlarında yazı koşulsuz beyazdı. Bazı mavi ve yeşil gradyanlarda bu yeterli kontrast sağlamıyordu. Bazı çiftlerde ise tek başına siyah veya beyaz renk seçmek iki uç için de yeterli değildi.
4. Kritik uyarı panelinde sabit açık renkler, rozet detaylarında sabit siyah metin ve rozet altyazılarında opaklığı düşük renkler vardı.
5. Koçluk karar ve müdahale raporları iç içe açık renkli HTML durum kutuları kullanıyor. Koyu temalı QTextEdit zeminine doğrudan oturtulduklarında miras alınan beyaz yazılar görünmeyebiliyordu.

## Yapılan değişiklikler

- **`ui/dashboard_widget.py`:** Donut ve haftalık bar grafiği çizim kalemleri anlık semantik paletten okunuyor; grafik yüzeyleri, başlıkları ve ortalama yazısı mevcut pencere açıkken tema değişimine tepki veriyor. Geciken ödev ve öğrenci kartlarının tıklama sinyalleri korunuyor.
- **`ui/gamification_widget.py`:** Sağdaki risk paneli ve 0–3 uyarı kartları açık/koyu temaya göre kontrastlı çiziliyor. Rozet detay metni ve düğmesi temayla yenileniyor. Tema geçişi yalnızca son bildirilen istatistik/uyarı listesini yeniden boyar, veritabanına erişmez.
- **`ui/today_priority_strip_v4.py`:** Özet şeridi ve düğmesi temayı dinliyor; veri okuma, zamanlayıcı ve `open_details` sinyali değişmedi.
- **`ui/adaptive_coaching_center_v26.py` ve `ui/adaptive_followup_v11.py`:** Dış pano ve yazı stiline temayla uyum eklendi. Mevcut HTML raporları, güvenli **beyaz rapor kâğıdı** içinde açık metinle gösterilir. Kırmızı/sarı/yeşil status HTML renkleri değiştirilmedi; rapor metni, verisi, buton bağlantıları ve iş mantığı aynıdır.
- **`ui/theme_visual_tokens_v40.py` (yeni):** Gradyanın iki ucunu da WCAG AA 4,5:1 eşik değerine getiren en küçük RGB renk mesafesi yaklaşımı. Yazı tonunu ve gerekirse renk uçlarını seçer.
- **`ui/theme_report_canvas_v40.py` (yeni):** Eski HTML raporları için okunabilir beyaz kâğıt yüzeyi ve açık seçili metin renkleri; native dialoglara veya diğer QTextEdit widgetlarına global müdahale yok.
- **`QA_V40` (yeni):** 33 hazır tema, değişken gradyan, grafik kalemleri, tema dinleyicileri ve HTML rapor izolasyonuna yönelik başsız testler; manuel test listesi.

## Doğrulama

- V40: 33 tema, kritik panel başlığı, semantik temel yüzeyler, sekiz örnek 2-duraklı gradyan; **en az 4,5:1** kontrast kontrolünden geçti.
- V36–V39 regresyon testleri yeniden çalıştırıldı ve başarılı.
- Tüm Python kaynak kodlarının AST sözdizimi geçerli.
- Önceki V39 ile dosya karşılaştırmasında 5 mevcut `.py` dosyası değiştirildi; 2 yardımcı `.py` eklendi. Veritabanı, JSON, offline/senkron, öğrenci/ödev iş dosyaları aynı kaldı.
- **Bu ortamda PyQt6 kurulu olmadığından** Windows/Mac pencereleri açılıp otomatik görsel test yapılmadı. Kullanıcı kabul testi gereklidir.

## Bilinçli kapsam sınırları

- Birbirinden farklı bütün özel Qt diyalogları ve HTML raporları tek tek düzeltilmiş değildir. Yalnızca yukarıdaki ekranlar hedeflendi.
- HTML raporlarında **tam koyu HTML şablonu** yapılmadı. İçerikteki sabit renkleri agresif biçimde değiştirmek risk durumlarını belirsizleştireceği için beyaz kâğıt görünümü korundu.
- PDF çıktıları, özel grafik çizimleri ve işletim sisteminin kendi açılır dosya diyalogları ayrıca incelenmelidir.
- **Canlı projede doğrudan üzerine yazma yerine izole test klasörü** önerilir.
