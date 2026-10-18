"""Optional teacher-facing preview. Does not alter any homework checkbox or save path."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                             QHBoxLayout, QTableWidget, QTableWidgetItem,
                             QAbstractItemView, QHeaderView, QMessageBox)

from services.curriculum_v236 import read_coverage_overview
from services.curriculum_v237 import teacher_guidance


class CurriculumMatrixPreview(QDialog):
    def __init__(self, parent, *, lesson, student_id, review, general_rows=None, overview=None):
        super().__init__(parent)
        self.lesson = lesson
        self.student_id = student_id
        self.general_rows = general_rows
        self.setWindowTitle('Konu ve Müfredat Uyumu — Öğretmen Rehberi (V23.8)')
        self.setModal(True)
        available = QGuiApplication.primaryScreen()
        area = available.availableGeometry() if available else None
        self.resize(min(750, max(400, area.width()-60)) if area else 680,
                    min(510, max(310, area.height()-100)) if area else 450)
        self.setMinimumSize(320, 260)
        layout = QVBoxLayout(self)
        self.summary = QLabel('')
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet('font-size: 13px; font-weight: 700; padding: 4px;')
        layout.addWidget(self.summary)
        self.result = QLabel('')
        self.result.setWordWrap(True)
        self.result.setStyleSheet('background: #f0f9ff; color: #0f3d63; border: 1px solid #bfdbfe; '
                                  'border-radius: 6px; padding: 10px; font-weight: 600;')
        layout.addWidget(self.result)
        self.scoped_summary = QLabel('')
        self.scoped_summary.setWordWrap(True)
        self.scoped_summary.setStyleSheet('background: #f8fafc; color: #334155; padding: 7px;')
        layout.addWidget(self.scoped_summary)
        note = QLabel('Bu denetim, yerel konu kayıtlarının matris uyumunu gösterir; güncel MEB müfredatının doğrulandığı anlamına gelmez.')
        note.setWordWrap(True)
        note.setStyleSheet('color: #64748b; font-size: 10px;')
        layout.addWidget(note)
        # A clear decision and safe action come BEFORE optional technical tables.
        self.guidance = QLabel('')
        self.guidance.setWordWrap(True)
        self.guidance.setStyleSheet('color:#0f172a; font-size:12px; padding:5px;')
        layout.addWidget(self.guidance)
        self.review_button = QPushButton('🔎 Sorunlu konuyu göster', self)
        self.review_button.clicked.connect(self._show_first_problem)
        layout.addWidget(self.review_button)
        self.editor_button = QPushButton('✏️ Konu düzenleme ekranına git (öğretmen kontrolü)', self)
        self.editor_button.clicked.connect(self._open_topic_editor)
        layout.addWidget(self.editor_button)
        self.detail_btn = QPushButton('▸ Konu listesini ve teknik ayrıntıları göster', self)
        self.detail_btn.setCheckable(True)
        self.detail_btn.setToolTip('Konu kimliklerini ve kapsam kaynağını ayrıntılı incele')
        layout.addWidget(self.detail_btn)
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(['📌 Konu', '🎯 Kapsam kaynağı', '📊 Matris uyumu'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setVisible(False)
        self.detail_btn.toggled.connect(self._toggle_details)
        layout.addWidget(self.table, 1)
        self._populate(review, overview)

        # Existing V23.3 scoped task ledger; never writes to the main checkbox matrix.
        scoped_button = QPushButton('📚 Kapsama Özel Ödevler (Aç / Yönet)', self)
        scoped_button.setStyleSheet('font-weight: 600; padding: 7px 12px;')
        scoped_button.setToolTip('Bu dersin grup/öğrenci özel konularını ve ayrı kayıtlı özel ödevlerini aç.')
        scoped_button.clicked.connect(self._open_scoped_homework)
        layout.addWidget(scoped_button)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton('Kapat')
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _toggle_details(self, show):
        self.table.setVisible(bool(show))
        self.detail_btn.setText('▾ Teknik ayrıntıları gizle' if show
                                else '▸ Konu listesini ve teknik ayrıntıları göster')

    def _populate(self, review, overview=None):
        # Existing students/lesson stay explicit; never infer success from homework ticks.
        if overview is None:
            self.summary.setText(f'Öğrenci #{self.student_id} · {self.lesson}')
            self.result.setText('Konu kapsamı okundu. Ayrıntılar için listeyi açın.')
            self.scoped_summary.setText(f'Ana matris: {review.legacy_row_count} konu · '
                                        f'Ayrı özel konu: {review.scoped_only_count}')
        else:
            self.summary.setText(f'👤 {overview.student_label} · {self.lesson}'
                                 + (f' · {overview.group_label}' if overview.group_label else ''))
            self.result.setText(('⚠️ ' if overview.needs_attention else '✓ ')
                                + overview.teacher_message)
            self.scoped_summary.setText(
                f'Ana matris: {overview.general_count} konu · Uyumlu genel konu: {overview.matrix_match_count}\n'
                f'Grup kapsamı: {overview.group_count} · Öğrenci kapsamı: {overview.personal_count} · '
                f'Ana matriste olmayan özel konu: {overview.extra_count}\n'
                f'📋 Bu dersteki özel ödevler (ana ödev sayısından ayrı): '
                f'Açık {overview.scoped_tasks.open_count} · '
                f'Tamam {overview.scoped_tasks.completed_count} · '
                f'İptal {overview.scoped_tasks.cancelled_count}'
            )
            self.result.setToolTip('\n'.join(overview.problems) if overview.problems
                                   else 'Bu kontrol yalnızca yerel konu kimliklerine ilişkindir; MEB müfredatını doğrulamaz.')
        self.table.setRowCount(len(review.rows))
        for i, item in enumerate(review.rows):
            for j, value in enumerate((item.title, item.source, item.status)):
                cell = QTableWidgetItem(value)
                cell.setToolTip(item.details + '\nKonu kimliği: ' + item.reference)
                self.table.setItem(i, j, cell)
        guide = teacher_guidance(overview) if overview is not None else None
        self.guidance.setText(guide.message if guide else 'İsterseniz ayrıntılı konu listesini inceleyebilirsiniz.')
        self.review_button.setVisible(bool(guide and guide.needs_review))
        self.editor_button.setVisible(bool(guide and guide.needs_review))
        # No 31-row technical table by default. One-click safe review if needed.


    def _show_first_problem(self):
        # Existing V23.2 review already marks identity mismatches: don't guess based on names.
        self.detail_btn.setChecked(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 2)
            if item is not None and item.text() == 'Kimlik denetimi gerekli':
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                break
        else:
            # A stale general matrix may only produce a warning without a specific row.
            self.table.scrollToTop()

    def _open_topic_editor(self):
        # Explicit teacher action only. The editor is the ORIGINAL safe editing path.
        # Open after closing the modal preview so the teacher can interact with it.
        from ui.topic_editor import DersKonuEditor
        form = self.parentWidget()
        if form is None:
            return
        try:
            editor = getattr(form, '_curriculum_topic_editor_v237', None)
            if editor is None:
                editor = DersKonuEditor()  # original editor intentionally used without parent
                form._curriculum_topic_editor_v237 = editor
            editor.cmbKapsam.setCurrentText('Genel')
            idx = editor.cmbDers.findData(self.lesson)
            if idx < 0:
                raise ValueError('Seçili ders düzenleyicide bulunamadı; yanlış ders açılmadı.')
            editor.cmbDers.setCurrentIndex(idx)
        except Exception as exc:
            QMessageBox.warning(self, 'Konu düzenleme', f'Düzenleyici güvenle açılamadı: {exc}')
            return
        self.close()
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _open_scoped_homework(self):
        from ui.scoped_homework_v233 import ScopedHomeworkDialog
        ScopedHomeworkDialog(self, student_id=self.student_id, lesson=self.lesson).exec()
        if self.general_rows is not None:
            try:
                import db
                updated = read_coverage_overview(db.get_conn(), lesson=self.lesson,
                                                  student_id=self.student_id, general_rows=self.general_rows)
                self._populate(updated.review, updated)
            except Exception as exc:
                QMessageBox.warning(self, 'Özel ödevler yenilenemedi',
                                    f'Kayıt işlemi tamamlandıysa pencereyi yeniden açarak kontrol edin: {exc}')


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
            overview = read_coverage_overview(db.get_conn(), lesson=lesson,
                                              student_id=student_id, general_rows=general_rows)
            review = overview.review
        except Exception as exc:
            QMessageBox.warning(owner, 'Müfredat önizlemesi',
                                f'Konu kapsamı güvenli biçimde okunamadı: {exc}')
            return
        dialog = CurriculumMatrixPreview(owner, lesson=lesson,
                                         student_id=student_id, review=review,
                                         general_rows=general_rows, overview=overview)
        owner._curriculum_preview_v232 = dialog
        dialog.exec()

    button.clicked.connect(show)
    owner._curriculum_scope_button_v237 = button
    # V23.8 watcher is attached after the original UI/Student 360/Coach Assistant
    # have been created. No hooks into old checkbox or save routines.
    from ui.curriculum_guidance_v238 import attach_coverage_watch
    QTimer.singleShot(0, lambda: attach_coverage_watch(owner, button))
