# KoçPilot 360 V3.5.86 – Toplu PDF ve Gerçek Sayfa Önizlemesi

## Bu yama ne ekler?

- **Detaylı Raporlar → Rapor Merkezi → Toplu PDF + Önizleme (Pilot)** düğmesiyle ayrı bir diyalog.
- Aktif öğrencileri **sayısal öğrenci ID'si** üzerinden listeler. Ana grup/alt grup filtresi, öğrenci arama, tek/çoklu öğrenci seçimi, görünürleri seç ve temizle.
- Kullanıcı **7, 30 veya 90 gün** ile mevcut **Veli / Öğretmen / Bütünleşik Öğrenci 360** şablonlarından birini seçer.
- *Tek bir birleşik PDF* hazırlanır: içindekiler/seçili öğrenci listesi + her öğrenci için önceki sürümlerin **aynı rapor oluşturma motorları** üzerinden ayrı sayfalar.
- Oluşturmadan önce seçilen öğrenci isimleri ve rapor kapsamı doğrulanır; filtre değişince gizli işaretlemeler temizlenir. En fazla **60 öğrenci/çıktı** (pilotta UI gecikmesini sınırlama).
- Gerçek PDF sayfa önizlemesi: sayfa ilerletme ve yakınlaştırma. Hem yeni toplu PDF hem de tekli Profesyonel PDF Atölyesi için kullanılabilir.
- Dönem, öğrenci veya rapor tipi değişince önceden oluşturulan **son PDF'yi aç** kısayolu geçersizleşir.

## Kanıt, gizlilik, bütünlük

1. Öğrenciler **tam ID eşleşmesi** ve `aktif=1` ile doğrulanır. Her raporun dönen `student_id` kimliği tekrar sınanır. Pasif/silinmiş kayıt içeren seçimin tamamı reddedilir; kullanıcı ad benzerliğine göre eşleştirme yapılmaz.
2. Bir grupta hem `odev` hem `odev_satir` satırları olması halinde **önceki V3.5.83 tekil kayıt seçimi** korunur. Yeniden toplam ya da yazma yapılmaz.
3. PDF içindekilerindeki ödev yüzdeleri yalnızca mevcut durumdaki **teslim tarihi gelmiş ödevlerdir**. Hiç kanıt yoksa `%0` değil **Veri yok** yazılır. Bunlar sınav başarısı değildir.
4. `PyMuPDF` yalnızca PDF birleştirme/önizleme amacıyla kullanılır; mevcut öğrenci/veritabanı kayıtlarına dokunmaz. Birleştirme ve görsel önizleme için bu **isteğe bağlı bağımlılık kurulmalıdır** (`requirements_v3586_preview_optional.txt`). Windows bağımlılık listesinde zaten `pymupdf>=1.24.0` yer alıyor; kurulum ortamında doğrulayın.
5. PDF üretimi özel geçici klasörde yapılır. İptal/hata sonrasında henüz kaydedilmemiş öğrenci PDF parçaları silinir. Hedef `.pdf` dosyası sadece münhasır yeni dosya açma moduyla (`xb`) oluşturulur; mevcut dosyaların üstüne yazılmaz.
6. Bu yama **otomatik WhatsApp/e-posta/portal paylaşımı yapmaz**. PDF kişisel öğrenci verisidir: öğretmen alıcı yetkisini kendisi kontrol eder. Farklı kullanıcı/kurumlar arası sunucu tarafı rol yetkisi bu kaynak yamasıyla oluşturulmaz.
7. İşlem uzun sürerse ilerleme ve iptal sunulur; 60 öğrenci/çıktı sınırı büyük kurumlar için **ilk pilot performans sınırıdır**, nihai kurumsal ölçeklendirme değildir.

## Kurulum – önce test kopyası

1. Güncel ve çalışır **V3.5.80 tam kaynak** klasörü ile öğrencilerin/veritabanının yedeğini alın.
2. Orijinal tam kaynak kodunu **AYRI TEST** klasörüne açın. Bu ZIP'in tüm dosyalarını mevcut dizin yapısını koruyarak üzerine kopyalayın. **V3.5.81–85 yamaları ayrı gerekmez**; hepsi bu ZIP'in içindedir.
3. Python ortamında `pip install -r requirements_v3586_preview_optional.txt` komutuyla isteğe bağlı gerçek sayfa görüntüleyicisini kurun (veya gereksinimin kurulu olduğunu kontrol edin).
4. Kaynak testlerini çalıştırın: `python -m unittest tests.test_bulk_report_v3586 tests.test_report_planner_bridge_v3585 tests.test_integrated_report_v3584 tests.test_professional_pdf_v3583 tests.test_report_center_v3581 tests.test_report_evidence_v3582 tests.test_v14_performance_evidence tests.test_v15_performance_coaching tests.test_v35_release_gate -q`.
5. **Gerçek Windows/macOS PyQt6 GUI** üzerinde grup filtresi, ad arama, çoklu seçim, önizleme, ESC/iptal, geçmiş PDF korunması ve PDF/çıktı yolu test edilmeli. EXE'ye `fitz`/PyMuPDF modülünün dahil olduğu PyInstaller ile doğrulanmalı.

## Gerçekleştirilen kaynak testleri

- **100 ilgili otomatik test başarılı**, canlı öğrenci verisi kullanılmadı.
- Sentetik iki öğrenciyle **3 sayfalık** (bir sayfa içindekiler + iki veli raporu) gerçek PDF üretildi ve sayfalar görsel kontrol edildi.
- Sentetik 60 öğrenciyle **63 sayfalık** yoğunluk testi (3 sayfalık içindekiler + 60 bireysel PDF) gerçekleştirildi.
- 10 korumalı dosyanın kaynak özetleri orijinal V3.5.80 ile karşılaştırıldı. Ana pencere, Ödev Takip, Ödev Kontrol ve Haftalık Planlayıcı kaynakları değiştirilmedi.
- **Sınır**: Gerçek Windows/macOS PyQt6 arayüzü, gerçek okul verisi, paylaşımlı ağ, farklı kullanıcı rolleri, yazıcı ve üretim EXE **henüz test edilmedi**. Pilot kodu, kullanıcı kabul testinden önce canlı müşterilere gönderilmemeli.

## Kalan tek planlı ana aşama

**V3.5.87 stabilizasyon:** GUI/EXE/paketleme doğrulaması, kaynaklar arası tutarlılık, erişim yetkisi ve performans kabul testi. Testlerde ek sorun çıkarsa ayrıca hata düzeltme gerekebilir.
