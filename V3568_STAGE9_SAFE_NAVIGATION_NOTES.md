# KoçPilot 360 — v3.5.68 / Aşama 9 — Güvenli Koçluk Yönlendirmesi (PİLOT)

## Ne geliştirildi?

v3.5.67 paketi temel alınmıştır. Mevcut Ödev Takip ekranı, Ödev Kontrol ekranı, checkbox, kaydetme, geri alma, renk, kilit ve ana sayfa yerleşimi **değiştirilmemiştir**.

- **YENİ** `services/coaching_navigation_v3568.py`: Aynı gün ve aynı öğrenci için doğrulanmış `v3565` akademik önceliğini, mevcut Öğrenme ekranına; doğrulanmış `v3564` mevcut kitap–konu taslağını ise var olan Sihirbaz ekranına yönlendirmeye uygun salt-okunur menü öğelerine dönüştürür. Yeni taslak, ödev, checkbox veya mesaj oluşturmaz.
- **YARDIMCI GÜNCELLEME** `ui/research_coaching_bridge_v3563.py`: Arka plan analizinden alınmış aynı öğrenciye ait kaynaklar sadece mevcut öğrenci için bellekte tutulur. Öğrenci değişimi veya kayıt yenilemesi sırasında eski yönlendirme önbelleği temizlenir. `navigation_recommendations_v3568()` aracılığıyla güncel, kontrollü öneriler sağlanır.
- **YARDIMCI GÜNCELLEME** `ui/homework_context_integrations_v2.py`: Mevcut konu tablosu sağ tık menüsündeki **Mevcut Merkezlere Git** grubuna yalnızca doğrulanmış öneri varsa **Koçluk önerisinden işleme geç** alt grubu eklenir. Öneriye tıklanırsa eski `execute_existing()` çağrılır; hiçbir yeni ekran veya ayrı kayıt yolu oluşturulmaz.
- **YENİ** `tests/test_coaching_navigation_v3568.py`: öğrenci değişimi, tarih uyumsuzluğu, yasak otomatik işlem bayrakları, eşleşmemiş kitap, eski yüklü matris, özellik kapatma ve menü açıldığında işlem olmaması kontrolleri.

## Kullanıcıya görünen fark

Ana formun yeri, boyutu, butonları ve tablosu **aynıdır**. Öğretmen eski konu tablosunda sağ tık yapınca ve güvenilir akademik öneri mevcutsa menüde bir alt seçenek görebilir:

- **Öğrenme kontrolünü incele** → eski `btnOgrenme` düğmesinin zaten bağlı bulunduğu işlem.
- **Mevcut Sihirbaz taslağını incele** → eski `btnSihirbaz` düğmesinin zaten bağlı bulunduğu işlem. Burada eşleşme yeniden değerlendirilir, öğretmen onayı ve mevcut Kaydet işlemi hâlâ gereklidir.

Eşleşme yoksa, öneri henüz hesaplanmadıysa, farklı öğrenci seçildiyse veya öğrenci verileri değiştiyse yeni menü gösterilmez veya tıklama güvenli biçimde reddedilir. Önerilen konu Sihirbaz içinde otomatik seçilmez. Her şey kullanıcı tıklamasıyla başlar.

## Geri dönüş

Yeni menü katmanını kapatmak için:

- `QSettings('EduTrack','HomeworkManagerV2')` anahtarı `coaching_navigation_v3568_enabled=0`, veya
- çalıştırma ortamında `KOCPILOT_COACH_NAV_V3568=0`.

Eski sağ tık menüsü ve tüm mevcut modüller kullanılmaya devam eder. Bu pilot için ayarlarda yeni kontrol oluşturulmadı.

## Test, güvence ve sınırlar

- Seçili regresyon kümesi: **190 başarılı, 1 atlandı, 38 alt test başarılı**.
- `python tools/v3527_core_guard.py --root .`: **PASS** (salt-okunur statik kaynak sözleşmesi).
- Önceki v3.5.67 kaynaklarıyla SHA-256 karşılaştırması, Ödev Takip / Ödev Kontrol / Sihirbaz / eski Koç Asistanı'nın aynen kaldığını doğrulamalı (paket üretim adımında yapılır).
- **Windows/PyQt6 gerçek GUI ve EXE performans kabul testleri henüz yapılmadı.** Bu kaynak paketi üretim ortamına otomatik güncellemeyle gönderilmemelidir.
- Uygulamanın kendi `version.py` / `version.json` numaraları değiştirilmedi; `v3.5.68` yalnızca kaynak geliştirmenin etiketidir.

## Windows kabul testi

1. Önce v3.5.67 ile ödev ver–Kaydet, geri al, kilit, renklendirme ve kontrol davranışını kaydedin.
2. Güncel öğrenme kaydı olan öğrencide konu tablosuna sağ tıklayın; yalnızca doğrulanmış öneri varsa yeni alt menünün açıldığını kontrol edin.
3. Öğrenci A için menüyü açıp B'ye geçin, sonra A'nın önerisine tıklayın; herhangi bir ekranın yanlış öğrenciyle açılmaması gerekir.
4. Eski öğrenciye ait matris ekranda kalmışsa Sihirbaz yönlendirmesinin engellendiğini kontrol edin.
5. Menüde öneriyi seçmeden ekran değişimi, ödev oluşturma veya tik değişimi olmamalıdır.
6. Özelliği `coaching_navigation_v3568_enabled=0` yapınca önceki menü biçimine dönmelidir.
7. Farklı monitör ölçeklerinde, Windows DPI'da ve yavaş veritabanında tıklama gecikmesini ayrıca ölçün.
