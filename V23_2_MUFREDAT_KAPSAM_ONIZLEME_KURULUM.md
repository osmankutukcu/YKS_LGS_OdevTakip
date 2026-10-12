# V23.2 – Ödev Takip Formunda Müfredat Kapsamı (Güvenli Önizleme)

## Kısa açıklama

V23.1'den gelen müfredat referansları, Ödev Takip Formu'nun mevcut tikleme/kaydetme mantığına müdahale edilmeden öğretmenin görebileceği **salt okunur** bir konu kapsamı önizlemesine bağlandı.

**ÖNEMLİ:** Bu sürümde grup veya öğrenciye özel konu satırları ana matrisin tiklenebilir alanına EKLENMEZ. Eski sistem `odev.konu_id` için genel ders tablosundaki tamsayıları kullanıyor; özel konu tablolarındaki aynı sayısal ID'yi doğrudan buraya yazmak yanlış ödev oluşturabilir. Bu nedenle görünürlük bağlantısı kurulmuştur, yazma bağlantısı henüz açılmamıştır.

## Kullanım (Windows)

1. Uygulamayı mevcut verilerle açın, bir öğrenci seçip **Getir** ile ödev matrisini yükleyin.
2. Ders sekmesine geçin.
3. Ders çubuğundaki **📚 Konu Kapsamı** düğmesini açın (dar ekranda çubuk yatay kaydırılabilir).
4. Genel, grup ve öğrenciye ait etkin konu listesini, özgün kapsamı ve hangi konuların ana matrise tıkla–kaydet yapısı olmadan sadece bilgi amaçlı gösterildiğini inceleyin.
5. Çakışma uyarıları varsa kayıt ID'lerini kontrol edin. **Kapat** ile eski Ödev Takip Formu'na dönün.

Önizleme öğrencinin eski kaydedilmiş tiklerini, ödevlerini, koçluk hedeflerini veya öğrenci/kapsam tanımlarını değiştirmez. Yeni müfredat tanımlamaları Ders/Konu Düzenle ekranından yapılmaya devam eder.

## Kurulum

- Çalışan sürüm v3.5.17 farklı kod içerebilir: önce V23.1 tabanıyla dosya farkını inceleyin.
- Windows'ta öğrenci veritabanı, `plan_profiles.json`, kaynak klasörü ve `requirements_win.txt` için yedek alın.
- V23.2 küçük yama **yalnızca tam V23.1 kaynak sürümüne** uygulanır. Mevcut V22 veya V23.0 üstüne tek başına kopyalamayın.
- Yamayı ayrı test klasörüne açın, klasör yapısını koruyarak birleştirin, testte doğrulamadan canlıya taşımayın.
- `python -m pytest -q tests/test_v232_matrix_curriculum_preview.py tests/test_v231_curriculum_identity.py tests/test_v23_curriculum_safety.py`

## Kabul kontrolü

- 1366×768, 1280×720 ve 1024×768; Windows %100/%125/%150 ölçeklendirmesinde düğme ve pencere açılıyor mu?
- Ders/geçerli öğrenci seçilmeden konu kapsamı başka kişiye ait içerik getiriyor mu? **Getirmemeli.**
- Sarı/yeşil kilitli tiklerin davranışı ve kaydedilmiş ödevlerin görünümü **V23.1 ile birebir aynı** mı?
- Öğrenci değiştirince önceki kişinin kapsam bilgileri tekrar açılabiliyor mu? **Açılamamalı.**
- Coğrafya gibi aynı adlı konular uyarı veriyor mu? **Vermeli.**
- Yedek alıp geri yükleme, açma/kapatma ve Ödev Kontrol/Form işlemleri önceki sürüm gibi çalışıyor mu?

## Sıradaki geliştirme için zorunlu koşul

Kapsam özel konularının da gerçek ödev satırı olarak kullanılabilmesi için `odev` ve `odev_satir` kayıtlarıyla ilişkili, kapsam+öğrenci+ders+konu kimliğini atomik ve geri alınabilir biçimde saklayan ayrı bağlantı modelinin tasarlanması; eski konularla yan yana kullanımının yük ve rollback testlerinden geçmesi gerekir. Bu veri modeli bulunmadan V23.1 ID'lerinin sayısal parçaları `odev.konu_id` alanına yazılmamalıdır.
