# KoçPilot 360 — Aşama 13 / v3.5.72 — Onaylı öğrenci–veli yanıtlarının koçluğa bağlanması

## Neler eklendi?

1. `services/homework_feedback_coaching_v3572.py`: yalnızca Aşama 12'deki **öğretmen onaylı** ödev geri bildirimlerini aynı öğrenci ve aynı ödeve ait olacak şekilde, salt okunur SQL bağlantısıyla analiz eden bir sunum katmanı. Eski ödev, öğretmen Hızlı Teşhis, öğrenme ve takvim tablolarına yazmaz. Öğrenci–ödev–ödev kümesi sahipliği yeniden kontrol edilir. Konusu daha sonra değişmiş ödevin geçmiş yanıtı yanıltıcı biçimde yeni konuya atfedilmez.
2. `ui/student360_journey_sidecar_v3566.py`: mevcut Öğrenci 360° arka plan işçisi aynı SQLite **query_only** anlık görüntüsünden, isteğe bağlı Aşama 13 özetini okuyabilir. Ek arayüz veya kontrol oluşturulmadı.
3. `ui/research_coaching_bridge_v3563.py`: mevcut Koç Asistanı bildirim kutusuna aynı öğrencinin en güncel onaylı bildiriminden kaynak etiketi açık bir görüşme önerisi eklenebilir. Ayrı popup, buton veya otomatik gönderim eklenmedi. Öneride öğretmenin onayına, kısa bağımsız ölçüme ve öğrenmenin henüz doğrulanmadığına vurgu yapılır.
4. `tests/test_homework_feedback_coaching_v3572.py`: kimlik, kaynak ve bütünlük testleri; mevcut ödev/hızlı teşhis tablolarının değişmemesi.

## Özellikle korunmuş sınırlar

- `ui/homework_form.py`, `ui/odev_kontrol.py`, `ui/quick_coaching_bridge_v28.py`, Haftalık Planlayıcı ve PDF üreticisi değiştirilmedi.
- Mevcut anket cevaplama formu, API bağlantıları, mevcut öğretmen Hızlı Teşhis ve onay akışları değişmedi.
- Öğrencinin anket işaretlemesi ödevin yapılması, öğretmen teşhisi veya kazanım ustalığı sayılmaz.
- Öğrenci değişirse asenkron bir önceki öğrenci yanıtı yeni öğrenciye gösterilmez.
- Bu özellik için Aşama 12'nin `YKS_HOMEWORK_FEEDBACK_V12_ENABLED=1` pilot seçeneği gerekir. Koç Asistanı kartı ayrıca ayarlar içinden `homework_feedback_coaching_v3572_enabled=0` yapılarak kapatılabilir. Eski özellikler aynen sürer.

## Çevrim içi anket: gerçekte hazır olan ve olmayan

**Hazır pilot kod:** FastAPI `GET/POST /h/{token}` telefon formu, 48 saat geçerli rastgele tek kullanımlık bağlantı, öğrenci/veli ayrımı, form ve öğretmen kabul/red iş akışı. Masaüstü `Anketler → Çevrim İçi` menüsündeki bağlantı panoya kopyalanır. Whatsapp üzerinden *otomatik gönderim yapılmaz*.

**Henüz tamamlanmamış canlı çalışma koşulları:**

- İnternette çalışan gerçek HTTPS servisi ve doğru `YKS_SURVEY_PUBLIC_BASE_URL`.
- Web sunucusu ile öğretmenin **yerel** SQLite kayıtları arasında yetkili iki yönlü iş akışı (yalnızca gerekli davet/yanıt verisi için); çift yazma/çakışma/idempotency kontrolleri.
- Çok öğretmenli/çok kurumlu kurulumda kurum/öğrenci ayrımı, bireysel oturum/rol yetkileri. Mevcut `web_api/auth.py` sadece tek yönetici erişim anahtarıdır; çok kullanıcı yetkilendirme sistemi değildir.
- KVKK veri minimizasyonu, aydınlatma, saklama/silme süresi, yetki ve denetim kayıtları.
- Link ile yanıtlayanın kimliği kesin doğrulanmaz. Ek kimlik doğrulaması ve kötüye kullanım / hız sınırlama üretim öncesi gerekir.
- Sunucu internete açılmadan ve uçtan uca gerçek Windows + telefon testi yapılmadan öğrenci/veli kitlesine link dağıtmayın.

**Önerilen internet mimarisi:** ayrı HTTPS API + asgari veriye sahip merkezi veri deposu + Windows uygulamasından yalnızca dışarıya açılan kimliği doğrulanmış senkronizasyon. Yerel veri tabanını doğrudan internete açmayın. Var olan web giriş anahtarını linke koymayın. EduTrack'in alan adına bağımlılık yoktur.

## Otomatik testler

```
python -m pytest -q \
  tests/test_homework_feedback_coaching_v3572.py \
  tests/test_homework_feedback_v3571.py \
  tests/test_v9_online_survey_flow.py \
  tests/test_survey_evidence_v7.py \
  tests/test_survey_integrity_v8.py \
  tests/test_coaching_integration_guard_v3560.py \
  tests/test_coaching_journey_v3566.py \
  tests/test_coaching_action_center_v3567.py \
  tests/test_automatic_coaching_cycle_v3565.py \
  tests/test_coaching_navigation_v3568.py \
  tests/test_weekly_coaching_alignment_v3570.py \
  -k 'not test_known_plan_approved_topic_mechanism_reused'
```

Sonuç: **121 geçti, 5 atlandı, 1 seçilmedi, 34 alt test geçti.** Erişilemeyen gerçek PyQt6/Windows arayüz ve HTTPS sunucusu ayrı doğrulama gerektirir. Bu bir **pilot kaynak paketidir**; mevcut müşterilere otomatik dağıtılmamalıdır.
