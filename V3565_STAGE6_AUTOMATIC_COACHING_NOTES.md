# KoçPilot 360 v3.5.65 — Aşama 6: Otomatik Akademik Koçluk Döngüsü (Pilot)

## Başlangıç sürümü
v3.5.64 Aşama 5 tam kaynak paketi. Eski 782 dosyanın **tamamı korunur**. Önceden mevcut dosyalardan yalnızca yeni nesil isteğe bağlı `ui/research_coaching_bridge_v3563.py` güncellendi; Ödev Takip, Ödev Kontrol, eski Koç Asistanı, orijinal Akıllı Sihirbaz ve veritabanı koduna müdahale edilmedi.

## Eklenen parçalar
- `services/automatic_coaching_cycle_v3565.py`: mevcut doğrulanmış ödev/öğrenme kanıtlarını ve yalnızca öğretmenin kaydettiği V11 müdahale izlem kayıtlarını birleştiren salt okunur karar döngüsü. En fazla iki farklı, çakışmayan adım önerir.
- `tests/test_automatic_coaching_cycle_v3565.py`: kimlik/tarih/sahiplik, kaynak güvenliği, öncelik, tekrarlı tavsiye önleme, bekleyen müdahale kontrolü, gelecekteki öneri tarihi, öğrenci izolasyonu ve salt-okunur testler.
- Bu belge.

## Koçluk karar sırası
1. Akademik kaynaklardan biri doğrulanamadıysa hiçbir eylem önerme (DATA_REVIEW).
2. V11'de daha önce **öğretmenin kaydettiği** ve ölçüm zamanı gelen müdahale için yeniden ölçüm/yorum hatırlatması (müdahale yazılmaz).
3. V25 bağımsız soru sonuçlarından hedefli inceleme/yeniden kontrol/aralıklı hatırlama önerisi (önceden var olan V3562 hesaplarını tekrar kullanır).
4. Bağımsız öğrenme gözlemi hiç yoksa ve V3535 kanonik öğrenciye ait tamamlanan ödevler güvenle saptanabiliyorsa **konusuz, isteğe bağlı** kısa yoklama önerisi. Tamamlanmanın tarihi ve öğrenme düzeyi uydurulmaz.
5. Öğretmen tarafından zaten incelenmiş veya zamanı gelmemiş izlem bir alarm sayılmaz.

## Arayüz ve otomasyon sınırları
- Program kullanıcıya yeni pencere açmaz. Çıktı, mevcut asistanın gelen kutusunda ancak öğrenci seçimi veya eski Kaydet/Getir kontrolü sonrası kısa gecikmeyle işlenir.
- Yalnızca `INTERVENTION_FOLLOWUP` veya `OPTIONAL_INDEPENDENT_CHECK` yeni gelen kutusu kartı olur; konu odaklı V25 araştırma tavsiyeleri zaten eski V3563 kartlarında bulunur; böylece öğretmeni yinelenen kartlarla bunaltmayız.
- `btnKontrol` açılması bir veri kaydı yapıldığı anlamına gelmediği için yeni kaydetme sinyali olarak kullanılmaz. **Ödev Kontrol alt formundaki kayıt tamamlanması henüz doğrudan otomatik tetiklenmiyor**; yeni kart öğrenci seçimi/kaynak ana formu Kaydet/Getir sonrası yenilenir. Bu, bir sonraki kontrollü entegrasyon konusudur.
- İşlemler mevcut QThreadPool / 2,5 sn SQLite ilerleme-iptal mekanizmasında; arayüz iş parçacığında SQL yok. Saha performansı ölçümü yapılmadı.
- Sistem QSettings `research_coaching_v3563_enabled` anahtarı üzerinden mevcut araştırma asistanıyla birlikte kapatılabilir. Gelecekte bağımsız kullanıcı anahtarı eklenebilir.

## Bilimsel doğruluk ve güvenlik
- Ödevin tamamlanması konu öğrenimini kanıtlamaz.
- Tek öğretmen gözlemi kesin neden değildir; müdahale öncesi/sonrası ilişki nedensel etki değildir.
- Sabit kişisel unutma yüzdesi, başarı artışı garantisi, otomatik tanı, psikolojik değerlendirme yoktur.
- Otomatik ödev ataması, checkbox işaretleme, kontrol kaydı, mesaj, şema migrasyonu ve öğrenciye veri yazımı yoktur.
- Üretilen eylem öğretmen onaylı yorum/ölçüm tavsiyesidir.

## Test / yayın durumu
- Seçili regresyon grubu: 146 otomatik test başarılı; kod ve bütünlük koruması geçiyor.
- Test komutu: `python -m unittest -q tests.test_automatic_coaching_cycle_v3565 tests.test_science_wizard_alignment_v3564 tests.test_evidence_based_coach_v3563 tests.test_learning_intervention_bridge_v3562 tests.test_coaching_evidence_hub_v3561 tests.test_coaching_integration_guard_v3560 tests.test_v3538_intervention_followup tests.test_adaptive_coaching_v25 tests.test_adaptive_draft_review_v30 tests.test_coach_module_bridge_v264 tests.test_coach_decision_hub_v265 tests.test_v3536_academic_actions tests.test_wizard_student_transfer_v8 tests.test_coaching_safety_v244 tests.test_core_integrity_v133`
- Korunan çekirdek: `python tools/v3527_core_guard.py --root .`
- **Windows PyQt6 kullanıcı arayüzü, gerçek veritabanı performansı, Ödev Kontrol kayıt sonrası yenileme ve canlı dağıtım testi yapılmadı.** Paket pilot kaynak koddur, üretime otomatik geçirilmemelidir.

## Windows kabul testleri
1. Önce v3.5.64 üzerinde kayıt, geri alma, checkbox renk, kilit, satır tıklama ve öğretmen seçimi videosunu/referansını alın. v3.5.65 ile birebir karşılaştırın.
2. 1. öğrenci seçin; Koç Asistanı gelen kutusunu inceleyin. İkinci öğrenciye geçerek içerik karışmadığını teyit edin.
3. Öğrenme ölçümü olmayan ama doğrulanmış tamamlanan ödev bulunan öğrenciyle isteğe bağlı kısa yoklama kartını kontrol edin. Yetersiz şema varsa kart olmamasının güvenlik davranışı olduğunu doğrulayın.
4. V11 müdahale kaydı ve günü gelmiş izlem olan öğrencide bir hatırlatma göründüğünü, başka müdahale kaydı yazılmadığını doğrulayın.
5. Kaydet/Getir ardından asistan güncellesin; checkbox anında SQL çalışmasın, tıklama gecikmesi artmasın.
6. Müdahale takibi veya öğrenme tablosu bozuksa veri değişmeden sistemin eski işlevleri kullanılmaya devam etsin.
7. Özellik kapalıyken yeni arka plan okuması yapılmasın.
