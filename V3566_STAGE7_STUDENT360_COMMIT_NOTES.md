# KoçPilot 360 — Aşama 7 (v3.5.66 PILOT)

## Kaynak ve sınır
v3.5.65 Aşama 6 tam kaynak ZIP üzerine kuruldu. Ödev Takip (`ui/homework_form.py`) ve Ödev Kontrol (`ui/odev_kontrol.py`) dosyaları, checkbox/renk/kilit/kaydet/geri-al/aktar işlemleri, eski Koç Asistanı kodu ve kayıt şemaları değiştirilmedi.

**Bu bir kaynak paketidir.** `version.py` / `version.json` içindeki mevcut uygulama sürümü **3.5.56** olarak bırakılmıştır. Aşama etiketi bir üretim sürümü veya GitHub güncellemesi değildir. Kullanıcının mevcut yüklemesine otomatik dağıtılmamalıdır.

## Teknik değişiklik
1. `ui/research_coaching_bridge_v3563.py` (önceki ek modül) genişletildi. Var olan `ui/live_change_bridge_v241.py`'ın öğrenciye göre filtrelenmiş SQLite `data_version`/snapshot bildirimi kullanılır. **Düğme tıklaması kayıt değildir**; abonelik yalnızca commit sonrası koşullar sağlandığında `_schedule_refresh` çağırır. Mevcut `btnKaydet`/`btnGetir` sessiz yenilemesi de devam eder. 850 ms gecikme, iş kuyruğu ve 2,5 sn sorgu sınırı korunur.
2. `services/coaching_journey_summary_v3566.py` eklendi. Mevcut v3565 karar kartını hiçbir SQL veya öğrenci verisi yazmadan, kimlik ve güvenlik alanları doğrulanarak, kısa Türkçe Öğrenci 360° açıklamasına dönüştürür.
3. `ui/student360_journey_sidecar_v3566.py` eklendi. SQLite `mode=ro` + `PRAGMA query_only=ON`, tek snapshot, arka plan `QThreadPool`, 2,5 sn ilerleme iptali; öğrenci/istek kimliği sonucu göstermekten hemen önce yeniden kontrol edilir.
4. `ui/student360_panel_v16.py` mevcut metin özetinin sonuna isteğe bağlı asenkron alt bölüm çağıracak şekilde genişletildi. Düzen, sekmeler, mevcut butonlar ve eski özet aynen korunur.
5. `tests/test_coaching_journey_v3566.py` kimlik, güvenlik alanları, kanıt yokluğu, otomatik işlem yapmama ve statik entegrasyon kontrollerini test eder.

## Kullanıcı etkisi
- Ödev Kontrol alt penceresi gerçekten kaydedince ilgili öğrenci için Koç Asistanı önerileri sessizce güncellenebilir. 2 saniyelik eski yerel commit izleme aralığına bağlıdır. Başka bilgisayardan bulut senkronizasyonu değildir.
- Öğrenci 360° özeti, v3565 motorunun doğruladığı en fazla iki akademik sonraki adımı açıklayıcı metin olarak gösterir. Motor aksiyon bulamıyorsa veya kanıt güvensizse tahmin yapmaz.
- Öğretmen onayı olmadan otomatik ödev, kontrol işareti, veli mesajı, müdahale veya veritabanı yazımı yapılmaz.
- Yeni Öğrenci 360° alt bölümü `QSettings('EduTrack','HomeworkManagerV2')` içindeki `coaching_journey_v3566_enabled=0` ile kapatılabilir; koçluk asistanı araştırma önerileri önceki `research_coaching_v3563_enabled` ayarına tabidir.

## Bilinen sınırlar
- Mevcut `student_change_scope_v242.py` yalnızca izinli tablo listesini izler; izinli olmayan özel ölçüm tablolarında tek başına commit olursa yeni uyarı anında tetiklenmeyebilir. Öğrenci yeniden seçildiğinde veya Kaydet/Getir sonrası yenilenir. İzlem kaynağının kapsamı sonraki aşamada genişletilmeli.
- Günlük Öğrenci 360° eski özetinin kendi sorguları zaten ana UI tarafında çalışıyor; bu geliştirme yalnızca ek koçluk okumasını arka plana taşır. Çok büyük veritabanlarında bütün panel için performans testi gerekir.
- Windows PyQt6 çalışma zamanı, gerçek DB ve ekran/ölçekleme testi yapılmadı. Sistemi **üretime hazır** olarak nitelendirmeyin.
- Koç Asistanı eylem butonu var olan Öğrenme ekranına yönlendirir. Öğretmen onayını aşan otomatik Sihirbaz ataması yoktur.

## Test
`python -m unittest -q tests.test_coaching_journey_v3566 tests.test_automatic_coaching_cycle_v3565 tests.test_science_wizard_alignment_v3564 tests.test_evidence_based_coach_v3563 tests.test_learning_intervention_bridge_v3562 tests.test_coaching_evidence_hub_v3561 tests.test_coaching_integration_guard_v3560 tests.test_v3538_intervention_followup tests.test_adaptive_coaching_v25 tests.test_adaptive_draft_review_v30 tests.test_coach_module_bridge_v264 tests.test_coach_decision_hub_v265 tests.test_v3536_academic_actions tests.test_wizard_student_transfer_v8 tests.test_coaching_safety_v244 tests.test_core_integrity_v133`

`python tools/v3527_core_guard.py --root .`

Seçili regresyon testleri: **155 başarılı**, çekirdek koruma PASS. PyQt6 Windows UAT henüz yapılmadı.

## Windows kabul senaryoları
1. v3.5.65 ile v3.5.66 ödev takip/kontrol formu checkbox, geri-al, kilit, renk, kaydet ve kontrol sonrası satır davranışını ekran videosuyla karşılaştırın.
2. Öğrenci A için Ödev Kontrol alt penceresinde gerçekten kaydedin; pencereden döndükten sonra 2–5 saniye içinde Koç Asistanı'nın gelen kutusunu kontrol edin. Yalnızca Kontrol penceresini açıp kapatınca kayıt oluşmamalı.
3. A'nın seçimini B'ye değiştirin; A'ya ait koçluk içeriği B'de gözükmemeli.
4. Öğrenci 360°'de eksik kanıt ve gerçek onaylı müdahale örnekleriyle yeni bölümün sadece doğrulanmış önerileri gösterdiğini denetleyin.
5. V3566 yan özet özelliğini kapatın; ana Öğrenci 360° ve eski Koç Asistanı çalışmaya devam etmeli.
6. Yavaş/kitli SQLite ve büyük sınıflar için kayıt sonrası tıklama gecikmesi ile bellek tüketimini ayrıca ölçün.
