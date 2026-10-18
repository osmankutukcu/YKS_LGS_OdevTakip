# V24.1 – Ortak Değişiklik İzleme ve Ekran Yenileme

**V24.0 üzerine kurulur.** Güncelleme yalnızca `ui/coaching_manager.py`, `ui/topic_map_dialog.py`, `ui/student360_panel_v16.py` dosyalarını değiştirir ve `services/live_change_probe_v241.py` ile `ui/live_change_bridge_v241.py` modüllerini ekler. Ödev formları, ödev kontrol, `db.py` ve veri şeması değiştirilmez.

## Test ortamında kurulum

1. Bütün uygulama pencerelerini kapatın; proje ve veritabanının ayrı yedeğini alın.
2. ZIP içindeki `install_v241.py`, `checksums.json` ve `payload/` aynı dizinde olmalı.
3. Önce `python install_v241.py --project "/proje/kok" --check` çalıştırın. `clean` sonucu beklenir.
4. Test proje kopyasında `python install_v241.py --project "/proje/kok" --install` çalıştırın.
5. Geri alma: `python install_v241.py --project "/proje/kok" --rollback`. Yedekleri silmeyin. Windows'ta `py`, Mac'te `python3` kullanılabilir.

## Davranış ve sınırlar

- Programın kendi **yerel SQLite dosyası** başka bir bağlantı üzerinden başarıyla güncellendiğinde (commit), açık ve görünür Koçluk Planı → Konu Takibi, Konu Haritası ortak özet şeridi ve Öğrenci 360° sekmesi en geç birkaç saniye içinde yeniden okuyabilir. Her iki saniyede bir çok hafif `PRAGMA data_version` kontrolü yapılır; veri satırları taranmaz.
- Her modül **kendi seçili öğrencisini** kullanır. Yeni veri geldiğinde başka öğrenci otomatik seçilmez. Kaydın türü veya öğrencisi bu pilotta olaydan çıkartılamaz; görünür modüllerin ilgili özeti yenilenir.
- Konu Haritası **kartların tamamını otomatik yeniden yüklemez**, sadece V24.0 ortak kanıt şeridini günceller. Koçluk Planı da yalnızca aynı şeridi yeniler. Öğrenci 360° görünürken kendi özetini yeniden okur.
- Bu izleyici başka **cihazların veritabanlarını** dinlemez, bulut/offline senkron kurmaz; dış ağ veya öğrenci bilgisi göndermez. İlk kayıt algısı kullanıcıdan bir işlem istemez.
- Kapatmak için uygulama açılırken `YKS_LIVE_CHANGE_EVENTS=0` ortam değişkenini kullanabilirsiniz.
- `PRAGMA data_version`, işlemi yapan aynı bağlantı üzerinde takip edilmez; izleyici özel ve kalıcı bir okuma bağlantısı kullandığı için diğer bağlantılardan commit sonrası değişimleri görür. Kaynakta kalıcı veritabanı yolu değişirse yeni başlatma gerekir.
- Gerçek Mac/Windows Qt GUI, dağıtılmış EXE ve uzun süreli yük testi bu ortamda doğrulanmadı. `_tik_degisti` eski sürüm koruma sözleşmesi uyarısı bu sürümün kapsamı dışındadır.
