# YKS/LGS Ödev Takip v3.5.16 — V13.4 Çekirdek İşlem Döngüsü Denetimi

## Kapsam

V13.3 kümülatif kaynak kodu esas alındı. Çalışan öğrenci veritabanı, kullanıcı profilleri, fontlar ve gerçek öğrenci kayıtları değiştirilmedi. V13.4 kaynak düzeyinde güncellemedir, Windows/macOS kabul testi henüz yapılmadı.

## Kesin kod tespitleri / yapılan düzeltmeler

1. **Kaydet sonrası yanlış hücre kilidi:** `_kaydet_kume` veritabanına kaydettikten sonra ilk uygun konu/kitap adını arıyordu. Bu arama birebir-tekil eşleşme `unique_exact_cell` ile değiştirildi; yanlış/çift hücrede boya-kilit uygulanmıyor. Kaydetme öncesi öğrenci ve yüklü matrise ait kimlik karşılaştırması eklendi.
2. **Ödev kontrolünden tamamlanma dönüşü:** `_odev_kayit_sonucu_tamamlanan`, kısmi/esnek eski arama ve sinyal üretme riskinden arındırıldı. Öğrenci kimliği doğrulanıyor, yalnızca birebir-tekil hücre sessizce yeşile kilitleniyor.
3. **Eski geri aktarımda kayıtlı kilitlerin kaldırılması:** `_uygula_aktar_listesi`, doğrudan hücre kilidini açmak yerine V8 güvenli manuel tik aktarımını kullanıyor. Veritabanında kayıtlı/korunan hücre yeni taslak gibi işlenmiyor; gereken durumda aktarım atlanıyor.
4. **Kaydedilmemiş ödevlerin yok olması:** `_senkronize_odev_durumlari` artık sağdaki taslak listesinde birebir karşılığı olan, kullanıcıya açık işaretli hücreyi yalnızca veritabanında kaydı henüz olmadığı için temizlemiyor. Doğru öğrenci matrisi doğrulanmadan senkronizasyon çalışmıyor.
5. **Tiki kaldırınca sağda yinelenen satır kalması:** `_tik_degisti` aynı ders/kitap/konu anahtarına sahip birden fazla taslak satır varsa tik kaldırıldığında hepsini siliyor. Diğer konu satırları korunuyor.

## Testler

- `python -m unittest tests.test_v134_homework_lifecycle -v`: **10 / 10 başarılı** (Qt taklit nesneleriyle davranış ve kod denetimi).
- `PYTHONPATH="$PWD:$PWD/tests" python ...`: **368 / 368 seçilmiş regresyon testi başarılı**, 0 hata, 0 başarısızlık.
- Python `compileall`: başarılı.
- Test dışı kalan modüller: `test_update_delivery`, `test_update_pipeline`, `test_v3516_fixes`, `test_whatsapp_and_brief_ui` (PyQt6/runtime GUI bağımlılıkları ve kurulum testleri). Başarı olarak sayılmadı.
- Gerçek Windows/macOS arayüz tıklaması, kayıtlı ödev kilidi ile geri dönüş süreci ve ağ/güncelleme kurulum testleri yapılmadı.

## Kalan riskler ve önerilen sıra

- **Yüksek:** Kaydedilmiş `odev` ile `odev_satir` tabloları arasındaki bilinen 3 kopuk bağlantı, ayrı bir salt okunur incelemeden sonra tek tek uzlaştırılmalı. Otomatik silme/eşleme yapmadık.
- **Yüksek:** Kaydet sonrası yeni kayıtların hemen UI içinde ve yeniden yüklemede aynı görünmesi Qt arayüzünde test edilmeli.
- **Orta:** `_senkronize_odev_durumlari` DB kayıtları `konu_id` ile eşleştiriyor; tarihsel çoklu kayıt/konu ID değişimi senaryoları ek doğrulama gerektiriyor.
- **Orta:** Ana formda hâlâ davranışları farklı olabilen yinelenmiş bazı metotlar mevcut. Toplu silinmedi.

## Güvenli uygulama

1. Mac/Windows canlı kurulumuna dokunmadan hem veritabanının hem öğrenci rutin JSON dosyalarının yedeğini alın.
2. V13.3 test kaynak kopyasını kullanıyorsanız yalnızca V13.4 yamasını uygulayın; V13.3 yoksa veriler hariç V13.4 tam kaynak ZIP'i ayrı bir dizine açın.
3. İki örnek öğrenciyle sırayla deneyin: manuel tik→kaydet→yeniden yükle; aynı tiki geri alma (yalnızca henüz kaydedilmemiş taslakta), Sihirbaz/Takviye/Eksikler/Öneri aktarımı ve dönüş.
4. Kaydedilmiş, tamamlanmış ve gecikmiş ödevlerin kilitlerinin korunmasını kontrol edin.
5. Doğrulama yapılmadan mevcut çalışan kuruluma geçmeyin.

Güncelleme: v3.5.16 kaynak zinciri, V13.3 üzerine V13.4. Bu sürüm tüm masaüstü işlevlerin uçtan uca doğrulandığı anlamına gelmez.
