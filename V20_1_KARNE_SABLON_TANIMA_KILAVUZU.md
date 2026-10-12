# V20.1 – Karne Şablonlarını Güvenli Tanıma

## Hedef
V20'nin okunabilir CSV/TSV/XLSX ve metin içeren PDF'lerinden soru-konu kanıtı hazırlama işlevini koruyup yaygın sütun başlığı çeşitlerini ve çok sayfalı Excel çalışma kitaplarını tanımak. Sadece mevcut V19 güvenli önizleme/onay/kayıt akışı kullanılır.

## Değişenler
- `services/question_evidence_v19/layout_detector_v201.py` (yeni): Birebir başlık eşleştirme ve görünür Excel sayfalarını sınırlı kaynak kullanımıyla salt okunur tarama. Formüller, gizli sayfalar ve aşırı büyük tablolar otomatik kanıt sayılmaz.
- `services/question_evidence_v19/karne_adapter_v20.py`: İlk Excel sayfasıyla sınırlı işlem yerine, ayrı ayrı doğrulanan çok sayfalı veriler. Eksik soru tablosu başlığı bulunan sayfalar sessizce atlanmaz.
- `ui/question_evidence_import_v19.py`: Önizlemede tanınan düzen ve incelenen sayfa sayısı gösterilir. Kaydetme onayı mevcut V19 katmanında kalır.
- `tests/test_v201_layout_detection.py` (yeni): Çok sayfalı dosya, karışmış öğrenci, yinelenen soru, formül, eksik başlık, gizli sayfa ve veri yetersizliği testleri.

## Kullanım
Deneme Sınavları > öğrenci ve deneme seç > Soru–Konu > Karne / Analiz Dosyası. CSV/TSV, XLSX veya aranabilir PDF seç. Tanınan tablo, öğrenci/deneme kimliği uyarıları ve satır bazında yeni/değişen/aynı/hata durumlarını incele. Belirsiz durum varsa kaydetme. Kaydetme için mevcut öğretmen onayı gerekir.

## Bilinçli sınırlar
- Fotoğraf/taranmış PDF **OCR ile okunmaz**; böyle bir işlem yapıldığı iddia edilmez.
- Her yayınevi şablonu tanınmış değildir. Sütunları açıkça etiketlenmemiş belgeler reddedilir veya uyarı verir.
- Ödev, koçluk, eski deneme puanları ve akademik yeterlilik otomatik değiştirilmez.
- Bu sürüm gerçek Mac/Windows arayüzünde ve farklı yayınevlerinin gerçek karneleriyle ayrıca doğrulanmalıdır.

## Kurulum
Mevcut V20 kaynak sürümünün yedeğinde yalnızca değişen dosyalar paketini uygulayın veya tam kaynağı yeni test klasörüne çıkarın. Canlı öğrenci veritabanına değil örnek veritabanına bağlanarak test edin. Mevcut uygulamanızın sürümü farklıysa önce dosya karşılaştırması yapın.
