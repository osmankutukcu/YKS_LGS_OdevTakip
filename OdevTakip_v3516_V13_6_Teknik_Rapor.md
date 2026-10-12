# YKS/LGS Ödev Takip v3.5.16 – V13.6 Teknik Rapor

## Amaç

V13.5'te saptanan SQLite ödev bağlantı tutarsızlıklarını **tahmin ederek düzeltmeyen**, manuel inceleme ve onay gerektiren, yalnızca yeni kopyada işlem yapan güvenli uzlaştırma sistemi.

## Kaynak ve izlenen veri

Temel proje: `OdevTakip_v3516_V13_5_Veriler_Haric_Tam_Kaynak.zip`. Doğrulama için v3.5.16 geliştirici yedeğindeki SQLite dosyasının kopyası salt okunur modda incelendi. Çalışan veritabanı güncellenmedi.

İncelemede `odev_satir.odev_id` alanı karşılığı bulunamayan **3 satır** doğrulandı. Satırlar aynı öğrenci ve ödev kümesiyle bağlantılıdır. Aynı öğrenci+küme+tam ders–kitap–konu eşleşmesiyle **0 güvenilir aday** bulundu. Bu, kaydın kendisinin kesinlikle yanlış olduğu anlamına gelmez: geçmiş silme veya farklı veri akışları incelenmelidir. Her üç kaydın önerilen durumu `review` olarak bırakıldı; herhangi bir düzeltme yapılmadı.

## Yeni kaynak dosyaları

- `services/homework_reconciliation_v136.py`: salt okunur rapor, imzalı olmayan fakat SHA-256 satır-fingerprint ile tutarlılık denetlenen inceleme şeması; sert kısıtlı inceleme ve yalnızca kopyaya yazma motoru.
- `tools/reconcile_homework_v136.py`: komut satırından `review` ve açık `apply` seçenekleri.
- `tests/test_v136_safe_reconciliation.py`: 22 sentetik regresyon testi.
- `V13_6_VERI_UZLASTIRMA_KULLANIM.md`: uygulama ve koruma yönergeleri.

## Geliştirilen korumalar

1. İşlem öncesinde öğrenci kimliği, küme kimliği, eski bağlantı, satır parmak izi doğrulanır; eski manifest reddedilir.
2. Doğrulanmadan yeni satır/ödev yaratılmaz; yalnızca mevcut bağı temizleme veya kanıtlı mevcut ödeve bağlama desteklenir.
3. Yeniden bağlama yalnızca aynı öğrenci ve kümede, birebir ders–kitap–konu eşleşmesinde ve aynı hedef zaten başka satıra bağlı değilse mümkündür.
4. Değişiklik için gerekçe ve açık onay ifadesi gerekir. Şüpheli kayıtların varsayılan işlemi `review` (beklet).
5. Kaynak dosya `mode=ro` ve `PRAGMA query_only=ON` ile açılır. SQLite `backup()` yöntemi ile **mevcut olmayan yeni dosya** üretilir.
6. Değişiklikler transaction içinde yazılır, SQLite bütünlük testi ve V13.5 bağlantı denetimi uygulanır. Yeni uyarılar artarsa kopya reddedilir.
7. Kaynak dosyanın üzerine yazılmaz; onaylı kopyada yapılan ID değişiklikleri ayrı JSON işlem günlüğüne kaydedilir.
8. Kaynak/satır eskidiğinde, yeni kopuk kayıt oluştuğunda, çift vaka olduğunda veya hedef başka öğrenciye aitse işlem reddedilir.

## Test sonuçları

| Çalışma | Sonuç |
|---|---|
| V13.6 hedefli sentetik testler | **22/22 başarılı** |
| Önceki modüllerle geniş PyQt6-hariç koşum | **460 test ve 44 alt test başarılı** |
| Çalıştırılmayan testler | **3 GUI testi** + **3 Qt bağımlı modül** + `utils/test_motive_settings.py` |
| Kaynak kod sözdizimi | **188 Python dosyası başarılı** |
| Gerçek yedek veri için salt okunur inceleme | **3 kopuk bağlantı, 0 güvenilir hedef adayı** |

### Sınırlamalar

Bu sürüm, geçmiş ödevlerin silinme sebebini otomatik kanıtlayamaz; güvenilir yedekler yoksa bağlantı hâlâ belirsizdir. CLI onayını veren kişinin kimliği kriptografik olarak doğrulanmıyor; kurumun dosya/işlem yetkilendirmesi ayrıca uygulanmalı. Canlı masaüstü uygulamaya otomatik veri geçişi veya otomatik onarım yapılmamaktadır. Gerçek macOS/Windows ekran testleri tamamlanmadı.

## Güvenli sonraki adım

1. Önce Mac ve Windows test kopyasında manuel tikleme → kaydet → yeniden aç → geri alma zincirini deneyin.
2. Üç kopuk bağlantının geçmişini orijinal/önceki yedeklerden veya yetkili öğretmen kayıtlarından doğrulayın; kanıt yoksa olduğu gibi bırakın.
3. Yalnızca belgeli yönetici kararıyla üretilmiş yeni veritabanı kopyasını ayrı bir test kurulumunda doğrulayın.
4. Test geçmeden canlı veritabanı dosyasını değiştirmeyin. Yeni kodu kurarken font ve kişisel profil dosyalarını koruyun.
