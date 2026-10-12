# Ödev Takip V23.2 – Müfredat Kapsamını Ana Forma Güvenli Bağlama

**Tarih:** 12 Ekim 2026  
**Taban:** V23.1 kümülatif kaynak (v3.5.16 zinciri); v3.5.17 canlı Windows sürümüyle birebir birleştirme henüz yapılmadı.

## Yönetici özeti

V23.1'deki Genel/Grup/Öğrenci konu kimliği okuyucusu, V22'nin yatay kaydırılabilir ders gezinme çubuğu üzerinden ana Ödev Takip Formu'na bağlandı. **Bu aşama salt okunur entegrasyondur.** Eski sarı/yeşil tikleri, `odev.konu_id` tamsayı kimliklerini, ödev kontrol/kaydet/geri alma fonksiyonlarını ve mevcut müfredat kayıtlarını değiştiren işlem bulunmaz. Grup/öğrenci konuları kapsam farkıyla birlikte görüntülenir, ancak güvenli yazma sözleşmesi kurulmadan ana tik matrisine ilave edilmez.

## Neden doğrudan tüm konuları matrise koymadık?

Ana tabloda `ui/homework_form.py::_ders_tab_olustur()` şu an `db.ders_konularini_cek()` satırlarından genel konu ID'sini kullanır. Kaydedilmiş işaretlerin anahtarı `(ders, konu_id, kitap_ad)` şeklindedir. Grup ve öğrenci konularının kendi tablolarındaki örneğin `id=1` değeri, genel ders tablosunun `id=1` değerinden farklı bir konu olabilir. Her ikisini aynı sayısal ID ile işaretlemek veri karışıklığına yol açar. Yalnızca aynı adı taşımaları kimlik eşdeğerliği kanıtı değildir.

## Dosya ve görev matrisi

| Dosya | Değişiklik |
|---|---|
| `ui/homework_form.py` | Yalnızca `_build_ui` içinde ders gezinme çubuğuna opsiyonel bağlantı. `_ders_tab_olustur`, `_tik_degisti`, kayıt/kontrol yöntemleri değişmedi. |
| `services/curriculum_v232/bridge.py` | Salt okunur, kapsamlı konu listesini eski matris satırlarıyla karşılaştırır; çakışma/kapsam uyarıları sağlar. |
| `services/curriculum_v232/__init__.py` | Ayrı modül ihracı. |
| `ui/curriculum_matrix_preview_v232.py` | Windows DPI mantıksal kullanılabilir alanını dikkate alan modal önizleme; öğrenci değişim koruması. |
| `tests/test_v232_matrix_curriculum_preview.py` | Eşleşme, kapsam, mükerrer isim, veri değişmezliği ve ana form bağları. |
| `V23_2_MUFREDAT_KAPSAM_ONIZLEME_KURULUM.md` | Kullanıcı ve test yönergesi. |

## Doğrulanmış otomatik testler

- V23.2 / V23.1 / V23.0 hedefli testler: **54 başarılı + 4 alt test başarılı** (ilk test turu; ek doğrulama testleri de paketlendi).
- Tüm projenin regresyon testi: **711 passed; 1 skipped; 48 subtests passed; 4 failed; 4 collection errors**. Başarısız üç GUI testi ve dört koleksiyon yükleme hatası PyQt6 bulunmamasına; bir test ise ZIP içinde bulunmayan `.github/workflows/build_installer.yml` dosyasına bağlıdır. Bunlar gerçek Windows GUI doğrulaması yerine geçmez.
- Sözdizimi taraması: **244 Python dosyası, 0 hata**.
- AST bazlı ana form karşılaştırması: sadece `OdevTakipFormu._build_ui` farklı. `_ders_tab_olustur`, tikleme ve ödev kaydetme metotları değişmedi.
- Önceki yedekteki gerçek SQLite veritabanı **`mode=ro`** kullanılarak: **16 aktif öğrenci × 20 ders = 320 kontrol, 0 okuma hatası**, 6816 konu görüntü satırı; veritabanı SHA-256 değişmedi. Coğrafya gibi aynı başlıklı konu kayıtları uyarı olarak belirdi. Görüntüleme sayısı farklı öğrenciler ve dersler üzerinden toplanmıştır; benzersiz konu sayısı değildir.

## Tamamlanmamış işler ve risk sınırları

1. Yeni grup/öğrenci konularını ana tik/kaydet listesine güvenle ekleyen **yazma adaptörü bulunmuyor**. Bu özellik bilinçli olarak kapalı.
2. Gerçek Windows 10/11, PyQt6, DPI %125/%150 tıklama/sığma testleri henüz yapılmadı.
3. v3.5.17 çalışan kaynakla V23.2'nin v3.5.16 tabanlı dosyaları ayrı test klasöründe karşılaştırılarak birleştirilmeli.
4. Önceki veritabanı incelemesindeki belirsiz konu eşleşmeleri ve bağlantısız eski kayıtlar otomatik değiştirilmedi.

## Kurulum kararı

**V23.2 kaynakta hazırdır; canlı kurulum için test bekliyor.** V23.1 üstüne küçük yama veya ayrı dizinde kümülatif ZIP kullanın. Windows'a geçişten önce veri/kod yedeği ve tıklama, kaydetme, geri alma, öğrenci değiştirme kabul testleri zorunludur.
