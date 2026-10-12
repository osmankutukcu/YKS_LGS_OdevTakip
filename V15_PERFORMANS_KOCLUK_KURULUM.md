# V15 – Performans Paneli / Deneme & Koçluk – Kurulum

**Başlangıç:** V14 güncellemesi entegre edilmiş v3.5.16/V13.6 **kaynak projesi**. Görselde çalışan v3.5.17 veya yeni sürümle dosya farkları karşılaştırılmadan üzerine yazmayın.

1. Çalışan programı kapatın. Kaynak, SQLite (.db ve varsa .db-wal/.db-shm) ve öğrenci plan/profil JSON dosyaları için geri döndürülebilir yedek alın.
2. Uygulamanın **ayrı test kopyasına** `OdevTakip_V15_Yalnizca_Degisen_Dosyalar.zip` içindeki dosyaları kendi klasör yapıları korunarak uygulayın. Yama V14 dosyası `ui/performans_paneli.py` içindir.
3. Python ortamınızda proje bağımlılıklarıyla çalıştırın, Performans Paneli'nde beş sekmeyi kontrol edin. “Deneme & Koçluk” sekmesinde ödev ve deneme alanlarının ayrı olduğunu doğrulayın.
4. **Gerçek Mac/Windows kabul testi:** bu hafta/geçen hafta, öğrenci arama, aynı isimli iki öğrenci, farklı sınav türleri, farklı soru sayıları, tek deneme, panelden öğrenciye Detaylı Analiz, PDF/Excel/poster/Web Portalı, aç/kapat.
5. Kayıt değişmezliği: testten önce/sonra öğrenci ve ödev tablolarının sayılarını karşılaştırın; yeni analiz SQL yazmamalıdır. Deneme verisi yoksa “Yok” görülmesi normaldir.
6. Hata görülürse çalışan sürümü durdurun ve kaynak + veritabanı **aynı ana ait yedeğe** geri dönün.

## Hangi sınav kayıtları karşılaştırılır?

Yeni tip `denemeler/deneme_sonuclari` kayıtlarında sınav türü ve ders aynı, iki **farklı tarih** mevcut, ayrıca **boş soru sayısı pozitif olarak kaydedilmiş** ve doğru/yanlış/boş toplamları eşitse sınırlı bir net karşılaştırması gösterilebilir. Uygulama boş soru alanını varsayılan `0` olarak bıraktığında toplam soru sayısı ispatlanmaz; güvenli karşılaştırma yapılmaz. Eski tip `deneme/deneme_sonuc` kayıtları sadece son ölçüm olarak gösterilir. Her durumda farklı sınavların güçlük düzeylerinin eşitliği bilinmez.

**Yapılmayanlar:** Ödev ekleme/silme; öğrenci kaydını değiştirme; netleri ödev tamamlama puanına karıştırma; sınavdaki yanlış soruyu kazanım eksikliği ilan etme; internete öğrenci verisi gönderme.

**Güvenlik:** Paylaşılan tam kaynak pakette veri dosyaları, özel yönetici/lisans üretim araçları ve fontlar bulunmaz. Bunları önceki özel kurulumunuzdan koruyun, GitHub'da yayımlamayın. Ana arayüz için PyQt6 yüklü Mac/Windows ortamında kabul testi gereklidir.
