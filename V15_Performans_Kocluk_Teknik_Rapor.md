# YKS/LGS Ödev Takip – V15 Performans Paneli / Deneme ve Koçluk Teknik Raporu

**Tarih:** 12 Ekim 2026  
**Baz alınan kaynak:** `OdevTakip_V14_Performans_Paneli_Kumulatif_Veriler_Haric_Kaynak.zip` (v3.5.16/V13.6 tabanlı).  
**Çalışan Mac ekranı:** v3.5.17; bu sürümün tüm kaynak farkları elimizde olmadığı için onun üzerine doğrudan yükleme yapılmamalıdır.

## Amaç ve neden

Mevcut V14 ödev takibi yüzdesi öğrenme kazanımı/net değildir. Farklı sınavları karşılaştırmak, kayıtlı olmayan soru sayılarını tahmin etmek ve öğrencinin farklı çalışma durumlarını tek bir başarı puanına dönüştürmek gerçekçi olmaz. V15, deneme sonuçlarını ayrı veri kanıtı olarak gösterir ve öğretmene kontrol önerisi sunar.

## Kaynakta yapılan somut değişiklikler

| Dosya | Değişiklik | Neden |
|---|---|---|
| `services/performance_coaching_v15.py` (yeni) | Salt okunur, öğrenci kimliğine dayalı deneme özeti ve sınırlı kıyaslama | Deneme, ödev ve öğrenci verilerinin karışmasını önlemek |
| `ui/performans_paneli.py` | Beşinci **🎯 Deneme & Koçluk** sekmesi; Yenile, öğrenci arama, detaylı analiz ve web portalı için yeni sekme bağlantıları | Tek pencerede sade ve entegre görünüm |
| `ui/performans_paneli.py` | PDF'de Tüm Öğrenciler ve Deneme & Koçluk bölümleri; PDF ve Excel geçici görsellerinin temizlenmesi | Mevcut çıktıların kapsamını artırmak, geçici öğrenci görsellerinin disk üzerinde kalmasını önlemek |
| `tests/test_v15_performance_coaching.py` (yeni) | Öğrenci/sınav türü/tarih/soru sayısı/kaynak ayrımı, salt okunurluk ve UI kaynak bağlantıları | Regresyonu otomatik kontrol etmek |
| `V15_PERFORMANS_KOCLUK_KURULUM.md` (yeni) | Test kopyasına kurulum ve kabul adımları | Mevcut kurulumun korunması |

## Analiz kuralları

- Panel ödevleri V14'ün `performance_evidence_v14.py` kaynağından okur; deneme sonuçlarını bunlarla **toplam puanda birleştirmez**.
- İki sınav farklı öğrenci, tür, ders veya tarihteki farklı ölçme modeliyle ilgiliyse karşılaştırma yapılmaz.
- Yeni deneme tablosundaki `bos` alanı, uygulamanın bazı yazma yollarında varsayılan `0` olarak saklanmaktadır. Bu nedenle doğru+yanlış toplamı kesin soru adedi sayılamaz. Yalnızca **boş sayısı pozitif olarak kaydedilmiş**, kayıtlı toplam soru sayısı eşit ve sınav türü/dersi aynı iki ölçüm için **sınırlı** net farkı gösterilebilir. **Boş sayısı 0 ise gerçek tam çözüm bile olsa güvenli otomatik kıyaslama yapılmaz.**
- `deneme/deneme_sonuc` eski şemasında güvenilir toplam soru sayısı bulunmadığından son ölçüm yalnızca gösterilir; iki farklı şema aynı öğrenci için otomatik birleştirilmez.
- Ödev gecikmesi varsa koçluk kontrol listesinde öncelik alır. Veri tutarsızlığı daha önce araştırılır. Öğretmen onayı olmadan yeni ödev, mesaj, tanı veya müdahale üretilmez.
- Sınav güçlük düzeyleri kontrol edilemediğinden net farkları akademik başarının kanıtı olarak ifade edilmez.

## Test ve doğrulama

- Yeni modülün sentetik SQLite veritabanıyla **24/24 hedefli testi başarılı**. 
- Bütün kaynak paketteki Python dosyaları AST sözdizimi taramasında kontrol edildi.
- Geniş regresyon: **507 passed, 44 subtests passed, 3 failed, 4 errors**. Başarısız üç GUI testi ve dört yükleme hatasının görünen kaynağı PyQt6 bağımlılığıdır; bu testler gerçek masaüstü doğrulaması olarak sayılamaz.
- v3.5.16/V13.6 geliştirici yedeğindeki SQLite'ın **salt okunur kopyasında** 16 aktif öğrenciye ait 16 koçluk özeti üretildi; 15 kayıt için uygun deneme kanıtı yoktu, 1 kayıt için tek ölçüm vardı. Bu **veri yokluğunu yanlış başarı düşüşüne dönüştürmemek** açısından beklenen davranıştır. Hiçbir gerçek öğrenci kaydı değiştirilmedi.

## Korunan işlevler

V14 dört sekme, haftalık/30 günlük ödev hesabı, liderlik koşulu, Detaylı Analiz, Web Portalı, PDF, Excel, poster, öğrenci kimliği üzerinden geçiş ve `db.get_conn()` mekanizması korunmuştur. Haftalık planlayıcı, Sihirbaz, Takviye, Eksikler, tik/kayıt mekanizması, koçluk planları ve veritabanı şeması değiştirilmedi.

## Kalan sınırlar ve kurulum kararı

1. **Gerçek Mac/Windows Qt testi yapılmadı.** PDF/Excel görsel düzeni, panel tıklamaları ve performans yoğunlukta kabul edilmelidir.
2. Çalışan **v3.5.17** kaynaklarıyla fark birleştirmesi gerekir; V14 tabanlı yamayı doğrudan kuruluma uygulamayın.
3. Eski geliştirici veritabanında bildirilen **üç kopuk ödev bağlantısı** düzeltilmedi; V13.6 uzlaştırma aracıyla ayrıca değerlendirilmeli.
4. Gerçek konu-kazanım teşhisi için soru bazında doğrulanmış ölçme verisi gerekir; mevcut ders netinden bu çıkarım yapılamaz.
5. Deneme türü ve kayıtlı soru sayıları ayrıntılı girilmedikçe güvenli otomatik karşılaştırma sınırlı kalacaktır. Bunu gizlemiyoruz.

**Karar:** V15 kaynak güncellemesi hedefli testlere uygundur; çalışan gerçek Mac/Windows kurulumu için henüz sürüm onayı verilmemiştir. Test kopyasında deneyip uygun olduğunda kontrollü biçimde birleştirilmelidir.
