# KoçPilot 360 — V3.5.87 Kaynak Stabilizasyon ve Kabul Raporu

**Durum:** Birleşik kaynak yaması / kontrollü test; **müşteriye dağıtıma hazır değil**.
**Temel paket:** `YKS_LGS_HomeworkManager_v3.5.80_KocPilot360_Son_Surum.zip`.
**Kapsam:** Önceki V3.5.81–86 güncellemelerinin birleştirilmesi, V3.5.87'de toplu PDF'nin tamamlanmadan hedef yolda görünmesini engelleyen güvenli yayımlama ve kaynak bütünlük doğrulaması.

## V3.5.87 somut değişiklikleri

1. Toplu PDF kayıt işlemi, hedef klasörde rastgele adlandırılmış özel geçici dosyaya tamamı yazılıp senkronize edildikten sonra `os.link` ile **mevcut dosyayı değiştirmeden** yayımlanır. Geçici dosya her durumda temizlenir. Hedef diskte hard-link/atomik yayımlama desteklenmiyorsa işlem **hata vererek durur**, eski dosyayı değiştirmez ve eksik PDF bırakmaz. NTFS/APFS ve ağ/paylaşımlı disklerin uyumluluğu gerçek cihazda ayrıca denenmelidir.
2. Eksik disk alanı/kopyalama hatası, dosyanın kayıt sırasında başka işlemce oluşturulması, atomik bağlantının desteklenmemesi ve PDF'nin tam olduğunun yayımlanmadan önce doğrulanması için **5 yeni regresyon testi**.
3. Orijinal V3.5.80 kaynak ZIP'i ve birleşik V3.5.87 yamayı **çevrimdışı** karşılaştıran `tools/v3587_release_gate.py`; dosya özeti, yasaklı veri/gizli anahtar dosyaları ve 10 korumalı kaynağı kontrol eder.

## Otomatik testlerin kesin durumu

- V3.5.81–V3.5.87 odaklı **105 test başarılı**; gerçek öğrenciler kullanılmadı. Bu sayı daha önceki 100 teste eklenen 5 testtir.
- Ek olarak mevcut Ödev Takip / çekirdek / Öğrenci 360 / güncelleme koduyla ilgili seçili **89 eski test başarılı**.
- Derleme/sözdizimi kontrolü: kaynak yamasındaki bütün `.py` dosyaları Python derleyicisinden geçirildi.
- 10 korumalı dosyanın V3.5.80 temeliyle SHA-256 eşleşmesi doğrulandı: `db.py`, `main_window.py`, `ui/book_dialog.py`, `ui/coaching_manager.py`, `ui/curriculum_page.py`, `ui/homework_form.py`, `ui/modern_settings.py`, `ui/odev_kontrol.py`, `ui/reports.py`, `ui/topic_editor.py`.
- Geniş test taramasında **3 test PyQt6 eksikliği nedeniyle başlatılamadı** (`test_routine_homework`, `test_smart_calendar_executive`, `test_weekly_routine_habits_v35`). Bu testler başarısızlık değil, ortam yetersizliğidir; çalıştırılmış kabul edilmemelidir.
- Eski `tests.test_v3554_stabilization` içindeki bir kontrol **altı farklı geçersiz öğrenci ID'sinde başarısız**: test PDF'den çıkarılan metinde `güvenlik için kapatıldı` ifadesini bitişik bekliyor; mevcut PDF renderer'ı `güvenlik\niçin kapatıldı.` olarak iki satır döndürüyor. Aynı testte yetkisiz `wa.me`/`tel:` URI bağlantısı bulunmadığı denetimi geçiyor. Test ve `services/smart_mobile_pdf_v3545.py` kaynakları orijinal V3.5.80 ile **birebir eşleşiyor**. Bu nedenle yeni raporlamadan kaynaklandığına dair delil yok; yine de eski test yeşil değildir ve metin çıkarımı regresyonu ayrıca ele alınmalıdır.

## Manuel kabul testleri (henüz yapılmadı)

1. **Windows 10/11 ve macOS** üzerinde gerçek PyQt6 GUI: ana sayfa açılıyor; **Detaylı Raporlar → Rapor Merkezi → PDF Atölyesi / Toplu PDF** yolları bulunuyor. Ekranlar farklı pencere boyutlarında okunuyor, tema ve kaydırma çalışıyor.
2. Öğrenci/grup seçimi, filtre değişimi ve açık seçim onayı: hiçbir gizli/pasif/başka öğrencinin kaydı eklenmiyor. Farklı sınıflar ve aynı ad-soyad için ID doğrulanıyor.
3. Tekli/60 öğrenci PDF önizleme, sayfa geçişi, yakınlaştırma, çıktı kaydı, yazıcı ve açılır dosya yolu testleri; iptal/hata halinde eksik dosya kalmıyor. Özellikle **NTFS/APFS, harici sürücü ve ağ klasörlerinde** atomic dosya yayımlama ve izinler test edilmeli.
4. **Ödev Takip / Ödev Kontrol** tıkla, kaydet, geri al, renklendir, kilitle, filtrele; beklenen sonuçlar V3.5.80 ile karşılaştırılmalı. Haftalık Planlayıcı çıktısı aynı kalmalı.
5. Programı öğrenci verilerinin **yedeklenmiş, gerçek kayıtlardan ayrılmış test kopyasında** çalıştırın; yetkisi olmayan öğretmenin başka sınıf/kurum kayıtlarını raporlayamadığı doğrulanmadan kurumlar arası canlı paylaşım açılmamalıdır.
6. PyInstaller/EXE paketinde `reportlab`, `fitz`, `PyQt6` ve fontların bulunması, otomatik güncelleme sonrası açılış, yeni rapor ekranları ve önceki raporların davranışları doğrulanmalıdır.
7. İstem dışı WhatsApp/e-posta gönderimi yapılmadığı, PDF dosyalarının uygulama hatasında **kullanıcı dışına sızmadığı** kontrol edilmeli.

## Kurulum/geriye dönüş

- Önce çalışır V3.5.80'in **kaynak ve veritabanı yedeğini** alın.
- Tam V3.5.80 kaynak ZIP'ini **ayrı bir TEST klasörüne** açın. V3.5.87 birleşik yamayı **dizin yapısını koruyarak** üzerine kopyalayın. V3.5.81–86'nın ayrıca kurulması gerekmez.
- Paketi önce doğrulayın: `python tools/v3587_release_gate.py "YKS_LGS_HomeworkManager_v3.5.80_KocPilot360_Son_Surum.zip" "KocPilot360_V3587_Son_Stabilizasyon_BIRLESIK_PILOT.zip"`.
- Test: `python -m unittest tests.test_v3587_stabilization tests.test_bulk_report_v3586 tests.test_report_planner_bridge_v3585 tests.test_integrated_report_v3584 tests.test_professional_pdf_v3583 tests.test_report_center_v3581 tests.test_report_evidence_v3582 tests.test_v14_performance_evidence tests.test_v15_performance_coaching tests.test_v35_release_gate -q`.
- Sorun varsa test kopyasını bırakıp **orijinal V3.5.80** ile devam edin; gerçek veri klasörü/kurulu EXE dosyalarını değiştirmeyin.

**Not:** Otomatik test, gerçek Windows/macOS GUI ya da cihaz kurulumunu %100 garanti etmez. Korunan kaynak dosyalarının eşitliği, programın davranışının bütünüyle aynı olduğunun kanıtı değildir. Bu aşamayla planlı kaynak geliştirmesi tamamlanmıştır; canlı kullanım onayı, elle kabul testleri ve olası düzeltmelere bağlıdır.
