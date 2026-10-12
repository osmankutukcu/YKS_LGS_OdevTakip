# V22 — Windows ve düşük çözünürlükte tek ekran kullanım kılavuzu

## Kaynak tabanı ve kurulum
- V22, V21 kümülatif kaynak ZIP'inden türetilmiştir. Çalışan v3.5.17 üzerine **doğrudan yazmayın**; önce kaynak farklarını kontrol edin.
- Uygulamayı kapatın, **kaynak kodunu ve SQLite/öğrenci profili verilerini ayrı ayrı yedekleyin**.
- Test amacıyla **V21 kaynak kodunun kopyasını** hazırlayın. Küçük V22 yamayı aynı kök dizine çıkarın; aynı adlı kaynak dosyalarını yalnızca test kopyasında değiştirin. Alternatif olarak veriler hariç V22 tam kaynak ZIP'ini ayrı klasöre çıkarın.
- Bu kaynak paketleri Windows .exe kurulum veya GitHub güncellemesi değildir; Windows sürümünün PyInstaller ile yeniden oluşturulması gerekir.
- Windows gereksinimleri `requirements_win.txt` dosyasındadır; Qt6, Windows DPI ölçeklendirmesini işletim sisteminden otomatik okur. Kullanıcı sistemdeki ölçeklendirme ayarını değiştirmek zorunda değildir.

## Dar ekrandaki işleyiş
1. Ana pencere daralınca sabit 240px sol modül menüsü yerini **☰ Menü / Modüller** açılır menüsüne bırakır. Menü, mevcut modül düğmelerinin **aynı tıklama davranışını** çağırır.
2. Ödev Takip Formu'nda sol ders tablosu ve sağ verilen ödevler alanı korunur. Dar ekranda **Öğrenci 360°** açıldığında yalnızca sağ verilen ödevler alanının yerini alır. **360° Gizle** ile verilen ödevler tekrar görünür. Hiçbir kayıt silinmez.
3. Üstteki öğrenci seçimi/Kaydet/Kontrol; alttaki Rapor/Sihirbaz/Denetim düğmeleri; ders gezinme çubuğu ve sağ taraftaki işlem satırları **yatay kaydırılabilir** hale geldi.
4. Ödev Kontrol Formu dahil `ui.responsive.apply_responsive` kullanan pencerelerin minimum boyutu, Windows görev çubuğu hariç ekran kullanılabilir alanına göre sınırlandırılır.
5. Öğrenci 360° hâlâ **salt okunur**; Kontrol işlemi önceki Ödev Kontrol Formu'nu açar. Yeni ödev kaydı veya yeni tikleme yolu yoktur.

## Windows kabul test matrisi — gerçek bilgisayarda yapılmalı
| Ekran | Ölçek | Kontrol |
|---|---|---|
| 1920×1080 | %100, %150 | Menünün ve 360° üçüncü sütunun geniş ekrandaki davranışı |
| 1366×768 | %100, %125, %150 | Dar görünüm; üst/alt butonlara yatay kaydırarak erişim |
| 1280×720 | %100, %125 | Verilen ödevler ↔ Öğrenci 360° geçişi |
| 1024×768 | %100, %125 | Ana form ve Ödev Kontrol penceresi; kenar düğmelerinin erişilebilirliği |
| Çift monitör | Farklı ölçekler | Ekran değiştirince maksimum pencere/ölçek ve öğrenci özeti |

Her testte **öğrenci değiştir**, **manuel tik → Kaydet**, **Kontrol → tamamlandı/geri al**, **Verilen Ödevler**, **Öğrenci 360° aç/kapat**, **Planlayıcı**, **Sihirbaz**, **PDF/Excel** yollarını test edin. Öğrencinin değişiminde önceki öğrencinin özeti görünmemelidir. Gerçek öğrenci kayıtlarında değil, test verilerinde deneyin.

## Test komutları
Windows terminalinde proje dizininden:

```bat
python tools\v22_windows_screen_diagnostics.py
python -m pytest -q tests\test_v22_windows_compact_layout.py tests\test_v22_qt_layout_optional.py tests\test_v21_student_workspace.py
```

`v22_windows_screen_diagnostics.py` salt okunur şekilde monitörlerin Qt mantıksal çözünürlüğünü/DPI oranını gösterir, kişisel veri açmaz.

## Kalan sınırlamalar
- Bu çalışma ortamında PyQt6 yoktur; gerçek Windows yerleşimi ve 125–150% ölçeklenme **bağımsız görsel testten geçmedi**.
- Çok küçük monitörlerde veya büyük erişilebilirlik yazı tipinde bazı tablo sütunları yatay kaydırma gerektirir. Küçük font zorlanmadı.
- Tüm üçüncü taraf pencereler (farklı yayınevi raporları, eski diyaloglar) V22'de tek tek yeniden tasarlanmadı; güvenli hedefli testler ve sonraki kararlı sürüm testleri gerekir.
- Kaynak dosyaları kullanıcı verilerini içermez; orijinal SQLite, ödev profilleri ve kurulum lisans dosyaları ayrı korunmalıdır.
