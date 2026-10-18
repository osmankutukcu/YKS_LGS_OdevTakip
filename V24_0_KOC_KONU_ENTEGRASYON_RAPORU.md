# V24.0 Koçluk Planı + Konu Haritası — İlk Güvenli Entegrasyon Raporu

**16 Ekim 2026** · Dayanak: kullanıcının son yüklediği `YKS_LGS_HomeworkManager_v2_Son_Hal(2).zip`. Bu değişiklikler kaynak ZIP'in birebir kopyasına uygulanmıştır; öğrencinin aktif bilgisayarında kurulum yapılmamıştır.

## Hedef

Ödev Takip / Ödev Kontrol'ü kayıtların ana otoritesi olarak korumak. Konu Haritası ve Koçluk Planı'nın mevcut servislerindeki çalışmaları yok etmeden, iki ekranı **aynı ve kaynağı açıklanmış** öğrenci kanıtlarına bağlamak. Aynı ödevi iki defa saymamak; koçluk hâkimiyet puanını sınav başarısı sanmamak.

## Somut kod değişiklikleri

1. **`services/coach_shared_topic_v1.py` (yeni)**: Salt-okunur `read_shared_topic_summary()`, halihazırdaki `services/topic_evidence_v18.read_topic_evidence()` servisini yeniden kullanır. Ana ödev `odev/odev_satir` (küme eşleşmesi kontrolü), Konu Haritası `odev_takip`, öğretmen işaretleri `koc_konu_takip` ve onaylı soru kanıtları (`soru_konu_kanit_v19`, yalnızca geçerli denemeye bağlı olan) kendi kaynaklarıyla okunur. Kaynakları otomatik olarak aynı görev türüne dönüştürmez. Belirsiz kitap/konu eşleşmelerini tek hâkimiyet sayısına indirgemez. Öğrenci ID doğrulaması vardır.
2. **`ui/coaching_manager.py`**: Konu Takibi alanında teknik tablo üzerinde, seçili öğrenci ve derse ait iki satırlık ortak kanıt özeti ve açıklaması gösterilir. Hızlı aramalar sırasında gereksiz ardışık sorguları azaltmak için 350 ms tek-seferlik zamanlayıcı kullanılır. Öğrenci ve ders değişimlerinde özet yenilenir. Eski ödev ve hedef kaydetme fonksiyonları değiştirilmedi. “Genel Takip” için kitap kapsamı yardım ipucu kondu; öznel hâkimiyet/sınav başarısı ayrımı metinlerde netleştirildi.
3. **`ui/topic_map_dialog.py`**: Konu Haritası üstünde seçili öğrenciye ait aynı salt-okunur kaynak ayrımı ve kanıt özeti gösterilir, ekran yenilendiğinde tekrar okunur. Kart, mikro ödev, hâkimiyet işareti, PDF ve yazdırma fonksiyonlarına dokunulmadı. Yerel konu önem etiketleri güncel ÖSYM araştırması gibi sunulmaz.
4. **`services/student360_v16/reader.py`**: Öğretmen tarafından işaretli konu sayacı önceki `durum=2` yanında tam hâkimiyet anlamındaki `durum=4` değerini de tanır. Tarihî kayıtlar ve veri şeması değiştirilmedi. Bu sayaç bağımsız ölçülmüş başarı değil, öğretmen işaretidir.

## İstemeden değişmeyen alanlar

`ui/homework_form.py` ve `db.py` arşivdeki orijinal dosyayla **birebir aynıdır**. `_tik_degisti`, ödev tamamlama/geri alma/kilit/renk davranışı, mevcut koçluk yazma sorguları, mikro ödev oluşturma, `koc_hedef` plan oluşturma, sınav/deneme yazma işlemleri ve öğrenci verileri güncellenmedi. SQL migrasyonu yoktur.

## Test ve kurulum kabulü

- Entegrasyon, izolasyon, öğrenci ayırımı, bilinmeyen ders adı, iki farklı kitap, salt-okunur SQLite, V18/V19 kanıtları, eski/new 360 konu durumu ve V14/V15 performans bileşenlerinin seçilmiş test takımı: **168 başarılı test ve 4 başarılı alt test**.
- Kod sözdizimi dört Python dosyasında doğrulandı.
- Tam kaynak ZIP'ten alınan dört dosya için SHA-256 korumalı kurulum; `clean` -> `installed` -> `clean` geri alma ve ikinci kez kurulum/no-op doğrulandı.
- Tanınmayan kaynak içeriği reddedildi. Yedek dosyalar ve kurulu içerik bütünlüğü geri alma öncesinde doğrulanır.
- Gerçek öğrenci veritabanında test yapılmadı; gönderilen ZIP'te bu veriler bulunmuyor. PyQt6 bu ortamda olmadığı için Mac/Windows canlı GUI testi yapılamadı.

## Kalan entegrasyon işleri

1. Son commit sonrasında `student_id`, ders ve kaynak içeren **salt-haber olayları** yayınlamak, ilgili açık ekranların veriyi yeniden okumasını sağlamak; döngüsel karşılıklı yazma yapmamak.
2. Ana formda seçili öğrenci bilgisini Koçluk, Hedef Analizi, Konu Haritası ve Koça Sor'a güvenli taşımak; varsayılan ilk öğrenciye sessiz geçişi önlemek.
3. LGS/YKS uygun ders seçimi, kitap bazlı genel özet, konu kimliği/alias sözlüğü ve ölçülen başarı / öğretmen kanaati ayrımını UI boyunca tutarlı yapmak.
4. Öğrencinin ana ödevden Koçluk Planı'na iş planı önerisi için öğretmen onaylı, ayrı kayıt/atama adımları; otomatik checkbox değiştirme **yapılmayacak**.
5. `_tik_degisti` eski koruma imzası uyuşmazlığı ve gerçek Windows/Mac testleri çözülmeden sürümü canlıya yükseltmemek.

**Durum:** V24.0 bir **güvenli ortak kanıt okuma pilotudur**, bütün modüllerin çift yönlü/anlık entegrasyonu değildir.
