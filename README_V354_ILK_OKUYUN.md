# Ödev Takip V3.5.4 — Önce bunu okuyun

Bu ZIP **yeni kurulum EXE'si değil**, V3.5.3'ü temel alan **tam kaynak kod adayıdır**. Önceki GitHub sürüm güncelleme, yedekleme, web anahtarı ve ödev senkronizasyon düzeltmeleri korunmuştur. Bu turda yeni özellik eklenmemiştir.

**Öne çıkanlar:** Mobil toplu ödev kaydında öğrenci/ders/konu/tarih doğrulaması, eşzamanlı SQLite yazıcı sıralaması, işlem hatasında bütüncül geri alma, çoklu eski alt satır ilişkilendirmesi, tekrarlanan tamamlama isteğinde zaman damgasını koruma.

**Test:** `python -m pytest -q tests` → 102 passed, 23 subtests passed. `python tools/validate_release.py` ve `python -m compileall -q .` başarılı. Gerçek Windows PyQt6 EXE, GitHub Actions canlı Release ve yükseltme bu ortamda denenmedi.

**Koruma:** Örnek veya gerçek öğrenci veritabanı, lisans anahtarı veya yerel gizli dosya dağıtım ZIP'ine eklenmedi. Font dosyaları da paylaşılmadı; derleme için kendi font klasörünüz kullanılmalıdır.

**Önemli:** Mevcut çalışan kurulumun üzerine rastgele dosya kopyalamayın. Önce Windows test bilgisayarında sahte öğrenci verileriyle tüm kritik iş akışlarını doğrulayın. Ayrıntılar `V3_5_4_DETAYLI_STABILIZASYON_RAPORU.md` içinde.
