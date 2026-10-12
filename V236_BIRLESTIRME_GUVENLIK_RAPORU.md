# V23.6 — v3.5.18 + V23.5 üçlü kaynak birleştirme raporu

**Temel kaynak:** kullanıcıdan gelen `OdevTakip_v3518_V13_6_Veriler_Haric_Temiz_Kaynak.zip`.
**Geliştirme kaynağı:** `OdevTakip_V23_5_Kumulatif_Tam_Kaynak_Veriler_Haric.zip`.
**Ortak ata:** v3.5.16/V13.6 veri hariç kaynak.

## Birleştirme kuralları

- Ortak ataya göre tek taraflı geliştirmeler alınmıştır.
- v3.5.18 sürüm numarası, GitHub güncelleme testleri, Windows `setup.iss` ve `.github/workflows/build_installer.yml` **aynen korunmuştur**.
- İki tarafın farklılaştırdığı `ui/plan_settings_dialog.py` için **v3.5.18 kaynak kodu bütünüyle korunmuştur**; planlayıcının çizim ve hata korumaları üzerine eski kod yazılmamıştır.
- `README.md`, v3.5.18 metni korunarak geliştirmelerin açıklaması eklenmiştir.
- V23.5'e ait ana ödev, ödev kontrolü, müfredat, Öğrenci 360° ve entegre test dosyaları korunmuştur.
- **Canlı veritabanı, kullanıcı profili ve lisans üretici özel yönetim araçları dahil değildir.** Yazı tipi dosyaları da aktarılmamıştır; uygulama dağıtımında gerekli font varlıkları ilgili hak ve lisansları gözetilerek ayrı tedarik edilmelidir.
- Bu, **kaynak kod birleşimidir; EXE değildir.** PyQt6/Windows testleri tamamlanmadan canlıya kurulmaz.

## Üçlü fark özeti (gizli/ikili dosya hariç seçime yansıtıldı)
- `v3518_workflow_restored`: 1 dosya
- `unchanged`: 251 dosya
- `manually_resolved_readme`: 1 dosya
- `v235_adopted`: 106 dosya
- `excluded_private_or_binary`: 6 dosya
- `v3518_preserved`: 4 dosya
- `manually_resolved_preserve_live_plan_safety`: 1 dosya

## Kritik sonraki testler

1. Windows 11 ve Windows 10 (varsa), 1366×768 %100/%125/%150 DPI.
2. Mevcut 3.5.18 test ortamında yeni öğrenci/konu, genel ödev sarı/yeşil tik, kaydetme, kapatıp açma ve geri alma.
3. Grup/öğrenci kapsam ödevi tamamlama, iptal, tekrar açma, öğrenci değiştirince izolasyon.
4. Müfredat konu adı değişikliği ve eski ödevlerin doğru bağlanması; sıralama ve mükerrer konu uyarıları.
5. Otomatik GitHub güncelleme senaryosu, kurulum imzası, eski sürümden güncelleme ve geri dönüş.
6. Önce test veritabanında V23.5 `services` denetimi; bağlantı kopuklukları otomatik düzeltilmez.
7. Masaüstü grafik sınaması henüz yapılmadığından **üretime uygunluğu kanıtlanmamıştır**.

## Uygulama

Bu arşiv, v3.5.18 temiz kaynak üzerine güvenli şekilde birleştirilmiş kaynak durumunu temsil eder. Program Files altına veya canlı kurulum klasörüne doğrudan kopyalamayın. Ayrı geliştirme/test dizininde, projeye özgü bağımlılıkları kurup test edin.
