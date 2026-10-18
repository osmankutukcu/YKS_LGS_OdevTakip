# V24.5 – Koçluk Planı Tek Bakış Özeti ve Ortak Veri Bağlantısı

## Hedef ve mevcut durum

V24.4 birleşik kaynak üzerine **7 sekmeye yeni sekme eklemeden**, Koçluk Planı'nın sekmelerin üstünde sabit kalan **salt okunur öğrenci özeti** eklendi. Öğretmen başka ekranları açmadan kaynak kapsamı belli bilgileri görebilir; tek düğmeyle ilgili mevcut sekmeye geçebilir.

## Eklenenler

- Seçili öğrenci ve haftaya ait toplam soru hedefi / kaydedilmiş çözülen soru / ders sayısı (koçluk planı).
- Ana Ödev Takip/Ödev Kontrol kayıtlarından açık ve tamamlanmış satır sayısı; eski/yeni ödev gölge kayıtları çift sayılmamaya çalışılır. Teslimi geçmiş açık ödevler öncelik alır.
- Seçili haftadaki kayıtlı program bloğu sayısı; mevcut program girdileri değişmez.
- Sadece son deneme tarihinin mevcut yeni/önceki kayıt biçimlerinde gösterimi; kaynaklar birleştirilerek sahte net veya başarı puanı üretilmez.
- Konu Takibi'nde kitap tekrarı giderilmiş **öğretmen işareti sayısı**; konu öğrenildiği sonucuna dönüşmez.
- Genel özette yalnızca **hassas olmayan** çalışma anketi kayıt adedi; sınav kaygısı/uyku gibi hassas ankete ait varlık veya cevap içerikleri açıklanmaz.
- Görüşme notu **arşiv kayıt adedi**, yapılmış görüşme iddiasına dönüşmez.
- Otomatik öncelik önerisi: haftalık plan eksikliği / kayıt çakışması / gecikmiş açık ödev / boş program / mevcut analizlere bakma. Öğretmen açıkça tıklarsa doğru mevcut sekmeye geçilir; kayıt oluşturma veya düzenleme yapılmaz.
- Öğrenci ve hafta değişiminde aynı öğrenciyi yeniden doğrulayıp özet güncellenir; eski öğrencinin özeti önce gizlenir. V24.1–V24.3 kayıt değişiklik köprüsüne **öğrenci bazında** ikinci salt-okunur abone eklenir. Ders bazlı köprü ve mevcut Konu Haritası kartları korunur.

## Sayıların kapsamı

**Haftalık hedef = seçili haftanın koçluk planı.** **Ana ödev sayıları = seçili öğrenciye ait anlık kayıt durumları; aynı hafta sınırlaması yok.** **Program = seçili haftanın kayıtlı blok sayısı.** **Deneme = en son görülen kayıt tarihi; net analizi değildir.** **Konu = koçluk işareti bulunan benzersiz ders/konu tanımları.** **Anket = genel çalışma anketi kayıtları, psikolojik ölçüm değildir.** **Not = yazılmış kayıt, gerçekleşmiş toplantı garantisi değildir.** Bunlar aynı paydada toplanmaz.

## Kod değişiklik sınırı

- Güncellenen: `ui/coaching_manager.py` (yedi mevcut sekme ve mevcut yazma yolları korunur).
- Yeni: `services/coaching_overview_v245.py` (pure SELECT/okuma, veri kaydı yok).
- **Değişmeyen:** `ui/homework_form.py`, `ui/odev_kontrol.py`, `db.py`, `ui/topic_map.py` (varsa), `services/coaching_safety_v244.py`, `ui/student360_panel_v16.py` ve mevcut sekmelerin kayıt metodları.
- Yeni tablo, migrasyon, internet isteği, otomatik ödev, otomatik Koç Asistanı bildirimi, cihazlar arası senkronizasyon yok.

## Test ve güvenlik

- 19/19 V24.5 sentetik servis/UI-kablolama testi geçti.
- Seçilmiş kapsamda **128 başarılı, 5 atlanan** regresyon testi (bu toplam 19 yeni testi de içeriyor); atlanan testler seçilen eski test paketlerinin durumundan kaynaklanıyor.
- Eksik öğrenci veya hafta, farklı öğrenci, mükerrer plan, aynalanmış ödev, kitap satırları, hassas anket, eksik kaynak, salt okunur bağlantı, görünen sekme yönlendirmesi test edildi.
- Tek adım kurulumun sürüm ön-denetimi, bilinmeyen kaynağı reddetmesi, geri alma ve yeniden yükleme denetimi ayrıca doğrulanır.
- **PyQt6 bulunmadığı için gerçek Windows/Mac grafik arayüz testi yapılmadı.** Ekran yerleşimi ve buton tıklamaları canlı cihazda kontrol edilmeli.

## Riskler / sonraki aşama

Bu sürüm modülleri **ortak, kaynak etiketli bir özet üzerinden bağlar**; bütün eski modüllerin sayım ve konu adlandırma algoritmalarını tekleştirmez. Ana ödev kayıtları bazı eski/yeni biçimlerde farklılaşabilir; mevcut V5 korumalı sayacı kullanır. Görsel test, büyük veri stres testi ve gerçek kullanıcı kabulü beklemektedir.
