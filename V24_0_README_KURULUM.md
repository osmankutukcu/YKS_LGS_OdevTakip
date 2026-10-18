# V24.0 — Koçluk Planı / Konu Haritası Ortak Kanıt Entegrasyonu

**Kaynak uyumu:** `YKS_LGS_HomeworkManager_v2_Son_Hal(2).zip` içindeki birebir kaynak sürümü. **Pilot:** Gerçek Mac/Windows PyQt6 arayüzünde henüz denenmedi.

## Güncelleme yöntemi

1. Gerçek öğrenci veritabanınızın ve proje klasörünüzün **ayrı bir yedeğini alın**.
2. `OdevTakip_V24_0_TEK_ADIM_GUVENLI_GUNCELLEME.zip` arşivini boş bir klasöre açın.
3. Terminal/komut isteminde arşivdeki `install_v24.py` dosyasına gidin.
4. Önce kaynak uygunluğunu kontrol edin:

   `python install_v24.py --project "/tam/yol/proje" --check`

5. `clean` görünüyorsa **test proje kopyanızda** yükleyin:

   `python install_v24.py --project "/tam/yol/proje" --install`

6. Geri almak için:

   `python install_v24.py --project "/tam/yol/proje" --rollback`

Windows'ta Python başlatıcısı `py` olabilir, Mac'te `python3` kullanılabilir. Kurucunun çalıştırıldığı dizin proje kökü olmak zorunda değildir; `--project` ile **tam proje kök klasörünü** verin. Bilinmeyen sürümde kurucu dosyaları değiştirmeden durur. Değişen üç mevcut dosya proje kökündeki `.v24_coach_integration_backups/original/` dizinine yedeklenir; orijinal yedeği silmeyin.

## Bu etapta gerçekten çalışanlar

- Koçluk Planı → Konu Takibi ekranında öğrenci ve seçili ders için **ana ödev**, **Konu Haritası mikro ödevi**, **öğretmen konu değerlendirmesi** ve varsa **öğretmen onaylı soru sonuçları** tek özet içinde ayrı ayrı okunur.
- Konu Haritası'nda aynı öğrenciye ait bu kaynakların ortak özeti gösterilir. Önceden bulunan ayrıntılı **Birleşik Konu Kanıtları** penceresi korunur.
- Ders ismi için yalnızca güvenle belirlenmiş TYT/AYT ad varyasyonları eşitlenir; LGS Matematik ile TYT Matematik rastgele karıştırılmaz.
- Öğrenci 360°'ın öğretmen tarafından işaretlenen konu sayacı hem eski `durum=2` hem tam hâkimiyet `durum=4` kayıtlarını okuyabilir. Bu bir öğrenme başarı oranı değildir.
- “Genel Takip (Özet)”in aslında tüm kitapları birleştirmediğini açıklayan yardım ipucu ve belirsiz sınav kanıtı etiketlerinde daha dikkatli sözcükler kullanıldı.

## Henüz yapılmayanlar

- Ödev Takip / Ödev Kontrol işlemlerini otomatik olarak koçluk işaretine veya mikro ödeve dönüştürmek **yoktur**; veri kaynakları bilinçli olarak ayrı tutulur.
- Canlı **olay otobüsü**, pencereler arası anlık yenileme, bütün modüllerde ortak `student_id` köprüsü, mevcut koçluk hedeflerini ana ödev sistemine çift yönlü yazma **bu etapta yapılmadı**.
- Gerçek Mac/Windows GUI, EXE, büyük öğrenci kümesi ve cihazlar arası senkron henüz denenmedi.
- Kaynakta ayrıca saptanan checkbox `_tik_degisti` koruma imzası sorunu bu sürümde çözülmedi. Canlıya çıkış öncesi test gerekir.

Önemli: Bu paket **yapay zekâ/otomatik internet araştırması** özelliği sunmaz; eğitim verilerini dışarı göndermez. Öğrenci kayıtları ZIP içinde yer almaz.
