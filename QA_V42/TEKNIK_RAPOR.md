# YKS/LGS Ödev Takip — V42 Özel Bileşenler ve Ekran Renk Bütünlüğü

**Temel:** V41 kaynakları (V36–V41 birikimli değişiklikler korunur).  
**Statü:** Güvenli **pilot**. İşlevsel uygulama/kullanıcı kabul testleri yapılmadan üretim sürümü değildir.

## Bu turda doğrulanan somut sorunlar

1. Haftalık plan zaman çizelgesinde `QPainter` ile doğrudan çizilen koyu başlık, saat, kapasite ve lejant yazıları, koyu temaya duyarlı değildi. QSS tek başına bu renkleri düzeltemiyordu.
2. Mini ödev tamamlama göstergesi koyu yazıları yerel olarak çiziyor, zemin rengini sabitlemiyordu.
3. Performans tablosu trend delegate'i bazı değerlerde **hiç arka plan çizmeden beyaz yazı** kullanıyordu. Bu özellikle açık temalarda görünmezlik riskiydi. Diğer yüzde delegate'i ise renkli çubuk üzerinde sabit koyu metin kullanıyordu.
4. Güncelleme penceresinde açık tema sabit renkleri, metin–zemin tutarsızlığı ve ayrıca hatalı fazladan kapanış süslü parantez içeren bir QSS bölümü tespit edildi.
5. Kılavuz ve Akıllı Sihirbaz'daki HTML okuma alanları ile bazı açık arka planlı giriş alanlarında metin rengi açıkça eşlenmemişti; koyu temadan yazı miras alma riski vardı.
6. Öğrenci 360° yardımcı yan paneli, ana tema değişse de açık sabit yüzeyde kalabiliyordu.

## Uygulanan değişiklikler

| Konum | Görsel düzeltme | Korunan işlev |
| --- | --- | --- |
| `ui/theme_special_v42.py` (yeni) | Ortak renk/kontrast hesaplayıcısı | Qt GUI / veri bağımlılığı yok |
| `ui/plan_settings_dialog.py` | Takvim çiziminde aktif tema; renkli okul/kurs işaretleri; canlı tema yenileme | Plan aralıkları ve takvim hesapları |
| `ui/odev_kontrol.py` | Mini istatistikler için opak tema yüzeyi ve okunur metin | Ödev toplamları ve yüzdeler |
| `ui/performans_paneli.py` | Opak %/trend etiket alanları, kontrastlı yazı ve durum renkleri | Tablo verileri, yüzde, işaretlerin anlamı ve raporlama |
| `ui/update_dialog.py` | Renk uyumlu pencere, düğme, ilerleme çubuğu; hatalı QSS kapanışı düzeltildi | İndirme/kurma ve iptal iş akışı |
| `ui/homework_guide_dialog.py` | Sekme, başlık ve düğme paleti; HTML rapor için beyaz belge | Kılavuz içerikleri ve sekme düzeni |
| `ui/smart_wizard_dialog.py` | Beyaz giriş alanlarına yazı rengi, 7 HTML okuma alanına açık belge yüzeyi; tema güncelleme | Koçluk/ödev analizi, seçim, mesaj/kopyalama |
| `ui/student_workspace_panel_v21.py` | Yan panel kabuğu tema uyumu, raporun açık kağıt görünümü korunur | Öğrenci 360° kanıt, yazma ve senkronizasyon yolları |

## Test kanıtı ve sınırlar

- **33 hazır tema × zaman çizelgesi/yüzde/trend için toplam 858 metin–zemin kontrast eşleşmesi:** ≥4,5:1, başarılı.
- V36, V37, V38, V39, V40, V41'in mevcut başsız kontrolleri tekrar çalıştırıldı; başarılı.
- Toplam **501 Python kaynak dosyası** sözdizimi kontrolünden geçti.
- V41'e göre yalnızca **7 mevcut arayüz `.py` dosyası** değişti, **1 Qt bağımsız yardımcı modül** eklendi. Ayrıca QA ve bu rapor eklendi.
- `.db`, `.sqlite`, `.json`, `.xlsx` veri dosyaları değiştirilmedi. Başsız testler gerçek öğrenci kaydına yazmadı.
- **Bu ortamda PyQt6 bulunmadığından uygulamanın gerçek GUI'si açılıp test edilmedi.** Buradaki başarı kontrast hesapları ve kodun yapısal tutarlılığı içindir; bütün ekranların hatasızlığını kanıtlamaz.

## Kalan riskler ve V43

- Diğer modüllerde hâlâ yüzlerce yerel `setStyleSheet()` ile özel HTML/QPainter renk tanımı var. V42 bunların **tamamını** otomatik düzeltmez; otomatik toplu dönüşüm veri/durum renklerini bozabilir.
- PDF/yazdırma çıktılarının sabit beyaz sayfası bilinçli olarak korunmuştur.
- Windows/macOS yerel diyalogları, sistem fontları, farklı ekran ölçekleri ve açık–koyu temanın tüm pencereler açıkken değiştirilmesi, gerçek cihazda doğrulanmalı.
- V43: regresyon test matrisi (tüm ana formlar, bildirimler, sağ tık menüleri, tablolar, kaydırma çubukları ve yardım pencereleri), etkilenmeyen iş akışı testi, son pilot/kararlı sürüm kararı.

**Kurulum:** Çalışan proje üzerine doğrudan kurmayın. Ayrı test klasöründe kullanın. Tam kod ZIP'i font dosyaları olmadan hazırlanmıştır; önceki sağlam kurulumunuzdaki fontları koruyun. Veriler için mevcut yedekleme prosedürünü uygulayın.
