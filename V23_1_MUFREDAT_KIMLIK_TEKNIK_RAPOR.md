# Ödev Takip V23.1 – Müfredat Ortak Konu Kimliği ve Güvenli Eşleştirme

**Tarih:** 12.10.2026  
**Kaynak:** `OdevTakip_V23_0_Mufredat_Moduler_Kumulatif_Kaynak_Veriler_Haric.zip`  
**Hedef:** V23.0 müfredat güvenlik katmanını koruyarak Genel, Grup ve Öğrenci kapsamlarındaki konu kimliklerini ayıran *salt okunur* bir servis ve öğretmen denetim arayüzü.

## Yönetici özeti

V23.1'in ilk korumalı aşaması hazırdır. Konuların kaynak tablosundaki sayısal ID'si tek başına kimlik kabul edilmiyor. V23.1 kimlikleri **ders, kapsam türü, kapsam sahibi ve satır ID** ile ayırıyor. Belirsiz eski ödev eşleşmeleri otomatik düzeltilmiyor. Kullanıcı Ders/Konu Düzenle tablosunda sağ tıkla **Konu Kimliği ve Çakışma Denetimi (V23.1)** raporuna ulaşabilir.

**Bu sürüm ana ödev matrisinin okuma yolunu değiştirmez.** V23.2 için güvenli hazırlık katmanıdır; eski konu ve ödev tablolarını migrate etmez.

## Neyi değiştirdik?

**Düzenlenen tek mevcut dosya**

- `ui/topic_editor.py`: Sağ tık menüsüne V23.1 denetimi eklendi; mevcut kayıt, silme, yeniden adlandırma ve etkin liste fonksiyonlarına dokunulmadı.

**Yeni modüller**

- `services/curriculum_v231/identity.py`: `TopicIdentity`, Türkçe harf farkını koruyan ada göre karşılaştırma anahtarı.
- `services/curriculum_v231/reader.py`: Genel → tam eşleşen Grup → Öğrenci sıra ve önceliğini SQL `SELECT` ile sunar; kaynağı, kapsamdaki gölgelenen kayıtları ve belirsizlik uyarılarını döner.
- `services/curriculum_v231/legacy.py`: Tarihsel adı veya genel tablo ID'si belirsiz olan eski ödevler için `unique / ambiguous / missing / mismatch / name_changed_review` değerlendirmesi. Eski ödevlere yazmaz.
- `services/curriculum_v231/__init__.py`: Dış API.
- `ui/curriculum_identity_dialog_v231.py`: Salt okunur rapor ekranı, düşük çözünürlüklü Windows ekranlarına göre sınırlanmış pencere boyutu.
- `tests/test_v231_curriculum_identity.py`: 23 yeni hedefli test.
- `V23_1_MUFREDAT_KIMLIK_KILAVUZU.md`: Kurulum ve kullanım belgesi.

## Veri güvenliği ve varsayımlar

1. **Sıfır şema geçişi:** SQLite tablolarına yeni kolon/indeks eklenmedi; `odev`, `odev_satir`, `konu_istatistik` ve `grup_konu_duzen` / `ogrenci_konu_duzen` değiştirilmedi.
2. **Çift kimlik ayrımı:** Aynı dersteki `id=1`, genel/grup/öğrenci kapsamlarında farklı kayıtlardır. Kalıcı olarak kullanılacak referans mevcut SQLite kaydının ömrüne bağlıdır; bağımsız veritabanlarında çakışmayan küresel UUID değildir.
3. **Konu adı eşitliği, kimlik eşitliği değildir:** Genel ve öğrenci kapsamındaki `Elektrik` adları etkin listede öğrenci önceliği ile gösterilebilir. Ancak tarihsel bir ödevin hangi kayda ait olduğu kesin değilse eski ödev otomatik yeniden bağlanmaz.
4. **Eksik öğrenci/grup bağlamı:** Grup kaydı kesinleşmiyorsa başka grubun konuları getirilmez. Başka öğrenci ID'si veya grup uyumsuzluğu hata verir.
5. **Tarihsel ID–ad uyumsuzluğu:** Yeniden adlandırma ya da farklı eşleştirme olasılığında otomatik çözüm yerine manuel inceleme sonucu döner.
6. **Önceki V23.0 kayıt güvenliği olduğu gibi kalır.** Yeni kod dosyalarının hiçbiri UPDATE, INSERT, DELETE veya schema değişikliği yapmaz.

## Testler

- `tests/test_v231_curriculum_identity.py` + `tests/test_v23_curriculum_safety.py`: **40 passed, 4 subtests passed**.
- Geniş regresyon: **697 passed, 48 subtests passed, 1 skipped, 4 failed, 4 collection errors** (PyQt6 bağımlılığına bağlı 3 GUI başarısızlığı ve 4 koleksiyon hatası; eksik `.github/workflows/build_installer.yml` kaynaklı 1 dağıtım testi başarısızlığı).
- V23.1 ile ilgili Python kaynaklarının sözdizimi kontrolü başarılı.
- Eski v3.5.16 gerçek veritabanı yedeğinin *ayrı, salt okunur kopyasında* 16 öğrenci × 3 ders = **48 başarılı görünüm**, 0 okuma hatası; SHA-256 dosya özeti önce/sonra aynı. Bu yalnızca veri okuma testidir; gerçek Windows GUI kabul testi değildir.
- ZIP CRC/bütünlük kontrolleri başarılı; eski V23.0 paketindeki hiçbir dosya çıkarılmadı.

## Tamamlanmayanlar

- **Ana Ödev Takip Formu** `db.ders_konularini_cek()` yolunu bu sürümde kullanmaya devam ediyor. Kimlik servisini doğrudan matrisle birleştirmek yeni bir değişikliktir ve V23.2 için bırakılmıştır.
- Gerçek Windows %125/%150 DPI altında PyQt6 ekran tıklama testleri burada yapılamadı.
- Eski aynı adlı konuların geçmiş ödevlere otomatik eklenmesi, yeniden adlandırılması veya onaylı toplu taşınması yapılmadı.
- Resmî MEB/Maarif Modeli sınıf/ünite/kazanım uygunluğu teyidi bu sürümün kapsamına alınmadı.

## Kurulum

1. Çalışan sistemin ZIP, DB, profil dosyaları ve EXE yedeğini alın.
2. **V23.0 yüklü ayrı test çalışma klasörüne** `OdevTakip_V23_1_Mufredat_Kimlik_Yalnizca_Degisen_Dosyalar.zip` dosyasını açın.
3. Ders/Konu Düzenle → bir ders ve kapsam seçin → konu tablosunda sağ tık → **Konu Kimliği ve Çakışma Denetimi**.
4. Raporu farklı öğrenci ve gruplar için karşılaştırın. Ana matristeki eski ödev ve tikler aynı kalmalıdır.
5. Çalışan v3.5.17 uygulamanız V23.0 kaynak zinciri ile henüz karşılaştırılmadıysa güncellemeyi doğrudan canlı klasörüne yüklemeyin.

## V23.2 için koşullar

Yeni etkin liste eski matrisin yerine kullanılmadan önce sırasıyla: öğrenci/grup kimliği karşılaştırması, görünür ders/konu sayımı, örnek tik verilerinin birebir korunması, eksik/çakışan konu raporlarının öğretmen onayı, rollback ve düşük çözünürlüklü Windows kabul testi. **Değişiklik güvenle geri alınamıyorsa canlıda açılmayacak.**
