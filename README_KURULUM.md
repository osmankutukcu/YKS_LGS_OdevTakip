# V24.3 — Ders/Konu Bazlı Güvenli Yenileme

Bu ZIP yalnızca **V24.2'nin birebir kaynak sürümü** üzerine uygulanacak küçük ve geri alınabilir ek yamadır. ZIP'in içinde tüm uygulamanın EXE/DMG kurulumu bulunmaz. İlk deneme için **proje klasörünün ayrı bir kopyasını** kullanın.

## Kurulum

1. Mevcut kaynak projenizi, öğrenci veritabanınızı ve varsa canlı yapılandırmayı ayrıca yedekleyin.
2. Bu ZIP'i projeden ayrı bir klasöre açın.
3. Terminal veya Komut İstemi ile ZIP'in açıldığı klasöre gidin.
4. Ön denetim: `python install_v243.py --project "/tam/yol/proje" --check`  (Windows: `py install_v243.py --project "C:\\Proje" --check`).
5. Durum `clean` ise: `python install_v243.py --project "/tam/yol/proje" --install`.
6. Kontrol: aynı komutun `--check` sürümünü yeniden çalıştırın; `installed` çıkmalı.
7. Önce test verisiyle Mac/Windows üzerinde uygulama ekranlarını ve ödev tiklerini kontrol edin.

**Geri alma:** `python install_v243.py --project "/tam/yol/proje" --rollback`. Yedekler proje kökündeki `.v243_course_scope_backups/` klasörüne ve durum dosyası `.v243_course_scope_state.json` içerisine yazılır. Geri alma, yamalı dosyalar kullanıcı tarafından değiştirilmişse güvenlik nedeniyle çalışmaz; önce dosyaları manuel uzlaştırın.

## Kapsam

- Koçluk Planı'nın konu kanıtı özetine giden canlı yenileme, seçilen öğrencinin **seçili dersi** açısından yönlendirilebilir.
- Kaynağı belli olan `odev`, `odev_satir`, `odev_takip`, `koc_konu_takip`, `koc_kitaplar` tablolarında konu değişiklikleri **salt okunur** olarak belirlenebilir. Belirsiz diğer kaynaklar genel yenilemeye düşer.
- Konu Haritası kartları ve Öğrenci 360° ekranı **mevcut öğrenci bazlı yenileme şeklinde devam eder**. Bütün konu kartları otomatik yeniden çizilmez.
- Ortak kanıt özetinde Ana Ödev / Konu Haritası ödevi / konu tamamlanma yüzdesi arasındaki fark daha açık anlatılır.
- `homework_form.py`, `odev_kontrol.py`, `db.py` ve gerçek öğrenci kayıtlarına dokunulmaz.

**Sınırlar:** Bu mekanizma aynı yerel SQLite veritabanını kullanan açık ekranlarda, başka bağlantılardan tamamlanmış commit'lerin izlenmesine dayanır. Bulut/çok cihazlı senkronizasyon, genel amaçlı olay otobüsü, tam sınıf/öğrenci bazlı istatistik eşitlemesi veya tüm modüllere konu bazlı canlı yenileme değildir. Gerçek PyQt6 Mac/Windows arayüz testi henüz yapılmadı.
