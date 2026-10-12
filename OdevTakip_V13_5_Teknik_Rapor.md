# V13.5 – Ödev Veri Bütünlüğü ve Kendini Denetleme (v3.5.16 kaynak zinciri)

## Temel sonuç

V13.4 kümülatif kaynak paketi üzerine **salt okunur, öğretmenin isteğiyle açılan** veri denetimi eklendi. Ana Ödev Takip Formu'nun ödev kaydetme, silme, tikleme, Sihirbaz, Eksikler, Takviye ve Öneri çalışma yolları değiştirilmedi. Alt bara küçük **🔎 Denetim** düğmesi eklendi.

## Uygulanan değişiklikler

| Dosya | İşlem |
| --- | --- |
| `services/homework_integrity_v135.py` | Yeni bağımsız, Qt gerektirmeyen veritabanı ve taslak kontrol motoru |
| `ui/homework_integrity_dialog_v135.py` | Yeni salt okunur denetim penceresi, raporu kopyalama; hücreleri/ödevleri değiştirmez |
| `ui/homework_form.py` | Alt bara Denetim düğmesi ve yeni diyalog çağrısı |
| `tools/audit_homework_v135.py` | Açıkça verilen DB yolunda yalnızca okuma yapan bağımsız konsol denetimi |
| `tests/test_v135_integrity_audit.py` | 31 yeni otomatik test |
| `V13_5_VERI_BUTUNLUGU_KULLANIM.md` | Öğretmen ve teknik ekip kullanım/kurulum açıklaması |

### Veri kontrolleri

- `odev`, `odev_satir` ve `odev_kume` tablolarında kayıp öğrenci ve küme bağlantıları.
- Ödev satırının bağlı olduğu kümenin başka öğrenciye ait olması.
- `odev_satir.odev_id` mevcutsa ve hedef `odev` yoksa kopuk bağlantı.
- `odev_satir` ve bağlı `odev` arasında öğrenci kimliği uyuşmazlığı.
- Sağ taslakta yinelenen ders–kitap–konu, belirsiz çift hücre, düzenlenebilir tik ve taslak arasında eşleşme eksikliği.
- Seçili öğrenci ile yüklenmiş matris ID'si uyuşmazsa taslak denetimini sonlandırma.

**Yanlış alarmı azaltan kurallar:** `odev_satir.odev_id` boş olabilir; iki tablonun satır sayılarını eşitlemeye çalışmıyoruz. Kaydedilmiş ve kilitli matris tikleri geçici ödev listesiyle karşılaştırılmıyor. Tüm bulgular yalnızca tavsiye niteliğindedir, otomatik onarım yoktur.

## v3.5.16 yedek veritabanında kontrol

Kullanıcının sağladığı ZIP içindeki `YKS_LGS_HomeworkManager.db` dosyasının **yerel kopyası**, SQLite salt okunur bağlantıyla açılıp incelendi. Yeni motorda yalnızca `MISSING_LINKED_HOMEWORK = 3` bulundu. Bu kayıtlar değiştirilmedi, silinmedi veya başka öğrencilerle eşleştirilmedi. Bu sonuç tek ZIP kopyası için geçerlidir; canlı bilgisayarın güncel veritabanının birebir aynı olduğu kanıtlanmış değildir.

## Testler

- V13.5 özel testler: **31/31 başarılı** (yapay SQLite veritabanları, kilitli/taslak Qt taklitleri, öğrenci sahipliği, tekil eşleşme, salt okunurluk, arayüz bağlantısının statik kontrolü).
- PyQt6 bağımlı üç modül hariç geniş regresyon: **405/405 başarılı**, 0 hata/0 başarısızlık.
- Hariç bırakılan modüller: `test_update_delivery`, `test_v3516_fixes`, `test_whatsapp_and_brief_ui`; bu çalışma ortamında PyQt6 kurulu değil. Mac/Windows gerçek GUI testi yapılmadı.
- Python compileall ve ZIP arşiv testi yapılmıştır.

## Kalan kritik işler ve önerilen V13.6

1. **Veri uzlaştırma:** Bilinen 3 kopuk bağlantının kayıt geçmişiyle incelenmesi ve yalnızca insan onaylı, geri alınabilir düzeltme prosedürü.
2. **Arayüz kabul testi:** İki örnek öğrenci ve farklı kitap/konularla otomatik aktarma → tik kaldırma → kaydetme → yeniden yükleme → Ödev Kontrol dönüşü. Sarı/yeşil kilitler ayrı test edilmeli.
3. **Ekran uyarı otomasyonu:** Salt okunur denetimi ana form açıldığında istek üzerine veya düşük yükle devreye sokmayı ancak performans ve yanlış alarm ölçümünden sonra değerlendirin.
4. **Tek veri modeli:** Tarihsel `odev` ve `odev_satir` tabloları için tek kayıt kaynağına kademeli geçiş tasarlayın. Kayıt sayılarını rastgele eşitlemeyin.

## Güvenli dağıtım

Güncelleme **V13.4 test kaynak kodu** üzerine geliştirilmiştir. Veritabanı, kullanıcı profili, gerçek öğrenci kayıtları ve özel yedekler dağıtım ZIP'lerinde yoktur. Canlı kurulumun üzerine otomatik yazmayın. Kod ve DB yedeği aldıktan sonra Mac ve Windows'ta deneyin.
