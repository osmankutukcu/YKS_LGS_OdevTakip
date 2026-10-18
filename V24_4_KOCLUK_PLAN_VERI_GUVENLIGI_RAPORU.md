# V24.4 — Koçluk Planı Veri Güvenliği ve Test Raporu

**Temel:** V24.3 birleşik kaynak. **Tür:** Geri alınabilir kaynak yaması. **Kapsam:** `ui/coaching_manager.py` ile yeni `services/coaching_safety_v244.py`. `homework_form.py`, `odev_kontrol.py`, `db.py` değişmedi.

## Değişiklikler

1. Haftalık planın yeniden oluşturulması artık `koc_hedef` satırlarını `DELETE` ile silmiyor. Aynı dersin kalıcı ID, çözülen soru, hedef/çalışılan saat ve durum alanları korunuyor; sadece seçilmiş hedef soru güncelleniyor. Yeni ders ekleniyor. Öğretmenin yeniden seçmediği ders otomatik silinmiyor. Çift hedef veya çift haftalık plan tespitinde **işlem durur**, sessiz veri birleştirme yapılmaz.
2. Hedef ilerleme düzenlemesi `koc_hedef.id + plan_id + öğrenci sahipliği` ile yapılıyor. Tüm sayılar **yazmadan önce** doğrulanıyor; hatalı/negatif/sonsuz değerlerde hiçbir satır güncellenmiyor. Ekranın açılışındaki değerler saklanıyor; başka bir işlem değeri değiştirmişse otomatik üzerine yazılmıyor. Yarım kayıt engelleniyor. Yeniden planlama öncesinde kaydedilmemiş ilerleme varsa öğretmene önce kaydetmesi söyleniyor.
3. Görüşme notları için yalnızca ilk **not kaydetme** işleminde `koc_gorusme_gecmis_v244` adlı bağımsız eklemeli arşiv tablosu oluşturuluyor. Haftalık `koc_plan.notlar` mevcut okuyucular için en son notu tutuyor; eski notlar yeni arşivde korunuyor. Öğrenci/hafta kimliği SQL ile doğrulanıyor. Eski format görüşmeler de arşivde gösteriliyor.
4. Otomatik koçluk değerlendirmesi **"taslak"** olarak işaretlendi. Gerçekleşmeyen görüşme, doğrulanmamış motivasyon kaybı veya uygulanmamış eylem gerçekleşmiş gibi ileri sürülmüyor.
5. Haftalık ders programı, anketler, konu işaretleri, 360°, Koça Sor, Ödev Takip ve Ödev Kontrol ana kayıtları değiştirilmedi.

## Risk ve sınırlar

- **Veritabanı notu:** Güncelleme kurucusu veritabanı dosyasına dokunmaz. Ancak Koçluk Planı'nda görüşme notu kaydedildiğinde yeni geçmiş tablosu **mevcut aktif veritabanında** oluşturulur. Kaynak dosyalarını geri almak, bu veritabanı tablosunu silmez; böylece görüşme geçmişi kaybolmaz. Her hâlükârda kurulumdan önce veritabanı yedeği alınmalıdır.
- Var olan aynı öğrenci/hafta çift plan kayıtları **otomatik birleştirilmez**; öğretmen verisi üzerinde riskli temizlik yapılmaz.
- Seçilmeyen dersler **silinmez**, ilerlemesi ve bağlı raporları korunur. İleride onaylı güvenli arşivleme akışı ayrıca eklenebilir.
- Çalışma saatleri ve soru sayıları yine öğretmen girişi temellidir; deneme sonucu/ana ödev checkbox verileriyle otomatik aynılaştırılmaz.
- PyQt6 ile gerçek Mac/Windows arayüz tıklamaları ve gerçek kullanıcı DB stres testi henüz çalıştırılmadı. Tam canlı yayın onayı değildir.

## Test kapsamı

- 44 servis/güvenlik testi: hedef değişikliğinde ilerleme koruma; ikinci öğrenci; ders ve plan tekrarı; hata ve negatif sayılar; arşiv geçmişi/legacy; veri sıralaması; rollback ve ana ödev tablosuna dokunmama.
- Seçilmiş V24.0–V24.3/Öğrenci 360°/Adaptif Koç regresyon testleri yeniden çalıştırıldı.
- **44/44 yeni veri güvenliği testi** geçti. **108/108 seçilmiş önceki modül regresyon testi** geçti; toplam **152/152** (yineleme sayımı).
- **Tek adım kurulum/geri alma:** temiz V24.3, ikinci kurulumun reddi, yedeklerle birebir geri alma, bilinmeyen kaynağı reddetme senaryoları başarılı. `homework_form.py`, `odev_kontrol.py`, `db.py` SHA-256 değerleri değişmedi.
- `ui/coaching_manager.py` ve yeni servis Python sözdizimi doğrulamasından geçti. PyQt6 gerçek görsel etkileşim testi yapılmadı.
