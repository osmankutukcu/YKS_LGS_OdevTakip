# KoçPilot 360 — v3.5.67 / Aşama 8 — Ortak Koçluk Önceliği (PİLOT)

## Ne yapıldı?

v3.5.66 temel alındı. Aşama 8 ile **aynı öğrenci + aynı tarih + aynı V3565 doğrulanmış koçluk kanıtı** için tek bir akademik öncelik sunum sözleşmesi hazırlandı. V3565 sıralamasındaki ilk doğrulanmış öneri **yeniden sıralanmadan** alınır. Tekrarlı bildirimler Koç Asistanı'nda azaltılır, öğrenme düzeyi veya kök neden kesin teşhis edilmez.

- `services/coaching_action_center_v3567.py` (YENİ): fail-closed, salt okunur ortak öncelik kartı; kimlik, tarih, alan, çalışma türü ve otomatik işlem bayrağı doğrulaması; öğretmen için tek satırlık özet.
- `ui/research_coaching_bridge_v3563.py` (MEVCUT YARDIMCI): öneriyi mevcut Koç Asistanı gelen kutusunda sunar, eski `btnOgrenme` yoluna yönlendirir; onay olmadan Sihirbaz ataması yapmaz. Aynı kazanımdaki yeni araştırma kartını ikinci kez sunmamak için azaltır. Yeni özellik kapatılırsa eski V3565 gelen kutusu davranışı geri gelir.
- `ui/student360_journey_sidecar_v3566.py` (MEVCUT YARDIMCI): aynı V3565 veritabanı snapshot'ından hesaplanan önceliği, Öğrenci 360°'nin var olan salt okunur koçluk özetinin sonuna ekler; ek sorgu veya ayrı pencere yok.
- `services/teacher_copilot_v5.py` ve `ui/teacher_copilot_strip_v5.py` (MEVCUT YARDIMCILAR): ana ekran Akıllı Takip şeridindeki **zaten seçili ilk öğrenci** için uygun süre varsa salt okunur öncelik hesaplayıp var olan açıklama satırının sonuna ekler. V10/V11/Günün Akıllı Özeti ödev/gecikme sıralaması ve gerçek diyalogun algoritması değiştirilmedi. Diğer öğrenciler bu aşamada topluca taranmıyor.
- `tests/test_coaching_action_center_v3567.py` (YENİ): 10 test; özellikle öğrenci karışması, eski tarih, unsafe bayraklar, ikinci kayıt güvenlik reddi, kaynakların ortaklaşması, özellik kapatma ve çekirdek koruması.

## Güvenlik ve uyumluluk

- Kaynak karşılaştırması: v3.5.66'nın **789 dosyasının tümü korunmuştur**. Var olan dört yardımcı dosya yukarıdaki işlemler için değişti. İki yeni kod/test dosyası, bu not ve README güncellemesi eklendi.
- `ui/homework_form.py`, `ui/odev_kontrol.py`, `ui/smart_wizard_dialog.py`, eski asistanın çekirdek kodu, `db.py`, `version.py`, `version.json` değiştirilmedi.
- Yeni bileşende SQL veya veri yazımı yok; tüm çalıştırma salt okunur; öğretmen onayı dışında ödev/mesaj/checkbox değişikliği yok.
- Aynı kartın yalnızca var olan Öğrenme ekranına gitmesi desteklenir; otomatik öğrenciye ödev veya Sihirbaz ataması yapılmaz.
- **Geri dönüş:** `QSettings('EduTrack','HomeworkManagerV2')` anahtarı `coaching_action_center_v3567_enabled=0`. Bu durumda eski v3566 Öğrenci 360 özeti, v3565 Koç Asistanı uyarıları ve orijinal öğretmen şeridi davranışı korunur.
- Uygulama sürümü bilerek `3.5.56` kaldı; `v3.5.67` yalnızca kaynak geliştirme etiketidir. Kurulum/EXE ya da GitHub otomatik güncellemesi değildir.

## Test sonuçları

- Seçili koçluk, öğrenme, ödev bütünlüğü, veri akışı, günlük özet ve yeni ortak öncelik regresyonları: **174/174 başarılı**.
- `python tools/v3527_core_guard.py --root .`: PASS; `original_forms_modified=false`, `production_release_authorized=false`.
- Önceki ZIP dosyalarıyla SHA-256 içerik karşılaştırması yapıldı. Ödev Takip, Ödev Kontrol ve Sihirbaz dosyaları birebir aynı.
- Linux konteynerinde PyQt6 kurulu değil; gerçek Windows UI, checkbox hızı, erişilebilirlik, EXE derleme, süre ve büyük gerçek veritabanı performans testleri **YAPILMADI**. Paket üretim ortamına dağıtılmamalı.

## Windows kabul senaryoları

1. v3.5.66 ile aynı öğrencide, aynı gün, ölçümü bulunan konu için Öğrenci 360° ve Koç Asistanı'nda **aynı ilk akademik adımın** göründüğünü karşılaştırın.
2. Ana ekran şeridinde ilk V10/V11 adayı aynı öğrenci ise ortak adımı doğrulayın. V10/V11 ödev gecikme sıralaması değişmemeli.
3. Öğrenci A'dan B'ye geçin; A'nın akademik önerisi B'ye taşınmamalı.
4. Yeni özelliği kapatın; eski koçluk bildirimleri ve Öğrenci 360° özeti çalışmalı.
5. Ödev Takip, Ödev Kontrol, Sihirbaz — tik, kayıt, geri al, öğrenci seç, renk, kilit, taslak aktarımını eskisiyle karşılaştırın.
6. Çok büyük SQLite ve uzun süreli veri kilidinde, arka plan analizini ve ana şerit yenilemeyi ölçün.
7. İleri aşamada Günün Özeti diyalogunun bütün öğrenci listesiyle aynı doğrulanmış öncelik sistemine entegre edilmesini ayrıca ele alın.
