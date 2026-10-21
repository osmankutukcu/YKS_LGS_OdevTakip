# KoçPilot 360 v3.5.94 – Rapor Merkezi güvenli erişim düzeltmesi

**Kapsam:** Sürüm numarası değiştirilmeden yapılan küçük, geri alınabilir kullanılabilirlik ve dayanıklılık düzeltmesi. Bu pilot, Windows/macOS gerçek uygulama kabul testlerinin yerini almaz.

## Neden?

Sol menüdeki beş eski rapor butonunun gizlenmesi **bilinçli, doğru bir sadeleştirmedir**. Kullanıcı normal durumda yalnızca **Rapor Merkezi** aracılığıyla eski ekranlara erişir. Ancak yeni modülün açılışında oluşabilecek bir hata (örneğin eksik derleme bağımlılığı, dosya/arayüz yükleme hatası) kullanıcıların korunmuş rapor fonksiyonlarına erişimini güçleştirebilirdi. Bu, beklenen veya sürekli oluşan bir hata olduğu anlamına gelmez.

## Ne değişti?

1. `app.py`: Rapor Merkezi ana menüye başarıyla yerleştirildikten sonra eski beş düğme gizlenir. Normal durumda beş düğme geri gelmez. Hata sırasında **Tekrar Dene / Yedek Rapor Erişimi / Kapat** seçenekleri gösterilir.
2. `services/report_entry_guard_v3594.py` (yeni): Yalnızca ana penceredeki altı önceden mevcut rapor fonksiyonunu izinli liste üzerinden açabilir. Veritabanı, öğrenci kimliği, PDF hesaplaması veya ödev kayıtlarını değiştirmez. Yedek erişim sol menüye eklenen kalıcı bir düğme değildir.
3. `ui/report_center_v3581.py`: Rapor kartının açılışında istisna oluşursa geçici gizlenen Rapor Merkezi yeniden gösterilir. Mevcut yönlendirme isimleri ve normal akış korunur.
4. `.github/workflows/build_installer.yml`: Yeni güvenli erişim testi mevcut test iş akışına eklendi.
5. `tests/test_report_center_recovery_v3594.py` (yeni): Fonksiyon izin listesi, gizli menü düzeni, başarısız kurulumda eski girişlerin korunması için statik kontroller.

## Korunan işlevler

- Ödev Takip ve Ödev Kontrol: Tablo, hücre, tik, kaydet, geri alma, kilit, senkronizasyon kodları değiştirilmedi.
- Öğrenci 360, Adaptif Koçluk, Konu–Kazanım–Öğrenme, Koç'a Sor, Koç Asistanı: İlgili modüllerin kaynakları değiştirilmedi.
- Mevcut PDF/Excel rapor motorları, sınıf analizleri, öğrenci detayları, hedef analizi ve haftalık planlayıcı değişmedi.
- Kişisel öğrenci dosyası ve veritabanı bu kaynak pakete eklenmedi.

## Test / sınırlar

- Seçili 129 pytest testi geçti; iki gerçek Qt testi ortamda PyQt6 olmadığı için atlandı; 102 ek alt kontrol geçti.
- Korunan 10 kaynak, `tools/v3527_core_guard.py` ile başarıyla doğrulandı.
- Bu denetim **çalışan EXE veya gerçek Windows/macOS arayüzü testinin eşdeğeri değildir**.

## Gerçek cihazda kabul senaryoları

1. Normal açılış: Sol menüde yalnız Rapor Merkezi bulunmalı; eski beş bağımsız buton görünmemeli.
2. Merkezden mevcut raporların her birini açıp kapatın; rapor ekranı kapanınca merkez tekrar erişilebilir olmalı.
3. Test kopyasında Rapor Merkezi yüklenmesini kontrollü başarısız yapın (ör. bir bağımlılığın geçici olarak devre dışı bırakıldığı test paketi). Yedek erişim seçim listesi açılmalı; eski rapor fonksiyonları çalışmaya devam etmeli.
4. Ödev Takip/Ödev Kontrol'de öğrenci seçimi, checkbox, kaydetme ve geri alma davranışlarını mevcut kararlı sürümle karşılaştırın.
5. EXE yeniden derleme, PDF önizleme ve otomatik güncelleme testlerini tamamlamadan müşterilere yayımlamayın.

## Kurulum

Tam kaynak ZIP yalnızca temiz bir test klasörüne çıkarılmalı. Küçük yama yalnızca **v3.5.94 tam kaynak** üzerine uygulanmalı; mevcut öğrenci verileri / yazı tipleri / lisans dosyalarının üzerine yazılmamalı. Varsa önce çalışan sürümün yedeğini alın.
