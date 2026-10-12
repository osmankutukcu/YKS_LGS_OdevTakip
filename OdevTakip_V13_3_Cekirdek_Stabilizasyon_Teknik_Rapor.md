# Ödev Takip V13.3 — Öğrenci Kimliği, Tik ve Ödev Bütünlüğü

## Temel sürüm

- Esas alınan sürüm: Kullanıcının v3.5.16 geliştirici yedeği üzerine hazırlanmış V13.2 kaynak proje.
- Bu paket gerçek öğrenci verisi içermez; herhangi bir öğrenci veritabanı değiştirilmemiştir.
- v3.5.16 canlı kurulum üzerinde Windows/macOS grafik kabul testi henüz yapılmamıştır.

## Tespit edilen sorunlar ve uygulanan değişiklikler

1. **Kısmi konu eşleşmesi riski.** `_hucre_bul` önce `konu in satır_metni` kullanıyordu. Örneğin `Elektro` arandığında `Elektrostatik` satırını bulabilirdi. Artık `unique_exact_cell` ile ders, kitap, konu **tam, normalize edilmiş ve tekil** eşleşmek zorunda. Aynı ada sahip birden fazla satır/kitap/ders bulunursa işlem reddedilir. Etkilenen dosyalar: `ui/homework_form.py`, `utils/homework_integrity_v133.py`.
2. **Öğrenciler arası tamamlanma karışması.** İki `OneriPaneli` sınıfında `_global_done_check`, öğrenci kimliğine bağlı olmadan `odev` tablosunu tarıyordu. Bu, A öğrencisinin tamamladığı bir konuyu B öğrencisinde de tamamlandı sayabiliyordu. Artık `student_completed_task` kullanılıyor; yalnızca seçilen öğrencinin ID'siyle eşleşen, silinmemiş, tamamlandı durumundaki kayıtlar değerlendirilir. Eski `odev` ve `odev_satir` şemalarına **salt okunur** uyum eklendi.
3. **Eski ödev kümesine kayıtta sahiplik kontrolü eksikliği.** Var olan bir `kume_id` ile kayıtta `odev_kume.ogrenci_id` doğrulanmıyordu. Kayıttan önce `SELECT id FROM odev_kume WHERE id=? AND ogrenci_id=?` kontrolü eklendi. Uyuşmazlıkta kayıt durdurulur; başkasının kümesine ödev yazılmaz.
4. **Otomatik işaretlemede pasif hücre kontrolü.** Yeni tik aktarımı artık etkin (`ItemIsEnabled`) olmayan hücrelere müdahaleyi de reddediyor; kilitli ödevler korunur.
5. **Çift `_tik_degisti` tanımı.** Ana formda eski ve son tanımın işlevsel gövdeleri aynıydı; eskisinin iki ek içe aktarma satırı vardı. Python'un etkisiz bıraktığı eski tanım kaldırıldı. Aktif son tanım ve mevcut QTableWidget sinyal akışı değiştirilmedi. Diğer 5 yinelenen fakat davranışları farklı metot **korundu**.

## Sürümde değişmeyenler

- Manuel tikleme, tik kaldırma, Sihirbaz/Takviye/Eksikler/Öneri için mevcut güvenli aktarım işlemleri, ödevleri kaydetme ve korunan/tamamlanmış hücre kuralları.
- SQLite tablo şeması, kayıtlı öğrenci verileri, uygulama ikonları, PDF raporları ve koçluk hesaplamaları.
- Üç kopuk `odev_satir → odev` bağlantısı bu aşamada otomatik silinmedi veya eşleştirilmedi; kontrollü veri uzlaştırma gerektirir.

## Testler

- V13.3'e özgü öğrenci kimliği, Türkçe karakter, silinmiş/tamamlanmamış ödev, iki tablo, tam/tekil hücre eşleştirme ve önceki aktarım testleri başarılı.
- Geniş başsız regresyon: **397 başarılı test, 44 başarılı alt test**. **3 grafik arayüz testi PyQt6 eksikliği nedeniyle seçilmedi**.
- PyQt6 gerektiren dört ek test modülü bu sistemde yüklenemedi; GUI'nin bütünü doğrulanmış değildir.
- Kaynak Python dosyalarının tamamı AST sözdizimi kontrolünden geçti; ZIP dosyalarının `testzip` bütünlük kontrolü yapıldı.

## Kurulum — önerilen sıra

1. Gerçek çalışma bilgisayarında **hem SQLite hem WAL/SHM dahil tutarlı veritabanı yedeği**, profil JSON'ları, uygulama kaynakları ve kullanıcı dosyalarını yedekleyin. SQLite yedeğini uygulama aracılığıyla güvenli yöntemle üretin.
2. Kullanımdaki V13.2 kaynak projesinin bir **ayrı test kopyasını** alın; yalnız değişen dosyaları bu kopyadaki aynı yolların üstüne uygulayın. V13.2 yoksa veri/font hariç tam kaynak paketini kullanın.
3. Önce Osman Fizik ve benzer isimli başka öğrenciyle seçme, farklı konu isimleri, manuel tikle-geri al, Sihirbaz/Takviye/Eksikler/Öneri, eski küme seçimi, silinmiş/tamamlanmış ödev koruması ve farklı ders kitaplarının birebir eşleşmesini deneyin.
4. Windows ve Mac üzerinde ekran testleri başarılı olmadan canlı sürümün üzerine kopyalamayın.

## Kalan yüksek öncelikler

- Ana formdaki davranışı farklı olan 5 yinelenen metodun kontrollü ayrıştırılması, gerçek Qt sinyal testleri.
- `odev` ve `odev_satir` için kayıt kaynaklarının kontrollü uzlaştırılması; kopya üç satır için elle doğrulama.
- Profil/ödev/SQLite tutarlılığıyla birlikte uçtan uca Mac/Windows kabul testleri, gerçek yedekten geri yükleme provası.
- `student_completed_task` çok büyük öğrenci geçmişlerinde hız için indeks/önbellek testleri.
