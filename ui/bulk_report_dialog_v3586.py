# -*- coding: utf-8 -*-
"""V3.5.86: opt-in student/group controlled batch PDF dialog."""
from __future__ import annotations
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFrame,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QProgressDialog, QPushButton, QVBoxLayout)

from services.bulk_reports_v3586 import active_students, export_batch_pdf, MAX_BATCH_STUDENTS
from ui.pdf_page_preview_v3586 import PDFPagePreviewDialog


class BulkReportDialog(QDialog):
    def __init__(self, con, parent=None):
        super().__init__(parent)
        self.con = con
        self._last_file = None
        self.setWindowTitle('KoçPilot 360 · Toplu Öğrenci / Sınıf PDF (Pilot)')
        self.resize(900, 760)
        self.setMinimumSize(720, 600)
        self._build()
        self._load()

    def _build(self):
        outer=QVBoxLayout(self); outer.setContentsMargins(20,18,20,18); outer.setSpacing(12)
        box=QFrame(); box.setStyleSheet('QFrame { background: #17263f; border-radius: 10px; }'
                                          'QLabel {color: white; background: transparent;}')
        head=QVBoxLayout(box)
        title=QLabel('📑  TOPLU ÖĞRENCİ & SINIF RAPORU'); title.setStyleSheet('font-size: 18px; font-weight: 750;')
        info=QLabel('Sınıf/grup filtreleyin, öğrencileri işaretleyin, aynı türde tek bir birleşik PDF hazırlayın.')
        info.setWordWrap(True); head.addWidget(title); head.addWidget(info); outer.addWidget(box)
        row=QHBoxLayout(); row.addWidget(QLabel('Grup'))
        self.group=QComboBox(); row.addWidget(self.group, 2)
        row.addWidget(QLabel('Dönem'))
        self.days=QComboBox()
        for n in (7,30,90): self.days.addItem(f'Son {n} gün',n)
        self.days.setCurrentIndex(1); row.addWidget(self.days,1)
        outer.addLayout(row)
        row=QHBoxLayout(); row.addWidget(QLabel('Rapor türü'))
        self.template=QComboBox(); self.template.addItem('Veli bilgilendirme (kısa)','veli')
        self.template.addItem('Öğretmen gelişim (ayrıntılı)','ogretmen')
        self.template.addItem('Bütünleşik Öğrenci 360 (çok modüllü)','butunlesik')
        row.addWidget(self.template,1); outer.addLayout(row)
        self.search=QLineEdit(); self.search.setPlaceholderText('Öğrenci adı, soyadı veya ID ara…')
        outer.addWidget(self.search)
        selector=QHBoxLayout(); self.select_visible=QPushButton('Görünenleri Seç')
        self.clear=QPushButton('Seçimi Temizle'); self.selection=QLabel('Seçili: 0')
        selector.addWidget(self.select_visible); selector.addWidget(self.clear)
        selector.addStretch(); selector.addWidget(self.selection); outer.addLayout(selector)
        self.list=QListWidget(); self.list.setAlternatingRowColors(True)
        self.list.setAccessibleName('Rapor hazırlanacak aktif öğrenciler')
        outer.addWidget(self.list,1)
        self.notice=QLabel('Önemli: Öğrenci seçimi zorunludur. En fazla 60 öğrenci tek çıktıda birleştirilir. '
                           'Veritabanına yazılmaz; var olan PDF değiştirilmez. Kişisel verileri paylaşmadan önce alıcıyı kontrol edin.')
        self.notice.setWordWrap(True); self.notice.setStyleSheet('color: #475569; font-size: 11px;')
        outer.addWidget(self.notice)
        foot=QHBoxLayout(); self.preview=QPushButton('🔍 Gerçek PDF Önizlemesi')
        self.export=QPushButton('📄 Toplu PDF Oluştur…')
        self.export.setStyleSheet('background: #2563eb; color: white; padding: 9px 16px; font-weight: 700;')
        self.open_pdf=QPushButton('Son PDF’yi Aç'); self.open_pdf.setEnabled(False)
        self.close=QPushButton('Kapat')
        foot.addWidget(self.preview); foot.addWidget(self.open_pdf)
        foot.addStretch(); foot.addWidget(self.close); foot.addWidget(self.export)
        outer.addLayout(foot)
        self.group.currentIndexChanged.connect(self._filter)
        self.search.textChanged.connect(self._filter)
        self.list.itemChanged.connect(self._selection_changed)
        self.select_visible.clicked.connect(self._select_visible)
        self.clear.clicked.connect(self._clear)
        self.preview.clicked.connect(self._preview)
        self.export.clicked.connect(self._save)
        self.open_pdf.clicked.connect(self._open_last)
        self.close.clicked.connect(self.accept)
        self.days.currentIndexChanged.connect(self._invalidate_last)
        self.template.currentIndexChanged.connect(self._invalidate_last)

    def _load(self):
        try: rows=active_students(self.con)
        except Exception as exc:
            QMessageBox.warning(self,'Öğrenci listesi',f'Öğrenciler okunamadı: {exc}')
            rows=()
        self.group.blockSignals(True); self.group.clear(); self.group.addItem('Tüm aktif öğrenciler',None)
        keys=sorted({(a,b) for _,_,a,b in rows},key=lambda x:(x[0].casefold(),x[1].casefold()))
        for primary,sub in keys:
            self.group.addItem(' / '.join(filter(None, (primary,sub))) or 'Grup belirtilmedi', (primary,sub))
        self.group.blockSignals(False)
        self.list.blockSignals(True); self.list.clear()
        for sid,name,primary,sub in rows:
            label=f'{name}  ·  {" / ".join(filter(None, (primary,sub))) or "Grup belirtilmedi"}  ·  ID {sid}'
            item=QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole,(sid,primary,sub,name))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self._filter()

    def _invalidate_last(self,*args):
        self._last_file=None; self.open_pdf.setEnabled(False)

    def _filter(self,*args):
        # A hidden previously checked student must NEVER silently be exported.
        # Changing class/search narrows selection to the currently visible rows.
        key=self.group.currentData(); q=self.search.text().strip().casefold()
        self.list.blockSignals(True)
        try:
            for i in range(self.list.count()):
                item=self.list.item(i); sid,a,b,name=item.data(Qt.ItemDataRole.UserRole)
                hidden=(key is not None and key!=(a,b)) or bool(q and q not in f'{name} {sid}'.casefold())
                if hidden and item.checkState()==Qt.CheckState.Checked:
                    item.setCheckState(Qt.CheckState.Unchecked)
                item.setHidden(hidden)
        finally: self.list.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self,*args):
        ids=self._selected()
        self.selection.setText(f'Seçili: {len(ids)} / {MAX_BATCH_STUDENTS}')
        available=0 < len(ids) <= MAX_BATCH_STUDENTS
        self.preview.setEnabled(available); self.export.setEnabled(available)
        self._invalidate_last()

    def _selected(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)[0]
                for i in range(self.list.count())
                if self.list.item(i).checkState()==Qt.CheckState.Checked]

    def _select_visible(self):
        self.list.blockSignals(True)
        try:
            count=len(self._selected())
            for i in range(self.list.count()):
                item=self.list.item(i)
                if not item.isHidden() and item.checkState()!=Qt.CheckState.Checked and count<MAX_BATCH_STUDENTS:
                    item.setCheckState(Qt.CheckState.Checked); count+=1
        finally: self.list.blockSignals(False)
        self._selection_changed()
        if len(self._selected())==MAX_BATCH_STUDENTS:
            QMessageBox.information(self,'Toplu rapor sınırı',
                                    'Bir çıktıda en fazla 60 öğrenci seçilebilir. Diğer öğrenciler için ikinci rapor oluşturabilirsiniz.')

    def _clear(self):
        self.list.blockSignals(True)
        try:
            for i in range(self.list.count()): self.list.item(i).setCheckState(Qt.CheckState.Unchecked)
        finally: self.list.blockSignals(False)
        self._selection_changed()

    def _confirm_selection(self):
        students=[self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                  if self.list.item(i).checkState()==Qt.CheckState.Checked]
        if not students or len(students)>MAX_BATCH_STUDENTS:
            QMessageBox.warning(self,'Öğrenci seçimi','En az 1, en fazla 60 öğrenci seçin.')
            return False
        names='\n'.join(f'  • {name} (ID {sid})' for sid,_,_,name in students[:12])
        rest=f'\n  ... ve {len(students)-12} öğrenci daha.' if len(students)>12 else ''
        message=(f'{len(students)} seçili öğrenci için {self.template.currentText()} hazırlanacak.\n'
                 f'Kapsam: {self.days.currentText()}\n\n{names}{rest}\n\n'
                 'Öğrenci listesini ve PDF’yi paylaşacağınız alıcıları kontrol edin. Devam edilsin mi?')
        return QMessageBox.question(self,'Rapor kapsamını doğrulayın',message,
                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                     QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def _build_pdf(self,target):
        ids=self._selected(); days=int(self.days.currentData()); kind=self.template.currentData()
        if not ids or len(ids)>MAX_BATCH_STUDENTS:
            raise ValueError('En az 1, en fazla 60 öğrenci seçin.')
        progress=QProgressDialog('Seçilen öğrencilerin raporları hazırlanıyor…', 'İptal',0,len(ids),self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        controls=(self.list,self.search,self.group,self.days,self.template,
                  self.select_visible,self.clear,self.export,self.preview)
        for control in controls: control.setEnabled(False)
        def tick(i,n):
            progress.setValue(i)
            QApplication.processEvents()
            if progress.wasCanceled(): raise InterruptedError('Toplu PDF hazırlığı kullanıcı tarafından iptal edildi.')
        try:
            result=export_batch_pdf(self.con, ids, str(target), period_days=days,
                                    template=kind, progress=tick)
            progress.setValue(len(ids))
            return result
        finally:
            progress.close()
            for control in controls: control.setEnabled(True)
            self._selection_changed()

    def _preview(self):
        if not self._confirm_selection(): return
        try:
            with TemporaryDirectory(prefix='kocpilot_preview_') as directory:
                pdf=Path(directory)/'temporary_batch_preview.pdf'
                self._build_pdf(pdf)
                PDFPagePreviewDialog(str(pdf),self).exec()
        except InterruptedError: pass
        except ImportError:
            QMessageBox.warning(self,'Önizleme bileşeni eksik',
                                'Gerçek PDF sayfa önizlemesi için PyMuPDF kurulmalıdır.')
        except Exception as exc:
            QMessageBox.warning(self,'Önizleme hazırlanamadı',str(exc))

    def _save(self):
        if not self._confirm_selection(): return
        ids=self._selected()
        proposed=f'KocPilot_Toplu_{self.template.currentData()}_{len(ids)}ogr_{date.today():%Y%m%d}.pdf'
        path,_=QFileDialog.getSaveFileName(self,'Toplu PDF kaydet',proposed,'PDF (*.pdf)')
        if not path: return
        if not path.lower().endswith('.pdf'): path+='.pdf'
        if Path(path).exists():
            QMessageBox.warning(self,'Mevcut dosya','Dosya zaten mevcut; farklı ad seçin. Üzerine yazılmadı.')
            return
        try:
            file,rows=self._build_pdf(path)
        except InterruptedError: return
        except Exception as exc:
            QMessageBox.critical(self,'Toplu PDF oluşturulamadı',str(exc)); return
        self._last_file=file; self.open_pdf.setEnabled(True)
        QMessageBox.information(self,'Rapor hazır',
                                f'{len(rows)} öğrenci için birleşik PDF kaydedildi:\n{file}\n\nPaylaşım öncesi alıcıları kontrol edin.')

    def _open_last(self):
        if self._last_file and Path(self._last_file).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_file))
