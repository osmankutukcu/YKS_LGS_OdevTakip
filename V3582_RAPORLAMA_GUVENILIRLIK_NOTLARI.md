# KoçPilot 360 – V3.5.82 Rapor Güvenilirliği ve Okunabilirlik (PİLOT)

> Bu **birleşik pilot yama**, orijinal v3.5.80 kaynak sürümü üzerine kurulmak üzere hazırlanmıştır. V3.5.81 Rapor Merkezi dahil edilmiştir; V3.5.81'i ayrıca kurmayın. Bu paket ticari dağıtım / Windows-EXE güncellemesi değildir.

## Kullanıcıya görünen yenilikler

1. **Detaylı Raporlar → Rapor Merkezi:** Önceki pilotun 6 amaç odaklı yönlendirme kartı aynen dahil.
2. **Detaylı Raporlar / Toplu Değerlendirme:** Yüzdelerin **sınav başarısı değil, ödev tamamlanma oranı** olduğu görünür. Kaydı olmayan öğrenci için “—” gösterilir. Kaydı olanların ortalaması, boş kayıtlardan bağımsız hesaplanır. Karttaki öğrenci sayıları seçili filtreyi takip eder.
3. **Örneklem kuralı:** Performans Paneli'nde zaten kullanılan 5 görev eşiği yalnızca ödül ve takip önerisi sınıflandırmasında kullanılır. Oran hesabı veya hiçbir ödev kaydı değişmez. 1/1 tamamlayan öğrenci oranı %100 görür ama şampiyon sayılmaz; 0/0 kaydı olan öğrenci %0 başarısız görünmez.
4. **Veri kalitesi satırı:** Seçili filtrede veri bulunan, hiç görev kaydı bulunmayan ve az sayıda görevi bulunan öğrencilerin sayısı belirtilir.
5. **Sınıf grafiği:** Kaydı olmayan öğrenci %0 çubuğu gibi çizilmez, gerçek sıralama korunan yüzde verilerinden çizilir.
6. **Ders grafiği:** Tüm dersler korunur. Alt grafik kaydırılabilir hale gelir ve yüksekliği ders sayısına uyarlanır; %100 etiketleri grafik kenarının dışına taşmaz. Ders grafiğinin haftalık ödev verisine, öğrenci tablosunun ise tüm kayıtların ödev verisine ait olduğu netleştirilir.
7. **Öğrenci Detayı:** Günlük ilerleme ölçümü yoksa “Veri Yok”; 1–4 geçerli günlük ölçüm varsa “Sınırlı Veri” gösterilir. Koçluk açıklaması tek başına “başarı düşüşü” veya “riskli” diye hüküm vermez. Bu hesaplamalar gerçek yapay zekâ tahmini olmadığından panel başlığı **Veriye Dayalı Koçluk Analizi** olarak düzeltildi.
8. **Bakım:** `report_dashboard.py` içindeki iki aynı isimli `_get_summary_rows` yönteminden erişilemeyen ilk sürüm kaldırıldı. Fiilen çalışan ikinci yöntemin SQL ve filtre mantığı korunuyor. Sınıf filtreli ve aktarılan durumlu senaryolar test edildi.

## Kapsamın sınırları

- Sadece raporlama arayüzleri ve **salt okuma/yorumlama** yardımcıları değiştirildi. Veri yazma yok, DB şema göçü yok.
- `main_window.py`, Ödev Takip, Ödev Kontrol, `db.py`, orijinal PDF üretim hizmetleri ve korunan kaynaklar **değiştirilmedi**.
- Söz konusu rapor ekranlarındaki farklı veri kaynaklarını bu aşamada zorla ortaklaştırmadık: **Detaylı Raporlar öğrenci tablosu tüm kayıtlara**, ders bazlı grafiği haftalık özet kaynağına bakar; Öğrenci Detayı günlük özetleri kullanır. Veri kaynakları birebir uyumlandırılmadan bu oranların eşit olması beklenmemelidir.
- `0/0` ve `1/1` durumunda PDF üreten **orijinal** hizmetlerin iç rapor hesaplamaları bu yamada değişmedi. PDF'ler için aynı kanıt ayrımı sonraki kontrollü aşamada ele alınmalıdır.
- Öğrenci Detayı'nın `odev` + `odev_satir` eksik kayıt sayımı, kaynak örtüşmeleri açısından ayrıca doğrulanmalıdır. Bu yama sayıları sessizce dönüştürmez.
- Rapor Rehberi'nin iki defa açılması ve Hızlı PDF'de Yazdır + otomatik kaydetme ayrışması, korumalı ana pencere akışında bulunduğundan bilinçli olarak değiştirilmedi.

## Kurulum

1. v3.5.80 kaynak dosyalarınızı ve deneme veritabanınızı yedekleyin.
2. Önce ayrı **test kopyasına** ZIP'deki dosyaları göreli yollarını koruyarak çıkartın. `ui/report_dashboard.py` ve `ui/student_detail.py` orijinal dosyalar üstüne yazılır. `ui/report_center_v3581.py`, `services/report_evidence_v3582.py`, iki test dosyası ve bu not yeni eklenir.
3. **Önceki V3.5.81 yaması bu paketle zaten gelir.** Aynı yama iki kere yüklenmemelidir.
4. `python -m unittest tests.test_report_center_v3581 tests.test_report_evidence_v3582 -v` ile Qt gerektirmeyen kaynak/hakikat testlerini çalıştırın.
5. Mac/Windows uygulamasını gerçek cihazda açarak ekran/tema/dpi, rapor seçimi, sınıf filtresi, PDF üretme/önizleme/yazdırma ve Excel dışa aktarma için elle duman testi yapın.
6. Kontrol edilmesi gereken örnekler: (a) hiç ödevi olmayan öğrenci, (b) 1/1, (c) 0/5, (d) 4/5, (e) 20+ ders listesi, (f) aktarılmış görev ayarı açık/kapalı, (g) 7/14/30 gün aralığı, (h) koyu/açık tema, (i) çoklu öğrenci PDF.

## Testler

- `tests.test_report_center_v3581` + `tests.test_report_evidence_v3582`: 12 başarılı test.
- İlgili önceki performans ve sürüm koruma regresyonları (`test_v14_performance_evidence`, `test_v15_performance_coaching`, `test_v35_release_gate` dahil): toplam 70 başarılı test.
- Python kaynak derleme/AST söz dizimi kontrolleri başarılı. **PyQt6 bu geliştirme ortamında kurulu olmadığı için gerçek GUI, yazıcı veya PDF çıktı testi yapılamadı.** Pilotun gerçek uygulama içinde doğrulanmadan müşteriye dağıtılması önerilmez.

## Sonraki kontrollü geliştirmeler

1. Görev ve gecikme ölçümleri için kaynak uzlaştırması; örtüşen `odev`/`odev_satir` kayıtlarını çift saymayan, aktarılan/gizli kayıtların ayrımını yapan kanonik kural ve ekranlar arası metrik sözlüğü.
2. Orijinal PDF hizmetlerine ayrı şablon sürümü, veri kalitesi notu, örneklem sayısı ve çıktı önizleme ekleme; eski şablonları koruma.
3. Yeni şablonlar: tek sayfa veli karnesi, öğrenci gelişim raporu, sınıf/kurum raporu, telafi raporu. Sadece mevcut kanıtlanan kaynaklardan veri kullanma; eksik kaynakta “veri yok” gösterme.
4. Erişim yetkisi, toplu PDF kaydı/isim güvenliği, veritabanı anlık görüntüsü ve gerçek Windows/Mac kullanıcı testi.
