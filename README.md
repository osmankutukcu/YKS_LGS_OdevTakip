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
