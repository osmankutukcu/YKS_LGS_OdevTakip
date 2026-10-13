# YKS/LGS Ödev & Takip Yöneticisi (MVP)

Bu proje, PyQt6 + SQLite ile geliştirilen, öğrenci kaydı, ödevlendirme ve takip,
raporlar ve kitap yönetimi özelliklerini içeren **MVP** bir masaüstü uygulamadır.

## Kurulum
```bash
pip install -r requirements.txt
python app.py
```

İlk çalıştırmada `~/.yks_lgs_manager/veritabani.db` oluşturulur ve `seed/*.json` dosyalarındaki
konular ders tablolarına yüklenir.

## Modüller
- `app.py`: Giriş noktası
- `main_window.py`: Ana menü ve geçişler
- `db.py`: Veritabanı ve seed yükleme
- `ui/student_form.py`: Öğrenci kaydı (Excel içe aktarma + progress + async)
- `ui/homework_form.py`: Ödev takibi (sekmeler, dinamik kitap sütunları, checkbox)
- `ui/book_dialog.py`: Kitap Ekle/Sil (tek/seçilen/tümü hedefleri)
- `ui/progress.py`: Genel amaçlı ilerleme penceresi
- `ui/reports.py`: Raporlar (örnek grafik yer tutucu)
- `utils/async_workers.py`: Arka plan iş sarmalayıcısı
- `utils/xlsx_io.py`: Excel şablon ve içe aktarma
- `utils/whatsapp.py`: WhatsApp gönderim **yer tutucu**

## Notlar
- Bu, kapsamlı isteğinizin çekirdek işlevlerini çalışır şekilde örnekleyen bir başlangıçtır.
- Ödev kontrol ekranı, yazdırma/PDF, WhatsApp otomasyonu, hücre kilitleme/renklendirme gibi ileri özellikler
  bir sonraki yinelemede eklenecek şekilde yer tutucularla işaretlenmiştir.


## V29 · Kontrol Sonrası Adaptif Karar (modüler)

- Ödev Kontrol → seçili ödevde sağ tık → **🧠 Sonraki adım önerisini göster (salt okunur)**.
- Ödev Takip → **Adaptif Koçluk** sağ panelinde güncel öğretmen notlarına dayalı kısa öneriler.
- **V29 ödev kaydı, checkbox, Kaydet veya WhatsApp kodlarını değiştirmez.**
- Yalnız yeni özelliği devre dışı bırakmak: Windows PowerShell'de başlatmadan önce `$env:EDUTRACK_ADAPTIVE_V29='0'`.
- Pilot ve Windows test bilgileri: `V29_KONTROL_SONRASI_ADAPTIF_KARAR_WINDOWS_TEST_RAPORU.md`.


## V30 · Öğretmen Onaylı Tek Ekran Ödev Taslağı

- **Ödev Takip → Adaptif Koçluk → Genel Bakış → Taslağı İncele ve Seç**.
- Sadece mevcut öğrencinin V25 verilerinden ve varsa V29 açık öğretmen notlarından öneriler hazırlanır.
- Ders/kitap/konu hücresi bulunamıyor, kilitli veya işaretliyse aktarım yapılamaz.
- Öğretmen önerileri seçip onayladıktan sonra **yalnızca** mevcut `_wizard_transfer_tasks` çağrılır.
- `Verilen Ödevler` tablosundaki değişiklikler eskisi gibi **Kaydet** ile kalıcı olur.
- Ödev Kontrol, tik, kayıt geri alma, yazdırma ve WhatsApp işlemleri değişmez.
- Varsayılanı kapatmak: `$env:EDUTRACK_ADAPTIVE_V30='0'` (uygulamayı açmadan önce).
- Windows pilot ayrıntıları: `V30_MODULER_OGRETMEN_ONAYLI_TASLAK_RAPORU.md`.

## V33 – Windows A/B hız pilotu ve Stable'a bitirme planı

- Test DB üzerinde eski/yeni tablo stil yenilemesini kıyaslamak için `tools/v33_windows_ab_pilot.py`.
- Deneysel stil birleştirme **normal programda kapalıdır**. Ödev Takip, Ödev Kontrol, veritabanı ve Kaydet/Geri Taşı kaynak dosyaları V32 ile aynıdır.
- Windows komutları, raporun nasıl yorumlanacağı ve V35 Stable kabul kriterleri için `V33_WINDOWS_PILOT_VE_BITIRME_PLANI.md`.

### V35 Windows kabul adayı (Stable değildir)

V34 adaptif koçluk ve Ödev Takip / Ödev Kontrol çekirdeği korunmuştur.
V35'te yalnızca güvenli yayın kapısı, geçici/sahte veritabanında Windows EXE açılış
kontrolü ve manuel pilot kabul süreci eklenmiştir. Başlangıç: `python tools/v35_release_gate.py`.
Test koşulları için `V35_WINDOWS_KARARLILIK_VE_YAYIN_KABUL_RAPORU.md` dosyasına bakın.
Gerçek Windows kabulü tamamlanmadan GitHub tag release'i engellenir.


## V35 son Windows pilot kiti (yayın adayı)

Windows üzerinde çift tıklamayla başlatmak için `V35_Windows_Pilot_Baslat.bat`.
Geçerli, tamamen sahte SQLite DB önceden oluşturulur; mevcut öğrenci DB'si
otomatik seçilmez. Sadece gerçek Windows kullanıcı kabulü sonrası sürüm yayımlanabilir.
Ayrıntılı rehber: `V35_WINDOWS_PILOT_KULLANIM_VE_SON_DOGRULAMA.md`.


### V35 RC2 son Windows pilot güvenlik düzeltmesi

Windows test başlatıcısının kullanıcı profili ve ek dosya yollarını yalıtan güncel sürümü, gerçek verilerle karışmayı azaltır. Yalnız sahte öğrenci ve ayrı test kurulumuyla çalışın; bu paket henüz Stable değildir. Ayrıntılar: `V35_WINDOWS_PILOT_KULLANIM_VE_SON_DOGRULAMA.md` ve `V35_RC2_SON_PILOT_GUVENLIK_RAPORU.md`.
