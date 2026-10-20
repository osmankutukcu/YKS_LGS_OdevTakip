# KoçPilot 360 — v3.5.79 / Performans V3 (salt okunur SQL denetimi)

## Neden kademeli ilerliyoruz?
Öğrenci değiştirilirken `_ders_tab_olustur()` her ders için aynı öğrencinin **tüm ödev satırlarını** `odev` tablosundan yeniden okuyor. Ders sayısına göre aynı sorgu birçok kez çalışabilir. İlgili sorguyu değiştiren prototipte, ana Ödev Takip Formu'nun korunmuş SHA-256 değeri değiştiği için **5 eski koruma testi hata verdi**. Prototip **geri alındı** ve korunan ana form kaynak dosyası v3.5.78 ile birebir eşit hale getirildi. Değişmiş prototip bu pakete konmadı.

Bu nedenle V3'te üretim kodu sorgularını ve veritabanını değiştirmeden, gelecek optimizasyon için kanıt toplamayı sağlayan modüler, salt okunur SQL denetimi hazırlanmıştır.

## Eklenen dosyalar
- `services/student_load_sql_audit_v3579.py`: mevcut `odev` tablosunda öğrenci kimliğiyle başlayan indeks bulunup bulunmadığını, ödev satırlarının toplam sayısını ve mevcut sorgunun `EXPLAIN QUERY PLAN` sonucunu raporlar. Veritabanı `mode=ro` ile açılır; `PRAGMA query_only=ON` kullanılır.
- `tools/student_load_sql_audit_v3579.py`: bu denetimi komut satırından JSON olarak gösterir. Dosya yolu, öğrenci kimliği, öğrenci adı, ders, kitap veya ödev metni çıktı verisine yazılmaz.
- `tests/test_student_load_sql_audit_v3579.py`: doğru indeks tanıma, yanlış indeks, kayıt/gizlilik korunması, eksik tablo, gerçek read-only ve CLI hata senaryoları (8 test).

## Mevcut uygulama davranışı
- Progress bar **değişmedi**.
- `ui/homework_form.py`, `ui/odev_kontrol.py`, `db.py`, `ui/progress.py`, checkbox/renk/kilit/kaydetme, Haftalık Planlayıcı ve PDF kaynakları **değişmedi**.
- Ana açılış dosyası `app.py` ve V1/V2 hızlandırmaları **değişmedi**.
- Yeni SQL denetimi **uygulama açılırken çalışmaz**, gerçek öğrenci yüklemesini yavaşlatmaz ve indeks oluşturmaz.
- Bu sürüm tek başına herhangi bir hızlanma sağlamaz. Amaç veritabanı indeks değişikliğinin gerekip gerekmediğini gerçek veriler üzerinde güvenle araştırmaktır.

## Denetimi nasıl uygularız?
Sadece **yedek/test veritabanında**, Python kurulu ortamda, ZIP'i çıkardıktan sonra:

```bat
python -m tools.student_load_sql_audit_v3579 --database "C:\\Yedekler\\KoçPilot_Test.db"
```

Sonuçta `has_student_prefix_index`, `query_plan_search` / `query_plan_scan`, `homework_row_count` ve `recommendation` gibi anonim alanlar bulunur. Sunucu veya internet kullanılmaz. **Araç hiçbir SQL CREATE/UPDATE/DELETE komutu çalıştırmaz.**

## Değerlendirme ve olası V4
- Büyük veritabanında uygun indeks eksik ve sorgu `SCAN` yapıyorsa, bir **yedek veritabanında** opsiyonel `odev(ogrenci_id)` indeksinin okuma ve kayıt maliyetleri karşılaştırılabilir. İndeks ekleme işlemi bu pakette yapılmamıştır.
- V1 ölçümünde `%LOCALAPPDATA%\\KocPilot360\\diagnostics\\student_load_v1.jsonl` dosyasındaki öğrenci yükleme sürelerini eski ve yeni sürümde karşılaştırın.
- Aynı A→B→A öğrenci geçişinde ders, kitap, checkbox, renk, kilit, sağdaki Verilen Ödevler ve Haftalık PDF sonuçları karşılaştırılmalıdır.
- Windows/PyQt6 canlı arayüz testi yapılmadan müşteriye dağıtmayın.

## Test sonuçları
- Yeni SQL tanılama testleri: **8 geçti**.
- Öğrenci yükleme, korunan çekirdek, checkbox, Windows performans yardımcıları, Haftalık Planlayıcı güvenlik ve akademik kanıt dahil geniş seçili regresyon: **139 test, 8 alt test geçti**.
- Bu testler gerçek Windows yükleme süresini ölçmez. Gerçek PyQt6/EXE ve canlı veritabanı performans testleri hâlâ bekliyor.
