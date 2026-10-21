# KoçPilot 360 – V3.5.85 Haftalık Planlayıcı Rapor Bağlantısı

## Kapsam ve kullanıcı görünümü

Bu **kaynak kodu pilot yaması** önceki V3.5.81–V3.5.84 raporlama yenilikleriyle birlikte sunulur. EXE/üretim sürümü değildir.

- Detaylı Raporlar → Rapor Merkezi → Yeni PDF Şablonları (Pilot) → **Bütünleşik Öğrenci 360**.
- Var olan 'Haftalık çalışma planı' bölümü artık öğrencinin **sayısal ID'siyle eşleştirilmiş** kayıtlı V2 profilini *salt okunur* özetler. Çalışma aralığı bulunan gün sayısı (7 gün), günlük limit ve etkin etüt oturumu süresi görüntülenir.
- 'Onaylı haftalık plan özeti' bölümünde yine öğrenci ID'sine bağlı olarak kayıt tarihi, planlanan çalışma birimi, yerleştirilen/yerleşmeyen dakika görüntülenir. 7 günden eski kayıtlar açıkça eski gösterilir.
- Eşleşme yoksa **kayıt yok**, geçersiz/başka öğrenciye aitse **doğrulanamadı** yazılır; varsayılan veya isim benzerliğine göre profil seçilmez. Başka öğrenciye özgü plan içeriği rapora taşınmaz.
- Şablon birden fazla öğrenciye atanmışsa **paylaşılan şablon** olarak gösterilir; kişiye özel olduğuna hükmedilmez.
- Öneri/önizleme metni ve PDF kaynak/kapsam açıklamaları da güncellenir. **Mevcut PDF oluşturma, hızlı çıktı, haftalık plan oluşturma/önizleme, ödev kayıt ve kontrol işlemlerine dokunulmadı.**

## Kaynaklar

- `services/plan_profile_store.py`: `load_assignments()` ve `load_profiles()` **mevcut okuma API'leri**; değişiklik yapılmadı.
- `services/planning_constraints.py`: `availability_for_week()` **mevcut takvim kuralı doğrulaması**; değişiklik yapılmadı.
- `services/plan_replanner.py`: `load_approved(student_id)` **öğrenci ID anahtarlı** onaylı taslak okuma API'si; değişiklik yapılmadı.
- `services/report_planner_bridge_v3585.py`: **yeni** isteğe bağlı, salt okunur entegrasyon katmanı.
- `services/integrated_report_v3584.py`: rapordaki iki ilgili kaynağı bu yeni katmana bağlar.

## Kanıt ve sınırlar

1. Rutin kaydı, gerçek çalışmanın veya okulda katılımın kanıtı değildir. Aday çalışma saatleri **gerçekleşmiş çalışma saatleri** olarak yorumlanmaz.
2. Onaylı taslak, verildiği gün için oluşturulmuş ödev programının kayıtlı özetidir; bugünkü ödevlerin aynı olduğunu veya öğrenci tarafından uygulandığını kanıtlamaz. Bu aşamada haftalık PDF dosyalarının kendisi otomatik içe aktarılmaz.
3. Kaynaklar yerel dosyalardır; gerçek çoklu kullanıcı/kurum rol yetkisi, dosya okuma izinleri ve farklı bilgisayarlar arası senkronizasyon bu yama ile oluşturulmaz. Raporu paylaşacak kişi izinleri doğrulamalıdır.
4. Hesaplamalar öğrenci ID'si dışında ad/soyad eşleştirmesi kullanmaz. Sahiplik çakışması varsa bilgi gösterilmez. Ortak kullanımdaki şablonlar özel öğrenci planı olarak etiketlenmez.
5. Pano/grafik/PDF görünümleri mevcut yaklaşımla korunur. Bu yama toplu sınıf PDF, sayfa düzeyinde gerçek GUI PDF önizlemesi veya otomatik WhatsApp gönderimi içermez.

## Kurulum – yalnızca test kopyasına

1. Orijinal V3.5.80 **tam kaynak** klasörünü, veritabanını ve mevcut plan profil dosyalarını yedekleyin.
2. V3.5.80 tam kaynaklarını ayrı bir TEST klasörüne açın.
3. Bu ZIP içindeki dosyaları klasör yapılarını koruyarak TEST klasörüne yerleştirin; **daha önceki V3.5.84 yamasını ayrıca kurmanız gerekmez**.
4. `python -m unittest tests.test_report_planner_bridge_v3585 tests.test_integrated_report_v3584 tests.test_professional_pdf_v3583 tests.test_report_center_v3581 tests.test_report_evidence_v3582 tests.test_v14_performance_evidence tests.test_v15_performance_coaching tests.test_v35_release_gate -q`
5. Windows ve macOS üzerinde gerçek PyQt6 arayüzünde öğrenci değiştirerek ve mevcut PDF ekranlarından eski-yeni çıktıları karşılaştırarak ayrıca test edin. Kurumsal rol/erişim testini tamamlamadan müşteri güncellemesi yapmayın.

## Test durumu

- 95 ilgili otomatik test (V3.5.81–V3.5.85 raporlama + performans okuyucuları + korunmuş kaynaklar) başarılı.
- Sentetik verilerle örnek PDF üretildi; 2 A4 sayfa, Türkçe karakterler ve metin sınırları denetlendi.
- `tests/v42_protected_hashes.json` içindeki 10 dosya, orijinal V3.5.80 ZIP ile SHA-256 seviyesinde birebir doğrulandı.
- Gerçek macOS/Windows PyQt6 UI, ağ/çok kullanıcılı senaryolar, Windows EXE/PyInstaller ve yazıcı testleri **yapılmadı**; canlı onay yok.

## Kalan planlı aşamalar

- **V3.5.86:** Yetki/filtre tasarımı doğrulandıktan sonra toplu, kontrollü bütünleşik PDF ve gerçek PDF sayfa önizlemesi.
- **V3.5.87:** Stabilizasyon, sürüm birleştirme, performans/EXE ve gerçek cihaz kabul testleri. Kabul testi sonuçlarına göre ek hata düzeltmesi gerekebilir; otomatik seri sürüm artışı hedef değil.
