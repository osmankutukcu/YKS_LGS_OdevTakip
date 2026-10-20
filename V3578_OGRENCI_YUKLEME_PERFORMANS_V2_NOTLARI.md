# KoçPilot 360 — Öğrenci Yükleme Performansı V2 (v3.5.78 pilot)

## Amaç
V1 tanılaması korunarak yalnızca **başarılı öğrenci değişimi** sırasında yinelenen öneri paneli ve üst özet yenilemesini azaltmak. Gerçek Windows ölçümleri henüz olmadığından tablo yeniden kullanımı, SQLite sorguları, progress bar ve checkbox koduna müdahale edilmedi.

## Kaynak değişiklikleri
- `services/student_load_fastpath_v3578.py`: bağımsız, açılıp kapanabilen uygulama başlangıç bağlantısı.
- `app.py`: V1 gözlemci kurulmadan önce V2 hızlı yolunun kurulum çağrısı. Hızlı yol hatası uygulama açılışını engellemez.
- `tests/test_student_load_fastpath_v3578.py`: başarılı yükleme, eksik seçim, erken dönüş, hata, devre dışı bırakma, V1 ölçüm uyumu.

Ödev Takip (`ui/homework_form.py`), Ödev Kontrol (`ui/odev_kontrol.py`), `ui/progress.py`, SQLite/`db.py`, Haftalık Planlayıcı, PDF, tema, checkbox ve kayıt kodlarına dokunulmadı.

## Davranış
- Mevcut `_bilgileri_getir()` zaten `self.oneri._yenile_click()` ve `self._update_student_snapshot()` çağırıyor. Başarılı yükleme sonunda `_loaded_student_id` seçilen öğrenciye eşitse, dış çağrı zincirindeki **ikinci** yenilemeler tekrar yapılmıyor.
- Eksik seçimde eski `_ogrenci_degisti_combo_ile` bütünüyle çalışır. Erken dönüşte eski dış güncellemeler yapılır. Hata olursa yükleme yeniden denenmez; dış özet/öneri kontrolü sürdürülür.
- Test ortamında sırf çağrı sayısı azaltılmıştır; gerçek Windows'ta yüklenmenin kaç ms hızlandığı **henüz ölçülmemiştir**.
- Önceki davranışa dönmek için uygulama başlamadan `KOCPILOT_STUDENT_LOAD_FASTPATH=0` ortam değişkenini tanımlayın. V1 ölçümü çalışmaya devam eder; onu ayrı olarak `KOCPILOT_LOAD_PROFILE=0` ile kapatabilirsiniz.
- Öğrenci kaydı, adı, ID'si, iletişim, ders/ödev içeriği veya SQL bu modül tarafından kaydedilmez ve değiştirilmez.

## Ölçüm ve kabul kriterleri
1. Ayrı Windows test EXE'si ile, gerçek öğrenci kayıtlarının **yedek kopyasında** deneyin. Önce `KOCPILOT_STUDENT_LOAD_FASTPATH=0`, sonra açıkken **aynı** üç öğrenciyi, her biri 5 kere değiştirin.
2. `%LOCALAPPDATA%\\KocPilot360\\diagnostics\\student_load_v1.jsonl` V1 raporlarını toplayın. Aynı anda iki kopyanın açılmasını ve farklı PC / data ile ölçümleri karıştırmayı önleyin.
3. İlk çalıştırmanın soğuk önbellek maliyetini ayrı değerlendirin; medyan/p95 süre, ders tablosu sayısı, yenileme çağrısı sayısı karşılaştırılmalı. Hız artışı yalnızca bu ölçümlerle iddia edilebilir.
4. A→B→A öğrenci değiştirme, verilen ödevler, checkbox, kilitli renkler, kaydetme/geri alma, öneri, Hızlı Teşhis ve haftalık PDF eski sürümle eşleşmeli.
5. Bir fark veya bozulma halinde **hızlı yolu kapatıp** eski davranışı sürdürün. Çalışan EXE'ye veya müşterilere doğrudan dağıtmayın.

## Testler
- `pytest`: seçili 153 test ve 14 alt test başarılı.
- Qt/Windows gerçek arayüz deneyleri bu ortamda yapılamadı. Veritabanı ve Qt tablolarına yönelik daha derin optimizasyonlar, ölçüm olmadan **ertelendi**.
