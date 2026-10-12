"""Optional teacher-facing preview. Does not alter any homework checkbox or save path."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QAbstractItemView, QHeaderView, QMessageBox)

from services.curriculum_v232 import inspect_matrix_topics


class CurriculumMatrixPreview(QDialog):
    def __init__(self, parent, *, lesson, student_id, review):
        super().__init__(parent)
        self.setWindowTitle('Müfredat Kapsamı — Salt Okunur (V23.2)')
        self.setModal(True)
        available = QGuiApplication.primaryScreen()
        area = available.availableGeometry() if available else None
        self.resize(min(750, max(400, area.width()-60)) if area else 680,
                    min(510, max(310, area.height()-100)) if area else 450)
        self.setMinimumSize(320, 260)
        layout = QVBoxLayout(self)
        summary = QLabel(f'Öğrenci: {student_id}  |  Ders: {lesson}  |  '
                         f'Eski matris: {review.legacy_row_count} konu  |  '
                         f'Ek kapsam konusu: {review.scoped_only_count}')
        summary.setWordWrap(True)
        layout.addWidget(summary)
        hint = QLabel('Bu pencere yalnızca konu kapsamlarını gösterir. '
                      'Sarı/yeşil tikler, ödevler ve konu kimlikleri değiştirilmez.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        table = QTableWidget(len(review.rows), 3, self)
        table.setHorizontalHeaderLabels(['Konu', 'Kaynak', 'Matris uyumu'])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setWordWrap(True)
        for i, item in enumerate(review.rows):
            for j, value in enumerate((item.title, item.source, item.status)):
                cell = QTableWidgetItem(value)
                cell.setToolTip(item.details + '\nKaynak referansı: ' + item.reference)
                table.setItem(i,j,cell)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table, 1)
        # V23.3: isolated scoped assignment ledger; legacy matrix cells remain unchanged.
        from ui.scoped_homework_v233 import ScopedHomeworkDialog
        scoped_button = QPushButton("Kapsama Özel Ödevler", self)
        scoped_button.setToolTip("Grup/öğrenci konularını eski tikleri değiştirmeden ödevlendir.")
        scoped_button.clicked.connect(lambda: ScopedHomeworkDialog(
            self, student_id=student_id, lesson=lesson).exec())
        layout.addWidget(scoped_button)
        if review.warnings:
            warnings = QLabel('Dikkat: ' + ' | '.join(review.warnings))
            warnings.setWordWrap(True)
            warnings.setToolTip('\n'.join(review.warnings))
            layout.addWidget(warnings)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton('Kapat')
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)


def install_curriculum_preview_navigation(layout, owner) -> None:
    """One compact button on the V22 horizontally scrollable lesson toolbar.

    No checkbox, topic row, QTableWidget, grade, old save action or class method
    is changed by this optional connection.
    """
    button = QPushButton('📚 Konu Kapsamı', owner)
    button.setToolTip('Seçili dersin genel, grup ve öğrenci konularını salt okunur incele.')
    button.setMaximumHeight(27)
    layout.addWidget(button)

    def show():
        try:
            student_id = int(owner._secili_ogrenci_id() or 0)
            loaded_id = int(getattr(owner, '_loaded_student_id', 0) or 0)
            if not student_id or student_id != loaded_id:
                QMessageBox.warning(owner, 'Öğrenci seçimi',
                                    'Önce seçili öğrencinin bilgilerini Getir ile yükleyiniz.')
                return
            index = owner.tabs.currentIndex()
            if index < 0:
                QMessageBox.warning(owner, 'Ders seçimi', 'Bir ders sekmesi seçiniz.')
                return
            tab_data = owner.tabs.tabBar().tabData(index)
            lesson = tab_data.get('key', '') if isinstance(tab_data, dict) else ''
            if not lesson:
                QMessageBox.warning(owner, 'Ders kimliği', 'Ders kimliği belirlenemedi; işlem yapılmadı.')
                return
            # Read EXACTLY what the already-rendered legacy checkbox table shows.
            # This also detects stale displays when the curriculum was edited meanwhile.
            from PyQt6.QtCore import Qt
            table = owner._ders_tablolari.get(lesson)
            if table is None:
                # Some older versions use different case or key formatting.
                table = next((v for k,v in owner._ders_tablolari.items()
                              if str(k).strip().lower() == str(lesson).strip().lower()), None)
            if table is None:
                raise ValueError('Derse ait mevcut ödev tablosu bulunamadı.')
            general_rows = []
            for row_index in range(table.rowCount()):
                item = table.item(row_index, 0)
                if item is None:
                    raise ValueError('Konu tablosunda eksik satır var.')
                general_rows.append({'id': item.data(Qt.ItemDataRole.UserRole),
                                     'konu': item.text()})
            import db
            review = inspect_matrix_topics(db.get_conn(), lesson=lesson,
                                           student_id=student_id, general_rows=general_rows)
        except Exception as exc:
            QMessageBox.warning(owner, 'Müfredat önizlemesi',
                                f'Konu kapsamı güvenli biçimde okunamadı: {exc}')
            return
        dialog = CurriculumMatrixPreview(owner, lesson=lesson,
                                         student_id=student_id, review=review)
        owner._curriculum_preview_v232 = dialog
        dialog.exec()

    button.clicked.connect(show)
