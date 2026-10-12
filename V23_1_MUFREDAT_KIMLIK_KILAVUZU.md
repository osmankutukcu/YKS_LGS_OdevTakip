# V23.1 – Ortak Müfredat Kimliği ve Çakışma Denetimi

## Amaç

V23.0'da güvenli hale getirilen Ders/Konu Düzenle bölümündeki **Genel, Grup ve Öğrenci** kapsamlarının konu kimliklerini birbirinden ayırmak. İlerideki ana matrise geçişten önce eski kayıtların nerede belirsiz kaldığını **veritabanına yazmadan** görebilmek.

## Kullanım

1. **Ders/Konu Düzenle** ekranını açın.
2. Önce **Genel**, **Grup** veya **Öğrenci** kapsamını, sonra dersi ve gerekiyorsa grup/öğrenciyi seçin.
3. Konu tablosunda **sağ tıklayın** → **Konu Kimliği ve Çakışma Denetimi (V23.1)**.
4. Etkin konu listesinde her konunun **Genel/Grup/Öğrenci** kaynağı ve kendi satır ID'si gösterilir.
5. Bir üst kapsamdaki ad yeni kapsamda tanımlanmışsa, öncelikte geride kalan kaynaklar da görünür. Aynı kapsamda ad çakışması veya öğrenci grup bilgisi eksikse uyarı alırsınız.

Bu ekran sadece **görüntüler**; silme, yeniden adlandırma, eski ödevleri bağlama, tikleme, güncelleme ve yeni tablo oluşturma işlemi yapmaz.

## Kimlik sözleşmesi

- Bir konu `ders + kapsam + kapsam sahibi + tablodaki id` ile tanımlanır.
- Genel `fizik:id=1`, grup `YKS/12-say/fizik:id=1` ve öğrenci `öğrenci=1/fizik:id=1` **üç farklı kayıttır**.
- `TopicIdentity.key` aynı veritabanında aynı kaynak satırı için yeniden hesaplanabilir. Ancak bağımsız iki veritabanı, silinip tekrar oluşturulmuş bir kayıt veya taşıma işlemi için evrensel/kalıcı UUID değildir.
- Etkin liste (Genel < Grup < Öğrenci) bir **görüntüleme** önceliğidir; eski ödevlerin aynı adlı konuya otomatik yeniden bağlanacağı anlamına gelmez.
- Geçmiş ödevin adından veya eski sayısal `konu_id` alanından kapsam kesin belirlenemiyorsa `resolve_legacy` bilinçli olarak **ambiguous / mismatch / name_changed_review** verir.
- Resmî müfredat/kazanım kodu veya iki farklı konu arasında anlamsal eşdeğerlik iddiası yoktur.

## Güvenli deneme / kurulum

- Önce çalışan v3.5.17 ile dosya farkını karşılaştırın; bu paket V23.0/v3.5.16 kaynak zincirinden gelir.
- Yedek alın: SQLite, öğrenci plan profilleri, kurulum klasörü.
- **V23.0 üzerine V23.1 yalnızca değişen dosyaları** uygulayın. V22 üzerine doğrudan uygulamayın.
- `python -m pytest tests/test_v231_curriculum_identity.py tests/test_v23_curriculum_safety.py -q`
- Windows'ta 1366×768 / %125 ölçeklendirmede sağ tık denetimini açıp rapor penceresinin ekran içinde kaldığını kontrol edin.
- Şimdilik ana matriste konu listesi V22/V23.0 gibi çalışmaya devam eder; V23.2'de korumalı adaptörle geçiş yapılacaktır.

## V23.2 geçiş koşulları

Ana formun konu okuması değiştirilmeden önce tüm mevcut öğrenci/grup/konu kayıtları için karşılaştırmalı rapor oluşturulmalı, aynı isimli farklı kapsam kayıtları manuel değerlendirilmiş olmalı, geçmiş tiklerin ve `odev` / `odev_satir` satırlarının birebir sabit kaldığı kanıtlanmalıdır.
