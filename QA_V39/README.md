# V39 popup, menü ve bildirim tema kabul testi

**Temel:** V38 güvenli pilot paket; V36/V37/V38 düzeltmeleri içerir. Üretime doğrudan yüklemeyin.

## Kod denetimi (PyQt6 gerektirmez)

Proje kök dizininde:

```sh
python QA_V39/test_popup_theme_v39.py
python QA_V38/test_notification_theme_v38.py
python QA_V37/test_v37_semantic.py
python QA_V36/run_theme_safety.py
```

## Windows/macOS canlı UI denetimi (PyQt6 gerekir)

```sh
python QA_V39/preview_popup_windows_v39.py
```

Örnek veri kullanan bu pencere kalıcı ayarlara, öğrenci/ödev kayıtlarına veya veritabanına erişmez. Tema seçimini değiştirirken menüleri, iki düğmeli uyarıyı, QErrorMessage'i ve özel ilerleme penceresini kontrol edin.

En az Cloud Light, Nord, Dracula, Klasik Koyu, Neon, bir spor teması ve kullanıcı tarafından oluşturulmuş açık/koyu temayı deneyin. Koyu moda geçerken açık kalan mesajlarda yeniden çizimi, Evet/Hayır'ın dönüş değerini, açılır menü aksiyonlarını, klavyeyle gezinmeyi ve pasif seçenekleri deneyin.

## Kapsam ve sınırlar

- Merkezi tema motorundan bağımsız tanımlanan her zengin HTML/özel boyanmış bileşen bu sürümde değiştirilmedi.
- İşletim sistemi tarafından çizilen QFileDialog/QColorDialog pencerelerini zorla Qt çizimine çevirmiyoruz.
- QWidget ekranının gerçek çizimini doğrulamak için uygulamayı Windows/macOS üzerinde çalıştırmak şarttır.
- Kapsam dışı modüllerin renk problemlerini bildirmek için önceki QA_V37 isteğe bağlı okunabilirlik denetimi kullanılabilir.
- Üretim dosyalarının üstüne yazmadan önce yedek alın, test ortamına çıkarın.
