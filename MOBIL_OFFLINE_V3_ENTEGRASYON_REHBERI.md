# YKS–LGS Ödev Takip — Mobil Offline V3, GÜVENLİ PİLOT

**Durum:** Ana kaynakla gerçek kod uyumluluğu karşılaştırıldı. Masaüstü kritik regresyonları geçti. **Canlı kurum verisine veya Windows kurulu EXE'ye doğrudan uygulanmamalı.**

## Kapsam

Kaynak: `YKS_LGS_HomeworkManager_v2_Guncel_Gelistirici_Yedegi.zip`. Önceki bağımsız modül kaynağı: `Mobil_Web_Ve_Offline_Sync_Kodlari.zip`; V2 iyileştirmeleri: `Mobil_Offline_SafePilot_V2_Denetim_ve_Kod.zip`.

**Değiştirilmeyen çekirdek dosyalar:** `db.py`, `main.py` (web API), `main_window.py`, `ui/homework_form.py`, `web_api/homework_store.py`, Windows güncelleme sistemi. Bu dosyalar ana ZIP'deki haliyle korundu.

Yeni modül/sınırlı değişiklikler:

- `web_api/sync_transactions.py` **yeni** — tek SQLite işlemi içinde ödev/durum yazımı + kalıcı işlem fişi, yanlış DB/şema koruması, eşzamanlı tekrar gönderme koruması, önkoşul/fingerprint çatışma tespiti, çevrimdışı tarih koruması.
- `web_api/sync_engine.py` — snapshot + sunucu işlemleri bazında onay; hatalı işlemden sonra sıralı erteleme; tutarsız snapshot'ı reddetme; öğrenciye ait ödevlerin fingerprint değerleri.
- `web_api/static/js/offline_sync.js` — IndexedDB transaction tamamlanma garantisi, işlem UUID'si, FIFO outbox, sadece onaylananları silme, sayfalı aktarma (100 işlem), bekleyen işlerin offline görünüme yansıtılması, masaüstü durum çakışması önkoşulları, tek öğrenci snapshot'ını yanlışlıkla tam paketin üstüne yazmama.
- `web_api/static/sw.js` — kök sayfa çevrimdışı cache kapsamı, öğrenci içeren API yanıtlarını Cache Storage'a yazmama.
- `web_api/templates/index.html` — `/sw.js` kök kaydı, aktarımda başarısızlık/eksik işlem uyarıları, Apple dokunmatik ikonu.
- `web_api/static/manifest.json`, `icon-192.png`, `icon-512.png`, `apple-touch-icon.png`, `favicon.png` — mevcut logo üzerinden uygun boyutlu PWA ikonları.
- `tools/offline_sync_preflight_v3.py` **yeni** — salt okunur veritabanı denetimi ve isteğe bağlı doğrulanmış SQLite Backup API yedeği.
- `tests/test_mobile_sync_v3_integration.py` **yeni** — gerçek projenin `db.init_db()`, `web_api.main.create_homework()` ve `sync_transactions` üzerinden sentetik SQLite ile entegrasyon testleri.

### Veritabanı etkisi

Mevcut `ogrenci`, `odev`, `odev_satir`, `odev_kume`, `kitap` tabloları ve kayıtları değiştirilmez. Ancak ilk eşitlemede **aynı SQLite dosyasında iki yeni yardımcı tablo** oluşturulur: `mobile_sync_identity` (DB kimliği) ve `mobile_sync_receipts` (işlem başına idempotent onay kaydı). Bu nedenle test veritabanı ve gerçek yedek olmadan üretime geçirilmemelidir.

## Güvenli deneme adımları

1. Çalışan programın KLASÖRÜNE kesinlikle dosya kopyalamayın. Ayrı bir test klasörüne orijinal güncel kaynakları çıkarın. Yedeklemeden önce canlı masaüstü uygulamasının kapalı olduğundan ve aktif DB yolunun gerçekten doğru olduğundan emin olun.
2. Veritabanının doğru yolunu masaüstünün DB bilgi panelinden veya `db.DB_PATH` üzerinden doğrulayın. ZIP'de birden fazla `.db` vardır; rastgele dosya seçmeyin.
3. Test klasöründe terminalden `python tools/offline_sync_preflight_v3.py --db "AKTIF_VERITABANI_YOLU" --backup "YEDEK_KLASORU"` komutunu çalıştırın. Program canlı DB'de DML/DDL yazmaz; doğrulama sonrası SQLite Online Backup ile **ayrı** yedek dosyası oluşturur.
4. Yalnızca test kaynaklarına `YKS_LGS_Offline_V3_Guvenli_Moduler_Yama.zip` içindeki göreli yolları uygulayın. **EXE** çalıştırıyorsanız kaynak ZIP'inin kendisi EXE'yi güncellemez; mevcut build/yayın süreciyle test EXE'si üretmeniz gerekir.
5. Python test ortamında `python -m pytest -q tests/test_mobile_sync_v3_integration.py` çalıştırın. Başka bir sanal ortamda diğer masaüstü regresyonlarını yeniden çalıştırın.
6. Windows bilgisayar + Android Chrome ve iPhone Safari/PWA üzerinde **kalıcı, güvenilir HTTPS origin** kullanarak ayrı test öğrencileriyle deneme yapın. `http://192.168...` üzerindeki Service Worker iOS'ta güvenilir bir PWA kurulumu sağlamaz.
7. Önce 1 gün, ardından 7 gün internet kesintisini ve bilgisayar kapanmasını simüle edin. Uygulamayı tamamen kapatıp açma, telefonun kapanması, 500+ komut, iki cihaz, ağ yanıtının kaybolması senaryolarını tekrar edin; ödevleri masaüstünde satır satır karşılaştırın.
8. Hata veya belirsizlikte eşitlemeyi durdurun; telefondaki bekleyen işlem kuyruğunu otomatik temizlemeyin. Test klasörünü silerek eski sürüme dönün; canlı veritabanına dokunmayın.

## Kalan kritik üretim engelleri

- **7 gün çevrimdışı güvenli oturum:** `sessionStorage` ile çevrimdışı yeniden giriş yetersiz. Şifrelenmiş yerel profil, cihaz bazlı offline PIN/parola ve oturum yönetimi henüz yok.
- **Cihaz verisi saklama:** IndexedDB tarayıcı/OS tarafından silinebilir. `navigator.storage.persist()` talebi desteklenen tarayıcılarla sınırlı. Şifreli dışa aktarım/yedek geri yükleme henüz yok.
- **Mobil tam kapsam:** Öğrenci ekleme/düzeltme, kitap tanımlama/atama, çevrimdışı yaratılmış ödev üzerinde henüz sync olmadan durum değiştirme gibi işlemler eksik. Mevcut ödev verme ve mevcut ödev durumu birinci pilot kapsamıdır.
- **Çoklu cihaz:** Önkoşul ve fingerprint çatışmalarının yakalanması eklendi; kullanıcıya iki sürümü gösteren çatışma çözüm ekranı henüz yok. Aynı durumun tekrar oluştuğu ABA senaryosunda fingerprint yetersiz olabilir; kalıcı revizyon kaydı gerekir.
- **Sabit HTTPS adresi:** Masaüstü web arayüzü şu an yerel HTTP/IP ve opsiyonel tünel üzerinden açılıyor. PWA'nın offline başlangıç için HTTPS üzerinden bir kez kurulmuş ve gerekli dosyalarının cache'lenmiş olması gerekir.
- **Güvenlik:** Var olan web erişimi tek yönetici anahtarıdır. Yerel snapshot IndexedDB içinde henüz uçtan uca şifreli değildir. Üretim için cihaz bazlı erişim/iptal ve şifreli yerel veri gerekiyor.
- **Ölçek ve tarihler:** Snapshot, tüm öğrenci/ders verisini sorgulayarak oluşturuluyor; çok büyük kurumlar için sayfalı ve delta-pull gerekir. Eşzamanlı DB değişiminde paket bu sürümde fail-closed olur.
- **iOS/Windows uçtan uca test:** Bu ortamda iPhone/Android/gerçek Windows GUI çalıştırılmadı. Service Worker / PWA tarayıcı senaryosu henüz doğrulanmadı.

## Test sonucu (bu çalışma oturumu)

- `tests/test_mobile_sync_v3_integration.py`: **7/7 geçti**; ana SQLite şeması, web API ile eşdeğer atama kayıtları, tarih, fingerprint, tekrar onayı, 500 işlem, kısmi hata.
- Seçili mevcut masaüstü testleri: `test_v134_homework_lifecycle`, `test_v135_integrity_audit`, `test_v136_safe_reconciliation`, `test_write_durability_v354`: **77 test + 3 alt test geçti**.
- `python -m compileall` ve `node --check` tamamlandı.
- **Çalışmayan testleri geçmiş saymıyoruz:** gerçek Windows PyQt GUI, iPhone/Android PWA ve 7 günlük donanım testi.

**Kurulum kararı:** Geliştirici test/pilot sürümü. Çalışan öğretmen verileriyle otomatik canlı güncelleme değildir.

## Kaynak paketin içerik sınırı

Veri içermeyen kaynak kopyası, özgün arşivdeki öğrenci/ayar SQLite dosyalarını, kişisel `plan_profiles.json` dosyasını, IDE önbelleklerini, özel yönetici yardımcılarını ve font dosyalarını **bilerek içermez**. Orijinal çalışma dosyaları ve gerekli lisanslı font/kurulum bağımlılıkları, kullanıcıdaki güvenli kopyasında muhafaza edilmelidir. Dolayısıyla bu ZIP, tek başına kurulum EXE'si değildir.
