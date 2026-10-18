# V24.2 – Koçluk, Konu Haritası ve Öğrenci 360° Seçili Öğrenci Değişiklik Yönlendirme Raporu

## Temel alınan kaynak

16 Ekim 2026 tarihli **V24.1 birleşik tam kaynak** (özgün kullanıcı projesi: `YKS_LGS_HomeworkManager_v2_Son_Hal(2).zip`). Bu güncelleme **V24.1 üzerine** kurulabilir. V24.0 veya daha eski sürüme doğrudan uygulamayın.

## Ne eklendi?

- `services/student_change_scope_v242.py` yeni: kalıcı salt-okunur SQLite bağlantısında commit algılandıktan sonra sadece seçili öğrenciye ait kayıtları kaynak bazında sınırlı şekilde özetleyerek kontrol eder. Öğrenci 1 üzerinde değişiklik yoksa öğrenci 2'nin kaydı onu yenilemez. Kaynak türleri: ödev, Konu Haritası, koçluk, sınav, performans, anket, öğrenci profili. Haftalık hedef ve program tablosu için `koc_plan`, eski deneme detayları için `deneme` öğrenci sahipliği üzerinden doğrulama yapılır.
- `ui/live_change_bridge_v241.py` V24.2 kapsamına genişletildi: V24.1'in `PRAGMA data_version` kontrolü korunur; görünür abonelere seçili öğrenci bağlamı filtrelemesi eklenir. Widget zayıf referansları korunur; hiçbir kullanıcı verisi diske kaydedilmez veya ağa gönderilmez.
- `ui/coaching_manager.py`, `ui/topic_map_dialog.py`, `ui/student360_panel_v16.py` yalnızca öğrenci bağlamı tanımlayan küçük bağlantılar içerir. Eski yenileme metotları değişmez.
- Değişikliğin türünü belirleyen yerel veri nesnesi mevcuttur, ama verinin **ders/konu/işlem** ayrıntısı kesin olarak saptanmamaktadır. Bu sürüm tam çift yönlü olay otobüsü değildir.

## Neler kesinlikle değiştirilmedi?

`ui/homework_form.py`, `ui/odev_kontrol.py`, `db.py`, `services/live_change_probe_v241.py`; ödev verme/silme/checkbox, kilit/renk, Konu Haritası'nın mevcut kartları, ödev ve koçluk yazma işlemleri, eski kayıtlar, veritabanı şeması. Ana ve mikro ödevler başka bir tabloda birleştirilmez. Ödevin tamamlanması otomatik olarak konu hâkimiyeti sayılmaz.

## Konu Haritası görseline ilişkin notlar

Gönderilen ekranda **LGS Matematik 2/12 konu tamamlandı** (%16, tam sayıya yuvarlanmış) ve genel **2/56** (%3) değerleri görülüyor. Bu sayılar konu işaretlerine dayalıdır; konu öğrenme/ölçülmüş sınav başarısının kesin yüzdesi değildir. Kartlardaki “Tamamlandı”, “Aktif Ödev”, “Henüz Başlanmadı” görünümü korunur. Sağdaki “ÖSYM” ifadesinin LGS seçiliyken görünmesi öğretmen açısından yanıltıcıdır; bu V24.2 altyapı güncellemesinde değiştirilmedi, sonraki kullanıcı deneyimi aşamasında ele alınmalıdır.

## Başarılı testler

- V24.2 yeni: **19/19** test (seçili öğrenci ayrımı, başka öğrenci kaynaklarının filtrelenmesi, köprü tür sınıflandırma, eski/yeni sınav ve koçluk ilişkisi, güncellemeye karşı güvenli geri dönüş, izin verilmeyen/sürümü farklı dosyayı koruma).
- Önceki seçili modül regresyonları: **174/174** test ve **4 alt test** (Öğrenci 360°, V18/V19 konu kanıtı, adaptif koç, kapsam, hedef, koçluk, öğrenci geçmişi).
- Önceki V24.1 SQLite izleme testleri: **8/8**. Bunların sayısı önceki grubun ayrı bir koşumudur.
- Toplamda **201 test çalıştırması başarılı**, grupların kapsamları kısmen örtüşebilir; tüm programın bütün senaryoları değildir.
- Gerçek Mac/Windows PyQt6 arayüz testi, dağıtılmış kurulum ve büyük kurum yük testi yapılmadı. Kaydedilmemiş/rollback işlemler için `data_version` izlemesinin kontrolü V24.1 testleri ile tekrar doğrulandı.

## Kapsam ve sonraki adım

Öğrenci seçimi değiştiğinde yeni öğrenciyle ekranı zaten mevcut uygulama değiştirir; yeni katman yalnızca açık pencerelere commit sonrası yenileme yönlendirmesi yapar. Görünmeyen ekranlar yüklenmez. Konu Haritası'nın bütün kartlarının, filtrelerinin ve seçimlerinin otomatik yeniden çizilmemesi bilinçli tasarım kararıdır. Yoğun veride (kaynak başına 500 satırı aşarsa veya şema beklenenden farklıysa) yanlış biçimde `değişiklik yok` demek yerine temkinli yenileme uygulanır.

Bu yapı veritabanını dinleyerek **hangi öğrencinin ilgili kaydı değiştiğini** karşılaştırma yoluyla belirler; SQLite commit kendi başına ders, konu ve olay türü taşımadığı için her kaydı kesin olarak yönlendiren kapsamlı olay otobüsü ancak ileride *yazma servislerinden commit sonrası açık olay yayınlama* ile kurulabilir. Bu özellikle ana ödev formuna dokunulmadan ayrıca tasarlanmalıdır. Canlı EXE'ye uygulanmadan önce ayrı test profilinde GUI performans testi önerilir.
