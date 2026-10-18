# V43 – Tema Sistemi Son Bütünlük Denetimi

**Durum:** Güvenli pilot; gerçek Windows/macOS GUI kabul testi yapılmadan kararlı/üretim sürümü olarak onaylanmaz.

## Yapılanlar

- V36–V42 arasındaki 7 bağımsız tema test grubu yeniden çalıştırılır.
- V43 bütünleşik tema geçişi/renk testi eklenmiştir: 33 hazır temanın ileri ve geri geçişleri, tablolar, bildirimler, giriş alanları, menüler ve kaydırma çubuğu seçicileri denetlenir.
- AST sözdizimi denetimi tüm Python kaynaklarına uygulanır.
- V42'ye ait 66 veri/config/manifest dosyasının SHA-256 özetleriyle değişmediği kontrol edilir; öğrenci/ödev kayıt dosyalarına yazılmaz.
- Projenin orijinal iki DejaVu fontu **tam pakete** dahildir. Orijinal ZIP ile SHA-256 eşleşmesi doğrulanmıştır.
- Kalıntı risk kaynaklarını sıralayan **salt-okunur** `scan_local_color_risks.py` eklenmiştir. Olası stil riskleri kesin hata olarak değerlendirilemez.
- PyQt6 olan gerçek Windows/macOS ortamında **yalnızca uydurma örnek verilerle** 33 temayı gösterebilen `gui_theme_smoke_v43.py` eklendi. Önceki sürümlerden hiçbir gerçek öğrenci bilgisi kullanılmaz.

## Otomatik kod denetimi

Proje kökünde:

```bash
python QA_V43/run_release_checks.py
python QA_V43/scan_local_color_risks.py
```

İkinci komut Qt veya öğrenci bilgisi gerektirmez. Bu işlemler programın veritabanını açmaz.

## İsteğe bağlı gerçek PyQt6 önizleme

PyQt6 kurulu bir Windows/Mac ortamında:

```bash
python QA_V43/gui_theme_smoke_v43.py
```

Dört örnek ekran görüntüsü ve JSON sonuçları `QA_V43/local_gui_preview/` içine yazılır. 33 tema için tüm görüntüleri almak isterseniz `--all-screenshots` parametresi ekleyin. Bu test, gerçek uygulamanın bütün modüllerini açmaz; **gerçek form testleri şarttır**.

## Gerçek program için minimum kabul matrisi

Her kategori **Cloud Light, Dracula, Fenerbahçe, Cyberpunk** ve en az bir kişisel tema ile açıkken denenmeli. Bir ekranı açık tutup tema değiştirmek, pencereyi kapatıp açmaktan farklı bir testtir.

| Kategori | Denetlenecek durumlar |
|---|---|
| Ana pencere ve sol menü | Arka plan, yazı, etkin/pasif düğmeler, odak |
| Ödev Takip Formu | Başlık, satırlar, checkbox, seçili hücre, hover, sağ tık |
| Koçluk/Öğrenci 360 | Kart, açılır bilgi, özel durum renkleri, rapor |
| Takvim/Planlayıcı | Saat çizelgesi, okul/kurs şeritleri, tarih seçici |
| Deneme/Sınav/Performans | Tablo hücresi, yüzde ve trend, grafik/legend |
| Akıllı Sihirbaz | Metin kutusu, sekme, HTML belge, iç içe kaydırma |
| Bildirimler ve diyaloglar | Bilgi/hata/uyarı, Evet-Hayır, Tamam-İptal; tuş yanıtı |
| Listeler/ComboBox/Menu | Normal, seçili, hover, disabled, popup listesi |
| Kaydırma çubukları | Dikey/yatay, ince/kalın, hover, sürükle, boş alan |
| Güncelleme/Kılavuz | İlerleme, iptal, sekmeler, HTML belge |
| Farklı görünüm ölçekleri | %100, %125, %150; Windows/macOS; ufak ekran |
| Yeniden başlatma | Kaydedilen tema geri gelmeli; modüller aynı açılmalı |

**Kabul engeli:** Siyah-siyah/beyaz-beyaz yazı, kaybolan seçim, tıklanamayan onay düğmesi, yanlış checkbox işleyişi, veri/senkron kaybı, çökme veya hedef cihazda yanlış DPI. Bunlardan biri oluşursa V43 kararlı sürüm olarak işaretlenmez.

Testlerde yalnızca **uydurma öğrenci** oluşturun. Canlı kurum verilerini değiştirmeyin. Ana uygulamadaki salt-okunur renk denetimi istenirse `YKS_THEME_AUDIT=1` ile açılabilir; rapor öğrenci adını veya metin kutusu içeriğini kaydetmez. Bu denetim QPalette üzerinden yaklaşık kontrast ölçer ve özel çizilen hücrelerin gerçek görüntüsünü tam yakalayamaz.

## Önemli sınırlamalar

Bu aşamada PyQt6 mevcut olmayan hazırlama ortamında gerçek Qt pencereleri açılmamış, Windows EXE ve macOS .app paketi üretilmemiştir. İş kurallarını korumak amacıyla **mevcut uygulama kaynak dosyaları V42 ile aynıdır**; V43 yeni bağımsız QA araçları ve teslim bütünlüğüdür.

**Veri gizliliği:** Tam kaynak ZIP, önceki tam proje ZIP'inin içindeki veritabanı/yedek dosyalarını değişmeden taşıyabilir. Bu arşivi herkese açık GitHub deposuna doğrudan yüklemeyin; dağıtılacak kod paketinde gerçek kullanıcı verileri ayrıca ayrıştırılmalıdır.
