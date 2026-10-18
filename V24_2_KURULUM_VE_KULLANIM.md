# V24.2 – Öğrenciye Göre Güvenli Değişiklik Yönlendirme

**Yalnızca V24.1'in tam kaynak sürümüne uygulanır.** Bu bir Windows EXE değildir.

## Kurulum

1. Uygulamayı kapatın, **proje ve öğrenci veritabanının yedeğini ayrı ayrı alın**.
2. ZIP içindeki `payload/`, `checksums.json`, `install_v242.py` dosyalarını aynı klasörde tutun.
3. `python3 install_v242.py --project "/proje/kok" --check` → `clean` görünmeli.
4. Önce test kopyasında `python3 install_v242.py --project "/proje/kok" --install` çalıştırın.
5. Geri alma: `python3 install_v242.py --project "/proje/kok" --rollback`.

## Ne yapar, ne yapmaz?

- V24.1'in okuma bağlantısı ile diğer SQLite bağlantılarındaki **commit** işlemlerini algılar; **seçili öğrencinin kayıtlarını** sınırlı, yalnızca-okunur örneklemlerle karşılaştırır.
- Değişiklik sadece *başka öğrenci* veya *izlenmeyen tablo* üzerindeyse açık ilgili panellerin ortak veri özetini gereksiz yenilemez.
- Öğrenci 360°, Koçluk Planı → Konu Takibi ve Konu Haritası ortak kanıt özetini yenileyebilir. **Konu Haritası kartlarının tamamı yeniden yüklenmez**, filtreler ve öğretmen seçimi korunur.
- Kaynağa göre `homework`, `topic_map`, `coaching`, `exam`, `performance`, `student`, `survey` kategorilerinde değişiklik algılanabilir. Bu bilgiler **yerel bellekte kalır**; öğrencinin kimliği, ad-soyadı veya verileri dışarı gönderilmez.
- Bu pilotta **ders/konu düzeyinde kesin hedefleme yok**; yalnızca öğrenci bazında filtreleme doğrulandı. Fazla kalabalık veya uyumsuz kaynaklarda sistem yenilemeyi engellemek yerine ihtiyatlı davranır.
- Yeni tablolara otomatik trigger eklemez; öğrenci veritabanı, ödev matrisi ve checkbox yazma işleyişi değiştirilmez.
- 2 saniyelik hafif `data_version` kontrolü, değişiklik görüldüğünde seçili öğrenci kayıtlarının sınırlı okumasını tetikler. Büyük/verimli olmayan veritabanlarında gerçek cihazda performans kontrolü gereklidir.
- Uygulama açılırken `YKS_LIVE_CHANGE_EVENTS=0` ile isteğe bağlı olarak kapatılabilir. Başka cihaz/bulut senkronizasyonu sağlanmaz.
- Gerçek Qt GUI, Windows/Mac sürümü, kurulumlu EXE ve uzun süreli yük testleri henüz yapılmadı.
