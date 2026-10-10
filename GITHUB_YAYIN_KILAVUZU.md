# Ödev Takip 3.5.2 — GitHub yayımlama ve kullanıcı güncelleme kılavuzu

## 1. Kurulumdan önce

- Bu paket bir **kaynak kod paketidir**, EXE değildir.
- `version.py` ve `setup.iss` içinde sürüm `3.5.2` olarak hazırlanmıştır.
- Orijinal GitHub depo adresi: `https://github.com/osmankutukcu/YKS_LGS_OdevTakip`.
- **Kayıt yedeğinizi alın**; mevcut kurulumu kaldırmayın. Gerçek kullanıcı kurulumunda önce pilot test yapın.

## 2. Kaynak kodunu GitHub'a taşıyın

Git ile çalışan bilgisayarda proje klasöründe:

```powershell
# İlk sefer, depoda daha önce yanlışlıkla sürümlenmiş SQLite dosyalarını yalnız git takibinden çıkarın.
git ls-files "*.db" "*.sqlite" "*.sqlite3"
# Bulunan her dosya için (örnek):
git rm --cached -- "YKS_LGS_HomeworkManager.db"
# Diğer takip edilen DB/SQLite örnekleri için de tekrarlayın.

git add .
git commit -m "Secure GitHub Windows updater v3.5.2"
git push origin main
```

`.gitignore` ileride bu dosyaların yanlışlıkla yeniden eklenmesini engeller; mevcut geçmişte duran kayıtları otomatik temizlemez. Kullanıcının açıklamasına göre bu depodaki 16 kişilik veri seti tamamen uydurmadır.

## 3. GitHub Actions ile kurulum EXE'si yayımlama

**Dikkat:** `main` dalına push etmek yalnızca derleme/test artefaktını üretir; kullanıcılara Release güncellemesi sunmaz. Başarılı ilk CI koşumundan sonra `v3.5.2` etiketi oluşturun:

```powershell
git tag v3.5.2
git push origin v3.5.2
```

GitHub > Actions > **Windows Installer (Guvenli Release)** çalışmasının başarılı olmasını bekleyin. GitHub > Releases içinde iki dosya olmalı:

- `OdevTakip_v2_Kurulum.exe`
- `OdevTakip_v2_Kurulum.exe.sha256`

**Önemli:** CI güvenlik kapısı, hâlâ Git tarafından takip edilen `.db/.sqlite` dosyaları varsa bilerek hata verir. Önce veritabanlarını sürüm kontrolünden çıkarın. Sürüm etiketi, `version.py` ve `setup.iss` eşit olmalıdır.

## 4. 3.5.0 kullanıcılarının ilk geçişi

Mevcut 3.5.0 güncelleme motoru kurulum EXE'sini ZIP gibi değerlendirebildiği için **3.5.2 ilk sürümünü kullanıcıların GitHub Releases sayfasından kurması gerekir.** Var olan programı kaldırmadan aynı Inno Setup AppId ile üstüne kurmayı deneyin; önce test bilgisayarında sentetik verilerle doğrulayın. Kayıtlar ve lisans korunmalıdır; bu vaat gerçek Windows testine kadar kesinleşmiş sayılmaz.

## 5. Sonraki güncelleme (3.5.2 ve sonrası)

`version.py` + `setup.iss` sürümlerini birlikte 3.5.2 yapıp yeniden derleyin; `git tag v3.5.2` ve `git push origin v3.5.2` ile yayınlayın. 3.5.2 istemcisi açılırken Release API'den sürümü kontrol eder, yeni `.exe` ve SHA256 bilgisini arar. Öğretmen **Güncellemeyi İndir ve Kur** düğmesine bastığında EXE indirilir, kontrol edilir, gerçek SQLite DB yedeklenir ve Windows kurulum sihirbazı başlatılır.

Kurulum halen kullanıcı onayı ve Windows izinlerini gerektirir. Yazılım güvenliği nedeniyle şeffaf olmayan, sessizce zorla kurulumu tercih etmedik.

## 6. Windows yerel EXE üretimi

Windows'ta Python 3.11, gerekli Python paketleri, PyInstaller ve Inno Setup kurulu olmalı.

```powershell
python -m pip install -r requirements_win.txt
python -m unittest discover -s tests -p "test_update_*.py" -v
python build_app.py
# Ardından kurulu Inno Setup 6 ISCC.exe ile setup.iss derleyin.
python publish_release.py 3.5.2
```

`publish_release.py` yalnızca `dist/OdevTakip_v2_Kurulum.exe` mevcutsa `dist_release` içine kurulum EXE + SHA256 kopyalar. Sürüm numarasını değiştirmez; güvenli dağıtım için yanlış sürüme izin vermez. GitHub Actions kullanıldığında yerelde elle Release hazırlamak zorunlu değildir.

## 7. Sorun giderme

- **Güncelleme bulunmuyor:** GitHub'da Release var mı, `v3.5.2` etiketi doğru mu, repo Public mi?
- **İndirme var, düğme pasif:** GitHub Release içinde EXE veya SHA256 eksik olabilir.
- **SHA-256 hatası:** Paketi kurmayın; Release dosyalarını yeniden üretin, onaysız dosyayı çalıştırmayın.
- **Yedekleme hatası:** Gerçek DB'nin erişilebilir/sağlam olduğundan emin olun; güncellemeyi zorla devam ettirmeyin.
- **Kurulum tamamlanmadı:** Eski sürümü silmeyin; orijinal öğrenci veritabanını/yedeği saklayın, Inno Setup günlüklerini kontrol edin.

## Sınır

Bu sürümde otomatik rollback ve Authenticode imzalama henüz yoktur. İmzasız EXE Windows SmartScreen uyarısı gösterebilir. Canlı GitHub Actions koşumu ve gerçek Windows uçtan uca testi henüz tamamlanmadı.
