# V23.5 – Windows bütünleşik kabul kontrol listesi

**Taban:** V23.4 kümülatif kaynak. **Kapsam:** Genel Ödev Takip → Ödev Kontrol → Öğrenci 360° → Müfredat → Kapsama Özel Ödevler. **Bu bir kaynak kodu / kabul testleri paketidir; imzalı Windows EXE değildir.**

## Kurulum ve veri güvenliği

1. Kullanılmakta olan Windows uygulamasını kapatın. Mevcut kodu, SQLite veritabanını, profil JSON dosyalarını ve EXE/kurulum paketini ayrı bir yedeğe alın. Veritabanı WAL modundaysa dosya kopyalamadan önce uygulamanın kapalı olduğundan emin olun veya SQLite backup API ile tutarlı yedek alın.
2. V23.4 kaynak kodunun **ayrı bir test kopyasına** V23.5 yamasını açın. Kodu çalışan Windows programının üzerine ve üretim veritabanına doğrudan uygulamayın. Kullanıcının çalışan v3.5.17 kaynağıyla henüz merge yapılmadı.
3. Terminalde test kopyasında: `py -m pytest -q tests/test_v235_integrated_acceptance.py tests/test_v235_cli_readonly.py`
4. **Yalnızca kopya veritabanında**: `py tools\audit_integration_v235.py --db "C:\TestVerileri\YKS_LGS_HomeworkManager.db"`
5. Denetim **hiçbir şeyi düzeltmez veya veri eklemez**. Çıkış kodu `0` = kontrol edilen bütünlük sorunları yok; `1` = denetimde bulgu var; `2` = şema/okuma hatası. V13.6 yedeğinde bilinen 3 kopuk bağlantı bulunduğundan `1` beklenir. Bu 3 satırı onaysız ilişkilendirmeyin.

## Gerçek öğretmen kabul senaryoları

| No | Senaryo | Beklenen sonuç |
|----|---------|----------------|
| W01 | Örnek öğrenci 1 seç, kaydedilmiş ödev tikini incele | Sarı/yeşil durum aynı kalır |
| W02 | Genel konudan ödev ver → Kaydet → öğrenci değiştir → geri dön | Aynı konunun ve öğrencinin kaydı kalıcıdır; mükerrer ödev yok |
| W03 | Ödev Kontrol → tamamla → kapat/aç | Kontrol ve ana form tutarlı; yalnızca doğru öğrenci değişir |
| W04 | Kontrol → geri al | Önceki tamamlandı durumu eski kurallara uygun şekilde geri döner |
| W05 | Müfredat & Dersler → Ders/Konu Düzenle | Her iki giriş noktası aynı kayıtları gösterir |
| W06 | Öğrenci/grup özel konuyu incele | Başka öğrencinin konusu görünmez; aynı sayısal ID genelle eş tutulmaz |
| W07 | Konu Kapsamı → Kapsama Özel Ödev oluştur | Ayrı kapsam kaydı olur; ana tikler değişmez |
| W08 | Ödev Kontrol → Kapsam Ödevleri → Tamamlandı | Sadece seçili kapsam kaydı güncellenir |
| W09 | Aynı kapsam kaydını Açık Duruma Al | Denetim geçmişi korunur; çakışma varsa işlem reddedilir |
| W10 | Öğrenci 360°'yi aç ve başka öğrenciye geç | Önceki öğrencinin adı/özeti anında silinir; veri karışmaz |
| W11 | Aynı öğrencinin deneme ve koçluk ekranını aç | Kanıtsız konu başarısı veya iki kat ödev sayımı yok |
| W12 | Uygulamayı kapatıp yeniden aç | Genel ve özel ödevler doğru kaynakta kalıcıdır |
| W13 | Yenileme / eski sürüme geri dönme denemesi | DB geri alma kontrollüdür; sessiz şema/veri kaybı yok |
| W14 | Bilinmeyen konu / bozuk kimlik | Yanlış satır otomatik düzeltilmez; gerekçeli uyarı gösterilir |

## Windows ekran ve performans matrisi

- 1920×1080 / %100 ve %125: normal iki/üç sütun düzeni, menü, kayıt butonları.
- 1366×768 / %100, %125, %150: kompakt menü, tek ekran bölmesi, Kontrol ve Kapsam Ödevleri. Düğmeler görev çubuğunun altında kalmamalı.
- 1280×720 / %125 ve %150: tabloların kaydırması, diyalog kapanışı, seçili öğrenci kimliği.
- 1024×768 / %100 veya varsa daha büyük Windows ölçeklendirme: işlem düğmelerine erişim, yatay/dikey kaydırma.
- Çoklu monitör arasında pencere taşınması, farklı DPI, çözünürlük değişikliği ve Windows yeniden başlatma.
- Özellikle 300+ konu, 500+ ödev, 16/100/1000 öğrenci gibi kademeli **sentetik** veri testinde tik yanıt süresi ve pencere yenileme algısı ölçülmeli; gerçek öğrenci kayıtlarına yük testi uygulanmamalı.

## Kabul koşulları

- Eski genel ödevin `odev/odev_satir/odev_kume` kayıtları ve sarı/yeşil tikleri, özel kapsam işlemlerinde **değişmeyecek**.
- `kapsam_odev_v233` ve `kapsam_odev_kontrol_log_v234` ayrı kalacak; sonuçlar yanlışlıkla ana ödev başarısı olarak toplanmayacak.
- Güvenli, tekil öğrenci kimliği kullanılacak; Excel'den gelen isim benzerliğiyle öğrenci ataması yapılmayacak.
- Üretim kurulumundan önce gerçek Windows masaüstü ve Windows GitHub update/rollback testleri başarılı olacak.
- **Teknik sınırlama:** Bu hazırlama ortamında PyQt6 bulunmadığı için masaüstü testleri tamamlanmamıştır. GitHub build workflow kaynak ZIP'de bulunmuyor; mevcut repodaki gerçek pipeline ayrıca görülmelidir.
