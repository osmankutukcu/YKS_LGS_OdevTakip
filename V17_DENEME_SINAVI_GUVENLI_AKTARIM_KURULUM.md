# V17 – Deneme Sınavı Güvenli Kayıt ve CSV/Excel İçe Aktarma

**Temel sürüm:** V16 modüler Öğrenci 360° kaynak paketi (v3.5.16 zinciri).

## Öğretmen kullanım akışı

1. Deneme Sınavları sayfasını açın ve **ilgili denemeyi** seçin.
2. **CSV / Excel İçe Aktar** düğmesine tıklayın.
3. İsterseniz **Boş CSV Şablonu** ile başlıkları oluşturun.
4. CSV (UTF-8), TSV ya da `.xlsx` dosyasını seçin. Excel için **ilk sayfa** okunur.
5. **Yeni / Değişecek / Aynı / Hata** önizlemesini kontrol edin.
6. Hatalı satır varsa hiçbir satır kaydedilemez; hata mesajında gösterilen satırı düzeltin.
7. Öğretmen onayıyla kaydedin; deneme listesi ve sonuçlar yenilenir.

CSV sütunları: `ogrenci_id,ad_soyad,ders,dogru,yanlis,bos`. `ogrenci_id` veya `ad_soyad` alanlarından **biri** yeterlidir. Aynı isimli öğrenciler için sayısal ID gereklidir. `bos` isteğe bağlıdır; boş bırakılırsa eski sonuçtaki boş değeri korunur. Sayısal doğru ve yanlış birlikte girilmelidir. Ders adı seçili denemenin derslerinden biri olmalıdır.

## Ne korunur?

- Kaynakta bulunan `deneme_sonuclari` satırları topluca silinmez.
- Ekranda bulunmayan/pasif öğrencilerin **önceden kaydedilmiş** sonuçları korunur.
- Öğrenci ID ve ad uyuşmazlığı, tekrar eden öğrenci/ders, muğlak ad ve mevcut veritabanında mükerrer kayıt kaydetmeyi engeller.
- Aynı sonuç bir daha içe aktarılırsa değişiklik yapılmaz.
- Önizlemeden sonra veritabanındaki sonuç değişirse işlem geri alınır ve yenileme istenir.
- Hatalı/eksik satır içeren dosyalar **kısmen kaydedilmez**.
- Mevcut `Kaydet` düğmesi de aynı güvenli veri yazma servisine bağlanmıştır.

## Sınırlar ve bilinen durumlar

- `.xlsx` dosyasında ilk çalışma sayfasının hücre **değerleri** okunur; formüller, makrolar ve harici bağlantılar yürütülmez. Formül hücresi varsa dosya reddedilir. `.xls` desteklenmez; CSV'ye dışa aktarın.
- Dosya sınırı 8 MB, en fazla 5000 veri satırı. Önizleme ilk 400 geçerli, ilk 50 hatalı satırı gösterir; hata sayısı toplu olarak belirtilir.
- Eski sonuçları temizlemek amacıyla hücrelerin silinmesi **otomatik kayıt silmez**. Bunun için ayrı ve denetlenebilir silme akışı gerekir.
- Mevcut tablo yapısında kesin sınav soru sayıları saklanmadığından doğru+yanlış+boş için evrensel 200 üst sınırı kullanılır; tam ders bazlı soru sayısı doğrulaması daha sonraki bir veri modeli geliştirmesidir.
- Net hesabı var olan uygulamadaki davranışla uyumlu olarak `max(0, doğru − yanlış/4)`; bu katsayı her sınav türü için ayrı doğrulanmış değildir. Yeni bir sınav kural motoru eklenmemiştir.
- Güncelleme **kaynak kod seviyesinde** hazırlanmıştır. PyQt6 ve gerçek Mac/Windows kullanıcı arayüzü burada doğrulanmadı.
- Kullanıcıların çalışan v3.5.17 sürümü bu V16 tabanlı kaynakla aynı olmayabilir. Canlıya uygulamadan önce dosya farkı ve GUI testi zorunludur.

## Güncellenen dosyalar

- `services/trial_exam_import_v17.py` – veri okuma, doğrulama, atomik kaydetme.
- `ui/trial_exam_import_v17.py` – dosya seçimi, önizleme, onay, CSV şablonu.
- `ui/trial_exam_manager.py` – import düğmesi ve güvenli elle kaydetme bağlantısı.
- `tests/test_v17_exam_import.py` – 21 bağımsız servise yönelik test.

## Test akışı

Önce **gerçek öğrenci verilerini içermeyen DB kopyasında** şu senaryoları uygulayın: farklı öğrenciler; aynı isimli öğrenciler; pasif öğrencinin mevcut kaydı; eski sınav sonuçları; Excel/CSV içe aktarma; tekrar import; aynı sınavı manuel düzenleme; ekranda bulunmayan öğrencilerin korunması; PDF/Excel raporlarının açılması; uygulamanın kapanıp açılması.

Her dağıtım öncesinde SQLite güvenli yedeği alın. Kaynak ZIP'lerini gerçek kullanıcı profilleri/veritabanlarıyla birleştirirken orijinal dosyaları üzerine yazmayın.
