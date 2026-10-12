# V14 – Kanıta Dayalı Performans Paneli / Kurulum Kılavuzu

**Taban:** Kullanıcının en son gönderdiği `OdevTakip_v3516_V13_6_Nihai_Tam_Guncel_Kaynak.zip`. Görselde v3.5.17 görünüyor; kaynak ZIP ile görselde çalışan sürümün aynı olduğu ayrıca doğrulanmalıdır.

## Güncellenenler

- `ui/performans_paneli.py`: Hesaplar artık eski günlük özetlerin güncelliğine bağlı değil. Önce öğrenci, ders/kitap/konu kayıtları üzerinde hiçbir değişiklik yapmayan analiz oluşturulur. Eski üç sekme, PDF ve Excel eylemleri korunur; yeni `🧭 Tüm Öğrenciler` sekmesi açılışta görünür.
- `services/performance_evidence_v14.py`: Kaynağın doğruluğunu, öğrenci–küme sahipliğini, teslim tarihini, görev durumunu ve örneklem büyüklüğünü denetleyerek tamamlama metrikleri oluşturur.
- `tests/test_v14_performance_evidence.py`: Sadece yapay SQLite kayıtlarıyla çalışan 23 test.

## Önemli veri kuralları

- Ödev tamamlama **sınav başarısı veya kazanım öğrenme düzeyi değildir**.
- Sonuçlar ilgili **teslim tarihi dönemi** için mevcut veritabanı durumunu gösterir. Önceki haftanın o tarihteki tarihsel durumu olarak yorumlanamaz.
- Geciken açık ödev, teslim tarihi geçmiş ve şu anda açık olan kayıttır. İptal, aktarım ve silinmiş ödevler paydaya katılmaz.
- Henüz gelmemiş teslim tarihleri, bu haftanın tamamlanma oranını düşürmez.
- `odev` ve `odev_satir` aynı kümeyi temsil ediyorsa toplanmaz; ana `odev` kaynağı kullanılır ve belirsizlik görünür. İkinci kaynak otomatik düzeltilmez veya silinmez. Sadece `odev_satir` bulunan bir küme o kaynaktan sayılabilir.
- Liderlik ve %80+ listesine **en az 5 tarihli ödev** ve belirsiz kaynak bulunmaması koşulu konur. Tek ödevle %100 gibi yanıltıcı podyumlar engellenir.
- Son 30 gün/önceki 30 gün dönemleri çakışmaz; bu karşılaştırma gerçek zaman içindeki değişimi kanıtlamaz.
- Deneme sonuçları konularla doğrulanmadan ödev tamamlama ile birleştirilmez.

## Güvenli uygulama

1. Çalışan uygulamayı kapatın; mevcut kaynak ve canlı veritabanını/yedekleri ayrı yerde koruyun.
2. Mevcut v3.5.16/V13.6 kaynak klasörünüzün **kopyasını** oluşturun.
3. Yalnızca değişen dosyalar ZIP'ini kopya proje köküne, **göreli klasör yapısını koruyarak** açın.
4. Öğretmen makinesinin PyQt6 ortamında Performans Paneli'ni açın. `🧭 Tüm Öğrenciler`, sonra diğer üç sekme, arama, Yenile, PDF, Excel ve öğrenci detayını test edin.
5. Farklı öğrenci kimlikleri, tek ödev/%100, gelecekteki teslim tarihi, aktarılmış ödev, geçmiş dönemin görünümü ve veri yetersizliği durumlarını **örnek DB** ile test edin.
6. Bu testler tamamlanmadan çalışan sürüme/güncelleme kanalına dağıtmayın.

Bu kaynak yaması yeni veritabanı tablosu veya göçü gerektirmez. Veritabanına yazmaz; mevcut üç kopuk bağlantıyı da çözmeye kalkışmaz.

**Gerçek macOS/Windows GUI kabul testi henüz çalıştırılmadı.** Bu ortamda PyQt6 yüklü değildir.
