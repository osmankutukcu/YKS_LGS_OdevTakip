"""Optional, narrow-screen-friendly V23.3 dialog for scoped homework.

Existing yellow/green matrix cells and old Homework Control are untouched.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QSpinBox, QDateEdit, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox, QScrollArea,
                             QWidget, QFormLayout)

from services.curriculum_v233 import (available_scoped_topics, available_books,
    list_assignments, create_assignment, change_status)


class ScopedHomeworkDialog(QDialog):
    def __init__(self, parent, *, student_id: int, lesson: str):
        super().__init__(parent)
        self.student_id = int(student_id)
        self.lesson = lesson
        self.setWindowTitle('Kapsama Özel Ödevler (V23.3)')
        self.setModal(True)
        screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else None
        if area:
            self.resize(min(850, max(340, area.width()-75)), min(590, max(340, area.height()-95)))
        else:
            self.resize(760, 510)
        self.setMinimumSize(320, 300)

        layout = QVBoxLayout(self)
        header = QLabel(f'Öğrenci #{student_id} · {lesson} — Grup/Öğrenci özel konuları')
        header.setWordWrap(True)
        layout.addWidget(header)
        note = QLabel('Bu ödevler ayrı kapsam kaydıdır. Eski ana ödev matrisi tikleri ve '
                      'Ödev Kontrol Formu bu ekrandan değiştirilmez.')
        note.setWordWrap(True)
        layout.addWidget(note)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        panel = QWidget()
        form = QFormLayout(panel)
        self.topic = QComboBox()
        self.topic.setMinimumWidth(100)
        self.book = QComboBox()
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 1440)
        self.minutes.setValue(45)
        self.due = QDateEdit(QDate.currentDate().addDays(7))
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat('dd.MM.yyyy')
        form.addRow('Kapsam konusu', self.topic)
        form.addRow('Öğrencinin kitabı', self.book)
        form.addRow('Çalışma süresi (dk)', self.minutes)
        form.addRow('Teslim tarihi', self.due)
        scroll.setWidget(panel)
        layout.addWidget(scroll)
        self.save_btn = QPushButton('Seçili Kapsam Konusuna Ödev Ver')
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['Konu', 'Kapsam', 'Kitap', 'Teslim', 'Durum'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        refresh = QPushButton('Yenile')
        refresh.clicked.connect(self._load)
        actions.addWidget(refresh)
        finished = QPushButton('Tamamlandı')
        finished.clicked.connect(lambda: self._change('tamam'))
        actions.addWidget(finished)
        cancel = QPushButton('İptal Et')
        cancel.clicked.connect(lambda: self._change('iptal'))
        actions.addWidget(cancel)
        actions.addStretch()
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self._load()

    def _load(self):
        try:
            import db
            con = db.get_conn()
            previous_topic = self.topic.currentData()
            previous_book = self.book.currentText()
            options = available_scoped_topics(con, student_id=self.student_id, lesson=self.lesson)
            books = available_books(con, student_id=self.student_id, lesson=self.lesson)
            records = list_assignments(con, student_id=self.student_id, lesson=self.lesson)
            self.topic.clear()
            for opt in options:
                self.topic.addItem(f'{opt.source} · {opt.title}', (opt.reference, opt.title))
            self.book.clear()
            self.book.addItems(books)
            if previous_topic is not None:
                for i in range(self.topic.count()):
                    if self.topic.itemData(i) == previous_topic:
                        self.topic.setCurrentIndex(i)
                        break
            if previous_book in books:
                self.book.setCurrentText(previous_book)
            self.save_btn.setEnabled(bool(options and books))
            self.table.setRowCount(len(records))
            for row, rec in enumerate(records):
                vals = (rec.topic_title, rec.source, rec.book, rec.due_date, rec.status)
                for col, value in enumerate(vals):
                    cell = QTableWidgetItem(str(value))
                    if col == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, rec.id)
                    self.table.setItem(row, col, cell)
        except Exception as exc:
            self.save_btn.setEnabled(False)
            QMessageBox.warning(self, 'Kapsam ödevi', f'Veriler güvenli okunamadı: {exc}')

    def _save(self):
        selection = self.topic.currentData()
        book = self.book.currentText()
        if not selection or not book:
            QMessageBox.warning(self, 'Eksik seçim', 'Konu ve öğrenciye kayıtlı kitap seçiniz.')
            return
        if QMessageBox.question(self, 'Ödev onayı',
              f'{self.topic.currentText()} için “{book}” kitabından ayrı kapsam ödevi oluşturulsun mu?',
              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            import db
            create_assignment(db.get_conn(), student_id=self.student_id, lesson=self.lesson,
                topic_reference=selection[0], expected_title=selection[1], book=book,
                minutes=self.minutes.value(), due_date=self.due.date().toString('yyyy-MM-dd'))
        except Exception as exc:
            QMessageBox.warning(self, 'Ödev oluşturulamadı', str(exc))
            return
        self._load()

    def _change(self, status):
        row = self.table.currentRow()
        cell = self.table.item(row, 0) if row >= 0 else None
        if cell is None:
            QMessageBox.information(self, 'Seçim', 'Önce kapsam ödevi satırını seçiniz.')
            return
        assignment_id = cell.data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, 'Durum onayı',
                f'Seçili kapsam ödevi “{status}” olarak işaretlensin mi?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            import db
            change_status(db.get_conn(), assignment_id=assignment_id,
                          student_id=self.student_id, new_status=status)
        except Exception as exc:
            QMessageBox.warning(self, 'İşlem tamamlanmadı', str(exc))
            return
        self._load()
