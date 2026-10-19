# 🎓 KoçPilot 360 — YKS & LGS Ödev ve Bütünleşik Koçluk Sistemi

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Database](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-v3.5.55-indigo.svg)](https://github.com/osmankutukcu/YKS_LGS_OdevTakip/releases)

**KoçPilot 360**, YKS ve LGS hazırlık sürecindeki öğrencilerin ödev takip, koçluk, deneme sınavı analizi, haftalık çalışma programı ve veli bilgilendirme süreçlerini tek bir merkezden yöneten profesyonel bir masaüstü uygulamasıdır.

---

## 🌟 Öne Çıkan Özellikler

### 🏠 1. Öğretmen Karar Masası & Kokpit
- **Sınav Geri Sayımı:** YKS, MSÜ ve LGS gün sayaçları ve güncel eğitim takvimi.
- **Anlık Metrikler (KPI):** Bugünkü ödev kontrolü, aktif öğrenciler, geciken görevler ve genel tamamlama oranı.
- **Akademik Trend Grafiği:** Haftalık başarı eğilimleri ve öğrenci performans rozetleri.

### 📱 2. Akıllı Cep Ajandası & İletişim Merkezi
- **Responsive Arayüz:** Her ekran çözünürlüğüne otomatik uyum sağlayan modern kart tasarımı.
- **Veli & Öğrenci İletişimi:** Tek tıkla WhatsApp üzerinden kişiselleştirilmiş ödev ve durum bildirimleri.
- **Hızlı Durum Raporlama:** Öğrencinin günlük ve haftalık programını doğrudan cep formatında görüntüleme.

### 📄 3. Akıllı Mobil PDF Asistanı
- **A5 Cep Formatı:** Telefon ve tabletlerde rahat okunabilen, yatay kaydırma gerektirmeyen optimize PDF planları.
- **Esnek Planlama:** 7, 10 veya 14 günlük periyotlarda dinamik soru hedefi ve konu dağılımı.
- **Dönemlik Mesaj & Geri Bildirim Merkezi:** Öğrenciye özel motivasyon notları ve öğretmen yönlendirmeleri.
- **Alıcı Kimlik Doğrulaması:** Yetkisiz erişimi engelleyen güvenli bağlantı ve karekod köprüleri.

### 📋 4. Ödev Takip & Dinamik Kontrol Formu
- **Dinamik Kitap & Ders Matrisi:** Öğrenciye tanımlı kaynaklara göre dinamik şekillenen etkileşimli tablo.
- **Hücre Koruma & Renklendirme:** Tamamlanan, geciken ve aktarılan ödevler için görsel kilit ve durum takibi.
- **Otomatik Senkronizasyon:** Form kapatıldığında veya tamamlandığında ana ekran ve menü durumunun kusursuz eşitlemesi.

### 📊 5. Deneme Sınavları & Eksik Konu Analizi
- **Net Takibi:** TYT, AYT, YDT ve LGS sınav sonuçlarının ders ve konu bazında detaylı dökümü.
- **Kazanım Eşleştirme:** Yanlış yapılan sorulara göre MEB ve ÖSYM müfredatına dayalı konu eksik tespit robotu.

### 🔒 6. Dual-Key Güvenlikli Lisanslama Mimarisi
- **2048-bit RSA V2 İmzası:** En yüksek endüstri standartlarında donanıma bağlı (Machine ID) şifreleme.
- **Kesintisiz Geçiş (Dual-Key Migration):** Mevcut lisanslı kullanıcıların haklarını koruyan, geriye dönük tam uyumlu doğrulama mekanizması.
- **Depo ve Dağıtım Hijyeni:** Gizli anahtar ve admin araçlarının dağıtım paketlerine sızmasını engelleyen otomatik CI/CD güvenlik kapıları.

---

## 📂 Proje Dizin Yapısı

```text
├── app.py                     # Uygulama ana giriş noktası
├── main_window.py             # Ana kokpit penceresi ve sol navigasyon menüsü
├── db.py                      # SQLite veritabanı motoru ve şema yönetimi
├── version.py / version.json  # Uygulama sürüm bilgisi ve güncelleme yapılandırması
├── setup.iss                  # Windows Inno Setup kurulum derleme betiği
├── ui/                        # PyQt6 arayüz modülleri ve formlar
│   ├── mobile_schedule.py     # Akıllı Cep Ajandası & İletişim Merkezi
│   ├── homework_form.py       # Ödev Takip Formu
│   ├── odev_kontrol.py        # Ödev Kontrol & Sonuç Giriş Formu
│   └── coaching_manager.py    # Adaptif Koçluk Merkezi
├── services/                  # İş mantığı, mobil PDF asistanı ve veri servisleri
├── utils/                     # Yardımcı kütüphaneler ve lisans yöneticisi
├── seed/                      # MEB / ÖSYM müfredat ve konu veri tabanları
├── tests/                     # Otomatik birim, entegrasyon ve regresyon testleri
└── tools/                     # Dağıtım, sürüm doğrulama ve güvenlik denetim araçları
```

---

## 🚀 Kurulum ve Çalıştırma

### 1. Gereksinimler
- Python 3.10 veya 3.11
- pip paket yöneticisi

### 2. Kaynak Koddan Çalıştırma

```bash
# Depoyu klonlayın
git clone https://github.com/osmankutukcu/YKS_LGS_OdevTakip.git
cd YKS_LGS_OdevTakip

# Sanal ortam oluşturun ve etkinleştirin
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# veya: .venv\Scripts\activate   # Windows

# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Uygulamayı başlatın
python app.py
```

### 3. Tek Tıkla Başlatıcılar
- **macOS:** `Baslat_Mac.command` dosyasına çift tıklayarak doğrudan çalıştırabilirsiniz.
- **Windows:** `Baslat_Windows.bat` dosyasına çift tıklayarak çalıştırabilirsiniz.

---

## 🧪 Testlerin Çalıştırılması

Tüm test paketini çalıştırmak için:

```bash
# Birim ve güvenlik testlerini çalıştırın
python -m unittest discover -s tests -p "test_*.py"

# Dağıtım ve sürüm hijyen kontrolü
python tools/validate_release.py --check-tracked
python tools/v3540_preflight.py
```

---

## 📦 Dağıtım ve Yayın Süreci (CI/CD)

Proje, GitHub Actions üzerinde tam otomatik derleme hattına sahiptir:
1. `push` veya sürüm etiketi (`v3.5.55`) verildiğinde derleme tetiklenir.
2. Otomatik güvenlik testleri, korunan çekirdek denetimi ve hijyen kapıları çalıştırılır.
3. PyInstaller ile Windows bağımsız EXE (`OdevTakip_v2.exe`) derlenir.
4. Inno Setup ile tek kurulumlu Windows Kurulum Paketi (`OdevTakip_v2_Kurulum.exe`) üretilir.
5. **SignPath Foundation** açık kaynak kod imzalama servisi üzerinden SHA-256 dijital sertifika ile imzalanır.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında açık kaynak olarak geliştirilmektedir.
Ticari modüller ve kurum lisanslama altyapısı KoçPilot 360 telif haklarına tabidir.
