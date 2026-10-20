# KoçPilot 360 — Aşama 11 / Kaynak Etiketi v3.5.70 (PİLOT)

## Karar: Var olan haftalık planlayıcıyı koru, yeniden yazma

Mevcut **Akıllı Haftalık Planlama & Takvim Sihirbazı** ödevleri Verilen Ödevler tablosundan alır; öğrencinin okul/uyku/uyanma/özel ders/kurs/dinlenme/sabit rutinlerini, çalışma kapasitesini ve gün bazlı gelişmiş ayarlarını kullanıp A4 yatay PDF oluşturur. Bu çalışma akışı **aynı kalmıştır**. Planlayıcının sekmeleri, kayıtlı rutin profilleri, Kaydet/Güncelle/Öğrenciye Ata/Hazır Planı Oluştur–Önizle akışı, mevcut HTML ve PDF şablonları değiştirilmemiştir.

## Bu aşamada gerçekten eklenenler

1. **YENİ `services/weekly_coaching_alignment_v3570.py`:** v3565 ortak otomatik koçluk motorunun **mevcut, öğrenciye ait ve aynı gün doğrulanmış** tavsiyelerini, mevcut haftalık verilen ödevler listesiyle eşleştirir. Saf fonksiyon; veri yazmaz, yeni görev/süre/saat/PDF satırı üretmez.
2. **MEVCUT YARDIMCI `ui/weekly_planner_adaptive_bridge_v35.py`:** Halihazırdaki **Genel Bakış → Adaptif Koçluk Önerilerini İncele** düğmesinin işlevini tamamlar. Eski adaptif öğretmen notu sonuçları korunurken, güvenilir yeni v3565 kanıtları da aynı onay penceresine eklenebilir. Ana form, ödev kontrol veya planlayıcı sekmelerinde yeni buton oluşturulmadı.
3. **Sınırlı öncelik:** Yalnızca *farklı günlerde tekrar doğrulanmış düşük ölçüm* için v3565 `TARGETED_REVIEW`, mevcut ödevde **tam ders + konu eşleşmesi varsa**, öğretmenin onayına sunulan geçici konu önceliği adayı olabilir. Mevcut V35 `accepted_topic_pairs` mekanizması tekrar kullanılır. Öğrencinin kaydedilmiş genel ders önceliği, başka konuları ve ödevler değiştirilmez.
4. **Ölçüm ayrı tutuluyor:** `INTERVENTION_FOLLOWUP`, `SPACED_RETRIEVAL`, `INDEPENDENT_RECHECK`, `CLARIFY_OBSERVATION` ve `OPTIONAL_INDEPENDENT_CHECK` gibi adımlar **yeni ödev sayılmaz**. Aynı haftanın verilen ödevleriyle konu bazında eşleşirse kısa bilgi notu olarak gösterilebilir; PDF'ye satır/süre/ek görev eklenmez.
5. **Fail closed:** Yanlış öğrenci, eski tarih, değiştirilmiş otomatik atama işareti, sahte ustalık iddiası veya bozuk kaynak sonucu yeni koçluk önceliğine dönüşmez. V35'in eski gözlem önerileri geriye dönük çalışmaya devam eder.
6. **Kullanıcı deneyimi:** Sadece mevcut düğmeye açıkça tıklandığında koçluk kaynağı okunur; normal checkbox, Ödev Kaydet veya PDF oluşturma sırasında ek koçluk sorgusu yapılmaz. Aynı SQLite salt-okunur görüntüsünde okuma yapılır; yeni kaynak için 350 ms sorgu süresi koruması vardır. Gecikirse yeni öneri kullanılmaz, eski işlev devam eder.

## Bilerek değiştirilMEYENLER

- `ui/homework_form.py`, `ui/odev_kontrol.py`, `ui/plan_settings_dialog.py`, `ui/weekly_planner_overview_v35.py`
- `services/smart_calendar.py`, `services/planning_constraints.py`, `services/weekly_topic_priority_v35.py`, `services/weekly_planner_presentation_v35.py`
- `ui/research_coaching_bridge_v3563.py` ve diğer v3.5.60–69 modülleri
- Ödevlerin sayısı, süreleri, kaydetme/geri alma/checkbox işlemleri, rutin profilleri, haftalık PDF sayfa şablonu

## Test durumu

- `tests/test_weekly_coaching_alignment_v3570.py`: Öğrenci sahipliği, tarih, doğrulanmamış kanıt, gerçek ders/konu eşleşmesi, tekrarlanan nedenler, okul ve PDF'ye veri eklememe gibi yeni kontrat testleri.
- Seçilen haftalık planlama/öğrenme/koçluk regresyon testleri: **177 geçti, 36 alt test geçti**. Qt PDF sayfa sayısı doğrulama testi, bu ortamda gerçek PyQt6 bulunmadığı için ayrı tutuldu (**1 test çalıştırılmadı**). Daha önce dahil edilerek çalıştırıldığında PyQt6 eksikliği nedeniyle hata verdi; bu, üretim ortamı doğrulaması değildir.
- `python tools/v3527_core_guard.py --root .`: **PASS** (sadece kaynak sözleşmesi; kaynakta daha önceden var olan iki gölgelenmiş metot uyarısı sürüyor).
- Herhangi bir üretim veritabanına yazılmadı; Windows/EXE arayüz, PDF çıktısı ve yüksek DPI testleri henüz **YAPILMADI**.

## Kabul testi (Gerçek Windows)

1. Eski sürüm ile aynı örnek öğrencide planlayıcının tüm sekmelerini, profil Kaydet/Güncelle/Öğrenciye Ata davranışını karşılaştırın.
2. Öğrencinin sabit kurs/okul/uyku saatlerini kaydedin, A4 yatay planın aynı gün/saat aralıklarını ve aynı toplam dakika/görev sayısını koruduğunu doğrulayın.
3. Aynı ders/konuda *iki farklı gün düşük bağımsız ölçüm* varken var olan **Adaptif Koçluk Önerilerini İncele** butonuna basın; yalnız öğretmen onayından sonra aynı verilmiş konuya öncelik verildiğini kontrol edin.
4. Müdahale sonrası kontrol veya aralıklı tekrar önerisini inceleyin; **yeni ödev veya PDF satırı oluşturmadan** bilgi mesajında kaldığını doğrulayın.
5. Başka öğrenciye geçin, yanlış öğrenciye ait öneri çıkmadığını test edin.
6. Öğrencinin mevcut başka görevleri ve ödev tablosunun checkbox, kilit, renk, kayıt/geri alma davranışlarının değişmediğini kontrol edin.
7. Test sonunda yeni kaynak önerileri yoksa mevcut V35 adaptif düğme davranışının aynen sürdüğünü doğrulayın.

**Yayın kararı:** PİLOT. Müşterilere/otomatik GitHub güncellemesine göndermeyin. v3.5.70 ZIP etiketi, uygulama içi sürüm/version.json veya lisans sistemini değiştirmez.
