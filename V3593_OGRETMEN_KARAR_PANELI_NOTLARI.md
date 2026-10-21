# KoçPilot 360 – V3.5.93 Öğretmen Karar Paneli (PİLOT)

## Amaç ve önceki sürümden farkı

V3.5.92'de öğretmen için kontrollü öneriler yalnızca bütünleşik öğrenci PDF raporunda vardı. Yeni sürümde **Rapor Merkezi'nin üst kısmına isteğe bağlı “Öğretmen Karar Paneli”** düğmesi eklendi. Raporun altı mevcut kartı, profesyonel PDF ve toplu PDF yolları kaldırılmadı.

Kullanıcı öğrenci adını veya numarasını arayıp **açıkça öğrenciyi seçer**, ardından son 30, 90 ya da 180 günlük **deneme** dönemini seçer. Ekran ders bazlı doğrulanmış net ve soru sayısını, öğretmenin konu işaretlerini, veri uyarılarını ve V3592'nin en fazla üç kontrollü adımını gösterir. Konu işaretlerinde tarih filtresi bulunmaz; bu sınır ekranda belirtilir.

## Neyi neden, nasıl değiştirdik?

| Neden | Nasıl | Kazanım |
|---|---|---|
| PDF oluşturma gerekmeden öğretmen kararı | `ui/teacher_decision_dialog_v3593.py` salt-okunur ekranı | Öğrencinin mevcut kanıtına hızla erişim |
| Öğrenci bilgilerinin karışması riski | Numerik öğrenci ID'si, seçim araması değişince önizleme temizliği, seçim eşleştirmesi | Yanlış öğrenciye ait eski yorum gösterilmez |
| Belirsiz verilerden yanlış kesin çıkarım | `services/report_decision_view_v3593.py` yalnızca V3591'nin yapılandırılmış kanıtını ve V3592'nin önerilerini biçimlendirir | Net/konu takip kayıtları ayrı ve kaynağı belli kalır |
| Mevcut altı rota bozulmasın | `ui/report_center_v3581.py` içine **tek ek düğme ve modal bağlantı**; altı rota aynen korunur | Kullanıcıların alıştığı raporlara erişim kaybolmaz |
| Qt arayüz testi sessizce atlanmasın | Windows CI'ya PyQt6 bağımlılıkları kurulduktan sonra zorunlu Qt regresyon adımı | Gerçek Windows test altyapısında UI kabulü zorunlu tutulur |

## Uygulama sınırları

- Yeni panelde `INSERT`, `UPDATE`, `DELETE`, `commit`, dosya yazma, WhatsApp, internet veya otomatik görev/plan değiştirme yoktur.
- Net, soru sayısı doğrulanmışsa gösterilir; aynı deneme/ders için mükerrer ölçüm varsa kesin net gösterilmez.
- Öğretmen konu işaretleri, öğrenme veya kazanım başarısı kanıtı **değildir**.
- Öğrenci kayıtları başka bir servise gönderilmez, ağ çağrısı yapılmaz.
- Eski Öğrenci Detayı, Detaylı Raporlar, Performans Paneli, Hızlı PDF, Haftalık Planlayıcı, Ödev Takip, Ödev Kontrol korunur.
- Korunan 10 çekirdek kaynağın içerikleri bu sürümde değiştirilmedi.

## Dosyalar

- Yeni: `services/report_decision_view_v3593.py`, `ui/teacher_decision_dialog_v3593.py`, `tests/test_teacher_decision_v3593.py`.
- Bağlantı: `ui/report_center_v3581.py`.
- Sürüm ve CI: `version.py`, `version.json`, `setup.iss`, `.github/workflows/build_installer.yml`, `README.md`.

## Testler ve kullanım onayı

- Kaynak testleri: 115 geçti, 95 alt kontrol geçti, 2 gerçek Qt testi **PyQt6 kurulu olmadığı için atlandı**.
- `python -m tools.v3588_unified_preflight`: geçti; 16 zorunlu tek-kök kaynak ve pilot kanal.
- `python -m tools.validate_release`: geçti, 3.5.93 sürüm tutarlı.
- `python tools/v3527_core_guard.py`: geçti; iki eski mükerrer metot tanımı uyarısı V3.5.92'den devralındı.
- `--check-tracked` Git deposu olmayan yerel ZIP açılımında çalıştırılamadı; gerçek CI Git deposunda zorunlu.
- **Gerçek GUI, Windows EXE, macOS ve yazdırma testi burada yapılamadı.** Bu pilot müşteri otomatik güncellemesi için onaylı değildir.

## Kurulum

- Tam kaynak: V3.5.93 pilot ZIP mevcut V3.5.92'yi kapsar, geçmiş veri içermez.
- Küçük yama: Yalnızca doğrulanmış V3.5.92 kaynak kökünün üzerine, tam yedek sonrası ve test klasöründe.
- PDF yazı tipleri teslim paketinde dağıtılmaz; mevcut güvenli derleme ortamındaki fontlarla devam edilir.
