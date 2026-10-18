# V41 — Kaydırma ve görünüm güvenli pilot

Önce V36–V40'ın üzerine inşa edilen **V41 delta paketini** izole kopyada deneyin. Mevcut canlı/kurulu sürümün üzerine doğrudan yazmayın. 

`python QA_V41/test_v41_scrollbars.py` başsız renk denetimidir. `python QA_V41/preview_v41_scrollbars.py` PyQt6 kurulu test bilgisayarında **yalnızca örnek veriyle** grafik arayüz önizlemesi açar. Aynı klasörde `QA_V41/README.md` manuel kabul adımları var.

V41 yalnızca arayüz renk ve QSS değişikliklerini içerir. Kullanıcı verileri, ödev kayıt/checkbox iş mantığı, offline senkronizasyonu ve lisans işleri değiştirilmemiştir.

**Not:** Dağıtım paketinde font varlıkları paylaşılmamıştır. Orijinal çalışan kurulumun `fonts/` klasörünü koruyun.
