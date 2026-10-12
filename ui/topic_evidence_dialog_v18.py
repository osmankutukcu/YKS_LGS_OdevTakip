"""Compact, read-only topic evidence dialog shared by Topic Map and Student360."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from urllib.parse import quote
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox, QHeaderView)
from services.topic_evidence_v18 import read_topic_evidence


class TopicEvidenceDialog(QDialog):
    def __init__(self, student_id, parent=None):
        super().__init__(parent)
        self.student_id = int(student_id) if student_id is not None else None
        self._report = None
        self.setWindowTitle('Konu Haritası | Birleşik Kanıt Görünümü')
        self.resize(1060, 750)
        root = QVBoxLayout(self)
        self.head = QLabel('Konu bazlı ödev/koçluk kayıtları ve ders düzeyindeki denemeler')
        self.head.setWordWrap(True)
        root.addWidget(self.head)
        self.notice = QLabel('Ödev tamamlamak = konu öğrenildi demek değildir. Deneme netleri konuya otomatik atanmaz.')
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        buttons = QHBoxLayout()
        refresh = QPushButton('↻ Verileri Yenile')
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)
        copy = QPushButton('Raporu Kopyala')
        copy.clicked.connect(self.copy_report)
        buttons.addWidget(copy)
        import_questions = QPushButton('📥 Soru–Konu Dosyası')
        import_questions.clicked.connect(self.import_question_evidence)
        buttons.addWidget(import_questions)
        buttons.addStretch()
        root.addLayout(buttons)
        self.grid = QTableWidget(0, 7)
        self.grid.setHorizontalHeaderLabels(['Ders', 'Konu', 'Ana ödev açık/biten', 'Harita açık/biten', 'Koçluk', 'Soru kanıtı', 'Kontrol önerisi'])
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.grid.setAlternatingRowColors(True)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.grid.horizontalHeader().setSectionResizeMode(6,QHeaderView.ResizeMode.Stretch)
        self.grid.itemSelectionChanged.connect(self.show_details)
        root.addWidget(self.grid,stretch=3)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        root.addWidget(self.details,stretch=1)
        close_btn = QPushButton('Kapat')
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn,alignment=Qt.AlignmentFlag.AlignRight)
        self.refresh()

    def refresh(self):
        self.grid.setRowCount(0)
        self._report = None
        if not self.student_id:
            self.details.setPlainText('Önce bir öğrenci seçin.')
            return
        from db import DB_PATH
        try:
            uri = 'file:' + quote(str(DB_PATH.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri,uri=True,timeout=8)) as con:
                con.execute('PRAGMA query_only=ON')
                report = read_topic_evidence(con,self.student_id)
        except (sqlite3.Error,ValueError,OSError) as exc:
            self.details.setPlainText('Veriler okunamadı: ' + str(exc) + '\nHiçbir kayıt değiştirilmedi.')
            return
        self._report = report
        self.head.setText(f'{report.student_name} | Birleşik Konu Kanıtları ({len(report.topics)} kayıtlı konu)')
        self.grid.setRowCount(len(report.topics))
        for row,topic in enumerate(report.topics):
            columns = (topic.lesson,topic.topic,f'{topic.main_open} / {topic.main_done}',
                       f'{topic.map_open} / {topic.map_done}',
                       ('Belirsiz' if topic.duplicate_teacher_records else
                        ('Yok' if topic.teacher_state is None else f'İşaret: {topic.teacher_state}')),
                       f'{topic.question_correct}D / {topic.question_wrong}Y / {topic.question_blank}B',
                       topic.recommendation)
            for col,label in enumerate(columns):
                item=QTableWidgetItem(str(label))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(row,col,item)
        exam_lines=['Ders düzeyinde deneme sonuçları (konu kanıtı değildir):']
        exam_lines += [f'• {e.lesson}: {e.latest} ({e.count} kayıt)' for e in report.exam_context]
        if not report.exam_context: exam_lines.append('• Kayıtlı, doğrulanmış deneme sonucu yok.')
        if report.warnings: exam_lines += ['', 'Uyarılar:', *('• ' + s for s in report.warnings)]
        self._course_text='\n'.join(exam_lines)
        self.show_details()

    def show_details(self):
        if self._report is None: return
        items=self.grid.selectedItems()
        row=items[0].row() if items else -1
        if row >= 0 and row < len(self._report.topics):
            t=self._report.topics[row]
            text=f'{t.lesson} / {t.topic}\n{t.recommendation}'
            if t.question_correct+t.question_wrong+t.question_blank:
                text+=f'\nÖğretmen onaylı soru kayıtları: {t.question_correct} doğru, {t.question_wrong} yanlış, {t.question_blank} boş.'
            if t.outcome_codes: text+='\nDosyada beyan edilen kazanım kodları (resmî doğrulama yok): '+', '.join(t.outcome_codes)
            if t.teacher_note: text+='\nÖğretmen notu: '+t.teacher_note
            if t.source_warning: text+='\nUyarı: '+t.source_warning
            text+='\n\n'+self._course_text
        else:
            text=self._course_text
        self.details.setPlainText(text)

    def copy_report(self):
        if self._report is None:
            QMessageBox.information(self,'Rapor','Kopyalanacak veri yok.')
            return
        QApplication.clipboard().setText(self._report.explain())

    def import_question_evidence(self):
        if not self.student_id:
            QMessageBox.information(self,'Öğrenci','Önce öğrenci seçin.')
            return
        from ui.question_evidence_import_v19 import QuestionEvidenceImportDialog
        dialog=QuestionEvidenceImportDialog(self.student_id,self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
