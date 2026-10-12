# V21 – Tek Ekran Ödev Takip + Öğrenci 360°

## Ne eklendi?

Ödev Takip Formu altındaki **🧭 Öğrenci 360°** düğmesiyle sağ tarafta açılıp kapanan, salt okunur bir çalışma bölmesi. Bölme mevcut ders/kitap/konu tabloları ve Verilen Ödevler listesinin yanında görünür.

Seçilen öğrencinin:

- Ana Ödev Kontrol kayıtlarından bitmiş/açık/belirsiz kayıt sayıları ve son 6 kontrol satırı,
- Son 30 güne ilişkin teslim dönemi özetleri ve gecikmiş açık ödevleri,
- Deneme sınavlarının karşılaştırılabilirlik uyarıları,
- Koçluk hedefleri, rutin profili ve Konu Haritası bilgileri,
- Kaynağa dayanan kısa ve ihtiyatlı öğretmen önerileri görüntülenir.

**✅ Kontrolü Aç**, eski Ödev Kontrol Formu'nun aynı düğmesini çağırır. Yeni ayrı bir tikleme/kayıt yolu yoktur. Konu Kanıtları kendi mevcut ekranına yönlendirir.

## Güncelleme

1. Çalışan uygulamanın kodunun, SQLite veritabanlarının ve plan profilinin ayrı yedeğini alın.
2. Çalışan **v3.5.17** ile bu paketin **v3.5.16 tabanlı V20.2** kaynak zinciri aynı değildir. Önce sürüm farklarını birleştirin.
3. Test kopyasında **V20.2** üzerinde yalnızca değişen dosyalar ZIP'ini proje köküne açın; klasör yapısını koruyun.
4. Mac/Windows üzerinde PyQt6 ile öğrenci seçimleri, Kaydet, Kontrol, geri alma, Konu Haritası, farklı öğrenci geçişi ve dar ekranı test edin.
5. Hata varsa yalnızca yeni V21 bağlantısını geri alın; gerçek veri dosyalarını hiçbir zaman eski ZIP ile değiştirmeyin.

## Güvenlik ve sınırlar

- Yeni V21 modülleri veritabanını `mode=ro` ve `PRAGMA query_only=ON` ile açar; hiçbir ödev, tik veya koçluk kaydı yazmaz.
- Bölme başlangıçta kapalıdır; öğretmen açtığında veri okur, seçim değiştiğinde eski öğrencinin içeriğini anında siler.
- Ödev Kontrol özetinde ana `odev` tablosu esas alınır; gölge `odev_satir` ikinci kez sayılmaz. Bu sayılar V14'ün tarihli ödev oranlarıyla aynı metrik değildir.
- Ödev bitmiş görünmesi, konunun öğrenildiği anlamına gelmez.
- Ayrıntılı Ödev Kontrol hâlâ eski diyalogla açılır; tek ekran üzerinden ikinci bir yazma arayüzü oluşturulmamıştır.
- Mevcut Öğrenci 360° okuyucusu V14 performans motorunu tekrar kullandığı için çok büyük veritabanlarında okuma süresi ayrıca ölçülmelidir.
- Bu kaynak paketinde canlı öğrenci verileri, profil JSON'ları ve özel lisans dosyaları bulunmaz.

## Dosyalar

- `services/student_workspace_v21.py`: veri modelleri, ana Kontrol durumu, son kontrol satırları ve ortak öğrenci okuması.
- `ui/student_workspace_panel_v21.py`: sağdaki salt okunur panel.
- `ui/homework_workspace_bridge_v21.py`: ana forma bağlantı ve var olan Kontrol düğmesine yönlendirme.
- `ui/homework_form.py`: yalnızca ilk öğrenci eşleştirmesi, programatik seçim bildirimi ve küçük bağlantı kodu.
- `tests/test_v21_student_workspace.py`: kimlik ayrımı, salt okunur DB ve uyumluluk testleri.
