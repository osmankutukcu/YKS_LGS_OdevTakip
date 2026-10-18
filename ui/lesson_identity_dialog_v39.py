from __future__ import annotations
"""V39: Öğretmenler için ders adı/kodu açıklaması; yazma işlemi yoktur."""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit)
from PyQt6.QtCore import Qt
from pathlib import Path
from contextlib import closing
import sqlite3
import db
from services.lesson_catalog_v39 import inspect_lesson_identities


class LessonIdentityDialogV39(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Ders Adları ve Bağlantıları • Sadece Görüntüleme')
        self.resize(850, 570)
        layout = QVBoxLayout(self)
        title = QLabel('Ders adı ile ders kodu neden farklı olabilir?')
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        help_text = QLabel(
            'Ders adı öğretmenin gördüğü etikettir; ders kodu ise kitap ve ödevlerin '
            'bağlandığı değişmeyen kimliktir. Pasif ve geçmiş dersler de burada '
            'görünebilir. Hiçbir öğrenci, kitap, koçluk veya ödev kaydı değiştirilmez.'
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(['Ders adı', 'Ders kodu', 'Durum', 'Koçluk kaydı'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setAccessibleName('Ders adları, kalıcı kodlar ve eşleşen koçluk kayıtları')
        layout.addWidget(self.table, 1)
        self.notes = QPlainTextEdit(self)
        self.notes.setReadOnly(True)
        self.notes.setMaximumHeight(120)
        layout.addWidget(self.notes)
        actions = QHBoxLayout()
        refresh = QPushButton('Listeyi Yenile')
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        actions.addStretch(1)
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        path = Path(db.DB_PATH).expanduser().resolve()
        if not path.is_file():
            self.notes.setPlainText('Veritabanı bulunamadı. Hiçbir kayıt oluşturulmadı.')
            return
        try:
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as con:
                con.execute('PRAGMA query_only=ON')
                con.execute('BEGIN')
                result = inspect_lesson_identities(con, legacy=db.DERS_TABLOLARI)
        except (sqlite3.Error, OSError, ValueError) as exc:
            self.notes.setPlainText(f'Liste okunamadı: {exc}. Hiçbir kayıt değiştirilmedi.')
            return
        matched = dict(result.coaching_counts)
        self.table.setRowCount(len(result.options))
        for idx, lesson in enumerate(result.options):
            status = ('Aktif' if lesson.active else 'Pasif') if lesson.catalogued else 'Eski kod'
            for col, value in enumerate((lesson.name, lesson.code, status,
                                         str(matched.get(lesson.code, 0)))):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(idx, col, item)
        notices = [f'Koçluk kaydı: {result.total_coaching}. '
                   f'Kesin eşleşmeyen etiket sayısı: {len(result.unresolved_coaching)}.']
        if result.unresolved_coaching:
            notices.append('Kontrol gerektiren etiketler: ' + ', '.join(
                f'{name or "(boş)"} ({count})' for name, count in result.unresolved_coaching[:12]))
        if result.legacy_codes:
            notices.append('Katalog dışı ama geçmiş kaydı bulunan kodlar: ' +
                           ', '.join(result.legacy_codes[:12]))
        notices.append('Belirsiz kayıtlar otomatik birleştirilmez; geçmiş veriler korunur.')
        self.notes.setPlainText('\n'.join(notices))
