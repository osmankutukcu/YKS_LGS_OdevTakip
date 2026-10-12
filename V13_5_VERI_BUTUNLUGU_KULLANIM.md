# V13.5 – Salt okunur veri bütünlüğü denetimi

## Öğretmen için kullanım

1. Öğrenciyi seçip **Bilgileri Getir** ile ders/kitap/konu matrisini yükleyin.
2. Ana Ödev Takip Formu alt barındaki **🔎 Denetim** düğmesini açın.
3. İki ayrı sonuç görünür: **veritabanı bağlantıları** (genel) ve **seçili öğrencinin kaydedilmemiş taslağı**.
4. `Kritik / Yüksek / Orta` bulguları inceleyin. Raporu kopyalayabilirsiniz; hiçbir kayıt düzeltilmez veya silinmez.

## Neler kontrol ediliyor?

- Kayıp öğrenci veya ödev kümesi bağlantıları.
- Ödev, ödev satırı ve ödev kümesi arasında farklı öğrenciye işaret eden bağlantılar.
- `odev_satir.odev_id` verilmiş olduğu halde `odev` içinde bulunmayan kayıtlar.
- Seçilen öğrenci kimliğiyle yüklenmiş ders matrisi uyuşması.
- Kaydedilmemiş düzenlenebilir tik / geçici sağ ödev listesi tutarsızlıkları.
- Yinelenen sağ taslak satırları ve belirsiz (aynı isimli) matris hücreleri.

**Önemli kapsam sınırı:** `odev` ve `odev_satir` iki farklı tarihsel kayıt türüdür. Sayılarının farklı olması bozuk veri anlamına gelmez. `odev_id IS NULL` yasal eski kayıt olabilir. Tamamlanmış/kilitli ödevler taslak eşleşme analizine dahil edilmez. `odev_id` bulunmayan üç eski kayıt otomatik değiştirilmez.

## Teknik ekip için bağımsız kullanım

Kaynak dizininde:

```bash
python tools/audit_homework_v135.py --db "/path/to/your/database.db"
python tools/audit_homework_v135.py --db "/path/to/your/database.db" --json
```

Araç veritabanını `mode=ro` ve `PRAGMA query_only=ON` ile açar. Otomatik onarım yapmaz. Veritabanı yolu açıkça verilmelidir; çalışma bilgisayarında dosya aramaz. Denetim raporlarında örnek kayıt ID'leri bulunabilir; üçüncü taraflarla paylaşmadan önce gözden geçirin.

## Kurulum

- V13.4 kurulu **kaynak test kopyanız** varsa yalnızca V13.5 yamasındaki dosyaları aynı yollarına alın.
- Önceki güncellemeler yoksa veri içermeyen V13.5 kümülatif kaynak paketini ayrı bir dizinde açın.
- Gerçek öğrenci veritabanı ve profil JSON dosyalarını kaynak dosyalarla birlikte değiştirmeyin.
- Çalışan Windows/Mac uygulamasına yama yapmadan önce yedek ve GUI kabul testi gerekir.

## Test sınırları

V13.5'e özel 31 otomatik test ve Qt bağımlı üç test modülü dışındaki toplam 405 test başarılıdır. PyQt6 kurulu gerçek Windows/macOS ortamında tıklama testleri henüz yapılmamıştır. Denetim veriyi düzeltmez; uzlaştırmayı öğretmen/yönetici onayından sonra ayrı araçla tasarlamak gerekir.
