# V24.1 — Ortak Değişiklik İzleme ve Okuma Yenileme Raporu

**Kaynak:** Kullanıcının 16 Ekim 2026 tarihli `YKS_LGS_HomeworkManager_v2_Son_Hal(2).zip` dosyasına dayanarak hazırlanan **V24.0 tam kaynak**. V24.1 yalnızca V24.0 üzerine kurulur.

## Amaç

Ana kayıt otoritesi olan Ödev Takip/Ödev Kontrol formlarının hiçbir yazma fonksiyonuna dokunmadan, **başka bir SQLite bağlantısından başarıyla kaydedilmiş** değişikliklerden Koçluk Planı, Konu Haritası ve Öğrenci 360°'ı haberdar etmek. Tekrarlanan kayıt kopyaları veya çapraz-modül güncelleyiciler oluşturulmaz.

## Somut değişiklikler

1. `services/live_change_probe_v241.py` (**yeni**): Salt-okunur ve kalıcı SQLite bağlantısında `PRAGMA data_version` izleyerek başka bağlantılardaki başarılı commit sonrası değişiklikleri belirler. Rollback ve henüz commit edilmemiş yazımların değişiklik olarak bildirilmemesi; WAL modu; veritabanının yenisiyle değiştirilmesi; geçici erişilememe durumunda güvenli hata davranışı test edildi. **Değişen kayıt, öğrenci kimliği veya veri türünü tespit etmez.**
2. `ui/live_change_bridge_v241.py` (**yeni**): Aynı veritabanını kullanan görünür pencereler için ortak, iki saniyelik hafif Qt zamanlayıcısı ve zayıf referanslı aboneler. Salt okunur yenileme tetikler; önceden saklanmış öğrenci bilgisini başka ekrana aktarmaya çalışmaz. Gizli pencereye sorgu yüklemez. `YKS_LIVE_CHANGE_EVENTS=0` ile kapatılabilir.
3. `ui/coaching_manager.py`: Sadece **Konu Takibi sekmesi açıksa** mevcut V24.0 ortak konu kanıtı özetini yeniler; 350 ms debounce zamanlayıcısından yararlanır.
4. `ui/topic_map_dialog.py`: Görünür Konu Haritası'nda **V24.0 ortak kanıt şeridi** yeniden okunur; kartlar, düğmeler, mikro ödev oluşturma ve öğretmen işaretleri değiştirilmez.
5. `ui/student360_panel_v16.py`: Görünür Öğrenci 360° sekmesinin seçili öğrenciye ilişkin salt-okunur özeti yeniden oluşturulur.

## Değiştirilmeyenler

- `ui/homework_form.py`, `ui/odev_kontrol.py`, `db.py` — **birebir V24.0 ile aynı**. `_tik_degisti`, checkbox, renk, kilit, kaydet/geri al davranışına dokunulmaz.
- Var olan `odev`, `odev_satir`, `odev_takip`, `koc_konu_takip`, `koc_hedef` tabloları ve bütün öğrenci veri kayıtları değiştirilmez. **Migrasyon yok.**
- Ödev tamamlandı diye otomatik konu hâkimiyeti, mikro ödev veya koçluk hedefi üretilmez.

## Testler

- V24.0/V24.1 ile ilişkili **141/141 seçilmiş modül ve regresyon testi başarılı**. Bu grup öğrenci ayrımı, 360°, adaptif karar, deneme kanıtları ve konu kanıtı servislerini içerir.
- V24.1 değişiklik izleyicisi + kaynak koruma + otomatik kurucu senaryolarında **11/11 test başarılı**; toplamı önceki gruptaki 8 testle kısmen örtüşür.
- Kurucu: `clean → installed → clean` ve tekrar kurulum, kaynak sürümü uyuşmazlığı, kurulu kaynak kullanıcı tarafından değiştirilince geri alma reddi doğrulandı.
- Kaynak Python modüllerinin sözdizimi doğrulandı.
- Testler sentetik ve salt-okunur örnek SQLite dosyalarıyladır; **gerçek kullanıcı veritabanı incelenmedi**. PyQt6 bu test ortamında bulunmadığı için gerçek Mac/Windows Qt pencerelerinin yenileme davranışı ve yük altında akıcılık uçtan uca test edilmedi.

## Önemli kapsam sınırları

**Bu V24.1 tam çift yönlü olay yönlendiricisi değil.** SQLite'da değişim olduğunu algılar, hangi öğrencinin/dersin değiştiğini olaydan tespit edemez. Görünür ekranlarda sadece ilgili mevcut salt-okunur özetleri günceller. Konu Haritası'nın bütün kartlarını veya Koçluk Planı'nın bütün sekmelerini otomatik yeniden yüklemek, veri yazma servislerinden işlem kimliği olayları yayınlamak, başka cihazlarla senkron ve internet üzerinden araştırma kapsam dışıdır.

Bir sonraki aşamada güvenli yazma servislerinin commit sonrasına açık `student_id/lesson/source` olayları koymak; başarısız yazımın yayınlanmamasını test etmek; olayları tek bir performanslı merkezde sınıflandırmak önerilir. Ana formun `_tik_degisti` imza koruma uyuşmazlığı ile gerçek Mac/Windows kullanıcı kabul testleri çözülmeden canlı EXE'ye aktarılmamalı.
