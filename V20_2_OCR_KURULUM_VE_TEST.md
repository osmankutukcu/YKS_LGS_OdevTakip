# V20.2 – Sınırlı yerel OCR ve güvenli önizleme

## Kullanım

Deneme Sınavları → Soru–Konu → **Karne / Fotoğraf (OCR)** → JPG, PNG, CSV, XLSX veya PDF seçin. Görseller ve **tamamen görüntü tabanlı PDF** OCR ile okunur. Yazı içeren PDF'ler önce V20'nin metin tablosu okuma yolundan geçer. OCR yavaş olabileceğinden arka planda çalışır; işlem sürerken kayıt düğmesi açılmaz. Belge ile karşılaştırıp onaylayın; V19 servisi soruları ve öğrenci/deneme sonuçlarını yeniden kontrol eder.

## İsteğe bağlı kurulum

- `python -m pip install -r requirements_ocr_optional.txt`
- Tesseract OCR motorunu ayrı kurun; **`eng`** dil verisini yükleyin ve komutun PATH üzerinde çalıştığını doğrulayın: `tesseract --version`.
- Windows: Tesseract'ın kurulumu/PATH ayarı ayrıca gerekir; Mac: `brew install tesseract` kullanılabilir. Türkçe harfler ve farklı basım düzenlerinin OCR kalitesi değişir.
- PyQt6, önceki uygulamanın masaüstü gereksinimidir; yalnızca OCR servisinin testleri Qt gerektirmez.

## Güvenlik ve sınırlar

- OCR **tamamen cihazda çalışır**, çevrim içi servis, otomatik ödev veya veritabanına doğrudan yazma yoktur.
- JPG/PNG ve **en fazla 6 sayfalık** görüntü tabanlı PDF; dosya en fazla 8 MB. Sayfa çözünürlüğü sınırlıdır; OCR motorunun sayfa başına 20 saniyelik zaman aşımı vardır.
- Kötü okuma, eksik soru başlığı veya yalnızca ders neti tablosu otomatik eşleştirilmez. Resmî kazanım doğrulaması yapılmaz. Ortalama OCR güveni %65 altındaysa reddedilir; %65 üstü **doğruluk garantisi değildir**.
- İlk aşama yalnızca açık **ders–soru numarası–sonuç–konu** sütunlarını destekler. Serbest form ve karmaşık grafik karneler, çok sütunlu taramalar otomatik doğrulanmış sayılmaz. Öğretmen her satırı kontrol eder.
- Öğrencinin kimliği belge OCR sonucuna göre otomatik seçilmez. Seçili öğrenci/deneme başka bilgiyle karışırsa işlem reddedilir.
- PDF içinde yazı olduğu halde soru tablosu bulunamazsa güvenlik gereği belgenin tamamı OCR'a körlemesine gönderilmez.

## Test ve yayın

`python -m pytest -q tests/test_v202_scanned_reports.py tests/test_v201_layout_detection.py tests/test_v20_karne_adapter.py`

Gerçek yayınevi, tarama ve telefon fotoğrafı çeşitliliğiyle bağımsız saha doğrulaması ve gerçek Mac/Windows Qt testi **henüz yapılmadı**. OCR altyapısı ve mevcut UI için bu doğrulamalar tamamlanmadan otomatik yüksek hacimli yayına alınmamalıdır.
