# V40 Tema ve Özel Kartlar — Güvenli Pilot

Kaynak: V39 güvenli pilot tam paket. Kurulu üretim programının üzerine doğrudan yazmayın.

## Başlangıç
1. Orijinal kaynak kod ZIP'ini ve veritabanı dosyalarını ayrı yere yedekleyin.
2. `YKS_LGS_Tema_V40_GuvenliPilot_TamProje.zip` paketini **ayrı bir test klasörüne** çıkartın. Mac ve Windows ortamında, projenin zaten kullandığı PyQt6 bağımlılıklarını kurulu tutun.
3. İsteğe bağlı statik test: proje kökünden `python QA_V40/test_v40_critical_panels.py`; ardından `QA_V36`, `QA_V37`, `QA_V38`, `QA_V39` içindeki testleri çalıştırın.
4. İki açık ve iki koyu tema deneyin (örneğin Cloud Light, Fenerbahçe, Nord, Dracula). Öğrenci kaydı oluşturmadan ve gerçek veriye dokunmadan ana ekranı, Günün Özeti şeridini, başarı grafiğini, gecikmiş ödev uyarılarını, rozetleri ve detaylarını açın.
5. Tema **açık pencere sırasında** değiştirildiğinde başlık, grafik yüzde yazısı, kırmızı uyarı, yardımcı yazılar, sağ tık menüsü ve modal mesajlar hâlâ okunabilir olmalı.
6. Adaptif Koçluk Merkezi ve Müdahale Takip raporlarının HTML kartları özellikle beyaz doküman zemini üzerinde okunabilir kalmalı. Bu, yeni koyu HTML rapor şablonu değil, kontrast koruyan güvenli geçiş tasarımıdır.
7. Mac/Windows yüksek DPI, ekran büyütme (%125, %150), işletim sistemi karanlık modu ve kullanıcı tanımlı özel renklerde görsel karşılaştırma yapın.
8. Evet/Hayır, Kapat, rozete tıklama, navigasyon ve veri güncelleme davranışlarının V39 ile aynı olduğuna emin olun. Bu senaryoları bu ortamda gerçek GUI'de çalıştırmak mümkün olmadı.

## Kapsam sınırı
V40, ana sayfada ve iki HTML koçluk raporunda hedefli bir iyileştirmedir. **Tüm uygulamanın temasının tamamlandığı anlamına gelmez.** Özellikle diğer QTextBrowser HTML içerikleri, Qt dışında çizilen çıktılar, PDF ve native dosya seçimi pencereleri ayrı kabul testine ihtiyaç duyar.
