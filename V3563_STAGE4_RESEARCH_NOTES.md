# KoçPilot 360 v3.5.63 — Aşama 4: Kanıta Dayalı Koçluk Pilotu

**Başlangıç:** v3.5.62 tam kaynak; mevcut Ödev Takip / Ödev Kontrol / Koç Asistanı kaynakları aynen korunmuştur.

## Yeni kod

- `services/evidence_based_coach_v3563.py`: v3562 kayıtlı öğrenme kanıtından araştırma destekli, gerekçesi ve kaynakları açık öğretmen eylem kartı oluşturur; veritabanına yazmaz.
- `ui/research_coaching_bridge_v3563.py`: mevcut Koç Asistanı'nın öneri gelen kutusuna **arka planda** güvenli kayıt gönderir; yeni buton, popup, tema, pencere, kontrol formu ve checkbox işlemi eklemez.
- `ui/homework_workspace_bridge_v21.py`: mevcut Öğrenci 360°/Koç Asistanı koordinasyon noktasına 3.5.63 sidecar'ı yükler (tek mevcut kod entegrasyonu).
- `tests/test_evidence_based_coach_v3563.py`: sentetik kayıtlar üzerinden kaynak eşleştirme, öğrenci izolasyonu, müdahale ve yanlış öneri güvenliği testleri.

## Araştırma rehberleri — kanıt düzeyi ve kullanım alanı

1. **Dunlosky vd. (2013)**, *Improving Students' Learning with Effective Learning Techniques*, Psychological Science in the Public Interest. Alıştırma testleri / dağıtılmış tekrar güçlü bir genel dayanağa sahip; v3563 `SPACED_CHECK` eylemi kısa hatırlama kontrolü olarak kullanır. https://www.psychologicalscience.org/journals/pspi/1529100612453266/
2. **IES/What Works Clearinghouse (2007)**, *Organizing Instruction and Study to Improve Student Learning*. Öğrenmeyi zamana yayma için orta, anahtar içeriği tekrar gündeme getiren kısa sınamalar için güçlü kanıt kategorileri belirtir. `SPACED_CHECK`, `CHECK_ERRORS`, `TARGETED_REVIEW` adımlarını bilgilendirir. https://ies.ed.gov/ncee/wwc/PracticeGuide/1
3. **EEF (2025)**, *Metacognition and Self-Regulated Learning*, ikinci baskı. Planlama–izleme–değerlendirme ve öğretmen modellemesi; `CLARIFY_OBSERVATION` için öz değerlendirme sorusu. https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/metacognition
4. **EEF (2021)**, *Teacher Feedback to Improve Pupil Learning*. Zamanında, görevle ilişkili, eyleme geçirilebilir geri bildirim; `TARGETED_REVIEW`, `CHECK_ERRORS`, `CLARIFY_OBSERVATION` için rehberdir. https://educationendowmentfoundation.org.uk/education-evidence/guidance-reports/feedback

**Sınır:** Koçluk görüşmesinin, GROW modelinin, Ebbinghaus yüzde eğrisinin veya tek bir tekrar takviminin her öğrencide sonuç verdiği iddia edilmez. Yukarıdaki çalışmalar yönteme yönelik araştırma bulgularını temsil eder; KoçPilot'un öğrenciler üzerindeki etkisi ayrıca sınanmalıdır. Öğrencinin klinik, psikolojik veya nedensel teşhisi oluşturulmaz.

## Kullanım

1. Öğrenciyi her zamanki şekilde seçin.
2. Arka plan işçisi, öğrenci ve ödev sahipliği doğrulanabiliyorsa kayıtlı Öğrenme/Hızlı Teşhis verilerini değerlendirir.
3. Uygun öneriler, **Koç Asistanı > sağ tık > seçili öğrencinin son önerileri** alanında görünür. Yeni pencere veya otomatik popup açılmaz; mevcut `Koça Sor` ve `Öğrenme` yolları korunur.
4. Öğretmen dilerse öneriden mevcut `Öğrenme` ekranına geçer. Otomatik ödev, kayıt, mesaj veya plan değişikliği yapılmaz.
5. Koç Asistanı mevcut Açık/Kapalı anahtarıyla kapatılırsa yeni köprü de pasif kalır. Ayrıca `QSettings('EduTrack','HomeworkManagerV2')` içindeki `research_coaching_v3563_enabled=0` ayarı pilotu kapatabilir. Tek başına kullanıcı ayarı olarak ayrı bir GUI seçeneği henüz yoktur.

## Koruyucu teknik kurallar

- Sadece `mode=ro` ve `PRAGMA query_only` bağlantısı; tutarlı read transaction; SQL ilerleme sayacıyla yaklaşık 2,5 saniyelik analiz bütçesi; istisnada öneri üretmeme.
- Başka öğrenciye geçildiğinde eski sonuç seri/öğrenci kimliğiyle reddedilir, bekleyen işler güncel öğrenci için yeniden planlanır.
- Öğretmenin doğrudan etkileşimini kesmeyen **inbox-only** kaynak politikası kullanılır; kaynaklar kullanıcıya gösterilir, başarı garantisi verilmez.
- Hiçbir modül eski veritabanı kayıtlarına yazmaz; özellikle Öğrenme ölçümleri ödevin tamamlandı durumuyla bir tutulmaz.
- Mevcut Ödev Takip, Ödev Kontrol, Koç Asistanı ve korunan kaynakların hash değerleri değiştirilmedi.

## Sınamalar ve sınırlamalar

- Seçilmiş testlerde 168 test ve 27 alt test başarılı (sonraki paketleme denetimi ayrıca raporlanır).
- `tools/v3527_core_guard.py` korunmuş kaynak/işleyiş denetimi uygulanır.
- Bu çalışma ortamında PyQt6 yüklü olmadığından gerçek Windows kullanıcı arayüzü, görsel uygunluk, hafif/yük altında gecikme ve gerçek öğrenci veritabanı performansı henüz doğrulanamadı. Pilot kontrollü Windows testinden sonra üretime alınmalıdır.
- Araştırma kaynağı tanımlayan JSON benzeri sabitler çevrimdışı; öğrencinin kişisel bilgisi internete gönderilmez.

## Sonraki sürümler için ayrıca değerlendirilecek kanıtlar

- **EEF Homework**: Ödev miktarından çok amaç, dersle bağlantı ve yapılan işe verilen geri bildirim önemli. Hedef: otomatik ödev yoğunluğu önerilerinde yük–amaç–geri bildirim dengesini hesaba katmak. https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/homework/
- **EEF One-to-one Tuition**: Tanımlanmış ihtiyaca yönelik, düzenli bireysel destek ve sonuç izleme; hedef: öğretmene gerektiğinde telafi etüdü taslağı önermek. Bu v3.5.63 kodunda otomatik etüt atama YOKTUR. https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/one-to-one-tuition%2B
- **EEF Mastery Learning**: İlerlemeyi farklı zamanda tekrarlanan ölçümlerle kontrol etme; araştırma güveni sınırlı olduğu için sabit yüzdeyle ustalık teşhisi yapılmaz. https://educationendowmentfoundation.org.uk/education-evidence/teaching-learning-toolkit/mastery-learning/
