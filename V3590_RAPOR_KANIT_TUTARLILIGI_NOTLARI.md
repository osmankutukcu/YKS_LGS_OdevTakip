# KoçPilot 360 V3.5.90 – Rapor Kanıt ve Veri Tutarlılığı Pilotu

**Durum:** Kaynak kodu pilotu. Windows/macOS kullanıcı kabulü henüz yapılmadı; GitHub üzerinden müşterilere yayımlanmaz.

## Önce / neden / nasıl / sonuç

| Önce | Neden | Yeni uygulama | Kullanıcı açısından |
|---|---|---|---|
| Rapor Merkezi'ndeki Veri Kontrolü yalnızca aynı öğrenci/küme/ders anahtarının iki kaynakta bulunma sayısını veriyordu. | Bu benzerlik mükerrer ödevin kesin kanıtı değil; gerçek bağlantı ve sahiplik kontrolü gerekiyordu. | `services/report_integrity_v3590.py`, mevcut `canonical_homework_evidence_v3535.py` motorunun doğruladığı kanıt sayılarını anonim olarak sunuyor. | Belirsiz kayıtlar, açıklanabilir uyarılarla öğretmen kontrolüne yönlendiriliyor. |
| Bir öğrenciye ait eksik veya başka öğrenciye bağlanmış görev kaydı bütünleşik raporun sayılarından açıkça anlaşılamıyordu. | Yanlış sahiplikle ilişkilendirilen kayıtlar, güvenilir öğrenci yorumu yapılmasını engeller. | `audit_student_integrity()` yalnızca seçili öğrencinin kendisine, üst görevine veya ödev kümesine bağlanan satırları kontrol ediyor. | Kişiler arası veri karışması ve eksik tarih için uyarı ekleniyor; öğrenci hakkında otomatik hüküm verilmiyor. |
| Büyük veri kümelerinde kapsamlı tarama arayüzü yavaşlatabilir. | Her kurumun kayıt hacmi farklıdır. | Küme ön denetimi için 15.000 satır, öğrenci için 5.000 satır sınırı var. Sınır aşılırsa taranmış gibi davranılmıyor. | “Sınırlı denetim” mesajıyla belirsizlik açıkça belirtiliyor. |
| Kaynak sürümü ile kuruluma hazırlık bilgisi birbirine karışabiliyordu. | Pilotun yanlışlıkla yayımlanmasını önlemek gerekiyor. | `version.py`, `version.json` ve `setup.iss` 3.5.90 olarak eşitlendi; kanal hâlâ **pilot**. GitHub Windows iş akışına yeni regresyon testi eklendi. | Testler geçmeden ürün sürümü yayımlanmamalı. |

## Değiştirilen / eklenen kaynaklar

- **Yeni:** `services/report_integrity_v3590.py` — salt-okunur, kişisel bilgi döndürmeyen global ve öğrenci düzeyli sahiplik/kanonik kanıt ön denetimi.
- **Güncellendi:** `services/integrated_report_v3584.py` — eski sayıları değiştirmeden `notes` bölümüne ihtiyaca göre veri kalitesi uyarısı ekler.
- **Güncellendi:** `ui/report_center_v3581.py` — mevcut **Veri Kontrolü** düğmesi artık daha anlamlı, anonim kanıt özetini gösterir. Altı yönlendirme kartı aynı kalır.
- **Yeni:** `tests/test_report_integrity_v3590.py` — farklı öğrenci bağlantısı, belirsiz bağımsız satırlar, açık üst görev eşleşmesi, tarih/durum belirsizliği, satır sınırı, eksik şema, veri gizliliği ve salt-okunur testler.
- Sürüm uyumu ve yayın hattında `version.py`, `version.json`, `setup.iss`, `tools/v3588_unified_preflight.py`, `.github/workflows/build_installer.yml` güncellendi. `README.md` pilot sürümü işaret eder.

## Değişmeyen davranışlar

- Ödev Takip ve Ödev Kontrol formlarının tıklama, checkbox, renklendirme, kilit, kaydetme/geri alma ve aktarma işlemleri **değiştirilmedi**.
- Ana pencere yerleşimi, Rapor Merkezi altı kartı, mevcut PDF ve Excel motorları **değiştirilmedi**.
- Raporların mevcut SQL sorguları ve tamamlanma oranları sessizce yeniden hesaplanmadı.
- Öğrenci ve veli verileri dış servise aktarılmıyor. Çevrimiçi akademik karşılaştırma bu sürümün kapsamında değil.

## Kısıtlar ve yorumlama kuralları

1. Bu denetimin “temiz” çıkması, öğrenci başarısının doğrulandığı anlamına gelmez. Yalnızca kontrol edilen bağlantıların yapısal tutarlılığını belirtir.
2. `odev` ve `odev_satir` içindeki **aynı öğrenci/küme/ders** benzerliği tek başına mükerrer kayıt kanıtı değildir. Bu satırlar otomatik silinmez/birleştirilmez.
3. Toplu kanonik ödev sayıları ile hafta/30 gün veya PDF sayıları farklı dönemleri kapsayabilir; birbirine doğrudan eşitlenmemeli.
4. Eksik veya eski veritabanı şeması, değerlendirme sınırının aşılması ve hatalı tarih **sınırlı/doğrulanamadı** olarak gösterilir.
5. Öğrenci bütünleşik raporu notları yalnızca veri kalitesi uyarısıdır; öğretmen onayı olmadan mesaj göndermez, görev değiştirmez veya risk teşhisi koymaz.
6. Dağıtılabilir tam kaynak ZIP'inde **yazı tipi dosyaları bulunmaz**. PDF motoru için kullanıcının önceki yasal/yerel kurulumundaki `fonts/` gereksinimi ayrıca karşılanmalıdır. Küçük yama ZIP'i mevcut font klasörüne dokunmaz.

## Testler

İlgili regresyonlar: **159 test, 51 alt kontrol geçti.** Korumalı 10 temel kaynak dosyası kendi SHA-256 manifestiyle eşleşti. Tek-kök preflight geçti.

**Doğrulanmayanlar:** PyQt6 ile gerçek macOS/Windows pencere etkileşimleri, PDF yazdırma/yazıcı, Windows EXE kurulum/açılış ve GitHub dağıtımı. Gerçek cihaz kabulü yapılmadan canlı müşteriye yayın yapılmaz.

## Kurulum önerisi

1. Kullanıcı veritabanını ve çalışan sürümü yedekleyin; mevcut dizinin üzerine körlemesine kopyalamayın.
2. Yalnızca **V3.5.89** kaynakları üstüne kurulacaksa küçük yama ZIP'ini test kopyasına dosya yolunu koruyarak uygulayın. Birleştirilmiş kaynak ZIP'i alternatif test kopyasıdır.
3. Mevcut yerel PDF fontları ve gereken bağımlılıkları test ortamında sağlayın.
4. `python -m pytest -q tests/test_report_integrity_v3590.py tests/test_integrated_report_v3584.py tests/test_report_interpretation_v3589.py` ve Windows manuel kullanım senaryolarını çalıştırın.
5. Rapor Merkezi → Veri Kontrolü'nde açıklamaları doğrulayın; ardından öğrenci seçimi, tekli/toplu PDF, çıktı alma, Ödev Takip/Ödev Kontrol ve otomatik güncelleme kabul testlerini tamamlayın.
