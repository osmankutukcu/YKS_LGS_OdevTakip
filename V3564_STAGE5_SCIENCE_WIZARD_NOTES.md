# KoçPilot 360 v3.5.64 — Aşama 5: Bilimsel Koçluk ↔ Mevcut Ödev Sihirbazı

## Kapsam

Temel alınan sürüm: v3.5.63 tam kaynak. Ödev Takip, Ödev Kontrol, eski Koç Asistanı, Smart Wizard ve mevcut V30 taslak/aktarım kodları **değiştirilmedi**. Eski ZIP içindeki tek güncellenen kaynak `ui/research_coaching_bridge_v3563.py` (isteğe bağlı yeni okuma ve gelen kutusu bilgisi). Diğer yeni işlevler `services/science_wizard_alignment_v3564.py` içinde yalıtılmıştır.

## Yeni davranış

1. Öğrenci seçimi sonrası mevcut asenkron Koç Asistanı okuyucusu, **aynı salt okunur SQLite anlık görünümünde**, v3.5.63 araştırma kartını inceler.
2. Akademik kanıt yeterli ve öğrenci–ödev bağlantısı doğrulanmışsa V30'un **mevcut** adaptif ödev taslağı (`build_draft`) okunur. Opt-in V25 tabloları yoksa hiçbir tablo oluşturulmaz; yeni kart sessizce sunulmaz.
3. Yalnızca birebir ders + konu ve **gerçek kitap** içeren mevcut V30 taslak satırları bilimsel öğrenme önerisiyle eşleştirilir. Ders/konu farklıysa, kitap yoksa veya yinelenen aynı konu için birden çok kitap belirsizse eşleştirme güvenle engellenir.
4. Öncelik listesi 2 adayı geçmez. V30 iş yükü uyarısı varsa en fazla 1 adaya düşürülür. **Bu sayılar akademik etki iddiası değil, arayüzde dikkat yükü sınırlarıdır.**
5. Koç Asistanı'nın **mevcut gelen kutusuna** ek bilgi kartı eklenir. Mevcut asistanın eylem yönlendiricisi Sihirbaz butonunu açmadığından, yeni kartın düğmesi *Öğrenme* ekranını açar; öğretmen **mevcut Sihirbaz'ı ayrıca** açıp gereken onayları verir. Yanlış “tek tıkla aktarım” vaadi yoktur.
6. Mevcut bilimsel öneri kartı ile Sihirbaz eşleşmesi ayrı anahtarlar kullandığından aynı konuya ait iki bilgi birbirini silmez. Yeni pencere/pop-up, otomatik onay, mesaj, ödev seçimi, checkbox işaretleme, veritabanı yazımı ve sunucu çağrısı yoktur.

## Güvenlik sınırları

- Öğrenci ID, tarih, araştırma şeması/öğrenci ID/güvenlik bayrakları ve V30 taslak parmak izi doğrulanır. İçeriği güncellenmiş taslak engellenir.
- Yeni modül salt okunur kart üretir; seçilen taslağın mevcut checkbox hücresine atanabilir olduğuna dair **son karar vermez**. Tek yetkili aktarım `HomeworkForm._wizard_transfer_tasks` ve onun eski kaydetme yoludur.
- Bilimsel destekli yöntem önerisi, öğrencinin başarısını artıracağının kanıtı veya kesin kök neden tanısı değildir. Ödev tamamlanması ustalık kanıtı değildir.
- UI arka plan işi mevcut 2,5 saniyelik SQL ilerleme/iptal korumasını kullanır. Ekran veya düğme tıklaması bloklanmaz; ancak Windows performansı henüz saha testi görmedi.

## Uygulama testi

- `python -m unittest -q tests.test_science_wizard_alignment_v3564 tests.test_evidence_based_coach_v3563`
- `python -m unittest -q tests.test_science_wizard_alignment_v3564 tests.test_evidence_based_coach_v3563 tests.test_learning_intervention_bridge_v3562 tests.test_coaching_evidence_hub_v3561 tests.test_coaching_integration_guard_v3560 tests.test_adaptive_coaching_v25 tests.test_adaptive_draft_review_v30 tests.test_coach_module_bridge_v264 tests.test_coach_decision_hub_v265 tests.test_v3536_academic_actions tests.test_wizard_student_transfer_v8 tests.test_coaching_safety_v244 tests.test_core_integrity_v133`
- `python tools/v3527_core_guard.py --root .`

## Kontrol edilmesi gerekenler (Windows/UAT)

1. Öğrenci değiştirerek Koç Asistanı gelen kutusunu gözle; eski öğrencinin bilgisi görünmemeli.
2. V25 Öğrenme ölçümleri olan, kitap konusu birebir eşleşen ve eşleşmeyen öğrenciyle dene.
3. Hızlı Teşhis, tek gün düşük sonuç, iki ayrı gün düşük sonuç, iş yükü uyarısı ve iki kitapta aynı konu için önerilerin doğruluğunu kontrol et.
4. Koç Asistanı kapalıyken çalışma yapılmamalı. Öğretmen form checkbox'ları/kayıt/geri alma/renk/kilit davranışları özgün sürümle birebir aynı kalmalı.
5. Tavsiye kartındaki işlem Öğrenme'yi açmalı. Öğretmenin manuel açtığı mevcut Sihirbaz, kendi taslağını yeniden hesaplamalı; yeni kart hiçbir satırı kendiliğinden seçmemeli veya atamamalı.
6. Kaydı olmayan, kısmi/bozuk V25 şeması olan kurulumlar ekrana hata ve otomatik veri değişikliği çıkarmamalı.

**Durum:** Kaynak ve otomatik testler tamam; Windows PyQt6 görsel/performans ve üretim ortamı entegrasyon testi yapılmadı. Güncellemeyi canlı sistemde zorunlu olarak etkinleştirmeyin.
