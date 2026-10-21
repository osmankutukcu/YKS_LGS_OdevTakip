# KoçPilot 360 – V3.5.87 Dağıtım Öncesi Güvenlik ve CI Düzeltmesi

**Durum:** Test amaçlı, kaynak kodu birleşik yaması; **müşteriye dağıtım izni verilmedi**.
**Temel:** `YKS_LGS_HomeworkManager_v3.5.80_KocPilot360_Son_Surum.zip`
**Kapsam:** V3.5.81–V3.5.87 raporlama geliştirmeleri + bu güvenlik/CI düzeltmesi. Üretim verileri, lisans anahtarları, EXE ve kurulum dosyaları bulunmaz.

## Somut değişiklikler

1. `.github/workflows/build_installer.yml`: EXE izole açılış testi başarısız olduğunda `exit 0` ile hata yutulması kaldırıldı. Test başarısızsa CI işi başarısız olur; Inno Setup ve GitHub Release adımına geçilmez. Ayrıca rapor modüllerinin regresyon testleri EXE derlemesinden önce zorunlu.
2. `tests/test_v3554_stabilization.py`: PDF metni satır sonunda bölündüğünde aynı güvenlik ifadesini bulabilmek için **yalnızca metin sorgusundaki boşluklar normalize edildi**. WhatsApp/telefon yetki ve URI denetimleri değiştirilmedi. Üretim mobil PDF kodu değiştirilmedi.
3. `OdevTakip_v2.spec`: yeni gerçek PDF önizleme ve toplu PDF işlevinin kullandığı `fitz` modülü PyInstaller gizli importlarına açıkça eklendi. Mevcut `fonts` ve ReportLab paket girdileri korundu.
4. `tools/v3587_ci_preflight.py`: iş akışı, PyMuPDF, fontlar, test zorunluluğu ve hatası yutulan EXE smoke testi için salt-okunur kaynak kontrolü.
5. `tests/test_v3587_ci_preflight.py`: zorunlu denetim olmadan dağıtımı reddetme durumlarına yönelik 3 otomatik test.

## Gerçekten çalıştırılan testler

- **105/105** önceki raporlama/kanıt/regresyon testi başarılı.
- **6/6** eski `tests.test_v3554_stabilization` testi başarılı. Hatalı öğrenci ID örneklerini kapsayan alt testlerde bağlantılar kapalı kalıyor.
- **3/3** yeni CI ön denetim testi başarılı.
- **10 temel korumalı kaynak** orijinal V3.5.80 ile byte bazında aynı. Ödev Takip, Ödev Kontrol, ana pencere ve haftalık planlayıcı işleyiş kodları değişmedi.
- `tools/v3587_release_gate.py` ile birleşik ZIP dosya bütünlüğü / manifest kontrolü yapılmalı.

## Halen bekleyen canlı kabul

- PyQt6 bu test ortamında kurulu değil: üç eski GUI testi başlatılamıyor. Gerçek Windows 10/11 ve macOS arayüz ve yazıcı testleri yapılmadı.
- GitHub Actions koşumu burada yapılmadı. Windows EXE gerçekten yeniden derlenmedi. `fitz` gömülmesini yalnızca statik paketleme konfigürasyonu düzeyinde denetledik; gerçek EXE ile sayfa önizlemesi ayrıca denenmeli.
- **Kurumsal erişim yetkileri ve veri izolasyonu** test edilmeden raporları farklı sınıf/öğretmen/kurumlara otomatik açmayın.
- Test düzeltmesi eski mobil PDF'nin kullanıcıya çıkan görünümünü değiştirmez; yalnızca yanlış negatif otomatik kontrolü düzeltir.

## Güvenli kurulum ve geri dönüş

1. V3.5.80 projesini ve gerçek verileri yedekleyin. Gerçek öğrenci kayıtlarında deney yapmayın.
2. **Ayrı test klasörüne** orijinal V3.5.80 kaynak ZIP'ini çıkartın; bu birleşik test ZIP'ini **dizin yapısını koruyarak** üzerine açın. Önceki V3.5.81–V3.5.87 yamaları ayrıca gerekmez.
3. Test bilgisayarında: `python tools/v3587_ci_preflight.py` ve `python -m pytest -q tests/test_v3554_stabilization.py` komutlarını çalıştırın; ayrıca `python -m unittest tests.test_v3587_ci_preflight tests.test_v3587_stabilization tests.test_bulk_report_v3586 tests.test_report_planner_bridge_v3585 tests.test_integrated_report_v3584 tests.test_professional_pdf_v3583 tests.test_report_center_v3581 tests.test_report_evidence_v3582 -q`.
4. Test amaçlı GitHub dalında Windows CI çalıştırın; EXE testinden hata dönerse **dağıtımı durdurun**, hatayı inceleyin; hata yutma davranışını geri getirmeyin.
5. Manuel kontrol: Ana sayfa, Öğrenci Detayı, Detaylı Raporlar, Rapor Merkezi, tekli/toplu PDF, gerçek önizleme, yazdır, gruplar/filtreler, tema ve farklı ekran boyutları. Ardından V3.5.80 ile Ödev Takip ve Ödev Kontrol tıkla/geri al/kaydet/renk/kilit davranışlarını karşılaştırın.
6. Onay gelmezse test klasörünü bırakıp kullanıcıların mevcut V3.5.80 sürümünde kalmasını sağlayın. **Müşterilere otomatik güncelleme yapmayın.**
