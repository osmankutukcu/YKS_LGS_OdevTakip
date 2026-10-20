# KoçPilot 360 — v3.5.71 / Aşama 12: Ödeve bağlı öğrenci–veli mini geri bildirimleri

## Amaç

Ödev Kontrol'deki mevcut **Hızlı Teşhis** öğretmen gözlemini değiştirmeden,
öğrenciden ve veliden bir ödev için kısa (3 adet 1–5 değerlendirme ve bir güçlük
seçimi) geri bildirim almak; yanıtları öğretmen onayına kadar ayrı tutmak.

## Mevcut modüller yeniden yazılmadı

- `ui/homework_form.py` ve `ui/odev_kontrol.py` değiştirilmedi.
- `ui/quick_coaching_bridge_v28.py` ve
  `services/adaptive_coaching_v28/quick_notes.py` değiştirilmedi.
- Haftalık Planlayıcı, rutin profilleri, PDF üreticisi, mevcut öğretmen koçluğu
  ve verilen ödev kayıt sistemi değiştirilmedi.
- Eski dokuz anket ve V9 çevrim içi anket akışları korunuyor.

## Yeni / değişen kod

- `services/homework_feedback_v3571.py` **yeni**: ödev sahipliği doğrulaması,
  tek kullanımlık 48 saatlik linkler, yanıt kaydı, öğrenci ve veli kaynak ayrımı,
  öğretmen onayı ve salt okunur özet.
- `web_api/homework_feedback_v3571.py` **yeni**: HTTPS altında tek kullanımlık
  mobil form, açık rıza/onay kutusu, yönetici API'leri, HTML kaçışları,
  `no-store`, CSP ve yerinde sınırlı giriş doğrulaması.
- `ui/homework_feedback_bridge_v3571.py` **yeni**: mevcut Anketler panelinden
  ödev seçimi, bağlantıyı panoya kopyalama, bekleyen geri bildirim inceleme,
  kabul / ret. Koçluk/checkbox müdahalesi yok.
- `ui/survey_manager.py` **değişti**: var olan `Çevrim İçi` düğmesinin menüsüne,
  sadece özellik etkinleştirildiğinde 3 seçenek eklendi; yeni ana buton yok.
- `web_api/main.py` **değişti**: yeni router ve sadece `/h/<token>` GET/POST
  için anonim form erişim izni. `/api/...` uçları yine mevcut X-Access-Key
  middleware ile korunuyor.
- `tests/test_homework_feedback_v3571.py` **yeni**: sentetik SQLite veriyle
  sahiplik, tek kullanım, kimlik tutarlılığı, öğretmen onayı, eski verilerin
  değişmemesi, API yetkisi ve mobil gönderim testleri.

## Kullanım / Pilot etkinleştirme

1. Öğretmen bilgisayarında önce veritabanını yedekleyin; kaynak paketi
   çalışmakta olan müşteri EXE'si yerine doğrudan yayınlamayın.
2. Yalnızca test ortamında `YKS_HOMEWORK_FEEDBACK_V12_ENABLED=1` kullanın.
   Varsayılan durumda yeni menü görünmez ve mobil form özelliği kapalıdır.
3. `YKS_SURVEY_PUBLIC_BASE_URL=https://<gerçek-anket-hostu>` değeri,
   etkin HTTPS sunucusunu göstermelidir. Alan adı uydurmayın.
4. Telefon kullanıcılarının açtığı FastAPI sunucusu, öğretmenin veri tabanına
   **yetkili ve güncel** erişime sahip olmalıdır. Öğretmenin yerel SQLite
   dosyası bir bulut sunucusundan kendiliğinden erişilebilir değildir; uzak
   bağlantı ve güvenli senkronizasyon ayrıca kurulmadan gerçek öğrencilere
   bağlantı dağıtmayın.
5. Mevcut `Anketler → Çevrim İçi` menüsünden öğrenci/veli mini formunu seçin.
   Ödev seçildiğinde **yalnızca link panoya kopyalanır**. WhatsApp otomatik
   gönderimi yapılmaz; öğretmen mevcut gönderim kanallarında isterse paylaşır.
6. Yanıtlar `Gelen ödev geri bildirimleri` menüsünde öğrenci bağlamıyla
   gösterilir; öğretmen onayladığında bile eski `adaptive_quick_note_v28`,
   `odev`/`odev_satir`, `ogrenci_anket` ve PDF/plan kayıtlarına yazılmaz.
7. Onaylı geri bildirim `approved_summary(student_id)` ile ayrı, açık kaynak
   etiketli, yalnızca görüşme desteği olarak okunabilir. Ortak öğrenme motoruna
   ustalık/başarı kanıtı olarak otomatik bağlanmaz.

## Güvenlik sınırları ve kalan işler

- Davet, belirli aktif öğrenci + o öğrenciye ve kümesine ait ödeve bağlanır.
- Student/parent türü link oluşturulurken atanır; bağlantı başkasına
  iletilirse gerçek yanıtlayanın kimliği **kesin doğrulanamaz**. Üretim öncesinde
  alıcı doğrulaması/erişim ve veri koruma süreçleri ayrı değerlendirilmelidir.
- Tokenın düz metni veritabanında saklanmaz; SHA-256 özeti saklanır.
- Öğrenciye ve veliye sorulanlar psikometrik test değildir. Gönüllü yanıtlar
  kesin kök neden, nesnel ödev tamamlama veya öğrenme kanıtı değildir.
- Yeni tablolarda silme/retention takvimi ve kayıtların kullanıcılar arası
  senkronizasyonu kurum dağıtımı öncesi tasarlanmalıdır.
- Açık HTTPS pilotu gerçek Windows/PyQt6 uygulaması ve gerçek ağ ortamında
  ayrıca test edilmelidir. Mesaj gönderim servisleriyle uçtan uca test yoktur.

## Test

Komut:

```
python -m pytest -q \
  tests/test_homework_feedback_v3571.py \
  tests/test_v9_online_survey_flow.py \
  tests/test_survey_evidence_v7.py \
  tests/test_survey_integrity_v8.py \
  tests/test_coaching_integration_guard_v3560.py \
  tests/test_automatic_coaching_cycle_v3565.py \
  tests/test_coaching_action_center_v3567.py \
  tests/test_weekly_coaching_alignment_v3570.py \
  -k 'not test_known_plan_approved_topic_mechanism_reused'
```

Sonuç: **97 başarılı, 5 atlandı, 1 seçilmedi, 25 alt test başarılı**.
Seçilmeyen test `PyQt6.QtPrintSupport.QPrinter` bağımlılığı nedeniyle bu
ortamda çalışmıyor; Windows'ta gerçek PDF/plan bütünlüğü doğrulanmalı.

Bu bir **pilot kaynak kod sürümüdür**; canlı dağıtım onayı değildir.
