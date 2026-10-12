# Ödev Takip V23.5 – Bütünleşik Stabilizasyon ve Kabul Denetimi

**Taban kaynak:** `OdevTakip_V23_4_Kapsam_Kontrol_Kumulatif_Kaynak_Veriler_Haric.zip`  
**Tarih:** 12 Ekim 2026  
**Durum:** Salt okunur çapraz-modül denetim kodu, sentetik entegrasyon testleri ve kabul kılavuzu hazır. **Windows üretim dağıtımı onaylanmadı.**

## 1. Neden yeni özellik eklemedik?

V23.4 ile kapsam özel ödevleri Ödev Kontrol penceresinden açılabiliyor. Ancak üretim güvenliği için ana genel ödev kayıtları ile yeni kapsam kayıtlarının birbirinden bağımsız kalması, yanlış öğrencilerin karıştırılmaması, durum geri almanın yalnızca doğru tabloda işlem yapması ve Windows düşük çözünürlükte araçların erişilebilir olması doğrulanmalı. V23.5, eski GUI/kayıt yolunu tekrar yazarak risk oluşturmak yerine bağımsız kabul katmanı ekler.

## 2. Eklenen modüller

| Yeni dosya | İşlev |
|---|---|
| `services/stabilization_v235/__init__.py` | Küçük ve bağımsız API |
| `services/stabilization_v235/audit.py` | Genel/özel ödevleri **ayrı** sayan, SQLite quick_check, kopuk bağlantı ve yanlış öğrenci bağını tespit eden salt okunur denetim |
| `tools/audit_integration_v235.py` | `mode=ro` ve `PRAGMA query_only=ON` ile güvenli komut satırı denetimi; sıfır otomatik düzeltme |
| `tests/test_v235_integrated_acceptance.py` | Öğrenci izolasyonu, durum geri alma, eski tabloların korunması, bozuk bağlantı ve eksik tablo testleri |
| `tests/test_v235_cli_readonly.py` | CLI çıkış kodu, sahte/eksik DB ve dosya değişmezliği kontrolü |
| `V23_5_WINDOWS_BUTUNLESIK_KABUL_KILAVUZU.md` | Windows öğretmen kabul senaryoları, DPI/ekran matrisi ve güvenli kurulum |

**Değiştirilmeyenler:** `ui/homework_form.py`, `ui/odev_kontrol.py`, `ui/student_workspace_panel_v21.py`, mevcut konu servisleri, kayıt/tik/geri alma kodu, veritabanı şeması. Bu pakette üretim GUI davranışına doğrudan değişiklik yapılmadı.

## 3. Veri hesaplaması neden ayrı?

- `odev` ana ödev kaydı: mevcut kontrol durumları, transfer/silinme ayrı hesaplanır.
- `kapsam_odev_v233`: `devam/tamam/iptal` olarak **ayrı** sayılır; ana kontrol yüzdesine katılmaz.
- `odev_satir.odev_id → odev.id`: kopuk bağlantı ve eşleşmiş satırın öğrenci kimliği kontrol edilir. Bağlantı yoksa kendiliğinden yeni ödev atılmaz.
- Öğrenci ID'si olmayan veya var olmayan öğrenciye ait satırlar bildirilir. Rapora varsayılan olarak **öğrenci adı/ID** yazdırılmaz.
- Ödevin bitmesi konu hâkimiyeti olarak yorumlanmaz; başarı/puan yüzdesi üretilmez.

## 4. Gerçek veritabanı kontrolü

V13.6 nihai ZIP içindeki `YKS_LGS_HomeworkManager.db`, ayrı kopyaya alınarak **salt okunur** incelendi:

| Denetim | Değer |
|---|---:|
| SQLite `quick_check` | `ok` |
| Aktif öğrenci | 16 |
| Ana ödev | 565 |
| Kapsam ödevi | 0 (V23.3 öncesi yedek; beklenen) |
| `odev_satir.odev_id` kopuk bağlantı | **3** (önceki V13.6 bulgusu devam ediyor) |
| Öğrencisi farklı eşleşmiş satır | 0 |

Bu veri üzerinde hiçbir otomatik düzeltme/silme/yazma yapılmadı. Salt okunur denetim, 3 kopuk bağlantı nedeniyle **uyarı ve çıkış kodu 1** verdi. Bu, yeni V23.5 bug'ı veya öğrenciye otomatik yeni ödev oluşturulması değildir.

## 5. Otomatik testler

- Yeni **13 entegrasyon + 4 CLI = 17** test başarılı. V23.3/V23.4 ve V21 testleriyle birlikte **69** hedefli/önceki test başarılı.
- Geniş regresyon: son çalıştırmada **764 başarılı**, **48 alt test başarılı**, **1 atlandı**, **4 başarısız**, **4 modül yükleme hatası**. 3 GUI testi ve 4 yükleme hatası bu ortamda PyQt6 bulunmaması; diğer başarısızlık `.github/workflows/build_installer.yml` dosyasının kaynak ZIP'te bulunmamasından.
- CLI araçlarının veritabanı dosyasını değiştirmemesi geçici SQLite testlerinde doğrulandı. Gerçek yedek kontrolünde de kaynak dosya üzerinde yazma yapılmadı.
- **Bu sonuçlar**, Windows'taki EXE/otomatik güncelleme, PyQt6 gerçek tıklama, çoklu ekran DPI davranışı ve bütün PDF/WhatsApp yollarını doğrulamaz.

## 6. Mevcut yapıyı koruma güvencesi ve açık konular

1. Ana Ödev Takip / Kontrol / Sihirbaz / Planlayıcı koduna yama yapılmadı; sadece yeni bağımsız dosyalar eklendi.
2. 3 eski kopuk `odev_satir` bağlantısı, otomatik onarıma uygun kesin eşleştirme bulunmadığı için **aynen bırakıldı**.
3. Ana ödevler ile kapsam ödevleri farklı kurallara ve veri tablolarına sahiptir; ortak ölçüm/rapor ürünleri geliştirilecekse kaynak etiketi zorunlu olmalıdır.
4. Kullanıcının Windows'ta çalışan **v3.5.17** kaynağıyla V23.4/V23.5 zinciri henüz karşılaştırılıp birleştirilmedi. Bu ZIP çalışan EXE'nin üzerine kurulamaz.
5. Gerçek Windows 1366×768 %125/%150, 1280×720 %150, veri kalıcılığı, rollback ve GitHub kurulum/test iş akışı, saha kabulüne açık kalır.

## 7. Tavsiye edilen sonraki adım

**Önce Windows pilot kabulü ve son v3.5.17 kaynak birleştirmesi.** Yeni versiyon sayısını artırmak yerine hata çıkmayan tek üretim adayı hazırlanmalıdır. Böylece kullanıcıların çalışan ödev vermesi, kontrol etmesi, müfredat yönetmesi ve öğrenci özeti görmesi korunur.
