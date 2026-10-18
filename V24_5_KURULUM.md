# V24.5 — Koçluk Planı Tek Bakış Özeti

## Tek adım güncelleme

Bu ZIP, **tam V24.4 kaynak sürümü** içindir. EXE veya DMG değildir. Önce tüm proje klasörünü ve veritabanını ayrıca yedekleyin ve **test kopyasında** deneyin.

Komut satırında önce kontrol:

```bash
python install_v245.py --project "/proje/dizini" --check
```

Çıktı `clean` ise:

```bash
python install_v245.py --project "/proje/dizini" --install
```

Geri alma:

```bash
python install_v245.py --project "/proje/dizini" --rollback
```

Windows için `python` yerine `py` kullanılabilir. Güncelleyici öğrenci veritabanına dokunmaz; sadece iki kaynak dosyasını kontrol eder/kurar. Durum `mixed/unknown` olursa projeye dokunmaz. Başka sürümde çalıştırmayın.

## Kullanım

Koçluk Planı'nı açın → soldan öğrenci seçin. Sağ tarafta yedi sekmenin **üstündeki sabit özet** otomatik oluşur. Haftayı değiştirince özet de değişir. Gecikmiş ödev veya eksik plan varsa açıklama ve **tek yönlendirme düğmesi** gösterilir. Ekran bilgileri değiştirmez, tek tıkla mevcut uygun sekmeye geçer.

**Önemli:** Hedef soru tamamlama ≠ deneme başarısı ≠ konu hâkimiyeti. Özet farklı kaynakları etiketleyerek gösterir.
