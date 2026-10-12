# Ödev Takip V16 – Modüler Öğrenci 360° Entegrasyonu

## Amaç

Mevcut **Koçluk Planı** ekranının altı sekmesini ve veri kayıt işlemlerini değiştirmeden, seçilen öğrencinin bilgilerini ayrı servislerden okumak. Yeni yedinci sekme: **🔎 Öğrenci 360°**.

## Eklenen küçük modüller

| Dosya | Görev |
|---|---|
| `services/student360_v16/models.py` | Değiştirilemez veri sözleşmesi |
| `services/student360_v16/reader.py` | Kimlik doğrulamalı, salt okunur ödev–deneme–koçluk–konu birleştirmesi |
| `services/student360_v16/advisor.py` | Açıklanabilir, temkinli öğretmen kontrol önerileri |
| `services/student360_v16/profile.py` | Haftalık rutin profilinin sadece eşleşme bilgisini okur |
| `ui/student360_panel_v16.py` | Sade kullanıcı sekmesi: yenile, kopyala |
| `ui/coaching_manager.py` | Yalnızca yeni sekme ve öğrenci seçim bağlantısı |
| `tests/test_student360_v16.py` | Öğrenci ayrımı, kaynak doğruluğu ve salt okunurluk testleri |

## Nasıl çalışır?

1. **Koçluk Planı** açılır; öğrenci sol listeden seçilir.
2. **Öğrenci 360°** sekmesi açılınca analiz yapılır.
3. Ödev oranı için var olan V14 motoru; denemeler için V15 motoru kullanılır. Eski ve yeni ödev/deneme kaynakları rastgele birleştirilmez.
4. `koc_plan`, `koc_hedef`, `koc_program`, `koc_konu_takip` sadece seçilen `ogrenci.id` kapsamında okunur.
5. Kaydedilmiş rutin profili varsa durumu gösterilir, saat veya ödev eklemez.
6. Deneme ilerlemesi akademik ustalık olarak gösterilmez; işaretlenmiş konu öğrenilmiş sayılmaz.

## Veri koruması

- Yeni tablo, migration, UPDATE, DELETE veya INSERT yoktur.
- UI `mode=ro` SQLite bağlantısı ve `PRAGMA query_only=ON` kullanır.
- Yeni koçluk ekranı diğer öğrencinin bilgisine otomatik geçmez.
- Eski Koçluk Planı giriş, düzenleme, ders hedefi, anket, deneme ve konu takibi korunur.
- Öğretmen sadece **Özeti Kopyala**ya bastığında içerik panoya alınır.

## Kurulum

1. Önce çalışan kaynak, SQLite ve profil JSON dosyalarının yedeğini alın.
2. V15 tabanlı test kopyasına `OdevTakip_V16_Yalnizca_Degisen_Dosyalar.zip` içeriğini klasör yapılarını koruyarak uygulayın. Alternatif: tam V16 veri içermeyen kaynak ZIP'ini ayrı klasöre açın.
3. Bağımlılıkları ilgili işletim sisteminin requirements dosyasıyla yükleyin.
4. Test kopyasında farklı iki öğrenci seçip **Koçluk Planı → Öğrenci 360°** ekranında kimlik/ödev/deneme/koçluk bilgilerini karşılaştırın.
5. Mevcut hedef oluşturma, güncelleme, ana Ödev Takip formu tikleme, kaydetme ve geri alma senaryolarını ayrıca sınayın.
6. Kaynak paketini Mac'te çalışan **v3.5.17** üzerine doğrudan yazmayın; sürüm farklılıklarını karşılaştırarak birleştirin.

## Sınırlar

Bu sürüm tek yönlü **okuma entegrasyonu** başlatır. Koçluk hedefleri otomatik yazılmaz, sınav sonuçları içeri aktarılmaz, konu haritasındaki `odev_takip` verileri ana ödev tablosuna taşınmaz. Bunlar sonraki kontrollü aşamalardır. Veritabanındaki daha önce bulunan kopuk ödev bağlantıları V16 tarafından değiştirilmez.

**Masaüstü PyQt6 arayüz testi** bu geliştirme ortamında PyQt6 kurulmadığı için yapılamadı. Bu paket canlı kullanım onayı değildir.
