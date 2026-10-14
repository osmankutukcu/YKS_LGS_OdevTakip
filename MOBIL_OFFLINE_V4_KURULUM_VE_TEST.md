# YKS–LGS Mobil Offline V4 — Test/Pilot Entegrasyon

## Durum

**Gerçek kullanıcı veritabanına uygulanmamış, test amacıyla hazırlanmış modüler paket.** V3 üzerine eklenir. Windows EXE üretimi ve mobil cihaz testi yapılmamıştır. Canlı çalışan EXE'ye ZIP'i doğrudan kopyalamayın.

## V4 yenilikleri

- Yeni `web_api/static/js/offline_vault.js`: çevrimiçi girişte doğrulanmış erişim anahtarını 12+ karakterli kullanıcı parolasıyla PBKDF2-SHA256 (310.000 tur) + AES-256-GCM kullanarak cihazda şifreli saklama. Bilgisayar kapalıyken anahtar bu parolayla çözülebilir; daha sonra mevcut çevrimdışı snapshot üzerinden mobil sayfa açılır. **Yalnızca giriş anahtarı şifrelenir: IndexedDB snapshot ve outbox şu anda açık veri olarak saklanmaktadır.** Bu özellik tam yerel veri şifreleme değildir.
- Kullanıcı seçimiyle `.yksbackup` şifreli dışa aktarma. Tam snapshot, bekleyen işlemler, varsa şifreli offline erişim kaydı birlikte AES-256-GCM ile korunur. Parola dosyaya konmaz ve sunucuya gönderilmez.
- Yanlış parola veya değişmiş dosya geri yüklenmez; masaüstü `database_id` eşleşmesi aranır.
- Geri yükleme: tek IndexedDB işlemi içinde mevcut kuyruğu korur, yeni işlem ID'lerini sonda ekler, aynı ID ve farklı payload durumunda geri yüklemeyi durdurur. Daha yeni sunucu snapshot'ı seçilir; kalıcı işlem kayıtları asla silinmez.
- PWA shell sürümü `v4` olur; altı kritik bileşenden biri indirilemezse eksik çevrimdışı kurulum etkinleştirilmez.
- Masaüstü çekirdek ve SQLite tablo tanımları değiştirilmez. Mevcut V3 offline sync kodlarına yalnızca yedek geri yükleme sırasında işlemleri durdurma koruması ve senkron başlamadan IndexedDB hazırlanmasını bekleme eklendi.

## Pilot senaryo

1. Mevcut uygulamayı/yedeğini dokunmadan muhafaza edin. **Ayrı test klasörü + kopya SQLite DB** kullanın. Test kaynağına V3, ardından V4 modül yamasını uygulayın. EXE için uygulamanın normal Windows build adımları gerekir.
2. Mobil uygulamayı kalıcı, güvenilir **HTTPS** adresinde açın. `http://192.168.x.x` iPhone PWA'sında güvenilir/offline Service Worker ortamı değildir.
3. Masaüstü açıkken doğru web erişim anahtarıyla giriş yapın; `📥 İndir` ile tam snapshot alın.
4. `🛡 Yedek` panelinden 12+ karakterli güçlü parola belirleyip `🔐 Çevrimdışı Giriş Ayarla` seçin. Parolayı ayrı güvenli yerde saklayın; unutulursa masaüstüne çevrimiçi erişim gerekebilir.
5. `📤 Şifreli Yedek Al` seçip `.yksbackup` dosyasının gerçekten cihazda/kullanıcının belirlediği güvenli konumda bulunduğunu **kendiniz doğrulayın**. Dosya indirme çağrısı dosyanın kalıcı olarak kaydedildiğini garanti etmez.
6. Tarayıcı/PWA'yı tamamen kapatın, bağlantıyı kesin ve yeniden açın. `🔐 Telefon verilerini çevrimdışı aç` ile aynı erişim parolasını girin. Öğrencilerin yüklenmesini ve yeni bir sentetik ödevin kuyrukta kalmasını doğrulayın.
7. Sıfırlanmış ayrı test tarayıcı profilinde `.yksbackup` dosyasıyla `🛟 Şifreli yedekten kurtar` yolunu deneyin. Yedek parolası ayrı, çevrimdışı giriş parolası ayrı olabilir.
8. İnternet ve masaüstü geri gelince `🔄 Aktar` seçin. Sunucudan **onay alan** işlemler telefondan silinir, kalanlar korunur. Aynı yedeği tekrar yükleyip yeniden aktararak idempotency kontrolü yapın.
9. İki cihazın aynı ödevi ters yönde değiştirmesi, 500+ işlemlik sıra, ağ kopması, yanlış DB, cihaz saati, telefon yeniden başlatma ve 7 gerçek gün kesintiyi ayrıca test edin.

## V4 testlerinin kapsamı

- Node.js WebCrypto + tarayıcı IndexedDB davranışını taklit eden test: çevrimdışı anahtar çözme, yanlış parola, gerçek AES-GCM şifreleme/deşifre, şifreli dosyada düz metin görünmemesi, veri silindikten sonra geri yükleme, çift içe aktarmada tek işlem, farklı database_id engeli.
- `python -m pytest -q tests/test_mobile_sync_v3_integration.py tests/test_v134_homework_lifecycle.py tests/test_v135_integrity_audit.py tests/test_v136_safe_reconciliation.py tests/test_write_durability_v354.py` başarılı (84 test + 3 alt test).
- `node --check` ile JS Service Worker, offline_sync ve offline_vault syntax kontrolü.
- Bu ortamın Chromium politikası `ERR_BLOCKED_BY_ADMINISTRATOR` ile yerel deneme sayfasını engellediği için gerçek tarayıcı IndexedDB/PWA E2E, iPhone Safari ve Windows GUI testi henüz yapılmadı. Test doubles ve sentetik SQLite başarılı olsa da gerçek cihaz garantisi değildir.

## Tamamlanmamış üretim riskleri

1. **At-rest şifreleme eksik:** Snapshot ve outbox içindeki öğrenci bilgileri IndexedDB'de hâlâ düz metin bulunabilir. Yerel şifreleme anahtar yönetimi ve cihaz kilidi olmadan gerçek cihaz kaybına karşı uçtan uca gizlilik iddia edilmez.
2. Parolalı çevrimdışı giriş, mevcut uygulamanın oturum akışına isteğe bağlı bir ek katmandır; ayrı rol yetkilendirmesi, cihaz iptali veya 2FA sağlamaz. Kullanılan mevcut yönetici anahtarı offline unlock sonrasında yalnızca `sessionStorage` içinde tutulur.
3. Tarayıcı işletim sistemi, IndexedDB ve Cache Storage'ı temizleyebilir. `navigator.storage.persist()` bazı cihazlarda desteklenmez veya izin vermez; şifreli dışa aktarma kullanıcı tarafından yapılmalıdır.
4. Kullanıcının yedeği alıp güvenli saklaması, çakışma çözümü ve 7 günlük gerçek donanım testi olmadan **“7 gün koşulsuz garantili çevrimdışı çalışma”** iddiası yoktur.
5. Öğrenci/kitap yaratma, çevrimdışı oluşturulmuş ödevin değiştirilmesi, delta snapshot, yetkilendirme iptali, SQLite ABA revizyon kaydı hâlâ kapsam dışıdır.
6. Aynı tarayıcıda birden fazla açık sekmede yedeklemenin eşzamanlı atomik kilidi henüz yoktur; pilotu tek sekmede kullanın. Çalışan ana programın işleyişi değiştirilmemiştir.

## Geri dönüş

Kurulum yalnızca ayrı test klasöründedir. Test klasörünü kaldırarak V3'e dönebilirsiniz. Pilot test veritabanı ile üretim veritabanını karıştırmayın. Öğrenciye ait gerçek veriyi içeren ZIP'i üçüncü kişilerle paylaşmayın. `.yksbackup` dosyasını şifresiz kanaldan iletmeyin; parolayı ayrıca koruyun.
