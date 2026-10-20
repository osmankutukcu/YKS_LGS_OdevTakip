# KoçPilot 360 v3.5.75 — Aşama 16 / Kararlılık Kabul Altyapısı

## Kapsam
Bu bir **pilot kaynak paketi ve denetim aracı**dır; mevcut Windows EXE ya da internet servisi değildir.
Ödev Takip / Ödev Kontrol / mevcut ana sayfa / Haftalık Planlayıcı / PDF üretici / Hızlı Teşhis / Web API ve anket kodları değiştirilmemiştir.

## Yeni dosyalar
- `tools/v3575_stabilization_gate.py` — dört izole pytest grubunu, bütün Python dosyalarının sözdizimini, 15 kritik kaynak hash'ini ve `v3527_core_guard` bütünlük kapısını kontrol eder. Testleri ayrı Python süreçlerinde çalıştırır: bazı eski testler global Qt taklitleri kurduğundan tek oturum yanıltıcı başarısızlıklara neden olabilir.
- `tests/v3575_critical_source_manifest.json` — 15 önemli dosyanın v3.5.74 kaynak SHA-256 değerleri; ileride kasıtlı kod değişikliklerinde insan incelemesi gerekir.
- `tests/test_stabilization_gate_v3575.py` — 6 test; değişen veya kaybolan kaynakların reddini ve canlı sürümün otomatik onaylanmamasını sınar.
- Bu rapor.

## 20 Ekim 2026 test sonuçları
- Yeni araç testleri: **6 başarılı**.
- Dört izole regresyon grubunda: **267 başarılı** (koçluk 110, haftalık planlama 74, anket 48, Windows performans/kayıt yardımcıları 35).
- 658 Python dosyası: sözdizimi sorunu yok.
- 15 kritik dosya değişmemiş. Çekirdek koruma: 10 dosya, 4 yardımcı, 13 etkili işlem işleyicisi, PASS.
- Windows Qt olmaması nedeniyle iki özel test **ertelendi**: `test_known_plan_approved_topic_mechanism_reused`, `test_page_count_single_page_when_details_disabled`. Bunlar başarılı kabul edilmedi.
- Tam `pytest tests/` taraması, Qt/PyQt6 ve kaynak pakette bulunmayan özel lisans test bağımlılığı sebebiyle toplama hataları veriyor. Tam proje için **yeşil** test beyanı yok.
- Kaynak koruma denetiminde `ui/homework_form.py:_odev_kontrol` ve `ui/odev_kontrol.py:_hesapla_yuzde` için önceden var olan gölgelenmiş tanım uyarıları var; davranışları değiştirilmedi. Refaktör öncesi insan incelemesi gerekir.

## Yeniden çalıştırma
Proje klasöründe:

```bash
python -m pytest -q tests/test_stabilization_gate_v3575.py
python -m tools.v3575_stabilization_gate --run-tests --output stabilization_report.json
```

Araç internete bağlanmaz, gerçek öğrenci verisi okumaz veya değiştirmez, EXE yayımlamaz. Araçtaki `PASS_STATIC_AND_SELECTED_TESTS` **yalnızca seçilmiş testlerin geçtiği** anlamına gelir; canlı dağıtımı onaylamaz.

## Windows'ta zorunlu son kabul listesi

### Korunan formlar
- [ ] Aynı öğrenciye aynı konu/kitap hücrelerinden ödev ver: tabloya anında birer kez gelsin.
- [ ] Çok hızlı 30–50 checkbox tıklaması: gecikme/yanlış hücre/çift kayıt gözlenmesin; süreyi eski EXE ile aynı donanımda karşılaştır.
- [ ] Öğrenci değiştir: önceki öğrencinin taslağı veya öğretmen önerisi yenisine karışmasın.
- [ ] Kaydet, yeniden aç, geri al, kilitle/kilidi aç: önceki sürümle aynı sonuçlar oluşsun.
- [ ] Tema ve bildirimlerin görünümü; yazı-zemin kontrastı aynı olsun.

### Haftalık Planlayıcı
- [ ] Okul, kurs, özel ders, uyku ve dinlenme rutinlerini kaydet/yeniden aç: değerler korunmalı.
- [ ] Verilen Ödevler'deki görev ve süre toplamı planda yerleşen + yerleşemeyen toplamıyla eşleşmeli.
- [ ] Okul/özel ders/uyku bloklarında çalışma olmamalı; günlük kapasite aşılmamalı.
- [ ] A4 yatay PDF önizlemesini v3.5.56 kararlı referansıyla yan yana karşılaştır: sayfa, font, çizim, görev içerikleri ve uzun metin taşmaları.
- [ ] `test_page_count_single_page_when_details_disabled` testi gerçek PyQt6 kurulumu ile yürütülmeli.

### Koçluk / Anket / Dağıtım
- [ ] Öğrenme, Hızlı Teşhis, Öğrenci 360°, Koç Asistanı ve Sihirbaz aynı öğrencinin kayıtlarını göstermeli.
- [ ] Onaysız anket yanıtı ödev durumunu ve Hızlı Teşhis öğretmen kaydını değiştirmemeli.
- [ ] Özellikler kapalıyken eski menü ve işlevlere geri dönüş denenmeli.
- [ ] Gerçek öğrenci kaydı kullanılmadan HTTPS/telefon testi daha sonra yapılmalı.
- [ ] Kurulum EXE, lisans anahtarı, GitHub güncellemesi, geri dönüş ve veri yedeği testleri yapılmalı.

## Yayın kararı
**PILOT / MÜŞTERİYE DAĞITMAYIN.** Gerçek Windows arayüzü, canlı performans, PDF piksel/sayfa karşılaştırması, EXE, lisans ve otomatik güncelleme kontrolleri tamamlanmadı.
