# KoçPilot 360 v3.5.80 — Performans V4: Bellekte indeks karşılaştırma (PİLOT)

## Bu sürümün kapsamı
v3.5.79'daki salt okunur SQL indeks denetiminin üzerine **isteğe bağlı** performans karşılaştırma aracı eklendi. Mevcut Ödev Takip, Ödev Kontrol, progress bar, checkbox, veritabanı şeması, haftalık takvim ve PDF üretimi **değişmedi**. Öğrenci seçimindeki yükleme fonksiyonuna da dokunulmadı.

### Eklenen üç dosya
- `services/student_load_index_benchmark_v3580.py`: Kaynak veritabanını **salt okunur** açar; boyut uygunsa (`<=96 MiB`) SQLite `:memory:` kopyası oluşturur. Aynı ödev okuma sorgusunu önce mevcut hâliyle, sonra **yalnızca bellekte** geçici öğrenci indeksi ekleyerek karşılaştırır. Kaynak veritabanına indeks, kayıt veya şema yazmaz. Örnek öğrenci kimlikleri, ders, kitap, konu ve veritabanı dosya yolu raporda gösterilmez.
- `tools/student_load_index_benchmark_v3580.py`: Elle çağrılan test aracı. Program açılışına bağlanmaz.
- `tests/test_student_load_index_benchmark_v3580.py`: kaynak bütünlüğü, veri gizliliği, memory-limit, geriye dönüş ve mevcut indeks senaryoları için testler.

## Nasıl kullanılır?
ZIP'i açtıktan sonra, kaynak dizininde komut istemini çalıştırın:

**Hiç gerçek veri kullanmadan örnek gösterim:**

```bat
python -m tools.student_load_index_benchmark_v3580 --synthetic
```

**Yalnızca yedek/test veritabanında (programdan bağımsız):**

```bat
python -m tools.student_load_index_benchmark_v3580 --database "C:\Yedekler\KocPilot_TEST.db"
```

Komut çıktısı `before.median_ms`, `after_memory_index.median_ms`, `rows_equivalent`, `existing_student_index`, `recommendation` gibi kimlik içermeyen alanlardan oluşur. `memory_limit_exceeded` dönerse veritabanını başka bir biçimde incelemek gerekir, **program veya kullanıcı veritabanı değiştirilmez**. Hata çıktısı yalnızca hata türünü gösterir, veritabanı yolunu gizler.

## Neden otomatik indeks eklenmiyor?
- Yalnızca okuma sorgusunun iyileşmesi, uygulamanın öğrenci değiştirme performansının ölçülmüş biçimde iyileştiğini kanıtlamaz.
- İndekslerin veri yazma ve yedekleme maliyeti bulunur; bu sürüm **yazma maliyetini ölçmez**.
- Farklı Windows diskleri, öğrenci/kitap sayıları ve SQLite şema/indeksleri farklı sonuç verebilir.
- İndeks eklemek gerçek veritabanında şema değişikliği olurdu; bunu kullanıcıdan alınacak sonuçlardan önce yapmıyoruz.

## Ölçümün kapsamı
Dört yoğun öğrenci örneği için `SELECT ders, konu_id, kitap_ad, durum FROM odev WHERE ogrenci_id=?` sorgusunun ortanca ve 95. yüzdelik süreleri kaydedilir. Sonuç satırları karşılaştırılır; fark varsa öneri **`do_not_apply_results_differ`** olur. 96 MiB üstü yedekler varsayılan olarak işlem dışı bırakılır. Başka indeksler mevcutsa taşıma önerisi verilmez. Yedek dosyanın kendisi `mode=ro` ve `query_only` ile açılır. Bellekteki kopya kapanınca silinir.

`--synthetic` ile üretilen örnek yalnızca yapay veridir. Bu rakamlar sizin Windows cihazınızda hızlanma sağlandığını **göstermez**.

## Sınamalar
- V4 ve V3 SQL araçları + öğrenci yükleme/progress + kritik formlar: **93 test başarılı, 14 alt test başarılı**.
- Haftalık planlama/performans yardımcıları: **80 test başarılı, 7 alt test başarılı**.
- Toplam seçili: **173 test başarılı, 21 alt test başarılı**.
- Gerçek Windows/PyQt6, test EXE, A→B→A öğrenci değiştirme, PDF görsel karşılaştırması ve V1 JSONL süre analizi **henüz tamamlanmadı**.

## Sonraki karar
Önce Windows üzerinde V1/V2 öğrenci yükleme süreleri ve bir test veritabanı V4 raporu elde edilmeli. Gerçek sorun SQL okuması değil tablo/checkbox kurulumuysa SQL indeks değişikliği yapılmamalı. Üretime otomatik güncelleme olarak dağıtılmamalıdır.
