# V20 — Analizli Karne Önizleme ve Güvenli Soru–Konu Aktarımı

## Neler eklendi?
- **Deneme Sınavları → öğrenci seç → Soru–Konu → Karne / Analiz Dosyası** ile yeni içe aktarma seçeneği.
- CSV / TSV / XLSX dosyalarında farklı sütun başlıklarının kontrollü eşleştirilmesi.
- **Aranabilir (metin içerikli) PDF** içinde açık soru tablosunun kontrollü okunması: ders, soru numarası, doğru/yanlış/boş, konu, isteğe bağlı kazanım kodu.
- Dosyada öğrenci/deneme kimliği varsa seçili kayıtla eşleşmesi zorunlu. Kimlik yoksa seçili öğrenci ve deneme önizleme bağlamına eklenir ve **açık doğrulama uyarısı** gösterilir.
- Yalnızca ders netlerinden soru/konu üretme yoktur. Emin olunmayan satırlarda güvenli hata.
- Tüm yazma işlemleri V19'un **öğretmen onaylı, çift kayıt denetimli ve atomik** servisinden geçer. Ana ödev, deneme neti ve koçluk tablosu değiştirilmez.

## Desteklenen belgeler
- **CSV, TSV, XLSX**: açık `Ders`, `Soru No`, `Sonuç`, `Konu` sütunları bulunmalı. `Öğrenci ID`, `Deneme ID` ve `Kazanım Kodu` isteğe bağlı; ilk ikisi yoksa öğretmen doğrulaması gerekir.
- **PDF**: en çok 20 sayfa, 8 MB, aranabilir metin içeren, satırlarında `|`, `;`, TAB veya ayrık çoklu boşlukla başlıkları açık şekilde ayıran tablo. Alternatif olarak `Ders: Fizik` satırından sonra `Soru No | Sonuç | Konu` tablosu.
- **Desteklenmeyen**: fotoğraflar, taranmış/görüntü PDF, yalnızca net/puan özetli karne, etiketleri belirlenemeyen yayınevi tasarımları. V20 OCR veya geniş çaplı yayınevi şablonu tanıma iddiasında bulunmaz.

## Hızlı kullanım
1. Önce **Deneme Sınavları** ekranına öğrenciye ait ders bazlı sonuçları kaydedin.
2. İlgili öğrenciyi ve denemeyi açıp **Soru–Konu** bağlantısını seçin.
3. **Karne / Analiz Dosyası** ile belgeyi yükleyin; yeni/değişecek/aynı durumlarını ve kimlik uyarılarını inceleyin.
4. Dosyadaki öğrenci ve sınav, tüm soru numaraları, sonuçlar ve konu adlarını doğrulayın.
5. Onay kutusunu işaretleyip kaydedin. Veritabanı işleminden önce sonuçlar tekrar doğrulanır; değişiklik algılanırsa işlem iptal edilir.

## Veri güvenliği
- Dosya içeriği **yerel olarak** işlenir; internete gönderilmez.
- PDF metin çıkarımı OCR değildir; belge içeriğini doğrulanmış kabul etmez.
- Resmî MEB/ÖSYM kazanım eşleştirmesi yapmaz. Kazanım sütunu öğretmen beyanı olarak kalır.
- Tek belge en fazla 5000 veri satırı; 8 MB; PDF en çok 20 sayfa.
- Görsel PDF işleme bu sürümde engellenir: yanlış öğrenciye konu atanmasını önlemek için.
- Veritabanına yazılanlar sadece V19'un `soru_konu_kanit_v19` ve denetim günlüğü kayıtlarıdır.

## Windows / Mac kabul kontrolleri
- Farklı öğrenci ve deneme kimliğine ait dosya içe aktarımı engellensin.
- Aranabilir PDF tablosu ve CSV/Excel birkaç örnekle denensin.
- Yalnızca ders netleri veya fotoğraf içeren PDF açıkça reddedilsin.
- Eşleşmeyen konu, görünür uyarı oluştursun; öğretmen onayı olmadan kaydetme yapılamasın.
- Aynı dosyanın ikinci kez yüklenmesi çoğaltma oluşturmasın.
- Mevcut ödev tikleri, Deneme netleri, Koçluk Planı ve Konu Haritası kayıtları değişmesin.
- Gerçek v3.5.17 ile birleştirme öncesi dosya diff ve GUI testleri yapılsın.
