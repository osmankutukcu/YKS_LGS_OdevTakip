# -*- coding: utf-8 -*-
"""Müfredat/Ders Yönetimi — mevcut SQLite sözleşmesiyle uyumlu güvenli arayüz.

Ders durumları ve yeni özel dersler eski sürümde olduğu gibi anında kaydedilir.
Grup eşleştirmeleri yalnızca bilinçli kaydetmede yazılır; varsayılanlar açılışta
veritabanına gereksiz yere kopyalanmaz. Kayıtlı konular/ödevler silinmez.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QCheckBox, QLabel, QInputDialog, QMessageBox,
    QComboBox, QFrame, QTabWidget, QListWidget, QListWidgetItem, QGroupBox,
    QSplitter, QScrollArea, QLineEdit, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
import db
import unicodedata


def _search_key(value):
    """Türkçe I/İ/ı ve aksan farklılıklarında tutarlı ders araması."""
    normalized = unicodedata.normalize('NFKD', str(value).casefold().replace('ı', 'i'))
    return ''.join(c for c in normalized if not unicodedata.combining(c))



class CurriculumPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.immediate_changes = False
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # V40: Kısa ve tıklanabilir işlem yolu. Yalnızca sunum/navigasyon;
        # eski kaydetme sözleşmesi ve çekirdek ödev ekranları değişmez.
        heading = QHBoxLayout()
        heading.setSpacing(8)
        heading_title = QLabel("Derslerinizi üç adımda yönetin")
        title_font = heading_title.font()
        title_font.setBold(True)
        heading_title.setFont(title_font)
        heading.addWidget(heading_title, 1)
        self.btnHelp = QPushButton("ⓘ Nasıl Kullanılır?")
        self.btnHelp.setAccessibleName("Müfredat ve ders yönetimi kullanım rehberini aç")
        self.btnHelp.setToolTip("Adım adım kullanım ve kaydetme kurallarını gösterir")
        self.btnHelp.clicked.connect(self._show_help)
        heading.addWidget(self.btnHelp)
        root.addLayout(heading)

        steps_frame = QFrame()
        steps_frame.setObjectName("CurriculumSteps")
        # Sistem paletini kullan: koyu/açık temada sabit açık renk dayatma.
        steps_frame.setStyleSheet(
            "QFrame#CurriculumSteps { border: 1px solid palette(mid); "
            "border-radius: 8px; background: palette(alternate-base); } "
            "QPushButton#CurriculumStep { text-align: left; padding: 8px 10px; "
            "border: none; background: transparent; font-weight: 600; } "
            "QPushButton#CurriculumStep:hover { background: palette(midlight); } "
            "QPushButton#CurriculumStep:checked { background: palette(midlight); }"
        )
        quick = QHBoxLayout(steps_frame)
        quick.setContentsMargins(6, 4, 6, 4)
        quick.setSpacing(4)
        self.step_buttons = []
        for index, (label, caption) in enumerate(zip(
            ("1. Dersleri Yönet", "2. Gruplara Ata", "3. Konuları Düzenle"),
            ("Ders ekle veya pasifleştir", "Sınıf için ders seç", "Dersin konularını düzenle")
        )):
            button = QPushButton(f"{label}\n{caption}")
            button.setObjectName("CurriculumStep")
            button.setCheckable(True)
            button.setAccessibleName(label)
            button.setToolTip("İlgili sekmeye geçer; değişiklik kaydetmez")
            button.setMinimumHeight(46)
            button.clicked.connect(lambda _checked=False, i=index: self.tabs.setCurrentIndex(i))
            quick.addWidget(button, 1)
            self.step_buttons.append(button)
            if index < 2:
                arrow = QLabel("→")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                quick.addWidget(arrow)
        root.addWidget(steps_frame)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs, 1)
        self.tab_list = LessonListPage()
        self.tab_mapping = GroupMappingPage()
        self.tabs.addTab(self.tab_list, "Ders Listesi")
        self.tabs.addTab(self.tab_mapping, "Grup Eşleştirmeleri")

        bridge = QWidget()
        bridge_layout = QVBoxLayout(bridge)
        bridge_layout.setContentsMargins(18, 18, 18, 18)
        title_topics = QLabel("Ders ve konu listelerini düzenleyin")
        topics_font = title_topics.font()
        topics_font.setBold(True)
        title_topics.setFont(topics_font)
        bridge_layout.addWidget(title_topics)
        guide = QLabel(
            "Ana ekrandaki Müfredat düğmesiyle aynı konu düzenleyicisi açılır. "
            "Ders → sınıf/grup → konu sırasıyla çalışabilirsiniz. "
            "Kayıtlı ödev ve konu bağlantıları silinmez."
        )
        guide.setWordWrap(True)
        bridge_layout.addWidget(guide)
        open_editor = QPushButton("📚 Ders/Konu Düzenleyicisini Aç")
        open_editor.setToolTip("Ana ekrandaki Müfredat ile aynı editörü açar")
        open_editor.setAccessibleName("Ortak ders ve konu düzenleyicisini aç")
        open_editor.clicked.connect(self._open_topic_editor)
        bridge_layout.addWidget(open_editor)
        bridge_layout.addStretch()
        self.tabs.addTab(bridge, "Konu Düzenle")

        # V38: Salt-okunur entegrasyon görünümü; eski 3 adımlı iş akışı değişmez.
        from ui.curriculum_integration_page_v38 import CurriculumIntegrationPreview
        self.tab_integration = CurriculumIntegrationPreview()
        self.tabs.addTab(self.tab_integration, "Bağlantı Kontrolü")

        # Kaydetme davranışının önemli farkını gizlemeyen kalıcı açıklama.
        self.context_help = QLabel()
        self.context_help.setWordWrap(True)
        self.context_help.setAccessibleName("Seçili müfredat sekmesinin kullanım açıklaması")
        self.context_help.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.context_help)
        note = QLabel(
            "ⓘ Ders ekleme ve aktif/pasif değişikliği ANINDA kaydedilir; "
            "'İptal' bunları geri almaz. Grup ataması ayrıca Kaydet gerektirir."
        )
        note.setWordWrap(True)
        note.setToolTip("Kapatma düğmesi, daha önce anında kaydedilen ders değişikliklerini geri almaz")
        root.addWidget(note)

        self.tab_list.changed.connect(self._on_lesson_changed)
        self.tab_list.request_mapping.connect(lambda: self.tabs.setCurrentIndex(1))
        self.tabs.currentChanged.connect(self._on_tab_change)
        self._on_tab_change(self.tabs.currentIndex())

    def _show_help(self):
        """Yalnızca açıklayıcı yardım: veritabanına erişmez veya kayıt değiştirmez."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Müfredat Yönetimi • Kullanım Rehberi")
        dialog.setMinimumWidth(525)
        body = QVBoxLayout(dialog)
        body.setSpacing(12)
        title = QLabel("Hangi işlemi nereden yapmalıyım?")
        font = title.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize(), 12))
        title.setFont(font)
        body.addWidget(title)
        tips = (
            ("1 • Ders Listesi", "Dersi açın/kapatın veya yeni özel ders oluşturun. "
             "Bu işlemler anında kaydedilir. Pasif dersler yeni listelerde gizlenir; "
             "eski ödevler silinmez."),
            ("2 • Grup Eşleştirmeleri", "Sınıf veya öğrenci grubunu seçin. "
             "Gerekli dersleri işaretleyin ve 'Değişiklikleri Kaydet' düğmesine basın. "
             "Yeni bir özel ders, gruba atanmadıkça öğrenciye otomatik eklenmez."),
            ("3 • Konu Düzenle", "Grup/öğrenci konularını ortak konu düzenleyicisinde "
             "yönetin. Ana ekrandaki 'Müfredat' düğmesi de aynı düzenleyiciyi açar."),
            ("Kontrol • Bağlantılar", "Derslerin kitap, ödev ve koçluk kayıtlarıyla "
             "bağlantılarını sadece görüntüleyin. Bu sekme veri kaydetmez.")
        )
        for title_text, description in tips:
            section = QLabel(f"{title_text}\n{description}")
            section.setWordWrap(True)
            section.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            body.addWidget(section)
        note = QLabel(
            "Önemli: Alt kısımdaki 'İptal', daha önce anında kaydedilen ders açma/kapatma "
            "ve ders ekleme işlemlerini geri almaz. Grup seçimleri ise kaydetmeden uygulanmaz."
        )
        note.setWordWrap(True)
        body.addWidget(note)
        actions = QHBoxLayout()
        for idx, label in enumerate(("Derslere Git", "Grup Atamaya Git", "Konulara Git", "Bağlantıları Gör")):
            b = QPushButton(label)
            b.clicked.connect(lambda _checked=False, i=idx: (dialog.accept(), self.tabs.setCurrentIndex(i)))
            actions.addWidget(b)
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(dialog.reject)
        actions.addWidget(close_button)
        body.addLayout(actions)
        dialog.exec()

    def _on_lesson_changed(self):
        self.immediate_changes = True
        self.tab_mapping.refresh_lessons()

    def _on_tab_change(self, idx):
        contexts = (
            "Ders açma/kapatma anında kaydedilir. Dersinizi ekledikten sonra 2. adımda hangi sınıfa ait olduğunu seçin.",
            "Grup için işaretlediğiniz dersler yalnız 'Değişiklikleri Kaydet' sonrasında uygulanır.",
            "Konu düzenleyicisi, ana ekrandaki Müfredat ile ortaktır. Konuları düzenlemek için aç düğmesini kullanın.",
            "Kitap, ödev ve koçluk bağlantılarının salt-okunur önizlemesi. Yeni kayıt oluşturmaz veya mevcutları değiştirmez."
        )
        if 0 <= idx < len(contexts):
            self.context_help.setText("İpucu: " + contexts[idx])
        for step_index, button in enumerate(self.step_buttons):
            button.setChecked(idx == step_index)
        if idx == 0:
            self.tab_list.refresh()
        elif idx == 1:
            self.tab_mapping.refresh_groups()
            self.tab_mapping.refresh_lessons()
        elif idx == 3:
            self.tab_integration.refresh()

    def _open_topic_editor(self):
        if not self.tab_mapping.confirm_leave():
            return
        # Uygulama-modallik içindeki bağımsız top-level pencere yerine
        # gerçek çocuk QDialog: macOS ve Windows'ta da tıklanabilir kalır.
        from ui.topic_editor import DersKonuEditor
        dialog = QDialog(self)
        dialog.setWindowTitle("Ders/Konu Düzenle")
        dialog.resize(1100, 730)
        layout = QVBoxLayout(dialog)
        editor = DersKonuEditor(dialog)
        layout.addWidget(editor)
        dialog.exec()
        self.tab_list.refresh()
        self.tab_mapping.refresh_lessons()

    def save(self):
        if not self.tab_mapping.save_current(silent=True):
            raise RuntimeError("Grup ders eşleştirmesi kaydedilemedi.")

    def confirm_leave(self):
        return self.tab_mapping.confirm_leave()


class LessonListPage(QWidget):
    changed = pyqtSignal()
    request_mapping = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        info = QLabel(
            "Ders ekleyin, arayın veya durumunu değiştirin. Sistem dersleri silinemez; "
            "pasifleştirme geçmiş ödevleri silmez."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎 Ders adı veya kodu ara...")
        self.search.setAccessibleName("Ders adı veya ders koduyla ara")
        self.search.setToolTip("Örnek: Fizik, LGS, TYT veya ders kimliği")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filters)
        tools.addWidget(self.search, 3)
        self.filter_status = QComboBox()
        self.filter_status.addItems(["Tüm durumlar", "Yalnızca aktif", "Yalnızca pasif"])
        self.filter_status.setAccessibleName("Derslerin aktiflik durumuna göre filtrele")
        self.filter_status.currentIndexChanged.connect(self._apply_filters)
        tools.addWidget(self.filter_status, 1)
        self.filter_group = QComboBox()
        self.filter_group.addItem("Tüm gruplar")
        self.filter_group.setAccessibleName("Dersin üst grubuna göre filtrele")
        self.filter_group.currentIndexChanged.connect(self._apply_filters)
        tools.addWidget(self.filter_group, 1)
        layout.addLayout(tools)

        h = QHBoxLayout()
        h.setSpacing(8)
        self.summary = QLabel("Dersler yükleniyor...")
        self.summary.setWordWrap(True)
        self.summary.setAccessibleName("Ders arama ve filtreleme sonuç sayacı")
        h.addWidget(self.summary, 1)
        reload_button = QPushButton("↻ Yenile")
        reload_button.setToolTip("Ders listesini yeniden veritabanından oku")
        reload_button.clicked.connect(self.refresh)
        h.addWidget(reload_button)
        self.btnMap = QPushButton("Gruba Ata →")
        self.btnMap.setToolTip("Dersin hangi öğrenci gruplarında görüneceğini ayarlayın")
        self.btnMap.clicked.connect(lambda _checked=False: self.request_mapping.emit())
        h.addWidget(self.btnMap)
        self.btnAdd = QPushButton("+ Yeni Özel Ders Ekle")
        self.btnAdd.setObjectName("primary")
        self.btnAdd.setToolTip("Yeni ders oluşturur; kaydı hemen gerçekleşir. Gruba atamayı ayrıca yapmalısınız.")
        self.btnAdd.clicked.connect(self.add_lesson)
        h.addWidget(self.btnAdd)
        layout.addLayout(h)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID (Ders Kodu)", "Görünen Ad", "Grup", "Durum", "Tür"])
        self.table.setAccessibleName("Ders listesi: kod, ad, grup, aktiflik durumu ve tür")
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(29)
        self.table.horizontalHeader().setMinimumHeight(32)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.empty_state = QLabel("Bu arama ve filtrelere uygun ders bulunamadı. Filtreleri değiştirebilirsiniz.")
        self.empty_state.setWordWrap(True)
        self.empty_state.setVisible(False)
        layout.addWidget(self.empty_state)
        self.feedback = QLabel("Dersleri açıp kapattığınızda değişiklikler hemen kaydedilir.")
        self.feedback.setWordWrap(True)
        self.feedback.setAccessibleName("Ders yönetimi işlem sonucu")
        layout.addWidget(self.feedback)
        self._records = {}
        self.refresh()

    def refresh(self):
        conn = db.get_conn()
        try:
            db.init_curriculum(conn)
            config = db.get_lesson_config(conn)
        finally:
            conn.close()
        self._records = config
        current_group = self.filter_group.currentText()
        self.filter_group.blockSignals(True)
        self.filter_group.clear()
        self.filter_group.addItem("Tüm gruplar")
        self.filter_group.addItems(sorted({str(v.get('grup') or 'Genel') for v in config.values()}))
        self.filter_group.setCurrentText(current_group if self.filter_group.findText(current_group) >= 0 else "Tüm gruplar")
        self.filter_group.blockSignals(False)

        self.table.setRowCount(0)
        items = sorted(config.values(), key=lambda x: (str(x.get('grup') or ''), (x.get('siralama') or 999), x.get('ad', '')))
        self.table.setRowCount(len(items))
        for r, item in enumerate(items):
            lid = str(item['id'])
            for col, val in ((0, lid), (1, str(item.get('ad') or lid)),
                             (2, str(item.get('grup') or 'Genel')),
                             (4, '✦ Özel' if item.get('ozel') else '🔒 Sistem')):
                cell = QTableWidgetItem(val)
                if col == 0:
                    cell.setToolTip("Değişmez ders kimliği; geçmiş ödev bağlantıları için korunur")
                if col == 4:
                    cell.setToolTip("Sistem dersleri silinmez" if not item.get('ozel') else "Kullanıcının eklediği özel ders")
                self.table.setItem(r, col, cell)
            chk = QCheckBox("Aktif" if item.get('aktif') else "Pasif")
            chk.setAccessibleName(f"{item['ad']} dersinin aktiflik durumu")
            chk.setToolTip("Bu dersin yeni listelerde gösterilmesini değiştirir; anında kaydedilir. Geçmiş ödevler korunur.")
            chk.setChecked(bool(item.get('aktif')))
            chk.toggled.connect(lambda checked, box=chk: box.setText("Aktif" if checked else "Pasif"))
            chk.toggled.connect(lambda checked, lesson_id=lid: self.toggle_active(lesson_id, checked))
            wrapper = QWidget()
            wl = QHBoxLayout(wrapper)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wl.addWidget(chk)
            self.table.setCellWidget(r, 3, wrapper)
        self._apply_filters()

    def _apply_filters(self, *_):
        query = _search_key(self.search.text().strip())
        status = self.filter_status.currentIndex()
        group = self.filter_group.currentText()
        visible = 0
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is None:
                continue
            rec = self._records.get(item.text(), {})
            active = bool(rec.get('aktif'))
            matching = (query in _search_key(str(rec.get('ad') or '') + ' ' + item.text())
                        and (status == 0 or (active if status == 1 else not active))
                        and (group == 'Tüm gruplar' or str(rec.get('grup') or 'Genel') == group))
            self.table.setRowHidden(r, not matching)
            visible += matching
        active_count = sum(bool(v.get('aktif')) for v in self._records.values())
        self.summary.setText(
            f"{visible} ders gösteriliyor / {len(self._records)} • "
            f"Aktif: {active_count} • Pasif: {len(self._records) - active_count}"
        )
        self.empty_state.setVisible(visible == 0)

    def toggle_active(self, lid, checked):
        try:
            db.update_lesson_status(lid, checked)
        except Exception as exc:
            QMessageBox.warning(self, "Ders durumu kaydedilemedi", str(exc))
            self.refresh()
            return
        if lid in self._records:
            self._records[lid]['aktif'] = int(checked)
        self._apply_filters()
        name = self._records.get(lid, {}).get('ad') or lid
        self.feedback.setText(
            f"✓ {name}: {'Aktif' if checked else 'Pasif'} olarak kaydedildi. "
            "Geçmiş ödevler ve konular korunur."
        )
        self.changed.emit()

    def add_lesson(self):
        name, ok = QInputDialog.getText(self, "Yeni Özel Ders", "Ders adı:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Eksik ders adı", "Lütfen bir ders adı yazın.")
            return
        groups = ["YKS", "LGS", "Ara Sınıf", "Genel"]
        grup, ok = QInputDialog.getItem(self, "Ders Grubu", "Üst grup:", groups, 0, False)
        if not ok:
            return
        result = db.add_custom_lesson(name, grup)
        if result and result[0]:
            self.refresh()
            self.feedback.setText(
                f"✓ {name} oluşturuldu. Şimdi 'Gruba Ata' ile ilgili sınıfın derslerine ekleyin."
            )
            self.changed.emit()
            QMessageBox.information(
                self, "Ders eklendi",
                f"{result[1]}\n\nÖnemli: Yeni ders henüz öğrenci gruplarına atanmadı. "
                "Bu dersin öğrencilerde görünmesi için 'Gruba Ata' bölümünden ilgili grubu seçin."
            )
        else:
            QMessageBox.warning(self, "Ders eklenemedi", str(result[1] if len(result) > 1 else result))


class GroupMappingPage(QWidget):
    """Grup değiştirilirken kaydedilmemiş seçimleri kaybetmeyen atama arayüzü."""
    def __init__(self):
        super().__init__()
        self._loading = False
        self._dirty = False
        self._baseline = set()
        self._hidden_ids = set()
        self.check_map = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        intro = QLabel(
            "Önce öğrenci grubunu, sonra o grupta kullanılacak dersleri seçin. "
            "Seçimler kaydedilmeden uygulanmaz; öğrencilerin eski ödevleri korunur."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        groups = QGroupBox("1. Öğrenci grubunu seçin")
        g_layout = QVBoxLayout(groups)
        self.listGroups = QListWidget()
        self.listGroups.setAccessibleName("Ders tanımlanacak öğrenci grupları")
        self.listGroups.setToolTip("Öğrenci grubunu seçin; kaydedilmemiş seçimler varsa önce size sorulur")
        self.listGroups.currentItemChanged.connect(self.load_mapping)
        g_layout.addWidget(self.listGroups)
        group_guide = QLabel("Bir grubu seçtikten sonra sağda kullanılacak dersleri işaretleyin.")
        group_guide.setWordWrap(True)
        g_layout.addWidget(group_guide)
        splitter.addWidget(groups)

        lessons = QGroupBox("2. Dersleri seçin")
        l_layout = QVBoxLayout(lessons)
        self.lblMode = QLabel("Grup seçiniz")
        self.lblMode.setWordWrap(True)
        self.lblMode.setAccessibleName("Seçili grubun ders ve kaydetme durumu")
        l_layout.addWidget(self.lblMode)
        self.lblGuide = QLabel("Bir grubu seçip ihtiyaç duyduğu dersleri işaretleyin. Öğrencinin eski ödevleri silinmez.")
        self.lblGuide.setWordWrap(True)
        l_layout.addWidget(self.lblGuide)
        self.txtFilter = QLineEdit()
        self.txtFilter.setPlaceholderText("🔎 Ders ara: Fizik, Matematik, TYT...")
        self.txtFilter.setAccessibleName("Gruba atanabilecek dersleri ara")
        self.txtFilter.setClearButtonEnabled(True)
        self.txtFilter.textChanged.connect(self._filter_checks)
        l_layout.addWidget(self.txtFilter)
        selection = QHBoxLayout()
        self.btnAll = QPushButton("Görünenleri Seç")
        self.btnAll.setToolTip("Arama filtresinde görünen dersleri işaretler; diğer seçimler korunur")
        self.btnAll.clicked.connect(lambda: self._select_visible(True))
        self.btnNone = QPushButton("Görünenleri Kaldır")
        self.btnNone.setToolTip("Sadece arama filtresindeki derslerin işaretini kaldırır; kaydetmeden uygulanmaz")
        self.btnNone.clicked.connect(lambda: self._select_visible(False))
        selection.addWidget(self.btnAll)
        selection.addWidget(self.btnNone)
        selection.addStretch()
        l_layout.addLayout(selection)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chkContainer = QWidget()
        self.chkLayout = QVBoxLayout(self.chkContainer)
        self.scroll.setWidget(self.chkContainer)
        l_layout.addWidget(self.scroll, 1)
        buttons = QHBoxLayout()
        self.btnReset = QPushButton("Varsayılan Derslere Dön")
        self.btnReset.setToolTip("Bu gruptaki özel eşleştirmeyi, onayınızla varsayılan gruba döndürür")
        self.btnReset.clicked.connect(self.reset_mapping)
        self.btnSave = QPushButton("Değişiklikleri Kaydet")
        self.btnSave.setToolTip("Yalnızca seçilen öğrenci grubunun ders eşleştirmesini kaydeder")
        self.btnSave.clicked.connect(self.save_mapping)
        buttons.addWidget(self.btnReset)
        buttons.addWidget(self.btnSave)
        l_layout.addLayout(buttons)
        self.lblUnsaved = QLabel("Henüz değişiklik yapılmadı.")
        self.lblUnsaved.setWordWrap(True)
        self.lblUnsaved.setAccessibleName("Kaydedilmemiş ders seçimi sayısı")
        l_layout.addWidget(self.lblUnsaved)
        splitter.addWidget(lessons)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([210, 630])
        root.addWidget(splitter, 1)

        self.refresh_groups()
        self.init_lesson_list()
        if self.listGroups.count():
            self.listGroups.setCurrentRow(0)

    def _group_name(self, item=None):
        item = item or self.listGroups.currentItem()
        return (item.data(Qt.ItemDataRole.UserRole) or item.text()) if item else ''

    def refresh_groups(self):
        selected = self._group_name()
        groups = db.get_curriculum_groups()
        ordered = [g for names in groups.values() for g in names]
        if [self._group_name(self.listGroups.item(i)) for i in range(self.listGroups.count())] == ordered:
            return
        if self._dirty and not self.confirm_leave():
            return
        self.listGroups.blockSignals(True)
        self.listGroups.clear()
        for main, names in groups.items():
            for group_name in names:
                item = QListWidgetItem(group_name)
                item.setData(Qt.ItemDataRole.UserRole, group_name)
                item.setToolTip(f"{main} grubunun ders eşleştirmesi")
                self.listGroups.addItem(item)
        pos = ordered.index(selected) if selected in ordered else 0
        self.listGroups.setCurrentRow(pos if ordered else -1)
        self.listGroups.blockSignals(False)
        self._load_selected()

    def init_lesson_list(self):
        config = db.get_lesson_config()
        items = sorted((v for v in config.values() if v.get('aktif')),
                       key=lambda x: (str(x.get('grup') or ''), (x.get('siralama') or 999), x['ad']))
        while self.chkLayout.count():
            item = self.chkLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.check_map.clear()
        previous_group = None
        for rec in items:
            if rec.get('grup') != previous_group:
                lbl = QLabel(str(rec.get('grup') or 'Genel'))
                font = lbl.font()
                font.setBold(True)
                lbl.setFont(font)
                self.chkLayout.addWidget(lbl)
                previous_group = rec.get('grup')
            checkbox = QCheckBox(str(rec['ad']))
            checkbox.setToolTip(f"Ders kodu: {rec['id']}")
            checkbox.toggled.connect(self._on_changed)
            self.chkLayout.addWidget(checkbox)
            self.check_map[rec['id']] = checkbox
        self.chkLayout.addStretch()
        self._filter_checks()

    def refresh_lessons(self):
        selected_before = self._selected_ids()
        visible_before = set(self.check_map)
        was_dirty = self._dirty
        self.init_lesson_list()
        self._load_selected()
        if was_dirty:
            self._loading = True
            try:
                for lid, check in self.check_map.items():
                    # Yenilenen (eski ekranda bulunmayan) ders varsayılan seçimini korur.
                    if lid in selected_before:
                        check.setChecked(True)
                    elif lid in visible_before:
                        check.setChecked(False)
            finally:
                self._loading = False
            self._on_changed()

    def _load_selected(self):
        group_name = self._group_name()
        self._loading = True
        try:
            ids = db.get_lessons_for_group(group_name) if group_name else []
            is_custom = bool(ids)
            effective = ids if is_custom else db.get_effective_group_lessons(
                group_name, db.get_group_main_group(group_name))
            effective = set(effective)
            self._old_visible_ids = set(self.check_map)
            self._hidden_ids = (set(ids) if is_custom else effective) - set(self.check_map)
            for lid, check in self.check_map.items():
                check.setChecked(lid in effective)
            self._baseline = self._selected_ids()
            self._dirty = False
            self._is_custom = is_custom
        finally:
            self._loading = False
        self._update_state()

    def load_mapping(self, current_item, previous_item):
        if self._loading:
            return
        if previous_item is not None and self._dirty:
            if not self.confirm_leave():
                self.listGroups.blockSignals(True)
                self.listGroups.setCurrentItem(previous_item)
                self.listGroups.blockSignals(False)
                return
        self._load_selected()

    def _selected_ids(self):
        return {lid for lid, check in self.check_map.items() if check.isChecked()}

    def _on_changed(self, *_):
        if not self._loading:
            self._dirty = self._selected_ids() != self._baseline
            self._update_state()

    def _update_state(self):
        group = self._group_name()
        selected_count = len(self._selected_ids())
        mode = 'Özelleştirilmiş' if getattr(self, '_is_custom', False) else 'Varsayılan'
        status = ' • Kaydedilmemiş değişiklik var' if self._dirty else ''
        self.lblMode.setText(f"{group or 'Grup seçiniz'} • {mode} eşleştirme • {selected_count} seçili ders{status}")
        difference = len(self._selected_ids().symmetric_difference(self._baseline))
        if self._dirty:
            self.lblUnsaved.setText(
                f"● {difference} ders seçimi değişti ve henüz kaydedilmedi. "
                "Uygulamak için 'Değişiklikleri Kaydet' düğmesine basın."
            )
        else:
            self.lblUnsaved.setText("✓ Kaydedilmemiş grup değişikliği bulunmuyor.")
        self.btnSave.setEnabled(self._dirty)
        self.btnAll.setEnabled(bool(group))
        self.btnNone.setEnabled(bool(group))
        self.btnReset.setEnabled(bool(group))

    def _filter_checks(self, *_):
        text = _search_key(self.txtFilter.text().strip())
        for check in self.check_map.values():
            check.setVisible(text in _search_key(check.text()))

    def _select_visible(self, select):
        if not self._group_name():
            return
        # Ebeveyn sekme geçici gizliyken QWidget.isVisible() False olur.
        # Bu nedenle seçim kapsamını doğrudan arama metninden belirliyoruz.
        query = _search_key(self.txtFilter.text().strip())
        for check in self.check_map.values():
            if not query or query in _search_key(check.text()):
                check.setChecked(select)

    def _save(self, *, notify):
        if not self._dirty:
            return True
        group = self._group_name()
        if not group:
            return False
        selected = self._selected_ids() | self._hidden_ids
        if not selected:
            if notify:
                QMessageBox.warning(
                    self, "En az bir ders gerekli",
                    "Hiç ders seçmezseniz bu sistemde varsayılan dersler devreye girer. "
                    "Tüm dersleri gizlemek yerine en az bir ders seçin veya "
                    "'Varsayılan Derslere Dön' düğmesini kullanın.")
            return False
        try:
            db.set_lessons_for_group(group, sorted(selected))
        except Exception as exc:
            QMessageBox.critical(self, "Eşleştirme kaydedilemedi", str(exc))
            return False
        self._baseline = self._selected_ids()
        self._is_custom = True
        self._dirty = False
        self._update_state()
        if notify:
            QMessageBox.information(self, "Kaydedildi", f"{group}: {len(selected)} ders eşleştirildi.")
        return True

    def save_mapping(self):
        self._save(notify=True)

    def save_current(self, silent=False):
        return self._save(notify=not silent)

    def confirm_leave(self):
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self, "Kaydedilmemiş ders seçimleri",
            "Bu gruptaki ders seçimleri henüz kaydedilmedi. Ne yapmak istersiniz?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._save(notify=False)
        self._dirty = False
        self._load_selected()
        return True

    def reset_mapping(self):
        group = self._group_name()
        if not group:
            return
        answer = QMessageBox.question(
            self, "Varsayılan derslere dön",
            f"'{group}' grubunun özel ders eşleştirmesi kaldırılacak. "
            "Önceden verilmiş ödevler silinmez. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            db.set_lessons_for_group(group, [])
            self._load_selected()
            QMessageBox.information(self, "Varsayılanlara dönüldü", f"'{group}' grubu varsayılan derslerine döndü.")
        except Exception as exc:
            QMessageBox.critical(self, "Eşleştirme sıfırlanamadı", str(exc))
