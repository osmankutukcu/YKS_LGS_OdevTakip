# V37 tema / kontrast kalite kontrolü

Bu kontrol yalnızca *görünüm* üzerinde çalışır. Öğrenci, ödev, lisans, veritabanı, senkronizasyon ve WhatsApp kayıtlarını değiştirmez.

## 1. Otomatik kod kontrolleri

Proje ana dizininden:

```bash
python QA_V36/run_theme_safety.py
python QA_V37/test_v37_semantic.py
python QA_V37/scan_theme_qss.py
```

`QA_V37/static_report.json` stil bildirimlerini, sabit arka plan–metin eşleşmelerini ve inceleme gerektiren kalan durumları içerir. **Buradaki sayılar ekranda görünme garantisi değildir.** Dinamik `setStyleSheet`, öğeye sonradan atanan `QBrush`, gradyanlar, opaklık, ikonlar ve özelleştirilmiş paintEvent burada tam çözümlenmez.

## 2. Gerçek cihazda görsel denetimi etkinleştirme

Windows PowerShell:

```powershell
$env:YKS_THEME_AUDIT = "1"
python app.py
```

macOS Terminal:

```bash
YKS_THEME_AUDIT=1 python3 app.py
```

Uygulamanın bütün formlarını açarak sırayla iki açık (`Cloud Light`, `Catppuccin Latte`), iki koyu (`Klasik Koyu`, `Nord`) ve zıt spor/özel (`Fenerbahçe`, `Neon`) temada kontrol et. Panel, diyalog, liste ve tabloda gez; açılır menü ve seçili satır durumlarını da test et.

`QA_V37/theme_runtime_findings.jsonl` dosyası uygulamanın çalıştığı dizine yazılır. İçerik, yalnızca pencere türleri, widget türleri, renklere ilişkin sayısal bulgular ve örneklenen tablo satır/sütun indekslerinden oluşur. **Öğrenci adları, telefonlar, metin kutusu veya tablo metinleri kaydedilmez.** Bu dosya görüntü sorununun kesin kanıtı değildir; QSS ve özel boyamalarda Qt paleti gerçek boyamadan farklı olabilir.

Veri yükü: tablo başına en fazla 4.000 hücre örneği; rapor başına en fazla 500 bulgu. Bu QA modu **varsayılan olarak kapalıdır**. Otomatik tarama yeni QDialog/QMainWindow görüntülendiğinde ve tema değiştirildiğinde yapılır.

## 3. Kabul için gerekli manuel testler

- Ana ekran: gün, öğrenci sayısı, ödev durumları, trend ve bildirim panelleri
- Ödev Takip Formu: bütün ders sekmeleri, konu/kitap, atanmış ödev tablosu, seçili satır ve checkbox
- Koçluk, öğrenci 360, öğrenci kartı, akıllı sihirbaz, öneriler
- Sınav, deneme, analiz, rapor, grafik ve PDF önizleme
- Takvim, haftalık programlayıcı, randevu, Pomodoro
- WhatsApp toplu mesaj, hızlı gönder, günlükler ve anketler
- Ayarlar, temalar, kullanıcı, lisans, yedekleme, yardım
- Hover, focus, pressed, checked, unchecked, disabled, selected, popup
- Her tema için 100%, 125%, 150% ölçek ve uygulamayı kapatıp yeniden açma
- Veri değiştiren işlemler yalnızca bir *test veritabanı* kopyasıyla denenmelidir.

## 4. Sınırlama

Geliştirme ortamında PyQt6 kurulamadığı için bu sürümün gerçek QWidget ekran görüntüleri alınamadı. Otomatik analiz, sabit tanımlardaki birçok kontrast kusurunu azaltır ancak **bütün ekranlarda yüzde yüz tema uyumu henüz doğrulanmamıştır**. Özellikle dinamik hücre boyamaları ve açık zeminli yerel QFrame kartları cihaz testinde önceliklidir.
