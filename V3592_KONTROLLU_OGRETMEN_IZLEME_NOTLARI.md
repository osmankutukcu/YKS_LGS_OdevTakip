# KoçPilot 360 V3.5.92 – Kontrollü Ölçüm ve Öğretmen Rehberi (PİLOT)

## Önce / neden / nasıl / kullanıcıya faydası

| Önce | Risk | Yapılan | Fayda |
|---|---|---|---|
| Deneme netleri ve öğretmen konu işaretleri yan yana görünüyordu. | Öğretmen hangi eylemle başlaması gerektiğini ayrıca belirliyordu. | Yeni salt-okunur `services/report_intervention_plan_v3592.py` üç adımı geçmeyen ölçüm/inceleme rehberi hazırlar. | Öğretmen veri kontrolü, soru incelemesi ve yeniden ölçüm sırasını görür. |
| Akademik özet metin biçimindeydi. | Metinden sayı ve ders tahmin ederek öneri üretmek kimlik/ders karışması riski taşır. | `CourseMeasurement` adlı sınırlı yapılandırılmış kanıt V3591 okuyucusuna eklendi; eskilerin `value/status/warnings` alanları korunur. | Aynı öğrenci ve kesin ders kodu kullanılır. |
| Mükerrer ölçüm, kaynak yokluğu veya çelişkili işaret olabilir. | Belirsiz veriden hatalı öğrenci teşhisi çıkabilir. | Önce `Önce veriyi doğrula` önerisi üretilir; mükerrer netler tavsiye gerekçesi yapılmaz. | Öğrenci hakkında yanlış olumsuz hüküm azaltılır. |
| PDF ikinci sayfasında koçluk önerileri bulunuyordu. | Yeni uzun metin ikinci sayfayı taşırabilir. | Bütünleşik PDF'ye kısa, kaynak ve sınırları belirtilmiş bölüm eklendi; ayrıntılar ayrı saf fonksiyondadır. | Okunabilir iki sayfalık şablon korunur (sentetik örnek). |

## Dosyalar

- Yeni: `services/report_intervention_plan_v3592.py`
- Güncellendi: `services/report_academic_bridge_v3591.py`, `services/integrated_report_v3584.py`
- Yeni test: `tests/test_report_intervention_plan_v3592.py`
- Sürüm/pilot: `version.py`, `version.json`, `setup.iss`, `.github/workflows/build_installer.yml`, `README.md`

## Güvenli yorum ilkeleri

- Tek bir ders neti **konu/kazanım eksikliğinin kanıtı değildir**. Bir öğrenciye otomatik başarısızlık veya zekâ değerlendirmesi yapılmaz.
- Tarihli deneme aynı öğrenci ID'si ve kesin sınav/ders türü üzerinden okunur. Mükerrer ölçümde net birleştirilmez.
- Öğretmen işaretleri gerçek soru bazlı kazanım ölçümü yerine geçmez.
- Kısa konu yoklaması ve yaklaşık bir hafta sonra aynı tür/kapsamda yeniden ölçüm öneridir; **otomatik ödev, plan, bildirim veya kayıt oluşturulmaz**.
- Ağ çağrısı yapılmaz, kişisel öğrenci kaydı dışarı aktarılmaz.
- `ui/homework_form.py`, `ui/odev_kontrol.py`, `main_window.py`, `db.py`, `ui/reports.py` ve diğer korumalı dosyalar değişmez.

## Yapılan teknik testler

- Sentetik SQLite ile kaynak güvenilirliği, çapraz öğrenci sızıntısı, aynı sınav/ders için mükerrer satır, eksik konu şeması, belirsiz ders, öğretmen işareti çelişkisi ve `PRAGMA query_only` kontrolü.
- Bütünleşik PDF üretimi ve sayfa taşması kontrolü; örnek iki A4 sayfası.
- Kaynak ve pilot yayın ön denetimleri; gerçek Windows/macOS GUI, yazıcı, EXE ve GitHub otomatik güncelleme kabulü **yapılmadı**.

## Kullanım

Öğrenci → Rapor Merkezi → Yeni PDF Şablonları → Bütünleşik Öğrenci Raporu. Öğretmen analiz içeriğini okuyabilir; önerileri otomatik çalıştıracak düğme eklenmez. Gerçek verilerle deneme öncesi mutlaka yedek alın.
