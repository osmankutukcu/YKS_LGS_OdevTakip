# KoçPilot 360 – V3.5.83 Profesyonel PDF Atölyesi (birleşik pilot yama)

**Temel:** Orijinal v3.5.80 kaynak paketinin üzerine uygulanabilir. V3.5.81 ve V3.5.82 dosyalarını içerir; önceki yamaları ayrı yüklemek gerekmez. Zaten v3.5.82 kullanıyorsanız yine aynı relative yollarla uygulanabilir. **Bu ticari/EXE yayın paketi değildir.**

## Öğretmen açısından yapılanlar

- Mevcut **Detaylı Raporlar → Rapor Merkezi** ekranının altına **Yeni PDF Şablonları (Pilot)** eklendi. Orijinal altı yönlendirme kartı ve ana ekran/sol menü değişmedi.
- Öğrenci seçimi, 7/30/90 günlük tarih aralığı, rapor türü, canlı **metin özet önizlemesi**, açık dosya adı ile PDF kaydetme ve oluşturulan PDF'yi açma seçeneği sunuluyor.
- İki yeni, **isteğe bağlı** şablon: **Veli Bilgilendirme** (tek sayfalık özet) ve **Öğretmen Gelişim** (gösterge tanımları ve görüşme kontrol listesi ekli, sayfa sayısı içeriğe göre artabilir).
- Renkli ölçüm kartları, görsel oran çubuğu, ders bazlı özet tablosu, veri kalitesi ve somut takip gündemi içerir. Türkçe gömülü DejaVuSans fontları kullanılır.
- Veli özeti bir sayfa hedefi için en yüksek 5 dersi gösterir; geri kalan derslerin sayısı belirtilir. Öğretmen raporu 30 derse kadar listeler. Bu sınır sadece **yeni şablonun sunumudur**, veriler silinmez ve önceki rapor motoru olduğu gibi durur.

## Metrik güvenliği / anlamı

- Dönem = bitiş tarihi son 7/30/90 günde olan **ve teslim tarihi gelmiş** ödevlerin bugünkü kayıt durumuna göre tamamlanması.
- `odev` ve `odev_satir` aynı ödev kümesinde bulunuyorsa **iki tabloyu toplayarak sahte görev üretmeyiz**: `odev` birincil kabul edilir; ikincil satırlar dışlanır ve sayısı uyarıda gösterilir.
- Geçersiz veya bulunmayan bitiş tarihi, tanınmayan durum ve iptal/aktarım/silme ayrı sayılır, performans paydasını şişirmez. Veri yok = %0 **değildir**. 5'ten az görevde örneklem uyarısı var.
- “Dönemde geciken” dönem içi, “Açık geciken (tümü)” eski dönemler dahil toplam açık gecikmedir.
- Bu rakamlar **ödev takibi**, **sınav neti, gerçek kazanım düzeyi veya geçmiş döneme ait o tarihteki durum fotoğrafı değil**. Diğer modüllerden doğrulanmamış veriler kullanılmaz.
- Kayıtları okurken yalnızca SQLite `SELECT` sorguları kullanılır; veritabanı, ödev işaretleme, geri alma, haftalık plan ve koçluk kayıtları güncellenmez.

## Güvenlik

- PDF'ler **yerel** olarak, seçilen dosya konumuna oluşturulur; ağ veya bulut servisine otomatik aktarım yapılmaz.
- Kayıt sırasında aynı adda dosya varsa **üzerine yazılmaz**. Oluşturma başarısız olursa kaynak raporlar veya mevcut PDF dosyaları değiştirilmez.
- Yalnızca uygulamaya zaten erişebilen kişinin seçtiği aktif öğrenci görüntülenir; **bu pilot, yeni bir öğrenci/kurum bazlı yetkilendirme altyapısı sunmaz**. Paylaşmadan önce alıcı/veli kimliğini öğretmen doğrulamalıdır.
- ZIP paketi **öğrenci verisi, uygulama DB'si, anahtar veya PII içermez**. Örnek PDF'ler kurgusal öğrenciden üretilmiştir.

## Kurulum (TEST KOPYASI)

1. Projenin v3.5.80 **tam kaynak klasörünün ve yerel DB dosyalarının yedeğini** alın.
2. Orijinal `YKS_LGS_HomeworkManager v2` klasörünün **ayrı bir test kopyasını** oluşturun.
3. Bu ZIP içindeki `ui/`, `services/`, `tests/` altındaki dosyaları göreli yollarla test kopyasına uygulayın. `ui/report_dashboard.py`, `ui/student_detail.py` ve `ui/report_center_v3581.py` üzerinde güncelleme vardır. Korumalı ana pencereye/ödev formlarına dokunulmaz.
4. **Detaylı Raporlar → Rapor Merkezi → Yeni PDF Şablonları (Pilot)** menüsünden girin. Öğrenci/dönem/tür seçin, hesaplama özetini kontrol edin, **PDF Oluştur…** ile yerel konuma kaydedin.
5. Çok öğrenciye rapor için **mevcut Hızlı PDF ve Toplu Veli PDF** yollarını kullanmaya devam edin; yeni şablonların toplu ve WhatsApp gönderimi henüz eklenmedi.
6. Python tarafında kontrol: `python -m unittest tests.test_professional_pdf_v3583 tests.test_report_center_v3581 tests.test_report_evidence_v3582 tests.test_v14_performance_evidence tests.test_v15_performance_coaching tests.test_v35_release_gate -q`.
7. Gerçek Windows/macOS için PyQt6, ReportLab ve Türkçe font kurulumu; açık/koyu temalar, HiDPI, PDF kaydı/çıktısı, Windows paketleme ve desteklenen veritabanı sürümleri ayrıca doğrulanmalıdır.

## Test ve sınırlama

- Yapay (kişisel veri içermeyen) SQLite örneğiyle doğru dönem sayımı, mükerrer kaynak, geçersiz durum, silinmiş/aktarılan görev, sıfır veri, PDF üstüne yazma yasağı kontrol edildi.
- İki örnek PDF ReportLab ile üretildi, PyMuPDF ile metin ve sayfa sınırları denetlendi, sayfalar görsel olarak render edilip gözden geçirildi.
- Kapsamlı örnekte 20+ uzun ders adı bulunduğunda veli PDF'sinin tek sayfada kalması doğrulandı.
- **PyQt6 bu çalışma ortamında kurulu değildir. GUI, gerçek yazdırma, Windows EXE ve gerçek kurum verisi üzerinde uçtan uca sınama yapılmadı.** Bu pilotu müşterilere otomatik güncellemeyle göndermeyin.

## Sonraki etap

1. İsteğe bağlı gerçek PDF sayfa önizlemesi ve PDF çıktı galerisi.
2. Deneme, hedef, Öğrenci 360, Adaptif Koçluk, haftalık plan gibi modüller için doğrulanmış ayrı veri bağlayıcıları; mevcut hesapları koruyarak açık kaynak etiketiyle sunma.
3. Kurum/şube raporu; izinlere dayalı toplu çıktı, dosya adlandırma, tekrar deneme ve çıktı günlüğü.
4. Sınıflandırma ölçütlerinin merkezî ve sürümlü hale getirilmesi; gerçek kullanıcı kabul testi.
