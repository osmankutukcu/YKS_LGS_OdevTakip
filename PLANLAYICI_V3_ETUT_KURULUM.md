# Akıllı Haftalık Planlayıcı V3 – Kişisel Etüt & Onaylı Yeniden Planlama

**Temel:** Kullanıcının ilettiği v3.5.11 kaynak kodu + önceki V2 İnce Ayarlar. Bu paket, Windows uygulaması değil, kaynak güncellemesidir.

## Etüt oturumu nasıl ayarlanır?

1. **Verilen Ödevler** üzerinden **Akıllı Haftalık Planlama** ekranını açın.
2. **⚙️ İnce Ayarlar** sekmesinde **Her kesintisiz etüt için üst süre belirle** kutusunu işaretleyin. *Günlere özel ince ayarlar* anahtarını ayrıca açmak gerekmez.
3. **Azami tek oturum** için 15–180 dakika (örneğin 45, 60 veya 90), **oturumlar arası mola** için 0–60 dakika belirleyin.
4. **Uzun ödevleri oturumlara otomatik böl** açık olursa 120 dk'lık ödev 45 + 45 + 30 dakika olarak parçalara ayrılabilir. Sığmayan parça ayrıca raporlanır. Bölünemez işaretli ödev zorla bölünmez.
5. **Profili Kaydet** / **Öğrenciye Ata**. Seçilen öğrencinin profili bir sonraki kullanımda otomatik çağrılır.
6. **Haftalık Planı Oluştur & Önizle** ile kısıtları ve PDF saatlerini kontrol edin.

Öğrencinin günlük üst sınırı gerçek **çalışma süresi**dir; molalar sınırın içine sayılmaz, fakat takvimde zaman kaplar. Örneğin 4 x 45 dk çalışma ve 3 x 10 dk mola, takvimde toplam 210 dk yer ister. Günlük üst sınır 180 dk olabilir fakat müsaitlik penceresi 180 dk ise dört oturum o güne sığmaz. Sığmayan işler başka uygun günlere kaydırılır veya yerleşmeyenler listesine düşer.

## Güvenli yeniden planlama

Haftalık plan **yeniden oluşturulup önizlenirken**, yeni taslak otomatik olarak önceki **öğretmen onaylı** taslakla karşılaştırılır. Ödevler, rutinler veya saatler değişmişse özet gösterilir. Önizleme kapandıktan sonra **öğretmen Evet derse** yeni taslak sonraki karşılaştırma için saklanır. **Hayır** durumunda önceki onay aynen korunur. Bu özellik Verilen Ödevler tablosunu, öğrenci ödev durumlarını veya ayrı manuel Haftalık Plan düzenleyicisini **değiştirmez**. Yeni taslak kendiliğinden öğrencinin gerçek ödev kayıtlarına yazılmaz.

**Sınır:** Tam otomatik, ödevdeki her işaretlemeye anında tepki veren arka plan izleme değildir; karşılaştırma **Akıllı Takvim PDF Önizlemesi açılırken** çalışır. Henüz öğretmen elle sabitlediği bir oturumu akıllı PDF'ye taşımayı sağlayan kilitli-oturum arayüzü yoktur. Diğer uygulama modüllerindeki haftalık planlar dokunulmadan bırakılmıştır.

## Güncelleme adımları

- Önce kaynak GitHub klasörünüzü ve Windows'ta `%APPDATA%/YKS_LGS_OdevTakip/` altındaki profilleri yedekleyin.
- **Kümülatif Yama** önceki V1/V2 onarımlarını da içerir; ZIP içindeki klasörleri **kaynak projenizin kök dizininde** birleştirin. EXE veya Program Files içine kopyalamayın.
- Windows üzerinde kurulum için kendi GitHub Actions/derleme akışınızı çalıştırın. **Tam Kaynak (Fontsuz)** dosyasını seçerseniz önceki proje `fonts/` klasörünüzü koruyun.
- Önceki profil JSON dosyaları silinmez. Yeni alanlar kaydedilen profilin içinde bulunur. Onaylı taslaklar kullanıcıya özel veri klasöründe ayrı `approved_weekly_plan_snapshots.json` dosyasında saklanır.
- Gerçek Windows formu test edilmedi: Profil Kaydet → Kapat → Aç → Profili Yükle → 45/90 dk ayarı → 120 dk ödev → Önizle → Taslak farkını gör → Hayır/Evet → yeniden aç aşamalarını Windows'ta doğrulayın.

## Test

```bash
python -m unittest tests.test_planning_constraints_v3511 tests.test_advanced_planner_v2 tests.test_sessions_and_replan_v3 -q
```

38 bağımsız hedeflenmiş test başarılı; ayrıca tüm kaynak için sözdizimi derlemesi yapıldı. Genel test keşfi bu Linux ortamında Qt bağımlılığı bulunmaması ve eski bir testin geçici Qt stublarıyla çakışması nedeniyle tamamlanamadı. Windows GUI ve EXE kabul testi ayrı gereklidir.
