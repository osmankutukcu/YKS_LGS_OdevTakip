# V3.5.2 Windows kabul ve pilot testleri

Testler **yalnızca sahte veri** ile ve kurulu uygulama kopyasında çalıştırılmalıdır. Üretim veritabanını kopyalayıp üzerinde deneme yapmayın.

## Kontrol listesi

- [ ] Windows 10 ve Windows 11: ilk kurulumda UAC/izin, açılış, kısayol, program kapat-aç
- [ ] 3.5.0 -> 3.5.2 manuel yükseltme: veri kopyası hash/bütünlük ve kayıt sayısı değişmiyor
- [ ] Güncelleme Release: `v3.5.2` etiketinden EXE+sha256 indiriliyor, `v3.5.3` prova ile yeni güncelleme algılanıyor
- [ ] İndirme bağlantısı kesilince mevcut kurulum ve veritabanı korunuyor
- [ ] Yanlış SHA256 veya indirilen HTML/ZIP dosyası kurulmuyor
- [ ] Güncelleme öncesi aktif DB bulunamazsa kurulum başlamıyor
- [ ] Program açıkken SQLite WAL ek kayıtları ile yedek tutarlı
- [ ] Boş veritabanı ve bozuk dosya güvenli hata veriyor; boş ZIP başarı sayılmıyor
- [ ] Yedekten geri yüklenmiş kopyada öğrenci, ödev, kitap, program verileri eşit
- [ ] Öğrenci ekle/düzenle/kapat-aç/sil; aynı kayıt iki kere eklenmiyor
- [ ] Ödev tekli/çoklu verme, aynı konuyu tekrar verme, geri alma, bitiş tarihi
- [ ] Ödev başlık/satır ve web/mobil paneli aynı sonucu gösteriyor
- [ ] Web API `/api/students`: anahtarsız 401, doğru anahtarla 200
- [ ] Web paneli ilk açılışta erişim anahtarı ekranı; yanlış anahtar reddediliyor
- [ ] Anahtar sistemden başka kişilere açılmadan güvenli kanal ile aktarılabiliyor
- [ ] Öğrenci telefonu/notu linklere, hatalı cevaplara veya günlüklerde sızmıyor
- [ ] Web ekranındaki özel karakterleri ve HTML içeren sahte öğrenci adı ekranda düz metin gösteriliyor
- [ ] Ayrı bir kullanıcı/veli rolü mevcut değildir: anahtar velilere gönderilmiyor
- [ ] Web HTTPS/ngrok güvenilir alanda çalışıyor; HTTP üzerinden gerçek veri kullanılmıyor
- [ ] Raporda Türkçe karakter, grafik, yazdır/PDF çıktıları çalışıyor
- [ ] Koçluk programı, sınav puan/net hesapları örnek referanslarla karşılaştırılıyor
- [ ] WhatsApp mesajı prova modunda hazırlanıyor, gerçek numaraya gönderilmiyor
- [ ] 100/1000/5000 deneme ödevinde arama ve açılış tepki süreleri ölçülüyor
- [ ] %100/%125/%150 DPI, küçük pencere, tablet/telefon en boy oranı kontrolü
- [ ] Kurulum geri alınırsa önceki EXE ve veri yedeği kontrollü geri getiriliyor

## İmza/onay

Bu dosyadaki hiçbir kutu, yalnızca kaynak kod testleri geçti diye işaretlenmiş değildir. Saha testini yapan kişinin tarih/sürüm/log bilgileriyle doldurması gerekir.
