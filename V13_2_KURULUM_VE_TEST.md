# V13.2 — Güvenli Giriş ve Çekirdek Koruma

**Kaynak taban:** kullanıcının v3.5.16 geliştirici yedeğinden hazırlanan V13.1.

1. Mevcut çalışan sürümün veritabanı, profil dosyaları ve kaynak kodunu güvenli yere yedekleyin.
2. Test kopyasına sadece değişen dosyaları, klasör yapısını koruyarak uygulayın; ya da verisiz tam kaynak paketini test ortamına çıkarın.
3. **Mevcut `.db`, `.db-wal`, `.db-shm`, kullanıcı profil JSON'ları ve fontları asla güncelleme dosyalarıyla değiştirmeyin.** V13.2 paketlerinde bunlar yoktur.
4. Yeni kurulumda ilk açılışta `admin` hesabı için güçlü bir parola seçilir. Bilinen bir başlangıç parolası yoktur.
5. Daha önceki `admin/admin` hesabıyla girişte zorunlu güçlü parola değişimi istenir; ardından yeni parolayla tekrar giriş yapılır.
6. Diğer mevcut SHA-256 kullanıcı parolaları başarılı girişten sonra tuzlu PBKDF2 biçimine yükseltilir. Kullanıcıya veri veya ödev değişikliği uygulanmaz.
7. Yönetim Panelindeki yeni parola oluşturma ve parola sıfırlama işlemleri yeni biçimi kullanır; minimum 12 karakter uygulanır.
8. Veritabanını fabrika ayarlarına döndürme işleminde artık yönetici parolası, metinsel onay ve başarılı SQLite tutarlı yedeği gerekir. **Bu işlemi test amacıyla gerçek öğrenci verisinde kullanmayın.**
9. Ödev Takip Formu tikleme, ödev aktarma ve geri alma yöntemlerine V13.2'de dokunulmamıştır.
10. Windows/macOS ekran testi yapılmadı. Özellikle İlk Kurulum, Kullanıcı Oluşturma, Ortak Parolalı Giriş, Öğrenci seçimi ve Reset yetkilendirmesini test makinesinde sınayın.

**Bilinçli sınır:** Var olan kurulumda kullanıcı tarafından açıkça `enable_login=0` seçildiyse bu tercih korunur; dolayısıyla bu kullanıcılar için tam erişim kontrolü sağlanmış değildir. Yeni kurulumda/ayar yoksa giriş açık; kullanıcı tablosu boşsa giriş zorunludur.

**Geri dönüş:** V13.1 kaynak yedeğini ve önceden alınmış veritabanı/yapılandırma yedeklerini geri yükleyin. PBKDF2'ye yükseltilmiş kullanıcı parolaları eski sürüm tarafından doğrulanamaz; bu nedenle güvenli geri dönüş için veritabanı da uyumlu, işlem öncesi sürümden geri yüklenmelidir. Geri yüklemek, yedek tarihinden sonraki kayıtları kaybettirebilir.
