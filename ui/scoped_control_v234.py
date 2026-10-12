"""Optional V23.4 scoped-homework control dialog, invoked from Homework Control.

Separate visually and transactionally from the legacy checkbox grid. The
parent's student ID is fixed for the dialog lifetime. No global students list,
no legacy 'Save All' behavior, and no data loading on idle/other pages.
"""
from __future__ import annotations

from contextlib import closing

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
    QPushButton, QMessageBox)

from services.curriculum_v234 import get_overview, set_scoped_control_status, status_history


_STATUS = {'devam': 'Açık', 'tamam': 'Tamamlandı', 'iptal': 'İptal'}


class ScopedControlDialogV234(QDialog):
    def __init__(self, parent, *, student_id: int):
        super().__init__(parent)
        self.student_id = int(student_id)
        self.setWindowTitle('Ödev Kontrol · Kapsama Özel Ödevler')
        self.setModal(True)
        self._shown = []
        screen = self.screen() or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        if geo:
            self.resize(max(360, min(920, geo.width()-48)), max(310, min(585, geo.height()-48)))
        else:
            self.resize(800, 520)

        root = QVBoxLayout(self)
        title = QLabel('🎯 Grup ve Öğrenciye Özel Ödevlerin Kontrolü')
        title.setWordWrap(True)
        root.addWidget(title)
        note = QLabel('Bu kayıtlar ana ödevlerden ayrıdır. Buradaki durum işlemleri '
                      'sarı/yeşil tikleri, eski kümeleri ve ana başarı yüzdesini değiştirmez.')
        note.setWordWrap(True)
        root.addWidget(note)
        self.summary = QLabel('Kapsam ödevleri yükleniyor…')
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        filters = QHBoxLayout()
        self.lesson = QComboBox(self)
        self.lesson.addItem('Bütün dersler', None)
        self.lesson.currentIndexChanged.connect(self._filter_rows)
        self.state = QComboBox(self)
        self.state.addItem('Tüm durumlar', None)
        for status, label in _STATUS.items():
            self.state.addItem(label, status)
        self.state.currentIndexChanged.connect(self._filter_rows)
        filters.addWidget(self.lesson, 1)
        filters.addWidget(self.state, 1)
        root.addLayout(filters)

        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(['Ders','Konu','Kapsam','Kitap','Teslim','Süre','Durum'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(False)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        root.addWidget(self.table, 1)

        # Two compact rows keep controls reachable at Windows 125–150% scaling.
        buttons = QGridLayout()
        buttons.setHorizontalSpacing(6)
        buttons.setVerticalSpacing(6)
        self.finish = QPushButton('✓ Tamamlandı')
        self.cancel = QPushButton('İptal')
        self.undo = QPushButton('↩ Açık Duruma Al')
        self.audit = QPushButton('Geçmiş')
        self.refresh = QPushButton('Yenile')
        self.close_btn = QPushButton('Kapat')
        for index, widget in enumerate((self.finish, self.cancel, self.undo,
                                         self.audit, self.refresh, self.close_btn)):
            buttons.addWidget(widget, index // 3, index % 3)
        root.addLayout(buttons)
        self.finish.clicked.connect(lambda: self._change('tamam'))
        self.cancel.clicked.connect(lambda: self._change('iptal'))
        self.undo.clicked.connect(lambda: self._change('devam'))
        self.audit.clicked.connect(self._show_audit)
        self.refresh.clicked.connect(self.reload)
        self.close_btn.clicked.connect(self.accept)
        self._update_buttons()
        self.reload()

    def reload(self):
        try:
            import db
            with closing(db.get_conn()) as con:
                overview = get_overview(con, student_id=self.student_id)
        except Exception as exc:
            self._shown = []
            self.table.setRowCount(0)
            self.summary.setText(f'Kapsam ödevleri okunamadı: {exc}')
            self._update_buttons()
            QMessageBox.warning(self, 'Kapsam Ödevleri', str(exc))
            return
        self._shown = list(overview.assignments)
        self.summary.setText('Öğrenci #{0} · Açık: {1}  |  Tamamlanan: {2}  |  İptal: {3}  '
                             '(ana ödev toplamlarından ayrı)'.format(
                self.student_id, overview.open_count, overview.completed_count, overview.cancelled_count))
        lessons = sorted({r.lesson for r in self._shown}, key=str.casefold)
        selected = self.lesson.currentData()
        self.lesson.blockSignals(True)
        self.lesson.clear()
        self.lesson.addItem('Bütün dersler', None)
        for lesson in lessons:
            self.lesson.addItem(lesson, lesson)
        index = self.lesson.findData(selected)
        self.lesson.setCurrentIndex(index if index >= 0 else 0)
        self.lesson.blockSignals(False)
        self._filter_rows()

    def _filter_rows(self):
        lesson, state = self.lesson.currentData(), self.state.currentData()
        records = [r for r in self._shown if (lesson is None or r.lesson == lesson)
                   and (state is None or r.status == state)]
        self.table.setRowCount(len(records))
        for index, record in enumerate(records):
            for col, value in enumerate((record.lesson, record.topic_title, record.source,
                                         record.book, record.due_date, record.minutes,
                                         _STATUS.get(record.status, record.status))):
                cell = QTableWidgetItem(str(value))
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, (record.id, record.status))
                self.table.setItem(index, col, cell)
        self._update_buttons()

    def _selected(self):
        row = self.table.currentRow()
        cell = self.table.item(row, 0) if row >= 0 else None
        return cell.data(Qt.ItemDataRole.UserRole) if cell else None

    def _update_buttons(self):
        chosen = self._selected()
        state = chosen[1] if chosen else None
        self.finish.setEnabled(state == 'devam')
        self.cancel.setEnabled(state == 'devam')
        self.undo.setEnabled(state in ('tamam', 'iptal'))
        self.audit.setEnabled(chosen is not None)

    def _change(self, target):
        selection = self._selected()
        if not selection:
            return
        assignment_id, prior = selection
        if QMessageBox.question(self, 'Kapsam ödevi onayı',
            f'Öğrenci #{self.student_id} · Kapsam ödevi #{assignment_id}\n'
            f'{_STATUS.get(prior,prior)} → {_STATUS.get(target,target)}\n\nİşlem onaylansın mı?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            import db
            with closing(db.get_conn()) as con:
                set_scoped_control_status(con, student_id=self.student_id,
                    assignment_id=assignment_id, expected_status=prior, new_status=target)
        except Exception as exc:
            QMessageBox.warning(self, 'Kayıt yapılmadı', str(exc))
        self.reload()

    def _show_audit(self):
        selection = self._selected()
        if not selection:
            return
        try:
            import db
            with closing(db.get_conn()) as con:
                rows = status_history(con, student_id=self.student_id, assignment_id=selection[0])
            info = ('\n'.join(f'{r[2]} · {r[0]} → {r[1]}' for r in rows)
                    if rows else 'V23.4 sonrasında henüz bir durum değişikliği yok.')
            QMessageBox.information(self, 'Kapsam Ödevi İşlem Geçmişi', info)
        except Exception as exc:
            QMessageBox.warning(self, 'İşlem geçmişi', str(exc))
