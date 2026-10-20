# KoçPilot 360 v3.5.76 — Baileys Windows Kurulum ve Sağlık Denetimi (Pilot)

## Amaç

Ekranda görülen `Node.js 20+ bulunamadı` hatasını *gönderimden önce* tespit etmek, eksik Node.js/npm bileşenleri için bir kez izin alarak Windows paket yöneticisiyle kurmayı denemek, npm kurulumunun **gerçek bitiş kodunu** beklemek ve başarılı bağımlılık/protokol testinden önce QR/gönderimi hazır ilan etmemek.

## Değişen dosyalar

- `ui/baileys_bulk_v258.py`: Kur/Güncelle artık `os.startfile` yerine Qt `QProcess` ile asenkron yürür; Windows `winget` varsa, kullanıcı onayıyla Node.js LTS kurulumunu dener; npm kurulumu ayrı onayla yapılır. Durum ve hata kodu görünür. İşlem sürerken gönderim kilitlenir. QR bağlantısı için ayrıca onay gerekir.
- `services/whatsapp_queue/baileys_bulk_v258.py`: Başlatma ön koşulu, yeni Node/npm keşif modülünü kullanır. Aynı eksiksiz eski Baileys sürüm ve bütünlük denetimi korunur.
- `services/whatsapp_queue/baileys_node_v257/Windows_Hazirla_V258.cmd`: Node 20+ sürüm kontrolü, isteğe bağlı etkileşimsiz onay belirteci, net çıkış kodları, `npm ci --ignore-scripts`, eski paket kilidine sadakat ve gönderimsiz Node protokol testleri.

## Yeni dosyalar

- `services/whatsapp_queue/baileys_runtime_v3576.py`: Salt okunur Windows Node/npm/winget keşif ve hata açıklama fonksiyonları.
- `tests/test_baileys_install_v3576.py`: Bağlantı, indirme ve mesajlaşma yapmayan sahte Windows testleri.
- `V3576_BAILEYS_GUVENLI_KURULUM_NOTLARI.md`: Bu rapor.

## Windows kullanım akışı

1. İletişim → WhatsApp → Baileys izinli toplu gönderim; alıcıları kontrol edin.
2. **Baileys Windows Motorunu Kur / Güncelle** düğmesine basın.
3. Node.js/npm zaten varsa program sürümleri denetleyip Baileys bağımlılıkları için izin ister. Node eksikse `winget` uygunsa **açık kullanıcı izni** ile resmî `OpenJS.NodeJS.LTS` paketini kurmayı dener. `winget` yoksa resmî Node.js sayfasını açmayı önerir.
4. Baileys bağımlılıkları kullanıcı profiline yüklenir; `npm ci` ve gönderimsiz protokol testleri tamamlanmadan **hazır** sayılmaz. Eski Node.js/npm veya başarısız indirmede mesaj gönderimi engellenir.
5. **QR bağlantısını başlat** ve gönderim, her alıcının bildirime izni doğrulandıktan ve son onay alındıktan sonra ayrıca gerçekleştirilir.

## Korunanlar

Ödev Takip, Ödev Kontrol, Öğrenci 360°, PDF, Haftalık Planlayıcı, web API, lisanslama ve eski Selenium/WhatsApp Masaüstü/WhatsApp Web bileşenlerine dokunulmadı. Baileys kuyruk şifrelemesi (DPAPI), ret listesi, kişi başına çakışma koruması, en fazla 150 alıcı, teslim belirsizliğinde yeniden göndermeme kuralları korunur.

## Önemli sınırlamalar

- **Windows'ta `winget` veya Node.js indirmesi bu geliştirme ortamında gerçek olarak denenmedi.** Qt arayüzünün, Windows EXE'nin ve fiziksel QR eşleştirmesinin kabul testleri gerekiyor.
- Uygulama açık kullanıcı onayı olmadan yazılım indirmez; kurulumda Windows izin pencereleri veya yeniden açma gerekebilir. `winget` her Windows sürümünde veya her kurum politikası altında çalışmayabilir.
- Projede kullanılan Baileys sürümü hâlen `7.0.0-rc14` olarak sabittir. Bu sürümün gelecekte WhatsApp ile uyumlu kalacağı garanti değildir.
- Baileys resmî WhatsApp Business API değildir, hesap kısıtlaması riski vardır. Bağlantı ve istemci kabulü **mesaj tesliminin garantisi değildir**.
- Bu kaynak ZIP bir **pilot geliştirme paketidir**. Windows testleri tamamlanmadan müşterilerin otomatik güncelleme kanalına yüklenmemelidir.

## Gerçek Windows kabul senaryoları

1. Node kurulu değil, `winget` var → kullanıcı onayı → kurulum → npm/protokol testi → QR.
2. Node kurulu değil, `winget` yok → resmî indirme sayfası / açık yönlendirme.
3. Node 18 veya npm eksik → güvenli engelleme ve doğru açıklama.
4. Node LTS yüklü, PATH henüz yenilenmedi → ortak kurulum klasörü algılanması.
5. İnternet veya npm kesintisi → başarısız çıkış kodu, göndermeme.
6. QR eşleştirme başarısı → yalnızca tek izinli test alıcısı; teslim durumu manuel kontrol.
7. Başlatma sırasında kesinti → kuyruğun bekleyen ve sonucu belirsiz kayıtları otomatik tekrar göndermemesi.
8. Eski Selenium, WhatsApp Web ve Masaüstü modları ve iki ana formun değişmeden çalışması.
