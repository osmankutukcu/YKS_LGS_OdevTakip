"""Isolated PyQt6 file import preview; main trial-exam UI stays intact."""
from __future__ import annotations

import csv
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView)
from services.trial_exam_import_v17 import parse_file, prepare, apply, ExamImportError


class TrialExamImportDialog(QDialog):
    def __init__(self, connection_factory, exam_id: int, subjects: list[str], parent=None):
        super().__init__(parent)
        self.connection_factory = connection_factory
        self.exam_id = exam_id
        self.subjects = tuple(subjects)
        self.preview = None
        self.setWindowTitle('📥 Deneme Sonuçlarını Güvenle İçe Aktar')
        self.resize(940, 570)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('CSV / XLSX → doğrulama → önizleme → öğretmen onayı.\n'
                                'Var olan öğrencilerin diğer deneme sonuçları korunur.'))
        bar = QHBoxLayout()
        self.open_btn = QPushButton('📂 CSV / Excel Seç')
        self.open_btn.clicked.connect(self._choose)
        self.template_btn = QPushButton('Boş CSV Şablonu')
        self.template_btn.clicked.connect(self._template)
        bar.addWidget(self.open_btn); bar.addWidget(self.template_btn); bar.addStretch()
        layout.addLayout(bar)
        self.summary = QLabel('Henüz dosya seçilmedi.')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Satır','Öğrenci ID','Ders','Doğru / Yanlış','Durum','Açıklama'])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        foot = QHBoxLayout(); foot.addStretch()
        self.cancel_btn = QPushButton('Kapat'); self.cancel_btn.clicked.connect(self.reject)
        self.apply_btn = QPushButton('✅ Doğrulanan Değişiklikleri Kaydet')
        self.apply_btn.setEnabled(False); self.apply_btn.clicked.connect(self._apply)
        foot.addWidget(self.cancel_btn);foot.addWidget(self.apply_btn);layout.addLayout(foot)

    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Deneme sonuçlarını seç', '',
                    'Sonuç dosyaları (*.csv *.tsv *.xlsx);;Tüm dosyalar (*)')
        if path:
            self.load(path)

    def load(self, path):
        self.preview = None
        self.apply_btn.setEnabled(False)
        self.table.setRowCount(0)
        try:
            records = parse_file(path)
            con = self.connection_factory()
            try:
                preview = prepare(con, self.exam_id, self.subjects, records)
            finally:
                con.close()
            self.preview = preview
            counts = preview.counts
            self.summary.setText(f'Dosya: {Path(path).name} | Yeni: {counts["new"]} | '
                f'Güncellenecek: {counts["update"]} | Aynı: {counts["same"]} | '
                f'Hata: {len(preview.errors)}\n'
                'Not: Eşleşmeyen veya mükerrer satırlar varsa hiçbir kayıt yazılmaz.')
            rows = list(preview.changes)
            visible = min(len(rows), 400)
            self.table.setRowCount(visible + min(len(preview.errors), 50))
            for i, ch in enumerate(rows[:visible]):
                s = ch.item
                vals = (s.source_row, s.student_id, s.subject, f'{s.correct} / {s.wrong}',
                        {'new':'Yeni','update':'Değişecek','same':'Aynı'}[ch.status], '')
                for j,val in enumerate(vals):self.table.setItem(i,j,QTableWidgetItem(str(val)))
            for i,err in enumerate(preview.errors[:50], visible):
                self.table.setItem(i,4,QTableWidgetItem('HATA'))
                self.table.setItem(i,5,QTableWidgetItem(err))
            self.apply_btn.setEnabled(not preview.errors and counts['new']+counts['update'] > 0)
        except Exception as e:
            self.summary.setText(f'İçe aktarma hatası: {e}')
            self.table.setRowCount(0)

    def _apply(self):
        if self.preview is None or self.preview.errors:
            return
        try:
            con = self.connection_factory()
            try: counts = apply(con, self.exam_id, self.preview)
            finally: con.close()
        except Exception as exc:
            QMessageBox.warning(self, 'Kaydetme durduruldu', str(exc))
            return
        QMessageBox.information(self, 'Deneme sonuçları kaydedildi',
            f'{counts["new"]} yeni, {counts["update"]} güncellenen, '
            f'{counts["same"]} değişmeyen kayıt.\nDiğer sonuçlara dokunulmadı.')
        self.accept()

    def _template(self):
        path, _ = QFileDialog.getSaveFileName(self,'Boş CSV şablonunu kaydet',
                                             'deneme_sonuc_sablon.csv','CSV (*.csv)')
        if not path:return
        try:
            with open(path, 'w', encoding='utf-8-sig', newline='') as stream:
                csv.writer(stream).writerow(['ogrenci_id','ad_soyad','ders','dogru','yanlis','bos'])
        except OSError as exc:
            QMessageBox.warning(self,'Dosya hatası',str(exc))
