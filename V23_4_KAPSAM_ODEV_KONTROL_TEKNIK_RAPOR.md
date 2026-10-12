# Ödev Takip V23.4 – Kapsama Özel Ödevlerin Ödev Kontrol'den Yönetimi

**Temel sürüm:** `OdevTakip_V23_3_Moduler_Kumulatif_Kaynak_Veriler_Haric.zip`  
**Tarih:** 12 Ekim 2026  
**İlke:** Ana ödev kontrol, sarı/yeşil tik, kume–satır ilişkisi ve eski sayımlar korunur.  
**Durum:** Kaynak düzeyinde geliştirme ve otomatik regresyon tamamlandı; **gerçek Windows/PyQt6 GUI testi yapılmadı**.

## 1. Önceki sınırlama

Normal ödevler genel ders konularının kimliğini kullanan `odev`, `odev_satir`, `odev_kume` yapısında; V23.3'ün grup/öğrenci kapsam ödevleri `kapsam_odev_v233` tablosunda. Bunları aynı `konu_id` ile tek kontrol tablosunda işlemek yanlış konu ve öğrenci güncellemesi üretebilir. Yeni modül mevcut Kontrol ekranında tek giriş noktası sağlar ancak iki kayıt türünü **hesaplamada ve veritabanında ayrı tutar**.

## 2. Değiştirilen/eklenen dosyalar

| Dosya | Amaç |
|---|---|
| `ui/odev_kontrol.py` | Tek mevcut değişiklik: araç çubuğuna **🎯 Kapsam Ödevleri** butonu ve modal açıcı metot. Ana formun 58 mevcut metodundan yalnızca `_build_ui` değişti; 57'si aynı kaldı. |
| `ui/scoped_control_v234.py` | Öğrenci kimliği sabit modal; ders/durum filtresi, ayrı kapsam satırları, açık/bitmiş/iptal durum yönetimi, işlem geçmişi, ekran boyutuna uyumlu düğme yerleşimi. |
| `services/curriculum_v234/control.py` | Salt-okunur öğrenci özeti, kontrollü durum geçişi ve geri alma, atomik SQLite audit geçmişi. |
| `services/curriculum_v234/__init__.py` | Modüler ve açıklanabilir servis API'si. |
| `tests/test_v234_scoped_control.py` | Öğrenci izolasyonu, mükerrer kayıt/geri alma çakışması, stale durum, audit geri alma, eski tablo bütünlüğü ve modal bağlama testleri. |
| `V23_4_KAPSAM_ODEV_KONTROL_KURULUM.md` | Kullanım, Windows testleri ve güvenli kurulum. |

## 3. İşlem güvenliği ve eski kodla uyumluluk

- Normal ödev tablosuna özel kapsam satırı eklenmedi; normal **Kaydet, Aktar, Hepsi Tamam, Geri Taşı, silme, WhatsApp/PDF** işlemlerine yeni kapsam ödevleri dahil edilmedi.
- Öğrenci seçimi `OdevKontrolDialog.ogr_id` üzerinden sabitleniyor; özel ekranda farklı öğrenci seçilemiyor.
- Yeni durum değişikliği `BEGIN IMMEDIATE`, öğrenci ID'si, satır ID'si, beklenen durum ve SQLite kısmi tekil indeks korumasıyla onaylanıyor.
- `devam → tamam/iptal` ve `tamam/iptal → devam` işlemleri açık kullanıcı onayıyla ve aynı transaction'da audit kaydıyla yapılıyor. Başarısız değişiklikte `ROLLBACK` uygulanıyor.
- Audit tablosu `kapsam_odev_kontrol_log_v234` sadece ilk başarılı durum işlemi içinde oluşturuluyor. Yalnızca ödevleri görmek veritabanı şemasını değiştirmiyor.
- Geri alırken ikinci bir açık ödev aynı ders/konu/kitap anahtarında varsa işlem reddediliyor. V23.3'ün daha önce tamamlanan ödevleri silinmiyor.
- **Bilinçli sınır:** Kapsam ödevleri ana performans yüzdesine veya eski kontrol tablosu tiklerine henüz dahil edilmiyor; çift sayım önleniyor.

## 4. Windows/düşük çözünürlük

Yeni modal ekranın boyutu aktif ekranın kullanılabilir alanıyla sınırlandırılır. 7 sütunlu tabloda yatay kaydırma kullanılabilir; işlem düğmeleri 3+3 biçiminde iki satıra ayrıldı. Eski kontrol toolbar'ı `FlowLayout` kullandığı için yeni düğme de otomatik sarılır.

## 5. Test sonuçları ve sınırlar

- V23.4 + V23.3 çekirdek otomatik testleri: **36 başarılı** (yeni 15, V23.3'ten 21).
- Geniş regresyon: **747 başarılı, 48 alt test başarılı, 1 atlanan, 4 başarısız, 4 modül yükleme hatası**.
- 3 başarısız GUI testi ve 4 toplama/yükleme hatası bu çalışma ortamında PyQt6 olmamasına; 1 test `.github/workflows/build_installer.yml` dosyasının kaynak arşivinde olmamasına bağlı.
- Python sözdizimi kontrolü: kaynak paketteki 252 `.py` dosyasında hata yok (paketleme öncesi kontrol).
- Kaydedilmiş öğrenci verileri üzerinde yazma yapılmadı; değişiklik testleri geçici SQLite belleği üzerinde çalıştırıldı.
- **Gerçek Windows 1366×768/%125 veya 1280×720/%150 ve EXE testleri henüz yapılmadı.** V23.3 kaynağının tabanı v3.5.16; kullanıcının çalışan v3.5.17 sürümüyle birleştirme gereklidir.

## 6. Açık sonraki işler

- Windows üzerinde uçtan uca senaryo doğrulama ve kaynak farklarının birleştirilmesi.
- Kapsam ödevlerini PDF/rapor gibi ortak çıktılara katma istenirse ayrı ve açık **kaynak etiketiyle** yapılmalı; mevcut ana toplamlar değişmemeli.
- Performans ve koçluk hesaplarına özel ödev kanıtı dahil edilirse ayrı kategori ve açıklanabilir oranlar kullanılmalı; otomatik başarı varsayılmamalı.

**Önemli:** Bu sürüm, V23.3'ün özel kapsam kayıtlarını mevcut Ödev Kontrol penceresinden açılabilir ve yönetilebilir yapar. Eski kontrol satırlarını veya ana tikleri fiziksel olarak tek tabloya birleştirmez; bu bilinçli bir veri bütünlüğü kararıdır.
