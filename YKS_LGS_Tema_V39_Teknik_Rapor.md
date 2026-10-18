# V39 – Tema/Popup Koruma Teknik Raporu

**Kaynak:** V38 güvenli pilot tam ZIP; V36/V37/V38 iyileştirmeleri korunur.

## Bu aşamada bulunan sorunlar

- Bazı sağ tık ve bağlamsal menüler, `background:#ffffff` ile açık zemine sabitlenmişken koyu temadan miras kalan beyaz yazıyı kullanabiliyor. Seçili/pasif öğelerin ön plan renkleri de yerel stile bağlı kalabiliyor.
- V38 standart bildirim filtresi `QErrorMessage` için QSS kuralları taşıyor ancak bu sınıfı olay yakalama listesine almıyordu.
- V38 bildirimi pencere açıkken bir bileşen tarafından yeni `setStyleSheet` ile biçimlendirilirse eski yerel stil yeniden yüklenebiliyordu.
- `IlerlemePenceresi` yalnızca beyaz arka plan/siyah yazı kullanıyor ve ilerleme metnini zorla siyah renkli HTML etiketi içine yerleştiriyordu.
- Kitap yönetimindeki bazı giriş alanları beyaz zemini açıkça tanımlarken yazı rengini başka stillerden devralıyordu.

## V39 düzenlemeleri

1. **`ui/theme_popup_runtime_v39.py` (yeni):** QMenu açılırken ve tema değiştiğinde ön plan/zemin/seçili/pasif durumların semantik renklendirmesi. Menü aksiyonlarına, kısa yollara, açılış/konuma müdahale etmez. Lokal stili saklar ve sonradan değiştirilmesini tanır; tekrarlı ekleme yapmaz. İsteğe bağlı `_v39_preserve_menu_style=True` özellikli menüleri olduğu gibi bırakır.
2. **`ui/theme_popup_runtime_v38.py`:** `QErrorMessage` desteği ve açık dialog üzerinde sonradan değişmiş yerel CSS'i koruma.
3. **`ui/theme.py`:** Yeni menü koruma katmanını mevcut tema uygulama yoluna ekleme; hata durumunda mevcut işlevin devamı.
4. **`ui/progress.py`:** Özel ilerleme diyaloğu için tema duyarlı ve canlı yenilenen arayüz. Düz metin gösterimi, zorla siyah HTML ön plan kaldırıldı. Değer/başlık güncelleme ve pencere davranışı korundu.
5. **`ui/book_dialog.py`:** Beyaz giriş alanlarına kesin koyu metin ve seçili metin kontrastı eklendi.
6. **`QA_V38`, `QA_V39`:** Önceki test stub uyumluluğu, yeni statik regresyonlar ve gerçek makinede denenebilecek örnek arayüz.

## Statik taramanın sınırları

Aşağıdaki adetler Python kaynak kodunda görülen sözdizimsel eşleşmelerdir; açılabilen gerçek form adedi veya onaylanmış arayüz hatası değildir.

- QDialog constructor: **38** eşleşme.
- QMenu constructor: **30** eşleşme.
- QMessageBox reference: **1174** eşleşme.
- inline CSS/style HTML fragments: **263** eşleşme.

## Kod doğrulaması

- 33 tema × 3 bağlamsal menü renk çifti: en az 4,5:1 kontrast geçti.
- Açılır menüde idempotent uygulama, sonradan değişen yerel QSS, opt-out, sinyalleri/aksiyonları değiştirmeme: sahte Qt nesnelerinde geçti.
- V38'in 33 tema × 10 bildirim renk durumu, V37'nin 33 × 16 semantik renk çifti ve V36 temel QSS denetimleri tekrar geçti.
- Tüm Python dosyalarının sözdizimi AST ile doğrulandı.
- Python ortamında PyQt6 bulunmadığı için gerçek macOS ve Windows GUI çizimi, native dosya seçim diyalogları, QAction erişilebilirliği ve tüm özel HTML panelleri uçtan uca test **edilmedi**.

## Henüz yapılmayanlar

- Kullanıcıların farklı işletim sistemi/ölçek/görüntü modları altında uygulamanın tüm özel formlarında ekran görüntülü, etkileşimli kabul testi.
- Kendi `paintEvent` ve HTML/CSS'i olan, bazen tema motorundan bağımsız çizilen panellerin her birinin ayrı düzeltmesi.
- Sistem tarafından çizilen yerel QFileDialog/QColorDialog pencerelerini değiştirme (bilinçli olarak kapsam dışı).
- Gerçek öğrenci verileriyle deneme (bilinçli olarak yapılmadı).

## Kurulum tavsiyesi

Önce çalışan projenin ZIP yedeğini alın ve yeni sürümü **ayrı bir test klasörüne** çıkarın. `QA_V39/README.md` içindeki testleri uygulayın. Üretim sürümüne geçiş için Windows ve macOS üzerinde kullanıcı kabul testi gerekir.
