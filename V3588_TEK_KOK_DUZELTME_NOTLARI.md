# V3.5.88 tek proje kökü – entegrasyon notları

- Eski `YKS_LGS_HomeworkManager v2/` projesi temel alınıp V3.5.88 ZIP kökündeki 29 yeni dosya aynı proje köküne doğru yerde işlendi; iki `app.py` / iki `version.py` kalmadı.
- Eksik V3.5.87 regresyon testleri, CI preflight ve raporlama araçları geri eklendi.
- Yeni Rapor Merkezi, eski beş analiz kısayolunu gizlemez; hata varsa eski menüler kullanılabilir.
- Windows etiketli Release ve Mac/mobil kabulü, gerçek onay bilgileri olmadan artık yayınlanmaz.
- Sürüm 3.5.88 kalır ancak `version.json` kanalı **pilot** olarak işaretlendi. Bu dosyanın müşteriye otomatik güncelleme olarak yayınlanması önerilmez.
- Kullanıcı veritabanları, WAL/SHM, yedekler, günlükler, makineye özel ayarlar ve özel lisans üretim araçları çıkarıldı.
- Font dosyaları dağıtılmadı; PDF/EXE derlemesi öncesi `FONTS_KURULUM_NOTU.md` uygulanmalı.
- PyQt6, gerçek EXE, Windows/macOS yazıcı ve otomatik güncelleme testleri bu ortamda doğrulanamaz; ek kullanıcı kabulü gerekir.
