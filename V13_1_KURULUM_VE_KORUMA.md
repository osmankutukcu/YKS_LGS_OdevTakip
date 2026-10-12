# V13.1 — Veri Koruma, Yedek ve Planlama Doğruluğu

Bu paket, **v3.5.16 geliştirici kaynak yedeğinden** hazırlanmıştır. Mac veya Windows üzerinde çalışan kurulum dosyası değildir. Ana Ödev Takip Formu'nun tik ve kayıt mekanizması bu aşamada değiştirilmemiştir.

## Yapılan kod düzeltmeleri

1. `utils/backup_manager.py`: Veritabanı online backup korunarak, mevcutsa `plan_profiles.json` ve `plan_student_assignments.json` aynı ZIP'e eklenir. İki JSON dosyasının şeması kontrol edilir, SHA-256 listesi ve `backup_manifest.json` içinde doğrulama yapılır. Bozuk profil dosyası varsa “başarılı yedek” denmez. `BackupManager.verify_backup(...)` salt okunur ZIP doğrulamasıdır; geri yükleme yapmaz.
2. `services/daily_followup_v12.py`: Öğrenciye ait tamamlanmış, silinmiş veya teslimi henüz gelmemiş yüzlerce tarihsel satır, 250 açık gecikmiş ödev sınırını yanlış doldurmaz. Gecikmiş/açık adaylar SQL'de seçildikten sonra limit uygulanır; tarihsiz/geçersiz kayıtlar öğretmen incelemesine gider. Kaynak öğrenci kimliği korunur.
3. `tools/audit_odev_links_v13.py`: `odev`–`odev_satir` bağlantılarını **yalnızca okur**; eksik `odev_id`, öğrenci/grup uyumsuzluğu ve grup kopukluklarını bildirir. **Otomatik silme, taşıma, düzeltme veya veri birleştirme yoktur.**
4. `tests/test_v13_stabilization.py`: Sentetik öğrenci ve ödevlerle yeni yedek/profil, doğrulama ve sorgu sınırı testleri.

## Kullanım

- Orijinal uygulama klasörünün **tam yedeğini** alın. Kaynak kod güncellemesini canlı çalışan Mac/Windows kurulumuna doğrudan kopyalamayın.
- Önce yedek bir proje kopyasında yalnızca değişen dosyaları aynı dizinlerine yerleştirin.
- Veritabanı kontrolünü yerel makinede `python tools/audit_odev_links_v13.py "/gercek/yol/uygulama.db"` komutuyla çalıştırın. Komut hiçbir kaydı düzeltmez.
- Programda **Şimdi Yedekle** işlemiyle ZIP oluşturun; yeni ZIP'in içinde iki plan dosyasının mevcut olduğunu doğrulayın. Henüz hiç profil oluşturulmadıysa bunlar normal olarak bulunmayabilir.
- Yedek dosyası **şifrelenmemiş ZIP**'tir. Öğrenci/veli verileri içerebilir: yalnızca erişimi sınırlı, güvenilir bir konumda saklayın.
- Güncellemeyi onaylamadan önce gerçek Mac/Windows PyQt6 ekranlarında: programı aç → öğrenci seç → profil kaydet → yedekle → ZIP içeriğini kontrol et → takip planı önizle → Sihirbaz/Takviye/Eksikler/Öneri tik at/geri al işlemlerini deneyin.

## Bu aşamada bilerek yapılmayanlar

- **Kritik:** Varsayılan yönetici hesabı, eski SHA-256 hash'leri ve yönetici panelindeki ikinci başlatma yolu **henüz değişmedi**. Canlı sistemde erişim politikasını kontrol edin; V13.2'de ilk kurulum, parola değişimi ve mevcut oturumlar birlikte düzeltilmeli.
- Kaynağı olmayan 3 `odev_satir.odev_id` bağlantısı silinmedi veya uydurma bir `odev` satırına bağlanmadı. Öğretmen/program yöneticisinin veri modeli doğrulaması gerekiyor.
- PyQt6/macOS/Windows masaüstü testleri ve gerçek geri yükleme (restore) akışı tamamlanmadı. `verify_backup` **restore değil**, yalnızca ZIP doğrulamasıdır.
- Ana formun yinelenen `_tik_degisti` ve başka yöntemleri korunuyor. V13.2'de davranışı karakterizasyon testleriyle dondurmadan silinmemelidir.
- Web API yetkilendirme ve bütün ödev modüllerini tek kanonik veriye geçirme işlemleri bu pakette yapılmadı.

## Sürüm notu

Bu ZIP'te öğrenci/veritabanı dosyaları, çalışma günlükleri, yönetici gizli araçları, Git geçmişi, derleme önbelleği veya font dosyaları **bulunmaz**. Çalışan uygulama mevcut kullanıcı veritabanından ve lisans/kurulum ayarlarından yararlanır; bunları otomatik olarak değiştirmez.
