# KoçPilot 360 — Öğrenci Yükleme Performansı V1 (Tanılama Pilotu)

## Kapsam

Kaynak temel: `KocPilot360_v3.5.76_Baileys_Otomatik_Kurulum_Guvenli_TamKaynak_PILOT.zip`.

**Bu sürüm, ölçüm sürümüdür. Henüz çalışma sürelerini azaltan bir optimizasyon yapıldığı iddia edilmez.** Gerçek darboğazı ölçmeden tablo/checkbox/DB koduna müdahale edilmemiştir.

### Kaynak değişiklikleri

- `services/student_load_profiler_v3577.py` (yeni): Öğrenci yükleme döngüsünün toplam süresi, ders sekmesi oluşturma, özet, gecikme, rozet, tablo görsel hazırlığı ve progress güncelleme sürelerini sayaçlarla izler. `functools.wraps` ile özgün metotları tam bir kez çağırır; dönüş/istisna davranışını korur.
- `tools/student_load_report_v1.py` (yeni): Yerel rapor için, yalnızca standart Python kütüphanesi kullanır.
- `tests/test_student_load_profiler_v3577.py` (yeni): çağrı sayısı, dönüş sonucu, istisna, progress, mahremiyet, log döndürme testleri.
- `app.py` (küçük bağlantı): Ana pencere oluşturulmadan **önce** isteğe bağlı gözlemciyi kurar. Tanılama çalışmazsa uygulama açılışını etkilemez.
- Ödev Takip (`ui/homework_form.py`), Ödev Kontrol (`ui/odev_kontrol.py`), progress bar (`ui/progress.py`), kaydetme/geri alma/checkbox, Haftalık Planlayıcı, PDF üretim ve diğer modüllere dokunulmadı.

### Ne ölçülüyor?

`_ogrenci_degisti_combo_ile`, `_bilgileri_getir`, `_ders_tab_olustur`, `_update_student_snapshot`, `_toplam_sure_guncelle`, `_mark_overdue_cells`, `_apply_global_done_for_current`, `_update_overdue_badges`, `_tabs_compact_apply`, `_tabs_split_long_titles`, `_polish_left_tables`, `_apply_tables_visuals`, `IlerlemePenceresi.guncelle`.

Ölçümler `perf_counter_ns` ile alınır. İç içe fonksiyon süreleri çakışabilir; alt sürelerin toplamı genel süre değildir. İlk başlangıçtaki Python import maliyetini ayrıca ölçmez. Genel yükleme süresi, kullanıcı arayüzü yükleme fonksiyonu açısından ölçülür.

**Gizlilik:** Öğrenci adı/ID, telefon, ders, konu, kitap, SQL ve ödev verisi kaydedilmez. Sadece süreler, çağrı sayıları, tablo boyutları ve tamamlanma durumu bulunur. Kayıtlar internet üzerinden gönderilmez.

**Log:** Windows: `%LOCALAPPDATA%\KocPilot360\diagnostics\student_load_v1.jsonl`. En fazla ~2 MB güncel + 2 MB önceki dosya. Linux/macOS: `~/.kocpilot360/diagnostics/student_load_v1.jsonl`. Kayıt erişilemiyorsa form etkilenmez. Tanılamayı devre dışı bırakmak için ortam değişkeni `KOCPILOT_LOAD_PROFILE=0` kullanılabilir.

### Gerçek Windows'ta doğrulama

1. Bu pilot kaynakla ayrı bir **test EXE** derleyin ve test veritabanının yedeğini koruyun. Müşteri canlı EXE'sine doğrudan dağıtmayın.
2. Formu ilk açtığınızda progress bar ve yükleme davranışını gözlemleyin. Farklı miktarda ders/kitap içeren en az üç test öğrencisini sırayla seçin; her öğrenciye üç kez geçin.
3. Aynı öğrencinin kitapları, dersleri, checkbox renklendirmeleri, kilitleri ve verilen ödevleri doğru yüklendi mi kontrol edin. Kaydetme ve geri alma eski sürümle aynı olmalı.
4. Kaynak klasöründe `python -m tools.student_load_report_v1` komutu ile anonim süre raporunu alın (çalışan EXE dizini için gerektiğinde bu aracı Python kaynak ortamından çalıştırabilirsiniz).
5. Gerekirse `%LOCALAPPDATA%\KocPilot360\diagnostics\student_load_v1.jsonl` dosyasını inceleme için paylaşın; dosya isim/ID içermez.
6. **V2 optimizasyonlarına yalnızca bu ölçümlerden sonra geçin.** Özellikle önce tekrar eden özet/öneri hesaplarını, sonra DB sorgularını ele alın; tabloyu yeniden kullanmayı en sona bırakın.

### Test sınırları

- Test ortamı: 79 pytest başarılı, 2 alt test başarılı, 1 PyQt6 gerektiren PDF testi hariç (PyQt6 mevcut değil).
- Yeni gözlemci: 6 özel test başarılı.
- Gerçek Windows, PyQt6, müşteri veri hacmi ve EXE başlangıç profili bu ortamda ölçülmedi.
- Çalışan ödev verme/kaydetme mekanizmasında davranış değişikliği yapılmadı. Kod gözlemcisi çok düşük ek hesaplama maliyeti getirir; sıfır performans etkisi garantisi verilmez.
