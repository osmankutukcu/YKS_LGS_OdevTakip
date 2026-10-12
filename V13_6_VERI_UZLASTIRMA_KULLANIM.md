# V13.6 – Güvenli ödev bağlantısı uzlaştırma

## Kapsam ve korunacak veriler

Bu sürüm, V13.5'in salt okunur **🔎 Denetim** ekranını ve ana ödev formunu değiştirmez. Yeni araç yalnızca `odev_satir.odev_id` dolu olup `odev.id` karşılığı olmayan bağlantılar içindir. Diğer tutarsızlık türlerini otomatik onarmaz. Öğrenci profilleri, tikler, ödev durumları ve normal kayıt yollarına dokunmaz.

**Her zaman önce uygulamayı kapatın ve bağımsız, güvenilir bir tam yedek alın.** İnceleme işlemi salt okunurdur. Açık onayla yapılan işlem bile **yalnızca yeni bir SQLite kopyasına** uygulanır; canlı kaynak dosya korunur. Kullanıcıya dönük otomatik onarım düğmesi yoktur.

## 1. Salt okunur inceleme dosyası oluşturma

Kaynak kod kökünde:

```bash
python tools/reconcile_homework_v136.py review --db "/path/to/source.db" --manifest "/secure/review.json"
```

`review.json` her vaka için satır kimliği, öğrenci ve küme kimlikleri, eski ödev bağlantısı, mevcut satır özetinin SHA-256 değeri ve **yalnızca incelenmeye aday** ödev kimlikleri içerir. Ad/telefon bilgisi taşımaz; yine de iç kayıt kimlikleri bulunduğundan güvenli tutulmalıdır. `islem: "review"` varsayılandır ve **değişiklik anlamına gelmez**.

## 2. Manuel kontrol ve gerekçeli karar

Yetkili kişi kaynak yedekleri, ilgili ödev geçmişi ve öğretmen kayıtlarını incelemelidir. Güvenilir belge yoksa `islem: "review"` olarak bırakın. Kanıtlanmış durumlarda iki seçenek vardır:

- `"islem": "relink"` ve `"yeni_odev_id": 123`: yalnızca mevcut, aynı öğrenci ve aynı kümedeki, ders–kitap–konusu birebir örtüşen ve başka ödev satırına bağlı olmayan açık hedefe bağlama.
- `"islem": "unlink"` ve `"yeni_odev_id": null`: yetkili, eski bağlantının geçersiz olduğunu **kanıtlayarak** sadece bağlantı alanını boşaltmayı seçer. Satırın kendisi, ödev bilgisi, öğrenci, küme, durum ve diğer alanlar silinmez. Bununla birlikte tarihsel bağlantı kanıtı değiştiği için gerekçesiz kullanılmamalıdır.

Her onaylı vakaya en az 15 karakterlik `gerekce` yazın. Bu kararları sistem kendisi vermez. **V13.6, yönetici kimliğini doğrulayan oturum açma ekranı sunmaz:** CLI'da verilen isim ve onay beyanı işletimsel denetimdir, kriptografik kimlik doğrulama değildir. Kurum yöneticisi dosya erişimlerini ayrıca kontrol etmelidir.

## 3. Yalnızca ayrı bir kopyada uygulama

```bash
python tools/reconcile_homework_v136.py apply \
  --db "/path/to/source.db" \
  --manifest "/secure/approved-review.json" \
  --output "/secure/validated-copy.db" \
  --approver "Yetkili Yönetici" \
  --confirm ONAYLI_KOPYA_OLUSTUR
```

**Çıktı dosyası mevcut olmamalıdır.** Kaynak dosyaya çıktı olarak aynı yol verilemez. Yazma aracı SQLite'ın yedekleme API'siyle tutarlı yeni kopya oluşturur, manifestonun güncel satırlarla birebir eşleştiğini doğrular, değişiklikleri işlem bütünlüğü içinde uygular, sonra SQLite ve bağlantı denetimini çalıştırır. Çıktıyla birlikte `validated-copy.db.uzlastirma.json` işlem günlüğü oluşur.

Kullanıcı kaynak veritabanını yeniden adlandırıp uygulamaya takmayı **otomatik yapan hiçbir işlem yoktur**. Böyle bir canlı geçiş ayrıca veritabanı+profil yedeği, dosya kilidi kontrolleri, kurulum denemesi ve yetkili onayı gerektirir. Eski sürüme dönüş gerektiğinde orijinal veritabanına geri dönmek mümkündür; arada yeni kayıt yapıldıysa doğrudan dosya değiştirmeyin.

## Gerçek v3.5.16 geliştirici yedeği hakkında

Üç kopuk bağlantı tespit edildi; aynı öğrenci, aynı küme ve birebir ders–kitap–konu ile güvenilir başka `odev` adayı çıkmadı. Bu nedenle **üçü de `review` olarak kalmalı**; yalnızca kaynak yedekleri ve öğretmen kanıtlarıyla desteklenen ayrı bir yönetici kararı sonrasında uzlaştırılabilir. Gerçek öğrenci verileri paketlere dahil edilmemiştir.

## Test kapsamı ve sınırlar

- V13.6'ya özel 22 sentetik test başarılı (onay, yanlış öğrenci, yanlış kitap/konu, çift hedef, eskimiş manifest, orijinalin korunması, kopya bütünlüğü, günlük kaydı ve CLI dahil).
- Geniş test kümesinde PyQt6 bağımlı testleri ayırınca 460 test ve 44 alt test başarılı; 3 ek GUI testi hariç bırakıldı, 3 PyQt6 bağımlı test modülü ve `utils/test_motive_settings.py` ortam nedeniyle yüklenemedi.
- Mac/Windows masaüstü gerçek tikleme, kurulum ve geri yükleme testleri yapılmadı.
