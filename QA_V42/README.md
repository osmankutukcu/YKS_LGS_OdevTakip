# V42 — Özel çizimler ve tema uyumlu ekranlar

V41 temel alınmıştır. Güvenli pilot; otomatik üretim/stabil sürüm değildir.

## Değişikliklerin kapsamı

- `ui/theme_special_v42.py`: Qt bağımlılığı olmayan ortak kontrast ve özel çizim renkleri.
- `ui/plan_settings_dialog.py`: DayTimelineWidget, açık/koyu tema duyarlı başlık, eksen, durum ve blok renkleri; canlı tema güncelleme dinleyicisi.
- `ui/odev_kontrol.py`: özel mini istatistik widget'ında açık/koyu yüzey ve metin kontrastı.
- `ui/performans_paneli.py`: iki özel tablo delegate'inde etiketlerin açık arka plan üzerinde kaybolmasını önleyen opak hücre çizimi ve kontrastlı metin; ilerleme miktarı görsel göstergesi korunur.
- `ui/update_dialog.py`: güncelleme penceresi tema uyumu, HTML sürüm notları için sabit açık okuma zemini, geçersiz QSS düzeltmesi, açık pencereyi yeniden renklendirme.
- `ui/homework_guide_dialog.py`: kullanım kılavuzu sekmeleri/başlık/alt düğmeler tema uyumlu, içindeki açık HTML belge korunur.
- `ui/smart_wizard_dialog.py`: açık giriş, metin kutusu ve 7 HTML okuyucuda açık zeminle tutarlı koyu metin; sekme ve başlık tema yenileme.
- `ui/student_workspace_panel_v21.py`: Öğrenci 360° yan panel kabuğu ortak palete uyumlu, rapor içerik rengi korunur.

## Başsız test

`python QA_V42/test_v42_special_colors.py`

V36–V41 QA betikleri de tekrar çalıştırılmalı. Hiçbiri gerçek GUI kabulünün yerini tutmaz.

## Gerçek cihazda gereken testler

Windows ve macOS'ta her tema ile plan zaman çizelgesi ve mini istatistikler, performans tablosu %/trend renkleri, Akıllı Sihirbaz'ın her sekmesi, Güncelleme penceresi ve Kılavuzun sekmeleri açılarak doğrulanmalıdır. Tema bu pencereler açıkken değiştirilmeli; seçme/tıklama/kopyalama/ödev verme işlevlerinin aynı kaldığı kontrol edilmelidir.

Sürüm notu HTML metni bilerek açık kağıt üzerinde gösterilir. PDF/yazdırma çıktılarının renkleri V42'de değiştirilmemiştir.
