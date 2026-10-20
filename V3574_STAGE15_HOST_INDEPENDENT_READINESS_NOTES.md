# KoçPilot 360 — v3.5.74 / Sunucu Bağımsız Anket Altyapısı Hazırlığı

## Amaç
Bulut sağlayıcısını (Cloudflare, Railway, özel VPS vb.) şimdi SEÇMEDEN,
mevcut v3.5.73 anket HTTP sözleşmesini ve yerel programı koruyarak dağıtım
öncesi güvenli ayar/uygunluk denetimi hazırlamak. Sunucuya dağıtım YAPILMADI.

## Eklenenler
- `services/feedback_deployment_v3574.py`: Sağlayıcı adı istemeyen, ağ bağlantısı
  kurmayan, yalnızca kurulum durumunu okuyan kontrol katmanı. Windows ve röle
  ayarlarını ayrı değerlendirir; gizli anahtar/token/öğrenci kimliğini raporlamaz.
  Varsayılan sonuç `disabled`; eksik kurulum `incomplete`; canlı ortam hiçbir
  zaman çevrim dışı kontrolden `live_verified=true` sonucu alamaz.
- `tools/feedback_preflight_v3574.py`: `--role desktop/server/contract` ve `--json`
  ile tanısal rapor. `--strict` yalnızca yapılandırma kabulü için kullanılır,
  gerçek kullanıcı kabul testlerinin yerini alamaz.
- `deploy/feedback/hosting-neutral.example.json`: Sunucu sağlayıcısından bağımsız
  zorunlu kapasite/özellik listesi. AÇIKÇA `hosting_provider: null`.
- `deploy/feedback/ENV_TEMPLATE.txt`: Windows ve FastAPI sunucusunun gerekli
  ortam ayarlarını, sırların gerçek değerlerini göstermeden belgeleyen örnek.
- `tests/test_feedback_deployment_v3574.py`: Çevrim dışı ve sırsız testler.

## Mevcut yetenekler
- **Mevcut** anket rölesi FastAPI + kalıcı SQLite içerir ve her uygun HTTPS
  barındırıcıda test edilerek çalıştırılabilir; sağlayıcı seçimi gerektirmez.
- D1/Workers ya da başka sunucusuz platformlar için uyumlu uygulama **henüz
  yazılmış değildir**. Bu belge/şablon, orada kodun çalışacağını iddia etmez.
- Ödev durumları, Hızlı Teşhis ve haftalık PDF kaydı buluta taşınmaz.
- Öğrenci veya veli cevapları canlı bir akademik kanıt/teşhis değildir.
- Güncel ağ geçidi çevrim dışı varsayılanıyla kapalıdır.

## Kaynak koruması
Bu aşamada önceki sürümdeki kaynak dosyalarının **hiçbiri değiştirilmedi**.
Yalnızca yeni bağımsız dosyalar eklendi. Özellikle `web_api/main.py`,
`ui/homework_form.py`, `ui/odev_kontrol.py`, haftalık planlayıcı/PDF motoru,
`services/feedback_relay_v3573.py` ve `services/homework_feedback_cloud_bridge_v3573.py`
birebir korunur. Bu sebeple anketlerin güncel çalışma davranışları değişmez.

## Test özeti
- Yeni hazırlık kontrolleri: 10 test başarılı.
- Seçilmiş mevcut anket, akademik ve çekirdek regresyonuyla birlikte:
  110 başarılı, 5 atlandı, 10 alt test başarılı.
- Testler sentetik ve çevrim dışı ortamda gerçekleştirildi. Gerçek PyQt6/Windows
  uygulaması, HTTPS dağıtımı, EXE ve telefon testi yapılmadı.

## Yarım kalanlar ve önerilen sıra
1. **Kararlı sürüm kabulü**: Gerçek Windows/EXE üzerinde iki temel formun
   tüm tıklama, checkbox, kilit, geri alma, öğrenci değiştirme davranışlarını
   önceki kararlı sürümle karşılaştır; checkbox gecikmesini ölç.
2. **Plan/PDF kontrolü**: Kayıtlı rutin profilini ve mevcut verilen ödevleri
   kullanarak haftalık planı üret; eski PDF ile sayfa, çizim ve görev kapsamını
   görsel ve sayısal karşılaştır. Çekirdeği değiştirme.
3. **Koçluk kalite kontrolü**: Öğrenme kanıtı yetersizliği, farklı öğrenci,
   yanlış konu, öz değerlendirme ve müdahale önerileri için gerçekçi sentetik
   veri senaryolarıyla tek öneri tutarlılığını doğrula.
4. **Anket canlıya hazırlık (SONRA)**: Sunucu sağlayıcısı seçimi, veri bölgesi,
   HTTPS, rate limiting, sürekli saklama, yedek, KVKK, gerçek öğretmen–telefon
   senkronu, kimlik güvencesi, isteğe bağlı WhatsApp gönderimi.
5. **Yayın kapısı**: Lisans, Windows kurulumu, GitHub otomatik güncelleme,
   geri dönüş, sürüm numarası ve yükseltme senaryoları kontrol edildikten sonra
   kontrollü dağıtım.

> **PİLOT**: v3.5.74 bir kurulum/denetim altyapısı paketidir. Gerçek bulut hesabı,
> alan adı, canlı HTTPS, gerçek cihaz kabulü veya müşteriye dağıtım yapılmadı.
