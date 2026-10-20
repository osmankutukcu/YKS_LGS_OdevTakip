# KoçPilot 360 — v3.5.69 / Aşama 10 — Akıllı Çalışma Planı (PİLOT)

## Amaç

Bu paket önceki v3.5.68 kaynaklarını temel alır. Ödev Takip ve Ödev Kontrol formlarının **tamamı byte düzeyinde değişmeden** kalır; yeni ana ekran, kolon, alt buton, checkbox akışı veya kayıt yolu eklenmez.

## Uygulanan değişiklikler

- `services/smart_study_plan_v3569.py` (YENİ): v3565 onay gerektiren, sıralı akademik önerileri ile v3564 gerçek kitap/konu taslak eşleşmelerini bağlayan salt-okunur, deterministik çalışma önerisi. Yalnızca doğrulanmış öğrenci/tarih/kanıt kombinasyonunda çalışır. Hedefli kontrol ve müdahale sonrası yeniden ölçüm önceliklerini korur. Bir müdahale takibini otomatik olarak yeni ödeve dönüştürmez.
- `ui/research_coaching_bridge_v3563.py` (yardımcı entegrasyon): Aynı mevcut arka plan okuyucusunda, aynı transaction içindeki verilerle saf plan önizlemesini hesaplar. Mevcut Koç Asistanı'nın **var olan Ortak Koçluk Önceliği** kartına, güvenilir eşleşme bulunduğunda tek cümlelik plan notu ekler. Yeni bildirim, pencere, buton, otomatik tıklama veya veritabanı işlemi eklemez.
- `tests/test_smart_study_plan_v3569.py` (YENİ): Sahte öğrenci testleriyle kimlik, tarih, kaynak güvenliği, sahte kitap, iş yükü, süre, öncelik, mükerrer kayıt, yetkisiz transfer ve değişmezlik denetimleri.

## Kullanıcı için örnek

**Koç Asistanı → Ortak Koçluk Önceliği** kartının kendi metninin altında:

> Çalışma planı: Sihirbaz taslak adayı: AYT 1 — 20 dk. Takvime uygunluk doğrulanmadı; ödev atanmadı.

*Bu ifade sadece aynı öğrenci, aynı gün ve aynı gerçek kitap/konu eşleşmesi doğrulanmışsa gösterilir.* Öğretmen mevcut Sihirbazı açarak normal onay/kaydetme akışını kullanır.

## Kapasite ve bilimsel sınırlar

- Kullanıcı takviminden doğrulanmış **net, atanmamış haftalık dakika** yoksa kullanılabilir zaman **bilinmiyor** kabul edilir; ne otomatik saat, ne gün ne de planlama garantisi üretilir.
- v3564'ün doğrulanmış kitap önerisinde `overload_limited=True` varsa otomatik ek ödev önerisine dönüştürülmez; önce iş yükü gözden geçirilir.
- `verified_unallocated_minutes` yalnızca dışarıdan bağımsız biçimde doğrulanırsa saf motor bütçe karşılaştırması yapabilir. Bugünkü arayüzde bu parametre **bilerek verilmez**.
- Ödev tiki, kazanım öğrenildi anlamına gelmez. Kök neden, müdahale etkisi, kalıcılık veya unutma oranı iddiası üretilmez.
- Akış okuma odaklıdır; öğrenciye ödev eklemez, checkbox işaretlemez, veritabanı şeması değiştirmez, WhatsApp göndermez, plan kaydetmez.

## Kapatma / geri dönüş

`QSettings('EduTrack','HomeworkManagerV2')` içinde `smart_study_plan_v3569_enabled = 0` yapılırsa mevcut Koç Asistanı'nın öncelik kartına plan notu eklenmez. Böylece önceki v3.5.68 kart davranışı devam eder. Mevcut koçluk bağlantılarının ve checkbox işleyişinin kendi ayarları aynıdır.

## Testler ve sınırlamalar

- `python tools/v3527_core_guard.py --root .`: **PASS**, kaynak statik sözleşmesi; tarihsel olarak iki gölgelenmiş metot uyarısı mevcut.
- Seçili saf öğrenme/koçluk/planlama testleri başarılı (güncel sonuç raporu teslimde ayrıca verilir).
- Tam proje `pytest tests` toplamasında ortam eksikleri: gerçek PyQt6 widget'ları ve mevcut pakette olmayan `_admin_tools_private` nedeniyle **7 koleksiyon hatası**, dolayısıyla tam test takımı başarılı denemez.
- **Windows / gerçek PyQt6 / EXE / yüksek DPI / kullanıcı tıklama hızı / üretim veritabanında uzun süreli testler YAPILMADI.** Paket yalnızca pilot; müşterilere otomatik güncelleme ile dağıtmayın.
- Uygulamanın `version.py` ve `version.json` dosyalarına dokunulmadı. v3.5.69 yalnızca kaynak dağıtım etiketi, çalıştırılabilir ürün sürüm numarası değil.

## Önerilen Windows kabul akışı

1. Eski v3.5.68 ile ödev ver–Kaydet, tik, geri al, kontrol, kilit, renk ve Sihirbaz aktarımı davranışını örnek test verisinde kaydedin.
2. Aynı öğrencinin aynı gün bağımsız ölçüm ve kitap/konu eşleşmesini oluşturup Koç Asistanı'nda var olan öncelik kartına kısa plan notunun eklendiğini doğrulayın.
3. Koç Asistanı açıkken farklı öğrenciye geçip önceki öğrencinin taslağının görünmediğini kontrol edin.
4. Öğrencide fazla iş yükü varsa plan notunun yeni çalışma atanabilir algısı oluşturmadığını kontrol edin.
5. Özelliği kapattığınızda v3.5.68 öneri metnine döndüğünü doğrulayın.
6. Önce/sonra checkbox tıklama gecikmesi, Kaydet süresi, takılma, tutarsız kayıt ve Windows DPI ölçümleriyle yayın kararı verin.
