# V24.4 Tek Adım Güvenli Kaynak Güncelleme

**Uyumlu kaynak:** Yalnızca belirtilen V24.3 tam kaynak sürümü. Bu bir EXE veya otomatik Windows kurucusu değildir.

1. Mevcut proje klasörünü ve öğrencilerin aktif SQLite veritabanı dosyasını yedekleyin; programı kapatın.
2. Güncelleme ZIP'ini ayrı klasöre çıkarın.
3. Komut satırında `python install_v244.py --project "PROJE_KLASORU" --check` çalıştırın. Beklenen sonuç: `clean`.
4. `python install_v244.py --project "PROJE_KLASORU" --install` çalıştırın.
5. Ayrı test veritabanında haftalık plan, ilerleme ve iki görüşme kaydı oluşturup arşiv/sayı doğruluğunu kontrol edin.
6. Geri almak için: `python install_v244.py --project "PROJE_KLASORU" --rollback`.

Kurulum, mevcut `ui/coaching_manager.py` dosyasının tam SHA-256 özetini bekler; farklı kaynak sürümünde durur. Başka modüllerdeki değişiklikleri sıfırlamaz. Yalnız iki dosyaya müdahale eder.

**Not:** Kurulum sırasında DB değişmez; ancak programda yeni görüşme kaydedilirse `koc_gorusme_gecmis_v244` adlı **veri koruyucu arşiv tablosu** oluşur. Kaynak geri alması bu tabloyu otomatik silmez. DB yedeğini ayrıca saklayın. Üretimde uygulamadan önce gerçek Mac/Windows arayüz pilotu gereklidir.
