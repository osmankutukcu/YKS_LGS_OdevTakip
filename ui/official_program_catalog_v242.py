# -*- coding: utf-8 -*-
"""V24.2 isteğe bağlı kamuya açık program kaydı önizleme penceresi.

Eski hedef analiz/kaydet işlevinden bağımsızdır. Öğrenci verisi okumaz/yazmaz.
"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog,
    QLineEdit, QComboBox, QCheckBox, QHeaderView, QApplication
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from services.target_analysis_v24.program_catalog_v242 import (
    CatalogError, MAX_BYTES, prepare_csv_bytes, preview_import, apply_import,
    list_programs, ProgramRow,
)
from services.target_analysis_v24.catalog_browser_v246 import browse_catalog


class OfficialProgramCatalogDialog(QDialog):
    def __init__(self, catalog_path, *, year: int, on_select=None, parent=None):
        super().__init__(parent)
        self.catalog_path = Path(catalog_path)
        self.year = year
        self.on_select = on_select
        self.prepared = None
        self.preview_stats = None
        self.visible_rows = []
        self.page_index = 0
        self.page_size = 200  # CSV onay önizlemesi
        self.catalog_page_size = 100  # Kaydedilmiş katalog tarayıcısı
        self.catalog_page_index = 0
        self.setWindowTitle(f'Program Kataloğu – {year} (Öğretmen Kontrollü)')
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.resize(min(840, max(420, geo.width()-60)),
                        min(610, max(360, geo.height()-80)))
        layout = QVBoxLayout(self)
        info = QLabel('Kaynak adresi resmî olsa bile CSV içeriği otomatik doğrulanmış sayılmaz. '
                      'Veriler yalnızca öğretmenin kontrolünden sonra ayrı kataloğa alınır; '
                      'öğrenci hedefi, sınav neti ve ödev kayıtları değişmez.')
        info.setWordWrap(True)
        layout.addWidget(info)

        header = QHBoxLayout()
        self.btn_load = QPushButton('CSV Dosyası Önizle')
        self.btn_load.clicked.connect(self._load_file)
        header.addWidget(self.btn_load)
        self.btn_template = QPushButton('CSV Şablonu Kaydet')
        self.btn_template.clicked.connect(self._save_template)
        header.addWidget(self.btn_template)
        layout.addLayout(header)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Program adı / üniversite / kod ara')
        self.search.textChanged.connect(self._filters_changed)
        filters.addWidget(self.search, 1)
        self.score_filter = QComboBox()
        self.score_filter.addItems(['Tümü', 'SAY', 'EA', 'SOZ', 'DIL', 'TYT'])
        self.score_filter.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(self.score_filter)
        self.source_filter = QComboBox()
        self.source_filter.addItems(['Tüm Kaynaklar', 'YÖK Atlas', 'ÖSYM'])
        self.source_filter.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(self.source_filter)
        layout.addLayout(filters)
        self.lbl_status = QLabel('Kaydedilmiş program kataloğu henüz okunmadı.')
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(['Kod', 'Üniversite', 'Program', 'Tür', 'Taban puan', 'Sıra', 'TYT net', 'AYT/YDT net', 'Kaynak'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        layout.addWidget(self.table, 1)
        pages = QHBoxLayout()
        self.btn_prev = QPushButton('‹ Önceki')
        self.btn_prev.clicked.connect(lambda: self._move_page(-1))
        pages.addWidget(self.btn_prev)
        self.lbl_page = QLabel('Kayıtlı katalog görünümü')
        pages.addWidget(self.lbl_page, 1)
        self.btn_next = QPushButton('Sonraki ›')
        self.btn_next.clicked.connect(lambda: self._move_page(1))
        pages.addWidget(self.btn_next)
        layout.addLayout(pages)
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)

        self.approve = QCheckBox('Yalnızca gösterilen sayfaları değil, içe aktarılacak TÜM CSV satırlarını kaynaklarla kontrol ettim.')
        layout.addWidget(self.approve)
        actions = QHBoxLayout()
        self.btn_apply = QPushButton('Onayla ve Kataloğa Ekle')
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._apply)
        actions.addWidget(self.btn_apply)
        self.btn_open = QPushButton('Seçili Resmî Sayfayı Aç')
        self.btn_open.clicked.connect(self._open_source)
        actions.addWidget(self.btn_open)
        self.btn_choose = QPushButton('Hedef Adına Aktar (Netleri Değil)')
        self.btn_choose.clicked.connect(self._choose)
        # Dar Windows ekranlarında üç uzun düğme yan yana taşmasın.
        layout.addLayout(actions)
        layout.addWidget(self.btn_choose)
        self._refresh()

    def _save_template(self):
        path, _ = QFileDialog.getSaveFileName(self, 'CSV şablonunu kaydet', 'program_katalog_sablonu.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            from services.target_analysis_v24.program_catalog_v242 import COLUMNS
            # Boş şablon, gerçek bir program verisi içermez.
            Path(path).write_text(';'.join(COLUMNS) + '\n', encoding='utf-8-sig')
            QMessageBox.information(self, 'Şablon', 'Boş CSV şablonu kaydedildi.')
        except OSError as exc:
            QMessageBox.warning(self, 'Hata', str(exc))

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Program verisi seç', '', 'CSV ve TSV (*.csv *.tsv)')
        if not path:
            return
        self.btn_apply.setEnabled(False)
        self.prepared = None
        self.preview_stats = None
        try:
            if Path(path).stat().st_size > MAX_BYTES:
                raise CatalogError('CSV 2 MB boyut sınırını aşıyor.')
            data = Path(path).read_bytes()
            prepared = prepare_csv_bytes(data, expected_year=self.year)
            stats = preview_import(self.catalog_path, prepared)
            self.prepared, self.preview_stats = prepared, stats
            self.page_index = 0
            self._show_page()
            self.lbl_status.setText(
                f'ÖNİZLEME: {len(prepared.rows)} satır; {stats["new"]} yeni, '
                f'{stats["same"]} aynı, {stats["conflict"]} çelişkili. '
                f'Sayfalara bölünmüş önizleme; toplam {len(prepared.rows)} satır kaydedilecek. SHA-256: {prepared.sha256[:16]}… '
                'Dosya henüz kataloğa yazılmadı.')
            self.btn_apply.setEnabled(stats['conflict'] == 0 and stats['new'] > 0)
            self.approve.setChecked(False)
        except (OSError, CatalogError) as exc:
            QMessageBox.warning(self, 'CSV reddedildi', str(exc))
            self._refresh()

    def _move_page(self, delta):
        if self.prepared is not None:
            self.page_index = max(0, self.page_index + delta)
            self._show_page()
        else:
            self.catalog_page_index = max(0, self.catalog_page_index + delta)
            self._refresh()

    def _show_page(self):
        if self.prepared is None:
            return
        total = len(self.prepared.rows)
        pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.page_index = min(max(self.page_index, 0), pages - 1)
        start = self.page_index * self.page_size
        self._fill_rows(self.prepared.rows[start:start + self.page_size])
        self.lbl_page.setText(f'Önizleme {self.page_index + 1}/{pages} – satır {start + 1}–{min(total, start + self.page_size)} / {total}')
        self.btn_prev.setEnabled(self.page_index > 0)
        self.btn_next.setEnabled(self.page_index < pages - 1)

    def _fill_rows(self, rows):
        self.visible_rows = list(rows)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            vals = [row.program_code, row.university, row.program, row.score_type,
                    '' if row.min_score is None else str(row.min_score),
                    '' if row.min_rank is None else str(row.min_rank),
                    '' if row.tyt_net is None else str(row.tyt_net),
                    '' if row.second_net is None else str(row.second_net), row.source]
            for j, val in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(val))
        self.table.resizeColumnsToContents()

    def _filters_changed(self, *_):
        self.catalog_page_index = 0
        self._refresh()

    def _refresh(self, *_):
        # CSV onay önizlemesini başka verilerle karıştırmayın.
        if self.prepared is not None:
            return
        try:
            selected_score = self.score_filter.currentText()
            source = ('', 'YOK_ATLAS', 'OSYM')[self.source_filter.currentIndex()]
            result = browse_catalog(
                self.catalog_path, year=self.year,
                page=self.catalog_page_index, page_size=self.catalog_page_size,
                score_type='' if selected_score == 'Tümü' else selected_score,
                source=source, query=self.search.text())
            self.catalog_page_index = result.page
            self._fill_rows(result.rows)
            self.lbl_page.setText(
                f'Katalog {result.page + 1}/{result.pages} – '
                f'{result.total} eşleşen kayıt')
            self.btn_prev.setEnabled(result.page > 0)
            self.btn_next.setEnabled(result.page + 1 < result.pages)
            self.lbl_status.setText(
                f'{result.total} eşleşen program, sayfa başına {result.page_size}. '
                'Kayıtlar öğretmen kontrollü aktarılmıştır; '
                'resmî içerikle bağımsız doğrulanmamıştır.')
        except CatalogError as exc:
            self._fill_rows([])
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.lbl_page.setText('Katalog okunamadı')
            self.lbl_status.setText('Katalog okunamadı: ' + str(exc))

    def _selected(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.visible_rows):
            QMessageBox.information(self, 'Program seçimi', 'Önce bir program satırını seçin.')
            return None
        return self.visible_rows[index]

    def _open_source(self):
        row = self._selected()
        if row:
            # Kaynak daha önce URL + program kodu ile sıkı doğrulanmıştır.
            from services.target_analysis_v24.program_catalog_v242 import _source_url
            try:
                _source_url(row.source_url, row.program_code, row.year, row.source)
                QDesktopServices.openUrl(QUrl(row.source_url))
            except CatalogError as exc:
                QMessageBox.warning(self, 'Geçersiz kaynak', str(exc))

    def _choose(self):
        if self.prepared is not None:
            QMessageBox.warning(self, 'Önizleme',
                'Henüz kaydedilmemiş CSV önizlemesinden hedef seçilemez. Önce katalog aktarımını onaylayın.')
            return
        row = self._selected()
        if row and self.on_select:
            if self.on_select(row):
                self.accept()

    def _apply(self):
        if not self.prepared or not self.preview_stats:
            return
        if not self.approve.isChecked():
            QMessageBox.warning(self, 'Onay gerekli', 'Önce kaynak satırlarını kontrol edip onaylayın.')
            return
        resp = QMessageBox.question(
            self, 'Kataloğa kaydet',
            f'{self.preview_stats["new"]} yeni kamuya açık program kaydı eklenecek. '
            'Bu işlem öğrenci hedeflerini değiştirmez. Devam edilsin mi?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            stats = apply_import(self.catalog_path, self.prepared,
                                 approved_hash=self.prepared.sha256,
                                 expected_stats=self.preview_stats)
            self.prepared = None
            self.preview_stats = None
            self.btn_apply.setEnabled(False)
            self.approve.setChecked(False)
            self._refresh()
            QMessageBox.information(self, 'İçe aktarıldı', f'{stats["new"]} yeni kayıt eklendi.')
        except Exception as exc:
            QMessageBox.warning(self, 'İşlem yapılmadı', str(exc))
