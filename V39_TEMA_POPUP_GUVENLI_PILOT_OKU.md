# V39 – Açılır Menü / Özel Bildirim / İlerleme Penceresi Tema Güvenli Pilotu

Kaynak: `YKS_LGS_Tema_V38_Bildirim_GuvenliPilot_TamProje.zip`.

Düzeltilenler:
- `QErrorMessage` de V38 standart mesaj gardına eklendi. Diyalog kapanma/seçim/sinyal mantığına dokunulmadı.
- V38 mesaj gardı, özel diyalog kendi stilini sonradan değiştirirse yeni geliştirici stilini korur.
- QMenu açılış ve tema değiştirmede kendi renk katmanıyla güncellenir. Menü aksiyonları, pasif durum, sinyal ve kısayollar korunur. `'_v39_preserve_menu_style'=True` özel çizilmiş menülerde katmanı devre dışı bırakır.
- Özel `IlerlemePenceresi` açık/koyu renkleri, tema değişiminde güncellenir; kullanıcı metnini sabit siyah HTML yerine düz metin olarak gösterir.
- Kitap ekranındaki beyaz zeminli giriş alanları artık açıkça koyu ön plan rengi kullanır.

Bu sürüm hâlâ statik kod testleriyle doğrulanan bir **pilot** sürümdür; gerçek platform çizimleri Windows/macOS üzerinde denenmelidir.

Test için: `python QA_V39/test_popup_theme_v39.py`, ardından `python QA_V39/preview_popup_windows_v39.py`.
