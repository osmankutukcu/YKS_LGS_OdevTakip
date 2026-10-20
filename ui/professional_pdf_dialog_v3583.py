# -*- coding: utf-8 -*-
"""Opt-in report creator. Works alongside all legacy print/PDF paths."""
from __future__ import annotations
from datetime import date
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFrame, QTextEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

from services.professional_pdf_v3583 import get_report_snapshot, export_professional_pdf


class ProfessionalPDFDialog(QDialog):
    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self.setWindowTitle('KoçPilot 360 • Profesyonel PDF (Pilot)')
        self.setMinimumSize(640, 540)
        self.resize(760, 610)
        self._snapshot = None
        self._last_file = None
        self._build()
        self._fill_students()
        self._preview()

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 18, 20, 18)
        main.setSpacing(10)
        banner = QFrame(self)
        banner.setStyleSheet('QFrame { background: #17263f; border-radius: 10px; }'
                             'QLabel { color: #ffffff; background: transparent; }')
        head = QVBoxLayout(banner)
        title = QLabel('Profesyonel PDF Atölyesi  ·  PİLOT')
        title.setStyleSheet('font-size: 19px; font-weight: 800;')
        title.setWordWrap(True)
        head.addWidget(title)
        subtitle = QLabel('Öğrenciyi, dönemi ve rapor tipini seçin. PDF’yi oluşturmadan önce içerik özetini kontrol edin.')
        subtitle.setWordWrap(True)
        head.addWidget(subtitle)
        main.addWidget(banner)

        filters = QHBoxLayout()
        filters.addWidget(QLabel('Öğrenci'))
        self.students = QComboBox(self)
        self.students.setMinimumWidth(220)
        filters.addWidget(self.students, 2)
        filters.addWidget(QLabel('Dönem'))
        self.period = QComboBox(self)
        for day in (7, 30, 90):
            self.period.addItem(f'Son {day} gün', day)
        self.period.setCurrentIndex(1)
        filters.addWidget(self.period, 1)
        main.addLayout(filters)

        reports = QHBoxLayout()
        reports.addWidget(QLabel('Rapor'))
        self.template = QComboBox(self)
        self.template.addItem('Veli Bilgilendirme (tek sayfa hedefi)', 'veli')
        self.template.addItem('Öğretmen Gelişim (detaylı)', 'ogretmen')
        self.template.addItem('Bütünleşik Öğrenci 360 (Pilot · 2+ sayfa)', 'butunlesik')
        reports.addWidget(self.template, 1)
        main.addLayout(reports)

        lbl = QLabel('Kaydedilmeden önce veri özeti')
        lbl.setStyleSheet('font-weight: 700; padding-top: 10px;')
        main.addWidget(lbl)
        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName('Raporun hesaplama özeti ve veri uyarıları')
        main.addWidget(self.preview, 1)
        note = QLabel('Önemli: Ödev oranı sınav başarısı değildir. Yalnızca seçilen dönemde teslim tarihi gelmiş görevler kullanılır. Eski raporlar değiştirilmez.')
        note.setWordWrap(True)
        note.setStyleSheet('color: #475569; font-size: 11px;')
        main.addWidget(note)

        buttons = QHBoxLayout()
        self.refresh = QPushButton('↻ Yeniden Hesapla')
        buttons.addWidget(self.refresh)
        buttons.addStretch(1)
        self.page_preview = QPushButton('🔍 PDF Sayfa Önizlemesi')
        buttons.addWidget(self.page_preview)
        self.open_pdf = QPushButton('Son PDF’yi Aç')
        self.open_pdf.setEnabled(False)
        buttons.addWidget(self.open_pdf)
        self.close = QPushButton('Kapat')
        buttons.addWidget(self.close)
        self.save = QPushButton('PDF Oluştur…')
        self.save.setStyleSheet('background: #2563eb; color: #fff; padding: 8px 18px; font-weight: 700;')
        buttons.addWidget(self.save)
        main.addLayout(buttons)
        self.students.currentIndexChanged.connect(self._preview)
        self.period.currentIndexChanged.connect(self._preview)
        self.template.currentIndexChanged.connect(self._preview)
        self.refresh.clicked.connect(self._preview)
        self.save.clicked.connect(self._save)
        self.open_pdf.clicked.connect(self._open_pdf)
        self.page_preview.clicked.connect(self._preview_pages)
        self.close.clicked.connect(self.accept)

    def _fill_students(self):
        try:
            rows = self.con.execute('SELECT id, ad, soyad, COALESCE(alt_grup, \'\') '
                                    'FROM ogrenci WHERE COALESCE(aktif,1)=1 '
                                    'ORDER BY ad COLLATE NOCASE, soyad COLLATE NOCASE, id').fetchall()
        except Exception as ex:
            QMessageBox.warning(self, 'Öğrenci listesi', f'Öğrenci listesi okunamadı: {ex}')
            rows = []
        self.students.blockSignals(True)
        self.students.clear()
        for sid, first, last, group in rows:
            self.students.addItem(f'{first} {last}  ·  {group or "Grup belirtilmedi"}', int(sid))
        self.students.blockSignals(False)
        if not rows:
            self.preview.setPlainText('Rapor hazırlanacak aktif öğrenci bulunamadı.')
            self.save.setEnabled(False)

    def _preview(self, *args):
        # Prevent the PDF shortcut from opening the previous student's file
        # after a student/period/report switch or a failed refresh.
        self._last_file = None
        self.open_pdf.setEnabled(False)
        sid = self.students.currentData()
        self._snapshot = None
        self.save.setEnabled(False)
        if sid is None:
            return
        try:
            if self.template.currentData() == 'butunlesik':
                from services.integrated_report_v3584 import read_integrated_report
                snap = read_integrated_report(self.con, int(sid),
                                              period_days=int(self.period.currentData()))
            else:
                snap = get_report_snapshot(self.con, int(sid), int(self.period.currentData()))
        except Exception as ex:
            self.preview.setPlainText(f'Önizleme hazırlanamadı: {ex}')
            return
        self._snapshot = snap
        if self.template.currentData() == 'butunlesik':
            from services.integrated_report_v3584 import preview_text
            self.preview.setPlainText(preview_text(snap))
            self.save.setEnabled(True)
            return
        pct = snap.evidence.percent
        lines = [
            f'ÖĞRENCİ: {snap.name}   |   GRUP: {snap.group}',
            f'DÖNEM: {snap.period_start:%d.%m.%Y} – {snap.as_of:%d.%m.%Y}',
            '',
            f'Tamamlanan ödev: {snap.done} / {snap.total}',
            f'Tamamlama oranı: {"Veri yok" if pct is None else f"%{pct:.1f}"}',
            f'Dönem içi geciken: {snap.overdue_in_period}',
            f'Bütün dönemlerden açık geciken: {snap.overdue_all}',
            '', 'DERSLER',
        ]
        lines += [f'  • {lesson}: {done}/{total}' for lesson, done, total in snap.by_subject] or ['  Veri yok']
        lines += ['', 'ÖNERİ', snap.suggestion, '', 'VERİ KALİTESİ']
        lines += list(snap.warnings) or ['Kaynak uyarısı tespit edilmedi.']
        lines += ['', 'Bu önizleme yalnızca rapor içeriğinin metin özetidir; PDF görünümü değildir.']
        self.preview.setPlainText('\n'.join(lines))
        self.save.setEnabled(True)

    def _save(self):
        # Refresh immediately before export so a stale snapshot is never reused.
        self._preview()
        snap = self._snapshot
        if snap is None:
            return
        kind = self.template.currentData()
        day_tag = date.today().strftime('%Y%m%d')
        proposed = f'KocPilot_{kind}_{snap.student_id}_{day_tag}.pdf'
        path, _ = QFileDialog.getSaveFileName(self, 'Profesyonel PDF kaydet', proposed, 'PDF (*.pdf)')
        if not path:
            return
        if not path.lower().endswith('.pdf'):
            path += '.pdf'
        if Path(path).exists():
            QMessageBox.information(self, 'Dosya korunuyor',
                                    'Bu isimde dosya mevcut. Var olan raporun üstüne yazılmadı. Yeni bir dosya adı seçin.')
            return
        try:
            if kind == 'butunlesik':
                from services.integrated_report_v3584 import export_integrated_pdf
                exported = export_integrated_pdf(snap, path)
            else:
                exported = export_professional_pdf(snap, path, kind)
        except Exception as ex:
            QMessageBox.critical(self, 'PDF hatası', f'Yeni PDF oluşturulamadı:\n{ex}')
            return
        self._last_file = exported
        self.open_pdf.setEnabled(True)
        QMessageBox.information(self, 'Rapor hazır', f'Profesyonel PDF kaydedildi:\n{exported}')

    def _open_pdf(self):
        if self._last_file and Path(self._last_file).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_file))

    def _preview_pages(self):
        """Generate ephemeral actual PDF for visual inspection, not a text mockup."""
        from tempfile import TemporaryDirectory
        from ui.pdf_page_preview_v3586 import PDFPagePreviewDialog
        try:
            self._preview()  # refresh student+period+template and invalidate stale file
            snap = self._snapshot
            if snap is None:
                return
            with TemporaryDirectory(prefix='kocpilot_single_preview_') as tmp:
                location = str(Path(tmp) / 'preview.pdf')
                if self.template.currentData() == 'butunlesik':
                    from services.integrated_report_v3584 import export_integrated_pdf
                    export_integrated_pdf(snap, location)
                else:
                    export_professional_pdf(snap, location, self.template.currentData())
                PDFPagePreviewDialog(location, self).exec()
        except ImportError:
            QMessageBox.warning(self, 'Önizleme bileşeni eksik',
                                'Gerçek sayfa önizlemesi için PyMuPDF kurulmalıdır.')
        except Exception as exc:
            QMessageBox.warning(self, 'PDF önizleme açılamadı', str(exc))
