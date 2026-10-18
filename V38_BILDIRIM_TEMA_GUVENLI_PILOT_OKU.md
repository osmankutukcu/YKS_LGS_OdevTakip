# V38 – Bildirim ve Mesaj Pencereleri Tema Güvenliği

**Temel:** V37 güvenli pilot tam proje. Bu paket V36 ve V37 tema iyileştirmelerini içerir.

## Ne değişti?

- `QMessageBox` (bilgi/uyarı/hata/onay), `QInputDialog` ve `QProgressDialog` için tema uyumlu, normal/hover/varsayılan/pasif düğme renkleri tanımlandı.
- `ui/theme_popup_runtime_v38.py` uygulama düzeyinde tek bir olay dinleyicisi kurar. Diyalog gösterildiğinde renkleri ayarlar, açık standart diyalogları tema değişiminde yeniler. Hiçbir butonun işlevini veya cevap dönüş değerini değiştirmez.
- `QMessageBox` zemininin kart renginden, metninin yanlışlıkla ana sayfa yazı renginden türetilmesi düzeltildi.
- Temel toast, motivasyon bildirimi, kitap yöneticisi toast'u ve görünüm ayarları yedek toast'u için düşük kontrast düzeltmeleri eklendi. Özgün mesaj içerikleri, bildirim süreleri ve aksiyonlar korunur.
- `QA_V38/test_notification_theme_v38.py` Qt gerektirmeyen statik testler; `QA_V38/preview_notification_windows_v38.py` Windows/macOS için **örnek veri kullanan** görsel kontrol aracı.

## Test etmek için

1. **Yalnızca ayrı bir test klasörüne** çıkarın; mevcut kurulumun üzerine yazmayın.
2. Mac/Windows üzerinde PyQt6 kurulu proje ortamında `python QA_V38/preview_notification_windows_v38.py` komutunu çalıştırın. Bu test kullanıcı ayarlarını/veritabanını değiştirmez; temaları bellekte tutar.
3. `Cloud Light`, `Klasik Koyu`, `Fenerbahçe`, `Neon` temalarında bilgi, onay, metin girişi, ilerleme ve toast örneklerini açıp deneyin.
4. Modeless bilgi penceresi açıkken temayı değiştirin; mesaj ve düğmelerin arka planıyla yazısı uyumlu kalmalı.
5. Uygulamanın gerçek formlarında **örnek veriyle** onay/iptal düğmelerini test edin; özellikle silme, WhatsApp gönderme, veri aktarımı gibi eylemlerde yanlışlıkla onay vermeyin.

## Sınırlar

- Bu sürüm standart Qt bildirimleri ve dört ortak toast türünü güçlendirir. Her özel çizimli veya HTML renkli bildirim panelini kapsadığı ileri sürülmez.
- İşletim sisteminin **yerel** dosya ve renk seçicilerinin görünümü Mac/Windows tarafından yönetilebilir; bunları zorla Qt penceresine dönüştürmedik.
- PyQt6 mevcut olmayan kod analiz ortamında gerçek uygulama ekranları açılamadığı için **gerçek Windows/macOS görsel testi henüz tamamlanmadı**.
- Veritabanı, öğrenci kayıtları, lisans, gönderme akışı, planlama ve ödev iş kuralları değiştirilmedi; bu değişikliklerin regresyonsuz olduğunu kanıtlamak için gerçek cihazda pilot kabul testi gerekir.
