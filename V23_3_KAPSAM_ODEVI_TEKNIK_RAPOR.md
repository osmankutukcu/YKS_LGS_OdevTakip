# Ödev Takip V23.3 — Kapsama Özel Konu Ödevleri / Güvenli Modüler Bağlantı

**Temel kaynak:** `OdevTakip_V23_2_Moduler_Kumulatif_Kaynak_Veriler_Haric.zip`  
**Tarih:** 12 Ekim 2026  
**Statü:** Kaynak düzeyinde geliştirildi; gerçek Windows PyQt6/EXE kabul testi bekliyor.  
**İlke:** Eski matris genel `konu_id` akışını, sarı/yeşil tikleri, kaydetme ve kontrol ekranlarını değiştirmeden çalışmak.

## Teknik problem ve karar

Eski `odev.konu_id` genel ders konusunun **sayısal** kimliğini tutar. `grup_konu_duzen.id` ve `ogrenci_konu_duzen.id` farklı ad alanlarıdır. Örneğin üç tabloda `id=1` bulunabilir. Doğrudan eski ödev matrisine bağlamak, yanlış tik veya ödev durumunu tetikleyebilir. Bu nedenle yeni özel kapsam ödevlerini ayrı bir tablodan yöneten **kademeli** yaklaşım seçildi; `konu_id=0` gibi yapay ID'ler kullanılmadı.

## Değiştirilen / eklenen kaynaklar

| Dosya | Değişiklik ve gerekçe |
|---|---|
| `services/curriculum_v233/service.py` | Kapsam kimliği, seçili öğrenci/grup doğrulama, öğrenciye kayıtlı kitap, tarih, yinelenen ödev denetimi, SQLite transaction, ayrı kayıt tablosu, durum geçişi. |
| `services/curriculum_v233/__init__.py` | Açık ve küçük servis API'si. |
| `ui/scoped_homework_v233.py` | Modüler görev penceresi: konu/kitap seçimi, dakika, teslim tarihi, açık öğretmen onayı, mevcut kayıtların listesi, tamamla/iptal işlemleri. |
| `ui/curriculum_matrix_preview_v232.py` | Mevcut `Konu Kapsamı` penceresine tek düğme eklendi; eski tablo ve önizleme duruyor. |
| `ui/student_workspace_panel_v21.py` | V23.3 kapsam ödevleri Öğrenci 360° içinde **ayrı sayı kategorisi** olarak gösteriliyor; eski kontrol toplamlarına dahil edilmiyor. |
| `tests/test_v233_scoped_homework.py` | 21 modüler test: kimlik, kapsam, ad/kitap değişikliği, DB işlemleri, geri alma/iptal durumları, çakışma ve eski veri bütünlüğü. |
| `V23_3_KAPSAM_ODEVI_GUVENLI_KULLANIM.md` | Öğretmen ve Windows test kullanım kılavuzu. |

**Özellikle değiştirilmedi:** `ui/homework_form.py`, `ui/odev_kontrol.py`, `db.py`, `services/curriculum_v231` ve `services/curriculum_v232/bridge.py`. Yeni tablolar eski tablo/kolonları yeniden yapılandırmaz.

## Veritabanı ve işlem güvenliği

- Yeni tablo `kapsam_odev_v233` yalnızca ilk gerçek kayıt işleminde eklenir. Genel/grup/öğrenci müfredat tablolarındaki satırların ID’leri hiç değiştirilmez.
- Yeni görev kimliği `scope + ders + satır ID + grup/öğrenci kapsamı` içeren V23.1 `TopicIdentity` referansıdır. SQL'e elle konu adı üzerinden bağlama yapılmaz.
- Önizleme ve kayıt anında konu yeniden okunur. Adı/kapsamı değişmiş, çakışan veya geçersiz konular reddedilir.
- Kitap, **aynı öğrenci ve derse atanmış** `ogrenci_kitap` tablosundan doğrulanır.
- `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` ile tek işlem kullanılır; var olan bağlantıda başka işlemin açık transaction'ı varsa yazma reddedilir.
- Kısmi aktif benzersizlik: aynı öğrenci/ders/konu referansı/kitap için eşzamanlı **açık** görev oluşturulamaz. Tamamlanmış veya iptal edilmiş kayıtlar silinmeden saklanır.
- Durum değiştirmede hem `id` hem `ogrenci_id` hem de beklenen `devam` durumu kontrol edilir. Bir öğrencinin ödevi diğer öğrenci tarafından işaretlenemez.
- `odev`, `odev_satir`, `odev_kume` tablolarına INSERT, UPDATE veya DELETE yapılmadı. Bu tablolardaki eski kayıtlar ve sarı/yeşil tikler yeni işlemden etkilenmez.

## Test sonuçları

- V23.3 + V23.2 + V23.1 + V23.0 hedefli testleri: **75 passed, 4 subtests passed**.
- Genel regresyon: **732 passed, 48 subtests passed, 1 skipped, 4 failed, 4 collection errors**.
- Genel başarısızlıkların üçü ve dört yükleme hatası ortamda gerçek PyQt6 bulunmamasından; bir başarısızlık tam kaynak arşivinde `.github/workflows/build_installer.yml` bulunmamasından kaynaklanıyor.
- Python sözdizimi kontrolü geçti; ZIP bütünlüğü kontrolü ayrıca yapıldı.
- **Gerçek veri read-only testi:** önceki v3.5.16 yedeğindeki 16 öğrenci × 20 ders = **320 başarılı okuma**, hata 0. Mevcut v3.5.16 yedek verisinde bulunan tek özel konu bağlamında öğrenciye atanmış kitap bulunmadığından bu yedekte gerçek kapsam ödevi oluşturma testi yapılmadı. Gerçek veri kopyasının SHA-256 değeri değişmedi.
- **Gerçek Windows Qt GUI testi yapılamadı** ve EXE/v3.5.17 canlıya alma doğrulaması yoktur.

## Açık entegrasyon sınırları

1. Yeni kapsam ödevleri **eski Ödev Kontrol Formu'nda görünmüyor ve o formdan değiştirilemiyor**. Yönetimi şimdilik `Konu Kapsamı → Kapsama Özel Ödevler` penceresinde yapılır.
2. Yeni kayıtlar Öğrenci 360° içinde ayrı özetlenir ama ana performans paydasına, sarı/yeşil matris tiklerine veya eski ödev kontrol sayılarına otomatik katılmaz. Bu, yanlış çift sayımı bilinçli olarak engeller.
3. Ana ödev formuna doğrudan yeni kapsam satırı eklenmesi hâlâ ayrı kimlik-aware render/kayıt/geri alma geçişi gerektirir. Bu adımı tam Windows kabul testlerinden önce etkinleştirmek doğru değildir.
4. Çalışan v3.5.17 kaynak farklılıkları henüz bu v3.5.16 tabanlı V23.2/V23.3 zincirine birleştirilmedi. Yama **doğrudan canlı EXE üzerine kopyalanmamalıdır**.

## Sonuç

V23.3, mevcut matris akışını değiştirmeden grup/öğrenci konularına özel ödev açılabilmesini ve bu görevlerin **izlenebilir, doğrulanmış bir kimlikle** takip edilmesini sağlayan **ilk kontrollü yazma köprüsüdür**. Eski Ödev Kontrol ekranıyla tam iki yönlü entegrasyon **tamamlanmış değildir**. Sonraki aşama, gerçek Windows kurulumunda regresyon ve gerekli veri/GUI köprü testleri tamamlandıktan sonra kararlaştırılmalıdır.
