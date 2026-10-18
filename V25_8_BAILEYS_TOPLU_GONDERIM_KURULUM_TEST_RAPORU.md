# V25.8 – Baileys Windows Toplu Gönderim (İzinli Pilot)

## Kısa özet

**V25.7 tek alıcı testine ek olarak**, mevcut **Mail Gönder → WhatsApp** ekranında yeni bir gönderim yöntemi eklenmiştir: **Baileys – izinli toplu gönderim (Windows / pilot)**. Bu seçimi yaptıktan sonra öğrencileri, öğrenci/veli telefon sütunlarını, şablonu ve kişiselleştirme seçeneklerini *eski yöntemlerdeki gibi* belirleyin; **Gönder (WhatsApp)** düğmesi yeni ayrı kontrol penceresini açar. Tek onaydan sonra Baileys seçilen **1–150 farklı izinli numarayı** aynı bağlantıda sırayla işleyebilir. 100–150 alıcı ayrı ayrı tıklanmaz; her birine 20 saniye aralıkla tek deneme yapılır.

**Önemli:** Bu ZIP Baileys kaynak motorunu içerir, **Node bağımlılıkları yüklenmiş şekilde değildir**. Windows ve gerçek WhatsApp uçtan uca gönderim testleri henüz yapılmadı. Bu paket **Windows gerçek kullanıcı pilotudur; üretim sertifikası değildir**.

## Windows kurulum – uygulamanın içinden

1. Windows 10/11 üzerine resmî kaynaktan **Node.js 20 veya daha yeni** kurun; gerekirse uygulamayı yeniden açın. Node.js, npm ve internet erişimi gereklidir.
2. ZIP içindeki proje kaynak kodunu kurun veya aynı kaynaklardan PyInstaller ile Windows uygulamasını derleyin. Ana program: **Mail Gönder → WhatsApp**.
3. **Gönderim yöntemi → Baileys – izinli toplu gönderim** seçin. Seçili öğrenciler ve mesajla **Gönder** deyin.
4. Açılan pencerede **Baileys Windows Motorunu Kur / Güncelle** düğmesine basın. Onay sonrası yalnızca bu Windows kullanıcısının `%LOCALAPPDATA%\YKS_LGS_HomeworkManager\BaileysNodeV258` klasörüne doğrulanabilir uygulama dosyaları kopyalanır. Açılan komut penceresi `npm install --package-lock-only` ve `npm ci --ignore-scripts` çalıştırır. Ekrandaki npm onayını verin; Node testlerinin başarılı olduğuna bakın. Bu bir **tek seferlik kullanıcı başlatmalı kurulumdur**.
5. Önce **kendi test telefonunuzla** ayrı V25.7 tekli Baileys denemesini yapın (mevcut tekli pilot bundan bağımsızdır); ardından V25.8 için 1–2 izinli numarayla deneyin.
6. Toplu pencerede seçim özeti, atlanan numaralar ve **ilk mesaj örneğini** inceleyin. Mesaj istemeyen numarayı **Ret listesine ekle** ile kalıcı olarak dışlayın.
7. Seçilen **her alıcının WhatsApp bildirimleri için önceden izin verdiğini** kurum kayıtlarınızdan teyit edip onay kutusunu işaretleyin. **Başlat / QR** ve son onaydan sonra QR kodunu telefonda WhatsApp → Bağlı Cihazlar bölümünden okutun.
8. Pencereyi açık bırakın. İlerleme/sonuçlar `İstemci kabulü (teslim belirsiz)`, `Sonuç belirsiz`, `Bekleyen`, `Gönderilmedi` şeklindedir. **İstemci kabulü teslimat değildir.**
9. Bağlantı koparsa **Durdur**; kalan işler şifreli kuyrukta kalır. **Baileys yöntemini seçip Kuyruğu Gör / Sürdür** ile aynı partinin yalnızca *henüz denenmemiş* mesajlarını **yeniden açık izin onayı ve QR ile** sürdürebilirsiniz. Sonucu belirsiz iş asla otomatik tekrarlanmaz.

## Güvenlik ve sorumluluk

- Baileys **WhatsApp'ın resmî API'si değildir**. Hesap sınırlaması, bağlantı kopması, hizmet koşulu ve uyumluluk riski kalır. **20 saniyelik aralık bir güvenlik garantisi değildir**; korumaları atlatmak veya yüksek hacimli spam üretmek için kullanılmamalıdır.
- Alıcının numarasına sahip olmak **WhatsApp izni olduğu anlamına gelmez**. İzin kayıtları uygulamada otomatik mevcut sayılmaz: kullanıcı her alıcı için kurumsal rızayı doğrular. Ret taleplerini kaydedin, yanlış/çakışan telefonları düzeltin.
- Baileys yeni kuyruk verilerini **Windows kullanıcı DPAPI'si ile** şifreler; eski WhatsApp/Selenium kuyruğunu veya kayıt kodlarını dönüştürmez. Farklı kullanıcı hesabında veya bilgisayarda aynı şifreli kuyruk açılamayabilir. Eski düz metin kuyruk olduğu gibi kalır; bu sürüm onu otomatik taşımıyor.
- Tek parti en fazla **150 farklı telefon**; her mesaj 3000 karakterle sınırlı. Paylaşılan numaraya bağlı farklı öğrenci kayıtları otomatik **atlanır**. Şüpheli/boş telefonlar ve ret listesi dışlanır.
- **Her parti için yeni QR eşleştirmesi gerekebilir**; kimlik doğrulama anahtarları Node tarafında yalnızca işlem belleğinde tutulur ve diskte saklanmaz. Bu nedenle WhatsApp bağlı cihaz yönetimini kullanıcı takip etmelidir.
- Erişilemeyen/çöken node modülü, kapanan pencere, işlem süresi aşımı veya belirsiz sonuçta program **asla aynı numarayı kendi kendine yeniden denemez**.
- Üretimde uzun dönem kullanım ve daha yüksek ölçek için **resmî WhatsApp Business Platform** ve kurallara uygun izin/şablon yönetimi ayrıca değerlendirilmelidir.

## Kod değişiklikleri

- **Yeni:** `services/whatsapp_queue/baileys_bulk_v258.py`: seçili alıcıların tekilleştirilmesi, ret listesi, şifreli Baileys kuyruğu, Windows hazırlık adımları.
- **Yeni:** `services/whatsapp_queue/baileys_node_v257/bulk_bridge_v258.mjs`, `bulk_rules_v258.mjs`, yeni Node test dosyası ve `Windows_Hazirla_V258.cmd`.
- **Yeni:** `ui/baileys_bulk_v258.py`: kontrollü mesaj önizleme, bağlantı QR'ı, durdur/sürdür ve ilerleme ekranı.
- **Sınırlı ekleme:** `ui/mail_send_whatsapp.py` (yöntem seçimi, yeni sihirbaza yönlendirme ve Baileys kuyruğunu seçme), `services/whatsapp_queue/transport_v249.py` (yeni izinli yöntem).
- **Değişmedi:** `ui/homework_form.py`, `ui/odev_kontrol*.py`, öğrenci/ödev ana DB yazım işlemleri, mevcut Selenium/Masaüstü/Web yöntemlerinin aktarım motorları ve V25.7 tekli test motoru.
- **Değişmedi:** `version.py` ve GitHub release versiyonu. Bu özellik V25.8 pilot katmanıdır; Windows kullanıcı kabulü sonrası genel sürüm etiketi ayrıca belirlenmelidir.

## Bu ortamda çalıştırılan otomatik testler

- 87 adet seçili Python testi geçti, Windows'a özgü 1 gerçek DPAPI testi bu Linux ortamında atlandı.
- 6 adet Node protokol testi geçti (Node 22.16.0): komut onayı, 150 sınırı, 15 saniyelik alt sınır, benzersiz numara ve tekli V25.7 koruması.
- Python dosyalarında sözdizimi derlemesi yapıldı.
- **Gerçek Windows/WhatsApp testi yapılmadı.** Ortamda PyQt6 ve npm kayıt sunucusuna ağ erişimi yok. `npm install` kayıt sunucusuna erişemediği için `package-lock.json` ve `node_modules` bu ZIP'e konmadı. Windows'ta yukarıdaki kurulum bunları oluşturacak.

## Gerçek Windows kabul kontrol listesi

- [ ] Kurulum komut penceresi sorunsuz tamamlandı ve Node testleri geçti.
- [ ] 1–2 izinli kendi test numarasına gerçek QR ve kontrollü gönderim doğrulandı.
- [ ] 5 izinli numarada kişiselleştirilmiş mesaj ve doğru alıcı doğrulandı.
- [ ] 100–150 alıcı denemesi ancak kurum izin kayıtları doğrulanıp ön testler başarıyla tamamlandıktan sonra yapıldı.
- [ ] 5. mesajda ağ kesilmesi ve durdurma sonrası belirsiz işler **yeniden gitmedi**; kalanlar sürdürüldü.
- [ ] Paylaşılan veli telefonu, yanlış numara ve ret listesindeki numara atlandı.
- [ ] Selenium, Web, Masaüstü, Ödev Takip ve Ödev Kontrol eski akışları ayrıca kontrol edildi.

> **Not:** V25.8 motorunun otomatik 100–150 alıcı işleme kodu eklenmiştir. Gerçek başarı/teslim oranı Windows pilot sonuçları olmadan iddia edilmez.
