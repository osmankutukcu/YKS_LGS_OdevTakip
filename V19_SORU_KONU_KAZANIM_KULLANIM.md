# V19 – Modüler Soru–Konu Kanıtı

## Amaç
Bir denemenin **öğrenci + ders + soru numarası** için, öğretmenin doğruladığı konu bilgisini saklamak; Konu Haritası ve Öğrenci 360° üzerinde göstermektir. **Kazanım kodunun doğruluğu, bu sürümde resmî MEB/ÖSYM kaynağından ayrıca doğrulanmaz.** Bu nedenle kod açıkça `dosyadan beyan edilen` olarak belirtilir. Soru doğru, yanlış veya boş olsa bile tek veriyle akademik teşhis yapılmaz.

## Nereden açılır?
- **Deneme Sınavları → ilgili deneme → öğrenci satırı → 🔗 Soru–Konu**
- **Konu Haritası → Birleşik Konu Kanıtları → 📥 Soru–Konu Dosyası**
- **Koçluk Planı → Öğrenci 360° → Konu Kanıtları → 📥 Soru–Konu Dosyası**

## CSV/TSV/XLSX şablonu

`ogrenci_id,deneme_id,ders,soru_no,sonuc,konu,kazanim_kodu`

**Bu satır yalnızca başlıktır, öğrenci verisi değildir.** Satırları öğretmen onayıyla doldurun. Bir denemede ders sonucunun önceden Deneme Sınavları ekranına kaydedilmiş olması gerekir. `sonuc` için `doğru`, `yanlış`, `boş` kabul edilir. `kazanim_kodu` isteğe bağlıdır; resmî doğrulanmış çıktı değildir.

## Akış
1. İlgili öğrenciyi ve denemeyi seçin. Sistem başka öğrenciye varsayılan olarak geçmez.
2. CSV veya Excel dosyasını seçin ve önizlemede hataları/uyarıları kontrol edin.
3. Ekran **Yeni / Değişecek / Aynı / Hata** durumlarını gösterir. Herhangi bir hata varsa hiçbir satır kaydedilmez.
4. Ders–konu eşleşmeleri mevcut öğrenci konularında yoksa uyarı verilir. Öğretmen konuyu doğrulamadan işaretlemez.
5. Öğretmen onay kutusunu işaretleyerek kaydeder. Sadece V19'un ayrı soru kanıtı tablosu ve değişiklik günlüğü güncellenir.
6. Birleşik Konu Kanıtları'na dönün; doğru/yanlış/boş sayılarının ve gerekçelerin görüntülendiğini kontrol edin.

## Güvenlik ve sınırlar
- Yeni `soru_konu_kanit_v19` ve `soru_konu_kanit_log_v19` tabloları **yalnızca ilk onaylı kayıt sırasında** oluşturulur.
- Eski `odev`, `odev_satir`, `odev_takip`, `denemeler`, `deneme_sonuclari`, `koc_konu_takip` kayıtları değiştirilmez.
- Öğrenci/deneme/ders eşleşmesi, soru numarası, sonuç sayıları, tekrarlanan satırlar kontrol edilir.
- Önizleme alındıktan sonra ilgili deneme sonucu veya soru kaydı değişmişse işlem durur.
- Öğretmenin onayladığı metnin yanlış olması algoritmayla tamamen engellenemez; özgün sınav soru–konu anahtarını öğretmen kontrol etmelidir.
- PDF fotoğraf OCR, resmî kazanım katalog taraması ve otomatik soru sınıflandırma **bu sürümde yapılmaz**. Bunların varlığı varsayılmamalıdır.
- İçeri aktarma, arka planda kendi kendine başlamaz; öğretmenin açık onayı gerekir.

## Test önerisi
- İki farklı öğrenciye ait aynı soru numarasını dene: kayıtlar karışmamalı.
- Elektrostatik ve Elektrostatik Ek: kısmi konu eşleşmesi olmamalı.
- Aynı dosyayı tekrar yükle: ikinci kez ekleme olmamalı.
- Kaydedilmiş konu bağlantısını değiştir: tek satır güncellenmeli ve eski değer işlem günlüğünde saklanmalı.
- Önizleme açıkken deneme sonucunu başka oturumdan değiştir: kaydetme durmalı.
- Manuel tik / Sihirbaz / Takviye / Eksikler / Öneri / Haftalık plan işlevleri değişmemeli.
- Gerçek Mac ve Windows PyQt6 ekran testi ayrıca yapılmalı.

## Dağıtım
V18 kaynak koduna **yalnızca değişen dosya yamasını**, yolu korunarak uygulayın. V18 yerine doğrudan çalışan v3.5.17 kurulumu varsa önce kaynak farklarını birleştirin. Kurmadan önce SQLite + JSON profil yedeği alın. Kullanıcı veritabanını kaynak ZIP'e eklemeyin.
