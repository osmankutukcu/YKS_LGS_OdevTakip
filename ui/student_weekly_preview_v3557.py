# -*- coding: utf-8 -*-
"""V3557: existing simulation window opens this *separate*, non-writing preview.

Main dashboard and existing Homework/Control UIs are untouched.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel, QVBoxLayout,
                             QHBoxLayout, QPushButton, QPlainTextEdit)
from services.weekly_exam_plan_v3557 import WeeklyPlanDraft


class WeeklyPlanPreviewDialog(QDialog):
    def __init__(self, plan: WeeklyPlanDraft, parent=None):
        super().__init__(parent)
        self._plan = plan
        self.setWindowTitle('Haftalık Çalışma Planı — Salt Okunur Önizleme')
        self.resize(760, 620)
        self.setMinimumSize(510, 380)
        self.setStyleSheet('''
            QDialog { background-color:#0b1220; }
            QLabel { color:#e2e8f0; }
            QPlainTextEdit { color:#e2e8f0; background-color:#111e32;
                border:1px solid #334155; border-radius:8px; padding:12px;
                font-family:monospace; font-size:12px; }
            QPushButton { color:white; background-color:#1d4ed8; border:1px solid #2563eb;
                border-radius:7px; padding:9px 14px; font-weight:600; }
            QPushButton:hover { background-color:#2563eb; }
        ''')
        root = QVBoxLayout(self)
        header = QLabel(f'📘 {plan.exam} · {plan.student_label} · Kişisel Haftalık Plan')
        header.setStyleSheet('font-size:17px;font-weight:800;')
        root.addWidget(header)
        state = ('Tüm başlıklar plana sığdı.' if not plan.unscheduled else
                 f'{plan.unscheduled} başlık plan dışında kaldı; haftalık tempo veya süreyi yeniden değerlendirin.')
        notice = QLabel(f'Önerilen {plan.planned}/{plan.candidates} başlık · {state}')
        notice.setWordWrap(True)
        notice.setStyleSheet('color:#fbbf24; font-size:12px;')
        root.addWidget(notice)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(plan.to_text())
        root.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        explain = QLabel('Bu pencerede veri kaydedilmez, ödev atanmaz.')
        explain.setStyleSheet('font-size:11px; color:#94a3b8;')
        actions.addWidget(explain, 1)
        copy_btn = QPushButton('Metni Kopyala')
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self._plan.to_text()))
        actions.addWidget(copy_btn)
        close_btn = QPushButton('Kapat')
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        root.addLayout(actions)
