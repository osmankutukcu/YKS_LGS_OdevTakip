# KoçPilot 360 – V3.5.89 Açıklanabilir Raporlama Pilotu

## Hedef ve kapsam

Girdi: Kullanıcının gönderdiği `KocPilot360_V3588_TekKok_Final_TamKaynak(1).zip` ve dört rapor ekranı görüntüsü. Bu yama mevcut kayıt, ödev verme ve kontrol, PDF ve Excel işlemlerini koruyup açıklamaların güvenilirliğini artırır. Ana sayfa yerleşimi ve mevcut Rapor Merkezi altı seçenek yapısı korunur.

## Kaynak denetiminde görülen dört mesele

1. **Sınıf/kurum:** `ui/report_dashboard.py` ana öğrenci tablosu `ogrenci`/`odev_kume`/`odev` üzerinden tüm kayıtları değerlendirirken ders grafiği `ogrenci_perf_hafta_ders` tablosundaki *tüm kayıtlı haftaları* özetliyordu. Bu, yanlışlıkla tek hafta veya seçilen sınıfın istatistiği gibi yorumlanabilir. Sorguyu değiştirmeden kapsamı açık yazan başlık/uyarı eklendi.
2. **Öğrenci detayı:** `ui/student_detail.py` tamamlanmamış satırları iki ayrı kaynaktan (`odev`, `odev_satir`) birleştirerek sayıyor. Buradaki sayı **gecikmiş ödev sayısı değildir**; iki kaynakta potansiyel örtüşme vardır. KPI araç ipucuna bu sınır açıkça yazıldı. Günlük grafikteki sabit %80 çizgisi artık kişisel hedef gibi sunulmuyor; **örnek referans** olarak adlandırıldı.
3. **Gelişmiş grafikler:** Önceki kural tabanlı açıklamalar 'çok süre harcandı → zorlandı' veya 'çok tamamlanan görev → lider' gibi bilimsel olarak yeterince desteklenmeyen çıkarımlar yapabiliyordu. Ayrı `services/report_interpretation_v3589.py` ile ölçüme sadık, örneklem/kaynak sınırlarını açık söyleyen, HTML güvenli çıktı oluşturuldu. `ui/reports.py` korumalıdır ve hiç değiştirilmedi. Bunun yerine yeni `ui/safe_reports_v3589.py` alt sınıfı yalnızca Rapor Merkezi üzerinden kullanılmaya başlandı.
4. **Performans paneli:** `ui/performans_paneli.py` başlığının altına veri türlerinin farkını açıklayan küçük, salt-sunum etiketi eklendi. Kayıt sorguları ve sekme/çıktı işlevleri değişmedi.

## Rapor Merkezi'ne eklenen iki güvenli araç

- **🔎 Veri Kontrolü:** `services/report_diagnostics_v3589.py` yalnızca SELECT kullanarak `odev` ve `odev_satir` tablolarının kayıt sayısını, şema varlığını ve öğrenci/küme/ders anahtarındaki olası örtüşme sayısını gösterir. Bir örtüşme aynı görevin iki kez sayıldığını **kanıtlamaz**. Öğrenci isimleri/kimlikleri ekrandaki istatistiklere aktarılmaz; veri otomatik birleştirilmez veya silinmez.
- **🌐 Resmî Kaynaklar:** Kullanıcı isterse ÖSYM resmî sınav takvimini veya MEB öğretim programları sayfasını harici tarayıcıda açar. **Bu aşamada internetten otomatik öğrenci analizi yapılmaz, hiçbir öğrenci verisi buluta yüklenmez.** Gerçek çevrimiçi kaynakların içeriği kullanıcı tarafında görülmelidir; uygulamada kaynak doğrulama/önbellekleme ve kazanım eşleştirme ayrı bir onaylı tasarım konusudur.

## Kullanıcıya kazanç

- Ödev tamamlama ile akademik başarı birbirine karıştırılmaz.
- Haftalık karşılaştırma ve görev sayısı farklı öğrencilere ilişkin yorumlar temkinli üretilir.
- Eksik veri düşük performans diye sunulmaz.
- Sınıf/ders grafiklerinin farklı kaynak ve dönem ölçtüğü açıklanır.
- Yeni yorumların öğrenci adlarındaki `<` veya `&` gibi karakterleri HTML koduna dönüştürerek yanlış biçimde işlememesine dikkat edildi.
- Kararsız ya da negatif grafik sayıları güçlü bir çıkarımın parçası yapılmaz.

## Koruma sınırları

`main_window.py`, `db.py`, `ui/homework_form.py`, `ui/odev_kontrol.py`, `ui/reports.py` ve koruma manifestindeki 10 temel dosya **byte-byte aynı** tutuldu. Diğer değişen dosyalar yalnızca `ui/report_center_v3581.py`, `ui/student_detail.py`, `ui/report_dashboard.py`, `ui/performans_paneli.py`. Eklenen üç kaynak modülü ve bir test dosyası ayrı tutuldu.

## Test doğrulaması

- `PYTHONPATH=<proje_kökü> pytest -q tests/test_report_interpretation_v3589.py tests/test_report_evidence_v3582.py tests/test_report_center_v3581.py tests/test_report_planner_bridge_v3585.py tests/test_integrated_report_v3584.py tests/test_bulk_report_v3586.py tests/test_v14_performance_evidence.py tests/test_v15_performance_coaching.py tests/test_coaching_integration_guard_v3560.py tests/test_coaching_evidence_hub_v3561.py`
- **104 test, 36 ek alt kontrol başarılı.**
- Korunan 10 dosyanın SHA-256 eşleşmesi doğrulandı.
- Sentetik SQLite kayıtları üzerinde salt-okunur denetim test edildi.
- **PyQt6 bu çalışma ortamında yüklü olmadığı için gerçek GUI/Windows EXE/macOS arayüz ve yazıcı kabulü doğrulanmadı.**

## Bildiğimiz açık konular – canlı öncesi mutlaka kontrol

1. `odev` ile `odev_satir` arasında gerçek çift sayım var mı? Aynı öğrenci/küme/ders anahtarı tek başına kesin kanıt değildir. Veri kümesi özelinde durum/tarih/satır kimliği eşleştirme gerekir.
2. Sınıf grafiklerinde tüm zamanlar yerine kullanıcı tarafından seçilen dönem filtresi isteniyor mu? Bu yeni bir semantik değişikliktir; öğretmen kabul testi olmadan değiştirilmedi.
3. Tüm ana rapor ve Excel/PDF üretimleri gerçek Windows/macOS ortamında kontrol edilmeli.
4. Yeni `AciklanabilirRaporlarFormu` sürümü Rapor Merkezi ve Sınıf/Kurum ekranının detaylı rapor yolunda çalışır. Korumalı eski modüle doğrudan giden diğer gizli yollar orijinal davranışa devam eder.
5. Gerçek çevrimiçi analiz için kaynak tarihleri, sürüm, izinli alan adları, güncelleme sıklığı, bağlantı hatasında çevrimdışı çalışma, kurum politikası ve kişisel veri aktarım izni ayrı tasarlanmalıdır. Bu pilotta **otomatik web analiz motoru yoktur**.

## Güvenli kurulum

1. Mevcut çalışan sürümün ve kullanıcı veritabanının yedeğini alın; test ortamı kullanın.
2. Temiz tam kaynak ZIP'ini ayrı klasöre çıkarın; eski klasörün üzerine doğrudan kopyalamayın.
3. Bağımlılıkları `requirements` yönergelerine uygun olarak test makinesinde yükleyin; PyQt6 ve PDF araçlarını doğrulayın.
4. Dört rapor yolunu, veri kontrolünü, resmî kaynak bağlantılarını, kaydetme/yazdırma/Excel'i sınayın.
5. Ödev Takip ve Ödev Kontrol'ün önceki sürümle aynı tıklama/kaydetme/geri alma davranışını doğrulayın.
6. Kabul tamamlanmadan GitHub üzerinden müşterilere otomatik yayın yapmayın.

**Sürüm niteliği:** Kaynak kodu pilotu; canlı dağıtım onayı değildir.
