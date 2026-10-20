# KoçPilot 360 — v3.5.73 / Aşama 14 / HTTPS Anket Rölesi (PİLOT)

## Çalışan kodun kapsamı

- `services/feedback_relay_v3573.py`: **ayrı çalıştırılan** FastAPI rölesi. Tenant/kurum başına SHA-256 ile doğrulanan ayrı API anahtarı gerekir. Sunucunun SQLite kaydı yalnızca rastgele davet referansı, token özeti, ders/konu, cevaplar ve zamanlardan oluşur; `student_id`, `homework_id`, kişi adı veya telefon bulunmaz. Anket formu bir kez yanıtlanır ve 48 saatte biter.
- `services/homework_feedback_cloud_bridge_v3573.py`: Masaüstünden **dışarıya giden HTTPS** bağlantısıyla davet oluşturma ve yanıt çekme. Yanıtın gerçek öğrenci/ödev kimliği yalnızca öğretmenin **yerel** veritabanındaki eşleştirme tablosunda saklanır. Öğrenci–ödev–ödev kümesi sahipliği kontrol edilir. Ağ koparsa cursor ilerletilmez. Başarıda yanıt ve cursor tek SQLite işleminde kaydedilir; tekrar senkronizasyonda yanıt çoğaltılmaz.
- `ui/homework_feedback_bridge_v3571.py`: Halihazırdaki **Anketler → Çevrim İçi** işlevi isteğe bağlı etkin rölede arka plan işçisiyle bağlantı oluşturur; incelerken yanıtları önce senkronize eder. Ana ekran düzeni ve iki ödev formu aynı kalır. Röle kapalıysa Aşama 12/13 davranışı sürer.
- `tools/feedback_relay_cleanup_v3573.py`: Röle kayıtlarının süreli temizlenmesi için açık onaylı CLI (`--dry-run`/`--apply`). Hukuki saklama koşulları kuruma göre kararlaştırılmalıdır.
- `tests/test_feedback_relay_v3573.py`: Yerel sentetik SQLite + HTTP TestClient. Gerçek öğrenci kullanılmadı.

## İki AYRI ortam gerekir

### Sunucu (internet HTTPS reverse proxy arkasında)

Aşağıdakiler örnektir. Gerçek kurum anahtarı gizli ortam değişkeninde tutulmalı, `.env` / GitHub / sohbet ile paylaşılmamalıdır.

1. Python + `fastapi uvicorn python-multipart` kurun; ayrı ve kalıcı diskli barındırma ayarlayın. Ephemeral/kısa ömürlü disk, mevcut SQLite rölesiyle uyumlu **değildir**.
2. `YKS_FEEDBACK_RELAY_DB` = röle sunucusunda mutlak, kalıcı ve erişimi sınırlandırılmış SQLite dosya yolu.
3. `YKS_FEEDBACK_RELAY_PUBLIC_URL` = gerçek **HTTPS** alan adınız (özel bir alt alan adı olabilir; EduTrack alan adına bağımlı değil).
4. `YKS_FEEDBACK_RELAY_TENANT_HASHES` = `{"kurum_kodu":"<64 haneli SHA-256 API anahtarı özeti>"}` biçiminde JSON. Kurumların anahtarları farklı olmalı. Minimum 32 karakterlik rastgele düz anahtar gereklidir.
5. Ayrı sunucu uygulamasını: `uvicorn services.feedback_relay_v3573:app --host 127.0.0.1 --port 8765` komutuyla başlatın; TLS/HTTPS reverse proxy bu porta yönlendirsin.
6. Reverse proxy: HTTPS, HSTS, istek hız sınırı, boyut sınırı, ayrıntılı erişim kontrolü ve güvenli log politikası uygulasın. Yalnızca `/r/<token>` halka açık; `/v14/*` kurum API anahtarı gerektirir.
7. Günlük tutma/backup/veri saklama politikası ve arka plan izleme ayrı yapılandırılmalıdır. Örn. `python -m tools.feedback_relay_cleanup_v3573 --dry-run` ardından onaylı `--apply`.

### Öğretmen Windows masaüstü

1. `YKS_HOMEWORK_FEEDBACK_V12_ENABLED=1` (mevcut mini anket özelliği).
2. `YKS_FEEDBACK_RELAY_V14_ENABLED=1` (yeni bağlantı; varsayılan KAPALI).
3. `YKS_FEEDBACK_RELAY_URL` = sunucudaki aynı HTTPS adresi.
4. `YKS_FEEDBACK_RELAY_TENANT` = ör. `kurum_kodu`.
5. `YKS_FEEDBACK_RELAY_KEY` = o kurumun gizli, rastgele 32+ karakter düz anahtarı. **Öğrenci telefonuna gönderilen bağlantıya veya EXE içine sabit olarak eklemeyin.**
6. Mevcut Anketler → Çevrim İçi menüsünden kayıtlı öğrenci/ödevi seçin. URL panoya kopyalanır; mevcut WhatsApp yöntemiyle **öğretmen gönderir**. Öğrenci tarayıcıdan yanıtlar. Öğretmen "Gelen Yanıtları İncele" menüsüne bastığında röleye giden bağlantı ile yeni yanıtlar alınır, ardından öğretmen onaylar/reddeder.

## Önemli sınırlar ve dağıtım uyarısı

- Bu paket **çalıştırılabilir kaynak kodlu pilot**tur. Biz buradan sunucu/alan adı kurmadık, HTTPS sertifikası bağlamadık, gerçek WhatsApp gönderimi veya gerçek Windows–telefon uçtan uca canlı test yapmadık.
- Sunucu bugün ayrı bir SQLite pilotu. Çok kurumlu ticari üretimde merkezi PostgreSQL, bireysel öğretmen rolleri, kurum/şube yetkisi, anahtar döndürme, KVKK aydınlatma ve veri silme/erişim politikaları, kötüye kullanım koruması, hız sınırı, izleme ve otomatik yedekleme gereklidir.
- Form bağlantısına sahip olmak yanıt verme olanağı sağlar, fakat yanıtlayanın gerçekten öğrenci/veli olduğunu tek başına ispatlamaz. Öğretmen onaylı bile olsa **öz bildirim akademik ustalık kanıtı sayılmaz**.
- Öğretmen bilgisayarı kapalıysa sunucu yanıtı geçici olarak saklar. Öğretmen menüyü açıp güvenli senkronizasyonu çalıştırınca yerel veritabanına alınır. Otomatik arka plan senkronizasyonu/saatlik görev **henüz yok**.
- Eksik veya başka öğrenciye geçmiş ödev için yanıt aktarılmaz. Böyle eşleşmeler sunum için kullanılmaz, ayrı bir teknik reddetme sayacıyla takip edilebilir.
- Eski ana ders/ödev/kitap/ödev kontrol, Hızlı Teşhis, Haftalık Planlayıcı, PDF ve otomatik güncelleme yolu **değiştirilmedi**.

## Kabul testi

1. Windows EXE'de bağlantı oluşturma; öğrenci değişirken işçi sonucu; pencereyi kapatma.
2. Mobil cihaz tarayıcısında HTTPS formu, yanlış/süresi dolmuş/ikinci kullanım link.
3. İnternet kesilip tekrar geldiğinde yanıt alma ve tekrarların tekilleştirilmesi.
4. İki kurumun API anahtarıyla ayrı veriler ve yetki kontrolleri.
5. 20–100 test anketiyle gecikme; sunucu erişim hızı ve saldırı yüzeyi.
6. Öğretmen onayı sonrası Öğrenci 360°, Koç Asistanı ve eski ödev formu karşılaştırmaları.
7. KVKK ve saklama süresi, lisans dağıtımı ve gerçek Windows EXE paketi ile test.

**Canlıya dağıtmayın**: Bu doğrulamaların ardından ayrı onay gerekiyor.
