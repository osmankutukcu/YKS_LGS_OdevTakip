# KoçPilot 360 V3.5.91 — Akademik kanıtı açıklayan bütünleşik rapor (PİLOT)

## Önce / neden / nasıl / kullanıcının kazancı

| Önce | Sorun | Çözüm | Faydası |
|---|---|---|---|
| Deneme özeti ile koçluk konu işaretleri raporda ayrı alanlarda bulunuyordu. | Öğretmen aynı dersin iki kaynağını ilişki kurmadan okumak zorundaydı. | Yeni `services/report_academic_bridge_v3591.py` modülü, **aynı öğrenci ID’sine** ait son 90 gün deneme **ders ölçümlerini** ve **tüm dönemlerin öğretmen konu işaretlerini** sınırlamalarıyla yan yana gösterir. | Hangi bölümün ölçüm, hangisinin kayıtlı öğretmen işareti olduğu anlaşılır. |
| “Matematik” ders adı birden fazla sınav türünde geçebiliyordu. | TYT / AYT / LGS yanlış karışabilir. | Sınav türü + bilinen kesin ders kodu birlikte eşleştirilir; belirsiz adı eşleştirilmemiş olarak belirtilir. | Başka kapsamdan net aktarılma riski azaltılır. |
| Aynı sınav ve ders için çift satır çıkabiliyor. | İki netin toplanması veya ortalama alınması yanıltır. | Çift kayıt sayısı işaretlenir; net birleştirilmez. Yeni/eski sınav kaynakları ayrı tutulur. | Kullanıcıya sahte başarı değeri gösterilmez. |
| Koçluk durum işaretleri “kazanım başarısı” sanılabiliyor. | İşaret, sınavdaki o kazanımın doğru çözüldüğünü kanıtlamaz. | “Öğretmen konu işareti” olarak yazılır; konu bazlı sınav başarısı ya da neden-sonuç iddiası üretilmez. | Yorumlar kanıt sınırına sadık kalır. |

## Neler değişti?

- **Yeni:** `services/report_academic_bridge_v3591.py`: sınav ve ders türü eşleşmesi, son 90 gün, öğrenci ID, mükerrer net, öğretmen konu işareti çelişkisi, kapasite uyarıları, salt-okunur analiz.
- **Güncellendi:** `services/integrated_report_v3584.py`: PDF/önizlemede *Ders ölçümleri ve konu işaretleri* adlı ek kaynak bloğu. Mevcut sayısal ödev/deneme/hedef hesapları değiştirilmedi.
- **Yeni:** `tests/test_report_academic_bridge_v3591.py`: sentetik iki öğrencide kimlik yalıtımı, ders disambiguasyonu, çelişki, çift ölçüm, dönem, salt-okunur ve eksik şema testleri.
- **Sürüm ve pilot kanalı:** `version.py`, `version.json`, `setup.iss`, `.github/workflows/build_installer.yml`, `README.md`.

## Sınırlar / güvenlik

- Sınav neti **ders düzeyinde ölçümdür**. Sınavın sorularının hangi kazanıma ait olduğu bu tablolarda doğrulanmadığından konu veya kazanım öğrenildi/öğrenilmedi teşhisi yapılamaz.
- Koçlukta `durum=4`, **öğretmen tarafından işaretlenmiş** anlamına gelir; otomatik olarak “öğrendi” demek değildir.
- Ödev bitişi ile sınav başarı/netteki artış arasında **neden-sonuç ilişkisi** kurulmaz.
- Deneme verisi son 90 gün; koçluk konu işaretlerinin tarihi filtrelenmez. Bu kapsam PDF'de açıkça yazılır.
- Belirsiz ders, yeni/eski çift kaynak, çoklu aynı sınav/ders, eksik veritabanı şeması, aşırı büyük kayıt miktarı **kesin yoruma çevrilmez**. Sınır: 20.000 deneme satırı / 5.000 öğrenci konu satırı; aşılırsa akademik kısım sınırlanır.
- Ağ çağrısı veya öğrenci verisinin haricî sunucuya gönderimi **yok**. ÖSYM/MEB verileriyle otomatik eşleştirme bu sürümde yoktur.
- Ödev Takip, Ödev Kontrol, `main_window.py`, korumalı rapor çekirdeği ve haftalık planlayıcı kodu **değiştirilmedi**.
- PDF için gerekli yerel fontlar telif ve dağıtım koşulları nedeniyle teslim ZIP dosyalarına eklenmedi. Mevcut yasal font klasörünü koruyun.

## Doğrulama

- Sentetik veriyle **191 otomatik test, 64 alt kontrol başarılı**.
- 10 kritik/korumalı dosyanın SHA-256 değeri proje koruma manifestiyle eşleşiyor.
- Örnek bütünleşik PDF üretildi; iki A4 sayfa; akademik bölüm ikinci sayfada.
- `python -m tools.v3588_unified_preflight` ve `python tools/validate_release.py` kaynak kontrolleri geçti.
- Gerçek Windows/macOS GUI, yazıcı, Windows EXE ve GitHub otomatik güncelleme **henüz kabul edilmedi**. Müşterilere dağıtmayın.

## Yükleme / önerilen test

1. Gerçek veritabanını ve mevcut V3.5.90 kaynaklarını **yedekleyin**; canlı kaynakları otomatik değiştirmeyin.
2. Bir test klasöründe V3.5.90 üzerine küçük yamayı **klasör yollarını koruyarak** çıkarın. Alternatif olarak tam pilot kaynak paketini ayrı dizine çıkarın.
3. Önce `python -m pytest -q tests/test_report_academic_bridge_v3591.py tests/test_integrated_report_v3584.py` çalıştırın.
4. Gerçek verilerle yalnızca yetkili öğretmen hesabından öğrenciyi seçerek PDF önizleme, çıktı, eksik/çift kayıt ve öğrenci değiştirme akışlarını doğrulayın; kullanıcı kayıtlarını değiştirmeyin.
5. Gerçek Windows/macOS ve EXE kabulü tamamlanmadan kanal `pilot` olarak kalsın.
