# V18 – Modüler Konu Kanıtları Köprüsü

## Amaç
Ödev Takip, Konu Haritası, Koçluk ve Deneme sonuçlarını öğrenci kimliğine bağlı **salt okunur** inceleme ekranında göstermek. **Ödevin tamamlanması konu öğrenme kanıtı sayılmaz.** Ders düzeyindeki deneme netleri kazanım/konu düzeyine otomatik aktarılmaz.

## Yeni modüller
- `services/topic_evidence_v18/models.py`: salt okunur sonuç veri sınıfları
- `services/topic_evidence_v18/reader.py`: öğrenciye özel ana ödev, harita ödevi, koçluk ve ders düzeyindeki deneme okuyucusu
- `services/topic_evidence_v18/advisor.py`: kesin teşhis içermeyen açıklamalı kontrol önerileri
- `services/topic_evidence_v18/__init__.py`: küçük dış arayüz
- `ui/topic_evidence_dialog_v18.py`: tek ortak öğrenci/konu inceleme ekranı
- `tests/test_v18_topic_evidence.py`: hedefli regresyonlar

## Sadece bağlanan eski dosyalar
- `ui/topic_map_dialog.py`: “Birleşik Konu Kanıtları” düğmesi, mevcut öğrenci seçimi kullanılıyor.
- `ui/student360_panel_v16.py`: “Konu Kanıtları” düğmesi. Aynı ortak pencereyi açar.

## Veri ilkeleri
1. Öğrenci kimliği (`ogrenci.id`) doğrulanır; bulunamazsa ilk öğrenciye düşülmez.
2. Ders ve konu yalnızca normalize edilmiş **tam metin eşleşmesiyle** birleştirilir; belirsiz isimlerde otomatik tahmin yapılmaz.
3. `odev` ve `odev_satir` aynı ödev kümesinde ise ikincil tablo ayrıca sayılmaz, uyarı gösterilir.
4. `odev_takip` ayrı bağımsız çalışma kaynağı olarak etiketlenir. Bunun ana ödevle aynı çalışma olup olmadığı kanıtlanmış sayılmaz.
5. Çoklu `koc_konu_takip` kayıtlarında tek bir hâkimiyet kararı verilmez.
6. Deneme neti yalnızca ders düzeyinde görünür; konu bazlı net veya eksik sonucu üretilmez.
7. Kod mevcut veritabanını açarken `mode=ro`, `query_only=ON` kullanır; ekleme, silme, güncelleme veya göç yapmaz.

## Kurulum
V17 kaynak proje yedeğinde klasör yapısını koruyarak `OdevTakip_V18_Yalnizca_Degisen_Dosyalar.zip` içeriğini çıkarın. Hiçbir kişisel veritabanını veya profil dosyasını değiştirmeyin. GitHub/kurulum dağıtımı için öğrenci verisi olmayan paket kullanın.

## Önerilen gerçek kullanıcı testi
1. Koçluk → Öğrenci 360° → öğrenci seç → Konu Kanıtları → ders/konu özetini kontrol et.
2. Konu Haritası → aynı öğrenciyi seç → Birleşik Konu Kanıtları → aynı çıktıyı gör.
3. Başka öğrenciye geç → önceki öğrencinin kayıtlarının görünmediğini doğrula.
4. Benzer konuları kontrol et (Elektrostatik / Elektrostatik Ek), yanlış birleştirme olmamalı.
5. Ödev Takip'te manuel tik/kaydet ve Koçluk'ta manuel konu değiştir → yeni pencerede Yenile; işaretler ve ödevler kendiliğinden değişmemeli.
6. Deneme Matematik netinin belirli bir matematik konusuna atanmadığını doğrula.
7. Mac ve Windows'ta pencere boyutu, kopyala, yenile ve kapat işlemleri.

## Sınırlar
Bu V18 **ilk entegrasyon**dur: deneme sorusu→konu eşlemesi, koçluk hedefini otomatik güncelleme ve iki ödev sistemini fiziksel olarak birleştirme yapılmadı. Eksik/yanlış akademik teşhis üretmekten kaçınmak için bunlar açıkça ayrı sonraki aşamalardır. Geçerli Windows/macOS grafik arayüzü testleri ayrıca gereklidir.
