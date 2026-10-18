# YKS–LGS V12 PWA | Gerçek cihaz pilotu

**Bu eklenti mevcut V12 masaüstü dosyalarını, SQLite şemasını veya senkronizasyon kodunu değiştirmez.** Ayrı bir test veritabanı üzerinden çalışır. Kendi Windows makinenizde test etmeniz gerekir. Gerçek öğrenci verileriyle ilk deneme yapmadan önce yedeğiniz olmalıdır.

## V12'de olan ve eksik kalan

PWA manifesti, uygulama simgeleri, Service Worker, 17 dosyalık önbellek, şifreli offline veri kasası, öğrenci snapshot'ı ve ödev kuyruğu **kaynaklarda mevcut**. Ancak normal `Baslat_Windows.bat` mobil API'yi açmıyor. `launcher.py` de mevcut kaynak ZIP'inde bulunmayan `web_ui` klasörüne ihtiyaç duyuyor. Ek başlatıcı bu iki dosyayı değiştirmeden FastAPI'yi açar.

**Telefon tarafında HTTPS zorunludur:** `http://192.168.x.x:8000` gibi LAN adreslerinden açılan uygulamalar güvenli Service Worker/WebCrypto ortamı sayılmaz. `http://127.0.0.1:8000` yalnızca **Windows bilgisayarın kendi tarayıcısında** güvenli origin istisnasına girer; iPhone'daki `localhost` bilgisayara değil telefona aittir.

## Windows test kopyasını hazırlama

1. `YKS_LGS_V12_Kararli_Surum_Adayi_RC_Kaynak_ve_Kontrol.zip` içeriğini **yeni bir test klasörüne** çıkartın. Bu kiti aynı test klasörüne kopyalayın. Ana program dosyalarının üzerine açmayın.
2. Windows bilgisayarınızda Python ve `requirements_win.txt` bağımlılıkları hazır olmalı. Eksikse test klasöründe `python -m pip install -r requirements_win.txt` (uygun sanal ortamda) çalıştırın. Bağımlılıkları kurarken gerçek ana programa dokunmayın.
3. `PWA_PILOT_HAZIRLA.bat` çalıştırıp mevcut veritabanının **tam dosya yolunu** girin (dışarıdan tırnak işareti eklemeyin). Sık kullanılan konum `%LOCALAPPDATA%\YKS_LGS_HomeworkManager\YKS_LGS_HomeworkManager.db`; taşınabilir kurulumlarda farklı olabilir. Doğru dosyayı doğrulayın. Script kaynak SQLite dosyasını *read-only* açar, veritabanı bütünlüğünü kontrol eder ve `%LOCALAPPDATA%\YKS_LGS_PWA_Pilot\pilot.sqlite3` konumuna güvenli SQLite backup ile ayrı test kopyası alır. Mevcut pilot kopyasını **asla kendiliğinden ezmez**.
4. `PWA_PILOT_BASLAT.bat` çalıştırın. Tarayıcıda `http://127.0.0.1:8000` sayfasını açın. Erişim anahtarı, yalnızca sizin bilgisayarınızın terminalinde gösterilir. **Şifreyi/anahtarı sohbet mesajına göndermeyin.**
5. Ödev yazma denemeleri **pilot kopyaya** kaydedilir; gerçek masaüstü veritabanınıza aktarılmaz. Bu pilot testin başarıyla bitmesi, ana EXE'ye entegrasyonun hazır olduğu anlamına gelmez.

## Telefondan güvenilir HTTPS ile bağlanma — örnek özel ağ

Önerilen pilot çözüm: [Tailscale](https://tailscale.com/) her iki cihazda da kurulup **aynı özel ağa** giriş yapılabilir. Bu, genel internete API yayınlamadan özel ağ HTTPS bağlantısı oluşturma seçeneğidir; kendi kuruluşunuzun güvenlik gereksinimlerini değerlendirin.

1. Windows ve telefon/tablet üzerinde Tailscale bağlantısını etkinleştirin.
2. Windows'ta PWA sunucusu çalışırken **ayrı bir PowerShell penceresinde** `tailscale serve --bg 8000` çalıştırın. Sürüm/hesap izinleri nedeniyle HTTPS etkinleştirme onayı istenebilir.
3. `tailscale serve status` çıktısındaki `https://...ts.net` bağlantısını kopyalayın. **Yalnızca Serve kullanın; herkese açık Funnel kullanmayın.** Bu adresi telefonda Safari/Chrome ile açın.
4. Anahtarı telefonda giriş ekranına girin. İlk veriyi indirmeden bilgisayarı kapatmayın.

Resmî doküman: https://tailscale.com/docs/reference/tailscale-cli/serve

## iPhone / Android PWA testi

1. Bağlantı HTTPS olduğunda önce **📥 İndir** ile verileri alın.
2. **🔐 Çevrimdışı Giriş Ayarla**, ardından **yerel çalışma alanını şifrele** ve **şifreli yedek oluştur** adımlarını uygulayın.
3. **🧪 Çevrimdışı Hazırlık Denetimi** sonucunda HTTPS, Service Worker, 17 dosya, yerel snapshot ve çevrimdışı giriş kontrollerini doğrulayın. Eksik varsa cihazı internetsiz kullanmaya başlamayın.
4. iPhone/iPad Safari: Paylaş > Ana Ekrana Ekle; Android Chrome: Menü > Ana ekrana ekle / Uygulamayı yükle.
5. Ana ekrandaki yeni ikonu **bir kez çevrimiçiyken** açın. Güvenlik panelini kontrol edin.
6. Windows'ta mobil sunucuyu durdurun. Telefonda Wi-Fi ve hücresel veriyi kapatın. İkondan uygulamayı yeniden açıp çevrimdışı giriş yapın. **Yalnızca test öğrencileriyle** bir ödev oluşturun, bir ödevi tamamlayıp geri alın. Bekleyen işlem sayısını not edin.
7. Windows sunucusunu ve bağlantıyı yeniden açın. **🔄 Aktar** düğmesiyle aktarın. Bekleyen işlem sayısını ve **pilot** SQLite kayıtlarını karşılaştırın. Aynı aktarımı tekrar deneyip mükerrer işlem oluşmadığını kontrol edin.
8. İki günlük, ardından yedi günlük gerçek cihaz denemesinde her gün uygulamayı kapatıp yeniden açın; telefon yeniden başlatma, yedek kurtarma ve bağlantı kopması senaryolarını kontrol edin.

## Kabul şartları

- İlk kurulum ve offline hazırlık denetimi başarıyla tamamlanmış olmalı.
- Bilgisayar ve telefon internetsizken uygulama *ikondan* açılmalı.
- Çevrimdışı öğrenci bilgileri görüntülenmeli ve deneme işlemleri kuyrukta kalmalı.
- Yeniden eşitlemede yalnızca bir kez uygulanmalı, masaüstü ödev formuyla test kopyası karşılaştırılmalı.
- Veri silinmesi/kayıp kuyruğu veya çalışmayan yedek varsa **canlıya geçmeyin**.
- **Gerçek 7 günlük saklama ve Windows EXE kabulü** ayrıca yapılmalı. Bir pilot testte sunucu kapalıyken web uygulamasının ilk açılışı cihazın depolama politikasına bağlı kalır.

**Güvenlik notu:** Pilot SQLite kopyasında gerçek öğrenci bilgileri varsa o da kişisel veridir. E-posta veya sohbetle paylaşmayın. Testten sonra manuel olarak güvenli şekilde kaldırın. Ana sistem korunur, ancak bu paket bir canlı üretim dağıtımı değildir.
