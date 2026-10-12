# V23.3 — Grup ve Öğrenci Konularına Güvenli Ödev Verme

## Kurulum

1. **Çalışan uygulamayı durdurun.** Program klasörünün, SQLite veritabanının, öğrenci/profil verilerinin ve EXE kurulumunun ayrı yedeğini alın.
2. V23.2 kaynak sürümünün **ayrı test kopyasında** `OdevTakip_V23_3_Kapsam_Odevleri_Yalnizca_Degisen_Dosyalar.zip` içeriğini mevcut dosyaların üzerine çıkarın. Doğrudan üretim klasörüne kurmayın.
3. Windows testinde gerçek v3.5.17 sürümüyle farkların birleştirildiğinden emin olun. PyQt6, 1366×768, %125–%150 DPI ve 1280×720 ekran testlerini yapın.
4. Bir öğrenci seçin → **Getir** → ders sekmesi → **Konu Kapsamı** → **Kapsama Özel Ödevler**.
5. Yalnızca öğrencinin grubuna veya kendisine tanımlı, çakışmasız konuların listelendiğini kontrol edin. Öğrenciye önceden atanmış bir kitap seçin, süre ve teslim tarihi belirleyin, **açık onayla** kaydedin.
6. Aynı pencerede `devam/tamam/iptal` durumlarını inceleyin. Yanlış öğrenci, adı değiştirilmiş konu, kaydı olmayan kitap ve tekrarlanan açık ödevler engellenir.
7. **Öğrenci 360°** bölmesinde `KAPSAMA ÖZEL ÖDEVLER (AYRI KAYIT)` özetini kontrol edin. Ana Ödev Kontrol Formu'nun tamamlanan/açık sayıları ile **toplamayın**.

## Ne değişir, ne değişmez?

- Yeni ödev ekleme işlemi yalnızca `kapsam_odev_v233` adlı **yeni** SQLite tablosunu oluşturur ve kullanır. Bu tablo daha önce yoksa salt okunur önizleme hiçbir şema değişikliği yapmaz.
- `odev`, `odev_satir`, `odev_kume`, müfredat tabloları, genel konu ID’leri ve sarı/yeşil tikler **değiştirilmez**.
- Kapsam ödevleri mevcut **Ödev Kontrol Formu üzerinden henüz düzenlenemez**. Onları ayrı V23.3 penceresinden tamamlayabilir veya iptal edebilirsiniz. Bu bir **kademeli entegrasyon** özelliğidir, eski ödev kayıtlarının yerine geçmez.
- İptal edilen veya tamamlanan kapsam kayıtları geçmiş denetimi için silinmez; aynı öğrenci–ders–konu–kitap için birden fazla **açık** kayıt oluşturulamaz.
- Öğrencinin grubu veya konu ismi değişirse geçmiş kayıt aniden başka bir konuya taşınmaz; yeni işlem yapılmadan önce güncel kimlik doğrulanır.

## Sınırlar ve kabul şartları

- V23.3 kaynak ve SQLite seviyesinde test edildi. PyQt6 kurulamadığı için Windows'ta **gerçek pencere/tuş kabul testi yapılamadı**.
- Yeni özel konu ödevlerini eski `odev` tablosuna tahminî `konu_id=0` ile yazmak yasaktır: yanlış hücreye kilit atabilir.
- Eski Ödev Kontrol Formu'nda tek ekranda birleşme, tamamlanma ve geri alma kontrolleri ayrı entegrasyon testinden sonra ele alınmalı. Bundan önce `kapsam_odev_v233` sayılarını akademik performansla birlikte hesaplamayın.
- Canlıya alma kriteri: yedekten geri dönme, çift kayıt denemesi, farklı öğrenci erişimi, müfredat değişimi sırasında deneme, aynı dersin eski tiklerinin birebir korunması, düşük çözünürlükte bütün kontrol düğmelerine erişim.
