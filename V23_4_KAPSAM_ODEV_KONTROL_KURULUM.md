# V23.4 – Kapsama Özel Ödevlerin Ödev Kontrol'den Güvenli Yönetimi

**Kaynak taban:** V23.3 kümülatif kaynak (v3.5.16 kökenli). **Durum:** Windows GUI sahada doğrulanmadı; canlı EXE üzerine doğrudan kurulmaz.

## Öğretmen kullanım adımları

1. Ödev Takip Formu'ndan öğrenciyi seçip **Ödev Kontrol**'ü açın.
2. Üst işlem çubuğundaki **🎯 Kapsam Ödevleri** düğmesini tıklayın. Açılan modal, aynı öğrencinin yalnızca grup/öğrenci özel konu ödevlerini listeler.
3. **Ders** ve **Durum** filtrelerini kullanın. Önce satırı seçin; açık ödev için **Tamamlandı** veya **İptal**, tamamlanmış/iptal edilmiş ödev için **Açık Duruma Al** seçeneğine basın.
4. İşlemi onaylayın. Diğer açık ödevle çakışma veya eşzamanlı durum değişikliği varsa işlem yapılmaz. **Geçmiş** ile V23.4'te yapılan durum değişikliklerini görebilirsiniz.
5. Kapatınca eski Ödev Kontrol görünümü ve tikler olduğu gibi kalır. Öğrenci 360° özetini güncellemek için ilgili ekranda **Yenile** kullanın.

## Veri ve işlem güvenliği

- **Eski tabloya yazılmaz:** `odev`, `odev_satir`, `odev_kume` ve ana formun tik durumları korunur.
- **Farklı kategori:** V23.3 özel ödevleri `kapsam_odev_v233` tablosunda tutulur; eski ana ödev toplamlarına otomatik eklenmez.
- **Yeni audit:** Sadece ilk *V23.4 durum değişikliği* sırasında `kapsam_odev_kontrol_log_v234` tablosu açılır; izleme/read işlemi tablo oluşturmaz.
- **Geri alma:** `tamam` veya `iptal` → `devam` yalnızca öğretmen onayıyla, aynı öğrenci/konu/kitap için başka açık görev bulunmuyorsa yapılır.
- **Bağlantı:** Öğrenci ID'si mevcut kontrol ekranından sabit alınır, başka öğrenci seçilemez.
- **Eski özel kapsam UI'sı:** V23.3'ün Konu Kapsamı penceresi durur; oradaki kayıt yöntemini V23.4'te değiştirmedik.

## Windows kabul testleri (gerçek bilgisayarda)

- Ayrı test kopyası: kod, SQLite, profil dosyaları ve git sürümünün yedeği.
- 1920×1080 (%100), 1366×768 (%125), 1280×720 (%150) ekranlarda menü, tablo kaydırma ve iki satırlı butonlar.
- Öğrenci A'nın özel ödevini tamamlama; öğrenci B kontrol penceresinde bu ödevin görünmemesi.
- Normal ödev **Kaydet**, **Aktar**, **Geri Taşı**, tikleme ve Kontrol formu yeniden açma; eski durumlar değişmemeli.
- Özel kapsam ödevini tamamla → geri al; aynı anahtar için yeni açık ödev varsa geri almanın reddedilmesi.
- **Geçmiş** ekranının kayıttan sonra değişiklik göstermesi; normal ödev PDF, WhatsApp ve kontrol yüzdelerinin eski davranışı koruması.
- Kurulum/otomatik GitHub güncelleme ve geri dönüş testi; çalışan v3.5.17 kaynak farklılıkları ayrıca birleştirilmeli.

## Kaynak kurulumu

1. **V23.3 kümülatif kaynak** üzerinde çalışın; son V23.3 yedeğini alın.
2. V23.4 küçük yama ZIP'ini proje köküne *klasör yapısını koruyarak* açın. Yalnızca `ui/odev_kontrol.py` önceki halinin üzerine yazılır; diğerleri yeni dosyalardır.
3. `python -m pytest -q tests/test_v233_scoped_homework.py tests/test_v234_scoped_control.py` ile çekirdek kayıt testini çalıştırın.
4. Windows'ta PyQt6 bağımlılıklarını kendi uygun sanal ortamınıza yükleyip yukarıdaki senaryolarla test edin.
5. **Canlı sürüme geçmeden önce** v3.5.17 kaynak farklarını birleştirin; bu paket bir derlenmiş `.exe` değildir.
