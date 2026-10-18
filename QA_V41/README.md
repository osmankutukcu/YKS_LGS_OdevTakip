# V41 — Görünüm ve kaydırma çubuğu kabul denetimi

Başsız test: `python QA_V41/test_v41_scrollbars.py`.

Ayrı deneme bilgisayarında **PyQt6 kuruluysa** yalnızca örnek verilerle gerçek pencere testi:
`python QA_V41/preview_v41_scrollbars.py`.

1. Tema seçiminde en az iki açık, iki koyu, bir spor ve bir pastel tema deneyin.
2. 6, 9, 12, 18, 24 piksel kalınlıklarda hem yatay hem dikey tutamacı kontrol edin.
3. Mouse ile üstüne gelme, sürükleme, scrollbar track tıklama, fare tekeri ve touchpad kaydırmayı deneyin.
4. Liste/tablo seçimini koruyarak temayı değiştirin. İçerik veya kaydırma pozisyonu sıfırlanmamalı.
5. Asıl uygulamada Ödev Takip Formu, WhatsApp, Konu Haritası ve bilgi panosunda kaydırmayı deneyin.
6. Özellikle Windows ekran ölçekleri %100, %125, %150 ve Mac Retina ekranı kontrol edin.
7. Gerçek öğrenci verileriyle yapılacak denemeleri test kopyasında gerçekleştirin.

Not: PyQt6 bu paketin hazırlandığı test ortamında bulunmadığı için masaüstü Qt GUI kabul testleri otomatik olarak çalıştırılamadı. Başsız kontroller gerçek sürükleme/ölçekleme davranışını kanıtlamaz.
