# Ödev Takip V24.3 — Ders/Konu Kapsamlı Yenileme ve Sayım Açıklaması

## Dayanak

Özgün kullanıcı kaynağı: `YKS_LGS_HomeworkManager_v2_Son_Hal(2).zip`; önceki birleşik yapı: **V24.2**. Bu değişiklik doğrudan V24.2'nin doğrulanmış sürümüne uygulanır. Gerçek öğrenci verisi taşınmaz ve yeniden yazılmaz.

## Neler yapıldı?

1. **Salt okunur ders/konu izi** (`services/course_topic_scope_v243.py`): Beş tanımlı tabloda yalnızca seçilen öğrenciye ait sınırlandırılmış satırları okur; ders eşleşen kayıtların kaynak/konu parmak izlerini karşılaştırır. İlgisiz derste değişiklik doğrulanabiliyorsa gereksiz yenilemeyi engeller. Ders adı karışık, şema eksik, 500 satır üstü, bilinmeyen tablo veya önceki özeti yoksa **yenilemeyi engellemez**. `TYT Matematik` ile `LGS Matematik` ayrı kalır; Türkçe `İ` normalize edilir.
2. **Değişen tablonun açık kimliği** (`services/student_change_scope_v242.py`): Önceki `StudentDataChange` yapısına geriye dönük eşitlik davranışını koruyan salt okunur `tables` alanı eklenir.
3. **Koçluk Planı konu sekmesi** (`ui/live_change_bridge_v241.py`, `ui/coaching_manager.py`): Mevcut 2 saniyelik yerel SQLite değişiklik izleyicisine, sadece ilgili Koçluk Planı konu özetinin güncellenmesinde kullanılan opsiyonel `course_attr` desteği eklenir. Mevcut callback, öğrenci değişimi ve koçluk yazma mantığı korunur.
4. **Neden farklı rakamlar?** (`services/coach_shared_topic_v1.py`): Ortak konu kanıtları özeti; Ana Ödev satırları, Konu Haritası mikro ödevleri ve kartlardaki konu işaretlerinin farklı ölçüler olduğunu açıklamaya devam eder, daha anlaşılır metin sunar.

## Kapsam sınırları

- **Konu ayrıntısı kodda tespit ediliyor**, ama Konu Haritası'nın kartları değiştirilmediği için kartlar tek tek otomatik yenilenmez. Mevcut Konu Haritası/Öğrenci 360° öğrenci bazlı genel özet yenilemesi sürer.
- Ders/konu düzeyli kesin sınıflandırma sadece bilinen beş tablo için geçerlidir. `koc_plan`, deneme, genel öğrenci profili gibi konu bazında güvenle ayrıştırılamayan değişiklikler, **belirsiz** sayılır ve özet yenilenir.
- SQLite'ın `PRAGMA data_version` sinyali aynı bağlantı üzerinden yapılan commit'lerde değil, **başka bağlantılar üzerinden yapılan commit'lerde** farklılaşır. Bunun üzerine bütün program için anlık, garantili değişiklik teslimi iddia edilmez.
- Bilgi özeti ayrı kayıt türlerini **toplamaz**. Ödevin tamamlanması konu öğrenildiği anlamına gelmez.
- Daha önce belirlenen `homework_form._tik_degisti` koruma testi uyuşmazlığı bu kapsamda düzeltilmedi; gerçek checkbox ve arayüz testlerinin yayın öncesi yapılması gerekiyor.

## Değiştirilen dosyalar

- `services/student_change_scope_v242.py`
- `services/course_topic_scope_v243.py` (**yeni**)
- `ui/live_change_bridge_v241.py`
- `ui/coaching_manager.py`
- `services/coach_shared_topic_v1.py`

**Değişmeyen kritik dosyalar:** `ui/homework_form.py`, `ui/odev_kontrol.py`, `db.py`, `ui/topic_map_dialog.py`, `ui/student360_panel_v16.py`, `services/live_change_probe_v241.py`; ayrıca veritabanı şeması ve kayıtları.

## Testler

- Seçili yeni ve ilgili regresyon test koşumu: **269 test + 4 alt test başarılı** (çalıştırma; tüm program testleri değildir).
- Yeni sürüm kontrolleri: Türkçe ders anahtarları; aynı öğrenci farklı ders; başka konuya taşıma; mikro ödev; öğretmen konu kaydı; kitap verisi; koçluk planı gibi konu dışı kaynakların temkinli yenilenmesi; bilinmeyen öğrenci/ders; şema bozuk; kayıt sayısı sınırı; salt okunur olma; geçmiş `StudentDataChange` karşılaştırmalarını koruma.
- Kurucu denetimleri: temiz V24.2 kurulumu, yeniden kurmama, geri alma, bilinmeyen sürümü reddetme, ana form ve `db.py` dosya özeti kontrolü.
- **Yapılmayan testler:** PyQt6 ile gerçek Mac/Windows arayüz testi, canlı öğrenci verisiyle tam sayı karşılaştırmaları, EXE paketleme, kurum yük ve bulut senkronizasyon testi.

## Önerilen devam

Bundan sonra yeni ayrı ekranlar yerine, ana formlardaki başarılı commit'ler için isteğe bağlı işlem kaynağı kimliği, uygun olaylar için UI bağlam yenilemesi ve iki ana form ile 360°/Adaptif Koç'un sayım kapsamı karşılaştırmaları üzerinde gerçek cihazlı entegrasyon pilotu önerilir. Ana ödev yazma kodları izinsiz değiştirilmemelidir.
