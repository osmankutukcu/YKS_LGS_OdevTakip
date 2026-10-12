# Akıllı Haftalık Planlayıcı – İnce Ayarlar V2

Bu paket, kullanıcının sağladığı **YKS_LGS_OdevTakip_v3.5.11_Kaynak_Kod.zip** temel alınarak hazırlanmış, bir önceki planlayıcı onarımını da içeren **kümülatif kaynak kod güncellemesidir**.

## Yeni kullanım akışı

1. Verilen Ödevler tablosundan ilgili öğrenci için Akıllı Haftalık Planlayıcı penceresini açın.
2. Zaman & Okul sekmesinde okul/kurs/özel ders ve sabit rutinleri belirleyin.
3. Hedef & Tempo sekmesinde genel günlük üst sınırı, uyanma/yatış aralığını ve isteğe bağlı dinlenme gününü girin.
4. **⚙️ İnce Ayarlar** sekmesindeki anahtarı açın. Yalnızca farklı saatleri olan günlerin **Özel** kutusunu etkinleştirin.
5. Gün bazında uyanma, yatış, **birinci çalışma dilimi**, günlük maksimum çalışma süresini belirleyin. Gerekirse **ikinci çalışma dilimi** ekleyin.
6. Aynı düzeni tekrar kullanmak için **Gün Ayarlarını Kopyala** ile seçili günü hafta içine, hafta sonuna veya tüm haftaya dağıtın.
7. **Profili Kaydet** → gerekiyorsa **Öğrenciye Ata** seçeneğini kullanın. Sonraki açılışlarda öğrenci ID'si üzerinden ilişkilendirilen profil seçilir.
8. **Haftalık Planı Oluştur & Önizle** ile verilen ödevleri gerçek boş zamanlara dağıtın. Zaman yetmezse yerleşmeyen ödevleri kontrol edin.

### Örnek

* Pazartesi: uyanma 07:00, yatış 22:00; birinci çalışma 17:30–19:00, ikinci çalışma 20:00–21:30, maksimum 120 dk.
* Cumartesi: uyanma 09:00, yatış 23:00; çalışma 10:00–12:00 ve 17:00–19:00, maksimum 180 dk.
* Salı: gelişmiş gün özelleştirmesi açılmamışsa genel ayarlar kullanılır.

**Notlar:** Saat olarak tanımlanmayan serbest notlar otomatik bir meşguliyet olarak uygulanmaz; gerçek okul/kurs/antrenman saatlerini Sabit Rutinler'e girin. Çalışma dilimleri aynı gün içinde, uyanma ve yatış arasında ve çakışmasız olmalıdır. Gelişmiş ayar anahtarı kapalıyken günlere özel ayarlar dosyada korunur fakat planlamada uygulanmaz.

## Güncelleme

**Önce:** GitHub proje klasörünü ve kullanıcı profillerini yedekleyin. Daha önce güncelleme uygulamamış olsanız da **Kümülatif Yama ZIP** önceki onarımı da içerir. ZIP dosyasının klasör yapısını koruyarak mevcut *kaynak* proje içine açın. Daha sonra Windows kurulumunu kendi GitHub Actions/derleme sürecinizle yeniden üretin. ZIP dosyasını kurulu EXE içine kopyalamayın.

Kullanıcı profilleri Windows'ta `%APPDATA%/YKS_LGS_OdevTakip/plan_profiles.json` altında saklanır; mevcut `plan_profiles.json` dosyasını silmeyin. Uygulama kullanıcıya özel kayıtları eski biçimden okuyabilir. Farklı Windows bilgisayarları arasında bulut senkronizasyonu bu sürümün kapsamı dışındadır.

**Tam kaynak ZIP** üzerinden kurulum üretiyorsanız daha önceki kaynak projesinde mevcut olan `fonts/` klasörünü **aynen koruyun**. Dağıtım ZIP'ine yazı tipi dosyaları eklenmemiştir.

## Doğrulama

`python -m pytest -q tests/test_planning_constraints_v3511.py tests/test_advanced_planner_v2.py`

Otomatik testler, kaynak derlemesi ve saf planlama motoru doğrulandı. Bu Linux ortamında PyQt6 kurulumu, Windows EXE/kurulum derlemesi veya gerçek kullanıcı tıklamaları uçtan uca test edilemedi. Windows kabul testi zorunludur.
