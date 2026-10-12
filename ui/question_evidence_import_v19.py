"""Small optional file import dialog for question-to-topic evidence.

Does not touch homework/coach tables. Existing exam results must already exist.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import quote
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QFileDialog,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QCheckBox)
from ui.question_evidence_ocr_worker_v202 import ReportReadWorker, ACTIVE_READERS
from services.question_evidence_v19 import (fetch_exams_for_student,parse_file,prepare,
    apply,EvidenceImportError,parse_analysis_file,ReportFormatError)

class QuestionEvidenceImportDialog(QDialog):
    def __init__(self,student_id:int,parent=None,preselect_exam_id:int|None=None):
        super().__init__(parent)
        self.student_id=student_id
        self._preview=None
        self._file=None
        self._file_mode="v19"
        self._document_warnings=()
        self._pending_workers=set()
        self._preview_generation=0
        self._dialog_closed=False
        self.setWindowTitle('Soru–Konu Eşleştirme | Öğretmen Onaylı')
        self.resize(1000,650)
        root=QVBoxLayout(self)
        heading=QLabel('Deneme sorularını öğrenci–ders–soru numarası ve açık konu adıyla eşleştirin.')
        heading.setWordWrap(True)
        root.addWidget(heading)
        caution=QLabel('Dosyadaki konu ve kazanım kodları resmî olarak doğrulanmış sayılmaz. '
            'Konu bağlantısı öğretmen tarafından kontrol edilmelidir. Ödev tikleri değişmez.')
        caution.setWordWrap(True);root.addWidget(caution)
        row=QHBoxLayout();row.addWidget(QLabel('Deneme:'))
        self.exams=QComboBox();row.addWidget(self.exams,1)
        choose=QPushButton('CSV / Excel Seç');choose.clicked.connect(self.select_file);row.addWidget(choose)
        karne=QPushButton('Karne / Fotoğraf (OCR)');karne.clicked.connect(self.select_analysis_file);row.addWidget(karne)
        template=QPushButton('CSV Şablon');template.clicked.connect(self.save_template);row.addWidget(template)
        root.addLayout(row)
        self.summary=QLabel('Öğrenci için kayıtlı deneme seçin, ardından dosyayı açın.')
        self.summary.setWordWrap(True);root.addWidget(self.summary)
        self.grid=QTableWidget(0,7)
        self.grid.setHorizontalHeaderLabels(['Satır','Ders','Soru','Sonuç','Konu','Kazanım (beyan)','İşlem'])
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.grid.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.grid,1)
        self.confirm=QCheckBox('Öğrenci/deneme kimliğini ve her soru–konu sonucunu kaynak belgeyle karşılaştırdım; kaydı onaylıyorum.')
        self.confirm.stateChanged.connect(self._button_state)
        root.addWidget(self.confirm)
        bottom=QHBoxLayout()
        self.apply_button=QPushButton('Kontrol Edilmiş Eşleştirmeleri Kaydet')
        self.apply_button.clicked.connect(self.commit)
        bottom.addWidget(self.apply_button)
        close=QPushButton('Kapat');close.clicked.connect(self.reject);bottom.addWidget(close)
        root.addLayout(bottom)
        self.exams.currentIndexChanged.connect(self.refresh_preview)
        self._load_exams(preselect_exam_id)
        self._button_state()

    @staticmethod
    def _open(*,readonly):
        from db import DB_PATH
        p=Path(DB_PATH).resolve()
        if readonly:
            uri='file:'+quote(str(p),safe='/')+'?mode=ro'
            con=sqlite3.connect(uri,uri=True,timeout=10)
            con.execute('PRAGMA query_only=ON')
        else:
            con=sqlite3.connect(str(p),timeout=10)
            con.execute('PRAGMA foreign_keys=ON')
        return con

    def _load_exams(self,preferred):
        try:
            with closing(self._open(readonly=True)) as con:
                options=fetch_exams_for_student(con,self.student_id)
            for exam_id,name,day,kind in options:
                self.exams.addItem(f'{day} · {name} ({kind}) · ID {exam_id}',int(exam_id))
            if preferred:
                ix=self.exams.findData(preferred)
                if ix>=0:self.exams.setCurrentIndex(ix)
            if not options:
                self.summary.setText('Bu öğrenciye ait kayıtlı ders bazlı deneme sonucu bulunamadı. Önce Deneme Sınavları ekranından sonuç girin.')
        except Exception as exc:
            self.summary.setText('Deneme listesi okunamadı: '+str(exc))

    def select_file(self):
        file,_=QFileDialog.getOpenFileName(self,'Soru–konu dosyasını seç','','Veri Dosyaları (*.csv *.tsv *.xlsx)')
        if not file:return
        self._file=file
        self._file_mode='v19'
        self.refresh_preview()

    def select_analysis_file(self):
        file,_=QFileDialog.getOpenFileName(self,'Analizli karne dosyasını seç','',
            'Karne ve Analizler (*.pdf *.csv *.tsv *.xlsx *.png *.jpg *.jpeg)')
        if not file:return
        self._file=file
        self._file_mode='analysis'
        self.refresh_preview()

    def save_template(self):
        path,_=QFileDialog.getSaveFileName(self,'Boş CSV şablon','soru_konu_sablon.csv','CSV (*.csv)')
        if not path:return
        import csv
        with open(path,'w',encoding='utf-8-sig',newline='') as fh:
            writer=csv.writer(fh);writer.writerow(['ogrenci_id','deneme_id','ders','soru_no','sonuc','konu','kazanim_kodu'])
        QMessageBox.information(self,'Şablon','Başlıkları içeren boş şablon oluşturuldu.\n'
            'Öğrenci/deneme ID değerlerini ve soru konu bağlantılarını doğrulayın.')

    def refresh_preview(self):
        self._preview_generation += 1
        self._preview=None;self._document_warnings=();self.confirm.setChecked(False);self.grid.setRowCount(0)
        if not self._file or self.exams.currentData() is None:
            self._button_state();return
        if self._file_mode == 'analysis' and Path(self._file).suffix.lower() in {'.pdf', '.png', '.jpg', '.jpeg'}:
            # OCR can take seconds. Never freeze the normal Qt event loop.
            current = self._preview_generation
            selected = int(self.exams.currentData())
            worker = ReportReadWorker(self._file, self.student_id, selected)
            self._pending_workers.add(worker)
            ACTIVE_READERS.add(worker)
            worker.report_ready.connect(lambda report, error, generation=current: self._worker_result(generation, report, error))
            worker.finished.connect(lambda thread=worker: self._worker_cleanup(thread))
            self.summary.setText('Karne yerel olarak okunuyor. Bu sırada kayıt yapılmaz; işlem sonunda önizleme gösterilecek.')
            self._button_state()
            worker.start()
            return
        try:
            if self._file_mode=='analysis':
                report=parse_analysis_file(self._file,student_id=self.student_id,
                    exam_id=int(self.exams.currentData()), allow_ocr=True)
                self._show_report(report)
            else:
                self._show_rows(parse_file(self._file))
        except Exception as exc:
            self.summary.setText('Önizleme hazırlanamadı: '+str(exc))
        self._button_state()

    def _worker_result(self, generation, report, error):
        if self._dialog_closed or generation != self._preview_generation:
            return  # Student/exam/file changed: stale OCR must never become a preview.
        if error is not None:
            self.summary.setText('Önizleme hazırlanamadı: ' + str(error))
        else:
            try:
                self._show_report(report)
            except Exception as exc:
                self.summary.setText('Önizleme hazırlanamadı: ' + str(exc))
        self._button_state()

    def _worker_cleanup(self, worker):
        self._pending_workers.discard(worker)
        ACTIVE_READERS.discard(worker)
        worker.deleteLater()

    def _show_report(self, report):
        self._document_warnings=(
            f'Otomatik tanınan düzen: {report.detected_layout} · incelenen sayfa: {report.scanned_sheets}',
            *report.warnings,
        )
        self._show_rows(report.rows)

    def _show_rows(self, rows):
        with closing(self._open(readonly=True)) as con:
            self._preview=prepare(con,int(self.exams.currentData()),self.student_id,rows)
        p=self._preview; counts=p.counts
        self.summary.setText(f'Önizleme: {counts["new"]} yeni · {counts["update"]} değişen · '
            f'{counts["same"]} aynı · {len(p.errors)} hata · {len(p.warnings)} konu kontrol uyarısı.\n'
            + '\n'.join((list(self._document_warnings)+list(p.errors)+list(p.warnings))[:12]))
        self.grid.setRowCount(len(p.changes))
        for ix,change in enumerate(p.changes):
            item=change.item
            for col,value in enumerate((item.source_row,item.subject,item.question_no,item.result,
                                        item.topic,item.outcome_code,change.status)):
                self.grid.setItem(ix,col,QTableWidgetItem(str(value)))

    def reject(self):
        self._dialog_closed=True
        self._preview_generation+=1
        super().reject()

    def accept(self):
        self._dialog_closed=True
        self._preview_generation+=1
        super().accept()

    def _button_state(self):
        ok=bool(self._preview and not self._preview.errors and
                any(x.status!='same' for x in self._preview.changes) and self.confirm.isChecked())
        self.apply_button.setEnabled(ok)

    def commit(self):
        if not self._preview or self._preview.errors or not self.confirm.isChecked():return
        try:
            with closing(self._open(readonly=False)) as con:
                result=apply(con,self._preview,teacher_confirmed=True)
        except (EvidenceImportError,sqlite3.Error,OSError) as exc:
            QMessageBox.warning(self,'Güvenli kayıt engellendi',str(exc)+'\nDosyayı yeniden önizleyin.')
            return
        QMessageBox.information(self,'Soru kanıtları kaydedildi',
            f'{result["new"]} yeni, {result["update"]} güncelleme, {result["same"]} değişmedi.\n'
            'Mevcut ödevler, deneme netleri ve koçluk işaretleri korunmuştur.')
        self.accept()
