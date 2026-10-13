# -*- coding: utf-8 -*-
"""V24.4 – seçilebilir, kaydetmeyen koçluk/çalışma taslağı penceresi."""
from __future__ import annotations
from contextlib import closing
import sqlite3
from urllib.parse import quote

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
    QCheckBox, QPushButton, QHBoxLayout, QPlainTextEdit, QMessageBox, QLineEdit,
)

from services.target_analysis_v24.study_draft_v244 import read_study_draft, render_selected_draft


class TargetStudyDraftDialog(QDialog):
    def __init__(self, student_id: int, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self._draft = None
        self._checks: list[tuple[str, QCheckBox, QWidget]] = []
        self._preview_text = None
        self.setWindowTitle('Öğrenci 360° – Öğretmen Kontrollü Çalışma Taslağı')
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.resize(min(750, max(330, area.width() - 50)), min(660, max(320, area.height() - 70)))
            self.setMinimumSize(min(340, area.width()), min(300, area.height()))
        lay = QVBoxLayout(self)
        label = QLabel('Veri kanıtlarına göre öneriler. Öğretmen seçmedikçe taslak üretilmez; '
                       'ödev, tik, hedef veya koçluk kayıtlarına yazılmaz.')
        label.setWordWrap(True)
        lay.addWidget(label)
        self.list_area = QScrollArea()
        self.list_area.setWidgetResizable(True)
        self.items_root = QWidget()
        self.items_layout = QVBoxLayout(self.items_root)
        self.items_layout.addStretch(1)
        self.list_area.setWidget(self.items_root)
        lay.addWidget(self.list_area, 2)
        self.note = QLineEdit()
        self.note.setMaxLength(500)
        self.note.setPlaceholderText('İsteğe bağlı öğretmen notu (taslakta kalır)')
        self.note.textChanged.connect(self._invalidate)
        lay.addWidget(self.note)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText('Seçilen öneriler burada görüntülenecek.')
        lay.addWidget(self.preview, 2)
        self.approve = QCheckBox('Seçtiğim önerileri ve öğrenci bilgilerini kontrol ettim')
        self.approve.stateChanged.connect(self._update_copy)
        lay.addWidget(self.approve)
        bar = QVBoxLayout()
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        self.btn_refresh = QPushButton('↻ Kaynakları Yenile')
        self.btn_refresh.clicked.connect(self.refresh)
        row1.addWidget(self.btn_refresh)
        self.btn_preview = QPushButton('Seçilenleri Önizle')
        self.btn_preview.clicked.connect(self.build_preview)
        row1.addWidget(self.btn_preview)
        self.btn_copy = QPushButton('Onaylı Taslağı Kopyala')
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self.copy_draft)
        row2.addWidget(self.btn_copy)
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        row2.addWidget(close)
        bar.addLayout(row1)
        bar.addLayout(row2)
        lay.addLayout(bar)
        self.refresh()

    def _invalidate(self):
        self._preview_text = None
        self.preview.clear()
        self.approve.setChecked(False)
        self.btn_copy.setEnabled(False)

    def _update_copy(self):
        self.btn_copy.setEnabled(bool(self._preview_text and self.approve.isChecked()))

    def refresh(self):
        from db import DB_PATH
        self._invalidate()
        for _, checkbox, widget in self._checks:
            self.items_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._checks = []
        self._draft = None
        try:
            uri = 'file:' + quote(str(DB_PATH.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=8)) as con:
                con.execute('PRAGMA query_only=ON')
                draft = read_study_draft(con, self.student_id)
            if draft.student_id != self.student_id:
                raise ValueError('Öğrenci eşleşmesi bulunamadı.')
            self._draft = draft
            for action in draft.actions:
                widget = QWidget()
                item_lay = QVBoxLayout(widget)
                item_lay.setContentsMargins(6, 4, 6, 5)
                check = QCheckBox(action.title)
                check.setToolTip(action.evidence_source)
                check.toggled.connect(self._invalidate)
                item_lay.addWidget(check)
                desc = QLabel('Gerekçe: ' + action.reason + '\nÖneri: ' + action.proposed_step)
                desc.setTextFormat(Qt.TextFormat.PlainText)
                desc.setWordWrap(True)
                item_lay.addWidget(desc)
                self.items_layout.insertWidget(self.items_layout.count() - 1, widget)
                self._checks.append((action.action_id, check, widget))
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.preview.setPlainText('Taslak güvenle okunamadı: ' + str(exc) + '\nHiçbir kayıt değiştirilmedi.')
            self.btn_preview.setEnabled(False)
            return
        self.btn_preview.setEnabled(True)

    def build_preview(self):
        if self._draft is None or self._draft.student_id != self.student_id:
            return
        selected = tuple(action_id for action_id, checkbox, _ in self._checks if checkbox.isChecked())
        try:
            self._preview_text = render_selected_draft(self._draft, selected, teacher_note=self.note.text())
            self.preview.setPlainText(self._preview_text)
            self._update_copy()
        except ValueError as exc:
            self._invalidate()
            QMessageBox.information(self, 'Taslak seçimi', str(exc))

    def copy_draft(self):
        # Veri yalnız açık öğretmen eylemiyle, değişmeyen önizlemeden kopyalanır.
        if self._draft is None or self._draft.student_id != self.student_id:
            return
        if self.approve.isChecked() and self._preview_text:
            QApplication.clipboard().setText(self._preview_text)
