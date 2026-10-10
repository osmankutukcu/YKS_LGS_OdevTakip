# YKS–LGS Ödev Takip V3.5.4 — Kararlılık ve Veri Bütünlüğü Raporu

**Hazırlanma tarihi:** 10 Ekim 2026  
**Başlangıç sürümü:** V3.5.3 kaynak kod adayı  
**Yeni sürüm:** V3.5.4 kaynak kod adayı  
**Çalışma türü:** Yeni kullanıcı işlevi eklemeksizin hata giderme, SQLite işlem güvenliği, ödev eşleştirmesi ve geriye dönük regresyon kontrolü.

## 1. Kapsam ve önemli sınırlar

V3.5.3'teki mevcut öğrenci, ödev, koçluk, sınav, raporlama, PDF ve GitHub güncelleme modülleri korunmuştur. V3.5.4'te yoğunlukla `web_api/main.py` ve `web_api/homework_store.py` değiştirilmiştir. **Bu dosya Windows üzerinde çalışan yeni bir EXE değildir.** Linux test ortamında FastAPI, geçici SQLite veritabanları, derleme/CI betikleri ve birim testleri doğrulanmıştır. PyQt6 bağımlılığı bulunmadığından gerçek `db.get_conn()` ve Windows masaüstü arayüzünün birlikte çalışması bu ortamda uçtan uca doğrulanmamıştır.

## 2. Gerçekleştirilen düzeltmeler — ne, neden, nasıl

| No | Problem / risk | Düzeltme ve yaklaşım | Kontrol |
|---|---|---|---|
| 1 | Mobil toplu ödev kaydı olmayan öğrenciye yazabiliyordu. | `create_bulk_homework`: öğrenci kaydı işlem başlamadan kontrol ediliyor; geçersizse işlem duruyor. | Yetim küme üretilmedi. |
| 2 | Toplu kayıtta sahte ders adı veya olmayan/yanlış ders konusu kabul edilebiliyordu. | Ders beyaz listesi, gerçek konu tablosundaki ID/ad eşleşmesi doğrulanıyor; dinamik SQL yalnızca izinli tabloya uygulanıyor. | Geçersiz tablo ve konu reddedildi. |
| 3 | Boş ya da aşırı büyük toplu istek ve geçersiz konu/kitap satırı kaydedilebiliyordu. | 1–500 satır sınırı, trim/boş kontrolü, aynı istek içindeki eş ödevlerin tekilleştirilmesi. | Sınır/tekrar testleri. |
| 4 | Toplu kayıtta başlık `lgs_matematik`, alt satır `LGS Matematik` olabiliyordu. | Her iki tabloda kalıcı ders anahtarı kullanılıyor. Ekrandaki görünen ders etiketine dokunulmadı. | Yeni kayıtlar ve bağlantılar karşılaştırıldı. |
| 5 | Hatalı teslim tarihleri veritabanına girebiliyordu. | Tekli ve toplu API için `YYYY-MM-DD` geçerli takvim tarihi kontrolü. Boş tarihe önceki 7 gün varsayılanı uygulanıyor. | 2026-02-31 / farklı biçim reddedildi. |
| 6 | İki eşzamanlı istek önce okuyup sonra yazmaya çalışırken SQLite kilit çakışması veya eski duruma göre işlem riski taşıyordu. | Tekli/tümel ödev yazma ve durum güncelleme API'lerinde `BEGIN IMMEDIATE`; commit/rollback tek işlem içinde. | 32 eşzamanlı sentetik API isteği başarılı ve başlık/satır tutarlı. |
| 7 | İşlem ortasındaki SQL hatası bağlantısız başlık, satır veya kitap bırakabilirdi. | Tek SQLite işlemi içinde yazma ve herhangi bir hata anında rollback; HTTP 422 için de rollback korundu. | Sentetik tetikleyiciyle ikinci satırda hata: hiçbir ek kayıt kalmadı. |
| 8 | Kullanıcının aynı tamamla komutunu yeniden göndermesi daha önceki tamamlanma tarihini ileri taşıyabiliyordu. | `set_single_line_done` ve `set_headers_done` zaten tamamlanmış kaydın mevcut zaman damgasını koruyor; geri alıp tekrar tamamlamada yeni zaman kullanılıyor. | Eski tarih koruma testleri. |
| 9 | Eski şemadan gelen, tek başlığa kesin ait olan birden fazla `odev_id IS NULL` alt satırın yalnızca biri bağlanabiliyordu. | Başlık benzersiz ve öğrenci/küme/ders/konu/kitap eşleşmesi kesin olduğunda tüm alt satırlar bağlanıyor; belirsiz eşleşmede tahmin edilmiyor. | Çoklu eski satır ve farklı ders testleri. |
| 10 | Tek bağlı alt satır tamamlanınca, aynı üst ödevin bekleyen eski bağlantısız satırı görmezden gelinebiliyordu. | Üst ödev durumu hesaplanmadan önce kesin eşleşen eski alt satırlar da hesaplamaya dahil ediliyor. | Üst durum yalnızca bütün satırlar bitince tamam oluyor. |
| 11 | Bozuk yabancı öğrenci ilişkisiyle bağlanmış alt satırlar toplu durum değişikliğinden etkilenebiliyordu. | Üst/alt satırın öğrenci ve küme alanları eşleşmeden durum değiştirilmez. | Sahte farklı öğrenci satırı değişmedi. |
| 12 | Küme sorgusu hata verdiğinde SQLite bağlantısı açık kalabiliyordu. | Küme listeleme metoduna `try/finally: con.close()` eklendi. | Kaynak kapanma regresyonunda küme API'si eklendi. |

**Not:** Aynı istekte yinelenen ödevlerin tekilleştirilmesi, farklı HTTP isteklerinin iki kez gönderilmesini otomatik olarak tekilleştirmez. İstekler arası tam idempotency anahtarı bu sürümde yoktur. Eski şemada belirsiz kayıt eşleştirmeleri bilinçli olarak otomatik onarılmaz.

## 3. Test sonuçları

```
python -m pytest -q tests
102 passed, 23 subtests passed

python tools/validate_release.py
Release surumu kontrol edildi: 3.5.4

python -m compileall -q .
Başarılı
```

- Yeni dosyadaki **14** veri dayanıklılığı testi: geçersiz öğrenci/ders/konu/tarih, boş ve çoklu giriş, aynı istekte çoğaltma, 119 kayıtla yeniden açma, sentetik orta-işlem hata, eski bağlantısız kayıtlar, tekrar tamamlamada tarih koruma, bozuk FK ilişkisi ve 32 paralel HTTP isteği.
- Sürüm `version.py` / `version.json` / Inno Setup `setup.iss` **3.5.4** olarak eşleşiyor.
- GitHub Actions, yeni regresyon test dosyasını Windows dağıtımından önce çalıştırmak üzere genişletildi.
- Testler sentetik SQLite verisi üzerinde çalıştırıldı; gerçek öğrenci kaydı okunmadı veya değiştirilmedi.

### Doğrulama yapılamayan kısımlar

1. Windows PyQt6 masaüstü programı (bu ortamda PyQt6 kurulu değil).
2. Gerçek `db.get_conn()` ile Windows üzerinde çok işlemcili/eşzamanlı masaüstü + web yazma testi; izole süreçle denenince `ModuleNotFoundError: No module named 'PyQt6'` alındı, dolayısıyla geçtiği iddia edilmez.
3. Gerçek GitHub Actions Windows EXE/Inno Setup derlemesi ve kurulu 3.5.3 → 3.5.4 güncellemesi.
4. Elektrik kesilmesi/sistem çökmesi sonrası SQLite dayanıklılığı ve başarısız kurulumdan otomatik eski sürüme dönüş.
5. Veli/öğrenciye yönelik ayrı yetki modeli, uçtan uca HTTPS, ZIP yedek şifrelemesi; önceki sürümün bilinen sınırları sürmektedir.

## 4. Değişen ana kaynak dosyaları

- `web_api/main.py` — doğrulama, kilit/transaction, bağlantı kapama
- `web_api/homework_store.py` — eski kayıt bağlama, zaman damgası koruma ve güvenilir üst/alt durum
- `tests/test_write_durability_v354.py` — yeni regresyon testleri
- `tests/test_stabilization_regressions.py` — küme bağlantı kapama kontrolü
- `.github/workflows/build_installer.yml` — yeni testleri CI'ye ekleme
- `version.py`, `version.json`, `setup.iss`, `utils/updater.py`, `tests/test_update_core.py` — sürüm tutarlılığı

Diğer kaynak modülleri korunmuş, çalışma kapsamı dışındaki büyük masaüstü dosyaları yeniden düzenlenmemiştir.

## 5. Windows kabul testleri (yayından önce zorunlu)

1. Tam kaynak dosyasını **yeni klasöre** açın; mevcut kurulu EXE üzerine elle kopyalamayın. Kaynak paketinde yazı tipleri verilmez; derleme için kendi lisanslı font varlıklarınızı ilgili klasöre koyun.
2. Windows üzerinde Python/PyQt6 bağımlılıklarını kurun ve otomatik testleri çalıştırın.
3. V3.5.3 ve V3.5.4 için ayrı sahte kullanıcı veritabanı hazırlayın; ilk kurulum / yükseltme / geri dönüş işlemlerini test edin.
4. 3 ayrı sahte öğrenciye önce tekli, sonra 100+ satırlı toplu ödev verin. Programı kapatıp yeniden açtıktan sonra tüm başlık, satır, kitap ve küme kayıtlarını doğrulayın.
5. Aynı ödevi masaüstü ve mobil panelden arka arkaya tamamla/geri al; tekrar istek, internet kesintisi ve ağ zaman aşımı senaryolarını kontrol edin.
6. Yedek alıp ayrı bir test klasörüne geri açın; SQLite `PRAGMA integrity_check` ve toplam kayıt sayılarını doğrulayın.
7. GitHub'da Windows Actions testlerini ve sürüm EXE'sinin SHA-256 doğrulamasını geçmeden etiketli sürüm yayımlamayın.
8. Eski kurulum EXE ve yedeği saklayın; hata durumunda kullanıcıya dağıtımı durdurun.

## 6. Yayın kararı

**V3.5.4: Otomatik Python ve sentetik SQLite testlerinden geçmiş stabilizasyon kaynak kod adayıdır. Henüz gerçek Windows kullanımında onaylanmış nihai ticari dağıtım değildir.**
