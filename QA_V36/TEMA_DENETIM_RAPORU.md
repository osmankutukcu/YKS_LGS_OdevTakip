# YKS/LGS Ödev Takip — Tema Sistemi Denetimi / V36 Güvenli Pilot

Kaynak: `YKS_LGS_HomeworkManager_v2_Son_Hal(3).zip`, 17 Ekim 2026.

## Karar

**Mevcut sürümde temalar tüm formlara tamamen entegre DEĞİL.** PyQt6'nın
uygulama-geneli QSS kuralları mevcut olmakla birlikte birçok pencere `setStyleSheet`
ile kendi açık renklerini veya düz metin renklerini dayatıyor. Tema seçimi tek
bir ayar anahtarı üzerinden tutarlı biçimde yürütülmüyor. Çalıştırılabilir
Windows ve macOS testi yapılmadan “tamamıyla sorunsuz” olarak nitelenemez.

## Ölçülen kapsama ve bulgular

- 481 Python kaynak dosyası analiz edildi (pilot QA kontrol dosyası hariç).
- Yaklaşık **1.621** `setStyleSheet(...)` çağrısı ve **3.471** açık hex renk bildirimi bulundu.
  Bu sayılar hata sayısı değildir; bunların bir bölümü bilinçli uyarı/rozet
  tasarımıdır ve değiştirilmemelidir.
- Ana tema üretimi: `ui/theme.py`; 33 hazır palet.
- Ana tema seçim ekranı: `ui/theme_selector_dialog.py`.
- Alternatif ayarlar: `ui/modern_settings.py` ve `ui/app_settings.py`.
- Ana kabuk: `main_window.py`.
- Tema bağımsız görünüm uygulayan yoğun modüllerden örnekler:
  `ui/homework_form.py`, `ui/coaching_manager.py`, `ui/randevu_takvimi.py`,
  `ui/topic_map_dialog.py`, `ui/odev_kontrol.py`, `ui/mobile_schedule.py`.
- **Doğrudan sebep:** `main_window.py` içerik hostuna verilen
  `"QWidget { background-color: #f1f5f9; }"` seçicisi, bu hostun alt
  widget'larında da açık renk uygulanmasına yol açabiliyordu.
- **Doğrudan sebep:** hazır tema seçimi `tema_mod` anahtarını güncelliyor,
  ortak QSS ise önce `tema` anahtarını okuyordu. Bunlar çelişebiliyordu.
- **Doğrudan sebep:** önceki özel tema renkleri yeni hazır tema seçimine
  taşınabiliyordu; yazı/zemin ve başlık/sekme çakışmaları üretebiliyordu.
- Tema yöneticisinin özel tema açılır listesini yenileyen yerde
  `self.cmbCustom.clear` çağrılmadığından eski seçenekler kalabiliyordu.

## Pilot kod değişiklikleri (modüler ve korumacı)

1. `ui/theme.py`
   - Kaydetme anahtarları senkronize edildi (`tema` ve `tema_mod`).
   - Hazır palete geçildiğinde önceden tanımlanmış özel renk kalıntıları temizleniyor.
   - Renk ve sayısal ayar girişleri doğrulanıyor; geçersiz girdiler güvenli varsayılana dönüyor.
   - Metin, buton durumu, sekme, tablo satırı, seçili satır, liste başlığı,
     açılır menü ve uyarı butonlarında otomatik kontrast koruması eklendi.
   - QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, tarih/saat alanları ve
     takvimler koyu/açık temaya uygun metin ve arka plan alıyor.
   - Yan menü/ana içerik için `#Sidebar`, `#ThemeSidebarAction`,
     `#ThemeSidebarBrand`, `#ThemeContentHost` semantik QSS seçicileri tanımlandı.
   - Mevcut onay kutusu çizimleri/olayları, iş kuralları ve ödev mekanizması değişmedi.
2. `main_window.py`
   - Yan menü butonları ve marka başlığındaki sabit renkler, ortak tema seçicilerine bağlandı.
   - İçerik alanındaki torun widget'ları etkileyen genel `QWidget` kuralı kaldırıldı.
3. `ui/theme_selector_dialog.py`
   - Canlı önizleme sırasında kullanıcı çıkış/İptal yaparsa eski tema ayarlarını
     geri alma imkânı eklendi; Kaydet ve Kapat seçilince korunuyor.
4. `ui/modern_settings.py`
   - Tema modu anahtarları birlikte yazılıyor; manuel mod seçimi ile seçilen
     hazır paletin doğal modunun uyuşmaması halinde eski arka plan bırakılmıyor.
   - Görünüm ayarları diyalogunda yerel açık renk tuvali netleştirildi.
5. `ui/app_settings.py`
   - Özel tema listesi yenileme düzeltildi.
   - Hazır palet yüklemesi kartlar/sekme/düğme renklerini de yeniliyor.
   - Tema renk editörü temadan bağımsız okunabilir açık zemin üzerinde kalıyor.

## Çalıştırılan testler

- 33 paletin tamamında QSS oluşumu, dengeli `{}` sayısı ve mod kaydı: **GEÇTİ**.
- Özel renk kalıntılarının temizlenmesi: **GEÇTİ**.
- Bozuk hex renk ve sayısal ayar durumunda QSS'nin oluşması: **GEÇTİ**.
- Buton normal/hover/pressed durumu için 4,5:1 metin kontrastı algoritması: **GEÇTİ**.
- 482 Python dosyası için AST söz dizimi kontrolü (QA betiği dahil): **GEÇTİ**.
- PyQt6 widget'larının masaüstünde gerçek oluşturulması, macOS/Windows sistem
  temaları, Qt varyantları, ikon çizimleri: **ÇALIŞTIRILAMADI** (bu ortamda PyQt6 yok).
- 481 kaynak dosyasındaki bütün yerel widget stillerinin tek tek görsel testi:
  **YAPILMADI; ek modüler uyarlama gerekiyor**.

Test tekrar: `python QA_V36/run_theme_safety.py` (PyQt6 gerektirmez).

## Windows/Mac kabul testleri (pilot aşama)

1. `Cloud Light`, `Klasik Koyu`, `Nord`, `Catppuccin Latte`, `Fenerbahçe`,
   `Neon` seç; Tema penceresini iptal ederek eski rengin geri döndüğünü doğrula.
2. Ana menüde tüm düğmeler, aktif/hover/disabled durumları ve yazılar okunur mu?
3. Öğrenci, Ödev Takip Formu, Koçluk, Sınav/Deneme, Takvim, Raporlar,
   Kullanıcılar, Ayarlar, WhatsApp, Kitaplar, Tema Editörü ekranlarını tek tek aç.
4. Her pencerede QLineEdit, QTextEdit, ComboBox açılır liste, SpinBox,
   Checkbox/Radio, Tab, Table, ToolTip, Dialog ve hata uyarısı metnini kontrol et.
5. Tema değişikliğinden sonra uygulamayı yeniden aç. Tema kalıcılığını test et.
6. 100%, 125%, 150% ekran ölçeğinde, küçük laptop ve geniş monitörde dene.
7. Ödev checkbox işaretleme, ödev ekleme/kaldırma, kayıt/senkron,
   sınav oluşturma ve raporlama akışlarında eski işlevlerin aynen kaldığını doğrula.
8. Koyu temada beyaz-yazı/beyaz-zemin veya koyu-yazı/koyu-zemin kalırsa
   pencere adı + ekran görüntüsü + seçili tema ile raporla.

## Sonraki aşama — tam entegrasyon

Bütün modülleri tek seferde yeniden stillendirmek yerine, yerel renkler
**semantik tasarım tokenları** (`surface`, `surfaceAlt`, `text`, `textMuted`,
`inputBg`, `inputText`, `primary`, `onPrimary`, `danger`, `success`, `border`)
üzerinden modül bazında güncellenmeli. İlk etap Ödev Takip Formu ve Koçluk;
ikincisi Sınav/Deneme ve Takvim; üçüncüsü Rapor/WhatsApp/diğer yardımcı
pencerelerdir. Her etapta ekran bazlı ışık/koyu görüntü karşılaştırması ve
etkileşim regresyonu aranmalıdır. Doğrudan veri, lisans, bulut, senkron ve
PDF/ödev hesaplama işlevlerine dokunulmamalıdır.

## Dağıtım güvenliği

Kod değişikliği yalnızca yukarıdaki **beş** Python dosyasında yapıldı.
Uygulama sürümü, SQLite veritabanları, WAL dosyaları, yedekler,
lisans/kullanıcı kayıtları ve iş kuralları değiştirilmedi. Pilot sürüm,
geri dönüş için orijinal ZIP yedeklenerek test makinesinde denenmelidir.
