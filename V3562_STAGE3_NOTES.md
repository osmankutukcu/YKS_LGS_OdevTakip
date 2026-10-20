# KoçPilot 360 v3.5.62 — Aşama 3 / Öğrenme ve Müdahale Köprüsü

## Değişiklik kapsamı

**Başlangıç:** v3.5.61 Aşama 2 tam kaynak.

**Eklenen dosyalar:**
- `services/learning_intervention_bridge_v3562.py`: KoçPilot'un mevcut V3.5.61 ortak kanıt katmanını, `adaptive_observation_v25` ölçümlerini ve `adaptive_quick_note_v28` öğretmen gözlemlerini **salt okunur** bir öneri kartına bağlar.
- `tests/test_learning_intervention_bridge_v3562.py`: Yeni motor için 20 sentetik otomatik test.
- Bu sürüm notu.

**Mevcut dosyalara değişiklik:** README ve eski modüller dahil hiçbir mevcut kaynak dosyası değiştirilmedi. Eski Aşama 1 ve 2 bileşenleri pakette korunmaktadır. Temel iki form dahil tüm eski dosyalar byte-özdeş kalır.

## Motorun ürettiği taslaklar

- **CHECK_ERRORS:** Tek kısa ölçümde düşük doğruluk görüldüyse neden/öğrenme tanısı koymadan yeni bağımsız kontrol ister.
- **TARGETED_REVIEW:** Ayrı günlerde iki düşük sonuç varsa öğretmene hedefli inceleme ve telafi taslağı önerir.
- **CLARIFY_OBSERVATION:** Hızlı Teşhis gözlemini gerçek bir tanı saymadan öğretmenden kısa doğrulama ister.
- **SPACED_CHECK:** Eski geçerli kısa ölçümden sonra, tahmini unutma oranı uydurmadan yeni hatırlama kontrolü önerir.
- En fazla 3 öneri; aynı ders/konu için tek öncelikli öneri.

## Değişmeyen garantiler / sınırlar

- Ödev Takip/Ödev Kontrol/checkbox/tema/kayıt/geri alma/öğrenci 360 mevcut ekranları değiştirilmedi.
- SQLite şema oluşturulmaz; INSERT/UPDATE/DELETE/commit yapılmaz; hiçbir otomatik ödev, takvim veya WhatsApp işlemi yoktur.
- Öğrenci aktifliğini ve öğrenci/ödev ilişkisini doğrular. V3.5.61 kanıt kartı `UNVERIFIED`, `LINK_REVIEW` veya kaynak çelişkisi gösterirse öneri üretimi durur.
- Eski tablolarda veriler yoksa `NO_LEARNING_PRIORITY`; bu, 'öğrenci konuyu biliyor' demek değildir.
- Oranlar yalnızca kaydedilmiş doğru/yanlış/boş sorulardan hesaplanır. Yüzde 65 **öneri filtre eşiğidir**, bilimsel başarı/ustalık sınırı değildir. 2/7 günlük pencereler **geçici çalışma önerileridir**, kişisel unutma eğrisi değildir.
- Günlük öğrenci deneyiminde **henüz arayüz entegrasyonu yoktur**. Hiçbir yeni popup, otomatik tetikleyici, arka plan servisi aktive edilmedi.
- `hub_card` parametresini yalnızca aynı işlem/snapshot üzerinde `read_coaching_evidence_hub` çıktısını yeniden kullanmak için çağırın; dışarıdan gelen JSON'a güvenmeyin.
- UI'ye bağlanacağı aşamada okuma ana UI thread'inden ayrı yapılmalı; okuma süre sınırı, iptal ve öğrenci değiştirmede eski sonuçları iptal etmek zorunludur.

## Geliştirici çağrısı (opt-in, salt okunur)

```python
from datetime import date
from services.learning_intervention_bridge_v3562 import read_learning_intervention_draft
# con: çağıranın yönettiği, tutarlı snapshot taşıyan SQLite bağlantısı
card = read_learning_intervention_draft(con, verified_student_id, today=date.today())
```

## Doğrulama

- 2026-10-20: Yeni ve seçili eski modüllerde **158 test çalıştı, 157 geçti, 1 atlandı.**
- `tools/v3527_core_guard.py`: **PASS**. 10 korunan dosya, 4 korunan yardımcı, statik davranış/AST kontrolü başarılı.
- Windows GUI / gerçek öğrenci veritabanı uçtan uca test **YAPILMADI**; bu paket canlı kullanım onayı değildir.

## Sıradaki aşama

Öğretmen arayüzüne entegrasyon için önce kontrollü, bayrakla kapatılabilir pilot: mevcut Koç Asistanı'nın ekranını ve ana formları bozmadan, sadece öğrenci bazlı salt okunur öneri gösterimi. Üretime açmadan önce Windows GUI, veri gizliliği, hızlı öğrenci değiştirme ve büyük veritabanı performans testleri gereklidir.
