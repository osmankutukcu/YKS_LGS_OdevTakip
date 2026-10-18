"""Optional, narrow-screen-friendly V23.3 dialog for scoped homework.

Existing yellow/green matrix cells and old Homework Control are untouched.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QGuiApplication, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QDateEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFrame,
    QWidget, QInputDialog, QSizePolicy, QCheckBox
)

from services.curriculum_v233 import (
    available_scoped_topics, available_books,
    list_assignments, create_assignment, change_status, ScopedAssignmentError
)
from services.curriculum_v234 import set_scoped_control_status, ScopedControlError


_STATUS_LABELS = {
    'devam': 'Açık (Devam)',
    'tamam': 'Tamamlandı',
    'iptal': 'İptal Edildi',
}


class ScopedHomeworkDialog(QDialog):
    def __init__(self, parent, *, student_id: int, lesson: str):
        super().__init__(parent)
        self.student_id = int(student_id)
        self.lesson = lesson
        self._updating_table = False
        self._book_checkboxes: list[QCheckBox] = []

        self.setWindowTitle('Kapsama Özel Ödevler (V23.3)')
        self.setModal(True)
        screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else None
        if area:
            self.resize(min(860, max(420, area.width() - 75)), min(600, max(380, area.height() - 95)))
        else:
            self.resize(800, 540)
        self.setMinimumSize(420, 340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Üst Başlık + Bilgi (Tek Kompakt Satır)
        top_info = QHBoxLayout()
        header = QLabel(f'<b>🎯 Öğrenci #{student_id} · {lesson} — Grup / Öğrenci Özel Konuları</b>')
        top_info.addWidget(header)
        top_info.addStretch()
        note = QLabel('<span style="color:#64748b; font-size:11px;">(Ana ödev matrisi tiklerinden bağımsız ayrı kayıt)</span>')
        top_info.addWidget(note)
        layout.addLayout(top_info)

        self.status_hint = QLabel('')
        self.status_hint.setWordWrap(True)
        self.status_hint.setStyleSheet(
            'color: #1d4ed8; background: #eff6ff; border: 1px solid #bfdbfe; '
            'border-radius: 5px; padding: 4px 8px; font-size: 11.5px;'
        )
        self.status_hint.setVisible(False)
        layout.addWidget(self.status_hint)

        # --- KOMPAKT ÜST KONTROL KARTI (2 Satır) ---
        ctrl_card = QFrame(self)
        ctrl_card.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QLabel { border: none; background: transparent; font-size: 12px; color: #1e293b; }
        """)
        card_lay = QVBoxLayout(ctrl_card)
        card_lay.setContentsMargins(10, 8, 10, 8)
        card_lay.setSpacing(6)

        # 1. Satır: Konu Seçimi + Özel Konu Ekle + Süre + Teslim + Ödev Ver
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(QLabel('<b>Konu:</b>'))
        self.topic = QComboBox()
        self.topic.setMinimumWidth(180)
        self.topic.setMaximumWidth(280)
        self.topic.setFixedHeight(28)
        self.topic.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row1.addWidget(self.topic, 1)

        self.btn_add_topic = QPushButton('➕ Konu Ekle')
        self.btn_add_topic.setFixedHeight(28)
        self.btn_add_topic.setToolTip('Bu öğrenciye ve derse özel yeni bir konu başlığı tanımla')
        self.btn_add_topic.setStyleSheet(
            'QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 5px; padding: 2px 8px; font-size: 11.5px; font-weight: 600;  color: #15191E;}'
            'QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }'
        )
        self.btn_add_topic.clicked.connect(self._quick_add_student_topic)
        row1.addWidget(self.btn_add_topic)

        row1.addSpacing(4)
        row1.addWidget(QLabel('<b>Süre:</b>'))
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 1440)
        self.minutes.setValue(45)
        self.minutes.setSuffix(' dk')
        self.minutes.setFixedHeight(28)
        self.minutes.setFixedWidth(74)
        row1.addWidget(self.minutes)

        row1.addWidget(QLabel('<b>Teslim:</b>'))
        self.due = QDateEdit(QDate.currentDate().addDays(7))
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat('dd.MM.yyyy')
        self.due.setFixedHeight(28)
        self.due.setFixedWidth(102)
        row1.addWidget(self.due)

        self.save_btn = QPushButton('✅ Ödev Ver')
        self.save_btn.setFixedHeight(28)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setToolTip('Seçili kapsam konusunu işaretlenen tüm kitaplar için ödev olarak ata')
        self.save_btn.setStyleSheet(
            'QPushButton { background: #2563eb; color: white; border: none; border-radius: 5px; padding: 3px 12px; font-size: 12px; font-weight: 700; }'
            'QPushButton:hover { background: #1d4ed8; }'
            'QPushButton:disabled { background: #94a3b8; color: #373839; }'
        )
        self.save_btn.clicked.connect(self._save)
        row1.addWidget(self.save_btn)
        card_lay.addLayout(row1)

        # 2. Satır: Çoklu Kitap Seçimi (Checkbox'lar) + Tümünü Seç + Kitap Ekle
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        row2.addWidget(QLabel('<b>Kitaplar:</b>'))

        self.books_wrap = QWidget()
        self.books_wrap.setStyleSheet('background: transparent; border: none;')
        self.books_lay = QHBoxLayout(self.books_wrap)
        self.books_lay.setContentsMargins(0, 0, 0, 0)
        self.books_lay.setSpacing(8)
        row2.addWidget(self.books_wrap, 1)

        # Geriye dönük uyumluluk için gizli QComboBox
        self.book = QComboBox()
        self.book.setVisible(False)

        self.btn_toggle_books = QPushButton('Tümünü Seç')
        self.btn_toggle_books.setFixedHeight(25)
        self.btn_toggle_books.setStyleSheet(
            'QPushButton { background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 7px; font-size: 11px; color: #334155; }'
            'QPushButton:hover { background: #e2e8f0; }'
        )
        self.btn_toggle_books.clicked.connect(self._toggle_all_books)
        row2.addWidget(self.btn_toggle_books)

        self.btn_add_book = QPushButton('📚 Kitap Ekle')
        self.btn_add_book.setFixedHeight(25)
        self.btn_add_book.setToolTip('Bu derste öğrenciye yeni bir kaynak kitap ekle')
        self.btn_add_book.setStyleSheet(
            'QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 1px 8px; font-size: 11px; font-weight: 600;  color: #15191E;}'
            'QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }'
        )
        self.btn_add_book.clicked.connect(self._quick_add_student_book)
        row2.addWidget(self.btn_add_book)
        card_lay.addLayout(row2)

        layout.addWidget(ctrl_card)

        # --- GENİŞ TABLO ALANI (Doğrudan Checkbox ile Tamamlama Destekli) ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['📌 Konu', '🎯 Kapsam', '📖 Kitap', '📅 Teslim', '☑ Durum (Tıkla)'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(29)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.table, 1)

        # Alt Aksiyon Satırı
        actions = QHBoxLayout()
        actions.setSpacing(6)
        refresh = QPushButton('🔄 Yenile')
        refresh.clicked.connect(self._load)
        actions.addWidget(refresh)

        finished = QPushButton('✓ Seçiliyi Tamamla')
        finished.clicked.connect(lambda: self._change('tamam'))
        actions.addWidget(finished)

        reopen = QPushButton('↩ Açık Duruma Al')
        reopen.setToolTip('Tamamlanan veya iptal edilen ödevi tekrar açık (devam) durumuna döndürür')
        reopen.clicked.connect(lambda: self._change('devam'))
        actions.addWidget(reopen)

        cancel = QPushButton('✕ İptal Et')
        cancel.clicked.connect(lambda: self._change('iptal'))
        actions.addWidget(cancel)

        actions.addStretch()
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self._load()

    def _selected_books(self) -> list[str]:
        return [cb.text() for cb in self._book_checkboxes if cb.isChecked()]

    def _toggle_all_books(self):
        if not self._book_checkboxes:
            return
        all_checked = all(cb.isChecked() for cb in self._book_checkboxes)
        for cb in self._book_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(not all_checked)
            cb.blockSignals(False)
        self._update_save_enabled()

    def _update_save_enabled(self):
        has_topic = self.topic.currentData() is not None
        has_books = len(self._selected_books()) > 0
        self.save_btn.setEnabled(bool(has_topic and has_books))

    def _quick_add_student_topic(self):
        text, ok = QInputDialog.getText(
            self,
            'Öğrenciye Özel Konu Ekle',
            f'Öğrenci #{self.student_id} ({self.lesson}) için özel konu başlığı yazın:\n'
            '(Örn: Atışlar Özel, Paragrafta İkilemeler, Çıkmış Soru Kampı vb.)'
        )
        topic_name = (text or '').strip()
        if not ok or not topic_name:
            return
        try:
            import db
            con = db.get_conn()
            con.execute("""
                CREATE TABLE IF NOT EXISTS ogrenci_konu_duzen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ogrenci_id INTEGER NOT NULL,
                    ders TEXT NOT NULL,
                    konu TEXT NOT NULL,
                    ort_soru INTEGER,
                    ort_sure INTEGER,
                    UNIQUE(ogrenci_id, ders, konu)
                )
            """)
            con.execute(
                "INSERT OR IGNORE INTO ogrenci_konu_duzen (ogrenci_id, ders, konu, ort_soru, ort_sure) VALUES (?, ?, ?, ?, ?)",
                (self.student_id, self.lesson, topic_name, 20, self.minutes.value())
            )
            con.commit()
            self._load()
            for i in range(self.topic.count()):
                data = self.topic.itemData(i)
                if isinstance(data, tuple) and len(data) == 2 and str(data[1]).strip().casefold() == topic_name.casefold():
                    self.topic.setCurrentIndex(i)
                    break
        except Exception as exc:
            QMessageBox.warning(self, 'Özel Konu Eklenemedi', str(exc))

    def _quick_add_student_book(self):
        text, ok = QInputDialog.getText(
            self,
            'Öğrenciye Kitap Ekle',
            f'Öğrenci #{self.student_id} ({self.lesson}) için kaynak kitap adı yazın:'
        )
        book_name = (text or '').strip()
        if not ok or not book_name:
            return
        try:
            import db
            con = db.get_conn()
            exists = con.execute(
                "SELECT 1 FROM ogrenci_kitap WHERE ogrenci_id=? AND LOWER(TRIM(ders))=LOWER(TRIM(?)) AND LOWER(TRIM(kitap_ad))=LOWER(TRIM(?))",
                (self.student_id, self.lesson, book_name)
            ).fetchone()
            if not exists:
                con.execute(
                    "INSERT INTO ogrenci_kitap (ogrenci_id, ders, kitap_ad) VALUES (?, ?, ?)",
                    (self.student_id, self.lesson, book_name)
                )
                con.commit()
            self._load(newly_added_book=book_name)
        except Exception as exc:
            QMessageBox.warning(self, 'Kitap Eklenemedi', str(exc))

    def _load(self, newly_added_book: str | None = None):
        try:
            import db
            con = db.get_conn()
            previous_topic = self.topic.currentData()
            previously_checked = set(self._selected_books())
            if newly_added_book:
                previously_checked.add(newly_added_book)

            options = available_scoped_topics(con, student_id=self.student_id, lesson=self.lesson)
            books = available_books(con, student_id=self.student_id, lesson=self.lesson)
            records = list_assignments(con, student_id=self.student_id, lesson=self.lesson)

            self.topic.blockSignals(True)
            self.topic.clear()
            if options:
                for opt in options:
                    self.topic.addItem(f'{opt.source} · {opt.title}', (opt.reference, opt.title))
            else:
                self.topic.addItem("— Henüz özel konu yok ('➕ Konu Ekle' ile ekleyin) —", None)
            if previous_topic is not None:
                for i in range(self.topic.count()):
                    if self.topic.itemData(i) == previous_topic:
                        self.topic.setCurrentIndex(i)
                        break
            self.topic.blockSignals(False)

            # Kitap checkbox'larını yenile
            while self.books_lay.count():
                item = self.books_lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._book_checkboxes.clear()
            self.book.clear()

            if books:
                self.book.addItems(books)
                for idx, b_name in enumerate(books):
                    cb = QCheckBox(b_name)
                    cb.setStyleSheet(
                        'QCheckBox { font-size: 11.5px; font-weight: 600; color: #0f172a; '
                        'background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; }'
                        'QCheckBox:checked { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }'
                    )
                    # İlk açılışta ilk kitabı seçili getir, önceden seçim varsa onları koru
                    should_check = (b_name in previously_checked) if previously_checked else (idx == 0)
                    cb.setChecked(should_check)
                    cb.toggled.connect(self._update_save_enabled)
                    self.books_lay.addWidget(cb)
                    self._book_checkboxes.append(cb)
                self.books_lay.addStretch(1)
                self.btn_toggle_books.setVisible(len(books) > 1)
            else:
                lbl_no_book = QLabel("<span style='color:#64748b;'>Bu derste kayıtlı kitap yok ('📚 Kitap Ekle' ile ekleyin)</span>")
                self.books_lay.addWidget(lbl_no_book)
                self.books_lay.addStretch(1)
                self.btn_toggle_books.setVisible(False)

            missing = []
            if not options:
                missing.append("<b>➕ Konu Ekle</b> ile özel konu tanımlayın")
            if not books:
                missing.append("<b>📚 Kitap Ekle</b> ile kaynak kitap ekleyin")
            if missing:
                self.status_hint.setText("ℹ️ Ödev verebilmek için " + " ve ".join(missing) + ".")
                self.status_hint.setVisible(True)
            else:
                self.status_hint.setVisible(False)

            self._update_save_enabled()

            self._updating_table = True
            self.table.setRowCount(len(records))
            for row, rec in enumerate(records):
                vals = (rec.topic_title, rec.source, rec.book, rec.due_date, _STATUS_LABELS.get(rec.status, rec.status))
                for col, value in enumerate(vals):
                    cell = QTableWidgetItem(str(value))
                    if col == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, rec.id)
                        cell.setData(Qt.ItemDataRole.UserRole + 1, rec.status)
                    if col == 4:
                        cell.setFlags(
                            Qt.ItemFlag.ItemIsSelectable
                            | Qt.ItemFlag.ItemIsEnabled
                            | Qt.ItemFlag.ItemIsUserCheckable
                        )
                        cell.setCheckState(
                            Qt.CheckState.Checked if rec.status == 'tamam' else Qt.CheckState.Unchecked
                        )
                        cell.setToolTip('Kutucuğu işaretleyerek doğrudan Tamamlandı / Açık durumuna geçirebilirsiniz.')
                    if rec.status == 'tamam':
                        cell.setBackground(QColor('#f0fdf4'))
                        cell.setForeground(QColor('#166534'))
                    elif rec.status == 'iptal':
                        cell.setBackground(QColor('#fef2f2'))
                        cell.setForeground(QColor('#991b1b'))
                    self.table.setItem(row, col, cell)
            self._updating_table = False
        except Exception as exc:
            self._updating_table = False
            self.save_btn.setEnabled(False)
            QMessageBox.warning(self, 'Kapsam ödevi', f'Veriler güvenli okunamadı: {exc}')

    def _on_table_item_changed(self, item: QTableWidgetItem):
        """Durum sütunundaki checkbox tıklandığında onay penceresi sormadan hızlıca durumu değiştir."""
        if self._updating_table or item.column() != 4:
            return
        row = item.row()
        first_cell = self.table.item(row, 0)
        if first_cell is None:
            return
        assignment_id = first_cell.data(Qt.ItemDataRole.UserRole)
        prior_status = first_cell.data(Qt.ItemDataRole.UserRole + 1)
        target_status = 'tamam' if item.checkState() == Qt.CheckState.Checked else 'devam'
        if prior_status == target_status:
            return
        try:
            import db
            con = db.get_conn()
            set_scoped_control_status(
                con,
                student_id=self.student_id,
                assignment_id=int(assignment_id),
                expected_status=str(prior_status),
                new_status=target_status,
            )
        except Exception as exc:
            QMessageBox.warning(self, 'Durum Güncellenemedi', str(exc))
        self._load()

    def _save(self):
        selection = self.topic.currentData()
        selected_books = self._selected_books()
        if not selection or not selected_books:
            QMessageBox.warning(self, 'Eksik seçim', 'Lütfen bir kapsam konusu ve en az bir kitap seçiniz.')
            return
        books_str = ', '.join(selected_books)
        if QMessageBox.question(
            self,
            'Ödev onayı',
            f'{self.topic.currentText()} konusu için seçilen {len(selected_books)} kitaptan ({books_str}) ayrı kapsam ödevi oluşturulsun mu?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        added = 0
        errors = []
        import db
        con = db.get_conn()
        for book in selected_books:
            try:
                create_assignment(
                    con,
                    student_id=self.student_id,
                    lesson=self.lesson,
                    topic_reference=selection[0],
                    expected_title=selection[1],
                    book=book,
                    minutes=self.minutes.value(),
                    due_date=self.due.date().toString('yyyy-MM-dd'),
                )
                added += 1
            except Exception as exc:
                errors.append(f'{book}: {exc}')
        self._load()
        if errors and added == 0:
            QMessageBox.warning(self, 'Ödev oluşturulamadı', '\n'.join(errors))
        elif errors:
            QMessageBox.information(
                self,
                'Kısmi Kayıt',
                f'{added} kitap için ödev eklendi.\nAtlananlar:\n' + '\n'.join(errors)
            )

    def _change(self, target_status: str):
        row = self.table.currentRow()
        cell = self.table.item(row, 0) if row >= 0 else None
        if cell is None:
            QMessageBox.information(self, 'Seçim', 'Önce tablodan bir kapsam ödevi satırı seçiniz.')
            return
        assignment_id = int(cell.data(Qt.ItemDataRole.UserRole))
        prior_status = str(cell.data(Qt.ItemDataRole.UserRole + 1) or 'devam')
        if prior_status == target_status:
            QMessageBox.information(self, 'Bilgi', f'Seçili ödev zaten “{_STATUS_LABELS.get(target_status, target_status)}” durumunda.')
            return

        try:
            import db
            con = db.get_conn()
            # Eğer 'tamam' durumundaki bir ödev doğrudan 'iptal' edilmek istenirse (veya tersi),
            # önce 'devam' durumuna alıp ardından hedef duruma geçirerek hatayı önle.
            if prior_status in ('tamam', 'iptal') and target_status in ('tamam', 'iptal'):
                set_scoped_control_status(
                    con,
                    student_id=self.student_id,
                    assignment_id=assignment_id,
                    expected_status=prior_status,
                    new_status='devam',
                )
                prior_status = 'devam'

            set_scoped_control_status(
                con,
                student_id=self.student_id,
                assignment_id=assignment_id,
                expected_status=prior_status,
                new_status=target_status,
            )
        except Exception as exc:
            QMessageBox.warning(self, 'İşlem tamamlanmadı', str(exc))
            return
        self._load()
