# -*- coding: utf-8 -*-
"""V24.3 – Hedef Analizi içinde küçük, salt okunur koçluk özeti."""
from __future__ import annotations

from contextlib import closing
import sqlite3
from urllib.parse import quote

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout,
)

from services.target_analysis_v24.coaching_bridge_v243 import (
    read_coaching_brief, render_coaching_brief,
)


class TargetCoachingBriefDialog(QDialog):
    def __init__(self, student_id: int, *, draft_target_name: str | None = None, parent=None):
        super().__init__(parent)
        self.student_id = student_id
        self.draft_target_name = draft_target_name
        self.setWindowTitle('Öğrenci 360° – Hedef ve Koçluk Özeti (Salt Okunur)')
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(700, max(360, available.width() - 48)),
                        min(610, max(330, available.height() - 64)))
            self.setMinimumSize(min(360, available.width()), min(320, available.height()))
        layout = QVBoxLayout(self)
        description = QLabel('Kayıtlı hedef, deneme ve ödev bilgileri birlikte gösterilir. '
                             'Bu ekran hiçbir öğrenci, hedef veya ödev kaydı değiştirmez.')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.content = QTextEdit()
        self.content.setReadOnly(True)
        self.content.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.content, 1)
        bar = QHBoxLayout()
        self.btn_refresh = QPushButton('↻ Özeti Yenile')
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        self.btn_copy = QPushButton('Özeti Kopyala')
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        bar.addWidget(self.btn_copy)
        secondary_bar = QHBoxLayout()
        self.btn_study_v244 = QPushButton('Çalışma Taslağı')
        self.btn_study_v244.setToolTip('Salt okunur kaynaklardan öğretmenin seçeceği taslak; ödev kaydetmez.')
        self.btn_study_v244.clicked.connect(self.open_study_draft_v244)
        secondary_bar.addWidget(self.btn_study_v244)
        self.btn_goal_audit_v245 = QPushButton('Veri Kontrolü')
        self.btn_goal_audit_v245.setToolTip('Öğrenci, deneme ve resmî kaynak kaydı salt okunur denetlenir.')
        self.btn_goal_audit_v245.clicked.connect(self.open_goal_audit_v245)
        secondary_bar.addWidget(self.btn_goal_audit_v245)
        secondary_bar.addStretch(1)
        bar.addStretch(1)
        close = QPushButton('Kapat')
        close.clicked.connect(self.accept)
        bar.addWidget(close)
        layout.addLayout(bar)
        layout.addLayout(secondary_bar)
        self.refresh()

    def refresh(self):
        from db import DB_PATH
        try:
            # db.get_conn() ile paylaşılan bağlantı açmayın; ana uygulamanın
            # bağlantı PRAGMA/transaction durumunu bozmayın.
            uri = 'file:' + quote(str(DB_PATH.resolve()), safe='/') + '?mode=ro'
            with closing(sqlite3.connect(uri, uri=True, timeout=8)) as con:
                con.execute('PRAGMA query_only=ON')
                brief = read_coaching_brief(con, self.student_id)
            output = render_coaching_brief(brief, draft_target_name=self.draft_target_name)
            self.content.setPlainText(output)
        except (ValueError, sqlite3.Error, OSError) as exc:
            self.content.setPlainText('Bu öğrenciye ait koçluk özeti güvenle okunamadı: '\
                                      + str(exc) + '\nHiçbir kayıt değiştirilmedi.')

    def copy_to_clipboard(self):
        # Öğrenci bilgileri sadece öğretmenin açık eylemi üzerine kopyalanır.
        QApplication.clipboard().setText(self.content.toPlainText())

    def open_study_draft_v244(self):
        from ui.target_study_draft_v244 import TargetStudyDraftDialog
        TargetStudyDraftDialog(self.student_id, parent=self).exec()

    def open_goal_audit_v245(self):
        from ui.target_goal_audit_v245 import TargetGoalAuditDialog
        TargetGoalAuditDialog(self.student_id, parent=self).exec()
