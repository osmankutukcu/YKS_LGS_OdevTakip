# V22 – Windows / Düşük Çözünürlük / Öğrenci 360° Teknik Rapor

**Tarih:** 12 Ekim 2026  
**Temel sürüm:** V21 tek ekran kümülatif kaynak (v3.5.16 kaynak zinciri).  
**Durum:** Kod ve otomatik regresyon testleri tamamlandı; Windows görsel kabul testleri bekleniyor.

## Sorun ve çözüm
- Sabit **240px sol menü** içerik genişliğini azaltıyordu. V22 `ui/responsive_shell_v22.py` ile <1280 Qt mantıksal pikselde menüyü açılır menüye dönüştürüyor. Menü butonları **eski düğme sinyallerini** kullanıyor.
- Eski Ödev Takip Formu en az **600 + 360px** yatay alan istiyordu; V21 Öğrenci 360° 285px ekliyordu. V22 min genişlikleri 350 + 230px'e düşürüp tablo içinde kaydırmayı koruyor. <1440 Qt mantıksal pikselde Öğrenci 360° açıldığında sağ **Verilen Ödevler** alanının yerini alıyor; 360° kapatılınca eski liste geri geliyor. Geniş ekranda üç sütun mantığı korunuyor.
- Üst, alt, ders menüsü, sağ üst işlem ve sağ alt aksiyon satırları `ui/responsive_toolbar_v22.py` ile kaydırılabilir hale getirildi. Butonların mevcut `clicked` bağları korunuyor.
- `ui/responsive.py` sabit 960×600 minimum yerine **ekran kullanılabilir alanı** ile sınırlanmış minimum kullanıyor. Bu, `OdevKontrolDialog` gibi mevcut uyarlama kullanan pencereleri etkiler. Windows görev çubuğu alanı hesaba katılıyor.
- Windows Qt6 DPI mantıksal pikselleri esas alınır; işletim sistemi ölçeği, uygulama yazı boyutu ve font boyutları zorla değiştirilmez.

## Kaynak mimarisi
**Değiştirilen mevcut dosyalar (5):**
- `main_window.py`
- `ui/homework_form.py`
- `ui/homework_workspace_bridge_v21.py`
- `ui/responsive.py`
- `ui/student_workspace_panel_v21.py`

**Yeni dosyalar (8):**
- `V22_WINDOWS_KOMPAKT_KURULUM_VE_TEST.md`
- `services/responsive_v22.py`
- `tests/test_v22_qt_layout_optional.py`
- `tests/test_v22_windows_compact_layout.py`
- `tools/v22_windows_screen_diagnostics.py`
- `ui/responsive_homework_v22.py`
- `ui/responsive_shell_v22.py`
- `ui/responsive_toolbar_v22.py`


## Korunan işleyiş
`_kaydet_kume`, `_odev_kontrol`, `_open_weekly_plan_dialog` ve öğrenci seçimi/tik kayıt kodları içeriği değiştirilmedi. `HomeworkWorkspaceBridgeV21(self, mid_split, bottom)` çağrı biçimi korundu; adaptasyon içerde isteğe bağlı olarak eklendi. Öğrenci verileri ve veritabanları yazılmadı.

## Doğrulama
- V21 + V22 hedefli regresyon: **26 başarılı**.
- PyQt6 gerektiren yeni isteğe bağlı Qt görsel testleri: bu ortamda **1 modül atlandı** (PyQt6 bulunmuyor). Windows'ta ayrıca çalıştırılabilir.
- Geniş otomatik test: **657 passed, 44 subtests passed, 4 failed, 4 collection errors**. Başarısız üç GUI testi / dört modül yükleme hatası PyQt6 yokluğu, dördüncü başarısız test ise kaynak paketindeki `.github/workflows/build_installer.yml` eksikliğiyle ilişkili. Bu durumlar V22 düzeninin Windows'ta doğrulandığı anlamına gelmez.
- Değişen Python dosyalarının sözdizimi kontrolü ve ZIP arşiv `testzip` bütünlüğü başarılı. Gerçek Windows 100/125/150% DPI testleri bekliyor.

## Açık riskler ve gereklilikler
1. Qt ekran boyutu ve olay döngüsü testi Mac/Windows fiziksel cihazda çalıştırılmalı. Önce test öğrenci verileri kullanılmalı.
2. Eski v3.5.17 çalışan uygulamayla bu v3.5.16-temelli kaynak zincirinin farkları birleştirilmeden kurulum yapılmamalı.
3. Mevcut önceki 3 yetim `odev_satir.odev_id` veri tutarlılığı kaydına V22 dokunulmadı.
4. `.github/workflows/build_installer.yml` eksikliği ve Windows EXE imzalama/otomatik güncelleme işlemleri ayrıca kararlı sürüm kabulünde çözülmeli.
5. Görünüm daralınca gizlenen **Verilen Ödevler** widget'ı *yalnızca görünmez olur*; kayıttan silinmez.

### Yayına alma kararı
**V22 kaynak yaması hazır, Windows EXE sahada doğrulanmadan genel dağıtım önerilmez.** Kılavuz: `V22_WINDOWS_KOMPAKT_KURULUM_VE_TEST.md`.
