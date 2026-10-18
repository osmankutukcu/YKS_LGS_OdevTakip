# -*- coding: utf-8 -*-
"""Small on-demand editor for teacher-reviewed coaching references.

No automatic publication and no connection to student SQLite. V12.7 checks a fixed public-site catalog only after a teacher click.
"""
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QListWidget, QLineEdit, QTextEdit, QComboBox,
    QMessageBox, QFileDialog, QTabWidget, QWidget, QSplitter, QScrollArea, QFrame)
from services.coach_assistant_v1.knowledge_manager_v126 import ReviewStore, CATEGORIES
from services.coach_assistant_v1.official_sources_v127 import (
    SOURCES, SourceCache, check_source, catalog_entry)

_RUNNING_SOURCE_WORKERS = set()

class OfficialCheckThread(QThread):
    result_ready = pyqtSignal(object)
    failed = pyqtSignal(str)
    def __init__(self, source_id):
        super().__init__()
        self.source_id=source_id
    def run(self):
        try:self.result_ready.emit(check_source(self.source_id))
        except (ConnectionError,ValueError,OSError) as exc:self.failed.emit(str(exc))


LABELS={'coaching':'Koçluk','homework':'Ödev Takibi','assessment':'Ölçme ve Değerlendirme',
        'planning':'Planlama','learning_science':'Öğrenme Bilimi','pedagogy':'Pedagoji',
        'error_analysis':'Hata Analizi','student_support':'Öğrenci Desteği','methodology':'Yöntemler'}

class CoachKnowledgeManagerV126(QDialog):
    def __init__(self, parent=None, store_path=None):
        super().__init__(parent)
        self.store = ReviewStore(store_path)
        self.setWindowTitle('Koç Asistanı · Bilgi Kütüphanesi')
        self.setMinimumSize(600, 420)
        self.resize(780, 540)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
            }
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background: #ffffff;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #e2e8f0;
                color: #475569;
                padding: 6px 14px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f172a;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-bottom: none;
            }
            QListWidget {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-size: 11px;
                padding: 4px;
            
                color: #15191E;}
            QListWidget::item {
                padding: 5px 8px;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background: #e0f2fe;
                color: #0369a1;
                font-weight: 600;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 4px 7px;
                font-size: 11px;
                color: #1e293b;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1.5px solid #3b82f6;
                background: #ffffff;
            }
            QLabel {
                color: #334155;
                font-size: 11px;
            }
            QPushButton {
                font-size: 11px;
                padding: 5px 10px;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        heading = QLabel('📚 Bilgi Kütüphanesi · Onaylı İçerik ve Belge İnceleme')
        heading.setStyleSheet('font-weight: 700; font-size: 13px; color: #0f172a;')
        layout.addWidget(heading)

        note = QLabel('Belgeler önce taslaktır. Öğrenci verilerini içeren belgeleri buraya yüklemeyin. Öğretmen onayı bilimsel doğrulama değildir.')
        note.setStyleSheet('color: #64748b; font-size: 10px;')
        note.setWordWrap(True)
        layout.addWidget(note)

        actions = QHBoxLayout()
        self.import_button = QPushButton('＋ Belge ekle (taslak)')
        self.import_button.setStyleSheet('background: #0284c7; color: white; font-weight: 600; padding: 5px 12px;')
        self.import_button.clicked.connect(self._import)
        actions.addWidget(self.import_button)

        self.refresh_button = QPushButton('↻ Yenile')
        self.refresh_button.setStyleSheet('background: #f1f5f9; border: 1px solid #cbd5e1; color: #334155;')
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.refresh_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # TAB 1: İnceleme taslakları
        draft = QWidget()
        draft_outer = QVBoxLayout(draft)
        draft_outer.setContentsMargins(4, 4, 4, 4)
        draft_outer.setSpacing(0)

        draft_splitter = QSplitter(Qt.Orientation.Horizontal)
        draft_splitter.setChildrenCollapsible(False)

        # Left: Drafts list
        left_holder = QWidget()
        left_layout = QVBoxLayout(left_holder)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)
        lbl_drafts = QLabel('İnceleme Bekleyen Taslaklar:')
        lbl_drafts.setStyleSheet('font-weight: 600; color: #475569;')
        left_layout.addWidget(lbl_drafts)
        self.drafts = QListWidget()
        self.drafts.setMinimumWidth(160)
        self.drafts.currentRowChanged.connect(self._selected_draft)
        left_layout.addWidget(self.drafts, 1)
        draft_splitter.addWidget(left_holder)

        # Right: Form inside ScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        form_holder = QWidget()
        form = QVBoxLayout(form_holder)
        form.setContentsMargins(8, 6, 8, 8)
        form.setSpacing(8)

        lbl_excerpt = QLabel('📄 Belgeden Alınan Ham Metin (Etkin değildir):')
        lbl_excerpt.setStyleSheet('font-weight: 600; color: #475569;')
        form.addWidget(lbl_excerpt)
        self.excerpt = QTextEdit()
        self.excerpt.setReadOnly(True)
        self.excerpt.setMinimumHeight(55)
        self.excerpt.setMaximumHeight(85)
        self.excerpt.setStyleSheet('background: #f8fafc; border: 1px solid #e2e8f0; color: #475569;')
        form.addWidget(self.excerpt)

        details = QFormLayout()
        details.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        details.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        details.setHorizontalSpacing(8)
        details.setVerticalSpacing(6)

        self.title_input = QLineEdit()
        self.title_input.setMaxLength(150)
        self.title_input.setMinimumHeight(26)

        self.category = QComboBox()
        self.category.setMinimumHeight(26)
        for code, label in LABELS.items():
            self.category.addItem(label, code)

        self.keywords = QLineEdit()
        self.keywords.setPlaceholderText('Virgülle ayırın: erteleme, planlama')
        self.keywords.setMaxLength(250)
        self.keywords.setMinimumHeight(26)

        self.guidance = QTextEdit()
        self.guidance.setMinimumHeight(55)
        self.guidance.setMaximumHeight(80)

        self.question = QLineEdit()
        self.question.setMaxLength(250)
        self.question.setMinimumHeight(26)

        self.caution = QLineEdit()
        self.caution.setMaxLength(350)
        self.caution.setMinimumHeight(26)

        for label, field in [
            ('Başlık:', self.title_input),
            ('Kategori:', self.category),
            ('Anahtar kelimeler:', self.keywords),
            ('Kısa öneri:', self.guidance),
            ('Görüşme sorusu:', self.question),
            ('Sınırlama / uyarı:', self.caution)
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet('font-weight: 600; color: #475569;')
            details.addRow(lbl, field)
        form.addLayout(details)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(6)
        self.approve_button = QPushButton('✔ İnceledim · Rehber Olarak Etkinleştir')
        self.approve_button.setStyleSheet('background: #059669; color: white; font-weight: 600; padding: 6px 12px; border: none;')
        self.approve_button.setToolTip('Bu işlem bilimsel geçerlilik anlamına gelmez; yalnızca sizin kısa rehberinizi etkinleştirir.')
        self.approve_button.clicked.connect(self._approve)
        btn_box.addWidget(self.approve_button, 2)

        self.discard_button = QPushButton('🗑 Bu Taslağı Sil')
        self.discard_button.setStyleSheet('background: #fee2e2; color: #ca2323; border: 1px solid #fca5a5; font-weight: 500; padding: 6px 10px;')
        self.discard_button.clicked.connect(self._discard)
        btn_box.addWidget(self.discard_button, 1)
        form.addLayout(btn_box)

        scroll_area.setWidget(form_holder)
        draft_splitter.addWidget(scroll_area)
        draft_splitter.setSizes([220, 500])

        draft_outer.addWidget(draft_splitter)
        self.tabs.addTab(draft, 'İnceleme taslakları')

        # TAB 2: Etkin rehberler
        approved = QWidget()
        approved_layout = QVBoxLayout(approved)
        approved_layout.setContentsMargins(8, 8, 8, 8)
        approved_layout.setSpacing(6)
        lbl_act = QLabel('Asistan yanıtlarında kullanılan aktif öğretmen rehberleri:')
        lbl_act.setStyleSheet('font-weight: 600; color: #475569;')
        approved_layout.addWidget(lbl_act)
        self.active = QListWidget()
        approved_layout.addWidget(self.active, 1)
        retire = QPushButton('Seçili rehberi pasifleştir')
        retire.setStyleSheet('background: #fff1f2; color: #d81c45; border: 1px solid #fecdd3; padding: 6px 12px; font-weight: 600;')
        retire.clicked.connect(self._retire)
        approved_layout.addWidget(retire)
        self.tabs.addTab(approved, 'Etkin rehberler')

        # TAB 3: Resmî Kaynaklar
        self.source_cache = SourceCache()
        sources_page = QWidget()
        sources_layout = QVBoxLayout(sources_page)
        sources_layout.setContentsMargins(8, 8, 8, 8)
        sources_layout.setSpacing(6)
        description = QLabel('Resmî kaynakları yalnızca siz istediğinizde kontrol eder. Sayfa değişimi bilimsel doğruluk veya yeni materyal kanıtı değildir. Öğrenci bilgisi gönderilmez.')
        description.setStyleSheet('color: #64748b; font-size: 10px;')
        description.setWordWrap(True)
        sources_layout.addWidget(description)

        src_splitter = QSplitter(Qt.Orientation.Vertical)
        src_splitter.setChildrenCollapsible(False)

        self.official_sites = QListWidget()
        for sid, meta in SOURCES.items():
            self.official_sites.addItem(meta['name'] + ' · ' + meta['description'])
        self.official_sites.currentRowChanged.connect(self._selected_source)
        src_splitter.addWidget(self.official_sites)

        src_bottom = QWidget()
        src_bottom_layout = QVBoxLayout(src_bottom)
        src_bottom_layout.setContentsMargins(0, 4, 0, 0)
        src_bottom_layout.setSpacing(6)

        self.source_details = QTextEdit()
        self.source_details.setReadOnly(True)
        self.source_details.setMinimumHeight(70)
        src_bottom_layout.addWidget(self.source_details, 1)

        web_buttons = QHBoxLayout()
        web_buttons.setSpacing(6)
        self.source_check_btn = QPushButton('↻ Kaynağı kontrol et')
        self.source_check_btn.setStyleSheet('background: #0284c7; color: white; font-weight: 500;')
        self.source_check_btn.clicked.connect(self._check_source)

        self.source_open_btn = QPushButton('↗ Resmî siteyi aç')
        self.source_open_btn.setStyleSheet('background: #f1f5f9; border: 1px solid #cbd5e1; color: #334155;')
        self.source_open_btn.clicked.connect(self._open_source)

        self.source_draft_btn = QPushButton('📥 İnceleme taslağına al')
        self.source_draft_btn.setStyleSheet('background: #f1f5f9; border: 1px solid #cbd5e1; color: #334155;')
        self.source_draft_btn.clicked.connect(self._source_to_draft)

        for btn in (self.source_check_btn, self.source_open_btn, self.source_draft_btn):
            web_buttons.addWidget(btn)
        src_bottom_layout.addLayout(web_buttons)
        src_splitter.addWidget(src_bottom)
        src_splitter.setSizes([100, 160])

        sources_layout.addWidget(src_splitter, 1)
        self.tabs.addTab(sources_page, '🌐 Resmî Kaynaklar')

        self._source_worker = None
        self.official_sites.setCurrentRow(0)
        self._draft_rows = []
        self._approved_rows = []
        self.refresh()

    def refresh(self):
        try:
            self._draft_rows=self.store.list_entries('draft')
            self._approved_rows=self.store.list_entries('reviewed')
        except (ValueError,OSError,RuntimeError) as exc:
            QMessageBox.warning(self,'Kütüphane okunamadı',str(exc));return
        self.drafts.clear();self.active.clear()
        for e in self._draft_rows:self.drafts.addItem((e.get('source_name') or 'Belge')+' · '+str(e.get('original_excerpt',''))[:65])
        for e in self._approved_rows:self.active.addItem((e.get('title') or '')+' · '+(e.get('source_name') or 'Kaynak'))
        if self._draft_rows:self.drafts.setCurrentRow(0)
        else:self._selected_draft(-1)

    def _selected_draft(self,index):
        if index<0 or index>=len(self._draft_rows):
            self.excerpt.clear();self.title_input.clear();self.keywords.clear()
            self.guidance.clear();self.question.clear();self.caution.clear()
            self.approve_button.setEnabled(False);self.discard_button.setEnabled(False);return
        e=self._draft_rows[index]
        self.excerpt.setPlainText(e.get('original_excerpt',''))
        self.title_input.setText(e.get('title',''))
        self.keywords.setText(e.get('keywords',''))
        self.guidance.setPlainText(e.get('guidance',''))
        self.question.setText(e.get('teacher_question',''))
        self.caution.setText(e.get('caution',''))
        self.approve_button.setEnabled(True);self.discard_button.setEnabled(True)

    def _import(self):
        path,_=QFileDialog.getOpenFileName(self,'İnceleme için belge seçin','','Belgeler (*.docx *.txt *.md)')
        if not path:return
        answer=QMessageBox.question(self,'Belge kontrolü',
           'Belgede kişisel öğrenci verisi bulunmadığını ve bu belgeden yalnızca pasif taslak oluşturulacağını onaylıyor musunuz?')
        if answer!=QMessageBox.StandardButton.Yes:return
        try:n=self.store.import_document(path)
        except (ValueError,OSError,RuntimeError) as exc:QMessageBox.warning(self,'İçe aktarma durduruldu',str(exc));return
        self.refresh();QMessageBox.information(self,'Taslak oluşturuldu',f'{n} bölüm inceleme taslağına alındı. Henüz asistan yanıtlarında kullanılmıyor.')

    def _approve(self):
        i=self.drafts.currentRow()
        if not 0<=i<len(self._draft_rows):return
        prompt='Bu önerinin öğrenciye özel teşhis olmadığını; metnin doğruluğu, izinleri ve yaş grubuna uygunluğunu kontrol ettiğinizi onaylıyor musunuz?'
        if QMessageBox.question(self,'Öğretmen incelemesi',prompt)!=QMessageBox.StandardButton.Yes:return
        try:
            self.store.review(self._draft_rows[i]['id'],title=self.title_input.text(),category=self.category.currentData(),
                keywords=self.keywords.text(),guidance=self.guidance.toPlainText(),
                teacher_question=self.question.text(),caution=self.caution.text())
        except (ValueError,OSError,RuntimeError) as exc:
            QMessageBox.warning(self,'Kayıt yapılamadı',str(exc));return
        self.refresh();QMessageBox.information(self,'Rehber etkin','Öğretmen incelemesinden geçmiş kısa rehber artık ilgili sorularda kullanılabilir.')

    def _discard(self):
        i=self.drafts.currentRow()
        if not 0<=i<len(self._draft_rows):return
        if QMessageBox.question(self,'Taslağı sil','Bu inceleme taslağı silinsin mi? Etkin rehberler etkilenmez.') != QMessageBox.StandardButton.Yes:return
        try:self.store.discard_draft(self._draft_rows[i]['id'])
        except (ValueError,OSError,RuntimeError) as exc:
            QMessageBox.warning(self,'Taslak silinemedi',str(exc));return
        self.refresh()

    def _retire(self):
        i=self.active.currentRow()
        if not 0<=i<len(self._approved_rows):return
        if QMessageBox.question(self,'Rehberi pasifleştir','Bu bilgi bundan sonra asistan yanıtlarında kullanılmasın mı?')!=QMessageBox.StandardButton.Yes:return
        try:self.store.retire(self._approved_rows[i]['id'])
        except (ValueError,OSError,RuntimeError) as exc:QMessageBox.warning(self,'İşlem yapılamadı',str(exc));return
        self.refresh()

    def _current_source_id(self):
        index=self.official_sites.currentRow()
        return list(SOURCES)[index] if 0<=index<len(SOURCES) else None

    def _selected_source(self,_index):
        sid=self._current_source_id()
        if sid is None:
            self.source_details.setPlainText('Kaynak seçin')
            self.source_draft_btn.setEnabled(False)
            return
        try:record=self.source_cache.get(sid)
        except (OSError,ValueError) as exc:
            self.source_details.setPlainText('Önbellek okunamadı: '+str(exc));return
        self.source_draft_btn.setEnabled(record is not None)
        if record is None:
            self.source_details.setPlainText('Henüz kontrol edilmedi. Kaynak: '+SOURCES[sid]['url'])
            return
        status={'first_check':'İlk kontrol','changed':'Sayfa değişmiş','unchanged':'Sayfa değişmemiş'}.get(record.get('change_status'),'Kontrol kaydı')
        when=str(record.get('checked_at',''))[:19].replace('T',' ')
        declared=record.get('declared_publish_date') or 'Sayfada belirtilmemiş'
        self.source_details.setPlainText(
            'Kaynak: '+record['url']+'\nKontrol: '+when+' UTC'
            +'\nSayfanın belirttiği yayın tarihi: '+declared
            +'\nDurum: '+status+' (sayfa düzeyi karşılaştırma)'
            +'\nBaşlık: '+str(record.get('title',''))[:180]
            +'\nÖnizleme (otomatik doğrulanmamış): '+str(record.get('excerpt',''))[:500])

    def _check_source(self):
        sid=self._current_source_id()
        if sid is None or (self._source_worker is not None and self._source_worker.isRunning()):return
        self.source_check_btn.setEnabled(False)
        self.source_check_btn.setText('Bağlantı kontrol ediliyor…')
        self.source_details.setPlainText('Yalnızca resmî sitenin genel sayfası kontrol ediliyor; öğrenci verisi gönderilmiyor.')
        worker=OfficialCheckThread(sid)
        self._source_worker=worker
        _RUNNING_SOURCE_WORKERS.add(worker)
        worker.result_ready.connect(self._source_success)
        worker.failed.connect(self._source_failure)
        worker.finished.connect(lambda w=worker:self._source_finished(w))
        worker.start()

    def _source_success(self,record):
        try:
            self.source_cache.put(record)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Kaynak kaydedilemedi',str(exc))
        self._selected_source(0)

    def _source_failure(self,message):
        QMessageBox.warning(self,'Çevrim içi kontrol başarısız',
            message+'\nEski kayıt varsa tarihini kontrol edin; çevrim dışı bilgi güncel sayılmaz.')
        self._selected_source(0)

    def _source_finished(self,worker):
        _RUNNING_SOURCE_WORKERS.discard(worker)
        if self._source_worker is worker:
            self._source_worker=None
            self.source_check_btn.setEnabled(True)
            self.source_check_btn.setText('↻ Kaynağı kontrol et')

    def _open_source(self):
        sid=self._current_source_id()
        if sid is not None:
            QDesktopServices.openUrl(QUrl(catalog_entry(sid)['url']))

    def _source_to_draft(self):
        sid=self._current_source_id()
        if sid is None:return
        try:record=self.source_cache.get(sid)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'Kaynak okunamadı',str(exc));return
        if not record:
            QMessageBox.information(self,'Kontrol gerekli','Önce resmî kaynak kontrolü yapın.');return
        question=('Bu resmî web sayfasındaki kısa önizleme yalnızca taslağa alınacak. '
                  'Asistan bunu siz inceleyip kısa rehber oluşturana kadar kullanmayacak. Devam edilsin mi?')
        if QMessageBox.question(self,'Kaynak inceleme',question)!=QMessageBox.StandardButton.Yes:return
        try:added=self.store.import_official_snapshot(record)
        except (ValueError,OSError,RuntimeError) as exc:
            QMessageBox.warning(self,'Taslak eklenemedi',str(exc));return
        self.refresh()
        self.tabs.setCurrentIndex(0)
        QMessageBox.information(self,'İnceleme taslağı',
            'Kaynak taslaklara eklendi.' if added else 'Aynı sayfanın aynı sürümü daha önce eklenmiş.')
