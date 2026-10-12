# Akıllı Haftalık Planlayıcı V4 — 1 Tıkla Etüt Uyarlama

**Kaynak:** Kullanıcının v3.5.11 kaynak projesi üzerine önceki V1–V3 planlayıcı düzeltmeleri ve bu V4 özelliği. Bu paket **Windows kurulum dosyası değildir**.

## Yoğun öğretmen için en sade akış

1. **Verilen Ödevler → Akıllı Haftalık Planlama → ⚙️ İnce Ayarlar → Etüt Oturumu & Mola** bölümüne girin.
2. Öğrencinin **kayıtlı profilini** açın. Etüt süresi (örn. 45 / 60 / 90 dk) ve mola ayarları önceki gibi çalışır.
3. Öğrencinin etütleriyle ilgili bir gözleminiz varsa sadece **Zorlandı**, **Uygundu** veya **Rahat** düğmesine dokunun. **Zorunlu bir anket veya soru formu yoktur.** Aynı günde ikinci tıklama, aynı günün gözlemini değiştirir; fazladan oy sayılmaz.
4. Sistem son **28 gündeki farklı günlere** ait gözlemleri ve veritabanındaki **geçmiş vadeli ödev tamamlama durumunu** okur. Gerçek çalışılmış dakikalar kayıtlı olmadığı için **tamamlanan ödevleri oturum süresinin kanıtı saymaz**.
5. **Yeterli ve tutarlı en az üç ayrı günlük gözlem** oluşursa sistem çok küçük bir değişiklik teklif edebilir: zorlanıyorsa **−10 dk**, rahat gidiyorsa **+5 dk**. Karışık veri veya düşük tamamlama varsa oturum **korunur**. Öğretmen **✨ Önerilen Etüt Süresini Tek Tıkla Uygula** dediğinde yalnızca o öğrenciye özel profil güncellenir.
6. Sonra **Haftalık Plan Oluştur** ile yeni oturum ayarı, molalar ve ödev kapasitesi üzerinden mevcut V3 motorunda yeni taslak oluşturulur. Öğretmen onayı olmadan eski onaylı plan değişmez.

## Güvenli sınırlar

- Gözlem yoksa veya yetersizse **mevcut süreyi korumak bilinçli davranıştır**. Sistem öğrencinin 45 dk dayanabildiğini veya ödevi tam kaç dakikada bitirdiğini uydurmaz.
- Ödev tamamlama bilgileri **bilgilendirme ve düşük başarıda süre artışına karşı temkin** amaçlıdır; tek başına oturum süresi çıkarımı yapmaz.
- Bir ders oturumunun tamamlanması, puanı, öğrencinin keyfi veya motivasyonu gibi veriler otomatik ölçülmez.
- **Ortak şablon** otomatik olarak güncellenmez. Sistemin ilk uygulamasında öğrenciye özel bir kopya oluşturulur. Aynı öğrenciye ait kişisel profilde değişiklik için yeni gözlem gerekir. Mevcut Verilen Ödevler, checkbox'lar, PDF içerikleri ve manuel planlar otomatik değiştirilmez.
- Aynı gözlem kümesinin iki kez uygulanması önlenir.
- Program, Windows'ta `%APPDATA%/YKS_LGS_OdevTakip/plan_session_feedback.json` içinde her öğrencinin **yalnızca gün + üç durumdan biri** biçiminde kısa geri bildirimini ayrı tutar. Dosya atomik kaydedilir; bozuksa üzerine yazmaz. Öğrenci adı, kişisel not, akademik sır veya tam çalışma kaydı burada tutulmaz. Mevcut ödev veritabanında *yazma* yapmaz.
- Çok öğretmenli, cihazlar arası eşzamanlı gözlem paylaşımı **bu sürümün kapsamında değildir**. Profil ve gözlem dosyaları Windows kullanıcısına özeldir. Aynı cihaz/hesap dışında veriler kendiliğinden birleşmez.

## Kurulum

- Mevcut GitHub kaynaklarını ve profil klasörünü yedekleyin.
- **Kümülatif Yama** ZIP'indeki dizinleri **kaynak projenin köküne** çıkartın; V1, V2 ve V3 planlama değişikliklerini de içerir. EXE veya `Program Files` içine doğrudan yapıştırmayın.
- Alternatif **Tam Kaynak (fontlar/kişisel dosyalar hariç)** ZIP'ini kullanırsanız önceki `fonts/` klasörünüzü koruyun.
- GitHub Actions Windows kurulum iş akışını çalıştırıp gerçek ekran üzerinde öğrenci seçimi, profil kaydetme/yeniden açma, hızlı gözlem, öneri onayı, haftalık PDF ve yeniden planlama testlerini yapın.

## Yerel otomatik test

```sh
python -m unittest tests.test_planning_constraints_v3511 tests.test_advanced_planner_v2 tests.test_sessions_and_replan_v3 tests.test_session_advisor_v4 -q
```

V1–V4 hedefli **56 bağımsız testin tamamı geçti**. Bu Linux ortamında `PyQt6` bulunmadığından Windows GUI/EXE testi yapıldığı iddia edilmez.
