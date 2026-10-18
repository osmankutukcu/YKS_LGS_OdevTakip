# -*- coding: utf-8 -*-
"""Optional, collapsible teacher guide inside the existing coaching note tab.

This widget does not read or write databases, dispatch assignments, send
WhatsApp messages, or save notes. It only inserts a teacher-selected prompt
into the existing editable agenda/actions QTextEdit field.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from services.srl_grow_guide_v6 import PHASES, phase, append_prompt


class SrlGrowGuideV6(QWidget):
    def __init__(self, *, student_selected, agenda, actions, parent=None):
        super().__init__(parent)
        self._student_selected = student_selected
        self._agenda = agenda
        self._actions = actions
        self.setObjectName('SrlGrowGuideV6')
        self.setStyleSheet('''
            QWidget#SrlGrowGuideV6 { background: #f8fafc;
              border: 1px solid #dbeafe; border-radius: 8px; }
            QLabel { border: none; background: transparent; color: #334155; }
            QPushButton { border: 1px solid #cbd5e1; background: #fff;
              color: #1e40af; padding: 5px 9px; border-radius: 5px; }
        ''')
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(6)
        row = QHBoxLayout()
        self.phase_combo = QComboBox(self)
        for p in PHASES:
            self.phase_combo.addItem(p.title, p.key)
        self.phase_combo.setToolTip('Görüşme aşamasını seçin. Bu seçim veritabanına kaydedilmez.')
        self.phase_combo.currentIndexChanged.connect(self._set_phase)
        row.addWidget(QLabel('Görüşme adımı:'))
        row.addWidget(self.phase_combo, 1)
        box.addLayout(row)

        self.help_text = QLabel(self)
        self.help_text.setWordWrap(True)
        box.addWidget(self.help_text)
        self.question_combo = QComboBox(self)
        self.question_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self.question_combo.setToolTip('Öğrenciyle konuşurken sorulabilecek isteğe bağlı soru')
        box.addWidget(self.question_combo)

        controls = QHBoxLayout()
        agenda_btn = QPushButton('Gündem notuna ekle', self)
        agenda_btn.setToolTip('Kaydetmez; yalnızca mevcut gündem notuna seçilen soruyu ekler.')
        agenda_btn.clicked.connect(lambda: self._insert(self._agenda))
        controls.addWidget(agenda_btn)
        action_btn = QPushButton('Aksiyon notuna ekle', self)
        action_btn.setToolTip('Kaydetmez; yalnızca mevcut aksiyon notuna seçilen soruyu ekler.')
        action_btn.clicked.connect(lambda: self._insert(self._actions))
        controls.addWidget(action_btn)
        controls.addStretch()
        box.addLayout(controls)
        self.status = QLabel('Kayıt yapılmaz. Notu düzenleyip mevcut Kaydet düğmesini kullanın.', self)
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        self._set_phase()

    def _set_phase(self, *_):
        p = phase(self.phase_combo.currentData() or PHASES[0].key)
        self.help_text.setText(f'{p.aim}  •  {p.next_step}')
        self.question_combo.clear()
        self.question_combo.addItems(p.questions)
        self.status.setText('Bu rehber karar vermez veya kaydetmez; öğretmenin seçimine yardımcı olur.')

    def _insert(self, editor):
        if not self._student_selected():
            self.status.setText('Önce öğrenci seçin; başka bir öğrencinin notuna ekleme yapılmadı.')
            return
        current = editor.toPlainText()
        next_text = append_prompt(current, self.question_combo.currentText(),
                                  phase_key=self.phase_combo.currentData())
        if next_text == current.rstrip():
            self.status.setText('Bu soru zaten bu notta var; ikinci kez eklenmedi.')
            return
        editor.setPlainText(next_text)
        editor.setFocus(Qt.FocusReason.OtherFocusReason)
        editor.moveCursor(QTextCursor.MoveOperation.End)
        self.status.setText('Soru not alanına eklendi (henüz kaydedilmedi).')
