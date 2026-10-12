# V23.0 — Ortak Müfredat Yönetimi / Güvenli Düzenleme

**Taban:** V22 Windows Responsive kümülatif kaynak (v3.5.16 kod zinciri).  
**Amaç:** Ders/Konu Düzenle ile Müfredat & Dersler ekranlarını tek konu düzenleme kaynağına bağlamak; eski ödev/tikleri korumak.

## Ne değişir?

- **Sistem Ayarları → Müfredat & Dersler** içinde üçüncü **Konu Düzenle** sekmesi ve **Ders/Konu Düzenle ekranını aç** düğmesi bulunur. Ana ekrandaki mevcut Ders/Konu Düzenle aynı bileşeni kullanır.
- Ders aktif/pasif ve grup ders atamaları mevcut ayarlar ekranında kalır.
- Konu listesi (genel, grup, öğrenci) mevcut editörde kalır. Yeni `services/curriculum_v23/` servisleri yeniden adlandırma, silme ve toplu kaydetme işleminde verileri korur.
- Kayıtlı bir konu hücrede doğrudan yeniden adlandırılamaz; güvenli ad değiştirme sihirbazını kullanın.
- Geçmiş ödev veya istatistikte kullanılan konu artık doğrudan silinemez. Kullanılmayan yeni konular yine silinebilir.
- Ad değiştirme **katalog ID'sini korur**, mevcut ödev ve istatistik satırlarını değiştirmez. Eski ödevin kayıt anındaki adı eski kalabilir; analizler arası alias/kimlik uyumu sonraki aşamanın işidir.
- Anahtar kelime vurgusu artık sınav sıklığı kanıtı olarak tanıtılmaz.

## Güvenli kurulum

1. Uygulamayı kapatın; çalışan **kaynak klasörünün**, SQLite veritabanının ve plan profillerinin ayrı yedeğini alın.
2. GitHub otomatik güncellemeyle kullanılan **çalışan v3.5.17** ile bu V22 tabanlı sürümü doğrudan üst üste kopyalamayın. Önce dosya farklarını birleştirin.
3. V22 test kopyasına `OdevTakip_V23_0_Mufredat_Guvenli_Yama.zip` içeriğini dosya yollarını koruyarak açın veya veri içermeyen kümülatif V23 ZIP'ini yeni klasöre açın.
4. Önce yapay/test öğrenci verileriyle şu işlemleri deneyin: yeni konu ekle, hedef güncelle, aynı kapsamda kopya ad, kullanılan konu silme engeli, kullanılmayan konu silme, ad değiştirme, öğrenci/grup kapsam ayrımı.
5. Windows 1366×768, 125/150% DPI ekranında Ders/Konu Düzenle ve Müfredat & Dersler ekranlarına erişimi kontrol edin.
6. **Ana ödev formu**: eski sarı/yeşil tikler, öğrenci değiştirme, kaydetme/kontrol, geri alma ve kapanıp tekrar açınca korunma kontrolü. Karşılanmıyorsa eski yedeğe dönün.

## Kasıtlı sınırlar

- Eski konu ve ders tabloları **migre edilmedi**. Doğrudan silme yerine kullanılan kaydın silinmesi bloke edildi; tam pasife alma/alias yönetimi ayrı geliştirmedir.
- Grup/öğrenciye özel yeni konular **ana ödev matrisine zorla eklenmedi**; çünkü eski `odev.konu_id` eşleşmesi tamamlanmadan bu işlem yanlış tik eşleşmesi üretebilir.
- Ders tanımı `ad/grup` tablosundaki hücreler görsel olarak salt okunur hale geldi. Yanıltıcı kaydetme izlenimi kaldırıldı; güvenli ders adı/grubu güncelleme sihirbazı sonraki aşamadır.
- Gerçek Windows GUI testi **yapılmadı** (bu ortamda PyQt6 yok). Sürüm v3.5.17 ile **birleştirilmiş değil**.
- Sürüm `V23.0` *ilk güvenlik/ortak ekran aşaması*; bütün müfredat entegrasyonu tamamlandı anlamına gelmez.
