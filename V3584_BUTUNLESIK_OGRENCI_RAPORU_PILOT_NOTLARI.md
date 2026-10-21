# KoçPilot 360 – V3.5.84 Bütünleşik Öğrenci Raporu (Birleşik Pilot Yaması)

## Bu paketin durumu
- **Test için kaynak kodu yamasıdır; kurulum EXE'si, müşteri güncellemesi veya üretime onay değildir.**
- Orijinal `YKS_LGS_HomeworkManager_v3.5.80_KocPilot360_Son_Surum.zip` kaynak klasörüne göre hazırlanmıştır. Önceki V3.5.81, V3.5.82 ve V3.5.83 güncellemeleri de bu ZIP'in içindedir. Önceki yamaları ayrıca kurmayın.
- Paket, kişisel öğrenci verileri, `.db` dosyaları, parola, API anahtarı, örnek özel öğrenci raporu veya uygulama derlemesi içermez.

## Kullanıcı için değişiklikler
1. **Detaylı Raporlar → Rapor Merkezi → Yeni PDF Şablonları (Pilot)** yolunda üçüncü bir seçenek: **Bütünleşik Öğrenci 360 (Pilot)**.
2. Öğrenci, 7/30/90 günlük **ödev teslim dönemi** ve rapor türünü seçme. PDF öncesi **salt metin veri özeti** ve hatalı/eksik veri açıklaması.
3. PDF: (a) öğrenci kimliği ve ödev göstergeleri, (b) ilk 6 dersin tamamlanma çubuğu, (c) doğrulanabilir hedef ve deneme, (d) haftanın koçluk planı, konu takibi, öneriler ve veri-kalitesi uyarıları.
4. Kaynak görünürlüğü: **kayıt**, **eksik kayıt** ve **doğrulanamadı** durumları farklı gösterilir. Öğrenci hedefi öğretmen kaydıdır; deneme net değişimi öğrenme/yerleşme garantisi değildir.
5. Rapor seçimi/öğrenci değişince **önceki PDF'yi Aç** kısayolu sıfırlanır; yeni seçim ile eski öğrencinin dosyasına yönlendirme yapılmaz.
6. Mevcut tekli/toplu Hızlı PDF, Performans Paneli ve Detaylı Raporlar akışları değişmez. Bu yeni modülde **toplu bütünleşik PDF / otomatik WhatsApp gönderimi yoktur**.

## Veri bütünlüğü ve teknik sınırlar
- Okuma, uygulamadaki mevcut V14/V15, Öğrenci 360 V16, Hedef Analizi V24 ve yeni V3.5.83 ödev kanıt okuyucularını yeniden kullanır. Giriş yalnızca `ogrenci.id` ile eşleştirilir; isim benzerliğinden öğrenci seçilmez.
- Ödevler için `odev` ve `odev_satir` çift sayımı önlenir. Teslim tarihi belirsiz/gelecekte olan ve silinmiş/aktarılmış görevler dönem oranına girmez; ölçüm **mevcut durumun teslim tarihli dönem içindeki görünümü**, tarihsel anlık durum kaydı değil.
- Deneme karşılaştırması yalnızca mevcut V15 okuyucusunun sınırlı koşullarında yapılır. Kayıt şeması yoksa “öğrencinin denemesi yok” denmez, “bu kaynak doğrulanamadı” denir.
- Koçluk planı için yalnızca rapor tarihini kapsayan kayıtlı plan sayılır; konunun işaretlenmesi kazanım başarısı sayılmaz.
- Öğrencinin haftalık rutin profili ve haftalık plan PDF'si **henüz otomatik bağlanmıyor**; farklı öğrenci programını yanlışlıkla rapora katmamak için bağlantı ertelendi.
- Bu pilot mevcut öğrenci/kurum erişim mekanizmasını kullanır; yeni veri yetkilendirmesi sağlamaz. PDF paylaşmadan önce doğru alıcı ve izinler kontrol edilmelidir.
- PDF yalnızca kullanıcının seçtiği **yerel dosyaya** oluşturulur, mevcut dosyanın üzerine yazılmaz. Uygulama arka planda veri yazmaz veya ağ üzerinden göndermez.
- PDF'nin iki sayfa olması **normal örnek veri** içindir; çok uzun alanlar veya ek uyarılar olduğunda sayfa sayısı artabilir. İlk sayfada 6 dersin barları gösterilir; bütün dersler için mevcut Öğretmen Gelişim PDF raporuna yönlendirir.

## Kurulum – Yalnızca test kopyası
1. Tam orijinal kaynak klasörünün ve **öğrenci veritabanının ayrı bir yedeğini** alın.
2. Orijinal kaynakla **ayrı bir TEST klasörü** açın. İlk önce mevcut v3.5.80 tabanından başlayın; bu ZIP zaten önceki üç yamayı içerir.
3. ZIP içindeki `ui/`, `services/`, `tests/` dosyalarını ve ilgili notları, test klasörüne **göreli yollarını koruyarak** uygulayın. Ödev, Kontrol, Ana Pencere, DB veya planlayıcı dosyalarını yama ile değiştirmeyin.
4. Python bağımlılıklarının (özellikle **PyQt6**, **ReportLab**, Türkçe gömülü DejaVu fontları) kurulumda varlığını kontrol edin.
5. Uygulamayı test modunda açın; **Detaylı Raporlar → Rapor Merkezi → Yeni PDF Şablonları (Pilot) → Bütünleşik Öğrenci 360** yolunu deneyin.
6. En az: veri yok, tek görev, 5+ görev, 2+ ders, deneme kaydı yok, hedef kaydı yok, öğrenci geçişi, mevcut dosya adı, açık/koyu tema, farklı ekran ölçeği, Windows PDF yazdırma ve macOS PDF açma durumlarını elle doğrulayın.
7. Müşterilere dağıtmak için ayrıca Windows EXE/PyInstaller paketleme, gerçek kullanıcı yetkileri, kaynak bağımlılıkları, gizlilik ve kabul testleri gerekir.

## Doğrulama
- Test: `python -m unittest tests.test_integrated_report_v3584 tests.test_professional_pdf_v3583 tests.test_report_center_v3581 tests.test_report_evidence_v3582 tests.test_v14_performance_evidence tests.test_v15_performance_coaching tests.test_v35_release_gate -q`
- **85 ilgili otomatik test geçti**. Örnek SQLite verileri kullanıldı, gerçek öğrenci veritabanı kullanılmadı.
- PDF fiziksel olarak üretildi, Türkçe karakterler/grafikler görsel olarak kontrol edildi; metin sınırı, iki sayfalık temel çıktı, uzun ders isimli stres çıktı, üzerine yazmama test edildi.
- `tests/v42_protected_hashes.json` içindeki 10 korumalı dosya, orijinal v3.5.80 ZIP'inden çıkarılan dosyalarla SHA-256 düzeyinde karşılaştırıldı: **birebir aynı**.
- **PyQt6 bu çalışma ortamında kurulu olmadığından gerçek etkileşimli GUI ve EXE testleri yapılmadı.** Kaynak dosya sözdizimleri/testleri geçti; bu sonuç canlı yazıcı ya da dağıtım garantisi değildir.

## Sonraki çalışmalar (bu pakette yok)
- Öğrenci bazlı haftalık rutin profilini güvenilir benzersiz anahtar ile bağlama.
- İzinli, şube/kurum filtreli toplu PDF, veliye güvenli paylaşım ve takip defteri.
- Gerçek arayüz önizlemesi, tarihsel durum görüntüsü, hız testleri ve tüm rapor ekranlarında ortak metrik kataloğu.
