# KoçPilot 360 – V3.5.94 Kontrollü Koçluk ve Planlayıcı Geçişi (PİLOT)

## Değişikliğin amacı

V3.5.93'te Öğretmen Karar Paneli kanıt ve öneri gösteriyordu fakat öğretmen, uygulama için farklı menülerde yeniden öğrenci arıyordu. Bu sürümde **yalnızca öğretmenin açıkça onayladığı** iki geçiş eklendi. Eski planlayıcı, koçluk ekranları ve ödev motorları yeniden yazılmadı.

## Kullanıcı akışı

1. **Rapor Merkezi → Öğretmen Karar Paneli** bölümünü açın.
2. Öğrenci ve son 30/90/180 günlük deneme dönemini seçip verileri inceleyin.
3. **Koçluk Planı’na Git** veya **Haftalık Planlayıcı’ya Git** düğmesini seçin.
4. Onay penceresinde öğrenci ID ve hedef ekranı kontrol edin, **Evet** deyin.
5. Koçluk için **mevcut Koçluk Planı** ekranı aynı öğrenci ID'siyle açılır. Haftalık planlama için **mevcut Ödev Takip formu** aynı öğrenci ID'siyle açılır; bundan sonra öğretmen eski Haftalık Planlayıcı düğmesine kendisi basar.

**Bu sürüm önerileri ödev listesine aktarmıyor, otomatik ödev oluşturmuyor, takvim/öğrenci hedefi değiştirmiyor, veliye mesaj göndermiyor.** Mevcut ekranlardaki öğretmen işlemleri eskisi gibi çalışır.

## Teknik yöntem ve korumalar

| Problem | Çözüm | Mevcut sistem üzerindeki etki |
|---|---|---|
| Yanlış öğrenciye geçme | Sabit sayısal öğrenci kimliği ve aktif öğrenci kontrolü | Kayıtlar değiştirilmez |
| Panel açıkken başka öğrenci seçme | Eski analiz ve geçiş yetkisi temizlenir | Yanlış öneri aktarılmaz |
| Önceki onayın daha sonra kullanılması | 120 saniyelik geçiş isteği, hedef ekran açılmadan tekrar kontrol | Güncel olmayan seçim reddedilir |
| Modal pencerelerin üst üste kalması | Önce karar paneli ve rapor merkezi kapatılır, sonra mevcut form açılır | Eski gezinme akışları korunur |
| Koçluk formunda varsayılan ilk öğrencinin açılması | Mevcut `CoachingManager` alt sınıfı aynı ID'yi listede doğrulayarak seçer | Orijinal koçluk formu değişmez |
| Ödev formunda yanlış varsayılan öğrenci | Mevcut `OdevTakipFormu` öğrenci ID'si kurucuda verilerek açılır; seçili kimlik yeniden kontrol edilir | Orijinal Ödev Takip formu değişmez |
| Sınırlı ekran genişliği | İki onaylı geçiş düğmesi ayrı satırda | Mevcut panel kartları korunur |

### Eklenen dosyalar

- `services/report_navigation_v3594.py`: saf salt-okunur öğrenci/niyet doğrulama hizmeti.
- `ui/report_navigation_bridge_v3594.py`: onaylı geçişleri **mevcut ekranlarla** ilişkilendiren yardımcı katman.
- `tests/test_report_navigation_v3594.py`: geçersiz/kapalı/farklı öğrenci, niyet süresi, yanlış form seçimi, değişmez çekirdek testleri.

### Değiştirilen entegrasyon dosyaları

- `ui/teacher_decision_dialog_v3593.py`: iki açık onaylı geçiş düğmesi.
- `ui/report_center_v3581.py`: onaylı geçişi geri iletme.
- `app.py`: her iki modal kapandıktan sonra yönlendirmeyi gerçekleştirme.
- `version.py`, `version.json`, `setup.iss`, `README.md`, `.github/workflows/build_installer.yml`: pilot sürüm ve test kapısı.

**Değişmeyenler:** `main_window.py`, `db.py`, `ui/homework_form.py`, `ui/odev_kontrol.py`, Koçluk Planı ve mevcut Haftalık Planlayıcı kodları; rapor veri hesaplayıcıları, PDF şablonları ve mevcut altı rapor rotası. Projedeki 10 korumalı kaynağın SHA-256 değerleri kontrol edilir.

## Test ve yayın durumu

- Sentetik SQLite verileriyle salt-okunur geçiş doğrulaması, öğrenci izolasyonu, yanlış ekranın engellenmesi, eski rapor regresyonları ve 10 korumalı dosya hash kontrolü çalıştırılmıştır.
- PyQt6 bu çalışma ortamında bulunmadığından **gerçek Qt arayüzü testleri burada çalıştırılmadı**; Windows CI'da PyQt6 kurulduktan sonra zorunlu test aşamasına eklendi.
- PDF regresyonu için çalışma ortamında geçici DejaVu font bağlantıları kullanıldı; **font dosyaları paketlere dahil edilmedi**.
- Windows EXE / macOS uygulama / canlı GitHub güncelleme kabulü yapılmadı. **Pilot test tamamlanmadan müşterilere gönderilmemelidir.**

## Test klasöründe kurulum

- **Tam kaynak:** V3.5.94 ZIP'i yeni, boş bir test klasörüne açın; eski yerel öğrenci veritabanını bu paketin içine kopyalamayın. V3.5.93'ün tüm kaynakları dahildir.
- **Küçük yama:** Yalnızca doğrulanmış V3.5.93 tam kaynak köküne, yedek aldıktan sonra uygulayın.
- PDF yazı tipleri (lisans ve dağıtım koşullarına uygun olanlar) mevcut derleme ortamında ayrıca sağlanmalıdır.
