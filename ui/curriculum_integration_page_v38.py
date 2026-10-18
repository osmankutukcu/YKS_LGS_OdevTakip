# -*- coding: utf-8 -*-
from __future__ import annotations
"""V38: Ayarlar içinde salt-okunur bağlantı önizlemesi; çekirdek ekranları değiştirmez."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit, QLineEdit
)
import db
from services.curriculum_integration_audit_v38 import inspect_group_curriculum, search_key


class CurriculumIntegrationPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        title = QLabel('Derslerin diğer modüllerle bağlantısını kontrol edin')
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)
        guide = QLabel(
            'Bu bölüm yalnızca bilgi gösterir. Ders ataması yapmak için “Gruplara Ata”, '
            'konuları değiştirmek için “Konuları Düzenle” bölümünü kullanın. '
            'Ödev Takip veya Ödev Kontrol kayıtları burada değiştirilemez. Grup atamada kaydedilmemiş seçimler bu önizlemeye yansımaz.'
        )
        guide.setWordWrap(True)
        root.addWidget(guide)

        bar = QHBoxLayout()
        bar.addWidget(QLabel('Öğrenci grubu:'))
        self.group = QComboBox()
        self.group.setAccessibleName('Bağlantı kontrolü öğrenci grubu')
        self.group.setMinimumWidth(160)
        self.group.currentIndexChanged.connect(self._load)
        bar.addWidget(self.group, 1)
        self.button = QPushButton('Yeniden Kontrol Et')
        self.button.clicked.connect(self.refresh)
        bar.addWidget(self.button)
        # V39: Sadece görüntüleyen açıklama penceresi. Bu sekmenin kayıt davranışı değişmez.
        self.btnIdentity = QPushButton('Ders Adı / Kodu Rehberi')
        self.btnIdentity.setToolTip('Kitap, rapor ve koçlukta kullanılan ders kimliklerini inceleyin')
        self.btnIdentity.clicked.connect(self._show_identity_guide)
        bar.addWidget(self.btnIdentity)
        root.addLayout(bar)
        filters = QHBoxLayout()
        filters.addWidget(QLabel('Görünüm:'))
        self.scope = QComboBox()
        self.scope.addItems(['Grubun etkin dersleri', 'Tüm dersler', 'Geçmiş kaydı olan diğer dersler'])
        self.scope.currentIndexChanged.connect(self._render)
        filters.addWidget(self.scope)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Ders adı veya kodu ara...')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._render)
        filters.addWidget(self.search, 1)
        root.addLayout(filters)
        self.summary = QLabel('Kontrol için bir grup seçin.')
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            'Ders', 'Durum', 'Konu', 'Kitap havuzu', 'Öğrenci kitabı',
            'Ödev / satır', 'Koçluk', 'Ders kodu'
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setAccessibleName('Derslerin grup, kitap, ödev ve koçluk bağlantı özeti')
        root.addWidget(self.table, 1)

        root.addWidget(QLabel('Açıklamalar ve dikkat edilmesi gerekenler'))
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMinimumHeight(115)
        self.notes.setMaximumHeight(180)
        self.notes.setAccessibleName('Bağlantı kontrolü uyarıları')
        root.addWidget(self.notes)
        self._loaded = False
        self._snapshot = None

    def _show_identity_guide(self):
        from ui.lesson_identity_dialog_v39 import LessonIdentityDialogV39
        LessonIdentityDialogV39(self).exec()

    def refresh(self):
        """Sekme açıldığında en güncel veriyi okur; kayıt yapmaz."""
        current = self.group.currentData() or self.group.currentText()
        try:
            groups = db.get_curriculum_groups()
            names = [name for values in groups.values() for name in values]
            names = list(dict.fromkeys(names))
        except Exception as exc:
            self.summary.setText('Grup listesi okunamadı.')
            self.notes.setPlainText(str(exc))
            return
        self.group.blockSignals(True)
        self.group.clear()
        for g in names:
            self.group.addItem(g, g)
        pos = self.group.findData(current)
        if pos >= 0:
            self.group.setCurrentIndex(pos)
        self.group.blockSignals(False)
        self._loaded = True
        self._load()

    def _load(self, *_):
        if not self._loaded:
            return
        name = self.group.currentData()
        self._snapshot = None
        self.table.setRowCount(0)
        if not name:
            self.summary.setText('Öğrenci grubu seçin.')
            return
        try:
            snapshot = inspect_group_curriculum(
                db.DB_PATH, name,
                group_defaults=db.DEFAULT_GRUP_DERSLER,
                standard_groups=db.CURRICULUM_GROUPS
            )
        except (OSError, ValueError, RuntimeError) as exc:
            self.summary.setText(f'Bağlantı denetimi tamamlanamadı: {exc}')
            self.notes.setPlainText('Hiçbir kayıt değiştirilmedi. Veritabanı ve bağlantı izinlerini kontrol edin.')
            return
        except Exception as exc:
            self.summary.setText('Bağlantı önizlemesi beklenmeyen nedenle gösterilemedi.')
            self.notes.setPlainText(f'Kayıtlar değiştirilmedi. Hata türü: {type(exc).__name__}')
            return
        active = sum(item.assigned for item in snapshot.rows)
        self.summary.setText(
            f'{snapshot.group} • {snapshot.main_group} • {snapshot.assignment_mode} atama • '
            f'{snapshot.student_count} kayıtlı öğrenci • {active} etkin ders'
        )
        self._snapshot = snapshot
        self._render()
        text = []
        if snapshot.warnings:
            text.extend('Kontrol gerektiriyor: ' + warning for warning in snapshot.warnings)
        else:
            text.append('Katalog ve grup bağlantılarında otomatik kontrolün görebildiği bir tutarsızlık bulunmadı.')
        text.extend('Bilgi: ' + note for note in snapshot.notices)
        self.notes.setPlainText('\n\n'.join(text))

    def _render(self, *_):
        snapshot = self._snapshot
        if snapshot is None:
            return
        query = search_key(self.search.text().strip())
        scope = self.scope.currentIndex()
        rows = [lesson for lesson in snapshot.rows
                if (scope == 1 or (lesson.assigned if scope == 0 else
                    not lesson.assigned and (lesson.assigned_books or lesson.homework or
                                             lesson.homework_rows or lesson.coaching_topics)))
                and query in search_key(lesson.name + ' ' + lesson.lesson_id)]
        self.table.setRowCount(len(rows))
        for row_index, lesson in enumerate(rows):
            has_history = bool(lesson.assigned_books or lesson.homework or
                               lesson.homework_rows or lesson.coaching_topics)
            status = ('Görünüyor' if lesson.assigned else
                      'Pasif • geçmiş var' if not lesson.active and has_history else
                      'Pasif' if not lesson.active else
                      'Atanmamış • geçmiş var' if has_history else 'Gruba atanmadı')
            values = (
                lesson.name, status,
                str(lesson.topic_count) if lesson.topic_count is not None else '—',
                str(lesson.pool_books), str(lesson.assigned_books),
                f'{lesson.homework} / {lesson.homework_rows}',
                str(lesson.coaching_topics), lesson.lesson_id,
            )
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col in (2, 3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col, item)
