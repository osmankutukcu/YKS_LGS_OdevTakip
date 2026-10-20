# KoçPilot 360 v3.5.61 — Aşama 2: Ortak Akademik Kanıt Köprüsü

## Gerçekte yapılanlar

- v3.5.60 tam kaynak üzerine **yalnızca yeni dosyalar** eklendi.
- `services/coaching_evidence_hub_v3561.py`: `academic_actions_v3536` ve `coaching_integration_guard_v3560` / `shared_academic_decision_v3530` okumalarını karşılaştırıp **tek, sınırlı, salt okunur akademik sonraki adım kartı** verir.
- Öğrenci kimliği ve kaynak öğrencisi uyuşmazlığı, bağlantı çelişkisi, kısmi veri ve kaynağın okunamaması ayrı sonuçlar olarak belirtilir; bu durumlarda sistem **akademik teşhis üretmez**.
- Öğrenciye ait gecikmiş ödev, plan kontrolü gibi kanıta dayalı önceliklerde bir adet öğretmen önerisi üretir; iki modülden benzer plan önerilerini art arda göstermemeyi hedefler.
- Öğrenme ustalığına dair çıkarım yapmaz; ödev tamamlamayı öğrenme saymaz. Haftalık takvimin, uzak veri kaynağının, müdahale başarısının doğrulandığını iddia etmez.
- Onay gerektirdiğini açıkça bildirir; ödev, öğrenci, veritabanı, gönderim veya UI üzerinde hiçbir değişiklik yapmaz.
- `tests/test_coaching_evidence_hub_v3561.py`: kaynak öğrencisi, tutarsız bağ, veri eksikliği, çakışma, kararsız durum, çift öneri, veri yazmama, `row_factory` ve öncelik senaryoları.

## Test / doğrulama

- İlgili 12 regresyon modülünde 117 test: **BAŞARILI** (2026-10-20 çalışma ortamı, sentetik veriler).
- `tools/v3527_core_guard.py` denetimi: **PASS**. Korunan Ödev Takip ve Ödev Kontrol dosyaları, basit dosya/AST eşleşme denetimine göre değişmedi.
- Yerel Windows GUI ve gerçek kurum veritabanında uçtan uca test henüz yapılmadı.

## Kullanım sınırları

- **Yeni motor henüz ana ekrana/Koç Asistanı'na otomatik bağlanmadı.** Bu, bir sonraki kontrollü entegrasyon aşamasıdır. Bu sürümü yüklemek yeni bir arayüz veya otomatik uyarı sağlamaz.
- Varsayılan olarak pasiftir, hiçbir arka plan görevi başlatmaz.
- Geliştirici, mevcut SQLite bağlantısını aynı tutarlı salt-okunur işlem içinde `read_coaching_evidence_hub(con, verified_student_id, today=...)` çağrısına iletebilir. Gerçek arayüzde sorgular ana UI iş parçacığından uzak tutulmalı, iptal/zaman bütçesi ve bellek kısıtları uygulanmalıdır.
- Bir kaynağın anlaşılmaması, öğrenci başarı/eksiklik hükmü olarak sunulmaz; güvenli doğrulama talebidir.
- Birleşik arayüz, yeni ödev yazma, tekrar takvimi ve otomatik bildirim hâlâ yapılacak işlerdir.

## Temel koruma

Yeni dosyalar dışında mevcut v3.5.60 proje dosyaları korunmuştur. Mevcut Ödev Takip/Ödev Kontrol görünümleri, checkbox, kayıt/geri alma ve kilitler **değiştirilmemiştir**. Testler GUI'nin tüm çalışma koşullarını garanti etmez.
